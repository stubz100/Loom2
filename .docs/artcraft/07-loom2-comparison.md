# 07 · loom2 vs ArtCraft — comparison and proposed improvements

Compares loom2 at `4e0db08` plus the uncommitted D34 Catalogue work (2026-10-08) with ArtCraft at `3e5793b693`. Everything in §4
is a **proposal**: per this repository's convention nothing becomes a decision until the author accepts it into
[13](../proto01/13-decision-log-and-open-questions.md). Proposals respect the standing constraints: 16 GB AMD/ROCm rig (T1),
ComfyUI for inference only (D2, D15), mouse-first with keys as accelerators (D19, D32), small drafts by default (D18), EU-first
licensing (D17), `full`/`open` variants (D26).

**Licence reminder:** ArtCraft's licence forbids using its code in a competing product ([05 §7](05-engineering-practices.md)).
Everything below borrows *ideas*; where code would help, it points at upstream MIT sources (OpenCut, Three.js) instead.

## 1. Two different products

| | ArtCraft | loom2 |
| --- | --- | --- |
| Purpose | general "IDE for artists": every modality, every model, sold through credits | local studio for **storyboard pre-production** on one GPU, with the Story workspace next (D23) |
| Where models run | cloud (hosted API, fal, consumer accounts) — nothing local | local ComfyUI on the RX 9070 XT — nothing in the cloud |
| Where work lives | backend media tokens + CDN | project folders on the work disk; files are truth, SQLite an index |
| Scale | ~520k lines, a company team | ~20k hand-written lines (Python 7.2k + tests 2.8k + scripts 3.3k, TS ~9.3k, Rust 0.3k), one author + AI |
| Maturity signal | broad, polished, uneven underneath | narrow, deeply verified (rig acceptance runs, contract tests, journal) |

"More advanced" is true of ArtCraft's **breadth of creative surfaces and product polish**. In the core engineering loom2 cares
about — durability, provenance, layered-editing fidelity, engine contracts, security — loom2 is already ahead. The useful question
is therefore *which ArtCraft surfaces and patterns fit loom2's tenets*, not how to catch up on breadth.

## 2. Side-by-side

| Dimension | ArtCraft | loom2 | Edge |
| --- | --- | --- | --- |
| Model breadth | 62+ models, 5 modalities | FLUX.2 dev/Klein, Wan 2.2, LTX-2.3, tools (BiRefNet, SAM 3, ESRGAN) | ArtCraft |
| Inference control | none (provider decides) | full: presets, encoder choice (D31), VRAM admission, warm groups, offload flags | loom2 |
| Model description | backend capability listing + TS overlay classes; router capability enums | `/capabilities` from presets + roster + rules, but model knowledge spread over `graphs.py`, `roster.py`, `recipes.py` | ArtCraft (cleaner shape) |
| Request building | builder → pure plan → draft/finalize → send; mismatch policy; parity tests | typed recipes → `compile_recipe` → contract check against `/object_info`; preparation mixed into `queue.py` | tie (loom2's contract check is stronger; ArtCraft's staging cleaner) |
| Job durability | task row at enqueue, pollers, checkpointed downloads; DB reset on schema change | durable queue, atomic writes, resume paused, stall watchdog, Job Objects, rebuildable index | loom2 |
| Result routing | `frontend_subscriber_id` echoed in completion events | `document_id` on edit recipes; generic jobs route via events + stores | ArtCraft (more general) |
| Library | cloud gallery, folders, tags, lightbox hub, drag onto any editor | catalogue with lineage, album pages and groups (D34), split panes, filters, loupe/compare | loom2 (provenance) / ArtCraft (drag-out + lightbox hub) |
| 2D editing | Konva object collage, snapshot undo, tinted mask, no selections | layered PixiJS compositor, exact W3C blends checked against numpy, masks, selections, AI segment, ORA/PSD, tile undo | **loom2, clearly** |
| AI on canvas | inpaint / instruction edit / bg removal; results as candidate base images | inpaint modes, refine, outpaint, tiled refine, upscale, segment; variant strip of candidate layers | loom2 |
| 3D staging | full stage: kitbash, FK posing, cameras with focal length, timeline, record | none | **ArtCraft** |
| Image → 3D, splats | yes (cloud) | no | ArtCraft |
| Video | i2v across many models + OpenCut-based editor | Wan / LTX i2v with FLF, keyframe beats, frame-accurate player, frame harvest, FaceSim | loom2 for generation control, ArtCraft for editing |
| Moodboards | grid + free canvas + present, sync | album pages with free arrangement (D34) | comparable |
| Prompting | prompt box with reference deck, `@`character mentions, capability-gated options, live cost | BFL JSON tree / JSON / text, field presets, live `/recipes/preview` with ETA and VRAM fit | loom2 for control, ArtCraft for references |
| Keyboard | remappable registry, `when` gates, presets, cheatsheet | command registry where every command must have a mouse placement (D32), `?` overlay, `Ctrl+K` | loom2's rule is stricter; ArtCraft's is remappable |
| IPC / API contract | hand-mirrored enums | OpenAPI exported, `schema.d.ts` generated **but not imported** | neither |
| Security | permissive CSP, `**` asset scope, plaintext secrets | strict CSP verified by `csp_check.py`; token on mutating routes; **GETs unauthenticated** | loom2 |
| Frontend tests | Vitest specs, Playwright smoke + perf harness with mocked IPC | none (tsc + headed Edge scripts) | ArtCraft |
| Backend tests | ~4,900 offline Rust tests | 111 pytest incl. fake ComfyUI and contract fixtures; rig acceptance scripts | loom2 relative to size |
| CI | publish only, no PR checks | PR CI: tests + both variant builds; installers on main | loom2 |
| Agent docs | `AGENTS.md` per subsystem with recipes and footguns | numbered design docs + journal + decision log; **no `AGENTS.md`/`CLAUDE.md`** | ArtCraft for agents, loom2 for decisions |
| Performance practice | measured startup harness, lazy pages | measured spikes (E1–E3, E6), headed checks; suites not lazy, suite stages remount on switch | both partial |

## 3. Where loom2 is ahead — keep, do not regress

- **Files are truth, the index is rebuildable**, atomic fsync'd writes, quarantine of corrupt state, resume paused after a crash.
  ArtCraft throws its task history away on schema changes.
- **Contract tests against the pinned engine** (`engine/contract.py`, `pin_review.py`) — ArtCraft has nothing comparable for its
  providers because it cannot.
- **Exact compositing** (D31 · compositing: blend shaders verified against `compose.py`) and real layers, masks, selections, ORA/PSD — ArtCraft's 2D
  canvas is far simpler.
- **Lineage stamped at write time** and a lineage view; FaceSim as an advisory meter.
- **Strict CSP and a CSP check in CI**; no analytics or session recording in the app.
- **Decision log + journal with measurements**; rig acceptance runs as the definition of done.

## 4. Proposed improvements

Effort: **S** ≤ 1 day, **M** 2–5 days, **L** 1–3 weeks (author + AI). "When" maps onto the post-MVP backlog in 13.

| # | Proposal | Value | Effort | When |
| --- | --- | --- | --- | --- |
| P1 | Model descriptors as one data registry | high | M | now |
| P2 | Plan → finalize → submit stages for recipes | high | M | now |
| P3 | Use the generated API types; CI freshness check | medium | S | now |
| P4 | Job `origin` echoed in every job and asset event | medium | S | now |
| P5 | Keep heavy suite stages alive; lazy-load suites; measure | medium | S–M | now |
| P6 | Frontend test harness (Vitest + fake-orchestrator smoke + perf baseline) | high | M | now |
| P7 | `AGENTS.md` per subsystem with add-X recipes and footguns | high | S | now |
| P8 | Split `api.py` into routers; one domain per module | medium | M | now |
| P9 | Authenticate GETs and the WebSocket properly | medium | S | now |
| P10 | Idle pre-save of the Edit document before AI verbs | medium | S–M | now |
| P11 | Library as the "send to" hub: drag-out to every slot, lightbox verbs | medium | S–M | next |
| P12 | Reference deck with `@`-mentions of groups / characters | high (Story) | M | with Story workspace |
| P13 | **Stage suite: 3D blocking with control passes** | very high (Story) | L + spike | after Story L1–L2 |
| P14 | Viewpoint / angles verb (orbit sphere UI) | medium | M + spike | with Story coverage |
| P15 | Task-oriented quick actions on an empty-state home | low–medium | S | next |
| P16 | Remappable keys with `when` gates (on the D32 registry) | low (mouse-first) | M | later |
| P17 | Timeline for Shots & Takes (single lane; OpenCut not embeddable) | medium | spike + L | with Story P3/P5 |
| P18 | Image → mesh locally for props (TRELLIS.2 / Pixal3D; Hunyuan3D excluded in the EU) | low | spike | later |
| P19 | Release hygiene: single version source, build metadata in About | low | S | next |

### P1 · Model descriptors as one data registry

- **ArtCraft:** one capability shape per model (`OmniGenVideoModelDetails`: input slots with max counts, option lists with defaults,
  duration ranges, prompt limits, `is_disabled`) served to the UI; the UI renders only supported controls; request builders clamp
  defensively with an explicit mismatch policy (`PayMoreUpgrade | PayLessDowngrade | ErrorOut`) and field-named errors
  (`ModelDoesNotSupportOption { field, value }`).
- **loom2 today:** `ModelPreset`/`PRESETS`, `TE_ALTERNATES`, `I2V_RULES`, `BASE_SECONDS` and VRAM estimates live in `graphs.py`;
  roster facts in `roster.py`; sampler enums in `recipes.py`; `/capabilities` is assembled inline in `api.py`. Adding a model touches
  four files and the frontend's assumptions.
- **Proposal:** a `models/` package (or one TOML/YAML file per model) holding *everything* about a model: roster ids per role (weights,
  TE options + default, VAE), sampling presets per tier (Draft / Full, D18), size multiples and frame rules, input slots (references
  max, start/end frame, mask), option domains with defaults, VRAM/seconds estimators, licence and variants (D26), and the graph-builder
  entry point. `/capabilities` becomes a serialisation of the registry; Generate, Edit AI and Animate panels gate every control on it
  (they partly do); snapping to multiples becomes an explicit policy (`snap_up | snap_down | error`) with field-named 422s.
- **Tests:** a sweep that compiles every model × tier × option grid against the `object_info` fixture (extends the 17-variant check in
  `pin_review.py`), plus "estimates are monotonic in size/frames" property tests.
- **Fits:** T8 "display == reality", D25 (LoRA slots become a descriptor field), the post-MVP items that add models (LTX-2.5, Qwen-Edit,
  SeedVR2, H3).

### P2 · Plan → finalize → submit stages for recipes

- **ArtCraft:** `build2()` is pure (validate, snap, price) and returns a *draft* when inputs still need uploading; `finalize(ctx)` does
  the I/O; the *request* is then sent. Cost/ETA are available on the draft, before any I/O.
- **loom2 today:** `_run_one` interleaves engine start, uploads, document cropping (`_prepare_document_inputs`), compilation and
  contract checks; document and i2v pre/post-processing (~300 lines) sit inside `queue.py`, and the "mark done, record, persist,
  broadcast" block is repeated three times.
- **Proposal:** `plan(recipe) -> Plan` (pure: effective params, compiled graph with placeholders, estimates, required inputs) used by both
  `/recipes/preview` and the queue; `finalize(plan, ctx) -> Submission` (crop/upload/resolve names against `object_info`); per-kind
  `Finisher`s for assets, document layers and clips moved out of `queue.py`; one `_complete(job, outputs)` path. The queue keeps
  scheduling, admission, the watchdog and durability only.
- **Payoff:** smaller `queue.py`, the preview shows exactly what will run (T8), and finishers become unit-testable without the fake engine.

### P3 · Use the generated API types

- **ArtCraft's lesson:** hand-mirrored enums drifted enough that its own files say "should use code gen".
- **loom2 today:** `openapi.json` and `schema.d.ts` are regenerated, but nothing imports `schema.d.ts`; `types.ts` is a hand mirror and
  request bodies are `Record<string, unknown>`; the journal records `openapi.json` going stale for several milestones.
- **Proposal:** add `response_model`s to the orchestrator routes (today only 2 routes declare one, so the spec has almost no response
  schemas); then `openapi-fetch` (or typed wrappers) over `schema.d.ts` in `api/client.ts`; migrate `types.ts` to re-exports of schema
  types; a script that exports `openapi.json` from the app, and a CI step that regenerates both files and fails on a diff. Do the same for WebSocket event payloads (a pydantic
  union exported to JSON Schema → TS).

### P4 · Job `origin` echoed everywhere

- **ArtCraft:** every request carries `frontend_caller` + `frontend_subscriber_id` (+ opaque payload); completion events echo them, so
  each surface resolves only its own placeholders. Its one mistake — the job listing not echoing the id — produced a
  timestamp-matching hack.
- **loom2 today:** edit recipes carry `document_id`; other routing relies on stores reacting to `asset.created` and a second bus of
  `window` CustomEvents (`loom2:group-changed`, `loom2:asset-event`).
- **Proposal:** `JobRecord.origin = {suite, surface, ref, payload}` set by the caller (e.g. `{suite: "generate", surface: "ref-slot", ref: 3}`,
  `{suite: "animate", surface: "end-frame"}`, `{suite: "catalogue", surface: "group", ref: grp_…}`), persisted, returned by `GET /jobs`,
  and copied into `job.*` and `asset.created` events. Results can then land where they were asked for (e.g. into the group that was open,
  per D34's "every new item lands in Unprocessed" unless the origin says otherwise — an author decision). Retire the window-event bus in
  favour of the WS event router.

### P5 · Keep heavy suite stages alive; lazy-load; measure

- **ArtCraft:** lazy-loaded 15 pages (−38 % startup), and found that serialising/rebuilding an editor on every tab switch was the expensive
  part; its 3D stage documents "never unmount the canvas hosts".
- **loom2 today:** `frame/Stage.tsx` (and Strip, Panel, Inspector) render only the active suite, keyed by `suite.id`, so switching away from
  Edit destroys the PixiJS application and coming back re-inits it, re-runs the WebGPU probe and refits (C21 made that safe, not cheap);
  Animate's player reopens and re-decodes its proxy; all suites are bundled eagerly and the Mediabunny chunk is modulepreloaded at startup.
- **Proposal:** measure suite-switch time and startup first (journal entry with method and raw numbers, ArtCraft-style); then keep the
  Edit and Animate stages mounted but hidden after first visit (`display: none`, render loop paused), and `React.lazy` the Edit and Animate
  suites (PixiJS, ag-psd, Mediabunny) so the Catalogue paints first. Also drop the `spikes.html` input from production builds.

### P6 · Frontend test harness

- **ArtCraft:** Vitest specs on pure logic (`buildModelsFromListing.spec.ts`, keybind conflict tests), a Playwright smoke that drives the
  real UI against a deterministic mocked-IPC fixture, and a perf runner with baselines.
- **loom2 today:** no frontend unit tests; correctness of `transform.ts`, `filters.ts`, `split.ts`, PageView layout maths, chord parsing
  and store event application rests on `tsc` and headed Edge scripts.
- **Proposal:** (1) Vitest for pure modules and the store event reducers; (2) a smoke run in CI: orchestrator with `fake_comfy.py` + a
  synthetic catalogue (`make_synthetic_assets.py` exists) + the built frontend in headless Edge/Playwright, scripted through
  `window.__loom2Commands` (already exposed for headed tours); (3) a perf script (startup, suite switch, 10k-asset scroll) whose results
  are appended to the journal with a baseline. WebGPU-only checks stay in `edit_headed_check.py`.

### P7 · `AGENTS.md` per subsystem

- **ArtCraft:** focused agent docs next to the code — the router's five-step "add a model" checklist, the 3D stage's ⚠ footguns, the
  one-command-per-file rule. (Its symlinked `CLAUDE.md` files are broken on Windows; its 3D spec drifted from the code.)
- **loom2 today:** excellent specs in `.docs/proto01`, but no file an agent reads automatically, and footguns live in journal entries
  (WebView2 kills `window.confirm`; HTML5 drag events never fire with the OS file-drop handler on; Pixi sprite masks break blend
  backdrops; FileResponse chunk size must be 4 MiB; ComfyUI-GGUF tokenizer patch).
- **Proposal:** a real root `CLAUDE.md` (pointer to `.docs/proto01/00-README.md`, the rig, the test commands, the D32 rule) and short
  `AGENTS.md` files in `orchestrator/loom2/engine/` (add a model / recipe / node pin: roster → descriptor → builder → fixture → test →
  capability → UI), `frontend/src/frame/` (command registry rules, drag manager, AskDialog), `frontend/src/suites/edit/` (compositor
  invariants and footguns). Each carries a "verified at <commit>" line refreshed at milestone starts.

### P8 · Split `api.py`

- **ArtCraft:** one command per file, one endpoint binding per file — small diffs, local agent edits.
- **loom2 today:** `create_app()` holds ~95 routes as nested functions in 1,170 lines with inline imports and business logic (e.g.
  `/capabilities`).
- **Proposal:** FastAPI `APIRouter`s per domain (`routes/assets.py`, `groups.py`, `documents.py`, `clips.py`, `jobs.py`, `models.py`,
  `engine.py`, `meta.py`), dependencies via `Depends(get_services)`, business logic moved to the domain modules; move the blocking
  catalogue calls consistently behind `asyncio.to_thread` while touching them. Mechanical, but do it before the Story workspace adds
  its own endpoints.

### P9 · Authenticate GETs and the WebSocket

- **ArtCraft** is the cautionary tale (permissive CSP, whole-disk asset scope, plaintext secrets).
- **loom2 today:** strict CSP, but GET routes (asset files, thumbnails, document pixels, settings, job records with prompts) need no
  token, FastAPI's `/docs`, `/redoc` and `/openapi.json` are served, and the WS token travels in the query string.
- **Proposal:** require the token on every route; for `<img>`/`<video>` URLs use a per-launch HttpOnly cookie set by a token-authenticated
  bootstrap call (works with Range requests), or a short-lived signed URL parameter; send the WS token as the first message. Keep any
  future secrets (HF token, licence keys) in Windows Credential Manager via `keyring`, never in `app.json`.

### P10 · Idle pre-save before AI verbs in Edit

- **ArtCraft:** pre-bakes the composite in a worker 300 ms after any change, so Generate finds a ready file; yields one frame so the busy
  state paints first; generation counters discard stale bakes.
- **loom2 today:** AI jobs crop the *saved* composite and selection server-side, so `runAi` first awaits a full `save()` — which always PUTs
  the stack, uploads every dirty layer, POSTs `/save` and toasts "Saved", even when nothing changed — then uploads the whole selection, then
  posts the job.
- **Proposal:** flush dirty layers and the selection to the orchestrator on idle (debounced, cancelled by new strokes, guarded by the
  document revision from C1/C20); make `save()` a no-op when nothing is dirty; the AI button then only posts the recipe. Show the region
  preview and size from the already-saved state.

### P11 · The library as the "send to" hub

- **ArtCraft:** the lightbox owns every destination verb (edit, animate, remove background, make 3D, recreate); its gallery modal turns
  translucent and click-through when a drag leaves it so items can be dropped onto the editor behind; a tilting drag ghost shows an
  ok/blocked badge before the drop.
- **loom2 today:** cross-suite verbs exist (07 §3c) and `frame/drag.ts` handles drops onto suite tabs (Edit opens the asset, Generate adds
  references, Animate fills start/end), reference slots, Animate slots and beats, the Edit stage and album pages; the loupe bar carries only
  Keep / Reject / Edit / Reference.
- **Proposal:** make the loupe the hub (one bar with every send-to verb, mouse-first), add a drag ghost with a valid/invalid badge driven
  by each target's `accepts()` (e.g. Animate end-frame rejects clips), and switch suites when a drag hovers a suite tab for ~600 ms so a
  tile can be carried straight into Generate's reference slots or an Animate slot (today the tab itself is the drop target).

### P12 · Reference deck with `@`-mentions

- **ArtCraft:** a reference *deck* (drag, reorder, per-model limits) and `@`character chips in the prompt that resolve to saved character
  reference sets.
- **loom2 today:** Generate has reference slots (FLUX.2 multi-reference); Story workspace AssetProfiles (14) will need exactly this.
- **Proposal:** when Story L2 lands, let a prompt mention `@group` / `@character`, expanding to that profile's reference images (capped by
  the descriptor's `references_max`, P1) and stamping the profile version into the manifest (lineage at write time, loom lesson 7).

### P13 · Stage suite — 3D blocking with control passes

The single biggest capability ArtCraft has and loom2 lacks, and it serves loom2's actual goal (storyboard shots with consistent sets,
characters and cameras) better than it serves ArtCraft's.

- **What to take from ArtCraft (as design, re-implemented):** vanilla Three.js engine behind event bus → bridge → store; canvas hosts
  never unmounted; kitbash library with raycast drop; outliner with lock/visibility; Blender-literate but mouse-driven gizmos; render
  camera as an object with focal length in mm and framing guides; command-pattern undo serialised through a promise chain; capture a
  still or record frame-stepped video.
- **What to do better:**
  - **Control passes**, not just a beauty render: depth, normals, pose skeleton, per-object masks, rendered at the project's draft size
    (D18) and stored as assets with `lineage_kind = stage-pass`.
  - **IK** (two-bone for limbs) and **pose presets**, not FK-only Mixamo picking.
  - Scenes as project files (`stages/<id>.json` with media by asset id), atomic writes, reopened on launch — not a backend blob.
  - Camera aspect and size from `project.json` (16:9 target, draft tiers).
- **Conditioning on the 16 GB rig** needs a spike (E10) before any UI promise: FLUX.2 / Klein with the beauty pass + character references
  through `ReferenceLatent` (exists today), versus depth/pose ControlNet-style conditioning for the families in the roster where ComfyUI
  nodes and weights exist, versus LanPaint-style refinement of a rough composite; measure adherence and seconds per image with the bench
  method (04 §6). Props can start as BiRefNet cut-outs on image planes (D33 already produces the mattes).
- **Placement:** after Story L1–L2 (14), as part of Shots & Takes (L3): a shot = stage scene + camera → keyframe stills → Animate (FLF /
  LTX beats). Rail/Panel/Stage/Inspector map directly onto the 07 frame (outliner in Panel, viewport in Stage, object/camera in Inspector).

### P14 · Viewpoint / angles verb

- **ArtCraft:** an orbit-sphere control (rotation, tilt, zoom) that regenerates an image from another viewpoint, using an angle-tuned
  image-edit model (its router lists a Qwen-Image-Edit-2511 "angles" variant).
- **loom2 relevance:** character coverage (loom's coverage matrix of angles and poses) is the Story workspace's bootstrap loop.
- **Proposal:** spike a local angle edit on the 16 GB rig (Qwen-Image-Edit was deferred at 475 s cold / ≈ 95 s warm in E8; re-measure with
  the current pin and an fp8 path, D30), and if it holds, add a "New angle…" verb on Catalogue tiles and Edit documents with the orbit
  control in the Panel.

### P15 · Quick actions on an empty-state home

ArtCraft's landing page offers task-oriented cards ("Remove background", "Change angle", "Image to video", "Extract frame"). For a
mouse-first user, an empty Catalogue (or a new project) could show the same: each card opens the right suite with the tool and
inputs preselected (Edit + AI Select subject; Animate with the picked start frame; Edit + Upscale). Cheap discoverability; every card is
just a D32 command with a placement.

### P16 · Remappable keys

ArtCraft's keybind registry adds user overrides, presets (Gamer / Blender), `when(ctx)` availability gates with enforced mutual exclusivity
and a hold-to-peek cheatsheet. loom2's D32 registry already enforces the more important rule (every command has a mouse placement); adding
overrides + conflict detection is straightforward but low value for a mouse-first author. Revisit when a pen tablet arrives (D19).

### P17 · Timeline for Shots & Takes

ArtCraft adopted OpenCut (MIT) as a ~71k-line library behind adapters rather than writing an editor — and then never wired project
reopening. Upstream OpenCut is **not embeddable**: the classic Next.js app was archived on 2026-05-17, the new default branch is a Rust/GPUI
rewrite whose editor API is roadmap-only, and `opencut-wasm` ships a compositor and time maths but no timeline UI. loom2's plan (14, loom
P5) — a single-lane episode timeline with overlap transitions and EDL/FCPXML export to Resolve — is therefore the right shape; borrow only
OpenCut's integer-tick media time. Delivery: a two-day spike, then the build inside the Story workspace (08 §P17).

### P18 · Image → mesh locally

ArtCraft's image→3D (Hunyuan 3D and others) feeds its stage with props. **Hunyuan3D is unusable for loom2:** its 2.0 and 2.1 community
licences exclude the European Union from the licensed territory (D17's EU-first rule), so the `hunyuan_3d_v2.1.safetensors` on `D:` must stay
out of the roster. The pinned ComfyUI v0.39.0 natively runs **TRELLIS.2** (MIT code and weights) and **Pixal3D** (MIT) in pure torch, which
makes them the candidates for a spike on 16 GB — only after P13 exists. Image planes from BiRefNet cut-outs cover most storyboard props.

### P19 · Release hygiene

ArtCraft keeps the version in three files with a bump script, releases from a branch into **draft** releases, and shows git SHA and build
time in About. loom2 already builds both installers in CI; add a single version source (`pyproject`/`package.json`/`tauri.conf.json`
synced by a script), the git SHA and build time in `/version` and Settings → About, and draft releases on tags.

## 5. Deliberately not copied

| ArtCraft choice | Why not for loom2 |
| --- | --- |
| Cloud providers and scraped consumer accounts (browser-fingerprint emulation, captured cookies) | contradicts the local-only scope; terms-of-service and breakage risk; the author's rule is ComfyUI for inference |
| Media identity = backend tokens + CDN | loom2's content-addressed project files with sidecar manifests are stronger and offline |
| Task DB reset on schema change | loom2's rebuildable index + migrations-by-rebuild already avoid data loss |
| Konva object canvas, snapshot undo, tinted masks | loom2's compositor is more capable and exact |
| Unmount-and-serialise editors on tab switch | the cost ArtCraft measured; P5 goes the other way |
| Three state paradigms, window-event buses, globals | loom2 should retire its own small window-event bus (P4) rather than grow one |
| Per-provider sleep loops | loom2's single queue + engine event pump is the better shape |
| Permissive CSP, `**` asset scope, plaintext credentials, URL-fetch-anything command | security regressions |
| Symlinked `CLAUDE.md` on Windows; agent specs that drift from the code | P7 uses real files with a "verified at" line |
| Analytics and session recording inside the desktop app | personal tool; no |

## 6. Suggested order

1. **Hardening batch, before the Story workspace:** P7 → P3 → P8 → P2 → P1 → P4 → P9 → P6 → P5 → P10. P7 first because every later step is
   done with agents; P8/P2 before P1 because the registry is easier to introduce into smaller modules. Delivery plans with slices,
   tests, acceptance runs and estimates: [08](08-delivery-plans.md).
2. **With Story L1–L2:** P12, P11, P15, P19.
3. **Spikes alongside Story L3 (Shots & Takes):** E10 for P13 conditioning, P14 angles, then the Stage suite (P13).
4. **Later:** P17, P16, P18.

If accepted, each item would get a D-number in [13](../proto01/13-decision-log-and-open-questions.md) and a slot in its post-MVP
backlog; P13 would also need its own UI document in the 07–11 series before implementation (D12).
