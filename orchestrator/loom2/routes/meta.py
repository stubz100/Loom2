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
from ..engine.graphs import CompileError, I2V_WEIGHTS, PRESETS, effective_params, estimate_i2v_seconds, i2v_params
from ..recipes import I2V, T2I, parse_recipe
from .deps import Svc

router = APIRouter(tags=["meta"])


class RecipeBody(BaseModel):
    recipe: dict[str, Any]


@router.get("/health")
async def health(svc: Svc):
    return {"ok": True, "version": __version__, "project_open": svc.ws is not None,
            "engine_running": svc.engine.state()["running"], "variant": svc.app.settings.variant,
            "start_suite": os.environ.get("LOOM2_START_SUITE"), "session_id": svc.app.session_id}   # start_suite: dev affordance


@router.get("/version")
async def version(svc: Svc):
    """D36: app version, checkout commit, shell build, engine pin and running engine, node pins, schema versions, paths."""
    info = await asyncio.to_thread(version_info)
    pin = info.pop("engine_pin")
    return {**info, "variant": svc.app.settings.variant, "engine": {"pin": pin, "running": svc.engine.version},
            "paths": {"state": str(svc.app.state_dir), "logs": str(svc.app.logs_dir), "models_root": str(svc.app.models_root)}}


@router.get("/capabilities")
async def capabilities(svc: Svc):
    return build_capabilities(svc)


@router.post("/recipes/preview")
async def recipe_preview(svc: Svc, body: RecipeBody):
    """09 §3a: the exact string the engine will receive, effective parameters, ETA and VRAM fit, missing weights."""
    try:
        recipe = parse_recipe(body.recipe)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if isinstance(recipe, I2V):                                  # M6: snapped size / frames, the preset that runs, missing weights, ETA
        try:
            ep = i2v_params(recipe)
        except CompileError as e:
            raise HTTPException(422, str(e))
        missing = []
        for mid in I2V_WEIGHTS[recipe.model_id]:
            r = svc.roster.resolve(mid)
            if r.path is None:
                missing.append({"model_id": mid, "health": r.health, "approx_gb": r.entry.approx_gb})
        return {**ep, "missing": missing, "estimate": estimate_i2v_seconds(recipe), "count": len(recipe.seeds or [0])}
    if not isinstance(recipe, T2I):
        raise HTTPException(422, "preview supports t2i and i2v recipes")
    try:
        ep = effective_params(recipe)
    except CompileError as e:
        raise HTTPException(422, str(e))
    missing = []
    preset = PRESETS[recipe.model_id]
    for mid in [recipe.model_id, ep["te_id"], preset.vae_id, *([preset.turbo_lora] if ep["turbo"] and preset.turbo_lora else []), *[l.model_id for l in recipe.loras]]:
        try:
            r = svc.roster.resolve(mid)
        except KeyError as e:
            raise HTTPException(422, str(e))              # B11: an unknown LoRA id is the caller's error, not a 500
        if r.path is None:
            missing.append({"model_id": mid, "health": r.health, "approx_gb": r.entry.approx_gb})
    est = svc.queue.estimate(recipe) if svc.queue else {"seconds": None, "source": "no project"}
    return {**ep, "missing": missing, "estimate": est, "count": len(recipe.seeds or [0])}


@router.post("/shutdown")
async def shutdown(request: Request):
    """Graceful exit for the shell (06 §1): the lifespan teardown stops the queue (clean mark) and the engine."""
    fn = getattr(request.app.state, "request_shutdown", None)
    if fn is None:
        raise HTTPException(501, "no shutdown hook installed")
    asyncio.get_running_loop().call_later(0.2, fn)
    return {"shutting_down": True}
