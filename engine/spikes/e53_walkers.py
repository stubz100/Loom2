"""Spike E53 (the author: walkers painted into person-sized places in front of the counters; journal 2026-10-31 17:21): on E47's copy, the
right stall front 3.2–8.8 m (752 × 672), through the app's own routes, two seeds — the crop as a document, its selection three boxes the
size of a person standing on the face's base, Klein's Fill paints a shopper in each (prompt first); the start flattened; the plain Wan 2.2
loop from it back to it (tone-locked on copies, as the product does); the matte (matte_sequence on the clip, SAM 3 "person:20"); a filter
judging whole people (the quarter grid closed before it is labelled); the walkers packed over the static face and mapped onto Final 5's plate.
Outputs under engine/spikes/out/e53/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e53_walkers.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e49_crowd as e  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e53"
FROM_M, TO_M = 3.2, 8.8
SEEDS = (53, 54)
BOX_M = (0.75, 1.9)                               # a person's place: width, height
BOX_AT = (0.18, 0.50, 0.82)
PAINT = "a shopper walking in profile, the whole figure from head to feet, carrying a basket, standing on the floor in front of the fish counter"
F5 = "fin_d5ce3248"


def closed_walkers(masks: list[np.ndarray], px_per_m: float, foot: float = 0.85, tallest_m: float = 2.34, step: int = 4) -> tuple[list[np.ndarray], list[int]]:
    """D174's filter judging whole people: the quarter grid closed by a cell (a person's pieces join) before it is labelled; feet in the
    bottom 15 %, no taller than `tallest_m`, or overlapping a kept part on the frame before."""
    out, counts, prev = [], [], None
    for m in masks:
        small = m[::step, ::step] > 0.5
        closed = small.copy()
        closed[1:] |= small[:-1]; closed[:-1] |= small[1:]; closed[:, 1:] |= small[:, :-1]; closed[:, :-1] |= small[:, 1:]
        h, w = closed.shape
        seen = np.zeros_like(closed, bool)
        keep = np.zeros_like(closed, bool)
        n = 0
        for y0, x0 in zip(*np.nonzero(closed)):
            if seen[y0, x0]:
                continue
            comp, dq = [], deque([(y0, x0)])
            seen[y0, x0] = True
            while dq:
                y, x = dq.popleft()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and closed[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        dq.append((yy, xx))
            ys = [c[0] for c in comp]
            tall = (max(ys) - min(ys) + 1) * step
            if tall <= tallest_m * px_per_m and (max(ys) >= foot * (h - 1) or (prev is not None and any(prev[c] for c in comp))):
                for c in comp:
                    keep[c] = True
                n += 1
        keep &= small | keep                                                  # the closing's ring stays out
        prev = keep
        big = np.repeat(np.repeat(keep, step, 0), step, 1)[: m.shape[0], : m.shape[1]]
        out.append(m * big)
        counts.append(n)
    return out, counts


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.engine.tone import lock_loop
    from loom2.models import registry
    from loom2.place_sets import CROWD_FPS, CROWD_FRAMES, WALKER_MOTION, crowd_size
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(e.PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(e.PROJECT)
    cat = Catalogue(ws)
    face = next(f for f in StoryStore(ws).profile(e.PID).version(e.VID).place_set.faces if f.id == e.FACE)
    tex = Image.open(cat.abs_path(cat.get(face.texture_asset_id))).convert("RGB")
    height_m = tex.height * face.texel_m
    w, h = crowd_size(TO_M - FROM_M, height_m)
    px_m = h / height_m
    crop = tex.crop((round(FROM_M / face.texel_m), 0, round(TO_M / face.texel_m), tex.height)).resize((w, h), Image.Resampling.LANCZOS)
    crop.save(OUT / "crop.png")
    sel = np.zeros((h, w), np.uint8)
    bw, bh = round(BOX_M[0] * px_m), round(BOX_M[1] * px_m)
    for a in BOX_AT:
        x0 = round(a * w - bw / 2)
        sel[h - 4 - bh:h - 4, max(0, x0):min(w, x0 + bw)] = 255
    Image.fromarray(sel).save(OUT / "selection.png")
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "size": [w, h], "px_per_m": round(px_m, 2), "arms": {}}
    api = httpx.Client(base_url=f"http://127.0.0.1:{e.PORT}", headers={"X-Loom-Token": e.TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(e.PORT), "--state",
                             str(e.STATE), "--project", str(e.PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": e.TOKEN}, stdout=log, stderr=subprocess.STDOUT)

    def run(recipe: dict, label: str) -> dict:
        t0 = time.time()
        r = api.post("/jobs", json={"recipe": recipe})
        r.raise_for_status()
        jid = r.json()["jobs"][0]["id"]
        while True:
            j = api.get(f"/jobs/{jid}").json()
            if j["status"] not in ("queued", "running", "staged"):
                break
            time.sleep(4)
        print(f"{label}: {j['status']} in {round(time.time() - t0)} s {j.get('error') or ''}", flush=True)
        if j["status"] != "done":
            raise RuntimeError(f"{label}: {j.get('error')}")
        return {"seconds": round(time.time() - t0), "result": j.get("result") or {}}

    data: dict[int, dict] = {}
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        crop_id = api.post("/assets/import", json={"paths": [str(OUT / "crop.png")]}).json()["items"][0]["id"]
        model = registry.default_model("i2v", "full")
        for seed in SEEDS:
            arm: dict = {}
            doc = api.post("/documents", json={"from_asset": crop_id, "name": f"E53 {seed}"}).json()["id"]
            r = api.put(f"/documents/{doc}/selection", params={"w": w, "h": h}, content=sel.tobytes())
            r.raise_for_status()
            s = run({"kind": "inpaint", "mode": "fill", "document_id": doc, "prompt_text": PAINT, "prompt_mode": "prompt_first", "feather": 4, "seeds": [seed]}, f"paint {seed}")
            r = api.post(f"/documents/{doc}/flatten", json={"to_catalogue": True, "name": f"E53 start {seed}"})
            r.raise_for_status()
            start = r.json()["asset"]["id"]
            st = Image.open(cat.abs_path(cat.get(start))).convert("RGB").resize((w, h))
            st.save(OUT / f"start_{seed}.png")
            outside = np.asarray(sel) == 0
            arm["paint_s"] = s["seconds"]
            arm["outside_mae"] = round(float(np.abs(np.asarray(st, dtype=np.float64) - np.asarray(crop, dtype=np.float64))[outside].mean()), 2)
            c = run({"kind": "i2v", "model_id": model, "start_asset": start, "end_asset": start, "prompt_text": WALKER_MOTION + "; a static locked-off camera.",
                     "frames": CROWD_FRAMES, "fps": CROWD_FPS, "width": w, "height": h, "preset": "draft", "seeds": [seed]}, f"loop {seed}")
            clip_id = c["result"]["clip_id"]
            arm["loop_s"] = c["seconds"]
            rec = json.loads((e.PROJECT / "clips" / clip_id / "clip.json").read_text(encoding="utf-8"))
            d = OUT / f"loop_{seed}"
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir()
            paths = []
            for p in sorted((e.PROJECT / rec["master_dir"]).glob("*.png")):
                shutil.copyfile(p, d / p.name)
                paths.append(d / p.name)
            arm["lock"] = lock_loop(paths)
            mt = run({"kind": "matte_sequence", "clip_id": clip_id, "mode": "text", "text": "person:20", "threshold": 0.4}, f"matte {seed}")
            arm["matte_s"] = mt["seconds"]
            masks = [np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0 for p in sorted((e.PROJECT / "clips" / clip_id / "matte").glob("*.png"))]
            frames = [np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) for p in paths]
            arm["drift"] = e.measure([Image.open(p).convert("RGB") for p in paths])
            data[seed] = {"frames": frames, "masks": masks}
            results["arms"][str(seed)] = arm
            print(f"seed {seed}:", json.dumps(arm), flush=True)
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    plate_dir = e.PROJECT / "finals" / F5 / "plate" / "frames"
    n = len(sorted(plate_dir.glob("*.png")))
    W_face, H_face = round(tex.width * face.texel_m * px_m), round(height_m * px_m)
    bg = np.asarray(tex.resize((W_face, H_face), Image.Resampling.BICUBIC), dtype=np.float32)
    bh_ = int(480 * e.MATCH["band"])
    v, u = np.mgrid[0:bh_, 0:848].astype(np.float64)
    for seed, dd in data.items():
        kept, counts = closed_walkers(dd["masks"], px_m)
        results["arms"][str(seed)]["kept_counts"] = {"min": int(min(counts)), "median": int(np.median(counts)), "max": int(max(counts))}
        sheet = Image.new("RGB", (w * 3, (h // 2 + 16) * 3), (20, 20, 20))
        dr = ImageDraw.Draw(sheet)
        for r_, k in enumerate((0, 40, 70)):
            fr = dd["frames"][k]
            cut = fr * kept[k][..., None] + 30 * (1 - kept[k][..., None])
            for c_, im in enumerate((fr, np.repeat(dd["masks"][k][..., None] * 255, 3, 2), cut)):
                sheet.paste(Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).resize((w // 2 * 2 // 2, h // 2)), (c_ * w, r_ * (h // 2 + 16) + 16))
            dr.text((4, r_ * (h // 2 + 16) + 2), f"seed {seed} · frame {k}: the loop · SAM 3 · the walkers kept ({counts[k]})", fill=(230, 230, 230))
        sheet.save(OUT / f"walkers_{seed}.jpg", quality=86)
        pv = []
        x_at = round(FROM_M * px_m)
        for k in range(n):
            plate = np.asarray(Image.open(plate_dir / f"{k:04d}.png").convert("RGB")).copy()
            f = bg.copy()
            i = k % (len(dd["frames"]) - 1)
            a = kept[i][..., None]
            region = f[:h, x_at:x_at + w]
            f[:h, x_at:x_at + w] = region * (1 - a) + dd["frames"][i] * a
            x0 = e.MATCH["x0"] + (e.MATCH["x64"] - e.MATCH["x0"]) * k / max(1, n - 1)
            tx, ty = x0 + e.MATCH["s"] * u, e.MATCH["y"] + e.MATCH["s"] * v
            fx = np.clip((tx * face.texel_m * px_m).round().astype(int), 0, W_face - 1)
            fy = np.clip((ty * face.texel_m * px_m).round().astype(int), 0, H_face - 1)
            plate[:bh_] = np.clip(f[fy, fx], 0, 255).astype(np.uint8)
            pv.append(Image.fromarray(plate))
        for k in (5, 32, 60):
            pv[k].save(OUT / f"plate_{seed}_{k}.png")
        import av
        with av.open(str(OUT / f"plate_{seed}.mp4"), "w", format="mp4") as cont:
            s_ = cont.add_stream("libx264", rate=16)
            s_.width, s_.height, s_.pix_fmt = 848, 480, "yuv420p"
            s_.options = {"crf": "18"}
            for im in pv:
                for pkt in s_.encode(av.VideoFrame.from_image(im)):
                    cont.mux(pkt)
            for pkt in s_.encode():
                cont.mux(pkt)
    starts = Image.new("RGB", (w * 3, h), (20, 20, 20))
    starts.paste(crop, (0, 0))
    for i, seed in enumerate(SEEDS):
        if (OUT / f"start_{seed}.png").is_file():
            starts.paste(Image.open(OUT / f"start_{seed}.png"), (w * (i + 1), 0))
    starts.resize((w * 3 // 2, h // 2)).save(OUT / "starts.jpg", quality=86)
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results["arms"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
