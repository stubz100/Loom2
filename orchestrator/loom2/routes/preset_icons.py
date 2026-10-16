"""D90 (02 §6.3): the preset swatch pack — app state, not project data (`loom2.preset_icons`). List, the swatch file (a media GET: the
`?k=` key opens it, D67), make (one staged t2i job per item in one batch; the jobs live in the open project's queue) and delete."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..engine.graphs import FieldError
from ..fsio import new_id
from ..origin import JobOrigin
from ..preset_icons import EVENT, SURFACE, SWATCH_SEED, PresetIconList, PresetIconStore, icon_key, swatch_recipe
from ..schemas import Deleted, PresetIconsMade
from .deps import Svc

router = APIRouter(tags=["preset-icons"])
REVALIDATE = {"Cache-Control": "private, no-cache"}       # re-made in place under the same key: the ETag answers, never a stale swatch


class PresetItem(BaseModel):
    field: str = Field(min_length=1, max_length=64)            # the prompt field (lighting · mood · style · background · scene …) or a snippet's
    value: str = Field(min_length=1, max_length=400)           # the preset's text, exactly as the field inserts it


class MakeBody(BaseModel):
    items: list[PresetItem] = Field(min_length=1, max_length=200)
    stage: bool = True                                         # D90: staged by default — the author releases the pack from the Dock
    seed: int = Field(SWATCH_SEED, ge=0)                       # one seed for the pack (a set reads alike); 0 = a random one per job (re-make)


def _store(svc) -> PresetIconStore:
    return PresetIconStore(svc.app.state_dir)


@router.get("/preset-icons", response_model=PresetIconList)
async def preset_icons_list(svc: Svc):
    return {"items": [i.model_dump() for i in await asyncio.to_thread(_store(svc).list)]}


@router.post("/preset-icons/make", response_model=PresetIconsMade)
async def preset_icons_make(svc: Svc, body: MakeBody):
    """One t2i job per item on the variant's swatch model (`/capabilities.defaults.swatch`), origin `{generate, swatch, {key, field, value}}`;
    the finisher stores the result under the key. Needs an open project — the jobs and their Catalogue results live there."""
    if not (svc.ws and svc.catalogue and svc.queue):
        raise HTTPException(409, "open a project to make preset swatches — their jobs run in its queue")
    _, _, q = svc.require_project()
    variant = svc.app.settings.variant
    batch = new_id("bat") if len(body.items) > 1 else None
    jobs, items = [], []
    try:
        for it in body.items:
            key = icon_key(it.field, it.value)
            origin = JobOrigin(suite="generate", surface=SURFACE, ref=key, payload={"key": key, "field": it.field, "value": it.value})
            made = q.submit(swatch_recipe(it.field, it.value, variant, body.seed, svc.app.settings.samples.swatch_prompts), stage=body.stage, origin=origin, batch_id=batch)   # D90: the scenes of Settings › Samples
            jobs += made
            items.append({"key": key, "field": it.field, "value": it.value, "job_id": made[0].id})
    except FieldError as e:
        raise HTTPException(422, e.detail())
    except ValueError as e:
        raise HTTPException(422, str(e))
    out = {"batch_id": batch, "items": items, "jobs": [j.model_dump() for j in jobs]}
    await q.flush()                                                          # D64: on disk before the reply
    return out


@router.get("/preset-icons/{key}/file")
async def preset_icons_file(svc: Svc, key: str):
    try:
        p = _store(svc).path(key)
    except KeyError:
        raise HTTPException(404, "no such swatch")
    if not await asyncio.to_thread(p.is_file):
        raise HTTPException(404, "no such swatch")
    return FileResponse(p, media_type="image/webp", headers=REVALIDATE)


@router.delete("/preset-icons/{key}", response_model=Deleted)
async def preset_icons_delete(svc: Svc, key: str):
    try:
        found = await asyncio.to_thread(_store(svc).delete, key)
    except KeyError:
        found = False
    if not found:
        raise HTTPException(404, "no such swatch")
    svc.hub.broadcast(EVENT, {"keys": [key], "deleted": True})
    return {"deleted": key}
