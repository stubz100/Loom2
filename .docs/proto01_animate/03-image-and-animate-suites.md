# 03 · Two making suites, Image and Animate, and an animation editor

Status: **proposal, 2026-10-18, for the author to refine.** Nothing is decided or built. If the author accepts the direction, it becomes a
D-number (D95) before any work (the house rule). The effectcraft route gets its own D-number after its spike (§5).

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
| **R1 · WebAssembly facade** | a small crate over `engine` + `render` + `gpu` (no `ui-egui`, no encoders) with wasm-bindgen: `execute(cmd, json)`, `render_frame(comp, t, scale)`; run in a Web Worker on the webview's WebGPU | the **interactive preview**: scrubbing, playing, every edit visible at once | **proposed**, if E27 finds the size and speed acceptable |
| **R2 · CLI sidecar** | the pinned `effectcraft-cli` binary, driven by the orchestrator as a job (`render` of a `.ecproj` to PNG / ProRes / H.264) | the **final render and export**, at full size, in the queue like every other job (stall handling, staging, lineage) | **proposed** |
| R3 · link into the Tauri shell | the engine crates inside `src-tauri`, frames to the webview over a custom protocol | the preview, natively | not proposed: it makes the thin shell a 380k-line build, breaks the browser dev mode (`dev.ps1 -Browser`), and needs a readback and IPC for every preview frame |
| R4 · a loom2 compositor of its own | Mediabunny decode + a WebGPU / Pixi canvas compositor for layers, blends, opacity and transforms; EffectCraft only for export | the fallback | **the fallback**, if R1 fails E27 |

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
| **E27 · Spike: EffectCraft as the engine** (beside E23) | build the R1 facade at a pinned commit (no egui, no encoders): its size (raw and compressed), the start-up time, the preview frame time for a 3-layer 832×480 composition with a mask, a blur and a track matte, at 24 fps, in the webview on the RX 9070 XT (headed, WebGPU); the memory, with ComfyUI running beside it; the R2 CLI render of the same composition, CPU against GPU and against the preview (≤ 1/255); our toolchain (Rust ≥ 1.95; the shell declares 1.90) | 2–3 | a D-number: R1 + R2, or R4 + R2, with the numbers |
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

## 9. Questions for the author

1. **Three tabs:** Story · Image · Animate, with the Stage and Edit tabs gone?
2. **Stills from a stage:** made in Image (*From a stage*) while the stage itself is edited in Animate, or should Stage stills stay in
   Animate?
3. **Edit's left panel** as one scrolling column too, like Make's?
4. **Animate without a right Inspector** (the Selection section in the column), to keep it from stretching sideways?
5. **The EffectCraft route:** the WebAssembly preview + the CLI render (recommended, after E27), or the native link in the shell?
6. **Episode:** keep it as the cut in Story (FilmCraft as its model later, if it needs tracks), with Animate's editor for one shot?
