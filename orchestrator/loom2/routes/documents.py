"""Layered documents (10 §7, §13): stack, raw layer pixels and selection, save / flatten / export / compare, AI jobs.

Pixels travel as raw bytes with `X-Loom-Width/Height/Channels` (D4). `DocumentStore` has no lock of its own, so only
pure work (decode, encode, compare, zip reads) moves off the event loop besides the store's own `get` / `save` / `flatten`.
"""
from __future__ import annotations

import asyncio
import io
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel

from .. import matting
from ..compose import srgb_delta
from ..documents import Document
from ..schemas import Closed, CompareReply, Deleted, DocList, DocumentPutReply, FlattenedToCatalogue, FlattenedToFile, JobsSubmitted, PixelsPut, RefineReply, SelectionReply
from ..recipes import RefineEdge
from .deps import Svc
from .jobs import JobSubmit

router = APIRouter(tags=["documents"])
NO_STORE = {"Cache-Control": "no-store"}


class DocumentCreate(BaseModel):
    from_asset: str | None = None
    name: str | None = None
    w: int | None = None
    h: int | None = None
    background: str = "transparent"


class FlattenRequest(BaseModel):
    to_catalogue: bool = True
    name: str | None = None


class ExportRequest(BaseModel):
    format: str = "png"


@router.get("/documents", response_model=DocList)
async def documents_list(svc: Svc):
    return {"items": await asyncio.to_thread(svc.require_documents().list)}


@router.post("/documents", response_model=Document)
async def documents_create(svc: Svc, body: DocumentCreate):
    docs = svc.require_documents()
    _, cat, _ = svc.require_project()
    base = None
    name = body.name
    w, h = body.w, body.h
    if body.from_asset:
        a = await asyncio.to_thread(cat.get, body.from_asset)
        if not a:
            raise HTTPException(404, "asset not found")
        base = await asyncio.to_thread(_decode_rgba, cat.abs_path(a))      # B11: a 4K decode does not block the event loop
        h, w = base.shape[:2]
        name = name or f"{a.model_id or a.suite} {a.seed or a.id[-6:]}"
    if not w or not h:
        raise HTTPException(422, "w and h are required without from_asset")
    od = await asyncio.to_thread(docs.create, name or "Untitled", int(w), int(h), body.background, body.from_asset, base)
    svc.hub.broadcast("document.changed", {"id": od.doc.id})
    return od.doc.model_dump()


@router.get("/documents/{doc_id}", response_model=Document)
async def documents_get(svc: Svc, doc_id: str):
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    return od.doc.model_dump()


@router.put("/documents/{doc_id}", response_model=DocumentPutReply)
async def documents_put(svc: Svc, doc_id: str, body: dict):
    """Replace the stack. The reply lists raster layers / masks the server has no bytes for, so the editor uploads
    them before `/save` even when it does not consider them dirty (B15: delete · save · undo · save)."""
    od = await asyncio.to_thread(svc.require_documents().update_stack, doc_id, body)
    px, mk = od.missing_pixels()
    return od.doc.model_dump() | {"missing_pixels": px, "missing_masks": mk}


@router.get("/documents/{doc_id}/layers/{lid}/pixels")
async def layer_pixels_get(svc: Svc, doc_id: str, lid: str, kind: str = "image", raw: int = 0):
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    arr = od.masks.get(lid) if kind == "mask" else od.pixels.get(lid)
    if arr is None:
        raise HTTPException(404, "no pixels for this layer")
    if raw:
        return Response(content=arr.tobytes(), media_type="application/octet-stream",
                        headers={"X-Loom-Width": str(arr.shape[1]), "X-Loom-Height": str(arr.shape[0]), "X-Loom-Channels": str(1 if arr.ndim == 2 else 4), **NO_STORE})
    png = await asyncio.to_thread(_png_bytes, arr, 3)
    return Response(content=png, media_type="image/png", headers=NO_STORE)


@router.put("/documents/{doc_id}/layers/{lid}/pixels", response_model=PixelsPut)
async def layer_pixels_put(svc: Svc, doc_id: str, lid: str, request: Request, w: int, h: int, kind: str = "image"):
    """Raw uint8 body: RGBA (w·h·4 bytes) for images, grey (w·h) for masks; the fast path from the compositor (E2)."""
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    body = await request.body()
    ch = 1 if kind == "mask" else 4
    if len(body) != w * h * ch:
        raise HTTPException(400, f"expected {w * h * ch} bytes for {w}×{h}×{ch}, got {len(body)}")
    arr = np.frombuffer(body, dtype=np.uint8).reshape((h, w) if ch == 1 else (h, w, 4)).copy()
    if kind == "mask":
        od.set_mask(lid, arr)
        return {"layer": lid, "kind": "mask", "w": w, "h": h}
    node = od.set_pixels(lid, arr)
    return {"layer": lid, "kind": "image", "w": node.w, "h": node.h}


@router.post("/documents/{doc_id}/save", response_model=Document)
async def documents_save(svc: Svc, doc_id: str):
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    await asyncio.to_thread(od.save)
    svc.hub.broadcast("document.changed", {"id": doc_id, "saved_at": od.doc.saved_at})
    return od.doc.model_dump()


@router.post("/documents/{doc_id}/flatten", response_model=FlattenedToCatalogue | FlattenedToFile)
async def documents_flatten(svc: Svc, doc_id: str, body: FlattenRequest):
    _, cat, _ = svc.require_project()
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    merged = await asyncio.to_thread(od.flatten)
    out = svc.ws.temp_dir / "flatten" / f"{doc_id}.png"   # type: ignore[union-attr]
    out.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(lambda: Image.fromarray(merged, "RGBA").save(out, "PNG"))
    if not body.to_catalogue:
        return {"path": str(out)}
    src = await asyncio.to_thread(cat.get, od.doc.source_asset_id) if od.doc.source_asset_id else None
    rec = await asyncio.to_thread(cat.ingest_file, out, kind="image", move=True, suite="edit", parents=[src.id] if src else [],
                                  model_id=src.model_id if src else None, seed=src.seed if src else None, prompt_text=src.prompt_text if src else None,
                                  params={"document_id": doc_id, "document_name": body.name or od.doc.name, "layers": len(list(od.doc.walk()))})
    rec = await asyncio.to_thread(cat.make_thumbs, rec)
    if src:
        updated = await asyncio.to_thread(cat.patch, src.id, {"has_document": True})
        svc.hub.broadcast("asset.updated", updated.model_dump())   # type: ignore[union-attr]
    od.doc.meta["last_flatten_asset"] = rec.id
    svc.hub.broadcast("asset.created", rec.model_dump())
    return {"asset": rec.model_dump()}


@router.post("/documents/{doc_id}/export")
async def documents_export(svc: Svc, doc_id: str, body: ExportRequest):
    if body.format != "png":
        raise HTTPException(422, "the orchestrator exports PNG; PSD is written by the editor (ag-psd)")
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    merged = await asyncio.to_thread(od.flatten)
    png = await asyncio.to_thread(_png_bytes, merged, 6)
    return Response(content=png, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{od.doc.name}.png"'})


@router.post("/documents/{doc_id}/compare", response_model=CompareReply)
async def documents_compare(svc: Svc, doc_id: str, request: Request, w: int, h: int):
    """Raw straight-alpha RGBA of the editor's GPU composite (w·h·4 bytes) → per-channel delta against the exact
    flatten (10 §14 item 1). Both images are kept under temp/compare for inspection; the result lands in doc.meta."""
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    body = await request.body()
    if len(body) != w * h * 4:
        raise HTTPException(400, f"expected {w * h * 4} bytes for {w}×{h}×4, got {len(body)}")
    if (w, h) != (od.doc.w, od.doc.h):
        raise HTTPException(400, f"composite is {w}×{h}, the document is {od.doc.w}×{od.doc.h}")
    gpu = np.frombuffer(body, dtype=np.uint8).reshape((h, w, 4)).copy()
    exact = await asyncio.to_thread(od.flatten)
    out = svc.ws.temp_dir / "compare"   # type: ignore[union-attr]

    def measure() -> dict:
        d = srgb_delta(exact, gpu)
        rgb = srgb_delta(exact[..., :3], gpu[..., :3])
        out.mkdir(parents=True, exist_ok=True)
        Image.fromarray(exact, "RGBA").save(out / f"{doc_id}-exact.png")
        Image.fromarray(gpu, "RGBA").save(out / f"{doc_id}-gpu.png")
        return {"mean": d["mean"], "p99": d["p99"], "max": d["max"], "rgb_mean": rgb["mean"], "rgb_p99": rgb["p99"], "rgb_max": rgb["max"],
                "w": w, "h": h, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    d = await asyncio.to_thread(measure)
    od.doc.meta["last_compare"] = d
    return d


@router.get("/documents/{doc_id}/thumbnail")
async def documents_thumbnail(svc: Svc, doc_id: str):
    p = svc.require_documents().path_for(doc_id)
    data = await asyncio.to_thread(_ora_thumbnail, p)
    return Response(content=data, media_type="image/png", headers=NO_STORE)


@router.get("/documents/{doc_id}/selection")
async def documents_selection_get(svc: Svc, doc_id: str):
    """The document's selection as raw grey bytes (the AI Select result lands here, M5 slice 2)."""
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    if od.selection is None:
        raise HTTPException(404, "no selection")
    sel = od.selection
    return Response(content=sel.tobytes(), media_type="application/octet-stream",
                    headers={"X-Loom-Width": str(sel.shape[1]), "X-Loom-Height": str(sel.shape[0]), "X-Loom-Channels": "1", **NO_STORE})


@router.put("/documents/{doc_id}/selection", response_model=SelectionReply)
async def documents_selection_put(svc: Svc, doc_id: str, request: Request, w: int = 0, h: int = 0):
    """The editor's selection as raw grey bytes (w·h); an empty body clears it. The M5 edit jobs read it."""
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    body = await request.body()
    if not body:
        od.selection = None
        od.doc.has_selection = False
        return {"selection": None}
    if len(body) != w * h or w <= 0 or h <= 0:
        raise HTTPException(400, f"expected {w * h} bytes for {w}×{h}, got {len(body)}")
    if (w, h) != (od.doc.w, od.doc.h):              # B10: the region maths index the selection with document coordinates
        raise HTTPException(400, f"selection {w}×{h} must match the document {od.doc.w}×{od.doc.h}")
    od.selection = np.frombuffer(body, dtype=np.uint8).reshape((h, w)).copy()
    od.doc.has_selection = True
    od.dirty = True
    return {"selection": [w, h]}


@router.post("/documents/{doc_id}/selection/refine", response_model=RefineReply)
async def documents_selection_refine(svc: Svc, doc_id: str, body: RefineEdge):
    """D45 Refine Edge: refine the document's selection against its exact composite (guided filter in the edge band, then smooth /
    feather / contrast / shift edge); the result replaces the selection. Upload the editor's selection first (PUT …/selection)."""
    od = await asyncio.to_thread(svc.require_documents().get, doc_id)
    if od.selection is None:
        raise HTTPException(400, "no selection to refine")

    def run() -> tuple[float, int]:
        t0 = time.perf_counter()
        od.selection = matting.refine(od.selection, od.flatten(), matting.params_from(body))
        od.doc.has_selection = True
        od.dirty = True
        return float(od.selection.mean() / 255.0), int((time.perf_counter() - t0) * 1000)
    coverage, ms = await asyncio.to_thread(run)
    return {"selection": [od.doc.w, od.doc.h], "coverage": round(coverage, 4), "ms": ms}


@router.post("/documents/{doc_id}/ai", response_model=JobsSubmitted)
async def documents_ai(svc: Svc, doc_id: str, body: JobSubmit):
    """Queue an inpaint / refine / upscale job on this document (10 §13); results come back as layers
    (`document.changed` events with `added`) or, for upscale, as a Catalogue asset too."""
    _, _, q = svc.require_project()
    await asyncio.to_thread(svc.require_documents().get, doc_id)            # 404 if the document does not exist
    recipe = dict(body.recipe)
    if recipe.get("kind") not in ("inpaint", "i2i", "upscale", "segment"):
        raise HTTPException(422, "document jobs are inpaint, i2i (refine), upscale or segment (AI Select)")
    recipe["document_id"] = doc_id
    try:
        jobs = q.submit(recipe, stage=body.stage)                            # the queue is not thread-safe: stays on the loop
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"jobs": [j.model_dump() for j in jobs]}


@router.post("/documents/{doc_id}/close", response_model=Closed)
async def documents_close(svc: Svc, doc_id: str):
    svc.require_documents().close(doc_id)
    return {"closed": doc_id}


@router.delete("/documents/{doc_id}", response_model=Deleted)
async def documents_delete(svc: Svc, doc_id: str):
    if not svc.require_documents().delete(doc_id):
        raise HTTPException(404, "no document")
    svc.hub.broadcast("document.changed", {"id": doc_id, "deleted": True})
    return {"deleted": doc_id}


def _decode_rgba(p: Path) -> np.ndarray:
    with Image.open(p) as im:
        return np.asarray(im.convert("RGBA"))


def _png_bytes(arr: np.ndarray, compress_level: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, "L" if arr.ndim == 2 else "RGBA").save(buf, "PNG", compress_level=compress_level)
    return buf.getvalue()


def _ora_thumbnail(p: Path) -> bytes:
    if not p.is_file():
        raise HTTPException(404, "no document")
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        src = next((n for n in ("Thumbnails/thumbnail.png", "mergedimage.png") if n in names), None)
        if src is None:
            raise HTTPException(404, "the document has no thumbnail")      # C13: a foreign ORA without a merged image
        return z.read(src)
