"""Recipe → ComfyUI API graph (06 §3b, the recipe compiler). One builder per recipe kind; every builder resolves
roster ids through the `Roster`, never types a file name, and the result is contract-checked against
`/object_info` before submission. M3: T2I on FLUX.2 dev (JSON through the Mistral template) and Klein (prose),
with Turbo / LoRA chains, reference images and an exact serialisation preview (09 §3a).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..recipes import FLUX2_SCHEDULE, SAMPLERS, SCHEDULERS, TE_DEVICES, WEIGHT_DTYPES, T2I, I2I, Inpaint, I2V, LoraRef, Segment, Upscale
from ..edit_ai import plan_tiles
from ..roster import Roster
from .contract import check_graph, resolve_names


@dataclass
class ModelPreset:
    te_id: str
    vae_id: str = "flux2-vae"
    steps: int = 20
    guidance: float = 4.0
    cfg: float = 1.0
    weight_dtype: str = "default"
    distilled: bool = False          # distilled Klein: 4 steps, CFG 1, no negative
    turbo_lora: str | None = None    # dev: Flux2TurboComfyv2 (8 steps)
    turbo_steps: int = 8
    json_prompt: bool = True         # dev takes the BFL JSON verbatim (Mistral template); Klein wants prose
    sampler: str = "euler"
    scheduler: str = "simple"
    max_refs: int = 4
    label: str = ""


PRESETS: dict[str, ModelPreset] = {
    "flux2-dev-fp8mixed": ModelPreset(te_id="mistral3-small-flux2-fp8", steps=20, guidance=4.0, turbo_lora="flux2-turbo-lora", max_refs=10, label="FLUX.2 dev · JSON"),
    "klein-4b": ModelPreset(te_id="qwen3-4b", steps=4, guidance=1.0, weight_dtype="fp8_e4m3fn", distilled=True, json_prompt=False, label="Klein 4B"),
    "klein-base-4b": ModelPreset(te_id="qwen3-4b", steps=20, guidance=1.0, cfg=3.5, weight_dtype="fp8_e4m3fn", json_prompt=False, label="Klein 4B base"),
    "klein-9b": ModelPreset(te_id="qwen3-8b-fp8mixed", steps=4, guidance=1.0, weight_dtype="fp8_e4m3fn", distilled=True, json_prompt=False, label="Klein 9B"),
    "klein-base-9b": ModelPreset(te_id="qwen3-8b-fp8mixed", steps=20, guidance=1.0, cfg=3.5, weight_dtype="fp8_e4m3fn", json_prompt=False, label="Klein 9B base"),
    "klein-9b-kv": ModelPreset(te_id="qwen3-8b-fp8mixed", steps=4, guidance=1.0, weight_dtype="fp8_e4m3fn", distilled=True, json_prompt=False, label="Klein 9B KV"),
}

# VRAM estimates (GB) for the queue's admission check (06 §3d `Engine.estimate`); measured peaks from the spikes
VRAM_ESTIMATE_GB: dict[str, float] = {
    "flux2-dev-fp8mixed": 14.0, "klein-4b": 8.5, "klein-base-4b": 9.2, "klein-9b": 15.0, "klein-base-9b": 15.0, "klein-9b-kv": 15.0,
    "wan22-i2v-high-fp8": 14.5, "ltx23-distilled-fp8": 14.0, "realesrgan-x2": 2.0, "realesrgan-x4": 2.5,
    "sam3": 5.0, "birefnet": 2.5,
}

# Seconds per image at 960×544 from the spikes (E0, E8), used until the project has its own history
BASE_SECONDS: dict[tuple[str, bool], float] = {
    ("flux2-dev-fp8mixed", False): 65.0, ("flux2-dev-fp8mixed", True): 40.0,
    ("klein-4b", False): 10.0, ("klein-base-4b", False): 30.0, ("klein-9b", False): 18.0, ("klein-base-9b", False): 50.0, ("klein-9b-kv", False): 18.0,
}


class CompileError(ValueError):
    pass


@dataclass
class Compiled:
    graph: dict[str, Any]
    output_node: str
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    graph_hash: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    serialized_prompt: str = ""


def flatten_json_prompt(p: dict | list | str | int | float | None, depth: int = 0) -> str:
    """BFL tree → prose for Klein (04 §3c: subject + action + style + context; keys become light structure)."""
    if p is None:
        return ""
    if isinstance(p, (str, int, float)):
        return str(p)
    if isinstance(p, list):
        return ", ".join(flatten_json_prompt(x, depth + 1) for x in p if x not in (None, ""))
    parts = []
    for k, v in p.items():
        text = flatten_json_prompt(v, depth + 1)
        if not text:
            continue
        parts.append(f"{k}: {text}" if depth == 0 else text)
    return ". ".join(parts) if depth == 0 else ", ".join(parts)


def serialize_prompt(recipe: T2I, preset: ModelPreset | None = None) -> tuple[str, str]:
    """The exact string the engine receives and how it was produced: 'json' | 'prose' | 'text'."""
    preset = preset or PRESETS.get(recipe.model_id) or PRESETS["flux2-dev-fp8mixed"]
    if recipe.prompt_mode in ("tree", "json") and recipe.prompt_json:
        tree = {k: v for k, v in recipe.prompt_json.items() if v not in (None, "", [], {})}
        if preset.json_prompt:
            return json.dumps(tree, ensure_ascii=False, separators=(",", ":")), "json"
        prose = flatten_json_prompt(tree)
        return (f"{recipe.prompt_text.strip()}. {prose}" if recipe.prompt_text.strip() else prose), "prose"
    return recipe.prompt_text.strip(), "text"


def word_count(text: str) -> int:
    return len([w for w in text.replace("{", " ").replace("}", " ").replace('"', " ").split() if w.strip(",.:;")])


def _mult16(n: int) -> int:
    return max(16, int(round(n / 16.0)) * 16)


def _lora_chain(g: dict, model_link: list, loras: list[LoraRef], roster: Roster, first_id: int) -> tuple[list, int]:
    nid = first_id
    for ref in loras:
        _, name = roster.require(ref.model_id)
        g[str(nid)] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_link, "lora_name": name, "strength_model": float(ref.strength)}}
        model_link = [str(nid), 0]
        nid += 1
    return model_link, nid


def effective_params(recipe: T2I) -> dict[str, Any]:
    """What will actually run (the UI shows exactly this: 07 §1.4 'display == reality'). A sampler, scheduler, weight
    dtype or encoder device the engine does not offer is an error here — never a silent fall-back to the preset."""
    preset = PRESETS.get(recipe.model_id)
    if preset is None:
        raise CompileError(f"no T2I preset for model '{recipe.model_id}'")
    turbo = bool(recipe.turbo and preset.turbo_lora)
    steps = recipe.steps if recipe.steps else (preset.turbo_steps if turbo else preset.steps)
    if preset.distilled:
        steps = preset.steps                                  # fixed for distilled variants (09 §3b)
    guidance = recipe.guidance if recipe.guidance is not None else preset.guidance
    cfg = preset.cfg if preset.distilled else (recipe.cfg if recipe.cfg is not None else preset.cfg)
    sampler = recipe.sampler or preset.sampler
    if sampler not in SAMPLERS:
        raise CompileError(f"unknown sampler {sampler!r} (the pinned engine offers {len(SAMPLERS)})")
    scheduler = recipe.scheduler or preset.scheduler
    if scheduler not in SCHEDULERS and scheduler != FLUX2_SCHEDULE:
        raise CompileError(f"unknown scheduler {scheduler!r}")
    weight_dtype = recipe.weight_dtype or preset.weight_dtype
    if weight_dtype not in WEIGHT_DTYPES:
        raise CompileError(f"unknown weight dtype {weight_dtype!r}")
    te_device = recipe.te_device or "default"
    if te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    shift = recipe.base_shift is not None or recipe.max_shift is not None
    base_shift = recipe.base_shift if recipe.base_shift is not None else (0.5 if shift else None)      # ModelSamplingFlux node defaults
    max_shift = recipe.max_shift if recipe.max_shift is not None else (1.15 if shift else None)
    w, h = _mult16(recipe.width), _mult16(recipe.height)
    if w * h > 4_200_000 or w < 64 or h < 64:
        raise CompileError(f"size {w}×{h} outside the 64 px – 4 MP range")
    text, mode = serialize_prompt(recipe, preset)
    return {"model_id": recipe.model_id, "te_id": preset.te_id, "width": w, "height": h, "steps": steps, "guidance": guidance, "cfg": cfg,
            "sampler": sampler, "scheduler": scheduler, "turbo": turbo, "turbo_strength": float(recipe.turbo_strength) if turbo else None,
            "distilled": preset.distilled, "negative_used": bool(recipe.negative) and not preset.distilled,
            "weight_dtype": weight_dtype, "te_device": te_device, "base_shift": base_shift, "max_shift": max_shift,
            "tiled_vae": bool(recipe.tiled_vae), "tile_size": int(recipe.tile_size) if recipe.tiled_vae else None,
            "prompt_mode": mode, "serialized_prompt": text, "word_count": word_count(text), "token_estimate": int(word_count(text) * 1.4) + 8,
            "refs": min(len(recipe.refs), preset.max_refs), "max_refs": preset.max_refs, "loras": [l.model_dump() for l in recipe.loras]}


def build_t2i(recipe: T2I, roster: Roster, seed: int, out_prefix: str, ref_files: dict[str, str] | None = None) -> Compiled:
    preset = PRESETS[recipe.model_id] if recipe.model_id in PRESETS else None
    if preset is None:
        raise CompileError(f"no T2I preset for model '{recipe.model_id}'")
    ep = effective_params(recipe)
    _, unet = roster.require(recipe.model_id)
    _, te = roster.require(preset.te_id)
    _, vae = roster.require(preset.vae_id)
    text = ep["serialized_prompt"]
    if not text.strip():
        raise CompileError("empty prompt")
    w, h = ep["width"], ep["height"]

    g: dict[str, Any] = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": ep["weight_dtype"]}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "flux2", "device": ep["te_device"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["2", 0]}},
        "8": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}},
    }
    # decode: plain, or tiled for headroom on the Full tier (D13)
    if ep["tiled_vae"]:
        g["10"] = {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["9", 0], "vae": ["3", 0], "tile_size": int(ep["tile_size"]), "overlap": min(64, int(ep["tile_size"]) // 4),
                                                              "temporal_size": 64, "temporal_overlap": 8}}
    else:
        g["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}}
    # reference images: LoadImage → (downscale) → VAEEncode → ReferenceLatent chained on the conditioning
    cond: list = ["5", 0]
    nid = 30
    ref_files = ref_files or {}
    for i, ref in enumerate(recipe.refs[: preset.max_refs]):
        key = ref.asset_id or ref.blob or ""
        name = ref_files.get(key)
        if not name:
            raise CompileError(f"reference {i + 1} ({key}) was not uploaded to the engine")
        g[str(nid)] = {"class_type": "LoadImage", "inputs": {"image": name}}
        img: list = [str(nid), 0]
        nid += 1
        if recipe.ref_max_px:
            g[str(nid)] = {"class_type": "ImageScale", "inputs": {"image": img, "upscale_method": "lanczos", "width": int(recipe.ref_max_px), "height": int(recipe.ref_max_px), "crop": "disabled"}}
            # ImageScale needs both sizes; the orchestrator pre-fits references to ≤ ref_max_px² before upload, so this is a no-op guard
            img = [str(nid), 0]
            nid += 1
        g[str(nid)] = {"class_type": "VAEEncode", "inputs": {"pixels": img, "vae": ["3", 0]}}
        lat = [str(nid), 0]
        nid += 1
        g[str(nid)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": cond, "latent": lat}}
        cond = [str(nid), 0]
        nid += 1
    g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": cond, "guidance": float(ep["guidance"])}}
    if ep["negative_used"]:
        g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative, "clip": ["2", 0]}}
    else:
        g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    model_link: list = ["1", 0]
    if ep["base_shift"] is not None:                          # resolution-dependent shift instead of the model's constant (FLUX.2: 2.02)
        g["12"] = {"class_type": "ModelSamplingFlux", "inputs": {"model": model_link, "max_shift": float(ep["max_shift"]), "base_shift": float(ep["base_shift"]), "width": w, "height": h}}
        model_link = ["12", 0]
    if ep["turbo"]:
        _, lora = roster.require(preset.turbo_lora)  # type: ignore[arg-type]
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_link, "lora_name": lora, "strength_model": float(ep["turbo_strength"])}}
        model_link = ["4", 0]
    model_link, nid = _lora_chain(g, model_link, recipe.loras, roster, nid)     # B11: after the reference nodes, never over them
    if ep["scheduler"] == FLUX2_SCHEDULE:
        # BFL's resolution-shifted sigmas (Flux2Scheduler) need the custom sampler path; CFG > 1 keeps the negative through CFGGuider
        g["13"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": int(seed)}}
        g["14"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": ep["sampler"]}}
        g["15"] = {"class_type": "Flux2Scheduler", "inputs": {"steps": int(ep["steps"]), "width": w, "height": h}}
        if float(ep["cfg"]) > 1.0:
            g["16"] = {"class_type": "CFGGuider", "inputs": {"model": model_link, "positive": ["6", 0], "negative": ["7", 0], "cfg": float(ep["cfg"])}}
        else:
            g["16"] = {"class_type": "BasicGuider", "inputs": {"model": model_link, "conditioning": ["6", 0]}}
        g["9"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["13", 0], "guider": ["16", 0], "sampler": ["14", 0], "sigmas": ["15", 0], "latent_image": ["8", 0]}}
    else:
        g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": int(ep["steps"]), "cfg": float(ep["cfg"]),
                                                     "sampler_name": ep["sampler"], "scheduler": ep["scheduler"], "positive": ["6", 0], "negative": ["7", 0],
                                                     "latent_image": ["8", 0], "denoise": 1.0}}
    summary = {k: v for k, v in ep.items() if k != "serialized_prompt"}
    return Compiled(graph=g, output_node="11", summary=summary, serialized_prompt=text)


# ---- M5 edit recipes (10 §4, D7; graphs ported from engine/spikes/e8_inpaint.py) ------------------------------
def _flux2_loaders(g: dict[str, Any], roster: Roster, model_id: str, preset: ModelPreset) -> list:
    """UNET / text encoder / VAE loaders for a FLUX.2-family model; returns the model link (Turbo LoRA for dev)."""
    _, unet = roster.require(model_id)
    _, te = roster.require(preset.te_id)
    _, vae = roster.require(preset.vae_id)
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": preset.weight_dtype}}
    g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "flux2", "device": "default"}}
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
    if preset.turbo_lora:
        _, lora = roster.require(preset.turbo_lora)
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}}
        return ["4", 0]
    return ["1", 0]


def inpaint_model_id(recipe: Inpaint) -> str:
    if recipe.mode == "fill_hero":
        return "flux2-dev-fp8mixed"
    if recipe.mode in ("fill_match", "remove"):
        return recipe.model_id if recipe.model_id.startswith("klein") and "base" not in recipe.model_id else "klein-9b"
    return recipe.model_id


def build_inpaint(recipe: Inpaint, roster: Roster, seed: int, out_prefix: str, image_name: str, mask_name: str, w: int, h: int) -> Compiled:
    model_id = inpaint_model_id(recipe)
    preset = PRESETS.get(model_id)
    if preset is None:
        raise CompileError(f"no preset for inpaint model '{model_id}'")
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, model_id, preset)
    dev = model_id == "flux2-dev-fp8mixed"
    prompt = recipe.prompt_text.strip()
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["102"] = {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}}
    image, mask = ["100", 0], ["102", 0]
    summary: dict[str, Any] = {"mode": recipe.mode, "model_id": model_id, "width": w, "height": h, "seed": int(seed), "feather": recipe.feather, "margin_pct": recipe.margin_pct}
    if recipe.mode in ("fill", "fill_hero", "outpaint"):
        # LanPaint: image-encode with the mask, ReferenceLatent of the same image, custom sampler with LanPaint steps
        steps, guidance = (8, 4.0) if dev else (int(preset.steps), float(preset.guidance))
        prompt_first = recipe.prompt_mode == "prompt_first"
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
        g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": guidance}}
        g["7"] = {"class_type": "LanPaint_ImageEncode", "inputs": {"image": image, "vae": ["3", 0], "mask": mask}}
        g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["6", 0], "latent": ["7", 0]}}
        g["9"] = {"class_type": "BasicGuider", "inputs": {"model": model_link, "conditioning": ["8", 0]}}
        g["10"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": int(seed)}}
        g["11"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        g["12"] = {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": w, "height": h}}
        g["13"] = {"class_type": "LanPaint_SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["9", 0], "sampler": ["11", 0], "sigmas": ["12", 0],
                                                                              "latent_image": ["7", 0], "LanPaint_NumSteps": 5, "LanPaint_Lambda": 8.0 if prompt_first else 5.0,
                                                                              "LanPaint_StepSize": 0.15, "LanPaint_PromptMode": "Prompt First" if prompt_first else "Image First", "LanPaint_Info": "loom2"}}
        g["14"] = {"class_type": "LanPaint_ImageDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0], "image": image, "mask": mask, "blend_overlap": 9}}
        out = "14"
        summary |= {"sampler": "lanpaint", "steps": steps, "guidance": guidance, "lambda": 8.0 if prompt_first else 5.0, "prompt_mode": recipe.prompt_mode}
    else:
        # ICM: InpaintModelConditioning + ReferenceLatent (+ the hole neutralised to mid grey for Remove, E8b / Q17)
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}}
        ref_pixels: list = image
        if recipe.mode == "remove":
            g["15"] = {"class_type": "EmptyImage", "inputs": {"width": w, "height": h, "batch_size": 1, "color": 0x808080}}
            g["16"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": image, "source": ["15", 0], "x": 0, "y": 0, "resize_source": False, "mask": mask}}
            ref_pixels = ["16", 0]
        g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ref_pixels, "vae": ["3", 0]}}
        g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
        g["9"] = {"class_type": "InpaintModelConditioning", "inputs": {"positive": ["8", 0], "negative": ["6", 0], "vae": ["3", 0], "pixels": image, "mask": mask, "noise_mask": True}}
        g["10"] = {"class_type": "DifferentialDiffusion", "inputs": {"model": model_link}}
        g["11"] = {"class_type": "KSampler", "inputs": {"model": ["10", 0], "seed": int(seed), "steps": int(preset.steps), "cfg": float(preset.cfg),
                                                        "sampler_name": "euler", "scheduler": "simple", "positive": ["9", 0], "negative": ["9", 1],
                                                        "latent_image": ["9", 2], "denoise": 1.0}}
        g["12"] = {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}}
        g["13"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": image, "source": ["12", 0], "x": 0, "y": 0, "resize_source": False, "mask": mask}}
        out = "13"
        summary |= {"sampler": "icm", "steps": int(preset.steps), "cfg": float(preset.cfg), "hole": recipe.mode == "remove"}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": [out, 0], "filename_prefix": out_prefix}}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


def build_i2i(recipe: I2I, roster: Roster, seed: int, out_prefix: str, image_name: str, w: int, h: int) -> Compiled:
    preset = PRESETS.get(recipe.model_id)
    if preset is None:
        raise CompileError(f"no preset for refine model '{recipe.model_id}'")
    if preset.distilled:
        raise CompileError("refine needs Klein base or FLUX.2 dev: distilled Klein cannot partial-denoise (04 §4)")
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, recipe.model_id, preset)
    dev = recipe.model_id == "flux2-dev-fp8mixed"
    steps = int(recipe.steps or (8 if dev else preset.steps))
    strength = max(0.05, min(1.0, float(recipe.strength)))
    prompt = recipe.prompt_text.strip()
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": float(preset.guidance)}}
    if dev:
        g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    else:
        g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, text, watermark", "clip": ["2", 0]}}
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["8"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": steps, "cfg": float(preset.cfg), "sampler_name": "euler", "scheduler": "simple",
                                                 "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0], "denoise": strength}}
    g["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": recipe.model_id, "source": recipe.source, "strength": strength, "steps": steps, "cfg": float(preset.cfg), "guidance": float(preset.guidance), "width": w, "height": h, "seed": int(seed)}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


def upscale_factor(model_id: str) -> int:
    m = re.search(r"x(\d)", model_id)
    return int(m.group(1)) if m else 2


def build_upscale(recipe: Upscale, roster: Roster, out_prefix: str, image_name: str, w: int = 0, h: int = 0, seed: int = 0) -> Compiled:
    """Model upscale, optionally followed by the tiled refine (10 §4): every tile of the upscaled image is re-sampled at
    `strength` with the refine model and pasted back through a feathered mask, in one engine graph."""
    _, name = roster.require(recipe.model_id)
    g: dict[str, Any] = {
        "100": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "101": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": name}},
        "102": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["101", 0], "image": ["100", 0]}},
    }
    summary: dict[str, Any] = {"model_id": recipe.model_id, "source": recipe.source, "factor": upscale_factor(recipe.model_id)}
    out: list = ["102", 0]
    prompt = ""
    if recipe.refine:
        if not (w and h):
            raise CompileError("tiled refine needs the input size")
        preset = PRESETS.get(recipe.refine_model_id)
        if preset is None or preset.distilled:
            raise CompileError("tiled refine needs Klein base or FLUX.2 dev (distilled Klein cannot partial-denoise)")
        model_link = _flux2_loaders(g, roster, recipe.refine_model_id, preset)
        dev = recipe.refine_model_id == "flux2-dev-fp8mixed"
        steps = int(recipe.steps or (8 if dev else preset.steps))
        prompt = recipe.prompt_text.strip()
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
        g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": float(preset.guidance)}}
        g["7"] = ({"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}} if dev
                  else {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, text, watermark", "clip": ["2", 0]}})
        W, H = w * summary["factor"], h * summary["factor"]
        tiles = plan_tiles(W, H, recipe.tile, recipe.overlap)
        half = int(recipe.overlap) // 2
        nid = 200
        for i, (x, y, tw, th) in enumerate(tiles):
            crop, enc, ks, dec, solid, feath, comp = (str(nid + k) for k in range(7))
            nid += 7
            g[crop] = {"class_type": "ImageCrop", "inputs": {"image": ["102", 0], "width": tw, "height": th, "x": x, "y": y}}
            g[enc] = {"class_type": "VAEEncode", "inputs": {"pixels": [crop, 0], "vae": ["3", 0]}}
            g[ks] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed) + i, "steps": steps, "cfg": float(preset.cfg), "sampler_name": "euler",
                                                        "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0], "latent_image": [enc, 0], "denoise": float(recipe.strength)}}
            g[dec] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": ["3", 0]}}
            g[solid] = {"class_type": "SolidMask", "inputs": {"value": 1.0, "width": tw, "height": th}}
            g[feath] = {"class_type": "FeatherMask", "inputs": {"mask": [solid, 0], "left": half if x > 0 else 0, "top": half if y > 0 else 0,
                                                              "right": half if x + tw < W else 0, "bottom": half if y + th < H else 0}}
            g[comp] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": out, "source": [dec, 0], "x": x, "y": y, "resize_source": False, "mask": [feath, 0]}}
            out = [comp, 0]
        summary |= {"refine_model_id": recipe.refine_model_id, "strength": float(recipe.strength), "steps": steps, "tile": recipe.tile, "overlap": recipe.overlap,
                    "tiles": len(tiles), "upscaled": [W, H]}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": out, "filename_prefix": out_prefix}}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


def build_segment(recipe: Segment, roster: Roster, out_prefix: str, image_name: str, points: list[dict] | None = None, box: list[int] | None = None,
                  w: int = 0, h: int = 0) -> Compiled:
    """AI Select → a mask image (MaskToImage → SaveImage). `points` / `box` are already in engine pixels; `w`×`h` is the engine image."""
    g: dict[str, Any] = {"100": {"class_type": "LoadImage", "inputs": {"image": image_name}}}
    if recipe.mode == "subject":
        _, name = roster.require("birefnet")
        g["1"] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": name}}
        g["2"] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["100", 0]}}
        mask: list = ["2", 0]
        summary: dict[str, Any] = {"model_id": "birefnet", "mode": "subject"}
    else:
        _, ckpt = roster.require("sam3")
        g["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
        inputs: dict[str, Any] = {"model": ["1", 0], "image": ["100", 0], "threshold": float(recipe.threshold), "refine_iterations": int(recipe.refine_iterations), "individual_masks": False}
        if recipe.mode == "text":
            if not recipe.text.strip():
                raise CompileError("SAM 3 text mode needs a prompt")
            g["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.text.strip(), "clip": ["1", 1]}}
            inputs["conditioning"] = ["2", 0]
        elif recipe.mode == "points":
            pos = [{"x": int(p["x"]), "y": int(p["y"])} for p in (points or []) if int(p.get("label", 1)) == 1]
            neg = [{"x": int(p["x"]), "y": int(p["y"])} for p in (points or []) if int(p.get("label", 1)) == 0]
            if not pos:
                raise CompileError("SAM 3 points mode needs at least one positive point")
            inputs["positive_coords"] = json.dumps(pos)
            if neg:
                inputs["negative_coords"] = json.dumps(neg)
        else:
            if not box or len(box) != 4:
                raise CompileError("SAM 3 box mode needs a box")
            x0, y0, x1, y1 = (int(v) for v in box)
            # CreateBoundingBoxes parses a JSON list of {x, y, width, height} in the pixel grid given by width/height (nodes_bounding_boxes.py)
            g["3"] = {"class_type": "CreateBoundingBoxes", "inputs": {"bboxes": json.dumps([{"x": x0, "y": y0, "width": max(1, x1 - x0), "height": max(1, y1 - y0)}]), "width": int(w), "height": int(h), "editor_state": []}}   # the canvas widget's own state: empty, so the JSON boxes win
            inputs["bboxes"] = ["3", 0]
        g["4"] = {"class_type": "SAM3_Detect", "inputs": inputs}
        mask = ["4", 0]
        summary = {"model_id": "sam3", "mode": recipe.mode, "threshold": recipe.threshold, "points": len(points or []), "box": box}
    g["5"] = {"class_type": "MaskToImage", "inputs": {"mask": mask}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": out_prefix}}
    return Compiled(graph=g, output_node="99", summary=summary | {"op": recipe.op, "expand": recipe.expand, "feather": recipe.feather}, serialized_prompt=recipe.text)


def compile_recipe(recipe: T2I | I2I | Inpaint | Upscale | I2V, roster: Roster, object_info: dict, seed: int, out_prefix: str,
                   ref_files: dict[str, str] | None = None, inputs: dict[str, Any] | None = None) -> Compiled:
    """`inputs` carries the uploaded engine input names and sizes for the document recipes (queue._prepare_document_inputs)."""
    if isinstance(recipe, T2I):
        c = build_t2i(recipe, roster, seed, out_prefix, ref_files)
    elif isinstance(recipe, Inpaint):
        i = inputs or {}
        c = build_inpaint(recipe, roster, seed, out_prefix, i["image"], i["mask"], int(i["w"]), int(i["h"]))
    elif isinstance(recipe, I2I):
        i = inputs or {}
        c = build_i2i(recipe, roster, seed, out_prefix, i["image"], int(i["w"]), int(i["h"]))
    elif isinstance(recipe, Upscale):
        i = inputs or {}
        c = build_upscale(recipe, roster, out_prefix, i["image"], int(i.get("w", 0)), int(i.get("h", 0)), seed)
    elif isinstance(recipe, Segment):
        i = inputs or {}
        c = build_segment(recipe, roster, out_prefix, i["image"], i.get("points"), i.get("box"), int(i.get("w", 0)), int(i.get("h", 0)))
    else:
        raise NotImplementedError(f"recipe kind '{recipe.kind}' is compiled in a later milestone (M6 video)")
    c.notes = resolve_names(object_info, c.graph)
    c.problems = check_graph(object_info, c.graph)
    c.graph_hash = hashlib.sha256(json.dumps(c.graph, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return c


def estimate_vram_gb(recipe: T2I | I2I | Inpaint | Upscale | Segment | I2V) -> float:
    if isinstance(recipe, Upscale) and recipe.refine:
        return VRAM_ESTIMATE_GB.get(recipe.refine_model_id, 12.0)
    return VRAM_ESTIMATE_GB.get(recipe.model_id, 12.0)


def estimate_seconds(recipe: T2I, history: list[dict] | None = None) -> dict[str, Any]:
    """ETA per image (09 §3c): rolling average of this project's matching jobs, else the spike baseline scaled by
    pixels (≈ linear) and steps. `history` rows: {model_id, px, steps, wall_s}."""
    ep = effective_params(recipe)
    px = ep["width"] * ep["height"]
    matches = [h for h in (history or []) if h.get("model_id") == recipe.model_id and h.get("wall_s") and abs(h.get("px", 0) - px) / px < 0.25 and h.get("steps") == ep["steps"]]
    if len(matches) >= 2:
        recent = matches[-5:]
        return {"seconds": round(sum(h["wall_s"] for h in recent) / len(recent), 1), "source": f"measured ({len(recent)} jobs)"}
    base = BASE_SECONDS.get((recipe.model_id, ep["turbo"]), 60.0)
    base_steps = 8 if ep["turbo"] else (PRESETS[recipe.model_id].steps if recipe.model_id in PRESETS else 20)
    seconds = base * (px / (960 * 544)) * (ep["steps"] / max(1, base_steps)) + 4 * len(recipe.refs)
    return {"seconds": round(seconds, 1), "source": "baseline (spikes)"}
