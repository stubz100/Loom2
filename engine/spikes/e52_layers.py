"""Spike E52 (the author: a static background and a crowd of people only on a layer; journal 2026-10-31 16:43): E51's two good loops
(C 41, CM 42, their tone-locked frames) matted by SAM 3 "person" through the app's own graph on the spike's engine, then laid as people-only
segments on E47's copy's static right stall front (its texture under D170) — S2: two loops side by side with a gap; S1: one loop tiled,
the second mirrored and 40 frames later — each segment's alpha faded over its outer 0.3 m, mapped onto Final 5's plate (E49's match).
Measured: the mattes' flicker and soft edge; frames 5, 32, 60 and a video beside E50's (c). Outputs under engine/spikes/out/e52/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e52_layers.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e49_crowd as e  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e52"
E51 = ROOT / "engine" / "spikes" / "out" / "e51"
LOOPS = {"C41": E51 / "C_41", "CM42": E51 / "CM_42"}
LOOP_M = (3.2, 14.4)                              # the loops' stretch on the face (E51)
PX_M = 1088 / (LOOP_M[1] - LOOP_M[0])             # the loops' density, px a metre
FADE_M = 0.3
THRESH = 0.4
TEXT = "person:20"                                # E52: SAM 3 keeps one detection a prompt unless the words say how many (comfy sam3_clip `:N`)
F5 = "fin_d5ce3248"
E50C = "fin_817396d7"                             # E50's (c): D173's whole-stretch clip, for the eye


def matte(loops: dict[str, Path]) -> dict[str, list[np.ndarray]]:
    """SAM 3 by "person" on every frame of each loop (the app's MatteSequence graph), masks as float 0–1 at the loop's size."""
    from e12_angles import Engine
    from e40_seedvr2 import launch_engine, stop_engine
    from m1_acceptance import port_busy
    from loom2.config import AppState
    from loom2.engine.graphs import build_matte_sequence
    from loom2.recipes import MatteSequence, matte_mode
    from loom2.roster import Roster
    from loom2.stages import encode_guide
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    app = AppState()
    roster = Roster(app.models_root, [Path(x) for x in app.settings.mounted_model_trees], app.settings.variant).scan()
    out: dict[str, list[np.ndarray]] = {}
    log = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None
    try:
        proc, launch = launch_engine(log)
        out_dir = Path(launch["argv"][launch["argv"].index("--output-directory") + 1])
        eng = Engine("127.0.0.1:8188")
        for key, d in loops.items():
            frames = sorted(d.glob("*.png"))
            clip = OUT / f"{key}.mp4"
            encode_guide(frames, clip, 16)
            r = httpx.post("http://127.0.0.1:8188/upload/image", files={"image": (clip.name, clip.read_bytes(), "video/mp4")}, data={"overwrite": "true", "type": "input"}, timeout=120)
            r.raise_for_status()
            j = r.json()
            name = (j.get("subfolder") + "/" if j.get("subfolder") else "") + j["name"]
            prefix = f"e52/{key.lower()}/m"
            shutil.rmtree(out_dir / "e52" / key.lower(), ignore_errors=True)
            comp = build_matte_sequence(MatteSequence(final_id="e52", layer_id=key, mode=matte_mode(app.settings.variant), text=TEXT, threshold=THRESH), roster, name, prefix)
            t0 = time.time()
            eng.run(comp.graph, timeout=1800)
            masks = sorted((out_dir / "e52" / key.lower()).glob("m*.png"))
            size = Image.open(frames[0]).size
            out[key] = [np.asarray(Image.open(p).convert("L").resize(size, Image.BILINEAR), dtype=np.float32) / 255.0 for p in masks[: len(frames)]]
            print(f"matte {key}: {len(masks)} masks in {round(time.time() - t0)} s", flush=True)
    finally:
        if proc is not None:
            stop_engine(proc)
    return out


def grounded(m: np.ndarray, foot: float = 0.9, step: int = 4) -> np.ndarray:
    """E52: only the people standing on the ground line — a mask's connected parts (on a quarter-size grid) whose lowest row reaches `foot`
    of the frame's height; the ones behind a counter or deep in the hall stop higher and are dropped."""
    from collections import deque
    small = m[::step, ::step] > 0.5
    h, w = small.shape
    seen = np.zeros_like(small, bool)
    keep = np.zeros_like(small, bool)
    for y0, x0 in zip(*np.nonzero(small)):
        if seen[y0, x0]:
            continue
        comp, q = [], deque([(y0, x0)])
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            comp.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and small[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    q.append((yy, xx))
        if max(c[0] for c in comp) >= foot * (h - 1):
            for c in comp:
                keep[c] = True
    big = np.repeat(np.repeat(keep, step, 0), step, 1)[: m.shape[0], : m.shape[1]]
    grow = big.copy()                                                     # the quarter grid's cells, a cell wider, so no edge is cut
    grow[1:] |= big[:-1]; grow[:-1] |= big[1:]; grow[:, 1:] |= big[:, :-1]; grow[:, :-1] |= big[:, 1:]
    return m * grow


def main() -> int:
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / f"masks_{TEXT.replace(':', '_')}_{THRESH}.npz"
    if cache.is_file():
        z = np.load(cache)
        masks = {k: list(z[k]) for k in LOOPS}
    else:
        masks = matte(LOOPS)
        np.savez_compressed(cache, **{k: np.stack(v) for k, v in masks.items()})
    rgb = {k: [np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) for p in sorted(d.glob("*.png"))] for k, d in LOOPS.items()}
    masks = {**masks, **{f"{k}g": [grounded(m) for m in ms] for k, ms in masks.items()}}     # E52: the walkers only
    rgb = {**rgb, **{f"{k}g": v for k, v in rgb.items()}}
    res: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "mattes": {}}
    for k, ms in masks.items():
        a = np.stack(ms)
        res["mattes"][k] = {"frames": len(ms), "coverage": round(float(a.mean()), 4), "soft_share": round(float(((a > 0.1) & (a < 0.9)).mean() / max(1e-6, (a > 0.1).mean())), 3),
                            "flicker": round(float(np.abs(np.diff(a, axis=0)).mean()), 4)}
    print("mattes:", json.dumps(res["mattes"]), flush=True)
    ws = Workspace(e.PROJECT)
    cat = Catalogue(ws)
    face = next(f for f in StoryStore(ws).profile(e.PID).version(e.VID).place_set.faces if f.id == e.FACE)
    tex = Image.open(cat.abs_path(cat.get(face.texture_asset_id))).convert("RGB")
    face_w_m, face_h_m = tex.width * face.texel_m, tex.height * face.texel_m
    W, H = round(face_w_m * PX_M), round(face_h_m * PX_M)
    bg = np.asarray(tex.resize((W, H), Image.Resampling.BICUBIC), dtype=np.float32)
    lh, lw = rgb["C41"][0].shape[:2]

    def segment(key: str, start: int, at_m: float, k: int, shift: int = 0, mirror: bool = False) -> tuple[np.ndarray, np.ndarray, int, int]:
        n = len(rgb[key]) - 1                                                   # the loop: the last frame is the first
        i = (k + shift) % n
        x0, x1 = start, min(lw, start + lw // 2)                                # half a loop, where its people are (the masks' columns)
        c, a = rgb[key][i][:, x0:x1], masks[key][i][:, x0:x1].copy()
        if mirror:
            c, a = c[:, ::-1], a[:, ::-1]
        fade = int(FADE_M * PX_M)
        ramp = np.ones(a.shape[1], np.float32)
        ramp[:fade] = np.linspace(0, 1, fade)
        ramp[-fade:] = np.linspace(1, 0, fade)
        a = a * ramp[None, :]
        return c, a, round(at_m * PX_M), round(((at_m * PX_M) / PX_M) * 0 + (H - lh) / 2)    # vertically centred (the loop is the face's full height)

    rich = {}
    for key, ms in masks.items():                                               # each loop's half with the most people in it
        col = np.stack(ms).mean(axis=(0, 1))
        rich[key] = int(np.argmax(np.convolve(col, np.ones(lw // 2), "valid")))
    res["windows_px"] = rich
    layouts = {
        "S2": [("C41", rich["C41"], 3.0, 0, False), ("CM42", rich["CM42"], 9.2, 0, False)],
        "S1": [("C41", rich["C41"], 3.0, 0, False), ("C41", rich["C41"], 9.2, 40, True)],
        "S2g": [("C41g", rich["C41g"], 3.0, 0, False), ("CM42g", rich["CM42g"], 9.2, 0, False)],   # the walkers only
    }

    def face_at(layout: str, k: int) -> np.ndarray:
        f = bg.copy()
        for key, half, at, shift, mirror in layouts[layout]:
            c, a, x, y = segment(key, half, at, k, shift, mirror)
            h_, w_ = a.shape
            x = max(0, min(W - w_, x)); y = max(0, min(H - h_, y))
            region = f[y:y + h_, x:x + w_]
            f[y:y + h_, x:x + w_] = region * (1 - a[..., None]) + c * a[..., None]
        return f

    plate_dir = e.PROJECT / "finals" / F5 / "plate" / "frames"
    n = len(sorted(plate_dir.glob("*.png")))
    bh = int(480 * e.MATCH["band"])
    v, u = np.mgrid[0:bh, 0:848].astype(np.float64)
    previews: dict[str, list[Image.Image]] = {}
    for layout in layouts:
        frames_out = []
        for k in range(n):
            plate = np.asarray(Image.open(plate_dir / f"{k:04d}.png").convert("RGB")).copy()
            x0 = e.MATCH["x0"] + (e.MATCH["x64"] - e.MATCH["x0"]) * k / max(1, n - 1)
            tx, ty = x0 + e.MATCH["s"] * u, e.MATCH["y"] + e.MATCH["s"] * v          # texels of the face
            fx = np.clip((tx * face.texel_m * PX_M).round().astype(int), 0, W - 1)
            fy = np.clip((ty * face.texel_m * PX_M).round().astype(int), 0, H - 1)
            fc = face_at(layout, k)
            plate[:bh] = np.clip(fc[fy, fx], 0, 255).astype(np.uint8)
            frames_out.append(Image.fromarray(plate))
        previews[layout] = frames_out
        Image.fromarray(np.clip(face_at(layout, 0), 0, 255).astype(np.uint8)).save(OUT / f"face_{layout}_0.jpg", quality=88)
    previews["E50 (c)"] = [Image.open(e.PROJECT / "finals" / E50C / "plate" / "frames" / f"{k:04d}.png").convert("RGB") for k in range(n)]
    import av
    with av.open(str(OUT / "compare.mp4"), "w", format="mp4") as cont:
        st = cont.add_stream("libx264", rate=16)
        st.width, st.height, st.pix_fmt = 848, 480 * 3, "yuv420p"
        st.options = {"crf": "20"}
        for k in range(n):
            canvas = Image.new("RGB", (848, 480 * 3))
            d2 = ImageDraw.Draw(canvas)
            for r_, name in enumerate(("S2", "S2g", "E50 (c)")):
                canvas.paste(previews[name][k], (0, r_ * 480))
                d2.text((8, r_ * 480 + 6), {"S2": "S2: two loops, every person cut out", "S2g": "S2g: the walkers only (feet on the ground line)", "E50 (c)": "E50 (c): D173's whole-stretch clip"}[name], fill=(255, 255, 255))
            for pkt in st.encode(av.VideoFrame.from_image(canvas)):
                cont.mux(pkt)
        for pkt in st.encode():
            cont.mux(pkt)
    sheet = Image.new("RGB", (424 * 3, (240 + 18) * 3), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for r_, k in enumerate((5, 32, 60)):
        for c_, name in enumerate(("S2", "S2g", "E50 (c)")):
            sheet.paste(previews[name][k].resize((424, 240)), (c_ * 424, r_ * 258 + 18))
            dr.text((c_ * 424 + 4, r_ * 258 + 3), f"{name} · frame {k}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=88)
    for k in (5, 32, 60):
        previews["S2"][k].save(OUT / f"S2_{k}.png")
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
