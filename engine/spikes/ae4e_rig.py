"""AE4e rig (D118): a processing layer on the PS5 rig's final through the app — the stack from Mara's layer down rendered apart by the real
effectcraft-cli, the Creative pass over it on the real engine (LTX-2.3 locked to the shot's depth: the fast one), the composition synced
(the layer brought in above Mara), the finished shot rendered; then the plate nudged below it (stale), the pass run again (replaced, not
stale), the layer dropped. Outputs under engine/spikes/out/ae4e/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/ae4e_rig.py [--preset creative|cleanup] [--strength 0.35]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
from m1_acceptance import Orch  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "ae4e"
PROJECT = ROOT / "engine" / "spikes" / "out" / "ps5" / "project"
FID, LID = "fin_0f41f551", "fig_m"
PORT = 8797


def log(m: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"
    print(line, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="creative")
    ap.add_argument("--strength", type=float, default=0.35)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    o = Orch(state, PORT, PROJECT).start(timeout=180)
    results: dict = {}
    try:
        h = o.http
        c0 = h.get(f"/finals/{FID}/composition").json()
        layers0 = h.get(f"/finals/{FID}/composition/layers").json()["items"]
        point = next(cl for cl in c0["layers"] if cl["id"] == LID)
        idx0 = next(l["index"] for l in layers0 if l["id"] == point["layer"])
        log(f"composition rev {c0['revision']} · {len(layers0)} layers · Mara's engine layer {point['layer']} at index {idx0} · processing {c0.get('processing')}")

        def run_pass(strength: float) -> dict:
            t0 = time.time()
            r = h.post(f"/finals/{FID}/layers/{LID}/pass", json={"preset": a.preset, "strength": strength, "scope": "below"}, timeout=120)
            r.raise_for_status()
            j = o.wait_job(r.json()["job_id"], {"done", "failed", "cancelled"}, timeout=3600)
            log(f"  {j['status']} {j['id']} in {time.time() - t0:.0f} s: {(j.get('log_tail') or [])[-2:]}")
            return {"status": j["status"], "wall_s": round(time.time() - t0), "job_id": j["id"], "error": j.get("error")}
        results["first"] = run_pass(a.strength)
        if results["first"]["status"] != "done":
            raise SystemExit(1)
        c1 = h.post(f"/finals/{FID}/composition/sync", timeout=300).json()
        layers1 = h.get(f"/finals/{FID}/composition/layers").json()["items"]
        pid = f"proc_{LID}"
        eid = c1["processing"][pid]
        pl = next(l for l in layers1 if l["id"] == eid)
        idx_m = next(l["index"] for l in layers1 if l["id"] == point["layer"])
        log(f"synced: rev {c1['revision']} · processing {c1['processing']} stale {c1['processing_stale']} · '{pl['name']}' at index {pl['index']}, Mara at {idx_m}")
        results["synced"] = {"layer": eid, "index": pl["index"], "mara_index": idx_m, "name": pl["name"], "stale": c1["processing_stale"].get(pid)}
        t1 = time.time()
        jid = h.post(f"/finals/{FID}/composition/render", timeout=60).json()["job_id"]
        j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=1800)
        if j["status"] == "done":
            clip = h.get(f"/clips/{j['result']['clip_id']}").json()
            shutil.copyfile(PROJECT / clip["proxy_path"], OUT / f"final_processed_{a.preset}.mp4")
        results["render"] = {"status": j["status"], "wall_s": round(time.time() - t1)}
        log(f"  rendered: {results['render']}")
        # a change below: the plate nudged → stale; run again → replaced, fresh
        plate = next(cl for cl in c1["layers"] if cl["id"] == "plate")
        h.post(f"/finals/{FID}/composition/batch", json={"steps": [{"id": "layer.nudge", "params": {"layers": [plate["layer"]], "x": 2, "y": 0}}]}, timeout=300).raise_for_status()
        c2 = h.get(f"/finals/{FID}/composition").json()
        log(f"the plate nudged: rev {c2['revision']} · stale {c2['processing_stale']}")
        results["stale_after_nudge"] = c2["processing_stale"].get(pid)
        results["again"] = run_pass(a.strength)
        c3 = h.post(f"/finals/{FID}/composition/sync", timeout=300).json()
        layers3 = h.get(f"/finals/{FID}/composition/layers").json()["items"]
        log(f"run again and synced: rev {c3['revision']} · processing {c3['processing']} stale {c3['processing_stale']} · processed layers {sum(1 for l in layers3 if l['name'].startswith('Processed'))}")
        results["again_synced"] = {"same_layer": c3["processing"].get(pid) == eid, "stale": c3["processing_stale"].get(pid), "count": sum(1 for l in layers3 if l["name"].startswith("Processed"))}
        h.post(f"/finals/{FID}/composition/batch", json={"steps": [{"id": "layer.nudge", "params": {"layers": [plate["layer"]], "x": -2, "y": 0}}]}, timeout=300).raise_for_status()
        r = h.delete(f"/finals/{FID}/processing/{pid}", timeout=300)
        c4 = r.json().get("composition") or {}
        layers4 = h.get(f"/finals/{FID}/composition/layers").json()["items"]
        log(f"dropped: {r.status_code} · processing {c4.get('processing')} · processed layers {sum(1 for l in layers4 if l['name'].startswith('Processed'))} · {len(layers4)} layers")
        results["dropped"] = {"status": r.status_code, "count": sum(1 for l in layers4 if l["name"].startswith("Processed")), "layers": len(layers4)}
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        log(f"done: {json.dumps(results)}")
    finally:
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
