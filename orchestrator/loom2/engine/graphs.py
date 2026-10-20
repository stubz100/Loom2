"""Recipe → ComfyUI API graph (06 §3b, the recipe compiler). One builder per recipe kind; every builder resolves
roster ids through the `Roster`, never types a file name, and the result is contract-checked against
`/object_info` before submission. M3: T2I on FLUX.2 dev (JSON through the Mistral template) and Klein (prose),
with Turbo / LoRA chains, reference images and an exact serialisation preview (09 §3a).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from ..recipes import (FLUX2_SCHEDULE, SAMPLERS, SCHEDULERS, TE_DEVICES, WEIGHT_DTYPES, T2I, I2I, ImageToMesh, Inpaint, Keypoints, MatteSequence, AssembleFinal, I2V, LoraRef, Reangle, RefImage, Render, Segment, StageShot, TrainLora, TTS, Upscale,
                       inpaint_model_id, reangle_method, reangle_model_id, stage_model_id)
from ..edit_ai import plan_tiles
from ..models import registry
from ..models.spec import ModelSpec
from ..roster import Roster, ROSTER_BY_ID
from .contract import check_graph, resolve_names
from .image_families import family


def image_spec(model_id: str, what: str = "T2I preset") -> ModelSpec:
    """D65: the spec of an image model (the FLUX.2 family; D89's creative families) — a CompileError for anything else."""
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


def recipe_te_id(recipe: T2I | I2I | Inpaint | Upscale | StageShot, variant: str = "full") -> str | None:
    """The encoder a FLUX.2-family recipe will load (None for recipes without one); raises CompileError on a bad override."""
    if isinstance(recipe, Inpaint):
        mid = inpaint_model_id(recipe, variant)
    elif isinstance(recipe, Upscale):
        if not recipe.refine:
            return None
        mid = recipe.refine_model_id
    elif isinstance(recipe, (T2I, I2I)):
        mid = recipe.model_id
    elif isinstance(recipe, StageShot):
        mid = stage_model_id(recipe, variant)                             # ST3: the model the method runs in this build
    else:
        return None
    spec = registry.get(mid)
    return None if spec is None or spec.roles.te is None or spec.graph not in registry.IMAGE_GRAPHS else resolve_te_id(spec, recipe.te_id)


def _te_loader(te_name: str, te_device: str | None, clip_type: str = "flux2") -> dict[str, Any]:
    """Core CLIPLoader for safetensors; ComfyUI-GGUF's CLIPLoaderGGUF for a .gguf (no device input — it loads on the default device).
    `clip_type` is the family's (D89: krea2, lumina2 for Z-Image, chroma)."""
    if te_device is not None and te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    if te_name.lower().endswith(".gguf"):
        if te_device not in (None, "default"):
            raise CompileError("a GGUF text encoder loads on the default device (CLIPLoaderGGUF has no device input)")
        return {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": te_name, "type": clip_type}}
    return {"class_type": "CLIPLoader", "inputs": {"clip_name": te_name, "type": clip_type, "device": te_device or "default"}}


# ---- image-to-video (M6; 11 §3b; D8 Wan 2.2, D9 LTX-2.3; recipes from the E4/E4b/E4c/E5b spikes) -------------
def video_spec(model_id: str) -> ModelSpec:
    spec = registry.get(model_id)
    if spec is None or not (spec.recipes.i2v or spec.recipes.animate or spec.recipes.lipsync) or spec.video is None:
        raise CompileError(f"{model_id!r} is not an image-to-video model (Wan 2.2 or LTX-2.3)")
    return spec


def animate_pad_size(recipe: I2V) -> tuple[int, int]:
    """CN4: the size the reference is padded to before upload (the clip's own, after the grid) — E19: never cropped."""
    ep = i2v_params(recipe)
    return int(ep["width"]), int(ep["height"])


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
    if spec.graph in ("wan_animate", "wan_s2v"):                      # CN4 / D88 XL: one window (77 frames)
        if geo.frames and frames > geo.frames:
            raise FieldError("frames", recipe.frames, [geo.frames], f"{spec.label} makes one window of up to {geo.frames} frames (E19); shorten the range")
        steps = recipe.steps or p.steps
        out |= {"steps": steps, "cfg": recipe.cfg if recipe.cfg is not None else (p.cfg_high or 1.0), "shift": recipe.shift if recipe.shift is not None else (p.shift or 8.0),
                "label": p.label}
    elif spec.graph == "wan22":
        steps = recipe.steps or p.steps
        out |= {"steps": steps, "split": max(1, min(steps - 1, round(steps * p.split / p.steps))), "cfg_high": recipe.cfg if recipe.cfg is not None else p.cfg_high,
                "cfg_low": p.cfg_low, "shift": recipe.shift if recipe.shift is not None else p.shift, "lora_high": p.lora_high, "lora_low": p.lora_low, "label": p.label}
    else:
        steps = recipe.steps or p.steps
        out |= {"steps": steps, "shift": recipe.shift, "label": f"{spec.label.split(' · ')[0]} · {steps} steps"}
    return out


def build_i2v(recipe: I2V, roster: Roster, seed: int, out_prefix: str, start_name: str, end_name: str | None = None,
              beat_names: dict[str, str] | None = None, guide_name: str | None = None, lead_name: str | None = None,
              audio_name: str | None = None, carry_names: list[str] | None = None) -> Compiled:
    """Wan: loaders → ModelSamplingSD3 ×2 → WanImageToVideo / WanFirstLastFrameToVideo → KSamplerAdvanced high → low → VAEDecode
    → SaveImage (one PNG per frame: the clip master; the proxy is encoded by the orchestrator). LTX: the E5 graph — joint
    audio-video latent, LTXVAddGuide for the end frame (frame_idx −1) and every beat — ending in SaveImage the same way. ST4 (D76): with
    `recipe.guide`, the IC-LoRA Union on the model, `GetICLoRAParameters` and one more `LTXVAddGuide` on the uploaded guide video at
    frame 0 — the E11 graph."""
    ep = i2v_params(recipe)
    spec = video_spec(recipe.model_id)
    if recipe.extend_from and spec.recipes.extend_lead is None:
        raise CompileError(f"{spec.label} does not continue clips (extend)")
    if recipe.extend_from and recipe.extend_from.lead > 1 and not lead_name:
        raise CompileError("the lead-in frames were not uploaded to the engine (pipeline.prepare_i2v)")
    if spec.graph == "wan_s2v":                                       # D88 XL: the line is the whole point
        if not recipe.audio or not audio_name:
            raise CompileError(f"{spec.label} follows a spoken line — give it the line's audio")
        if recipe.end_asset or recipe.beats or recipe.guide or recipe.extend_from:
            raise CompileError(f"{spec.label} takes one image and one line — no end frame, beats, guide or extension")
    elif recipe.audio:
        raise CompileError(f"{spec.label} does not follow audio (lip-sync is the S2V model's)")
    if spec.graph == "wan_animate":                                   # CN4: the pose pass is the whole point
        if not recipe.guide or recipe.guide.kind != "pose":
            raise CompileError(f"{spec.label} performs the Stage's pose sequence — render the pose sequence and pass it as the guide")
        if recipe.end_asset or recipe.beats:
            raise CompileError(f"{spec.label} takes one reference image — no end frame, no beats")
        chain = recipe.chain
        if chain and chain.clip_id and len(carry_names or []) != chain.carry:
            raise CompileError("the previous batch's last frames were not uploaded to the engine (pipeline.prepare_i2v)")
    elif recipe.chain:
        raise CompileError(f"{spec.label} does not perform in batches (a pose-driven model does)")
    elif recipe.guide and (spec.graph != "ltx23" or not spec.recipes.guide_lora):
        raise CompileError(f"a pass-sequence guide needs LTX-2.3 with its IC-LoRA; {spec.label} has none")
    if recipe.guide and not guide_name:
        raise CompileError("the guide video was not uploaded to the engine (pipeline.prepare_i2v)")
    roles, video = spec.roles, spec.video
    assert roles.te is not None and roles.vae is not None and video is not None
    w, h, frames, fps = ep["width"], ep["height"], ep["frames"], ep["fps"]
    g: dict[str, Any] = {}

    def load_scaled(nid: str, name: str) -> list:
        g[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[nid + "s"] = {"class_type": "ImageScale", "inputs": {"image": [nid, 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        return [nid + "s", 0]

    if spec.graph == "wan_animate":                                   # CN4 (E19's graph): the reference padded by prepare_i2v, the pose pass scaled to the clip
        _, unet = roster.require(spec.id)
        _, lora = roster.require(roles.extra["lightning"])
        _, cv = roster.require(roles.extra["clip_vision"])
        _, te = roster.require(roles.te.default)
        _, vae = roster.require(roles.vae)
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
        g["1l"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}}
        g["1s"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1l", 0], "shift": ep["shift"]}}
        g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
        g["4"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": cv}}
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.prompt_text, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative if recipe.negative is not None else video.negative, "clip": ["2", 0]}}
        ref = load_scaled("100", start_name)
        g["8"] = {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["4", 0], "image": ref, "crop": "center"}}
        g["52"] = {"class_type": "LoadVideo", "inputs": {"file": guide_name}}
        g["53"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["52", 0]}}
        g["54"] = {"class_type": "ImageScale", "inputs": {"image": ["53", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        g["11"] = {"class_type": "WanAnimateToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": w, "height": h, "length": frames,
                                                                "batch_size": 1, "clip_vision_output": ["8", 0], "reference_image": ref, "pose_video": ["54", 0],
                                                                "continue_motion_max_frames": chain.carry if chain else 5,
                                                                "video_frame_offset": chain.offset if chain else 0}}
        if carry_names:                                               # D111 (PS5c, E23a W1): the previous batch's last frames continue the motion
            link: list = ["c0", 0]
            for i, n in enumerate(carry_names):
                g[f"c{i}"] = {"class_type": "LoadImage", "inputs": {"image": n}}
                if i:
                    g[f"cb{i}"] = {"class_type": "ImageBatch", "inputs": {"image1": link, "image2": [f"c{i}", 0]}}
                    link = [f"cb{i}", 0]
            g["11"]["inputs"]["continue_motion"] = link
        g["12"] = {"class_type": "KSampler", "inputs": {"model": ["1s", 0], "seed": seed, "steps": ep["steps"], "cfg": ep["cfg"], "sampler_name": "euler", "scheduler": "simple",
                                                        "positive": ["11", 0], "negative": ["11", 1], "latent_image": ["11", 2], "denoise": 1.0}}
        g["13"] = {"class_type": "TrimVideoLatent", "inputs": {"samples": ["12", 0], "trim_amount": ["11", 3]}}
        g["14"] = {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}}
        out_node = "15"
        g[out_node] = {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": out_prefix}}
    elif spec.graph == "wan_s2v":                                     # D88 XL (E18's graph): wav2vec2 on the line → WanSoundImageToVideo
        _, unet = roster.require(spec.id)
        _, te = roster.require(roles.te.default)
        _, vae = roster.require(roles.vae)
        _, aenc = roster.require(roles.extra["audio_encoder"])
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
        g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
        g["4"] = {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": aenc}}
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.prompt_text, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative if recipe.negative is not None else video.negative, "clip": ["2", 0]}}
        g["8"] = {"class_type": "LoadAudio", "inputs": {"audio": audio_name}}
        g["9"] = {"class_type": "AudioEncoderEncode", "inputs": {"audio_encoder": ["4", 0], "audio": ["8", 0]}}
        g["10"] = {"class_type": "WanSoundImageToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": w, "height": h, "length": frames,
                                                                    "batch_size": 1, "audio_encoder_output": ["9", 0], "ref_image": load_scaled("100", start_name)}}
        g["11"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": ep["shift"]}}
        g["12"] = {"class_type": "KSampler", "inputs": {"model": ["11", 0], "seed": seed, "steps": ep["steps"], "cfg": ep["cfg"], "sampler_name": "uni_pc", "scheduler": "simple",
                                                        "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["10", 2], "denoise": 1.0}}
        g["13"] = {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}}
        out_node = "14"
        g[out_node] = {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": out_prefix}}
    elif spec.graph == "wan22":
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
        model_link: list = ["1", 0]
        if recipe.guide and guide_name:                                     # ST4: the IC-LoRA and the guide video, last in the chain (E11)
            _, ic = roster.require(spec.recipes.guide_lora or "")
            g["50"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": ic, "strength_model": 1.0}}
            g["51"] = {"class_type": "GetICLoRAParameters", "inputs": {"iclora_model": ["50", 0]}}
            g["52"] = {"class_type": "LoadVideo", "inputs": {"file": guide_name}}
            g["53"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["52", 0]}}
            g["54"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["3", 0], "latent": lat, "image": ["53", 0],
                                                            "frame_idx": 0, "strength": float(recipe.guide.strength), "iclora_parameters": ["51", 0]}}
            pos, neg, lat = ["54", 0], ["54", 1], ["54", 2]
            model_link = ["50", 0]
        if recipe.extend_from and lead_name:                               # D88 XE (E17 A): the previous clip's last frames pinned at frame 0, last in the chain
            g["56"] = {"class_type": "LoadVideo", "inputs": {"file": lead_name}}
            g["57"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["56", 0]}}
            g["58"] = {"class_type": "ImageScale", "inputs": {"image": ["57", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
            g["59"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["3", 0], "latent": lat, "image": ["58", 0],
                                                            "frame_idx": 0, "strength": 1.0}}
            pos, neg, lat = ["59", 0], ["59", 1], ["59", 2]
        g["12"] = {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": frames, "frame_rate": fps, "batch_size": 1, "audio_vae": ["99", 0]}}
        g["13"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": lat, "audio_latent": ["12", 0]}}
        g["14"] = {"class_type": "BasicGuider", "inputs": {"model": model_link, "conditioning": pos}}
        g["15"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
        g["16"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        g["17"] = {"class_type": "LTXVScheduler", "inputs": {"steps": ep["steps"], "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": ["13", 0]}}
        g["18"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["15", 0], "guider": ["14", 0], "sampler": ["16", 0], "sigmas": ["17", 0], "latent_image": ["13", 0]}}
        g["19"] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["18", 0]}}
        g["20"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": pos, "negative": neg, "latent": ["19", 0]}}
        g["21"] = {"class_type": "VAEDecode", "inputs": {"samples": ["20", 2], "vae": ["3", 0]}}
        out_node = "22"
        g[out_node] = {"class_type": "SaveImage", "inputs": {"images": ["21", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": recipe.model_id, **{k: v for k, v in ep.items() if k != "label"}, "label": ep["label"],
               **({"guide": recipe.guide.kind, "guide_strength": recipe.guide.strength} if recipe.guide else {}),
               **({"extend_from": recipe.extend_from.clip_id, "lead": recipe.extend_from.lead} if recipe.extend_from else {}),
               **({"audio": recipe.audio.asset_id} if recipe.audio else {}), **({"experimental": True} if recipe.extend_from or recipe.audio else {})}
    return Compiled(graph=g, output_node=out_node, summary=summary, serialized_prompt=recipe.prompt_text)


def estimate_i2v_seconds(recipe: I2V) -> dict[str, Any]:
    """The plain clip's estimate; a guided clip (ST4) is scaled by E11's measured ratio (guide_seconds over the Draft preset's seconds)."""
    est = _estimate_i2v_plain(recipe)
    if recipe.audio:
        return {**est, "source": "baseline (E18 2026-10-15: S2V, 77 frames at 832×480) — experimental"}
    if recipe.guide and (registry.get(recipe.model_id) or video_spec(recipe.model_id)).recipes.animate:
        return {**est, "source": "baseline (E19 2026-10-15: Animate Move, 77 frames at 832×480)"}     # its preset's seconds are the guided figure
    if recipe.guide:
        spec = registry.get(recipe.model_id)
        draft = (spec.video.presets.get("draft").seconds if spec and spec.video and spec.video.presets.get("draft") else None) if spec else None
        ratio = (spec.recipes.guide_seconds / draft) if spec and spec.recipes.guide_seconds and draft else 1.25
        if est.get("seconds") is not None:
            est = {**est, "seconds": round(float(est["seconds"]) * ratio, 1), "source": f"{est.get('source', 'baseline')} × {ratio:.2f} for the IC-LoRA guide (E11 2026-10-12)"}
    return est


def _estimate_i2v_plain(recipe: I2V) -> dict[str, Any]:
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


def kept_refs(recipe: T2I, spec: ModelSpec) -> list:
    """D73: the references the model takes (its `refs_max`, in order); the rest are dropped — and said so (`refs_dropped`), never silently."""
    return recipe.refs[: spec.inputs.refs_max]


def _unmention(v: Any, names: list[str]) -> Any:
    """D73: '@hero' → 'hero' in every string of the prompt (the mention's images and note carry the rest)."""
    if isinstance(v, str):
        for n in names:
            v = v.replace("@" + n, n)
        return v
    if isinstance(v, list):
        return [_unmention(x, names) for x in v]
    if isinstance(v, dict):
        return {k: _unmention(x, names) for k, x in v.items()}
    return v


def _then(text: str, more: str) -> str:
    """`text`, then `more` as the next sentence."""
    text = text.rstrip()
    if not more:
        return text
    if not text:
        return more
    return f"{text}{'' if text[-1] in '.!?' else '.'} {more}"


def ref_notes(recipe: T2I, spec: ModelSpec, bound: set[int] | None = None) -> list[tuple[int, str]]:
    """(index, note) of the kept references that have a note — 1-based, the numbering the prompt uses ('image 1'). D93 (A3): the ones a
    subject binds (`bound`) are said by the subject instead."""
    return [(i + 1, r.note.strip()) for i, r in enumerate(kept_refs(recipe, spec)) if r.note and r.note.strip() and (i + 1) not in (bound or set())]


def binds_refs(recipe: T2I, spec: ModelSpec) -> bool:
    """D93 (A3): whether the prompt binds linked subjects to their references — the recipe's choice, else the model's spec."""
    return bool(spec.inputs.refs_max) and (recipe.bind_refs if recipe.bind_refs is not None else spec.inputs.bind_refs)


def ref_span(idx: list[int]) -> str:
    """'reference image 2', 'reference images 1–3', 'reference images 1, 3' (the words the prompt and the subject card use)."""
    if len(idx) == 1:
        return f"reference image {idx[0]}"
    run = idx == list(range(idx[0], idx[0] + len(idx)))
    return f"reference images {idx[0]}–{idx[-1]}" if run else "reference images " + ", ".join(map(str, idx))


def _binding(m: Any, role: str, at: int | None, refs: list, kept: list, offset: int = 0) -> dict[str, Any]:
    """One linked mention's binding: the kept references it gave (numbered as the prompt numbers them, from `offset` + 1) and how many of its
    set did not fit (left out by the resolver, or cut at the model's limit)."""
    idx = [offset + i + 1 for i, r in enumerate(kept) if r.mention == m.group_id]
    cut = len([r for r in refs[len(kept):] if r.mention == m.group_id])
    return {"subject": at, "role": role, "name": m.name, "profile_id": m.profile_id, "version": m.version, "refs": idx, "span": ref_span(idx) if idx else None,
            "skipped": (m.skipped or 0) + cut}


def subject_bindings(recipe: T2I, spec: ModelSpec) -> list[dict[str, Any]]:
    """D93 (A3): each subject card linked to a profile (a resolved mention with `subject`) and the kept references its mention gave, 1-based;
    `skipped` counts the set's images that did not fit (left out by the resolver, or cut at the model's limit). Only subjects the prompt
    has (tree / JSON modes). D93 (C6): also each prop a subject holds (`role` held, `subject` = its holder) and the place of the scene
    (`role` scene, `subject` None)."""
    tree = (recipe.prompt_json or {}) if recipe.prompt_mode in ("tree", "json") else {}
    subs = tree.get("subjects")
    subs = subs if isinstance(subs, list) else []
    kept = kept_refs(recipe, spec)
    ok = lambda k: k is not None and k < len(subs) and isinstance(subs[k], dict)  # noqa: E731
    out: list[dict[str, Any]] = []
    for m in recipe.mentions:
        if not m.profile_id:
            continue
        if m.subject is not None:
            if ok(m.subject) and not any(b["role"] == "subject" and b["subject"] == m.subject for b in out):
                out.append(_binding(m, "subject", m.subject, recipe.refs, kept))
        elif m.held_by is not None:
            if ok(m.held_by) and subs[m.held_by].get("holding") and not any(b["role"] == "held" and b["subject"] == m.held_by for b in out):
                out.append(_binding(m, "held", m.held_by, recipe.refs, kept))
        elif m.scene and isinstance(tree.get("scene"), str) and tree.get("scene") and not any(b["role"] == "scene" for b in out):
            out.append(_binding(m, "scene", None, recipe.refs, kept))
    return out


def _lead(text: str, name: str, span: str | None) -> str:
    """D93 (A3): the name with the range in brackets leading a clause ("Mara (reference images 1–3), a wiry courier …"); a clause that does
    not start with the name gets it. Without a range the clause is returned as it is."""
    d = (text or "").strip()
    if not span:
        return d
    lead = f"{name} ({span})"
    if name and d.lower().startswith(name.lower()):
        return lead + d[len(name):]
    return f"{lead}, {d}" if d else lead


def _bind_subject(sub: dict, name: str, span: str, prose: bool) -> dict:
    """D93 (A3): a subject that names its references the way its family reads them — a JSON field for the JSON-prompted models
    (`"reference": "reference images 1–3"`), the name with the range in brackets leading the description in prose ("Mara (reference
    images 1–3), a wiry courier …")."""
    if not prose:
        return {**sub, "reference": span}
    return {**sub, "description": _lead(str(sub.get("description") or ""), name, span)}


def _hold(sub: dict, prose: bool, name: str = "", span: str | None = None) -> dict:
    """D93 (C6): the prop a subject holds, said as its family reads it — prose: ", holding <the prop's clause>" after the description (its name
    and range leading it when bound: "holding the compass (reference image 3), a brass compass …"); JSON: `"holding": "<clause>"`, or
    `{"description", "reference"}` when bound."""
    clause = str(sub.get("holding") or "").strip()
    if not clause:
        return {k: v for k, v in sub.items() if k != "holding"}
    if not prose:
        return {**sub, "holding": {"description": clause, "reference": span} if span else clause}
    d = str(sub.get("description") or "").strip().rstrip(",")
    held = "holding " + _lead(clause, name, span)
    return {**{k: v for k, v in sub.items() if k != "holding"}, "description": f"{d}, {held}" if d else held}


def serialize_prompt(recipe: T2I, spec: ModelSpec | None = None) -> tuple[str, str]:
    """The exact string the engine receives and how it was produced: 'json' | 'prose' | 'text'. D73: reference notes go in per model
    family — a JSON-prompted model (dev) gets a `references: [{index, note}]` section, prose and text prompts (Klein) a sentence per
    image ("Image 2 shows the hero."); @mentions read as the plain name."""
    spec = spec or registry.get(recipe.model_id) or registry.SPECS[registry.default_model("t2i")]
    names = sorted((m.name for m in recipe.mentions if m.name), key=len, reverse=True)
    binds = [b for b in subject_bindings(recipe, spec) if b["refs"]] if binds_refs(recipe, spec) else []   # D93 (A3, C6)
    notes = ref_notes(recipe, spec, {i for b in binds for i in b["refs"]})
    sentences = " ".join(f"Image {i} shows {n.rstrip('.')}." for i, n in notes)
    style = (recipe.style_text or "").strip()                                   # D85: the Story style's fragment, appended after the prompt (loom R104)
    prompt_text = _unmention(recipe.prompt_text.strip(), names)
    if recipe.prompt_mode in ("tree", "json") and recipe.prompt_json:
        tree = {k: v for k, v in _unmention(recipe.prompt_json, names).items() if v not in (None, "", [], {})}
        prose = not spec.sampling.json_prompt
        if isinstance(tree.get("subjects"), list):                             # D93 (A3): each linked subject names its own references
            subs = list(tree["subjects"])
            for b in binds:
                if b["role"] == "subject":
                    subs[b["subject"]] = _bind_subject(subs[b["subject"]], b["name"] or "", b["span"], prose)
            held = {b["subject"]: b for b in binds if b["role"] == "held"}       # D93 (C6): the prop a subject holds — "holding …", bound when it has images
            subs = [_hold(x, prose, (held[k]["name"] or "") if k in held else "", held[k]["span"] if k in held else None) if isinstance(x, dict) else x for k, x in enumerate(subs)]
            tree["subjects"] = subs
        place = next((b for b in binds if b["role"] == "scene"), None)
        if place and isinstance(tree.get("scene"), str):                       # D93 (C6): the place's range leads the scene it composed
            tree["scene"] = _lead(tree["scene"], place["name"] or "", place["span"])
        if style:                                                               # the tree's own style slot (04 §3c) takes the fragment, after what is there
            cur = tree.get("style")
            tree["style"] = f"{cur}, {style}" if isinstance(cur, str) and cur.strip() else style
        if spec.sampling.json_prompt:
            if notes:
                tree["references"] = [{"index": i, "note": n} for i, n in notes]
            return json.dumps(tree, ensure_ascii=False, separators=(",", ":")), "json"
        prose = flatten_json_prompt(tree)
        text = f"{prompt_text}. {prose}" if prompt_text else prose
        return _then(text, sentences), "prose"
    return _then(_then(prompt_text, style), sentences), "text"


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
    """LT1 (18 §3b): the slots' LoRAs after the preset's own (Turbo, Lightning) and after the reference nodes (B11); a roster id by its
    file name, a `file:` id by its path under the loras folder (the contract check matches the engine's listing)."""
    from ..loras import lora_name                                                  # the slots' module reads the roster; no cycle at import
    nid = first_id
    for ref in loras:
        name = lora_name(roster, ref.model_id)
        g[str(nid)] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_link, "lora_name": name, "strength_model": float(ref.strength)}}
        model_link = [str(nid), 0]
        nid += 1
    return model_link, nid


def loras_summary(loras: list[LoraRef], roster: Roster | None) -> list[dict[str, Any]]:
    """The slots as the preview and the manifest show them: id, strength and the loader's name (display == reality, T8); without a
    roster (the estimate's effective_params) the name stays None."""
    from ..loras import lora_name
    out = []
    for l in loras:
        try:
            name = lora_name(roster, l.model_id) if roster is not None else None
        except (FileNotFoundError, KeyError):
            name = None
        out.append({**l.model_dump(), "lora_name": name})
    return out


def effective_params(recipe: T2I, roster: Roster | None = None) -> dict[str, Any]:
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
    fam = family(spec)
    guidance = (recipe.guidance if recipe.guidance is not None else sm.guidance) if fam.flux_guidance else None   # D89: no FluxGuidance, no guidance
    cfg = sm.cfg if sm.distilled else (recipe.cfg if recipe.cfg is not None else sm.cfg)
    sampler = recipe.sampler or sm.sampler
    if sampler not in SAMPLERS:
        raise CompileError(f"unknown sampler {sampler!r} (the pinned engine offers {len(SAMPLERS)})")
    scheduler = recipe.scheduler or sm.scheduler
    if scheduler not in SCHEDULERS and scheduler != FLUX2_SCHEDULE:
        raise CompileError(f"unknown scheduler {scheduler!r}")
    if scheduler == FLUX2_SCHEDULE and spec.graph not in registry.FLUX_GRAPHS:
        raise CompileError(f"the {FLUX2_SCHEDULE} schedule is FLUX.2's; {spec.short or spec.label} takes one of the engine's schedulers")
    weight_dtype = recipe.weight_dtype or sm.weight_dtype
    if weight_dtype not in WEIGHT_DTYPES:
        raise CompileError(f"unknown weight dtype {weight_dtype!r}")
    te_device = recipe.te_device or "default"
    if te_device not in TE_DEVICES:
        raise CompileError(f"unknown text-encoder device {te_device!r}")
    shift = recipe.base_shift is not None or recipe.max_shift is not None
    if shift and not fam.flux_shift:
        raise CompileError(f"base / max shift (ModelSamplingFlux) does not apply to {spec.short or spec.label}; its shift is {sm.model_shift}")
    base_shift = recipe.base_shift if recipe.base_shift is not None else (0.5 if shift else None)      # ModelSamplingFlux node defaults
    max_shift = recipe.max_shift if recipe.max_shift is not None else (1.15 if shift else None)
    mult = spec.geometry.size_mult
    w, h = snap(recipe.width, mult, mult, recipe.size_policy, "width"), snap(recipe.height, mult, mult, recipe.size_policy, "height")
    refs_max = spec.inputs.refs_max
    if len(recipe.refs) > refs_max and recipe.size_policy == "error":           # D73: no silent truncation — refused, field-named, on request
        raise FieldError("refs", len(recipe.refs), [refs_max], f"{spec.short or spec.label} takes at most {refs_max} reference image{'s' if refs_max != 1 else ''}; {len(recipe.refs)} given")
    if w * h > 4_200_000 or w < 64 or h < 64:
        raise CompileError(f"size {w}×{h} outside the 64 px – 4 MP range")
    text, mode = serialize_prompt(recipe, spec)
    bind = binds_refs(recipe, spec)
    bindings = subject_bindings(recipe, spec)                                   # D93 (A3): what each linked subject got (the card shows its slots)
    return {"model_id": recipe.model_id, "te_id": resolve_te_id(spec, recipe.te_id) if spec.roles.te else None, "width": w, "height": h, "steps": steps, "guidance": guidance, "cfg": cfg,
            "sampler": sampler, "scheduler": scheduler, "turbo": turbo, "turbo_strength": float(recipe.turbo_strength) if turbo else None,
            "distilled": sm.distilled, "negative_used": bool(recipe.negative) and not sm.distilled,
            "weight_dtype": weight_dtype, "te_device": te_device, "base_shift": base_shift, "max_shift": max_shift,
            "tiled_vae": bool(recipe.tiled_vae), "tile_size": int(recipe.tile_size) if recipe.tiled_vae else None,
            "prompt_mode": mode, "serialized_prompt": text, "word_count": word_count(text), "token_estimate": int(word_count(text) * 1.4) + 8,
            "refs": min(len(recipe.refs), refs_max), "max_refs": refs_max, "refs_dropped": max(0, len(recipe.refs) - refs_max),
            "ref_notes": len(ref_notes(recipe, spec, {i for b in bindings for i in b["refs"]} if bind else None)), "loras": loras_summary(recipe.loras, roster),
            "bind_refs": bind, "bindings": bindings,
            "style_id": recipe.style_id, "style_text": recipe.style_text}                                   # D85: what the Story style added (the manifest keeps both)


def build_t2i(recipe: T2I, roster: Roster, seed: int, out_prefix: str, ref_files: dict[str, str] | None = None) -> Compiled:
    spec = image_spec(recipe.model_id)
    ep = effective_params(recipe, roster)
    fam = family(spec)
    text = ep["serialized_prompt"]
    if not text.strip():
        raise CompileError("empty prompt")
    w, h = ep["width"], ep["height"]

    g: dict[str, Any] = {}
    model_link, clip, vae = _image_loaders(g, roster, spec, ep["te_id"], ep["te_device"], ep["weight_dtype"])
    prefix = spec.sampling.prompt_prefix or ""                                  # D91: Lumina 2's system prompt leads the positive (its example's)
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prefix + text, "clip": clip}}
    g["8"] = {"class_type": fam.latent, "inputs": {"width": w, "height": h, "batch_size": 1}}
    g["11"] = {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}}
    # decode: plain, or tiled for headroom on the Full tier (D13)
    if ep["tiled_vae"]:
        g["10"] = {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["9", 0], "vae": vae, "tile_size": int(ep["tile_size"]), "overlap": min(64, int(ep["tile_size"]) // 4),
                                                              "temporal_size": 64, "temporal_overlap": 8}}
    else:
        g["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": vae}}
    # reference images: LoadImage → (downscale) → VAEEncode → ReferenceLatent chained on the conditioning
    cond: list = ["5", 0]
    nid = 30
    ref_files = ref_files or {}
    for i, ref in enumerate(kept_refs(recipe, spec)):
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
        g[str(nid)] = {"class_type": "VAEEncode", "inputs": {"pixels": img, "vae": vae}}
        lat = [str(nid), 0]
        nid += 1
        g[str(nid)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": cond, "latent": lat}}
        cond = [str(nid), 0]
        nid += 1
    positive: list = cond
    if fam.flux_guidance:
        g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": cond, "guidance": float(ep["guidance"])}}
        positive = ["6", 0]
    if ep["negative_used"] or not (fam.flux_guidance or ep["distilled"]):       # D89: a real-CFG family encodes its negative, empty or not (the templates')
        g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.negative, "clip": clip}}
    else:
        g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
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
            g["16"] = {"class_type": "CFGGuider", "inputs": {"model": model_link, "positive": positive, "negative": ["7", 0], "cfg": float(ep["cfg"])}}
        else:
            g["16"] = {"class_type": "BasicGuider", "inputs": {"model": model_link, "conditioning": positive}}
        g["9"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["13", 0], "guider": ["16", 0], "sampler": ["14", 0], "sigmas": ["15", 0], "latent_image": ["8", 0]}}
    else:
        g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": int(ep["steps"]), "cfg": float(ep["cfg"]),
                                                     "sampler_name": ep["sampler"], "scheduler": ep["scheduler"], "positive": positive, "negative": ["7", 0],
                                                     "latent_image": ["8", 0], "denoise": 1.0}}
    summary = {k: v for k, v in ep.items() if k != "serialized_prompt"}
    if prefix:
        summary["prompt_prefix"] = prefix                                           # the manifest keeps what the encoder saw before the prompt
    return Compiled(graph=g, output_node="11", summary=summary, serialized_prompt=text)


# ---- M5 edit recipes (10 §4, D7; graphs ported from engine/spikes/e8_inpaint.py) ------------------------------
def _flux2_loaders(g: dict[str, Any], roster: Roster, model_id: str, spec: ModelSpec, te_device: str | None = None,
                   te_id: str | None = None) -> list:
    """UNET / text encoder / VAE loaders for a FLUX.2-family model; returns the model link (the Turbo LoRA when the spec has one).
    `te_id` swaps in a listed alternate encoder (D31); a .gguf goes through CLIPLoaderGGUF."""
    if spec.graph not in registry.FLUX_GRAPHS:                     # D89: inpaint, tiled refine, Angle and Stage are FLUX.2-family graphs
        raise CompileError(f"{spec.short or spec.label} runs Generate and Refine only; this graph needs a FLUX.2-family model")
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


def _image_loaders(g: dict[str, Any], roster: Roster, spec: ModelSpec, te_id: str | None, te_device: str | None,
                   weight_dtype: str) -> tuple[list, list, list]:
    """D89: the (model, clip, vae) links of a T2I / I2I graph for any image family — UNET + CLIP (the family's type) + VAE as "1" / "2" / "3"
    (the FLUX.2 graphs' ids, unchanged), or one CheckpointLoaderSimple as "1" (SD 3.5); then Chroma's T5 options ("21") and the family's
    shift node at the spec's `model_shift` ("22"). No Turbo LoRA — T2I chains it itself, the Edit graphs through `_flux2_loaders`."""
    fam = family(spec)
    _, main = roster.require(spec.id)
    if fam.clip_type is None:
        if te_id is not None or te_device not in (None, "default"):
            raise CompileError(f"{spec.short or spec.label} carries its encoders in one checkpoint: no encoder choice or device")
        g["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": main}}
        model, clip, vae = ["1", 0], ["1", 1], ["1", 2]
    else:
        _, te = roster.require(resolve_te_id(spec, te_id))
        _, vae_name = roster.require(spec.roles.vae or "")
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": main, "weight_dtype": weight_dtype}}
        g["2"] = _te_loader(te, te_device, fam.clip_type)
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}}
        model, clip, vae = ["1", 0], ["2", 0], ["3", 0]
    if fam.t5_options:
        g["21"] = {"class_type": "T5TokenizerOptions", "inputs": {"clip": clip, "min_padding": 0, "min_length": 0}}
        clip = ["21", 0]
    if fam.shift_node and spec.sampling.model_shift is not None:
        g["22"] = {"class_type": fam.shift_node, "inputs": {"model": model, "shift": float(spec.sampling.model_shift)}}
        model = ["22", 0]
    return model, clip, vae


def build_inpaint(recipe: Inpaint, roster: Roster, seed: int, out_prefix: str, image_name: str, mask_name: str, w: int, h: int,
                  variant: str = "full") -> Compiled:
    model_id = inpaint_model_id(recipe, variant)
    spec = image_spec(model_id, "preset for inpaint model")
    sm = spec.sampling
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, model_id, spec, recipe.te_device, recipe.te_id)
    model_link, _ = _lora_chain(g, model_link, recipe.loras, roster, 300)           # LT1: the slots, after the Turbo LoRA the loaders chain
    prompt = recipe.prompt_text.strip()
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["102"] = {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}}
    image, mask = ["100", 0], ["102", 0]
    summary: dict[str, Any] = {"mode": recipe.mode, "model_id": model_id, "width": w, "height": h, "seed": int(seed), "feather": recipe.feather, "margin_pct": recipe.margin_pct,
                               "loras": loras_summary(recipe.loras, roster)}
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
    fam = family(spec)
    flux = spec.graph in registry.FLUX_GRAPHS
    g: dict[str, Any] = {}
    if flux:
        model_link = _flux2_loaders(g, roster, recipe.model_id, spec, recipe.te_device, recipe.te_id)
        clip, vae = ["2", 0], ["3", 0]
        sampler, scheduler = "euler", "simple"
    else:                                                                           # D89: the creative families, at their own sampler / scheduler
        model_link, clip, vae = _image_loaders(g, roster, spec, recipe.te_id, recipe.te_device, sm.weight_dtype)
        sampler, scheduler = sm.sampler, sm.scheduler
    model_link, _ = _lora_chain(g, model_link, recipe.loras, roster, 300)           # LT1: the slots
    steps = int(recipe.steps or (sm.edit_steps if sm.edit_steps is not None else sm.steps))
    strength = max(0.05, min(1.0, float(recipe.strength)))
    prompt = recipe.prompt_text.strip()
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": (sm.prompt_prefix or "") + prompt, "clip": clip}}   # D91: a system prompt first (Lumina 2)
    positive: list = ["5", 0]
    if fam.flux_guidance:
        g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": float(sm.guidance)}}
        positive = ["6", 0]
    if sm.edit_negative == "zero_out" or (not flux and sm.distilled):
        g["7"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    else:
        g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, text, watermark", "clip": clip}}
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["8"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": vae}}
    g["9"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": steps, "cfg": float(sm.cfg), "sampler_name": sampler, "scheduler": scheduler,
                                                 "positive": positive, "negative": ["7", 0], "latent_image": ["8", 0], "denoise": strength}}
    g["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": vae}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": recipe.model_id, "source": recipe.source, "strength": strength, "loras": loras_summary(recipe.loras, roster), "steps": steps, "cfg": float(sm.cfg),
               "guidance": float(sm.guidance) if fam.flux_guidance else None, "width": w, "height": h, "seed": int(seed)}
    if not flux:
        summary |= {"sampler": sampler, "scheduler": scheduler}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


# ---- P14 (D82): a new viewpoint of an asset — the E12 pair (D77), ported from engine/spikes/e12_angles.py --------------------
# The angles LoRA's own instructions (dx8152; Chinese, no trigger word) and the Klein prompt shape that kept identity in E12 (C2).
ANGLE_INSTRUCTIONS: dict[str, str] = {
    "left45": "将镜头向左旋转45度", "right45": "将镜头向右旋转45度", "topdown": "将镜头转为俯视", "closeup": "将镜头转为特写镜头", "wide": "将镜头转为广角镜头",
}
KLEIN_VIEWS: dict[str, tuple[str, str]] = {
    "left45": ("a 45-degree front three-quarter view from the subject's left", "a front three-quarter angle 45 degrees to the left, eye-level"),
    "right45": ("a 45-degree front three-quarter view from the subject's right", "a front three-quarter angle 45 degrees to the right, eye-level"),
    "topdown": ("a high-angle top-down view", "directly above, looking straight down"),
    "closeup": ("a close-up detail view of the main subject's face and shoulders", "close up"),
    "wide": ("a wide shot showing the whole scene around the subject", "far back, a wide angle"),
}
KLEIN_VIEW_PROMPT = ("Using the input image as the strict visual reference, create {view} of the same subject. Preserve the exact identity, "
                     "proportions, silhouette, materials, colours, clothing, markings and design language from the input image. Preserve the "
                     "same expression, pose, posture, gesture and object positions; the subject stays in the same moment, only viewed from "
                     "{angle}. Photorealistic, same subject, same pose, same setting and lighting, only the viewing angle changes.")


def reangle_prompt(recipe: Reangle, variant: str = "full") -> str:
    """The exact text the engine gets: the method's own instruction for the move, then the recipe's sentence (if any)."""
    extra = recipe.prompt_text.strip()
    if reangle_method(recipe, variant) == "angles_lora":
        return ANGLE_INSTRUCTIONS[recipe.move] + (f"，{extra}" if extra else "")
    view, angle = KLEIN_VIEWS[recipe.move]
    return KLEIN_VIEW_PROMPT.format(view=view, angle=angle) + (f" {extra}" if extra else "")


def build_reangle(recipe: Reangle, roster: Roster, seed: int, out_prefix: str, image_name: str, w: int, h: int, variant: str = "full") -> Compiled:
    """angles_lora: Qwen-Image-Edit 2509 fp8 + Lightning 4-step + the Multiple-angles LoRA, the source through TextEncodeQwenImageEditPlus and
    as the latent (1 MP, the LoRA's training size). klein_prompt: Klein 9B (4B under `open`), the source as ReferenceLatent, the
    strict-reference prompt, the output at the source's size. Both measured in E12 (journal 2026-10-12)."""
    method = reangle_method(recipe, variant)
    try:
        spec = registry.get(reangle_model_id(recipe, variant))
    except ValueError as e:
        raise CompileError(str(e)) from e
    if spec is None or spec.recipes.reangle != method:
        raise CompileError(f"no spec implements the angles method {method!r}")
    prompt = reangle_prompt(recipe, variant)
    g: dict[str, Any] = {"100": {"class_type": "LoadImage", "inputs": {"image": image_name}}}
    if method == "angles_lora":
        _, unet = roster.require(spec.id)
        _, te = roster.require(spec.roles.te.default)                  # type: ignore[union-attr]
        _, vae = roster.require(spec.roles.vae or "")
        _, lightning = roster.require(spec.roles.extra["lightning"])
        _, angles = roster.require(spec.roles.extra["angles"])
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": spec.sampling.weight_dtype}}
        g["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "qwen_image", "device": "default"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lightning, "strength_model": 1.0}}
        g["41"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["4", 0], "lora_name": angles, "strength_model": 1.0}}
        g["5"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["41", 0], "shift": float(spec.sampling.model_shift or 3.0)}}
        g["6"] = {"class_type": "CFGNorm", "inputs": {"model": ["5", 0], "strength": 1.0}}
        g["20"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["100", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 8}}
        g["7"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0], "image1": ["20", 0]}}
        g["8"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": "", "vae": ["3", 0], "image1": ["20", 0]}}
        g["9"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["20", 0], "vae": ["3", 0]}}
        g["10"] = {"class_type": "KSampler", "inputs": {"model": ["6", 0], "seed": int(seed), "steps": int(spec.sampling.steps), "cfg": float(spec.sampling.cfg),
                                                      "sampler_name": spec.sampling.sampler, "scheduler": spec.sampling.scheduler,
                                                      "positive": ["7", 0], "negative": ["8", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    else:
        model_link = _flux2_loaders(g, roster, spec.id, spec, None, recipe.te_id)
        mult = spec.geometry.size_mult
        ow, oh = max(mult, (w // mult) * mult), max(mult, (h // mult) * mult)
        g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
        g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}}
        g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
        g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
        g["9"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ow, "height": oh, "batch_size": 1}}
        g["10"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": int(spec.sampling.steps), "cfg": float(spec.sampling.cfg),
                                                      "sampler_name": spec.sampling.sampler, "scheduler": spec.sampling.scheduler,
                                                      "positive": ["8", 0], "negative": ["6", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": spec.id, "method": method, "method_requested": recipe.method, "move": recipe.move, "steps": int(spec.sampling.steps),
               "cfg": float(spec.sampling.cfg), "seed": int(seed), "source_size": [w, h]}                 # what was asked and what ran
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


# ---- P13 ST3 (D78, 16 §7): the Stage → image graphs, ported from engine/spikes/e10_stage.py ----------------------------------------
STAGE_CLAY_LEAD = ("Image 1 is a grey clay blocking of this exact shot: the grey mannequins stand for the people described below, the grey blocks for the "
                   "set and props. Render it as a finished cinematic still: keep image 1's camera, framing, composition, and every figure's pose, "
                   "position and size exactly; replace every mannequin with its person and the clay with the real scene, nothing stays grey.")
STAGE_POSE_LEAD = "apply pose from image 1 with reference from image 2."
# D111 (PS5b): a plate — the clay lead names mannequins and people, and the rig's first plate came back with two men in the empty room
STAGE_SET_LEAD = ("Image 1 is a grey clay blocking of an empty set: the grey surfaces stand for the place described below. Render it as a finished "
                  "cinematic still of the empty place: keep image 1's camera, framing and composition exactly, and replace the clay with the real "
                  "surfaces. There are no people, no figures and no objects in it; nothing stays grey.")
STAGE_NEG = "blurry, low quality, deformed, extra limbs, text, watermark"
STAGE_HINTS = {"clay": "keeps the blocking (E10: 10/10 on the sheet); limbs may drift (PCK 0.60)",
               "refcontrol": "exact limbs (PCK 0.86) from the pose pass; needs one reference image, ≈ 6× slower"}


def stage_pass_for(method: str) -> str:
    """The pass a method takes as image 1: the clay for `clay`, the pose map for `refcontrol` (D81: the pose pass alone)."""
    return "pose" if method == "refcontrol" else "clay"


def stage_refs(recipe: StageShot, spec: ModelSpec) -> list[RefImage]:
    """The references that follow image 1: `refcontrol` takes exactly one (image 2), `clay` fills the model's remaining slots."""
    room = 1 if spec.recipes.stage == "refcontrol" else max(0, spec.inputs.refs_max - 1)
    return recipe.refs[:room]


def stage_binds(recipe: StageShot, spec: ModelSpec | None) -> bool:
    """D93 (C8): whether the prompt binds each figure to its references — the recipe's choice, else the method's spec (`inputs.bind_refs`)."""
    return bool(spec) and (recipe.bind_refs if recipe.bind_refs is not None else bool(spec.inputs.bind_refs))


def stage_bindings(recipe: StageShot, spec: ModelSpec | None) -> list[dict[str, Any]]:
    """D93 (C8): each figure bound to a character (resolved mentions with `figure`, in screen order left to right — `figure` N is its place,
    1-based) and the images it was given, numbered as the prompt numbers them (image 1 is the pass, the references follow from 2)."""
    kept = stage_refs(recipe, spec) if spec else []
    out = []
    for k, m in enumerate(m for m in recipe.mentions if m.figure and m.profile_id):
        b = _binding(m, "figure", k, recipe.refs, kept, offset=1)
        out.append({**b, "figure": k + 1, "object_id": m.figure, "composed": m.composed})
    return out


def stage_prompt(recipe: StageShot, variant: str = "full") -> str:
    """The exact text the engine gets: the method's lead sentence about image 1, then a sentence per noted reference ("Image 2 shows …",
    D73), then the recipe's own sentence. D93 (C8): the figures bound to characters, left to right, each with its sheet — and, when the
    method binds, its own range ("figure 1 is Mara (reference images 2–3), …"; those images' sentences are then said by the figure)."""
    spec = registry.get(stage_model_id(recipe, variant))
    extra = recipe.prompt_text.strip()
    figs = stage_bindings(recipe, spec)
    bind = stage_binds(recipe, spec)
    bound = {i for b in figs for i in b["refs"]} if bind else set()
    named = lambda b: _lead(b["composed"] or "", b["name"] or "", "") if (b["composed"] or "").lower().startswith((b["name"] or "").lower()) else ", ".join(x for x in (b["name"], b["composed"]) if x)  # noqa: E731
    who = "; ".join(f"figure {b['figure']} is " + (_lead(named(b), b["name"] or "", b["span"]) if bind else named(b)) for b in figs)
    figures = f"From left to right in image 1: {who}." if figs else ""
    if recipe.method == "refcontrol":
        text = STAGE_POSE_LEAD
    else:
        text = STAGE_SET_LEAD if recipe.empty else STAGE_CLAY_LEAD
    notes = [(i + 2, r.note.strip().rstrip(".")) for i, r in enumerate(stage_refs(recipe, spec) if spec else []) if r.note and r.note.strip() and (i + 2) not in bound]
    if recipe.method == "refcontrol":
        notes = []                                                              # E10's exact-pose sentence names image 2 itself
    text = _then(text, figures)
    for i, n in notes:
        text = _then(text, f"Image {i} shows {n}.")
    return _then(text, extra)


def build_stage_shot(recipe: StageShot, roster: Roster, seed: int, out_prefix: str, inputs: dict[str, Any], ref_files: dict[str, str] | None = None,
                     variant: str = "full") -> Compiled:
    """clay: Klein 9B (4B under `open`) with the clay pass as a ReferenceLatent on the prompt, the deck's images chained after it, the
    output at the recipe's size. refcontrol: Klein base 9B + RefControl's pose LoRA (0.9), the pose pass as image 1, the first
    reference (fitted to 0.6 MP) as image 2, the E10 negative, 30 steps at CFG 4. Both measured in E10 (journal 2026-10-12)."""
    try:
        mid = stage_model_id(recipe, variant)
    except ValueError as e:
        raise CompileError(str(e)) from e
    spec = registry.get(mid)
    if spec is None or spec.recipes.stage != recipe.method:
        raise CompileError(f"no spec implements the Stage method {recipe.method!r}")
    key = stage_pass_for(recipe.method)
    pass_name = inputs.get(key)
    if not pass_name:
        raise CompileError(f"the {key} pass was not uploaded to the engine")
    refs = stage_refs(recipe, spec)
    if recipe.method == "refcontrol" and not refs:
        raise CompileError("the exact-pose method needs one reference image (image 2)")
    prompt = stage_prompt(recipe, variant)
    mult = spec.geometry.size_mult
    w, h = max(mult, (recipe.width // mult) * mult), max(mult, (recipe.height // mult) * mult)
    g: dict[str, Any] = {}
    model_link = _flux2_loaders(g, roster, mid, spec, None, recipe.te_id)
    steps = int(spec.recipes.stage_steps or spec.sampling.steps)
    cfg = float(spec.recipes.stage_cfg if spec.recipes.stage_cfg is not None else spec.sampling.cfg)
    if recipe.method == "refcontrol":
        if not spec.recipes.stage_lora:
            raise CompileError("the exact-pose spec names no pose LoRA")
        _, lora = roster.require(spec.recipes.stage_lora)
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_link, "lora_name": lora, "strength_model": 0.9}}
        model_link = ["4", 0]
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "" if spec.sampling.distilled else STAGE_NEG, "clip": ["2", 0]}}
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": pass_name}}
    g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}          # image 1: the pass
    cond: list = ["8", 0]
    nid = 30
    ref_files = ref_files or {}
    for i, ref in enumerate(refs):
        rkey = ref.asset_id or ref.blob or ""
        rname = ref_files.get(rkey)
        if not rname:
            raise CompileError(f"reference image {i + 2} ({rkey}) was not uploaded to the engine")
        g[str(nid)] = {"class_type": "LoadImage", "inputs": {"image": rname}}
        img: list = [str(nid), 0]
        nid += 1
        if recipe.method == "refcontrol":                                       # E10: the reference at 0.6 MP beside a 0.9 MP pose map
            g[str(nid)] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": img, "upscale_method": "lanczos", "megapixels": 0.6, "resolution_steps": 16}}
            img = [str(nid), 0]
            nid += 1
        g[str(nid)] = {"class_type": "VAEEncode", "inputs": {"pixels": img, "vae": ["3", 0]}}
        lat = [str(nid), 0]
        nid += 1
        g[str(nid)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": cond, "latent": lat}}
        cond = [str(nid), 0]
        nid += 1
    g["9"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    g["10"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": int(seed), "steps": steps, "cfg": cfg,
                                                  "sampler_name": spec.sampling.sampler, "scheduler": spec.sampling.scheduler,
                                                  "positive": cond, "negative": ["6", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": out_prefix}}
    summary = {"model_id": mid, "method": recipe.method, "stage_id": recipe.stage_id, "camera_id": recipe.camera_id, "image1": key, "steps": steps,
               "cfg": cfg, "seed": int(seed), "width": w, "height": h, "refs": len(refs), "refs_dropped": max(0, len(recipe.refs) - len(refs))}
    return Compiled(graph=g, output_node="99", summary=summary, serialized_prompt=prompt)


# ---- P18 (D84): image → mesh from the frozen Pixal3D graph --------------------------------------------------------------------------------
_MESH_GRAPH: dict[str, Any] | None = None


def mesh_graph_fixture() -> dict[str, Any]:
    """The template's Pixal3D branch as scripts/make_mesh_graph.py froze it: `graph` (blank loader names) and `roles` (node id → role)."""
    global _MESH_GRAPH
    if _MESH_GRAPH is None:
        _MESH_GRAPH = json.loads((Path(__file__).parent / "pixal3d_graph.json").read_text(encoding="utf-8"))
    return _MESH_GRAPH


def build_mesh(recipe: ImageToMesh, roster: Roster, seed: int, out_prefix: str, image_name: str) -> Compiled:
    """The frozen graph with the roster's file names in its loaders, the source image, one seed in every sampler, the face count, the
    upsample resolution and the output prefix; a `RenderMesh` view of the final mesh saved beside the GLB for the thumbnail."""
    spec = registry.get(recipe.model_id)
    if spec is None or not spec.recipes.mesh or spec.graph != "pixal3d":
        raise CompileError(f"{recipe.model_id!r} is not an image → mesh model")
    fx = mesh_graph_fixture()
    g: dict[str, Any] = copy.deepcopy(fx["graph"])
    roles: dict[str, str] = fx["roles"]
    by_role = {r: k for k, r in roles.items()}
    files = {"model": roster.require(spec.id)[1]}
    for role in ("shape_vae", "texture_vae", "dino", "moge", "matte"):
        rid = spec.roles.extra.get(role)
        if not rid:
            raise CompileError(f"the {spec.label} spec names no {role}")
        files[role] = roster.require(rid)[1]
    for k, role in roles.items():
        node = g[k]
        if role == "model":
            node["inputs"]["unet_name"] = files["model"]
        elif role in ("shape_vae", "texture_vae"):
            node["inputs"]["vae_name"] = files[role]
        elif role == "dino":
            node["inputs"]["clip_name"] = files["dino"]
        elif role == "moge":
            node["inputs"]["model_name"] = files["moge"]
        elif role == "matte":
            node["inputs"]["bg_removal_name"] = files["matte"]
        elif role == "image":
            node["inputs"]["image"] = image_name
        elif role == "sampler":
            node["inputs"]["seed"] = int(seed)
        elif role == "decimate":
            node["inputs"]["target_face_count"] = int(recipe.faces)
        elif role == "upsample":
            node["inputs"]["target_resolution"] = int(recipe.resolution)
        elif role == "save":
            node["inputs"]["filename_prefix"] = out_prefix
    final = by_role.get("final_mesh")
    if final:
        g["900"] = {"class_type": "RenderMesh", "inputs": {"mesh": [final, 0], "mode": "auto", "width": 512, "height": 512, "background": "#2a2a2e"}}
        g["901"] = {"class_type": "SaveImage", "inputs": {"images": ["900", 0], "filename_prefix": out_prefix + "_view"}}
    summary = {"model_id": spec.id, "resolution": recipe.resolution, "faces": recipe.faces, "seed": int(seed), "nodes": len(g), "template": fx.get("source")}
    return Compiled(graph=g, output_node=by_role.get("save", "322"), summary=summary, serialized_prompt="")


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
        if spec is None or spec.graph not in registry.FLUX_GRAPHS or not spec.recipes.i2i:      # D89: the creative families refine, not tile
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


def build_keypoints(recipe: Keypoints, roster: Roster, image_name: str) -> Compiled:
    """CA1b (D104): E10's scorer as a job — RT-DETR boxes the people, SDPose wholebody reads each one; PreviewAny returns the keypoints as
    text (the finisher parses them; nothing is saved to the Catalogue)."""
    spec = registry.get(recipe.model_id)
    if spec is None or not spec.recipes.keypoints:
        raise CompileError(f"{recipe.model_id!r} does not read body keypoints")
    _, ckpt = roster.require(spec.id)
    _, det = roster.require(spec.roles.extra["detector"])
    g: dict[str, Any] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": det, "weight_dtype": "default"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "4": {"class_type": "RTDETR_detect", "inputs": {"model": ["2", 0], "image": ["3", 0], "threshold": 0.4, "class_name": "person", "max_detections": 6}},
        "5": {"class_type": "SDPoseKeypointExtractor", "inputs": {"model": ["1", 0], "vae": ["1", 2], "image": ["3", 0], "batch_size": 1, "bboxes": ["4", 0]}},
        "6": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}},
    }
    return Compiled(graph=g, output_node="6", summary={"model_id": spec.id, "detector": spec.roles.extra["detector"], "asset_id": recipe.asset_id})


def build_matte_sequence(recipe: MatteSequence, roster: Roster, video_name: str, out_prefix: str) -> Compiled:
    """D111 (PS5d): SAM 3 by text on every frame of a character layer (E22's per-frame detection follows a walking figure), the masks
    saved as images, one per frame."""
    sid = recipe.model_id
    g: dict[str, Any] = {"2": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
                         "3": {"class_type": "GetVideoComponents", "inputs": {"video": ["2", 0]}}}
    if recipe.mode == "subject":                                      # `open`: BiRefNet's subject matte on every frame
        _, name = roster.require(sid)
        g["1"] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": name}}
        g["5"] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["3", 0]}}
    else:
        _, ckpt = roster.require(sid)
        g["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
        g["4"] = {"class_type": "CLIPTextEncode", "inputs": {"text": recipe.text.strip() or "person", "clip": ["1", 1]}}
        g["5"] = {"class_type": "SAM3_Detect", "inputs": {"model": ["1", 0], "image": ["3", 0], "conditioning": ["4", 0], "threshold": recipe.threshold,
                                                          "refine_iterations": 2, "individual_masks": False}}
    g["7"] = {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}}
    g["99"] = {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": out_prefix}}
    return Compiled(graph=g, output_node="99", summary={"model_id": sid, "mode": recipe.mode, "text": recipe.text, "threshold": recipe.threshold}, serialized_prompt=recipe.text)


def compile_recipe(recipe: T2I | I2I | Inpaint | Upscale | I2V | Reangle | StageShot | ImageToMesh | Keypoints | MatteSequence, roster: Roster, object_info: dict, seed: int, out_prefix: str,
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
        c = build_i2v(recipe, roster, seed, out_prefix, i["start"], i.get("end"), i.get("beats"), i.get("guide"), i.get("lead"), i.get("audio"), i.get("carry"))
    elif isinstance(recipe, Reangle):
        i = inputs or {}
        if "image" not in i:
            raise CompileError("reangle needs the uploaded source (pipeline.prepare_reangle)")
        c = build_reangle(recipe, roster, seed, out_prefix, i["image"], int(i.get("w", 0)), int(i.get("h", 0)), variant)
    elif isinstance(recipe, StageShot):
        i = inputs or {}
        if not (i.get("clay") or i.get("pose")):
            raise CompileError("stage_shot needs the uploaded passes (pipeline.prepare_stage_shot)")
        c = build_stage_shot(recipe, roster, seed, out_prefix, i, ref_files, variant)
    elif isinstance(recipe, ImageToMesh):
        i = inputs or {}
        if "image" not in i:
            raise CompileError("image_to_mesh needs the uploaded source (pipeline.prepare_mesh)")
        c = build_mesh(recipe, roster, seed, out_prefix, i["image"])
    elif isinstance(recipe, Keypoints):
        i = inputs or {}
        if "image" not in i:
            raise CompileError("keypoints needs the uploaded image (pipeline.prepare_keypoints)")
        c = build_keypoints(recipe, roster, i["image"])
    elif isinstance(recipe, MatteSequence):
        i = inputs or {}
        if "video" not in i:
            raise CompileError("matte_sequence needs the uploaded frames (pipeline.prepare_matte)")
        c = build_matte_sequence(recipe, roster, i["video"], out_prefix)
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
    if (isinstance(recipe, Inpaint) and recipe.mode == "quick_remove") or isinstance(recipe, (Render, AssembleFinal)):
        return 0.0                                                    # R3 (D62) / P17 / D111: CPU only, the engine is never started
    if isinstance(recipe, TrainLora):                                 # LT2: E16's measured peak of the base (the engine is stopped for it)
        spec = registry.get(recipe.model_id)
        return float(spec.recipes.train.vram_gb) if spec and spec.recipes.train else 14.0
    if isinstance(recipe, TTS):                                       # CN2: E20's peak of the cloning tier; the draft tier never touches the card
        from ..voices import RATES
        return float(RATES[recipe.tier]["vram_gb"])
    if isinstance(recipe, Upscale) and recipe.refine:
        return _vram(recipe.refine_model_id)
    if isinstance(recipe, Inpaint):
        return _vram(inpaint_model_id(recipe, variant))               # C10: Fill Hero runs dev, whatever the panel named
    if isinstance(recipe, Reangle):
        return _vram(reangle_model_id(recipe, variant))
    if isinstance(recipe, StageShot):
        return _vram(stage_model_id(recipe, variant))
    return _vram(recipe.model_id)


def recipe_weights(recipe: T2I | I2I | Inpaint | Upscale | Segment | I2V | Reangle | Render | StageShot | ImageToMesh, variant: str = "full") -> list[str]:
    """Every roster id a recipe would load — the open-variant gate (C3, D26) and the admission estimate read this."""
    if isinstance(recipe, TrainLora):
        return [recipe.model_id]                                      # LT2: the base's transformer (its encoder comes from HF_HOME, its VAE from the hub)
    if isinstance(recipe, TTS):
        return []                                                     # CN2: the TTS models live in HF_HOME, not the roster
    if isinstance(recipe, (ImageToMesh, Keypoints, MatteSequence)):
        spec = registry.get(recipe.model_id)
        return spec.weights() if spec else [recipe.model_id]           # P18: the transformer, both VAEs, DINOv3, MoGe, BiRefNet; CA1b: SDPose + RT-DETR
    if isinstance(recipe, I2V):
        spec = registry.get(recipe.model_id)
        ids = spec.weights() if spec else [recipe.model_id]
        if recipe.guide and spec is not None and spec.recipes.guide_lora:
            ids = [*ids, spec.recipes.guide_lora]                      # ST4: the IC-LoRA rides only on a guided clip
        return ids
    if (isinstance(recipe, Inpaint) and recipe.mode == "quick_remove") or isinstance(recipe, (Render, AssembleFinal)):
        return []                                                     # R3 (D62) / P17 / D111: no weights at all

    te_over = getattr(recipe, "te_id", None)

    def model_ids(mid: str, turbo: bool) -> list[str]:
        spec = registry.get(mid)
        return spec.weights(te_over, turbo) if spec else [mid]

    ids: list[str] = []
    if isinstance(recipe, T2I):
        ids += model_ids(recipe.model_id, bool(recipe.turbo))
    elif isinstance(recipe, Reangle):
        ids += model_ids(reangle_model_id(recipe, variant), False)     # the spec's extras carry the Lightning and angles LoRAs
    elif isinstance(recipe, StageShot):
        mid = stage_model_id(recipe, variant)
        ids += model_ids(mid, False)
        spec = registry.get(mid)
        if spec is not None and spec.recipes.stage_lora:
            ids.append(spec.recipes.stage_lora)                        # ST3: the pose LoRA rides only on the Stage graph
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
    ids += [l.model_id for l in getattr(recipe, "loras", []) if l.model_id in ROSTER_BY_ID]   # LT1: `file:` and trained ids are not roster weights
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
    seconds = base * (px / (960 * 544)) * (ep["steps"] / max(1, base_steps)) + 4 * min(len(recipe.refs), spec.inputs.refs_max if spec else len(recipe.refs))
    return {"seconds": round(seconds, 1), "source": "baseline (spikes)"}
