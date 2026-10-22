# 25 · The Clay level's coherence — the author's notes of 2026-10-22 and the plan (D119)

Status: **proposed 2026-10-22; D119 recorded; SC1 and SC2 built, E30 run (→ D120) and SC3's first slice built the same day (journal 2026-10-22 15:16).** The author's four notes, what each meets in the app today, and the
plan: SC1 the scene outliner with the camera as an object, SC2 the preset panel behind the +, E30 → SC3 a set from an image.

## 1 · The notes (the author, 2026-10-22, after AE4)

1. "We need to make the stage assembly a bit more coherent. I create a stage in my own project, but I only have presets (like room and
   stage) — we should be able to create 3D scenes from images."
2. "I'm struggling to find out how to move the camera in the 3D scene — I found the selection section in the bottom of the menu, and
   nowhere to select it as an object on the 3D view main panel."
3. "We need to clean up the Animate menus on Clay — there should be the same structure for templates like what we have in Image (the +
   sign next to the item — although this also needs upgrading, as it only saves presets, and they are still piling up as icons under the
   corresponding item). Best: keep the + sign, which expands into a small panel when clicked on, containing all presets as small icons and
   all functions related to presets (save, edit, delete, create new icon image …)."
4. "We also need a comprehensive outliner, where every object can be selected and all their properties are easily accessed (like how we
   did it with the layers in Final)."

5. (The evening, after SC3's first slice.) "When selecting any object from the Bin, there should be a small icon on the top right corner
   (based on the original selection criteria) that will action the image selection. This top-right icon should only appear when the
   selection was initiated from the main panel and should correspond to the exact response as the origin of the action — when clicked on
   Sets: From an image…, the icon should correspond to *Add to the stage (a set from an image)*; when clicked on Image planes: Add image
   plane…, then *Add to the stage (image plane)*, etc. The right-clicks should remain also!"
6. "The rotate button on the 3D view is moving and not rotating the object."

## 2 · What each meets today

| Note | Today | The gap |
| --- | --- | --- |
| 1 · a set from an image | The Scene's Library adds a **set** as architecture only (`room`, `street`, `deck`, `empty`: boxes, D108), **props** from the Cast library (a 3D model made from an image by Pixal3D, P18) or the five block presets, an **image plane** (a Catalogue image standing in the scene, facing the camera), lights and mannequins. The plate of a final shot is a Klein still of the bare set projected along the camera path (PS5b). | No way to turn an image of a place into a set the camera can move in. MoGe (the scene-depth model Pixal3D already carries, MIT) can give an image its relief; Pixal3D can cut free-standing things out of it. Unmeasured: spike E30. |
| 2 · moving the camera | A camera is a row in the Camera section (add, rename, delete, *Look through*, *Set from view*, *To shot*) and in the Outliner's camera list; its position and target are two vectors in the **Selection** section at the bottom of the column, shown when nothing is selected; in the viewport the camera has no body, so it cannot be clicked or dragged. The way to place it is to move the free view and *Set from view*. | The camera is not an object: not in the view, not under the outliner's selection, its numbers far from its row. |
| 3 · the Clay menus and the + | The Library is four grids of text buttons (mannequins, sets, props, lights, the plane) with no icons and no user templates. In Image every preset is an icon tile under its field (D90 R3) and the field's **+** saves the current text as one more tile; the tiles row grows with every save. Panel presets are a list (Saved panels), Animate's presets a list, Edit's brushes a list, Stage's poses a list. | One mechanism for all of them: the + opens a panel with the tiles and the verbs; under the item only the + and the chosen one. The Clay library joins it with icons and the author's own templates. |
| 4 · the outliner | The Outliner lists the objects (swatch, kind, name, bound tag, hide, lock; double-click frames) and, under it, the cameras; the properties of the selected thing are in the Selection section at the bottom (transform, the kind's fields, parent, the verbs). | Everything in one list with the editor under the selected row, as the Final level's Layers (UX9 U1): the stage itself, the set, the cameras, the lights, the figures, the props, the planes. |

## 3 · The plan

| Step | What | Where | GPU | Days |
| --- | --- | --- | --- | --- |
| **SC1 · the scene outliner, the camera as an object** | One outliner in the Scene section with a row for everything — the stage (the root: the frame, the ambient, rename / delete), the set, each camera (★ the active one; focal, roll, position, target; Look through, Set from view, To shot, Key camera, rename, delete), each light (LightControls), figure (character, pose, path), prop / mesh (MeshProp), plane (faces camera), with the transform, the parent and the object verbs under the selected row (UX9 U1's pattern). The Selection section goes at the Clay level; the Camera section's verbs move to the rows (its head keeps *Add camera*). In the viewport every camera has a **body** (a small frustum with a handle at its position) that is picked and dragged like an object: dragging moves the camera and its target together; double-click looks through it. | `StageParts.tsx`, `engine.ts`, `stageStore.ts`, `stageCommands.ts`, `AnimateSuite.tsx` | no | 1 |
| **SC2 · the preset panel** | One component behind the **+** of any item: a small panel with the presets as icon tiles (frame/PresetIcons), the chosen one marked, and the verbs — *Save the current as a preset…*, *Rename…*, *Delete* (asks), *Set as default*, *Make its picture* (the swatch / sample job, D91), *Show the words*. Under the item only the + and the chosen one's tile stay. Used by Image's field presets and Saved panels, the styles, Animate's presets, Edit's brushes, Stage's poses, and the **Clay library**: sets, props, mannequins and lights as templates with icons, plus the author's own templates — an arrangement saved from the outliner (the set with its props and lights, D108's "sets are architecture" kept: a template is a recipe of objects, not a mesh). | `frame/PresetPanel.tsx` (new), `PresetIcons`, `fieldPresets`, `GenerateColumn`, `AnimateSuite`, `EditSuite`, `StageParts`, `preset_icons` | the picture jobs only | 1–2 |
| **E30 · a set from an image** (spike) | Two set images (a room, a street) through (a) **MoGe's relief**: the depth as a displaced grid textured by the image, the camera moving within a parallax budget; (c) **cut and relief**: SAM 3 cuts the free-standing things, Pixal3D makes each a model, MoGe's relief carries the rest. Measured: how far the camera moves before the relief tears (±10° / ±0.5 m at the Draft size), whether the passes the pipeline wants (depth, clay, mask) come out of it, and the plate: an image set projects *itself* along the camera path — the relief has the depth PS5b lacks. Time and VRAM. | `engine/spikes/e30_set_from_image.py`, `frontend/src/spikes/e30Set.ts` | yes | 1 — **ran 2026-10-22, §3b** |
| **SC3 · a set from an image** (after E30's decision; the first slice built 2026-10-22, §3b) | *Set from an image…* in the Library (a Catalogue image or a Klein still of a place): the relief as a set object (its depth and clay passes from the relief, its plate the image), the cut-out things as props; the camera free within the budget E30 found (±0.25 m / ±5° / orbit ±10° for a Draft shot), the outliner saying when it leaves it. After E30 (D120): the lens shown and editable (MoGe's wobbles), the masked pixels (the sky) a backdrop at the far depth, the sheet for a smooth place and the cut where things stay (both from one MoGe run), the things' models scaled by the width of their front edge and stood on the fitted floor plane, the picture itself as the plate at every camera. | `stages.py`, `engine.ts`, `graphs.py`, `StageParts` | yes | 2 |

Order: SC1 (the usability the author hit first; no GPU), SC2, E30 → SC3. Each step: its tests, a commit, a rig or headed check, and a
check row here.

## 3b · Status

- **2026-10-22 15:16 — SC1 built.** The Scene's outliner lists the stage (its row: the frame, the contents, the ambient, Frame all / rename / delete),
  every object (its row: the transform, the kind's fields, the parent, the verbs — the Selection section's contents of before) and every
  camera (★ the active one; its row: position, target, focal, sensor, roll, Look through / Set from view / Key camera / To shot / rename /
  delete). Clicking a row opens its editor under it; again closes it. A camera's row selects the camera as an object and makes it the
  active one; in the free view every camera has a body (the glyph) that is clicked to select and dragged with the translate gizmo — its
  target follows by the same move — and double-clicked to look through; right-click gives the camera menu. The Selection section is gone
  at the Clay level (it stays for the clip levels); the Camera section keeps Add camera, the active camera at a glance (its name jumps
  to its row) and the shot's verbs. Checks below.

- **2026-10-22 15:36 — SC2 built.** `frame/PresetPanel.tsx`: one panel behind an item's + — beside the + only the tiles in use; the panel holds every
  tile (PresetIcons: glyphs or pictures), the words toggle, *Save the current as a preset…* (a name typed in place) and the host's verbs for
  the tile last clicked (a CommandRow of its commands). Hosts: Image's prompt fields (the World library's entries; save = add to the
  library; picture / edit in World / move / remove) and Saved panels (apply, rename, show in World, delete); Edit's brushes (save, delete
  yours); Animate's saved panels (save, apply, delete); the Clay level's poses (the built-in and the project's saved ones; Save this pose…,
  delete a saved one) and its **Library**: Figures, Sets and Stand-ins behind a + each, and **Templates** — the author's own: the stage's
  set, props, meshes, planes and lights saved under a name (`/project/stage-templates`, `stages/templates.json`), added to any stage by a
  click with new ids (a parent inside the template kept), deleted from the panel. Lights and image planes stay single buttons; Cast props
  and meshes keep their picture cards.

- **2026-10-22 17:51 — E30 run → D120.** `engine/spikes/e30_set_from_image.py` (the engine half) and `frontend/src/spikes/e30Set.ts` (Edge, WebGL): four
  set images frozen in `bench/sets/` (E22's room with its things, E28b's clean room, PS5b's bare room, a new Klein alley at night), each a
  MoGe relief two ways (cut at depth jumps / one sheet), the room also as D109's pipeline (the clean room's relief + E28c's models at the
  footprints the point map gives E28b's masks) and as the picture cut without a clean plate; 28 camera moves each, the holes inside the
  picture and the smear counted apart from the picture's own edge; sheets `engine/spikes/out/e30/sheet_*.jpg` (beauty · clay · depth).
  Found: MoGe is quick (under a second an image, 1.4 GB) and its relief **does not tear inside an empty picture** for any move tried; the
  picture's edge is the limit (dolly in free, truck ±0.25 m 5 %, pan ±5° 10 %, orbit ±10° 3–6 %); things left in the picture tear
  behind themselves (2–7 %), cut out without a clean plate 14 %; on the clean plate with the things as models the room moves like an
  empty one (≤ 0.1 %). The lens MoGe recovers wobbles (75° from the PNG, 69° from its JPEG) — SC3 shows it and lets the author set it.

- **2026-10-22 18:23 — SC3 built, the first slice: a set from an image.** The Library's Sets row has *From an image…* (and the Bin's right-click
  on a picture *Add to the stage (a set from this image)*): the `image_to_set` job runs MoGe-2 on the engine (E30's graph, seconds), the
  relief lands in the Catalogue as a `mesh` asset (lineage `image-to-set` ← the picture, MoGe's depth render its thumbnail, the lens / floor
  / depth read back from its vertices) and on the stage as a locked **Picture set** standing on the stage floor, with a **Picture camera**
  — where the picture was taken, at the height of its floor, with the lens — made the active one. The set's row shows the lens, the
  camera, and whether the active camera is still **within the picture's budget** (E30: ±0.25 m / ±5°, or an orbit of ±10°) with a ? on
  what happens beyond; *Look through the picture's camera* is its verb. The viewport shows the relief unlit (the picture is the plate).
  Rig (`engine/spikes/sc3_rig.py`, the real engine through the app): bench/sets/room.jpg (1280×720) → the job done in 18 s with the engine's start inside it (22 s the first time), the relief 227,775 vertices / 449,624 faces, 10.4 MiB, lens 69.16° × 42.36°, the floor 0.938 m under the camera, median depth 4.67 m; on the stage the locked Picture set and the Picture camera at [0, 0.938, 0] looking down −Z at 26.1 mm, active; the asset of kind mesh with lineage image-to-set and its thumbnail; the engine stopped with the orchestrator (8188 free). Not in this slice (the next): the things cut out and stood
  on the clean plate as models (D109's path, measured in E30 — today they are made by hand: the mask job, the remove, *Make a 3D prop…*,
  the model placed), the masked pixels (the sky) as a backdrop, a lens field before the job, figures' shadows on the relief (it is unlit).

- **2026-10-22 19:03 — notes 5 and 6 answered.** The Bin has a **pick**: a panel button that wants a picture (*Add image plane…*, *From an image…*)
  starts one (`session.ui.pick`: the Bin verb it names, the command whose icon it carries, its label); while it lasts every tile that has
  that verb shows a small accent button top right with the command's icon — a click runs exactly that verb (the plane, the set) and ends
  the pick; the Bin's bar says *picking for: …* with a ✕ to stop; a double-click runs the pick's verb too; the right-click keeps every verb;
  a suite change drops the pick. The rotate tool: an object selected after a camera's body (translate whatever the tool, SC1) or after a
  joint (rotate, local) kept their gizmo mode — now the object takes the gizmo in the tool's mode every time.

- **2026-10-22 19:21 — the follow-ups to notes 5 and 6** ("the pick button works — add a cancel when a right click or the escape button is pressed";
  "camera still don't rotate"): Escape and a right-click end the pick (the right-click on a tile still opens every verb; the ✕ in the bar
  stays the mouse placement). The camera's body takes the **rotate** gizmo under Rotate (translate under Move and Scale): a turn is a new
  target at the old distance and the roll about it (`onCameraTurned` → `updateCamera {target, roll}`); the glyph shows the roll now.

## 4 · Checks for the author

| Check | Your note |
| --- | --- |
| SC1: is the camera's body in the view the right thing to grab? Dragging moves camera and target together — right, or should the target have its own handle? | |
| SC1: the editor under the row — is anything you need still far from the thing? | |
| SC2: the + panel — which verbs are missing? Should the chosen preset's tile stay beside the +, or the + alone? | |
| E30 / SC3: how far should the camera move in an image set before it is a different shot? E30 says the picture's edge is the limit (10 % of the frame at truck ±0.5 m or pan ±5°) — is 10 % the bar, or should the edge be filled (a Klein outpaint of the plate before the relief)? | |
| E30: `engine/spikes/out/e30/sheet_room_props.jpg` — the clean room with the things as models: do they sit where the picture had them? `sheet_room_cut.jpg` and `sheet_room_sheet.jpg` — the picture with its things left in: the holes behind them (cut) or the skirts (sheet) — which do you prefer when a thing is not worth a model? | |
| SC3: *From an image…* on one of your own pictures of a place (a Klein still or an import): does the relief read as the place in the viewport, and does the Picture camera frame it as the picture did? Move the camera a little — is the budget line's warning early enough, or too fussy? | |
| SC3: should the things in the picture be cut out and modelled automatically (one job: the cut, the clean plate, the models), or stay a choice per thing? | |
| E30: the lens — MoGe read 75° from the PNG and 69° from its JPEG. Should a set from an image ask you for the lens (the Klein recipe's camera when the picture is the app's own)? | |
