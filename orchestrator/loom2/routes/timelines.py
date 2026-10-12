"""Sequences (P17 / D83): the single-lane timeline documents — list, create, read, replace (409 on a stale revision), delete, and the
EDL / FCPXML exports written from the document for Resolve (14 R151 / R152)."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..clips import ClipStore
from ..origin import JobOrigin
from ..schemas import Deleted, JobsSubmitted, TimelineExported, TimelineList
from ..timelines import StaleTimeline, Timeline, TimelineStore
from .deps import Svc

router = APIRouter(tags=["timelines"])


class TimelineCreate(BaseModel):
    name: str = "Sequence"
    fps: int | None = None                        # default: the project format's (D18: 24)
    w: int | None = None
    h: int | None = None


class TimelineExport(BaseModel):
    format: Literal["edl", "fcpxml"]


@router.get("/timelines", response_model=TimelineList)
async def timelines_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [t.model_dump(by_alias=True) for t in await asyncio.to_thread(TimelineStore(ws).list)]}


@router.post("/timelines", response_model=Timeline, response_model_by_alias=True)
async def timeline_create(svc: Svc, body: TimelineCreate):
    ws, _, _ = svc.require_project()
    fmt = ws.load().format
    tl = await asyncio.to_thread(TimelineStore(ws).create, body.name, body.fps or fmt.fps, body.w or fmt.width, body.h or fmt.height)
    svc.hub.broadcast("timeline.updated", {"id": tl.id, "revision": tl.revision})
    return tl.model_dump(by_alias=True)


@router.get("/timelines/{tl_id}", response_model=Timeline, response_model_by_alias=True)
async def timeline_get(svc: Svc, tl_id: str):
    ws, _, _ = svc.require_project()
    tl = await asyncio.to_thread(TimelineStore(ws).get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    return tl.model_dump(by_alias=True)


@router.put("/timelines/{tl_id}", response_model=Timeline, response_model_by_alias=True)
async def timeline_put(svc: Svc, tl_id: str, body: dict):
    """Replace the document from a body based on its `revision`; every clip must be in the project and its `out` within the clip's frames."""
    ws, _, _ = svc.require_project()
    store, clips = TimelineStore(ws), ClipStore(ws)
    frames = {c.id: c.frames for c in await asyncio.to_thread(clips.list)}
    try:
        tl = await asyncio.to_thread(store.put, tl_id, body, frames)
    except KeyError:
        raise HTTPException(404, "sequence not found")
    except StaleTimeline as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("timeline.updated", {"id": tl.id, "revision": tl.revision})
    return tl.model_dump(by_alias=True)


@router.delete("/timelines/{tl_id}", response_model=Deleted)
async def timeline_delete(svc: Svc, tl_id: str):
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(TimelineStore(ws).delete, tl_id):
        raise HTTPException(404, "sequence not found")
    svc.hub.broadcast("timeline.deleted", {"id": tl_id})
    return {"deleted": tl_id}


@router.post("/timelines/{tl_id}/render", response_model=JobsSubmitted)
async def timeline_render(svc: Svc, tl_id: str):
    """P17: the draft render as a CPU job (no engine) — the result is a Catalogue clip with lineage to every clip on the lane."""
    ws, _, queue = svc.require_project()
    store, clips = TimelineStore(ws), ClipStore(ws)
    tl = await asyncio.to_thread(store.get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    if not tl.clips:
        raise HTTPException(422, "the sequence is empty")
    recs = {c.id for c in await asyncio.to_thread(clips.list)}
    missing = [c.clip_id for c in tl.clips if c.clip_id not in recs]
    if missing:
        raise HTTPException(422, f"clips missing from the project: {', '.join(missing)}")
    try:
        jobs = queue.submit({"kind": "render", "timeline_id": tl_id}, origin=JobOrigin(suite="animate", surface="sequence", ref=tl_id))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"jobs": [j.model_dump() for j in jobs]}


@router.post("/timelines/{tl_id}/export", response_model=TimelineExported)
async def timeline_export(svc: Svc, tl_id: str, body: TimelineExport):
    ws, _, _ = svc.require_project()
    store, clips = TimelineStore(ws), ClipStore(ws)
    tl = await asyncio.to_thread(store.get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    recs = {c.id: c for c in await asyncio.to_thread(clips.list)}
    missing = [c.clip_id for c in tl.clips if c.clip_id not in recs]
    if missing:
        raise HTTPException(422, f"clips missing from the project: {', '.join(missing)}")
    try:
        path, text = await asyncio.to_thread(store.export, tl, body.format, recs)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"format": body.format, "path": path.relative_to(ws.path).as_posix(), "text": text}
