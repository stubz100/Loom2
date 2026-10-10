# 03 · Frontend architecture

Source: `F:\source\repos\artcraft\frontend` at `3e5793b693`. Covers the workspace, the app shell, state, the bridge to Rust, the
model catalogue and the generation UX. The heavy editors (2D canvas, 3D stage, video editor, moodboard) are in
[04](04-creative-surfaces.md).

## 1. Stack and workspace

| Concern | Choice | Notes |
| --- | --- | --- |
| Monorepo | **Nx 21.2** + npm workspaces | inferred targets (`build`, `test`, `serve`, `typecheck`); `apps/artcraft` + ~45 `libs/*` |
| UI | **React 18.3**, TypeScript 5.8 | `@types/react` 19 (drift) |
| Bundler | **Vite 6** (root) | app `package.json` still says Vite 5, jest, Remix — stale; the root manifest wins |
| Styling | Tailwind 3.4 + CSS variable themes | Radix primitives + Headless UI, wrapped as `@storyteller/ui-*`; lucide + hugeicons |
| State | **Zustand 5** (new code) + **Preact signals** (legacy) + `window` CustomEvents | three paradigms side by side |
| 2D | Konva / react-konva | [04 §1](04-creative-surfaces.md) |
| 3D | Three.js 0.171 (vanilla), Spark (Gaussian splats) | [04 §2](04-creative-surfaces.md) |
| Video | mediabunny (WebCodecs) + opencut-wasm | [04 §3](04-creative-surfaces.md) |
| Tests | Vitest 3 + jsdom + Testing Library; Playwright 1.63 for scripted smoke/perf | ~134 spec files workspace-wide, no coverage threshold |
| Analytics | PostHog (prod), gtag, Microsoft Clarity | Clarity session recording runs inside the desktop app |

**Library resolution.** `tsconfig.base.json` maps every `@storyteller/*` import to the lib's `src/index.ts`, and
`apps/artcraft/vite.config.ts` loads those paths explicitly, so the app builds against library *source* — no per-lib `dist/`
needed (CI only passed by accident on cached `dist/` folders until commit #1949 fixed this). `libs/shared-vite-config.ts` externalises
React, signals, zustand, three and `@storyteller/*` in lib builds; `StorytellerApiHostStore` stashes itself on `window` because a
duplicated singleton *did* happen.

**Lib boundaries.**

| Layer | Libs | Role |
| --- | --- | --- |
| Transport | `tauri-api`, `tauri-events`, `tauri-utils`, `api` | `invoke()` wrappers (one file per command), `listen()` hooks, `IsDesktopApp`/`FetchProxy`/window controls, HTTP client to `api.storyteller.ai` |
| Contracts | `api-enums`, `common` | hand-mirrored Rust enums (`GenerationProvider`, `TaskStatus`, `TaskType`, `Common*` generation enums) |
| Domain | `model-list`, `omni-gen`, `state/credits`, `state/subscription` | model catalogue, omni-gen hooks, account stores |
| UI | `libs/components/*` (~45) | shared with a separate web app (in `artcraft-services`), hence the adapter seams (§8) |

## 2. Boot and shell

`app/index.html` → `src/index.tsx` renders `<StrictMode><BrowserRouter>` with:

1. **`GlobalSettingsManager`** — boot work: `GetAppInfo` → point `StorytellerApiHostStore` at the host Rust chose (prod or
   `localhost:12345`), restore the session, init PostHog, apply the theme class from `localStorage['st-theme']`, install the sound
   manager, and `useModelsStore.loadModelsFromBackend()`.
2. A `.topbar-spacer` with `data-tauri-drag-region` (the window is frameless on Windows).
3. **`MainApp`** + **`GlobalFileDropHandler`**.

**Routing is not really used.** No `<Routes>` is mounted; navigation is a Zustand tab switch. `root.tsx`, `entry.*.tsx` and
`routes/*` are Remix/Netlify leftovers.

**`pages/MainApp.tsx`** keeps the always-mounted chrome — `TopBar`, `LoginModal`, `GalleryDragComponent`, `ErrorDialog`,
`Toaster`, `PricingModal`, `CreditsModal` — and the **global Tauri listeners** (`useGenerationEnqueueSuccess/FailureEvent`,
`useGenerationComplete/FailedEvent`, `useTextToImageGenerationCompleteEvent`, `useMediaFileDeletedEvent`, flash errors), so a
completion surfaces whatever tab is open. `TabBody` switches on `useTabStore().activeTabId`; every page except the 2D canvas and
the Apps landing page is `React.lazy` behind Suspense. **Inactive pages unmount**; their state survives only because Zustand
stores are module singletons (and the 3D scene's JSON tab cache, 04 §2).

**Top bar** (`components/signaled/TopBar/TopBar.tsx`, 56 px, 3-column grid): left = app switcher (`MenuIconSelector`: Home, Create
Image, Create Video, Create Audio, Image Editor, 3D Stage — large items show demo GIFs; switching throttled to 500 ms and locked
while a 3D scene loads); centre = breadcrumbs or the 3D scene title; right = gallery view toggles, **credits popover** (balance,
buy, cost calculator), Upgrade, **TaskQueue**, My Library, Upload, Settings, custom window buttons. The app registry is
`config/appMenu.tsx` (`APP_DESCRIPTORS`, colour palettes, NEW/BETA/SOON badges, `useVisibleApps`, `goToApp`).

### 2a. Pages (user-facing modes)

| Tab | Component | What the user does |
| --- | --- | --- |
| `APPS` | `pages/PageApps/AppsIndexPage.tsx` | Landing: "What will you craft today?" — a card grid of task-oriented apps |
| `IMAGE` | `pages/PageImage/TextToImage.tsx` | Text/reference → image; feed above a floating `PromptBoxImage` |
| `VIDEO` | `pages/PageVideo/ImageToVideo.tsx` | Text/image/reference → video |
| `AUDIO` | `pages/PageAudio/CreateAudio.tsx` | Suno music/sounds, Seed Audio (omni-gen audio flow) |
| `2D` | `pages/PageDraw` → `ui-pagedraw` | Konva canvas: compose, mask, inpaint/edit, background removal |
| `3D` | `pages/PageScene` → `ui-pagescene` | Three.js stage: kitbash, pose, frame a camera, capture/record |
| `VIDEO_EDITOR` | `pages/PageVideoEditor` → `ui-video-editor` | Timeline editor (BETA) |
| `MOODBOARD` | `pages/PageMoodboard` → `ui-moodboard` | Reference boards; "send to generation" |
| `IMAGE_TO_3D_OBJECT` / `_WORLD` | `components/experiences/ImageTo3DExperience.tsx` | Image → mesh (Hunyuan 3D…) or → splat world (Marble); preview, then "Open in 3D Editor" |
| `REMOVE_BACKGROUND` | `pages/PageRemoveBackground` | Background removal with before/after |
| `ANGLES` | `pages/PageAngles` (+ `OrbitSphere.tsx`) | Drag on an orbit sphere (rotation, tilt, zoom) → regenerate the image from that viewpoint |
| `STORYBOARD` | `pages/PageStoryboard` | Shots with sketch, dialogue, action, duration, filmstrip — local only, behind an experimental flag |
| `VIDEO_FRAME_EXTRACTOR` | `pages/PageVideoFrameExtractor` | Scrub, grab a frame, download or send to the Video prompt |
| watermark removal, background change | — | "SOON" / hidden |

## 3. State management

- **App stores** (none persisted): `TabState.ts` (`activeTabId`, `tabData` JSON per tab), per-page stores for Image-to-3D,
  Remove Background, Angles, Storyboard. `TextToImageStore` / `ImageToVideoStore` are written but never read (the feed moved to the
  task queue).
- **Lib stores:** `useModelsStore` (`tauri-api/models/modelsStore.ts`), `useCreditsState` (stale-response token counter, a 3 s
  "slow" timer, "recovered" held 1 s), `useSubscriptionState`.
- **Signals:** auth status, legacy job lists, legacy toasts, gallery-modal lightbox state (`galleryModalLightbox*`).
- **Persistence:** UI state is not persisted to the backend. `localStorage` holds the theme, small flags and a `task_enqueue_meta`
  cache; Zustand `persist` is used only inside component libs (keybinds, gallery view, moodboard library, video editor).
- **Cross-page hand-offs** are imperative: write the target page's store via `getState()`, then `setActiveTab(...)` ("Edit" resets
  the 2D store and adds the image; "Make video" fills `usePromptVideoStore`; the moodboard fills `usePromptImageStore.referenceImages`).
  A second bus of `window` CustomEvents (`task-queue-update`, `credits-change`, `gallery-2d-drop`) and globals
  (`window.__storeTaskEnqueueMeta`, `window.FetchProxy`) exists alongside.

## 4. Bridge to Rust

**Commands** (`libs/tauri-api`): one file per command, a typed async wrapper around `invoke("<name>_command", { request })`. Groups:
`generate/*` (unified `generate_image|video_command`; `GenerateOmni.ts` for audio/mesh/splat), `cost_estimate/*`, `artcraft/*`
(credits, subscription, task queue), `download/*`, provider credential probes, settings, `util/LoadWithoutCors`. Results follow the
backend's `CommandResult` envelope (`status: success | bad_request | unauthorized | server_error`, `payload` or
`error_type` + `error_message`, [02 §4](02-backend-architecture.md)). Wrappers take a `Model` object and read `model.tauriId`, using
a `kind` discriminator instead of `instanceof` (minification mangles class names). Listing DTOs type enum fields as plain strings
because the Rust enums have an `Unknown(String)` catch-all.

**Events** (`libs/tauri-events`): each event is a `useXxxEvent(cb)` hook that calls `listen()` in an effect and unsubscribes even if
the component unmounts before `listen` resolves. Payloads are `BasicEventWrapper<T> { status, data }`. The lifecycle hooks are
self-contained: each plays a sound and raises a toast with an action-specific message.

**Correlation.** Callers create a `frontend_subscriber_id` (UUID) and a `frontend_caller` on enqueue; completion events echo it, so a
page resolves only its own placeholders (`PageDraw`'s `useTauriEventBridges`, `AnglesStore`). The task-queue listing does *not* echo
it, so `TopBar/taskEnqueueMeta.ts` re-associates prompts and reference thumbnails by timestamp (±30 s) and model — the file calls
itself "hacky and temporary".

**HTTP** (`libs/api`): `ApiManager` subclasses (`MediaFilesApi`, `MediaUploadApi`, `UsersApi`, `FoldersApi`, `PromptsApi`,
`OmniGenApi`…) over `FetchProxy`, which inside Tauri goes through the (vendored) HTTP plugin so cookies live in Rust's jar.
A second, older copy of the API classes lives in `app/src/Classes/ApiManager/*`.

**Web mode:** `IsDesktopApp()` gates a few things, but most features call `invoke` unconditionally; the *web* product is a separate
app that mounts the same libs with REST adapters.

## 5. Model catalogue and the generation UX

**Model classes** (`libs/model-list`): `Model` (`kind`, `id`, `tauriId`, `fullName`, `creator`, selector name/description/badges,
`tags` such as `InstructiveEdit` / `MaskedInpainting`, `providers`, `preferredProvidersByPage`, `progressBarTime`, `maxPromptLength`).
`ImageModel` adds generation counts, editing flags (`canEditImages`, `usesInpaintingMask`, `editingIsInpainting`,
`canUseImagePrompt` + `maxImagePromptCount`, `canTextToImage`, `canEditAngles`), and option lists with defaults (`aspectRatios`,
`resolutions`, `qualityOptions`). `VideoModel` adds start/end frame, `requiresImage`, durations, sizes, sound, reference limits.
`SplatModel`, `Object3DModel` cover 3D.

**Backend-authoritative with a local overlay.** `loader/buildModelsFromListing.ts` merges the backend listing
(`list_image|video_models_command`, cached 60 s in Rust, served stale on failure) over static overlay lists
(`lists/ImageModels.ts`, `lists/VideoModels.ts`): **membership, order and capability fields come from the backend**; the overlay
adds presentation, page-subset flags and provider knowledge. New backend models appear without a release. Costs are not in the
catalogue; they come from live `estimate_*_cost_command`s.

**Request assembly** (Image page, `libs/components/promptbox/src/lib/PromptBoxImage.tsx`):

1. `ClassyModelSelector` (filtered to the page; selection per page in `useClassyModelSelectorStore`, a provider picker when a model
   has several providers).
2. `PromptBoxImage` holds prompt, references, count, aspect, resolution, quality; validates `maxPromptLength` with a counter.
3. `handleEnqueue` builds `GenerateImageRequest`: always `{prompt, model, batch_size, frontend_caller, frontend_subscriber_id}`;
   `aspect_ratio` / `resolution` / `quality` **only when the model supports them**; `image_media_tokens` when `canUseImagePrompt`.
   `buildAudioRequest` (omni-gen) counts a capability as supported only if it is `=== true`.
4. A live **cost estimate** sits in the prompt box, with a calculator modal explaining it.

**Progress and results.** Enqueue → `generation-enqueue-success-event` (sound + toast). Errors needing the user raise
backend-pushed modals (`show_provider_login_modal_event`, `show_provider_billing_modal_event`). `useDesktopGenerationFeed` polls
`GetTaskQueue` every 5 s (and on completion events) and splits tasks into in-progress (fake progress from `progressBarTime`),
failed (friendly labels for policy refusals, dismissable) and newly completed (expanded to gallery items, retrying missing video
thumbnails for up to 10 min). `DesktopCreatePageShell` = hero empty state + feed + fixed bottom prompt box + cost/help buttons. The
global **TaskQueue** popover (1,301 lines) shows in-progress/completed/failed cards with prompt marquee, reference thumbnails, time
left, copy prompt, unread badge, bulk clear; it re-fetches credits 2 s after a failure because refunds settle late. Audio uses yet
another polling hook — three job-tracking systems coexist.

## 6. Library, references, drops

- **My Library** = `GalleryModal` (`libs/components/gallery-modal`): server media by user, folders, view mode with action callbacks
  (download, edit in 2D, make video, remove background, make 3D, recreate from prompt, delete) and a **select mode reused as the
  asset picker** everywhere. Media is addressed by **media tokens** (`mf_…`) — the universal reference currency; uploads return one.
- **Drag from library** onto the 2D canvas, 3D stage and moodboard; each tab registers its drop bridge only while mounted.
- **OS file drops** (`GlobalFileDropHandler`): Tauri `onDragDropEvent`, files classified by extension (GLB → 3D, PNG/JPG → image,
  SPZ → splat), a full-screen "Drop to upload" overlay, deferral to local drop zones and open modals, a toast for skipped files.
- **References ("ingredients")**: the prompt-box *deck* (`promptbox/src/lib/deck`) holds image/video/audio refs by token;
  `@`-mention chips reference saved **characters** (`reference_character_tokens`).

## 7. Accounts, settings, keybinds, theming

- **Login**: device-code flow (`DesktopLoginBridge.tsx`): create challenge → QR + confirmation code → open browser → poll until
  redeemed/expired. Credentials never reach JS ([02 §6](02-backend-architecture.md)).
- **Credits**: refreshed on login, every 60 s, and on `CreditsBalanceChanged`; the coin shows a slow/failed/recovered badge with Retry.
- **Settings** (`libs/components/settings-modal`): General, Accounts, Appearance, Audio, Downloads, Video, Provider Priority,
  Billing, About (version, build time, git SHA, data dirs), Experimental (unlocked from About). Opened with a deep-link `initialSection`.
- **Keybinds** (`libs/components/keybinds`): a registry of stable action ids; presets **Gamer** (default) and **Blender**; user
  overrides persisted; `ActionDef.when(ctx)` availability gates let two actions share a key only if their gates are mutually exclusive
  (`actionsCoAvailable`, enforced in tests and in the conflict UI); a hold-to-peek cheatsheet. Tooltips render the current binding.
- **Theming**: CSS variable themes (`light`, `gray` default, `black`, `aurora`, `sunset`) mapped to Tailwind tokens; many hard-coded
  colours bypass them. **No i18n.**
- **Sound**: `SoundManager` plays on enqueue/complete/fail/delete (configurable).

## 8. The adapter seam (the cleanest idea in the frontend)

Heavy editors never import Tauri. Each takes a host **adapter**, and the app supplies a Tauri implementation while the web app
supplies a REST one:

| Library | Adapter | Host implementation |
| --- | --- | --- |
| `ui-pagedraw` | `PageDrawAdapter` (`pagedraw/src/lib/adapter.ts`) | `apps/artcraft/app/src/pages/PageDraw/PageDraw.tsx` |
| `ui-pagescene` | `PageSceneAdapter` (~60 members, `pagescene/src/lib/adapter.ts`) | `pages/PageScene/useTauriPageSceneAdapter.tsx`, `sceneOutputAdapter.ts` |
| `ui-video-editor` | media source, asset gallery, export sink, auth, toast, upload | `pages/PageVideoEditor/adapters/*` |
| `ui-moodboard` | `MoodboardAdapter` + `MoodboardPersistenceAdapter` | `pages/PageMoodboard/desktopMoodboardAdapter.tsx` |
| `omni-gen` | injectable `generate` transport | Tauri `GenerateAudio` on desktop, HTTP on web |

Adapters also carry **render slots** (`renderBaseImageSelector`, `renderAssetUploader`, `renderLibraryPicker`) so host UI can be
injected without the lib knowing about it. Result: portable, testable editors, and one place per host that knows about transport.

## 9. Tests and build

- Vitest workspace globbing every `vite.config`/`vitest.config`; jsdom in the app (only 3 app specs); lib specs concentrated in
  `model-list` (`buildModelsFromListing.spec.ts`), `omni-gen`, moodboard (7), pagescene, keybinds, login-modal.
- **Scripted E2E without a backend**: `tools/testing/desktop-session.mjs` drives the real UI in headless Chrome with a deterministic
  **mocked IPC fixture** (`tools/performance/browser-fixture.mjs`) — landing, credits, settings, library, navigation, logout.
- **Performance harness**: `tools/performance/run.mjs` builds with a benchmark plugin and measures startup and tab-switch timings
  over N runs with baseline comparison ([05 §5](05-engineering-practices.md)).
- Tauri wiring: `devUrl http://localhost:5173`, `beforeBuildCommand: npx nx run artcraft:build`, `frontendDist` → the app's `dist`.

## 10. Frontend tech debt (for calibration)

Remix leftovers and an empty router; three state paradigms and two toast systems; two API layers; three job-polling systems (5 s
each); hand-mirrored Rust enums ("should use code gen"); the timestamp-matching `taskEnqueueMeta` hack; files over 1,200 lines
(`TaskQueue.tsx`, `Storyboard.tsx`, `ImageTo3DExperience.tsx`) against the app README's own 200-line rule; TopBar importing five
pages' stores; `__TAURI__` vs `__TAURI_INTERNALS__` checks disagreeing; permissive CSP with analytics and session recording inside
the desktop app.
