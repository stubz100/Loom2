"""Content-addressed uploads (06 §2): `PUT /blobs/{sha256}` streams the body to disk and checks its hash; never buffered whole."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..fsio import _tmp_for
from ..services import Services
from .deps import Svc

router = APIRouter(tags=["blobs"])


@router.put("/blobs/{sha}")
async def blob_put(svc: Svc, sha: str, request: Request):
    dest = _blob_path(svc, sha)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(dest)                            # B11: unique per writer — two uploads of one blob never share a temp file
    h = hashlib.sha256()
    size = 0
    try:
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)
        if h.hexdigest() != sha:
            raise HTTPException(400, "body sha256 does not match the blob id")
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return {"sha256": sha, "bytes": size}


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
