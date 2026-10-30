"""E43 (proto01_UI2 12 — W46, W58): a character layer performed in its own window. A figure small in the frame (W46) or cut by its edge
(W58) breaks Wan Animate at the final's size: the pose guide is drawn at the figure's size in the frame, its reference placed there (or, cut,
padded and centred), and the take paints the empty frame (a ghost face) or a close-up of a part (a hand) — the matte then follows that.
Like D118's head pass (heads.py: crop, work at the model's size, paste back), the layer is performed in a window that holds the whole
figure — tracked from its COCO-18 keypoints over the shot, smoothed, at Wan's portrait size with the final's pixel count (480×848), allowed
to reach outside the frame — the guide drawn in the window, the A-pose placed where the figure starts in it (the window always holds the
whole figure, so `place_reference` always places it); the take and its SAM 3 matte are pasted back into the frame by the window, and the
app's own assembly (final_assembly.assemble_frames) composites the shot.

Cases, on a copy of the walkthrough's project (F:/loom2-projects/ux-walk2-last-ferry → F:/loom2-projects/_e43/last-ferry-copy):
- T: Arrival's Final 2, Tomas — 50 px tall at 18 m through the picture's 20.7 mm camera, 49 frames (W46);
- I: The seal's Final 4, Ines — cut at the knees by the frame's bottom and its left edge, her back to the camera, the first 77 frames (W58).

Runs per case (the app's Wan Animate graph, graphs.build_i2v, Draft, the layer's own seed and prompt; its SAM 3 matte graph):
- B baseline: the walkthrough's own take and matte (no GPU);
- F frame: the 18-point guide redrawn at the frame from the stored keypoints (Stage draws the hands too — they are not stored), the
  layer's own reference — the control: the guide without the hands, nothing else changed;
- W window: the guide and the reference in the window, the take and its matte pasted back.

Measures: the matte against the figure's Stage silhouette in the frame (|layer depth − plate depth| > eps, as the assembly) — IoU per
frame against the silhouette grown 3 px, the share of frames ≥ 0.5, the largest matte / silhouette; the app's identity (facesim.clip_identity
against the run's reference); the seconds and the peak VRAM; sheets. Bars: journal E43, set before the run.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e43_window.py [--cases T,I] [--runs F,W] [--dry]

The engine is started here as the orchestrator starts it and stopped at the end (one GPU job at a time, rule 10).
Results: engine/spikes/out/e43/results.json, sheet_<case>.jpg, the guides and references, the assembled frames.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]

ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "e43"
SOURCE = Path("F:/loom2-projects/ux-walk2-last-ferry")
PROJECT = Path("F:/loom2-projects/_e43/last-ferry-copy")
CASES = {"T": {"name": "Arrival · Tomas (W46)", "final": "fin_b608e3d8", "layer": "fig_04370fc0", "frames": None},
         "I": {"name": "The seal · Ines (W58)", "final": "fin_47a428a0", "layer": "fig_q98kue1v", "frames": 77}}
WW, WH = 480, 848                                 # the window: Wan's portrait at the final's pixel count (848 × 480)
SMOOTH = 9                                        # the window's centre and size smoothed over this many frames (heads.SMOOTH)
TOP, BOTTOM, MARGIN = 0.10, 0.05, 1.15            # above the highest point (the skull over the eyes and ears), below the ankles, all round
BAR_PEAK_GB, BAR_IOU, BAR_GOOD, BAR_RATIO, BAR_FACE, BAR_ID, BAR_TIME = 15.5, 0.6, 0.9, 2.5, 0.5, 0.35, 1.25

LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLOURS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
           (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]


def windows(kps: list, n: int) -> list[tuple[float, float, float]]:
    """(x0, y0, scale) per frame: a WW × WH window round every one of the figure's 18 points (in the frame or not), the skull and the soles
    added, a margin all round, widened for spread arms; the centre and the height smoothed over SMOOTH frames."""
    cs, hs = [], []
    for i in range(n):
        k = np.array(kps[min(i, len(kps) - 1)], dtype=float).reshape(-1, 3)[:, :2]
        x0, y0 = k.min(axis=0)
        x1, y1 = k.max(axis=0)
        tall = max(8.0, y1 - y0)
        y0, y1 = y0 - TOP * tall, y1 + BOTTOM * tall
        h = (y1 - y0) * MARGIN
        h = max(h, (x1 - x0) * MARGIN * WH / WW)
        cs.append(((x0 + x1) / 2, (y0 + y1) / 2))
        hs.append(h)
    c, hh = np.array(cs), np.array(hs)
    pad = SMOOTH // 2
    out = []
    for i in range(n):
        a, b = max(0, i - pad), min(n, i + pad + 1)
        cx, cy = c[a:b].mean(axis=0)
        h = float(hh[a:b].max())                                             # the window never cuts the figure the smoothing would shrink it on
        w = h * WW / WH
        out.append((float(cx - w / 2), float(cy - h / 2), WH / h))
    return out


def to_window(kp: list, win: tuple[float, float, float]) -> list[list[float]]:
    """A frame's keypoints in the window's pixels; a point is drawn when it lies in the window (in the frame or not)."""
    x0, y0, s = win
    out = []
    for x, y, _v in kp:
        u, v = (x - x0) * s, (y - y0) * s
        out.append([u, v, 1 if (0 <= u < WW and 0 <= v < WH) else 0])
    return out


def drawn(kp: list) -> list:
    """D158 (passes.ts drawnPoints): a figure facing away draws no nose and no eyes."""
    from loom2.finals import faces_away
    return [[p[0], p[1], 0] if (faces_away(kp) and i in (0, 14, 15)) else p for i, p in enumerate(kp)]


def draw_pose(kp: list, w: int, h: int) -> Image.Image:
    """passes.ts drawPose for the 18 points: limbs as ellipses at 0.6 alpha, the points as discs, the stroke scaled to the frame."""
    r = max(3, round(min(w, h) / 180))
    base = Image.new("RGB", (w, h), (0, 0, 0))
    kp = drawn(kp)
    for k, (a, b) in enumerate(LIMBS):
        if not (kp[a][2] and kp[b][2]):
            continue
        (x1, y1), (x2, y2) = kp[a][:2], kp[b][:2]
        mx, my, half, ang = (x1 + x2) / 2, (y1 + y2) / 2, float(np.hypot(x2 - x1, y2 - y1)) / 2, float(np.arctan2(y2 - y1, x2 - x1))
        t = np.linspace(0, 2 * np.pi, 36)
        pts = [(mx + half * np.cos(q) * np.cos(ang) - r * np.sin(q) * np.sin(ang), my + half * np.cos(q) * np.sin(ang) + r * np.sin(q) * np.cos(ang)) for q in t]
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon(pts, fill=(*COLOURS[k], 153))
        base = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
    d = ImageDraw.Draw(base)
    for k, (x, y, v) in enumerate(kp):
        if v:
            d.ellipse((x - r, y - r, x + r, y + r), fill=COLOURS[k])
    return base


def paste_back(img: Image.Image, win: tuple[float, float, float], fw: int, fh: int, fill) -> Image.Image:
    """A window's picture into the frame: scaled by 1 / scale, placed at (x0, y0), what falls outside the frame dropped."""
    x0, y0, s = win
    w, h = max(1, round(img.width / s)), max(1, round(img.height / s))
    small = img.resize((w, h), Image.LANCZOS)
    canvas = Image.new(img.mode, (fw, fh), fill)
    canvas.paste(small, (round(x0), round(y0)))
    return canvas


def cutout_bridged(ref: Path):
    """W47: finals.cutout with the key grown 2 px before its central blob is taken (and cut back to the key) — a collar the colour of the
    ground no longer parts the head from the body."""
    import loom2.finals as fin
    a = np.asarray(Image.open(ref).convert("RGB"))
    lab = fin.to_lab(a)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    m = np.linalg.norm(lab - np.median(border, axis=0), axis=-1) > 14
    m = fin.central_blob(grow(m, 2)) & m
    alpha = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0
    ys, xs = np.nonzero(alpha > 0.5)
    ground = tuple(int(v) for v in np.median(np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]), axis=0))
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1], ground


def gray(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0


def grow(m: np.ndarray, r: int) -> np.ndarray:
    return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * r + 1)), dtype=np.uint8) > 127


def agreement(store, fid: str, lid: str, n: int, mattes: list[Path]) -> dict:
    """The matte against the figure's Stage silhouette, frame by frame (the baseline's measure, e43_baseline)."""
    from loom2.final_assembly import DEPTH_EPS
    ious, ratios = [], []
    for i in range(n):
        sil = np.abs(gray(store.pass_dir(fid, lid, "depth") / f"{i:04d}.png") - gray(store.pass_dir(fid, "plate", "depth") / f"{i:04d}.png")) > DEPTH_EPS
        if not sil.any():
            continue
        m = gray(mattes[i]) > 0.5
        s3 = grow(sil, 3)
        ious.append(float((m & s3).sum() / max(1, (m | s3).sum())))
        ratios.append(float(m.sum() / sil.sum()))
    if not ious:
        return {"frames": 0}
    return {"frames": len(ious), "iou": round(float(np.mean(ious)), 3), "good_share": round(float(np.mean([x >= 0.5 for x in ious])), 2),
            "worst_iou": round(min(ious), 3), "ratio_max": round(max(ratios), 1)}


def sheet(rows: list[tuple[str, list[Image.Image]]], path: Path, size: tuple[int, int] = (424, 240)) -> None:
    w, h = size
    cols = max(len(ims) for _, ims in rows)
    out = Image.new("RGB", (cols * w, len(rows) * (h + 22)), (18, 18, 18))
    d = ImageDraw.Draw(out)
    for r, (label, ims) in enumerate(rows):
        d.text((6, r * (h + 22) + 4), label, fill=(230, 230, 230))
        for c, im in enumerate(ims):
            im = im.convert("RGB")
            im.thumbnail((w, h))
            out.paste(im, (c * w + (w - im.width) // 2, r * (h + 22) + 22))
    out.save(path, quality=86)


def scratch_final(store, src_id: str, new_id: str, n: int, lid: str, frames: list[Image.Image] | None, mattes: list[Image.Image] | None):
    """A copy of the final (its passes trimmed to n frames) with the figure layer's take and matte replaced — the app's assembly reads it."""
    src, dst = store.folder(src_id), store.folder(new_id)
    shutil.rmtree(dst, ignore_errors=True)
    for p in src.rglob("*"):
        if p.is_dir() or p.name == "final.json":
            continue
        rel = p.relative_to(src)
        if p.suffix == ".png" and p.stem.isdigit() and int(p.stem) >= n:
            continue
        (dst / rel.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
    rec = json.loads((src / "final.json").read_text(encoding="utf-8"))
    rec["id"], rec["frames"], rec["clip_id"], rec["processing"] = new_id, n, None, []
    for layer in rec["layers"]:
        layer["frames_done"] = min(layer.get("frames_done") or 0, n)
        if layer["id"] == lid and frames is not None:
            layer["source"], layer["takes"] = None, []
    (dst / "final.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    for name, ims in (("frames", frames), ("matte", mattes)):
        if ims is None:
            continue
        d = dst / lid / name
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        for i, im in enumerate(ims):
            im.save(d / f"{i:04d}.png")
    return store.get(new_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="T,I")
    ap.add_argument("--runs", default="F,W")
    ap.add_argument("--dry", action="store_true", help="the inputs only (windows, guides, references) and the baseline: no engine")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    import httpx
    from loom2.catalogue import Catalogue
    from loom2.config import AppState
    from loom2.final_assembly import assemble_frames
    from loom2.finals import BACK_WORDS, CARRY, CHARACTER_TAIL, FinalStore, mostly_away, place_reference, plan_batches
    from loom2.models import registry
    from loom2.recipes import I2V, MatteSequence, matte_mode
    from loom2.stages import encode_guide
    from loom2.story import StoryStore, compose_sheet
    from loom2.tools.facesim import FaceSim, clip_identity
    from loom2.workspace import Workspace
    OUT.mkdir(parents=True, exist_ok=True)
    if not PROJECT.exists():
        print(f"copying {SOURCE} → {PROJECT}", flush=True)
        shutil.copytree(SOURCE, PROJECT)
    app = AppState()
    ws = Workspace(PROJECT)
    cat = Catalogue(ws, [32], session_id="e43")
    store = FinalStore(ws)
    stories = StoryStore(ws)
    fs = FaceSim(app.models_root)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "project": str(PROJECT), "window": [WW, WH], "cases": {}, "failures": []}

    def save() -> None:
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    prepared: dict = {}
    for key in [c.strip() for c in a.cases.split(",") if c.strip() in CASES]:
        case = CASES[key]
        f = store.get(case["final"])
        layer = next(x for x in f.layers if x.id == case["layer"])
        fw, fh, fps = f.size["w"], f.size["h"], f.rate
        n = min(f.frames, case["frames"] or f.frames)
        kps = store.keypoints(f.id, layer.id)[:n]
        p = stories.profile(layer.profile_id)
        v = p.version(layer.version or p.current)
        behind = mostly_away(kps)
        anim = cat.get(v.anim_ref_back_asset_id if behind and v.anim_ref_back_asset_id else v.anim_ref_asset_id)
        prompt = f"{p.name}, {compose_sheet(v, name=p.name)}, {BACK_WORDS + '. ' if behind else ''}{CHARACTER_TAIL}"
        d = OUT / key
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        # the window: per frame, the figure whole in it; the guide and the reference drawn there
        wins = windows(kps, n)
        wk = [to_window(k, w) for k, w in zip(kps, wins)]
        whole = sum(all(q[2] for q in k) for k in wk)
        for name, dims, pts in (("guide_W", (WW, WH), wk), ("guide_F", (fw, fh), kps)):
            g = d / name
            g.mkdir()
            for i, k in enumerate(pts):
                draw_pose(k, *dims).save(g / f"{i:04d}.png")
            encode_guide(sorted(g.glob("*.png")), d / f"{name}.mp4", fps)
        ref_w = d / "reference_W.png"
        placed_w = place_reference(cat.abs_path(anim), wk[0], WW, WH, ref_w)
        import loom2.finals as fin
        ref_h, orig = d / "reference_H.png", fin.cutout
        fin.cutout = cutout_bridged                                          # run H: the window, the reference with its head (W47)
        try:
            place_reference(cat.abs_path(anim), wk[0], WW, WH, ref_h)
        finally:
            fin.cutout = orig
        own = cat.get(layer.reference_asset_id) if layer.reference_asset_id else None
        ref_f = d / "reference_F.png"
        Image.open(cat.abs_path(own) if own else cat.abs_path(anim)).convert("RGB").save(ref_f)
        base = agreement(store, f.id, layer.id, n, [store.matte_dir(f.id, layer.id) / f"{i:04d}.png" for i in range(n)])
        frames_b = sorted(store.frames_dir(f.id, layer.id).glob("*.png"))[:n]
        mattes_b = sorted(store.matte_dir(f.id, layer.id).glob("*.png"))[:n]
        fb = scratch_final(store, f.id, f"{f.id}-e43{key.lower()}b", n, layer.id, None, None)
        assemble_frames(store, fb, d / "assembled_B")
        res = {"name": case["name"], "final": f.id, "layer": layer.id, "frames": n, "behind": behind, "seed": layer.seed, "prompt": prompt,
               "window_whole_frames": whole, "window_px": [round(WH / w[2], 1) for w in (wins[0], wins[-1])], "reference_W_placed": placed_w,
               "runs": {"B": {"matte": base, "identity": clip_identity(fs, np.asarray(Image.open(ref_f).convert("RGB")), frames_b)}}}
        results["cases"][key] = res
        save()
        prepared[key] = {"f": f, "layer": layer, "n": n, "fw": fw, "fh": fh, "fps": fps, "wins": wins, "d": d, "prompt": prompt, "refs": {"W": ref_w, "F": ref_f, "H": ref_h},
                         "frames_b": frames_b, "mattes_b": mattes_b}
        print(f"{key} {case['name']}: {n} frames, behind={behind}, the window holds the whole figure on {whole}/{n} frames "
              f"(the figure {res['window_px'][0]}–{res['window_px'][1]} px of frame tall per window), reference placed in the window: {placed_w}; "
              f"baseline matte {base}", flush=True)
        if a.dry:
            sheet([(f"{key} inputs: the frame guide (F) · the window guide (W) · the layer's reference (F) · the window reference (W)",
                    [Image.open(d / "guide_F" / "0000.png"), Image.open(d / "guide_W" / "0000.png"), Image.open(ref_f), Image.open(ref_w) if placed_w else Image.new("RGB", (8, 8))]),
                   (f"{key} the baseline take, its matte, its assembly (frame 0, mid, last)",
                    [Image.open(frames_b[0]), Image.open(mattes_b[n // 2]), Image.open(d / "assembled_B" / "000000.png"),
                     Image.open(d / "assembled_B" / f"{n // 2:06d}.png"), Image.open(d / "assembled_B" / f"{n - 1:06d}.png")])], OUT / f"sheet_{key}.jpg")
    if a.dry:
        print(f"dry: inputs and sheets in {OUT}", flush=True)
        return 0

    import cr_acceptance as cr
    from e12_angles import Engine
    from e40_seedvr2 import launch_engine, stop_engine
    from m1_acceptance import port_busy
    from loom2.roster import Roster
    from loom2.engine.graphs import build_i2v, build_matte_sequence
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

        def run(graph: dict, prefix: str) -> tuple[list[Path], float | None, float, float | None, str | None]:
            shutil.rmtree((out_dir / prefix).parent, ignore_errors=True)            # a run's own frames only (none left from an earlier try)
            vram.mark()
            t0 = time.time()
            try:
                hist, wall, exec_s = eng.run(graph, timeout=3600)
                msgs = {m[0]: m[1] for m in hist["status"].get("messages", [])}
                err = (msgs.get("execution_error") or {}).get("exception_message")
            except Exception as e:  # noqa: BLE001
                wall, exec_s, err = time.time() - t0, None, f"{type(e).__name__}: {e}"[:400]
            return (sorted((out_dir / prefix).parent.glob(f"{Path(prefix).name}*.png")) if not err else []), exec_s, wall, vram.window(), err

        for key, c in prepared.items():
            f, layer, n, fw, fh, fps, d = c["f"], c["layer"], c["n"], c["fw"], c["fh"], c["fps"], c["d"]
            batch = plan_batches(n)[0]
            rows = [(f"{key} inputs: frame guide · window guide · the layer's reference · the window reference",
                     [Image.open(d / "guide_F" / "0000.png"), Image.open(d / "guide_W" / "0000.png"), Image.open(c["refs"]["F"]), Image.open(c["refs"]["W"])]),
                    (f"{key} B baseline (the walkthrough's): take · matte · assembled (0, mid, last) · matte {results['cases'][key]['runs']['B']['matte']}",
                     [Image.open(c["frames_b"][n // 2]), Image.open(c["mattes_b"][n // 2]), Image.open(d / "assembled_B" / "000000.png"),
                      Image.open(d / "assembled_B" / f"{n // 2:06d}.png"), Image.open(d / "assembled_B" / f"{n - 1:06d}.png")])]
            for rk in [r.strip() for r in a.runs.split(",") if r.strip() in ("F", "W", "H")]:
                w, h = (WW, WH) if rk in ("W", "H") else (fw, fh)
                recipe = I2V.model_validate({"kind": "i2v", "model_id": spec.id, "start_asset": "e43", "prompt_text": c["prompt"], "frames": batch["frames"], "fps": fps,
                                             "width": w, "height": h, "preset": "draft", "seeds": [layer.seed], "guide": {"asset_id": "e43", "kind": "pose", "strength": 1.0},
                                             "chain": {"clip_id": None, "carry": CARRY, "offset": 0}})
                prefix = f"e43/{key.lower()}{rk.lower()}/f"
                comp = build_i2v(recipe, roster, layer.seed, prefix, upload(c["refs"][rk], "image/png"), guide_name=upload(d / f"guide_{'F' if rk == 'F' else 'W'}.mp4", "video/mp4"))
                frames, exec_s, wall, peak, err = run(comp.graph, prefix)
                row: dict = {"size": [w, h], "exec_s": round(exec_s, 1) if exec_s else None, "wall_s": round(wall, 1), "peak_gb": peak, "frames": len(frames), "error": err}
                if frames:
                    frames = frames[:n]
                    clip = d / f"take_{rk}.mp4"
                    encode_guide(frames, clip, fps)
                    mrec = MatteSequence(final_id="e43", layer_id=layer.id, mode=matte_mode(app.settings.variant))
                    mprefix = f"e43/{key.lower()}{rk.lower()}m/m"
                    mcomp = build_matte_sequence(mrec, roster, upload(clip, "video/mp4"), mprefix)
                    masks, m_exec, _, m_peak, m_err = run(mcomp.graph, mprefix)
                    row["matte_exec_s"], row["matte_peak_gb"], row["matte_error"] = (round(m_exec, 1) if m_exec else None), m_peak, m_err
                    takes = [Image.open(p).convert("RGB") for p in frames]
                    mts = [Image.open(p).convert("L").resize((w, h), Image.BILINEAR) for p in masks[:n]]
                    sampled = frames[::4]
                    row["frontal_faces"] = f"{sum(1 for p in sampled if any(x.score >= 0.5 for x in fs.detect(np.asarray(Image.open(p).convert('RGB')), thresh=0.5)))}/{len(sampled)}"
                    if rk in ("W", "H"):
                        takes_f = [paste_back(t, c["wins"][i], fw, fh, (192, 192, 192)) for i, t in enumerate(takes)]
                        mts_f = [paste_back(m, c["wins"][i], fw, fh, 0) for i, m in enumerate(mts)]
                    else:
                        takes_f, mts_f = takes, mts
                    if len(mts_f) == n:
                        md = d / f"matte_{rk}"
                        md.mkdir(exist_ok=True)
                        for i, m in enumerate(mts_f):
                            m.save(md / f"{i:04d}.png")
                        row["matte"] = agreement(store, f.id, layer.id, n, sorted(md.glob("*.png")))
                        fx = scratch_final(store, f.id, f"{f.id}-e43{key.lower()}{rk.lower()}", n, layer.id, takes_f, mts_f)
                        row["assembly"] = assemble_frames(store, fx, d / f"assembled_{rk}")
                        a_dir = d / f"assembled_{rk}"
                        rows.append((f"{key} {rk}: take · matte · assembled (0, mid, last) · {row['exec_s']} s · {peak} GB · matte {row['matte']}",
                                     [takes[n // 2], mts[n // 2], Image.open(a_dir / "000000.png"), Image.open(a_dir / f"{n // 2:06d}.png"), Image.open(a_dir / f"{n - 1:06d}.png")]))
                    row["identity"] = clip_identity(fs, np.asarray(Image.open(c["refs"][rk]).convert("RGB")), frames)
                results["cases"][key]["runs"][rk] = row
                save()
                sheet(rows, OUT / f"sheet_{key}.jpg")
                print(f"{key} {rk}: {row.get('exec_s')} s · peak {peak} GB · matte {row.get('matte')} · identity {(row.get('identity') or {}).get('mean')} "
                      f"({(row.get('identity') or {}).get('with_face')}/{(row.get('identity') or {}).get('sampled')} with a face) · {err or ''}", flush=True)
    finally:
        stop_engine(proc)
        log.close()
    # the bars (journal E43)
    for key, res in results["cases"].items():
        for rk, r in res["runs"].items():
            if rk == "B":
                continue
            check(not r.get("error") and r.get("frames", 0) >= res["frames"], f"{key} {rk} done ({r.get('frames')} frames)")
            check(r.get("peak_gb") is None or r["peak_gb"] <= BAR_PEAK_GB, f"{key} {rk} peak {r.get('peak_gb')} GB ≤ {BAR_PEAK_GB}")
        hr = res["runs"].get("H")
        if hr and "matte" in hr:                                             # run H (journal E43, after the first result): the window and a reference with its head
            m = hr["matte"]
            check(m.get("iou", 0) >= BAR_IOU and m.get("good_share", 0) >= BAR_GOOD and m.get("ratio_max", 99) <= BAR_RATIO, f"{key} H fixes the matte: IoU {m.get('iou')}, good on {m.get('good_share')}, ≤ {m.get('ratio_max')}× the figure")
            if res["behind"]:
                got, of = (int(x) for x in hr["frontal_faces"].split("/"))
                check(got <= 0.2 * of, f"{key} H from behind: a frontal face on {got}/{of} sampled frames (≤ 20 %, D158)")
        wr = res["runs"].get("W")
        if not wr or "matte" not in wr:
            continue
        m = wr["matte"]
        check(res["window_whole_frames"] == res["frames"], f"{key}: the window holds the whole figure on every frame ({res['window_whole_frames']}/{res['frames']})")
        check(m.get("iou", 0) >= BAR_IOU and m.get("good_share", 0) >= BAR_GOOD and m.get("ratio_max", 99) <= BAR_RATIO,
              f"{key} W fixes the matte: IoU {m.get('iou')} ≥ {BAR_IOU}, good on {m.get('good_share')} ≥ {BAR_GOOD}, matte ≤ {m.get('ratio_max')}× ≤ {BAR_RATIO}× the figure")
        if not res["behind"]:
            idn = wr.get("identity") or {}
            share = (idn.get("with_face") or 0) / max(1, idn.get("sampled") or 1)
            check(share >= BAR_FACE and (idn.get("mean") or 0) >= BAR_ID, f"{key} W keeps the face: on {share:.2f} ≥ {BAR_FACE} of the sampled frames, identity {idn.get('mean')} ≥ {BAR_ID}")
        fr = res["runs"].get("F")
        if fr and fr.get("exec_s") and wr.get("exec_s"):
            check(wr["exec_s"] <= BAR_TIME * fr["exec_s"], f"{key} W {wr['exec_s']} s ≤ {BAR_TIME} × F {fr['exec_s']} s")
    save()
    return 0 if not results["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
