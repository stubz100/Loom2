"""Async client for the headless ComfyUI engine (06 §3b): REST for prompts, history, uploads and outputs; the
WebSocket for progress, previews and completion. One client per orchestrator; the queue owns submission order.
"""
from __future__ import annotations

import asyncio
import json
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import websockets


@dataclass
class EngineEvent:
    type: str                 # status | execution_start | executing | progress | executed | execution_success |
                              # execution_error | execution_cached | execution_interrupted | preview | ws_closed
    data: dict[str, Any]
    prompt_id: str | None = None
    binary: bytes | None = None


class EngineError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: float = 60.0) -> None:
        self.host, self.port = host, port
        self.base = f"http://{host}:{port}"
        self.client_id = uuid.uuid4().hex
        self._http = httpx.AsyncClient(base_url=self.base, timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---- REST -------------------------------------------------------------------------------------
    async def system_stats(self) -> dict:
        r = await self._http.get("/system_stats")
        r.raise_for_status()
        return r.json()

    async def is_up(self) -> bool:
        try:
            await self.system_stats()
            return True
        except (httpx.HTTPError, OSError):
            return False

    async def object_info(self, node_class: str | None = None) -> dict:
        r = await self._http.get(f"/object_info/{node_class}" if node_class else "/object_info")
        r.raise_for_status()
        return r.json()

    async def queue_prompt(self, graph: dict, extra: dict | None = None) -> str:
        body = {"prompt": graph, "client_id": self.client_id}
        if extra:
            body["extra_data"] = extra
        r = await self._http.post("/prompt", json=body)
        if r.status_code >= 400:
            try:
                detail = r.json()
            except ValueError:
                detail = r.text
            raise EngineError(f"/prompt rejected ({r.status_code}): {json.dumps(detail)[:2000]}")
        return r.json()["prompt_id"]

    async def history(self, prompt_id: str) -> dict | None:
        r = await self._http.get(f"/history/{prompt_id}")
        r.raise_for_status()
        return r.json().get(prompt_id)

    async def queue_state(self) -> dict:
        r = await self._http.get("/queue")
        r.raise_for_status()
        return r.json()

    async def interrupt(self) -> None:
        await self._http.post("/interrupt")

    async def free(self, unload_models: bool = True, free_memory: bool = True) -> None:
        await self._http.post("/free", json={"unload_models": unload_models, "free_memory": free_memory})

    async def upload_image(self, path: Path, subfolder: str = "", overwrite: bool = True, kind: str = "input") -> str:
        """Returns the name ComfyUI stored the file under (LoadImage enum value, with subfolder if any)."""
        path = Path(path)
        with path.open("rb") as f:
            r = await self._http.post("/upload/image", files={"image": (path.name, f, "application/octet-stream")},
                                      data={"subfolder": subfolder, "overwrite": "true" if overwrite else "false", "type": kind})
        r.raise_for_status()
        j = r.json()
        return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]

    async def view(self, filename: str, subfolder: str = "", kind: str = "output") -> bytes:
        r = await self._http.get("/view", params={"filename": filename, "subfolder": subfolder, "type": kind})
        r.raise_for_status()
        return r.content

    # ---- WebSocket --------------------------------------------------------------------------------
    async def events(self) -> AsyncIterator[EngineEvent]:
        """Yields engine events until the socket closes. Binary frames are previews (event 1, image type 1 jpeg / 2 png)."""
        url = f"ws://{self.host}:{self.port}/ws?clientId={self.client_id}"
        async with websockets.connect(url, max_size=64 * 2**20, ping_interval=20, ping_timeout=60) as ws:
            async for msg in ws:
                if isinstance(msg, (bytes, bytearray)):
                    if len(msg) >= 8:
                        ev_type, img_type = struct.unpack(">II", msg[:8])
                        if ev_type == 1:
                            yield EngineEvent(type="preview", data={"format": "jpeg" if img_type == 1 else "png"}, binary=bytes(msg[8:]))
                    continue
                try:
                    j = json.loads(msg)
                except ValueError:
                    continue
                data = j.get("data") or {}
                yield EngineEvent(type=j.get("type", ""), data=data, prompt_id=data.get("prompt_id"))
        yield EngineEvent(type="ws_closed", data={})


async def wait_for_engine(client: ComfyClient, timeout_s: float = 120.0, poll_s: float = 1.0) -> bool:
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    while loop.time() - t0 < timeout_s:
        if await client.is_up():
            return True
        await asyncio.sleep(poll_s)
    return False
