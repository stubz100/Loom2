"""V13 (review 2026-10-27, journal 08:21): what dropping ComfyUI's cache after a document job costs, on the rig. On the pinned engine
`/free` with `free_memory` unloads every model (`main.py`: `flags.get("unload_models", free_memory)`), so the drop after every Edit job
made the next job load its model again. Six Klein fills on one document, the real engine, one at a time:

    A — `engine.free_after_jobs_gb = 99` (the behaviour before V13: dropped after every job): a1, a2, a3
    B — `engine.free_after_jobs_gb = 0`  (never dropped): b1 (cold after A's last drop), b2, b3 (warm)

Each job's wall time, its loader node times (the model load) and the engine's free VRAM after it. The numbers set the default of
`free_after_jobs_gb` (the pressure threshold) and go to the journal.

    orchestrator/.venv/Scripts/python.exe scripts/v13_free_cache_rig.py

Results: engine/spikes/out/v13/results.json (and the orchestrator's log beside it).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

PORT = 8771
TOKEN = "v13token"
OUT = ROOT / "engine" / "spikes" / "out" / "v13"


def api(method: str, path: str, body=None, raw: bytes | None = None, query: str = ""):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {"X-Loom-Token": TOKEN, "Content-Type": "application/octet-stream" if raw is not None else "application/json"}
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}{query}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        b = r.read()
        return json.loads(b.decode("utf-8") or "null")


def wait_job(jid: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == jid), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        if api("GET", "/queue").get("paused"):
            raise RuntimeError(f"the queue is paused while {jid} waits")
        time.sleep(1.5)
    raise TimeoutError(jid)


def vram_free_gb() -> float | None:
    try:
        e = api("GET", "/engine")
        for k in ("vram_free_gb", "free_gb"):
            if isinstance(e.get(k), (int, float)):
                return float(e[k])
        v = e.get("vram") or {}
        if isinstance(v, dict) and isinstance(v.get("free_gb"), (int, float)):
            return float(v["free_gb"])
    except Exception:  # noqa: BLE001
        pass
    return None


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.config import AppState
    from loom2.models import registry
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-v13-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [],
                                             "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"runs": [], "model": None}
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "V13", "size_cap_gb": 20})
        # one picture, one document, one selection in its middle
        w, h = 1024, 768
        y, x = np.mgrid[0:h, 0:w]
        img = np.stack([(x * 255 // w), (y * 255 // h), np.full((h, w), 90)], axis=-1).astype(np.uint8)
        img[200:560, 300:720] = (210, 200, 180)
        src = tmp / "table.png"
        Image.fromarray(img).save(src)
        asset = api("POST", "/assets/import", {"paths": [str(src)]})["items"][0]
        doc = api("POST", "/documents", {"from_asset": asset["id"]})
        sel = np.zeros((h, w), np.uint8)
        sel[260:500, 360:660] = 255
        api("PUT", f"/documents/{doc['id']}/selection", raw=sel.tobytes(), query=f"?w={w}&h={h}")
        mid = registry.default_model("inpaint", "full")
        results["model"] = mid
        recipe = {"kind": "inpaint", "mode": "fill", "model_id": mid, "document_id": doc["id"], "prompt_text": "a red apple on a wooden table", "seeds": [7],
                  "expand": 16, "feather": 8}

        def run(label: str) -> dict:
            t = time.time()
            jid = api("POST", f"/documents/{doc['id']}/ai", {"recipe": recipe})["jobs"][0]["id"]
            j = wait_job(jid)
            nodes = sorted(((float(v), k) for k, v in (j.get("node_times") or {}).items()), reverse=True)
            row = {"label": label, "status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t, 1), "top_nodes": [[k, round(v, 1)] for v, k in nodes[:4]],
                   "log_tail": (j.get("log_tail") or [])[-2:], "vram_free_after_gb": vram_free_gb(), "error": j.get("error")}
            print(f"{label}: {row['status']} wall {row['wall_s']} s · nodes {row['top_nodes']} · free {row['vram_free_after_gb']} GB · {row['log_tail'][-1:] }", flush=True)
            results["runs"].append(row)
            (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
            if j["status"] != "done":
                raise RuntimeError(f"{label}: {j['status']} {j.get('error')}")
            return row
        api("PUT", "/settings", {"engine": {"free_after_jobs_gb": 99.0}})         # A: dropped after every job (as before V13)
        for k in (1, 2, 3):
            run(f"a{k}")
        api("PUT", "/settings", {"engine": {"free_after_jobs_gb": 0.0}})          # B: never dropped
        for k in (1, 2, 3):
            run(f"b{k}")
        results["summary"] = {"a_wall_s": [r["wall_s"] for r in results["runs"][:3]], "b_wall_s": [r["wall_s"] for r in results["runs"][3:]],
                              "vram_free_after": [r["vram_free_after_gb"] for r in results["runs"]]}
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(json.dumps(results["summary"]), flush=True)
        return 0
    finally:
        try:
            api("POST", "/engine/stop")
            api("POST", "/shutdown")
            time.sleep(1.5)
        except Exception:  # noqa: BLE001
            pass
        if proc.poll() is None:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
