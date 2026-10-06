"""EventHub (B11): one ordered sender per client, previews dropped for a client that cannot keep up, state never dropped."""
from __future__ import annotations

import asyncio
import json

from loom2.events import EventHub


class _Sock:
    def __init__(self, delay: float = 0.0) -> None:
        self.frames: list[str | bytes] = []
        self.delay = delay

    async def send_text(self, t: str) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.frames.append(t)

    async def send_bytes(self, b: bytes) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.frames.append(b)


async def test_frames_arrive_in_broadcast_order_with_hello_first():
    hub = EventHub()
    ws = _Sock()
    hub.attach(ws, hello={"seq": 0, "type": "hello", "data": {}})
    for i in range(50):
        hub.broadcast("job.progress", {"i": i})
        if i % 10 == 0:
            hub.broadcast_binary({"type": "job.preview", "job_id": "job_x"}, b"\x89PNG" + bytes([i]))
    await asyncio.sleep(0.05)
    assert json.loads(ws.frames[0])["type"] == "hello"
    texts = [json.loads(f) for f in ws.frames if isinstance(f, str)]
    assert [t["data"]["i"] for t in texts[1:]] == list(range(50))
    assert sum(isinstance(f, bytes) for f in ws.frames) == 5
    assert hub.clients == 1
    hub.detach(ws)
    assert hub.clients == 0


async def test_slow_client_drops_previews_not_state():
    hub = EventHub(max_pending=5)
    slow = _Sock(delay=0.5)
    hub.attach(slow)
    for i in range(20):
        hub.broadcast("job.updated", {"i": i})
        hub.broadcast_binary({"type": "job.preview"}, b"p" + bytes([i]))
    assert hub.dropped > 0
    pending_text = sum(1 for _ in range(20))
    assert pending_text == 20                                   # every state frame is queued …
    hub.detach(slow)                                            # … and the queue dies with the client, not with the hub


async def test_gone_client_is_detached_on_first_failure():
    hub = EventHub()

    class Dead(_Sock):
        async def send_text(self, t: str) -> None:
            raise ConnectionError("gone")

    ws = Dead()
    hub.attach(ws)
    hub.broadcast("queue.state", {})
    await asyncio.sleep(0.05)
    assert hub.clients == 0
