"""The ComfyUI engine process (06 §3b): health and VRAM, start / stop / restart, free cached models."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import Services
from .deps import Svc

router = APIRouter(tags=["engine"])


@router.get("/engine")
async def engine_get(svc: Svc):
    return await svc.engine.health()


@router.post("/engine/start")
async def engine_start(svc: Svc):
    try:
        return await svc.engine.start()
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.post("/engine/stop")
async def engine_stop(svc: Svc):
    _engine_idle(svc)
    return await svc.engine.stop()


@router.post("/engine/restart")
async def engine_restart(svc: Svc):
    _engine_idle(svc)
    return await svc.engine.restart()


@router.post("/engine/free")
async def engine_free(svc: Svc):
    _engine_idle(svc)
    await svc.engine.client.free()
    return {"freed": True}


def _engine_idle(svc: Services) -> None:
    """C14: stop / restart / free while a job renders would fail that job — the user cancels it first."""
    running = svc.queue.state()["running"] if svc.queue else None
    if running:
        raise HTTPException(409, f"job {running} is running — cancel it first")
