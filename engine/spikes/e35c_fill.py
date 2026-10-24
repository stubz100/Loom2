"""E35c (D132, proto01_animate 31 §4f): the plate for a large camera move as *project and fill* — a keyframe every 8th frame made of the
keyframes before it projected into its own camera (the most recent first, a pixel from the first that saw it: Stage's projector's
coverage mode), only what none of them saw filled by Klein's Fill on an Edit document; the frames between keyframes the nearest
keyframes projected the same way. On a copy of E35's project (CA3's F16 run: the same set, path, first still, prompt and seed).

Measured as E35: the room's travel against the set's clay (px of 256, every 8 frames), the step frame to frame, the share of each keyframe
filled, the time; beside the first still projected alone (E35's), CA3's generated plate. Sheet: the set · projected · generated · E35c,
and the keyframes as filled.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e35c_fill.py            # Vite on 1420; the engine free (one GPU job at a time, D97)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e35c_fill.py --measure  # the measurements again (no GPU)
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

from PIL import Image, ImageDraw  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "e35"
OUT = ROOT / "engine" / "spikes" / "out" / "e35c"
ARGS = {"every": "8", "expand": "6", "feather": "8", "graze": "0.17"}     # the first run's; --every 16 --expand 48 … for a variant (--out to keep it apart)


def run() -> dict:
    from loom2.finals import PLATE_LEAD
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC / "proj", OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    e35 = json.loads((SRC / "run.json").read_text(encoding="utf-8"))
    fid = e35["final_id"]
    P.OUT = OUT
    app = P.App(OUT / "proj")
    t0 = time.time()
    try:
        f = P.api("GET", f"/finals/{fid}")
        plate = next(x for x in f["layers"] if x["id"] == "plate")
        jobs = {j["id"]: j for j in json.loads((OUT / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
        seed = jobs[plate["job_ids"][-2]]["seed"]
        r = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e35c_browser.cjs"), f["stage_id"], fid, plate["still_asset_id"], str(seed),
                            f"{PLATE_LEAD} {PROMPT}", str(OUT), ARGS["every"], ARGS["expand"], ARGS["feather"], ARGS["graze"]], cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=7200)
        (OUT / "browser.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-3000:])
        res = json.loads(r.stdout.strip().splitlines()[-1])
        res["final_id"], res["wall_s"], res["args"] = fid, round(time.time() - t0), dict(ARGS)
        blobs = OUT / "proj" / "_temp" / "blobs"
        (OUT / "frames").mkdir()
        for i, sha in enumerate(res["frames"]):
            shutil.copyfile(blobs / sha, OUT / "frames" / f"{i:04d}.png")
        (OUT / "keys_filled").mkdir()
        for k, aid in res["keys"].items():
            shutil.copyfile(OUT / "proj" / P.api("GET", f"/assets/{aid}")["path"], OUT / "keys_filled" / f"{int(k):04d}.png")
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
    rows = {"the set (clay)": clay, "projected (PS5b)": sorted((SRC / "projected").glob("*.png")),
            "generated (CA3)": sorted(st.pass_dir(res["final_id"], "plate", "frames").glob("*.png")), "E35c · project and fill": sorted((OUT / "frames").glob("*.png"))}
    t_set = travel(clay)
    res["measured"] = {}
    for name, frames in rows.items():
        t = travel(frames)
        res["measured"][name] = {"travel": t, "end": t[-1], "apart": max(abs(x - c) for x, c in zip(t, t_set)), "flicker": round(flicker(frames), 2)}
    n = len(clay) - 1
    cols = [0, n // 4, n // 2, 3 * n // 4, n]
    tw, th = 320, 185
    sheet = Image.new("RGB", (170 + tw * len(cols), 22 + th * (len(rows) + 1)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    keys = sorted((OUT / "keys_filled").glob("*.png"))
    for ri, (name, frames) in enumerate([*rows.items(), ("E35c keyframes, filled", None)]):
        d.text((6, 22 + ri * th + th // 2), name, fill=(220, 220, 220))
        for c, k in enumerate(cols):
            src = frames[k] if frames is not None else min(keys, key=lambda p: abs(int(p.stem) - k))
            sheet.paste(Image.open(src).convert("RGB").resize((tw, th)), (170 + c * tw, 22 + ri * th))
            if ri == 0:
                d.text((170 + c * tw + 6, 5), f"frame {k}", fill=(220, 220, 220))
    sheet.save(OUT / "e35c_sheet.jpg", quality=86)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def main() -> int:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8")
    for k in ARGS:
        if f"--{k}" in sys.argv:
            ARGS[k] = sys.argv[sys.argv.index(f"--{k}") + 1]
    if "--out" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
    if "--measure" not in sys.argv:
        run()
    res = measure()
    for name, m in res["measured"].items():
        print(f"{name:26s} travel {m['end']:4d} px · at most {m['apart']:3d} apart · step {m['flicker']}")
    fills = res["fills"]
    print("keyframes filled: " + ", ".join(f"{x['k']}: {x['holes'] * 100:.1f} % ({x.get('fill_s') or 0:.0f} s)" for x in fills))
    print(f"frames left unseen (median {sorted(res['frame_holes'])[len(res['frame_holes']) // 2] * 100:.2f} %, max {max(res['frame_holes']) * 100:.2f} %), {res['wall_s']} s in all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
