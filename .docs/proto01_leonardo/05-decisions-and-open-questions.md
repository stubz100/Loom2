# 05 · Proposed decisions and open questions

Every entry here is **proposed** (2026-10-08). When the author accepts one, it moves into
`../proto01/13-decision-log-and-open-questions.md` as the next D-number with its date, and the status here changes to point
at it. Ids are local to this folder (LD = Leonardo decision, LQ = Leonardo question).

## Proposed decisions

| Id | Decision | Status | Where | Rationale (short) |
| --- | --- | --- | --- | --- |
| LD1 | **Cloud inference via Leonardo is allowed as an opt-in second engine.** Conditions: local stays the default everywhere, cloud is off until enabled with a key, every cloud model is labelled, there is no automatic fallback from local to cloud, and every job shows what leaves the machine and what it costs. Revises the MVP non-goal "cloud" (`../proto01/03-vision-scope-and-mvp.md` §4), "ComfyUI is the sole engine" (D2 / D28 wording) and the ArtCraft "not copied" row (`../artcraft/07-loom2-comparison.md` §5) | proposed | 03 §1 | adds models a 16 GB card cannot run (H3 without the territorial licence, Kling, Veo, Seedance, Nano Banana, GPT Image) and FHD / 4K output in seconds, without giving up local-first for everything else |
| LD2 | **The orchestrator is the only caller.** The webview never contacts Leonardo, never holds the key and never shows a CDN URL; the CSP stays loopback-only | proposed | 03 §1, §2g | keeps the CSP, the token gate and "pixels over loopback" (D4) exactly as verified |
| LD3 | **Polling, not webhooks** (`GET /v1/generations/{id}` with back-off and a shared request budget) | proposed | 01 §3 | webhooks need a public HTTPS endpoint, which a desktop app does not have |
| LD4 | **Cloud is available in both build variants (`full`, `open`), off by default**; manifests record `provider` next to `variant` | proposed | 03 §4 | D26 filters weights that loom2 distributes; cloud jobs distribute none |
| LD5 | **The API key lives in Windows Credential Manager** (`keyring`, service `loom2/leonardo`), with `LEONARDO_API_KEY` as the fallback; write-only API; never in `app.json`, `/settings`, logs or manifests | proposed | 03 §2g | `/settings` returns the whole settings model today; `app.json` is plain text |
| LD6 | **A cloud model registry separate from the roster**, stored as data, namespaced ids (`leo/<model>`), validated against the mirrored spec in CI and against `GET /v2/models` at runtime | proposed | 03 §2c | the roster's contract is "a weight file with sha256"; cloud models have none, and they change monthly |
| LD7 | **A cloud lane in the queue**: its own runner, a concurrency cap (default 3), no VRAM gate, provider failures pause only that lane; a job with a generation id is resumed after a crash, never re-created | proposed | 03 §2b | a long cloud video must not block the GPU; re-creating would bill twice |
| LD8 | **Mask-less editors become inpainters through loom2's paste-back**: the cropped region goes out, the result comes back resized to the plan and is composited through the feathered selection as a layer. A new `InstructEdit` recipe carries it | proposed | 03 §2d | no v2 model takes a mask; the editor's selection already defines the change, and outside pixels stay untouched by construction |
| LD9 | **Cloud video lands as a PNG master + GOP-6 proxy** (D5), the original MP4 kept as `source.mp4`; `motion_has_audio: false` until clips have a sound model | proposed | 03 §2f | one clip model for both engines; scrubbing and frame extraction keep working |
| LD10 | **Spend guard**: monthly cap (default USD 25), a confirmation over USD 1 or when the estimate is unknown, an app-level ledger, refusal at submit like the disk guard | proposed | 03 §2h | there is no cost concept in loom2 today |
| LD11 | **Provenance defaults**: `public: false` always; `prompt_enhance: "OFF"` by default (the recorded prompt is the prompt that ran); the request body with inline data hashed is the job's compiled record | proposed | 01 §1, 03 §2e | provenance measure (`../proto01/03-vision-scope-and-mvp.md` §6) |
| LD12 | **A hand-written httpx client, not the official SDK** | proposed | 01 §1 | ten calls; byte-exact request bodies for provenance; no generated dependency to pin |

## Open questions (need the author)

| Id | Question | Affects | Proposed default |
| --- | --- | --- | --- |
| LQ1 | Accept LD1 at all — is cloud inference acceptable in loom2, given the earlier "ComfyUI for inference only" rule? | everything | yes, under LD1's conditions |
| LQ2 | Which models make the first shortlist? | L3–L5 scope, cost of acceptance runs | Generate: FLUX.2 Pro, Nano Banana Pro, Lucid Origin · Animate: H3 (`hailuo-03`), Kling 3.0, Veo 3.1 Fast · Edit: Kontext Pro, Nano Banana Pro, Aurora Precise / Creative, remove-bg |
| LQ3 | Monthly spend cap and per-job confirmation threshold | LD10 | USD 25 / month, confirm above USD 1 or unknown |
| LQ4 | After download, delete the generation (and uploaded inputs) on Leonardo? | privacy vs being able to reference outputs by id (`GENERATED`) later | keep generations (needed for cheap chaining), always delete uploaded inputs |
| LQ5 | Does cloud H3 (`hailuo-03`) replace the local H3 plan (D17, post-MVP backlog item 6), or sit beside it? | Animate roadmap, the D17 licence application | beside it: cloud now, local graph stays in the backlog for offline and cost reasons |
| LQ6 | Order of L4 (Animate) and L5 (Edit)? | plan | Animate first: the hero tier is the clearest gain |
| LQ7 | Is the live acceptance budget (≈ USD 15–25 for L0–L5) acceptable, and from which account? | L0–L6 gates | yes, the author's own API account with a separate key named `loom2-dev` |
| LQ8 | Should a second provider be designed for now (fal, Replicate, BFL direct)? | how generic the registry and client are | no — keep the `provider` field and the `Engine` protocol generic, build only Leonardo |

## Volatile facts to re-check at each milestone start

- The model list and parameter schemas (`tools/mirror_docs.py`, then `tools/model_matrix.py` and a diff of 02 §3).
- `source/docs/deprecations-changes.md` for retirements affecting the registry.
- Limits (`source/reference-v1/limits.md`) and pricing (`source/docs/payg-guide.md`, `source/docs/pricing-and-plans-faq.md`).
- Whether a v2 read endpoint (`GET /v2/generations/{id}`) has appeared, which would replace the v1 read.
