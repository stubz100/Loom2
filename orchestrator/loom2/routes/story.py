"""Story (17 §7, D85): the workspace's records — SY0: the world (read, replace with a revision guard); SY1: profiles with versions (create
from a hero image, patch, copy, lock, delete), curation (keep → the reference set, reject) and Expand (one T2I job per coverage cell in one
batch, the results placed on the version's candidates page); SY2: shots with versions (from a stage camera and / or a clip; takes; the
finalize gate = the project format's size); SY3: the flow (one file per node, the index of positions, edges and the start; bind /
spawn a shot as a node's sole property; validation as a list)."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..fsio import new_id
from ..origin import JobOrigin
from ..clips import ClipStore
from ..schemas import Curated, Deleted, Expanded, FlowOut, FlowProblems, NodeShot, ProfileList, ShotList
from ..stages import StageStore
from ..story import NODE_TYPES, PRESETS, FlowGraph, FlowNode, Profile, ProfileClass, Shot, StaleFlow, StaleProfile, StaleShot, StaleWorld, StoryStore, World, expand_spec, finalize_reason, plan_expand, validate_flow
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


@router.post("/story/flow/validate", response_model=FlowProblems)
async def flow_validate(svc: Svc):
    ws, _, _ = svc.require_project()
    store = StoryStore(ws)
    nodes = await asyncio.to_thread(store.flow_nodes)
    g = await asyncio.to_thread(store.flow_graph, nodes)
    world = await asyncio.to_thread(store.world)
    shots = {s.id: s for s in await asyncio.to_thread(store.shots)}
    return {"problems": validate_flow(g, nodes, [v.name for v in world.variables], shots)}
