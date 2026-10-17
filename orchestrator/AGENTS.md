# orchestrator — notes for coding agents

Verified at 07cb440 on 2026-10-10. Specs: `.docs/proto01/06-architecture.md` (processes, storage, data model, API, flows).

Python 3.13 package `loom2`, managed by uv (`orchestrator/pyproject.toml`, `orchestrator/uv.lock`). Torch-free: the GPU lives in the
engine process (`engine/`). Run as `python -m loom2.main --port N [--state DIR] [--project DIR]`; it prints a `LOOM2_READY {json}`
line that the Tauri shell (`frontend/src-tauri/src/lib.rs`) parses for the port and the per-launch token.

## Module map (`orchestrator/loom2/`)

| Module | Owns |
| --- | --- |
| `api.py` | `create_app()`: lifespan, CORS, the token gate, error → status mapping, includes `routes.ROUTERS` (D37) |
| `services.py` | `Services`: app state, event hub, roster, engine supervisor and the open project's stores; `require_project/groups/documents` |
| `routes/` | one `APIRouter` per domain (`meta`, `settings`, `projects`, `assets`, `groups`, `documents`, `clips`, `jobs`, `models`, `engine`, `blobs`, `events_ws`); request models live with their routes; `deps.py` gives handlers `svc: Svc` |
| `capabilities.py` / `build_info.py` | the `/capabilities` document (07 §3d) and the `/version` facts (D36) |
| `schemas.py` | response models (D38): `Out` (strict, every field present) and `Open` (composite dicts: extra fields pass, defaulted fields optional); the WebSocket event frames (`EVENT_FRAMES`) |
| `queue.py` | `JobQueue` / `JobRecord`: durable queue (written off the loop: `persist()` → one writer, `await flush()`), admission (models, disk guard, VRAM), warm-group scheduling, the run loop `_run_one` (plan → finalize → submit → follow → finish → `_complete`, D64) |
| `engine/` | ComfyUI client, supervisor, recipe → graph builders, contract checks; the job pipeline (`pipeline.py`, `follow.py`, `finishers.py`, D64) — see `orchestrator/loom2/engine/AGENTS.md` |
| `recipes.py` | pydantic recipes `T2I`, `I2I`, `Inpaint`, `Upscale`, `Segment`, `I2V` (discriminated on `kind`), sampler enums, `warm_group` |
| `roster.py` | `ROSTER` (every weight file: repo, folder, licence, variants, retired), scan / resolve / sha256 ledger |
| `catalogue.py` | `AssetRecord` sidecar manifests + the SQLite index (`catalogue.sqlite`, FTS5), ingest, thumbnails, lineage, trash, rebuild |
| `groups.py` | D34 album: one JSON per group under `groups/`, one placement per item, revision → 409 |
| `mentions.py` | D73: `@`mentions → references (cover first, then page order by position; mentions take turns within the model's remaining `refs_max`), stamped `{group_id, name, revision, asset_ids}`; run by `JobQueue.resolve_mentions` before `plan()` in submit and preview; D93: then each mention's images sit together (subject order) and the set's images left out are stamped as `skipped` — `graphs.subject_bindings` / `serialize_prompt` bind a linked subject to its range per family (`inputs.bind_refs`); D93 (B4): a linked subject's description is composed here from the mention's version's sheet (`story.compose_sheet` — appearance, outfit, bound colours, marks) and the card's `Mention.shot`, stamped as `composed` (a stamped recipe is never composed again); D93 (C6): a place linked to the scene (`Mention.scene`) composes `prompt_json.scene`, a prop held by a card (`Mention.held_by`) its `holding` (a place or a prop wears no outfit); (C8) `resolve_figures` gives a StageShot's bound figures (`Mention.figure`, left to right) their references within the method's room — the queue runs it for preview and submit |
| `documents.py` / `compose.py` / `edit_ai.py` | layered documents (ORA), the exact numpy compositor, AI region maths |
| `maskops.py` / `matting.py` | bounded exact EDT, round expand / contract (D44); Refine Edge — guided filter, smart radius, post steps (D45) |
| `clips.py` | clip masters (PNG sequence) + GOP-6 proxies |
| `workspace.py` / `config.py` | project tree, `ProjectFormat`; app state `app.json`, `Settings`, the token |
| `preset_icons.py` | D90 (02 §6.3): the preset swatch pack in app state (`<state>/preset_icons/`, index + `<key>.webp`, key = sha1(field + "
" + value)[:16]); `routes/preset_icons.py` makes one staged t2i per item on the sample model — D91: `Settings.samples.model_id` when it names a spec with `recipes.sample` this variant offers (`registry.sample_model`), else the spec with `default_for = ["swatch"]` — at its `geometry.sample_px.swatch`; `/capabilities.sample_models` lists the choices (the default first); `AssetFinisher` stores the result on `origin.surface == "swatch"` |
| `library.py` | D92: the project's World library (`story/library.json`: entries `{id, field, name, text}`, revision → 409; seeded on the first read from `library_seed.json` — the one built-in vocabulary, the frontend's glyph test reads it — and the app-wide `snippets.json`, once) and Generate's saved panels (`generate/presets.json` as a record with `thumb_asset_id`, set by the finisher for a job whose origin payload names `saved_panel`) |
| `events.py` | `EventHub`: WebSocket fan-out with seq numbers, 200-frame replay, binary previews |
| `fsio.py` | `atomic_write_json/bytes/text`, `atomic_copy/move`, `read_json`, `new_id` |
| `tools/` | `facesim.py` (advisory identity), `fetch.py` (weights), `pngmeta.py` (import metadata) |
| `native.py`, `heal.py` | D62: the optional PhotoCraft extension (content-aware fill, PatchMatch) and Spot Healing on top of it |

## Native extension (D62)

`loom2/native.py` wraps the optional `loom2_pcalgo` wheel (PhotoCraft's content-aware fill and PatchMatch, committed in `vendor/`, pinned and
checksummed; `uv sync --extra native`). Everything that uses it — Quick Remove (`Inpaint.mode == "quick_remove"`, run on the CPU in
`queue._run_quick_remove` without starting the engine), the Remove pre-fill (`Inpaint.prefill`), Spot Healing (`heal.py`, `POST /heal`) —
must answer cleanly when it is absent; `/capabilities.content_aware.available` tells the UI.

## Rules

1. **Files are truth.** Asset sidecars, `groups/*.json`, documents, `jobs/queue.json` and `project.json` are authoritative; `catalogue.sqlite`
   is an index that `Catalogue.rebuild()` regenerates. Every write goes through `fsio` (temp → fsync → replace); every record has a
   `schema_version`; a corrupt state file is quarantined, not trusted.
2. **Durability.** After an unclean shutdown the queue loads paused with running jobs re-queued (`retry_count += 1`); non-resumable jobs
   fail. Never mark a job done before its outputs are moved into the project and the manifest is written.
3. **Async discipline (D37).** FastAPI handlers run on the event loop; SQLite and file work belongs in `await asyncio.to_thread(...)`.
   The catalogue (one connection behind an `RLock`, `check_same_thread=False`) and the group store lock themselves; **`JobQueue` is not
   thread-safe** — call it on the loop; `DocumentStore` has no lock — only its `get` / `save` / `flatten` and pure encodes go to threads.
4. **Routes:** a new endpoint goes into the domain module under `routes/` (or a new module added to `routes.ROUTERS`). Register literal
   paths before parameterised ones (`/assets/counts` before `/assets/{asset_id}`); `tests/test_routes_d37.py` checks the order and the
   route table against `tests/fixtures/routes_d37.json` — update the snapshot in the same commit when you add or remove a route.
   **Every JSON route declares `response_model=`** (D38; `tests/test_contract_d38.py` enforces it) — a record model, or a model in
   `schemas.py`. A record returned in replies sets `json_schema_serialization_defaults_required=True`. After any API change run
   `scripts/export_openapi.py` and `npm run api:types` (in `frontend/`) and commit `openapi.json` + `schema.d.ts`; CI fails otherwise.
5. **Token (D67).** Every route but `/health` requires `X-Loom-Token` (`token_gate` in `api.py`); the token is per launch and never
   persisted. Media GETs (`MEDIA_PATH`) also accept the read-only `?k=` media key (`AppState.media_key`, `GET /session`); a new media
   route goes into `MEDIA_PATH` and the matrix in `tests/test_auth_d67.py`. The WebSocket authenticates with its first message. Tests get
   an authenticated `TestClient` by default (`conftest.py`); pass `headers={}` to test the gate.
6. **Lineage at write time.** Parents, `lineage_kind`, model, seed, prompt, `compiled_graph_hash` and the variant are stamped when an asset
   is ingested; nothing reconstructs them later.
7. **IDs** are prefixed (`ast_`, `job_`, `doc_`, `clp_`, `grp_`, `bat_`) via `fsio.new_id`.
8. **Pixels** never travel as base64 or through Tauri IPC: files over loopback HTTP with `Range` / `ETag`
   (`FileResponse.chunk_size` is set to 4 MiB in `api.py`; 64 KiB caps loopback at ~400 MiB/s — E2), raw RGBA for layers.

## Tests (`orchestrator/tests/`)

- Run: `orchestrator/.venv/Scripts/python.exe -m pytest orchestrator -q`. `pyproject.toml` sets `asyncio_mode=auto`, `timeout=120` and
  `-m 'not rig'`, so GPU tests (`@pytest.mark.rig`) never run by default.
- Fixtures: `conftest.py` (`object_info` from `tests/fixtures/object_info.json`, a fake `models_tree`); `test_lifecycle.Rig` builds a
  real supervisor + queue against `tests/fake_comfy.py` (`FakeComfy` modes `success`, `silent` for the stall watchdog, `error`).
- Test files are named by milestone (`test_*_m2` … `test_durability_m7`), review register (`test_review_c.py`) or decision
  (`test_groups_d34.py`, `test_te_gguf.py`). A bug fix adds a regression test named after its register id.
- Rig scripts in `scripts/` (`m1_acceptance.py` …) drive a live orchestrator and engine; their results go to the journal.

## Footguns

- Starlette's `FileResponse.chunk_size` is a class attribute, not a constructor argument.
- `roster.scan()` walks two model roots; keep it off the event loop.
- A job's engine outputs land in `<state>/engine_out/loom2/<job_id>`; they are moved into the project or deleted when the job ends, and
  leftovers are reconciled when a project opens.
- The engine keeps answering HTTP with a dead GPU after a driver TDR; the stall watchdog (`engine.stall_timeout_s`) is what notices.
- `fsio.replace` retries with `time.sleep` (up to ~0.63 s) while antivirus or the indexer holds the target. `JobQueue.persist()` calls it
  on the event loop (the queue is loop-only), so a held `queue.json` stalls the loop that long; anything new that writes from an async
  handler goes through `asyncio.to_thread` (as `blob_put` does since review R8).
