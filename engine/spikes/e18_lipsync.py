"""E18 — lip-sync (19 §2, D87): does a character's still plus a spoken line become a clip whose lips follow the voice, on this card?

Methods, both on the pinned engine's own nodes:
  ltx_ia2v   LTX-2.3 distilled 1.1 (on disk): loom2's LTX graph with the line's audio encoded by `LTXVAudioVAEEncode` into the joint
             audio-video latent in place of the empty audio latent (one node); 121 f at 24 fps, 1024×576, the draft preset (8 steps)
  wan_s2v    Wan2.2 S2V-14B fp8 (E18's fetch, Apache-2.0): `AudioEncoderLoader` (wav2vec2) → `AudioEncoderEncode` → `WanSoundImageToVideo`
             77 f at 16 fps, 832×480, 20 steps at CFG 6 (the template's figures; its Lightning LoRA is not trained for S2V)
Inputs: three of E20's lines (en1, en3 draft; de1 clone) × two faces (Mara's hero bench/angles/07.jpg, the bench's portrait-grief), fixed
seeds; the audio trimmed or padded to the clip's length. Scores per clip:
  sync       a mouth-motion proxy: the motion energy of the mouth crop (around the detector's two mouth-corner landmarks) per frame against
             the audio's RMS envelope at the clip's fps, Pearson r at the best lag within ±3 frames — bar ≥ 0.5
  facesim    FaceSim of the start image's face at the first, middle and last frame — bar ≥ 0.45 (the minimum)
  time       exec seconds per clip — bar ≤ 240 s
Outputs under engine/spikes/out/e18/: every clip as mp4 with the audio muxed (PyAV), a sheet per method, results.jsonl. Needs port 8188
free (starts the engine standalone, stops it after) and E20's WAVs.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e18_lipsync.py [--methods ltx_ia2v,wan_s2v] [--lines en1,en3,de1] [--faces mara,grief]
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
import soundfile as sf
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e12_angles import Engine  # noqa: E402
from loom2.engine.graphs import build_i2v  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2V  # noqa: E402
from loom2.roster import Roster  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e18"
RESULTS = OUT / "results.jsonl"
VOICE = REPO / "engine" / "spikes" / "out" / "e20"
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
ENGINE = "127.0.0.1:8188"
ROSTER = Roster(MODELS, [], "full").scan()
LTX = next(i for i, s in registry.SPECS.items() if s.graph == "ltx23")
SEED = 20261014
BARS = {"sync": 0.5, "facesim": 0.45, "time": 240.0}
FACES = {"mara": REPO / "bench" / "angles" / "07.jpg", "grief": REPO / "bench" / "i2v" / "frames" / "portrait-grief_s20261004.png"}
LINE_WAV = {"en1": "en1_draft.wav", "en2": "en2_draft.wav", "en3": "en3_draft.wav", "en4": "en4_draft.wav", "de1": "de1_clone.wav", "de2": "de2_clone.wav"}
SPEC = {"ltx_ia2v": {"frames": 121, "fps": 24, "w": 1024, "h": 576}, "wan_s2v": {"frames": 77, "fps": 16, "w": 832, "h": 480}}
SPEC["wan_s2v10"] = {**SPEC["wan_s2v"], "steps": 10}            # E18 follow-up 2026-10-15: half the steps — does the sync hold at half the time?
S2V = {"unet": "wan2.2_s2v_14B_fp8_scaled.safetensors", "te": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "vae": "wan_2.1_vae.safetensors", "audio": "wav2vec2_large_english_fp16.safetensors"}
NEG_WAN = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
           "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")
PROMPT = "a close-up of the character speaking the line to the camera, calm, natural head motion, steady camera, soft light"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def engine_listening() -> bool:
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2)
        return True
    except Exception:
        return False


def fit_audio(src: Path, seconds: float, dest: Path) -> tuple[np.ndarray, int]:
    """The line trimmed or padded with silence to the clip's length, mono, as a WAV the engine's LoadAudio reads."""
    a, sr = sf.read(src, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    n = int(round(seconds * sr))
    a = a[:n] if len(a) >= n else np.concatenate([a, np.zeros(n - len(a), dtype=np.float32)])
    sf.write(dest, a, sr)
    return a, sr


def rms_envelope(a: np.ndarray, sr: int, fps: int, frames: int) -> np.ndarray:
    hop = sr / fps
    out = np.zeros(frames, dtype=np.float32)
    for i in range(frames):
        s = a[int(i * hop): int((i + 1) * hop)]
        out[i] = float(np.sqrt(np.mean(s * s))) if len(s) else 0.0
    return out


def mouth_energy(fs: FaceSim, frames: list[Path]) -> tuple[np.ndarray, int]:
    """The motion energy of the mouth crop per frame (mean absolute difference to the previous frame), the crop from the detector's two
    mouth-corner landmarks of frame 0 (kept fixed: a head that moves is motion the proxy must not count twice)."""
    first = np.asarray(Image.open(frames[0]).convert("RGB"))
    faces = fs.detect(first)
    if not faces:
        return np.zeros(len(frames), dtype=np.float32), 0
    kps = max(faces, key=lambda x: x.area).kps
    ml, mr = kps[3], kps[4]
    cx, cy = (ml[0] + mr[0]) / 2, (ml[1] + mr[1]) / 2
    d = max(8.0, float(np.hypot(mr[0] - ml[0], mr[1] - ml[1])))
    x0, x1 = int(max(0, cx - 0.9 * d)), int(min(first.shape[1], cx + 0.9 * d))
    y0, y1 = int(max(0, cy - 0.6 * d)), int(min(first.shape[0], cy + 0.8 * d))
    prev = None
    out = np.zeros(len(frames), dtype=np.float32)
    for i, p in enumerate(frames):
        crop = np.asarray(Image.open(p).convert("L"), dtype=np.float32)[y0:y1, x0:x1]
        if prev is not None and crop.shape == prev.shape and crop.size:
            out[i] = float(np.mean(np.abs(crop - prev)))
        prev = crop
    return out, 1


def sync_score(motion: np.ndarray, env: np.ndarray) -> tuple[float, int]:
    best, lag_best = -1.0, 0
    for lag in range(-3, 4):
        if lag >= 0:
            m, e = motion[lag:], env[: len(env) - lag]
        else:
            m, e = motion[: len(motion) + lag], env[-lag:]
        if len(m) < 8 or np.std(m) < 1e-6 or np.std(e) < 1e-6:
            continue
        r = float(np.corrcoef(m, e)[0, 1])
        if r > best:
            best, lag_best = r, lag
    return round(best, 3), lag_best


def largest_face(fs: FaceSim, p: Path) -> np.ndarray | None:
    a = np.asarray(Image.open(p).convert("RGB"))
    faces = fs.detect(a)
    return fs.embed(a, max(faces, key=lambda x: x.area).kps) if faces else None


def download_frames(e: Engine, h: dict, node: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, o in enumerate(h["outputs"][node]["images"]):
        r = e.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
        p = dest / f"{i:06d}.png"
        p.write_bytes(r.content)
        out.append(p)
    return out


def mux(frames: list[Path], wav: Path, path: Path, fps: int, w: int, h: int) -> None:
    a, sr = sf.read(wav, dtype="float32", always_2d=True)
    with av.open(str(path), "w") as out:
        v = out.add_stream("libx264", rate=fps)
        v.width, v.height, v.pix_fmt, v.time_base = w, h, "yuv420p", Fraction(1, fps)
        v.options = {"crf": "12", "preset": "veryfast", "g": str(fps)}
        s = out.add_stream("aac", rate=sr)
        s.layout = "mono"
        for i, f in enumerate(frames):
            vf = av.VideoFrame.from_ndarray(np.asarray(Image.open(f).convert("RGB")), format="rgb24")
            vf.pts = i
            for p in v.encode(vf):
                out.mux(p)
        for p in v.encode():
            out.mux(p)
        chunk = 1024
        mono = a.mean(axis=1).astype(np.float32)
        for i in range(0, len(mono), chunk):
            seg = mono[i:i + chunk]
            af = av.AudioFrame.from_ndarray(seg.reshape(1, -1), format="flt", layout="mono")
            af.sample_rate = sr
            af.pts = i
            for p in s.encode(af):
                out.mux(p)
        for p in s.encode():
            out.mux(p)


def ltx_graph(face_name: str, audio_name: str, sp: dict, seed: int, prefix: str) -> tuple[dict, str]:
    """loom2's own LTX graph with the line's audio in the joint latent instead of silence."""
    recipe = I2V(model_id=LTX, start_asset="start", prompt_text=PROMPT, frames=sp["frames"], fps=sp["fps"], width=sp["w"], height=sp["h"], preset="draft")
    c = build_i2v(recipe, ROSTER, seed, prefix, face_name)
    g = c.graph
    g["60"] = {"class_type": "LoadAudio", "inputs": {"audio": audio_name}}
    g["61"] = {"class_type": "LTXVAudioVAEEncode", "inputs": {"audio": ["60", 0], "audio_vae": ["99", 0]}}
    g["13"]["inputs"]["audio_latent"] = ["61", 0]
    g.pop("12", None)
    return g, c.output_node


def s2v_graph(face_name: str, audio_name: str, sp: dict, seed: int, prefix: str) -> tuple[dict, str]:
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": S2V["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": S2V["te"], "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": S2V["vae"]}},
        "4": {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": S2V["audio"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG_WAN, "clip": ["2", 0]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": face_name}},
        "7s": {"class_type": "ImageScale", "inputs": {"image": ["7", 0], "upscale_method": "lanczos", "width": sp["w"], "height": sp["h"], "crop": "center"}},
        "8": {"class_type": "LoadAudio", "inputs": {"audio": audio_name}},
        "9": {"class_type": "AudioEncoderEncode", "inputs": {"audio_encoder": ["4", 0], "audio": ["8", 0]}},
        "10": {"class_type": "WanSoundImageToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": sp["w"], "height": sp["h"], "length": sp["frames"],
                                                                "batch_size": 1, "audio_encoder_output": ["9", 0], "ref_image": ["7s", 0]}},
        "11": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "12": {"class_type": "KSampler", "inputs": {"model": ["11", 0], "seed": seed, "steps": sp.get("steps", 20), "cfg": 6.0, "sampler_name": "uni_pc", "scheduler": "simple",
                                                    "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["10", 2], "denoise": 1.0}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": prefix}},
    }
    return g, "14"


def sheet(cells: list[tuple[Path, str]], path: Path, cols: int = 6, cell: int = 224) -> None:
    rows = (len(cells) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 16)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, (p, label) in enumerate(cells):
        th = Image.open(p).convert("RGB"); th.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        im.paste(th, (x, y))
        d.text((x + 2, y + cell + 2), label[:36], fill=(220, 220, 220))
    im.save(path, quality=88)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="ltx_ia2v,wan_s2v")
    ap.add_argument("--lines", default="en1,en3,de1")
    ap.add_argument("--faces", default="mara,grief")
    a = ap.parse_args()
    if engine_listening():
        print("an engine is already listening on 8188 — stop it first"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [l for l in a.lines.split(",") if l and (VOICE / LINE_WAV[l]).is_file()]
    if not lines:
        print("no E20 lines found under", VOICE); return 2
    eng_log = (OUT / "engine.log").open("a", encoding="utf-8")
    eng = subprocess.Popen(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-start.ps1")], stdout=eng_log, stderr=subprocess.STDOUT, text=True)
    try:
        t0 = time.time()
        while time.time() - t0 < 180 and not engine_listening():
            time.sleep(1.0)
        if not engine_listening():
            print("the engine did not come up"); return 1
        e = Engine(ENGINE)
        fs = FaceSim(MODELS)
        for method in [m for m in a.methods.split(",") if m]:
            sp = SPEC[method]
            cells: list[tuple[Path, str]] = []
            for face in [f for f in a.faces.split(",") if f]:
                face_name = e.upload(FACES[face])
                hero = largest_face(fs, FACES[face])
                for lid in lines:
                    secs = sp["frames"] / sp["fps"]
                    wav = OUT / f"{lid}_{method}_{int(secs * 1000)}ms.wav"
                    audio, sr = fit_audio(VOICE / LINE_WAV[lid], secs, wav)
                    audio_name = e.upload(wav)
                    prefix = f"e18/{method}_{face}_{lid}"
                    g, node = (ltx_graph if method == "ltx_ia2v" else s2v_graph)(face_name, audio_name, sp, SEED, prefix)
                    try:
                        h, wall, exec_s = e.run(g, timeout=3600)
                    except Exception as ex:  # noqa: BLE001
                        log(f"  FAILED {method} {face} {lid}: {type(ex).__name__}: {str(ex)[:300]}")
                        with RESULTS.open("a", encoding="utf-8") as f:
                            f.write(json.dumps({"method": method, "face": face, "line": lid, "error": f"{type(ex).__name__}: {str(ex)[:300]}", "stamp": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
                        continue
                    frames = download_frames(e, h, node, OUT / f"{method}_{face}_{lid}")
                    motion, ok = mouth_energy(fs, frames)
                    env = rms_envelope(audio, sr, sp["fps"], len(frames))
                    r, lag = sync_score(motion[1:], env[1:]) if ok else (None, 0)
                    sims = []
                    for idx in (0, len(frames) // 2, len(frames) - 1):
                        emb = largest_face(fs, frames[idx])
                        sims.append(round(fs.similarity(hero, emb), 3) if hero is not None and emb is not None else None)
                    mp4 = OUT / f"{method}_{face}_{lid}.mp4"
                    mux(frames, wav, mp4, sp["fps"], sp["w"], sp["h"])
                    for idx in np.linspace(0, len(frames) - 1, 6).astype(int):
                        cells.append((frames[idx], f"{face} {lid} f{idx}"))
                    vals = [s for s in sims if s is not None]
                    row = {"method": method, "face": face, "line": lid, "frames": len(frames), "fps": sp["fps"], "exec_s": round(exec_s, 1), "sync_r": r, "sync_lag": lag,
                           "mouth_found": bool(ok), "facesim": sims, "mp4": str(mp4),
                           "bars": {"sync": r is not None and r >= BARS["sync"], "facesim": bool(vals) and min(vals) >= BARS["facesim"], "time": exec_s <= BARS["time"]},
                           "stamp": time.strftime("%Y-%m-%d %H:%M")}
                    with RESULTS.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(row) + "\n")
                    log(f"  {method} {face} {lid}: {exec_s:.0f} s, sync r {r} (lag {lag}), facesim {sims}")
            if cells:
                sheet(cells, OUT / f"{method}_sheet.jpg")
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
