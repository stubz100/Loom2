"""E35d (D133, proto01_animate 31 §4g): project and fill tuned for any large move — keyframes placed where the move needs them (a frame
whose share of *bad* pixels passes 3 %: seen by no keyframe, or seen more than twice as head-on as by the best keyframe while that one saw
it below 70°), each pixel of a frame from the keyframe that saw it most head-on, a keyframe's bad pixels filled by Klein's Fill. Two moves
with the same settings:

  orbit — E35's (CA3's F16 run: the camera orbiting 50° and closing in a quarter over 5 s), against E35c's every-16th;
  crane — the A1 room, the camera rising from 1.05 to 2.4 m and coming 1.3 m in while it tilts down onto the floor and pans a little
          left (the near floor and the left wall come into view), its own final and Klein still.

Measured as E35: the room's travel against the set's clay (px of 256, every 8 frames, sideways and up-down), the step frame to frame, the
keyframes and their Fills, the share of each frame still bad, the time. Sheets: the set · projected · project and fill · its keyframes.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e35d_run.py orbit     # Vite on 1420; the engine free (one GPU job at a time, D97)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e35d_run.py crane
    orchestrator/.venv/Scripts/python.exe engine/spikes/e35d_run.py crane --measure
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
from ca3_acceptance import PROMPT, _grad  # noqa: E402
from e34_plate import flicker  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUTS = ROOT / "engine" / "spikes" / "out"
NEUTRAL = "Continue the surrounding surfaces seamlessly: the same materials, the same light."   # E35d: a Fill continues, it does not re-describe the place
OPTS = {"unseen": "0.03", "prompt": "place"}                               # the first run's; --unseen 0.08 --prompt neutral (--tag to keep runs apart)
A1 = OUTS / "a1" / "project"
E35 = OUTS / "e35"


def shift2(a: np.ndarray, b: np.ndarray) -> tuple[int, int]:
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(F / (np.abs(F) + 1e-9)).real
    y, x = (int(v) for v in np.unravel_index(np.argmax(r), r.shape))
    return -(x if x < r.shape[1] // 2 else x - r.shape[1]), -(y if y < r.shape[0] // 2 else y - r.shape[0])


def travel2(frames: list[Path], step: int = 8) -> list[tuple[int, int]]:
    out, tx, ty = [], 0, 0
    for i in range(0, len(frames) - step, step):
        dx, dy = shift2(_grad(frames[i]), _grad(frames[i + step]))
        tx, ty = tx + dx, ty + dy
        out.append((tx, ty))
    return out


def setup_crane(out: Path) -> tuple[str, str, int]:
    """The crane move's project: A1's room as a bare stage, the move keyed, the final made and its Klein still landed."""
    shutil.copytree(A1, out / "proj", ignore=shutil.ignore_patterns("_temp"))
    P.OUT = out
    app = P.App(out / "proj")
    try:
        a1 = next(s for s in P.api("GET", "/stages")["items"] if any(o["id"] == "fig_m" for o in s["objects"]))
        a1 = P.api("GET", f"/stages/{a1['id']}")
        cam = a1["cameras"][0]
        end_pos, end_target = [-0.8, 2.4, 3.0], [-1.2, 0.2, -0.5]
        st = P.api("POST", "/stages", {"name": "E35d crane"})
        keys = {"camera": {cam["id"]: [{"frame": 0, "ease": "ease", "pos": cam["pos"], "target": cam["target"], "focal_mm": cam["focal_mm"]},
                                       {"frame": 120, "ease": "ease", "pos": end_pos, "target": end_target, "focal_mm": cam["focal_mm"]}]}, "objects": {}}
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "size": a1["size"], "objects": [o for o in a1["objects"] if o["kind"] in ("set", "light")],
                                                   "cameras": [cam], "active_camera": cam["id"], "keyframes": keys, "range": {"start": 0, "end": 120}, "ambient": a1.get("ambient")})
        r = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e35d_setup.cjs"), st["id"], PROMPT], cwd=str(ROOT / "frontend"), capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=1800)
        (out / "setup.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-2000:])
        fid = json.loads(r.stdout.strip().splitlines()[-1])["final_id"]
        t0 = time.time()
        while time.time() - t0 < 1800:
            plate = next(x for x in P.api("GET", f"/finals/{fid}")["layers"] if x["id"] == "plate")
            if plate["still_asset_id"] or plate["status"] == "failed":
                break
            time.sleep(3)
        if not plate["still_asset_id"]:
            raise RuntimeError(f"the still did not land: {plate.get('error')}")
    finally:
        app.close()
    jobs = {j["id"]: j for j in json.loads((out / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
    return fid, plate["still_asset_id"], jobs[plate["job_ids"][-1]]["seed"]


def run(move: str, out: Path) -> dict:
    from loom2.finals import PLATE_LEAD
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    if move == "orbit":
        shutil.copytree(E35 / "proj", out / "proj", ignore=shutil.ignore_patterns("_temp"))
        fid = json.loads((E35 / "run.json").read_text(encoding="utf-8"))["final_id"]
        jobs = {j["id"]: j for j in json.loads((out / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
        f = json.loads((out / "proj" / "finals" / fid / "final.json").read_text(encoding="utf-8"))
        plate = next(x for x in f["layers"] if x["id"] == "plate")
        still, seed = plate["still_asset_id"], jobs[plate["job_ids"][-2]]["seed"]
    elif (OUTS / "e35d_crane" / "run.json").is_file() and out.name != "e35d_crane":    # a rerun: the first crane run's final, still and seed
        base = OUTS / "e35d_crane"
        shutil.copytree(base / "proj", out / "proj", ignore=shutil.ignore_patterns("_temp"))
        shutil.copytree(base / "projected", out / "projected")
        fid = json.loads((base / "run.json").read_text(encoding="utf-8"))["final_id"]
        jobs = {j["id"]: j for j in json.loads((out / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
        f = json.loads((out / "proj" / "finals" / fid / "final.json").read_text(encoding="utf-8"))
        plate = next(x for x in f["layers"] if x["id"] == "plate")
        still, seed = plate["still_asset_id"], jobs[plate["job_ids"][0]]["seed"]
    else:
        fid, still, seed = setup_crane(out)
    P.OUT = out
    app = P.App(out / "proj")
    t0 = time.time()
    try:
        f = P.api("GET", f"/finals/{fid}")
        fill_prompt = f"{PLATE_LEAD} {PROMPT}" if OPTS["prompt"] == "place" else NEUTRAL
        r = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e35d_browser.cjs"), f["stage_id"], fid, still, str(seed), fill_prompt, str(out), OPTS["unseen"]],
                           cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=7200)
        (out / "browser.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-3000:])
        res = json.loads(r.stdout.strip().splitlines()[-1])
        res["final_id"], res["wall_s"], res["move"], res["opts"] = fid, round(time.time() - t0), move, dict(OPTS)
        blobs = out / "proj" / "_temp" / "blobs"
        (out / "frames").mkdir()
        for i, sha in enumerate(res["frames"]):
            shutil.copyfile(blobs / sha, out / "frames" / f"{i:04d}.png")
        (out / "keys_filled").mkdir()
        for k, aid in res["keys"].items():
            shutil.copyfile(out / "proj" / P.api("GET", f"/assets/{aid}")["path"], out / "keys_filled" / f"{int(k):04d}.png")
        # the first still projected alone, for the comparison row (the orbit has E35's)
        if move != "orbit" and not (out / "projected").is_dir():
            r2 = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e35_browser.cjs"), f["stage_id"], fid, json.dumps({"0": still})],
                                cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8",
                                env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=1800)
            if r2.returncode != 0:
                raise RuntimeError(r2.stderr[-2000:])
            (out / "projected").mkdir()
            for i, sha in enumerate(json.loads(r2.stdout.strip().splitlines()[-1])["plain"]):
                shutil.copyfile(blobs / sha, out / "projected" / f"{i:04d}.png")
    finally:
        app.close()
    (out / "run.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def measure(move: str, out: Path) -> dict:
    res = json.loads((out / "run.json").read_text(encoding="utf-8"))
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    st = FinalStore(Workspace(out / "proj"))
    clay = sorted(st.pass_dir(res["final_id"], "plate", "clay").glob("*.png"))
    rows = {"the set (clay)": clay, "projected (PS5b)": sorted(((E35 if move == "orbit" else out) / "projected").glob("*.png"))}
    if move == "orbit":
        rows["E35c every 16th"] = sorted((OUTS / "e35c_v2" / "frames").glob("*.png"))
    rows["E35d project and fill"] = sorted((out / "frames").glob("*.png"))
    t_set = travel2(clay)
    res["measured"] = {}
    for name, frames in rows.items():
        t = travel2(frames)
        res["measured"][name] = {"travel": t, "end": t[-1], "apart": max(max(abs(a[0] - c[0]), abs(a[1] - c[1])) for a, c in zip(t, t_set)),
                                 "flicker": round(flicker(frames), 2)}
    n = len(clay) - 1
    cols = [0, n // 4, n // 2, 3 * n // 4, n]
    tw, th = 320, 185
    keys = sorted((out / "keys_filled").glob("*.png"))
    allrows = [*rows.items(), ("E35d keyframes, filled", None)]
    sheet = Image.new("RGB", (170 + tw * len(cols), 22 + th * len(allrows)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for ri, (name, frames) in enumerate(allrows):
        d.text((6, 22 + ri * th + th // 2), name, fill=(220, 220, 220))
        for c, k in enumerate(cols):
            src = frames[k] if frames is not None else min(keys, key=lambda p: abs(int(p.stem) - k))
            sheet.paste(Image.open(src).convert("RGB").resize((tw, th)), (170 + c * tw, 22 + ri * th))
            d.text((170 + c * tw + 6, 22 + ri * th + 4) if frames is None else (170 + c * tw + 6, 5), f"key {int(src.stem)}" if frames is None else (f"frame {k}" if ri == 0 else ""), fill=(220, 220, 220))
    sheet.save(out / "e35d_sheet.jpg", quality=86)
    (out / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    move = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "orbit"
    for k in OPTS:
        if f"--{k}" in sys.argv:
            OPTS[k] = sys.argv[sys.argv.index(f"--{k}") + 1]
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    out = OUTS / f"e35d_{move}{'_' + tag if tag else ''}"
    if "--measure" not in sys.argv:
        run(move, out)
    res = measure(move, out)
    for name, m in res["measured"].items():
        print(f"{name:24s} travel {tuple(m['end'])} px · at most {m['apart']:3d} apart · step {m['flicker']}")
    fills = [x for x in res["fills"] if x.get("fill")]
    print(f"keyframes {sorted(int(k) for k in res['keys'])}: {len(fills)} Fills ({', '.join(f'{x['filled'] * 100:.0f} %' for x in fills)}), "
          f"each ≈ {np.median([x['fill_s'] for x in fills]):.0f} s; frames still bad: median {np.median(res['frame_bad']) * 100:.1f} %, max {max(res['frame_bad']) * 100:.1f} %; {res['wall_s']} s in all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
