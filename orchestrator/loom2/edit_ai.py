"""Edit AI pipeline helpers (10 §4, D7): region planning around a selection, crop/scale of the composite and
mask for the engine, outpaint padding, and paste-back as a new layer with a feathered alpha. Pure numpy/PIL so
the queue stays thin and the maths is unit-tested without an engine.

Region contract (10 §4 "region"): the mask's bounding box grows by `margin_pct` of its longer side (≥ 32 px) for
context, is rounded to multiples of 16 and clamped to the document; the crop is sent at ≥ `min_size` on its
longer side (auto-upscale of small regions, ≤ `max_size`), and the result is resized back to the crop size.
The new layer holds the result inside the crop with alpha = feathered mask, so compositing *is* the paste-back.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image, ImageFilter

from . import maskops, poisson, tone


def round16_up(n: float) -> int:
    return max(16, int(np.ceil(n / 16.0)) * 16)


@dataclass
class RegionPlan:
    x: int
    y: int
    w: int
    h: int
    scale: float = 1.0          # engine image = crop × scale (then rounded to multiples of 16)
    ew: int = 0                 # engine image size
    eh: int = 0
    pad: dict | None = None     # outpaint padding {left, top, right, bottom}

    def to_dict(self) -> dict:
        return asdict(self)


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask > 0)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def dilate(mask: np.ndarray, px: int) -> np.ndarray:
    """D44: round growth through the bounded distance transform (maskops) — PIL's MaxFilter grew squares and took 17 s for
    64 px on a 1080p mask (67 s at 4K); this takes 0.1 s (0.5 s)."""
    if px <= 0:
        return mask
    return maskops.expand(mask, px)


def feather(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    return np.asarray(Image.fromarray(mask, "L").filter(ImageFilter.GaussianBlur(radius=float(px))))


MAX_PIXELS_DEFAULT = 1_048_576   # ≈ 1 MP engine images: E8 measured 0.5 MP; the 2026-10-05 TDR came with VRAM pressure


def _engine_size(w: int, h: int, min_size: int, max_size: int, max_pixels: int = 0) -> tuple[float, int, int]:
    longer = max(w, h)
    scale = 1.0
    if min_size and longer < min_size:
        scale = min_size / longer
    if max_size and longer * scale > max_size:
        scale = max_size / longer
    if max_pixels and w * h * scale * scale > max_pixels:
        scale = (max_pixels / float(w * h)) ** 0.5
    ew, eh = round16_up(w * scale), round16_up(h * scale)
    while max_pixels and ew * eh > max_pixels and scale > 0.05:      # the 16-rounding may overshoot the cap
        scale *= 0.99
        ew, eh = round16_up(w * scale), round16_up(h * scale)
    return scale, ew, eh


def plan_region(mask: np.ndarray, doc_w: int, doc_h: int, margin_pct: int = 25, min_size: int = 1024, max_size: int = 2048,
                max_pixels: int = MAX_PIXELS_DEFAULT) -> RegionPlan | None:
    bb = mask_bbox(mask)
    if bb is None:
        return None
    x0, y0, x1, y1 = bb
    m = max(32, int(round(max(x1 - x0, y1 - y0) * margin_pct / 100.0)))
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
    w, h = round16_up(x1 - x0), round16_up(y1 - y0)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, h = min(w, doc_w), min(h, doc_h)
    x = int(round(cx - w / 2.0)); y = int(round(cy - h / 2.0))
    x = max(0, min(x, doc_w - w)); y = max(0, min(y, doc_h - h))
    scale, ew, eh = _engine_size(w, h, min_size, max_size, max_pixels)
    return RegionPlan(x, y, w, h, scale, ew, eh)


def whole_plan(doc_w: int, doc_h: int, max_size: int = 2048) -> RegionPlan:
    scale, ew, eh = _engine_size(doc_w, doc_h, 0, max_size)
    return RegionPlan(0, 0, doc_w, doc_h, scale, ew, eh)


def layer_plan(x: int, y: int, w: int, h: int, max_size: int = 2048) -> RegionPlan:
    scale, ew, eh = _engine_size(w, h, 0, max_size)
    return RegionPlan(x, y, w, h, scale, ew, eh)


def _resize_rgb(rgb: np.ndarray, w: int, h: int) -> np.ndarray:
    if rgb.shape[1] == w and rgb.shape[0] == h:
        return rgb
    return np.asarray(Image.fromarray(rgb).resize((w, h), Image.Resampling.LANCZOS))


def _resize_mask(m: np.ndarray, w: int, h: int) -> np.ndarray:
    if m.shape[1] == w and m.shape[0] == h:
        return m
    return np.asarray(Image.fromarray(m, "L").resize((w, h), Image.Resampling.BILINEAR))


def crop_inputs(composite_rgba: np.ndarray, mask: np.ndarray | None, plan: RegionPlan) -> tuple[np.ndarray, np.ndarray | None]:
    """The engine image (RGB, ew×eh) and mask (L, ew×eh) for a plan."""
    x, y, w, h = plan.x, plan.y, plan.w, plan.h
    rgb = np.ascontiguousarray(composite_rgba[y:y + h, x:x + w, :3])
    rgb = _resize_rgb(rgb, plan.ew, plan.eh)
    m = None
    if mask is not None:
        m = _resize_mask(np.ascontiguousarray(mask[y:y + h, x:x + w]), plan.ew, plan.eh)
    return rgb, m


def outpaint_plan(doc_w: int, doc_h: int, pad: dict, max_size: int = 2048, max_pixels: int = MAX_PIXELS_DEFAULT) -> RegionPlan:
    l, t, r, b = (int(pad.get(k, 0)) for k in ("left", "top", "right", "bottom"))
    nw, nh = doc_w + l + r, doc_h + t + b
    scale, ew, eh = _engine_size(nw, nh, 0, max_size, max_pixels)
    return RegionPlan(-l, -t, nw, nh, scale, ew, eh, {"left": l, "top": t, "right": r, "bottom": b})


def outpaint_inputs(composite_rgba: np.ndarray, plan: RegionPlan, band: int = 24) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Edge-padded RGB, the engine mask (strips + an inner band so the model blends the seam) and the full-size
    mask used for the layer's alpha (strips only, feathered later)."""
    p = plan.pad or {}
    l, t, r, b = p.get("left", 0), p.get("top", 0), p.get("right", 0), p.get("bottom", 0)
    rgb = np.pad(composite_rgba[..., :3], ((t, b), (l, r), (0, 0)), mode="edge")
    strips = np.zeros((plan.h, plan.w), dtype=np.uint8)
    if t: strips[:t, :] = 255
    if b: strips[plan.h - b:, :] = 255
    if l: strips[:, :l] = 255
    if r: strips[:, plan.w - r:] = 255
    engine_mask = dilate(strips, band) if band else strips
    return _resize_rgb(rgb, plan.ew, plan.eh), _resize_mask(engine_mask, plan.ew, plan.eh), strips


def plan_tiles(w: int, h: int, tile: int = 1024, overlap: int = 128) -> list[tuple[int, int, int, int]]:
    """Overlapping tiles (x, y, tw, th) covering w×h for the tiled refine (10 §4). Tile sides are multiples of 16 and
    clamped to the image; the last column / row is pulled back to the edge so every tile has the full size and the
    whole image is covered."""
    tw = max(16, min(tile, w) // 16 * 16)
    th = max(16, min(tile, h) // 16 * 16)
    ov = max(0, min(overlap, tw - 16, th - 16))

    def starts(n: int, t: int) -> list[int]:
        if t >= n:
            return [0]
        step = max(16, t - ov)
        xs = list(range(0, n - t, step))
        xs.append(n - t)
        return xs
    return [(x, y, tw, th) for y in starts(h, th) for x in starts(w, tw)]


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    return maskops.contract(mask, px)


def mask_from_engine(gray: np.ndarray, doc_w: int, doc_h: int, expand: int = 0, feather_px: int = 0) -> np.ndarray:
    """An engine mask (any size, uint8 grey) back at document size with the Segment recipe's expand / feather."""
    m = _resize_mask(np.ascontiguousarray(gray), doc_w, doc_h)
    if expand > 0:
        m = dilate(m, expand)
    elif expand < 0:
        m = erode(m, -expand)
    return feather(m, feather_px) if feather_px else m


def combine_selection(current: np.ndarray | None, mask: np.ndarray, op: str) -> np.ndarray:
    """replace · add · subtract · intersect of a new mask with the document's selection (both uint8 grey)."""
    if current is None or op == "replace":
        return mask
    if op == "add":
        return np.maximum(current, mask)
    if op == "subtract":
        return np.clip(current.astype(np.int16) - mask.astype(np.int16), 0, 255).astype(np.uint8)
    if op == "intersect":
        return np.minimum(current, mask)
    raise ValueError(f"unknown selection op {op!r}")


def harmonise(rgb: np.ndarray, context: np.ndarray, mask: np.ndarray, feather_px: int, blend: str = "feather", match_colour: bool = False) -> np.ndarray:
    """Make an engine result sit in the plate (crop-sized uint8 RGB in, out). `context` is the original composite over the same crop,
    `mask` the selection there (before feathering).

    D48 match colour: the Lab statistics of the result on the *context ring* (outside the mask grown past the feather) are mapped onto
    the plate's on the same ring and applied to the whole result — the model's drift goes, an intended change inside the mask stays.
    D47 seamless: the result is Poisson-cloned onto the plate through the mask contracted by the feather, so where the layer is (almost)
    opaque it keeps the AI texture but meets the plate's colour and light; the feathered mask then fades it in as before."""
    if match_colour:
        ring = maskops.expand(mask, feather_px + 4) < 128
        rgb = tone.match_colour(rgb, rgb, context, ring)
    if blend == "seamless":
        core = maskops.contract(mask, max(1, feather_px)) >= 128
        core[0, :] = core[-1, :] = False                  # a 1-px plate margin: a fully Dirichlet problem
        core[:, 0] = core[:, -1] = False
        if core.any():
            rgb = poisson.seamless_clone(rgb, context, core)
    return rgb


def assemble_layer(result: np.ndarray, plan: RegionPlan, alpha_mask: np.ndarray | None, feather_px: int, context: np.ndarray | None = None,
                   blend: str = "feather", match_colour: bool = False, match_on: str = "ring") -> np.ndarray:
    """The new layer's RGBA (h×w) from the engine result: resized back to the crop, alpha = feathered mask
    (document-sized `alpha_mask` cropped to the plan, or opaque when None). With `context` (the plate over the crop), D47 / D48 run
    first: `match_on="ring"` measures the colour drift around a selection (`harmonise`), `"all"` over the whole image or layer (a refine
    of the visible composite or of a layer, whose decode changes every pixel)."""
    rgb = _resize_rgb(np.ascontiguousarray(result[..., :3]), plan.w, plan.h)
    if alpha_mask is None:
        a = np.full((plan.h, plan.w), 255, dtype=np.uint8)
    elif alpha_mask.shape[0] == plan.h and alpha_mask.shape[1] == plan.w:
        a = alpha_mask
    else:
        a = np.ascontiguousarray(alpha_mask[plan.y:plan.y + plan.h, plan.x:plan.x + plan.w])
    if context is not None and match_colour and match_on == "all":
        rgb = tone.match_colour(rgb, rgb, context, a > 0)
    elif context is not None and alpha_mask is not None and (blend != "feather" or match_colour):
        rgb = harmonise(rgb, context, a, feather_px, blend, match_colour)
    if alpha_mask is not None:
        a = feather(a, feather_px)
    return np.dstack([rgb, a]).astype(np.uint8)
