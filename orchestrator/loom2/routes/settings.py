"""App settings and the prompt snippet library (07 §6, 09 §3e) — app state, not project data."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..fsio import atomic_write_json, read_json_or
from ..roster import Roster
from .deps import Svc

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def get_settings(svc: Svc):
    return svc.app.settings.model_dump()


@router.put("/settings")
async def put_settings(svc: Svc, patch: dict):
    try:
        s = svc.app.update_settings({k: v for k, v in patch.items() if k != "variant"})   # C3: the variant is the build's, never a setting
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0].get("msg", "invalid settings") if e.errors() else "invalid settings")
    svc.roster = await asyncio.to_thread(Roster(svc.app.models_root, [Path(p) for p in s.mounted_model_trees], s.variant).scan)   # C7: off the loop
    if svc.queue:                                   # B7: the live queue compiles against the new roster at once
        svc.queue.roster = svc.roster
    svc.engine.reconfigure()
    return s.model_dump()


@router.get("/snippets")
async def snippets_get(svc: Svc):
    return await asyncio.to_thread(read_json_or, svc.app.state_dir / "snippets.json", {"snippets": []})


@router.put("/snippets")
async def snippets_put(svc: Svc, body: dict):
    await asyncio.to_thread(atomic_write_json, svc.app.state_dir / "snippets.json", body)
    return body
