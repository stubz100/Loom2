"""E40 (post-MVP item 5, 03 §5 item 5, 04 §4): SeedVR2 3B as the "add real detail" upscaler, measured on this card against Real-ESRGAN.

The pinned ComfyUI's own SeedVR2 nodes (comfy_extras/nodes_seedvr.py, no custom node): the engine venv's template graph
(utility_seedvr2_3b_int8_upscale_image.json) — a Lanczos resize by the factor → SeedVR2Preprocess → VAEEncodeTiled 512/128 →
SeedVR2Conditioning → a one-step KSampler (euler / simple, cfg 1, denoise 1) → VAEDecodeTiled → SeedVR2PostProcessing (the colour
match) — on the bench's Draft boards (bench/i2v/frames, 960×544) at ×2 (1920×1088, the FHD tier) and ×4, with the 3B in int8 convrot
and in fp8, against Real-ESRGAN ×2 / ×4 through the same engine. Measured: seconds (the first run of a weight cold), the peak VRAM, a
detail measure (the Laplacian variance of the result, as a ratio to ESRGAN's at the same factor), the colour drift (mean ΔE in Lab
against the Lanczos resize) and a sheet of 1:1 crops for the author's eye. Then a Wan clip at ×2 through the video path
(SeedVR2TemporalChunk auto) for the Full tier's frame upscale.

Bars (set before the run, journal E40): ×2 warm ≤ 60 s and peak ≤ 15.5 GB; sharper than ESRGAN (Laplacian ratio > 1) with ΔE ≤ 3 under
the lab match; ×4 fits or is said not to; the clip at ×2 ends inside 10 min. Kill: ×2 over 120 s warm or out of memory.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e40_seedvr2.py [--images alley-rain,fish-market,portrait-grief | --all]
        [--weights int8,fp8] [--factors 2,4] [--x4-images 2] [--color lab] [--clip PATH | --no-clip] [--clip-weight int8]

The engine is started by the script as the orchestrator starts it (python -m loom2.engine.supervisor --argv) and stopped at the end; the
port must be free (one GPU job at a time, rule 10). Results: engine/spikes/out/e40/results.json, sheet_x2.jpg, sheet_x4.jpg, sheet_clip.jpg,
clip_x2.mp4 and every full-size output beside them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]

ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "e40"
FRAMES = ROOT / "bench" / "i2v" / "frames"
WEIGHTS = {"int8": "seedvr2_3b_int8_convrot.safetensors", "fp8": "seedvr2_3b_fp8_e4m3fn.safetensors"}
VAE = "seedvr2_ema_vae_fp16.safetensors"
ESRGAN = {2: "RealESRGAN_x2.pth", 4: "RealESRGAN_x4.pth"}
BAR_WARM_S, BAR_PEAK_GB, BAR_DE, BAR_CLIP_S, KILL_S = 60.0, 15.5, 3.0, 600.0, 120.0
CROP = 384


def engine_get(path: str):
    with urllib.request.urlopen(f"http://{ENGINE}{path}", timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def launch_engine(log) -> tuple[subprocess.Popen, dict]:
    """The engine as the orchestrator launches it (the same flags, mounts and output folder), started here and stopped by the caller."""
    out = subprocess.check_output([sys.executable, "-m", "loom2.engine.supervisor", "--argv"], cwd=str(ROOT / "orchestrator"), text=True, encoding="utf-8")
    launch = json.loads(out)
    proc = subprocess.Popen(launch["argv"], cwd=launch["cwd"], env={**os.environ, **launch["env"]}, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 240:
        if proc.poll() is not None:
            raise RuntimeError(f"the engine exited with {proc.returncode} (see {OUT / 'engine.log'})")
        try:
            engine_get("/system_stats")
            return proc, launch
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("the engine did not come up")


def stop_engine(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except Exception:  # noqa: BLE001
        proc.kill()


# ---- the graphs (API format) ----
def tiled(tile: int = 512, overlap: int = 128, temporal: int = 4096, toverlap: int = 8) -> dict:
    return {"tile_size": tile, "overlap": overlap, "temporal_size": temporal, "temporal_overlap": toverlap}


def seedvr2_graph(image_name: str, weight: str, factor: int, color: str, prefix: str, seed: int = 1) -> dict:
    return {
        "100": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "101": {"class_type": "ImageScaleBy", "inputs": {"image": ["100", 0], "upscale_method": "lanczos", "scale_by": float(factor)}},
        "102": {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["101", 0]}},
        "103": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "104": {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["102", 0], "vae": ["103", 0], **tiled()}},
        "105": {"class_type": "UNETLoader", "inputs": {"unet_name": weight, "weight_dtype": "default"}},
        "106": {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["105", 0], "vae_conditioning": ["104", 0]}},
        "107": {"class_type": "KSampler", "inputs": {"model": ["105", 0], "seed": seed, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["106", 0], "negative": ["106", 1], "latent_image": ["104", 0], "denoise": 1.0}},
        "108": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["107", 0], "vae": ["103", 0], **tiled()}},
        "109": {"class_type": "SeedVR2PostProcessing", "inputs": {"images": ["108", 0], "original_resized_images": ["101", 0], "color_correction_method": color}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["109", 0], "filename_prefix": prefix}},
    }


def esrgan_graph(image_name: str, factor: int, prefix: str) -> dict:
    return {
        "100": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "101": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": ESRGAN[factor]}},
        "102": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["101", 0], "image": ["100", 0]}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["102", 0], "filename_prefix": prefix}},
    }


def clip_graph(video_name: str, weight: str, factor: int, color: str, prefix: str, seed: int = 1) -> dict:
    return {
        "100": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "101": {"class_type": "GetVideoComponents", "inputs": {"video": ["100", 0]}},
        "102": {"class_type": "ImageScaleBy", "inputs": {"image": ["101", 0], "upscale_method": "lanczos", "scale_by": float(factor)}},
        "103": {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["102", 0]}},
        "104": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "105": {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["103", 0], "vae": ["104", 0], **tiled(temporal=64)}},
        "106": {"class_type": "UNETLoader", "inputs": {"unet_name": weight, "weight_dtype": "default"}},
        "110": {"class_type": "SeedVR2TemporalChunk", "inputs": {"latent": ["105", 0], "temporal_overlap": 0, "chunking_mode": "auto"}},
        "107": {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["106", 0], "vae_conditioning": ["110", 0]}},
        "108": {"class_type": "KSampler", "inputs": {"model": ["106", 0], "seed": seed, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["107", 0], "negative": ["107", 1], "latent_image": ["110", 0], "denoise": 1.0}},
        "111": {"class_type": "SeedVR2TemporalMerge", "inputs": {"latents": ["108", 0], "temporal_overlap": ["110", 1]}},
        "109": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["111", 0], "vae": ["104", 0], **tiled(temporal=64)}},
        "112": {"class_type": "SeedVR2PostProcessing", "inputs": {"images": ["109", 0], "original_resized_images": ["102", 0], "color_correction_method": color}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["112", 0], "filename_prefix": prefix}},
    }


# ---- the measures ----
def gray(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("L"), dtype=np.float64)


def lap_var(im: Image.Image) -> float:
    g = gray(im)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return round(float(lap.var()), 1)


def to_lab(im: Image.Image) -> np.ndarray:
    rgb = np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.LANCZOS)
    return round(float(np.linalg.norm(to_lab(a) - to_lab(b), axis=-1).mean()), 2)


def crop_at(im: Image.Image, rel: tuple[float, float] = (0.62, 0.38)) -> Image.Image:
    x = int(min(max(im.width * rel[0] - CROP / 2, 0), im.width - CROP)); y = int(min(max(im.height * rel[1] - CROP / 2, 0), im.height - CROP))
    return im.crop((x, y, x + CROP, y + CROP))


def sheet(rows: list[list[tuple[str, Image.Image]]], path: Path) -> None:
    cols = max(len(r) for r in rows)
    im = Image.new("RGB", (cols * (CROP + 6), len(rows) * (CROP + 20)), (24, 24, 24))
    dr = ImageDraw.Draw(im)
    for r, row in enumerate(rows):
        for c, (lbl, tile) in enumerate(row):
            x, y = c * (CROP + 6), r * (CROP + 20)
            im.paste(tile, (x, y + 18)); dr.text((x + 3, y + 3), lbl, fill=(230, 230, 230))
    im.save(path, quality=90)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="alley-rain,fish-market,portrait-grief")
    ap.add_argument("--all", action="store_true", help="every board under bench/i2v/frames")
    ap.add_argument("--weights", default="int8,fp8")
    ap.add_argument("--factors", default="2,4")
    ap.add_argument("--x4-images", type=int, default=2, help="how many of the boards go through ×4 (the fit check)")
    ap.add_argument("--color", default="lab", choices=["lab", "wavelet", "adain", "none"])
    ap.add_argument("--clip", default=str(ROOT / "engine" / "spikes" / "out" / "a1" / "final.mp4"))
    ap.add_argument("--no-clip", action="store_true")
    ap.add_argument("--clip-weight", default="", help="the weight for the clip (default: the faster of the two that met the bars)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="results.json", help="the results file under engine/spikes/out/e40/ (the sheets take its stem as a suffix)")
    a = ap.parse_args()
    import cr_acceptance as cr
    from e12_angles import Engine
    from m1_acceptance import port_busy
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    names = sorted(p.stem.split("_s")[0] for p in FRAMES.glob("*.png")) if a.all else [s.strip() for s in a.images.split(",") if s.strip()]
    boards = {n: next(FRAMES.glob(f"{n}_s*.png")) for n in names}
    weights = [w.strip() for w in a.weights.split(",") if w.strip()]
    factors = [int(f) for f in a.factors.split(",")]
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "boards": names, "weights": weights, "factors": factors, "color": a.color, "runs": [], "failures": [], "notes": []}
    suffix = "" if a.out == "results.json" else "_" + Path(a.out).stem
    log = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    def save() -> None:
        (OUT / a.out).write_text(json.dumps(results, indent=1), encoding="utf-8")

    clip = Path(a.clip) if not a.no_clip and Path(a.clip).exists() else None
    vname = f"e40_{clip.stem}.mp4" if clip else ""
    if clip:                                                            # into the engine's input folder before it starts: LoadVideo lists the folder
        import shutil
        (ROOT / "engine" / "comfyui" / "input").mkdir(exist_ok=True)
        shutil.copyfile(clip, ROOT / "engine" / "comfyui" / "input" / vname)
    try:
        proc, launch = launch_engine(log)
        out_dir = Path(launch["argv"][launch["argv"].index("--output-directory") + 1])
        eng = Engine(ENGINE)
        vram = cr.VramSampler()
        uploaded = {n: eng.upload(p) for n, p in boards.items()}
        outputs: dict[tuple[str, str, int], Image.Image] = {}

        def run(label: str, graph: dict, key: tuple[str, str, int], extra: dict) -> dict:
            free0 = cr.vram_free_gb() if hasattr(cr, "vram_free_gb") else None
            vram.mark()
            t0 = time.time()
            try:
                h, wall, exec_s = eng.run(graph, timeout=1800)
                msgs = {m[0]: m[1] for m in h["status"].get("messages", [])}
                err = (msgs.get("execution_error") or {}).get("exception_message")
                im = eng.image(h, "99") if not err and h["outputs"].get("99", {}).get("images") else None
            except Exception as e:  # noqa: BLE001
                wall, exec_s, err, im = time.time() - t0, None, f"{type(e).__name__}: {e}"[:300], None
            peak = vram.window()
            row = {"label": label, **extra, "exec_s": round(exec_s, 1) if exec_s else None, "wall_s": round(wall, 1), "peak_gb": peak, "vram_free_before_gb": free0,
                   "out_size": list(im.size) if im else None, "lap_var": lap_var(im) if im else None, "error": err}
            if im is not None:
                outputs[key] = im
                im.save(OUT / f"{key[0]}_{key[1]}_x{key[2]}.png")
            results["runs"].append(row)
            print(f"{label}: {'error ' + err if err else f'{row['exec_s']} s exec / {row['wall_s']} s wall · {im.size if im else None} · lap {row['lap_var']}'} · peak {peak} GB", flush=True)
            save()
            return row

        # ESRGAN: the baseline at both factors, every board
        for f in factors:
            for n in names:
                run(f"esrgan ×{f} {n}", esrgan_graph(uploaded[n], f, f"e40/esrgan-x{f}-{n}"), (n, "esrgan", f), {"board": n, "method": "esrgan", "factor": f})
        # SeedVR2: a weight at ×2 on every board (the first cold), then ×4 on the first boards; a kill stops a weight
        for w in weights:
            dead = False
            for f in factors:
                for i, n in enumerate(names):
                    if dead or (f == 4 and i >= a.x4_images):
                        continue
                    row = run(f"seedvr2 {w} ×{f} {n}", seedvr2_graph(uploaded[n], WEIGHTS[w], f, a.color, f"e40/seedvr2-{w}-x{f}-{n}", a.seed), (n, w, f),
                              {"board": n, "method": f"seedvr2-{w}", "factor": f, "color": a.color})
                    if f == 2 and row["error"] and ("memory" in row["error"].lower() or "oom" in row["error"].lower()):
                        results["notes"].append(f"{w} ×2 out of memory on {n}: the weight is out (kill)"); dead = True
                    if f == 2 and i > 0 and row["wall_s"] > KILL_S and not row["error"]:
                        results["notes"].append(f"{w} ×2 warm {row['wall_s']} s over the kill line {KILL_S:g} s"); dead = True
            # the colour drift without the match, one board
            if not dead and names:
                n = names[0]
                run(f"seedvr2 {w} ×2 {n} (no colour match)", seedvr2_graph(uploaded[n], WEIGHTS[w], 2, "none", f"e40/seedvr2-{w}-x2-{n}-nomatch", a.seed), (n, f"{w}-nomatch", 2),
                    {"board": n, "method": f"seedvr2-{w}", "factor": 2, "color": "none"})

        # the measures against ESRGAN and the Lanczos resize
        for row in results["runs"]:
            n, f = row["board"], row["factor"]
            key = (n, row["method"].replace("seedvr2-", "") + ("-nomatch" if row.get("color") == "none" else ""), f)
            im = outputs.get(key)
            if im is None:
                continue
            src = Image.open(boards[n]).convert("RGB")
            lanczos = src.resize((src.width * f, src.height * f), Image.Resampling.LANCZOS)
            row["delta_e_vs_lanczos"] = delta_e(im, lanczos)
            base = outputs.get((n, "esrgan", f))
            row["lap_ratio_vs_esrgan"] = round(row["lap_var"] / lap_var(base), 2) if base is not None and row["lap_var"] else None
        save()

        # the sheets: a row per board, the Lanczos resize, ESRGAN and every weight, 1:1 crops
        for f in factors:
            rows = []
            for n in names:
                src = Image.open(boards[n]).convert("RGB")
                lanczos = src.resize((src.width * f, src.height * f), Image.Resampling.LANCZOS)
                row = [(f"{n} · lanczos ×{f}", crop_at(lanczos))]
                for m in ["esrgan", *weights]:
                    im = outputs.get((n, m, f))
                    r = next((x for x in results["runs"] if x["board"] == n and x["factor"] == f and x["method"] == ("esrgan" if m == "esrgan" else f"seedvr2-{m}") and x.get("color") != "none"), None)
                    if im is not None and r:
                        row.append((f"{m} · {r['exec_s']} s · lap {r.get('lap_ratio_vs_esrgan') or 1.0}× · ΔE {r.get('delta_e_vs_lanczos')}", crop_at(im)))
                rows.append(row)
            if rows:
                sheet(rows, OUT / f"sheet_x{f}{suffix}.jpg")

        # the bars on the boards
        for w in weights:
            x2 = [r for r in results["runs"] if r["method"] == f"seedvr2-{w}" and r["factor"] == 2 and r.get("color") != "none"]
            ok_runs = [r for r in x2 if not r["error"]]
            warm = [r["wall_s"] for r in ok_runs[1:]]
            check(bool(ok_runs) and len(ok_runs) == len(x2), f"{w}: every ×2 board done ({len(ok_runs)}/{len(x2)}; {[r['error'] for r in x2 if r['error']]})")
            check(bool(warm) and max(warm) <= BAR_WARM_S, f"{w}: ×2 warm ≤ {BAR_WARM_S:g} s (warm {warm}, the first {ok_runs[0]['wall_s'] if ok_runs else None} s cold)")
            check(bool(ok_runs) and max(r["peak_gb"] for r in ok_runs) <= BAR_PEAK_GB, f"{w}: ×2 peak ≤ {BAR_PEAK_GB} GB ({[r['peak_gb'] for r in ok_runs]})")
            ratios = [r.get("lap_ratio_vs_esrgan") for r in ok_runs if r.get("lap_ratio_vs_esrgan")]
            check(bool(ratios) and min(ratios) > 1.0, f"{w}: sharper than ESRGAN at ×2 on every board (Laplacian ratios {ratios})")
            des = [r.get("delta_e_vs_lanczos") for r in ok_runs if r.get("delta_e_vs_lanczos") is not None]
            check(bool(des) and max(des) <= BAR_DE, f"{w}: colour drift ΔE ≤ {BAR_DE:g} under the {a.color} match ({des})")
            x4 = [r for r in results["runs"] if r["method"] == f"seedvr2-{w}" and r["factor"] == 4]
            results["notes"].append(f"{w} ×4: " + ("; ".join(f"{r['board']} {'error ' + r['error'][:80] if r['error'] else f'{r['wall_s']} s, peak {r['peak_gb']} GB'}" for r in x4) or "not run"))

        # the clip: the faster weight that met its bars (or --clip-weight), ×2 through the video path
        if clip:
            met = [w for w in weights if not any(w + ":" in f for f in results["failures"])]
            cw = a.clip_weight or (min(met, key=lambda w: min(r["wall_s"] for r in results["runs"] if r["method"] == f"seedvr2-{w}" and r["factor"] == 2 and not r["error"])) if met else None)
            if cw:
                import av
                c = av.open(a.clip); s = c.streams.video[0]
                fps, nframes, cw_, ch_ = float(s.average_rate), s.frames, s.width, s.height
                c.close()
                prefix = f"e40/clip-{cw}-x2/f"
                row = run(f"clip {cw} ×2 ({cw_}×{ch_} × {nframes} at {fps:g} fps)", clip_graph(vname, WEIGHTS[cw], 2, a.color, prefix, a.seed), ("clip", cw, 2),
                          {"board": "clip", "method": f"seedvr2-{cw}", "factor": 2, "color": a.color, "clip": a.clip, "frames_in": nframes, "fps": fps})
                frames = sorted((out_dir / f"e40/clip-{cw}-x2").glob("*.png"))
                row["frames_out"] = len(frames)
                check(not row["error"] and len(frames) >= nframes, f"the clip at ×2: {len(frames)} frames of {nframes} ({row['error'] or 'ok'})")
                check(row["wall_s"] <= BAR_CLIP_S, f"the clip at ×2 inside {BAR_CLIP_S:g} s ({row['wall_s']} s, peak {row['peak_gb']} GB)")
                if frames:
                    # a sheet (first / middle / last frame: the Lanczos resize against SeedVR2) and the clip itself for the author
                    c = av.open(a.clip)
                    src_frames = [fr.to_image() for fr in c.decode(video=0)]
                    c.close()
                    rows = []
                    for idx in sorted({0, len(frames) // 2, len(frames) - 1}):
                        s_im = src_frames[min(idx, len(src_frames) - 1)]
                        lanczos = s_im.resize((s_im.width * 2, s_im.height * 2), Image.Resampling.LANCZOS)
                        o_im = Image.open(frames[idx]).convert("RGB")
                        rows.append([(f"frame {idx} · lanczos ×2", crop_at(lanczos, (0.5, 0.4))), (f"seedvr2 {cw} ×2 · ΔE {delta_e(o_im, lanczos)}", crop_at(o_im, (0.5, 0.4)))])
                    sheet(rows, OUT / f"sheet_clip{suffix}.jpg")
                    with av.open(str(OUT / "clip_x2.mp4"), "w") as oc:
                        first = Image.open(frames[0])
                        st = oc.add_stream("libx264", rate=int(round(fps)) or 16)
                        st.width, st.height, st.pix_fmt = first.width - first.width % 2, first.height - first.height % 2, "yuv420p"
                        for p in frames:
                            fr = av.VideoFrame.from_image(Image.open(p).convert("RGB").crop((0, 0, st.width, st.height)))
                            for pkt in st.encode(fr):
                                oc.mux(pkt)
                        for pkt in st.encode():
                            oc.mux(pkt)
                save()
            else:
                results["notes"].append("the clip was not run: no weight met its bars")
        save()
        print(f"{len(results['failures'])} failure(s) → {OUT / a.out}; notes: {results['notes']}", flush=True)
        return 1 if results["failures"] else 0
    finally:
        try:
            vram.stop = True
        except Exception:  # noqa: BLE001
            pass
        stop_engine(proc)
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
