"""E5 driver: LTX-2.3 (distilled) image-to-video with keyframe guides through the headless engine (12 §1 E5, 04 §5b D9).

Usage (engine running):
  engine/.venv/Scripts/python.exe engine/spikes/e5_ltx_i2v.py [--tasks 01,03] [--ltx-format gguf|fp8] [--preflight]

Graph (ComfyUI 0.38 LTX-2 nodes): loaders → CLIPTextEncode ×2 → LTXVConditioning(frame_rate) → LTXVImgToVideo(start)
→ [LTXVAddGuide(end image, frame_idx=-1)] → audio-video latent (LTXVEmptyLatentAudio + LTXVConcatAVLatent, because the
LTX-2 transformer is joint AV) → SamplerCustomAdvanced (BasicGuider, euler, LTXVScheduler) → LTXVSeparateAVLatent →
VAEDecode (video VAE) → CreateVideo(24 fps) → SaveVideo.  --preflight prints the signatures of every LTX node used
and runs the contract check without sampling, because the AV-latent plumbing is the least certain part.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "bench" / "i2v"
OUT = REPO / "engine" / "spikes" / "out" / "e5"
RESULTS = REPO / "engine" / "spikes" / "out" / "e5_results.jsonl"
LTX_NODES = ["LTXVImgToVideo", "LTXVAddGuide", "LTXVConditioning", "LTXVScheduler", "LTXVEmptyLatentAudio", "LTXVConcatAVLatent",
             "LTXVSeparateAVLatent", "LTXVCropGuides", "LTXVPreprocess", "UnetLoaderGGUF", "DualCLIPLoader", "CLIPLoader", "VAELoader"]


def http(server, path, data=None, timeout=120):
    req = urllib.request.Request(f"http://{server}{path}", method="POST" if data is not None else "GET")
    body = None
    if data is not None:
        body = json.dumps(data).encode(); req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, body, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw


def upload(server, path: Path) -> str:
    r = requests.post(f"http://{server}/upload/image", files={"image": (path.name, path.open("rb"), "image/png")},
                      data={"overwrite": "true", "type": "input"}, timeout=120)
    r.raise_for_status(); j = r.json()
    return (j.get("subfolder") + "/" if j.get("subfolder") else "") + j["name"]


def sig(obj, cls):
    o = obj.get(cls)
    if not o: return f"{cls}: NOT REGISTERED"
    def fmt(d):
        r = []
        for k, v in d.items():
            t = v[0] if isinstance(v, list) and v else v
            if isinstance(t, list): t = f"enum[{len(t)}:{','.join(map(str, t[:3]))}…]"
            cfg = v[1] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], dict) else {}
            r.append(f"{k}:{t}" + (f"={cfg['default']}" if cfg.get("default") is not None else ""))
        return ", ".join(r)
    return f"{cls}  REQ[{fmt(o['input'].get('required', {}))}]  OPT[{fmt(o['input'].get('optional', {}))}] -> {o.get('output')}"


def build(fmt: str, prompt: str, start: str, end: str | None, w: int, h: int, frames: int, fps: int, steps: int, seed: int, tag: str) -> dict:
    g = {}
    if fmt == "gguf":
        g["1"] = {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf"}}
    else:
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors", "weight_dtype": "default"}}
    g["2"] = {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "gemma_3_12B_it_fp8_scaled.safetensors", "clip_name2": "ltx-2.3_text_projection_bf16.safetensors", "type": "ltxv"}}
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.3_video_vae_bf16.safetensors"}}
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, distorted, low quality, static, watermark", "clip": ["2", 0]}}
    g["7"] = {"class_type": "LTXVConditioning", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "frame_rate": float(fps)}}
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": start}}
    g["110"] = {"class_type": "ImageScale", "inputs": {"image": ["100", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
    g["111"] = {"class_type": "LTXVPreprocess", "inputs": {"image": ["110", 0], "img_compression": 35}}
    g["8"] = {"class_type": "LTXVImgToVideo", "inputs": {"positive": ["7", 0], "negative": ["7", 1], "vae": ["3", 0], "image": ["111", 0], "width": w, "height": h, "length": frames, "batch_size": 1, "strength": 1.0}}
    pos, neg, lat = ["8", 0], ["8", 1], ["8", 2]
    if end:
        g["101"] = {"class_type": "LoadImage", "inputs": {"image": end}}
        g["112"] = {"class_type": "ImageScale", "inputs": {"image": ["101", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        g["113"] = {"class_type": "LTXVPreprocess", "inputs": {"image": ["112", 0], "img_compression": 35}}
        g["9"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["3", 0], "latent": lat, "image": ["113", 0], "frame_idx": -1, "strength": 1.0}}
        pos, neg, lat = ["9", 0], ["9", 1], ["9", 2]
    # joint audio-video latent (the LTX-2 transformer samples both); audio is discarded after sampling
    g["99"] = {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.3_audio_vae_bf16.safetensors"}}  # core 0.38 requires an audio VAE even for silent clips (E5 preflight 2026-10-05)
    g["12"] = {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": frames, "frame_rate": fps, "batch_size": 1, "audio_vae": ["99", 0]}}
    g["13"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": lat, "audio_latent": ["12", 0]}}
    g["14"] = {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": pos}}
    g["15"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    g["16"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    g["17"] = {"class_type": "LTXVScheduler", "inputs": {"steps": steps, "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": ["13", 0]}}
    g["18"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["15", 0], "guider": ["14", 0], "sampler": ["16", 0], "sigmas": ["17", 0], "latent_image": ["13", 0]}}
    g["19"] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["18", 0]}}
    g["20"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": pos, "negative": neg, "latent": ["19", 0]}}
    g["21"] = {"class_type": "VAEDecode", "inputs": {"samples": ["20", 2], "vae": ["3", 0]}}
    g["22"] = {"class_type": "CreateVideo", "inputs": {"images": ["21", 0], "fps": float(fps)}}
    g["23"] = {"class_type": "SaveVideo", "inputs": {"video": ["22", 0], "filename_prefix": f"e5/{tag}", "format": "mp4", "codec": "h264"}}
    return g


NAME_INPUTS = {"unet_name", "clip_name", "clip_name1", "clip_name2", "vae_name", "lora_name", "image"}


def fix_names(obj, graph):
    """Resolve file-name inputs by basename against each node's current enum (sub-folder files are listed with OS
    separators; uploaded images appear only after a fresh /object_info)."""
    notes = []
    for nid, node in graph.items():
        d = obj.get(node["class_type"], {}).get("input", {})
        for k, v in list(node["inputs"].items()):
            if k not in NAME_INPUTS or not isinstance(v, str): continue
            spec = d.get("required", {}).get(k) or d.get("optional", {}).get(k)
            choices = spec[0] if isinstance(spec, list) and spec and isinstance(spec[0], list) else None
            if not choices or v in choices: continue
            base = Path(v).name.lower()
            match = next((c for c in choices if Path(c.replace("\\", "/")).name.lower() == base), None)
            if match: notes.append(f"{nid} {k}: {v} -> {match}"); node["inputs"][k] = match
    return notes


def contract_check(obj, graph):
    problems = []
    for nid, node in graph.items():
        cls = node["class_type"]
        if cls not in obj:
            problems.append(f"{nid}: {cls} not registered"); continue
        d = obj[cls].get("input", {})
        allowed = set(d.get("required", {})) | set(d.get("optional", {}))
        for k in node["inputs"]:
            if k not in allowed: problems.append(f"{nid} ({cls}): unknown input '{k}' (declared {sorted(allowed)})")
        for k, spec in d.get("required", {}).items():
            if k not in node["inputs"]: problems.append(f"{nid} ({cls}): required '{k}' missing")
            elif isinstance(spec, list) and spec and isinstance(spec[0], list) and isinstance(node["inputs"][k], str) and node["inputs"][k] not in spec[0]:
                problems.append(f"{nid} ({cls}): '{k}'={node['inputs'][k]!r} not available (e.g. {spec[0][:4]})")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--tasks", default="01,03")
    ap.add_argument("--ltx-format", choices=["gguf", "fp8"], default="gguf")
    ap.add_argument("--width", type=int, default=1024); ap.add_argument("--height", type=int, default=576)
    ap.add_argument("--frames", type=int, default=121); ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--steps", type=int, default=8); ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--timeout", type=float, default=3600); ap.add_argument("--preflight", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    obj = http(a.server, "/object_info")
    if a.preflight:
        for cls in LTX_NODES: print(sig(obj, cls)[:400])
    for t in [x for x in spec["tasks"] if x["id"][:2] in a.tasks.split(",")]:
        start_p = BENCH / t["start"]; end_p = BENCH / t["end"] if t.get("end") else None
        if not start_p.exists() or (end_p and not end_p.exists()):
            print(f"[{t['id']}] missing frame(s)"); continue
        start = upload(a.server, start_p); end = upload(a.server, end_p) if end_p else None
        obj = http(a.server, "/object_info")  # refresh enums after the uploads
        tag = f"{t['id']}_ltx23_{a.ltx_format}"
        g = build(a.ltx_format, t["prompt"], start, end, a.width, a.height, a.frames, a.fps, a.steps, a.seed, tag)
        for n in fix_names(obj, g): print("   resolved", n)
        problems = contract_check(obj, g)
        row = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "task": t["id"], "kind": t["kind"], "format": a.ltx_format, "size": [a.width, a.height],
               "frames": a.frames, "fps": a.fps, "steps": a.steps, "seed": a.seed}
        if problems:
            row.update(status="contract_error", error=problems); print(f"[{t['id']}] CONTRACT:\n   " + "\n   ".join(problems)[:1500])
        elif a.preflight:
            print(f"[{t['id']}] contract OK (preflight only)"); continue
        else:
            free0 = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
            t0 = time.time()
            pid = http(a.server, "/prompt", {"prompt": g, "client_id": str(uuid.uuid4())})["prompt_id"]
            print(f"[{t['id']}] queued {pid}")
            hist = {}; t_end = time.time() + a.timeout
            while time.time() < t_end:
                hh = http(a.server, f"/history/{pid}")
                if pid in hh: hist = hh[pid]; break
                time.sleep(3)
            st = hist.get("status", {})
            msgs = {m[0]: m[1].get("timestamp") for m in st.get("messages", []) if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict)}
            exec_s = ((msgs.get("execution_success") or msgs.get("execution_error") or 0) - (msgs.get("execution_start") or 0)) / 1000
            outs = []
            for node_out in hist.get("outputs", {}).values():
                for key in ("images", "videos", "gifs"):
                    for f in node_out.get(key, []) or []:
                        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
                        dest = OUT / f"{tag}_{Path(f['filename']).name}"; dest.write_bytes(http(a.server, f"/view?{q}", timeout=600)); outs.append(str(dest))
            free1 = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
            err = [m for m in st.get("messages", []) if m[0] == "execution_error"] if st.get("status_str") != "success" else None
            row.update(status=st.get("status_str"), wall_s=round(time.time() - t0, 1), engine_exec_s=round(exec_s, 1), outputs=outs,
                       vram_free_before_gb=round(free0 / 2**30, 2), vram_free_after_gb=round(free1 / 2**30, 2), error=err)
            print(f"[{t['id']}] {row['status']} exec {row['engine_exec_s']} s → {outs[0] if outs else '-'}" + (f" ERROR {str(err)[:400]}" if err else ""))
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
