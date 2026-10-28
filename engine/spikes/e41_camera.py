"""E41 (post-MVP item 6, 04 §5 — E4b's open end): camera control for Wan 2.2 clips on this card — Wan 2.2 Fun-Camera (Alibaba PAI, Apache-2.0;
Comfy-Org's fp8-scaled experts) on the pinned ComfyUI's own `WanCameraEmbedding` + `WanCameraImageToVideo`, against the plain I2V model with
the move asked for in the prompt (E4b's baseline).

The graph is the app's Wan 2.2 Draft graph (Lightning 2 + 2, cfg 1, shift 5, 832×480 × 81) with two nodes swapped: the camera embedding and
the camera conditioning. The bench's alley board is the start image (a street with depth). Each clip is read back from its frames: the global
translation of every second frame pair by phase correlation (the pan — its direction, its size as a share of the width, how many pairs agree),
the zoom as the scale that best maps the first frame onto the last (a scan of 0.6–1.6 about the centre), the first frame's distance from the
start image (the subject kept), the seconds and the peak VRAM. Sheets of first / middle / last frames and the clips are written for the author.

Bars (journal E41, set before the run): every clip done; peak ≤ 15.5 GB; a warm clip ≤ 240 s; the pans move the right way by ≥ 5 % of the
width with ≥ 70 % of the pairs agreeing; the zooms reach ≥ 1.15 (in) / ≤ 0.87 (out); Static within 1 % and 3 % of scale; the first frame
within MAE 12 of the start image. Content moves opposite to the camera: Pan Left (the camera goes left) shifts the picture to the right.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e41_camera.py [--moves "Pan Left,Pan Right,Zoom In,Zoom Out,Static"] [--speed 1.0]
        [--no-baseline] [--seed 20261028] [--out results.json]

The engine is started by the script as the orchestrator starts it and stopped at the end (one GPU job at a time, rule 10).
Results: engine/spikes/out/e41/<out>, sheet.jpg, <run>.mp4, the frames under the engine's output folder.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]

ENGINE = "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "e41"
BOARD = next((ROOT / "bench" / "i2v" / "frames").glob("alley-rain_s*.png"))
W, H, FRAMES, FPS = 832, 480, 81, 16
CAMERA = {"high": "wan2.2_fun_camera_high_noise_14B_fp8_scaled.safetensors", "low": "wan2.2_fun_camera_low_noise_14B_fp8_scaled.safetensors"}
PROMPT_STILL = "she stands still in the light rain holding the brass compass, looking at the viewer, neon signs flicker, rain falls softly"
PROMPT_BASELINE = {"Pan Left": "the camera pans slowly to the left across the alley; " + PROMPT_STILL, "Zoom In": "a slow dolly push-in toward her; " + PROMPT_STILL}
BAR_PEAK_GB, BAR_WARM_S, BAR_PAN_SHARE, BAR_PAN_AGREE, BAR_ZOOM_IN, BAR_ZOOM_OUT, BAR_STATIC_SHARE, BAR_STATIC_ZOOM, BAR_FIRST_MAE = 15.5, 240.0, 0.05, 0.7, 1.15, 0.87, 0.01, 0.03, 12.0
EXPECT = {"Pan Left": ("pan", +1), "Pan Right": ("pan", -1), "Pan Up": ("tilt", +1), "Pan Down": ("tilt", -1), "Zoom In": ("zoom", +1), "Zoom Out": ("zoom", -1), "Static": ("static", 0)}


# ---- the graph: the app's Wan 2.2 Draft graph, the camera nodes swapped in ----
def wan_graph(names: dict[str, str], start_name: str, prompt: str, negative: str, seed: int, prefix: str, camera: str | None, speed: float, lora: bool = True) -> dict:
    """With `lora` the Draft recipe (Lightning 2 + 2, cfg 1, shift 5); without it the Quality recipe (10 + 10, cfg 3.5, shift 8) — the tone question."""
    steps, split, cfg, shift = (4, 2, 1.0, 5.0) if lora else (20, 10, 3.5, 8.0)
    g: dict = {
        "100": {"class_type": "LoadImage", "inputs": {"image": start_name}},
        "101": {"class_type": "ImageScale", "inputs": {"image": ["100", 0], "upscale_method": "lanczos", "width": W, "height": H, "crop": "center"}},
        "1h": {"class_type": "UNETLoader", "inputs": {"unet_name": names["high"], "weight_dtype": "default"}},
        "1l": {"class_type": "UNETLoader", "inputs": {"unet_name": names["low"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": names["te"], "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": names["vae"]}},
        "4h": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1h", 0], "lora_name": names["lora_high"], "strength_model": 0.7}},
        "4l": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1l", 0], "lora_name": names["lora_low"], "strength_model": 1.0}},
        "8h": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4h", 0] if lora else ["1h", 0], "shift": shift}},
        "8l": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4l", 0] if lora else ["1l", 0], "shift": shift}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["2", 0]}},
    }
    cond: dict = {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": W, "height": H, "length": FRAMES, "batch_size": 1, "start_image": ["101", 0]}
    if camera:
        g["20"] = {"class_type": "WanCameraEmbedding", "inputs": {"camera_pose": camera, "width": W, "height": H, "length": FRAMES, "speed": float(speed)}}
        cond["camera_conditions"] = ["20", 0]
        g["7"] = {"class_type": "WanCameraImageToVideo", "inputs": cond}
    else:
        g["7"] = {"class_type": "WanImageToVideo", "inputs": cond}
    g["9"] = {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8h", 0], "add_noise": "enable", "noise_seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple",
                                                          "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["7", 2], "start_at_step": 0, "end_at_step": split, "return_with_leftover_noise": "enable"}}
    g["10"] = {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8l", 0], "add_noise": "disable", "noise_seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple",
                                                           "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["9", 0], "start_at_step": split, "end_at_step": 10000, "return_with_leftover_noise": "disable"}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": prefix}}
    return g


# ---- the measures ----
def small_gray(im: Image.Image) -> np.ndarray:
    """A 416×240 grayscale, mean removed, Hann-windowed — what the phase correlation and the zoom scan see."""
    g = np.asarray(im.convert("L").resize((W // 2, H // 2), Image.Resampling.BOX), dtype=np.float64)
    g -= g.mean()
    wy = np.hanning(g.shape[0])[:, None]; wx = np.hanning(g.shape[1])[None, :]
    return g * wy * wx


def shift_between(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """(dx, dy) in half-resolution pixels such that b ≈ a moved by (dx, dy): the content's move between the two frames (phase correlation)."""
    F, G = np.fft.fft2(a), np.fft.fft2(b)
    R = G * np.conj(F)
    R /= np.abs(R) + 1e-9
    r = np.fft.ifft2(R).real
    iy, ix = np.unravel_index(int(np.argmax(r)), r.shape)
    h, w = r.shape
    dy = iy if iy <= h // 2 else iy - h
    dx = ix if ix <= w // 2 else ix - w
    return float(dx), float(dy)


def zoom_between(first: Image.Image, last: Image.Image) -> float:
    """The scale s (0.6–1.6) that best maps the first frame, zoomed about its centre, onto the last — a zoom in reads > 1."""
    base = first.convert("L").resize((W // 2, H // 2), Image.Resampling.BOX)
    tgt = np.asarray(last.convert("L").resize((W // 2, H // 2), Image.Resampling.BOX), dtype=np.float64)
    w, h = base.size
    cx, cy, rw, rh = w // 2, h // 2, int(w * 0.3), int(h * 0.3)                # the central 60 %: what every scale keeps in frame
    t = tgt[cy - rh:cy + rh, cx - rw:cx + rw]; t = (t - t.mean()) / (t.std() + 1e-6)
    best, best_s = -2.0, 1.0
    for s in np.linspace(0.6, 1.6, 51):
        zw, zh = max(8, int(round(w * s))), max(8, int(round(h * s)))
        z = base.resize((zw, zh), Image.Resampling.BILINEAR)
        za = np.asarray(z, dtype=np.float64)
        zcx, zcy = zw // 2, zh // 2
        if zcx - rw < 0 or zcy - rh < 0 or zcx + rw > zw or zcy + rh > zh:
            continue
        c = za[zcy - rh:zcy + rh, zcx - rw:zcx + rw]; c = (c - c.mean()) / (c.std() + 1e-6)
        ncc = float((c * t).mean())
        if ncc > best:
            best, best_s = ncc, float(s)
    return round(best_s, 3)


def measure(frames: list[Path], start: Image.Image) -> dict:
    ims = [Image.open(p).convert("RGB") for p in frames]
    g = [small_gray(im) for im in ims[::2]]
    shifts = [shift_between(g[i], g[i + 1]) for i in range(len(g) - 1)]
    dx = np.array([s[0] for s in shifts]); dy = np.array([s[1] for s in shifts])
    cum_x, cum_y = float(dx.sum()), float(dy.sum())
    moving = np.abs(dx) >= 0.5
    agree_x = float((np.sign(dx[moving]) == np.sign(cum_x)).mean()) if moving.any() and cum_x else 0.0
    moving_y = np.abs(dy) >= 0.5
    agree_y = float((np.sign(dy[moving_y]) == np.sign(cum_y)).mean()) if moving_y.any() and cum_y else 0.0
    first_mae = float(np.abs(np.asarray(ims[0], dtype=np.float64) - np.asarray(start.resize(ims[0].size, Image.Resampling.LANCZOS), dtype=np.float64)).mean())
    return {"frames": len(ims), "pan_px": round(cum_x * 2, 1), "pan_share": round(cum_x * 2 / W, 4), "pan_agree": round(agree_x, 2), "tilt_px": round(cum_y * 2, 1),
            "tilt_share": round(cum_y * 2 / H, 4), "tilt_agree": round(agree_y, 2), "zoom": zoom_between(ims[0], ims[-1]), "first_mae": round(first_mae, 2),
            "pair_dx": [round(float(x) * 2, 1) for x in dx]}


def verdict(move: str, m: dict) -> tuple[bool, str]:
    kind, sign = EXPECT.get(move, ("?", 0))
    if kind == "pan":
        ok = np.sign(m["pan_share"]) == sign and abs(m["pan_share"]) >= BAR_PAN_SHARE and m["pan_agree"] >= BAR_PAN_AGREE
        return bool(ok), f"pan {m['pan_share'] * 100:+.1f} % of the width ({m['pan_px']:+.0f} px), {m['pan_agree'] * 100:.0f} % of the pairs agree (expected {'right' if sign > 0 else 'left'}-moving content ≥ {BAR_PAN_SHARE * 100:.0f} %)"
    if kind == "tilt":
        ok = np.sign(m["tilt_share"]) == sign and abs(m["tilt_share"]) >= BAR_PAN_SHARE and m["tilt_agree"] >= BAR_PAN_AGREE
        return bool(ok), f"tilt {m['tilt_share'] * 100:+.1f} % of the height, {m['tilt_agree'] * 100:.0f} % agree"
    if kind == "zoom":
        ok = m["zoom"] >= BAR_ZOOM_IN if sign > 0 else m["zoom"] <= BAR_ZOOM_OUT
        return bool(ok), f"zoom ×{m['zoom']:.2f} first → last (expected {'≥ ' + str(BAR_ZOOM_IN) if sign > 0 else '≤ ' + str(BAR_ZOOM_OUT)})"
    if kind == "static":
        ok = abs(m["pan_share"]) <= BAR_STATIC_SHARE and abs(m["tilt_share"]) <= BAR_STATIC_SHARE and abs(m["zoom"] - 1) <= BAR_STATIC_ZOOM
        return bool(ok), f"pan {m['pan_share'] * 100:+.1f} %, tilt {m['tilt_share'] * 100:+.1f} %, zoom ×{m['zoom']:.2f} (expected still)"
    return False, "no expectation"


def sheet(rows: list[tuple[str, list[Image.Image]]], path: Path, size: tuple[int, int] = (416, 240)) -> None:
    w, h = size
    im = Image.new("RGB", (3 * (w + 6), len(rows) * (h + 20)), (24, 24, 24))
    dr = ImageDraw.Draw(im)
    for r, (lbl, ims) in enumerate(rows):
        dr.text((3, r * (h + 20) + 3), lbl, fill=(230, 230, 230))
        for c, f in enumerate(ims[:3]):
            im.paste(f.resize((w, h)), (c * (w + 6), r * (h + 20) + 18))
    im.save(path, quality=90)


def write_mp4(frames: list[Path], path: Path, fps: int) -> None:
    import av
    first = Image.open(frames[0])
    with av.open(str(path), "w") as oc:
        st = oc.add_stream("libx264", rate=fps)
        st.width, st.height, st.pix_fmt = first.width - first.width % 2, first.height - first.height % 2, "yuv420p"
        for p in frames:
            for pkt in st.encode(av.VideoFrame.from_image(Image.open(p).convert("RGB").crop((0, 0, st.width, st.height)))):
                oc.mux(pkt)
        for pkt in st.encode():
            oc.mux(pkt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--moves", default="Pan Left,Pan Right,Zoom In,Zoom Out,Static")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--no-baseline", action="store_true", help="skip the plain I2V runs with the move in the prompt")
    ap.add_argument("--seed", type=int, default=20261028)
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--no-lora", action="store_true", help="the Quality recipe (10 + 10, cfg 3.5): is the tone lift the Lightning LoRAs'?")
    a = ap.parse_args()
    import cr_acceptance as cr
    from e12_angles import Engine
    from e40_seedvr2 import launch_engine, stop_engine
    from m1_acceptance import port_busy
    from loom2.models import registry
    from loom2.roster import ROSTER_BY_ID
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    spec = registry.get(registry.default_model("i2v"))
    negative = spec.video.negative if spec and spec.video else ""
    i2v = {"high": ROSTER_BY_ID[spec.id].name, "low": ROSTER_BY_ID[spec.roles.extra["low_expert"]].name, "te": ROSTER_BY_ID[spec.roles.te.default].name, "vae": ROSTER_BY_ID[spec.roles.vae].name,
           "lora_high": ROSTER_BY_ID[spec.roles.extra["lightning_high"]].name, "lora_low": ROSTER_BY_ID[spec.roles.extra["lightning_low"]].name}
    cam = {**i2v, **CAMERA}
    moves = [m.strip() for m in a.moves.split(",") if m.strip()]
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "lora": not a.no_lora, "board": BOARD.name, "size": [W, H, FRAMES], "speed": a.speed, "seed": a.seed, "runs": [], "failures": [], "notes": []}
    log = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    def save() -> None:
        (OUT / a.out).write_text(json.dumps(results, indent=1), encoding="utf-8")

    start_im = Image.open(BOARD).convert("RGB")
    rows: list[tuple[str, list[Image.Image]]] = [("start image", [start_im.resize((W, H), Image.Resampling.LANCZOS)] * 3)]
    try:
        proc, launch = launch_engine(log)
        out_dir = Path(launch["argv"][launch["argv"].index("--output-directory") + 1])
        eng = Engine(ENGINE)
        vram = cr.VramSampler()
        start_name = eng.upload(BOARD)
        plan: list[tuple[str, str, dict, str | None, str]] = []
        if not a.no_baseline:
            for mv, prompt in PROMPT_BASELINE.items():
                plan.append((f"prompt only · {mv}", prompt, i2v, None, mv))
        for mv in moves:
            plan.append((f"Fun-Camera · {mv}", PROMPT_STILL, cam, mv, mv))
        for label, prompt, names, camera, move in plan:
            prefix = f"e41/{label.replace(' · ', '-').replace(' ', '_').lower()}{'-nolora' if a.no_lora else ''}/f"
            vram.mark()
            t0 = time.time()
            try:
                h, wall, exec_s = eng.run(wan_graph(names, start_name, prompt, negative, a.seed, prefix, camera, a.speed, not a.no_lora), timeout=3600)
                msgs = {m[0]: m[1] for m in h["status"].get("messages", [])}
                err = (msgs.get("execution_error") or {}).get("exception_message")
            except Exception as e:  # noqa: BLE001
                wall, exec_s, err = time.time() - t0, None, f"{type(e).__name__}: {e}"[:400]
            peak = vram.window()
            frames = sorted((out_dir / Path(prefix).parent).glob("*.png")) if not err else []
            row = {"label": label, "move": move, "camera": camera, "prompt": prompt, "exec_s": round(exec_s, 1) if exec_s else None, "wall_s": round(wall, 1), "peak_gb": peak, "frames": len(frames), "error": err}
            if frames:
                m = measure(frames, start_im)
                row |= m
                ok, text = verdict(move, m)
                row["as_told"] = ok
                mid = frames[len(frames) // 2]
                rows.append((f"{label} · {row['exec_s']} s · {text}", [Image.open(frames[0]).convert("RGB"), Image.open(mid).convert("RGB"), Image.open(frames[-1]).convert("RGB")]))
                try:
                    write_mp4(frames, OUT / f"{Path(prefix).parent.name}.mp4", FPS)
                except Exception as e:  # noqa: BLE001
                    results["notes"].append(f"{label}: no mp4 ({e})")
                print(f"{label}: {row['exec_s']} s exec · peak {peak} GB · {len(frames)} frames · {text} · first-frame MAE {m['first_mae']}", flush=True)
            else:
                print(f"{label}: error {err} · {row['wall_s']} s · peak {peak} GB", flush=True)
            results["runs"].append(row)
            save()
            if err and ("memory" in err.lower() or "oom" in err.lower()):
                results["notes"].append(f"{label}: out of memory — the rest of its kind skipped")
                if camera:
                    break
        sheet(rows, OUT / "sheet.jpg")
        # the bars
        cam_runs = [r for r in results["runs"] if r["camera"]]
        check(bool(cam_runs) and all(not r["error"] and r["frames"] == FRAMES for r in cam_runs), f"every Fun-Camera clip done ({sum(1 for r in cam_runs if not r['error'])}/{len(cam_runs)}, {[r['error'][:60] for r in cam_runs if r['error']]})")
        peaks = [r["peak_gb"] for r in results["runs"] if r.get("peak_gb")]
        check(bool(peaks) and max(peaks) <= BAR_PEAK_GB, f"peak VRAM ≤ {BAR_PEAK_GB} GB ({peaks})")
        warm = [r["exec_s"] for r in cam_runs[1:] if r.get("exec_s")]
        check(bool(warm) and max(warm) <= BAR_WARM_S, f"a warm Fun-Camera clip ≤ {BAR_WARM_S:g} s (warm {warm}; the first {cam_runs[0]['exec_s'] if cam_runs else None} s with the experts read from disk)")
        for r in cam_runs:
            if not r["error"] and r["frames"]:
                check(bool(r.get("as_told")), f"Fun-Camera {r['move']} moves as told — {verdict(r['move'], r)[1]}")
        firsts = [r["first_mae"] for r in cam_runs if r.get("first_mae") is not None]
        check(bool(firsts) and max(firsts) <= BAR_FIRST_MAE, f"the first frame keeps the start image (MAE {firsts} ≤ {BAR_FIRST_MAE:g})")
        for r in results["runs"]:
            if not r["camera"] and r.get("frames"):
                results["notes"].append(f"baseline {r['move']} in the prompt: {verdict(r['move'], r)[1]}{' — as told' if r.get('as_told') else ' — not as told'}")
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
