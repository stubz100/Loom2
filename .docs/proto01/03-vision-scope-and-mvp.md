# 03 · loom2 — vision, principles, MVP scope

## 1. Vision

loom2 is a **local AI image and video studio for storyboard pre-production**, running entirely on one
Windows machine with an AMD RX 9070 XT (16 GB). It generates starting images with FLUX.2, refines and
repaints them in a Photoshop-like layered editor, animates them into short clips, and keeps everything in a
browsable, groupable catalogue with full provenance. The narrative layers of loom (story bible, shots, flow
graph, episode export) are not abandoned; they return later as workspaces **on top of** this studio instead
of being the skeleton it is built around.

The two things loom2 changes on purpose:

1. **One model-sourcing convention.** Every weight loom2 can load comes from a single, declared convention
   with provenance and checksums, so "which repo, which quant, which key layout" is never a per-model
   adventure again. The candidate anchors (ComfyUI model layout vs a single quantiser such as Unsloth) are
   evaluated in `04-model-strategy.md`.
2. **A real editing surface.** Generation results become layers in a document, not rows in a job table. The
   editor has layers, groups, masks, blend modes, adjustment and filter layers, pressure brushes, history,
   and AI inpaint / refine as first-class operations. Engine decision: `05-frontend-engine-evaluation.md`.

## 2. Principles (design tenets)

| # | Tenet | Consequence |
| --- | --- | --- |
| T1 | **16 GB-first.** Every pipeline is designed for offload on 16 GB ROCm, and is measured on the rig before it is called done. | Two-phase TE/transformer loading, warm workers, quantised weights, `torch.cuda.synchronize()` around every timing. No CUDA-only kernels. |
| T2 | **One sourcing convention, declared provenance.** | A single `models/` layout + a roster with repo, file, sha256, licence, "used by". Presence probe → explicit, resumable, verified fetch as a queue job. |
| T3 | **Suites, not stages.** Catalogue · Generate · Edit · Animate are self-contained workspaces sharing one asset store and one job queue. | Each suite has its own UI document approved before implementation (07–11). |
| T4 | **Documents, not jobs.** The Edit suite works on a layered document (ORA); a generation result is a layer or an asset, never only a job output. | Server-side flatten/crop/paste-back exist as backend operations with lineage. |
| T5 | **Pixels never cross the shell's IPC.** | Python → loopback HTTP (raw bytes, Range) → GPU texture; WebSocket for events; Tauri IPC for commands only. |
| T6 | **Durable by default.** | Durable queue that resumes paused, atomic writes, schema versions, lineage stamped at write time, disk guard. (loom rules, see 02 §2.) |
| T7 | **Design the frame before the first control.** | `07-ui-frame.md` fixes the shell; suite docs place every control in a named region. No hover-only affordances, no native prompts, type ≥ 12 px. |
| T8 | **Display == reality.** | Every default the UI shows is exactly what the worker runs; parameters come from one catalogue served by the backend. |
| T9 | **Advisory, never blocking.** | Meters, duplicate hints and quality scores inform; they never stop a generation or a save. |
| T10 | **Standard formats over bespoke ones.** | ORA project files, PSD export, PNG with embedded metadata, MP4 proxies + PNG-sequence masters, GGUF/safetensors under upstream tensor names. |
| T11 | **Keep the engine replaceable.** | Model execution sits behind an adapter contract; the first engine is the proven loom FLUX.2 worker, and 04 decides whether a shared engine (ComfyUI-core, diffusers, sd.cpp) replaces it. |

## 3. MVP scope

The MVP is **four suites on one foundation**, each gated by an executable acceptance run on the rig.

### 3a. Foundation (F)
- Tauri 2 shell + React/TS frontend + Python FastAPI sidecar, loopback HTTP + WebSocket, token-gated.
- Project workspace on the work disk: `project.json`, `assets/`, `documents/`, `clips/`, `jobs/`,
  `lineage/`, thumbnails, SQLite catalogue index.
- Durable queue (resume paused, cancel = tree kill, VRAM admission, OOM retry, warm workers).
- Models roster + resolver + fetch/verify jobs, Models page.
- **Two build variants** from day one (D26): `full` and `open` (Apache/MIT weights only), as a roster filter +
  build flag, with both installers produced by CI.
- Disk guard, logging, graceful shutdown handshake.

### 3b. Suite A — Generate (FLUX.2 t2i)  *(user target a)*
- **FLUX.2 dev first** (D21): the default and first-built model, with JSON prompting through the Mistral
  template; Klein 4B / 9B tiers join later (prose-flattened prompt). Sampling presets per variant.
- **Structured JSON prompting** as a form tree and as raw JSON, serialised into the prompt; text mode too.
- Batch of N with seed control; resolution presets bound to the project format; optional reference images
  (FLUX.2 multi-reference).
- Warm worker keeps the model resident across a batch; progress + previews stream to the UI.
- Results land in the Catalogue with full parameters; "re-run with changes" from any asset.
- **Acceptance:** JSON tree → image where camera, lighting, palette and subject pose are visibly honoured;
  Klein and dev both run on the rig; timings recorded in the journal.

### 3c. Suite B — Edit (layered inpaint / refine)  *(user target b)*
- Layered document: raster layers, groups, layer masks, opacity, Photoshop blend modes, adjustment layers
  (levels, curves, HSL, colour balance), filter layers (blur, sharpen, noise), transform.
- Selections: brush, lasso, polygon, rectangle/ellipse, magic wand, **AI segment** (SAM 3 / BiRefNet) →
  mask; feather/expand/contract/invert.
- **AI inpaint** on a selection with the model chosen in 04 (primary + fallback), including crop-region
  hi-res inpaint with paste-back and seam blending; result as a new layer with its mask.
- **i2i refine** on a layer or the flattened document (FLUX.2 img2img with the corrected strength schedule).
- History (undo/redo), ORA save/load, PSD export, PNG export with metadata; mouse-first input, pen-ready (D19).
- **Acceptance:** open a catalogue image → mask a region → inpaint → refine → export PSD that opens in
  Photoshop/Krita with layers intact.

### 3d. Suite C — Animate (image-to-video)  *(user target c)*
- Start image (+ prompt) or start + end image → 3–5 s clip with the model chosen in 04.
- Resolution/length presets within 16 GB; progress; MP4 proxy + PNG-sequence master.
- Scrub with frame-accurate stepping, side-by-side comparison, extract frames to the Catalogue, send a frame
  to Edit.
- **Acceptance:** a storyboard frame animates with recognisable character identity; start+end interpolation
  reaches the end image; a frame extracted from the clip round-trips to Edit.

### 3e. Suite D — Catalogue
- Virtualised grid over thousands of assets, thumbnail pyramid, metadata index.
- Grouping (batch, lineage chain, session, model, collection), filters, sort, keep/reject, rating, tags.
- Loupe + compare, lineage inspector, parameters inspector with "reuse".
- Import external images/videos; collections and smart collections; send-to-suite verbs.

## 4. Non-goals for the MVP

- LoRA training and dataset tooling (loom P2) — returns post-MVP via ai-toolkit on the same queue. LoRA
  **slots** are designed into the data model and reserved in the UI now (D25) but not implemented in MVP.
- StoryBible / AssetProfile versions / coverage matrix / readiness meter / captions.
- Narrative graph, shots & takes timeline, episode export, TTS / lip-sync, 3D (TRELLIS), engine export.
- Muse assistant (SLM/VLM) — every AI call remains a queued job later.
- Multi-user, cloud, multi-GPU, a CUDA code path, mobile.
- Identity swap / face restore from research-licensed weights.

## 5. Post-MVP (committed order, D23/D25)

1. **Story workspace, adopted as-is from loom's design** (kb-storyboard01 L1–L4 and the P3–P5 specs: StoryBible,
   AssetProfiles with versions, Shots & Takes, flow graph, episode export), followed by a **refining session**
   once it is on loom2's foundation. Pointer and adoption notes: 14.
2. **LoRA slots live** (D25) and LoRA training via ai-toolkit (proven on this rig) from a collection.
3. Klein tiers in Generate if they slipped past MVP (D21).
4. Video extension, keyframe chains, pose/VACE control, lip-sync; fps conform per spike E9.
5. SeedVR2 / tiled upscale as Edit actions; Muse prompt drafting as queued jobs.

## 6. Success measures for the MVP

| Measure | Target |
| --- | --- |
| Rig acceptance runs | all four suites green on the RX 9070 XT, recorded with timings |
| Model sourcing | 100 % of loadable weights listed in the roster with sha256 and licence; zero bespoke key remaps outside the engine |
| Edit suite | 6 × 4K layers composited at 60 fps; pen stroke ≤ 1 frame visible lag at 2K preview |
| Catalogue | 10 000 assets scroll smoothly; first paint < 1 s on a warm index |
| Durability | kill the app mid-job → relaunch resumes paused with the job queued, no corrupt records |
| Provenance | every asset answers: model, quant, seed, prompt (JSON), parents, suite, timestamp |
