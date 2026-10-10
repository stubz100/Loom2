# 04 · Development plan: Leonardo in loom2

Status: **proposal, 2026-10-08**, not started. It follows the house rules of `../proto01/12-roadmap.md`: a spike retires the
unknowns before code depends on them, every slice ends with offline tests **and** a rig (here: live) acceptance run, and
measurements go to `../proto01/90-journal.md` with real timestamps. Nothing starts before LD1 (05) is accepted.

## Overview

| Slice | Goal | Depends on | Effort (focused days) | Live spend |
| --- | --- | --- | --- | --- |
| **L0** | Probe spike: answer every **unverified** item in 01 with real responses | LD1, an API key with a small balance | 0.5–1 | ≈ USD 3–5 |
| **L1** | Extract the engine seam from `JobQueue._run_one`, no behaviour change | — (can run in parallel with L0) | 1–1.5 | — |
| **L2** | Client, cloud registry, key storage, fake server, contract test | L0, L1 | 1.5 | — |
| **L3** | Cloud lane + Generate (T2I) end to end, spend guard, Settings | L2 | 2–2.5 | ≈ USD 3 |
| **L4** | Animate: cloud I2V with first / last frame, H3 card | L3 | 2 | ≈ USD 5–10 |
| **L5** | Edit: instruct edit with loom2 paste-back, cloud upscale, remove-bg select | L3 | 2–2.5 | ≈ USD 3 |
| **L6** | Catalogue, drift detection, hardening, docs | L3–L5 | 1 | — |

About 10–12 focused days in total. L4 and L5 are independent and can swap order: L4 first if the H3 hero tier matters
more than Edit, L5 first if cloud inpainting does.

## L0 · Probe spike

**Deliverable:** `scripts/leonardo_probe.py` (stdlib + httpx, key from `LEONARDO_API_KEY`) and
`orchestrator/tests/fixtures/leonardo/*.json`, the recorded responses, with the key and URLs redacted.

| # | Question (01 marks it **unverified**) | Probe |
| --- | --- | --- |
| P1 | Response shape of `GET /v1/generations/{id}` for v2 image, video, upscale jobs | one `flux-pro-2.0` 1-image job, one `kling-3.0` 5 s 720p job (or `hailuo-03` 768p), one `aurora-upscaler-precise` ×2 |
| P2 | Does inline `type: BASE64` work for `image_reference` and `start_frame`, and up to what body size? | refs of 0.5, 2, 8 and 16 MB; record the first failure |
| P3 | Does FLUX.2 Pro take the BFL JSON prompt verbatim? | the same bench prompt as JSON and as prose, `prompt_enhance: OFF`; compare by eye and record `generations_by_pk.prompt` |
| P4 | Is the seed reported back, and does a fixed seed reproduce? | two identical requests with `seed` |
| P5 | What does `DELETE /v1/generations/{id}` do to a PENDING job (stop? refund?) | delete a video job right after create; read `/v1/me` before and after |
| P6 | Recovering a create whose response was lost | `GET /v1/generations/user/{userId}?limit=5` (v1 `getgenerationsbyuserid`) to find it by prompt and time |
| P7 | Cost: does `apiCreditCost` arrive in dollars or credits under PAYG; how does `/v1/me` show the balance; does the pricing calculator know v2 models? | read all three around one job |
| P8 | Typical latency per model (queue and render) | timestamps from P1, and `createdAt` → `updatedAt` |
| P9 | Error bodies for a bad key, a moderated prompt and (if cheap to provoke) an empty balance | three requests |
| P10 | Sync endpoint: `remove-bg` with `base64: true` and `ephemeral: true` | one 1 MP image |

**Gate:** every row answered in a journal entry; 01 and 03 amended the same day where an answer changes them (the house
rule in `../proto01/00-README.md`); the price observations seed `price_hint` for L3.

## L1 · Engine seam (no behaviour change)

- `orchestrator/loom2/engine/base.py`: the `Engine` protocol (03 §2a). The current ComfyUI path in `_run_one` moves behind
  `ComfyEngine` (prepare inputs / start / follow / outputs / cancel); `JobQueue` keeps scheduling, guards, finalisers and
  events.
- `JobRecord.engine` set at `submit()`; `prompt_id` generalised as `remote_id` (read `prompt_id` from old `queue.json` files —
  the durability rule says old files must still load).
- The finalisers take a list of local files plus the `Compiled` summary and no longer reach into ComfyUI history.

**Gate:** the whole offline suite unchanged and green (115 tests collected on 2026-10-08), `tsc -b` clean, a rig smoke of one
Generate, one Edit inpaint and one Animate draft clip with timings within noise of the last journal numbers.

## L2 · Client, registry, key, fake server

- `engine/leonardo/client.py` (httpx.AsyncClient, timeouts, 429 / 5xx back-off, redacting logger), `registry.py` +
  `models.json` (seeded from 02 §2: about 12 models), `compile.py` (recipe → body, JSON-schema validation; add `jsonschema` to
  the orchestrator's dependencies or a 100-line subset validator — decide in the slice).
- Key: `keyring` dependency, `PUT/DELETE /providers/leonardo/key`, `POST /providers/leonardo/test`, `GET /providers`;
  `Settings.leonardo` without the key.
- `tests/fake_leonardo.py` with the behaviours in 03 §5; fixtures from L0.
- Contract test: registry vs `.docs/proto01_leonardo/source/openapi-v2-creategeneration.json`.

**Gate:** offline tests for client, compile, registry contract and key handling (the key never appears in `/settings`,
`/providers`, logs or job records); `scripts/csp_check.py` unchanged and green.

## L3 · Cloud lane and Generate

Orchestrator:
- `LeonardoEngine` (inputs inline / upload, create, poll with a shared request budget, download into
  `engine_out/loom2/<job_id>_*`, cost capture); the cloud lane runner with `max_concurrent`; resume-not-recreate on reload;
  cancel semantics; provider pause; `provider.state` events.
- T2I mapping (03 §2d); `/capabilities` gains `cloud.leonardo.models{…}` when enabled; `/recipes/preview` returns `cost_usd`
  and `typical_s` for cloud recipes.
- Spend ledger and guard (03 §2h).

Frontend:
- Settings → Cloud providers; Generate picker driven by capabilities (retires the hard-coded order list in
  `GenerateSuite.tsx`); per-model size presets, quantity, extras; cost confirmation modal; job dock cost and elapsed display.

**Gate (offline):** lane concurrency, durability (kill during poll → relaunch paused → resume → exactly one create in the fake's
log), cancel, spend cap refusal, NSFW prompt and output, 429 recovery, `open` variant with cloud enabled.
**Gate (live, `scripts/leonardo_acceptance.py generate`):** FLUX.2 Pro, Nano Banana Pro and Lucid Origin on three bench prompts
(`bench/`), one with two references from the Catalogue; assets carry the provider block; lineage edges to the references;
a kill-and-relaunch during a job charges once (ledger and `/v1/me` agree); times and costs recorded in the journal.

## L4 · Animate

- I2V mapping for cloud ids (duration in seconds, resolution pairs or follow-the-start-frame, `end_frame`, audio off);
  MP4 → PNG master (PyAV) → `ClipStore.create` → GOP-6 proxy; `source.mp4` kept next to the master.
- Animate cards from capabilities (cloud ones behind the provider); the locked **H3 card** becomes the `hailuo-03` card when
  the provider is enabled; `MODEL_RULES` keeps the local Wan / LTX rules and reads cloud rules from capabilities.

**Gate (live):** one FLF clip from two Catalogue stills on `hailuo-03`, `kling-3.0` and `veo-3.1-fast-generate-001` at their
cheapest 720p-class setting; frame-accurate scrub on the proxy, frame extraction to the Catalogue with `frame-extract`
lineage, FaceSim recorded where a face is present (`../proto01/11-ui-suite-animate.md` §6, the E4 protocol); wall time and cost per clip compared with the
local Wan draft numbers in the journal.

## L5 · Edit

- `InstructEdit` recipe + `/documents/{id}/ai` kind; the region crop from `_prepare_document_inputs()` goes out as
  `image_reference[0]`, the result is resized to the plan and pasted back through the feathered selection as a layer in the
  AI group (`document.changed`).
- Cloud upscalers in the Upscale op (`aurora-*`, factor 2–8); `remove-bg` as an engine choice for AI Select · Subject (sync
  endpoint, alpha → selection, joined with `op`).
- Edit AI panel options from capabilities instead of the hard-coded `<select>` lists in `EditSuite.tsx`.

**Gate (live):** the five inpaint bench tasks (`../proto01/04-model-strategy.md` §6) through `flux-kontext-pro` and
`gemini-image-2`, scored against the recorded Klein + LanPaint results (E8); pixels outside the selection unchanged (by
construction — asserted with the compare endpoint); one ×4 Aurora upscale of a draft; one remove-bg subject selection.

## L6 · Catalogue and hardening

- Catalogue Source chip "Leonardo", Inspector provider block, tile-menu "Copy generation id".
- Drift: at provider enable and once a day, `GET /v2/models` vs the registry; a changed schema marks the model "check" in the
  picker and logs the diff; a missing model becomes `retired` with a readable job error.
- Optional `delete_remote_after_download`; uploaded inputs deleted after the job.
- Docs: `../proto01/03-vision-scope-and-mvp.md` §4 (non-goal amended), `06` §1 / §3d / §11 (second engine, variants), `13` (LD decisions moved in as
  D35+ and the backlog), `00-README` reading order, `07` / `09` / `10` / `11` for the UI changes; this folder's status lines.

**Gate:** offline suite green for both variants in CI; one full live acceptance run (L3–L5 scripts) appended to the journal.

## Later (not planned)

| Item | Why later |
| --- | --- |
| Audio (`music-v1`, `sound-effects-v2`, `dialogue-v3`) | needs a sound model in clips; belongs to the Story workspace (14) |
| 3D (`rodin-v2`) | no 3D surface in loom2 yet |
| Video edit (`kling-video-o-3`, `wan-2.7` `omni_edit`) | needs `POST /v1/media` uploads and a clip-as-input verb in Animate |
| Webhooks | need a public HTTPS endpoint; polling is enough at loom2's volume |
| A second provider (fal, Replicate, BFL direct) | the `provider` field and the `Engine` protocol leave room; no demand yet |

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Model churn breaks a wired model (five deprecations in three months) | high | registry as data, daily drift check, readable failure, mirror re-run at milestone start |
| Double billing after a crash or a lost create response | medium | `remote_id` persisted before the first poll; resume, never re-create; P6 recovery by listing |
| Spend surprises | medium | cap + confirm threshold + ledger; estimates shown before submit; live test budgets printed by the scripts |
| The key leaks through settings, logs or manifests | low after L2 | write-only route, keyring, redacting logger, tests that grep every surface |
| Cloud results do not match local quality expectations for edits (no mask, whole-image re-render) | medium | paste-back through loom2's mask keeps the outside pixels; bench comparison in L5 decides whether the op ships |
| Scope creep into a cloud-first product | medium | LD1's conditions: local default, opt-in, no automatic fallback; ArtCraft's broader cloud surfaces stay out |
| ToS or content-policy changes on Leonardo's side | low–medium | `public: false`, moderation errors surfaced verbatim, provider can be disabled without touching local work |
