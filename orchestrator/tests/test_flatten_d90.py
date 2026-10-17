"""D90 (UI6, owed): Edit › Flatten image — the editor asks the server for the exact flatten (`POST /documents/{id}/export`
format "raw", the same `od.flatten` Save to Catalogue and the PNG export use) and makes it the document's one raster layer; Save to
Catalogue of the flattened document must match the layered one."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState
from loom2.documents import AdjustmentLayer, FilterLayer, GroupLayer, Mask, RasterLayer

W, H = 24, 16
OCT = {"Content-Type": "application/octet-stream"}


def _app(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1},
                                     "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    return create_app(state)


def _noise(seed: int, w: int, h: int, alpha: int | None = 255) -> np.ndarray:
    a = np.random.default_rng(seed).integers(0, 256, (h, w, 4), dtype=np.uint8)
    if alpha is not None:
        a[..., 3] = alpha
    return a


def _put(client, H_, doc_id, lid, arr, kind="image"):
    h, w = arr.shape[:2]
    r = client.put(f"/documents/{doc_id}/layers/{lid}/pixels", params={"w": w, "h": h, "kind": kind}, content=arr.tobytes(), headers={**H_, **OCT})
    assert r.status_code == 200, r.text


def _raw(client, H_, doc_id) -> np.ndarray:
    r = client.post(f"/documents/{doc_id}/export", json={"format": "raw"}, headers=H_)
    assert r.status_code == 200 and r.headers["x-loom-channels"] == "4"
    w, h = int(r.headers["x-loom-width"]), int(r.headers["x-loom-height"])
    return np.frombuffer(r.content, dtype=np.uint8).reshape(h, w, 4)


def test_flatten_raw_is_the_exact_flatten_and_a_flattened_document_saves_the_same(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app)
    H_ = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "F", "size_cap_gb": 10}, headers=H_)
        for background in ("#203040", "transparent"):
            d = client.post("/documents", json={"name": f"stack {background}", "w": W, "h": H, "background": background}, headers=H_).json()
            # every kind Photoshop's Flatten Image folds in: a group (isolated, masked) with blend modes, a clipped layer, an adjustment,
            # a filter, a masked layer at an offset, a hidden layer (dropped)
            layers = [
                AdjustmentLayer(id="adj", type="hue_saturation", params={"hue": 20, "saturation": -30, "lightness": 0}).model_dump(),
                FilterLayer(id="blur", type="gaussian_blur", params={"radius": 1.0}, opacity=0.6).model_dump(),
                GroupLayer(id="grp", passthrough=False, opacity=0.8, blend="screen", mask=Mask(), children=[
                    RasterLayer(id="clip", name="clip", clip=True, blend="multiply").model_dump(),
                    RasterLayer(id="inner", name="inner", x=2, y=3, w=12, h=8, blend="overlay").model_dump()]).model_dump(),
                RasterLayer(id="hidden", name="hidden", visible=False).model_dump(),
                RasterLayer(id="mid", name="mid", x=-3, y=2, w=20, h=10, opacity=0.7, blend="soft-light", mask=Mask(x=0, y=0)).model_dump(),
                RasterLayer(id="base", name="Paper").model_dump(),
            ]
            d = client.put(f"/documents/{d['id']}", json={**d, "layers": layers}, headers=H_).json()
            _put(client, H_, d["id"], "base", _noise(1, W, H, alpha=None if background == "transparent" else 255))
            _put(client, H_, d["id"], "mid", _noise(2, 20, 10, alpha=None))
            m = np.zeros((10, 20), np.uint8); m[:, :12] = 255; m[:, 12:15] = 128
            _put(client, H_, d["id"], "mid", m, "mask")
            _put(client, H_, d["id"], "hidden", _noise(3, W, H))
            _put(client, H_, d["id"], "inner", _noise(4, 12, 8, alpha=200))
            _put(client, H_, d["id"], "clip", _noise(5, W, H))
            gm = np.full((H, W), 255, np.uint8); gm[:4] = 0
            _put(client, H_, d["id"], "grp", gm, "mask")

            layered = _raw(client, H_, d["id"])
            od = app.state.services.require_documents().get(d["id"])
            assert np.array_equal(layered, od.flatten())                          # the same function Save to Catalogue runs
            png = np.asarray(Image.open(io.BytesIO(client.post(f"/documents/{d['id']}/export", json={"format": "png"}, headers=H_).content)).convert("RGBA"))
            assert np.array_equal(png, layered)

            # what the editor does: one raster layer (the bottom layer's name), the raw flatten as its pixels, the stack PUT with the revision
            d = client.get(f"/documents/{d['id']}", headers=H_).json()
            flat_stack = {**d, "layers": [RasterLayer(id="lyr_flat", name="Paper", w=W, h=H).model_dump()]}
            r = client.put(f"/documents/{d['id']}", json=flat_stack, headers=H_)
            assert r.status_code == 200 and r.json()["missing_pixels"] == ["lyr_flat"]
            _put(client, H_, d["id"], "lyr_flat", layered.copy())
            assert np.array_equal(_raw(client, H_, d["id"]), layered)            # flattening changes nothing you see
            asset = client.post(f"/documents/{d['id']}/flatten", json={"to_catalogue": True}, headers=H_).json()["asset"]
            _, cat, _ = app.state.services.require_project()
            saved = cat.abs_path(cat.get(asset["id"]))
            assert np.array_equal(np.asarray(Image.open(saved).convert("RGBA")), layered)
        assert client.post(f"/documents/{d['id']}/export", json={"format": "psd"}, headers=H_).status_code == 422
        client.post("/project/close", headers=H_)
