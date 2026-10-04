# 01 · Target rig and existing assets (inventory, 2026-10-04)

Everything in loom2 is bounded by this machine. This file records what was verified on
2026-10-04 so later design decisions can cite it instead of re-discovering it.

## 1. Hardware

| Item | Value | Consequence for loom2 |
| --- | --- | --- |
| GPU | AMD Radeon RX 9070 XT (RDNA4, gfx1201), **16 GB** VRAM, **Adrenalin 26.9.2** (driver store 32.0.32015.2008, 2026-09-28; ≥ 26.8.1 required by ROCm 10.0) | No CUDA-only kernels (SageAttention, Nunchaku SVDQuant, xformers CUDA paths). Every model must fit 16 GB with quantisation + offload. |
| CPU | AMD Ryzen 9 9950X, 16 cores | Fast CPU offload / GGUF dequant; CPU-side image ops (ONNX, OpenCV) are cheap. |
| RAM | 128 GB | Huge headroom for CPU-resident text encoders and block-swap. The 24B Mistral TE for FLUX.2-dev can live in RAM. |
| Disks | C: 832 GB free · D: 125 GB free (ComfyUI) · E: 291 GB free · F: 365 GB free (`F:\HF_HOME`, projects) | Weight cache stays on F:. Disk guard (loom R96) still matters. |
| OS | Windows 11 Pro 10.0.26300 | ROCm-on-Windows only; no WSL dependency wanted. |

## 2. Software stacks

### 2a. loom's stack (reference only — proves ROCm works on this GPU; **not** loom2's target)

Shared venv: `F:\source\repos\stubz-002-tripo-sf\.venv` (Python 3.12.10). Follows the older "PyTorch on
Windows 7.2.1" path (separate `rocm_sdk_*` wheels from repo.radeon.com, Python 3.12 only). Left untouched for
loom; used by loom2 only as an A/B reference during spike E0.

| Package | Version | Note |
| --- | --- | --- |
| torch / torchvision / torchaudio | **2.9.1+rocm7.2.1** | Official ROCm-on-Windows wheels; `torch.cuda.is_available()` is True and reports the 9070 XT. |
| flash_attn | 2.8.4 (built locally from upstream `Dao-AILab/flash-attention` @ 5301a35, 2026-03-27, RDNA3/4 CK support) | Proves FA2 builds on RDNA4 Windows. **Not carried into loom2** (D16): SDPA/AOTriton is the default; the upstream recipe is noted only in case profiling demands a rebuild against torch 2.13. |
| triton-windows | 3.6.0.post26 | Triton on Windows is present; kernel coverage on ROCm is still partial. |
| diffusers | 0.39.0.dev0 | Has `Flux2Transformer2DModel`, single-file BFL converter, GGUF quantiser (`quantizers/gguf/utils.py`). |
| transformers | 5.4.0 | |
| optimum-quanto | 0.2.7 | qfloat8 used by the loom LoRA trainer. |
| onnxruntime | 1.24.4 | CPU provider; used for GFPGAN / inswapper in loom. |
| opencv-python, pillow, imageio(-ffmpeg), decord | current | No system `ffmpeg` on PATH — only the imageio-ffmpeg binary. loom2 should ship/pin its own ffmpeg. |
| fastapi / uvicorn | 0.136 / 0.49 | |

### 2b. loom2 target stack (decision D16, accepted 2026-10-04)

| Component | Target | Why |
| --- | --- | --- |
| ROCm channel | **ROCm 10.0.0 stable** via `https://stable.repo.amd.com/rocm/whl-next/` (released 2026-08-26) | the current official Windows path; ROCm libraries arrive as pip extras (`torch[device-all]`), no separate SDK wheels |
| PyTorch | **torch 2.13.0+rocm10.0.0**, torchvision 0.28.0+rocm10.0.0, torchaudio 2.11.0.2+rocm10.0.0 | exactly the command ComfyUI v0.38.2 documents for AMD on Windows; wheels for cp311–cp314 |
| Python | **3.13** (installed and pinned by `uv`, not on PATH) | ComfyUI: "3.13 very well supported, 3.12 fallback, 3.14 may break custom nodes"; ROCm 10 and triton-windows ship cp313 |
| Environment manager | **uv** with a lockfile per component; interpreter path stored in loom2's config | reproducible re-creation; no global PATH/env changes; the 3.12 install stays for loom |
| Venvs | `orchestrator/.venv` (torch-free) and `engine/.venv` (ComfyUI + GPU tools) | API process stays light; GPU stack isolated |
| Attention | torch SDPA (AOTriton flash backend inside the wheel); **no FlashAttention build carried over**; SageAttention experimental toggle | no official Windows ROCm FA wheels exist; loom measured AOTriton SDPA fastest |
| Triton | `triton-windows==3.8.0.post29` (optional, for `torch.compile` / nodes that need it) | cp313 wheel on PyPI; AMD's own index has no Windows triton |
| Driver | Adrenalin, driver only; the **AI Bundle** (global Python 3.12.0 + AMD-chosen PyTorch) is **not used** | pinned, testable versions beat an auto-managed global environment |
| Fallbacks | torch 2.12.0 / 2.11.0 + rocm10.0.0 on the same index; loom's venv for A/B | |

Toolchains: Node 22.20, npm 10.9, Rust 1.96 (cargo), Python 3.12 system install (loom's; loom2 does not use it).
WebView2 runtime (Edge) **154.0.4258.53** — a current Chromium, so WebGL2 and WebGPU are available to a
Tauri 2 webview on this machine.

ComfyUI `0.19.3` (git 2026-04-19) at `D:\comfyui\ComfyUI` — **kept by the author only as a backup for its
model files**; the code is stale (upstream is v0.38.2 as of 2026-10-04) and loom2 uses its own pinned checkout
(06 §3b, D15). It still proves ROCm compatibility: it runs on the **same ROCm venv**
(`D:\comfyui\.venv`, torch 2.9.1+rocm7.2.1). Custom nodes present: ComfyUI-RMBG, comfyui-manager.
Saved workflows show FLUX.2-dev t2i (fp8mixed transformer + Mistral fp8 TE, `res_multistep` /
`sgm_uniform`, 20 steps, guidance 1) and FLUX.2 i2i with the Turbo LoRA already run on this rig.

## 3. Weights already on disk

### 3a. Hugging Face cache `F:\HF_HOME\hub` (≈632 GB total)

| Repo | Large files present | Relevance |
| --- | --- | --- |
| `Comfy-Org/flux2-dev` | `flux2_dev_fp8mixed.safetensors` 35.5 GB · Mistral TE bf16 35.6 GB / **fp8 18.0 GB** / fp4-mixed 12.3 GB · Turbo LoRA ×2 (2.8 GB) · `flux2-vae.safetensors` 0.34 GB | The ComfyUI-convention FLUX.2-dev distribution. Public, ungated. |
| `unsloth/FLUX.2-dev-GGUF` | `flux2-dev-Q4_K_M.gguf` 20.0 GB | Unsloth DOES publish FLUX.2 GGUFs — candidate single-source anchor. |
| `unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF` | `Q4_K_M` 14.3 GB | GGUF Mistral TE (the ComfyUI workflow references a `UD-Q8_K_XL` too). |
| `black-forest-labs/FLUX.2-klein-4B` | 7.75 GB transformer (+ Qwen3-4B TE 8 GB, VAE) | Fits 16 GB in bf16. Apache-2.0. |
| `black-forest-labs/FLUX.2-klein-9B`, `-9b-kv`, `-klein-base-9B` | 18.2 GB transformer each (+ Qwen3-8B TE 16.4 GB) | Needs FP8/GGUF to fit; base = undistilled (CFG, trainable). |
| `black-forest-labs/FLUX.2-dev` | only `ae.safetensors` 0.34 GB | Gated BFL repo; loom proved the Comfy VAE is byte-identical. |
| `black-forest-labs/FLUX.2-small-decoder` | 0.25 GB | Fast preview decoder. |
| `Qwen/Qwen3-4B`, `Qwen/Qwen3-8B` | TE for Klein | |
| `Tongyi-MAI/Z-Image`, `Z-Image-Turbo` | | loom P0 smoke model; Apache-2.0, fast. |
| `stabilityai/stable-diffusion-3.5-{large,large-turbo,medium}` | gated | loom casting pool; loom2 can drop. |
| `InstantX/SD3-Controlnet-Tile` | 1.2 GB | loom `Upscale ✨`; loom2 can drop with SD3.5. |
| `krea/Krea-2-Turbo` | 26 GB | fourth t2i generator in loom; drop. |
| `stabilityai/stable-video-diffusion-img2vid-xt` | 9.5 GB | Legacy i2v; superseded. |
| `ZhengPeng7/BiRefNet`, `BiRefNet_HR` | 0.9 GB each | Subject matting — still useful for mask generation in the inpaint suite (MIT). |
| `ezioruan/inswapper_128.onnx`, `facefusion/models-3.0.0` | | Identity swap / GFPGAN — research-only / mirror origin. **Drop** (questionable provenance). |

### 3b. ComfyUI `D:\comfyui\ComfyUI\models` (relevant entries)

| Folder | File | Size | Relevance |
| --- | --- | --- | --- |
| diffusion_models | `flux2_dev_fp8mixed.safetensors` | 35.5 GB | duplicate of HF cache copy |
| diffusion_models | `qwen_image_edit_2509_fp8_e4m3fn.safetensors` | 20.4 GB | **inpaint/edit candidate** already on disk |
| diffusion_models | `qwen_image_2512_fp8_e4m3fn.safetensors`, `qwen_image_fp8_e4m3fn.safetensors` | 20.4 GB each | Qwen-Image t2i |
| diffusion_models | `wan2.2-i2v-rapid-aio-v10-*.safetensors`, `wan2.2-t2v-rapid-aio-v10-*` | 23.4 / 21.3 GB | community all-in-one Wan 2.2 merges (fast but merged provenance) |
| diffusion_models | `flux1-dev.safetensors` | 23.8 GB | FLUX.1 dev |
| text_encoders | `mistral_3_small_flux2_bf16.safetensors` 35.6 GB · `qwen_2.5_vl_7b_fp8_scaled` 9.4 GB · `qwen_2.5_vl_fp16` 7.5 GB · `t5xxl_fp16` 9.8 GB · `t5xxl_fp8_e4m3fn_scaled` 5.2 GB · `clip_l` | | |
| text_encoders / unet | `flux2_nsfw/qwen3-4b-abl-q4_0.gguf` | 2.4 GB | GGUF Qwen3-4B TE (ablated community variant) |
| loras | `Flux_2-Turbo-LoRA_comfyui`, Qwen-Image(-Edit) Lightning 4/8-step, `Qwen-Edit-2509-Multiple-angles` | | **Qwen-Image-Edit Lightning LoRAs** make 4-step edits practical on 16 GB |
| vae | `flux2-vae`, `qwen_image_vae`, `flux1/ae` | 0.3 GB each | |
| sam3 | `sam3.pt` | 3.5 GB | **SAM 3** — AI segmentation for masks |
| ultralytics | face/hand/person/skin/hair YOLOv8 bbox+seg | small | auto-mask helpers (Impact-pack style) |
| checkpoints | `hunyuan_3d_v2.1` + assorted community SDXL/Flux merges | | not needed by loom2 |

Also cloned in the monorepo: `Wan2.2` (official repo, 2026-03-17), `Wan2.2-Animate-14B`
(checkpoint processing only, no weights), BFL `flux2` (with local patches: tqdm progress,
unsloth processor path fix, Comfy-VAE key remap, quantised-dev loader guard).

## 4. What this inventory implies

1. **ROCm on Windows works today** for this GPU (loom's 7.2.1 venv proves it), and ROCm 10.0 now ships current torch wheels for Python 3.11–3.14 through pip. loom2 builds its own pinned ROCm 10 / torch 2.13 / Python 3.13 environment (§2b) and never depends on CUDA-only kernels.
2. **FLUX.2-dev is already runnable here** in two forms: Comfy-Org FP8 split files (proven in loom and in ComfyUI on this rig) and Unsloth GGUF Q4_K_M. Klein 4B/9B are also cached.
3. **Qwen-Image-Edit-2509 FP8 + Lightning LoRA and SAM 3 are already on disk** — a near-zero-download starting point for the inpaint suite's evaluation.
4. **Wan 2.2 weights are only present as community AIO merges**; the official I2V-A14B (or GGUF) still needs downloading for a clean evaluation.
5. A single `models/` convention shared with ComfyUI would let loom2 reuse ≈150 GB already on D: without copying.
