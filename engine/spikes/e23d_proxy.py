"""Spike E23d (proto01_animate 02 §3; the author's idea after D105): a dummy shaped like its character, so Stage's shadows get the
character's outline — "it doesn't have to be perfect, just a dummy to cast close enough shadows".

E23c's shot (locked camera, the window light, the fitted bodies, M0's character layers, seeds 20261021–22). The shadows on the plate:

  MS   Stage's shadow of the dummy (E23c)
  MP   Stage's shadow of a **proxy**: a mesh made from the character's animation reference by the app's image → mesh job (Pixal3D, D84),
       bound to the figure's twelve joints in the reference's A-pose (each vertex to its nearest segments, weighted by distance) — it
       follows every pose, it is seen only by the light (a layer the cameras do not render), and the dummy casts nothing
  MC   a **shadow card**: the character's own matte (M0's SAM 3 matte, every frame) stood up on a vertical card through the figure's feet,
       facing the camera, its shadow cast by the same light onto the floor (numpy; no GPU)
  MW   the white set's generated shadow (E23c), the character's real outline drawn by the model

Measured: each method's shadow mask against MW's (IoU, and the area ratio), the proxy's fit (its silhouette in the clay against the
character's matte), time; for the author: compare.mp4 (MS | MP | MC | MW, seed 20261021) and a proxy check image.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e23d_proxy.py meshes   # the two meshes through the app (GPU, one job at a time)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23d_proxy.py stage    # the proxies bound in Stage (visible Edge, Vite on 1420)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23d_proxy.py shadows  # MC and the compositions (CPU)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23d_proxy.py score
Outputs under engine/spikes/out/e23d/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e23d"
E23C = ROOT / "engine" / "spikes" / "out" / "e23c"
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
CAST = {"Mara": "mara.png", "Ines": "ines.png"}


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def meshes(a: argparse.Namespace) -> int:
    from loom2.config import AppState
    from m1_acceptance import Orch, port_busy
    if port_busy(8188):
        print("the engine port is busy — one GPU job at a time"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "meshes").mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-e23d-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": 8188}})
    o = Orch(tmp / "state", 8790).start()
    s = load_state()
    try:
        assert o.http.post("/project", json={"path": str(tmp / "proj"), "name": "E23d", "size_cap_gb": 20}).status_code == 200
        for name, file in CAST.items():
            src = o.http.post("/assets/import", json={"paths": [str(E23C / "refs" / file)]}).json()["items"][0]["id"]
            t0 = time.time()
            jid = o.http.post("/jobs", json={"recipe": {"kind": "image_to_mesh", "asset_id": src}}).json()["jobs"][0]["id"]
            while True:
                j = next((x for x in o.http.get("/jobs").json()["items"] if x["id"] == jid), None)
                if j and j["status"] in ("done", "failed", "cancelled"):
                    break
                time.sleep(2)
            if j["status"] != "done":
                print(name, j["status"], j.get("error")); return 1
            aid = j["result"]["asset_ids"][0]
            (OUT / "meshes" / f"{name.lower()}.glb").write_bytes(o.http.get(f"/assets/{aid}/file", timeout=120).content)
            s.setdefault("meshes", {})[name] = {"wall_s": round(time.time() - t0, 1), "job_wall_s": j.get("wall_s"),
                                                "bytes": (OUT / "meshes" / f"{name.lower()}.glb").stat().st_size}
            log(f"{name}: mesh in {time.time() - t0:.0f} s ({s['meshes'][name]['bytes'] / 2**20:.1f} MiB)")
            save_state(s)
    finally:
        try:
            o.http.post("/engine/stop", timeout=120); o.http.post("/shutdown", timeout=30)
        except Exception:
            pass
        time.sleep(2)
        if o.proc and o.proc.poll() is None:
            o.proc.kill()
    return 0


def _b():
    """e23b_layers set up for E23d: its own folder, E23c's locked camera, light and fitted bodies, the lit clay."""
    os.environ["LOOM2_E23B_OUT"] = str(OUT)
    os.environ["LOOM2_E23B_BODIES"] = str(E23C / "bodies.json")
    import e23b_layers as B
    import e23c_white as C
    B.C1 = B.C0
    B.WITH_CLAY = True
    B.EXTRA_OBJECTS = [C.LIGHT]
    return B, C


def stage(a: argparse.Namespace) -> int:
    B, _ = _b()
    if not (OUT / "refs").exists():
        import shutil
        shutil.copytree(E23C / "refs", OUT / "refs")
    s = load_state(); s.setdefault("refs", json.loads((E23C / "state.json").read_text(encoding="utf-8"))["refs"]); save_state(s)

    def prepare(api) -> dict:
        out = {}
        for name in CAST:
            aid = api("POST", "/assets/import", {"paths": [str(OUT / "meshes" / f"{name.lower()}.glb")]})["items"][0]["id"]
            out[name] = {"shadow_proxy": aid}
        return out
    B.PREPARE = prepare
    return B.stage(a)


def ratio_from_clay(stage_dir: Path, fid: str, i: int, B) -> np.ndarray:
    a = np.asarray(Image.open(stage_dir / fid / "clay" / f"{i:04d}.png").convert("L"), dtype=np.float32)
    b = np.asarray(Image.open(stage_dir / "set" / "clay" / f"{i:04d}.png").convert("L"), dtype=np.float32)
    r = np.clip(a / np.maximum(8.0, b), 0.0, 1.0)
    r[B.dilate(B.stage_mask(fid, i), 2)] = 1.0
    return r


def card_shadow(B, C, matte: np.ndarray, kp: list, darkness: float) -> np.ndarray:
    """MC: the character's matte (as the camera sees it) on a vertical card through its feet, turned to face the window light, scaled so
    the matte's height is the figure's; each floor pixel traced back along the light onto the card — inside the matte, it is in shadow
    (no holes: every floor pixel is decided). A card facing the camera would stand edge-on to this side light (its shadow a line)."""
    b = np.array(kp, float)
    if len(b) < 14 or b[10, 2] <= 0 or b[13, 2] <= 0 or matte.max() < 0.5:
        return np.ones_like(matte)
    cam = B.C0
    o, rd = B.rays(cam, B.W, B.H)
    # the feet: the ankles' midpoint ray onto the floor (the ankle ≈ 8 cm up)
    ax, ay = (b[10, 0] + b[13, 0]) / 2, (b[10, 1] + b[13, 1]) / 2
    d0 = rd[int(np.clip(ay, 0, B.H - 1)), int(np.clip(ax, 0, B.W - 1))]
    F = o + d0 * ((0.08 - o[1]) / d0[1])
    F[1] = 0.0
    L = np.array(C.LIGHT["transform"]["pos"], float)
    d = np.array([0.0, 1.0, 0.0]) - L; d /= np.linalg.norm(d)               # the key light's direction (engine.syncLight: towards (0, 1, 0))
    m = np.array([d[0], 0.0, d[2]]); m /= np.linalg.norm(m)                  # the card's normal: the light's way, level
    h = np.cross([0.0, 1.0, 0.0], m)                                        # the card's horizontal axis
    # the matte's own frame: its box in the picture, its height the figure's (the stature, from the body's height)
    ys, xs = np.nonzero(matte > 0.5)
    y_top, y_bot, cx = float(ys.min()), float(ys.max()), float(np.median(xs))
    k = (y_bot - y_top) / 1.70                                               # pixels per metre on the card
    with np.errstate(divide="ignore", invalid="ignore"):
        tf = -o[1] / rd[..., 1]
    floor = (tf > 0) & np.isfinite(tf)
    G = o + rd * np.where(floor, tf, 0)[..., None]
    sv = ((G - F) @ m) / float(d @ m)                                       # back along the light onto the card
    Q = G - sv[..., None] * d
    ok = floor & (sv > 0) & (Q[..., 1] > 0)
    u = cx - ((Q - F) @ h) * k                                              # the card's coordinates → the matte's pixels
    v = y_bot - Q[..., 1] * k
    inside = ok & (u >= 0) & (u < B.W - 1) & (v >= 0) & (v < B.H - 1)
    alpha = np.zeros_like(matte)
    alpha[inside] = matte[v[inside].astype(int), u[inside].astype(int)]
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.5)), dtype=np.float32) / 255.0
    r = 1 - darkness * alpha
    r[matte > 0.3] = 1.0
    return r


def shadows(a: argparse.Namespace) -> int:
    """The four shadow sources for E23c's M0 layers (seed 20261021): MS (the dummy, E23c's clay), MP (the proxy, E23d's clay), MC (the
    card), MW (E23c's white set, its extracted ratios); each composited over the plate with M0's characters."""
    import shutil
    B, C = _b()
    seed = 20261021
    src = E23C / "runs" / f"M0_s{seed}"
    s_c = json.loads((E23C / "state.json").read_text(encoding="utf-8"))
    run = next(r for r in s_c["runs"] if r["arm"] == "M0" and r["seed"] == seed)
    kps = {f: json.loads((OUT / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in B.FIGS}
    mw = np.load(E23C / "runs" / f"MW_s{seed}" / "shadow.npz")
    plate = [B.arr(p) for p in B.frames_of(E23C / "plate")]
    sams = {f: B.kept_mattes(src, f, 36, json.loads(json.dumps(run["layers"][f]))) for f in B.FIGS}
    dist = json.loads((OUT / "stage" / "dist.json").read_text(encoding="utf-8"))
    # the card's darkness: the dummy's shadow's own (MS) median, so MC differs from MS in shape only
    ms0 = np.concatenate([ratio_from_clay(E23C / "stage", f, i, B)[ratio_from_clay(E23C / "stage", f, i, B) < 0.9] for f in B.FIGS for i in range(0, B.N, 20)])
    dark = float(1 - np.median(ms0)) if ms0.size else 0.4
    src_of = {"MS": lambda f, i: ratio_from_clay(E23C / "stage", f, i, B), "MP": lambda f, i: ratio_from_clay(OUT / "stage", f, i, B),
              "MC": lambda f, i: card_shadow(B, C, sams[f][i], kps[f][i], dark), "MW": lambda f, i: mw[f][i].astype(np.float32) / 255.0}
    s = load_state(); s["card_darkness"] = round(dark, 3)
    masks = {}
    for arm, fn in src_of.items():
        d = OUT / "runs" / arm / "merged"
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        masks[arm] = {f: [] for f in B.FIGS}
        for i in range(B.N):
            out = plate[i].copy()
            for f in B.FIGS:
                r = fn(f, i)
                out *= r[..., None]
                masks[arm][f].append(r < 0.85)
            for f in sorted(B.FIGS, key=lambda x: -dist[min(i, len(dist) - 1)][x]):
                al = B.soft(sams[f][i], 1.2) * B.dilate(sams[f][i] > 0.5, 3)
                out = out * (1 - al[..., None]) + B.arr(B.frames_of(src / f / "chain")[i]) * al[..., None]
            Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(d / f"{i:04d}.png")
        np.savez_compressed(OUT / "runs" / arm / "masks.npz", **{f: np.stack(v) for f, v in masks[arm].items()})
        log(f"{arm}: composed")
    save_state(s)
    return 0


def score(a: argparse.Namespace) -> int:
    """Each Stage-light shadow (MS, MP, MC) against the white set's (MW, the character's real outline): IoU and the area ratio over the
    frames, per character, in the floor region around the figure; the compare video and the proxy check."""
    import shutil
    import e23a_joins as A
    B, _ = _b()
    m = {arm: np.load(OUT / "runs" / arm / "masks.npz") for arm in ("MS", "MP", "MC", "MW")}
    rows = {}
    for arm in ("MS", "MP", "MC"):
        for f, name in B.FIGS.items():
            ious, areas = [], []
            for i in range(0, B.N, 4):
                region = B.dilate(B.stage_mask(f, i), 160) & ~B.dilate(B.stage_mask(f, i), 3)
                x, w = m[arm][f][i] & region, m["MW"][f][i] & region
                if w.sum() > 50:
                    ious.append((x & w).sum() / max(1, (x | w).sum()))
                    areas.append(x.sum() / w.sum())
            rows[f"{arm} {name}"] = {"iou_vs_white_set": round(float(np.mean(ious)), 3) if ious else None,
                                     "area_vs_white_set": round(float(np.median(areas)), 2) if areas else None}
            log(f"{arm} {name}: {rows[f'{arm} {name}']}")
    s = load_state(); s["scores"] = rows; s["scored_at"] = time.strftime("%Y-%m-%d %H:%M"); save_state(s)
    # 24 fps (RIFE) and the 2 × 2 compare
    seqs = {}
    for arm in ("MS", "MP", "MC", "MW"):
        d = OUT / "runs" / arm
        shutil.rmtree(d / "chain", ignore_errors=True); shutil.copytree(d / "merged", d / "chain")
        seqs[arm] = A.rife(d, 241)
        shutil.rmtree(d / "chain", ignore_errors=True)
    names = {"MS": "Stage: the dummy's shadow", "MP": "Stage: the character-shaped proxy", "MC": "the character's matte on a card", "MW": "the white set: the model's shadow"}
    tw, th = B.W // 2, B.H // 2
    grid = []
    for i in range(min(len(v) for v in seqs.values())):
        im = Image.new("RGB", (tw * 2, th * 2), (0, 0, 0))
        for k, arm in enumerate(("MS", "MP", "MC", "MW")):
            t = Image.open(seqs[arm][i]).convert("RGB").resize((tw, th), Image.LANCZOS)
            im.paste(A.label(t, f"{names[arm]} · {i / 24:.2f} s"), ((k % 2) * tw, (k // 2) * th))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    # the proxy check: what the light sees (the proxy in clay) beside the character, three frames each
    sheet = Image.new("RGB", (B.W, B.H), (20, 20, 20))
    for r_, f in enumerate(B.FIGS):
        for c_, i in enumerate((0, 80, 160)):
            p = OUT / "stage" / f / "proxy" / f"{i:04d}.png"
            if p.is_file():
                sheet.paste(Image.open(p).convert("RGB").resize((B.W // 3, B.H // 2)), (c_ * B.W // 3, r_ * B.H // 2))
    sheet.save(OUT / "proxy_check.jpg", quality=90)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["meshes", "stage", "shadows", "score"])
    a = ap.parse_args()
    return {"meshes": meshes, "stage": stage, "shadows": shadows, "score": score}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
