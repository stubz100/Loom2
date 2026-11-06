"""The ComfyUI engine process (06 §3b): health and VRAM, start / stop / restart, free cached models."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from ..schemas import EngineState, Freed
from ..services import Services
from .deps import Svc

router = APIRouter(tags=["engine"])
# D61: an engine that cannot start or is not running answers 503 with the reason, never a 500 (found by the route fuzz)
ENGINE_DOWN = (RuntimeError, OSError, httpx.HTTPError)


@router.get("/engine", response_model=EngineState, response_model_exclude_unset=True)
async def engine_get(svc: Svc):
    return await svc.engine.health()


@router.post("/engine/start", response_model=EngineState, response_model_exclude_unset=True)
async def engine_start(svc: Svc):
    _card_free(svc)
    try:
        return await svc.engine.start()
    except ENGINE_DOWN as e:
        raise HTTPException(503, f"the engine could not start: {e}")


@router.post("/engine/stop", response_model=EngineState, response_model_exclude_unset=True)
async def engine_stop(svc: Svc):
    _engine_idle(svc)
    return await svc.engine.stop()


@router.post("/engine/restart", response_model=EngineState, response_model_exclude_unset=True)
async def engine_restart(svc: Svc):
    _engine_idle(svc)
    try:
        return await svc.engine.restart()
    except ENGINE_DOWN as e:
        raise HTTPException(503, f"the engine could not restart: {e}")


@router.post("/engine/free", response_model=Freed)
async def engine_free(svc: Svc):
    _engine_idle(svc)
    try:
        await svc.engine.client.free()
    except ENGINE_DOWN as e:
        raise HTTPException(503, f"the engine is not reachable: {e}")
    return {"freed": True}


def _card_free(svc: Services) -> None:
    """K (rule 10, D97): a job that took the whole card and stopped the engine for it (training, TTS cloning, the mouth step) — the engine
    starts after it, never beside it (Start in the Engine menu launched ComfyUI next to a 13.6 GB trainer)."""
    q = svc.queue
    rid = q.state()["running"] if q else None
    job = q.get(rid) if q and rid else None
    if job is None:
        return
    from ..engine.pipeline import plan
    from ..recipes import parse_recipe
    try:
        p = plan(parse_recipe(job.recipe), job.variant)
    except Exception:  # noqa: BLE001 — a recipe that no longer parses is not this route's concern
        return
    if p.gpu and not p.engine:
        raise HTTPException(409, f"job {rid} has the whole card — the engine starts after it (one job on the GPU, D97)")


def _engine_idle(svc: Services) -> None:
    """C14: stop / restart / free while a job renders would fail that job — the user cancels it first."""
    running = svc.queue.state()["running"] if svc.queue else None
    if running:
        raise HTTPException(409, f"job {running} is running — cancel it first")
