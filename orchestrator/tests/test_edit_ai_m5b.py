"""M5 slice 2 (10 §4, 10 §14 item 3): AI Select graphs (BiRefNet subject, SAM 3 text / points / box), the tiled refine
upscale graph, the tile planner and the selection algebra, and the document API for selections — offline against the
captured engine catalogue."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2 import edit_ai
from loom2.api import create_app
from loom2.config import AppState
from loom2.engine import graphs
from loom2.recipes import Segment, Upscale, parse_recipe, warm_group
from loom2.roster import Roster


def _tree(tmp_path: Path) -> Roster:
    root = tmp_path / "models"
    for rel in ("diffusion_models/flux2_dev_fp8mixed.safetensors", "text_encoders/mistral_3_small_flux2_fp8.safetensors", "vae/flux2-vae.safetensors",
                "loras/Flux2TurboComfyv2.safetensors", "diffusion_models/flux-2-klein-base-9b.safetensors", "text_encoders/qwen_3_8b_fp8mixed.safetensors",
                "upscale_models/RealESRGAN_x2.pth", "background_removal/BiRefNet-general.safetensors", "sam3/sam3.pt"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(root).scan()


# ---- tiles and selection algebra ---------------------------------------------------------------------------------
def test_plan_tiles_covers_the_image_with_full_size_tiles():
    tiles = edit_ai.plan_tiles(1920, 1088, 1024, 128)
    assert all(tw == 1024 and th == 1024 for _, _, tw, th in tiles)
    assert tiles[0][:2] == (0, 0) and any(x + tw == 1920 for x, _, tw, _ in tiles) and any(y + th == 1088 for _, y, _, th in tiles)
    cover = np.zeros((1088, 1920), dtype=np.uint8)
    for x, y, tw, th in tiles:
        cover[y:y + th, x:x + tw] = 1
    assert cover.all() and len(tiles) == 4                                   # 2 × 2: 0–1024 and 896–1920 / 0–1024 and 64–1088
    assert edit_ai.plan_tiles(960, 544, 1024, 128) == [(0, 0, 960, 544)]    # smaller than a tile: one tile, 16-aligned
    assert all(tw % 16 == 0 and th % 16 == 0 for _, _, tw, th in edit_ai.plan_tiles(1000, 700, 512, 64))


def test_selection_algebra_and_engine_mask():
    cur = np.zeros((8, 8), dtype=np.uint8); cur[:, :4] = 255
    new = np.zeros((8, 8), dtype=np.uint8); new[:4, :] = 255
    assert (edit_ai.combine_selection(None, new, "replace") == new).all()
    assert edit_ai.combine_selection(cur, new, "add")[7, 0] == 255 and edit_ai.combine_selection(cur, new, "add")[0, 7] == 255
    assert edit_ai.combine_selection(cur, new, "subtract")[0, 0] == 0 and edit_ai.combine_selection(cur, new, "subtract")[7, 0] == 255
    inter = edit_ai.combine_selection(cur, new, "intersect")
    assert inter[0, 0] == 255 and inter[7, 0] == 0 and inter[0, 7] == 0
    small = np.zeros((16, 32), dtype=np.uint8); small[4:12, 8:24] = 255
    m = edit_ai.mask_from_engine(small, 64, 32, expand=2, feather_px=0)
    assert m.shape == (32, 64) and m[16, 32] == 255 and m[0, 0] == 0
    assert edit_ai.mask_from_engine(small, 64, 32, expand=-3)[16, 32] == 255 and edit_ai.mask_from_engine(small, 64, 32, expand=-3).sum() < m.sum()


# ---- graphs --------------------------------------------------------------------------------------------------------
def test_segment_graphs_compile_against_the_engine(tmp_path: Path, object_info):
    roster = _tree(tmp_path)
    inputs = {"image": "image.png", "w": 1024, "h": 576}
    c = graphs.compile_recipe(Segment(document_id="d", mode="subject"), roster, object_info, 0, "loom2/s", inputs=inputs)
    assert not c.problems, c.problems
    assert c.graph["1"]["class_type"] == "LoadBackgroundRemovalModel" and c.graph["2"]["class_type"] == "RemoveBackground"
    assert c.graph["5"]["class_type"] == "MaskToImage" and c.graph["99"]["inputs"]["images"] == ["5", 0]
    c = graphs.compile_recipe(Segment(document_id="d", model_id="sam3", mode="text", text="a woman"), roster, object_info, 0, "loom2/s", inputs=inputs)
    assert not c.problems, c.problems
    assert c.graph["1"]["class_type"] == "CheckpointLoaderSimple" and c.graph["2"]["inputs"]["clip"] == ["1", 1] and c.graph["4"]["inputs"]["conditioning"] == ["2", 0]
    pts = [{"x": 100, "y": 50, "label": 1}, {"x": 10, "y": 10, "label": 0}]
    c = graphs.compile_recipe(Segment(document_id="d", model_id="sam3", mode="points"), roster, object_info, 0, "loom2/s", inputs=inputs | {"points": pts})
    assert not c.problems, c.problems
    assert json.loads(c.graph["4"]["inputs"]["positive_coords"]) == [{"x": 100, "y": 50}] and json.loads(c.graph["4"]["inputs"]["negative_coords"]) == [{"x": 10, "y": 10}]
    c = graphs.compile_recipe(Segment(document_id="d", model_id="sam3", mode="box"), roster, object_info, 0, "loom2/s", inputs=inputs | {"box": [10, 20, 110, 220]})
    assert not c.problems, c.problems
    bb = json.loads(c.graph["3"]["inputs"]["bboxes"])
    assert bb == [{"x": 10, "y": 20, "width": 100, "height": 200}] and c.graph["3"]["inputs"]["width"] == 1024 and c.graph["4"]["inputs"]["bboxes"] == ["3", 1]   # C32: output 1 is the BOUNDING_BOX
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(Segment(document_id="d", model_id="sam3", mode="text", text=""), roster, object_info, 0, "loom2/s", inputs=inputs)
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(Segment(document_id="d", model_id="sam3", mode="points"), roster, object_info, 0, "loom2/s", inputs=inputs | {"points": [{"x": 1, "y": 1, "label": 0}]})
    assert warm_group(Segment(document_id="d", model_id="sam3", mode="text", text="x")) == "sam3"


def test_tiled_refine_upscale_graph(tmp_path: Path, object_info):
    roster = _tree(tmp_path)
    plain = graphs.compile_recipe(Upscale(document_id="d"), roster, object_info, 0, "loom2/u", inputs={"image": "image.png", "w": 960, "h": 544})
    assert not plain.problems and plain.graph["99"]["inputs"]["images"] == ["102", 0] and plain.summary["factor"] == 2
    r = Upscale(document_id="d", refine=True, strength=0.25, tile=1024, overlap=128, prompt_text="alley")
    c = graphs.compile_recipe(r, roster, object_info, 5, "loom2/u", inputs={"image": "image.png", "w": 960, "h": 544})
    assert not c.problems, c.problems
    tiles = [n for n in c.graph.values() if n["class_type"] == "ImageCrop"]
    assert len(tiles) == c.summary["tiles"] == 4 and c.summary["upscaled"] == [1920, 1088]
    ks = [n for n in c.graph.values() if n["class_type"] == "KSampler"]
    assert len(ks) == 4 and all(n["inputs"]["denoise"] == 0.25 for n in ks) and {n["inputs"]["seed"] for n in ks} == set(range(5, 9))
    comps = [n for n in c.graph.values() if n["class_type"] == "ImageCompositeMasked"]
    assert len(comps) == 4 and comps[0]["inputs"]["destination"] == ["102", 0] and c.graph["99"]["inputs"]["images"][0] == max(c.graph, key=lambda k: int(k) if k.isdigit() else -1)
    feathers = [n for n in c.graph.values() if n["class_type"] == "FeatherMask"]
    first = next(n for n in feathers if n["inputs"]["left"] == 0 and n["inputs"]["top"] == 0)
    assert first["inputs"]["right"] == 64 and first["inputs"]["bottom"] == 64            # the corner tile feathers only inward
    assert warm_group(r) == "klein-base-9b" and graphs.estimate_vram_gb(r) == graphs.VRAM_ESTIMATE_GB["klein-base-9b"]
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(Upscale(document_id="d", refine=True, refine_model_id="klein-9b"), roster, object_info, 0, "loom2/u", inputs={"image": "image.png", "w": 960, "h": 544})


# ---- API: selection round trip, segment accepted ---------------------------------------------------------------------
def test_selection_endpoints_and_segment_submission(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    with TestClient(create_app(state)) as client:
        H = {"X-Loom-Token": client.app.state.services.app.token}
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "P", "size_cap_gb": 10}, headers=H)
        png = tmp_path / "in.png"
        Image.new("RGB", (64, 48), (10, 120, 200)).save(png)
        asset = client.post("/assets/import", json={"paths": [str(png)]}, headers=H).json()["items"][0]
        doc = client.post("/documents", json={"from_asset": asset["id"]}, headers=H).json()
        assert client.get(f"/documents/{doc['id']}/selection").status_code == 404
        sel = np.zeros((48, 64), dtype=np.uint8); sel[10:30, 20:40] = 255
        assert client.put(f"/documents/{doc['id']}/selection?w=64&h=48", content=sel.tobytes(), headers=H).status_code == 200
        r = client.get(f"/documents/{doc['id']}/selection")
        assert r.status_code == 200 and r.headers["x-loom-width"] == "64" and r.headers["x-loom-channels"] == "1" and np.frombuffer(r.content, np.uint8).reshape(48, 64)[20, 30] == 255
        client.post("/queue/pause", headers=H)
        r = client.post(f"/documents/{doc['id']}/ai", json={"recipe": {"kind": "segment", "model_id": "birefnet", "mode": "subject"}}, headers=H)
        assert r.status_code == 200 and r.json()["jobs"][0]["kind"] == "segment" and r.json()["jobs"][0]["warm_group"] == "birefnet"
        assert "segment" in client.get("/capabilities").json()["recipes"]
        assert parse_recipe({"kind": "segment", "document_id": "d", "op": "intersect", "expand": -8}).expand == -8
        with pytest.raises(ValueError):
            parse_recipe({"kind": "segment", "document_id": "d", "threshold": 2})
        client.post("/project/close", headers=H)
