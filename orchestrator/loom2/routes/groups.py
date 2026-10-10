"""Album pages (D34, proto01_design/01 §6c, §8): the group tree, pages with free item layout, move / group / ungroup / duplicate.

Order matters: `/groups/tree`, `/groups/where` and `/groups/move` are registered before `/groups/{gid}`.
"""
from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..groups import ROOT_ID
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


class GroupLayout(BaseModel):
    items: list[dict]
    revision: int | None = None


class GroupMove(BaseModel):
    items: list[ItemRef]
    to: str | None = None                     # a group id, or None = back to Unprocessed (assets only)
    positions: list[dict] | None = None


class GroupMake(BaseModel):
    items: list[ItemRef]
    name: str = "Group"


@router.get("/groups/tree")
async def groups_tree(svc: Svc):
    return await asyncio.to_thread(svc.require_groups().tree)


@router.get("/groups/where")
async def groups_where(svc: Svc, ids: Annotated[list[str], Query()]):
    return await asyncio.to_thread(svc.require_groups().where, ids)


@router.post("/groups")
async def groups_create(svc: Svc, body: GroupCreate):
    g = await asyncio.to_thread(svc.require_groups().create, body.name, body.parent_id, body.x, body.y)
    svc.group_changed([g.id, body.parent_id])
    return g.model_dump()


@router.post("/groups/move")
async def groups_move(svc: Svc, body: GroupMove):
    changed = await asyncio.to_thread(svc.require_groups().move, [(i.kind, i.id) for i in body.items], body.to, body.positions)
    svc.group_changed(changed)
    return {"changed": sorted(changed)}


@router.get("/groups/{gid}")
async def groups_page(svc: Svc, gid: str):
    return await asyncio.to_thread(svc.require_groups().page, gid)


@router.patch("/groups/{gid}")
async def groups_patch(svc: Svc, gid: str, body: GroupPatch):
    g = await asyncio.to_thread(svc.require_groups().update, gid, body.name, body.cover_id)
    svc.group_changed([gid])
    return g.model_dump()


@router.delete("/groups/{gid}")
async def groups_delete(svc: Svc, gid: str):
    st = svc.require_groups()
    parent = st.parent.get(("group", gid), ROOT_ID)
    freed = await asyncio.to_thread(st.delete, gid)
    svc.group_changed([gid, parent])
    return {"deleted": gid, "unprocessed": freed}


@router.patch("/groups/{gid}/items")
async def groups_layout(svc: Svc, gid: str, body: GroupLayout):
    g = await asyncio.to_thread(svc.require_groups().layout, gid, body.items, body.revision)
    svc.group_changed([gid])
    return {"revision": g.revision}


@router.post("/groups/{gid}/group")
async def groups_make(svc: Svc, gid: str, body: GroupMake):
    g = await asyncio.to_thread(svc.require_groups().group_items, gid, [(i.kind, i.id) for i in body.items], body.name)
    svc.group_changed([gid, g.id])
    return g.model_dump()


@router.post("/groups/{gid}/ungroup")
async def groups_ungroup(svc: Svc, gid: str):
    parent = await asyncio.to_thread(svc.require_groups().ungroup, gid)
    svc.group_changed([gid, parent])
    return {"parent": parent}


@router.post("/groups/{gid}/duplicate")
async def groups_duplicate(svc: Svc, gid: str):
    st = svc.require_groups()
    g = await asyncio.to_thread(st.duplicate_group, gid)
    svc.group_changed([g.id, st.parent.get(("group", g.id), ROOT_ID)])
    for aid in await asyncio.to_thread(st._asset_ids, g.id):
        if (rec := await asyncio.to_thread(svc.catalogue.get, aid)) is not None:
            svc.hub.broadcast("asset.created", rec.model_dump())
    return g.model_dump()
