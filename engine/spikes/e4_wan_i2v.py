"""E4 driver: Wan 2.2 I2V-A14B (GGUF Q5_K_M, high + low experts) through the headless engine — start-image + prompt,
and first/last-frame (FLF) on the same weights (12 §1 E4, 04 §5b D8).

Usage (engine running):
  engine/.venv/Scripts/python.exe engine/spikes/e4_wan_i2v.py [--tasks 01,03] [--recipe lightning|quality] [--frames 81]

Recipes
  lightning  4 steps total (high expert steps 0-2, low expert 2-4), cfg 1.0, Lightning 4-step LoRAs (high 0.7, low 1.0), shift 5
  quality    20 steps (10 + 10), cfg 3.5, no LoRA, shift 8 — slow; use for one task only
  lightning44  E4b: 8 steps (4 + 4), Lightning LoRAs on both experts, cfg 1, shift 5
  motion       E4b: 8 steps; high expert WITHOUT the LoRA at cfg 3.5 (0-4) for motion, low expert with the LoRA at cfg 1 (4-8)
Graph follows ComfyUI's Wan 2.2 14B i2v / flf2v templates: WanImageToVideo / WanFirstLastFrameToVideo →
KSamplerAdvanced (high) → KSamplerAdvanced (low) → VAEDecode → CreateVideo → SaveVideo (mp4, h264).
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
OUT = REPO / "engine" / "spikes" / "out" / "e4"
RESULTS = REPO / "engine" / "spikes" / "out" / "e4_results.jsonl"
NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
       "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")


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


def build(recipe: str, prompt: str, start: str, end: str | None, w: int, h: int, frames: int, fps: int, seed: int, tag: str) -> dict:
    g = {
        "1h": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf"}},
        "1l": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}},
        "100": {"class_type": "LoadImage", "inputs": {"image": start}},
        "110": {"class_type": "ImageScale", "inputs": {"image": ["100", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}},
    }
    if recipe in ("lightning", "lightning44", "motion"):
        g["4h"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1h", 0], "lora_name": "Wan2.2-I2V-A14B-Lightning-4steps-high.safetensors", "strength_model": 0.7}}
        g["4l"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1l", 0], "lora_name": "Wan2.2-I2V-A14B-Lightning-4steps-low.safetensors", "strength_model": 1.0}}
    if recipe == "lightning":
        mh, ml, steps, split, cfg_h, cfg_l, shift = ["4h", 0], ["4l", 0], 4, 2, 1.0, 1.0, 5.0
    elif recipe == "lightning44":   # E4b: twice the steps, LoRAs on both experts
        mh, ml, steps, split, cfg_h, cfg_l, shift = ["4h", 0], ["4l", 0], 8, 4, 1.0, 1.0, 5.0
    elif recipe == "motion":        # E4b: high expert without the LoRA at real CFG (motion), low expert distilled
        mh, ml, steps, split, cfg_h, cfg_l, shift = ["1h", 0], ["4l", 0], 8, 4, 3.5, 1.0, 5.0
    else:
        mh, ml, steps, split, cfg_h, cfg_l, shift = ["1h", 0], ["1l", 0], 20, 10, 3.5, 3.5, 8.0
    g["8h"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": mh, "shift": shift}}
    g["8l"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": ml, "shift": shift}}
    cond = {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": w, "height": h, "length": frames, "batch_size": 1, "start_image": ["110", 0]}
    if end:
        g["101"] = {"class_type": "LoadImage", "inputs": {"image": end}}
        g["111"] = {"class_type": "ImageScale", "inputs": {"image": ["101", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        cond["end_image"] = ["111", 0]
        g["7"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": cond}
    else:
        g["7"] = {"class_type": "WanImageToVideo", "inputs": cond}
    g["9"] = {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8h", 0], "add_noise": "enable", "noise_seed": seed, "steps": steps, "cfg": cfg_h, "sampler_name": "euler",
                                                          "scheduler": "simple", "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["7", 2],
                                                          "start_at_step": 0, "end_at_step": split, "return_with_leftover_noise": "enable"}}
    g["10"] = {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8l", 0], "add_noise": "disable", "noise_seed": seed, "steps": steps, "cfg": cfg_l, "sampler_name": "euler",
                                                           "scheduler": "simple", "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["9", 0],
                                                           "start_at_step": split, "end_at_step": 10000, "return_with_leftover_noise": "disable"}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["12"] = {"class_type": "CreateVideo", "inputs": {"images": ["11", 0], "fps": fps}}
    g["13"] = {"class_type": "SaveVideo", "inputs": {"video": ["12", 0], "filename_prefix": f"e4/{tag}", "format": "mp4", "codec": "h264"}}
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
            if k not in allowed: problems.append(f"{nid} ({cls}): unknown input '{k}'")
        for k, spec in d.get("required", {}).items():
            if k not in node["inputs"]: problems.append(f"{nid} ({cls}): required '{k}' missing")
            elif isinstance(spec, list) and spec and isinstance(spec[0], list) and isinstance(node["inputs"][k], str) and node["inputs"][k] not in spec[0]:
                problems.append(f"{nid} ({cls}): '{k}'={node['inputs'][k]!r} not available (e.g. {spec[0][:4]})")
    return problems


def follow(server, client_id, prompt_id, timeout):
    info = {"nodes": {}, "steps": [], "error": None}
    try:
        import websocket
    except ImportError:
        return info
    ws = websocket.create_connection(f"ws://{server}/ws?clientId={client_id}", timeout=timeout)
    t_end = time.time() + timeout
    try:
        while time.time() < t_end:
            msg = ws.recv()
            if not isinstance(msg, str): continue
            m = json.loads(msg); t, d = m.get("type"), m.get("data", {})
            if d.get("prompt_id") not in (None, prompt_id): continue
            now = time.time()
            if t == "executing":
                if d.get("node") is None: break
                info["nodes"].setdefault(d["node"], {})["start"] = now
            elif t == "progress": info["steps"].append((now, d.get("value"), d.get("max"), d.get("node")))
            elif t == "execution_error": info["error"] = d; break
            elif t == "execution_success": break
    finally:
        ws.close()
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--tasks", default="01,02,03,04,05")
    ap.add_argument("--recipe", choices=["lightning", "quality", "lightning44", "motion"], default="lightning")
    ap.add_argument("--width", type=int, default=832); ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--frames", type=int, default=81); ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--seed", type=int, default=20261005); ap.add_argument("--timeout", type=float, default=3600)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    obj = http(a.server, "/object_info")
    stats = http(a.server, "/system_stats")
    print(f"engine comfyui {stats['system'].get('comfyui_version')} torch {stats['system'].get('pytorch_version')}")
    for t in [x for x in spec["tasks"] if x["id"][:2] in a.tasks.split(",")]:
        start_p = BENCH / t["start"]; end_p = BENCH / t["end"] if t.get("end") else None
        if not start_p.exists() or (end_p and not end_p.exists()):
            print(f"[{t['id']}] missing frame(s): {start_p.name}{' / ' + end_p.name if end_p else ''}"); continue
        start = upload(a.server, start_p); end = upload(a.server, end_p) if end_p else None
        obj = http(a.server, "/object_info")  # refresh enums after the uploads
        tag = f"{t['id']}_{a.recipe}"
        g = build(a.recipe, t["prompt"], start, end, a.width, a.height, a.frames, a.fps, a.seed, tag)
        for n in fix_names(obj, g): print("   resolved", n)
        problems = contract_check(obj, g)
        row = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "task": t["id"], "kind": t["kind"], "recipe": a.recipe, "size": [a.width, a.height],
               "frames": a.frames, "fps": a.fps, "seed": a.seed}
        if problems:
            row.update(status="contract_error", error=problems); print(f"[{t['id']}] CONTRACT: " + "; ".join(problems)[:600])
        else:
            free0 = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
            cid = str(uuid.uuid4()); t0 = time.time()
            pid = http(a.server, "/prompt", {"prompt": g, "client_id": cid})["prompt_id"]
            print(f"[{t['id']} {a.recipe}] queued {pid}")
            live = follow(a.server, cid, pid, a.timeout)
            t_end = time.time() + 600
            hist = {}
            while time.time() < t_end:
                hh = http(a.server, f"/history/{pid}")
                if pid in hh: hist = hh[pid]; break
                time.sleep(2)
            t_done = time.time()
            st = hist.get("status", {})
            msgs = {m[0]: m[1].get("timestamp") for m in st.get("messages", []) if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict)}
            exec_s = ((msgs.get("execution_success") or msgs.get("execution_error") or 0) - (msgs.get("execution_start") or 0)) / 1000
            starts = sorted(((v["start"], k) for k, v in live["nodes"].items() if "start" in v))
            node_s = {f"{k}:{g[k]['class_type']}" if k in g else k: round(tb - ta, 1) for (ta, k), (tb, _) in zip(starts, starts[1:] + [(t_done, "end")])}
            outs = []
            for node_out in hist.get("outputs", {}).values():
                for key in ("images", "videos", "gifs"):
                    for f in node_out.get(key, []) or []:
                        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
                        dest = OUT / f"{tag}_{Path(f['filename']).name}"
                        dest.write_bytes(http(a.server, f"/view?{q}", timeout=600)); outs.append(str(dest))
            free1 = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
            steps = live["steps"]
            row.update(status=st.get("status_str"), wall_s=round(t_done - t0, 1), engine_exec_s=round(exec_s, 1),
                       sampling_s=round(steps[-1][0] - steps[0][0], 1) if len(steps) > 1 else None, steps_seen=len(steps), node_s=node_s,
                       vram_free_before_gb=round(free0 / 2**30, 2), vram_free_after_gb=round(free1 / 2**30, 2), outputs=outs,
                       error=live["error"] or (st if st.get("status_str") != "success" else None))
            print(f"[{t['id']} {a.recipe}] {row['status']} exec {row['engine_exec_s']} s sampling {row['sampling_s']} s → {outs[0] if outs else '-'}" + (f" ERROR {str(row['error'])[:300]}" if row["error"] else ""))
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
