"""D45 Refine Edge: the guided-filter primitives against brute force, what refining does to soft and hard edges and what it leaves
alone, the post steps (smooth / feather / contrast / shift edge), the defaults in /capabilities, and the route."""
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2 import matting
from loom2.api import create_app
from loom2.config import AppState
from loom2.recipes import RefineEdge, Segment


def test_box_mean_and_running_extremes_match_brute_force():
    x = np.random.default_rng(3).random((20, 23))
    bf = np.array([[x[max(0, i - 3):i + 4, max(0, j - 3):j + 4].mean() for j in range(23)] for i in range(20)])
    assert np.abs(matting.box_mean(x, 3) - bf).max() < 1e-12
    for use_max, f in ((True, np.max), (False, np.min)):
        bf = np.array([[f(x[max(0, i - 2):i + 3, max(0, j - 2):j + 3]) for j in range(23)] for i in range(20)])
        assert np.array_equal(matting._square_extreme(x, 2, use_max), bf)


def test_guided_filter_follows_the_guide():
    # a guide that is a scaled copy of the input: the local linear model reproduces it almost exactly
    rng = np.random.default_rng(5)
    p = rng.random((40, 40))
    guide = np.repeat(p[..., None], 3, axis=-1) * 0.5 + 0.2
    q = matting.guided_filter_color(guide, p, 4)
    assert np.abs(q - p).max() < 0.05


def _image(w=200, h=120):
    img = np.full((h, w, 3), 230, np.uint8)
    img[:, :100] = 40                                             # a hard edge at x = 100
    img[80:, 92:104] = np.linspace(40, 230, 12).astype(np.uint8)[None, :, None]   # a soft ramp below
    img[80:, 104:] = 230
    return img


def test_refine_softens_where_the_image_is_soft_and_keeps_the_rest():
    img = _image()
    mask = np.zeros((120, 200), np.uint8)
    mask[:, :100] = 255
    out = matting.refine(mask, img)
    ramp = out[100, 92:104].astype(int)
    assert (np.diff(ramp) <= 1).all() and ((ramp > 20) & (ramp < 235)).sum() >= 5        # the ramp's transition is transferred
    assert out[40, 98] >= 220 and out[40, 102] <= 20                                       # the hard edge stays nearly hard
    assert out[40, 40] == 255 and out[40, 180] == 0                                         # outside the band: untouched


def test_post_steps():
    img = _image()
    soft = np.zeros((120, 200), np.uint8)
    soft[:, :100] = 255
    p0 = matting.RefineParams(radius=0, smart_radius=False)
    feathered = matting.refine(soft, img, matting.RefineParams(radius=0, feather=8))
    assert ((feathered > 10) & (feathered < 245)).sum() > ((soft > 10) & (soft < 245)).sum() + 100
    hardened = matting.refine(feathered, img, matting.RefineParams(radius=0, contrast=80))
    assert ((hardened > 10) & (hardened < 245)).sum() < ((feathered > 10) & (feathered < 245)).sum()
    grown = matting.refine(soft, img, matting.RefineParams(radius=0, shift_edge=50))
    shrunk = matting.refine(soft, img, matting.RefineParams(radius=0, shift_edge=-50))
    assert grown.astype(int).sum() > soft.astype(int).sum() > shrunk.astype(int).sum()
    assert np.array_equal(matting.refine(soft, img, p0), soft)                              # nothing asked, nothing changed


def test_api_model_defaults_match_the_worker():
    assert matting.params_from(RefineEdge()) == matting.DEFAULTS
    assert Segment().edge_refine is None


def test_refine_route_and_capabilities(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        caps = client.get("/capabilities", headers=H).json()
        assert caps["refine_edge"]["defaults"] == RefineEdge().model_dump()
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "R", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "src.png"
        Image.fromarray(_image(), "RGB").save(src)
        asset = client.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        d = client.post("/documents", json={"from_asset": asset["id"]}, headers=H).json()
        assert client.post(f"/documents/{d['id']}/selection/refine", json={}, headers=H).status_code == 400   # nothing to refine
        sel = np.zeros((120, 200), np.uint8)
        sel[:, :100] = 255
        client.put(f"/documents/{d['id']}/selection", params={"w": 200, "h": 120}, content=sel.tobytes(), headers={**H, "Content-Type": "application/octet-stream"})
        r = client.post(f"/documents/{d['id']}/selection/refine", json={"radius": 10, "feather": 2}, headers=H)
        assert r.status_code == 200 and r.json()["selection"] == [200, 120] and 0.4 < r.json()["coverage"] < 0.6
        got = np.frombuffer(client.get(f"/documents/{d['id']}/selection", headers=H).content, np.uint8).reshape(120, 200)
        assert ((got > 0) & (got < 255)).any() and got[40, 40] == 255 and got[40, 190] == 0
        assert client.post(f"/documents/{d['id']}/selection/refine", json={"radius": 99}, headers=H).status_code == 422      # out of range
