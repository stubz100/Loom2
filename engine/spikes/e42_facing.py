"""E42 (D157, proto01_UI2 07 §2 — F42, F43): why a figure walking away from the camera is performed facing it. Wan Animate's three inputs are
changed one at a time on the walkthrough's *Stay* (a copy of The Last Ferry: its final made for the shot, Ines's layer — 65 frames at 16 fps,
848×480, her back to the camera in every frame): the pose guide, the reference, the prompt.

- R0 baseline: the app's guide (Stage draws the nose and the eyes whichever way the head faces), the front A-pose placed where the figure
  starts (the layer's own reference — the app never gives the back view), the app's prompt (the sheet and CHARACTER_TAIL);
- R1 guide: the nose and the eyes, and the limbs drawn to them, taken out of the guide on the frames that face away (a real back view gives
  DWPose no face points; the ears stay);
- R2 reference: the back A-pose placed instead;
- R3 prompt: "seen from behind, walking away from the camera, her back to the camera" after the sheet;
- R4 all three.

The graph is the app's (`graphs.build_i2v`, Wan Animate Move at the Draft preset, the layer's size and rate, one batch of 65 frames, one seed
for every run). Each run's frames are read back with SCRFD (FaceSim's detector, on the CPU): the share of the away frames where a frontal
face is found (score ≥ 0.5). Bars (journal E42, set before the run): every run done, peak ≤ 15.5 GB; R0 shows the fault (a face on ≥ 50 % of
its away frames); an input fixes the facing when its run has a face on ≤ 20 % of them; R4 within 10 points of the best single input.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e42_facing.py [--runs R0,R1,R2,R3,R4] [--seed 20261029] [--out results.json]

The engine is started by the script as the orchestrator starts it and stopped at the end (one GPU job at a time, rule 10).
Results: engine/spikes/out/e42/<out>, sheet.jpg, the guides, the placed references, <run>.mp4.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]

ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "e42"
PROJECT = Path("F:/loom2-projects/_u3-check/last-ferry-copy")
FINAL, LAYER = "fin_d9047e7a", "fig_uqkyec80"                 # Stay's final 2 (the Town street plate), Ines
BACK_WORDS = "seen from behind, walking away from the camera, her back to the camera"
BAR_PEAK_GB, BAR_FAULT, BAR_FIX, BAR_ALL = 15.5, 0.5, 0.2, 0.1

# passes.ts: OpenPose COCO-18 as Stage draws it
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLOURS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255),
           (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]
FACE_POINTS = (0, 14, 15)                                      # the nose and the eyes (the ears, 16 and 17, a back view still shows)
FACE_LIMBS = [k for k, (a, b) in enumerate(LIMBS) if a in FACE_POINTS or b in FACE_POINTS]


def away(kp: list[list[float]]) -> bool:
    """The figure's back to the camera: its right shoulder on the image's right of its left one (both in frame)."""
    r, l = kp[2], kp[5]
    return bool(r[2] and l[2] and r[0] > l[0])


def _ellipse(a: tuple[float, float], b: tuple[float, float], r: float, n: int = 24) -> list[tuple[float, float]]:
    """The limb's ellipse as Stage draws it (half its length along it, `r` across) as a polygon."""
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ang, half = math.atan2(b[1] - a[1], b[0] - a[0]), math.hypot(b[0] - a[0], b[1] - a[1]) / 2
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + half * math.cos(t) * ca - r * math.sin(t) * sa, cy + half * math.cos(t) * sa + r * math.sin(t) * ca) for t in (2 * math.pi * i / n for i in range(n))]


def faceless(src: Path, kp: list[list[float]], out: Path) -> None:
    """The frame with the nose, the eyes and their limbs taken out; the neck, the shoulders' limbs and the ears drawn back as Stage draws them."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    r = max(3, round(min(w, h) / 180))
    d = ImageDraw.Draw(im)
    for k in FACE_LIMBS:                                       # black over each face limb and face point (a pixel more, for the soft edge)
        a, b = LIMBS[k]
        if kp[a][2] and kp[b][2]:
            d.polygon(_ellipse((kp[a][0], kp[a][1]), (kp[b][0], kp[b][1]), r + 1.5), fill=(0, 0, 0))
    for p in (*FACE_POINTS, 16, 17):
        if kp[p][2]:
            d.ellipse([kp[p][0] - r - 1.5, kp[p][1] - r - 1.5, kp[p][0] + r + 1.5, kp[p][1] + r + 1.5], fill=(0, 0, 0))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))            # what the black may have clipped: the shoulders' limbs at the neck, at 0.6
    ld = ImageDraw.Draw(layer)
    for k in (0, 1):
        a, b = LIMBS[k]
        if kp[a][2] and kp[b][2]:
            ld.polygon(_ellipse((kp[a][0], kp[a][1]), (kp[b][0], kp[b][1]), r), fill=(*COLOURS[k], 153))
    im = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")
    d = ImageDraw.Draw(im)
    for p in (1, 2, 5, 16, 17):                                # the neck, the shoulders and the ears as dots
        if kp[p][2]:
            d.ellipse([kp[p][0] - r, kp[p][1] - r, kp[p][0] + r, kp[p][1] + r], fill=COLOURS[p])
    im.save(out)


def faces_on(frames: list[Path], which: list[bool], fs) -> dict:
    """The share of the chosen frames where SCRFD finds a frontal face (score ≥ 0.5), and each frame's best score."""
    scores = []
    for f, use in zip(frames, which):
        if not use:
            continue
        found = fs.detect(np.asarray(Image.open(f).convert("RGB")), thresh=0.5)
        scores.append(max((x.score for x in found), default=0.0))
    n = len(scores)
    return {"frames": n, "with_face": sum(1 for s in scores if s >= 0.5), "share": round(sum(1 for s in scores if s >= 0.5) / n, 3) if n else None,
            "mean_score": round(float(np.mean(scores)), 3) if n else None}


def sheet(rows: list[tuple[str, list[Image.Image]]], path: Path, size: tuple[int, int] = (424, 240)) -> None:
    cols = max(len(r[1]) for r in rows)
    im = Image.new("RGB", (size[0] * cols, (size[1] + 22) * len(rows)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, (label, ims) in enumerate(rows):
        y = i * (size[1] + 22)
        d.text((6, y + 4), label, fill=(230, 230, 230))
        for j, x in enumerate(ims):
            im.paste(x.convert("RGB").resize(size, Image.Resampling.LANCZOS), (j * size[0], y + 22))
    im.save(path, quality=88)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="R0,R1,R2,R3,R4")
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--dry", action="store_true", help="the inputs only (the placed references, the two guides): no engine")
    a = ap.parse_args()
    import cr_acceptance as cr
    import httpx
    from e12_angles import Engine
    from e40_seedvr2 import launch_engine, stop_engine
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.config import AppState
    from loom2.engine.graphs import build_i2v
    from loom2.finals import CARRY, CHARACTER_TAIL, FinalStore, place_reference
    from loom2.models import registry
    from loom2.recipes import I2V
    from loom2.roster import Roster
    from loom2.stages import encode_guide
    from loom2.story import StoryStore, compose_sheet
    from loom2.tools.facesim import FaceSim
    from loom2.workspace import Workspace
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    app = AppState()                                            # the author's settings, read only (the models root, the mounted trees)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws, [32], session_id="e42")
    store = FinalStore(ws)
    f = store.get(FINAL)
    layer = next(x for x in f.layers if x.id == LAYER)
    p = StoryStore(ws).profile(layer.profile_id)
    v = p.version(layer.version or p.current)
    w, h, n, fps = f.size["w"], f.size["h"], f.frames, f.rate
    kps = store.keypoints(FINAL, LAYER)
    which = [away(k) for k in kps]
    sheet_words = compose_sheet(v, name=p.name)
    prompts = {"app": f"{p.name}, {sheet_words}, {CHARACTER_TAIL}", "back": f"{p.name}, {sheet_words}, {BACK_WORDS}. {CHARACTER_TAIL}"}
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "project": str(PROJECT), "final": FINAL, "layer": LAYER, "size": [w, h, n, fps], "seed": a.seed,
                     "away_frames": sum(which), "prompts": prompts, "runs": [], "failures": [], "notes": []}

    def save() -> None:
        (OUT / a.out).write_text(json.dumps(results, indent=1), encoding="utf-8")

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    # the references: the front and the back A-pose, each placed where the figure starts (E23c)
    refs: dict[str, Path] = {}
    for side, aid in (("front", v.anim_ref_asset_id), ("back", v.anim_ref_back_asset_id)):
        rec = cat.get(aid) if aid else None
        if rec is None:
            raise SystemExit(f"{p.name} {v.id} has no {side} A-pose")
        out = OUT / f"reference_{side}.png"
        if not place_reference(cat.abs_path(rec), kps[0], w, h, out):
            raise SystemExit(f"the {side} A-pose could not be placed where the figure starts")
        refs[side] = out
    # the guides: as Stage drew it, and without the face on the away frames
    pose = sorted(store.pass_dir(FINAL, LAYER, "pose").glob("*.png"))
    if len(pose) != n or len(kps) != n:
        raise SystemExit(f"the layer has {len(pose)} pose frames and {len(kps)} keypoint frames for {n}")
    guides = {"drawn": OUT / "guide_drawn.mp4", "faceless": OUT / "guide_faceless.mp4"}
    encode_guide(pose, guides["drawn"], fps)
    fl = OUT / "faceless"
    fl.mkdir(exist_ok=True)
    for i, (src, kp) in enumerate(zip(pose, kps)):
        dst = fl / f"{i:04d}.png"
        if which[i]:
            faceless(src, kp, dst)
        else:
            Image.open(src).save(dst)
    encode_guide(sorted(fl.glob("*.png")), guides["faceless"], fps)
    plan = {"R0": ("drawn", "front", "app", "baseline"), "R1": ("faceless", "front", "app", "no face in the guide"), "R2": ("drawn", "back", "app", "the back A-pose"),
            "R3": ("drawn", "front", "back", "from behind in the prompt"), "R4": ("faceless", "back", "back", "all three")}
    runs = [r.strip() for r in a.runs.split(",") if r.strip() in plan]
    if a.dry:
        sheet([("inputs: the guide as drawn · without the face · the front and the back A-pose placed",
                [Image.open(pose[0]), Image.open(fl / "0000.png"), Image.open(refs["front"]), Image.open(refs["back"])])], OUT / "inputs.jpg")
        print(f"dry: {sum(which)} of {n} frames face away; the inputs in {OUT}", flush=True)
        return 0

    spec = next(s for s in registry.animate_specs() if registry.offered(s, app.settings.variant))
    roster = Roster(app.models_root, [Path(x) for x in app.settings.mounted_model_trees], app.settings.variant).scan()
    fs = FaceSim(app.models_root)
    log = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None
    first = [Image.open(pose[0]), Image.open(fl / "0000.png"), Image.open(refs["front"]), Image.open(refs["back"])]
    rows: list[tuple[str, list[Image.Image]]] = [("inputs: the guide as drawn · without the face · the front and the back A-pose placed", first)]
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

        names = {"drawn": upload(guides["drawn"], "video/mp4"), "faceless": upload(guides["faceless"], "video/mp4"),
                 "front": upload(refs["front"], "image/png"), "back": upload(refs["back"], "image/png")}
        for run in runs:
            guide, ref, words, label = plan[run]
            recipe = I2V.model_validate({"kind": "i2v", "model_id": spec.id, "start_asset": "e42", "prompt_text": prompts[words], "frames": n, "fps": fps, "width": w, "height": h,
                                         "preset": "draft", "seeds": [a.seed], "guide": {"asset_id": "e42", "kind": "pose", "strength": 1.0},
                                         "chain": {"clip_id": None, "carry": CARRY, "offset": 0}})
            prefix = f"e42/{run.lower()}/f"
            c = build_i2v(recipe, roster, a.seed, prefix, names[ref], guide_name=names[guide])
            vram.mark()
            t0 = time.time()
            try:
                hist, wall, exec_s = eng.run(c.graph, timeout=3600)
                msgs = {m[0]: m[1] for m in hist["status"].get("messages", [])}
                err = (msgs.get("execution_error") or {}).get("exception_message")
            except Exception as e:  # noqa: BLE001
                wall, exec_s, err = time.time() - t0, None, f"{type(e).__name__}: {e}"[:400]
            peak = vram.window()
            frames = sorted((out_dir / "e42" / run.lower()).glob("*.png")) if not err else []
            row = {"run": run, "label": label, "guide": guide, "reference": ref, "prompt": words, "exec_s": round(exec_s, 1) if exec_s else None, "wall_s": round(wall, 1),
                   "peak_gb": peak, "frames": len(frames), "error": err}
            if frames:
                m = faces_on(frames, which[:len(frames)], fs)
                row["away"] = m
                towards = [not x for x in which[:len(frames)]]
                if any(towards):
                    row["towards"] = faces_on(frames, towards, fs)
                k = len(frames)
                rows.append((f"{run} {label} · a face on {m['with_face']}/{m['frames']} away frames · {row['exec_s']} s · {peak} GB",
                             [Image.open(frames[i]) for i in (0, k // 3, 2 * k // 3, k - 1)]))
                try:
                    import av
                    with av.open(str(OUT / f"{run.lower()}.mp4"), "w") as o:
                        s = o.add_stream("h264", rate=fps)
                        s.width, s.height, s.pix_fmt = w - w % 2, h - h % 2, "yuv420p"
                        for fr in frames:
                            o.mux(s.encode(av.VideoFrame.from_image(Image.open(fr).convert("RGB").crop((0, 0, s.width, s.height)))))
                        o.mux(s.encode())
                except Exception as e:  # noqa: BLE001
                    results["notes"].append(f"{run}: no mp4 ({e})")
                print(f"{run} {label}: {row['exec_s']} s · peak {peak} GB · a face on {m['with_face']} of {m['frames']} away frames (mean score {m['mean_score']})", flush=True)
            else:
                print(f"{run} {label}: error {err}", flush=True)
            results["runs"].append(row)
            save()
            sheet(rows, OUT / "sheet.jpg")
    finally:
        stop_engine(proc)
        log.close()
    by = {r["run"]: r for r in results["runs"]}
    for r in results["runs"]:
        check(not r["error"] and r["frames"] == n, f"{r['run']} done ({r['frames']} frames)")
        check(r["peak_gb"] is None or r["peak_gb"] <= BAR_PEAK_GB, f"{r['run']} peak {r['peak_gb']} GB ≤ {BAR_PEAK_GB}")
    share = lambda run: (by.get(run) or {}).get("away", {}).get("share")  # noqa: E731
    if share("R0") is not None:
        check(share("R0") >= BAR_FAULT, f"R0 shows the fault: a face on {share('R0')} of the away frames (≥ {BAR_FAULT})")
    fixes = [run for run in ("R1", "R2", "R3") if share(run) is not None and share(run) <= BAR_FIX]
    results["fixes"] = fixes
    singles = [share(run) for run in ("R1", "R2", "R3") if share(run) is not None]
    if share("R4") is not None and singles:
        check(share("R4") <= min(singles) + BAR_ALL, f"R4 {share('R4')} within {BAR_ALL} of the best single input ({min(singles)})")
    print(f"inputs that fix the facing (≤ {BAR_FIX}): {', '.join(fixes) or 'none'}", flush=True)
    save()
    return 0 if not results["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
