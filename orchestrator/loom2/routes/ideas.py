"""proto01_UIcast CW1–CW2 (D136 U1–U4; 06 §2.1–2.2): Cast's ideas — their own store (`ideas.py`), the board's routes: list, make (from a
picture: *Prototype ▸*, copied, U2; named from its prompt when no name is given, U3), patch, delete; a variant added or removed;
*Make the clay ▶* on a character's variant (the A-pose picture, the fit, the shell — queued one after another); *Keep ▶* (a new Cast
profile or a new version of one)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..body import Body

from ..ideas import ClayStep, Idea, IdeaClass, IdeaStore, StaleIdea, keep, plan_clay, start_step
from ..schemas import Deleted
from ..story import Profile
from .deps import Svc

router = APIRouter(tags=["ideas"])


class IdeaList(BaseModel):
    items: list[Idea]


class IdeaCreate(BaseModel):
    cls: IdeaClass = "character"
    asset_id: str | None = None                   # the picture *Prototype ▸* starts it from (copied onto the idea's page)
    name: str | None = Field(None, max_length=80)  # None: read from the picture's prompt (U3)
    note: str = Field("", max_length=1000)


class VariantAdd(BaseModel):
    asset_id: str


class ClayIn(BaseModel):
    """CW3: what a free object in Clay is, as a variant's clay."""
    kind: Literal["figure", "model"]
    body: Body | None = None
    shell_asset_id: str | None = None
    model_asset_id: str | None = None
    height_m: float | None = Field(None, gt=0.0, le=100.0)


class IdeaFromClay(BaseModel):
    cls: IdeaClass
    name: str = Field(..., min_length=1, max_length=80)
    blob: str = Field(..., pattern=r"^[0-9a-f]{64}$")   # Clay's view of it, a PNG uploaded first (PUT /blobs/{sha})
    clay: ClayIn


class ClayQueued(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    job_id: str
    idea: Idea


class KeepBody(BaseModel):
    variant_id: str
    profile_id: str | None = None                 # a new version of this Cast profile; None: a new profile (v1)
    name: str | None = Field(None, max_length=80)  # a new profile's name (the idea's by default)


class Kept(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    profile: Profile
    idea: Idea


def _changed(svc, idea: Idea, **extra) -> None:
    svc.hub.broadcast("story.changed", {"kind": "idea", "id": idea.id, "revision": idea.revision, **extra})


@router.get("/story/ideas", response_model=IdeaList)
async def ideas_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [i.model_dump() for i in await asyncio.to_thread(IdeaStore(ws).list)]}


@router.post("/story/ideas", response_model=Idea)
async def idea_create(svc: Svc, body: IdeaCreate):
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    try:
        idea = await asyncio.to_thread(IdeaStore(ws).create, body.cls, groups, body.asset_id, body.name, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.group_changed([idea.group_id])
    _changed(svc, idea)
    return idea.model_dump()


@router.post("/story/ideas/from-clay", response_model=Idea)
async def idea_from_clay(svc: Svc, body: IdeaFromClay):
    """CW3 (06 §2.7): *Prototype ▸* on a free figure or mesh in Clay — a new idea whose first variant is Clay's view of it (a picture made
    for it, on the idea's page) and whose clay is the object: a figure's body and shell, or a mesh's model and height."""
    from ..origin import JobOrigin
    ws, cat, _ = svc.require_project()
    groups = svc.require_groups()
    p = ws.temp_dir / "blobs" / body.blob
    if not p.is_file():
        raise HTTPException(422, f"blob {body.blob[:12]}… was not uploaded (PUT /blobs/{{sha}} first)")
    if (body.cls == "character") != (body.clay.kind == "figure"):
        raise HTTPException(422, "a figure is a character idea, a model a prop idea")
    parents = [x for x in (body.clay.model_asset_id, body.clay.shell_asset_id) if x]
    rec = await asyncio.to_thread(cat.ingest_file, p, kind="image", move=False, suite="stage", lineage_kind="clay-view", parents=parents,
                                  origin=JobOrigin(suite="stage", surface="prototype", ref=None, payload=None), params={"view": "clay"})
    store = IdeaStore(ws)
    try:
        idea = await asyncio.to_thread(store.create, body.cls, groups, rec.id, body.name, "", True)
        idea = await asyncio.to_thread(store.set_clay, idea.id, idea.variants[0].id, kind=body.clay.kind, step="done",
                                       body=body.clay.body.model_dump() if body.clay.body else None, shell_asset_id=body.clay.shell_asset_id,
                                       model_asset_id=body.clay.model_asset_id, height_m=body.clay.height_m, job_id=None, error=None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.group_changed([idea.group_id])
    _changed(svc, idea)
    return idea.model_dump()


@router.get("/story/ideas/{iid}", response_model=Idea)
async def idea_get(svc: Svc, iid: str):
    ws, _, _ = svc.require_project()
    idea = await asyncio.to_thread(IdeaStore(ws).get, iid)
    if idea is None:
        raise HTTPException(404, "idea not found")
    return idea.model_dump()


@router.patch("/story/ideas/{iid}", response_model=Idea)
async def idea_patch(svc: Svc, iid: str, body: dict):
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    try:
        idea = await asyncio.to_thread(IdeaStore(ws).patch, iid, body, groups)
    except KeyError as e:
        raise HTTPException(404, f"no idea or variant {e.args[0]!r}")
    except StaleIdea as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    if "name" in body:
        svc.group_changed([idea.group_id])
    _changed(svc, idea)
    return idea.model_dump()


@router.delete("/story/ideas/{iid}", response_model=Deleted)
async def idea_delete(svc: Svc, iid: str):
    """The idea goes; its page and pictures stay in the album (as a deleted profile's do)."""
    ws, _, _ = svc.require_project()
    try:
        idea = await asyncio.to_thread(IdeaStore(ws).delete, iid)
    except KeyError:
        raise HTTPException(404, "idea not found")
    svc.hub.broadcast("story.changed", {"kind": "idea", "id": iid, "revision": idea.revision + 1, "deleted": True})
    return {"deleted": iid}


@router.post("/story/ideas/{iid}/variants", response_model=Idea)
async def idea_variant_add(svc: Svc, iid: str, body: VariantAdd):
    """*Add to ‹idea›* (*Prototype ▸*), *Add as a variant* (CW2), a picture dropped on its card: a copy on the idea's page, in focus."""
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    try:
        idea, _ = await asyncio.to_thread(IdeaStore(ws).add_variant, iid, body.asset_id, groups)
    except KeyError:
        raise HTTPException(404, "idea not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.group_changed([idea.group_id])
    _changed(svc, idea)
    return idea.model_dump()


@router.delete("/story/ideas/{iid}/variants/{vid}", response_model=Idea)
async def idea_variant_remove(svc: Svc, iid: str, vid: str):
    ws, _, _ = svc.require_project()
    try:
        idea = await asyncio.to_thread(IdeaStore(ws).remove_variant, iid, vid)
    except KeyError as e:
        raise HTTPException(404, f"no idea or variant {e.args[0]!r}")
    _changed(svc, idea)
    return idea.model_dump()


@router.post("/story/ideas/{iid}/variants/{vid}/clay", response_model=ClayQueued)
async def idea_variant_clay(svc: Svc, iid: str, vid: str):
    """*Make the clay ▶* (06 §2.3): a character variant's figure — an A-pose picture drawn from it (about a minute), the body fitted to it —
    and then its shell (Pixal3D, about four minutes, full only), queued one after another; the variant's clay follows each step."""
    ws, _, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = IdeaStore(ws)
    idea = await asyncio.to_thread(store.get, iid)
    if idea is None:
        raise HTTPException(404, "idea not found")
    try:
        v = idea.variant(vid)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    if v.clay is not None and v.clay.step in ("drawing", "fitting", "shell") and svc.queue.job_live(v.clay.job_id):   # V21: a job gone or over is not busy
        raise HTTPException(409, "the clay is being made — wait for it, or cancel its job in the Dock")
    fmt = ws.load().format
    h = 720
    w = max(64, round(h * fmt.width / fmt.height / 16) * 16)
    try:
        recipe, origin = plan_clay(idea, v, svc.app.settings.variant, width=w, height=h)
        job = await start_step(svc.queue, ClayStep(iid, vid, recipe, origin, {"step": "drawing", "anim_ref_asset_id": None, "body": None, "body_points": None,
                                                                             "note": None, "shell_asset_id": None}))   # V22 / V30: staged until the marker is written
    except ValueError as e:
        raise HTTPException(422, str(e))
    idea = await asyncio.to_thread(store.get, iid)
    await svc.queue.flush()
    _changed(svc, idea)
    return {"job_id": job.id, "idea": idea.model_dump()}


@router.post("/story/ideas/{iid}/keep", response_model=Kept)
async def idea_keep(svc: Svc, iid: str, body: KeepBody):
    """*Keep ▶*: a variant becomes a Cast profile (v1) or a new version of one — the hero, a sheet drafted from its prompt, its clay."""
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    try:
        p, idea = await asyncio.to_thread(keep, ws, groups, iid, body.variant_id, body.profile_id, body.name)
    except KeyError as e:
        raise HTTPException(404, f"no idea, variant or profile {e.args[0]!r}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.group_changed([v.group_id for v in p.versions])
    svc.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    _changed(svc, idea)
    return {"profile": p.model_dump(), "idea": idea.model_dump()}
