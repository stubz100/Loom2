"""D45 rig check: Refine Edge on a real BiRefNet matte at 1080p.

Starts its own orchestrator on a temporary state (only the engine / model settings are copied from the real one, so no project of the
author's is touched), opens a temporary project, imports the bench source upscaled to 1920×1080, runs AI Select · Subject (BiRefNet)
plain and with `edge_refine`, times `POST /documents/{id}/selection/refine` on the plain matte, and writes before / after crops of the
selection edge to engine/spikes/out/pe2/.

    orchestrator/.venv/Scripts/python.exe scripts/refine_edge_rig.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "engine" / "spikes" / "out" / "pe2"
PORT, TOKEN = 8771, "rigtoken"
BASE = f"http://127.0.0.1:{PORT}"


def call(method: str, path: str, body=None, raw: bool = False):
    headers = {"X-Loom-Token": TOKEN}
    data = None
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body); headers["Content-Type"] = "application/octet-stream"
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, method=method, headers=headers), timeout=900) as r:
        payload = r.read()
        return (payload, dict(r.headers)) if raw else json.loads(payload or b"null")


def wait_job(jid: str, timeout: float = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = call("GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1)
    raise TimeoutError(jid)


def selection(did: str) -> np.ndarray:
    data, h = call("GET", f"/documents/{did}/selection", raw=True)
    return np.frombuffer(data, np.uint8).reshape(int(h["X-Loom-Height"] if "X-Loom-Height" in h else h["x-loom-height"]), -1)


def crop_sheet(img: np.ndarray, masks: list[np.ndarray], path: Path) -> None:
    """The most edge-heavy 320 px square of the plain matte, as image | plain | refined (mask over the image)."""
    m0 = masks[0].astype(np.int16)
    edge = (np.abs(np.diff(m0, axis=1, prepend=0)) > 0)
    best, by, bx = -1, 0, 0
    for y in range(0, img.shape[0] - 320, 80):
        for x in range(0, img.shape[1] - 320, 80):
            s = int(edge[y:y + 320, x:x + 320].sum())
            if s > best:
                best, by, bx = s, y, x
    tiles = [img[by:by + 320, bx:bx + 320, :3]]
    for m in masks:
        a = m[by:by + 320, bx:bx + 320, None].astype(np.float32) / 255
        tiles.append((img[by:by + 320, bx:bx + 320, :3] * a + np.array([255, 0, 255]) * (1 - a) * 0.5 + img[by:by + 320, bx:bx + 320, :3] * (1 - a) * 0.5).astype(np.uint8))
    Image.fromarray(np.concatenate(tiles, axis=1)).save(path)


def main() -> int:
    real = json.loads((REPO / ".loom2_state" / "app.json").read_text(encoding="utf-8"))["settings"]
    tmp = Path(tempfile.mkdtemp(prefix="loom2-pe2-"))
    state = tmp / "state"
    state.mkdir()
    (state / "app.json").write_text(json.dumps({"schema_version": 1, "settings": {k: real[k] for k in ("engine", "models_root", "mounted_model_trees", "variant") if k in real}}), encoding="utf-8")
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(state)], cwd=str(REPO / "orchestrator"), env=env,
                            stdout=open(tmp / "orchestrator.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(120):
            try:
                call("GET", "/health"); break
            except Exception:
                time.sleep(0.5)
        call("POST", "/project", {"path": str(tmp / "proj"), "name": "PE2 rig", "size_cap_gb": 10})
        src = Image.open(REPO / "bench" / "inpaint" / "source.png").convert("RGB").resize((1920, 1080), Image.LANCZOS)
        src_path = tmp / "source-1080p.png"
        src.save(src_path)
        asset = call("POST", "/assets/import", {"paths": [str(src_path)]})["items"][0]
        doc = call("POST", "/documents", {"from_asset": asset["id"], "name": "pe2-refine"})
        did = doc["id"]
        call("POST", "/queue/unpause")
        print(f"document {did} {doc['w']}×{doc['h']}", flush=True)

        def select(edge_refine: dict | None) -> tuple[dict, np.ndarray]:
            recipe = {"kind": "segment", "model_id": "birefnet", "mode": "subject", "seeds": [0], "edge_refine": edge_refine}
            job = call("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]
            j = wait_job(job["id"])
            if j["status"] != "done":
                raise RuntimeError(f"segment failed: {j.get('error')}")
            return j, selection(did)

        j1, plain = select(None)
        print(f"BiRefNet subject (plain): {j1['wall_s']} s, coverage {plain.mean() / 255:.3f}", flush=True)
        defaults = call("GET", "/capabilities")["refine_edge"]["defaults"]
        timings = []
        for _ in range(3):
            call("PUT", f"/documents/{did}/selection?w=1920&h=1080", plain.tobytes())
            r = call("POST", f"/documents/{did}/selection/refine", defaults)
            timings.append(r["ms"])
        refined = selection(did)
        print(f"refine route on the 1080p matte (defaults {defaults}): {timings} ms", flush=True)
        j2, chained = select(defaults)
        print(f"BiRefNet subject with edge_refine: {j2['wall_s']} s", flush=True)
        soft = lambda m: int(((m > 8) & (m < 247)).sum())  # noqa: E731
        print(f"soft edge pixels: plain {soft(plain)}, refined {soft(refined)}, in the job {soft(chained)}", flush=True)
        crop_sheet(np.asarray(src), [plain, refined], OUT / "refine-edge-1080p.png")
        print(f"crops: {OUT / 'refine-edge-1080p.png'}", flush=True)
        return 0
    finally:
        try:
            call("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=60)
        except Exception:
            orch.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
