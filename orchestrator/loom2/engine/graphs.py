"""Recipe → ComfyUI API graph (06 §3b, the recipe compiler). One builder per recipe kind; every builder resolves
roster ids through the `Roster`, never types a file name, and the result is contract-checked against
`/object_info` before submission. M1: T2I on FLUX.2 dev (JSON prompt through the Mistral template) and Klein.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from ..recipes import T2I, I2I, Inpaint, I2V, LoraRef
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


PRESETS: dict[str, ModelPreset] = {
    "flux2-dev-fp8mixed": ModelPreset(te_id="mistral3-small-flux2-fp8", steps=20, guidance=4.0, turbo_lora="flux2-turbo-lora"),
    "klein-4b": ModelPreset(te_id="qwen3-4b", steps=4, guidance=1.0, weight_dtype="fp8_e4m3fn", distilled=True, json_prompt=False),
    "klein-base-4b": ModelPreset(te_id="qwen3-4b", steps=20, guidance=1.0, cfg=3.5, weight_dtype="fp8_e4m3fn", json_prompt=False),
    "klein-9b": ModelPreset(te_id="qwen3-8b-fp8mixed", steps=4, guidance=1.0, weight_dtype="fp8_e4m3fn", distilled=True, json_prompt=False),
    "klein-base-9b": ModelPreset(te_id="qwen3-8b-fp8mixed", steps=20, guidance=1.0, cfg=3.5, weight_dtype="fp8_e4m3fn", json_prompt=False),
    "klein-9b-kv": ModelPreset(te_id="qwen3-8b-fp8mixed", steps=4, guidance=1.0, weight_dtype="fp8_e4m3fn", distilled=True, json_prompt=False),
}

# VRAM estimates (GB) for the queue's admission check (06 §3d `Engine.estimate`); measured peaks from the spikes
VRAM_ESTIMATE_GB: dict[str, float] = {
    "flux2-dev-fp8mixed": 14.0, "klein-4b": 8.5, "klein-base-4b": 9.2, "klein-9b": 15.0, "klein-base-9b": 15.0, "klein-9b-kv": 15.0,
    "wan22-i2v-high-fp8": 14.5, "wan22-i2v-high-q5": 13.5, "ltx23-distilled-fp8": 14.0,
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


def flatten_json_prompt(p: dict | list | str | int | float | None, depth: int = 0) -> str:
    """BFL-style JSON prompt → prose for Klein (keys become light structure, values are kept verbatim)."""
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


def build_t2i(recipe: T2I, roster: Roster, seed: int, out_prefix: str) -> Compiled:
    preset = PRESETS.get(recipe.model_id)
    if preset is None:
        raise CompileError(f"no T2I preset for model '{recipe.model_id}'")
    _, unet = roster.require(recipe.model_id)
    _, te = roster.require(preset.te_id)
    _, vae = roster.require(preset.vae_id)
    w, h = _mult16(recipe.width), _mult16(recipe.height)
    if recipe.prompt_json and preset.json_prompt:
        text = json.dumps(recipe.prompt_json, ensure_ascii=False)
    elif recipe.prompt_json:
        text = flatten_json_prompt(recipe.prompt_json)
        if recipe.prompt_text:
            text = f"{recipe.prompt_text}. {text}"
    else:
        text = recipe.prompt_text
    if not text.strip():
        raise CompileError("empty prompt")
    turbo = bool(recipe.turbo and preset.turbo_lora)
    steps = recipe.steps if recipe.steps else (preset.turbo_steps if turbo else preset.steps)
    guidance = recipe.guidance if recipe.guidance is not None else preset.guidance
    cfg = preset.cfg if preset.cfg != 1.0 else recipe.cfg

    g: dict[str, Any] = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": preset.weight_dtype}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["2", 0]}},
        "6": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": float(guidance)}},
        "8": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}},
    }
    if preset.distilled or not recipe.negative:
        g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    else:
        g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative, "clip": ["2", 0]}}
    model_link: list = ["1", 0]
    nid = 20
    if turbo:
        _, lora = roster.require(preset.turbo_lora)  # type: ignore[arg-type]
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_link, "lora_name": lora, "strength_model": 1.0}}
        model_link = ["4", 0]
    model_link, nid = _lora_chain(g, model_link, recipe.loras, roster, nid)
    g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": int(steps), "cfg": float(cfg),
                                                 "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0],
                                                 "latent_image": ["8", 0], "denoise": 1.0}}
    summary = {"model_id": recipe.model_id, "te_id": preset.te_id, "width": w, "height": h, "steps": steps, "guidance": guidance, "cfg": cfg,
               "turbo": turbo, "loras": [l.model_dump() for l in recipe.loras], "prompt_mode": "json" if (recipe.prompt_json and preset.json_prompt) else "text"}
    return Compiled(graph=g, output_node="11", summary=summary)


def compile_recipe(recipe: T2I | I2I | Inpaint | I2V, roster: Roster, object_info: dict, seed: int, out_prefix: str) -> Compiled:
    if isinstance(recipe, T2I):
        c = build_t2i(recipe, roster, seed, out_prefix)
    else:
        raise NotImplementedError(f"recipe kind '{recipe.kind}' is compiled in a later milestone (M5 edit, M6 video)")
    c.notes = resolve_names(object_info, c.graph)
    c.problems = check_graph(object_info, c.graph)
    c.graph_hash = hashlib.sha256(json.dumps(c.graph, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return c


def estimate_vram_gb(recipe: T2I | I2I | Inpaint | I2V) -> float:
    return VRAM_ESTIMATE_GB.get(recipe.model_id, 12.0)
