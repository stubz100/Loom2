"""Recipe → ComfyUI API graph (06 §3b, the recipe compiler). One builder per recipe kind; every builder resolves
roster ids through the `Roster`, never types a file name, and the result is contract-checked against
`/object_info` before submission. M3: T2I on FLUX.2 dev (JSON through the Mistral template) and Klein (prose),
with Turbo / LoRA chains, reference images and an exact serialisation preview (09 §3a).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from ..recipes import SAMPLERS, SCHEDULERS, T2I, I2I, Inpaint, I2V, LoraRef
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
    "wan22-i2v-high-fp8": 14.5, "ltx23-distilled-fp8": 14.0,
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
    """What will actually run (the UI shows exactly this: 07 §1.4 'display == reality')."""
    preset = PRESETS.get(recipe.model_id)
    if preset is None:
        raise CompileError(f"no T2I preset for model '{recipe.model_id}'")
    turbo = bool(recipe.turbo and preset.turbo_lora)
    steps = recipe.steps if recipe.steps else (preset.turbo_steps if turbo else preset.steps)
    if preset.distilled:
        steps = preset.steps                                  # fixed for distilled variants (09 §3b)
    guidance = recipe.guidance if recipe.guidance is not None else preset.guidance
    cfg = preset.cfg if preset.distilled else (recipe.cfg if recipe.cfg is not None else preset.cfg)
    sampler = recipe.sampler if recipe.sampler in SAMPLERS else preset.sampler
    scheduler = recipe.scheduler if recipe.scheduler in SCHEDULERS else preset.scheduler
    w, h = _mult16(recipe.width), _mult16(recipe.height)
    if w * h > 4_200_000 or w < 64 or h < 64:
        raise CompileError(f"size {w}×{h} outside the 64 px – 4 MP range")
    text, mode = serialize_prompt(recipe, preset)
    return {"model_id": recipe.model_id, "te_id": preset.te_id, "width": w, "height": h, "steps": steps, "guidance": guidance, "cfg": cfg,
            "sampler": sampler, "scheduler": scheduler, "turbo": turbo, "distilled": preset.distilled, "negative_used": bool(recipe.negative) and not preset.distilled,
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
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": preset.weight_dtype}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["2", 0]}},
        "8": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}},
    }
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
    if ep["turbo"]:
        _, lora = roster.require(preset.turbo_lora)  # type: ignore[arg-type]
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_link, "lora_name": lora, "strength_model": 1.0}}
        model_link = ["4", 0]
    model_link, nid = _lora_chain(g, model_link, recipe.loras, roster, 20)
    g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": int(ep["steps"]), "cfg": float(ep["cfg"]),
                                                 "sampler_name": ep["sampler"], "scheduler": ep["scheduler"], "positive": ["6", 0], "negative": ["7", 0],
                                                 "latent_image": ["8", 0], "denoise": 1.0}}
    summary = {k: v for k, v in ep.items() if k != "serialized_prompt"}
    return Compiled(graph=g, output_node="11", summary=summary, serialized_prompt=text)


def compile_recipe(recipe: T2I | I2I | Inpaint | I2V, roster: Roster, object_info: dict, seed: int, out_prefix: str,
                   ref_files: dict[str, str] | None = None) -> Compiled:
    if isinstance(recipe, T2I):
        c = build_t2i(recipe, roster, seed, out_prefix, ref_files)
    else:
        raise NotImplementedError(f"recipe kind '{recipe.kind}' is compiled in a later milestone (M5 edit, M6 video)")
    c.notes = resolve_names(object_info, c.graph)
    c.problems = check_graph(object_info, c.graph)
    c.graph_hash = hashlib.sha256(json.dumps(c.graph, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return c


def estimate_vram_gb(recipe: T2I | I2I | Inpaint | I2V) -> float:
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
