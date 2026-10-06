"""A fake ComfyUI for offline lifecycle tests (06 §9 "integration without GPU"): the REST surface the orchestrator
drives (`/system_stats`, `/object_info`, `/upload/image`, `/prompt`, `/history/{id}`, `/interrupt`, `/free`) and the
`/ws` event stream. Served by uvicorn on an ephemeral loopback port in a thread; the supervisor adopts it because it
already listens on the configured port.

Behaviours: "success" (writes a PNG under `<output_dir>/loom2/` and streams executing → progress → execution_success),
"silent" (accepts the prompt and never speaks again: the stall watchdog's case), "error" (execution_error).
The output image takes the size of the last uploaded `image.png` so inpaint paste-back gets the engine size it asked for.
"""
from __future__ import annotations

import asyncio
import io
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from PIL import Image


class FakeComfy:
    def __init__(self, object_info: dict, output_dir: Path, *, behaviour: str = "success", color=(255, 0, 255, 255),
                 object_info_delay: float = 0.0) -> None:
        self.object_info = json.loads(json.dumps(object_info))          # private copy: LoadImage's enum grows with uploads
        self.output_dir = Path(output_dir)
        self.behaviour = behaviour
        self.color = color
        self.object_info_delay = object_info_delay
        self.uploads: list[tuple[str, bytes]] = []
        self.prompts: list[dict] = []
        self.histories: dict[str, dict] = {}
        self.interrupts = 0
        self.frees: list[dict] = []
        self.object_info_calls = 0
        self._clients: set[WebSocket] = set()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.port = 0
        self.app = self._build()

    # ---- lifecycle --------------------------------------------------------------------------------
    def start(self) -> int:
        cfg = uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(cfg)
        self._thread = threading.Thread(target=self._server.run, name="fake-comfy", daemon=True)
        self._thread.start()
        t0 = time.time()
        while not self._server.started:
            if time.time() - t0 > 10:
                raise RuntimeError("fake ComfyUI did not start")
            time.sleep(0.02)
        self.port = self._server.servers[0].sockets[0].getsockname()[1]
        return self.port

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=10)

    # ---- helpers ----------------------------------------------------------------------------------
    def uploaded(self, name: str) -> list[bytes]:
        return [b for n, b in self.uploads if n == name]

    def _output_size(self) -> tuple[int, int]:
        for name, data in reversed(self.uploads):
            if name == "image.png":
                with Image.open(io.BytesIO(data)) as im:
                    return im.size
        return (64, 64)

    async def _send(self, msg: dict) -> None:
        for ws in list(self._clients):
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                self._clients.discard(ws)

    async def _execute(self, pid: str, graph: dict) -> None:
        await asyncio.sleep(0.05)
        save = next((n for n in graph.values() if n.get("class_type") == "SaveImage"), None)
        prefix = (save or {}).get("inputs", {}).get("filename_prefix", "loom2/out")
        subfolder, _, base = prefix.rpartition("/")
        await self._send({"type": "execution_start", "data": {"prompt_id": pid}})
        await self._send({"type": "executing", "data": {"prompt_id": pid, "node": "1"}})
        if self.behaviour == "silent":
            return
        if self.behaviour == "error":
            self.histories[pid] = {"outputs": {}, "status": {"completed": True, "status_str": "error"}}
            await self._send({"type": "execution_error", "data": {"prompt_id": pid, "node_type": "KSampler", "exception_message": "fake failure", "traceback": ["boom"]}})
            return
        for v in (1, 2):
            await self._send({"type": "progress", "data": {"prompt_id": pid, "value": v, "max": 2, "node": "1"}})
        vid = next((n for n in graph.values() if n.get("class_type") in ("WanImageToVideo", "WanFirstLastFrameToVideo", "LTXVImgToVideo")), None)
        if vid:                                                  # M6: a video graph decodes `length` frames; SaveImage writes one PNG each
            w, h, count = int(vid["inputs"].get("width", 64)), int(vid["inputs"].get("height", 64)), int(vid["inputs"].get("length", 1))
        else:
            (w, h), count = self._output_size(), 1
        out_dir = self.output_dir / subfolder if subfolder else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        n0 = sum(1 for p in out_dir.glob(f"{base}_*"))
        images = []
        for i in range(count):
            fname = f"{base}_{n0 + i + 1:05d}_.png"
            col = self.color if not vid else (self.color[0], (i * 29) % 256, self.color[2], 255)      # frames differ, so the proxy encode is real work
            Image.new("RGBA", (w, h), col).save(out_dir / fname)
            images.append({"filename": fname, "subfolder": subfolder, "type": "output"})
        self.histories[pid] = {"outputs": {"99": {"images": images}}, "status": {"completed": True, "status_str": "success"}}
        await self._send({"type": "executing", "data": {"prompt_id": pid, "node": None}})
        await self._send({"type": "execution_success", "data": {"prompt_id": pid}})

    # ---- routes -----------------------------------------------------------------------------------
    def _build(self) -> FastAPI:
        app = FastAPI()
        fake = self

        @app.get("/system_stats")
        async def system_stats():
            return {"system": {"comfyui_version": "fake-0.38.2", "python_version": "3.13"},
                    "devices": [{"name": "fake", "vram_total": 16 * 2**30, "vram_free": 12 * 2**30}]}

        @app.get("/object_info")
        async def object_info():
            fake.object_info_calls += 1
            if fake.object_info_delay:
                await asyncio.sleep(fake.object_info_delay)
            return fake.object_info

        @app.post("/upload/image")
        async def upload(image: UploadFile, subfolder: str = Form(""), overwrite: str = Form("true"), type: str = Form("input")):
            data = await image.read()
            name = image.filename or "upload.png"
            fake.uploads.append((name, data))
            enum = fake.object_info["LoadImage"]["input"]["required"]["image"][0]
            if name not in enum:
                enum.append(name)
            menum = fake.object_info.get("LoadImageMask", {}).get("input", {}).get("required", {}).get("image", [[]])[0]
            if isinstance(menum, list) and name not in menum:
                menum.append(name)
            return {"name": name, "subfolder": subfolder, "type": type}

        @app.post("/prompt")
        async def prompt(request: Request):
            body = await request.json()
            pid = uuid.uuid4().hex
            fake.prompts.append({"prompt_id": pid, "graph": body["prompt"], "client_id": body.get("client_id")})
            asyncio.get_running_loop().create_task(fake._execute(pid, body["prompt"]))
            return {"prompt_id": pid, "number": len(fake.prompts), "node_errors": {}}

        @app.get("/history/{pid}")
        async def history(pid: str):
            return {pid: fake.histories[pid]} if pid in fake.histories else {}

        @app.post("/interrupt")
        async def interrupt():
            fake.interrupts += 1
            return {}

        @app.post("/free")
        async def free(request: Request):
            fake.frees.append(await request.json())
            return {}

        @app.websocket("/ws")
        async def ws(sock: WebSocket):
            await sock.accept()
            fake._clients.add(sock)
            try:
                await sock.send_text(json.dumps({"type": "status", "data": {"status": {"exec_info": {"queue_remaining": 0}}}}))
                while True:
                    await sock.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                fake._clients.discard(sock)

        return app


def graph_image_name(graph: dict, class_type: str = "LoadImage") -> str | None:
    n = next((n for n in graph.values() if n.get("class_type") == class_type), None)
    return (n or {}).get("inputs", {}).get("image")

