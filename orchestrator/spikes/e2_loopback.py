"""E2 loopback-throughput spike server (12 §1 E2; 05 §5 / 06 §2 transport rules).

Run:  orchestrator/.venv/Scripts/python.exe orchestrator/spikes/e2_loopback.py   (127.0.0.1:8765)

Serves big buffers the way the real orchestrator will: raw octet-stream files with Range support, never base64,
never built in Python memory per request. Also accepts streaming uploads (PUT /blobs/{sha256}) and records
browser-side spike results (POST /spike/result → orchestrator/spikes/out/<spike>.jsonl).

Endpoints
  GET  /latent                200 MB float16 "latent" (random, generated once to a temp file)
  GET  /image8k.png           8192×8192 RGBA PNG (an E0 render upscaled, generated once; ~100+ MB)
  GET  /image8k.raw           the same image as raw RGBA8 bytes (256 MB) — the zero-decode path to a GPU texture
  PUT  /blobs/{sha256}        streaming upload; verifies the hash; returns MB/s
  POST /spike/result          {"spike": "e1", ...} appended as one JSONL row
  GET  /health
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "orchestrator" / "spikes" / "out"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "cache"
CACHE.mkdir(exist_ok=True)
SOURCE_PNG = REPO / "engine" / "spikes" / "out" / "e0_fp8-20st-960x544_s20261004.png"

app = FastAPI(title="loom2 E2 loopback spike")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "http://tauri.localhost", "https://tauri.localhost"],
    allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Length", "X-Gen-Seconds"],
)


def latent_file() -> Path:
    p = CACHE / "latent_200mb.f16"
    if not p.exists():
        t0 = time.perf_counter()
        arr = np.random.default_rng(0).standard_normal(200 * 1024 * 1024 // 2, dtype=np.float32).astype(np.float16)
        p.write_bytes(arr.tobytes())
        print(f"[e2] latent generated in {time.perf_counter()-t0:.1f}s: {p.stat().st_size/2**20:.0f} MiB")
    return p


def image8k_files() -> tuple[Path, Path]:
    png, raw = CACHE / "image8k.png", CACHE / "image8k.raw"
    if not png.exists() or not raw.exists():
        t0 = time.perf_counter()
        src = Image.open(SOURCE_PNG).convert("RGBA") if SOURCE_PNG.exists() else Image.radial_gradient("L").convert("RGBA")
        big = src.resize((8192, 8192), Image.LANCZOS)
        raw.write_bytes(big.tobytes())
        big.save(png, compress_level=1)
        print(f"[e2] 8k image generated in {time.perf_counter()-t0:.1f}s: png {png.stat().st_size/2**20:.0f} MiB, raw {raw.stat().st_size/2**20:.0f} MiB")
    return png, raw


@app.get("/health")
def health():
    return {"ok": True, "pid": os.getpid()}


CHUNK = int(os.environ.get("E2_CHUNK_MIB", "4")) * 2**20  # Starlette's default is 64 KiB; 2026-10-05: testing 4 MiB
FileResponse.chunk_size = CHUNK  # class attribute in this Starlette version (not a constructor argument)


@app.get("/latent")
def get_latent():
    return FileResponse(latent_file(), media_type="application/octet-stream", headers={"Cache-Control": "no-store"})


@app.get("/image8k.png")
def get_image8k_png():
    png, _ = image8k_files()
    return FileResponse(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/image8k.raw")
def get_image8k_raw():
    _, raw = image8k_files()
    return FileResponse(raw, media_type="application/octet-stream",
                        headers={"Cache-Control": "no-store", "X-Width": "8192", "X-Height": "8192"})


@app.put("/blobs/{sha256}")
async def put_blob(sha256: str, request: Request):
    h = hashlib.sha256()
    n = 0
    t0 = time.perf_counter()
    async for chunk in request.stream():
        h.update(chunk)
        n += len(chunk)
    dt = time.perf_counter() - t0
    ok = h.hexdigest() == sha256.lower()
    return JSONResponse({"ok": ok, "bytes": n, "seconds": round(dt, 3), "mb_per_s": round(n / 2**20 / dt, 1) if dt else None,
                         "sha256": h.hexdigest()}, status_code=200 if ok else 422)


@app.post("/spike/result")
async def spike_result(request: Request):
    row = await request.json()
    row["server_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    spike = str(row.get("spike", "unknown")).replace("/", "_")
    with (OUT / f"{spike}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[spike:{spike}] {json.dumps(row, ensure_ascii=False)[:300]}")
    return {"ok": True}


if __name__ == "__main__":
    latent_file()
    image8k_files()
    uvicorn.run(app, host="127.0.0.1", port=8765, http="httptools", log_level="warning")
