"""The orchestrator's HTTP + WebSocket surface (06 §6). Bytes go over loopback HTTP with 4 MiB chunks (E2/D4);
events over `/events`; every mutating call needs `X-Loom-Token` (per-launch token, injected by the shell).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ValidationError

from . import __version__
from .clips import ClipStore, compute_identity
from .tools import facesim
from .catalogue import AssetPage, AssetQuery, Catalogue, CollectionRecord, GroupHeader
from .config import AppState
from .documents import DocumentStore
from .engine.graphs import CompileError, I2V_RULES, I2V_WEIGHTS, LTX_STEPS, PRESETS, VRAM_ESTIMATE_GB, WAN_PRESETS, effective_params, estimate_i2v_seconds, i2v_params
from .engine.supervisor import EngineSupervisor
from .events import EventHub
from .fsio import StateError, _tmp_for
from .queue import JobQueue
from .recipes import FLUX2_SCHEDULE, I2V, SAMPLERS, SCHEDULERS, T2I, TE_DEVICES, WEIGHT_DTYPES, parse_recipe
from .roster import ROSTER_BY_ID, Roster
from .tools.fetch import FetchJob, sha256_of
from .tools.pngmeta import parse_image_metadata
from .workspace import Workspace

FileResponse.chunk_size = 4 * 2**20   # E2: 64 KiB chunks cap loopback at ~400 MiB/s; 4 MiB gives > 1 GiB/s
log = logging.getLogger("loom2.api")
DEV_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]


class Services:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.app = AppState(state_dir)
        self.hub = EventHub()
        self.roster = Roster(self.app.models_root, [Path(p) for p in self.app.settings.mounted_model_trees], self.app.settings.variant)
        self.engine = EngineSupervisor(self.app, on_state=lambda s: self.hub.broadcast("engine.state", s))
        self.ws: Workspace | None = None
        self.catalogue: Catalogue | None = None
        self.queue: JobQueue | None = None
        self.documents: DocumentStore | None = None
        self.fetches: dict[str, FetchJob] = {}

    # ---- project binding ------------------------------------------------------------------------
    async def open_project(self, path: Path) -> dict:
        await self.close_project()
        ws = Workspace.open(path)
        # B8: build everything first so a corrupt catalogue or queue file leaves no half-open project behind
        catalogue = Catalogue(ws, self.app.settings.thumbnail_sizes, session_id=self.app.session_id)
        try:
            queue = JobQueue(ws, self.app, self.engine, self.roster, catalogue, self.hub)
            documents = DocumentStore(ws)
            queue.documents = documents
            await queue.start()
        except Exception:
            catalogue.close()
            raise
        self.ws, self.catalogue, self.queue, self.documents = ws, catalogue, queue, documents
        self.app.touch_project(ws.path)
        info = ws.info()
        self.hub.broadcast("project.opened", info)
        return info

    async def close_project(self) -> None:
        if self.queue:
            await self.queue.stop()
            self.queue = None
        if self.catalogue:
            self.catalogue.close()
            self.catalogue = None
        self.documents = None
        if self.ws:
            self.hub.broadcast("project.closed", {"path": str(self.ws.path)})
            self.ws = None

    def require_project(self) -> tuple[Workspace, Catalogue, JobQueue]:
        if not (self.ws and self.catalogue and self.queue):
            raise HTTPException(409, "no project is open")
        return self.ws, self.catalogue, self.queue


class ClipExtract(BaseModel):
    frames: list[int]


class ProjectCreate(BaseModel):
    path: str
    name: str
    format: dict | None = None
    size_cap_gb: float = 100.0


class ProjectOpen(BaseModel):
    path: str


class JobSubmit(BaseModel):
    recipe: dict[str, Any]
    stage: bool = False


class RecipeBody(BaseModel):
    recipe: dict[str, Any]


class AssetPatch(BaseModel):
    state: str | None = None
    rating: int | None = None
    tags: list[str] | None = None
    collection_ids: list[str] | None = None


class ImportRequest(BaseModel):
    paths: list[str]
    suite: str = "import"


class FetchRequest(BaseModel):
    model_id: str


class IdList(BaseModel):
    ids: list[str]


class BulkPatch(BaseModel):
    ids: list[str]
    changes: dict[str, Any]


class PurgeRequest(BaseModel):
    ids: list[str] | None = None
    older_than_days: int | None = None


class CollectionCreate(BaseModel):
    name: str
    kind: str = "manual"
    filter: dict | None = None


class CollectionPatch(BaseModel):
    name: str | None = None
    kind: str | None = None
    filter: dict | None = None


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


def create_app(state_dir: Path | None = None, project: Path | None = None, ready_cb=None) -> FastAPI:
    svc = Services(state_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc.roster.scan()
        target = project or (Path(svc.app.record.last_project) if svc.app.settings.reopen_last_project and svc.app.record.last_project else None)
        if target:
            try:
                await svc.open_project(Path(target))
            except Exception as e:  # noqa: BLE001 — B8: a damaged last project must not keep the orchestrator from starting
                log.error("could not open project %s: %s", target, e)
        if ready_cb:
            ready_cb(svc)
        try:
            yield
        finally:
            await svc.close_project()
            await svc.engine.stop()
            await svc.engine.client.aclose()

    app = FastAPI(title="loom2 orchestrator", version=__version__, lifespan=lifespan)
    app.state.services = svc
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Loom-Width", "X-Loom-Height", "X-Loom-Channels", "Content-Disposition"])

    @app.middleware("http")
    async def token_gate(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path not in ("/health",):
            if request.headers.get("X-Loom-Token") != svc.app.token:
                return JSONResponse({"detail": "missing or wrong X-Loom-Token"}, status_code=401)
        return await call_next(request)

    @app.exception_handler(StateError)
    async def _state_error(_: Request, e: StateError):
        return JSONResponse({"detail": str(e)}, status_code=400)

    # ---- meta -----------------------------------------------------------------------------------
    @app.get("/health")
    async def health():
        return {"ok": True, "version": __version__, "project_open": svc.ws is not None,
                "engine_running": svc.engine.state()["running"], "variant": svc.app.settings.variant,
                "start_suite": os.environ.get("LOOM2_START_SUITE"), "session_id": svc.app.session_id}   # start_suite: dev affordance

    @app.get("/version")
    async def version():
        return {"orchestrator": __version__, "engine": svc.engine.version, "variant": svc.app.settings.variant}

    @app.get("/capabilities")
    async def capabilities():
        models = {}
        for mid, preset in PRESETS.items():
            e = ROSTER_BY_ID[mid]
            if svc.app.settings.variant == "open" and "open" not in e.variants:
                continue
            r = svc.roster.resolve(mid)
            models[mid] = {"family": e.family, "label": preset.label, "health": r.health, "steps": preset.steps, "guidance": preset.guidance, "cfg": preset.cfg,
                           "distilled": preset.distilled, "turbo": preset.turbo_lora is not None, "turbo_steps": preset.turbo_steps, "json_prompt": preset.json_prompt,
                           "max_refs": preset.max_refs, "sampler": preset.sampler, "scheduler": preset.scheduler, "vram_gb": VRAM_ESTIMATE_GB.get(mid),
                           "wired": mid == "flux2-dev-fp8mixed" or e.family == "klein", "license": e.license, "variants": e.variants}
        live = svc.queue.engine_enum if svc.queue else (lambda cls, key: None)      # the running engine's own enums when it has answered
        i2v_models = {}
        for mid, needs in I2V_WEIGHTS.items():
            e = ROSTER_BY_ID[mid]
            rule = I2V_RULES[e.family]
            healths = {x: svc.roster.resolve(x).health for x in needs}
            missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
            i2v_models[mid] = {"family": e.family, "label": rule["label"], "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                               "missing": missing, "fps": rule["fps"], "frames": rule["frames"], "frame_step": rule["frame_step"], "size_mult": rule["size_mult"], "size": list(rule["size"]),
                               "presets": {k: (v.label if e.family == "wan22" else f"{LTX_STEPS[k]} steps") for k, v in WAN_PRESETS.items()}, "beats": e.family == "ltx23", "flf": True,
                               "vram_gb": VRAM_ESTIMATE_GB.get(mid), "license": e.license, "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
        i2v_caps = {"models": i2v_models, "tiers": {"draft": {"wan22": [832, 480], "ltx23": [1024, 576]}, "hd": {"wan22": [1280, 720], "ltx23": [1280, 704]}},
                    "portrait": {"wan22": [480, 832], "ltx23": [576, 1024]}, "square": {"wan22": [640, 640], "ltx23": [640, 640]}}
        return {"recipes": ["t2i", "inpaint", "i2i", "upscale", "segment", "i2v"], "i2v": i2v_caps, "models": models,
                "facesim": {"available": facesim.available(svc.app.settings.models_root), "dir": str(facesim.weights_dir(svc.app.settings.models_root))}, "variant": svc.app.settings.variant, "vram_budget_gb": svc.app.settings.vram_budget_gb,
                "samplers": live("KSampler", "sampler_name") or SAMPLERS, "schedulers": (live("KSampler", "scheduler") or SCHEDULERS) + [FLUX2_SCHEDULE],
                "weight_dtypes": live("UNETLoader", "weight_dtype") or WEIGHT_DTYPES, "te_devices": TE_DEVICES,
                "advanced": {"model_shift": {"flux2-dev-fp8mixed": 2.02, "klein": 2.02}, "shift_node_defaults": {"base": 0.5, "max": 1.15}, "tile_size_default": 512,
                             "flux2_schedule": FLUX2_SCHEDULE},
                "tiers": {"thumb": {"flux2": [896, 512], "klein": [896, 512]}, "draft": {"flux2": [960, 544], "klein": [1280, 720]}, "full": {"flux2": [1920, 1088], "klein": [1920, 1088]}}}

    @app.post("/recipes/preview")
    async def recipe_preview(body: RecipeBody):
        """09 §3a: the exact string the engine will receive, effective parameters, ETA and VRAM fit, missing weights."""
        try:
            recipe = parse_recipe(body.recipe)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if isinstance(recipe, I2V):                                  # M6: snapped size / frames, the preset that runs, missing weights, ETA
            try:
                ep = i2v_params(recipe)
            except CompileError as e:
                raise HTTPException(422, str(e))
            missing = []
            for mid in I2V_WEIGHTS[recipe.model_id]:
                r = svc.roster.resolve(mid)
                if r.path is None:
                    missing.append({"model_id": mid, "health": r.health, "approx_gb": r.entry.approx_gb})
            return {**ep, "missing": missing, "estimate": estimate_i2v_seconds(recipe), "count": len(recipe.seeds or [0])}
        if not isinstance(recipe, T2I):
            raise HTTPException(422, "preview supports t2i and i2v recipes")
        try:
            ep = effective_params(recipe)
        except CompileError as e:
            raise HTTPException(422, str(e))
        missing = []
        preset = PRESETS[recipe.model_id]
        for mid in [recipe.model_id, preset.te_id, preset.vae_id, *([preset.turbo_lora] if ep["turbo"] and preset.turbo_lora else []), *[l.model_id for l in recipe.loras]]:
            try:
                r = svc.roster.resolve(mid)
            except KeyError as e:
                raise HTTPException(422, str(e))              # B11: an unknown LoRA id is the caller's error, not a 500
            if r.path is None:
                missing.append({"model_id": mid, "health": r.health, "approx_gb": r.entry.approx_gb})
        est = svc.queue.estimate(recipe) if svc.queue else {"seconds": None, "source": "no project"}
        return {**ep, "missing": missing, "estimate": est, "count": len(recipe.seeds or [0])}

    @app.get("/settings")
    async def get_settings():
        return svc.app.settings.model_dump()

    @app.put("/settings")
    async def put_settings(patch: dict):
        try:
            s = svc.app.update_settings(patch)
        except ValidationError as e:
            raise HTTPException(422, e.errors()[0].get("msg", "invalid settings") if e.errors() else "invalid settings")
        svc.roster = Roster(svc.app.models_root, [Path(p) for p in s.mounted_model_trees], s.variant).scan()
        if svc.queue:                                   # B7: the live queue compiles against the new roster at once
            svc.queue.roster = svc.roster
        svc.engine.reconfigure()
        return s.model_dump()

    # ---- project --------------------------------------------------------------------------------
    @app.post("/project")
    async def project_create(body: ProjectCreate):
        Workspace.create(Path(body.path), name=body.name, fmt=body.format, size_cap_gb=body.size_cap_gb, variant=svc.app.settings.variant)
        return await svc.open_project(Path(body.path))

    @app.post("/project/open")
    async def project_open(body: ProjectOpen):
        return await svc.open_project(Path(body.path))

    @app.post("/project/close")
    async def project_close():
        await svc.close_project()
        return {"open": False}

    @app.get("/project")
    async def project_get():
        if not svc.ws:
            return {"open": False}
        info = svc.ws.info()
        info["assets"] = svc.catalogue.count() if svc.catalogue else 0
        info["usage_gb"] = round((svc.catalogue.usage_bytes() if svc.catalogue else 0) / 2**30, 2)
        info["jobs_indexed"] = svc.catalogue.jobs_indexed() if svc.catalogue else 0
        return info

    @app.get("/project/presets")
    async def presets_get():
        ws, _, _ = svc.require_project()
        from .fsio import read_json_or
        return read_json_or(ws.path / "generate" / "presets.json", {"presets": [], "last": None})

    @app.put("/project/presets")
    async def presets_put(body: dict):
        ws, _, _ = svc.require_project()
        from .fsio import atomic_write_json
        atomic_write_json(ws.path / "generate" / "presets.json", body)
        return body

    @app.get("/snippets")
    async def snippets_get():
        from .fsio import read_json_or
        return read_json_or(svc.app.state_dir / "snippets.json", {"snippets": []})

    @app.put("/snippets")
    async def snippets_put(body: dict):
        from .fsio import atomic_write_json
        atomic_write_json(svc.app.state_dir / "snippets.json", body)
        return body

    @app.get("/projects")
    async def projects():
        return {"last": svc.app.record.last_project, "recents": svc.app.record.recents}

    # ---- assets ---------------------------------------------------------------------------------
    @app.get("/assets", response_model=AssetPage)
    async def assets_list(q: Annotated[AssetQuery, Query()]):
        _, cat, _ = svc.require_project()
        return await asyncio.to_thread(cat.list, q)

    @app.get("/assets/groups", response_model=list[GroupHeader])
    async def assets_groups(q: Annotated[AssetQuery, Query()]):
        _, cat, _ = svc.require_project()
        return await asyncio.to_thread(cat.groups, q)

    @app.get("/assets/counts")
    async def assets_counts():
        _, cat, _ = svc.require_project()
        return await asyncio.to_thread(cat.counts)

    @app.get("/assets/tags")
    async def assets_tags():
        _, cat, _ = svc.require_project()
        return {"items": cat.tags()}

    @app.patch("/assets/bulk")
    async def assets_bulk(body: BulkPatch):
        _, cat, _ = svc.require_project()
        recs = cat.patch_many(body.ids, body.changes)
        for r in recs:
            svc.hub.broadcast("asset.updated", r.model_dump())
        return {"items": [r.model_dump() for r in recs]}

    @app.post("/assets/trash")
    async def assets_trash(body: IdList):
        _, cat, _ = svc.require_project()
        recs = cat.trash(body.ids)
        for r in recs:
            svc.hub.broadcast("asset.updated", r.model_dump())
        return {"trashed": [r.id for r in recs]}

    @app.post("/assets/restore")
    async def assets_restore(body: IdList):
        _, cat, _ = svc.require_project()
        recs = cat.restore(body.ids)
        for r in recs:
            svc.hub.broadcast("asset.updated", r.model_dump())
        return {"restored": [r.id for r in recs]}

    @app.post("/assets/purge")
    async def assets_purge(body: PurgeRequest):
        _, cat, _ = svc.require_project()
        gone = await asyncio.to_thread(cat.purge, body.ids, body.older_than_days)
        if len(gone) > 50:                                # emptying a 10k trash: one event, the clients reload (not 10k frames)
            svc.hub.broadcast("catalogue.changed", {"purged": len(gone)})
        else:
            for i in gone:
                svc.hub.broadcast("asset.deleted", {"id": i})
        return {"purged": len(gone), "ids": gone if len(gone) <= 50 else []}

    @app.get("/lineage/tree/{root_id}")
    async def lineage_tree(root_id: str):
        _, cat, _ = svc.require_project()
        return cat.lineage_tree(root_id)

    # ---- collections ----------------------------------------------------------------------------
    @app.get("/collections", response_model=list[CollectionRecord])
    async def collections_list():
        _, cat, _ = svc.require_project()
        return cat.collections()

    @app.post("/collections", response_model=CollectionRecord)
    async def collections_create(body: CollectionCreate):
        _, cat, _ = svc.require_project()
        rec = cat.collection_create(body.name, body.kind, body.filter)
        svc.hub.broadcast("collection.changed", {"id": rec.id})
        return rec

    @app.patch("/collections/{cid}", response_model=CollectionRecord)
    async def collections_patch(cid: str, body: CollectionPatch):
        _, cat, _ = svc.require_project()
        rec = cat.collection_update(cid, name=body.name, kind=body.kind, filter_=body.filter)
        if not rec:
            raise HTTPException(404, "collection not found")
        svc.hub.broadcast("collection.changed", {"id": cid})
        return rec

    @app.delete("/collections/{cid}")
    async def collections_delete(cid: str):
        _, cat, _ = svc.require_project()
        if not cat.collection_delete(cid):
            raise HTTPException(404, "collection not found")
        svc.hub.broadcast("collection.changed", {"id": cid})
        return {"deleted": cid}

    @app.post("/collections/{cid}/assets")
    async def collections_add(cid: str, body: IdList):
        _, cat, _ = svc.require_project()
        n = cat.collection_add(cid, body.ids)
        svc.hub.broadcast("collection.changed", {"id": cid})
        return {"count": n}

    @app.post("/collections/{cid}/assets/remove")
    async def collections_remove(cid: str, body: IdList):
        _, cat, _ = svc.require_project()
        n = cat.collection_remove(cid, body.ids)
        svc.hub.broadcast("collection.changed", {"id": cid})
        return {"count": n}

    @app.get("/assets/{asset_id}")
    async def asset_get(asset_id: str):
        _, cat, _ = svc.require_project()
        rec = cat.get(asset_id)
        if not rec:
            raise HTTPException(404, "asset not found")
        return rec.model_dump()

    @app.patch("/assets/{asset_id}")
    async def asset_patch(asset_id: str, body: AssetPatch):
        _, cat, _ = svc.require_project()
        rec = cat.patch(asset_id, body.model_dump(exclude_none=True))
        if not rec:
            raise HTTPException(404, "asset not found")
        svc.hub.broadcast("asset.updated", rec.model_dump())
        return rec.model_dump()

    @app.delete("/assets/{asset_id}")
    async def asset_delete(asset_id: str):
        _, cat, _ = svc.require_project()
        if not cat.delete(asset_id):
            raise HTTPException(404, "asset not found")
        svc.hub.broadcast("asset.deleted", {"id": asset_id})
        return {"deleted": asset_id}

    @app.get("/assets/{asset_id}/file")
    async def asset_file(asset_id: str):
        _, cat, _ = svc.require_project()
        rec = cat.get(asset_id)
        if not rec:
            raise HTTPException(404, "asset not found")
        return FileResponse(cat.abs_path(rec), headers={"Cache-Control": "private, max-age=31536000, immutable", "ETag": f'"{rec.sha256}"'})

    @app.get("/thumbs/{asset_id}/{size}")
    async def thumb(asset_id: str, size: int):
        ws, cat, _ = svc.require_project()
        p = ws.thumb_path(asset_id, size)
        if not p.is_file():
            rec = cat.get(asset_id)
            if not rec:
                raise HTTPException(404, "asset not found")
            await asyncio.to_thread(cat.make_thumbs, rec)
            if not p.is_file():
                raise HTTPException(404, "no thumbnail")
        return FileResponse(p, media_type="image/webp", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @app.get("/lineage/{asset_id}")
    async def lineage(asset_id: str):
        _, cat, _ = svc.require_project()
        return cat.lineage(asset_id)

    @app.post("/assets/import")
    async def assets_import(body: ImportRequest):
        _, cat, _ = svc.require_project()
        out = []
        files: list[Path] = []
        for p in body.paths:
            src = Path(p)
            if src.is_dir():
                files += sorted(x for x in src.iterdir() if x.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"))
            elif src.is_file():
                files.append(src)
            else:
                raise HTTPException(400, f"not a file or folder: {p}")
        for src in files:
            meta = parse_image_metadata(src) if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else {}
            kind = "video" if src.suffix.lower() in (".mp4", ".webm") else "image"
            rec = await asyncio.to_thread(cat.ingest_file, src, kind=kind, move=False, suite=body.suite, prompt_text=meta.get("prompt_text"),
                                          prompt_json=meta.get("prompt_json"), seed=meta.get("seed") if isinstance(meta.get("seed"), int) else None,
                                          params={"imported_from": str(src), **{k: v for k, v in meta.items() if k not in ("prompt_text", "prompt_json", "seed", "w", "h")}})
            rec = await asyncio.to_thread(cat.make_thumbs, rec)
            svc.hub.broadcast("asset.created", rec.model_dump())
            out.append(rec.model_dump())
        return {"items": out}

    @app.post("/catalogue/rebuild")
    async def catalogue_rebuild():
        _, cat, _ = svc.require_project()
        n = await asyncio.to_thread(cat.rebuild)
        return {"indexed": n}

    # ---- documents (10 §7, §13) ---------------------------------------------------------------------
    def _docs() -> DocumentStore:
        svc.require_project()
        assert svc.documents is not None
        return svc.documents

    @app.get("/documents")
    async def documents_list():
        return {"items": _docs().list()}

    @app.post("/documents")
    async def documents_create(body: DocumentCreate):
        import numpy as np
        from PIL import Image
        docs = _docs()
        _, cat, _ = svc.require_project()
        base = None
        name = body.name
        w, h = body.w, body.h
        if body.from_asset:
            a = cat.get(body.from_asset)
            if not a:
                raise HTTPException(404, "asset not found")

            def decode(p: Path) -> np.ndarray:
                with Image.open(p) as im:
                    return np.asarray(im.convert("RGBA"))
            base = await asyncio.to_thread(decode, cat.abs_path(a))      # B11: a 4K decode does not block the event loop
            h, w = base.shape[:2]
            name = name or f"{a.model_id or a.suite} {a.seed or a.id[-6:]}"
        if not w or not h:
            raise HTTPException(422, "w and h are required without from_asset")
        od = await asyncio.to_thread(docs.create, name or "Untitled", int(w), int(h), body.background, body.from_asset, base)
        svc.hub.broadcast("document.changed", {"id": od.doc.id})
        return od.doc.model_dump()

    @app.get("/documents/{doc_id}")
    async def documents_get(doc_id: str):
        od = await asyncio.to_thread(_docs().get, doc_id)
        return od.doc.model_dump()

    @app.put("/documents/{doc_id}")
    async def documents_put(doc_id: str, body: dict):
        """Replace the stack. The reply lists raster layers / masks the server has no bytes for, so the editor uploads
        them before `/save` even when it does not consider them dirty (B15: delete · save · undo · save)."""
        od = await asyncio.to_thread(_docs().update_stack, doc_id, body)
        px, mk = od.missing_pixels()
        return od.doc.model_dump() | {"missing_pixels": px, "missing_masks": mk}

    @app.get("/documents/{doc_id}/layers/{lid}/pixels")
    async def layer_pixels_get(doc_id: str, lid: str, kind: str = "image", raw: int = 0):
        import numpy as np
        from PIL import Image
        od = await asyncio.to_thread(_docs().get, doc_id)
        arr = od.masks.get(lid) if kind == "mask" else od.pixels.get(lid)
        if arr is None:
            raise HTTPException(404, "no pixels for this layer")
        if raw:
            return Response(content=arr.tobytes(), media_type="application/octet-stream",
                            headers={"X-Loom-Width": str(arr.shape[1]), "X-Loom-Height": str(arr.shape[0]), "X-Loom-Channels": str(1 if arr.ndim == 2 else 4), "Cache-Control": "no-store"})
        import io
        buf = io.BytesIO()
        Image.fromarray(arr, "L" if arr.ndim == 2 else "RGBA").save(buf, "PNG", compress_level=3)
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.put("/documents/{doc_id}/layers/{lid}/pixels")
    async def layer_pixels_put(doc_id: str, lid: str, request: Request, w: int, h: int, kind: str = "image"):
        """Raw uint8 body: RGBA (w·h·4 bytes) for images, grey (w·h) for masks; the fast path from the compositor (E2)."""
        import numpy as np
        od = await asyncio.to_thread(_docs().get, doc_id)
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

    @app.post("/documents/{doc_id}/save")
    async def documents_save(doc_id: str):
        od = await asyncio.to_thread(_docs().get, doc_id)
        await asyncio.to_thread(od.save)
        svc.hub.broadcast("document.changed", {"id": doc_id, "saved_at": od.doc.saved_at})
        return od.doc.model_dump()

    @app.post("/documents/{doc_id}/flatten")
    async def documents_flatten(doc_id: str, body: FlattenRequest):
        from PIL import Image
        _, cat, _ = svc.require_project()
        od = await asyncio.to_thread(_docs().get, doc_id)
        merged = await asyncio.to_thread(od.flatten)
        out = svc.ws.temp_dir / "flatten" / f"{doc_id}.png"   # type: ignore[union-attr]
        out.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(lambda: Image.fromarray(merged, "RGBA").save(out, "PNG"))
        if not body.to_catalogue:
            return {"path": str(out)}
        src = cat.get(od.doc.source_asset_id) if od.doc.source_asset_id else None
        rec = await asyncio.to_thread(cat.ingest_file, out, kind="image", move=True, suite="edit", parents=[src.id] if src else [],
                                      model_id=src.model_id if src else None, seed=src.seed if src else None, prompt_text=src.prompt_text if src else None,
                                      params={"document_id": doc_id, "document_name": body.name or od.doc.name, "layers": len(list(od.doc.walk()))})
        rec = await asyncio.to_thread(cat.make_thumbs, rec)
        if src:
            cat.patch(src.id, {"has_document": True})
            svc.hub.broadcast("asset.updated", cat.get(src.id).model_dump())   # type: ignore[union-attr]
        od.doc.meta["last_flatten_asset"] = rec.id
        svc.hub.broadcast("asset.created", rec.model_dump())
        return {"asset": rec.model_dump()}

    @app.post("/documents/{doc_id}/export")
    async def documents_export(doc_id: str, body: ExportRequest):
        import io
        from PIL import Image
        if body.format != "png":
            raise HTTPException(422, "the orchestrator exports PNG; PSD is written by the editor (ag-psd)")
        od = await asyncio.to_thread(_docs().get, doc_id)
        merged = await asyncio.to_thread(od.flatten)
        buf = io.BytesIO()
        Image.fromarray(merged, "RGBA").save(buf, "PNG")
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{od.doc.name}.png"'})

    @app.post("/documents/{doc_id}/compare")
    async def documents_compare(doc_id: str, request: Request, w: int, h: int):
        """Raw straight-alpha RGBA of the editor's GPU composite (w·h·4 bytes) → per-channel delta against the exact
        flatten (10 §14 item 1). Both images are kept under temp/compare for inspection; the result lands in doc.meta."""
        import io
        from datetime import datetime, timezone
        import numpy as np
        from PIL import Image
        from .compose import srgb_delta
        od = await asyncio.to_thread(_docs().get, doc_id)
        body = await request.body()
        if len(body) != w * h * 4:
            raise HTTPException(400, f"expected {w * h * 4} bytes for {w}×{h}×4, got {len(body)}")
        if (w, h) != (od.doc.w, od.doc.h):
            raise HTTPException(400, f"composite is {w}×{h}, the document is {od.doc.w}×{od.doc.h}")
        gpu = np.frombuffer(body, dtype=np.uint8).reshape((h, w, 4)).copy()
        exact = await asyncio.to_thread(od.flatten)
        d = srgb_delta(exact, gpu)
        rgb = srgb_delta(exact[..., :3], gpu[..., :3])
        d = {"mean": d["mean"], "p99": d["p99"], "max": d["max"], "rgb_mean": rgb["mean"], "rgb_p99": rgb["p99"], "rgb_max": rgb["max"],
             "w": w, "h": h, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        out = svc.ws.temp_dir / "compare"   # type: ignore[union-attr]
        out.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(lambda: (Image.fromarray(exact, "RGBA").save(out / f"{doc_id}-exact.png"), Image.fromarray(gpu, "RGBA").save(out / f"{doc_id}-gpu.png")))
        del io
        od.doc.meta["last_compare"] = d
        return d

    @app.get("/documents/{doc_id}/thumbnail")
    async def documents_thumbnail(doc_id: str):
        import io
        import zipfile
        docs = _docs()
        p = docs.path_for(doc_id)
        if not p.is_file():
            raise HTTPException(404, "no document")
        with zipfile.ZipFile(p) as z:
            data = z.read("Thumbnails/thumbnail.png") if "Thumbnails/thumbnail.png" in z.namelist() else z.read("mergedimage.png")
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/documents/{doc_id}/selection")
    async def documents_selection_get(doc_id: str):
        """The document's selection as raw grey bytes (the AI Select result lands here, M5 slice 2)."""
        od = await asyncio.to_thread(_docs().get, doc_id)
        if od.selection is None:
            raise HTTPException(404, "no selection")
        sel = od.selection
        return Response(content=sel.tobytes(), media_type="application/octet-stream",
                        headers={"X-Loom-Width": str(sel.shape[1]), "X-Loom-Height": str(sel.shape[0]), "X-Loom-Channels": "1", "Cache-Control": "no-store"})

    @app.put("/documents/{doc_id}/selection")
    async def documents_selection_put(doc_id: str, request: Request, w: int = 0, h: int = 0):
        """The editor's selection as raw grey bytes (w·h); an empty body clears it. The M5 edit jobs read it."""
        import numpy as np
        od = await asyncio.to_thread(_docs().get, doc_id)
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

    @app.post("/documents/{doc_id}/ai")
    async def documents_ai(doc_id: str, body: JobSubmit):
        """Queue an inpaint / refine / upscale job on this document (10 §13); results come back as layers
        (`document.changed` events with `added`) or, for upscale, as a Catalogue asset too."""
        _, _, q = svc.require_project()
        await asyncio.to_thread(_docs().get, doc_id)            # 404 if the document does not exist
        recipe = dict(body.recipe)
        if recipe.get("kind") not in ("inpaint", "i2i", "upscale", "segment"):
            raise HTTPException(422, "document jobs are inpaint, i2i (refine), upscale or segment (AI Select)")
        recipe["document_id"] = doc_id
        try:
            jobs = q.submit(recipe, stage=body.stage)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"jobs": [j.model_dump() for j in jobs]}

    @app.post("/documents/{doc_id}/close")
    async def documents_close(doc_id: str):
        _docs().close(doc_id)
        return {"closed": doc_id}

    @app.delete("/documents/{doc_id}")
    async def documents_delete(doc_id: str):
        if not _docs().delete(doc_id):
            raise HTTPException(404, "no document")
        svc.hub.broadcast("document.changed", {"id": doc_id, "deleted": True})
        return {"deleted": doc_id}

    # ---- jobs / queue ---------------------------------------------------------------------------
    # ---- clips (M6, 11 §10): PNG master + h264 proxy per clip; frame harvest with lineage -------------------------------
    @app.get("/clips")
    async def clips_list():
        ws, _, _ = svc.require_project()
        return {"items": [c.model_dump() for c in ClipStore(ws).list()]}

    @app.get("/clips/{clip_id}")
    async def clip_get(clip_id: str):
        ws, _, _ = svc.require_project()
        rec = ClipStore(ws).get(clip_id)
        if not rec:
            raise HTTPException(404, "clip not found")
        return rec.model_dump()

    @app.get("/clips/{clip_id}/proxy.mp4")
    async def clip_proxy(clip_id: str):
        ws, _, _ = svc.require_project()
        rec = ClipStore(ws).get(clip_id)
        if not rec or not rec.proxy_path:
            raise HTTPException(404, "proxy not ready")
        return FileResponse(ws.path / rec.proxy_path, media_type="video/mp4", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @app.get("/clips/{clip_id}/frames/{name}")
    async def clip_frame(clip_id: str, name: str):
        ws, _, _ = svc.require_project()
        store = ClipStore(ws)
        rec = store.get(clip_id)
        try:
            n = int(name.split(".")[0])
        except ValueError:
            raise HTTPException(400, "a frame index is expected, e.g. 37.png")
        if not rec or n < 0 or n >= rec.frames:
            raise HTTPException(404, "frame not found")
        return FileResponse(store.frame_path(clip_id, n), media_type="image/png", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @app.post("/clips/{clip_id}/identity")
    async def clip_identity(clip_id: str):
        """FaceSim advisory on demand (11 §6): cosine similarity of the start frame's face across the clip."""
        ws, cat, _ = svc.require_project()
        store = ClipStore(ws)
        rec = store.get(clip_id)
        if not rec:
            raise HTTPException(404, "clip not found")
        if not facesim.available(svc.app.settings.models_root):
            raise HTTPException(409, "FaceSim weights are not fetched (scripts/fetch_facesim.py)")
        start = cat.get(rec.start_asset_id)
        ref = cat.abs_path(start) if start else None
        rec.identity = await asyncio.to_thread(compute_identity, svc.app.settings.models_root, store, rec, ref)
        store.save(rec)
        svc.hub.broadcast("clip.updated", {"clip_id": rec.id, "identity": rec.identity})
        return rec.model_dump()

    @app.post("/clips/{clip_id}/extract")
    async def clip_extract(clip_id: str, body: ClipExtract):
        """Master frames → Catalogue images with `frame-extract` lineage from the clip's asset (11 §6)."""
        ws, cat, _ = svc.require_project()
        store = ClipStore(ws)
        rec = store.get(clip_id)
        if not rec:
            raise HTTPException(404, "clip not found")
        wanted = sorted({n for n in body.frames if 0 <= n < rec.frames})[:64]
        if not wanted:
            raise HTTPException(422, "no valid frame indices")
        out = []
        for n in wanted:
            tmp = ws.temp_dir / "extract" / f"{rec.id}_{n:06d}.png"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(store.frame_path(rec.id, n).read_bytes())
            a = await asyncio.to_thread(cat.ingest_file, tmp, kind="image", move=True, suite="animate", lineage_kind="frame-extract", job_id=rec.job_id, batch_id=rec.batch_id,
                                        model_id=rec.model_id, seed=rec.seed, prompt_text=rec.prompt, parents=[rec.asset_id] if rec.asset_id else [],
                                        params={"clip_id": rec.id, "frame_index": n, "fps": rec.fps, "time_s": round(n / rec.fps, 3), "preset": rec.preset})
            a = await asyncio.to_thread(cat.make_thumbs, a)
            svc.hub.broadcast("asset.created", a.model_dump())
            out.append(a.model_dump())
            rec.extracted_asset_ids.append(a.id)
        store.save(rec)
        return {"items": out, "clip": rec.model_dump()}

    @app.post("/jobs")
    async def jobs_submit(body: JobSubmit):
        _, _, q = svc.require_project()
        try:
            jobs = q.submit(body.recipe, stage=body.stage)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"jobs": [j.model_dump() for j in jobs]}

    @app.post("/jobs/{job_id}/release")
    async def job_release(job_id: str):
        _, _, q = svc.require_project()
        out = q.release(job_id)
        if not out:
            raise HTTPException(409, "job is not staged")
        return {"released": [j.id for j in out]}

    @app.post("/queue/release")
    async def queue_release():
        _, _, q = svc.require_project()
        return {"released": [j.id for j in q.release()]}

    @app.get("/jobs")
    async def jobs_list(status: str | None = None):
        _, _, q = svc.require_project()
        return {"items": q.list(status)}

    @app.get("/jobs/{job_id}")
    async def job_get(job_id: str):
        _, _, q = svc.require_project()
        j = q.get(job_id)
        if not j:
            raise HTTPException(404, "job not found")
        return j.model_dump()

    @app.post("/jobs/{job_id}/cancel")
    async def job_cancel(job_id: str):
        _, _, q = svc.require_project()
        if not await q.cancel(job_id):
            raise HTTPException(409, "job is not cancellable")
        return {"cancelled": job_id}

    @app.delete("/jobs/{job_id}")
    async def job_delete(job_id: str):
        _, _, q = svc.require_project()
        if not q.delete(job_id):
            raise HTTPException(409, "only finished jobs can be deleted")
        return {"deleted": job_id}

    @app.get("/queue")
    async def queue_get():
        _, _, q = svc.require_project()
        return q.state()

    @app.post("/queue/pause")
    async def queue_pause():
        _, _, q = svc.require_project()
        q.pause()
        return q.state()

    @app.post("/queue/unpause")
    async def queue_unpause():
        _, _, q = svc.require_project()
        q.unpause()
        return q.state()

    # ---- models ---------------------------------------------------------------------------------
    @app.get("/models")
    async def models(include_retired: bool = False):
        return {"items": svc.roster.listing(include_retired), "models_root": str(svc.app.models_root),
                "scanned_at": svc.roster.scanned_at, "fetches": {k: v.state() for k, v in svc.fetches.items()}}

    @app.post("/models/scan")
    async def models_scan():
        svc.roster.scan()
        return {"items": svc.roster.listing(), "unlisted": svc.roster.unlisted_files()}

    @app.get("/models/unlisted")
    async def models_unlisted():
        return {"items": svc.roster.unlisted_files()}

    @app.post("/models/fetch")
    async def models_fetch(body: FetchRequest):
        entry = ROSTER_BY_ID.get(body.model_id)
        if not entry:
            raise HTTPException(404, "unknown model id")
        if svc.app.settings.variant == "open" and "open" not in entry.variants:
            raise HTTPException(403, "model is not part of the open variant")
        job = svc.fetches.get(body.model_id)
        if job and job.status in ("queued", "downloading", "hashing"):
            return job.state()
        job = FetchJob(entry, svc.app.models_root, svc.hub, svc.app.settings.hf_home)
        svc.fetches[body.model_id] = job
        job.start()
        return job.state()

    @app.post("/models/{model_id}/verify")
    async def models_verify(model_id: str):
        try:
            r = svc.roster.resolve(model_id)
        except KeyError:
            raise HTTPException(404, "unknown model id")
        if not r.path:
            raise HTTPException(404, f"{model_id} is {r.health}")
        digest = await asyncio.to_thread(sha256_of, Path(r.path))
        return {"model_id": model_id, "sha256": digest, "matches_ledger": (r.sha256 == digest) if r.sha256 else None}

    # ---- engine ---------------------------------------------------------------------------------
    @app.get("/engine")
    async def engine_get():
        return await svc.engine.health()

    @app.post("/engine/start")
    async def engine_start():
        try:
            return await svc.engine.start()
        except RuntimeError as e:
            raise HTTPException(503, str(e))

    @app.post("/engine/stop")
    async def engine_stop():
        return await svc.engine.stop()

    @app.post("/engine/restart")
    async def engine_restart():
        return await svc.engine.restart()

    @app.post("/engine/free")
    async def engine_free():
        await svc.engine.client.free()
        return {"freed": True}

    # ---- blobs ----------------------------------------------------------------------------------
    def _blob_path(sha: str) -> Path:
        ws, _, _ = svc.require_project()
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise HTTPException(400, "blob id must be a lowercase sha256")
        return ws.temp_dir / "blobs" / sha

    @app.put("/blobs/{sha}")
    async def blob_put(sha: str, request: Request):
        dest = _blob_path(sha)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = _tmp_for(dest)                            # B11: unique per writer — two uploads of one blob never share a temp file
        h = hashlib.sha256()
        size = 0
        try:
            with tmp.open("wb") as f:
                async for chunk in request.stream():
                    f.write(chunk)
                    h.update(chunk)
                    size += len(chunk)
            if h.hexdigest() != sha:
                raise HTTPException(400, "body sha256 does not match the blob id")
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        return {"sha256": sha, "bytes": size}

    @app.get("/blobs/{sha}")
    async def blob_get(sha: str):
        p = _blob_path(sha)
        if not p.is_file():
            raise HTTPException(404, "blob not found")
        return FileResponse(p, media_type="application/octet-stream")

    @app.post("/shutdown")
    async def shutdown():
        """Graceful exit for the shell (06 §1): the lifespan teardown stops the queue (clean mark) and the engine."""
        fn = getattr(app.state, "request_shutdown", None)
        if fn is None:
            raise HTTPException(501, "no shutdown hook installed")
        asyncio.get_running_loop().call_later(0.2, fn)
        return {"shutting_down": True}

    # ---- events ---------------------------------------------------------------------------------
    @app.websocket("/events")
    async def events(ws: WebSocket, token: str | None = None):
        if token != svc.app.token:
            await ws.close(code=4401)
            return
        await ws.accept()
        svc.hub.attach(ws, hello={"seq": 0, "type": "hello", "data": {"version": __version__, "recent": svc.hub.recent[-20:]}})
        try:
            while True:
                msg = await ws.receive_text()
                if msg == "ping":
                    await ws.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            pass
        finally:
            svc.hub.detach(ws)

    return app
