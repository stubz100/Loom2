# 03 · Two making suites, Image and Animate, and an animation editor

Status: **accepted as D95, 2026-10-18** (the author's answers in §9), except the EffectCraft route for the preview (§5.2), which waits
for spike E27 and the author's choice. Animate comes first, Story after. Nothing is built yet.

The author (2026-10-18):

> *"The Generate tab is really just an image generation menu, and Edit only edits images … we should have two suites: an image
> generation with comprehensive editing features, and a video/animation editing suite with comprehensive editing features … instead of
> Generate it should be **Image**, and **Edit should be under Image**, easily accessible from anywhere during the image generation process
> … We should build something similar for animations. The current Animate menu should be rearranged to support the process we outlined
> earlier, with **the Stage and clay figures moving into here**. It should also have **the same layout as the current Generate** … everything
> on the same panel scrolling vertically, and it should not over-stretch horizontally … perhaps a **UI/UX review** should also be added to our
> implementation plan … **F:\source\repos\effectcraft** should be the basis of the animation-edit menu."*

## 1. Where we are

Today's top tabs (`frame/railTabs.tsx`): **Story** (with the Catalogue) · **Generate** · **Edit** · **Animate** · **Stage**. The D90
review found the app reading as "nine applications sharing a window" (`.docs/proto01_UI/02-ui-plan.md` §2). For moving pictures it found
three separate places, each with its own transport:

| Today | What it is | Its timeline |
| --- | --- | --- |
| **Animate** (`suites/animate/`, ≈ 1,350 lines) | an image-to-video maker: start/end stills, prompt, beats, model, length → a clip; a frame-accurate player (Mediabunny), compare, onion skin, extract frames, takes | a scrubber for **one clip** with in/out points; no layers, no tracks, no trimming |
| **Stage** (`suites/stage/`, three.js) | the clay world: sets, figures bound to Cast characters, cameras, poses, joint keys (ST4); passes; stills (Clay reference, Exact pose); clips (IC-LoRA depth, Wan Animate) that land in Animate | keyframes for objects, joints and the camera |
| **Episode** (Story, `story/episode/`) | a single-lane cut: clips in order, trims, dissolves, EDL / FCPXML / SRT, a draft render | the cut |

**Edit** (`suites/edit/`, PixiJS on WebGPU) is reached from Generate only through the Catalogue's *Open in Edit* (E), a drop on the Edit
tab, or Animate's *Send to Edit*. **Nothing in loom2 edits a moving picture**: no layers over time, no mattes, no effects, no colour,
no retiming. The clay pipeline (01, 02) needs exactly that: its layers (plate, characters, shadows) must be assembled, corrected and
finished.

## 2. The proposal in one picture

```
Story ─────────── what and in which order: World · Cast · Catalogue · Shots · Flow · Episode (the cut)
Image ─────────── stills: make (today's Generate column)  ⇄  edit (today's Edit, in place)
Animate ───────── one shot in motion: scene (Stage) · motion · performance · edit (the comp) · finish · takes
```

**Three top tabs instead of five.** Each one answers one question:

- **Story:** what happens, and in what order. **Episode stays here**, as the cut of shots.
- **Image:** make and finish a still.
- **Animate:** make and finish one shot in motion. Its editor is a **compositing** editor (one shot, layers over time, After Effects'
  model), not a cutting editor. The cut is Episode's job.

This split matches the tools the author pointed to:

- **EffectCraft** is a clean-room After Effects: layers in a composition.
- Its sibling **FilmCraft** (`F:\source\repos\filmcraft`, a Premiere Pro clone) would be the model for a richer Episode later; not
  proposed now (§9).

## 3. Image: Generate and Edit in one suite

**The tab.** *Generate* is renamed **Image** (Ctrl+2). The *Edit* tab goes away; Edit becomes the Image suite's second mode. Old deep
links (`?suite=generate`, `?suite=edit`) keep working as aliases.

**Two modes, one place:**

| | **Make** (today's Generate) | **Edit** (today's Edit) |
| --- | --- | --- |
| Left column | today's one scrolling column: Saved panels · Prompt · Refs · Look · Camera · Model · Size | **one scrolling column too** (proposed): Tool options · Brushes · Selection · AI · Documents, with the same jump rail and scroll sync (`GenerateColumn`'s pattern) |
| Centre | the results grid (this batch / session / all) | the editor canvas |
| Right | the result's Inspector | Layers · Properties · History · Info (as today) |
| Foot | Generate n ▶ · Queue · Preview | Save (a new version) · Save to Catalogue · PNG · PSD |

**Getting into Edit from anywhere in the making:**

- **Edit ✎** on every result tile (shown on hover; also a right-click menu item);
- a **double-click** on a result;
- the **E** accelerator;
- the Inspector's *Edit* button;
- a switch **Make | Edit** at the top of the column, which returns to the last document.

Edit opens **in place**: the column and the centre swap, and the results stay one click away (**← Results**, or Esc).

**Getting out:**

- *Save* writes a new version beside the original, so the Catalogue keeps both, with lineage.
- *Use as reference* sends the edited image back into the Make column's Refs.

**Edit without making** (open a file, a new document) stays reachable from ☰ › *New document*, and by dropping an image on the Image tab.

The editor's invariants (`suites/edit/AGENTS.md`: keep-alive, WebGPU, the revision on stack writes, candidate layers for AI) do not
change. Only its host and its left panel do.

## 4. Animate: one shot, from clay to final

### 4.1 The layout — Generate's, plus a timeline

```
┌──────────────┬───────────────────────────────────────────────┐
│ the column   │  Viewer           [ Clay | Performance | Final ]│
│ (≈ 30 %,     │                                               │
│  resizable,  │                                               │
│  one scroll, │                                               │
│  jump rail)  ├───────────────────────────────────────────────┤
│              │  Timeline: layers / figures / camera · keys ·  │
│              │  batches · work area · one playhead            │
├──────────────┴───────────────────────────────────────────────┤
│ foot: the shot's cost · Run ▶ · Queue                         │
└──────────────────────────────────────────────────────────────┘
```

- **Two columns, not three.** The left column (default 30 %, drag-resizable, at most 45 %, as Generate) and the viewer. There is **no
  right Inspector**: the selected thing's properties are the column's *Selection* section, which follows the selection. That keeps the
  suite from stretching horizontally, as the author asked.
- **The timeline sits under the viewer.** Its height is resizable; in a narrow window it folds to a scrubber. Time is horizontal by
  nature, so this is the one horizontal element, and it lives inside the centre.
- **One playhead, one transport** for the 3D scene, the performance and the final. D90 §8.2 asked for one transport with one key set;
  this merges Stage's keyframe timeline and Animate's clip scrubber into one.
- **The viewer has three levels**, the three models of the shot from 01 §1:
  - **Clay:** Stage's three.js viewport;
  - **Performance:** the Wan Animate or I2V layers;
  - **Final:** the edited, post-processed composition.

  The level can be switched at any frame. *Compare* shows two levels side by side, or as a wipe.

### 4.2 The column, top to bottom (the process of 01 §2, steps 3–8)

| Section | What it holds | Comes from |
| --- | --- | --- |
| **Shot** | the For chip (the Story shot and version), the frame range, the fps (24), the format, the shot's takes | Animate's ForChip, Story D93 |
| **Scene** | the set (blocks, the library), the figures bound to Cast characters with a version, props, the outliner, layers (which object goes in which layer) | Stage's Library and Outliner tabs, D93 C8 |
| **Motion** | the motion library (clips, retargeted; 01 step 5), pose presets, the selected figure's keys, root motion along a path, foot lock | Stage's Poses tab, ST4; CA1 |
| **Camera** | cameras, the shot camera, camera keys (moves), lens | Stage's Cameras tab |
| **Plate** | the plate still from the empty set; the moving plate (projection / depth-guided video) | 01 step 4; CA3 |
| **Performance** | the method, as cards: **Image to video** (today's Animate: start/end, prompt, beats, model, length — the quick route for a one-character shot), **Pose-driven** (Wan Animate per layer, Move or Replace; the clay pipeline, batches, keyframe stills), **Depth-guided** (IC-LoRA); model and preset; the batch plan and its cost | today's Animate panel; Stage's Render › Clip fold; CA4/CA5 |
| **Edit** | the composition: the selected layer's blend mode, opacity, matte, masks, effects and colour; effect presets as small icons (D90's rule) | new: the animation editor (§5) |
| **Finish** | the post stages of 01 step 8: the layer pass (an amount and a model per layer), the image stream, the final polish, healing patches | E24 → CA7 |
| **Selection** | the properties of whatever is selected: an object, a camera, a key, a layer | Stage's and Edit's Inspectors |
| **Output** | render the final as a take on the Story shot; export (PNG sequence, ProRes 4444, an H.264 proxy) | Animate's takes, D93 |

**Clips** (today's Animate › Clips tab) becomes a Catalogue view (type: clip), shared with Episode's bin. D90 §9 already said so.

**Stills from a stage.** Stage's still methods (Clay reference, Exact pose) make *images*. They move to Image as a source in the Make
column, *From a stage*: pick a stage, a camera and a frame, then render. *Open the stage ▸* jumps to Animate › Scene. The scene is
edited in one place (Animate); stills are made in one place (Image).

### 4.3 What goes away

- the **Stage** and **Edit** top tabs;
- Animate's five rail tabs (Inputs, Model, Length, Presets, Clips) and Stage's five (Library, Outliner, Cameras, Poses, Render), which
  become sections of the one column;
- **two of the four transports** (Stage's and Animate's become one); Episode's stays, with the same keys;
- the "Animate ▶ in Stage is not the Animate suite" confusion (function inventory S28).

## 5. The animation editor, on EffectCraft

### 5.1 What EffectCraft is

Reviewed 2026-10-18 at `F:\source\repos\effectcraft` (v0.12.0, `f36b2b3e`, 2026-10-17):

- **A clean-room reimplementation of After Effects in pure Rust.** In its own counts: ≈ 380k lines, 32 crates, 307 effects, 623
  commands, 3,564 tests. It is part of the ArtCraft family (beside PhotoCraft, which loom2 already uses: D59, D62).
- **Licence:** MIT OR Apache-2.0. The ArtCraft brand assets in `docs/brand/` must not be shipped; the bundled fonts are OFL-1.1. There
  is no GPL/LGPL and no FFmpeg: every codec is pure Rust (decoders from FilmCraft; VP9, HEVC, AV1 and Opus encoders its own; H.264,
  ProRes and AAC from FilmCraft).
- **Maturity: alpha.** Its `ROADMAP.md` puts it at ≈ 91 % of After Effects' breadth but ≈ 45 % "ready for real work", with 216 open
  issues including crash reports. 2,060 commits in 17 days, mostly agent-written; no CI gate on pull requests.
- **The data model is After Effects':**
  - a `Project` holds items: compositions, footage, solids;
  - a `Comp` holds `layers` (footage, comp, solid, text, shape, null, camera, light, 3D model);
  - each `Layer` has in/out points, stretch, a blend mode (38), a track matte, a parent and a **property tree** (transform, masks,
    effects);
  - each property has **keyframes** (linear, Bezier, hold, eases, roving) and an optional expression.

  Projects are saved as `.ecproj` (versioned JSON).
- **The engine is cleanly layered** (`docs/architecture.md`, enforced by `cargo xtask layers`). Nothing below the UI layer depends on
  egui or winit, and **every engine crate builds for wasm32**. The engine `Session` takes every edit as `execute(command_id, json)`, with
  branching undo.
- **Rendering:**
  - a CPU compositor (the reference);
  - a wgpu compositor that mirrors it (280 effects on the GPU, checked against the CPU to ≤ 1/255), on WebGPU in a browser;
  - a layer cache.
- **Export:** H.264 / HEVC / AV1 MP4, ProRes (4444 with alpha), WebM (VP9 with alpha), PNG / TIFF / EXR sequences.
- **Interfaces:** a CLI (`effectcraft-cli render | exec | get | set | mcp`) and an MCP server.
- **Features that matter to us:**
  - masks and roto: the pen tool, feather, Roto Brush with MobileSAM;
  - point tracking and stabilisation;
  - **Pixel Motion / Timewarp** (optical-flow retiming), relevant to 01's B3 in-betweens and A5's flow propagation;
  - colour: Curves, Levels, Lumetri, scopes;
  - track mattes and blend modes;
  - motion blur;
  - Lottie and FCPXML / OTIO / EDL interchange.
- **The user interface is egui** (≈ 85k lines), in its own window or one 58 MB WebAssembly canvas. **None of it can be used inside
  loom2's React app.** Its timeline, graph editor and viewer overlays are design references only.

### 5.2 How loom2 would use it

The PhotoCraft precedent (D59, D62) shows the pattern: **loom2 keeps its own mouse-first React UI** and uses the sibling's engine through
a **pinned, prebuilt artifact** with a build script and a CI check, rebuilt only when the pin moves.

| Route | What | For | Verdict |
| --- | --- | --- | --- |
| **R1 · WebAssembly facade** | a small crate over `engine` + `render` + `gpu` (no `ui-egui`, no encoders) with wasm-bindgen: `execute(cmd, json)`, `render_frame(comp, t, scale)`; run in a Web Worker on the webview's WebGPU | the **interactive preview**: scrubbing, playing, every edit visible at once | **the page's share of the preview** (§5.2a), not the whole of it; kept open (the author: not ruled out) |
| **R2 · CLI sidecar** | the pinned `effectcraft-cli` binary, driven by the orchestrator as a job (`render` of a `.ecproj` to PNG / ProRes / H.264) | the **final render and export**, at full size, in the queue like every other job (stall handling, staging, lineage) | **proposed** |
| R3 · link into the Tauri shell | the engine crates inside `src-tauri`, frames to the webview over a custom protocol | the preview, natively | not proposed: it makes the thin shell a 380k-line build, breaks the browser dev mode (`dev.ps1 -Browser`), and needs a readback and IPC for every preview frame |
| R3b · a native preview server | the pinned engine as a sidecar beside the orchestrator, frames over loopback HTTP | the preview tiers T1–T3, natively | **proposed: the main preview** (the author, 2026-10-18), in tandem with the page (§5.2a) |
| R4 · a loom2 compositor of its own | Mediabunny decode + a WebGPU / Pixi canvas compositor for layers, blends, opacity and transforms; EffectCraft only for export | the fallback | **the page's first tier** (§5.2a): what the page can draw alone, instantly |

**The difference between R1 and the native routes, explained** (the author's question 5, 2026-10-18).

The final render is R2 in every case: the pinned command-line tool, run by the orchestrator as a job. The question is only **where the
interactive preview runs**, the frames you see while scrubbing and editing. There are two kinds of answer:

- **R1, inside the page.** The engine is compiled to WebAssembly and runs in a Web Worker of the webview, the same place loom2's React
  UI and Edit's canvas run. It draws with the webview's WebGPU straight into a canvas.
- **Native, outside the page.** The engine runs as ordinary Rust on the machine and sends finished frames to the page. Two ways:
  - **R3:** linked into the Tauri shell, with frames over the shell's IPC;
  - **R3b:** a small preview server the orchestrator starts beside ComfyUI (EffectCraft already has a control channel), with frames over
    loopback HTTP, the way Edit's pixels travel today.

| | **R1 · WebAssembly in the page** | **R3 / R3b · native engine, frames sent to the page** |
| --- | --- | --- |
| A frame on screen | rendered on the GPU into the canvas; nothing is copied | rendered on the GPU, **read back** to the CPU, sent over IPC or HTTP, uploaded again: ≈ 1.6 MB a frame at 832×480 (≈ 38 MB/s at 24 fps), ≈ 8 MB at 1080p. Adds latency to every scrub |
| Speed of heavy effects | the GPU path is about the same; the CPU fallback is slower (WebAssembly threads, SIMD) | full native speed, every CPU thread |
| Memory | at most 4 GB (32-bit WebAssembly); EffectCraft's web build caps its caches at 512 + 256 MB | no such limit |
| Video decode | in the page (EffectCraft's pure-Rust decoders on the CPU, or loom2 feeding frames from Mediabunny / WebCodecs, hardware decode) | native, multi-threaded |
| Browser dev mode and the Playwright smoke | **work as today** (`dev.ps1 -Browser`, Edge against the orchestrator) | R3 exists only inside the Tauri app, so the browser and the e2e cannot see the editor. R3b works in the browser too |
| Building loom2 | one prebuilt `.wasm`, pinned with a checksum and a build script (D59's pattern); the app build needs no Rust | R3: the shell compiles EffectCraft's ≈ 650 packages (Rust ≥ 1.95, git dependencies) in every installer build and CI run. R3b: one prebuilt binary, pinned like the CLI |
| A crash in the engine | kills the worker; the editor restarts it, and the app stays up | R3: takes the whole app window down. R3b: kills the sidecar; the orchestrator restarts it |
| GPU sharing with ComfyUI (16 GB) | through the browser's GPU process, like Edit | another native GPU device on the same card |
| Fits loom2's rules | yes: the shell stays thin, pixels never cross Tauri IPC | R3 no (pixels over IPC); R3b yes (loopback HTTP) |

**In short.**

- **R1** keeps everything in the page: no copying, nothing new to build in the app, and it works in the browser and the tests. Its
  limits are WebAssembly's: memory, and CPU-side speed.
- **The native routes** are faster for heavy work, at the cost of sending every preview frame across a process boundary.
  - **R3** (in the shell) also costs build time and crash isolation, and loses the browser mode. **Not proposed.**
  - **R3b** (a preview server beside the orchestrator) keeps those, and is **the native fallback** if E27 finds R1 too slow or too big.

**The author's answer (2026-10-18):** the in-page preview alone is not enough, but is not ruled out. The preview server beside the orchestrator is preferred, working **together with the page** to stream the best preview it can, with quality steps down. The final render is a backend job. §5.2a describes how EffectCraft separates the two, and the balanced design.


### 5.2a · Preview and full render: how EffectCraft does it, and the balance for loom2

**In EffectCraft** (read from its code and docs, v0.12.0), as in After Effects, one engine renders under two sets of options.

**The viewer** (the interactive preview):

- **Resolution** per composition: Auto (follows the zoom), Full, Half, Third, Quarter or Custom (every n-th pixel)
  (`project::Resolution`).
- **Layer quality:** Best, Draft or Wireframe.
- **Fast Previews:**
  - *Adaptive Resolution* drops the resolution while you drag, down to a set limit (½, ¼ or ⅛). A playing preview keeps the viewer's
    resolution.
  - *Draft* turns off 3D lights, depth of field and shadows, and uses faster effects.
  - *Fast Draft* and *Wireframe* go further.
- **Caches:**
  - a **layer cache**, keyed by content hash, so an unchanged layer is not rendered again;
  - a footage frame cache;
  - a **RAM preview cache**, filled for the work area so it plays in real time ("Cache Frames When Idle" fills it after a second without
    input);
  - an optional **disk cache** that survives sessions.
- **Proxies:** a footage item or a composition can have a lighter stand-in file for editing. The render chooses whether to use it.

**The render queue** (the final): render settings (quality Best, resolution Full, frame rate, motion blur, frame blending, effects,
colour depth) plus output modules (the encoders). Every frame renders on the project's renderer, so runs are repeatable.

**In its browser build the work is already split three ways** (`docs/web.md`):

- **The page** draws frames without effects itself, on WebGPU (no copy).
- **Frame workers** hold a replica of the project and render the rest. They are kept up to date by **diffs**: a slider drag sends a
  few hundred bytes, not the project. A render request names the revision, time and render options, and a stale revision is refused
  (`engine/src/remote.rs`).
- **Job workers** run the render queue, apart from the viewer.

So the author's guess is right: **one engine with a preview mode and a full-render mode** is how EffectCraft itself works.

**The balance for loom2: the page and a preview server, in tandem.**

```
 page (React + WebGPU)                    preview server (native EffectCraft, beside the orchestrator)
 ─────────────────────                    ──────────────────────────────────────────────────────────────
 T0  draws at once what it can:           holds a replica of the composition (diff sync by revision,
     cached layer frames, transforms,     EffectCraft's remote protocol), renders on request:
     opacity, blend modes, mattes         T1  while scrubbing or dragging: adaptive resolution (¼–½),
     (no effects), so a drag never              Draft quality — the frame lands in ≈ 1 frame time
     waits                                T2  when the playhead stops: Full at Draft, then Best
 shows the best frame it has; swaps       T3  when idle: the work area into the RAM / disk cache,
 in a better one when it arrives              so playback is real time at the chosen quality
                                          frames over loopback HTTP (raw at ¼, JPEG/WebP or raw at full)

 final render: a queued orchestrator job, `effectcraft-cli render` (Best, Full, the encoders) — a separate process (R2)
```

- **Progressive refinement.** The page always shows the best frame it holds and swaps in a better one when the server sends it: T0
  instantly, T1 while moving, T2 at rest, T3 for playback.
- **Priority.** The server renders the frame under the playhead first, then a few frames around it (prefetch), then the idle cache.
  A newer revision cancels older requests.
- **Quality steps down under load.** While ComfyUI runs a job (the orchestrator knows), the server lowers its resolution floor and
  can move to its CPU renderer, so a generation is never starved of VRAM. The step taken shows in the viewer ("¼ · Draft").
- **Preview and final are two processes.** The long-lived preview server and the queued render job are separate, so a long render
  never blocks scrubbing, and a crash in one does not take the other.
- **R1 stays possible.** If WebAssembly proves fast enough later, it can take over T0 and T1 in the page, and the server keeps T2,
  T3 and the final.

**E27 (rescoped):**

- build the preview server over `effectcraft-host` (no egui) with the diff sync and a frame endpoint;
- measure T1, T2 and T3 on a 3-layer 832×480 composition with a mask, a blur and a track matte, with ComfyUI idle and running;
- measure T0 in the page (a WebGPU compositor of cached layer frames, R4's code);
- R1 only as a comparison, if time allows.

**Bars:** T1 ≥ 12 fps while scrubbing; T2 Full Draft ≤ 150 ms a frame; T3 real-time playback after the cache fills; the final equal to
T2 Best (≤ 1/255).

**The document.**

- A shot version owns **one composition**: an `.ecproj` in the project's shot folder, written through `fsio`.
- It is wrapped in a loom2 record with `schema_version`, lineage (the stage revision, the layers' clips) and the pinned EffectCraft
  version.
- The orchestrator **writes** the composition, for example from the clay pipeline's assembly (02 CA6: plate, figure layers, mattes,
  shadow pass, depth order) or from a single clip.
- The author **edits** it in the Animate › Edit section.
- **The render reads it.**

Files are truth (house rule 4): the composition is a file, and the preview and the render read the same one.

### 5.3 What the editor does (first version)

The **curated subset** a storyboard shot needs, not After Effects' whole surface:

- **Layers:**
  - the plate, each figure's clip, the shadow pass, solids and text;
  - order, solo / hide / lock;
  - in/out trim, slip and move;
  - parenting; blend modes; opacity;
  - track mattes (a figure's matte from its mask sequence).
- **Keys:**
  - transform and opacity keys in the timeline (drag, box-select, copy);
  - ease and hold through a right-click menu (D32: every action has a mouse placement; After Effects' keys are accelerators only);
  - the graph editor later.
- **Masks:** the pen tool, feather and expansion. The roto refine of a figure's matte uses SAM 3 (loom2 has it) or MobileSAM
  (EffectCraft's).
- **Effects and colour,** about 20 to start:
  - Curves, Levels, Hue/Saturation, Lumetri (basic);
  - Gaussian and directional blur, glow, grain;
  - drop shadow;
  - a keyer;
  - Pixel Motion / Timewarp.

  Each is applied from **icon presets** (D90's rule), with its parameters in the column.
- **AI passes on a layer:** the post stages of 01 step 8 (E24 decides which) run as jobs. A result lands as a **new version of that
  layer's footage**, a candidate the author keeps or rejects, as Edit's AI results land as candidate layers. A **healing patch** (A6) is a
  region drawn in the viewer over a frame range marked on the timeline.
- **Output:** render the final (R2) → a clip → a **take on the Story shot** (D93) → Episode.

## 6. The UI/UX review in the plan (the author's request)

Two reviews, one before the build and one after it:

- **UX0 · before any build (≈ 2–3 days).**
  1. Update the function inventory (`.docs/proto01_UI/01-function-inventory.md`) for the three-tab model: every function of Generate,
     Edit, Animate and Stage gets its new home (section, mode, menu); none is lost.
  2. Low-fidelity **wireframes** of Image (Make, Edit) and Animate (each column section, the three viewer levels, the timeline) as an
     HTML mock, with screenshots for the author.
  3. **Walk the canonical paths** and count the clicks (D32's rule: every action is reachable by mouse):
     - a character → an image → an edit → a shot frame;
     - a shot → a stage → motion → a performance → an edit → a take → the Episode;
     - a quick shot: an image → image-to-video → a take.
  4. **The author reviews and corrects** the wireframes before IM1.
- **UX9 · after the build (≈ 1–2 days).**
  1. The same paths in the built app (`scripts/edit_headed_check.py`-style headed checks, screenshots).
  2. A heuristic pass: discoverability, one transport and one key set, consistent names, mouse placements, nothing over-stretching at
     1280 px.
  3. The author's click-through.
  4. Findings go into a register and are fixed.

## 7. Implementation plan

Effort in working days; every wave ends with its tests (Vitest, the e2e smoke, the command audit) and, where it touches the engine, a rig
check. The waves of this document are named **IM** (Image), **AN** (Animate) and **AE** (the animation editor).

| Wave | Content | Effort | Acceptance |
| --- | --- | --- | --- |
| **UX0 · Review and wireframes** | §6: the inventory for three tabs, the wireframes, the click paths; the author's corrections | 2–3 | the author signs off the wireframes; every inventory row has a home |
| **IM1 · The Image suite** | Generate → **Image**; Edit becomes Image's second mode (Make ⇄ Edit in place, ← Results, Edit ✎ on tiles, double-click, E, the switch); Edit's left panel becomes one scrolling column; Save writes a new version with lineage; *Use as reference*; ☰ › New document; deep-link aliases; the Edit tab removed; Ctrl+1–3 re-assigned; the e2e smoke and the command audit updated | 3–4 | the e2e smoke under both variants; a headed edit check (WebGPU) inside Image; no function of the inventory lost |
| **AN1 · The Animate shell** | the one column with the jump rail and scroll sync (§4.2's sections); Stage moves in (its tabs become Scene, Motion, Camera; its viewport becomes the *Clay* level); today's Animate becomes the *Image to video* card of Performance; the viewer's three levels and Compare; **one timeline and one transport** (Stage's keys + the clip scrubber); no right Inspector (the Selection section); Clips as a Catalogue view; *From a stage* in Image; the Stage tab removed | 6–8 | every Stage and Animate function reachable (the inventory); the e2e smoke; the existing rig checks for Stage stills and clips (ST3, CN4) still pass |
| **E27 · Spike: EffectCraft as the engine** (beside E23) | §5.2a: the preview server (R3b) with tiers T1–T3 + the page tier T0 (R4's compositor); R1 only as a comparison; at a pinned commit (no egui; no encoders in the preview): its size (raw and compressed), the start-up time, the preview frame time for a 3-layer 832×480 composition with a mask, a blur and a track matte, at 24 fps, in the webview on the RX 9070 XT (headed, WebGPU); the memory, with ComfyUI running beside it; the R2 CLI render of the same composition, CPU against GPU and against the preview (≤ 1/255); our toolchain (Rust ≥ 1.95; the shell declares 1.90) | 2–3 | a D-number: R1 + R2, R3b + R2 or R4 + R2, with the numbers |
| **AE1 · The composition** | the shot version's composition (`.ecproj` in a loom2 record, fsio, lineage, the pin); the orchestrator writes it from a single clip and from the clay assembly (with CA6); a `comp_render` job through the CLI (R2) with staging, stall handling and its cost; the pinned binary with a build script and `--check` in CI (D59's pattern) | 3–4 | a composition written, rendered and reopened byte-identical; the render matches the preview |
| **AE2 · Viewer and timeline** | the R1 worker (or R4); layer rows with trim, slip and move; transform and opacity keys (drag, ease and hold by right-click); blend modes, opacity, track mattes, solo / hide / lock, parenting; the pen tool for masks; undo through the engine's history; every action a command with a mouse placement | 6–8 | a 3-layer shot edited by mouse alone; scrubbing at ≥ 12 fps at Draft size; undo and redo across every action |
| **AE3 · Effects and colour** | the curated ≈ 20 effects as icon presets with their parameters in the column; colour (Curves, Levels, Lumetri basic) with a before/after | 3–4 | each effect's preview matches the CLI render; presets apply in one click |
| **AE4 · AI passes on layers** | the post stages E24 keeps, as layer jobs landing as candidate footage versions; the healing patch (a region × a frame range); the roto refine of a matte (SAM 3) | 4–5 | a layer pass and a patch on the acceptance shot within E24's bars; keep and reject per candidate |
| **AE5 · Output** | render the final → a clip → a take on the Story shot (D93); PNG sequence, ProRes 4444, an H.264 proxy; Episode picks it up | 2 | the take plays in Story › Shots and exports through the Episode |
| **UX9 · Review after the build** | §6 | 1–2 | the register fixed; the author's click-through |

**Total:** about 32–43 working days.

**How it meets the clay plan (02):**

- **UX0, IM1 and AN1 come first.** They re-house what exists, so the clay waves are built into the new Animate suite from the start.
- **E27 runs beside E23.**
- **CA6 (assembly) writes an AE1 composition** instead of a flat clip.
- **CA8 (the clay UI) folds into AN1 and AE2.** Its Animate-shot panel is the Performance section plus the timeline.
- **AE4 carries CA7's post stages** into the editor.

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| EffectCraft is alpha and moves very fast (crashes in its issue list, no CI gate) | a pinned commit, rebuilt only on purpose; only the curated subset is exposed; every composition is a file the CLI can re-render; R4 as the fallback |
| The WebAssembly facade is too big or slow in the webview (the full web app is 58 MB raw) | no egui and no encoders in the facade; measured in E27; a Draft-size preview; R4 |
| Two GPU users on 16 GB: ComfyUI and the WebGPU preview | the engine's `reserve_vram_gb` (1.5 GB) already keeps room for Edit's canvas; E27 measures it with a job running |
| Headless Edge cannot present WebGPU (as for Edit) | headed checks, as `edit_headed_check.py` does |
| Building the editor UI is the big cost (EffectCraft's UI cannot be reused) | the curated subset first; EffectCraft's timeline and graph editor as design references |
| After Effects' keyboard habits against D32 | every action a command with a button or menu; keys only as accelerators |
| Moving Stage and Edit breaks habits and links | deep-link aliases; the inventory in UX0; the e2e smoke and the command audit |
| H.264 / HEVC encoding carries patent licensing separate from copyright | the author's D17 reading before shipping those encoders; ProRes, PNG and VP9 / AV1 need no such reading for a storyboard master |

## 9. Questions for the author — answered 2026-10-18 (D95)

| # | Question | The author's answer |
| --- | --- | --- |
| 1 | Three tabs: Story · Image · Animate? | **Yes**, for now |
| 2 | Stills from a stage made in Image, the stage edited in Animate? | **Yes**. The Catalogue will play a role here, grouping images, videos and other objects efficiently: ideas mocked up in [04](04-catalogue-for-making.md) |
| 3 | Edit's left panel as one scrolling column? | **Yes** |
| 4 | Animate without a right Inspector? | **Yes, on trial**; it can be reinstated |
| 5 | The EffectCraft route? | **Explanation asked**; given in §5.2 ("The difference between R1 and the native routes"). Open until E27 |
| 6 | Episode stays the cut in Story? | **Yes**, with FilmCraft as its model for later enrichment. **Animate first, Story afterwards** |
