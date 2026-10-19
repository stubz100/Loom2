"""Spike E25, scoring checked: the first pass's hand PCK (a hit within 0.2 × the guide hand's own box, 4–5 px for a 20 px hand at this
framing) was near zero in both arms while the hands were found in 89–95 % of the frames — too strict for hands this small, or a side /
order mismatch. This re-scores the same clips (the spike's temp project) with SDPose: the hand points against the guide's at 0.1 × the
guide figure's torso (neck to mid-hip, PCKh-style — about 10 px here) for both side assignments (the image's left / right against the
character's), the mean error in torso lengths, and an overlay of one frame per run (guide hand points green, detected red).

    orchestrator/.venv/Scripts/python.exe engine/spikes/e25_rescore.py <the spike's temp project dir>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "engine" / "spikes"))
import e25_hands as E  # noqa: E402

OUT = E.OUT


def main() -> int:
    proj = Path(sys.argv[1])
    rows = [json.loads(x) for x in (OUT / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()][-1]["rows"]
    rig = E.Rig(E.GLB)
    guides = {}
    for key, (anim, speed, _) in E.CLIPS.items():
        _, _, body, hands = E.render_guides(rig, anim, speed)
        guides[key] = {"body": body, "hands": hands}
    tmp = Path(tempfile.mkdtemp(prefix="loom2-e25r-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": E.TOKEN, "PYTHONIOENCODING": "utf-8"}
    log = (OUT / "rescore_orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(E.PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env, stdout=log, stderr=subprocess.STDOUT, text=True)
    out = []
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                E.api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        E.api("POST", "/engine/start")                                           # SDPose only: the engine, no job
        from e10_stage import sdpose_graph
        from e12_angles import Engine
        eng = Engine("127.0.0.1:8188")
        for row in rows:
            if not row.get("clip_id"):
                continue
            frames = sorted((proj / "clips" / row["clip_id"] / "master").glob("*.png"))
            g = guides[row["clip"]]
            stats = {"same": [0, 0, []], "swap": [0, 0, []]}
            overlay_done = False
            for idx in range(0, len(frames), 6):
                im = Image.open(frames[idx]).convert("RGB")
                sx, sy = im.size[0] / E.W, im.size[1] / E.H
                hp, _, _ = eng.run(sdpose_graph(eng.upload(frames[idx])))
                people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                if not people:
                    continue
                person = max(people, key=lambda q: sum(q["pose_keypoints_2d"][2::3]))
                b = np.array(g["body"][idx][0], float)[:, :2] * [sx, sy]
                torso = np.linalg.norm(b[1] - (b[8] + b[11]) / 2)
                gh = np.array(g["hands"][idx], float) * [sx, sy]
                pr = np.array(person.get("hand_right_keypoints_2d") or [0] * 63, float).reshape(-1, 3)
                pl = np.array(person.get("hand_left_keypoints_2d") or [0] * 63, float).reshape(-1, 3)
                for mode, (gr, gl) in (("same", (gh[:21], gh[21:])), ("swap", (gh[21:], gh[:21]))):
                    for gt, pred in ((gr, pr), (gl, pl)):
                        for k in range(21):
                            stats[mode][1] += 1
                            if pred[k, 2] > 0.3:
                                e = np.linalg.norm(pred[k, :2] - gt[k]) / max(1.0, torso)
                                stats[mode][2].append(e)
                                if e <= 0.1:
                                    stats[mode][0] += 1
                if not overlay_done and idx >= len(frames) // 3:
                    d = ImageDraw.Draw(im)
                    for x, y in gh:
                        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(0, 220, 0))
                    for pred in (pr, pl):
                        for x, y, c in pred:
                            if c > 0.3:
                                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(230, 0, 0))
                    xs, ys = gh[:, 0], gh[:, 1]
                    box = (max(0, xs.min() - 60), max(0, ys.min() - 60), min(im.size[0], xs.max() + 60), min(im.size[1], ys.max() + 60))
                    im.crop(box).resize((int((box[2] - box[0]) * 3), int((box[3] - box[1]) * 3))).save(OUT / f"overlay_{row['clip']}_{row['arm']}_{row['run']}.png")
                    overlay_done = True
            r = {"clip": row["clip"], "arm": row["arm"], "run": row["run"]}
            for mode in ("same", "swap"):
                hit, tot, errs = stats[mode]
                r[f"pck_{mode}"] = round(hit / tot, 3) if tot else None
                r[f"err_{mode}"] = round(float(np.median(errs)), 3) if errs else None
            out.append(r)
            print(time.strftime("%H:%M:%S"), r, flush=True)
    finally:
        try:
            E.api("POST", "/shutdown"); time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
        log.close()
    for arm in ("A", "B"):
        rs = [r for r in out if r["arm"] == arm]
        if rs:
            best = "same" if np.mean([r["pck_same"] or 0 for r in rs]) >= np.mean([r["pck_swap"] or 0 for r in rs]) else "swap"
            print(f"arm {arm}: hand PCK@0.1·torso ({best}) mean {np.mean([r[f'pck_{best}'] for r in rs]):.3f}, median error {np.mean([r[f'err_{best}'] for r in rs]):.3f} torso over {len(rs)} runs")
    with (OUT / "rescore.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "rows": out}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
