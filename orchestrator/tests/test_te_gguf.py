"""Klein 9B text encoder (D31, 2026-10-07): the presets default to unsloth's Qwen3-8B Q4_K_M GGUF (ComfyUI-GGUF's CLIPLoaderGGUF),
the Comfy-Org fp8 repack is the alternate a recipe may name in `te_id`, anything unlisted fails at compile time and at submission
(422), and the weight list / open gate / capabilities see the encoder that will actually load."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom2.engine import graphs
from loom2.engine.contract import check_graph
from loom2.recipes import I2I, Inpaint, T2I, Upscale
from loom2.roster import ROSTER_BY_ID, Roster


def _tree(tmp_path: Path) -> Roster:
    root = tmp_path / "models"
    for rel in ("diffusion_models/flux-2-klein-9b.safetensors", "diffusion_models/flux-2-klein-base-9b.safetensors", "diffusion_models/flux-2-klein-4b.safetensors",
                "text_encoders/qwen_3_8b_fp8mixed.safetensors", "text_encoders/qwen_3_4b.safetensors", "text_encoders/Qwen3-8B-Q4_K_M.gguf",
                "vae/flux2-vae.safetensors", "upscale_models/RealESRGAN_x2.pth"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(root).scan()


def test_roster_and_presets_follow_d31():
    q = ROSTER_BY_ID["qwen3-8b-q4km"]
    assert q.folder == "text_encoders" and q.family == "klein" and q.role == "text_encoder" and q.name.endswith(".gguf") and q.repo == "unsloth/Qwen3-8B-GGUF" and not q.retired
    assert ROSTER_BY_ID["qwen3-8b-q4ks"].retired and ROSTER_BY_ID["qwen3-8b-q3km"].retired
    for mid in ("klein-9b", "klein-base-9b", "klein-9b-kv"):
        assert graphs.PRESETS[mid].te_id == "qwen3-8b-q4km" and graphs.te_options(graphs.PRESETS[mid]) == ["qwen3-8b-q4km", "qwen3-8b-fp8mixed"]
    assert graphs.te_options(graphs.PRESETS["klein-4b"]) == ["qwen3-4b"] and graphs.te_options(graphs.PRESETS["flux2-dev-fp8mixed"]) == ["mistral3-small-flux2-fp8"]


def test_default_is_clip_loader_gguf_and_fp8_is_the_alternate(tmp_path: Path, object_info):
    roster = _tree(tmp_path)
    inputs = {"image": "image.png", "w": 960, "h": 544}
    base = graphs.compile_recipe(Upscale(document_id="d", refine=True, prompt_text="alley"), roster, object_info, 0, "loom2/u", inputs=inputs)
    assert base.graph["2"] == {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Qwen3-8B-Q4_K_M.gguf", "type": "flux2"}}
    assert not base.problems, base.problems                                        # the fixture carries CLIPLoaderGGUF (recaptured 2026-10-07)
    assert not check_graph(object_info, base.graph)
    enc = [n for n in base.graph.values() if n["class_type"] == "CLIPTextEncode"]
    assert enc and all(n["inputs"]["clip"] == ["2", 0] for n in enc)
    fp8 = graphs.compile_recipe(Upscale(document_id="d", refine=True, prompt_text="alley", te_id="qwen3-8b-fp8mixed"), roster, object_info, 0, "loom2/u", inputs=inputs)
    assert fp8.graph["2"] == {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}} and not fp8.problems
    # T2I / I2I / Inpaint take the same override; the fp8 encoder may still go to the CPU
    t = graphs.compile_recipe(T2I(model_id="klein-9b", prompt_mode="text", prompt_text="a cat", te_id="qwen3-8b-fp8mixed", te_device="cpu"), roster, object_info, 1, "loom2/t")
    assert t.graph["2"]["class_type"] == "CLIPLoader" and t.graph["2"]["inputs"]["device"] == "cpu" and not t.problems, t.problems
    assert graphs.effective_params(T2I(model_id="klein-9b"))["te_id"] == "qwen3-8b-q4km"
    i = graphs.compile_recipe(I2I(document_id="d", prompt_text="x"), roster, object_info, 1, "loom2/i", inputs=inputs)
    assert i.graph["2"]["class_type"] == "CLIPLoaderGGUF" and not i.problems, i.problems
    assert graphs.recipe_te_id(Inpaint(document_id="d", model_id="klein-9b")) == "qwen3-8b-q4km"


def test_unlisted_mismatched_or_retired_encoder_is_a_compile_error(tmp_path: Path, object_info):
    roster = _tree(tmp_path)
    inputs = {"image": "image.png", "w": 960, "h": 544}
    with pytest.raises(graphs.CompileError, match="does not pair"):                # the 4B encoder on a 9B model: a shape error inside the engine otherwise
        graphs.compile_recipe(Upscale(document_id="d", refine=True, te_id="qwen3-4b"), roster, object_info, 0, "loom2/u", inputs=inputs)
    with pytest.raises(graphs.CompileError, match="does not pair"):                # an 8B encoder on the 4B model
        graphs.compile_recipe(T2I(model_id="klein-4b", prompt_mode="text", prompt_text="x", te_id="qwen3-8b-q4km"), roster, object_info, 0, "loom2/t")
    with pytest.raises(graphs.CompileError, match="does not pair"):                # retired quantizations are not offered
        graphs.recipe_te_id(Upscale(document_id="d", refine=True, te_id="qwen3-8b-q3km"))
    with pytest.raises(graphs.CompileError, match="default device"):               # CLIPLoaderGGUF has no device input: cpu needs the fp8 alternate
        graphs.compile_recipe(Upscale(document_id="d", refine=True, te_device="cpu"), roster, object_info, 0, "loom2/u", inputs=inputs)
    assert graphs.recipe_te_id(Upscale(document_id="d")) is None                   # no refine → no encoder


def test_weight_list_queue_gate_and_capabilities_see_the_encoder(tmp_path: Path):
    r = Upscale(document_id="d", refine=True)
    assert graphs.recipe_weights(r) == ["realesrgan-x2", "klein-base-9b", "qwen3-8b-q4km", "flux2-vae"]
    assert graphs.recipe_weights(Upscale(document_id="d", refine=True, te_id="qwen3-8b-fp8mixed"))[2] == "qwen3-8b-fp8mixed"
    assert graphs.recipe_weights(Upscale(document_id="d", refine=True, te_id="qwen3-4b"))[2] == "qwen3-8b-q4km"   # tolerant here; compile / submission reject it
    from loom2.api import create_app
    from fastapi.testclient import TestClient
    state = tmp_path / "state"
    app = create_app(state, variant="full")
    with TestClient(app) as c:
        h = {"X-Loom-Token": app.state.services.app.token}
        c.put("/settings", json={"models_root": str(_tree(tmp_path).models_root), "variant": "full"}, headers=h)
        c.post("/project", json={"path": str(tmp_path / "prj"), "name": "p", "size_cap_gb": 10}, headers=h)
        for te in ("no-such-encoder", "qwen3-4b", "qwen3-8b-q3km"):               # unknown, mismatched, retired: 422s, not a job that fails minutes later
            resp = c.post("/jobs", json={"recipe": {"kind": "t2i", "model_id": "klein-9b", "prompt_mode": "text", "prompt_text": "x", "te_id": te}}, headers=h)
            assert resp.status_code == 422, (te, resp.text)
        caps = c.get("/capabilities", headers=h).json()
        assert caps["te_alternates"] == graphs.TE_ALTERNATES
        opts = caps["models"]["klein-9b"]["te_options"]
        assert caps["models"]["klein-9b"]["te_id"] == "qwen3-8b-q4km" and [o["id"] for o in opts] == ["qwen3-8b-q4km", "qwen3-8b-fp8mixed"]
        assert opts[0]["default"] and opts[0]["gguf"] and opts[0]["health"] == "present" and not opts[1]["default"] and not opts[1]["gguf"]
        assert [o["id"] for o in caps["models"]["klein-4b"]["te_options"]] == ["qwen3-4b"]
