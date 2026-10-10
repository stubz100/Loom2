"""Retouching on pixels the editor sends (D62): Spot Healing. Stateless — the region and the stroke come in, healed pixels go out."""
from __future__ import annotations

import asyncio

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .. import native
from ..heal import spot_heal

router = APIRouter(tags=["retouch"])
MAX_SIDE = 4096


@router.post("/heal", response_class=Response, responses={200: {"content": {"application/octet-stream": {}}, "description": "the healed RGBA region (w·h·4 bytes)"}},
             openapi_extra={"requestBody": {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}, "required": True}})
async def heal(request: Request, w: int, h: int, seed: int = 1):
    """PhotoCraft's Spot Healing over a region: the body is the region's straight RGBA (w·h·4 bytes) followed by the stroke's coverage
    (w·h bytes, > 0 heals); the reply is the region with the stroke healed (same size, alpha unchanged)."""
    if not native.available():
        raise HTTPException(503, "Spot Healing needs the native extension (uv sync --project orchestrator --extra native)")
    if not (0 < w <= MAX_SIDE and 0 < h <= MAX_SIDE):
        raise HTTPException(400, f"the region must be 1–{MAX_SIDE} px on each side")
    body = await request.body()
    n = w * h
    if len(body) != n * 5:
        raise HTTPException(400, f"expected {n * 5} bytes (RGBA {w}×{h} then the coverage), got {len(body)}")
    buf = np.frombuffer(body, dtype=np.uint8)
    rgba = buf[: n * 4].reshape(h, w, 4)
    cov = buf[n * 4:].reshape(h, w)
    out = await asyncio.to_thread(spot_heal, rgba, cov, seed)
    return Response(content=out.tobytes(), media_type="application/octet-stream", headers={"Cache-Control": "no-store"})
