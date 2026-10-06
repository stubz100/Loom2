"""FaceSim advisory (11 §11 item 6): the geometry that wraps the ONNX models is tested without weights (Umeyama alignment,
SCRFD decode helpers, NMS), and the integration degrades to a clear status when the weights are not fetched."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from loom2.tools import facesim


def test_umeyama_recovers_a_similarity_transform():
    rng = np.random.default_rng(1)
    src = rng.uniform(0, 100, (5, 2))
    ang, scale, t = 0.3, 1.7, np.array([12.0, -5.0])
    r = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    dst = (scale * (r @ src.T)).T + t
    m = facesim.umeyama(src, dst)
    mapped = (m[:, :2] @ src.T).T + m[:, 2]
    assert np.allclose(mapped, dst, atol=1e-6)
    assert abs(np.linalg.norm(m[:, 0]) - scale) < 1e-6


def test_warp_face_puts_the_landmarks_on_the_template():
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    kps = facesim.ARCFACE_DST * 2.0 + np.array([60.0, 40.0])          # the template scaled ×2 and shifted
    for x, y in kps.astype(int):
        img[y - 2:y + 3, x - 2:x + 3] = 255
    out = facesim.warp_face(img, kps)
    assert out.shape == (112, 112, 3)
    for x, y in facesim.ARCFACE_DST.astype(int):
        assert out[y, x].max() > 128, (x, y)                            # each landmark lands on its template spot


def test_scrfd_decode_helpers_and_nms():
    pts = np.array([[10.0, 10.0], [50.0, 50.0]])
    boxes = facesim.distance2bbox(pts, np.array([[2, 3, 4, 5], [1, 1, 1, 1]], dtype=float))
    assert boxes.tolist() == [[8, 7, 14, 15], [49, 49, 51, 51]]
    kps = facesim.distance2kps(pts, np.tile(np.array([[1.0, -1.0]]), (2, 5)))
    assert kps.shape == (2, 10) and kps[0, 0] == 11 and kps[0, 1] == 9
    dets = np.array([[0, 0, 10, 10, 0.9], [1, 1, 11, 11, 0.8], [50, 50, 60, 60, 0.7]], dtype=np.float32)
    assert facesim.nms(dets, 0.4) == [0, 2]


def test_missing_weights_are_reported_not_raised_through_the_store(tmp_path: Path):
    assert facesim.available(tmp_path) is False
    with pytest.raises(FileNotFoundError):
        facesim.FaceSim(tmp_path)


def test_clip_identity_on_the_rig_weights_if_present():
    """Runs only where scripts/fetch_facesim.py has been run (the rig): two renders of the same face must match."""
    from loom2.config import AppState, default_state_dir

    root = Path(AppState(default_state_dir()).settings.models_root)
    if not facesim.available(root):
        pytest.skip("FaceSim weights not fetched")
    bench = Path(__file__).resolve().parents[2] / "bench" / "i2v" / "frames"
    a, b = bench / "rooftop-night_s20261004.png", bench / "rooftop-standing_s20261004.png"
    if not (a.is_file() and b.is_file()):
        pytest.skip("bench frames missing")
    from PIL import Image

    fs = facesim.FaceSim(root)
    ref = np.asarray(Image.open(a).convert("RGB"))
    res = facesim.clip_identity(fs, ref, [a, b], samples=2)
    assert res["status"] == "ok" and res["with_face"] == 2 and res["per_frame"][0]["sim"] > 0.9       # the frame vs itself
