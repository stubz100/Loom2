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
MAX_AREA = 2048 * 2048          # R6: ≤ 4 MP per call (20 MiB of body) — a stroke's bounding box, not a whole canvas
HEAL_TIMEOUT_S = 60.0           # R6: the PatchMatch thread keeps running after this, but the request answers


@router.post("/heal", response_class=Response, responses={200: {"content": {"application/octet-stream": {}}, "description": "the healed RGBA region (w·h·4 bytes)"}},
             openapi_extra={"requestBody": {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}, "required": True}})
async def heal(request: Request, w: int, h: int, seed: int = 1):
    """PhotoCraft's Spot Healing over a region: the body is the region's straight RGBA (w·h·4 bytes) followed by the stroke's coverage
    (w·h bytes, > 0 heals); the reply is the region with the stroke healed (same size, alpha unchanged)."""
    # R6: at most MAX_SIDE px a side and MAX_AREA px in all; the size is checked before the body is read; bounded by HEAL_TIMEOUT_S
    if not native.available():
        raise HTTPException(503, "Spot Healing needs the native extension (uv sync --project orchestrator --extra native)")
    if not (0 < w <= MAX_SIDE and 0 < h <= MAX_SIDE):
        raise HTTPException(400, f"the region must be 1–{MAX_SIDE} px on each side")
    n = w * h
    if n > MAX_AREA:
        raise HTTPException(400, f"the region is {w}×{h} px; Spot Healing takes at most {MAX_AREA} px (2048×2048) per call")
    want = n * 5
    declared = request.headers.get("content-length")
    if declared is not None:                       # R6: refuse a wrong size before reading a byte of it
        try:
            size = int(declared)
        except ValueError:
            raise HTTPException(400, "Content-Length is not a number")
        if size > want:
            raise HTTPException(413, f"expected {want} bytes (RGBA {w}×{h} then the coverage), the request declares {size}")
        if size != want:
            raise HTTPException(400, f"expected {want} bytes (RGBA {w}×{h} then the coverage), got {size}")
    body = bytearray()
    async for chunk in request.stream():           # a chunked body without a length is read only up to the size it must have
        body += chunk
        if len(body) > want:
            raise HTTPException(413, f"expected {want} bytes (RGBA {w}×{h} then the coverage), got more")
    if len(body) != want:
        raise HTTPException(400, f"expected {want} bytes (RGBA {w}×{h} then the coverage), got {len(body)}")
    buf = np.frombuffer(bytes(body), dtype=np.uint8)
    rgba = buf[: n * 4].reshape(h, w, 4)
    cov = buf[n * 4:].reshape(h, w)
    try:
        out = await asyncio.wait_for(asyncio.to_thread(spot_heal, rgba, cov, seed), HEAL_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise HTTPException(504, f"Spot Healing took longer than {HEAL_TIMEOUT_S:g} s — heal a smaller stroke")
    return Response(content=out.tobytes(), media_type="application/octet-stream", headers={"Cache-Control": "no-store"})
