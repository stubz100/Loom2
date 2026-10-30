"""D165: a character layer's window (D163) and its head box (D118, the face pass and lip-sync) as keyframed boxes, in the frame's pixels.

- A window's key is `{frame, cx, cy, h}`: its centre and height. Its width follows Wan's portrait (WINDOW), so a window is resized, never
  reshaped.
- A head box's key is `{frame, cx, cy, side}`.
- The automatic track (finals.figure_windows, heads.head_boxes) is offered as keys: simplified, so that a key stands at the first and last
  frame and wherever the straight line between keys strays from the track.
- The frames between keys are interpolated, and the ends are held.
- On the layer, `window_keys` / `head_keys` are None for automatic and [] for removed by hand.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import numpy as np

from .finals import WINDOW, figure_windows, layer_window
from .heads import head_boxes

if TYPE_CHECKING:
    from .finals import FinalLayer

TOL_POS = 0.02            # a key where the line between keys strays from the track by more than this share of the frame's height
TOL_SIZE = 0.05           # … or its size by more than this fraction
MIN_SIZE = 8.0            # px: the smallest window height or head box side a key may ask for
HEAD_POINTS = (0, 14, 15, 16, 17)                                       # COCO-18: the nose, the eyes, the ears


def window_track(kps: list, n: int) -> list[dict[str, float]]:
    """The automatic window, frame by frame, as centre and height (whether or not D163's rule would use it)."""
    ww, wh = WINDOW
    out = []
    for x0, y0, s in figure_windows(kps, n):
        h = wh / s
        out.append({"cx": x0 + ww / s / 2, "cy": y0 + h / 2, "h": h})
    return out


def head_track(kps: list, n: int, w: int, h: int) -> list[dict[str, float]]:
    """The automatic head box, frame by frame, as centre and side."""
    return [{"cx": x0 + s / 2, "cy": y0 + s / 2, "side": float(s)} for x0, y0, s in head_boxes(kps, n, w, h)]


def simplify(track: list[dict[str, float]], size: str, height: float) -> list[dict[str, float]]:
    """The track as keys: the first and the last frame, and — splitting where the straight line between two keys strays most — every frame
    where it strays by more than TOL_POS of the frame's height in position or TOL_SIZE in size (Douglas–Peucker on the frames)."""
    n = len(track)
    if not n:
        return []
    keep = {0, n - 1}
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        worst, at = 0.0, -1
        for i in range(a + 1, b):
            t = (i - a) / (b - a)
            lin = {k: track[a][k] + (track[b][k] - track[a][k]) * t for k in ("cx", "cy", size)}
            off = max(abs(lin["cx"] - track[i]["cx"]) / (TOL_POS * height), abs(lin["cy"] - track[i]["cy"]) / (TOL_POS * height),
                      abs(lin[size] - track[i][size]) / max(1e-6, TOL_SIZE * track[i][size]))
            if off > worst:
                worst, at = off, i
        if worst > 1.0:
            keep.add(at)
            stack += [(a, at), (at, b)]
    return [{"frame": i, "cx": round(track[i]["cx"], 2), "cy": round(track[i]["cy"], 2), size: round(track[i][size], 2)} for i in sorted(keep)]


def clean(keys: list[dict[str, Any]], size: str, n: int) -> list[dict[str, float]]:
    """The author's keys made sound: one per frame (the last given wins), inside the shot's frames, a size of at least MIN_SIZE. ValueError
    when a key is not a key."""
    by: dict[int, dict[str, float]] = {}
    for k in keys:
        try:
            fr, cx, cy, sz = int(k["frame"]), float(k["cx"]), float(k["cy"]), float(k[size])
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"a key needs frame, cx, cy and {size}: {k!r}") from e
        if not all(np.isfinite([cx, cy, sz])):
            raise ValueError(f"a key's numbers must be finite: {k!r}")
        by[min(max(fr, 0), max(0, n - 1))] = {"frame": min(max(fr, 0), max(0, n - 1)), "cx": round(cx, 2), "cy": round(cy, 2), size: round(max(MIN_SIZE, sz), 2)}
    return [by[i] for i in sorted(by)]


def interpolate(keys: list[dict[str, float]], size: str, n: int) -> list[dict[str, float]]:
    """Every frame's box from the keys: straight lines between them, the first and the last held."""
    if not keys:
        return []
    ks = sorted(keys, key=lambda k: k["frame"])
    out = []
    j = 0
    for i in range(n):
        while j + 1 < len(ks) and ks[j + 1]["frame"] <= i:
            j += 1
        a = ks[j]
        b = ks[j + 1] if j + 1 < len(ks) else a
        t = 0.0 if b["frame"] == a["frame"] or i <= a["frame"] else min(1.0, (i - a["frame"]) / (b["frame"] - a["frame"]))
        if i < ks[0]["frame"]:
            a, b, t = ks[0], ks[0], 0.0
        out.append({k: a[k] + (b[k] - a[k]) * t for k in ("cx", "cy", size)})
    return out


def windows_from(keys: list[dict[str, float]], n: int) -> list[list[float]]:
    """Per frame [x0, y0, scale] (finals.figure_windows' form) from window keys."""
    ww, wh = WINDOW
    out = []
    for b in interpolate(keys, "h", n):
        s = wh / b["h"]
        out.append([round(b["cx"] - ww / s / 2, 2), round(b["cy"] - b["h"] / 2, 2), round(s, 5)])
    return out


def heads_from(keys: list[dict[str, float]], n: int, w: int, h: int) -> list[tuple[int, int, int]]:
    """Per frame (x0, y0, side) (heads.head_boxes' form) from head keys — clamped to the picture, as the paste needs."""
    out = []
    for b in interpolate(keys, "side", n):
        side = int(round(min(b["side"], w, h)))
        out.append((int(round(max(0, min(w - side, b["cx"] - side / 2)))), int(round(max(0, min(h - side, b["cy"] - side / 2)))), side))
    return out


def layer_windows(layer: "FinalLayer", kps: list | None, n: int) -> list[list[float]]:
    """The windows the layer is performed in: its keys' when the author set them, none when they removed it, else D163's rule."""
    if layer.window_keys is None:
        return layer_window(kps, n)
    return windows_from(layer.window_keys, n) if layer.window_keys else []


def layer_heads(layer: "FinalLayer", kps: list, n: int, w: int, h: int) -> list[tuple[int, int, int]] | None:
    """The head boxes the face pass crops: its keys' when the author set them, None when they removed it, else the tracked ones."""
    if layer.head_keys is None:
        return head_boxes(kps, n, w, h)
    return heads_from(layer.head_keys, n, w, h) if layer.head_keys else None


def window_cuts(kps: list | None, wins: list[list[float]]) -> list[int]:
    """The frames where the window leaves one of the figure's 18 points out (in the frame or not: Stage projects them all)."""
    ww, wh = WINDOW
    out = []
    for i, (x0, y0, s) in enumerate(wins):
        k = np.asarray((kps or [[]])[min(i, len(kps or [[]]) - 1)] or [], dtype=float).reshape(-1, 3)[:18, :2]
        if len(k) and (((k[:, 0] - x0) * s < 0) | ((k[:, 0] - x0) * s > ww) | ((k[:, 1] - y0) * s < 0) | ((k[:, 1] - y0) * s > wh)).any():
            out.append(i)
    return out


def head_misses(kps: list | None, boxes: list[tuple[int, int, int]] | None) -> list[int]:
    """The frames where the head box leaves the nose, an eye or an ear out."""
    out = []
    for i, (x0, y0, s) in enumerate(boxes or []):
        k = np.asarray((kps or [[]])[min(i, len(kps or [[]]) - 1)] or [], dtype=float).reshape(-1, 3)
        if len(k) < 18:
            continue
        p = k[list(HEAD_POINTS), :2]
        if ((p[:, 0] < x0) | (p[:, 0] > x0 + s) | (p[:, 1] < y0) | (p[:, 1] > y0 + s)).any():
            out.append(i)
    return out


def sig(boxes: Any) -> str:
    """A short signature of a layer's windows or head boxes (rounded to the pixel): what a performance or a face take was made with."""
    rows = [[round(float(v)) if j < 2 else round(float(v), 3) for j, v in enumerate(b)] for b in (boxes or [])]
    return hashlib.sha1(json.dumps(rows).encode()).hexdigest()[:12]
