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
