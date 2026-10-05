"""E8 inpaint bake-off driver (12 §1 E8, 04 §4 D7): run the bench/inpaint tasks through the headless engine with
several methods and record timings + outputs for scoring.

Usage (engine running):  engine/.venv/Scripts/python.exe engine/spikes/e8_inpaint.py [--methods klein_icm,...] [--tasks 01,02,...]

Methods
  klein_icm       FLUX.2 Klein 9B (distilled, cast fp8) · InpaintModelConditioning + ReferenceLatent + DifferentialDiffusion · 4 steps
  klein_base_icm  FLUX.2 Klein base 9B · same conditioning · 20 steps, CFG 3.5 (real CFG, negatives work)
  klein_lanpaint  FLUX.2 Klein 9B · LanPaint ImageEncode → Flux2Scheduler + LanPaint_SamplerCustomAdvanced → LanPaint ImageDecode
  dev_lanpaint    FLUX.2 dev fp8mixed + Turbo LoRA · LanPaint (the "Fill Hero" mode)
  fill            FLUX.1 Fill dev (official file, cast fp8) · InpaintModelConditioning · guidance 30 · 20 steps
  qwen_edit       Qwen-Image-Edit 2509 fp8 + Lightning 4-step LoRA · TextEncodeQwenImageEditPlus + LanPaint masked sampling

Images go in through POST /upload/image (the orchestrator's path; no shared folders). Masks are grey PNGs
(white = repaint) read with LoadImageMask(channel=red). Task 04 (outpaint) pads the canvas with
ImagePadForOutpaint; task 03 (matte) is skipped until a segmentation node is in the engine.
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
BENCH = REPO / "bench" / "inpaint"
OUT = REPO / "engine" / "spikes" / "out" / "e8"
RESULTS = REPO / "engine" / "spikes" / "out" / "e8_results.jsonl"


def http(server: str, path: str, data: dict | None = None, timeout: float = 120):
    req = urllib.request.Request(f"http://{server}{path}", method="POST" if data is not None else "GET")
    body = None
    if data is not None:
        body = json.dumps(data).encode(); req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, body, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw


def upload(server: str, path: Path) -> str:
    r = requests.post(f"http://{server}/upload/image", files={"image": (path.name, path.open("rb"), "image/png")},
                      data={"overwrite": "true", "type": "input"}, timeout=120)
    r.raise_for_status()
    j = r.json()
    return (j.get("subfolder") + "/" if j.get("subfolder") else "") + j["name"]


# ---------------------------------------------------------------- graph builders
# Every builder returns (graph, output_node_id). `img`/`msk` are LoadImage / LoadImageMask node ids already in g.

def common_io(g: dict, image_name: str, mask_name: str | None, outpaint: dict | None):
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    if outpaint:
        g["101"] = {"class_type": "ImagePadForOutpaint", "inputs": {"image": ["100", 0], "left": outpaint.get("left", 0), "top": outpaint.get("top", 0),
                                                                   "right": outpaint.get("right", 0), "bottom": outpaint.get("bottom", 0), "feathering": 40}}
        return ["101", 0], ["101", 1]
    g["102"] = {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}}
    return ["100", 0], ["102", 0]


def flux2_loaders(g: dict, unet: str, clip: str, weight_dtype: str = "default"):
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": weight_dtype}}
    g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "flux2", "device": "default"}}
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}


def build_icm(method: str, prompt: str, image, mask, seed: int, g: dict):
    base = method == "klein_base_icm"
    flux2_loaders(g, "flux-2-klein-base-9b.safetensors" if base else "flux-2-klein-9b.safetensors", "qwen_3_8b_fp8mixed.safetensors", "fp8_e4m3fn")
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, text, watermark" if base else "", "clip": ["2", 0]}}
    g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": image, "vae": ["3", 0]}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
    g["9"] = {"class_type": "InpaintModelConditioning", "inputs": {"positive": ["8", 0], "negative": ["6", 0], "vae": ["3", 0], "pixels": image, "mask": mask, "noise_mask": True}}
    g["10"] = {"class_type": "DifferentialDiffusion", "inputs": {"model": ["1", 0]}}
    g["11"] = {"class_type": "KSampler", "inputs": {"model": ["10", 0], "seed": seed, "steps": 20 if base else 4, "cfg": 3.5 if base else 1.0,
                                                    "sampler_name": "euler", "scheduler": "simple", "positive": ["9", 0], "negative": ["9", 1],
                                                    "latent_image": ["9", 2], "denoise": 1.0}}
    g["12"] = {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}}
    g["13"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": image, "source": ["12", 0], "x": 0, "y": 0, "resize_source": False, "mask": mask}}
    return "13"


def build_lanpaint_flux2(method: str, prompt: str, image, mask, seed: int, g: dict, w: int, h: int):
    dev = method == "dev_lanpaint"
    if dev:
        flux2_loaders(g, "flux2_dev_fp8mixed.safetensors", "mistral_3_small_flux2_fp8.safetensors")
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "Flux2TurboComfyv2.safetensors", "strength_model": 1.0}}
        model, steps, guidance = ["4", 0], 8, 4.0
    else:
        flux2_loaders(g, "flux-2-klein-9b.safetensors", "qwen_3_8b_fp8mixed.safetensors", "fp8_e4m3fn")
        model, steps, guidance = ["1", 0], 4, 1.0
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": guidance}}
    g["7"] = {"class_type": "LanPaint_ImageEncode", "inputs": {"image": image, "vae": ["3", 0], "mask": mask}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["6", 0], "latent": ["7", 0]}}
    g["9"] = {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": ["8", 0]}}
    g["10"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    g["11"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    g["12"] = {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": w, "height": h}}
    g["13"] = {"class_type": "LanPaint_SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["9", 0], "sampler": ["11", 0], "sigmas": ["12", 0],
                                                                          "latent_image": ["7", 0], "LanPaint_NumSteps": 5, "LanPaint_Lambda": 5.0,
                                                                          "LanPaint_StepSize": 0.15, "LanPaint_PromptMode": "Image First", "LanPaint_Info": "loom2 e8"}}
    g["14"] = {"class_type": "LanPaint_ImageDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0], "image": image, "mask": mask, "blend_overlap": 9}}
    return "14"


def build_fill(prompt: str, image, mask, seed: int, g: dict):
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-fill-dev.safetensors", "weight_dtype": "fp8_e4m3fn"}}
    # CLIP-L, T5 fp8 and the FLUX.1 ae come from the mounted D:\comfyui tree (sub-folder names as ComfyUI lists them)
    g["2"] = {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "clip_l.safetensors", "clip_name2": "t5/t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "flux"}}
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": "flux1/ae.safetensors"}}
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": 30.0}}
    g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    g["9"] = {"class_type": "InpaintModelConditioning", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["3", 0], "pixels": image, "mask": mask, "noise_mask": True}}
    g["11"] = {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "normal",
                                                    "positive": ["9", 0], "negative": ["9", 1], "latent_image": ["9", 2], "denoise": 1.0}}
    g["12"] = {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}}
    g["13"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": image, "source": ["12", 0], "x": 0, "y": 0, "resize_source": False, "mask": mask}}
    return "13"


def build_qwen_edit(prompt: str, image, mask, seed: int, g: dict):
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}}
    g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}}
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}}
    g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1.0}}
    g["5"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["4", 0], "shift": 3.0}}
    g["6"] = {"class_type": "CFGNorm", "inputs": {"model": ["5", 0], "strength": 1.0}}
    g["7"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0], "image1": image}}
    g["8"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": "", "vae": ["3", 0], "image1": image}}
    g["9"] = {"class_type": "LanPaint_ImageEncode", "inputs": {"image": image, "vae": ["3", 0], "mask": mask}}
    g["10"] = {"class_type": "LanPaint_KSampler", "inputs": {"model": ["6", 0], "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                             "positive": ["7", 0], "negative": ["8", 0], "latent_image": ["9", 0], "denoise": 1.0,
                                                             "LanPaint_NumSteps": 5, "LanPaint_PromptMode": "Image First", "LanPaint_Info": "loom2 e8",
                                                             "Inpainting_mode": "🖼️ Image Inpainting"}}
    g["11"] = {"class_type": "LanPaint_ImageDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0], "image": image, "mask": mask, "blend_overlap": 9}}
    return "11"


METHODS = ["klein_icm", "klein_base_icm", "klein_lanpaint", "dev_lanpaint", "fill", "qwen_edit"]


NAME_INPUTS = {"unet_name", "clip_name", "clip_name1", "clip_name2", "vae_name", "lora_name", "image"}


def fix_names(obj: dict, graph: dict) -> list[str]:
    """Resolve file-name inputs against the node's current enum by basename (ComfyUI lists sub-folder files with
    OS separators, e.g. 't5\\\\t5xxl…', and newly uploaded images only appear after a fresh /object_info)."""
    notes = []
    for nid, node in graph.items():
        d = obj.get(node["class_type"], {}).get("input", {})
        for k, v in list(node["inputs"].items()):
            if k not in NAME_INPUTS or not isinstance(v, str):
                continue
            spec = d.get("required", {}).get(k) or d.get("optional", {}).get(k)
            choices = spec[0] if isinstance(spec, list) and spec and isinstance(spec[0], list) else None
            if not choices or v in choices:
                continue
            base = Path(v).name.lower()
            match = next((c for c in choices if Path(c.replace("\\", "/")).name.lower() == base), None)
            if match:
                notes.append(f"{nid} {k}: {v} -> {match}")
                node["inputs"][k] = match
    return notes


def contract_check(obj: dict, graph: dict) -> list[str]:
    problems = []
    for nid, node in graph.items():
        cls = node["class_type"]
        if cls not in obj:
            problems.append(f"{nid}: {cls} not registered"); continue
        d = obj[cls].get("input", {})
        allowed = set(d.get("required", {})) | set(d.get("optional", {}))
        for k in node["inputs"]:
            if k not in allowed:
                problems.append(f"{nid} ({cls}): unknown input '{k}' (declared {sorted(allowed)})")
        for k, spec in d.get("required", {}).items():
            if k not in node["inputs"]:
                problems.append(f"{nid} ({cls}): required '{k}' missing")
            elif isinstance(spec, list) and spec and isinstance(spec[0], list) and isinstance(node["inputs"][k], str) and node["inputs"][k] not in spec[0]:
                problems.append(f"{nid} ({cls}): '{k}'={node['inputs'][k]!r} not available (e.g. {spec[0][:5]})")
    return problems


def wait_done(server: str, pid: str, timeout: float):
    t_end = time.time() + timeout
    while time.time() < t_end:
        h = http(server, f"/history/{pid}")
        if pid in h:
            return h[pid]
        time.sleep(1)
    raise TimeoutError


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--tasks", default="01,02,04,05")
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    src = (BENCH / spec["source"]).resolve()
    w, h = spec["size"]
    obj = http(a.server, "/object_info")
    stats = http(a.server, "/system_stats")
    print(f"engine comfyui {stats['system'].get('comfyui_version')} torch {stats['system'].get('pytorch_version')}")
    image_name = upload(a.server, src)
    print("uploaded source:", image_name)
    tasks = [t for t in spec["tasks"] if t["id"][:2] in a.tasks.split(",")]
    for t in tasks:
        mask_name = None
        if "boxes" in (t.get("mask") or {}):
            mask_name = upload(a.server, BENCH / "masks" / f"{t['id']}.png")
        obj = http(a.server, "/object_info")  # refresh: uploaded images only appear in the enums after upload
        outpaint = t.get("canvas")
        for method in a.methods.split(","):
            g: dict = {}
            image, mask = common_io(g, image_name, mask_name, outpaint)
            tw, th = (w + (outpaint or {}).get("left", 0) + (outpaint or {}).get("right", 0), h + (outpaint or {}).get("top", 0) + (outpaint or {}).get("bottom", 0))
            if method in ("klein_icm", "klein_base_icm"):
                out_id = build_icm(method, t["prompt"], image, mask, a.seed, g)
            elif method in ("klein_lanpaint", "dev_lanpaint"):
                out_id = build_lanpaint_flux2(method, t["prompt"], image, mask, a.seed, g, tw, th)
            elif method == "fill":
                out_id = build_fill(t["prompt"], image, mask, a.seed, g)
            elif method == "qwen_edit":
                out_id = build_qwen_edit(t["prompt"], image, mask, a.seed, g)
            else:
                print("unknown method", method); continue
            g["99"] = {"class_type": "SaveImage", "inputs": {"images": [out_id, 0], "filename_prefix": f"e8/{t['id']}_{method}"}}
            for n in fix_names(obj, g):
                print("   resolved", n)
            problems = contract_check(obj, g)
            row = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "task": t["id"], "method": method, "seed": a.seed, "size": [tw, th]}
            if problems:
                row.update(status="contract_error", error=problems)
                print(f"[{t['id']} {method}] CONTRACT: " + "; ".join(problems)[:600])
            else:
                free0 = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
                t0 = time.time()
                pid = http(a.server, "/prompt", {"prompt": g, "client_id": str(uuid.uuid4())})["prompt_id"]
                hist = wait_done(a.server, pid, a.timeout)
                dt = time.time() - t0
                st = hist.get("status", {})
                msgs = {m[0]: m[1].get("timestamp") for m in st.get("messages", []) if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict)}
                exec_s = (msgs.get("execution_success") or msgs.get("execution_error") or 0) - (msgs.get("execution_start") or 0)
                outs = []
                for node_out in hist.get("outputs", {}).values():
                    for im in node_out.get("images", []):
                        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
                        dest = OUT / f"{t['id']}_{method}.png"
                        dest.write_bytes(http(a.server, f"/view?{q}"))
                        outs.append(str(dest))
                free1 = (http(a.server, "/system_stats").get("devices") or [{}])[0].get("vram_free", 0)
                err = None
                if st.get("status_str") != "success":
                    err = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                row.update(status=st.get("status_str"), wall_s=round(dt, 1), engine_exec_s=round(exec_s / 1000, 1), outputs=outs,
                           vram_free_before_gb=round(free0 / 2**30, 2), vram_free_after_gb=round(free1 / 2**30, 2), error=err)
                print(f"[{t['id']} {method}] {row['status']} exec {row['engine_exec_s']} s → {outs[0] if outs else '-'}" + (f"  ERROR {str(err)[:300]}" if err else ""))
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
