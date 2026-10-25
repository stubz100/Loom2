"""Spike E39 (proto01_UIcast 06 §2.9; D136 U18, D137 stage 3): do Stage's starter poses and motion clips fit characters whose skeletons are
not the default adult's — a child, a heavy build, a long dress, a coat, and A1's Mara and Ines? It decides whether contacts and IK (the
pose editor, AP1) are enough, or whether clips need a retargeting model (its licence read against D17 first).

  measure  the browser half (frontend/src/spikes/e39Poses.ts, visible Edge, Vite on 1420) on E36's project: each character's shell bound as
           the shots bind it (bone heat, in its stance, placed by its picture); every starter pose and the chosen starter clips (retargeted,
           the root scaled to the character's hip, the foot lock with its body, as Animate applies them): the planted foot's slide, how far it
           floats or sinks at each stance (its lowest point against its standing height), a fingertip through the body (inside the
           posed shell, nearest the torso or a leg); the default adult as the baseline
  score    the table and the sheets (.docs/proto01_UIcast/img/e39-*.jpg), results.json

    orchestrator/.venv/Scripts/python.exe engine/spikes/e39_poses.py measure|score
Outputs under engine/spikes/out/e39/ (git-ignored). Mara's and Ines' E36 shells come from arms-down pictures (fused arms, D139): their
feet are measured, their hands are not.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

E36 = ROOT / "engine" / "spikes" / "out" / "e36"
OUT = ROOT / "engine" / "spikes" / "out" / "e39"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"
WITH_SHELL = ["Pip", "Bruno", "Dancer", "Fisherman"]
FEET_ONLY = ["Mara", "Ines"]
DEFAULT = {"height_m": 1.75}                                                # the default adult: the clips' baseline (no shell)
CLIPS = ["Walk_Loop", "Jog_Fwd_Loop", "Idle_Loop", "Sitting_Enter", "Sitting_Idle_Loop", "Walk_Carry_Loop", "Farm_Harvest", "Pistol_Aim_Neutral",
         "Crouch_Idle_Loop", "Interact"]


def measure() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "browser").mkdir(exist_ok=True)
    s = json.loads((E36 / "state.json").read_text(encoding="utf-8"))
    P.OUT = OUT
    app = P.App(E36 / "proj")
    try:
        inputs = [{"name": "Default", "body": DEFAULT, "points": None, "mesh": None, "clips": CLIPS}]
        for name in WITH_SHELL + FEET_ONLY:
            c = s["characters"][name]
            v = P.api("GET", f"/story/profiles/{c['pid']}")["versions"][0]
            inputs.append({"name": name, "body": v["body"], "points": v["body_points"], "mesh": c["mesh"] if name in WITH_SHELL else None, "clips": CLIPS})
        r = subprocess.run(["node", str(Path(__file__).with_name("e39_browser.cjs")), json.dumps(inputs), str(OUT / "browser")], cwd=str(ROOT / "frontend"),
                           capture_output=True, text=True, encoding="utf-8", timeout=7200, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
        print(r.stdout[-2000:], r.stderr[-3000:])
        if r.returncode != 0:
            raise RuntimeError("the browser half failed")
    finally:
        app.close()


def score() -> None:
    rows = json.loads((OUT / "browser" / "results.json").read_text(encoding="utf-8"))
    for row in rows:
        name = row["name"]
        clips = {k: v for k, v in row["clips"].items() if not v.get("missing")}
        poses = row["poses"]
        bad_poses = {k: v["hands_in_body"] for k, v in poses.items() if v["hands_in_body"]}
        print(f"{name} (hip {row['hip_m']} m): poses — feet {min(v['foot_cm'] for v in poses.values()):.1f}…{max(v['foot_cm'] for v in poses.values()):.1f} cm, "
              f"hands in the body {bad_poses or 'none'}")
        for k, v in clips.items():
            fix = v.get("after_contact") or {}
            print(f"   {k}: slide {v['slide_cm']} cm, float {v['float_cm']} / sink {v['sink_cm']} cm, hands in the body {v['hands_in_body']}"
                  f" · with the vertical contact: stance {fix.get('stance_cm')} cm, a foot under the floor {fix.get('under_cm')} cm, with leg IK {fix.get('under_ik_cm')} cm"
                  f" · AP1's module: stance {(v.get('after_module') or {}).get('stance_cm')} cm, under {(v.get('after_module') or {}).get('under_cm')} cm")
        views = sorted(p for p in (OUT / "browser").glob(f"{name}_*.png"))
        if views:
            tiles = [Image.open(p).convert("RGB") for p in views]
            w, h = tiles[0].size
            cols = min(6, len(tiles))
            out = Image.new("RGB", (cols * (w + 6) + 6, ((len(tiles) + cols - 1) // cols) * (h + 22) + 6), (24, 24, 24))
            d = ImageDraw.Draw(out)
            for i, (t, p) in enumerate(zip(tiles, views)):
                x, y = 6 + (i % cols) * (w + 6), 6 + (i // cols) * (h + 22)
                out.paste(t, (x, y + 16))
                d.text((x + 2, y + 2), p.stem[len(name) + 1:], fill=(225, 225, 225))
            out.save(IMG / f"e39-{name.lower()}.jpg", quality=84)
    names = sorted({k for r in rows for k, v in r["clips"].items() if not v.get("missing")})
    print("clips measured:", names, "· missing:", sorted({k for r in rows for k, v in r["clips"].items() if v.get("missing")}))
    (OUT / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["measure", "score"])
    a = ap.parse_args()
    {"measure": measure, "score": score}[a.step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
