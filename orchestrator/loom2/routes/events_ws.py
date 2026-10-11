"""`WS /events` (06 §2): job, asset, document, clip, group, queue, engine and model events with a short replay on connect."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import __version__
from .deps import Svc

router = APIRouter(tags=["events"])


AUTH_TIMEOUT_S = 2.0


@router.websocket("/events")
async def events(svc: Svc, ws: WebSocket):
    """D67: the socket connects without a credential (none in the URL, so none in a log) and must send `{"type": "auth", "token": …}`
    within 2 s; anything else closes it with 4401."""
    await ws.accept()
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), AUTH_TIMEOUT_S))
        ok = isinstance(first, dict) and first.get("type") == "auth" and first.get("token") == svc.app.token
    except (asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        ok = False
    if not ok:
        try:
            await ws.close(code=4401)
        except RuntimeError:
            pass
        return
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
