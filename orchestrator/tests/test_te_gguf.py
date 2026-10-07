"""Quantized text encoders (2026-10-07 encoder experiment): a recipe may swap the preset's encoder for a listed alternate
(`TE_ALTERNATES`); a .gguf alternate compiles to ComfyUI-GGUF's CLIPLoaderGGUF, anything unlisted fails at compile time
and at submission (422), and the weight list / open gate see the encoder that will actually load."""
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
                "text_encoders/Qwen3-8B-Q3_K_M.gguf", "vae/flux2-vae.safetensors", "upscale_models/RealESRGAN_x2.pth"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(root).scan()


def test_roster_lists_the_quantized_encoders():
    for mid in graphs.TE_ALTERNATES["qwen3-8b-fp8mixed"]:
        e = ROSTER_BY_ID[mid]
        assert e.folder == "text_encoders" and e.family == "klein" and e.role == "text_encoder" and e.name.endswith(".gguf") and e.repo == "unsloth/Qwen3-8B-GGUF"


def test_gguf_alternate_compiles_to_clip_loader_gguf(tmp_path: Path, object_info):
    roster = _tree(tmp_path)
    inputs = {"image": "image.png", "w": 960, "h": 544}
    base = graphs.compile_recipe(Upscale(document_id="d", refine=True, prompt_text="alley"), roster, object_info, 0, "loom2/u", inputs=inputs)
    assert base.graph["2"] == {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}}
    q = graphs.compile_recipe(Upscale(document_id="d", refine=True, prompt_text="alley", te_id="qwen3-8b-q4km"), roster, object_info, 0, "loom2/u", inputs=inputs)
    assert q.graph["2"] == {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Qwen3-8B-Q4_K_M.gguf", "type": "flux2"}}
    assert not q.problems, q.problems                                           # the fixture carries CLIPLoaderGGUF (recaptured 2026-10-07)
    assert not check_graph(object_info, q.graph)
    # every other node still hangs off node 2 the same way
    enc = [n for n in q.graph.values() if n["class_type"] == "CLIPTextEncode"]
    assert enc and all(n["inputs"]["clip"] == ["2", 0] for n in enc)
    # T2I and I2I take the same override
    t = graphs.compile_recipe(T2I(model_id="klein-9b", prompt_mode="text", prompt_text="a cat", te_id="qwen3-8b-q3km"), roster, object_info, 1, "loom2/t")
    assert t.graph["2"]["class_type"] == "CLIPLoaderGGUF" and t.graph["2"]["inputs"]["clip_name"] == "Qwen3-8B-Q3_K_M.gguf" and not t.problems, t.problems
    assert graphs.effective_params(T2I(model_id="klein-9b", te_id="qwen3-8b-q3km"))["te_id"] == "qwen3-8b-q3km"
    i = graphs.compile_recipe(I2I(document_id="d", prompt_text="x", te_id="qwen3-8b-q4km"), roster, object_info, 1, "loom2/i", inputs=inputs)
    assert i.graph["2"]["class_type"] == "CLIPLoaderGGUF" and not i.problems, i.problems


def test_unlisted_or_mismatched_encoder_is_a_compile_error(tmp_path: Path, object_info):
    roster = _tree(tmp_path)
    inputs = {"image": "image.png", "w": 960, "h": 544}
    with pytest.raises(graphs.CompileError, match="does not pair"):                # the 4B encoder on a 9B model: a shape error inside the engine otherwise
        graphs.compile_recipe(Upscale(document_id="d", refine=True, te_id="qwen3-4b"), roster, object_info, 0, "loom2/u", inputs=inputs)
    with pytest.raises(graphs.CompileError, match="does not pair"):                # an 8B GGUF on the 4B model
        graphs.compile_recipe(T2I(model_id="klein-4b", prompt_mode="text", prompt_text="x", te_id="qwen3-8b-q4km"), roster, object_info, 0, "loom2/t")
    with pytest.raises(graphs.CompileError, match="default device"):               # CLIPLoaderGGUF has no device input
        graphs.compile_recipe(Upscale(document_id="d", refine=True, te_id="qwen3-8b-q4km", te_device="cpu"), roster, object_info, 0, "loom2/u", inputs=inputs)
    # the preset's own id is always accepted
    assert graphs.recipe_te_id(Inpaint(document_id="d", model_id="klein-9b", te_id="qwen3-8b-fp8mixed")) == "qwen3-8b-fp8mixed"
    assert graphs.recipe_te_id(Upscale(document_id="d")) is None                   # no refine → no encoder


def test_weight_list_and_queue_gate_see_the_override(tmp_path: Path):
    r = Upscale(document_id="d", refine=True, te_id="qwen3-8b-q4ks")
    assert graphs.recipe_weights(r) == ["realesrgan-x2", "klein-base-9b", "qwen3-8b-q4ks", "flux2-vae"]
    assert "qwen3-8b-fp8mixed" not in graphs.recipe_weights(r)
    bogus = Upscale(document_id="d", refine=True, te_id="qwen3-4b")
    assert graphs.recipe_weights(bogus)[2] == "qwen3-8b-fp8mixed"                 # tolerant here; compile / submission reject it
    # submission: unknown id and a mismatched pairing are 422s, not a job that fails minutes later
    from loom2.api import create_app
    from fastapi.testclient import TestClient
    state = tmp_path / "state"
    app = create_app(state, variant="full")
    with TestClient(app) as c:
        h = {"X-Loom-Token": app.state.services.app.token}
        c.put("/settings", json={"models_root": str(_tree(tmp_path).models_root), "variant": "full"}, headers=h)
        c.post("/project", json={"path": str(tmp_path / "prj"), "name": "p", "size_cap_gb": 10}, headers=h)
        for te in ("no-such-encoder", "qwen3-4b"):
            resp = c.post("/jobs", json={"recipe": {"kind": "t2i", "model_id": "klein-9b", "prompt_mode": "text", "prompt_text": "x", "te_id": te}}, headers=h)
            assert resp.status_code == 422, (te, resp.text)
        caps = c.get("/capabilities", headers=h).json()
        assert caps["te_alternates"] == graphs.TE_ALTERNATES
