"""D44: the bounded Euclidean distance transform and the round, fractional expand / contract it drives (edit_ai's dilate / erode)."""
import numpy as np

from loom2 import edit_ai, maskops


def brute(inside: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(inside)
    yy, xx = np.mgrid[0:inside.shape[0], 0:inside.shape[1]]
    return np.sqrt(((yy[..., None] - ys) ** 2 + (xx[..., None] - xs) ** 2).min(-1))


def test_edt_is_exact_up_to_the_cap():
    rng = np.random.default_rng(7)
    for _ in range(6):
        m = rng.random((37, 51)) < 0.04
        m[0, 0] = True
        for cap in (3, 8, 20):
            assert np.allclose(maskops.edt_bounded(m, cap), np.minimum(brute(m), cap + 1), atol=1e-5)


def test_expanding_a_point_gives_a_disc():
    m = np.zeros((41, 41), np.uint8)
    m[20, 20] = 255
    out = maskops.expand(m, 10)
    yy, xx = np.mgrid[0:41, 0:41]
    d = np.hypot(yy - 20, xx - 20)
    assert (out[d <= 10] == 255).all()                       # full inside the radius
    assert (out[d >= 11] == 0).all()                         # nothing beyond r + 1
    rim = (d > 10) & (d < 11)
    assert ((out[rim] > 0) & (out[rim] < 255)).any()         # a fractional, anti-aliased rim
    assert out[20, 31] == 0 and out[31, 31] == 0             # round, not the square PIL's MaxFilter made


def test_contract_and_expand_are_complementary_and_monotone():
    m = np.zeros((60, 80), np.uint8)
    m[15:45, 20:60] = 255
    grown, shrunk = maskops.expand(m, 5), maskops.contract(m, 5)
    assert (grown >= m).all() and (shrunk <= m).all()
    assert shrunk[15 + 5, 40] == 255 and shrunk[15 + 3, 40] == 0
    assert grown[15 - 5, 40] == 255 and grown[15 - 7, 40] == 0
    assert np.array_equal(edit_ai.dilate(m, 5), grown) and np.array_equal(edit_ai.erode(m, 5), shrunk)


def test_empty_and_zero_radius_are_no_ops():
    m = np.zeros((10, 10), np.uint8)
    assert np.array_equal(maskops.expand(m, 4), m)
    full = np.full((10, 10), 255, np.uint8)
    assert np.array_equal(maskops.contract(full, 0), full) and np.array_equal(maskops.expand(full, 0), full)
