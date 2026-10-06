"""Fetch loom2 weights into the ComfyUI-layout models root with sha256 recorded (seed of the roster tool, 04 §1b).

Run (engine venv has huggingface_hub):
  engine/.venv/Scripts/python.exe scripts/fetch_weights.py [--only e8|e4|e5|klein4b] [--root F:/loom2-models]

Each entry: repo, file in repo, destination folder (ComfyUI key), optional rename, licence, spike. Files are
downloaded with hf_hub_download(local_dir=<tmp>) (resumable), hashed, moved into place, and appended to
<root>/roster.index.json. Existing destinations with the right size are skipped. Gated repos use the
HF token already stored in HF_HOME (F:/HF_HOME/token).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from huggingface_hub import hf_hub_download

MANIFEST = [
    # ---- M5 Edit AI tools ----
    dict(spike="m5", repo="ai-forever/Real-ESRGAN", file="RealESRGAN_x2.pth", dest="upscale_models", license="bsd-3-clause"),
    dict(spike="m5", repo="ai-forever/Real-ESRGAN", file="RealESRGAN_x4.pth", dest="upscale_models", license="bsd-3-clause"),
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
    # ---- open variant: Klein 4B text encoder (transformer already present) ----
    dict(spike="klein4b", repo="Comfy-Org/flux2-klein-4B", file="split_files/text_encoders/qwen_3_4b.safetensors",
         dest="text_encoders", license="apache-2.0"),
]


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(16 * 2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
    ap.add_argument("--only", action="append", help="spike tag(s) to fetch; default all")
    ap.add_argument("--no-hash", action="store_true")
    ap.add_argument("--include-retired", action="store_true", help="also fetch entries marked retired=... (deleted by policy D30)")
    a = ap.parse_args()
    root = Path(a.root)
    tmp = root / "_incoming"
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
        local = Path(hf_hub_download(m["repo"], m["file"], local_dir=str(tmp), token=True))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        shutil.move(str(local), str(dest))
        size = dest.stat().st_size
        dt = time.time() - t0
        digest = None if a.no_hash else sha256_of(dest)
        print(f"[done]  {dest.name}  {size/2**30:.2f} GiB in {dt:.0f} s ({size/2**20/max(dt,1):.0f} MiB/s)  sha256={digest[:16] if digest else '-'}…")
        index["files"] = [f for f in index["files"] if f["path"] != str(dest)] + [dict(
            path=str(dest), folder=m["dest"], repo=m["repo"], file=m["file"], size=size, sha256=digest,
            license=m["license"], spike=m["spike"], fetched=time.strftime("%Y-%m-%d %H:%M:%S"))]
        index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    # clean empty incoming dirs
    for p in sorted(tmp.rglob("*"), reverse=True):
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    print("[fetch] complete; index:", index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
