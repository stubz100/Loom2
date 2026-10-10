"""D57 curves: PhotoCraft's natural-spline curve LUT (compose.spline_lut / lut_lookup), each channel before the master for
`interp: "spline"`, and pre-D57 documents (no `interp`) keep their straight-line curves, master first, exactly."""
import numpy as np

from loom2 import compose


def test_identity_curve_is_identity():
    t = compose.spline_lut([[0, 0], [255, 255]])
    x = np.arange(compose.CURVE_LUT_N) / (compose.CURVE_LUT_N - 1)
    assert len(t) == 4096 and np.abs(t - x).max() < 1e-4


def test_s_curve_is_monotone_and_bends_like_photoshop():
    t = compose.spline_lut([[0, 0], [64, 40], [191, 215], [255, 255]])
    assert np.all(np.diff(t) >= -1e-6)
    assert t[1023] < 0.25 and t[3071] > 0.75


def test_flat_outside_the_end_points_and_clamped():
    t = compose.spline_lut([[30, 20], [128, 250], [220, 200]])
    assert np.allclose(t[: int(30 / 255 * 4095)], 20 / 255) and np.allclose(t[int(221 / 255 * 4095) + 1:], 200 / 255)
    assert t.max() <= 1.0 and t.min() >= 0.0
    over = compose.spline_lut([[0, 0], [100, 250], [140, 255], [255, 0]])
    assert over.max() == 1.0                                       # the overshoot between points is clamped


def test_spline_passes_through_its_points():
    pts = [[0, 10], [70, 120], [180, 90], [255, 240]]
    t = compose.spline_lut(pts)
    for a, b in pts:
        assert abs(float(compose.lut_lookup(t, np.float32(a / 255))) - b / 255) < 2e-3


def test_channel_curve_runs_before_the_master():
    rgb = np.full((1, 1, 3), 0.5, dtype=np.float32)
    p = {"interp": "spline", "rgb": [[0, 0], [255, 128]], "r": [[0, 0], [128, 255], [255, 255]]}
    out = compose.ADJUSTMENTS["curves"](rgb, p)
    # r: 0.5 → ≈1 through its curve, then the master halves it → ≈0.5; g, b: only the master → 0.25
    assert abs(out[0, 0, 0] - 0.5) < 0.01 and abs(out[0, 0, 1] - 0.25) < 0.01


def test_pre_d57_curves_keep_their_lines_master_first():
    rgb = np.linspace(0, 1, 256, dtype=np.float32).reshape(1, 256, 1).repeat(3, axis=2)
    p = {"rgb": [[0, 0], [128, 200], [255, 255]], "r": [[0, 255], [255, 0]]}
    out = compose.ADJUSTMENTS["curves"](rgb, p)
    m = compose._curve(rgb[..., 0], p["rgb"])
    assert np.allclose(out[..., 1], m) and np.allclose(out[..., 0], compose._curve(m, p["r"]))
