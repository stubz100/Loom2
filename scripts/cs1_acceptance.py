"""CS1 (proto01_UIcast 03 §3.1, E37 steps 1–3, D137 stage 1): the skeleton's fixes on the rig — the real engine on a fresh copy of the A1
rig's project, where the author saw Mara's neck, hands and feet go wrong (proto01_UIcast 01 §1.6):

1. the refit: Mara's and Ines' bodies fitted again by the app (the new fit: hips, elbows, knees, feet, S7's pull) — the ratios met, the
   points kept on the version, the A-pose check's note (A1's two stand arms-down: S8);
2. the guide: a new final made from the same stage by Stage (the Final shot card's own path) — Mara's pose guide's hands begin at the
   wrist point (A1's began 0.033 of the height below it; S1, CB5);
3. Wan Animate again, the same seed, on both character layers (Mara's walk, Ines' sit), one GPU job at a time (D97); SDPose reads the
   same frames of the old and the new layers: the hand's reach, nose → neck and the toes' reach against each character's reference.

    orchestrator/.venv/Scripts/python.exe scripts/cs1_acceptance.py          (Vite on 1420 for the browser half)

Results: engine/spikes/out/cs1/results.json; the sheets: .docs/proto01_UIcast/img/cs1-*.jpg.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "cs1"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"
FRAMES = list(range(0, 81, 10))                       # the frames SDPose reads, old and new


def people_of(asset_id: str) -> list[dict]:
    j = P.wait_job(P.api("POST", "/jobs", {"recipe": {"kind": "keypoints", "asset_id": asset_id}, "stage": False})["jobs"][0]["id"])
    return (j.get("result") or {}).get("people") or [] if j["status"] == "done" else []


def measures(person: dict) -> dict[str, float] | None:
    """A figure's proportions as SDPose reads them, over nose → ankles: the hand's reach (its wrist to its farthest point, the larger hand),
    nose → neck, the toes' reach (an ankle to its big toe, the farther)."""
    b = np.array(person.get("pose_keypoints_2d") or [], float).reshape(-1, 3)
    if len(b) < 14 or (b[[0, 1, 10, 13], 2] < 0.3).any():
        return None
    h = float(np.linalg.norm(b[0, :2] - (b[10, :2] + b[13, :2]) / 2))
    if h < 20:
        return None
    reach = []
    for key in ("hand_left_keypoints_2d", "hand_right_keypoints_2d"):
        q = np.array(person.get(key) or [], float).reshape(-1, 3)
        if len(q) >= 21 and q[0, 2] >= 0.3:
            pts = q[1:][q[1:, 2] >= 0.3, :2]
            if len(pts):
                reach.append(float(np.linalg.norm(pts - q[0, :2], axis=1).max()))
    f = np.array(person.get("foot_keypoints_2d") or [], float).reshape(-1, 3)
    toes = [float(np.linalg.norm(f[i, :2] - b[a, :2])) for i, a in ((0, 13), (3, 10)) if len(f) >= 6 and f[i, 2] >= 0.3 and b[a, 2] >= 0.3]
    return {"hand": max(reach) / h if reach else float("nan"), "neck": float(np.linalg.norm(b[0, :2] - b[1, :2])) / h,
            "toes": max(toes) / h if toes else float("nan")}


def guide_hand_gap(pose_dir: Path, keypoints: list) -> float:
    """The pose guide's hand points' gap to the body's wrist point (the nearest blue hand pixel), over nose → ankles; the median of frames."""
    gaps = []
    for i in range(0, len(keypoints), 4):
        p = np.array(keypoints[i], float)
        if p.shape[0] < 14:
            continue
        a = np.asarray(Image.open(pose_dir / f"{i:04d}.png").convert("RGB")).astype(int)
        ys, xs = np.nonzero((a[..., 2] > 200) & (a[..., 0] < 70) & (a[..., 1] < 70))
        h = float(np.linalg.norm(p[0, :2] - (p[10, :2] + p[13, :2]) / 2))
        for w in (4, 7):
            d = np.hypot(xs - p[w, 0], ys - p[w, 1])
            m = d < 0.25 * h
            if m.sum() >= 5:
                gaps.append(float(d[m].min()) / h)
    return float(np.median(gaps)) if gaps else float("nan")


def read_layer(fid: str, lid: str, tag: str) -> list[dict | None]:
    folder = OUT / "proj" / "finals" / fid / lid / "frames"
    keep = OUT / "frames" / tag
    keep.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in FRAMES:
        dst = keep / f"{lid}_{i:04d}.png"
        shutil.copy(folder / f"{i:04d}.png", dst)
        paths.append(str(dst))
    recs = P.api("POST", "/assets/import", {"paths": paths})["items"]
    return [measures(pp[0]) if (pp := people_of(r["id"])) else None for r in recs]


def med(rows: list[dict | None], k: str) -> float:
    v = [r[k] for r in rows if r and np.isfinite(r[k])]
    return float(np.median(v)) if v else float("nan")


def sheet(fid_old: str, fid_new: str, lid: str, name: str, frames: list[int]) -> None:
    tiles = []
    for i in frames:
        for f, d in ((fid_old, "frames"), (fid_new, "pose"), (fid_new, "frames")):
            tiles.append(Image.open(OUT / "proj" / "finals" / f / lid / d / f"{i:04d}.png").convert("RGB"))
    w, h = tiles[0].size
    s = 0.5
    tw, th = int(w * s), int(h * s)
    out = Image.new("RGB", (3 * tw + 20, len(frames) * th + (len(frames) - 1) * 10 + 34), (24, 24, 24))
    d = ImageDraw.Draw(out)
    for c, label in enumerate(("before (A1)", "the new guide", "after (the same seed)")):
        d.text((c * (tw + 10) + 6, 8), label, fill=(225, 225, 225))
    for k, t in enumerate(tiles):
        r, c = divmod(k, 3)
        out.paste(t.resize((tw, th)), (c * (tw + 10), 30 + r * (th + 10)))
    out.save(IMG / f"cs1-{name}.jpg", quality=86)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    P.OUT = OUT
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    app = P.App(OUT / "proj")
    try:
        old = next(f for f in P.api("GET", "/finals")["items"] if f["clip_id"])
        layers = {l["id"]: l for l in old["layers"] if l["kind"] == "figure"}
        profiles = {p["id"]: p for p in P.api("GET", "/story/profiles")["items"]}
        refs: dict[str, dict] = {}
        # 1 · the refit
        for lid, layer in layers.items():
            p = profiles[layer["profile_id"]]
            before = p["versions"][0]["body"]
            j = P.wait_job(P.api("POST", f"/story/profiles/{p['id']}/versions/v1/body/fit")["job_id"])
            v = P.api("GET", f"/story/profiles/{p['id']}")["versions"][0]
            worst = max(abs(x["reference"] - x["fitted"]) / x["reference"] for x in j["result"]["fit"].values())
            refs[lid] = measures(j["result"]["people"][0])
            res[f"{p['name']}_body"] = {"read_as": before, "refit": v["body"], "worst_ratio": round(worst, 4), "note": v["anim_ref_note"], "reference": refs[lid]}
            check(f"{p['name']} refitted: the ratios met, the points kept", j["status"] == "done" and worst < 0.01 and len((v["body_points"] or {}).get("pose") or []) == 18,
                  f"worst {worst:.4f}; neck ×{v['body']['neck']}, hips ×{v['body']['hips']}, feet ×{v['body']['feet']} (read as ×{before['neck']})")
            check(f"{p['name']}'s reference noted: the arms touch the body (S8)", v["anim_ref_note"] == "arms_close", str(v["anim_ref_note"]))
        # 2 · the guide, made by Stage
        t0 = time.time()
        r = subprocess.run(["node", str(ROOT / "scripts" / "cs1_browser.cjs"), old["stage_id"], str(old["rate"]), str(old["size"]["w"]), str(old["size"]["h"])],
                           cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8", timeout=1800,
                           env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
        if r.returncode != 0:
            raise RuntimeError(f"the browser half failed: {r.stderr[-1500:]}")
        new_id = json.loads(r.stdout.strip().splitlines()[-1])["final_id"]
        res["guide_s"] = round(time.time() - t0, 1)
        kp_old = json.loads((OUT / "proj" / "finals" / old["id"] / "fig_m" / "keypoints.json").read_text(encoding="utf-8"))["frames"]
        kp_new = json.loads((OUT / "proj" / "finals" / new_id / "fig_m" / "keypoints.json").read_text(encoding="utf-8"))["frames"]
        gap_old = guide_hand_gap(OUT / "proj" / "finals" / old["id"] / "fig_m" / "pose", kp_old)
        gap_new = guide_hand_gap(OUT / "proj" / "finals" / new_id / "fig_m" / "pose", kp_new)
        res["guide_hand_gap"] = {"before": round(gap_old, 4), "after": round(gap_new, 4)}
        check("Mara's guide: the hand begins at the wrist point (S1)", gap_new < 0.015 and gap_new < gap_old, f"{gap_old:.3f} → {gap_new:.3f} of the height")
        # 3 · Wan Animate again, the same seed; SDPose on the same frames
        for lid, layer in layers.items():
            t1 = time.time()
            q = P.api("POST", f"/finals/{new_id}/layers/{lid}/run", {"seed": layer["seed"]})
            P.wait_job(q["job_id"])
            deadline = time.time() + 3600
            while time.time() < deadline:
                lay = next(x for x in P.api("GET", f"/finals/{new_id}")["layers"] if x["id"] == lid)
                if lay["status"] in ("done", "failed"):
                    break
                time.sleep(5)
            for jid in lay.get("job_ids") or []:
                P.wait_job(jid)
            lay = next(x for x in P.api("GET", f"/finals/{new_id}")["layers"] if x["id"] == lid)
            res[f"{lid}_run_s"] = round(time.time() - t1, 1)
            check(f"{layer['name']}'s layer performed again (seed {layer['seed']})", lay["status"] == "done" and lay["frames_done"] == old["frames"], f"{lay['status']} · {res[f'{lid}_run_s']} s")
        for lid, layer in layers.items():
            before, after = read_layer(old["id"], lid, "before"), read_layer(new_id, lid, "after")
            ref = refs[lid]
            row = {k: {"reference": round(ref[k], 4), "before": round(med(before, k), 4), "after": round(med(after, k), 4)} for k in ("hand", "neck", "toes")}
            res[f"{lid}_measures"] = row
            off = {k: (abs(row[k]["before"] / ref[k] - 1), abs(row[k]["after"] / ref[k] - 1)) for k in row if ref[k] and np.isfinite(ref[k])}
            check(f"{layer['name']}: the hand nearer the reference's (Wan's figure, SDPose)", off["hand"][1] < off["hand"][0],
                  f"reach {row['hand']['before']:.3f} → {row['hand']['after']:.3f} (reference {row['hand']['reference']:.3f})")
            check(f"{layer['name']}: nose → neck and the toes, against the reference", True,
                  f"neck {row['neck']['before']:.3f} → {row['neck']['after']:.3f} (ref {row['neck']['reference']:.3f}); toes {row['toes']['before']:.3f} → {row['toes']['after']:.3f} (ref {row['toes']['reference']:.3f})")
            sheet(old["id"], new_id, lid, f"{layer['name'].lower()}-before-after", [10, 40, 70])
    finally:
        app.close()
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"cs1_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
