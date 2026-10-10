"""The orchestrator's HTTP + WebSocket surface (06 §6). Bytes go over loopback HTTP with 4 MiB chunks (E2/D4);
events over `/events`; every mutating call needs `X-Loom-Token` (per-launch token, injected by the shell).

This module assembles the app (D37): lifespan, CORS, the token gate, error mapping and the per-domain routers in
`routes/`. Routes reach the live state (`services.Services`) through `routes/deps.py`.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .documents import StaleStack
from .fsio import StateError
from .groups import GroupNotFound, StaleGroup
from .routes import ROUTERS
from .services import Services

FileResponse.chunk_size = 4 * 2**20   # E2: 64 KiB chunks cap loopback at ~400 MiB/s; 4 MiB gives > 1 GiB/s
log = logging.getLogger("loom2.api")
DEV_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
ERROR_STATUS = {StaleStack: 409,       # C1: the editor merges the newer server layers and saves again
                StaleGroup: 409,       # D34: the page reloads the group and redoes the drag
                GroupNotFound: 404,
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

    app = FastAPI(title="loom2 orchestrator", version=__version__, lifespan=lifespan)
    app.state.services = svc
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["X-Loom-Width", "X-Loom-Height", "X-Loom-Channels", "Content-Disposition"])

    @app.middleware("http")
    async def token_gate(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path not in ("/health",):
            if request.headers.get("X-Loom-Token") != svc.app.token:
                return JSONResponse({"detail": "missing or wrong X-Loom-Token"}, status_code=401)
        return await call_next(request)

    for exc, status in ERROR_STATUS.items():
        app.add_exception_handler(exc, _status_handler(status))
    for router in ROUTERS:
        app.include_router(router)
    return app


def _status_handler(status: int):
    async def handle(_: Request, e: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=status)
    return handle
