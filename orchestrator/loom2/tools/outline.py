"""The outline of a binary mask as a polygon (D116: a mask *from the layer* — a character's matte, a prop's alpha, the shadows — traced into
an EffectCraft mask path). numpy + Pillow only: the largest connected region (Pillow's flood fill, in C), its outer boundary traced
pixel by pixel (Moore neighbourhood), simplified (Douglas–Peucker) and, when asked, resampled to a fixed number of points by arc length,
so the frames of a shot key the same vertex count."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

# the eight neighbours clockwise from the west, as (dy, dx); Moore tracing walks them from the one after the last backtrack
_N8 = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1)]


def binary(img: Image.Image, threshold: int = 128) -> np.ndarray:
    """A footage frame as a boolean mask: the alpha of an RGBA image, else its luma, at or above `threshold`."""
    a = np.asarray(img.getchannel("A") if img.mode in ("RGBA", "LA") else img.convert("L"))
    return a >= threshold


def clean(m: np.ndarray, radius: int = 1) -> np.ndarray:
    """A morphological open (erode, then dilate) by `radius` pixels: specks and one-pixel threads go, the body stays."""
    if radius <= 0 or not m.any():
        return m
    out = m.copy()
    for _ in range(radius):                                                 # erode
        p = np.pad(out, 1, constant_values=False)
        out = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    for _ in range(radius):                                                 # dilate
        p = np.pad(out, 1, constant_values=False)
        out = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return out


def largest_region(m: np.ndarray) -> np.ndarray:
    """The largest 4-connected region of the mask (Pillow's flood fill marks each region in turn)."""
    if not m.any():
        return m
    img = Image.fromarray(np.where(m, 255, 0).astype(np.uint8), "L").copy()   # a writable image: one built on the array is read-only and a flood fill on it is lost
    best: np.ndarray | None = None
    best_n = 0
    remaining = int(m.sum())
    while remaining > best_n:                                               # a smaller remainder cannot hold a larger region
        a = np.asarray(img)
        ys, xs = np.nonzero(a == 255)
        if not len(ys):
            break
        ImageDraw.floodfill(img, (int(xs[0]), int(ys[0])), 128)             # the topmost-leftmost pixel's region becomes 128
        a = np.asarray(img)
        region = a == 128
        n = int(region.sum())
        if n > best_n:
            best, best_n = region, n
        img = Image.fromarray(np.where(region, 0, a).astype(np.uint8), "L").copy()  # this region done: gone from the remainder
        remaining -= n
    return best if best is not None else m


def trace(m: np.ndarray) -> list[tuple[float, float]]:
    """The outer boundary of the mask's region as pixel centres (x, y), clockwise in image coordinates; the region must be one connected
    piece (`largest_region`). An empty mask gives an empty list; a single pixel its centre."""
    if not m.any():
        return []
    p = np.pad(m, 1, constant_values=False)
    ys, xs = np.nonzero(p)
    sy, sx = int(ys[0]), int(xs[0])                                           # the topmost-leftmost pixel: its west neighbour is outside
    pts: list[tuple[int, int]] = [(sy, sx)]
    cy, cx = sy, sx
    back = 0                                                                 # the direction we came from (west at the start)
    limit = int(p.sum()) * 4 + 8
    while len(pts) < limit:
        found = False
        for k in range(8):
            d = (back + 1 + k) % 8                                           # scan clockwise from the pixel after the backtrack
            ny, nx = cy + _N8[d][0], cx + _N8[d][1]
            if p[ny, nx]:
                cy, cx = ny, nx
                back = (d + 4) % 8                                           # the way back is the opposite direction
                # Jacob's stopping criterion: back at the start entering it the same way
                if (cy, cx) == (sy, sx) and len(pts) > 1 and back == 0:
                    return [(float(x - 1), float(y - 1)) for y, x in pts]
                pts.append((cy, cx))
                found = True
                break
        if not found:                                                        # an isolated pixel
            break
        if (cy, cx) == (sy, sx):
            pts.pop()
            break
    return [(float(x - 1), float(y - 1)) for y, x in pts]


def simplify(pts: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas–Peucker on a closed polygon: no point of the outline is farther than `tolerance` from the result."""
    n = len(pts)
    if n < 4 or tolerance <= 0:
        return list(pts)
    a = np.asarray(pts, dtype=np.float64)
    # split the ring at the two farthest-apart points, simplify both arcs
    i0 = 0
    d = np.hypot(*(a - a[i0]).T)
    i1 = int(np.argmax(d))
    keep = np.zeros(n, dtype=bool)
    keep[i0] = keep[i1] = True

    def dp(lo: int, hi: int) -> None:                                        # indices along the ring from lo to hi (lo < hi)
        stack = [(lo, hi)]
        while stack:
            s, e = stack.pop()
            if e - s < 2:
                continue
            seg = a[s:e + 1]
            p0, p1 = seg[0], seg[-1]
            v = p1 - p0
            L = np.hypot(*v)
            if L == 0:
                dist = np.hypot(*(seg - p0).T)
            else:
                dist = np.abs(v[0] * (seg[:, 1] - p0[1]) - v[1] * (seg[:, 0] - p0[0])) / L
            k = int(np.argmax(dist[1:-1])) + 1 if len(seg) > 2 else 0
            if k and dist[k] > tolerance:
                keep[s + k] = True
                stack.append((s, s + k))
                stack.append((s + k, e))

    lo, hi = sorted((i0, i1))
    dp(lo, hi)
    # the other arc, hi → n → lo, as one run: roll so it is contiguous
    rolled = np.roll(a, -hi, axis=0)
    keep_r = np.zeros(n, dtype=bool)
    a_saved, keep_saved = a, keep
    a = rolled
    keep = keep_r
    dp(0, (lo - hi) % n)
    a, keep = a_saved, keep_saved
    keep |= np.roll(keep_r, hi)
    return [tuple(map(float, q)) for q in a[keep]]


def resample(pts: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    """`count` points at equal arc-length steps around the closed polygon, starting at its topmost point (then leftmost): frames of a
    shot keyed this way share a vertex count and a start, so the engine interpolates sanely between keys."""
    if len(pts) < 3 or count < 3:
        return list(pts)
    a = np.asarray(pts, dtype=np.float64)
    start = int(np.lexsort((a[:, 0], a[:, 1]))[0])
    a = np.roll(a, -start, axis=0)
    ring = np.vstack([a, a[:1]])
    seg = np.hypot(*np.diff(ring, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 0:
        return [tuple(map(float, a[0]))] * count
    targets = np.linspace(0, total, count, endpoint=False)
    xs = np.interp(targets, cum, ring[:, 0])
    ys = np.interp(targets, cum, ring[:, 1])
    return [(float(x), float(y)) for x, y in zip(xs, ys)]


def outline(img: Image.Image, tolerance: float = 1.5, max_points: int = 160, fixed: int | None = None, threshold: int = 128) -> list[tuple[float, float]]:
    """The polygon around the frame's visible content: the largest cleaned region's boundary, simplified to `tolerance` pixels and at most
    `max_points` (the tolerance grows until it fits), or resampled to exactly `fixed` points. Coordinates are the frame's pixels, the
    boundary running through the edge pixels' centres grown by half a pixel outward."""
    m = largest_region(clean(binary(img, threshold)))
    pts = trace(m)
    if len(pts) < 3:
        return []
    tol = max(tolerance, 0.1)
    out = simplify(pts, tol)
    while len(out) > max_points and tol < 64:
        tol *= 1.5
        out = simplify(pts, tol)
    if fixed:
        out = resample(out, fixed)
    # half a pixel outward: the centres sit half a pixel inside the region's true edge
    c = np.asarray(out).mean(axis=0) if out else np.zeros(2)
    grown = []
    for x, y in out:
        dx, dy = x - c[0], y - c[1]
        L = float(np.hypot(dx, dy)) or 1.0
        grown.append((round(x + 0.5 * dx / L, 2), round(y + 0.5 * dy / L, 2)))
    return grown
