"""Weights roster (04 §1b, Models suite): listing with health, scan, unlisted files, fetch as a job, sha256 verify."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..roster import ROSTER_BY_ID
from ..tools.fetch import FetchJob, sha256_of
from .deps import Svc

router = APIRouter(tags=["models"])


class FetchRequest(BaseModel):
    model_id: str


@router.get("/models")
async def models(svc: Svc, include_retired: bool = False):
    items = await asyncio.to_thread(svc.roster.listing, include_retired)
    return {"items": items, "models_root": str(svc.app.models_root),
            "scanned_at": svc.roster.scanned_at, "fetches": {k: v.state() for k, v in svc.fetches.items()}}


@router.post("/models/scan")
async def models_scan(svc: Svc):
    roster = svc.roster
    await asyncio.to_thread(roster.scan)                     # D37: two model roots are walked; never on the event loop
    return {"items": await asyncio.to_thread(roster.listing), "unlisted": await asyncio.to_thread(roster.unlisted_files)}


@router.get("/models/unlisted")
async def models_unlisted(svc: Svc):
    return {"items": await asyncio.to_thread(svc.roster.unlisted_files)}


@router.post("/models/fetch")
async def models_fetch(svc: Svc, body: FetchRequest):
    entry = ROSTER_BY_ID.get(body.model_id)
    if not entry:
        raise HTTPException(404, "unknown model id")
    if svc.app.settings.variant == "open" and "open" not in entry.variants:
        raise HTTPException(403, "model is not part of the open variant")
    job = svc.fetches.get(body.model_id)
    if job and job.status in ("queued", "downloading", "hashing"):
        return job.state()
    job = FetchJob(entry, svc.app.models_root, svc.hub, svc.app.settings.hf_home)
    svc.fetches[body.model_id] = job
    job.start()
    return job.state()


@router.post("/models/{model_id}/verify")
async def models_verify(svc: Svc, model_id: str):
    try:
        r = svc.roster.resolve(model_id)
    except KeyError:
        raise HTTPException(404, "unknown model id")
    if not r.path:
        raise HTTPException(404, f"{model_id} is {r.health}")
    digest = await asyncio.to_thread(sha256_of, Path(r.path))
    return {"model_id": model_id, "sha256": digest, "matches_ledger": (r.sha256 == digest) if r.sha256 else None}
