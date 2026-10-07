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

from ..recipes import FLUX2_SCHEDULE, SAMPLERS, SCHEDULERS, TE_DEVICES, WEIGHT_DTYPES, T2I, I2I, Inpaint, I2V, LoraRef, Segment, Upscale, inpaint_model_id
from ..edit_ai import plan_tiles
from ..roster import ROSTER_BY_ID, Roster
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

# Text encoders a preset may swap in (2026-10-07 encoder experiment): llama.cpp quantizations of Qwen3-8B for the Klein 9B family.
# Keyed by the preset's te_id; /capabilities publishes the map and a recipe names its choice in `te_id`.
TE_ALTERNATES: dict[str, list[str]] = {"qwen3-8b-fp8mixed": ["qwen3-8b-q4km", "qwen3-8b-q4ks", "qwen3-8b-q3km"]}


def resolve_te_id(preset: ModelPreset, te_id: str | None) -> str:
    """The preset's encoder, or a listed alternate — anything else (the 4B encoder on a 9B model, say) fails here as a
    CompileError, not minutes later as a shape error inside the engine."""
    if te_id is None or te_id == preset.te_id:
        return preset.te_id
    if te_id not in TE_ALTERNATES.get(preset.te_id, []):
        raise CompileError(f"text encoder {te_id!r} does not pair with this model (it takes {preset.te_id} or {TE_ALTERNATES.get(preset.te_id, [])})")
    return te_id


def recipe_te_id(recipe: T2I | I2I | Inpaint | Upscale, variant: str = "full") -> str | None:
    """The encoder a FLUX.2-family recipe will load (None for recipes without one); raises CompileError on a bad override."""
    if isinstance(recipe, Inpaint):
        mid = inpaint_model_id(recipe, variant)
    elif isinstance(recipe, Upscale):
        if not recipe.refine:
            return None
        mid = recipe.refine_model_id
    elif isinstance(recipe, (T2I, I2I)):
        mid = recipe.model_id
    else:
        return None
    preset = PRESETS.get(mid)
    return None if preset is None else resolve_te_id(preset, recipe.te_id)


def _te_loader(te_name: str, te_device: str | None) -> dict[str, Any]:
    """Core CLIPLoader for safetensors; ComfyUI-GGUF's CLIPLoaderGGUF for a .gguf (no device input — it loads on the default device)."""
    if te_device is not None and te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    if te_name.lower().endswith(".gguf"):
        if te_device not in (None, "default"):
            raise CompileError("a GGUF text encoder loads on the default device (CLIPLoaderGGUF has no device input)")
        return {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": te_name, "type": "flux2"}}
    return {"class_type": "CLIPLoader", "inputs": {"clip_name": te_name, "type": "flux2", "device": te_device or "default"}}


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

# ---- image-to-video (M6; 11 §3b; D8 Wan 2.2, D9 LTX-2.3; recipes from the E4/E4b/E4c/E5b spikes) -------------
WAN_NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
                "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")
LTX_NEGATIVE = "blurry, distorted, low quality, static, watermark"
# every roster id a video model needs on disk; the queue validates the set at submission and /capabilities reports it
I2V_WEIGHTS: dict[str, list[str]] = {
    "wan22-i2v-high-fp8": ["wan22-i2v-high-fp8", "wan22-i2v-low-fp8", "umt5-xxl-fp8", "wan21-vae", "wan22-lightning-high", "wan22-lightning-low"],
    "ltx23-distilled-fp8": ["ltx23-distilled-fp8", "gemma3-12b-fp8", "ltx23-text-projection", "ltx23-video-vae", "ltx23-audio-vae"],
}
I2V_RULES: dict[str, dict[str, Any]] = {   # 04 §9a: spatial multiple, frame rule, native fps, Draft tier
    "wan22": {"size_mult": 16, "frame_step": 4, "fps": 16, "frames": 81, "size": (832, 480), "label": "Wan 2.2 I2V-A14B · faithful"},
    "ltx23": {"size_mult": 32, "frame_step": 8, "fps": 24, "frames": 121, "size": (1024, 576), "label": "LTX-2.3 distilled · fast, beats"},
}


@dataclass
class WanPreset:
    steps: int
    split: int                       # high expert runs steps [0, split), low expert [split, steps)
    cfg_high: float
    cfg_low: float
    shift: float
    lora_high: bool                  # Lightning 4-step LoRA on the expert (E4b: dropping it on the high expert buys motion)
    lora_low: bool
    label: str


WAN_PRESETS: dict[str, WanPreset] = {
    "draft": WanPreset(4, 2, 1.0, 1.0, 5.0, True, True, "Draft · Lightning 2 + 2 (≈ 4 min at 480p)"),
    "motion": WanPreset(8, 4, 3.5, 1.0, 5.0, False, True, "Motion · undistilled high expert at CFG 3.5 (≈ 8 min)"),
    "quality": WanPreset(20, 10, 3.5, 3.5, 8.0, False, False, "Quality · 10 + 10 steps, no LoRA (slow)"),
}
LTX_STEPS: dict[str, int] = {"draft": 8, "motion": 12, "quality": 20}
I2V_BASE_SECONDS: dict[tuple[str, str], float] = {   # E4c / E4b / E5b at the Draft tier
    ("wan22", "draft"): 236.0, ("wan22", "motion"): 495.0, ("wan22", "quality"): 900.0,
    ("ltx23", "draft"): 141.0, ("ltx23", "motion"): 165.0, ("ltx23", "quality"): 210.0,
}


def i2v_family(model_id: str) -> str:
    e = ROSTER_BY_ID.get(model_id)
    if e is None or e.family not in I2V_RULES:
        raise CompileError(f"{model_id!r} is not an image-to-video model (Wan 2.2 or LTX-2.3)")
    return e.family


def _snap(v: int, mult: int, lo: int) -> int:
    return max(lo, int(round(v / mult)) * mult)


def i2v_params(recipe: I2V) -> dict[str, Any]:
    """What will actually run: sizes snapped to the model's multiple, frames to 4n+1 / 8n+1, preset values with overrides."""
    fam = i2v_family(recipe.model_id)
    rule = I2V_RULES[fam]
    mult = rule["size_mult"]
    w, h = _snap(recipe.width, mult, mult * 8), _snap(recipe.height, mult, mult * 8)
    step = rule["frame_step"]
    frames = max(1, int(round((recipe.frames - 1) / step))) * step + 1
    out: dict[str, Any] = {"family": fam, "width": w, "height": h, "frames": frames, "fps": recipe.fps, "preset": recipe.preset,
                           "flf": bool(recipe.end_asset), "beats": len(recipe.beats)}
    if fam == "wan22":
        p = WAN_PRESETS[recipe.preset]
        steps = recipe.steps or p.steps
        out |= {"steps": steps, "split": max(1, min(steps - 1, round(steps * p.split / p.steps))), "cfg_high": recipe.cfg if recipe.cfg is not None else p.cfg_high,
                "cfg_low": p.cfg_low, "shift": recipe.shift if recipe.shift is not None else p.shift, "lora_high": p.lora_high, "lora_low": p.lora_low, "label": p.label}
    else:
        steps = recipe.steps or LTX_STEPS[recipe.preset]
        out |= {"steps": steps, "shift": recipe.shift, "label": f"LTX-2.3 distilled · {steps} steps"}
    return out


def build_i2v(recipe: I2V, roster: Roster, seed: int, out_prefix: str, start_name: str, end_name: str | None = None,
              beat_names: dict[str, str] | None = None) -> Compiled:
    """Wan: loaders → ModelSamplingSD3 ×2 → WanImageToVideo / WanFirstLastFrameToVideo → KSamplerAdvanced high → low → VAEDecode
    → SaveImage (one PNG per frame: the clip master; the proxy is encoded by the orchestrator). LTX: the E5 graph — joint
    audio-video latent, LTXVAddGuide for the end frame (frame_idx −1) and every beat — ending in SaveImage the same way."""
    ep = i2v_params(recipe)
    w, h, frames, fps = ep["width"], ep["height"], ep["frames"], ep["fps"]
    g: dict[str, Any] = {}

    def load_scaled(nid: str, name: str) -> list:
        g[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[nid + "s"] = {"class_type": "ImageScale", "inputs": {"image": [nid, 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        return [nid + "s", 0]

    if ep["family"] == "wan22":
        _, high = roster.require("wan22-i2v-high-fp8")
        _, low = roster.require("wan22-i2v-low-fp8")
        _, te = roster.require("umt5-xxl-fp8")
        _, vae = roster.require("wan21-vae")
        g["1h"] = {"class_type": "UNETLoader", "inputs": {"unet_name": high, "weight_dtype": "default"}}
        g["1l"] = {"class_type": "UNETLoader", "inputs": {"unet_name": low, "weight_dtype": "default"}}
        g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
        mh: list = ["1h", 0]
        ml: list = ["1l", 0]
        if ep["lora_high"]:
            _, lh = roster.require("wan22-lightning-high")
            g["4h"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": mh, "lora_name": lh, "strength_model": 0.7}}
            mh = ["4h", 0]
        if ep["lora_low"]:
            _, ll = roster.require("wan22-lightning-low")
            g["4l"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ml, "lora_name": ll, "strength_model": 1.0}}
            ml = ["4l", 0]
        g["8h"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": mh, "shift": ep["shift"]}}
        g["8l"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": ml, "shift": ep["shift"]}}
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.prompt_text, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative if recipe.negative is not None else WAN_NEGATIVE, "clip": ["2", 0]}}
        cond: dict[str, Any] = {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": w, "height": h, "length": frames, "batch_size": 1,
                                "start_image": load_scaled("100", start_name)}
        if end_name:
            cond["end_image"] = load_scaled("101", end_name)
            g["7"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": cond}
        else:
            g["7"] = {"class_type": "WanImageToVideo", "inputs": cond}
        g["9"] = {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8h", 0], "add_noise": "enable", "noise_seed": seed, "steps": ep["steps"], "cfg": ep["cfg_high"],
                                                              "sampler_name": "euler", "scheduler": "simple", "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["7", 2],
                                                              "start_at_step": 0, "end_at_step": ep["split"], "return_with_leftover_noise": "enable"}}
        g["10"] = {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8l", 0], "add_noise": "disable", "noise_seed": seed, "steps": ep["steps"], "cfg": ep["cfg_low"],
                                                               "sampler_name": "euler", "scheduler": "simple", "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["9", 0],
                                                               "start_at_step": ep["split"], "end_at_step": 10000, "return_with_leftover_noise": "disable"}}
        g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
        out_node = "12"
        g[out_node] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": out_prefix}}
    else:
        _, unet = roster.require("ltx23-distilled-fp8")
        _, te1 = roster.require("gemma3-12b-fp8")
        _, te2 = roster.require("ltx23-text-projection")
        _, vvae = roster.require("ltx23-video-vae")
        _, avae = roster.require("ltx23-audio-vae")
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
        g["2"] = {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": te1, "clip_name2": te2, "type": "ltxv"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vvae}}
        g["99"] = {"class_type": "VAELoader", "inputs": {"vae_name": avae}}      # core 0.38: the joint AV latent needs an audio VAE even for silent clips (E5)
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.prompt_text, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative if recipe.negative is not None else LTX_NEGATIVE, "clip": ["2", 0]}}
        g["7"] = {"class_type": "LTXVConditioning", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "frame_rate": float(fps)}}

        def guide_image(nid: str, name: str) -> list:
            scaled = load_scaled(nid, name)
            g[nid + "p"] = {"class_type": "LTXVPreprocess", "inputs": {"image": scaled, "img_compression": 35}}
            return [nid + "p", 0]

        g["8"] = {"class_type": "LTXVImgToVideo", "inputs": {"positive": ["7", 0], "negative": ["7", 1], "vae": ["3", 0], "image": guide_image("100", start_name),
                                                            "width": w, "height": h, "length": frames, "batch_size": 1, "strength": 1.0}}
        pos, neg, lat = ["8", 0], ["8", 1], ["8", 2]
        guides: list[tuple[str, int, float, str]] = []
        if end_name:
            guides.append((end_name, -1, 1.0, "101"))
        for i, b in enumerate(recipe.beats):
            name = (beat_names or {}).get(b.asset_id)
            if not name:
                raise CompileError(f"beat at frame {b.frame}: asset {b.asset_id} was not uploaded")
            guides.append((name, min(b.frame, frames - 1), b.strength, f"13{i}"))
        for k, (name, idx, strength, nid) in enumerate(guides):
            gid = f"guide{k}"
            g[gid] = {"class_type": "LTXVAddGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["3", 0], "latent": lat, "image": guide_image(nid, name),
                                                             "frame_idx": idx, "strength": strength}}
            pos, neg, lat = [gid, 0], [gid, 1], [gid, 2]
        g["12"] = {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": frames, "frame_rate": fps, "batch_size": 1, "audio_vae": ["99", 0]}}
        g["13"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": lat, "audio_latent": ["12", 0]}}
        g["14"] = {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": pos}}
        g["15"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
        g["16"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        g["17"] = {"class_type": "LTXVScheduler", "inputs": {"steps": ep["steps"], "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": ["13", 0]}}
        g["18"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["15", 0], "guider": ["14", 0], "sampler": ["16", 0], "sigmas": ["17", 0], "latent_image": ["13", 0]}}
        g["19"] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["18", 0]}}
        g["20"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": pos, "negative": neg, "latent": ["19", 0]}}
        g["21"] = {"class_type": "VAEDecode", "inputs": {"samples": ["20", 2], "vae": ["3", 0]}}
        out_node = "22"
        g[out_node] = {"class_type": "SaveImage", "inputs": {"images": ["21", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": recipe.model_id, **{k: v for k, v in ep.items() if k != "label"}, "label": ep["label"]}
    return Compiled(graph=g, output_node=out_node, summary=summary, serialized_prompt=recipe.prompt_text)


def estimate_i2v_seconds(recipe: I2V) -> dict[str, Any]:
    """ETA from the E4/E5 spike baselines at the Draft tier, scaled by pixel-frames and (half) by the step ratio — the VAE
    passes are a fixed share of a Wan clip (Q18)."""
    ep = i2v_params(recipe)
    rule = I2V_RULES[ep["family"]]
    base = I2V_BASE_SECONDS[(ep["family"], recipe.preset)]
    work = (ep["width"] * ep["height"] * ep["frames"]) / (rule["size"][0] * rule["size"][1] * rule["frames"])
    steps_ref = WAN_PRESETS[recipe.preset].steps if ep["family"] == "wan22" else LTX_STEPS[recipe.preset]
    return {"seconds": round(base * work * (0.5 + 0.5 * ep["steps"] / steps_ref), 1), "source": "baseline (E4/E5 spikes)"}


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
    return {"model_id": recipe.model_id, "te_id": resolve_te_id(preset, recipe.te_id), "width": w, "height": h, "steps": steps, "guidance": guidance, "cfg": cfg,
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
    _, te = roster.require(ep["te_id"])
    _, vae = roster.require(preset.vae_id)
    text = ep["serialized_prompt"]
    if not text.strip():
        raise CompileError("empty prompt")
    w, h = ep["width"], ep["height"]

    g: dict[str, Any] = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": ep["weight_dtype"]}},
        "2": _te_loader(te, ep["te_device"]),
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
def _flux2_loaders(g: dict[str, Any], roster: Roster, model_id: str, preset: ModelPreset, te_device: str | None = None,
                   te_id: str | None = None) -> list:
    """UNET / text encoder / VAE loaders for a FLUX.2-family model; returns the model link (Turbo LoRA for dev). `te_id` swaps
    in a listed alternate encoder (TE_ALTERNATES); a .gguf goes through CLIPLoaderGGUF."""
    if te_device is not None and te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    _, unet = roster.require(model_id)
    _, te = roster.require(resolve_te_id(preset, te_id))
    _, vae = roster.require(preset.vae_id)
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": preset.weight_dtype}}
    g["2"] = _te_loader(te, te_device)
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
    if preset.turbo_lora:
        _, lora = roster.require(preset.turbo_lora)
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}}
        return ["4", 0]
    return ["1", 0]


def build_inpaint(recipe: Inpaint, roster: Roster, seed: int, out_prefix: str, image_name: str, mask_name: str, w: int, h: int,
                  variant: str = "full") -> Compiled:
    model_id = inpaint_model_id(recipe, variant)
    preset = PRESETS.get(model_id)
    if preset is None:
        raise CompileError(f"no preset for inpaint model '{model_id}'")
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, model_id, preset, recipe.te_device, recipe.te_id)
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
    model_link = _flux2_loaders(g, roster, recipe.model_id, preset, recipe.te_device, recipe.te_id)
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
        model_link = _flux2_loaders(g, roster, recipe.refine_model_id, preset, recipe.te_device, recipe.te_id)
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
            g["3"] = {"class_type": "CreateBoundingBoxes", "inputs": {"bboxes": json.dumps([{"x": x0, "y": y0, "width": max(1, x1 - x0), "height": max(1, y1 - y0)}]), "width": int(w), "height": int(h), "editor_state": {}}}
            # C32: `editor_state` is the canvas widget's own state and must be *empty* so the JSON `bboxes` win — but not an empty
            # list: ComfyUI's API validator reads every list value as a link ("Bad linked input, must be a length-2 list"); `{}` is
            # falsy for the node (`editor_state or []`) and passes validation (seen on the rig 2026-10-07)
            inputs["bboxes"] = ["3", 1]            # C32: output 0 is the preview IMAGE; 1 is the BOUNDING_BOX (C9's type check caught it)
        g["4"] = {"class_type": "SAM3_Detect", "inputs": inputs}
        mask = ["4", 0]
        summary = {"model_id": "sam3", "mode": recipe.mode, "threshold": recipe.threshold, "points": len(points or []), "box": box}
    g["5"] = {"class_type": "MaskToImage", "inputs": {"mask": mask}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": out_prefix}}
    return Compiled(graph=g, output_node="99", summary=summary | {"op": recipe.op, "expand": recipe.expand, "feather": recipe.feather}, serialized_prompt=recipe.text)


def compile_recipe(recipe: T2I | I2I | Inpaint | Upscale | I2V, roster: Roster, object_info: dict, seed: int, out_prefix: str,
                   ref_files: dict[str, str] | None = None, inputs: dict[str, Any] | None = None, variant: str = "full") -> Compiled:
    """`inputs` carries the uploaded engine input names and sizes for the document recipes (queue._prepare_document_inputs)."""
    if isinstance(recipe, T2I):
        c = build_t2i(recipe, roster, seed, out_prefix, ref_files)
    elif isinstance(recipe, Inpaint):
        i = inputs or {}
        c = build_inpaint(recipe, roster, seed, out_prefix, i["image"], i["mask"], int(i["w"]), int(i["h"]), variant)
    elif isinstance(recipe, I2I):
        i = inputs or {}
        c = build_i2i(recipe, roster, seed, out_prefix, i["image"], int(i["w"]), int(i["h"]))
    elif isinstance(recipe, Upscale):
        i = inputs or {}
        c = build_upscale(recipe, roster, out_prefix, i["image"], int(i.get("w", 0)), int(i.get("h", 0)), seed)
    elif isinstance(recipe, Segment):
        i = inputs or {}
        c = build_segment(recipe, roster, out_prefix, i["image"], i.get("points"), i.get("box"), int(i.get("w", 0)), int(i.get("h", 0)))
    elif isinstance(recipe, I2V):
        i = inputs or {}
        if "start" not in i:
            raise CompileError("i2v needs the uploaded start frame (queue._prepare_i2v_inputs)")
        c = build_i2v(recipe, roster, seed, out_prefix, i["start"], i.get("end"), i.get("beats"))
    else:
        raise NotImplementedError(f"recipe kind '{recipe.kind}' has no compiler")
    c.notes = resolve_names(object_info, c.graph)
    c.problems = check_graph(object_info, c.graph)
    c.graph_hash = hashlib.sha256(json.dumps(c.graph, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return c


def estimate_vram_gb(recipe: T2I | I2I | Inpaint | Upscale | Segment | I2V, variant: str = "full") -> float:
    if isinstance(recipe, Upscale) and recipe.refine:
        return VRAM_ESTIMATE_GB.get(recipe.refine_model_id, 12.0)
    if isinstance(recipe, Inpaint):
        return VRAM_ESTIMATE_GB.get(inpaint_model_id(recipe, variant), 12.0)      # C10: Fill Hero runs dev, whatever the panel named
    return VRAM_ESTIMATE_GB.get(recipe.model_id, 12.0)


def recipe_weights(recipe: T2I | I2I | Inpaint | Upscale | Segment | I2V, variant: str = "full") -> list[str]:
    """Every roster id a recipe would load — the open-variant gate (C3, D26) and the admission estimate read this."""
    if isinstance(recipe, I2V):
        return list(I2V_WEIGHTS.get(recipe.model_id, [recipe.model_id]))

    te_over = getattr(recipe, "te_id", None)

    def preset_ids(mid: str, turbo: bool) -> list[str]:
        p = PRESETS.get(mid)
        if p is None:
            return [mid]
        te = te_over if te_over in TE_ALTERNATES.get(p.te_id, []) else p.te_id
        return [mid, te, p.vae_id, *([p.turbo_lora] if turbo and p.turbo_lora else [])]

    ids: list[str] = []
    if isinstance(recipe, T2I):
        ids += preset_ids(recipe.model_id, bool(recipe.turbo))
    elif isinstance(recipe, Inpaint):
        mid = inpaint_model_id(recipe, variant)
        ids += preset_ids(mid, mid == "flux2-dev-fp8mixed")                 # _flux2_loaders chains the Turbo LoRA on dev
    elif isinstance(recipe, I2I):
        ids += preset_ids(recipe.model_id, recipe.model_id == "flux2-dev-fp8mixed")
    elif isinstance(recipe, Upscale):
        ids.append(recipe.model_id)
        if recipe.refine:
            ids += preset_ids(recipe.refine_model_id, recipe.refine_model_id == "flux2-dev-fp8mixed")
    else:
        ids.append(recipe.model_id)
    ids += [l.model_id for l in getattr(recipe, "loras", [])]
    return list(dict.fromkeys(ids))


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
