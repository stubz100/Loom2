"""Q15 (2026-10-05, 12 E0 / E7): the sampling speed that alternates under load — dev Turbo at ≈ 4.5 or ≈ 7.2 s/it after a while against
3.5 fresh, and (2026-10-28, Q18's rig) the first Wan job of a session sampling 15 % slower than the six after it. The cheap instrument
(no hot-spot or clock telemetry — amdsmi has no Windows build): the same job repeated through the queue on the real engine, the samplers'
seconds per step read from the job's node times, laid out by process and by order, with the idle seconds before each job — so a pattern
tied to the first job of a process (cold kernels, the weights' first pass), to sustained load (a drift or an alternation job after job) or
to rest (a gap making the next job fast again) shows as a table rather than a guess.

    orchestrator/.venv/Scripts/python.exe scripts/q15_speed_rig.py --kind t2i --processes 2 --jobs 6            # dev Turbo 960×544, 8 steps
    orchestrator/.venv/Scripts/python.exe scripts/q15_speed_rig.py --kind i2v --processes 1 --jobs 4            # Wan 2.2 Draft 832×480 × 81
    orchestrator/.venv/Scripts/python.exe scripts/q15_speed_rig.py --kind i2v --processes 3 --jobs 1            # three cold starts
    … [--idle SECONDS] (a rest before every job but the first)  [--seed N]  [--out NAME]

A process is one orchestrator with one engine; its jobs run back to back (seeds N, N+1, …). Results: engine/spikes/out/q15/<out>.json and a
table on stdout. One GPU job at a time (serial through the queue; nothing else on the card while this runs — it measures speed).
"""
from __future__ import annotations

import argparse
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

PORT = 8775
TOKEN = "q15token"
ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "q15"
BENCH = ROOT / "bench"


def api(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def engine_get(path: str):
    with urllib.request.urlopen(f"http://{ENGINE}{path}", timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def vram_free_gb() -> float | None:
    try:
        return round(float(engine_get("/system_stats")["devices"][0]["vram_free"]) / 2**30, 2)
    except Exception:  # noqa: BLE001
        return None


def wait_job(jid: str, timeout: float = 3600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == jid), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        if api("GET", "/queue").get("paused"):
            raise RuntimeError(f"the queue is paused while {jid} waits")
        time.sleep(1.0)
    raise TimeoutError(jid)


def launch(tmp: Path, log) -> subprocess.Popen:
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": 8188, "free_after_jobs_gb": 0}})
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            api("GET", "/health")
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    raise RuntimeError("the orchestrator did not come up")


def shutdown(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        api("POST", "/engine/stop")
        api("POST", "/shutdown")
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.wait(timeout=30)
    except Exception:  # noqa: BLE001
        proc.kill()
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            engine_get("/system_stats")
            time.sleep(1.0)
        except Exception:  # noqa: BLE001
            return


def recipe_for(kind: str, caps: dict, tmp: Path, seed: int) -> tuple[dict, int, str]:
    """The job, its sampling steps and the model — the bench's task 01 (t2i, dev Turbo as Q15 saw it) or task 02 (i2v, Wan Draft)."""
    if kind == "t2i":
        model = caps["defaults"]["t2i"]
        t = json.loads((BENCH / "t2i" / "01-alley-rain.json").read_text(encoding="utf-8"))
        subj = t["subjects"][0]
        text = f"{t['scene']}. {subj['description']}, {subj['action']}, {subj['pose']}. {t.get('style', '')}".strip()
        m = caps["models"][model]
        steps = int(m.get("turbo_steps") or 8) if m.get("turbo") else int(m.get("steps") or 20)
        return ({"kind": "t2i", "model_id": model, "prompt_mode": "text", "prompt_text": text, "width": 960, "height": 544, "seeds": [seed], "turbo": True, "tier": "draft"}, steps, model)
    model = caps["defaults"]["i2v"]
    spec = json.loads((BENCH / "i2v" / "tasks.json").read_text(encoding="utf-8"))
    task = next(x for x in spec["tasks"] if x["id"].startswith("02"))
    sid = api("POST", "/assets/import", {"paths": [str(BENCH / "i2v" / "frames" / Path(task["start"]).name)]})["items"][0]["id"]
    return ({"kind": "i2v", "model_id": model, "start_asset": sid, "prompt_text": task["prompt"], "frames": 81, "fps": 16, "width": 832, "height": 480, "preset": "draft", "seeds": [seed]}, 4, model)


def sampler_seconds(j: dict) -> tuple[float | None, dict[str, float]]:
    """The samplers' seconds in the job (its graph read back from the engine's history: every KSampler* node), and every node's by class."""
    nt = j.get("node_times") or {}
    by_class: dict[str, float] = {}
    try:
        graph = engine_get(f"/history/{j['prompt_id']}")[j["prompt_id"]]["prompt"][2]
    except Exception:  # noqa: BLE001
        return None, {}
    for nid, secs in nt.items():
        cls = graph.get(nid, {}).get("class_type", nid)
        by_class[cls] = round(by_class.get(cls, 0.0) + float(secs), 2)
    s = sum(float(v) for nid, v in nt.items() if graph.get(nid, {}).get("class_type", "").startswith("KSampler"))
    return (round(s, 2) if s else None), by_class


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="t2i", choices=["t2i", "i2v"])
    ap.add_argument("--processes", type=int, default=1, help="engine processes, one after the other")
    ap.add_argument("--jobs", type=int, default=4, help="jobs per process, back to back")
    ap.add_argument("--idle", type=float, default=0.0, help="seconds of rest before every job but a process's first")
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--out", default="", help="the results file's name (default: results_<kind>.json)")
    a = ap.parse_args()
    from m1_acceptance import port_busy
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / (a.out or f"results_{a.kind}.json")
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "kind": a.kind, "processes": a.processes, "jobs_per_process": a.jobs, "idle_s": a.idle, "seed": a.seed, "jobs": []}
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = None
    try:
        seed = a.seed
        for p in range(a.processes):
            tmp = Path(tempfile.mkdtemp(prefix="loom2-q15-"))
            proc = launch(tmp, log)
            api("POST", "/project", {"path": str(tmp / "proj"), "name": "Q15", "size_cap_gb": 40})
            caps = api("GET", "/capabilities")
            t_prev_end = None
            for k in range(a.jobs):
                recipe, steps, model = recipe_for(a.kind, caps, tmp, seed)
                results["model"], results["steps"] = model, steps
                if k and a.idle > 0:
                    time.sleep(a.idle)
                idle = round(time.time() - t_prev_end, 1) if t_prev_end else None
                t1 = time.time()
                job = api("POST", "/jobs", {"recipe": recipe, "origin": {"suite": "generate" if a.kind == "t2i" else "animate", "surface": "q15", "ref": "q15", "payload": {}}})["jobs"][0]
                j = wait_job(job["id"])
                t_prev_end = time.time()
                samp, by_class = sampler_seconds(j)
                row = {"process": p + 1, "job": k + 1, "seed": seed, "status": j["status"], "error": j.get("error"), "wall_s": j.get("wall_s"), "elapsed_s": round(t_prev_end - t1, 1),
                       "idle_before_s": idle, "sampler_s": samp, "s_per_it": round(samp / steps, 2) if samp else None, "by_class": by_class, "vram_free_after_gb": vram_free_gb(),
                       "clock": time.strftime("%H:%M:%S")}
                results["jobs"].append(row)
                out_json.write_text(json.dumps(results, indent=1), encoding="utf-8")
                print(f"process {p + 1} job {k + 1} ({row['clock']}): {j['status']} wall {j.get('wall_s')} s · samplers {samp} s = {row['s_per_it']} s/it over {steps} steps · "
                      f"idle before {idle} s · {row['vram_free_after_gb']} GB free · {j.get('error') or ''}", flush=True)
                seed += 1
            shutdown(proc)
            proc = None
        rows = results["jobs"]
        print("\ns/it by process and order:")
        for p in range(a.processes):
            print(f"  process {p + 1}: " + "  ".join(f"{r['s_per_it']}" for r in rows if r["process"] == p + 1), flush=True)
        return 0
    finally:
        shutdown(proc)
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
