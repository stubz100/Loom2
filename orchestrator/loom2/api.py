"""The orchestrator's HTTP + WebSocket surface (06 §6). Bytes go over loopback HTTP with 4 MiB chunks (E2/D4);
events over `/events`; every mutating call needs `X-Loom-Token` (per-launch token, injected by the shell).

This module assembles the app (D37): lifespan, CORS, the token gate, error mapping and the per-domain routers in
`routes/`. Routes reach the live state (`services.Services`) through `routes/deps.py`.
"""
from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from pydantic.json_schema import models_json_schema

from . import __version__
from .documents import DocumentTooNew, StaleStack
from .fsio import StateError
from .groups import GroupLocked, GroupNotFound, StaleGroup
from .recipes import I2I, I2V, T2I, Inpaint, Segment, Upscale
from .routes import ROUTERS
from .schemas import EVENT_FRAMES
from .services import Services

RECIPES = (T2I, I2I, Inpaint, Upscale, Segment, I2V)

FileResponse.chunk_size = 4 * 2**20   # E2: 64 KiB chunks cap loopback at ~400 MiB/s; 4 MiB gives > 1 GiB/s
log = logging.getLogger("loom2.api")
# D67: routes anyone may call, and the media routes the read-only key (`?k=`) opens — pixels only, never settings, jobs or prompts
OPEN_PATHS = {"/health"}
DEV_DOCS = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
MEDIA_PATH = re.compile(r"^/(thumbs/[^/]+/[^/]+|assets/[^/]+/file|clips/[^/]+/(proxy\.mp4|frames/[^/]+)|documents/[^/]+/thumbnail|blobs/[^/]+|preset-icons/[^/]+/file|finals/[^/]+/layers/[^/]+/[^/]+/\d+|finals/[^/]+/composition/frame)$")   # D90: + the preset swatches; AE1: + the composition's frames
DEV_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
ERROR_STATUS = {StaleStack: 409,       # C1: the editor merges the newer server layers and saves again
                StaleGroup: 409,       # D34: the page reloads the group and redoes the drag
                DocumentTooNew: 409,   # R10: saved by a newer loom2 — refused, never opened and downgraded
                GroupNotFound: 404,
                GroupLocked: 423,      # 17 (D85): a final profile version's reference set
                StateError: 400}


def create_app(state_dir: Path | None = None, project: Path | None = None, ready_cb=None, variant: str | None = None) -> FastAPI:
    svc = Services(state_dir, variant)

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
            svc.effectcraft.stop()                                  # AE1: the editor's session ends with the orchestrator

    dev = os.environ.get("LOOM2_DEV") == "1"                  # D67: the interactive docs only in development
    app = FastAPI(title="loom2 orchestrator", version=__version__, lifespan=lifespan,
                  docs_url="/docs" if dev else None, redoc_url="/redoc" if dev else None, openapi_url="/openapi.json" if dev else None)
    open_paths = OPEN_PATHS | (DEV_DOCS if dev else set())
    app.state.services = svc
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["X-Loom-Width", "X-Loom-Height", "X-Loom-Channels", "Content-Disposition"])

    @app.middleware("http")
    async def token_gate(request: Request, call_next):
        """D67: every route needs the token (`X-Loom-Token`) but /health; the media GETs an <img> / <video> makes also take the
        read-only media key as `?k=`. CORS preflights pass (they carry no headers by design)."""
        path = request.url.path
        if request.method == "OPTIONS" or path in open_paths or request.headers.get("X-Loom-Token") == svc.app.token:
            return await call_next(request)
        if request.method in ("GET", "HEAD") and MEDIA_PATH.match(path) and request.query_params.get("k") == svc.app.media_key:
            return await call_next(request)
        return JSONResponse({"detail": "missing or wrong X-Loom-Token"}, status_code=401)

    for exc, status in ERROR_STATUS.items():
        app.add_exception_handler(exc, _status_handler(status))
    for router in ROUTERS:
        app.include_router(router)
    app.openapi = _openapi_with_contract(app)
    return app


def _openapi_with_contract(app: FastAPI):
    """D38: the OpenAPI document also carries what no route declares — the WebSocket event frames (`EventFrame`) and the recipe
    models a job body holds (`Recipe`) — so `schema.d.ts` types `applyEvent` and the panels' recipe builders too."""
    def openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        models = [(m, "serialization") for m in EVENT_FRAMES] + [(m, "validation") for m in RECIPES]
        _, defs = models_json_schema(models, ref_template="#/components/schemas/{model}")
        comps = schema.setdefault("components", {}).setdefault("schemas", {})
        for name, s in defs.get("$defs", {}).items():
            comps.setdefault(name, s)
        comps["EventFrame"] = {"oneOf": [{"$ref": f"#/components/schemas/{m.__name__}"} for m in EVENT_FRAMES], "title": "EventFrame"}
        comps["Recipe"] = {"oneOf": [{"$ref": f"#/components/schemas/{m.__name__}"} for m in RECIPES], "title": "Recipe"}
        app.openapi_schema = schema
        return schema
    return openapi


def _status_handler(status: int):
    async def handle(_: Request, e: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=status)
    return handle
