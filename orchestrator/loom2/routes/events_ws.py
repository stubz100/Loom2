"""`WS /events` (06 §2): job, asset, document, clip, group, queue, engine and model events with a short replay on connect."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import __version__
from .deps import Svc

router = APIRouter(tags=["events"])


@router.websocket("/events")
async def events(svc: Svc, ws: WebSocket, token: str | None = None):
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
