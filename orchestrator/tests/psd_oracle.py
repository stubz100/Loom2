"""D40: Photoshop as the oracle for compose.py. A PSD's layers (read by psd-tools) become a loom2 stack, compose.py flattens it, and
the result is compared with the merged image Photoshop stored in the file. Files using features loom2 does not model are out of
scope, with the reason recorded, rather than failed.

Method from PhotoCraft's crates/io/tests/corpus.rs @ b37bff98 (pass = premultiplied max difference ≤ 2/255, ratcheting floor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from loom2 import compose

TOLERANCE = 2 / 255


class OutOfScope(Exception):
    """The file uses something loom2 does not model (the message says what)."""


@dataclass
class Result:
    name: str
    status: str                     # "pass" | "fail" | "out of scope" | "error"
    detail: str = ""
    max_diff: float = 0.0
    p99: float = 0.0


@dataclass
class Stack:
    nodes: list[dict] = field(default_factory=list)
    pixels: dict[str, np.ndarray] = field(default_factory=dict)
    masks: dict[str, np.ndarray] = field(default_factory=dict)


def _modes():
    from psd_tools.constants import BlendMode as B

    table = {B.NORMAL: "normal", B.DARKEN: "darken", B.MULTIPLY: "multiply", B.COLOR_BURN: "color-burn", B.LINEAR_BURN: "linear-burn",
             B.LIGHTEN: "lighten", B.SCREEN: "screen", B.COLOR_DODGE: "color-dodge", B.LINEAR_DODGE: "linear-dodge", B.OVERLAY: "overlay",
             B.SOFT_LIGHT: "soft-light", B.HARD_LIGHT: "hard-light", B.VIVID_LIGHT: "vivid-light", B.LINEAR_LIGHT: "linear-light",
             B.PIN_LIGHT: "pin-light", B.HARD_MIX: "hard-mix", B.DIFFERENCE: "difference", B.EXCLUSION: "exclusion", B.SUBTRACT: "subtract",
             B.DIVIDE: "divide", B.HUE: "hue", B.SATURATION: "saturation", B.COLOR: "color", B.LUMINOSITY: "luminosity"}
    return table, B.PASS_THROUGH


def _rgba(im) -> np.ndarray:
    arr = np.asarray(im.convert("RGBA") if im.mode != "RGBA" else im, dtype=np.uint8)
    return np.ascontiguousarray(arr)


def _check_layer(layer) -> None:
    from psd_tools.constants import Tag

    if layer.has_vector_mask():
        raise OutOfScope(f"vector mask on {layer.name!r}")
    if layer.has_effects() and getattr(layer.effects, "enabled", True) and any(getattr(e, "enabled", True) for e in layer.effects):
        raise OutOfScope(f"layer effects on {layer.name!r}")
    tb = layer.tagged_blocks
    if tb.get_data(Tag.KNOCKOUT_SETTING, 0):
        raise OutOfScope(f"knockout on {layer.name!r}")
    if not tb.get_data(Tag.BLEND_CLIPPING_ELEMENTS, 1) or tb.get_data(Tag.BLEND_INTERIOR_ELEMENTS, 0):
        raise OutOfScope(f"advanced blending on {layer.name!r}")
    ranges = layer._record.blending_ranges
    if ranges is not None:
        full = (0, 65535)
        if any(tuple(r) != full for r in ranges.composite_ranges) or any(tuple(r) != full for ch in ranges.channel_ranges for r in ch):
            raise OutOfScope(f"blend-if on {layer.name!r}")


def _mask_params(layer) -> dict:
    """D52: the user mask's density (0–255 → 0–1) and feather (px, taken as the Gaussian σ — every corpus file that sets it also has a
    vector mask, so Photoshop's exact feather kernel is not measured here)."""
    pr = layer.mask.parameters
    if pr is None:
        return {}
    out: dict = {}
    if pr.user_mask_density is not None:
        out["density"] = pr.user_mask_density / 255
    if pr.user_mask_feather:
        out["feather"] = float(pr.user_mask_feather)
    return out


def _mask(layer, w: int, h: int) -> np.ndarray | None:
    m = layer.mask
    if m is None:
        return None
    out = np.full((h, w), int(m.background_color), dtype=np.uint8)
    im = m.topil()
    if im is not None:
        arr = np.asarray(im.convert("L"), dtype=np.uint8)
        x0, y0 = m.left, m.top
        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        cw = min(w - dx0, arr.shape[1] - sx0)
        ch = min(h - dy0, arr.shape[0] - sy0)
        if cw > 0 and ch > 0:
            out[dy0:dy0 + ch, dx0:dx0 + cw] = arr[sy0:sy0 + ch, sx0:sx0 + cw]
    return out


def _adjustment(layer) -> tuple[str, dict]:
    kind = layer.kind
    if kind == "levels":
        recs = layer.data
        ident = (0, 255, 0, 255, 100)
        if any((r.input_floor, r.input_ceiling, r.output_floor, r.output_ceiling, r.gamma) != ident for r in recs[1:4]):
            raise OutOfScope(f"per-channel levels on {layer.name!r}")
        r = recs[0]
        return "levels", {"in_black": r.input_floor, "in_white": r.input_ceiling, "out_black": r.output_floor, "out_white": r.output_ceiling, "gamma": r.gamma / 100}
    if kind == "curves":
        params: dict = {}
        for item in layer.extra or []:
            key = {0: "rgb", 1: "r", 2: "g", 3: "b"}.get(item.channel_id)
            if key is None:
                raise OutOfScope(f"curves channel {item.channel_id} on {layer.name!r}")
            params[key] = [[int(i), int(o)] for o, i in item.points]      # PSD stores (output, input)
        if not params:
            raise OutOfScope(f"legacy curves on {layer.name!r}")
        return "curves", params
    if kind == "exposure":
        return "exposure", {"exposure": float(layer.exposure), "offset": float(layer.exposure_offset), "gamma": float(layer.gamma)}
    if kind == "invert":
        return "invert", {}
    if kind in ("huesaturation", "brightnesscontrast", "colorbalance", "blackandwhite"):
        raise OutOfScope(f"{kind} (loom2's maths differ from Photoshop's by design, D41)")
    raise OutOfScope(f"{kind} layer {layer.name!r}")


def to_stack(psd) -> Stack:
    from psd_tools.constants import ColorMode, Tag

    if psd.color_mode != ColorMode.RGB or psd.depth != 8:
        raise OutOfScope(f"colour mode {psd.color_mode.name} / {psd.depth}-bit")
    w, h = psd.width, psd.height
    modes, pass_through = _modes()
    st = Stack()
    counter = [0]

    def conv(layers) -> list[dict]:
        out = []
        for layer in reversed(list(layers)):                     # psd-tools lists bottom-first; loom2 stacks are top-first
            _check_layer(layer)
            counter[0] += 1
            lid = f"l{counter[0]}"
            if layer.blend_mode == pass_through:
                mode = "pass-through"
            elif layer.blend_mode in modes:
                mode = modes[layer.blend_mode]
            else:
                raise OutOfScope(f"blend mode {layer.blend_mode.name} on {layer.name!r}")
            node: dict = {"id": lid, "name": layer.name, "visible": bool(layer.visible), "opacity": layer.opacity / 255, "clip": bool(layer._record.clipping),   # psd-tools' `clipping` property reads False on groups
                          "blend": "normal" if mode == "pass-through" else mode, "mask": None}
            m = _mask(layer, w, h)
            if m is not None:
                st.masks[lid] = m
                node["mask"] = {"enabled": not layer.mask.disabled, "linked": False, "x": 0, "y": 0, **_mask_params(layer)}
            kind = layer.kind
            if kind == "group":
                if layer.fill_opacity != 255:
                    raise OutOfScope(f"group fill opacity on {layer.name!r}")
                node.update(kind="group", passthrough=mode == "pass-through", children=conv(layer))
                if mode == "pass-through":
                    node["blend"] = "normal"
            elif kind == "pixel" and Tag.BRIGHTNESS_AND_CONTRAST in layer.tagged_blocks:
                raise OutOfScope(f"legacy brightness/contrast on {layer.name!r} (loom2's maths differ by design, D41)")
            elif kind in ("pixel", "type", "smartobject", "shape"):
                im = layer.topil()
                px = _rgba(im) if im is not None else np.zeros((1, 1, 4), dtype=np.uint8)
                st.pixels[lid] = px
                node.update(kind="raster", x=int(layer.left) if im is not None else 0, y=int(layer.top) if im is not None else 0,
                            w=px.shape[1], h=px.shape[0], fill=layer.fill_opacity / 255)
            else:
                if layer.fill_opacity != 255:
                    raise OutOfScope(f"adjustment fill opacity on {layer.name!r}")
                typ, params = _adjustment(layer)
                node.update(kind="adjustment", type=typ, params=params)
            out.append(node)
        return out

    st.nodes = conv(psd)
    return st


def merged(psd) -> np.ndarray:
    """Photoshop's own composite, stored in the file (float RGBA)."""
    im = psd.topil()
    if im is None:
        raise OutOfScope("no merged image")
    return _rgba(im).astype(np.float32) / 255.0


def diff(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Premultiplied per-channel difference: (max, p99)."""
    pa = np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], axis=-1)
    pb = np.concatenate([b[..., :3] * b[..., 3:4], b[..., 3:4]], axis=-1)
    d = np.abs(pa - pb)
    return float(d.max()), float(np.percentile(d, 99))


def run_file(path: Path, name: str) -> Result:
    from psd_tools import PSDImage

    try:
        psd = PSDImage.open(path)
        st = to_stack(psd)
        want = merged(psd)
        got = compose.Renderer(psd.width, psd.height, st.pixels, st.masks, background="transparent").flatten(st.nodes)
        got = np.round(got * 255) / 255                           # compare at the 8 bits both images are stored with
        mx, p99 = diff(got, want)
        return Result(name, "pass" if mx <= TOLERANCE + 1e-6 else "fail", "", mx * 255, p99 * 255)
    except OutOfScope as e:
        return Result(name, "out of scope", str(e))
    except Exception as e:                                        # a crash is a finding, not a skip
        return Result(name, "error", f"{type(e).__name__}: {e}")
