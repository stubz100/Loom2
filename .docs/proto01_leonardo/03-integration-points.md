# 03 · Integration points: where Leonardo plugs into loom2

Status: **proposal, 2026-10-08.** Mapped against the working tree on that date (`main` at 4e0db08 plus the uncommitted D34
catalogue pass); line numbers drift, function names do not. Read 01 (the API) first.

## 1. Position

loom2 is local-first by decision: "cloud" is an MVP non-goal (`../proto01/03-vision-scope-and-mvp.md` §4), ComfyUI is the
sole engine (D2, D28), and the ArtCraft review explicitly did not copy cloud providers
(`../artcraft/07-loom2-comparison.md` §5). Adding Leonardo **revises** that stance, so it is decision LD1 in 05, not an
implementation detail. The integration below is shaped so that the revision is as small as possible:

1. **The orchestrator is the only caller.** The webview never talks to Leonardo, never holds the key and never displays a CDN
   URL. The CSP stays loopback-only and `scripts/csp_check.py` keeps passing unchanged.
2. **Leonardo is a second engine behind loom2's own queue**, not a separate app area. A cloud job is a loom2 job: same
   recipe, same job dock, same finalisers, same assets, same lineage.
3. **Files stay the truth.** Every output is downloaded into the project and gets a manifest; Leonardo is never the store.
4. **Local stays the default.** Cloud is off until the author enables it and enters a key; every cloud model is labelled as
   such wherever it can be picked; nothing falls back to the cloud automatically.
5. **Every cloud job states what leaves the machine and what it costs** before it runs, and records what it cost after.

```
┌──────────────────────── Orchestrator ────────────────────────────────────────────┐
│ POST /jobs ─► JobQueue.submit ─► validate (roster │ cloud registry) ─► guards     │
│                                   (disk · VRAM for local · spend for cloud)       │
│        ┌───────────── GPU lane (1 job) ─────────────┐ ┌── cloud lane (N jobs) ──┐ │
│        │ ComfyEngine: upload · /prompt · WS events  │ │ LeonardoEngine: inline / │ │
│        │ · /history · engine_out/loom2/<job>        │ │ upload · create · poll · │ │
│        └──────────────────────┬─────────────────────┘ │ download → engine_out/   │ │
│                               └──────────┬────────────┴───────────┬─────────────┘ │
│                          shared finalisers: ingest_file · ClipStore · paste-back  │
└───────────────────────────────────────────────────────────────────────────────────┘
        │ loopback HTTP + WS (unchanged)                       │ HTTPS (new, orchestrator only)
     webview                                          cloud.leonardo.ai · cdn.leonardo.ai
```

## 2. Orchestrator

### 2a. The engine seam (does not exist yet)

06 §3d describes an `Engine` adapter (`capabilities / estimate / submit / events / cancel / free / health`), but it was never
built: `JobQueue._run_one` (`orchestrator/loom2/queue.py`, ≈ 450–605) calls `ComfyClient` directly and branches on recipe type.
The only trace of the idea is the unused `JobRecord.engine: str = "comfyui"` (`queue.py:58`).

| Step in `_run_one` today | ComfyUI-specific? | With Leonardo |
| --- | --- | --- |
| `engine.ensure_running()`, `_ensure_ws()`, `_object_info_fresh()`, `roster.scan()` | yes | skipped for cloud jobs |
| reference inputs: `_fit_reference()` then `client.upload_image()` | the upload only | `_fit_reference()` reused; bytes inlined as BASE64 or uploaded via `/v1/init-image` |
| document inputs: `_prepare_document_inputs()` — crop / plan / mask in PIL, then `upload_image` (≈ 694–696) | the upload tail only | the PIL "work" half reused unchanged (it yields `plan` and `alpha_mask` for paste-back) |
| `compile_recipe()` → `Compiled{graph, …, graph_hash, summary, serialized_prompt}` (`engine/graphs.py:682`) | yes | `compile_leonardo()` → the same `Compiled` shape with `graph` = the request body |
| `client.queue_prompt()` → `job.prompt_id` | yes | `POST /v2/generations` → `job.remote_id` (generation id) |
| `_follow()` — WS events, stall watchdog, `/history` fallback | yes | poll `GET /v1/generations/{id}` with back-off; per-model timeout replaces the stall watchdog |
| `_outputs_from_history()` → files under `engine_out/` | yes | download each result URL to `engine_out/loom2/<job_id>_<n>.<ext>` |
| finalisers: T2I inline ingest, `_finish_document_job()`, `_finish_i2v_job()` | **no** — they take files on disk | reused; video needs one adapter step (2f) |
| `_cleanup_job_files()`, `_reconcile_leftovers()` | no | reused because downloads land in the same place |

**Proposal (slice L1):** extract the seam first, with no behaviour change, then add the second implementation:

```
orchestrator/loom2/engine/
  base.py        # Engine protocol: prepare(job, recipe) · start(job) · follow(job) · outputs(job) · cancel(job) · health()
  comfy/…        # today's code moved behind the protocol (graphs.py, contract.py, client.py, supervisor.py)
  leonardo/
    client.py    # httpx.AsyncClient: create, create_sync, get_generation, delete_generation, init_image, me, models
    registry.py  # cloud model registry (2c) + live /v2/models schema cache
    compile.py   # recipe → request body; validation against the model's JSON schema
    engine.py    # LeonardoEngine: inputs, create, poll, download, cost capture
```

### 2b. Queue: a second lane

| Concern | Today (`queue.py`) | Change |
| --- | --- | --- |
| Scheduling | one runner, `_run_loop` / `_next()` with warm-group affinity; strictly one job at a time | a **cloud lane**: its own runner with `settings.leonardo.max_concurrent` (default 3, Leonardo allows 10). The GPU lane is untouched, so a 5-minute Kling job never blocks a Klein inpaint |
| VRAM gate | `submit()` fails a job whose `estimate_vram_gb()` exceeds the budget; unknown ids default to 12 GB (`graphs.py:712–717`) | skipped for `engine == "leonardo"`; `/recipes/preview` reports cost instead of VRAM fit |
| Engine selection | `JobRecord.engine` never set | set in `submit()` from the model id's registry (roster → `comfyui`, cloud registry → `leonardo`) |
| Durability on unclean shutdown | `load()` re-queues a running job with `prompt_id=None`, `retry_count+1` | a cloud job that has a `remote_id` is **resumed** (poll again), never re-created — re-creating would bill twice. A cloud job without one is re-queued as today |
| Cancel | `client.interrupt()` | stop following, mark cancelled, then `DELETE /v1/generations/{id}` once it ends (01 §3); the UI says the job may still be charged |
| Pause on failure | `_engine_unavailable()` pauses the whole queue | provider failures (key rejected, balance empty, repeated 5xx) pause **the cloud lane only** and raise `provider.state` |
| Retries | none automatic | 429 / 5xx / network: bounded back-off **inside** the job; never a second `create` once one may have succeeded (a create that timed out is resolved by listing recent generations — unverified, L0) |

### 2c. A cloud model registry next to the roster

The roster (`orchestrator/loom2/roster.py`) is a list of **weight files** with sha256, folder and health; every check in it
(`scan`, `resolve`, `require`) assumes a local file. Cloud models are not weights. A separate, data-driven registry keeps both
honest:

```python
class CloudModel(BaseModel):
    id: str              # loom2 id, namespaced: "leo/flux-pro-2.0"
    provider: str        # "leonardo"
    model: str           # the v2 discriminator: "flux-pro-2.0"
    kind: Literal["t2i", "instruct_edit", "upscale", "matte", "i2v"]
    label: str
    sizes: list[tuple[int, int]] | None   # enumerated pairs, or None + min/max for free ranges
    size_range: tuple[int, int] | None
    durations: list[int] | None           # seconds (video)
    max_refs: int; flf: bool; audio: bool; seed: bool; negative: bool; max_quantity: int
    defaults: dict       # e.g. {"prompt_enhance": "OFF"}
    typical_s: float     # learned, for the progress bar
    price_hint: dict     # learned from charged costs (2h)
    status: Literal["active", "deprecated", "retired"]
```

- Stored as data (`orchestrator/loom2/engine/leonardo/models.json`), seeded from 02 §2 and checked against the mirrored spec
  in a test; refreshed against `GET /v2/models` at runtime (cached in `<state>/providers/leonardo/models.json`).
- `_validate_models()` (`queue.py:301`) accepts an id that is in `ROSTER_BY_ID` **or** in the enabled cloud registry, and
  validates the recipe against the model's JSON schema (the cloud equivalent of the `/object_info` contract check).
- `recipe_weights()`, `warm_group()`, `estimate_vram_gb()`, `estimate_seconds()` learn to return "no weights / no warm group /
  0 GB / typical_s" for cloud ids.

### 2d. Recipes

Reuse the existing kinds where the verb is the same; add one where it is not.

| loom2 verb | Recipe | Cloud models | Mapping notes |
| --- | --- | --- | --- |
| Generate | `T2I` (`recipes.py:41`) | FLUX.2 Pro, Nano Banana, GPT Image, Seedream, Ideogram, Lucid | `prompt_text` (or the serialized JSON tree where pass-through is confirmed) → `prompt`; `width/height` snapped to the model's allowed sizes; `seeds[]` → one job per seed as today (or `quantity` when the model has no seed); `refs[]` → `guidances.image_reference`; `negative` only where the model has it; local-only fields (`steps`, `cfg`, `sampler`, `te_id`, …) rejected for cloud ids |
| Edit · Instruct edit | **new `InstructEdit`** (06 §3d already lists it) | Kontext Pro / Max, Nano Banana, GPT Image, Seedream, FLUX.2 Pro | `document_id`, `source`, `prompt_text`, `margin_pct`, `feather`, `extra_refs[]`; the region is cropped by `_prepare_document_inputs()`, sent as `image_reference[0]`, and the result is **pasted back through loom2's own feathered selection mask** — that is what makes a mask-less editor usable as an inpainter. Resize back to the crop size is part of paste-back |
| Edit · Upscale | `Upscale` (`recipes.py:116`) | Aurora Precise / Creative | `model_id` = cloud id; `factor` 2–8; `upscale_mode` / `creativity` in `extra`; result as layer or Catalogue asset as today |
| Edit · AI Select · Subject | `Segment` mode `subject` | `remove-bg` (sync endpoint) | the alpha of the returned PNG becomes the selection (D33 path, `op` join unchanged) |
| Animate | `I2V` (`recipes.py:167`) | H3 (`hailuo-03`), Kling 3.0 / O3, Veo 3.1, Seedance 2.x, Wan 2.7 / 3.0, LTX-2.3 Pro | `start_asset` / `end_asset` → `start_frame` / `end_frame`; `frames`+`fps` replaced by `duration` (seconds) for cloud ids; `width/height` from the model's pairs or `0×0` (follow the start frame); `beats` rejected; `audio` flag (default off, see 2f) |

Model-specific parameters that loom2 has no vocabulary for (`quality`, `resolution`, `upscale_mode`, `creativity`,
`transparency`, `style_ids`) travel in one validated `extra: dict` on the recipe, checked against the model's schema. Nothing
else is passed through.

### 2e. Compilation and provenance

`compile_leonardo(recipe, model, inputs, seed)` returns the existing `Compiled` shape:

- `graph` = the exact request body (inline BASE64 data replaced by `sha256:<hash>` placeholders before it is stored);
- `graph_hash` = sha256 of the canonical body — recorded as `compiled_graph_hash` exactly like a ComfyUI graph;
- `summary` = effective parameters for the inspector; `serialized_prompt` = the prompt string sent.

Each asset's manifest (`catalogue.AssetRecord`, `catalogue.py:38`) records, without schema change:
`model_id` = `leo/<model>`, `seed` = the seed Leonardo reports (`generations_by_pk.seed`), `params.provider =
{name: "leonardo", model, generation_id, image_id, cost: {amount, unit}, prompt_enhance, nsfw}`, `params.recipe`,
`timings.wall_s` (+ `remote_s` = Leonardo's `createdAt` → `updatedAt`). That satisfies the provenance measure in
`../proto01/03-vision-scope-and-mvp.md` §6 (model, seed, prompt, parents, suite, timestamp) for cloud assets too.

### 2f. Outputs and finalisation

| Output | Finaliser | Adapter |
| --- | --- | --- |
| Images (T2I) | inline ingest (`queue.py` ≈ 567–592): `catalogue.ingest_file(move=True, suite="generate")` + thumbs | none — the downloaded file is moved in |
| Instruct-edit result | `_finish_document_job()` → `_add_result_layer()` | resize to the crop plan, then the existing paste-back with `alpha_mask` |
| Upscale | `_finish_document_job()` (layer or asset) | none |
| Video | `_finish_i2v_job()` → `ClipStore.create(frames)` → `encode_proxy` (GOP 6) | **decode the MP4 to a PNG sequence first** (PyAV is already used for probing) so the clip keeps D5's master-is-PNG rule; keep the original as `clips/<id>/source.mp4` because it may carry an audio track loom2 has no model for yet |
| Matte (remove-bg) | `_finish_document_job()` segment branch | alpha → grey selection |

Audio tracks in video (Kling, Veo, Seedance, H3 with `motion_has_audio`) have no place in loom2's clip model; the proposal
sends `motion_has_audio: false` until the Story workspace (14) defines one.

### 2g. Configuration and the key

Today there is **no secret storage**: `GET /settings` returns `Settings.model_dump()` in full (`api.py:344–346`), so a key put
in `Settings` would be served to the webview in plain text, and `app.json` is a plain file.

- Key storage: **Windows Credential Manager** through `keyring` (DPAPI-protected, per Windows user), service
  `loom2/leonardo`; fallback: the `LEONARDO_API_KEY` environment variable for CI and headless runs. Never in `app.json`.
- `Settings.leonardo = {enabled: false, max_concurrent: 3, spend_cap_usd: 25.0, confirm_over_usd: 1.0,
  delete_remote_after_download: false, base_url}` (no key). `base_url` exists so tests point at the fake server.
- New routes, all behind the token gate: `PUT /providers/leonardo/key` (write-only), `DELETE /providers/leonardo/key`,
  `POST /providers/leonardo/test` (calls `/v1/me`), `GET /providers` → `{leonardo: {enabled, key_set, key_hint: "…1a2b",
  available, balance?, spent_month_usd, last_error}}`.

### 2h. Spend guard

There is no notion of cost anywhere in loom2 today. Proposed, mirroring the disk guard (`_disk_guard`, `queue.py:327`):

- **Ledger:** `<state>/providers/leonardo/ledger.jsonl` (app-level, append-only, one line per charged job: time, job, project,
  model, cost) + per-project totals derived from asset manifests.
- **Estimate:** `/recipes/preview` returns `cost_usd` for cloud recipes from the learned `price_hint` (median of the last
  charges for that model and size / duration), `"unknown"` before the first charge; the pricing calculator is used where it
  supports the model (unverified, L0).
- **Guard at submit:** refuse (HTTP 422, like the disk guard) when the month's spend plus the estimate exceeds
  `spend_cap_usd`; ask for confirmation in the UI when one submission is estimated over `confirm_over_usd` or unknown.

### 2i. Events

- `job.progress` `{id, progress, text}` with `progress` from elapsed / `typical_s` (capped at 0.95) and `text` =
  "Leonardo · queued 12 s" / "rendering 1 m 40 s"; no previews.
- `job.updated` unchanged (now carrying `engine`, `remote_id`, `cost`).
- New `provider.state` `{name, available, reason, balance, spent_month_usd}` for the Settings banner and the job dock.

## 3. Frontend

| Place | File | Today | Change |
| --- | --- | --- | --- |
| Settings | `frontend/src/frame/SettingsModal.tsx` | sections Weights / Engine / App / Catalogue / Engine output / Licences; `save()` sends a field whitelist | new **Cloud providers** section: enable, key (set / replace / clear, shows `…1a2b` only), Test, balance, month spend vs cap, confirm threshold, delete-after-download; whitelist extended |
| Generate · model picker | `frontend/src/suites/generate/GenerateSuite.tsx` (≈ 205–240) | **hard-coded order list** of six local ids filtered by `caps.models` | picker driven by `/capabilities`: local group, then "Cloud · Leonardo" group (cloud badge, cost hint) shown only when the provider is enabled; parameters panel switches to the model's own sizes / quantity / extras; local-only Advanced fields hidden for cloud ids |
| Generate · prompt | same | tree / JSON / text | JSON tree offered only for models where pass-through is confirmed (FLUX.2 Pro, L0); others get text |
| Edit · AI panel | `frontend/src/suites/edit/EditSuite.tsx` (≈ 259–332) | model ids and `<select>` options hard-coded per op | new op **Instruct edit** (cloud models listed from capabilities), cloud upscalers in the Upscale op, `remove-bg` as an AI Select · Subject engine choice |
| Animate · model cards | `frontend/src/suites/animate/AnimateSuite.tsx` (≈ 81–103), `animateStore.ts` `MODEL_RULES` (27–48) | Wan / LTX rules hard-coded, plus a locked "H3 (hero)" card | cloud cards from capabilities; **H3 card unlocks through `hailuo-03`** when the provider is enabled (the local H3 graph stays post-MVP); duration in seconds and resolution presets for cloud models; no beats |
| Job dock | `frontend/src/frame/` dock | progress from WS | cloud jobs show the provider, elapsed vs typical, estimated → charged cost, "may still be charged" on cancel |
| Catalogue | `frontend/src/suites/catalogue/filters.ts`, `Inspector.tsx` | chips State, Type, Source, Model, Rating, Date, Tags, Batch (D34) | **Source** chip gains "Leonardo"; Inspector shows the provider block (model, generation id, cost); "Copy generation id" in the tile menu |
| Cost confirmation | new modal | — | shown for unknown or over-threshold estimates; lists what leaves the machine (prompt, N images) |

Every new action is a registry command with a mouse placement and a right-click entry where it acts on an object (D32,
`../proto01/07-ui-frame.md`). Presets stay behind one icon per field; nothing new becomes mandatory.

## 4. Build variants (D26)

The variant is a **licence filter on weights** that loom2 ships or fetches. Cloud models ship no weights, so they do not
change what either installer distributes; their terms are Leonardo's. Proposal (LD4 in 05): the cloud provider is available in
**both** variants, off by default, and every job manifest already records `variant` next to the new `provider` block. The
`open` build's promise ("Apache/MIT weights only") stays true because no weights are involved.

## 5. Tests

Following the fake-ComfyUI pattern (`orchestrator/tests/fake_comfy.py`: a FastAPI app on an ephemeral loopback port in a
daemon thread, adopted by the real supervisor):

- `tests/fake_leonardo.py`: `POST /v2/generations`, `POST /v2/generationssync`, `GET /v1/generations/{id}`,
  `DELETE /v1/generations/{id}`, `POST /v1/init-image` + a fake S3 form endpoint, `GET /v1/me`, `GET /v2/models`, and a CDN
  route serving PNG / MP4 bytes. Behaviours: `success`, `slow`, `failed`, `nsfw_prompt` (400), `nsfw_output` (flag),
  `rate_limited` (429 then success), `server_error`, `bad_key`, `balance_empty`, `create_timeout` (create succeeds, response
  lost).
- Test files per slice (04): client and compile units; queue lane, durability (resume polling after a kill — **no second
  create**), cancel, spend guard, key never in `/settings`, variant `open` + cloud; finaliser round trips (image → asset,
  instruct edit → layer, MP4 → PNG master + proxy).
- Contract: the cloud registry vs `source/openapi-v2-creategeneration.json` (every registry entry exists, sizes / durations /
  max refs agree), run offline in CI like `test_roster_contract.py`.
- Rig / live: `scripts/leonardo_acceptance.py`, marked like the `rig` tests, needs a key and spends real money with a printed
  budget (≈ USD 2–5 per full run, to be confirmed in L0).

## 6. Invariants this integration must not break

| Invariant | Where it is guarded |
| --- | --- |
| Pixels and keys never cross into the webview from outside; CSP loopback-only | `scripts/csp_check.py`; test that `/settings` and `/providers` never contain the key |
| Kill anywhere → relaunch paused, nothing billed twice, nothing corrupt | durability tests with the fake server |
| Every asset answers model, seed, prompt, parents, suite, timestamp | manifest test for cloud assets |
| Local is the default; cloud only when chosen | capabilities test: no cloud models when disabled; no automatic fallback anywhere |
| The GPU queue's behaviour is unchanged | the existing offline suite (115 tests collected on 2026-10-08) passes untouched after the seam extraction (L1 gate) |
| A retired cloud model fails readably and old assets still open | registry `status`, test with a retired id |
