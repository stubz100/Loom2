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
| **E1** | PixiJS v8 WebGPU compositor inside Tauri 2 on this rig; WebGL2 fallback toggle | 60 fps, 6 × 4K layers, 3 advanced blend modes, masks — **PASS 2026-10-05 (Edge and Tauri/WebView2)**: 3.0 ms median / 4.1 ms p95 per composite on WebGPU measured into an offscreen target, ≤ 1 ms on WebGL2; rAF fps shows 30 only because the monitor runs at 29 Hz | D3 renderer (05) |
| **E2** | Loopback throughput: FastAPI streams a 200 MB latent + an 8K PNG; UI uploads a 64 MB mask via `PUT /blobs` | ≥ 500 MB/s into a GPU texture — **PASS 2026-10-05**: 782 MiB/s end-to-end (8K raw → WebGPU texture), 1 276 MiB/s single fetch, 1 957 MiB/s with 4 ranges, after raising `FileResponse.chunk_size` to 4 MiB (64 KiB gave 329–422 MiB/s) | D4 transport |
| **E3** | Worker brush (FastMask pattern) with `pointerrawupdate` + predicted events, **mouse-driven** (D19: no pen yet; pressure/Delegated Ink implemented, untested) | event→commit median ≤ 1.5 frames, p95 ≤ 2 (the rAF floor) at 2K preview; no dropped dabs at fast mouse strokes — **PASS 2026-10-05** (1.5 / 1.95 frames, 0 of 4 800 dropped at 250 events/s) | Edit feasibility |
| **E4** | Wan 2.2 I2V-A14B GGUF Q5_K_M + umT5 fp8 + Lightning via ComfyUI on the rig; FLF with `WanFirstLastFrameToVideo` | 81 f @ 480p completes; time and peak VRAM recorded; identity visually acceptable — **PASS 2026-10-05**: 5/5 clips, 312–366 s each at 832×480 × 81 f (Lightning 2+2, CFG 1), ≈ 9 GB resident after the run (peak not captured); identity held in all five, FLF reached the end pose; VAE decode + encode = 54 % of the time (Q18); camera-move adherence weak. **E4b done**: 4+4 Lightning steps = no gain (424–550 s); undistilled high expert at CFG 3.5 + distilled low ("motion", 495 s) = real character action → presets Draft / Motion; camera moves need VACE or camera LoRAs post-MVP. **E4c (D30)**: Comfy-Org fp8-scaled experts 236 s vs 322 s per clip (sampling 60 vs 106 s) → fp8 is the D8 recipe, GGUF pair deleted | D8 primary i2v — **accepted** |
| **E5** | LTX-2.3 distilled via ComfyUI (GGUF Q4_K_M, then the Kijai fp8 transformer streamed) + Gemma-3 fp8; FLF via `LTXVAddGuide` at −1 | 121 f completes; time recorded — **PASS 2026-10-05**: both tasks at 1024×576 × 121 f; GGUF 649–715 s (68–81 s/it), **fp8 141 s (4.7 s/it)**; motion and prompt adherence better than Wan, identity softer; the audio VAE is required by core 0.38 (fetched) | D9 secondary i2v — **accepted** (fp8 only) |
| **E6** | Mediabunny `CanvasSink` scrub on a 121-frame MP4; exact seek on the backend (PyAV; TorchCodec optional) | every frame reachable, step < 50 ms — **PASS 2026-10-05**: 0 wrong frames in 3 × 222 seeks; GOP 24 random 17.8 ms, **GOP 6 ≈ 10 ms** for every pattern (proxy policy), intra ≈ 7.5 ms; backend PyAV 6–15 ms | video stack |
| **E7** | MIOpen on/off for VAE decode and ESRGAN on gfx1201 under ComfyUI | pick the faster, document — **DONE 2026-10-05: MIOpen off** (VAE decode 0.9 s Draft / 5.6 s Full; MIOpen costs 12–16 s search per new shape, wins 0.7 s warm); ESRGAN deferred until an upscaler is in the roster | runtime policy (04 §2, D13) |
| **E8** | Inpaint quality bake-off on the bench tasks: Klein+ICM, Klein base+ICM, Klein+LanPaint, dev+LanPaint, FLUX.1 Fill (official file), Qwen-Image-Edit 2509 | ranked results with timings — **DONE 2026-10-05** (run 3: 4 tasks × 6 methods, 0 errors): Klein+LanPaint 22–28 s is the best fast method; Klein ICM 18–33 s conservative; dev+LanPaint 255–281 s is the hero tier and the only removal; FLUX.1 Fill 76–82 s dropped; Qwen-Edit 475 s (≈ 95 s warm) deferred. **E8b done 2026-10-05**: Klein removes with a neutralised-hole reference (10 s) or LanPaint Prompt First (21 s) — Q17 resolved; task 03 in M5 | D7 inpaint stack — **accepted with amendments** |

**E0 status — closed PASS on 2026-10-04** (journal 18:44–20:40): environment and engine verified; dev fp8mixed
**62 s warm / 107 s cold** for 20 steps at 960×544 (loom's worker: 649 s); GGUF Q4 ≈ 11× slower (kept as a
VRAM-saving option only); Turbo 8-step ≈ 40–68 s; 57 engine executions incl. a 50-job loop with 0 errors; one
node-drift bug patched (`engine/patches/`). The Klein 9B and Klein-inpaint sub-items moved to M5/E8 per D21.
Follow-ups: Q15 (bimodal sampling speed under sustained load), E7 (MIOpen on real VAE decode — the sanity conv
favoured MIOpen on), encoder stays on the GPU (CPU encode ≈ 170 s per new prompt).

**E1 / E2 / E3 / E6 status — closed PASS on 2026-10-05** (journal 08:01–08:15), measured in Edge 154 and inside
the Tauri 2 shell (WebView2, first Rust build 54 s): compositor 3.0 ms per 6×4K composite on WebGPU; loopback
695–782 MiB/s into a WebGPU texture with 4 MiB response chunks; brush 0 dropped dabs at the rAF floor;
frame-accurate scrubbing at ≈ 10 ms with GOP-6 proxies. Harness: `frontend/src/spikes/`, server
`orchestrator/spikes/e2_loopback.py`, results `orchestrator/spikes/out/*.jsonl` (gitignored). Monitor runs at
29 Hz — author to switch to 60/75 Hz before any UI feel judgement.

**E4 / E5 / E7 / E8 status — closed on 2026-10-05** (journal 11:50–13:11): the model spikes are done and D7,
D8, D9 are accepted — inpaint on Klein 9B + LanPaint (Remove via a neutralised-hole reference, Fill Hero on
dev), Wan 2.2 Lightning as the identity-safe i2v (Draft ≈ 315 s / Motion ≈ 495 s per 5 s clip at 832×480),
LTX-2.3 fp8 as the fast beat-driven i2v (141 s per 5 s at 1024×576). Struck: FLUX.1 Fill, Qwen-Image-Edit
(post-MVP), Klein base for inpaint, 4 + 4 Lightning, and every GGUF video model on this card (fp8 streamed
from RAM is 5–15× faster). Drivers: `engine/spikes/e4_wan_i2v.py`, `e5_ltx_i2v.py`, `e8_inpaint.py`; sheets
`e8_sheets.py`, `i2v_sheets.py`; results under `engine/spikes/out/` (gitignored, reproducible from the frozen
bench inputs and seeds). **M0 is closed.** Carried forward: Q15 (sampling-speed telemetry, M3), Q18 (Wan VAE
time, M6), E9 (fps conform, M6), inpaint bench task 03 (M5). Nothing gates M1.

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

**M1 status 2026-10-05** (journal 13:49, 14:11): orchestrator core + rig acceptance **20/20**
(`scripts/m1_acceptance.py`); Tauri shell supervises the orchestrator sidecar (READY handshake, token via
`backend_info`, graceful `/shutdown` on close, kill-on-close Job Object, single instance); frame skeleton (07)
with Top bar · Banner · Rail · Panel · Strip · Stage · Inspector · Dock · Toasts, global keys, Settings modal,
project dialogs, Models suite (roster health, fetch meter, verify, engine panel); OpenAPI → `src/api/schema.d.ts`
+ typed client; variant surfaced read-only. **Open in M1:** OS folder picker for project dialogs (Tauri dialog
plugin), response models in the OpenAPI schema (responses are plain dicts today), `--project` restore of the
last project at launch, a `loom2 dev` task that starts Vite + shell + orchestrator with one command.

## 3. M2 · Catalogue (2–3 weeks) — gate: 08 approved

Virtual grid, group modes (Batch, Lineage, Session, Model, None), filters + FTS, loupe, compare, inspector
tabs, states/ratings/tags, collections (manual + smart), import with metadata parsing, trash/undo, thumbnail
pipeline (pyvips worker), cross-suite verbs wired to stubs.

Acceptance: 08 §9 checklist on 10k synthetic assets + the M1 real assets.

**M2 status 2026-10-05** (journal 15:22): backend — `AssetQuery` filters, FTS5 search over prompt text /
JSON / tags, server-side group headers (batch, lineage root, session, model) and smart-folder counts, lineage
roots and per-launch session ids on every asset, trash / restore / purge, bulk edits, collections (manual +
smart, freeze on convert), ComfyUI / A1111 PNG metadata on import, stale-index rebuild; 22 offline tests. Frontend
— `suites/catalogue`: Library / Filters / Collections / Import panel, strip (group, state, sort, bulk Keep /
Reject / tag / collection / trash, zoom, fit/fill), virtualised grid with group headers and keyboard-by-row,
loupe (zoom/pan, prev/next, facts), compare (2-up / 4-up, locked zoom/pan, wipe, difference, swap), inspector
Info / Params / Lineage / Tags, two-step delete with Undo, live `asset.*` events. On the 10k synthetic project:
groups 60 ms, page 50 ms, counts 60 ms, FTS 40 ms. **Open in M2:** sticky group headers, drag-to-add
collections, date-range filter, lineage chain layout (left → right), video hover-scrub (needs clips, M6),
document tiles (M4), duplicate hints, disk-guard purge, an interactive scroll-FPS pass on the rig.

## 4. M3 · Generate, dev-first (3–4 weeks) — gate: 09 approved

**FLUX.2 dev is the only wired model in this milestone (D21).** Prompt tree/JSON/text with the exact-string
preview and the Mistral `[SYSTEM_PROMPT]…[INST]` template; dev variants (GGUF Q4 / fp8mixed per E0), Turbo LoRA
toggle, steps/guidance presets; Draft 960×544 default with Thumb/Full tiers and token/time estimates; batch,
seeds, **Stage** for overnight runs, resident weights across a batch, live previews; references (up to 10);
presets and snippet library; variations/re-run; the LoRA section present but disabled (D25); Klein entries
shown greyed "coming in M5". Upsample as a queued LLM job (optional within the milestone).

Acceptance: 09 §10 checklist on dev; the 10-prompt JSON bench on dev recorded with timings; a staged batch of 8
completes unattended and resumes after a kill.

**M3 status 2026-10-05** (journal 16:08): dev fp8mixed wired end to end — Prompt tree / JSON / text with the
exact serialisation preview and word/token counter, Model (dev + Klein entries greyed "coming in M5", sampling
controls with disabled reasons, Turbo, seed modes, LoRA slots disabled), Size & Batch (tiers, aspects, ×16
snapping, count, ETA + VRAM fit), References (drop / `R`, downscale, dev chain through `ReferenceLatent`),
Presets + snippets, Stage / release, results on the Catalogue grid with interim preview tiles, Catalogue verbs
(reference, re-run, variations, load into panel). Bench: 10/10 dev Turbo images, mean 45 s.
Acceptance `scripts/m3_acceptance.py`: 17/17.
**Open in M3:** Upsample LLM pass (optional), adherence scoring of the bench by eye, "fetch then run" automation,
diff-against-panel in the Params tab.

## 5. M4 · Edit core (5–7 weeks) — gate: 10 approved (editor sections)

Document model + ORA I/O (Python writer/reader, 16-bit layers); PixiJS tiled compositor with layers, groups,
masks, 24 blend modes, adjustment + filter layers (shader preview, Python exact on save); tools V M L W B E
G I C H Z; selections + quick mask; history with dirty-tile snapshots; pen input; export PNG/PSD; Save to
Catalogue with lineage. No AI yet.

Acceptance: 10 §14 items 1, 2, 6, 7.

**M4 status 2026-10-05** (journal 18:44): backend — pydantic document model, ORA writer/reader (8-bit layers,
masks, stack.xml + `loom2.json`), exact numpy compositor (24 modes, masks, groups, clip, adjustments, filters),
documents API with raw RGBA layer transfer and a compare endpoint; frontend — PixiJS editor with layers, groups,
masks, **exact W3C blend shaders** (Pixi's own set measured and replaced), clip, render-texture passes for
masked layers and isolated groups, tools V M L W B E G I C H Z, selections + quick mask, tile-snapshot history,
Layers/Properties/History/Info inspector, Save / Save to Catalogue / PNG / PSD, `E` from the Catalogue.
**Acceptance `scripts/m4_acceptance.py` 12/12**: item 1 (preview vs exact: p99 3/255 over a 33-layer stack of
every blend mode plus 8 adjustment/filter layers, ≤ 1 per feature and per adjustment/filter type), item 6 (ORA
round trip lossless; PSD written — opening it in Photoshop/Krita is a manual check), item 7 (lineage +
`has_document`). Item 2's undo/redo is in; the tablet latency half waits for a pen (D19). Adjustment and filter
previews landed (journal 18:56). Remaining in M4: free transform (Ctrl+T), gradient fill, marching ants, and an
on-demand render loop (the ticker currently re-renders every frame, which a blur layer makes costly).

## 6. M5 · Edit AI (3–4 weeks) — gate: 10 approved (AI section), E8 decided

AI Select (SAM 3, BiRefNet); Inpaint Fill (Klein + LanPaint) / Fill-Match (Klein ICM) / Fill Hero (dev + LanPaint; Fill Pro and Instruct dropped by E8) with region
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
- **Mouse-first UI (D32)**: a new action is a registry command with an icon/button or a right-click menu entry
  before it gets a key; no key-only or gesture-only actions ship (07 §3c).
- Each milestone's first task is re-checking the volatile facts list (04 §8) for its models.
- No milestone closes with "rig owed".
- Memory and UI budgets are tested, not assumed; measurements replace the extrapolations in 04 §2 as they land.
