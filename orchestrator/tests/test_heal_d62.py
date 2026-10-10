"""D62 (PC14, PC15): the native extension's content-aware fill, Spot Healing (PatchMatch + the Poisson membrane) and the stateless
/heal route; Quick Remove as a queue mode needs no engine."""
from pathlib import Path

import numpy as np
import pytest

from loom2 import native
from loom2.heal import dilate_square, spot_heal

pytestmark = pytest.mark.skipif(not native.available(), reason="the native extra is not installed")


def texture(h: int = 96, w: int = 128) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w]
    rgb = np.stack([(np.sin(x / 3.0) * 40 + 120), (np.cos(y / 4.0) * 40 + 110), np.full_like(x, 90.0)], -1)
    return np.clip(rgb + np.random.default_rng(3).normal(0, 3, rgb.shape), 0, 255).astype(np.uint8)


def test_dilate_square_grows_by_r():
    m = np.zeros((9, 9), bool); m[4, 4] = True
    assert dilate_square(m, 2).sum() == 25 and dilate_square(m, 0).sum() == 1


def test_content_aware_fill_replaces_a_blemish_with_its_surroundings():
    img = texture()
    hole = np.zeros(img.shape[:2], bool); hole[40:56, 60:76] = True
    dirty = img.copy(); dirty[hole] = (255, 0, 255)
    out = native.content_aware_fill(dirty, hole, seed=1)
    assert np.array_equal(out[~hole], dirty[~hole])
    assert np.abs(out[hole].astype(int) - img[hole].astype(int)).mean() < 40          # magenta (≈ 150 away) is gone


def test_spot_heal_removes_a_blemish_and_keeps_the_rest():
    img = texture()
    rgba = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    cov = np.zeros(img.shape[:2], np.uint8); cov[44:52, 62:72] = 255
    dirty = rgba.copy(); dirty[cov > 0, :3] = (255, 0, 255)
    out = spot_heal(dirty, cov, seed=1)
    healed = dilate_square(cov > 0, 1)
    assert np.array_equal(out[~healed], dirty[~healed]) and np.array_equal(out[..., 3], dirty[..., 3])
    assert np.abs(out[cov > 0, :3].astype(int) - img[cov > 0].astype(int)).mean() < 25


def test_heal_route_round_trip(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    app = create_app(tmp_path / "state")
    c = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token, "Content-Type": "application/octet-stream"}
    img = texture(32, 40)
    rgba = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    cov = np.zeros(img.shape[:2], np.uint8); cov[12:18, 15:22] = 255
    with c:
        r = c.post("/heal", params={"w": 40, "h": 32}, content=rgba.tobytes() + cov.tobytes(), headers=H)
        assert r.status_code == 200 and len(r.content) == 40 * 32 * 4
        assert c.post("/heal", params={"w": 40, "h": 32}, content=b"short", headers=H).status_code == 400
        assert c.post("/heal", params={"w": 0, "h": 32}, content=b"", headers=H).status_code == 400


def test_quick_remove_runs_without_the_engine(tmp_path: Path):
    import time
    from fastapi.testclient import TestClient
    from PIL import Image
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    c = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with c:
        assert c.post("/project", json={"path": str(tmp_path / "proj"), "name": "qr", "size_cap_gb": 10}, headers=H).status_code == 200
        Image.fromarray(texture(96, 128)).save(tmp_path / "in.png")
        asset = c.post("/assets/import", json={"paths": [str(tmp_path / "in.png")]}, headers=H).json()["items"][0]["id"]
        did = c.post("/documents", json={"from_asset": asset}, headers=H).json()["id"]
        sel = np.zeros((96, 128), np.uint8); sel[40:56, 60:76] = 255
        assert c.put(f"/documents/{did}/selection", params={"w": 128, "h": 96}, content=sel.tobytes(), headers={**H, "Content-Type": "application/octet-stream"}).status_code == 200
        r = c.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "quick_remove"}}, headers=H)
        assert r.status_code == 200, r.text
        jid = r.json()["jobs"][0]["id"]
        c.post("/queue/unpause", headers=H)
        t0 = time.time()
        while time.time() - t0 < 30:
            job = c.get(f"/jobs/{jid}").json()
            if job["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert job["status"] == "done", job.get("error")
        doc = c.get(f"/documents/{did}").json()
        group = next(n for n in doc["layers"] if n["kind"] == "group")
        layer = group["children"][0]
        assert layer["name"] == "quick remove" and layer["mask"] is not None
        assert c.get("/engine").json().get("running") in (False, None)                 # the engine was never started
