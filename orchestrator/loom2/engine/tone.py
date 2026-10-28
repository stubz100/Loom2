"""D156 (E41): a clip's tone matched to its start image. Wan 2.2 Fun-Camera starts its clip about fifteen levels brighter than the start image
— a global per-channel offset with a small gain, no spatial shift, the subject kept (E41: MAE 17.4 against the plain model's 9.3). One affine
per channel, fitted by least squares on the first frame against the start image (scaled and centre-cropped as the graph scaled it), applied to
every frame, brings the first frame back to the plain model's distance (9.5). Pure numpy + PIL; the frames are rewritten in place."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def scaled_like_graph(start: Image.Image, w: int, h: int) -> Image.Image:
    """The start image as `ImageScale … crop=center` gave it to the model: scaled to cover w×h, the middle kept."""
    s = max(w / start.width, h / start.height)
    big = start.resize((max(w, round(start.width * s)), max(h, round(start.height * s))), Image.Resampling.LANCZOS)
    x, y = (big.width - w) // 2, (big.height - h) // 2
    return big.crop((x, y, x + w, y + h))


def fit_affine(frame: np.ndarray, target: np.ndarray) -> tuple[list[float], list[float]]:
    """Per channel, the gain and offset (least squares) that take `frame` closest to `target`; both H×W×3 in 0–255."""
    gains, offsets = [], []
    for c in range(3):
        x = frame[..., c].astype(np.float64).ravel()
        y = target[..., c].astype(np.float64).ravel()
        A = np.stack([x, np.ones_like(x)], axis=1)
        g, o = np.linalg.lstsq(A, y, rcond=None)[0]
        gains.append(round(float(g), 4)); offsets.append(round(float(o), 2))
    return gains, offsets


def apply_affine(frame: np.ndarray, gains: list[float], offsets: list[float]) -> np.ndarray:
    out = frame.astype(np.float64) * np.array(gains) + np.array(offsets)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def mae(a: np.ndarray, b: np.ndarray) -> float:
    return round(float(np.abs(a.astype(np.float64) - b.astype(np.float64)).mean()), 2)


def match_frames_to(paths: list[Path], start_path: Path) -> dict:
    """Fit on the first frame, apply to every frame (rewritten in place as PNG); what was done, for the clip's record."""
    if not paths:
        return {"frames": 0}
    first = Image.open(paths[0]).convert("RGB")
    start = np.asarray(scaled_like_graph(Image.open(start_path).convert("RGB"), first.width, first.height))
    f0 = np.asarray(first)
    gains, offsets = fit_affine(f0, start)
    before = mae(f0, start)
    after = mae(apply_affine(f0, gains, offsets), start)
    if after >= before:                                                 # a fit that helps nothing is not applied
        return {"frames": len(paths), "applied": False, "gains": gains, "offsets": offsets, "mae_before": before, "mae_after": before}
    for p in paths:
        im = Image.open(p)
        rgb = np.asarray(im.convert("RGB"))
        fixed = Image.fromarray(apply_affine(rgb, gains, offsets), "RGB")
        if im.mode == "RGBA":
            fixed.putalpha(im.getchannel("A"))
        fixed.save(p, "PNG")
    return {"frames": len(paths), "applied": True, "gains": gains, "offsets": offsets, "mae_before": before, "mae_after": after}
