"""Shared route dependencies (D37). Handlers take `svc: Svc` and reach the open project through `svc.require_project()`,
`svc.require_groups()` and `svc.require_documents()`, which raise 409 when no project is open.

Rule: SQLite and file work in a handler goes through `await asyncio.to_thread(...)` — the catalogue and the group store guard
themselves with locks. The job queue is the exception: it is not thread-safe, so `JobQueue` calls stay on the event loop.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from ..services import Services


def get_services(conn: HTTPConnection) -> Services:
    """Works for HTTP and WebSocket routes alike."""
    return conn.app.state.services


Svc = Annotated[Services, Depends(get_services)]
