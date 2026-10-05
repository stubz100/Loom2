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
    # ---- E8 inpaint bake-off (and M5 Klein tiers) ----
    dict(spike="e8", repo="Comfy-Org/flux2-klein-9B", file="split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
         dest="text_encoders", license="flux-nc (TE: Qwen3 Apache-2.0 repack)"),
    dict(spike="e8", repo="black-forest-labs/FLUX.1-Fill-dev", file="flux1-fill-dev.safetensors",
         dest="diffusion_models", license="flux-nc (gated, official)"),
    dict(spike="e8", repo="black-forest-labs/FLUX.1-Fill-dev", file="ae.safetensors",
         dest="vae", rename="flux1-ae.safetensors", license="flux-nc (gated, official)"),
    dict(spike="e8", repo="comfyanonymous/flux_text_encoders", file="clip_l.safetensors",
         dest="text_encoders", license="openrail (CLIP-L)"),
    dict(spike="e8", repo="comfyanonymous/flux_text_encoders", file="t5xxl_fp8_e4m3fn_scaled.safetensors",
         dest="text_encoders", license="apache-2.0 (T5-XXL)"),
    # ---- E4 Wan 2.2 I2V-A14B ----
    dict(spike="e4", repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="HighNoise/Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf",
         dest="diffusion_models", license="apache-2.0 (QuantStack GGUF)"),
    dict(spike="e4", repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="LowNoise/Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf",
         dest="diffusion_models", license="apache-2.0 (QuantStack GGUF)"),
    dict(spike="e4", repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
         dest="text_encoders", license="apache-2.0"),
    dict(spike="e4", repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/vae/wan_2.1_vae.safetensors",
         dest="vae", license="apache-2.0"),
    dict(spike="e4", repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors",
         dest="loras", rename="Wan2.2-I2V-A14B-Lightning-4steps-high.safetensors", license="apache-2.0"),
    dict(spike="e4", repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors",
         dest="loras", rename="Wan2.2-I2V-A14B-Lightning-4steps-low.safetensors", license="apache-2.0"),
    # ---- E5 LTX-2.3 ----
    dict(spike="e5", repo="unsloth/LTX-2.3-GGUF", file="distilled-1.1/ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf",
         dest="diffusion_models", license="ltx-2.x community (unsloth GGUF)"),
    dict(spike="e5", repo="unsloth/gemma-3-12b-it-GGUF", file="gemma-3-12b-it-Q4_K_M.gguf",
         dest="text_encoders", license="gemma"),
    dict(spike="e5", repo="Lightricks/LTX-2.3", file="ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
         dest="upscale_models", license="ltx-2.x community"),
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
    a = ap.parse_args()
    root = Path(a.root)
    tmp = root / "_incoming"
    tmp.mkdir(parents=True, exist_ok=True)
    index_path = root / "roster.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"files": []}
    known = {f["path"] for f in index["files"]}
    todo = [m for m in MANIFEST if not a.only or m["spike"] in a.only]
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
