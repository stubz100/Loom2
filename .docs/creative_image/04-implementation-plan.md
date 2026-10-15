# 04 — Implementation plan: wave CR (creative image models)

Status: **accepted 2026-10-15 as D89** (the author: no filter, the Stability licence accepted, the downloads with the Krea LoRAs, SD 3.5
Large). **Built and accepted on the rig the same evening** (journal 2026-10-15 21:22): CR6 changed three defaults — Krea 2 Turbo refines
(its partial denoise held), Z-Image loads its bf16 file cast to fp8_e4m3fn (peak 14.51 → 13.87 GB), Krea 2's Draft tier stays at 960×544.

**Scope (the author, 2026-10-15):**

| Model | t2i | i2i | Variant |
| --- | --- | --- | --- |
| Krea 2 Turbo | yes | if the rig shows that partial denoise holds at 8 steps (§6) | `full` |
| Krea 2 Raw | yes | yes | `full` |
| Z-Image (base) | yes | yes | `full` + `open` |
| Chroma1-HD | yes | yes | `full` + `open` |
| SD 3.5 Large | — | yes | `full` |

"t2i" means Generate (the `T2I` recipe). "i2i" means the Edit suite's **Refine** (the `I2I` recipe: partial denoise of the visible
document, the active layer or a selection). In loom2 that is the only i2i surface today, and the new models appear in its model picker
without frontend work.

**In this wave, added by the author's answer 3:** Krea 2's nine style LoRAs as roster LoRAs with base `krea2` (the LoRA slots take them on
both Krea specs). **Out of this wave:** Krea 2's style-reference LoRA (fetched; a preset, never a slot — wave CR+, §8); the levers in 02 (Explore grid, handoff, prompt
expansion); tiled refine (Upscale) and inpainting on the new families; reference images (`refs`) on the new families.

## 1. Decision to record (proposed D89) and questions for the author

> **D89 · Wave CR — creative t2i / i2i models (`.docs/creative_image/04`)**: Krea 2 Turbo + Raw (`full`), Z-Image base and Chroma1-HD
> (`full` + `open`) as Generate and Refine models, SD 3.5 Large as a Refine-only model (`full`). All run on core nodes of the pinned engine
> (v0.39.0: `Krea2`, `ZImage`, `Chroma`, `SD3`), with no custom node. The graphs come from the Comfy templates in the engine venv
> (`comfyui_workflow_templates_json`). `build_t2i` / `build_i2i` gain a per-graph family table, and the FLUX.2 / Klein graphs stay
> byte-identical. ≈ 73 GB of weights; the Krea 2 encoder and VAE, and Z-Image's encoder, reuse files loom2 already holds or shares between
> the new models. Closed by a rig acceptance (`scripts/cr_acceptance.py`).

Questions (§9 has the defaults I would assume):

1. **Krea 2 licence.** The deployer must run "reasonable content filters", and commercial use is capped at USD 1 M revenue. Is loom2, as a
   single-user local studio, fine with that duty recorded as the author's (default: yes, noted in the roster `license` field and in the
   Models suite), or should the wave ship a filter?
2. **SD 3.5 licence.** The Stability AI Community License caps commercial use at USD 1 M revenue and binds the user to its acceptable use
   policy. Accept it (default: yes, `full` only)?
3. **Downloads.** ≈ 73 GB to `F:/loom2-models` (660 GB free), plus ≈ 4.7 GB if the Krea style LoRAs come along. Approve?
4. **SD 3.5 size.** Large (8.1B, the bundled fp8 checkpoint is 14.9 GB) or Medium (2.5B, 11.6 GB bundle, weaker)? Default: Large.

## 2. What exists and what is missing

- `models/registry.py`: `IMAGE_GRAPHS = ("flux2", "klein")`. Everything image-side filters on it: `image_spec`, `image_specs()` → the
  `/capabilities` model lists, tiers, `te_alternates`, `recipe_te_id`.
- `engine/graphs.py`: `build_t2i` and `build_i2i` are FLUX.2-shaped: `CLIPLoader type=flux2`, `EmptyFlux2LatentImage`, `FluxGuidance`,
  `ReferenceLatent` references. `_flux2_loaders` (used by i2i, inpaint and tiled refine) assumes UNET + CLIP + VAE.
- `models/spec.py`: the `Graph` literal lists the builders. A spec cannot name a graph that does not exist.
- The frontend lists `caps.models` by `order` and gates on `recipes`. The Edit Refine picker shows the `i2i` models
  (`EditSuite.tsx:362, 440`); its strength slider runs 0.1–0.8.

The four families differ from FLUX.2 in a handful of places, all read from the pinned templates:

| Graph | Loader | `CLIPLoader.type` | Empty latent | Guidance | Negative | Shift | Sampling (template) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `flux2` / `klein` (today) | UNET + CLIP + VAE | `flux2` | `EmptyFlux2LatentImage` | `FluxGuidance` | zero-out or text | `ModelSamplingFlux` on request | as now |
| `krea2` | UNET + CLIP + VAE | `krea2` | `EmptyLatentImage` | none | `ConditioningZeroOut` (Turbo) / text (Raw) | built-in 1.15; `ModelSamplingFlux` (base 0.5 / max 1.15) on request | Turbo 8 st, CFG 1, euler / simple · Raw 52 st (CLI default 28), CFG 3.5–4.5 |
| `zimage` | UNET + CLIP + VAE | `lumina2` | `EmptySD3LatentImage` | none | text | `ModelSamplingAuraFlow` 3 (= built-in) | 25 st, CFG 4, res_multistep / simple |
| `chroma` | UNET + CLIP + VAE, plus `T5TokenizerOptions(0, 0)` | `chroma` | `EmptySD3LatentImage` | none | text | `ModelSamplingAuraFlow` 1 | 26 st, CFG 3.5, euler / beta |
| `sd3` | `CheckpointLoaderSimple` (the fp8 bundle carries CLIP-L/G + T5) | — | (i2i: `VAEEncode`) | none | text | built-in 3.0 | 20 st, CFG 4, euler / sgm_uniform |

## 3. Weights (proposed roster ids; sizes from the HF API, 2026-10-15)

| Roster id (proposed) | File | Repo | GB | Licence | Variants | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `krea2-turbo-fp8` | `krea2_turbo_fp8_scaled.safetensors` | Comfy-Org/Krea-2 | 13.14 | krea-2-community | full | not gated on Comfy-Org |
| `krea2-raw-fp8` | `krea2_raw_fp8_scaled.safetensors` | Comfy-Org/Krea-2 | 13.14 | krea-2-community | full | |
| `qwen3vl-4b-fp8` | `qwen3vl_4b_fp8_scaled.safetensors` | Comfy-Org/Krea-2 | 5.24 | apache-2.0 (Qwen3-VL) | full, open | the Krea 2 encoder; check the licence on the file's model card |
| `qwen-image-vae` (exists) | `qwen_image_vae.safetensors` | — | — | apache-2.0 | — | **same sha256** as Comfy-Org/Krea-2's copy (a70580f0…) — reused |
| `zimage-bf16` | `z_image_bf16.safetensors` | Comfy-Org/z_image | 12.31 | apache-2.0 | full, open | no fp8 file published; load with `weight_dtype = fp8_e4m3fn` if bf16 streams (§6). Avoid `int8_convrot` (04 §8: gfx1201) |
| `qwen3-4b` (exists) | `qwen_3_4b.safetensors` | — | — | apache-2.0 | — | **same sha256** as Comfy-Org/z_image_turbo's copy (6c671498…) — reused |
| `flux1-ae` | `ae.safetensors` | Comfy-Org/z_image_turbo (split_files/vae) | 0.34 | apache-2.0 | full, open | the FLUX.1 VAE; same sha256 as the Lumina repackage that Chroma's template names — one entry for both |
| `chroma1-hd-fp8mixed` | `Chroma1-HD-fp8mixed.safetensors` | Comfy-Org/Chroma1-HD_repackaged | 9.19 | apache-2.0 | full, open | |
| `t5xxl-fp8-scaled` | `t5xxl_fp8_e4m3fn_scaled.safetensors` | comfyanonymous/flux_text_encoders | 5.16 | apache-2.0 | full, open | Chroma's encoder |
| `sd35-large-fp8` | `sd3.5_large_fp8_scaled.safetensors` (folder `checkpoints`) | Comfy-Org/stable-diffusion-3.5-fp8 | 14.93 | stabilityai-ai-community | full | bundles CLIP-L, CLIP-G and T5 fp8; not gated |

Total ≈ **72.5 GB** new, plus ten Krea LoRAs at 0.47 GB each (9 styles + `krea2_style_reference`; fetched with the wave, answer 3) ≈ **77 GB**.

## 4. Code changes

### 4a. Specs and registry (data, D65)

- `models/spec.py`: `Graph` gains `"krea2" | "zimage" | "chroma" | "sd3"`.
- `models/registry.py`: `IMAGE_GRAPHS` gains the four. `_check` adds two rules:
  - a `sd3` (checkpoint) spec has no `roles.te` / `roles.vae`, and every other image graph needs both;
  - a spec with `recipes.inpaint`, `stage`, `reangle` or `refs_max > 0` must be on a FLUX graph. This keeps the new families out of the
    paths this wave does not port.
- Four new spec files. Values come from the templates; `estimates` are placeholders marked unmeasured until the rig run (§6):

```toml
# specs/krea2.toml — Krea 2 (Krea AI, 2026-06): trained for creative and stylistic exploration (Krea's technical report). Community licence:
# commercial use under USD 1 M revenue, content filters by the deployer (D89, 01 §2). Graph from the pinned image_krea2_turbo_t2i template.
[[model]]
id = "krea2-turbo-fp8"
family = "krea2"
label = "Krea 2 Turbo"
short = "krea turbo"
hint = "creative, fast; little variety across seeds"
order = 20
graph = "krea2"
roles.te = { default = "qwen3vl-4b-fp8" }
roles.vae = "qwen-image-vae"
sampling = { steps = 8, cfg = 1.0, guidance = 0.0, sampler = "euler", scheduler = "simple", distilled = true, json_prompt = false }
recipes = { t2i = true }                      # i2i only if CR6 shows partial denoise holds at 8 steps (§6)
geometry = { size_mult = 16, tiers = { thumb = [896, 512], draft = [960, 544], full = [1920, 1088] } }
estimates = { vram_gb = 15.0 }                # unmeasured (CR6)

[[model]]
id = "krea2-raw-fp8"
family = "krea2"
label = "Krea 2 Raw"
short = "krea raw"
hint = "creative, real CFG and negatives; slow"
order = 21
graph = "krea2"
roles.te = { default = "qwen3vl-4b-fp8" }
roles.vae = "qwen-image-vae"
sampling = { steps = 28, cfg = 4.0, guidance = 0.0, sampler = "euler", scheduler = "simple", json_prompt = false }
recipes = { t2i = true, i2i = true }
geometry = { size_mult = 16, tiers = { thumb = [896, 512], draft = [960, 544], full = [1344, 768] } }   # Raw is trained to about 1 MP
estimates = { vram_gb = 15.0 }
```

```toml
# specs/zimage.toml — Z-Image base (Tongyi-MAI, 2026-01), Apache-2.0: the undistilled checkpoint, high seed diversity, real CFG.
[[model]]
id = "zimage-bf16"
family = "zimage"
label = "Z-Image"
short = "z-image"
hint = "creative, open licence; real CFG and negatives"
order = 22
graph = "zimage"
roles.te = { default = "qwen3-4b" }
roles.vae = "flux1-ae"
sampling = { steps = 25, cfg = 4.0, guidance = 0.0, sampler = "res_multistep", scheduler = "simple", json_prompt = false, model_shift = 3.0 }
recipes = { t2i = true, i2i = true }
geometry = { size_mult = 16, tiers = { thumb = [896, 512], draft = [960, 544], full = [1920, 1088] } }
estimates = { vram_gb = 14.0 }
```

```toml
# specs/chroma.toml — Chroma1-HD (lodestones), Apache-2.0: FLUX.1-schnell retrained on artistic and niche styles; uncensored (01 §2).
[[model]]
id = "chroma1-hd-fp8mixed"
family = "chroma"
label = "Chroma1-HD"
short = "chroma"
hint = "artistic range, open licence; slow"
order = 23
graph = "chroma"
roles.te = { default = "t5xxl-fp8-scaled" }
roles.vae = "flux1-ae"
sampling = { steps = 26, cfg = 3.5, guidance = 0.0, sampler = "euler", scheduler = "beta", json_prompt = false, model_shift = 1.0 }
recipes = { t2i = true, i2i = true }
geometry = { size_mult = 16, tiers = { thumb = [896, 512], draft = [960, 544], full = [1344, 768] } }
estimates = { vram_gb = 13.0 }
```

```toml
# specs/sd35.toml — SD 3.5 Large (Stability AI, 2024-10): Refine only (D89) — a broad style range for re-imagining a board.
[[model]]
id = "sd35-large-fp8"
family = "sd3"
label = "SD 3.5 Large"
short = "sd3.5"
hint = "re-imagines in many styles; Refine only"
order = 24
graph = "sd3"
sampling = { steps = 20, cfg = 4.0, guidance = 0.0, sampler = "euler", scheduler = "sgm_uniform", json_prompt = false }
recipes = { i2i = true }
geometry = { size_mult = 16 }
estimates = { vram_gb = 14.0 }
```

The roster entries (§3) go in `roster.py`, next to the existing families. `scripts/model_literals_check.py` keeps the ids out of code.

### 4b. Graph builders (`engine/graphs.py`)

1. **A family table** (`engine/image_families.py`, new; about 60 lines): per `graph` it records the loader kind (unet / checkpoint), the
   `CLIPLoader.type`, the empty-latent class, whether `FluxGuidance` applies, the shift node class, the extra tokenizer node, and whether
   `ReferenceLatent` references exist. It holds node shapes only; values (steps, CFG, shift, sampler) stay in the spec.
2. **`_flux2_loaders` → `_image_loaders`**: returns `(model, clip, vae)` links. The `sd3` checkpoint path uses one
   `CheckpointLoaderSimple` (outputs 0 / 1 / 2). `te_device` / `te_id` on a checkpoint model is a `CompileError` (there is no separate
   encoder to move). `_te_loader` takes the family's `type` instead of the fixed `"flux2"`.
3. **`build_t2i`**: the loader, latent, guidance and shift nodes come from the table. On families without `FluxGuidance` the positive
   conditioning goes straight to the sampler. The negative is `CLIPTextEncode(negative)` when the spec is not distilled and the recipe has
   one, else `ConditioningZeroOut`. The FLUX.2-only branches (`Flux2Scheduler`, Turbo LoRA, refs) are unchanged and unreachable from the new
   specs.
4. **`build_i2i`**: same loaders. Guidance only on FLUX graphs. The fixed refine negative (`"blurry, low quality, text, watermark"`) stays
   for real-CFG families. The KSampler uses the spec's sampler and scheduler instead of the hard-coded euler / simple, for every family. That
   changes nothing for FLUX.2 / Klein, whose specs already say euler / simple.
5. **Node ids stay stable** for flux2 / klein, so `test_graph_parity_d64.py` passes **without** `--parity-update`. That is the proof the
   refactor changed nothing (the same `graph_hash` for every FLUX.2 recipe in `pin_review.recipes()`).
6. **Guards:** `build_inpaint`, `build_upscale` (tiled refine), `build_reangle` and `build_stage_shot` refuse a non-FLUX graph with a
   `CompileError` naming the model, and `/capabilities` keeps those pickers on FLUX specs (filter by recipe flags; the registry rule in 4a
   enforces them).

### 4c. Display == reality (T8) and `/capabilities`

- `effective_params` reports `guidance: None` on families without `FluxGuidance`, and `negative_used` honestly. The Generate panel hides
  Guidance when it is `None` and shows Negative only for non-distilled specs. Read the current gating in `GenerateSuite.tsx` during CR1. If
  it keys on `guidance` being present, nothing changes; if not, add one flag to `/capabilities.models[id]`, re-export OpenAPI and run
  `npm run api:types`.
- `capabilities.image_tiers()` gives each new family its tiers. `advanced()` shows each family's shift.
- `scripts/settings_audit.py`: every new spec field must reach the graph; the audit stays clean with no new allow-list lines.

### 4d. Fixture, pin review and tests

- **Fixture:** recapture `orchestrator/tests/fixtures/object_info.json` from the running pinned engine with
  `scripts/make_object_info_fixture.py`. The new classes and enum values are `EmptyLatentImage`, `EmptySD3LatentImage`,
  `ModelSamplingAuraFlow`, `T5TokenizerOptions`, and `CLIPLoader.type` ∋ `krea2 | lumina2 | chroma`. Then the contract check sees the new
  file names via the roster.
- **`scripts/pin_review.py` `recipes()`:** add `t2i krea turbo`, `t2i krea raw`, `t2i z-image`, `t2i chroma` and `i2i` for krea raw /
  z-image / chroma / sd3.5.
- **`test_registry_d65.py::test_sweep_every_spec_compiles`:** it picks the new specs up by itself (every tier and recipe, zero problems,
  estimates growing with pixels).
- **New `tests/test_creative_d89.py`** (≈ 12 tests):
  - each family's node set: loader type, latent class, no `FluxGuidance` off FLUX, the negative wired when CFG > 1, the shift node value,
    and `T5TokenizerOptions` only on Chroma;
  - SD 3.5: T2I is refused ("no T2I preset") and I2I compiles through `CheckpointLoaderSimple`;
  - the `open` variant offers Z-Image and Chroma and hides Krea 2 and SD 3.5;
  - Refine's picker lists all five i2i models; inpaint, tiled refine, Angle and Stage list none of them;
  - `te_device` on SD 3.5 is a `CompileError`;
  - LoRA slots refuse a Klein LoRA on a Krea spec (the `base` check).
- Frontend: Vitest only if 4c adds a flag; one smoke scenario that the Refine picker shows a new model in both variants.

## 5. Slices

| Slice | Content | Effort |
| --- | --- | --- |
| **CR0** | D89 recorded in 13; the author's answers to §1; `scripts/fetch_weights.py` for §3's entries (sha256 into the ledger); journal line | 0.5 d |
| **CR1** | The family table + `_image_loaders` refactor with the FLUX.2 / Klein graphs byte-identical (parity without update), guards, registry rules; offline suite green | 1 d |
| **CR2** | Z-Image + Chroma specs and graph rows; fixture recapture; tests | 1 d |
| **CR3** | Krea 2 Turbo + Raw specs and graph row; tests | 0.5 d |
| **CR4** | SD 3.5 Large (checkpoint loader path, i2i-only spec); tests | 0.5 d |
| **CR5** | `/capabilities` and panel check (4c), settings audit, OpenAPI and types if needed, `pin_review` variants, smoke | 0.5 d |
| **CR6** | Rig acceptance (`scripts/cr_acceptance.py`), journal, measured `estimates` into the specs, NO-GO handling (§6) | 1 d |

≈ **5 days**. CR2–CR4 are independent after CR1 and can be built in any order. CR6 runs once all three are in.

## 6. Rig acceptance (CR6, `scripts/cr_acceptance.py`, through the app like `cn_acceptance.py`)

Per model, on `F:` weights, with the engine started fresh and `--reserve-vram 1.5`:

| Check | How | Bar (proposed; the author can adjust) |
| --- | --- | --- |
| t2i cold / warm, Draft 960×544 | 3 prompts from `bench/t2i` (01-alley-rain, 06-fish-market, 07-portrait-grief), 2 seeds | warm ≤ 60 s for Turbo, ≤ 180 s for Raw / Z-Image / Chroma; cold recorded |
| peak VRAM | the engine's `/system_stats` during the job | ≤ 14.5 GB (leaves the reserve); DynamicVRAM streaming noted, as with D31 |
| sane output | no black / NaN frames, the right size, the manifest's `serialized_prompt` and `graph_hash` | 6 / 6 |
| seed variety | 8 seeds of one prompt: mean pairwise DINO distance, against Klein 9B and FLUX.2 dev on the same prompt | recorded (the point of the wave); no bar |
| i2i (Refine) | 3 Draft board frames at strength 0.3 / 0.55 / 0.75: DINO to the source + the author's look | strength 0.3 keeps the composition (DINO ≥ 0.8); 0.75 visibly re-imagines it |
| Krea 2 Turbo i2i | the same at 8 steps | if 0.3–0.55 holds, `recipes.i2i = true` on Turbo; otherwise Raw alone does i2i (stated in the hint) |
| Z-Image weight dtype | bf16 `default` vs `fp8_e4m3fn` cast in `UNETLoader` | the faster one that passes the look becomes the spec's `weight_dtype` |
| Krea 2 Draft size | 960×544 vs 1280×720 at the same seed | if 960×544 is visibly worse, Krea's Draft tier moves to 1280×720 (D18 allows per-family tiers) |
| open variant | launch `open`: Z-Image and Chroma listed, Krea 2 and SD 3.5 absent | pass |

**A NO-GO** is a model that misses the VRAM bar after the dtype and encoder options, or produces broken output on ROCm. Its spec gets
`wired = false` with `disabled_reason`, its weights are deleted (D30), and the journal records it. The rest of the wave still closes.

## 7. Risks

- **Krea 2 on 16 GB:** 13.1 GB transformer + 5.2 GB encoder > 16 GB, so DynamicVRAM streams the first job (the D31 pattern). The mitigation
  is the encoder unloaded between prompt and sampling (the default) or `te_device = cpu` (slow per new prompt). There is no GGUF of the
  Krea transformer yet.
- **Z-Image bf16 at 12.3 GB + an 8 GB encoder:** the same pattern; the fp8 cast or the existing GGUF-encoder idea (D31) mitigates it.
- **fp8 "scaled" files on gfx1201:** FLUX.2 dev's fp8mixed works here, so this is likely fine. INT8 convrot builds are avoided until 04 §8
  clears them.
- **The refactor touching every FLUX.2 recipe:** parity without `--parity-update` is the gate; CR1 lands alone, before any new model.
- **Content:** Chroma is uncensored, and Krea's licence asks for filters. Both are recorded in their roster `license` / `note` and on the
  Models suite card. A filter is a separate decision (§1 question 1).

## 8. After the wave (CR+, not scoped here)

- Krea 2 **style reference** as creative i2i: `TextEncodeQwenImageEditPlus` + `FluxKontextMultiReferenceLatentMethod` + the
  `krea2_style_reference` LoRA (the pinned `image_krea2_turbo_int8_image_style_reference` template, on the fp8 transformer). It would enter
  through T2I `refs` with `refs_max = 2` on Krea, plus a "Style from image…" verb.
- **Prompt expansion** through the core `TextGenerate` node. Krea's template already runs it on `qwen3vl_4b_fp8_scaled`, so that encoder
  file keeps its language-model head (02 §5).
- **Explore grid** and the first-step handoff (02 §1–2, §7).

## 9. Defaults assumed if the author does not say otherwise

Krea 2's filter duty is recorded as the author's (no filter in this wave). The Stability licence is accepted for `full`. The downloads are
approved without the Krea LoRAs. SD 3.5 Large, not Medium. The Refine strength slider keeps its 0.1–0.8 range. CR6 decides Krea Turbo i2i,
Z-Image's dtype and Krea's Draft size.
