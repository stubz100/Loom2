"""Projects: create, open, close, info, recents, Generate presets (06 §4)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..fsio import atomic_write_json, read_json_or
from ..schemas import ProjectInfo, Recents
from ..workspace import Workspace
from .deps import Svc

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    path: str
    name: str
    format: dict | None = None
    size_cap_gb: float = 100.0


class ProjectOpen(BaseModel):
    path: str


@router.post("/project", response_model=ProjectInfo, response_model_exclude_unset=True)
async def project_create(svc: Svc, body: ProjectCreate):
    await asyncio.to_thread(Workspace.create, Path(body.path), name=body.name, fmt=body.format, size_cap_gb=body.size_cap_gb,
                            variant=svc.app.settings.variant)
    return await svc.open_project(Path(body.path))


@router.post("/project/open", response_model=ProjectInfo, response_model_exclude_unset=True)
async def project_open(svc: Svc, body: ProjectOpen):
    return await svc.open_project(Path(body.path))


@router.post("/project/close", response_model=ProjectInfo, response_model_exclude_unset=True)
async def project_close(svc: Svc):
    await svc.close_project()
    return {"open": False}


@router.get("/project", response_model=ProjectInfo, response_model_exclude_unset=True)
async def project_get(svc: Svc):
    if not svc.ws:
        return {"open": False}
    info = svc.ws.info()
    cat = svc.catalogue
    if cat is None:
        return info | {"assets": 0, "usage_gb": 0.0, "jobs_indexed": 0}
    count, usage, jobs = await asyncio.to_thread(lambda: (cat.count(), cat.usage_bytes(), cat.jobs_indexed()))
    return info | {"assets": count, "usage_gb": round(usage / 2**30, 2), "jobs_indexed": jobs}


@router.get("/project/presets", response_model=dict[str, Any])
async def presets_get(svc: Svc):
    ws, _, _ = svc.require_project()
    return await asyncio.to_thread(read_json_or, ws.path / "generate" / "presets.json", {"presets": [], "last": None})


@router.put("/project/presets", response_model=dict[str, Any])
async def presets_put(svc: Svc, body: dict):
    ws, _, _ = svc.require_project()
    await asyncio.to_thread(atomic_write_json, ws.path / "generate" / "presets.json", body)
    return body


@router.get("/projects", response_model=Recents)
async def projects(svc: Svc):
    return {"last": svc.app.record.last_project, "recents": svc.app.record.recents}
