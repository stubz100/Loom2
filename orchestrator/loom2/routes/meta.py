"""Health, version, capabilities, recipe preview and the shell's shutdown call (06 §6)."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import __version__
from ..build_info import version_info
from ..capabilities import capabilities as build_capabilities
from ..engine.graphs import CompileError, FieldError
from ..engine.pipeline import plan, preview_problems
from ..recipes import I2V, T2I, parse_recipe
from ..schemas import Capabilities, DocumentPreview, HealthInfo, I2VPreview, SessionInfo, ShuttingDown, T2IPreview, VersionInfo
from .deps import Svc

router = APIRouter(tags=["meta"])


class RecipeBody(BaseModel):
    recipe: dict[str, Any]


@router.get("/health", response_model=HealthInfo)
async def health(svc: Svc):
    return {"ok": True, "version": __version__, "project_open": svc.ws is not None,
            "engine_running": svc.engine.state()["running"], "variant": svc.app.settings.variant,
            "start_suite": os.environ.get("LOOM2_START_SUITE"), "session_id": svc.app.session_id}   # start_suite: dev affordance


@router.get("/version", response_model=VersionInfo)
async def version(svc: Svc):
    """D36: app version, checkout commit, shell build, engine pin and running engine, node pins, schema versions, paths."""
    info = await asyncio.to_thread(version_info)
    pin = info.pop("engine_pin")
    return {**info, "variant": svc.app.settings.variant, "engine": {"pin": pin, "running": svc.engine.version},
            "paths": {"state": str(svc.app.state_dir), "logs": str(svc.app.logs_dir), "models_root": str(svc.app.models_root)}}


@router.get("/session", response_model=SessionInfo)
async def session_info(svc: Svc):
    """D67: what this launch's client needs besides the token — the read-only media key for <img> / <video> URLs (`?k=`)."""
    return {"session_id": svc.app.session_id, "media_key": svc.app.media_key}


@router.get("/capabilities", response_model=Capabilities)
async def capabilities(svc: Svc):
    return build_capabilities(svc)


@router.post("/recipes/preview", response_model=T2IPreview | I2VPreview | DocumentPreview, response_model_exclude_unset=True)
async def recipe_preview(svc: Svc, body: RecipeBody):
    """09 §3a / D64: the plan of any recipe — effective parameters (the exact string the engine will receive for t2i), what it needs,
    ETA and VRAM fit, missing weights, and the contract problems a submission would hit (checked against the engine's last object_info)."""
    try:
        recipe = parse_recipe(body.recipe)
    except ValueError as e:
        raise HTTPException(422, str(e))
    variant = svc.app.settings.variant
    try:
        p = plan(recipe, variant, svc.queue.timing_history() if svc.queue else None)
    except FieldError as e:
        raise HTTPException(422, e.detail())                                  # D65: {field, value, allowed, message}
    except CompileError as e:
        raise HTTPException(422, str(e))
    missing = []
    for mid in p.weights:
        try:
            r = svc.roster.resolve(mid)
        except KeyError as e:
            raise HTTPException(422, str(e))              # B11: an unknown LoRA id is the caller's error, not a 500
        if r.path is None:
            missing.append({"model_id": mid, "health": r.health, "approx_gb": r.entry.approx_gb})
    est = svc.queue.estimate(recipe) if svc.queue else {**p.estimate, "vram_gb": p.vram_gb}
    problems = preview_problems(recipe, svc.roster, svc.queue.object_info_cached() if svc.queue else None, variant)
    common = {"missing": missing, "estimate": est, "count": p.count, "problems": problems, "weights": p.weights, "warm_group": p.warm_group}
    if isinstance(recipe, (T2I, I2V)):
        return {**p.params, **common}
    return {"kind": p.kind, "model_id": p.model_id, "engine": p.engine, "params": p.params, "needs": p.needs, **common}


@router.post("/shutdown", response_model=ShuttingDown)
async def shutdown(request: Request):
    """Graceful exit for the shell (06 §1): the lifespan teardown stops the queue (clean mark) and the engine."""
    fn = getattr(request.app.state, "request_shutdown", None)
    if fn is None:
        raise HTTPException(501, "no shutdown hook installed")
    asyncio.get_running_loop().call_later(0.2, fn)
    return {"shutting_down": True}
