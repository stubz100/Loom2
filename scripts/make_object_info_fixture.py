"""Reduce a captured ComfyUI `/object_info` to the node classes loom2's graph builders use, for offline contract
tests (06 §9). Re-run after an engine pin bump:

  engine/.venv/Scripts/python.exe scripts/make_object_info_fixture.py \
      [--capture engine/spikes/out/object_info_v0.38.2.json] [--out orchestrator/tests/fixtures/object_info.json]

The capture is produced by GET /object_info (+ /system_stats) on the running engine; the fixture keeps the
engine version and only the listed classes, so it stays small enough to commit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CLASSES = [
    # loaders
    "UNETLoader", "UnetLoaderGGUF", "CLIPLoader", "CLIPLoaderGGUF", "DualCLIPLoader", "VAELoader", "LoraLoaderModelOnly", "LoraLoader", "LoadImage", "LoadImageMask",
    # FLUX.2 / Klein
    "CLIPTextEncode", "FluxGuidance", "ConditioningZeroOut", "EmptyFlux2LatentImage", "KSampler", "KSamplerAdvanced", "VAEDecode", "VAEEncode",
    "SaveImage", "PreviewImage", "ReferenceLatent", "InpaintModelConditioning", "DifferentialDiffusion", "ImageCompositeMasked", "EmptyImage",
    "ImagePadForOutpaint", "ImageScale", "ImageCrop", "Flux2Scheduler", "BasicGuider", "RandomNoise", "KSamplerSelect", "SamplerCustomAdvanced",
    "ModelSamplingFlux", "ModelSamplingSD3", "VAEDecodeTiled", "CFGGuider",
    # M5 slice 2: AI Select and the tiled refine
    "CheckpointLoaderSimple", "SAM3_Detect", "CreateBoundingBoxes", "LoadBackgroundRemovalModel", "RemoveBackground", "MaskToImage", "ImageToMask",
    "SolidMask", "FeatherMask", "GrowMask", "InvertMask", "ThresholdMask", "PrimitiveString",
    # LanPaint (custom node, pinned)
    "LanPaint_ImageEncode", "LanPaint_ImageDecode", "LanPaint_SamplerCustomAdvanced", "LanPaint_KSampler",
    # Wan 2.2
    "WanImageToVideo", "WanFirstLastFrameToVideo", "CreateVideo", "SaveVideo",
    # LTX-2.3
    "LTXVImgToVideo", "LTXVAddGuide", "LTXVConditioning", "LTXVScheduler", "LTXVEmptyLatentAudio", "LTXVConcatAVLatent", "LTXVSeparateAVLatent",
    "LTXVCropGuides", "LTXVPreprocess",
    # upscale / tools
    "UpscaleModelLoader", "ImageUpscaleWithModel",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", default="engine/spikes/out/object_info_v0.38.2.json")
    ap.add_argument("--out", default="orchestrator/tests/fixtures/object_info.json")
    a = ap.parse_args()
    cap = json.loads(Path(a.capture).read_text(encoding="utf-8"))
    info = cap["object_info"]
    missing = [c for c in CLASSES if c not in info]
    reduced = {c: info[c] for c in CLASSES if c in info}
    # enum inputs list the files present at capture time; keep them (tests resolve names by basename against them)
    out = {"system": cap.get("system"), "classes": sorted(reduced), "missing_at_capture": missing, "object_info": reduced}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"fixture: {len(reduced)} classes, {Path(a.out).stat().st_size/1024:.0f} KiB -> {a.out}; missing at capture: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
