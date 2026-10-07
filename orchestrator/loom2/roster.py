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

from pydantic import BaseModel, Field

Folder = Literal["diffusion_models", "text_encoders", "vae", "loras", "clip_vision", "upscale_models",
                 "controlnet", "checkpoints", "sam3", "background_removal", "embeddings"]
Health = Literal["present", "verified", "missing", "retired"]


class RosterEntry(BaseModel):
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


# The catalogue. Order: family, then role. `open` variant = Apache/MIT only (D26).
ROSTER: list[RosterEntry] = [
    # ---- tools (M5 Edit AI: upscalers, segmentation) ----
    RosterEntry(id="birefnet", name="BiRefNet-general.safetensors", folder="background_removal", family="tools", role="tool",
                repo="ZhengPeng7/BiRefNet", file="model.safetensors", license="mit", variants=["full", "open"], approx_gb=0.89,
                note="subject matte for AI Select · Subject (core LoadBackgroundRemovalModel / RemoveBackground, 1024² input)"),
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
                license="flux-nc", approx_gb=2.6, note="8-step Turbo LoRA for dev (E0: ≈ 40 s per 960×544)"),
    # ---- FLUX.2 Klein (Edit workhorse, Iterate/Quality tiers, D6/D7) ----
    RosterEntry(id="klein-4b", name="flux-2-klein-4b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-4B", file="split_files/diffusion_models/flux-2-klein-4b.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=7.2),
    RosterEntry(id="klein-base-4b", name="flux-2-klein-base-4b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-4B", file="split_files/diffusion_models/flux-2-klein-base-4b.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=7.2),
    RosterEntry(id="qwen3-4b", name="qwen_3_4b.safetensors", folder="text_encoders", family="klein", role="text_encoder",
                repo="Comfy-Org/flux2-klein-4B", file="split_files/text_encoders/qwen_3_4b.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=7.5),
    RosterEntry(id="klein-9b", name="flux-2-klein-9b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-9B", file="split_files/diffusion_models/flux-2-klein-9b.safetensors", license="flux-nc", approx_gb=16.9),
    RosterEntry(id="klein-base-9b", name="flux-2-klein-base-9b.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-9B", file="split_files/diffusion_models/flux-2-klein-base-9b.safetensors", license="flux-nc", approx_gb=16.9, note="refine path only (E8)"),
    RosterEntry(id="klein-9b-kv", name="flux-2-klein-9b-kv.safetensors", folder="diffusion_models", family="klein", role="transformer",
                repo="Comfy-Org/flux2-klein-9B", file="split_files/diffusion_models/flux-2-klein-9b-kv.safetensors", license="flux-nc", approx_gb=16.9, note="multi-ref KV cache; unbenchmarked"),
    RosterEntry(id="qwen3-8b-fp8mixed", name="qwen_3_8b_fp8mixed.safetensors", folder="text_encoders", family="klein", role="text_encoder",
                repo="Comfy-Org/flux2-klein-9B", file="split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors", license="apache-2.0", approx_gb=8.1),
    # 2026-10-07 encoder experiment: llama.cpp quantizations of the same Qwen3-8B, loaded through ComfyUI-GGUF's CLIPLoaderGGUF. The fp8
    # encoder (8.3 GB resident) and the fp8-cast 9B transformer (8.7 GB) do not fit 16 GB together, so DynamicVRAM streams the sampler
    # (journal 09:37); a 4-bit encoder leaves the pair resident. 9B family only — the 4B models have a different hidden size.
    RosterEntry(id="qwen3-8b-q4km", name="Qwen3-8B-Q4_K_M.gguf", folder="text_encoders", family="klein", role="text_encoder",
                repo="unsloth/Qwen3-8B-GGUF", file="Qwen3-8B-Q4_K_M.gguf", license="apache-2.0", approx_gb=5.03, note="Klein 9B encoder, 4-bit K_M (CLIPLoaderGGUF)"),
    RosterEntry(id="qwen3-8b-q4ks", name="Qwen3-8B-Q4_K_S.gguf", folder="text_encoders", family="klein", role="text_encoder",
                repo="unsloth/Qwen3-8B-GGUF", file="Qwen3-8B-Q4_K_S.gguf", license="apache-2.0", approx_gb=4.80, note="Klein 9B encoder, 4-bit K_S (CLIPLoaderGGUF)"),
    RosterEntry(id="qwen3-8b-q3km", name="Qwen3-8B-Q3_K_M.gguf", folder="text_encoders", family="klein", role="text_encoder",
                repo="unsloth/Qwen3-8B-GGUF", file="Qwen3-8B-Q3_K_M.gguf", license="apache-2.0", approx_gb=4.12, note="Klein 9B encoder, 3-bit K_M (CLIPLoaderGGUF)"),
    # ---- Wan 2.2 I2V-A14B (primary i2v, D8) ----
    RosterEntry(id="wan22-i2v-high-q5", name="Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf", folder="diffusion_models", family="wan22", role="transformer",
                repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="HighNoise/Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf", license="apache-2.0", variants=["full", "open"], approx_gb=10.1, retired="E4c 2026-10-05: fp8 scaled experts are 1.8× faster at sampling (D30)"),
    RosterEntry(id="wan22-i2v-low-q5", name="Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf", folder="diffusion_models", family="wan22", role="transformer",
                repo="QuantStack/Wan2.2-I2V-A14B-GGUF", file="LowNoise/Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf", license="apache-2.0", variants=["full", "open"], approx_gb=10.1, retired="E4c 2026-10-05: fp8 scaled experts are 1.8× faster at sampling (D30)"),
    RosterEntry(id="wan22-i2v-high-fp8", name="wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", folder="diffusion_models", family="wan22", role="transformer",
                repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=13.3, note="E4c 2026-10-05: 236 s per 81 f clip vs 322 s GGUF; D8 recipe"),
    RosterEntry(id="wan22-i2v-low-fp8", name="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", folder="diffusion_models", family="wan22", role="transformer",
                repo="Comfy-Org/Wan_2.2_ComfyUI_Repackaged", file="split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=13.3, note="E4c 2026-10-05: 236 s per 81 f clip vs 322 s GGUF; D8 recipe"),
    RosterEntry(id="umt5-xxl-fp8", name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", folder="text_encoders", family="wan22", role="text_encoder",
                repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=6.3),
    RosterEntry(id="wan21-vae", name="wan_2.1_vae.safetensors", folder="vae", family="wan22", role="vae",
                repo="Comfy-Org/Wan_2.1_ComfyUI_repackaged", file="split_files/vae/wan_2.1_vae.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=0.24),
    RosterEntry(id="wan22-lightning-high", name="Wan2.2-I2V-A14B-Lightning-4steps-high.safetensors", folder="loras", family="wan22", role="lora",
                repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=1.1),
    RosterEntry(id="wan22-lightning-low", name="Wan2.2-I2V-A14B-Lightning-4steps-low.safetensors", folder="loras", family="wan22", role="lora",
                repo="lightx2v/Wan2.2-Lightning", file="Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors", license="apache-2.0", variants=["full", "open"], approx_gb=1.1),
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
        self._found = found
        ledger_path = self.models_root / "roster.index.json"
        self._ledger = {}
        if ledger_path.is_file():
            try:
                for f in json.loads(ledger_path.read_text(encoding="utf-8")).get("files", []):
                    self._ledger[Path(f["path"]).name] = f
            except (OSError, ValueError):
                pass
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

    def unlisted_files(self) -> list[dict]:
        """Files on disk no roster entry claims — surfaced in the Models suite as 'unknown'."""
        claimed = {(e.folder, e.name) for e in ROSTER}
        return [{"folder": k[0], "name": k[1], "path": str(v[0]), "size": v[0].stat().st_size}
                for k, v in sorted(self._found.items()) if k not in claimed]
