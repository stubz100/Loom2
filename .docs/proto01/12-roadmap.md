# 12 · Roadmap — spikes, milestones, gates

Durations are honest ranges for one developer with an AI assistant, assuming the rig is available. Every
milestone ends with a **rig acceptance run** recorded in the journal (`90-journal.md`), per loom lesson 2.
UI documents (07–11) are approved **before** their milestone starts (the user's requirement).

## 0. Order of work and why

```
M0 spikes ──► M1 foundation ──► M2 catalogue ──► M3 generate ──► M4 edit core ──► M5 edit AI ──► M6 animate ──► M7 MVP
   (retire risk)   (skeleton)      (see anything)  (target a)     (editor)        (target b)      (target c)    (hardening)
```

Catalogue comes before Generate because every suite's results are viewed through it; Edit core precedes
Edit AI because the compositor is the biggest technical risk after the engine; Animate last because its
models are the heaviest and benefit from a hardened queue.

## 1. M0 · Spikes (2–3 weeks, parallelisable)

| Id | Spike | Pass bar | Decides |
| --- | --- | --- | --- |
| **E0** | Set up the environment per §1a (uv, Python 3.13, torch 2.13.0+rocm10.0.0), clone Comfy-Org/ComfyUI at **v0.38.2** into `engine/comfyui/`, install ComfyUI-GGUF + LanPaint, mount `D:\comfyui\ComfyUI\models` via `extra_model_paths.yaml`; run the sanity matrix; then drive it headless from Python, **dev first (D21)**: FLUX.2 dev JSON-prompt t2i at 960×544 as GGUF Q4_K_M + Mistral GGUF Q4_K_M and as Comfy fp8mixed + Mistral fp8 (pick the faster/stabler), with and without the Turbo LoRA; then Klein 9B fp8 t2i and Klein inpaint via `InpaintModelConditioning` + `ReferenceLatent`; measure vs loom's torch worker on identical prompts | runs unattended for 50 jobs without HIP failure; dev produces JSON-adherent images with time + peak VRAM recorded for both formats; Klein 9B ≤ 15 s/image at 1 MP; inpaint seam acceptable on 2 bench tasks | D2 engine (06 §3), dev format choice |
| **E1** | PixiJS v8 WebGPU compositor inside Tauri 2 on this rig; WebGL2 fallback toggle | 60 fps, 6 × 4K layers, 3 advanced blend modes, masks | D3 renderer (05) |
| **E2** | Loopback throughput: FastAPI streams a 200 MB latent + an 8K PNG; UI uploads a 64 MB mask via `PUT /blobs` | ≥ 500 MB/s into a GPU texture | D4 transport |
| **E3** | Worker brush (FastMask pattern) with `pointerrawupdate` + predicted events, **mouse-driven** (D19: no pen yet; pressure/Delegated Ink implemented, untested) | ≤ 1 frame visible lag at 2K preview; no dropped dabs at fast mouse strokes | Edit feasibility |
| **E4** | Wan 2.2 I2V-A14B GGUF Q5_K_M + umT5 fp8 + Lightning 4+4 via ComfyUI on the rig; FLF with `WanFirstLastFrameToVideo` | 81 f @ 480p completes; time and peak VRAM recorded; identity visually acceptable | D8 primary i2v |
| **E5** | LTX-2.3 distilled GGUF Q4_K_M + Gemma-3 Q4 via ComfyUI; one mid keyframe | 121 f completes; time recorded | D9 secondary i2v |
| **E6** | Mediabunny `CanvasSink` scrub on a 121-frame MP4; TorchCodec exact seek on the master | every frame reachable, step < 50 ms | video stack |
| **E7** | MIOpen on/off for VAE decode and ESRGAN on gfx1201 under ComfyUI | pick the faster, document | runtime policy |
| **E8** | Inpaint quality bake-off on 5 bench tasks: Klein+ICM, Klein+LanPaint, FLUX.1 Fill Q8, Qwen-Image-Edit (2509 on disk) | ranked results with timings | D7 inpaint stack |

**E0 status — closed PASS on 2026-10-04** (journal 18:44–20:40): environment and engine verified; dev fp8mixed
**62 s warm / 107 s cold** for 20 steps at 960×544 (loom's worker: 649 s); GGUF Q4 ≈ 11× slower (kept as a
VRAM-saving option only); Turbo 8-step ≈ 40–68 s; 57 engine executions incl. a 50-job loop with 0 errors; one
node-drift bug patched (`engine/patches/`). The Klein 9B and Klein-inpaint sub-items moved to M5/E8 per D21.
Follow-ups: Q15 (bimodal sampling speed under sustained load), E7 (MIOpen on real VAE decode — the sanity conv
favoured MIOpen on), encoder stays on the GPU (CPU encode ≈ 170 s per new prompt).

### 1a. Environment setup (E0 prerequisite; decision D16)

Nothing here touches PATH, the system Python 3.12, or loom's venv.

```powershell
# 0. uv (one-time) — https://docs.astral.sh/uv/
irm https://astral.sh/uv/install.ps1 | iex
uv python install 3.13

# 1. engine venv: ComfyUI + GPU tools
uv venv engine\.venv --python 3.13
# constraints pin the ROCm torch so ComfyUI's unpinned "torch" can never resolve to a CPU build from PyPI
@"
torch==2.13.0+rocm10.0.0
torchvision==0.28.0+rocm10.0.0
torchaudio==2.11.0.2+rocm10.0.0
"@ | Set-Content engine\constraints.txt
uv pip install --python engine\.venv `
  --index-url https://stable.repo.amd.com/rocm/whl-next/ --extra-index-url https://pypi.org/simple `
  "torch[device-all]==2.13.0+rocm10.0.0" "torchvision[device-all]==0.28.0+rocm10.0.0" "torchaudio==2.11.0.2+rocm10.0.0"
git clone --branch v0.38.2 --depth 1 https://github.com/Comfy-Org/ComfyUI engine\comfyui
uv pip install --python engine\.venv -c engine\constraints.txt `
  --index-url https://stable.repo.amd.com/rocm/whl-next/ --extra-index-url https://pypi.org/simple `
  -r engine\comfyui\requirements.txt
uv pip install --python engine\.venv "triton-windows==3.8.0.post29"     # optional
# pinned custom nodes (commits recorded in engine/nodes.lock): ComfyUI-GGUF, LanPaint

# 2. orchestrator venv: torch-free
uv venv orchestrator\.venv --python 3.13
uv pip install --python orchestrator\.venv -r orchestrator\requirements.txt
```

Sanity matrix (recorded in the journal before any model runs):

| Check | Expect |
| --- | --- |
| `torch.__version__`, `torch.version.hip`, `torch.cuda.get_device_name(0)` | `2.13.0+rocm10.0.0`, HIP 7.x/10.x, `AMD Radeon RX 9070 XT` |
| SDPA backends (`flash_sdp_enabled`, `mem_efficient_sdp_enabled`) and a 4K-token bf16 SDPA call | flash (AOTriton) available and faster than math |
| fp8 `torch._scaled_mm` on gfx1201; fp8 text-encoder cast (the 7.14.1-nightly regression) | works, no `hipErrorInvalidValue` |
| MIOpen on vs off for a FLUX.2 VAE decode and an ESRGAN pass (E7) | pick the faster, document |
| ComfyUI `/object_info` reachable headless; Klein 4B fp8 t2i 1024² | image produced; time recorded |
| 50 back-to-back Klein jobs | no HIP launch failure; otherwise enable restart-per-N |
| Same Klein prompt on loom's 7.2.1 venv (Engine B) | A/B timing and pixel sanity |

If torch 2.13 misbehaves, repeat with `2.12.0+rocm10.0.0`, then `2.11.0+rocm10.0.0`, before considering nightlies.

Exit: decision log entries D2–D9 marked *accepted* or revised; `bench/` populated; journal has first rig numbers
and the sanity matrix.

## 2. M1 · Foundation (3–4 weeks)

Build: repo layout (`app/` Tauri shell, `frontend/`, `orchestrator/`, `engine/`, `models/`), the shell with
sidecar supervision + READY handshake + token injection + graceful shutdown; orchestrator with project
workspace, atomic I/O, schema validation, SQLite catalogue index, durable queue (ported from loom
`runner.py`, domain fields stripped), roster + resolver + fetch/verify jobs (ported `weights.py`,
`hf_cache` worker), engine adapter interface with the ComfyUI managed process (graph builders for T2I; no second engine — D28);
OpenAPI → generated TS client; WS events; disk guard; logging;
frame skeleton (07) with Top bar, Rail, Panel, Stage, Inspector, Dock, Banner; Models suite (roster health,
fetch meter); Settings; **build-variant plumbing** (D26: `LOOM2_VARIANT`, roster `variants`, variant-aware
pickers and fetch, SAM 3 licence verified for `open`); recipes carry `loras[]` (D25).

Acceptance (executable): new project → fetch Klein 4B if missing → generate one image from a text prompt
through Engine A → asset + manifest + lineage + thumbnail exist → kill the app mid-job → relaunch resumes
paused with the job queued → cancel kills the engine job tree. Contract tests pass against the pinned
ComfyUI `/object_info`.

## 3. M2 · Catalogue (2–3 weeks) — gate: 08 approved

Virtual grid, group modes (Batch, Lineage, Session, Model, None), filters + FTS, loupe, compare, inspector
tabs, states/ratings/tags, collections (manual + smart), import with metadata parsing, trash/undo, thumbnail
pipeline (pyvips worker), cross-suite verbs wired to stubs.

Acceptance: 08 §9 checklist on 10k synthetic assets + the M1 real assets.

## 4. M3 · Generate, dev-first (3–4 weeks) — gate: 09 approved

**FLUX.2 dev is the only wired model in this milestone (D21).** Prompt tree/JSON/text with the exact-string
preview and the Mistral `[SYSTEM_PROMPT]…[INST]` template; dev variants (GGUF Q4 / fp8mixed per E0), Turbo LoRA
toggle, steps/guidance presets; Draft 960×544 default with Thumb/Full tiers and token/time estimates; batch,
seeds, **Stage** for overnight runs, resident weights across a batch, live previews; references (up to 10);
presets and snippet library; variations/re-run; the LoRA section present but disabled (D25); Klein entries
shown greyed "coming in M5". Upsample as a queued LLM job (optional within the milestone).

Acceptance: 09 §10 checklist on dev; the 10-prompt JSON bench on dev recorded with timings; a staged batch of 8
completes unattended and resumes after a kill.

## 5. M4 · Edit core (5–7 weeks) — gate: 10 approved (editor sections)

Document model + ORA I/O (Python writer/reader, 16-bit layers); PixiJS tiled compositor with layers, groups,
masks, 24 blend modes, adjustment + filter layers (shader preview, Python exact on save); tools V M L W B E
G I C H Z; selections + quick mask; history with dirty-tile snapshots; pen input; export PNG/PSD; Save to
Catalogue with lineage. No AI yet.

Acceptance: 10 §14 items 1, 2, 6, 7.

## 6. M5 · Edit AI (3–4 weeks) — gate: 10 approved (AI section), E8 decided

AI Select (SAM 3, BiRefNet); Inpaint Fill (Klein) / Fill+ / Fill Pro / Fill Hero (dev) / Instruct with region
crop, min working size, paste-back feather, candidate strip (4 Klein / 2 dev, D22); Refine (Klein base/dev)
with exact schedule; Upscale (ESRGAN, tiled refine); Outpaint; recipes stored per layer with re-run. **Because
the Klein graphs now exist, Generate gains the Klein 9B / 4B entries here** (prose flattening, 4-step presets) —
a small item, deferrable to post-MVP if M5 runs long (D21).

Acceptance: 10 §14 items 3, 4, 5; the 5 inpaint bench tasks recorded; Klein t2i from Generate if included.

## 7. M6 · Animate (4–5 weeks) — gate: 11 approved, E4/E5 decided

Inputs/model/length panels; Wan I2V + FLF graphs; LTX keyframe graphs; H3 opt-in behind the licence
confirmation; clip storage (PNG master + proxy); Mediabunny player, filmstrip, compare, onion skin; timeline
dock; frame extraction with lineage; identity advisory (ArcFace FaceSim) as a CPU job.

**Spike E9 (D27) runs inside M6**: interpolate Wan 16 fps bench clips to 24 fps with RIFE (Practical-RIFE)
and FILM; score identity drift, flicker and ghosting against the native 24 fps LTX render of the same task;
decide the export conform policy (interpolate · duplicate · keep native) and record it in 13.

Acceptance: 11 §11 checklist; the 5 i2v bench tasks recorded; E9 verdict logged.

## 8. M7 · MVP hardening (2–3 weeks)

Durability suite (power-loss simulation, corrupt-file recovery, engine crash mid-job, disk hard-stop),
performance passes against the budgets (03 §6), the author's end-to-end click-through of all four suites,
docs refresh (00–14 + journal), ComfyUI/torch pin review, installer script for the engine venv, and **CI
producing both installers** (`full`, `open`) with the `open` build smoke-tested on Klein 4B + Wan 2.2 only.

Exit: all suite acceptance checklists green on the rig; decision log closed for the MVP; a post-MVP backlog
ordered.

## 9. Totals and parallelism

Sequential sum ≈ 24–32 weeks. Realistic overlaps: E1–E3 and E6 run while E0/E4/E5 occupy the GPU; M2 UI can
start on fixtures while M1's engine work finishes; M4 (no GPU) can overlap M3's rig runs. A plausible
calendar is **5–6 months** to the MVP with the rig available throughout.

## 10. Standing rules during execution
- Append-only journal (`90-journal.md`) with real timestamps; same-day spec amendments to the affected doc.
- Each milestone's first task is re-checking the volatile facts list (04 §8) for its models.
- No milestone closes with "rig owed".
- Memory and UI budgets are tested, not assumed; measurements replace the extrapolations in 04 §2 as they land.
