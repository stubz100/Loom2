# 06 · Building ArtCraft from the ground up — implementation plan

The question this document answers: *if the ArtCraft product ([01](01-overview.md)) were started today from an empty repository,
how should it be built?* It keeps what ArtCraft got right ([02](02-backend-architecture.md)–[05](05-engineering-practices.md)),
designs out the debt it accumulated, and orders the work so that risk is retired early and every phase ships something usable.
It is a plan for *ArtCraft's* scope (multi-provider image/video/audio/3D creation with 2D, 3D and timeline surfaces); what loom2
should take from it is in [07](07-loom2-comparison.md).

## 1. Decisions to make before the first line of code

| # | Decision | Recommendation | Why |
| --- | --- | --- | --- |
| 1 | Where does inference run? | **Behind one engine/provider interface from day one**, with cloud providers first and a local engine (ComfyUI) as a planned implementation | ArtCraft's own roadmap now wants to "remove dependence on hosted services"; retrofitting locality into a token/CDN-centred design is the expensive path |
| 2 | Where does the user's work live? | **Local-first**: projects, media and documents on disk, content-addressed, with an index; cloud sync optional per project | ArtCraft's library, scenes and boards live on its backend; its video-editor projects are not even reopened. Local-first makes offline, export and provenance trivial |
| 3 | Shell | **Tauri 2 + Rust core** | small binaries, a real backend language for jobs/IO/credentials; ArtCraft proves it at scale. Keep pixels off IPC (stream large files through a scoped custom protocol or loopback HTTP) |
| 4 | Frontend | **React + TypeScript + Vite, one state library (Zustand)**, Nx or pnpm workspaces with editor libraries | ArtCraft ended with Zustand + signals + window events + globals; pick one bus |
| 5 | IPC contract | **Generated** TypeScript bindings for commands and events (e.g. `tauri-specta`), checked in, verified in CI | ArtCraft hand-mirrors Rust enums in TS and mixes event naming styles |
| 6 | Licence | decide before accepting contributions | ArtCraft's unfinished "fair source" text is a liability for users and contributors |
| 7 | Business surface | credits/billing as a **plugin to the provider layer**, not woven into commands | ArtCraft's billing errors, modals and credit refreshes are threaded through many layers |

## 2. Principles (each answers a specific ArtCraft lesson)

1. **Every job is a durable row before it is anything else** — written at submit with the provider's job id, joined back on every
   restart (ArtCraft got this right).
2. **Persist results before announcing them** — download/ingest, then update the row, then emit events (ArtCraft got this right).
3. **One scheduler, many drivers.** A single supervised job engine with per-provider drivers, back-off, cancellation and clean
   shutdown — not eight independent sleep loops.
4. **Models are data.** Capability descriptors (inputs, limits, options, defaults, cost model) are served to the UI; request
   building is pure and tested; the UI shows only what a model supports.
5. **Forward compatible by construction.** Stored and wire enums never rename values, carry `Unknown(String)`; requests pass unknown
   fields through; ids are prefixed tokens.
6. **Migrations, not resets.** Append-only schema migrations with tests; never "bump the file name and start empty".
7. **Editors are libraries behind adapters.** No IPC inside an editor; the host injects transport, storage and UI slots.
8. **Undo is a command log, not a snapshot of the world.** Command pattern with coalescing; snapshots only for small state.
9. **Secure by default.** Strict CSP, asset protocol scoped to the library, secrets in the OS keyring, never returned to the UI or
   logged.
10. **Every PR is checked.** Lint, typecheck, unit tests, contract freshness and a smoke run on every pull request.
11. **Docs are versioned with the code.** Per-subsystem `AGENTS.md` with add-X recipes and footguns, dated and re-verified at each
    milestone; decisions in a log.

## 3. Target architecture

```
┌──────────────────────────────────── Desktop app (Tauri 2) ─────────────────────────────────────┐
│ WebView (React/TS)                                                                               │
│  app shell: workspace tabs · command registry · job dock · library · settings · notifications    │
│  editor libs (no IPC):  canvas2d · stage3d · timeline · boards · prompt/reference deck           │
│  host adapters ──► generated bindings (commands + events)                                        │
│────────────────────────────────────────── IPC (small JSON) ───────────────────────────────────── │
│ Rust core                                                                                        │
│  ┌ commands (one per file, uniform envelope) ┐  ┌ event hub (typed, versioned) ┐                │
│  ├ job engine: queue · scheduler · drivers · back-off · cancellation · restart reconciliation   │
│  ├ provider registry: model descriptors · planners (pure) · cost/ETA estimators · finalizers    │
│  ├ media store: content-addressed files · SQLite index (+FTS) · thumbnails · lineage · import   │
│  ├ documents: canvas (layered) · scene (3D) · timeline · board — files on disk, schema-versioned│
│  ├ accounts & secrets (OS keyring) · billing plugin · settings · telemetry (opt-in)             │
│  └ media protocol: scoped `media://` (Range, ETag) for pixels/video — never base64 over IPC     │
└───────────┬───────────────────────────┬───────────────────────────────┬─────────────────────────┘
            ▼                           ▼                               ▼
   hosted API (own models,     third-party official APIs        local engine (ComfyUI or
   credits, optional sync)     (fal, xAI, World Labs…)          sd.cpp) — later phase
```

### 3a. Provider layer (keep ArtCraft's router design, generalise it)

```
GenerationIntent { modality, model_id, inputs: [MediaRef], options: {aspect, resolution, duration, batch, quality, …},
                   mismatch_policy: Upgrade | Downgrade | Error, idempotency_key, origin: {surface, subscriber_id, payload} }
   │ registry.plan(intent)                       — pure: resolve model descriptor, snap options, validate, price, ETA
   ▼
Plan { provider, model, request_state, unresolved_inputs, estimate: {cost, seconds, vram?, watermark, refundable} }
   │ finalize(plan, ctx)                         — I/O: upload/re-host inputs to where the provider can read them
   ▼
ProviderRequest  ──submit──►  JobHandle { provider_job_id, poll_url | ws_topic, outbound_payload }   (stored in the job row)
```

- **Model descriptor** (data, versioned, served to the UI): id, family, provider bindings, input slots (kind, required, min/max
  count, max total duration), options with allowed values and defaults, prompt limits, cost model, capability tags, licence,
  `disabled` with reason. ArtCraft's `GET /v1/omni_gen/models` and `OmniGenVideoModelDetails` are the template.
- **Drivers** implement `submit`, `status` (poll) or `subscribe` (push) + periodic reconciliation, `fetch_result`, `cancel`,
  `classify_error` (content policy · billing · auth · rate limit · transient · permanent).
- **Tests**: planners and estimators are pure → table and sweep tests per model (ArtCraft's parity sweeps); fixture-based
  serde tests for every provider response; live tests opt-in, never in CI, with secrets from the keyring.

### 3b. Job engine

- Rows: `job(id, kind, model, provider, provider_job_id UNIQUE, status, origin json, request_hash, outbound_payload, estimate,
  attempts, next_check_at, result_ids, failure{class, message}, timestamps)`.
- One scheduler task: picks due rows by `next_check_at`, runs the driver step, applies back-off (per-provider rate limits),
  honours a global cancellation token on shutdown; push channels feed the same state machine.
- Status machine: `draft → submitting → queued → running → ingesting → done | failed | cancelled`, with `ingesting` checkpointed
  per output file (ArtCraft's auto-download checkpoint generalised).
- Events: `job.created/updated/progress/done/failed` carrying `origin` so the surface that asked can resolve its own placeholder;
  the job listing returns `origin` too (ArtCraft's task-queue hack exists because it didn't).

### 3c. Media store and documents

- `library/<yyyy-mm>/<sha256>.<ext>` + sidecar metadata; SQLite index with FTS, tags, folders/collections, lineage edges
  (`generated_from`, `edited_from`, `frame_of`, `upscaled_from`), thumbnails in sizes, import with metadata parsing.
- Documents are files: canvas (layered, OpenRaster-like zip), scene (JSON + referenced media by content hash), timeline
  (OpenCut-compatible project JSON), board (JSON). Each has `schema_version`, atomic writes, autosave, and is reopened on launch.
- Optional sync: per-project upload to the hosted backend, last-write-wins with tombstones (ArtCraft's moodboard sync controller is a
  good model), never required.

## 4. Phased plan

Estimates assume a team of **3–4 engineers** (one Rust, two frontend, one graphics/3D) plus AI assistants. A solo developer with
agents should multiply by roughly 2.5–3. Every phase ends with an exit demo and a release build.

### Phase 0 — Foundations (3–4 weeks)

- Repository, workspace layout, `AGENTS.md` skeleton, decision log, licence.
- Tauri shell: single instance, window state, frameless option per OS, strict CSP, scoped `media://` protocol.
- Rust core skeleton: data directories (typed, ArtCraft's `DataSubdir` idea), settings, logging (file + console, rotation), panic hook
  and crash reports (opt-in), build metadata in About.
- **IPC contract**: command envelope, typed event hub, generated TS bindings, CI freshness check.
- SQLite with append-only migrations and migration tests.
- CI on every PR: `cargo clippy/test`, `tsc`, vitest, bindings freshness, a Playwright smoke against a mocked-IPC fixture; release
  workflow producing signed draft installers for Windows and macOS; version single-sourced with a bump script; auto-updater.
- **Exit:** an empty app that installs, updates itself, logs, and has green CI.

### Phase 1 — Job engine and provider registry (4–6 weeks)

- Job table, scheduler, driver trait, back-off, cancellation, restart reconciliation, ingest checkpoints.
- Provider registry with model descriptors and pure planners; first two drivers (one official cloud API with queue semantics such as
  fal; one with push semantics) and a **fake driver** used by all UI tests.
- Cost/ETA estimate command; error classes → typed UI events (login needed, billing, policy refusal).
- Secrets in the OS keyring; BYO API keys UI.
- **Exit:** a CLI or debug page submits intents to two providers, survives a kill mid-job, ingests results exactly once.

### Phase 2 — Media library (3–4 weeks)

- Content-addressed store, index, thumbnails (worker pool), import (drag-drop from OS, metadata parsing), lineage.
- Library UI: virtualised grid, folders/collections, tags, rating, filters, lightbox with "send to" verbs, drag out onto any surface,
  marquee selection, right-click menus everywhere.
- **Exit:** 10,000 assets scroll smoothly; first paint < 1 s; every generated file has provenance.

### Phase 3 — Create pages: image, video, audio (4–6 weeks)

- Model picker driven by descriptors (badges, disabled reasons, per-page memory); prompt box with a reference deck (drag, reorder,
  limits from the descriptor), `@`-mentions of saved characters/reference sets; options rendered only when supported.
- Live estimate (credits or seconds) beside the primary button; generation feed with placeholders that become results in place,
  friendly failure reasons, retry; global job dock.
- Sounds and toasts as optional feedback; empty-state "apps" landing with task-oriented entry points.
- **Exit:** text/reference → image and video on at least 10 models across 2 providers; a new model added by descriptor only.

### Phase 4 — 2D canvas (6–8 weeks)

- **A real layered compositor** (WebGPU with WebGL2 fallback, e.g. PixiJS v8): raster/image/shape/text layers, groups, masks,
  blend modes, transform; brush, eraser, mask brush, lasso/rectangle selection, AI segmentation as a selection source.
- Command-log undo with coalescing; autosave to the document file.
- AI verbs on a selection: inpaint (binary mask, crop-and-stitch), instruction edit of the composite, background removal, upscale;
  **results as candidate variants** in a strip (ArtCraft's HistoryStack) that become layers when picked.
- Idle pre-bake of the composite/mask in a worker; yield a frame before heavy work.
- Export PNG/PSD; drop 3D models in as re-posable render nodes.
- **Exit:** compose → mask → inpaint → pick variant → export, with undo across all of it.

### Phase 5 — 3D stage (8–10 weeks)

- Three.js engine behind an event bus → bridge → store (ArtCraft's one-way flow), canvas hosts never unmounted.
- Kitbash library (characters, props, sets, image planes, skyboxes, splats), raycast drop placement, gizmos, outliner, command undo.
- Characters: humanoid rig standard, FK **and two-bone IK** for limbs, pose presets library, clip retargeting.
- Cameras as objects: focal length in mm, sensor, aspect from the project, framing guides, keyframes.
- **Render passes for conditioning**: beauty, depth, normals, pose skeleton (OpenPose-style), object masks — not only a beauty pass.
- Capture a still or record frame-stepped video (WebCodecs) → straight into Create/Canvas with passes attached.
- Image → mesh and image → splat generation feeding the library and the stage.
- **Exit:** block a shot with two posed characters and a set, render passes, generate a consistent image from them.

### Phase 6 — Timeline (4–6 weeks, adopt rather than build)

- Embed upstream **OpenCut** (MIT) as a library behind adapters (media source = library, export sink = library + disk), with
  attribution; fix the gaps ArtCraft left: project list and reopen, autosave to a document file, auto-landing of generated clips.
- **Exit:** cut a 60-second sequence from generated clips, reopen it tomorrow, export MP4.

### Phase 7 — Boards and story (3–5 weeks)

- Moodboards (grid, free canvas, present) as documents; "send to generation" as references; palette extraction.
- Storyboard: shots with sketch/reference, dialogue, duration, linked to stage scenes, canvas documents and timeline clips.

### Phase 8 — Accounts, billing, sync (3–4 weeks, only if a hosted service exists)

- Device-code login (credentials stay in Rust), credits and subscription as a billing plugin of the provider layer, optional
  per-project sync.

### Phase 9 — Local engine (4–6 weeks)

- A ComfyUI (or sd.cpp) driver: supervised process, graph compilation from descriptors, contract tests against the engine's node
  catalogue, VRAM-aware admission. The descriptor/planner design means no UI change is required.

**Total:** roughly 10–14 months for a team of 3–4 to reach ArtCraft's breadth with a sounder core; Phases 0–4 (≈ 5–6 months) already
make a credible product.

## 5. Cross-cutting plans

| Concern | Plan |
| --- | --- |
| Testing | pure planners/estimators: table + sweep tests; providers: fixture serde tests; job engine: fake drivers + kill/restart tests; editors: unit tests on command logic via adapters with fakes; app: Playwright smoke with mocked IPC on every PR; live provider tests manual and logged |
| Performance | budgets (startup < 400 ms to first frame, tab switch < 50 ms, 60 fps canvas at 4K with 6 layers, library scroll 60 fps at 10k); a perf harness with baselines (ArtCraft's `perf:desktop` method); lazy-load editors; keep editor engines alive across tab switches instead of serialise/rebuild |
| Security | strict CSP without `unsafe-eval`; `media://` scoped to the library; keyring secrets; no URL-fetch-anything command; login webviews without devtools in release; no third-party session recording in the desktop app |
| Accessibility & input | command registry: every action has a mouse placement (button or context menu), keys are remappable accelerators with `when` gates and conflict detection, a cheatsheet; type ≥ 12 px |
| Observability | structured logs with job ids, per-job logs, opt-in crash reports, a diagnostics bundle export |
| Docs | per-subsystem `AGENTS.md` (real files), decision log, dated incident and performance notes with raw data, "add a model / add a provider / add an editor verb" recipes |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| Provider churn (models appear and vanish monthly) | descriptors served by data; passthrough of unknown options; per-model modules |
| Consumer-site automation (scraped sessions) breaks or violates terms | do not build on it; official APIs or local engines only |
| WebGPU availability in WebViews | WebGL2 fallback with an automatic pixel probe |
| Scope explosion (five modalities × four editors) | phase gates with exit demos; adopt OpenCut instead of building a timeline |
| Data loss in editors | documents are files with autosave and atomic writes from Phase 0 |
| Two codebases for web and desktop | editor libraries behind adapters from the first editor |

## 7. Summary: ArtCraft as built vs as planned here

| Area | ArtCraft today | This plan |
| --- | --- | --- |
| Inference | cloud only | provider interface; cloud first, local engine planned |
| User data | backend media tokens, CDN | local-first content-addressed library, optional sync |
| Jobs | ~8 polling loops, task DB reset on schema change | one scheduler + drivers, migrations, origin echoed everywhere |
| Models | backend listing + TS overlay classes; router capabilities in code | one descriptor format for UI, planner and pricing |
| IPC | hand-mirrored enums, mixed event names | generated bindings, CI-verified |
| 2D | Konva object collage, snapshot undo, tinted mask | layered GPU compositor, command undo, binary masks, selections |
| 3D | FK only, beauty pass only | FK + IK, pose presets, depth/normal/pose passes |
| Video | OpenCut port without reopen | upstream OpenCut with persistence and attribution |
| Security | permissive CSP, `**` asset scope, plaintext secrets | strict CSP, scoped protocol, keyring |
| Process | no PR CI | PR CI from day one, signed builds, updater |
