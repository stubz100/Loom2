# 04 · Creative surfaces — 2D canvas, 3D stage, video editor, moodboard

Source: `F:\source\repos\artcraft\frontend\libs\components\*` at `3e5793b693`. These libraries are what makes ArtCraft an
"IDE" rather than a model aggregator. All of them are host-agnostic through adapters ([03 §8](03-frontend.md)) and address media by
backend **media tokens** (`mf_…`): inputs are uploaded first, then referenced.

## 0. The generation round trip every surface uses

1. The surface builds a request; its adapter calls the Tauri command (`GenerateImage(...)` etc.) with a client UUID as
   `frontend_subscriber_id`.
2. Rust enqueues, records a task row, and later emits a completion event carrying `maybe_frontend_subscriber_id` plus
   `generated_images[] {media_token, cdn_url, maybe_thumbnail_template}`.
3. Each page's bridge accepts only subscriber ids it owns, so several surfaces can share one global event without collisions.

## 1. pagedraw — 2D compositing, drawing, inpainting

**Technology:** Konva via react-konva; no WebGL in the 2D path. Core files: `src/lib/PageDraw.tsx` (1,386 lines, orchestration and
generation), `src/lib/PaintSurface.tsx` (2,060, stage + tools), `src/lib/stores/SceneState.ts` (1,548, `useSceneStore`).

**Layer model — fixed Konva layers, not user layers:**

| Konva layer | Contents |
| --- | --- |
| `bg-layer` | the base image (`baseImageBitmap`) or a blank canvas with a fill colour |
| `draw-layer` | one ordered array `drawNodes: (Node \| LineNode)[]` — shapes (`rectangle`, `circle`, `triangle`), images, brush/eraser strokes interleaved; z-order = array index |
| `invis-mask-layer` | `inpaintLineNodes` — the inpaint mask, cyan strokes, `destination-out` for minus/eraser |
| cursor layer | brush-size circle, counter-scaled to stay constant on screen |
| transformer layer | per-node and multi-select `Transformer`s |

**Tools:** select/move (marquee), shapes, upload image, brush (colour, size, opacity), mask, eraser, canvas background, undo/redo.
Right-click menu: **Remove background**, lock/unlock, bring forward/back, duplicate, delete. Copy/paste offsets pasted items.
*Not present:* lasso, magic wand, flood fill, real raster layers, blend modes. Keybinds go through the shared registry; tooltips
show the binding; a cheatsheet overlay exists.

**Background removal:** base64 the node image → `adapter.enqueueBgRemoval(base64, nodeId)` with the node id as subscriber id →
`canvas_bg_removed_event` → `finishRemoveBackground(nodeId, mediaToken, cdnUrl)` swaps the image in place.

**3D objects inside 2D:** a dropped GLB is rendered offscreen (`utilities/render3DModel.ts`: `WebGLRenderer` with alpha, five-light
rig, `GLTFLoader`) to a PNG node that remembers `modelUrl` + `model3dParams` (camera, fov, scale). "Edit 3D" reopens a live Three.js
overlay (`components/Model3DOverlay.tsx`) to re-pose it and re-bake the bitmap.

**Undo/redo:** whole-document snapshots in the store (`history[]`, `historyIndex`, `saveState()`); undo is *async* because it
rebuilds `Node`s and re-decodes every image. Mutators take `shouldSaveState` so a drag commits once on drag-end. Simple, but it does
not scale to many large images.

**Flatten and send to a model** (`PageDraw.tsx`: `getCompositeCanvasFile`, `getMaskArrayBuffer`, `handleGenerate`):

1. Read the draw layer back at native resolution (`layer.toCanvas(... pixelRatio: 1/scale)`, main thread because Konva is DOM-bound).
2. Transfer `ImageBitmap`s to an **inline Web Worker** (`utilities/generatePipeline.worker.ts`) that composites base + markers on an
   `OffscreenCanvas` and encodes PNG; bitmaps are `close()`d in `finally` (a 4K failure leaked ~67 MB before).
3. **Idle pre-bake:** any change marks the composite dirty and re-bakes after 300 ms; a generation counter and an in-flight promise
   make concurrent bakes safe, so the Generate click usually finds a ready file.
4. On Generate, yield one `requestAnimationFrame` so the disabled button paints, then branch on the model:
   - *Inpainting models* → mask PNG (the semi-transparent cyan render — the backend must threshold alpha) + base token.
   - *Instruction-edit models* (Nano Banana, GPT Image…) → upload the composite as a "scene snapshot", send its token plus reference
     tokens, aspect (`auto|wide|tall|square`) and resolution (`1k|2k|4k`).

**Results come back as versions, not overwrites.** Pending jobs appear as dismissable placeholders in `HistoryStack.tsx` (a
filmstrip of base-image "bundles"); a result becomes a selectable alternative base image. Selecting one saves the current overlay
nodes against the old base (`historyImageNodeMap`) and restores the new base's own overlays, so each version keeps its annotations.
A load-generation counter (`baseImageLoadGen`) stops a stale `onload` from overwriting; `img.decode()` preloads to avoid flashes.

**Persistence:** none on the backend. `exportSceneAsJson` (`version "2.0"`, images inlined as base64) to a downloaded file; the live
store survives tab switches as a module singleton.

## 2. pagescene — 3D staging

**Technology:** vanilla **Three.js** (not react-three-fiber), **Spark** `SplatMesh` for Gaussian splats, `three/addons`
`EffectComposer`, `MMDLoader`, mediabunny for recording. `libs/components/pagescene/AGENTS.md` (513 lines) is the design + status doc
(partly stale: it still calls recording a stub).

**One-way data flow (documented and followed):**
`Three.js engine → typed EngineEventBus → EngineStoreBridge → Zustand usePageSceneStore → React → actions/* → engine methods`.
`EngineEventBus` is keyed by event class (~30 events: `SelectionChangedEvent`, `OutlinerRefreshedEvent`, `TimelineChangedEvent`…);
`EngineStoreBridge` is the only engine-to-store writer; `actions/*.ts` are thin dispatchers.

**Lifecycle:** `Stage3D.tsx` → `EngineProvider` builds `new Editor(adapter)` once three DOM nodes are registered. **Footgun
(documented):** never conditionally unmount the canvas hosts — hide them with CSS — or the editor is torn down and rebuilt. On unmount
the scene is serialised and cached in the tab store; on remount it is restored.

**Editor subsystems** (`engine/editor.ts` 1,170 lines + `engine/editor/*`):

| Subsystem | What it does |
| --- | --- |
| `CameraController` | viewport camera (sees helpers) vs **render camera** (layer 0 only); `focalLengthToFov(focal, sensor=24)`; aspect presets (16:9 = 1280×720, 3:2, 2:3, 9:16, 1:1); camera view with framing rect and rule of thirds |
| `GizmoController` / `ModalTransformController` | vendored `TransformControls.js`; Blender-style modal grab |
| `HistoryManager` | command pattern `UndoableAction {label, apply, revert}`, capacity 64, undo/redo **serialised through a promise chain** with an `isReplaying` guard |
| `PostProcessingPipeline` | selection outline pass; stylistic feature-edge outlines (surface ids) — *not* ControlNet passes |
| `TimelineController` | keyframe tracks (full transform, cubic-bezier easing) + clip lanes |
| `CharacterAnimationManager` | one `AnimationMixer` per rigged object, deterministic playhead evaluation |
| `EntranceAnimator` | mesh drop and a per-splat "settle" written as a Spark `dyno` shader graph |
| `useFreeCam` | WASD/QE fly navigation |

**Objects and loading** (`engine/scene.ts`, 1,338 lines): every object carries `userData.media_id`. `loadObject(media_id)` resolves
the URL through the adapter (cached, batch-warmed) and dispatches on extension: `.pmd/.pmx` → MMD, images/videos → planes (videos
chroma-keyable), `.spz` → splat, else GLB. Loads take an `AbortSignal` and a load *ticket* so superseded loads bail out.

**Kitbash library** (`comps/AssetMenu/AssetModal.tsx`): tabs All · Characters · Objects · Memes · Sets · Creatures · Animations, plus
image planes and skyboxes; featured + user media; click-to-add or drag a ghost card, dropped by **raycast** onto the scene.

**Posing:** forward kinematics only (`engine/KinHelpers/FKHelper.ts`): picker spheres on Mixamo-named bones, click to attach a
local-space rotate gizmo; pose saved per object as bone JSON. No IK, no pose presets, no retargeting (clips bind by bone name; a drag
badge shows green/red compatibility by preloading the clip's track names).

**Image → 3D, worlds:** separate pages call `GenerateMesh` (Hunyuan 3D…) or `GenerateSplat` (World Labs Marble), preview in
`Viewer3D`, then "Open in 3D Editor" adds the result to the stage.

**From 3D to an image — the "3D compositing / identity transfer" features.** There are **no depth, normal or pose control passes**.
`Editor.snapShotOfCurrentFrame()` hides helpers, renders the render camera at the preset size, and returns a PNG; that *beauty pass*
is sent to an **instruction-edit model** as the scene image, with character photos as references. The current flow is a Record mode:
*Capture* a still or *Record* the timeline frame by frame (`engine/recording/TimelineRecorder.ts`: stop the loop, seek, render, feed
mediabunny `CanvasSource` → MP4/WebM, cancellable), then a completion modal that uploads and hands off to the shared lightbox
(Edit on Canvas, Make Video…).

**Save format** (`engine/save_manager.ts`): `{version, scene: [ObjectJSON], skybox, cameras, timeline}`; each object stores
transform, `object_uuid` (preserved so timeline tracks resolve), `media_file_token`, material tweaks, lock/visibility, bone pose.
Assets by token, never embedded. Saved to the backend as a JSON file (named `.glb`, a misnomer) plus a rendered cover image.

**GPU hygiene** (recent commit #1972): `Scene.disposeObject` stops video textures and unregisters helpers before the shared
`disposeObject3D`; `Editor.unmountEngine()` aborts loads, stops RAF, disposes renderers and passes, and calls `forceContextLoss()`
**only when the canvas is detached**, so scene swaps reuse the context while page exits free it.

## 3. video-editor — an OpenCut port

`libs/components/video-editor` is by far the largest library (~507 files, **~71k lines**). It is a port of **OpenCut** ("OpenCut
Classic", MIT), restructured from a Next.js app into a library with adapters: `opencut-wasm` (MIT) supplies frame-rate / media-time
maths and the compositor, and eslint rules are named `opencut/*`.

| Area | Shape |
| --- | --- |
| Core | `EditorCore` singleton (`core/index.ts`) with 12 plain-class managers: command (undo), timeline, playback, scenes, project, media, renderer, save, audio, selection, clipboard, diagnostics; React reads them through `useEditor(selector)` on `useSyncExternalStore`; Zustand only for UI prefs |
| Project | `TProject {metadata, scenes[], currentSceneId, settings {fps num/den, canvasSize, background}, version, timelineViewState}` |
| Timeline | `TScene {tracks: {main, overlay[], audio[]}, bookmarks}`; elements video · image · audio · text · sticker · graphic · effect (adjustment clip) with `startTime`, `duration`, `trimStart/End`, `params`, keyframed `animations` (linear/hold/bezier, graph editor), per-clip `effects[]`, `masks[]`, `retime`; time is an integer-tick `MediaTime`. **No transitions** |
| Editing | ripple, group move/resize, box select, split, snapping to edges/playhead/bookmarks/keyframes (threshold in screen pixels); ~30 `Command` classes, drags preview then commit as one snapshot command |
| Playback | render-node tree → **WebGPU compositor (wgpu in WASM, from opencut-wasm)**; video frames via mediabunny `CanvasSink` with prefetch and seek generations; Web Audio with 2 s lookahead, `soundtouchjs` for pitch-preserving retime; without WebGPU a degraded banner |
| Export | `SceneExporter` steps frames deterministically into **mediabunny** `CanvasSource` (MP4 AVC+AAC/Opus, WebM VP9+Opus), all in-browser, no ffmpeg, no MediaRecorder (WebM durations were unreliable); whole file in memory |
| Persistence | `StorageAdapter<T>` key-value interface (IndexedDB by default); `SaveManager` autosaves `ProjectDocument v1` 800 ms after changes. **The desktop host creates a fresh `local-<uuid>` project on every mount and never reopens one** — work is lost between sessions and IndexedDB rows are orphaned |

Host adapters (`apps/.../PageVideoEditor/adapters/`): media source, asset gallery (the gallery's select mode — how generated videos
reach the bin; nothing lands on the timeline automatically), export sink (save to disk and/or re-upload), auth user, toast, upload by
kind. The port carries no visible MIT attribution to OpenCut; only two tests.

## 4. Moodboard and the smaller libraries

- **moodboard** (73 files, ~9.6k lines): three surfaces — a virtualised masonry **grid**, a free **Konva canvas** per board (snapping,
  pack-into-collage, group by proximity, snapshot undo), and a **present** slideshow; rating triage on number keys, palette extraction,
  link metadata, rebindable keys. The durable model is `BoardLibraryStore` in localStorage; `persistence/moodboardSync.ts` is a real
  replication controller (per-board dirty flags, last-write-wins that respects local edits, 2 s debounce, exponential retry,
  tombstones, per-account scoping) behind `MoodboardPersistenceAdapter`, whose methods must never throw. "Send to generation"
  de-duplicates by token and appends to the Image prompt's references.
- **promptbox** (~14.5k lines): one prompt bar per page (`PromptBoxImage/Video/Audio/2D/3D/Edit`), each with its own store;
  **controls appear only when the selected model supports them** (aspect, resolution, quality, reference count, end frame, duration,
  audio); a sortable reference *deck* (dnd-kit), OS drops with live accept/reject, a contentEditable `MentionTextarea` with
  `@`-character chips; video batches fan out to N calls, each with its own subscriber id.
- **generation-list** (~3.5k lines): the unified pending/failed/completed feed (masonry and list); progress is *estimated* from elapsed
  time over the model's `progressBarTime`, capped at 95 %; the finished card replaces the pending card in the same render; missing
  video thumbnails are re-probed with back-off.
- **gallery-modal** (main file 3,771 lines): the library in `view` and `select` (picker) modes; date groups lazily mounted with
  IntersectionObserver; instant reopen from a module cache; OS-style **marquee selection with edge auto-scroll**, right-click menus,
  folder move/copy; a hand-rolled pointer drag engine where the modal turns **translucent and click-through once the cursor leaves it**
  so you can drop onto the canvas behind; a velocity-tilting drag ghost with an ok/blocked badge.
- **lightbox-modal**: full-screen viewer (image batches in a carousel, video, waveform audio, `Viewer3D` for meshes/splats), prompt and
  model metadata, tag chips, and the **action callbacks that route media to every destination** (edit, to video, remove background,
  make 3D, recreate).
- **upload-modal**: split-pane uploaders with live Three/Spark previews snapshotted as the cover thumbnail; **FBX → GLB in a worker**;
  uploads routed by extension, in parallel, per-file status.
- **model-selector**: `ClassyModelSelector` popover with creator icons, capability badges and a provider submenu; selection per page;
  models compared by `tauriId` because instances are rebuilt when the listing hydrates.
- **viewer-3d**: imperative viewer (orbit, grid, GLTF with clip selector, Spark for `.spz/.ply/.splat`), thumbnail capture, and the
  shared `disposeObject3D` (with a spec) used by every 3D surface.
- **vfx**: the "background change" page — a server-side video model only (≤ 15 s input, mask, reference, prompt); no client shaders.
- **camera-settings-modal**: up to six cameras with a focal-length slider that previews live while dragging.
- **soundboard**: howler-played retro UI sounds for enqueue/success/failure/delete, gated by app preferences; **icons**: lucide plus a
  few brand icons; **keybinds**: [03 §7](03-frontend.md).

## 5. Patterns worth studying

| Pattern | Where | Why it is good |
| --- | --- | --- |
| Results as selectable versions with per-version overlays | pagedraw `HistoryStack`, `historyImageNodeMap` | non-destructive iteration; nothing is overwritten by a late result |
| Placeholder per pending job, dismissable | pagedraw, generation feed | the user sees the queue where the result will land |
| Idle pre-bake in a worker, yield one frame before heavy work | pagedraw generate pipeline | click-to-queue latency hidden; UI never freezes on Generate |
| Load-generation counters, tickets, abort signals | pagedraw, pagescene | stale async results cannot overwrite fresh state during fast navigation |
| Engine → event bus → bridge → store, one way | pagescene | the 3D engine stays framework-free and testable |
| Command-pattern undo serialised through a promise chain | pagescene `HistoryManager` | async undo cannot interleave when Ctrl+Z is mashed |
| Drag from library with raycast drop and compatibility badge | pagescene | strong mouse-first affordance |
| Camera as a selectable object with focal length in mm and framing guides | pagescene | photographic language, not FOV numbers |
| Deterministic frame-stepped export via WebCodecs | video-editor, pagescene recorder | exact frame timing, no MediaRecorder quirks |
| Detached-canvas-only context loss | pagescene | no WebGL context exhaustion across tab switches |

## 6. Gaps and debt in these surfaces

Whole-document snapshot undo in 2D; a mask format that is a tinted overlay rather than a binary mask; FK-only posing tied to Mixamo
names; **no control passes from 3D** (depth / normal / pose) — conditioning relies on an edit model reading a beauty render; very large
mixed-concern files (`PaintSurface.tsx`, `SceneState.ts`, `editor.ts`, `scene.ts`); the 3D editor serialises and rebuilds the whole
scene on every tab visit; `setTimeout(500)` and 10 s re-enable timers as race fixes; two incompatible `FilterEngineCategories` enums;
an AGENTS.md that contradicts the code in places.
