"""Gradient-domain ("Poisson") blending for the AI paste-back (D47).

Method: P. Pérez, M. Gangnet, A. Blake, *Poisson Image Editing*, SIGGRAPH 2003. Seamless cloning keeps the source's gradients inside
the region and matches the destination on its boundary; with the guidance field v = ∇src the solution is f = src + h, where h is the
*membrane* (harmonic) interpolant of the boundary mismatch dst − src. So an inpainted region keeps the AI texture while its colour and
light are pulled to the plate around it — VAE drift no longer shows as a halo at the seam.

The Laplace equation Δh = 0 is solved on the 4-connected grid by over-relaxed Gauss–Seidel (SOR), accelerated *cascadically*: the
problem is restricted to half resolution recursively, solved there, prolonged bilinearly as the initial guess, and a few sweeps per
level remove what is left. The sweeps are red-black ordered so each half-sweep is one vectorised numpy step. Out-of-grid neighbours
are ignored (a Neumann edge). Ported from PhotoCraft crates/algo/src/poisson.rs @ b37bff98; Copyright (c) 2026 ArtCraft Team and the
PhotoCraft contributors, MIT OR Apache-2.0.
"""
from __future__ import annotations

import numpy as np

Arr = np.ndarray
TOL = 2e-5           # max update per sweep (values 0–1)
FINE_ITERS = 30      # sweeps per level above the coarsest (PhotoCraft: within ~1e-3 of a converged solve on a 96×72 disc)
FINE_OMEGA = 1.7
COARSE_ITERS = 2000
COARSE_OMEGA = 1.85


def _neighbours(v: Arr) -> Arr:
    """Sum of the 4-neighbours (missing ones count 0); v is H×W×C."""
    s = np.zeros_like(v)
    s[1:] += v[:-1]
    s[:-1] += v[1:]
    s[:, 1:] += v[:, :-1]
    s[:, :-1] += v[:, 1:]
    return s


def _counts(h: int, w: int) -> Arr:
    n = np.full((h, w), 4.0)
    n[0] -= 1
    n[-1] -= 1
    n[:, 0] -= 1
    n[:, -1] -= 1
    return np.maximum(n, 1.0)[..., None]


def _sor(v: Arr, unknown: Arr, iters: int, omega: float) -> None:
    h, w = unknown.shape
    n = _counts(h, w)
    yy, xx = np.indices((h, w))
    red = unknown & ((yy + xx) % 2 == 0)
    black = unknown & ((yy + xx) % 2 == 1)
    for _ in range(iters):
        top = 0.0
        for colour in (red, black):
            d = omega * (_neighbours(v) / n - v)
            d[~colour] = 0
            v += d
            top = max(top, float(np.abs(d).max()) if d.size else 0.0)
        if top < TOL:
            break


def solve_membrane(v: Arr, unknown: Arr, depth: int = 0) -> Arr:
    """Solve Δv = 0 on `unknown` (H×W bool) with the other pixels of `v` (H×W×C float) as Dirichlet values; returns v."""
    h, w = unknown.shape
    n_unknown = int(unknown.sum())
    if n_unknown == 0 or n_unknown == h * w:
        return v
    if w >= 8 and h >= 8 and n_unknown > 64 and depth < 16:
        # restrict: a coarse pixel is known when any of its 2×2 children is (value = mean of the known children)
        ch, cw = -(-h // 2), -(-w // 2)
        known = np.zeros((ch * 2, cw * 2), dtype=np.float64)
        known[:h, :w] = ~unknown
        vals = np.zeros((ch * 2, cw * 2, v.shape[2]))
        vals[:h, :w] = v * (~unknown)[..., None]
        k = known.reshape(ch, 2, cw, 2).sum(axis=(1, 3))
        s = vals.reshape(ch, 2, cw, 2, -1).sum(axis=(1, 3))
        cu = k == 0
        cv = np.where(cu[..., None], 0.0, s / np.maximum(k, 1)[..., None])
        cv = solve_membrane(cv, cu, depth + 1)
        # prolong: a bilinear sample of the coarse solution as the initial guess for the unknown pixels
        fy = np.clip((np.arange(h) + 0.5) / 2 - 0.5, 0, ch - 1)
        fx = np.clip((np.arange(w) + 0.5) / 2 - 0.5, 0, cw - 1)
        y0, x0 = np.floor(fy).astype(int), np.floor(fx).astype(int)
        y1, x1 = np.minimum(y0 + 1, ch - 1), np.minimum(x0 + 1, cw - 1)
        ty, tx = (fy - y0)[:, None, None], (fx - x0)[None, :, None]
        a = cv[y0][:, x0] + (cv[y0][:, x1] - cv[y0][:, x0]) * tx
        b = cv[y1][:, x0] + (cv[y1][:, x1] - cv[y1][:, x0]) * tx
        guess = a + (b - a) * ty
        v = np.where(unknown[..., None], guess, v)
        _sor(v, unknown, FINE_ITERS, FINE_OMEGA)
    else:
        mean = v[~unknown].mean(axis=0)
        v = np.where(unknown[..., None], mean, v)
        _sor(v, unknown, COARSE_ITERS, COARSE_OMEGA)
    return v


def seamless_clone(src: Arr, dst: Arr, mask: Arr, smooth: float = 2.0) -> Arr:
    """Pérez seamless cloning: `dst` outside `mask` (H×W bool), inside `src` plus the membrane that removes the boundary mismatch.
    src / dst: H×W×C uint8 or float 0–1 (same type returned). Leave a 1-px unmasked margin for a fully Dirichlet problem.

    D47 choice: the boundary mismatch dst − src is smoothed with a Gaussian of σ = `smooth` px (normalised over the known pixels)
    before the solve — the paste-back corrects colour and light drift, not pixel noise along the seam (the alpha feather hides that),
    and smooth boundary data keeps the cascadic solve within one 8-bit step of a converged one (σ 2: 0.73 levels worst case against
    full-range noise, 10.6 unsmoothed). Work is confined to the mask's bounding box."""
    as_u8 = src.dtype == np.uint8
    mask = mask.astype(bool)
    out = (dst.astype(np.float64) / 255.0) if as_u8 else dst.astype(np.float64)
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return dst.copy()
    g = 1 + int(np.ceil(3 * smooth))
    H, W = mask.shape
    y0, y1, x0, x1 = max(0, ys.min() - g), min(H, ys.max() + g + 1), max(0, xs.min() - g), min(W, xs.max() + g + 1)
    m = mask[y0:y1, x0:x1]
    s = src[y0:y1, x0:x1].astype(np.float64) / (255.0 if as_u8 else 1.0)
    d = out[y0:y1, x0:x1]
    diff = d - s
    if smooth > 0:
        from .matting import gaussian_blur
        known = (~m).astype(np.float64)
        den = gaussian_blur(known, smooth)
        diff = np.stack([gaussian_blur(diff[..., c] * known, smooth) for c in range(diff.shape[2])], axis=-1) / np.maximum(den, 1e-9)[..., None]
    h = solve_membrane(np.where(m[..., None], 0.0, diff), m)
    out[y0:y1, x0:x1] = np.where(m[..., None], s + h, d)
    if as_u8:
        return np.clip(np.rint(out * 255), 0, 255).astype(np.uint8)
    return np.clip(out, 0, 1)
