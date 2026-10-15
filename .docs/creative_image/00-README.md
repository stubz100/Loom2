# Creative image models — study (2026-10-15)

FLUX.2 dev follows prompts closely but is not very creative: seeds converge on one composition, one light and one "house look". Klein's
distilled checkpoints behave the same way. This study looks for open text-to-image (t2i) and image-to-image (i2i) models, plus
model-independent techniques, that loom2 can add for **ideation** (many different takes on a board) while FLUX.2 keeps the
**accurate pass**.

It was a quick web pass, not a rig run. Every number below is a vendor or community figure until it is measured on the RX 9070 XT (house
rule 1). Licences are read against EU terms (D17), and the variant column follows D26.

## Reading order

| File | Contents |
| --- | --- |
| [01-candidates.md](01-candidates.md) | the models found, what the pinned engine already supports, licence, 16 GB fit, what is creative about each; sources |
| [02-creativity-levers.md](02-creativity-levers.md) | techniques that add variety with any model (base vs distilled, first-step handoff, APG, diversity LoRA, prompt expansion, style references) |
| [03-loom2-integration.md](03-loom2-integration.md) | how they enter loom2 under D65 (specs are data), the graphs and fixtures they need, proposed spikes and build steps, UI placement |
| [04-implementation-plan.md](04-implementation-plan.md) | **wave CR** (the author's pick, 2026-10-15): Krea 2 Turbo / Raw, Z-Image and Chroma for t2i + i2i, SD 3.5 Large for i2i only — proposed D89, weights, code changes, slices CR0–CR6, rig acceptance |

## Summary

**The engine is ready.** The pinned ComfyUI (v0.39.0) already has native model classes for Krea 2, Z-Image, Chroma, HiDream-O1,
Qwen-Image-2.1, Ideogram 4 and SDXL (`comfy/supported_models.py`). None of the candidates needs a custom node, so house rule 2 is not
triggered. Each needs a roster entry, a spec, and a graph builder for its family.

**Recommended order:**

1. **Levers on the models loom2 already has** (no downloads). Klein base 4B/9B with real CFG and negatives, the base-then-distilled
   first-step handoff, APG, seed × prompt variation grids, and prompt expansion through the core `TextGenerate` node. This is the cheapest
   test of how much of the "not creative" problem comes from distillation rather than from the model.
2. **Krea 2 (Turbo + Raw)** for the `full` variant. It is trained explicitly for "creative and stylistic exploration", ships 9 style LoRAs
   and a style-reference LoRA (1–2 images, which makes it a creative i2i model), and has native ComfyUI support. Its Community License has no
   EU exclusion, but commercial use is capped at USD 1 M company revenue and the deployer must run a content filter. It is 12.9B: fp8 is
   about 13 GB plus a Qwen3-VL-4B encoder, so expect DynamicVRAM streaming as with Klein 9B.
3. **Z-Image (base)** for the `open` variant. It is Apache-2.0 and 6B, so it fits easily. The non-distilled checkpoint is documented as
   high-diversity, with real CFG and negatives. It probably shares the Qwen3-4B encoder file with Klein 4B; check the sha256.
4. **Chroma1-HD** as a second `open` candidate: Apache-2.0, 8.9B, real CFG, trained on artistic and niche styles. It is slower, needs a
   T5-XXL encoder, and is uncensored, which needs a policy note.
5. **To watch:** HiDream-O1 (MIT, unified t2i + editing + storyboard mode, unmeasured on ROCm), Qwen-Image-2.1 (non-commercial; RGBA and
   10-reference editing are its strengths, more than creativity) and Ideogram 4 (non-commercial, typography and design, tight on 16 GB).
   SDXL Illustrious / NoobAI is fast and has a huge style-LoRA ecosystem, but it leans anime and uses tag prompts. SD 3.5 Large (Stability
   Community licence, under USD 1 M revenue) has a broad style range and varied seeds on paper, but it dates from 2024 and is weaker on
   anatomy and adherence; it is an optional entrant in the bake-off.

**Product shape:** *diverge, then converge.* A creative model (or Klein with the levers) fills a variation grid at the Thumb or Draft tier.
The author picks tiles, and FLUX.2 dev or Klein refines the pick through i2i or references, which loom2 already has.

## Status

This is a proposal only. Nothing is built, fetched or decided. Taking any of it forward needs a D-number in
`.docs/proto01/13-decision-log-and-open-questions.md` before the work, and spike numbers (E21–E23 are proposed in 03) confirmed there.
