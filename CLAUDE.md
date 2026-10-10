# loom2 — notes for coding agents

Verified at a4b4cfb on 2026-10-10.

loom2 is a local AI image and video studio for storyboard pre-production, running on one Windows machine with an AMD RX 9070 XT
(16 GB, ROCm). It has a Tauri 2 shell, a React/TS frontend, a Python orchestrator (FastAPI) and a pinned ComfyUI used headless as
the engine. The author works mouse-first and is EU-based.

## Where the truth lives

- **Specs:** `.docs/proto01/00-README.md` (read 01 → 15 in order). The decision log is `.docs/proto01/13-decision-log-and-open-questions.md`;
  a change in direction is a new D-number there, recorded *before* the work.
- **Journal:** `.docs/proto01/90-journal.md`, append-only, real timestamps (`date '+%Y-%m-%d %H:%M'`). Measurements and rig runs go
  there; never rewrite old entries.
- **Proposals in flight:** `.docs/artcraft/08-delivery-plans.md` (waves H1–H4, X1, spikes E10–E14). The Catalogue redesign is in
  `.docs/proto01_design/01-catalogue-inventory.md`.
- **Subsystem notes:** `orchestrator/AGENTS.md`, `orchestrator/loom2/engine/AGENTS.md`, `frontend/src/frame/AGENTS.md`,
  `frontend/src/suites/edit/AGENTS.md`.

## Commands

| What | Command |
| --- | --- |
| Offline tests (145+, ~40 s) | `orchestrator/.venv/Scripts/python.exe -m pytest orchestrator -q` |
| Photoshop oracle (D40) | `python scripts/fetch_corpus.py` once, then `… -m pytest orchestrator -m corpus -s` (needs `--extra oracle`); floor in `bench/corpus/psd-tools.floor.json` |
| Frontend typecheck + build | `cd frontend; npm run build` (`tsc -b` + `vite build`) |
| Lint (frontend) | `cd frontend; npm run lint` (oxlint) |
| Agent-doc path check | `orchestrator/.venv/Scripts/python.exe scripts/agents_check.py` |
| Settings audit (D60) | `orchestrator/.venv/Scripts/python.exe scripts/settings_audit.py` — every Settings field, recipe field and `/capabilities` parameter must reach the code that runs (allow-list with reasons) |
| API contract (D38) | `orchestrator/.venv/Scripts/python.exe scripts/export_openapi.py` then `cd frontend; npm run api:types` after any API change |
| Versions (D36) | `python scripts/bump_version.py --check` · `… patch\|minor\|major\|X.Y.Z` (rewrites every location from `VERSION`) |
| Whole app | `scripts/dev.ps1` (Vite + shell + orchestrator; the engine starts on the first job) |
| Browser dev | `scripts/dev.ps1 -Browser` → `http://127.0.0.1:1420/?token=devtoken&port=8766` |
| Rig acceptance (GPU) | `scripts/m1_acceptance.py`, `m3_`, `m4_`, `m5_`, `m6_acceptance.py`, `m7_durability.py` |
| Headed editor / player checks | `scripts/edit_headed_check.py render\|paint\|kit\|layers\|props\|transform\|smartsel\|heal\|masks\|tour\|cmpdiag\|grid\|brush\|selection\|psd\|animate\|perf` (visible Edge, needs Vite on 1420; `psd` needs `uv sync --project orchestrator --extra dev --extra oracle`) |
| CSP check of the production build | `scripts/csp_check.py` (headless Edge; incl. the smart-select Worker's WebAssembly) |
| Content-aware wheel (D62) | `python scripts/build_pcalgo.py --check` (CI); installed by `uv sync --project orchestrator --extra native`; rebuild only when the PhotoCraft pin moves: `python scripts/build_pcalgo.py` then `uv lock --project orchestrator`. Rig: `scripts/d62_remove_rig.py` |
| Smart-select WebAssembly (D59) | `python scripts/build_pcwasm.py --check` (CI); rebuild only when the PhotoCraft pin moves: `python scripts/build_pcwasm.py` (needs the PhotoCraft checkout beside this repository at the pin and `rustup target add wasm32-unknown-unknown`) |

CI (`.github/workflows/ci.yml`) runs the offline suite and the frontend build for both variants (`full`, `open`) on every push and
pull request, and builds both installers on pushes to `main` and on tags.

## House rules

1. **16 GB first.** Every model path is measured on the rig before it is called done ("no milestone closes with rig owed"). fp8 streamed
   from RAM beats GGUF for large transformers on this card (D30); unneeded weights are deleted, not kept.
2. **ComfyUI is for inference only** (D2, D15): loom2 never uses ComfyUI's UI or queue. The engine is the pinned submodule `engine/comfyui`
   plus the custom nodes in `engine/nodes.lock`. Adding a custom node is a decision, not a convenience.
3. **Mouse-first (D32).** Every action is a command in `frontend/src/frame/commands.ts` with at least one mouse placement (button, toolbar or
   right-click menu). Keys are accelerators shown in tooltips. No key-only or gesture-only features.
4. **Files are truth, indexes are rebuildable.** Write through `orchestrator/loom2/fsio.py` (temp → fsync → replace), with a `schema_version` on
   every record and lineage stamped at write time.
5. **Display == reality (T8).** Defaults the UI shows must be exactly what the worker runs; parameters come from `/capabilities`.
6. **No native dialogs.** `window.confirm` / `window.prompt` crash in WebView2; use `askConfirm` / `askText` from `frontend/src/store/session.ts`.
7. **Licences are read against EU terms (D17).** Variants (D26): `open` = Apache/MIT weights only. Hunyuan3D is excluded (its licence
   excludes the EU).
8. **Small drafts by default (D18):** 16:9 project format, Draft tier first, FHD optional.
9. **Commits** follow the existing style: one long summary line naming the journal entry, what changed, test counts and rig results; then
   the attribution trailer. Commit only what belongs to the change.

## Layout

```
.docs/proto01/      specs 00–15, decision log 13, journal 90
bench/              frozen benchmark prompts and tasks (t2i / inpaint / i2v)
engine/             comfyui (submodule, v0.39.0), nodes.lock, patches/, extra_model_paths.yaml, constraints.txt, spikes/
orchestrator/       Python package loom2 (uv, Python 3.13) + tests/
frontend/           Vite 8 + React 19 + TS 6 app; src-tauri/ is the Tauri 2 shell
scripts/            setup, engine control, weights, acceptance runs, browser checks, pin review
```
