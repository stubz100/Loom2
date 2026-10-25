"""PF1 (D135, proto01_animate 31 §4h): the plate projected and filled, accepted on the rig — the product's route on E35d's two moves (copies
of their projects: the same set, path and still): the plate's method set to *filled* through its route, Stage's fill steps run in a visible
Edge as the Final shot card's poll runs them, the keyframes' Fills on the real engine (Klein, one GPU job at a time). The orbit with the
in-between heal off, the crane with it on.

Checks per move: the plate is done with the final's frames at its size; every keyframe landed and the last frame is one; it stays on the set
(the room's travel against the set's clay within 3 px of the projection's own gap); the shot under 10 minutes. Recorded: the keyframes and
their Fills (share, seconds), the heal's keyframes, the step frame to frame. Sheets: the set · projected · PF1 at 0, ¼, ½, ¾, the end.

    orchestrator/.venv/Scripts/python.exe scripts/pf1_acceptance.py      # Vite on 1420; the engine free (D97)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
from ca3_acceptance import PROMPT  # noqa: E402
from e34_plate import flicker  # noqa: E402
from e35d_run import travel2  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

OUTS = ROOT / "engine" / "spikes" / "out"
MOVES = {"orbit": (OUTS / "e35", OUTS / "e35" / "projected", False, 4), "crane": (OUTS / "e35d_crane", OUTS / "e35d_crane" / "projected", True, 13)}


def run(move: str) -> dict:
    src, projected, heal, proj_apart = MOVES[move]
    out = OUTS / f"pf1_{move}"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    shutil.copytree(src / "proj", out / "proj", ignore=shutil.ignore_patterns("_temp"))
    fid = json.loads((src / "run.json").read_text(encoding="utf-8"))["final_id"]
    P.OUT = out
    app = P.App(out / "proj")
    res: dict = {"move": move, "heal": heal, "final_id": fid, "checks": []}
    try:
        f = P.api("PUT", f"/finals/{fid}/layers/plate/method", {"method": "filled", "prompt_text": PROMPT})      # the place as its still was asked for
        P.api("PUT", f"/finals/{fid}/layers/plate/heal", {"heal": heal})
        t0 = time.time()
        r = subprocess.run(["node", str(ROOT / "scripts" / "pf1_browser.cjs"), f["stage_id"], fid], cwd=str(ROOT / "frontend"), capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=4000)
        (out / "browser.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-2000:])
        res["browser"] = json.loads(r.stdout.strip().splitlines()[-1])
        res["wall_s"] = round(time.time() - t0)
        f = P.api("GET", f"/finals/{fid}")
    finally:
        app.close()
    plate = next(x for x in f["layers"] if x["id"] == "plate")
    jobs = {j["id"]: j for j in json.loads((out / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
    keys = plate["keys"]
    res["keys"] = [{"frame": k["frame"], "filled": k["filled"], "heal": k["heal"], "fill_s": jobs[k["job_id"]].get("wall_s") if k.get("job_id") else None} for k in keys]
    res["place_prompt"] = plate.get("prompt")
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    st = FinalStore(Workspace(out / "proj"))
    frames = sorted(st.pass_dir(fid, "plate", "frames").glob("*.png"))
    clay = sorted(st.pass_dir(fid, "plate", "clay").glob("*.png"))
    size = Image.open(frames[0]).size if frames else (0, 0)
    res["checks"].append(("the plate is done with the final's frames at its size", plate["status"] == "done" and len(frames) == f["frames"] and size == (f["size"]["w"], f["size"]["h"]),
                          f"{plate['status']}, {len(frames)} frames at {size[0]}×{size[1]}"))
    res["checks"].append(("every keyframe landed and the last frame is one", all(k["asset_id"] for k in keys) and keys and keys[-1]["frame"] == f["frames"] - 1,
                          f"{len(keys)} keyframes at {[k['frame'] for k in keys]}, {sum(1 for k in keys if k.get('job_id'))} filled, {sum(1 for k in keys if k['heal'])} healing"))
    t_set, t_pf = travel2(clay), travel2(frames)
    apart = max(max(abs(a[0] - c[0]), abs(a[1] - c[1])) for a, c in zip(t_pf, t_set))
    res["travel"] = {"set": t_set[-1], "pf1": t_pf[-1], "apart": apart, "projection_apart": proj_apart}
    res["flicker"] = round(flicker(frames), 2)
    res["checks"].append(("it stays on the set (within 3 px of the projection's own gap)", apart <= proj_apart + 3, f"travel {t_pf[-1]} against the set's {t_set[-1]}, at most {apart} apart (the projection {proj_apart})"))
    res["checks"].append(("the shot under 10 minutes", res["wall_s"] <= 600, f"{res['wall_s']} s, {len([k for k in keys if k.get('job_id')])} Fills"))
    n = len(frames) - 1
    cols = [0, n // 4, n // 2, 3 * n // 4, n]
    tw, th = 320, 185
    rows = [("the set (clay)", clay), ("projected (PS5b)", sorted(projected.glob("*.png"))), (f"PF1{' · heal' if heal else ''}", frames)]
    sheet = Image.new("RGB", (150 + tw * len(cols), 22 + th * len(rows)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for ri, (name, fr) in enumerate(rows):
        d.text((6, 22 + ri * th + th // 2), name, fill=(220, 220, 220))
        for c, k in enumerate(cols):
            sheet.paste(Image.open(fr[k]).convert("RGB").resize((tw, th)), (150 + c * tw, 22 + ri * th))
            if ri == 0:
                d.text((150 + c * tw + 6, 5), f"frame {k}", fill=(220, 220, 220))
    sheet.save(out / "pf1_sheet.jpg", quality=86)
    (out / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ok = True
    for move in (sys.argv[1:] or list(MOVES)):
        res = run(move)
        for name, good, detail in res["checks"]:
            print(f"{'PASS' if good else 'FAIL'} [{move}] {name}: {detail}")
            ok = ok and good
        print(f"[{move}] keyframes {res['keys']} · step {res['flicker']}")
    print(f"pf1_acceptance: {'all passed' if ok else 'failures above'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
