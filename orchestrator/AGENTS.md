# orchestrator — notes for coding agents

Verified at 07cb440 on 2026-10-10. Specs: `.docs/proto01/06-architecture.md` (processes, storage, data model, API, flows).

Python 3.13 package `loom2`, managed by uv (`orchestrator/pyproject.toml`, `orchestrator/uv.lock`). Torch-free: the GPU lives in the
engine process (`engine/`). Run as `python -m loom2.main --port N [--state DIR] [--project DIR]`; it prints a `LOOM2_READY {json}`
line that the Tauri shell (`frontend/src-tauri/src/lib.rs`) parses for the port and the per-launch token.

## Module map (`orchestrator/loom2/`)

| Module | Owns |
| --- | --- |
| `api.py` | `Services` (the open project's stores), request models, `create_app()` with every route and the `/events` WebSocket (split per domain under D37) |
| `queue.py` | `JobQueue` / `JobRecord`: durable queue, admission (models, disk guard, VRAM), warm-group scheduling, the run loop, engine event following, stall watchdog, document / i2v pre- and post-processing |
| `engine/` | ComfyUI client, supervisor, recipe → graph builders, contract checks (see `orchestrator/loom2/engine/AGENTS.md`) |
| `recipes.py` | pydantic recipes `T2I`, `I2I`, `Inpaint`, `Upscale`, `Segment`, `I2V` (discriminated on `kind`), sampler enums, `warm_group` |
| `roster.py` | `ROSTER` (every weight file: repo, folder, licence, variants, retired), scan / resolve / sha256 ledger |
| `catalogue.py` | `AssetRecord` sidecar manifests + the SQLite index (`catalogue.sqlite`, FTS5), ingest, thumbnails, lineage, trash, rebuild |
| `groups.py` | D34 album: one JSON per group under `groups/`, one placement per item, revision → 409 |
| `documents.py` / `compose.py` / `edit_ai.py` | layered documents (ORA), the exact numpy compositor, AI region maths |
| `clips.py` | clip masters (PNG sequence) + GOP-6 proxies |
| `workspace.py` / `config.py` | project tree, `ProjectFormat`; app state `app.json`, `Settings`, the token |
| `events.py` | `EventHub`: WebSocket fan-out with seq numbers, 200-frame replay, binary previews |
| `fsio.py` | `atomic_write_json/bytes/text`, `atomic_copy/move`, `read_json`, `new_id` |
| `tools/` | `facesim.py` (advisory identity), `fetch.py` (weights), `pngmeta.py` (import metadata) |

## Rules

1. **Files are truth.** Asset sidecars, `groups/*.json`, documents, `jobs/queue.json` and `project.json` are authoritative; `catalogue.sqlite`
   is an index that `Catalogue.rebuild()` regenerates. Every write goes through `fsio` (temp → fsync → replace); every record has a
   `schema_version`; a corrupt state file is quarantined, not trusted.
2. **Durability.** After an unclean shutdown the queue loads paused with running jobs re-queued (`retry_count += 1`); non-resumable jobs
   fail. Never mark a job done before its outputs are moved into the project and the manifest is written.
3. **Async discipline.** FastAPI handlers run on the event loop; SQLite and file work belongs in `await asyncio.to_thread(...)`. The
   catalogue's single connection is shared behind an `RLock` (`check_same_thread=False`).
4. **Token.** Mutating routes require `X-Loom-Token` (`token_gate` in `api.py`); the token is per launch and never persisted.
5. **Lineage at write time.** Parents, `lineage_kind`, model, seed, prompt, `compiled_graph_hash` and the variant are stamped when an asset
   is ingested; nothing reconstructs them later.
6. **IDs** are prefixed (`ast_`, `job_`, `doc_`, `clp_`, `grp_`, `bat_`) via `fsio.new_id`.
7. **Pixels** never travel as base64 or through Tauri IPC: files over loopback HTTP with `Range` / `ETag`
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
