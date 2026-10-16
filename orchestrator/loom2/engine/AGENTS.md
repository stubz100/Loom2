# orchestrator/loom2/engine — notes for coding agents

Verified at 07cb440 on 2026-10-10. Specs: `.docs/proto01/06-architecture.md` §3 (ComfyUI as the engine), `.docs/proto01/04-model-strategy.md`
(model choices, measured timings), decisions D1, D2, D15, D16, D30, D31, D33 in `.docs/proto01/13-decision-log-and-open-questions.md`.

## Files

| File | Owns |
| --- | --- |
| `supervisor.py` | `EngineSupervisor`: starts `engine/comfyui/main.py` from `engine/.venv` (lazily on the first job), health via `/system_stats`, Job Object + `taskkill` backstop, adopts an engine already on the port, restart policy, logs under `<state>/logs/engine-*.log` |
| `client.py` | `ComfyClient`: REST (`/prompt`, `/history`, `/interrupt`, `/free`, `/upload/image`, `/view`, `/object_info`) and the `/ws` event stream (binary preview frames) |
| `graphs.py` | the builders (they read `models/registry.py` specs — D65: no model constants or id comparisons here) `build_t2i`, `build_i2i`, `build_inpaint`, `build_upscale`, `build_segment`, `build_i2v`; `compile_recipe` dispatches and runs the contract check |
| `image_families.py` | D89: the per-`graph` node shapes of T2I / I2I (CLIPLoader type, empty latent, FluxGuidance or not, shift node, T5 options, checkpoint loader) for the FLUX.2 family and the creative families (krea2, zimage, chroma, sd3; D91: lumina2 — a checkpoint with ModelSamplingAuraFlow, its system prompt the spec's `sampling.prompt_prefix` on the positive only) |
| `contract.py` | `resolve_names` (basename → engine enum value) and `check_graph` (unknown class, missing input, enum value, link type) against `/object_info` |
| `pipeline.py` | D64: `plan()` (pure: effective params, needs, weights, warm group, VRAM, ETA — `/recipes/preview` for every kind), `preview_problems()` (compile on placeholder inputs), `finalize()` (references, document region, i2v frames uploaded; compile + contract), `prepare_document` / `prepare_i2v` / `fit_reference`, `JobCancelled` |
| `finishers.py` | D64: `finisher_for(recipe)` → `AssetFinisher` · `DocumentFinisher` (paste-back, upscale; `add_result_layer`) · `SelectionFinisher` · `ClipFinisher` (+ the identity side task); `run_quick_remove` (no engine) |
| `follow.py` | D64: `EngineFollower` — the `/ws` event pump, `follow()` (progress, node times, history fallback, stall watchdog → engine restart + queue pause), `outputs()`, `free_cache()` |

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
6. **Display == reality:** whatever `/capabilities` and `/recipes/preview` show comes from the same specs the builders read (D65).

## Add a model (D65: specs are data)

1. **Roster entry** — the weight file, its ComfyUI folder, family, role, HF repo/file, **licence read against EU terms (D17)**, `variants`
   (`open` only for Apache/MIT, D26), `approx_gb`: in `orchestrator/loom2/roster.py`, or as a `weight = { … }` table inside the spec (the
   registry adds it to the roster at load). Fetch it into the models root (`scripts/fetch_weights.py`, sha256 into `roster.index.json`).
2. **Spec** — a `[[model]]` in `orchestrator/loom2/models/specs/<family>.toml` (or a file in a folder named by `LOOM2_MODEL_SPECS`):
   `graph` (the builder), roles (encoder + alternates, VAE, extras), sampling, recipes it runs (`t2i`, `i2i`, inpaint modes, `inpaint_hero`,
   `icm_default`, upscale factor, segment modes, i2v / flf / beats, `default_for`, D91 `sample` — a style-sample / swatch model, sized by `geometry.sample_px`), inputs, geometry (size multiple, tiers, video rules),
   estimates (VRAM, seconds), video presets. `registry.load()` validates it against the roster at import. Nothing else names the id:
   `scripts/model_literals_check.py` (CI) fails on a quoted roster id in the orchestrator's or the frontend's code.
3. **Builder** — only for a new `graph` (a new family's node layout). Builders read the spec; they never compare model ids. A new *image*
   family that only needs T2I / I2I is a row in `image_families.py` plus the `Graph` literal and `registry.IMAGE_GRAPHS` (D89); inpaint, tiled
   refine, Angle, Stage and references stay on `registry.FLUX_GRAPHS` (`_flux2_loaders` refuses anything else).
4. **Fixture** — if the graph uses node classes the fixture lacks, capture `/object_info` from the running engine and rerun
   `scripts/make_object_info_fixture.py`.
5. **Tests** — `test_registry_d65.py::test_sweep_every_spec_compiles` compiles every spec × tier / mode / preset against the fixture with
   zero problems and checks the estimates grow with pixels and frames; add the variant to `scripts/pin_review.py` `recipes()` and rerun
   `test_graph_parity_d64.py --parity-update` only for an intended graph change.
6. **Frontend** — nothing: the panels list `caps.models` / `caps.i2v.models` / `caps.tools` by `order`, gate controls on `recipes` / `inputs`,
   and start from `caps.defaults` (variant-aware).
7. **Rig** — run the model through the app, record time and VRAM in the journal (then put the measured numbers into the spec's
   `estimates`). Delete weights that lose (D30).

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
- Models without `recipes.i2i` (the distilled ones) reject I2I and tiled refine. A spec's Turbo LoRA (`sampling.turbo`) is optional in
  t2i (the recipe's `turbo`) but always chained in the Edit graphs (`_flux2_loaders`), and `recipe_weights` lists it accordingly.
- D89: `IMAGE_GRAPHS` (Generate and Refine) is wider than `FLUX_GRAPHS` (every Edit graph). The FLUX.2 graphs keep their node ids (`"1"`–`"11"`);
  the creative families add `"21"` (T5 options) and `"22"` (the shift node), and SD 3.5's one checkpoint is `"1"` with outputs 0 / 1 / 2.
  A real-CFG family encodes its negative even when it is empty (the Comfy templates'); guidance is `None` where there is no FluxGuidance.
- A size or frame count off the grid is snapped **down** by default (D65 `size_policy`, D18): 950 × 540 runs at 944 × 528; `snap_up` or
  `error` (a 422 naming the field and the two values allowed) on request.
