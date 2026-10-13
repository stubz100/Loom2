"""Stages (P13 / ST1, 16 §12): the 3D blocking documents — list, create (one camera, the project's size and fps), read, replace
(409 on a stale revision), delete. ST3: the passes a camera rendered become `stage-pass` assets on the stage's album page. Shots (ST4) join here."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..fsio import atomic_write_json, read_json_or, utc_now
from ..origin import JobOrigin
from ..recipes import STAGE_PASSES
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


class PassesUpload(BaseModel):
    """ST3 (16 §7): the passes the client rendered for one camera — each a PNG already put through `PUT /blobs/{sha}` — with the COCO-18
    keypoints behind the pose pass and the mask pass's colour legend."""
    camera_id: str
    revision: int                                 # the document revision the passes were rendered from (staleness is judged against it)
    size: dict[str, int]                          # {w, h} they were rendered at
    passes: dict[str, str]                        # pass name → blob sha256
    keypoints: list[Any] = []                     # per figure: 18 × [x, y, visible] in `size` pixels
    legend: dict[str, Any] = {}                   # mask colour → object id / name


@router.post("/stages/{st_id}/passes", response_model=Stage)
async def stage_passes(svc: Svc, st_id: str, body: PassesUpload):
    """Each pass becomes an asset (`lineage_kind = stage-pass`, suite stage, `params {stage_id, camera_id, revision, pass, size}`, the
    keypoints on the pose pass, the legend on the mask pass) placed on the stage's album page (made on first use, D34); the document
    records them for the camera and comes back at its new revision."""
    ws, catalogue, _ = svc.require_project()
    groups = svc.require_groups()
    store = StageStore(ws)
    st = await asyncio.to_thread(store.get, st_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    if not any(c.id == body.camera_id for c in st.cameras):
        raise HTTPException(422, f"camera {body.camera_id!r} is not in the stage")
    bad = [k for k in body.passes if k not in STAGE_PASSES]
    if bad or not body.passes:
        raise HTTPException(422, f"passes are {', '.join(STAGE_PASSES)}; got {sorted(body.passes) or 'none'}")
    files = {}
    for name, sha in body.passes.items():
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise HTTPException(422, f"pass {name}: a blob id is a lowercase sha256")
        p = ws.temp_dir / "blobs" / sha
        if not p.is_file():
            raise HTTPException(422, f"pass {name}: blob {sha[:12]}… was not uploaded (PUT /blobs/{{sha}} first)")
        files[name] = p
    gid = st.group_id if st.group_id and st.group_id in groups.groups else None
    if gid is None:
        gid = (await asyncio.to_thread(groups.create, f"Stage · {st.name}")).id
    origin = JobOrigin(suite="stage", surface="passes", ref=st_id, payload={"camera_id": body.camera_id})
    assets: dict[str, str] = {}
    for name, p in files.items():
        params = {"stage_id": st_id, "camera_id": body.camera_id, "revision": body.revision, "pass": name, "size": body.size}
        if name == "pose":
            params["keypoints"] = body.keypoints
        if name == "mask":
            params["legend"] = body.legend
        rec = await asyncio.to_thread(catalogue.ingest_file, p, kind="image", move=False, suite="stage", lineage_kind="stage-pass", origin=origin, params=params,
                                      prompt_text=f"{st.name} · {name} pass")
        rec = await asyncio.to_thread(catalogue.make_thumbs, rec)
        svc.hub.broadcast("asset.created", rec.model_dump())
        assets[name] = rec.id
    await asyncio.to_thread(groups.move, [("asset", a) for a in assets.values()], gid)
    entry = {"camera_id": body.camera_id, "revision": body.revision, "size": body.size, "assets": assets, "keypoints": body.keypoints, "legend": body.legend,
             "rendered_at": utc_now()}
    st2 = await asyncio.to_thread(store.set_passes, st_id, entry, gid)
    svc.hub.broadcast("stage.updated", {"id": st2.id, "revision": st2.revision})
    return st2.model_dump()


@router.delete("/stages/{st_id}", response_model=Deleted)
async def stage_delete(svc: Svc, st_id: str):
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(StageStore(ws).delete, st_id):
        raise HTTPException(404, "stage not found")
    svc.hub.broadcast("stage.deleted", {"id": st_id})
    return {"deleted": st_id}
