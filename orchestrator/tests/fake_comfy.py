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
        self.vram_free_gb = 12.0                                         # D69: tests set it low to see the engine.vram_pressure event
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
        outputs: dict = {"99": {"images": images}}
        save3d = next((k for k, n in graph.items() if n.get("class_type") == "Save3DAdvanced"), None)
        if save3d:                                                      # P18: a mesh graph writes one GLB (a real, minimal one — the browser's loader reads it)
            gprefix = graph[save3d]["inputs"].get("filename_prefix", "loom2/mesh")
            gsub, _, gbase = gprefix.rpartition("/")
            gdir = self.output_dir / gsub if gsub else self.output_dir
            gdir.mkdir(parents=True, exist_ok=True)
            gname = f"{gbase}_{sum(1 for p in gdir.glob(f'{gbase}_*.glb')) + 1:05d}_.glb"
            (gdir / gname).write_bytes(minimal_glb())
            outputs[save3d] = {"3d": [{"filename": gname, "subfolder": gsub, "type": "output"}]}
        self.histories[pid] = {"outputs": outputs, "status": {"completed": True, "status_str": "success"}}
        await self._send({"type": "executing", "data": {"prompt_id": pid, "node": None}})
        await self._send({"type": "execution_success", "data": {"prompt_id": pid}})

    # ---- routes -----------------------------------------------------------------------------------
    def _build(self) -> FastAPI:
        app = FastAPI()
        fake = self

        @app.get("/system_stats")
        async def system_stats():
            return {"system": {"comfyui_version": "fake-0.38.2", "python_version": "3.13"},
                    "devices": [{"name": "fake", "vram_total": 16 * 2**30, "vram_free": int(self.vram_free_gb * 2**30)}]}

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
            if name.lower().endswith((".mp4", ".webm", ".mov")):                # ST4: a guide video shows up in LoadVideo's enum
                vspec = fake.object_info.get("LoadVideo", {}).get("input", {}).get("required", {}).get("file")
                if isinstance(vspec, list) and vspec:
                    if isinstance(vspec[0], str) and len(vspec) > 1 and isinstance(vspec[1], dict):     # V3 dynamic combo: ["COMBO", {"options": [...]}]
                        opts = vspec[1].setdefault("options", [])
                        if name not in opts:
                            opts.append(name)
                    elif isinstance(vspec[0], list) and name not in vspec[0]:
                        vspec[0].append(name)
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


def main(argv: list[str] | None = None) -> int:
    """Standalone fake engine for the frontend end-to-end run (D68, P6): serves until killed. The orchestrator adopts it because it
    already listens on the configured engine port; `--output-dir` must be the orchestrator's `<state>/engine_out`."""
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="fake_comfy")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--mode", choices=("success", "silent", "error"), default="success")
    ap.add_argument("--object-info", default=str(Path(__file__).resolve().parent / "fixtures" / "object_info.json"))
    ap.add_argument("--output-dir", required=True, help="the orchestrator's <state>/engine_out")
    ap.add_argument("--models-root", default=None, help="LT1: list this tree's loras/ in LoraLoaderModelOnly's enum, as ComfyUI does (subfolders with the OS separator)")
    a = ap.parse_args(argv)
    data = json.loads(Path(a.object_info).read_text(encoding="utf-8"))
    fake = FakeComfy(data.get("object_info", data), Path(a.output_dir), behaviour=a.mode)
    if a.models_root:
        list_loras(fake.object_info, Path(a.models_root))
    sys.stdout.write(f"fake ComfyUI ({a.mode}) starting on 127.0.0.1:{a.port}, outputs in {a.output_dir}\n")   # callers poll /system_stats
    sys.stdout.flush()
    uvicorn.run(fake.app, host="127.0.0.1", port=a.port, log_level="warning", lifespan="off")
    return 0

def list_loras(object_info: dict, models_root: Path) -> list[str]:
    """LT1: ComfyUI's loras enum for a tree — every .safetensors under loras/, subfolders joined with the OS separator (E16: `e16\\x.safetensors`)."""
    import os
    folder = models_root / "loras"
    try:
        enum = object_info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0]
    except (KeyError, TypeError, IndexError):
        return []
    added = []
    if folder.is_dir():
        for p in sorted(folder.rglob("*.safetensors")):
            rel = os.sep.join(p.relative_to(folder).parts)
            if rel not in enum:
                enum.append(rel)
                added.append(rel)
    return added


def minimal_glb() -> bytes:
    """A valid glTF 2.0 binary with one triangle (positions only): what the fake engine 'generates' for a mesh job."""
    import struct
    positions = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    gltf = {"asset": {"version": "2.0", "generator": "loom2 fake engine"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 0.0]}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions)}], "buffers": [{"byteLength": len(positions)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    binc = positions + b"\x00" * ((4 - len(positions) % 4) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binc), 0x004E4942) + binc
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


if __name__ == "__main__":
    raise SystemExit(main())
