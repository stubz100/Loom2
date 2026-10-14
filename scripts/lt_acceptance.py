"""18 §8 (D86) acceptance of the LoRA wave on the rig, through the app's API: a project with the hero (bench/angles/07.jpg) → Mara → Expand
`full` on Klein 9B (36 candidates, all kept) → a `train_lora` job on Klein base-4B (1 000 steps, staged, released) → the orchestrator killed at
step ≥ 300 and relaunched on its state (the trainer dies with it — the job object), the job requeued → it resumes from the step-250 save and
finishes → the record, the version's slot, the engine's cache, `GET /loras` on Klein 4B → a Generate job "@Mara at the gate" takes the LoRA
and the trigger by itself (the manifest says so) → the identity check (8 jobs, FaceSim with / without) → a wrong base refused (422) → Delete.

Needs port 8188 free (the orchestrator it starts launches the engine) and the trainer venv (scripts/trainer-setup.ps1). Models on F:.
Results: engine/spikes/out/lt/results.jsonl, the orchestrator log, the check sheet.

    orchestrator/.venv/Scripts/python.exe scripts/lt_acceptance.py [--steps 1000] [--kill-at 300] [--no-kill]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))

PORT, TOKEN, ENGINE = 8776, "lora", "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "lt"
HERO = ROOT / "bench" / "angles" / "07.jpg"
STUB = "Mara, a wiry courier in a long grey coat with a red scarf"
BARS = {"s_per_it": 2.0, "vram_gb": 15.0, "facesim": 0.30, "over": 0.20}


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def status_of(method: str, path: str, body=None) -> int:
    try:
        api(method, path, body)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def wait_jobs(ids: list[str], timeout_s: float = 3600, progress_s: float = 900, on_poll=None) -> dict[str, dict]:
    t0, last, t_prog = time.time(), -1, time.time()
    while time.time() - t0 < timeout_s:
        jobs = {j["id"]: j for j in api("GET", "/jobs")["items"] if j["id"] in ids}
        if on_poll:
            on_poll(jobs)
        done = [j for j in jobs.values() if j["status"] in ("done", "failed", "cancelled")]
        if len(done) != last:
            last, t_prog = len(done), time.time()
            log(f"  jobs {len(done)}/{len(ids)} finished")
        if len(done) >= len(ids):
            return jobs
        if time.time() - t_prog > progress_s:
            raise TimeoutError("no job progress")
        time.sleep(2.0)
    raise TimeoutError("jobs")


def sheet(ids: list[str], path: Path, labels: dict[str, str], cols: int = 8, cell: int = 192) -> None:
    rows = (len(ids) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 16)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, aid in enumerate(ids):
        try:
            th = Image.open(io.BytesIO(api("GET", f"/thumbs/{aid}/256", raw=True))).convert("RGB")
        except Exception:
            continue
        th.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        im.paste(th, (x, y))
        d.text((x + 2, y + cell + 2), labels.get(aid, "")[:36], fill=(220, 220, 220))
    im.save(path, quality=88)


def restart_orchestrator(proc: dict, check) -> None:
    proc["orch"].kill()
    try:
        proc["orch"].wait(timeout=20)
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < 10:
        try:
            api("GET", "/health"); time.sleep(0.3)
        except Exception:
            break
    proc["orch"] = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(proc["state"]), "--project", str(proc["project"])],
                                    cwd=str(ROOT / "orchestrator"), env=proc["env"], stdout=proc["log"], stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    while time.time() - t0 < 90:
        try:
            if api("GET", "/project")["open"]:
                break
        except Exception:
            pass
        time.sleep(0.5)
    check(api("GET", "/project")["open"], "the orchestrator relaunched with the project open")


def trainer_pids() -> list[int]:
    # python processes only: the PowerShell query's own command line carries the pattern and would match itself
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*ai-toolkit*run.py*' }).ProcessId"],
                         capture_output=True, text=True).stdout.split()
    return [int(x) for x in out if x.strip().isdigit()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--kill-at", type=int, default=300)
    ap.add_argument("--no-kill", action="store_true")
    ap.add_argument("--preset", default="full")
    ap.add_argument("--reuse", default=None, help="a previous run's temp dir (loom2-lt-*): skip Expand and the training, run the checks after it on its LoRA")
    a = ap.parse_args()
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1)"); return 2
    except Exception:
        pass
    if trainer_pids():
        print("a trainer is already running:", trainer_pids()); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(a.reuse) if a.reuse else Path(tempfile.mkdtemp(prefix="loom2-lt-"))
    from loom2.config import AppState
    if not a.reuse:
        AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("a" if a.reuse else "w", encoding="utf-8")
    argv = [sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")] + (["--project", str(tmp / "proj")] if a.reuse else [])
    proc = {"orch": subprocess.Popen(argv, cwd=str(ROOT / "orchestrator"), env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True),
            "env": env, "log": orch_log, "state": tmp / "state", "project": tmp / "proj"}
    log(f"orchestrator on {PORT}, state {tmp} ({'reused' if a.reuse else 'new'})")
    failures: list[str] = []
    row: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "steps": a.steps}

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            failures.append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        if not a.reuse:
            api("POST", "/project", {"path": str(tmp / "proj"), "name": "LT", "size_cap_gb": 60})
        caps = api("GET", "/capabilities")
        tc = caps["train"]
        check(tc["available"] and any(b["model_id"] == "klein-base-4b" and b["health"] != "missing" for b in tc["bases"]), f"the trainer is available with Klein base-4B ({tc['why']})")
        check(caps["facesim"]["available"], "FaceSim weights present (the identity check)")
        if a.reuse:                                                                            # the trained state of a previous run
            p = api("GET", "/story/profiles")["items"][0]
            pid, vid = p["id"], p["versions"][0]["id"]
            refs = api("GET", f"/groups/{p['versions'][0]['group_id']}")["assets"]
            recs = api("GET", "/story/loras")["items"]
            check(bool(recs) and p["versions"][0]["lora"] == recs[0]["id"], f"reused: {p['name']} {vid} with LoRA {recs[0]['id'] if recs else None} and {len(refs)} references")
            row.update({"reused": str(tmp), "refs": len(refs)})
            rec = recs[0]
            cache = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")) / "loras" / "projects" / api("GET", "/project")["id"] / f"{rec['id']}.safetensors"
            after_training(pid, rec, refs, cache, check, row)
            row["failures"] = failures
            (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(row) + "\n")
            print(json.dumps({k: v for k, v in row.items() if k != "identity"}, indent=1))
            return 1 if failures else 0
        hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
        p = api("POST", "/story/profiles", {"name": "Mara", "cls": "character", "hero_asset_id": hero, "stub": STUB})
        pid, vid = p["id"], p["versions"][0]["id"]
        # 1. the reference set through Expand (the product's path, as E16)
        t_exp = time.time()
        r = api("POST", f"/story/profiles/{pid}/expand", {"preset": a.preset, "seeds_per_cell": 1, "tier": "draft"})
        jobs = wait_jobs(r["job_ids"])
        cands = list(api("GET", f"/groups/{r['group_id']}")["assets"].values())
        api("POST", f"/story/profiles/{pid}/versions/{vid}/curate", {"asset_ids": [x["id"] for x in cands], "verdict": "keep"})
        refs = api("GET", f"/groups/{p['versions'][0]['group_id']}")["assets"]
        check(len(refs) == len(cands) + 1 >= 25, f"{len(refs)} references on the version's page after Expand ({time.time() - t_exp:.0f} s)")
        row["refs"] = len(refs)
        # 2. the staged training job, released; killed at a step and resumed
        tr = api("POST", f"/story/profiles/{pid}/train", {"model_id": "klein-base-4b", "steps": a.steps, "setting": "plain studio background", "stage": True})
        check(tr["staged"] and tr["trigger"].startswith("mara_"), f"train staged: job {tr['job_id']}, trigger {tr['trigger']}, base {tr['model_id']}")
        check(api("GET", f"/story/profiles/{pid}")["versions"][0]["trigger"] == tr["trigger"], "the version carries the trigger before the job runs")
        api("POST", f"/jobs/{tr['job_id']}/release")
        t_train = time.time()
        killed = {"done": False, "step": None}

        def on_poll(js: dict) -> None:
            j = js.get(tr["job_id"])
            if not j or killed["done"] or a.no_kill:
                return
            txt = j.get("progress_text") or ""
            if txt.startswith("step "):
                try:
                    step = int(txt.split()[1])
                except ValueError:
                    return
                if step >= a.kill_at:
                    killed["done"], killed["step"] = True, step
                    log(f"  killing the orchestrator at step {step} (trainer pids {trainer_pids()})")
                    restart_orchestrator(proc, check)
                    time.sleep(3)
                    pids = trainer_pids()
                    check(not pids, f"the trainer died with the orchestrator (job object) — pids now {pids}")
                    j2 = api("GET", f"/jobs/{tr['job_id']}")
                    log(f"  after the relaunch the job is {j2['status']} (resumable {j2.get('resumable')}), queue paused {api('GET', '/queue')['paused']}")
                    if j2["status"] == "failed":
                        api("POST", f"/jobs/{tr['job_id']}/requeue")
                    if api("GET", "/queue")["paused"]:
                        api("POST", "/queue/unpause")

        jobs = wait_jobs([tr["job_id"]], timeout_s=5400, progress_s=1500, on_poll=on_poll)
        j = jobs[tr["job_id"]]
        wall = time.time() - t_train
        check(j["status"] == "done", f"the training job finished: {j['status']} in {wall:.0f} s — {j.get('error') or j.get('progress_text')}")
        res = j.get("result") or {}
        row.update({"train_wall_s": round(wall, 1), "s_per_it": res.get("s_per_it"), "peak_vram_gb": res.get("peak_vram_gb"), "resumed_from": res.get("resumed_from"), "killed_at": killed["step"]})
        if j["status"] == "done":
            check(bool(res.get("s_per_it")) and res["s_per_it"] <= BARS["s_per_it"], f"{res.get('s_per_it')} s/it (bar ≤ {BARS['s_per_it']})")
            check(res.get("peak_vram_gb") is not None and res["peak_vram_gb"] <= BARS["vram_gb"], f"peak VRAM {res.get('peak_vram_gb')} GB (bar ≤ {BARS['vram_gb']})")
            if not a.no_kill:
                check(bool(res.get("resumed_from")), f"resumed from step {res.get('resumed_from')} after the kill at {killed['step']}")
            rec = api("GET", f"/story/loras/{res['lora_id']}")
            v = api("GET", f"/story/profiles/{pid}")["versions"][0]
            check(v["lora"] == rec["id"] and v["trigger"] == rec["trigger"], "the version holds the LoRA and its trigger")
            check(rec["dataset"]["count"] == len(refs) and rec["dataset"]["setting"] == "plain studio background" and rec["size"] > 10_000_000, f"the record: {rec['dataset']['count']} refs, {rec['size'] / 2**20:.0f} MB, sha {rec['sha256'][:8]}")
            cache = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")) / "loras" / "projects" / api("GET", "/project")["id"] / f"{rec['id']}.safetensors"
            check(cache.is_file() and cache.stat().st_size == rec["size"], f"the engine's cache {cache.name} is there")
            slots = api("GET", "/loras?model_id=klein-4b")["items"]
            check(bool(slots) and slots[0]["id"] == rec["id"] and slots[0]["fits"] and slots[0]["source"] == "trained" and slots[0]["trigger"] == rec["trigger"], "GET /loras on Klein 4B lists it first, fitting, with the trigger")
            check(not any(o["id"] == rec["id"] and o["fits"] for o in api("GET", "/loras?model_id=klein-9b")["items"]), "on Klein 9B it does not fit")
            after_training(pid, rec, refs, cache, check, row)
        row["failures"] = failures
        (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(row) + "\n")
        print(json.dumps({k: v for k, v in row.items() if k != "identity"}, indent=1))
    finally:
        shutdown(proc, orch_log)
    print(f"{len(failures)} failure(s)" if failures else "all checks ok")
    return 1 if failures else 0


def after_training(pid: str, rec: dict, refs: dict, cache: Path, check, row: dict) -> None:
    """18 §8 items 3–6: the mention's auto-slot, the identity check, the base gate, the delete — on a trained version."""
    if True:
        if True:
            # 3. the mention: @Mara takes the LoRA and the trigger by itself
            pv = api("POST", "/recipes/preview", {"recipe": {"kind": "t2i", "model_id": "klein-4b", "prompt_mode": "text", "prompt_text": "@Mara waits at the city gate at dawn", "width": 1024, "height": 576,
                                                              "mentions": [{"profile_id": pid, "name": "Mara"}]}})
            check(pv["mentions"][0].get("lora") == rec["id"] and pv["loras"][0]["model_id"] == rec["id"] and rec["trigger"] in pv["serialized_prompt"], f"the preview adds the LoRA and the trigger: {pv['serialized_prompt'][:120]!r}")
            t_gen = time.time()
            job = api("POST", "/jobs", {"recipe": {"kind": "t2i", "model_id": "klein-4b", "prompt_mode": "text", "prompt_text": "@Mara waits at the city gate at dawn", "width": 1024, "height": 576, "seeds": [11],
                                                   "mentions": [{"profile_id": pid, "name": "Mara"}]}, "stage": False, "origin": {"suite": "generate", "surface": "results"}})["jobs"][0]
            g = wait_jobs([job["id"]])[job["id"]]
            check(g["status"] == "done", f"the Generate job with @Mara done in {time.time() - t_gen:.0f} s")
            if g["status"] == "done":
                asset = api("GET", f"/assets/{g['result']['asset_ids'][0]}")
                check(asset["params"]["recipe"]["loras"][0]["model_id"] == rec["id"] and asset["params"]["recipe"]["mentions"][0]["lora"] == rec["id"], "the manifest records the slot the mention added")
                check(g["result"]["compiled"]["loras"][0]["lora_name"].endswith(f"{rec['id']}.safetensors"), "the engine loaded it under its cache name")
                (OUT / "mention_result.jpg").write_bytes(api("GET", f"/assets/{asset['id']}/file", raw=True))
            # 4. the identity check: 8 jobs, FaceSim with / without
            t_chk = time.time()
            chk = api("POST", f"/story/loras/{rec['id']}/check")
            cj = wait_jobs(chk["job_ids"])
            check(all(x["status"] == "done" for x in cj.values()), f"the check's {len(cj)} jobs done in {time.time() - t_chk:.0f} s on {chk['model_id']}")
            ident = api("GET", f"/story/loras/{rec['id']}")["identity"]
            row["identity"] = ident
            wm, wo = ident.get("with_mean"), ident.get("without_mean")
            check(ident.get("status") == "ok" and wm is not None, f"identity {ident.get('status')}: with {wm} · without {wo} over {ident.get('done')} images")
            if wm is not None:
                check(wm >= BARS["facesim"] and wm >= (wo or 0) + BARS["over"], f"FaceSim with {wm} ≥ {BARS['facesim']} and ≥ without {wo} + {BARS['over']}")
            page = api("GET", f"/groups/{chk['group_id']}")["assets"]
            labels = {x["id"]: f"{x['params']['recipe'].get('loras') and 'with' or 'without'} {x['seed']}" for x in page.values()}
            sheet(list(page), OUT / "check.jpg", labels)
            # 5. the gate and the delete
            check(status_of("POST", "/jobs", {"recipe": {"kind": "t2i", "model_id": "klein-9b", "prompt_mode": "text", "prompt_text": "x", "width": 64, "height": 64, "seeds": [1],
                                                        "loras": [{"model_id": rec["id"], "strength": 1.0}]}, "stage": False}) == 422, "a wrong base is refused at submission (422)")
            api("DELETE", f"/story/loras/{rec['id']}")
            check(status_of("GET", f"/story/loras/{rec['id']}") == 404 and not cache.exists() and api("GET", f"/story/profiles/{pid}")["versions"][0]["lora"] is None
                  and api("GET", f"/story/profiles/{pid}")["versions"][0]["trigger"] == rec["trigger"], "Delete: the record, the cache and the slot gone, the trigger kept")


def shutdown(proc: dict, orch_log) -> None:
    try:
        api("POST", "/shutdown")
    except Exception:
        pass
    try:
        proc["orch"].wait(timeout=60)
    except Exception:
        proc["orch"].kill()
    orch_log.close()
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2)
        pid = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 8188 -State Listen | Select-Object -First 1).OwningProcess"], capture_output=True, text=True).stdout.strip()
        if pid.isdigit():
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
            print(f"stopped the leftover engine (pid {pid})")
    except Exception:
        pass
    for pid in trainer_pids():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        print(f"stopped a leftover trainer (pid {pid})")


if __name__ == "__main__":
    sys.exit(main())
