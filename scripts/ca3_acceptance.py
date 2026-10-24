"""CA3 (D130, proto01_animate 31 §4c): the plate generated along the path, accepted on the rig — E34's move (the A1 room as a bare stage,
the camera orbiting 50° about its target and closing in a quarter over 5 s) made into a final at F16 by Stage in a visible Edge: the plate's
method is chosen by the camera's travel, *Make the plate* queues its Klein still, and the server generates the plate from it along the
path (LTX-2.3 on the plate's depth pass) into the layer's frames.

Checks (read from the project on disk): the method chosen is `generated`; the clip ran on the depth guide at the final's rate and LTX's
grid from the still; the plate has the final's frames at its size; its first frame is the still; it follows the camera path — the room
in it moves sideways with the set's clay pass (the cumulative shift by phase correlation, every 8 frames, within 10 % of the width at
every step: E34's plate at 24 fps 117 against the clay's 121 px of 256). Sharpness is recorded, not checked: a sharp still's floor planks
fill its first frame (CA3's first run: 328 → 168 with nothing smeared), while E34's streaked projection kept 26.5 → 24.0. A contact sheet
(frames 0, ¼, ½, ¾, the last) is the author's look.

    orchestrator/.venv/Scripts/python.exe scripts/ca3_acceptance.py           # Vite on 1420; the engine free (one GPU job at a time, D97)
    orchestrator/.venv/Scripts/python.exe scripts/ca3_acceptance.py --reuse   # the checks again on the last run's project (no GPU)
    orchestrator/.venv/Scripts/python.exe scripts/ca3_acceptance.py --rate 24 # the final at F24 (--out <folder> to keep another run)
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
from e34_plate import flicker, orbit, sharp  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ca3"
PROMPT = "an empty room with white plaster walls and a worn wooden floor, daylight from the tall window"


def run(rate: int, prompt: str) -> dict:
    """The final made and its plate generated on the rig; returns what the browser saw (the travel and the method chosen)."""
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    P.OUT = OUT
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    app = P.App(OUT / "proj")
    t0 = time.time()
    try:
        a1 = next(s for s in P.api("GET", "/stages")["items"] if any(o["id"] == "fig_m" for o in s["objects"]))
        a1 = P.api("GET", f"/stages/{a1['id']}")
        cam = a1["cameras"][0]
        far = orbit(cam["pos"], cam["target"], 50.0, 0.75)
        st = P.api("POST", "/stages", {"name": "CA3 orbit"})
        keys = {"camera": {cam["id"]: [{"frame": 0, "ease": "ease", "pos": cam["pos"], "target": cam["target"], "focal_mm": cam["focal_mm"]},
                                       {"frame": 120, "ease": "ease", "pos": far, "target": cam["target"], "focal_mm": cam["focal_mm"]}]}, "objects": {}}
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "size": a1["size"], "objects": [o for o in a1["objects"] if o["kind"] in ("set", "light")],
                                                   "cameras": [cam], "active_camera": cam["id"], "keyframes": keys, "range": {"start": 0, "end": 120}, "ambient": a1.get("ambient")})
        r = subprocess.run(["node", str(ROOT / "scripts" / "ca3_browser.cjs"), st["id"], prompt, str(rate)], cwd=str(ROOT / "frontend"), capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=1800)
        (OUT / "browser.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-2000:])
        b = json.loads(r.stdout.strip().splitlines()[-1])
        while time.time() - t0 < 3600:
            plate = next(x for x in P.api("GET", f"/finals/{b['final_id']}")["layers"] if x["id"] == "plate")
            if plate["status"] in ("done", "failed"):
                break
            time.sleep(3)
        b["wall_s"] = round(time.time() - t0)
    finally:
        app.close()
    b["prompt"] = prompt
    (OUT / "browser.json").write_text(json.dumps(b, indent=1), encoding="utf-8")
    return b


def _grad(p: Path) -> np.ndarray:
    from PIL import ImageFilter
    a = np.asarray(Image.open(p).convert("L").resize((256, 144)).filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float64)
    g = np.hypot(np.diff(a, axis=1)[:-1, :], np.diff(a, axis=0)[:, :-1])
    g -= g.mean()
    return g * np.hanning(g.shape[0])[:, None] * np.hanning(g.shape[1])[None, :]


def _shift(a: np.ndarray, b: np.ndarray) -> int:
    """How far b's content moved sideways against a's (px at 256 wide): phase correlation of their gradients."""
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(F / (np.abs(F) + 1e-9)).real
    x = int(np.unravel_index(np.argmax(r), r.shape)[1])
    return -(x if x < r.shape[1] // 2 else x - r.shape[1])


def travel(frames: list[Path], step: int = 8) -> list[int]:
    """The cumulative sideways shift every `step` frames."""
    out, total = [], 0
    for i in range(0, len(frames) - step, step):
        total += _shift(_grad(frames[i]), _grad(frames[i + step]))
        out.append(total)
    return out


def measure(b: dict) -> dict:
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    ws = Workspace(OUT / "proj")
    store = FinalStore(ws)
    f = store.get(b["final_id"])
    plate = next(x for x in f.layers if x.id == "plate")
    res: dict = {"final_id": f.id, "travel": b["travel"], "why": b["why"], "wall_s": b.get("wall_s"), "checks": []}
    checks = res["checks"]
    checks.append(("the camera's travel advises the plate generated along the path", b.get("advice", b["method"]) == "generated" and plate.method == "generated",
                   f"{b['why'].split(' — ')[0]} → {plate.method}"))
    if plate.status != "done":
        checks.append(("the plate is made", False, f"{plate.status}: {plate.error}"))
        return res
    jobs = {j["id"]: j for j in json.loads((ws.path / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
    still_job, clip_job = jobs[plate.job_ids[-2]], jobs[plate.job_ids[-1]]
    rc = clip_job["recipe"]
    res["still_seconds"], res["clip_seconds"] = still_job.get("wall_s"), clip_job.get("wall_s")
    res["clip"] = {"frames": rc["frames"], "fps": rc["fps"], "w": rc["width"], "h": rc["height"], "guide": rc.get("guide"), "prompt": rc["prompt_text"]}
    checks.append(("the clip ran on the plate's depth at the final's rate and LTX's grid, from the still",
                   rc["kind"] == "i2v" and (rc.get("guide") or {}).get("kind") == "depth" and rc["fps"] == f.rate and rc["frames"] % 8 == 1 and rc["frames"] >= f.frames
                   and rc["start_asset"] == plate.still_asset_id and rc["width"] % 64 == 0 and rc["height"] % 64 == 0,
                   f"{rc['frames']} frames at {rc['fps']} fps, {rc['width']}×{rc['height']}, {clip_job.get('wall_s')} s"))
    frames = sorted(store.pass_dir(f.id, "plate", "frames").glob("*.png"))
    size = Image.open(frames[0]).size
    checks.append(("the plate has the final's frames at its size", len(frames) == f.frames and size == (f.size["w"], f.size["h"]),
                   f"{len(frames)} frames at {size[0]}×{size[1]}"))
    cat = Catalogue(ws)
    still = cat.abs_path(cat.get(plate.still_asset_id))
    g0 = np.asarray(Image.open(frames[0]).convert("RGB").resize((512, 288)), dtype=np.float64)
    s0 = np.asarray(Image.open(still).convert("RGB").resize((512, 288)), dtype=np.float64)
    d0 = float(np.abs(g0 - s0).mean())
    res["frame0_vs_still"] = round(d0, 2)
    checks.append(("its first frame is the still (≤ 6 levels)", d0 <= 6, f"{d0:.2f} levels"))
    res["sharpness"] = {"start": round(sharp(frames[0]), 1), "end": round(sharp(frames[-1]), 1)}
    res["flicker"] = round(flicker(frames), 2)
    clay = sorted(store.pass_dir(f.id, "plate", "clay").glob("*.png"))
    t_gen, t_set = travel(frames), travel(clay)
    res["travel_px"] = {"clay": t_set, "generated": t_gen}
    lead = max(abs(a - c) for a, c in zip(t_gen, t_set))
    checks.append(("it follows the camera path (within 10 % of the width of the set's clay at every step)", lead <= 25.6,
                   f"{t_gen[-1]} px against the set's {t_set[-1]} of 256, at most {lead} apart"))
    n = len(frames) - 1
    cols = [0, n // 4, n // 2, 3 * n // 4, n]
    tw, th = 384, 216
    sheet = Image.new("RGB", (tw * len(cols), th + 24), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for c, k in enumerate(cols):
        sheet.paste(Image.open(frames[min(k, len(frames) - 1)]).convert("RGB").resize((tw, th)), (c * tw, 24))
        d.text((c * tw + 6, 6), f"frame {k}", fill=(220, 220, 220))
    sheet.save(OUT / "ca3_sheet.jpg", quality=88)
    return res


def main() -> int:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8")
    if "--out" in sys.argv:                                                  # another run's folder (with --reuse)
        OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
    rate = int(sys.argv[sys.argv.index("--rate") + 1]) if "--rate" in sys.argv else 16
    prompt = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else PROMPT
    b = json.loads((OUT / "browser.json").read_text(encoding="utf-8")) if "--reuse" in sys.argv else run(rate, prompt)
    res = measure(b)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, ok, detail in res["checks"]:
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    print(f"ca3_acceptance: {sum(1 for c in res['checks'] if c[1])}/{len(res['checks'])}")
    return 0 if all(c[1] for c in res["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
