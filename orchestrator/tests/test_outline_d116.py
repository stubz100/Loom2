"""D116: the outline of a layer's visible content as a polygon (loom2.tools.outline) — the largest region, within tolerance, a fixed count."""
import numpy as np
from PIL import Image, ImageDraw

from loom2.tools.outline import binary, clean, largest_region, outline, resample, simplify, trace


def disc(w=200, h=120, c=(100, 60), r=40, mode="L"):
    img = Image.new(mode, (w, h), 0)
    ImageDraw.Draw(img).ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=255 if mode == "L" else (255, 255, 255, 255))
    return img


def test_trace_and_simplify_follow_a_disc_within_tolerance():
    m = binary(disc())
    pts = trace(m)
    assert len(pts) > 200                                                  # the boundary, pixel by pixel
    poly = simplify(pts, 1.5)
    assert 8 <= len(poly) <= 60
    a = np.asarray(poly)
    rad = np.hypot(a[:, 0] - 100, a[:, 1] - 60)
    assert rad.min() > 37 and rad.max() < 42                               # every corner near the circle of radius 40
    out = outline(disc(), tolerance=1.5)
    assert 8 <= len(out) <= 60 and all(isinstance(x, float) for p in out for x in p)


def test_the_largest_region_wins_and_specks_go():
    img = disc()
    d = ImageDraw.Draw(img)
    d.ellipse([160, 90, 172, 102], fill=255)                               # a second, smaller blob
    d.point([(5, 5), (6, 5)], fill=255)                                    # a speck
    m = clean(binary(img))
    assert not m[5, 5]                                                     # the speck is gone
    big = largest_region(m)
    assert big[60, 100] and not big[96, 166]                               # the disc, not the blob
    out = outline(img)
    a = np.asarray(out)
    assert a[:, 0].max() < 150                                             # the polygon is the disc alone


def test_rgba_uses_the_alpha_and_a_fixed_count_resamples():
    img = disc(mode="RGBA")
    out = outline(img, fixed=48)
    assert len(out) == 48
    ys = [p[1] for p in out]
    assert out[0][1] <= min(ys) + 0.6                                      # the ring starts at the topmost point (then grown half a pixel outward)
    assert outline(Image.new("L", (50, 50), 0)) == []                      # nothing visible: no polygon
    r = resample([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)], 8)
    assert len(r) == 8 and r[0] == (0.0, 0.0) and r[2] == (10.0, 0.0)      # equal steps of 5 along a 40-long ring
