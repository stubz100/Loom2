"""App settings (07 §6) — app state, not project data. D92: the app-wide prompt snippets (`/snippets`) are gone — every project's Story ·
World library holds its presets, seeded once from `<state>/snippets.json` (library.py)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..config import Settings
from ..roster import Roster
from .deps import Svc

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=Settings)
async def get_settings(svc: Svc):
    return svc.app.settings.model_dump()


@router.put("/settings", response_model=Settings)
async def put_settings(svc: Svc, patch: dict):
    try:
        s = svc.app.update_settings({k: v for k, v in patch.items() if k != "variant"})   # C3: the variant is the build's, never a setting
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0].get("msg", "invalid settings") if e.errors() else "invalid settings")
    svc.roster = await asyncio.to_thread(Roster(svc.app.models_root, [Path(p) for p in s.mounted_model_trees], s.variant).scan)   # C7: off the loop
    if svc.queue:                                   # B7: the live queue compiles against the new roster at once
        svc.queue.roster = svc.roster
    await asyncio.to_thread(svc.publish_trained)     # V2: the project's trained LoRAs are the fresh roster's too
    svc.engine.reconfigure()
    return s.model_dump()

