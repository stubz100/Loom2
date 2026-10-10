"""Jobs and the queue (06 §6, 07 §5): submit (or stage), release, cancel, delete, pause. `JobQueue` is not thread-safe, so
every call here stays on the event loop.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .deps import Svc

router = APIRouter(tags=["jobs"])


class JobSubmit(BaseModel):
    recipe: dict[str, Any]
    stage: bool = False


@router.post("/jobs")
async def jobs_submit(svc: Svc, body: JobSubmit):
    _, _, q = svc.require_project()
    try:
        jobs = q.submit(body.recipe, stage=body.stage)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"jobs": [j.model_dump() for j in jobs]}


@router.post("/jobs/{job_id}/release")
async def job_release(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    out = q.release(job_id)
    if not out:
        raise HTTPException(409, "job is not staged")
    return {"released": [j.id for j in out]}


@router.post("/queue/release")
async def queue_release(svc: Svc):
    _, _, q = svc.require_project()
    return {"released": [j.id for j in q.release()]}


@router.get("/jobs")
async def jobs_list(svc: Svc, status: str | None = None):
    _, _, q = svc.require_project()
    return {"items": q.list(status)}


@router.get("/jobs/{job_id}")
async def job_get(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    j = q.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j.model_dump()


@router.post("/jobs/{job_id}/cancel")
async def job_cancel(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    if not await q.cancel(job_id):
        raise HTTPException(409, "job is not cancellable")
    return {"cancelled": job_id}


@router.delete("/jobs/{job_id}")
async def job_delete(svc: Svc, job_id: str):
    _, _, q = svc.require_project()
    if not q.delete(job_id):
        raise HTTPException(409, "only finished jobs can be deleted")
    return {"deleted": job_id}


@router.get("/queue")
async def queue_get(svc: Svc):
    _, _, q = svc.require_project()
    return q.state()


@router.post("/queue/pause")
async def queue_pause(svc: Svc):
    _, _, q = svc.require_project()
    q.pause()
    return q.state()


@router.post("/queue/unpause")
async def queue_unpause(svc: Svc):
    _, _, q = svc.require_project()
    q.unpause()
    return q.state()
