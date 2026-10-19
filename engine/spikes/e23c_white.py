"""Spike E23c (proto01_animate 02 §3; the author's idea, D103): the white set — does a Move layer made in front of the set's floor and blocks
in **white** give contact and shadows that blend onto the plate better than a plain grey ground with drawn contact shadows?

E23b's shot with a **locked-off camera** at E21's (a Move layer's background is its reference's, which does not move), Mara and Ines with
their fitted bodies (D104, engine/spikes/out/ca1b/bodies.json), D102's F16 with W1 chaining. Built on e23b_layers.py (the blocking by the
app in a visible Edge, the plate, the chains, the SAM 3 text mattes kept inside the Stage mask).

  M0    the animation reference on its grey ground (CN4's padding), contact shadows drawn under the ankles (E23b's Move)
  MW    the white set: Stage's clay render of the empty set from the camera, lifted to white, the character cut from its animation
        reference (a colour key off its plain ground) and placed where the figure starts (frame 0: its position and height); the shadows
        are the model's — the layer's luminance ÷ the white set's outside the character, normalised on the far background, multiplied
        onto the plate
  MWf   as MW with the bodies' feet ×0.85 (the author: "their feet is still quite large"), one seed
  MS    M0's layers with Stage's own shadows instead of the drawn ones: a `light` object at the plate's window (left, high, a little behind)
        casts the mannequins' shadows in Stage's lit clay pass, and each figure's shadow (the clay with it over the clay without it) darkens
        the plate; no generation of its own

The first MW run had no light at all (the white set was the unlit clay lifted to white, the character pasted in with no shadow) and the
model drew none (the author: "there are no shadows, did we add lights?"); it was stopped. The white set is now the lit clay: the light
object's shadows, the blocks' and the character's own frame-0 shadow on the floor.

Measured (score): PCK and the joins (E23b's), the shadow under each figure (its area within a box under the ankles, and how dark),
Ines' contact with the stool once seated (her hips against the stool's top edge in the frame), E21's band step, the reference's ghost,
the feet (SDPose heel → big toe against the height, MW against MWf); time and VRAM. For the author: compare.mp4 (M0 | MW, a row per
seed), feet.jpg (MW against MWf).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e23c_white.py stage   # visible Edge, Vite on 1420 (both bodies: feet ×1 and ×0.85)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23c_white.py refs    # the white set and the placed references (CPU)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23c_white.py run     # the arms, one GPU job at a time
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23c_white.py ms      # MS from the M0 runs (CPU)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23c_white.py score
Outputs under engine/spikes/out/e23c/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e23c"
FIT = ROOT / "engine" / "spikes" / "out" / "ca1b" / "bodies.json"
os.environ["LOOM2_E23B_OUT"] = str(OUT)
os.environ["LOOM2_E23B_BODIES"] = str(OUT / "bodies.json")
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e23a_joins as A  # noqa: E402
import e23b_layers as B  # noqa: E402

B.C1 = B.C0                                       # the locked-off camera
B.WITH_CLAY = True                                # the lit clay sequences (Stage's shadows)
LIGHT = {"id": "light_key", "kind": "light", "name": "Window", "preset": None, "transform": {"pos": [-3.4, 2.8, 0.2], "rot": [0, 0, 0], "scale": [1, 1, 1]},
         "colour_id": 5}                          # inside the room by the plate's window (left, high): Stage's room has no window opening, so a light outside it is blocked by the wall
B.EXTRA_OBJECTS = [LIGHT]
W, H, N, FPS = B.W, B.H, B.N, B.FPS
SEEDS = [20261021, 20261022]
ARMS = [("M0", s) for s in SEEDS] + [("MW", s) for s in SEEDS] + [("MWf", SEEDS[0])]
FEET_SMALL = 0.85


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    return B.load_state()


def save_state(s: dict) -> None:
    B.save_state(s)


# ---- stage: the blocking twice (feet ×1, ×0.85), the empty set's clay ---------------------------------------------------------------
def stage(a: argparse.Namespace) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bodies = json.loads(FIT.read_text(encoding="utf-8"))
    (OUT / "bodies.json").write_text(json.dumps(bodies, indent=1), encoding="utf-8")
    ca1b = json.loads((ROOT / "engine" / "spikes" / "out" / "e23b" / "state.json").read_text(encoding="utf-8"))
    s = load_state(); s["refs"] = ca1b["refs"]; save_state(s)
    for src in ("refs",):
        if not (OUT / src).exists():
            shutil.copytree(ROOT / "engine" / "spikes" / "out" / "e23b" / src, OUT / src)
    if B.stage(a):
        return 1
    # the feet ×0.85 blocking into its own folder (the pose sequences differ only in the drawn feet)
    small = {k: {**v, "feet": round(v.get("feet", 1.0) * FEET_SMALL, 3)} for k, v in bodies.items()}
    f_out = OUT / "feet"
    f_out.mkdir(parents=True, exist_ok=True)
    (f_out / "bodies.json").write_text(json.dumps(small, indent=1), encoding="utf-8")
    keep_out, keep_bodies = B.OUT, B.BODIES
    B.OUT, B.STATE, B.BODIES = f_out, f_out / "state.json", str(f_out / "bodies.json")
    try:
        if B.stage(a):
            return 1
    finally:
        B.OUT, B.STATE, B.BODIES = keep_out, keep_out / "state.json", keep_bodies
    return 0


def plate(a: argparse.Namespace) -> int:
    return B.plate(a)


# ---- the white set and the placed references -----------------------------------------------------------------------------------------
def cutout(ref: Path) -> tuple[np.ndarray, np.ndarray]:
    """The character off its plain ground: pixels ΔE > 14 from the border's median, the largest blob, softened 1 px."""
    a = np.asarray(Image.open(ref).convert("RGB"))
    L = A.lab(a)
    border = np.concatenate([L[0], L[-1], L[:, 0], L[:, -1]])
    m = np.linalg.norm(L - np.median(border, axis=0), axis=-1) > 14
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)), dtype=np.float32) / 255.0
    return a, m


def whites(clay: np.ndarray) -> np.ndarray:
    """The lit clay pass lifted to white: its brightest white, the mid-greys lifted (γ 0.55) so the walls read white while the light's
    shadows keep their contrast."""
    g = clay.astype(np.float32).mean(axis=2)
    hi = max(1.0, float(np.percentile(g, 99.5)))
    return np.repeat((255 * np.clip(g / hi, 0, 1) ** 0.55)[..., None], 3, axis=2)


def stage_shadow(fid: str, i: int) -> np.ndarray:
    """Stage's own shadow of a figure in frame i, as a ratio on the plate: the lit clay with the figure over the lit clay without it, <= 1,
    1 on the figure itself (its mask grown 2 px)."""
    a = np.asarray(Image.open(OUT / "stage" / fid / "clay" / f"{i:04d}.png").convert("L"), dtype=np.float32)
    b = np.asarray(Image.open(OUT / "stage" / "set" / "clay" / f"{i:04d}.png").convert("L"), dtype=np.float32)
    r = np.clip(a / np.maximum(8.0, b), 0.0, 1.0)
    r[B.dilate(B.stage_mask(fid, i), 2)] = 1.0
    return r


def refs(a: argparse.Namespace) -> int:
    clay = np.asarray(Image.open(OUT / "stage" / "set" / "clay" / "0000.png").convert("RGB"))
    white = whites(clay)
    Image.fromarray(white.astype(np.uint8)).save(OUT / "white_set.png")
    s = load_state()
    for fid, name in B.FIGS.items():
        kp = json.loads((OUT / "stage" / fid / "keypoints.json").read_text(encoding="utf-8"))[0]
        b = np.array(kp, float)
        ank = (b[10, :2] + b[13, :2]) / 2
        h = float(np.linalg.norm(b[0, :2] - ank))                    # nose → ankles at frame 0
        img, m = cutout(OUT / "refs" / f"{name.lower()}.png")
        ys, xs = np.nonzero(m > 0.5)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        # the reference's own nose → ankles is ≈ 0.86 of its head-to-sole box (the fitted references, SDPose); its soles ≈ 4 % below the ankles
        scale = (h / 0.86) / max(1, y1 - y0)
        cw, ch = max(1, int((x1 - x0) * scale)), max(1, int((y1 - y0) * scale))
        piece = Image.fromarray(img[y0:y1, x0:x1]).resize((cw, ch), Image.LANCZOS)
        alpha = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)).resize((cw, ch), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))
        hip_x = float((b[8, 0] + b[11, 0]) / 2)
        sole = float(ank[1] + 0.045 * h)
        ox, oy = int(hip_x - cw / 2), int(sole - ch)
        lit = white * stage_shadow(fid, 0)[..., None]                 # the character's own shadow on the white floor, from the window light
        out = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
        out.paste(piece, (ox, oy), alpha)
        out.save(OUT / "refs" / f"{name.lower()}_white.png")
        s.setdefault("white_refs", {})[fid] = {"box": [ox, oy, ox + cw, oy + ch], "scale": round(scale, 3)}
        log(f"{name}: placed at {ox},{oy} ({cw}×{ch} px) in the white set")
    save_state(s)
    sheet = Image.new("RGB", (W * 2, H), (0, 0, 0))
    for i, name in enumerate(("mara", "ines")):
        sheet.paste(Image.open(OUT / "refs" / f"{name}_white.png"), (i * W, 0))
    sheet.resize((W, H // 2)).save(OUT / "white_refs.jpg", quality=90)
    return 0


# ---- the arms ----------------------------------------------------------------------------------------------------------------------
def shadow_ratio(layer: np.ndarray, white: np.ndarray, keep: np.ndarray, fig_far: np.ndarray) -> np.ndarray:
    """The model's shadows: the layer's luminance over the white set's, outside the character (its matte grown 3 px), normalised on the
    far background (the frame away from both figures), clipped to [0.25, 1], softened 2 px."""
    ll, lw = layer.mean(axis=2), np.maximum(8.0, white.mean(axis=2))
    r = ll / lw
    norm = float(np.median(r[fig_far])) if fig_far.sum() > 1000 else 1.0
    r = np.clip(r / max(1e-3, norm), 0.25, 1.0)
    r[B.dilate(keep > 0.3, 3)] = 1.0
    return np.asarray(Image.fromarray((r * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), dtype=np.float32) / 255.0


def assemble_white(dest: Path, plate_fr: list, layers: dict, white: np.ndarray) -> dict:
    dist = json.loads((OUT / "stage" / "dist.json").read_text(encoding="utf-8"))
    md = dest / "merged"
    shutil.rmtree(md, ignore_errors=True); md.mkdir(parents=True)
    sams = {f: B.kept_mattes(dest, f, 36, layers[f]) for f in B.FIGS}
    alphas, shadows = {f: [] for f in B.FIGS}, {f: [] for f in B.FIGS}
    for i in range(N):
        far = np.ones((H, W), bool)
        for f in B.FIGS:
            far &= ~B.dilate(B.stage_mask(f, i), 90)
        out = plate_fr[i].copy()
        for fid in B.FIGS:                                       # the shadows first, every layer's
            layer = B.arr(B.frames_of(dest / fid / "chain")[i])
            r = shadow_ratio(layer, white, sams[fid][i], far)
            out *= r[..., None]
            shadows[fid].append((r * 255).astype(np.uint8))
        for fid in sorted(B.FIGS, key=lambda f: -dist[min(i, len(dist) - 1)][f]):
            layer = B.arr(B.frames_of(dest / fid / "chain")[i])
            al = B.soft(sams[fid][i], 1.2) * B.dilate(sams[fid][i] > 0.5, 3)
            out = out * (1 - al[..., None]) + layer * al[..., None]
            alphas[fid].append(al.astype(np.float16))
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(md / f"{i:04d}.png")
    np.savez_compressed(dest / "alpha.npz", **{f: np.stack(v) for f, v in alphas.items()})
    np.savez_compressed(dest / "shadow.npz", **{f: np.stack(v) for f, v in shadows.items()})
    return {}


def assemble_stage_shadows(src: Path, dest: Path, plate_fr: list, layers: dict) -> None:
    """MS: the M0 layers (their chains and mattes), the plate darkened by Stage's own shadow of each figure (the window light), then the
    figures far -> near; no generation of its own."""
    dist = json.loads((OUT / "stage" / "dist.json").read_text(encoding="utf-8"))
    md = dest / "merged"
    shutil.rmtree(md, ignore_errors=True); md.mkdir(parents=True)
    sams = {f: B.kept_mattes(src, f, 36, layers[f]) for f in B.FIGS}
    alphas = {f: [] for f in B.FIGS}
    for i in range(N):
        out = plate_fr[i].copy()
        for fid in B.FIGS:
            out *= stage_shadow(fid, i)[..., None]
        for fid in sorted(B.FIGS, key=lambda f: -dist[min(i, len(dist) - 1)][f]):
            al = B.soft(sams[fid][i], 1.2) * B.dilate(sams[fid][i] > 0.5, 3)
            out = out * (1 - al[..., None]) + B.arr(B.frames_of(src / fid / "chain")[i]) * al[..., None]
            alphas[fid].append(al.astype(np.float16))
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(md / f"{i:04d}.png")
    np.savez_compressed(dest / "alpha.npz", **{f: np.stack(v) for f, v in alphas.items()})


def shadows_from_stage(a: argparse.Namespace) -> int:
    """MS for every M0 run (CPU)."""
    s = load_state()
    plate_fr = [B.arr(p) for p in B.frames_of(OUT / "plate")]
    for r in [x for x in s.get("runs", []) if x["arm"] == "M0"]:
        if any(x["arm"] == "MS" and x["seed"] == r["seed"] for x in s["runs"]):
            continue
        src, dest = OUT / "runs" / f"M0_s{r['seed']}", OUT / "runs" / f"MS_s{r['seed']}"
        dest.mkdir(parents=True, exist_ok=True)
        for fid in B.FIGS:                                           # the score reads the layers where the run is
            if not (dest / fid).exists():
                shutil.copytree(src / fid, dest / fid)
        assemble_stage_shadows(src, dest, plate_fr, json.loads(json.dumps(r["layers"])))
        A.encode(B.frames_of(dest / "merged"), dest / "merged.mp4", FPS, crf=12)
        s["runs"].append({**r, "arm": "MS", "note": "M0's layers, Stage's shadows (no generation)", "stamp": time.strftime("%Y-%m-%d %H:%M")})
        save_state(s)
        log(f"MS seed {r['seed']}: assembled")
    return 0


def run(a: argparse.Namespace) -> int:
    s = load_state()
    if "white_refs" not in s:
        print("stage and refs first"); return 2
    ros = A.roster()
    kps = {f: json.loads((OUT / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in B.FIGS}
    far_near = B.order()
    done = {(r["arm"], r["seed"]) for r in s.get("runs", [])}
    white = np.asarray(Image.open(OUT / "white_set.png").convert("RGB"), dtype=np.float32)
    plate_fr = [B.arr(p) for p in B.frames_of(OUT / "plate")]
    with A.Session() as x:
        refs_grey = {f: x.e.upload(A.pad_reference(OUT / "refs" / f"{B.FIGS[f].lower()}.png", OUT / "refs" / f"{B.FIGS[f].lower()}_padded.png")) for f in B.FIGS}
        refs_white = {f: x.e.upload(OUT / "refs" / f"{B.FIGS[f].lower()}_white.png") for f in B.FIGS}
        poses = {f: x.e.upload(OUT / "stage" / f"pose_{f}.mp4") for f in B.FIGS}
        poses_small = {f: x.e.upload(OUT / "feet" / "stage" / f"pose_{f}.mp4") for f in B.FIGS}
        for arm, seed in ARMS:
            if (arm, seed) in done:
                continue
            t0 = time.time()
            dest = OUT / "runs" / f"{arm}_s{seed}"
            log(f"{arm} seed {seed}")
            layers = {}
            for fid in far_near:
                c = B.CAST[B.FIGS[fid]]
                ground = "Plain light grey studio background" if arm == "M0" else "A plain white room with white blocks, soft shadows"
                prompt = f"{c['desc'][0].upper() + c['desc'][1:]} {c['act']}. {ground}, static camera."
                ref = refs_grey[fid] if arm == "M0" else refs_white[fid]
                pose = poses_small[fid] if arm == "MWf" else poses[fid]
                layers[fid] = B.chain(x, ros, ref, pose, seed, prompt, dest / fid, f"{arm}_s{seed}_{fid}")
                B.matte(x, ros, dest, fid, layers[fid])
            if arm == "M0":
                B.assemble_m(dest, kps, plate_fr, layers)
            else:
                assemble_white(dest, plate_fr, layers, white)
            A.encode(B.frames_of(dest / "merged"), dest / "merged.mp4", FPS, crf=12)
            row = {"arm": arm, "seed": seed, "layers": layers, "wall_min": round((time.time() - t0) / 60, 1), "order": far_near,
                   "peak_vram_gb": max([b["peak_vram_gb"] for L in layers.values() for b in L["batches"]] + [L.get("sam_peak_vram_gb", 0) for L in layers.values()]),
                   "stamp": time.strftime("%Y-%m-%d %H:%M")}
            s.setdefault("runs", []).append(row)
            save_state(s)
            log(f"{arm} seed {seed}: {row['wall_min']} min, peak {row['peak_vram_gb']} GB")
    return 0


# ---- the scores ----------------------------------------------------------------------------------------------------------------------
def stool_top_y() -> float:
    """The stool's top front edge in the frame (builders.ts room: the 0.45 × 0.48 × 0.45 block at the origin), through E21's camera."""
    pts = np.array([[-0.225, 0.48, 0.225], [0.225, 0.48, 0.225]])
    _, py = B.project(B.C0, pts, W, H)
    return float(np.mean(py))


def shadow_under(sh: np.ndarray | None, kp: list, frame: np.ndarray, plate: np.ndarray) -> tuple[float, float]:
    """The shadow in a box under the ankles (as wide as the hips' twice, from the ankles to 6 % of the height below): its area (the fraction
    darker than 0.9 of the plate) and its mean darkness there."""
    b = np.array(kp, float)
    if len(b) < 14 or b[10, 2] <= 0 or b[13, 2] <= 0:
        return float("nan"), float("nan")
    h = float(np.linalg.norm(b[0, :2] - (b[10, :2] + b[13, :2]) / 2))
    cx = float((b[10, 0] + b[13, 0]) / 2)
    y0 = int(max(b[10, 1], b[13, 1]) - 0.02 * h)
    x0, x1 = int(cx - 0.25 * h), int(cx + 0.25 * h)
    y1 = int(y0 + 0.08 * h)
    x0, x1, y0, y1 = max(0, x0), min(W, x1), max(0, y0), min(H, y1)
    if x1 - x0 < 4 or y1 - y0 < 2:
        return float("nan"), float("nan")
    ratio = frame[y0:y1, x0:x1].mean(axis=2) / np.maximum(8.0, plate[y0:y1, x0:x1].mean(axis=2))
    dark = ratio < 0.9
    return float(dark.mean()), float(1 - ratio[dark].mean()) if dark.any() else 0.0


def score(a: argparse.Namespace) -> int:
    from loom2.tools.facesim import FaceSim
    from e10_stage import sdpose_graph
    from e23b_proportions import ratios
    s = load_state()
    fs = FaceSim(B.MODELS)
    heroes = {}
    for f, name in B.FIGS.items():
        im = np.asarray(Image.open(OUT / "refs" / f"{name.lower()}.png").convert("RGB"))
        heroes[f] = fs.embed(im, max(fs.detect(im), key=lambda q: q.area).kps)
    kps = {f: json.loads((OUT / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in B.FIGS}
    plate_fr = B.frames_of(OUT / "plate")
    top = stool_top_y()
    scores = []
    with A.Session() as x:
        for r in s["runs"]:
            sc = B.score_run(r, x.e, fs, heroes, kps)
            dest = OUT / "runs" / f"{r['arm']}_s{r['seed']}"
            merged = B.frames_of(dest / "merged")
            sh = {}
            for f in B.FIGS:
                vals = [shadow_under(None, kps[f][i], B.arr(merged[i]), B.arr(plate_fr[i])) for i in range(0, N, 8)]
                vals = [v for v in vals if v[0] == v[0]]
                sh[B.FIGS[f]] = {"area": round(float(np.mean([v[0] for v in vals])), 3), "dark": round(float(np.mean([v[1] for v in vals])), 3)} if vals else None
            sc["shadow"] = sh
            # Ines seated (frames from 40 on): her hips against the stool's top edge, in pixels (+ = below the edge)
            offs, feet = [], {}
            for i in (60, 100, 140):
                hp, _, _ = x.e.run(sdpose_graph(x.e.upload(merged[i])))
                people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                ik = np.array(kps["fig_i"][i], float)
                best = min(people, key=lambda p: np.hypot(p["pose_keypoints_2d"][0] - ik[0, 0], p["pose_keypoints_2d"][1] - ik[0, 1]), default=None)
                if best:
                    q = np.array(best["pose_keypoints_2d"], float).reshape(-1, 3)
                    if q[8, 2] > 0.3 and q[11, 2] > 0.3:
                        offs.append(float((q[8, 1] + q[11, 1]) / 2 - top))
            sc["ines_hips_vs_stool_px"] = round(float(np.mean(offs)), 1) if offs else None
            for f, idx in (("fig_m", (110, 140, 160)),):
                acc = []
                for i in idx:
                    hp, _, _ = x.e.run(sdpose_graph(x.e.upload(B.frames_of(dest / f / "chain")[i])))
                    people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                    if people:
                        p = max(people, key=lambda q: sum(q["pose_keypoints_2d"][2::3]))
                        rr = ratios(p["pose_keypoints_2d"], [p.get("hand_left_keypoints_2d"), p.get("hand_right_keypoints_2d")], p.get("foot_keypoints_2d"))
                        if rr and "foot" in rr:
                            acc.append(rr["foot"])
                feet[B.FIGS[f]] = round(float(np.median(acc)), 3) if acc else None
            sc["foot"] = feet
            sc["ghost_frames"] = {B.FIGS[f]: L.get("ghost_frames") for f, L in r["layers"].items()}
            scores.append(sc)
            log(f"{sc['arm']} s{sc['seed']}: PCK {sc['pck']}, joins {[(j['frame'], j['ratio']) for j in sc['joins']]}, shadow {sh}, Ines' hips vs the stool "
                f"{sc['ines_hips_vs_stool_px']} px, foot {feet}, band {sc['band_grad_ratio']}, ghost {sc['ghost_frames']}, {sc['wall_min']} min, peak {sc['peak_vram_gb']} GB")
    for r in s["runs"]:
        d = OUT / "runs" / f"{r['arm']}_s{r['seed']}"
        shutil.rmtree(d / "chain", ignore_errors=True); shutil.copytree(d / "merged", d / "chain")
        A.encode(A.rife(d, 241), d / "merged24.mp4", 24, crf=14)
        shutil.rmtree(d / "chain", ignore_errors=True)
    outputs(s["runs"], scores)
    s["scores"] = scores
    s["scored_at"] = time.strftime("%Y-%m-%d %H:%M")
    save_state(s)
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f_:
        f_.write(json.dumps({"at": s["scored_at"], "scores": scores}) + "\n")
    return 0


def outputs(runs: list[dict], scores: list[dict]) -> None:
    seqs = {(r["arm"], r["seed"]): B.frames_of(OUT / "runs" / f"{r['arm']}_s{r['seed']}" / "rife24") for r in runs}
    n = min(len(v) for v in seqs.values())
    tw, th = W // 2, H // 2
    grid = []
    for i in range(n):
        im = Image.new("RGB", (tw * 3, th * len(SEEDS)), (0, 0, 0))
        names = {"M0": "grey ground, drawn shadows", "MS": "grey ground, Stage shadows", "MW": "white set, the model's shadows"}
        for row, seed in enumerate(SEEDS):
            for col, arm in enumerate(("M0", "MS", "MW")):
                p = seqs.get((arm, seed))
                if p:
                    t = Image.open(p[i]).convert("RGB").resize((tw, th), Image.LANCZOS)
                    im.paste(A.label(t, f"{names[arm]} · seed {seed} · {i / 24:.2f} s"), (col * tw, row * th))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    cw, ch, cols = 166, 96, 11
    cs = Image.new("RGB", (8 + cols * (cw + 2), 8 + len(scores) * (ch + 18)), (24, 24, 24))
    dr = ImageDraw.Draw(cs)
    for ri, sc in enumerate(scores):
        merged = B.frames_of(OUT / "runs" / f"{sc['arm']}_s{sc['seed']}" / "merged")
        y = 8 + ri * (ch + 18)
        dr.text((8, y), f"{sc['arm']} seed {sc['seed']} · PCK {sc['pck']} · shadow {sc['shadow']} · stool {sc['ines_hips_vs_stool_px']} px", fill=(230, 230, 230))
        for c in range(cols):
            cs.paste(Image.open(merged[min(len(merged) - 1, c * FPS)]).convert("RGB").resize((cw, ch), Image.LANCZOS), (8 + c * (cw + 2), y + 14))
    cs.save(OUT / "sheet.jpg", quality=90)
    # the feet: MW against MWf, the same seed, Mara and Ines where they stand
    if ("MW", SEEDS[0]) in seqs and ("MWf", SEEDS[0]) in seqs:
        st = Image.new("RGB", (W, H), (0, 0, 0))
        for r_, arm in enumerate(("MW", "MWf")):
            for c_, i in enumerate((0, 100, 150)):
                f = Image.open(B.frames_of(OUT / "runs" / f"{arm}_s{SEEDS[0]}" / "merged")[i]).convert("RGB").crop((0, H // 2, W, H)).resize((W // 3, H // 4))
                st.paste(A.label(f, f"{arm} {'feet ×1' if arm == 'MW' else 'feet ×0.85'} · frame {i}"), (c_ * W // 3, r_ * H // 4))
        st.crop((0, 0, W, H // 2)).save(OUT / "feet.jpg", quality=90)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["stage", "plate", "refs", "run", "ms", "score"])
    a = ap.parse_args()
    return {"stage": stage, "plate": plate, "refs": refs, "run": run, "ms": shadows_from_stage, "score": score}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
