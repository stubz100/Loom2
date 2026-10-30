"""Spike E44 (Q32; journal 2026-10-30 23:00): a head in profile drawn as a real one is seen — the nose, the near eye and the near ear, the far
eye and ear hidden as DWPose would find them — against today's D158 rule, which reads a profile's overlapping eyes as "facing away".

Cases (the first 77 frames, each layer in its D163 window, the app's Wan Animate graph at Draft):
- M: the market walk's Mira (F:/loom2-projects/market-walk, a true profile: the ears overlap) — arms C, N, NP;
- I: The seal's Ines (the E43 copy, a head turned three-quarters away) — arms C, N.
Arms: C today's guide, reference and prompt; N the profile rule (side < 0.25 of the ear spread to the nose–neck: the near side drawn, not
away; 0.25–0.6 with the eyes mirrored: the nose and the near ear, still away); NP N with "seen from the side, in profile" in the prompt.
Three seeds each. Measured on 12 sampled frames of each take: a face found (SCRFD ≥ 0.5) and frontal (the eyes ≥ 0.3 of the box apart, the
nose between them); a sheet per case. Outputs under engine/spikes/out/e44/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e44_profile.py [--cases M,I] [--seeds 3]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "e44"
N_FRAMES = 77
CASES = {
    "M": {"name": "the market walk · Mira", "project": Path("F:/loom2-projects/market-walk"), "final": "fin_3a18423e", "layer": "fig_mira0001", "arms": ["C", "N", "NP"]},
    "I": {"name": "The seal · Ines", "project": Path("F:/loom2-projects/_e43/last-ferry-copy"), "final": "fin_47a428a0", "layer": "fig_q98kue1v", "arms": ["C", "N"]},
}
SIDE, AWAY_PROFILE = 0.25, 0.6
PROFILE_WORDS = "seen from the side, in profile"


def classify(k: list, mirrored: bool) -> tuple[str, str]:
    """A head by its ears' spread against its nose–neck length: side (a true profile), away_profile (turned away past the side), away,
    front; and the near side (the one the nose points to: facing the image's right shows the figure's right)."""
    a = np.asarray(k, dtype=float).reshape(-1, 3)
    d = max(1e-6, float(np.hypot(*(a[0, :2] - a[1, :2]))))
    r = abs(a[16, 0] - a[17, 0]) / d
    side = "right" if a[0, 0] > (a[16, 0] + a[17, 0]) / 2 else "left"
    if r < SIDE:
        return "side", side
    if r < AWAY_PROFILE and mirrored:
        return "away_profile", side
    return ("away" if mirrored else "front"), side


def profiled(kw: list, kind: str, side: str) -> list:
    """Window keypoints with the hidden head points off: a side profile keeps the nose, the near eye and the near ear; a turned-away profile
    the nose and the near ear."""
    pts = [list(p) for p in kw]
    near_eye, far_eye, near_ear, far_ear = (14, 15, 16, 17) if side == "right" else (15, 14, 17, 16)
    if kind == "side":
        pts[far_eye][2] = pts[far_ear][2] = 0.0
    elif kind == "away_profile":
        pts[near_eye][2] = pts[far_eye][2] = pts[far_ear][2] = 0.0
    return pts


def face_measure(fs, frames: list[Path], idx: list[int]) -> dict:
    found = frontal = 0
    dirs = []
    for i in idx:
        a = np.asarray(Image.open(frames[i]).convert("RGB"))
        faces = [x for x in fs.detect(a, thresh=0.5) if x.score >= 0.5]
        if not faces:
            continue
        found += 1
        f = faces[0]
        bw = float(f.bbox[2] - f.bbox[0])
        (ex0, _), (ex1, _), (nx, _) = f.kps[0], f.kps[1], f.kps[2]
        ed = abs(ex1 - ex0)
        if ed >= 0.3 * bw and min(ex0, ex1) - 0.25 * ed <= nx <= max(ex0, ex1) + 0.25 * ed:
            frontal += 1
        dirs.append(1 if nx > (ex0 + ex1) / 2 else -1)
    return {"sampled": len(idx), "found": found, "frontal": frontal, "nose_right": sum(1 for d in dirs if d > 0), "nose_left": sum(1 for d in dirs if d < 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="M,I")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    import httpx
    import loom2.finals as fin
    from loom2.catalogue import Catalogue
    from loom2.config import AppState
    from loom2.finals import BACK_WORDS, CARRY, CHARACTER_TAIL, WINDOW, FinalStore, draw_pose, place_reference, to_window, window_wholebody
    from loom2.models import registry
    from loom2.recipes import I2V
    from loom2.stages import encode_guide
    from loom2.story import StoryStore, compose_sheet
    from loom2.tools.facesim import FaceSim
    from loom2.workspace import Workspace
    WW, WH = WINDOW
    OUT.mkdir(parents=True, exist_ok=True)
    app = AppState()
    fs = FaceSim(app.models_root)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "cases": {}}
    rp = OUT / "results.json"

    def save() -> None:
        rp.write_text(json.dumps(results, indent=1), encoding="utf-8")

    original_faces_away = fin.faces_away
    prepared = []
    for key in [c.strip() for c in a.cases.split(",") if c.strip() in CASES]:
        case = CASES[key]
        ws = Workspace(case["project"])
        cat = Catalogue(ws, [32], session_id="e44")
        store, stories = FinalStore(ws), StoryStore(ws)
        f = store.get(case["final"])
        layer = next(x for x in f.layers if x.id == case["layer"])
        n = min(N_FRAMES, f.frames)
        kps = store.keypoints(f.id, layer.id)[:n]
        wbs = store.wholebody(f.id, layer.id)
        wins = (layer.window or fin.figure_windows(kps, n))[:n]
        p = stories.profile(layer.profile_id)
        v = p.version(layer.version or p.current)
        kinds = [classify(k, original_faces_away(k)) for k in kps]
        d = OUT / key
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        res = {"name": case["name"], "final": f.id, "layer": layer.id, "frames": n, "window_min": round(min(w[2] for w in wins), 2),
               "kinds": {k: sum(1 for x in kinds if x[0] == k) for k in ("side", "away_profile", "away", "front")}, "sides": sorted({s for _, s in kinds}), "arms": {}}
        for arm in case["arms"]:
            profile_rule = arm in ("N", "NP")
            behind = (sum(1 for kd, _ in kinds if kd in ("away", "away_profile")) * 2 > n) if profile_rule else fin.mostly_away(kps)
            anim = cat.get(v.anim_ref_back_asset_id if behind and v.anim_ref_back_asset_id else v.anim_ref_asset_id)
            words = (PROFILE_WORDS + ", ") if arm == "NP" else ""
            prompt = f"{p.name}, {compose_sheet(v, name=p.name)}, {BACK_WORDS + '. ' if behind else ''}{words}{CHARACTER_TAIL}"
            g = d / f"guide_{arm}"
            g.mkdir()
            kws = []
            try:
                if profile_rule:
                    fin.faces_away = lambda kp: False                         # the profile rule has already hidden what is hidden
                for i, (k, win) in enumerate(zip(kps, wins)):
                    kw = to_window(k, win)
                    if profile_rule:
                        kd, sd = kinds[i]
                        kw = profiled(kw, kd, sd) if kd in ("side", "away_profile") else kw
                        if kd in ("away", ):
                            kw = [[q[0], q[1], 0.0] if j in (0, 14, 15) else q for j, q in enumerate(kw)]
                    kws.append(kw)
                    draw_pose(kw, WW, WH, window_wholebody(wbs[i] if i < len(wbs) else None, win)).save(g / f"{i:04d}.png")
            finally:
                fin.faces_away = original_faces_away
            encode_guide(sorted(g.glob("*.png")), d / f"guide_{arm}.mp4", f.rate)
            ref = d / f"reference_{arm}.png"
            placed = place_reference(cat.abs_path(anim), kws[0], WW, WH, ref)
            if not placed:
                Image.open(cat.abs_path(anim)).convert("RGB").save(ref)
            res["arms"][arm] = {"behind": behind, "reference": anim.id, "placed": placed, "prompt": prompt, "seeds": {}}
            prepared.append((key, arm, d, ref, layer.seed, f.rate, prompt, n))
        results["cases"][key] = res
        save()
        print(f"{key} {case['name']}: {res['kinds']} sides {res['sides']} window ×{res['window_min']}; arms "
              + "; ".join(f"{k}: behind={x['behind']}" for k, x in res["arms"].items()), flush=True)

    import cr_acceptance as cr
    from e12_angles import Engine
    from e40_seedvr2 import launch_engine, stop_engine
    from m1_acceptance import port_busy
    from loom2.engine.graphs import build_i2v
    from loom2.roster import Roster
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    spec = next(s for s in registry.animate_specs() if registry.offered(s, app.settings.variant))
    roster = Roster(app.models_root, [Path(x) for x in app.settings.mounted_model_trees], app.settings.variant).scan()
    log = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None
    try:
        proc, launch = launch_engine(log)
        out_dir = Path(launch["argv"][launch["argv"].index("--output-directory") + 1])
        eng = Engine(ENGINE)
        vram = cr.VramSampler()

        def upload(path: Path, mime: str) -> str:
            r = httpx.post(f"http://{ENGINE}/upload/image", files={"image": (path.name, path.read_bytes(), mime)}, data={"overwrite": "true", "type": "input"}, timeout=120)
            r.raise_for_status()
            j = r.json()
            return (j.get("subfolder") + "/" if j.get("subfolder") else "") + j["name"]

        rows: dict[str, list] = {}
        for key, arm, d, ref, seed0, fps, prompt, n in prepared:
            for s in range(a.seeds):
                seed = seed0 + s
                recipe = I2V.model_validate({"kind": "i2v", "model_id": spec.id, "start_asset": "e44", "prompt_text": prompt, "frames": n, "fps": fps,
                                             "width": WW, "height": WH, "preset": "draft", "seeds": [seed], "guide": {"asset_id": "e44", "kind": "pose", "strength": 1.0},
                                             "chain": {"clip_id": None, "carry": CARRY, "offset": 0}})
                prefix = f"e44/{key.lower()}{arm.lower()}{s}/f"
                shutil.rmtree((out_dir / prefix).parent, ignore_errors=True)
                comp = build_i2v(recipe, roster, seed, prefix, upload(ref, "image/png"), guide_name=upload(d / f"guide_{arm}.mp4", "video/mp4"))
                vram.mark()
                t0 = time.time()
                err = None
                try:
                    hist, wall, exec_s = eng.run(comp.graph, timeout=3600)
                    msgs = {m[0]: m[1] for m in hist["status"].get("messages", [])}
                    err = (msgs.get("execution_error") or {}).get("exception_message")
                except Exception as e:  # noqa: BLE001
                    exec_s, err = None, f"{type(e).__name__}: {e}"[:300]
                frames = sorted((out_dir / prefix).parent.glob(f"{Path(prefix).name}*.png"))[:n] if not err else []
                row = {"seed": seed, "exec_s": round(exec_s, 1) if exec_s else None, "wall_s": round(time.time() - t0, 1), "peak_gb": vram.window(), "error": err, "frames": len(frames)}
                if frames:
                    idx = sorted({int(round(i * (len(frames) - 1) / 11)) for i in range(12)})
                    row.update(face_measure(fs, frames, idx))
                    keep = d / f"take_{arm}{s}"
                    keep.mkdir(exist_ok=True)
                    for i in (0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1):
                        Image.open(frames[i]).convert("RGB").resize((240, 424)).save(keep / f"{i:04d}.png")
                    rows.setdefault(key, []).append((f"{arm} seed {seed}: frontal {row.get('frontal')}/{row.get('sampled')}, faces {row.get('found')}", sorted(keep.glob("*.png"))))
                results["cases"][key]["arms"][arm]["seeds"][str(seed)] = row
                save()
                print(f"{key} {arm} seed {seed}: {row}", flush=True)
        for key, rs in rows.items():
            w, h = 240, 424
            sheet = Image.new("RGB", (w * 4 + 260, (h + 4) * len(rs)), (24, 24, 24))
            dr = ImageDraw.Draw(sheet)
            for r_, (label, files) in enumerate(rs):
                dr.text((6, r_ * (h + 4) + h // 2), label, fill=(230, 230, 230))
                for c_, p in enumerate(files[:4]):
                    sheet.paste(Image.open(p), (260 + c_ * w, r_ * (h + 4)))
            sheet.save(OUT / f"sheet_{key}.jpg", quality=86)
    finally:
        if proc is not None:
            stop_engine(proc)
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
