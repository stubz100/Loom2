# orchestrator/loom2/engine — notes for coding agents

Verified at 07cb440 on 2026-10-10. Specs: `.docs/proto01/06-architecture.md` §3 (ComfyUI as the engine), `.docs/proto01/04-model-strategy.md`
(model choices, measured timings), decisions D1, D2, D15, D16, D30, D31, D33 in `.docs/proto01/13-decision-log-and-open-questions.md`.

## Files

| File | Owns |
| --- | --- |
| `supervisor.py` | `EngineSupervisor`: starts `engine/comfyui/main.py` from `engine/.venv` (lazily on the first job), health via `/system_stats`, Job Object + `taskkill` backstop, adopts an engine already on the port, restart policy, logs under `<state>/logs/engine-*.log` |
| `client.py` | `ComfyClient`: REST (`/prompt`, `/history`, `/interrupt`, `/free`, `/upload/image`, `/view`, `/object_info`) and the `/ws` event stream (binary preview frames) |
| `graphs.py` | model knowledge today (`ModelPreset` / `PRESETS`, `TE_ALTERNATES`, `VRAM_ESTIMATE_GB`, `BASE_SECONDS`, `I2V_RULES`, `WAN_PRESETS`) and the builders `build_t2i`, `build_i2i`, `build_inpaint`, `build_upscale`, `build_segment`, `build_i2v`; `compile_recipe` dispatches and runs the contract check |
| `contract.py` | `resolve_names` (basename → engine enum value) and `check_graph` (unknown class, missing input, enum value, link type) against `/object_info` |

Recipes are pydantic models in `orchestrator/loom2/recipes.py`; weights in `orchestrator/loom2/roster.py`.

## Rules

1. **Recipes carry roster ids, never paths.** The builder resolves ids through `Roster.require` / `Roster.resolve` to the
   `folder/filename` pair loader nodes take.
2. **Every graph is contract-checked** against the pinned engine's `/object_info` before submission; `compile_recipe` returns
   `Compiled.problems`, and the queue fails the job on any problem. Offline tests use `orchestrator/tests/fixtures/object_info.json`.
3. **Core nodes first.** The engine carries two custom nodes (`engine/nodes.lock`: ComfyUI-GGUF, LanPaint) and one patch
   (`engine/patches/`). Adding a custom node needs a decision in 13 (D33 kept segmentation core-only on purpose).
4. **Output naming:** `SaveImage` / video savers use `filename_prefix = loom2/<job_id>` so the queue finds and moves the outputs.
5. **Provenance:** `Compiled.graph_hash` (sha256 of the graph) goes into every manifest; `serialized_prompt` is the exact string the model saw.
6. **Display == reality:** whatever `/capabilities` and `/recipes/preview` show must come from the same presets the builders use.

## Add a model (today)

1. Fetch the weights into the models root (`scripts/fetch_weights.py`, ComfyUI layout, sha256 into `roster.index.json`).
2. Add a `RosterEntry` to `ROSTER` in `orchestrator/loom2/roster.py`: id, file name, ComfyUI folder, family, role, HF repo/file, **licence
   read against EU terms (D17)**, `variants` (`open` only for Apache/MIT, D26), `approx_gb`.
3. Add its behaviour in `graphs.py`: a `ModelPreset` in `PRESETS` (image models) or an `I2V_WEIGHTS` / `I2V_RULES` entry (video), plus
   `VRAM_ESTIMATE_GB` and `BASE_SECONDS`. A new family needs a builder.
4. If the graph uses node classes the fixture lacks: capture `/object_info` from the running engine and rerun
   `scripts/make_object_info_fixture.py`.
5. Tests: compile every recipe kind the model supports against the fixture with zero `problems` (see `test_generate_m3.py`,
   `test_edit_ai_m5.py`, `test_animate_m6.py`); add the variant to `scripts/pin_review.py` `recipes()`.
6. Frontend: Generate / Edit / Animate still hard-code some model ids (D38/P1 removes this) — grep for an existing id of the same family.
7. Rig: run the model through the app, record time and VRAM in the journal. Delete weights that lose (D30).

## Bump the ComfyUI pin

1. `git -C engine/comfyui worktree add .loom2_state/comfy-<tag> <tag>` and start it on the CPU on port 8189 (see the docstring of
   `scripts/pin_review.py`).
2. `scripts/pin_review.py --url http://127.0.0.1:8189 --tag <tag>`: diffs node signatures for the classes loom2 uses and compiles every
   recipe variant; any new problem blocks the bump.
3. Move the submodule, recapture the fixture, re-check the custom nodes and patches in `engine/nodes.lock`, run a rig smoke, journal it,
   amend D15.

## Footguns

- ComfyUI-GGUF rebuilds the tekken tokenizer for the Mistral encoder; core 0.38+ needed the special-token patch in
  `engine/patches/comfyui-gguf-pr479-tekken-special-tokens.patch`.
- DynamicVRAM streams a model's first job when the transformer and text encoder together exceed 16 GB (Klein 9B with the fp8 encoder:
  1157 s cold vs 279 s with the Q4_K_M GGUF encoder, D31). Measure cold and warm.
- The engine runs with `--reserve-vram` (`Settings.engine.reserve_vram_gb`, 1.5) so the editor's WebGPU canvas keeps headroom.
- SAM 3 box prompts read output 1 and need `editor_state {}` (review C32).
- Distilled presets reject I2I and tiled refine; the dev Turbo rule lives in three places in `graphs.py` (`build_t2i`, `effective_params`,
  `recipe_weights`) — change them together.
