"""The orchestrator's WebSocket event hub (06 §2): `job.*`, `asset.*`, `engine.*`, `model.*`, `disk.*` as JSON
frames; preview images as binary frames = 4-byte big-endian header length + JSON header + image bytes.

Each client has its own outbound queue drained by one sender task (B11): frames reach a client in broadcast order,
nothing is sent concurrently on one socket, and a slow client drops *previews* (never state frames) once its backlog
passes `max_pending`.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import logging
import struct
import threading
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
        self.run = secrets.token_hex(4)                 # V65: this hub's run — seqs of another run (an orchestrator restart) do not line up
        # K (three reviewers): finishers and routes broadcast from worker threads (asyncio.to_thread) — the seq and the history under a lock,
        # the clients' queues fed on the loop (a put from another thread did not wake it: a frame measured 3 s late; debug mode raised)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _on_loop(self) -> bool:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None and self._loop is None:
            self._loop = running
        return self._loop is None or running is self._loop

    def _deliver(self, fn, *args) -> None:
        if self._on_loop():
            fn(*args)
        elif self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(fn, *args)

    def replay(self, since: int, run: str | None) -> tuple[list[dict], bool]:
        """V65: the frames a reconnecting client missed (it names the last seq it applied and the run it saw) and whether some are gone —
        a gap: the client saw another run, or more frames passed than the history holds; it then fetches instead. A first connect
        (since 0) has nothing to catch up."""
        if since <= 0:
            return [], False
        if run != self.run or since > self.seq:
            return [], True
        missed = [f for f in self._recent if f["seq"] > since]
        return missed, len(missed) != self.seq - since

    def attach(self, ws: Any, hello: dict | None = None) -> None:
        c = _Client(ws)
        if hello is not None:
            c.queue.put_nowait(json.dumps(hello, default=str, ensure_ascii=False))
        self._loop = asyncio.get_running_loop()
        c.task = self._loop.create_task(self._sender(c), name="loom2-events-sender")
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
        with self._lock:
            self.seq += 1
            frame = {"seq": self.seq, "type": type_, "t": round(time.time(), 3), "data": data or {}}
            self._recent.append(frame)
            del self._recent[:-self._history]
            text = json.dumps(frame, default=str, ensure_ascii=False)
            self._deliver(self._put_text, text)                      # in seq order: off the loop it is queued on the loop, FIFO
        return frame

    def _put_text(self, text: str) -> None:
        for c in list(self._clients.values()):
            c.queue.put_nowait(text)

    def broadcast_binary(self, header: dict, payload: bytes) -> None:
        h = json.dumps({**header, "t": round(time.time(), 3)}, default=str).encode("utf-8")
        self._deliver(self._put_binary, struct.pack(">I", len(h)) + h + payload)

    def _put_binary(self, frame: bytes) -> None:
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
