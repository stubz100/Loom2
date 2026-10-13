"""Story (17 §7, D85): the workspace's records — SY0: the world (read, replace with a revision guard). Profiles, shots and the flow join here."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ..story import StaleWorld, StoryStore, World
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
