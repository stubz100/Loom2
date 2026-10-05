"""M1 rig acceptance (12 §2): new project → generate one image through the supervised engine → asset, manifest,
lineage and thumbnail exist → hard-kill the orchestrator mid-job (the engine must die with it) → relaunch
resumes paused with the job queued → unpause, cancel a running job → graceful stop. Also checks the live
`/object_info` against the committed fixture classes.

  orchestrator/.venv/Scripts/python.exe scripts/m1_acceptance.py [--projects F:/loom2-projects] [--port 8765]
Appends a JSON line to engine/spikes/out/m1_acceptance.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
ORCH_PY = REPO / "orchestrator" / ".venv" / "Scripts" / "python.exe"
RESULTS = REPO / "engine" / "spikes" / "out" / "m1_acceptance.jsonl"
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def port_busy(port: int) -> bool:
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port)); return True
    except OSError:
        return False
    finally:
        s.close()


class Orch:
    def __init__(self, state: Path, port: int, project: Path | None = None) -> None:
        self.state, self.port, self.project = state, port, project
        self.proc: subprocess.Popen | None = None
        self.token = ""
        self.http: httpx.Client | None = None

    def start(self, timeout: float = 60) -> "Orch":
        args = [str(ORCH_PY), "-m", "loom2.main", "--state", str(self.state), "--port", str(self.port)]
        if self.project:
            args += ["--project", str(self.project)]
        self.proc = subprocess.Popen(args, cwd=str(REPO / "orchestrator"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self.proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                if self.proc.poll() is not None:
                    raise RuntimeError("orchestrator exited early")
                continue
            if line.startswith("LOOM2_READY "):
                self.token = json.loads(line[len("LOOM2_READY "):])["token"]
                break
        else:
            raise RuntimeError("no READY line")
        self.http = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", headers={"X-Loom-Token": self.token}, timeout=60)
        # drain stdout in the background so the pipe never fills
        import threading
        threading.Thread(target=lambda: [None for _ in iter(self.proc.stdout.readline, "")], daemon=True).start()  # type: ignore[union-attr]
        return self

    def kill_hard(self) -> None:
        subprocess.run(["taskkill", "/F", "/PID", str(self.proc.pid)], capture_output=True)  # type: ignore[union-attr]
        self.proc.wait(timeout=10)  # type: ignore[union-attr]

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.http.post("/shutdown", timeout=5)  # type: ignore[union-attr]
                self.proc.wait(timeout=30)
                return
            except Exception:
                pass
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def wait_job(self, job_id: str, states: set[str], timeout: float, min_progress: float = 0.0) -> dict:
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = self.http.get(f"/jobs/{job_id}").json()  # type: ignore[union-attr]
            if j["status"] in states and j.get("progress", 0) >= min_progress:
                return j
            time.sleep(1.0)
        return self.http.get(f"/jobs/{job_id}").json()  # type: ignore[union-attr]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--engine-port", type=int, default=8188)
    a = ap.parse_args()
    t_start = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    state = Path(a.projects) / f"_state-{stamp}"
    project = Path(a.projects) / f"acceptance-{stamp}"
    print(f"M1 acceptance {stamp}: state {state}, project {project}")
    if port_busy(a.engine_port):
        print("engine port busy — stop the engine first"); return 2

    o = Orch(state, a.port).start()
    H = o.http
    try:
        # 1. project
        r = H.post("/project", json={"path": str(project), "name": "M1 acceptance", "size_cap_gb": 20})
        check("project created", r.status_code == 200, r.text[:120])
        # 2. one real generation (dev fp8 + Turbo, Draft size)
        recipe = {"kind": "t2i", "model_id": "flux2-dev-fp8mixed", "turbo": True, "width": 960, "height": 544, "seeds": [20261005],
                  "prompt_json": {"scene": "a rain-soaked harbour alley at night, neon sign", "subject": "a young woman in a green hooded cloak holding a brass compass",
                                  "style": "painterly storyboard frame", "camera": "medium shot, eye level"}}
        job = H.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]
        j = o.wait_job(job["id"], {"done", "failed", "cancelled"}, timeout=600)
        check("generation done", j["status"] == "done", f"{j['status']} wall {j.get('wall_s')} s {j.get('error') or ''}"[:200])
        asset_ids = j.get("result", {}).get("asset_ids", [])
        check("asset produced", len(asset_ids) == 1, str(asset_ids))
        if asset_ids:
            asset = H.get(f"/assets/{asset_ids[0]}").json()
            afile = project / asset["path"]
            check("asset file + manifest", afile.is_file() and afile.with_suffix(".json").is_file(), asset["path"])
            check("asset dimensions recorded", asset["w"] == 960 and asset["h"] == 544, f"{asset['w']}×{asset['h']}")
            check("thumbnail served", H.get(f"/thumbs/{asset['id']}/256").status_code == 200 and asset["thumb_status"] == "done")
            check("lineage endpoint", H.get(f"/lineage/{asset['id']}").status_code == 200)
            check("manifest carries graph hash + seed", bool(asset.get("compiled_graph_hash")) and asset["seed"] == 20261005)
            check("job indexed in the catalogue", H.get("/project").json().get("jobs_indexed", 0) >= 1)
        eng = H.get("/engine").json()
        check("engine supervised", eng["running"] and eng["responding"] and eng.get("job_object"), f"pid {eng.get('pid')} vram_free {eng.get('vram_free_gb')} GB")
        # 3. live contract: compile the same recipe against the live /object_info — no problems
        from importlib import import_module
        sys.path.insert(0, str(REPO / "orchestrator"))
        contract = import_module("loom2.engine.contract"); graphs = import_module("loom2.engine.graphs")
        roster_mod = import_module("loom2.roster"); recipes = import_module("loom2.recipes")
        live = httpx.get(f"http://127.0.0.1:{a.engine_port}/object_info", timeout=60).json()
        fixture = json.loads((REPO / "orchestrator" / "tests" / "fixtures" / "object_info.json").read_text(encoding="utf-8"))
        missing = [c for c in fixture["classes"] if c not in live]
        check("fixture classes exist on the live engine", not missing, str(missing))
        roster = roster_mod.Roster(Path("F:/loom2-models"), [Path("D:/comfyui/ComfyUI/models")]).scan()
        comp = graphs.compile_recipe(recipes.parse_recipe(recipe), roster, live, 1, "x")
        check("live contract check clean", comp.problems == [], str(comp.problems)[:200])
        # 4. hard kill mid-job → engine dies with the orchestrator (Job Object)
        job2 = H.post("/jobs", json={"recipe": {**recipe, "seeds": [7]}}).json()["jobs"][0]
        j2 = o.wait_job(job2["id"], {"running"}, timeout=120, min_progress=0.2)
        check("second job running mid-way", j2["status"] == "running" and j2["progress"] >= 0.2, f"progress {j2.get('progress')}")
        o.kill_hard()
        t0 = time.time()
        while port_busy(a.engine_port) and time.time() - t0 < 20:
            time.sleep(0.5)
        check("engine died with the orchestrator", not port_busy(a.engine_port), f"after {time.time()-t0:.1f} s")
        # 5. relaunch → paused, job queued
        o = Orch(state, a.port, project).start()
        H = o.http
        q = H.get("/queue").json()
        jr = H.get(f"/jobs/{job2['id']}").json()
        check("relaunch resumed paused with the job queued", q["paused"] and q.get("resumed_unclean") and jr["status"] == "queued" and jr["retry_count"] == 1,
              f"paused={q['paused']} status={jr['status']} retries={jr['retry_count']}")
        check("first asset still indexed", H.get("/assets").json()["items"][0]["id"] == asset_ids[0] if asset_ids else False)
        # 6. unpause → running → cancel kills the engine job (interrupt), engine stays alive
        H.post("/queue/unpause")
        jr = o.wait_job(job2["id"], {"running"}, timeout=180, min_progress=0.1)
        H.post(f"/jobs/{job2['id']}/cancel")
        jr = o.wait_job(job2["id"], {"cancelled", "done", "failed"}, timeout=60)
        check("cancel interrupted the running job", jr["status"] == "cancelled", jr["status"])
        eng = H.get("/engine").json()
        check("engine alive after cancel", eng["running"] and eng["responding"])
        # 7. graceful stop
        o.stop()
        t0 = time.time()
        while port_busy(a.engine_port) and time.time() - t0 < 30:
            time.sleep(0.5)
        check("graceful stop took the engine down", not port_busy(a.engine_port), f"after {time.time()-t0:.1f} s")
        qfile = json.loads((project / "jobs" / "queue.json").read_text(encoding="utf-8"))
        check("queue file marks a clean shutdown", qfile.get("clean_shutdown") is True)
    finally:
        o.stop()
        if port_busy(a.engine_port):
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "scripts" / "engine-stop.ps1")], capture_output=True)
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    row = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "passed": passed, "total": len(CHECKS), "wall_s": round(time.time() - t_start, 1),
           "project": str(project), "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in CHECKS]}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nM1 acceptance: {passed}/{len(CHECKS)} checks passed in {row['wall_s']} s")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
