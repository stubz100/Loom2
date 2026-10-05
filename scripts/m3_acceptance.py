"""M3 rig acceptance (12 §4, 09 §10): a staged batch of 8 dev Turbo images completes unattended and resumes after a
hard kill; previews stream; every image lands as an asset with seed, params, serialised prompt and lineage; a
reference-image job compiles and runs; distilled/base rules and the exact-string preview come from the API.

  orchestrator/.venv/Scripts/python.exe scripts/m3_acceptance.py [--projects F:/loom2-projects] [--port 8767]
Appends a JSON line to engine/spikes/out/m3_acceptance.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from m1_acceptance import CHECKS, Orch, check, port_busy  # noqa: E402

RESULTS = REPO / "engine" / "spikes" / "out" / "m3_acceptance.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--engine-port", type=int, default=8188)
    a = ap.parse_args()
    t_start = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    state = Path(a.projects) / f"_state-m3-{stamp}"
    project = Path(a.projects) / f"m3-acceptance-{stamp}"
    print(f"M3 acceptance {stamp}: state {state}, project {project}")
    if port_busy(a.engine_port):
        print("engine port busy — wait for the running job to finish"); return 2
    tree = json.loads((REPO / "bench" / "t2i" / "02-captain-cabin.json").read_text(encoding="utf-8"))
    recipe = {"kind": "t2i", "model_id": "flux2-dev-fp8mixed", "prompt_mode": "tree", "prompt_json": tree, "turbo": True, "width": 640, "height": 352, "seeds": [0] * 8}

    o = Orch(state, a.port).start()
    H = o.http
    try:
        r = H.post("/project", json={"path": str(project), "name": "M3 acceptance", "size_cap_gb": 20})
        check("project created", r.status_code == 200)
        # 1. preview: exact string, rules
        pv = H.post("/recipes/preview", json={"recipe": recipe}).json()
        check("preview: dev gets compact JSON", pv["prompt_mode"] == "json" and pv["serialized_prompt"].startswith("{") and pv["steps"] == 8 and pv["count"] == 8, f"{pv['prompt_mode']} {pv['steps']} st, {pv['word_count']} words")
        pvk = H.post("/recipes/preview", json={"recipe": {**recipe, "model_id": "klein-9b", "steps": 30, "cfg": 5, "negative": "blurry"}}).json()
        check("preview: distilled Klein fixes steps/CFG and drops the negative", pvk["prompt_mode"] == "prose" and pvk["steps"] == 4 and pvk["cfg"] == 1.0 and pvk["negative_used"] is False)
        pvb = H.post("/recipes/preview", json={"recipe": {**recipe, "model_id": "klein-base-9b", "negative": "blurry"}}).json()
        check("preview: Klein base enables CFG + negative", pvb["cfg"] == 3.5 and pvb["negative_used"] is True)
        # 2. stage 8, release, previews, kill mid-batch
        jobs = H.post("/jobs", json={"recipe": recipe, "stage": True}).json()["jobs"]
        check("8 jobs staged", len(jobs) == 8 and all(j["status"] == "staged" for j in jobs) and len({j["seed"] for j in jobs}) == 8, "distinct random seeds")
        time.sleep(3)
        q = H.get("/queue").json()
        check("staged jobs are not picked up", q["running"] is None and q["counts"].get("staged") == 8)
        released = H.post("/queue/release").json()["released"]
        check("release queues all 8", len(released) == 8)
        ids = [j["id"] for j in jobs]
        # wait until at least 2 are done and one is running mid-way → kill
        t0 = time.time()
        saw_preview = False
        while time.time() - t0 < 900:
            js = [H.get(f"/jobs/{i}").json() for i in ids]
            done = [j for j in js if j["status"] == "done"]
            running = [j for j in js if j["status"] == "running"]
            if running and running[0]["progress"] >= 0.3 and any(j["status"] == "running" and j["progress"] > 0 for j in js):
                saw_preview = saw_preview or True
            if len(done) >= 2 and running and running[0]["progress"] >= 0.3:
                break
            time.sleep(1.5)
        check("two done, third running mid-way", len(done) >= 2 and bool(running), f"done {len(done)}, running progress {running[0]['progress'] if running else None}")
        o.kill_hard()
        t0 = time.time()
        while port_busy(a.engine_port) and time.time() - t0 < 20:
            time.sleep(0.5)
        check("engine died with the orchestrator", not port_busy(a.engine_port))
        # 3. relaunch: paused, interrupted job queued, done assets intact
        o = Orch(state, a.port, project).start()
        H = o.http
        q = H.get("/queue").json()
        js = [H.get(f"/jobs/{i}").json() for i in ids]
        check("relaunch: paused, interrupted job re-queued, others queued", q["paused"] and q.get("resumed_unclean") and sum(j["status"] == "queued" for j in js) == 8 - len(done) and sum(j["status"] == "done" for j in js) == len(done))
        H.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 1200:
            js = [H.get(f"/jobs/{i}").json() for i in ids]
            if all(j["status"] in ("done", "failed", "cancelled") for j in js):
                break
            time.sleep(3)
        check("all 8 done after resume", all(j["status"] == "done" for j in js), ", ".join(f"{j['status']}" for j in js))
        walls = [j["wall_s"] for j in js if j.get("wall_s")]
        check("per-image time recorded", len(walls) == 8, f"{min(walls):.0f}–{max(walls):.0f} s at 640×352 Turbo" if walls else "")
        # 4. assets: seeds, params, serialised prompt, lineage
        assets = [H.get(f"/assets/{j['result']['asset_ids'][0]}").json() for j in js if j.get("result", {}).get("asset_ids")]
        check("8 assets with seed, recipe, serialised prompt and graph hash", len(assets) == 8 and all(a["seed"] == j["seed"] for a, j in zip(assets, js)) and all(a["params"].get("recipe") and a["prompt_text"].startswith("{") and a["compiled_graph_hash"] for a in assets))
        check("assets share the batch id", len({a["batch_id"] for a in assets}) == 1 and assets[0]["batch_id"] == jobs[0]["batch_id"])
        groups = H.get("/assets/groups", params={"group": "batch", "suite": "generate"}).json()
        check("catalogue groups the batch", any(g["key"] == assets[0]["batch_id"] and g["count"] == 8 for g in groups))
        # 5. reference image job (FLUX.2 unified editing) on the first result
        ref_recipe = {**recipe, "seeds": [20261005], "refs": [{"asset_id": assets[0]["id"]}], "prompt_mode": "text",
                      "prompt_text": "the same captain's cabin as reference image 1, but at night with the lamp as the only light"}
        rj = H.post("/jobs", json={"recipe": ref_recipe}).json()["jobs"][0]
        rj = o.wait_job(rj["id"], {"done", "failed", "cancelled"}, timeout=600)
        check("reference-image job runs (ReferenceLatent chain)", rj["status"] == "done" and rj["result"]["compiled"]["refs"] == 1, f"{rj['status']} {rj.get('wall_s')} s {rj.get('error') or ''}"[:160])
        if rj["status"] == "done":
            ra = H.get(f"/assets/{rj['result']['asset_ids'][0]}").json()
            check("reference recorded as lineage parent", ra["parents"] == [assets[0]["id"]] and H.get(f"/lineage/{ra['id']}").json()["parents"][0]["from_id"] == assets[0]["id"])
        o.stop()
    finally:
        o.stop()
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    row = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "passed": passed, "total": len(CHECKS), "wall_s": round(time.time() - t_start, 1), "project": str(project),
           "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in CHECKS]}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nM3 acceptance: {passed}/{len(CHECKS)} checks passed in {row['wall_s']} s")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
