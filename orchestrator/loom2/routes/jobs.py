"""Jobs and the queue (06 §6, 07 §5): submit (or stage), release, cancel, delete, pause. `JobQueue` is not thread-safe, so
every call here stays on the event loop.
"""
from __future__ import annotations
from ..origin import JobOrigin
from ..engine.graphs import FieldError

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import Field, BaseModel

from ..queue import JobRecord
from ..schemas import Cancelled, Deleted, JobList, JobsSubmitted, QueueState, Released
from ..story import FOR_SHOT, StoryStore, check_for_shot
from ..fsio import new_id
from .deps import Svc

router = APIRouter(tags=["jobs"])


class JobSubmit(BaseModel):
    recipe: dict[str, Any]
    stage: bool = False
    origin: JobOrigin | None = None               # D66: the suite / surface that asks


@router.post("/jobs", response_model=JobsSubmitted)
async def jobs_submit(svc: Svc, body: JobSubmit):
    ws, _, q = svc.require_project()
    if body.origin and body.origin.surface == FOR_SHOT:                       # D90 (02 §5): its results become takes of an open shot version
        try:
            await asyncio.to_thread(check_for_shot, StoryStore(ws), body.origin.payload)
        except ValueError as e:
            raise HTTPException(422, str(e))
    try:
        jobs = q.submit(body.recipe, stage=body.stage, origin=body.origin)
    except FieldError as e:
        raise HTTPException(422, e.detail())                                  # D65: {field, value, allowed, message}
    except ValueError as e:
        raise HTTPException(422, str(e))
    out = {"jobs": [j.model_dump() for j in jobs]}                        # the state at submission, before the loop runs on
    await q.flush()                                                          # D64: on disk before the reply
    return out


@router.post("/jobs/{job_id}/release", response_model=Released)
async def job_release(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    out = q.release(job_id)
    if not out:
        raise HTTPException(409, "job is not staged")
    await q.flush()                                                          # D64: on disk before the reply
    return {"released": [j.id for j in out]}


@router.post("/queue/release", response_model=Released)
async def queue_release(svc: Svc):
    _, _, q = svc.require_project()
    out = q.release()
    await q.flush()                                                          # D64: on disk before the reply
    return {"released": [j.id for j in out]}


@router.get("/jobs", response_model=JobList)
async def jobs_list(svc: Svc, status: str | None = None):
    _, _, q = svc.require_project()
    return {"items": q.list(status)}


@router.get("/jobs/{job_id}", response_model=JobRecord)
async def job_get(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    j = q.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j.model_dump()


@router.post("/jobs/{job_id}/cancel", response_model=Cancelled)
async def job_cancel(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    if not await q.cancel(job_id):
        raise HTTPException(409, "job is not cancellable")
    await q.flush()                                                          # D64: on disk before the reply
    return {"cancelled": job_id}


@router.post("/jobs/{job_id}/requeue", response_model=JobRecord)
async def job_requeue(svc: Svc, job_id: str):
    """LT2: a failed, resumable job back to the queue (a killed trainer continues from its newest save)."""
    _, _, q = svc.require_project()
    try:
        rec = q.requeue(job_id)
    except KeyError:
        raise HTTPException(404, "job not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    await q.flush()                                                       # V11: D64 — on disk before the reply
    return rec


@router.delete("/jobs/{job_id}", response_model=Deleted)
async def job_delete(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    if not q.delete(job_id):
        raise HTTPException(409, "only finished jobs can be deleted")
    await q.flush()                                                          # D64: on disk before the reply
    return {"deleted": job_id}


@router.get("/queue", response_model=QueueState)
async def queue_get(svc: Svc):
    _, _, q = svc.require_project()
    return q.state()


@router.post("/queue/pause", response_model=QueueState)
async def queue_pause(svc: Svc):
    _, _, q = svc.require_project()
    q.pause()
    state = q.state()
    await q.flush()                                                          # D64: on disk before the reply
    return state


@router.post("/queue/unpause", response_model=QueueState)
async def queue_unpause(svc: Svc):
    _, _, q = svc.require_project()
    q.unpause()
    state = q.state()
    await q.flush()                                                          # D64: on disk before the reply
    return state


# ---- D115: several recipes as one batch (Image's Expand: one job per pose cell, each with its own origin) --------------------------
class JobsBatchItem(BaseModel):
    recipe: dict[str, Any]
    origin: JobOrigin | None = None


class JobsBatchSubmit(BaseModel):
    items: list[JobsBatchItem] = Field(min_length=1, max_length=200)
    stage: bool = False


@router.post("/jobs/batch", response_model=JobsSubmitted)
async def jobs_submit_batch(svc: Svc, body: JobsBatchSubmit):
    """D115: the items as one batch under one batch id (Image's Expand ▶: one job per pose cell); every item is checked first, so a
    refused item refuses the whole submit and leaves no job behind."""
    ws, _, q = svc.require_project()
    batch = new_id("bat")
    jobs = []
    try:
        for it in body.items:
            q.check(it.recipe)
            if it.origin and it.origin.surface == FOR_SHOT:
                await asyncio.to_thread(check_for_shot, StoryStore(ws), it.origin.payload)
        for it in body.items:
            jobs += q.submit(it.recipe, stage=body.stage, origin=it.origin, batch_id=batch)
    except FieldError as e:
        raise HTTPException(422, e.detail())
    except ValueError as e:
        raise HTTPException(422, str(e))
    await q.flush()
    return {"jobs": jobs}
