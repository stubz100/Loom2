"""The orchestrator's WebSocket event hub (06 §2): `job.*`, `asset.*`, `engine.*`, `model.*`, `disk.*` as JSON
frames; preview images as binary frames = 4-byte big-endian header length + JSON header + image bytes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from typing import Any

log = logging.getLogger("loom2.events")


class EventHub:
    def __init__(self, history: int = 200) -> None:
        self._clients: set[Any] = set()
        self._recent: list[dict] = []
        self._history = history
        self.seq = 0

    def attach(self, ws: Any) -> None:
        self._clients.add(ws)

    def detach(self, ws: Any) -> None:
        self._clients.discard(ws)

    @property
    def recent(self) -> list[dict]:
        return list(self._recent)

    def broadcast(self, type_: str, data: dict | None = None) -> dict:
        self.seq += 1
        frame = {"seq": self.seq, "type": type_, "t": round(time.time(), 3), "data": data or {}}
        self._recent.append(frame)
        del self._recent[:-self._history]
        text = json.dumps(frame, default=str, ensure_ascii=False)
        for ws in list(self._clients):
            asyncio.create_task(self._send(ws, text))
        return frame

    def broadcast_binary(self, header: dict, payload: bytes) -> None:
        h = json.dumps({**header, "t": round(time.time(), 3)}, default=str).encode("utf-8")
        frame = struct.pack(">I", len(h)) + h + payload
        for ws in list(self._clients):
            asyncio.create_task(self._send(ws, frame))

    async def _send(self, ws: Any, frame: str | bytes) -> None:
        try:
            if isinstance(frame, bytes):
                await ws.send_bytes(frame)
            else:
                await ws.send_text(frame)
        except Exception as e:  # a gone client is detached on its next failure
            log.debug("event client dropped: %s", e)
            self._clients.discard(ws)
