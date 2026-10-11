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

from ..recipes import FLUX2_SCHEDULE, SAMPLERS, SCHEDULERS, TE_DEVICES, WEIGHT_DTYPES, T2I, I2I, Inpaint, I2V, LoraRef, Segment, Upscale, inpaint_model_id
from ..edit_ai import plan_tiles
from ..models import registry
from ..models.spec import ModelSpec
from ..roster import Roster
from .contract import check_graph, resolve_names


def image_spec(model_id: str, what: str = "T2I preset") -> ModelSpec:
    """D65: the spec of a FLUX.2-family model (dev, Klein) — a CompileError for anything else."""
    spec = registry.get(model_id)
    if spec is None or spec.graph not in registry.IMAGE_GRAPHS:
        raise CompileError(f"no {what} for model '{model_id}'")
    return spec


def te_options(spec: ModelSpec) -> list[str]:
    """The spec's encoder first, then its alternates (D31) — the order the panels list them in."""
    return [spec.roles.te.default, *spec.roles.te.alternates] if spec.roles.te else []


def te_alternates() -> dict[str, list[str]]:
    """{default encoder: alternates} across the image models (/capabilities.te_alternates)."""
    out: dict[str, list[str]] = {}
    for spec in registry.image_specs():
        if spec.roles.te and spec.roles.te.alternates:
            out.setdefault(spec.roles.te.default, list(spec.roles.te.alternates))
    return out


def te_label(te_id: str) -> str | None:
    for spec in registry.image_specs():
        if spec.roles.te and te_id in spec.roles.te.labels:
            return spec.roles.te.labels[te_id]
    return None


def resolve_te_id(spec: ModelSpec, te_id: str | None) -> str:
    """The spec's encoder, or a listed alternate — anything else (the 4B encoder on a 9B model, say) fails here as a
    CompileError, not minutes later as a shape error inside the engine."""
    assert spec.roles.te is not None
    if te_id is None or te_id == spec.roles.te.default:
        return spec.roles.te.default
    if te_id not in spec.roles.te.alternates:
        raise CompileError(f"text encoder {te_id!r} does not pair with this model (it takes {spec.roles.te.default} or {spec.roles.te.alternates})")
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
    spec = registry.get(mid)
    return None if spec is None or spec.roles.te is None or spec.graph not in registry.IMAGE_GRAPHS else resolve_te_id(spec, recipe.te_id)


def _te_loader(te_name: str, te_device: str | None) -> dict[str, Any]:
    """Core CLIPLoader for safetensors; ComfyUI-GGUF's CLIPLoaderGGUF for a .gguf (no device input — it loads on the default device)."""
    if te_device is not None and te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    if te_name.lower().endswith(".gguf"):
        if te_device not in (None, "default"):
            raise CompileError("a GGUF text encoder loads on the default device (CLIPLoaderGGUF has no device input)")
        return {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": te_name, "type": "flux2"}}
    return {"class_type": "CLIPLoader", "inputs": {"clip_name": te_name, "type": "flux2", "device": te_device or "default"}}


# ---- image-to-video (M6; 11 §3b; D8 Wan 2.2, D9 LTX-2.3; recipes from the E4/E4b/E4c/E5b spikes) -------------
def video_spec(model_id: str) -> ModelSpec:
    spec = registry.get(model_id)
    if spec is None or not spec.recipes.i2v or spec.video is None:
        raise CompileError(f"{model_id!r} is not an image-to-video model (Wan 2.2 or LTX-2.3)")
    return spec


def i2v_family(model_id: str) -> str:
    return video_spec(model_id).family




def i2v_params(recipe: I2V) -> dict[str, Any]:
    """What will actually run: sizes snapped to the model's multiple, frames to 4n+1 / 8n+1, preset values with overrides."""
    spec = video_spec(recipe.model_id)
    fam, geo, presets = spec.family, spec.geometry, spec.video.presets   # type: ignore[union-attr]
    if recipe.preset not in presets:
        raise CompileError(f"{spec.label} has no preset {recipe.preset!r} ({', '.join(presets)})")
    mult, policy = geo.size_mult, recipe.size_policy
    w, h = snap(recipe.width, mult, mult * 8, policy, "width"), snap(recipe.height, mult, mult * 8, policy, "height")
    step = geo.frame_step or 1
    try:
        frames = snap(recipe.frames - 1, step, step, policy, "frames") + 1    # 4n+1 (Wan) / 8n+1 (LTX)
    except FieldError as e:                                                    # reported in frames, not on the n grid
        raise FieldError("frames", recipe.frames, [a + 1 for a in e.allowed], f"frames {recipe.frames} is not {step}n+1 for {spec.label}") from None
    out: dict[str, Any] = {"family": fam, "width": w, "height": h, "frames": frames, "fps": recipe.fps, "preset": recipe.preset,
                           "flf": bool(recipe.end_asset), "beats": len(recipe.beats)}
    p = presets[recipe.preset]
    if spec.graph == "wan22":
        steps = recipe.steps or p.steps
        out |= {"steps": steps, "split": max(1, min(steps - 1, round(steps * p.split / p.steps))), "cfg_high": recipe.cfg if recipe.cfg is not None else p.cfg_high,
                "cfg_low": p.cfg_low, "shift": recipe.shift if recipe.shift is not None else p.shift, "lora_high": p.lora_high, "lora_low": p.lora_low, "label": p.label}
    else:
        steps = recipe.steps or p.steps
        out |= {"steps": steps, "shift": recipe.shift, "label": f"{spec.label.split(' · ')[0]} · {steps} steps"}
    return out


def build_i2v(recipe: I2V, roster: Roster, seed: int, out_prefix: str, start_name: str, end_name: str | None = None,
              beat_names: dict[str, str] | None = None) -> Compiled:
    """Wan: loaders → ModelSamplingSD3 ×2 → WanImageToVideo / WanFirstLastFrameToVideo → KSamplerAdvanced high → low → VAEDecode
    → SaveImage (one PNG per frame: the clip master; the proxy is encoded by the orchestrator). LTX: the E5 graph — joint
    audio-video latent, LTXVAddGuide for the end frame (frame_idx −1) and every beat — ending in SaveImage the same way."""
    ep = i2v_params(recipe)
    spec = video_spec(recipe.model_id)
    roles, video = spec.roles, spec.video
    assert roles.te is not None and roles.vae is not None and video is not None
    w, h, frames, fps = ep["width"], ep["height"], ep["frames"], ep["fps"]
    g: dict[str, Any] = {}

    def load_scaled(nid: str, name: str) -> list:
        g[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[nid + "s"] = {"class_type": "ImageScale", "inputs": {"image": [nid, 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        return [nid + "s", 0]

    if spec.graph == "wan22":
        _, high = roster.require(spec.id)
        _, low = roster.require(roles.extra["low_expert"])
        _, te = roster.require(roles.te.default)
        _, vae = roster.require(roles.vae)
        g["1h"] = {"class_type": "UNETLoader", "inputs": {"unet_name": high, "weight_dtype": "default"}}
        g["1l"] = {"class_type": "UNETLoader", "inputs": {"unet_name": low, "weight_dtype": "default"}}
        g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
        mh: list = ["1h", 0]
        ml: list = ["1l", 0]
        if ep["lora_high"]:
            _, lh = roster.require(roles.extra["lightning_high"])
            g["4h"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": mh, "lora_name": lh, "strength_model": 0.7}}
            mh = ["4h", 0]
        if ep["lora_low"]:
            _, ll = roster.require(roles.extra["lightning_low"])
            g["4l"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ml, "lora_name": ll, "strength_model": 1.0}}
            ml = ["4l", 0]
        g["8h"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": mh, "shift": ep["shift"]}}
        g["8l"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": ml, "shift": ep["shift"]}}
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.prompt_text, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative if recipe.negative is not None else video.negative, "clip": ["2", 0]}}
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
        _, unet = roster.require(spec.id)
        _, te1 = roster.require(roles.te.default)
        _, te2 = roster.require(roles.extra["projection"])
        _, vvae = roster.require(roles.vae)
        _, avae = roster.require(roles.extra["audio_vae"])
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
        g["2"] = {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": te1, "clip_name2": te2, "type": "ltxv"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vvae}}
        g["99"] = {"class_type": "VAELoader", "inputs": {"vae_name": avae}}      # core 0.38: the joint AV latent needs an audio VAE even for silent clips (E5)
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.prompt_text, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative if recipe.negative is not None else video.negative, "clip": ["2", 0]}}
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
    spec = video_spec(recipe.model_id)
    p = spec.video.presets[recipe.preset]                          # type: ignore[union-attr]
    size, frames = spec.geometry.size or [ep["width"], ep["height"]], spec.geometry.frames or ep["frames"]
    work = (ep["width"] * ep["height"] * ep["frames"]) / (size[0] * size[1] * frames)
    base, steps_ref = p.seconds or 240.0, p.steps
    return {"seconds": round(base * work * (0.5 + 0.5 * ep["steps"] / steps_ref), 1), "source": "baseline (E4/E5 spikes)"}


class CompileError(ValueError):
    pass


class FieldError(CompileError):
    """D65: a recipe value the model does not take — answered as 422 {field, value, allowed, message} so the panel can mark the field."""

    def __init__(self, field: str, value: Any, allowed: list, message: str) -> None:
        super().__init__(message)
        self.field, self.value, self.allowed = field, value, allowed

    def detail(self) -> dict[str, Any]:
        return {"message": str(self), "field": self.field, "value": self.value, "allowed": self.allowed}


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


def serialize_prompt(recipe: T2I, spec: ModelSpec | None = None) -> tuple[str, str]:
    """The exact string the engine receives and how it was produced: 'json' | 'prose' | 'text'."""
    spec = spec or registry.get(recipe.model_id) or registry.SPECS[registry.default_model("t2i")]
    if recipe.prompt_mode in ("tree", "json") and recipe.prompt_json:
        tree = {k: v for k, v in recipe.prompt_json.items() if v not in (None, "", [], {})}
        if spec.sampling.json_prompt:
            return json.dumps(tree, ensure_ascii=False, separators=(",", ":")), "json"
        prose = flatten_json_prompt(tree)
        return (f"{recipe.prompt_text.strip()}. {prose}" if recipe.prompt_text.strip() else prose), "prose"
    return recipe.prompt_text.strip(), "text"


def word_count(text: str) -> int:
    return len([w for w in text.replace("{", " ").replace("}", " ").replace('"', " ").split() if w.strip(",.:;")])


def snap(value: int, mult: int, lo: int, policy: str, field: str) -> int:
    """D65 size policy: a value on the grid (a multiple of `mult`, at least `lo`) passes; otherwise it is snapped down (the default),
    up, or refused with a FieldError naming the field and the two grid values around it."""
    down = max(lo, (int(value) // mult) * mult)
    up = max(lo, -(-int(value) // mult) * mult)
    if value == down:
        return down
    if policy == "error":
        raise FieldError(field, value, sorted({down, up}), f"{field} {value} is not on the model's grid (a multiple of {mult}, at least {lo})")
    return up if policy == "snap_up" else down


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
    spec = image_spec(recipe.model_id)
    sm = spec.sampling
    if not spec.recipes.t2i:
        raise CompileError(f"no T2I preset for model '{recipe.model_id}'")
    turbo = bool(recipe.turbo and sm.turbo)
    steps = recipe.steps if recipe.steps else (sm.turbo.steps if turbo and sm.turbo else sm.steps)
    if sm.distilled:
        steps = sm.steps                                      # fixed for distilled variants (09 §3b)
    guidance = recipe.guidance if recipe.guidance is not None else sm.guidance
    cfg = sm.cfg if sm.distilled else (recipe.cfg if recipe.cfg is not None else sm.cfg)
    sampler = recipe.sampler or sm.sampler
    if sampler not in SAMPLERS:
        raise CompileError(f"unknown sampler {sampler!r} (the pinned engine offers {len(SAMPLERS)})")
    scheduler = recipe.scheduler or sm.scheduler
    if scheduler not in SCHEDULERS and scheduler != FLUX2_SCHEDULE:
        raise CompileError(f"unknown scheduler {scheduler!r}")
    weight_dtype = recipe.weight_dtype or sm.weight_dtype
    if weight_dtype not in WEIGHT_DTYPES:
        raise CompileError(f"unknown weight dtype {weight_dtype!r}")
    te_device = recipe.te_device or "default"
    if te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    shift = recipe.base_shift is not None or recipe.max_shift is not None
    base_shift = recipe.base_shift if recipe.base_shift is not None else (0.5 if shift else None)      # ModelSamplingFlux node defaults
    max_shift = recipe.max_shift if recipe.max_shift is not None else (1.15 if shift else None)
    mult = spec.geometry.size_mult
    w, h = snap(recipe.width, mult, mult, recipe.size_policy, "width"), snap(recipe.height, mult, mult, recipe.size_policy, "height")
    if w * h > 4_200_000 or w < 64 or h < 64:
        raise CompileError(f"size {w}×{h} outside the 64 px – 4 MP range")
    text, mode = serialize_prompt(recipe, spec)
    return {"model_id": recipe.model_id, "te_id": resolve_te_id(spec, recipe.te_id), "width": w, "height": h, "steps": steps, "guidance": guidance, "cfg": cfg,
            "sampler": sampler, "scheduler": scheduler, "turbo": turbo, "turbo_strength": float(recipe.turbo_strength) if turbo else None,
            "distilled": sm.distilled, "negative_used": bool(recipe.negative) and not sm.distilled,
            "weight_dtype": weight_dtype, "te_device": te_device, "base_shift": base_shift, "max_shift": max_shift,
            "tiled_vae": bool(recipe.tiled_vae), "tile_size": int(recipe.tile_size) if recipe.tiled_vae else None,
            "prompt_mode": mode, "serialized_prompt": text, "word_count": word_count(text), "token_estimate": int(word_count(text) * 1.4) + 8,
            "refs": min(len(recipe.refs), spec.inputs.refs_max), "max_refs": spec.inputs.refs_max, "loras": [l.model_dump() for l in recipe.loras]}


def build_t2i(recipe: T2I, roster: Roster, seed: int, out_prefix: str, ref_files: dict[str, str] | None = None) -> Compiled:
    spec = image_spec(recipe.model_id)
    ep = effective_params(recipe)
    _, unet = roster.require(recipe.model_id)
    _, te = roster.require(ep["te_id"])
    _, vae = roster.require(spec.roles.vae or "")
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
    for i, ref in enumerate(recipe.refs[: spec.inputs.refs_max]):
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
        _, lora = roster.require(spec.sampling.turbo.lora)  # type: ignore[union-attr]
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
def _flux2_loaders(g: dict[str, Any], roster: Roster, model_id: str, spec: ModelSpec, te_device: str | None = None,
                   te_id: str | None = None) -> list:
    """UNET / text encoder / VAE loaders for a FLUX.2-family model; returns the model link (the Turbo LoRA when the spec has one).
    `te_id` swaps in a listed alternate encoder (D31); a .gguf goes through CLIPLoaderGGUF."""
    if te_device is not None and te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    _, unet = roster.require(model_id)
    _, te = roster.require(resolve_te_id(spec, te_id))
    _, vae = roster.require(spec.roles.vae or "")
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": spec.sampling.weight_dtype}}
    g["2"] = _te_loader(te, te_device)
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
    if spec.sampling.turbo:
        _, lora = roster.require(spec.sampling.turbo.lora)
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}}
        return ["4", 0]
    return ["1", 0]


def build_inpaint(recipe: Inpaint, roster: Roster, seed: int, out_prefix: str, image_name: str, mask_name: str, w: int, h: int,
                  variant: str = "full") -> Compiled:
    model_id = inpaint_model_id(recipe, variant)
    spec = image_spec(model_id, "preset for inpaint model")
    sm = spec.sampling
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, model_id, spec, recipe.te_device, recipe.te_id)
    prompt = recipe.prompt_text.strip()
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["102"] = {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}}
    image, mask = ["100", 0], ["102", 0]
    summary: dict[str, Any] = {"mode": recipe.mode, "model_id": model_id, "width": w, "height": h, "seed": int(seed), "feather": recipe.feather, "margin_pct": recipe.margin_pct}
    if recipe.mode in ("fill", "fill_hero", "outpaint"):
        # LanPaint: image-encode with the mask, ReferenceLatent of the same image, custom sampler with LanPaint steps
        steps = int(sm.edit_steps if sm.edit_steps is not None else sm.steps)
        guidance = float(sm.edit_guidance if sm.edit_guidance is not None else sm.guidance)
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
        if recipe.mode == "remove" and not recipe.prefill:          # D62: a content-aware pre-fill is the reference instead of mid grey
            g["15"] = {"class_type": "EmptyImage", "inputs": {"width": w, "height": h, "batch_size": 1, "color": 0x808080}}
            g["16"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": image, "source": ["15", 0], "x": 0, "y": 0, "resize_source": False, "mask": mask}}
            ref_pixels = ["16", 0]
        g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ref_pixels, "vae": ["3", 0]}}
        g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
        g["9"] = {"class_type": "InpaintModelConditioning", "inputs": {"positive": ["8", 0], "negative": ["6", 0], "vae": ["3", 0], "pixels": image, "mask": mask, "noise_mask": True}}
        g["10"] = {"class_type": "DifferentialDiffusion", "inputs": {"model": model_link}}
        g["11"] = {"class_type": "KSampler", "inputs": {"model": ["10", 0], "seed": int(seed), "steps": int(sm.steps), "cfg": float(sm.cfg),
                                                        "sampler_name": "euler", "scheduler": "simple", "positive": ["9", 0], "negative": ["9", 1],
                                                        "latent_image": ["9", 2], "denoise": 1.0}}
        g["12"] = {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}}
        g["13"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": image, "source": ["12", 0], "x": 0, "y": 0, "resize_source": False, "mask": mask}}
        out = "13"
        summary |= {"sampler": "icm", "steps": int(sm.steps), "cfg": float(sm.cfg), "hole": recipe.mode == "remove", "prefill": bool(recipe.prefill)}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": [out, 0], "filename_prefix": out_prefix}}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


def build_i2i(recipe: I2I, roster: Roster, seed: int, out_prefix: str, image_name: str, w: int, h: int) -> Compiled:
    spec = image_spec(recipe.model_id, "preset for refine model")
    sm = spec.sampling
    if not spec.recipes.i2i:
        raise CompileError("refine needs Klein base or FLUX.2 dev: distilled Klein cannot partial-denoise (04 §4)")
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, recipe.model_id, spec, recipe.te_device, recipe.te_id)
    steps = int(recipe.steps or (sm.edit_steps if sm.edit_steps is not None else sm.steps))
    strength = max(0.05, min(1.0, float(recipe.strength)))
    prompt = recipe.prompt_text.strip()
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": float(sm.guidance)}}
    if sm.edit_negative == "zero_out":
        g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    else:
        g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, text, watermark", "clip": ["2", 0]}}
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["8"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": steps, "cfg": float(sm.cfg), "sampler_name": "euler", "scheduler": "simple",
                                                 "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0], "denoise": strength}}
    g["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": recipe.model_id, "source": recipe.source, "strength": strength, "steps": steps, "cfg": float(sm.cfg), "guidance": float(sm.guidance), "width": w, "height": h, "seed": int(seed)}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


def upscale_factor(model_id: str) -> int:
    spec = registry.get(model_id)
    if spec is None or spec.recipes.upscale_factor is None:
        raise CompileError(f"{model_id!r} is not an upscaler")
    return spec.recipes.upscale_factor


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
        spec = registry.get(recipe.refine_model_id)
        if spec is None or spec.graph not in registry.IMAGE_GRAPHS or not spec.recipes.i2i:
            raise CompileError("tiled refine needs Klein base or FLUX.2 dev (distilled Klein cannot partial-denoise)")
        sm = spec.sampling
        model_link = _flux2_loaders(g, roster, recipe.refine_model_id, spec, recipe.te_device, recipe.te_id)
        steps = int(recipe.steps or (sm.edit_steps if sm.edit_steps is not None else sm.steps))
        prompt = recipe.prompt_text.strip()
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
        g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": float(sm.guidance)}}
        g["7"] = ({"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}} if sm.edit_negative == "zero_out"
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
            g[ks] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed) + i, "steps": steps, "cfg": float(sm.cfg), "sampler_name": "euler",
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
    seg_id = registry.segment_model(recipe.mode)
    if recipe.mode == "subject":
        _, name = roster.require(seg_id)
        g["1"] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": name}}
        g["2"] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["100", 0]}}
        mask: list = ["2", 0]
        summary: dict[str, Any] = {"model_id": seg_id, "mode": "subject"}
    else:
        _, ckpt = roster.require(seg_id)
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
        summary = {"model_id": seg_id, "mode": recipe.mode, "threshold": recipe.threshold, "points": len(points or []), "box": box}
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


def _vram(model_id: str) -> float:
    spec = registry.get(model_id)
    return spec.estimates.vram_gb if spec else 12.0


def estimate_vram_gb(recipe: T2I | I2I | Inpaint | Upscale | Segment | I2V, variant: str = "full") -> float:
    if isinstance(recipe, Inpaint) and recipe.mode == "quick_remove":
        return 0.0                                                    # R3 (D62): CPU only, the engine is never started
    if isinstance(recipe, Upscale) and recipe.refine:
        return _vram(recipe.refine_model_id)
    if isinstance(recipe, Inpaint):
        return _vram(inpaint_model_id(recipe, variant))               # C10: Fill Hero runs dev, whatever the panel named
    return _vram(recipe.model_id)


def recipe_weights(recipe: T2I | I2I | Inpaint | Upscale | Segment | I2V, variant: str = "full") -> list[str]:
    """Every roster id a recipe would load — the open-variant gate (C3, D26) and the admission estimate read this."""
    if isinstance(recipe, I2V):
        spec = registry.get(recipe.model_id)
        return spec.weights() if spec else [recipe.model_id]
    if isinstance(recipe, Inpaint) and recipe.mode == "quick_remove":
        return []                                                     # R3 (D62): no weights at all

    te_over = getattr(recipe, "te_id", None)

    def model_ids(mid: str, turbo: bool) -> list[str]:
        spec = registry.get(mid)
        return spec.weights(te_over, turbo) if spec else [mid]

    ids: list[str] = []
    if isinstance(recipe, T2I):
        ids += model_ids(recipe.model_id, bool(recipe.turbo))
    elif isinstance(recipe, Inpaint):
        ids += model_ids(inpaint_model_id(recipe, variant), True)      # _flux2_loaders chains the spec's Turbo LoRA in the Edit graphs
    elif isinstance(recipe, I2I):
        ids += model_ids(recipe.model_id, True)
    elif isinstance(recipe, Upscale):
        ids.append(recipe.model_id)
        if recipe.refine:
            ids += model_ids(recipe.refine_model_id, True)
    else:
        ids.append(recipe.model_id)
    ids += [l.model_id for l in getattr(recipe, "loras", [])]
    return list(dict.fromkeys(ids))


# D64: Quick Remove has no model — its baseline is the D62 rig (CPU, seconds); every other document job reads its model's spec
CPU_SECONDS = 1.0


def doc_estimate_seconds(recipe: I2I | Inpaint | Upscale | Segment, variant: str = "full") -> dict[str, Any]:
    """ETA of one document job (per candidate), from the spec of the model that runs. A tiled refine adds about one `tile_seconds` per
    tile of the upscaled image — the region is not known before the document is read, so the source says so."""
    if isinstance(recipe, Inpaint) and recipe.mode == "quick_remove":
        return {"seconds": CPU_SECONDS, "source": "baseline (D62 rig, CPU)"}
    if isinstance(recipe, Segment):
        spec = registry.get(registry.segment_model(recipe.mode))
        return {"seconds": spec.estimates.doc_seconds if spec else None, "source": "baseline (M5 acceptance, warm)"}
    if isinstance(recipe, Upscale):
        spec = registry.get(recipe.model_id)
        out = {"seconds": spec.estimates.doc_seconds if spec else None, "source": f"baseline ({spec.label if spec else recipe.model_id})"}
        if recipe.refine:
            ref = registry.get(recipe.refine_model_id)
            tile = ref.estimates.tile_seconds if ref and ref.estimates.tile_seconds else None
            out["source"] += f"; tiled refine adds ≈ {tile:.0f} s per {recipe.tile}² tile" if tile else "; tiled refine adds time per tile"
        return out
    mid = inpaint_model_id(recipe, variant) if isinstance(recipe, Inpaint) else recipe.model_id
    spec = registry.get(mid)
    return {"seconds": spec.estimates.doc_seconds if spec else None, "source": "baseline (rig, warm, incl. model swap)"}


def estimate_seconds(recipe: T2I, history: list[dict] | None = None) -> dict[str, Any]:
    """ETA per image (09 §3c): rolling average of this project's matching jobs, else the spike baseline scaled by
    pixels (≈ linear) and steps. `history` rows: {model_id, px, steps, wall_s}."""
    ep = effective_params(recipe)
    px = ep["width"] * ep["height"]
    matches = [h for h in (history or []) if h.get("model_id") == recipe.model_id and h.get("wall_s") and abs(h.get("px", 0) - px) / px < 0.25 and h.get("steps") == ep["steps"]]
    if len(matches) >= 2:
        recent = matches[-5:]
        return {"seconds": round(sum(h["wall_s"] for h in recent) / len(recent), 1), "source": f"measured ({len(recent)} jobs)"}
    spec = registry.get(recipe.model_id)
    est = spec.estimates if spec else None
    base = (est.turbo_seconds if ep["turbo"] else est.base_seconds) if est else None
    base = base if base is not None else 60.0
    turbo = spec.sampling.turbo if spec else None
    base_steps = (turbo.steps if ep["turbo"] and turbo else (spec.sampling.steps if spec else 20))
    seconds = base * (px / (960 * 544)) * (ep["steps"] / max(1, base_steps)) + 4 * len(recipe.refs)
    return {"seconds": round(seconds, 1), "source": "baseline (spikes)"}
