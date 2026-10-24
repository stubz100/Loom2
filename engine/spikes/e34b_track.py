"""E34b (proto01_animate 31 §4c, after CA3's rig): does the plate generated along the path hold the camera's path? CA3's rig runs led the
set mid-move (the room's sideways travel against the set's clay pass: 142 / 124 at F16, 171 / 122 at F24, 151 / 122 with a plain prompt)
where E34 had held it (118 / 122). On a CA3 run's project (its still, its depth guide, its seed), the plate's clip again with one thing
changed at a time — the negative without "static" (LTX's stock negative asks for motion from frame 0), the Quality preset (20 steps) — each
measured the way scripts/ca3_acceptance.py measures it.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e34b_track.py engine/spikes/out/ca3_f24_plain     # the engine free (D97)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
from ca3_acceptance import travel  # noqa: E402

VARIANTS = {
    "negative without static": {"negative": "blurry, distorted, low quality, watermark"},
    "quality (20 steps)": {"preset": "quality"},
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    run = Path(sys.argv[1]).resolve()
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    from loom2.clips import ClipStore
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    ws = Workspace(run / "proj")
    store = FinalStore(ws)
    f = store.get(res["final_id"])
    plate = next(x for x in f.layers if x.id == "plate")
    jobs = {j["id"]: j for j in json.loads((ws.path / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
    base = jobs[plate.job_ids[-1]]
    clay = sorted(store.pass_dir(f.id, "plate", "clay").glob("*.png"))
    t_set = travel(clay)
    out = {"run": run.name, "seed": base["seed"], "clay": t_set, "as_run": res["travel_px"]["generated"], "variants": {}}
    P.OUT = run
    app = P.App(run / "proj")
    try:
        queued = {}
        for name, change in VARIANTS.items():
            recipe = {**base["recipe"], **change, "seeds": [base["seed"]]}
            queued[name] = P.api("POST", "/jobs", {"recipe": recipe, "stage": False})["jobs"][0]["id"]
        for name, jid in queued.items():
            j = P.wait_job(jid, timeout=3600)
            if j["status"] != "done":
                out["variants"][name] = {"error": j.get("error")}
                continue
            clip = ClipStore(ws).get(j["result"]["clip_id"])
            frames = [ClipStore(ws).frame_path(clip.id, i) for i in range(min(clip.frames, f.frames))]
            t = travel(frames)
            out["variants"][name] = {"travel": t, "end": t[-1], "apart": max(abs(a - c) for a, c in zip(t, t_set)), "seconds": j.get("wall_s"), "clip_id": clip.id}
    finally:
        app.close()
    (run / "e34b.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"the set {t_set[-1]} px · as run {out['as_run'][-1]} (apart {max(abs(a - c) for a, c in zip(out['as_run'], t_set))})")
    for name, v in out["variants"].items():
        print(f"{name}: " + (f"{v['end']} px, at most {v['apart']} apart, {v['seconds']} s" if "end" in v else f"failed: {v['error']}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
