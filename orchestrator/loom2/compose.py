"""Exact layer compositor (10 §3, 05 §3b): the Python reference that renders a document stack on save / export
and defines what the GPU preview approximates. Float32, straight alpha, the W3C compositing formula with Photoshop's
blend-mode set and formulas, and Photoshop's structure (D39): clipping groups (clipped layers atop an isolated base),
pass-through groups (mixed against the backdrop below 100 % or masked) or isolated, layer masks, adjustment and filter
layers blended in their own mode. Pixels come in as uint8 RGBA arrays; the result is uint8 RGBA.
"""
from __future__ import annotations

import math
from typing import Any, Callable

import zlib

import numpy as np

Arr = np.ndarray

# D39: 2 = Photoshop clipping / pass-through / adjustment-blend semantics and formulas; 1 (implicit) = the M4 W3C-style rules.
# D40: 3 = Exposure in linear light (2.2 power), as the Photoshop oracle showed.
# Stamped into every saved document's meta so a changed render can be explained.
COMPOSE_VERSION = 3

# ---------------------------------------------------------------- separable blend functions B(cb, cs) → rgb
def _hard_light(cb: Arr, cs: Arr) -> Arr:
    return np.where(cs <= 0.5, cb * 2 * cs, 1 - (1 - cb) * (1 - (2 * cs - 1)))


# D39: Soft Light, Vivid Light, Hard Mix and the Burn / Dodge edge rule follow Photoshop, not W3C. Ported from PhotoCraft
# crates/color/src/blend.rs and crates/compose/src/psblend.rs @ b37bff98 (fitted on psd-tools blend-modes/*.psd).
# Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors. MIT OR Apache-2.0.
EDGE = 1e-4   # a backdrop within EDGE of 0 / 1 counts as exact: a value that should be 1 can arrive one rounding step below it


def _soft_light(cb: Arr, cs: Arr) -> Arr:
    # the lower half equals W3C's; the upper half is Photoshop's 2·cb·(1−cs) + √cb·(2cs−1)
    return np.where(cs <= 0.5, 2 * cb * cs + cb * cb * (1 - 2 * cs), 2 * cb * (1 - cs) + np.sqrt(np.maximum(cb, 0)) * (2 * cs - 1))


def _color_dodge(cb: Arr, cs: Arr) -> Arr:
    out = np.where(cs >= 1, 1.0, np.minimum(1.0, cb / np.maximum(1e-6, 1 - cs)))
    return np.where(cb <= EDGE, 0.0, out)


def _color_burn(cb: Arr, cs: Arr) -> Arr:
    out = np.where(cs <= 0, 0.0, 1 - np.minimum(1.0, (1 - cb) / np.maximum(1e-6, cs)))
    return np.where(cb >= 1 - EDGE, 1.0, out)


def _vivid_light(cb: Arr, cs: Arr) -> Arr:
    """Photoshop: the source extremes win (cs = 0 → 0 even over white, cs = 1 → 1 even over black)."""
    burn = 1 - np.minimum(1.0, (1 - cb) / np.maximum(1e-6, 2 * cs))
    dodge = np.minimum(1.0, cb / np.maximum(1e-6, 2 * (1 - cs)))
    return np.where(cs <= 0, 0.0, np.where(cs >= 1, 1.0, np.where(cs <= 0.5, burn, dodge)))


def _pin_light(cb: Arr, cs: Arr) -> Arr:
    return np.where(cs <= 0.5, np.minimum(cb, 2 * cs), np.maximum(cb, 2 * cs - 1))


def _hard_mix(cb: Arr, cs: Arr) -> Arr:
    """Photoshop: the thresholded *generic* vivid light (backdrop extremes win, with the EDGE rule) — `cb + cs ≥ 1` inside,
    black source over white → white, white over black → black."""
    generic = np.where(cs <= 0.5, _color_burn(cb, 2 * cs), _color_dodge(cb, 2 * cs - 1))
    return np.where(generic >= 0.5 - 1e-6, 1.0, 0.0)


SEPARABLE: dict[str, Callable[[Arr, Arr], Arr]] = {
    "normal": lambda cb, cs: cs,
    "dissolve": lambda cb, cs: cs,                       # alpha handled in composite()
    "darken": np.minimum,
    "multiply": lambda cb, cs: cb * cs,
    "color-burn": _color_burn,
    "linear-burn": lambda cb, cs: np.clip(cb + cs - 1, 0, 1),
    "lighten": np.maximum,
    "screen": lambda cb, cs: cb + cs - cb * cs,
    "color-dodge": _color_dodge,
    "linear-dodge": lambda cb, cs: np.clip(cb + cs, 0, 1),
    "overlay": lambda cb, cs: _hard_light(cs, cb),
    "soft-light": _soft_light,
    "hard-light": _hard_light,
    "vivid-light": _vivid_light,
    "linear-light": lambda cb, cs: np.clip(cb + 2 * cs - 1, 0, 1),
    "pin-light": _pin_light,
    "hard-mix": _hard_mix,
    "difference": lambda cb, cs: np.abs(cb - cs),
    "exclusion": lambda cb, cs: cb + cs - 2 * cb * cs,
    "subtract": lambda cb, cs: np.clip(cb - cs, 0, 1),
    "divide": lambda cb, cs: np.clip(cb / np.maximum(cs, 1e-6), 0, 1),
}


# ---------------------------------------------------------------- non-separable (W3C): hue / saturation / color / luminosity
def _lum(c: Arr) -> Arr:
    return 0.3 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2]


def _clip_color(c: Arr) -> Arr:
    l = _lum(c)[..., None]
    n = c.min(axis=-1, keepdims=True)
    x = c.max(axis=-1, keepdims=True)
    c = np.where(n < 0, l + (c - l) * l / np.maximum(l - n, 1e-6), c)
    c = np.where(x > 1, l + (c - l) * (1 - l) / np.maximum(x - l, 1e-6), c)
    return c


def _set_lum(c: Arr, l: Arr) -> Arr:
    d = (l - _lum(c))[..., None]
    return _clip_color(c + d)


def _sat(c: Arr) -> Arr:
    return c.max(axis=-1) - c.min(axis=-1)


def _set_sat(c: Arr, s: Arr) -> Arr:
    mx = c.max(axis=-1, keepdims=True)
    mn = c.min(axis=-1, keepdims=True)
    rng = mx - mn
    out = np.where(rng > 1e-6, (c - mn) * s[..., None] / np.maximum(rng, 1e-6), 0.0)
    return out


NON_SEPARABLE: dict[str, Callable[[Arr, Arr], Arr]] = {
    "hue": lambda cb, cs: _set_lum(_set_sat(cs, _sat(cb)), _lum(cb)),
    "saturation": lambda cb, cs: _set_lum(_set_sat(cb, _sat(cs)), _lum(cb)),
    "color": lambda cb, cs: _set_lum(cs, _lum(cb)),
    "luminosity": lambda cb, cs: _set_lum(cb, _lum(cs)),
}

BLEND_MODES = [*SEPARABLE, *NON_SEPARABLE]


def blend(mode: str, cb: Arr, cs: Arr) -> Arr:
    f = SEPARABLE.get(mode) or NON_SEPARABLE.get(mode)
    if f is None:
        raise ValueError(f"unknown blend mode {mode!r}")
    return np.clip(f(cb, cs), 0, 1)


def composite(dst: Arr, src: Arr, mode: str = "normal", alpha: Arr | float = 1.0, seed: int = 0) -> Arr:
    """`dst`, `src`: float32 HxWx4 straight alpha. `alpha` multiplies the source alpha (opacity × mask). Returns a new buffer.
    W3C: co = cs·αs·(1−αb) + cb·αb·(1−αs) + B(cb,cs)·αs·αb ; αo = αs + αb·(1−αs), then un-premultiplied."""
    cb, ab = dst[..., :3], dst[..., 3:4]
    cs = src[..., :3]
    a_s = src[..., 3:4] * (alpha if np.isscalar(alpha) else alpha[..., None])
    if mode == "dissolve":
        rng = np.random.default_rng(seed)
        a_s = np.where(rng.random(a_s.shape) < a_s, 1.0, 0.0)
    b = blend(mode, cb, cs)
    ao = a_s + ab * (1 - a_s)
    co = cs * a_s * (1 - ab) + cb * ab * (1 - a_s) + b * a_s * ab
    out = np.empty_like(dst)
    out[..., :3] = np.where(ao > 1e-6, co / np.maximum(ao, 1e-6), 0.0)
    out[..., 3:4] = ao
    return out


def _mix_premultiplied(a: Arr, b: Arr, k: Arr | float) -> Arr:
    """a·(1−k) + b·k in premultiplied colour, stored straight (PhotoCraft's pass-through mix)."""
    k_arr = (np.full(a.shape[:2], k, dtype=np.float32) if np.isscalar(k) else k)[..., None]
    wa = a[..., 3:4] * (1 - k_arr)
    wb = b[..., 3:4] * k_arr
    alpha = wa + wb
    out = np.empty_like(a)
    out[..., :3] = np.where(alpha > 1e-6, (a[..., :3] * wa + b[..., :3] * wb) / np.maximum(alpha, 1e-6), 0.0)
    out[..., 3:4] = alpha
    return out


def _boxes_for_gauss(sigma: float) -> list[int]:
    """Box radii whose three passes approximate a Gaussian of standard deviation sigma (Kovesi) — selectionOps.ts boxesForGauss."""
    n = 3
    w_ideal = math.sqrt((12 * sigma * sigma) / n + 1)
    wl = math.floor(w_ideal)
    if wl % 2 == 0:
        wl -= 1
    wu = wl + 2
    m = round((12 * sigma * sigma - n * wl * wl - 4 * n * wl - 3 * n) / (-4 * wl - 4))
    return [max(0, int(math.floor(((wl if i < m else wu) - 1) / 2 + 0.5))) for i in range(n)]


def _box_blur(src: Arr, r: int) -> Arr:
    """Running box blur of radius r, edge-clamped, horizontal then vertical — selectionOps.ts boxBlur."""
    if r < 1:
        return src
    h, w = src.shape
    n = 2 * r + 1
    xs = np.clip(np.arange(-r, w + r + 1), 0, w - 1)
    c = np.concatenate([np.zeros((h, 1)), np.cumsum(src[:, xs], axis=1)], axis=1)
    tmp = (c[:, n:n + w] - c[:, 0:w]) / n
    ys = np.clip(np.arange(-r, h + r + 1), 0, h - 1)
    c = np.concatenate([np.zeros((1, w)), np.cumsum(tmp[ys, :], axis=0)], axis=0)
    return (c[n:n + h, :] - c[0:h, :]) / n


def derived_mask(arr: Arr, density: float = 1.0, feather: float = 0.0) -> Arr:
    """D52: a layer mask as it renders — feathered (Gaussian σ = feather px as three box passes, rounded to 8 bits, exactly as the
    editor derives it) and with density (1 − density·(1 − v)). uint8 in, uint8 out."""
    out = arr
    if feather > 0:
        f = arr.astype(np.float64)
        for r in _boxes_for_gauss(feather):
            f = _box_blur(f, r)
        out = np.floor(f + 0.5).clip(0, 255).astype(np.uint8)
    if density < 1:
        out = np.floor(255 - density * (255 - out.astype(np.float64)) + 0.5).clip(0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------- adjustments f(rgb) → rgb
def _levels(rgb: Arr, p: dict) -> Arr:
    ib, iw, g = p.get("in_black", 0) / 255, p.get("in_white", 255) / 255, max(0.01, p.get("gamma", 1.0))
    ob, ow = p.get("out_black", 0) / 255, p.get("out_white", 255) / 255
    x = np.clip((rgb - ib) / max(1e-6, iw - ib), 0, 1) ** (1 / g)
    return ob + x * (ow - ob)


def _curve(x: Arr, points: list) -> Arr:
    if not points:
        return x
    pts = sorted((float(a) / 255, float(b) / 255) for a, b in points)
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    if xs[0] > 0:
        xs, ys = [0.0, *xs], [ys[0], *ys]
    if xs[-1] < 1:
        xs, ys = [*xs, 1.0], [*ys, ys[-1]]
    return np.interp(x, xs, ys)


def _curves(rgb: Arr, p: dict) -> Arr:
    out = rgb.copy()
    if p.get("rgb"):
        out = _curve(out, p["rgb"])
    for i, ch in enumerate(("r", "g", "b")):
        if p.get(ch):
            out[..., i] = _curve(out[..., i], p[ch])
    return out


def _rgb_to_hsl(rgb: Arr) -> tuple[Arr, Arr, Arr]:
    mx, mn = rgb.max(-1), rgb.min(-1)
    l = (mx + mn) / 2
    d = mx - mn
    s = np.where(d < 1e-6, 0.0, d / np.maximum(1e-6, 1 - np.abs(2 * l - 1)))
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(l)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where(mx == r, ((g - b) / np.maximum(d, 1e-6)) % 6, h)
        h = np.where(mx == g, (b - r) / np.maximum(d, 1e-6) + 2, h)
        h = np.where(mx == b, (r - g) / np.maximum(d, 1e-6) + 4, h)
    h = np.where(d < 1e-6, 0.0, h / 6) % 1.0
    return h, s, l


def _hsl_to_rgb(h: Arr, s: Arr, l: Arr) -> Arr:
    c = (1 - np.abs(2 * l - 1)) * s
    hp = (h % 1.0) * 6
    x = c * (1 - np.abs(hp % 2 - 1))
    m = l - c / 2
    z = np.zeros_like(h)
    conds = [(hp < 1), (hp < 2), (hp < 3), (hp < 4), (hp < 5)]
    r = np.select(conds, [c, x, z, z, x], default=c)
    g = np.select(conds, [x, c, c, x, z], default=z)
    b = np.select(conds, [z, z, x, c, c], default=x)
    return np.stack([r + m, g + m, b + m], axis=-1)


def _hue_sat(rgb: Arr, p: dict) -> Arr:
    h, s, l = _rgb_to_hsl(rgb)
    h = (h + p.get("hue", 0) / 360) % 1.0
    s = np.clip(s * (1 + p.get("saturation", 0) / 100), 0, 1)
    li = p.get("lightness", 0) / 100
    l = np.clip(l + li * (1 - l) if li > 0 else l * (1 + li), 0, 1)
    return _hsl_to_rgb(h, s, l)


def _color_balance(rgb: Arr, p: dict) -> Arr:
    lum = _lum(rgb)
    sh = np.clip(1 - lum * 2, 0, 1)[..., None]
    hi = np.clip(lum * 2 - 1, 0, 1)[..., None]
    mid = 1 - sh - hi
    out = rgb.copy()
    for name, w in (("shadows", sh), ("midtones", mid), ("highlights", hi)):
        shift = np.array(p.get(name, [0, 0, 0]), dtype=np.float32) / 100
        out = out + w * shift
    return np.clip(out, 0, 1)


def _brightness_contrast(rgb: Arr, p: dict) -> Arr:
    b = p.get("brightness", 0) / 100
    c = p.get("contrast", 0) / 100
    out = rgb + b
    f = (1 + c) / max(1e-6, 1 - c) if c < 1 else 1e6
    return np.clip((out - 0.5) * f + 0.5, 0, 1)


def _exposure(rgb: Arr, p: dict) -> Arr:
    """D40: Photoshop's Exposure works in linear light through a pure 2.2 power (found by the psd-tools oracle; PhotoCraft
    crates/compose/src/adjust.rs fitted the same): encode((decode(v)·2^ev + offset)^(1/gamma))."""
    ev, off, g = p.get("exposure", 0.0), p.get("offset", 0.0), max(0.01, p.get("gamma", 1.0))
    lin = np.maximum(np.maximum(rgb, 0) ** 2.2 * (2.0 ** ev) + off, 0) ** (1 / g)
    return np.clip(lin ** (1 / 2.2), 0, 1)


def _bw(rgb: Arr, p: dict) -> Arr:
    w = np.array([p.get("r", 40), p.get("g", 60), p.get("b", 20)], dtype=np.float32)
    w = w / max(1e-6, w.sum()) if w.sum() > 0 else np.array([0.3, 0.59, 0.11], dtype=np.float32)
    g = (rgb * w).sum(-1, keepdims=True)
    return np.repeat(g, 3, axis=-1)


ADJUSTMENTS: dict[str, Callable[[Arr, dict], Arr]] = {
    "levels": _levels, "curves": _curves, "hue_saturation": _hue_sat, "color_balance": _color_balance,
    "brightness_contrast": _brightness_contrast, "exposure": _exposure, "black_white": _bw, "invert": lambda rgb, p: 1 - rgb,
}


# ---------------------------------------------------------------- filters f(rgba) → rgba
def gaussian_blur(img: Arr, radius: float) -> Arr:
    """Separable Gaussian on a float HxWxC array (edge-clamped). radius ≈ sigma."""
    if radius <= 0:
        return img
    sigma = float(radius)
    r = max(1, int(math.ceil(sigma * 3)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()

    def conv_axis(a: Arr, axis: int) -> Arr:
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r, r)
        ap = np.pad(a, pad, mode="edge")
        out = np.zeros_like(a)
        for i, w in enumerate(k):
            sl = [slice(None)] * a.ndim
            sl[axis] = slice(i, i + a.shape[axis])
            out += w * ap[tuple(sl)]
        return out

    return conv_axis(conv_axis(img, 0), 1)


def _blur_premult(rgba: Arr, radius: float) -> Arr:
    pm = rgba[..., :3] * rgba[..., 3:4]
    b = gaussian_blur(np.concatenate([pm, rgba[..., 3:4]], axis=-1), radius)
    a = b[..., 3:4]
    return np.concatenate([np.where(a > 1e-6, b[..., :3] / np.maximum(a, 1e-6), 0.0), a], axis=-1)


def _sharpen(rgba: Arr, p: dict) -> Arr:
    amount, radius, threshold = p.get("amount", 100) / 100, p.get("radius", 1.0), p.get("threshold", 0) / 255
    blurred = _blur_premult(rgba, radius)
    diff = rgba[..., :3] - blurred[..., :3]
    diff = np.where(np.abs(diff) >= threshold, diff, 0.0)
    out = rgba.copy()
    out[..., :3] = np.clip(rgba[..., :3] + amount * diff, 0, 1)
    return out


def _hash32(x: np.ndarray) -> np.ndarray:
    """lowbias32 (Wellons) on uint32 arrays; the editor's shaders run the same five steps (adjustFilters.ts aj_h)."""
    x = x.astype(np.uint32, copy=True)
    x ^= x >> np.uint32(16)
    x *= np.uint32(0x7FEB352D)
    x ^= x >> np.uint32(15)
    x *= np.uint32(0x846CA68B)
    x ^= x >> np.uint32(16)
    return x


def noise_field(w: int, h: int, seed: int) -> np.ndarray:
    """Unit-variance normal noise (h, w, 3) that is a pure function of (seed, x, y): hash → two 23-bit uniforms per pair →
    Box-Muller. The GPU preview evaluates exactly this per fragment, so preview and flatten agree to rounding."""
    xs = np.arange(w, dtype=np.uint32)[None, :]
    ys = np.arange(h, dtype=np.uint32)[:, None]
    s = _hash32(np.full((1, 1), seed & 0xFFFFFFFF, dtype=np.uint32))
    with np.errstate(over="ignore"):
        k = _hash32(_hash32(s + xs) + ys)
        k2 = _hash32(k)
        k3 = _hash32(k2)
        k4 = _hash32(k3)

    def u(v: np.ndarray) -> np.ndarray:                       # (0, 1), exactly representable in float32 like the shader's
        return ((v >> np.uint32(9)).astype(np.float32) + np.float32(0.5)) / np.float32(8388608.0)

    r1 = np.sqrt(-2.0 * np.log(u(k)))
    a1 = 2.0 * np.pi * u(k2)
    r2 = np.sqrt(-2.0 * np.log(u(k3)))
    a2 = 2.0 * np.pi * u(k4)
    return np.stack([r1 * np.cos(a1), r1 * np.sin(a1), r2 * np.cos(a2)], axis=-1).astype(np.float32)


def _noise(rgba: Arr, p: dict) -> Arr:
    amt = np.float32(p.get("amount", 10) / 100)
    n = noise_field(rgba.shape[1], rgba.shape[0], int(p.get("seed", 0))) * amt
    if p.get("monochrome", True):
        n = np.repeat(n[..., :1], 3, axis=-1)
    out = rgba.copy()
    out[..., :3] = np.clip(rgba[..., :3] + n, 0, 1)
    return out


def _high_pass(rgba: Arr, p: dict) -> Arr:
    blurred = _blur_premult(rgba, p.get("radius", 3.0))
    out = rgba.copy()
    out[..., :3] = np.clip(rgba[..., :3] - blurred[..., :3] + 0.5, 0, 1)
    return out


def _hex_rgb(value: object, default: str = "#ffffff") -> Arr:
    h = str(value or default).lstrip("#")
    if len(h) != 6:
        h = default.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def _color_to_alpha(rgba: Arr, p: dict) -> Arr:
    """D49 Colour to Alpha: a pixel P that is a colour Q over the key C (P = a·Q + (1 − a)·C) gets the smallest a that keeps Q in range
    (aᵢ = (Pᵢ − Cᵢ)/(1 − Cᵢ) above the key, (Cᵢ − Pᵢ)/Cᵢ below, a = maxᵢ aᵢ), Q = C + (P − C)/a and alpha × a; thresholds (0–100 %) map
    a ≤ transparency to 0 and a ≥ opacity to 1, linear between. Over C again it gives back P. PhotoCraft crates/algo/src/color_to_alpha.rs
    @ b37bff98 (MIT OR Apache-2.0, © 2026 ArtCraft Team and the PhotoCraft contributors)."""
    key = _hex_rgb(p.get("colour"))
    t = float(np.clip(p.get("transparency_threshold", 0) / 100, 0, 1))
    o = float(np.clip(p.get("opacity_threshold", 100) / 100, 0, 1))
    c = rgba[..., :3]
    up = np.where(key < 1, (c - key) / np.maximum(1 - key, 1e-6), 1.0)
    down = np.where(key > 0, (key - c) / np.maximum(key, 1e-6), 1.0)
    a = np.clip(np.where(c > key, up, np.where(c < key, down, 0.0)).max(axis=-1), 0, 1)
    a = np.where(a <= t, 0.0, np.where(a >= o, 1.0, np.clip((a - t) / max(o - t, 1e-6), 0, 1)))[..., None]
    q = np.where(a >= 1, c, np.where(a <= 0, key, np.clip(key + (c - key) / np.maximum(a, 1e-6), 0, 1)))
    out = rgba.copy()
    out[..., :3] = q
    out[..., 3:4] = rgba[..., 3:4] * a
    return out


FILTERS: dict[str, Callable[[Arr, dict], Arr]] = {
    "gaussian_blur": lambda rgba, p: _blur_premult(rgba, p.get("radius", 2.0)),
    "sharpen": _sharpen, "noise": _noise, "high_pass": _high_pass, "color_to_alpha": _color_to_alpha,
}


# ---------------------------------------------------------------- the stack
def to_float(u8: Arr) -> Arr:
    return u8.astype(np.float32) / 255.0


def to_u8(f: Arr) -> Arr:
    return np.clip(np.rint(f * 255.0), 0, 255).astype(np.uint8)


def place(canvas_h: int, canvas_w: int, pixels: Arr, x: int, y: int) -> Arr:
    """A document-sized float RGBA buffer with `pixels` (float RGBA) pasted at (x, y), clipped."""
    out = np.zeros((canvas_h, canvas_w, 4), dtype=np.float32)
    h, w = pixels.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas_w, x + w), min(canvas_h, y + h)
    if x1 > x0 and y1 > y0:
        out[y0:y1, x0:x1] = pixels[y0 - y:y1 - y, x0 - x:x1 - x]
    return out


class Renderer:
    """Renders a document's layer tree. `pixels[layer_id]` are uint8 HxWx4 arrays, `masks[layer_id]` uint8 HxW."""

    def __init__(self, width: int, height: int, pixels: dict[str, Arr], masks: dict[str, Arr] | None = None, background: str = "transparent") -> None:
        self.w, self.h = width, height
        self.pixels, self.masks = pixels, masks or {}
        self.background = background

    def _mask_for(self, node: dict) -> Arr | None:
        m = node.get("mask")
        if not m or not m.get("enabled", True):
            return None
        arr = self.masks.get(node["id"])
        if arr is None:
            return None
        arr = derived_mask(arr, float(m.get("density", 1.0)), float(m.get("feather", 0.0)))
        # a linked mask follows the layer: its offset is relative to the layer's own (x, y)
        base_x, base_y = (int(node.get("x", 0)), int(node.get("y", 0))) if m.get("linked", True) else (0, 0)
        mx, my = base_x + int(m.get("x", 0)), base_y + int(m.get("y", 0))
        full = place(self.h, self.w, np.repeat(to_float(arr)[..., None], 4, axis=-1), mx, my)[..., 0]
        default = int(m.get("default", 0))
        if default:
            # D54: outside its extent a mask reads its default value, through the same density as the pixels inside
            outside = derived_mask(np.full((1, 1), default, dtype=np.uint8), float(m.get("density", 1.0)))[0, 0] / 255.0
            cover = place(self.h, self.w, np.ones(arr.shape + (4,), dtype=np.float32), mx, my)[..., 0]
            full = full + (1.0 - cover) * np.float32(outside)
        return full

    def _k(self, node: dict) -> Arr | float:
        """Opacity × fill × mask: how much of the node reaches what it composites onto."""
        k: Arr | float = float(node.get("opacity", 1.0)) * float(node.get("fill", 1.0))
        m = self._mask_for(node)
        return k * m if m is not None else k

    def _content(self, node: dict) -> Arr | None:
        """The node's own pixels on transparent with its mask applied (PhotoCraft `render_content`); None for adjustment and
        filter layers, which have none."""
        kind = node.get("kind", "raster")
        if kind == "raster":
            px = self.pixels.get(node["id"])
            if px is None:
                return None
            out = place(self.h, self.w, to_float(px), int(node.get("x", 0)), int(node.get("y", 0)))
        elif kind == "group":
            out = self.render_nodes(node.get("children", []), np.zeros((self.h, self.w, 4), dtype=np.float32))
        else:
            return None
        m = self._mask_for(node)
        if m is not None:
            out[..., 3] *= m
        return out

    def _apply(self, node: dict, buf: Arr) -> Arr | None:
        """An adjustment or filter layer's function applied to `buf` (None for an unknown type)."""
        kind = node.get("kind")
        fn = (ADJUSTMENTS if kind == "adjustment" else FILTERS).get(node.get("type", ""))
        if fn is None:
            return None
        if kind == "adjustment":
            out = buf.copy()
            out[..., :3] = np.clip(fn(buf[..., :3], node.get("params", {})), 0, 1)
            return out
        return fn(buf, node.get("params", {}))

    def _mix_adjusted(self, node: dict, acc: Arr, adjusted: Arr) -> Arr:
        """D39: an adjustment (or filter) result blends back in its own mode — rgb += (B(mode, rgb, adjusted) − rgb) × k. An
        adjustment keeps the backdrop's alpha; a filter (blur can move alpha) mixes alpha linearly."""
        k = self._k(node)
        k_arr = (np.full(acc.shape[:2], k, dtype=np.float32) if np.isscalar(k) else k)[..., None]
        mode = node.get("blend", "normal")
        mode = "normal" if mode == "pass-through" else mode
        out = acc.copy()
        out[..., :3] = acc[..., :3] + (blend(mode, acc[..., :3], adjusted[..., :3]) - acc[..., :3]) * k_arr
        if node.get("kind") == "adjustment":
            return np.where(acc[..., 3:4] > 0, out, acc)
        out[..., 3:4] = acc[..., 3:4] * (1 - k_arr) + adjusted[..., 3:4] * k_arr
        return out

    def _atop(self, clipped: list[dict], base: Arr) -> Arr:
        """D39: clipped layers composite atop their base — blended as if the base were opaque, the base's alpha kept."""
        for c in clipped:
            kind = c.get("kind", "raster")
            if kind in ("adjustment", "filter"):
                adjusted = self._apply(c, base)
                if adjusted is not None:
                    mixed = self._mix_adjusted(c, base, adjusted)
                    base = np.concatenate([mixed[..., :3], base[..., 3:4]], axis=-1)
                continue
            src = self._content(c)
            if src is None:
                continue
            opaque = base.copy()
            opaque[..., 3] = 1.0
            mode = c.get("blend", "normal")
            r = composite(opaque, src, "normal" if mode == "pass-through" else mode, float(c.get("opacity", 1.0)) * float(c.get("fill", 1.0)),
                          seed=zlib.crc32(c["id"].encode("utf-8")) & 0xFFFF)
            base = np.concatenate([np.where(base[..., 3:4] > 0, r[..., :3], base[..., :3]), base[..., 3:4]], axis=-1)
        return base

    def render_nodes(self, nodes: list[dict], backdrop: Arr) -> Arr:
        """Nodes are top-first (ORA order); render bottom-up onto the backdrop. A node followed (above) by `clip` nodes forms a
        clipping group with them (D39); a clipped node with no unclipped node below it renders as an ordinary layer."""
        order = list(reversed(nodes))
        acc = backdrop
        i = 0
        while i < len(order):
            base = order[i]
            j = i + 1
            if not base.get("clip"):
                while j < len(order) and order[j].get("clip"):
                    j += 1
            if base.get("visible", True):
                acc = self._node(base, [c for c in order[i + 1:j] if c.get("visible", True)], acc)
            i = j
        return acc

    def _node(self, node: dict, clipped: list[dict], acc: Arr) -> Arr:
        kind = node.get("kind", "raster")
        mode = node.get("blend", "normal")
        if kind in ("adjustment", "filter"):
            adjusted = self._apply(node, acc)
            if adjusted is None:
                return acc
            if clipped:
                adjusted = self._atop(clipped, adjusted)
            return self._mix_adjusted(node, acc, adjusted)
        if kind == "group":
            m = node.get("mask")
            masked = bool(m and m.get("enabled", True))
            # C28 / D39: pass-through when flagged, Normal or Pass Through, not clipped and with no clipping group of its own
            passthrough = node.get("passthrough", True) and mode in ("normal", "pass-through") and not node.get("clip") and not clipped
            if passthrough:
                opacity = float(node.get("opacity", 1.0))
                if abs(opacity - 1.0) < 1e-6 and not masked:
                    return self.render_nodes(node.get("children", []), acc)
                # D39: below 100 % or masked, the children still composite into the backdrop; the result is mixed against the
                # original backdrop by opacity × mask (premultiplied), so adjustments inside keep reaching the layers below
                out = self.render_nodes(node.get("children", []), acc.copy())
                return _mix_premultiplied(acc, out, self._k(node))
        content = self._content(node)
        if content is None:
            return acc
        if clipped:
            content = self._atop(clipped, content)
        k = float(node.get("opacity", 1.0)) * float(node.get("fill", 1.0))
        return composite(acc, content, "normal" if mode == "pass-through" else mode, k, seed=zlib.crc32(node["id"].encode("utf-8")) & 0xFFFF)

    def flatten(self, nodes: list[dict]) -> Arr:
        base = np.zeros((self.h, self.w, 4), dtype=np.float32)
        if self.background and self.background != "transparent":
            c = self.background.lstrip("#")
            r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
            base[..., :3] = (r, g, b)
            base[..., 3] = 1.0
        return self.render_nodes(nodes, base)

    def flatten_u8(self, nodes: list[dict]) -> Arr:
        return to_u8(self.flatten(nodes))


def srgb_delta(a_u8: Arr, b_u8: Arr) -> dict[str, float]:
    """A cheap per-channel difference summary for the acceptance (10 §14 item 1): mean / p99 / max in 0–255."""
    d = np.abs(a_u8.astype(np.int16) - b_u8.astype(np.int16))
    return {"mean": float(d.mean()), "p99": float(np.percentile(d, 99)), "max": float(d.max())}


def all_blend_modes() -> list[str]:
    return list(BLEND_MODES)


def _unused(_: Any) -> None:  # keeps the module's public surface explicit for linters
    return None
