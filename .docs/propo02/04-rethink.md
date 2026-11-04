<!-- markdownlint-disable MD013 MD024 -->
# 04 · The rethink: Clay as a layer of its own, the shot as a card that lists what it owns, the Bin by kind

Written 2026-11-03 after the author looked at the scene ([03](03-findings.md) §3). **Status: accepted as D181 the same day** — the author took every
recommendation in §6 as the answer ([05](05-answers.md)); §8 is the decision as recorded. C0, C1, C2, C2b and C2c were built on 2026-11-03, C5 (D184, the hybrid), C3 (Record: the animatic, the scene's length) and C4 (the ledger, the storyboard's play) on 2026-11-04 ([05](05-answers.md) keeps the status). The ArtCraft study is read again for it
([artcraft 04 §2](../artcraft/04-creative-surfaces.md), [26 §2](../proto01_animate/26-animate-modes.md)); its licence allows ideas, not files.

## 0. The author's four points

> 1. The prototyping part of World is ok for chars / props / places.
> 2. Clay seems to be all over the place. It was meant to be a 3D drafting place to create a more accurate animation, but it feels more like a chore than
>    something that helps putting together a complete and accurate scene. Eventually it either produces half-baked results, or a mixed bag of clay and
>    text-generated animation mashed together. It is also in World and in Shots as well, so it is very confusing as to where it should be used and how.
>    The idea was that a shot card created in Shots will contain a clay scene with everything in it animated to a certain max length — in essence a Shot
>    could produce a final (even post-processed) shot. All building blocks of a shot (the clay scene) should be generated in World, so generating these
>    should not happen here — only assignment of char / prop / place assets and generation of 3D assets for the clay scene. I would like a complete
>    rethink of how Clay / Shots should work; we should seriously look into ArtCraft's structure to recreate Clay in loom2. I would go as far as to move
>    Clay to a separate menu on the top rail.
> 3. The shot flow is a good start, but the UI contains a lot of useless information. It would be great if a shot had all the underlying things listed
>    under it in a diluted but informative way. This part needs a serious rethink.
> 4. The Bin needs to be way more detailed: all the different types of assets should be categorized — a depth map for a place creates a lot of
>    different images, character poses, etc. Everything that could be relevant should be added as a subcategory.

## 1. What the walk says about the four points

The record (`data/functions.jsonl`, 279 uses) sorted by where the clicks went:

| Where | Uses | Distinct controls | What came of it |
| --- | --- | --- | --- |
| World · the prototyping (Sheet, Make, Look, the bin, the roles) | 52 | 38 | three characters and a street with their pictures, in about 12 minutes of GPU |
| World · Build (the animation reference, the body, the set and its faces, the bench) | 45 | 36 | three fitted bodies, one set almost all Fill (P4, P5) |
| Shots · Clay (the outliner, the editors, the transport, the library, the blocks, the pose editor) | 119 | 74 | one figure walking a path, two figures standing, a camera move, a stop that was meant as a glance (P8, P21) |
| Shots · the header, the storyboard, Performance, Final | 45 | 29 | two finals; the extras lost (P19), the legs cut (P26), no shadows (P27) |
| Episode, the Bin, the frame | 18 | 13 | the movie |

**Point 1 holds.** World's prototyping took 52 uses, gave what it was asked for, and the findings against it are about breadth (P1, P2, P3), not structure.

**Point 2 holds, in numbers.** Clay and World's 3D building took **164 of 279 uses (59 %)** and 110 of the 167 distinct controls, for one walking figure
and two standing ones. The motion that came out is the clay's; the pictures are not: each figure was redrawn alone in a studio by Wan Animate from
its clay (the *Layered* method), the plate is the built set's five Fills, and the composition stacked the three. That is the "mixed bag": the clay decides
where things are, the model decides what they look like, and the seams (no shadows, the depth cut, the empty mattes) are where the two meet.

**Point 4 holds.** The Bin's tree ends at the version: `world/place/Cobbled street/v1` held **36 things in one grid** — the four candidates, the set
picture, the depth, the bakes (a face each), the coverage masks, the Fills (a face each, two passes), the cut-outs — told apart only by a kind chip
(*pictures · clips · audio · models*) and the role badges (register §9). The passes a shot renders (1449 pictures for shot 1: nine a frame) are files in
the final's folder and not in the Bin at all; a character's body, shell and poses are records, not things one can see there.

**Point 3 holds.** The storyboard card carries a thumbnail, a number, the name *Shot* (P12) and three dots; under it the header lists the scene, the camera,
the range, the cast and the words, and then the level's whole column: Clay's four sections, Performance's recipe template, three method cards, the finals'
rows with their matte strays and five verbs a take, Final's compositor. The things the shot *has* (its scene, its animatic, its takes, its final) are not
listed anywhere as a list.

## 2. Clay today: four doors, no home

| Door | What opens | Decided by |
| --- | --- | --- |
| World › a character or prop › Build › **Bench ▶**, **Line-up ▶** | Clay's whole column and viewport inside World, on a bench stage bound to the version | D142, D161 |
| World › Build › Body › **Skeleton…** | the skeleton bench: the reference beside the shell, its own panes | CS2 (D137) |
| World › a place › Build › **The set** | a 3D fit drawn on the set picture (walls' feet to drag, the kind, the sizes), the bake, the Fills, **Bench ▶** again | D143, CW6 |
| Shots › the rail's **Clay** | the shot's scene: the same column (Shot · Scene · Motion · Camera), the viewport, the timeline, the pose editor | D157 U4 |

Each door is right on its own terms (D142's reason: one engine, not a copy), and together they are the confusion the author names: the same panels appear
under two tabs, a bench stage is a stage with a `purpose` flag kept out of the pickers, the set is built in a 2D overlay in World but stood in 3D in
Shots, and the body is fitted in World but posed in Shots.

**What Clay produces** is also not one thing. Its foot is *Render the passes ▶* and *To Performance ▸*; what Performance then makes of the passes depends
on a method card: *Layered* (each figure alone, the plate apart), *Stage clip* (the whole frame from the passes), *Image to video* (a still, the motion
the model's). The clay itself — lit by its lights, casting shadows (`engine.ts:151`, the lights cast, the figures receive) — is never recorded as a
picture of its own: D180's rig recorded Departure's clay through its camera into a 4 s MP4 by script, and no button does it.

**The chore**, control by control (the register's §5 and [03](03-findings.md)):

| # | What the walk had to do | Why it is a chore |
| --- | --- | --- |
| P7 | type x·y·z for every figure | a figure lands on the centre ray; a gizmo cannot be aimed at a metre; nothing drops a thing *onto* the floor where the mouse is |
| P9 | aim floor clicks for a path, by calibration | a path is clicks, not points: no point to drag afterwards, no number, no snap to the kerb |
| P10 | move the playhead first, then Apply | a clip lands at the playhead, wherever it is |
| P11 | re-select the figure, remove the stray key | *Key object* keys whatever is selected, the set included |
| P8 | give up the glance | a pose key replaces the walk's pose instead of correcting it; only the last joint edited survives |
| P14 | pick Walk_Loop at ×1.5 and an idle | the library has walks and idles; nothing for "look back while walking", "hurry", "push a door" |
| P16 | accept 848×480 at 16 fps from the built set | the final's size, rate and plate are stated, not chosen |

## 3. ArtCraft's structure, read for Clay

ArtCraft's 3D stage is one page with two modes and almost nothing else on screen ([26 §2](../proto01_animate/26-animate-modes.md), the code's own
notes in `pagescene/AGENTS.md` §Build / §Record):

| ArtCraft | What it is | For loom2's Clay |
| --- | --- | --- |
| **the page** | one top-level tab, *3D Stage*; scenes are files with a cover image; the storyboard is another tab that refers to them | Clay on the top rail; a scene is the shot's file |
| **the library modal (+)** | Characters · Objects · Sets · Creatures · Animations · image planes · skyboxes; featured and the user's own; click to add or drag with a **raycast drop** onto the scene | Clay's **Library**: the 3D assets made *from* World's entities; a drop lands where the mouse points |
| **Build \| Record** | Build: the outliner, the gizmo bar, the selected object's panel, the camera pill, the PiP, the timeline bar; Record: everything hidden, the view locked to the render camera, **Capture** a still / **Record** the timeline | the same two modes; Record also writes the passes |
| **the outliner** | one row per object: icon, name, kind, look-through for a camera, lock, eye | kept (today's Scene section is this) |
| **one selected thing, one small panel** | the object's colour, transform, delete; pose mode entered from the selected character | the Inspector column, in place of the editor under the row |
| **the camera as an object** | a render camera is a scene object with a frustum; *camera view* looks through it with the framing overlay and the focal length; the viewport camera is separate | kept (SC1 made the camera a body); the pill and the overlay are the part not built |
| **the timeline bar** | collapsed to a scrubber until the scene has keys; expanded, **one track per object**: diamonds (a full transform each) or a **natural-language motion clip** spanning a range; a bezier easing popover | the tracks with blocks and a key layer of *corrections*; the text clip is a spike (§7, E60) |
| **the hand-off** | Capture / Record land in the library; the lightbox offers the next steps (*Edit on Canvas*, *Make Video*) | the shot card's rows offer the next steps (§4.4) |

What ArtCraft has nothing of, and loom2 keeps: the passes (depth, pose, masks), the layers and the composition, a body fitted to a character's
pictures, IK with contacts and pins, a set fitted from one picture, the motion library retargeted by contacts, every job local.

## 4. The proposal

### 4.1 The top rail: World · Clay · Shots · Episode · Bin

| Layer | Its question | Its unit | What it makes |
| --- | --- | --- | --- |
| **World** | what exists, in pictures? | an entity version | the sheet, the hero, the references, the A-pose pictures, the set picture, the Look |
| **Clay** | what is it in 3D, and how does a scene move? | a library asset; a scene | a figure, a prop model, a set, a light, an animation; a scene with its cameras and its animation; the animatic and the passes |
| **Shots** | what happens, shot by shot, and how far is each? | a shot card | the shot's scene (made in Clay), its takes, its final |
| **Episode** | how do the shots play together? | a cut | the movie, the Resolve folder |
| **Bin** | where is everything, and what kind of thing is it? | a home, and the kinds inside it | — |

The order is the order of the work, and the layers keep [02](../proto01_UI2/02-structure.md)'s rule: an order of refinement, not a wizard. A shot card
can be made before its cast has a body; its rows say what is owed and where.

### 4.2 What moves where

| Today | Proposed | Why |
| --- | --- | --- |
| World › Make's A-pose framings; Build › the candidates and the pick of the front, back and side | **World › Make**, unchanged: the A-pose is a picture with a role, picked by hand (D161) | a picture is World's |
| World › Build › **Body** (the fit, the sliders, the hands, the attachments, the shell, the skeleton bench, the turn test) | **Clay › Library › the figure** | the body is the 3D asset made from the pictures |
| World › Build › **3D model** (Pixal3D from the hero, the height) | **Clay › Library › the prop** | same |
| World › Build › **The set** (the fit, the kind, the sizes, the parts, the bake, the Fills and the faces' words, the things that move, Crowd, Walkers) | **Clay › Library › the set** | the set is the 3D asset made from the set picture |
| World › Build › **Bench ▶**, **Line-up ▶**; World's Clay mode | **Clay › Library**: an asset opened is the bench; several picked are the line-up | one door |
| World's readiness line *Ready for Clay* | **World:** *pictures done* (hero · references · A-pose front · back); **Clay's library row:** *body fitted · shell · back view · model · set built · filled* | each layer says what it owes |
| Shots › the rail's **Clay** level | **Clay**, opened from the shot card's scene row and back; the card's level dots keep *Clay* | the editor has one home, the shot keeps the ownership |
| Shots › **Performance**, **Final** | **Shots**, as the card's rows; their editors open from the rows (§4.4) | the shot's outputs are the shot's |
| bench and line-up stages (`purpose`), the stage pickers | gone: Clay › Scenes lists the shots' scenes only | nothing to keep out of a list |

The author's "generation of 3D assets for the clay scene" is the Library's first use: dragging Nora into a scene when she has no body yet offers
*Fit the body ▶* in place, from her A-pose front; a place with no set offers *Build ▶* from its set picture. The Library row exists for every World
entity as soon as the entity does.

### 4.3 Clay

```
┌ ☰ Project ▾ │ World · Clay · Shots · Episode · Bin ───────────────────────────────────────── engine · queue ┐
│rail │ Scene of 3 · The seal  ← Back to the shot        [ Build | Record ]       cam A · 35 mm ▾ ◉   16:9 ▾  │
│ ▦   ├──────────────────────────┬───────────────────────────────────────────────┬─────────────────────────────┤
│Libr.│ OUTLINER                 │ ┌ + · ✥ ⟳ ⤢ · ⌁ path · snap · ↶ ↷ ┐          │ INSPECTOR                   │
│ ◫   │ ▸ Pier (set)        🔒 👁 │ └──────────────────────────────────┘          │ the selected thing:         │
│Scen.│ ▸ Ines (figure)     👁   │                                               │  a figure: body · pose ▸ ·  │
│     │ ▸ Tomas (figure)    👁   │              the viewport                      │   position · facing · parent│
│     │   the letter (prop)      │                                               │  a camera: lens · height ·  │
│     │ ☀ low sun (light)        │        ┌ Pose Ines · Done ┐                   │   Set from view · Key       │
│     │ ▣ cam A (shot 3)  ◉      │        └──────────────────┘    ┌ PiP cam A ┐  │  a light: the light editor  │
│     │ ▣ cam B (shot 4)         │                                └───────────┘  │  a block: speed · loops ·   │
│     │ ＋ figure · prop · set · │                                               │   along the path · blend    │
│     │   light · camera · card  ├───────────────────────────────────────────────┤  a path point: x · z        │
│     │                          │ ⏮ ◀ ▶ ▶ ⏭  0048 / 0120 · 5.0 s   ▭ shot 3: 0–96 │                             │
│     │                          │ cam A   ◆──────────────◆                      │                             │
│     │                          │ Ines    [ Walk_Loop · along her path ──────][Idle]  ◆ (head turn, a correction) │
│     │                          │ Tomas   [ Idle_Lantern ───────────────────────── ]                            │
│     │ foot: Record ▶ · ≈ 10 s  │ Lines   ▮ Ines "Do you know…" 4.1 s ▮            Library ▸                   │
└─────┴──────────────────────────┴───────────────────────────────────────────────┴─────────────────────────────┘
```

**The rail: Library · Scenes.**

- **Library** is the grid of the project's 3D assets by kind: *Figures · Props · Sets · Lights · Cameras · Animations*, each bound to a World entity and
  version where it has one, with its readiness on the tile (*body fitted ✓ · shell ○ · back view ○*). A tile opened is the asset's page: its builder
  (today's Build › Body, Build › 3D model, Build › The set, moved whole) beside its own viewer — the bench, with the asset alone on a floor, a 1.75 m
  figure for scale, the turn test. Several tiles picked and *Line up* is the line-up. *Animations* holds the CC0 files, the local folder and *Mine*
  (the templates), searched as clips (F36). Lights and cameras hold the templates (Q10's presets, D157).
- **The animation workshop (D182, the author after C2: "edit animations — not just use the downloaded ones — and create a library of my own").**
  An animation is an asset of the author's. *Animations* shows every one as a tile — the author's library, the project's, the files' clips —
  with a thumbnail and its length; a tile opens it on the **animation bench**: a figure on the floor playing it as its one block, with the
  editor's chrome (C1) and the tracks (C2). Editing is what the tracks already do: corrections and keys over the block, its trims, speed,
  loops, mirror and blends, a second clip dropped after it (a splice, blended in), the range cut; *Save* writes it back over the animation
  (its revision), *Save as…* a new one. *New animation…* starts from a figure standing still over N frames. A downloaded clip is edited
  through *Make it mine* — a copy on the mannequin rig, its source file and licence kept on the record (D17). E60's text-to-motion, if it
  holds, is one more way in. No curve editor: a correction a frame is the grain; curves are a later item if the author wants them.
- **Shells only, the skeleton placed by hand (D183, the author after C2b: "there should be only a shell for a character in clay"; "a bench where
  the animation points could be allocated across the shell manually").** A scene holds characters, as their shells: the figure ＋ lists the
  Library's figures and no adult or child preset; fitting a body queues its shell by itself, and until it lands the figure is a ghost (the
  mannequin in x-ray) that everything works on. The dummy is the animation bench's, for an animation that is nobody's — *Try it on ‹character›*
  puts a shell on it. The skeleton bench's 3D pane takes a drag on any joint of the tree, written as an offset from the fitted body
  (`body.joint_offsets`), the bind redone from the placed joints: a lizard's hips, a stooped back, a heavy build are a few drags after the fit.
- **Scenes** lists the scenes, each with the shots it serves and its length; *New scene* (empty, at a World place, a copy of another), *Duplicate*.

**Build mode** is the editor, with ArtCraft's four rules (26 §2): the mode owns the chrome; the viewport carries the tools; one selected thing, one
editor — the Inspector; the outliner is a list, not a page of controls. The outliner's editors under the rows (SC1) move to the Inspector. A camera's
row has the look-through ◉; the pill at the top says which camera the view is and its lens; the PiP shows the shot's camera while the free view is used.

**The chore, fixed:**

| # | Today | In Clay |
| --- | --- | --- |
| P7 | a figure lands on the centre ray | **drop by raycast:** a library tile dragged onto the viewport lands where the mouse points on the floor, facing the camera; ＋ in the outliner lands in the shot camera's frame on the floor (F35); *Stand here* on the floor's right-click moves the selection there; the numbers stay in the Inspector |
| P9 | a path is floor clicks | **a path is an object:** its points are handles on the floor, dragged or typed in the Inspector, snapped to the set's floor parts (the pavement, the kerb) and to the figure's feet; the clip along it re-flows when a point moves |
| P10 | a clip lands at the playhead | **a clip lands where it is dropped** on the track; *Apply* lands at the shot's start; the playhead is for looking |
| P11 | *Key object* keys whatever is selected | a key is set **on a track row** (its ◆ at the playhead, as ArtCraft's row-end diamond); the viewport's selection follows the row and the row the selection |
| P8 | a pose key is the whole pose | **a key on a block is a correction:** the pose editor stores the joints changed, on top of the block's pose at that frame, blended over the key's handles — the spec's rule ([04 §3.2](../proto01_UI2/04-ui-shots.md)), not built; all joints edited survive |
| P14 | walks and idles | *Mine* grows by **Save as animation…** from any block or key range (06 §2.4, not built); the story motions are the E60 spike (§7) |
| — | the path tool, snap, the toolbar | kept; **the gizmo bar** sits on the viewport, not the strip |

**Record mode** hides the chrome, locks the view to the shot's camera over the shot's range, and offers three things:

- **Record ▶ — the animatic:** the clay through the camera, lit by the scene's lights with their shadows, at the project's draft size, frame-stepped to a
  clip. It lands as the shot's *animatic* row and in the Bin under the shot. It costs seconds on the CPU, no GPU, and it is the storyboard's own
  deliverable: the cut can be assembled from animatics before any model runs (Q6).
- **Capture — a still** through the camera at the playhead (today's *From a stage* still, Performance's start still).
- **The passes** (depth, pose, masks, per figure and for the whole frame) — today's *Render the passes ▶*, run when a performance asks for them.

**The scene's length.** A scene has a length, set when it is made (a default from the project, Q4), and the shot's range lies inside it; a block longer
than the scene is shown past the end and the length never grows by itself (F37). Several shots on one scene (coverage) are D157's Q2: *New shot from
this scene* in Shots, which is the one case where a scene is shared.

### 4.4 Shots: the card, and what it lists

The storyboard strip becomes the layer's main view, and a card opened is the shot's page: the **ledger** of what the shot owns, one row a thing, each
row *name · state · one fact · one verb*. Nothing else is in the left column. The Flow's graph is behind a toggle (Q9).

```
3 · The seal ▾                                                           v1 ▾ · 4.0 s · Clay ● Perf ● Final ○
  description   Ines asks the ferryman; he answers without looking up.
  lines         Ines "Do you know…" 4.1 s ✓ 🎙 · Tomas "A heron. I…" 6.1 s ✓ 🎙              ＋ line
  scene         Pier (shared with 4 · Departure) · cam A · 0–96 at 24 fps                     Open in Clay ▸
  cast          Ines ✓ · Tomas ✓ · the letter ✓                                               (a member owed: *Tomas · no body* ▸ Clay)
  animatic      ▶ 96 frames · recorded 10:32 · current                                        Record again ▸
  performance   one pass · take 2 ✓ · identity Ines 0.52 Tomas 0.61 · the Look's words        Perform ▶ · takes ▸ · method ▾
  final         rendered 10:41 · 848×480 · not marked                                         Render ▶ · Mark final ✓ · open the composition ▸
```

| Row | State · fact | Verb | What it hides |
| --- | --- | --- | --- |
| **description, lines** | as today's header | ＋ line, 🎙 | the lines editor opens on the row |
| **scene** | the scene's name, who else uses it, the camera, the range | *Open in Clay ▸* (the deep link; Clay's *← Back* returns) | Clay |
| **cast** | each member ✓ or what it owes, with the link to Clay's Library or World | — | the cast is read from the scene |
| **animatic** | frames, recorded when, *current* or *stale since the scene changed* | *Record again ▸*; ▶ plays it in the centre | nothing: it is a clip |
| **performance** | the method, the take in use, the identity scores, *N owed* | *Perform ▶* (the owed work with its minutes), *takes ▸* (the takes with Re-take, Variations, the windows view), *method ▾* | the recipe template, the method cards, the matte strays, the five verbs a take, *Show the words* (the hover) |
| **final** | rendered when, the size, marked or not | *Render ▶*, *Mark final ✓*, *open the composition ▸* (the compositor in the centre) | the compositor's layers, blends, mattes, the render settings (P16's size and rate become a field here) |

The centre shows what the selected row is about: the animatic or the clay through the camera, the takes' player with the wipe, the composition. The
level dots on the card stay (Clay · Performance · Final) and are the rows' states.

**The storyboard plays.** The strip, played, shows each card's current picture — the final where there is one, else the performance, else the
animatic — for the shot's length, in order: ArtCraft's filmstrip, on loom2's records. That is the animatic cut before Episode has anything.

**Fixes carried:** a shot is named at *New shot* (P12); a shot's scene is made once with the shot and binding a place reuses it (P13); the Shots tab
reopens where it was left (P17); the rows read the open shot's records only (P23); the storyboard's order *is* the route — ＋ New shot links the node
after the selection, so *Assemble from the Flow* has a route and the cut needs no *New cut…* first (P24, P25).

### 4.5 Performance: what the rethink changes, and what it asks

The author's verdict is on the *Layered* method's result: cut-outs on a filled plate. The rethink can put the methods behind one row, but which is the
default is a pipeline question the walk cannot answer, because only one method ran. The scene is the test case for it:

**E59 · the same shot three ways** (alone on the GPU, rule 10): shot 1 of this scene (a) as made, *Layered*; (b) *one pass*: the whole frame redrawn
from the clay's passes (depth and the pose guides, the Look's words, the start still from the lit clay); (c) *from the animatic*: the lit clay's first
frame redrawn as a still, then image-to-video with the camera move (D156's Fun-Camera). Judged on the author's four complaints: the passers-by visible,
the legs whole, shadows, the look; and on identity (FaceSim) and the minutes. The recommendation after it: the default for a street with extras is
whichever keeps the extras and the shadows; *Layered* stays the method for a shot where a character's identity must be exact.

Until then the performance row's defaults are a **field**, not a statement (P16): the size (the project's draft or FHD, D18), the rate, the plate's
source.

### 4.6 The records

| Record | Today | Proposed |
| --- | --- | --- |
| the scene | a stage, `stages/<id>.json`, with `purpose` for benches, a range for all cameras | **a scene is the shot's** (`shots/<nn>/scene.json`, or shared by reference for coverage); it has a `length`; no `purpose`, no bench stages |
| the library asset | the body on the Cast version (`CastBody`), the model on the prop, the set on the place, each under `story/profiles` | **a library record per asset** (`clay/<kind>/<id>.json`) bound to the entity version; the body, the model and the set move there with their files; World keeps the pictures and the roles |
| the animatic | — | a clip under the shot's home (`shots/<nn>/<version>/animatic`), stamped with the scene's revision, so the row can say *stale* |
| the shot card | the Flow node + the Story shot (RC2a) | unchanged; the rows read the node, the scene, the finals and the clips |
| the clip blocks | baked keys (06 §2.4's gap) | the blocks and the key layer of corrections, as 06 §2.4 specified |

### 4.7 The Bin: a home's things by kind

Today a home is one grid, and a thing is told apart by its asset kind (image · video · audio · mesh), its role (hero, reference, A-pose, set picture,
model, final, frame, clip, sample) and a free-text `lineage_kind` the job stamps (`stage-pass`, `set-fill`, `set-bake`, `set-coverage`, `place-thing`,
`clean-plate`, `shell`, `render`, `final`, … twenty-one strings, `catalogue.py:55`). The tree stops at the version.

**Proposed: every home has a third level, its kinds**, read from the lineage kind and the role at write time — rebuildable from the files (rule 4),
nothing the author files by hand. Each kind is a node with a count; the grid shows one kind, or the home with its kinds as headed sections.

```
bin/
├── world/
│   ├── character/ Nora/ v1/
│   │     pictures/   hero ★ · references · candidates (by framing: portrait · waist-up · full body)
│   │     A-pose/     front ✓ · back ✓ · side · the candidates of each
│   │     body/       the fit (its picture with the keypoints) · the shell · the skeleton · the turn test (a clip)
│   │     poses/      her own poses, each with its still
│   │     voice/      the samples · the cloned voice · every line spoken (audio, by shot)
│   ├── prop/      The letter/ v1/      pictures/ · model/ (the mesh, its turntable)
│   ├── place/     Cobbled street/ v1/
│   │     pictures/   candidates · the set picture ★ · the cleaned picture · details
│   │     set/        depth (MoGe) · the fit · bakes (a face each) · coverage masks (a face each) · fills (a face each, every pass) · things (cut-outs · cards · models)
│   │     life/       crowd loops · walker loops (a face each)
│   ├── look/      a style/   samples
│   └── sketches/
├── clay/          library assets with no entity (stand-ins, imported meshes, the animations imported, Mine)
├── shots/     03 The seal/ v1/
│       animatic/   the recordings (each a clip, stamped with the scene revision)
│       stills/     the start still · captures · frames extracted
│       passes/     depth · pose (a figure each) · masks (a figure each) — **a sequence is one tile** with its count and a scrubber
│       takes/      the plate · Nora (take 1 · 2 · 3, each with its matte and its face pass) · the man · the woman · the shadows
│       composition/ the render master (one tile) · the proxy
│       final/      the final ✓, marked or not
├── episode/   a cut/     movies · exports (the Resolve folders)
├── imports/
└── trash/
```

**Rules:**

- **A sequence is one tile.** A pass, a master, a matte run are folders of frames; each is one thing in the Bin with its frame count, a scrubber on
  hover and *Open the frames ▸* for the loupe. The passes enter the Bin this way (they are not in it today).
- **The kinds are a closed vocabulary per class**, in the orchestrator (the `lineage_kind` strings become a `Literal` with the sub-category each maps to),
  so a new job kind must name its shelf before it can land. The settings audit's way (D60): every job kind reaches a kind.
- **A kind's verbs are its own,** on the right-click and in the Inspector: a fill → *Fill this face again ▶*; a take → *Re-take ▶ · Variations*; a pass →
  *Render the passes again*; a bake → *Bake again*; a pose → *Apply in Clay*; a voice line → *Voice again 🎙*. The Bin stays without verbs of making
  of its own (05 §2.3): each verb opens or queues where the thing belongs.
- **Counts on the tree** at every level, and the search names the kind in its results (*fills · 5 · Cobbled street v1*).
- **The drawer** (05 §2.3) offers the same tree, so a drag into Make, onto a stage or onto a track starts from the right shelf.

## 5. What goes

- World's Build tab as a 3D place: the body, the model and the set leave it; what stays of Build is the pick of the A-pose pictures, which folds into
  Make's bin (a role chip, D161's manual pick) — World becomes **Make | Edit**, as the author read it (point 1).
- The four doors of §2; *Bench ▶*, *Line-up ▶*, the bench stage and `purpose`.
- Clay's *Shot* section (the For chip, the stage picker) — the header is *Scene of 3 · The seal*.
- The editors under the outliner's rows; the Templates and Stand-ins kinds as separate rows (a template is a library asset; a stand-in is a figure with no
  entity).
- Performance's recipe template picker and the method cards on the page; Final's compositor as a level of its own (it opens from the final row).
- *New shot in a new scene* / *in the same scene* as the ＋ menu: ＋ *New shot* asks the name and the scene (new at a place · the shot before's) in one sheet.

## 6. Questions for the author

| # | Question | Recommendation |
| --- | --- | --- |
| Q1 | The top rail: **World · Clay · Shots · Episode · Bin**, in that order? | yes: the order of the work |
| Q2 | The A-pose pictures stay in World's Make (a framing, the pick by hand) and only the body fit moves to Clay's Library? Or does the whole animation-reference step move with the body? | the pictures in World, the fit in Clay: a picture is World's, a body is Clay's; the Library row says *no A-pose yet ▸ World* when the picture is missing |
| Q3 | **A scene is the shot's** (one each, the author's "shot card contains a clay scene"), with coverage as the one shared case (*New shot from this scene*, D157 Q2)? | yes; the shared case keeps D157's blocking-made-once |
| Q4 | **The scene's length:** a project default with a per-scene field; what default and what cap? | 5 s default (Wan's 81 frames at 16 fps is one batch), 20 s cap; the shot's range any part of it |
| Q5 | **Performance's default method** for a shot like this one: decide after E59, on this scene? | yes; the walk shows one method only |
| Q6 | **The animatic as a deliverable:** *Record ▶* writes the lit clay through the camera as the shot's first output, usable in the storyboard's play and in Episode's cut before any GPU minute? | yes; it is what a storyboard tool makes, and it costs seconds |
| Q7 | **Story motions:** a text-to-motion spike (E60: a local model that turns "walks on, looks back over her shoulder" into a clip on the mannequin, licences read against D17), or hand-made templates only? | the spike, two days; the templates come anyway with *Save as animation…* |
| Q8 | **The shot page:** the ledger as the left column, with the row's editor (the takes, the composition) taking the centre? Or the editors as sheets over the page? | the centre: the page stays one page, the frame's columns stay |
| Q9 | **The Flow:** the storyboard first, the graph behind a toggle, and the route made from the storyboard's order? | yes; the logic nodes stay in the graph |
| Q10 | **Build beside or in place:** this is a re-housing of parts that exist (`StageParts`, `WorldBuild`, the finals' rows); wave by wave in the shell the author runs? | in place, each wave ending usable; a flag only for Record and the ledger while they are new |
| Q11 | **Names:** *Clay* for the layer, *Library* for its 3D assets (the Bin stays the files)? | yes |
| Q12 | **The Bin's kinds:** a closed vocabulary per class, read from the lineage kinds (§4.7), or folders the author makes and files into? | the vocabulary: it is rebuildable from the files and a job cannot land outside it; tags stay for the author's own grouping |
| Q13 | **Working files** (the depth, the coverage masks, the fit's keypoints): their own kinds, shown always, or behind a *working files* toggle? | their own kinds, always: the author asked for everything relevant; a kind with a count costs one tree row, not a mixed grid |

## 7. The order, and what it costs

Rough, author + AI, each wave ending usable; the spikes alone on the GPU.

| Wave | What | ≈ |
| --- | --- | --- |
| **C0** | the Clay layer on the rail; the Library (the body, the model and the set builders moved whole; the bench as the asset's viewer; the line-up); World = Make \| Edit; the readiness split | 1½ weeks |
| **C1** | the scene editor's chrome: Build \| Record, the outliner as a list, the Inspector, the camera pill and the look-through, the PiP on the viewport; drop by raycast, *Stand here*, keys on rows (P7, P11) | 1½ weeks |
| **C2** | the timeline as tracks: blocks kept as blocks, the key layer as corrections (P8), the path as an object (P9), drop where dropped (P10), *Save as animation…* | 1½ weeks |
| **C3** | Record: the animatic (frame-stepped, lit, shadows), the still, the passes; the scene's length; the scene as the shot's record | 1 week |
| **C4** | the shot page's ledger and the storyboard's play; the rows' editors in the centre; the Flow behind the toggle with the route from the order; P12, P13, P17, P23–P25 | 1 week |
| **C6** | the Bin's kinds: the vocabulary in the orchestrator, the tree's third level with counts, sequences as one tile (the passes, the masters, the mattes), the kinds' verbs, the drawer | 1 week |
| **C2b** | the animation workshop (D182): the Animations tiles with thumbnails, the animation bench, Save over and Save as…, New animation…, Make it mine with the source and licence kept, Rename / Duplicate / Remove | 1 week |
| **C2c** | shells only (D183): the scene's figure ＋ lists characters, the shell queued by the fit, the ghost until it lands, *Make the shells (n)*; the bench's *Try it on ‹character›*; the skeleton placed on the shell by hand (`joint_offsets`, the bench's 3D drag, the bind redone); the e2e's figures as characters | 3 days |
| **E59** | the same shot three ways (§4.5) | 1 day on the rig |
| **E60** | text-to-motion on the mannequin (Q7) | 2 days |
| **C5** | Performance's default and fields after E59; the story motions after E60 | ½ week + |

About nine weeks with the spikes. C0, C4 and C6 can go first in any order; C1–C3 are one piece of work on the scene editor; C2b and C2c follow C2.

## 8. The decision, as it would be recorded

**D181 · Clay is a layer of its own on the top rail — the 3D library made from World's pictures, and the scene editor every shot opens; a shot is a
card that lists what it owns.** World = Make | Edit (the pictures and their roles); Clay = Library (figures, props, sets, lights, cameras, animations,
each bound to a World entity version, built on first use) and Scenes (Build | Record: the outliner, the Inspector, the viewport's chrome, the tracks with
blocks and correction keys, the path as an object; Record writes the animatic, a still, the passes); Shots = the storyboard of cards, each a ledger
(description, lines, scene, cast, animatic, performance, final) whose rows open their editors; the route from the storyboard's order. A scene is the
shot's, with a length; coverage shares one. The Bin's homes gain a third level, their kinds, a closed vocabulary per class read from the lineage kinds,
a sequence one tile. The performance's default follows E59; story motions follow E60. Supersedes D142 (the bench as Clay in
World), D161's Build tab as a 3D place, D157 U4's Clay as a Shots level, D121's stepper and 05 §2.1's tree ending at the version; keeps D110 / D111 (one 3D scene, split into layers as a
method), D141, D143, D163–D165, D96's staleness (the animatic's revision stamp is one more use of it).
