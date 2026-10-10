"""Mask geometry for selections and AI masks (D44): an exact Euclidean distance transform, bounded to the radius in use, and the
round, fractional expand / contract built on it — the same rules as the editor's selectionOps.ts.

expand(v, r) = max(v, clamp(r + 1 − d)) where d is the distance to the nearest pixel with v ≥ 128, so a single selected pixel grows
into a disc of radius r with an anti-aliased rim (PIL's MaxFilter grew squares). Ported from PhotoCraft crates/algo/src/selection.rs
@ b37bff98; Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors, MIT OR Apache-2.0.

The distance is exact up to `cap` and saturates beyond it: an exact 1-D distance along each row (two running scans), then for each
pixel the minimum of g(y')² + (y − y')² over |y − y'| ≤ cap — any nearer pixel within `cap` must lie in that band. Work is
confined to the mask's bounding box grown by `cap`.
"""
from __future__ import annotations

import numpy as np

Arr = np.ndarray


def edt_bounded(inside: Arr, cap: int) -> Arr:
    """Euclidean distance (float32) from each pixel to the nearest True pixel of `inside`; values above `cap` read as cap + 1."""
    h, w = inside.shape
    far = float(cap + 1)
    if not inside.any():
        return np.full((h, w), far, dtype=np.float32)
    big = w + h + cap + 2
    idx = np.arange(w, dtype=np.int64)[None, :]
    left = np.where(inside, idx, -big)
    np.maximum.accumulate(left, axis=1, out=left)
    right = np.where(inside, idx, w + big)
    right = np.minimum.accumulate(right[:, ::-1], axis=1)[:, ::-1]
    g = np.minimum(idx - left, right - idx).astype(np.float64)
    np.minimum(g, far, out=g)
    g2 = g * g
    d2 = g2.copy()
    for dy in range(1, cap + 1):
        add = float(dy * dy)
        if add >= far * far:
            break
        np.minimum(d2[dy:], g2[:-dy] + add, out=d2[dy:])
        np.minimum(d2[:-dy], g2[dy:] + add, out=d2[:-dy])
    return np.minimum(np.sqrt(d2), far).astype(np.float32)


def _bbox(mask: Arr, grow: int) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return None
    h, w = mask.shape
    return max(0, int(ys.min()) - grow), min(h, int(ys.max()) + grow + 1), max(0, int(xs.min()) - grow), min(w, int(xs.max()) + grow + 1)


def expand(mask: Arr, r: float) -> Arr:
    """Grow a uint8 mask by r px (round, fractional rim)."""
    if r <= 0:
        return mask
    cap = int(np.ceil(r)) + 1
    inside = mask >= 128
    box = _bbox(inside, cap)
    if box is None:
        return mask
    y0, y1, x0, x1 = box
    d = edt_bounded(inside[y0:y1, x0:x1], cap)
    grown = np.clip(r + 1 - d, 0, 1) * 255
    out = mask.copy()
    out[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1], np.rint(grown).astype(np.uint8))
    return out


def contract(mask: Arr, r: float) -> Arr:
    """Shrink a uint8 mask by r px: the complement grown by r."""
    if r <= 0:
        return mask
    return (255 - expand(255 - mask, r)).astype(np.uint8)
