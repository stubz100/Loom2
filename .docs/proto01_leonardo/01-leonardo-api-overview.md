# 01 · Leonardo.Ai Production API: what loom2 needs to know

A condensed reading of the mirrored documentation (`source/`, captured 2026-10-08), restricted to what an integration in
loom2's orchestrator touches. Every claim cites the mirrored file it comes from. Items marked **unverified** are absent or
contradictory in the docs and must be settled by the probe in 04 slice L0.

## 1. Two API generations, one integration

| | v1 (`https://cloud.leonardo.ai/api/rest/v1`) | v2 (`https://cloud.leonardo.ai/api/rest/v2`) |
| --- | --- | --- |
| Role today | account, uploads, **reading results**, legacy SDXL / Phoenix / Motion endpoints | **all current models** (79): image, video, upscale, background removal, audio, 3D |
| Model selection | `modelId` UUID per platform model | `model` string discriminator (`flux-pro-2.0`, `kling-3.0`, …) |
| Spec in the mirror | `source/reference-v1/*.md` (one OpenAPI document embedded per endpoint) | `source/openapi-v2-creategeneration.json`, `-createsyncgeneration.json`, `-getmodels.json` |

loom2 only needs **v2 for creation** and **v1 for everything around it**:

| Call | Endpoint | Source |
| --- | --- | --- |
| Create a job (async) | `POST /v2/generations` → `{generationId, apiCreditCost}` | `reference/creategeneration.md` |
| Create a job (sync, ≤ ≈ 27 s, `remove-bg` only today) | `POST /v2/generationssync` → `{id, results[{url \| dataB64, contentType, width, height}], cost{amount, unit}, blockedCount}` | `reference/createsyncgeneration.md`, `docs/remove-bg.md` |
| List models with their parameter schema | `GET /v2/models` → `productionApiAvailableModels[{id, name, parameters}]` | `reference/getmodels.md` |
| Read a job | `GET /v1/generations/{id}` → `generations_by_pk{status, generated_images[{id, url, nsfw, motionMP4URL, …}], seed, prompt, …}` | `reference-v1/getgenerationbyid.md`, `docs/api-faq.md` |
| Delete a job (and its outputs on Leonardo) | `DELETE /v1/generations/{id}` | `reference-v1/deletegenerationbyid.md` |
| Upload an image (presigned S3) | `POST /v1/init-image {extension}` → `uploadInitImage{id, url, fields}`, then a multipart POST to `url` **without** the API key → 204 | `recipes/uploading-an-image.md`, `reference-v1/uploadinitimage.md` |
| Upload video / audio (for video-reference models) | `POST /v1/media {extension, originalFilename?}` → `uploadMedia{uploadId, url, fields}` | `reference-v1/uploadmedia.md` |
| Delete an uploaded image | `DELETE /v1/init-image/{id}` | `reference-v1/deleteinitimagebyid.md` |
| Account and balance | `GET /v1/me` → `user_details[{user{id, username}, apiConcurrencySlots, apiPaidTokens, apiSubscriptionTokens, …}]` | `reference-v1/getuserself.md` |
| Cost estimate before running | `POST /v1/pricing-calculator {service, serviceParams}` → `calculateProductionApiServiceCost.cost` | `reference-v1/pricingcalculator.md` |

The official SDKs (`Leonardo-Interactive/leonardo-python-sdk`, `leonardo-ts-sdk`; `docs/leonardoai-official-sdks.md`) are
generated clients. loom2 does not need them: the orchestrator already depends on `httpx`, the call surface above is ten
requests, and a hand-written client keeps the request body that loom2 records as provenance byte-exact.

## 2. Authentication

- One header: `authorization: Bearer <api_key>`; the key is a UUID (`docs/api-error-messages.md`, "Invalid response from
  authorization hook"). Production keys are created at app.leonardo.ai → API Access; at most 10 keys per account
  (`docs/api-faq.md`).
- API access is billed separately from web-app plans (`docs/getting-started.md`). "Do not embed it in client-side code" — in
  loom2 terms: the key never reaches the webview (03 §5).
- The presigned S3 upload must be sent **without** the authorization header; adding it causes 403
  (`docs/api-error-messages.md`).

## 3. The generation lifecycle

```
POST /v2/generations {model, public:false, parameters}          → 200 {generationId, apiCreditCost}
   (inputs referenced inline: image.type = BASE64 | URL, or by id: UPLOADED / GENERATED)
loop: GET /v1/generations/{generationId}                         → generations_by_pk.status
   PENDING  → generated_images = []                              (keep polling with back-off)
   COMPLETE → generated_images[].url  (images; durable CDN URLs, "do not expire")
              generated_images[].motionMP4URL (video)
   FAILED   → error
download each URL (no auth header needed on the CDN)              → bytes into loom2
```

- **Inputs without an upload step.** v2 image references accept `type: BASE64` with `data`, or `type: URL` with a data URL
  (`openapi-v2-creategeneration.json`, every `guidances.*.image`). For one-off inputs (an Edit region, an Animate start frame)
  loom2 can inline the bytes and skip the presigned round trip. The request-size limit is not documented (**unverified**);
  above it, fall back to `POST /v1/init-image` and `type: UPLOADED`.
- **Outputs as inputs.** An image generated on Leonardo can be referenced by its image id with `type: GENERATED`; loom2 records
  that id on the asset so a chain of cloud jobs does not re-upload.
- **Statuses.** `PENDING`, `COMPLETE`, `FAILED` (`docs/api-faq.md`). There is no progress percentage and no preview — loom2
  shows elapsed time against a per-model typical duration instead (03 §3c).
- **Webhooks** exist (`docs/guide-to-the-webhook-callback-feature.md`) but require a public **HTTPS** URL configured on the
  key, called from six fixed AWS IPs. A desktop app on a home connection has none, so **loom2 polls**. Recorded so nobody
  re-litigates it; it changes only if loom2 ever runs a relay.
- **Output shapes for audio and 3D are unverified.** The v1 read schema predates them (`generated_images[].url` and
  `motionMP4URL` only). The probe (04 L0) records one real response per modality into `fixtures/`.
- **Cancel** does not exist. `DELETE /v1/generations/{id}` deletes a generation; whether it stops a running one and refunds
  is **unverified** — loom2 treats cancel as "stop waiting, delete when finished" (03 §3d).

## 4. Moderation

- Prompts are filtered **before** the job: `400` / `403` with `{"error": "content moderation filter: <word>", "code":
  "unexpected"}` or "Your prompt appears to contain inappropriate content…" (`docs/guide-to-handling-not-safe-for-work-image-generation-nsfw.md`,
  `docs/api-error-messages.md`).
- Outputs carry `nsfw: true|false`; the sync API withholds flagged outputs and reports `blockedCount`. loom2 surfaces both as a
  job error or a partial result, never as a silent empty batch.

## 5. Limits

From `reference-v1/limits.md` and `docs/guide-to-concurrency-queue-and-rate-limit.md` (defaults, raisable on a custom plan):

| Limit | Default |
| --- | --- |
| Concurrent generation jobs (image, video, 3D each) | 10 |
| Pending image jobs | 200 (20 per concurrency slot) |
| Pending upscales / 3D jobs | 100 each |
| Requests, all endpoints | 2000 / min |
| Create requests (`/v1/generations`, `/v2/generations`, upscaler, nobg, …) | 100 / min each |

Polling must stay well inside 2000 requests/min across every running job; loom2's poller is one task with a shared budget
(03 §3d). Excess jobs simply queue on Leonardo's side, so loom2 needs no concurrency logic beyond a small cap of its own.

## 6. Errors worth mapping

| Response | Meaning | loom2 reaction |
| --- | --- | --- |
| `{"error": "Invalid response from authorization hook"}`, `"Authentication hook unauthorized this request"` (`access-denied`) | bad or missing key | job fails "Leonardo key rejected"; provider marked unavailable; Settings banner |
| `400` "content moderation filter: …" / `403` "inappropriate content" | prompt blocked | job fails with the filter word; **not retried** |
| `400` "Too many images" | quantity above the model's maximum | prevented by validation against the model schema |
| `"invalid file extension"` / `403` on the S3 POST | upload misuse | client bug; fail loudly |
| `"couldn't access image"` / `"failed to find init variation"` / `"invalid init image id"` | wrong id kind (UPLOADED vs GENERATED) | client bug; fail loudly |
| `429` | rate limit | back-off and retry inside the job, not a failure |
| `5xx`, timeouts | provider trouble | retry with back-off a bounded number of times, then fail; never re-create a generation that may exist (03 §3d) |
| balance exhausted | "API requests will pause until additional credit is added" (`docs/pricing-and-plans-faq.md`); the exact response is **unverified** | job fails "Leonardo balance empty", cloud lane pauses |

## 7. Privacy and retention

- Every request carries `public: false`; otherwise outputs appear in Leonardo's community feed.
- Generated outputs "will not expire and can also be accessed from the Web App" (`docs/api-faq.md`). loom2 copies them into the
  project (the files are the truth, 06 §4) and may delete the generation on Leonardo afterwards (03 §5, setting).
- Uploaded inputs stay on Leonardo until deleted (`DELETE /v1/init-image/{id}`); inline BASE64 inputs avoid creating them.
- The account is EU-resident in practice (the author), the service is not: Leonardo's terms govern what leaves the machine.
  loom2 states plainly in the UI that a cloud job sends the prompt and the input images to Leonardo (03 §5).

## 8. Money

- Billing is **pay-as-you-go in US dollars** from a prepaid balance, optional auto top-up (`docs/payg-guide.md`,
  `docs/pricing-and-plans-faq.md`); the balance does not expire.
- Every create returns the job's cost: `apiCreditCost` (async) or `cost{amount, unit: CREDITS | DOLLARS}` (sync). The webhook
  example also shows `apiDollarCost` on the generation. loom2 records the returned cost on the job and on each asset.
- **Before** running, the only machine-readable estimate is `POST /v1/pricing-calculator`, whose `service` enum predates most
  v2 models (**unverified** for v2 models). Fallback: a per-model price table that loom2 learns from the costs it has been
  charged (03 §4c).
- `GET /v1/me` reports the balance fields (`apiPaidTokens`, `apiSubscriptionTokens`); how dollars map onto them under PAYG
  is **unverified**.

## 9. Change management

- The v2 spec is generated from Leonardo's own model registry (`x-generated-notice` in the JSON) and changes often: five
  deprecations in three months, 2–4 weeks' notice (`docs/deprecations-changes.md`).
- `GET /v2/models` returns each model's parameter schema at runtime. loom2 can validate against it live and compare it with
  the mirrored spec to detect drift — the cloud equivalent of the ComfyUI `/object_info` contract check (06 §3b).
- `tools/mirror_docs.py` re-captures the documentation; `tools/model_matrix.py` regenerates 02 §3.
