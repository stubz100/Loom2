"""E35 (Q26 → D131, proto01_animate 31 §4e): the plate for a large camera move as Klein stills chained along the path — the author's scheme:
each frame's still made from that frame's clay pass (image 1, Stage's clay method) with the stills just before it as its references
(frame 10 from 9, 8 and 7; Klein takes four images), so the room stays where the set is (each still is its own frame's clay) and keeps its
look (each still sees the ones before it). On CA3's F16 run (the same set, path, first still, prompt and seed as the plate generated along
the path that led the set by 32 px of 256):

  A — dense: every frame a still from its clay and the three before it (80 Klein shots);
  B — keyframes: every 8th frame a still from its clay and the three keyframes before it; Stage projects each keyframe along the path and
      a frame between two keyframes blends their projections by its distance to each (10 Klein shots).

Measured as CA3: the room's travel against the set's clay (every 8 frames, px of 256), the step frame to frame (flicker), the time; beside
the first still projected alone (PS5b) and CA3's generated plate. Contact sheet: the set · projected · generated · A · B.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e35_chain.py     # Vite on 1420; the engine free (one GPU job at a time, D97)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e35_chain.py --measure   # the measurements again (no GPU)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
from ca3_acceptance import PROMPT, travel  # noqa: E402
from e34_plate import flicker  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "ca3_f16"
OUT = ROOT / "engine" / "spikes" / "out" / "e35"
KEY_EVERY = 8
NOTE = "the same empty room a moment earlier, seen from nearly the same place: keep its walls, window, floor, light and materials exactly"


def still_paths(ids: dict[int, str]) -> dict[int, Path]:
    return {k: OUT / "proj" / P.api("GET", f"/assets/{a}")["path"] for k, a in ids.items()}


def chain(base: dict, clay_ids: list[str], frames: list[int], first: str, log: list) -> dict[int, str]:
    """Klein stills at `frames` in order, each from its clay with the three stills before it in the chain as its references."""
    made = {frames[0]: first}
    for k in frames[1:]:
        prev = [made[x] for x in reversed(list(made))][:3]
        recipe = {**base, "passes": {"clay": clay_ids[k]}, "refs": [{"asset_id": a, "note": NOTE} for a in prev], "seeds": [base["seeds"][0]]}
        t0 = time.time()
        jid = P.api("POST", "/jobs", {"recipe": recipe, "stage": False})["jobs"][0]["id"]
        j = P.wait_job(jid, timeout=1800)
        if j["status"] != "done":
            raise RuntimeError(f"frame {k}: {j.get('error')}")
        made[k] = j["result"]["asset_ids"][0]
        log.append({"frame": k, "job": jid, "wall_s": j.get("wall_s"), "s": round(time.time() - t0, 1)})
        print(f"frame {k}: {j.get('wall_s')} s", flush=True)
    return made


def run() -> dict:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC / "proj", OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    ca3 = json.loads((SRC / "results.json").read_text(encoding="utf-8"))
    fid = ca3["final_id"]
    P.OUT = OUT
    app = P.App(OUT / "proj")
    res: dict = {"final_id": fid, "times": {}}
    try:
        f = P.api("GET", f"/finals/{fid}")
        plate = next(x for x in f["layers"] if x["id"] == "plate")
        jobs = {j["id"]: j for j in json.loads((OUT / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
        still_job = jobs[plate["job_ids"][-2]]
        base = {**still_job["recipe"], "seeds": [still_job["seed"]]}
        first = plate["still_asset_id"]
        clay_dir = OUT / "proj" / "finals" / fid / "plate" / "clay"
        clay_ids = [P.api("POST", "/assets/import", {"paths": [str(p)], "suite": "stage"})["items"][0]["id"] for p in sorted(clay_dir.glob("*.png"))]
        n = f["frames"]
        log_a: list = []
        log_b: list = []
        t0 = time.time()
        a = chain(base, clay_ids, list(range(n)), first, log_a)
        res["times"]["A"] = {"total_s": round(time.time() - t0), "per_still": [x["wall_s"] for x in log_a]}
        t0 = time.time()
        keys = list(range(0, n, KEY_EVERY)) + ([n - 1] if (n - 1) % KEY_EVERY else [])
        b = chain(base, clay_ids, keys, first, log_b)
        res["times"]["B"] = {"total_s": round(time.time() - t0), "per_still": [x["wall_s"] for x in log_b]}
        res["A"], res["B_keys"] = a, b
        pa = still_paths(a)
        (OUT / "A").mkdir()
        for k, p in pa.items():
            Image.open(p).convert("RGB").resize((f["size"]["w"], f["size"]["h"]), Image.LANCZOS).save(OUT / "A" / f"{k:04d}.png")
        st = P.api("GET", f"/stages/{f['stage_id']}")
        r = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e35_browser.cjs"), st["id"], fid, json.dumps(b)], cwd=str(ROOT / "frontend"),
                           capture_output=True, text=True, encoding="utf-8", env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=3600)
        (OUT / "browser.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-2000:])
        out = json.loads(r.stdout.strip().splitlines()[-1])
        blobs = OUT / "proj" / "_temp" / "blobs"
        for arm, shas in (("projected", out["plain"]), ("B", out["blend"])):
            (OUT / arm).mkdir()
            for i, sha in enumerate(shas):
                shutil.copyfile(blobs / sha, OUT / arm / f"{i:04d}.png")
    finally:
        app.close()
    (OUT / "run.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def measure() -> dict:
    res = json.loads((OUT / "run.json").read_text(encoding="utf-8"))
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    st = FinalStore(Workspace(OUT / "proj"))
    clay = sorted(st.pass_dir(res["final_id"], "plate", "clay").glob("*.png"))
    rows = {"the set (clay)": clay, "projected (PS5b)": sorted((OUT / "projected").glob("*.png")),
            "generated (CA3)": sorted(st.pass_dir(res["final_id"], "plate", "frames").glob("*.png")),
            "A · every frame": sorted((OUT / "A").glob("*.png")), "B · keyframes + projection": sorted((OUT / "B").glob("*.png"))}
    t_set = travel(clay)
    res["measured"] = {}
    for name, frames in rows.items():
        t = travel(frames)
        res["measured"][name] = {"travel": t, "end": t[-1], "apart": max(abs(x - c) for x, c in zip(t, t_set)), "flicker": round(flicker(frames), 2)}
    n = len(clay) - 1
    cols = [0, n // 4, n // 2, 3 * n // 4, n]
    tw, th = 320, 185
    sheet = Image.new("RGB", (170 + tw * len(cols), 22 + th * len(rows)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for ri, (name, frames) in enumerate(rows.items()):
        d.text((6, 22 + ri * th + th // 2), name, fill=(220, 220, 220))
        for c, k in enumerate(cols):
            sheet.paste(Image.open(frames[k]).convert("RGB").resize((tw, th)), (170 + c * tw, 22 + ri * th))
            if ri == 0:
                d.text((170 + c * tw + 6, 5), f"frame {k}", fill=(220, 220, 220))
    sheet.save(OUT / "e35_sheet.jpg", quality=86)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if "--measure" not in sys.argv:
        run()
    res = measure()
    for name, m in res["measured"].items():
        print(f"{name:28s} travel {m['end']:4d} px · at most {m['apart']:3d} apart · flicker {m['flicker']}")
    for arm, t in res["times"].items():
        per = [x for x in t["per_still"] if x]
        print(f"{arm}: {len(per)} stills, {t['total_s']} s, median {sorted(per)[len(per) // 2] if per else '-'} s a still")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
