"""E23b follow-up (journal 2026-10-19 17:10) — proportions: the animation references (the characters as made) against Stage's skeleton and against what Move drew, all from SDPose
wholebody (COCO-WholeBody 133 → the OpenPose-style dict SDPose returns) or Stage's 18 keypoints. Ratios to the figure's height (nose → the
lower ankle, plus a head allowance is not needed: the same definition everywhere)."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"F:\source\repos\stubz003_loom2")
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e23a_joins as A  # noqa: E402
from e10_stage import sdpose_graph  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e23b"
# COCO-18 (OpenPose): 0 nose 1 neck 2 r_sho 3 r_elb 4 r_wri 5 l_sho 6 l_elb 7 l_wri 8 r_hip 9 r_knee 10 r_ank 11 l_hip 12 l_knee 13 l_ank


def ratios(b, hands=None, feet=None):
    b = np.array(b, float).reshape(-1, 3)
    ok = lambda *i: all(b[k, 2] > 0.2 for k in i)  # noqa: E731
    d = lambda i, j: float(np.linalg.norm(b[i, :2] - b[j, :2]))  # noqa: E731
    if not ok(0, 1, 8, 11, 10, 13):
        return None
    hip = (b[8, :2] + b[11, :2]) / 2
    ank = (b[10, :2] + b[13, :2]) / 2
    h = float(np.linalg.norm(b[0, :2] - ank))
    r = {"height_px": round(h, 1),
         "head_neck": d(0, 1) / h, "torso": float(np.linalg.norm(b[1, :2] - hip)) / h,
         "leg": (d(8, 9) + d(9, 10) + d(11, 12) + d(12, 13)) / 2 / h, "shoulders": d(2, 5) / h, "hips": d(8, 11) / h,
         "arm": (d(2, 3) + d(3, 4) + d(5, 6) + d(6, 7)) / 2 / h}
    if hands:
        hs = []
        for hand in hands:
            q = np.array(hand, float).reshape(-1, 3)
            if (q[:, 2] > 0.3).sum() >= 10:
                v = q[q[:, 2] > 0.3, :2]
                hs.append(float(np.linalg.norm(q[0, :2] - q[12, :2])) if q[0, 2] > 0.3 and q[12, 2] > 0.3 else float(np.ptp(v, axis=0).max()))
        if hs:
            r["hand"] = float(np.median(hs)) / h
    if feet is not None:
        f = np.array(feet, float).reshape(-1, 3)
        fl = [float(np.linalg.norm(f[k, :2] - f[k + 2, :2])) for k in (0, 3) if f[k, 2] > 0.3 and f[k + 2, 2] > 0.3]
        if fl:
            r["foot"] = float(np.median(fl)) / h
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}


def detect(e, path):
    hp, _, _ = e.run(sdpose_graph(e.upload(path)))
    people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
    if not people:
        return None
    p = max(people, key=lambda q: sum(q["pose_keypoints_2d"][2::3]))
    return p


rows = {}
with A.Session() as x:
    for name in ("mara", "ines"):
        p = detect(x.e, OUT / "refs" / f"{name}.png")
        rows[f"{name} reference"] = ratios(p["pose_keypoints_2d"], [p.get("hand_left_keypoints_2d"), p.get("hand_right_keypoints_2d")], p.get("foot_keypoints_2d"))
        print(name, "keys:", [k for k in p.keys()])
    for run in ("M_s20261021", "M_s20261022"):
        for fid, name, frames in (("fig_m", "mara", (110, 140, 160)), ("fig_i", "ines", (0, 8, 16))):
            acc = []
            for f in frames:
                p = detect(x.e, OUT / "runs" / run / fid / "chain" / f"{f:04d}.png")
                if p:
                    r = ratios(p["pose_keypoints_2d"], [p.get("hand_left_keypoints_2d"), p.get("hand_right_keypoints_2d")], p.get("foot_keypoints_2d"))
                    if r:
                        acc.append(r)
            if acc:
                rows[f"{name} Move {run[-2:]}"] = {k: round(float(np.median([a[k] for a in acc if k in a])), 3) for k in acc[0]}
for fid, name, frames in (("fig_m", "mara", (110, 140, 160)), ("fig_i", "ines", (0, 8, 16))):
    kp = json.loads((OUT / "stage" / fid / "keypoints.json").read_text(encoding="utf-8"))
    acc = [ratios(kp[f]) for f in frames]
    acc = [a for a in acc if a]
    rows[f"{name} Stage"] = {k: round(float(np.median([a[k] for a in acc])), 3) for k in acc[0]}
for k, v in rows.items():
    print(f"{k:22s}", v)
(OUT / "proportions.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
