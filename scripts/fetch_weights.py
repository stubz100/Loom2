"""Fetch loom2 weights into the ComfyUI-layout models root with sha256 recorded (seed of the roster tool, 04 §1b).

Run (engine venv has huggingface_hub):
  engine/.venv/Scripts/python.exe scripts/fetch_weights.py [--only e8|e4|e5|klein4b] [--root F:/loom2-models]

Each entry: repo, file in repo, destination folder (ComfyUI key), optional rename, licence, spike. Files are
downloaded with hf_hub_download(local_dir=<tmp>) (resumable), hashed, moved into place, and appended to
<root>/roster.index.json. Existing destinations with the right size are skipped. Gated repos use the
HF token already stored in HF_HOME (F:/HF_HOME/token).

Stall watchdog (D91 follow-up: the SD 3.5 Medium transfer sat at 8.25 GB for ~4 min with the connection open): each download runs in
a child process; when nothing in the run's staging folder has grown for --stall-s seconds (default 120) the child is stopped and the
download started again — hf_hub_download resumes from its `.incomplete` file — up to --stall-retries times, each one logged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

MANIFEST = [
    # ---- M5 Edit AI tools ----
    dict(spike="m5", repo="ai-forever/Real-ESRGAN", file="RealESRGAN_x2.pth", dest="upscale_models", license="bsd-3-clause"),
    dict(spike="m5", repo="ai-forever/Real-ESRGAN", file="RealESRGAN_x4.pth", dest="upscale_models", license="bsd-3-clause"),
    # ---- E14 image → mesh (D74): ComfyUI's Pixal3D + TRELLIS.2 template (core nodes); int8 first, bf16 only if int8 fails on ROCm (08 §7).
    #      DINOv3 ships in an MIT repo but its weights carry Meta's DINOv3 licence: `full` only until reviewed (D17 / D26). BiRefNet is already here.
    dict(spike="e14", repo="Comfy-Org/TRELLIS.2", file="diffusion_models/trellis_2_int8_convrot.safetensors", dest="diffusion_models", license="mit",
         retired="E14 2026-10-12: silhouette IoU 1/5 (one prop a crumpled shell) against Pixal3D's 5/5; the VAEs, DINOv3 and MoGe are shared and stay"),
    dict(spike="e14", repo="Comfy-Org/Pixal3D", file="diffusion_models/pixal3d_int8_convrot.safetensors", dest="diffusion_models", license="mit"),
    dict(spike="e14", repo="Comfy-Org/Pixal3D", file="vae/trellis_2_shape_vae_bf16.safetensors", dest="vae", license="mit"),
    dict(spike="e14", repo="Comfy-Org/Pixal3D", file="vae/trellis_2_texture_vae_bf16.safetensors", dest="vae", license="mit"),
    dict(spike="e14", repo="Comfy-Org/Pixal3D", file="clip_vision/dino_v3_L_naf_fp32.safetensors", dest="clip_vision", license="dinov3 (Meta custom; full only until reviewed)"),
    dict(spike="e14", repo="Comfy-Org/MoGe", file="geometry_estimation/moge_2_vitl_normal_fp16.safetensors", dest="geometry_estimation", license="mit"),
    # ---- E11 Stage → video (D74): LTX-2.3's IC-LoRA Union (canny + depth + pose) through core GetICLoRAParameters + LTXVAddGuide
    dict(spike="e11", repo="Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control", file="ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors", dest="loras",
         license="ltx-2.x community (as the LTX-2.3 weights, D9)"),
    # ---- E10 Stage → image (D74): method 2 — RefControl's pose LoRA for Klein base 9B; method 3 — Z-Image Turbo + Fun ControlNet Union 2.1
    #      lite (core ModelPatchLoader + ZImageFunControlnet). Z-Image's encoder is the Klein 4B Qwen3-4B file already here (same sha256) and its
    #      VAE the FLUX.1 ae in the mounted D: tree (same sha256), so neither is fetched again.
    dict(spike="e10", repo="thedeoxen/refcontrol-FLUX.2-klein-9B-reference-pose-lora", file="refcontrol_v2_poses.safetensors", dest="loras", license="apache-2.0"),
    dict(spike="e10", repo="Comfy-Org/z_image_turbo", file="split_files/diffusion_models/z_image_turbo_bf16.safetensors", dest="diffusion_models", license="apache-2.0",
         retired="E10 2026-10-12: method 3 lost — PCK 0.30 depth / 0.08 pose, the figure at the wrong scale, same blocking 6/10"),
    dict(spike="e10", repo="alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1", file="Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors", dest="model_patches", license="apache-2.0",
         retired="E10 2026-10-12: with method 3"),
    # E10 scoring only (evaluation, never a product path): SDPose wholebody for keypoints, RT-DETR to box several people, DA3-BASE for depth
    dict(spike="e10", repo="Comfy-Org/SDPose", file="checkpoints/sdpose_wholebody_fp16.safetensors", dest="checkpoints", license="mit"),
    dict(spike="e10", repo="Comfy-Org/SDPose", file="diffusion_models/rt_detr_v4-x-hgnet_fp16.safetensors", dest="diffusion_models", license="mit (Comfy-Org repack; RT-DETRv4 apache-2.0)"),
    dict(spike="e10", repo="Comfy-Org/Depth-Anything-3", file="geometry_estimation/depth_anything_3_base.safetensors", dest="geometry_estimation", license="apache-2.0"),
    # ---- E12 angles, method B (D74): Qwen-Image-Edit 2511 as a Q4_K_M GGUF + fal's 96-pose angles LoRA + lightx2v's 4-step LoRA ----
    # E12 method D2 (2026-10-12, the author's web-search follow-up): fal-trained multi-angle LoRA for FLUX.2 dev — dev is `full` only (flux-nc)
    dict(spike="e12", repo="lovis93/Flux-2-Multi-Angles-LoRA-v2", file="flux-multi-angles-v2-72poses-comfy.safetensors", dest="loras",
         license="creativeml-openrail-m (LoRA; its base FLUX.2 dev is flux-nc, so full only)",
         retired="E12 2026-10-12: method D2 (dev + Turbo 8 steps) 105 s warm against the 60 s bar, rotations 4-5/10; identity 0.74 was good"),
    dict(spike="e12", repo="unsloth/Qwen-Image-Edit-2511-GGUF", file="qwen-image-edit-2511-Q4_K_M.gguf", dest="diffusion_models", license="apache-2.0",
         retired="E12 2026-10-12: method B warm 154 s against the 90 s kill rule (08 §7); identity 0.72 was the best, speed killed it"),
    dict(spike="e12", repo="fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA", file="qwen-image-edit-2511-multiple-angles-lora.safetensors", dest="loras", license="apache-2.0",
         retired="E12 2026-10-12: with method B"),
    dict(spike="e12", repo="lightx2v/Qwen-Image-Edit-2511-Lightning", file="Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", dest="loras", license="apache-2.0",
         retired="E12 2026-10-12: with method B"),
    # ---- E8 inpaint bake-off (and M5 Klein tiers) ----
    dict(spike="e8", repo="Comfy-Org/flux2-klein-9B", file="split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
         dest="text_encoders", license="flux-nc (TE: Qwen3 Apache-2.0 repack)"),
    dict(spike="e8", repo="black-forest-labs/FLUX.1-Fill-dev", file="flux1-fill-dev.safetensors",
         dest="diffusion_models", license="flux-nc (gated, official)", retired="E8 2026-10-05: weakest on 3 of 4 bench tasks"),
    # FLUX.1 ae, clip_l and t5xxl fp8 already exist in the mounted D:\comfyui tree (vae/flux1/ae.safetensors,
    # text_encoders/clip_l.safetensors, text_encoders/t5/t5xxl_fp8_e4m3fn_scaled.safetensors) — not re-fetched.
    # ---- E4 Wan 2.2 I2V-A14B ----
    dict(spike="e4", repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="HighNoise/Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf",
         dest="diffusion_models", license="apache-2.0 (QuantStack GGUF)", retired="E4c 2026-10-05: fp8 scaled is 1.8x faster at sampling"),
    dict(spike="e4", repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="LowNoise/Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf",
         dest="diffusion_models", license="apache-2.0 (QuantStack GGUF)", retired="E4c 2026-10-05: fp8 scaled is 1.8x faster at sampling"),
    dict(spike="e4", repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
         dest="text_encoders", license="apache-2.0"),
    dict(spike="e4", repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/vae/wan_2.1_vae.safetensors",
         dest="vae", license="apache-2.0"),
    dict(spike="e4", repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors",
         dest="loras", rename="Wan2.2-I2V-A14B-Lightning-4steps-high.safetensors", license="apache-2.0"),
    dict(spike="e4", repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors",
         dest="loras", rename="Wan2.2-I2V-A14B-Lightning-4steps-low.safetensors", license="apache-2.0"),
    # E4c (2026-10-05, performance-first policy D30): fp8-scaled experts to replace the GGUF Q5_K_M pair if faster
    dict(spike="e4", repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
         dest="diffusion_models", license="apache-2.0 (Comfy-Org repack)"),
    dict(spike="e4", repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
         dest="diffusion_models", license="apache-2.0 (Comfy-Org repack)"),
    # ---- E5 LTX-2.3 ----
    dict(spike="e5", repo="unsloth/LTX-2.3-GGUF", file="distilled-1.1/ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf",
         dest="diffusion_models", license="ltx-2.x community (unsloth GGUF)", retired="E5b 2026-10-05: 68-81 s/it vs 4.7 s/it fp8"),
    dict(spike="e5", repo="unsloth/gemma-3-12b-it-GGUF", file="gemma-3-12b-it-Q4_K_M.gguf",
         dest="text_encoders", license="gemma", retired="E5 2026-10-05: gemma fp8 used instead"),
    dict(spike="e5", repo="Lightricks/LTX-2.3", file="ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
         dest="upscale_models", license="ltx-2.x community"),
    # ComfyUI-native LTX-2.3 pieces (added 2026-10-05 after reading the Kijai / Comfy-Org repacks):
    dict(spike="e5", repo="Kijai/LTX2.3_comfy", file="vae/LTX23_video_vae_bf16.safetensors",
         dest="vae", rename="ltx-2.3_video_vae_bf16.safetensors", license="ltx-2.x community (Kijai repack)"),
    # ComfyUI 0.38 requires an audio VAE on LTXVEmptyLatentAudio even for silent clips (E5 preflight 2026-10-05):
    dict(spike="e5", repo="Kijai/LTX2.3_comfy", file="vae/LTX23_audio_vae_bf16.safetensors",
         dest="vae", rename="ltx-2.3_audio_vae_bf16.safetensors", license="ltx-2.x community (Kijai repack)"),
    dict(spike="e5", repo="Kijai/LTX2.3_comfy", file="text_encoders/ltx-2.3_text_projection_bf16.safetensors",
         dest="text_encoders", license="ltx-2.x community (Kijai repack)"),
    dict(spike="e5", repo="Comfy-Org/ltx-2", file="split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors",
         dest="text_encoders", license="gemma (Comfy-Org repack)"),
    # E5b (2026-10-05): GGUF Q4 runs at 68-81 s/it on the 9070 XT; fp8 with weight streaming is the fast path (E0)
    dict(spike="e5", repo="Kijai/LTX2.3_comfy", file="diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors",
         dest="diffusion_models", license="ltx-2.x community (Kijai repack)"),
    # ---- E18 lip-sync (D87): Wan2.2 S2V-14B fp8 + its wav2vec2 audio encoder (Comfy-Org repack, Apache-2.0) ----
    dict(spike="e18", repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors", dest="diffusion_models", license="apache-2.0"),
    dict(spike="e18", repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/audio_encoders/wav2vec2_large_english_fp16.safetensors", dest="audio_encoders", license="apache-2.0"),
    # ---- E19 pose-driven shots (D87): Wan2.2 Animate-14B fp8 (Kijai's scaled repack, the ComfyUI template's file), clip_vision_h, the LightX2V 4-step I2V LoRA ----
    dict(spike="e19", repo="Kijai/WanVideo_comfy_fp8_scaled", file="Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", dest="diffusion_models", license="apache-2.0 (Kijai repack)"),
    dict(spike="e19", repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/clip_vision/clip_vision_h.safetensors", dest="clip_vision", license="apache-2.0"),
    dict(spike="e19", repo="Kijai/WanVideo_comfy", file="Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", dest="loras", license="apache-2.0 (lightx2v; Kijai repack)"),
    # ---- wave CR (D89, .docs/creative_image/04 §3): creative t2i / i2i — Krea 2 Turbo + Raw, Z-Image base, Chroma1-HD, SD 3.5 Large (Refine only).
    #      Krea 2's VAE is the qwen_image_vae already here and Z-Image's encoder the Klein 4B qwen_3_4b (same sha256); the FLUX.1 ae serves Z-Image and Chroma.
    dict(spike="cr", repo="Comfy-Org/Krea-2", file="diffusion_models/krea2_turbo_fp8_scaled.safetensors", dest="diffusion_models", license="krea-2-community"),
    dict(spike="cr", repo="Comfy-Org/Krea-2", file="diffusion_models/krea2_raw_fp8_scaled.safetensors", dest="diffusion_models", license="krea-2-community"),
    dict(spike="cr", repo="Comfy-Org/Krea-2", file="text_encoders/qwen3vl_4b_fp8_scaled.safetensors", dest="text_encoders", license="apache-2.0 (Qwen3-VL, Comfy-Org repack)"),
    *[dict(spike="cr", repo="Comfy-Org/Krea-2", file=f"loras/krea2_{s}.safetensors", dest="loras", license="krea-2-community")
      for s in ("darkbrush", "dotmatrix", "kidsdrawing", "neondrip", "rainywindow", "retroanime", "softwatercolor", "sunsetblur", "vintagetarot", "style_reference")],
    dict(spike="cr", repo="Comfy-Org/z_image", file="split_files/diffusion_models/z_image_bf16.safetensors", dest="diffusion_models", license="apache-2.0"),
    dict(spike="cr", repo="Comfy-Org/z_image_turbo", file="split_files/vae/ae.safetensors", dest="vae", license="apache-2.0 (FLUX.1 VAE)"),
    dict(spike="cr", repo="Comfy-Org/Chroma1-HD_repackaged", file="split_files/diffusion_models/Chroma1-HD-fp8mixed.safetensors", dest="diffusion_models", license="apache-2.0"),
    dict(spike="cr", repo="comfyanonymous/flux_text_encoders", file="t5xxl_fp8_e4m3fn_scaled.safetensors", dest="text_encoders", license="apache-2.0 (T5)"),
    dict(spike="cr", repo="Comfy-Org/stable-diffusion-3.5-fp8", file="sd3.5_large_fp8_scaled.safetensors", dest="checkpoints", license="stabilityai-ai-community"),
    # ---- D91 sample models: Lumina Image 2.0 (all-in-one: Gemma 2B encoder + VAE inside) and SD 3.5 Medium (its CLIP-L / CLIP-G / T5 fp8 inside) ----
    dict(spike="sm", repo="Comfy-Org/Lumina_Image_2.0_Repackaged", file="all_in_one/lumina_2.safetensors", dest="checkpoints", license="apache-2.0"),
    dict(spike="sm", repo="Comfy-Org/stable-diffusion-3.5-fp8", file="sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors", dest="checkpoints", license="stabilityai-ai-community"),
    # ---- open variant: Klein 4B text encoder (transformer already present) ----
    dict(spike="klein4b", repo="Comfy-Org/flux2-klein-4B", file="split_files/text_encoders/qwen_3_4b.safetensors",
         dest="text_encoders", license="apache-2.0"),
    # ---- E40 (2026-10-28, post-MVP item 5): SeedVR2 as the "add real detail" upscaler — ComfyUI core nodes at the pin (nodes_seedvr), Apache-2.0
    #      (ByteDance-Seed; Comfy-Org's repack). The 3B in the template's int8 convrot and in fp8 (04 §4 named fp8); the shared VAE. The loser is deleted (D30).
    dict(spike="e40", repo="Comfy-Org/SeedVR2", file="vae/seedvr2_ema_vae_fp16.safetensors", dest="vae", license="apache-2.0"),
    dict(spike="e40", repo="Comfy-Org/SeedVR2", file="diffusion_models/seedvr2_3b_int8_convrot.safetensors", dest="diffusion_models", license="apache-2.0"),
    dict(spike="e40", repo="Comfy-Org/SeedVR2", file="diffusion_models/seedvr2_3b_fp8_e4m3fn.safetensors", dest="diffusion_models", license="apache-2.0",
         retired="E40 2026-10-28: equal to int8 convrot on the sheet and the numbers (Laplacian 308 against 334, the same seconds and peak); int8 — the template's — kept"),
]


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(16 * 2**20), b""):
            h.update(chunk)
    return h.hexdigest()


class Stalled(RuntimeError):
    """A download made no progress for the stall window more often than the retries allow."""


def watch(start: Callable[[], "object"], probe: Callable[[], int], *, stall_s: float = 120.0, retries: int = 3, poll_s: float = 5.0,
          log: Callable[[str], None] = print, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
    """Run a download under a stall watchdog. `start()` returns a worker with `alive()`, `stop()` and `result()` (raises if it failed);
    `probe()` is the bytes on disk so far. No growth for `stall_s` → stop the worker and start a new one (the download resumes from its
    partial file), at most `retries` times; then `Stalled`. Pure on its arguments so the offline test drives it with a fake clock."""
    restarts = 0
    while True:
        w = start()
        last, since = probe(), clock()
        while w.alive():
            sleep(poll_s)
            n = probe()
            if n != last:
                last, since = n, clock()
            elif clock() - since >= stall_s:
                w.stop()
                if restarts >= retries:
                    log(f"[stall] no growth for {stall_s:.0f} s at {last / 2**30:.2f} GiB; {retries} restart(s) used, giving up")
                    raise Stalled(f"no progress for {stall_s:.0f} s after {retries} restart(s)")
                restarts += 1
                log(f"[stall] no growth for {stall_s:.0f} s at {last / 2**30:.2f} GiB; restart {restarts}/{retries} (resumes from the partial file)")
                break
        else:
            return w.result()


_CHILD = "import sys; from huggingface_hub import hf_hub_download; hf_hub_download(sys.argv[1], sys.argv[2], local_dir=sys.argv[3], token=True)"


class _Proc:
    """One hf_hub_download in a child process (the same interpreter) — a thread blocked on a dead socket cannot be stopped, a process can."""

    def __init__(self, repo: str, file: str, local_dir: Path) -> None:
        self.target = local_dir / file
        self.p = subprocess.Popen([sys.executable, "-c", _CHILD, repo, file, str(local_dir)])

    def alive(self) -> bool:
        return self.p.poll() is None

    def stop(self) -> None:
        self.p.kill()
        self.p.wait(30)

    def result(self) -> Path:
        if self.p.wait() != 0 or not self.target.is_file():
            raise RuntimeError(f"download failed (exit {self.p.returncode})")
        return self.target


def staged_bytes(tmp: Path) -> int:
    """Everything in this run's staging folder (the `.incomplete` under .cache/huggingface/download and the finished file)."""
    n = 0
    for f in tmp.rglob("*"):
        try:
            if f.is_file():
                n += f.stat().st_size
        except OSError:
            pass
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
    ap.add_argument("--only", action="append", help="spike tag(s) to fetch; default all")
    ap.add_argument("--no-hash", action="store_true")
    ap.add_argument("--include-retired", action="store_true", help="also fetch entries marked retired=... (deleted by policy D30)")
    ap.add_argument("--stall-s", type=float, default=120.0, help="restart a transfer whose partial file has not grown for this long (s)")
    ap.add_argument("--stall-retries", type=int, default=3, help="restarts per file before giving up")
    a = ap.parse_args()
    root = Path(a.root)
    # one staging folder per run: two fetches at once (2026-10-11) shared `_incoming`, and one's clean-up removed the folder the other's
    # download was being copied into
    tmp = root / "_incoming" / f"run-{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    index_path = root / "roster.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"files": []}
    known = {f["path"] for f in index["files"]}
    todo = [m for m in MANIFEST if (not a.only or m["spike"] in a.only) and (a.include_retired or not m.get("retired"))]
    print(f"[fetch] {len(todo)} entries → {root}")
    for m in todo:
        dest = root / m["dest"] / (m.get("rename") or Path(m["file"]).name)
        if dest.exists() and str(dest) in known:
            print(f"[skip]  {dest.name} (indexed)")
            continue
        t0 = time.time()
        print(f"[get]   {m['repo']} :: {m['file']}")
        local = watch(lambda m=m: _Proc(m["repo"], m["file"], tmp), lambda: staged_bytes(tmp), stall_s=a.stall_s, retries=a.stall_retries)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        shutil.move(str(local), str(dest))
        size = dest.stat().st_size
        dt = time.time() - t0
        digest = None if a.no_hash else sha256_of(dest)
        print(f"[done]  {dest.name}  {size/2**30:.2f} GiB in {dt:.0f} s ({size/2**20/max(dt,1):.0f} MiB/s)  sha256={digest[:16] if digest else '-'}…")
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"files": []}   # re-read: another run may have written
        index["files"] = [f for f in index["files"] if f["path"] != str(dest)] + [dict(
            path=str(dest), folder=m["dest"], repo=m["repo"], file=m["file"], size=size, sha256=digest,
            license=m["license"], spike=m["spike"], fetched=time.strftime("%Y-%m-%d %H:%M:%S"))]
        index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    # clean this run's empty staging dirs (only its own)
    for p in sorted(tmp.rglob("*"), reverse=True):
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    if tmp.is_dir() and not any(tmp.iterdir()):
        tmp.rmdir()
    print("[fetch] complete; index:", index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
