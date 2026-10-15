# 03 — Fitting it into loom2

## 1. What "easily implemented" means here

D65 makes models data: a roster entry and a `[[model]]` spec, plus a builder only when the family's node layout is new
(`orchestrator/loom2/engine/AGENTS.md` → "Add a model"). The frontend lists `caps.models` by `order` and needs no change for a new t2i model.
Each candidate's cost:

| Candidate | Roster entries (new) | New `graph` builder | Fixture recapture | Engine work | Effort |
| --- | --- | --- | --- | --- | --- |
| Levers on Klein (02 §1–3, §5) | none | no: a recipe flag in the `klein` graph (handoff, APG, expansion) | for `KSamplerAdvanced` / `APG` / `TextGenerate` if the fixture lacks them | none | **S** |
| Z-Image base | transformer; encoder probably reused (`qwen3-4b`, compare sha256); FLUX.1 VAE | `zimage` | yes | none (core `ZImage`) | **S–M** |
| Krea 2 Turbo (+ Raw) | 1–2 transformers, `qwen3vl_4b` encoder, VAE (compare with `qwen-image-vae`), style LoRAs | `krea2` (+ style-reference inputs) | yes | none (core `Krea2`) | **M** |
| Chroma1-HD | transformer, T5-XXL fp8, FLUX.1 VAE | `chroma` | yes | none (core `Chroma`) | **M** |
| HiDream-O1 | one checkpoint (+ optional Gemma-4 E4B) | `hidream_o1` (checkpoint loader, reference images, seam smoothing) | yes | none (core `HiDreamO1`); ROCm unproven | **M** |
| Qwen-Image-2.1 | transformer, Qwen3-VL-8B (int8 / w4a8), RGBA VAE | `qwen_image21`; RGBA through the finishers | yes | none (core `QwenImage21`) | **M–L** |

Take node class names and loader `type` values from the running engine's `/object_info` and the Comfy templates, not from this document.
Every new graph goes through `contract.py`, `test_registry_d65.py::test_sweep_every_spec_compiles` and `scripts/pin_review.py` `recipes()`.

## 2. Constraints that apply

- **16 GB first (rule 1).** Krea 2 (≈ 13 GB fp8 plus the encoder) will hit the same DynamicVRAM streaming that Klein 9B hit before D31.
  Measure cold and warm, with the encoder unloaded and with a GGUF or int8 encoder. fp8 before GGUF (D30). Per the 04 §8 re-check list, the
  INT8 convrot builds Comfy-Org now ships may still be broken on gfx1201.
- **Licences (D17 / D26).** `open`: Z-Image, Chroma, HiDream-O1 (MIT; Gemma terms for the optional enhancer). `full` and flagged: Krea 2
  (revenue cap, content-filter duty), Qwen-Image-2.1 and Ideogram 4 (non-commercial). Record the licence of the SDA LoRA and each style LoRA
  before it enters the roster.
- **Display == reality (T8).** CFG, steps, shift, expansion on or off, and handoff steps come from `/capabilities`, so the panel shows exactly
  what runs. `scripts/settings_audit.py` must stay clean.
- **Mouse-first (D32).** "Explore" (variation grid), "Expand prompt", "Refine with FLUX.2" and "Style from image" are commands in
  `frontend/src/frame/commands.ts`, each with a button or a right-click placement; keys are accelerators only. Presets go behind one icon
  per field, and nothing is mandatory.
- **Weights.** Fetch losers for the spike only, and delete them after (D30; as with E10–E14's 34 GB).

## 3. Proposed spikes (numbers to be confirmed in 13; E19 and E20 are taken)

| Spike | Question | Inputs | Measures | Downloads |
| --- | --- | --- | --- | --- |
| **E21 — levers on Klein** | How much diversity do base CFG, the first-step handoff, APG and prompt expansion buy with no new model? | the frozen `bench/` t2i prompts + a short "creative" set (moods, abstract briefs) | seed diversity (pairwise DINO or CLIP distance over 8 seeds), an aesthetic score, adherence against FLUX.2 dev, s/image, peak VRAM, the author's blind pick | none |
| **E22 — creative bake-off** | Which new model beats E21's best on variety without losing too much adherence? | the same prompts on Krea 2 Turbo (± SDA, ± style LoRA), Krea 2 Raw, Z-Image base, Chroma1-HD (HiDream-O1 and SD 3.5 Large optional) | as E21, plus cold and warm times at Thumb and Draft | yes, losers deleted |
| **E23 — creative i2i** | Style transfer that keeps composition: Krea 2 style reference vs FLUX.2 / Klein references vs a Klein style LoRA (D86 trainer) | 10 board frames × 5 style images | content keep (DINO against the source), style match (CLIP against the reference), leakage, time | Krea 2 (shared with E22) |

GO criteria to agree before the spike, for example: E22's winner gives ≥ 1.5× E21's best seed diversity at no more than 10 % adherence loss
and fits the D18 Draft tier in under 2 minutes warm.

## 4. Possible build waves (after a D-number)

1. **CI1 Explore mode.** The variation grid (N seeds × M expansions) on the default model, the handoff and APG as recipe options on the Klein
   graph, prompt expansion through `TextGenerate` with the expanded text shown and editable, and "Refine with FLUX.2" on a tile, with lineage
   linking pick and refine.
2. **CI2 Creative model.** E22's winner as a spec plus its builder: Krea 2 in `full`, Z-Image or Chroma in `open`, and an `order` that puts it
   beside FLUX.2 dev in Generate.
3. **CI3 Style from image.** E23's winner as an i2i entry ("Style from image…" on an asset's right-click menu), plus the style LoRAs as a
   picker.

Each wave closes with its rig run journaled in `.docs/proto01/90-journal.md` and the measured numbers in the spec's `estimates`.
