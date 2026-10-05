"""The orchestrator's HTTP + WebSocket surface (06 §6). Bytes go over loopback HTTP with 4 MiB chunks (E2/D4);
events over `/events`; every mutating call needs `X-Loom-Token` (per-launch token, injected by the shell).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import __version__
from .catalogue import Catalogue
from .config import AppState
from .engine.graphs import PRESETS, VRAM_ESTIMATE_GB
from .engine.supervisor import EngineSupervisor
from .events import EventHub
from .fsio import StateError
from .queue import JobQueue
from .roster import ROSTER_BY_ID, Roster
from .tools.fetch import FetchJob, sha256_of
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
        self.fetches: dict[str, FetchJob] = {}

    # ---- project binding ------------------------------------------------------------------------
    async def open_project(self, path: Path) -> dict:
        await self.close_project()
        ws = Workspace.open(path)
        self.ws = ws
        self.catalogue = Catalogue(ws, self.app.settings.thumbnail_sizes)
        self.queue = JobQueue(ws, self.app, self.engine, self.roster, self.catalogue, self.hub)
        await self.queue.start()
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
        if self.ws:
            self.hub.broadcast("project.closed", {"path": str(self.ws.path)})
            self.ws = None

    def require_project(self) -> tuple[Workspace, Catalogue, JobQueue]:
        if not (self.ws and self.catalogue and self.queue):
            raise HTTPException(409, "no project is open")
        return self.ws, self.catalogue, self.queue


class ProjectCreate(BaseModel):
    path: str
    name: str
    format: dict | None = None
    size_cap_gb: float = 100.0


class ProjectOpen(BaseModel):
    path: str


class JobSubmit(BaseModel):
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


def create_app(state_dir: Path | None = None, project: Path | None = None, ready_cb=None) -> FastAPI:
    svc = Services(state_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc.roster.scan()
        target = project or (Path(svc.app.record.last_project) if svc.app.settings.reopen_last_project and svc.app.record.last_project else None)
        if target:
            try:
                await svc.open_project(Path(target))
            except StateError as e:
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
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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
                "engine_running": svc.engine.state()["running"], "variant": svc.app.settings.variant}

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
            models[mid] = {"family": e.family, "health": r.health, "steps": preset.steps, "guidance": preset.guidance, "distilled": preset.distilled,
                           "turbo": preset.turbo_lora is not None, "json_prompt": preset.json_prompt, "vram_gb": VRAM_ESTIMATE_GB.get(mid)}
        return {"recipes": ["t2i"], "models": models, "variant": svc.app.settings.variant, "vram_budget_gb": svc.app.settings.vram_budget_gb,
                "tiers": {"draft": {"flux2": [960, 544], "klein": [1280, 720]}, "hd": {"flux2": [1920, 1088]}}}

    @app.get("/settings")
    async def get_settings():
        return svc.app.settings.model_dump()

    @app.put("/settings")
    async def put_settings(patch: dict):
        s = svc.app.update_settings(patch)
        svc.roster = Roster(svc.app.models_root, [Path(p) for p in s.mounted_model_trees], s.variant).scan()
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

    @app.get("/projects")
    async def projects():
        return {"last": svc.app.record.last_project, "recents": svc.app.record.recents}

    # ---- assets ---------------------------------------------------------------------------------
    @app.get("/assets")
    async def assets_list(state: str | None = None, suite: str | None = None, model_id: str | None = None, job_id: str | None = None,
                          search: str | None = None, sort: str = "created_desc", limit: int = 200, cursor: str | None = None):
        _, cat, _ = svc.require_project()
        return cat.list(state=state, suite=suite, model_id=model_id, job_id=job_id, search=search, sort=sort, limit=min(limit, 1000), cursor=cursor)

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
        for p in body.paths:
            src = Path(p)
            if not src.is_file():
                raise HTTPException(400, f"not a file: {p}")
            rec = await asyncio.to_thread(cat.ingest_file, src, kind="image", move=False, suite=body.suite, params={"imported_from": str(src)})
            rec = await asyncio.to_thread(cat.make_thumbs, rec)
            svc.hub.broadcast("asset.created", rec.model_dump())
            out.append(rec.model_dump())
        return {"items": out}

    @app.post("/catalogue/rebuild")
    async def catalogue_rebuild():
        _, cat, _ = svc.require_project()
        n = await asyncio.to_thread(cat.rebuild)
        return {"indexed": n}

    # ---- jobs / queue ---------------------------------------------------------------------------
    @app.post("/jobs")
    async def jobs_submit(body: JobSubmit):
        _, _, q = svc.require_project()
        try:
            jobs = q.submit(body.recipe)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"jobs": [j.model_dump() for j in jobs]}

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
        r = svc.roster.resolve(model_id)
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
        tmp = dest.with_suffix(".part")
        h = hashlib.sha256()
        size = 0
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)
        if h.hexdigest() != sha:
            tmp.unlink(missing_ok=True)
            raise HTTPException(400, "body sha256 does not match the blob id")
        tmp.replace(dest)
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
        svc.hub.attach(ws)
        try:
            await ws.send_json({"seq": 0, "type": "hello", "data": {"version": __version__, "recent": svc.hub.recent[-20:]}})
            while True:
                msg = await ws.receive_text()
                if msg == "ping":
                    await ws.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            pass
        finally:
            svc.hub.detach(ws)

    return app
