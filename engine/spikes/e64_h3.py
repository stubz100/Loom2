"""E64 (D192): MiniMax H3 on the rig — the first + last frame model (FL2VA) through the pinned ComfyUI's own H3 nodes (comfy_extras/
nodes_minimax_h3.py, v0.39.0), the graph of ComfyUI's "Image to Video (MiniMax H3)" blueprint at the precisions this card runs: the pruned
transformer fp8 scaled, the 8-step turbo LoRA, the H3 encoder bf16, the video VAE fp16 and the audio VAE. The bench's FLF task (03, the
rooftop: crouch to stand) at its H3 size (864×480, 5 s at 24 fps), the frames from bench/i2v/frames; Wan 2.2 and LTX-2.3 made the same
task in E4 / E5. One job on the GPU (the engine started by hand, nothing else queued): the wall time, the VRAM low-water mark from
/system_stats every 2 s, the engine's resident memory; the clip to out/e64/.

    engine/.venv/Scripts/python.exe engine/spikes/e64_h3.py [steps] [seconds] [--no-lora] [--size=WxH] [--seed=N]   # psutil is in the engine's venv
"""
from __future__ import annotations

import io
import json
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import psutil
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out" / "e64"
OUT.mkdir(parents=True, exist_ok=True)
BENCH = ROOT / "bench" / "i2v"
PORT = 8188
TASK = "03-flf-rooftop-crouch-to-stand"


def http(path: str, body: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def upload(path: Path, name: str) -> str:
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO(); img.save(buf, "PNG")
    boundary = "----e64" + str(int(time.time() * 1000))
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def frames_for(seconds: float) -> int:
    """The blueprint's ComfyMathExpression: max(5, round(s × 24)) snapped up to the model's 17k + 5 grid."""
    n = max(5, round(seconds * 24))
    return n + (5 - n % 17) % 17


def graph(first: str, last: str, prompt: str, steps: int, length: int, lora: bool, seed: int = 64, w: int = 864, h: int = 480) -> dict:
    model = ["2", 0] if lora else ["1", 0]
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_bf16.safetensors", "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "6": {"class_type": "LoadImage", "inputs": {"image": first}},
        "7": {"class_type": "LoadImage", "inputs": {"image": last}},
        "8": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "prompt": prompt, "width": w, "height": h, "length": length,
                                                               "first_frame": ["6", 0], "last_frame": ["7", 0]}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": ["8", 0]}},
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "12": {"class_type": "BasicScheduler", "inputs": {"model": model, "scheduler": "simple", "steps": steps, "denoise": 1.0}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["11", 0], "sigmas": ["12", 0], "latent_image": ["8", 1]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["4", 0]}},
        "15": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["13", 0], "vae": ["5", 0]}},
        "16": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "audio": ["15", 0], "fps": 24}},
        "17": {"class_type": "SaveVideo", "inputs": {"video": ["16", 0], "filename_prefix": f"e64/h3_{w}x{h}_{steps}s{'_turbo' if lora else ''}", "format": "mp4", "codec": "h264"}},
    }
    if lora:
        g["2"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", "strength_model": 1.0}}
    return g


def engine_proc() -> psutil.Process | None:
    for c in psutil.net_connections(kind="tcp"):
        if c.laddr and c.laddr.port == PORT and c.status == psutil.CONN_LISTEN and c.pid:
            return psutil.Process(c.pid)
    return None


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    steps = int(args[0]) if args else 8
    seconds = float(args[1]) if len(args) > 1 else 5.0
    lora = "--no-lora" not in sys.argv
    size = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--size=")), "864x480")
    w, h = (int(x) for x in size.lower().split("x"))
    task = next(t for t in json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))["tasks"] if t["id"] == TASK)
    stats = http("/system_stats")
    dev = (stats.get("devices") or [{}])[0]
    total, free0 = dev.get("vram_total", 0), dev.get("vram_free", 0)
    print("engine", stats.get("system", {}).get("comfyui_version"), dev.get("name"), f"VRAM {total / 2**30:.1f} GB, free {free0 / 2**30:.1f}")
    tag = time.strftime("%H%M%S")                                         # a new name each run: a new job, nothing cached from the last
    first = upload(BENCH / task["start"], f"e64-first-{tag}.png")
    last = upload(BENCH / task["end"], f"e64-last-{tag}.png")
    length = frames_for(seconds)
    seed = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--seed=")), "64"))
    g = graph(first, last, task["prompt"], steps, length, lora, seed=seed, w=w, h=h)
    ram0 = stats.get("system", {}).get("ram_free", 0)
    low = {"free": free0, "rss": 0, "ram": ram0}
    proc = engine_proc()
    done = threading.Event()

    def watch() -> None:
        while not done.is_set():
            try:
                st = http("/system_stats", timeout=10)
                f = (st.get("devices") or [{}])[0].get("vram_free", free0)
                low["free"] = min(low["free"], f)
                low["ram"] = min(low["ram"], st.get("system", {}).get("ram_free", ram0))
                if proc:
                    low["rss"] = max(low["rss"], proc.memory_info().rss)
            except Exception:
                pass
            time.sleep(2)

    th = threading.Thread(target=watch, daemon=True); th.start()
    t0 = time.time()
    pid = http("/prompt", {"prompt": g})["prompt_id"]
    print("queued", pid, f"{length} frames, {steps} steps, turbo LoRA {lora}", flush=True)
    hd = None
    while time.time() - t0 < 7200:
        hist = http(f"/history/{pid}", timeout=30)
        if pid in hist:
            st = hist[pid].get("status", {})
            if st.get("status_str") == "error" or hist[pid].get("outputs"):
                hd = hist[pid]; break
        time.sleep(3)
    wall = time.time() - t0
    done.set(); th.join(timeout=5)
    res = {"when": time.strftime("%Y-%m-%d %H:%M"), "task": TASK, "size": f"{w}x{h}", "seed": seed, "steps": steps, "frames": length, "seconds_clip": round(length / 24, 2), "lora": lora, "wall_s": round(wall, 1),
           "vram_peak_gb": round((total - low["free"]) / 2**30, 2), "engine_rss_peak_gb": round(low["rss"] / 2**30, 2),
           "ram_taken_peak_gb": round((ram0 - low["ram"]) / 2**30, 1)}
    if not hd or hd.get("status", {}).get("status_str") == "error":
        res["error"] = json.dumps((hd or {}).get("status", {}))[:1500]
    else:
        msgs = hd.get("status", {}).get("messages") or []
        res["cached"] = sorted({n for m in msgs if isinstance(m, list) and m[0] == "execution_cached" for n in m[1].get("nodes", [])}, key=int)
        ts = {m[0]: m[1].get("timestamp") for m in msgs if isinstance(m, list) and len(m) > 1 and isinstance(m[1], dict)}
        if ts.get("execution_start") and ts.get("execution_success"):
            res["engine_s"] = round((ts["execution_success"] - ts["execution_start"]) / 1000, 1)
        for out in hd["outputs"].values():
            for v in (out.get("images") or []) + (out.get("videos") or []) + (out.get("gifs") or []):
                q = urllib.parse.urlencode({"filename": v["filename"], "subfolder": v.get("subfolder", ""), "type": v.get("type", "output")})
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/view?{q}", timeout=120) as r:
                    dst = OUT / v["filename"]
                    dst.write_bytes(r.read())
                    res["clip"] = str(dst)
    print(json.dumps(res, indent=1))
    with (OUT / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
