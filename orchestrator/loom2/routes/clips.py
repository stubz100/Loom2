"""Clips (M6, 11 §10): PNG master + h264 proxy per clip, filmstrip thumbnails, FaceSim advisory, frame harvest with lineage."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

from ..clips import ClipRecord, ClipStore, compute_identity
from ..fsio import _tmp_for, replace
from ..origin import JobOrigin
from ..schemas import ClipExtracted, ClipList, ExtendQueued
from ..tools import facesim
from .deps import Svc

router = APIRouter(tags=["clips"])
IMMUTABLE = {"Cache-Control": "private, max-age=31536000, immutable"}


class ClipExtract(BaseModel):
    frames: list[int]


class ExtendBody(BaseModel):
    prompt_text: str | None = None                # the clip's own prompt when absent
    stage: bool = False


@router.get("/clips", response_model=ClipList)
async def clips_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [c.model_dump() for c in await asyncio.to_thread(ClipStore(ws).list)]}


@router.get("/clips/{clip_id}", response_model=ClipRecord)
async def clip_get(svc: Svc, clip_id: str):
    ws, _, _ = svc.require_project()
    rec = await asyncio.to_thread(ClipStore(ws).get, clip_id)
    if not rec:
        raise HTTPException(404, "clip not found")
    return rec.model_dump()


@router.get("/clips/{clip_id}/proxy.mp4")
async def clip_proxy(svc: Svc, clip_id: str):
    ws, _, _ = svc.require_project()
    rec = await asyncio.to_thread(ClipStore(ws).get, clip_id)
    if not rec or not rec.proxy_path:
        raise HTTPException(404, "proxy not ready")
    p = ws.path / rec.proxy_path
    if not p.is_file():
        raise HTTPException(404, "proxy file is gone")           # C6: FileResponse on a missing file is a 500
    return FileResponse(p, media_type="video/mp4", headers=IMMUTABLE)


@router.get("/clips/{clip_id}/frames/{name}")
async def clip_frame(svc: Svc, clip_id: str, name: str, size: int = 0):
    """A master frame as PNG; with `size` a cached WebP thumbnail (longer side ≤ size) for the filmstrip (C24)."""
    ws, _, _ = svc.require_project()
    store = ClipStore(ws)
    rec = await asyncio.to_thread(store.get, clip_id)
    try:
        n = int(name.split(".")[0])
    except ValueError:
        raise HTTPException(400, "a frame index is expected, e.g. 37.png")
    if not rec or n < 0 or n >= rec.frames:
        raise HTTPException(404, "frame not found")
    if size:
        size = max(32, min(512, int(size)))
        out = store.dir(clip_id) / "strip" / f"{n:06d}_{size}.webp"
        if not out.is_file():
            await asyncio.to_thread(_strip_thumb, store.frame_path(clip_id, n), out, size)
        return FileResponse(out, media_type="image/webp", headers=IMMUTABLE)
    return FileResponse(store.frame_path(clip_id, n), media_type="image/png", headers=IMMUTABLE)


@router.post("/clips/{clip_id}/identity", response_model=ClipRecord)
async def clip_identity(svc: Svc, clip_id: str):
    """FaceSim advisory on demand (11 §6): cosine similarity of the start frame's face across the clip."""
    ws, cat, _ = svc.require_project()
    store = ClipStore(ws)
    rec = await asyncio.to_thread(store.get, clip_id)
    if not rec:
        raise HTTPException(404, "clip not found")
    if not facesim.available(svc.app.settings.models_root):
        raise HTTPException(409, "FaceSim weights are not fetched (scripts/fetch_facesim.py)")
    start = await asyncio.to_thread(cat.get, rec.start_asset_id)
    ref = cat.abs_path(start) if start else None
    rec.identity = await asyncio.to_thread(compute_identity, svc.app.settings.models_root, store, rec, ref)
    await asyncio.to_thread(store.save, rec)
    svc.hub.broadcast("clip.updated", {"clip_id": rec.id, "identity": rec.identity})
    return rec.model_dump()


@router.post("/clips/{clip_id}/extract", response_model=ClipExtracted)
async def clip_extract(svc: Svc, clip_id: str, body: ClipExtract):
    """Master frames → Catalogue images with `frame-extract` lineage from the clip's asset (11 §6)."""
    ws, cat, _ = svc.require_project()
    store = ClipStore(ws)
    rec = await asyncio.to_thread(store.get, clip_id)
    if not rec:
        raise HTTPException(404, "clip not found")
    wanted = sorted({n for n in body.frames if 0 <= n < rec.frames})[:64]
    if not wanted:
        raise HTTPException(422, "no valid frame indices")
    out = []
    for n in wanted:
        tmp = ws.temp_dir / "extract" / f"{rec.id}_{n:06d}.png"

        def copy_frame(n: int = n, tmp=tmp) -> None:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(store.frame_path(rec.id, n).read_bytes())
        await asyncio.to_thread(copy_frame)
        a = await asyncio.to_thread(cat.ingest_file, tmp, kind="image", move=True, suite="animate", lineage_kind="frame-extract", job_id=rec.job_id, batch_id=rec.batch_id,
                                    model_id=rec.model_id, seed=rec.seed, prompt_text=rec.prompt, parents=[rec.asset_id] if rec.asset_id else [],
                                    params={"clip_id": rec.id, "frame_index": n, "fps": rec.fps, "time_s": round(n / rec.fps, 3), "preset": rec.preset})
        a = await asyncio.to_thread(cat.make_thumbs, a)
        svc.hub.broadcast("asset.created", a.model_dump())
        out.append(a.model_dump())
        rec.extracted_asset_ids.append(a.id)
    await asyncio.to_thread(store.save, rec)
    return {"items": out, "clip": rec.model_dump()}


def _strip_thumb(src, out, size: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        tmp = _tmp_for(out)
        im.save(tmp, "WEBP", quality=80, method=4)
        try:
            replace(tmp, out)
        except OSError:                           # two requests for one frame: the other one won (C5's lesson)
            tmp.unlink(missing_ok=True)
            if not out.is_file():
                raise


@router.post("/clips/{clip_id}/extend", response_model=ExtendQueued)
async def clip_extend(svc: Svc, clip_id: str, body: ExtendBody):
    """D88 XE (experimental): continue the clip on its own model, preset, size, fps and length — its last frame extracted as the start
    (`frame-extract` lineage), its last `extend_lead` frames pinned as the lead-in (LTX 9; Wan 1 = the start alone). 422 with the sentence."""
    from ..models import registry
    ws, cat, q = svc.require_project()
    store = ClipStore(ws)
    rec = await asyncio.to_thread(store.get, clip_id)
    if not rec:
        raise HTTPException(404, "clip not found")
    spec = registry.get(rec.model_id)
    if spec is None or not spec.recipes.extend_lead:
        raise HTTPException(422, f"{spec.label if spec else rec.model_id} does not continue clips")
    prev = dict((rec.params or {}).get("recipe") or {})
    n = rec.frames - 1
    tmp = ws.temp_dir / "extract" / f"{rec.id}_{n:06d}.png"

    def copy_last() -> None:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(store.frame_path(rec.id, n).read_bytes())
    await asyncio.to_thread(copy_last)
    a = await asyncio.to_thread(cat.ingest_file, tmp, kind="image", move=True, suite="animate", lineage_kind="frame-extract", job_id=rec.job_id, batch_id=rec.batch_id,
                                model_id=rec.model_id, seed=rec.seed, prompt_text=rec.prompt, parents=[rec.asset_id] if rec.asset_id else [],
                                params={"clip_id": rec.id, "frame_index": n, "fps": rec.fps, "time_s": round(n / rec.fps, 3), "preset": rec.preset, "extend": True})
    a = await asyncio.to_thread(cat.make_thumbs, a)
    svc.hub.broadcast("asset.created", a.model_dump())
    rec.extracted_asset_ids.append(a.id)
    await asyncio.to_thread(store.save, rec)
    recipe = {"kind": "i2v", "model_id": rec.model_id, "start_asset": a.id, "prompt_text": (body.prompt_text if body.prompt_text is not None else rec.prompt),
              "frames": int(prev.get("frames") or rec.frames), "fps": rec.fps, "width": int(prev.get("width") or rec.w),
              "height": int(prev.get("height") or rec.h), "preset": rec.preset,
              "extend_from": {"clip_id": rec.id, "lead": int(spec.recipes.extend_lead)}}
    for k in ("negative", "steps", "cfg", "shift", "size_policy"):
        if prev.get(k) is not None:
            recipe[k] = prev[k]
    origin = JobOrigin(suite="animate", surface="extend", ref=rec.id, payload={"lead": int(spec.recipes.extend_lead)})
    try:
        job = q.submit(recipe, stage=body.stage, origin=origin)[0]
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"job_id": job.id, "start_asset_id": a.id, "lead": int(spec.recipes.extend_lead), "model_id": rec.model_id, "staged": job.status == "staged"}
