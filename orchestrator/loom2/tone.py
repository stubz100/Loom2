"""Colour statistics transfer (D48 "match colour to surroundings"): Reinhard-style Lab mean / standard-deviation matching, measured on
chosen pixels of two images and applied to a whole one. Ported from PhotoCraft crates/algo/src/tone.rs (`lab_stats`, `match_color`)
@ b37bff98; Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors, MIT OR Apache-2.0.

For the AI paste-back the statistics come from the *context ring* — pixels around the mask that the engine re-rendered but that should
look like the plate — so the transform corrects the model's colour / exposure drift without pulling an intended change inside the mask
back towards the plate.
"""
from __future__ import annotations

import numpy as np

Arr = np.ndarray
_M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
_WHITE = np.array([0.95047, 1.0, 1.08883])
SCALE_LIMITS = (0.5, 2.0)          # a ring with almost no variance must not blow the result up


def srgb_to_lab(rgb: Arr) -> Arr:
    """H×W×3 uint8 or float 0–1 sRGB → CIELAB (D65), float64."""
    c = rgb.astype(np.float64) / (255.0 if rgb.dtype == np.uint8 else 1.0)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M.T / _WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_srgb(lab: Arr) -> Arr:
    """CIELAB → sRGB uint8."""
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    xyz = np.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29)) * _WHITE
    lin = np.clip(xyz @ np.linalg.inv(_M).T, 0, 1)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(np.rint(c * 255), 0, 255).astype(np.uint8)


def lab_stats(lab: Arr, where: Arr) -> tuple[Arr, Arr]:
    px = lab[where]
    return px.mean(axis=0), px.std(axis=0)


def match_colour(image: Arr, measured_on: Arr, reference: Arr, where: Arr, strength: float = 1.0) -> Arr:
    """Map the Lab statistics of `measured_on[where]` onto those of `reference[where]` and apply the transform to `image` (uint8 RGB).
    `strength` blends between the original (0) and the matched result (1). Returns `image` unchanged when `where` is (nearly) empty."""
    if int(where.sum()) < 64:
        return image
    mu_a, sd_a = lab_stats(srgb_to_lab(measured_on), where)
    mu_b, sd_b = lab_stats(srgb_to_lab(reference), where)
    scale = np.clip(sd_b / np.maximum(sd_a, 1e-6), *SCALE_LIMITS)
    lab = srgb_to_lab(image)
    out = lab_to_srgb((lab - mu_a) * scale + mu_b)
    if strength >= 1:
        return out
    return np.clip(np.rint(image.astype(np.float64) * (1 - strength) + out * strength), 0, 255).astype(np.uint8)
