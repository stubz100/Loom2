# 02 · loom (Loreweave Studio) retrospective — what to keep, what to leave

Sources: `F:\source\repos\stubz-002-tripo-sf\loom\loom-loreweave-studio\.docs\` (kb-storyboard01, kb-loom-ui,
kb-loom-p0..p6 + journals, kb-loom-flux2-weights, kb-loom-cache) and the loom source tree, read 2026-10-04.
Rule references (R-numbers) point at `kb-storyboard01.md` §10.0.

## 1. What loom was

An articy:draft replacement for the desktop whose headline deliverable was a ~30-minute pitch "episode"
assembled from non-linear story nodes. Tauri 2 + React/TS shell, Python FastAPI orchestrator on
`127.0.0.1`, pipelines run as isolated subprocesses with file + manifest hand-off, one heavy model on the
GPU at a time.

Four content layers: **L1 StoryBible** (world, style fragments, spine) → **L2 Asset Library** (AssetProfile
with versions + LoRA) → **L3 Shots & Takes** (keyframes → i2v) → **L4 Narrative graph**, plus a VRAM-aware
queue and a "Muse" assistant that never spends GPU on its own.

The character bootstrap loop (R7) drove almost all shipped work: **Cast** (multi-model t2i pool, star a
hero) → **Expand** (coverage matrix of poses/angles/expressions via FLUX.2 multi-ref, img2img, inpaint,
LTX video-sketch frame harvest) → **Curate** (keep/reject vs a readiness meter) → **Train** (ai-toolkit
LoRA on ROCm) → **Lock**.

Where it got to: P0 accepted; P1 "functionally complete" (2026-06-14); P2 one rig session from its stamp
(2026-08-08) when the GPU went to RMA; Sept 2026 was GPU-free hardening, the v2 UI rebuild, a CPU/ggml
spike and a cache manager. **P3–P6 (shots, flow graph, episode export, 3D) were never started.** Nothing
in the v2 UI was ever driven by a person; the first LTX video job never ran on the GPU.

Code size for orientation: orchestrator ≈ 15.5k lines (`main.py` 3 803), vendored pipelines ≈ 15.8k,
frontend v2 + shared client ≈ 7.7k (`orchestrator.ts` alone 1 664, hand-written).

## 2. Keep: the durable engineering rules

These paid for themselves repeatedly and are independent of the storyboard domain.

| Rule | Keep in loom2 because |
| --- | --- |
| Git = app only; projects are user data on a work disk; weights never in git (R3/R72/R160) | 100 GB repos are unusable; projects outlive app versions |
| One weights roster with repo + file + sha256 + "used by"; presence probe → explicit resumable fetch as a *queue job*; resolver pins a cached revision, never trusts `refs/main` (R160/R163, kb-loom-cache §4) | ref drift in the shared HF cache 412'd a fully cached model; a stock `hf delete-cache` would have deleted the working snapshot |
| Durable `queue.json`, resume **paused**, one job lifecycle with a `resumable` flag, graceful `/shutdown` handshake from the shell (R69/R78/R159) | the rig lost power 42 times in 120 days; the trainer survived them only because of this |
| Stable IDs, `schema_version` on every record, atomic writes (temp → fsync → rename), loader refuses partial JSON | every rename-only write was a real data-loss bug in the 2026-09-20 hardening pass |
| Single GPU worker, subprocess isolation, static VRAM-estimate admission, capped OOM retry; every AI call (incl. VLM/SLM) is a queue job (R141/R142) | 16 GB cannot co-load; nothing may auto-spend GPU |
| Cancel = worker **tree** kill via a Windows Job Object nested under a kill-on-close parent job | no orphaned GPU processes after a crash or cancel |
| GPU work is **staged** then explicitly queued (R118) | the author's compute-cost worry; made training safe |
| Token-gated mutating endpoints, CORS allowlist, token injected at runtime (never baked into `dist/`) | a baked token masked a broken READY-time injection for months |
| Adapter contract: `build_argv` / `parse_result` / `capabilities` / `progress`; **manifest status is truth**, never "newest PNG" | normalise worker quirks in one place |
| Warm worker: resident model per `warm_group`, one JSON line per job over stdin, `[serve-result]` line back, idle grace eviction | model load once per batch instead of per image; the only way dev FLUX.2 sweeps were tolerable |
| One lineage edge per output; stamp `style_id`, `chained_from`, model, LoRA, seed **at write time** (R98) | 0/661 jobs carried `chained_from`; nothing downstream can recover it later |
| Disk guard polls project-cap headroom *and* disk free: warn < 5 %, hard-stop < 2 %, never deletes a master (R96) | an oversubscribed disk dies before any single project hits its cap |
| Project format (aspect, resolution, fps) fixed at creation (R45/R56) | every clip and render must match the finalize gate |
| Shared known-good ROCm venv + isolated dependency overlays via `PYTHONPATH` (R25/R103) | never mutate the one working torch stack |
| "Display == reality": every default the UI shows is what the worker runs | a recurring bug class in P1/P2 |
| Advisory meters, never blockers (R14) | the author: "I would not want any constraints on any creation in the app" |
| Lossless PNG-sequence clip masters + mp4 proxy (R161) | codec round-trips break frame continuity |

## 3. Leave behind (for the MVP)

- The storyboard domain objects as *mandatory structure*: StoryBible, AssetProfile versions, coverage-cell
  vocabulary, dataset recipes, readiness meter, captions, LoRA staging. loom2's MVP is a generation + editing
  studio; these can return later as an optional "Story" workspace on top of the catalogue.
- The multi-model casting pool (flux2 + sd35 + zimage + krea2) and SD3.5-specific tooling (Tile ControlNet
  upscale). One primary t2i family (FLUX.2) is the point of loom2.
- Identity-lock swapper (InsightFace research weights), GFPGAN via a facefusion mirror, inswapper —
  questionable provenance and licensing.
- The bespoke Comfy-FP8 loader stack (`scaled_fp8.py`: three key remaps, fused-qkv LoRA row slicing,
  vendored Mistral tokenizer) *as an in-house component*. Either run the same files through a maintained
  engine or use GGUF under BFL tensor names, which needed no remap.
- Polling-based UI state (2 s full `/jobs` refresh), hand-rolled 240 px panes, `window.prompt` dialogs,
  hover-only affordances, a hand-written 1 664-line fetch client without generated types.

## 4. Pain points loom2 is specifically answering

### 4a. Model sourcing (user point 1)
- Repos came from six kinds of origin: BFL gated, Comfy-Org repackaging (own key layout, upstream moved
  twice → ref drift), unsloth/city96/leejet GGUFs, Tongyi/Stability/InstantX diffusers repos, ONNX mirrors
  of research weights (inswapper, GFPGAN via facefusion), and auto-downloading packs (insightface).
- The planned companion HF repo with sha256s was **never built**; checksum verification stayed a TODO from P0.
- Four scattered manifests (`models.json` phase list, `multi_presets`, `postproc`, catalog pins) were only
  unified in the last month (`weights.py` roster + `/cache` manager, click-through owed).
- Lesson: **anchor to one convention with declared provenance** and build the roster + resolver on day one.

### 4b. UI (user point 2)
- v1: a 4 070-line `App.tsx`, two fixed 240 px columns, a 14-control wrapping bar on the stage, 128
  tooltips carrying essential semantics, 8–11 px type. The author: "the pane arrangements are very
  ineffective", "the image generation part … is not used correctly or efficiently."
- v2 fixed the frame (rail · panel · stage strip · canvas · inspector · dock; keyboard-by-visual-row;
  grouped/lineage view with cover cards; branching post stacks; loupe + compare) but was never used by a
  person, had no virtualisation past ~300 tiles, and its "Edit mode" was one `<img>` plus one overlay
  `<canvas>` holding a single mask (brush/eraser/lasso/feather/invert/from-matte), re-blitted in full on
  every pointer move, posted as a base64 PNG to `/outputs/masks`. No layers, no undo, no pan/zoom, no
  pressure, no soft brushes.
- Images reached the UI as full-resolution PNGs over plain HTTP with `loading="lazy"` as the only
  mitigation: no thumbnails, no size variants, no cache headers. Video tiles rendered as text.
- A post-processing step's result was a new job output, not a layer: no compositing, no crop-and-paste-back
  for local hi-res inpainting, no soft-mask blending, and no FLUX.2 inpaint path at all.
- Lesson: the content model (tiles, grouped tree, post stack, JSON prompt tree) was right; the editing
  surface needs a real layered raster engine with a document model, and the frame must be designed before
  the first control.

## 5. FLUX.2 on this rig — measured facts to design against

| Fact | Number | Source |
| --- | --- | --- |
| FLUX.2-dev FP8 (Comfy) transformer resident | ~18 GB > 16 GB → HMM re-streams weights every step | p2-imp probe |
| dev 512², 8 steps, cold single run | ≈ 185 s | p2-imp M2.5 |
| dev-turbo 4 steps, warm cell (flow resident, TE shuttled) | ≈ 100 s | p2-imp M2.7 |
| klein-9b warm cell | ≈ 80 s | p2-imp M2.7 |
| dev 50 steps | NaN latents → black PNG (~686 s); default became 8 steps / g 3.0–4.0 / 512² | p2-imp M2.5 |
| dev VAE | must load **float32** on ROCm (bf16 crashed `encode_image_refs`) | p2-imp M2.5 |
| 1024² hero reference | 4 096 ref tokens ≈ 80 % of the attention sequence | p2-imp probe |
| klein-4b (8 GB) + Qwen3-4B TE (8 GB) | nominally fit, thrash if co-resident → two-phase TE→flow | P1-11 |
| conv-heavy VAE decode | 888 s → 1.9 s with `MIOPEN_FIND_MODE=2` | p2-imp M0e |
| SDPA backend | AOTriton fastest; `aiter` hollow on Windows; `torch.compile` ≈ +10 % | p2-imp |
| Timing | HIP is async: `torch.cuda.synchronize()` at every boundary or the numbers lie | p2-imp 06-29 / 07-04 |
| GGUF Q4_K_M (unsloth) | BFL tensor names, **no remap**; CPU: 1 373 s vs 1 651 s FP8-dequant, 32 GB vs 51 GB RAM, equal JSON adherence | kb-loom-flux2-weights |
| sd.cpp CPU, klein-4B 512² | 54 s; dev 512²/20 steps 27.5 min | p2-imp M2.15 |
| i2i schedule | place `num_steps` across `[strength, 0]` with inverted shift; otherwise 4 steps × 0.6 strength = 2 real steps | p2-imp 08-09 |
| Text encoding (dev) | prompt is the *user turn* of a Mistral chat template with BFL's fixed system message; hidden layers 10/20/30 stacked; max 512 tokens; no negative prompt | stage1_load_models.py |
| JSON prompt tree | scene · subjects[] · camera · lighting · style · mood · color_palette → compact JSON **is the prompt string**; no schema enforced on the model side | orchestrator.ts / p2-imp M0d |
| Multi-ref | `encode_image_refs` + `denoise(img_cond_seq=…)`, ≤4 refs klein / ≤6 dev; identity carried into new poses img2img cannot reach | p1-imp P1-11 |

Journal guidance that still holds: **Klein for sweeps, dev for a few hero shots, then upscale.**

## 6. Video in loom

LTX-Video `2b_0.9.7_distilled` (704×480, 121 frames, 8 steps, `offload=model` because T5-XXL is ~11 GB)
was wired as a "video sketch" whose frames were harvested as stills. Two-phase: denoise to latents on disk,
tear down, reload the VAE standalone with tiling, export MP4 through ffmpeg. Proven only in the no-GPU
suite; by 2026-09-21 the LTX repos were gone from the cache. P3 planned LTX sketch → Wan 2.2 Animate drive
tier, LTX-extend, RIFE/FILM seam welding. **loom2 starts video evaluation from zero measured data.**

## 7. Twelve lessons carried into loom2

1. Foundation first was right; keep the walking-skeleton + executable acceptance pattern.
2. Make the rig run part of every done-line; "no-GPU verified, rig owed" debt never got paid.
3. Synchronize before timing anything on ROCm.
4. 16 GB means offload *design* (two-phase TE/flow, resident flow per batch), not offload flags.
5. A LoRA holds identity only at its trained resolution.
6. Photo-tuned heuristics (dHash, ArcFace) break on stylised, deliberately varied sets; keep meters advisory.
7. Stamp provenance at write time; it cannot be reconstructed.
8. Own the weights roster and ship checksum verification on day one.
9. Prefer standard formats with declared provenance (GGUF under original names) over repackagings that need a bespoke loader.
10. Design the frame before the first control; rebuilding beside the old UI on a shared typed client beat refactoring.
11. Hardware: watch hot-spot temperature, not GPU temperature; sustained warm-worker load is the worst thermal profile.
12. Process hygiene: append-only journals, real clock stamps, isolated state dirs for tests, same-day spec amendments.

## 8. Code reuse map (from the source read)

**Port or copy, after stripping domain fields:**

| Module | What it gives loom2 | Strip |
| --- | --- | --- |
| `orchestrator/runner.py` | durable queue, Job-Object tree kill, OOM retry, STOP file, warm-worker stdin/stdout protocol, tombstone-safe delete | `profile_version_id`, `stage`, `coverage_cell`; generalise `_submit_chained` into a generic "next node" hook |
| `workspace.py`, `lineage.py`, `projects.py`, `diskguard.py`, `logsetup.py`, `config.py` | atomic writes, schema validator, project registry, disk guard, env/.env loader | `story.json`, `bible/`, `assets/` paths |
| `weights.py`, `adapters/hf_cache.py`, `pipelines/hf_cache/run_pipeline.py`, `flux2/hf_pins.py` | roster + revision resolver + fetch/verify/move as torch-free queue jobs | `roster()` source becomes the loom2 model registry |
| `adapters/base.py`, `_batch.py`, `model_catalog.py` machinery | `JobSpec` / `CompletionRecord`, batch manifest parsing, `validate_params` / `emit_argv`, UI-driving param specs | catalog *content* |
| `pipelines/multistack/src/pipeline/flux2/*` + `flux2/src/flux2/*` | reference implementation of two-phase offload, `img2img_schedule`, ref mode, serve mode, NaN guard | **reference only, not built into loom2** (D28, after E0 measured it ≈ 10× slower than the ComfyUI engine on identical files); the `img2img_schedule` semantics are re-implemented in the recipe compiler |
| `ltxv/`, `zimage/`, `sd35/` workers, `postproc/_common.py`, birefnet/resize workers | reference implementations of i2v, inpaint pipelines, matting | |
| `flux2_prompt.py` directive tables + `REF_*` clauses | pose/angle/shot vocabulary for prompt helpers | coverage-cell coupling |
| Tauri `lib.rs` / `main.rs` | sidecar spawn, READY handshake, token injection, graceful shutdown on exit | |
| `Flux2JsonTree.tsx`, `ParamControls.tsx`, `Models.tsx` + `cacheUi.tsx`, `Dock` | JSON prompt form, catalog-driven controls, cache manager UI | adapt to the new store |

**Leave behind:** `bible.py`, `assets.py`, `coverage.py`, `recipe.py`, `readiness.py`, `training.py`,
`factgraph.py`, `adapters/multi.py`, `identity.py`, `frame_harvest.py`, `zimage_trainer.py`,
`pipeline/multi/`, ≈80 % of `main.py`, and in the frontend `world/*`, `ReadinessTab`, `VersionTab`,
`Expand`, `Train`, `LoraPreview`, `Captions`, the A/B/C/D stage model in `store.ts` / `tiles.ts` /
`Stage.tsx`, and `Edit.tsx` (reference only).
