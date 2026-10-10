# 01 · ArtCraft — overview

Source: `F:\source\repos\artcraft`, `main` at `3e5793b693` (2026-10-06), app version 0.41.0. Read 2026-10-08.

## 1. What it is

ArtCraft calls itself **"the IDE for artists"**: a desktop application (Tauri 2, Windows and macOS releases, Linux from source) for
interactive AI image, video, audio and 3D creation. Its pitch is *crafting instead of prompting*: compose in 2D, stage scenes in
3D, then generate, with the model of your choice.

The important architectural fact: **ArtCraft runs no models locally.** Every generation goes to a cloud service — mostly the
company's own hosted "Omni Gen" API (62 models across five modalities, paid in credits), optionally fal.ai with the user's API key,
or the user's own consumer accounts on Midjourney, Grok, Sora and World Labs, driven through captured browser sessions. The media
library, scenes and moodboards also live on the hosted backend. The desktop app is a rich **client**: the creative tools run in the
WebView, Rust handles accounts, job tracking, downloads and provider plumbing.

The company (Learning Machines LLC, "Storyteller" / FakeYou historically) is also a content studio; the 2026 roadmap's first goal is
to be "better and more useful than model aggregation websites", followed by "tangible" surfaces where scenes are moulded like clay,
"add every model and provider", purpose-built models for relighting and reposing, and — architecturally — **removing the dependence
on ArtCraft-hosted services**.

## 2. Feature map

| Area | What the user does | Where it lives |
| --- | --- | --- |
| **Create Image** | text and reference images → image; model picker with per-model capabilities; live credit cost | `pages/PageImage`, `promptbox` |
| **Create Video** | text / start (+ end) frame / references / `@`characters → video | `pages/PageVideo` |
| **Create Audio** | music, sound effects, remix (Suno, Seed Audio) | `pages/PageAudio` |
| **Image Editor (2D canvas)** | layer images, shapes and strokes over a base image; mask and inpaint; instruction-edit the composite; background removal per object; drop a 3D model in and re-pose it | `libs/components/pagedraw` ([04 §1](04-creative-surfaces.md)) |
| **3D Stage** | kitbash characters, props, sets and splat worlds; FK-pose Mixamo rigs; animate with keyframes and clips; frame a render camera by focal length; capture a still or record a clip, then send it to image/video generation | `libs/components/pagescene` ([04 §2](04-creative-surfaces.md)) |
| **Image → 3D object / world** | image or text → mesh (Hunyuan 3D, Tripo, Meshy, Rodin) or → Gaussian-splat world (Marble); preview; open in the 3D stage | `components/experiences/ImageTo3DExperience.tsx` |
| **Angles** | drag on an orbit sphere to re-render an image from another viewpoint | `pages/PageAngles` |
| **Remove background**, **frame extractor**, **background change (VFX)** | single-purpose "apps" | `pages/*`, `libs/components/vfx` |
| **Video Editor** (beta) | multi-track timeline, effects, masks, keyframes, retime, WebCodecs export (an OpenCut port) | `libs/components/video-editor` ([04 §3](04-creative-surfaces.md)) |
| **Moodboard** (beta) | reference boards: grid, free canvas, slideshow; send references to generation | `libs/components/moodboard` |
| **Storyboard** (experimental) | shots with sketch, dialogue, action, duration, filmstrip | `pages/PageStoryboard` |
| **Library** | every generated/uploaded file, folders, tags, lightbox with "send to" actions, drag onto any editor | `libs/components/gallery-modal`, `lightbox-modal` |
| **Accounts** | device-code login, credits and subscription, provider logins, BYO API keys, cost calculator | `login-modal`, `settings-modal`, Rust `services/*` |

## 3. Model catalogue (from the README)

| Modality | Families (ArtCraft-hosted) | Count |
| --- | --- | --- |
| Images | Nano Banana (1, 2, Pro), GPT Image (1.5, 2, 2.5 variants), FLUX.1 dev/schnell, FLUX 1.1 pro/ultra, Seedream 4–5 | 16 |
| Video | Seedance 1–2, Kling 1.6–3.0, Veo 2–3.1, Sora 2, Vidu Q3, MiniMax H3, Flux 3 | 25 |
| Music and sound | Suno (music, remix, sounds, sample), Seed Audio | 5 |
| 3D meshes | Hunyuan 3D 2.0–3.1 (incl. sketch, part, smart topology), Tripo3D, Meshy 6, Rodin | 11 |
| Worlds / splats | Marble 1.0–1.1, TripoSplat | 5 |

Plus Midjourney (own account), Grok Imagine (now routed through ArtCraft), Sora / GPT Image (own account), World Labs Marble (own
account), fal.ai (own key). Kling, Google, Runway and Luma direct integrations are planned. The model list is served by the backend,
so new models appear without a desktop release ([03 §5](03-frontend.md)).

## 4. Architecture at a glance

```
┌─────────────────────── ArtCraft desktop (Tauri 2) ───────────────────────┐
│  WebView: React 18 + Zustand (+ legacy Preact signals), Nx monorepo      │
│    shell: top bar · tab pages (lazy) · task queue · library · settings  │
│    editors as host-agnostic libs with adapters:                          │
│      pagedraw (Konva) · pagescene (Three.js + Spark) ·                   │
│      video-editor (OpenCut port, WebGPU/WASM, mediabunny) · moodboard    │
│        │ invoke() commands            ▲ typed events                     │
│  Rust: 63 commands · task DB (SQLite) · ~8 polling loops ·               │
│        auto-download · credentials · login/billing webviews              │
│        artcraft_router (intent → priced provider request)                │
└────────┬───────────────────────┬─────────────────────────┬──────────────┘
         ▼                       ▼                         ▼
  ArtCraft Omni Gen API     fal.ai (BYO key)      consumer web apps via the
  (models, credits, media   queue                 user's session (Midjourney,
  library, CDN, scenes)                           Grok, Sora, World Labs, Kinovi)
```

Details: backend and provider layer [02](02-backend-architecture.md), frontend [03](03-frontend.md), creative surfaces
[04](04-creative-surfaces.md), build/release/conventions [05](05-engineering-practices.md).

## 5. Technology stack

| Layer | Choice |
| --- | --- |
| Shell | Tauri 2.11 (vendored `tauri-plugin-http` for cookie access), frameless window on Windows |
| Backend | Rust (tokio, sqlx 0.7 + SQLite, reqwest + **wreq** for browser-fingerprint HTTP), ~258k lines of Rust in total |
| Frontend | React 18.3, TypeScript 5.8, Vite 6, Nx 21, Zustand 5 + Preact signals, Tailwind 3.4, Radix, lucide |
| 2D | Konva / react-konva, OffscreenCanvas workers |
| 3D | Three.js 0.171 (vanilla), Spark (Gaussian splats), MMD loader |
| Video | OpenCut-derived editor, opencut-wasm (wgpu compositor), mediabunny (WebCodecs) |
| Tests | ~5,950 Rust tests (4,900 offline, ~720 ignored live), Vitest, Playwright smoke + perf with mocked IPC |
| Release | GitHub Actions publish workflows → draft releases; macOS signed/notarised; Windows unsigned; no auto-updater |

## 6. Size and history

~520k lines in ~5,760 tracked files: Rust 258k (of which the provider clients ~195k), TS/TSX 207k (component libraries 163k, the
video editor alone ~71k). The repository was restarted on 2026-09-11 from a larger monorepo (server code moved to a private
`artcraft-services` repository); since then 19 squash-merged PRs: Midjourney fixes, new models (GPT Image 2.5, Wan), a native website
login, per-destination client identity after a session regression, a tested combined dev launcher, lazy-loaded pages (−38 % startup),
thumbnail speed-ups, restyling to match the web app, and GPU-asset disposal in the 3D stage.

## 7. Strengths and weaknesses in one table

| Strengths | Weaknesses |
| --- | --- |
| Breadth: five modalities, 62+ models, three provider tiers behind one request shape | Not local: needs the hosted service and credits for almost everything; the library lives in the cloud |
| Real creative surfaces: 2D compositing, 3D staging with cameras and posing, a full video editor, moodboards | 2D canvas has no real layers, blend modes or selections; 3D has no control passes (depth/pose) and FK only |
| Clean seams: editors as host-agnostic libraries with adapters; pure, heavily tested request building and pricing | Three state paradigms, three job-polling systems, legacy API generations side by side |
| Forward compatibility: passthrough requests, backend-served capabilities, `Unknown(String)` enums | Weak security posture: permissive CSP, filesystem-wide asset scope, plaintext credentials, scraped consumer APIs |
| Careful async hygiene (subscriber ids, load tickets, pre-bake, GPU disposal) | No PR CI; video-editor projects are never reopened; several 1,000–2,000-line files |
| Agent-oriented conventions (`AGENTS.md` per subsystem, add-a-model checklists) | Licence forbids reuse of the code in a competing product ([05 §7](05-engineering-practices.md)) |
