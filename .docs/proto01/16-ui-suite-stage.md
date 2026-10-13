# 16 · Suite E — Stage (3D blocking → control passes → image / clip) — UI document

Status: **approved 2026-10-13 (D81) with the §14 defaults; ST1 in progress.** Proposed 2026-10-12. Plan: ArtCraft 08 §8 (P13, slices ST1–ST4, 25–30 d). Conditioning
decided by the spikes: E10 → D78 (the clay reference by default, RefControl as the "exact pose" switch), E11 → D76 (LTX-2.3 with its
IC-LoRA on the depth pass). Props: E14 → D79 (Pixal3D, P18, after ST1). Frame rules: 07 (D32 mouse-first, D34 drags, D69 keep-alive,
D71 drops explain themselves, D72 remappable keys). The design takes ArtCraft's stage *as design, re-implemented* (ArtCraft 04 §2,
07 §P13): vanilla Three.js behind an event bus → bridge → store, canvas hosts never unmounted, cameras as objects in photographic
language, command-pattern undo — and does what it does not: control passes, IK and pose presets, scenes as project files.

## 1. Purpose
Block a storyboard shot in 3D — a set, one or two posed figures, a camera with a real focal length — and turn the blocking into a
consistent image (ST3) or a clip that follows the camera (ST4), with the same characters and set shot after shot. The stage is the
*place* a shot is composed; the image models do the rendering. Everything a shot needs is a file in the project (`stages/<id>.json`,
passes and results as assets), reopened exactly.

## 2. Layout

```
Rail: [Library] [Outliner] [Cameras] [Poses] [Shot]
┌────────────────────────┬──────────────────────────────────────────────────┬──────────────────┐
│ Panel · Library        │ Strip: view ◉ camera ○ free   ▣ guides  passes ▾  ◉ clay ○ depth ○ pose │ Inspector        │
│ Figures                ├──────────────────────────────────────────────────┤ Object · Pose ·  │
│  ▢ mannequin  ▢ child  │ ┌─ gizmo bar ───────────────┐                    │ Camera · Shot    │
│ Sets                   │ │ ↖ select  ✥ move  ⟳ rotate │                    │ ───────────────  │
│  ▢ room  ▢ street      │ │ ⤢ scale   ⌖ snap ☐ local ☐ │                    │ Mannequin · Ada  │
│  ▢ deck   ▢ empty      │ └───────────────────────────┘                    │ x 0.00 y 0 z 0   │
│ Props                  │                                                  │ yaw 30°          │
│  ▢ crate  ▢ stool      │               Viewport (three, WebGL2)           │ pose: point ▾    │
│  ▢ plane (image)       │     ┌─ framing rect 16:9 · thirds ─┐             │ ☐ locked ☑ shown │
│  (E14 props, P18)      │     │       figures · set         │             │ ───────────────  │
│ Album ▸ cut-outs (D33) │     └──────────────────────────────┘             │ Mirror · Reset   │
│ drag → raycast drop    │                                                  │ Duplicate · ✕    │
│                        ├──────────────────────────────────────────────────┤                  │
│ [ Render passes ▶ ]    │ Dock  ▸ Running: stage-shot klein-9b 2/4 ███░ 00:09   · Queued 0     │                  │
└────────────────────────┴──────────────────────────────────────────────────┴──────────────────┘
```

The Rail tabs switch the Panel. The primary action pinned at the Panel's foot follows the tab: **Render passes** (Library · Outliner ·
Cameras · Poses) or **Generate** (Shot). The Strip switches the viewport between the *free* view (helpers, gizmos) and the *camera*
view (what the render camera sees, with the framing rectangle at the project's aspect), toggles guides, and previews a pass in the
viewport (clay · depth · normal · pose · masks) without leaving the scene.

## 3. Rail · Panel

### 3a. Library
Cards by category with a search box; click adds at the viewport centre, **drag** drops where the ray hits the floor or a surface
(`frame/drag.ts`; the ghost says "Place on the floor" / "Place on crate").
- **Figures:** the procedural mannequin of E10 (`frontend/src/spikes/e10Stage.ts`, lifted into `suites/stage/`): a joint tree with
  COCO-18 markers, no licence question, already proven to carry a blocking (E10, D78). Sizes: adult 1.75 m, child 1.2 m. ST2 adds the
  CC0 Quaternius base mannequins as skinned bodies on the same joint names; **Mixamo assets must not ship** (08 §7).
- **Sets:** primitives that read as rooms, streets, decks (floor, walls with openings, a few blocks) — the three E10 sets plus
  *empty*. Walls carry object-ID colours for the masks pass.
- **Props:** primitives (crate, stool, table, pole) now; P18 adds meshes made from a cut-out (E14, Pixal3D) into this list, tagged
  with the source asset.
- **Image planes:** any Catalogue asset as a plane (its BiRefNet cut-out one click away, D33: *Cut out* on the card); a plane
  faces the camera by default (billboard) or stands fixed. Albums and groups drop as a stack of planes.
- A card's menu: Add · Add at cursor · Open source (planes) · Remove from library (user items).

### 3b. Outliner
A tree of the scene: figures, set, props, planes, cameras. Rows show name, type icon, 👁 visibility and 🔒 lock toggles, and the
object-ID swatch. Click selects (the viewport follows), double-click frames the object, drag reorders / parents (a prop onto a figure's
hand parents it). Row menu: Rename · Duplicate · Mirror (figures) · Frame · Hide others · Lock · Delete. The Outliner is the only
list; there is no second "layers" view.

### 3c. Cameras
The shot's cameras as a list (one is *active*; the Strip's camera view and every pass render use it). A camera is an object:
**focal length in mm** (sensor 36 mm, the full-frame vocabulary: 24 · 35 · 50 · 85 presets and a slider 14–200), position and
target, roll, and the aspect and size from `project.json` (D18: 16:9, the Draft tier of the recipe's model by default). Buttons:
Add camera · Duplicate · Look through (free view ↔ camera view) · Frame all · Set from view (copies the free view into the camera)
· Delete. Framing guides: rectangle, thirds, centre cross, title-safe (the Strip's *guides* toggle, remembered).

### 3d. Poses
Presets as a grid of silhouettes (stand, sit, walk, run, point, reach, crouch, wave, look left, arms crossed — E10's ten, in
`stages/poses/*.json`, user presets saved beside them). Click applies to the selected figure(s); **Mirror** swaps left/right;
**Reset** returns to rest; **Save pose…** (`askText`) stores the current joints as a preset. ST2 adds posing in the viewport:
FK on joint pickers (click a joint, a rotate gizmo appears) and **two-bone IK** handles at hands and feet (drag the hand, elbow
and shoulder follow; analytic, with `CCDIKSolver` as the fallback); the pose tab shows the active joint's angles.

*ST2 built 2026-10-13 (journal of that day): the Poses rail tab shows the ten built-in presets (`builders.ts POSES`, in code rather
than `stages/poses/*.json` — they are the mannequin's own) and the project's saved poses from one file, `stages/poses.json`
(`GET` / `PUT /stages/poses`, each pose `{preset, joints}` with a delete ×). While the tab is open the selected figure wears its
pickers: orange spheres on the twelve joints (click → the rotate gizmo in local space, the free-rotate ball off so neighbours stay
clickable) and blue cubes at hands and feet (click → a translate gizmo on a proxy; dragging it solves the two bones analytically in
the chain parent's space, `ik.ts solveTwoBone`, bend hints elbows +Z / knees −Z; out of reach the chain points at the target). Every
commit writes the twelve joints in degrees (YXZ) into the document, one undo entry; Mirror swaps left / right and negates Y / Z;
Reset returns to stand; the tab also takes a joint from a list and its x · y · z by number. `CCDIKSolver` was not needed.*

### 3e. Shot
The generation form for the blocking, generated from `/capabilities` (07 §3d):
- **Method** (D78): ◉ **Clay reference** — Klein 9B, the clay pass as `ReferenceLatent`, "keep image 1's camera, framing and poses";
  ≈ 12 s, keeps the blocking (10/10 on the E10 sheet), limbs may drift (PCK 0.60). ○ **Exact pose** — Klein base 9B + the
  RefControl pose LoRA, the pose pass as image 1 and a character reference as image 2; ≈ 74 s, PCK 0.86. Each shows its measured
  time and what it is good for; *Exact pose* needs one reference and says so.
- **Prompt** with the reference deck (D73): slots and `@`mentions; the notes feed the "image N shows …" sentences. The clay / pose
  pass is always image 1 and is shown as a locked first slot.
- **Size** from the project tier (Draft by default, HD / Full as the model allows), **seeds** (candidates 1–4), **preset**.
- Foot: **[Generate ▶]** (`Ctrl+Enter`) — renders the passes for the active camera if they are stale, uploads them, queues
  `StageShot`; the estimate line names the method's measured time. **Stage** queues without starting (09's staging).

## 4. Stage · Viewport
- One `three` scene on its **own canvas and WebGL2 renderer** (separate from Pixi; Edit may be on WebGPU). The suite is
  `keepAlive` under D69's policy: the Stage stays mounted and hidden after the first visit, pauses its render loop while hidden,
  and is released like Edit after *Keep … loaded* minutes or on `engine.vram_pressure` — the viewport's GPU memory is the reason the
  plan asked for a measurement, and the policy already exists for it. Re-entry reloads the stage file (≤ 300 ms budget).
- **Navigation** (owned by the viewport): orbit = drag, pan = `Space`+drag or middle drag, zoom = wheel; `Ctrl+0` frame all,
  `Ctrl+1` frame selection; the free view never moves the render camera unless *Set from view* is pressed.
- **Gizmo bar** (floating over the viewport's top-left, always visible): Select · Move · Rotate · Scale · Snap · Local/World — the
  mouse home of every transform (D32); `G` / `R` / `S` are accelerators shown in the tooltips. The gizmo is `TransformControls`;
  dragging a figure keeps it on the floor unless *free* is on; rotate snaps at 15° with Snap.
- **Right-click on an object:** Frame · Duplicate · Mirror · Pose ▸ presets · Parent to… · Lock · Hide · Delete. On empty space:
  Add ▸ (library categories) · Camera here · Paste.
- **Camera view** draws the framing rectangle at the project aspect, darkens outside it, and shows the guides; everything outside
  the rectangle is still editable. The pass preview (Strip) swaps the viewport's material / shader for clay, linear-disparity depth
  (near white, far black, 1/z), view-space normals, the COCO-18 skeleton or the object-ID masks — the exact images the recipe gets.
- **Selection** follows 07 §3b (click, Ctrl, marquee on empty floor); the Inspector shows the primary object.
- **Undo** is command-pattern (`UndoableAction {label, apply, revert}`) serialised through a promise chain, suite-scoped
  `Ctrl+Z` / `Ctrl+Shift+Z`; every edit in this document is an action with a label the toast shows.

## 5. Inspector
- **Object:** name, type, transform (x y z · yaw pitch roll · scale, typed), locked / visible, parent, object-ID colour, the source
  asset for planes and props (open in the loupe). Duplicate · Mirror · Delete.
- **Pose** (figures): the preset, per-joint angles (collapsed), Mirror · Reset · Save as preset; ST2: IK handles on / off.
- **Camera:** focal mm, sensor, position / target / roll, aspect · size (from the project, read-only with a link to Settings),
  Look through · Set from view · Frame all.
- **Shot** (when a result is selected in the Dock or the Catalogue): the method and its time, the passes used (thumbnails, open in
  the loupe), the prompt, references, seed; **Keep / Reject / Rate**, **Re-run** (same passes), **Variations**, **Send to Edit**,
  **Send to Animate as start** — the frame's verbs (07 §3c); **Open the stage at this camera** from the Catalogue side.

## 6. Dock
The frame's job queue (stage-shot jobs show step progress and the method); ST4 adds a **Shots** strip under the viewport (like
Animate's timeline under the player): a frames ruler with camera and object keyframes (◆), the pass-sequence range and the clip
pins — not a second timeline implementation (P17 owns clips; this is keyframes).

## 7. Passes → image (ST3)
1. **Render passes** (client, three): for the active camera at the recipe's size — clay (grey Lambert, soft key light), depth
   (linear disparity, per-scene normalisation), normals, pose (COCO-18 from the joint positions, OpenPose colours and limb order),
   object-ID masks (one flat colour per object, a legend in the sidecar). The keypoints are kept as JSON beside the passes.
2. **Upload** as assets: `POST /stages/{id}/passes` → each pass is an asset with `lineage_kind = stage-pass`, `metadata {stage_id,
   camera_id, revision, pass, size}`, grouped under the stage's album page (D34) so they are findable and never mistaken for results.
3. **Recipe** `StageShot {stage_id, camera_id, passes: {clay, pose?}, method: clay | refcontrol, prompt_text, refs[], seeds[],
   width, height, preset, te_id?}` with spec entries (klein-9b for *clay*, klein-base-9b + the RefControl LoRA for *refcontrol*) and a
   graph builder in `engine/graphs.py` ported from `engine/spikes/e10_stage.py`; `/capabilities` lists the methods with their
   measured seconds; `/recipes/preview` shows the sentence image 1 gets.
4. **Results** land in the Catalogue next to the passes with `lineage_kind = stage-shot`, parents = the passes (+ references), the
   job's `origin {suite: stage, surface: shot, ref: stage_id/camera_id}` (D66) — the Dock's *Go to origin* reopens the stage at
   that camera.
Stale passes: the Shot tab shows "passes from revision 12, scene is at 15 — re-render on Generate" and does it unless *Use as is*.

## 8. Shots → clip (ST4)
Keyframes on the camera and objects (position, rotation, pose preset, linear or ease), a frame range at the project's fps (D18:
24), **Render sequence** → the depth pass per frame (the E11 guide) and the first frame's clay pass → the `I2V` recipe gains
`guide {asset_ids[], kind: depth}` → LTX-2.3 with its IC-LoRA Union (`GetICLoRAParameters` + `LTXVAddGuide`, D76) and the start frame
made by the clay method; result = an Animate clip with `lineage_kind = stage-shot`. The pose guide is offered as a weaker second
(E11: 3/5). The shot keeps its stage id, camera and frame range, which is what Story L3 (14, Shots & Takes) links to later.

## 9. Workflows
1. **Block and render:** Library → drag *room*, drag two mannequins → Outliner names them → Poses: *point* and *arms crossed* →
   Cameras: 35 mm, Look through, frame → **Render passes** → Shot: clay method, prompt, `@heroine` → Generate (12 s) → the result
   in the Dock / Catalogue → Keep.
2. **Exact pose:** the same blocking, method *Exact pose*, the heroine's reference in slot 2 → 74 s → compare both in the loupe.
3. **Reverse angle:** Cameras → Duplicate → move to the other side (the set stays) → Render passes → Generate: the same characters
   from the other side, lineage back to the same stage.
4. **A moving shot (ST4):** keyframe the camera at frames 0 and 120 (dolly in), *walk* → *stand* on the figure → Render sequence →
   Generate clip (≈ 150 s) → Animate's player → Extract frame.
5. **Props from a photo (P18):** Catalogue card → *Make a prop* → Pixal3D (≈ 4 min, Dock) → the mesh appears in Props → drag in.

## 10. States
- No stage yet: an empty viewport with three cards (New stage · Open stage · Start from a Catalogue image as a plane).
- Weights missing for the chosen method (RefControl LoRA; the IC-LoRA): inline *Fetch* (07 §5).
- Passes stale / never rendered (Shot tab line, see §7). Scene too heavy (> 2 M triangles or > 20 planes): a Banner, the render
  continues at Draft size.
- Reopen conflict: the stage file changed on disk (`revision` 409) → "Reload" / "Keep mine as a copy" (`askConfirm`).
- WebGL2 lost (context loss): the viewport rebuilds from the store and says so in a toast; nothing is lost because the scene lives
  in the store and the file, never in the renderer.

## 11. Keyboard
All are registry commands with mouse homes (D32) and remappable (D72); unmodified Arrows, Esc, Space and Tab are fixed.
`Ctrl+6` Stage suite · `G` / `R` / `S` move / rotate / scale · `W` select · `Q` snap · `F` frame selection · `Ctrl+0` frame all ·
`C` look through the active camera · `Shift+C` camera here · `Ctrl+D` duplicate · `M` mirror pose · `H` / `Alt+H` hide / show all ·
`L` lock · `Del` ×2 delete · `Ctrl+Enter` generate · `Shift+P` render passes · `1`–`5` pass preview (clay, depth, normal, pose, masks) ·
`0` beauty view · `Ctrl+Z` / `Ctrl+Shift+Z` undo / redo.

## 12. Data and API
- **`stages/<id>.json`** (fsio, `schema_version`, `revision`): `{id, name, created_at, updated_at, size: {w, h, fps}, objects:
  [{id, kind: mannequin | set | prop | plane | mesh, name, asset_id?, transform {pos, rot, scale}, parent?, locked, visible, colour_id,
  pose?: {preset?, joints: {name: [x, y, z]}}}], cameras: [{id, name, pos, target, roll, focal_mm, sensor_mm}], active_camera,
  keyframes: {camera: {id: [{frame, pos, target, focal_mm, ease}]}, objects: {id: [{frame, transform, pose?, ease}]}}, range: {start,
  end}, passes: [{camera_id, revision, frame?, assets: {clay, depth, normal, pose, mask}, keypoints}]}`. Assets by id, never embedded.
- **Routes** (`routes/stages.py`): `GET /stages`, `POST /stages`, `GET /stages/{id}`, `PUT /stages/{id}` (409 on revision),
  `DELETE /stages/{id}`, `POST /stages/{id}/passes` (multipart: the pass PNGs + keypoints JSON → assets), `GET /stages/{id}/thumb`.
- **Jobs:** `POST /jobs` with `StageShot` (§7) and `I2V` + `guide` (§8), `origin {suite: stage, …}`; WS `job.progress` as today.
- **Lineage kinds:** `stage-pass`, `stage-shot`. **Specs:** `klein-9b` / `klein-base-9b` gain a `stage` recipe entry; the RefControl
  LoRA and the IC-LoRA are roster entries (already fetched by the spikes). **Settings:** none new; the project format (D18) decides
  size and fps.
- **Frontend:** `suites/stage/` — `engine/` (three: scene, cameras, passes, gizmos, undo), `bus.ts` → `bridge.ts` → `stageStore.ts`
  (zustand; project data never in component state), `StageSuite.tsx` (Panel / Strip / Stage / Inspector / PrimaryAction),
  `stageCommands.ts`; registered with `lazySuite` and `keepAlive`. Pure parts (keypoint projection, depth normalisation, the
  mannequin's joint tree, the stage file's migration) are modules with Vitest tests.

## 13. Acceptance checklist (`scripts/st_acceptance.py`, rig)
*ST1 built 2026-10-13 (D81; journal of that day): the suite tab (Ctrl+6), Library · Outliner · Cameras, the viewport with the gizmo
bar, raycast placement and image planes by drop, cameras in mm with the letterboxed camera view and guides, `stages/<id>.json` with
revision saves, undo / redo; the smoke scenario covers create → add → outliner → save → reload. Passes are ST3.*
*ST2 built 2026-10-13: joint pickers (FK), hand / foot handles (two-bone IK), Mirror / Reset / Save pose…, the project pose library;
the smoke scenario drives the mouse onto a joint and drags a hand, mirrors twice (an involution) and saves a pose.*
- [ ] Create a stage, place two mannequins and a set plane, pose with presets (ST1) and IK (ST2), frame a 35 mm camera, export
      the five passes at Draft size; the keypoints JSON matches the pose pass (vitest on projection).
- [ ] Generate with the clay method: the blocking is kept (the author's blind check ≥ 8/10 on a 10-shot set, as E10); with
      *Exact pose*: PCK@0.1 ≥ 0.8 on the result (SDPose, evaluation only).
- [ ] Kill the app mid-job → relaunch resumes paused (the queue's existing durability).
- [ ] Reopen the stage: identical (objects, poses, cameras, keyframes); a concurrent save gives 409 and the dialog.
- [ ] One ST4 shot renders a clip whose camera move follows the keyframes (PCK on sampled frames as E11).
- [ ] Suite switch away and back under D69 keeps the view; release and re-entry ≤ 300 ms; WebGL2 context loss recovers.

## 14. Open questions — decided by the author 2026-10-13 (D81)
- Sensor convention: **36 mm full-frame** (the photographic default storyboard artists expect; ArtCraft's 24 mm vertical rejected).
- The mask pass **ships in ST3** (no E10 method uses it yet; region prompting can take it later).
- The *Exact pose* method takes **the pose pass alone** (as E10 measured); the clay as a third reference is not added.
- Image planes in the clay pass render as **grey cards** (consistent with "image 1 is a grey clay blocking").
