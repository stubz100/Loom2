# 18 · Wave LT — LoRA training: D25's slots live, ai-toolkit on ROCm as a staged job — plan

Status: **proposed 2026-10-14**; approval gates E16 and LT1 (D86). 03 §5 item 2, 17 §13 "LT · LoRA training", loom P2 (02 §2).

A character, place or prop of the Cast (17 §3b) gets its own LoRA, trained on the rig from a version's reference set as a staged
queue job, promoted into the version's `trigger` and `lora` slots, loaded by Generate's LoRA slots (09 §3b) and, through `@Mara`,
by every recipe that mentions the profile. The spike E16 decides first whether ai-toolkit trains Klein on this card at all.

## 0. What exists

| Where | What | State |
| --- | --- | --- |
| D25 (`recipes.py`, `graphs.py`, `queue.py`) | `LoraRef {model_id, strength}` on every generative recipe; `_lora_chain` adds `LoraLoaderModelOnly` nodes after the reference nodes (B11); `_validate_models` checks every id against `ROSTER_BY_ID`; manifests record `loras[]`; `recipe_weights` lists them | plumbing only — `loras` is empty on every recipe the UI submits |
| Roster (`roster.py`) | `role="lora"` entries (FLUX.2 Turbo, Wan Lightning high / low, Qwen-Edit Lightning + angles, LTX IC-LoRA Union, RefControl poses) | used by the model specs' presets (turbo / lightning toggles, the Stage guide LoRA), never by a slot |
| Generate (`GenerateSuite.tsx`) | "LORA SLOTS (D25)" — four disabled selects, "loading is wired post-MVP" | the stub this wave replaces |
| Story (D85, `story.py`) | `ProfileVersion.trigger` / `.lora` reserved (`None`); the Cast version page shows "— (LoRA wave)"; the bootstrap's *Train* step is greyed; a version's reference set is an album group whose Expand results carry `params.coverage_cell`; `final` locks the group | the data the trainer reads is already curated by the author |
| loom P2 · M1 (2026-06-21, `kb-loom-p2-imp.md` §M1, `trainers/ai-toolkit/LOOM_VENDOR.md`) | ai-toolkit `548a286` trains on the RX 9070 XT under Windows ROCm (then torch 2.9.1 + rocm 7.2.1): Z-Image 6B at 512², rank / alpha 16 / 16, qfloat8 Quanto on the transformer and the encoder, `low_vram`, gradient checkpointing, plain AdamW 1e-4, batch 1 — 1.34 s/it, 500 steps ≈ 11 min of compute (the 100-step adapter did not learn the identity, 500 did: ArcFace centroid 0.263 vs −0.016 for the base control); a kill + relaunch resumed twice from `optimizer.pt`. Six patch seams (TorchAO optional, `AI_TOOLKIT_MINIMAL_ZIMAGE`, a `torch.distributed` cleanup predicate, the Diffusers FSDP import shim) and an overlay without `torchao` / `bitsandbytes`, NumPy 1.26.4 for the SciPy 1.12 pin, PEFT 0.18.1 | the gate was GO; M2's queued trainer was a skeleton only, never a product path |
| ai-toolkit today (`f7a1fb9`, 2026-10-10, MIT) | `arch: flux2_klein_4b` / `flux2_klein_9b` (`extensions_built_in/diffusion_models/flux2/flux2_klein_model.py`): the transformer is read from `name_or_path/flux-2-klein-base-4b.safetensors` when that file exists in the folder — loom2's own file under `diffusion_models/`; the VAE `ae.safetensors` from `vae_path` or the hub (`ai-toolkit/flux2_vae`); the encoder Qwen3-4B / 8B as a transformers folder (`flux2_klein_te_path`, a class attribute); the UI's Klein defaults are `quantize` + `quantize_te` `qfloat8`, `low_vram`, flowmatch, weighted timesteps. Pins: `torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0` (the engine venv's exact versions in their ROCm build), `torchao==0.10.0`, `bitsandbytes`, `optimum-quanto==0.2.4`, `peft==0.18.1`, `transformers==5.5.3`, Diffusers at a commit, `scipy==1.12.0` (no 3.13 wheel → Python 3.12), `torchcodec` / `av` (video; not needed here). No ROCm or Windows statement. HF's Klein blog: a base-4B LoRA trains in ≈ 13 GB bf16, 1 800 steps ≈ 1 h on a 4090, lr 1e-4, and a LoRA trained on *base* loads on the distilled model | the versions line up with the engine venv; the ROCm seams are loom's to re-apply |
| On disk (`F:/loom2-models`) | `flux-2-klein-base-4b` / `-9b`, `flux-2-klein-4b` / `-9b` / `-9b-kv`, `vae/flux2-vae.safetensors`, `text_encoders/qwen_3_4b.safetensors` (ComfyUI's single file — not a transformers folder), `loras/` (6.7 GB of roster LoRAs); `F:/HF_HOME` 0.9 GB (BiRefNet only); 750 GB free | the trainer needs the encoder as a transformers folder: one download (§2) |

## 1. Purpose and scope

- **In:** a LoRA per profile version (character, place, prop) on **Klein base-4B** (Apache-2.0, both variants), trained from the
  version's reference set with template captions, as a **staged** queue job with progress, cancel and resume; a per-project registry
  of trained LoRAs; Generate's LoRA slots for trained and roster LoRAs; `@mention` → the LoRA + trigger; a readiness meter (advisory);
  an optional identity check with FaceSim; the Models suite's "Trained" group. Klein base-9B as a per-job choice only if E16d fits.
- **Out (v1):** style LoRAs (the same job on an album group — v1.1 once the character path is proven), video LoRAs (Wan / LTX), text-encoder
  training, DoRA / LoKr, multi-GPU, any upload. Expand (17 §3b) keeps using the hero as its identity source and never loads the LoRA.

## 2. Spike E16 — ai-toolkit on torch 2.13 ROCm 10 with Klein (3 d, the gate)

`engine/spikes/e16_klein_lora.py`, journal entry with every number, D86 accepted or revised by its verdict. 08 §7's kill rule applies.

| Bar | What | Pass |
| --- | --- | --- |
| **E16a install** | `trainers/.venv` by `scripts/trainer-setup.ps1`: uv, **Python 3.12** (SciPy 1.12 has no 3.13 wheel), the engine's torch wheels from the AMD index (`torch==2.13.0+rocm10.0.0`, `torchvision 0.28.0`, `torchaudio 2.11.0.2`), ai-toolkit as a **submodule at a pin** (`trainers/ai-toolkit`, as `engine/comfyui` is) plus `trainers/patches/*.patch` (loom's seams, re-derived against the pin) and `trainers/constraints.txt` (no `torchao`, no `bitsandbytes`, NumPy 1.26.4, torch never swapped for a CUDA build — as `engine/constraints.txt`) | installs on a clean clone; ≤ 8 patch seams, none in the training algorithm; `python run.py --help` and an import of the flux2 extension succeed |
| **E16b train** | Klein base-4B on the SY1 rig run's kept references (30 refs of *Mara*, `engine/spikes/out/sy/`), 512², rank / alpha 16 / 16, qfloat8 Quanto on transformer + encoder, `low_vram`, gradient checkpointing, AdamW 1e-4, batch 1, **1 000 steps**, a save every 250, sampling off | runs to the end with **peak VRAM ≤ 15 GB** (sampled through `torch.cuda.mem_get_info` by the wrapper); **≤ 2.0 s/it** (1 000 steps ≤ 35 min); a kill at step ≈ 300 and a relaunch resume from the step-250 checkpoint with the step count continuing |
| **E16c load** | the adapter through ComfyUI 0.39.0's `LoraLoaderModelOnly` on **klein-4b** (distilled — Generate's Iterate model) and on klein-base-4b, loom2's own t2i graph, 8 fixed-seed prompts "`<trigger>`, `<coverage sentence>`" with and without the LoRA | the engine's LoRA key report clean (0 unmatched keys — else a key remap in the wrapper at save time, as loom remapped the VAE keys); FaceSim centroid similarity to the hero **≥ 0.30 with the LoRA and ≥ base + 0.20**; by eye the same character in ≥ 6 / 8 |
| **E16d 9B (stretch, recorded, not a bar)** | the same on klein-base-9b with Qwen3-8B on the CPU (`low_vram`) | peak VRAM and s/it recorded; it becomes a per-job base only if it stays under 15 GB and ≤ 4 s/it |

**Downloads and installs E16 needs (the author's approval, D86):** `Qwen/Qwen3-4B` as a transformers folder, **7.5 GB, Apache-2.0**,
into `F:/HF_HOME` (the encoder loom2 already holds is ComfyUI's single file, which transformers cannot load); for E16d `Qwen/Qwen3-8B`,
**15.3 GB, Apache-2.0**; the VAE is tried from loom2's `vae/flux2-vae.safetensors` first (the same tensors as the hub's `ae.safetensors`,
E16 checks the key names), else the hub's 0.3 GB file; the trainers venv ≈ 7 GB (the ROCm torch wheels alone are 3+ GB). Everything is
deleted on a NO-GO. **NO-GO:** the wave shrinks to LT1 (slots live for roster LoRAs) and 13 records that training waits for a lighter
recipe on this card.

## 3. Design

### 3a. The trained-LoRA record — files are truth

`story/loras/<id>.json` + `story/loras/<id>.safetensors` in the project (`id` = `lora-` + 8 hex):

```
{schema_version, id, name, profile_id, version, base: "klein-4b" | "klein-9b",   # the family + size the adapter fits
 trigger, steps, rank, resolution, lr, seed,
 dataset: {group_id, asset_ids[], captions_sha256}, job_id, sha256, size, created_at,
 measured: {s_per_it, peak_vram_gb, wall_s}, identity: {with, without, hero_refs_band} | null,   # 3h, advisory
 previous: [ids]}                                                                   # a retrain keeps the old record and file until deleted
```

The lineage is the record itself (dataset + job); the reference assets get nothing stamped. **The engine sees it through its `loras`
folder:** `ensure_mounted(record)` copies the file to `<models_root>/loras/projects/<project_id>/<id>.safetensors` when it is missing or
its sha differs — a rebuildable cache (house rule 4); `lora_name` for the loader is `projects/<project_id>/<id>.safetensors` (ComfyUI
lists subfolders). Why not mount the project folder: `extra_model_paths.yaml` is read when the engine starts, so a project switch would
need an engine restart. `Roster.unlisted_files` skips the `projects/` subtree; the Models suite shows the registry instead (3g).

### 3b. `LoraRef` and the chain

`LoraRef {model_id, strength}` is unchanged. A trained LoRA's `model_id` is its record id (`lora-…` is not a roster prefix):
`_validate_models` accepts an id found in the project's registry; `_lora_chain` resolves it to the cache path (3a) and a roster id as
today; the **base check** refuses at submission (422) a LoRA whose `base` is not the recipe's model (a 4B adapter on klein-9b: "Mara v2
was trained for Klein 4B"); `klein-4b` and `klein-base-4b` are the same base, `klein-9b` / `-base-9b` / `-9b-kv` the other. The manifest
records `loras[]` with each file's sha256. Under `open` a trained LoRA on Klein base-4B is open (Apache + Apache + the author's own refs);
the roster entries keep their tags (D26).

### 3c. The training job

`Train` recipe, `kind: "train_lora"`: `{profile_id, version, base: "klein-base-4b" | "klein-base-9b", steps (1 000; 250–3 000),
rank (16; 8 / 16 / 32), resolution (512; 768 as the slower option), lr (1e-4), seed, trigger, name}`. `plan().engine` is False and
a new `plan().gpu` is True: **the queue stops the engine** (`supervisor.stop`) before the trainer starts — `free_cache` is not enough on
16 GB — and the next engine job starts it again through `ensure_running` as today. **Staged by default** (`stage=True`, 09 §3 "Stage",
loom R118 / R123, D10): the Cast page shows the staged card with *Release* and *Cancel*; "Train now" is the same job queued at once.
`_validate_models`: the version has ≥ 4 references, the base weights are on disk, the trainers venv exists (else 422 "run
scripts/trainer-setup.ps1"), the disk guard as for every job.

**Dataset:** `temp/train-<job>/set/` — every asset of the version's reference group (the hero included; the candidates group is not
read) as PNG at ≤ 1 024 px on the long side, plus `<name>.txt` = `"<trigger>, <caption>"`; the caption is `cell_sentence(coverage_cell)`
for an Expand result ("close-up, three-quarter left, neutral expression"), the version's stub for the hero and for a reference without a
cell. `caption_dropout_rate 0.05`, `resolution [512]` (D18: small first; 768 by choice), `cache_latents_to_disk`.

**Config:** loom's exercised yaml shape (`config/loom_zimage_rocm.example.yaml`) with `arch flux2_klein_4b`, `name_or_path
<models_root>/diffusion_models` (ai-toolkit picks the base file in it), `vae_path` (E16), `quantize` + `quantize_te` `qfloat8`,
`low_vram`, `gradient_checkpointing`, `adamw 1e-4`, `save_every 250`, `max_step_saves_to_keep 2`, `disable_sampling true` (sampling is
Generate's job), `training_folder temp/train-<job>/out`. The encoder path becomes a config key (`te_name_or_path` exists in
`ModelConfig`; a one-line patch in `trainers/patches/`, upstreamable) pointing at the HF folder.

**Runner `trainers/loom2_train.py`** (runs in the trainers venv): writes the yaml, launches `run.py`, parses the trainer's progress lines
(`step / steps`, loss, s/it) into a JSON progress file the orchestrator tails, mirrors stderr into `state/logs/train-<job>.log` (never an
unread pipe), samples VRAM every 5 s, writes `done.json {adapter, sha256, steps, peak_vram_gb, s_per_it, wall_s}`. The orchestrator
drives it through an asyncio subprocess; **cancel** terminates the process tree; **resume** is ai-toolkit's own (the next release of the
same job finds the newest checkpoint in `training_folder` and continues — proven by loom) and `job.resumable` stays True until the
finisher runs. The job card: "step 420 / 1 000 · loss 0.38 · 1.6 s/it · 15 min left".

**`TrainFinisher`:** copies the final adapter to `story/loras/<id>.safetensors`, writes the record, `ensure_mounted`, sets the version's
`lora` (the `trigger` was set at submission) — a retrain moves the old id into `previous`; events `story.changed {kind: profile}` and
`lora.changed`. Delete = the record, the file, the cache copy, the version's slot cleared (askConfirm, "3 jobs' manifests name it").

### 3d. Readiness — advisory (loom P2's meter, D10)

`readiness(version)` in `story.py`: references (≥ 12 good, ≥ 24 strong), shot-size rows covered (of 4), angles (≥ 3), expressions (≥ 2),
a hero, captions available (a cell on ≥ 80 %), duplicates by sha → a 0–100 score with sentences. The Cast version page shows it on the
*Train* step: "ready 72 — 18 refs, 4 rows, 3 angles; more expressions would help". **Never a gate:** Train is offered from 4 references.

### 3e. Generate's LoRA slots (09 §3b)

The "LORA SLOTS (D25)" section comes alive: **four slots**, each a picker and a strength (0–1.5, step 0.05). The picker lists the
project's trained LoRAs that fit the model first ("Mara v2 · Klein 4B · 1 000 steps"), then the roster's `role: lora` entries of the
family that are not preset toggles (Turbo and Lightning stay toggles; the IC-LoRA and the guide LoRAs stay in their recipes); strength
defaults from the record (0.8 trained, 1.0 roster). "+ trigger" on a trained slot inserts the trigger at the prompt's start (one click;
the mention path does it by itself, 3f). `GET /loras?model_id=` is the list the pickers show (T8: what the worker will load, with
health); the recipe preview shows the chain; the manifest records it. Under `open` the roster entries are filtered as everywhere.

### 3f. Mentions (D73 / D85)

`@Mara` whose current version has a `lora`: `resolve_mentions` appends `LoraRef(<id>, 0.8)` when the recipe's model has the LoRA's
base, a slot is free and the id is not already there, and the mention stub carries the trigger ("Mara (mara_7f3a)"). The panel shows
the chip "LoRA mara_7f3a · 0.8 from @Mara v2 · ×" — dropping it is remembered for that prompt. Expand never adds it (§1).

### 3g. The Models suite

A **Trained (this project)** group under the roster listing: name, base, steps, size, sha, "used by n jobs", *Show in Cast*, *Delete*
(askConfirm). The `projects/` subtree is left out of *unknown files*.

### 3h. Identity check — optional, advisory (11 §6's FaceSim)

*Check ▶* on a trained character queues 8 Iterate-tier T2I jobs (4 coverage sentences × with / without the LoRA, fixed seeds, the
trigger in the prompt) into a "LoRA check" group on the version's candidates page; when they land, FaceSim (present when
`scripts/fetch_facesim.py` ran) scores them against the hero and the record gets `identity {with, without, hero_refs_band}` — a line
on the version page ("identity 0.41 with · 0.08 without · the refs' own band 0.45–0.70"). Never a gate; absent without the weights.

## 4. Data and API

| Route | What |
| --- | --- |
| `GET /story/loras` · `GET /story/loras/{id}` · `DELETE /story/loras/{id}` | the registry (3a) |
| `POST /story/profiles/{id}/train` `{version?, base, steps, rank, resolution, lr, seed, name, stage}` | → the job (staged by default); 422 with the reason (3c) |
| `POST /story/loras/{id}/check` | 3h's 8 jobs as one batch |
| `GET /loras?model_id=` | the slots' list: trained + roster, filtered by base / family, with health and the default strength |
| `/capabilities.train` | `{available, why, bases[], steps {min, max, default}, ranks[], resolutions[], lr}` — `scripts/settings_audit.py` covers every field |
| events | `story.changed`, `lora.changed {id, profile_id}`, `job.updated` with the trainer's progress text |

Settings: `trainers_python` (default `trainers/.venv/Scripts/python.exe`), `hf_home` (`F:/HF_HOME`, the env the engine already uses).
Records: `story/loras/<id>.json` (3a); jobs of kind `train_lora` in the queue and the catalogue's job index as every job.

## 5. Frontend

- **Cast version page:** the readiness line on the *Train* step; *Train ▶* opens the dialog (base, steps, resolution, name, "stage for
  later" on) → the staged job card inline with *Release* / *Cancel*; the `trigger` / `LoRA` slots filled; *Retrain*, *Delete LoRA*,
  *Use in Generate* (opens Generate with the slot and the trigger), *Check ▶* (3h). Commands `story.cast.train`, `story.cast.useLora`,
  `story.cast.deleteLora`, `story.cast.checkLora` — buttons, as D32 asks.
- **Generate:** the slots (3e) in the Model tab; the mention chip (3f); the preview's chain line. Commands `gen.lora.add`, `gen.lora.remove`,
  `gen.lora.trigger`.
- **Models:** the Trained group (3g); `models.lora.delete`, `models.lora.showInCast`.
- **Jobs:** the train job's card with the progress text and the log tail; the staged state as today.

## 6. Slices

| Slice | What | Days |
| --- | --- | --- |
| **E16** | the spike (§2) | 3 |
| **LT1 · slots live** | `_validate_models` + `_lora_chain` for roster and registry ids with the base check, `GET /loras`, the Generate slots, preview and manifest; tests; the smoke scenario (a roster LoRA in a slot, the fake engine's graph carries the loader node) | 2 |
| **LT2 · the training job** | `trainers/` (submodule at the pin, patches, constraints, `scripts/trainer-setup.ps1`, the runner), the `Train` recipe, `plan().gpu` + the engine stop, the dataset materialiser and captions, progress / cancel / resume, `TrainFinisher`, the registry + `ensure_mounted`, readiness, the Cast UI, the Models group; tests on a **fake trainer** (a stub the runner launches instead of `run.py`: it prints steps and writes a 1 KB safetensors; the kill / resume path included); the smoke scenario | 5 |
| **LT3 · mentions, the check, acceptance** | 3f, 3h, `scripts/lt_acceptance.py` on the rig (§8); 09 / 17 / 12 / 08 updated, D86 closed | 3 |

≈ 13 d; LT1 can start during E16 (it needs no trainer). Gate: D86 approved; E16 GO before LT2.

## 7. Tests

- **Offline:** the registry round trip and `ensure_mounted` (missing / stale / same); `_validate_models` with a registry id, a wrong
  base (422), an unknown id; `_lora_chain` on klein-4b with a registry + a roster LoRA (graph parity fixture); `GET /loras` filtered;
  the dataset materialiser (captions from cells, the stub fallback, the PNG size cap); the `Train` job on the fake trainer end to end
  (staged → release → progress lines → done → the record, the version's slot, the events), cancel mid-run, a relaunch resume (the
  checkpoint found); the finisher's retrain (`previous`); readiness on fixtures; `resolve_mentions` adding the LoRA and respecting a
  full slot set; the `open` variant; the settings audit and route snapshot.
- **Unit (Vitest):** the slot picker's filtering, the trigger chip, the readiness rendering, the mention chip.
- **Smoke (Playwright):** "a lora (18)": the SY1 fixture's version → Train ▶ (staged) → Release → the fake trainer's job to done → the
  version page shows trigger + LoRA → Generate with @Mara shows the chip and the slot → a job's recipe carries `loras[]`.

## 8. Acceptance checklist (`scripts/lt_acceptance.py`, rig)

1. E16's bars (§2) hold again inside the app: *Mara* v1 from the SY1 run's refs, 1 000 steps as a staged job released from the Cast
   page; peak VRAM, s/it and wall time on the job card and in the record.
2. A kill of the orchestrator at step ≈ 300 and a relaunch on its state: the job back to staged / queued (resumable), the release
   continues from the step-250 checkpoint, the adapter lands.
3. Generate: the slot lists *Mara v1*; a 1024×576 Iterate image with the trigger shows her; FaceSim ≥ 0.30 and ≥ base + 0.20
   over 8 seeds (3h's check through the app).
4. `@Mara` in a prompt without a slot set adds the LoRA and the trigger (the chip); `×` drops it; the manifest records `loras[]`.
5. A wrong base refused at submission with the sentence; the open variant trains and loads the same (klein-base-4b, Apache).
6. The Models suite lists the LoRA under Trained; Delete removes the file, the record and the cache copy.

## 9. Defaults to approve (D86)

1. **Base:** Klein base-4B for both variants; 9B base only as a per-job choice if E16d stays under 15 GB.
2. **The encoder for training** is the `Qwen/Qwen3-4B` transformers folder (7.5 GB, Apache-2.0) in `F:/HF_HOME` — a second copy of
   the encoder beside ComfyUI's single file; the 8B folder (15.3 GB) only for E16d.
3. **ai-toolkit** as a submodule at a pin under `trainers/ai-toolkit` with `trainers/patches/` and `trainers/constraints.txt`, its own
   venv `trainers/.venv` (Python 3.12, the engine's ROCm torch wheels) by `scripts/trainer-setup.ps1`; the engine venv is never touched.
4. **A trained LoRA lives in the project** (`story/loras/`), cached under `<models_root>/loras/projects/<project_id>/` for the engine.
5. **Training jobs are staged by default**; the engine is stopped for them and restarted by the next engine job.
6. **Recipe defaults:** 1 000 steps, rank 16, 512², lr 1e-4, qfloat8, batch 1, captions = trigger + the coverage sentence, sampling
   off, strength 0.8 at use; the trigger `<name-slug>_<4 hex>`.
7. **`@mention` adds the LoRA** when the base matches (droppable per prompt); Expand never loads one.
8. **Readiness is advisory**; Train is offered from 4 references.
9. **Not in v1:** style LoRAs, video LoRAs, encoder training, DoRA / LoKr.
