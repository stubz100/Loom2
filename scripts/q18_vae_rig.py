"""Q18 (2026-10-05, 04 §5): the Wan VAE's share of a clip, measured on the rig as the app runs it today, and the two things the question
proposed — MIOpen on for the 3D convolutions, and `VAEDecodeTiled` with temporal tiling.

Phase **a** (the launch as it is — MIOpen off, D13): the bench task 02 (walk toward camera) as one Wan 2.2 Draft i2v job through the
queue (832×480 × 81 frames, the real engine): the job's node times (the start image's encode inside WanImageToVideo, the two samplers,
the decode, the PNGs). Then, the engine's node cache holding everything but the decode (the rig's state sets `free_after_jobs_gb` 0, so
the cache stays), the job's own graph is submitted straight to the engine with the decode node swapped for `VAEDecodeTiled` — one tile
and one chunk (the warm plain decode, the control), spatial tiles only, temporal chunks only, both. Each run's execution seconds are the
decode plus the PNGs (the engine lists the cached nodes; a run that re-sampled is marked), the peak VRAM sampled meanwhile.
Phase **b**: the orchestrator relaunched with `COMFYUI_ENABLE_MIOPEN=1` in the engine's environment; the same job twice (the first
decode tunes MIOpen's kernels on the shape, the second is warm), then the control and the fastest tiled variant of phase a.

    orchestrator/.venv/Scripts/python.exe scripts/q18_vae_rig.py [--phases a,b] [--seed 20261005] [--jobs N] [--no-variants] [--out results.json]

An A/B of the launches alone (the samplers' time under MIOpen, Q15's variance in mind): `--phases a,b,a,b --jobs 1 --no-variants --out results_ab.json`.
Measured 2026-10-28 (journal, D147): the decode 11–14 s of a 119–131 s clip; tiling buys memory, not time; MIOpen on moves 5–7 s from the decode to the
encode and holds 4.5 GB after the job. The variants resubmit the last job's graph — the engine's cache holds that job's seed (the first run's phase b
re-sampled for resubmitting the first job's).

Results: engine/spikes/out/q18/results.json; the baseline clip's sheet beside it. One GPU job at a time (serial through the queue and the
engine; nothing else on the card).
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
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

PORT = 8774
TOKEN = "q18token"
ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "q18"
BENCH = ROOT / "bench" / "i2v"
VARIANTS = {                                                           # name: (tile_size, overlap, temporal_size, temporal_overlap)
    "control-one-tile-one-chunk": (4096, 0, 4096, 8),                  # the warm plain decode through the tiled node's path
    "spatial-512": (512, 64, 4096, 8),
    "temporal-32": (4096, 0, 32, 8),
    "temporal-16": (4096, 0, 16, 8),
    "spatial-512-temporal-32": (512, 64, 32, 8),
}


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
        time.sleep(2.0)
    raise TimeoutError(jid)


def launch(tmp: Path, env_extra: dict[str, str], log) -> subprocess.Popen:
    """A temporary orchestrator on PORT with its own state (the cache kept after jobs); the engine inherits env_extra."""
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": 8188, "free_after_jobs_gb": 0}})
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, **env_extra, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
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
    while time.time() - t0 < 60:                                       # the engine's port free before the next launch
        try:
            engine_get("/system_stats")
            time.sleep(1.0)
        except Exception:  # noqa: BLE001
            return


def job_row(j: dict, label: str) -> dict:
    nt = j.get("node_times") or {}
    return {"label": label, "status": j["status"], "wall_s": j.get("wall_s"), "error": j.get("error"), "node_times": nt,
            "encode_s": nt.get("7"), "sampler_high_s": nt.get("9"), "sampler_low_s": nt.get("10"), "decode_s": nt.get("11"), "png_s": nt.get("12"),
            "decode_share": round(float(nt["11"]) / float(j["wall_s"]), 3) if nt.get("11") and j.get("wall_s") else None,
            "log_tail": (j.get("log_tail") or [])[-3:], "prompt_id": j.get("prompt_id")}


def save(results: dict) -> None:
    Path(results["_out"]).write_text(json.dumps({k: v for k, v in results.items() if k != "_out"}, indent=1), encoding="utf-8")


def run_baseline(recipe: dict, label: str, results: dict, sheet_to: Path | None, tmp: Path) -> dict:
    t1 = time.time()
    job = api("POST", "/jobs", {"recipe": recipe, "origin": {"suite": "animate", "surface": "clip", "ref": "q18", "payload": {}}})["jobs"][0]
    j = wait_job(job["id"])
    row = job_row(j, label)
    row["elapsed_s"] = round(time.time() - t1, 1)
    row["vram_free_after_gb"] = vram_free_gb()
    results["jobs"].append(row)
    print(f"{label}: {j['status']} wall {j.get('wall_s')} s · encode {row['encode_s']} · samplers {row['sampler_high_s']} + {row['sampler_low_s']} · "
          f"decode {row['decode_s']} ({row['decode_share']}) · png {row['png_s']}", flush=True)
    save(results)
    if j["status"] != "done":
        raise RuntimeError(f"{label} failed: {j.get('error')}")
    if sheet_to is not None:
        frames = sorted((tmp / "proj" / "clips" / j["result"]["clip_id"] / "master").glob("*.png"))
        picks = [frames[0], frames[len(frames) // 2], frames[-1]]
        ims = [Image.open(p).convert("RGB") for p in picks]
        canvas = Image.new("RGB", (sum(i.width for i in ims) + 20, max(i.height for i in ims)), (24, 24, 24))
        x = 0
        for im in ims:
            canvas.paste(im, (x, 0))
            x += im.width + 10
        canvas.save(sheet_to, quality=88)
        row["clip"] = {"id": j["result"]["clip_id"], "frames": len(frames), "size": list(ims[0].size)}
    return row


def run_variants(prompt_id: str, names: list[str], phase: str, results: dict) -> list[dict]:
    """The job's own graph straight to the engine, the decode node swapped; the engine's node cache serves the rest."""
    import cr_acceptance as cr
    from e12_angles import Engine
    graph = engine_get(f"/history/{prompt_id}")[prompt_id]["prompt"][2]
    decode = [k for k, v in graph.items() if v["class_type"] == "VAEDecode"]
    save = [k for k, v in graph.items() if v["class_type"] == "SaveImage"]
    assert len(decode) == 1 and len(save) == 1, (decode, save)
    dec, sav = decode[0], save[0]
    samplers = [k for k, v in graph.items() if v["class_type"].startswith("KSampler")]
    eng = Engine(ENGINE)
    vram = cr.VramSampler()
    rows = []
    try:
        for name in names:
            tile, overlap, temporal, toverlap = VARIANTS[name]
            g = json.loads(json.dumps(graph))
            g[dec] = {"class_type": "VAEDecodeTiled", "inputs": {"samples": graph[dec]["inputs"]["samples"], "vae": graph[dec]["inputs"]["vae"],
                                                                  "tile_size": tile, "overlap": overlap, "temporal_size": temporal, "temporal_overlap": toverlap}}
            g[sav]["inputs"]["filename_prefix"] = f"q18/{phase}-{name}"
            free0 = vram_free_gb()
            vram.mark()
            h, wall, exec_s = eng.run(g)
            peak = vram.window()
            msgs = {m[0]: m[1] for m in h["status"].get("messages", [])}
            cached = set((msgs.get("execution_cached") or {}).get("nodes") or [])
            images = h["outputs"].get(sav, {}).get("images", [])
            im = np.asarray(eng.image(h, sav)) if images else None
            row = {"phase": phase, "variant": name, "tile_size": tile, "overlap": overlap, "temporal_size": temporal, "temporal_overlap": toverlap,
                   "exec_s": round(exec_s, 1), "wall_s": round(wall, 1), "frames": len(images), "first_frame_std": round(float(im.std()), 1) if im is not None else None,
                   "samplers_cached": all(s in cached for s in samplers), "cached_nodes": len(cached), "peak_vram_gb": peak, "vram_free_before_gb": free0, "vram_free_after_gb": vram_free_gb(),
                   "error": (msgs.get("execution_error") or {}).get("exception_message")}
            rows.append(row)
            results["variants"].append(row)
            print(f"{phase} {name}: exec {row['exec_s']} s (decode + png; samplers cached: {row['samplers_cached']}) · {row['frames']} frames · peak {peak} GB · "
                  f"{row['error'] or ''}", flush=True)
            save(results)
    finally:
        vram.stop = True
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="a,b", help="a: as launched (MIOpen off) · b: COMFYUI_ENABLE_MIOPEN=1")
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--jobs", type=int, default=0, help="jobs per phase (0: one for a, two for b — the second with MIOpen tuned)")
    ap.add_argument("--no-variants", action="store_true", help="the jobs alone, no tiled decodes")
    ap.add_argument("--out", default="results.json", help="the results file under engine/spikes/out/q18/")
    a = ap.parse_args()
    phases = [p.strip() for p in a.phases.split(",") if p.strip()]
    from m1_acceptance import port_busy
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    task = next(t for t in spec["tasks"] if t["id"].startswith("02"))
    start = BENCH / "frames" / Path(task["start"]).name
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "task": task["id"], "seed": a.seed, "jobs": [], "variants": []}
    results["_out"] = str(OUT / a.out)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = None
    fastest: str | None = None
    try:
        for phase in phases:
            env = {"COMFYUI_ENABLE_MIOPEN": "1"} if phase == "b" else {}
            tmp = Path(tempfile.mkdtemp(prefix=f"loom2-q18{phase}-"))
            proc = launch(tmp, env, log)
            api("POST", "/project", {"path": str(tmp / "proj"), "name": "Q18", "size_cap_gb": 40})
            caps = api("GET", "/capabilities")
            model = caps["defaults"]["i2v"]
            health = caps["i2v"]["models"][model]["health"]
            if health == "missing":
                raise SystemExit(f"{model}: weights missing")
            results["model"] = model
            sid = api("POST", "/assets/import", {"paths": [str(start)]})["items"][0]["id"]
            recipe = {"kind": "i2v", "model_id": model, "start_asset": sid, "prompt_text": task["prompt"], "frames": 81, "fps": 16, "width": 832, "height": 480,
                      "preset": "draft", "seeds": [a.seed]}
            results[f"env_{phase}"] = env
            print(f"== phase {phase} ({'MIOpen on' if env else 'as launched, MIOpen off'}) · {model} · Draft 832×480 × 81", flush=True)
            n_jobs = a.jobs or (2 if phase == "b" else 1)
            last = run_baseline(recipe, f"{phase}: the job as the app runs it", results, OUT / f"sheet_{phase}.jpg", tmp)
            for k in range(1, n_jobs):                                 # phase b's second job: the decode on the same shapes, MIOpen's kernels tuned
                last = run_baseline({**recipe, "seeds": [a.seed + k]}, f"{phase}: the job again ({"MIOpen tuned" if phase == "b" else k + 1})", results, None, tmp)
            if phase == "b":
                names = ["control-one-tile-one-chunk"] + ([fastest] if fastest and fastest != "control-one-tile-one-chunk" else [])
            else:
                names = list(VARIANTS)
            rows = run_variants(last["prompt_id"], names, phase, results) if not a.no_variants else []   # the last job's graph: its seed is what the cache holds
            if phase == "a" and rows:
                ok = [r for r in rows if r["samplers_cached"] and not r["error"] and r["frames"] == 81]
                fastest = min(ok, key=lambda r: r["exec_s"])["variant"] if ok else None
                results["fastest_a"] = fastest
            shutdown(proc)
            proc = None
        save(results)
        print("decode by job:", [(r["label"], r["decode_s"], r["decode_share"]) for r in results["jobs"]], flush=True)
        print("variants:", [(r["phase"], r["variant"], r["exec_s"], r["samplers_cached"], r["peak_vram_gb"]) for r in results["variants"]], flush=True)
        return 0
    finally:
        shutdown(proc)
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
