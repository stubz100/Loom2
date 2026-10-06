"""Exact layer compositor (10 §3, 05 §3b): the Python reference that renders a document stack on save / export
and defines what the GPU preview approximates. Float32, straight alpha, W3C compositing formulas with the
Photoshop blend-mode set, groups (pass-through or isolated), layer masks, clipping, adjustment and filter
layers. Pixels come in as uint8 RGBA arrays; the result is uint8 RGBA.
"""
from __future__ import annotations

import math
from typing import Any, Callable

import zlib

import numpy as np

Arr = np.ndarray

# ---------------------------------------------------------------- separable blend functions B(cb, cs) → rgb
def _hard_light(cb: Arr, cs: Arr) -> Arr:
    return np.where(cs <= 0.5, cb * 2 * cs, 1 - (1 - cb) * (1 - (2 * cs - 1)))


def _soft_light(cb: Arr, cs: Arr) -> Arr:
    d = np.where(cb <= 0.25, ((16 * cb - 12) * cb + 4) * cb, np.sqrt(cb))
    return np.where(cs <= 0.5, cb - (1 - 2 * cs) * cb * (1 - cb), cb + (2 * cs - 1) * (d - cb))


def _color_dodge(cb: Arr, cs: Arr) -> Arr:
    out = np.where(cs >= 1, 1.0, np.minimum(1.0, cb / np.maximum(1e-6, 1 - cs)))
    return np.where(cb <= 0, 0.0, out)


def _color_burn(cb: Arr, cs: Arr) -> Arr:
    out = np.where(cs <= 0, 0.0, 1 - np.minimum(1.0, (1 - cb) / np.maximum(1e-6, cs)))
    return np.where(cb >= 1, 1.0, out)


def _vivid_light(cb: Arr, cs: Arr) -> Arr:
    return np.where(cs <= 0.5, _color_burn(cb, 2 * cs), _color_dodge(cb, 2 * cs - 1))


def _pin_light(cb: Arr, cs: Arr) -> Arr:
    return np.where(cs <= 0.5, np.minimum(cb, 2 * cs), np.maximum(cb, 2 * cs - 1))


def _hard_mix(cb: Arr, cs: Arr) -> Arr:
    return np.where(_vivid_light(cb, cs) < 0.5, 0.0, 1.0)


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
    ev, off, g = p.get("exposure", 0.0), p.get("offset", 0.0), max(0.01, p.get("gamma", 1.0))
    return np.clip((rgb * (2.0 ** ev) + off), 0, 1) ** (1 / g)


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


def _noise(rgba: Arr, p: dict) -> Arr:
    rng = np.random.default_rng(int(p.get("seed", 0)))
    amt = p.get("amount", 10) / 100
    n = rng.normal(0, amt, rgba[..., :3].shape).astype(np.float32)
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


FILTERS: dict[str, Callable[[Arr, dict], Arr]] = {
    "gaussian_blur": lambda rgba, p: _blur_premult(rgba, p.get("radius", 2.0)),
    "sharpen": _sharpen, "noise": _noise, "high_pass": _high_pass,
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
        # a linked mask follows the layer: its offset is relative to the layer's own (x, y)
        base_x, base_y = (int(node.get("x", 0)), int(node.get("y", 0))) if m.get("linked", True) else (0, 0)
        full = place(self.h, self.w, np.repeat(to_float(arr)[..., None], 4, axis=-1), base_x + int(m.get("x", 0)), base_y + int(m.get("y", 0)))
        return full[..., 0]

    def _layer_alpha(self, node: dict, below: Arr | None) -> Arr | float:
        a: Arr | float = float(node.get("opacity", 1.0)) * float(node.get("fill", 1.0))
        m = self._mask_for(node)
        if m is not None:
            a = a * m
        if node.get("clip") and below is not None:
            a = a * below[..., 3]
        return a

    def render_nodes(self, nodes: list[dict], backdrop: Arr) -> Arr:
        """Nodes are top-first (ORA order); render bottom-up onto the backdrop."""
        acc = backdrop
        for node in reversed(nodes):
            if not node.get("visible", True):
                continue
            kind = node.get("kind", "raster")
            mode = node.get("blend", "normal")
            if kind == "raster":
                px = self.pixels.get(node["id"])
                if px is None:
                    continue
                src = place(self.h, self.w, to_float(px), int(node.get("x", 0)), int(node.get("y", 0)))
                acc = composite(acc, src, mode, self._layer_alpha(node, acc), seed=zlib.crc32(node["id"].encode("utf-8")) & 0xFFFF)
            elif kind == "group":
                children = node.get("children", [])
                passthrough = node.get("passthrough", True) and mode in ("normal", "pass-through") and not node.get("mask")
                if passthrough and abs(float(node.get("opacity", 1.0)) - 1.0) < 1e-6:
                    acc = self.render_nodes(children, acc)
                else:
                    inner = self.render_nodes(children, np.zeros_like(acc))
                    acc = composite(acc, inner, "normal" if mode == "pass-through" else mode, self._layer_alpha(node, acc))
            elif kind in ("adjustment", "filter"):
                table = ADJUSTMENTS if kind == "adjustment" else FILTERS
                fn = table.get(node.get("type", ""))
                if fn is None:
                    continue
                if kind == "adjustment":
                    adjusted = acc.copy()
                    adjusted[..., :3] = np.clip(fn(acc[..., :3], node.get("params", {})), 0, 1)
                else:
                    adjusted = fn(acc, node.get("params", {}))
                # the adjusted backdrop replaces the backdrop where the layer's alpha allows
                a = self._layer_alpha(node, acc)
                a_arr = (np.full(acc.shape[:2], a, dtype=np.float32) if np.isscalar(a) else a)[..., None]
                keep = acc[..., 3:4] > 0
                mixed = acc * (1 - a_arr) + adjusted * a_arr
                acc = np.where(keep, mixed, acc) if kind == "adjustment" else mixed
        return acc

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
