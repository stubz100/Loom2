"""Stages (P13 / ST1, 16 §12): the 3D blocking documents — list, create (one camera, the project's size and fps), read, replace
(409 on a stale revision), delete. Passes upload (ST3) and shots (ST4) join here."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..fsio import atomic_write_json, read_json_or
from ..schemas import Deleted, StageList
from ..stages import Stage, StageStore, StaleStage
from .deps import Svc

router = APIRouter(tags=["stages"])


class StageCreate(BaseModel):
    name: str = "Stage"


@router.get("/stages", response_model=StageList)
async def stages_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [s.model_dump() for s in await asyncio.to_thread(StageStore(ws).list)]}


@router.post("/stages", response_model=Stage)
async def stage_create(svc: Svc, body: StageCreate):
    ws, _, _ = svc.require_project()
    fmt = ws.load().format
    st = await asyncio.to_thread(StageStore(ws).create, body.name, {"w": fmt.width, "h": fmt.height, "fps": fmt.fps})
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


class PoseLibrary(BaseModel):
    """ST2: the project's saved poses — name → {preset?, joints {joint: [x, y, z] degrees}} — kept as `stages/poses.json`."""
    poses: dict[str, dict] = {}


@router.get("/stages/poses", response_model=PoseLibrary)
async def poses_get(svc: Svc):
    ws, _, _ = svc.require_project()
    p = ws.stages_dir / "poses.json"
    return await asyncio.to_thread(lambda: read_json_or(p, {"poses": {}}))


@router.put("/stages/poses", response_model=PoseLibrary)
async def poses_put(svc: Svc, body: PoseLibrary):
    ws, _, _ = svc.require_project()
    for name, pose in body.poses.items():
        joints = pose.get("joints", {}) if isinstance(pose, dict) else None
        if not name.strip() or not isinstance(joints, dict) or any(not (isinstance(v, list) and len(v) == 3) for v in joints.values()):
            raise HTTPException(422, f"pose {name!r}: joints are {{name: [x, y, z]}} in degrees")
    await asyncio.to_thread(atomic_write_json, ws.stages_dir / "poses.json", body.model_dump())
    return body.model_dump()



@router.get("/stages/{st_id}", response_model=Stage)
async def stage_get(svc: Svc, st_id: str):
    ws, _, _ = svc.require_project()
    st = await asyncio.to_thread(StageStore(ws).get, st_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    return st.model_dump()


@router.put("/stages/{st_id}", response_model=Stage)
async def stage_put(svc: Svc, st_id: str, body: dict):
    ws, _, _ = svc.require_project()
    try:
        st = await asyncio.to_thread(StageStore(ws).put, st_id, body)
    except KeyError:
        raise HTTPException(404, "stage not found")
    except StaleStage as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


@router.delete("/stages/{st_id}", response_model=Deleted)
async def stage_delete(svc: Svc, st_id: str):
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(StageStore(ws).delete, st_id):
        raise HTTPException(404, "stage not found")
    svc.hub.broadcast("stage.deleted", {"id": st_id})
    return {"deleted": st_id}
