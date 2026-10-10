"""Catalogue assets: query, judge, trash and purge, duplicate, files and thumbnails, lineage, import, index rebuild (08, 06 §6).

Order matters: the literal `/assets/...` paths are registered before `/assets/{asset_id}` (tests/test_routes_d37.py checks it).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..catalogue import AssetPage, AssetQuery, Catalogue, GroupHeader
from ..tools.pngmeta import parse_image_metadata
from .deps import Svc

router = APIRouter(tags=["assets"])

IMPORTABLE = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm")
IMMUTABLE = {"Cache-Control": "private, max-age=31536000, immutable"}


class AssetPatch(BaseModel):
    state: str | None = None
    rating: int | None = None
    tags: list[str] | None = None


class ImportRequest(BaseModel):
    paths: list[str]
    suite: str = "import"


class IdList(BaseModel):
    ids: list[str]


class BulkPatch(BaseModel):
    ids: list[str]
    changes: dict[str, Any]


class PurgeRequest(BaseModel):
    ids: list[str] | None = None
    older_than_days: int | None = None


@router.get("/assets", response_model=AssetPage)
async def assets_list(svc: Svc, q: Annotated[AssetQuery, Query()]):
    _, cat, _ = svc.require_project()
    return await asyncio.to_thread(cat.list, q)


@router.get("/assets/groups", response_model=list[GroupHeader])
async def assets_groups(svc: Svc, q: Annotated[AssetQuery, Query()]):
    _, cat, _ = svc.require_project()
    return await asyncio.to_thread(cat.groups, q)


@router.get("/assets/counts")
async def assets_counts(svc: Svc):
    _, cat, _ = svc.require_project()
    return await asyncio.to_thread(cat.counts)


@router.get("/assets/tags")
async def assets_tags(svc: Svc):
    _, cat, _ = svc.require_project()
    return {"items": await asyncio.to_thread(cat.tags)}


@router.patch("/assets/bulk")
async def assets_bulk(svc: Svc, body: BulkPatch):
    _, cat, _ = svc.require_project()
    recs = await asyncio.to_thread(cat.patch_many, body.ids, body.changes)
    for r in recs:
        svc.hub.broadcast("asset.updated", r.model_dump())
    return {"items": [r.model_dump() for r in recs]}


@router.post("/assets/trash")
async def assets_trash(svc: Svc, body: IdList):
    _, cat, _ = svc.require_project()
    recs = await asyncio.to_thread(cat.trash, body.ids)
    for r in recs:
        svc.hub.broadcast("asset.updated", r.model_dump())
    return {"trashed": [r.id for r in recs]}


@router.post("/assets/restore")
async def assets_restore(svc: Svc, body: IdList):
    _, cat, _ = svc.require_project()
    recs = await asyncio.to_thread(cat.restore, body.ids)
    for r in recs:
        svc.hub.broadcast("asset.updated", r.model_dump())
    return {"restored": [r.id for r in recs]}


@router.post("/assets/purge")
async def assets_purge(svc: Svc, body: PurgeRequest):
    _, cat, _ = svc.require_project()
    gone = await asyncio.to_thread(cat.purge, body.ids, body.older_than_days)
    if gone and (changed := await asyncio.to_thread(svc.require_groups().forget_assets, gone)):
        svc.group_changed(changed)
    if len(gone) > 50:                                # emptying a 10k trash: one event, the clients reload (not 10k frames)
        svc.hub.broadcast("catalogue.changed", {"purged": len(gone)})
    else:
        for i in gone:
            svc.hub.broadcast("asset.deleted", {"id": i})
    return {"purged": len(gone), "ids": gone if len(gone) <= 50 else []}


@router.post("/assets/import")
async def assets_import(svc: Svc, body: ImportRequest):
    _, cat, _ = svc.require_project()
    files = await asyncio.to_thread(_import_files, body.paths)
    out = []
    for src in files:
        rec = await asyncio.to_thread(_ingest_import, cat, src, body.suite)
        svc.hub.broadcast("asset.created", rec.model_dump())
        out.append(rec.model_dump())
    return {"items": out}


@router.post("/assets/duplicate")
async def assets_duplicate(svc: Svc, body: IdList):
    st = svc.require_groups()
    new = await asyncio.to_thread(st.duplicate_assets, body.ids)
    for aid in new:
        if (rec := await asyncio.to_thread(svc.catalogue.get, aid)) is not None:
            svc.hub.broadcast("asset.created", rec.model_dump())
    svc.group_changed({st.parent[("asset", a)] for a in new if ("asset", a) in st.parent})
    return {"ids": new}


@router.get("/assets/{asset_id}")
async def asset_get(svc: Svc, asset_id: str):
    _, cat, _ = svc.require_project()
    rec = await asyncio.to_thread(cat.get, asset_id)
    if not rec:
        raise HTTPException(404, "asset not found")
    return rec.model_dump()


@router.patch("/assets/{asset_id}")
async def asset_patch(svc: Svc, asset_id: str, body: AssetPatch):
    _, cat, _ = svc.require_project()
    rec = await asyncio.to_thread(cat.patch, asset_id, body.model_dump(exclude_none=True))
    if not rec:
        raise HTTPException(404, "asset not found")
    svc.hub.broadcast("asset.updated", rec.model_dump())
    return rec.model_dump()


@router.delete("/assets/{asset_id}")
async def asset_delete(svc: Svc, asset_id: str):
    _, cat, _ = svc.require_project()
    if not await asyncio.to_thread(cat.delete, asset_id):
        raise HTTPException(404, "asset not found")
    if changed := await asyncio.to_thread(svc.require_groups().forget_assets, [asset_id]):
        svc.group_changed(changed)
    svc.hub.broadcast("asset.deleted", {"id": asset_id})
    return {"deleted": asset_id}


@router.get("/assets/{asset_id}/file")
async def asset_file(svc: Svc, asset_id: str):
    _, cat, _ = svc.require_project()
    rec = await asyncio.to_thread(cat.get, asset_id)
    if not rec:
        raise HTTPException(404, "asset not found")
    return FileResponse(cat.abs_path(rec), headers={**IMMUTABLE, "ETag": f'"{rec.sha256}"'})


@router.get("/thumbs/{asset_id}/{size}")
async def thumb(svc: Svc, asset_id: str, size: int):
    ws, cat, _ = svc.require_project()
    p = ws.thumb_path(asset_id, size)
    if not p.is_file():
        rec = await asyncio.to_thread(cat.get, asset_id)
        if not rec:
            raise HTTPException(404, "asset not found")
        await asyncio.to_thread(cat.make_thumbs, rec)
        if not p.is_file():
            raise HTTPException(404, "no thumbnail")
    return FileResponse(p, media_type="image/webp", headers=IMMUTABLE)


@router.get("/lineage/tree/{root_id}")
async def lineage_tree(svc: Svc, root_id: str):
    _, cat, _ = svc.require_project()
    groups = svc.require_groups()

    def build() -> dict:
        tree = cat.lineage_tree(root_id)
        tree["locations"] = groups.where([i["id"] for i in tree["items"]])       # where each one lives (D34)
        return tree
    return await asyncio.to_thread(build)


@router.get("/lineage/{asset_id}")
async def lineage(svc: Svc, asset_id: str):
    _, cat, _ = svc.require_project()
    return await asyncio.to_thread(cat.lineage, asset_id)


@router.post("/catalogue/rebuild")
async def catalogue_rebuild(svc: Svc):
    _, cat, _ = svc.require_project()
    n = await asyncio.to_thread(cat.rebuild)
    return {"indexed": n}


def _import_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        src = Path(p)
        if src.is_dir():
            files += sorted(x for x in src.iterdir() if x.suffix.lower() in IMPORTABLE)
        elif src.is_file():
            files.append(src)
        else:
            raise HTTPException(400, f"not a file or folder: {p}")
    return files


def _ingest_import(cat: Catalogue, src: Path, suite: str):
    """One imported file → asset with the generation metadata its PNG carries (ComfyUI / A1111), then thumbnails."""
    meta = parse_image_metadata(src) if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else {}
    kind = "video" if src.suffix.lower() in (".mp4", ".webm") else "image"
    rec = cat.ingest_file(src, kind=kind, move=False, suite=suite, prompt_text=meta.get("prompt_text"),
                          prompt_json=meta.get("prompt_json"), seed=meta.get("seed") if isinstance(meta.get("seed"), int) else None,
                          params={"imported_from": str(src), **{k: v for k, v in meta.items() if k not in ("prompt_text", "prompt_json", "seed", "w", "h")}})
    return cat.make_thumbs(rec)
