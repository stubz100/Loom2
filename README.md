# loom2

A local AI image and video studio for storyboard pre-production on a single Windows machine with an AMD
Radeon RX 9070 XT (16 GB): FLUX.2 generation with BFL JSON prompting, a layered inpaint/refine editor,
image-to-video, and a catalogue with full provenance. Successor to the author's "loom" / Loreweave Studio.

**Status (2026-10-04):** planning complete, spike E0 passed (engine + environment verified on the rig). No app
code yet.

- Plan and decisions: [`.docs/proto01/00-README.md`](.docs/proto01/00-README.md) (read in order 01 → 14)
- Implementation journal: [`.docs/proto01/90-journal.md`](.docs/proto01/90-journal.md)
- Benchmarks that gate every milestone: [`bench/`](bench/README.md)

## Layout

```
.docs/proto01/   plan (01–14), decision log (13), journal (90)
bench/           t2i JSON prompts, inpaint tasks + masks, i2v tasks
engine/
  comfyui/       pinned Comfy-Org/ComfyUI submodule (v0.38.2) — model and inference management only
  nodes.lock     pinned custom nodes (ComfyUI-GGUF, LanPaint) + local patches in engine/patches/
  constraints.txt / extra_model_paths.yaml / spikes/
scripts/         engine-setup.ps1 · engine-start.ps1 · engine-stop.ps1
```

## Engine quickstart (Windows 11, ROCm 10.0, Python 3.13 via uv)

```powershell
git clone --recurse-submodules <this repo>
.\scripts\engine-setup.ps1      # venv + torch 2.13.0+rocm10.0.0 + ComfyUI deps + pinned nodes + patches
.\scripts\engine-start.ps1      # headless ComfyUI on 127.0.0.1:8188
engine\.venv\Scripts\python.exe engine\spikes\e0_comfy_t2i.py --config fp8 --turbo --steps 8
```

Weights are never in git. Model roots are mounted through `engine/extra_model_paths.yaml` (ComfyUI layout).
