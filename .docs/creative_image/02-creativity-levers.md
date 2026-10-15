# 02 — Creativity levers (model-independent)

"Not creative" usually means **low seed diversity** (one prompt gives one image) plus a **narrow default aesthetic**. The first is mostly a
property of guidance and step distillation, which affects Klein, Krea 2 Turbo and Z-Image-Turbo. The second is mostly about training data
and post-training. The levers below address the first on any model, and the second through styles and prompts. All of them use core engine
nodes, except where marked.

## 1. Use the base checkpoint, with real CFG

Distilled models settle the layout in the first denoising step; base models build it over many steps ("Distilling Diversity and Control in
Diffusion Models", arXiv 2503.10637). loom2 already has **Klein 4B base and 9B base** (`klein.toml`: t2i and i2i, real CFG, negatives), so an
"explore" preset on them costs no downloads. The same applies to Krea 2 Raw and Z-Image base.

The cost is about 50 steps instead of 4–8, which is fine at the Thumb tier and in overnight batches (D6 already plans for staged batches).

## 2. First-step handoff (base for step 1–2, distilled for the rest)

The paper above restores most of the base model's diversity by running **only the first step(s)** on the base model and the rest on the
distilled model, at nearly distilled speed. In ComfyUI this is two `KSamplerAdvanced` nodes with `start_at_step` / `end_at_step` on the same
latent. The pairs share a latent space:

| Base → distilled | Fit |
| --- | --- |
| Klein 4B base → Klein 4B | both resident ≈ 8 + 8 GB with the shared Qwen3-4B encoder → probably fits |
| Klein 9B base → Klein 9B | two 9B transformers → streamed; measure |
| Krea 2 Raw → Turbo | two 12.9B transformers → streamed or swapped; measure |
| Z-Image base → Turbo | two 6B → fits |

## 3. Guidance shaping (real-CFG models only)

- `APG` (Adaptive Projected Guidance, `comfy_extras/nodes_apg.py`) allows a higher CFG, which pushes harder towards the prompt and the
  negatives, without the oversaturation plain CFG gives. `nodes_tcfg.py` and `nodes_cfg.py` hold related options.
- Negative prompts become a creative control on base models: steer away from "studio lighting, centred subject, symmetrical" and the rest of
  the house look.

## 4. Diversity LoRA / noise tricks for distilled models

- **Krea 2 Turbo SDA LoRA** (F16, released 2026-09): rank 32, 447 MB. The author reports +85 % pairwise CLIP distance at equal HPSv2.1.
  It must apply **only during the first 2 of 8 steps**; on all 8 it degrades quality by about 10 % HPS. The published workflow uses
  ClownsharKSampler, a custom node, but the core hook nodes (`nodes_hooks.py`: `CreateHookLora` + `CreateHookKeyframe` /
  `SetHookKeyframes`) gate a LoRA by step without one. **No licence is stated**, so it cannot enter the roster until one is.
- **ComfyUI-DiversityBoost** is a training-free node for step-distilled models (FLUX.2 Klein, Z-Image-Turbo). It is a custom node, so it would
  need a D-number (house rule 2). It is listed for completeness; levers 1–2 should be measured first.
- Research to watch: noise optimisation for collapse recovery (CVPR 2026) and SliderSpace random directions. Neither is packaged.

## 5. Prompt expansion

- The core `TextGenerate` node (`comfy_extras/nodes_textgen.py`) runs a loaded text-encoder LLM as a generator, with temperature, top-p,
  seed, a system prompt and thinking mode. Krea 2's and HiDream-O1's Comfy templates use this for their prompt enhancers. Krea trained its
  expander with a diversity reward, which is the point: N expansions of one prompt give N different boards.
- **To check:** whether loom2's encoder files (`qwen_3_4b`, `qwen_3_8b_fp8mixed`, the Qwen3-8B GGUF, Krea's `qwen3vl_4b`) keep the LM head that
  `TextGenerate` needs. Encoder-only exports sometimes drop it.
- **T8 (display == reality):** the expanded prompt must show in the panel and be editable before or after the run. `Compiled.serialized_prompt`
  already records what the model saw. Expanding a FLUX.2 JSON prompt tree means expanding the prose fields, not the structure.

## 6. Styles and style references (creative i2i)

- Krea 2's nine style LoRAs and its style-reference LoRA (1–2 images, a strength per reference, built to limit content leakage) provide
  "this board in that look" without copying the reference's content.
- loom2's LoRA wave (D86) already trains LoRAs on Klein base 4B. A style LoRA from the author's own references is the same job with style
  captions.
- FLUX.2 / Klein multi-reference editing (dev up to 10 references) can already carry a style image. Measuring how much style it takes before
  content leaks is a cheap test.

## 7. Workflow: diverge, then converge

1. **Diverge:** N seeds × M prompt expansions at the Thumb tier on a creative model or with levers 1–2, laid out as a variation grid and run
   as a staged or overnight batch.
2. **Pick:** the author marks tiles (mouse-first: a click on each tile, or the right-click menu).
3. **Converge:** "Refine with FLUX.2" sends the picked tile to FLUX.2 dev or Klein i2i or reference editing at Draft or Full, keeping the
   composition and fixing adherence. The lineage records both steps.

This keeps FLUX.2 as the accurate model the author trusts, and adds variety where it matters, at the start.
