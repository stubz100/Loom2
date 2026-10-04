"""E0 driver: run FLUX.2 dev text-to-image through the headless ComfyUI engine and time it.

Usage (engine venv, engine already running via scripts/engine-start.ps1):
  engine/.venv/Scripts/python.exe engine/spikes/e0_comfy_t2i.py --config gguf --runs 2
  engine/.venv/Scripts/python.exe engine/spikes/e0_comfy_t2i.py --config fp8 --turbo --steps 8 --runs 2

What it does (06 §3b in miniature):
  1. GET /system_stats and /object_info; verify every node class + input this graph needs (contract check).
  2. Build an API-format graph for the chosen weight format; the prompt is the compact JSON of a bench file,
     which ComfyUI's flux2 CLIPTextEncode wraps in BFL's Mistral [SYSTEM_PROMPT]…[INST] template.
  3. POST /prompt, follow progress on the WebSocket (if websocket-client is installed) or poll /history.
  4. Record timings from the engine's own execution timestamps, pull the PNG via /view, append a JSONL row.
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

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "engine" / "spikes" / "out"
RESULTS = OUT_DIR / "e0_t2i_results.jsonl"

CONFIGS = {
    "gguf": {
        "unet": ("UnetLoaderGGUF", {"unet_name": "flux2-dev-Q4_K_M.gguf"}),
        "clip": ("CLIPLoaderGGUF", {"clip_name": "Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf", "type": "flux2"}),
    },
    "fp8": {
        "unet": ("UNETLoader", {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"}),
        "clip": ("CLIPLoader", {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2"}),
    },
    # GGUF transformer + Comfy fp8 text encoder: sidesteps the ComfyUI-GGUF tekken-tokenizer gap (E0 finding 1)
    "gguf-fp8te": {
        "unet": ("UnetLoaderGGUF", {"unet_name": "flux2-dev-Q4_K_M.gguf"}),
        "clip": ("CLIPLoader", {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2"}),
    },
}
NEEDED = ["VAELoader", "CLIPTextEncode", "FluxGuidance", "ConditioningZeroOut", "EmptyFlux2LatentImage",
          "KSampler", "VAEDecode", "SaveImage", "LoraLoaderModelOnly"]


def http(server: str, path: str, data: dict | None = None, timeout: float = 60) -> dict | bytes:
    url = f"http://{server}{path}"
    req = urllib.request.Request(url, method="POST" if data is not None else "GET")
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, body, timeout=timeout) as r:
        raw = r.read()
    if r.headers.get("Content-Type", "").startswith("application/json"):
        return json.loads(raw)
    return raw


def build_graph(cfg: str, prompt: str, w: int, h: int, seed: int, steps: int, guidance: float,
                sampler: str, scheduler: str, turbo: bool, tag: str, obj: dict, te_device: str = "default") -> dict:
    c = CONFIGS[cfg]
    unet_cls, unet_in = c["unet"]
    clip_cls, clip_in = c["clip"]
    clip_in = dict(clip_in)
    # CLIPLoader gained an optional "device" input in newer versions; only pass it if the node declares it.
    if "device" in obj.get(clip_cls, {}).get("input", {}).get("optional", {}):
        clip_in["device"] = te_device
    g = {
        "1": {"class_type": unet_cls, "inputs": unet_in},
        "2": {"class_type": clip_cls, "inputs": clip_in},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": guidance}},
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "8": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": steps, "cfg": 1.0,
                                                   "sampler_name": sampler, "scheduler": scheduler,
                                                   "positive": ["6", 0], "negative": ["7", 0],
                                                   "latent_image": ["8", 0], "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": f"e0/{tag}"}},
    }
    if turbo:
        g["4"] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"model": ["1", 0], "lora_name": "Flux2TurboComfyv2.safetensors", "strength_model": 1.0}}
        g["9"]["inputs"]["model"] = ["4", 0]
    return g


def contract_check(obj: dict, graph: dict) -> list[str]:
    problems = []
    for nid, node in graph.items():
        cls = node["class_type"]
        if cls not in obj:
            problems.append(f"node {nid}: class {cls} not registered")
            continue
        declared = obj[cls].get("input", {})
        allowed = set(declared.get("required", {})) | set(declared.get("optional", {}))
        for k in node["inputs"]:
            if k not in allowed:
                problems.append(f"node {nid} ({cls}): input '{k}' unknown; declared {sorted(allowed)}")
        for k, spec in declared.get("required", {}).items():
            if k not in node["inputs"]:
                problems.append(f"node {nid} ({cls}): required input '{k}' missing")
            elif isinstance(spec, list) and spec and isinstance(spec[0], list) and isinstance(node["inputs"][k], str):
                if node["inputs"][k] not in spec[0]:
                    problems.append(f"node {nid} ({cls}): '{k}'={node['inputs'][k]!r} not in choices "
                                    f"({len(spec[0])} options, e.g. {spec[0][:6]})")
    return problems


def follow(server: str, client_id: str, prompt_id: str, timeout_s: float) -> dict:
    """Follow execution on the WebSocket if possible; return per-node and per-step timing."""
    info = {"ws": False, "nodes": {}, "steps": [], "error": None}
    try:
        import websocket  # type: ignore
    except ImportError:
        return info
    info["ws"] = True
    ws = websocket.create_connection(f"ws://{server}/ws?clientId={client_id}", timeout=timeout_s)
    t_end = time.time() + timeout_s
    try:
        while time.time() < t_end:
            msg = ws.recv()
            if not isinstance(msg, str):
                continue
            m = json.loads(msg)
            t, d = m.get("type"), m.get("data", {})
            if d.get("prompt_id") not in (None, prompt_id):
                continue
            now = time.time()
            if t == "executing":
                node = d.get("node")
                if node is None:
                    break  # finished
                info["nodes"].setdefault(node, {})["start"] = now
            elif t == "progress":
                info["steps"].append((now, d.get("value"), d.get("max"), d.get("node")))
            elif t == "execution_error":
                info["error"] = d
                break
            elif t == "execution_success":
                break
    finally:
        ws.close()
    return info


def wait_history(server: str, prompt_id: str, timeout_s: float) -> dict:
    t_end = time.time() + timeout_s
    while time.time() < t_end:
        hist = http(server, f"/history/{prompt_id}")
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(1.0)
    raise TimeoutError("history never reported the prompt")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--config", choices=CONFIGS, default="gguf")
    ap.add_argument("--prompt-file", default=str(REPO / "bench" / "t2i" / "01-alley-rain.json"))
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=544)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--guidance", type=float, default=4.0)
    ap.add_argument("--sampler", default="res_multistep")
    ap.add_argument("--scheduler", default="sgm_uniform")
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--turbo", action="store_true", help="apply the Comfy Flux2 Turbo LoRA")
    ap.add_argument("--te-device", choices=["default", "cpu"], default="default",
                    help="CLIPLoader device: 'cpu' keeps the text encoder off the GPU so the transformer stays resident")
    ap.add_argument("--runs", type=int, default=1, help="repeat with seed+i (run 1 = cold, run 2 = warm)")
    ap.add_argument("--timeout", type=float, default=3600)
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_obj = json.loads(Path(a.prompt_file).read_text(encoding="utf-8"))
    prompt = json.dumps(prompt_obj, ensure_ascii=False, separators=(",", ":"))
    print(f"prompt: {len(prompt)} chars, ~{len(prompt.split())} words (compact JSON)")

    stats = http(a.server, "/system_stats")
    sysinfo = stats.get("system", {})
    dev0 = (stats.get("devices") or [{}])[0]
    print(f"engine: comfyui {sysinfo.get('comfyui_version')} | torch {sysinfo.get('pytorch_version')} | "
          f"{dev0.get('name')} vram_total {dev0.get('vram_total', 0)/2**30:.1f} GB free {dev0.get('vram_free', 0)/2**30:.1f} GB")
    obj = http(a.server, "/object_info")
    missing = [n for n in NEEDED + [CONFIGS[a.config]['unet'][0], CONFIGS[a.config]['clip'][0]] if n not in obj]
    if missing:
        print("FAIL: missing node classes:", missing)
        return 2

    tag = f"{a.config}{'-turbo' if a.turbo else ''}{'-tecpu' if a.te_device == 'cpu' else ''}-{a.steps}st-{a.width}x{a.height}"
    for i in range(a.runs):
        seed = a.seed + i
        graph = build_graph(a.config, prompt, a.width, a.height, seed, a.steps, a.guidance, a.sampler,
                            a.scheduler, a.turbo, tag, obj, a.te_device)
        problems = contract_check(obj, graph)
        if problems:
            print("FAIL: graph contract problems:\n  " + "\n  ".join(problems))
            return 3
        client_id = str(uuid.uuid4())
        free_before = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
        t_submit = time.time()
        resp = http(a.server, "/prompt", {"prompt": graph, "client_id": client_id})
        prompt_id = resp["prompt_id"]
        print(f"[run {i+1}/{a.runs}] seed {seed} queued as {prompt_id}")
        live = follow(a.server, client_id, prompt_id, a.timeout)
        hist = wait_history(a.server, prompt_id, a.timeout)
        t_done = time.time()
        status = hist.get("status", {})
        msgs = status.get("messages", [])
        ts = {m[0]: m[1].get("timestamp") for m in msgs if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict)}
        exec_ms = None
        if ts.get("execution_start") and (ts.get("execution_success") or ts.get("execution_error")):
            exec_ms = (ts.get("execution_success") or ts.get("execution_error")) - ts["execution_start"]
        steps = live["steps"]
        sample_s = (steps[-1][0] - steps[0][0]) if len(steps) >= 2 else None
        outputs = []
        for node_out in hist.get("outputs", {}).values():
            for img in node_out.get("images", []):
                q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                            "type": img.get("type", "output")})
                data = http(a.server, f"/view?{q}")
                dest = OUT_DIR / f"e0_{tag}_s{seed}.png"
                dest.write_bytes(data)
                outputs.append(str(dest))
        free_after = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
        row = {
            "when": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": a.config, "turbo": a.turbo, "steps": a.steps, "guidance": a.guidance,
            "sampler": a.sampler, "scheduler": a.scheduler, "size": [a.width, a.height], "seed": seed,
            "run_index": i + 1, "status": status.get("status_str"),
            "wall_s": round(t_done - t_submit, 1),
            "engine_exec_s": round(exec_ms / 1000, 1) if exec_ms else None,
            "sampling_s_first_to_last_step": round(sample_s, 1) if sample_s else None,
            "steps_seen": len(steps), "ws": live["ws"],
            "vram_free_before_gb": round(free_before / 2**30, 2), "vram_free_after_gb": round(free_after / 2**30, 2),
            "comfyui": sysinfo.get("comfyui_version"), "torch": sysinfo.get("pytorch_version"),
            "outputs": outputs, "error": live["error"] or (status if status.get("status_str") != "success" else None),
        }
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, indent=2, ensure_ascii=False))
        if row["status"] != "success":
            return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
