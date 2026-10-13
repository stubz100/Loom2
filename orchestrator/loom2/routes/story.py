"""Story (17 §7, D85): the workspace's records — SY0: the world (read, replace with a revision guard); SY1: profiles with versions (create
from a hero image, patch, copy, lock, delete), curation (keep → the reference set, reject) and Expand (one T2I job per coverage cell in one
batch, the results placed on the version's candidates page). Shots and the flow join here."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..fsio import new_id
from ..origin import JobOrigin
from ..schemas import Curated, Deleted, Expanded, ProfileList
from ..story import PRESETS, Profile, ProfileClass, StaleProfile, StaleWorld, StoryStore, World, expand_spec, plan_expand
from .deps import Svc

router = APIRouter(tags=["story"])


@router.get("/story/world", response_model=World)
async def world_get(svc: Svc):
    ws, _, _ = svc.require_project()
    return (await asyncio.to_thread(StoryStore(ws).world)).model_dump()


@router.put("/story/world", response_model=World)
async def world_put(svc: Svc, body: dict):
    ws, _, _ = svc.require_project()
    try:
        w = await asyncio.to_thread(StoryStore(ws).put_world, body)
    except StaleWorld as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("story.changed", {"kind": "world", "revision": w.revision})
    return w.model_dump()


# ---- profiles (SY1, 17 §3b) --------------------------------------------------------------------------------------------------------
class ProfileCreate(BaseModel):
    name: str
    cls: ProfileClass = "character"
    hero_asset_id: str | None = None              # moves onto the version's reference page as its cover
    stub: str = ""                                # the clause a mention carries; the name when empty


class CurateBody(BaseModel):
    asset_ids: list[str]
    verdict: Literal["keep", "reject"]


class ExpandBody(BaseModel):
    version: str | None = None                    # the current one when absent
    preset: str = "full"
    seeds_per_cell: int = Field(1, ge=1, le=4)
    tier: str | None = None                       # draft (default) | full — the project format's aspect at the tier's height
    style_id: str | None = None


def _changed(svc, p: Profile) -> None:
    svc.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})


@router.get("/story/profiles", response_model=ProfileList)
async def profiles_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [p.model_dump() for p in await asyncio.to_thread(StoryStore(ws).profiles)]}


@router.post("/story/profiles", response_model=Profile)
async def profile_create(svc: Svc, body: ProfileCreate):
    ws, cat, _ = svc.require_project()
    groups = svc.require_groups()
    if body.hero_asset_id:
        rec = await asyncio.to_thread(cat.get, body.hero_asset_id)
        if rec is None or rec.trashed_at is not None or rec.kind != "image":
            raise HTTPException(422, "the hero must be an image in the Catalogue")
    try:
        p = await asyncio.to_thread(StoryStore(ws).create_profile, body.name, body.cls, groups, body.hero_asset_id, body.stub)
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.group_changed([v.group_id for v in p.versions])
    _changed(svc, p)
    return p.model_dump()


@router.get("/story/profiles/{pid}", response_model=Profile)
async def profile_get(svc: Svc, pid: str):
    ws, _, _ = svc.require_project()
    p = await asyncio.to_thread(StoryStore(ws).profile, pid)
    if p is None:
        raise HTTPException(404, "profile not found")
    return p.model_dump()


@router.patch("/story/profiles/{pid}", response_model=Profile)
async def profile_patch(svc: Svc, pid: str, body: dict):
    ws, _, _ = svc.require_project()
    try:
        p = await asyncio.to_thread(StoryStore(ws).patch_profile, pid, body)
    except KeyError:
        raise HTTPException(404, "profile not found")
    except StaleProfile as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _changed(svc, p)
    return p.model_dump()


@router.delete("/story/profiles/{pid}", response_model=Deleted)
async def profile_delete(svc: Svc, pid: str):
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    store = StoryStore(ws)
    p = await asyncio.to_thread(store.profile, pid)
    if p is None:
        raise HTTPException(404, "profile not found")
    await asyncio.to_thread(store.delete_profile, pid, groups)
    svc.group_changed([v.group_id for v in p.versions])
    svc.hub.broadcast("story.changed", {"kind": "profile", "id": pid, "revision": p.revision + 1, "deleted": True})
    return {"deleted": pid}


@router.post("/story/profiles/{pid}/versions", response_model=Profile)
async def profile_new_version(svc: Svc, pid: str):
    """A full copy of the current version (its reference set duplicated), open, now the current one."""
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    try:
        p = await asyncio.to_thread(StoryStore(ws).new_version, pid, groups)
    except KeyError:
        raise HTTPException(404, "profile not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    v = p.version()
    svc.group_changed([v.group_id, groups.parent.get(("group", v.group_id), "root")])
    for aid in await asyncio.to_thread(groups._asset_ids, v.group_id):
        if (rec := await asyncio.to_thread(svc.catalogue.get, aid)) is not None:
            svc.hub.broadcast("asset.created", rec.model_dump())
    _changed(svc, p)
    return p.model_dump()


@router.post("/story/profiles/{pid}/versions/{vid}/lock", response_model=Profile)
async def profile_lock(svc: Svc, pid: str, vid: str):
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    try:
        p = await asyncio.to_thread(StoryStore(ws).lock_version, pid, vid, groups)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.group_changed([p.version(vid).group_id])
    _changed(svc, p)
    return p.model_dump()


@router.post("/story/profiles/{pid}/versions/{vid}/curate", response_model=Curated)
async def profile_curate(svc: Svc, pid: str, vid: str, body: CurateBody):
    """Keep: the assets are marked keep and move onto the version's reference page; reject: marked reject, left where they are."""
    ws, cat, _ = svc.require_project()
    groups = svc.require_groups()
    p = await asyncio.to_thread(StoryStore(ws).profile, pid)
    if p is None:
        raise HTTPException(404, "profile not found")
    try:
        v = p.version(vid)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if v.state != "open":
        raise HTTPException(423, f"version {vid} is locked")
    ids = [i for i in body.asset_ids if (r := await asyncio.to_thread(cat.get, i)) is not None and r.trashed_at is None]
    recs = await asyncio.to_thread(cat.patch_many, ids, {"state": body.verdict})
    for r in recs:
        svc.hub.broadcast("asset.updated", r.model_dump())
    if body.verdict == "keep" and ids:
        changed = await asyncio.to_thread(groups.move, [("asset", i) for i in ids], v.group_id)
        svc.group_changed(changed)
    return {"kept": ids if body.verdict == "keep" else [], "rejected": ids if body.verdict == "reject" else []}


@router.post("/story/profiles/{pid}/expand", response_model=Expanded)
async def profile_expand(svc: Svc, pid: str, body: ExpandBody):
    """One queued T2I job per coverage cell of the preset (× seeds), in one batch, each with the hero as reference 1 and the cell's sentence
    after the stub; the results land on the version's candidates page (made on the first Expand) with `params.coverage_cell`."""
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = StoryStore(ws)
    p = await asyncio.to_thread(store.profile, pid)
    if p is None:
        raise HTTPException(404, "profile not found")
    try:
        v = p.version(body.version)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if body.preset not in PRESETS:
        raise HTTPException(422, f"unknown preset {body.preset!r}; one of {', '.join(PRESETS)}")
    variant = svc.app.settings.variant
    spec = expand_spec(variant)
    if spec is None:
        raise HTTPException(422, "no model to expand with in this build")
    fmt = ws.load().format
    h = 1080 if body.tier == "full" else 544
    w = max(64, round(h * fmt.width / fmt.height / 16) * 16)
    gid = v.candidates_group_id if v.candidates_group_id and v.candidates_group_id in groups.groups else None
    if gid is None:
        gid = (await asyncio.to_thread(groups.create, f"{p.name} · {v.id} · candidates")).id
        p = await asyncio.to_thread(store.set_candidates, pid, v.id, gid)
        v = p.version(v.id)
        svc.group_changed([gid])
    try:
        planned = plan_expand(p, v, body.preset, variant, seeds_per_cell=body.seeds_per_cell, width=w, height=h, style_id=body.style_id, tier=body.tier or "draft", group_id=gid)
    except ValueError as e:
        raise HTTPException(422, str(e))
    batch = new_id("bat")
    jobs = []
    try:
        for recipe, origin in planned:
            jobs += svc.queue.submit(recipe, origin=JobOrigin.model_validate(origin), batch_id=batch)
    except ValueError as e:
        raise HTTPException(422, str(e))
    _changed(svc, p)
    return {"batch_id": batch, "job_ids": [j.id for j in jobs], "cells": len(planned), "group_id": gid, "model_id": spec.id}
