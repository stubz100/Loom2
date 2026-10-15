"""E19 — pose-driven shots (19 §2, D87): the Cast's character performing the Stage's blocking, by Wan2.2 Animate *Move* on loom2's own
rendered pose pass (E11's five shots: crouch_crane, run_track, turn_orbit, walk_dolly, wave_static — pose.mp4 + keypoints.json), with
Mara's hero (bench/angles/07.jpg) as the reference image. No DWPose, no face video, no masks.

Graph (core nodes): UNETLoader (Wan2_2-Animate-14B fp8, Kijai's scaled repack — the ComfyUI template's file) → LoraLoaderModelOnly (the
LightX2V I2V 4-step LoRA, as the template) → ModelSamplingSD3 (shift 8) · CLIPLoader umT5 · VAELoader Wan 2.1 · CLIPVisionLoader clip_vision_h →
CLIPVisionEncode of the reference · LoadVideo (pose.mp4) → GetVideoComponents → ImageScale → WanAnimateToVideo (reference_image, pose_video,
77 f at 832×480) → KSampler (4 steps, CFG 1, euler / simple) → TrimVideoLatent (the reference's latent frame) → VAEDecode → SaveImage.
Scores per shot: PCK@0.1 (SDPose on every 10th frame vs the rendered keypoints at the same index — E10's scorer), FaceSim to the hero at the
first / middle / last frame, exec seconds; bars (19 §2): PCK ≥ 0.8 (E11's "followed" ≥ 0.5 reported too), FaceSim ≥ 0.45, ≤ 300 s per 77 f,
no OOM. Outputs under engine/spikes/out/e19/: the clips as mp4, a sheet, results.jsonl. Needs port 8188 free and E19's fetch (fetch_weights.py
--only e19).

    orchestrator/.venv/Scripts/python.exe engine/spikes/e19_animate.py [--shots walk_dolly,turn_orbit,...] [--ref bench/angles/07.jpg]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e10_stage import pck, sdpose_graph  # noqa: E402
from e12_angles import Engine  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e19"
E11 = REPO / "engine" / "spikes" / "out" / "e11"
RESULTS = OUT / "results.jsonl"
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
ENGINE = "127.0.0.1:8188"
SEED = 20261014
W, H, FRAMES, FPS = 832, 480, 77, 16
BARS = {"pck": 0.8, "followed": 0.5, "facesim": 0.45, "time": 300.0}
FILES = {"unet": "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", "lora": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
         "te": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "vae": "wan_2.1_vae.safetensors", "clip_vision": "clip_vision_h.safetensors"}
PROMPT = "the character performs the motion naturally, full body visible, steady camera, cinematic light, a clean studio floor"
NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
       "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def engine_listening() -> bool:
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2)
        return True
    except Exception:
        return False


def animate_graph(ref_name: str, pose_name: str, seed: int, prefix: str) -> tuple[dict, str]:
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": FILES["unet"], "weight_dtype": "default"}},
        "1l": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": FILES["lora"], "strength_model": 1.0}},
        "1s": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1l", 0], "shift": 8.0}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": FILES["te"], "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": FILES["vae"]}},
        "4": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": FILES["clip_vision"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": ref_name}},
        "7s": {"class_type": "ImageScale", "inputs": {"image": ["7", 0], "upscale_method": "lanczos", "width": W, "height": H, "crop": "center"}},
        "8": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["4", 0], "image": ["7s", 0], "crop": "center"}},
        "9": {"class_type": "LoadVideo", "inputs": {"file": pose_name}},
        "10": {"class_type": "GetVideoComponents", "inputs": {"video": ["9", 0]}},
        "10s": {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": W, "height": H, "crop": "center"}},
        "11": {"class_type": "WanAnimateToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": W, "height": H, "length": FRAMES, "batch_size": 1,
                                                            "clip_vision_output": ["8", 0], "reference_image": ["7s", 0], "pose_video": ["10s", 0], "continue_motion_max_frames": 5, "video_frame_offset": 0}},
        "12": {"class_type": "KSampler", "inputs": {"model": ["1s", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["11", 0], "negative": ["11", 1], "latent_image": ["11", 2], "denoise": 1.0}},
        "13": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["12", 0], "trim_amount": ["11", 3]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}},
    }
    return g, "15"


def map_figs(figs: list, src: tuple[int, int]) -> list:
    """E11's keypoints are in its render's pixels (1024×576); the pose video reaches WanAnimateToVideo through ImageScale (cover, centre
    crop) at W×H — the same transform on the points, or PCK compares two coordinate spaces (the first run's 0.0)."""
    sw, sh = src
    s = max(W / sw, H / sh)
    ox, oy = (sw * s - W) / 2, (sh * s - H) / 2
    out = []
    for fig in figs:
        g = np.array(fig, dtype=float)
        g[:, 0] = g[:, 0] * s - ox
        g[:, 1] = g[:, 1] * s - oy
        out.append(g.tolist())
    return out


def padded_ref(src: Path, dest: Path) -> Path:
    """The reference fitted inside W×H (no crop) on its own edge colour — the first run centre-cropped a portrait hero to landscape and the
    model painted the cropped face into the background (turn_orbit's ghost)."""
    im = Image.open(src).convert("RGB")
    im.thumbnail((W, H), Image.LANCZOS)
    a = np.asarray(im)
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]).mean(axis=0).astype(int)
    canvas = Image.new("RGB", (W, H), tuple(int(x) for x in edge))
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)
    return dest


def score_pck(e: Engine, frames: list[Path], kp: dict, every: int) -> float | None:
    gt = kp["frames"]
    size = tuple(kp.get("size") or (W, H))
    hit = tot = 0
    for idx in range(0, len(frames), every):
        if idx >= len(gt):
            break
        hp, _, _ = e.run(sdpose_graph(e.upload(frames[idx])))
        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
        h_, t_ = pck(map_figs(gt[idx], size), people)
        hit += h_; tot += t_
    return round(hit / tot, 3) if tot else None


def download_frames(e: Engine, h: dict, node: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, o in enumerate(h["outputs"][node]["images"]):
        r = e.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
        p = dest / f"{i:04d}.png"
        p.write_bytes(r.content)
        out.append(p)
    return out


def encode(frames: list[Path], path: Path) -> None:
    with av.open(str(path), "w") as out:
        s = out.add_stream("libx264", rate=FPS)
        s.width, s.height, s.pix_fmt, s.time_base = W, H, "yuv420p", Fraction(1, FPS)
        s.options = {"crf": "12", "preset": "veryfast", "g": str(FPS)}
        for i, f in enumerate(frames):
            vf = av.VideoFrame.from_ndarray(np.asarray(Image.open(f).convert("RGB")), format="rgb24")
            vf.pts = i
            for p in s.encode(vf):
                out.mux(p)
        for p in s.encode():
            out.mux(p)


def largest_face(fs: FaceSim, p: Path) -> np.ndarray | None:
    a = np.asarray(Image.open(p).convert("RGB"))
    faces = fs.detect(a)
    return fs.embed(a, max(faces, key=lambda x: x.area).kps) if faces else None


def sheet(cells: list[tuple[Path, str]], path: Path, cols: int = 7, cell: int = 224) -> None:
    rows = (len(cells) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 16)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, (p, label) in enumerate(cells):
        th = Image.open(p).convert("RGB"); th.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        im.paste(th, (x, y))
        d.text((x + 2, y + cell + 2), label[:34], fill=(220, 220, 220))
    im.save(path, quality=88)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="walk_dolly,turn_orbit,wave_static,run_track,crouch_crane")
    ap.add_argument("--ref", default=str(REPO / "bench" / "angles" / "07.jpg"))
    ap.add_argument("--every", type=int, default=10, help="score every n-th frame with SDPose")
    ap.add_argument("--ref-mode", default="pad", choices=["pad", "crop"], help="fit the reference inside the frame (pad) or centre-crop it (the first run)")
    ap.add_argument("--rescore", action="store_true", help="score the saved frames again (the keypoints mapped) — no Animate run")
    a = ap.parse_args()
    if engine_listening():
        print("an engine is already listening on 8188 — stop it first"); return 2
    missing = [n for n in (FILES["unet"], FILES["lora"]) if not list(MODELS.rglob(n))]
    if missing:
        print("weights missing:", missing, "— scripts/fetch_weights.py --only e19"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    eng_log = (OUT / "engine.log").open("a", encoding="utf-8")
    eng = subprocess.Popen(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-start.ps1")], stdout=eng_log, stderr=subprocess.STDOUT, text=True)
    cells: list[tuple[Path, str]] = []
    try:
        t0 = time.time()
        while time.time() - t0 < 180 and not engine_listening():
            time.sleep(1.0)
        if not engine_listening():
            print("the engine did not come up"); return 1
        e = Engine(ENGINE)
        fs = FaceSim(MODELS)
        ref = Path(a.ref)
        hero = largest_face(fs, ref)
        ref_name = e.upload(padded_ref(ref, OUT / "ref_padded.png") if a.ref_mode == "pad" else ref)
        if a.rescore:
            for sid in [s for s in a.shots.split(",") if s]:
                frames = sorted((OUT / sid).glob("*.png"))
                kp_path = E11 / sid / "keypoints.json"
                if not frames or not kp_path.is_file():
                    continue
                pck_v = score_pck(e, frames, json.loads(kp_path.read_text(encoding="utf-8")), a.every)
                row = {"shot": sid, "rescored": True, "frames": len(frames), "pck": pck_v, "stamp": time.strftime("%Y-%m-%d %H:%M")}
                with (OUT / "results_rescored.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + chr(10))
                log(f"  rescored {sid}: PCK {pck_v} ({len(frames)} frames)")
            return 0
        rows = []
        for sid in [s for s in a.shots.split(",") if s]:
            pose = E11 / sid / "pose.mp4"
            kp_path = E11 / sid / "keypoints.json"
            if not pose.is_file() or not kp_path.is_file():
                log(f"  {sid}: no pose.mp4 / keypoints.json under {E11 / sid} — skipped"); continue
            pose_name = e.upload(pose)
            prefix = f"e19/{sid}"
            g, node = animate_graph(ref_name, pose_name, SEED, prefix)
            try:
                h, wall, exec_s = e.run(g, timeout=3600)
            except Exception as ex:  # noqa: BLE001
                log(f"  FAILED {sid}: {type(ex).__name__}: {str(ex)[:300]}")
                with RESULTS.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"shot": sid, "error": f"{type(ex).__name__}: {str(ex)[:300]}", "stamp": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
                continue
            frames = download_frames(e, h, node, OUT / sid)
            encode(frames, OUT / f"{sid}.mp4")
            pck_v = score_pck(e, frames, json.loads(kp_path.read_text(encoding="utf-8")), a.every)
            sims = []
            for idx in (0, len(frames) // 2, len(frames) - 1):
                emb = largest_face(fs, frames[idx])
                sims.append(round(fs.similarity(hero, emb), 3) if hero is not None and emb is not None else None)
            vals = [s for s in sims if s is not None]
            for idx in np.linspace(0, len(frames) - 1, 7).astype(int):
                cells.append((frames[idx], f"{sid} f{idx}"))
            row = {"shot": sid, "ref_mode": a.ref_mode, "frames": len(frames), "exec_s": round(exec_s, 1), "pck": pck_v, "facesim": sims,
                   "bars": {"pck": pck_v is not None and pck_v >= BARS["pck"], "followed": pck_v is not None and pck_v >= BARS["followed"],
                            "facesim": bool(vals) and min(vals) >= BARS["facesim"], "time": exec_s <= BARS["time"]}, "stamp": time.strftime("%Y-%m-%d %H:%M")}
            rows.append(row)
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            log(f"  {sid}: {len(frames)} f in {exec_s:.0f} s, PCK {pck_v}, facesim {sims}")
        if cells:
            sheet(cells, OUT / "sheet.jpg")
        print(json.dumps(rows, indent=1))
    finally:
        try:
            subprocess.run(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-stop.ps1")], capture_output=True, timeout=60)
        except Exception:
            pass
        try:
            eng.wait(timeout=30)
        except Exception:
            eng.kill()
        eng_log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
