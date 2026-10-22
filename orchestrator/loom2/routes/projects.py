"""Projects: create, open, close, info, recents, Generate's saved panels (06 §4; D92: a record with a picture each)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..library import AnimatePanels, SavedPanels, put_animate_panels, put_panels, read_animate_panels, read_panels, StageTemplates, put_stage_templates, read_stage_templates
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


@router.get("/project/presets", response_model=SavedPanels)
async def presets_get(svc: Svc):
    ws, _, _ = svc.require_project()
    return (await asyncio.to_thread(read_panels, ws.path)).model_dump()


@router.put("/project/presets", response_model=SavedPanels)
async def presets_put(svc: Svc, body: dict):
    """D92: the saved panels as a record — a panel sent without its picture keeps the one the server holds (the finisher sets it)."""
    ws, _, _ = svc.require_project()
    try:
        out = await asyncio.to_thread(put_panels, ws.path, body)
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("story.changed", {"kind": "panels", "revision": 0})
    return out.model_dump()


@router.get("/project/animate-presets", response_model=AnimatePanels)
async def animate_presets_get(svc: Svc):
    """D95 (AN1, UX0 #11): Animate's saved panels, a project record (they lived in the browser before)."""
    ws, _, _ = svc.require_project()
    return (await asyncio.to_thread(read_animate_panels, ws.path)).model_dump()


@router.put("/project/animate-presets", response_model=AnimatePanels)
async def animate_presets_put(svc: Svc, body: dict):
    ws, _, _ = svc.require_project()
    try:
        out = await asyncio.to_thread(put_animate_panels, ws.path, body)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return out.model_dump()


@router.get("/project/stage-templates", response_model=StageTemplates)
async def stage_templates_get(svc: Svc):
    """D119 (SC2): the project's stage templates — arrangements of the Clay level saved under a name from the Library's preset panel."""
    ws, _, _ = svc.require_project()
    return (await asyncio.to_thread(read_stage_templates, ws.path)).model_dump()


@router.put("/project/stage-templates", response_model=StageTemplates)
async def stage_templates_put(svc: Svc, body: dict):
    ws, _, _ = svc.require_project()
    try:
        out = await asyncio.to_thread(put_stage_templates, ws.path, body)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return out.model_dump()


@router.get("/projects", response_model=Recents)
async def projects(svc: Svc):
    return {"last": svc.app.record.last_project, "recents": svc.app.record.recents}
