"""E21 scoring (see e21_layers.py): identity, swaps, seam visibility, background flicker, shadows, time and VRAM per step; the sheets,
the MP4s and the side-by-side. CPU only (FaceSim on onnxruntime). Called as `e21_layers.py score`.

Definitions (also in report.md):
  identity  FaceSim (SCRFD + ArcFace, loom2.tools.facesim — the LoRA check's and the D93 rigs') on every 8th frame. Two-character clips: the
            largest face in the left half is Mara's place, in the right half Ines's; own = cosine to that character's hero, cross = to the
            other's; *wrong* = cross > own. The single-character layer clips (the ceiling): the largest face, own vs cross the same way.
  seam      over every 4th frame, the band where a layer's alpha is between 0.05 and 0.95 (dilated 1 px): mean luminance-gradient magnitude in the
            merged clip ÷ the same pixels in that layer's own clip (1.0 = the merge adds no edge); and the band's mean |merged − layer clip|
            (0–255), the step a viewer could see where plate meets clip.
  flicker   temporal std of luminance (0–255), averaged over the background: outside both figures' silhouettes dilated 40 px, the shadow
            zones and every frame's tracked masks (dilated 20 px) — the same pixels for every arm.
  shadow    under each figure's feet (the shadow ellipse minus the character's own tracked mask), the share of pixels ≥ 6 levels darker than
            the plate: in the copy still, the layer clip, the merged clip (and its ratio to the layer clip: what the merge kept).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from e21_layers import (CHARS, FPS, OUT, H, W, MODELS, arr, blur, dilate, encode_mp4, fit_cover, frames_of, load_mask, load_state, lum,
                        shadow_zone)

EVERY_ID, EVERY_SEAM = 8, 4


def face_pairs(fs, a: np.ndarray, heroes: dict) -> dict:
    """{'L': (own, cross) | None, 'R': …} from the largest face in each half."""
    fl = fs.detect(a.astype(np.uint8))
    out: dict = {"L": None, "R": None}
    for side, cond in (("L", lambda cx: cx < W / 2), ("R", lambda cx: cx >= W / 2)):
        c = [f for f in fl if cond((f.bbox[0] + f.bbox[2]) / 2)]
        if not c:
            continue
        f = max(c, key=lambda x: x.area)
        e = fs.embed(a.astype(np.uint8), f.kps)
        other = "R" if side == "L" else "L"
        out[side] = (fs.similarity(e, heroes[side]), fs.similarity(e, heroes[other]))
    return out


def face_single(fs, a: np.ndarray, heroes: dict, k: str):
    fl = fs.detect(a.astype(np.uint8))
    if not fl:
        return None
    f = max(fl, key=lambda x: x.area)
    e = fs.embed(a.astype(np.uint8), f.kps)
    return (fs.similarity(e, heroes[k]), fs.similarity(e, heroes["R" if k == "L" else "L"]))


def ident_summary(vals: list) -> dict:
    got = [v for v in vals if v is not None]
    if not got:
        return {"n": len(vals), "found": 0, "own_mean": None, "own_min": None, "cross_mean": None, "wrong": 0}
    own = [v[0] for v in got]
    cross = [v[1] for v in got]
    return {"n": len(vals), "found": len(got), "own_mean": round(float(np.mean(own)), 3), "own_min": round(float(np.min(own)), 3),
            "cross_mean": round(float(np.mean(cross)), 3), "wrong": sum(1 for v in got if v[1] > v[0])}


def grad(a: np.ndarray) -> np.ndarray:
    l_ = lum(a)
    gy, gx = np.gradient(l_)
    return np.hypot(gx, gy)


def thumbs(paths: list[Path], idx: list[int], tw: int) -> list[Image.Image]:
    out = []
    for i in idx:
        im = Image.open(paths[min(i, len(paths) - 1)]).convert("RGB")
        out.append(im.resize((tw, round(tw * im.height / im.width)), Image.LANCZOS))
    return out


def sheet(rows: list[tuple[str, list[Image.Image]]], path: Path, title: str) -> None:
    pad, lab = 6, 16
    wmax = max(sum(im.width + pad for im in ims) for _, ims in rows) + pad
    hsum = 24 + sum(lab + max(im.height for im in ims) + pad for _, ims in rows)
    sh = Image.new("RGB", (wmax, hsum), (24, 24, 24))
    d = ImageDraw.Draw(sh)
    d.text((pad, 6), title, fill=(240, 180, 60))
    y = 24
    for label, ims in rows:
        d.text((pad, y + 2), label, fill=(220, 220, 220))
        x = pad
        for im in ims:
            sh.paste(im, (x, y + lab)); x += im.width + pad
        y += lab + max(im.height for im in ims) + pad
    sh.save(path, quality=86)


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
    plate = np.load(OUT / "plate832.npy")
    sil = {k: load_mask(OUT / "masks" / f"sil832_{k}.png") > 0.5 for k in CHARS}
    zone = {k: shadow_zone(sil[k], 1.0) for k in CHARS}
    # the background: the same pixels for every arm
    fg = dilate(sil["L"], 40) | dilate(sil["R"], 40) | shadow_zone(sil["L"], 1.6) | shadow_zone(sil["R"], 1.6)
    for d in sorted((OUT / "sam").iterdir()):
        if d.is_dir():
            for p in frames_of(d)[::4]:
                fg |= dilate(load_mask(p) > 0.5, 20)
    bg = ~fg
    rows: list[dict] = []
    stamp = time.strftime("%Y-%m-%d %H:%M")

    def flicker(paths: list[Path]) -> float:
        st = np.stack([lum(arr(p)) for p in paths])
        return round(float(st.std(axis=0)[bg].mean()), 3)

    def shadow_cov(frame: np.ndarray, k: str, own: np.ndarray | None) -> float:
        z = zone[k] & ~(dilate(own, 2) if own is not None else sil[k])
        dark = lum(frame) < lum(plate) - 6
        return float(dark[z].mean()) if z.any() else float("nan")

    single: dict[str, dict] = {}
    for sd in seeds:
        for k in CHARS:
            for nm in (f"{k}_s{sd}", f"{k}anim_s{sd}"):
                fr = frames_of(OUT / "clips" / nm)
                if not fr:
                    continue
                sam = frames_of(OUT / "sam" / nm)
                ids = [face_single(fs, arr(fr[i]), heroes, k) for i in range(0, len(fr), EVERY_ID)]
                cov = [shadow_cov(arr(fr[i]), k, load_mask(sam[i]) > 0.5 if sam else None) for i in range(0, len(fr), EVERY_ID)]
                copy = OUT / "copies" / f"{k}_s{sd}.png"
                cov_copy = shadow_cov(np.asarray(fit_cover(Image.open(copy).convert("RGB"))).astype(np.float32), k, load_mask(sam[0]) > 0.5 if sam else None)
                row = {"arm": "single", "clip": nm, "seed": sd, "char": CHARS[k]["name"], "frames": len(fr), "identity": {CHARS[k]["name"]: ident_summary(ids)},
                       "flicker": flicker(fr), "shadow": {CHARS[k]["name"]: {"copy": round(cov_copy, 3), "clip": round(float(np.nanmean(cov)), 3)}},
                       "sam_coverage": round(float(np.mean([load_mask(p).mean() for p in sam])), 4) if sam else None}
                single[nm] = row
                rows.append(row)
                print(json.dumps({k_: v for k_, v in row.items()}, ensure_ascii=False))
    arms = [("a", lambda sd: OUT / "clips" / f"a_s{sd}"), ("b", lambda sd: OUT / "merged" / f"b_s{sd}"), ("b2", lambda sd: OUT / "merged" / f"b2_s{sd}"),
            ("banim", lambda sd: OUT / "merged" / f"banim_s{sd}")]
    for arm, where in arms:
        for sd in seeds:
            fr = frames_of(where(sd))
            if not fr:
                continue
            pairs = [face_pairs(fs, arr(fr[i]), heroes) for i in range(0, len(fr), EVERY_ID)]
            row: dict = {"arm": arm, "seed": sd, "frames": len(fr), "identity": {CHARS[k]["name"]: ident_summary([p[k] for p in pairs]) for k in CHARS},
                         "both_found": sum(1 for p in pairs if p["L"] and p["R"]), "swapped_frames": sum(1 for p in pairs if p["L"] and p["R"] and p["L"][1] + p["R"][1] > p["L"][0] + p["R"][0]),
                         "flicker": flicker(fr)}
            if arm != "a":
                alpha = np.load(OUT / "merged" / f"{'b' if arm == 'b2' else arm}_s{sd}_alpha.npz")["alpha"].astype(np.float32)
                layer_names = [f"L{'anim' if arm == 'banim' else ''}_s{sd}", f"R_s{sd}"]
                seam, step, shadow = {}, {}, {}
                for li, (k, nm) in enumerate(zip(CHARS, layer_names)):
                    lf = frames_of(OUT / "clips" / nm)
                    sam = frames_of(OUT / "sam" / nm)
                    rs, ds, cov = [], [], []
                    for t in range(0, min(len(fr), len(lf)), EVERY_SEAM):
                        al = alpha[li, t]
                        band = dilate((al > 0.05) & (al < 0.95), 1)
                        if band.sum() < 20:
                            continue
                        m, c = arr(fr[t]), arr(lf[t])
                        gm, gc = grad(m)[band].mean(), grad(c)[band].mean()
                        rs.append(gm / max(gc, 1e-3))
                        ds.append(float(np.abs(m - c).mean(axis=2)[band].mean()))
                        if t % EVERY_ID == 0:
                            cov.append(shadow_cov(m, k, load_mask(sam[t]) > 0.5 if sam else None))
                    name = CHARS[k]["name"]
                    seam[name] = round(float(np.mean(rs)), 3) if rs else None
                    step[name] = round(float(np.mean(ds)), 2) if ds else None
                    sc = single.get(nm, {}).get("shadow", {}).get(name, {}).get("clip")
                    mc = round(float(np.nanmean(cov)), 3) if cov else None
                    shadow[name] = {"merged": mc, "layer_clip": sc, "kept": round(mc / sc, 2) if mc is not None and sc else None}
                row |= {"seam_grad_ratio": seam, "seam_band_delta": step, "shadow": shadow}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False))
    # ---- times per shot (wall, from the state's steps)
    st = s.get("steps", {})

    def t(name: str) -> float:
        return float(st.get(name, {}).get("wall_s") or 0.0)

    plate_t = t(f"plate_s{s.get('plate_seed')}")
    times = {}
    for sd in seeds:
        times.setdefault("a", []).append(t(f"a_still_s{sd}") + t(f"clip_a_s{sd}"))
        b = plate_t + t(f"copy_L_s{sd}") + t(f"copy_R_s{sd}") + t(f"clip_L_s{sd}") + t(f"clip_R_s{sd}") + t(f"sam_L_s{sd}") + t(f"sam_R_s{sd}") + t(f"merge_b_s{sd}")
        times.setdefault("b", []).append(b)
        if f"v2v_b2_s{sd}" in st:
            times.setdefault("b2", []).append(b + t(f"v2v_b2_s{sd}"))
        if f"clip_Lanim_s{sd}" in st:
            times.setdefault("banim", []).append(plate_t + t(f"copy_L_s{sd}") + t(f"copy_R_s{sd}") + t(f"clip_Lanim_s{sd}") + t(f"clip_R_s{sd}") + t(f"sam_Lanim_s{sd}")
                                                 + t(f"sam_R_s{sd}") + t(f"merge_banim_s{sd}"))
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"stamp": stamp, **r}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"stamp": stamp, "times_per_shot_s": {k: [round(x, 1) for x in v] for k, v in times.items()}, "steps": st}, ensure_ascii=False) + "\n")
    # ---- sheets and clips
    idx = [0, 16, 32, 48, 64, 80]
    tw = 300
    hdr_a = [Image.open(OUT / "stills" / f"a_s{sd}.png").convert("RGB").resize((tw, round(tw * 9 / 16))) for sd in seeds]
    sheet([("stills (Stage clay, both bound)", hdr_a)] + [(f"a · seed {sd} · frames {idx}", thumbs(frames_of(OUT / "clips" / f"a_s{sd}"), idx, tw)) for sd in seeds],
          OUT / "sheet_a.jpg", "E21 (a) composite still → one Wan 2.2 I2V clip")
    for arm, title in (("b", "E21 (b) layers: plate + each character animated alone, merged"), ("b2", "E21 (b2) = (b) + Wan low-noise v2v from σ 0.3"),
                       ("banim", "E21 (banim) = (b) with the speaker by Wan Animate on a drawn pose sequence")):
        have = [sd for sd in seeds if frames_of(OUT / "merged" / f"{arm}_s{sd}")]
        if not have:
            continue
        sd0 = have[0]
        hdr = [Image.open(OUT / "stills" / "plate.png").convert("RGB").resize((tw, round(tw * 9 / 16)))]
        hdr += [Image.open(OUT / "copies" / f"{k}_s{sd0}.png").convert("RGB").resize((tw, round(tw * 9 / 16))) for k in CHARS]
        al = np.load(OUT / "merged" / f"{'b' if arm == 'b2' else arm}_s{sd0}_alpha.npz")["alpha"].astype(np.float32)[:, 32]
        m = arr(frames_of(OUT / "merged" / f"{arm}_s{sd0}")[32])
        ov = m * 0.5 + np.stack([al[0] * 255, al[1] * 255, np.zeros_like(al[0])], axis=-1) * 0.5
        hdr.append(Image.fromarray(ov.astype(np.uint8)).resize((tw, round(tw * H / W))))
        rows_ = [(f"plate · copy Mara · copy Ines (seed {sd0}) · alphas at frame 32 (red Mara, green Ines)", hdr)]
        rows_ += [(f"{arm} · seed {sd} · frames {idx}", thumbs(frames_of(OUT / "merged" / f"{arm}_s{sd}"), idx, tw)) for sd in have]
        if arm == "b":
            rows_ += [(f"layer clips seed {sd0}: Mara alone", thumbs(frames_of(OUT / "clips" / f"L_s{sd0}"), idx, tw)),
                      (f"layer clips seed {sd0}: Ines alone", thumbs(frames_of(OUT / "clips" / f"R_s{sd0}"), idx, tw))]
        sheet(rows_, OUT / f"sheet_{arm}.jpg", title)
    for i, sd in enumerate(seeds, 1):
        for arm, d in (("a", OUT / "clips" / f"a_s{sd}"), ("b", OUT / "merged" / f"b_s{sd}"), ("b2", OUT / "merged" / f"b2_s{sd}"), ("banim", OUT / "merged" / f"banim_s{sd}"),
                       ("layerMara", OUT / "clips" / f"L_s{sd}"), ("layerInes", OUT / "clips" / f"R_s{sd}")):
            if frames_of(d):
                encode_mp4(frames_of(d), OUT / f"{arm}_seed{i}.mp4", crf=24)
    # the best seed: the highest mean own FaceSim over both characters in (b)
    def own(arm: str, sd: int) -> float:
        r = next((r for r in rows if r["arm"] == arm and r["seed"] == sd), None)
        v = [x["own_mean"] for x in (r or {}).get("identity", {}).values() if x["own_mean"] is not None]
        return float(np.mean(v)) if v else -1.0
    best = max(seeds, key=lambda sd: own("b", sd))
    cols = [("a", OUT / "clips" / f"a_s{best}"), ("b", OUT / "merged" / f"b_s{best}"), ("b2", OUT / "merged" / f"b2_s{best}")]
    cols = [(n, frames_of(d)) for n, d in cols if frames_of(d)]
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
    encode_mp4(out, OUT / "compare.mp4", crf=25)
    summary = {"best_seed": best, "times_per_shot_s": {k: [round(x, 1) for x in v] for k, v in times.items()}}
    (OUT / "score_summary.json").write_text(json.dumps({"stamp": stamp, "rows": rows, **summary}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary))
    return 0
