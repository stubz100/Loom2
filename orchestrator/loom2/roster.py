"""Weights roster (04 §1b, D1, D30): the authored catalogue of every weight loom2 may use, resolved against the
ComfyUI-layout models root and the mounted trees, with health from the fetch ledger (`roster.index.json`).

Recipes reference `RosterEntry.id`; the compiler resolves an id to the `(folder, filename)` pair a loader node
takes. File identity is by basename inside a ComfyUI folder key, never a hand-typed path (E8 lesson).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Folder = Literal["diffusion_models", "text_encoders", "vae", "loras", "clip_vision", "upscale_models", "audio_encoders",
                 "controlnet", "checkpoints", "sam3", "background_removal", "embeddings", "geometry_estimation"]
Health = Literal["present", "verified", "missing", "retired"]


class RosterEntry(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    id: str
    name: str                                  # basename as ComfyUI lists it inside `folder`
    folder: Folder
    family: str                                # flux2 | klein | wan22 | ltx23 | tools
    role: str                                  # transformer | text_encoder | vae | lora | upscaler | tool
    repo: str | None = None
    file: str | None = None                    # path inside the repo (fetch source)
    license: str = "unknown"
    variants: list[str] = Field(default_factory=lambda: ["full"])
    approx_gb: float | None = None
    retired: str | None = None                 # D30: struck by a spike; deleted from disk, re-fetchable
    note: str | None = None
    base: str | None = None                    # LT1 (18 §3b): a LoRA's base — the model base it fits (klein-9b, flux2, wan22 …); the family when absent
    preset: str | None = None                  # LT1: the mechanism that applies this LoRA (turbo | lightning | angles | stage | guide) — never a slot


# P18 (D84): weights loom2 never lists or suggests, by a name fragment, with the licence reason the Models suite shows.
IGNORED_UNLISTED: list[tuple[str, str]] = [
    ("hunyuan3d", "Hunyuan3D's licence excludes the EU (D17); loom2 makes props with Pixal3D (D79)"),
    ("hunyuan_3d", "Hunyuan3D's licence excludes the EU (D17); loom2 makes props with Pixal3D (D79)"),
]


def ignore_reason(name: str) -> str | None:
    low = name.lower()
    return next((why for frag, why in IGNORED_UNLISTED if frag in low), None)


# The catalogue. Order: family, then role. `open` variant = Apache/MIT only (D26).
ROSTER: list[RosterEntry] = [
    # ---- tools (M5 Edit AI: upscalers, segmentation) ----
    RosterEntry(id="birefnet", name="BiRefNet-general.safetensors", folder="background_removal", family="tools", role="tool",
                repo="ZhengPeng7/BiRefNet", file="model.safetensors", license="mit", variants=["full", "open"], approx_gb=0.89,
                note="subject matte for AI Select · Subject (core LoadBackgroundRemovalModel / RemoveBackground, 1024² input)"),
    # CA1b (D104): body keypoints for fitting a figure to its character's animation reference (E10's scorer, now a product path)
    RosterEntry(id="sdpose-wholebody", name="sdpose_wholebody_fp16.safetensors", folder="checkpoints", family="tools", role="tool",
                repo="Comfy-Org/SDPose", file="checkpoints/sdpose_wholebody_fp16.safetensors", license="mit", variants=["full", "open"], approx_gb=1.92,
                note="SDPose wholebody (core SDPoseKeypointExtractor): body, hands, feet and face keypoints of each boxed person"),
    RosterEntry(id="rtdetr-v4", name="rt_detr_v4-x-hgnet_fp16.safetensors", folder="diffusion_models", family="tools", role="tool",
                repo="Comfy-Org/SDPose", file="diffusion_models/rt_detr_v4-x-hgnet_fp16.safetensors", license="mit (Comfy-Org repack; RT-DETRv4 apache-2.0)",
                variants=["full", "open"], approx_gb=0.12, note="RT-DETR v4 person boxes for SDPose (core RTDETR_detect)"),
    RosterEntry(id="sam3", name="sam3.pt", folder="sam3", family="tools", role="tool",
                repo="facebook/sam3", file="sam3.pt", license="sam-license (gated)", variants=["full"], approx_gb=3.45,
                note="SAM 3 detector + its text encoder in one checkpoint; loads through CheckpointLoaderSimple (the sam3 folder is mounted as a checkpoints path)"),
    RosterEntry(id="realesrgan-x2", name="RealESRGAN_x2.pth", folder="upscale_models", family="tools", role="upscaler",
                repo="ai-forever/Real-ESRGAN", file="RealESRGAN_x2.pth", license="bsd-3-clause", variants=["full", "open"], approx_gb=0.07,
                note="Real-ESRGAN 2× (spandrel loader); cheap detail-preserving upscale (10 §4)"),
    RosterEntry(id="realesrgan-x4", name="RealESRGAN_x4.pth", folder="upscale_models", family="tools", role="upscaler",
                repo="ai-forever/Real-ESRGAN", file="RealESRGAN_x4.pth", license="bsd-3-clause", variants=["full", "open"], approx_gb=0.07,
                note="Real-ESRGAN 4×"),
    # ---- FLUX.2 dev (Hero / Generate default, D21/D29) ----
    RosterEntry(id="flux2-dev-fp8mixed", name="flux2_dev_fp8mixed.safetensors", folder="diffusion_models", family="flux2", role="transformer",
                repo="Comfy-Org/flux2-dev", file="split_files/diffusion_models/flux2_dev_fp8mixed.safetensors", license="flux-nc", approx_gb=33.0),
    RosterEntry(id="mistral3-small-flux2-fp8", name="mistral_3_small_flux2_fp8.safetensors", folder="text_encoders", family="flux2", role="text_encoder",
                repo="Comfy-Org/flux2-dev", file="split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors", license="apache-2.0 (Mistral)", approx_gb=16.8),
    RosterEntry(id="flux2-vae", name="flux2-vae.safetensors", folder="vae", family="flux2", role="vae",
                repo="Comfy-Org/flux2-dev", file="split_files/vae/flux2-vae.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=0.31),
    RosterEntry(id="flux2-small-decoder", name="flux2-small-decoder.safetensors", folder="vae", family="flux2", role="vae",
                license="apache-2.0", variants=["full", "open"], approx_gb=0.23, note="fast preview decoder"),
    RosterEntry(id="flux2-turbo-lora", name="Flux2TurboComfyv2.safetensors", folder="loras", family="flux2", role="lora",
                license="flux-nc", approx_gb=2.6, note="8-step Turbo LoRA for dev (E0: ≈ 40 s per 960×544)", base="flux2", preset="turbo"),
    # ---- FLUX.2 Klein (Edit workhorse, Iterate/Quality tiers, D6/D7) ----
    RosterEntry(id="klein-4b", name="flux-2-klein-4b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-4B", file="split_files/diffusion_models/flux-2-klein-4b.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=7.2),
    RosterEntry(id="klein-base-4b", name="flux-2-klein-base-4b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-4B", file="split_files/diffusion_models/flux-2-klein-base-4b.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=7.2),
    RosterEntry(id="qwen3-4b", name="qwen_3_4b.safetensors", folder="text_encoders", family="klein", role="text_encoder",
                repo="Comfy-Org/flux2-klein-4B", file="split_files/text_encoders/qwen_3_4b.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=7.5),
    # 2026-10-17 (ledger_verify): the 9B transformers live in BFL's gated repos (Comfy-Org/flux2-klein-9B holds only the encoder and VAE); the
    #   files on disk match those repos' LFS sha256, as the Lightning (a subfolder) and the angles LoRA (the repo's 镜头转换.safetensors, renamed) do
    RosterEntry(id="klein-9b", name="flux-2-klein-9b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="black-forest-labs/FLUX.2-klein-9B", file="flux-2-klein-9b.safetensors", license="flux-nc", approx_gb=16.9),
    RosterEntry(id="klein-base-9b", name="flux-2-klein-base-9b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="black-forest-labs/FLUX.2-klein-base-9B", file="flux-2-klein-base-9b.safetensors", license="flux-nc", approx_gb=16.9, note="refine path only (E8)"),
    RosterEntry(id="klein-9b-kv", name="flux-2-klein-9b-kv.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="black-forest-labs/FLUX.2-klein-9b-kv", file="flux-2-klein-9b-kv.safetensors", license="flux-nc", approx_gb=16.9, note="multi-ref KV cache; unbenchmarked"),
    RosterEntry(id="qwen3-8b-fp8mixed", name="qwen_3_8b_fp8mixed.safetensors", folder="text_encoders", family="klein", role="text_encoder",
                repo="Comfy-Org/flux2-klein-9B", file="split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors", license="apache-2.0", approx_gb=8.1,
                note="alternate 9B encoder since D31 (2026-10-07): with it the 9B transformer streams on a cold engine (tiled refine 1157 s vs 279 s)"),
    # Klein 9B text encoder (D31, 2026-10-07): the fp8 encoder (8.3 GB resident) and the fp8-cast 9B transformer (8.7 GB) do not fit 16 GB
    # together, so DynamicVRAM streams the sampler; unsloth's llama.cpp quantization of the same Qwen3-8B, loaded through ComfyUI-GGUF's
    # CLIPLoaderGGUF, keeps the pair resident. Q4_K_M is the default; Q4_K_S / Q3_K_M measured identical in speed and were deleted (D30).
    # 9B family only — the 4B models have a different hidden size.
    RosterEntry(id="qwen3-8b-q4km", name="Qwen3-8B-Q4_K_M.gguf", folder="text_encoders", family="klein", role="text_encoder",
                repo="unsloth/Qwen3-8B-GGUF", file="Qwen3-8B-Q4_K_M.gguf", license="apache-2.0", approx_gb=5.03,
                note="default Klein 9B encoder (D31): 6.8 GB resident, cold tiled refine 279 s instead of 1157 s; renders match fp8 by eye"),
    RosterEntry(id="qwen3-8b-q4ks", name="Qwen3-8B-Q4_K_S.gguf", folder="text_encoders", family="klein", role="text_encoder",
                repo="unsloth/Qwen3-8B-GGUF", file="Qwen3-8B-Q4_K_S.gguf", license="apache-2.0", approx_gb=4.80, retired="D31 2026-10-07: same speed as Q4_K_M, no reason to keep both"),
    RosterEntry(id="qwen3-8b-q3km", name="Qwen3-8B-Q3_K_M.gguf", folder="text_encoders", family="klein", role="text_encoder",
                repo="unsloth/Qwen3-8B-GGUF", file="Qwen3-8B-Q3_K_M.gguf", license="apache-2.0", approx_gb=4.12, retired="D31 2026-10-07: same speed as Q4_K_M, a little looser on pose"),
    # ---- Wan 2.2 I2V-A14B (primary i2v, D8) ----
    RosterEntry(id="wan22-i2v-high-q5", name="Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf", folder="diffusion_models", family="wan22", role="transformer",
                repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="HighNoise/Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf", license="apache-2.0", variants=["full", "open"], approx_gb=10.1, retired="E4c 2026-10-05: fp8 scaled experts are 1.8× faster at sampling (D30)"),
    RosterEntry(id="wan22-i2v-low-q5", name="Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf", folder="diffusion_models", family="wan22", role="transformer",
                repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="LowNoise/Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf", license="apache-2.0", variants=["full", "open"], approx_gb=10.1, retired="E4c 2026-10-05: fp8 scaled experts are 1.8× faster at sampling (D30)"),
    RosterEntry(id="wan22-i2v-high-fp8", name="wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", folder="diffusion_models", family="wan22", role="transformer",
                repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=13.3, note="E4c 2026-10-05: 236 s per 81 f clip vs 322 s GGUF; D8 recipe"),
    RosterEntry(id="wan22-i2v-low-fp8", name="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", folder="diffusion_models", family="wan22", role="transformer",
                repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=13.3, note="E4c 2026-10-05: 236 s per 81 f clip vs 322 s GGUF; D8 recipe"),
    # ---- wave CN (D87, 19 §2): E18 lip-sync and E19 pose-driven shots — Apache-2.0 repacks, both variants ----
    RosterEntry(id="wan22-s2v-fp8", name="wan2.2_s2v_14B_fp8_scaled.safetensors", folder="diffusion_models", family="wan22", role="transformer",
                repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=15.3, note="Wan2.2 S2V-14B: a reference image + audio → a talking clip (E18)"),
    RosterEntry(id="wav2vec2-large-english", name="wav2vec2_large_english_fp16.safetensors", folder="audio_encoders", family="wan22", role="audio_encoder",
                repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/audio_encoders/wav2vec2_large_english_fp16.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=0.6, note="the S2V audio encoder (core AudioEncoderLoader)"),
    RosterEntry(id="wan22-animate-fp8", name="Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", folder="diffusion_models", family="wan22", role="transformer",
                repo="Kijai/WanVideo_comfy_fp8_scaled", file="Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", license="apache-2.0 (Kijai repack)",
                variants=["full", "open"], approx_gb=17.1, note="Wan2.2 Animate-14B: a reference image + a pose video → the character performing it (E19, Move)"),
    RosterEntry(id="clip-vision-h", name="clip_vision_h.safetensors", folder="clip_vision", family="wan22", role="clip_vision",
                repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/clip_vision/clip_vision_h.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=1.2, note="the CLIP vision Animate conditions the reference on"),
    RosterEntry(id="lightx2v-i2v-4step", name="lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", folder="loras", family="wan22", role="lora",
                repo="Kijai/WanVideo_comfy", file="Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", license="apache-2.0 (lightx2v; Kijai repack)",
                variants=["full", "open"], approx_gb=0.7, base="wan22", preset="lightning", note="the 4-step distillation LoRA the Animate template samples with"),
    RosterEntry(id="umt5-xxl-fp8", name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", folder="text_encoders", family="wan22", role="text_encoder",
                repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=6.3),
    RosterEntry(id="wan21-vae", name="wan_2.1_vae.safetensors", folder="vae", family="wan22", role="vae",
                repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/vae/wan_2.1_vae.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=0.24),
    RosterEntry(id="wan22-lightning-high", name="Wan2.2-I2V-A14B-Lightning-4steps-high.safetensors", folder="loras", family="wan22", role="lora",
                repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=1.1,
                base="wan22", preset="lightning"),
    RosterEntry(id="wan22-lightning-low", name="Wan2.2-I2V-A14B-Lightning-4steps-low.safetensors", folder="loras", family="wan22", role="lora",
                repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=1.1,
                base="wan22", preset="lightning"),
    # ---- LTX-2.3 distilled (secondary i2v, D9, fp8 only after E5b) ----
    RosterEntry(id="ltx23-distilled-fp8", name="ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors", folder="diffusion_models", family="ltx23", role="transformer",
                repo="Kijai/LTX2.3_comfy", file="diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors", license="ltx-2.x community", approx_gb=23.5),
    RosterEntry(id="gemma3-12b-fp8", name="gemma_3_12B_it_fp8_scaled.safetensors", folder="text_encoders", family="ltx23", role="text_encoder",
                repo="Comfy-Org/ltx-2", file="split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors", license="gemma", approx_gb=12.3),
    RosterEntry(id="ltx23-text-projection", name="ltx-2.3_text_projection_bf16.safetensors", folder="text_encoders", family="ltx23", role="text_encoder",
                repo="Kijai/LTX2.3_comfy", file="text_encoders/ltx-2.3_text_projection_bf16.safetensors", license="ltx-2.x community", approx_gb=2.2),
    RosterEntry(id="ltx23-video-vae", name="ltx-2.3_video_vae_bf16.safetensors", folder="vae", family="ltx23", role="vae",
                repo="Kijai/LTX2.3_comfy", file="vae/LTX23_video_vae_bf16.safetensors", license="ltx-2.x community", approx_gb=1.35),
    RosterEntry(id="ltx23-audio-vae", name="ltx-2.3_audio_vae_bf16.safetensors", folder="vae", family="ltx23", role="vae",
                repo="Kijai/LTX2.3_comfy", file="vae/LTX23_audio_vae_bf16.safetensors", license="ltx-2.x community", approx_gb=0.34, note="core 0.38 needs it on LTXVEmptyLatentAudio"),
    RosterEntry(id="ltx23-upscaler-x2", name="ltx-2.3-spatial-upscaler-x2-1.1.safetensors", folder="upscale_models", family="ltx23", role="upscaler",
                repo="Lightricks/LTX-2.3", file="ltx-2.3-spatial-upscaler-x2-1.1.safetensors", license="ltx-2.x community", approx_gb=0.93),
    # ---- Qwen-Image-Edit 2509 (P14 / D82): E12's angles method — the fp8 transformer, its Qwen2.5-VL encoder and VAE, lightx2v's Lightning
    #      and dx8152's Multiple-angles LoRA; all Apache-2.0, so `full` and `open` ----
    RosterEntry(id="qwen-edit-2509-fp8", name="qwen_image_edit_2509_fp8_e4m3fn.safetensors", folder="diffusion_models", family="qwen_image", role="transformer",
                repo="Comfy-Org/Qwen-Image-Edit_ComfyUI", file="split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=20.4, note="E12 method A (D77): a new viewpoint with the Multiple-angles LoRA; 31.6 s warm, 27 s cold from F:"),
    RosterEntry(id="qwen25vl-7b-fp8", name="qwen_2.5_vl_7b_fp8_scaled.safetensors", folder="text_encoders", family="qwen_image", role="text_encoder",
                repo="Comfy-Org/Qwen-Image_ComfyUI", file="split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=9.4),
    RosterEntry(id="qwen-image-vae", name="qwen_image_vae.safetensors", folder="vae", family="qwen_image", role="vae",
                repo="Comfy-Org/Qwen-Image_ComfyUI", file="split_files/vae/qwen_image_vae.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=0.25),
    RosterEntry(id="qwen-edit-2509-lightning-4", name="Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", folder="loras", family="qwen_image", role="lora",
                repo="lightx2v/Qwen-Image-Lightning", file="Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=0.85, base="qwen_image", preset="lightning"),
    RosterEntry(id="qwen-edit-2509-angles", name="Qwen-Edit-2509-Multiple-angles.safetensors", folder="loras", family="qwen_image", role="lora",
                repo="dx8152/Qwen-Edit-2509-Multiple-angles", file="镜头转换.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=0.24, note="camera instructions in Chinese (将镜头向左旋转45度 …); used with the Lightning LoRA", base="qwen_image", preset="angles"),
    # ---- Image → mesh props (P18, D79 / D84): ComfyUI's Pixal3D template — Pixal3D int8, the two TRELLIS.2 VAEs, MoGe (MIT) and DINOv3 ----
    RosterEntry(id="pixal3d-int8", name="pixal3d_int8_convrot.safetensors", folder="diffusion_models", family="pixal3d", role="transformer",
                repo="Comfy-Org/Pixal3D", file="diffusion_models/pixal3d_int8_convrot.safetensors", license="mit", variants=["full"], approx_gb=5.6,
                note="E14 (D79): props from a cut-out, IoU 0.90–0.99, 46–50k triangles, warm 243 s / cold 361 s at 1024; full only while DINOv3 is (D17)"),
    RosterEntry(id="trellis2-shape-vae", name="trellis_2_shape_vae_bf16.safetensors", folder="vae", family="pixal3d", role="vae",
                repo="Comfy-Org/Pixal3D", file="vae/trellis_2_shape_vae_bf16.safetensors", license="mit", variants=["full", "open"], approx_gb=1.1),
    RosterEntry(id="trellis2-texture-vae", name="trellis_2_texture_vae_bf16.safetensors", folder="vae", family="pixal3d", role="vae",
                repo="Comfy-Org/Pixal3D", file="vae/trellis_2_texture_vae_bf16.safetensors", license="mit", variants=["full", "open"], approx_gb=0.95),
    RosterEntry(id="dinov3-l", name="dino_v3_L_naf_fp32.safetensors", folder="clip_vision", family="pixal3d", role="text_encoder",
                repo="Comfy-Org/Pixal3D", file="clip_vision/dino_v3_L_naf_fp32.safetensors", license="dinov3 (Meta custom)", variants=["full"], approx_gb=1.2,
                note="the image encoder of Pixal3D and TRELLIS.2; its licence keeps P18 full-only until reviewed (D17 / D26)"),
    RosterEntry(id="moge2-vitl", name="moge_2_vitl_normal_fp16.safetensors", folder="geometry_estimation", family="pixal3d", role="tool",
                repo="Comfy-Org/MoGe", file="geometry_estimation/moge_2_vitl_normal_fp16.safetensors", license="mit", variants=["full", "open"], approx_gb=0.66,
                note="the field of view the template estimates for Pixal3D's conditioning"),
    # ---- Stage → clip (P13 ST4, D76): LTX-2.3's IC-LoRA Union — the depth (or pose) sequence as the guide at frame 0 ----
    RosterEntry(id="ltx23-ic-lora-union", name="ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors", folder="loras", family="ltx23", role="lora",
                repo="Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control", file="ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors", license="ltx-2.x community",
                approx_gb=0.65, note="E11 (D76): GetICLoRAParameters + LTXVAddGuide on the rendered depth sequence; 1.22× plain LTX, the pose followed 4/5", base="ltx23", preset="guide"),
    # ---- Stage → image (P13 ST3, D78): E10's exact-pose method — RefControl's pose LoRA for Klein base 9B (apache-2.0) ----
    RosterEntry(id="refcontrol-v2-poses", name="refcontrol_v2_poses.safetensors", folder="loras", family="klein", role="lora",
                repo="thedeoxen/refcontrol-FLUX.2-klein-9B-reference-pose-lora", file="refcontrol_v2_poses.safetensors", license="apache-2.0",
                variants=["full"], approx_gb=0.17, note="E10 (D78): 'apply pose from image 1 with reference from image 2', strength 0.9 — PCK 0.86 at ≈ 74 s", base="klein-9b", preset="stage"),
    # ---- wave CR (D89, .docs/creative_image/04 §3): creative t2i / i2i. Krea 2's VAE is `qwen-image-vae` and Z-Image's encoder `qwen3-4b`
    #      (the same files, sha256-checked 2026-10-15); the FLUX.1 ae serves Z-Image and Chroma. Krea 2's licence: commercial use under
    #      USD 1 M revenue, content filters are the deployer's duty — the author's, recorded here (no filter in loom2, D89) ----
    RosterEntry(id="krea2-turbo-fp8", name="krea2_turbo_fp8_scaled.safetensors", folder="diffusion_models", family="krea2", role="transformer",
                repo="Comfy-Org/Krea-2", file="diffusion_models/krea2_turbo_fp8_scaled.safetensors", approx_gb=13.14,
                license="krea-2-community (commercial use under USD 1 M revenue; content filters are the deployer's duty — the author's, D89)"),
    RosterEntry(id="krea2-raw-fp8", name="krea2_raw_fp8_scaled.safetensors", folder="diffusion_models", family="krea2", role="transformer",
                repo="Comfy-Org/Krea-2", file="diffusion_models/krea2_raw_fp8_scaled.safetensors", approx_gb=13.14,
                license="krea-2-community (commercial use under USD 1 M revenue; content filters are the deployer's duty — the author's, D89)"),
    RosterEntry(id="qwen3vl-4b-fp8", name="qwen3vl_4b_fp8_scaled.safetensors", folder="text_encoders", family="krea2", role="text_encoder",
                repo="Comfy-Org/Krea-2", file="text_encoders/qwen3vl_4b_fp8_scaled.safetensors", license="apache-2.0 (Qwen3-VL-4B)", variants=["full", "open"], approx_gb=5.24),
    *[RosterEntry(id=f"krea2-lora-{s.replace('_', '-')}", name=f"krea2_{s}.safetensors", folder="loras", family="krea2", role="lora",
                  repo="Comfy-Org/Krea-2", file=f"loras/krea2_{s}.safetensors", license="krea-2-community", approx_gb=0.47, note=f"Krea's {label} style LoRA (strength 0.8–1.0)")
      for s, label in (("darkbrush", "dark brush"), ("dotmatrix", "dot-matrix"), ("kidsdrawing", "kid's drawing"), ("neondrip", "neon drip"),
                       ("rainywindow", "rainy window"), ("retroanime", "retro anime"), ("softwatercolor", "soft watercolour"), ("sunsetblur", "sunset blur"),
                       ("vintagetarot", "vintage tarot"))],
    RosterEntry(id="krea2-style-reference", name="krea2_style_reference.safetensors", folder="loras", family="krea2", role="lora",
                repo="Comfy-Org/Krea-2", file="loras/krea2_style_reference.safetensors", license="krea-2-community", approx_gb=0.46, preset="style_reference",
                note="Krea 2's style reference (1–2 style images through TextEncodeQwenImageEditPlus); wired in CR+, not a slot"),
    RosterEntry(id="zimage-bf16", name="z_image_bf16.safetensors", folder="diffusion_models", family="zimage", role="transformer",
                repo="Comfy-Org/z_image", file="split_files/diffusion_models/z_image_bf16.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=12.31,
                note="Z-Image base (Tongyi-MAI): the undistilled checkpoint — real CFG, negatives, high seed diversity"),
    RosterEntry(id="flux1-ae", name="ae.safetensors", folder="vae", family="zimage", role="vae",
                repo="Comfy-Org/z_image_turbo", file="split_files/vae/ae.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=0.34,
                note="the FLUX.1 VAE (16 channels) — Z-Image and Chroma1-HD"),
    RosterEntry(id="chroma1-hd-fp8mixed", name="Chroma1-HD-fp8mixed.safetensors", folder="diffusion_models", family="chroma", role="transformer",
                repo="Comfy-Org/Chroma1-HD_repackaged", file="split_files/diffusion_models/Chroma1-HD-fp8mixed.safetensors", license="apache-2.0",
                variants=["full", "open"], approx_gb=9.19, note="Chroma1-HD (lodestones): FLUX.1-schnell retrained on artistic and niche styles; uncensored"),
    RosterEntry(id="t5xxl-fp8-scaled", name="t5xxl_fp8_e4m3fn_scaled.safetensors", folder="text_encoders", family="chroma", role="text_encoder",
                repo="comfyanonymous/flux_text_encoders", file="t5xxl_fp8_e4m3fn_scaled.safetensors", license="apache-2.0 (T5)", variants=["full", "open"], approx_gb=5.16),
    RosterEntry(id="sd35-large-fp8", name="sd3.5_large_fp8_scaled.safetensors", folder="checkpoints", family="sd3", role="transformer",
                repo="Comfy-Org/stable-diffusion-3.5-fp8", file="sd3.5_large_fp8_scaled.safetensors", approx_gb=14.93,
                license="stabilityai-ai-community (commercial use under USD 1 M revenue; accepted by the author, D89)",
                note="SD 3.5 Large with CLIP-L, CLIP-G and T5 fp8 in one checkpoint (CheckpointLoaderSimple); Refine only"),
    # ---- D91 sample models: small t2i models for the style samples and the preset swatches (also in Generate) ----
    RosterEntry(id="lumina-image-2", name="lumina_2.safetensors", folder="checkpoints", family="lumina2", role="transformer",
                repo="Comfy-Org/Lumina_Image_2.0_Repackaged", file="all_in_one/lumina_2.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=10.62,
                note="Lumina Image 2.0 (Alpha-VLLM, 2.6B) with its Gemma 2B encoder and the FLUX.1 VAE in one checkpoint (CheckpointLoaderSimple)"),
    RosterEntry(id="sd35-medium-fp8", name="sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors", folder="checkpoints", family="sd3", role="transformer",
                repo="Comfy-Org/stable-diffusion-3.5-fp8", file="sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors", approx_gb=11.64,
                license="stabilityai-ai-community (commercial use under USD 1 M revenue; accepted by the author, D89 / D91)",
                note="SD 3.5 Medium (2.5B) with CLIP-L, CLIP-G and T5 fp8 in one checkpoint (CheckpointLoaderSimple)"),
    # ---- retired by spikes (D30: deleted, re-fetchable) ----
    RosterEntry(id="flux1-fill-dev", name="flux1-fill-dev.safetensors", folder="diffusion_models", family="flux1", role="transformer",
                repo="black-forest-labs/FLUX.1-Fill-dev", file="flux1-fill-dev.safetensors", license="flux-nc (gated)", approx_gb=22.2, retired="E8 2026-10-05"),
    RosterEntry(id="ltx23-distilled-q4", name="ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf", folder="diffusion_models", family="ltx23", role="transformer",
                repo="unsloth/LTX-2.3-GGUF", file="distilled-1.1/ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf", license="ltx-2.x community", approx_gb=13.2, retired="E5b 2026-10-05: 68–81 s/it vs 4.7 fp8"),
    RosterEntry(id="flux2-dev-q4", name="flux2-dev-Q4_K_M.gguf", folder="diffusion_models", family="flux2", role="transformer",
                repo="unsloth/FLUX.2-dev-GGUF", file="flux2-dev-Q4_K_M.gguf", license="flux-nc", approx_gb=18.6, retired="E0: 11× slower than fp8mixed"),
]

ROSTER_BY_ID: dict[str, RosterEntry] = {e.id: e for e in ROSTER}
assert len(ROSTER_BY_ID) == len(ROSTER), "duplicate roster ids"


class ResolvedModel(BaseModel):
    entry: RosterEntry
    path: str | None
    health: Health
    size: int | None = None
    sha256: str | None = None
    source_tree: str | None = None            # which root the file was found in


class Roster:
    """Scans the models root (and the mounted trees) for roster files; merges sha256 from the fetch ledger."""

    def __init__(self, models_root: Path, mounted: list[Path] | None = None, variant: str = "full") -> None:
        self.models_root = Path(models_root)
        self.mounted = [Path(m) for m in (mounted or [])]
        self.variant = variant
        self._found: dict[tuple[str, str], tuple[Path, Path]] = {}
        self.trained: dict[str, dict] = {}          # LT2 (18 §3a): the open project's trained LoRAs — id → {name (the loader's), base, label, trigger, steps, size}; loras.publish fills it
        self._ledger: dict[str, dict] = {}
        self.scanned_at: float | None = None

    def scan(self) -> "Roster":
        found: dict[tuple[str, str], tuple[Path, Path]] = {}
        for root in [self.models_root, *self.mounted]:
            if not root.is_dir():
                continue
            for folder_dir in root.iterdir():
                if not folder_dir.is_dir() or folder_dir.name.startswith(("_", ".")):
                    continue
                for p in folder_dir.rglob("*"):
                    if p.is_file() and p.suffix.lower() in (".safetensors", ".gguf", ".pt", ".pth", ".onnx", ".ckpt"):
                        found.setdefault((folder_dir.name, p.name), (p, root))
        ledger_path = self.models_root / "roster.index.json"
        ledger: dict[str, dict] = {}
        if ledger_path.is_file():
            try:
                for f in json.loads(ledger_path.read_text(encoding="utf-8")).get("files", []):
                    ledger[Path(f["path"]).name] = f
            except (OSError, ValueError):
                pass
        self._found, self._ledger = found, ledger      # D37: swapped whole, so a reader on the event loop never sees half a scan
        self.scanned_at = time.time()
        return self

    def resolve(self, model_id: str) -> ResolvedModel:
        entry = ROSTER_BY_ID.get(model_id)
        if entry is None:
            raise KeyError(f"unknown roster id: {model_id}")
        hit = self._found.get((entry.folder, entry.name))
        if entry.retired and hit is None:
            return ResolvedModel(entry=entry, path=None, health="retired")
        if hit is None:
            return ResolvedModel(entry=entry, path=None, health="missing")
        path, root = hit
        led = self._ledger.get(entry.name)
        size = path.stat().st_size
        return ResolvedModel(entry=entry, path=str(path), size=size, sha256=(led or {}).get("sha256"),
                             health="verified" if led and led.get("sha256") and led.get("size") == size else "present",
                             source_tree=str(root))

    def require(self, model_id: str) -> tuple[str, str]:
        """(folder, filename) for a loader node; raises if the file is not on disk."""
        r = self.resolve(model_id)
        if r.path is None:
            raise FileNotFoundError(f"weight '{model_id}' ({r.entry.name}) is {r.health}")
        return r.entry.folder, r.entry.name

    def listing(self, include_retired: bool = False) -> list[dict]:
        out = []
        for e in ROSTER:
            if e.retired and not include_retired:
                continue
            if self.variant == "open" and "open" not in e.variants:
                continue
            r = self.resolve(e.id)
            out.append({**e.model_dump(), "path": r.path, "health": r.health, "size": r.size, "sha256": r.sha256, "source_tree": r.source_tree})
        return out

    def lora_files(self) -> list[dict]:
        """LT1 (18 §3b): files under the loras folders (the models root and the mounted trees, subfolders included) no roster entry claims —
        `rel` is the loader's name relative to the folder (with "/"), the slots' `file:<rel>` id. The engine's cache of trained LoRAs
        (`loras/projects/…`, LT2) is left out: the project's registry lists those."""
        claimed = {e.name for e in ROSTER if e.folder == "loras"}
        out = []
        for (folder, name), (path, root) in sorted(self._found.items()):
            if folder != "loras" or name in claimed or ignore_reason(name) or path.suffix.lower() != ".safetensors":
                continue
            rel = path.relative_to(root / folder).as_posix()
            if rel.startswith("projects/"):
                continue
            out.append({"rel": rel, "name": name, "path": str(path), "size": path.stat().st_size, "root": str(root)})
        return out

    def unlisted_files(self) -> list[dict]:
        """Files on disk no roster entry claims — surfaced in the Models suite as 'unknown'; the ignore list's files are left out (ignored_files)."""
        claimed = {(e.folder, e.name) for e in ROSTER}
        return [{"folder": k[0], "name": k[1], "path": str(v[0]), "size": v[0].stat().st_size}
                for k, v in sorted(self._found.items()) if k not in claimed and not ignore_reason(k[1])
                and not (k[0] == "loras" and v[0].relative_to(v[1] / "loras").as_posix().startswith("projects/"))]   # LT2's cache is the registry's

    def ignored_files(self) -> list[dict]:
        """P18 (D84): files on disk loom2 will never suggest, with the reason (Hunyuan3D: its licence excludes the EU, D17)."""
        claimed = {(e.folder, e.name) for e in ROSTER}
        return [{"folder": k[0], "name": k[1], "path": str(v[0]), "size": v[0].stat().st_size, "reason": ignore_reason(k[1]) or ""}
                for k, v in sorted(self._found.items()) if k not in claimed and ignore_reason(k[1])]
