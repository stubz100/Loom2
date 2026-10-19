"""CA1 (proto01_animate 02 §5): the motion library's files — `GET /motion/files` lists the starter set and the local motion folder,
`GET /motion/files/{id}` serves one (the client parses it with three.js and retargets its clips)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..motion import MotionFile, resolve, scan, starter_dir
from .deps import Svc

router = APIRouter(tags=["motion"])

MEDIA = {".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".fbx": "application/octet-stream"}


class MotionFiles(BaseModel):
    items: list[MotionFile]
    starter_dir: str | None                        # where the starter set was looked for (None: not found)
    local_dir: str | None                          # Settings › Motion › local folder (None: not set or not found)


def _dirs(svc) -> tuple[Path | None, Path | None]:
    m = svc.app.settings.motion
    s = starter_dir(svc.app.settings.models_root, m.starter_dir)
    loc = Path(m.local_dir) if m.local_dir else None
    return (s if s.is_dir() else None), (loc if loc and loc.is_dir() else None)


@router.get("/motion/files", response_model=MotionFiles)
async def motion_files(svc: Svc):
    starter, local = _dirs(svc)
    items = await asyncio.to_thread(scan, starter, local)
    return {"items": [i.model_dump() for i in items], "starter_dir": str(starter) if starter else None, "local_dir": str(local) if local else None}


@router.get("/motion/files/{file_id}")
async def motion_file(svc: Svc, file_id: str):
    starter, local = _dirs(svc)
    p = await asyncio.to_thread(resolve, file_id, starter, local)
    if p is None or not p.is_file():
        raise HTTPException(404, "motion file not found")
    return FileResponse(p, media_type=MEDIA.get(p.suffix.lower(), "application/octet-stream"), headers={"Cache-Control": "private, max-age=3600"})
