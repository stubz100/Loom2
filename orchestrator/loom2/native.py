"""D62: PhotoCraft's content-aware fill and PatchMatch completion (photocraft-algo @ b37bff98, MIT OR Apache-2.0) through the
optional `native` extra — the committed abi3 wheel built from orchestrator/native/pcalgo. Everything here answers "not available"
cleanly when the wheel is not installed, and /capabilities says so (`content_aware.available`)."""
from __future__ import annotations

import numpy as np

try:
    import loom2_pcalgo as _pc  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — the extra is optional
    _pc = None


def available() -> bool:
    return _pc is not None


def capabilities() -> dict:
    return {"available": available(), "modes": ["quick_remove"] if available() else []}


def _f32(rgb: np.ndarray) -> np.ndarray:
    a = np.asarray(rgb)
    return np.ascontiguousarray(a.astype(np.float32) / 255.0 if a.dtype == np.uint8 else a.astype(np.float32))


def content_aware_fill(rgb: np.ndarray, hole: np.ndarray, seed: int = 1) -> np.ndarray:
    """Content-Aware Fill of `hole` (H×W bool) in `rgb` (H×W×3, uint8 or 0..1 floats) from the rest of the image; uint8 out."""
    if _pc is None:
        raise RuntimeError("content-aware fill needs the native extension (uv sync --project orchestrator --extra native)")
    out = _pc.content_aware_fill(_f32(rgb), np.ascontiguousarray(hole.astype(bool)), seed=int(seed) & 0xFFFFFFFF)
    return (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def complete(rgb: np.ndarray, hole: np.ndarray, seed: int = 1) -> np.ndarray | None:
    """PatchMatch / Wexler completion of `hole` (the Spot Healing core); None when nothing is left to sample from."""
    if _pc is None:
        raise RuntimeError("PatchMatch needs the native extension (uv sync --project orchestrator --extra native)")
    try:
        out = _pc.complete_hole(_f32(rgb), np.ascontiguousarray(hole.astype(bool)), seed=int(seed) & 0xFFFFFFFF)
    except ValueError:
        return None
    return (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
