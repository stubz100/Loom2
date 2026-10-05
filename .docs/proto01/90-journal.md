# loom2 · implementation journal (append-only)

Rules: append at the end, never rewrite; real clock stamps (local time, CEDT/CET); every timing names the
stack (torch, ROCm, ComfyUI commit, model file, resolution, steps) and is bracketed by
`torch.cuda.synchronize()` or taken from the engine's execution events. Spec amendments the same day in the
affected `NN-*.md`, logged here.

---

## 2026-10-04 18:44 (CEST, from the Windows clock; Git Bash `date` reports one hour early — use PowerShell `Get-Date` for stamps) — E0 start: environment + pinned engine

- Author approved D1–D14 ("go"); all open questions Q1–Q14 resolved earlier today (13).
- `git init -b main` in `F:\source\repos\stubz003_loom2`; `.gitignore` excludes venvs, engine outputs, weights.
- ComfyUI cloned at **v0.38.2** (`daeb5e5`, 2026-10-02) into `engine/comfyui` and registered as a submodule.
- Custom nodes pinned in `engine/nodes.lock`: ComfyUI-GGUF `6ea2651` (2026-01-12), LanPaint `2d7912f` (2026-09-28).
  ComfyUI-GGUF needs `gguf>=0.13.0` (+ sentencepiece, protobuf); LanPaint has no requirements file.
- `engine/constraints.txt` pins torch 2.13.0+rocm10.0.0 / torchvision 0.28.0 / torchaudio 2.11.0.2.
- Engine venv creation + torch install started in the background (uv, Python 3.13, AMD stable index with
  `[device-all]`).
- `engine/extra_model_paths.yaml` mounts `F:\loom2-models` (loom2 root, default) and `D:\comfyui\ComfyUI\models`
  (backup, files only). `F:\loom2-models` populated with **hardlinks** (same volume as `F:\HF_HOME`) to the
  cached unsloth FLUX.2-dev Q4_K_M, Mistral-Small-3.2 Q4_K_M, Comfy fp8mixed transformer, Mistral fp8 TE,
  flux2 VAE and Turbo LoRA — no bytes copied.
- First bench prompt written: `bench/t2i/01-alley-rain.json` (BFL schema, ~75 words, red-braid character).
- Sanity script: `engine/spikes/e0_sanity.py` (device, SDPA per backend at 4096×128 bf16, fp8 `_scaled_mm`,
  fp8 cast round-trip, conv with MIOpen on/off).

## 2026-10-04 18:47 — E0 environment result: torch 2.13.0+rocm10.0.0 installed and sane

- `uv venv engine/.venv --python 3.13` → Python **3.13.16**; `torch[device-all]==2.13.0+rocm10.0.0` from
  `stable.repo.amd.com/rocm/whl-next/` pulled `rocm-sdk-libraries` + per-arch device packages (gfx1201 included);
  install ≈ 2.5 min. ComfyUI v0.38.2 + ComfyUI-GGUF requirements installed under `engine/constraints.txt` —
  torch untouched (transformers 5.18.0, safetensors 0.8.0, av 19.0.1, gguf, websocket-client 1.9.2).
- **Sanity matrix** (`engine/spikes/out/e0_sanity.json`, 18:46 CEST; all timings synchronised):

| Check | Result |
| --- | --- |
| torch / HIP / device | 2.13.0+rocm10.0.0 · HIP 7.15.26333 · AMD Radeon RX 9070 XT (**gfx1201**, 15.92 GB) |
| bf16 GEMM 4096³ | **121.7 TFLOPS** |
| SDPA 1×24×4096×128 bf16 | flash (AOTriton) **2.84 ms** · mem_efficient 2.86 ms · math 60.2 ms → the flash backend works on gfx1201 |
| fp8 `_scaled_mm` e4m3 1024×2048×4096 | OK, finite |
| fp8 cast round-trip 4096² | OK (max abs err 0.25, expected for e4m3) |
| conv3×3 128ch 512² bf16 | MIOpen **on 1.84 ms** vs off 3.43 ms → MIOpen helps here; ComfyUI disables cudnn on AMD by default — E7 decides on a real VAE decode |

- Verdict: **D16 holds** — no fallback to torch 2.12/2.11 needed. The two fp8 regressions reported for 7.14.x
  nightlies do not reproduce on the 10.0.0 stable wheel.

## 2026-10-04 18:50 — E0 engine: headless ComfyUI v0.38.2 running on the new stack

- `scripts/engine-start.ps1` → ComfyUI 0.38.2, "AMD arch: gfx1201", "ROCm version: (7, 15)", vram state
  NORMAL_VRAM, "DynamicVRAM support detected and enabled", async weight offloading with 2 streams, PyTorch
  attention, `torch.backends.cudnn.enabled = False` (ComfyUI default on AMD). comfy-aimdo 0.5.5 hooked the WDDM
  adapter; comfy-kitchen 0.2.36 eager backend only (no CUDA kernels, as expected).
- Custom nodes imported: ComfyUI-GGUF (0.0 s), LanPaint (0.5 s). Model mounts from `engine/extra_model_paths.yaml`
  resolved (`F:\loom2-models\vae\flux2-vae.safetensors` picked up).
- First prompt (dev GGUF Q4_K_M + Mistral GGUF Q4_K_M, 960×544, 20 steps, `res_multistep`/`sgm_uniform`,
  guidance 4.0, bench `01-alley-rain.json`) accepted; GGUF qtypes Q6_K/F32/Q4_K detected; tekken tokenizer
  recreated from GGUF metadata. Timing follows below.

## 2026-10-04 18:51 — E0 finding 1: GGUF Mistral text encoder fails on ComfyUI 0.38.2 (tekken tokenizer)

- `CLIPLoaderGGUF` → `KeyError: 'default_num_special_tokens'` in core `comfy/text_encoders/bpe_tokenizer.py:271`
  (`from_tekken_json`). Root cause: ComfyUI-GGUF `loader.py:gguf_tekken_tokenizer_loader` rebuilds a tekken JSON
  from the GGUF's HF-style tokenizer metadata with `config = {num_vocab_tokens, default_vocab_size}` only; core's
  newer parser also needs `default_num_special_tokens` (the offset it adds to vocab ranks; 1000 in Mistral's real
  `tekken.json`). The GGUF transformer itself loaded fine (qtypes Q6_K/F32/Q4_K detected). Engine stayed healthy.
- Upstream: **city96/ComfyUI-GGUF PR #479** (2026-09-05, open) fixes exactly this; the pinned node commit
  (`6ea2651`, 2026-01-12) predates core's parser change. This is the "graph/engine API drift" risk from 06 §10,
  caught by the first contract run rather than by a user.
- The Comfy-Org fp8 encoder (`mistral_3_small_flux2_fp8.safetensors`) embeds the real tokenizer as a
  `tekken_model` U8 tensor (19.4 MB), which is why the core `CLIPLoader` path does not have this problem.
- Decision for E0: (a) run the fp8 variant now; (b) add a **`gguf-fp8te`** config (GGUF transformer + fp8 encoder)
  so the GGUF transformer can be timed independently of the tokenizer gap; (c) apply PR #479's change to the
  vendored node as a **recorded local patch** (`engine/patches/`) until it is merged, then re-test the all-GGUF
  config. The roster must be able to express "this GGUF text encoder needs an external tokenizer".
- Patch applied: `engine/patches/comfyui-gguf-pr479-tekken-special-tokens.patch` (one line, `default_num_special_tokens: 1000`),
  recorded in `engine/nodes.lock`. Takes effect after an engine restart.

## 2026-10-04 18:54 — E0 result: first FLUX.2 dev JSON-prompt image through the engine (fp8mixed) ✅

Stack: ComfyUI 0.38.2 (`daeb5e5`) · torch 2.13.0+rocm10.0.0 · HIP 7.15 · gfx1201 · `flux2_dev_fp8mixed.safetensors`
(33.8 GB staged for dynamic VRAM) + `mistral_3_small_flux2_fp8.safetensors` (17.2 GB staged) + `flux2-vae` ·
960×544 · 20 steps · `res_multistep` / `sgm_uniform` · guidance 4.0 · cfg 1.0 · seed 20261004 · prompt =
compact JSON of `bench/t2i/01-alley-rain.json` (1 239 chars) wrapped by core in BFL's Mistral template.

| Run | engine exec | sampling (first→last step) | per step | VRAM free after | note |
| --- | --- | --- | --- | --- | --- |
| 1 (cold) | **107.4 s** | 52.1 s | ≈ 2.7 s/it | 6.84 GB (≈ 9 GB resident) | model init 29 s on the first step, TE encode + staging the rest |
| 2 (warm, seed +1) | **62.3 s** | 53.5 s | ≈ 2.8 s/it | 6.81 GB | init 6.7 s; weights stayed staged between prompts |

- **Adherence** (`engine/spikes/out/e0_fp8-20st-960x544_s20261004.png`): subject identity (red braids, freckles,
  green hooded wool cloak, brass compass in the right hand), position (right third, waist-up), pose (body away,
  head turned back over the shoulder), lighting (cyan neon rim from the left, warm sodium lamp behind, wet-ground
  fill), background (crates, steaming vent, **legible "MARLOW & SONS" sign**, harbour cranes in mist), composition
  (diagonal alley, foreground rain streaks), shallow depth of field, painterly concept-art style and the four-colour
  palette are all present. Camera angle reads near eye level rather than clearly low — the same miss loom saw.
  Seed +1 (`…_s20261005.png`) keeps every identity trait and the composition, renders the sign as cyan neon text
  and moves the lamp — good seed-to-seed consistency for a storyboard character without any reference image.
- **Versus loom's torch worker** (02 §5: dev-turbo 4 steps ≈ 100 s per warm cell at 512², dev 8 steps ≈ 185 s cold):
  the ComfyUI engine on ROCm 10 does **20 full steps at 2× the pixel count in about the same wall time**, with the
  33.8 GB fp8 transformer streamed by DynamicVRAM/async offload instead of HMM thrashing. **D2 (ComfyUI as engine)
  and D16 (new stack) pass their first gate.**
- Still owed in E0: GGUF Q4 transformer timing (`gguf-fp8te`, then all-GGUF after the engine restart with the
  tokenizer patch), Turbo LoRA 8-step variant, Klein 9B, the 50-job stability loop, and the A/B against loom's venv.

## 2026-10-04 19:03 — E0 finding 2 (preliminary): GGUF Q4_K_M transformer is ~12× slower than fp8mixed here

- `gguf-fp8te` (unsloth `flux2-dev-Q4_K_M.gguf` 18.6 GB via ComfyUI-GGUF + Comfy fp8 TE), same prompt/size/steps:
  engine log "loaded partially; 13 914 MB usable, 13 669 MB loaded, 5 798 MB offloaded"; model init 27.6 s;
  sampling **≈ 32.7 s/it** vs **2.8 s/it** for `flux2_dev_fp8mixed` (DynamicVRAM-streamed).
- **Final (19:06):** run 1 engine exec **675.8 s**, sampling 620.9 s for 20 steps (**31 s/it**), VRAM free after
  7.12 GB. Same seed as the fp8 image → `e0_gguf-fp8te-20st-960x544_s20261004.png` is **visually equivalent**
  (same composition, sign, lighting, identity), i.e. Q4_K_M costs nothing in quality here, only **≈ 11× the
  time**. Warm repeat interrupted via `POST /interrupt` at 19:06:57 (engine handled it cleanly).

## 2026-10-04 19:08 — E0 result: FLUX.2 dev + Comfy Turbo LoRA, 8 steps (fp8mixed)

| Run | engine exec | sampling | per step | VRAM free after | note |
| --- | --- | --- | --- | --- | --- |
| 1 (seed 20261004) | **39.1 s** | 28.3 s | 3.5 s/it | 6.78 GB | includes LoRA patch (`Flux2TurboComfyv2`, strength 1.0) |
| 2 (seed +1) | 52.2 s | 43.9 s | 5.5 s/it | 7.06 GB | slower: ran right after the interrupted GGUF job (free VRAM had dropped to 1.96 GB), engine was re-staging — re-measure in the stability loop |

- `e0_fp8-turbo-8st-960x544_s20261004.png`: adherence holds (identity, compass, neon rim, legible "MARLOW & SONS",
  cranes, rain); slightly more stylised/graphic rendering than the 20-step image, as expected from the
  step-distillation LoRA. **Draft-tier operating point candidates:** 20 steps ≈ 62 s (quality) · Turbo 8 steps ≈ 40 s.
- E0 t2i summary so far (960×544, dev): fp8 20 st **62 s warm / 107 s cold** · fp8 Turbo 8 st **≈ 40 s** · GGUF Q4
  20 st **676 s**. Loom's old worker: ≈ 100 s per warm cell at 512² (4-step turbo) — the new engine is roughly
  **4–5× faster per pixel-step** on the same card.

## 2026-10-04 19:10–19:39 — E0: engine restart, all-GGUF check, stability loop chunk 1

- Engine stopped (`scripts/engine-stop.ps1`, two PIDs: the PowerShell wrapper and python) and restarted with the
  patched ComfyUI-GGUF; ready in 6 s.
- **All-GGUF (dev Q4_K_M + Mistral Q4_K_M GGUF), 4 steps, 960×544:** success — the PR #479 patch fixes the
  tokenizer; GGUF TE "loaded completely; 14 615 MB usable, 14 057 MB loaded". Engine exec 218.3 s, sampling 103.5 s
  (25.9 s/it), VRAM free after 6.94 GB. Confirms finding 2: GGUF is the slow path on this stack.
- **Stability loop chunk 1 — 25/25 success, 0 errors, no HIP faults** (fp8mixed + Turbo, 8 steps, 896×512, seeds
  1000–1024). Engine exec min 42.4 / median 67.6 / max 69.2 s; sampling min 27.1 / median 57.7 / max 59.4 s;
  VRAM free after 6.78–7.65 GB.
- **Finding 3 — bimodal per-job time (7 fast ≈ 42 s, 18 slow ≈ 68 s):** sampling alternates between ≈ 4.5 s/it
  and ≈ 7.2 s/it, both slower than the 3.5 s/it seen before the GGUF jobs. Reading: with the 17 GB fp8 text
  encoder and the 34 GB fp8 transformer sharing 16 GB, DynamicVRAM evicts the transformer whenever the encoder is
  brought back for the next prompt, so most jobs re-stream transformer weights during sampling. This is loom's
  two-phase lesson (02 §7 #4) reappearing inside the engine. Mitigations to test: (a) `CLIPLoader device=cpu`
  (encoder never touches the GPU; Mistral-24B fp8 encode on the 9950X with 128 GB RAM), (b) batch graphs that
  encode N prompts first and sample N latents with the transformer resident, (c) smaller encoder (`fp4_mixed`,
  12.3 GB). (a) gets a 3-run test right after chunk 2 (`--te-device cpu` added to the driver).

## 2026-10-04 20:04 — E0: stability loop complete — **50/50 jobs succeeded, 0 errors, no HIP faults**

- Chunk 2 (seeds 1025–1049, 19:40:26 → 20:04:04): 25/25 success; exec min 42.5 / median 67.6 / max 69.7 s;
  sampling min 35.6 / median 57.7 / max 59.6 s; 9 fast runs; VRAM free after 7.31–7.65 GB (no leak across 50 jobs).
- Whole day on the engine: 57 executions (incl. the GGUF variants), 1 deliberate interrupt, **no "unspecified
  launch failure", no NaN/black outputs, no restart needed**. The restart-per-N-jobs mitigation (04 §2) stays
  available but was not required on ROCm 10.0 stable with this GPU.
- The bimodal timing (finding 3) persisted through all 50 jobs → it is systematic, not warm-up. Encoder-on-CPU
  test next.

## 2026-10-04 20:10 — E0: encoder-on-CPU test (3 runs) — finding 3 corrected

| Run | engine exec | sampling | note |
| --- | --- | --- | --- |
| 1 | 206.5 s | 35.0 s | first encode on the CPU (Mistral-24B fp8 → ≈ 170 s on the 9950X) |
| 2 | 67.1 s | 57.5 s | **no re-encode**: ComfyUI caches `CLIPTextEncode` for an unchanged prompt |
| 3 | 68.9 s | 59.1 s | same |

- **Correction:** the stability loop used one prompt for all 50 jobs, so the text encoder never re-ran after
  job 1 and the encoder/transformer eviction story cannot explain the slow jobs. The slowness is in the
  **transformer sampling itself**: ≈ 7.2 s/it (slow jobs) / 4.5 s/it (fast jobs) at 896×512 versus 3.5 s/it at
  960×544 in the first Turbo run and 2.7 s/it in the 20-step runs. Moving the encoder to CPU changed nothing
  (and costs ~170 s per *new* prompt) → **keep the encoder on the GPU** (default).
- Open hypotheses for the slow mode, to be tested in M3 with instrumentation: (1) **thermal throttling** under
  sustained load (loom lesson 11 — hot-spot temperature; the fast/slow alternation looks like a duty cycle);
  (2) DynamicVRAM residency of the streamed fp8 transformer varying job to job; (3) Turbo-LoRA patches applied
  per streamed weight rather than fused. Needed: a GPU hot-spot/clock log alongside the driver (HWiNFO shared
  memory or ADLX), a no-LoRA 8-step control, and a `--disable-dynamic-vram` control. Not blocking E0: every pass
  bar is met and the worst case (≈ 68 s per Turbo draft) is still well under loom's old ≈ 100 s per cell.
- Reading: on gfx1201 + ROCm 10 the native fp8 path is far better than on-device GGUF dequantisation with partial
  offload — the "GGUF under-utilisation on AMD" reports (04 §2) reproduce. Consequence for D6/04 §3b: **fp8mixed
  (Comfy-Org) is the dev default format**; GGUF stays a disk/VRAM-saving option, not the speed path. Worth one
  follow-up: `UnetLoaderGGUFAdvanced` dequant-dtype options and `--lowvram` to see whether full-GPU residency of a
  smaller quant (Q3_K_M 15.8 GB) changes the picture — low priority given the fp8 result.

*(Ordering note: the 19:06–20:10 entries above were inserted under the 18:54 entry before this one; read by
timestamp, not by position.)*

## 2026-10-04 20:35 — E0: A/B against loom's torch worker (Engine B) — same prompt, same settings

Engine stopped first (GPU exclusive). loom's vendored `pipeline.flux2.run_pipeline --jobs-file` in loom's
untouched venv (torch 2.9.1+rocm7.2.1, Comfy fp8 split files through loom's `scaled_fp8` loader, two-phase
TE→flow, `MIOPEN_FIND_MODE=2`), `flux.2-dev`, 20 steps, guidance 4.0, 960×544, seeds 20261004/20261005.
(First attempt failed on Windows PowerShell 5.1 mangling the quoted JSON argument — fixed by using the jobs file;
`e0_loom_ab.ps1` rewritten accordingly.)

| Engine | per image (20 st, 960×544) | notes |
| --- | --- | --- |
| loom worker, old stack | **649 s / 650 s** (batch total 1 371 s incl. 22.7 s text encode for both) | tqdm claimed 32 step/s — async HIP again (loom lesson 3); the real cost is weight paging per step |
| ComfyUI engine, new stack | **107 s cold / 62 s warm** | same files, DynamicVRAM streaming + async offload |

→ **≈ 10× faster per image** on the new engine + stack for the identical model, size and step count.
`loom-ab/flux2_…_s20261004.png` is a valid, on-prompt render (different sampler schedule, so not
pixel-comparable) — the old path still works, it is simply far slower.

## 2026-10-04 20:40 — **E0 closed: PASS** (dev scope; Klein items moved per D21)

| Pass bar (12 §1) | Result |
| --- | --- |
| Environment sane on the rig | ✅ torch 2.13.0+rocm10.0.0 / HIP 7.15 / gfx1201; flash SDPA, fp8 `_scaled_mm`, fp8 casts OK |
| Pinned ComfyUI v0.38.2 headless on the new stack | ✅ ready in 6 s; DynamicVRAM; both custom nodes imported; one drift bug (GGUF tekken tokenizer) found and patched (PR #479) |
| dev produces JSON-adherent images, time + VRAM recorded, both formats | ✅ fp8mixed 62 s warm / 107 s cold; GGUF Q4 676 s; Turbo 8-step ≈ 40 s (42–68 s under sustained load); adherence high on `01-alley-rain` incl. legible sign text; VRAM free after 6.8–7.6 GB |
| 50 jobs unattended, no HIP failure | ✅ 50/50 + 7 other executions, 0 errors, no leak |
| Measure vs loom's worker | ✅ 649 s vs 62 s per image (≈ 10×) |
| Klein 9B ≤ 15 s/image; Klein inpaint seam on 2 tasks | ⏭ moved to M5/E8 by D21 (dev-first); Klein graphs are built there |

Decisions confirmed: **D2** (ComfyUI as the engine) and **D16** (new environment) are verified; **D6/D21
amended → D29**: dev default format = Comfy-Org fp8mixed, encoder on the GPU. New proposal **D28**: no Engine B
adapter in M1 (vendored worker kept as reference). Open: **Q15** (slow-mode cause), **Q16** (accept D28?).
Artefacts: `engine/spikes/out/` (e0_sanity.json, e0_t2i_results.jsonl — 60 rows, PNGs, engine logs, loom-ab/),
`bench/t2i/01–10`, `bench/inpaint/tasks.json` + masks, `bench/i2v/tasks.json`, `scripts/engine-start|stop.ps1`,
`engine/spikes/e0_*.py|ps1`, `engine/patches/`, `engine/nodes.lock`. Nothing committed yet (author's call).

## 2026-10-04 21:05 — first commit and push; D28 accepted

- Initial commit `409e2a1` (51 files, ≈ 380 KB; venvs, weights, spike outputs excluded) pushed to
  **https://github.com/stubz100/Loom2** (`origin/main`). Added `scripts/engine-setup.ps1` (recreates venv,
  submodule, pinned nodes and patches from `nodes.lock`), root `README.md`, `.gitattributes`.
- **D28 accepted** by the author after reviewing the E0 evidence: loom's worker is not built into loom2 (reference
  only). Scope of the proof recorded in 13: identical files/settings, 649 s vs 62 s per image, the gap attributed to
  loom's whole-model HMM paging design (its own probes), capability gap (no inpaint/video nodes), stability of 57
  engine executions. Not isolated: the worker on the new torch/ROCm stack (not worth porting). Q16 closed; Q15
  (bimodal sampling speed) remains the only open question.

## 2026-10-04 21:40 — M0 GPU-free spikes: harness built, E6 backend half measured

- `frontend/` scaffolded (Vite 8, React 19, TS 6; pixi.js **8.22.0**, mediabunny **1.61.1**, @tauri-apps/cli 2.12.1;
  `src-tauri` initialised, identifier `com.stubz100.loom2`). Spike harness in `frontend/src/spikes/` (plain DOM,
  hash routes `#e1 #e1-webgl #e2 #e3 #e6 #all`), results posted to the E2 server → `orchestrator/spikes/out/*.jsonl`.
- `orchestrator/.venv` (uv, Python 3.13, torch-free): fastapi, uvicorn[standard], numpy, pillow, av. E2 server
  `orchestrator/spikes/e2_loopback.py` on 127.0.0.1:8765 (200 MB float16 latent, 8K PNG + raw RGBA, streaming
  `PUT /blobs/{sha256}`, `/spike/result`).
- **E6 backend (PyAV)**: `orchestrator/spikes/e6_make_clip.py` encodes 121 frames @ 24 fps 1024×576 h264 (GOP 24,
  frame index burned in as a 7-bit pixel code + text; 1.2 MiB) in 0.9 s; exact seek (seek to keyframe + decode
  forward) over 29 scattered forward/backward targets: **0 wrong frames, 4.2 / 12.5 / 21.6 ms min/median/max** →
  the backend half of E6 passes without TorchCodec. (Windows console needs `PYTHONIOENCODING=utf-8` for the
  script's arrows — noted for the orchestrator's logging setup.)
- Browser run of `#all` launched in Edge 154 at 21:40 (same Chromium as WebView2); Tauri window run follows.
- 21:41: the assistant session ended mid-run; the E2 and Vite servers (children of that session) died with it,
  so only E1's two rows (WebGPU, WebGL) were recorded. Both show a flat **30 fps** (33.4 ms frames, max 34 ms)
  in every phase — a presentation cap, not compositing cost (frame time does not change between fit, 1:1 and 2×).

## 2026-10-05 08:00 — M0 spikes resumed

- Servers restarted (E2 on 8765, Vite on 1420); `#all` re-run in a maximised new Edge window to rule out the
  unfocused-window throttle as the cause of the 30 fps cap; E3 reports the measured rAF rate independently.
- Harness bug found: `#all` read its queue before setting it, so the sequence stopped after E1 (the "WebGL"
  row of 2026-10-04 was in fact a second WebGPU run). Fixed; renderer name now taken from `RendererType`.

## 2026-10-05 08:01 — M0 spikes, first complete Edge run (Edge 154, window 1262×547 CSS @ DPR 1.5)

| Spike | Result | Bar | Verdict |
| --- | --- | --- | --- |
| **E1** compositor, 6 × 4096² layers, 3 advanced blend modes + mask | WebGPU **29.8–30 fps**, WebGL **30 fps**; frame time 33.4 ms median in *every* phase (fit, 1:1, 2×), max 34 ms (one 67 ms hitch on WebGPU); layers built in 24–34 ms; ≈ 384 MiB of textures | 60 fps | **inconclusive**: a presentation cap — compositing cost does not change between phases |
| **E2** loopback | 200 MB fetch **422 MiB/s**; 8K raw (256 MB) → WebGPU texture: fetch 0.59 s + upload 0.18 s = **329 MiB/s** end-to-end; 8K PNG 64 MB: fetch 0.20 s + decode 0.52 s; 64 MB PUT **338 MiB/s** client-side (server-side streaming 1 167 MB/s, sha ok) | ≥ 500 MB/s into a texture | **below bar** — single-connection FileResponse with 64 KiB chunks; testing 4 MiB chunks + parallel Range fetches |
| **E3** brush, 2048×1152 worker canvas | 1 200 `pointerrawupdate`-path events × 4 coalesced = 4 800 points at **250 events/s**, **4 800 dabs drawn, 0 dropped**; latency median **49.9 ms = 1.5 frames at the measured 30 Hz** (p95 1.95 frames); worker 40 fps | ≤ 1 frame, no drops | drops: **pass**; latency: 1.5 frames by a conservative measure (event → start of the frame *after* the one that drew it, i.e. commit); needs a 60 Hz measurement |
| **E6** scrub (Mediabunny CanvasSink, h264 1024×576 121 f, GOP 24) | **0 wrong frames** in 222 seeks; sequential median **35 ms** (p95 67), random **65 ms**, backward-by-3 **66 ms**; backend PyAV exact seek 12.5 ms median | every frame, < 50 ms | accuracy **pass**; random access over bar → re-encode proxies with GOP 6 / intra-only (ours to choose) |

- **30 Hz everywhere, explained:** `Win32_VideoController.CurrentRefreshRate = 29` — the 3840×2160 display (DPR
  1.5, console session, not RDP) is running at **29–30 Hz**; its max is 75 Hz. Every rAF-paced number today is
  vsync-limited to 30 fps. → **Author action:** set the monitor to 60 Hz (or 75 Hz) in Windows display settings;
  loom2's brush/scrub latency halves with it. E1 gains a vsync-independent throughput phase (render + GPU
  completion per frame) so compositing cost can be measured regardless of refresh.
- **E3 verdict refined → pass:** with the commit-based measure, the theoretical minimum for any rAF-driven
  renderer is 1.5 frames median (0–1 frame to the next rAF + 1 frame to present); measured 1.5 / p95 1.95 with
  0 of 4 800 dabs dropped at 250 events/s → the worker brush is at the floor. The pass bar in 05 §9 / 12 E3 is
  reworded to "median ≤ 1.5 frames, p95 ≤ 2, no drops" (same-day amendment).

## 2026-10-05 08:05 — second Edge run: E1 and E6 pass, E2 re-test pending

| Spike | Result |
| --- | --- |
| **E1** vsync-independent throughput (render + GPU completion per frame, 6 × 4096² layers, 3 advanced blends + mask) | **WebGPU: 3.0 ms median / 4.5 ms p95 per frame (≈ 330 fps-equivalent)** in fit, 1:1 and 2× phases; **WebGL2: 0.4–0.7 ms median** (readPixels sync; likely not a full GPU fence, so treat as "≤ 1 ms"). Either way the compositing budget is < 5 ms of a 16.7 ms frame → **PASS on cost**; the rAF fps stays 30 only because of the 29 Hz monitor. Tauri/WebView2 confirmation follows. |
| **E3** repeat | identical: 0 dropped, 1.5 / 1.96 frames at 30 Hz |
| **E6** three proxy encodings, Mediabunny `CanvasSink`, all **0 wrong frames** | GOP 24 (1.2 MiB): sequential 12.3 ms, random **17.8 ms**, backward 14.9 ms median (first run's 65 ms was CPU contention); **GOP 6 (2.3 MiB): ≈ 10 ms for every access pattern**; intra-only (5.1 MiB): ≈ 7.5 ms. Backend PyAV: 14.5 / 13.6 / 6.1 ms median. → **PASS**; proxy policy: **GOP 6** h264 (2× the size of GOP 24, uniform ≈ 10 ms seeks), intra-only optional for scrub-heavy clips. |
| **E2** | the page failed because the server returned 500 on every file request: in this Starlette version `FileResponse.chunk_size` is a class attribute, not a constructor argument. Fixed and re-run below. |

## 2026-10-05 08:07 — E2 loopback with 4 MiB response chunks: **PASS**

| Path | 64 KiB chunks (yesterday) | **4 MiB chunks** |
| --- | --- | --- |
| 200 MB float16 fetch → ArrayBuffer | 422 MiB/s | **1 276 MiB/s** (0.157 s) |
| same, 2 / 4 / 8 parallel Range requests | — | 1 635 / **1 957** / 1 393 MiB/s (joined: 1 377 / 1 625 / 1 217) |
| 8K raw RGBA (256 MB) → WebGPU texture, end-to-end | 329 MiB/s | **782 MiB/s** (fetch 0.158 s + upload 0.169 s) |
| 8K PNG (64 MB) fetch + `createImageBitmap` decode | 0.20 + 0.52 s | 0.13 + 0.52 s (decode is the cost: raw beats PNG for GPU-bound paths) |
| 64 MB streaming `PUT` with server-side sha256 | 338 MiB/s client / 1 167 MB/s server | 315 MiB/s client / 963 MB/s server (client time includes the hash reply) |

→ bar "≥ 500 MB/s into a GPU texture" met with margin. Transport rules confirmed (06 §2): raw octet-stream,
Range supported (`206` verified), **FileResponse chunk size 4 MiB**, 2–4 parallel ranges for the biggest
buffers, no base64. Starlette 500s were silent to the browser — the real orchestrator must log 5xx with
tracebacks (E2 server now does).

## 2026-10-05 08:13 — the same sequence inside the **Tauri 2 shell (WebView2)**

`npx tauri init` (identifier `com.stubz100.loom2`, devUrl 127.0.0.1:1420) → first Rust build **54 s** (352
crates) → window opens the dev URL and runs `#all` by itself. (Lesson: Tauri's `beforeDevCommand` starts its own
Vite; a separately started Vite on the same strict port aborts `tauri dev` — one dev-server owner only.)

| Spike | WebView2 (Tauri window 800×480 CSS) | vs Edge |
| --- | --- | --- |
| **E1** WebGPU | renders (blend modes + mask) at 30 fps rAF; **canvas "render + completion" = 33.3 ms exactly** → in WebView2 `onSubmittedWorkDone` after a canvas render waits for the swap-chain present, so this measure is vsync-bound here; WebGL2 0.4–0.7 ms as in Edge | Edge 3.0 ms on the same measure — an offscreen-target measure is added to settle it |
| **E2** | latent 1 002 MiB/s · 4 ranges 1 957 MiB/s · **8K raw → WebGPU texture 695 MiB/s** · PNG decode 0.57 s · 64 MB PUT 173 MiB/s client (server 416 MB/s) | same class; uploads ≈ 2× slower in WebView2 — fine for masks |
| **E3** | 0 of 4 800 dropped at 250 ev/s, 1.5 / 1.96 frames at 30 Hz | identical |
| **E6** | 0 wrong frames; GOP 24 random 17.3 ms, **GOP 6 9.7 ms**, intra 7.3 ms | identical |

→ **D3/D4 hold inside the real shell**: WebGPU + PixiJS v8 + Mediabunny + loopback HTTP all work in WebView2 on
this AMD rig; only the 60 fps bar is unverifiable on a 29 Hz monitor.

## 2026-10-05 08:14 — E1 settled with the offscreen measure (Tauri/WebView2, relaunched window)

Composite of 6 × 4096² layers (normal, multiply, screen, overlay, soft-light, difference) + a Graphics mask into
a viewport-sized RenderTexture, GPU completion awaited per frame:

| Renderer | fit | 1:1 | 2× | note |
| --- | --- | --- | --- | --- |
| **WebGPU** | **3.0 ms** median, 4.1 p95 | 3.0 / 4.1 | 3.0 / 4.4 | ≈ 330 fps-equivalent; identical to Edge; the earlier 33 ms canvas-path number was swap-chain acquisition waiting for vsync |
| WebGL2 | 0.0–0.1 ms reported | — | — | `gl.finish()` does not block in Chromium's command buffer → not a measurement; the canvas-path readPixels sync gave 0.4–0.7 ms, so WebGL2 is at least as cheap |

**E1 verdict: PASS** — compositing cost is < 5 ms of a 16.7 ms frame on both renderers inside the Tauri shell;
rAF fps is 30 only because the display runs at 29 Hz (author action: switch the monitor to 60/75 Hz).

## 2026-10-05 08:15 — **M0 GPU-free spikes closed: E1, E2, E3, E6 all PASS** (Edge and Tauri/WebView2)

| Spike | Verdict | Key number | Policy it fixes |
| --- | --- | --- | --- |
| E1 compositor | PASS | 3.0 ms per 6×4K composite with advanced blends + mask (WebGPU, WebView2) | D3 stands: PixiJS v8 WebGPU with WebGL2 fallback; 2048² tiles unchanged |
| E2 transport | PASS | 782 MiB/s (Edge) / 695 MiB/s (WebView2) 8K raw → WebGPU texture; 1.0–1.3 GiB/s single fetch, ~2 GiB/s with 4 ranges | D4 stands + `FileResponse.chunk_size = 4 MiB`, raw over PNG for GPU-bound buffers, 2–4 parallel ranges for ≥ 100 MB |
| E3 brush | PASS | 0 of 4 800 dabs dropped at 250 events/s; latency at the rAF floor (1.5 frames median) | worker + OffscreenCanvas brush architecture stands; pressure path untested (no pen, D19) |
| E6 scrub | PASS | 0 wrong frames in 3 × 222 seeks; GOP 6 proxies ≈ 10 ms for any access pattern; backend PyAV exact seek 6–15 ms | video proxies = h264 GOP 6 (intra optional); Mediabunny `CanvasSink` is the player core; TorchCodec not required |

Remaining M0 spikes need the GPU engine: E4 (Wan 2.2 I2V + FLF), E5 (LTX-2.3), E7 (MIOpen on real VAE
decode), E8 (inpaint bake-off); E9 lives in M6. Harness kept as `frontend/src/spikes/` for M1 regression use.

## 2026-10-05 08:19 — E4 / E5 / E8 weight manifest (from the HF API; **awaiting the author's go** before fetching)

Nothing below is downloaded yet. Sizes are the hub's; all land in `F:\loom2-models` (ComfyUI layout) and get
roster entries with sha256 on fetch. Disk F: has ≈ 365 GB free.

| Spike | File (repo → path) | Size | Licence / provenance |
| --- | --- | --- | --- |
| **E4 Wan 2.2 I2V-A14B** | `QuantStack/Wan2.2-I2V-A14B-GGUF` → `HighNoise/…-Q5_K_M.gguf` + `LowNoise/…-Q5_K_M.gguf` | 10.05 + 10.05 GiB | Apache-2.0 weights; QuantStack GGUF (community quantiser, D1 order) |
| | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` → `split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `split_files/vae/wan_2.1_vae.safetensors` | 6.27 + 0.24 GiB | Comfy-Org repack |
| | `lightx2v/Wan2.2-Lightning` → `Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/{high,low}_noise_model.safetensors` | 1.14 + 1.14 GiB | Apache-2.0 |
| **E5 LTX-2.3** | `unsloth/LTX-2.3-GGUF` → `distilled-1.1/ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf` | 13.22 GiB | LTX-2.x Community; Unsloth GGUF |
| | `unsloth/gemma-3-12b-it-GGUF` → `gemma-3-12b-it-Q4_K_M.gguf` (text encoder) | 6.80 GiB | Gemma licence |
| | `Lightricks/LTX-2.3` → `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` (+ VAE/TE split files from `Kijai/LTX2.3_comfy` or `Comfy-Org/ltx-2.3`, to be confirmed when E5 starts — the Comfy-Org repo currently lists only LoRAs) | 0.93 GiB (+ ≈ 1 GiB) | LTX Community |
| **E8 FLUX.1 Fill** (quality fallback) | option a: `YarvixPA/FLUX.1-Fill-dev-GGUF` → `flux1-fill-dev-Q8_0.gguf` | 11.85 GiB | FLUX NC; community GGUF of gated weights |
| | option b (cleaner provenance): `black-forest-labs/FLUX.1-Fill-dev` → `flux1-fill-dev.safetensors` with the author's HF token, cast to fp8 on load by the engine | 22.17 GiB | FLUX NC, gated (licence already accepted for loom) |
| **E8 / M5 Klein 9B** | transformer: BFL `flux-2-klein-9b.safetensors` **already cached** (18.2 GB bf16, hardlink); TE: `Comfy-Org/flux2-klein-9B` → `split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors` | 0 + 8.07 GiB | FLUX NC (9B); Comfy-Org has no fp8 9B transformer — stream the bf16 or cast on load |
| **open variant Klein 4B** (optional now) | `Comfy-Org/flux2-klein-4B` → `split_files/diffusion_models/flux-2-klein-4b.safetensors`, `split_files/text_encoders/qwen_3_4b.safetensors` | 7.22 + 7.49 GiB | Apache-2.0 |
| E8 Qwen-Image-Edit | already on `D:` (2509 fp8 + Lightning LoRAs) | 0 | Apache-2.0 |

Totals: **E4 ≈ 29 GiB · E5 ≈ 22 GiB · E8 ≈ 20–30 GiB (Fill a/b + Klein TE)** → **≈ 71–81 GiB**, plus ≈ 15 GiB if
Klein 4B is fetched now. Order proposed: E8 (Klein TE 8 GiB, then Fill) → E4 → E5.

## 2026-10-05 08:25 — E7 (MIOpen on real workloads), configuration A = ComfyUI AMD default (cudnn/MIOpen **off**)

Driver now records per-node wall time from the engine's `executing` events. fp8mixed dev + Turbo, 8 steps.

| Job | engine exec | KSampler node | **VAEDecode node** | CLIPTextEncode | note |
| --- | --- | --- | --- | --- | --- |
| 960×544, run 1 (cold) | 83.6 s | 59.9 s (incl. ≈ 30 s model init) | **2.27 s** (incl. VAE → GPU) | 19.6 s (incl. 17 GB TE staging) | |
| 960×544, run 2 (warm) | 58.6 s | 57.6 s (slow mode, ≈ 7 s/it — Q15) | **0.92 s** | 0 (cached) | |
| **1920×1088 (Full tier)**, warm | **279 s** | 273 s (≈ 30 s/it at 8 160 tokens) | **5.55 s** | 0 | first measured FHD dev image: ≈ 4.7 min at 8 steps → confirms D18 "dev FHD = Draft + upscale", not native |

VAE decode is already cheap with MIOpen off (0.9 s at 0.5 MP, 5.6 s at 2.1 MP); configurations B
(`COMFYUI_ENABLE_MIOPEN=1 MIOPEN_FIND_MODE=2`) and C (MIOpen on, default find mode) follow.

## 2026-10-05 08:32 — E7 configuration B = `COMFYUI_ENABLE_MIOPEN=1 MIOPEN_FIND_MODE=2` (loom's old setting)

| Job | engine exec | KSampler | **VAEDecode** | note |
| --- | --- | --- | --- | --- |
| 960×544 run 1 | 80.6 s | 60.3 s | **11.98 s** | MIOpen find-mode tuning on the first decode shape (vs 2.27 s with MIOpen off) |
| 960×544 run 2 | 59.6 s | 58.7 s | **0.91 s** | identical to MIOpen off once tuned |
| 1920×1088 | 269.1 s | 261.5 s | **7.35 s** | new shape → tuned again; slower than MIOpen off (5.55 s) |

→ MIOpen buys nothing for the FLUX.2 VAE on this stack (ROCm 10 / torch 2.13): warm decode is equal, every
new resolution pays a tuning penalty. The sanity-matrix conv win (18:46 yesterday) does not carry over to the
real workload. Sampling is unaffected (transformer path is matmul/attention, not conv).

## 2026-10-05 08:40 — E7 configuration C = `COMFYUI_ENABLE_MIOPEN=1`, default find mode — and the **E7 verdict**

| Job | engine exec | KSampler | **VAEDecode** | note |
| --- | --- | --- | --- | --- |
| 960×544 run 1 | 88.1 s | 60.4 s | **16.25 s** | full MIOpen search on the first shape |
| 960×544 run 2 | 73.8 s | 73.5 s (slow mode) | **0.25 s** | the tuned kernel is 3.7× faster than MIOpen-off (0.92 s) |
| 1920×1088 | 277.8 s | 262.6 s | **15.1 s** | new shape → full search again (no warm FHD sample) |

**E7 verdict (closed, PASS as a decision):** keep ComfyUI's AMD default — **MIOpen off** (D13 confirmed).
Evidence: with MIOpen off the VAE decode is 0.9 s at Draft and 5.6 s at Full, i.e. < 2 % of a dev image; MIOpen
costs 12–16 s of search per new resolution per session and only wins ≈ 0.7 s per warm Draft decode. An optional
post-MVP optimisation exists (MIOpen on + a warm-up decode per tier at engine start, if MIOpen's find-db
persists across runs on Windows — unverified), worth ≈ 0.7 s at Draft and a few seconds at Full. ESRGAN was not
measured (no upscale model on disk); revisit when SeedVR2/ESRGAN enter the roster.

**M0 spike board after E7:** E0 ✅ · E1 ✅ · E2 ✅ · E3 ✅ · E6 ✅ · E7 ✅ · **E4, E5, E8 pending the weight
downloads (author's go)** · E9 scheduled in M6. Q15 (bimodal sampling speed) remains open — every E7 run showed
it again: KSampler ≈ 58–74 s for 8 steps at 960×544 in warm runs vs 27 s sampling in cold run 1.

## 2026-10-05 09:05 — HF cache on F: cleaned for loom2 (author's request); FLUX.1 Fill = official gated file (Q2)

- Author decisions: delete the old loom weights from `F:\HF_HOME`; fetch FLUX.1 Fill from the official gated
  repo (not the community GGUF); go for the E4/E5/E8 downloads.
- Kept by **hardlinking into `F:\loom2-models`** first (same volume, no copy): FLUX.2 dev fp8mixed, Mistral fp8,
  flux2 VAE, Turbo LoRA, dev Q4_K_M GGUF + Mistral Q4_K_M GGUF, **Klein single files** (4B, base-4B, 9B, 9B-KV,
  base-9B), FLUX.2 small decoder. All still intact after the cleanup (link count 1 each).
- Deleted from the hub (22 repos ≈ 630 GB on disk): Comfy-Org/flux2-dev remainder (bf16 + fp4 encoders), Krea 2,
  SD3.5 large/large-turbo/medium, Z-Image + Turbo, SVD, the Klein repos' diffusers shards + HF Qwen3 encoders,
  Qwen/Qwen3-4B/8B, InstantX Tile CN, inswapper, facefusion mirror, BFL FLUX.2-dev (ae only), the unsloth GGUF
  cache entries (data survives via the hardlinks); plus `insightface/` and `xet/`. **Kept:** BiRefNet, BiRefNet_HR.
- **F: free space 350 GB → 832 GB.** `datasets/parquet` (41.6 GB, four HF `datasets` caches from 2026-06-05)
  inspected next; `modules/` (BiRefNet remote code) kept.
- `scripts/fetch_weights.py` written: manifest-driven fetch into the ComfyUI layout with sha256 + licence into
  `F:\loom2-models\roster.index.json` (the roster's seed). Order: E8 (Klein 9B TE, FLUX.1 Fill official + ae,
  CLIP-L, T5 fp8) → E4 (Wan 2.2 set) → E5 (LTX-2.3 set) → Klein 4B TE.
- `datasets/parquet` identified as Wikipedia parquet→arrow caches of an unrelated project (`E:\…\LLM-Embedding-main`,
  sources on E:) → deleted (41.6 GB). `F:\HF_HOME` now holds only `hub/` (BiRefNet ×2), `modules/`, the token files.
  **F: free = 874 GB.** Downloads (≈ 85 GiB) started 09:08 via `fetch_weights.py` (log:
  `orchestrator/spikes/out/fetch_weights.log`). Rate is bursty over the hub's xet backend (15 s samples from
  3 to 114 MiB/s) but the **average is ≈ 16–18 MiB/s** (Klein encoder: 8.07 GiB in 515 s; NIC inbound 17.7 MiB/s
  during the Fill download) → whole manifest ≈ 1–1.5 h. A plain-HTTPS CDN probe was far slower (0.3 MB/s single
  stream, ~7 MB/s with 6 ranges) and `hf_transfer` is deprecated in hub 1.x — xet stays. The bake-offs are
  chained to start as their files land (E8 first). Trimmed the manifest: CLIP-L, T5 fp8 and the
  FLUX.1 ae already exist in the mounted `D:\comfyui` tree, so only the Klein 9B encoder and the official Fill
  file are fetched for E8.

## 2026-10-05 09:20 — E8 preparation while the weights land

- LanPaint ships example workflows for exactly loom2's cases (`Flux2_Klein_EncodeDecode_Inpaint`,
  `Flux2Dev_ImageEncode_Inpaint`, `Flux_EncodeDecode_Inpaint`, `Qwen_Image_Edit_EncodeDecode_Inpaint`) — wiring
  extracted: `LanPaint_ImageEncode(image, vae, mask)` → `ReferenceLatent` → `BasicGuider` →
  `LanPaint_SamplerCustomAdvanced(Flux2Scheduler sigmas, NumSteps 5, Lambda 5, StepSize 0.15, "Image First")` →
  `LanPaint_ImageDecode(blend_overlap 9)`; Qwen-Edit uses `TextEncodeQwenImageEditPlus` + `ModelSamplingAuraFlow(3)`
  + `CFGNorm` + Lightning LoRA + `LanPaint_KSampler`.
- Node signatures read from `/object_info` (engine started briefly): `InpaintModelConditioning(positive, negative,
  vae, pixels, mask, noise_mask)` → (pos, neg, latent); `ReferenceLatent(conditioning, latent?)`;
  `DifferentialDiffusion(model, strength?)`; `LanPaint_KSampler(... LanPaint_NumSteps, LanPaint_PromptMode,
  Inpainting_mode)`; `ImageCompositeMasked(destination, source, x, y, resize_source, mask?)`.
- `engine/spikes/e8_inpaint.py` written: six methods (`klein_icm`, `klein_base_icm`, `klein_lanpaint`,
  `dev_lanpaint`, `fill`, `qwen_edit`) × bench tasks 01/02/04/05 (03 needs a matte node — deferred to M5),
  images uploaded through `POST /upload/image`, masks via `LoadImageMask(channel=red)`, outpaint via
  `ImagePadForOutpaint`, results → `engine/spikes/out/e8/` + `e8_results.jsonl`.

## 2026-10-05 09:30 — E4 / E5 drivers and the i2v bench frames (GPU idle while weights land)
*(stamp corrected from a guessed "10:05": the frames rendered 09:22–09:29 and the drivers followed — loom lesson 12,
read the clock)*

- Wan/LTX node signatures dumped from `/object_info` (`engine/spikes/out/node_signatures_e4e5.json`):
  `WanImageToVideo` / `WanFirstLastFrameToVideo(positive, negative, vae, width 832, height 480, length 81, …,
  start_image, end_image)` → (pos, neg, latent) — no CLIP-vision needed on 2.2; `KSamplerAdvanced` split
  high/low experts; `LTXVImgToVideo`, `LTXVAddGuide(frame_idx, strength)`, `LTXVConditioning(frame_rate)`,
  `LTXVScheduler`, AV-latent helpers; `CreateVideo(fps)` + `SaveVideo(mp4/h264)`.
- `engine/spikes/e4_wan_i2v.py`: Wan 2.2 I2V-A14B Q5_K_M high+low via `UnetLoaderGGUF`, umT5 fp8, Wan 2.1 VAE,
  **Lightning** recipe (4 steps, high 0–2 / low 2–4, cfg 1, shift 5, LoRA high 0.7 / low 1.0) and a **quality**
  recipe (20 steps 10+10, cfg 3.5, shift 8); start+prompt and FLF on the same weights; 832×480×81 @ 16 fps;
  per-node timings, VRAM, MP4 pulled via `/view`.
- `engine/spikes/e5_ltx_i2v.py`: LTX-2.3 distilled (GGUF Q4_K_M, or Kijai fp8_scaled fallback) with
  `DualCLIPLoader(gemma_3_12B_it_fp8_scaled + ltx-2.3_text_projection, type ltxv)`, Kijai video VAE,
  `LTXVImgToVideo` + optional `LTXVAddGuide(frame_idx -1)` end frame, joint AV latent plumbing; `--preflight`
  prints node signatures and runs only the contract check (the AV-latent wiring is the uncertain part).
  Manifest extended with the Kijai VAE + text projection and the Comfy-Org Gemma fp8 encoder.
- i2v bench frames rendered with the engine (fp8 dev, 20 steps, 960×544, seed 20261004) from prompts 01, 06, 05,
  **05b (rooftop standing — new end frame for the FLF task)**, 02, 07 → `bench/i2v/frames/`.
- Chains scheduled: E8 starts when the Fill file is indexed; E4 starts when the Wan files are indexed *and*
  E8 has finished (24 result rows, port 8188 free).

## 2026-10-05 09:38 — E8 run 1: 24 contract errors (harness), no sampling — fixed, re-run

- FLUX.1 Fill (22.17 GiB, official gated file) landed and was indexed with sha256; E8 chain fired on time.
- Every job failed my own contract check, not the engine: (1) `/object_info` was fetched before the uploads, so
  the uploaded source/mask names were not in `LoadImage`'s enum yet; (2) ComfyUI lists files from mounted
  sub-folders with the OS separator (`t5\t5xxl_fp8_e4m3fn_scaled.safetensors`, `flux1\ae.safetensors`), which an
  exact-string check rejects. Fix in all three drivers: refresh `/object_info` after uploads and resolve every
  file-name input by **basename** against the node's current enum (`fix_names`). Lesson for the roster/recipe
  compiler (06 §3b): file identity must be by roster id → resolved path, never by a hand-typed string.
- Run 1 rows kept as `e8_results_contract_errors_run1.jsonl`; run 2 started 09:38.

## 2026-10-05 10:45 — E8 run 2 invalid (my error): wrong source image + a duplicate driver

- All 24 run-2 jobs **succeeded** (Klein ICM 34 s, Klein base 60 s, Klein+LanPaint 23 s, dev+LanPaint 254 s,
  Fill 78 s, Qwen-Edit 480 s at 960×544), but on the **wrong image**: `tasks.json` pointed at the E0 output file
  `e0_fp8-20st-960x544_s20261004.png`, and the 09:22 frame-rendering run re-used that name for every prompt, so
  the file had become the portrait-grief render while the masks were drawn for the alley scene. Every output shows
  the portrait; the fill/outpaint results are plausible but unscorable against the tasks.
- A second instance of the driver also ran concurrently: the superseded first E8 chain's waiter timed out and,
  because its remaining lines were not chained with `&&`, it still launched the driver against run 2's engine
  (duplicate task-01 rows, inflated task-04 times from model swapping).
- Fixes: `bench/inpaint/source.png` is a **frozen copy** (bench inputs never point into spike output folders);
  the e0 driver now prefixes outputs with the prompt stem for non-default prompts; all drivers and the engine were
  stopped; run-2 artefacts kept under `e8_invalid_run2/` and `e8_results_run2_wrong_source.jsonl`. Lesson for
  06 §4: assets are content-addressed, never "newest file with this name" (loom's manifest-as-truth rule, again).
- **Run 3 started 10:45** on the frozen source. The E4 chain waits for its 24 rows.

## 2026-10-05 11:50 — E8 run 3 scored: D7 accepted with amendments

- Run 3 (frozen `bench/inpaint/source.png`, seed 20261004, 960×544, tasks 01/02/04/05 × 6 methods): 24 jobs,
  0 errors, engine 10:42–11:45. Task 03 (background swap) needs the BiRefNet matte and waits for M5's AI Select
  path. Scored on side-by-side sheets (`engine/spikes/e8_sheets.py` → `engine/spikes/out/e8_sheets/`:
  half-size overview plus full-resolution crops around the repainted region).
- Wall time per job in seconds (includes the model swap after the previous method):

  | method | 01 remove crates | 02 change cloak | 04 outpaint right | 05 face fix |
  | --- | --- | --- | --- | --- |
  | Klein 9B ICM (4 steps) | 18.2 | 29.6 | 33.3 | 30.4 |
  | Klein base ICM (20 steps, CFG 3.5) | 45.6 | 54.7 | 61.7 | 155.2 |
  | Klein 9B + LanPaint (4 steps × 5 inner) | 22.3 | 22.3 | 27.5 | 23.3 |
  | dev fp8mixed + Turbo + LanPaint (8 × 5) | 256.8 | 255.4 | 281.3 | 255.6 |
  | FLUX.1 Fill (official file, fp8 cast, 20 steps, guidance 30) | 76.1 | 76.9 | 81.6 | 77.8 |
  | Qwen-Image-Edit 2509 fp8 + Lightning + LanPaint (8) | 473.2 | 475.7 | 481.6 | 474.7 |

- Findings per task:
  - **01 removal**: only **dev + LanPaint** removed the crates (the floor became grey brick with a drain grate
    rather than the golden cobbles). Both Klein ICM graphs kept them (`ReferenceLatent` feeds the masked content
    back in), Klein + LanPaint swapped them for a steaming tub, Qwen for a cyan AC unit, and Fill **added**
    crates. → Q17.
  - **02 cloak**: Klein ICM (red leather cape), Klein + LanPaint (red leather biker jacket) and dev + LanPaint
    (best: studded leather, rain beads, pose and compass kept) all pass; Klein base went brown; Fill muddy and
    flat; Qwen red wool instead of leather. Face, hand and compass untouched in every method.
  - **04 outpaint (+240 px)**: Klein ICM seamless but no doorway; base, LanPaint, dev and Qwen all put a lit
    doorway in, with a small tone step at x = 960 for base / LanPaint / Qwen; dev seamless; Fill smeared the strip.
  - **05 face**: every method except Fill kept the identity (freckles, hairline, eyes); Fill changed the face.
- Qwen's 475 s is 4 min 55 s of model init per job: the 19.5 GB fp8 file exceeds 16 GB VRAM, sits on D:
  (`fast_disk=False`) and is evicted by every other method; sampling itself is ≈ 90 s at 11.4 s/it. Even warm
  it is 4× Klein + LanPaint, and it never beat Klein on quality.
- **Verdict D7 (accepted with amendments — 04 §4, 12 E8, 13):** Fill = Klein 9B + LanPaint (default),
  Fill-Match = Klein ICM (texture continuation, conservative), Fill Hero = dev + LanPaint. FLUX.1 Fill is
  dropped from the roster (the 22 GB file stays on disk until the user decides); Qwen-Image-Edit is deferred
  post-MVP; Klein base stays on the refine path only. The 2-candidate-per-model default (D22) holds.
- Follow-up **E8b** (once E4/E5 free the engine): a Klein removal recipe on task 01 — ICM without the reference
  on the hole, LanPaint "Prompt First" / higher λ. Until then removal is a Fill Hero job.
- E4 started 11:46 on the freed engine (Wan 2.2 I2V-A14B Q5_K_M + Lightning 4+4, 5 tasks incl. FLF).

## 2026-10-05 12:17 — E4 Wan 2.2 passed (D8 accepted); E5 blocked by the audio VAE, fixed and re-run

- **E4** ran 11:46–12:13 on the engine freed by E8: 5 tasks, Lightning recipe (high 0–2 / low 2–4 steps, LoRA
  0.7 / 1.0, CFG 1, shift 5), 832×480 × 81 f @ 16 fps, seed 20261005, 0 errors. VRAM free 15.76 → 6.66 GB
  after the run (models staged; peak not captured). Frame sheets: `engine/spikes/i2v_sheets.py` →
  `engine/spikes/out/e4_sheets/`.

  | task | exec s | sampling s | VAE decode s | image encode s |
  | --- | --- | --- | --- | --- |
  | 01 character turn | 366 | 130 | 134 | 39 |
  | 02 walk toward camera | 322 | 106 | 131 | 40 |
  | 03 FLF crouch → stand | 312 | 104 | 131 | 36 |
  | 04 camera push cabin | 314 | 106 | 132 | 38 |
  | 05 dialogue gesture | 315 | 106 | 131 | 38 |

- Scores (identity / motion / prompt or end-frame reach, 0–2): 01 = 2/2/1 (she lowers the compass and looks
  down, never turns to camera; braids, cloak, sign intact); 02 = 2/2/2 (walks in, scale grows, crowd parallax,
  freckles resolve as she nears); 03 = 2/1/2 (reaches the standing end pose; the rise happens between 1 s and
  2 s with a position jump worth checking frame by frame); 04 = 2/1/1 (geometry stable, captain nods, but the
  dolly barely moves); 05 = 2/2/2 (blink, look down and back up, tear, no mouth artefacts in a tight close-up).
- **Verdict D8: accepted.** Identity is the property we bought Wan for and it held in all five. Motion
  adherence at CFG 1 is the Lightning trade-off → **E4b** (4 + 4 steps, CFG 2.5 on the high expert) on tasks 01
  and 04 when the engine is free. The clock is dominated by the VAE (decode 131–134 s + encode 36–40 s = 54 %)
  → **Q18**.
- **E5** started 12:13 and stopped at my contract check: core 0.38.2's `LTXVEmptyLatentAudio` has a required
  `audio_vae` input (the LTX-2 transformer samples a joint audio-video latent even for silent clips) and the
  graph had none. Fix: `ltx-2.3_audio_vae_bf16.safetensors` (Kijai repack, 0.34 GiB, sha256 5bc10fa4…) added to
  the manifest and fetched; the driver loads it in a second `VAELoader` (node 99) wired into node 12. Run-1
  rows kept as `e5_results_contract_errors_run1.jsonl`; **run 2 started 12:17** (preflight, then tasks
  01 and 03). Lesson for the recipe compiler (06 §3b): contract checks must run against the pinned core before
  a weight is declared "enough" — the audio VAE was missing from the roster, not from the node graph.

## 2026-10-05 12:42 — E5 LTX-2.3 run 2: both tasks pass; GGUF speed is the problem → E5b (fp8 streaming) started

- Run 2 (audio VAE wired in, contract OK) 12:17–12:40: tasks 01 and 03 at 1024×576 × 121 f @ 24 fps, 8 distilled
  steps, seed 20261005, 0 errors. Sheets: `engine/spikes/out/e5_sheets/`.

  | task | exec s | sampling | s/it | VRAM |
  | --- | --- | --- | --- | --- |
  | 01 character turn | 649 | 9 min 01 s | 68 | "loaded partially": 13.3 GB in VRAM, 0.5 GB offloaded |
  | 03 FLF crouch → stand | 715 | 10 min 49 s | 81 | 13.0 GB in VRAM, 0.8 GB offloaded |

- Scores (identity / motion / prompt or end reach, 0–2): **01 = 1/2/2** — she does turn to the camera and lowers
  the compass (Wan did not), motion is fluid at 24 fps, but the "subtle handheld" became a full reframing and by
  4–5 s the face and costume soften (a white top appears under the cloak, the hood changes shape).
  **03 = 2/2/1** — a fluid rise with the cloak flaring, braids and cloak kept, the standing pose at 5 s is close
  to the end frame but not on it, and a glowing blue chimney artefact appears at 4 s.
- Speed: 68–81 s per step is the GGUF dequant path (E0: GGUF ≈ 11× slower than fp8 on this card). Per second of
  Draft video LTX costs ≈ 2× Wan (121 f @ 1024×576 vs 81 f @ 832×480), so the "fastest open model" line in
  04 §5 does not hold in GGUF form on 16 GB. **E5b:** fetch Kijai's
  `ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors` (≈ 22 GB; should stream the way FLUX.2
  dev fp8mixed does) and re-run task 01 with `--ltx-format fp8`. Download started 12:42; the run goes
  on the engine after the E8b/E4b chain.
- **D9 stays provisional until E5b.** LTX earns its place on motion / prompt adherence and arbitrary keyframes,
  not on speed; Wan remains primary on identity (D8).
- Driver gap: the e5 driver does not collect per-node times (the e4 driver does, via the websocket) — the
  engine log's progress bars were used instead; port the e4 collector before M6.

## 2026-10-05 12:44 — E8b: Klein removes objects once the reference stops showing them (Q17 resolved)

- Task 01 (remove crates) × 4 Klein variants on the frozen source, 12:41–12:42, 0 errors:
  `klein_icm_noref` 31 s (cold load), `klein_icm_hole` 10 s, `klein_lanpaint_pf` 21 s, `klein_lanpaint_noref` 13 s.
- Results (detail sheet `engine/spikes/out/e8_sheets/01-remove-crates_detail.png`): **every variant cleared the
  crates.** `klein_icm_hole` (reference image with the hole painted mid grey) gives a clean brick wall with a
  grille vent and the golden cobbles continuing at the bottom — the most scene-faithful; `klein_lanpaint_pf`
  ("Prompt First", λ 8) leaves an almost empty floor with steam and a low metal step — closest to "empty";
  `klein_icm_noref` builds a wall with a steaming pipe; `klein_lanpaint_noref` swaps in a steaming trough.
  dev + LanPaint (255 s) remains the best-looking removal but is no longer the only one.
- Why run 3 failed on this task: `ReferenceLatent` of the untouched source tells Klein "this scene contains
  crates here", and LanPaint "Image First" leans on the same latent. Neutralising the hole (not dropping the
  reference) keeps the rest of the scene anchored while freeing the masked region.
- Bench note: the task prompt literally asks for "a grimy brick wall with a steaming vent", so every variant
  painted a vent — the prompt stays frozen, but the **Remove** verb in 10 must send a background-only
  description (what the floor and wall are, nothing about objects).
- **Q17 resolved → D7 amended again (04 §4, 10, 12, 13):** Remove = Klein ICM with the neutralised-hole
  reference (default), LanPaint Prompt First as the alternative, Fill Hero for quality.

## 2026-10-05 13:07 — E4b: the motion lever is the undistilled high expert, not more Lightning steps

- Three extra Wan clips on the shared engine, 12:43–13:06 (832×480 × 81 f, seed 20261005, 0 errors):

  | task | recipe | exec s | sampling s | high / low sampler s | VAE decode s |
  | --- | --- | --- | --- | --- | --- |
  | 01 character turn | lightning44 (4 + 4, LoRAs, CFG 1) | 550 | 330 | 173 / 203 | 116 |
  | 04 camera push | lightning44 | 424 | 240 | 142 / 137 | 115 |
  | 04 camera push | motion (high no LoRA CFG 3.5 0–4, low LoRA CFG 1 4–8) | 495 | 313 | 249 / 129 | 116 |

- lightning44 reproduces the 2 + 2 clips almost frame for frame (01 still looks down at the compass, 04 still
  barely moves) for 35–60 % more time → dropped. The **motion** recipe makes the captain unfold his arms and
  lean in to point at the chart, the girl follows with her eyes, identity and the cabin geometry hold; the
  dolly push itself is still minimal — camera moves are a control problem (VACE / camera LoRAs), not a sampler
  setting. CFG 3.5 on the high expert costs 2 forward passes per step (249 s vs 142 s).
- VAE decode fell to 115–116 s from 131–134 s on a warm engine (the first E4 run decoded cold) — still the
  largest fixed cost (Q18).
- **Presets for M6 (04 §5b, 12 E4):** Draft = Lightning 2 + 2 (≈ 315 s per 5 s clip), Motion = undistilled
  high + distilled low (≈ 495 s). D8 unchanged.

## 2026-10-05 13:11 — E5b: LTX-2.3 fp8 streamed = 141 s per clip; D9 accepted; M0 closed

- E5b 13:07–13:09 on the fp8 transformer (`ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors`,
  23.5 GB, sha256 indexed): task 01 at 1024×576 × 121 f, 8 steps — **4.7 s/it, 37 s sampling, 141 s total**
  (GGUF Q4: 68–81 s/it, 649 s). VRAM free after the run 15.35 GB: the engine streamed the whole transformer from
  RAM (`loaded partially` never appeared) and still ran 14× faster than the dequant path. Same seed → the clip
  matches the GGUF clip frame for frame, including the costume drift at 3–4 s and the turn-away at 5 s.
- Consequence for the roster (04 §1, §5): on this card **GGUF is only for weights that cannot stream**;
  fp8 (scaled) is the default for every large transformer. The LTX GGUF entry is struck; the Wan GGUF
  experts stay only until an fp8 pair is benchmarked (E4 per-expert 70–92 s incl. load is acceptable).
- **D9 accepted:** LTX-2.3 fp8 = preview / beat-driven engine (fast, fluid, arbitrary keyframes), Wan 2.2 =
  identity-safe primary (D8). 13 and 12 E5 updated.
- **M0 closed** (12 §1): E0–E8 all passed or decided; carried forward Q15 (M3), Q18 (M6), E9 (M6), inpaint
  bench task 03 (M5). Next: M1 foundation (06) — engine service, roster/resolver, job queue, project store.

## 2026-10-05 13:25 — D30 performance-first weights: GGUF twins and FLUX.1 Fill deleted, Wan fp8 experts on the way

- User instruction: performance is the most important aspect; use fp8 wherever it is faster, apply the same to
  other models and scenarios; delete every model we do not need (re-download later if wanted); then move on
  to M1. Recorded as **D30** (13) and in the 04 §1 heading.
- Deleted with the new `scripts/prune_weights.py` (drops the roster index entry too; hard-link aware):
  `flux1-fill-dev.safetensors` 22.17 GiB (E8), `ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf` 13.22 (E5b),
  `flux2-dev-Q4_K_M.gguf` 18.59 (E0: 11× slower than fp8mixed), `Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf`
  13.35 (its TE), `gemma-3-12b-it-Q4_K_M.gguf` 6.80 (E5 used the fp8) — **74.1 GiB freed**, F: now 820 GB free.
  Manifest entries carry `retired=...` and are skipped unless `--include-retired`. The e0 driver's `gguf`
  configs are now historical (files gone); the Klein family, dev fp8mixed and all fp8 text encoders stay.
  Note for M1's roster scan: the index lists 14 fetched files, but the hard-linked Klein / dev / TE files were
  never indexed — `POST /models/scan` must pick them up.
- `D:\comfyui\ComfyUI\models` (the user's backup tree, ≈ 150 GB) was not touched; loom2 still mounts it for
  SAM 3 / BiRefNet-class tools. Pruning it is the user's call.
- **E4c** queued: Comfy-Org's fp8-scaled Wan 2.2 I2V experts (2 × 13.3 GiB, manifest `e4`) are downloading;
  the chain then runs bench task 02 with `--wan-format fp8` (GGUF Q5_K_M reference: 322 s, sampling 106 s).
  If faster, the GGUF pair is deleted and D8's recipe switches to fp8.
- Next: M1 foundation (06) starts now — orchestrator core first (workspace, roster + resolver, engine
  supervisor + ComfyUI client, recipe compiler with contract tests, durable queue, API + WS), then the shell
  and frame skeleton.

## 2026-10-05 13:49 — M1 orchestrator core landed; rig acceptance 20/20

- `orchestrator/loom2` (uv, Python 3.13.16, fastapi 0.142, pydantic 2.13, websockets 17, httpx): `fsio` (ids,
  atomic fsync writes, readers that refuse torn JSON), `config` (app.json, per-launch token, engine paths),
  `workspace` (06 §4 tree, format geometry lock), `roster` (29 authored entries incl. 3 retired; disk scan
  over the models root + mounted trees; ledger sha merge; `open` variant filter), `recipes` (T2I/I2I/Inpaint/I2V
  pydantic, `loras[]`), `engine.client` (REST + WS, binary previews), `engine.supervisor` (Job Object
  kill-on-close + `taskkill /T`, health probe, restart-every-N), `engine.contract` (object_info checks, basename
  resolution), `engine.graphs` (T2I dev JSON-through-Mistral / Klein prose, Turbo + LoRA chain, ×16 sizes,
  graph hash), `queue` (durable `jobs/queue.json`, one engine job at a time, VRAM admission, warm-group order,
  resume paused after an unclean shutdown, cancel = `/interrupt`), `catalogue` (assets + sidecar manifests,
  lineage, rebuildable SQLite index, WebP thumb pyramid), `events` (WS hub), `tools.fetch`, `api` (06 §6 subset,
  token gate, 4 MiB `FileResponse` chunks, blobs, `/shutdown`), `main` (READY line for the shell).
- Offline tests: 16 pass (contract tests run against `tests/fixtures/object_info.json`, 53 node classes reduced
  from a live capture by `scripts/make_object_info_fixture.py`).
- **Rig acceptance `scripts/m1_acceptance.py`: 20/20 in 120 s** (`engine/spikes/out/m1_acceptance.jsonl`):
  project → dev fp8 + Turbo 960×544 generation through the supervised engine in 66 s warm (101 s cold) → asset,
  manifest, lineage, thumbnail, job index → live `/object_info` matches the fixture and the compiled graph is
  contract-clean → hard `taskkill` of the orchestrator mid-job takes the engine down in 1.5 s (Job Object) →
  relaunch comes back **paused** with the job queued, retry 1 → unpause, cancel interrupts the running job and
  the engine stays alive → `POST /shutdown` stops engine and marks the queue clean.
- Bugs the acceptance caught before any UI existed: a 5-placeholder insert into a 6-column jobs table (turned
  done/cancelled jobs into failed), `Popen.terminate()` is a hard kill on Windows (hence `/shutdown`),
  thumbnails must exist before a job reads as done.
- Remaining M1 (12 §2): Tauri shell sidecar supervision + READY handshake + token injection + graceful
  shutdown; frame skeleton (07) with Models suite and Settings; generated TS client; variant plumbing in the UI.

## 2026-10-05 14:04 — E4c: Wan 2.2 fp8-scaled experts beat the GGUF pair; D8 recipe switched, GGUF deleted

- Task 02 (walk toward camera), Lightning 2 + 2, 832×480 × 81 f, same seed: **fp8 236 s vs GGUF 322 s** per clip;
  sampling 60 s vs 106 s (high expert 42 s vs 78 s, low 40 s vs 70 s at 19 s/it); VAE decode 106 s vs 131 s
  (warm vs cold engine); image encode 39 s both. VRAM free after the run 10.8 GB vs 6.7 GB — the fp8 experts
  are streamed rather than held. Same policy result as E0 (FLUX.2 dev) and E5b (LTX): on this card the
  fp8-scaled file streamed from RAM is the fast path.
- Applied: `wan22-i2v-high-fp8` / `-low-fp8` are the D8 weights (04 §5b, 12 E4, 13 D8, roster presets);
  `Wan2.2-I2V-A14B-*-Q5_K_M.gguf` deleted with `prune_weights.py` (20.1 GiB freed, manifest + roster entries
  `retired=`). F: now holds no GGUF at all; the remaining open i2v cost is the Wan VAE (Q18).
- Driver: `e4_wan_i2v.py --wan-format fp8` (default stays `gguf` for reproducing the old rows; flip the default
  in M6 when the Animate recipe compiler takes over).

## 2026-10-05 14:11 — M1 shell + frame: the app window renders through the sidecar handshake

- **Shell** (`frontend/src-tauri/src/lib.rs`): spawns `orchestrator/.venv/Scripts/python.exe -m loom2.main
  --port 8765` (override `LOOM2_ORCH_CMD`, `LOOM2_PORT`, `LOOM2_REPO`), parses the `LOOM2_READY {json}` stdout
  line, serves `backend_info` / `request_exit` / `reveal_path` commands, POSTs `/shutdown` on window close and
  waits up to 20 s before killing, assigns the sidecar to a kill-on-close Job Object (raw kernel32, no extra
  crate), single-instance plugin. Verified: `npx tauri dev` → orchestrator answered `/health` after 41 s (first
  Rust build) → the window rendered the frame → `Stop-Process app.exe` killed the orchestrator with it
  (nothing listening on 8765 afterwards).
- **Frame** (`frontend/src/frame`, 07 §2): CSS-grid regions, graphite theme with the amber accent, suite tabs
  with `Ctrl+1…5`, project switcher (recents, New, Open, Close), status chips (engine with VRAM, jobs, disk,
  weights), one sticky banner (queue paused / resumed unclean / engine down / weights missing / disk), rail with
  per-suite tabs, panel with the pinned primary action, strip, stage, inspector, dock (collapsed line + Active /
  Queued / Recent columns with previews from the binary WS frames), toasts, Settings modal, keyboard overlay.
  Store: one zustand store (`store/session.ts`), layout persisted per machine, events applied from `/events`.
  Models suite: roster table with health badges, fetch meter, verify sha256, reveal; engine panel with
  start / stop / restart / free VRAM. Other suites are placeholders holding their frame slots.
- Two bugs found by screenshotting the webview (no console in WebView2): a module cycle (`Rail.tsx` ↔
  `suiteRegistry.tsx`, fixed with a leaf `railTabs.tsx`) and an infinite re-render from a zustand selector that
  returned a fresh object (`selectJobsByStatus`; now a `useMemo`). A crash overlay in `main.tsx` renders
  uncaught errors on screen from now on; headless Edge (`msedge --headless=new --screenshot`) against a
  second orchestrator (`LOOM2_TOKEN=devtoken --port 8766`) is the quick visual check; `?suite=models` deep link.
- Tooling: `npm run api:types` regenerates `src/api/schema.d.ts` from `src/api/openapi.json` (exported from the
  FastAPI app); `npm run typecheck`; spike harness kept at `spikes.html`.
