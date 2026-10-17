"""E22 scoring (see e22_layers.py): per-character action proxies from per-frame SAM 3 masks, identity, time and VRAM per step; the sheets,
the per-character strips, the MP4s and the side-by-side. CPU only. Called as `e22_layers.py score [--best-a SEED --best-b SEED]`.

Definitions:
  masks     every two-character clip (a, a_ltx, b merged) gets the same measurement: SAM3_Detect by text "woman:2" on every frame (union),
            split per frame into left (Mara) and right (Ines) at the widest empty column run between the two people (no gap → the previous
            frame's split column; counted as `split_fallback`).
  h0        a character's mask height over frames 0–4 (median) — every distance is in body heights (bh), so 832×480 and 1024×576 compare.
  walk      the feet x (mean x of the mask's lowest 8 % rows): last 8 frames' median − first 5 frames' median, ÷ h0 (+ = to the right);
            `walk_max` the largest |displacement| at any frame.
  arms_up   max over frames of (mask top at frames 0–4 − mask top at t) ÷ h0: how far the mask rises above the start (arms above the head).
  reach_l   max over frames of the mask's extent left of its own feet x, minus that at the start, ÷ h0 (an arm pointing left).
  motion    mean |Δ luminance| (0–255) between consecutive frames inside the character's mask ∪ the previous mask (dilated 4 px); `motion_bins`
            its mean over ten equal time bins (≈ 0.5 s each), `motion_mean` over the clip.
  identity  FaceSim on every 8th frame: a face belongs to the character whose split mask holds its centre (else the nearer side); own vs
            cross like E21 (`wrong` = cross > own); single-character layer clips: the largest face.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from e21_layers import arr, dilate, encode_mp4, frames_of, load_mask, lum
from e21_score import face_single, ident_summary, sheet, thumbs
from e22_layers import BEATS, CHARS, E21, MODELS, OUT, SEED0, load_state

EVERY_ID = 8
IDX9 = [0, 10, 20, 30, 40, 50, 60, 70, 80]


def split_lr(m: np.ndarray, prev_x: float | None) -> tuple[np.ndarray, np.ndarray, float, bool]:
    """(left mask, right mask, split column, fell back)."""
    occ = m.any(axis=0)
    xs = np.nonzero(occ)[0]
    w = m.shape[1]
    if len(xs) == 0:
        x = prev_x if prev_x is not None else w / 2
        return np.zeros_like(m), np.zeros_like(m), x, True
    gaps = np.diff(xs)
    k = int(np.argmax(gaps)) if len(gaps) else -1
    if k >= 0 and gaps[k] >= 3:
        x = (xs[k] + xs[k + 1]) / 2
        fb = False
        if prev_x is not None and abs(x - prev_x) > 0.2 * w:   # a stray blob: keep the previous split
            x, fb = prev_x, True
    else:
        x, fb = (prev_x if prev_x is not None else w / 2), True
    left = m.copy(); left[:, int(x):] = False
    right = m.copy(); right[:, : int(x)] = False
    return left, right, float(x), fb


def char_series(masks: list[np.ndarray], frames: list[Path]) -> dict:
    n = len(masks)
    top, feet, left_ext, area = [], [], [], []
    for m in masks:
        ys, xs = np.nonzero(m)
        if len(ys) < 30:
            top.append(np.nan); feet.append(np.nan); left_ext.append(np.nan); area.append(0); continue
        y0, y1 = ys.min(), ys.max()
        band = ys >= y1 - 0.08 * (y1 - y0)
        fx = xs[band].mean()
        top.append(y0); feet.append(fx); left_ext.append(fx - xs.min()); area.append(len(ys))
    top, feet, left_ext = np.array(top, float), np.array(feet, float), np.array(left_ext, float)
    hs = []
    for m in masks[:5]:
        ys = np.nonzero(m)[0]
        if len(ys):
            hs.append(ys.max() - ys.min())
    h0 = float(np.median(hs)) if hs else float("nan")
    mot = []
    prev_l, prev_m = None, None
    for t in range(n):
        l_ = lum(arr(frames[t]))
        if prev_l is not None:
            reg = dilate(masks[t] | prev_m, 4)
            mot.append(float(np.abs(l_ - prev_l)[reg].mean()) if reg.any() else 0.0)
        prev_l, prev_m = l_, masks[t]
    mot = np.array(mot)
    f0, f1 = np.nanmedian(feet[:5]), np.nanmedian(feet[-8:])
    bins = [round(float(b.mean()), 2) for b in np.array_split(mot, 10)]
    return {"h0_px": round(h0, 1), "walk_bh": round(float((f1 - f0) / h0), 3), "walk_max_bh": round(float(np.nanmax(np.abs(feet - f0)) / h0), 3),
            "arms_up_bh": round(float(np.nanmax(np.nanmedian(top[:5]) - top) / h0), 3),
            "reach_l_bh": round(float(np.nanmax(left_ext - np.nanmedian(left_ext[:5])) / h0), 3),
            "motion_mean": round(float(mot.mean()), 2), "motion_bins": bins, "missing_frames": int(sum(1 for a in area if a == 0)),
            "feet_path_bh": [round(float((x - f0) / h0), 3) if not np.isnan(x) else None for x in feet[::10]]}


def two_char(name: str, frames: list[Path], sam_dir: Path) -> tuple[dict, dict[str, list[np.ndarray]]]:
    sm = frames_of(sam_dir)
    n = min(len(frames), len(sm))
    L, R, fb, prev = [], [], 0, None
    for t in range(n):
        m = load_mask(sm[t]) > 0.5
        a, b, prev, f = split_lr(m, prev)
        L.append(a); R.append(b); fb += int(f)
    return {"split_fallback": fb, "Mara": char_series(L, frames[:n]), "Ines": char_series(R, frames[:n])}, {"L": L, "R": R}


def face_pairs_masked(fs, a: np.ndarray, heroes: dict, mL: np.ndarray, mR: np.ndarray) -> dict:
    fl = fs.detect(a.astype(np.uint8))
    out: dict = {"L": None, "R": None}
    best: dict = {}
    for f in fl:
        cx, cy = int((f.bbox[0] + f.bbox[2]) / 2), int((f.bbox[1] + f.bbox[3]) / 2)
        cy, cx = min(max(cy, 0), a.shape[0] - 1), min(max(cx, 0), a.shape[1] - 1)
        side = "L" if mL[cy, cx] else "R" if mR[cy, cx] else None
        if side is None:
            lx = np.nonzero(mL.any(axis=0))[0]; rx = np.nonzero(mR.any(axis=0))[0]
            dl = abs(cx - lx.mean()) if len(lx) else 1e9
            dr = abs(cx - rx.mean()) if len(rx) else 1e9
            side = "L" if dl <= dr else "R"
        if side not in best or f.area > best[side].area:
            best[side] = f
    for side, f in best.items():
        e = fs.embed(a.astype(np.uint8), f.kps)
        other = "R" if side == "L" else "L"
        out[side] = (fs.similarity(e, heroes[side]), fs.similarity(e, heroes[other]))
    return out


def crop_strip(frames: list[Path], masks: list[np.ndarray], idx: list[int], th: int = 220) -> list[Image.Image]:
    """The character's whole path: the union bbox of its masks over the clip, padded, the same crop on every shown frame."""
    u = np.zeros_like(masks[0])
    for m in masks:
        u |= m
    ys, xs = np.nonzero(u)
    if len(ys) == 0:
        return thumbs(frames, idx, 160)
    hh, ww = u.shape
    py, px = int(0.06 * (ys.max() - ys.min())), int(0.1 * (ys.max() - ys.min()))
    box = (max(0, xs.min() - px), max(0, ys.min() - py), min(ww, xs.max() + px), min(hh, ys.max() + py))
    out = []
    for i in idx:
        im = Image.open(frames[min(i, len(frames) - 1)]).convert("RGB").crop(box)
        out.append(im.resize((round(th * im.width / im.height), th), Image.LANCZOS))
    return out


def score(a) -> int:
    from loom2.tools.facesim import FaceSim
    s = load_state()
    fs = FaceSim(MODELS)
    heroes = {}
    for k in CHARS:
        im = np.asarray(Image.open(OUT / "heroes" / f"{k}.png").convert("RGB"))
        f = max(fs.detect(im), key=lambda x: x.area)
        heroes[k] = fs.embed(im, f.kps)
    seeds = sorted({int(n.split("_s")[1]) for n in s.get("clips", {}) if n.startswith("a_s")})
    stamp = time.strftime("%Y-%m-%d %H:%M")
    rows: list[dict] = []
    split_masks: dict[str, dict] = {}
    arms = {"a": lambda sd: OUT / "clips" / f"a_s{sd}", "a_ltx": lambda sd: OUT / "clips" / f"altx_s{sd}", "b": lambda sd: OUT / "merged" / f"b_s{sd}"}
    samname = {"a": "a_s{}", "a_ltx": "altx_s{}", "b": "b_s{}"}
    for arm, where in arms.items():
        for sd in seeds:
            fr = frames_of(where(sd))
            sdir = OUT / "sam" / samname[arm].format(sd)
            if not fr or not frames_of(sdir):
                continue
            act, sm = two_char(f"{arm}_{sd}", fr, sdir)
            split_masks[f"{arm}_{sd}"] = sm
            every = EVERY_ID if arm != "a_ltx" else 12
            pairs = [face_pairs_masked(fs, arr(fr[i]), heroes, sm["L"][i], sm["R"][i]) for i in range(0, len(sm["L"]), every)]
            row = {"arm": arm, "seed": sd, "frames": len(fr), "action": act,
                   "identity": {CHARS[k]["name"]: ident_summary([p[k] for p in pairs]) for k in CHARS},
                   "both_found": sum(1 for p in pairs if p["L"] and p["R"]),
                   "swapped_frames": sum(1 for p in pairs if p["L"] and p["R"] and p["L"][1] + p["R"][1] > p["L"][0] + p["R"][0])}
            rows.append(row)
            print(json.dumps({k_: v for k_, v in row.items() if k_ != "action"}, ensure_ascii=False))
            print("   ", json.dumps({c: {x: act[c][x] for x in ("walk_bh", "walk_max_bh", "arms_up_bh", "reach_l_bh", "motion_mean")} for c in ("Mara", "Ines")}))
    single_masks = {}
    for sd in seeds:
        for k in CHARS:
            nm = f"{k}_s{sd}"
            fr = frames_of(OUT / "clips" / nm)
            sm = frames_of(OUT / "sam" / nm)
            if not fr or not sm:
                continue
            masks = [load_mask(p) > 0.5 for p in sm[: len(fr)]]
            single_masks[nm] = masks
            ids = [face_single(fs, arr(fr[i]), heroes, k) for i in range(0, len(fr), EVERY_ID)]
            row = {"arm": "single", "clip": nm, "seed": sd, "char": CHARS[k]["name"], "frames": len(fr),
                   "action": {CHARS[k]["name"]: char_series(masks, fr[: len(masks)])}, "identity": {CHARS[k]["name"]: ident_summary(ids)}}
            rows.append(row)
            print(json.dumps({k_: v for k_, v in row.items() if k_ != "action"}, ensure_ascii=False))
    # ---- times per shot
    st = s.get("steps", {})

    def t(name: str) -> float:
        return float(st.get(name, {}).get("wall_s") or 0.0)

    e21st = json.loads((E21 / "state.json").read_text(encoding="utf-8"))
    plate_t = float(e21st["steps"][f"plate_s{e21st['plate_seed']}"]["wall_s"])
    copy_all = {k: sum(v["wall_s"] for n, v in st.items() if n.startswith(f"copy_{k}_c")) for k in CHARS}
    tries = {k: len(s.get("copy_tries", {}).get(k, [])) for k in CHARS}
    times: dict[str, list] = {}
    for i, sd in enumerate(seeds):
        times.setdefault("a", []).append(t(f"a_still_s{sd}") + t(f"clip_a_s{sd}"))
        if f"clip_altx_s{sd}" in st:
            times.setdefault("a_ltx", []).append(t(f"a_still_s{sd}") + t(f"clip_altx_s{sd}"))
        cps = sum(copy_all[k] / max(1, tries[k]) * tries[k] / max(1, len(seeds)) for k in CHARS)   # every try, spread over the shots
        times.setdefault("b", []).append(plate_t + cps + sum(t(f"clip_{k}_s{sd}") + t(f"sam_{k}_s{sd}") for k in CHARS) + t(f"merge_b_s{sd}"))
    summary = {"stamp": stamp, "times_per_shot_s": {k: [round(x, 1) for x in v] for k, v in times.items()},
               "copy_tries": s.get("copy_tries"), "copies_picked": s.get("copies"), "still_yaw": s.get("yaw"), "prompts": s.get("prompts"),
               "beats": BEATS, "vram_peak_gb": {n: v.get("vram_peak_gb") for n, v in st.items()}}
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"stamp": stamp, **r}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"stamp": stamp, **summary, "steps": st}, ensure_ascii=False) + "\n")
    # ---- sheets
    tw = 200
    hdr_a = [Image.open(OUT / "stills" / f"a_s{sd}.png").convert("RGB").resize((300, 169)) for sd in seeds]
    sheet([("stills (Stage clay, both bound)", hdr_a)] + [(f"a · Wan 2.2 · seed {sd} · frames {IDX9}", thumbs(frames_of(OUT / "clips" / f"a_s{sd}"), IDX9, tw)) for sd in seeds],
          OUT / "sheet_a.jpg", "E22 (a) one Stage still -> one Wan 2.2 I2V clip, both actions in one prompt")
    ltx_seeds = [sd for sd in seeds if frames_of(OUT / "clips" / f"altx_s{sd}")]
    if ltx_seeds:
        idx_l = [round(i * 1.5) for i in IDX9]
        sheet([("stills (the same as a)", hdr_a)] + [(f"a_ltx · LTX-2.3 · seed {sd} · frames {idx_l} (24 fps)", thumbs(frames_of(OUT / "clips" / f"altx_s{sd}"), idx_l, tw))
                                                     for sd in ltx_seeds], OUT / "sheet_a_ltx.jpg", "E22 (a_ltx) the same stills -> one LTX-2.3 distilled clip")
    hdr = [Image.open(OUT / "stills" / "plate.png").convert("RGB").resize((300, 169))]
    hdr += [Image.open(OUT / "copies" / f"{k}_c{c}.png").convert("RGB").resize((300, 169)) for k in CHARS for c in s["copies"][k]]
    rows_ = [("plate · copies Mara x3 · copies Ines x3 (facing as blocked)", hdr)]
    rows_ += [(f"b · seed {sd} · frames {IDX9}", thumbs(frames_of(OUT / "merged" / f"b_s{sd}"), IDX9, tw)) for sd in seeds if frames_of(OUT / "merged" / f"b_s{sd}")]
    for sd in seeds:
        for k in CHARS:
            if frames_of(OUT / "clips" / f"{k}_s{sd}"):
                rows_.append((f"layer seed {sd}: {CHARS[k]['name']} alone", thumbs(frames_of(OUT / "clips" / f"{k}_s{sd}"), IDX9, tw)))
    sheet(rows_, OUT / "sheet_b.jpg", "E22 (b) layers: plate + each character (facing as blocked) animated alone with its own action, stacked by a plain alpha")
    # the copy tries with their yaw
    tr = []
    for k in CHARS:
        ims = []
        for tt in s.get("copy_tries", {}).get(k, []):
            im = Image.open(OUT / "copies" / f"{k}_c{tt['seed']}.png").convert("RGB").resize((300, 169))
            ImageDraw.Draw(im).text((6, 6), f"c{tt['seed']} yaw {tt['yaw']} {'ok' if tt['ok'] else 'REDO'}", fill=(255, 230, 60))
            ims.append(im)
        tr.append((f"{CHARS[k]['name']} copies (yaw: + = turned right; need {'+' if CHARS[k]['sign'] > 0 else '-'}0.4)", ims))
    sheet(tr, OUT / "sheet_copies.jpg", "E22 copy tries")
    # per-character strips: every arm and seed, the character's path cropped
    for arm, where in arms.items():
        rws = []
        for sd in seeds:
            key = f"{arm}_{sd}"
            if key not in split_masks:
                continue
            fr = frames_of(where(sd))
            idx = IDX9 if arm != "a_ltx" else [round(i * 1.5) for i in IDX9]
            for k in CHARS:
                rws.append((f"{arm} · seed {sd} · {CHARS[k]['name']} · frames {idx}", crop_strip(fr, split_masks[key][k], idx)))
        if arm == "b":
            for sd in seeds:
                for k in CHARS:
                    nm = f"{k}_s{sd}"
                    if nm in single_masks:
                        rws.append((f"layer alone · seed {sd} · {CHARS[k]['name']}", crop_strip(frames_of(OUT / "clips" / nm), single_masks[nm], IDX9)))
        if rws:
            sheet(rws, OUT / f"strips_{arm}.jpg", f"E22 per-character strips · {arm}")
    # ---- MP4s
    for i, sd in enumerate(seeds, 1):
        for name, d in (("a", OUT / "clips" / f"a_s{sd}"), ("a_ltx", OUT / "clips" / f"altx_s{sd}"), ("b", OUT / "merged" / f"b_s{sd}"),
                        ("layerMara", OUT / "clips" / f"L_s{sd}"), ("layerInes", OUT / "clips" / f"R_s{sd}")):
            if frames_of(d):
                encode_mp4(frames_of(d), OUT / f"{name}_seed{i}.mp4", fps=24 if name == "a_ltx" else 16, crf=24)
    best_a = a.best_a or seeds[0]
    best_b = a.best_b or seeds[0]
    cols = [(f"(a) one clip · seed {best_a}", frames_of(OUT / "clips" / f"a_s{best_a}")), (f"(b) layers · seed {best_b}", frames_of(OUT / "merged" / f"b_s{best_b}"))]
    if a.best_ltx and frames_of(OUT / "clips" / f"altx_s{a.best_ltx}"):
        lf = frames_of(OUT / "clips" / f"altx_s{a.best_ltx}")
        cols.append((f"(a) LTX-2.3 · seed {a.best_ltx}", [lf[min(len(lf) - 1, round(i * 1.5))] for i in range(81)]))
    n = min(len(f) for _, f in cols)
    cw, ch = 624, 360
    out = []
    for tt in range(n):
        canvas = Image.new("RGB", (cw * len(cols), ch), (0, 0, 0))
        d = ImageDraw.Draw(canvas)
        for c, (name, f) in enumerate(cols):
            canvas.paste(Image.open(f[tt]).convert("RGB").resize((cw, ch), Image.LANCZOS), (c * cw, 0))
            d.text((c * cw + 8, 6), name, fill=(255, 220, 80))
        out.append(np.asarray(canvas).astype(np.float32))
    encode_mp4(out, OUT / "compare.mp4", fps=16, crf=24)
    summary |= {"compare": {"a": best_a, "b": best_b, "a_ltx": a.best_ltx}}
    (OUT / "score_summary.json").write_text(json.dumps({**summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"times_per_shot_s": summary["times_per_shot_s"], "copy_tries": summary["copy_tries"]}))
    return 0
