# 04 · Model strategy — sourcing convention, runtime policy, model selection

Research date 2026-10-04. Hardware: RX 9070 XT (gfx1201, 16 GB), Windows 11, 128 GB RAM, torch
2.13.0+rocm10.0.0 on Python 3.13 via uv — the agreed loom2 target stack, D16 (see 01 §2b; loom's 2.9.1+rocm7.2.1
venv is an A/B reference only). This document answers the user's point 1 (anchor model sourcing to one
convention) and evaluates the models for MVP targets a, b, c.

## 1. Decision: anchor on the ComfyUI convention, with GGUF as a format inside it

### 1a. The two candidate anchors

| | ComfyUI convention | Unsloth as the single source |
| --- | --- | --- |
| What it is | `models/<kind>/` folder keys + state-dict **key-based** model detection + Comfy-Org `split_files` safetensors as the reference artefact; `extra_model_paths.yaml` to mount other trees | Unsloth's "Diffusion GGUFs" collection (≈20 repos, Apr 2026): FLUX.2 dev / Klein 4B / 9B (+base), FLUX.1 dev/schnell/Kontext, Qwen-Image family, Z-Image, LTX-2/2.3; plus their LLM GGUFs usable as text encoders (Mistral-Small-3.2, Qwen3) |
| Coverage | everything ComfyUI core loads: diffusion models, text encoders, VAEs, LoRAs, ControlNets, upscalers, segmentation, video models, day-0 repackaging by Comfy-Org (Qwen-Image-2.1 within days) | **no Wan**, no FLUX.1 Fill, no SD3.5/SDXL, no ControlNets, no upscalers, no VAEs in matching layout; GGUFs are produced with city96's converter anyway |
| Formats | bf16, fp8 scaled / `fp8mixed`, `fp4mixed`, int8 (Jun 2026); GGUF through the ComfyUI-GGUF node | GGUF Q2–Q8 "Dynamic 2.0", bnb-4bit |
| ROCm fit | fp8 scaled compute is enabled on gfx1201 (torch ≥ 2.7, ROCm ≥ 6.4) and is the fastest path; GGUF dequantises with plain torch ops | GGUF only → always pays per-step dequant |
| Provenance | official org, stable filenames referenced by official templates | trusted quantiser, fast, well documented |
| Reuse of what is on disk | `D:\comfyui\ComfyUI\models` (≈150 GB) is already in this layout | the Q4_K_M FLUX.2-dev and Mistral GGUFs in `F:\HF_HOME` |

**Decision D1.** loom2 adopts the ComfyUI `models/` layout and key-based detection verbatim. Comfy-Org
`split_files` safetensors are the canonical artefacts; GGUF is the low-VRAM *format* inside the same
folders, sourced in freshness order **Unsloth → city96 → QuantStack**, each recorded with publisher and
sha256 in the roster. loom2 reads and writes `extra_model_paths.yaml`, so the user's existing ComfyUI tree
is mounted rather than copied, and anything the user drops into ComfyUI is visible to loom2.

Why not Unsloth-only: it would leave Wan 2.2 (the chosen i2v model), FLUX.1 Fill, ControlNets, upscalers and
matching VAEs/TEs outside the convention on day one, and we would still be reading GGUFs made with city96's
tooling.

### 1b. The roster (replaces loom's four manifests)

One `models.roster.json` (versioned, in git) + a per-machine resolved index (SQLite). Each entry:

```
id, kind (diffusion_model | text_encoder | vae | lora | controlnet | upscale | segmentation | video_model),
family (flux2-klein-9b | flux2-dev | wan2.2-i2v-a14b | …), role (what loom2 uses it for),
publisher (Comfy-Org | unsloth | city96 | QuantStack | black-forest-labs | …), repo_id, filename,
format (bf16 | fp8_scaled | fp8mixed | gguf-Q5_K_M | …), size_bytes, sha256, license (apache-2.0 |
flux-nc | ltx-community | tencent-community | qwen-research | …), gated (bool), tier (1 | 2 | 3),
detect (expected state-dict signature keys), notes
```

Rules carried from loom (02 §2): presence probe → explicit resumable **fetch as a queue job** with sha256
verify; the resolver pins a cached revision and never trusts `refs/main`; prune never deletes a complete
set; the Models page shows health per entry (`ok · missing · partial · drift · unused`).

The roster also drives the **build variants (D26)**: `full` (every licence the author holds — dev, Klein 9B,
FLUX.1 Fill, LTX, H3 after application) and `open` (Apache-2.0 / MIT only — Klein 4B, Wan 2.2, Qwen-Image-Edit-
2511, SeedVR2, BiRefNet, SAM 3 only if its licence verifies permissive). The variant is a build flag
(`LOOM2_VARIANT`) that filters the roster, the model pickers and the fetch catalogue; CI produces both installers.
LoRAs are roster entries of `kind: lora` from day one (D25) even though LoRA loading ships post-MVP.

## 2. Runtime policy on the RX 9070 XT (Windows)

| Topic | Policy | Evidence |
| --- | --- | --- |
| PyTorch (D16) | **torch 2.13.0+rocm10.0.0** (+ torchvision 0.28.0, torchaudio 2.11.0.2) from the **ROCm 10.0.0 stable** index `stable.repo.amd.com/rocm/whl-next/` with the `[device-all]` extras; fallbacks 2.12.0 / 2.11.0 on the same index. Nightly (`nightly.repo.amd.com`) only in throwaway venvs for spikes | ROCm 10.0.0 release notes (2026-08-26): Windows = PyTorch 2.13.0; ComfyUI v0.38.2 README documents this exact command; driver ≥ Adrenalin 26.8.1 (installed: 26.9.2) |
| Python / env (D16) | **Python 3.13** installed and pinned by **uv**; two venvs (`orchestrator/.venv` torch-free, `engine/.venv` GPU); `uv.lock` per component; a **constraints file** pins torch so ComfyUI's unpinned `torch` can never resolve to a CPU build from PyPI; the Adrenalin **AI Bundle** (global Python 3.12.0 + AMD-managed PyTorch) is not used | ComfyUI README: 3.13 "very well supported", 3.12 fallback, 3.14 may break custom nodes; cp313 wheels on the AMD index and for triton-windows |
| Attention | **SDPA** default (`--use-pytorch-cross-attention`); on ROCm the flash SDPA backend is **AOTriton, shipped inside the torch wheel** — loom measured it as the fastest backend. **No FlashAttention build is carried over** (no official Windows ROCm wheels; the only gfx1201 Windows wheel is an experimental D=128 backward-only build against a torch 2.15 nightly). Rebuild upstream flash-attention (RDNA3/4 support since 2026-03) against torch 2.13 only if a profile shows attention-bound slowness. SageAttention only as an experimental toggle (memory faults reported on Navi48) | AMD CK/FA study; mjun0812 prebuilds (ROCm = Linux only); loom p2-imp |
| Triton | `triton-windows==3.8.0.post29` (PyPI, cp313) paired with torch 2.13 for `torch.compile` and nodes that need it; optional | triton-windows compatibility table (torch 2.10+ ↔ triton 3.6+); AMD's gfx120X index has Linux-only triton |
| MIOpen | **Keep ComfyUI's AMD default: MIOpen off** (E7, 2026-10-05). On ROCm 10 / torch 2.13 the FLUX.2 VAE decode costs 0.9 s at 960×544 and 5.6 s at 1920×1088 with MIOpen off; enabling it costs 12–16 s of kernel search per new resolution per session and wins only ≈ 0.7 s per warm Draft decode (tuned 0.25 s). loom's `MIOPEN_FIND_MODE=2` is no longer needed. Optional later: MIOpen on + per-tier warm-up decode if the find-db persists on Windows | Comfy #15674; loom p2-imp M0e; E7 journal |
| Weight formats | prefer **fp8 scaled** (fast on gfx1201) and **GGUF** (safe, slower); **avoid INT8 convrot for UNets** (NaN/black on gfx1201 as of Jul 2026); no NVFP4 / Nunchaku (CUDA) | Comfy #15084; model_management.py |
| Memory flags | `--disable-pinned-memory`, tiled VAE decode by default, `--disable-dynamic-vram` available; text encoders offload to CPU after encoding (128 GB RAM makes this cheap) | AMD Windows ComfyUI guide; 7900 XTX LTX stall reports |
| Stability | one engine job at a time; process-restart-per-N-jobs option (HIP "unspecified launch failure" after repeated runs was reported on 9070 XT) | TheRock #2846 |
| Timing | `torch.cuda.synchronize()` at every boundary; every benchmark records model, format, resolution, steps, wall time, peak VRAM | loom lesson 3 |
| Fallback engine | stable-diffusion.cpp **Vulkan** (FLUX.2 dev/Klein, Qwen-Image, Z-Image, Wan, inpaint, GGUF) as a zero-driver fallback; not MVP | sd.cpp releases Jan–Sep 2026 |

Measured on this rig (E0, 2026-10-04, ComfyUI 0.38.2 on the D16 stack): **FLUX.2 dev fp8mixed 20 steps 960×544
= 62 s warm / 107 s cold (2.7–2.8 s/it); dev + Turbo LoRA 8 steps = 39 s fresh, 42–68 s under sustained load
(Q15); dev GGUF Q4_K_M = 676 s (31 s/it); loom's old worker on the same files = 649 s.** Still extrapolated:
Klein 4B fp8 1024² 4 steps ≈ 3–6 s; Klein 9B fp8 ≈ 6–12 s; Wan 2.2 A14B Q5 + Lightning 480p 5 s clip ≈ 4–8 min;
MiniMax H3 ≈ 13–14 min (third-party 9070 XT measurement).

## 3. Target a — FLUX.2 text-to-image with JSON prompting

### 3a. FLUX.2 family (status 2026-10)

| Variant | Params | Text encoder | License | Steps / CFG | 16 GB fit |
| --- | --- | --- | --- | --- | --- |
| **Klein 4B** (distilled) | 4B | Qwen3-4B (layers 9/18/27) | **Apache-2.0**, ungated | exactly 4 / 1.0 | fp8 ≈ 4 GB + TE 4–8 GB → ~8.4 GB peak |
| Klein 4B **base** | 4B | Qwen3-4B | Apache-2.0 | ~50 / real CFG (negatives work) | ~9.2 GB peak; fine-tunable |
| **Klein 9B** (distilled) | 9B | Qwen3-8B | FLUX NC, gated | 4 / 1.0 | fp8 ≈ 9–10 GB, TE `qwen_3_8b_fp8mixed` 8.7 GB → ~15 GB peak with TE unload |
| Klein 9B **base** | 9B | Qwen3-8B | NC | 50 / CFG | as above |
| Klein 9B-**KV** (Mar 2026) | 9B | Qwen3-8B | NC | 4 | KV-cache of reference tokens, up to 2.5× faster multi-ref editing |
| **dev** | 32B | Mistral-Small-3.2-24B (layers 10/20/30) | NC, gated | 28–50 BFL / 20 Comfy / ~8 with Turbo LoRA; g ≈ 4 | fp8mixed 35.5 GB or GGUF Q4_K_S 19.3 / Q4_K_M 20.1 GB → always streamed/offloaded; Mistral TE Q4_K_M 14.3 GB on CPU |
| pro / flex / max | — | — | API only | — | — |

No open FLUX.2 variant has a mask channel; no open Fill/Kontext/turbo FLUX.2 checkpoint exists (BFL's Erase /
Outpaint / Deblur and FLUX.3 are API-only). All open variants unify t2i and multi-reference editing (dev up to
10 refs).

### 3b. Tiering decision D6, ordered by D21 ("the complex first")

- **Default and first-built: FLUX.2 dev** — **Comfy-Org `flux2_dev_fp8mixed` + `mistral_3_small_flux2_fp8`** is
  the default format (E0, 2026-10-04: 20 steps at 960×544 in **62 s warm / 107 s cold**, ≈ 2.8 s/step, streamed
  by ComfyUI's DynamicVRAM); the unsloth GGUF Q4_K_M transformer measured **≈ 11× slower per step** (31 s/it, 676 s per image)
  through ComfyUI-GGUF on this stack with visually equivalent output, so it is kept only as a disk/VRAM-saving
  option. Turbo LoRA optional for 8-step runs. The only variant whose 24B Mistral encoder parses **BFL JSON** reliably, and the
  model the author named as producing the most accurate starting images. On this rig it is minutes per image at
  the Draft tier (960×544), so Generate is built around **staged / overnight batches, resident weights across a
  batch, and live previews** rather than instant feedback. Labelled "dev · JSON · slow" in the UI.
- **Later: Klein 9B / 9B-base / 9B-KV** fp8 + `qwen_3_8b_fp8mixed` (quality prototyping, seconds per image) and
  **Klein 4B / 4B-base** (Apache-clean, the `open` variant's default). They join the Generate picker once their
  graphs exist for Edit (M5) and may slip past MVP; the same prompt tree is **flattened to prose** for them.
- **Klein is still first in the Edit suite**: interactive inpaint (D7) runs on Klein 4B/9B because a fill must
  return in seconds; dev is offered there as the slow "Fill Hero" mode.

Guidance from loom (02 §5) is inverted for the MVP on purpose: dev for the real boards first, Klein for sweeps
later. Upscale/refine after dev stays the route to FHD (§9c).

### 3c. JSON prompting (BFL guide)

Official schema (fields verbatim from docs.bfl.ai/guides/prompting_guide_flux2):

```json
{
  "scene": "overall scene description",
  "subjects": [{"description": "...", "position": "where in frame", "action": "...", "pose": "...", "color_match": "exact"}],
  "style": "artistic style",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "lighting": "lighting description",
  "mood": "emotional tone",
  "background": "background details",
  "composition": "framing and layout",
  "camera": {"angle": "...", "lens": "...", "depth_of_field": "...", "f-number": "...", "distance": "..."}
}
```

Rules: hex colours must be bound to objects; literal text in quotes inside subject descriptions; 30–80 words
ideal; order matters (subject + action + style + context); **no negative prompts**; nesting beyond two
levels degrades; the JSON is simply the user string. For dev, ComfyUI's tokenizer wraps it as
`[SYSTEM_PROMPT]You are an AI that reasons about image descriptions…[/SYSTEM_PROMPT][INST]{prompt}[/INST]`
(BFL's own system message). Klein uses the Qwen3 chat template and, per community testing, rewards layered
prose over JSON and ignores negatives on distilled variants → loom2 **flattens the same tree to prose for
Klein** and sends raw JSON for dev. An optional "upsample" pass (BFL's `SYSTEM_MESSAGE_UPSAMPLING_T2I/I2I`
through Mistral or Qwen3) can expand a short prompt before encoding; it is a separate queued LLM job.

The loom v2 tree (scene · subjects[] · camera · lighting · style · mood · color_palette) is a subset of the
BFL schema; loom2 adopts the full BFL field set plus loom's pose/angle directive vocabulary as pickers.

## 4. Target b — inpainting, editing and refinement

| Model | Type | Footprint on 16 GB | License | Verdict |
| --- | --- | --- | --- | --- |
| **FLUX.2 Klein 4B / 9B** | unified gen + reference edit; masked fill at the sampler level (`InpaintModelConditioning` + `ReferenceLatent` + differential diffusion + crop-and-stitch) | shares the t2i weights | Apache (4B) / NC (9B) | **Primary (E8 2026-10-05).** 18–33 s per 960×544 fill incl. model swap; seamless, colour-matched, identity kept; the ICM graph is conservative — continues texture well, keeps objects the prompt says to remove |
| **LanPaint 2.2** (Sep 2026) | sampler-level masked inpaint/outpaint for any model incl. Klein, Qwen-Image 2.1, Wan; alpha-channel inpainting | no weights, extra "thinking" steps | node licence to check | **Default fill sampler on Klein (E8).** 22–28 s, best prompt adherence of the fast methods (cloak → red leather, lit doorway), identity kept; also the only way dev works as a fill |
| **FLUX.1 Fill dev** | true mask-conditioned fill + outpaint | official bf16 file 22.2 GB cast to fp8 at load + T5 fp8 4.9 GB + CLIP-L; guidance 30, 20 steps in E8 | FLUX NC, gated | **Dropped by E8 (2026-10-05).** 76–82 s and the weakest on 3 of 4 tasks: muddy cloak, smeared outpaint strip, *added* crates, and the only method that changed the face. File kept on disk, not in the MVP roster |
| **Qwen-Image-Edit-2511** (Dec 2025) | instruction edit, multi-image | GGUF Q4_K_M 13.2 GB + Qwen2.5-VL-7B fp8 offloaded; 4–8 steps with Lightning LoRA | **Apache-2.0** | **Deferred post-MVP (E8).** 2509 fp8 + Lightning + LanPaint kept identity and made decent semantic edits, but softer than Klein, no removal, and 19.5 GB does not fit 16 GB: 475 s per job cold (4 min 55 s model init from D:), ≈ 95 s warm. 2511 GGUF Q4 only if a use case appears that Klein + LanPaint cannot do |
| Qwen-Image-2.1 (Sep 2026) | unified gen + edit, native RGBA, mask/annotation local edits | GGUF Q4 ≈ 5 GB + Qwen3-VL-8B int8 9.4 GB | Qwen Research (non-commercial) | watch; strong transparent-layer inpainting with LanPaint |
| FLUX.1 Kontext dev | instruction edit, no mask | Q8 ≈ 12.7 GB | NC | superseded by Qwen-Image-Edit for loom2's needs |
| FLUX.2 dev | edit with up to 10 refs; masked fill via LanPaint | fp8mixed + Turbo LoRA, 8 LanPaint steps | NC | **Fill Hero (E8):** 255–281 s at 960×544, best material detail, and the only method that actually removed the crates |
| SDXL inpaint / ControlNet Union, BrushNet, PowerPaint | legacy mask-conditioned | tiny | permissive | lightweight fallback only |
| HiDream-E1.1, OmniGen2 | instruction edit | heavy / mediocre | MIT / Apache | no |

**Decision D7 (inpaint stack) — accepted with amendments 2026-10-05 after E8 (journal 11:50):** Klein 9B
(same weights as Generate) with **LanPaint as the default fill sampler** and the `InpaintModelConditioning` /
`ReferenceLatent` graph as the conservative "match surroundings" mode, both with crop-and-stitch at the
document's native resolution; **FLUX.2 dev + LanPaint as Fill Hero** (slow, best detail, the only method that
removed an object). FLUX.1 Fill is dropped (second-slowest and weakest on 3 of 4 bench tasks), Qwen-Image-Edit
is deferred post-MVP (does not fit 16 GB, softer, no removal), and Klein base brought nothing to inpaint (wrong
cloak colour, 46–155 s) and stays on the refine path only. The editor's "AI inpaint" verb exposes **Fill
(Klein + LanPaint) · Fill-Match (Klein ICM) · Fill Hero (dev + LanPaint)** with the same selection → mask →
new-layer contract; "Edit by instruction" waits for a model that beats Klein on this bench. Candidate defaults
(D22): **4 on Klein, 2 on dev**. In the `open` variant Fill Hero is absent and Fill runs on Klein 4B
(unmeasured). **Q17 resolved by E8b (2026-10-05):** Klein removes objects once the reference stops showing
them — ICM with the hole neutralised to mid grey in the reference image (`klein_icm_hole`, 10 s warm) and
LanPaint in "Prompt First" mode (λ 8, 21 s) both cleared the crates that every reference-fed graph had kept;
dropping the reference entirely also clears them but drifts further from the scene. The editor's **Remove**
verb therefore runs the hole recipe with a background-only prompt (the bench prompt's "steaming vent" duly
produced a vent in every variant), and Fill Hero stays the quality option for removal.

**Masks:** SAM 3 (`sam3.pt` on disk) for click/box/text-prompt segmentation, BiRefNet / BiRefNet_HR (MIT) for
subject matting, YOLOv8 face/hand/person/skin/hair detectors for one-click region masks.

**Refine / upscale:** distilled Klein cannot do partial-denoise img2img (every edit starts from noise with the
source as reference) → low-denoise refinement uses **Klein base or dev** (0.2–0.35 enhance, 0.4–0.6 restyle)
with loom's corrected `[strength, 0]` schedule semantics, or distilled Klein with an "enhance detail, keep
composition" instruction. Tiled refine (Ultimate-SD-Upscale pattern) with Klein for creative upscales;
**SeedVR2 3B fp8** (Apache, one-step, in ComfyUI core since Jul 2026, ROCm fixes in the numz pack) as the
"add real detail" upscaler; ESRGAN for cheap 2×. SeedVR2 is post-MVP unless the spike shows it is trivial.

## 5. Target c — image-to-video

### 5a. Candidates (open weights, status 2026-10)

| Model | Params / TE | Native | End frame | Identity evidence | 16 GB fit | License |
| --- | --- | --- | --- | --- | --- | --- |
| **Wan 2.2 I2V-A14B** (Jul 2025) | MoE 2×14B (14B active), umT5-XXL | 480p/720p, 16 fps, 81 f | **yes, same weights** via `WanFirstLastFrameToVideo`; `Wan2.2-Fun-A14B-InP` if morphing | **FaceSim 0.578 vs 0.379 (5B)** (arXiv 2510.14255); best photoreal faces in community tests | GGUF Q5_K_M 10.8 GB / Q6_K 12 GB per expert + umT5 fp8 offloaded; Lightning 4-step LoRAs | Apache-2.0 |
| Wan 2.2 TI2V-5B | 5B dense | 720p 24 fps | community node only | FaceSim 0.379 | fp8 8–10 GB | Apache-2.0; RDNA4 colour corruption reported on ROCm 7.2.1 |
| **LTX-2.3** (Mar 2026) | 22B, Gemma-3-12B | up to 4K, 24/48 fps, 121 f | **keyframes at arbitrary indices** (`LTXVAddGuide`, per-guide strength), FLF template | softer faces than Wan; fastest open model; IC-LoRA pose/depth/canny control | GGUF Q4_K_M 13–16.5 GB + Gemma Q4 ≈ 8 GB offloaded; distilled 8 steps | LTX Community (< $10M ARR) |
| LTX-2.5 (Aug 2026) | 22B, Gemma-4-12B | 1920×1088, 121 f, multishot, HDR | yes | AA Elo 1038 (Fast) | official ≥ 34 GB; community GGUF Q4 15.7 GB + Gemma-4 Q4 8.4 GB; no 16 GB numbers yet | LTX Community |
| **MiniMax H3** (Aug 2026) | 33B (~20B loaded), Qwen3-VL-32B | 768p, 24 fps, 4–15 s | **native first + last frame** (FL2VA), ≤ 9 refs (Ref2VA) | top open-weights Elo 1181; **measured on a 9070 XT Windows: 864×480, 5 s, 20 steps = 13 m 39 s**, faces close to source | GGUF Q4_0 11.4 GB, spills to RAM (64 GB recommended) | Community licence with **application required for USA/EU/UK/KR users** |
| HunyuanVideo 1.5 (Nov 2025) | 8.3B | 480p/720p, 24 fps, 121 f | **no** | best motion naturalness; step-distilled 8–12 steps | fp8 / GGUF Q4 7–11 GB | Tencent community (territorial terms) |
| Kandinsky 5.0 Lite/Pro | 2B / 19B | 768×512, 24 fps | no | — | easy (Lite) | MIT |
| SkyReels V3 R2V | 14B (Wan-derived) | 720p 24 fps | no FLF | reference-to-video with 1–4 refs | 24 GB recommended; fp8 + offload | Skywork licence |
| Wan 2.5 / 2.6 / 2.7 / 3.0 | — | — | — | — | **API-only**; "open weights" claims verified false | — |
| Wan2.2-Animate-14B / Animate-2 (Aug 2026), SCAIL-2, One-to-All, UniAnimate-DiT | reference image + driving video / pose | — | n/a | dedicated character animation; Animate Q8 ran on a 16 GB card (5 s ≈ 7 min) | GGUF | Apache |

### 5b. Decisions D8 / D9

- **Primary (start image + prompt, and start + end image): Wan 2.2 I2V-A14B**, GGUF Q5_K_M (or Q6_K) high +
  low experts, umT5 fp8 offloaded to CPU, Wan 2.1 VAE, **Lightning 4-step LoRAs** (high expert 0.6–0.8
  strength, low 1.0, 4 + 4 steps, CFG ≈ 2.5 on high to keep motion), 480p–576p, 81 frames @ 16 fps. End frame
  via `WanFirstLastFrameToVideo` on the same weights. Reasons: the only quantitative identity evidence
  favours it; zero extra weights for FLF; Apache; the largest LoRA/control ecosystem (VACE, Fun-InP, Animate,
  Stand-In) covers every later loom2 feature. **E4 2026-10-05 — D8 accepted:** 5 of 5 bench clips at
  832×480 × 81 f with Lightning 2 + 2 steps (high 0.7 / low 1.0, CFG 1, shift 5), **312–366 s per clip**, of
  which the Wan VAE decode is 131–134 s and the start-image encode 36–40 s (Q18) against 104–130 s of
  sampling; identity held in every clip including the tight close-up, FLF reached the end pose. Weak spots:
  camera moves (the push-in barely moves) and the turn-to-camera (she looks down at the compass instead) —
  E4b tries 4 + 4 steps with CFG 2.5 on the high expert for motion before M6 fixes the presets.
- **Secondary engine: LTX-2.3 distilled** GGUF Q4_K_M + Gemma-3-12B Q4, `LTXVAddGuide` at frame 0 / −1 (+
  optional middle beats), 8 steps, 24 fps. Reasons: fastest open model (interactive previews on AMD),
  arbitrary keyframe conditioning maps directly onto "boards → beats", IC-LoRA pose/depth for driven motion,
  LTX-2.5 upgrade path.
- **"Hero clip" tier: MiniMax H3 FL2VA** (proven on this exact GPU/OS; native first+last; highest quality;
  ≈ 3× slower). **Enabled (D17)**: the author is EU-located, eligible and willing to complete the community-licence
  application; the tier unlocks in Settings once the application is confirmed filed.
- **Not selected for MVP:** HunyuanVideo 1.5 (no end frame), Wan 2.2 5B (identity, RDNA4 colour bug),
  Kandinsky/SkyReels/CogVideoX (stale or no FLF), MAGI-2 (307 GB).
- **Post-MVP character animation:** Wan2.2-Animate-14B GGUF (pose/driving video → character), watching
  Animate-2 distilled and SCAIL-2 for ComfyUI/GGUF support.

Community AIO merges already on disk (`wan2.2-i2v-rapid-aio-*`) are **not** roster candidates (merged
provenance); they may serve the first smoke test only.

### 5c. End-frame behaviour to expect

Wan 2.2 FLF gives the most identity-faithful boundary frames but can morph through the middle of long gaps
(keep ≤ 81 frames; escalate to Fun-InP). LTX keyframes give more direction control (mid-frames, per-beat
strength) but "more conservative interpolations" when the two boards differ a lot. H3 has native FL
conditioning with the best quality at ~3× the cost. The Animate suite exposes these as **Wan (faithful) ·
LTX (fast, beats) · H3 (hero)** with the same start/end/prompt contract.

## 6. Evaluation protocol (binding for every "done")

A fixed benchmark set lives in `.docs/proto01/bench/` (to be created in M0):

- **T2I**: 10 storyboard prompts as BFL JSON (characters, interiors, exteriors, action, typography). Score
  adherence per field (subject, pose, camera, lighting, palette), detail, artefacts; record wall time, peak
  VRAM, model/format/steps. Run on Klein 4B, Klein 9B, dev Q4.
- **Inpaint**: 5 tasks (object removal on texture, clothing change, background swap, outpaint 25 %, face
  region fix). Score seam visibility, colour match, identity preservation, time. Run Klein+ICM, Klein+LanPaint,
  FLUX.1 Fill, Qwen-Edit. **Run 2026-10-05 (E8 run 3)** on the frozen `bench/inpaint/source.png`: tasks
  01/02/04/05 × 6 methods, scored on side-by-side sheets from `engine/spikes/e8_sheets.py`; task 03 (BiRefNet
  matte) waits for the AI Select path in M5.
- **I2V**: 5 tasks (character turn, walk cycle, two-board FLF with pose change, camera push, dialogue gesture).
  Score face/clothing identity (ArcFace FaceSim within the clip, advisory), motion plausibility, end-frame
  reach, time. Run Wan 2.2 Q5 + Lightning, LTX-2.3 distilled, optionally H3.

Results are appended to the implementation journal with `torch.cuda.synchronize()`-bracketed timings.

## 7. Licence summary (roster `license` field)

| Licence | Entries | Use in loom2 |
| --- | --- | --- |
| Apache-2.0 / MIT | Klein 4B (+base), FLUX.2 VAE, Wan 2.2 family, Qwen-Image-Edit-2511, SeedVR2, BiRefNet, LanPaint weights-free | unrestricted; the "Apache-clean" tier |
| FLUX Non-Commercial | FLUX.2 dev, Klein 9B family, FLUX.1 Fill | personal use OK; flagged |
| LTX Community (< $10M ARR) | LTX-2.3 / 2.5 | OK; flagged |
| Tencent / Skywork community | HunyuanVideo 1.5, SkyReels V3 | not selected |
| Qwen Research (NC) | Qwen-Image-2.1 | watch |
| MiniMax H3 Community (territorial application) | H3 | **enabled after the author's EU application is filed** (D17); Settings toggle records the confirmation |

Licensing is read **EU-first** (D17): every roster entry's `license` is checked against its EU terms; US-only
or other-territory clauses are noted but not optimised for.
| SAM 3 | `sam3.pt` | check Meta's licence terms before shipping (open question Q9) |

## 8. Re-check list (volatile facts)

Windows ROCm nightlies (AOTriton kernels, fp8 regressions in 7.14.1, dynamic VRAM), INT8 convrot fix on
gfx1201, any open FLUX.2 "fill" release, Qwen-Image-2.1 licence changes, sd.cpp Klein-VAE / 9B-KV fixes,
LTX-2.5 GGUF maturity on 16 GB, Wan-Animate-2 ComfyUI support, ComfyUI version pin for the engine (06).

## 9. Resolution, frame-count and fps constraints → project format tiers (D18)

### 9a. Hard constraints per model

| Model | Spatial rule | Native / trained sizes | Frames | fps | Notes |
| --- | --- | --- | --- | --- | --- |
| FLUX.2 Klein 4B / 9B | W, H multiples of **16**; 64 px – 4 MP | any aspect; community: quality drops when the short side < ~768 px on Klein | — | — | exactly 4 steps (distilled); tokens = W/16 × H/16 |
| FLUX.2 dev | multiples of 16; up to 4 MP | any; loom ran 512²–1024² on this rig | — | — | every extra token costs on a streamed 32B model; 1024² hero ref alone = 4 096 tokens |
| Wan 2.2 I2V-A14B | multiples of **16** | **480p (832×480)** and **720p (1280×720)** trained; 576p (1024×576) works | **4n+1**, 81 default (≈ 5 s) | **16** | 720p on 16 GB at Q5 is tight and slow; no native 1080p |
| LTX-2.3 | multiples of **32** | 768×512 · 1024×576 · 1280×704 (720 is not ×32) · up to 4K via **two-stage: base at half size + 2× spatial upscaler** | **8n+1**, 121 default (5 s) | 24 (48 optional) | the upscaler stage is the designed route to FHD |
| MiniMax H3 | per its VAE (16×) | 768p default; **864×480** measured on this rig | 4–15 s | 24 | ≈ 13 min per 5 s here |
| 1080 rows | — | **1080 is neither ×16 nor ×32** | — | — | generate **1920×1088** and crop 4 px top and bottom; the asset is stored cropped, the manifest records the generation size |

### 9b. Image cost model (FLUX.2 latent tokens = W/16 × H/16; attention ≈ quadratic)

| Preset (16:9) | Size | Tokens | Relative attention cost | Klein 9B fp8 (extrapolated; measure in M0) |
| --- | --- | --- | --- | --- |
| Thumb | 896×512 | 1 792 | 0.25× | ~3–5 s |
| **Draft (default)** | 1280×720 | 3 600 | 1× | ~6–12 s |
| Square 1 MP | 1024×1024 | 4 096 | 1.3× | ~7–14 s |
| Full (FHD) | 1920×1088 → crop 1080 | 8 160 | 5× | ~20–45 s |
| dev Draft | 960×544 | 2 040 | — | minutes (streamed weights) |

### 9c. The tiers loom2 exposes (bound to the project aspect, 16:9 by default)

| Tier | Images | Video | Intended use |
| --- | --- | --- | --- |
| Thumb | 896×512 | — | composition sweeps, 8–16 variants |
| **Draft** (default) | **1280×720** Klein · 960×544 dev | **Wan 832×480 @16 fps 81 f** · **LTX 1024×576 @24 fps 121 f** · H3 864×480 | the daily loop |
| HD | 1280×720 (same as Draft for images) | Wan 1280×720 (slow, Q5) · LTX 1280×704 | selective |
| **Full (FHD)** | Klein 1920×1088 → crop · dev: Draft + tiled refine/SeedVR2 | LTX two-stage → 1920×1088 → crop · Wan/H3: + frame upscale (SeedVR2, post-MVP) | hero frames and final boards |

Project record: `format.target = {aspect: 16:9, width: 1920, height: 1080, fps: 24}` (export/finalize
reference, fixed at creation per loom R45) and `format.default_tier = "draft"`. Clip masters keep their native
fps (Wan 16, LTX/H3 24); conforming to 24 fps is an export step (Q14, post-MVP). All size pickers snap to the
selected model's multiple and show the token count and the time estimate.

## Sources

BFL: bfl.ai/blog/flux-2 · bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence ·
docs.bfl.ai/guides/prompting_guide_flux2 · github.com/black-forest-labs/flux2 (system_messages.py,
flux2_klein_kv_cache.md) · HF cards FLUX.2-dev / klein-4B / klein-9B / klein-9b-kv
Quantisers: huggingface.co/Comfy-Org (flux2-dev, flux2-klein-4B, flux2-klein-9B) · unsloth collection
"unsloth-diffusion-ggufs" · city96/FLUX.2-dev-gguf · QuantStack (Wan2.2-I2V-A14B-GGUF, LTX-2-GGUF) ·
unsloth/LTX-2.3-GGUF · github.com/nunchaku-tech/nunchaku · github.com/BoomerCyb/Nunchaku-AMD
ComfyUI: comfy/model_detection.py · comfy/model_management.py · comfy/text_encoders/flux.py ·
extra_model_paths.yaml.example · docs.comfy.org/tutorials/flux/flux-2-klein · docs.comfy.org/tutorials/video/wan/wan2_2 ·
comfy_extras/nodes_wan.py · blog.comfy.org/p/official-amd-rocm-support-arrives · issues #15084 #15674 #13730
ROCm: rocm.docs.amd.com (7.2 limitations, Windows ComfyUI guide, 7.12 preview PyTorch) · ROCm/TheRock
RELEASES.md, #2846, #7861 · rocm.blogs.amd.com (comfyui-radeon-9000, comfyui-fa-backends) ·
github.com/patientx-cfz/comfyui-rocm · github.com/guinmoon/rocm7-triton-flash-attention-sage-attention-bnb
Inpaint: HF FLUX.1-Fill-dev · HF Qwen/Qwen-Image-Edit-2511 · github.com/QwenLM/Qwen-Image-2.1 ·
github.com/scraed/LanPaint · comfyui-wiki.com/en/news/2026-09-28-lanpaint-2-2-qwen-image-2-1 ·
Comfy PR #14424 (SeedVR2) · github.com/numz/ComfyUI-SeedVR2_VideoUpscaler
Video: github.com/Wan-Video/Wan2.2 · HF Lightricks/LTX-2, LTX-2.3, LTX-2.5 · github.com/Lightricks/LTX-2 ·
HF MiniMaxAI/MiniMax-H3 · github.com/Tencent-Hunyuan/HunyuanVideo-1.5 · arxiv.org/html/2510.14255v1 ·
HF lightx2v/Wan2.2-Lightning · artificialanalysis.ai/video/leaderboard/image-to-video/open-weights ·
HF Wan-AI/Wan2.2-Animate-2-14B · github.com/zai-org/SCAIL · github.com/kijai/ComfyUI-WanVideoWrapper ·
github.com/deepbeepmeep/Wan2GP · note.com/taka_friday549 (9070 XT H3 run)
sd.cpp: github.com/leejet/stable-diffusion.cpp (#1216, #1341)
