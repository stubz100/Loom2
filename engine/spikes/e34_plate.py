"""E34 (proto01_animate 31 §4, CA3): the plate for a large camera move — the projection of a Klein still along the camera path (PS5b, today's
plate) against a depth-guided LTX-2.3 clip that starts from the same still (the IC-LoRA union control on the bare set's depth along the
path, Stage's guided method). The A1 rig's room on a copy of its project, the camera orbiting 50° about its target and closing in a quarter
over 5 s (121 frames at 24 fps).

Measured: the clip's first frame against the still (the plate must start where the still is); each method's sharpness at the end of the
move against its start (variance of the Laplacian — a projection stretches, a generation draws); the step from frame to frame (flicker);
the clip's time and the engine's peak memory. A contact sheet (both rows at 0, 30, 60, 90, 120) is the author's look.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e34_plate.py     # Vite on 1420; the engine free (one GPU job at a time, D97)
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "e34"
PROMPT = "an empty room with white plaster walls and a worn wooden floor, daylight from the tall window, the camera moving slowly through the room"


def orbit(pos: list[float], target: list[float], deg: float, closer: float) -> list[float]:
    x, y, z = (pos[i] - target[i] for i in range(3))
    a = math.radians(deg)
    rx, rz = x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)
    return [round(target[0] + rx * closer, 4), round(target[1] + y * closer, 4), round(target[2] + rz * closer, 4)]


def sharp(p: Path) -> float:
    g = np.asarray(Image.open(p).convert("L").resize((512, 288)), dtype=np.float64)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def flicker(frames: list[Path]) -> float:
    a = [np.asarray(Image.open(p).convert("RGB").resize((256, 144)), dtype=np.float64) for p in frames]
    return float(np.median([np.abs(a[i + 1] - a[i]).mean() for i in range(len(a) - 1)]))


def main() -> int:
    res: dict = {}
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    P.OUT = OUT
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    app = P.App(OUT / "proj")
    try:
        a1 = next(s for s in P.api("GET", "/stages")["items"] if any(o["id"] == "fig_m" for o in s["objects"]))
        a1 = P.api("GET", f"/stages/{a1['id']}")
        cam = a1["cameras"][0]
        far = orbit(cam["pos"], cam["target"], 50.0, 0.75)
        st = P.api("POST", "/stages", {"name": "E34 orbit"})
        keys = {"camera": {cam["id"]: [{"frame": 0, "ease": "ease", "pos": cam["pos"], "target": cam["target"], "focal_mm": cam["focal_mm"]},
                                       {"frame": 120, "ease": "ease", "pos": far, "target": cam["target"], "focal_mm": cam["focal_mm"]}]}, "objects": {}}
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "size": a1["size"], "objects": [o for o in a1["objects"] if o["kind"] in ("set", "light")],
                                                   "cameras": [cam], "active_camera": cam["id"], "keyframes": keys, "range": {"start": 0, "end": 120}, "ambient": a1.get("ambient")})
        res["camera"] = {"from": cam["pos"], "to": far, "target": cam["target"], "orbit_deg": 50, "closer": 0.75}
        r = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e34_browser.cjs"), st["id"], PROMPT], cwd=str(ROOT / "frontend"), capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")}, timeout=3600)
        (OUT / "browser.log").write_text(r.stderr, encoding="utf-8")
        if r.returncode != 0:
            print(r.stderr[-2000:])
            return 1
        b = json.loads(r.stdout.strip().splitlines()[-1])
        j = P.wait_job(b["clip_job"], timeout=3600)
        if j["status"] != "done":
            print("the clip failed:", j.get("error"))
            return 1
        from loom2.clips import ClipStore
        from loom2.finals import FinalStore
        from loom2.workspace import Workspace
        ws = Workspace(OUT / "proj")
        clip = ClipStore(ws).get(j["result"]["clip_id"])
        gen = [ClipStore(ws).frame_path(clip.id, i) for i in range(clip.frames)]
        proj = sorted(FinalStore(ws).pass_dir(b["final_id"], "plate", "frames").glob("*.png"))
        still = ws.path / P.api("GET", f"/assets/{b['still']}")["path"]
        g0 = np.asarray(Image.open(gen[0]).convert("RGB").resize((512, 288)), dtype=np.float64)
        s0 = np.asarray(Image.open(still).convert("RGB").resize((512, 288)), dtype=np.float64)
        res["frame0_vs_still"] = round(float(np.abs(g0 - s0).mean()), 2)
        res["sharpness"] = {"projection": {"start": round(sharp(proj[0]), 1), "end": round(sharp(proj[-1]), 1)},
                            "generated": {"start": round(sharp(gen[0]), 1), "end": round(sharp(gen[-1]), 1)}}
        res["flicker"] = {"projection": round(flicker(proj), 2), "generated": round(flicker(gen), 2)}
        res["clip"] = {"frames": clip.frames, "fps": clip.fps, "w": clip.w, "h": clip.h, "seconds": j.get("wall_s"),
                       "log": [ln for ln in j.get("log_tail", []) if "VRAM" in ln or "peak" in ln.lower() or "s/it" in ln][-6:]}
        res["projection_frames"] = len(proj)
        # the contact sheet: the projection over the generated plate at 0, 30, 60, 90, 120
        cols = [0, 30, 60, 90, 120]
        tw, th = 384, 216
        sheet = Image.new("RGB", (tw * len(cols) + 110, th * 2 + 30), (24, 24, 24))
        d = ImageDraw.Draw(sheet)
        for r_, (label, frames) in enumerate((("projected", proj), ("generated", gen))):
            d.text((8, 30 + r_ * th + th // 2), label, fill=(220, 220, 220))
            for c, k in enumerate(cols):
                im = Image.open(frames[min(k, len(frames) - 1)]).convert("RGB").resize((tw, th))
                sheet.paste(im, (110 + c * tw, 30 + r_ * th))
                if r_ == 0:
                    d.text((110 + c * tw + 6, 8), f"frame {k}", fill=(220, 220, 220))
        sheet.save(OUT / "e34_sheet.jpg", quality=88)
        res["clip_proxy"] = str(Path(clip.proxy_path)) if getattr(clip, "proxy_path", None) else None
        res["final_id"], res["still"], res["clip_id"] = b["final_id"], b["still"], clip.id
    finally:
        app.close()
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
