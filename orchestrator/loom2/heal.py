"""D62 (PC15): Spot Healing as PhotoCraft does it (crates/engine/src/retouch_cmds.rs `spot_heal_surface` @ b37bff98, MIT OR
Apache-2.0): the stroke's area grown by 2 px is synthesised from its surroundings by PatchMatch completion (content-aware fill when
completion has nothing to sample), then gradient-domain blended back over the area grown by 1 px — the synthesised ring around the
stroke differs from the untouched pixels, and that mismatch is what the Poisson membrane corrects. Stateless: region pixels in,
healed pixels out; the editor puts them on a layer of their own (non-destructive)."""
from __future__ import annotations

import numpy as np

from . import native
from .poisson import seamless_clone


def dilate_square(mask: np.ndarray, r: int) -> np.ndarray:
    """Square structuring element of radius r (PhotoCraft's `dilate`)."""
    out = mask.copy()
    if r <= 0:
        return out
    h, w = mask.shape
    tmp = mask.copy()
    for d in range(1, r + 1):
        tmp[:, d:] |= mask[:, :-d]
        tmp[:, :-d] |= mask[:, d:]
    out = tmp.copy()
    for d in range(1, r + 1):
        out[d:, :] |= tmp[:-d, :]
        out[:-d, :] |= tmp[d:, :]
    return out


def spot_heal(rgba: np.ndarray, coverage: np.ndarray, seed: int = 1) -> np.ndarray:
    """`rgba` H×W×4 uint8 (the region around the stroke), `coverage` H×W uint8 (the stroke, > 0 = heal). Returns H×W×4 uint8: the
    healed colour inside the healed area, the input elsewhere; alpha unchanged."""
    hole = coverage > 0
    if not hole.any():
        return rgba.copy()
    rgb = np.ascontiguousarray(rgba[..., :3])
    domain = dilate_square(hole, 2)
    heal_mask = dilate_square(hole, 1)
    filled = native.complete(rgb, domain, seed)
    if filled is None:
        filled = native.content_aware_fill(rgb, domain, seed)
    healed = seamless_clone(filled, rgb, heal_mask, smooth=0.0)
    out = rgba.copy()
    out[..., :3] = np.where(heal_mask[..., None], healed, rgb)
    return out
