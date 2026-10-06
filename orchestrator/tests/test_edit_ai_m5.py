"""M5 Edit AI (10 §4, D7): region planning, crop/outpaint inputs, paste-back layers, the inpaint / refine / upscale
graph compilers against the engine's node catalogue, and the documents AI endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from loom2 import edit_ai
from loom2.engine import graphs
from loom2.recipes import I2I, Inpaint, Upscale, parse_recipe, warm_group
from loom2.roster import Roster


def _tree(tmp_path: Path) -> Roster:
    root = tmp_path / "models"
    for rel in ("diffusion_models/flux2_dev_fp8mixed.safetensors", "text_encoders/mistral_3_small_flux2_fp8.safetensors", "vae/flux2-vae.safetensors",
                "loras/Flux2TurboComfyv2.safetensors", "diffusion_models/flux-2-klein-9b.safetensors", "diffusion_models/flux-2-klein-base-9b.safetensors",
                "text_encoders/qwen_3_8b_fp8mixed.safetensors", "upscale_models/RealESRGAN_x2.pth"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(root).scan()


# ---- region maths -----------------------------------------------------------------------------------------
def test_plan_region_margin_mult16_and_upscale():
    mask = np.zeros((544, 960), dtype=np.uint8)
    mask[150:250, 100:300] = 255
    plan = edit_ai.plan_region(mask, 960, 544, margin_pct=25, min_size=1024)
    assert plan is not None
    assert plan.w % 16 == 0 and plan.h % 16 == 0
    assert plan.x <= 100 - 32 and plan.x + plan.w >= 300 + 32          # the margin ring is inside the crop
    assert plan.y <= 150 - 32 and plan.y + plan.h >= 250 + 32
    assert 0 <= plan.x and plan.x + plan.w <= 960 and 0 <= plan.y and plan.y + plan.h <= 544
    assert max(plan.ew, plan.eh) >= 1024 and plan.ew % 16 == 0 and plan.eh % 16 == 0
    assert plan.scale > 1
    assert plan.ew * plan.eh <= edit_ai.MAX_PIXELS_DEFAULT                   # the pixel cap holds after the 16-rounding
    big = np.zeros((1088, 1920), dtype=np.uint8); big[100:900, 200:1700] = 255
    capped = edit_ai.plan_region(big, 1920, 1088, 25, 1024)
    assert capped is not None and capped.scale < 1 and capped.ew * capped.eh <= edit_ai.MAX_PIXELS_DEFAULT
    assert capped.ew % 16 == 0 and capped.eh % 16 == 0 and capped.ew * capped.eh > 0.9 * edit_ai.MAX_PIXELS_DEFAULT


def test_plan_region_clamps_to_document_and_caps_size():
    mask = np.zeros((544, 960), dtype=np.uint8)
    mask[10:540, 10:950] = 255                                           # nearly everything
    plan = edit_ai.plan_region(mask, 960, 544, margin_pct=25, min_size=1024, max_size=1280)
    assert plan is not None
    assert (plan.x, plan.y, plan.w, plan.h) == (0, 0, 960, 544)
    assert max(plan.ew, plan.eh) <= 1280 + 15
    assert edit_ai.plan_region(np.zeros((8, 8), dtype=np.uint8), 8, 8) is None


def test_crop_inputs_and_assemble_layer_roundtrip():
    comp = np.zeros((544, 960, 4), dtype=np.uint8); comp[..., 1] = 200; comp[..., 3] = 255
    mask = np.zeros((544, 960), dtype=np.uint8); mask[200:300, 400:500] = 255
    plan = edit_ai.plan_region(mask, 960, 544, 25, 1024)
    assert plan is not None
    img, msk = edit_ai.crop_inputs(comp, mask, plan)
    assert img.shape == (plan.eh, plan.ew, 3) and msk is not None and msk.shape == (plan.eh, plan.ew)
    assert msk.max() == 255 and msk.min() == 0
    result = np.full((plan.eh, plan.ew, 3), 90, dtype=np.uint8)
    layer = edit_ai.assemble_layer(result, plan, mask, feather_px=6)
    assert layer.shape == (plan.h, plan.w, 4)
    a = layer[..., 3]
    cy, cx = 250 - plan.y, 450 - plan.x
    assert a[cy, cx] == 255                                              # inside the selection: opaque
    assert a[2, 2] == 0                                                  # far outside: transparent
    assert 0 < a[200 - plan.y - 3, cx] < 255                             # feathered edge


def test_dilate_and_feather():
    m = np.zeros((64, 64), dtype=np.uint8); m[30:34, 30:34] = 255
    d = edit_ai.dilate(m, 4)
    assert d[26, 30] == 255 and d[25, 30] == 0
    f = edit_ai.feather(m, 2)
    assert 0 < f[28, 31] < 255


def test_outpaint_inputs_pad_and_strips():
    comp = np.zeros((544, 960, 4), dtype=np.uint8); comp[..., 0] = 120; comp[..., 3] = 255
    plan = edit_ai.outpaint_plan(960, 544, {"right": 240})
    assert (plan.x, plan.y, plan.w, plan.h) == (0, 0, 1200, 544) and plan.pad == {"left": 0, "top": 0, "right": 240, "bottom": 0}
    img, msk, strips = edit_ai.outpaint_inputs(comp, plan, band=24)
    assert img.shape == (plan.eh, plan.ew, 3) and img[10, -5, 0] == 120   # edge-padded colour continues
    assert strips[10, 1000] == 255 and strips[10, 900] == 0
    sx = int(round(950 * plan.ew / plan.w))
    assert msk[10, sx] == 255                                            # the band reaches 24 px into the image
    layer = edit_ai.assemble_layer(np.full((plan.eh, plan.ew, 3), 7, dtype=np.uint8), plan, strips, 8)
    assert layer.shape == (544, 1200, 4) and layer[10, 1150, 3] == 255 and layer[10, 400, 3] == 0


# ---- recipes and graphs ------------------------------------------------------------------------------------
def test_recipes_parse_and_warm_groups():
    r = parse_recipe({"kind": "inpaint", "mode": "fill_hero", "document_id": "doc_x", "prompt_text": "a lamp"})
    assert isinstance(r, Inpaint) and warm_group(r) == "flux2-dev-fp8mixed"
    r2 = parse_recipe({"kind": "i2i", "document_id": "doc_x", "strength": 0.25})
    assert isinstance(r2, I2I) and r2.model_id == "klein-base-9b"
    r3 = parse_recipe({"kind": "upscale", "document_id": "doc_x"})
    assert isinstance(r3, Upscale) and r3.model_id == "realesrgan-x2"


@pytest.mark.parametrize("mode", ["fill", "fill_match", "fill_hero", "remove", "outpaint"])
def test_build_inpaint_compiles_against_object_info(tmp_path: Path, object_info: dict, mode: str):
    roster = _tree(tmp_path)
    r = Inpaint(mode=mode, document_id="doc_x", prompt_text="wet cobblestones", outpaint={"right": 240} if mode == "outpaint" else None)
    # upload names must be in the engine's LoadImage enum (the queue refreshes object_info after uploading); the
    # fixture lists the E8 bench files
    c = graphs.compile_recipe(r, roster, object_info, 7, "loom2/job_x", inputs={"image": "alley-rain_s20261004.png", "mask": "01-remove-crates.png", "w": 1024, "h": 576})
    assert not c.problems, c.problems
    kinds = {n["class_type"] for n in c.graph.values()}
    assert "SaveImage" in kinds and "LoadImage" in kinds and "LoadImageMask" in kinds
    if mode in ("fill", "fill_hero", "outpaint"):
        assert "LanPaint_SamplerCustomAdvanced" in kinds and "LanPaint_ImageDecode" in kinds
        assert c.summary["sampler"] == "lanpaint"
    else:
        assert "InpaintModelConditioning" in kinds and "DifferentialDiffusion" in kinds
        assert ("EmptyImage" in kinds) == (mode == "remove")
    assert c.summary["model_id"] == ("flux2-dev-fp8mixed" if mode == "fill_hero" else "klein-9b")
    if mode == "fill_hero":
        assert "LoraLoaderModelOnly" in kinds and c.summary["steps"] == 8


def test_build_i2i_and_upscale(tmp_path: Path, object_info: dict):
    roster = _tree(tmp_path)
    img = "alley-rain_s20261004.png"
    c = graphs.compile_recipe(I2I(document_id="doc_x", strength=0.3, prompt_text="more detail"), roster, object_info, 3, "p", inputs={"image": img, "w": 960, "h": 544})
    assert not c.problems, c.problems
    ks = next(n for n in c.graph.values() if n["class_type"] == "KSampler")
    assert ks["inputs"]["denoise"] == 0.3 and ks["inputs"]["steps"] == 20 and ks["inputs"]["cfg"] == 3.5
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(I2I(model_id="klein-9b", document_id="doc_x"), roster, object_info, 3, "p", inputs={"image": img, "w": 960, "h": 544})
    u = graphs.compile_recipe(Upscale(document_id="doc_x"), roster, object_info, 0, "p", inputs={"image": img})
    # the fixture predates the upscaler on disk: only the model-name enum may complain
    assert all("UpscaleModelLoader" in p for p in u.problems), u.problems
    assert {n["class_type"] for n in u.graph.values()} >= {"UpscaleModelLoader", "ImageUpscaleWithModel", "SaveImage"}


# ---- API ---------------------------------------------------------------------------------------------------
def test_documents_selection_and_ai_endpoints(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        assert client.post("/project", json={"path": str(tmp_path / "proj"), "name": "AI", "size_cap_gb": 10}, headers=H).status_code == 200
        client.post("/queue/pause", headers=H)
        r = client.post("/documents", json={"w": 64, "h": 48, "name": "ai"}, headers=H)
        assert r.status_code == 200, r.text
        did = r.json()["id"]
        sel = np.zeros((48, 64), dtype=np.uint8); sel[10:30, 20:40] = 255
        r = client.put(f"/documents/{did}/selection", params={"w": 64, "h": 48}, content=sel.tobytes(), headers={**H, "Content-Type": "application/octet-stream"})
        assert r.status_code == 200 and r.json()["selection"] == [64, 48]
        r = client.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "fill", "prompt_text": "x", "seeds": [1, 2]}, "stage": True}, headers=H)
        assert r.status_code == 200, r.text
        jobs = r.json()["jobs"]
        assert len(jobs) == 2 and all(j["kind"] == "inpaint" and j["recipe"]["document_id"] == did and j["status"] == "staged" for j in jobs)
        assert client.post(f"/documents/{did}/ai", json={"recipe": {"kind": "t2i"}}, headers=H).status_code == 422
        assert client.post("/documents/doc_nope/ai", json={"recipe": {"kind": "upscale"}}, headers=H).status_code in (400, 404, 409, 422)
        r = client.put(f"/documents/{did}/selection", content=b"", headers=H)
        assert r.status_code == 200 and r.json()["selection"] is None
