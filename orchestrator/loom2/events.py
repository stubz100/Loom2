"""The orchestrator's WebSocket event hub (06 §2): `job.*`, `asset.*`, `engine.*`, `model.*`, `disk.*` as JSON
frames; preview images as binary frames = 4-byte big-endian header length + JSON header + image bytes.

Each client has its own outbound queue drained by one sender task (B11): frames reach a client in broadcast order,
nothing is sent concurrently on one socket, and a slow client drops *previews* (never state frames) once its backlog
passes `max_pending`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("loom2.events")


@dataclass
class _Client:
    ws: Any
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None


class EventHub:
    def __init__(self, history: int = 200, max_pending: int = 500) -> None:
        self._clients: dict[Any, _Client] = {}
        self._recent: list[dict] = []
        self._history = history
        self._max_pending = max_pending
        self.seq = 0
        self.dropped = 0

    def attach(self, ws: Any, hello: dict | None = None) -> None:
        c = _Client(ws)
        if hello is not None:
            c.queue.put_nowait(json.dumps(hello, default=str, ensure_ascii=False))
        c.task = asyncio.get_running_loop().create_task(self._sender(c), name="loom2-events-sender")
        self._clients[ws] = c

    def detach(self, ws: Any) -> None:
        c = self._clients.pop(ws, None)
        if c and c.task:
            c.task.cancel()

    @property
    def recent(self) -> list[dict]:
        return list(self._recent)

    @property
    def clients(self) -> int:
        return len(self._clients)

    def broadcast(self, type_: str, data: dict | None = None) -> dict:
        self.seq += 1
        frame = {"seq": self.seq, "type": type_, "t": round(time.time(), 3), "data": data or {}}
        self._recent.append(frame)
        del self._recent[:-self._history]
        text = json.dumps(frame, default=str, ensure_ascii=False)
        for c in list(self._clients.values()):
            c.queue.put_nowait(text)
        return frame

    def broadcast_binary(self, header: dict, payload: bytes) -> None:
        h = json.dumps({**header, "t": round(time.time(), 3)}, default=str).encode("utf-8")
        frame = struct.pack(">I", len(h)) + h + payload
        for c in list(self._clients.values()):
            if c.queue.qsize() >= self._max_pending:      # a client that cannot keep up loses previews, not state
                self.dropped += 1
                continue
            c.queue.put_nowait(frame)

    async def _sender(self, c: _Client) -> None:
        try:
            while True:
                item = await c.queue.get()
                if isinstance(item, (bytes, bytearray)):
                    await c.ws.send_bytes(item)
                else:
                    await c.ws.send_text(item)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a gone client is detached on its first failure
            log.debug("event client dropped: %s", e)
            self._clients.pop(c.ws, None)
