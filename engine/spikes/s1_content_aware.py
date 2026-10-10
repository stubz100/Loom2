"""S1 spike (PE3): PhotoCraft's content-aware fill through the PyO3 wheel built from engine/spikes/pcalgo — CPU cost, and whether it makes
a better AI Remove than today's mid-grey hole.

    uvx maturin build --release -m engine/spikes/pcalgo/Cargo.toml
    orchestrator/.venv/Scripts/python.exe engine/spikes/s1_content_aware.py

The wheel is not installed: its .pyd is extracted to a temporary folder and imported from there, so the orchestrator venv stays as locked.
Comparison on bench task 01 (remove the crates), Klein 9B, seed 7, on a temporary state and project:
  A  content-aware fill alone (no GPU)
  B  Remove as today (ICM, the hole neutralised to mid grey in the reference)
  C  Fill-Match on the content-aware-filled image (ICM with the pre-fill as the reference) — what a pre-fill would give Remove
A sheet lands in engine/spikes/out/s1/ for scoring by eye.
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
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "bench" / "inpaint"
OUT = REPO / "engine" / "spikes" / "out" / "s1"
PORT, TOKEN = 8773, "rigtoken"
BASE = f"http://127.0.0.1:{PORT}"


def load_wheel(tmp: Path):
    wheel = next((REPO / "engine" / "spikes" / "pcalgo" / "target" / "wheels").glob("loom2_pcalgo-*.whl"))
    with zipfile.ZipFile(wheel) as z:
        z.extractall(tmp / "wheel")
    sys.path.insert(0, str(tmp / "wheel"))
    import loom2_pcalgo  # noqa: E402
    return loom2_pcalgo, wheel


def call(method: str, path: str, body=None, raw: bool = False):
    headers = {"X-Loom-Token": TOKEN}
    data = None
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body); headers["Content-Type"] = "application/octet-stream"
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, method=method, headers=headers), timeout=1800) as r:
        payload = r.read()
        return (payload, {k.lower(): v for k, v in r.headers.items()}) if raw else json.loads(payload or b"null")


def wait_job(jid: str) -> dict:
    while True:
        j = call("GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="loom2-s1-"))
    OUT.mkdir(parents=True, exist_ok=True)
    pc, wheel = load_wheel(tmp)
    print(f"wheel {wheel.name}: {wheel.stat().st_size / 1e6:.2f} MB", flush=True)
    sys.path.insert(0, str(REPO / "orchestrator"))
    from loom2 import maskops  # noqa: E402

    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    task = next(t for t in spec["tasks"] if t["id"].startswith("01"))
    original = np.asarray(Image.open(BENCH / spec["source"]).convert("RGB"))
    H, W = original.shape[:2]
    mask = np.asarray(Image.open(BENCH / "masks" / f"{task['id']}.png").convert("L").resize((W, H)))
    hole = maskops.expand(mask, 6) >= 128                                # cover the feathered edge too

    def timed(fn, *a, **k):
        t0 = time.perf_counter(); r = fn(*a, **k); return r, time.perf_counter() - t0

    img = original.astype(np.float32) / 255
    filled, t_fill = timed(pc.content_aware_fill, img, hole, seed=7)
    _, t_complete = timed(pc.complete_hole, img, hole, seed=7)
    big = np.asarray(Image.fromarray(original).resize((1920, 1080), Image.LANCZOS)).astype(np.float32) / 255
    big_hole = np.asarray(Image.fromarray((hole * 255).astype(np.uint8)).resize((1920, 1080))) >= 128
    _, t_big = timed(pc.content_aware_fill, big, big_hole, seed=7)
    print(f"content-aware fill {W}×{H}, hole {int(hole.sum())} px: {t_fill:.2f} s · PatchMatch completion {t_complete:.2f} s · 1920×1080 ({int(big_hole.sum())} px): {t_big:.2f} s", flush=True)
    prefill = np.clip(np.rint(filled * 255), 0, 255).astype(np.uint8)
    Image.fromarray(prefill).save(tmp / "prefill.png")

    real = json.loads((REPO / ".loom2_state" / "app.json").read_text(encoding="utf-8"))["settings"]
    state = tmp / "state"
    state.mkdir()
    (state / "app.json").write_text(json.dumps({"schema_version": 1, "settings": {k: real[k] for k in ("engine", "models_root", "mounted_model_trees", "variant") if k in real}}), encoding="utf-8")
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(state)], cwd=str(REPO / "orchestrator"), env=env,
                            stdout=open(tmp / "orchestrator.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                call("GET", "/health"); break
            except Exception:
                time.sleep(0.5)
        call("POST", "/project", {"path": str(tmp / "proj"), "name": "S1 spike", "size_cap_gb": 10})
        call("POST", "/queue/unpause")
        results = {}
        for name, path, mode in (("B remove (grey hole)", BENCH / spec["source"], "remove"), ("C fill-match on the pre-fill", tmp / "prefill.png", "fill_match")):
            asset = call("POST", "/assets/import", {"paths": [str(path)]})["items"][0]
            did = call("POST", "/documents", {"from_asset": asset["id"], "name": name})["id"]
            call("PUT", f"/documents/{did}/selection?w={W}&h={H}", mask.tobytes())
            recipe = {"kind": "inpaint", "mode": mode, "model_id": "klein-9b", "prompt_text": task["prompt"], "seeds": [7], "feather": 8}
            j = wait_job(call("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]["id"])
            if j["status"] != "done":
                print(f"{name}: FAILED {j.get('error')}", flush=True); return 1
            png, _ = call("POST", f"/documents/{did}/export", {"format": "png"}, raw=True)
            import io
            results[name] = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
            print(f"{name}: {j['wall_s']} s", flush=True)
        ys, xs = np.nonzero(hole)
        y0, y1, x0, x1 = max(0, ys.min() - 40), min(H, ys.max() + 40), max(0, xs.min() - 40), min(W, xs.max() + 40)
        tiles = [original, prefill, results["B remove (grey hole)"], results["C fill-match on the pre-fill"]]
        Image.fromarray(np.concatenate([t[y0:y1, x0:x1] for t in tiles], axis=1)).save(OUT / "s1-task01.png")
        print(f"sheet: {OUT / 's1-task01.png'} (original · A content-aware fill · B Remove today · C Fill-Match on the pre-fill)", flush=True)
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
