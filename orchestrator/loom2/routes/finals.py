"""D111 (PS5): the final shot — make one from a finished Stage scene (its layers' passes uploaded as blobs), list, read, a pass frame, delete."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..finals import LAYER_PASSES, Final, FinalLayer, FinalStore
from ..schemas import Deleted
from ..stages import StageStore
from .deps import Svc

router = APIRouter(tags=["finals"])


class FinalLayerIn(BaseModel):
    id: str
    kind: str
    name: str
    object_id: str | None = None
    method: str | None = None                      # None = the kind's default (finals.DEFAULT_METHOD)
    profile_id: str | None = None
    version: str | None = None
    passes: dict[str, list[str]]                   # pass name → the frames' blob ids (sha256), in order
    keypoints: list[Any] | None = None             # a figure's per-frame keypoints (Stage's COCO-18 for that figure)


class FinalCreate(BaseModel):
    name: str = "Final"
    stage_id: str
    camera_id: str
    stage_revision: int
    range: dict[str, int]
    rate: int = 16
    size: dict[str, int]
    frames: int
    shot_id: str | None = None
    layers: list[FinalLayerIn] = Field(default_factory=list)


class FinalList(BaseModel):
    items: list[Final]


def _blob(ws, sha: str):
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise HTTPException(422, f"{sha[:16]}…: a blob id is a lowercase sha256")
    p = ws.temp_dir / "blobs" / sha
    if not p.is_file():
        raise HTTPException(422, f"blob {sha[:12]}… was not uploaded (PUT /blobs/{{sha}} first)")
    return p


@router.post("/finals", response_model=Final)
async def final_create(svc: Svc, body: FinalCreate):
    """PS5a: a final from the scene's layers — the record and each layer's passes (Stage's renders at the shot's rate) on disk."""
    from ..finals import DEFAULT_METHOD
    ws, _, _ = svc.require_project()
    st = await asyncio.to_thread(StageStore(ws).get, body.stage_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    if body.camera_id not in [c.id for c in st.cameras]:
        raise HTTPException(422, f"camera {body.camera_id} is not in the stage")
    for x in body.layers:
        if x.kind not in LAYER_PASSES:
            raise HTTPException(422, f"layer {x.id}: a layer is a plate, a figure, a prop or the shadows")
    passes = {x.id: {name: [_blob(ws, sha) for sha in shas] for name, shas in x.passes.items()} for x in body.layers}
    keypoints = {x.id: x.keypoints for x in body.layers if x.keypoints is not None}
    data = body.model_dump(exclude={"layers"}) | {"layers": [FinalLayer(id=x.id, kind=x.kind, name=x.name, object_id=x.object_id, method=x.method or DEFAULT_METHOD[x.kind],  # type: ignore[arg-type]
                                                                        profile_id=x.profile_id, version=x.version).model_dump() for x in body.layers]}
    try:
        f = await asyncio.to_thread(FinalStore(ws).create, data, passes, keypoints)
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})
    return f.model_dump()


@router.get("/finals", response_model=FinalList)
async def finals_list(svc: Svc, stage_id: str | None = None):
    ws, _, _ = svc.require_project()
    return {"items": [f.model_dump() for f in await asyncio.to_thread(FinalStore(ws).list, stage_id)]}


@router.get("/finals/{fid}", response_model=Final)
async def final_get(svc: Svc, fid: str):
    ws, _, _ = svc.require_project()
    f = await asyncio.to_thread(FinalStore(ws).get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    return f.model_dump()


@router.get("/finals/{fid}/layers/{lid}/{name}/{n}")
async def final_frame(svc: Svc, fid: str, lid: str, name: str, n: int):
    """A layer's pass (or own) frame as PNG — the panel's previews."""
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None or not any(x.id == lid for x in f.layers):
        raise HTTPException(404, "final or layer not found")
    if not name.replace("_", "").isalnum():
        raise HTTPException(422, "a pass name is a word")
    p = store.pass_dir(fid, lid, name) / f"{n:04d}.png"
    if not p.is_file():
        raise HTTPException(404, "no such frame")
    return FileResponse(p, media_type="image/png")


@router.delete("/finals/{fid}", response_model=Deleted)
async def final_delete(svc: Svc, fid: str):
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(FinalStore(ws).delete, fid):
        raise HTTPException(404, "final not found")
    svc.hub.broadcast("final.updated", {"id": fid, "revision": -1})
    return {"deleted": fid}
