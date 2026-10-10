# 08 · Delivery plans for proposals P1–P19

Status: **proposed 2026-10-10** — one delivery plan per proposal in [07 §4](07-loom2-comparison.md). The author considers all 19 valid
improvements; each still becomes a decision only when it is entered in [13](../proto01/13-decision-log-and-open-questions.md), and
the milestones below would join [12](../proto01/12-roadmap.md).

**Baseline:** `4e0db08` plus the uncommitted D34 Catalogue work (35 modified and 13 new files). The offline suite has 115 tests and
passes in 38.5 s (`orchestrator/.venv/Scripts/python.exe -m pytest orchestrator -q`, measured 2026-10-10). Line numbers below refer to
that working tree.

## 0. How the plans are written

Every plan follows the shape the MVP milestones used (12): **goal → today → design → slices → tests → acceptance (executable) →
docs and decision → risks → effort**.

- **Slices** are commit-sized: each leaves the suite green and the app usable.
- **Acceptance** is a script or test someone can run. Where the rig matters, a run goes into `90-journal.md` with timings.
- **Effort** is given in focused author+AI days at *planning rates*. The MVP ran far faster than 12 planned (M1–M7 in four days), so
  calendar time will probably come in well under these numbers. The ratios between plans are the useful part.

**Spike names** continue the E-series of 12 §1: E10 (Stage conditioning, image), E11 (Stage conditioning, video), E12 (angles),
E13 (timeline), E14 (image → mesh).

**Prerequisite for everything:** commit the D34 working tree first. P8, P3 and P4 touch `api.py`, `types.ts` and `session.ts`, which
D34 has modified.

## 1. Programme

| Wave | Proposals | Theme | Effort | Depends on |
| --- | --- | --- | --- | --- |
| **H1 · Agent-ready** | P7, P19, P8, P3 | docs for agents, versions, router split, typed API | ≈ 9 d | D34 committed |
| **H2 · Engine pipeline** | P2, P1, P4 | plan/finalize/submit, model registry, job origin | ≈ 15 d | H1 (P8 before P2; P3 before P1's typed capabilities) |
| **H3 · Safety and tests** | P9, P6 | authenticated reads, frontend test harness | ≈ 7 d | H1 (P8 for P9; P3 for P6's typed fixtures) |
| **H4 · Responsiveness** | P5, P10 | keep-alive stages and lazy suites; idle pre-save in Edit | ≈ 6 d | H3 (P6's perf script measures both) |
| **X1 · Flow** (with Story L1–L2) | P11, P15, P12, P16 | send-to hub and drag, quick actions, `@`mentions, remappable keys | ≈ 14 d | H2 (P4 origin, P1 inputs), Story L2 for P12's characters |
| **Spikes** | E10, E11, E12, E13, E14 | Stage conditioning (image, video), angles, timeline, image → mesh | ≈ 13 d | H2 (P1 registry to land winners) |
| **ST · Stage suite** (with Story L3) | P13 | 3D blocking with control passes | ≈ 25–30 d | E10/E11 decided, UI doc approved (D12), P5 policy |
| **Later** | P14 build, P17 build, P18 build | angles verb, single-lane timeline, mesh props | 6 / 10 / 6 d | E12 / E13 / E14 passed |

```
D34 commit ─► H1: P7 ─► P19 ─► P8 ─► P3
                              │      │
                              ▼      ▼
              H2: P2 ─────► P1 ─► P4 ───────────────► X1: P11 · P15 · P16 ─► P12 (Story L2)
                              │                           ▲
              H3: P9 · P6 ────┼─► H4: P5 · P10 ───────────┘
                              │
                              └─► Spikes: E10 · E11 · E12 · E13 · E14 ─► ST: P13 (Story L3) ─► P14 · P17 · P18 builds
```

The hardening waves H1–H4 total ≈ 37 planning days (about 7–8 weeks at 12's rates). At the MVP's observed pace, budget about two weeks.

## 2. H1 · Agent-ready

### P7 · `AGENTS.md` per subsystem — 1 d

**Goal.** An agent opening any part of the repo finds the rules, recipes and footguns that today live only in specs and journal
entries.

**Today.** There is no `CLAUDE.md` or `AGENTS.md` anywhere. The footguns sit in journal entries:
- `window.confirm` / `window.prompt` crash in WebView2.
- HTML5 drag events never fire with the OS file-drop handler on.
- Pixi sprite masks break the blend backdrop.
- `FileResponse.chunk_size` must be 4 MiB.
- The ComfyUI-GGUF tekken patch.

**Design.** Real files, not symlinks (ArtCraft's symlinked `CLAUDE.md` checks out as a 9-byte text file on Windows). Each file is
≤ 150 lines, carries a `Verified at <commit> on <date>` line, and points to the numbered spec instead of repeating it.

**Slices.**
1. **Root `CLAUDE.md`:**
   - what loom2 is and the doc index (`.docs/proto01/00-README.md`);
   - rig constraints (16 GB ROCm, ComfyUI for inference only);
   - commands: pytest, `npm run build`, `scripts/dev.ps1 [-Browser]`, acceptance scripts;
   - house rules: D32 mouse-first, atomic writes, append-only journal, decisions in 13, never `window.confirm`;
   - where things live.
2. **`orchestrator/AGENTS.md`:**
   - module map;
   - durability rules (files are truth, `fsio` atomic writes, schema versions);
   - the async rule (blocking catalogue/file work goes through `asyncio.to_thread`);
   - test tiers, `fake_comfy` modes, the `rig` marker.
3. **`orchestrator/loom2/engine/AGENTS.md`:**
   - add-a-model and add-a-recipe checklists (rewritten after P1 lands);
   - pin bump procedure (`pin_review.py`, fixture recapture with `make_object_info_fixture.py`, `nodes.lock`, `engine/patches/`).
4. **`frontend/src/frame/AGENTS.md`:**
   - command registry rules (every command needs a placement);
   - drag manager instead of HTML5 DnD;
   - AskDialog instead of native dialogs;
   - theme tokens only;
   - deep links.
5. **`frontend/src/suites/edit/AGENTS.md`:**
   - compositor invariants: own W3C blend shaders, render-texture passes, no sprite masks, `compose.py` is the truth;
   - the WebGPU probe;
   - why WebGPU checks need the headed Edge script.
6. **`scripts/agents_check.py`** (wired into CI):
   - every backticked repo path in an `AGENTS.md`/`CLAUDE.md` must exist;
   - every file must have a `Verified at` line.

   This catches the drift that made ArtCraft's 3D spec contradict its code.

**Acceptance.**
- `scripts/agents_check.py` passes in CI.
- Renaming a referenced file makes it fail.
- A fresh agent session asked "add a Klein preset" quotes the engine checklist.

**Docs.** 13: one decision ("subsystem agent docs, verified per milestone"); 12: add "re-verify `AGENTS.md`" to the milestone-start
checklist.

**Risks.** Docs drift; the path check and the per-milestone re-verify are the mitigation.

### P19 · Release hygiene — 1 d

**Today.**
- `0.1.0` appears in `orchestrator/pyproject.toml`, `loom2/__init__.py`, `tauri.conf.json` and `src-tauri/Cargo.toml`; `frontend/package.json`
  says `0.0.0`.
- `/version` returns `{orchestrator, engine, variant}`, but no UI calls it; the only visible version is the TopBar app-menu label.
- CI uploads installers as artifacts; there are no GitHub releases and no git tags.

**Design.** One `VERSION` file at the root.
- **`scripts/bump_version.py [major|minor|patch|X.Y.Z]`** rewrites the five places and fails if they disagree.
- **Build metadata.** The shell's `build.rs` bakes `LOOM2_GIT_SHA` and `LOOM2_BUILD_TIME` (as `option_env!` does for the variant) and passes them
  to the orchestrator. `/version` then returns:
  - `{app, git_sha, build_time, variant}`;
  - `engine: {comfyui_tag, comfyui_running}`;
  - `nodes: nodes.lock` entries;
  - `schemas: {queue, app, group, asset, index}`.
- **Settings → About pane:** versions, git SHA, build time, state/models/log directories with Reveal buttons, and a **"Copy diagnostics"**
  button (versions, settings minus paths, last 200 log lines).
- **CI:**
  - a version-consistency check on every push;
  - on tags `v*`, a **draft GitHub release** with both variant installers attached (`loom2-full-<ver>.exe`, `loom2-open-<ver>.exe`).

**Slices.** (1) `VERSION` file and bump script, plus the CI consistency check; (2) build metadata through the shell into `/version`;
(3) About pane; (4) draft release on tags.

**Tests.** A pytest checks that the `/version` keys are present. The bump script gets a dry-run test on a temp copy.

**Acceptance.**
- `bump_version.py minor` updates all five files and CI goes green.
- Hand-editing one file makes CI fail.
- About shows the same SHA as `git rev-parse --short HEAD`.
- Pushing tag `v0.2.0` yields a draft release with two installers.

**Docs.** 06 §11 (build variants and releases); 07 §6 (Settings → About).

### P8 · Split `api.py` into routers — 3 d

**Today.** `api.py` is 1,170 lines:
- `Services` at l.45–102;
- 16 request models at l.105–206;
- `create_app` at l.209–1170, with 89 HTTP routes (36 GET, 53 mutating) and one WebSocket, all as closures over `svc`.

Inline imports sit at about 15 sites. Blocking work runs on the event loop in many handlers, among them:
- `project_get`, `assets_tags`, `assets_bulk`, trash/restore, lineage, `asset_get`/patch/delete;
- groups tree/where/create/patch/delete/layout/ungroup;
- `assets_import` metadata parsing;
- documents list/thumbnail/pixels/export/compare/selection;
- clips list/get/extract;
- presets/snippets writes, project create/open;
- `jobs_submit` and `documents_ai` (`q.submit` persists);
- `models_scan`.

**Design.**
- `orchestrator/loom2/routes/` holds one module per domain: `meta.py`, `settings.py`, `projects.py`, `assets.py`, `groups.py`,
  `documents.py`, `clips.py`, `jobs.py`, `models.py`, `engine.py`, `blobs.py`, `events_ws.py`.
- `deps.py` provides `get_services`, `require_project`, `require_groups` and `require_token`.
- `api.py` keeps `create_app` (middleware, CORS, error mapping, router includes) and stays under 200 lines.
- Request models move next to their routes. Business logic moves into domain modules: `/capabilities` assembly goes to
  `capabilities.py`, and P1 replaces it later.
- **Rule:** every handler that touches SQLite or files calls through `asyncio.to_thread` (or a `run_blocking` helper). The `JobQueue`
  keeps its own `persist` on the loop for now (atomicity); P2 revisits it.

**Slices.**
1. `routes/` scaffolding with `deps.py`; move meta/settings; add a test that snapshots the route table.
2. Projects, assets and lineage.
3. Groups.
4. Documents.
5. Clips, jobs and queue.
6. Models, engine, blobs and WS.
7. Blocking calls behind `to_thread`, imports to module tops.
8. Remove the six dead `/collections` request models and the `collection_*` catalogue methods left over from D34.

**Tests.**
- **Route-table snapshot** (method + path + response status codes) taken from `app.routes` before slice 1; after every slice it must
  be identical.
- The full pytest suite after every slice.
- A new test runs 50 concurrent `GET /assets` calls during a `POST /assets/import` of 200 files; the event loop's lag must stay under 50 ms
  (measured with a heartbeat task).

**Acceptance.**
- `api.py` < 200 lines; no route function over 60 lines.
- The `openapi.json` paths are unchanged.
- 115+ tests are green.
- `scripts/m1_acceptance.py` passes on the rig.

**Docs.** 06 §6 (API surface: module map); `orchestrator/AGENTS.md` (P7).

**Risks.** Merge pain against uncommitted work — hence the D34 commit first. The snapshot test guards against silently dropped routes.

### P3 · Use the generated API types — 4 d

**Today.**
- `schema.d.ts` (4,575 lines) is imported nowhere.
- `types.ts` (82 lines, 18 importers) is a hand-written mirror.
- 80 `api.*` call sites, 41 of them with untyped inline bodies.
- 8 raw `fetch` calls in `editorStore.ts`.
- **Only 2 routes declare a `response_model`**, so the spec has almost no response schemas.
- `openapi.json` has no export script; it went "several milestones stale" (journal).
- The spec still carries `Collection*` schemas.

**Design.**
1. **`scripts/export_openapi.py`:**
   - imports `create_app` with a temp state directory and writes `frontend/src/api/openapi.json` with sorted keys;
   - `npm run api:types` chains export → `openapi-typescript` (still via `npx`, because of its TypeScript 5 peer);
   - **CI regenerates both files and fails on `git diff --exit-code`.**
2. **Response models:**
   - pydantic models for every GET, plus the POSTs whose responses the UI reads (`JobRecord`, `AssetRecord`, `AssetPage`, `GroupTree`,
     `DocumentStack`, `ClipRecord`, `QueueState`, `EngineState`, `ProjectInfo`, `Settings`, `Capabilities` from P1);
   - `response_model=` on each route. `AssetRecord` and `JobRecord` are already pydantic.
3. **Typed client:**
   - `openapi-fetch` (about 6 kB) behind the existing `call()`, keeping the token header, `ApiError` and 204 handling;
   - `api.get('/assets/{id}', {params: {path: {id}}})` checks the path, params, body and result;
   - raw fetches keep their byte paths but import typed URL builders.
4. **`types.ts` becomes re-exports:** `export type Asset = components['schemas']['AssetRecord']`, plus UI-only types.
5. **WebSocket events:**
   - a pydantic discriminated union `Event` (`job.*`, `asset.*`, `document.changed`, `clip.*`, `group.changed`, `queue.state`, …) exported to
     JSON Schema;
   - converted to `events.d.ts` with `json-schema-to-typescript`;
   - `applyEvent` switches on a typed union.
6. **Recipes:** the `Recipe` discriminated union (`recipes.py`) goes into the spec, and `recipeFromPanel` / `recipeFor` / `runAi` return
   typed recipes instead of `Record<string, unknown>`.

**Slices.** (1) export script and CI freshness; (2) response models for meta/projects/assets/groups; (3) documents/clips/jobs/models/engine;
(4) typed client and migration of `session.ts`; (5) migration of the suite stores; (6) event union; (7) typed recipes.

**Tests.** `tsc -b` is the main check. A pytest asserts that every GET route has a `response_model` (except file/stream routes, which are
listed explicitly). The CI freshness step is demonstrated by a deliberately stale commit on a branch.

**Acceptance.**
- `schema.d.ts` is imported by `client.ts`.
- `types.ts` has no hand-written API interfaces.
- `grep "Record<string, unknown>"` finds no request bodies.
- CI fails on a stale spec.
- The headed tour (`edit_headed_check.py tour`) passes.

**Docs.** 06 §6 (generated client, event union); journal.

**Risks.**
- Response validation cost on hot routes (`/assets` pages). Measure; use `response_model_exclude_none` and keep thumbnails/files as
  `FileResponse`.
- Event schema churn. The event union is versioned together with the API.

## 3. H2 · Engine pipeline

### P2 · Plan → finalize → submit — 5 d

**Today.** `JobQueue._run_one` (`queue.py:450–605`) runs these steps in order:
1. start the engine;
2. refresh `object_info`;
3. `roster.scan` (every job);
4. fit and upload references;
5. document crop/upload (`_prepare_document_inputs` 608–700);
6. i2v frames (`_prepare_i2v_inputs` 787–804);
7. `compile_recipe` with the contract check;
8. submit and follow.

Completion is written three times: I2V at 543–552, document jobs at 553–562, T2I inline at 563–591, all sharing the same tail (done
fields, `record_job`, `persist`, `job.updated`, counters, `_last_group`). Document and i2v post-processing (`_finish_document_job`
702–760, `_add_result_layer` 762–784, `_finish_i2v_job` 806–843) also lives in `queue.py`. `/recipes/preview` covers only T2I and I2V and never
compiles a graph, so a contract problem shows up only after submission.

**Design** (`orchestrator/loom2/engine/pipeline.py`).

```
plan(recipe, roster, specs, variant) -> Plan                      # pure: no I/O, no engine
   Plan { kind, model_id, params (effective), warm_group, estimate {seconds, vram_gb, fit},
          needs: [RefInput | DocumentCrop | I2VFrame], summary, serialized_prompt }
finalize(plan, ctx: FinalizeCtx) -> Submission                    # I/O: fit/crop/upload, object_info, compile + contract
   Submission { graph, output_node, graph_hash, uploads, notes, problems }
Finisher protocol: AssetFinisher · DocumentFinisher · ClipFinisher · SelectionFinisher
   finish(job, outputs, ctx) -> FinishResult {asset_ids, events}
JobQueue._complete(job, result)                                   # the single shared tail
```

- `/recipes/preview` calls `plan()` for **every** kind. It also runs `compile_recipe` with placeholder inputs against the cached
  `object_info`, so `problems` appear in the panel before submission.
- `roster.scan` runs once at startup and again on `models.*` events or an mtime change of the model roots, not once per job.

**Slices.**
1. Extract the finishers unchanged into `engine/finishers.py`.
2. The single `_complete` tail.
3. Pure `plan()`; `/recipes/preview` for all six kinds.
4. `finalize()` absorbs the reference, document and i2v preparation.
5. `_run_one` ≤ 80 lines; cached roster scan.
6. Move `persist()` to `to_thread` behind an `asyncio.Lock`, keeping write order.

**Tests.**
- `plan()` unit tests per kind: effective params, needs, estimate.
- Finisher tests driven by fixture output files, without the fake engine.
- A test that preview `problems` equal submission `problems` for a broken recipe.
- All existing lifecycle and durability tests unchanged.

**Acceptance.**
- `queue.py` ≤ 650 lines (from 996).
- 115+ tests green.
- Rig: `scripts/m5_acceptance.py` (inpaint and segment) and `scripts/m6_acceptance.py` (Wan draft) pass with timings within ±10 % of the
  last journal run.
- The Edit AI panel shows an ETA and crop size from `/recipes/preview`.

**Docs.** 06 §3d (engine adapter: plan/finalize), §7 (key flows); `engine/AGENTS.md`.

**Risks.** A behaviour change hidden in a refactor. The graph-hash parity check (P1 slice 1) runs here too: all 17 `pin_review` variants
must compile to identical `graph_hash` before and after.

### P1 · Model descriptors as one data registry — 7 d

**Today.** Model knowledge is spread across the backend and the frontend:
- `graphs.py`: `ModelPreset`/`PRESETS` (6), `TE_ALTERNATES`, `VRAM_ESTIMATE_GB` (12 ids), `BASE_SECONDS`, `I2V_WEIGHTS`, `I2V_RULES`,
  `WAN_PRESETS`, `LTX_STEPS`, and the size rules `_mult16` and `effective_params` caps.
- The dev special case: `model_id == "flux2-dev-fp8mixed"` at three sites, plus `recipe_weights` 739–745.
- `recipes.py`: default ids per recipe, `inpaint_model_id` (string prefix logic), `warm_group`.
- `roster.py`: licence and variants, across 37 entries.
- `edit_ai.py`: its own ×16 rounding.
- `/capabilities` (`api.py:268–306`) lists only `PRESETS` models; the i2v tiers and the image tiers are hard-coded (298–299, 306);
  `wired = dev or klein`.
- The frontend hard-codes model ids in `GenerateSuite` (l.219 order, 233, 249–250, 114), `EditSuite` (263–266, 288, 315–332),
  `aiPanelStore`, `generateStore`, and `animateStore` (a duplicated `MODEL_RULES` table, 27–30).

**Design.**
- **`orchestrator/loom2/models/`:**
  - `spec.py` holds pydantic `ModelSpec`;
  - `specs/*.toml` has one file per model family (flux2, klein, wan22, ltx23, tools);
  - `registry.py` loads and validates the specs at import and cross-checks them against `ROSTER`.
- **`ModelSpec` fields:**
  - `id, family, label, wired, disabled_reason?`
  - `roles: {diffusion, te: {default, alternates[]}, vae, extra: {low_expert, loras[], projection, audio_vae…}}` — roster ids
  - `graph: flux2 | klein | wan22 | ltx23 | esrgan | birefnet | sam3` — names the builder
  - `recipes: {t2i?: {…}, i2i?: {distilled_ok}, inpaint?: {modes[]}, upscale?: {factor, refine_ok}, segment?: {prompts[]}, i2v?: {flf, beats}}`
  - `sampling: {steps, guidance, cfg, sampler, scheduler, weight_dtype, distilled, turbo {lora, steps}, json_prompt, conditioning_zero_out}`
  - `inputs: {refs_max, start_frame, end_frame, beats_max, mask}`
  - `geometry: {size_mult, frame_step, fps, frames, max_pixels, tiers {thumb, draft, hd, full}}`
  - `estimates: {vram_gb, base_seconds, turbo_seconds, per_megapixel}`
  - licence and variants come **from the roster** (one source).
- `graphs.py` builders read the spec instead of constants and id comparisons, and `recipes.py` defaults come from the registry. The
  `inpaint_model_id` prefix logic becomes `recipes.inpaint.modes` plus a spec flag.
- `/capabilities` becomes `registry.capabilities(variant, health, engine_enums)` and returns a typed `Capabilities` model (feeds P3):
  - every wired model, including tools and video;
  - new `inputs` / `options` / `geometry` blocks;
  - old keys kept for one release.
- **Mismatch policy:** recipes get `size_policy: snap_up | snap_down | error` (default `snap_down` to protect VRAM, D18). Violations return
  `422 {field, value, allowed}` and are shown by the panel next to the field.
- **Frontend:** every model id and rule table is derived from `caps`; controls are gated on `inputs`/`recipes`; `MODEL_RULES` is deleted.

**Slices.**
1. Spec schema; specs generated from today's constants; **parity test**: the 17 `pin_review` variants plus every existing compile test give
   identical `graph_hash` and identical `effective_params`.
2. Builders read specs; the constants are deleted; parity still holds.
3. `/capabilities` from the registry (old keys kept).
4. Frontend: hard-coded ids and `MODEL_RULES` removed; capability gating.
5. Mismatch policy and field-named 422s.
6. **Sweep test**: every spec × tier × recipe × option corner compiles against the fixture with zero problems; estimates are monotonic in
   pixels and frames.
7. Rewrite the `engine/AGENTS.md` add-a-model checklist: roster entry → spec → (builder if new family) → fixture recapture if new nodes →
   sweep → rig smoke.

**Tests.** Parity (slice 1), sweep (slice 6), registry validation (a spec referencing an unknown roster id fails at import), and an API test
of the 422 shape.

**Acceptance.**
- A test-only spec file (a fake Klein variant) appears in `/capabilities`, compiles and is selectable in Generate without touching Python
  code or the frontend.
- No `"flux2-dev-fp8mixed"` or `"klein"` string literal is left outside `specs/` and tests (grep check in CI).
- Rig smoke: dev T2I, Klein inpaint, Wan draft — times within ±10 % of the journal.

**Docs.** 04 §1b (spec next to the roster), 06 §3d, 09/10/11 (controls from capabilities), 13 (decision), `engine/AGENTS.md`.

**Risks.**
- TOML expressiveness for per-family quirks. Builders stay code; specs carry only data.
- Frontend regressions while hard-coded ids are removed. P6's smoke run covers the suites.

### P4 · Job `origin` echoed everywhere — 3 d

**Today.**
- `JobRecord` (`queue.py:52–75`) has no origin. Edit routing works only because `api.py:846` injects `document_id`.
- `asset.created` carries the `AssetRecord`, but nothing about where the request came from.
- `catalogueStore` ignores `asset.created` while a group or filter is active.
- `onClipReady` **always** switches Animate's player to the new clip.
- Two window events (`loom2:group-changed`, `loom2:asset-event`) are a second bus that only `PageView.tsx` uses.
- The Dock has no "go to origin".

**Design.**
- `JobOrigin {suite, surface, ref?, payload?}`, optional in `JobSubmit`, stored on `JobRecord` (schema version 2; a v1 `queue.json`
  loads with `origin=None`) and copied to `AssetRecord.origin` (asset schema bump; the index rebuild tolerates its absence).
- Set by callers:
  - Generate: `{generate, results}` or `{generate, ref-slot, n}`;
  - Animate: `{animate, clip}`;
  - Edit: `{edit, ai, doc_id}` (set server-side for `/documents/{id}/ai`);
  - Catalogue verbs: `{catalogue, group, gid}` for re-run/variations from a page.
- **Placement option** (an author decision; default off to keep D34's "everything lands in Unprocessed"): `origin.place_in: gid` puts the
  new assets into that group next to their source via `GroupStore._place`.
- **Frontend:**
  - Interim tiles filter by origin;
  - Animate auto-plays a new clip only when the origin matches the clip view the user is on, otherwise a toast with "Play";
  - the Dock job row menu gains **"Go to origin"**;
  - `PageView` subscribes to the stores and the two window events are deleted.

**Slices.** (1) Backend field, persistence, events and v1 compatibility; (2) frontend callers set origin; Dock "Go to origin";
(3) Animate auto-select rule and Interim filtering; (4) the window-event bus removed; (5) the optional placement setting, if the author
accepts it.

**Tests.**
- A v1 `queue.json` fixture loads.
- Origin survives a restart (durability test).
- `job.*` and `asset.created` frames carry it.
- The placement policy places next to the source.
- Frontend vitest (P6) for `applyEvent` routing.

**Acceptance.**
- Start an Animate job, switch to the Catalogue, finish: no forced player switch; the toast offers Play.
- "Go to origin" on a Generate job opens Generate with that batch shown.
- `grep "loom2:"` in `src/` finds no window events.

**Docs.** 06 §5 (Job, Asset), 07 §5 (job states), 13 (placement decision).

## 4. H3 · Safety and tests

### P9 · Authenticate GETs and the WebSocket — 2 d

**Today.**
- `token_gate` (`api.py:234–239`) checks only POST/PUT/PATCH/DELETE.
- 36 GET routes are open, including `/settings`, project paths, `/models` absolute paths, prompts in `/jobs` and `/assets`, document pixels,
  selection, `/blobs`.
- `/docs`, `/redoc` and `/openapi.json` are served.
- The WS token travels as `?token=`.
- Media URLs (`thumbUrl`, `assetUrl`, `fileUrl`: 32 uses in 11 files) carry no credential.
- There are no stored secrets (the HF token stays in `HF_HOME/token`).

**Design.**
- Gate **every** route except `/health`.
- **API GETs** use the existing header: `call()` already sends `X-Loom-Token` on GETs, and so do `editorStore`'s raw fetches.
- **Media GETs used by `<img>`/`<video>`** — `/thumbs`, `/assets/{id}/file`, `/clips/{id}/proxy.mp4`, `/clips/{id}/frames/*`,
  `/documents/{id}/thumbnail`, `/blobs/*` — accept a separate per-launch **read-only media key** as `?k=`. The key is issued in
  `backend_info` alongside the token. A leaked media key exposes pixels but cannot mutate anything or read settings, jobs or prompts.
  Uvicorn access logging is configured to drop query strings.
- **WebSocket:** connect without a credential, then send `{"type":"auth","token":…}` within 2 s, otherwise close with 4401.
- `docs_url`/`redoc_url`/`openapi_url` are disabled unless `LOOM2_DEV=1` (`export_openapi.py` from P3 calls `app.openapi()` directly).
- **Frontend:** the media key is appended in the three URL helpers. Raw media paths are routed through the helpers first (`Player.tsx:20`,
  `AnimateSuite.tsx:307`, `EditSuite.tsx:394`).
- **Scripts:** `acceptance_common` helpers send the header on GETs; `csp_check` and `edit_headed_check` pass the token through the URL
  bootstrap as today.

**Slices.** (1) Server gating, media key, WS auth message and disabled docs; (2) frontend helpers; (3) scripts.

**Tests.**
- **Route matrix**: iterate `app.routes`; every GET without credentials is 401 except `/health`; media routes accept `k` and refuse `k` on
  non-media routes; mutating routes refuse `k`.
- The WS closes with 4401 without the auth message.
- The existing `test_api` keeps passing.

**Acceptance.**
- The matrix test passes.
- `scripts/m1_acceptance.py` and the headed tour pass with no broken images.
- `curl http://127.0.0.1:<port>/settings` returns 401.

**Docs.** 06 §2 (security paragraph), 13.

### P6 · Frontend test harness — 5 d

**Today.** There is no vitest or Playwright. CI runs pytest and `npm run build` per variant. Browser checks are Python + raw CDP with Edge
(`csp_check.py`, `edit_headed_check.py` 821 lines). Dev hooks `__loom2Commands`, `__loom2Session`, `__loom2Animate`, `__loom2App` and
`__loom2Editor` exist behind `import.meta.env.DEV`.

**Design.**
1. **Vitest (jsdom)**, `npm test`, run in CI. First extract the pure maths that today lives in component closures:
   - `catalogue/pageLayout.ts`: `toPage`, `fit`, marquee hit test, resize, z-order from `PageView.tsx` l.71–80, 130, 194, 222–223;
   - export `qs()` from `catalogueStore`, `planSize` from `EditSuite`, and `curve`/`channelMap` from `adjustFilters`.
2. **Unit suites (≈ 60 tests):**
   - `commands.ts`: `parseChord`, `matchChord`, `keyLabel`, plus **the D32 audit as a test** — every registered command has a non-empty
     placement, and no two commands in one scope share keys;
   - `transform.ts`;
   - `generateStore`: `cleanTree`, `treeFromJson`, and `recipeFromPanel` ↔ `panelFromRecipe` round trip;
   - `animateStore`: `recipeFor`, `sizeFor` snapping against a `caps` fixture;
   - `filters.ts`, `albumStore` (`flatGroups`, `pathOf`);
   - `editorStore` reducers that need no canvas (`findNode`, the `mergeServerLayers` stack merge with a fake `LayerPixels`);
   - `session.applyEvent` routing with spy stores.
3. **E2E smoke** with **Playwright using `channel: 'msedge'`** (Edge ships on the Windows CI runners). The global setup starts:
   - the orchestrator with `LOOM2_TOKEN`;
   - **`tests/fake_comfy.py` as a standalone process** (a new `__main__` taking a port and a mode);
   - a small synthetic project (`make_synthetic_assets.py --count 200`);
   - `vite preview` of a build with `VITE_E2E=1`, which keeps the dev hooks.

   Scenarios:
   - open the project → the grid shows tiles;
   - Keep/Reject via the context menu;
   - drag a tile to a group page;
   - Generate (Klein 4B) → the fake engine returns an image → it lands in Unprocessed;
   - Edit opens from an asset with `?renderer=webgl`, brushes a stroke, saves;
   - Animate fills start/end slots.

   WebGPU-specific checks stay in `edit_headed_check.py`.
4. **Perf script** (`frontend/e2e/perf.spec.ts`). It measures startup to the first painted tile, Catalogue → Edit → Catalogue switch time,
   Edit re-entry time and 10k scroll frame pacing. Results go to `bench/perf/<date>.json`, with a comparison script against the last
   baseline (ArtCraft's `perf:desktop` method). Its numbers feed P5 and P10.

**Slices.** (1) Vitest scaffold and extractions; (2) the unit suites; (3) the standalone fake engine and Playwright setup; (4) smoke
scenarios in CI (both variants); (5) the perf script and first baseline in the journal.

**Acceptance.**
- CI runs vitest and the Playwright smoke on both variants in under 6 extra minutes.
- A deliberately broken `matchChord` fails CI.
- A command registered without a placement fails CI.
- The first perf baseline is recorded in the journal.

**Docs.** 06 §9 (test tiers), 12 (CI), `frontend/src/frame/AGENTS.md`.

**Risks.**
- Headless Edge cannot present WebGPU (known). The smoke run forces WebGL2.
- CI time. The smoke run uses 200 assets and Klein through the fake engine only.

## 5. H4 · Responsiveness

### P5 · Keep heavy stages alive, lazy-load suites — 3 d

**Today.**
- `Stage.tsx`, `Strip`, `Panel` and `Inspector` render only the active suite, keyed by `suite.id`.
- Leaving Edit destroys the Pixi `Application` (`EditorCanvas.tsx:185–277`); returning re-inits it, re-runs the WebGPU probe and refits.
- Animate's `Player` reopens and re-decodes the proxy.
- `SUITE_DEFS` imports all suites statically; the Mediabunny chunk (`init-*.js`, 658 KB) is modulepreloaded; `spikes.html` is a production
  input.
- `edit_headed_check.py perf` has no Edit/Animate switch-back timing.

**Tension.** The feasibility research flags that WebView2's GPU memory comes out of the same 16 GB ComfyUI needs (the engine already runs
with `--reserve-vram 1.5`). Keeping the editor alive must not cost generation speed, so the plan measures first and adds a release policy.

**Design.**
- **Step 0, measure** with P6's perf script plus a VRAM probe: ComfyUI `/system_stats` free VRAM with Edit (6×4K document) visible,
  hidden-and-alive, and destroyed.
- `SuiteDef.keepAlive?: boolean`, true for Edit and Animate:
  - `Stage.tsx` renders every visited keep-alive stage, hiding inactive ones (`hidden` + `display:none`);
  - `EditorCanvas` stops the ticker (`app.stop()`) and ignores zero-size resizes while hidden;
  - `Player` pauses and keeps its sink.
  - Strip, Panel and Inspector stay keyed (they are cheap).
- **GPU release policy:** destroy the hidden editor app (today's path) when
  - it has been hidden longer than `ui.editKeepAliveMin` (default 10 min), or
  - a GPU job is admitted while the engine's free VRAM is below `engine.reserve_vram_gb + 1 GB`.

  Re-entry then pays today's cost. Both thresholds come from the Step 0 numbers.
- **Lazy suites:** `React.lazy` for Edit, Animate and Models (Stage/Panel/Inspector/Strip components) behind a skeleton Suspense. Mediabunny
  loads with Animate. `spikes.html` is built only when `LOOM2_SPIKES=1`.

**Slices.** (1) Measurements and journal; (2) keep-alive with ticker pause; (3) release policy; (4) lazy suites and the spikes input
removed; (5) re-measure.

**Acceptance.** Target values are set from Step 0 and recorded before slice 2:
- Edit switch-back ≤ 100 ms with the document intact (selection, zoom, tool).
- First Catalogue paint improves (expected: no Mediabunny preload).
- The 6×4K composite p95 does not regress (≤ 7.1 ms, M7).
- A GPU job admitted under VRAM pressure frees the hidden editor (log line and test).
- The headed tour passes.

**Docs.** 05 (frontend engine), 07 §1 (frame), 10 (Edit lifecycle), journal.

### P10 · Idle pre-save in Edit before AI verbs — 3 d

**Today.** `runAi` (`editorStore.ts:270–284`) does the following:
- awaits `save()`, which **always** PUTs the whole stack, uploads every dirty layer sequentially, POSTs `/save` and toasts "Saved", even
  when nothing changed;
- then PUTs the full selection (one byte per pixel, empty body when there is none);
- then posts `/documents/{id}/ai`.

Dirty tracking is per layer (`LayerPixels.dirty`) plus `docDirty`. Autosave runs every 120 s.

**Design.**
- **Fast path:** `save({quiet})` returns at once when nothing is dirty and the selection is unchanged; it toasts only for user-initiated saves.
- **Idle flush:**
  - 1.5 s after the last commit, with the pointer up and nothing in flight, PUT the stack (revision-guarded, with the C1/C20 409 merge path
    unchanged) and dirty layers, in parallel with a concurrency of 2;
  - selection uploads track a `selectionVersion`.
  - Slice 1 verifies whether AI jobs read the open-document state or the saved ORA. If they read the ORA, the idle flush also calls
    `POST /save`; otherwise `/save` stays with explicit save, autosave and close.
- **AI click:** await an in-flight flush if any, yield one frame (`requestAnimationFrame`) so the busy state paints, then post the job.
- **Region preview** and the "size it will send" readout come from the already-saved state.

**Slices.** (1) Confirm what the AI path reads (a test in `test_edit_ai_m5`); (2) the fast path and quiet saves; (3) the idle flush and
selection versioning; (4) the AI click path; (5) a headed timing mode.

**Tests.**
- Vitest (P6) for the dirty-state machine: idle → flushing → clean; a stroke during a flush re-dirties.
- A pytest that an AI job after a stack PUT, without `/save`, uses the PUT state (or the opposite, per slice 1).
- The 409 merge test still passes.

**Acceptance.** A new `edit_headed_check.py aiclick` mode:
- Clean document: Inpaint click → job posted ≤ 50 ms.
- A 4K layer edited 2 s earlier: ≤ 100 ms.
- No "Saved" toast on AI clicks.
- The candidate strip still fills correctly.

**Docs.** 10 §4 (AI panel flow), journal.

## 6. X1 · Flow (alongside Story L1–L2)

### P11 · The library as the send-to hub — 4 d

**Today.**
- `frame/drag.ts` provides pointer drags with a ghost: an image, an "N items" label and a `.can-drop` border.
- Drop targets: TopBar suite tabs (Edit opens, Generate adds references, Animate sets start/end), Generate `RefSlots`, Animate slots and
  beats, the Edit canvas and empty stage, Places rows, pane bodies, PageView.
- The loupe bar shows only `cat.keep`, `cat.reject`, `cat.edit` and `cat.reference`.
- The full verb set is in `catalogueCommands.ts` (`tileMenu`, Inspector buttons).

**Design.**
1. **Loupe as hub.** A `CommandRow` with Keep / Reject / rating, Edit, Reference, Animate ▾ (start / end), Re-run, Variations, Duplicate,
   Move to group…, Lineage, Reveal, with an overflow menu at narrow widths. All are existing commands, so D32 holds.
2. **Drop feedback.** `DropTarget` gains an optional `describe(payload) → {ok, label, reason?}`, for example "Add as reference 3 of 4",
   "Set end frame", or "Clips can't be references". The ghost shows ✓ or ✕ with that text while hovering.
3. **Spring-loaded suite tabs.** Hovering a suite tab with a drag for 600 ms switches suite and the drag continues, so a tile can be carried
   into a specific reference slot or Animate slot. The tab's existing drop behaviour stays for quick drops.
4. **Caps-aware limits.** Multi-tile drops on Generate respect `refs_max` from P1 and say how many were added.
5. **Edit layers panel** as a drop target: insert a layer at the drop row.

**Slices.** (1) Loupe bar; (2) `describe` and the ghost badge; (3) spring-loaded tabs; (4) limits and the layers-panel target.

**Tests.** Vitest for `describe` logic per target. Playwright (P6): drag a tile → hover the Generate tab → drop on slot 2 → the recipe
preview shows the reference.

**Acceptance.**
- Every send-to verb is reachable from the loupe bar and the context menu.
- Rejected drops explain why.
- The drag-hover switch works across all three suites.

**Docs.** 07 §3b–§3c, 08 (Catalogue loupe), 09 §3a (references).

### P15 · Quick actions on empty states and the Inspector — 2 d

**Today.**
- `EmptyGrid` (`CatalogueSuite.tsx:102–108`) shows text only.
- The Edit empty stage has New document / Open the Catalogue / Recent documents; Animate's is text only.
- There is no `?tool=` deep link.
- Setters exist: `setSuite`, `setRailTab`, `useEditor.setTool`, `useAiPanel.set({op})`, `openFromAsset`, `setStart`/`setEnd`, `addRef`,
  `loadFromAsset`.

**Design.**
- `openWith(assetId?, {suite, tool?, aiOp?, slot?})` helper plus `?tool=` / `?ai=` deep links.
- **Empty states** become card rows: *Generate an image* · *Import files* · *New document* · *Open a project* (Catalogue);
  *Animate from an image* (Animate).
- A **"Start from this image"** section in the Catalogue Inspector:
  - Remove background → Edit with AI Select · Subject preselected;
  - Upscale ×2 → Edit AI panel `upscale`;
  - Animate from here;
  - Variations;
  - New angle… (after P14).
- Every card is a registered command, so it appears in the palette and the D32 audit.

**Acceptance.**
- Each card reaches the right suite and tool in one click.
- P6's command audit passes.
- `?suite=edit&tool=ai&ai=select` works as a deep link.

**Docs.** 07 §3c, 08, 10.

### P12 · Reference deck with `@`mentions — 5 d

**Today.**
- `RefSlot {asset_id, note?}`: the note has **no UI** and the compiler ignores it.
- `graphs.py:428` silently truncates references beyond `max_refs` (10 for dev, 4 for Klein).
- The only mention convention is plain text ("reference image 1").
- Groups are available through `GET /groups/tree` and `flatGroups`.

**Design.** Deliverable now on **groups**; the Story workspace later swaps in AssetProfiles (14) behind the same resolver.
1. **Notes:**
   - inline captions on reference slots;
   - serialised per model family by the spec (P1): dev JSON gets a `references: [{index, note}]` section, Klein prose gets "Image N shows …";
   - checked on two bench prompts for adherence before becoming the default.
2. **Mentions:**
   - typing `@` in the Text field or tree fields opens a picker of groups (later characters);
   - a chip is inserted;
   - on submit, `resolve_mentions` turns each chip into references (cover first, then items in page order), deduplicated and capped by
     `inputs.refs_max`.
3. **No silent truncation:** `/recipes/preview` reports `refs_dropped` and the panel warns; submission with more references than allowed
   returns 422 under `size_policy=error`.
4. **Provenance:** the recipe and manifest record `mentions: [{group_id, revision, asset_ids}]` — lineage stamped at write time (loom lesson 7).

**Slices.** (1) Notes UI and serialisation (with the bench check); (2) truncation reporting; (3) the mention picker and chips; (4) the
resolver and provenance.

**Tests.**
- Resolver unit tests (cap, dedupe, empty group).
- A preview `refs_dropped` test.
- The manifest records `mentions`.
- Vitest for chip parsing.

**Acceptance.** "@hero walks into @tavern" with two groups resolves to references visible in the preview; the generated asset's manifest
lists both groups at their revisions; a rig bench prompt with notes is recorded in the journal.

**Docs.** 09 §3a, 14 (adoption note: mentions resolve to AssetProfiles), 13.

### P16 · Remappable keys — 3 d

**Today.**
- `Command {keys?, alt?, when?, placement}` lives in `REGISTRY`, alongside `parseChord`/`matchChord`/`handleKeyFor`, a help overlay and a
  palette.
- Several keys are hard-coded outside the registry:
  - `useKeyboardMap`: Ctrl+K, Shift+F10, Esc, Tab;
  - the Edit hook: `\`, 1–4 / Enter for candidates, 0–9 for brush opacity;
  - space-pan;
  - Loupe Ctrl+0/1, Compare Tab, grid arrows.
- `TOOL_KEYS` in `editorStore.ts:24` is unused.

**Design.**
1. Move the hard-coded keys into the registry. Arrows, Esc, Space and Tab are marked `fixed: true` (not remappable) but are listed in help.
2. Overrides live in `loom2.keys` (`{commandId: chord | null}`), resolved override → default.
3. A conflict checker per scope plus global; two commands may share a key only if their `when` gates are mutually exclusive (declared, as
   ArtCraft does).
4. **Settings → Keyboard:** search, list by scope, click to record a chord, conflict warnings, reset per command or all.
5. Tooltips, menus, help and the palette already read `keyLabel` from the registry, so they follow automatically.
6. Delete `TOOL_KEYS`.

**Tests.** Vitest: override resolution, conflict detection, persistence migration, fixed keys refused.

**Acceptance.** Remap Keep to `G`: the context menu, tooltip and help show `G`; `G` keeps; the old key does nothing; a conflicting remap is
refused with the other command's name; the setting survives a restart.

**Docs.** 07 §4 (keyboard map), 13. Priority stays low (mouse-first, D19). Revisit when a pen arrives.

## 7. Spikes (one week of rig time, after H2)

Each spike follows 12 §1: a driver under `engine/spikes/`, frozen inputs under `bench/`, a sheet, and a journal entry with timings and a
decision.

| Spike | Question | Methods | Pass bar | Effort |
| --- | --- | --- | --- | --- |
| **E10** Stage → image | Which conditioning makes a posed 3D blocking come out right on 16 GB? | (1) Klein 9B + clay render as `ReferenceLatent` + prompt (no download); (2) Klein base 9B + RefControl pose LoRA (Apache-2.0); (3) Z-Image Turbo + Fun ControlNet Union 2.1 lite via core `ModelPatchLoader` + `ZImageFunControlnet`, then Klein I2I 0.4–0.6; (4) optional, `full` only: dev + FLUX.2 Fun ControlNet Union (needs a **custom node** — a policy decision) | pose PCK@0.1 ≥ 0.8 (core `SDPoseKeypointExtractor` vs the rendered keypoints); depth Spearman ≥ 0.85 (DA3-BASE, Apache); warm ≤ 1.5× the method's plain T2I; no OOM; blind "same blocking" ≥ 8/10 | 4 d (incl. a Three.js pass exporter in `frontend/src/spikes/`) |
| **E11** Stage → video | Can a pass sequence drive i2v? | LTX-2.3 + IC-LoRA Union (depth + pose; nodes in core); fallback Wan 2.2 Fun Control | no OOM; ≤ 2× plain LTX (141 s / 5 s); pose followed in ≥ 4/5 clips | 2 d |
| **E12** Angles | A new viewpoint of an existing image, locally | A: Qwen-Edit 2509 fp8 + Multiple-angles LoRA + Lightning (**all on `D:`**); B: 2511 Q4_K_M + fal Multiple-Angles LoRA (~14 GB download); C: Klein 9B prompt-only; D: DA3 depth → mesh → re-render → Klein/LanPaint fill | correct move ≥ 7/10 per move; ArcFace identity ≥ 0.5 (evaluation only); warm ≤ 60 s, cold ≤ 180 s; kill B if warm > 90 s | 3 d |
| **E13** Timeline | Custom single lane, as 14/P5 plans (OpenCut is not embeddable) | DOM/React single lane with integer frame ticks; optional `opencut-wasm` compositor check in WebView2 | 10 × 5 s clips at 24 fps scrubbed with ≤ 1 frame error; smooth trim with 50 clips; one crossfade preview; EDL + FCPXML import into Resolve; ≤ 300 KB bundle growth | 2 d |
| **E14** Image → mesh | Props from a cut-out, on AMD 16 GB | TRELLIS.2 and Pixal3D via core nodes (`nodes_trellis2.py`, pure torch), 512 then 1024; bf16 if int8 fails on ROCm. **Hunyuan3D excluded** (licence excludes the EU) | no OOM at 1024; warm ≤ 120 s, cold ≤ 300 s; ≤ 50k faces after `DecimateMesh`; silhouette IoU ≥ 0.85; plausible back ≥ 3/5 | 2 d |

**Licence checks inside the spikes:**
- the Z-Image weights and their VAE (verify per file);
- DINOv3 (Meta's custom licence: `full` only until reviewed);
- SAM 3D Body (if used for photo → pose);
- the Quaternius mannequins (CC0; **Mixamo assets must not ship**);
- Qwen and RefControl LoRAs (Apache).

Each result is recorded against D17 (EU-first) and D26 (variants).

## 8. ST · Stage suite (P13) — 25–30 d, with Story L3

**Gates.** E10 (and E11 for the video half) decided; a UI document `16-ui-suite-stage.md` approved (D12); the P5 measurements decide
whether the Stage is keep-alive or released when hidden (the feasibility research recommends tearing down the Three canvas when hidden to
protect VRAM).

**Architecture.**
- **Frontend:** `three` (vanilla) in `suites/stage/`:
  - an engine behind an event bus → bridge → Zustand store (ArtCraft's one-way flow, re-implemented);
  - its **own canvas and WebGL2 renderer**, separate from Pixi (PixiJS's shared-context guide is WebGL-only and Edit prefers WebGPU);
  - canvas hosts never conditionally unmounted;
  - command-pattern undo serialised through a promise chain.
- **Backend:** `StageStore`:
  - `stages/<id>.json` per project (objects by asset id, transforms, rig poses, cameras, keyframes, `schema_version`, `revision` with 409
    like documents);
  - routes `routes/stages.py` (CRUD, passes upload);
  - lineage kinds `stage-pass` and `stage-shot`.
- **Assets:**
  - bundled CC0 Quaternius base mannequins;
  - image planes from Catalogue assets, with BiRefNet cut-outs one click away (D33);
  - meshes from E14 if it passes.

**Milestones.**

| Slice | Content | Effort |
| --- | --- | --- |
| ST1 Scene | suite registration (Rail: Library · Outliner · Cameras; Stage: viewport; Inspector: object / camera), library drop with raycast placement, gizmos (mouse-first: visible move/rotate/scale buttons plus context menu), outliner with lock/visibility, cameras with focal length in mm, aspect and size from `project.json` (D18), framing guides, save/reopen via `StageStore` | 8 d |
| ST2 Posing | FK on picker joints, **analytic two-bone IK** for arms and legs (~100 lines; `CCDIKSolver` as fallback), pose presets (JSON library: stand, sit, walk, point, reach, look), mirror pose, reset | 6 d |
| ST3 Passes → image | clay/beauty, linear-disparity depth (custom shader, not `MeshDepthMaterial`), normals, OpenPose COCO-18 drawn client-side from bone positions, object-ID masks; uploaded as `stage-pass` assets; recipe `StageShot {stage_id, camera_id, passes[], method (E10 winner), prompt, refs}` with spec entries (P1) and graph builder; results land with lineage to the passes and `origin` (P4) back to the stage | 8 d |
| ST4 Shots | camera and object keyframes → pass sequences → the E11 winner (LTX IC-LoRA) → clip; shot ↔ Story L3 link | 6 d |

**Tests.**
- `StageStore` durability (atomic writes, 409).
- Pass exporters (vitest on keypoint projection and depth normalisation).
- `StageShot` compile in the sweep (P1).
- Fake-engine lifecycle.

**Acceptance** (`scripts/st_acceptance.py`, rig):
- Create a stage, place two mannequins and a set plane, pose with IK, frame a camera, export passes.
- Generate with the E10 method: PCK ≥ 0.8 on the result.
- Kill the app mid-job → relaunch resumes paused.
- Reopen the stage and it is identical.
- One ST4 shot renders a clip that follows the camera move.

**Docs.** New `16-ui-suite-stage.md`; 03 (scope), 04 (conditioning models), 06 (StageStore, routes), 14 (Shots & Takes uses Stage), 13.

## 9. Builds after the spikes

### P14 · Viewpoint / angles verb — 6 d (after E12 passes)

- **Recipe** `Reangle {asset_id, azimuth, elevation, distance, method, candidates}`.
- **Specs and roster** for the winning method. On-disk option A: Qwen-Image-Edit 2509 fp8 (20.4 GB), the Multiple-angles LoRA (236 MB),
  Lightning 4-step (850 MB), the Qwen2.5-VL 7B fp8 encoder; all Apache.
- **Builder** mapping the controls to the LoRA's prompt vocabulary (B's parametric `<sks> front view eye-level shot medium shot` maps 1:1
  to UI controls).
- **UI:** a "New angle…" command on tiles, the loupe and Edit documents, opening a Panel with an **orbit sphere** (drag azimuth / elevation),
  distance presets (close-up · medium · wide) and candidates 1–4. Results land next to the source (P4 origin, `lineage_kind = reangle`).
- **Scheduling:** Qwen's ~20 GB streams on 16 GB, so reangle jobs get their own `warm_group` and the Dock shows the cold-load cost.
- If E12's method D (reprojection) wins for interiors, it ships as a second method reusing the Stage renderer.

**Acceptance.** E12's bars reproduced through the app on the 10-shot set, in `scripts/reangle_acceptance.py`.

### P17 · Single-lane timeline — 10 d (after E13 passes; inside Story P5)

- A `timeline` document (`timelines/<id>.json`, integer frame ticks, `schema_version`, `revision`).
- Single lane with overlap transitions (R157); clips from the Catalogue (master PNG sequences plus GOP-6 proxies); scrub through the
  existing Mediabunny player and the C24 frame-thumbnail endpoint.
- Export: EDL + FCPXML (R151/R152) and a draft render via ffmpeg on the CPU; fps conform per D27 (RIFE at export).

**Acceptance.** E13's bars plus a 60-second sequence reopened after restart and imported into Resolve with correct cuts.

### P18 · Image → mesh props — 6 d (after E14 passes, and only after ST1)

- Asset kind `mesh` (GLB) in the catalogue, with a thumbnail rendered client-side by the Stage renderer (or core `RenderMesh`).
- Recipe `ImageToMesh {asset_id, method (TRELLIS.2 | Pixal3D), resolution}` → `DecimateMesh` → GLB; lineage `image-to-mesh`.
- Roster entries with licences (TRELLIS.2 MIT, Pixal3D MIT, DINOv3 custom → `full` only until reviewed). Hunyuan3D files are added to an
  **ignore list with the licence reason**, so `/models/unlisted` stops suggesting them.
- The Stage library accepts meshes.

**Acceptance.** Five E14 inputs become posable props in a Stage scene through the app; licence fields are present in their manifests.

## 10. Decisions to record if accepted

| Proposal | Decision text (draft) |
| --- | --- |
| P7 | Subsystem `AGENTS.md` files with a verified-at line, path-checked in CI |
| P19 | One `VERSION` source, build metadata in `/version` and About, draft releases on tags |
| P8 | Orchestrator routes split per domain; blocking work off the event loop |
| P3 | Generated API and event types are the frontend contract, freshness-checked in CI |
| P2 | Recipes run as plan (pure) → finalize (I/O) → submit; preview = plan for every kind |
| P1 | Model knowledge lives in specs; `/capabilities` is generated from them; mismatch policy with field-named 422s |
| P4 | Jobs and assets carry `origin`; placement-in-group optional (author's call on D34) |
| P9 | Every route authenticated; read-only media key for media URLs; WS auth message |
| P6 | Vitest + Playwright-on-Edge smoke + perf baselines in CI |
| P5 | Edit/Animate stages kept alive within a VRAM release policy; suites lazy-loaded |
| P10 | Edit flushes on idle; AI verbs never wait for a full save |
| P11, P15 | Loupe is the send-to hub; drops explain themselves; quick actions as commands |
| P12 | `@`mentions resolve to reference sets with provenance; no silent reference truncation |
| P16 | Keys remappable with conflict checks; mouse placements remain mandatory |
| E10–E14 | Spike results decide P13's conditioning stack, P14's method, P17's timeline shape, P18's model; Hunyuan3D excluded under D17 |
| P13 | Stage suite: Three.js stage, IK + presets, control passes, `StageStore` files |
