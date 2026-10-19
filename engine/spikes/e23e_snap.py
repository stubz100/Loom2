"""Spike E23e (journal 2026-10-19 22:29, D106): the characters sit slightly off their shadows — Wan Animate's Move mode reads only the pose
skeleton, so a generated character lands near, not on, the dummy whose shadow Stage renders. Two ways to make them agree, on E23d's shot
(locked camera, the window light, the fitted bodies, the proxies; M0's characters, seed 20261021):

  (1) the shadow follows the character (CPU after one SDPose pass): the generated character's ankles found in every frame of its Move layer,
      the offset to the dummy's ankles taken onto the floor and smoothed, the figure moved by it in its clay (the dummy's shadow MS1, the
      proxy's MP1), the card cast from the detected feet (MC1) — against E23d's unmoved MS0 / MP0 / MC0
  (2) the character follows the proxy (GPU): Wan Animate's Replace mode, the plate blanked inside the proxy's silhouette (grown 4 px) and
      that silhouette the character mask, far → near; only the character's own SAM 3 matte (inside the silhouette grown 16 px) pasted back;
      with the proxy's shadow (RP)

Measured: the **gap** — from each character's feet (SDPose's ankles) to the nearest pixel of her shadow (the ratio < 0.85), every 4th
frame, median and 90th percentile; for (2) also PCK against Stage's keypoints and the blank left in the silhouette (near-black pixels that
are not the character). For the author: compare.mp4 (top: the dummy's shadow unmoved | moved | the card from the feet; bottom: the
proxy's unmoved | moved | Replace in the proxy).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e23e_snap.py feet      # SDPose on M0's layers (GPU, short)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23e_snap.py stage     # the moved clays and the proxies' silhouettes (Edge, Vite on 1420)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23e_snap.py replace   # (2) on the engine
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23e_snap.py score     # SDPose on the Replace layers (GPU), the gaps, the video
Outputs under engine/spikes/out/e23e/ (git-ignored).
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
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e23e"
E23C, E23D = ROOT / "engine" / "spikes" / "out" / "e23c", ROOT / "engine" / "spikes" / "out" / "e23d"
SEED = 20261021
M0 = E23C / "runs" / f"M0_s{SEED}"
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def _b(out: Path = OUT):
    os.environ["LOOM2_E23B_OUT"] = str(out)
    os.environ["LOOM2_E23B_BODIES"] = str(E23C / "bodies.json")
    import e23b_layers as B
    import e23c_white as C
    B.OUT, B.STATE = out, out / "state.json"
    B.C1 = B.C0
    B.WITH_CLAY = True
    B.EXTRA_OBJECTS = [C.LIGHT]
    return B, C


def load_state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def detect(e, path: Path, near: np.ndarray) -> list | None:
    """SDPose's person in `path` nearest the given keypoints (a Move layer can hold the reference's standing ghost too)."""
    from e10_stage import sdpose_graph
    hp, _, _ = e.run(sdpose_graph(e.upload(path)))
    people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
    best, bd = None, 1e9
    for p in people:
        q = np.array(p["pose_keypoints_2d"], float).reshape(-1, 3)
        both = (q[:, 2] > 0.3) & (near[:, 2] > 0)
        if both.sum() >= 4:
            dd = float(np.median(np.linalg.norm(q[both, :2] - near[both, :2], axis=1)))
            if dd < bd:
                best, bd = q.tolist(), dd
    return best


def floor_point(B, x: float, y: float, h: float = 0.08) -> np.ndarray:
    o, rd = B.rays(B.C0, B.W, B.H)
    d = rd[int(np.clip(y, 0, B.H - 1)), int(np.clip(x, 0, B.W - 1))]
    return o + d * ((h - o[1]) / d[1])


def ankles(q) -> tuple[float, float] | None:
    q = np.array(q, float)
    if q[10, 2] <= 0.3 or q[13, 2] <= 0.3:
        return None
    return float((q[10, 0] + q[13, 0]) / 2), float(max(q[10, 1], q[13, 1]))


# ---- feet: where Wan put each character -------------------------------------------------------------------------------------------
def feet(a: argparse.Namespace) -> int:
    import e23a_joins as A
    B, _ = _b(E23D)
    kps = {f: json.loads((E23D / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in B.FIGS}
    det: dict = {}
    with A.Session() as x:
        for layer, base in (("M0", M0),):
            for f in B.FIGS:
                rows = []
                for i in range(B.N):
                    rows.append(detect(x.e, B.frames_of(base / f / "chain")[i], np.array(kps[f][i], float)))
                det.setdefault(layer, {})[f] = rows
                log(f"{layer} {B.FIGS[f]}: {sum(r is not None for r in rows)} / {B.N} frames found")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "detected.json").write_text(json.dumps(det), encoding="utf-8")
    offsets = {}
    for f in B.FIGS:
        off = np.full((B.N, 2), np.nan)
        for i in range(B.N):
            st, dt = ankles(kps[f][i]), ankles(det["M0"][f][i]) if det["M0"][f][i] else None
            if st and dt:
                ps, pd = floor_point(B, *st), floor_point(B, *dt)
                off[i] = [pd[0] - ps[0], pd[2] - ps[2]]
        for k in range(2):                                           # gaps filled, a 5-frame median against SDPose's jitter
            col = off[:, k]
            good = ~np.isnan(col)
            col[~good] = np.interp(np.flatnonzero(~good), np.flatnonzero(good), col[good]) if good.any() else 0.0
            off[:, k] = [float(np.median(col[max(0, i - 2):i + 3])) for i in range(B.N)]
        offsets[f] = off.round(4).tolist()
        mag = np.linalg.norm(off, axis=1)
        log(f"{B.FIGS[f]}: the character sits {np.median(mag) * 100:.1f} cm from the dummy (median; 90 % ≤ {np.percentile(mag, 90) * 100:.1f} cm)")
    (OUT / "offsets.json").write_text(json.dumps(offsets), encoding="utf-8")
    s = load_state(); s["offset_cm"] = {B.FIGS[f]: [round(float(np.median(np.linalg.norm(np.array(v), axis=1))) * 100, 1), round(float(np.percentile(np.linalg.norm(np.array(v), axis=1), 90)) * 100, 1)] for f, v in offsets.items()}
    save_state(s)
    return 0


# ---- stage: the moved clays (proxy and dummy) and the proxies' silhouettes ---------------------------------------------------------
def stage(a: argparse.Namespace) -> int:
    offsets = json.loads((OUT / "offsets.json").read_text(encoding="utf-8"))
    for name, with_proxy in (("proxy", True), ("dummy", False)):
        out = OUT / name
        out.mkdir(parents=True, exist_ok=True)
        if not (out / "refs").exists():
            shutil.copytree(E23C / "refs", out / "refs")
        B, _ = _b(out)
        s = B.load_state(); s.setdefault("refs", json.loads((E23C / "state.json").read_text(encoding="utf-8"))["refs"]); B.save_state(s)
        B.OFFSETS, B.PROXYMASK = offsets, with_proxy

        def prepare(api) -> dict:
            return {n: {"shadow_proxy": api("POST", "/assets/import", {"paths": [str(E23D / "meshes" / f"{n.lower()}.glb")]})["items"][0]["id"]} for n in ("Mara", "Ines")}
        B.PREPARE = prepare if with_proxy else None
        if B.stage(a):
            return 1
        log(f"{name}: the moved clay rendered" + (" with the proxies' silhouettes" if with_proxy else ""))
    return 0


# ---- (2) Replace inside the proxy ------------------------------------------------------------------------------------------------
def pmask(f: str, i: int) -> np.ndarray:
    return np.asarray(Image.open(OUT / "proxy" / "stage" / f / "pmask" / f"{i:04d}.png").convert("L")) > 127


def replace(a: argparse.Namespace) -> int:
    import e23a_joins as A
    from e22_layers import sam_text_graph
    B, _ = _b(E23D)
    ros = A.roster()
    plate = [B.arr(p) for p in B.frames_of(E23C / "plate")]
    order = B.order()
    dest = OUT / "runs" / "RP"
    dest.mkdir(parents=True, exist_ok=True)
    s = load_state()
    t0 = time.time()
    with A.Session() as x:
        cur = [p.copy() for p in plate]
        layers = {}
        for li, f in enumerate(order):
            c = B.CAST[B.FIGS[f]]
            region = [B.dilate(pmask(f, i), 4) for i in range(B.N)]
            bd = dest / f"bg_{f}"; bd.mkdir(parents=True, exist_ok=True)
            for i, fr in enumerate(cur):
                b = fr.copy(); b[region[i]] = 0.0                          # Wan 2.2's own replace preprocessing: the region black
                Image.fromarray(np.clip(b, 0, 255).astype(np.uint8)).save(bd / f"{i:04d}.png")
            A.encode(B.frames_of(bd), dest / f"bg_{f}.mp4", B.FPS, crf=12)
            A.encode([np.repeat((m * 255).astype(np.uint8)[..., None], 3, axis=2) for m in region], dest / f"mask_{f}.mp4", B.FPS, crf=0)
            prompt = f"{B.SCENE}. {c['desc'][0].upper() + c['desc'][1:]} {c['act']}. Static camera."
            ref = x.e.upload(A.pad_reference(E23C / "refs" / f"{B.FIGS[f].lower()}.png", OUT / f"{B.FIGS[f].lower()}_padded.png"))
            pose = x.e.upload(E23D / "stage" / f"pose_{f}.mp4")
            layers[f] = B.chain(x, ros, ref, pose, SEED, prompt, dest / f, f"RP_{f}", x.e.upload(dest / f"bg_{f}.mp4"), x.e.upload(dest / f"mask_{f}.mp4"))
            A.encode(B.frames_of(dest / f / "chain"), dest / f"{f}.mp4", B.FPS, crf=12)
            h, _, sam_s = x.e.run(sam_text_graph(ros, x.e.upload(dest / f"{f}.mp4"), "woman:2", f"e23e/sam_{f}"), timeout=1800)
            shutil.rmtree(dest / f / "sam", ignore_errors=True)
            A.download(x.e, h, "99", dest / f / "sam")
            layers[f]["sam_s"] = round(sam_s, 1)
            al_all = []
            for i, p in enumerate(B.frames_of(dest / f / "chain")):
                sam = np.asarray(Image.open(B.frames_of(dest / f / "sam")[i]).convert("L"), dtype=np.float32) / 255.0
                keep = sam * B.dilate(pmask(f, i), 16)
                al = B.soft(keep, 1.2) * B.dilate(keep > 0.5, 3)
                cur[i] = cur[i] * (1 - al[..., None]) + B.arr(p) * al[..., None]
                al_all.append(al.astype(np.float16))
            np.save(dest / f"alpha_{f}.npy", np.stack(al_all))
            log(f"RP {B.FIGS[f]}: {sum(b['exec_s'] for b in layers[f]['batches']):.0f} s + matte {sam_s:.0f} s")
    s["replace"] = {"layers": layers, "wall_min": round((time.time() - t0) / 60, 1), "order": order,
                    "peak_vram_gb": max(b["peak_vram_gb"] for L in layers.values() for b in L["batches"])}
    save_state(s)
    return 0


# ---- the compositions, the gaps, the video --------------------------------------------------------------------------------------
def ratio(stage_dir: Path, f: str, i: int, B) -> np.ndarray:
    a = np.asarray(Image.open(stage_dir / f / "clay" / f"{i:04d}.png").convert("L"), dtype=np.float32)
    b = np.asarray(Image.open(stage_dir / "set" / "clay" / f"{i:04d}.png").convert("L"), dtype=np.float32)
    return np.clip(a / np.maximum(8.0, b), 0.0, 1.0)


def gap(shadow: np.ndarray, own: np.ndarray, feet_xy: tuple[float, float] | None) -> float | None:
    """Pixels from the feet to the nearest pixel of the character's shadow (outside her own matte)."""
    if feet_xy is None:
        return None
    ys, xs = np.nonzero((shadow < 0.85) & ~own)
    if not len(xs):
        return None
    return float(np.min(np.hypot(xs - feet_xy[0], ys - feet_xy[1])))


def score(a: argparse.Namespace) -> int:
    import e23a_joins as A
    import e23d_proxy as D
    from e10_stage import pck
    B, C = _b(E23D)
    kps = {f: json.loads((E23D / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in B.FIGS}
    det = json.loads((OUT / "detected.json").read_text(encoding="utf-8"))
    s = load_state()
    rdir = OUT / "runs" / "RP"
    # SDPose on the Replace layers: their feet, and PCK
    if "RP" not in det:
        with A.Session() as x:
            det["RP"] = {f: [detect(x.e, B.frames_of(rdir / f / "chain")[i], np.array(kps[f][i], float)) for i in range(B.N)] for f in B.FIGS}
        (OUT / "detected.json").write_text(json.dumps(det), encoding="utf-8")
    hits = {f: [0, 0] for f in B.FIGS}
    for f in B.FIGS:
        for i in range(0, B.N, 8):
            q = det["RP"][f][i]
            h_, t_ = pck([kps[f][i]], [{"pose_keypoints_2d": [c for p in q for c in p]}] if q else [])
            hits[f][0] += h_; hits[f][1] += t_
    s["replace_pck"] = {B.FIGS[f]: round(h / t, 3) if t else None for f, (h, t) in hits.items()}
    # the blank left: near-black pixels inside the silhouette that the character's matte does not cover
    left = {}
    for f in B.FIGS:
        al = np.load(rdir / f"alpha_{f}.npy")
        fr = []
        for i in range(0, B.N, 8):
            raw = B.arr(B.frames_of(rdir / f / "chain")[i]).mean(axis=2)
            reg = B.dilate(pmask(f, i), 4)
            fr.append(float(((raw < 25) & reg & (al[i] < 0.5)).sum() / max(1, reg.sum())))
        left[B.FIGS[f]] = round(float(np.mean(fr)), 3)
    s["replace_blank_left"] = left
    # the versions, composed over the plate (shadows first, then the characters far → near)
    plate = [B.arr(p) for p in B.frames_of(E23C / "plate")]
    dist = json.loads((E23D / "stage" / "dist.json").read_text(encoding="utf-8"))
    run = next(r for r in json.loads((E23C / "state.json").read_text(encoding="utf-8"))["runs"] if r["arm"] == "M0" and r["seed"] == SEED)
    m0 = {f: B.kept_mattes(M0, f, 36, json.loads(json.dumps(run["layers"][f]))) for f in B.FIGS}
    m0_alpha = {f: [B.soft(m0[f][i], 1.2) * B.dilate(m0[f][i] > 0.5, 3) for i in range(B.N)] for f in B.FIGS}
    rp_alpha = {f: np.load(rdir / f"alpha_{f}.npy").astype(np.float32) for f in B.FIGS}
    dark = json.loads((E23D / "state.json").read_text(encoding="utf-8")).get("card_darkness", 0.36)

    def feet_of(layer: str, f: str, i: int):
        q = det[layer][f][i]
        return ankles(q) if q else None

    def card_from_feet(f: str, i: int) -> np.ndarray:
        q = det["M0"][f][i]
        kp = q if q else kps[f][i]
        return D.card_shadow(B, C, m0[f][i], kp, dark)
    versions = {
        "MS0": (lambda f, i: D.ratio_from_clay(E23C / "stage", f, i, B), "M0", "the dummy's shadow, unmoved"),
        "MS1": (lambda f, i: ratio(OUT / "dummy" / "stage", f, i, B), "M0", "the dummy's shadow, moved to the feet"),
        "MC1": (card_from_feet, "M0", "the card, cast from the feet"),
        "MP0": (lambda f, i: D.ratio_from_clay(E23D / "stage", f, i, B), "M0", "the proxy's shadow, unmoved"),
        "MP1": (lambda f, i: ratio(OUT / "proxy" / "stage", f, i, B), "M0", "the proxy's shadow, moved to the feet"),
        "RP": (lambda f, i: D.ratio_from_clay(E23D / "stage", f, i, B), "RP", "Replace inside the proxy, its shadow"),
    }
    gaps: dict = {}
    for name, (fn, layer, label) in versions.items():
        d = OUT / "runs" / name / "merged"
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        g_all = {f: [] for f in B.FIGS}
        for i in range(B.N):
            out = plate[i].copy()
            for f in B.FIGS:
                r = fn(f, i)
                own = (m0_alpha[f][i] if layer == "M0" else rp_alpha[f][i]) > 0.3
                r = np.where(own, 1.0, r)
                out *= r[..., None]
                if i % 4 == 0:
                    g = gap(r, own, feet_of(layer, f, i))
                    if g is not None:
                        g_all[f].append(g)
            for f in sorted(B.FIGS, key=lambda x: -dist[min(i, len(dist) - 1)][x]):
                al = m0_alpha[f][i] if layer == "M0" else rp_alpha[f][i]
                src = B.frames_of((M0 if layer == "M0" else rdir) / f / "chain")[i]
                out = out * (1 - al[..., None]) + B.arr(src) * al[..., None]
            Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(d / f"{i:04d}.png")
        gaps[name] = {B.FIGS[f]: [round(float(np.median(v)), 1), round(float(np.percentile(v, 90)), 1)] if v else None for f, v in g_all.items()}
        log(f"{name} ({label}): the gap from the feet to the shadow, median / 90 % (px): {gaps[name]}")
    s["gaps_px"] = gaps
    s["scored_at"] = time.strftime("%Y-%m-%d %H:%M")
    save_state(s)
    # 24 fps (RIFE) and the 2 × 3 compare
    seqs = {}
    for name in versions:
        d = OUT / "runs" / name
        shutil.rmtree(d / "chain", ignore_errors=True); shutil.copytree(d / "merged", d / "chain")
        seqs[name] = A.rife(d, 241)
        shutil.rmtree(d / "chain", ignore_errors=True)
    tw, th = B.W // 2, B.H // 2
    grid = []
    for i in range(min(len(v) for v in seqs.values())):
        im = Image.new("RGB", (tw * 3, th * 2), (0, 0, 0))
        for k, name in enumerate(("MS0", "MS1", "MC1", "MP0", "MP1", "RP")):
            t = Image.open(seqs[name][i]).convert("RGB").resize((tw, th), Image.LANCZOS)
            im.paste(A.label(t, f"{versions[name][2]} · {i / 24:.2f} s"), ((k % 3) * tw, (k // 3) * th))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    log(f"PCK (Replace) {s['replace_pck']}, blank left {s['replace_blank_left']}; compare: {OUT / 'compare.mp4'}")
    return 0


def shift(a: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """An image (H × W or H × W × C) moved by (dx, dy) pixels, bilinear, the edges empty."""
    chans = a[..., None] if a.ndim == 2 else a
    out = np.stack([np.asarray(Image.fromarray(chans[..., c].astype(np.float32), mode="F").transform(
        (chans.shape[1], chans.shape[0]), Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR, fillcolor=0.0)) for c in range(chans.shape[2])], axis=-1)
    return out[..., 0] if a.ndim == 2 else out


def soles(m: np.ndarray) -> tuple[float, float] | None:
    """Where a figure's feet meet the floor in the frame: the lowest row of its mask, and the middle of the mask's pixels in the lowest 4 %
    of its height."""
    ys, xs = np.nonzero(m)
    if len(ys) < 50:
        return None
    top, bot = ys.min(), ys.max()
    low = ys >= bot - 0.04 * (bot - top)
    return float(np.median(xs[low])), float(bot)


def nudge(a: argparse.Namespace) -> int:
    """The author's idea (journal 23:20): leave the shadow where Stage cast it and move the character instead — a layer offset in the
    frame, so her feet stand on the dummy's (the shadow's start). Two ways: **constant**, one offset per character for the shot (a hand's
    nudge), and **per frame** (her detected feet, a 9-frame median). With the dummy's and the proxy's unmoved shadows."""
    import e23a_joins as A
    import e23d_proxy as D
    B, _ = _b(E23D)
    kps = {f: json.loads((E23D / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in B.FIGS}
    det = json.loads((OUT / "detected.json").read_text(encoding="utf-8"))
    s = load_state()
    run0 = next(r for r in json.loads((E23C / "state.json").read_text(encoding="utf-8"))["runs"] if r["arm"] == "M0" and r["seed"] == SEED)
    mat0 = {f: B.kept_mattes(M0, f, 36, json.loads(json.dumps(run0["layers"][f]))) for f in B.FIGS}
    off: dict = {}
    for f in B.FIGS:
        # her soles against the dummy's: the ankles agree within a couple of pixels, but her shoes reach lower and further than the dummy's
        # thin feet, and the shadow starts where the dummy's soles touch the floor (journal 23:25)
        v = np.full((B.N, 2), np.nan)
        for i in range(B.N):
            a_, b_ = soles(mat0[f][i] > 0.5), soles(B.stage_mask(f, i))
            if a_ and b_:
                v[i] = [b_[0] - a_[0], b_[1] - a_[1]]                 # the move that puts her soles on the dummy's
        for k in range(2):
            col = v[:, k]; good = ~np.isnan(col)
            col[~good] = np.interp(np.flatnonzero(~good), np.flatnonzero(good), col[good])
        per = np.array([np.median(v[max(0, i - 4):i + 5], axis=0) for i in range(B.N)])
        const = np.median(v, axis=0)
        off[f] = {"constant": const, "per_frame": per}
        log(f"{B.FIGS[f]}: the constant nudge {const[0]:+.1f} px across, {const[1]:+.1f} px down ("
            f"{'right' if const[0] > 0 else 'left'} and {'down' if const[1] > 0 else 'up'}); per frame {np.percentile(np.linalg.norm(per - const, axis=1), 90):.1f} px from it (90 %)")
    s["nudge_px"] = {B.FIGS[f]: [round(float(o["constant"][0]), 1), round(float(o["constant"][1]), 1)] for f, o in off.items()}
    plate = [B.arr(p) for p in B.frames_of(E23C / "plate")]
    dist = json.loads((E23D / "stage" / "dist.json").read_text(encoding="utf-8"))
    run = next(r for r in json.loads((E23C / "state.json").read_text(encoding="utf-8"))["runs"] if r["arm"] == "M0" and r["seed"] == SEED)
    m0 = {f: B.kept_mattes(M0, f, 36, json.loads(json.dumps(run["layers"][f]))) for f in B.FIGS}
    shadows = {"MS": lambda f, i: D.ratio_from_clay(E23C / "stage", f, i, B), "MP": lambda f, i: D.ratio_from_clay(E23D / "stage", f, i, B)}
    gaps: dict = {}
    for sname, sfn in shadows.items():
        for mode in ("constant", "per_frame"):
            name = f"{sname}_{'nc' if mode == 'constant' else 'nf'}"
            d = OUT / "runs" / name / "merged"
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            g_all = {f: [] for f in B.FIGS}
            for i in range(B.N):
                moved = {}
                for f in B.FIGS:
                    dx, dy = (off[f][mode] if mode == "constant" else off[f][mode][i])
                    al = B.soft(m0[f][i], 1.2) * B.dilate(m0[f][i] > 0.5, 3)
                    moved[f] = (shift(B.arr(B.frames_of(M0 / f / "chain")[i]), dx, dy), np.clip(shift(al, dx, dy), 0, 1), dx, dy)
                out = plate[i].copy()
                for f in B.FIGS:
                    own = moved[f][1] > 0.3
                    r = np.where(own, 1.0, sfn(f, i))
                    out *= r[..., None]
                    q = det["M0"][f][i]
                    if i % 4 == 0 and q:
                        ft = ankles(q)
                        g = gap(r, own, (ft[0] + moved[f][2], ft[1] + moved[f][3]) if ft else None)
                        if g is not None:
                            g_all[f].append(g)
                for f in sorted(B.FIGS, key=lambda x: -dist[min(i, len(dist) - 1)][x]):
                    img, al = moved[f][0], moved[f][1]
                    out = out * (1 - al[..., None]) + img * al[..., None]
                Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(d / f"{i:04d}.png")
            gaps[name] = {B.FIGS[f]: [round(float(np.median(v)), 1), round(float(np.percentile(v, 90)), 1)] if v else None for f, v in g_all.items()}
            log(f"{name}: the gap from the feet to the shadow, median / 90 % (px): {gaps[name]}")
    s["nudge_gaps_px"] = gaps
    save_state(s)
    # the compare: the proxy's shadow — before | nudged (constant) | nudged (per frame); the dummy's below
    seqs = {}
    for name in ("MP0", "MP_nc", "MP_nf", "MS0", "MS_nc", "MS_nf"):
        dd = OUT / "runs" / name
        shutil.rmtree(dd / "chain", ignore_errors=True); shutil.copytree(dd / "merged", dd / "chain")
        seqs[name] = A.rife(dd, 241)
        shutil.rmtree(dd / "chain", ignore_errors=True)
    labels = {"MP0": "the mesh's shadow, as before", "MP_nc": "the character nudged (one offset)", "MP_nf": "the character nudged (per frame)",
              "MS0": "the dummy's shadow, as before", "MS_nc": "the character nudged (one offset)", "MS_nf": "the character nudged (per frame)"}
    tw, th = B.W // 2, B.H // 2
    grid = []
    for i in range(min(len(v) for v in seqs.values())):
        im = Image.new("RGB", (tw * 3, th * 2), (0, 0, 0))
        for k, name in enumerate(("MP0", "MP_nc", "MP_nf", "MS0", "MS_nc", "MS_nf")):
            t = Image.open(seqs[name][i]).convert("RGB").resize((tw, th), Image.LANCZOS)
            im.paste(A.label(t, f"{labels[name]} · {i / 24:.2f} s"), ((k % 3) * tw, (k // 3) * th))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "nudge.mp4", 24, crf=16)
    log(f"nudge: {OUT / 'nudge.mp4'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["feet", "stage", "replace", "score", "nudge"])
    a = ap.parse_args()
    return {"feet": feet, "stage": stage, "replace": replace, "score": score, "nudge": nudge}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
