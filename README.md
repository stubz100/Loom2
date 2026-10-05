# loom2

A local AI image and video studio for storyboard pre-production on a single Windows machine with an AMD
Radeon RX 9070 XT (16 GB): FLUX.2 generation with BFL JSON prompting, a layered inpaint/refine editor,
image-to-video, and a catalogue with full provenance. Successor to the author's "loom" / Loreweave Studio.

**Status (2026-10-05):** M0 spikes closed (all model and frontend decisions taken on the rig); M1 foundation
in place — orchestrator core with a 20/20 rig acceptance, Tauri shell with sidecar supervision, frame skeleton,
Models suite and Settings. Next: M2 Catalogue.

- Plan and decisions: [`.docs/proto01/00-README.md`](.docs/proto01/00-README.md) (read in order 01 → 14)
- Implementation journal: [`.docs/proto01/90-journal.md`](.docs/proto01/90-journal.md)
- Benchmarks that gate every milestone: [`bench/`](bench/README.md)

## Layout

```
.docs/proto01/   plan (01–14), decision log (13), journal (90)
bench/           t2i JSON prompts, inpaint tasks + masks (frozen source), i2v tasks + frames
engine/
  comfyui/       pinned Comfy-Org/ComfyUI submodule (v0.38.2) — model and inference management only
  nodes.lock     pinned custom nodes (ComfyUI-GGUF, LanPaint) + local patches in engine/patches/
  constraints.txt / extra_model_paths.yaml / spikes/ (E0–E8 drivers and contact-sheet tools)
orchestrator/    Python package `loom2` (uv, 3.13): workspace, roster, ComfyUI client + supervisor, recipe
                 compiler + contract checks, durable queue, catalogue, FastAPI + WebSocket; tests/
frontend/        Vite 8 + React 19 + TS app (frame, suites, store, api) and the Tauri 2 shell in src-tauri/
scripts/         engine-setup/start/stop · fetch_weights · prune_weights · make_object_info_fixture ·
                 m1_acceptance · dev.ps1
```

## Quickstart (Windows 11, ROCm 10.0, Python 3.13 via uv, Node 22, Rust 1.90)

```powershell
git clone --recurse-submodules https://github.com/stubz100/Loom2
.\scripts\engine-setup.ps1                                  # engine venv + torch 2.13.0+rocm10.0.0 + ComfyUI deps + nodes
uv sync --project orchestrator --extra dev                  # orchestrator venv
cd frontend; npm install; cd ..
engine\.venv\Scripts\python.exe scripts\fetch_weights.py    # weights into F:\loom2-models (ComfyUI layout, sha256 ledger)
.\scripts\dev.ps1                                           # Vite + shell + orchestrator (engine starts on the first job)
```

Tests: `orchestrator\.venv\Scripts\python.exe -m pytest` (offline, against a captured `/object_info` fixture) and
`orchestrator\.venv\Scripts\python.exe scripts\m1_acceptance.py` (rig: real generation, kill/resume/cancel).

Weights are never in git. Model roots are mounted through `engine/extra_model_paths.yaml` (ComfyUI layout);
the roster lives in `orchestrator/loom2/roster.py` (D1), fp8 first (D30).
