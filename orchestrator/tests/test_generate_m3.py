"""M3 Generate backend: serialisation per model, effective params, references, staging, ETA, preview endpoint."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState
from loom2.engine import graphs
from loom2.recipes import T2I, parse_recipe
from loom2.roster import Roster

TREE = {"scene": "a rainy alley", "subjects": [{"description": "a woman in a green cloak", "action": "turning", "color_match": "exact"}],
        "style": "painterly", "color_palette": ["#0E1B2A"], "camera": {"angle": "low angle", "lens": "35mm"}, "mood": ""}


def _tree(tmp_path: Path) -> Roster:
    root = tmp_path / "models"
    for rel in ("diffusion_models/flux2_dev_fp8mixed.safetensors", "diffusion_models/flux-2-klein-9b.safetensors", "diffusion_models/flux-2-klein-base-9b.safetensors",
                "text_encoders/mistral_3_small_flux2_fp8.safetensors", "text_encoders/qwen_3_8b_fp8mixed.safetensors", "vae/flux2-vae.safetensors", "loras/Flux2TurboComfyv2.safetensors"):
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"x")
    return Roster(root).scan()


def test_serialisation_per_model():
    dev = T2I(prompt_mode="tree", prompt_json=TREE)
    text, mode = graphs.serialize_prompt(dev)
    assert mode == "json" and json.loads(text)["scene"] == "a rainy alley" and "mood" not in json.loads(text)   # empty fields dropped, compact
    klein = T2I(model_id="klein-9b", prompt_mode="tree", prompt_json=TREE, prompt_text="storyboard frame")
    text, mode = graphs.serialize_prompt(klein)
    assert mode == "prose" and text.startswith("storyboard frame. scene: a rainy alley") and "low angle, 35mm" in text
    plain = T2I(prompt_mode="text", prompt_text="just words", prompt_json=TREE)
    assert graphs.serialize_prompt(plain) == ("just words", "text")


def test_effective_params_rules():
    ep = graphs.effective_params(T2I(prompt_json=TREE, turbo=True, sampler="res_multistep", scheduler="sgm_uniform", width=950, height=540))
    assert ep["steps"] == 8 and ep["sampler"] == "res_multistep" and ep["scheduler"] == "sgm_uniform" and (ep["width"], ep["height"]) == (944, 544)
    ep = graphs.effective_params(T2I(model_id="klein-9b", prompt_text="x", steps=30, cfg=5, negative="blurry"))
    assert ep["steps"] == 4 and ep["cfg"] == 1.0 and ep["negative_used"] is False and ep["sampler"] == "euler" and ep["distilled"]
    with pytest.raises(graphs.CompileError, match="unknown sampler"):            # 2026-10-06: no silent fall-back to the preset
        graphs.effective_params(T2I(model_id="klein-9b", prompt_text="x", sampler="bogus"))
    ep = graphs.effective_params(T2I(model_id="klein-base-9b", prompt_text="x", negative="blurry"))
    assert ep["steps"] == 20 and ep["cfg"] == 3.5 and ep["negative_used"] is True
    assert ep["word_count"] == 1 and ep["token_estimate"] >= 8
    with pytest.raises(graphs.CompileError):
        graphs.effective_params(T2I(prompt_text="x", width=4000, height=4000))


def test_compile_with_references(tmp_path: Path, object_info: dict):
    roster = _tree(tmp_path)
    import copy
    object_info = copy.deepcopy(object_info)
    object_info["LoadImage"]["input"]["required"]["image"][0] += ["loom2_refs/a.png", "loom2_refs/b.png"]   # as a refreshed /object_info would list them
    r = T2I(prompt_json=TREE, refs=[{"asset_id": "ast_a"}, {"asset_id": "ast_b"}], ref_max_px=1024)
    c = graphs.compile_recipe(r, roster, object_info, 1, "p", ref_files={"ast_a": "loom2_refs/a.png", "ast_b": "loom2_refs/b.png"})
    assert c.problems == [], c.problems
    kinds = [n["class_type"] for n in c.graph.values()]
    assert kinds.count("ReferenceLatent") == 2 and kinds.count("LoadImage") == 2 and kinds.count("VAEEncode") == 2
    assert c.graph["6"]["inputs"]["conditioning"] != ["5", 0]                       # guidance takes the referenced conditioning
    assert c.serialized_prompt.startswith("{") and c.summary["refs"] == 2
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(r, roster, object_info, 1, "p", ref_files={"ast_a": "x.png"})   # second ref not uploaded
    # Klein base with a negative prompt gets a real negative encode
    c2 = graphs.compile_recipe(T2I(model_id="klein-base-9b", prompt_text="x", negative="blurry"), roster, object_info, 1, "p")
    assert c2.graph["7"]["class_type"] == "CLIPTextEncode" and c2.graph["9"]["inputs"]["cfg"] == 3.5


def test_estimate_seconds():
    r = T2I(prompt_json=TREE, turbo=True)
    base = graphs.estimate_seconds(r)
    assert base["source"].startswith("baseline") and 30 < base["seconds"] < 60
    hist = [{"model_id": "flux2-dev-fp8mixed", "px": 960 * 544, "steps": 8, "wall_s": 42.0}, {"model_id": "flux2-dev-fp8mixed", "px": 960 * 544, "steps": 8, "wall_s": 38.0}]
    m = graphs.estimate_seconds(r, hist)
    assert m["seconds"] == 40.0 and m["source"].startswith("measured")
    big = graphs.estimate_seconds(T2I(prompt_json=TREE, width=1920, height=1088))
    assert big["seconds"] > 3 * graphs.estimate_seconds(T2I(prompt_json=TREE)).get("seconds", 0)


def test_preview_stage_release_presets(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(_tree(tmp_path).models_root), "mounted_model_trees": []})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "G", "size_cap_gb": 10}, headers=H)
        caps = client.get("/capabilities").json()
        assert "res_multistep" in caps["samplers"] and caps["models"]["flux2-dev-fp8mixed"]["wired"] and caps["tiers"]["draft"]["flux2"] == [960, 544]
        pv = client.post("/recipes/preview", json={"recipe": {"kind": "t2i", "prompt_mode": "tree", "prompt_json": TREE, "turbo": True, "seeds": [1, 2, 3]}}, headers=H).json()
        assert pv["prompt_mode"] == "json" and pv["steps"] == 8 and pv["count"] == 3 and pv["missing"] == [] and pv["estimate"]["seconds"] > 0 and pv["estimate"]["vram_fit"] in ("ok", "tight")
        pv2 = client.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": "klein-4b", "prompt_text": "x"}}, headers=H).json()
        assert [m["model_id"] for m in pv2["missing"]] == ["klein-4b", "qwen3-4b"]
        assert client.post("/recipes/preview", json={"recipe": {"kind": "t2i", "prompt_text": "x", "width": 5000, "height": 5000}}, headers=H).status_code == 422
        # staging: not picked up; release → queued
        client.post("/queue/pause", headers=H)
        jobs = client.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "x", "seeds": [1, 2]}, "stage": True}, headers=H).json()["jobs"]
        assert all(j["status"] == "staged" for j in jobs) and client.get("/queue").json()["counts"] == {"staged": 2}
        assert client.post(f"/jobs/{jobs[0]['id']}/release", headers=H).json()["released"] == [jobs[0]["id"]]
        assert client.post(f"/jobs/{jobs[0]['id']}/release", headers=H).status_code == 409
        assert client.post("/queue/release", headers=H).json()["released"] == [jobs[1]["id"]]
        assert client.get("/queue").json()["counts"] == {"queued": 2}
        # presets per project, snippets per app
        body = {"presets": [{"name": "alley", "panel": {"model_id": "flux2-dev-fp8mixed"}}], "last": "alley"}
        assert client.put("/project/presets", json=body, headers=H).json() == body and client.get("/project/presets").json()["last"] == "alley"
        assert (tmp_path / "proj" / "generate" / "presets.json").is_file()
        assert client.put("/snippets", json={"snippets": [{"name": "rim", "field": "lighting", "text": "golden hour rim light"}]}, headers=H).json()["snippets"][0]["name"] == "rim"
        client.post("/project/close", headers=H)


def test_manifest_records_serialised_prompt(tmp_path: Path):
    """The queue stores the exact serialised prompt and the recipe on the asset (09 §9)."""
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [32])
    Image.new("RGB", (16, 16)).save(tmp_path / "o.png")
    rec = cat.ingest_file(tmp_path / "o.png", prompt_text='{"scene":"x"}', prompt_json={"scene": "x"}, params={"recipe": parse_recipe({"kind": "t2i", "prompt_json": {"scene": "x"}}).model_dump(), "prompt_mode": "json"})
    assert rec.params["recipe"]["kind"] == "t2i" and rec.prompt_text == '{"scene":"x"}'
    cat.close()


def test_engine_options_reach_the_graph(tmp_path: Path, object_info):
    """2026-10-06 audit: ComfyUI's t2i configuration is exposed end to end and contract-checked, not silently defaulted."""
    roster = _tree(tmp_path)
    base = dict(prompt_json=TREE, width=960, height=544)
    # 1. every sampler and scheduler the pinned engine lists is accepted and lands in the KSampler node
    assert len(graphs.SAMPLERS) == 45 and len(graphs.SCHEDULERS) == 9
    c = graphs.compile_recipe(T2I(**base, sampler="dpmpp_2m_sde_gpu", scheduler="kl_optimal"), roster, object_info, 1, "loom2/t")
    assert not c.problems and c.graph["9"]["inputs"]["sampler_name"] == "dpmpp_2m_sde_gpu" and c.graph["9"]["inputs"]["scheduler"] == "kl_optimal"
    # 2. shift → ModelSamplingFlux in front of the Turbo LoRA; dtype and encoder device on the loaders; Turbo strength honoured
    c = graphs.compile_recipe(T2I(**base, turbo=True, turbo_strength=0.8, base_shift=0.6, max_shift=1.3, weight_dtype="fp8_e4m3fn_fast", te_device="cpu"), roster, object_info, 1, "loom2/t")
    assert not c.problems, c.problems
    assert c.graph["12"]["class_type"] == "ModelSamplingFlux" and c.graph["12"]["inputs"]["base_shift"] == 0.6 and c.graph["12"]["inputs"]["max_shift"] == 1.3
    assert c.graph["4"]["inputs"]["model"] == ["12", 0] and c.graph["4"]["inputs"]["strength_model"] == 0.8
    assert c.graph["1"]["inputs"]["weight_dtype"] == "fp8_e4m3fn_fast" and c.graph["2"]["inputs"]["device"] == "cpu"
    assert c.summary["base_shift"] == 0.6 and c.summary["weight_dtype"] == "fp8_e4m3fn_fast" and c.summary["turbo_strength"] == 0.8
    # 3. only one shift value given → the node's default fills the other; none given → no node, model default
    ep = graphs.effective_params(T2I(**base, max_shift=2.0))
    assert ep["base_shift"] == 0.5 and ep["max_shift"] == 2.0
    assert graphs.effective_params(T2I(**base))["base_shift"] is None
    assert "12" not in graphs.compile_recipe(T2I(**base), roster, object_info, 1, "loom2/t").graph
    # 4. tiled decode swaps the decoder node and keeps the output link
    c = graphs.compile_recipe(T2I(**base, tiled_vae=True, tile_size=768), roster, object_info, 1, "loom2/t")
    assert not c.problems and c.graph["10"]["class_type"] == "VAEDecodeTiled" and c.graph["10"]["inputs"]["tile_size"] == 768 and c.graph["11"]["inputs"]["images"] == ["10", 0]
    # 5. the flux2 schedule takes the custom sampler path: BasicGuider at CFG 1, CFGGuider with a negative on a base model
    c = graphs.compile_recipe(T2I(**base, scheduler="flux2", sampler="res_multistep"), roster, object_info, 7, "loom2/t")
    assert not c.problems, c.problems
    assert c.graph["9"]["class_type"] == "SamplerCustomAdvanced" and c.graph["15"]["class_type"] == "Flux2Scheduler" and c.graph["16"]["class_type"] == "BasicGuider"
    assert c.graph["14"]["inputs"]["sampler_name"] == "res_multistep" and c.graph["13"]["inputs"]["noise_seed"] == 7 and c.summary["scheduler"] == "flux2"
    c = graphs.compile_recipe(T2I(model_id="klein-base-9b", prompt_text="x", negative="blurry", scheduler="flux2", width=960, height=544), roster, object_info, 7, "loom2/t")
    assert not c.problems, c.problems
    assert c.graph["16"]["class_type"] == "CFGGuider" and c.graph["16"]["inputs"]["cfg"] == 3.5 and c.graph["16"]["inputs"]["negative"] == ["7", 0]
    # 6. values the engine does not offer are errors at preview time, with the reason
    for bad in (dict(weight_dtype="int4"), dict(te_device="gpu1"), dict(scheduler="bogus")):
        with pytest.raises(graphs.CompileError):
            graphs.effective_params(T2I(**base, **bad))
    with pytest.raises(ValueError):                                          # bounds live on the recipe
        parse_recipe({"kind": "t2i", "prompt_text": "x", "turbo_strength": 5})


def test_capabilities_list_the_engine_configuration(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    with TestClient(create_app(state)) as client:
        caps = client.get("/capabilities").json()
        assert caps["recipes"] == ["t2i", "inpaint", "i2i", "upscale", "segment"]
        assert len(caps["samplers"]) == 45 and "flux2" in caps["schedulers"] and len(caps["schedulers"]) == 10
        assert caps["weight_dtypes"] == ["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"] and caps["te_devices"] == ["default", "cpu"]
        assert caps["advanced"]["shift_node_defaults"] == {"base": 0.5, "max": 1.15}
