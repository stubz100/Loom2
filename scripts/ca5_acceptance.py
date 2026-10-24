"""CA4 / CA5 (02 §3, proto01_animate 31 §4): a character layer re-taken from its second batch, accepted on the rig — the real engine on a
fresh copy of the A1 rig's project (Mara's layer: 81 frames at F16, two chained batches of Wan Animate):

1. the plan (CA4): two batches, both done, their measured times; nothing owed;
2. *Re-take from batch 2* (CA5): batch 1 kept (its clip unchanged), batch 2 made again with a new seed, continuing batch 1's clip (W1's
   carried 5 frames), the layer stitched and matted again;
3. the join between the kept batch and the new one is no worse than the old join (the mean step at frame 77 against the median step of the
   layer's frames — E23a's measure), and the frames before the join are the same files' pixels as before;
4. the time of the re-take against a whole layer's.

One GPU job at a time (D97): the engine runs the batch, then SAM 3. Results: engine/spikes/out/ca5/results.json.

    orchestrator/.venv/Scripts/python.exe scripts/ca5_acceptance.py
"""
from __future__ import annotations

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
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ca5"


def steps(frames: list[Path]) -> list[float]:
    a = [np.asarray(Image.open(p).convert("RGB").resize((208, 120)), dtype=np.float64) for p in frames]
    return [float(np.abs(a[i + 1] - a[i]).mean()) for i in range(len(a) - 1)]


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    P.OUT = OUT
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    app = P.App(OUT / "proj")
    try:
        fin = next(f for f in P.api("GET", "/finals")["items"] if f["clip_id"])
        lid = next(l["id"] for l in fin["layers"] if l["kind"] == "figure" and l["name"].startswith("Mara"))
        frames_dir = OUT / "proj" / "finals" / fin["id"] / lid / "frames"
        before = sorted(frames_dir.glob("*.png"))
        old_px = [np.asarray(Image.open(p)) for p in before[:77]]
        old_steps = steps(before)
        layer = next(l for l in fin["layers"] if l["id"] == lid)
        plan = P.api("GET", f"/finals/{fin['id']}/plan")
        pl = next(x for x in plan["layers"] if x["id"] == lid)
        check("the plan: two batches, both done, nothing owed", [b["state"] for b in pl["batches"]] == ["done", "done"] and pl["seconds_owed"] == 0,
              f"{[(b['k'], b['covers'], b['seconds']) for b in pl['batches']]}; {plan['source']}")
        t0 = time.time()
        r = P.api("POST", f"/finals/{fin['id']}/layers/{lid}/run", {"from_batch": 1})
        j = P.wait_job(r["job_id"])
        lay = next(l for l in P.api("GET", f"/finals/{fin['id']}")["layers"] if l["id"] == lid)
        jm = P.wait_job(lay["job_ids"][-1])
        took = round(time.time() - t0, 1)
        lay = next(l for l in P.api("GET", f"/finals/{fin['id']}")["layers"] if l["id"] == lid)
        check("batch 2 again with a new seed, continuing batch 1", j["status"] == "done" and j["recipe"]["seeds"] == [layer["seed"] + 1]
              and j["recipe"]["chain"]["clip_id"] == layer["batches"][0]["clip_id"] and lay["batches"][0]["clip_id"] == layer["batches"][0]["clip_id"]
              and lay["batches"][1]["clip_id"] != layer["batches"][1]["clip_id"], f"seed {j['recipe']['seeds']}, chain {j['recipe']['chain']}")
        check("stitched and matted again", jm["status"] == "done" and jm["recipe"]["kind"] == "matte_sequence" and lay["status"] == "done" and lay["frames_done"] == fin["frames"],
              f"{lay['status']} · {lay['frames_done']} frames")
        after = sorted(frames_dir.glob("*.png"))
        same = all(np.array_equal(a, np.asarray(Image.open(p))) for a, p in zip(old_px, after[:77]))
        check("the frames before the join unchanged", same and len(after) == fin["frames"], f"{len(after)} frames")
        new_steps = steps(after)
        med = float(np.median(new_steps))
        join_old, join_new = old_steps[76] / float(np.median(old_steps)), new_steps[76] / med
        check("the new join no worse than the old (step at frame 77 / median step)", join_new <= max(1.5, join_old * 1.25), f"old {join_old:.2f}, new {join_new:.2f}")
        res.update({"took_s": took, "batch_s": j.get("wall_s"), "matte_s": jm.get("wall_s"), "join_old": round(join_old, 3), "join_new": round(join_new, 3)})
        check("the time", True, f"re-take + matte {took} s (batch {j.get('wall_s')} s, matte {jm.get('wall_s')} s)")
    finally:
        app.close()
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ca5_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
