# 06 · System architecture

Builds on 02 (what to keep), 04 (models, convention) and 05 (frontend engine). Status: **implemented M1–M6** (2026-10-04 → 2026-10-06; amendments dated inline, the journal has the measurements); originally proposed 2026-10-04. The engine
decision (§3) is validated by spike E0 in the roadmap before any suite is built on it.

## 1. Overview

```
┌──────────────────────────── Tauri 2 shell (Rust) ─────────────────────────────┐
│  window · sidecar supervision · READY handshake · token injection · dialogs   │
│  graceful /shutdown on exit · single instance · (no pixels through IPC)       │
│                                                                               │
│  ┌──────────────────── WebView2 · React/TS frontend ────────────────────────┐ │
│  │ Suites: Catalogue · Generate · Edit · Animate · Models                   │ │
│  │ PixiJS v8 compositor (Edit) · TanStack Virtual (Catalogue)              │ │
│  │ Mediabunny (Animate) · zustand/immer stores · generated OpenAPI client  │ │
│  └───────────────▲───────────────────────────────▲──────────────────────────┘ │
└──────────────────│ http://127.0.0.1:<port> (bytes, Range) │ WebSocket (events) ─┘
                   │                                        │
┌──────────────────┴────────── Orchestrator (Python, FastAPI/uvicorn) ───────────┐
│ project workspace · catalogue DB (SQLite) · durable queue · lineage · roster   │
│ recipe compiler (typed recipe → engine graph) · media services (pyvips thumbs, │
│ TorchCodec frames, ORA/PSD compose, flatten/crop/paste-back) · disk guard      │
│ token gate · structured logs · per-job logs                                   │
└───────┬──────────────────────────────┬───────────────────────────┬────────────┘
        │ HTTP /prompt + WS            │ stdin/stdout JSON lines   │ argv + manifest
┌───────▼──────────────┐   ┌───────────▼───────────┐   ┌───────────▼─────────────┐
│ Engine A: ComfyUI    │   │ [Engine B: loom torch │   │ Tools: thumbs, SAM 3,  │
│ headless (pinned),   │   │  worker — reference   │   │ BiRefNet, ffmpeg,      │
│ ROCm venv, models/   │   │  only, not built: D28]│   │ hf fetch/verify (CPU)  │
│ via extra_model_paths│   │                       │   │                        │
└──────────────────────┘   └───────────────────────┘   └────────────────────────┘
          ▲ one GPU job at a time, admitted by the queue (VRAM budget 16 GB)
```

Processes: shell (1) · orchestrator (1) · engine (1 resident, restartable) · CPU tool workers (N, short-lived).

## 2. Transport rules (from 05 §5)

| Data | Path |
| --- | --- |
| Commands, metadata, small JSON | Tauri IPC (shell ↔ UI) and REST (UI ↔ orchestrator) |
| Images, masks, latents, thumbnails, video proxies | **loopback HTTP** from the orchestrator: raw octet-stream / PNG / WebP / MP4 with `Range`, `ETag`, `Cache-Control`; never base64. **Measured (E2, 2026-10-05):** `FileResponse.chunk_size` must be raised to 4 MiB (64 KiB gives ~400 MiB/s, 4 MiB gives ~1.3 GiB/s single-stream, ~2 GiB/s with 4 parallel ranges); 8K raw RGBA → WebGPU texture at 782 MiB/s end-to-end; prefer raw over PNG when the GPU is the destination (8K PNG decode costs 0.5 s). Video proxies: h264 **GOP 6** (E6: ≈ 10 ms frame-accurate seeks for any access pattern) |
| Progress, previews, job state, catalogue change events | WebSocket (JSON frames; preview JPEG frames binary with a small header) |
| Uploads from the UI (edited layers, masks, imported files) | `PUT /blobs/{sha256}` streaming body; the orchestrator never buffers whole bodies in Python |
| Inside the webview | `SharedArrayBuffer` (COOP/COEP set by Tauri `app.security.headers`) between brush worker and main thread |
| Between Python processes | `multiprocessing.shared_memory` / `np.memmap` for decode → thumbnail → API |

Security: every mutating endpoint requires `X-Loom-Token` (generated per launch, injected by the shell at
READY); CORS allowlist for the dev origin and `tauri.localhost`; blob paths are content-addressed, output
paths are project-relative and traversal-guarded (loom rules).

## 3. Engine layer — decision D2: ComfyUI as the headless engine

### 3a. Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| **A. ComfyUI headless as a managed engine process** (pinned checkout, own or shared ROCm venv, driven over its HTTP `/prompt` + WebSocket API with API-format graphs built by loom2) | realises "any model that runs in ComfyUI runs in loom2" literally; day-0 model support via Comfy-Org; GGUF (ComfyUI-GGUF), LanPaint, `InpaintModelConditioning`, `WanFirstLastFrameToVideo`, `LTXVAddGuide`, SeedVR2 all exist as nodes; ComfyUI's smart offload already does the TE-unload / model-cache dance loom hand-rolled; ComfyUI 0.19.3 **already runs on this rig on the same torch build** (the stale `D:\comfyui` install, kept only as a model-file backup), so ROCm compatibility is proven; krita-ai-diffusion proves the pattern | graph node names/inputs drift across versions → pin and vendor the version, keep graph builders in one module with contract tests; progress comes as node-level events; GPL-3 (process boundary, personal project; see §3c); a second Python environment to manage |
| B. Own torch workers (loom's approach: vendored BFL lib + diffusers) | proven on this rig for FLUX.2; full control over offload | every new model = a new loader; model-format anchoring on the ComfyUI convention means re-implementing its detection and quant loaders; loom spent months here |
| C. `comfy` core imported as a library in the orchestrator process | no second process | import stability not researched; mixes a 16 GB GPU process with the API server; crashes take the API down |
| D. stable-diffusion.cpp (Vulkan) | zero driver dependency, GGUF native, FLUX.2/Qwen/Wan/inpaint | no node ecosystem, rough edges (Klein-4B VAE on Vulkan), slower than ROCm; keep as fallback |

**Decision:** A is the engine (D2, verified by E0). B is **not built into loom2** (D28, accepted 2026-10-04 after
the E0 A/B: 649 s vs 62 s per image on identical files); loom's vendored worker stays available only as a
reference and for A/B reruns. D post-MVP.

### 3b. How loom2 uses ComfyUI

- **Managed checkout** (decision D15, accepted 2026-10-04): a **fresh clone of
  https://github.com/Comfy-Org/ComfyUI** under `<app>/engine/comfyui/`, pinned to a release tag (**v0.39.0** since 2026-10-07 — `b0b7435`; **v0.38.2** from
  2026-10-04 to 2026-10-07), as a git submodule once loom2 is a git repository. The `D:\comfyui` install
  (0.19.3, 19 minor releases behind) is never used for code — only its `models/` tree is mounted. Upgrading the
  pin is a deliberate milestone task with the contract tests as the gate. Plus a pinned set of custom nodes: `ComfyUI-GGUF` (city96), `LanPaint`, `comfyui-tooling-nodes` (Acly: Load
  Image Base64 / Send Image WebSocket — or loom2 reads outputs via `/view` and the output directory). Optional:
  `ComfyUI-LTXVideo`, `ComfyUI-SeedVR2`.
- **Environment** (D16): a dedicated `engine/.venv` created by **uv** on **Python 3.13** with **torch
  2.13.0+rocm10.0.0** (`[device-all]` extras) from the ROCm 10.0.0 stable index, the pinned ComfyUI's requirements
  under a constraints file that pins torch, optional `triton-windows`, and the pinned custom nodes; `uv.lock`
  committed. The orchestrator runs in its own torch-free `orchestrator/.venv`. loom's 7.2.1 venv is never
  touched (loom rule R103) and serves only as an A/B reference. Exact commands: 12 §1a.
- **Launch**: `python main.py --listen 127.0.0.1 --port <p> --disable-auto-launch --use-pytorch-cross-attention
  --disable-pinned-memory [--lowvram] --output-directory <app state>/engine_out --extra-model-paths-config
  <app>/models/extra_model_paths.yaml` — started and supervised by the orchestrator, restarted on failure or
  every N jobs (HIP launch-failure mitigation), killed with the orchestrator (Job Object).
- **Models**: `extra_model_paths.yaml` mounts (1) loom2's own `models/` root (roster-managed, where fetch jobs
  land files) and (2) the user's existing ComfyUI tree (`D:\comfyui\ComfyUI\models`) read-only. Roster entries
  are resolved to a `folder_key/filename` pair, which is exactly what loader nodes take.
- **Jobs**: the orchestrator's queue admits one engine job at a time. A `Recipe` (typed dataclass) is compiled
  to an API-format graph by `engine/comfy/graphs.py`; `POST /prompt` with a `client_id`; progress/preview/
  executed events arrive on ComfyUI's WebSocket and are re-emitted on loom2's WebSocket with loom2 job ids;
  cancel = `POST /interrupt`; "unload everything" = `POST /free`; outputs are read from the engine output dir
  and **moved into the project** with the loom2 manifest written next to them. Manifest status is truth.
- **Warm model cache**: ComfyUI keeps models resident between prompts; loom2 orders the queue by model family so
  swaps are rare (loom's `warm_group` concept survives as a scheduling hint).
- **Contract tests**: every graph builder is tested against the pinned ComfyUI's `/object_info` (node and input
  names exist, types match) so a version bump fails in CI, not at the user's first click.

### 3c. Licence note

ComfyUI is GPL-3. loom2 drives it as a separate process over HTTP and ships it as a pinned dependency; loom2's
own code (orchestrator, frontend) stays under its own licence. This mirrors how many MIT/Apache frontends use
ComfyUI. For a personal tool this is moot; recorded for a future distribution decision.

### 3d. Engine adapter interface (the ComfyUI engine implements it; sd.cpp would later)

```
Engine.capabilities() -> {families, modes, formats, max_resolution, supports: {inpaint, ref, flf2v, keyframes, lora}}
Engine.estimate(recipe) -> {vram_gb, seconds_hint}
Engine.submit(recipe, job_id) -> handle           # one at a time per engine
Engine.events(handle) -> async iterator of {progress, preview_jpeg, node, log}
Engine.cancel(handle); Engine.free(); Engine.health()
Recipe = T2I | I2I | Inpaint | InstructEdit | Upscale | Segment | Matte | I2V | FLF2V | KeyframeVideo | Thumb
# every generative recipe carries loras: [{model_id, strength}] — empty in MVP, wired post-MVP (D25)
```

Recipes carry roster ids, not file paths; the compiler resolves them. Every recipe records its exact compiled
graph into the job manifest (provenance, loom lesson 7).

## 4. Storage layout

```
<app state>  (%LOCALAPPDATA%/loom2 or <repo>/.loom2_state)
├── app.json                 # last project, recents (≤ 20), settings (models root, HF token, VRAM budget,
│                            #   attention backend, engine flags, "Apache-clean only")
├── models/                  # loom2-managed weights in ComfyUI layout (diffusion_models/, text_encoders/, …)
│   ├── extra_model_paths.yaml   # mounts this root + the user's ComfyUI tree
│   └── roster.index.sqlite      # resolved files, sha256 status, last verify
├── engine_out/              # ComfyUI output dir, shared by every project (the engine outlives project switches);
│                            #   files land under loom2/<job_id>, are moved into the project or deleted when the
│                            #   job ends, and leftovers are reconciled when a project opens (2026-10-06, B6)
├── engine_tmp/ engine_user/ # ComfyUI temp and user dirs
└── logs/

<work disk>/<project>/
├── project.json             # id, name, schema_version, format {aspect, width, height, fps}, size_cap_gb
├── catalogue.sqlite         # assets, tags, ratings, collections, lineage edges, jobs index (rebuildable
│                            #   from manifests — the files remain the truth)
├── assets/<yyyy-mm>/<asset_id>.{png|mp4|json}   # originals + sidecar manifest (prompt JSON, model, seed,
│                            #   params, parents, compiled graph hash, timings)
├── thumbs/<asset_id>/{256,512,1024}.webp
├── documents/<doc_id>.ora   # layered edit documents (16-bit PNG layers, masks, stack.xml + loom2 ext)
├── clips/<clip_id>/{master/%06d.png, proxy.mp4, clip.json}
├── masks/<asset_id>/<mask_id>.png
├── jobs/{queue.json, staged.json, logs/<job_id>.log}
└── _temp/
```

Rules from loom: atomic writes (temp → fsync → rename), `schema_version` on every record, stable ids
(`ast_…`, `doc_…`, `clp_…`, `job_…`), the disk guard polices project cap and disk free, weights never inside
a project.

## 5. Data model (orchestrator)

| Entity | Key fields |
| --- | --- |
| Project | id, name, `format.target` (aspect 16:9, 1920×1080, 24 fps — fixed at creation), `format.default_tier` (thumb / draft / hd / full; default draft — D18, 04 §9), size_cap, created |
| Asset | id, kind (image / video / mask / document-render), path, w, h, frames?, created, **job_id**, **parents[]** (asset ids), suite, model_id, format, seed, prompt_text, prompt_json, params, timings, state (keep / reject / none), rating 0–5, tags[], collection_ids[], thumb_status |
| Document | id, name, w, h, bit_depth, layers (ordered tree: raster / group / adjustment / filter; each with mask?, blend, opacity, visible, locked, bounds), history_ref, source_asset_id?, saved_at |
| Clip | id, start_asset_id, end_asset_id?, prompt, model_id, frames, fps, w, h, master_path, proxy_path, job_id, extracted_asset_ids[] |
| Job | id, recipe (typed), engine, status (staged / queued / running / done / failed / cancelled), progress, vram_estimate, created / started / finished, wall_s, result (asset ids, manifest path), error, log_tail, warm_group, retry_count, resumable |
| LineageEdge | from_asset → to_asset, via_job, kind (generate / inpaint / refine / frame-extract / import / flatten) |
| Collection | id, name, kind (manual / smart), filter_json? |
| ModelEntry | roster fields (04 §1b) + resolved path + health + `variants: [full, open]` |

**Forward compatibility with the Story workspace (D23).** loom's L1–L4 design maps onto this model without
migration: a Collection can become an AssetProfile (ref set) with versions layered on top; Asset lineage already
carries `asset@version`-style provenance; Clips are the Shots & Takes masters (PNG sequence + proxy); the
Project `format.target` is the finalize gate. Nothing in the MVP may hard-code against these extensions
(e.g. no assumption that an asset has exactly one owner suite).

## 6. API surface (sketch; OpenAPI generated → TS client)

```
GET  /health /version /capabilities /settings   PUT /settings
POST /project  /project/open  /project/close    GET /project /projects
GET  /assets?filter=…&sort=…&cursor=…           GET /assets/{id}  PATCH /assets/{id} (state, rating, tags)
GET  /assets/{id}/file  GET /thumbs/{id}/{size}  DELETE /assets/{id}   POST /assets/import (paths)
GET  /lineage/{id}  GET /collections  POST /collections  PATCH /collections/{id}
POST /jobs (recipe)  GET /jobs?status  GET /jobs/{id}  POST /jobs/{id}/cancel  DELETE /jobs/{id}
POST /queue/pause|unpause   GET /queue
GET  /documents (list)  POST /documents (from asset | w,h)  GET/PUT /documents/{id} (stack JSON)  POST /documents/{id}/save (ORA)
GET/PUT /documents/{id}/layers/{lid}/pixels?kind=image|mask&raw=1 (raw RGBA / grey bytes, X-Loom-Width/Height/Channels)
POST /documents/{id}/flatten {to_catalogue}  POST /documents/{id}/export (png; psd is written by the editor via ag-psd)
POST /documents/{id}/compare?w&h (editor composite → delta vs the exact flatten, 10 §14)  GET /documents/{id}/thumbnail
PUT  /documents/{id}/selection?w&h (raw grey; the region the AI recipes repaint)   POST /documents/{id}/close  DELETE /documents/{id}
POST /documents/{id}/ai {recipe: inpaint | i2i | upscale, stage} → jobs; the queue crops the saved composite + selection
     (edit_ai.py: margin, multiples of 16, ≥ min working size), uploads to the engine, runs the E8 graphs, pastes the
     result back as a layer (alpha = feathered mask) in a per-batch "AI" group — `document.changed {added, group}` —
     or, for upscale, as a Catalogue asset with lineage; `segment` (AI Select: BiRefNet subject / SAM 3 text · points · box) writes the
     document's selection instead (`document.changed {selection}`) — GET /documents/{id}/selection returns it (M5 slice 2, 2026-10-06)
POST /documents/{id}/inpaint  /refine  /instruct-edit  (recipes with crop region + paste-back policy)
GET  /clips/{id}  GET /clips/{id}/proxy.mp4 (Range)  GET /clips/{id}/frames/{n}.png  POST /clips/{id}/extract
GET  /models (roster + health)  POST /models/fetch  /models/{id}/verify  PUT /models/root  POST /models/scan
GET  /engine (status)  POST /engine/restart  /engine/free
PUT  /blobs/{sha256}   GET /blobs/{sha256}
WS   /events  (job.*, asset.*, engine.*, disk.*, model.*)
```

## 7. Key flows

**Generate (t2i):** UI builds `T2I{model_id, prompt_json|text, w, h, seed[], steps, guidance, refs[]}` →
`POST /jobs` → queue admits (VRAM estimate ≤ budget) → compile graph (dev: raw JSON inside the Mistral
template; Klein: flattened prose) → engine → previews over WS → outputs moved to `assets/`, manifest + lineage
written, thumbnails queued (CPU worker) → `asset.created` event → Catalogue updates.

**Edit → AI inpaint:** UI composites the document's visible layers below the target into a flattened PNG for
the selected crop region (padding + context margin), uploads region PNG + mask via `PUT /blobs` → `POST
/documents/{id}/inpaint {blob, mask_blob, region, model, mode: fill|fill_plus|fill_pro|instruct, prompt,
denoise}` → engine (Klein+ICM / LanPaint / FLUX.1 Fill / Qwen-Edit) at the region's native resolution,
upscaled tile if the region is small → orchestrator pastes back with seam feathering → returns a new layer
(PNG + mask) → UI inserts it above the target; the ORA save records the recipe in the layer's metadata.

**Animate:** `I2V{start_asset, end_asset?, prompt, model (wan|ltx|h3), frames, fps, w, h, seed}` → engine →
MP4 + PNG sequence written to `clips/` (master = PNG sequence, proxy = MP4) → Mediabunny scrubs the proxy;
frame extraction creates assets with lineage `frame-extract` from the clip.

**Durability:** kill the app anywhere → `queue.json` reloads paused with running jobs re-queued (or failed
if non-resumable and crashed); the engine process is reaped by the Job Object; `engine_out/` leftovers are
reconciled by manifest status.

## 8. Frontend structure

```
frontend/
├── shell/            # tauri adapters (dialogs, window, sidecar status); the only place @tauri-apps/api is imported
├── api/              # generated OpenAPI client + WS client + blob helpers
├── store/            # zustand slices: session, project, catalogue, jobs, settings, per-suite UI state (persisted layout)
├── frame/            # top bar, rail, panel, stage, inspector, dock, banners, shortcuts (07)
├── suites/
│   ├── catalogue/    # virtual grid, groups, filters, loupe, compare (08)
│   ├── generate/     # prompt tree, params, batch, refs (09)
│   ├── edit/         # document model, PixiJS compositor, tools, layers panel, history (10)
│   ├── animate/      # start/end pickers, timeline, scrubber, extract (11)
│   └── models/       # roster, health, fetch meters
└── engine-ui/        # shared: job dock, progress, preview tiles, parameter controls driven by /capabilities
```

Edit-suite engine (05): PixiJS v8 WebGPU with WebGL2 fallback, 2048² tiles, worker brush at ≤2K preview,
256² dirty-tile undo, ORA in/out, ag-psd export.

## 9. Observability and testing

- Structured JSON logs (orchestrator), per-job log files with the engine's node-level output, timings bracketed
  by `torch.cuda.synchronize()` in Engine B and taken from ComfyUI's execution events in Engine A.
- Test tiers: unit (recipe compiler, roster resolver, workspace I/O), contract (graph builders vs pinned
  `/object_info`), integration without GPU (fake engine), **rig acceptance** (executable scripts per suite,
  results appended to the journal). "Done" requires the rig run.

## 10. Risks specific to this architecture

| Risk | Mitigation |
| --- | --- |
| ComfyUI graph API drift | pinned version, contract tests, builders isolated in one module, upgrade as a deliberate milestone |
| Engine process instability on ROCm (HIP launch failures after many runs) | restart-per-N-jobs, health probe, automatic re-queue of the interrupted job |
| **GPU driver TDR under VRAM pressure** (2026-10-05: consecutive Klein inpaints streamed the model from RAM, a stalled kernel exceeded Windows' 2 s default and `amdkmdag.sys` reset; the engine kept answering HTTP with a dead GPU) | Windows `TdrDelay`/`TdrDdiDelay` = 60 s (user, admin + reboot); the queue frees ComfyUI's cached outputs after every edit job (`/free`, weights stay resident); a **stall watchdog** (`engine.stall_timeout_s`, 420 s without an engine event) fails the job, restarts the engine and pauses the queue; the engine launches with `--reserve-vram` (`engine.reserve_vram_gb`, 1.5) so the desktop and the editor's WebGPU canvas keep headroom; inpaint engine images are capped at ≈ 1 MP (`max_pixels`) and the AI panel shows the size it will send |
| Two Python environments | both created by `uv` from committed `pyproject.toml` + `uv.lock`; a `setup.ps1` recreates them; interpreter paths stored in loom2 settings, nothing on PATH |
| ROCm 10.0 on Windows is young (Aug 2026) | E0 sanity matrix first (12 §1a); fallbacks torch 2.12/2.11 on the same index; loom's venv for A/B |
| Progress granularity | node-level progress + sampler step callbacks (ComfyUI emits `progress` per step) |
| Output hand-off via files | content-addressed move + manifest; `/view` as fallback; Acly's binary WS nodes if latency matters |
| Spike E0 fails (performance or stability vs loom's worker) | Engine B stays the FLUX.2 path; ComfyUI used only for video/inpaint nodes; re-evaluate option C |

## 11. Build variants (D26)

`LOOM2_VARIANT = full | open` is set at build time and surfaced read-only in Settings. It filters the roster
(`variants` field), the model pickers, the fetch catalogue and the licence-confirmation toggles; `open` hides
every non-Apache/MIT entry and defaults Generate to Klein 4B. Both variants share one codebase and one engine
checkout; CI builds two installers (`loom2-full-<ver>.exe`, `loom2-open-<ver>.exe`). The variant is recorded in
every job manifest. **Implemented 2026-10-06 (M7 slice 4):** the shell bakes `LOOM2_VARIANT` in at compile time
(`option_env!`) and hands it to the orchestrator; `.github/workflows/ci.yml` runs the offline suite and the frontend build for
both variants on every push / PR and builds the two installers on pushes to main and tags (`loom2-full-*`, `loom2-open-*`);
the runners have no GPU, so the `open` smoke test is the offline suite under `LOOM2_VARIANT=open`. `scripts/setup.ps1`
recreates both venvs, the frontend, the engine checkout and the FaceSim weights on a machine.
