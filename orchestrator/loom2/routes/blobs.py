"""Content-addressed uploads (06 §2): `PUT /blobs/{sha256}` streams the body to disk and checks its hash; never buffered whole."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..fsio import _tmp_for, replace
from ..schemas import BlobPut
from ..services import Services
from .deps import Svc

router = APIRouter(tags=["blobs"])
FLUSH_BYTES = 4 * 2**20                            # R8: the body is written in ≤ 4 MiB slices, each in a worker thread


@router.put("/blobs/{sha}", response_model=BlobPut)
async def blob_put(svc: Svc, sha: str, request: Request):
    dest = _blob_path(svc, sha)
    tmp = _tmp_for(dest)                            # B11: unique per writer — two uploads of one blob never share a temp file
    h = hashlib.sha256()
    size = 0
    pending = bytearray()

    def flush(f, data: bytes) -> None:            # R8: file writes (and fsio.replace's retry sleeps) stay off the event loop
        f.write(data)
        h.update(data)

    f = await asyncio.to_thread(_open_tmp, tmp)
    try:
        try:
            async for chunk in request.stream():
                pending += chunk
                size += len(chunk)
                if len(pending) >= FLUSH_BYTES:
                    await asyncio.to_thread(flush, f, bytes(pending))
                    pending.clear()
            if pending:
                await asyncio.to_thread(flush, f, bytes(pending))
        finally:
            await asyncio.to_thread(f.close)
        if h.hexdigest() != sha:
            raise HTTPException(400, "body sha256 does not match the blob id")
        await asyncio.to_thread(replace, tmp, dest)
    finally:
        await asyncio.to_thread(tmp.unlink, True)
    return {"sha256": sha, "bytes": size}


def _open_tmp(tmp: Path):
    tmp.parent.mkdir(parents=True, exist_ok=True)
    return tmp.open("wb")


@router.get("/blobs/{sha}")
async def blob_get(svc: Svc, sha: str):
    p = _blob_path(svc, sha)
    if not p.is_file():
        raise HTTPException(404, "blob not found")
    return FileResponse(p, media_type="application/octet-stream")


def _blob_path(svc: Services, sha: str) -> Path:
    ws, _, _ = svc.require_project()
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise HTTPException(400, "blob id must be a lowercase sha256")
    return ws.temp_dir / "blobs" / sha
