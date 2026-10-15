# 01 — Candidate models

Status 2026-10-15, from a web pass. "Engine" means the class exists in the pinned `engine/comfyui` (v0.39.0, `comfy/supported_models.py`).
Fit figures are community estimates for 16 GB. They are unmeasured on the RX 9070 XT.

## 1. Overview

| Model | Params | Text encoder | Licence (EU read, D17) | Variant (D26) | Engine | 16 GB fit (estimate) | Creative angle | i2i / edit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Krea 2 Turbo / Raw** | 12.9B | Qwen3-VL-4B (fp8) | Krea 2 Community: worldwide, no EU clause; commercial only under USD 1 M company revenue; content filter required | `full` | `Krea2` | fp8 ≈ 13 GB + encoder → streamed | trained for "creative and stylistic exploration"; 9 style LoRAs | style reference (1–2 images) |
| **Z-Image (base)** | 6B | Qwen3-4B (probably Klein 4B's file) | Apache-2.0 | `open` + `full` | `ZImage` | bf16 ≈ 12 GB, fp8 ≈ 6 GB → fits | documented "high" seed diversity; real CFG 3–5, negatives | i2i by denoise; Edit variant not confirmed released |
| **Chroma1-HD** | 8.9B | T5-XXL | Apache-2.0 | `open` + `full` | `Chroma` | bf16 17.8 GB; Q8 GGUF 9.7 GB / fp8 ≈ 9 GB | artistic and niche styles in training; real CFG; uncensored | i2i by denoise |
| HiDream-O1-Image (Full / Dev) | 8B | none (pixel-space unified transformer); Gemma-4 E4B optional for prompt enhancement | MIT | `open` + `full` | `HiDreamO1` | fp8 file ≈ 10 GB; bf16 compute only | vendor claims parity with Qwen-Image; storyboard mode | instruction editing, subject references |
| Qwen-Image-2.1 | 7B | Qwen3-VL-8B (bf16 17.5 GB, int8 9.4 GB, w4a8 6.3 GB) | Qwen Research, **non-commercial** (2026-09-20) | `full`, flagged | `QwenImage21` | int8 denoiser + w4a8 encoder suggested for 16–24 GB | dense detail; native 2K; RGBA output | edit with 10 references, RGBA layers |
| Ideogram 4 | 9.3B | Qwen3-VL-8B | weights **non-commercial** (Ideogram NC Model Agreement), gated | `full`, flagged | `Ideogram4` | nf4 10–12 GB (CUDA path), fp8 16 GB+ → tight | typography and design layouts | — |
| SD 3.5 Large / Large Turbo / Medium | 8.1B / 8.1B / 2.5B | CLIP-L + CLIP-G + T5-XXL | Stability AI Community: free under USD 1 M company revenue, outputs owned by the user; no EU clause found in summaries (read the text) | `full` | `SD3` | Large fp8 ≈ 8 GB + T5 fp8 ≈ 5 GB → probably fits; Medium easily | broad style range (3D, painting, line art, photo); varied outputs per seed (QK-norm); not style-restricted | i2i by denoise; Stability ControlNets |
| SDXL: Illustrious XL / NoobAI-XL | 2.6B UNet | CLIP-L + G | Fair AI Public License family (verify each checkpoint) | `full` | `SDXL` | ≈ 7 GB → fits easily, seconds per image | largest style-LoRA ecosystem; anime and illustration lean | i2i, many ControlNets |

**Excluded:** Midjourney, GPT Image and Recraft (closed). Ideogram is also sold as an API, but the weights row above is the open release. USO
(a FLUX.1-dev LoRA under a non-commercial licence, superseded by Krea 2's style reference). HunyuanImage (Tencent's community licences exclude
the EU, the same reason Hunyuan3D is excluded, D17). Qwen-Image-2512 (Apache, but 20B: fp8 is 19 GB, and 2.1 superseded it).

The pin also lists `MageFlow` (Qwen3-VL-4B encoder, FLUX.2 latent). It was not researched.

## 2. Notes per model

### Krea 2 (Krea AI, released 2026-06-22) — the creativity lead

- **Two checkpoints.** Raw is undistilled: 52 steps, real CFG, and the target for LoRA training. Turbo is distilled for guidance and
  timesteps: 8 steps, CFG 0, mu 1.15. LoRAs trained on Raw run on Turbo.
- **Creativity is the design goal.** The technical report argues that most models have "converged on a narrow set of default aesthetics".
  Krea avoided aesthetic-score filtering that punishes deliberate softness or motion blur, kept long-tail concepts through clustering, left
  AI-generated images out of pretraining, and trained its prompt expander with a diversity reward.
- **Styles.** Nine style LoRAs ship with it (darkbrush, dotmatrix, kidsdrawing, neondrip, rainywindow, retroanime, softwatercolor,
  sunsetblur, vintagetarot), plus `krea2_style_reference`, which conditions a generation on 1–2 style images with a strength per
  reference. That makes it the creative **i2i** path: style transfer, not structure transfer. General image editing is listed as future
  work.
- **ComfyUI.** Native since v0.26. The Comfy-Org repackage provides `krea2_turbo_fp8_scaled`, `krea2_turbo_int8_convrot`, bf16, NVFP4 and
  MXFP8, the encoder `qwen3vl_4b_fp8_scaled` and the VAE `qwen_image_vae`. loom2's roster already has a `qwen-image-vae` entry; compare the
  sha256. The Comfy template includes an LLM prompt-enhancer toggle.
- **Weakness.** Turbo has low seed diversity: one prompt gives nearly the same image on every seed. That is distillation again, and the fix
  is in [02 §2–4](02-creativity-levers.md).
- **Licence** (krea.ai/krea-2-licensing): a worldwide, revocable, royalty-free grant; no territorial clause, only trade-compliance and US
  export language; outputs belong to the user. Commercial use is allowed only below USD 1 M trailing-12-month company revenue. The deployer
  must implement "reasonable content filters". Derivatives must be named "Krea …", and redistribution needs a NOTICE file. Krea can terminate
  on 30 days' notice; Delaware law. For a personal, local studio this is usable in `full`, but the filter duty needs a decision (for example,
  a user-side check on export).

### Z-Image (Tongyi-MAI / Alibaba) — the `open` creativity candidate

- The repository is `Tongyi-MAI/Z-Image`, the undistilled sibling of Z-Image-Turbo, released 2026-01-28. It recommends CFG 3–5 and 28–50
  steps; ComfyUI guides use res_multistep with shift 3.
- The model card rates diversity "High" against "Low" for Turbo: more variation in composition, faces and lighting across seeds, robust
  negative prompts, and a good base for LoRA and ControlNet. Its range covers photo, cinematic digital art, anime and illustration.
- Reviewers warn it is "not the best at everything" for artistic range; Turbo trades variety for balanced, simplified compositions.
- It is the cheapest fit on the list, and with an Apache licence it is a candidate for the `open` default alongside Klein 4B.

### Chroma1-HD (lodestones)

- A FLUX.1-schnell derivative, retrained on 5 M samples curated from 20 M, including artistic, photographic and niche styles. It has real
  CFG and working negatives at 26–40 steps. Chroma1-Flash is the CFG-baked fast version; Chroma-Radiance is a pixel-space sibling, and the
  pin knows it too.
- It uses the T5-XXL encoder and the FLUX.1 VAE, which loom2 does not hold today (Wan's `umt5-xxl` is a different file).
- It is uncensored. Under D17 that is not a licence problem, but the app has no content filter, so record a policy note.

### HiDream-O1-Image (HiDream-ai, released 2026-05-08)

- A pixel-level unified transformer: text tokens and pixels share one token space, so there is no VAE and no separate encoder. An optional
  Gemma-4 E4B rewrites prompts; check Gemma's terms before adding it. Full uses 50 steps; Dev is distilled to 28 steps at CFG 1.
- It covers t2i, instruction editing, subject personalisation and a **storyboard generation** task at up to 2048². That task is relevant to
  loom2's purpose and worth a look on its own.
- The pin's class sets `optimizations = {"fp8": False}` and runs bf16 or fp32 only, so fp8 files are a storage format and compute upcasts.
  Upstream says "CUDA required". The ComfyUI native path should be device-neutral, but this is unmeasured on ROCm.

### Qwen-Image-2.1 (Alibaba, released 2026-09-20)

- One 7B checkpoint does generation and editing (up to 10 references, KV-cached), native 2K, and **RGBA output** through a 64-channel VAE.
  The ComfyUI template defaults to 25 steps at CFG 1 (negatives ignored); the official pipeline uses 40–50.
- Comparisons describe it as filling the frame with dense detail. That is a different strength from creativity. It is already on the 04 §7
  "watch" list under its NC licence; nothing found changes that.

### Ideogram 4 (Ideogram, released 2026-06-03)

- A 9.3B single-stream DiT with a Qwen3-VL-8B encoder. It leads on design and typography (posters, title cards), not painterly range.
- Its nf4 build relies on a CUDA quantisation path, and fp8 is 16 GB+, so it is a poor fit for this card. Low priority.

### Stable Diffusion 3.5 (Stability AI, released 2024-10)

Added 2026-10-15 after the first pass missed it.

- **Variants.** Large is an 8.1B MMDiT at 1 MP, about 30 steps (sources say 20–40) and real CFG. Large Turbo is the 4-step distilled
  version and should show low diversity, as other distilled models do. Medium is 2.5B, supports up to 2 MP, and is weaker on composition.
- **Why it is on the list.** At launch, reviewers found Large handled a wider range of styles than FLUX.1 and gave genuinely different takes
  per seed; Stability attributes this to QK-normalisation. It is not deliberately style-restricted. On paper that is exactly the creativity
  FLUX.2 lacks.
- **Against it.** It is two years older than everything else here: weaker anatomy and hands, prompt adherence below FLUX.2, and a
  community that has largely moved on to Illustrious, Chroma, Z-Image and Krea 2, so it has few new LoRAs. No 2026 comparison was found.
- **Engine and weights.** The core `SD3` class covers it. The T5-XXL encoder would be shared with Chroma if both entered the roster.
  Comfy-Org's `sd3.5_large_fp8_scaled` bundles the encoders; the split files fit loom2's roster better.
- **Licence.** Stability AI Community License: free for research and non-commercial use, commercial use below USD 1 M annual revenue, and
  an enterprise licence above that. That is close to Krea 2's terms, but without the content-filter duty in the summaries. Read the current
  text against D17 before fetching. `full` only (not Apache/MIT, D26).
- **Verdict:** a cheap optional entrant in the E22 bake-off (Large at real CFG, about 30 steps). It is worth one run to see whether its range
  outweighs its age; it is not a lead candidate.

### SDXL fine-tunes (Illustrious XL, NoobAI-XL and their merges)

- Still the most common base for illustration-style LoRAs in 2026. Generation takes seconds on 16 GB, and the core engine supports
  ControlNet and IP-Adapter-style models. Prompts are Danbooru-style tags (no prose or JSON), outputs lean anime, and the v-pred variants
  need Euler or DDIM. The licences are the Fair AI Public License family, not Apache, and must be read per checkpoint. Worth having only if
  the author wants a stylised board look loom2 cannot reach otherwise.

## Sources

- Krea 2: [technical report](https://www.krea.ai/blog/krea-2-technical-report) · [licence](https://www.krea.ai/krea-2-licensing) ·
  [GitHub](https://github.com/krea-ai/krea-2) · [HF Turbo card](https://huggingface.co/krea/Krea-2-Turbo) ·
  [ComfyUI docs](https://docs.comfy.org/tutorials/image/krea/krea-2) ·
  [ComfyUI wiki](https://comfyui-wiki.com/en/news/2026-06-22-krea-2-open-source-text-to-image) ·
  [local guide (VRAM, licence)](https://localaimaster.com/blog/krea-2-local-guide) ·
  [SDA diversity LoRA](https://comfyui-wiki.com/en/news/2026-09-07-krea2-sda-diversity-lora)
- Z-Image: [HF card](https://huggingface.co/Tongyi-MAI/Z-Image) ·
  [release note](https://comfyui-wiki.com/en/news/2026-01-28-alibaba-z-image-base-release) ·
  [base vs Turbo](https://wavespeed.ai/blog/posts/blog-what-is-z-image-base/) ·
  [16 GB review](https://saascrmreview.com/z-image-turbo-review/) ·
  [vs Qwen-Image-2512](https://dev.to/gary_yan_86eb77d35e0070f5/qwen-image-2512-vs-z-image-turbo-5-prompt-benchmark-which-model-is-better-5ni)
- Chroma: [HF card](https://huggingface.co/lodestones/Chroma1-HD) ·
  [ComfyUI wiki](https://comfyui-wiki.com/en/models/chroma/chroma-1-hd) · [local guide](https://localaimaster.com/blog/chroma-local-guide)
- HiDream-O1: [ComfyUI docs](https://docs.comfy.org/tutorials/image/hidream/hidream-o1) ·
  [paper](https://arxiv.org/pdf/2605.11061) · [ComfyUI PR #13817](https://github.com/Comfy-Org/ComfyUI/pull/13817) ·
  [wiki](https://comfyui-wiki.com/en/models/hidream/hidream-o1-image)
- Qwen-Image-2.1: [Comfy blog](https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight) ·
  [local guide (files, sizes)](https://codersera.com/blog/how-to-run-qwen-image-2-1-locally-2026/) ·
  [licence note](https://cellcog.ai/blog/qwen-image-2-1/)
- Ideogram 4: [Ideogram](https://ideogram.ai/models/4.0/) · [explainer](https://www.3daistudio.com/blog/ideogram-4-open-image-model-explained) ·
  [licence review](https://vidcella.ai/posts/ideogram-4-0-review) · [specs](https://invideo.io/blog/ideogram-ai-image-generator/) ·
  [VRAM](https://aitoolsradar.org/blog/reviews/ideogram-ai-review-2026/)
- SD 3.5: [Stability AI](https://stability.ai/stable-diffusion) ·
  [launch review (styles vs FLUX)](https://decrypt.co/287807/stable-diffusion-3-5-stability-ai-redeems-itself-with-new-models-and-expanded-features) ·
  [Replicate card (diversity, licence)](https://internal.replicate.com/stability-ai/stable-diffusion-3.5-large) ·
  [variants and licensing](https://www.promptzone.com/zuri_wang/stable-diffusion-35-variants-licensing-and-prompting-1e15.md)
- Overview and leaderboards: [Artificial Analysis T2I](https://artificialanalysis.ai/image/leaderboard/text-to-image) ·
  [self-host ranking](https://pinggy.io/blog/best_free_open_source_ai_image_generators_to_self_host/) ·
  [Illustrious fine-tunes](https://techtactician.com/?p=44869) · [USO](https://blog.comfy.org/p/uso-available-in-comfyui)
