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


def fake_person(ratios: dict[str, float] | None = None, h: float = 400.0, cx: float = 416.0, top: float = 40.0) -> dict:
    """CA1b: one SDPose person (OpenPose-18 body + 21-point hands) standing in the A-pose, drawn from proportions given as fractions of the
    nose → ankles height — what the fake engine's keypoints graph returns."""
    import math
    r = {"head_neck": 0.16, "torso": 0.33, "shoulders": 0.23, "hips": 0.14, "leg": 0.5, "arm": 0.34, "palm": 0.06} | (ratios or {})
    neck_y = top + r["head_neck"] * h
    hip_y = neck_y + r["torso"] * h
    ank_y = top + h
    sh, hp = r["shoulders"] * h / 2, r["hips"] * h / 2
    ax, ay = math.sin(math.radians(22)), math.cos(math.radians(22))
    arm = r["arm"] * h
    leg_drop = ank_y - hip_y
    leg_dx = math.sqrt(max(0.0, (r["leg"] * h) ** 2 - leg_drop ** 2))      # the legs apart, so each is as long as the ratio says
    pts = {0: (cx, top), 1: (cx, neck_y)}
    for s, (i_s, i_e, i_w, i_h, i_k, i_a) in ((-1, (2, 3, 4, 8, 9, 10)), (1, (5, 6, 7, 11, 12, 13))):
        pts[i_s] = (cx + s * sh, neck_y)
        pts[i_e] = (cx + s * (sh + ax * arm / 2), neck_y + ay * arm / 2)
        pts[i_w] = (cx + s * (sh + ax * arm), neck_y + ay * arm)
        pts[i_h] = (cx + s * hp, hip_y)
        pts[i_k] = (cx + s * (hp + leg_dx / 2), (hip_y + ank_y) / 2)
        pts[i_a] = (cx + s * (hp + leg_dx), ank_y)
    for i, (dx, dy) in {14: (-8, -6), 15: (8, -6), 16: (-16, 0), 17: (16, 0)}.items():
        pts[i] = (cx + dx, top + dy)
    body = [c for i in range(18) for c in (*pts[i], 0.9)]

    def hand(i_w: int, s: int) -> list[float]:
        wx, wy = pts[i_w]
        out = []
        for k in range(21):
            t = 0 if k == 0 else 4 if k == 9 else (k - 1) % 4 + 1        # 9: the middle finger's base, a palm's length from the wrist
            out += [wx + s * ax * r["palm"] * h * t / 4, wy + ay * r["palm"] * h * t / 4, 0.9]
        return out
    return {"pose_keypoints_2d": body, "hand_right_keypoints_2d": hand(4, -1), "hand_left_keypoints_2d": hand(7, 1), "foot_keypoints_2d": [], "face_keypoints_2d": []}


class FakeComfy:
    def __init__(self, object_info: dict, output_dir: Path, *, behaviour: str = "success", color=(255, 0, 255, 255),
                 object_info_delay: float = 0.0) -> None:
        self.object_info = json.loads(json.dumps(object_info))          # private copy: LoadImage's enum grows with uploads
        self.output_dir = Path(output_dir)
        self.behaviour = behaviour
        self.color = color
        self.object_info_delay = object_info_delay
        self.models_root: Path | None = None                              # LT2: the tree whose loras/ the enum follows (the standalone's --models-root)
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

    def _sam_video(self, graph: dict) -> tuple[int, int, int] | None:
        """D111 (PS5d): a SAM3_Detect graph reading a LoadVideo — the uploaded video's size and frame count, else None."""
        if not any(n.get("class_type") in ("SAM3_Detect", "RemoveBackground") for n in graph.values()):
            return None
        lv = next((n for n in graph.values() if n.get("class_type") == "LoadVideo"), None)
        data = self.uploaded(lv["inputs"].get("file", "")) if lv else []
        if not data:
            return None
        import io
        import av
        with av.open(io.BytesIO(data[-1])) as c:
            frames = [f for f in c.decode(video=0)]
        return (frames[0].width, frames[0].height, len(frames)) if frames else None

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
        vid = next((n for n in graph.values() if n.get("class_type") in ("WanImageToVideo", "WanFirstLastFrameToVideo", "LTXVImgToVideo", "WanAnimateToVideo", "WanSoundImageToVideo")), None)
        sam_video = self._sam_video(graph)
        if vid:                                                  # M6: a video graph decodes `length` frames; SaveImage writes one PNG each
            w, h, count = int(vid["inputs"].get("width", 64)), int(vid["inputs"].get("height", 64)), int(vid["inputs"].get("length", 1))
        elif sam_video:                                          # D111 (PS5d): SAM 3 over an uploaded video answers one mask per frame
            w, h, count = sam_video
        else:
            (w, h), count = self._output_size(), 1
        out_dir = self.output_dir / subfolder if subfolder else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        n0 = sum(1 for p in out_dir.glob(f"{base}_*"))
        images = []
        for i in range(count):
            fname = f"{base}_{n0 + i + 1:05d}_.png"
            if sam_video:                                        # a white figure in the middle on black: what a matte looks like
                im = Image.new("RGB", (w, h), (0, 0, 0))
                im.paste((255, 255, 255), (w * 2 // 5, h // 5, w * 3 // 5, h * 9 // 10))
                im.save(out_dir / fname)
            else:
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
        preview = next((k for k, n in graph.items() if n.get("class_type") == "PreviewAny"), None)
        if preview and any(n.get("class_type") == "SDPoseKeypointExtractor" for n in graph.values()):
            people = getattr(self, "people", None) or [fake_person()]                       # CA1b: the keypoints graph answers with text only
            outputs = {preview: {"text": [json.dumps([{"people": people, "canvas_width": 832, "canvas_height": 480}])]}}
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
            if fake.models_root is not None:                                 # LT2: ComfyUI rescans its folders on every /object_info — a LoRA cached since then appears
                list_loras(fake.object_info, fake.models_root)
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
            if name.lower().endswith((".wav", ".flac", ".mp3")):                # D88 XL: a line shows up in LoadAudio's enum, as ComfyUI lists the input folder
                aspec = fake.object_info.get("LoadAudio", {}).get("input", {}).get("required", {}).get("audio")
                if isinstance(aspec, list) and aspec:
                    if isinstance(aspec[0], str) and len(aspec) > 1 and isinstance(aspec[1], dict):
                        opts = aspec[1].setdefault("options", [])
                        if name not in opts:
                            opts.append(name)
                    elif isinstance(aspec[0], list) and name not in aspec[0]:
                        aspec[0].append(name)
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
        fake.models_root = Path(a.models_root)
        list_loras(fake.object_info, fake.models_root)
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
