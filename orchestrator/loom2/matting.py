"""Refine Edge (D45, Photoshop's Select and Mask): soft, image-aware selection edges for hair, fur and blur, and the clean-up pass
for BiRefNet / SAM 3 masks that come back at ≤ 1024 px and hard-edged.

* Soft edges come from the **guided filter** (K. He, J. Sun and X. Tang, "Guided Image Filtering", PAMI 2013): filtering the selection
  with the image as guide fits a local linear model α ≈ aᵀI + b in every window, so the mask takes on the image's own transitions —
  but only inside a band of `radius` px around the selection edge (by the exact distance transform of maskops).
* **Smart radius** adapts the band per pixel to the transition width the image shows (local luminance range ÷ local max gradient): hard
  edges stay hard, hair gets a wide band.
* Then, in Photoshop's order: Smooth (blur σ = smooth/100·4, then a contrast regain), Feather (Gaussian σ = feather / 2), Contrast and
  Shift Edge (grey dilation / erosion by % of max(radius, 4 px)).

Only the 256² tiles that touch the edge band run the guided filter, so the cost follows the edge's length, not the selection's area.
Ported from PhotoCraft crates/algo/src/matting.rs @ b37bff98; Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors,
MIT OR Apache-2.0.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from . import maskops

Arr = np.ndarray
EPS = 1e-4          # guided-filter regulariser (colour guide, samples in 0–1)
TILE = 256


@dataclass(frozen=True)
class RefineParams:
    radius: float = 10.0          # edge band, px (0 = no image-guided step)
    smart_radius: bool = True
    smooth: float = 0.0           # 0–100
    feather: float = 0.0          # px
    contrast: float = 0.0         # 0–100
    shift_edge: float = 0.0       # −100–100, % of max(radius, 4 px)

    @property
    def gf_radius(self) -> int:
        return int(np.clip(np.ceil(self.radius), 1, 64))

    @property
    def smooth_sigma(self) -> float:
        return float(np.clip(self.smooth, 0, 100)) / 100 * 4

    @property
    def feather_sigma(self) -> float:
        return max(0.0, self.feather) / 2

    @property
    def shift_px(self) -> int:
        return int(np.clip(round(np.clip(self.shift_edge, -100, 100) / 100 * max(self.radius, 4.0)), -64, 64))

    @property
    def halo(self) -> int:
        """Pixels the guided step reads around an output pixel."""
        g = self.gf_radius
        return max(int(np.ceil(self.radius)), 2 * g + (g + 1 if self.smart_radius else 0)) + 2


DEFAULTS = RefineParams()
RANGES = {"radius": [0, 64, 0.5], "smooth": [0, 100, 1], "feather": [0, 64, 0.5], "contrast": [0, 100, 1], "shift_edge": [-100, 100, 1]}


def params_from(model) -> RefineParams:
    """A RefineParams from the API model (recipes.RefineEdge) or any object with the same fields."""
    return RefineParams(**{k: getattr(model, k) for k in asdict(DEFAULTS)})


def capabilities() -> dict:
    """What `/capabilities` publishes (T8): the defaults the panel shows are the ones the worker runs."""
    return {"defaults": asdict(DEFAULTS), "ranges": RANGES}


# ---- primitives ------------------------------------------------------------------------------------------------------
def box_mean(src: Arr, r: int) -> Arr:
    """Mean over a (2r+1)² window clipped to the image (divided by the pixels actually covered), separable via cumulative sums."""
    h, w = src.shape
    out = np.empty_like(src, dtype=np.float64)
    c = np.concatenate([np.zeros((h, 1)), np.cumsum(src, axis=1, dtype=np.float64)], axis=1)
    x = np.arange(w)
    lo, hi = np.clip(x - r, 0, w), np.clip(x + r + 1, 0, w)
    tmp = (c[:, hi] - c[:, lo]) / (hi - lo)
    c = np.concatenate([np.zeros((1, w)), np.cumsum(tmp, axis=0)], axis=0)
    y = np.arange(h)
    lo, hi = np.clip(y - r, 0, h), np.clip(y + r + 1, 0, h)
    out[:] = (c[hi, :] - c[lo, :]) / (hi - lo)[:, None]
    return out


def guided_filter_color(guide: Arr, p: Arr, r: int, eps: float = EPS) -> Arr:
    """He et al. Eq. 19–21 with a colour guide: a_k = (Σ_k + εU)⁻¹ cov_k(I, p), b_k = p̄_k − a_kᵀ μ_k; q = āᵀ I + b̄."""
    I = [guide[..., c].astype(np.float64) for c in range(3)]
    p = p.astype(np.float64)
    mu = [box_mean(c, r) for c in I]
    mp = box_mean(p, r)
    cov = [box_mean(c * p, r) - m * mp for c, m in zip(I, mu)]
    s = {}
    for a, b in ((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2)):
        s[a, b] = box_mean(I[a] * I[b], r) - mu[a] * mu[b]
    rr, rg, rb, gg, gb, bb = s[0, 0] + eps, s[0, 1], s[0, 2], s[1, 1] + eps, s[1, 2], s[2, 2] + eps
    i00, i01, i02 = gg * bb - gb * gb, gb * rb - rg * bb, rg * gb - gg * rb
    i11, i12, i22 = rr * bb - rb * rb, rb * rg - rr * gb, rr * gg - rg * rg
    det = rr * i00 + rg * i01 + rb * i02
    ok = np.abs(det) > 1e-30
    det = np.where(ok, det, 1.0)
    a0 = np.where(ok, (i00 * cov[0] + i01 * cov[1] + i02 * cov[2]) / det, 0.0)
    a1 = np.where(ok, (i01 * cov[0] + i11 * cov[1] + i12 * cov[2]) / det, 0.0)
    a2 = np.where(ok, (i02 * cov[0] + i12 * cov[1] + i22 * cov[2]) / det, 0.0)
    b = mp - a0 * mu[0] - a1 * mu[1] - a2 * mu[2]
    return box_mean(a0, r) * I[0] + box_mean(a1, r) * I[1] + box_mean(a2, r) * I[2] + box_mean(b, r)


def _running_extreme(src: Arr, r: int, axis: int, use_max: bool) -> Arr:
    """Max (or min) over a window of radius r along `axis` (edge-clipped), van Herk / Gil–Werman with block-wise accumulations —
    a constant number of passes whatever r."""
    a = np.moveaxis(src, axis, -1)
    n = a.shape[-1]
    k = 2 * r + 1
    pad = -np.inf if use_max else np.inf
    m = -(-(n + 2 * r) // k) * k
    padded = np.full(a.shape[:-1] + (m,), pad, dtype=np.float64)
    padded[..., r:r + n] = a
    blocks = padded.reshape(a.shape[:-1] + (m // k, k))
    acc = np.maximum.accumulate if use_max else np.minimum.accumulate
    g = acc(blocks, axis=-1).reshape(padded.shape)
    hb = acc(blocks[..., ::-1], axis=-1)[..., ::-1].reshape(padded.shape)
    f = np.maximum if use_max else np.minimum
    out = f(hb[..., :n], g[..., 2 * r:2 * r + n])
    return np.moveaxis(out, -1, axis)


def _square_extreme(src: Arr, r: int, use_max: bool) -> Arr:
    return _running_extreme(_running_extreme(src, r, 1, use_max), r, 0, use_max)


def edge_width(guide: Arr, r: int) -> Arr:
    """Per-pixel transition width (px) of the guide's luminance: local range ÷ local max gradient (a step gives ≈ 2, a ramp of width
    L gives ≈ L)."""
    y = 0.299 * guide[..., 0] + 0.587 * guide[..., 1] + 0.114 * guide[..., 2]
    gx = (np.concatenate([y[:, 1:], y[:, -1:]], axis=1) - np.concatenate([y[:, :1], y[:, :-1]], axis=1)) / 2
    gy = (np.concatenate([y[1:], y[-1:]], axis=0) - np.concatenate([y[:1], y[:-1]], axis=0)) / 2
    g = np.sqrt(gx * gx + gy * gy)
    return (_square_extreme(y, r, True) - _square_extreme(y, r, False)) / np.maximum(_square_extreme(g, r, True), 1e-4)


def gaussian_blur(src: Arr, sigma: float) -> Arr:
    """Separable Gaussian, edge-clamped (radius 3σ)."""
    if sigma < 0.1:
        return src
    r = int(np.ceil(sigma * 3))
    k = np.exp(-(np.arange(-r, r + 1) ** 2) / (2 * sigma * sigma))
    k /= k.sum()
    h, w = src.shape
    padded = np.pad(src, ((0, 0), (r, r)), mode="edge")
    tmp = sum(k[i] * padded[:, i:i + w] for i in range(2 * r + 1))
    padded = np.pad(tmp, ((r, r), (0, 0)), mode="edge")
    return sum(k[i] * padded[i:i + h] for i in range(2 * r + 1))


def morph(src: Arr, r: int, grow: bool) -> Arr:
    """Grey dilation (grow) or erosion by about r px: alternating 3×3 square and cross steps (an octagon)."""
    f = np.maximum if grow else np.minimum
    cur = src
    for k in range(r):
        p = np.pad(cur, 1, mode="edge")
        nxt = f(f(p[1:-1, :-2], p[1:-1, 2:]), f(p[:-2, 1:-1], p[2:, 1:-1]))
        if k % 2 == 0:
            nxt = f(nxt, f(f(p[:-2, :-2], p[:-2, 2:]), f(p[2:, :-2], p[2:, 2:])))
        cur = f(cur, nxt)
    return cur


# ---- refine ----------------------------------------------------------------------------------------------------------
def refine(mask: Arr, image: Arr, params: RefineParams = DEFAULTS) -> Arr:
    """Refine a uint8 selection (H×W) against an image (H×W×3 or ×4, uint8 or float 0–1); returns uint8."""
    m = mask.astype(np.float64) / 255.0
    img = image[..., :3].astype(np.float64)
    if image.dtype == np.uint8:
        img /= 255.0
    h, w = m.shape
    a = m.copy()
    if params.radius > 0:
        binary = m >= 0.5
        boundary = np.zeros_like(binary)
        boundary[:, 1:] |= binary[:, 1:] != binary[:, :-1]
        boundary[:, :-1] |= binary[:, 1:] != binary[:, :-1]
        boundary[1:] |= binary[1:] != binary[:-1]
        boundary[:-1] |= binary[1:] != binary[:-1]
        if boundary.any():
            reach = int(np.ceil(params.radius)) + 1
            dist = maskops.edt_bounded(boundary, reach)
            band = dist <= reach
            r, halo = params.gf_radius, params.halo
            for ty in range(0, h, TILE):
                for tx in range(0, w, TILE):
                    tb = band[ty:ty + TILE, tx:tx + TILE]
                    if not tb.any():
                        continue
                    y0, y1 = max(0, ty - halo), min(h, ty + TILE + halo)
                    x0, x1 = max(0, tx - halo), min(w, tx + TILE + halo)
                    q = np.clip(guided_filter_color(img[y0:y1, x0:x1], m[y0:y1, x0:x1], r), 0, 1)
                    cy, cx = ty - y0, tx - x0
                    th, tw = tb.shape
                    q = q[cy:cy + th, cx:cx + tw]
                    if params.smart_radius:
                        widths = edge_width(img[y0:y1, x0:x1], r)[cy:cy + th, cx:cx + tw]
                        reff = np.clip(widths, 1.5, max(params.radius, 1.5))
                    else:
                        reff = params.radius
                    wgt = np.clip(reff + 1 - dist[ty:ty + th, tx:tx + tw], 0, 1)
                    mt = m[ty:ty + th, tx:tx + tw]
                    a[ty:ty + th, tx:tx + tw] = mt + (q - mt) * wgt
    ss = params.smooth_sigma
    if ss >= 0.3:
        a = np.clip((gaussian_blur(a, ss) - 0.5) * (1 + ss) + 0.5, 0, 1)
    a = gaussian_blur(a, params.feather_sigma)
    if params.contrast > 0:
        gain = 1 / (1 - 0.99 * float(np.clip(params.contrast, 0, 100)) / 100)
        a = np.clip((a - 0.5) * gain + 0.5, 0, 1)
    if params.shift_px:
        a = morph(a, abs(params.shift_px), params.shift_px > 0)
    return np.clip(np.rint(a * 255), 0, 255).astype(np.uint8)
