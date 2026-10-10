# 02 · Backend architecture — the Rust desktop app and the provider layer

Source: `F:\source\repos\artcraft\crates` at `3e5793b693`. The desktop backend is a Tauri 2 app (`crates/desktop/artcraft`, ~30k
lines in 471 files) on top of a large provider layer (`crates/api_clients`, ~195k lines). Generation itself never runs on the
user's machine: every job is submitted to a cloud service and polled.

## 1. Process and data picture

```
┌──────────────────────── Tauri 2 process (Rust, artcraft_app_lib) ────────────────────────┐
│ main window (WebView, React app)  ·  login webviews (Midjourney, Grok, Sora, WorldLabs)   │
│ billing webview (Stripe)                                                                  │
│                                                                                           │
│ 63 #[tauri::command]s ── one file each ── uniform {status, payload | error_*} envelope    │
│ typed events (BasicSendableEvent) ──► frontend                                            │
│ ~8 supervised async loops: ArtCraft job poller (5 s) · fal poller (2–10 s) · Midjourney   │
│   WS + HTTP reconcile · Grok video/image · WorldLabs · Sora (deprecated) · window/cookie  │
│   sync (1 s) · activity heartbeat · Discord presence                                      │
│ sqlite_tasks (tasks_v7.sqlite, WAL)  ·  ~/Artcraft/{credentials,settings,state,temp,…}    │
└──────────────┬──────────────────────────────┬─────────────────────────────┬──────────────┘
               │ cookie session (vendored     │ BYO API key                  │ user's own consumer
               │ tauri-plugin-http jar)       │ (fal)                        │ sessions (cookies,
               ▼                              ▼                              ▼ browser emulation)
   ArtCraft "Omni Gen" API          fal.ai queue API              Midjourney · Grok · Sora ·
   (api.storyteller.ai) — 62        (artcraft_router builds        WorldLabs · Kinovi web apps
   models, credits, media library,   the typed request)
   CDN, scenes, folders, billing
```

Everything that produces media ends up as an ArtCraft **media file** (`m_…` / `mf_…` token + CDN URL): third-party results are
downloaded and re-uploaded so the library and the UI see one kind of object.

## 2. Startup (`src/lib.rs::run`, `core/lifecycle/startup/*`)

1. **Synchronous bootstrap** (before Tauri; logs via `println!` because the logger is not installed yet):
   `AppDataRoot::create_default()` → `~/Artcraft` with typed subdirectories (`assets/`, `credentials/`, `downloads/`, `settings/`,
   `state/`, `temp/`, each a `DataSubdir` impl); platform info and build metadata; app preferences; a credential loading cache; one
   credential manager per consumer provider loaded from disk; env configs (`settings/env_configs.json` switches production vs
   `localhost:12345`).
2. **`tauri::Builder`** with plugins dialog, the **vendored** HTTP plugin, opener, upload; 15 managed state objects; one
   `generate_handler![…]` listing 63 commands.
3. **`setup`** blocks on `setup_main_window` (window built in code: 2400×1300, frameless on Windows with a drawn title bar, overlay
   title bar + explicit Edit menu on macOS so Cmd+C/V reach WKWebView) and `handle_tauri_startup`, which runs one task per file:
   log plugin, **task DB connect + migrate**, provider priority, the window/cookie sync loop, the provider pollers, Discord presence,
   window size/position restore. Any startup error panics.

Background work is `tauri::async_runtime::spawn` tasks that never return (`-> !`): `loop { inner().await; log; sleep }`. There is no
shared scheduler and no cancellation on shutdown.

## 3. State

All managed types are `Clone` with shared interiors (`Arc<RwLock<…>>`, `CloneCell`, a sqlx pool); the same instance goes to `.manage()`
and into the spawned loops.

| Type | Holds |
| --- | --- |
| `AppDataRoot` | the `~/Artcraft` tree and helpers per subdirectory |
| `AppEnvConfigs` | API host (production or localhost) |
| `AppPreferencesManager` | download dir (system / custom), filename template, auto-download, sounds → `settings/app_preferences.json` |
| `TaskDatabase` | `sqlite_tasks::TaskDbConnection` (§5c) |
| `ProviderCredentialLoadingCache` | BYO credentials read lazily from `credentials/<provider>.api_key.txt`, 300 s TTL |
| `StorytellerCredentialManager` | ArtCraft session + visitor cookies, mirrored from the HTTP plugin's jar every second |
| `DesktopLoginBridgeState` | pending device-code login challenges (≤ 8) |
| `Sora/Midjourney/Grok/WorldlabsCredentialManager` | cookies, bearers, refresh tokens per consumer provider |
| `ArtcraftUsageTracker` | in-memory usage counters for the heartbeat |

## 4. Commands and the response contract

**One command per file**, named after the command (`storyteller_create_login_challenge_command.rs`); `mod.rs` files only declare;
command bodies delegate to a private `handle_request`. The convention is written into `services/storyteller/commands/AGENTS.md`.
Code is organised as **vertical provider slices** — `services/<provider>/{commands,state,threads,windows}` — with cross-cutting
infrastructure in `core/`.

| Area | Commands (63 registered) |
| --- | --- |
| Generation | `generate_{image,video,splat,mesh,audio}_command`, `enqueue_image_bg_removal_command`, `enqueue_image_to_3d_object_command`, `enqueue_image_to_gaussian_command` |
| Catalogue | `list_image_models_command`, `list_video_models_command` (proxy, retry, 60 s cache, serve stale on failure) |
| Cost | `estimate_{image,video,splat,audio,mesh}_cost_command` → `/v1/omni_gen/cost/{modality}` |
| Tasks | `get_task_queue_command`, `mark_task_as_dismissed_command`, `tasks_nuke_all_command` |
| Media/files | download to the user's folder, reveal, delete, flip image, `load_without_cors_command` (fetch any URL from Rust — no allowlist) |
| App | app info (version, build time, git SHA), platform info, preferences |
| Providers | BYO keys (`provider_list/set_api_key/clear`), consumer logins per provider (open login window, credential info, clear) |
| Account | password login/signup, **device-code login challenge** (create/poll/cancel), credits, subscription, Stripe checkout/portal windows |

**Envelope** (`core/commands/response/`): success `{status: "success", success_message?, payload?}`; error `{status:
"bad_request" | "unauthorized" | "too_many_requests" | "server_error", error_message?, error_type?, error_details?}`. Commands
return `Result<CommandSuccessResponseWrapper<T>, CommandErrorResponseWrapper<ET, EP>>`; Tauri serialises `Err` as a rejected
promise, so the frontend reads one shape either way. `shorthand.rs` defines aliases (`SimpleResponse`, `ResponseOrErrorType<S, ET>`,
`InfallibleResponse<S>`). Generation errors carry typed `error_type`s (`NeedsFalApiKey`, `NeedsMidjourneyCredentials`,
`BillingIssue`…) that the UI turns into the right modal. Debt: some commands still return `String` errors or Rust `{:?}` text.

## 5. The generation pipeline

### 5a. The Omni passthrough (current path)

All `generate_*` / `estimate_*` commands take an `OmniRequest`:

```rust
pub struct OmniRequest {
  pub provider: Option<GenerationProvider>,
  pub frontend_caller: Option<TauriCommandCaller>,
  pub frontend_subscriber_id: Option<String>,
  pub frontend_subscriber_payload: Option<String>,
  #[serde(flatten)] pub fields: Map<String, Value>,   // everything else is owned by the API
}
```

The desktop does **not** validate models or options: it forwards the JSON (with a few renames and legacy id mappings), so a new
server-side model needs no desktop release. Unit tests assert that unknown future models and fields pass through unchanged.
`omni::generate` (`core/commands/generate/omni/dispatch.rs`):

1. require ArtCraft credentials (else emit an error event and return 401 `needs_storyteller_credentials`);
2. upload any raw bytes in the request (canvas, scene, mask) as media files and substitute their tokens;
3. add an `idempotency_token` if missing;
4. `POST /v1/omni_gen/generate/{image|video|mesh|splat|audio}`;
5. for every returned job token, insert a **task row** (`provider = Artcraft`, `provider_job_id`) carrying the frontend's
   subscriber id and payload, emit `generation-enqueue-success-event`, then `credits_balance_changed_event`.

### 5b. Native / BYO paths (legacy)

When the provider is not ArtCraft, the request is decoded into a typed struct: Midjourney uses the user's own session; anything else
goes through **`artcraft_router`** (§7) with the BYO credential — only fal is implemented: build the typed fal request, create a
prompt record on ArtCraft for provenance, submit to fal's queue, store `queue_status_url` / `queue_response_url` in the task row.
`adapt_legacy_response` converts typed responses to the Omni JSON shape so the frontend has one contract.

### 5c. Task persistence (`crates/schema/database/sqlite_tasks`)

- `~/Artcraft/state/tasks_v{N}.sqlite` (currently v7), WAL, `sqlx::migrate!` with the migrations **compiled into the binary**, queries
  via compile-time-checked `query!` / `query_as!` with an offline `.sqlx/` cache (builds use `SQLX_OFFLINE=true`).
- **Schema evolution by file name:** the single migration file is edited in place and the version constant bumped, which creates a new
  empty DB — task history is treated as disposable. The migration header warns that forgetting the bump "will cause Windows to segfault
  at start".
- `tasks` columns: `id` (prefixed Crockford token), `task_status`, `task_type`, `model_type`, `provider`, `provider_job_id` (UNIQUE),
  `prompt_token`, `frontend_caller`, `frontend_subscriber_id`, `frontend_subscriber_payload` (opaque JSON echoed back),
  `is_dismissed_by_user`, fal queue URLs, `on_complete_*` (batch token, primary media token/class/CDN URL/thumbnail template),
  `on_failure_type` / `_message`, timestamps.
- Statuses: `pending`, `started`, `complete_success`, `complete_failure`, `attempt_failed`, `dead`, `cancelled_by_{user,provider,us}`.
  Stored enums are snake_case strings with hand-written `to_str`/`from_str`; `TaskModelType` has an **`Unknown(String)`** variant so
  future model ids survive.

### 5d. Polling and completion

| Loop | Behaviour |
| --- | --- |
| ArtCraft jobs (5 s) | list the session's jobs, join with local rows by `provider_job_id`; 60 s back-off on 429, 30 s on errors. On success: **auto-download first (must succeed, else retry next pass)** → store result metadata → clear the download checkpoint → typed per-task-type event → `generation-complete-event` |
| fal (10 s idle, 2 s when active) | poll the status URL; on completion download each result to `temp/`, **re-upload to ArtCraft** tied to the prompt token (batch token when several), update the row, emit events |
| Midjourney | one worker combining a WebSocket (per-job subscription, reconnect every 60 s) with **HTTP reconciliation every 15 s** — covers missed frames and jobs created before a restart |
| Grok, WorldLabs, Sora | similar per-provider loops; Sora's is `#[deprecated]` and only drains legacy tasks |

**Auto-download** (`core/utils/auto_download.rs`): when enabled, every completed result is saved to the user's download folder with a
filename template; a JSON **checkpoint** per task (temp file → `sync_all` → persist) records finished files so a retry skips them;
`persist_noclobber` with `_1…_9999` suffixes never overwrites; filenames are validated (no separators, `..`, shell characters,
executable extensions).

### 5e. Events to the frontend

`BasicSendableEvent` emits `{status: "success" | "failure", data: T}` under a constant name from a shared enum
(`enums::tauri::ux::TauriEventName`); `send_infallible` logs instead of failing.

| Event | Payload |
| --- | --- |
| `generation-enqueue-success-event` / `-failure-event` | action, service, model (`Unknown(String)`), reason |
| `generation-complete-event` / `generation-failed-event` | action, service, model, reason |
| `text_to_image_generation_complete_event`, `image_edit_complete_event`, `video_/object_/gaussian_generation_complete_event` | result tokens + CDN URLs + thumbnail template + `maybe_frontend_subscriber_id/payload` |
| `canvas_bg_removed_event` | media token, CDN URL, subscriber id/payload |
| `credits_balance_changed_event`, `subscription_plan_changed_event`, `refresh_account_state_event` | — |
| `show_provider_login_modal_event`, `show_provider_billing_modal_event` | provider — the backend decides the user must act |
| `flash_user_input_error_event`, `flash_file_download_error_event` | message |

## 6. Accounts, credentials, windows

- **ArtCraft login** (`services/storyteller/commands/login_bridge.rs`): password login/signup, or a **device-code challenge**
  (`{challenge_id, verification_url, confirmation_code, expires_at, poll_interval_seconds}`): the UI shows a QR code and polls;
  the device token never leaves Rust ("the UI holds only a local lookup handle"); verification URLs are allowlisted.
- **Why the HTTP plugin is vendored:** to read and write its private cookie jar, so the webview's `fetch` (through the plugin) and
  native Rust calls share one session; the fork also rewrites `Origin` and `User-Agent` per destination
  (`crates/lib/artcraft_client_identity`) after a dev-server port change made the API reject loopback origins
  (`docs/desktop-session-regression.md`).
- **Consumer-provider logins**: a `WebviewWindowBuilder` per provider, cookies cleared, two-step navigation (home, then login — avoids
  Cloudflare), a watcher polling every 2 s with a heuristic score (visited the auth domain, landed on the app, enough cookies) that
  saves cookies and closes the window. WorldLabs runs injected JS that reads Firebase tokens from IndexedDB and `invoke`s them back.
- **Billing**: Stripe checkout/portal in a webview; on return the backend emits credit/subscription events twice (now and after 5 s)
  to cover webhook lag.
- **Storage**: no OS keyring — keys, cookies and bearers are plaintext files under `~/Artcraft/credentials/`; one command returns the
  full API key to the UI; some cookie/bearer values reach info-level logs.
- **Config**: CSP allows `unsafe-eval`/`unsafe-inline`, `img-src *`, analytics and session-recording hosts; `assetProtocol` scope is
  `**` (the whole disk); `http:default` allows `https://*`. Logs to `artcraft_debug.log`; no crash reporting, no updater.

## 7. The provider layer (`crates/api_clients`)

### 7a. `artcraft_router` — intent → exact provider request

The router turns one provider-agnostic request into a validated, priced, provider-specific call. **The caller names both provider
and model**; the router dispatches on the pair. It does not poll.

**Vocabulary** (`src/api/`): `RouterProvider { Artcraft, Midjourney, Fal, GmiCloud, GrokApi, KinoviWeb, WorldLabs }`; one model enum
per modality (~24 image, ~45 video, audio, mesh, splat) whose serde names are asserted equal to the shared `Common*Model` enums;
**superset option enums** — `RouterAspectRatio` (every ratio any model accepts plus loose `Wide`/`Tall` and resolution-baked values,
documented "gracefully pick the nearest option"), `RouterResolution` (image K-tiers and video p-tiers in one enum), `RouterQuality`,
`RouterBitrate`; media references keep "ours" and "theirs" apart: `ImageRef { MediaFileToken, Url }`, list variants,
`CharacterListRef`.

**Lifecycle per modality** (documented in `src/generate/generate_video/AGENTS.md` with a five-step add-a-model checklist):

```
GenerateVideoRequestBuilder  (plain struct of Option fields + mismatch strategy + idempotency token)
   │ build2(): match (provider, model) → build_<provider>_<model>(builder)    — pure, unit-tested
   ▼
VideoGenerationDraftOrRequest
   ├── Draft(…)    unresolved media refs; finalize(ctx) uploads/re-hosts them   — I/O
   └── Request(…)  enum with one variant per (provider × model), ready to send
   │ estimate_cost()  — available on both, before any upload
   ▼ send_request(&RouterClient)
GenerateVideoResponse  (provider-tagged payload; fal keeps the exact outbound request for replay/debug)
```

Each model is a self-contained module `providers/<provider>/<model>/{build.rs, draft.rs?, cost.rs, request.rs}`. Builds enforce hard
limits as named constants (`MAX_REFERENCE_IMAGES = 9`), reject invalid combinations (end frame without start frame), and may pick
different endpoints from one input set (text-to-video vs image-to-video vs reference-to-video). ArtCraft-hosted models share one
`build_common` parameterised by small **capability enums** (`SupportedResolutions { Full, FullWith4k, Fast, NoFourEightyP }`,
`UltraWideSupport`) and planners (`plan_aspect_ratio`, `plan_output_resolution`, `plan_batch_count`, `plan_duration`, a
`nearest_aspect_ratio` table).

**Mismatch policy:** `RequestMismatchMitigationStrategy { PayMoreUpgrade, PayLessDowngrade, ErrorOut }` is threaded through every
planner; `ErrorOut` returns `ModelDoesNotSupportOption { field, value }`, the others snap to a neighbour (480p on a model without 480p
→ 1080p or 720p). The desktop uses `PayMoreUpgrade`.

**Cost:** `CostEstimate { cost_in_credits, cost_in_usd_cents, is_free, is_unlimited, is_rate_limited, has_watermark,
failures_are_refunded }` (credits = US cents), computable from the draft or the request; price constants live next to each model;
`parity_tests.rs` sweeps resolution × duration × batch to prove variant pairs price identically.

**Errors:** `ArtcraftRouterError { Client, Download, UnsupportedModel, UnsupportedProviderAndModelForNewApi, InvalidInput, Provider,
ProviderBillingError }`; billing failures from any provider are lifted into their own variant so the UI can say "top up" instead of
"failed".

### 7b. Hosted API (`artcraft_api_defs`, `artcraft_client`)

- `artcraft_api_defs` is shared with the server: one file per endpoint with a `…_PATH` const, request/response types with `utoipa`
  schemas.
- **Omni Gen** (cookie auth, in-app): one model-agnostic struct per modality serves both cost and generate
  (`OmniGenVideoCostAndGenerateRequest {model, idempotency_token, prompt, start/end frame tokens, reference image/video/audio/character
  tokens, resolution, aspect_ratio, duration_seconds, batch, generate_audio, estimate_only…}`); `POST /v1/omni_gen/generate/{modality}`,
  `POST /v1/omni_gen/cost/{modality}`, and **`GET /v1/omni_gen/models/{video|image}`** — the capability descriptor the UI renders from:
  per-slot support and max counts, aspect/resolution options with defaults, duration min/max/options/default (and max with image
  references), batch sizes, prompt max length, `is_disabled`, per-provider overrides.
- **Omni API** (public, `Bearer artcraft_api_…`): a deliberate fork of the same shapes with `*_url` siblings for every token field;
  uploads, job status by token or batch.
- `artcraft_client`: one endpoint per file, `reqwest`, cookie auth, Cloudflare-aware error filtering, typed `ApiError`
  (`PaymentRequired`, `TooManyRequests`…), **no retries — safety comes from idempotency tokens**.

### 7c. Third-party clients

| Client | API | Auth | Completion |
| --- | --- | --- | --- |
| `fal_client` (~650 files, ~91 models) | official | `Key` header | queue status/response URLs or webhook |
| `gmicloud_client` | official | Bearer | `GET /requests/{id}` |
| `grok_api_client` | official | Bearer | `GET /v1/videos/{id}` |
| `worldlabs_api_client` | official | `WLT-Api-Key` | `operations/{id}` done |
| `kinovi_web_client` | scraped tRPC | cookies | order polling |
| `midjourney_client` | scraped | Firebase cookies + CSRF | CBOR WebSocket |
| `grok_consumer_client` | scraped | cookies + scraped secrets + request signature | streamed chat / WebSocket |
| `openai_sora_client` | scraped | cookies → JWT + proof-of-work sentinel | drafts list |
| `worldlabs_consumer_client` | scraped | Google JWT + refresh | world status |

The scraped clients reuse the user's own logged-in sessions; they need **TLS/HTTP2 fingerprint emulation** (`wreq` + BoringSSL via
`crates/lib/browser_emulation`, whose `matching_user_agent()` keeps the webview's UA and picks the matching fingerprint so
Cloudflare's `cf_clearance` stays valid). Shared patterns: three-level error enums (`Client / ApiSpecific / ApiGeneric`) with
classifiers for content policy, billing, unauthorised and automation-blocked; no client owns a polling loop.

### 7d. Support libraries (`crates/lib`)

`cookie_store_wrapper` (RFC 6265 jar with a names-only change log, human-editable TOML, `wreq` cookie provider), `cloudflare_errors`
(challenge-page detection), `artcraft_client_identity` (destination classification → Origin/UA), `images` (decode, PNG conversion,
Lanczos resize, `normalize_image_bytes_to_flux_mask`), `jwt_light` (decode vendor JWTs without verifying), `mimetypes` (incl. GLB/FBX/PLY
sniffers), `memory_store` (`CloneCell`, `CloneSlot`), `build_metadata` (git SHA and build time baked in).

**Shared schema crates:** `crates/schema/public/enums` (stored/wire enums; *never rename a stored value; add variants freely; clients
must carry `Unknown(String)`*) and `crates/schema/public/tokens` (Stripe-like prefixed ids — `m_`, `jinf_`, `character_` — generated by
Crockford macros).

### 7e. Testing of this layer

About 4,900 offline tests: pure `build.rs` planning tests, `cost.rs` price tables and parity sweeps, serde round-trips against
captured fixture JSON (fal webhooks, Kinovi responses, Grok WebSocket frames), error classification. About 720 `#[ignore]` live tests
fire real (paid) requests with secrets from a developer's home directory, many ending in `assert_eq!(1, 2, "Inspect output above")`
for a human to read. Nothing mocks HTTP — the design makes it unnecessary, because build and cost are pure functions and `send()` is
a thin edge.

## 8. What to take from the backend, and what not

| Take | Leave |
| --- | --- |
| task row written at enqueue, provider job id UNIQUE, pollers join remote state to local rows → survives restarts | ~8 independent sleep loops with no shared scheduler or shutdown |
| persist the result *before* announcing it; checkpointed, no-clobber, atomic downloads | ephemeral task DB versioned by file name (history thrown away; "segfault" warning) |
| one command per file; vertical provider slices; one response envelope | plaintext credentials, permissive CSP, `assetProtocol` `**`, an unrestricted URL fetch command |
| typed events with constant names from a shared enum; `send_infallible` | mixed kebab/snake event names; Rust debug strings in user-facing errors |
| opaque subscriber id/payload echoed from enqueue to completion | the task-queue listing not echoing it (forcing a timestamp-matching hack in the UI) |
| builder → draft → request → send; pure build/cost; mismatch policy; capability enums; parity tests | two or three generations of API paths coexisting (Omni, typed legacy, deprecated commands still compiled) |
| WebSocket push + periodic HTTP reconciliation in one worker | a vendored HTTP plugin to maintain on every Tauri upgrade |
| idempotency tokens instead of retry libraries; `Unknown(String)` enums; prefixed ids | |
