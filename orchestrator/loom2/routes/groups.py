"""Album pages (D34, proto01_design/01 §6c, §8): the group tree, pages with free item layout, move / group / ungroup / duplicate.

Order matters: `/groups/tree`, `/groups/where`, `/groups/used-by` and `/groups/move` are registered before `/groups/{gid}`.
"""
from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..catalogue import AssetKind, AssetRecord

from ..groups import ROOT_ID, GroupRecord
from ..schemas import AlbumNode, ChangedGroups, GroupDeleted, GroupPage, LayoutReply, Location, Ungrouped
from ..usedby import GroupUser, users_of
from .deps import Svc

router = APIRouter(tags=["groups"])


class ItemRef(BaseModel):
    kind: Literal["asset", "group"]
    id: str


class GroupCreate(BaseModel):
    name: str
    parent_id: str = ROOT_ID
    x: float | None = None
    y: float | None = None


class GroupPatch(BaseModel):
    name: str | None = None
    cover_id: str | None = None


class GroupLayoutItem(BaseModel):
    """V8: one item's place on the page — typed, so a bad value is a 422, not a 500 from `layout()`'s casts."""
    kind: Literal["asset", "group"]
    id: str
    x: float | None = None
    y: float | None = None
    w: float | None = Field(None, ge=1.0)
    z: int | None = None


class GroupLayout(BaseModel):
    items: list[GroupLayoutItem]
    revision: int | None = None


class GroupMove(BaseModel):
    items: list[ItemRef]
    to: str | None = None                     # a group id, or None = back to Unprocessed (assets only)
    positions: list[dict] | None = None


class GroupMake(BaseModel):
    items: list[ItemRef]
    name: str = "Group"


@router.get("/groups/tree", response_model=AlbumNode)
async def groups_tree(svc: Svc):
    return await asyncio.to_thread(svc.require_groups().tree)


@router.get("/groups/where", response_model=dict[str, Location | None])
async def groups_where(svc: Svc, ids: Annotated[list[str], Query()]):
    return await asyncio.to_thread(svc.require_groups().where, ids)


@router.get("/groups/used-by", response_model=dict[str, list[GroupUser]])
async def groups_used_by(svc: Svc, ids: Annotated[list[str] | None, Query()] = None, deep: bool = False):
    """D92 §4.2: what uses each group (a Cast version's references or candidates, a style, a Flow board, a Stage page, a library entry) —
    computed from the records, nothing stored; no `ids` = every used group; `deep` adds the groups inside (a delete's confirm)."""
    ws, _, _ = svc.require_project()
    return await asyncio.to_thread(users_of, ws, svc.require_groups(), ids, deep)


class HomeAsk(BaseModel):
    path: Literal["world/look", "world/sketches", "imports"] = Field(description="U2 (D157, G1): a named home of the Bin; an entity's, a shot's or a cut's comes with its record")


@router.post("/bin/homes", response_model=GroupRecord)
async def bin_home(svc: Svc, body: HomeAsk):
    """U2 (G1): a named home of the Bin, made with its parents when missing (the Look's style samples go in `world/look`)."""
    from ..bins import home
    groups = svc.require_groups()
    g = await asyncio.to_thread(home, groups, body.path)
    svc.group_changed([g.id])
    return g.model_dump()


class BinNode(BaseModel):
    """U8 (05 §2.1): a home in the Bin's tree — its own things and its role pages' (`count`), with the homes under it (`total`)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    path: str
    name: str
    count: int
    total: int
    pages: list[str] = Field(default_factory=list)   # its role pages (a version's reference set and candidates): a page id → this home
    gone: bool = False                               # B0 (R5): its record (an entity, a shot, a cut) was deleted; its things are still here
    children: list[BinNode] = Field(default_factory=list)


class BinTree(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    homes: list[BinNode]
    trash: int


class BinThing(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    asset: AssetRecord
    roles: list[str] = Field(default_factory=list)   # hero, reference, a_pose_front, a_pose_back, set_picture, model, candidate, final, frame, clip …
    home_id: str | None = None
    path: str = ""                                   # its home's path (`imports` for a thing on no page)


class BinThings(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    home_id: str | None = None
    path: str = ""
    items: list[BinThing]
    total: int | None = None                         # B0: with the first page of a home
    next_cursor: str | None = None                   # B0: the next page, None at the end


class BinUse(BaseModel):
    """B1 (D159): a record that names a thing — `kind` version (an entity's), shot or stage — with the role it gives it."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: Literal["version", "shot", "stage"]
    id: str
    version: str | None = None
    name: str
    role: str


class BinMove(BaseModel):
    ids: list[str] = Field(min_length=1)
    to: str = Field(description="the home (or a page inside it) the things go to")
    confirm: bool = Field(False, description="B0 (D159 Q5): move the things that lose a role too, the record letting go of them")


class BinRole(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    roles: list[str] = Field(default_factory=list)
    role: str = ""
    home: str
    why: str = ""


class BinMoved(BaseModel):
    """B0 (D159 Q5): what moved; what would lose a role in its home (`ask`: moved only when confirmed); what stays (`refused`: a job's
    record is made on it, or its version is final); the roles the records let go of."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    moved: list[str]
    ask: list[BinRole]
    refused: list[BinRole]
    dropped: list[BinRole]


class BinRehomed(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    moved: int
    to: str


@router.get("/bin/tree", response_model=BinTree)
async def bin_tree(svc: Svc):
    """U8 (D157, 05 §2.1): the Bin's tree of homes with their counts (`imports` holds the things on no page), and the Trash's count."""
    from ..bins import home, tree
    ws, _, _ = svc.require_project()
    groups = svc.require_groups()
    await asyncio.to_thread(home, groups, "imports")
    return await asyncio.to_thread(tree, groups, ws)


@router.get("/bin/homes/{gid}/items", response_model=BinThings)
async def bin_home_items(svc: Svc, gid: str, cursor: str | None = None, limit: int = Query(200, ge=1, le=2000),
                         kinds: list[AssetKind] = Query(default_factory=list)):
    """U8 (05 §2.2): a home's things and everything below it, newest first, each with its roles and its home — B0: a page at a time
    (`cursor` from the last page's `next_cursor`), `kinds` keeping those kinds only."""
    from ..bins import home_page
    ws, _, _ = svc.require_project()
    try:
        return await asyncio.to_thread(home_page, svc.require_groups(), ws, gid, cursor, limit, list(kinds))
    except KeyError:
        raise HTTPException(404, "no such home")


@router.get("/bin/things/{aid}", response_model=BinThing)
async def bin_thing(svc: Svc, aid: str):
    """B1 (D159): one thing with its home and its roles there (the Bin opens it in its home, selected)."""
    from ..bins import thing
    ws, _, _ = svc.require_project()
    out = await asyncio.to_thread(thing, svc.require_groups(), ws, aid)
    if out is None:
        raise HTTPException(404, "no such thing")
    return out


@router.get("/bin/things/{aid}/uses", response_model=list[BinUse])
async def bin_thing_uses(svc: Svc, aid: str):
    """B1 (D159, 11 §3): what uses a thing — an entity version, a shot version, a stage — and the role each gives it."""
    from ..bins import uses_of
    ws, _, _ = svc.require_project()
    return await asyncio.to_thread(uses_of, ws, aid)


@router.post("/bin/move", response_model=BinMoved)
async def bin_move(svc: Svc, body: BinMove):
    """B0 (D159 Q5, R6): things moved to another home; a role they would lose is asked first (`ask`), a role a record is made on refused."""
    from ..bins import move_things
    ws, _, _ = svc.require_project()
    try:
        out = await asyncio.to_thread(move_things, svc.require_groups(), ws, body.ids, body.to, body.confirm)
    except KeyError:
        raise HTTPException(404, "no such home")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if out["changed"]:
        svc.group_changed(out["changed"])
    for rid in out["records"]:
        svc.hub.broadcast("story.changed", {"kind": "profile" if rid.startswith("prf_") else "shot", "id": rid, "revision": 0})
    return out


@router.post("/bin/homes/{gid}/rehome", response_model=BinRehomed)
async def bin_rehome(svc: Svc, gid: str):
    """B0 (R5): a home whose record was deleted gives its things to the Sketches and goes."""
    from ..bins import rehome
    try:
        out = await asyncio.to_thread(rehome, svc.require_groups(), gid)
    except KeyError:
        raise HTTPException(404, "no such home")
    svc.group_changed(out["changed"])
    return out


@router.get("/bin/search", response_model=BinThings)
async def bin_search(svc: Svc, q: str = ""):
    """U8 (05 §2.2): a search across every home — the prompt, the name, the tags, a seed — each thing with its home."""
    from ..bins import search
    return await asyncio.to_thread(search, svc.require_groups(), q)


@router.post("/groups", response_model=GroupRecord)
async def groups_create(svc: Svc, body: GroupCreate):
    g = await asyncio.to_thread(svc.require_groups().create, body.name, body.parent_id, body.x, body.y)
    svc.group_changed([g.id, body.parent_id])
    return g.model_dump()


@router.post("/groups/move", response_model=ChangedGroups)
async def groups_move(svc: Svc, body: GroupMove):
    changed = await asyncio.to_thread(svc.require_groups().move, [(i.kind, i.id) for i in body.items], body.to, body.positions)
    svc.group_changed(changed)
    return {"changed": sorted(changed)}


@router.get("/groups/{gid}", response_model=GroupPage)
async def groups_page(svc: Svc, gid: str):
    return await asyncio.to_thread(svc.require_groups().page, gid)


@router.patch("/groups/{gid}", response_model=GroupRecord)
async def groups_patch(svc: Svc, gid: str, body: GroupPatch):
    g = await asyncio.to_thread(svc.require_groups().update, gid, body.name, body.cover_id)
    svc.group_changed([gid])
    return g.model_dump()


@router.delete("/groups/{gid}", response_model=GroupDeleted)
async def groups_delete(svc: Svc, gid: str):
    st = svc.require_groups()
    parent = st.parent.get(("group", gid), ROOT_ID)
    freed = await asyncio.to_thread(st.delete, gid)
    svc.group_changed([gid, parent])
    return {"deleted": gid, "unprocessed": freed}


@router.patch("/groups/{gid}/items", response_model=LayoutReply)
async def groups_layout(svc: Svc, gid: str, body: GroupLayout):
    g = await asyncio.to_thread(svc.require_groups().layout, gid, [it.model_dump(exclude_none=True) for it in body.items], body.revision)
    svc.group_changed([gid])
    return {"revision": g.revision}


@router.post("/groups/{gid}/group", response_model=GroupRecord)
async def groups_make(svc: Svc, gid: str, body: GroupMake):
    g = await asyncio.to_thread(svc.require_groups().group_items, gid, [(i.kind, i.id) for i in body.items], body.name)
    svc.group_changed([gid, g.id])
    return g.model_dump()


@router.post("/groups/{gid}/ungroup", response_model=Ungrouped)
async def groups_ungroup(svc: Svc, gid: str):
    parent = await asyncio.to_thread(svc.require_groups().ungroup, gid)
    svc.group_changed([gid, parent])
    return {"parent": parent}


@router.post("/groups/{gid}/duplicate", response_model=GroupRecord)
async def groups_duplicate(svc: Svc, gid: str):
    st = svc.require_groups()
    g = await asyncio.to_thread(st.duplicate_group, gid)
    svc.group_changed([g.id, st.parent.get(("group", g.id), ROOT_ID)])
    for aid in await asyncio.to_thread(st._asset_ids, g.id):
        if (rec := await asyncio.to_thread(svc.catalogue.get, aid)) is not None:
            svc.hub.broadcast("asset.created", rec.model_dump())
    return g.model_dump()
