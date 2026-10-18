"""Story (17 §7, D85): the workspace's records — SY0: the world (read, replace with a revision guard); SY1: profiles with versions (create
from a hero image, patch, copy, lock, delete), curation (keep → the reference set, reject) and Expand (one T2I job per coverage cell in one
batch, the results placed on the version's candidates page); SY2: shots with versions (from a stage camera and / or a clip; takes; the
finalize gate = the project format's size); SY3: the flow (one file per node, the index of positions, edges and the start; bind /
spawn a shot as a node's sole property; validation as a list)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..fsio import new_id, utc_now
from ..origin import JobOrigin
from ..clips import ClipStore
from ..loras import LoraRegistry, publish, unpublish
from ..library import Library, LibraryStore, StaleLibrary
from ..schemas import Curated, Deleted, ProfileAdded, LibraryChange, LibraryRemoved, Expanded, FlowOut, FlowProblems, LipsyncQueued, LoraCheckQueued, LoraRecordList, LoraRecordOut, NodeShot, ProfileList, ShotList, TrainQueued, TtsQueued, VoiceList, VoiceRecordOut
from ..stages import StageStore
from ..shot_recipe import TEMPLATES, StampReader, Template, recipe_state, rerun_recipe, stale_plan, used_run
from ..story import FOR_SHOT, NODE_TYPES, PRESETS, cell_sentence, FlowGraph, FlowNode, Profile, ProfileClass, SheetColour, Shot, StaleFlow, StaleProfile, StaleShot, StaleWorld, StoryStore, VersionLocked, World, expand_spec, finalize_reason, plan_expand, validate_flow
from ..voices import VoiceRecord, VoiceStore, check_voice
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


# ---- the World library (D92) -------------------------------------------------------------------------------------------------------
class LibraryAdd(BaseModel):
    field: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=400)               # the words the field takes
    name: str = Field("", max_length=80)                          # the words when empty
    revision: int | None = None                                   # the library the client holds (409 when stale)
    id: str | None = Field(None, pattern=r"^lib_[0-9a-z]+$")    # the Undo of a removal: the entry's id …
    at: int | None = Field(None, ge=0)                            # … and its place


class LibraryOrder(BaseModel):
    ids: list[str]
    revision: int | None = None


def _library(svc) -> LibraryStore:
    ws, _, _ = svc.require_project()
    return LibraryStore(ws.story_dir, svc.app.state_dir)


def _lib_changed(svc, lib: Library) -> None:
    svc.hub.broadcast("story.changed", {"kind": "library", "revision": lib.revision})


async def _lib_call(svc, fn, *args, **kw):
    try:
        return await asyncio.to_thread(fn, *args, **kw)
    except KeyError:
        raise HTTPException(404, "no such library entry")
    except StaleLibrary as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/story/library", response_model=Library)
async def library_get(svc: Svc):
    """The project's library of prompt-field presets — seeded with the built-in vocabulary and the app-wide presets on the first read."""
    return (await asyncio.to_thread(_library(svc).get)).model_dump()


@router.post("/story/library/entries", response_model=LibraryChange)
async def library_add(svc: Svc, body: LibraryAdd):
    lib, e = await _lib_call(svc, _library(svc).add, body.field, body.name, body.text, base=body.revision, entry_id=body.id, at=body.at)
    _lib_changed(svc, lib)
    return {"library": lib.model_dump(), "entry": e.model_dump()}


@router.put("/story/library/order", response_model=Library)
async def library_order(svc: Svc, body: LibraryOrder):
    lib = await _lib_call(svc, _library(svc).reorder, body.ids, body.revision)
    _lib_changed(svc, lib)
    return lib.model_dump()


@router.patch("/story/library/entries/{eid}", response_model=LibraryChange)
async def library_patch(svc: Svc, eid: str, body: dict):
    lib, e = await _lib_call(svc, _library(svc).patch, eid, body)
    _lib_changed(svc, lib)
    return {"library": lib.model_dump(), "entry": e.model_dump()}


@router.delete("/story/library/entries/{eid}", response_model=LibraryRemoved)
async def library_remove(svc: Svc, eid: str, revision: int | None = None):
    lib, e, i = await _lib_call(svc, _library(svc).remove, eid, revision)
    _lib_changed(svc, lib)
    return {"library": lib.model_dump(), "entry": e.model_dump(), "index": i}


# ---- profiles (SY1, 17 §3b) --------------------------------------------------------------------------------------------------------
class ProfileCreate(BaseModel):
    name: str
    cls: ProfileClass = "character"
    hero_asset_id: str | None = None              # moves onto the version's reference page as its cover
    stub: str = ""                                # schema 1's clause — taken as the appearance; D93 (A9): empty stays empty (Cast says to describe the look)
    appearance: str | None = None                 # D93 (B4): version 1's sheet (the look, the outfit, bound colours, marks) and its label
    outfit: str | None = None
    colours: list[SheetColour] | None = None
    marks: str | None = None
    label: str | None = None


class CurateBody(BaseModel):
    asset_ids: list[str]
    verdict: Literal["keep", "reject"]


class ExpandBody(BaseModel):
    version: str | None = None                    # the current one when absent
    preset: str = "full"
    seeds_per_cell: int = Field(1, ge=1, le=4)
    tier: str | None = None                       # draft (default) | full — the project format's aspect at the tier's height
    style_id: str | None = None


class CandidatesBody(BaseModel):
    version: str | None = None                    # the current one when absent


class AddBody(BaseModel):
    asset_ids: list[str] = Field(min_length=1)
    role: Literal["hero", "reference", "candidate"]


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
        sheet = body.model_dump(include={"appearance", "outfit", "colours", "marks", "label"}, exclude_none=True)
        p = await asyncio.to_thread(lambda: StoryStore(ws).create_profile(body.name, body.cls, groups, body.hero_asset_id, body.stub, **sheet))
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


@router.post("/story/profiles/{pid}/candidates", response_model=Profile)
async def profile_candidates(svc: Svc, pid: str, body: CandidatesBody):
    """D93 (A1): the version's candidates page, made when it has none (as Expand does) — a casting run from Generate sends its results
    there through its origin's `group_id`. A final version refuses (423)."""
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    store = StoryStore(ws)
    p = await asyncio.to_thread(store.profile, pid)
    if p is None:
        raise HTTPException(404, "profile not found")
    try:
        v = p.version(body.version)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if v.state != "open":
        raise HTTPException(423, f"{p.name} {v.id} is final — its look is fixed; make a new version to cast it again")
    p, gid, made = await asyncio.to_thread(store.ensure_candidates, pid, v.id, groups)
    if made:
        svc.group_changed([gid, groups.parent.get(("group", gid), "root")])
        _changed(svc, p)
    return p.model_dump()


@router.post("/story/profiles/{pid}/versions/{vid}/add", response_model=ProfileAdded)
async def profile_add(svc: Svc, pid: str, vid: str, body: AddBody):
    """D93 (A2) "Add to character ▸": images from anywhere into a version — as the hero (onto the reference set as its cover), into the
    reference set, or as candidates. From Unprocessed or the version's candidates page they move; from any other page they are copied
    (the reply says which). A final version answers 423 with the reason."""
    ws, cat, _ = svc.require_project()
    groups = svc.require_groups()
    store = StoryStore(ws)
    before = {a: groups.parent.get(("asset", a)) for a in body.asset_ids}
    try:
        r = await asyncio.to_thread(store.add_assets, pid, vid, body.asset_ids, body.role, groups, cat)
    except KeyError as e:
        raise HTTPException(404, f"not found: {e}")
    except VersionLocked as e:
        raise HTTPException(423, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    for dup in r["copied"].values():
        if (rec := await asyncio.to_thread(cat.get, dup)) is not None:
            svc.hub.broadcast("asset.created", rec.model_dump())
    for rec in r.pop("updated"):
        svc.hub.broadcast("asset.updated", rec.model_dump())
    made = r.pop("made_page")
    svc.group_changed(sorted({r["group_id"], *(g for a, g in before.items() if g and a in r["moved"])} | ({groups.parent.get(("group", r["group_id"]), "root")} if made else set())))
    _changed(svc, r["profile"])
    return {**r, "profile": r["profile"].model_dump()}


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
    p, gid, made = await asyncio.to_thread(store.ensure_candidates, pid, v.id, groups)   # D93: one place makes the candidates page
    v = p.version(v.id)
    if made:
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


# ---- LoRA training (LT2, 18 §3c) ------------------------------------------------------------------------------------------------------
class TrainBody(BaseModel):
    version: str | None = None                    # the current one when absent
    model_id: str | None = None                   # the base; the first of /capabilities.train when absent
    steps: int = Field(1000, ge=100, le=5000)
    rank: int = Field(16, ge=4, le=128)
    resolution: int = Field(512, ge=256, le=1024)
    lr: float = Field(1e-4, gt=0.0, le=1e-2)
    seed: int = 42
    name: str = ""
    setting: str = ""
    trigger: str | None = None                    # made from the profile's name when absent (<slug>_<4 hex>)
    stage: bool = True                            # staged by default (18 §9): released when the rig is free


def _trigger(name: str) -> str:
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "", name.lower())[:12] or "lora"
    return f"{slug}_{new_id('t')[-4:]}"


@router.post("/story/profiles/{pid}/train", response_model=TrainQueued)
async def profile_train(svc: Svc, pid: str, body: TrainBody):
    """One `train_lora` job (staged by default) from the version's reference set; the queue's validation answers 422 with the sentence."""
    ws, _, q = svc.require_project()
    store = StoryStore(ws)
    p = await asyncio.to_thread(store.profile, pid)
    if p is None:
        raise HTTPException(404, "profile not found")
    try:
        v = p.version(body.version)
    except KeyError as e:
        raise HTTPException(404, str(e))
    from ..capabilities import _train
    caps = _train(svc, svc.app.settings.variant)
    model_id = body.model_id or next((b["model_id"] for b in caps["bases"] if b["health"] in ("present", "verified")), None)
    if not model_id:
        raise HTTPException(422, caps["why"] or "no trainable base with its weights on disk")
    trigger = (body.trigger or v.trigger or _trigger(p.name)).strip()
    recipe = {"kind": "train_lora", "profile_id": pid, "version": v.id, "model_id": model_id, "steps": body.steps, "rank": body.rank, "resolution": body.resolution,
              "lr": body.lr, "seed": body.seed, "trigger": trigger, "name": body.name.strip() or f"{p.name} {v.id}", "setting": body.setting}
    origin = JobOrigin(suite="story", surface="train", ref=pid, payload={"version": v.id})
    try:
        job = q.submit(recipe, stage=body.stage, origin=origin)[0]
    except ValueError as e:
        raise HTTPException(422, str(e))
    if v.trigger != trigger:                                                      # the trigger is the version's from now on (a retrain keeps it)
        p = await asyncio.to_thread(store.set_version_lora, pid, v.id, v.lora, trigger)
        _changed(svc, p)
    return {"job_id": job.id, "trigger": trigger, "model_id": model_id, "staged": job.status == "staged"}


@router.get("/story/loras", response_model=LoraRecordList)
async def loras_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [r.model_dump() for r in await asyncio.to_thread(LoraRegistry(ws).list)]}


@router.get("/story/loras/{lid}", response_model=LoraRecordOut)
async def lora_get(svc: Svc, lid: str):
    ws, _, _ = svc.require_project()
    r = await asyncio.to_thread(LoraRegistry(ws).get, lid)
    if r is None:
        raise HTTPException(404, "LoRA not found")
    return r.model_dump()


CHECK_CELLS = [{"shot": "close-up", "angle": "front", "expression": "neutral"}, {"shot": "medium", "angle": "three-quarter left", "expression": "smiling"},
               {"shot": "close-up", "angle": "three-quarter right", "expression": "neutral"}, {"shot": "medium", "angle": "front", "expression": "surprised"}]


@router.post("/story/loras/{lid}/check", response_model=LoraCheckQueued)
async def lora_check(svc: Svc, lid: str):
    """18 §3h (LT3), advisory: eight Iterate images — four coverage sentences × with / without the LoRA, the same seeds, the trigger in the
    prompt — into a "LoRA check" page under the version's candidates; FaceSim scores each against the hero as it lands (the finisher) and the
    record's `identity` grows. Never a gate; without the FaceSim weights the record says so."""
    ws, _, q = svc.require_project()
    groups = svc.require_groups()
    reg = LoraRegistry(ws)
    rec = await asyncio.to_thread(reg.get, lid)
    if rec is None:
        raise HTTPException(404, "LoRA not found")
    store = StoryStore(ws)
    p = await asyncio.to_thread(store.profile, rec.profile_id)
    if p is None:
        raise HTTPException(404, "the LoRA's profile is gone")
    v = p.version(rec.version)
    if not v.hero_asset_id:
        raise HTTPException(422, "the version has no hero to compare against")
    variant = svc.app.settings.variant
    from ..loras import model_base
    from ..models import registry as reg_models
    cands = sorted((s for s in reg_models.image_specs() if s.recipes.t2i and reg_models.offered(s, variant) and (s.base or s.family) == rec.base
                    and q.roster.resolve(s.id).path), key=lambda s: s.order)
    if not cands:
        raise HTTPException(422, f"no model of the {rec.base} base with its weights is offered in this build")
    spec = cands[0]
    fmt = ws.load().format
    h = 544
    w = max(64, round(h * fmt.width / fmt.height / 16) * 16)
    name = f"{p.name} · {v.id} · LoRA check"
    gid = next((g.id for g in groups.groups.values() if g.name == name), None) or (await asyncio.to_thread(groups.create, name)).id
    batch = new_id("bat")
    jobs = []
    try:
        for i, cell in enumerate(CHECK_CELLS):
            for which in ("with", "without"):
                recipe = {"kind": "t2i", "model_id": spec.id, "prompt_mode": "text", "prompt_text": f"{rec.trigger}, {cell_sentence(cell)}.", "width": w, "height": h,
                          "seeds": [1001 + i], "auto_lora": False, "loras": [{"model_id": rec.id, "strength": 1.0}] if which == "with" else []}
                origin = JobOrigin(suite="story", surface="lora_check", ref=rec.profile_id, payload={"lora_id": rec.id, "version": v.id, "which": which, "cell": cell, "group_id": gid})
                jobs += q.submit(recipe, origin=origin, batch_id=batch)
    except ValueError as e:
        raise HTTPException(422, str(e))
    rec.identity = {"status": "running", "model_id": spec.id, "hero_asset_id": v.hero_asset_id, "with": [], "without": [], "n": len(jobs)}
    await asyncio.to_thread(reg.save, rec)
    svc.hub.broadcast("lora.changed", {"id": rec.id, "profile_id": rec.profile_id, "version": rec.version})
    svc.group_changed([gid])
    return {"batch_id": batch, "job_ids": [j.id for j in jobs], "model_id": spec.id, "group_id": gid}


@router.delete("/story/loras/{lid}", response_model=Deleted)
async def lora_delete(svc: Svc, lid: str):
    """The record, the file, the engine's cached copy; every version pointing at it loses its slot (the trigger stays)."""
    ws, _, q = svc.require_project()
    reg = LoraRegistry(ws)
    r = await asyncio.to_thread(reg.get, lid)
    if r is None:
        raise HTTPException(404, "LoRA not found")
    await asyncio.to_thread(reg.delete, lid)
    project_id = (ws.info() or {}).get("id") or ws.path.name
    unpublish(q.roster, Path(svc.app.settings.models_root), project_id, lid)
    for p in await asyncio.to_thread(StoryStore(ws).clear_lora, lid):
        _changed(svc, p)
    svc.hub.broadcast("lora.changed", {"id": lid, "profile_id": r.profile_id, "version": r.version, "deleted": True})
    return {"deleted": lid}


# ---- shots (SY2, 17 §3c) --------------------------------------------------------------------------------------------------------------
class ShotCreate(BaseModel):
    name: str
    stage_id: str | None = None                   # with camera_id: the version is made from this camera (its frame and clip arrive as takes)
    camera_id: str | None = None
    clip_id: str | None = None                    # a clip to start from (Animate's "Make a shot from this clip")
    frame_asset_id: str | None = None


class TakeBody(BaseModel):
    kind: Literal["image", "clip"]
    id: str
    use: bool | None = None                       # make it the frame / clip; None: only when the slot is empty


def _shot_changed(svc, s: Shot) -> None:
    svc.hub.broadcast("story.changed", {"kind": "shot", "id": s.id, "revision": s.revision})


def _check_source(ws, cat, body: ShotCreate) -> int | None:
    """The stage and camera exist (→ the stage's revision), the clip exists, the frame is an image."""
    rev = None
    if (body.stage_id is None) != (body.camera_id is None):
        raise HTTPException(422, "a stage source names both the stage and the camera")
    if body.stage_id:
        st = StageStore(ws).get(body.stage_id)
        if st is None or not any(c.id == body.camera_id for c in st.cameras):
            raise HTTPException(422, "the stage or its camera does not exist")
        rev = st.revision
    if body.clip_id and ClipStore(ws).get(body.clip_id) is None:
        raise HTTPException(422, "the clip does not exist")
    if body.frame_asset_id:
        rec = cat.get(body.frame_asset_id)
        if rec is None or rec.trashed_at is not None or rec.kind != "image":
            raise HTTPException(422, "the frame must be an image in the Catalogue")
    return rev


@router.get("/story/shots", response_model=ShotList)
async def shots_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [s.model_dump() for s in await asyncio.to_thread(StoryStore(ws).shots)]}


@router.post("/story/shots", response_model=Shot)
async def shot_create(svc: Svc, body: ShotCreate):
    ws, cat, _ = svc.require_project()
    rev = await asyncio.to_thread(_check_source, ws, cat, body)
    try:
        s = await asyncio.to_thread(StoryStore(ws).create_shot, body.name, stage_id=body.stage_id, camera_id=body.camera_id, stage_revision=rev,
                                    clip_id=body.clip_id, frame_asset_id=body.frame_asset_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    _shot_changed(svc, s)
    return s.model_dump()


@router.get("/story/shots/{sid}", response_model=Shot)
async def shot_get(svc: Svc, sid: str):
    ws, _, _ = svc.require_project()
    s = await asyncio.to_thread(StoryStore(ws).shot, sid)
    if s is None:
        raise HTTPException(404, "shot not found")
    return s.model_dump()


@router.patch("/story/shots/{sid}", response_model=Shot)
async def shot_patch(svc: Svc, sid: str, body: dict):
    ws, _, _ = svc.require_project()
    try:
        s = await asyncio.to_thread(StoryStore(ws).patch_shot, sid, body)
    except KeyError:
        raise HTTPException(404, "shot not found")
    except StaleShot as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _shot_changed(svc, s)
    return s.model_dump()


@router.delete("/story/shots/{sid}", response_model=Deleted)
async def shot_delete(svc: Svc, sid: str):
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(StoryStore(ws).delete_shot, sid):
        raise HTTPException(404, "shot not found")
    svc.hub.broadcast("story.changed", {"kind": "shot", "id": sid, "revision": 0, "deleted": True})
    return {"deleted": sid}


@router.post("/story/shots/{sid}/versions", response_model=Shot)
async def shot_new_version(svc: Svc, sid: str):
    ws, _, _ = svc.require_project()
    try:
        s = await asyncio.to_thread(StoryStore(ws).new_shot_version, sid)
    except KeyError:
        raise HTTPException(404, "shot not found")
    _shot_changed(svc, s)
    return s.model_dump()


@router.post("/story/shots/{sid}/versions/{vid}/take", response_model=Shot)
async def shot_take(svc: Svc, sid: str, vid: str, body: TakeBody):
    """Record a take (an image or a clip) on an open version; `use` makes it the frame / clip."""
    ws, cat, _ = svc.require_project()
    if body.kind == "clip":
        if await asyncio.to_thread(ClipStore(ws).get, body.id) is None:
            raise HTTPException(422, "the clip does not exist")
    else:
        rec = await asyncio.to_thread(cat.get, body.id)
        if rec is None or rec.trashed_at is not None or rec.kind != "image":
            raise HTTPException(422, "the frame must be an image in the Catalogue")
    store = StoryStore(ws)
    s = await asyncio.to_thread(store.shot, sid)
    if s is None:
        raise HTTPException(404, "shot not found")
    try:
        v = s.version(vid)
        rev = None
        if v.stage_id:
            st = await asyncio.to_thread(StageStore(ws).get, v.stage_id)
            rev = st.revision if st else None
        s = await asyncio.to_thread(store.add_take, sid, vid, body.kind, body.id, use=body.use, stage_revision=rev)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _shot_changed(svc, s)
    return s.model_dump()


class RecipeStepOut(BaseModel):
    id: str
    label: str
    inputs: list[str]
    state: Literal["fresh", "stale", "missing", "planned"]
    reasons: list[str]
    wave: str | None
    experimental: bool
    runs: int
    kind: str | None
    seconds: float | None
    job_id: str | None
    outputs: list[str]
    at: str | None


class RecipeOut(BaseModel):
    shot_id: str
    version: str
    template: str
    label: str
    steps: list[RecipeStepOut]
    stale: int
    stale_seconds: float


class TemplateBody(BaseModel):
    template: str


class PlanStep(BaseModel):
    id: str
    label: str
    how: Literal["server", "passes", "stage", "manual"]
    kind: str | None
    seconds: float | None
    after: list[str]
    reasons: list[str]


class RunStaleBody(BaseModel):
    dry: bool = False                             # the plan and its cost only (the confirm shows it)
    passes: dict[str, str] | None = None          # a stage still's fresh passes (the client rendered them; `how: passes`)


class QueuedStep(BaseModel):
    step: str
    job_ids: list[str]


class RunStaleOut(BaseModel):
    plan: list[PlanStep]
    queued: list[QueuedStep]
    then: list[str]                               # queued by the server when the steps before them finish
    elsewhere: list[str]                          # made again by hand: a stage-guided clip (Animate · Clay), an edit (Image · Edit)
    seconds: float


@router.get("/story/recipe-templates", response_model=list[Template])
async def recipe_templates():
    """RC0 (D96, 05 §3): the shot recipe templates — every step named, the clay pipeline's with the wave that makes them runnable."""
    return [t.model_dump() for t in TEMPLATES.values()]


@router.get("/story/shots/{sid}/recipe", response_model=RecipeOut)
async def shot_recipe(svc: Svc, sid: str, version: str | None = None):
    """RC0 (D96, 05 §4): a shot version's recipe — its steps in the template's order, each fresh, stale (with the reasons), missing or
    planned, with the last run's cost; a step after a stale one is stale."""
    ws, _, _ = svc.require_project()
    store = StoryStore(ws)
    s = await asyncio.to_thread(store.shot, sid)
    if s is None:
        raise HTTPException(404, "shot not found")
    try:
        v = s.version(version)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    reader = StampReader(stages=StageStore(ws), groups=svc.groups, story=store)
    out = await asyncio.to_thread(recipe_state, v, reader)
    return {"shot_id": s.id, "version": v.id, **out}


@router.put("/story/shots/{sid}/versions/{vid}/template", response_model=Shot)
async def shot_template(svc: Svc, sid: str, vid: str, body: TemplateBody):
    ws, _, _ = svc.require_project()
    try:
        s = await asyncio.to_thread(StoryStore(ws).set_template, sid, vid, body.template)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _shot_changed(svc, s)
    return s.model_dump()


@router.post("/story/shots/{sid}/versions/{vid}/run-stale", response_model=RunStaleOut)
async def shot_run_stale(svc: Svc, sid: str, vid: str, body: RunStaleBody):
    """RC0 (D96, 05 §4): *Run stale* — the stale steps in dependency order with their cost; the first ones queued now (their results
    become the version's frame / clip), the server steps after them queued as each finishes. A stage still needs its passes (the client
    renders them and sends them); a stage-guided clip and an edit are made again by hand."""
    ws, _, q = svc.require_project()
    store = StoryStore(ws)
    s = await asyncio.to_thread(store.shot, sid)
    if s is None:
        raise HTTPException(404, "shot not found")
    try:
        v = s.version(vid)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    if v.state != "open":
        raise HTTPException(422, f"{s.name} {v.id} is final — make a new version to run it again")
    plan = await asyncio.to_thread(stale_plan, v, StampReader(stages=StageStore(ws), groups=svc.groups, story=store))
    total = round(sum(p["seconds"] or 0 for p in plan), 1)
    elsewhere = [p["id"] for p in plan if p["how"] in ("stage", "manual")]
    first = [p for p in plan if not p["after"] and (p["how"] == "server" or (p["how"] == "passes" and body.passes))]
    then = [p["id"] for p in plan if p not in first and p["how"] == "server"]
    if body.dry or not first:
        return {"plan": plan, "queued": [], "then": then if first else [], "elsewhere": elsewhere, "seconds": total}
    queued = []
    try:
        for p in first:
            run = used_run(v.recipe.step(p["id"]), v)
            recipe = rerun_recipe(run, v, body.passes if p["how"] == "passes" else None)
            jobs = q.submit(recipe, origin=JobOrigin(suite="animate", surface=FOR_SHOT, ref=None, payload={"shot_id": s.id, "version": v.id, "use": True, "chain": then}))
            queued.append({"step": p["id"], "job_ids": [j.id for j in jobs]})
    except ValueError as e:
        raise HTTPException(422, f"Run stale: {e}")
    await q.flush()
    return {"plan": plan, "queued": queued, "then": then, "elsewhere": elsewhere, "seconds": total}


@router.post("/story/shots/{sid}/versions/{vid}/finalize", response_model=Shot)
async def shot_finalize(svc: Svc, sid: str, vid: str):
    """The version becomes final when its clip is at the project format's size (fps is conformed at export, D27); 422 says why not."""
    ws, _, _ = svc.require_project()
    store = StoryStore(ws)
    s = await asyncio.to_thread(store.shot, sid)
    if s is None:
        raise HTTPException(404, "shot not found")
    try:
        v = s.version(vid)
    except KeyError as e:
        raise HTTPException(404, str(e))
    fmt = ws.load().format
    clip = await asyncio.to_thread(ClipStore(ws).get, v.clip_id) if v.clip_id else None
    why = finalize_reason(v, clip.w if clip else None, clip.h if clip else None, fmt.width, fmt.height)
    if why:
        raise HTTPException(422, why)
    s = await asyncio.to_thread(store.finalize_shot, sid, vid, (clip.w, clip.h) if clip else None, (fmt.width, fmt.height))
    _shot_changed(svc, s)
    return s.model_dump()


# ---- the flow (SY3, 17 §3d) ---------------------------------------------------------------------------------------------------------
class NodeCreate(BaseModel):
    type: str = "dialogue"
    title: str = ""
    x: float = 0.0
    y: float = 0.0
    text: str = ""
    target: str | None = None


class BindBody(BaseModel):
    shot_id: str
    version: str | None = None                    # the current one when absent


class SpawnBody(BaseModel):
    name: str = ""


def _flow_changed(svc, nid: str | None = None) -> None:
    svc.hub.broadcast("story.changed", {"kind": "flow", "id": nid, "revision": 0})


@router.get("/story/flow", response_model=FlowOut)
async def flow_get(svc: Svc):
    ws, _, _ = svc.require_project()
    store = StoryStore(ws)
    nodes = await asyncio.to_thread(store.flow_nodes)
    g = await asyncio.to_thread(store.flow_graph, nodes)
    return {"graph": g.model_dump(by_alias=True), "nodes": [n.model_dump() for n in nodes.values()]}


@router.post("/story/flow/nodes", response_model=FlowNode)
async def flow_node_create(svc: Svc, body: NodeCreate):
    ws, _, _ = svc.require_project()
    if body.type not in NODE_TYPES:
        raise HTTPException(422, f"unknown node type {body.type!r}; one of {', '.join(NODE_TYPES)}")
    n = await asyncio.to_thread(StoryStore(ws).create_node, body.type, body.title, body.x, body.y, text=body.text, target=body.target)
    _flow_changed(svc, n.id)
    return n.model_dump()


@router.patch("/story/flow/nodes/{nid}", response_model=FlowNode)
async def flow_node_patch(svc: Svc, nid: str, body: dict):
    ws, _, _ = svc.require_project()
    board = body.get("board_group_id")
    if board is not None and (not isinstance(board, str) or board not in svc.require_groups().groups):   # D90 (02 §4.2): a board is an album group
        cur = await asyncio.to_thread(StoryStore(ws).flow_node, nid)
        if cur is None or board != cur.board_group_id:                    # a board deleted since stays until it is changed (other saves pass)
            raise HTTPException(422, f"the board {board!r} is not a group of the album")
    place = body.get("place_id")
    if place is not None:                                                  # D93 (C7): where is a Cast place
        p = await asyncio.to_thread(StoryStore(ws).profile, place) if isinstance(place, str) else None
        if p is None or p.cls != "place":
            cur = await asyncio.to_thread(StoryStore(ws).flow_node, nid)
            if cur is None or place != cur.place_id:                       # a place deleted since stays until it is changed
                raise HTTPException(422, f"{place!r} is not a place of the Cast")
    pins = body.get("speaker_versions")
    if pins is not None:                                                   # D93 follow-up: a pin names a character and one of its versions
        if not isinstance(pins, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in pins.items()):
            raise HTTPException(422, "speaker_versions maps a character's profile id to one of its version ids")
        store = StoryStore(ws)
        cur = await asyncio.to_thread(store.flow_node, nid)
        for pid, vid in pins.items():
            if cur is not None and cur.speaker_versions.get(pid) == vid:
                continue                                                   # a pin whose character or version was deleted since stays until changed
            p = await asyncio.to_thread(store.profile, pid)
            if p is None or p.cls != "character" or not any(v.id == vid for v in p.versions):
                raise HTTPException(422, f"{vid!r} is not a version of the character {pid!r}")
    try:
        n = await asyncio.to_thread(StoryStore(ws).patch_node, nid, body)
    except KeyError:
        raise HTTPException(404, "node not found")
    except StaleFlow as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _flow_changed(svc, nid)
    return n.model_dump()


@router.delete("/story/flow/nodes/{nid}", response_model=Deleted)
async def flow_node_delete(svc: Svc, nid: str):
    ws, _, _ = svc.require_project()
    try:
        released = await asyncio.to_thread(StoryStore(ws).delete_node, nid)
    except KeyError:
        raise HTTPException(404, "node not found")
    if released is not None:
        svc.hub.broadcast("story.changed", {"kind": "shot", "id": released.id, "revision": released.revision})
    _flow_changed(svc, nid)
    return {"deleted": nid}


@router.put("/story/flow/graph", response_model=FlowGraph)
async def flow_graph_put(svc: Svc, body: dict):
    ws, _, _ = svc.require_project()
    try:
        g = await asyncio.to_thread(StoryStore(ws).put_graph, body)
    except StaleFlow as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _flow_changed(svc, None)
    return g.model_dump(by_alias=True)


@router.post("/story/flow/nodes/{nid}/bind", response_model=NodeShot)
async def flow_bind(svc: Svc, nid: str, body: BindBody):
    """The node takes the shot as its sole owner (an unbound shot, or a version of its own); 422 when another node owns it."""
    ws, _, _ = svc.require_project()
    try:
        n, sh = await asyncio.to_thread(StoryStore(ws).bind_shot, nid, body.shot_id, body.version)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("story.changed", {"kind": "shot", "id": sh.id, "revision": sh.revision})
    _flow_changed(svc, nid)
    return {"node": n.model_dump(), "shot": sh.model_dump()}


@router.post("/story/flow/nodes/{nid}/unbind", response_model=NodeShot)
async def flow_unbind(svc: Svc, nid: str):
    ws, _, _ = svc.require_project()
    try:
        n, sh = await asyncio.to_thread(StoryStore(ws).unbind_shot, nid)
    except KeyError:
        raise HTTPException(404, "node not found")
    if sh is not None:
        svc.hub.broadcast("story.changed", {"kind": "shot", "id": sh.id, "revision": sh.revision})
    _flow_changed(svc, nid)
    return {"node": n.model_dump(), "shot": sh.model_dump() if sh else None}


@router.post("/story/flow/nodes/{nid}/shot", response_model=NodeShot)
async def flow_spawn(svc: Svc, nid: str, body: SpawnBody):
    """A new, empty shot owned by the node (the handoff to the Shots tab, loom R134)."""
    ws, _, _ = svc.require_project()
    store = StoryStore(ws)
    n = await asyncio.to_thread(store.flow_node, nid)
    if n is None:
        raise HTTPException(404, "node not found")
    try:
        sh = await asyncio.to_thread(store.create_shot, body.name.strip() or n.title or n.type)
        n, sh = await asyncio.to_thread(store.bind_shot, nid, sh.id, None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("story.changed", {"kind": "shot", "id": sh.id, "revision": sh.revision})
    _flow_changed(svc, nid)
    return {"node": n.model_dump(), "shot": sh.model_dump()}


# ---- voices (CN2, 19 §3b, D87) ---------------------------------------------------------------------------------------------------------
class VoiceBody(BaseModel):
    name: str
    tier: Literal["draft", "cloning"] = "draft"
    voice: str | None = None                      # draft: one of /capabilities.voice.draft.voices
    language: str = "English"
    reference_asset_id: str | None = None         # cloning: an audio asset of 3–10 s (a recording, or a draft line)
    reference_text: str = ""                      # cloning: its transcript
    speaker: str = ""                             # cloning: whose voice
    consent: str = ""                             # cloning: the consent note (required)


class VoicePatch(BaseModel):
    name: str | None = None
    voice: str | None = None
    language: str | None = None
    reference_asset_id: str | None = None
    reference_text: str | None = None
    speaker: str | None = None
    consent: str | None = None


class LineVoiceBody(BaseModel):
    voice_id: str | None = None                   # the speaker's voice (the profile's `voice_id`) when absent
    speed: float = Field(1.0, ge=0.5, le=2.0)
    stage: bool = False


def _voice_changed(svc, vid: str) -> None:
    svc.hub.broadcast("story.changed", {"kind": "voice", "id": vid, "revision": 0})


@router.get("/story/voices", response_model=VoiceList)
async def voices_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [r.model_dump() for r in await asyncio.to_thread(VoiceStore(ws).list)]}


@router.post("/story/voices", response_model=VoiceRecordOut)
async def voice_create(svc: Svc, body: VoiceBody):
    """A voice of the project: the draft tier's fixed Kokoro voice, or the cloning tier's reference clip with its transcript and the note
    of whose voice it is and that they consented — 422 with the sentence."""
    ws, cat, _ = svc.require_project()
    rec = VoiceRecord(**body.model_dump())
    ref = await asyncio.to_thread(cat.get, rec.reference_asset_id) if rec.reference_asset_id else None
    try:
        check_voice(rec, ref.model_dump() if ref else None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    await asyncio.to_thread(VoiceStore(ws).save, rec)
    _voice_changed(svc, rec.id)
    return rec.model_dump()


@router.get("/story/voices/{vid}", response_model=VoiceRecordOut)
async def voice_get(svc: Svc, vid: str):
    ws, _, _ = svc.require_project()
    rec = await asyncio.to_thread(VoiceStore(ws).get, vid)
    if rec is None:
        raise HTTPException(404, "voice not found")
    return rec.model_dump()


@router.patch("/story/voices/{vid}", response_model=VoiceRecordOut)
async def voice_patch(svc: Svc, vid: str, body: VoicePatch):
    ws, cat, _ = svc.require_project()
    store = VoiceStore(ws)
    rec = await asyncio.to_thread(store.get, vid)
    if rec is None:
        raise HTTPException(404, "voice not found")
    rec = rec.model_copy(update={**body.model_dump(exclude_none=True), "updated_at": utc_now()})
    ref = await asyncio.to_thread(cat.get, rec.reference_asset_id) if rec.reference_asset_id else None
    try:
        check_voice(rec, ref.model_dump() if ref else None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    await asyncio.to_thread(store.save, rec)
    _voice_changed(svc, vid)
    return rec.model_dump()


@router.delete("/story/voices/{vid}", response_model=Deleted)
async def voice_delete(svc: Svc, vid: str):
    """The record goes (its spoken lines stay in the Catalogue); every profile that had it loses its voice."""
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(VoiceStore(ws).delete, vid):
        raise HTTPException(404, "voice not found")
    for p in await asyncio.to_thread(StoryStore(ws).clear_voice, vid):
        _changed(svc, p)
    _voice_changed(svc, vid)
    return {"deleted": vid}


def _voice_jobs(ws, q, store: StoryStore, n: FlowNode, indexes: list[int], body: LineVoiceBody, picked: bool) -> dict:
    """One `tts` job per voice: a line's voice is its speaker's (the profile's `voice_id`), the body's standing in where the speaker has
    none — or, `picked` (one line, chosen by hand), the body's first; a line with neither is the sentence. The job's result lands on
    the lines (`audio_asset_id`) as audio assets."""
    voices = VoiceStore(ws)
    profiles = {p.id: p for p in store.profiles()}
    groups: dict[str, list[dict]] = {}
    missing: list[int] = []
    for i in indexes:
        ln = n.lines[i]
        if not ln.text.strip():
            continue
        own = profiles[ln.speaker].voice_id if ln.speaker in profiles else None
        vid = (body.voice_id or own) if picked else (own or body.voice_id)
        if not vid:
            missing.append(i + 1)
            continue
        groups.setdefault(vid, []).append({"text": ln.text.strip(), "node_id": n.id, "index": i})
    if missing:
        raise HTTPException(422, f"line{'s' if len(missing) > 1 else ''} {', '.join(map(str, missing))}: no voice — give the speaker one in Cast, or pick one here")
    if not groups:
        raise HTTPException(422, "nothing to say: the lines are empty")
    jobs = []
    for vid, items in groups.items():
        rec = voices.get(vid)
        if rec is None:
            raise HTTPException(422, f"unknown voice {vid!r}")
        recipe = {"kind": "tts", "voice_id": vid, "tier": rec.tier, "language": rec.language, "speed": body.speed, "items": items}
        origin = JobOrigin(suite="story", surface="voice", ref=n.id, payload={"indexes": [it["index"] for it in items], "voice_id": vid})
        try:
            jobs.append(q.submit(recipe, stage=body.stage, origin=origin)[0])
        except ValueError as e:
            raise HTTPException(422, str(e))
    return {"job_ids": [j.id for j in jobs], "lines": sum(len(v) for v in groups.values()), "voice_ids": list(groups), "staged": all(j.status == "staged" for j in jobs)}


@router.post("/story/flow/nodes/{nid}/lines/{i}/voice", response_model=TtsQueued)
async def line_voice(svc: Svc, nid: str, i: int, body: LineVoiceBody):
    """CN2 (19 §3b): one line spoken — a `tts` job (the draft tier on the CPU beside the engine, the cloning tier with it stopped) whose
    result lands on the line as an audio asset."""
    ws, _, q = svc.require_project()
    store = StoryStore(ws)
    n = await asyncio.to_thread(store.flow_node, nid)
    if n is None:
        raise HTTPException(404, "node not found")
    if not 0 <= i < len(n.lines):
        raise HTTPException(404, f"the node has no line {i}")
    return await asyncio.to_thread(_voice_jobs, ws, q, store, n, [i], body, True)


@router.post("/story/flow/nodes/{nid}/voice", response_model=TtsQueued)
async def node_voice(svc: Svc, nid: str, body: LineVoiceBody):
    """Every non-empty line of the node, grouped by voice (each speaker's own; the body's as the fallback) — one job per voice."""
    ws, _, q = svc.require_project()
    store = StoryStore(ws)
    n = await asyncio.to_thread(store.flow_node, nid)
    if n is None:
        raise HTTPException(404, "node not found")
    return await asyncio.to_thread(_voice_jobs, ws, q, store, n, list(range(len(n.lines))), body, False)


# ---- lip-sync (D88 XL, experimental) ---------------------------------------------------------------------------------------------------
class LipsyncBody(BaseModel):
    node_id: str | None = None                    # a voiced Flow line: the node and the line's index …
    index: int | None = None
    audio_asset_id: str | None = None             # … or an audio asset directly
    image_asset_id: str | None = None             # the face; the version's frame when absent
    preset: Literal["draft", "fast"] = "draft"
    prompt_text: str = "the character speaks the line to the camera, calm, natural head motion, steady camera, soft light"
    stage: bool = True                            # ≈ 9–16 min: staged by default (an overnight job)


@router.post("/story/shots/{sid}/versions/{vid}/lipsync", response_model=LipsyncQueued)
async def shot_lipsync(svc: Svc, sid: str, vid: str, body: LipsyncBody):
    """D88 XL (experimental): a talking clip of the version's frame (or any image) speaking a voiced line — one window (≤ 4.8 s at 16 fps),
    English only (E18); it lands as a take on the version. 422 with the sentence."""
    import math
    from ..models import registry
    ws, cat, q = svc.require_project()
    store = StoryStore(ws)
    sh = await asyncio.to_thread(store.shot, sid)
    if sh is None:
        raise HTTPException(404, "shot not found")
    v = next((x for x in sh.versions if x.id == vid), None)
    if v is None:
        raise HTTPException(404, f"the shot has no version {vid}")
    audio_id = body.audio_asset_id
    if audio_id is None and body.node_id is not None:
        n = await asyncio.to_thread(store.flow_node, body.node_id)
        if n is None or body.index is None or not 0 <= body.index < len(n.lines):
            raise HTTPException(404, "that line is not in the flow")
        audio_id = n.lines[body.index].audio_asset_id
        if not audio_id:
            raise HTTPException(422, "the line has no voice yet — voice it in the Flow (🎙) first")
    if not audio_id:
        raise HTTPException(422, "name a voiced line (node and index) or an audio asset")
    image_id = body.image_asset_id or v.frame_asset_id
    if not image_id:
        raise HTTPException(422, "the version has no frame — give it one (or name an image)")
    spec = next((s for s in registry.lipsync_specs()), None)
    if spec is None:
        raise HTTPException(422, "no lip-sync model in this build")
    a = await asyncio.to_thread(cat.get, audio_id)
    img = await asyncio.to_thread(cat.get, image_id)
    if img is None:
        raise HTTPException(422, f"the image {image_id} is not in the Catalogue")
    fps, cap = int(spec.geometry.fps or 16), int(spec.geometry.frames or 77)
    secs = float(a.duration_s or 0) if a else 0.0
    frames = min(cap, 4 * math.ceil(max(1.0, secs * fps - 1) / 4) + 1)
    w, h = (spec.geometry.size or [832, 480])[:2]
    recipe = {"kind": "i2v", "model_id": spec.id, "start_asset": image_id, "prompt_text": body.prompt_text, "frames": frames, "fps": fps, "width": w, "height": h,
              "preset": body.preset, "audio": {"asset_id": audio_id}}
    origin = JobOrigin(suite="story", surface="lipsync", ref=sid, payload={"version": vid, "node_id": body.node_id, "index": body.index})
    try:
        job = q.submit(recipe, stage=body.stage, origin=origin)[0]
    except ValueError as e:
        raise HTTPException(422, str(e))
    p = spec.video.presets.get(body.preset) if spec.video else None
    return {"job_id": job.id, "model_id": spec.id, "frames": frames, "audio_asset_id": audio_id, "image_asset_id": image_id, "staged": job.status == "staged",
            "seconds": p.seconds if p else None}


@router.post("/story/flow/validate", response_model=FlowProblems)
async def flow_validate(svc: Svc):
    ws, _, _ = svc.require_project()
    store = StoryStore(ws)
    nodes = await asyncio.to_thread(store.flow_nodes)
    g = await asyncio.to_thread(store.flow_graph, nodes)
    world = await asyncio.to_thread(store.world)
    shots = {s.id: s for s in await asyncio.to_thread(store.shots)}
    return {"problems": validate_flow(g, nodes, [v.name for v in world.variables], shots)}
