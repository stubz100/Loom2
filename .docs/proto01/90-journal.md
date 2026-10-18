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

## 2026-10-05 15:22 — M2 Catalogue: backend + suite landed on the 10k synthetic project

- Backend (`loom2/catalogue.py` rewritten, 22 tests): `AssetQuery` (folder, kind, suite, state, model, rating,
  tags any/all, has_document, has_children, aspect, min px, dates, FTS `search`, seed, batch/root/session/
  collection/job), cursor or offset paging with totals, `groups()` via a window function (cover = best-rated),
  `counts()` for the smart folders, `last_session_id()`, `tags()`, trash/restore/purge, bulk patch, collections
  (manual + smart; converting a smart one freezes its members), `lineage_tree()`, stale-index detection
  (an index without `root_id` is dropped and rebuilt from the sidecars — found when the dev orchestrator opened
  the M1 acceptance project). API: typed `/assets` + `/assets/groups`, `/assets/counts|tags|bulk|trash|
  restore|purge`, `/collections` CRUD, folder import with `tools/pngmeta.py` (ComfyUI `prompt` chunk → longest
  CLIPTextEncode text, seed, steps, model; A1111 `parameters`).
- Frontend (`suites/catalogue`): zustand store with paged flat mode and lazily loaded groups, selection
  (single / Ctrl / Shift range over the visual order), tile zoom 96–512 with fit/fill, loupe and compare in the
  store (deep links `?loupe=` / `?compare=a,b` / `?group=` for screenshots), two-step Delete with Undo
  (trash → restore), live events. Grid: TanStack Virtual rows keyed by content and measured — the first cut
  cached the "loading…" row estimate for rows that later became tiles and everything overlapped.
- Synthetic project: `scripts/make_synthetic_assets.py` → 10 000 assets with sidecars, index and thumbs in
  229 s (2 612 batches, 12 sessions, 15 % derived). Query timings on it: groups 0.06 s, first page 0.05 s,
  counts 0.06 s, FTS "harbour market" 0.04 s (123 hits).
- Verified by screenshot (headless Edge): batch and flat grids, loupe with inspector, 2-up compare with wipe.
  Not yet verified interactively: keyboard-by-row, scroll FPS, OS pickers — next pass in the real window.

## 2026-10-05 16:08 — M3 Generate: dev wired end to end; bench and acceptance on the rig

- Backend (`recipes.py`, `engine/graphs.py`, queue + API; 28 tests): `prompt_mode` tree / json / text,
  `serialize_prompt` (compact JSON for dev, prose for Klein, text verbatim), `effective_params` (what runs is what
  the UI shows: distilled steps/CFG fixed, negatives only on base, sampler/scheduler from the allowed lists,
  ×16 sizes, 64 px – 4 MP), references fitted to ≤ `ref_max_px`², uploaded, `/object_info` refreshed, chained
  through `ReferenceLatent`; staged jobs + `/queue/release`; `estimate_seconds` from the project's history or the
  spike baselines; `/recipes/preview`, `/project/presets`, `/snippets`.
- Frontend (`suites/generate`): the Catalogue store is now a factory — Generate's results live on a second
  instance read through `CatalogueStoreCtx`, so grid, loupe, compare and inspector are shared code. Panel tabs
  per 09 §3; the pinned primary action is a component (`SuiteDef.PrimaryAction`) so the frame can show
  "Generate N", Stage, the ETA line and the disabled reason.
- **10-prompt JSON bench on dev Turbo (960×544, seed 20261005) through the API** — `engine/spikes/out/m3_bench_dev_turbo.jsonl`:

  | prompt | status | wall s | words |
  | --- | --- | --- | --- |
  | 01-alley-rain | done | 63.5 | 183 |
  | 02-captain-cabin | done | 43.3 | 189 |
  | 03-cliff-chase | done | 43.4 | 156 |
  | 04-wanted-poster | done | 43.9 | 164 |
  | 05-rooftop-night | done | 43.4 | 173 |
  | 06-fish-market | done | 43.2 | 181 |
  | 07-portrait-grief | done | 43.2 | 147 |
  | 08-storm-deck | done | 43.4 | 198 |
  | 09-lighthouse-map | done | 43.0 | 202 |
  | 10-dawn-departure | done | 43.0 | 183 |

  10/10 done, mean 45.3 s per image (engine warm after the first). The first alley-rain image
  was checked in the loupe: the braided woman, green cloak, compass, "MARLOW & SONS" sign, cyan neon, crates and
  harbour cranes are all there; adherence scoring per field is still to be done by eye (04 §6).
- **Acceptance `scripts/m3_acceptance.py`: 17/17 in 521.2 s** (47–59 s at 640×352 Turbo; reference job: done 55.7 s ).
  Every check passed: preview rules, staged → released, hard kill mid-batch, paused resume, 8 assets with seeds / recipe / serialised prompt / graph hash, batch grouping, reference-image job with lineage.

## 2026-10-05 16:09 — M3 bench adherence by eye; reference editing on dev confirmed

- Contact sheet of the 10 dev Turbo bench images (seed 20261005, 960×544): the character is consistent across
  all ten (red braids, pale freckles, dark green hooded cloak); scene, lighting and camera fields land in
  every frame; literal text renders correctly ("MARLOW & SONS", "HARBOUR MARKET", "WANTED … REWARD 200
  CROWNS", the red X on the lighthouse map); palette colours show where bound to objects (cyan neon, amber
  lamps). Weakest: 05 rooftop (crouch pose generic), 08 storm deck (lightning dominates the composition).
  No failures — Turbo 8-step is a usable Draft tier for dev (D29 holds).
- Reference job (acceptance step 5): "the same captain's cabin as reference image 1, but at night with the lamp
  as the only light" → identical cabin layout, both characters, map and clock preserved; lighting changed as
  asked. FLUX.2 dev reference editing through `ReferenceLatent` works at one reference; multi-reference and
  Klein 9B-KV are M5.
- 09 §10 "adherence recorded" is therefore done qualitatively; a per-field score table can follow when the
  Catalogue's compare view is used for a second seed.

## 2026-10-05 16:24 — Catalogue "expand all" on 10k: thousands of fetches → lazy group loading (user report)

- The user expanded all groups on the 10k project and got a wall of `TypeError: Failed to fetch`: `expandAll`
  fired one `/assets` fetch per group (2 612 at once); the browser dropped connections and every rejected
  promise hit the crash overlay. Fix: groups load only when their placeholder row scrolls into view (the
  virtualiser's visible range), at most 6 fetches in flight (`limited()` in the store), failures are recorded
  per group with a "retry" on the row and one line in the strip instead of an overlay.
- Found while verifying: single-image batches have no `batch_id`, so the header key fell back to `job_id` and
  the item request (`batch_id=<job_id>`) returned nothing — expanded groups looked empty. The item query now
  takes `group_by` + `group_key` and filters on the same `COALESCE(...)` expression the headers use (test added).
- Cosmetic: dev headers showed the raw JSON as excerpt; the scene field is shown instead.

## 2026-10-05 18:44 — M4 slice 2: the PixiJS editor; exact blend modes measured against the Python flatten

- **Edit suite is live** (`frontend/src/suites/edit/`): toolbox + tool options in the Panel (V M L W B E G I C H Z;
  A is an M5 placeholder), Brushes / Selection / AI (placeholder) / Documents panels, strip (zoom, fit, 1:1,
  pixel grid, mask overlay, before, quick mask, cursor, renderer badge), PixiJS stage, inspector with Layers
  (tree, eye/lock/solo, mask thumbnails, blend/opacity/fill/clip, add layer/group/adjustment/filter, duplicate,
  merge down, reorder, delete-twice), Properties (position, lineage, adjustment/filter parameters with sliders),
  History (tile snapshots for strokes, stack snapshots for structure; click to step), Info (size, source, memory,
  renderer, cursor, **compare preview vs exact**). Save (dirty layers only, raw RGBA) · Save to Catalogue
  (lineage) · Export PNG (orchestrator) / PSD (ag-psd, adjustment layers skipped with a warning). `E` in the
  Catalogue opens the asset's document (or creates it). Keys per 10 §10; `Ctrl+0/1/2` zoom wins over the suite
  switch while a document is open (capture-phase listener). Autosave every 2 min; unsaved-changes toast on
  suite switch. Deep links `?doc=<id>&verify=1` for the headless loop.
- **Toolbox lives at the top of the Tool options panel**, not in the frame Rail: 07 §2 makes the Rail the
  suite's section navigation, and that stays consistent across suites.
- **Blend modes: PixiJS's advanced set is not the Photoshop/W3C set.** Measured per mode on a 960×544 gradient
  layer over an opaque base (RGB p99 in 1/255): only normal/multiply/screen matched; darken 55, soft-light 30,
  hard-light 85, linear-light 145, hard-mix 165, hue 72, luminosity 53 … Pixi's filters use looser formulas (the
  Pegtop soft-light, premultiplied colours treated as straight, backdrop alpha ignored) and batch adjacent layers
  with the same mode into one pass. Replaced by `blendModes.ts`: 24 `BlendModeFilter` subclasses (GLSL + WGSL)
  porting compose.py's formulas, registered as `w3c-<mode>[-clip][-b]`; `-clip` multiplies the layer alpha by
  the backdrop alpha (clipping = alpha × everything below), `-b` alternates names so equal modes never batch.
  The filter emits only the source-side term (cs·(1−αb) + B·αb)·αs with alpha αs because Pixi draws the filter
  output over the backdrop with source-over — emitting the full W3C `co` double-counted the backdrop wherever it
  was semi-transparent (found through "two blended layers inside an isolated group" failing while one passed).
- **Masks and isolated groups go through render-texture passes**, not Pixi's sprite masks / `cacheAsTexture`:
  a sprite mask plus an advanced blend gave the blend a transparent backdrop (mask + multiply p99 57), and
  cacheAsTexture applied alpha/blend per child. Each masked layer renders (layer-sized RT) and each isolated
  group renders (document-sized RT, transparent clear) in a HIGH-priority ticker step when dirty; the result
  sprite carries the blend/opacity/mask. Pass-through is exactly compose.py's rule (flag ∧ normal ∧ no mask ∧
  opacity 1 ∧ no clip).
- **Result (`scripts/m4_acceptance.py`, 12/12 in ≈ 25 s):** document from asset; 25 layers in 5 groups with every
  mode, 6 masks, clips, opacities/fills, offsets; 52 MB raw upload 0.8 s; ORA save 2.2 s; reopen lossless
  (stack, pixels, masks); 37-entry ORA with mimetype first; flatten → asset with parents + `has_document`;
  **GPU preview vs exact flatten: RGB mean 0.63, p99 3, max 24 (1/255)** over the 25-layer stack with 8-bit
  intermediates — threshold p99 ≤ 4. Per feature (`m4_compositor_diag.py`): opacity, fill, offsets, masks
  (linked/unlinked), clip (over holes, in groups), pass-through and isolated groups (alpha, blend, mask, nested,
  offsets), stacked equal modes, and all 24 deterministic modes are **p99 ≤ 1** (divide ≤ 4 — 8-bit division
  noise; hard-mix max 193 at its threshold flip; dissolve is noise by design and excluded).
- Found on the way: FastAPI's CORS needed `expose_headers` for the raw-pixel size headers (the browser read 0×0);
  `extract.canvas()` returns a WebGPU canvas without a 2D context (redrawn into a plain canvas, which also
  un-premultiplies); `renderer.render({target})` clears to the renderer background unless `clearColor` is given;
  headless Edge renders with **WebGPU**, so both shader dialects are exercised by the acceptance.
- Still in M4: adjustment/filter GPU previews (slice 4; the canvas shows the stack without them, exact on save),
  free transform, gradient fill, marching ants (the selection shows as an additive tint), pen pressure (D19).
  Roadmap 12 §5 and 13 D31 updated.

## 2026-10-05 18:56 — M4 slice 4: adjustment and filter layer previews on the GPU, measured exact

- `adjustFilters.ts`: one PixiJS `Filter` per adjustment/filter layer, registered as a blend mode
  (`adj-<layerId>`) and driven by a document-sized white sprite (or the layer's mask) carrying the layer alpha;
  the filter reads the backdrop (`uBackTexture`), draws with blend **none** and writes compose.py's mix:
  adjustments `cb·(1−a) + f(cb)·a` where αb > 0, filters a straight-alpha mix of rgb and alpha. Per-channel
  types (levels, curves, exposure, brightness/contrast, invert) are evaluated on the CPU into a 256-entry LUT
  texture with the exact formulas; hue/saturation (the same HSL round trip), colour balance and black & white
  run in the shader; blur/sharpen/high-pass sample compose.py's Gaussian (σ = radius, taps to 3σ) over the
  premultiplied backdrop with `uInputClamp` edge clamping, strided beyond a 12-tap radius; noise is a
  hash-driven Box–Muller approximation of the seeded normal noise. Parameters are uniforms updated in place on
  every slider move (no shader recompiles); clip multiplies by the backdrop alpha; masks on any node kind load
  now (they were fetched for raster layers only — found by the masked-levels variant).
- Measured (`m4_compositor_diag.py adjust`, RGB p99 in 1/255): levels 0, curves 1, hue/saturation 1, colour
  balance 1, brightness/contrast 0, exposure 0, black & white 1, invert 0, masked levels at 50 % 1, clip over a
  hole 1, over a layer with holes 1, inside an isolated group 1; blur 1.5 → 1, blur 3 → 1, blur 8 (strided) → 1
  (max 6), sharpen 0, high-pass 1; noise ≈ by design (p99 90).
- **Acceptance 12/12** with the stack grown to 33 layers + 8 adjustment/filter nodes (39 nodes, 38-entry ORA):
  preview vs exact **mean 0.70, p99 3, max 32** (1/255). 10 §3, 12 §5 and D31 updated; the "preview ≈" badge now
  means noise, large blur radii and dissolve only.
- Cost note: Pixi's ticker renders every frame, so a blur layer's 169–625 taps per pixel run continuously; an
  on-demand render loop (render on change / paint only) is the next editor housekeeping item (12 §5).

## 2026-10-05 19:47 — UI operating rule (D32): command registry, right-click menus, icon toolbars, palette

- The user, after trying M4: keyboard shortcuts are welcome, but *everything* must be reachable by icons or a
  right-click menu. Audit of the UI as it stood: no right-click menus anywhere; Catalogue verbs only as text
  buttons in the Inspector; select all / clear / grouping cycle, loupe prev/next, Compare swap key-only; Edit
  undo/redo, clear selected pixels, group active layer, zoom in/out/200 % key-only; rename, solo, mask toggle,
  add/subtract selection gesture-only; focus mode and the dock toggle without an icon.
- **Built one mechanism rather than patching buttons in:** `frame/commands.ts` is a registry where every action
  is a `Command` (label, icon, shortcut, enabled predicate, and a **non-empty** list of mouse placements — a
  keyboard-only command does not type-check). `handleKeyFor(scope, e)` turns keys into accelerators for those
  commands; `CommandButton`/`CommandRow`/`MenuButton` render them as icon buttons with label + shortcut
  tooltips; `ContextMenu.tsx` renders any list of commands (or ad-hoc entries, separators, submenus, checks)
  at the pointer with ↑↓→←/Enter/Esc; the `?` overlay and the new `Ctrl+K` palette are generated from the
  registry; `Shift+F10` / the Menu key re-dispatch a context-menu event at the focused element; the dev build
  logs commands no menu or toolbar has rendered.
- Right-click menus: Catalogue tiles (loupe, edit, keep/reject/clear, rate ▸, tag, reference, re-run, variations,
  animate, pin/compare, reveal, trash/restore/purge), group headers, empty grid space (select all/none, group
  by ▸, expand/collapse, search), the loupe (same as tiles, plus ◀ ▶ buttons and a keep/reject/edit/reference
  row), Generate reference slots (remove, move, clear all), Edit layer rows (rename, hide/show, solo, lock,
  duplicate, merge, group, reorder, mask ▸, delete), the Edit canvas (undo/redo + Selection / Layer / View /
  Tool / Document submenus, selection items inline while a selection exists) and Dock job rows (cancel, run
  now, remove, copy id / recipe). Icon rows: the Catalogue strip's selection bar (keep/reject/clear, loupe,
  edit, reference, pin, select all/none, trash) with expand/collapse and tile-size icons; Edit strip (undo,
  redo, zoom −/+, fit, 100 %); Layers toolbar (new, group, group active, adjustment ▸, filter ▸, duplicate,
  merge, up/down, mask, hide/show, lock, delete, More ▸); brush size/hardness and colour swap/default buttons;
  Rail gets focus-mode and dock icons; the app menu lists palette, focus mode and dock.
- Verified in headless Edge with new dev deep links (`&ctx=<selector>` opens that element's menu, `&help=1`,
  `&palette=1`, `&menu=1`): tile menu, layer menu, canvas menu, help overlay, palette, loupe. Two findings on
  the way: headless Edge fires `blur`/`resize` on capture, so menus no longer close on those (pointer-down
  outside, wheel, Esc remain); and the loupe had a **re-render loop** (an unmemoised `{w,h}` recreated `fit`,
  whose mount effect set state) that hung the page — fixed with `useMemo` in both the loupe and Compare.
- Docs: 07 §3c (rule + registry + menu inventory), 07 §4 (`Shift+F10`, `Ctrl+K` built), 08 §6, 09 §8, 10 §10,
  12 §10 (standing rule), 13 D32. Lint: warnings only (pre-existing fast-refresh and purity notes).

## 2026-10-05 21:45 — M4 closed: free transform, marching ants, on-demand rendering

- **On-demand rendering** (10 §11): the Pixi application starts with `autoStart: false`; `requestRender()`
  schedules one frame on the next animation frame after a change (stroke, view, stack, transform, ants tick,
  host resize via a ResizeObserver). Nothing renders while idle, so adjustment/filter shaders cost nothing
  between edits. The acceptance still passes (12/12, preview vs exact p99 4/255 on the 39-node stack).
- **Marching ants** (10 §3): the selection's boundary is traced on the CPU as axis-aligned runs (two passes over
  the selection canvas, recomputed only when the selection changes) and drawn as a 1-px white line with black
  dashes whose phase advances every 120 ms while a selection exists; width follows the zoom. The orange tint is
  gone; quick mask keeps its red overlay.
- **Free transform** (10 §4, `Ctrl+T`): `transform.ts` holds the centre / scale / rotation model and the
  resampler; the preview applies the same numbers to the layer's sprite (or its mask pass); the box has 8 scale
  handles (Shift keeps the ratio), drag inside moves, drag outside rotates (Shift snaps 15°); Enter or a
  double-click bakes the transform through a high-quality Canvas2D resample into a new layer canvas (bounds
  recomputed, linked masks resampled with it), Esc cancels. Flip horizontal/vertical and rotate 90°/180° use the
  same path. Undo swaps the old canvases back (a new `swap` field on history entries), so a transform is one
  step like everything else. All of it is in the Move tool options, the strip (while transforming), the layer
  and canvas menus, and the palette (D32).
- Loupe facts bar wraps instead of clipping; strip labels no longer wrap. Verified in headless Edge with the dev
  deep links `&sel=half` (ants) and `&xform=1` (box).
- **M4 is closed**: 10 §14 items 1, 6 and 7 pass by script; item 2's undo/redo is instant across strokes and the
  pen-latency half waits for a tablet (D19). 12 §5 updated. Next: M5 Edit AI (inpaint / refine / segment on the
  E8 recipes; gradient fill arrives with it per 10 §4).

## 2026-10-05 22:20 — M5 slice 1: inpaint / refine / outpaint / upscale through the editor (written up 06-10 06:54)

- **Backend:** `edit_ai.py` (region planning: mask bbox + margin %, multiples of 16, auto-upscale to ≥ min
  working size, crop/scale of the exact composite + mask, outpaint edge-padding with an inner blend band,
  paste-back as a layer whose alpha is the feathered mask); recipes `Inpaint` (fill · fill_match · fill_hero ·
  remove · outpaint), `I2I` (refine on visible / active / selection) and `Upscale`; `graphs.py` ports the E8
  graphs (LanPaint ImageEncode → ReferenceLatent → BasicGuider → Flux2Scheduler → LanPaint sampler → ImageDecode;
  ICM = InpaintModelConditioning + ReferenceLatent + DifferentialDiffusion, hole variant for Remove; dev + Turbo for
  Fill Hero; partial-denoise KSampler for refine; UpscaleModelLoader for ESRGAN); the queue prepares the inputs
  from the saved document (uploads through `/upload/image`, refreshes object_info), runs the job and adds the
  result as a layer in a per-batch "AI" group (first candidate visible, recipe + seed + region on the layer) and
  saves the ORA; `PUT /documents/{id}/selection`, `POST /documents/{id}/ai`; Real-ESRGAN ×2/×4 in the roster and
  fetched (BSD-3). 46 tests.
- **Frontend:** AI panel (Inpaint / Refine / Upscale / Outpaint with the 10 §4 controls, candidates, seed), run =
  save → upload selection → job; `document.changed {added}` merges the server stack and fetches the new layers
  (undo keeps working: local canvases stay); candidate strip over the canvas (hover previews, 1–4 / Enter pick,
  keep all), resumed when a document reopens with an unpicked AI group; Properties → **Re-run (new seed)**.
- **First rig run** (`scripts/m5_acceptance.py`, bench source + masks, 2 candidates): Fill (Klein + LanPaint) on
  the crates **removed them seamlessly** (70 s cold incl. model load, 38 s warm); Fill-Match (ICM) 88 s, Remove
  (ICM hole) 130 s — both slower than E8's 18–33 s; the first cloak candidate took **548 s** with "Model
  Initializing 2 min 23 s" and the model *staged for dynamic VRAM loading* (streamed from RAM), and the second
  candidate hit a **GPU driver reset** (next entry).

## 2026-10-06 06:54 — GPU driver TDR during the M5 run: cause and fixes

- Windows: `LiveKernelEvent 141`, bucket `LKD_0x141_Tdr … amdkmdag.sys` at 22:16:54 — the GPU exceeded the
  default 2 s TDR limit (keys unset) and the AMD driver was reset while the engine sampled the second cloak
  candidate (Klein + LanPaint, 1024×880, step 2/4). The engine process kept answering `/history` with a dead GPU,
  so the orchestrator polled for 3 min; earlier `Kernel_141` dumps on 10-02 and 10-04 predate loom2's engine work.
- Cause: VRAM pressure building across consecutive Klein jobs (job times 59 → 37 → 87 → 129 → 548 s at the same
  size class; ComfyUI switched the 9 GB fp8 model to "8658 MB staged" streaming) — alternating LanPaint and ICM
  graphs re-patch the model and nothing freed ComfyUI's cached outputs between jobs; regions were upscaled to ≈ 0.9
  MP (E8: 0.5 MP); the engine ran without a VRAM reserve next to the editor's WebGPU canvas.
- Fixes: the user set `TdrDelay`/`TdrDdiDelay` = 60 s; loom2 frees the engine cache after every edit job
  (`/free`, weights resident), gains a **stall watchdog** (`engine.stall_timeout_s` 420: fail the job, restart the
  engine, pause the queue), launches ComfyUI with `--reserve-vram 1.5` (`engine.reserve_vram_gb`), caps inpaint
  engine images at ≈ 1 MP (`max_pixels`, scale reduced until the 16-rounded size fits) and shows the engine size
  in the AI panel. 06 §10 row added.

## 2026-10-06 07:03 — M5 acceptance rerun after the fixes: 13/13

- Same script, same bench, TDR at 60 s, cache freed after each job, `--reserve-vram 1.5`: Fill (Klein + LanPaint)
  crates ×2 in 169 s cold (engine + model load) then **40 s per candidate warm**; Fill-Match **20 s**; Remove **20 s**
  (both back to the E8 numbers — the 88/130 s of the first run were the VRAM thrash); cloak ×2 at 41 s each;
  face 50 s; outpaint right 240 at 32 s (document grew to 1200×544, layers shifted, selection padded); refine
  0.25 on Klein base 45 s; Real-ESRGAN ×2 6 s → Catalogue asset `ast_a5c6f3c5` + 1× detail layer; 19 nodes saved.
  No stall, no watchdog trigger. Contact sheets in `engine/spikes/out/m5/`: crates gone with continuous
  cobbles and wall; cloak → wet red leather jacket, face / hair / compass untouched; face fill keeps freckles and
  eyes; outpaint continues the alley with a lit doorway, no seam at x = 960. 12 §6 status written.

## 2026-10-06 08:29 — Code review of M0–M5 slice 1: bug register (B1–B24)

- Full read of `orchestrator/loom2`, `frontend/src`, the Tauri shell and the scripts against 06/07/10, with the
  offline suite (46 passed), `tsc` (clean) and `oxlint` (warnings only). B1 and B2 were reproduced with probe
  scripts before being recorded; the rest are confirmed at the cited lines. Status column is updated in place as
  fixes land (this entry is the register; fixes get their own entries below).

  **Backend (orchestrator)**

  | Id | Sev | Where | Defect | Status |
  | --- | --- | --- | --- | --- |
  | B1 | critical | `engine/supervisor.py` `start()` → `stop()` | `start()` holds the non-reentrant `asyncio.Lock` and awaits `stop()`, which takes it again: an engine that fails its health probe hangs the queue on "starting engine" forever and `/engine/*` with it | **fixed 08:45** |
  | B2 | high | `queue.py` `stop()` | reads `_running_id` after cancelling the task whose `finally` clears it → the running job is persisted as `running` with `clean_shutdown=true` and reloads as **failed** ("interrupted by shutdown"); `/interrupt` never sent. The unclean path (M1 acceptance) is fine | **fixed 08:45** |
  | B3 | high | `queue.py` `_prepare_document_inputs` / `_add_result_layer` | candidate 1 is inserted *visible* and saved; the next seed of the same batch flattens the document with it included → candidates chain instead of being alternatives (M5 acceptance ran 2 and did not notice) | **fixed 08:45** |
  | B4 | high | `queue.py` `_follow`; `recipes.py` | a hung `/history` poll raises out of `_follow` → `_fail` only (no engine restart, no pause); region preparation has no watchdog and `Inpaint.expand / margin_pct / min_size` are unbounded (`dilate(sel, 10**6)` wedges the worker thread) | **fixed 08:45** |
  | B5 | medium | `queue.py` `cancel` / `_run_one` | cancel while the job is still starting the engine / uploading / preparing → `/interrupt` is a no-op, the job renders to completion, then is marked cancelled and its outputs orphaned | **fixed 08:45** |
  | B6 | medium | `engine/supervisor.py` `_argv`; `queue.py` | engine outputs go to `<state>/engine_out` (06 §4 says `<project>/engine_out`, which is created and unused); nothing reconciles or cleans `engine_out`, `_temp/ai`, `_temp/refs`, `_temp/blobs` | **fixed 09:20** (per-job cleanup 08:45; reconciliation at project open and 06 §4 corrected 09:20) |
  | B7 | medium | `api.py` `PUT /settings` | the live `JobQueue.roster` and `EngineSupervisor.client` keep the old root / port; invalid payloads 500 instead of 422 | **fixed 08:45** |
  | B8 | medium | `api.py` `open_project` / lifespan | `self.ws` is set before the catalogue/queue open; a corrupt `catalogue.sqlite` leaves `GET /project` open while everything else 409s, and at startup only `StateError` is caught so the orchestrator does not start at all | **fixed 08:45** |
  | B9 | medium | `documents.py` `save` | fixed temp name `<doc>.ora.tmp`, no fsync; editor save and queue paste-back can write it concurrently | **fixed 08:45** |
  | B10 | medium | `api.py` `PUT /documents/{id}/selection` | selection size is not checked against the document → shape errors deep in `edit_ai` instead of a 400 | **fixed 08:45** |
  | B11 | low | `events.py`, `catalogue.py`, `compose.py`, `graphs.py` | fire-and-forget WS tasks without references; catalogue closed while a worker thread may still use it; `dissolve` seeded with salted `hash()`; node-id collision at ≥ 10 LoRAs; warm-group starvation; unknown roster ids → 500 | **fixed 09:20** |

  **Editor and catalogue (frontend)**

  | Id | Sev | Where | Defect | Status |
  | --- | --- | --- | --- | --- |
  | B12 | critical | `editorStore.ts` `save()` / `deleteNode` | dirty pixels of a layer deleted from the stack are still uploaded → server 400 "not a raster layer" → save aborts and keeps failing (autosave too); only close/reopen exits, losing the work | **fixed 08:45** |
  | B13 | critical | `catalogueStore.ts` module scope | `loadSeq` is shared by the Catalogue and Generate-results store instances; every `asset.created` discards the Catalogue's reload and leaves it on "loading" with stale tiles | **fixed 08:45** |
  | B14 | high | `editorStore.ts` `save()` | `lp.dirty = false` after the await: strokes finished during the upload are lost; `docDirty: false` set unconditionally | **fixed 08:45** |
  | B15 | high | `editorStore.ts` / `documents.py` | the server drops pixels of layers absent from the PUT stack, the client only re-uploads dirty ones → delete · save · undo · save leaves a raster layer with no pixels in the ORA | **fixed 08:45** |
  | B16 | high | `editorStore.ts` `addMask` | "mask from selection" fills white then draws the selection canvas, which is transparent where unselected → an all-white no-op mask for every marquee / lasso / wand selection | **fixed 08:45** |
  | B17 | high | `EditorCanvas.tsx` eyedropper | `extract.pixels({ frame: {…} as never })` — Pixi needs a `Rectangle` (`copyTo`) → always throws → crash overlay | **fixed 08:45** |
  | B18 | medium | `editorStore.ts` `pickCandidate` / `removeMask` | destroy pixels / masks that the history entry they push still references → undo shows empty layers / an unmasked layer | **fixed 08:45** |
  | B19 | medium | `editorStore.ts` history | `swap` canvases (free transform) are never destroyed when entries leave `history`/`future` or on close; Pixi's cache pins their textures | **fixed 08:45** |
  | B20 | medium | `EditSuite.tsx` `useEditKeys` | autosave interval and the unsaved-changes watcher live in the Edit strip, so they stop on every suite switch — exactly when the toast promises autosave | **fixed 08:45** |
  | B21 | medium | `api/client.ts`, `store/session.ts` | WS reconnect never resyncs (missed `job.updated` / `document.changed`); `init()`'s `refreshAll()` unguarded → crash overlay instead of the Retry banner | **fixed 08:45** |
  | B22 | medium | `catalogueStore.ts` `applyEvent` | grouped mode reloads everything on `asset.created` and wipes the selection | **fixed 08:45** |

  **Shell and repository**

  | Id | Sev | Where | Defect | Status |
  | --- | --- | --- | --- | --- |
  | B23 | high | `.gitignore`, `config.py` | `.loom2_state/` (app.json, ComfyUI user DB + WAL, an engine log) is tracked; every run dirties the tree | **fixed 08:45** |
  | B24 | medium | `src-tauri/src/lib.rs` `shutdown_backend`; `tauri.conf.json` | the `/shutdown` POST has no timeout (Alt-F4 can hang); `csp: null`; port fixed at 8765 with no fallback | **fixed 09:20** (timeout 08:45; CSP + ephemeral port 09:20) |

- Also noted, not bugs: no disk guard / per-job logs / structured logs / engine adapter interface (06 §4, §3d, §9);
  LoRAs compiled only for t2i; `fetch_weights.py` records but never verifies sha256; `prune_weights.py` deletes on a
  bare name match; engine venv has no lockfile; README and 00-README three milestones stale; 13's D table is
  appended newest-first after D28 and the Q table is split. Fix order: B1–B5 with a fake-ComfyUI lifecycle test
  (none exists), then B12–B18, then B23/B24 and the docs.

## 2026-10-06 08:45 — Review fixes B1–B5, B7–B10, B12–B23 landed; fake ComfyUI lifecycle tests

- **Backend.** B1: `EngineSupervisor.stop()` body moved to `_stop_locked()`, which `start()` calls while holding the
  lock; a failed health probe now raises `RuntimeError` and releases the lock (the launch failure path also closes
  the log handle, and `state()["job_object"]` reports the real assignment). B2: `JobQueue.stop()` reads the running
  job *before* cancelling the loop task, re-queues it, sends `/interrupt` if it had been submitted, and persists
  `queued` — a relaunch continues it instead of marking it failed. B3: `OpenDocument.flatten(exclude=…)` drops the
  batch's `grp_<batch>` group while a candidate's inputs are cropped, so candidates are alternatives. B4: a hung or
  refused `/history` poll is caught (30 s), the engine is checked with `_engine_alive()` (process poll or a 10 s
  probe), and the stall timer decides; the poll interval scales with `stall_timeout_s`; region preparation runs under
  a 300 s `wait_for`; every size knob on `Inpaint` / `I2I` is bounded (`expand` ≤ 256, `margin_pct` ≤ 200,
  `min_size` ≤ 4096, `max_pixels` ≤ 4 MP, `outpaint` sides ≤ 4096, `strength` 0–1). B5: `_cancelled()` checkpoints
  after engine start, uploads and region preparation and right before `/prompt`; `cancel()` only interrupts a
  submitted prompt; a cancel racing the submission interrupts what was just queued. B6 (part): `_cleanup_job_files()`
  removes `engine_out/loom2/<job>*` and `_temp/ai/<job>` when a job ends in any state; Upscale results are moved,
  not copied. B7: `PUT /settings` returns 422 on bad payloads, hands the new roster to the live queue and lets the
  supervisor follow a new host/port while no process is alive. B8: `open_project` binds the services only after
  catalogue, queue and documents all opened; the lifespan catches any exception from the last project. B9: ORA
  saves use a unique temp name, fsync, replace, and a per-document lock. B10: `PUT /documents/{id}/selection`
  rejects a selection whose size is not the document's. `PUT /documents/{id}` now answers with `missing_pixels`
  / `missing_masks` (for B15). `_run_one` survives a failed first `persist()` (disk full) by re-queuing and pausing.
- **Tests.** `tests/fake_comfy.py` is a fake ComfyUI (REST + `/ws`, uvicorn on an ephemeral port; behaviours
  success / silent / error; LoadImage's enum grows with uploads; outputs take the uploaded crop's size) that the
  supervisor adopts. `tests/test_lifecycle.py` (8 tests, ≈ 12 s): start failure raises and releases the lock;
  clean stop re-queues + interrupts; t2i end to end with the output moved into the project and `engine_out` empty;
  cancel before submission reaches no `/prompt`; stall → failed + restarted + paused; hung history poll ends in the
  watchdog, not a traceback; two inpaint candidates whose engine inputs contain no trace of each other, one AI group
  with the first visible, `/free(unload_models=false)` after each, no leftovers; recipe bounds. Run against the
  pre-fix code they fail (B1, B2, B3, B5, bounds). `python-multipart` joins the dev extras. **54 passed.**
- **Frontend.** B12/B14/B15: `save()` clears the dirty flags before uploading (an edit during the save re-dirties and
  rides the next one), uploads only layers / masks that are in the stack *and* (dirty or listed by the server as
  missing), restores the flag on failure, and returns a boolean that `runAi` / `saveToCatalogue` / `exportPng` honour.
  B13: `loadSeq` moved into the catalogue store factory. B16: "mask from selection" draws the selection's alpha over
  black. B17: eyedropper passes a `Rectangle`. B18: `pickCandidate` / `removeMask` keep canvases for undo; B19:
  `releaseEntries()` destroys swapped-out transform canvases when history entries drop or the document closes, and
  `gcPixels()` drops canvases no stack (current, undo, redo) refers to. B20: `ensureEditorAutosave()` runs the
  autosave interval and the unsaved-changes toast for the app's lifetime. B21: a reconnect refreshes session state
  and `useEditor.resync()` merges layers added meanwhile; `init()` catches a failing first fetch (Retry banner) and a
  bad WS frame is dropped. B22: event-driven catalogue reloads keep the selection. `tsc` clean; `oxlint` warnings
  unchanged.
- **Shell / repo.** B23: `.loom2_state/` ignored and untracked (`git rm --cached`, staged). B24 (part): the shutdown
  POST has a 5 s global timeout (`cargo check` clean). README status refreshed to M5 slice 1.
- Still open from the register: B11 (low), B6's startup reconciliation and output location, B24's CSP and port
  fallback, and the non-bug notes (disk guard, per-job logs, engine lockfile, sha256 verification in
  `fetch_weights.py`, 13's table order). Not re-run: the rig acceptances (no engine involvement changed in the
  graphs; `scripts/m5_acceptance.py` should be rerun before M5 slice 2 to confirm B3 on real candidates).

## 2026-10-06 09:20 — Review fixes B6 (rest), B11, B24 (rest); CSP verified in headless Edge

- **B6.** `JobQueue.start()` runs `_reconcile_leftovers()`: files under `<state>/engine_out/loom2/` and dirs under
  `<project>/_temp/ai/` that belong to no queued or running job are removed (a crashed run's outputs; the job that was
  running is re-queued by `load()` and renders again). The engine output location stays `<app state>/engine_out`
  (the engine outlives project switches); 06 §3b/§4 now say so, and the project tree lost its unused `engine_out/`.
- **B11.** `EventHub` has one outbound queue and sender task per client — frames arrive in broadcast order, nothing
  is sent concurrently on one socket, a slow client drops *previews* (never state) past 500 pending, and a dead
  client is detached on its first failure; the `/events` hello goes through the same queue. `Catalogue.close()`
  marks the index closed so an ingest finishing on a worker thread after the project closed writes nothing.
  `dissolve` is seeded with `crc32(layer id)` (deterministic across processes). The t2i LoRA chain starts after
  the reference nodes (no collision at ≥ 10 LoRAs). `_next()` ages out warm-group affinity after 10 min
  (`MAX_WARM_SKIP_S`). `submit()` rejects unknown model / LoRA ids (422) before anything starts; `/models/{id}/verify`
  404s and `/recipes/preview` 422s on unknown ids; malformed cursors are 400; `PUT /blobs` writes a unique temp per
  request; thumbnails of transparent sources keep their alpha (WebP RGBA); "today" is the user's local day; the
  source-asset decode in `POST /documents` runs off the event loop.
- **B24.** `tauri.conf.json` sets a `csp` (`default-src 'self'`; loopback `http://127.0.0.1:*` / `ws://` for the
  orchestrator in `connect-src`, `img-src`, `media-src`; `data:`/`blob:` for layer thumbnails and previews;
  `ipc: http://ipc.localhost` for Tauri; `object-src 'none'`, `frame-src 'none'`) and a `devCsp` that only adds
  `'unsafe-inline'` scripts for Vite's React Refresh preamble. COOP/COEP stay unset: nothing uses
  `SharedArrayBuffer` yet (06 §2 names it for the brush worker; set them with that work, CORP on the orchestrator's
  responses included). The shell picks a free loopback port when `LOOM2_PORT` is unset (`pick_port()`); the READY
  line already carried the port. `cargo check` clean.
- **Verification.** `scripts/csp_check.py` (new) serves `frontend/dist` from the dev origin `127.0.0.1:1420` with
  the exact `csp` read from `tauri.conf.json` as a response header, runs the orchestrator in browser mode with a
  project, an imported bench image and a document, loads Catalogue / Edit (with the document) / Generate in
  headless Edge and greps the console for CSP refusals → **0 violations, 0 JS errors on all three pages**; the
  screenshots in `engine/spikes/out/csp/` show the Catalogue tile with its loopback thumbnail and the Edit
  document with its layer thumbnail (`data:`), so `img-src`, `connect-src` and the WebSocket were all exercised.
  Negative control with `CSP_OVERRIDE="default-src 'self'"`: 14 refusals, so the harness sees violations when
  they exist. (A first run served the page from an ephemeral port that the orchestrator's CORS allowlist rejects —
  "clean" there meant only that the static assets loaded; the harness now pins the dev origin.) Tests:
  `tests/test_events.py` (order, preview drop, dead client), reconciliation, warm-group aging, unknown ids at
  submit, API 404/422/400 codes, alpha thumbnails; the workspace test no longer expects `engine_out/` in a project.
  **60 passed.**
- Register state: **B1–B24 fixed.** Still open as notes, not bugs: disk guard, per-job logs, engine lockfile,
  sha256 verification in `fetch_weights.py`, and the M5 acceptance rerun on the rig (B3 changed candidate inputs).

## 2026-10-06 09:35 — Generate panel rework (clean tree, per-field presets, optional subjects, references in the prompt) and the ComfyUI configuration audit

- **User direction:** the prompt tree was littered with preset chips; presets must exist for every field but only
  behind an icon next to the input; subject 1 must be as optional as subject 2; the 10 reference images of JSON
  prompting belong in the same panel; and check whether ComfyUI's configuration layer is fully available.
- **Panel.** `fieldPresets.ts`: a field key per input (`scene`, `subject.pose`, `camera.lens`, …), built-in
  vocabulary per field (loom's directives + BFL examples), `presetMenu()` = built-ins · the user's presets for that
  field · "Remove a preset ▸" · "Save current text as preset…" (inline name box, no native prompt). `Field` renders
  label + input + one ✦ `ListPlus` button; single-valued camera fields replace, the rest append. Subjects start
  empty (`NEW_SUBJECT`, `treeFromJson` no longer injects one); every card has a remove button. The reference slots
  (`RefSlots`, 10 on dev / 4 on Klein, compact 5-column grid, numbered, drop target, right-click menu, downscale)
  sit directly under `scene` in all three prompt modes; the References rail tab is gone (rail: Prompt · Model ·
  Size & Batch · Presets). Presets tab = panel presets + the list of field presets (remove). Persisted panels get
  the new fields' defaults through the store's `merge`. 09 §2/§3a/§3b/§3d/§3e updated.
- **Audit — what the t2i graph exposed vs what ComfyUI v0.38.2 offers for FLUX.2:**

  | Option (node.input) | Before | Now |
  | --- | --- | --- |
  | `KSampler.sampler_name` (45) | 7 whitelisted; others silently reverted to the preset | all 45, served live from `/object_info` via `/capabilities`; unknown = error in the preview |
  | `KSampler.scheduler` (9) | 6 | all 9 + `flux2` |
  | `Flux2Scheduler` sigmas (BFL's resolution-shifted schedule; the inpaint graphs already use it) | not for t2i | scheduler `flux2` → `RandomNoise` + `KSamplerSelect` + `Flux2Scheduler` + `BasicGuider` / `CFGGuider` (CFG > 1) + `SamplerCustomAdvanced` |
  | `ModelSamplingFlux.max_shift/base_shift` (FLUX.2 inherits Flux sampling, default constant shift 2.02) | not exposed (09 §3b named "shift") | Advanced: model default or custom base/max (node defaults 0.5 / 1.15) |
  | `UNETLoader.weight_dtype` | fixed per preset | Advanced select (default / fp8_e4m3fn / fp8_e4m3fn_fast / fp8_e5m2) — `_fast` is the speed candidate to measure on gfx1201 |
  | `CLIPLoader.device` | fixed GPU | Advanced (cpu = VRAM headroom, ≈ 170 s per new prompt per E0) |
  | Turbo `LoraLoaderModelOnly.strength_model` | fixed 1.0 | strength field next to the Turbo toggle |
  | `VAEDecodeTiled` (D13 "tiled VAE") | not used | Advanced: tiled decode + tile size |
  | `KSampler.denoise` | fixed 1.0 | unchanged — meaningless for t2i; Refine (I2I) carries it |
  | `EmptyFlux2LatentImage.batch_size` | 1 | unchanged by design — one job per seed streams, cancels and ingests per image |
  | `ImageScale.upscale_method` for references | lanczos | unchanged |
  | Engine flags (`--reserve-vram`, stall timeout) | in app.json only | Settings shows **Stall timeout** and **Reserve VRAM**; the raw flags field covers any other CLI flag |
  | Not exposed — candidates for a spike: `EasyCache` / `LazyCache` (step skipping on DiT, likely the biggest speed win on 16 GB), `PerturbedAttentionGuidance`, `SkipLayerGuidanceDiT`, `CFGZeroStar` / `CFGNorm`, `APG`, two-stage `KSamplerAdvanced`; LoRA slots (D25) | — | listed in 09 §3b as post-MVP measurements |

  `effective_params` validates sampler / scheduler / dtype / device against the pinned lists and raises
  `CompileError` (preview 422) instead of falling back; the compiled graph is still contract-checked against the live
  `/object_info`. The fixture gained `VAEDecodeTiled` and `CFGGuider` hand-built from the pinned source (flagged
  `hand_added`; `make_object_info_fixture.py` lists them for the next capture).
- **Verification.** `tsc` clean, lint unchanged; 62 offline tests (new: every exposed option reaches the graph and
  the contract; `/capabilities` lists 45 / 10 / 4 / 2). `scripts/csp_check.py` now also opens `&suite=generate&tab=model`
  (a generic `?suite=&tab=` deep link was added to `suiteRegistry`): screenshots in `engine/spikes/out/csp/` show the
  Prompt tab (scene → reference slots → optional subjects → look → camera → extras, one ✦ per field) and the Model tab
  (Turbo strength, full sampler list, Advanced disclosure) under the production CSP with 0 violations. Not run: a
  rig generation with the new options — the fp8 `_fast` dtype, shift and the flux2 schedule want E0-style timings
  before any default changes.

## 2026-10-06 13:05 — M5 closed: AI Select (SAM 3 + BiRefNet), tiled refine, gradient fill, bench task 03; acceptance 24/24

- **Finding first:** the 2026-10-05 entry said the SAM 3 / BiRefNet nodes were "not in the engine yet". ComfyUI v0.38.2 ships
  both in core — `comfy_extras/nodes_sam3.py` (`SAM3_Detect`, loaded from `sam3.pt` through `CheckpointLoaderSimple`, text
  encoder included) and `nodes_bg_removal.py` (`LoadBackgroundRemovalModel` / `RemoveBackground`, BiRefNet). No custom node
  pin was needed (D33). `sam3.pt` (3.4 GB) was already on disk in the backup install's `sam3/` folder, now mounted as a
  checkpoints path; BiRefNet came through the roster fetch (`ZhengPeng7/BiRefNet` `model.safetensors`, 424 MB fp16, MIT,
  stored as `background_removal/BiRefNet-general.safetensors`, sha256 in the ledger).
- **Backend.** `Segment` recipe (`subject` · `text` · `points` · `box`; threshold, refine iterations; `op` replace / add /
  subtract / intersect; expand ±256, feather; engine image ≤ 1024). The queue sends the whole visible composite, scales the
  prompts into engine pixels, and on completion turns the `MaskToImage` result into a document-sized mask
  (`edit_ai.mask_from_engine`), joins it with the selection (`combine_selection`), saves the ORA and broadcasts
  `document.changed {selection, coverage}`; `GET /documents/{id}/selection` returns the bytes. The box prompt goes through
  core `CreateBoundingBoxes` (a canvas widget node: JSON `{x, y, width, height}` boxes on the engine grid, `editor_state: []`).
  `Upscale` gained `refine` (Klein base / dev, strength, tile, overlap, steps, prompt): `edit_ai.plan_tiles` lays 16-aligned
  tiles with the last row/column pulled to the edge, and `build_upscale` emits per tile `ImageCrop` → `VAEEncode` →
  `KSampler` at `denoise = strength` → `VAEDecode` → `ImageCompositeMasked` through a `SolidMask` feathered only on inner edges —
  one engine graph, one job. `contract.py` now reads V3 `["COMBO", {options}]` enums (the new nodes use them), so file names
  and sampler names are validated there too. The fixture was **recaptured from the live engine** (988 classes → 68 kept, the
  two hand-added entries replaced; `make_object_info_fixture.py` lists the slice 2 classes).
- **Frontend.** `aiPanelStore.ts` holds the AI panel settings so the **A tool** options and the AI tab's new **Select**
  operation share them: Subject (BiRefNet) or SAM 3 with text / points / box, threshold, combine, expand, feather, Select ▶.
  On the canvas the A tool collects prompts: click = include point, Alt-click = exclude, drag = box (green / red dots and an
  amber box drawn in the overlay; a click switches the panel to the matching SAM mode). `document.changed {selection}` →
  `loadSelectionFromServer()` replaces the selection canvas. Upscale has a **tiled refine** disclosure (model, strength, tile,
  overlap, prompt). The **G tool** has solid / linear / radial: a drag paints foreground → background (mask: white → black)
  inside the selection, as one history step. The `A` tool lost its "arrives in M5" flag. Build with the full `tsc -b` type-check
  clean (note: `tsc --noEmit -p tsconfig.json` type-checks nothing — that file only references the app and node configs; the
  earlier "tsc clean" lines in this journal relied on the builds that followed them, which did run `tsc -b`).
- **Acceptance `scripts/m5_acceptance.py` — 24/24 on the rig** (log `engine/spikes/out/m5/acceptance-20261006-slice2.log`;
  the orchestrator in browser mode, engine started on the first job, candidates 2, B3 fix in place so candidates are
  independent): Fill crates 68.8 s cold / 39.8 s warm · Fill-Match 19.9 s · Remove 20.1 s · cloak 40.6 / 40.8 s · face 47.7 s ·
  outpaint right 240 31.5 s (1200×544) · refine 0.25 Klein base 47.0 s · ESRGAN ×2 5.8 s → asset. **New:** BiRefNet subject
  **2.3 s** — face 0.96 / cloak box 0.62 / crates box 0.00 / canvas 0.16 coverage; **task 03** background swap on the inverted
  matte 31.4 s — layer alpha **0.027 on the subject, 0.996 on the background** (subject preserved, sheet shows the sunlit harbour
  square around an unchanged figure); **SAM 3** text "the young woman in the hooded cloak" 33.0 s (includes the checkpoint load)
  — face 0.95 / cloak 0.62 / crates 0.00; SAM 3 point on the face, `add` → face 0.95 in **3.3 s**; **tiled refine** ×2 (Klein
  base, 1024 / 128, 0.25) 439.2 s → **2400×1088** asset over 6 tiles. 21 nodes saved in the ORA. 10 §14 items 1, 3, 4, 5, 6, 7
  ticked; item 2's pen half stays with D19. **M5 is closed** (12 §6). (After its last check the script crashed on its own
  cleanup line — a local named `a` shadowed the argparse namespace — so the summary line is missing from the log and the
  test document was left in the project; fixed in the script, the 24 check lines stand.)
- Not run / carried: Fill Hero on the bench (unchanged since E8, `--hero` flag), SeedVR2 and LoRA slots (post-MVP), a
  Photoshop/Krita open of the PSD (manual). Next: **M6 Animate** (11 approved, E4/E5 decided; E9 fps-conform spike inside it).

## 2026-10-06 14:30 — Empty trash; tiles dropped on Edit open there; renderer probe + WebGL2 fallback (user reports)

- **Report 1:** 10 000 assets moved to the trash, no way to delete them all. Added **Empty trash**: `cat.emptyTrash`
  command (panel · context · strip · palette) and an `EmptyTrashButton` in the Library panel under the folders and in the
  strip's selection bar — two-step, no native dialog: first click arms for 4 s ("Click again: delete N permanently"),
  second click calls `POST /assets/purge {ids: null}` (every trashed asset). The server now answers `{purged: n, ids}`
  and, above 50 assets, broadcasts one `catalogue.changed {purged}` instead of n `asset.deleted` frames (the clients
  reload both grids); test added (60 imports, 55 trashed → one frame, 5 left; a small purge still lists its ids).
- **Report 2:** "pull an image to edit mode: it doesn't show on the work area". Two readings, both handled:
  (a) *drag*: Catalogue tiles already carry `text/loom2-assets`, but nothing accepted the drop. Now the **Edit tab**
  opens the dropped asset as a document, the **Edit stage / empty state** opens it (no document) or adds it as a new
  raster layer above the active one (`addLayerFromAsset`: fetched through `/assets/{id}/file`, `LayerPixels.fromImage`,
  lineage to the asset), and the **Generate tab** takes dropped tiles as references.
  (b) *the canvas itself*: a headless check (`scratchpad` diag; the editor opened from a bench asset, console captured)
  showed the document loads and the Pixi scene is built — 1 raster 960×544, checker visible — yet on WebGPU nothing is
  drawn and the GPU-vs-exact compare never completes, while on WebGL2 (`&renderer=webgl`, new dev deep link) the stage
  renders and the compare is exact (mean 0.0). Headless WebGPU is not representative of WebView2 (E1 measured 3 ms
  composites there), so the real-app cause could not be confirmed from here; the design's D3 fallback is now
  **automatic**: after init a 4×4 white sprite is drawn and read back through the exact-compare path; a renderer that
  yields no pixels is destroyed and the editor boots again on WebGL2 ("WebGL2 (fallback)" badge + toast). The badge is a
  button cycling auto → forced WebGL2 → forced WebGPU (persisted; the canvas remounts). The on-demand render loop
  gained a 60 ms timer alongside the animation frame so a paused frame (hidden window) cannot leave the canvas stale.
  The `&verify=1` deep link now waits for the renderer instead of a fixed 2 s. 08 §12, 10 §11a, 13 D3 updated.
  Build with the full `tsc -b` check clean; 68 offline tests. Not verified from here: WebGPU in the user's WebView2 —
  if the work area still stays empty after this, the badge text (WebGPU / WebGL2 (fallback)) is the first thing to read.

## 2026-10-06 16:40 — Editor "not working" report: one render-loop bug behind four symptoms; brush panel rebuilt

- **Report:** "the image was invisible, but when I resized the window it popped out · zoom is not working · layers have
  no relevance yet · masks cannot be painted · the brush selection is very limited and most options are unconfigurable
  (like brush diameter)".
- **Root cause (first four symptoms):** the on-demand render loop (10 §11) coalesces requests through a pending flag
  that held the `requestAnimationFrame` id. The canvas's cleanup cancelled that frame but left the flag set, and React
  StrictMode (dev) mounts → unmounts → mounts the canvas once, with the zoom/pan effect requesting a frame before the
  renderer existed. Every later request saw "a frame is pending" and returned: strokes, mask edits, layer toggles and
  zooms all went into the store and the CPU canvases, nothing reached the screen until Pixi's own resize path drew a
  frame. Fix in `EditorCanvas.tsx`: a request before the renderer exists is dropped (init renders once itself), the
  frame callback clears the flag first, cleanup cancels *and* clears, and the 60 ms timer added yesterday as a belt is
  gone (it masked nothing and ticked while idle). The headless diagnosis of yesterday could not show any of this —
  headless Edge does not present WebGPU at all — so the editor was driven in a **visible Edge window over the DevTools
  protocol**; that harness is now `scripts/edit_headed_check.py` (modes `render` and `paint`; dev builds expose
  `window.__loom2App` / `window.__loom2Editor` for it). Numbers on the rig, WebGPU: stage 21.6 % bright at once (was 0
  until a resize), Ctrl+wheel → 70.5 %, after a window resize 73.9 % and zoom still works; `paint`: brush band changed
  34.8/255, eraser on a fresh mask 11.0/255 (checker shows through), layer eye off 45.5/255; WebGL2 identical. Painting
  itself had never been broken: the stroke was in the layer canvas and in the GPU composite all along.
- **Brush panel (fifth symptom):** every slider in the editor now has a **number field** (px for size, % for the rest;
  typed values are clamped), size runs to 1024 px, and the Brushes tab carries the full current brush (size, hardness,
  opacity, flow, spacing, smoothing, colour) under a preset list of seven built-ins with their own diameters (hard round ·
  soft round · airbrush · pencil · inker · marker · wash) plus **Save current as preset…** (named, persisted in the
  browser, deletable). The `[` `]` / `Shift+[` `]` step buttons got icons (±, dashed/solid circle) instead of the zoom
  glasses. 10 §4 Panel · Brushes, §11, §11a, §14 updated; README scripts line.
- Build with the full `tsc -b` check clean; 68 offline tests. Pixi's shared ticker still requests ~32 animation frames
  a second while idle (it renders nothing); left as a follow-up for the M6 power budget.

## 2026-10-06 17:50 — Native dialogs crash in WebView2; mask editing from the Move tool; whole-suite tour (user reports)

- **Report:** "If I click on the image it moves it — also after creating a mask and selecting it; deleting a new layer
  gives *unhandled: dialog.confirm not allowed. Command not found*; check the whole edit suite once again."
- **Dialogs.** `window.confirm` / `window.prompt` are routed by Tauri 2 to its dialog plugin, which the capabilities
  (rightly, 07 §1: no native dialogs) do not allow — so every confirm/prompt crashed with the overlay the user saw.
  Nine call sites existed (layer delete / rename / close document / delete .ora in Edit; purge, new / smart / rename
  collection in Catalogue; save preset in Generate). Replaced by the frame's own **AskDialog** (`askConfirm` /
  `askText` in the session store, promise-based, Enter / Escape, danger styling) and, for **Delete layer**, by no
  question at all: the layer goes at once and the toast offers **Undo** (guarded: only while nothing else happened).
  The crash overlay itself is now dismissible by click. 07 §1 amended.
- **Mask painting.** Add mask / clicking a mask thumbnail entered mask editing but left the tool alone, so with Move
  active the first click dragged the layer. Now a tool that cannot paint or select (Move, Crop, Zoom, Hand, Eyedropper)
  switches to the **Brush** when mask editing starts, a one-time toast and a hint row under the layer list say
  "white shows, black hides — B · E · G" with an *Edit pixels instead* button. 10 §6.
- **Whole-suite check.** `scripts/edit_headed_check.py tour` runs every Edit command through a dev hook
  (`window.__loom2Commands`) in a visible Edge window with a document open — 12 tools, 9 view toggles, 14 layer
  operations, 12 adjustment / filter types, 10 mask steps, 8 selection steps, transform begin / cancel / apply, 8
  flips and rotations, 6 brush / colour commands, delete + Undo toast, undo / redo ×8, save, Save to Catalogue, PNG
  and PSD export, exact compare, close via the in-app dialog — checking the state after each step and failing on any
  page exception, error toast or crash overlay: **all pass**. `cmpdiag` compares the GPU preview with the exact
  flatten feature by feature: 0/255 for masks, groups (isolated at 50 %: 1/255), every adjustment, blur / sharpen /
  high-pass (≤ 1/255), identity transform, flips and 90° rotations; the **noise** filter differs (p99 86) because its
  preview is a hash approximation of the seeded numpy noise *by design* (10 §3) — the tour hides it before comparing.
  Two things the tour surfaced on the way: **Compare** flattened the *saved* document, so with unsaved changes it
  reported nonsense (now saves first, like Export); and the first PSD export in a dev session failed because Vite
  discovered `ag-psd` lazily ("Outdated Optimize Dep" reload) — pre-bundled via `optimizeDeps.include`.
- Build with the full `tsc -b` check clean; the Python side is unchanged (68 tests). 10 §14 gained the tour line.

## 2026-10-06 18:20 — Noise filter preview made exact

- The noise filter was the one feature where the GPU preview and the exact flatten disagreed by design (hash
  approximation vs numpy's seeded normal). Both sides now evaluate the **same function of (seed, x, y)**: the
  lowbias32 integer hash (five shifts/multiplies on uint32, wrapping) → two 23-bit uniforms per pair → Box-Muller;
  three independent channels, monochrome repeats the first. GLSL ES 3.00 and WGSL run it per fragment,
  `compose.noise_field` runs it vectorised in numpy; four tests pin the hash against a scalar reference and the
  field's statistics. `cmpdiag` on the rig: noise [mean 0.02, p99 1, max 1]/255 — the same as blur and black & white;
  every feature now lands at 0–1/255. 10 §3 updated ("preview ≈" now only means large blur radii and dissolve).
  72 offline tests.

## 2026-10-06 19:40 — M6 Animate opened: volatile facts re-checked; slice 1 = the image-to-video backend

- **Re-check (12 §10 standing rule, 04 §8):** the engine pin v0.38.2 (cloned 2026-10-02) already carries the Wan 2.2
  and LTX-2 node families the E4/E5 drivers used; the fixture recaptured today lists all 27 node classes the two
  graphs need. LTX-2.5 exists (diffusion decoder, native multi-shot, core support merged before v0.32; 2.3 workflows
  carry over, checkpoints do not) — a candidate upgrade once an fp8 transformer is benchmarked on 16 GB, not an M6
  task; D9 stays on LTX-2.3 distilled fp8. Wan-Animate-2 is a reference/pose model, not i2v — irrelevant here.
  Weights on disk: both Wan fp8 experts, umT5 fp8, Wan VAE, Lightning LoRAs, LTX-2.3 fp8 transformer, Gemma fp8,
  projection, video + audio VAE — the M6 set is complete (04 §1).
- **Slice 1 — backend (11 §10, 06 §7):**
  - `I2V` recipe: model (`wan22-i2v-high-fp8` | `ltx23-distilled-fp8`), start / optional end asset (FLF), prompt,
    optional negative (stock lists by default), frames / fps / size, **preset** draft · motion · quality with step / CFG /
    shift overrides, LTX **beats** (`{frame, asset_id, strength}`), seeds, loras (D25, empty). `graphs.i2v_params`
    snaps size to ×16 / ×32 and frames to 4n+1 / 8n+1 and resolves the preset — the UI previews exactly that through
    `/recipes/preview`, which now answers i2v (snapped values, missing weights, ETA from the E4/E5 baselines).
  - `graphs.build_i2v`: the E4c Wan graph (fp8 experts, Lightning on both experts for Draft, undistilled high expert at
    CFG 3.5 for Motion per E4b, 10 + 10 without LoRA for Quality; `WanFirstLastFrameToVideo` when an end frame is set)
    and the E5b LTX graph (joint AV latent with the audio VAE, `LTXVAddGuide` for the end frame at −1 and for every beat
    at its index, clamped to the clip). Both end in **`SaveImage`** — one PNG per decoded frame is the clip **master**;
    no engine mp4 (the orchestrator encodes the proxy with the GOP it wants). Contract-checked against the fixture
    for every preset, FLF and beats.
  - Queue: start / end / beat frames are uploaded as PNG (the graph's `ImageScale` fits them), the frames come back as
    `clips/<clp_id>/master/%06d.png`, **`clips.ClipStore`** writes `clip.json`, encodes `proxy.mp4` (PyAV libx264,
    yuv420p, crf 18, **GOP 6** per E6, faststart), and the proxy is indexed **in place** as the Catalogue asset (kind
    `video`, frames / w / h, poster thumbnail from frame 0, parents = start / end / beats, params.clip_id). Events
    `job.updated` ("uploading frames" · "writing the master" · "encoding the proxy"), `asset.created`, **`clip.ready`**.
    Submission rejects non-video models and beats on Wan (422).
  - API: `GET /clips`, `GET /clips/{id}`, `GET /clips/{id}/proxy.mp4` (Range → 206 for Mediabunny), `GET
    /clips/{id}/frames/{n}.png` (master), `POST /clips/{id}/extract {frames}` → Catalogue images with
    **`frame-extract` lineage** (≤ 64 per call); `/capabilities` lists `i2v` with per-model health (all companion
    weights), rules, presets and the video tiers.
  - Fake engine: a graph with a video node yields `length` differing frames, so the proxy encode is exercised. Tests
    (`test_animate_m6.py`): snapping, Wan presets + FLF contract, LTX end + beats contract and ETA, queue end to end
    for Wan and for LTX with end + beat (clip, 9-frame h264 proxy decoded back, asset, lineage, `clip.ready`, engine_out
    clean), submission validation, the `/clips` API incl. Range and harvest. **78 offline tests.**
- Design notes: the timeline will live under the player inside the Stage (the frame's Dock stays the jobs list);
  `Catalogue.rebuild` does not yet re-index clip proxies from `clips/` (follow-up before M7's durability suite).
- Next: slice 2 — the Animate suite (11 §2–§6: Inputs / Model / Length panels, Mediabunny player with frame-accurate
  stepping, filmstrip, compare, onion skin, Clip / Frames / Lineage inspector, Catalogue `Shift+A` / `Shift+Z`), then the
  rig run of 11 §11 and E9.

## 2026-10-06 21:10 — M6 slice 2: the Animate suite (player, filmstrip, compare, timeline, harvest) — checked in a visible window

- **Suite** (`frontend/src/suites/animate/`, 11 §2–§6, D32 throughout — 36 `anim.*` commands with buttons or menus, keys
  as accelerators):
  - **Panel · Inputs**: start / end slots (drop a Catalogue tile, `Shift+A` / `Shift+Z` in the Catalogue, or drop on the
    Animate tab — two tiles set start and end), swap, prompt with motion chips, own-negative toggle (stock lists
    otherwise), FLF-on-Wan morphing hint, **beats** for LTX (drop frames; frame index, strength, remove).
  - **Panel · Model**: Wan (faithful) / LTX (fast, beats) cards with health from `/capabilities.i2v` (every companion
    weight), the locked H3 card (D17), preset draft · motion · quality with the compiler's labels, advanced steps / CFG
    (Wan high expert) / shift.
  - **Panel · Length & Size**: Draft / HD / custom tiers, landscape / portrait / square, size snapped to the model's
    multiple, frames (4n+1 / 8n+1), fps (native kept; conform is D27's), seed mode, clip count; the **estimate line** from
    `/recipes/preview` (what runs: W×H, frames, label, ETA, missing weights with a Fetch button). Presets · Clips tabs.
  - **Stage**: Mediabunny **player** over the GOP-6 proxy (frame n ← timestamp (n + ½)/fps, one canvas per frame, a
    newer request supersedes a decode in flight), onion skin (start / end stills at 30 %), **filmstrip** (every k-th frame
    from the PNG master), **compare** (A beside the start / end still or another clip synced by normalised time), the
    **transport** (first / −10 / step / play / step / +10 / last, in / out, extract, send to Edit), and the **timeline** under
    the player (ruler in seconds, scrub, draggable in / out handles, S / E markers, beat ♦, harvested ▼ pins) — the
    frame's Dock stays the jobs list (deviation from the 11 §2 sketch, recorded). Live i2v jobs show progress cards.
  - **Inspector**: Clip (Keep / Reject / Variations / Re-run / Try on the other model / Show in Catalogue, format, seed,
    prompt, time, source thumbnails, extend-by-hand), Frames (current frame, range, extract frame / range every k, send
    to Edit, harvested thumbnails), Lineage (sources, extracted children, siblings from the same start or batch).
  - Wiring: `clip.ready` selects the new clip and toasts; `?suite=animate&clip=<id>` deep link; a video asset's
    `Shift+A` opens its clip in Animate.
- **Check** — `scripts/edit_headed_check.py animate` writes a 24-frame clip whose frames carry their index as a 7-bit
  code (E6's trick) into the project, opens the suite on it and drives it through the dev hooks: **every frame shows its
  own code** stepping forward (23/23), backwards (12/12) and on random access (7/7); play advanced the counter and the
  canvas agreed; in 4 / out 20 + extract every 8th → pins 4 · 12 · 20, three Catalogue images with `frame_index` and
  `frame-extract` lineage, thumbnails done, timeline pins shown; onion / filmstrip (24 thumbs) / compare render; a start
  frame previews 832×480 · 81 f @ 16 with no missing weights and arms Animate. No page exception. 11 §11 item 4 (player
  steps every frame exactly) and item 5's Catalogue half are therefore ticked offline; the rig items wait for the run.
- Build with the full `tsc -b` check clean; 78 offline tests. Next: the **rig run** (11 §11 items 1–3: Wan Draft 81 f
  480p, FLF, LTX with a beat — time and peak VRAM recorded), E9 (fps conform spike), FaceSim advisory.

## 2026-10-06 22:30 — M6 rig run 17/17 (11 §11 items 1–3); E9 fps-conform spike measured (D27 decided)

- **Rig run** — `scripts/m6_acceptance.py` against the dev orchestrator (`.loom2_state`, project `F:/loom2-projects/m6-acceptance`),
  real engine started by the queue, seed 20261005, bench frames of 04 §6:

  | clip | model · preset | format | engine wall | VAE decode / samplers / image encode | lowest free VRAM |
  | --- | --- | --- | --- | --- | --- |
  | 01 character turn | Wan 2.2 Draft (Lightning 2 + 2) | 832×480 × 81 f @ 16 | **256 s** (incl. cold start + weight load) | 102 s / 44 + 43 s / 44 s | 5.31 GB |
  | 03 crouch → stand, FLF | Wan 2.2 Draft, `WanFirstLastFrameToVideo` | 832×480 × 81 f @ 16 | **255 s** | 96 s / 45 + 45 s / 63 s | 5.06 GB |
  | 03 with a beat at 60 (+ end) | LTX-2.3 distilled, 8 steps | 1024×576 × 121 f @ 24 | **172 s** | 78 s / 58 s / text 16 + 11 s | **2.69 GB** |

  Every clip: `clips/<id>/master` with the requested frame count, h264 proxy that decodes to the same count at the
  requested fps (1.4–1.8 MiB), a Catalogue video asset with lineage to the start (and end) frame and a poster
  thumbnail, three frames harvested with `frame-extract` lineage → **17/17 checks**. Sheets in `engine/spikes/out/m6/`:
  01 — identity intact (braids, cloak, compass, sign), she lowers the compass and looks down (as E4); 03 FLF — reaches
  the standing end pose, the rise happens early between frames 16 and 32 (E4's "position jump"); 03 LTX — the beat at
  60 is reached by frame 48 and held, one wild intermediate pose around frame 24, identity softer. The Wan VAE decode
  is still 38–40 % of the clip (Q18); LTX at 1024×576 leaves only 2.7 GB free on the card — HD tiers stay "selective".
- **E9 (D27)** — `scripts/e9_fps_conform.py`: the Wan FLF master (81 f @ 16) → 121 f @ 24 with **rife-ncnn-vulkan
  20221029, rife-v4.6** (Vulkan on the RX 9070 XT, `engine/tools/`, fetched tonight): **1.8–3.3 s** for the clip.
  Scores (mean |Δ luma| between frames = flicker; its std = judder; Laplacian variance = sharpness):

  | sequence | flicker mean · p95 · std | 2nd-difference | sharpness | notes |
  | --- | --- | --- | --- | --- |
  | Wan 16 fps native | 4.97 · 6.66 · 1.47 | 8.32 | 520 | reference |
  | Wan → 24 fps **RIFE** | 3.70 · 5.40 · **1.22** | 5.92 | 409 (in-betweens 0.98 × RIFE's own source frames) | even motion; every output frame keeps **80 %** of the master's Laplacian variance |
  | Wan → 24 fps hybrid (originals kept at source timestamps) | 3.74 · 6.17 · 1.43 | 6.04 | 443 (in-betweens 0.79 × neighbours) | sharpness alternates frame to frame — the classic ghost flicker |
  | Wan → 24 fps duplication | 3.31 · 6.56 · **2.63** | 6.09 | 522 | sawtooth: judder |
  | LTX-2.3 native 24 fps | 0.77 · 2.63 · 0.85 | 1.24 | 195 | smoothest by far, far softer image |

  **Verdict (recorded in 13 D27):** conform Wan drafts to the project's 24 fps **at export with RIFE v4.6 on the whole
  sequence** (not hybrid, never duplication); the clip master stays native 16 fps; where fluid motion matters more than
  detail, render natively on LTX. The 20 % softening is uniform (no ghosting visible on the sheet) — a mild unsharp
  pass after RIFE is a candidate follow-up, unmeasured. Identity: RIFE interpolates existing frames, so no drift by
  construction; FaceSim (11 §11 item 6) still waits for ArcFace on the rig (not installed; `insightface` needs a build
  toolchain on Windows — the ONNX pair from `buffalo_l` with onnxruntime is the lighter route).
- Also tonight: `Catalogue.rebuild` re-indexes clip proxies from `clips/*/proxy.json` and video thumbnails fall back to
  the clip's first master frame (test added; 78 offline tests). Open in M6: FaceSim advisory, the H3 unlock in Settings
  (D17), the two-clip compare sync on the rig (the suite supports it; the acceptance project now has three clips).

## 2026-10-06 23:30 — M6 closed: all five bench tasks through the app, FaceSim advisory, H3 toggle, compare sync; M7 opened

- **Leftovers done.** (1) **FaceSim** — `tools/facesim.py`: InsightFace `buffalo_l` (SCRFD det_10g + ArcFace w600k_r50,
  fetched by `scripts/fetch_facesim.py`, 275 MB zip → 182 MB kept under `<models_root>/insightface/`) on ONNX Runtime CPU
  (`onnxruntime` 1.30 added to the orchestrator). The geometry (Umeyama alignment to the ArcFace template, SCRFD decode,
  NMS) is unit-tested without weights; a side task measures every new clip after its proxy (`clip.updated`), `POST
  /clips/{id}/identity` and the inspector's *Measure identity* recompute; the Clip tab shows mean · min @ frame · frames
  with a face. ≈ 1 s per clip on the CPU. (2) **H3 toggle** (D17): `Settings.h3_licence_confirmed`, Settings → Licences;
  the Animate card reflects it but stays disabled until the H3 graph and weights land (post-MVP, 04 §5b). (3) **Compare
  sync** verified in the headed check with two coded clips (24 and 48 frames): A frame 12 ↔ B frame 25 by normalised time.
- **Rig run 2 — the remaining bench tasks on Wan Draft** (`m6_acceptance.py --tasks 02,04,05`, 17/17):

  | task | engine wall | lowest free VRAM | FaceSim mean · min | sheet |
  | --- | --- | --- | --- | --- |
  | 02 walk toward camera | 254 s | 4.99 GB | 0.49 · 0.05 at frame 80 (the reference face is tiny in the crowd) | walks in, scale grows, freckles resolve, crowd parallax |
  | 04 camera push cabin | 250 s | 3.24 GB | 0.77 · 0.57 | geometry and both characters stable, the captain nods, dolly minimal (E4b: a control problem) |
  | 05 dialogue gesture | 243 s | 3.09 GB | **0.87** · 0.79 | blink, look down and back up, a tear, no mouth artefacts |
  | 01 character turn (run 1) | 256 s | 5.31 GB | 0.70 · 0.62 | |
  | 03 crouch → stand FLF (run 1) | 255 s | 5.06 GB | 0.41 · 0.28 (9/12 frames with a face) | |
  | 03 LTX with a beat (run 1) | 172 s | 2.69 GB | 0.39 · 0.11 at frame 22 (the morph) | |

  With E4's five tasks on the spike driver and these five through the app, **04 §6's i2v bench is recorded end to end**;
  identity, time and VRAM match the spikes (fp8 experts, Lightning 2 + 2). FaceSim orders the clips the way the eye does.
- **11 §11: six of six ticked.** M6 acceptance met: the checklist, the five bench tasks, the E9 verdict (D27). **M6 closed.**
  Open items carried to post-MVP (13): the H3 graph + weights, native LTX extension, Wan latent previews (11 §12), the
  fps-conform export step (Q14), an unsharp pass after RIFE (E9 note).
- **M7 opened** (12 §8, slices 1–5): slice 1's offline half is in — `tests/test_durability_m7.py`: power loss mid-job
  (relaunch paused + re-queued), a **torn `queue.json` is quarantined** as `queue.json.corrupt-<ts>` and the queue starts
  paused with a recovery banner (it used to be fatal: `read_json_or` refuses torn records by design), a **corrupt
  `catalogue.sqlite` is quarantined and rebuilt** from the manifests, a truncated manifest is skipped, the engine dying
  mid-job fails the job and frees the queue, and a **disk guard** at submission (422 below 2 GB free or over the project's
  size cap). `/queue.recovery` carries the notes, the frame shows them as error banners. 89 offline tests. The rig half
  (`scripts/m7_durability.py`: `taskkill /F` the orchestrator while a clip samples, relaunch; kill ComfyUI mid-clip) runs
  tonight — results in the next entry.

## 2026-10-07 01:10 — M7 slices 1–4: durability on the rig 11/11, performance pass, pin review (v0.39.0 safe), setup + CI

- **Durability, rig half** — `scripts/m7_durability.py` (its own orchestrator on 8767 with a copy of the dev state, the
  acceptance project, real engine):
  - *power loss*: `taskkill /F` on the orchestrator while a Wan clip sampled → the ComfyUI process **died with it in 0.1 s**
    (Job Object); relaunch → **queue paused, the job re-queued** (`resumed_unclean`, retry 1), no recovery notes (records
    intact); unpause → the re-queued job **finished in 250 s** and its clip is complete (81 f, proxy 1.6 MiB).
  - *engine crash*: ComfyUI killed mid-sampling → the job **failed in 6 s** ("engine process died (ConnectError)"), the
    orchestrator kept answering, the queue stayed unpaused (7 done · 1 failed), and the next submission **started a fresh
    engine in 6 s** (new pid). 11/11 checks. With the offline half (89 tests) 03 §6's durability line holds.
- **Performance pass** — `scripts/edit_headed_check.py perf` on the regenerated 10k synthetic project (the old synthetic
  assets had gone to the trash in today's Empty-trash work; `make_synthetic_assets.py` rebuilt 10 000 in 224 s):

  | measure (03 §6) | result | budget |
  | --- | --- | --- |
  | Catalogue first paint on a warm index (switch back into the suite) | **14 ms** to the first tiles, 10 009 assets | < 1 s |
  | app boot → first Catalogue tile (page load, handshake, project info) | 2.3 s | — (information) |
  | Catalogue scroll, 3 s | **every display frame**, 0 long frames, 3 312 px | smooth |
  | editor composite, 6 × 4K layers with multiply / screen / overlay / soft-light, full re-render (CPU submit + GPU done) | **p50 5.8 ms · p95 7.1 ms · max 7.6 ms** on WebGPU | ≤ 16.7 ms (60 fps) |
  | brush on the 4K document, pointer move → next presented frame | p50 33.0 · p95 33.4 ms | ≤ 1 display frame |
  | Animate player frame latency, 1024×576 GOP-6 proxy, sequential / random | p50 33 / 34 ms | ≤ 41.7 ms (24 fps) |

  **Finding:** the author's 4K panel runs at **29–31 Hz** (`Win32_VideoController` 3840×2160 @ 29 Hz) — `requestAnimationFrame`
  cannot exceed ≈ 30 fps on this desktop, so every frame-rate number above is display-bound, not app-bound; the GPU budget is
  therefore measured as time per composite (a 60 Hz mode would show the same 7 ms). Worth a look at the display settings
  (DisplayPort / HDMI 2.x allow 60 Hz at 4K). The `perf` mode launches Edge without background / occlusion throttling and
  prints the window's own frame rate first.
- **Pin review** — `scripts/pin_review.py` against **ComfyUI v0.39.0** (released 2026-10-05; CPU engine from a scratch worktree
  with our custom nodes): **0 of the 68 node classes loom2 uses are missing or changed**, all 17 recipe variants compile
  (t2i dev / turbo / Klein / Klein base + refs, refine, five inpaint modes, upscale ± tiled refine, both segmenters, Wan draft /
  motion FLF, LTX with beats). **Verdict: safe to bump by the contract gate.** The bump itself is a dedicated step (D15):
  submodule → v0.39.0, `engine-setup.ps1` for its requirements, fixture recapture, a rig smoke (one Klein t2i, one Wan
  draft), rollback = submodule reset; scheduled with rig time rather than tonight. torch 2.13.0+rocm10.0.0 stays.
- **Setup + CI** — `scripts/setup.ps1` (both venvs, frontend, engine checkout + ROCm torch, FaceSim weights; `-SkipEngine`
  for a machine without the GPU); `.github/workflows/ci.yml`: offline suite + `tsc -b` + Vite build for `full` and `open` on
  every push / PR, Tauri installers for both variants on main / tags (`loom2-full-*`, `loom2-open-*`); the shell now bakes
  `LOOM2_VARIANT` in at compile time and hands it to the orchestrator (D26). Not yet run on GitHub (first push of the
  workflow is this commit).
- **Left in M7:** the pin bump step above; slice 5 — docs refresh (00–14) and the author's end-to-end click-through against
  07 §5 / 08 §10 / 09 §10 / 10 §14 / 11 §11; the post-MVP backlog ordered in 13; H3 remains post-MVP.

## 2026-10-07 03:20 — ComfyUI pin bumped to v0.39.0 (smoke passed); CI fixed; docs refreshed; click-through guide; backlog ordered

- **Pin bump (D15, M7 slice 3).** Submodule `engine/comfyui` → **v0.39.0** (`b0b7435`, 2026-10-05). Requirements diff was small
  (frontend package 1.53.6 → 1.53.10, workflow templates 0.11.74 → 0.11.76, embedded docs 0.5.12 → 0.5.13, comfy-kitchen 0.2.36 →
  0.2.37); `engine-setup.ps1 -SkipTorch` applied them, torch 2.13.0+rocm10.0.0 untouched. `/object_info` recaptured from the live
  engine (988 classes) → the fixture keeps our 68 (`comfyui_version` 0.39.0), **89 offline tests pass**. **Rig smoke:** Klein 4B
  t2i 1280×720 **20.1 s** (sampler 8.0 s, decode 5.4 s, text 5.3 s); Wan Draft task 01 through the app **236.7 s**, 7/7 pipeline
  checks (clip, proxy, lineage, harvest), lowest free VRAM 4.81 GB. Live enums unchanged (45 samplers / 9 schedulers).
  Rollback, if ever needed: `git -C engine/comfyui checkout v0.38.2` + `engine-setup.ps1 -SkipTorch`.
  Two setup-script fixes on the way: GitHub cannot serve a fetch by short hash (the node step now skips the fetch when the locked
  commit is checked out and fetches the remote fully otherwise), and PowerShell turned the expected non-zero exits of
  `git apply --check` into terminating errors under `Stop` — both made the script abort on a clean machine.
- **CI (first run on afac999 failed, both fixed).** (1) `npm ci` refused the lockfile: `openapi-typescript` pins TypeScript 5.x
  as a peer while the app is on TypeScript 6.0 — the generator is only run by hand, so it left `devDependencies` and the
  `api:types` script calls it through `npx`; the lockfile shrank by 362 lines and a clean clone now installs and builds.
  (2) Under `LOOM2_VARIANT=open` two tests assumed the full roster (dev is non-commercial, full only); both now check Klein 4B
  and expect dev only when the variant is full. Both variants: 89 passed.
- **Docs refresh (slice 5).** Status lines of 06 and 08–11 state the shipped milestones (the "proposed" line is kept as history);
  00's index covers D1–D33 / Q1–Q18, names the journal, the bench and the check scripts, and adds **15 · MVP click-through** —
  the author's guided end-to-end pass through the frame and the four suites with the automated twin of each step; 08 §10's
  lineage item is ticked (import → clip → three `frame-extract` children, five assets in the tree); 09 §10 ticks Klein
  references (M5) and records the Klein timing. **13** gained the **ordered post-MVP backlog** (Story workspace first, then the
  conform export step, Wan VAE time, LoRA slots, Klein refs in Edit AI / Fill Hero / SeedVR2, Animate extensions and H3,
  Edit 16-bit / clone / text / pen, Q15, frame and engine items).
- **M7 status:** slices 1–4 done, 3's bump done, 5's docs done. **What closes M7 is the author's click-through (15)** — its
  journal entry is the exit line of 12 §8; everything it leans on has an automated twin that passed tonight.

## 2026-10-07 07:44 — Final-milestone code review at eb44d38: bug register (C1–C32)

- Full read of `orchestrator/loom2` (api, queue, engine, media, tools), `frontend/src` (frame, store, all five suites, shell
  adapter), `src-tauri`, the scripts, CI and the offline tests, against 06/07/10/11. Baseline: 89 offline tests pass, `tsc -b`
  clean, `oxlint` warnings only, `cargo check` clean. C2, C3 (the persistence half), C4 (via the ComfyUI source) and C5 were
  reproduced with probe scripts before being recorded; C6's 500 was verified against Starlette; the rest are confirmed at the
  cited lines unless marked *plausible*. Status column is updated in place as fixes land (fixes get their own entries below).

  **Backend (orchestrator)**

  | Id | Sev | Where | Defect | Status |
  | --- | --- | --- | --- | --- |
  | C1 | high | `documents.py` `update_stack`; `api.py` `PUT /documents/{id}`; `editorStore.ts` `save()` | the client PUTs its whole stack and the server drops the pixels of every layer that stack does not list; an AI group inserted server-side (`queue._add_result_layer`) between the job's save and the client's merge is deleted when an autosave (every 120 s) or Ctrl+S lands first — the editor's merge then 404s on the layer and toasts "AI layer added" with nothing added; the engine output is already cleaned up. Window recurs per candidate of a batch | **fixed 08:03** |
  | C2 | high | `engine/supervisor.py` `wait_for_engine`; `queue.py` `_run_one` | the health poll runs to the timeout although the process already exited; a launch failure fails only that job and the loop takes the next → every queued job fails in turn (reproduced: engine script that exits at once, 3 jobs, all failed, queue not paused; 120 s each with the default timeout) | **fixed 08:03** |
  | C3 | high | `config.py` `Settings.variant` / `AppState`; `queue.py` `_validate_models`; `api.py` `/capabilities`, `PUT /settings`; `engine/graphs.py` `inpaint_model_id`; `generateStore.ts` `DEFAULT_PANEL`; `EditSuite.tsx` `AiTab` | D26 is not enforced: `LOOM2_VARIANT` only seeds the default and the persisted `app.json` value wins afterwards (reproduced: `open` shell → `full` runtime); `/jobs` accepts full-only model ids under `open`; the i2v capabilities are not filtered (LTX-2.3 offered); Fill Hero / Fill-Match / Remove force dev or Klein 9B (flux-nc) with no open fallback; Generate and the AI panel default to dev / Klein 9B / Klein 9B base / SAM 3; `PUT /settings` can change the variant | **fixed 08:03** |
  | C4 | high | `queue.py` `_finish_document_job` (Upscale, `as_layer`) | ComfyUI's LoadImage/SaveImage are RGB; the result is converted to RGBA with alpha 255 → the "1× detail layer" is opaque over the layer's whole box (an AI candidate's context ring and the area outside its mask become a hard-edged rectangle). Refine on the active layer carries `alpha_mask`; upscale does not | **fixed 08:03** |
  | C5 | medium | `catalogue.py` `make_thumbs`; `queue.py` + `api.py` `/thumbs`; `Tile.tsx` | one fixed temp name per size; the queue's thumbnail pass and `GET /thumbs` (requested by the grid as soon as `asset.created` arrives, status still pending) write the same file → one side raises, writes `thumb_status: failed` into the manifest and the index (reproduced 8/8 with two threads); the tile shows "no thumbnail" although the files exist | **fixed 08:03** |
  | C6 | medium | `catalogue.py` `_delete_files`; `clips.py`; `api.py` `GET /clips/{id}/proxy.mp4` | purging a clip proxy deletes proxy.mp4 + proxy.json only; `clips/<id>/master` and clip.json stay (`ClipStore.delete` has no caller); `/clips` still lists it and the proxy GET raises in `FileResponse` (500) | **fixed 08:03** |
  | C7 | medium | `queue.py` `_run_one`; `api.py` `put_settings` | `roster.scan()` (rglob over the mounted ComfyUI tree) runs synchronously on the event loop before every job and on every settings save | **fixed 08:03** |
  | C8 | medium | `queue.py` `stop()` / `_run_one` | a clean shutdown cancels `_run_one` anywhere; after `clips.create` / `_add_result_layer` but before `status=done` the job is re-queued and renders again on relaunch → duplicate clip or candidate | **fixed 08:03** |
  | C9 | low | `engine/contract.py` `check_graph` | a link is checked for output index only, never output type vs input type (06 §3b promises type matching) | **fixed 08:03** |
  | C10 | low | `engine/graphs.py` `estimate_vram_gb`; `recipes.py` `warm_group` | use `recipe.model_id`, not the model `inpaint_model_id` actually forces (Fill Hero admitted at the Klein estimate) | **fixed 08:03** |
  | C11 | low | `catalogue.py` `rebuild` | lineage edges are recreated with `kind=suite`; `frame-extract` becomes `animate` after a rebuild (the manifest never stores the kind) | **fixed 08:03** |
  | C12 | low | `catalogue.py` `ingest_file` | imported videos get no `w/h/frames/fps` | **fixed 08:03** |
  | C13 | low | `api.py` `documents_thumbnail` | `KeyError` → 500 on a foreign ORA without `mergedimage.png` | **fixed 08:03** |
  | C14 | low | `api.py` `/engine/free`, `/engine/stop`, `/engine/restart` | no guard against a running job | **fixed 08:03** |
  | C15 | low | `queue.py` `_follow` | completion detected through the history poll discards the engine's `status.messages`; the job reads "engine reported an error" | **fixed 08:03** |
  | C16 | low | `queue.py` `submit` | over-budget jobs are created `failed` but never `record_job`ed | **fixed 08:03** |
  | C17 | low | `documents.py` `save` / `update_stack` | `save()` reads `od.doc` several times on a worker thread while `update_stack` (another thread) can swap it → a rare inconsistent ORA | **fixed 08:03** |
  | C18 | low | `engine/client.py` `events`; `engine/supervisor.py` `start` | the event pump reconnects every second forever while the engine is stopped; one `engine-*.log` per start, never pruned | **fixed 09:37** |
  | C19 | low | `workspace.py` `create` | refuses when free space < size cap, so the default 100 GB cap fails on a disk with less than that free | **fixed 09:37** |
  | C32 | high | `engine/graphs.py` `build_segment` (SAM 3 box) | `SAM3_Detect.bboxes` was wired to `CreateBoundingBoxes` output 0 (the preview IMAGE); the BOUNDING_BOX is output 1 — found by C9's new type check; box mode was not among the M5 acceptance's prompts | **fixed 08:03** |

  **Frontend and shell**

  | Id | Sev | Where | Defect | Status |
  | --- | --- | --- | --- | --- |
  | C20 | high | `editorStore.ts` `mergeServerLayers` | adopts the server stack when an AI result lands: layers added / reordered / renamed during the job (minutes for hero jobs) vanish from the stack (canvases wait in `pixels` for gc); `docDirty` not set; Undo also removes the AI group | **fixed 08:03** |
  | C21 | medium | `EditorCanvas.tsx` scene sync | every revision `removeChildren()`s the layer and overlay containers and recreates the ants / prompt / guide / transform / frame `Graphics` and the background rect without `destroy()` → GPU geometry per stroke. *Plausible*, not measured | **fixed 08:03** |
  | C22 | medium | `src-tauri/src/lib.rs` `repo_root`; `ci.yml`; README | release builds bake `CARGO_MANIFEST_DIR` (the CI runner's path); the installer bundles neither venv nor engine; `LOOM2_REPO` / `LOOM2_ORCH_CMD` are documented only in the journal | **fixed 08:03** |
  | C23 | low | `generateStore.ts` `loadSnippets`; `GenerateSuite.tsx` `PresetsTab` | field presets load only when the Presets tab mounts; the preset menus lack the user's presets until then | **fixed 08:03** |
  | C24 | low | `AnimateSuite.tsx` `Filmstrip` | up to 40 full-size master PNGs as thumbnails | **fixed 09:37** |
  | C25 | low | `animateStore.ts` `MODEL_RULES` | duplicates the server's `I2V_RULES` | **fixed 09:37** |
  | C26 | low | `src-tauri/src/lib.rs` `reveal_path` | `explorer /select,<path>` through Rust's argument quoting likely breaks on paths with spaces. *Plausible* | **fixed 08:03** |
  | C27 | low | `ProjectDialog.tsx` | hard-coded `F:/loom2-projects/` | **fixed 08:03** |
  | C28 | low | `compose.py` `render_nodes` vs `EditorCanvas.tsx` `build` | a group with a *disabled* mask is isolated in Python and pass-through on the GPU; `clip` on groups differs too (visible only with non-normal child blends) | **fixed 09:37** |
  | C29 | low | `store/session.ts` previews | blob URLs of finished jobs are never revoked | **fixed 08:03** |
  | C30 | low | `EditorCanvas.tsx` `pick` | the eyedropper reads premultiplied pixels (darker over semi-transparent areas) | **fixed 09:37** |
  | C31 | low | `editorStore.ts` `openDocument` | no in-flight guard; two concurrent opens leak the loser's textures | **fixed 08:03** |

- **Test gaps:** nothing covers variant enforcement at `/jobs`, the upscale layer's alpha, purging a video asset, concurrent
  `make_thumbs`, an engine that fails to launch with several jobs queued, a stale stack PUT, or link types in the contract check.
- **Solid:** the durable queue with atomic writes and quarantine; the B1–B24 fixes present and tested; blob sha verification;
  the W3C blend shaders match `compose.py` formula for formula; the command registry; on-demand rendering; the fake-engine harness.
  Fix order: C1 + C20 together (stack revision on the server, merge instead of replace in the editor), C2, C3, C4, then C5–C8,
  then the low items that are one-liners (C9–C16), then C21/C22.

## 2026-10-07 08:03 — Review fixes C1–C17, C20–C23, C26, C27, C29, C31 landed; C9's type check found C32

- **C1 + C20 (the editor and the queue writing the same document).** `Document` gained `revision` (documents.py): every stack
  replace bumps it, and so does every layer the queue inserts (`_add_result_layer`). `PUT /documents/{id}` with a stack based on an
  older revision is refused with **409** (`StaleStack`); a body without `revision` is accepted as before (legacy callers). The
  editor's `save()` catches the 409, runs `resync()` and saves the merged stack; `mergeServerLayers` now **merges** the server's new
  group or layers into the *local* stack (later candidates join the group already there) instead of adopting the server stack, so
  layers added, moved or renamed while a job ran survive. Outpaint sends `shift {left, top}` in `document.changed`; the editor shifts
  its own raster layers, unlinked masks and the selection by it (inferred from a common layer on the resync path). `update_stack`
  runs under the document's save lock (C17). Test: `test_c1_stale_stack_put_is_refused_and_server_added_layers_survive`.
- **C2.** `wait_for_engine` takes `alive=` (the supervisor passes `proc.poll() is None`) and returns as soon as the process is gone;
  the error names the exit code. `JobQueue._run_one` catches the launch failure before anything else: the job goes back to
  **queued**, the queue **pauses**, `queue.state` and `job.updated` are broadcast — the "Engine down" banner carries the reason and
  Restart, the "Queue paused" banner Resume. Test: `test_c2_engine_launch_failure_requeues_the_job_and_pauses` (an engine that
  exits with code 3; two jobs; paused within seconds, both still queued, none failed).
- **C3 (D26 enforced).** `AppState(state_dir, variant)` / `create_app(..., variant)`: `main.py` hands `LOOM2_VARIANT` over and the
  value overrides whatever `app.json` holds, on load and after every settings update; `PUT /settings` drops `variant`. The queue's
  `_validate_models` walks `graphs.recipe_weights(recipe, variant)` (transformer, text encoder, VAE, Turbo LoRA, upscaler, segmenter,
  the full i2v set) and refuses any id without the `open` tag with a 422 that names the licence. `inpaint_model_id` moved to
  `recipes.py` with a `variant` argument (Fill-Match / Remove fall back to Klein 4B under `open`; Fill Hero is refused);
  `estimate_vram_gb` / `warm_group` use it (C10). `/capabilities.i2v` is filtered (LTX-2.3 is full only). Frontend: the AI panel maps
  its choices onto the open models (Klein 4B, Klein 4B base; no Fill Hero, no dev hero, no SAM 3), Generate falls back from a model
  the build does not list to Klein 4B, Animate lists only the models the capabilities carry. Tests that rely on full-only weights
  pin `"variant": "full"` in their settings (CI's `open` matrix still runs the dedicated open tests). Tests:
  `test_c3_shell_variant_wins_over_the_persisted_one_and_settings_cannot_change_it`,
  `test_c3_open_variant_rejects_full_only_weights_and_filters_capabilities`.
- **C4.** Upscale keeps `alpha_mask` (the active layer's alpha, or the composite's) and the detail layer is assembled with
  `edit_ai.assemble_layer`, like refine. Test: `test_c4_upscale_detail_layer_keeps_the_source_alpha` (left half transparent stays
  transparent, the engine's colour lands where the layer is visible).
- **C5.** A probe showed the unique temp name alone is not enough: two `replace()`s onto one destination still lose with
  `PermissionError` on Windows (4 of 20 runs). `make_thumbs` now takes a **per-asset lock**; the second maker finds the files and the
  `done` record and returns it. Test: `test_c5_concurrent_thumbnail_makers_both_succeed` (12 of 12 done, no temp files left).
- **C6.** `_delete_files` removes `clips/<id>/` when the purged asset is the proxy inside it; `GET /clips/{id}/proxy.mp4` answers
  404 when the file is gone. Test: `test_c6_purging_a_clip_proxy_removes_the_whole_clip`.
- **C7** `roster.scan()` in a thread (queue and settings). **C8** `job.resumable = False` once the engine has finished (persisted);
  `stop()` waits up to 30 s for the finalisation of such a job with the queue held, and a job that is still finalising when the
  wait ends is marked failed ("interrupted while its outputs were being written") instead of re-queued; `load()` already treated a
  non-resumable running job that way. **C9** `check_graph` compares the linked output's type with the input's (both plain strings,
  `*` excluded). **C11** `AssetRecord.lineage_kind` is stored and used by `rebuild`. **C12** imported videos are probed with PyAV.
  **C13** 404 instead of a KeyError. **C14** `/engine/stop|restart|free` answer 409 while a job runs. **C15** the history fallback
  keeps the engine's `execution_error` message and traceback, and recognises an interrupt. **C16** refused jobs are `record_job`ed.
- **C32 (new, found by C9).** The SAM 3 **box** graph wired `SAM3_Detect.bboxes` to `CreateBoundingBoxes` output **0** — the preview
  IMAGE; the BOUNDING_BOX is output **1**. The fixture confirms the outputs (`preview, bboxes, elements`); ComfyUI's own validation
  would have rejected the prompt at run time (box mode was not among the M5 acceptance's exercised prompts). Fixed, and the m5b test
  that asserted the wrong index corrected.
- **Frontend.** C21: the scene rebuild destroys the layer sprites, mask wrappers, pass contents and the background rect, keeps the
  labelled overlay Graphics (cleared and redrawn in place, re-ordered above the sprites) and reuses two ColorMatrix filters —
  `Graphics.destroy()` is what frees the GPU context, so this was a real leak per revision. C23: field presets load with the Generate
  panel. C27: the new-project path defaults next to the last project. C29: a finished job's preview blob URL is revoked. C31:
  `openDocument` is sequenced; a superseded load frees what it fetched.
- **Shell.** C22: `repo_root()` falls back from `LOOM2_REPO` to the built path only if it holds `orchestrator/`, else to the nearest
  ancestor of the executable holding `orchestrator/.venv`; the spawn error names the fix; README documents the installer's
  dependence on a checkout. C26: `explorer /select,"<path>"` through `raw_arg`.
- **Not done:** C18 (event pump reconnect loop while the engine is stopped; engine logs unpruned), C19 (free-space < cap refusal at
  project creation — a design question), C24 (filmstrip full PNGs), C25 (`MODEL_RULES` duplication), C28 (group pass-through
  parity on a disabled mask / clip), C30 (eyedropper premultiplied).
- **Verification:** offline suite **97 passed** (89 + 8 new in `tests/test_review_c.py`), `tsc -b` clean, `oxlint` warnings only
  (unchanged set), `cargo check` clean. Not yet re-run on the rig: the M5 acceptance (SAM 3 box mode after C32), an `open` launch
  through the shell, and the M7 durability script (C8 changes the shutdown path).

## 2026-10-07 08:41 — Rig re-check of the review fixes: M5 acceptance, SAM 3 box (C32 second half), M7 durability 11/11, `open` launch

- **M5 acceptance** (`scripts/m5_acceptance.py --port 8766`, dev orchestrator on the repo's `.loom2_state`, fresh project
  `F:/loom2-projects/acceptance-20261007-0815`): **23/25** — every generative check passed with the new code (fill 86.4 / 39.4 s,
  fill_match 19.7 s, remove 19.9 s, cloak 40 s ×2, face 47 s, outpaint 31 s → 1200×544, refine 45 s, upscale 4.1 s with the
  Catalogue asset, BiRefNet 2.6 s face 0.96 / crates 0.00, background swap alpha on subject 0.027 / background 0.996, SAM 3 text
  32.5 s, SAM 3 point 3.2 s, tiled refine 2400×1088 over 6 tiles, 21 nodes saved). The two failures were the **SAM 3 box** case
  the script gained this morning (the acceptance had never exercised box mode): after C32's output-index fix the engine refused
  the prompt for a second reason — `CreateBoundingBoxes.editor_state: []` is read by ComfyUI's API validator as a *link*
  ("Bad linked input, must be a length-2 list"). Any list value is a link to `validate_inputs`; the canvas state must be empty
  for the JSON `bboxes` to win (`editor_state or []`), so the graph now sends `{}`. Re-run on the rig after an orchestrator
  restart: **box mode works** — job 25.4 s, cloak box 0.68, crates 0.00, canvas 0.17. C32's row updated.
  Side notes: the script's end-of-run crash (`a.keep` on a numpy array; the background-swap block shadowed the argparse namespace,
  also seen at M5 close) is fixed by renaming. **Tiled refine took 892 s against 439 s at M5 close** for the same graph and
  tile count — not touched by this review; to be measured in isolation (ComfyUI v0.39.0 bump? resident weights after the SAM 3 /
  BiRefNet jobs with `--reserve-vram`?) before it is called a regression.
- **M7 durability, rig half** (`scripts/m7_durability.py --project F:/loom2-projects/m6-acceptance`): **11/11**. Power loss
  mid-clip: the engine died with the orchestrator in 0.1 s, the relaunch came up paused with the job re-queued (retry 1, no recovery
  notes), the re-queued clip finished in 248.4 s with 81 frames and a 1.6 MiB proxy. Engine crash mid-clip: the job failed with an
  engine error in 9 s, the orchestrator kept answering, the next job started a fresh engine in 6 s. C8's shutdown change (non-
  resumable finalisation) did not alter either path.
- **`open` launch through the entry point** (`LOOM2_VARIANT=open python -m loom2.main` on a state dir whose `app.json` persisted
  `full`): `/health` and `/settings` say `open`, `/capabilities` lists `klein-4b` and `klein-base-4b` only and Wan alone under i2v,
  `PUT /settings {variant: full}` answers `open`, `POST /jobs` refuses dev (422, "flux-nc … not part of the open variant (D26)")
  and LTX-2.3 ("ltx-2.x community") and accepts Klein 4B, and the persisted `app.json` now reads `open`. The shell itself
  (`LOOM2_VARIANT` baked by `option_env!`, handed over as the environment variable) was not driven; it passes exactly what this
  test set.
- Offline suite 97 passed, `tsc -b` clean, `oxlint` unchanged, `cargo check` clean. Committed as the review-fix commit.

## 2026-10-07 09:37 — Register closed (C18, C19, C24, C25, C28, C30); the tiled-refine timing is DynamicVRAM's cold start, measured, with the `--disable-dynamic-vram` control

- **Open items landed.** C18: the engine event pump ends when there is no engine to listen to (`_ensure_ws` restarts it with the
  next job) and `start()` keeps the last ten `engine-*.log` files. C19: project creation refuses only below the 10 GB floor — the
  size cap is the project's ceiling, the disk guard polices growth; a 100 GB cap on an 80 GB drive now works. C24:
  `GET /clips/{id}/frames/{n}.png?size=S` serves a cached WebP thumbnail (`clips/<id>/strip/`), the filmstrip asks for 352 px
  instead of 40 full master PNGs. C25: `animateStore.modelRules(id)` reads fps / frames / step / multiple / tier sizes from
  `/capabilities.i2v` once loaded; `MODEL_RULES` stays as the fallback and the source of the short labels. C28: `compose.py`'s
  group pass-through rule now matches the editor's — a *disabled* mask is no mask, `clip` isolates. C30: the eyedropper
  un-premultiplies what `extract.pixels` hands back. Tests: `test_c19_…`, `test_c24_…`, `test_c28_…` → **100 offline tests**;
  `tsc -b` clean, `oxlint` unchanged. Every register row is now fixed.
- **Tiled refine 892 s (acceptance) vs 439 s (M5 close): resolved — not a regression of the review or the pin.** Same job
  (upscale ×2 + Klein 9B base, 1200×544 → 6 tiles of 1024 / 128, 0.25), fresh engine, run twice back to back on the default flags:
  **cold 1156.7 s** (KSampler Σ 1102.7 s = 184 s per tile, 9.2 s/step; VAE enc 10.8 / dec 23.7 s; loaders 0.3 s) then **warm 262.2 s**
  (KSampler Σ 221.8 s = 37 s per tile, 1.85 s/step). The weights load *inside* the samplers under DynamicVRAM (the loader nodes take
  0.3 s; the log says "prepared for dynamic VRAM loading … 8658 MB staged" for Flux2 and 8262 MB for the Qwen3-8B encoder — more than
  16 GB together), and the first job streams for its whole length. This is E0's hypothesis (2), "DynamicVRAM residency varying job to
  job" (journal 2026-10-04), measured: 439 s at M5 close was a partially warm engine. **Control, `--disable-dynamic-vram`
  (E0's planned check):** the same job cold → **249.7 s** (37 s per tile; the log says "loaded completely; 12234 MB usable, 8658 MB
  loaded, full load: True"). But the same flag on **FLUX.2 dev Turbo 960×544: 201.0 s cold, 176.9 s warm** (KSampler 164 / 175 s =
  22 s/step) against ≈ 40 s with streaming (E0) — the classic partial-load path thrashes the 34 GB transformer. **Decision: keep
  DynamicVRAM on** (the dev path needs it; D21/D29 make dev the hero); the Klein 9B base first-job penalty (≈ 15 min once per engine
  start, then ≈ 4 min) is a known cost, recorded in 13's backlog as an engine-profile item (restart with `--disable-dynamic-vram`
  for a Klein-only session, or ComfyUI's `--vram-headroom` / pinned-memory tuning, or a fused-weights load before the first tile).
  The engine's flags are editable in Settings → Engine already. Settings and engine were restored to the defaults afterwards.
- Also run today: `scripts/m5_acceptance.py` gained the SAM 3 box case (C32) and lost its end-of-run crash; the `open` launch
  check and the M7 durability script passed (08:41). Dev orchestrator stopped; nothing left running on 8188 / 8766.

## 2026-10-07 10:36 — The VRAM clash behind the slow Klein 9B jobs, isolated: text encoder vs transformer under DynamicVRAM

- **Cause, measured.** Every slow case today had the Klein 9B family's Qwen3-8B encoder (8.2 GB staged) and the Klein transformer
  (8.6 GB) on the card together; `load_models_gpu` asks for ≈ 1.1× the transformer plus the reserve, DynamicVRAM keeps the
  encoder resident and streams the transformer for the whole job. Same tiled refine (6 tiles, 20 steps): **9.2 s/step** streamed
  (cold, 1157 s), **1.85 s/step** when the transformer fits (warm 262 s; `--disable-dynamic-vram` 250 s). The acceptance showed
  the same shape on Klein 9B fills: candidate 1 **86 s**, candidate 2 **39 s**. It is not a first-load effect: in the same engine
  session a plain refine on Klein 9B base took 45 s minutes before the tiled refine took 892 s.
- **Control 3: text encoder on the CPU** (`te_device: cpu`, now a field of the I2I / Inpaint / Upscale recipes like T2I's — CLIPLoader
  `device`): sampling back to **38.7 s per tile** (the transformer loads completely), but the Qwen3-8B fp8 encoder on the CPU
  takes **310 s** per new prompt → wall 905 s. Not a fix on its own (E0 found the same for Mistral: 170 s).
- **Design that removes the clash: two-phase prompts with a conditioning cache.** Core v0.39.0 has `SaveConditioning` (writes a
  safetensors to the output folder, tensor options such as reference latents included) and `ConditioningLoader` (reads it from
  the `embeddings` folder, which `extra_model_paths.yaml` already mounts). The queue would run phase A — CLIPLoader + CLIPTextEncode
  (+ FluxGuidance / ReferenceLatent) + SaveConditioning — then `/free` with `unload_models`, move the file into
  `<models>/embeddings/loom2-cond/<sha of te_id + text + refs>.safetensors`, refresh `/object_info`, and run phase B — UNETLoader + VAE
  + ConditioningLoader + sampler — with the whole card for the transformer. Expected: Klein 9B jobs at the warm rate from the
  first candidate (≈ 250 s for this tiled refine, ≈ 40 s per fill), phase A ≈ 30 s once per distinct prompt (the dev run's GPU
  text encode measured 32.7 s) and **zero** for the other candidates of a batch, re-runs and variations, which share the cached
  conditioning; dev (34 GB, streamed regardless) should also gain from losing the 17 GB Mistral during sampling — to be measured.
  Apply it when `transformer + text_encoder > usable VRAM` (roster sizes vs `vram_budget_gb − reserve_vram_gb`), i.e. the Klein 9B
  family and dev; Klein 4B (7.2 + 7.5 GB, measured fine) stays single-phase. The two nodes are not in the captured fixture yet
  (`scripts/make_object_info_fixture.py` recapture when the graphs use them). Alternative with no graph change: an engine profile
  per warm group (`--disable-dynamic-vram` restart for Klein-only sessions; 250 s cold) — cheaper to build, costs a restart on every
  dev ↔ Klein switch and leaves dev streaming. Recorded in 13's backlog (item 10) with the numbers; no decision taken here.

## 2026-10-07 12:58 — Quantized Qwen3-8B encoder for Klein 9B: the VRAM clash gone (cold tiled refine 279 s vs 1157 s), three GGUF sizes measured

- **Question (10:36 follow-up):** can a quantized encoder keep the Klein 9B pair resident? There is no encoder-only Klein GGUF
  anywhere (unsloth's Klein repos carry the transformer only, city96 has no Qwen3 encoder); the plain llama.cpp quantizations of
  Qwen3-8B (`unsloth/Qwen3-8B-GGUF`) load through ComfyUI-GGUF's `CLIPLoaderGGUF` — the pinned commit lists `qwen3` in its
  `TXT_ARCH_LIST`, core's `flux2` type detects Qwen3-8B by shape and builds `klein_te(model_type="qwen3_8b")`, the token embedding
  is dequantized to fp16 at load (+1.2 GB). The 4B family needs the 4B GGUF (hidden size), so the alternates are per preset.
- **Wired:** roster `qwen3-8b-q4km` / `qwen3-8b-q4ks` / `qwen3-8b-q3km` (`text_encoders`, apache-2.0; fetched with the app's own
  roster tool through `/models/fetch`, ledgered with sha256 — 5.03 / 4.80 / 4.12 GB, 13 min for the three); recipe `te_id` on T2I /
  I2I / Inpaint / Upscale → `graphs.resolve_te_id` (the preset's encoder or a `TE_ALTERNATES` entry, anything else a CompileError —
  the 4B encoder on a 9B model would otherwise surface as a mat1/mat2 shape error inside the engine); `_te_loader` emits
  `CLIPLoaderGGUF {clip_name, type: flux2}` for a `.gguf` (the node has no `device` input, so `te_device: cpu` + GGUF is a
  CompileError); `recipe_weights`, the open gate, `/recipes/preview` and `effective_params` see the override; `_validate_models`
  rejects a bad one with a 422 at submission; `/capabilities.te_alternates` publishes the map (and `types.ts` carries it). Fixture
  recaptured with `CLIPLoaderGGUF` (69 classes; `make_object_info_fixture.py`); `tests/test_te_gguf.py` → **104 offline tests**.
- **Measured** — default flags, each encoder on a stopped engine (scratch `te_experiment.py`: tiled refine cold → warm → two Klein
  9B T2I renders at 1280×720, seed 7; the tiled job is the 09:37 one: 1200×544 → 6 tiles of 1024 / 128, Klein 9B base, 0.25):

  | encoder | file / resident | tiled **cold** wall | KSampler per tile | tiled warm wall | text encode | encoder load |
  | --- | --- | --- | --- | --- | --- | --- |
  | fp8mixed (09:37 runs) | 8.07 GB / 8.26 GB staged | **1156.7 s** | 184 s (9.2 s/step) | 262.2 s | — | 0.3 s |
  | Q4_K_M | 5.03 / 6.83 GB | **279.1 s** | 36.8 s (1.84 s/step) | 263.6 s | 1.0 s | 5.5 s |
  | Q4_K_S | 4.80 / 6.61 GB | **280.5 s** | 36.9 s | 265.2 s | 1.0 s | 5.5 s |
  | Q3_K_M | 4.12 / 6.05 GB | **281.9 s** | 36.9 s | 266.1 s | 1.1 s | 6.0 s |

  The GGUF encoder takes the classic load path even with DynamicVRAM on (engine log: `loaded completely; 13292 MB usable,
  6829 MB loaded, full load: True`), is reloaded per job (≈ 5 s, from RAM) and the transformer samples at the resident
  1.85 s/step from the first tile: cold now equals warm, the 4.4× first-job penalty is gone, and the three quantizations are
  indistinguishable in time. Klein 9B T2I (distilled, 1280×720, two prompts back to back): with a GGUF 17.5 s then 10.1 s wall
  (KSampler 5.6 / 4.5 s, every run); with fp8 26.1 s then **54.1 s** (KSampler 5.7 s, then 47.1 s = 11.8 s/step with 2.9 GB free)
  — the fp8 pair's residency is erratic job to job, the GGUF pair's is not.
- **Quality, same seed, by eye:** Q4_K_M and Q4_K_S are near-identical to fp8 — composition, props, the "HARBOUR MARKET" sign,
  the crossed arms, the lamp key light; fp8 misses "hood down" exactly as the GGUFs do, so that is the model, not the encoder.
  Q3_K_M drifts a little (the cabin woman's face drops into profile instead of the three-quarter view; a second clock appears).
  PNGs live in the session scratchpad only.
- **Not decided here:** making Q4_K_M the three 9B presets' default encoder (and retiring the 8.7 GB fp8 file), and an encoder
  picker in the AI / Generate panels. Q4_K_M is the recommendation — the same speed as Q3_K_M, the closest to fp8. dev is
  untouched (its 34 GB transformer streams regardless), so the two-phase conditioning cache stays the dev fix (13, item 10).
  Settings and engine flags unchanged; dev orchestrator stopped afterwards.

## 2026-10-07 16:01 — D31: the Klein 9B presets default to the Q4_K_M GGUF encoder, fp8 stays as the alternate, encoder picker in both panels

- **Decision (user, after the 12:58 measurements):** Q4_K_M becomes the text encoder of `klein-9b`, `klein-base-9b` and `klein-9b-kv`;
  the Comfy-Org fp8 repack stays on disk as the alternate a recipe may name; Q4_K_S and Q3_K_M go (same speed, nothing to choose
  between them). Recorded as D31 in 13; the backlog paragraph in item 10, 04's model table, 09's Advanced row and 10's AI table updated.
- **Weights:** `scripts/prune_weights.py Qwen3-8B-Q4_K_S.gguf Qwen3-8B-Q3_K_M.gguf` — 8.31 GiB freed, both ledger rows dropped; the
  roster entries carry `retired="D31 …"` (D30 convention: re-fetchable, skipped by the panels).
- **Code:** `PRESETS[…9B].te_id = "qwen3-8b-q4km"`, `TE_ALTERNATES = {"qwen3-8b-q4km": ["qwen3-8b-fp8mixed"]}`, `TE_LABELS`,
  `te_options(preset)` (the preset's encoder first). `/capabilities.models[id]` gained `te_id` and `te_options`
  (`{id, label, name, health, approx_gb, gguf, default}`) so a panel needs nothing else to draw the picker. **Generate · Advanced**:
  the "text encoder" row is now the encoder select (rendered only where a model has more than one option — the 4B family and dev
  have none) next to the device select, which is a disabled "GPU" while a GGUF is the effective encoder (`CLIPLoaderGGUF` has no
  `device` input); an effect clears a persisted `te_id` that no longer pairs with the chosen model and a persisted `cpu` under a GGUF,
  so the preview never shows a stale 422. **Edit AI panel**: `EncoderPick` under Inpaint's mode, Outpaint's model, Refine's model and
  the tiled-refine model (`aiPanelStore.teId`, one choice for the panel, sent only where it pairs — a dev outpaint ignores it).
  Tests follow the decision (`test_te_gguf.py`: roster + presets, default graph = `CLIPLoaderGGUF` and `te_id: fp8` = `CLIPLoader`,
  retired / mismatched / `cpu`-under-GGUF errors, weight list + 422 + capabilities) and the 9B test trees carry the GGUF file →
  **104 offline**; `tsc -b` clean; oxlint +1 (`only-export-components` for `EncoderPick`, the warning every component in that file has).
- **Rig (dev orchestrator on 8766, cold engine, `scratch d31_check.py`):** default Klein 9B T2I → `gguf qtypes: Q6_K (37), F32 (145),
  Q4_K (217)` in the engine log, 29.9 s wall; `te_id: qwen3-8b-fp8mixed` → `Flux2TEModel_ … 8262MB Staged`, 36.9 s; fp8 +
  `te_device: cpu` → 345.6 s (the CPU encode measured at 10:36, now only reachable through the alternate); `te_id: qwen3-8b-q3km`
  → **422** "does not pair with this model (it takes qwen3-8b-q4km or ['qwen3-8b-fp8mixed'])"; Edit Refine on `klein-base-9b` through
  `/documents/{id}/ai` → GGUF, 34.5 s. Headed Edge (CDP, the `edit_headed_check.py` helper) screenshots of both pickers: Generate ·
  Advanced with the default and with fp8 chosen (device select re-enabled, hint flips), Edit AI Inpaint / Refine / Upscale + tiled
  refine; no page errors beyond the pre-existing LoRA-slots key warning. Dev orchestrator and engine stopped afterwards.

## 2026-10-07 19:48 — Dark / Light pastel theme, switchable in Settings and the ☰ menu

- **Why:** the Catalogue redesign mockups (`../proto01_design/01-catalogue-inventory.md`, Claude Design canvas) were drawn in a light
  pastel variant as well; the author asked for both in the app, switchable in Settings.
- **Tokens:** `frame.css` `:root` (dark, unchanged values except `--fg3` `#747474 → #8c8c8c` for 4.5:1) and
  `:root[data-theme="light"]`, plus the tokens the hard-coded CSS colours needed: `--accent-fg` (text on the accent), `--media-bg`
  (thumbnail wells), `--deep` (loupe / compare / player), `--canvas-bg` + `--checker-a/b`, `--overlay` / `--overlay-weak` (badges over
  media), `--shadow` / `--shadow-strong` / `--scrim`, `--ring-gap`, and state tints (`--keep-bg`, `--info-bg/-fg`, `--reject-bg/-fg`,
  `--open-bg/-fg`); `color-scheme` per theme so native controls follow. `frame.css`, `menu.css`, `animate.css`, `catalogue.css`,
  `edit.css`, `generate.css` now hold no colour literals except the white label drawn over candidate images in Edit.
- **Switch:** `ui.theme` in the session store (persisted in `loom2.ui`; the persist merge is now field by field so layouts saved before
  a UI field existed keep its default); `frame/theme.ts` (`THEMES`, `applyTheme`, `CANVAS_COLOURS`); `main.tsx` applies the theme
  before the first render and takes `?theme=light|dark`; Settings · App gets Theme (the empty App heading now holds Theme, Density,
  Thumbnail sizes, Log level; Licences below), the ☰ menu a Theme toggle next to Density. The editor's Pixi background and checker
  follow `CANVAS_COLOURS` at boot and on a switch (store subscription; old checker texture destroyed). Image-content colours (brush
  defaults, palette swatches, transform / AI-box overlays) stay as they are.
- **Checks:** `tsc -b` clean, oxlint unchanged (no new warnings), `vite build` ok. Headless Edge screenshots of the production build
  against a live orchestrator (`scratch theme_shots.py`, the `csp_check.py` harness): Catalogue, loupe, Generate, Animate, Models and
  Edit in light, Catalogue and Edit in dark, no page errors (the Edit stage's "unsafe-eval" toast appears in both themes — headless has
  no WebGPU and the WebGL path needs eval under the CSP; not new). Headed Edge `edit_headed_check.py paint` with `EXTRA=&theme=light`:
  all checks passed on WebGPU, light canvas surround and light checker under the erased mask band. Not exercised in a window: switching
  the theme while a document is open (the subscription path).

## 2026-10-07 20:26 — D34 implemented: Places, filter chips, album pages, split Stage, one-column Inspector, lineage view

The Catalogue redesign of `../proto01_design/01-catalogue-inventory.md` (slices 1–7 of its §13), in the order backend → frame →
Inspector → lineage → split → pages.
- **Groups backend** (`loom2/groups.py`, D34): one atomic JSON record per group in `groups/` (`album.json` the root page), items =
  assets or groups at free `x, y, w, z`; one placement per item (moving takes it off its old page; a hand-edited double placement keeps
  the most recent at load), no cycles, orphans back onto the Album; `revision` per group → 409 on a stale layout write. The index
  caches asset placements (`placements` table, rewritten from the files at every open): `folder=unprocessed` (not placed, not
  trashed), `group_id=`. Group / ungroup keep layouts; deleting a group frees its assets to Unprocessed (nothing trashed); purge
  forgets placements. **Duplicate** (`Catalogue.duplicate`): a new asset id, the file and thumbnails copied, `duplicate_of`, no lineage
  edge. **Migration** at the first open with groups: each collection (manual, or a smart one frozen) becomes a group card on the
  Album; an asset in several collections stays in the oldest and is duplicated into the others; a recovery note says how many.
  `date_preset` (today / last_session / 7d / 30d) resolved server-side like B11's today. `/collections*` routes removed (the methods
  stay for the migration). API: `/groups/tree|where|move`, `/groups/{id}` (+ `/items`, `/group`, `/ungroup`, `/duplicate`),
  `/assets/duplicate`, `lineage/tree` gains `locations`; WS `group.changed`. `openapi.json` re-exported (it was several milestones
  stale) and `schema.d.ts` regenerated. Tests: `test_groups_d34.py` (11) → **115 offline**.
- **Drag and drop by pointer events** (`frame/drag.ts`): Tauri's default OS file-drop handling (kept: it delivers dropped files with
  paths for imports, `shell/tauri.ts listenFileDrop`) leaves WebView2 without HTML5 drag events inside the page, so the existing drop
  sites (suite tabs, Generate reference slots, Animate slots and beats, the Edit stage and its empty state) and the new ones (Places
  rows, panes, pages) all register with one manager; `carry` hands a page's own item drag over when the pointer leaves the page.
- **Frame:** `SuiteDef.wideStrip` puts the Catalogue strip across panel, stage and inspector; one rail tab (Places); no panel foot.
- **Catalogue:** Places (Unprocessed, Library, the Album tree with counts / drop targets / menus, Trash with Empty trash); the
  fixed-slot strip (place or breadcrumb · search + filter chips + "+ Filter" + clear · count · sort · selection chip · compare tray ·
  Split · Import split button · zoom, page zoom + Fit on a page; loupe / compare / lineage reduce it to Back); filters as chips
  (`filters.ts`: state incl. unjudged, type, source, model, rating, date presets + range, tags, aspect, derivations, batch via "Show this
  batch", lineage); group-by retired in the Catalogue (store key `loom2.catalogue.v2`, opens on Unprocessed); Settings · Catalogue
  (thumbnail fit / fill, tile caption off by default); one-column Inspector (Judge, Tags always there — §10 finding 1 —, Location with
  breadcrumb / Move to / Back to Unprocessed / Duplicate, Actions + More, Lineage path, Prompt and Details folded, ids only in Details;
  bulk version with Group these; a card version for a selected group); lineage view (tree layout, edge kinds, each card's location;
  ⤷ badge, `L`, menus); split Stage (single / stacked / side by side, `split.ts`, two stores, the strip / Places / Inspector / commands
  follow the active pane, pane headers and menus, Unprocessed / Trash panes take drops); album pages (`PageView.tsx`: free move with
  live preview, resize handle, marquee, wheel / Ctrl+wheel / middle- or Space-drag, Ctrl+G / Ctrl+Shift+G, Del → Unprocessed with Undo,
  arrows nudge, Ctrl+Z layout undo, Ctrl+drag duplicates, cards with a cover fan, filters highlight instead of hiding, "Use as cover").
  New commands: duplicate (Ctrl+D), show this batch, back to Unprocessed, import, show lineage; Empty trash from a menu asks and runs
  (§10 finding 2); the loupe's pin is the command (finding 6). Deep links `place=`, `split=`, `place2=`, `select=`, `lineage=`.
- **Checks:** `tsc -b` clean, `vite build` ok, oxlint: no new warnings beyond the patterns the codebase already carries. Headless Edge
  screenshots (dark and light) of Unprocessed, Library, a group page, Trash, the loupe, the Inspector, the lineage view, stacked and
  side-by-side splits and the Album page; no console errors. Interaction run over CDP with real pointer and key input against a live
  orchestrator (`scratch cat_interact.py`): tile → page, move on the page + Ctrl+Z, a page photo carried onto a Places row,
  click + Ctrl+click + Ctrl+G (dialog) → group and card + tree row, Del → Unprocessed + Undo toast, tile → group row, tile → Trash,
  Ctrl+drag duplicate, double-click card → its page, breadcrumb back — **17/17**; tile → Generate tab (reference) and → Edit tab
  (document) pass. Not run: the desktop app itself (OS file drop into the grid, pointer drags in WebView2), Generate's results with
  the shared Inspector beyond the screenshots.

## 2026-10-10 09:33 — D34 and the theme committed: checks re-run on the tree as committed

- **What goes in:** the 2026-10-07 19:48 theme pass and the 20:26 D34 Catalogue pass, unchanged since then — `loom2/groups.py`,
  `catalogue.py` / `api.py` (groups, placements, duplicate, `date_preset`, `/collections*` routes removed), `frame/drag.ts`,
  `frame/theme.ts`, the Catalogue rewrite (`Places`, `Panes`, `split.ts`, `PageView`, `LineageView`, `Inspector`, `CatalogueStrip`,
  `filters.ts`, `albumStore.ts`), the touched frame / suite files, the re-exported `openapi.json` + `schema.d.ts`, the specs (07, 08, 13
  D34) and `../proto01_design/01-catalogue-inventory.md`.
- **Checks today:** `pytest orchestrator -q` **115 passed** in 38 s (104 before D34 + 11 in `test_groups_d34.py`); `npm run build`
  (`tsc -b` + `vite build`) ok — only the existing chunk-size and ineffective-dynamic-import warnings.
- **Still not run** (as on 2026-10-07): the desktop app itself — OS file drop into the grid and pointer drags inside WebView2 — and
  Generate's results view with the shared Inspector beyond screenshots. First thing to check in the next session with the shell.
- **Kept out of this commit:** `.docs/artcraft/` (committed separately) and `.docs/proto01_leonardo/` (a separate study, not part of D34).

## 2026-10-10 09:39 — D34 OS drop checked in the desktop app; Leonardo.Ai study committed as shelved

- **Author, in the Tauri shell:** dropping an image file from Explorer onto **Unprocessed** imports it — the OS file-drop path
  (`shell/tauri.ts listenFileDrop`) works alongside the pointer-event drag manager (D34). Still unchecked in the shell: pointer drags
  between panes and onto Places rows inside WebView2 (passed over CDP in Edge on 2026-10-07).
- **`.docs/proto01_leonardo/`** (written 2026-10-08: Leonardo.Ai as a cloud engine, 79-model catalogue, integration points, slices
  L0–L6, LD1–LD12) committed for reference and marked **shelved** in its README; LD1 is not accepted, nothing enters 13.

## 2026-10-10 09:43 — Wave H1 opened (D35–D38 accepted); D35: agent docs + path check

- **Decisions:** the author accepted wave H1 of `../artcraft/08-delivery-plans.md` — D35 agent docs (P7), D36 release hygiene (P19),
  D37 routes per domain (P8), D38 generated API types (P3) — entered in 13 with a backlog note (H1–H4 run before the Story workspace); 12
  gains §8b and a standing rule to re-verify agent docs at each milestone start.
- **D35 delivered:** root `CLAUDE.md` (where the truth lives, commands, house rules, layout) and `AGENTS.md` in `orchestrator/`
  (module map, durability and async rules, tests, footguns), `orchestrator/loom2/engine/` (files, rules, add-a-model and pin-bump
  checklists, footguns — the checklist gets rewritten by P1), `frontend/src/frame/` (suite registry, command registry rule, pointer-drag
  rule, AskDialog, theme tokens, state) and `frontend/src/suites/edit/` (compositor invariants, renderer selection, checks). Real files,
  each with a `Verified at` line.
- **`scripts/agents_check.py`** (CI step after the offline tests): every agent doc has the verified-at line and every backticked repo path
  exists (submodule paths skipped — CI checks out without them). First run found one ambiguous path (`engine/AGENTS.md` resolved
  against the repo root) — fixed to the full path; a deliberately broken path fails the check, 5 docs / 0 problems after.

## 2026-10-10 09:49 — D36: one VERSION, build facts in /version, Settings · About, draft releases on tags

- **Before:** `0.1.0` in pyproject, `loom2/__init__.py`, tauri.conf.json and Cargo.toml, but `0.0.0` in package.json /
  package-lock.json; `/version` returned three fields nothing read; no installer could be tied to a commit.
- **`VERSION` + `scripts/bump_version.py`:** ten locations (VERSION, pyproject + its `uv.lock` entry, `__init__`, package.json, package-lock
  root + `packages[""]`, tauri.conf.json, Cargo.toml + the `app` entry of Cargo.lock), regexes that keep each file's own line endings
  (the working copies mix LF and CRLF); `--check` in CI; package.json / package-lock moved to 0.1.0 by the script itself.
- **Build facts:** `build.rs` bakes `LOOM2_GIT_SHA` and `LOOM2_BUILD_EPOCH` (rerun when `.git/HEAD` / refs move), `spawn_backend` hands
  them over as `LOOM2_SHELL_*` (`cargo check` ok). `loom2/build_info.py`: app version, checkout commit (+ dirty, describe), shell build,
  engine pin (`git describe` of the submodule), node pins from `engine/nodes.lock`, schema versions — cached; `/version` adds the
  variant, the running engine and the state / logs / models paths. Live: an orchestrator on 8791 reported checkout `f7c9ff8-dirty` =
  `git rev-parse`, pin `v0.39.0`, both node pins.
- **Settings · About** (`frame/About.tsx`): versions, commits, engine, nodes, schemas, folders with Reveal, **Copy diagnostics** (version,
  health, engine, queue as JSON). Typechecked and built; not yet looked at in a window.
- **CI:** `release` job on tags `v*`: the tag must equal `v$(VERSION)`, both installer artifacts go into a **draft** GitHub release
  (`softprops/action-gh-release@v2`, generated notes). Not exercised until the first tag.
- **Tests:** `test_release_d36.py` (4): repository versions agree; bump on a temp copy rewrites all ten and `--check` catches a drifted
  Cargo.toml; shell facts from the environment; node pins + `/version` keys → **119 offline**; `npm run build` ok.

## 2026-10-10 09:59 — D37: orchestrator routes split per domain; blocking work off the event loop; M1 rig 20/20

- **Before:** `api.py` 1,175 lines — `Services`, 16 request models and `create_app()` with 89 HTTP routes + 1 WebSocket as closures;
  SQLite, file, zip and PNG work on the event loop in about 40 handlers.
- **After:** `api.py` 77 lines (lifespan, CORS, token gate, error → status table, router includes); `services.py` (`Services` +
  `require_documents`, `group_changed`); `capabilities.py` (the `/capabilities` document, same shape); `routes/` with `deps.py`
  (`Svc = Annotated[Services, Depends(get_services)]` on `HTTPConnection`, so the WebSocket route uses it too) and twelve domain routers
  (meta, settings, projects, assets, groups, documents, clips, jobs, models, engine, blobs, events_ws); request models moved next to their
  routes; inline imports gone. Blocking work now in `asyncio.to_thread`: project open (workspace, catalogue index, group store), project
  info counts, presets / snippets, asset get / patch / delete / tags / bulk / trash / restore, lineage, import (directory walk + PNG
  metadata), all group reads and writes, document list / thumbnail (zip) / PNG encodes / compare, clip list / get / extract / save,
  roster listing / scan / unlisted. `JobQueue` calls stay on the loop (not thread-safe; P2 revisits). `Roster.scan` now swaps
  `_found` and `_ledger` together, so a reader never sees a scan with the ledger half filled.
- **Behaviour kept:** route table identical to the snapshot taken before the move (`tests/fixtures/routes_d37.json`, 90 rows);
  operationIds unchanged; OpenAPI diff vs the committed export = router tags, the `/version` docstring, and `AssetPatch.collection_ids`
  dropped (legacy since D34, ignored by the client). The committed `openapi.json` itself is stale (still lists `/collections*`, lacks
  D34's `date_preset`) — D38 re-exports it from the app.
- **FastAPI 0.142 note:** included routers stay `_IncludedRouter` wrappers in `app.routes` (walk `original_router.routes`); the tests do.
- **Tests:** `test_routes_d37.py` (3): route table = snapshot; no literal path shadowed by an earlier parameterised route of the same
  method (proved by moving `GET /assets/{asset_id}` first — caught); OpenAPI lists every HTTP path → **122 offline**.
  Planned loop-lag test (50 reads during a 200-file import) not written: too timing-dependent for CI on shared runners.
- **Rig:** `scripts/m1_acceptance.py` **20/20** in 170 s against the split app (dev T2I 112.7 s cold, kill → resume paused, cancel,
  graceful stop, live contract clean). `orchestrator/AGENTS.md` (module map, async + route rules) and 06 §6 updated.

## 2026-10-10 10:22 — D38: the generated API contract is the frontend's types; H1 closed

- **Backend:** response models on every JSON route (`loom2/schemas.py`: `Out` for strict replies, `Open` for composite dicts — extra
  fields pass through, defaulted fields optional, sparse routes use `response_model_exclude_unset` so `GET /project` without a project is
  still `{"open": false}`); reply records (`AssetRecord`, `JobRecord`, `ClipRecord`, `Document`, `GroupRecord`, `Settings`, `RosterEntry`,
  `ProjectFormat`, …) set `json_schema_serialization_defaults_required`, so their fields are required in the schema; clip `beats` /
  `identity` stay dicts at runtime with typed JSON schemas (`WithJsonSchema`). `create_app` publishes the WebSocket frames
  (`EventFrame`, 16 frame types) and the recipe models (`Recipe`) as components. `scripts/export_openapi.py` writes
  `frontend/src/api/openapi.json` deterministically (env-read defaults pinned, the checkout path → `<repo>`) — the committed file had been
  stale again (still `/collections*`, no `date_preset`).
- **Frontend:** `openapi-fetch` 0.17 behind `unwrap(http.VERB(path, {params, body}))` (token by middleware, `ApiError` kept); all **83**
  JSON call sites migrated (session, Catalogue store / album / Inspector / lineage / pages, Generate, Animate, Edit, About) and the untyped
  `api.get/post/put/patch/del` removed (bytes and URLs stay on `api.*`); `types.ts` re-exports the generated types through a `Readable`
  mirror (openapi-fetch turns tuples into arrays); `applyEvent` switches on the typed `EventFrame` union and the suite handlers take the
  generated payloads; recipe builders return `T2IRecipe` / `I2VRecipe` / `DocumentRecipe`; `npm run api:types` with
  `--default-non-nullable false` (request fields with defaults stay optional). The editor keeps its flat node model behind one `asStack()`
  adapter. Only 14 type errors surfaced when the hand mirror was swapped for the generated types — the mirror had been close.
- **Bug found by the typing:** the Catalogue's "No derivations" chip (`has_children: false`) was never sent (the query builder dropped every
  `false`), so it showed every asset; the typed `queryOf` sends defined booleans (the backend already handled `false`).
- **Checks:** `test_contract_d38.py` (3: every JSON route has a reply model; the committed spec equals a fresh export; every JSON GET answers
  200 on a populated project) → **125 offline**; CI step re-exports, regenerates `schema.d.ts` and fails on a diff; `tsc -b` + `vite build`
  ok, lint unchanged. Headed Edge: `edit_headed_check.py tour` **all passed** (save, save to Catalogue, PNG/PSD export, compare p99 2/255),
  `animate` **all passed** (clips, preview, extract with lineage, identity); `csp_check.py` clean on Catalogue, Edit, Generate, model panel,
  Edit AI (0 CSP hits, 0 JS errors). Not run: the Tauri shell itself.
- **H1 closed** (D35–D38). 12 §8b status updated; next wave H2 (P2 plan/finalize/submit, P1 model registry, P4 job origin).

## 2026-10-10 10:25 — CI red since 2026-10-07: open-variant test pinned; agent-doc check judged by tracked files

- Read through the GitHub API (no `gh` here; job logs need admin rights): every CI run since at least `a202db3` (2026-10-07 08:38)
  failed in the `open` matrix leg's offline tests, and since D35 the `full` leg also failed at the agent-doc step.
- **open leg:** `test_lifecycle.py::test_warm_group_affinity_ages_out` submits a FLUX.2 dev job; under `LOOM2_VARIANT=open` the C3 gate
  rightly refuses dev (full-only). The test is about warm-group scheduling, so it now pins `AppState(..., variant="full")` like `Rig` does.
  Reproduced and verified locally: `LOOM2_VARIANT=open pytest` 125 passed.
- **full leg:** `scripts/agents_check.py` tested existence on disk; `orchestrator/loom2/engine/AGENTS.md` names `engine/.venv`, which exists
  here but is gitignored, so CI's checkout lacks it. The check now passes a path only when git tracks it (file or directory of tracked
  files) and skips gitignored local paths — same verdict on this machine and in CI; a broken path still fails.

## 2026-10-10 10:28 — CI: agents_check still red at e942fb9 — a `.venv/` pattern only matches a path git can see as a directory

- CI at `e942fb9`: the `open` leg's offline tests now pass; both legs still failed at the agent-doc step. Cause: `git check-ignore
  engine/.venv` answers "not ignored" when the directory does not exist (CI), because `.gitignore`'s `.venv/` matches directories only;
  `engine/.venv/` matches. `ignored()` now asks both spellings. Simulated CI by moving `engine/.venv` aside: 0 problems; restored.

## 2026-10-10 13:18 — PhotoCraft study for the Edit suite (`.docs/photocraft/` 00–06)

- PhotoCraft (`F:\source\repos\photocraft`, `b37bff98`, v0.6.0) is a clean-room Photoshop-class editor in Rust (egui, wgpu) by the
  ArtCraft team, licensed **MIT OR Apache-2.0** — unlike ArtCraft, its code may be ported with attribution. Read in five passes
  (engine/compositing, tools/algorithms, UI, formats/practices, and an inventory of loom2's Edit suite at `1cdc6d2`); nothing built.
- **Verified loom2 findings F1–F10** (06 §2): clipping multiplies by the accumulated backdrop alpha, so a clipped layer over an opaque
  background is not clipped (editor `-clip` shaders do the same; the one test clips to a base that is the whole backdrop); a pass-through
  group below 100 % opacity renders isolated; adjustment layers ignore their blend mode; Soft Light (upper half), Vivid Light and Hard Mix
  follow W3C, not Photoshop; brush opacity is per dab; selection edits are not in history; PSD export skips adjustment layers although
  ag-psd 31.0.2 writes all eight types; AI paste-back is alpha-feather only (spec's "match colour" and "layer with mask" missing);
  `fsio` has no Windows rename retry; every brush move re-uploads the whole texture.
- **Proposals PC1–PC26** in waves PE1 (fidelity) – PE6 (transform, smart select), spikes S1 (PyO3 `photocraft-algo`: content-aware
  fill, healing) and S2 (WASM: quick select, magnetic lasso); routes port / idea / crate. The author accepted the study and asked to
  start with PE1.

## 2026-10-10 13:37 — Wave PE1 opened (D39–D42); D39 Photoshop compositing semantics landed

- Recorded D39 (compositing semantics), D40 (Photoshop oracle), D41 (PSD export), D42 (rename retry) in 13 and the PE1–PE6 waves as
  12 §8c before starting.
- **compose.py:** Soft Light, Vivid Light, Hard Mix and the Burn / Dodge `EDGE` (1e-4) rule ported from PhotoCraft (`psblend.rs`,
  `color/blend.rs`); the renderer walks bottom-up in **clip runs** — the base's content (pixels × mask) alone, clipped layers composited
  atop it (as if opaque, base alpha kept; clipped adjustments blend their result onto it), the unit blended with the base's mode and
  opacity × fill; a hidden base hides its run; a **pass-through group** below 100 % or masked renders its children into the backdrop and
  mixes the result against the original by opacity × mask (premultiplied); a pass-through group with a clipping group of its own renders
  isolated; **adjustment and filter layers blend in their own mode**. `COMPOSE_VERSION = 2` is stamped in `meta.compose_version` on save.
  Correction to the study: Photoshop's Soft Light equals W3C's except where cs > ½ and cb ≤ ¼ (√cb vs a cubic, up to ≈ 5 levels).
- **Editor:** the `-clip` shader variants are gone; a clip run is three passes (base content → drawn `w3c-opaque` with the clipped layers
  over it → masked by the base's alpha with `setMask({channel: 'alpha'})`) blended with the base's mode; a pass-through mix renders a copy
  of the target's earlier content (`prefixOf`) plus the children into a pass drawn at opacity × mask — exact over an opaque backdrop,
  approximate where the backdrop is semi-transparent; adjustment / filter shaders take the layer's mode as a uniform (`w3_blendBy`).
  Moving or transforming a layer now marks passes dirty (it may sit inside a clip run).
- **Bug found by the headed check:** undo / redo restored a stack snapshot *with its old server revision*, so the next save got a 409 and
  the resync merged back server layers the snapshot lacked — an undone, already-saved layer could come back. Restores now keep the
  current `revision` / `saved_at`.
- **Checks:** `test_compose_d39.py` (15: formulas from PhotoCraft's Photoshop-fitted tests, clip to the base over an opaque background,
  unit opacity and mode, base alpha kept, hidden base, masked base, clipped adjustment, orphan clip, stacked clips, pass-through 50 % with
  an adjustment, adjustment in multiply / screen, compose_version) → **140 offline**. Headed Edge (WebGPU): `cmpdiag` all passed — every
  earlier case unchanged, D39 cases p99 0–1 (clip 0/1/1, multiply 1, unit opacity+mode 1, clipped invert 1, invert in multiply 1;
  formulas soft-light 1 / vivid 2 / hard-mix 0 (max 255 at threshold flips) / burn 4 / dodge 1); pass-through 50 % p99 1, max 15 — all
  of it on the one document row the bench image does not cover, where the backdrop is the half-transparent test layer (the documented
  approximation). `tour`, `render`, `paint` all passed; build ok. First port → `THIRD_PARTY_NOTICES.md` (PhotoCraft, MIT).

## 2026-10-10 13:39 — D42 atomic replace retries on Windows

- `fsio.replace` retries `os.replace` on `PermissionError` 7 times from 10 ms, doubling (≤ 0.63 s waiting; PhotoCraft's
  `format/src/atomic.rs` rule); other errors and the last failure propagate. Every atomic helper uses it, and so do the five places that
  called `os.replace` directly (document save, blob upload, strip thumbnails, the fetch index). `atomic_move` still falls back to
  copy-then-unlink for a cross-volume move.
- `test_fsio_d42.py` (5, failure injection): locked three times then written; locked for good → `PermissionError` after 7 tries with the
  old record intact and no temp file left; other errors not retried; cross-volume move still copies; an ORA save survives a briefly
  locked target → **145 offline** (also under `LOOM2_VARIANT=open`).

## 2026-10-10 13:50 — D41 PSD export carries the whole stack

- `psdExport.ts`: adjustment layers become Photoshop adjustment layers through ag-psd's `adjustment` records, with their mask, clip,
  blend, opacity and visibility — Levels (in/out points, gamma as the midtone), Curves (per channel), Exposure and Invert map exactly;
  Hue/Saturation (master, Photoshop's default colour ranges), Colour Balance, Brightness/Contrast (legacy) and Black & White keep their
  settings but Photoshop's maths differ, and the export toast names them. Fill opacity is written; a pass-through group is written as
  `pass through` (compose.py's rule), an isolated one in its mode; the editor's lock (no paint, no move) is written as Lock All instead of
  transparency lock. Filter layers have no Photoshop equivalent and stay skipped with a clearer warning (the merged image includes them).
- **ag-psd bug found by the read-back:** its Levels block is a version word plus 63 records with no `Lvls` header after the 29th, so
  psd-tools rejects it ("Invalid signature"). Patching ag-psd's handler through `ag-psd/dist-es/additionalInfo` does not work under
  Vite's pre-bundling (a second copy of its CommonJS internals). `fixLevelsBlocks` rewrites each block's tail in place to Photoshop's
  632-byte layout (29 records, `Lvls`, version 3, count 62, 33 records, 2 bytes padding — what PhotoCraft's `adjust_map.rs` reads);
  nothing moves, so no enclosing length changes. Worth reporting upstream.
- psd-tools 1.24 (MIT; now only `attrs` beyond numpy / Pillow) added as the orchestrator's optional `oracle` extra.
- **Checks:** new headed mode `edit_headed_check.py psd` builds a stack with every exported construct and reads the PSD back with
  psd-tools — fill 127/255, Lock All, clip + multiply, Levels values (10, 240, 5, 250, γ 1.2), Curves in screen at 50 %, pass-through and
  isolated groups, Hue/Sat, Exposure values, hidden Invert, filter skipped, toast text: **all passed**; `tour` all passed; 145 offline;
  build ok. Still a manual check: opening such a PSD in Photoshop or Krita (spec 10 §14).
- Observed, pre-existing: PixiJS logs "[BindGroup] a 'textureSource' was destroyed while still bound to a shader" on scene rebuilds —
  152 per `tour` before D39, 154 after; not caused by the D39 passes, left for a later clean-up.

## 2026-10-10 14:04 — D40 Photoshop is the compositing oracle; wave PE1 closed

- **Corpus:** 83 psd-tools test PSDs (MIT; blend modes, clipping, groups, pass-through, masks, opacity / fill, Levels / Curves /
  Exposure / Invert and the other adjustments) pinned at psd-tools `96eb134c` with SHA-256 sums taken from PhotoCraft's manifest
  (`bench/corpus/psd-tools.sha256`); `scripts/fetch_corpus.py` (stdlib) fetches and verifies them into the gitignored
  `bench/corpus/psd-tools/` (10 MB).
- **Oracle:** `orchestrator/tests/psd_oracle.py` turns a PSD (psd-tools) into a loom2 stack — rasters with offsets, groups (pass-through or
  isolated), opacity, fill, clipping (read from the layer record: psd-tools' `clipping` property reads False on groups), masks
  (document-sized, default colour outside), Levels (master only), Curves, Exposure, Invert — and records why a file is out of scope
  (vector masks 46, fill layers 12, Hue/Sat-style adjustments whose maths differ by design 8, group / adjustment fill, effects, per-channel
  levels, …). compose.py's flatten is compared with Photoshop's merged image at premultiplied max ≤ 2/255; `test_compose_oracle_d40.py`
  (marker `corpus`: skipped when absent, failing when selected and absent) holds the pass count to `bench/corpus/psd-tools.floor.json`.
- **Findings:** the pre-D39 compositor passes 6 of 10 in scope (`group-clipping` max 255, `passthrough_opacity` max 86 — the two D39 bugs,
  now confirmed against Photoshop); **Exposure was wrong** in compose.py and the editor (applied to encoded values; Photoshop works in
  linear light through a pure 2.2 power, as PhotoCraft had fitted) — fixed on both sides, `COMPOSE_VERSION` 3; `exposure_rgb` max 90 → 5.
  Result: **8 pass of 10 in scope, floor 8**; known failures Curves (natural cubic spline vs loom2's linear — PC21) and Exposure (max 5,
  p99 1: Photoshop rounds to 8 bits after each adjustment layer).
- **GPU parity grid:** `edit_headed_check.py grid` — seeded noise in 24 modes × plain / masked / clipped / isolated group / pass-through
  group at 50 % over a half-transparent base: 120 cases, 114 at p99 ≤ 1; Colour Dodge, Vivid Light and Divide reach p99 2 (max 31–62)
  plain and masked — they amplify the 8-bit rounding of the GPU backdrop where compose.py accumulates in float32; budget p99 ≤ 2 for
  those three. Rendering the editor's passes into rgba16float (PhotoCraft's choice) would close that; noted as a follow-up.
  `cmpdiag` gains a non-default Exposure case (p99 1): all passed.
- **CI:** the `oracle` extra is installed, the corpus is cached by its manifest hash and fetched, and a `-m corpus` step runs the oracle
  (it fails instead of skipping). Offline: **146 passed** (145 + the oracle).
- **Wave PE1 closed** (D39–D42); 12 §8c updated. Next Edit wave PE2 (selection) when the author chooses, relative to H2.

## 2026-10-10 15:02 — CI green on wave PE1

- GitHub Actions run 38050691055 on `06d7799`: offline tests + frontend for `full` and `open` (including the new psd-tools corpus
  fetch and the `-m corpus` Photoshop-oracle step) and both installers — all success. Every PE1 commit's CI passed
  (`85d7286` was superseded by `a4b4cfb` before it finished).

## 2026-10-10 15:19 — Wave PE2 opened (D43–D46); D43 selection history and D44 selection toolkit landed

- Recorded D43 (selection edits are history), D44 (manual selection toolkit), D45 (Refine Edge), D46 (clipboard) in 13; 12 §8c PE2 open.
- **D43:** `editSelection(label, fn, coalesce)` diffs the selection's values before / after per 256² tile and stores only the changed
  tiles plus whether a selection existed before / after, so undo / redo also restore "no selection" (deselect, the first marquee); every
  selection tool and command, AI Select results and deselect (`Ctrl+D`, Esc) go through it. `pushHistory` merges consecutive entries with
  the same `coalesce` key within 2 s (a run of nudges is one step; sliders already were).
- **Found while doing it:** the selection had two encodings — tools drew white with partial alpha on a transparent canvas, feather /
  invert wrote opaque grey — and `toRaw`, the ants and crop read the red channel only, so every anti-aliased or feathered tool edge
  counted as fully selected and a subtracted partial edge stayed at full value. The value is now red × alpha / 255 everywhere
  (`selectionValues`, `toRaw`, `selectionAlphaCanvas`); masks are opaque, so unaffected.
- **D44 (frontend, `selectionOps.ts`):** exact EDT (Felzenszwalb–Huttenlocher) → expand / contract / border (round, fractional rim),
  smooth (box + re-threshold), feather (Gaussian σ = r / 2, three box passes) driven by one amount in the Selection panel and a Modify ▸
  submenu on the canvas; every tool renders a document-sized shape combined by mode (replace / add / subtract / **intersect**, Shift+Alt);
  marquee feather and fixed ratio / fixed size; **polygonal lasso** (first corner, double-click, ✓ or Enter closes; ⊘ / Esc cancels; the
  options and the canvas menu show both while a polygon is open); the wand compares alpha too and matches transparent pixels regardless of
  hidden RGB, can run globally or on all layers (the GPU composite), and anti-aliases its edge pixels; **select layer transparency**
  (layer menu, Selection panel, Ctrl-click a thumbnail). 4K timings in Edge: expand 16 px 297 ms, contract 265, border 530, smooth 100,
  feather 202 (and 218 at 100 px), combine 16 — kept on the main thread.
- **D44 (orchestrator, `maskops.py`):** a bounded exact EDT (row scans + a band of row offsets, on the mask's bbox) behind
  `edit_ai.dilate` / `erode`. PIL's `MaxFilter` grew **squares** and was slow: 64 px took 16.8 s on a 1080p mask and **66.7 s at 4K**
  (AI Select's "expand 64"); the EDT takes 110 ms / 487 ms (8 px: 24 ms vs 411 ms at 1080p).
- **Checks:** `test_maskops_d44.py` (4: EDT vs brute force, a point grows into a disc, contract / expand complement, no-ops) → **150
  offline**. New headed mode `edit_headed_check.py selection`: in-page EDT vs brute force (worst 2e-7), disc, combine, contract / feather;
  then by mouse — marquee, undo to no selection, redo exact, Shift+Alt intersect, invert, expand / contract / border / smooth / feather
  by 8 px each undone, marquee feather, fixed ratio 2:1 (384 × 192), polygon closed by its first corner, cancelled with ⊘, closed by a
  double-click, wand global ⊇ contiguous with an anti-aliased edge, wand on all layers, layer transparency (exactly 50 × 40 px), deselect
  and its undo: **all passed**; `tour` and `cmpdiag` all passed; build ok.

## 2026-10-10 15:29 — D45 Refine Edge

- `orchestrator/loom2/matting.py` (port of PhotoCraft `matting.rs`): colour-guided filter (He–Sun–Tang; box means by cumulative sums,
  closed-form 3×3 inverse, vectorised), **smart radius** (luminance range ÷ max gradient through van Herk running max / min done with
  block-wise accumulations — constant cost in the radius), edge band from the D44 EDT, then smooth / feather (σ = r / 2) / contrast /
  shift edge in Photoshop's order; the guided step runs only on 256² tiles that touch the band.
- `POST /documents/{id}/selection/refine` (body `RefineEdge`, ranges enforced, 400 without a selection) refines the document's selection
  against its exact composite in a thread and reports coverage and ms; the Segment recipe gains `edge_refine` (AI Select runs it on the
  joined selection); `/capabilities.refine_edge` publishes the defaults and slider ranges (typed `RefineEdgeCaps`). Route snapshot and
  OpenAPI contract regenerated.
- Editor: a **Refine edge** section in the Selection panel (sliders from the server's ranges; the store keeps only the user's overrides
  over the server's defaults, Reset clears them — T8), `edit.sel.refine` in the panel and the canvas menu, a **refine edge** switch in AI
  Select; the client saves, uploads the selection (one shared helper with `runAi`), calls the route and reloads the selection as one undo
  step ("refine edge").
- What it does and does not do (offline tests and probes): soft image transitions are transferred into the mask (a 12-px blur ramp
  comes through monotone), a correctly placed hard edge stays nearly hard (234 / 0 at ±2 px), everything outside the band is untouched;
  it does **not** pull a mask that is a few px off onto the true edge (the binary input makes the local model settle near α ≈ 0.6) and
  does not pick out 1-px strands with a 10-px window — as in PhotoCraft. Smooth / contrast / shift edge are the levers for those.
- **Rig (RX 9070 XT, temporary state and project, `scripts/refine_edge_rig.py`):** bench source at 1920×1080, BiRefNet subject 16.0 s
  cold; the refine route on that matte 743 / 714 / 706 ms (defaults: radius 10, smart radius); BiRefNet with `edge_refine` 2.4 s warm;
  soft edge pixels 19 173 → 26 754; crops in `engine/spikes/out/pe2/` — differences are subtle at this hair, whose BiRefNet matte is
  already soft. Target "< 1 s at 1080p" met.
- **Checks:** `test_matting_d45.py` (6: box mean and running extremes vs brute force, guided filter reproduces a linear guide, soft / hard /
  untouched, post steps, defaults = worker, route + capabilities + 400 / 422) → **156 offline**; headed `selection` adds refine (0 → 15 841
  soft px, one history step, undo exact): all passed; build ok.

## 2026-10-10 15:40 — D46 clipboard and pasting in Edit; wave PE2 closed

- Store: `copySelection({merged, cut})` copies the selection's bounding box of the active layer (or of the GPU composite for Copy
  merged) masked by the selection (soft selections copy soft) into the editor's clipboard with its document position, mirrors it to the
  OS clipboard as PNG (best effort) and remembers the PNG's size; `pasteClipboard(inPlace)` / `pasteFromEvent(files)` add a new raster
  layer — centred on the document, or where it was copied from — and prefer an image copied in another app (a different PNG size than
  our own) over the editor's clipboard; `layerVia(cut)`; `addImageLayer`; `dropFiles(paths)` imports OS files through the Catalogue
  (`/assets/import`) and adds them with lineage.
- Commands with mouse placements (canvas menu: a "clipboard" group while there is a selection, a Clipboard ▸ submenu otherwise): Copy
  `Ctrl+C`, Cut `Ctrl+X`, Copy merged `Ctrl+Shift+C`, Paste `Ctrl+V`, Paste in place `Ctrl+Shift+V`, Layer via copy `Ctrl+Alt+J`, Layer
  via cut `Ctrl+Shift+J` (`Ctrl+J` stays Duplicate: the key dispatcher stops at the first matching command even when it is disabled, so
  two commands cannot share a key). `Ctrl+V` is let through to the browser so its `paste` event carries images from other apps without a
  clipboard permission; the Paste command's mouse path tries `navigator.clipboard.read()` and falls back to the editor's clipboard.
- OS files dropped on the canvas (Tauri's drag-drop paths, `listenFileDrop`) go through the Catalogue; the canvas shows a dashed accent
  outline while a file hovers it. Found while testing: a paste event dispatched on the window has no `closest()` — the guard checks
  `instanceof Element` first.
- **Checks:** headed `selection` gains (system clipboard stubbed in the test page, so the author's clipboard is never touched): copy
  288×218 at 96,54; paste centred on the document, undone; paste in place at 96,54; layer via copy; layer via cut (the source pixel's
  alpha 0); copy merged the same size; a synthetic Ctrl+V paste event with a 40×30 PNG → "Pasted image" 40×30; `dropFiles` with the
  bench file → a layer with lineage — **all passed**; `tour`, `cmpdiag`, `paint` all passed; 156 offline; build ok, lint unchanged.
- **Wave PE2 closed** (D43–D46); 12 §8c updated. Next Edit wave PE3 (AI blend-in), relative to H2 at the author's choice.

## 2026-10-10 16:32 — Wave PE3 opened (D47–D49): seamless paste-back with result masks, match colour on Refine, Colour to Alpha

- Recorded D47–D49 in 13 before the work; 12 §8c PE3 open (S1 to be recorded when it runs).
- **D47** `loom2/poisson.py` (port of PhotoCraft `poisson.rs`): membrane solve by cascadic multigrid with red-black SOR (vectorised), seamless
  clone on the mask's bounding box. Measured: against full-range noise on the boundary the cascadic solve is 8–14 levels off a converged
  one (the coarse grids move the boundary); smoothing the boundary mismatch with σ = 2 px (normalised over known pixels) brings it to
  0.73 levels and is the right model anyway — the paste-back corrects colour / light drift, not pixel noise along the seam. 1 MP crop,
  600×500 mask: 3.3 s → 0.54 s with the bbox. Inpaint gains `blend: feather | seamless` (`edit_ai.harmonise`: clone through the mask
  contracted by the feather, 1-px plate margin, then the feathered mask as before). Paste-back results (Inpaint, Outpaint, Refine of the
  selection) are now opaque pixels plus a **linked layer mask** (`_add_result_layer(as_mask=True)`), rendering identically to the old
  baked alpha (test) but repaintable.
- **D48** `loom2/tone.py` (Lab statistics transfer, port of PhotoCraft `tone.rs`). Designed for Inpaint on the context ring, then
  **measured on the rig and moved to Refine**: loom2's inpaint graphs composite the original outside the mask (LanPaint decode,
  `ImageCompositeMasked`), so the engine's context ring equals the plate — Fill and Fill-Match came back identical with and without it
  (ring drift 0.84 / 0.98 levels). Refine re-decodes every pixel: on the bench at strength 0.35 it brightened L* by +2.3; with match colour
  the Lab mean shift is 0.0 (mean |Δrgb| 20.96 → 19.02, the rest is the refined detail). I2I gains `match_colour` (ring around a
  selection, else the whole image / layer); the AI panel's switch sits under Refine. D48's row in 13 says so.
- **D49** Colour to Alpha: the exact unmix (`_color_to_alpha` in compose.py, the same in the filter shader), `colour` /
  `transparency_threshold` / `opacity_threshold` with a colour picker for hex parameters in Properties; "Ink from white" applies it to the
  active raster layer in place (one undo step).
- **Rig (temporary state, `scripts/pe3_blend_rig.py`), bench task 01 (remove the crates), Klein 9B Fill, seed 7:** feather 59.7 s (cold) ·
  seam energy 1.00; seamless 45.1 s · **0.07**; every result came back with a linked mask over opaque pixels; sheets in
  `engine/spikes/out/pe3/` — the seamless brick wall sits darker, in the plate's light, the feather one is brighter than its
  surroundings. Fill-Match: 37.2 / 22.4 s, identical with / without match colour (above).
- **Checks:** `test_pe3_blend.py` (9: membrane within an 8-bit step on smooth data, offset removed with texture kept, Lab round trip and
  match, drift removed but new content kept, no step at the seam, default path unchanged, result layers with a linked mask render as
  before, refine match over the whole image, colour to alpha unmix / round trip / thresholds) → **165 offline**; headed `cmpdiag`
  (colour_to_alpha p99 0, max 1), `selection` (ink from white: grey → black at α ½, white → transparent, one step, undone), `tour`: all
  passed; build ok, lint unchanged; API contract regenerated.

## 2026-10-10 16:37 — Spike S1: PhotoCraft content-aware fill through PyO3 — builds and is fast, but fills are blurry; recommend no-go

- `engine/spikes/pcalgo`: a PyO3 0.26 + rust-numpy 0.26 cdylib over `photocraft-algo` (local path to the checkout at `b37bff98`; an
  adoption would pin the git commit), `content_aware_fill` and `complete_hole` on numpy float32, the GIL released. `uvx maturin build
  --release` on Windows MSVC / Rust 1.96: abi3 wheel for CPython ≥ 3.13, **0.22 MB**, 42 s cold (all dependencies), 3.5 s warm. The spike
  loads the .pyd from a temporary folder — the orchestrator venv is untouched.
- **Cost (CPU):** bench task 01's hole (960×544, 73 515 px) 0.08 s; PatchMatch completion 0.05 s; the same at 1920×1080 (292 060 px)
  0.27 s; five small holes (3 641 px) 37 ms / 20 ms. Speed is no obstacle.
- **Quality (`engine/spikes/s1_content_aware.py`, sheets in `engine/spikes/out/s1/`):** on the 320×210 crate hole the fill is a smooth
  smear (PhotoCraft only refines, not re-synthesises, at levels where the hole is wider than 96 px); on 25–35 px holes on cobblestones,
  sky and wall it is still a textureless blob; only a thin 7-px line came out clean. Remove today (Klein ICM, grey hole) 37.6 s: the crates
  go (the model put an AC unit there). Fill-Match with the content-aware fill as its reference 22.2 s: it keeps the blurry pre-fill —
  worse than today.
- **Recommendation:** no-go for PC14 (pre-fill / quick Remove) and PC15 (spot healing on these kernels) at this PhotoCraft commit; the
  build route itself (PyO3 + maturin, abi3, 0.22 MB) is proven if a better kernel appears. Left for the author to decide (13).

## 2026-10-10 17:37 — CI green on wave PE3

- GitHub Actions run 38060336289 on `55542e0` (includes `1de73aa`, whose own run was superseded): offline tests + frontend for `full`
  and `open` (with the Photoshop-oracle step) and both installers — all success. S1's go / no-go (PC14 / PC15) is still the author's.

## 2026-10-10 17:51 — Wave PE4 opened (D50–D53); D50 brush model and D51 smoothing / painting modifiers landed

- Recorded D50 (brush model), D51 (smoothing + modifiers), D52 (masks), D53 (partial uploads) in 13; 12 §8c PE4 open.
- **D50** `brushEngine.ts` (port of PhotoCraft `paint/render.rs`): a per-stroke coverage buffer, c ← c + flow·f·(1 − c), f the tip
  falloff (hardness core, then (1 − t²)⁴; tips under 3 px radius sampled 4×4); each pointer move recomposites only the touched rect from
  the **pre-stroke pixels** — the undo tile snapshots the layer keeps anyway (`LayerPixels.preStroke`) — as colour × coverage × opacity
  × selection, so a stroke never exceeds its opacity. The eraser removes alpha by the same coverage; mask / quick-mask strokes move grey
  values towards white / black. New: painting is **clipped to the selection** (it was not); a per-layer **lock transparency**
  (`lock_alpha` on raster layers; PSD: transparency lock).
- **D51** a pulled-string `Smoother` (string = smoothing × 100 screen px ÷ zoom) with **catch-up** every frame while the pointer rests and a
  finish at the release point, over a `PathWalker` that carries the dab spacing across segments; **Shift-click** paints a straight line
  from where the last stroke ended; the **Straight lines** toggle makes a drag paint start → release; **Alt-click** or the one-shot
  **Pick colour** chip picks the composite colour. All with mouse placements (brush options, canvas menu).
- **Checks:** new headed mode `edit_headed_check.py brush` (by mouse events): a stroke crossing itself at 50 % → max alpha 128 (the old
  dabs reached 255); undo; a 2-px diagonal line without gaps (weakest 254); paint stays in the selection; lock transparency (colour
  changes, alpha 128 kept, empty pixels stay empty); a 50 % eraser crossing itself → 128; Shift-click line; line mode ignores the wiggles;
  Alt-click and the chip pick; with smoothing 0.9 the stroke reaches the release point — **all passed**. `perf`: brush on the 4K
  document p50 33.0 ms (one 31 Hz display frame, as at M7), the pointer handler itself 0.2 ms p50 / 0.4 ms p95; `paint`, `cmpdiag`
  passed; 165 offline; build ok, lint unchanged.
- **Environment, not code:** `tour` failed twice at PSD export / compare with "504 Outdated Optimize Dep" — the author's own `npm run
  dev` (started 17:32) holds a stale dependency hash after a Vite of mine, refused on the busy port, re-optimised the shared
  `node_modules/.vite` cache. Restarting `npm run dev` clears it; the same tour steps passed at `1de73aa`.

## 2026-10-10 17:59 — D53 partial texture uploads

- `LayerPixels.refreshRect` uploads only a stroke's changed rect through a renderer hook EditorCanvas registers
  (`setPartialUpload`), done the way Pixi uploads a canvas: WebGPU `copyExternalImageToTexture` with origin and size (premultiplied on
  upload as the source's alpha mode says), WebGL2 `texSubImage2D` from the region's ImageData with Pixi's premultiply / binding caches kept
  true; any failure falls back to the whole texture. `window.__loom2FullUpload = true` forces whole uploads (A/B).
- **Correctness:** headed `brush` now ends with a GPU-vs-exact compare after all its strokes — p99 0, max 0 on WebGPU **and** WebGL2
  (`EXTRA=&renderer=webgl`); `paint`, `selection`, `cmpdiag` passed (one `cmpdiag` run failed at its first case with p99 0 on a page
  error and passed on two reruns — the author's dev server was reloading).
- **Performance:** not measurable with the instruments here: `perf` on the 4K document reads 33.3 ms per presented frame either way (the
  31 Hz display), handler CPU 0.2 / 0.3 ms and render CPU 0.3 / 0.4 ms with partial / full uploads — the whole-texture upload is queued
  GPU / driver work that CPU timings do not see. Each move now sends ≈ 14 KB instead of 33 MB; the gain should show on a faster display or
  larger documents. `perf` reports the render CPU time now and takes `FULL_UPLOAD=1`.

## 2026-10-10 18:24 — D52 masks like Photoshop's; wave PE4 closed

- **Model (orchestrator):** `Mask` gains `density` (0–1, default 1) and `feather` (Gaussian σ px, 0–250, default 0); `DOC_SCHEMA_VERSION`
  1 → 2 — version-1 documents load with the defaults and `save()` now stamps the current version. `compose.derived_mask` feathers with
  three box passes (Kovesi radii, edge-clamped running sums — a port of `selectionOps.gaussian`), rounds to 8 bits, then applies
  density `1 − d·(1 − v)` with the same rounding; `_mask_for` uses it, so flatten, Save and the queue's crops all see the mask as it
  renders. `test_masks_d52.py` (6): defaults are a no-op, density rounding, feather within 1 level of a literal float32 transcription of
  the TS blur (< 1 % of pixels differ), a symmetric monotone edge, the renderer applies both, a version-1 file loads and saves as 2.
- **Oracle:** `psd_oracle.py` now maps the user mask's density (/255) and feather (px as σ) instead of ruling them out — but every corpus
  file that sets either (clipping-mask2, layer_mask_data, mask-density-layermask, mask_parameters, passthrough_vector_mask) also has a
  vector mask, which stays out of scope. **Photoshop's feather kernel is therefore not measured**; σ = feather px is the assumption
  (Photoshop's Gaussian Blur radius behaves as σ). A Photoshop-made file with a feathered pixel mask would settle it.
- **Editor:** `maskDerived.ts` derives the mask texture when density < 1 or feather > 0, cached per mask canvas by a new
  `LayerPixels.version`; the render loop re-derives before the passes. Painting a feathered mask re-derives **only around the stroke**:
  `LayerPixels.takeDamage()` hands over the union of `refreshRect`s, the output region is that rect plus the blur's reach (3σ + 3 px
  bounds the three radii) and the crop another reach beyond — the first version wrote only the damaged rect and the headed brush check
  caught it (max 94 at p99 0; the check now also bounds max ≤ 2). Full derive cost for reference (Node): 27 ms at 1080p, 140–150 ms at
  4K for σ 2–40.
- **Behaviour:** a raster's new mask is layer-sized and **linked** (adjustments, filters, groups keep document-sized, unlinked masks); a
  chain button in the layer row and the *linked* box link / unlink without moving the mask (offset converted); masks on every node kind
  are paintable (brush, eraser, fill, gradient, clear); mask controls (on, linked, density, feather, Apply / Load / Remove) under the
  blend controls in the Layers tab and in Properties for every kind; **Apply mask** (alpha × the derived mask, mask removed, one undo
  step) and **Mask from transparency** (alpha → linked mask, layer opaque); the pixel thumbnail gets the accent frame when it is the
  paint target and the layer has a mask; **Delete** while editing a mask removes the mask; merge down bakes the derived mask; PSD export
  writes `userMaskDensity` / `userMaskFeather`. Fixed on the way: canvas size / crop and the outpaint resync shifted unlinked masks on
  rasters only — groups' and adjustments' masks drifted (queue.py already shifted every kind).
- **Headed (Edge, WebGPU):** cmpdiag new cases all p99 ≤ 1 — density 60 % (max 1), feather 6.5 px (max 127 at 3 601 pixels whose alpha
  is 1/255 on both sides: the colour of an almost transparent pixel does not survive an 8-bit premultiplied texture; the mask agrees),
  density 40 % + feather 2 (max 1), linked mask follows a move, unlinked stays put, feathered 80 % mask on an Invert adjustment (max 1);
  cmpdiag now keeps any pair with max > 4 and prints the worst pixel. Brush: the eraser paints an Invert layer's mask black and the
  composite equals the exact flatten after the stroke (p99 0, max 1). Tour: link / unlink, the Layers-tab controls, Apply, From
  transparency, Delete-removes-the-mask and its undo pass; the two known failures (PSD export, compare) are the author's dev server's
  stale optimize-dep hash (504), as before. Paint, selection, render pass.
- 171 offline tests; frontend build and lint clean (one more per-component Fast Refresh note); API contract regenerated.
- **PE4 closed** (D50–D53). Remaining Edit work: PE5 (PC22 mouse kit, PC20 layers panel, PC21 properties incl. the Curves spline and
  a Levels histogram), PE6 (PC23 transform, S2 → PC24), PC25 / PC26 with H3; the S1 go / no-go is the author's.

## 2026-10-10 18:31 — CI green on wave PE4

- Run 38067539037 at d1faf87: offline tests + frontend build for both variants (full, open) and both installers passed; the draft
  release job is skipped off tags. Wave PE4 (D50–D53) is closed on CI too.

## 2026-10-10 19:01 — D54 mask mechanics from PhotoCraft (the author: "painting on a new mask does nothing")

- **Reproduced first** (new headed mode `masks`, mouse events and screenshots only — the exact-compare extractor re-renders every
  pass, so it cannot see a stale stage): with D52 a brush stroke in the default colours (foreground black) on a new mask left the mask
  at 255 — the brush always painted **white** on a mask, whatever the colour, so on a white mask nothing happened; only the eraser hid
  (it painted black). Clicking the layer row also dropped the mask target, so the next strokes went into the pixels. Remove-then-add
  came out clean here (a fresh white mask), so the "previous painting appears" part was not reproduced; Pixi's "textureSource
  destroyed while still bound" warnings (pre-existing, on every scene rebuild) remain the suspect if it recurs.
- **PhotoCraft read** (b37bff98, subagent report; `doc` LayerMask, `engine` ToolState::MASK_COLORS / target_mask, `brush_cmds`
  eraser on grey targets, `mask_thumbs_ui`, `masks.rs`): sparse canvas-unbounded grey masks with a default value; an app-wide mask
  target synced to the active layer; a separate remembered mask colour pair; colours written as Rec.601 luma; the eraser on grey
  targets paints the background colour; Reveal / Hide All / Selection; Alt-click grey view, Ctrl-click load, Shift-click disable.
- **Ported (D54):** app-wide target kept across row clicks (adjustment / filter rows target their mask; the store clears it when the
  layer has no mask); the mask pair swaps in while a mask or Quick Mask is the target (persisted as `maskColours`), shown on the
  swatches; brush / fill / gradient paint the pair's greys, the eraser the background's grey, Delete clears to the background;
  `Mask.default` (schema 3) — compose fills outside the extent with the density-adjusted default, the editor pads the mask with a pass
  when the content reaches past its extent, Apply / merge down bake through `maskAlphaCanvas`, PSD export writes `defaultColor`;
  Add mask in four flavours (+ box: reveal, Alt: hide; with a selection: reveal / hide the selection); Alt-click grey view (painting
  continues on it), Ctrl-click load as selection, Shift-click disable with a red ✕. **One deliberate deviation:** the mask pair
  starts black / white (PhotoCraft and Photoshop start white / black, which repeats the author's "nothing happens") — the brush hides,
  the eraser reveals, X swaps.
- **Not ported:** sparse tiled masks (loom2 keeps one canvas per mask with an extent and the default outside), transforming an
  unlinked mask alone (PE6), the vector masks, the rubylith colour / opacity options.
- **Checks:** `masks` headed mode all pass (brush on a new mask → mask 2, stage −51.5/255; the eraser over it → 253, stage within
  0.9/255 of before; X → white; the row keeps the target; the pixel thumbnail brings the image colours back; Alt-click grey view
  and painting on it 251.7/255; Shift-click ✕; hide-all and the eraser bringing the layer back within 0.9/255). `paint` and `brush`
  updated to D54 (the brush hides on a mask) and pass; cmpdiag (incl. an unlinked mask moved off its layer — the 255 default padding),
  tour (now with a fresh dev server: PSD export and compare pass too), selection pass. Offline 172 (default-value test added); build,
  lint unchanged; API contract regenerated.

## 2026-10-10 19:08 — CI green on D54

- Run 38070065962 at 51b40fe: offline tests + frontend build for both variants (full, open) and both installers passed; the draft
  release job is skipped off tags.

## 2026-10-10 19:29 — Wave PE5 opened (D55–D57 recorded); D55 mouse-first kit landed

- **PhotoCraft read first** (subagent report on b37bff98: `workspace_ui.rs::sticky_mods`, `press_menu.rs`, `widgets.rs`
  `popup_value_field` / `dropdown_wheel_hovered`, `blend_preview.rs`, the layers panel, Properties, `compose/adjust.rs` `curve_lut`).
  Corrections to the plan: PhotoCraft's adjustment Curves are a **natural cubic spline** (flat outside the end points, clamped; each
  channel's curve before the master; LUT 4096) — not monotone; D57's row now says so. Its latches stay on until clicked again and only
  canvas tools read them; it has no Ctrl+Enter for transforms (loom2 adds it as planned).
- **D55 landed:** strip latches ⇧ / Ctrl / Alt (`mods(e)` ORs them into every canvas gesture: Shift-click line, Alt-click pick, selection
  add / subtract / intersect, Ctrl-wheel zoom, transform constraints); ✓ / ⊘ in the strip for the open polygon lasso too; Ctrl+Enter
  applies a transform; every `MenuButton` is a press menu (frame `openPressMenu`); `widgets.tsx` `ValueField` (scrub 0.5 / px, 0.01 for
  ranges ≤ 10, Shift ÷10; typed values and sums; ↑ ↓ from the nearest whole unit — PhotoCraft snaps to the step grid, which made Shift+↑
  from 25 % give 40 %, so loom2 snaps to whole units: 55.4 + 1 = 56, 25 + 10 = 35; ▾ press-drag over a 160 px slider; one gesture = one
  undo step) on opacity, fill, the six brush numbers and mask density / feather; `BlendSelect` (one mode per wheel notch ≈ 100 px of
  deltaY — a browser notch, not egui's 40 pt; the hovered mode renders through `blendPreview` and is never recorded; a click is one step).
- **Headed mode `kit`** (mouse events): latched Alt makes a brush click pick (#123456 → #617775, no history), stays on, clicks off;
  press–drag–release on *Add adjustment ▾* adds Invert in one gesture; click-open-click chooses Levels; a press on the open button
  closes it; scrubbing opacity 40 px left = −20 % in one step; ▾ drag +73 px = +50 % in one step; *100/4* Enter = 25 %; Shift+↑ = 35 %; a
  wheel notch steps normal → dissolve in one step; hovering *multiply* previews with the document unchanged; a click chooses in one step;
  Ctrl+Enter applies; the polygon ✓ shows in the strip; the menu audit over 12 tools and every layer finds 0 problems. masks, paint,
  brush, cmpdiag, selection, render pass; tour passes (one run missed the PNG download, the rerun had it — a timing flake). 172 offline;
  build clean; lint +1 (the `openPressMenu` export beside `showMenu`, same Fast Refresh note).

## 2026-10-10 19:45 — D56 layers panel like PhotoCraft's

- **Store:** `selectedIds` + `anchorId` (the selection counts only while it holds the active layer, PhotoCraft `selected_layers()`);
  `selectLayer` replace / toggle (never empties) / range along the panel order; `targetIds()` (top-level, panel order); set operations
  `deleteNodes`, `duplicateNodes` (copies above their originals, deep with pixels and masks, become the selection), `groupNodes` (the
  group takes the topmost's place), `mergeNodes` (rasters only; hidden ones dropped; bottom→top into a fresh union-sized canvas with each
  layer's blend, opacity × fill and mask — canvas blends, like merge down; one undo step with the old pixels swapped back), `setPropsFor`,
  `moveNodesTo` (above / below / into, Alt copies, a group never into itself). History: stack-only entries with one coalesce key now
  merge across layers (the eye sweep). Commands group / duplicate / merge / delete / visibility / lock act on `targetIds()`; the layer
  menu pluralises.
- **Panel:** Ctrl / Shift clicks; row drag (4 px threshold, ghost label, insertion line above / below, outline into a group's middle
  0.3–0.7, edge auto-scroll min(32, ¼ height) at 80–600 px/s, Alt copies); footer drops (`data-drop` on CommandButton: New layer and
  Duplicate duplicate, New group and Group group, the trash deletes); eye sweep (the press toggles that row, rows the pointer passes get
  the same state, one step); right-click inside the selection keeps it. The row grid now auto-flows its columns (D52's chain had made a
  sixth child).
- **Found by the headed check:** a row drag after a Shift-click died silently — Shift-click had extended the page's text selection, so the
  press-drag became a native text drag (pointercancel, no pointerup, leaked listeners). Rows are now `user-select: none`, a press clears
  any selection, native drag starts are cancelled and pointercancel ends the gesture.
- **Headed mode `layers`** passes: Ctrl adds, Shift range, Ctrl removes, never empty; Hide on the set in one step; dragging a selected
  row carries the set below the bottom layer in one step; a single row above another; into a group's middle (at its top) and out again;
  an Alt copy; an eye sweep over three rows in one step; drop on the trash deletes, on New layer duplicates; right-click on the set →
  *Show / Lock / Duplicate / Merge / Group / Delete layers*. kit, masks, paint, brush, cmpdiag, tour, selection, render pass. The tour's
  PNG-export step slept a fixed 2.5 s while the export runs the exact flatten first — it failed twice under load; it now polls up to
  20 s like the PSD step. 172 offline; build clean; lint unchanged.

## 2026-10-10 20:03 — D57 properties like PhotoCraft's; wave PE5 closed

- **Curves (compose + editor):** `compose.spline_lut` / `lut_lookup` and `frontend/src/suites/edit/curves.ts` port PhotoCraft's
  `curve_lut` (natural cubic spline, f64 tridiagonal solve, flat outside the end points, clamped, 4096 entries sampled at f32 positions,
  linear lookup); `interp: "spline"` curves apply each channel's curve before the master (PhotoCraft `tone_luts_q`); curves without
  `interp` (every document before D57) keep their straight lines, master first, exactly. New Curves layers default to the spline; the
  editor's 256-entry shader table is filled from the same LUT. `test_props_d57.py` (6): identity within 1e-4, S-curve monotone and
  bent, flat ends and clamped overshoot, passes through its points, channel before master, pre-D57 lines unchanged.
- **Oracle:** the psd-tools converter marks curves `interp: "spline"`. curves_rgb.psd: linear max 255 / mean 50.8 / 37 871 of 40 000
  pixels over 2 → spline max 12 / mean 0.38 / **3** pixels over 2 (all in the x = 0 column) — still a known failure by the 2/255 rule,
  reason updated; passes 8 → **9**, floor raised to 9.
- **Properties panel:** `propsEditors.tsx` — collapsible sections, quick actions per kind filtered to the enabled ones (new command
  *Ungroup*, store `ungroupNode`), the histogram of the visible pixel layers below (CPU, ≤ 384 px, canvas blends; RGB = mean of R, G, B;
  scale top = 251st-smallest bin × 1.1), Levels (triangles: the nearest grabs, black ≤ white − 2, grey → gamma = ln t / ln ½; output
  handles; value fields; Auto at 0.1 % clipping), Curves (16 points, 2-level gap, 9 px hit, 12 px drag-off removes and drag-back
  reinserts, Ctrl / right-click / Delete remove, arrows nudge; other channels drawn on RGB; editing a pre-D57 curve makes it a spline,
  said in the panel), Colour balance (tone segments, three gradient rows, double-click resets, Reset all tones; no preserve-luminosity
  box — compose has no such parameter). Clip to layer below and Reset to defaults under every adjustment. The JSON text fields are
  gone. PSD export reports pre-D57 linear curves as approximate.
- **Headed mode `props`** passes: quick actions on a pixel layer; a new Curves layer is a spline without JSON fields; add + drag a point
  in one step; GPU = exact (p99 0, max 0) for a 3-point spline and a red-channel spline; drag off / Ctrl-click / right-click remove;
  the Levels histogram is drawn, black triangle → 44 in one step, grey left → gamma 1.67, GPU = exact (max 0), Auto → 3 / 245 / gamma 1;
  a Colour balance row → midtones red 76 in one step, GPU = exact (max 1); a section collapses; Ungroup. Full regression: props, layers,
  kit, masks, paint, brush, cmpdiag, grid, tour, selection, render, psd pass; 178 offline + the corpus oracle; build clean; lint 96.
- **PE5 closed** (D55–D57). Left for the author: PE6 (transform, S2), PC25 / PC26 with H3, the S1 go / no-go.

## 2026-10-10 20:12 — CI green on wave PE5

- Run 38074280397 at b2a9974 (D55–D57): offline tests + frontend build for both variants (full, open) and both installers passed; the
  draft release job is skipped off tags.

## 2026-10-10 20:41 — Wave PE6 opened; D58 free transform like PhotoCraft's

- **PhotoCraft read first** (subagent report on b37bff98: `algo/src/transform.rs`, `resample.rs`, `engine/src/transform_cmds.rs`,
  `extra_cmds.rs`, `ui-egui/src/transform_tool.rs`). Corrections to the plan, D58 amended before the work: PhotoCraft has no persistent
  floating layer (a selection's pixels are lifted, warped and composited back into the same layer, the hole stays transparent, the
  selection moves along), no multi-layer transform (a group transforms its rasters together), no skew fields; proportions are kept by
  default (Shift frees them, as in Photoshop CC).
- **`transform.ts` rewritten as the port:** `Homography` (row-major 3×3, Heckbert square → quad, rect → quad, inverse, local scale);
  `warpRaster` — inverse mapping at pixel centres, nearest / bilinear / Catmull-Rom (Keys a = −0.5) on premultiplied pixels, transparent
  outside, colour clamped to alpha, U8 rounding half up; below 50 % (local scale at the centre) a real separable resize first (the Keys
  kernel stretched by 1 / scale, normalised, premultiplied) to a power of two, the homography rescaled; `warpGray` for masks and the
  selection (lifted, warped, flattened onto the default, the vacated part reading the default); `splitSelected` / `compositeOver`;
  `hitTest` (corners, edge handles at the image of each edge's middle, the pivot, 12 screen px; inside even-odd, else rotate), `applyDrag`
  (move with an 8-direction Shift lock, pivot, rotate with a 15° Shift snap about the pivot, perspective mirroring a corner on its
  neighbour, distort one corner, skew an edge — Shift along it, Alt both edges — and scale in the box's own unit frame, proportional by
  default, Alt about the pivot), `keepConvex` (40 bisections), `carryPivot`, `modeMods` for the menu modes.
- **Editor:** the transform state is `{ rect, quad, pivot, interp, mode, selection }`; `beginTransform` frames the raster (cut to the
  selection's bounds when lifting) or a group's rasters and captures preview canvases (linked masks baked in; with a selection the lifted
  part and what stays); the scene renders each moving raster as a 24 × 24 `PerspectiveMesh` (and the rest as a sprite) — the drag only
  moves mesh corners; `bakeTransform` resamples every target once from its current pixels, warps linked masks and the selection, trims
  transparent margins, and records one history step (`swap` + new `more` / `selSwap`). Flip H / V and rotate 90 / 180 / 270 are
  PhotoCraft's exact presets (nearest, integer offsets). The strip's transform bar: X / Y of the reference point, W / H % with a link,
  angle, interpolation, Free / Skew / Distort / Perspective, ✓ / ⊘; the same modes in the Transform menus; arrows nudge (Shift 10 px);
  the Free transform command now also takes a group.
- **Headed mode `transform`** passes: homography corner error 2.8e-14, inverse round trip 5e-15, collapsed quad degenerate; an integer
  translation pixel-exact under all three interpolations; an 8× shrink of a 1-px checkerboard → 128/255; corner drag proportional
  (960×544 → 864×490); Shift frees; Ctrl-corner distorts one corner; perspective mode mirrors (+30 / −30); a Shift rotation snaps
  (1.90° → −45°) about the pivot; Alt-click places the pivot; Shift+→ nudges 10 px; W = 50 % halves the width; apply in one step and the
  GPU = exact flatten (p99 0, max 1), undo restores; flip H twice and rotate 90° + 270° give back identical pixels; a selection lift moves
  only the selected pixels (+200, +200), leaves a transparent hole, moves the selection, GPU = exact (max 0), undo restores both; a group's
  two rasters scale together in one step (the 100 px square trims to 52 px, the full layer 960 → 480), GPU = exact, one undo restores
  both. Full regression (13 modes incl. psd) passes; build clean; lint 97 (the TransformBar component note).
- **Apply cost (Node, one thread):** perspective bicubic 103 ms at 1080p, 431 ms at 4K (bilinear 54 / 189, nearest 48 / 143); a
  prefiltered shrink to 30 % 61 / 166 ms — fine on the main thread for an apply.
- Not ported (PhotoCraft has them, D58 did not ask): Warp mode, Transform Selection (the outline alone), Transform Again, a session-local
  undo inside the open box, the 9-point reference locator, transforming an unlinked mask alone.

## 2026-10-10 20:46 — Spike S2: PhotoCraft's Quick Selection and Magnetic Lasso as WebAssembly

- **Build:** `engine/spikes/pcwasm` — `photocraft-algo` (local checkout b37bff98, by path) for `wasm32-unknown-unknown` with a plain C ABI
  (`alloc` / `set_image` / `quick` / `region_*` / `trace` / `path_ptr`; no wasm-bindgen, no JS glue). The crate already builds for wasm32
  (its rayon is native-only). `rustup target add wasm32-unknown-unknown` (one-time); release build with LTO, `panic = "abort"`, stripped:
  **25 s** cold. Module **109 309 B, 43 947 B gzip -9**; instantiation **0.6–0.7 ms**.
- **Measured** (`scripts/s2_wasm_bench.mjs`, a Node worker thread — the same V8 as Edge / WebView2; the bench source.png resized):

  | | 1920 × 1080 | 3840 × 2160 |
  | --- | --- | --- |
  | set image | 2.1 ms | 8.3 ms |
  | quick select click, 30 px brush (five places) | 48 / 59 / 63 / 62 / 112 ms | 61 / 77 / 90 / 98 / 119 ms |
  | quick select drag, 15 points, 40 px brush | 581 ms | 1 082 ms |
  | quick select click, 200 px brush | 692 ms | 810 ms |
  | magnetic lasso, 120 px segment | 1.9 ms first, then 0.7–1.3 ms | 1.9 ms first, then 0.7–1.1 ms |

  The same strokes **natively** (one thread): clicks 35–103 / 47–123 ms, drag 568 / 992–1 024 ms, 200 px click 637 / 819–833 ms — the
  wasm build is within ~5–10 % of native, so the cost is the algorithm (one banded min cut at half resolution above 512² px, as
  Photoshop works), not WebAssembly. Moving it to the orchestrator (S1's PyO3 route) would buy nothing and add a pixel round trip.
- **Reading:** the Magnetic Lasso is comfortably interactive (≈ 1 ms per pointer move). Quick Selection clicks feel immediate
  (50–120 ms), but a long drag or a large brush takes 0.6–1.1 s per evaluation — usable in a Worker if the tool evaluates on release
  (and at most every ~300 ms during a drag, showing the last result), not on every pointer move.
- **Recommendation: go** for PC24 with both tools in a Worker — Quick Selection evaluated on stroke end (plus throttled previews), the
  Magnetic Lasso live. A go is a stack change (house rules): the frontend gains a Rust → wasm build. Two ways to carry it: (a) CI and
  `scripts/setup` install the wasm32 target and build it (≈ 25 s cold), or (b) commit the 44 KB `.wasm` with its pinned PhotoCraft
  commit, a checksum and the build script, rebuilt only when the pin moves (no Rust needed for the app build). I would take (b).
  **The decision — and its D-number — is the author's**; PC24 waits for it. Licence: MIT OR Apache-2.0 (no EU issue).

## 2026-10-10 21:07 — The author's decisions (D59–D62); D59 Quick Selection and Magnetic Lasso landed

- CI green on the S2 commit (run 38077143470 at 1ff8522: both variants' offline tests and frontend builds, both installers).
- **Decisions (author):** S2 go → PC24 (D59); PC25 (D60) and PC26 (D61) now; S1 go → PC14 / PC15 (D62) — over the spike's no-go, so the
  content-aware pre-fill for Remove will be a switch (off unless the rig shows it helps) and Quick Remove its own mode. Order: PC24,
  PC25, PC26, PC14 / PC15.
- **PhotoCraft read** (subagent, b37bff98 `retouch_ui.rs`, `magnetic_lasso_ui.rs`, `smartselect_cmds.rs`, `magnetic_cmds.rs`). D59
  amended before the work: Quick Selection has no live preview in PhotoCraft — the whole stroke goes once, on release, its footprint
  trail showing meanwhile; every stroke adds (also the first), Alt subtracts, Shift does nothing; the Magnetic Lasso fastens by distance
  along the traced border, (8 + (100 − frequency) · 0.9) screen px.
- **Build pipeline:** the spike crate moved to `frontend/wasm/pcwasm` (C ABI: `set_image`, `quick`, `region_*`, `snap`, `trace_guided`,
  `path_ptr`); `scripts/build_pcwasm.py` refuses unless `../photocraft` is clean at the pin, builds (25 s), copies the module to
  `frontend/src/suites/edit/smartselect/pcwasm.wasm` (110 911 B; 46 KB gzipped in the Vite build) and records the SHA-256 in
  `pcwasm.pin.json`; `--check` (no Rust) runs in CI. The app build needs no Rust.
- **Editor:** `smartselect/worker.ts` (the module in a module Worker), `client.ts` (requests by id; the image sent once per key),
  `source.ts` (the active layer placed in the document, or the composite with *sample all layers*), `magnetic.ts` (PhotoCraft's rules:
  first click snapped, live guided traces latest-wins, distance fastening ≤ 64 per move, click fastens, Alt-click straight / Alt-drag
  freehand, Backspace, close by the first point / double-click / Enter / ✓ traced back to the start (Alt: straight), Esc / ⊘; commits
  through the polygon lasso's fill as "magnetic lasso"). Quick Selection: a new tool (toolbox, no key), size 30 px default, `[` `]` ×/÷
  1.25, the footprint trail while drawing, the result combined add / subtract (Alt with nothing selected does nothing — PhotoCraft
  would clear). Lasso kinds freehand / polygon / magnetic with Width 10, Contrast 10 %, Frequency 57; `[` `]` change the width.
  Backspace removes a point while a border is open (caught before Clear). The Tauri CSP gains `'wasm-unsafe-eval'`.
- **Checks:** headed mode `smartsel` passes — a 30 px click selects a 160 px red square on blue exactly (IoU 1.000, 25 600 px); a click
  in flat blue ≈ the brush disc (1 136 px); the next stroke adds (→ 26 736); Alt subtracts (→ 25 600, the square kept); the magnetic
  lasso's first click snaps to the edge (300, 154.5); moving 4 px off the edges traces and fastens; Backspace removes a point; clicking
  the first point closes a border on the square (IoU 1.000); Esc cancels; a stroke on the photo selects 66 492 px in 0.66 s.
  `csp_check.py` gained an `edit-wasm` page (`&wasmprobe=1`): clean under the production CSP; the negative control without
  `'wasm-unsafe-eval'` reports the Worker's CompileError. Regression: kit, layers, selection, tour, transform, masks, brush, cmpdiag,
  render pass; build clean; lint 99 (two option components).

## 2026-10-10 21:10 — D60 settings audit (PC25)

- `scripts/settings_audit.py`: a static scan. Every recipe field (all pydantic models in recipes.py) must be named — attribute, keyword
  or string key — by the job code (queue, engine graphs / client / supervisor, edit_ai, matting, poisson, tone, maskops, clips); every
  Settings / EngineSettings field by some orchestrator module other than config.py (an attribute, or getattr / a key); every top-level
  `/capabilities` key must say which recipe fields or settings it feeds (then they must exist) or be marked informational. An allow-list
  carries the reasons: the union's `kind`, RefImage.note (panel only), Inpaint.image_blob / mask_blob (10 §13 compatibility, unused with
  a document), the record's schema_version, mounted_model_trees (the roster), T2I.tier (a label; width / height carry the size) and
  h3_licence_confirmed (a UI gate, D17).
- First run: 5 findings — none a dead setting in the end: `stall_timeout_s` is read through getattr (the scan learnt string keys), two
  were nested `facesim` keys (the scan now reads the returned dict's own keys only), `T2I.tier` and `h3_licence_confirmed` are allowed
  with their reasons above. Now **149 fields and parameters, 0 problems, 8 allowed**.
- `test_settings_audit_d60.py` (2): the tree passes; an injected recipe field nobody reads fails with its name. CI runs the audit next to
  agents_check. (CI note: run on f21af1f failed agents_check on a backticked `../photocraft`; fixed in d777f39.)

## 2026-10-10 21:13 — D61 route fuzz (PC26)

- `orchestrator/tests/test_route_fuzz_d61.py` (PhotoCraft's `panic_hunt` idea): the app as the tests run it (a temporary project with an
  imported image and a document, the engine's python missing — no GPU), every operation in the OpenAPI document but `/shutdown` (the
  session enders last): path parameters as the real ids where we have them, then `0`, an encoded `../../etc`, 300 characters and `%00`;
  query parameters as junk; JSON bodies none / `{}` / a list / not JSON / the schema's properties with the wrong types; uploads as junk or
  empty bytes. Rule: no 500 (a 503 is an honest "not available") and an answer within 4 s.
- **Found:** `POST /engine/start`, `/engine/restart` and `/engine/free` answered **500** when the engine cannot start or is not running
  (start caught only `RuntimeError`; restart and free caught nothing). They now answer 503 with the reason (`RuntimeError`, `OSError`,
  `httpx.HTTPError`). Nothing else: **89 operations, 431 requests, 0 failures** in ≈ 10 s. 183 offline.

## 2026-10-10 21:30 — D62 content-aware fill and Spot Healing (S1 go, the author's call); PhotoCraft's proposals all done

- **Packaging:** the S1 crate moved to `orchestrator/native/pcalgo`; `scripts/build_pcalgo.py` refuses unless the PhotoCraft checkout is
  clean at the pin, builds the abi3 wheel with maturin (`uvx`), copies it to `orchestrator/vendor/` (223 KB) and records the SHA-256 in
  `pcalgo.pin.json`; `--check` runs in CI. pyproject's optional extra `native` installs it from the vendored path (`tool.uv.sources`);
  CI, `scripts/setup.ps1` and the README sync with `--extra native`. `loom2/native.py` wraps it and answers "not available" cleanly
  without it; `/capabilities.content_aware` (typed `ContentAwareCaps`) tells the UI; the settings audit caught the new key until it was
  mapped (Inpaint.mode, Inpaint.prefill).
- **Quick Remove:** `Inpaint.mode == "quick_remove"` runs in `queue._run_quick_remove` on the CPU — the engine is never started — at 1×
  over the selection's region, then the AI modes' paste-back (`assemble_layer`: feathered layer mask, seamless optional, a candidate in
  its group). **Pre-fill:** `Inpaint.prefill` content-aware fills the hole before upload, and the Remove graph's reference latent is then
  that image instead of mid grey.
- **Spot Healing:** `loom2/heal.py` ports PhotoCraft's `spot_heal_surface` — PatchMatch completion over the stroke + 2 px (content-aware
  fill when completion finds nothing), `poisson.seamless_clone` (smooth 0, the exact membrane) over + 1 px; `POST /heal` is stateless
  (the region's RGBA + the stroke coverage in, healed RGBA out; route snapshot and contract updated, raw reply listed). The editor's `J`
  tool sends the region around the stroke (± max(size, 8) + 8 px) from the visible composite (default) or the target layer, masks the
  reply by the stroke's coverage and draws it on a *Spot healing* layer above the target (created once, then reused) — one undo step per
  stroke.
- **Tests:** `test_heal_d62.py` (5): square dilation; content-aware fill removes a magenta blemish and keeps the rest; Spot Healing heals
  it and leaves everything beyond the + 1 px ring and the alpha untouched; the route round-trips and refuses bad sizes; a Quick Remove job
  runs to *done* with the engine's python missing and lands a "quick remove" layer with a mask. 186 offline (the D61 entry's "183"
  should have read 181). Headed mode `heal`: the healed pixel comes back as the stripe colour (90, 122, 58), undo takes it back, Quick
  Remove lands a masked candidate in 0.8 s; smartsel, tour, kit, selection, props, render pass; build clean; lint 100.
- **Rig** (`scripts/d62_remove_rig.py`, bench task 01, seed 7, cold engine): Remove 58.9 s — the crates become an AC unit and a wall
  (re-imagined, not empty); Remove + pre-fill 23.0 s — the model keeps the pre-fill's dark smear (worse, as S1 found with Fill-Match);
  Quick Remove 0.4 s — the same smear on this 320 × 210 hole. **The pre-fill stays off by default**, as D62 required; Quick Remove's
  panel hint says it is for small or textured areas. Sheet: `engine/spikes/out/d62/remove-task01-seed7.png`.
- **PE6 closed;** all PhotoCraft proposals (PC1–PC26) are decided and delivered.

## 2026-10-10 21:37 — CI green on D59–D62

- Run 38080084162 at 3152e54: offline tests + frontend build for both variants (incl. the new steps: settings audit, the content-aware
  wheel and smart-select WebAssembly pin checks, the vendored wheel installed by `--extra native`) and both installers passed. The runs on
  f21af1f, d777f39 and 1af077f were cancelled by newer pushes; e76b482 (D59–D61) passed.

## 2026-10-10 22:05 — the author's UI report: popup backgrounds, submenus over their parent, Multiply "resizing" a layer

- **Transparent pop-ups:** the blend list and the value field's slider pop-up used `var(--panel, var(--bg))` and the option hover
  `var(--hover, …)` — none of those variables exists in the theme, so both drew transparent. Now `--bg2` / `--bg3` like the context
  menu. A scan of every `var(--…)` in `frontend/src` found one more undefined name (`--bg` on the colour-balance slider thumb → `--bg0`);
  none remain. Headed mode `kit` asserts both pop-ups are opaque.
- **Submenu over its parent:** `ContextMenu`'s MenuList clamped a submenu that did not fit on the right back into the viewport — on a
  layer row near the right edge the Transform submenu covered the parent's Mask entry. A submenu now opens to the parent's left when the
  right side has no room; `.ctx-menu` is `width: max-content` because a menu placed at the edge measured narrower (its labels wrapped)
  than it rendered after the flip (13 px overlap). Headed mode `layers` hovers every submenu of a row's menu: overlap 4 px (the
  intended tuck) for Transform and Mask.
- **Multiply resizing a layer: not reproduced.** A temporary on-screen probe (diff against the layer hidden, devicePixelRatio 1.5, zoom
  86 %) for a full-size layer, a 200 × 150 layer at (500, 150), the same with a mask, and a full-size masked layer, through Normal,
  Multiply, Screen, Overlay, Color Burn, Difference, Hue in both orders: the layer's footprint never moved or changed size. Asked the author
  for the case (layer kind, size, mask, group, zoom). The probe was not kept.
- Build clean; headed `layers` and `kit` pass.

## 2026-10-10 22:33 — D63 AI Select by prompt up front; dev.ps1 start-up

- **D63:** the A tool's options and the AI panel's Select now lead with a **find** field (full variant): typing switches to SAM 3 text
  mode, clearing it in text mode returns to the BiRefNet main subject, Enter runs Select (the Select ▶ button stays the mouse path). The
  separate *text* row under SAM 3 went (the find field is that text). Headed mode `kit`: typing → `sam3 / text`, Enter runs one segment
  recipe with the prompt, clearing → `birefnet / subject`; `aiPanelStore` exposes `__loom2AiPanel` in dev builds for it.
- **dev.ps1:** the author could not start the app. The orchestrator starts alone (LOOM2_READY with a temp state) and the shell compiles
  (`cargo check` 3.4 s); port 1420 was held by a Vite this session had started for the headed checks (`TaskStop` ended its `sh` wrapper,
  not the `node` child) — `tauri dev` runs `npm run dev` with `--strictPort`, so it fails while that lives. Ending it was left to the
  author.

## 2026-10-10 23:12 — Review of the PhotoCraft range (ceb638d..a380612): registers U1–U29, F1–F18, R1–R10, all fixed

The author asked for another review after the UI report. Three read-only reviewers: the Edit UI against the code and the latest headed
screenshots (U, 29), the frontend changes (F, 18) and the orchestrator changes (R, 10, each reproduced with a scratch script). Fixes were
split by file so that no two hands touched the same module.

- **Orchestrator (R):** R1 Quick Remove saved a stale `OpenDocument` — a document deleted mid-job came back, one closed and reopened lost
  the layer; it now re-fetches after the CPU work and fails cleanly when the document is gone or resized. R2 a mask with default 0 and
  density < 1 stayed fully hidden outside its extent in the exact compositor while the editor showed it partly visible — the outside value
  now always goes through the density (matches `maskDerived.outsideValue`; the PSD corpus still passes its floor). R3 Quick Remove is
  admitted without a model (VRAM 0, no roster or variant gate). R4 it honours cancel. R5 it is marked non-resumable before it writes.
  R6 `POST /heal` checks Content-Length before reading, caps the area at 2048² and times out at 60 s (504). R7 the settings audit only
  counts reads through the recipe object (per-model receivers), with a negative test. R8 `blob_put` writes off the event loop
  (`persist`'s on-loop retry recorded as a footgun in `orchestrator/AGENTS.md`). R9 a missing native extension refuses Quick Remove and
  the pre-fill at submit (422). R10 a document from a newer loom2 (schema_version > 3) is refused (409) instead of being downgraded on
  save. `test_review_r.py` (13 tests).
- **Editor store and canvas (F):** F1 re-adding a mask overwrote the canvas undo still needed (history `maskSwap`). F2 Cut / Layer via
  cut cleared the mask while the mask was edited, and "cut" a locked layer — now clears the pixels and refuses locked layers. F5 canvas
  size, crop and an AI result that grows the canvas recorded the selection change in history (undo left a selection of the wrong size).
  F6 Spot Healing re-checks the document and layer after the request, respects the lock, and the first stroke is one undo step. F7 the
  quick-select cache key could collide (an app-wide version counter now). F10 a transform bakes the selection captured at begin;
  selection, flip / rotate, canvas and cut commands are disabled while a transform is open. F12 a generation counter drops stale magnetic
  traces. F13 locked children stay put in a group transform. F14 Load mask as selection reads the mask as it renders (the outside value,
  density and feather). F15 Fill, gradient, Clear and Cut keep Lock transparency. F16 transform previews are freed on undo / redo /
  open / close. F17 opening or closing a document resets the polygon, AI prompts and layer selection. F18 async selection loads check
  the document after the await.
- **Panels, keys and widgets (F):** F3 Enter never applied a transform — the key dispatcher stopped at the first matching command even when
  it was disabled (the polygon close); disabled matches are now skipped. F4 Esc cancels the magnetic lasso. F8 Delete in the Curves graph
  wiped the adjustment's mask (the global handler ran first). F9 the strip's latches now modify Layers-panel gestures too (D55 said so).
  F11 typing a value was one undo step per keystroke and applied 7 % on the way to 75 % — one step until Enter / blur, Esc restores.
- **UI (U):** U16 the canvas showed a stretched frame after Compare (the extractor never scheduled a redraw). U1 / U2 the strip squeezed
  and cut its items under the Inspector — it wraps now, and the free-transform bar floats over the top of the stage (so the canvas never
  moves under the pointer). U3 the Selection tab's Refine edge block sat in the wrong grid cells. U4 the last undefined CSS variable
  (Curves points). U5 Remove mask got an icon; the trash says "Delete layer mask" while a mask is edited; the mask section no longer repeats
  Remove. U6 one spelling per adjustment / filter type (`labels.ts`: "Hue/Saturation", "Colour balance" …) and per blend mode ("Color Burn"
  in the row too). U7 the AI button no longer promises Ctrl+Enter. U8 / U18 one tool table (toolbox and the canvas menu's Tool submenu,
  with accelerators and a check mark; Quick selection shows its icon instead of "()" ). U9 / U11 every number in the Edit panels is the
  same value field (the old range sliders, marquee feather and W/H, selection amount, canvas size, outpaint grow, new document size), with
  units and steps. U10 "sample all layers" is a checkbox everywhere. U12 segments and tabs read in sentence case; buttons too. U13 one
  colour-balance reset, Auto no longer stretched. U14 the mask row lays out on two rows. U15 toasts: at most three, a repeat replaces
  its older copy, × at the right edge. U17 keys are written Ctrl+ / Shift+ / Alt+ app-wide (no Mac glyphs), texts name the mouse route.
  U19 transform modes use the menu's check column. U20 quick mask button marks its own command. U21 one separator in the strip title.
  U22 no decision / spec references in UI text. U23 hard-coded colours → theme variables. U24 nothing below 11 px. U25 brush preset names
  line up. U26 Close document has an icon, the document list deletes with a trash icon. U27 menus scroll instead of running off short
  windows. U28 transform and Properties X/Y/W/H have practical ranges (the ▾ slider was useless at ±300000). U29 `.segmented`, `.tabs2`,
  `.insp-thumb` moved from catalogue.css to frame.css. Not done: pop-ups inside a scrolling panel can still be clipped by it (would need a
  portal); colour balance keeps its gradient tracks with plain numbers.
- **Checks:** offline 200 (was 186; incl. the corpus test with `--extra oracle`); settings audit 150 / 0 problems; agents_check clean;
  build clean; lint 100 warnings, 0 errors (unchanged). Headed: all 16 modes pass (render, paint, kit, layers, props, transform, smartsel, heal, masks, selection, brush, grid, psd, cmpdiag, tour, animate) — psd / tour first failed on Vite's "504 Outdated Optimize Dep" from the long-running dev server (re-optimised by touching vite.config.ts), not on the code. New headed assertions: popups opaque, strip fits, typing is one
  step, Enter applies a transform, Ctrl latch in the Layers panel, find field; heal's undo check accepts the first stroke removing its layer.

## 2026-10-11 08:05 — The review's two open UI items, the AI panel's layout, and adjustment layers at 150 % display scaling

- **Pop-ups no longer clipped:** the value field's ▾ slider and the blend list render through a portal with fixed positioning
  (`usePopupPlace` in `widgets.tsx`): below the anchor, above when the space below is short, inside the window, following scrolls and
  resizes. Headed `kit` asserts the blend list's parent is the page body.
- **Colour balance numbers:** each row keeps its gradient track and gains the shared value field (type, scrub, ▾ slider; `bare` — the
  row names it); headed `props` asserts the rows fit the Inspector (the first layout ran 30 px past its edge).
- **AI panel (the author: it overspills both ways):** the label grid's value column could grow past the panel — long mode / encoder option
  texts and segmented rows widened it (Inpaint 157 px, Refine and Outpaint 64 px of sideways scroll). Now `minmax(0, 1fr)`, dropdowns
  and text fields take the column, segments wrap; the mode names are short (detail in their tooltips); whole-number fields show no decimals
  (candidates "4", not "4.00"). Vertically: the tuning controls (encoder, LanPaint order, margin, min size, feather, expand, blend, colour
  match) moved into a collapsible **Advanced** section per operation, closed until opened and remembered, placed after candidates and
  seed; Outpaint's four grow fields are a 2 × 2 block. New headed mode `aipanel`: every operation, Advanced closed and open, nothing
  outside or squeezed, no sideways scroll.
- **Adjustment layers were stretched on screen at 150 % display scaling** (found while checking the colour balance screenshot; review U16
  had blamed the compare): the adjustment filter rendered its input at resolution 1 while Pixi copied the backdrop at the screen's 1.5, and
  the shader samples both at the same coordinates — the picture came out 4/3 wider and 3/4 shorter with a black band below, before any
  compare. The compare renders at resolution 1, where both match, so it reported max 1/255. Fixed with `resolution: 'inherit'` on the
  filter. New headed mode `adjscreen` judges the screen (black rows in the document's middle column: 168 → 0, before and after a compare).
  New adjustment layers are named with the shared labels ("Colour balance").
- Offline 200; build clean; lint 100 (unchanged); headed: all 18 modes pass (adjscreen, aipanel, render, paint, kit, layers, props,
  transform, smartsel, heal, masks, selection, brush, grid, psd, cmpdiag, tour, animate). The author reports the Multiply "resize" no longer
  appears.

## 2026-10-11 08:30 — H2 opens: D64–D66 recorded; P2 plan → finalize → submit (D64) built

- **Decisions:** D64 (P2 plan → finalize → submit), D65 (P1 model registry), D66 (P4 job origin; placement into the source's group
  not built — the author's call on D34) entered in 13 before the work.
- **Guard first:** `test_graph_parity_d64.py` compiles the 17 `pin_review` variants against the pinned object_info and compares graph
  hash and summary with `fixtures/graph_parity.json`, recorded on the unchanged code (17 graphs, 0 problems). It held through every
  slice below (`--parity-update` only for an intended graph change).
- **Slices:** finishers moved unchanged into `engine/finishers.py` (Asset / Document / Selection / Clip, `add_result_layer`,
  `run_quick_remove`); the one completion tail `JobQueue._complete`; pure `plan()` in `engine/pipeline.py` (effective params, needs,
  weights, warm group, VRAM, ETA — document jobs get warm baselines from the journal: Klein 28 s, dev 270 s, Real-ESRGAN 6 s, BiRefNet
  2.5 s, SAM 3 3.5 s, Quick Remove 1 s); `finalize()` absorbs the reference / document / i2v preparation and the compile; the engine
  follow code (event pump, follow, stall watchdog, outputs, free) moved to `engine/follow.py`; `_run_one` is plan → finalize → submit →
  follow → `irreversible()` → finisher → `_complete` (≈ 75 lines); the roster is rescanned only when a model folder's mtime moved;
  `persist()` snapshots and hands the write to one writer task (newest wins, call order kept), `await flush()` before a job starts, at
  C8's irreversible point, in every mutating job route (replies built before the flush — the first version let the queue start the job
  in between and the reply said "running") and at shutdown; the load at start writes synchronously. `queue.py` 1087 → 612 lines.
- **Preview for every kind:** `/recipes/preview` returns `T2IPreview | I2VPreview | DocumentPreview` with `weights`, `warm_group` and
  `problems` — the contract check of a compile on placeholder inputs (an image the engine lists) against the engine's last object_info
  (None before the first job). The Edit AI panel reads it (debounced; fresh random seeds do not re-plan): the ETA per candidate with its
  source, weights not fetched, and the problems the engine would refuse — the hard-coded "Klein ≈ 20–35 s" text is gone.
- **Tests:** `test_pipeline_d64.py` (11: plan per kind, preview problems = a submission's for an object_info missing a node class,
  Selection / Document finishers from output files without an engine, finisher per kind, the writer's order and its one-time error,
  the preview route for Edit recipes); three tests moved to the new functions (`finishers.add_result_layer`), one now flushes before
  reading `queue.json`. **212 offline**; settings audit 150 / 0 (it scans pipeline.py and finishers.py); API types regenerated; build
  clean, lint 100; headed `aipanel` asserts the ETA comes from the preview.
- **Rig owed:** `m5_acceptance.py` and `m6_acceptance.py` against this code, timings within ±10 % of 2026-10-07 / 2026-10-05.

## 2026-10-11 08:53 — H2 · P1 model registry (D65) built

- **Specs:** `orchestrator/loom2/models/` — `ModelSpec` (pydantic, strict), five TOML files (flux2, klein, wan22, ltx23, tools; 12 models)
  transcribed from the constants and checked value for value against them before they were deleted; `registry.py` loads them (plus
  folders in `LOOM2_MODEL_SPECS`) and validates every roster id at import; a spec may carry its own `weight` table for a weight the roster
  does not list. Lookups replace id literals: `default_model(kind, variant)` (variant-aware: Klein 4B / 4B base under `open`),
  `hero_model()`, `icm_model(variant)`, `segment_model(mode)`, `offered()`.
- **Builders read specs:** PRESETS, TE_ALTERNATES / TE_LABELS, VRAM_ESTIMATE_GB, BASE_SECONDS, I2V_WEIGHTS / I2V_RULES, WAN_PRESETS,
  LTX_STEPS, I2V_BASE_SECONDS, the negatives and the D64 document baselines are gone from `graphs.py`; the dev special cases became flags
  (`edit_steps` / `edit_guidance`, `edit_negative = zero_out`, `recipes.i2i`, `inpaint_hero`, `icm_default`), the upscale factor is data
  (no regex on the id), AI Select's model follows the mode. Recipe defaults and `inpaint_model_id` read the registry. **Graph parity
  17/17 unchanged** through every step.
- **/capabilities from the registry:** first-release keys kept; every model gains `recipes` / `inputs` / `geometry` and `short`, `hint`,
  `order`, `cfg_fixed` / `cfg_note`, `model_shift`; video models `preset_params`; new `tools` (upscalers, AI Select) and `defaults` (per
  kind, for the session's variant). AI Select's builders were renamed `matte` / `sam` so no builder name equals a model id.
- **Size policy:** T2I and I2V carry `size_policy` — `snap_down` (default, D18: never more pixels than asked), `snap_up`, `error` → 422
  `{field, value, allowed, message}` at submission and in the preview (frames reported as frame counts: 80 → allowed 77 / 81 on Wan). This
  changes the old round-to-nearest: 950 × 540 now runs at 944 × 528 (two tests updated). Submission now plans the recipe, so a bad
  sampler or size is a 422 at once instead of a failed job later.
- **Frontend (slice 4, by a sub-agent on frontend/src only):** `MODEL_RULES` and every hard-coded model id removed — `store/modelCaps.ts`
  helpers; Generate sorts cards by `order`, CFG / shift / refs hint from caps; Animate's rules, CFG / shift / split hints from
  `preset_params`; Edit's AI Select tools, refine / upscale lists, hero buttons and inpaint model from caps; the `open` special cases
  are gone (defaults are variant-aware). Behaviour change: under `full` the refine lists also offer Klein 4B base (its spec runs i2i).
  Left as prose (fields named for later): the stock negatives, the Full-tier dev timing hint, the encoder / steps hints, tool timings.
- **Tests and checks:** `test_registry_d65.py` (4): an unknown weight fails at load; **a spec file alone adds a model** (a fake Klein
  variant with its `weight` table appears in /capabilities, compiles t2i and runs ICM itself, defaults unmoved); the 422 shape at
  submission and in the preview; the sweep compiles every spec × tier / mode / preset (≥ 40 graphs, zero problems) with estimates rising
  with pixels and frames. `scripts/model_literals_check.py` (CI): 0 quoted roster ids in code outside specs, roster, tests and generated
  API files. 216 offline; settings audit 154 / 0; agents_check clean; API regenerated; build clean, lint 100; headed aipanel, kit, tour,
  animate pass. The add-a-model checklist in `engine/AGENTS.md` is now roster entry → spec → (builder for a new graph) → sweep → rig.
- **Rig (P2, running):** M5's background-swap check read the layer's pixel alpha, which D47 made opaque (the edge is a linked mask
  since 2026-10-10) — the script now multiplies the mask in; results with the next entry.

## 2026-10-11 09:28 — H2 rig (P2, P1) and P4 job origin (D66) built; H2 closed

- **Rig, first pass (P2 code d7ae242, temp state, project `F:/loom2-projects/acceptance-20261011-h2`):** M6 **17/17** — Wan Draft 246.2 s
  (2026-10-05: 256), Wan FLF 255.3 s (255), LTX with a beat 184.3 s (172, +7 %); all within ±10 %. M5 24/25: the background-swap check
  read the result layer's pixel alpha, which D47 made opaque (the soft edge is the linked layer mask since 2026-10-10) — the script now
  multiplies the mask in. A sub-agent ran headed checks (Edge on WebGPU) during this M5 pass, so its timings were not trusted.
- **Rig, quiet pass (P1 + P4 backend, the working tree after ad320a3):** dev T2I Turbo 960×544 109.6 s cold / 87.2 s warm (origin
  echoed on the job and the asset); **M5 25/25** (background swap: alpha on subject 0.026 / on background 0.996 — 0.027 / 0.996 on
  10-07; BiRefNet 2.7 s, SAM 3 text 32.5 / point 3.3 / box 3.2 s, upscale 4.1 s, **tiled refine 269 s** against 892 s on 10-07);
  **Wan Draft 247.1 s** (7/7). The Klein jobs per candidate are 14–37 % slower than on 10-07 (fill 46.5 vs 39.4, Fill-Match 27.0 vs 19.7,
  remove 23.1 vs 19.9, refine 53.4 vs 45) in both passes — **inside the engine**: every job spends 1–2 s outside its nodes (upload,
  paste-back, save) and the graphs are byte-identical to the pre-refactor ones (`test_graph_parity_d64`), so the difference is the
  machine / engine state since 10-07, not P2 or P1. Recorded as an open measurement (with the earlier tiled-refine swing), not a regression.
- **P4 (D66) backend:** `loom2/origin.py` `JobOrigin {suite, surface, ref?, payload?}`; `JobRecord.origin` (queue schema 2 — a version-1
  file loads with none), `AssetRecord.origin` (asset schema 2, copied at ingest by the Asset / Document / Clip finishers), `clip.ready`
  carries it; `POST /jobs` takes it, `POST /documents/{id}/ai` sets `{edit, ai, doc}` server-side. `test_origin_d66.py` (3): v1 queue
  loads, origin survives a restart and reaches the job events, the asset, its manifest and `asset.created`; the Edit route sets it.
- **P4 frontend (sub-agent, frontend/src only):** Generate, Animate (`{animate, clip, ref: the clip on screen}`) and the Catalogue
  re-run / variations verbs send an origin; the Dock's job rows gain **Go to origin** (menu + row button; `store/origin.ts`); Animate's
  `onClipReady` switches the player only when Animate is on screen, the job came from Animate and the clip it was asked from is still
  shown (a batch plays through) — otherwise a toast with **Play** (toasts gained a generic `action`); interim strips list their own
  suite's jobs (and pre-D66 jobs); the `loom2:` window-event bus is gone (`onEvents()` store subscription; PageView uses it).
  Not built: placement into the source's group (D34 stands; the author's call). The live acceptance scenarios (finish an Animate job
  while on the Catalogue; Go to origin on a Generate batch) need an engine job — they wait for P6's harness or the next rig session.
- Checks: 219 offline; settings audit 154 / 0; literal check 0; API current; build clean, lint 100; headed tour, animate, aipanel, kit
  pass. **H2 (P2, P1, P4) closed.** Next by the programme: H3 (P9 authenticated reads, P6 frontend test harness).

## 2026-10-11 10:02 — H3 opens: D67–D68 recorded; P9 every route authenticated (D67) built

- **Decisions:** D67 (P9 authenticated reads and WebSocket) and D68 (P6 frontend test harness) entered in 13 before the work.
- **Server:** `token_gate` covers every route but `/health` (36 GETs were open: settings, paths, prompts, pixels); the six media GETs
  (`/thumbs`, `/assets/{id}/file`, `/clips/{id}/proxy.mp4`, `/clips/{id}/frames/*`, `/documents/{id}/thumbnail`, `/blobs/*`) also take a
  read-only media key `?k=` — HMAC of the token, one per launch, handed out by the gated `GET /session` (deviation from 08's plan, which put
  it in the shell's `backend_info`: the session route serves the shell and browser dev alike) and printed on the READY line for scripts;
  it never opens settings, jobs, prompts or a write. The WebSocket accepts bare and closes with 4401 unless its first message is
  `{"type": "auth", "token": …}` within 2 s — no credential in a URL. `/docs`, `/redoc`, `/openapi.json` only with `LOOM2_DEV=1`
  (`export_openapi.py` calls `app.openapi()`); the access log was already off.
- **Frontend:** the session fetches the media key before the app marks itself connected; `api.fileUrl` / `thumbUrl` / `assetUrl` append it
  (every media URL already went through them); the event socket sends the auth message on open. Scripts already sent the token on GETs.
- **Tests:** `test_auth_d67.py` (4): the route matrix over all 76 OpenAPI paths (401 without credentials except /health; the key opens
  exactly the media GETs, nothing else, no write; a wrong key is 401; `/settings` is 401 bare), `/session`, the WebSocket's 4401 (wrong
  token, wrong first message, silence) and hello after auth, docs off unless dev. `conftest.py` gives test clients the token by default
  (`headers={}` tests the gate); route snapshot + API regenerated. **223 offline under full and open.**
- **Checks:** headed tour, animate, render, kit pass; new headed mode `media` — the Catalogue's thumbnails load through the key, none
  broken; `csp_check.py` clean on all six pages of the production build; **M1 rig acceptance 20/20** (162 s: generation, hard kill
  mid-job, paused relaunch, cancel, graceful stop). Settings audit 154 / 0, literal check 0, build clean, lint 100.

## 2026-10-11 10:35 — H3 · P6 frontend test harness (D68) built; H3 closed

- **Dependencies** (pinned exact, each ≥ 2 weeks old): vitest 5.0.2, jsdom 30.1.1, @playwright/test 1.63.0 (Edge via `channel: 'msedge'`,
  no browser download). npm 10.9.3 failed on vitest with an arborist bug ("Cannot read properties of null (reading 'edgesOut')" in
  `#loadPeerSet`); npm 11.20.0 through `npx` installed it cleanly — the lockfile stays version 3.
- **Unit (slices 1–2, a sub-agent):** `npm test`, **122 tests in 13 files, ≈ 2 s**. Pure code moved out of components into testable modules
  (`catalogue/pageLayout.ts`, `edit/planSize.ts`, `edit/parseNum.ts`; `queryOf`, `curve` / `channelMap`, `applyEvent` exported).
  `commandAudit.test.ts` is the D32 audit: it finds every `registerCommands` module by source scan, checks placements, unique ids, labels,
  chords that match their own key event, and shared chords within a scope only through an allow-list with reasons (Enter: polygon close /
  transform apply; Escape: polygon cancel / transform cancel; Delete and Backspace: clear / magnetic back). Demonstrated: a
  `matchChord` that returns false fails 7 tests; a command without a placement fails the audit. Two bugs the tests exposed, fixed:
  the Edit AI panel's engine size overshot the 1 MP cap (1920 × 1080 showed 1376 × 768, the engine runs 1360 × 768 — now the same step-down
  as `edit_ai._engine_size`, checked against the Python values); "Send to back" on album pages could tie with the item already at the
  back. Known vitest 5.0.2 quirk: a second dynamic `import()` of a `vi.mock`ed module while the first is in flight resolves the real one —
  `session.test.ts` routes store-bound frames one at a time.
- **Smoke and perf (slices 3–5, a sub-agent):** `orchestrator/tests/fake_comfy.py` runs standalone; `scripts/e2e_setup.py` builds a fake
  models tree for the registry's Klein 4B (the engine command is `python -c`, so ComfyUI can never start), the app.json and a synthetic
  project; `e2e/global-setup.ts` starts the fake engine and the orchestrator (`LOOM2_TOKEN=e2etoken`, the CI variant) and refuses a
  non-e2e build; `src/devHooks.ts` keeps the hooks in `--mode e2e` only (a production build has none — the setup's guard proves it). The
  e2e build goes to `dist-e2e/` so a plain build cannot replace it mid-run. Six scenarios with real mouse input: open the project (12
  thumbnails decoded), Keep / Reject / clear from the context menu, a pointer drag of a tile onto a group in Places, Generate on Klein 4B
  through the fake engine (the id from /capabilities) landing in Unprocessed, Edit on WebGL2 — a brush stroke dirties, Save stores, Animate
  start / end slots from the tile menus. **6/6 in ≈ 16–27 s, under full and open.**
- **First perf baseline** (`bench/perf/2026-10-11.json`; 10 000 assets, headless Edge 155, WebGL2, Ryzen 9 9950X, medians of 5): startup to
  first painted tile **194.5 ms** (cold ≈ 300); first Open in Edit incl. creating the document 224 ms; Edit → Catalogue 10.6 ms; **Edit
  re-entry 22.2 ms** (a 64 px document — P5 needs a large one); Catalogue → Edit → Catalogue 32.5 ms; scrolling 4000 px/s for 5 s: frame
  time p50 0.6 / p95 1.3 / p99 2.0 / max 17.9 ms, 0 long frames (uncapped: `--disable-frame-rate-limit`). Headless numbers, for change
  tracking on this machine — not presented frame times (`edit_headed_check.py perf` measures those). `scripts/perf_compare.py` diffs the
  last two files (`--fail-over PCT`).
- **CI:** `npm test` and `npm run build:e2e && npm run test:e2e` per variant (results uploaded on failure). Checks: 223 offline,
  122 unit, smoke 6/6, settings audit 154 / 0, literal check 0, API current, lint 100 / 0 errors. **H3 (P9, P6) closed.**

## 2026-10-11 11:08 — H4 opens: D69–D70 recorded; P10 idle pre-save in Edit (D70) built

- **Decisions:** D69 (P5 keep-alive stages, release policy, lazy suites) and D70 (P10 idle pre-save) entered in 13 before the work.
- **Slice 1 — what an AI job reads:** the open document. `DocumentStore.get` serves an open document from memory; the editor's stack PUT
  and layer-pixel PUTs update it; `prepare_document` flattens it. `test_presave_d70.py`: after a layer upload and a stack PUT, with no
  `POST /save`, the flatten shows the upload and the .ora bytes are unchanged until a save. So the idle flush never writes the .ora.
- **Store (editorStore):** `sync()` — the stack PUT (adopting the server's new revision, so the next PUT is not a 409; the C1 merge path
  unchanged) and only the dirty layers, two at a time, plus the selection when its version moved; no .ora, no toast; one flight at a time
  (waiters retry a failed one). `save({quiet})` = sync, then `POST /save` only when the .ora lags (`fileDirty`), the toast only for user
  saves; autosave is quiet. **Idle flush:** 1.5 s after the last revision change, never during a pointer gesture (the canvas reports
  `setInteracting`) or another flight. AI verbs, Refine Edge and the compare sync instead of saving. A document opens with its selection
  marked as already on the server. **Deviation from 08:** no `requestAnimationFrame` yield before the AI post — fetch does not block
  painting, and the yield cost ≈ 50 ms behind a busy frame on the headed run (click → post 63 ms → 31 ms).
- **Headed `aiclick`** (new): clean document, Select all then Inpaint — **31 ms** click → `/ai` request (budget 50; includes the selection
  upload made 0.6 s earlier); a 3840 × 2160 document with a brush stroke 2 s earlier — **1.6 ms** (budget 100; the idle flush had sent
  everything); no "Saved" toast. The candidate strip needs a live engine — not checked here. The mode also found a server bug: `POST
  /documents` with `background: "white"` reached the compositor and answered 500 — the field (and the document model) now accept
  `transparent` or `#rrggbb` only (422 otherwise; regression test).
- **Tests:** vitest `presave.test.ts` (6: the fast path sends nothing; sync sends the stack and only dirty layers, adopts the revision,
  writes no .ora, no toast; a stroke during a flight re-dirties and rides the next sync; concurrent syncs share one flight; save writes the
  .ora only when it lags and a quiet save toasts nothing; the selection is uploaded once per version). 225 offline (full and open), 128
  unit; headed masks, layers, selection, props, tour, heal pass; lint 100; API regenerated.

## 2026-10-11 11:38 — H4 · P5 keep-alive stages, release policy, lazy suites (D69) built; H4 closed

- **Step 0 (today's destroy path, headed Edge, 6 × 3840 × 2160 document, `edit_headed_check.py keepalive`):** Catalogue → Edit
  switch-back 208–216 ms to a rendered frame; zoom lost (370 → 216 ‰: the re-init refits). The headed Edge's dedicated GPU memory
  (`GPU Process Memory` counters over its process tree): Edit visible 388.6 MiB, Edit left (destroyed) ≈ 150, back 404 — the editor holds
  ≈ 240 MiB. Targets fixed before slice 2: switch-back ≤ 100 ms with zoom / tool / selection intact; the release frees the ≈ 240 MiB.
- **Keep-alive:** `SuiteDef.keepAlive` (Edit, Animate); `Stage.tsx` renders every visited keep-alive stage in a `hidden` wrapper with a
  `StageActive` context. The editor ignores 0 × 0 resizes, draws nothing while hidden and resizes + renders once on return (no refit);
  Pixi's `resizeTo` is gone (it would follow the hidden host to 0 × 0 on a window resize) — init takes the host size, the ResizeObserver
  the rest. **Deviation from 08:** no `app.stop()` — the editor's ticker was already off (`autoStart: false`, on-demand frames). The player
  pauses when hidden.
- **Release policy:** `stageKeep.ts` — `expire` (hidden longer than `ui.editKeepAliveMin`, default 10, checked every 30 s; Settings › App ›
  *Keep Edit / Animate loaded*, 2–60 min) and `releaseHidden` on `engine.vram_pressure`: the queue reads ComfyUI's `/system_stats` after
  admitting a GPU job and broadcasts it when free VRAM < `reserve_vram_gb + 1 GB` (log line; advisory — a failed probe changes nothing).
  The active stage is never released; a toast names what was.
- **Measured (same run, same document):** switch-back **57–91 ms** over three headed runs (medians 82, 75, 67.5 — budget 100), zoom /
  tool / selection / layers intact (`[370,"lasso",true,6]` both sides); GPU memory with Edit hidden and alive 386–392 MiB, then a
  pressure frame → **150–156 MiB** (236 MiB freed), Edit reloads the document in 212–245 ms. Composite of 6 × 4K p95 **6.8 ms** (budget
  7.1, M7), brush and player latencies unchanged.
- **Lazy suites:** Edit, Animate and Models load through `frame/lazySuite.ts` (static rail + flags; components on first render behind a
  skeleton); the Edit / Animate rails moved to `railTabs.tsx`. Startup chunk `main` 795 → 455 KB; the 658 KB Mediabunny chunk is no
  longer modulepreloaded (it sits in Animate's); `spikes.html` is built only with `LOOM2_SPIKES=1`. Edit's commands import the editor
  store (Pixi textures), so they register with Edit's code, which is preloaded on the first idle moment after startup; Animate's commands
  stay eager; a pointer over a tab preloads that suite. **Found on the way:** `React.lazy` suspends on its first render even for a
  resolved module and React 19 throttles the reveal (≈ 300 ms) — the first Open in Edit went 209–223 → 416–502 ms (A/B against HEAD,
  also with a 2 s settle, so not the chunk). Once loaded, the parts now render the suite's components directly (fixed per mount, so a
  part never switches type and remounts): **239–243 ms**.
- **Perf script (headless, `bench/perf/2026-10-11.json` replaced; the H3 numbers are in the 10:35 entry and in git):** first Catalogue
  tile 194.5 → **180.6 ms**; first Open in Edit 224 → 243 ms (wall clock incl. a Playwright round trip); Edit → Catalogue 10.6 → 9.8;
  **Edit re-entry 22.2 → 8.9 ms**; round trip 32.5 → 18.7; scroll p95 1.3 → 1.0 ms. The perf readiness for Edit is now "canvas on screen
  and a frame rendered since the switch" (a kept-alive re-entry has the same Pixi app).
- **Tests:** `test_keepalive_d69.py` (pressure at 1.2 GB free → one event with job, free and threshold; 12 GB → none; the job runs
  either way); vitest `stageKeep.test.ts` (6: visit / hide, expiry spares the active stage, release, the event releases a hidden editor
  with a toast and leaves the visible one, lazy meta + load once). 227 offline (full and open), 134 unit, smoke 6/6, perf 3/3; headed
  keepalive, perf, tour, animate, render, kit, aiclick, layers, media pass; CSP clean (incl. the lazy chunks and the wasm Worker); settings
  audit 154 / 0, literal check 0, agents 0, versions 0; lint 100; API regenerated (`VramPressure`). **H4 (P10, P5) closed.**

## 2026-10-11 13:14 — X1 opens: D71–D73 recorded; P11 send-to hub and P15 quick actions (D71) built

- **Decisions:** D71 (P11 + P15), D72 (P16 remappable keys) and D73 (P12 reference notes and `@`mentions) entered in 13 before the work,
  in build order: D71, then D72, then D73 (P12 needs a rig check of the notes).
- **Loupe hub:** under the facts strip, one bar with every verb of the tile menu — Keep / Reject / Clear, Rate ▾, Edit, Reference,
  Animate ▾ (start / end), Re-run, Variations, Duplicate, Move to group ▾, Lineage, Reveal, Pin, More ▾ (the tile menu). A press on
  the bar selects the loupe's asset first (the verbs act on the selection). Container queries: below 760 px the secondary verbs fold
  into More, below 480 px icons only. Seen in screenshots at 1600 and 900 px wide; the first narrow version wrapped to three rows and
  clipped More — fixed (no shrinking, tighter spacing).
- **Found on the way — press menus at the window's foot:** a menu that did not fit below its button was clamped up over the button, so
  a plain click (press + release on the button) chose the first item: the hub's Animate ▾ set a start frame. Press menus now open above
  their button when they do not fit below (`ContextMenu` `openerTop`), as submenus already flip left.
- **Drops explain themselves:** `DropTarget.describe(payload) → {ok, label?, reason?}`; the ghost shows ✓ + label or ✕ + reason with a red
  border. The rules are pure (`frame/dropRules.ts`: references, Animate start / end / beats, Edit open, layers), used for accept, drop
  and describe alike. Tile, lineage and album-page drags carry each item's media (image / clip). `resolveTarget` takes the innermost
  accepting target, else the innermost refusal with a reason. Two refusals are fixes, not just messages: a clip dropped on Animate's
  start or end slot or on beats used to be set as a frame and would fail at run time (frames go through Pillow), and the Generate tab
  added references past the model's `max_refs`. Reference drops are capped and a toast says what did not fit; a clip on the Animate tab
  plays it (as the tile menu's Animate does).
- **Spring-loaded tabs:** a drag resting 600 ms on the Edit, Generate or Animate tab opens it (a bar fills under the tab) and the drag
  carries on to a slot; the timer survives TopBar re-renders (job progress). **Edit's layers list** takes tiles: layers above the row
  they land on.
- **P15 quick actions:** `frame/openWith.ts` — `openWith(assetId, {suite, tool, aiOp, selMode, slot})` through dynamic imports (Edit is
  lazy, D69), and `?suite=edit&tool=ai&ai=select&sel=subject[&asset=]` deep links. `CommandCard` (a registry command as a card).
  Catalogue empty state: Generate an image · Import files · New document · Open a project; Animate's empty player: Animate from an
  image; the Inspector of one image: **Start from this image** (Remove background → Edit, AI Select · Subject; Upscale → Edit, AI
  Upscale; Animate from here; Variations), also a tile-menu submenu. New commands: `global.project.new` / `.open`,
  `global.start.generate` / `.newDocument` / `.animate`, `cat.start.removeBg` / `.upscale`. The tool list moved to a leaf module
  (`suites/edit/tools.ts`) so the frame can validate deep links without loading the editor; the editor store is exposed to dev hooks when
  it loads (the canvas did it before, so a test without a document could not read it).
- **Tests:** vitest `dropRules.test.ts` (15: every rule's labels and reasons, caps, dedupe, clips, unknown media, `resolveTarget`) and
  `openWith.test.ts` (3); Playwright smoke 10/10 — new: a tile held on the Generate tab opens it, the ghost reads "✓ Add as reference 1
  of 4 — or hold to open Generate", the slot takes it, a second drag of the same tile reads "✕ Already a reference" and the tab does not
  open; holds on Animate (end slot) and Edit (empty stage); the loupe hub's 13 verbs, the Animate press menu, the fold at 900 px and
  Reference from the hub; Remove background from the Inspector reaches Edit with tool `ai`, op `select`, selector `subject` and the AI
  rail tab, and `?suite=edit&tool=ai&ai=upscale` does too. 152 unit, lint 100, headed layers / animate / keepalive (median 71.8 ms) pass.
- **Seen once — a Pixi render error:** the first headed `tour` after a cold Vite start failed one step with an uncaught `TypeError:
  Cannot read properties of null (reading 'geometry')` in `BatcherPipe.execute` from `app.render()`, right after the known "textureSource
  destroyed while still bound" warnings of a scene rebuild (journal 2026-10-08, 10-10); the next frame drew and every later check
  passed. Nine more tours on the same server passed without it (the Vite log holds that one occurrence). Not caused by D71 (no render code changed); recorded as open with the stack.
- Startup chunk `main` 455 → 466 KB (drop rules, `openWith`, cards); Pixi and Mediabunny stay out.

## 2026-10-11 13:28 — X1 · P16 remappable keys (D72) built

- **Registry:** each command's own chords are kept aside (`defaultKeysOf`); the user's overrides (`keyStore.ts`: `loom2.keys`,
  `{schema_version: 1, keys: {id: chord | null}}`, a bare map from before migrated, junk dropped, a broken store = none) are written
  into `keys` / `alt` at registration and on every change, so dispatch, tooltips, menus, help and the palette follow without knowing
  (and lazily registered suites get them when they load). A command whose own key is an unmodified Arrow, Esc, Space or Tab is
  marked `fixed` at registration. `keymap.ts`: `remap` (refused for fixed commands, for the fixed keys, and when another command that can
  fire in the same place — same scope, or either global — answers to the chord, naming it), `resetKey`, `resetAllKeys`,
  `chordFromEvent`, and `SHARED_KEYS`, moved here from the audit test so the test and the remap check read one list.
- **The audit got wider:** shared chords are now checked across overlapping scopes (a suite and global), not only within a scope. It
  found two undeclared pairs — Ctrl+1 / Ctrl+2 are suite switches and Edit's 100 % / 200 % — which work by dispatch order (Edit's
  capture-phase hook stops them while a document is open, 10 §5); declared as `byDispatch` with that reason.
- **Keys moved into the registry:** the menu key (`global.contextMenu`, Shift+F10 / Menu), the palette and focus mode through their
  commands in `useKeyboardMap`; Edit's candidate picks (`edit.cand.1–4`, `edit.cand.keep` on Enter — registered first so Enter keeps a
  candidate before it closes a polygon, as before) and brush-opacity digits (`edit.brush.opacity.0–9`), with the four digit pairs and
  the two Enter pairs declared; the before key `\` (`edit.view.before`, still held: the hook matches the command's chord on keydown and its
  key on keyup); the loupe's Ctrl+0 / Ctrl+1 (`cat.loupe.fit` / `.one`, now the Fit and 1:1 buttons) and Compare's swap
  (`cat.compare.swap`, Tab, fixed, the Swap button). `TOOL_KEYS` deleted. **Found by reading:** Compare's Tab handler and the global
  focus-mode Tab were both window listeners, so Tab in Compare also toggled focus mode; Compare now listens in the capture phase and
  stops it.
- **Settings › Keyboard** (`KeyboardSettings.tsx`): search, by scope, click a key and press the new one (Esc cancels), × no key, ↺ back to
  the default, Reset all (askConfirm); a refusal shows the reason on the row; it preloads the lazy suites so the conflict check sees
  every command. Key changes apply at once (Save / Cancel do not touch them; the section says so). Help lists fixed keys as such plus a
  fixed-keys section, and its footer shows the keys in force. Command buttons re-render their tooltips on a remap.
- **Acceptance (Playwright, smoke 11/11):** the plan's example, Keep to **G**, is refused — G is Cycle grouping's — and the row says
  “Cycle grouping”; Keep to **J**: the tile menu, the loupe hub's tooltip and the help show J, J keeps (API), K no longer does, the
  setting survives a reload, ↺ restores K. Vitest `keymap.test.ts` (8: override resolution and dispatch, conflicts incl. global and alt
  chords, fixed keys both ways, null / reset / back-to-default, persistence across a reload incl. a later-registered command,
  migration, a broken store, chord recording); audit 6/6 with the wider rule; 160 unit; lint 100; headed tour, kit, brush, animate,
  render pass.

## 2026-10-11 13:36 — CI: the D72 smoke assumed a tile's state

- CI (full) failed the D72 scenario at "K does nothing": the synthetic project gives some tiles a state at random and the second tile
  was already kept, so the check could not tell. The test now arranges both tiles to no state through the API first (the open run had
  drawn other tiles). Not a product bug; local run passes.

## 2026-10-11 14:02 — X1 · P12 reference notes, @mentions, no silent truncation (D73) built; X1 closed

- **Read first:** references were truncated silently in two places — the compile (`graphs.py` `refs[:refs_max]`) and the preview count
  (`min(len, max)`) — not at the line 08 named; `finalize` uploaded the dropped ones anyway and the asset listed them as parents.
- **No silent truncation:** `kept_refs` is the one slice; the preview reports `refs_dropped` and the panel says how many are left out;
  `size_policy: error` answers a 422 `{field: refs, value, allowed: [max]}` on preview and submit; dropped references are not uploaded,
  not counted in the ETA and not lineage parents.
- **Notes:** `RefImage.note` (declared since M3, ignored until now; the settings audit had it on the allow-list as "never sent") goes
  into the prompt per model family — JSON models get `references: [{index, note}]`, prose / text a sentence per image ("Image 2 shows
  …"), numbered over the kept references. The panel has a note per reference under the slots.
- **@mentions:** `T2I.mentions` and `mentions.py resolve_mentions` — cover first, then the page in order (y, x), trashed and clip assets
  skipped, deduplicated against the explicit references, mentions taking turns so two groups both get images, only into the room left
  after the explicit references (a mention never pushes one out); each reference it adds carries the group's name as its note and the
  group id; each mention is stamped `{group_id, name, revision, asset_ids}`; a stamped mention is not resolved again (a stored recipe
  re-runs with the same images). `JobQueue.resolve_mentions` runs before `plan()` in submit (so the job record and the manifest carry the
  stamp) and in `/recipes/preview` (which returns `ref_list` and `mentions`). `@name` in any prompt string reads as the plain name.
  Panel: typing `@` (or the @ button) lists the album's groups; chips show what each gave; the references they resolved to show under
  the slots; × keeps the name as plain text; a loaded recipe comes back with its mentions unstamped. The album tree loads with the
  prompt field (the Catalogue may not have loaded it — found by the Playwright run: the menu said "No groups yet"), and a pick typed
  with `@` hands the caret back to the field (found the same way: typing after a pick went nowhere).
- **Rig check of the notes** (`scripts/d73_notes_rig.py`, 640 × 352, seeds 20261011 / 20261012; two reference stills made with Klein 9B:
  the bench heroine and the grey-bearded captain alone on grey): bench 02 and 08 on Klein 9B, 02 on dev Turbo, each with both
  references, without and with notes. **Identity: right in all 12 renders, no swaps or blends in either arm.** Klein 9B: the arms are
  nearly identical. dev: bench 02's text says "knitted cap" while reference 2 wears a peaked cap — without notes dev followed the text
  (0/2 peaked), with notes the reference (2/2). Timing unchanged (Klein 9.4–19.0 s, dev 84.9–102.7 s, both arms). Notes stay on
  whenever written. Sheet: engine/spikes/out/d73/sheet.png (local).
- **Tests:** `test_mentions_d73.py` (8: notes per family incl. only kept ones, @names read plain, drop reported / 422 / compile takes the
  kept ones, page order + cover + trash, turns + room + stamping + no re-resolve + dedupe + empty / unknown group, preview `ref_list` /
  `mentions` / `refs_dropped` / 422 over HTTP, a fake-engine job whose asset records both the stamp and the parents); vitest +3 (mentions
  in use, stored recipe, chip removal and notes); Playwright: "@hero … walks into @tavern …" typed with `@` picks — two chips, four
  references in the preview (turns, Klein 4B's limit), the serialised prompt reads "… walks into …. Image 1 shows hero …. Image 2
  shows tavern …", the job's recipe has both mentions at the groups' current revisions with two images each, × leaves plain text.
  235 offline (full and open), 163 unit, smoke 12/12, settings audit 160 / 0 (`mentions.py` joined the job code; `Mention.asset_ids`
  allowed as provenance), literal check 0, parity fixture +2 zero keys per t2i recipe (no graph changed), lint 100, API regenerated.
  **X1 (P11, P15, P16, P12) closed.**

## 2026-10-11 14:14 — CI found a Settings bug: opened before the settings load, the dialog stayed invisible

- CI (full) failed the D72 scenario after its reload: Settings › Keyboard never appeared. Cause: `SettingsModal` copied the settings into
  its draft once, when it opened; opened before `GET /settings` answered (right after a start or reload — CI's slower runner hit it),
  the draft stayed empty, the dialog rendered nothing and stayed open invisibly until closed. A real bug, not the test's: the draft is
  now the loaded settings until the first edit, and the dialog says "Loading the settings…" meanwhile. Smoke 12/12, 163 unit, lint 100.

## 2026-10-11 14:25 — CI (open): a typed @ before the album loaded; one unexplained page-load timeout

- The D73 scenario typed `@` before the album tree had arrived: the menu showed "Loading the album…" and never refreshed. Typed `@` now
  waits for the tree and then opens the menu (the @ button keeps the loading entry; the tree loads with the field, so it is rare).
- In the same run the Edit scenario timed out on its first page load (`.frame` not visible in 15 s) — it passed in every earlier run
  and in two local runs under `open` now; nothing in the annotation says why. Recorded as unexplained; watched in the next runs.
- Smoke 12/12 under full and twice under open; lint 100.

## 2026-10-11 15:24 — the two open points: the Pixi render error found and fixed; CI page-load failures can no longer go dark

- **Pixi "Cannot read properties of null (reading 'geometry')" (seen once in ten tours, 13:14).** Read Pixi 8.22: a `Batch` whose
  `batcher` is null is one `Batch.destroy()` has run on; only `GlobalResourceRegistry.release()` does that, and it walks the whole
  **global** batch pool array — which still holds batches a live renderer took from it (`getBatchFromPool` only moves an index).
  `release()` runs from `renderer.destroy(true)`, and the editor destroyed its app with `app.destroy(true)` (meant: remove the canvas;
  `true` also means releaseGlobalResources). Reproduced in Edge with the dev build's Pixi: a renderer rebuilds its scene, the pools are
  released, its next render throws exactly that message (whether it hits in the app depends on pool slot order — hence 1 in 10). In the
  app two editors overlap when React StrictMode's cancelled first mount finishes its slow init after the second started (a cold dev
  server — the 13:14 run), or on any remount during a slow init. **Fix:** the three destroys use `{ removeView: true }` (`KEEP_SHARED`);
  `editorLifecycle.test.ts` guards the source. Six cold-start cycles (Vite restarted, headed tour each): all passed, 0 render errors.
- **The "textureSource destroyed while still bound" warnings (≈ 180 a tour)** are not a fault: a stack probe put ~112 on pass render
  targets destroyed at scene rebuilds and the rest on layer canvases freed by undo GC; Pixi's batch bind-group cache keeps an entry per
  texture set, and destroying any texture ever drawn makes that entry warn, however late (destroying a frame later was tried: no change,
  reverted). Left as is, documented in the edit AGENTS; reusing pass targets across rebuilds would cut most of them if they ever matter.
- **The unexplained CI timeout (`.frame` not visible, 13:5x).** `App` renders `Frame` unconditionally, so the tree never rendered or
  React unmounted it — with no error boundary any render error blanks the window. Now: `ErrorBoundary` around the app and every lazy
  suite part (the Stage explains, the panel says one line, the others stay empty; Try again / Reload); a failed suite chunk is no longer
  cached by `lazySuite`, and because the browser keeps a failed module for the page, a chunk failure offers Reload first. The e2e
  `openApp` now attaches the page's errors, console errors, failed requests, HTTP ≥ 400 and the page text to its failure, so a
  recurrence explains itself. New smoke scenario: Edit's chunk refused by the network → one explanation in the stage, the rest of the
  app works, reload after the network is back → Edit loads. Smoke 13/13 under full and open, 164 unit, lint 100, headed tour / render /
  transform / masks / kit / perf pass (6×4K composite p95 7.0 ms).

## 2026-10-11 16:30 — Spikes open (D74); E13 timeline passed (D75); E12 angles running

- **D74:** the spikes E10–E14 run, one decision per result; the author approved the model downloads (licences read against D17 / D26,
  a losing method's weights deleted). Order: E12 (its method A is on disk), E13 (no rig), E10, E11, E14.
- **E13 timeline** (`frontend/src/spikes/e13Lane.ts` model + `e13Timeline.ts` view, `#e13` in the spike harness, runner
  `frontend/e2e/spikes/e13.run.mjs`; clips from `orchestrator/spikes/e13_make_clips.py`: 10 × 120 frames, 640 × 360, GOP 6, an 11-bit
  clip + frame code burned in). Headless Edge: **scrub** 260 checks (every cut ± 3 frames, 200 random seeks) — 0 frames off, the right clip
  every time, 5.6 / 13.2 ms p50 / p95 per step; **trims** with 50 clips, 240 steps of model update + forced re-layout — 0.6 / 0.9 ms p50 /
  p95; **crossfade** mid-dissolve pixel within 0.3 / 255 of the weighted mix; **export** EDL (35 lines) and FCPXML 1.10 (well formed,
  2 dissolves, 1176 frames); **bundle** +9.4 KB minified / 3.9 KB gzip. Vitest `e13Lane.test.ts` (7). Verdict: **pass → D75**; the Resolve
  import of `engine/spikes/out/e13/e13.fcpxml` / `e13.edl` is left to the author (Resolve is installed; opening it is theirs to do).
- **E12 angles** (`engine/spikes/e12_angles.py`): ten frozen sources in `bench/angles/` (Klein 9B from bench/t2i 01–10, 1024 × 576, seed
  20261011, `sources.json`); methods A (Qwen-Edit 2509 fp8 + the dx8152 angles LoRA + Lightning 4-step) and C (Klein 9B + the source as
  ReferenceLatent + an English camera instruction) over five moves are running; method B's weights (2511 Q4_K_M + fal's angles LoRA +
  lightx2v's 2511 Lightning, Apache-2.0, ≈ 13.4 GB) are downloading through `scripts/fetch_weights.py --only e12`. First numbers for A:
  cold 428 s, warm 90 s (bars 180 / 60) — the 20 GB transformer and the 8 GB encoder do not fit together, so each job re-stages weights;
  sampling itself is ≈ 10 s.

## 2026-10-12 16:59 — Spikes E10, E11, E12, E14 measured (D76–D79); the first chain ran Klein with the wrong encoder

- **The encoder (the author's catch).** The first chain (from 2026-10-11 16:30, stopped by the author this morning) hard-coded Klein 9B's
  fp8 Qwen3-8B encoder (8.7 GB) in the spike graphs; D31's presets run the Q4_K_M GGUF (5.0 GB). On 16 GB the fp8 encoder and a 9B
  transformer do not fit together, so both streamed from RAM: Klein base 492–493 s a scene (30 steps at 16 s/it), `klein_clay` 68–90 s,
  `klein_plain` 39–50 s, E12's C 15.8 s warm. The spikes now take the encoder from the registry and roster (`klein_te()` in
  `engine/spikes/e12_angles.py` → `graphs._te_loader`, so a spike cannot drift from the app), and every Klein method was re-run on a
  restarted engine: base 36–37 s, `klein_clay` 12.0 s, `klein_plain` 10.0 s, C 5.8 s. The first chain's rows stay in each `results.jsonl`
  (scoring takes the latest row per key); A and B (Qwen's own encoder) and the frozen sources were unaffected and kept.
- **E12 angles** (`engine/spikes/e12_angles.py`; 10 sources × 5 moves × 3 methods; sheets `engine/spikes/out/e12/sheet_<move>.jpg`, the
  move counts judged on them):

  | Method | warm / cold | identity (median; ≥ 0.5; face lost) | left45 | right45 | top-down | close-up | wide |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | A `qwen_angles` — 2509 fp8 + dx8152's LoRA + Lightning | 31.6 s (max 89.7) / 428 s | 0.67; 30/45; 5/50 | 8 | 7 | 9 | 9 | 5 |
  | B `qwen2511_angles` — 2511 Q4_K_M + fal's LoRA + Lightning | 153.6 s / 118–142 s | 0.72; 31/48; 2/50 | 5 | 8 | 9 | 4 | 9 |
  | C `klein_prompt` — Klein 9B + `ReferenceLatent` + a camera sentence | 5.8 s (max 12) / 39 s | 0.50; 21/42; 8/50 | 6 | 7 | 9 | 10 | 9 |

  Bars: ≥ 7/10 per move, identity ≥ 0.5, warm ≤ 60 s, cold ≤ 180 s, kill B over 90 s warm. No method clears all five moves: A rotates
  (the LoRA's own instruction) and frames close, C does not reliably rotate but frames (top-down, close-up, wide) from the prompt alone
  at 5.8 s; B is the best on identity and killed on speed — its 14.4 GB deleted, manifest entries retired. A's cold 428 s is I/O: the
  20 GB transformer and the 8 GB encoder re-staged from disk once a session. → D77 (proposed, the author's call).
- **E10 Stage → image** (`engine/spikes/e10_stage.py`; passes from `frontend/e2e/spikes/e10.run.mjs` over the 10 blockings of
  `bench/stage/scenes.json`; sheet `engine/spikes/out/e10/sheet.jpg`):

  | Method | PCK@0.1 | depth ρ | warm | × plain | same blocking (eye) |
  | --- | --- | --- | --- | --- | --- |
  | `klein_clay` (1) | 0.60 | 0.78 | 12.0 s | 1.20 | 10/10 |
  | `klein_clay_pose` (1 + the pose map as image 2) | 0.64 | 0.74 | 24.0 s | 2.40 | 10/10 |
  | `base_refcontrol` (2) | 0.86 | 0.63 | 73.9 s | 2.00 | 9/10 |
  | `zimage_depth` (3) | 0.30 | 0.68 | 13.0 s | 1.57 | 6/10 |
  | `zimage_pose` (3) | 0.08 | 0.41 | 12.9 s | 1.55 | 6/10 |
  | `zimage_depth_kr` (3, then Klein base I2I 0.5) | 0.29 | 0.68 | 54.0 s | 6.51 | 6/10 |

  Plains: Klein 0.01 / 0.41 / 10.0 s, base 0.04 / 0.57 / 37.0 s, Z-Image 0.03 / 0.37 / 8.3 s. The depth metric's ceiling is 0.89 (DA3
  on the clay renders themselves against the rendered disparity), so the 0.85 bar sits at the ceiling. Bars: PCK ≥ 0.8, ρ ≥ 0.85,
  ≤ 1.5× plain, blind ≥ 8/10 — no method clears all four; the clay reference keeps the shot and misses the pose bar, RefControl clears
  the pose bar at 2× and 74 s. Z-Image's Fun ControlNet renders the figure at the wrong scale (close-ups where the blocking has a full
  figure) and leaks the mannequin; its weights go (Turbo bf16 12.3 GB + the ControlNet patch 2.0 GB deleted, manifest retired).
  → D78 (proposed, the author's call).
- **E11 Stage → video** (`engine/spikes/e11_video.py`; five 121-frame shots from `frontend/e2e/spikes/e11.run.mjs`, guides encoded with
  PyAV, start frames by `klein_clay`; sheets `engine/spikes/out/e11/sheet_<method>.jpg`). PCK@0.1 on every 20th frame per shot
  (crouch_crane, run_track, turn_orbit, walk_dolly, wave_static): `ltx_ic_depth` [—, 0.66, 0.81, 0.59, 0.94] followed 4/5 · 147.0 s =
  1.22× plain · cold 146 s; `ltx_ic_pose` [—, 0.58, 0.88, 0.47, 0.94] 3/5 · 146.9 s; `ltx_plain` [—, 0.07, 0.50, 0.18, 0.93] 2/5 ·
  120.0 s · cold 178 s. The crouch shot scores 0 for every method because SDPose finds no person in its frames (a crouched figure
  beside a mannequin); on the sheet the depth clip keeps her crouched while the camera cranes up, the plain clip stands her up and
  walks her off. Bars: no OOM, ≤ 2× plain, ≥ 4/5 followed → **pass, D76**. The IC-LoRA (Lightricks, one file) stays; the depth pass is
  the guide, the pose pass a weaker second.
- **E14 image → mesh** (`engine/spikes/e14_mesh.py`: ComfyUI's own `3d_pixal3d_trellis2_image_to_model` template converted to the API
  format by `engine/spikes/ui_to_api.py`; five props in `bench/mesh/`; lit views, silhouettes and triangle counts by
  `frontend/e2e/spikes/e14.run.mjs` (`#e14`, three.js GLTFLoader); IoU against each prop's own BiRefNet cut-out at the best of 8 yaws ×
  3 elevations after a uniform scale and centre alignment; sheets `engine/spikes/out/e14/sheet_<method>.jpg`). Pixal3D: IoU [0.98, 0.95,
  0.99, 0.93, 0.90] 5/5, plausible backs 5/5, 46–50k triangles, warm 243 s (221–384), cold 361 s. TRELLIS.2: IoU [0.85, 0.46, 0.86,
  0.74, 0.70] 1/5 (the lantern comes out as a crumpled black shell), backs 4/5, 44–50k, warm 99 s, cold 146 s. No OOM at 1024 for
  either (int8 runs on ROCm). 08's "512 then 1024" is not available: 0.39's `Trellis2UpsampleStage` floors at 1024. Bars: warm ≤ 120 s,
  cold ≤ 300 s, ≤ 50k, IoU ≥ 0.85, backs ≥ 3/5 — Pixal3D clears every bar but time (2× warm, 1.2× cold); TRELLIS.2 clears time and
  fails shape, its transformer deleted (5.3 GB; the VAEs, DINOv3 and MoGe are shared and stay). → D79 (proposed, the author's call).
  Found on the way: the converter missed V3 dynamic combos (`sign_mode.qef`-style sub-inputs), `COLOR` / `LOAD_3D` widgets and inputs
  the template predates (now the schema defaults), so the first E14 runs "succeeded" in 0.4 s with no mesh — ComfyUI runs a prompt
  whose other outputs validate and reports the bad node only in `/prompt`'s `node_errors`; `Engine.run` now treats `node_errors` as a
  failure.
- Checks: 235 offline, 171 unit, lint 100 (the baseline), model-literals and agents-check clean, tsc clean.

## 2026-10-12 18:07 — E12 follow-up: the cold bar was a hard disk (D80); a strict-reference prompt lifts Klein's identity; dev + angles LoRA too slow

- **The author's decisions on the spike proposals:** D78 accepted (clay reference by default, RefControl as ST3's "exact pose" switch),
  D79 accepted (Pixal3D at 1024 as P18's background job), D77 "both recommendations" plus a web search for a third angles method.
- **The search** (forums, model cards, 2026-10-12): the Qwen-Image-Edit-2511 angles LoRA we killed is the community's standard
  (ComfyUI's own camera node targets it); a Qwen-Image 2.1 Multiple-Angles LoRA (akhaliq, 2026-10-07, Apache) sits on a 7B unified
  gen + edit base our engine supports — but the base is under the Qwen Research License (non-commercial), so `full` only at best under
  D17, and it has no verified 4-step distillation: noted, not fetched. Nunchaku int4 is CUDA-only (out on ROCm); Z-Image-Edit is
  unreleased; video-orbit tricks cost a clip per frame. Two things were worth running: lovis93's fal-trained 72-position multi-angle
  LoRA for FLUX.2 dev (the only angles LoRA for a FLUX.2 model loom2 runs; openrail-m, 332 MB) and the prompt shape of a Civitai
  Klein character-sheet workflow (strict visual reference, the view named twice, "only the viewing angle changes"; native nodes).
- **The disk.** D: — where method A's 30 GB lived — is a SATA hard disk (83 MB/s measured; F: is NVMe at 1.2 GB/s). A's 428 s cold
  load was disk time. The author: D: is a backup drive only, F: is the model repository → **D80**: the D: mount is gone from
  `engine/extra_model_paths.yaml`, `Settings.mounted_model_trees` defaults to `[]` (the author's `.loom2_state/app.json` too), the
  spikes and `scripts/m1_acceptance.py` scan F: alone; A's four files, `qwen_image_vae.safetensors` and `sam3.pt` (≈ 34 GB) copied to
  F: — nothing else loom2 runs came from D: (roster check: no entry resolves only there). Nothing on D: deleted. The engine loads A
  from F: (its log). 235 offline tests pass with the new default.
- **E12 follow-up** (`engine/spikes/e12_angles.py` methods `klein_prompt2` = C2 and `dev_angles` = D2; sheets regenerated with five
  columns): A's cold from F: **27.2 s** (file cache warm from the copy; a cache-cold load adds ≤ 30 s of I/O at 1.2 GB/s), warm
  31.6 s. **C2** (Klein 9B + the strict-reference prompt): 6.0 s warm, 20–24 s cold; rotations no better than C (left 4/10, right
  4/10 — the prompt makes Klein copy the source) but identity 0.72 on the rotations (C: 0.50) and on the framing moves the same
  correctness as C (top-down 9/10, close-up 10/10, wide 9/10) with identity 0.56 over all 50 and the face lost 7/50 (C: 0.50, 8/50).
  **D2** (dev fp8 + Turbo 8 steps + the LoRA at 0.9): identity 0.74, rotations 4–5/10, warm 104.7 s (68–115) against the 60 s bar —
  killed; the LoRA deleted (332 MB), manifest retired.
- **E12 verdict, revised (D77 accepted):** rotations by A (left 8/10, right 7/10, identity 0.67, 31.6 s warm, 27 s cold), framing
  moves by C2 (9 / 10 / 9, identity 0.56, 6 s warm, 24 s cold) — every bar of 08 §7 met by the pair. Nothing on D:.
- Also found: `powershell -File` (Windows PowerShell 5.1) refuses the repo's scripts under the machine's execution policy; `pwsh`
  runs them. A chain that started the engine that way waited forever — start the engine with `pwsh` (or `-ExecutionPolicy Bypass`).

## 2026-10-12 18:48 — D: cleared of the six duplicates; 16-ui-suite-stage.md written (D81 proposed)

- The author: delete what is left on D: and continue as recommended. The six files copied to F: on D80 (A's four, the Qwen VAE,
  `sam3.pt`) were deleted from D: after a size check against their F: copies (D: 126 → 158 GB free); the rest of the author's old
  ComfyUI tree on D: is untouched and no longer mounted.
- **16 · Stage UI document** written as the P13 gate (D12): layout (Rail Library · Outliner · Cameras · Poses · Shot; a gizmo bar in
  the viewport, camera view with the framing rectangle, pass preview in the Strip), the procedural mannequin of E10 as the first figure,
  cameras in mm on a 36 mm sensor, `stages/<id>.json` with `revision` 409, passes as `stage-pass` assets, `StageShot` with the two
  D78 methods and their measured times, ST4 clips through D76's IC-LoRA on the depth pass, keys as registry commands, the acceptance
  list from 08 §8, four open questions (sensor convention, the mask pass, the exact-pose method's third reference, image planes in
  the clay pass). Recorded as **D81 (proposed)** — ST1 code starts when the author approves 16. 00-README lists it.

## 2026-10-12 19:30 — P14 built: the New angle tab (D82); rig acceptance 50/50 through the app

- **Backend.** `Reangle {asset_id, move, method: auto | angles_lora | klein_prompt, prompt_text, seeds, te_id}`; `auto` takes the first
  offered spec (by `order`) whose `recipes.reangle_moves` lists the move — Klein 9B for top-down / close-up / wide (Klein 4B under `open`,
  Klein 9B being flux-nc), the new `qwen-edit-2509-fp8` spec (`specs/qwen_edit.toml`, graph `qwen_edit`; roster entries for the fp8
  transformer, the Qwen2.5-VL encoder, the VAE, lightx2v's Lightning and dx8152's angles LoRA, all Apache → both variants) for the
  rotations. `graphs.build_reangle` ports E12's graphs (A: `TextEncodeQwenImageEditPlus` + Lightning + the angles LoRA at 1 MP, AuraFlow
  shift 3, CFGNorm; C2: `ReferenceLatent` + the strict-reference prompt at the source's size); `pipeline.prepare_reangle` uploads the
  source, the plan names the resolved method and its measured seconds, the finisher stamps `lineage_kind = reangle` with the source as
  parent; `/capabilities.reangle {moves, methods, auto}`. The object_info fixture grew the four Qwen classes. `Engine.run`-style
  variant awareness: every job-code reader asks `reangle_model_id(recipe, variant)`.
- **Frontend.** A Generate rail tab **New angle** (`suites/generate/AngleTab.tsx`): the source slot (drop with D71 verdicts from
  `dropRules.angleDrop`; clips refused), a five-button move pad, a method select that names Auto's pick, one optional sentence,
  candidates 1–4, the foot's **New angle ▶** with the method and ≈ seconds or the reason it is disabled. Entry points: `cat.start.angle`
  in the tile menu's "Start from this image", the Inspector's card and the loupe hub; `openWith(…, {suite: 'generate', slot: 'angle'})`.
- **Checks.** `test_reangle_d82.py` (8: auto per variant, both graphs against the engine contract, weights, lineage, plan, preview,
  capabilities under `open`), 2 unit (recipe body, drop rule), a smoke scenario (tile → the Angle tab → Wide → job → the asset with
  `reangle` lineage on the fake engine): 243 offline, 173 unit, smoke 14/14, lint 100, build clean, settings audit and model-literals
  clean, OpenAPI + TS types regenerated.
- **Rig acceptance** (`scripts/reangle_acceptance.py`: the ten E12 sources imported, 50 `Reangle` jobs through `POST /jobs`,
  19:16–19:29): angles LoRA 20/20 done, warm median 26.4 s (bar 60), cold 39.5 s (bar 180; the engine started on that job), ArcFace
  identity median 0.66 (14/19 ≥ 0.5), lineage 20/20; Klein 30/30, warm 6.2 s, cold 21.4 s, lineage 30/30, identity median 0.28 over the
  21 faces ArcFace found — the framing moves are where faces are tiny (top-down, wide) or restyled (close-up), so the number is weaker
  than E12's all-moves 0.56; on the sheets the close-ups keep the person 9/10, the wide shots 9/10 (03 loses the figures), left 7/10
  with this seed. Sheets in `engine/spikes/out/reangle/`. The plan's orbit sphere became a pad: the methods know five moves, not a
  continuous orbit. 09 §3f and 08 §9 P14 record the build.

## 2026-10-12 21:35 — P17 slice 1: the Sequence tab (D83) — document, routes, exports, the lane lifted from E13

- **D83 recorded first:** the single-lane timeline lives in Animate as a *Sequence* rail tab until Story's Episode tab exists (14 / loom
  P5); the lane runs at the project fps, a clip at another rate (Wan 16 fps) takes its duration in ticks and is scrubbed by nearest
  frame — no frames are made (D27: RIFE at export stays post-MVP, Q14); the exports carry each clip's native rate for Resolve to conform.
- **Backend** (`orchestrator/loom2/timelines.py`, `routes/timelines.py`): `Timeline {schema_version, id, name, fps, w, h, clips
  [{id, clip_id, in, out, fps?}], overlaps, revision, …}` as `timelines/<id>.json` (fsio), `check()` for the invariants (one overlap per
  clip, the first a cut, a dissolve shorter than both clips, `out` within the clip's frames when the clips are known), `put()` with
  the document-style 409 on a stale `revision`, EDL (CMX 3600; a dissolve as a "D nnn" event, source times at the clip's own rate)
  and FCPXML 1.10 (a `format` per rate, an asset per clip by proxy file URL, cross dissolves in the spine) written into
  `timelines/<id>/`; routes list / create (fps and size from the project format) / get / put / delete / export; `timeline.updated`
  events. The route-table snapshot (D37) and the OpenAPI contract regenerated.
- **Frontend:** `suites/animate/lane.ts` — the E13 model with `ticks()` for per-clip rates, `at()` by nearest frame, `trim`,
  `setOverlap`, `append`, `remove`, `move`, `toEDL` (the parity fixture: the same three-clip lane gives the same EDL text in
  `lane.test.ts` and `test_timeline_d83.py`); `sequenceStore.ts` (sequences, the open lane, selection, playhead, a 64-deep undo stack,
  saves debounced 300 ms with the revision, 409 → reload and a toast); `SequenceStage.tsx` (Mediabunny sinks per clip, the frame at
  the playhead with two frames mixed mid-dissolve, rAF playback at the lane fps, the lane with ruler / blocks / trim handles /
  dissolve grip / playhead, Ctrl+wheel zoom, context menus); `SequencePanel.tsx` (sequences + the clip bin with drags through
  `drag.ts` and D71 verdicts from `dropRules.laneDrop`, the Inspector with exports and the clip's verbs); 20 `anim.seq.*` commands
  (Ctrl+Z / Ctrl+Shift+Z for the sequence's undo in the Animate scope); the rail tab in `railTabs.tsx`; Animate's Stage and
  Inspector switch to the sequence while the tab is up.
- **Checks:** 5 offline (`test_timeline_d83.py`: maths at one and mixed rates, invariants, exports, store, routes), 9 unit (`lane.test.ts`,
  `sequenceStore.test.ts`, the drop rule), a smoke scenario (the fake engine animates a clip, it goes on a new lane from the bin, the
  document saves at revision ≥ 1, the EDL is written) — 248 offline, 182 unit, smoke 15/15, lint 100, build clean, audits clean. The
  e2e setup now fakes the default i2v model's weights too.
- **Left for slice 2:** the draft render as a CPU job → a Catalogue clip (PyAV, dissolves blended, frame-mapped), reorder by drag,
  the C24 frame-thumbnail strip on the blocks, and the Resolve import of an exported sequence (the author's check — E13's files and
  now any `timelines/<id>/*.edl|fcpxml`).

## 2026-10-12 21:43 — P17 slice 2: the draft render as a CPU job → a Catalogue clip

- `Render {timeline_id, seeds}` joins the recipes; `plan()` marks it engine-less like Quick Remove (warm group `cpu`, no weights, no
  VRAM), the queue's CPU branch became `run_cpu` (Quick Remove or the render); `run_render` reads every lane tick from the clips'
  PNG masters (exact, never the proxies — `timelines.at()` mirrors `lane.ts`), blends the dissolve by its weight, maps a clip at
  another rate by nearest frame (D27: no conform), renders at the first clip's size and the lane's fps in chunks of one second with
  cancel checks and progress, then the clip pipeline as for i2v: `ClipStore.create` + the proxy + the Catalogue asset (kind video,
  `lineage_kind = render`, parents = every source clip's asset, `model_id = sequence`), `clip.ready`. Route
  `POST /timelines/{id}/render` → `JobsSubmitted` (422 on an empty lane or a missing clip); the Inspector's **Render draft** and the
  lane menu's entry (`anim.seq.render`).
- Checks: the offline test renders two 6-frame clips with a 2-tick dissolve on the queue without the engine — 10 frames, the dissolve's
  first tick 150 / 50 red / blue (weight 0.25), its second 50 / 150, lineage to both assets; the smoke scenario now renders the
  fake-engine clip's lane too — a 16 fps, 81-frame Wan clip gives a 122-frame clip at 24 fps, as designed. 249 offline, 182 unit,
  smoke 15/15, lint 100, build clean, audits clean; the route snapshot and the OpenAPI regenerated (80 paths).

## 2026-10-13 08:08 — P17: reorder by drag and frame thumbnails on the lane blocks

- Blocks show frame thumbnails from the C24 strip endpoint (`/clips/{id}/frames/{n}.png?size=96`, cached WebP; one per ≈ 80 px at
  evenly spaced source frames, lazy-loaded); dragging a block body past a neighbour's middle swaps the two through `move()` — live,
  each swap its own undo step; a short press still selects and scrubs. The smoke scenario checks a thumbnail loads. tsc clean, lint 100,
  smoke 15/15. CI for the two P17 commits is green under both variants (the one `open` failure on 8e13865 did not recur and its
  suite passes here under `open` — treated as a runner hiccup; the log needs a token I do not have).

## 2026-10-13 08:23 — 16 approved (D81): ST1 starts

- The author approved `16-ui-suite-stage.md` with its four defaults (36 mm sensor; the mask pass in ST3; the exact-pose method on the
  pose pass alone; image planes as grey cards in the clay pass). ST1 (Scene: suite registration, library with raycast placement,
  gizmos, outliner, cameras in mm, framing guides, `StageStore` save / reopen) starts now; its plan is 08 §8 and 16 §§3–5, 12–13.

## 2026-10-13 08:42 — ST1 Scene built: the Stage suite (D81)

- **Backend** (`orchestrator/loom2/stages.py`, `routes/stages.py`): `Stage {schema_version, id, name, size {w, h, fps}, objects
  [{id, kind: mannequin | set | prop | plane | mesh | light, name, preset, asset_id, transform {pos, rot, scale}, parent, locked, visible,
  colour_id, pose {preset, joints}, billboard}], cameras [{id, name, pos, target, roll, focal_mm, sensor_mm = 36}], active_camera,
  keyframes, range, passes, revision}` as `stages/<id>.json`; `check()` (unique ids, parents that exist and never cycle, the active
  camera present, focal 4–1200 mm); `put()` with the document-style 409; create gives one 35 mm camera at eye level and the project's
  size and fps. Routes list / create / get / put / delete; `stage.updated` events. 3 offline tests; route snapshot (105 rows) and the
  OpenAPI regenerated; `JobOrigin.suite` gains `stage`.
- **Frontend** (`frontend/src/suites/stage/`): `builders.ts` — the E10 mannequin (joint tree, COCO-18 markers kept for ST3), the three
  E10 sets + `empty`, five primitive props, `vfovFor(focal, sensor, aspect)`; `engine.ts` — a `StageEngine` on its own WebGL2 canvas:
  free camera with OrbitControls, the render camera from the active document camera (vertical fov from the 36 mm sensor at the
  project aspect), the camera view letterboxed with scissor and a DOM overlay for the framing rectangle, thirds and centre,
  TransformControls as the gizmo (translate / rotate / scale, snap 0.25 m · 15° · 0.1), raycast picking and placement (set surfaces,
  then the floor plane), `sync(doc)` diffing objects by id (rebuild on kind / preset / asset change, transforms and visibility
  otherwise, poses re-applied), camera glyphs, a selection box, on-demand rendering paused while hidden (D69); `stageStore.ts` —
  stages, the open document, selection, tool / snap / view / guides, a 64-deep undo stack, saves debounced 300 ms with the
  revision (409 → reload and a toast), object and camera edits; `StageParts.tsx` — Library (stages list + figure / set / prop cards
  that add at the viewport's centre), Outliner (rows with visibility and lock, rename on double-click, cameras), Cameras (focal
  presets 24 / 35 / 50 / 85 + a field, roll, Look through, Set from view, Frame all), the Strip (free / camera, guides, frame), the
  viewport with the floating gizmo bar, image planes by dropping a Catalogue tile (placed under the pointer, D71 verdict), the
  Inspector (transform fields, pose preset, parent, billboard; the camera; the stage); `stageCommands.ts` — 30 `stage.*` commands
  (W / G / R / S tools, Q snap, C look through, Home / F framing, Delete, Ctrl+D, L, H, Ctrl+Z / Ctrl+Shift+Z). The suite is the
  sixth tab (`Ctrl+6`), lazy and kept alive like Edit; the deep link and start-suite setting accept it.
- **Checks:** smoke scenario (new stage → add a set and a figure → the Outliner lists both, the Inspector shows the figure → saved at
  revision ≥ 1 → camera view shows the framing rectangle at 35 mm → reload keeps both) — 16/16; 252 offline, 182 unit, lint 100,
  build clean, audits clean. The screenshot of the camera view (`frontend/node_modules/.e2e/stage-camera-view.png`) shows the room,
  the figure in its selection box, the 16:9 frame and the guides.
- Not in ST1 (by plan): IK and joint posing (ST2), passes and `StageShot` (ST3), keyframes and clips (ST4), meshes (P18). Known
  rough edges to take in ST2: the gizmo bar has no Local / World toggle yet; planes drop at the pointer but stand at a fixed 1.6 m
  width until their image loads the aspect; no rig acceptance script yet (`scripts/st_acceptance.py` comes with ST3's passes).

### 2026-10-13 09:12 — ST2 Posing built (D81, 16 §3d): joints, two-bone IK, the pose library
- **Maths:** `frontend/src/suites/stage/ik.ts` — `solveTwoBone(root, target, a, b, bend)` in the chain parent's space: the bend plane
  from the target direction and a hint (elbows +Z, knees −Z, a fallback when parallel), the upper bone's frame built from the hinge
  axis, the lower bone's angle `atan2(−z, −y)` inside it; returns degrees YXZ for both joints and the reach ratio. `mirrorJoints`
  swaps `r_` / `l_` and negates Y / Z. Limb lengths from the E10 mannequin (0.29 / 0.27 arm, 0.44 / 0.43 leg). Five vitest cases
  check the solve against forward kinematics (in reach lands within 1 mm, out of reach points at the target with a straight knee
  within 3°, the mirror is an involution). `CCDIKSolver` was not needed.
- **Routes:** `GET` / `PUT /stages/poses` — the project's pose library as one file, `stages/poses.json` (`PoseLibrary`: name →
  `{preset, joints}`; 422 on a joint that is not `[x, y, z]`), placed above `/stages/{st_id}` so the literal path wins; route
  snapshot (107 rows) and OpenAPI regenerated; `test_pose_library_routes`.
- **Engine:** every mannequin carries twelve orange picker spheres on its joints and four blue cubes at the hands and feet, hidden
  until pose mode (the Poses rail tab) and the figure is selected. `pick()` raycasts the pickers before the bodies (a joint sits
  inside its limb). A joint click puts the rotate gizmo on the joint in local space with the free-rotate ball off (its 52 px pick
  sphere covered the neighbouring joints ~30 px away); a handle click puts a translate gizmo on a proxy at the hand, `objectChange`
  solves the chain live, `mouseUp` commits all twelve joints (degrees YXZ from the quaternions) through `onPosed` → `setJoints`,
  which ignores an unchanged pose (a click without a turn makes no undo entry). The pointer → NDC mapping now uses the letterboxed
  frame in the camera view (picking there was off before). A dev hook `window.__loom2Stage.screenOf(joint | chain)` lets the
  smoke test aim the mouse.
- **UI:** the Poses tab — preset grid (the ten built-ins), the project's saved poses with a delete × (`askConfirm`), Mirror / Reset /
  Save pose… (`stage.pose.mirror` M, `stage.pose.reset`, `stage.pose.save` with `askText`; also on the figure's context menu and the
  Inspector), a joint list and its x · y · z fields; the Inspector's pose select marks an edited pose. User poses load with the
  project.
- **Checks:** the smoke scenario (new stage → figure → Poses → walk → click the elbow picker (the joint list shows r_elbow) → click the
  hand handle and drag it 28 / −36 px (the document gets twelve joints, the right arm leaves the walk preset, the hand ends at least
  twice as close to the goal) → Mirror twice (the two documents are each other's left / right swap) → r_elbow x = −90 by number →
  Save pose… "crossing step" → the card appears and `GET /stages/poses` has it with the −90) — 17/17; 253 offline, 187 unit, lint 100,
  tsc clean, audits clean. Two flakes fixed on the way: the store's `selectJoint(null)` effect ended a just-started IK drag (the
  engine now keeps a live handle when the joint is cleared), and the test read the document before the debounced save (polls now).
  Screenshot `frontend/node_modules/.e2e/stage-poses.png`: the walk pose with the right forearm raised, the pickers, the gizmo on
  the elbow, the saved card.
- Next: ST3 (passes → image, `StageShot`, `scripts/st_acceptance.py`), then ST4, P18.

### 2026-10-13 10:28 — ST3 Passes → image built (D78 / D81, 16 §7): the passes, StageShot, the Shot tab, rig acceptance
- **Passes (client):** `suites/stage/passes.ts` (COCO-18 order, limbs, OpenPose colours, the E10 disparity shader, `depthRange`,
  `projectPoints` / `projectMarkers`, `drawPose` with a stroke that scales with the frame, golden-angle `maskColour`; 5 vitest
  cases) and `engine.renderPasses(cam, w, h)`: a renderer of its own at the recipe size, the shot camera rebuilt from the document
  (36 mm sensor, roll), helpers / pickers / gizmo / camera glyphs hidden, hidden objects skipped, billboards faced; clay = grey
  Lambert override (planes are grey cards, D81), depth with near / far from the camera-to-target distance, normals, masks by
  swapping a flat `MeshBasicMaterial` per object (legend colour → id), pose from the figures' markers. The five PNGs go up as blobs
  (`PUT /blobs/{sha}`) and `POST /stages/{id}/passes` makes them `stage-pass` assets (suite stage, `params {stage_id, camera_id,
  revision, pass, size}`, keypoints on the pose pass, legend on the mask pass, `origin {stage, passes}`) on the album page
  "Stage · <name>" (made once, kept as the document's `group_id`), records `passes[]` per camera and returns the document at a
  new revision; the store flushes its debounced save first and takes the returned document.
- **Recipe and engine:** `StageShot {stage_id, camera_id, passes, method clay | refcontrol, prompt_text, refs, seeds, width, height,
  te_id}`; specs carry `recipes.stage` (klein-9b clay 12 s, klein-4b clay under `open` unmeasured, klein-base-9b refcontrol with
  `stage_lora = refcontrol-v2-poses` (new roster entry, apache-2.0, 0.17 GB), `stage_seconds 74`, `stage_steps 30`, `stage_cfg 4`);
  `registry.stage_specs()`, `stage_spec` / `stage_model_id` (open → 4B for clay, none for refcontrol); `build_stage_shot` ported from
  E10 (the pass as image 1 through ReferenceLatent, the deck's images chained after it — one for refcontrol, fitted to 0.6 MP;
  the LoRA at 0.9; the E10 negative on base), `stage_prompt` (the lead sentence, "Image N shows …" per noted reference, D73, then
  the recipe's text); plan / preview (needs `passes`, E10's seconds), `prepare_stage_shot` (the pass uploaded as PNG), the
  finisher (suite stage, lineage `stage-shot` ← the pass used + the kept references), `/capabilities.stage` (methods with model,
  health, seconds, image 1, max refs; passes; default), `recipe_te_id` covers the recipe; the audit maps the key. Route snapshot
  108 rows; the object_info fixture re-captured from the 0.39.0 engine (the roster-contract test now synthesises its sub-folder
  enum — D80 left every file flat). OpenAPI regenerated.
- **UI:** the Shot rail tab (Aperture): method cards (label, model, measured seconds, hint, missing weights), image 1 locked to the
  pass the method takes (thumbnail, "current" or "from revision N — re-rendered on Generate" with *use as is*), Render passes, the
  reference deck (drop, D71 verdict `shotRefDrop`; a note per image), prompt, Draft / Full size at the project aspect, candidates
  1–4, the exact prompt preview, the stage's results strip (live through `asset.created` with `origin.suite = stage`); the Panel's
  foot on that tab is Generate ▶ (`stage.shot.generate`, Ctrl+Enter) with the estimate; `stage.shot.passes`, `stage.shot.clearRefs`;
  *Go to origin* reopens the stage at the shot's camera (`store/origin.ts`). A zustand selector that returned a fresh tuple crashed
  the panel ("Stage is not available") — selectors return stable references now.
- **Checks:** smoke scenario (stage → set + figure → Shot → Render passes → five stage-pass assets, two of them with 18 keypoints and
  a 2-entry legend, on the album page → Generate ▶ on the fake engine → a stage-shot asset with parents [clay pass], origin
  stage / shot, the prompt carrying the lead and the text, the lineage edge) — 18/18; 258 offline, 192 unit, lint 100, build clean,
  audits clean. Screenshot `frontend/node_modules/.e2e/stage-shot.png`.
- **Rig (`scripts/st_acceptance.py`, through the app: its own orchestrator on 8771 launching the engine, Edge via CDP, the
  `__loom2Stage` dev hook, E10's SDPose PCK):** the room + two figures (walk, point) + a crate at 35 mm; the passes rendered and
  uploaded in 0.7 s; four shots: clay cold 46.5 s (first run 40.6), warm 14.3–32.4 s; exact pose cold 108–115 s, warm 121 s; every
  result with its lineage and origin; PCK@0.1 on the results: exact pose 1.000 / 1.000 (36/36 both rounds, both runs), clay 1.000 /
  1.000 after the lead sentence said "the grey mannequins stand for the people described below … nothing stays grey" (before it:
  0.50 / 0.00 — Klein painted the mannequins as mannequins and added the referenced woman beside them; with the new lead it still
  paints the reference woman a second time as a third person — the author's blind check decides what the clay method is for).
  Two things found and fixed on the way: (1) the second exact-pose shot took 474 s — the identical prompt was served from ComfyUI's
  output cache, the 6.8 GB encoder stayed resident and the LoRA-patched base 9B streamed from RAM at 15.7 s/it; the finisher now
  drops the cache after a refcontrol shot (`frees_cache`), the next one reloads from the page cache in ≈ 10 s and runs at 3.3 s/it
  (121 s); (2) the acceptance orchestrator stalled when its stdout was an unread pipe — it logs to a file now, and the script refuses a
  standalone engine on 8188 (its outputs land outside the orchestrator's state; every job finished with no asset). Sheet
  `engine/spikes/out/st/sheet.jpg`, rows in `results.jsonl`. The script's time bars are set from these runs (clay ≤ 45 s warm,
  exact pose ≤ 150 s); E10's 74 s for RefControl is not reproduced at 1280×720 / 30 steps on this card — 100 s of sampling alone.
- Not in ST3: `GET /stages/{id}/thumb`; region prompting from the mask pass; the clay method's extra-person habit with a reference.
  Next: ST4 (keyframes → pass sequences → the E11 IC-LoRA clip), then P18.

### 2026-10-13 15:45 — ST4 Shots → clip built (D76 / D81, 16 §8): keyframes, the timeline, the pass sequence, LTX + the IC-LoRA
- **Keyframes (client):** `suites/stage/anim.ts` — `keyframesOf`, `bracket` (the keys around a frame, held outside, smoothstep for
  `ease`), `sampleCamera` / `sampleObject` (rotations the short way, a pose preset switching at the halfway point, joints interpolated
  under one preset), `sampleDoc`, `withKey` / `withoutKey`, `keyedFrames`, `neighbourKey`, `clipFrames` (8n + 1 inside the range); 5
  vitest cases. The store holds `frame`, `playing`, `guideKind`, `shotStart`; `keyCamera` / `keyObject` write the state shown at the
  frame; `setTransform` and `updateCamera` auto-key a keyed object / camera (an unkeyed one edits the base); `removeKeyAt`, `setRange`.
  The viewport syncs `sampleDoc(current, frame)`; playback loops the range at the project's fps. The Strip gained the timeline row
  (transport, frame field, scrubber with key diamonds, range fields, `[` `]`, Key camera K, Key object Shift+K, remove keys);
  `stage.anim.*` commands, Space / arrows / Shift+arrows as accelerators.
- **Sequence → guide:** `engine.renderSequence(frames, w, h, kind, restoreDoc)` (the pass rendering factored into `shotCamera`,
  `hideHelpers`, `shotWith`, `depthFor`, `keypoints`; the scene synced per frame, left at the viewport's frame), uploaded as blobs;
  `POST /stages/{id}/guide {camera_id, revision, kind, fps, size, range, frames[sha], keypoints}` → `stages.encode_guide` (PyAV h264
  crf 10, yuv420p, the E11 encoding) under `stages/<id>/guides/`, ingested in place as a video asset (suite stage, `stage-pass`,
  `params {…, pass: "<kind>-sequence", frames, fps, range, keypoints}`, `origin {stage, guide}`) on the album page; `StageStore.set_guide`
  records `guides[kind]` under the camera's passes entry (made if the stills were never rendered). Route snapshot 109 rows.
- **Clip:** `I2V.guide {asset_id, kind depth | pose, strength}`; the LTX spec carries `guide_lora = ltx23-ic-lora-union` (new roster entry,
  0.65 GB, the model's licence) and `guide_seconds 147` (E11); `build_i2v` adds `LoraLoaderModelOnly` + `GetICLoRAParameters` +
  `LoadVideo` + `GetVideoComponents` + `LTXVAddGuide` at frame 0 last in the guide chain, the guider on the LoRA'd model (Wan refuses a
  guide); `prepare_i2v` uploads the mp4 as it is (LoadVideo reads it by name after the object_info refresh); `recipe_weights` adds the
  LoRA only with a guide; the estimate scales by E11's ratio; `placeholder_inputs` takes LoadVideo's first option (a V3 combo:
  `["COMBO", {options}]` — the fake engine learned to grow it on an mp4 upload); the clip finisher adds the guide to the parents, sets
  `lineage_kind stage-shot` and `suite stage` when the job's origin is the stage. `/capabilities.stage.clip` names the model, health,
  seconds, kinds, fps, frame step and size. Fixture classes +3 (76). The Shot tab's Clip section: guide kind, Render sequence with
  progress, the start shot picked by clicking a result, Animate ▶, the stage's clips. The Go-to-origin case covers the clip.
- **Checks:** smoke scenario (stage → figure → a shot on the fake engine → the start picked → Key camera at 0 → frame 8 → the camera's z
  edited on the Inspector (a keyed camera takes it as a key) → range 0–8 → Render sequence → the document's `guides.depth` has 9 frames,
  the asset is a 9-frame video with keypoints → Animate ▶ → the fake engine decodes 9 frames → a stage-shot clip whose parents are the
  shot and the guide, origin stage / clip) — 19/19; 262 offline (+4 clip tests), 197 unit, lint 100, tsc clean, audits clean.
  Screenshot `frontend/node_modules/.e2e/stage-clip.png`: the timeline with two key diamonds, the Clip section, "Clip ready".
- **Rig (`scripts/st_acceptance.py --methods clay --rounds 1`, the clip step on by default):** the camera keyed at 0 and 48 (a dolly
  from z 4.2 to 2.4 through the hook), the depth sequence rendered, uploaded and encoded in 2.4 s (49 frames at 1024×576, 24 fps),
  the clip job done in 131.5 s cold (LTX-2.3 distilled draft, 8 steps, the IC-LoRA), lineage stage-shot ← the clay shot + the guide,
  origin stage / clip; SDPose on frames 0, 8, … 48 vs the guide's keypoints: PCK@0.1 0.996 (240/241). The clip sheet
  (`engine/spikes/out/st/clip_sheet.jpg`) shows the dolly in on the two figures with the walk and the point held. 22/22 checks.
- Not in ST4: the Story L3 link (14); object keys beyond transform + pose; a pose-guide measurement (E11: the weaker second, offered).
  Next: P18 (Pixal3D props, D79).

### 2026-10-13 16:52 — P18 Image → mesh props built (D79 / D84): Pixal3D as a background job, mesh assets, props in the Stage
- **Graph:** ComfyUI's template `3d_pixal3d_trellis2_image_to_model.json` (the one E14 ran) frozen by `scripts/make_mesh_graph.py` into
  `orchestrator/loom2/engine/pixal3d_graph.json` — 41 nodes: the method switch set to Pixal3D and every constant `ComfySwitchNode`
  resolved, the TRELLIS.2-only nodes and every preview dropped (consumers rewired to what the preview showed), loader names blanked
  and the roles recorded by node id (model, shape / texture VAE, dino, moge, matte, image, four samplers, decimate, upsample, save,
  final mesh). `graphs.build_mesh` fills the names from the roster, one seed into every sampler, the face count (50k) and the
  upsample resolution (1024; 1536 is the template's own), and adds a `RenderMesh` view saved beside the GLB for the thumbnail. The
  contract checker learned type unions (`FILE_3D_GLB,FILE_3D_GLTF,…`) and V3 dynamic combos (`sign_mode.qef` under the chosen
  option); the fixture gained 28 classes (104). D65 kept: a roster id as a role name (`birefnet`) tripped `model_literals_check` —
  the role is `matte`.
- **Recipe and roster:** `ImageToMesh {asset_id, model_id = the registry's mesh default, resolution 1024 | 1536, faces 2k–700k}`;
  `specs/pixal3d.toml` (`recipes.mesh`, extras for both VAEs, DINOv3, MoGe and BiRefNet, `base_seconds 243`, `cold_seconds 361`);
  roster entries pixal3d-int8 (5.6 GB), trellis2-shape-vae, trellis2-texture-vae, moge2-vitl (MIT) and dinov3-l (Meta's licence) — the
  Pixal3D entry is `full`-only while DINOv3 is (D17 / D26), so `/capabilities.mesh` under `open` says why; Hunyuan3D names on
  `IGNORED_UNLISTED` with the reason, `/models/unlisted` returns them as `ignored`. `prepare_mesh` uploads the photo; the engine's
  history for `Save3DAdvanced` carries the GLB under `"3d"` and a bare path list under `"result"` — the output collector takes dict
  records only (the first rig job crashed on the string). `MeshFinisher`: the GLB becomes a `mesh` asset (new `AssetKind`, served as
  `model/gltf-binary`) with lineage `image-to-mesh` ← the photo, the six weights' licences in `params.licences`, the view as its
  thumbnail; the fake engine writes a real minimal GLB for a mesh graph (the helper must sit above its `__main__` block).
- **UI:** "Make a 3D prop…" on the tile menu's *Start from this image* and as an Inspector card, `askConfirm` with the model, the
  size, the warm and cold minutes and the missing-weights note before the job is queued; mesh tiles wear a badge and drag as
  `media: mesh` (`mediaOf`), image-only verbs take `kind === 'image'`, the loupe shows a mesh by its thumbnail; the Stage library's
  *Meshes* cards and a mesh drop on the viewport place a `mesh` object — `GLTFLoader` on the asset file, a wireframe stub until it
  arrives, centred on its footprint and stood on the floor at its own size; `__loom2Stage.meshes()` says which loaded.
- **Checks:** smoke scenario (tile → 3D prop → the dialog names Pixal3D and the minutes → the fake GLB → a mesh asset with lineage,
  licences and a thumbnail, the badge on the tile → Stage → the Meshes card → "Mesh 1" placed and its GLB loaded) — 20/20 (the ST4 and
  P18 scenarios are variant-aware: under `open` they assert the absence and the reason); 268 offline (+6: resolution, the frozen
  graph against the contract, plan / preview / capabilities, the finisher's asset, the job end to end on the fake engine, the output
  collector on the rig's history shape), 197 unit, lint 100, tsc clean, audits clean; the e2e teardown now keeps the fake-engine and
  orchestrator logs under `node_modules/.e2e/` for a post-mortem.
- **Rig (`scripts/p18_acceptance.py`, its own orchestrator + engine, Edge via CDP):** the five E14 inputs → five jobs: 344 s cold, then
  538 / 314 / 226 / 266 s warm — the GPU stages take seconds; the CPU stages (remesh at 768 from 6.2 M faces, unwrap, the 4096²
  bakes) vary with the prop, so the time is recorded with a 600 s runaway ceiling, not a bar (D79: the cost is shown). Every job
  produced a mesh asset with lineage, a thumbnail and the six licences; 46.5–49.9k triangles, 3 textures, 20–27 MB each. The Stage:
  the Library listed the five, all five GLBs loaded in the viewport, took transforms; screenshot `engine/spikes/out/p18/stage.png` —
  the boat, the wheel, the chest, the lantern and the compass in the room. One browser log line while five 22 MB GLBs loaded at
  once (`net::ERR_NO_BUFFER_SPACE` on a thumbnail image); 34 checks ok. The `RenderMesh` thumbnail frames the compass well but the
  lantern from inside (its own camera; see the next line).
- **Thumbnails:** `RenderMesh` with or without the Load3D viewer's `camera_info` gives the same view (tested on the lantern GLB through a
  Load3DAdvanced → Get3DComponents → RenderMesh graph: its camera sits inside the mesh for some props) — so the plan's other option is
  built: when the Stage loads a mesh asset, `engine.thumbnailOf` renders a lit three-quarter view with the camera fitted to the
  bounding sphere (the E14 renderer's framing) and `PUT /assets/{id}/thumbnail` (a PNG ≤ 8 MB, `params.thumb_source = client`) makes
  it the asset's thumbnails, once per asset; the engine's view remains the first thumbnail until a prop is placed. Route snapshot 110.
- Not in P18: a texture-size knob (the template bakes 4096², 20–27 MB per prop); a client thumbnail without placing the prop; TRELLIS.2
  (deleted by D79). Every ArtCraft proposal P1–P19 is now built; next the Story workspace (14) and the author's own checks (the
  Resolve import, the clay blind check, the licence review of DINOv3).

## 2026-10-13 17:45 — Story workspace: the refining session (14 §4) → `17-ui-suite-story.md`, D85 proposed
- Read against the shipped model: `kb-storyboard01.md` §2–§9 and R1–R170, `kb-loom-p1` §1–§4 / §7.1 / §13, `kb-loom-p2` §1–§9,
  `kb-loom-p3` §1–§8 / §16, `kb-loom-p4` §1–§10, `kb-loom-p5` §1–§9 / §14, `kb-loom-p6` §1–§3 / §6, `kb-loom-ui` §4–§7; loom2's 02 §2 /
  §7, 03 §5, 06 §5, 07 §2, 11 §5b, 14, and the code (`groups.py`, `catalogue.py`, `recipes.py` + `mentions.py`, `clips.py`,
  `timelines.py`, `stages.py`, `workspace.py`, `railTabs.tsx`, `suiteRegistry.tsx`, the video specs).
- Answers (17 §0): (1) deltas in 17 §9 — a `story/` directory of records beside groups / clips / stages / timelines; a profile version
  *is* a group (copy by `duplicate`, `final` = `locked` → 423), a shot version points at a stage camera and / or a clip, the flow is
  one node per file + a rebuildable index, the episode is a P17 timeline with shot stamps, `asset@version` = the D73 mention stamp
  plus `profile_id` / `version`; (2) Cast → Expand → Curate are Catalogue / Generate verbs reached from the Cast tab (Expand = one
  queued T2I per coverage cell with the hero as reference, cost confirmed first); (3) tiers = the Animate presets as measured (LTX
  draft 141 s, guided 147 s, Wan draft 236 s, quality 210 / 900 s, RIFE at export) — loom's drive tier is not built; (4) Muse deferred
  behind spike E15 to a wave after the alpha; v1 ships without any AI assistance.
- Plan: SY0 shell + World + the Style picker (3 d) · SY1 Cast (6 d) · SY2 Shots (5 d) · SY3 Flow on `@xyflow/react` (7 d) · SY4
  Episode (the Sequence tab moved, `.srt`, markers, checklist; 4 d) · SY5 alpha acceptance `scripts/sy_acceptance.py` (3 d) ≈ 28 d.
- Recorded: D85 (proposed, awaiting the author's answer on 17 §14), 14 §4 item 5 and §5, 00-README row 17, 12 §8d. Next: the
  author's answer, then SY0.
- 17:52 — the author approved 17 §14 as proposed (D85 accepted; the Sequence tab moves to Episode). SY0 starts.

## 2026-10-13 20:40 — SY0 · the Story suite's shell and World tab, the Style picker in Generate (17 §10, D85)
- **Backend:** `orchestrator/loom2/story.py` — `World` (logline, synopsis, `styles[]`, `default_style`, the spine's `beats[]`, the Flow's
  `variables[]` as bool / enum; `schema_version`, `revision`), `check_world` invariants, `StoryStore` (`story/world.json` through fsio;
  a read writes nothing; `put_world` with the revision guard → `StaleWorld`), `resolve_style` (the style's fragment stamped on the recipe
  as `style_text` at submit and preview; a stamped recipe is not resolved again). `routes/story.py`: `GET` / `PUT /story/world` (409 /
  422), the `story.changed` event frame. `T2I.style_id` / `style_text`; `serialize_prompt` appends the fragment after the prompt and
  before the reference sentences (text), into the tree's own `style` slot after what is there (prose and dev JSON); `effective_params`
  carries both into the preview and the manifest (`params.style_id` / `style_text` beside the recipe). `queue.resolve_mentions` resolves
  the style with the mentions, so a preview shows exactly what a submit runs (T8). `Workspace.story_dir`; `JobOrigin.suite` gains
  `story`; the audit allows `T2I.style_id` as provenance. Route snapshot 112; the OpenAPI document 195 schemas (`StoryStyle`,
  `StoryBeat`, `StoryVariable`, `World`, `StoryChanged` — a `Beat` already names the LTX beats).
- **Frontend:** the suite `story` (lazy, no keep-alive) with the rail tab World, `Ctrl+7`, the top-bar tab; `suites/story/storyStore.ts`
  (debounced saves with the revision, 409 → reload and a toast; `styleFor` for Generate), `StoryParts.tsx` (Panel: the sections with
  counts and the adders; Stage: the editor — logline, synopsis, style rows with the ★ default, beat rows with ▲ ▼, variable rows with
  type / values / default; Inspector: the format as the finalize gate, counts, the default style, the selected item's fields),
  `storyCommands.ts` (`story.world.*` — add style / beat / variable, make default, beat earlier / later, remove on Delete; every one a
  button or a menu entry), `story.css`, the `__loom2Story` dev hook; `store/origin.ts` case `story`; `session.ts` applies
  `story.changed`. Generate: `suites/generate/StylePicker.tsx` on the Prompt tab (default · the world's ★ style, none, or one by name;
  the hint says what is appended), `Panel.style_id` (absent = the world's default, null = none), `recipeFromPanel` / `panelFromRecipe`.
- **Checks:** `tests/test_story_d85.py` (+7: invariants, the store's guard, the routes, `resolve_style`, the serialisation per family,
  the preview, the asset's manifest on the fake engine — the text that ran, not today's fragment); the graph parity fixture rewritten
  for the two summary keys (`--parity-update`, nothing else changed); the smoke scenario "a world": World adds a style and a logline,
  the API has them at revision ≥ 1 with the first style as the default, Generate's picker names the fragment and the job's asset carries
  `style_id`, `style_text` and the appended prompt — 21/21 under `full` and `open` (one unreproduced failure of the new scenario in a
  full-variant run before the open run; alone and in the next full run it passed; to watch on CI). 276 offline, 197 unit, lint 100
  (the picker in its own file keeps the Fast Refresh warning count), tsc clean, settings audit / model literals / contract clean.
- Lesson for the scenarios: a click on the rail tab that is already active folds the panel (`Rail.tsx`); switch tabs, never re-click.
- Not in SY0: the World's styles as reference groups (`group_id` is stored, nothing reads it yet — SY1's mentions), the beat → Flow
  node verb (SY3). Next: SY1 Cast.

## 2026-10-13 21:21 — SY1 · Cast: profiles with versions, Expand by coverage cell, curation, locks, profile mentions (17 §3b / §10, D85)
- **Backend:** `story.py` — `Profile` (`name`, `cls` character | place | prop, `current`, `versions[]`, `revision`) and `ProfileVersion` (`state`
  open | final, `group_id` = the reference set as an album group, `candidates_group_id`, `hero_asset_id`, `stub`, the `trigger` / `lora`
  slots for the LoRA wave, `derived_from`); `StoryStore.create_profile` (a group "Name · v1", the hero moved onto it as its cover),
  `patch_profile` (revision guard; a locked version's stub and hero are read-only), `new_version` (the group store's deep `duplicate` —
  an asset lives on one page (D34), so the copy's images are duplicates with `duplicate_of`; the copy becomes current, open),
  `lock_version` (→ `GroupStore.set_locked`), `delete_profile` (the record goes, the groups stay, unlocked). The coverage vocabulary
  (loom `kb-loom-p1` §7.1: 4 shot sizes × 6 angles × 5 expressions) and five presets as rows of (shot, angles, expressions, seeds):
  comprehensive 89 · full 36 · portrait 29 · fullbody 42 · npc 18 cells; `plan_expand` → one T2I per cell (× seeds): Klein prose, the
  stub then the cell's sentence ("Mara, a wiry courier. a waist-up medium shot, a three-quarter view from the left, neutral
  expression."), the hero as reference 1, the project aspect at the tier's height, the origin `{suite: story, surface: expand,
  ref: profile, payload: {version, cell, group_id, preset}}`; `expand_spec` = D78's clay model (Klein 9B under full, 4B under open — it
  takes the hero as a reference and renders the same person; 12 s warm). `groups.py`: `GroupRecord.locked`, `GroupLocked` → 423 on
  update / layout / move (source pages and the target) / group / ungroup / delete. `mentions.py`: `Mention.profile_id` / `version` —
  a profile mention is pointed at its version's group (the current one unless pinned) before the turns, the stub rides on the note
  ("Image 1 shows Mara, a wiry courier in a grey coat"), the stamp keeps both (loom R98's `asset@version`). `queue.submit(batch_id=…)`
  joins a batch; the `AssetFinisher` places results on the origin's `group_id`, records `params.coverage_cell` and suite `story`.
  `routes/story.py`: `GET / POST /story/profiles`, `GET / PATCH / DELETE /story/profiles/{pid}`, `POST …/versions` (copy),
  `…/versions/{vid}/lock`, `…/curate {asset_ids, verdict}` (keep: state keep + moved onto the reference page; reject: marked, left),
  `…/expand {version?, preset, seeds_per_cell, tier, style_id}` → one batch; `/capabilities.story` (model, health, seconds, the presets'
  cell counts, the vocabulary). Route snapshot 121; 205 schemas; `MentionOut` gains the two fields.
- **Frontend:** the Cast rail tab — Panel: profiles by class chips with search, *New profile / place / prop…*; Strip: the version
  selector, *New version*, *Lock* / the lock badge, the bootstrap strip Cast › Expand › Curate › Train (greyed: the LoRA wave) › Lock
  with ✓ from the evidence; Stage: the version page (hero, name · class · state, the prompt stub saved after a pause with the revision,
  counts, the coverage grid from `coverage.ts` — thin cells tinted, advisory — and the candidates newest first with ✓ / ✕ on hover,
  click / Ctrl-click to pick, a right-click menu); Inspector: the profile (name, class, current, `@name`) and the version (hero,
  pages, trigger / LoRA slots, from, created) with the verbs; the panel foot **Expand ▶** with the cells and minutes; `askExpand`
  says the cost (D79's pattern) before one job per cell is queued. Commands `story.cast.*` (new ×3, expand Ctrl+Enter, keep K, reject X,
  setHero, lock, newVersion, openGroup, openCandidates, delete). The Catalogue's *Make a character / place / prop…* (tile menu under
  *Start from this image*, Inspector quick cards): `askText` for the name → the profile with the image as hero → Story · Cast opens on it.
  Generate's @ picker lists the cast first (`name · class · version`), the chip wears `.profile`, `recipeFromPanel` sends `profile_id`;
  an Expand job's *Go to origin* opens the profile at its version. `story.changed {kind: profile}` reloads the profiles,
  `group.changed` the selected version's pages.
- **Checks:** `tests/test_story_cast_d85.py` (+7: create / patch / copy / lock / delete, lock needs a hero, presets and cells,
  `plan_expand`, profile mentions incl. pinned versions and the stub, the routes end to end with 423 / 409 / 422 and the preview, Expand on
  the fake engine — one batch, the candidates placed with their cells, suite story, the hero as parent); `coverage.test.ts` (+3);
  `test_mentions_d73` compares without the two new fields; the smoke scenario "a cast": the quick card → the dialog → Story · Cast with
  the hero as cover, Expand ▶ says "Queue 36 jobs … min" (cancelled; the npc preset queued through the hook: 18 jobs in one batch, every
  candidate on the page with its cell), keep with the card's ✓ (the grid gains a cell, the reference page the asset), reject through the
  context menu, Lock through the strip (the badge, v1 final, `POST /groups/move` → 423, the foot says locked), the @ picker's entry
  `Mara · character · v1` → the chip and the text, the preview resolves to v1 with the hero first — 22/22 under `full` and `open` (the
  open run's hero is picked by the API: the newest image, a clip may sit first). 283 offline, 200 unit, lint 100, tsc and build clean,
  audits clean. The flaky "a suite whose code fails to load" scenario (the open runner's CI failure on cb1253b) gets a 150 s budget
  and a 90 s wait.
- **Rig (`scripts/sy_acceptance.py`, its own orchestrator + engine, Edge via CDP on the dev server, 21:12–21:20):** E12's source 07 imported as
  the hero → *Mara v1* (the hero on its page as cover) → Expand Full coverage: 36 Klein 9B jobs in one batch, 36/36 done with an asset in
  414 s — the first (cold) 33.8 s, then warm 7.5 / 10.9 / 11.0 s (min / median / max; bar ≤ 45 s) — every candidate on "Mara · v1 ·
  candidates" with its cell, suite story, the hero as its parent and the expand origin; the Cast page listed all 36; curate: 30 kept into
  the reference set (every shot-size row first, then by cell order; bar ≥ 25), all four rows covered, the kept marked keep, 3 rejected
  staying on the candidates page marked reject, the grid showing the cells; Lock → v1 final, `POST /groups/move` off the page 423, the
  locked stub 422, the strip's badge; `@Mara` → v1's reference set with the hero first (4 references on Klein), the note "Image 1 shows
  Mara, a wiry courier in a long grey coat with a red scarf"; a Generate job with the mention done in 39 s, its manifest stamping profile,
  version and the images, the hero a parent — the result is a two-panel image (a wide and a close view of Mara at the gate: Klein with
  four references of one person tends to a diptych; one reference or a composition sentence is the author's call, D73). 27 checks ok; sheets `engine/spikes/out/sy/candidates.jpg` (the same woman across the cells,
  the angle cells not all turned — Klein's rotations are 6–7/10, E12) and `kept.jpg`, `mention_result.jpg`, `results.jsonl`. A first run
  died on printing ≤ to a cp1252 console after the expand (36/36 in 419 s); the script now forces UTF-8 on its streams.
- Not measured: the curation quality (the script keeps by cell order; the author's eye decides) and the comprehensive preset (89 cells,
  ≈ 17 min warm by the same rate).
- Not in SY1: a hero drop slot (the Catalogue verb and *Make it the hero* on a candidate cover it); re-rolling one thin cell from the
  grid (P14's *New angle* on a tile lands in Unprocessed, not the candidates page); the style's reference group. Next: SY2 Shots.

## 2026-10-13 22:01 — SY2 · Shots: shot records with versions and takes, the finalize gate, the stage link (17 §3c / §10, D85)
- **Backend:** `story.py` — `Shot` (`name`, `owner_node` for the Flow's sole ownership (loom R146; SY3 binds), `current`, `versions[]`,
  `revision`), `ShotVersion` (`state` open | final, the source `stage_id` + `camera_id` + `stage_revision`, `frame_asset_id`, the one
  `clip_id`, `takes[]` of images and clips, `derived_from`, `finalized_at`), `ShotTake`; `create_shot` (a stage camera and / or a clip or a
  frame — each given one is also the first take), `patch_shot` (revision guard; a final version's frame and clip are fixed, `owner_node`
  always patchable), `new_shot_version` (the pointers copied, no takes, open and current — a retake, loom R62), `add_take` (dedupes;
  `use` or an empty slot fills the frame / clip and stamps the stage's revision), `finalize_shot` + `finalize_reason` (loom R166: one
  clip per version; the gate = the project format's size **within the video models' 32 px grid** — LTX Full is 1920×1088, Wan 1920×1072,
  the export crops the last rows (11 §3c); the refusal says "Draft 1024×576 — the format is 1920×1080; render Full in Animate"),
  `delete_shot`, `record_stage_result` (a camera's frame or clip becomes a take of every shot whose current open version points at
  that camera, the empty slot filled — ST4's "Story L3 link", 08 §8). The asset finisher calls it for a `StageShot` result, the clip
  finisher for a guided clip from a stage (`_stage_result`, never the job's failure; `story.changed {kind: shot}` per shot).
  `routes/story.py`: `GET / POST /story/shots` (the source checked: a stage names its camera, the clip and the frame exist),
  `GET / PATCH / DELETE /story/shots/{sid}`, `POST …/versions` (copy), `…/versions/{vid}/take {kind, id, use}`, `…/finalize` (422 with the
  reason). Route snapshot 129; 211 schemas.
- **Frontend:** the Shots rail tab — Panel: the shots grouped by owner (*Unbound* first; SY3 names the nodes), each with its frame or
  clip thumbnail, source and state, *New shot…*; Strip: the version selector, *New version*, *Finalize* or the *final* badge, the
  *stale* badge (the stage's revision past the version's, from `GET /stages`), the stage's name, *Open in Stage* / *Open in Animate*;
  Stage (the board): the version cards (frame, state, stale, the clip's frames and size), the current version's player (`<video>` on the
  clip's proxy, else the frame), the takes newest first with *✓ use* on the ones not in use; Inspector: the shot (name, owner, current,
  versions) and the version (source with the stage's name and camera, frame, clip with frames · fps · size, takes, from, created,
  finalized) with the verbs; the panel foot *New shot…* with the version's gate reason or "ready to finalize". Commands `story.shot.*`
  (new, newVersion, finalize — `when` mirrors the gate, openStage, openAnimate, release, delete). The ways in: *New shot from this
  camera…* on Stage's Cameras tab (and the Shot tab's head) → `askText` with "Stage · Camera" as the name → Story · Shots opens on it;
  *Make a shot from this clip…* on Animate's transport (and a clip tile's menu, `cat.start.shot`). `story.changed {kind: shot}` reloads
  the shots and their clips.
- **Checks:** `tests/test_story_shots_d85.py` (+4: invariants and the gate's reasons incl. the grid, the store end to end — takes, use,
  dedupe, patch and the revision guard, finalize twice, a final version refuses takes, copy, the stage link to the shots pointing at a
  camera, delete — the routes with 422s and the 409, the finisher hook: a StageShot result on the fake engine lands as the frame of the
  shot made from its camera with the stage's revision); the smoke scenario "a shot": Stage → *New shot from this camera…* on the
  Cameras tab → Story · Shots on the shot (the foot says "no clip yet"), back in Stage the passes render and Generate ▶ runs — the
  frame arrives on the shot's v1 as its frame and first take, the board shows it; a draft clip (the fake engine, 1024×576, nine frames)
  opened in Animate → *Make a shot from this clip…* on the transport → the second shot with the clip, the player shows the proxy, the
  foot and the API refuse the finalize with "Draft 1024×576 — the format is 1920×1080", the strip's Finalize is disabled; a clip at the
  format used as the clip through the hook → "ready to finalize" → Finalize through the strip → final (a further take refused, 422) →
  *New version* → v2 open with the pointers, ready — 23/23 under `full` and `open`. 287 offline, 200 unit, lint 100 (a stray escape in
  the Cast scenario's regex fixed), tsc and build clean, audits clean.
- **Rig (`scripts/sy_acceptance.py --part sy2`, its own orchestrator + engine, Edge via CDP on the dev server, 21:46–21:59):** a stage (the
  room, one figure, a 35 mm camera) → `createShot` from the camera (v1 at the stage's revision) → the Stage suite opened it, rendered the
  passes and queued the clay shot with the heroine as the reference: done in 43 s (Klein 9B cold), the result **landed on the shot's v1 as
  its frame and first take** through the finisher's link; a draft clip (the default i2v under `full` is Wan 2.2: 1024×576, 25 frames,
  108 s) used as the clip → finalize refused with "Draft 1024×576 — the format is 1920×1080; render Full in Animate" (422); a Full clip
  (asked 1920×1080 → Wan's grid 1920×1072, 25 frames, **644 s** — Wan at FHD is slow, 11 §3c's LTX two-stage Full is the intended
  path) used as the clip → **finalize accepted** within the grid, v1 final with it. 17 of 19 checks: the two UI checks (the strip's
  *final* badge, the *stale* badge after a focal change) failed because the script had left the suite on the World tab — the state was
  right (v1 final; the stage's revision past the version's); the hook gained `openShots` and the script uses it, and the smoke scenario
  now covers both badges on the fake engine (the strip shows *final*, then *stale* after a camera change through the API).
  `engine/spikes/out/sy/results.jsonl` holds the clip ids and walls.
- Not in SY2: *Use as the shot's frame / clip* on Stage's and Animate's own results strips (the takes strip on the board covers it, and
  a stage camera's results arrive by themselves); the owner node (SY3). Next: SY3 Flow.

## 2026-10-13 22:35 — SY3 · Flow: the narrative graph on React Flow, one file per node, binding, validation, play (17 §3d / §10, D85)
- **Backend:** `story.py` — `FlowNode` (one file per node under `story/flow/nodes/`, loom R139: `type` start | hub | dialogue | choice |
  condition | action | shot | jump | comment, `title`, Dialogue `lines[{speaker (a profile), text}]`, Choice `options[{id, label, require,
  set}]` each an out-port `opt:<id>`, Condition `cond {var, op eq | ne, value}` with *then* / *else*, Action `set[]`, Jump `target`, Comment
  `text`, the bound `shot_id` / `shot_version`, `revision`), `FlowGraph` (the thin index `story/flow/graph.json`: placements, edges
  `{from, port, to}`, the start; **rebuilt from the node files** whenever it is missing or disagrees — gone nodes' placements and edges
  dropped, missing placements laid out, the start the first Start node), `node_ports`, `validate_flow` (no / several Starts, a Choice
  without options, a dangling edge or Jump, an edge from a port the node lacks, an unreachable node, a visual node without a shot or with
  a non-final version, an undeclared variable — advisory rows with the node), the store's `create_node` / `patch_node` (the revision
  guard; an option removed takes its edge with it) / `delete_node` (edges go, the shot is released) / `put_graph` (positions, edges —
  one per out-port, ports checked — and the start, with the revision guard) / `bind_shot` (loom R146: an unbound shot or a version of
  its own; another node's → 422, "duplicate it into a new shot") / `unbind_shot`. `routes/story.py`: `GET /story/flow`, `POST / PATCH /
  DELETE /story/flow/nodes[/{nid}]`, `PUT /story/flow/graph`, `…/{nid}/bind`, `…/unbind`, `…/shot` (spawn an empty shot owned by the
  node), `POST /story/flow/validate`. Route snapshot 138; 225 schemas.
- **Frontend:** `@xyflow/react` 12.12.0 (MIT, released 2026-09-24; `scripts/csp_check.py` gained the `story-flow` page — clean).
  `suites/story/flow/FlowCanvas.tsx`: the node cards (type, title, the speaker and first line, the bound shot's thumbnail and state, a
  tinted border for a validation problem) with one target handle and the out-ports as source handles (a Choice one per option, a
  Condition then / else), edges labelled by option or branch, pan / zoom / minimap / fit, a drag saves on drop, a handle-to-handle drag
  connects (one edge per port), right-click the pane → *Add a node here* (nine types), right-click a node → its verbs; new nodes land at
  the view's centre stepped 40 px. `flow/play.ts` (pure, 3 unit tests): the walker — Start → the first waiting node; Dialogue and Shot wait
  for *Next*, a Choice for an option (its requirement read, its sets applied), a Condition branches, an Action sets, a Hub passes, a Jump
  goes to its target, no edge or a Comment = the end; a loop of pass-through nodes ends at 1 000 steps; **no model is ever invoked**
  (loom R143). The Flow rail tab: Panel — the outline by type with search and the variables (with their play values); Strip — the
  palette (nine ✚ buttons), the problem count, Validate, Play / Stop, Fit; Stage — the canvas, or the play view (the node's clip proxy
  or frame, the lines with the speakers' names, *Next* / the options / *Restart* / *Stop*, the trail and the variables); Inspector — the
  node's type and title, the lines editor (speaker from the cast, text), the options editor (label, *always* or a variable's value),
  the condition and the sets editors, the shot binding (an unbound shot from a select, the version, *New shot for this node…*, *Open the
  shot*, *Release the shot*), the node's problems; the panel foot *Play ▶* / *Stop* with where the play is. Commands `story.flow.*`
  (add × 9, delete, duplicate, newShot, unbind, openShot, validate, play P, stop, fit F) and `story.world.beatToNode` (*Make a Flow node
  from this beat* on a beat: a Shot node titled by the beat, its line as the text). Node saves are serialised per node and coalesce
  keystrokes (the latest local state, the latest revision); graph saves likewise, and the socket's `story.changed` never reloads while
  a save is pending (the earlier races lost edges and raised 409 toasts).
- **Checks:** `tests/test_story_flow_d85.py` (+3: ports and validation codes, the store end to end — index rebuilds, edge checks, the
  revision guards, bind / unbind / delete releasing, an option's edge pruned — the routes with 422 / 409 / 404); `play.test.ts` (+3);
  the smoke scenario "a flow": the Strip adds Start, Dialogue and Choice, the mouse spreads them and Fit frames them, the Inspector
  edits the title, a line and two options, three handle drags connect Start → Hello → Pick and Go → Hello (the API shows the three
  edges and the start), *New shot for this node…* spawns an owned shot, Validate lists the one advisory problem (the shot is not
  final), Play shows the line, offers Go and Stay, loops on Go and ends on Stay — the job count unchanged — and a reload brings the
  nodes, edges and the bound shot back — 24/24 under `full` and `open`. 290 offline, 203 unit, lint 100, tsc and build clean, CSP
  clean on six pages, audits clean. Two zustand lessons again: a selector returning `?? []` (a fresh array) looped React (error #185)
  and hid the Inspector behind the quiet boundary; the fix is deriving in render.
- No rig run: SY3 queues no job (the acceptance is the smoke and the unit tests; 17 §12 item 4 is covered by the scenario).
- Not in SY3: node colours in the Inspector (the field exists), a Choice option's `set` editor (the model has it; the Action node sets),
  centring the canvas on an outline click. Next: SY4 Episode (the Sequence tab moves to Story).

## 2026-10-13 22:49 — SY4 · Episode: the lane moves into Story, the Shots bin, the checklist, subtitles and chapter markers (17 §3e / §10, D85)
- **The move (D83's "until Story's Episode tab exists"):** `lane.ts`, `sequenceStore.ts`, `SequencePanel.tsx`, `SequenceStage.tsx`,
  `sequenceCommands.ts` and their tests went from `suites/animate/` to `suites/story/episode/` by `git mv` (imports re-pointed, the
  commands renamed `story.episode.*` in the Story scope — the lane's Delete key dropped, `story.world.remove` has it; Ctrl+Z / Ctrl+Shift+Z
  are the Story suite's undo now); the Animate rail lost its Sequence tab, the Story rail gained Episode; `?suite=animate&tab=sequence`
  lands on Story · Episode (`suiteRegistry` and the session's deep link, one release). The Episode tab: Panel = the sequences, **the Shots
  bin** (every shot whose current version has a clip, final first, named with its owner node, `+` adds it stamped) and the Clips bin; Stage
  = the lane as it was; Inspector = the sequence, **the checklist** (a plain clip, a version not final, a stale one — advisory, loom R153
  per 02 §7), the exports EDL · FCPXML + markers · SRT · Render draft, the clip's shot; the panel foot **Export ▶** (FCPXML) with "n of m
  clips not final shots".
- **Backend:** `TimelineClip.shot_id / shot_version / node_id` (optional — Animate-era documents load unchanged; the lane carries them as
  `LaneClip.shot` through every edit); `timelines.py`: `to_srt` (loom R152: each lane clip's Dialogue lines laid evenly over its ticks,
  SubRip times from the lane), `to_markers` (the sidecar `markers.txt`, `HH:MM:SS:FF<TAB>name`), `to_fcpxml` with a `<marker>` at the head
  of every named clip (loom R158 — Resolve reads them; unnamed clips stay self-closing), `TimelineStore.export(…, name_of, lines_of)`
  writing `markers.txt` beside the FCPXML; the export route takes `srt` and reads the Story records — a clip's chapter name is its
  node's title, else its shot's name; its lines are its node's (or the node bound to its shot). The route snapshot is unchanged.
- **Frontend:** `laneChecklist()` (what on the lane is not a final shot version, with the reason) and `exportChecked(format)` — the
  export asks with the list when something is not final and goes on when the author says so (17 §14.5); `addShot(clip, {id, version,
  node})`; `csp_check.py` pages `story-flow` and `story-episode` (Mediabunny in the Story chunk) — clean.
- **Checks:** `tests/test_story_episode_d85.py` (+2: SubRip times and the even layout over a dissolve, the markers sidecar, the FCPXML
  marker per named clip, the route end to end — the stamps round-trip and are optional, the SRT with the bound node's two lines, the
  FCPXML with one marker named by the node and `markers.txt`, EDL, an unknown format 422); the moved unit tests (+1: the stamps through
  the lane and back); the P17 scenario moved to Story · Episode (the checklist asks on the EDL export of a plain clip); the smoke scenario
  "an episode": a format-size fake-engine clip → a final shot → a Dialogue node with a line bound to it; the old deep link opens Story ·
  Episode; the Shots bin shows the shot *final* with its node's name, `+` puts it on the lane stamped, a plain clip beside it; the
  checklist names clip 2 and the foot says "1 of 2 clips not final shots"; Export ▶ asks "1 of 2 clips not finalized shots", the FCPXML
  carries one marker named by the node, the SRT the line at 00:00:00,000; Animate's rail has no Sequence tab — 25/25 under `full` and
  `open`. 292 offline, 204 unit, lint 100, tsc and build clean, CSP clean on seven pages, audits clean.
- **The author's check (17 §3e):** the Resolve import of an FCPXML with markers and an `.srt` — not mine to run.
- **CI on SY3 (35cc759) failed on both variants in the Flow scenario:** on the runner's smaller window the three nodes stacked at the view's
  centre overlapped, and a mouse drag of the Start grabbed the Dialogue (two columns instead of three). The scenario now lays the nodes
  out through `PUT /story/flow/graph`, reloads and fits, and keeps one mouse drag on the free Choice node (its saved y moves); passes
  under both variants here. Lesson: an e2e mouse gesture on React Flow nodes needs nodes that cannot overlap at any window size.
- Not in SY4: the Shots bin as a drop source onto the lane with stamps (its drag carries the clip, the stamps come with `+`); a per-clip
  "hold / freeze" at a transition (loom R157, the lane trims into content). Next: SY5 alpha — `scripts/sy_acceptance.py` through the six
  workflows of 17 §4 on the rig, the docs, D85's acceptance mark.

## 2026-10-14 01:21 — SY5 · the Story alpha: 17 §12 through the app on the rig, the documents closed (17 §10, D85)
- **`scripts/sy_acceptance.py` grew the rest of 17 §12** and ran as one pass (its own orchestrator + engine, Edge via CDP on the dev server):
  `world` (item 1), `sy1` with `durability` inside (items 2 and 6), `sy2` (item 3), `sy3` (item 4), `sy4` (item 5). Dev hooks for it:
  `__loom2Story.openTab`, `__loom2Sequence` (the lane's store, DEV only).
- **Rig (00:59–01:19, 71 checks ok, `engine/spikes/out/sy/`):** *world* — two styles, the first the default, the World tab shows both; the
  preview appends style B's fragment; a Klein 9B job with style B done in 31 s, its manifest stamping `style_id` and the fragment that ran.
  *sy1* — Mara v1 from the heroine (the hero its page's cover), the Cast page shows her; Expand Full coverage queues 36 jobs; **the
  orchestrator killed after 3 jobs and relaunched on the same state with `--project`: the queue came back paused with the 33 others
  queued, the world and the profile at their revisions, the page back on the socket; `POST /queue/unpause` resumed it** (the engine had
  gone with the killed process and came back cold on the next job: 33.9 s, then 10.6 s median) — 36/36 done in 411 s; 36 candidates
  with their cells, the Cast page lists them; 30 kept with every shot-size row, the rejected marked, the grid tinted; Lock → 423 on the
  page, the stub 422, the strip's badge; `@Mara` → v1 with the hero first, the stub on the note; a Generate job with the mention done
  in 38 s with the stamp in its manifest. *sy2* — the clay frame landed on the shot (32 s), the Wan draft clip (84 s) refused with the
  format in the reason, the Full one (1920×1072, 25 f, 621 s) accepted → final, the strip says final, then stale after a focal change.
  *sy3* — six nodes, six edges, the SY2 shot bound (a second bind 422), Validate names only the two empty end shots, the canvas shows
  the six, Play stops at the Dialogue (the play view with the lines and the bound clip), Push sets the variable and takes *then*, Wait
  takes *else*, the job count unchanged. *sy4* — the lane's first clip the final shot stamped with its version and node, the FCPXML with
  one marker "At the gate", `markers.txt`, the SRT with the two lines, the EDL, the draft render in 15 s. A first pass of the same
  script stalled for an hour after the relaunch: my script had called `/queue/release` (staged jobs) instead of `/queue/unpause` (the
  Resume the banner offers); `wait_jobs` now gives up when nothing finishes for 15 min and the check counts the jobs it asked for.
- **Docs:** 17's status closes (SY0–SY5 built, D85 accepted with the alpha on the rig), 17 §12 gets the run's line, 13 D85 the acceptance
  mark, 14 §5 and 12 §8d the built note, 08 §1 the SY row. The author's own checks stay theirs: the Resolve import of the FCPXML with
  markers and the SRT (`engine/spikes/out/sy/` holds a reel's exports from this run), and the curation of a real cast by eye.
- **What the alpha does not have (17 §13, by decision):** LoRA training (the version's `trigger` / `lora` slots wait for the LT wave),
  voice and lip-sync, Muse (spike E15 first, then queued assistants only), continuity chains beyond Animate's extract → first/last frame,
  a hold / freeze at a transition, re-rolling one thin coverage cell into the candidates page. Next: the author's checks; then the LT wave
  (03 §5 item 2) or Klein tiers / SeedVR2 (03 §5 items 3 and 5) — the author's call; E15 before any Muse work.

## 2026-10-14 08:11 — Wave LT · LoRA training: the plan → `18-lora-training.md`, D86 proposed
- After the Story alpha (01:21) the next wave of 17 §13 / 03 §5 item 2. Read: D25's plumbing (`LoraRef`, `_lora_chain`, `_validate_models`,
  the manifest's `loras[]`, Generate's disabled slots), the Story version's reserved `trigger` / `lora`, loom P2's M1 record
  (`kb-loom-p2-imp.md` §M1 and `trainers/ai-toolkit/LOOM_VENDOR.md`: ai-toolkit `548a286` trained Z-Image on this card under ROCm 7.2 —
  512², rank 16, qfloat8 Quanto, low_vram, AdamW 1e-4, 1.34 s/it, 500 steps for an identity, resume from `optimizer.pt`; six patch seams,
  no torchao / bitsandbytes, NumPy 1.26.4, PEFT in an overlay), ai-toolkit at `f7a1fb9` (2026-10-10: `arch flux2_klein_4b / _9b`, the base
  transformer read from a folder holding `flux-2-klein-base-4b.safetensors` — loom2's own file —, the encoder as a Qwen3 transformers folder,
  pins torch 2.13.0 / torchvision 0.28.0 / torchaudio 2.11.0 = the engine venv's versions, SciPy 1.12 → Python 3.12), the queue's CPU path
  (`plan().engine` False → `run_cpu`), `supervisor.stop`, the roster's `rglob` scan and `unlisted_files`, ComfyUI's `loras` folder listing
  subfolders, the disk (Klein base 4B / 9B and the VAE present; `F:/HF_HOME` holds BiRefNet only; 750 GB free).
- The plan (18): §2 spike E16 as the gate (install on torch 2.13 ROCm 10 in `trainers/.venv`; 1 000 steps of Klein base-4B on the SY1 run's 30
  Mara refs ≤ 2.0 s/it under 15 GB with a kill + resume; the adapter on distilled klein-4b through `LoraLoaderModelOnly` with FaceSim ≥ 0.30
  and ≥ base + 0.20; 9B a recorded stretch); §3 the design — the trained-LoRA record in the project (`story/loras/`) cached under
  `<models_root>/loras/projects/<project_id>/` for the engine, `LoraRef` ids from the registry with a base check at submission, the staged
  `train_lora` job with the engine stopped, captions = trigger + `cell_sentence(coverage_cell)`, the runner's progress file and log, resume by
  ai-toolkit's checkpoints, `TrainFinisher`, readiness (advisory), Generate's four slots fed by `GET /loras`, `@mention` → LoRA + trigger,
  the Models suite's Trained group, the optional FaceSim check; §6 E16 (3 d) · LT1 slots (2 d) · LT2 the job (5 d) · LT3 mentions + check +
  rig (3 d) ≈ 13 d; §9 the nine defaults for the author. 13 D86 proposed, 00 row 18, 12 §8e, 08 §1 the LT row, 17 §13 the pointer.
- Not done on purpose: nothing installed, nothing fetched — E16 needs the `Qwen/Qwen3-4B` transformers folder (7.5 GB, Apache-2.0) and ≈ 7 GB
  of venv, which the author approves with 18 §9 (the 16 / 17 precedent). Next: the author's answer → E16.

## 2026-10-14 09:14 — E16 · ai-toolkit on torch 2.13 ROCm 10 with Klein base-4B: GO (18 §2, D86)
- **E16a install:** `scripts/trainer-setup.ps1` → `trainers/.venv` (12 GB; Python 3.12.10 — ai-toolkit pins SciPy 1.12, no 3.13 wheel; torch
  2.13.0+rocm10.0.0, HIP 7.15, the AMD index resolves its wheels for cp312), ai-toolkit `f7a1fb9` (2026-10-10) as the submodule `trainers/ai-toolkit`,
  the requirements minus torchao / bitsandbytes / torchcodec under `trainers/constraints.txt` (numpy 1.26.4; `--index-strategy unsafe-best-match`
  after the first install stopped at the AMD index's own numpy). **One patch seam** instead of loom's six: `trainers/patches/0001-torchao-optional.patch`
  guards the three eager torchao imports (`toolkit/config_modules.py`, `toolkit/util/quantize.py`, `toolkit/models/lokr.py`); this torch build's
  `torch.distributed` is complete (is_initialized, c10d, fsdp), so loom's `run.py` predicate and the Diffusers FSDP shim are not needed. `run.py --help`,
  the flux2 extension (`flux2_klein_4b` / `_9b`), `quantize` and the trainer import clean. Fetched (the author's approval): `Qwen/Qwen3-4B` as a
  transformers folder (7.5 GB, 459 s) and `Qwen3-8B` (15.3 GB, 912 s) into `F:/HF_HOME`, the autoencoder `ae.safetensors` from `ai-toolkit/flux2_vae`
  (321 MB): loom2's `vae/flux2-vae.safetensors` is the diffusers-named repack (251 tensors, `decoder.conv_norm_out…`) the loader rejects
  (`KeyError decoder.up.0.block.0.conv1.bias`) — LT2 remaps it rather than carrying two files.
- **The reference set** through the product's own path (`e16_klein_lora.py --part refs`: loom2's orchestrator on a temp state, the hero
  `bench/angles/07.jpg` → Mara → Expand `full` on Klein 9B): 36 jobs in 504 s (walls 7.2 / 12.9 / 56.0 s), every candidate kept, 37 PNGs under
  `engine/spikes/out/e16/refs/` with `mara_e16, <cell sentence>` (the hero with the stub). The curate route lives under the version
  (`/story/profiles/<id>/versions/<vid>/curate`) — the first pass 404'd on a wrong path and was re-exported with `--reuse`.
- **E16b train:** 1 000 steps, 37 refs at 512, rank / alpha 16, qfloat8 Quanto on the transformer and the encoder, `low_vram`, gradient checkpointing,
  AdamW 1e-4, batch 1, sampling off: **1.07 s/it** steady (bar ≤ 2.0), **peak VRAM 13.6 GB** by Windows' GPU adapter counter (bar ≤ 15; 13.5 GB during
  the steps), 1 214 s wall for the two launches with their model loads; the kill at step 300 (`taskkill /T`) → the relaunch on the same yaml printed
  `#### IMPORTANT RESUMING FROM …\4b_1000_000000250.safetensors ####` · `Found step 250 in metadata, starting from there` and ran 250 → 1 000 (exit 0);
  the adapter `4b_1000.safetensors` 46.2 MB, sha256 `bf541319…`. The spike's first `resumed` flag read tqdm's initial `0/1000` bar as the first step —
  it now reads ai-toolkit's own resume lines.
- **E16c load:** the adapter copied to `F:/loom2-models/loras/e16/`, the engine standalone, loom2's Klein t2i graph + `LoraLoaderModelOnly`: the first
  prompt was refused — ComfyUI lists a subfolder's file as `e16\4b_1000.safetensors` (the OS separator, as E10 met for `flux1\ae.safetensors`); with
  `os.path.join` it loads with **0 `lora key not loaded` lines**. FaceSim (ArcFace, the largest face against the hero) over 8 coverage prompts
  (the back view has no face): klein-4b (4 steps, 4.0 s an image warm, 23 s cold) **LoRA 1.0 = 0.377** (7 / 8 faces), LoRA 0.8 = 0.291, trigger-only
  0.107, the stub without the LoRA 0.110; klein-base-4b (20 steps, 12.6 s) **LoRA 1.0 = 0.392, 0.8 = 0.405**, trigger-only 0.011, stub 0.049; the refs'
  own band to the hero p10 / median / p90 = 0.418 / 0.582 / 0.743 (34 faces of 36). Bars: ≥ 0.30 ✓ and ≥ control + 0.20 ✓ on both models. By eye
  (`load_4b_1000.jpg`): the LoRA rows show the same red-haired woman, grey coat and red scarf in 7 / 8 cells on both models; the trigger-only rows
  random people, the stub rows the costume on random faces. Two things for LT2: at 0.8 the distilled model drifts (hair colour) — the default strength
  is 1.0 on distilled, 0.8–1.0 on base; and the LoRA carried the refs' white-room setting with the character — the template captions name no
  background, so LT2's captions add the setting word (`caption_dropout_rate 0.05` kept).
- **Verdict: GO on Klein base-4B** — every bar of 18 §2 met on the first run; 18 §2 carries the run line, 18 §9 item 6 the strength, 13 D86 the
  mark. E16d (9B base with Qwen3-8B on the CPU) runs next and gets its own line. Next: LT1 (slots live), then LT2 on this spike's runner shape.

## 2026-10-14 09:23 — E16d · the 9B stretch: Klein base-9B fits only with layer offloading (18 §2, D86)
- **As configured for 4B** (qfloat8 Quanto on the transformer and the encoder, `low_vram` — Qwen3-8B on the CPU): the run paged from the first step
  — **70 s/it** at 15.7 GB dedicated + 8.2 GB shared (the 9B transformer at qfloat8 ≈ 9 GB plus the grads and activations is over the card, ROCm
  spills to host memory as loom saw with dev); killed at step 3.
- **With ai-toolkit's `layer_offloading`** (`--offload`; it turns `qfloat8` into torchao's `float8` on both models, so the first probe failed with
  `KeyError: 'float8'` under the torchao-optional seam): torchao 0.10.0's pure-Python wheel installs and imports on torch 2.13.0+rocm10.0.0 ("no
  triton" warning only), and 100 steps ran at **2.8 s/it (tqdm; 3.8 by the 2 s poller) with a peak of 8.7 GB**, the checkpoint and optimizer saved —
  1 000 steps ≈ 47 min, inside the stretch's bar (≤ 4 s/it, < 15 GB). The adapter's quality on 9B is not measured (100 steps); LT2 offers
  `klein-base-9b` as a per-job base with offloading on, and keeps 4B as the default. torchao stays in the trainer venv (`scripts/trainer-setup.ps1`
  no longer drops it; the venv is 12 GB); the optional-import patch stays — the 4B path runs without it. The spike's error list now reads the last
  launch's part of the appended log (the first attempt's KeyError had leaked into the row).
- **E16 closed:** GO on 4B (09:14), 9B a per-job base; 18 §2 / §9, 13 D86 carry both. Next: LT1 (slots live), LT2 on the spike's runner shape.

## 2026-10-14 09:48 — LT1 · D25's LoRA slots live (18 §3b / §3e, D86)
- **`orchestrator/loom2/loras.py`:** a `LoraRef.model_id` is a roster id (`role="lora"`, now with `base` — the model base it fits — and `preset` — the
  toggle or method that applies it: turbo / lightning / angles / stage / guide, never a slot), a `file:<path under a loras folder>` (the author's
  own files, E16's adapters under `loras/e16/`; no family declared, so offered to every model with that said, not under `open` — D26) or, with
  LT2, a trained `lora-…`. `model_base` from the spec's new `base` (`klein-4b` for 4B and base-4B, `klein-9b` for 9B, base-9B and KV; the family
  elsewhere), `lora_options` (what the pickers show, the non-fitting ones with their sentence), `check_recipe_loras` (≤ 4 slots, no duplicate, the
  base, the preset owners, the open gate, the file on disk — one sentence, 422 at submission and from the preview alike), `lora_name` (a roster
  file's name, a file's path with "/"; `contract.resolve_names` settles the engine's own spelling — ComfyUI lists a subfolder with the OS
  separator, E16), `lora_names_listed` (finalize refreshes `/object_info` once when a slot's file is newer than the engine's listing).
  `Roster.lora_files` reads the loras folders of every tree, LT2's `projects/` cache left out (and out of the unknown files).
- **Graphs:** `_lora_chain` by `lora_name`, after the preset's own LoRA (Turbo on dev) and the reference nodes (B11), now in t2i, i2i and inpaint
  (node ids 300+); every summary carries `loras[{model_id, strength, lora_name}]` (`loras_summary`; `effective_params` takes the roster) —
  the parity snapshot regenerated for the new key. `recipe_weights` keeps roster ids only.
- **API:** `GET /loras?model_id=` → `LoraListing {model_id, base, items[LoraOption], max_slots}` (139 routes; openapi 107 paths / 227 schemas,
  `schema.d.ts`); `/recipes/preview` runs the same check and leaves an unlisted slot file out of its contract problems. The fake engine's
  standalone takes `--models-root` and lists the tree's loras folder as ComfyUI does; the e2e tree holds `loras/smoke/mara_smoke.safetensors`.
- **Generate:** `LoraSlots.tsx` replaces the D25 stub in the Model tab — four selects (the fitting ones, then "does not fit" disabled with the
  sentence) with a strength each, the next slot opening after the last used one; `generateStore.loadLoras` on a model change prunes a persisted
  slot that no longer fits. Lint 100 (none new), tsc and build clean, Vitest 204.
- **Tests:** `test_lora_slots_lt1.py` (+5: the sources and the fit, a roster LoRA's base through a monkeypatched entry, the chain in the three
  graphs by its links with the engine's own spelling, the route and the 422, a job on the fake engine whose compiled summary and manifest record
  the slot after the listing refresh); `test_api` / `test_lifecycle` keep "unknown model id" for a bad slot id; 297 offline, audits clean
  (`base_label` reads the registry — D65 caught a literal first). Smoke "lora slots (18 / LT1)" 26/26 under full and open under full.
- Next: LT2 — the staged `train_lora` job on E16's runner shape, the registry (`story/loras/`), readiness, the Cast and Models UI.

## 2026-10-14 10:19 — LT2 · the staged `train_lora` job, the registry, readiness, the Cast and Models UI (18 §3a / §3c / §3d / §3g, D86)
- **Backend:** `recipes.TrainLora` (profile, version, the base's roster id, steps / rank / resolution / lr / seed, trigger, name, the `setting`
  word — one job through the queue's seed loop); the specs' `recipes.train` block (klein.toml: base-4B `flux2_klein_4b` + Qwen3-4B, 13.6 GB,
  1.07 s/it; base-9B offloaded, 8.7 GB, 2.8 s/it — E16's figures, D65); `Settings.trainer` (the venv's python, `run.py`, cwd, the hub VAE repo,
  the quantisation); `orchestrator/loom2/trainer.py` — `validate_train` (a trainable base offered under the variant with its weights, the venv,
  the trigger, the version with ≥ 4 references: one sentence at submission and from the preview), `materialise` (the reference page's images
  as PNG ≤ 1024 with `<trigger>, <cell sentence | the stub>[, <setting>]`, deterministic names so the trainer's latent cache survives a
  resume), `train_config` (loom P2's exercised shape with E16's Klein values), `run_train` (the engine stopped first — `plan().gpu` —, an
  asyncio subprocess of the trainer venv with its log in `state/logs/train-<job>.log`, the job card from the trainer's own lines
  "step N / M · loss · s/it · min left", VRAM sampled from the adapter counter, a cancel killing the process tree, an exit ≠ 0 failing the
  job with its last lines, the adapter promoted: `story/loras/<id>.json` + `.safetensors`, the version's `lora` + `trigger`, the engine's
  cache `loras/projects/<project>/`, `lora.changed`; the set and the saves deleted, the log kept); `loras.py`'s `LoraRecord` / `LoraRegistry`
  / `ensure_mounted` / `publish` (the roster's `trained` map at project open and after every change; trained ids first in the slots' list,
  the base check, the loader's name under `projects/`); `JobQueue.requeue` (a failed, resumable job back to the queue — a killed trainer
  continues from its newest save); routes `POST /story/profiles/{pid}/train` (the trigger made from the name, kept on the version), `GET /
  story/loras`, `GET /story/loras/{id}`, `DELETE /story/loras/{id}` (the file, the record, the cache, the versions' slots cleared, the trigger
  kept), `POST /jobs/{id}/requeue`; `/capabilities.train` (available + why, the bases with E16's figures and health, the ranges, `min_refs`)
  and `.models[].base`; 144 routes, openapi 111 / 237.
- **Frontend:** `coverage.ts readiness` (references, rows, angles, expressions, hero, celled → 0–100 with its sentences; advisory), the Cast
  strip's Train step live with the score, the Inspector's `TrainingBlock` (readiness, trigger, the LoRA with its measured figures, the
  options — base / steps / resolution / rank / name / setting / staged —, the estimate from E16's rate, the newest job's state with Release /
  Resume / Cancel as commands), `story.cast.train` (askConfirm with the cost), `useLora` (Generate on a model of the LoRA's base with slot 1 and
  the trigger), `deleteLora`, the Models suite's `TrainedTable`, LoraSlots' "+ trigger" chip, `lora.changed` → the registry, the profiles and
  the slots reload. Lint 100, tsc and build clean, Vitest 206 (+2 readiness).
- **Tests:** `tests/fake_trainer.py` (tqdm-shaped lines, the step saves, the resume lines, a crash at `FAKE_TRAINER_CRASH_AT`);
  `test_train_lora_lt2.py` (+5: the registry / publish / options, the dataset and the config, the staged job released → promoted → a Generate job
  carrying it under the engine's spelling and a retrain's `previous`, a crash requeued and resumed from step 250 + a cancel, the routes and the
  capabilities); 302 offline, audits clean. The "a cast" smoke scenario trains 100 steps on the fake trainer from the Inspector (staged →
  Release → the version holds the LoRA, the slot lists it on Klein 4B) — 26/26 under full and open.
- **Delta to 18 §3c:** no `trainers/loom2_train.py` wrapper — the orchestrator runs `run.py` itself; the identity check (3h) and the mention
  auto-slot (3f) are LT3's with the rig acceptance (`scripts/lt_acceptance.py`: the real Mara through the app).

## 2026-10-14 14:41 — LT3 · the mention auto-slot, the identity check, the rig acceptance — the LoRA wave closed (18 §3f / §3h / §8, D86)
- **3f:** `resolve_mentions(…, roster)` — a profile mention whose version holds a trained LoRA adds `LoraRef(id, 1.0)` to the slots when the
  recipe's model takes the base (`model_base`), a slot is free and it is not there yet; the trigger leads every note the mention's references
  carry into the prompt; the mention is stamped `lora` / `lora_available`; `T2I.auto_lora` (default on) is the per-prompt switch — the
  chip's "+ LoRA" / "LoRA off" in Generate (`RefExtras`), the stored recipe's mention-added slot dropped at reload (the server adds it again at
  today's version). The queue passes its roster, so the preview and the submit agree (T8).
- **3h:** `POST /story/loras/{id}/check` — eight Iterate jobs (four coverage sentences × with / without, seeds 1001–1004, the trigger in the
  prompt, `auto_lora` off) in one batch onto "<profile> · <version> · LoRA check" under the version; the asset finisher's `_lora_check_result`
  scores each image's largest face against the hero's (FaceSim, cosine) as it lands and the record's `identity` grows (`with`, `without`, the
  means, `done` / `n`, `status` — "weights missing — scripts/fetch_facesim.py" without the weights); the Inspector's identity line and the
  `story.cast.checkLora` verb (when the hero and the weights are there). Advisory, never a gate.
- **The trainer's process** is a `Popen` in the orchestrator's job object (`engine/supervisor._assign_to_job`): a killed orchestrator takes its
  trainer along — never two trainers on one card; the relaunch's `requeue` continues from the newest save.
- **Tests:** `test_lora_mentions_lt3.py` (+3: the auto-slot with the trigger, off per prompt, a slot already held, another base, the queue's
  path with the engine's graph and the manifest; the check's eight jobs and the record growing to 8 with the weights absent; the job object);
  `test_mentions_d73` excludes the new stamps; the fake engine rescans its loras folder on every `/object_info` as ComfyUI does (the e2e's
  check jobs met a stale enum before). 305 offline, 145 routes, openapi 112 / 238, audits clean, lint 100, tsc and build clean, Vitest 206;
  the "a cast" smoke scenario now ends with the mention's "+ LoRA" chip, the preview's slot and trigger, `auto_lora` off, and the check's
  eight fake-engine images — 26/26 under full and open.
- **Rig (`scripts/lt_acceptance.py`, 18 §8):** the hero → Mara → Expand full (36 jobs in 894 s with the e2e running beside it; 37 references kept) → the staged job released → **killed at step 300** (the trainer's two pids died with the orchestrator — the job object), relaunched, requeued → **resumed from the step-250 save** and finished: 1 255 s wall, **1.15 s/it, peak 13.5 GB**, the record 44 MB (37 refs, the setting word), the version's slot and trigger `mara_d01f`, the engine's cache, `GET /loras` on Klein 4B first and fitting, not on 9B; the preview and a 36 s Generate job with "@Mara waits at the city gate at dawn" took the LoRA and the trigger by themselves (the manifest and the compiled name say so); the check's 8 images in 37 s on klein-4b: **FaceSim with 0.426 · without 0.118** (bars ≥ 0.30 and ≥ without + 0.20 met); a wrong base refused (422); Delete removed the record, the file, the cache copy and the slot and kept the trigger (verified on disk — the route's reply shape was wrong for its schema and is fixed with a unit test). Two passes: the first stopped at the preview (a None guard in the preview's LoRA filter after a relaunch, fixed), the second ran the rest on the trained state (`--reuse`); 27 checks ok, 0 failed.
- **D86 closed:** 18's status, §3f / §3g / §3h notes and §8's run line, 13, 12 §8e, 08 §1, 00 row 18, `trainers/AGENTS.md`. Next: 17 §13's
  other waves (voice, Muse behind E15) or 03 §5 items 3 / 5 — the author's call; LT's follow-ups are 18 §1's "out" list (style LoRAs on an album
  group, video LoRAs) and the CI flakes noted on 8d380e5 / 9e3bfa2 (the open-variant smoke, a Windows replace race now retried in `fsio`).

## 2026-10-14 15:12 — Wave CN · continuity and voice: the plan → `19-continuity-and-voice.md`, D87 proposed
- The author chose 03 §5 item 4 for the next wave and asked for lip-sync with it (after the LoRA wave closed at a8fee57, CI green). Read:
  11 (Animate: FLF, beats, extract → first / last frame, the *Extend* verb reserved), 16 §8 (ST4: LTX + IC-LoRA on the Stage's depth pass, the
  pose pass weaker), 17 (shots with takes, Flow lines, the Episode's SRT), 18 (the LoRA as the identity source), loom P3 (continuity the
  make-or-break R&D: pixel-identical handoffs vs a seam weld vs a dissolve; node-level voice with two TTS tiers + lip-sync), D8 / D9 / D27 / D76's
  measurements; the pinned engine's own nodes — `WanSoundImageToVideo` (+ Extend), `WanInfiniteTalkToVideo`, `WanAnimateToVideo` / `…2`,
  `WanVaceToVideo`, `Wan22FunControlToVideo`, `LTXVAudioVAEEncode` / `LTXVConcatAVLatent` (loom2's LTX graph already builds the joint latent
  with an empty audio latent), `LTXVAddGuide` on a frame sequence, `AudioEncoderLoader`; the Apache repacks (S2V fp8 15.3 GB + wav2vec2 0.6 GB,
  Animate fp8 KJ 17.1 GB + clip_vision_h 1.2 GB, Fun-VACE 16.2 GB × 2 or Kijai's 2.8 GB modules); the 2026 TTS field (Kokoro Apache CPU,
  Chatterbox MIT, Qwen3-TTS Apache with ten languages and a 3-s clone — XTTS / F5 non-commercial, out under D17 / D26).
- The plan (19): four spikes first — E20 voice, E17 extend (LTX guide-frame extension with the previous clip's last 9 frames vs Wan last-frame
  chaining + a RIFE weld, a seam metric and FaceSim at both ends of a three-segment chain), E18 lip-sync (LTX-2.3 IA2V on the distilled
  transformer vs Wan2.2 S2V, a mouth-motion proxy against the audio envelope), E19 pose-driven shots (Wan2.2 Animate *Move* on loom2's own
  pose pass with the Cast hero, PCK vs the rendered keypoints; VACE only on a NO-GO); then CN1 extend (`extend_from`, `chained_from`, the
  Episode's weld at export, beats across a chain), CN2 voice (an `audio` asset kind, `voice` records with the consent note, the `tts` job per
  Flow line, an audio lane in the exports), CN3 lip-sync (a take on a shot version), CN4 the `animate` clip method, CN5 the rig acceptance;
  ≈ 22 d; nine defaults for the author (19 §6) incl. ≈ 38 GB of downloads and the TTS packages into `trainers/.venv`.
- 13 D87 proposed, 00 row 19, 12 §8f, 08 §1 the CN row, 17 §13 and 11 §3d pointers. Nothing installed or fetched.

## 2026-10-14 16:29 — E20 · the voice tiers: GO on both (19 §2, D87)
- **Setup:** the voice tools could not share `trainers/.venv` — `qwen-tts` pins transformers 4.57 while ai-toolkit pins 5.5.3 (with 5.5.3 restored,
  `qwen_tts` fails to import: `check_model_inputs() missing 1 required positional argument`) — so they have `voices/.venv` (`scripts/voices-setup.ps1`:
  Python 3.12, the engine's ROCm torch wheels, `kokoro` + `misaki[en]` + `soundfile` + `qwen-tts` under `voices/constraints.txt`, plus pip and spaCy's
  `en_core_web_sm` — Kokoro's English G2P fetches it through pip / uv, which need a venv marker and pip itself; the first run died on
  "No virtual environment found"). `voices/AGENTS.md` written. The draft tier's `soundfile` and PyAV also serve E18 in the orchestrator venv.
- **Draft (Kokoro-82M, Apache-2.0, CPU):** loads in 2.2 s; four English lines of 3.5–5.0 s of speech in 4.7 / 2.5 / 2.7 / 13.0 s — the 13 s one ran while
  E17's engine decode and two 15 GB downloads shared the machine (bar ≤ 5 s: 3 / 4, the outlier to be rerun at idle). No German in Kokoro.
- **Cloning (Qwen3-TTS-12Hz-0.6B-Base, Apache-2.0, GPU):** loads in 167 s cold (the 2.3 GB fetch included), the clone prompt from a 4.6 s Kokoro
  reference + its transcript in 19.5 s, then six lines — four EN of 3.4–4.1 s in 3.0–5.1 s, two DE of 5.0–5.4 s in 4.6–4.9 s — at a 2.6 GB peak,
  the plain-torch path (no FlashAttention). Bar ≤ 15 s ✓ on all six; by ear the author's (`engine/spikes/out/e20/*_clone.wav`). Chatterbox not needed.
- **Verdict: GO** — the draft tier on the CPU beside a running engine, the cloning tier on the GPU (2.6 GB fits beside an idle engine; the plan keeps
  it behind `plan().gpu` for the engine-stopped case). CN2's `tts` job runs `voices/.venv`'s python (`Settings.voices`). 19 §2 run line, §6 item 3
  amended, 13 D87 marked.

## 2026-10-15 09:17 — CN2 · voice: the audio asset kind, voice records, the `tts` job, the lines' voices, the exports' audio lane (19 §3b, D87)
- **Built** (19 §3b's built note has the detail): `AssetKind` + `audio` (WAV master, `duration_s`, the waveform as thumbnail, the Catalogue's
  badge / Type · Audio / player, WAV and FLAC importable); `orchestrator/loom2/voices.py` — `VoiceRecord` in `story/voices/` (draft: ten Kokoro
  voices, English; cloning: a 3–10 s reference asset + transcript + speaker + a required consent note), the `tts` recipe and job running
  `voices/tts.py` in `voices/.venv` (`Settings.voices`; the cloning tier behind `plan().gpu`), every line an audio asset stamped on its Flow line
  (`audio_asset_id` / `audio_text`, lineage `voice-clone` to the reference); `Profile.voice_id`; seven routes (145 → 152); `/capabilities.voice`;
  the FCPXML's connected audio clips on lane −1 and the EDL's `AX` events at the SRT's line ticks (`timelines.line_spans`, shared with the SRT);
  the Cast Inspector's Voice block, the Flow Inspector's ▶ / 🎙 per line, the fallback voice and *Voice all lines*; `soundfile` joins the
  orchestrator's dependencies (uv.lock); `orchestrator/tests/fake_tts.py` stands in for the runner; `scripts/cn_acceptance.py --parts voice`.
- **Tests:** `test_voice_cn2.py` (+5: the audio kind end to end, the records' sentences, the job on the fake runner — draft without the engine,
  cloning with the engine stopped and the reference as parent, a crash, a cancel, the stamp kept across a stale client patch — the audio lane,
  the routes and the capabilities); 310 offline, audits clean, openapi 116 / 248, lint 100, tsc and build clean, Vitest 206; the smoke's new
  "a voice" scenario (the Cast form → a draft voice → 🎙 on a line → ▶, the audio asset, *Voice all lines* with the fallback) and the episode
  scenario's audio lane — 27 / 27 under full and open.
- **Rig (`scripts/cn_acceptance.py --parts voice --tier both`, then `--tier draft` again after the fix):** draft (Kokoro, CPU) — 5.4 / 2.3 / 4.6 s
  lines spoken in 1.9 / 0.8 / 1.4 s, load 5 s, rtf 0.34; cloning (Qwen3-TTS-0.6B, GPU, the engine stopped) — a clone from a 5.4 s draft line,
  two German lines of 4.6 / 3.8 s in 4.6 / 3.8 s, load 11 s, peak 2.59 GB; the 422s (no fallback voice for a speakerless line, a clone without
  consent), the stamps, the lineage, the delete — all ok.
- **Finding:** the first draft run failed its bar on one line ("Thank you, that is kind of you.": 7.4–10 s for 2.3 s of speech while a 5.4 s line
  took 3 s). Profiled: 98 % in `addmm` — the ROCm Windows wheel's BLAS is OpenBLAS (`BLAS_INFO=open`), whose threaded small multiplies have
  ~100 ms cliffs at some row counts (a 48×768 · 768×768 took 112 ms at 8 threads, 0.9 ms at one; flushing denormals and `OPENBLAS_CORETYPE` change
  nothing). Kokoro at **one thread** speaks every line 3–10× faster than at 4–16 (and leaves the cores to a running engine) — `voices/tts.py`
  sets it; E20's 13 s outlier was this, not machine load. Worth remembering for any CPU torch work in these venvs.

## 2026-10-15 09:21 — CI · the smoke's red runs since 2026-10-13 sorted; the flow scenario connects one edge at a time
- Of the last ten completed CI runs, seven failed, each on one Playwright scenario that passes locally: "a flow" twice (b345d85, 8d380e5 —
  the handle drags made 1 or 2 of 3 edges: the slow Windows runner drops a drag whose pointer events outran React Flow), the Edit
  chunk-failure scenario once (5f39bcf — the 90 s boot), "@mentions" once (c343696 — `net::ERR_NO_BUFFER_SPACE`, the runner out of socket
  buffers), and the two already fixed (d4a99b6 the hub VAE, 9e3bfa2 the PermissionError).
- **Fix (the flow scenario):** each edge is connected and polled before the next; a missed drop is dragged again once (the same mouse path),
  and every drag ends with a pointermove over the target handle before the release. Playwright's `retries` stay 0 (a flake stays visible).
  The Edit boot and the socket-buffer failures are the runner's; they stay as they are and are named when they recur.

## 2026-10-15 09:41 — E19 · pose-driven shots: GO for one character per pose pass (19 §2, D87)
- **First run (2026-10-14 18:23, cut short when the session ended after two shots):** PCK 0.0 on both, and turn_orbit showed the hero's face
  painted huge and translucent into the background. Two faults, both the spike's: (1) the score compared E11's keypoints in its 1024×576
  render with SDPose's detections in the 832×480 output — the pose video reaches `WanAnimateToVideo` through `ImageScale` (cover, centre
  crop), so the points need the same transform (`map_figs`); rescored, the first run's walk_dolly is 0.965 and the ghosted turn_orbit 0.609;
  (2) the portrait hero was centre-cropped to landscape for `reference_image` — the model reproduced the crop as background. The reference is
  now fitted inside the frame on its own edge colour (`padded_ref`, `--ref-mode pad`).
- **Rerun (2026-10-15, padded, Wan2.2 Animate-14B fp8 KJ + LightX2V 4-step, 4 steps CFG 1, 77 f at 832×480):**

  | shot | PCK@0.1 | FaceSim first / mid / last | exec |
  | --- | --- | --- | --- |
  | walk_dolly | 0.958 | 0.08 / 0.12 / 0.07 (a small face) | 264 s |
  | turn_orbit | 0.805 | 0.38 / 0.49 / 0.40 | 283 s |
  | wave_static | 1.0 | 0.41 / 0.45 / 0.39 | 297 s |
  | run_track | 0.0 | 0.61 / 0.50 / 0.32 | 285 s |
  | crouch_crane | 0.972 | 0.33 / 0.19 / — | 288 s |

  Bars (19 §2): PCK ≥ 0.8 — 4 / 5 (the LTX IC-LoRA pose baseline followed 3 / 5); ≤ 300 s — 5 / 5; no OOM. **run_track** is a real failure: its
  pose pass holds two small overlapping runners (a tracking shot from E11) and Animate rendered a close-up of a face behind two hands — one
  character per pose pass. **FaceSim ≥ 0.45** is missed narrowly where the face is large enough to score (0.38–0.49) and meaningless on the wide
  shots; by eye the character holds across every shot (the face, the red braids, the green hood) — ArcFace on a painted hero at medium distance
  sits at the edge of its same-person band, as in E17.
- **Verdict: GO** for CN4 with three conditions recorded in 19 §2: the reference padded into the frame, one figure per pose pass (CN4 refuses a
  pass with two), FaceSim shown as advisory on the take (18 §3h's pattern). VACE stays unfetched. Nothing to delete (Animate is the winner;
  `clip_vision_h` and the LightX2V LoRA are its parts). One cosmetic note: the walk clip carries a hallucinated CJK caption top right despite
  the negative prompt's 字幕 — watch for it in CN4's rig run.

## 2026-10-15 11:16 — E17 extend and E18 lip-sync: NO-GO on both; CN1 and CN3 leave the wave (19 §2, §6 item 1, D87)
- **E17 (`engine/spikes/e17_extend.py`; the hybrid and `--rescore` ran 10:20–10:37):** three chains × three segments, scored by the seam ratio
  (bar ≤ 1.5× the clip's own inter-frame difference), FaceSim to the start frame at both ends (≥ 0.45, the end now at the last frame *with a
  face*, and a per-segment curve), time ≤ 1.3× a plain clip.

  | method | worst join alley / cabin / rooftop | FaceSim at the end (cabin / rooftop) | time |
  | --- | --- | --- | --- |
  | A · LTX guide frames (last 9 frames as `LTXVAddGuide`) | 1.06 / 0.31 / 0.95 ✓ | 0.075 / 0.056 ✗ | 1.1× ✓ |
  | B · Wan last frame + RIFE weld | 1.21 / 1.71 / 2.11 (4 / 6) | 0.545 ✓ / 0.371 ✗ | — |
  | hybrid · Wan, then LTX guide extensions | 0.76 / 0.84 / — ✓ | 0.336 ✗ | — |

  The per-segment curves say where it breaks: LTX loses the face at the first join (cabin 0.82 → none → 0.085: the continuation invents a
  person once the character leaves mid-frame — the by-eye note of 2026-10-14), Wan keeps it longest (cabin 0.88 → 0.85 → 0.77 → 0.69 → 0.66 →
  0.55) at the price of visible seams. The alley chain ends with the character turned away (no face to score). **NO-GO** on the bars: CN1
  leaves the wave. Kept for later: LTX guide frames are a clean *scene* continuation; a character's long take is worth a spike of chained
  Animate windows (`continue_motion` with the same reference each window).
- **E18 (`engine/spikes/e18_lipsync.py`; the 10-step S2V follow-up ran 09:40–10:17):** six lines (four EN, two DE from E20's tiers) on two
  faces; sync = Pearson r of the lower face's motion against the audio envelope at the best lag ±3 (bar ≥ 0.5), FaceSim ≥ 0.45, ≤ 240 s.
  LTX-2.3 IA2V (distilled 1.1): r 0.09–0.29 on 6 / 6, 118–152 s, FaceSim 0.84–0.97 (the face barely moves). Wan2.2 S2V-14B fp8, 20 steps CFG 6:
  EN 0.49 / 0.71 / 0.60 / 0.67, DE 0.37 / 0.32 (wav2vec2-large-*english*), FaceSim 0.56–0.96, 906–999 s; 10 steps: EN 0.35 / 0.61 / 0.53 / 0.72
  in 520–566 s. By eye the S2V mouths open and close through the lines (the muxed clips for the author's ear in `engine/spikes/out/e18/`).
  **NO-GO**: the only method that follows the audio is English-only at 2–4× the time bar. CN3 leaves the wave; the S2V transformer (16.4 GB)
  and wav2vec2 (0.6 GB) deleted from F:/loom2-models (19 §6 item 2; `fetch_weights.py --only e18` brings them back), the roster entries kept.
- **The wave now:** CN2 voice (built), CN4 pose-driven shots (built, rig next), CN5 acceptance and docs. 19 §2 run lines, §4 rows, 13 D87,
  12 §8f, 08, 11 §3d and 17 §13 updated.

## 2026-10-15 11:21 — CN4 · pose-driven shots: the Stage's Wan Animate method (19 §3d, D87)
- **Built** (19 §3d's built note): the Animate spec in `wan22.toml` (`recipes.animate`, graph `wan_animate`, E19's figures), reached through
  the `I2V` recipe with a pose guide; E19's graph in `graphs.build_i2v`; one window of ≤ 77 frames (`i2v_params` refuses more); the
  reference padded into the clip before upload (`pipeline.pad_reference`); the queue's sentences (a pose sequence required, one figure per
  pass from the stored keypoints, no end frame or beats); `/capabilities.stage.animate`; the Shot tab's clip method (IC-LoRA · Wan Animate)
  with the guide's grid, size and kind following it. The object_info fixture gains Animate's and the lip-sync nodes from a v0.39.0 capture
  (merged, the loader lists unioned; `make_object_info_fixture.py` lists them); the fake engine decodes `WanAnimateToVideo`'s length.
- **Tests:** `test_animate_cn4.py` (+4: the spec and the graph, the weights / estimate / padding, the submission's sentences and a clip on the
  fake engine with the padded upload and lineage, the capabilities); 314 offline, audits clean, openapi 116 / 249, lint 100, tsc and build
  clean; the smoke's "a pose-driven shot" (the method, the pose sequence at 480p on the 16-grid, the clip with lineage — both variants: Animate
  is Apache) and the 3D-prop scenario picking an image tile (the new clips had pushed one into its slot) — 28 / 28 under full and open.
- **Rig (`scripts/cn_acceptance.py --parts animate`):** a stage with E11 walk_dolly pose sequence uploaded through the guide route (77 frames, one figure) and the hero as the character: the job ran cold in 299 s wall (engine start and loads included; sampling 4 × 22 s), 77 frames at 848×480, PCK@0.1 1.0 (bar ≥ 0.8), lineage to the hero and the pass, the reference padded, no caption artefact this time; FaceSim 0.08–0.21 (a small face, advisory as in E19); E11 run_track (two figures) refused with the sentence (422) — 6 checks ok.

## 2026-10-15 11:29 — CN5 · wave CN accepted on the rig, D87 closed (19 §5)
- **`scripts/cn_acceptance.py --parts voice,animate,episode --tier both` (11:22–11:29), one orchestrator, the engine started by the app:
  41 / 41 checks.** Voice: draft lines 0.7–2.0 s (rtf 0.33, load 5 s; 21 s on the first, cold), cloning EN / DE 2.6–5.4 s at a 2.65 GB peak, the
  422s (no fallback voice, no consent), stamps, lineage, delete. Animate: the two-figure pass refused; E11's walk performed by the hero in
  278 s (warm-ish: the engine started for it), 77 frames at 848×480, PCK@0.1 0.993, the reference padded, lineage to the hero and the pass
  (FaceSim 0.14–0.19 on a small face, advisory). Episode (new part): the Animate clip as a shot bound to a Dialogue node, its two lines
  voiced by a draft voice in one job, one lane — the FCPXML has both lines as connected audio clips on lane −1 (their WAVs on disk) and the
  node's chapter marker, the EDL two `AX` events, the SRT both lines; copies in `engine/spikes/out/cn/episode/`.
- **D87 closed:** CN2 voice and CN4 pose-driven shots built and accepted; CN1 extend and CN3 lip-sync dropped on E17 / E18 (journal 11:16).
  19 status / §4 / §5, 13 D87, 12 §8f, 08, 00 row 19 updated. CI: 81286a3 red on the runner (the Animate scenario's app boot timed out at
  60 s — the runner class, docs-only commit), 0b27b43 running.
- **Owed by the author:** the Resolve import of `engine/spikes/out/cn/episode/cn_episode.fcpxml` (with the EDL and SRT beside it), a listen
  to the voices (`engine/spikes/out/cn/voice/`) and E18's muxed S2V clips if lip-sync is to be revisited.

## 2026-10-15 11:40 — CI · the lora slots scenario waits for its job
- 93ee175 went red on the full variant: "lora slots" read the job once, right after its asset appeared in Unprocessed, and found it still
  `running` (the finisher ingests the asset before it marks the job done). The scenario now polls the job to `done` (15 s). The open variant
  was green; 81286a3's red was the runner (the app boot over 60 s in the Animate scenario).

## 2026-10-15 12:02 — D88: extension and lip-sync back as experimental features (the author)
- The author, after the wave closed: "I'd like to revisit lip-sync, I think that in the long run we could refine it for better performance. I
  also feel the same way about extensions. Let's put these features back and mark them as experimental for now." Recorded as **D88** (13)
  and 19 §7 before the work: XE extend (`I2V.extend_from`, LTX guide frames / Wan last frame, `chained_from` / `overlap`, Animate's
  *Extend ▶*, the Episode trims the overlap) and XL lip-sync (Wan2.2 S2V through `I2V.audio`, English, one window ≤ 4.8 s, Draft 20 / Fast
  10 steps, a take on the shot version, staged), both flagged *experimental* with E17 / E18's measured caveats. Out: the export weld, beats
  across a chain, S2V's extension, German. The S2V transformer and wav2vec2 (17 GB, Apache-2.0) are being fetched again
  (`fetch_weights.py --only e18`).

## 2026-10-15 12:27 — D88 built: extension and lip-sync as experimental features (19 §7)
- **Built** (19 §7's built note): `I2V.extend_from` / `I2V.audio`, the specs' `extend_lead` and the S2V spec (Draft 20 / Fast 10 steps,
  English), the LTX lead-in guide and E18's S2V graph, the queue's sentences, the chain record (`chained_from` / `overlap`), the line in the
  proxy, the lip-sync take on the shot version, `POST /clips/{id}/extend` and `POST /story/shots/{sid}/versions/{vid}/lipsync` (152 → 154
  routes, openapi 118 / 258), `/capabilities.experimental` with the caveats, Animate's *Extend ▶ (experimental)*, the shot version's Lip-sync
  block, the Episode lane's overlap trim, an *experimental* badge. The fake engine lists uploaded audio (LoadAudio) and decodes
  `WanSoundImageToVideo`'s length. The proxy encoder adds the audio stream before any packet (PyAV refuses a stream added after the header).
- **Tests:** `test_experimental_d88.py` (+3: the graphs, the extend and lip-sync jobs on the fake engine with their sentences, the routes and
  capabilities), Vitest +1 (`chainIn`) — 317 offline, audits clean, lint 100, tsc and build clean, Vitest 207; the smoke's "experimental
  extension and lip-sync" (Extend ▶ with the caveat → the continuation's parent and overlap; Lip-sync ▶ → staged → released → the take)
  29 / 29 under full and open.
- **Rig (`scripts/cn_acceptance.py --parts extend` and `--parts lipsync`):** extend — an LTX-2.3 clip of the hero (121 frames, 1024×576) continued through `POST /clips/{id}/extend`: the continuation in 156 s, `chained_from` / `overlap 9` recorded, the seam ratio 1.46 (E17's bar ≤ 1.5), FaceSim to the hero 0.97 at the start and 0.69 at the continuation's end (the character mid-frame, walking — E17's failure case is the character leaving the middle). Lip-sync — a 3.1 s English line voiced by the draft tier on a shot with the hero's frame, Lip-sync at Fast through the app: staged, released, 49 frames in 282 s wall (cold load included), the take on the version, the line in the proxy, sync r 0.635 (E18's bar ≥ 0.5), FaceSim 0.70–0.95.
- **Experimental stays:** E17's case (the character leaving mid-frame) and E18's bars (≥ 0.5 on every line, ≤ 240 s, German) are not met;
  the caveats say so beside the verbs.

## 2026-10-15 12:42 — CI · the new-angle scenario pins its source tile by id
- c4bacaa went red on the full variant: "a new angle" read the ninth Catalogue tile twice (to click it, then for its id), and an asset that
  landed in between (an earlier scenario's job) shifted the grid — the job's parent was the clicked tile, the test expected the other. The id
  is read once and the tile clicked by it. The open variant was green.

## 2026-10-15 17:16 — UI · the Project menu leads the suite tabs
- The author found the project menu (New / Open / Close / Recent), shown at the right of the top bar under the open project's name, hard to
  recognise as a menu ("m5-acceptance-20261007" — the M5 rig run's project, reopened as the dev state's last project). It is now the first entry
  of the suite tabs: **Project** with the open project's name beside it, a separator, then Catalogue … Models; the menu itself is unchanged.
  The first smoke scenario checks its place and its items; 29 / 29, build clean, lint 100.

## 2026-10-15 18:09 — D89 · wave CR (creative image models) accepted; CR0 fetch started
- The author found FLUX.2 accurate but not creative and asked for a quick web study of creative t2i / i2i models: `.docs/creative_image/`
  00–03 (candidates, levers, integration), then picked Krea 2 Turbo / Raw, Z-Image base and Chroma1-HD for t2i + i2i and SD 3.5 Large for
  i2i only; the plan is 04 (wave CR, slices CR0–CR6). Answers to 04 §1: no content filter (Krea's duty is the author's), the Stability AI
  Community licence accepted, the downloads with the Krea LoRAs, SD 3.5 Large → D89 accepted.
- Found while planning: the pinned engine (v0.39.0) carries `Krea2`, `ZImage`, `Chroma` and `SD3` model classes and their Comfy templates
  (`comfyui_workflow_templates_json`), so no custom node; Comfy-Org's `qwen_image_vae` in Krea-2 and `qwen_3_4b` in z_image_turbo have the
  same sha256 as the files loom2 already holds (`qwen-image-vae`, `qwen3-4b`), so they are reused. The FLUX.1 `ae` the E10 note found in the
  D: tree is not on F: (D80), so it is fetched.
- CR0: `scripts/fetch_weights.py --only cr` (≈ 77 GB) started; the first run died on a cp1252 console encoding the "→" in its banner when
  the output was redirected — rerun with `PYTHONIOENCODING=utf-8`.

## 2026-10-15 21:22 — D89 built · wave CR (creative t2i / i2i) accepted on the rig
- **CR0:** the 18 files (≈ 77 GB: Krea 2 Turbo / Raw fp8, Qwen3-VL-4B fp8, the nine style LoRAs + the style reference, Z-Image bf16, the
  FLUX.1 ae, Chroma1-HD fp8mixed, T5-XXL fp8, the SD 3.5 Large fp8 bundle) fetched to F: at 15 MiB/s, every sha256 equal to the HF LFS oid.
- **CR1:** `engine/image_families.py` — the per-`graph` node shapes (CLIPLoader type, empty latent, FluxGuidance or not, shift node, Chroma's
  T5 options, SD 3.5's one checkpoint); `build_t2i` / `build_i2i` read it, `_image_loaders` beside `_flux2_loaders`, which now refuses a
  non-FLUX graph (inpaint, tiled refine, Angle, Stage); `registry.FLUX_GRAPHS` vs `IMAGE_GRAPHS` with the registry rules (no inpaint, refs,
  Stage, Angle, training or Turbo on the new families; a checkpoint graph has no te / vae). The 17 FLUX.2 / Klein parity graphs unchanged
  without `--parity-update` (only the I2I summary's sampler / scheduler keys are limited to the new families to keep it so).
- **CR2–CR4:** specs `krea2.toml`, `zimage.toml`, `chroma.toml`, `sd35.toml` from the pinned Comfy templates; 18 roster entries (Krea 2's
  style LoRAs as slot LoRAs with base `krea2`, the style reference a preset); `/capabilities.models[id]` gains `guidance_node` and
  `tiled_refine`, the preview's `guidance` is None without FluxGuidance (T8); Generate lists only `recipes.t2i` models and hides Guidance
  where there is no node, the tiled-refine picker keeps to the FLUX family. Fixture recaptured from the running v0.39.0 engine (+
  EmptyLatentImage, EmptySD3LatentImage, T5TokenizerOptions, the new files); `pin_review.recipes()` + 8 variants (parity 25: 8 added).
- **Tests:** `test_creative_d89.py` (+17), the LT1 slot tests read Krea's LoRAs as `fits: false` — **334 offline under full and open**,
  audits clean, Vitest 207, build clean, lint at its 3 warnings, smoke 29 / 29 (one flaky mentions run on the first pass, green alone and on
  the rerun).
- **Rig (`scripts/cr_acceptance.py`, three runs, 21:18 the last with 0 failures).** t2i at Draft 960×544, 3 bench prompts × 2 seeds, the
  engine restarted per model (cold = load + sampling, the OS file cache warm):

  | model | cold s | warm s (median) | peak GB | note |
  | --- | --- | --- | --- | --- |
  | Krea 2 Turbo | 15.4 | 14.1 | 13.85 | same prompt new seed 7.5 s; a new prompt ≈ 40 s (the encoder swap) |
  | Krea 2 Raw | 43.7 | 72.9 | 13.45 | same prompt 35 s; a new prompt 229–242 s — the encoder on the CPU: 88–91 s (cold 151 s), peak 13.1 GB |
  | Z-Image | 32.0 | 19.0 | 14.51 → **13.87 with fp8_e4m3fn** | bf16 missed the 14.5 GB bar by 0.01; the fp8 cast looks the same → the spec's `weight_dtype` |
  | Chroma1-HD | 27.1 | 19.8 | 13.82 | |

  Seed variety (one prompt × 8 seeds at Thumb; mean pairwise layout distance = 1 − the correlation of 32×32 greyscale thumbnails, colour =
  mean ΔE of 8×8 Lab — pixel proxies, no DINO in loom2): **FLUX.2 dev 0.262 / 86**, Krea 2 Turbo 0.281 / 123, Klein 9B 0.472 / 118,
  Krea 2 Raw 0.490 / 133, Chroma 0.648 / 154, **Z-Image 0.749 / 169** — the author's "FLUX.2 is not creative" in numbers.
  Refine (a fresh document per job; layout similarity to the source at 0.3 / 0.55 / 0.75 on bench/inpaint/source.png, 0.55 on two angles
  frames): Chroma 0.999 / 0.994 / 0.935 (39–53 s), Krea 2 Raw 0.976 / 0.891 / 0.698 (45–70 s), SD 3.5 Large 0.993 / 0.963 / 0.809
  (18–21 s), Z-Image (fp8) 0.995 / 0.975 / 0.912 (25–28 s), Krea 2 Turbo 0.970 / 0.831 / 0.682 (11–15 s) — every model keeps the
  composition at 0.3 (bar ≥ 0.8), peaks 13.2–14.2 GB. **Krea 2 Turbo's partial denoise holds** (an unprompted 0.55 re-imagines the alley
  with the layout kept) → `recipes.i2i` on Turbo. Krea at 1280×720 is no better than at 960×544 → its Draft tier stays.
- **Two acceptance-script bugs, fixed before the numbers above:** the first run reused one document per frame, so Refine (the *visible*
  composite) refined the previous model's result layer — SD 3.5 and Z-Image "failed" 0.3 at 0.311 / 0.285 (Krea's 0.75 layer underneath);
  and the Turbo probe built its Roster without `scan()`. Nothing deleted (D30): every model passed.
- Measured `estimates` and hints into the specs (Krea 2 Raw's hint names the new-prompt cost and the CPU encoder). Owed: the author's look
  at `engine/spikes/out/cr/` (t2i, variety, i2i, krea-size, zimage-dtype).

## 2026-10-16 19:28 — D90 · the UI reorganisation accepted; wave UI0 (bugs) started

- The author asked for an inventory of every function and its place (`.docs/proto01_UI/01-function-inventory.md`: the frame and seven
  suites, ≈ 330 functions with ids F/C/G/E/A/S/Y/M, 302 registered commands, 18 cross-suite concepts X1–X18, 19 bugs B1–B19), then gave
  the direction (Story first and highest, the Catalogue under Story after Cast, Models in ☰, Generate as one resizable scrolling panel,
  presets as icons, styles shown as images) and asked whether loom2 had become several applications. The plan
  (`.docs/proto01_UI/02-ui-plan.md`) answers it — one backend, nine applications on screen — and the author accepted it ("can you make
  this?") → **D90**, the open points of 02 §12 on the plan's defaults.
- The original loom read for the plan (`stubz-002-tripo-sf/loom`): one sample image per style in `bible/styles/`, picked from an image
  popover with the fragment only as a tooltip (the author's request of 2026-08-08); World the first top tab in v2 (Assets in v1); pose
  cells as generated mannequin icons; v2's single composer column with the action pinned and a drag-resizable 260–420 px width.
- Order: UI0 bugs (B1 Stage keys while typing and B2 Story keys across tabs can lose work) → UI1 frame → UI2 Generate column → UI3 icons
  and visual styles → UI4 context → UI5 vocabulary and shared components → UI6 makers.

## 2026-10-16 20:01 — D90 · waves UI0 (bugs) and UI1 (frame) built; the swatch backend and the preset-icon component for UI3

- **UI0 — the 19 bugs of `proto01_UI/01` §11.1 fixed.** B1 Stage keys in fields (and B8 Animate's Ctrl+Enter from the prompt) through
  `frame/fieldKeys.ts` — a field keeps its keys, the primary action still answers; B2 Story keys per tab (`story/storyKeys.ts`,
  `handleKeyFor(scope, e, only?)`), the Flow canvas and the Episode stage forward keys; B3 `story.flow.deleteEdge` (edge menu, Delete /
  Backspace, Undo toast); B4 `submitBlock` gates Ctrl+Enter / the palette; B5 one trash toast; B6 lip-sync lines over
  `experimental.lipsync.seconds_max` disabled (the voiced line's `duration_s`); B7 the Episode lane is the drop target, a Shots-bin card
  arrives stamped, the bin offers the final version (Y57, `episode/bin.ts`); B9 Edit's Crop tool draws a rectangle, Enter / a double-click
  inside crops (`edit.crop.apply` / `.cancel`); B10 clips and audio play in the loupe and compare (`catalogue/media.ts`); B11 "Add a node
  here" through `screenToFlowPosition`; B12 Generate follows the model (negative only where honoured, in every mode; the tier size
  re-applied; `/capabilities.models[id].flux_shift` hides base / max shift on Z-Image and Chroma; no reference block at `max_refs` 0;
  `addRefs` caps at the model's limit); B13 Generate's Inspector links open the Catalogue (`split.openPlaceFrom`), lineage gets a Back; B14
  profile and shot names saved after a 400 ms pause, one save at a time; B15 Show in Cast opens Cast; B16 Shift+F10 on the grid opens the
  selected tile's menu; B17 one predicate for Back to Unprocessed (`catalogue/placement.ts`); B18 a hovered AI candidate is a view
  override (`candPreview`, `viewDoc`), never a document edit; B19 a beat's line shows on Shot nodes.
- **UI1 — the frame (02 §3, §3.1, §7).** Top bar: ☰ first (Models & engine…, settings, keys, palette, focus, dock, theme, density,
  refresh, quit; the spike harness in dev builds only), Project ▾ kept on the project's name, then **Story · Generate · Edit · Animate ·
  Stage** on Ctrl+1–5. Story's rail is World · Cast · **Catalogue** · Shots · Flow · Episode (`railTabs.STORY_RAIL`, `TOP_TABS`,
  `useRailEntries`): the Catalogue stays its own suite underneath (scope, keys, deep links, wide strip unchanged) and shows under the
  Story tab; the Story tab returns to the workspace last open under it (`ui.storyLast`); Alt+1–6 open Story's workspaces. **Models &
  engine** is a sheet (`frame/ModelsSheet.tsx` over the old suite's parts: Roster / Engine, *only the missing weights*, *Fetch all
  missing*); every old route to the Models suite opens it on the missing weights, the engine chip on the Engine tab. The Panel and the
  Inspector are drag-resizable per suite (`frame/Resizer.tsx`, `panelWidth.ts`; Generate 30 % of the window by default, double-click
  resets). Settings › Keyboard and the D32 audit now include Stage and Story; the audit also reads `registerCommands(cmds)` (Story's main
  command file was never audited) — one declared pair, Delete for a World row / a Flow connection.
- **UI3 groundwork.** `frame/PresetIcons.tsx` (one tile row for every preset; words in the tooltip and `aria-label`, an optional caption)
  and `frame/presetGlyphs.tsx` (drawn glyphs for shot size, camera angle, lens, depth of field, aperture, composition, subject position,
  the angle moves, aspect and tier — every built-in of those fields has one, tested). The swatch pack backend: `preset_icons.py` +
  `routes/preset_icons.py` (`GET /preset-icons`, `GET …/{key}/file`, `POST /preset-icons/make` — one staged 512² t2i per preset on the
  `swatch` default, `default_for = ["swatch"]` on Klein 4B in `klein.toml`, origin surface `swatch` — and `DELETE`), the finisher writes
  `<state>/preset_icons/<key>.webp` and broadcasts `preset_icons.changed`. The pack's one-time cost is owed to the rig.
- Tests: Vitest 230 (+23), offline 340 under full and open (+6), audits clean, lint 96 warnings (100 at HEAD), build clean, smoke 29 / 29
  under full and open (`openCatalogue` in the fixtures: the Story tab, then the Catalogue workspace).

## 2026-10-16 20:16 — D90 · waves UI2 (Generate as one column) and UI3 (presets as icons, styles as images) built

- **UI2 (02 §6.1).** Generate's Panel is one scrolling column (`generate/GenerateColumn.tsx`): Saved panels · Prompt (Tree / Text / JSON,
  scene, subjects, lead text, negative where the model honours one) · References · Look (the Story style by its sample, lighting, mood,
  art style, background, composition, palette) · Camera (shot size, angle, lens, depth of field, aperture) · Model (compact cards with a
  health dot; Sampling, LoRAs and Advanced folded unless set) · Size (aspect and tier as drawn shapes, a count stepper, exact pixels only
  for a custom size) · Preview (the prompt as sent, opened from the Foot's **Preview**). The rail's seven buttons jump to the sections and
  follow the scroll; the Panel head says "Generate" (`SuiteDef.panelTitle`); the Panel opens at 30 % of the window (UI1). Look and Camera
  say so when the prompt is not a Tree. The dead "Upsample (later)" and the stale "coming in M5" are gone; guidance and CFG gained a reset;
  the FLUX-only `flux2` schedule is listed only where the graph has its shift. **New angle** left Generate's rail: a sheet over whatever
  suite is open (`AngleSheet`, opened by "New angle…" on an image), its five moves as drawn icons; queueing closes it.
- **UI3 (02 §4.1, §6.3).** Every prompt-field preset is an icon tile (`PresetRow` on `frame/PresetIcons`): drawn glyphs for geometry,
  generated swatches for looks (`generate/swatches.ts` over `/preset-icons`; the Look section's ▣ N makes the missing ones after a
  confirm, a tile's right-click remakes one, `preset_icons.changed` reloads), monograms until a swatch exists; words in the tooltip, a
  section's **Aa** shows them under the tiles (remembered). A field's **+** saves its text as a preset, which joins the row (right-click
  removes it). **Styles as images:** World › Styles is a tile grid of samples (`story/StyleWorld.tsx`; a style's face is the cover of its
  group, `StoryStyle.group_id`, made on first use as `Style · <name>`); **Make a sample image** queues one 768² text-mode t2i on
  `defaults.swatch` with the style applied and the result placed in the style's group (`origin.payload.group_id`); a dropped Catalogue
  image is copied in as a sample; the fragment is written only in the World Inspector. Generate (and anything else) picks a style from
  `story/StyleTiles.tsx` — default, none, then the samples with ★ on the default, the fragment in the tooltip. Commands
  `story.world.styleSample`, `story.world.openStyleGroup`, `story.world.open`.
- Tests: Vitest 235 (+5: style samples), smoke 29 / 29 under full and open (the angle scenario drives the sheet, the
  world scenario makes a sample and picks the style by its tile, the LoRA scenario opens the LoRAs fold), lint 88 warnings (100 at
  D90's start), build clean; `scripts/sy_acceptance.py` reads `.style-tile`. **Rig owed:** the swatch pack (64 look presets at 512² on
  Klein 4B) and a style sample, measured and looked at.

## 2026-10-16 20:48 — D90 · waves UI4 (makers in context) and UI6 (Edit, Animate) built

- **UI4 (02 §5, §4.2).** A shot can make its own frame and clip: **Make frame ▸** (in Generate · in Stage) and **Make clip ▸** (in Animate
  · in Stage · Lip-sync) on the shot's Strip, board, Inspector and right-click, and on a Flow node with a bound shot. Generate and
  Animate opened this way show a **For** chip ("For: Shot 12 · v1 ✕ · ← Back to Shot 12", `story/ForChip.tsx`, `origin.useMakeFor`), are
  pre-filled (a Shot node's line or title, a Dialogue node's speakers as @mentions, the node's board as references within the model's
  limit; the version's frame as Animate's start) and submit with origin surface `for_shot` — the finisher adds the results to the version
  as **takes** (`_shot_takes`, shared with lip-sync; the first fills an empty frame / clip), `POST /jobs` refuses a missing or final
  version (422). ✕ drops the context; a maker opened from its tab has none. **Flow boards:** a node carries `board_group_id` (an album
  group; Inspector select, a group card dropped on the node, its cover on the card; open / remove commands). **Go to origin** lands on the
  object for Expand, training, the LoRA check, lip-sync, shot takes, voices and style samples. Not built: takes as a Catalogue group (an
  asset lives on one page, D34 — moving takes would pull them off their pages) and the groups' "used by" line.
- **UI6 Animate (02 §9).** Extend, the continuation and the lip-sync line under one *Experimental* fold; the Clips tab has a search and a
  state filter, hides trashed clips and has a right-click per clip (Show in Catalogue, Keep, Reject, Make a shot…, Move to trash —
  `anim.trash`); J / K / L in a Shuttle submenu of the player menu (with ±4× in the speed select), Loop / Onion as checked commands,
  Identity and Make a shot there too; the beats hint no longer promises draggable markers.
- **UI6 Edit (02 §9).** The AI runs are commands (`edit.ai.select|inpaint|refine|upscale|outpaint|stage`, their `when`s from the tab's own
  reasons in `edit/aiRecipes.ts`, tested), an **AI ▸** group in the canvas menu (Select subject runs at once; Inpaint / Refine / Upscale /
  Outpaint open the tab on that operation), Re-run (new seed) and Copy recipe JSON as commands; the toolbox shows the storyboard
  essentials with Magic wand, Spot healing and Eyedropper behind **More tools** (keys and Tool ▸ unchanged); *Compare preview* and the
  renderer badge are dev-build diagnostics (Info › Diagnostics); declared placements made true (new group, pick colour, opacity ▸, the
  magnetic lasso's back step, the clipboard row in the Selection tab, Before as toggle + hold); **Merge visible**; the row lock acts on the
  selection and is undoable. Flatten is owed (it needs a server-side flatten that keeps the layers).
- Frame: Help lists the gestures of Animate, Stage and Story too; the Catalogue's grid menu always has **Group by ▸** (G's mouse home);
  `edit_headed_check.py heal` picks the tool by command.
- Tests: offline 343 under full and open (+3), Vitest 259 (+24), smoke 30 / 30 under full and open (+1: Make frame for a shot → the For
  chip → takes), lint 88, build clean, audits clean.

## 2026-10-16 21:23 — D90 · wave UI5 (one vocabulary, one transport, every action a command) built — D90 complete

- **One word per concept (02 §8.1)** in labels, tooltips, toasts and hints (command ids, tab ids and fields unchanged, so key overrides
  survive): the run-later button is **Queue** (Generate, Animate, Edit AI; the Dock's **Run now**); the Stage suite's Shot tab is
  **Render** with **Render frame** / **Render clip ▶**; Cast's Lock and Shots' Finalize are one **Mark final** with one badge **final**;
  Episode holds **cuts**; **count** everywhere; **Unbind from its node** for both shot/node releases, **Run now** for a staged training;
  Cast's keep is **Add to the reference set**, Edit's is **Use candidate N** / **Use all**; tiled refine shows as **Upscale (detailed)**;
  the Catalogue's **Select subject…** (was "Remove background…"), **Back (Esc)**, "Pin for compare" / "Unpin", one wording for the Animate
  verbs, "Move to group", no duplicate Variations / Animate in *Start from this image ▸*, "Make a shot from this clip…" at the top of a
  clip's menu; Story without spec jargon in its text, node titles instead of ids, **New character…** with distinct character / place /
  prop icons; Edit's **Save**, one **Quick mask**, "Add mask: …" in one vocabulary, "Close the shape".
- **One transport (02 §8.2):** Space play, ← / → frame, Shift+← / → ±10, Home / End first / last in Animate, the Stage timeline and the
  Episode lane (Animate keeps , . as alternates; the Stage's key jumps moved to Alt+← / →, its range to I / O with [ ] kept, Frame
  everything to Shift+F); a Vitest keeps the three transports' keys equal. Animate's frame step is now a fixed key (a plain arrow), so a
  remap of it no longer applies — as Settings › Keyboard treats every fixed key.
- **Every action a command:** Models & engine (`models.rescan`, `.fetchAll`, `.fetch`, `.verify`, `.reveal`, `.engine.*`, with keys while
  the sheet is open and a right-click per roster row), Story (`story.shot.useTake`, `story.flow.voiceLine`, `story.episode.addShot` /
  `addClip`, `story.flow.next` / `restart`), `cat.loadInGenerate`, `gen.fetchMissing`.
- **The audit catches drift now:** every command that declares `context` must be referenced by a menu in the sources (26 were not — each
  added to its menu or its false placement dropped), and a hand-written `markUsed` must name a command the file renders or runs (two
  fixed). The non-context placements are not checked statically; why is written in `commandAudit.test.ts` and `frame/AGENTS.md`.
- Tests: Vitest 263 (+4), smoke 30 / 30 under full and open, lint 88, build clean, settings and agents audits clean; offline suite
  unchanged (343, no Python touched but `edit_headed_check.py`'s strings). **D90 is complete** except what 02's status line lists; owed:
  the rig run of the swatch pack and a style sample, and the author's click-through of the new layout.

## 2026-10-16 21:42 — D90 follow-up · the sample scenes are settings (Settings › Samples)

- The author asked whether the style sample's prompt was baked into the code: it was (`styleSamples.ts` `SAMPLE_PROMPT`), as were the
  look-preset icons' scenes (`preset_icons.py` `PROMPTS`). Both now live in `Settings.samples` (`config.SampleSettings`:
  `style_prompt`, `swatch_prompts` per field, the old texts as the defaults in `config.py`), edited in **Settings › Samples**: a blank
  entry is its default again, a scene without `{value}` gets it appended; `POST /preset-icons/make` renders with the saved scenes and
  "Make a sample image" with the saved style scene. Existing samples and icons are not remade (a tile's right-click remakes one).
- Tests: offline 343 (the swatch test checks a changed scene reaches the job, the `{value}` append and the blank reset), Vitest 263
  (the recipe takes the setting, blank = default), settings audit 228 fields clean, contract regenerated, smoke 30 / 30, lint 88.

## 2026-10-16 21:50 — D91 · a sample-model choice; Lumina Image 2.0 and SD 3.5 Medium to be added

- The author asked for a model drop-down for the samples (style samples, preset icons) — Klein 4B and at least two smaller models — and
  picked **Lumina Image 2.0** (2.6B, Apache-2.0, both builds) and **SD 3.5 Medium** (2.5B, Stability AI Community, `full`) from four
  offered (SDXL base and Z-Image Turbo not taken). → D91. Work: specs + roster + fetch entries, the graphs from the pinned templates, a
  Sample model setting with the choices from the specs, fetch and sha256, the rig run.

## 2026-10-16 23:03 — D91 built · the sample-model choice; Lumina Image 2.0 and SD 3.5 Medium accepted on the rig

- **Fetch:** `scripts/fetch_weights.py --only sm` (two new entries, licences `apache-2.0` / `stabilityai-ai-community`) into
  `F:/loom2-models/checkpoints/`: `lumina_2.safetensors` 10 620 240 765 B, sha256 `b703b020…6b186`; `sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors`
  11 638 004 202 B, sha256 `1778e885…79bacf` — both equal to the HF LFS oid, both in `roster.index.json` (health `verified`). The line
  ran at 2–9 MiB/s (≈ 2 MiB/s through most of it); the first run died again on the cp1252 "→" (rerun with `PYTHONIOENCODING=utf-8`).
  SD 3.5 Medium went in a second process to share the line, and the first was stopped once Lumina was indexed (it would have fetched Medium
  again: its index is read at start). The Medium transfer **stalled** at 8.25 GB from 22:43 to ≈ 22:47 (an open connection, no bytes —
  the coordinator saw it hang) and then resumed by itself; it finished at 22:50 without a restart and the sha256 matched. Owed, not done:
  a stall timeout in `fetch_weights.py` (restart on no growth for 120 s).
- **Graphs:** the pinned templates carry no Lumina Image 2.0 graph (only its NetaYume fine-tune, the same shape) and no SD 3.5 Medium
  one; Lumina's is the engine's own example (`ComfyUI_examples/lumina2`, the workflow embedded in `lumina2_basic_example.png`):
  CheckpointLoaderSimple → ModelSamplingAuraFlow 6 → KSampler 25 steps, CFG 4, res_multistep / simple, EmptySD3LatentImage, the
  positive prefixed with the "superior" system prompt + `<Prompt Start>` (the text the core `CLIPTextEncodeLumina2` builds), the negative
  plain. A new image family `lumina2` in `image_families.py` (a checkpoint graph with the AuraFlow shift), `registry.IMAGE_GRAPHS` /
  `CHECKPOINT_GRAPHS`; the system prompt is spec data (`sampling.prompt_prefix`), applied in the graph only — the asset's
  `serialized_prompt` stays the author's text, the summary records `prompt_prefix`. SD 3.5 Medium runs loom2's `sd3` graph (the
  sd3.5_simple_example shape, built-in shift 3) at Stability's card values, 40 steps, CFG 4.5, euler / sgm_uniform (Skip Layer Guidance,
  which the card also suggests, is not in the graph); t2i **and** Refine (the same graph; Refine 0.3 measured below).
- **Specs / roster:** `specs/lumina2.toml` (`lumina-image-2`, family `lumina2`, `full` + `open`) and a second `[[model]]` in `sd35.toml`
  (`sd35-medium-fp8`, `full`); both `recipes = { t2i, sample }`, Medium also `i2i`; Generate tiers 896×512 / 960×544 / 1920×1088 (the
  `sd3` family's tiers now on SD 3.5 Large's entry, the first of its family). `ModelSpec` gains `recipes.sample` (a sample model must run
  t2i; the default swatch model must be one) and `geometry.sample_px = { style = 768, swatch = 512 }` (the defaults; a spec may say
  otherwise — none needed to: both new models read well at 768² and 512²). Klein 4B gets `sample = true` and stays `default_for = ["swatch"]`.
- **Choice:** `registry.sample_specs(variant)` (the default first, then by `order`) and `registry.sample_model(id, variant)` (the
  setting's when it names an offered sample model, else the default). `/capabilities.sample_models` = `[{id, label, short, health,
  missing, default, style_px, swatch_px, license, seconds}]` — full: Klein 4B · Lumina 2 · SD 3.5 Medium; open: Klein 4B · Lumina 2.
  `Settings.samples.model_id` (None = the default; blank → None); `swatch_recipe` / `POST /preset-icons/make` use it at the model's swatch
  size; the style sample (`styleSamples.pickSampleModel`, the same rule) at its style size. **Settings › Samples › Sample model** — a
  `<select>`: "default · Klein 4B", then the others, "(not fetched)" when a weight is missing; saved with the other sample settings.
- **Tests:** `test_sample_models_d91.py` (+8: licences / variants, the list and the fallback, the registry rules, Lumina's example graph,
  Medium's t2i + Refine, the swatch recipe, capabilities + the make route under full and open); D89's tests widened for the two models;
  the fixture's `CheckpointLoaderSimple` list gains the two files from a v0.39.0 capture (no new node classes); `pin_review.recipes()` + 3
  (parity 28 — the 25 earlier graphs unchanged). **Offline 354 under full and open**, settings audit 229 clean (`sample_models` mapped),
  model literals 0, agents check clean, contract regenerated, **Vitest 266** (+3: the rule, the size, the options), lint 88, build clean,
  **smoke 30 / 30 under full and open**.
- **Rig (`scripts/sm_acceptance.py`, 22:51–22:54, 0 failures)** — the engine restarted per model (cold = load + sampling, the file
  cache warm); the swatches through the real route (Settings › Samples set, `/preset-icons/make`, the icons stored with the model as
  lineage); peak = the engine's VRAM in use during the part:

  | model | style 768² cold s | warm s | 3 swatches 512² s | Draft 960×544 s | Refine 0.3 | peak GB (style / swatch / draft) |
  | --- | --- | --- | --- | --- | --- | --- |
  | Klein 4B (default) | 11.3 | 3.5 | 2.7 · 2.3 · 2.2 | 3.6 | — | 12.08 / 13.04 / 11.84 |
  | Lumina 2 | 16.2 | 9.1 – 9.4 | 4.1 · 3.8 · 4.1 | 7.8 | — | 10.49 / 10.50 / 10.49 |
  | SD 3.5 Medium | 17.2 | 8.9 – 9.4 | 5.1 · 5.7 · 4.3 | 9.7 | 19.3 s, layout 0.993 | 12.19 / 12.18 / 12.50 (Refine 11.69) |

  All within the 14.5 GB bar; an earlier run at 22:21 (Klein 4B + Lumina) agreed within a second. The images are under
  `engine/spikes/out/sm/` (style samples, swatches, drafts, the Refine): the three style samples are the same scene in recognisably
  different hands, the swatches read their value at 512² on all three. Measured estimates into the specs. Owed: the author's look.

## 2026-10-16 23:31 — D90 / D91 pushed

- The day's work goes to origin/main at the author's request: 6f5e5f9 (D90 · UI0 + UI1), 5d7065d (UI2 + UI3), 3eeed73 (UI4 + UI6),
  3c21765 (UI5, D90 complete), d8555b1 (the sample scenes as settings), fb94623 (D91 · the sample-model choice, Lumina Image 2.0 and
  SD 3.5 Medium), and this entry. A contact sheet of `engine/spikes/out/sm/` (each model's style sample and three swatches) was looked at
  before the push: all three models render the scene and the presets sensibly.
- Still owed: the author's click-through of the new layout; the full swatch pack (64 look presets, now on the chosen sample model);
  a stall timeout in `fetch_weights.py` (the SD 3.5 Medium transfer hung ≈ 4 min at 8.25 GB and recovered by itself); Klein 4B's ledger
  sha256 (it shows `present`); not built in D90 — takes as a Catalogue group, the groups' "used by", Edit's Flatten, For contexts for
  profiles and styles.

## 2026-10-17 08:08 — D92 accepted · World holds every Generate template; subjects are Cast characters; no lettered tiles

- The author: "In Generate - all templates should have an entry in Story/World and World/Character should be connected to
  Generate/Subject (they are essentially the same thing). There should be no boxes with 2 letter abbreviations." Asked and answered:
  field presets and saved panels; Cast stays the characters' home and Generate's subject cards pick from it; the library is per project,
  seeded. → D92 (wave UI7): a World library of field presets (words + picture), saved panels in World, subject ↔ Cast character, no
  monogram tiles (glyphs, sample pictures made automatically, a busy glyph meanwhile).

## 2026-10-17 08:52 — D92 built (wave UI7) · the World library, saved panels in World, subjects are Cast characters, no lettered tiles

- **The World library** (`orchestrator/loom2/library.py`, `story/library.json`): entries `{id, field, name, text, source, group_id}` with
  `schema_version` and `revision` (409 when stale), seeded on the project's first read from `library_seed.json` (the built-in vocabulary,
  moved out of `fieldPresets.ts` — the one source; the frontend's glyph test imports the same file) plus the author's app-wide presets
  (`<state>/snippets.json`, merged once; descriptions kept, not seeded). Routes `GET /story/library`, `POST /story/library/entries` (an
  Undo re-adds with its id and place), `PATCH|DELETE /story/library/entries/{eid}`, `PUT /story/library/order`; `story.changed {kind:
  library}`. `/snippets` (GET / PUT) is gone — nothing else used it. Story · World: **Library** and **Saved panels** sections (panel rows
  with counts), the library grouped Look · Camera · Prompt · Subject as `PresetIcons` tiles with names and a ＋ Add per field; the World
  Inspector edits name and words (debounced, one PATCH at a time), shows the picture large, Make a new picture, Move earlier / later,
  Remove (Undo in the toast). Generate's tiles read the library; a field's + adds an entry (name asked inline, blank = the words); a tile's
  right-click: Add to / Remove from the field, Make a new picture, Edit in Story · World, Remove from the library.
- **Saved panels** are a record now (`SavedPanels` / `SavedPanel` with `thumb_asset_id`): the picture is sent when a panel is saved (the
  newest Generate result) and set by the finisher when a job made from the panel applied in this session lands (`origin.payload.
  saved_panel`); a client PUT without a picture keeps the server's. World lists them (Apply in Generate, Rename…, Delete with a confirm);
  Generate's tiles show the picture, else the sliders glyph.
- **Subjects are Cast characters:** a subject card has a row of Cast profiles as hero tiles (characters, then props; places later, as
  the scene or background) and "free subject"; a pick fills the description with the current version's stub (typed words stay) and
  records the profile mention, which carries the reference set and the LoRA as before (`mentions.py` unchanged but for a new
  `Mention.subject` — the card's index — so a stored recipe brings the link back). The card shows the hero, the name and ✕ unlink; the
  mention chip's × unlinks too. Cast: **Use as a subject in Generate** (Inspector, row menu).
- **No monograms:** `monogram` is gone; `PresetIcon.icon` is required; `fieldGlyph` draws every field and kind (sun, mask, horizon,
  framed horizon, brush, text lines, circle-slash, running / standing figure, bust, box, pin, sliders, palette …), the four built-in
  negatives are drawn, the anamorphic lens lost its "ana". A look entry added or re-worded without a swatch queues one (run now) on the
  sample model; its tile shows the field's glyph with a busy ring meanwhile. Styles without a sample show the palette glyph (not queued).
  New swatch scenes for subject action / pose (a grey mannequin), description and the lead text (on the lighthouse scene).
- Commands: `story.world.addEntry` (panel, context), `.entryPicture`, `.entryEarlier`, `.entryLater`, `.applyPanel`, `.renamePanel`
  (inspector, context), `.editEntry` (context: Generate's tile and saved-panel menus), `story.cast.useAsSubject` (inspector, context),
  `story.cast.openInStory` (context: a subject card's Cast tile); `story.world.remove` also removes an entry (Undo) or a saved panel.
- **Rig — the pack** (`scripts/swatch_pack.py`, the real route, Klein 4B, the pack's seed): 61 look entries of the seeded library,
  61 / 61 done in 205 s (first 30.3 s cold, ≈ 3.3 s a swatch warm), peak 12.01 GB, 0 failures; contact sheet
  `engine/spikes/out/sm/pack_sheet.png` looked at: the three lead-text swatches were literal (a blank panel, a poster of gibberish) — the
  `text` scene became "a lighthouse on a cliff. {value}" and they were remade (`--only`, 39.7 s, 11.98 GB, `pack_sheet_redo.png`), now
  fine. Installed into `.loom2_state/preset_icons`; the Lumina pack there before (64, 2026-10-16) is kept in
  `.loom2_state/preset_icons.before-20261017-085007/`. The dark moods (tense, melancholic, eerie, lonely) read alike — the mood scene is
  Settings › Samples' to change.
- Tests: offline 362 under full and open (`test_library_d92.py`: seed, snippets once, revision / 409, add / edit / remove / undo / order,
  routes, saved-panel pictures incl. the finisher, the subject link on the mention), Vitest 278 (`PresetIcons.test.tsx` no-text tiles,
  glyphs against the seed, `libraryStore.test.ts` tiles and the subject ↔ profile link, `latestResult`), lint 88, build clean, settings
  audit 230 clean, model literals and agents clean, contract regenerated; smoke 32 / 32 under full and open (new: the library entry →
  its picture → a Generate tile → Edit in Story · World; a subject linked to a character → the job's mention and references).
- Owed: the author's click-through and a look at the pack; Places as scene / background subjects; a picture album per entry
  (`group_id` is there); reorder by drag (the Move commands do it).

## 2026-10-17 12:53 — D93 accepted · Cast ↔ subject made real, in three phases

- Reviewed the D92 link on a copy of stubz001 (screenshots sent to the author): char01 has no hero, its stub is "char01", 0 references; the
  linked subject brings "@char01 · 0 images" and the prompt sends "char01"; no route sends a result back to an existing character; the
  prompt does not bind references to subjects. Suggested nine changes; the author: "Let's do it according to your plan" → **D93**:
  phase A (Cast from Generate, Add to character ▸, references bound per subject, an empty stub by default), B (a live character sheet,
  the version chip), C (places and props, a subject per speaker from a Dialogue node, Stage figures bound to characters).

## 2026-10-17 13:42 — D93 phase A built · Cast from Generate, Add to character ▸, references bound per subject, an empty stub

- **A1 · Cast from Generate.** A subject card linked to a character offers **"Give <name> a look"** while the current version has no hero
  and its mention gives no references, **"More looks for <name>"** after (command `gen.subject.cast`, the card's button; a final version:
  disabled with the reason). The description must say the look: empty or only the name → the field takes the focus and the card says
  "describe <name>'s look first". The run is the panel as it stands (its count, 4 by default) with origin `{suite generate, surface cast,
  ref profile, payload {version, group_id, profile_id}}`; the finisher already places on `payload.group_id`, so the results land on the
  version's candidates page — made on demand by `POST /story/profiles/{pid}/candidates` (`StoryStore.ensure_candidates`, which Expand now
  uses too; a final version 423). The toast offers "Open <name> in Cast"; "Go to origin" goes to the profile (`origin.storyPlace`).
- **A2 · Add to character ▸** on every result — the tile menu (Catalogue, Generate's grid, the loupe's More), the Inspector's one-asset
  "Add to character ▾": the profile the image was made for first under "made for" (its recipe's profile mentions, a subject-linked one
  first), then Characters, Props, Places; each `<name> · v1 ▸` with "as the hero" / "into the reference set" / "as a candidate" (commands
  `cat.addTo.hero|reference|candidate`, run on the entry's profile through the new per-item menu entry `{cmd, on}` — ContextMenu wraps the
  command's `when` and `run`). Server `POST /story/profiles/{pid}/versions/{vid}/add` (`StoryStore.add_assets`): from Unprocessed or the
  version's own candidates page an image **moves**; from any other page it is **copied** and the original stays (the reply and the toast
  say so); the hero joins the reference set as its cover; hero / reference are marked keep; a final version answers 423 with the reason.
  Cast's own "Make it the hero" now goes through the same route, so a hero picked from the candidates is in the reference set (before, it
  stayed on the candidates page and the mention gave 0 images — the stubz001 gap).
- **A3 · references bound per subject.** `mentions.py` keeps its fair turns, then puts each mention's images together (subject order;
  explicit references first) and stamps `skipped` (the set's images that did not fit). `graphs.subject_bindings` / `serialize_prompt`, per
  family by the spec's new `inputs.bind_refs` (on for Klein and dev; recipe `bind_refs` overrides): prose (Klein) — "Mara (reference
  images 1–2), a courier" with the bound images' "Image N shows" sentences dropped; JSON (dev) — the subject object gets `"reference":
  "reference images 2–4"`, `references` keeps only unbound notes. `/recipes/preview` gains `bindings` [{subject, name, refs, span, skipped}]
  and `bind_refs`; the card shows its slots ("refs 1–3", "· 1 left out"), the Preview lists each binding and what was cut (T8). The client
  sends the subject's index among the subjects actually sent (a blank card before it no longer shifts the link). Generate's preview now
  re-resolves when a mentioned set or profile moves (`group.changed` / `story.changed`).
- **A9 · the stub.** A new profile's stub starts empty (server and Cast); its placeholder asks for the look; a subject description that is
  only the linked profile's name warns under the field. Existing stubs are not rewritten.
- **Found on the way:** Edit's `.cand-strip` (absolute, edit.css) leaked onto Story's candidates once Edit had loaded — the candidates
  floated over the Cast header. Story's strip is `.story-cands` now.
- **Rig** (`scripts/d93_bind_rig.py`, Klein 9B KV, Draft 960 × 544, seeds 20261017–22; two characters made through the app — a hero each
  plus two looks with the hero as reference, added "into the reference set" with A2's route; stubs give a role, not a look; four slots →
  two each, one per set left out and said): **off** (D73 sentences) FaceSim own 0.269 / cross 0.128 (margin 0.141), right 5 / 6, one swap,
  and 4 of 6 renders had **three or four people** (the per-image sentences read as more women); **on** (bound) own **0.442** / cross 0.124
  (margin **0.319**), right **6 / 6**, no swap, always exactly two people. 137–143 s per image in both arms (four 576² references at
  Draft), peak 12.33 GB. The binding stays on by default (`inputs.bind_refs = true`). Sheet: engine/spikes/out/d93/sheet.jpg (local).
- **Tests:** offline **371** under full and open (`test_cast_subject_d93.py` +9: the span words, Klein prose split 2 / 2 with skipped,
  dev JSON with an explicit note kept, no binding in text mode or unlinked, the cut at the limit counted, the empty stub, add move / copy /
  candidate page / hero, the routes incl. 423 and 422, a casting run on the fake engine landing in the candidates; `test_mentions_d73`
  updated for the grouped order; parity fixture: two summary keys per t2i recipe, no graph changed; route snapshot +2); Vitest **292**
  (+14: the offer states, the warning and the ask, the slots and the Preview lines, the sent index, the menu order with "made for" and
  the per-item entries); lint 88; build, settings audit (232 / 0), model literals, agents check, OpenAPI current; smoke **33 / 33** under
  full and open (new: a character without a look gets candidates from Generate and one becomes its hero via Add to character ▸; D73's
  scenario now expects the grouped order). Screenshots: frontend/node_modules/.e2e/d93a/ (local).
- **Owed:** the binding measured on dev (JSON) — on by spec, not yet rigged; the author's click-through; phases B (the live character
  sheet, the version chip) and C (places and props, a subject per speaker, Stage figures bound).

## 2026-10-17 14:24 — D93 phase B built · a live character sheet, the version chip (costumes)

- **B4 · the sheet.** A profile version (schema **2**) holds `appearance` (the look), `outfit`, `colours` [{`hex`, `object`}] and `marks`
  instead of the one `stub`, plus a `label` (B5). A schema-1 record reads as schema 2 — `stub` → `appearance`, the label = the id
  (`ProfileVersion._from_stub`, `Profile._migrate`); nothing is written by a read, the next save writes the new shape. `POST
  /story/profiles` and the PATCH take the fields (`stub` still taken as the appearance); a final version refuses its sheet (422) but its
  label can change; a new version copies the sheet with a label of its own. **The rule** (`story.compose_sheet`, the client's copy
  `generate/sheet.ts`, both held to `tests/fixtures/sheet_compose.json`): appearance, the outfit (this shot's, else the sheet's — "wearing
  …" unless it says how it is worn), the bound colours as "`#C0392B` rain jacket" (a colour without an object is kept but not sent), the
  marks, this shot's line — joined by ", "; empty → the name. Expand's prompts, the LoRA captions and a mention's reference note read
  the composed sheet (`ProfileVersion.stub` is now that clause).
- **Cast** (`CastSheet.tsx` on the version page): version label, appearance, outfit, colour chips (a colour picker + what it colours,
  ＋ colour, ×), marks, and the clause as sent under it; every field shows at once and saves after a pause in one PATCH with the revision,
  one save at a time (`storyStore.setSheet`, B14's chain); the version selectors show "v1 · rain gear".
- **Generate: a linked subject copies nothing.** The card shows the sheet read-only (appearance · outfit · colours · marks, "edit in Cast"),
  then **outfit** (this shot only; the sheet's struck through when set) and **this shot** ("soaked, hood up"), position, action, pose. The
  card sends no words: `Mention.shot` {outfit, note} and the chip's `version` ride the profile mention; `mentions.py` composes the
  subject's description at preview and submit from that version's sheet, writes it into the subject and stamps it (`Mention.composed`;
  a stamped recipe is never composed again, so a re-run keeps its words while a new submit follows Cast). Saved and persisted panels
  keep the link; an old panel's copied stub in a linked card is adopted (the copy dropped, extra words → "this shot"). Unlink leaves the
  composed words as a free card's description; JSON mode writes them in. The casting run (A1) asks for the look in Cast. The Preview lists
  each linked subject as composed (`preview-composed`) and the version in its binding line.
- **B5 · the version chip** "v2 · winter ▾" on the linked card (a press menu: the versions with their labels, the one in use checked;
  picking the current one follows it again) — the mention moves to that version's set, so the references, the LoRA and the sheet follow;
  the hero shown is that version's. `BindingOut.version` added.
- Command: `gen.subject.editSheet` "Edit the character sheet in Story · Cast" (panel: the sheet's "edit in Cast"; context: the version
  chip's menu) — opens Cast on the profile at the version the card uses, the appearance focused.
- **No rig run:** the binding wording is unchanged and a linked subject's text is the sheet, which for phase A's measured profiles
  (appearance = their stub) is the words the rig sent.
- **The author's project:** a copy of `F:\loom2-projects\stubz001` opened in the e2e orchestrator (`POST /project/open`): char01 reads as
  schema 2 (appearance "char01", label v1), the copy's record unchanged by the reads, the original's sha256 unchanged; Cast and the linked
  card show it (the name-only warning). Screenshots: `frontend/node_modules/.e2e/d93b/` (local).
- **Tests:** offline **385** under full and open (`test_character_sheet_d93b.py` +14: the 8 shared cases, the migration without a write,
  the routes' round trip with revisions / 409 / 422 / labels on a final version, Expand and the LoRA caption, the composed subject stamped
  and not recomposed, the version picking sheet / references / LoRA, the preview route); Vitest **308** (+16, `sheet.test.tsx`: the shared
  cases, adoption, the chip's menu, the debounced one-at-a-time sheet save, a linked card that shows the sheet, sends no words and follows a
  Cast edit, the chip switching set / sheet / version); lint 88; build, settings audit (236 / 0), model literals, agents check, OpenAPI
  current; smoke **34 / 34** under full and open (new: an outfit edited in Cast shows on the linked card and rides the job's prompt; the
  chip's v1 takes v1's references; D92 / A1 scenarios updated — the look is written in Cast).
- **Owed:** the author's click-through; phase C (places and props, a subject per speaker, Stage figures bound); FLUX.2 dev's JSON binding
  on the rig (from phase A).

## 2026-10-17 15:14 — D93 phase C built · places and props, a subject per speaker, Stage figures bound to characters — D93 complete

- **C6 · a Cast place is the scene.** The Tree's scene has a row of Cast places as hero tiles (and "free scene"); a pick links the scene
  (`Tree.scene_link {profile_id, version?, note}`) — the words typed in the scene become this shot's line, the place's sheet shows read-only
  with its version chip, its slots ("ref 3") and "this shot" ("rain on the stones"); unlink leaves the composed words. The link rides on the
  profile mention (`Mention.scene`, `shot.note`, `version`): `mentions.py` composes the scene from the version's sheet + the line and writes it
  into `prompt_json.scene`, stamped `composed` like a linked subject. A place or a prop **wears nothing**: `compose_sheet(…, cls)` (and the
  client's `composeSheet`) send no outfit for them — two shared cases added to `sheet_compose.json`; Cast hides their outfit field.
- **C6 · a prop held by a subject.** A subject card's **holds ▸** (a press menu of the Cast's props; the chip "holds Compass ▾ · ref 3 ✕")
  links the prop to the card (`Subject.holds`, `Mention.held_by` = the card's index among the subjects sent); a card with only a prop is still
  sent. `mentions.py` puts the prop's clause under the subject's `holding` (one prop per subject); the serialiser says it per family. A prop
  can still be a subject of its own (D92).
- **The binding formats (extending A3; `BindingOut.role` subject · held · scene, `subject` None for the scene).** The images sit subject by
  subject, each holder's prop right after it, the place after the subjects (`_bind_order`). Klein prose: `subjects: Mara (reference image 1),
  …, Ines (reference image 2), a woman …, holding Compass (reference image 3), a brass compass …` and `scene: Warehouse (reference image 4),
  a dim harbour warehouse …`; unbound (bind off or no images): `…, holding a brass compass …` with D73's "Image 3 shows Compass, …". dev JSON:
  `"holding": {"description": "<clause>", "reference": "reference images 7–8"}` (a plain string unbound) and the scene string led by
  `Harbour (reference images 4–5), …`. The Preview lists the composed scene / "subject 2 holds · Compass: holding …" and each binding (T8).
- **C7 · a subject per speaker.** Flow's Dialogue and Shot nodes have **where** (`FlowNode.place_id`, a Cast place — the Inspector's select
  with the place's hero; the node card says "@ Warehouse"; `PATCH` answers 422 for anything but a place, a place deleted since stays until
  changed). **Make frame ▸** from a node (`makeFor.framePrefill`) now switches Generate to Tree mode and makes **one linked subject card per
  speaker** (Cast characters, in the order they first speak), the scene linked to the node's place, the node's title as the lead text. The
  version: the one the shot's stage binds to that character (C8's figure `version`), else the current one; the figure's pose goes into the
  card's pose (`stage/poseWords.ts`: "pointing", "walking" …). **The first line goes into its speaker's action as "saying <the line>"**
  (quote marks dropped) rather than "this shot": a line is something the character does in this shot, while "this shot" is composed into the
  description right after the sheet (outfit, marks — the look), where speech would read as appearance; the action is its own field in both
  families, and unquoted it is not lettered into the image. A Shot node without speakers keeps the cards and only links the place.
- **C8 · Stage figures bound to characters.** A figure (`StageObject.profile_id`, `version` — a pinned costume; old stages read, only a
  mannequin binds, `check` refuses others) picks a character in the **Inspector** (the Cast's characters as hero tiles, "no character", the
  version select when it has several, Unbind / Open in Cast) or by **right-click ▸ Bind to a character ▸** (Outliner and viewport); one
  figure per character (a second binding moves it); a duplicate is unbound; the **Outliner** shows the hero and the name on the figure's row.
  The Render tab sends the visible bound figures **left to right on screen** (`stage/figures.ts`: the camera's own projection, roll included)
  as `StageShot.mentions` (`figure` = the object id); `mentions.resolve_figures` gives each its version's reference images after the deck's
  own, within the method's room (clay: the model's references less the pass; refcontrol: one), in turns then figure by figure, stamps them
  and composes each sheet. The prompt: `From left to right in image 1: figure 1 is Mara (reference images 2–3), a courier; figure 2 is Ines
  (reference image 4), a lighthouse keeper.` (unbound: the same without the ranges, D73's sentence per image). `/recipes/preview` returns
  `params.figures` and `params.ref_list` — the deck shows the figures' slots ("fig 1 · Mara" on images 2–3) and a line per figure. **Make
  frame ▸ in Stage** from a shot binds the owner node's speakers to the stage's figures in screen order when the counts match, else a toast
  says how to bind them. `StageShot.bind_refs` overrides the spec (`inputs.bind_refs`, on).
- **Commands:** `gen.subject.unhold` "Put the prop down" (panel: the chip's ✕; context: the holds ▸ menu), `gen.scene.editSheet` "Edit the
  place in Story · Cast" (panel: the scene sheet's "edit in Cast"; context: its version chip's menu), `stage.figure.unbind` "Unbind the
  character" and `stage.figure.openInCast` "Open the character in Story · Cast" (inspector: the figure's row; context: Bind to a character ▸).
  The picks themselves (place tiles, holds ▸ entries, the figure's tiles and submenu) are item entries, as the version chip's are.
- **Rig** (`scripts/d93c_stage_rig.py`; a copy of phase A's scratch project → `F:\loom2-projects\d93c-stage-20261017-144418`, the original
  untouched; ST3's acceptance passes — a walking figure left, a pointing one right — uploaded to a new stage; the figures bound to Mara and
  Ines (sheets that say a role, not a look); clay on Klein 9B at Draft 1280 × 720, three references after the pass; seeds 20261017–22):
  **none** (no binding, the figures by their words) own 0.041 / cross 0.044, right 0 / 6, ≈ 11 s warm; **off** (bound, D73's sentences, no
  ranges) own 0.115 / cross 0.054 (margin 0.061), right 2 / 6, 3 swapped, and in 5 of 6 a grey mannequin stayed grey or extra people
  appeared (4 in one frame), 26–130 s; **on** (ranges) own **0.251** / cross 0.044 (margin **0.207**), right **5 / 6**, 1 swapped, always
  exactly two real people, 65–79 s. Peak 12.6 GB. The binding stays on by default (no flag needed). Sheet: engine/spikes/out/d93c/sheet.jpg
  (local).
- **The author's project:** a copy of `F:\loom2-projects\stubz001` opened in the e2e orchestrator (`POST /project/open`): char01 reads
  (schema 2, v1), no nodes or stages; its profile and world unchanged by the reads (the copy gained D92's seeded `library.json`, as before),
  the original's story records' sha256 unchanged; Cast and a linked card show char01 as in phase B.
- **Tests:** offline **398** under full and open (`test_places_props_figures_d93c.py` +11: no outfit on a place, the scene composed and
  bound in Klein prose and dev JSON, a held prop in both families and unbound, a free holder and no recomposition, `place_id` and its 422s
  with an old node file, a figure binding and an old stage, figures within clay's room left to right / off / the deck first / refcontrol one /
  refusals, the plan's `figures` / `ref_list` and the compiled graph, the preview route; +2 shared composition cases; `test_mentions_d73`
  excludes the new fields); Vitest **323** (+15: `placesProps.test.tsx` the scene tiles, link / chip / slots / unlink / round trip, holds ▸
  and its recipe, JSON's "holding", Make frame's cards, the Preview lines; `figures.test.ts` the screen order, the mentions, the pre-binding;
  `FigureBinding.test.tsx` the Inspector tiles, one figure per character, the tag, the menu, Make frame ▸ in Stage; `makeFor.test.ts` the
  speakers' cards, versions and poses); lint 88; build, settings audit (239 / 0; `Mention.lora` / `lora_available` allow-listed as the stamps
  they are — the resolver now carries them by copy), model literals, agents check, OpenAPI regenerated; smoke **36 / 36** under full and
  open (new: a Dialogue node's where → Make frame → two linked cards and the place → holds ▸ → the job's prompt carries the scene, the cards
  and "holding" with their ranges; a figure bound in the Inspector and by right-click → the Outliner, the deck's figure slots → the frame's
  job carries the figures left to right). Screenshots: `frontend/node_modules/.e2e/d93c/` (local).
- **Owed:** the author's click-through; FLUX.2 dev's JSON binding on the rig (from phase A, now with "holding" and the scene); refcontrol
  with a bound figure on the rig (one image, unmeasured); a version pin for a speaker on the Flow node itself (only the stage's figure pins
  one today); links to profiles of another project stay in a persisted panel after a project switch (pre-existing since D92: the preview
  says "mentioned profile … does not exist" until the card is unlinked).

## 2026-10-17 15:28 — D93 follow-up · Generate drops links remembered from another project

- Phase C's report named a gap open since D92: Generate's panel is remembered across projects, so a subject / held prop / scene linked to
  another project's Cast profile — or an @mention of another project's album group — stayed in the panel and the preview refused
  ("mentioned profile … does not exist") until the card was unlinked by hand. Now, when Generate opens a project, `withoutForeignLinks`
  drops every link the project lacks (a card keeps its words: its "this shot" line joins the description; the scene keeps its line) and a
  toast says how many. Vitest 324 (+1), smoke 36 / 36 under full and open (the @mentions scenario failed once under `open` in a full run
  and passed alone 4 / 4 and in the next full run — its known flakiness, D89; the cleanup writes nothing when nothing is foreign).

## 2026-10-17 16:18 — The owed items · fetch stall watchdog, verified ledger, Edit's Flatten, groups' "used by", the library drag, speaker version pins

- **Fetch stall timeout** (D91's SD 3.5 Medium transfer sat at 8.25 GB for ≈ 4 min with the connection open): `scripts/fetch_weights.py` runs
  each `hf_hub_download` in a child process (a thread on a dead socket cannot be stopped) under `watch()`: no growth of the run's staging
  folder (the `.incomplete` + the file) for `--stall-s` (default 120) → the child is killed and started again, resuming from the partial
  file, at most `--stall-retries` (3) times, each restart logged; then it gives up (`Stalled`). sha256 and the ledger unchanged. Offline
  `test_fetch_stall.py` (6: fake clock — a stall restarts and resumes, gives up after the retries, slow growth is not a stall; a real thread
  writing a partial file that hangs, resumed to the exact size); a live child fetched a small Hub file once.
- **The ledger: no `present` left.** Nothing put on disk before the ledger existed was in `roster.index.json` — 19 entries, not only Klein 4B.
  New `scripts/ledger_verify.py` (orchestrator venv; background I/O priority, read-only) hashes every `present` roster file, compares it
  with the Hub's LFS oid (`get_paths_info`) and appends the entry the fetch tools write (+ `hf_sha256`, `hf_match`; a mismatch would be
  recorded unverified). **Klein 4B matches the Hub** (`ec3d4e73…a343`). 15 others match too: FLUX.2 dev fp8mixed, Mistral 3 small, the
  FLUX.2 VAE, Klein base 4B, Klein 9B / base 9B / 9B KV, Wan 2.2 Animate, clip_vision_h, lightx2v I2V, Qwen-Image-Edit 2509, Qwen 2.5 VL
  7B, the Qwen VAE, the 2509 Lightning and angles LoRAs. Five roster sources were stale and are fixed in `roster.py` (the files on disk
  are those files, by sha256): Klein 9B / base 9B / 9B KV live in BFL's gated repos (`black-forest-labs/FLUX.2-klein-9B`, `…-base-9B`,
  `…-9b-kv`; Comfy-Org's 9B repo holds only the encoder and the VAE), the Lightning LoRA in its repo's `Qwen-Image-Edit-2509/` folder,
  the angles LoRA is the repo's Chinese-named file (renamed on disk). Recorded without a Hub comparison: SAM 3 (gated, this token has no
  access), the FLUX.2 small decoder and Flux2TurboComfyv2 (no repo in the roster). 0 mismatches; the roster reports `verified` after a
  rescan. A copy of the ledger from before: the session scratchpad.
- **Edit › Flatten image** (owed since UI6): `edit.layer.flatten` in the canvas menu's Layer ▸ and the layers footer's More ▾ (the layer
  menu). The store syncs (D70), asks the server for its exact flatten as raw RGBA (`POST /documents/{id}/export` gains `format: "raw"` —
  the same `OpenDocument.flatten` Save to Catalogue and the PNG export run) and makes it the one full-canvas raster layer, named after the
  bottom pixel layer (else "Background"), lineage kept; hidden layers are discarded (the toast says how many, with Undo); one history step
  storing the stack only — the old layers' canvases stay in the maps (`gcPixels` keeps what a stack names), so Undo is cheap at any size;
  an edit during the fetch aborts it. Disabled on one plain full-canvas layer. `test_flatten_d90.py`: a stack of every kind (isolated masked
  group in screen, a clipped multiply, overlay, an adjustment, a filter, a masked soft-light layer at an offset, a hidden one) on a colour
  and a transparent background — raw == `od.flatten()` == the PNG, and the one-layer document flattens **bit-identically**, Save to
  Catalogue's file too. Headed check (`edit_headed_check.py`) not run: 1420 was free, but the other worker was measuring on the GPU and the
  check drives WebGPU in a visible Edge; the change adds no rendering path (the layer is server pixels), and the smoke runs it on WebGL2.
- **A press-menu bug found on the way** (D55, `frame/ContextMenu.tsx`): a menu too tall for either side of its button is placed over it,
  and the release of a plain click chose the entry under the pointer — a click on the layers footer's More ▾ ran *Solo*. A release under
  4 px from the press is now a click (the menu stays open); press–drag–release still chooses.
- **"Used by" on Catalogue groups** (D92 §4.2): `usedby.py` computes, per request, what names a group — a Cast version's reference set /
  candidates, a style's samples, a Flow node's board, a Stage's album page, a library entry (read without seeding) — as `GET /groups/used-by`
  (`?ids=…`, none = every used group; `deep` adds the groups inside, what a delete takes). The album store keeps the map (reloaded with the
  tree and on `story.changed`); the card Inspector has a Used by section ("Mara v1 · references; Style · Ink wash", each a link that opens
  Cast at the version, World at the style or the library, Flow at the node, the Stage), the page shows "used by: Mara v1 · references +1"
  top left (the first user, all in the tooltip); Delete group… (Inspector, card menu, Places) says who loses its images (deep) and Ungroup
  asks only when the group is used.
- **World › Library drag reorder**: a tile dragged within its field's row (pointer events, 5 px threshold, a ghost, Esc cancels) shows an
  insertion line before / after the tile under the pointer and drops through `PUT /story/library/order` (`moveToInField`; other fields
  keep their places; the row reorders at once). Move earlier / later stay; Help lists the gesture.
- **Flow nodes pin a version per speaker** (D93 C left it): `FlowNode.speaker_versions` (profile id → version id, absent = current; old node
  files read; PATCH 422 for a non-character or a version it lacks, a pin deleted since stays until changed). The node Inspector's
  **Speakers**: a chip per speaker ("current ▾" / "v2 · rain gear ▾", a press menu of the versions), with "the shot's stage binds v1 — the
  Stage binding wins" when the bound shot's stage binds that character to another version. Make frame ▸ in Generate uses
  `speakerVersion` (a figure bound with a version > the node's pin > current; the toast names an overridden pin); Make frame ▸ in Stage
  gives a newly bound figure the node's pin (an already bound figure keeps its own).
- **D90 §5 "For" contexts for profiles and styles — evaluated, not built:** covered without a chip — a profile's more candidates are Cast's
  Expand and, from Generate, D93 A1's casting run on a linked card (origin `cast`, results into the version's candidates, Go to origin →
  Cast; Cast's "Use as a subject in Generate" opens it), a style's sample is World's "Make a sample image" (origin `style`, into its
  samples). Takes stay a list (an asset lives on one page, D34). Both noted in `proto01_UI/02`'s status line.
- **Tests:** offline **411** under full and open (+13: `test_fetch_stall` 6, `test_flatten_d90` 1, `test_used_by_d92` 4,
  `test_speaker_versions_d93` 2; route snapshot + `GET /groups/used-by`); Vitest **341** (+17: `flatten.test.ts` 5, `groupUsers.test.tsx` 5,
  `libraryDrag.test.ts` 5, `makeFor` +1, `FigureBinding` +1); lint 88; build clean; settings audit 239 / 0, model literals, agents check,
  OpenAPI current (regenerated, `schema.d.ts`); smoke **38 / 38** under full and open (new: Flatten image from the canvas menu — one layer,
  the raw flatten byte-equal before / after, Save to Catalogue from it, Undo back to three, More ▾ by a click lists it and chooses nothing;
  a Cast version's group says "used by" on its page and in the card's Inspector, Delete group… warns, the link opens Cast). Screenshots
  (a temporary spec, deleted): `frontend/node_modules/.e2e/owed/` (local) — flatten-menu / -after, usedby-page / -inspector /
  -delete-confirm, library-drag / -after-drop, speaker-chip-menu / speaker-chips.
- **Owed:** the author's click-through; the headed Edit check of Flatten on WebGPU when the GPU is free; SAM 3's Hub hash (needs access to
  the gated repo); a stage-wins hint on the Flow node card itself (the Inspector says it).

## 2026-10-17 18:03 — Owed rig measurements · FLUX.2 dev's JSON binding (off by default now), exact pose with bound figures, a mood scene that shows the mood

- **1 · FLUX.2 dev's JSON binding** (owed since D93 A). `scripts/d93_bind_rig.py` gained `--source` (copies a project that already holds
  the characters — phase A's `d93-bind-20261017-131210`, untouched — to `F:\loom2-projects\d93-bind-flux2-dev-fp8mixed-20261017-153415`
  with its `_state-…`), `--turbo` and `--sheet`; the same Mara and Ines (a hero + two looks each, sheets that give a role), dev fp8 +
  Turbo (Generate's default, 8 steps) at Draft 960 × 544, seeds 20261017–22. dev takes ten references, so both sets go in whole: off =
  D73's `references: [{index, note}]` (six notes), on = `"reference": "reference images 1–3"` / `"4–6"` in the subject objects.

  | arm | FaceSim own | cross | margin | right | swapped | two people | extra people | s / image | peak |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | off (notes) | **0.561** | 0.390 | **0.171** | **4 / 6** | 2 | 6 / 6 | 0 | 302–557 (449) | 14.47 GB |
  | on (ranges) | 0.350 | 0.575 | −0.225 | 2 / 6 | 4 | 6 / 6 | 0 | 484–577 (527) | |

  dev keeps **both identities in every frame in both arms** (own ≈ 0.70–0.85 whenever the two stand on their own side) and never adds a
  person — Klein's phase-A failure (D73's per-image sentences read as more women) does not happen on dev. What decides the score is only
  who stands left: binding put Mara on the right in 4 of 6 (one blend in each arm: a red-haired Mara off, a capped Mara in Ines's jacket
  on). **Decision: `inputs.bind_refs = false` for dev** (`models/specs/flux2.toml`) — the ranges do not help there; a recipe's `bind_refs`
  still turns them on, and with them off dev's held props and places go unbound too (D73's notes, "holding" as a plain string; those two
  were never rigged on dev). Klein keeps the binding (phase A: own 0.27 → 0.44). The tests that asked dev for the binding now ask the
  recipe (`test_cast_subject_d93`, `test_character_sheet_d93b`, `test_places_props_figures_d93c` — the DEV pick no longer needs the flag;
  +1 assert that dev's default is unbound); the parity fixture's two dev summaries say `bind_refs: false` (graphs unchanged).
  **Timing note:** 290 s for the first image rising to 560 s (8 steps at 30 → 62 s/it) with six 576² references, the engine reloading the
  encoder, VAE and transformer for every job ("RAM pressure cache"); the GPU's 3D engine was idle while sampling and the disks quiet — dev
  with many references is far off its 66–110 s single-image figure and worth its own look. Sheet: `engine/spikes/out/d93/sheet_dev.jpg`
  (local), the line in `runs.jsonl`.
- **2 · exact pose with bound figures** (owed since D93 C). `/capabilities.stage.methods.refcontrol`: Klein base 9B + the RefControl pose
  LoRA, weights verified, **max_refs 1**. `scripts/d93c_stage_rig.py` gained `--method` / `--sheet` and per-side means; the copy of phase
  A → `F:\loom2-projects\d93c-stage-refcontrol-20261017-171246`; ST3's pose pass (walking left, pointing right), the figures bound to Mara
  and Ines, 1280 × 720, seeds 20261017–22. **What fits:** one image — figure 1's first reference as image 2; figure 2 gets none and is said
  by its words. `none` needs a reference too (the method refuses none): Mara's hero in the deck, as the Render tab took it before C8.

  | arm | own | cross | margin | right | swapped | own left (Mara) | own / cross right (Ines) | s / image | peak |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | none (deck + words) | 0.146 | 0.105 | 0.041 | 0 / 6 | 2 | 0.303 | −0.012 / 0.252 | 118–142 (124) | 11.37 GB |
  | off (bound, no range) | 0.146 | 0.105 | 0.041 | 0 / 6 | 2 | 0.303 | −0.012 / 0.252 | 118–124 (120) | |
  | on ("figure 1 is Mara (reference image 2)") | 0.147 | 0.102 | 0.046 | 0 / 6 | 1 | 0.313 | −0.019 / 0.252 | 117–118 (118) | |

  none and off send the same prompt with the same image 2, and the renders are identical (deterministic); on is within noise. The poses
  are exact in every frame, but **both figures become Mara** (black bob, grey coat; the right face is nearer Mara's hero than Ines's) — one
  reference slot cannot carry two characters, bound or not. **Decision: no flag.** The binding neither helps nor hurts on exact pose, and
  there is no per-method switch to set: `graphs.stage_binds` reads the method model's `inputs.bind_refs`, which for Klein base 9B also
  governs its t2i binding (a per-method flag would be code — `spec.py` + `graphs.stage_binds` — not done here). What would help is saying
  it: exact pose shows only figure 1's character; for two bound characters use clay (phase C: right 5 / 6). Sheet:
  `engine/spikes/out/d93c/sheet_refcontrol.jpg` (local), log `run_refcontrol.log`.
- **3 · the mood swatches** (the author: tense, melancholic, eerie and lonely look alike). New `scripts/mood_swatch_scenes.py`: a temporary
  orchestrator (own state, scratch project), per scene `PUT /settings` (Settings › Samples' mood scene) and the eight built-in moods through
  `POST /preset-icons/make` on the default sample model (Klein 4B, 512², 2.6 s a swatch warm, device peak 13.2 GB), seeds 90 (the pack's),
  91, 92. Scores are means over the three seeds; *dark* = the four dark moods. D89's proxies (layout = 1 − correlation of 32² z-normalised
  greyscale, colour = ΔE of 8² Lab) plus two structural ones, added after the sheets disagreed with the layout score (the z-normalisation
  turns the faint differences between near-black frames into large distances; `--rescore` recomputes all from the saved PNGs): 1 − SSIM
  (128² grey, 7² windows) and the mean absolute luminance difference (32², 0–255).

  | scene | layout (8) | colour (8) | layout (dark) | colour (dark) | 1 − SSIM (8) | **1 − SSIM (dark)** | lum (8) | **lum (dark)** |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | corner (before): "an empty street corner, {value} mood" | 0.557 | 195 | 0.213 | 106 | 0.656 | 0.294 | 73.4 | 10.4 |
  | **face**: "close-up portrait of a person's face and shoulders, {value} mood, the expression and the light show it" | 0.279 | 97 | 0.137 | 98 | **0.700** | **0.494** | 54.3 | 18.6 |
  | room: "a single person in a sparse room by a window, full figure, {value} mood, the posture and the light show it" | 0.261 | 94 | 0.239 | 63 | 0.512 | 0.360 | 48.9 | 20.5 |
  | landscape: "a wide open landscape with a road under a big sky, {value} mood, the weather and the light show it" | 0.195 | 162 | 0.126 | 79 | 0.476 | 0.290 | 59.1 | 30.1 |
  | quay: "a lone figure on a harbour quay, wide shot, {value} mood, the weather, the light and the posture show it" | 0.143 | 189 | 0.075 | 100 | 0.405 | 0.237 | 56.2 | 27.2 |

  On the sheets (`engine/spikes/out/mood/sheet_s90|91|92.png`, local) the corner's four dark moods are one dark corner (s90: the same
  picture four times) — its high layout score is that artefact; the corner changes only brightness and colour. Landscape and quay change
  the sky (all four dark ones a storm), room the light around a dark figure. **The face separates them**: a scowl (tense), a sad downcast
  face (melancholic), a teal half-lit face in near darkness (eerie), and the bright four by their smiles and light — expression and light
  together, readable at tile size, and still a mood rather than a subject (the light carries the atmosphere). Its nearest pair stays
  melancholic ~ lonely (1 − SSIM 0.12–0.27, the corner's 0.08–0.26). **Decision:** `config.SWATCH_PROMPTS["mood"]` = the face scene
  (`test_preset_icons_d90`'s blank-is-the-default assertion follows it); `pytest -k "preset or sample or swatch or library or settings"`
  41 passed.
  **The author's pack remade:** `.loom2_state/preset_icons` copied to `preset_icons.before-20261017-175624` first; `scripts/swatch_pack.py
  --only` with the eight moods (Klein 4B, seed 90, the new default scene): 8 / 8 in 36.5 s, peak 11.98 GB, installed through
  `PresetIconStore.store_from` — index 67 entries, the same keys, only the 8 mood entries and files changed, every entry has its file.
  Sheet: `engine/spikes/out/sm/pack_sheet_redo.png` (local).
  **The author's settings pin the old scene:** `.loom2_state/app.json` holds `settings.samples.swatch_prompts.mood = "an empty street
  corner, {value} mood"` — the old default saved verbatim with the rest of Samples (not an edit of theirs), and a stored entry wins over
  the default (`SampleSettings._swatches`), so a mood swatch made from the app (Make a picture, a new World entry) still uses the corner
  until that entry is blanked in Settings › Samples. Not changed here (app state, the author's setting). Their sample model is also set to
  Lumina 2 (`settings.samples.model_id`): new swatches from the app run on Lumina, the pack on Klein 4B.
- **Files:** `orchestrator/loom2/models/specs/flux2.toml` (dev `bind_refs = false`), `orchestrator/loom2/config.py` (the mood scene),
  `orchestrator/tests/test_cast_subject_d93.py`, `test_character_sheet_d93b.py`, `test_places_props_figures_d93c.py`,
  `test_preset_icons_d90.py`, `orchestrator/tests/fixtures/graph_parity.json`, `scripts/d93_bind_rig.py`, `scripts/d93c_stage_rig.py`,
  `scripts/mood_swatch_scenes.py` (new); outputs under `engine/spikes/out/d93`, `d93c`, `mood`, `sm` (local). Not committed.
- **Tests:** offline **411** under full and open; model literals 0, settings audit 239 / 0. Smoke not run (its binding scenarios use Klein
  4B and clay, untouched by the dev flag).
- **Owed:** D93's row in 13 still says the binding is on for dev; dev's slowness with six references (above); a per-method binding flag or
  an "only figure 1's character" hint for exact pose; the author blanks Settings › Samples' mood scene to get the face for new swatches.

## 2026-10-17 18:04 — Follow-ups to the 18:03 measurements · saved built-in scenes follow the built-in, exact pose says its limit

- **The author's saved mood scene was the old default verbatim:** Settings › Samples saves the whole scene map, so an untouched scene pinned
  the built-in of its day (`app.json` held "an empty street corner, {value} mood") and the new face scene would never reach the app.
  `config.PAST_SWATCH_DEFAULTS` lists every earlier built-in per field; a stored entry equal to one reads as the current built-in, an
  author's own scene stays (their style prompt — their own text — is untouched). Their app state was not edited; it reads correctly.
  Their sample model is Lumina 2 (D91), so swatches made from the app run on Lumina while the installed pack is Klein 4B's.
- **Exact pose has one reference slot:** with two bound figures it drew both as figure 1's character (0/6 right in every arm). The Render
  deck now says which figures only get words and points to Clay for several characters.
- **D93's row amended** (decision log): the binding is off by default on FLUX.2 dev, on for Klein; the exact-pose limit.
- **Owed:** FLUX.2 dev ran at 290–560 s per image in the 18:03 run (its usual 66–110 s) — the engine reloaded every model per job under
  "RAM pressure cache" with the GPU idle; to be looked at on its own.

## 2026-10-17 18:55 — Spike E21 started · two characters in one animated shot by layers

- The author: the goal is animation, not images; each character animates well alone, none of our models animates two characters from
  one prompt — "generate each part of the image separately … then merge it, and perhaps sync the lights and shadows with i2i". Agreed
  with one change: keep the characters apart *through* the animation (a merged still is as hard to animate as a generated pair). E21
  compares, on one static-camera two-character dialogue shot blocked in Stage (Mara and Ines, scratch project): **(a)** one composite still
  → one image-to-video clip; **(b)** layers — a plate from the set without figures, each character inpainted into its own copy of the plate
  at its figure's mask / pose with its references, each copy animated alone, merged over the steady plate by the difference to the plate
  (character + its shadow) cleaned by its mask, depth order from Stage; **(b2)** (b) plus a light video-to-video pass to unify the light.
  Measured: identity per character (FaceSim per frame vs a single-character clip), swaps, seam visibility, background flicker, time per
  shot, peak VRAM. The result decides a D-number; nothing is built into the app before it.

## 2026-10-17 20:26 — Spike E21 result · two characters by layers: it works, (a) stays the default, layers as the fallback, no v2v

- **Setup** (`engine/spikes/e21_passes.mjs`, `e21_layers.py run|score`, `e21_score.py`; outputs `engine/spikes/out/e21/`, local). A
  static two-shot blocked on the E10 page (the `room` set, camera (0, 1.05, 4.3) fov 30°, Mara `stand` at x −1, Ines `arms_crossed` at
  x +1); scratch copy of D93 C's project → `F:\loom2-projects\e21-layers-20261017-190731` (+ `_state-…`), a private orchestrator; seeds
  20261017–19. Every clip is Wan 2.2 I2V Draft through the app (832×480, 81 f @ 16 fps, Lightning 2 + 2).
  **(a)** Stage clay (Klein 9B) with both figures bound with ranges → one I2V clip with both actions in the prompt.
  **(b)** plate = clay on the empty set's pass (seed 1 drew a man, seed 2 empty, picked by a face check) → each character into its own
  copy (the plate with that figure's mannequin as image 1, hero + first look as images 2–3, Klein 9B Fill-Match from `build_inpaint`
  with the references chained on as `build_t2i` does — the app's inpaint takes no references; mask = silhouette + 24 px + a shadow
  ellipse under the feet) → each copy animated alone (one-character prompt) → per-frame SAM 3 masks → numpy merge over the steady plate
  (colour lock on a ring, alpha = max(SAM, difference to the plate inside SAM ∪ silhouette ∪ shadow zone), ≈ 5 px feather).
  **(b2)** (b) + Wan low-noise expert + Lightning low over the VAE-encoded merged clip from σ 0.3 (shift 1, denoise 0.3), conditioned on
  the merged first frame — core nodes. **(banim)** (b) with Mara by Wan Animate (E19's graph) on a pose sequence drawn from the Stage
  keypoints (stand → point, two beats), 2 seeds.

  | arm | Mara own (min) | Ines own (min) | swaps | bg flicker | seam grad ratio | band step | shadow kept | s / shot |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | (a) | 0.203 (0.083) | 0.257 (0.143) | 0 | 1.67 | — | — | — | 311–333 |
  | **(b)** | **0.246** (0.129) | **0.313** (0.216) | 0 | **0.00** | 0.93–0.95 | 4.2–4.8 | 0.83–0.91 | 577–692 |
  | (b2) | 0.197 (0.101) | 0.270 (0.188) | 0 | 0.94 | 0.92–0.95 | 5.0–6.3 | 0.89–1.02 | 877–956 |
  | (banim) | 0.204 (0.126) | 0.300 (0.216) | 0 | 0.00 | 0.93–0.95 | 4.2–5.9 | 0.80–0.90 | 735–742 |
  | ceiling: each layer alone | 0.245 (0.127) | 0.309 (0.211) | — | 1.0–2.0 | — | — | — | — |

  FaceSim on every 8th frame vs the hero (faces ≈ 40 px: advisory, and frontal faces score higher, which favours (b)); seam = luminance
  gradient in the 0.05–0.95 alpha band of the merged clip ÷ the same pixels in the layer clip, band step = |merged − layer| there (0–255);
  flicker = temporal luminance std over the background outside every figure / mask / shadow zone; shadow kept = darkened share of the
  feet ellipse, merged ÷ layer clip. Steps: clay still 69–78 s (10.9–11.8 GB), plate 11–19 s, copy 16 s warm (53–79 cold, ≤ 12.3 GB), Wan
  I2V 232–264 s (12.7 GB), Animate 285–326 s (13.5 GB), SAM 3 masks 17–21 s (1.8 GB), merge 16 s CPU, v2v 239–307 s (13.2 GB). No OOM.
- **What it showed.** (a) held both identities on this shot (3 / 3, no swap). The two face each other, so the eye lines read as a
  conversation, but the action split is loose: Mara's gesture fades after 1–2 s in 2 / 3 seeds, the nod is barely visible, and the
  background breathes. The stills are the risk (Ines in olive instead of yellow in 2 / 3). (b) equals each character's own clip
  (±0.004), with no swap, a steady background, seams invisible at Draft, each action controlled by its own prompt, and one character
  can be re-taken alone. **But** both characters stand frontal and look at the camera (each layer knows nothing of the other — a
  line-up, not a conversation). The shadows are round blobs the mask ellipse allowed, not cast from the window light. The plate kept two
  set blocks as grey clay. And it takes twice the GPU time. (b2): σ 0.3 changes nothing visible, costs 4–5 min, brings the flicker
  back and lowers FaceSim by ≈ 0.05 — the shared plate already gives every layer the same light. (banim): it follows the drawn pose (it
  even turns Mara towards Ines), but the gestures are smaller than I2V's and FaceSim is lower (0.204 vs 0.251 on the same seeds).
- **SAM 3 video tracking is in v0.39.0 but fails with our `sam3.pt`:** `SAM3_VideoTrack` crashes ("can't assign a tuple to a
  torch.HalfTensor" — `SAM3Tracker.track_video` returns a tensor where the node expects a dict; it looks written for SAM 3.1 multiplex
  weights). The fallback, `SAM3_Detect` on every frame with one box around the figure's area (AI Select's box path), followed the
  gesturing hands cleanly. No node added, no engine patch.
- **Recommendation (for the D-number):** keep (a) as the default for a static two-shot with the characters apart. Build (b) without the
  v2v pass as the tool for when (a) fails, or when each character's action must be controlled or re-taken. The app would need
  references on the inpaint graph, a plate render (the Stage camera with the figures hidden), per-frame SAM 3 box masks (VideoTrack once
  it works with our weights), the compositor (≈ 16 s of CPU per shot), the figure's facing written into the copy prompt (the eye line),
  and a shadow shaped by the light rather than an ellipse. Not v2v. Animate only when the blocking must be exact.
- **Not done:** no nod metric (no head pose); (a)'s room is a different generation from (b)'s plate, so there is no shadow number for
  (a); 3 seeds (Animate 2). The engine/spikes/out/e21/report.md the brief asked for was not written (the tables are here and in
  `results.jsonl`). Files: `engine/spikes/e21_passes.mjs`, `e21_layers.py`, `e21_score.py` (new, not committed); outputs: `sheet_a.jpg`,
  `sheet_b.jpg`, `sheet_b2.jpg`, `sheet_banim.jpg`, `a_|b_|b2_|banim_|layerMara_|layerInes_seedN.mp4`, `compare.mp4` (seed 20261017),
  `results.jsonl`, `state.json` (local, ≈ 0.9 GB with the frames).

## 2026-10-17 20:40 — D94 · two-character shots are one Stage still, animated once (E21 arm a)

- The author watched E21's `compare.mp4` and chose arm (a): "the characters are facing each other and the shadows are also pretty accurate
  (they are not blobs). That should be our way forward." How it was made: Stage blocking (room, fixed camera 1280×720 fov 30°, Mara at x −1
  turned +35°, Ines at x +1 turned −35°, both bound to their characters, D93 C) → Render frame by Clay reference on Klein 9B with the
  references bound per figure → Wan 2.2 I2V Draft (832×480, 81 frames, Lightning) with a prompt naming both actions. The facing came from
  the figures' turn; the shadows from Klein rendering the room and the people together. → **D94**; the layers route stays the documented
  fallback. Weak points to work on: costume drift in the still (Ines's olive jacket in 2/3), the listener's action fading, the background
  breathing.

## 2026-10-17 20:55 — Spike E22 started · complex action for both characters: one shared clip vs layers

- The author, after D94: E21's actions were small (one talks, one stands), the easy case for one shared clip. E22 gives **both
  characters a complex, different action at the same time** and compares **(a)** one Stage still (figures bound and turned towards
  each other, Clay reference) animated once with both actions in one prompt, against **(b)** layers — the same blocking, each character
  put into its own copy of the plate *facing as blocked* (E21's line-up fixed), animated alone with its own action, then stacked over the
  plate with a plain alpha (no colour matching, no shadow work, no video pass — "we can refine that later"). Measured: does each character
  do *its* action (motion and path per character, by eye on sheets), identity per character, swaps, time per shot. D94 stands until E22
  says otherwise.

## 2026-10-17 21:22 — SAM 3 verified against the Hub

- The author's request for `facebook/sam3` was granted. `sam3.pt` on F: (3 450 062 241 bytes) has the Hub's LFS sha256
  `9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e` — the ledger's hash recorded at 16:18 without a comparison now carries
  `hf_sha256` / `hf_match: true` like the other sixteen. Every roster file on disk is now verified against its source except the two with
  no repo in the roster (flux2-small-decoder, flux2-turbo-lora). Ledger backup in the session scratchpad. The token needed nothing new.

## 2026-10-17 22:17 — proto01_animate · the clay-animation idea documented for the author's review

- The author proposed animating each character from Stage's clay animation through Wan Animate, layer by layer, in 77-frame batches,
  then post-processing (a v2v pass or per-frame i2i) — and asked for a review and a document before building. Written:
  `.docs/proto01_animate/00-README.md`, `01-clay-animation.md` (the eight steps reviewed: the background generated *from* the Stage set,
  not apart from it; an animation reference per Cast version; motion presets as the real bottleneck; **Wan Animate has no end-frame input**
  — batches chain through `continue_motion` (the pinned `WanAnimateToVideo` node: reference, pose, face video, background video +
  character mask, continue_motion); **16 fps model frames vs the 24 fps Stage timeline** — 77 frames = 4.8 s ≈ 115 Stage frames, stride
  72 with a 5-frame overlap; Move vs Replace mode; the post-processing options against E21's v2v result and the per-frame-i2i flicker
  risk) and `02-implementation-plan.md` (spikes E23 core pipeline and E24 post-processing with bars, a decision gate, waves CA1–CA8 ≈
  22–25 days). Open questions for the author in 01 §7. Nothing decided; E22 still running.

## 2026-10-17 22:17 — Spike E22 result · complex action for both: one clip keeps each action but takes turns; layers act at once; D94 stands

- **Setup** (`engine/spikes/e22_layers.py run|score`, `e22_score.py`, reusing E21's passes, plate, heroes, references and helpers;
  outputs `engine/spikes/out/e22/`, local, ≈ 0.85 GB). E21's blocking unchanged (room, static camera, Mara x −1 turned +35° `stand`,
  Ines x +1 turned −35° `arms_crossed`); scratch copy of E21's project → `F:\loom2-projects\e22-action-20261017-210015` (+ `_state-…`),
  a private orchestrator, seeds 20261017–19. **The actions**, written into every prompt: Mara — *M1* walks two steps forward towards
  the middle of the room, *M2* stops and raises both arms high above her head, *M3* lowers them and puts her hands on her hips; Ines —
  *I1* uncrosses her arms, *I2* takes one step back, *I3* points with her outstretched arm at the window on the far left, *I4* turns
  her head to look at it. (a) prompt: "Static camera, a wide two-shot in a quiet room; two women face each other a few metres apart.
  The woman on the left, ⟨Mara⟩, ⟨M1–M3⟩. At the same time the woman on the right, ⟨Ines⟩, ⟨I1–I4⟩. They do not touch; the camera does
  not move." Layer prompts: "Static camera, a quiet room. ⟨Mara⟩, turned towards someone off-screen to the right, ⟨M1–M3⟩. The camera
  does not move." (Ines mirrored, only her own action.) Still text: "Mara stands with her arms relaxed at her sides, turned towards Ines;
  Ines stands with her arms crossed, turned towards Mara." + E21's scene. Exact strings in `state.json` → `prompts`.
  **(a)** Stage clay still (Klein 9B, both bound, D93 C) → Wan 2.2 I2V Draft (832×480, 81 f @ 16 fps, Lightning 2 + 2).
  **(a_ltx)** the same stills → LTX-2.3 distilled Draft (1024×576, 121 f @ 24 fps, 8 steps), the same prompt, 3 seeds. **Beats
  skipped:** a keyframe needs an end-of-action still of the *same* room (a Stage render of the end blocking draws a new room), and
  plain LTX already broke the blocking (below).
  **(b)** E21's plate → each character into its own copy (E21's Fill-Match + references graph; the facing in the prompt: "her body
  turned three-quarters to the right towards someone off-screen on the right, her face in three-quarter view looking to the right, not
  at the camera", the mannequin's yaw as image 1) → gate on FaceSim's 5 keypoints, yaw = (nose x − eye midpoint x) ÷ eye distance,
  calibrated on E21 (its (a) stills ±1.0, its copies 0.01–0.08): |yaw| ≥ 0.4 with the right sign, else another seed → each copy
  animated alone → per-frame `SAM3_Detect` by text ("woman", one detection — the character walks, a fixed box would not follow; core
  node, the SAM 3 checkpoint's own text encoder) → stacked over the plate, Ines then Mara, alpha = the mask feathered ≈ 2 px. No colour
  lock, no shadow zone, no video pass. Measurement for every two-character clip: `SAM3_Detect` "woman:2" per frame, split left/right at
  the empty columns between them.
- **Copies:** Mara passed 3 of 5 tries (yaw +0.43, +0.44, +0.43; rejected +0.31, +0.39), Ines 3 of 3 (−0.49, −0.44, −0.45). The heads
  now turn towards each other; the bodies only about a quarter turn (the (a) stills read ±1.0) — no longer a line-up, still less
  turned than (a). Mara's third copy changed her trousers for a dress.
- **Beats, by eye on per-character strips** (`strips_a.jpg`, `strips_b.jpg`, `strips_a_ltx.jpg`; ✓ done, ~ partly, ✗ not):

  | arm · seed | M1 walk | M2 arms up | M3 hips | I1 uncross | I2 step back | I3 point | I4 head | Ines starts | notes |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | a · 17 | ✗ | ✓ | ✓ | ✓ | ✗ side step | ✓ | ~ | ≈ 2.5 s | Mara adds hands-on-head |
  | a · 18 | ✗ | ✓ | ✓ | ✓ | ✗ | ✓ | ~ | ≈ 2 s | |
  | a · 19 | ✗ | ✓ | ✓ | ✓ | ✗ steps forward | ✓ | ~ | ≈ 2 s | |
  | b · 17 | ✗ | ~ hands by the head | ✓ | ✓ | ✗ | ✓ held 3 s | ~ | ≈ 1 s | |
  | b · 18 | ~ two short steps | ✓ | ~ one hand | ✓ | ✗ | ✓ held 3 s | ~ | ≈ 1 s | |
  | b · 19 | ~ one step | ✓ | ✓ | ✓ | ✗ | ✓ held 3 s | ~ | ≈ 1 s | |
  | a_ltx · 17 | ✓ overshoots | ✓ | ✓ | ~ | ✗ | ✓ | ~ | ≈ 1.5 s | **paths cross, they swap places** |
  | a_ltx · 18 | ✓ walks out of frame | ✓ | ✗ | ✓ | ✗ | ✓ | ~ | ≈ 1.5 s | **Mara walks past Ines and leaves** |
  | a_ltx · 19 | ✓ up to Ines | ✓ | ✓ | ~ | ✗ | ✗ | ✗ | — | **they touch** |

  Counting ✓ 1, ~ ½: Wan (a) Mara 6/9, Ines 7.5/12; (b) Mara 6/9, Ines 7.5/12 — **the same beats**. The difference is *when*: in (a)
  Ines holds still until Mara has finished (her motion over the first 2 s 2.2 / 4.5 / 3.8 levels vs Mara's 18–19; in (b) 9.2 / 8.3 /
  8.0) — the shared clip takes turns. Numeric proxies (`results.jsonl`, in body heights; mask-split per frame): Mara's walk (feet x, end
  − start) (a) +0.03 / +0.01 / +0.03, (b) +0.04 / +0.20 / +0.24, a_ltx +0.15 / +0.19 / +0.94 (the a_ltx splits fall back on 35–61 frames
  because the two overlap — those numbers are not per character); arms above the start top (a) 0.11–0.12, (b) 0.12–0.20; Ines's leftward
  reach (pointing) (a) 0.34–0.41, (b) 0.28–0.38; Ines's feet (a) −0.04 / −0.04 / +0.01, (b) −0.09 / −0.03 / −0.04 — I2 (step back = +)
  failed in every clip of every arm. The walk is Wan I2V's weak point either way (a: no steps at all; b: one or two short steps).
- **Identity** (FaceSim on every 8th frame, faces ≈ 40 px, advisory; LTX every 12th):

  | arm | Mara own mean (min) | Ines own mean (min) | wrong / swapped frames |
  | --- | --- | --- | --- |
  | (a) Wan | 0.199 (0.068) | 0.257 (0.098) | 0 / 0 |
  | (a_ltx) | 0.096 (−0.118) | 0.163 (−0.084) | 15 / 5 — the place swap and the crossings |
  | (b) layers | 0.158 (−0.041) | 0.252 (0.146) | 0 / 0 |
  | each layer alone (ceiling) | 0.145 (−0.032) | 0.232 (0.141) | — |

  Costumes: (a)'s Ines is olive in 2/3 again (seed 19 right), and Mara's shoes stand on the mannequin's grey foot plates in 2/3 stills.
- **What broke.** (a): turn-taking (above); the background shifts 2.0–4.5 levels from frame 0 (b: 0.0, the plate); Ines points "at
  the window" through Mara in every clip of both Wan arms. (b): Ines's point passes straight through Mara's head (her layer does not
  know Mara is there — it reads as pointing at Mara); **"turned towards someone off-screen to the right" made Wan walk a stranger in
  from the right in 2/3 of Mara's layer clips** (a woman, a man; a hand in the third) — the one-detection text mask kept them out of
  the stack (0 frames of Mara's mask right of x = 480), but the wording must go; no duplicates, no limbs in the wrong layer, no visible
  edge at Draft (seed 18 frame 75: one stray fleck); the feet carry only the shadow inside the mask, so they sit a little pasted.
  (a_ltx): more motion and real walking, but the blocking breaks in 3/3 (crossing, a swap, an exit, touching) and the room changes (a
  lamp appears) — unusable for two characters without guides.
- **Time per shot and peak VRAM:** (a) 299–321 s (still 48–77 s at 10.4–10.9 GB + clip 243–251 s at 12.5 GB); (a_ltx) 322–324 s
  (clip 247–274 s, 13.35–13.46 GB); (b) 713–726 s (E21's plate 11 s; copies 8 tries, 474 s in all, 2 rejected, 9.7–12.2 GB; two clips
  240–245 s each, 12.5 GB; SAM 3 text masks 28–33 s per layer, 3.0 GB; stack 7.7 s CPU). No OOM. Rig 21:00–22:12.
- **Recommendation.** D94 stands as the default: with complex, different actions the shared Wan clip still gives each character *its
  own* action (no mixing, no swaps, the same beat count as layers, bigger gestures, the eye lines and shadows of one image, half the
  time). What it does not do is act at the same time — it plays the two actions one after the other. When the beats must overlap (or
  one character must be re-taken), the layers route does it, at 2.3× the time and with no contact between the layers (a point or a
  look goes through the other person). Untested next steps, cheapest first: time words in (a)'s prompt ("from the first second, while
  …"), or Ines's action first; for (b), drop "someone off-screen" from the layer prompt and give the copy the other character as a grey
  placeholder so gestures respect it. LTX-2.3 is not a two-character route without a guide (beats or the IC-LoRA pose pass). The walk
  and the step back are the actions Wan Draft does not deliver in either arm.
- **Outputs** (`engine/spikes/out/e22/`, not committed): `sheet_a.jpg`, `sheet_a_ltx.jpg`, `sheet_b.jpg` (plate, the six copies, the
  stacks, every layer clip), `sheet_copies.jpg` (all tries with yaw), `strips_a|b|a_ltx.jpg`, `a_|a_ltx_|b_|layerMara_|layerInes_seedN.mp4`,
  `compare.mp4` ((a) seed 20261019 | (b) seed 20261018), `results.jsonl`, `score_summary.json`, `state.json`, `run.log`. Code:
  `engine/spikes/e22_layers.py`, `e22_score.py` (new, not committed). Not done: I1 / I4 by eye only (no pose metric); 3 seeds per arm;
  no report.md (the tables are here).

## 2026-10-17 22:53 — proto01_animate revised · the author's six notes worked into 01 and 02

The author reviewed `.docs/proto01_animate` and sent six notes. Both documents are revised; 01 §8 maps each note to where it went.

- **1 · The performance is a proxy.** Wan Animate's output is a model of the final, like the clay, so post-processing is the render, not
  a polish. Read from the pinned `WanAnimateToVideo`:
  - one output frame per pose frame, with no frame rate of its own;
  - `continue_motion` fixes a batch's first frames with *any* images (1, 5, 9, …);
  - there is no end-frame input;
  - the reference is centre-cropped to the clip's size.

  Hence two frame rates to measure: F16 (resample, RIFE) and F24 (Stage's poses as they are: 72 new frames = exactly 3 s). And two welds:
  W1 chains the last 5 frames; W2 starts every batch from a Stage keyframe still as a one-frame `continue_motion`, so each batch can be
  re-taken alone. The geometry welds by construction and the identity is re-anchored in every batch, so the risk left at a join is
  appearance drift.
- **2 · Steps 3 and 4 swapped.** The Stage set comes first and the plate is generated from it; the moving plate comes after the camera
  keys.
- **3 · Move against Replace** is its own spike, E23b, on the same shot, layers and batches. E23a (one layer: F16/F24 × W1/W2) comes
  first.
- **4 · Post-processing in three separate stages**, every idea an arm of E24:
  - A, the layer pass: an amount and a model per layer; a face crop; per-frame i2i with the neighbouring frames as references (FLUX.2 dev
    up to 10, Klein 9B KV up to 4); keyframes + flow;
  - B, the image stream: RIFE, native 24, in-betweens from refined keyframes, other rates;
  - C, the final polish, faithful and keeping shadows and light: Wan low-σ, LTX low strength, a structure-locked LTX + IC-LoRA depth
    from the shot's Stage depth (the candidate I expect most from), VACE only with a download decision, FLUX.2 dev with neighbours.

  The catch is cost: FLUX.2 dev per frame is ≈ 2.7–4.3 h per 10 s layer at the spec times, and more today under RAM pressure (owed). Its
  fix comes before E24.
- **5 · The motion library.** The old loom's `Godot4-MixamoLibraries` checkout is catprisbrey's *Godot4-OpenAnimationLibraries*:
  - its former README says the Mixamo files were removed for Adobe's terms (6.2.E);
  - what is left is game sets (MeleeLib, ShooterLib, a faulty locomotion set) as Godot `.res` (zstd) on Godot's humanoid skeleton;
  - no licence is declared (the old loom's notes called them CC0), some clips carry a `mixamo_com` track, and there are few acting moves;
  - not used.

  Mixamo itself is free in your own films but not to redistribute (Adobe's FAQ, to re-read against the live terms). So the plan is an
  FBX / glTF importer with retargeting onto the 12-joint mannequin (CA1), the author's clips in a local folder (the old loom's
  `mixamo_animations/` already holds `Walking.fbx`, usable in E23a), and a verified CC0 starter set to ship. A licence check (02 §2)
  comes before any fetch. The coarse rig drops wrists, ankles and fingers; COCO-18 does not need them.
- **6 · The animation reference at casting.** One per Cast version: 16:9, full body, A-pose, colours bound, an optional back view and
  test animation. It moved from CA8 into a new first wave, CA0.

Plan now: §2 licence check → E23a → E23b → E24 → a D-number → CA0–CA8 (≈ 26–30 days; CA0 and CA1 may start beside the spikes). Still open
for the author (01 §7): the starter library and the Mixamo downloads, camera moves, joins, the delivery rate (24 or 25 fps), the time
budget per shot, props, lip-sync. Nothing decided or run.

## 2026-10-17 23:14 — proto01_animate, second round · the CC0 starter motion fetched; detailed and non-human dummies an open question

The author's second notes:

- **Hands, feet and creatures.** A new open question, 01 §9, with proposals.
  - Hands and feet: H3, a Simple / Detailed level per figure, where Detailed is the starter set's skinned mannequin; spike E25 asks
    whether Wan Animate follows drawn hands (21 points) and feet.
  - Non-human: N1, humanoid creatures by proportion controls and attachments (Wan Animate as today), first. N3, not humanoid (a
    quadruped), needs a depth-guided performance instead of a pose skeleton (LTX IC-LoRA depth or VACE): spike E26, only if wanted.
- **The starter library, fetched with the author's yes.** Quaternius' *Universal Animation Library* 1 and 2 [Standard], CC0 1.0 (read
  in each archive's `License.txt`), from OpenGameArt to `F:/loom2-models/motion/`. `SOURCES.md` there holds the URLs and the sha256
  (UAL1 `18ff1a72…3ac2`, UAL2 `ec0e40d6…9217`).
  - 87 clips plus a rest pose in each: talking, folded arms, phone, yes / no, walk, formal walk, carry, jog, sprint, crouch, sit down /
    sitting / sitting talking / stand up, lie to idle, pick up, interact, open a chest, push, climb, falls, combat.
  - Missing for our shots: point, wave, turn on the spot, step back.
  - Each library has **skinned mannequins with fingers and feet**: UAL1 53 joints (Rigify `DEF-` names), UAL2 65 joints (Unreal names),
    plus a female mannequin on the same rig. E23a uses `Walk_Loop` for Mara.
- **Mixamo.** The download steps are in 01 step 5 (mixamo.com, an Adobe account, FBX Binary, Without Skin, 30 fps, untick In Place for
  walks, a local folder outside the repo). Re-reading Adobe's live terms is still owed (02 §2).
- **24 fps** stays the delivery rate; 25 matters only for a European TV master, so B4 is later.
- **Times are judged after the spikes.** The estimates are removed. A6 is new: a FLUX.2 dev *healing patch* on a region over a frame
  range. Klein 9B is named first for per-frame work.

## 2026-10-18 09:34 — proto01_animate 03 · Image and Animate as the two making suites; an animation editor on EffectCraft (proposal)

The author's direction:

- Generate becomes **Image**, with Edit under it, reachable from anywhere in the making.
- Animate is rearranged for the clay process, with **Stage moving into it** and **Generate's one-column layout**.
- A **UI/UX review** goes into the plan.
- `F:\source\repos\effectcraft` is to be the basis of the animation editor.

Written up as `.docs/proto01_animate/03-image-and-animate-suites.md`. Nothing decided; D95 if the author accepts.

**EffectCraft, reviewed (v0.12.0, `f36b2b3e`, 2026-10-17):**

- A clean-room **After Effects in pure Rust**: ≈ 380k lines, 32 crates, 307 effects, 623 engine commands, 3,564 tests.
- MIT OR Apache-2.0; no GPL and no FFmpeg; pure-Rust codecs (with FilmCraft's).
- **Alpha** (its roadmap: ≈ 45 % ready for real work), 2,060 commits in 17 days.
- The model is After Effects' (a composition of layers with property trees and keyframes, `.ecproj` JSON).
- The engine crates are UI-free and build for wasm32, with a CPU reference renderer, a wgpu renderer and a CLI.
- Its UI is **egui**, so none of it can be used inside loom2's React app.

**The proposal:**

- **Three top tabs.** Story (Episode stays the cut), Image (Make ⇄ Edit in place; Stage stills as *From a stage*), Animate (one
  column: Shot, Scene, Motion, Camera, Plate, Performance, Edit, Finish, Selection, Output).
- **Animate's layout:** no right Inspector; one timeline and one transport under the viewer, which shows the shot at three levels
  (Clay, Performance, Final).
- **An After Effects-style compositing editor for one shot.** loom2's own React UI over EffectCraft's engine, by D59's pinned-artifact
  pattern: a WebAssembly facade for the preview (R1, if spike E27 finds it small and fast enough; else R4, a compositor of our own), and
  the pinned CLI for final renders as orchestrator jobs (R2). A shot version owns one `.ecproj` composition in a loom2 record.
- **Waves:** UX0 review and wireframes → IM1 Image → AN1 Animate shell → E27 (beside E23) → AE1 composition → AE2 viewer and timeline →
  AE3 effects and colour → AE4 AI passes on layers → AE5 output → UX9 review. About 32–43 days. CA8 folds into AN1 / AE2; CA6 writes an
  AE1 composition.

**FilmCraft** (`F:\source\repos\filmcraft`, a Premiere clone, MIT/Apache) is noted as a later model for Episode. Six questions for the
author are in 03 §9.

## 2026-10-18 10:15 — D95 · three making tabs (Story · Image · Animate); the preview route explained; Catalogue ideas mocked up

The author answered proto01_animate 03 §9:

- three tabs, yes for now;
- stills from a stage made in Image while the stage is edited in Animate, yes ("the Catalogue will probably play a role … mock up a few
  ideas");
- Edit's left panel as one column, yes;
- Animate without a right Inspector, yes on trial;
- Episode stays the cut in Story, with FilmCraft as its model later. **Animate first, Story afterwards.**

Recorded as **D95** in 13.

**Question 5, the EffectCraft route, was answered with an explanation** (03 §5.2). The final render is always the pinned CLI (R2). The
choice is where the interactive preview runs:

- **R1, WebAssembly in the page:** no frame copies, a prebuilt `.wasm`, works in browser dev and the e2e, and a crash only kills a
  worker. Its limits are 4 GB and slower CPU-side work.
- **Native, with every frame read back and sent to the page** (≈ 38 MB/s at Draft 24 fps):
  - R3 inside the Tauri shell: rebuilds ≈ 650 packages in every installer, a crash takes the window, no browser mode. Not proposed.
  - New: **R3b**, a native preview server beside the orchestrator with frames over loopback HTTP, as the native fallback.

E27 measures R1 first, R3b only if R1 misses ≥ 12 fps scrubbing at Draft with ComfyUI running.

**The Catalogue ideas** are in a new `04-catalogue-for-making.md`, with four mockups (HTML → Edge screenshots in `img/`, using E21/E22
spike frames):

- **C1:** a Bin inside Image and Animate.
- **C2:** work made for a shot lands on an automatic shot page laid out in lanes (frames · from the stage · layers · takes and final).
- **C3:** every object is an item (stages, motion, compositions, layers, characters, voices, with kind badges and Type chips).
- **C4:** lineage across media, from the characters to the Episode take.
- C5–C7 are smaller: gather for a shot, group chips, stage stills on the stage's page.

A suggested order ties C1 and C3 to IM1 / AN1 / CA1 / AE1 and leaves C2, C4 and C5–C7 to the Story pass. Four questions for the
author.

## 2026-10-18 10:48 — The preview balanced between the page and a preview server; Flow nodes as shot recipes (proposals)

**The preview.** The author: the in-page preview is not enough, but is not ruled out. They prefer a preview server beside the
orchestrator working with the page, with quality steps down, and the final render as a backend job. They asked how EffectCraft does it.

**EffectCraft's split, from its code and docs:**

- **The viewer:** a resolution per composition (Auto / Full / Half / Third / Quarter / Custom); layer quality (Best / Draft /
  Wireframe); Fast Previews (Adaptive Resolution down to ½–⅛ while dragging, Draft 3D, Fast Draft, Wireframe); a content-hashed layer
  cache, a RAM preview cache filled when idle, a disk cache; proxies.
- **The render queue:** Best, Full, on the project's renderer, with the encoders.
- **Its web build** splits the work into the page (frames without effects on WebGPU), frame workers (project replicas synced by diffs,
  `remote.rs`) and job workers.

**03 §5.2a, the balance:**

- the page draws T0 at once (cached layer frames, transforms, blends, mattes);
- the native preview server (R3b, now the main preview) renders T1 at adaptive ¼–½ Draft while scrubbing, T2 Full Draft then Best at
  rest, and T3 the idle cache for real-time playback, by priority, stepping down while ComfyUI runs;
- the final render is a separate queued CLI job (R2);
- R1 can take over T0 / T1 later.

E27 is rescoped: the server plus T0. Bars: T1 ≥ 12 fps, T2 ≤ 150 ms, T3 real time, the final equal to T2 Best.

**The Flow idea** (the author, on C4): each Flow node is a small shot (≤ 30 s) defined by a combination of elements, ComfyUI-like; the
nodes build the movie, finished in a FilmCraft-like editor. Reviewed in the new `.docs/proto01_animate/05-flow-nodes-as-shot-recipes.md`:

- **Two levels:** the story graph, and each node's **recipe**, which is C4 as a plan, so stale steps re-run alone with the cost first.
  It is the original loom's model (a node owns its clip, continuity within a node, transitions between nodes;
  `kb-storyboard01.md`).
- **Animate becomes the node editor**: its column is the recipe's steps.
- **Care points:**
  - the name: today *Episode* is the cut. Options are A, the author's words (node = Episode, cut = Movie), or B, node = Shot (merged
    with the Story shot), cut = Episode. Recommended: B;
  - ComfyUI's paradigm with coarse loom2 steps, never ComfyUI's UI (D2, D15);
  - a soft 30 s cap;
  - one camera per node, with scene groups for coverage;
  - the logic nodes stay, with a cut per route;
  - the quick image-to-video case must stay quick.
- **Waves:** RC0, the recipe record and staleness, comes with AN1 / AE1. RC1 (the recipe graph), RC2 (node = shot in the Flow), RC3 (a
  cut from a route) and RC4 (the FilmCraft study) follow in the Story pass. Five questions for the author.

## 2026-10-18 11:09 — D96 · the Story Flow is a shot-flow; EffectCraft's preview model in the build plan

The author answered 05:

- **B**: the Flow node and the Story shot merge into one **Shot**; Episode stays the cut.
- **One camera per Shot.**
- **≈ 30 s as a guideline**: a warning, not a block.
- **The recipe graph opens both** in the Flow and in Animate.
- **The cut:** each Shot's content is rendered onto a video lane of the FilmCraft-like edit suite, where the movie is processed and
  rendered.
- ComfyUI's way of working, not ComfyUI.
- **"We should not sacrifice features for simplicity"**: like a ComfyUI workflow's 4–5 components for one image, every important part
  must be covered by the shot-flow.

Recorded as **D96**. 05 is rewritten as accepted:

- §3 holds a **coverage table**: every step's important parts, from Character to Take, with the Frame step's model, prompt, references,
  Look, size, LoRAs, encoder and seed.
- Templates prefill a recipe and hide no step.
- The recipe graph is shared with Animate's Graph view.
- The cut follows a Shot's new take, with a cut per route.
- RC0 is now 4–5 days, with the coverage check as a test (D60's pattern). RC1–RC4 come in the Story pass.

**03's build plan takes EffectCraft's own preview model.**

- **New wave AP1** (4–5 days, after E27):
  - the tiers T0–T3, with priority and cancellation;
  - viewer resolution (Auto · Full · Half · Third · Quarter);
  - layer quality (Best · Draft · Wireframe);
  - Fast Previews (Off · Adaptive with ½ · ¼ · ⅛ · Draft · Fast Draft · Wireframe);
  - the layer, RAM-preview (cache when idle) and disk caches with budgets in Settings › Animate (D60 audit);
  - proxies;
  - step-down while ComfyUI runs;
  - a status chip that matches the frame shown (T8);
  - the server's lifecycle.
- E27 is rewritten around the preview server.
- AE2 uses the tiers.
- AE5 uses EffectCraft's render settings (Best, Full, rate, motion blur, frame blending, colour depth, Proxy Use off) and output
  modules.
- 03's total is 36–48 days.
