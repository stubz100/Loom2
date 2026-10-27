"""Shared route dependencies (D37). Handlers take `svc: Svc` and reach the open project through `svc.require_project()`,
`svc.require_groups()` and `svc.require_documents()`, which raise 409 when no project is open.

Rule: SQLite and file work in a handler goes through `await asyncio.to_thread(...)` — the catalogue and the group store guard
themselves with locks. The job queue is the exception: it is not thread-safe, so `JobQueue` calls stay on the event loop.
"""
from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import Depends
from starlette.requests import HTTPConnection

from ..services import Services


def attachment(filename: str) -> dict[str, str]:
    """V36: a `Content-Disposition` for a download with any name — HTTP headers are latin-1, so a name with an em dash or an ellipsis
    used to raise in Starlette (a 500 on Export PNG). The ASCII fallback keeps what it can; `filename*` carries the name itself (RFC 6266)."""
    ascii_name = "".join(ch if 32 <= ord(ch) < 127 and ch not in '"\\' else "_" for ch in filename).strip() or "download"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"}


def get_services(conn: HTTPConnection) -> Services:
    """Works for HTTP and WebSocket routes alike."""
    return conn.app.state.services


Svc = Annotated[Services, Depends(get_services)]
