"""M7 durability, rig half (12 §8, 03 §6): real processes on the real engine.

  power-loss   start an orchestrator (own state dir cloned from .loom2_state so the rig's models and engine settings apply),
               open the project, submit a Wan Draft clip, wait until the engine is sampling, then kill the orchestrator with
               `taskkill /F` (no clean shutdown). Expect: the engine process dies with it (Job Object) within 10 s; a relaunch
               reports the queue *paused* with the job *re-queued* (`resumed_unclean`); unpausing finishes the clip.
  engine-crash submit another clip, kill the ComfyUI process mid-sampling. Expect: the job fails with an "engine" error
               within a minute, the orchestrator is still answering, the next submission starts the engine again (then the
               probe job is cancelled to save GPU time).

    LOOM2_TOKEN=devtoken python scripts/m7_durability.py --project F:/loom2-projects/m6-acceptance [--cases power-loss,engine-crash]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "bench" / "i2v"
OUT = REPO / "engine" / "spikes" / "out" / "m7"
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")
PY = REPO / "orchestrator" / ".venv" / "Scripts" / "python.exe"


def call(base: str, method: str, path: str, body=None, timeout: float = 60):
    data = None
    headers = {"X-Loom-Token": TOKEN}
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = r.read()
        return json.loads(payload) if payload else None


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return f'"{pid}"' in out


def kill(pid: int) -> None:
    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


class Orch:
    def __init__(self, state: Path, port: int, project: str) -> None:
        self.state, self.port, self.project = state, port, project
        self.base = f"http://127.0.0.1:{port}"
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
        self.proc = subprocess.Popen([str(PY), "-m", "loom2.main", "--port", str(self.port), "--state", str(self.state), "--project", self.project],
                                     cwd=str(REPO / "orchestrator"), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                if call(self.base, "GET", "/health")["ok"]:
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("orchestrator did not come up")

    def shutdown(self) -> None:
        try:
            call(self.base, "POST", "/shutdown")
        except Exception:
            pass
        if self.proc:
            try:
                self.proc.wait(timeout=30)
            except Exception:
                self.proc.kill()


def wait_sampling(base: str, jid: str, timeout: float = 600) -> dict:
    """Until the job reports sampler progress (the engine is really on the GPU), or a terminal state."""
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        j = call(base, "GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        msg = f"{j['progress_text']} {round((j['progress'] or 0) * 100)}%"
        if msg != last:
            print(f"      … {msg} ({round(time.time() - t0)} s)", flush=True); last = msg
        if j["status"] == "running" and ("step" in (j["progress_text"] or "") or (j["progress"] or 0) > 0.05):
            return j
        time.sleep(2)
    raise TimeoutError("job never started sampling")


def wait_terminal(base: str, jid: str, timeout: float) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = call(base, "GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(3)
    raise TimeoutError("job did not finish")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="F:/loom2-projects/m6-acceptance")
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--cases", default="power-loss,engine-crash")
    ap.add_argument("--state-src", default=str(REPO / ".loom2_state"))
    a = ap.parse_args()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, info: str = "") -> None:
        results.append((name, bool(ok), info))
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{(' — ' + info) if info else ''}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix="loom2-m7-state-"))
    shutil.copy(Path(a.state_src) / "app.json", state / "app.json")        # the rig's models root and engine settings, a fresh token
    orch = Orch(state, a.port, a.project)
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    t01 = next(t for t in spec["tasks"] if t["id"].startswith("01"))
    log_rows = []
    try:
        orch.start()
        proj = call(orch.base, "GET", "/project")
        check("orchestrator up with the project", proj.get("open") is True, proj.get("name", ""))
        start = call(orch.base, "POST", "/assets/import", {"paths": [str(BENCH / t01["start"])]})["items"][0]
        recipe = {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "start_asset": start["id"], "prompt_text": t01["prompt"], "frames": 81, "fps": 16, "width": 832, "height": 480, "preset": "draft", "seeds": [7]}
        call(orch.base, "POST", "/queue/unpause")
        cases = a.cases.split(",")

        if "power-loss" in cases:
            print("\n== power loss mid-job", flush=True)
            jid = call(orch.base, "POST", "/jobs", {"recipe": recipe})["jobs"][0]["id"]
            j = wait_sampling(orch.base, jid)
            eng = call(orch.base, "GET", "/engine")
            epid = eng.get("pid")
            check("engine sampling under the orchestrator", j["status"] == "running" and bool(epid), f"job {jid} · engine pid {epid} · {j['progress_text']}")
            t0 = time.time()
            kill(orch.proc.pid)                                            # the power goes
            orch.proc.wait(timeout=10)
            gone = False
            while time.time() - t0 < 15:
                if not alive(epid):
                    gone = True; break
                time.sleep(0.5)
            check("engine process died with the orchestrator (Job Object)", gone, f"{round(time.time() - t0, 1)} s")
            orch.start()
            q = call(orch.base, "GET", "/queue")
            j = call(orch.base, "GET", f"/jobs/{jid}")
            check("relaunch: queue paused, interrupted job re-queued", q["paused"] is True and q.get("resumed_unclean") is True and j["status"] == "queued" and j["retry_count"] >= 1,
                  f"paused {q['paused']} · resumed_unclean {q.get('resumed_unclean')} · job {j['status']} retry {j['retry_count']}")
            check("no recovery notes (records intact)", not q.get("recovery"), str(q.get("recovery")))
            call(orch.base, "POST", "/queue/unpause")
            j = wait_terminal(orch.base, jid, 900)
            check("re-queued job finishes after the relaunch", j["status"] == "done", f"{j['status']} · {j.get('wall_s')} s · {j.get('error') or ''}")
            if j["status"] == "done":
                clip = call(orch.base, "GET", f"/clips/{j['result']['clip_id']}")
                check("its clip is complete", clip["frames"] == 81 and bool(clip["proxy_path"]), f"{clip['frames']} f · proxy {clip['proxy_bytes'] / 2**20:.1f} MiB")
            log_rows.append({"case": "power-loss", "job": j})

        if "engine-crash" in cases:
            print("\n== engine crash mid-job", flush=True)
            jid = call(orch.base, "POST", "/jobs", {"recipe": {**recipe, "seeds": [8]}})["jobs"][0]["id"]
            j = wait_sampling(orch.base, jid)
            epid = call(orch.base, "GET", "/engine").get("pid")
            check("engine sampling", j["status"] == "running" and bool(epid), f"engine pid {epid}")
            t0 = time.time()
            kill(epid)
            j = wait_terminal(orch.base, jid, 120)
            check("job fails with an engine error, promptly", j["status"] == "failed" and "engine" in (j.get("error") or "").lower(), f"{j['status']} after {round(time.time() - t0)} s · {j.get('error')}")
            health = call(orch.base, "GET", "/health")
            check("orchestrator still answering", health.get("ok") is True)
            q = call(orch.base, "GET", "/queue")
            print(f"      queue after the crash: paused {q['paused']} · counts {q['counts']}")
            if q["paused"]:
                call(orch.base, "POST", "/queue/unpause")
            jid2 = call(orch.base, "POST", "/jobs", {"recipe": {**recipe, "seeds": [9]}})["jobs"][0]["id"]
            t0 = time.time()
            restarted = False
            while time.time() - t0 < 180:
                e = call(orch.base, "GET", "/engine")
                jj = call(orch.base, "GET", f"/jobs/{jid2}")
                if e.get("running") and e.get("pid") and e["pid"] != epid and jj["status"] == "running":
                    restarted = True; break
                if jj["status"] in ("failed", "cancelled"):
                    break
                time.sleep(2)
            check("the next job starts a fresh engine", restarted, f"{round(time.time() - t0)} s · engine pid {call(orch.base, 'GET', '/engine').get('pid')} (was {epid})")
            call(orch.base, "POST", f"/jobs/{jid2}/cancel")
            log_rows.append({"case": "engine-crash", "job": j})
    finally:
        orch.shutdown()
        (OUT / "m7_durability.json").write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": results, "rows": log_rows}, indent=1, default=str), encoding="utf-8")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nM7 durability (rig): {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
