<!-- markdownlint-disable MD013 MD024 -->
# 01 · loom2, the application as the author wants it to work

Written 2026-11-10 at `79ebcfc` from the author's request ([00](00-README.md) §1) and the investigation in [02](02-evaluation.md); **amended the
same day to the author's answers** ([06](06-answers.md)) and adopted as **D197**. This is the description the plan ([03](03-plan.md)) builds toward.
Where a choice came from an answer, the question's number is given.

It does not replace the history: [proto01 03](../proto01/03-vision-scope-and-mvp.md) (the vision), [proto01_UI2 02](../proto01_UI2/02-structure.md)
(the layers, D157) and [propo02 04](../propo02/04-rethink.md) (Clay on the top rail, D181) stay the record of how loom2 got here. §11 says which of
their decisions this one supersedes.

## 1. What loom2 is

A **local AI studio for pre-producing short animated episodes**, from the first picture of a character to the cut. It runs on one Windows machine
with an AMD RX 9070 XT (16 GB, ROCm 7.2). There is no cloud step.

| Part | What it is |
| --- | --- |
| Shell | Tauri 2, one window (a second for the detachable loupe, D155) |
| UI | React 19 / TypeScript, mouse-first (D32): every action a command with a mouse placement, keys as accelerators |
| Orchestrator | Python 3.13 / FastAPI: the durable queue (one GPU job at a time, D97), atomic records with schema versions and lineage, the weights roster |
| Engine | a pinned ComfyUI (v0.39.0) run headless for inference only (D2, D15), and three sidecars: EffectCraft (the shot's compositor and its passes, D112–D114), FilmCraft (the cut, D126), the VST3 host (sound, D127) |
| Models | declared in `orchestrator/loom2/models/specs/*.toml` (D65): FLUX.2, Klein, Krea 2, Z-Image, Chroma, Qwen-Image-Edit for pictures; Wan 2.2 (I2V, Fun-Camera, Animate, S2V), LTX-2.3, MiniMax H3 for clips; Pixal3D for 3D; SAM 3, BiRefNet, MoGe-2, SDPose, SeedVR2, RIFE, Kokoro / Qwen3-TTS as tools |

**The idea in one line: pictures make the world, clay makes the motion, and the models only redraw what the clay decided.**

A character, a prop or a place is first a set of pictures. From those pictures it gets a 3D stand-in: a body, a shell and a skeleton for a character,
a model for a prop, a set for a place. A shot is a scene of those stand-ins, blocked, animated and recorded in 3D. The video models then redraw the
recorded clay into footage, the compositor finishes it, and the episode is cut from the finished shots. Because the motion is fixed in the clay
before any model runs, a shot can be processed again without re-deciding its blocking, and the same processing can be copied across shots to keep
an episode coherent.

## 2. The work in four steps

```
 1  World                    2  Clay                          3  Clay › Process · Final               4  Episode
    (one entity)                (one shot = one scene)           (one shot)                              (the cut)
    Make → Edit → Clay          Scene: Build ⇄ Record            Process: the footage (v2v / i2v)        cut · sound · colour · deliver
    pictures → its 3D           blocked, animated, animatic      Final: composite, passes, output        → the movie

                              Shots (the overview): the Flow, the storyboard, every shot's state — the episode's order
```

| Step | Where | The author's words (2026-11-10) | Its unit | Done when |
| --- | --- | --- | --- | --- |
| 1 | **World** | "prototyping in World — characters, props and places" | an entity version | its pictures are picked and its 3D is made |
| 2 | **Clay › Scene** | "the editing bench to assemble each shot in detail" | a shot, which is its scene | the scene is blocked and animated and its animatic recorded |
| 3 | **Clay › Process, Final** | "a shot has a Clay part and a postprocess part also (like in world — you have make and edit)" | the shot's footage and its composition | the final is rendered and marked |
| 4 | **Episode** | "only a video cutting and post-processing bench" | the cut | the movie is rendered or exported |
| — | **Shots** | "a high level overview and a full assembly bench for each episode" | the Flow | every shot on the route has a final |

A project is one episode (Q11). The order is the order of the work, not a wizard: any layer can be opened at any time, and each says what it still
needs and where that is made (proto01_UI2 02 §1, kept).

## 3. The frame

```
┌ ☰ Project ▾ │ World · Clay · Shots · Episode · Bin ──────────────────────────────────── engine · queue · disk ┐
│rail │ header (the entity or the shot; its modes)  │ centre (the bin, the bench, the viewport, the player)  │ Inspector │
│     │ the mode's column                           │                                                         │           │
│     │ foot: the next step ▶ with its true cost    │ timeline (Clay: the tracks · Episode: the cut)          │           │
└ dock: queue · bin drawer ───────────────────────────────────────────────────────────────────────────────────────────┘
```

The top rail keeps D181's order, **World · Clay · Shots · Episode · Bin** (Ctrl+1–5; Q1). The frame's rules stay: the left column is the layer's panel,
the header is fixed at its top, the foot is the next step with its cost, help hides behind a ? (rule 11), no native dialogs (rule 6).

**One home per thing.** An entity's 3D is edited where the entity is (World), a shot is edited where the shot is (Clay). There is no *Open in Clay ▸*
from World and no *Open in World ▸* from Clay. Shots and Episode link into Clay to *open* a shot, which is navigation, not a second home.

## 4. World — what exists

**The rail:** Characters · Props · Places │ Look · Sketches. **The header:** the entity ▾, the version ▾, the readiness line, and the **mode rail:
Make · Edit · Clay**. The centre is the version's bin (Make), the editor (Edit) or the bench (Clay); the Inspector is the selected thing.

### 4.1 Make and Edit — as built

Make is the sheet (the entity's words), the picture settings with the model cards (D160, D186), the framings including the reference framings
(A-pose front, back, side; D162, D169, D176, D177) and the bin with the roles (hero, reference, A-pose, set picture), picked by hand (D161). Make's
reference framing is the one way an A-pose is made: the buttons that made them at another frame go (02 PG22). Edit is the layered editor on the
selected picture. Neither changes beyond the generation rule (§9 G2).

**Sketches** keeps the free picture making, Expand (Q21), and gains **free image to video** — a mood test from any picture, the one place a clip may
start from a picture that is no shot's clay (Q8).

### 4.2 Clay — the entity's 3D (new third mode)

Everything about the entity in 3D, for the version in the header: today's Clay › Library page for that entity, moved whole, plus the character's
poses.

**A character:**

| Section | What it holds | Today |
| --- | --- | --- |
| **Figure** | the body fitted to the A-pose front: height, build, proportions, the fit's points, the silhouette | Clay › Library › figure › Figure (`CastBody`) |
| **Shell** | the 3D model of the A-pose — a run form: the model tile (Pixal3D is the one model today), the source picture, resolution, face count, seeds, the cost; kept on the version, so the shell queued by itself after a fit (D183) runs these; the shells made, one picked | *Make the shell ▶*, a button with no form |
| **Skeleton** | the rigging screen: the body's joints placed on the shell, the hands, the feet & legs, the Humanoid switch, the rig's pictures (hand, feet) made and picked | Clay › Library › figure › Skeleton (`RigPanel`, `SkeletonBench`; D187–D191, D196) |
| **Poses** | the character's own poses, posed on the bench with pins, saved with a still, listed, renamed, removed (Q5) | saved from a scene's pose editor (*Save for ‹character›*, AP1b), listed in the skeleton screen |
| **Test** | the turn test (a GPU job, with its form) | *Test in motion ▶* |

**A prop:** **Model** (a run form on the hero or a picked picture; *Import a mesh…*; the models made, one picked) and **Height**.

**A place:** **The set** — the box set fitted from the set picture (the kind, the floor and walls, the sizes, the parts; D143), the bake, the Fills
(each a run form with the model card and the prompt's lead shown), the things that move (picked with SAM 3; a model or a card, D180), and the
place's life: the **crowd** and the **walkers** (D173, D174), made once from the place's faces and reused by every shot there (Q15).

**The centre** is the bench: the entity alone on a floor in Clay's own engine (D142's bench stage, an internal record), a 1.75 m figure for scale,
the turn test playing; on Skeleton the skeleton screen's panes. **The line-up** (several entities of a class side by side at their sizes) is offered
from the class rail's right-click (Q20).

**The readiness line** joins what World and Clay's Library said apart: *pictures — hero · references · A-pose front · back* and *3D — fitted · shell
· skeleton* (a character), *model · height* (a prop), *set built · filled* (a place). An item owed is a link to its section.

## 5. Clay — the shot bench

Clay is where a shot is built, from its scene to its final. The author: "every setting to do with shot settings should move here instead of the
shot menu."

```
┌ ☰ │ World · Clay · Shots · Episode · Bin ─────────────────────────────────────────────────────────────────────────────┐
│ ●1 The street ─ ●2 The glance ─◇─ ○3 The door ─ ○4 Inside        ＋                      (the shot rail: the Flow's shots) │
│                                └─ ○3b She walks on                                                                        │
├─────┬──────────────────────────────┬────────────────────────────────────────────────────────────┬──────────────────────────┤
│Shot │ 2 · The glance ▾  v1 ▾  6.0 s │                                                            │ INSPECTOR                │
│     │ [ Scene | Process | Final ]   │                   the viewport (Scene)                      │ the selected thing       │
│Anim.│ Build | Record                │                   the player (Process) · the compositor     │                          │
│     │ outliner · the shot's settings├────────────────────────────────────────────────────────────┤                          │
│     │ foot: Record ▶ · Process ▸    │ tracks: cam ◆──◆ · Nora [Walk ─── ◆] · Lines ▮ "Wait…" ▮    │                          │
└─────┴──────────────────────────────┴────────────────────────────────────────────────────────────┴──────────────────────────┘
```

### 5.1 The shot rail

A thin rail across the top: **the Flow's shots as a simple graph** (Q4), in the route's order, a branch drawn as a fork. Each shot is a small node:
its number, its name and one state dot (scene · animatic · processed · final). The logic nodes (choices, conditions) are small unlabelled diamonds so
the forks read. A click opens that shot; the open one is marked; ＋ makes a new shot after the open one, with its scene (§5.3).

### 5.2 The rail: Shot · Animations

- **Shot** — the open shot: the header and its three modes (§5.4–§5.6).
- **Animations** — the animation workshop (D182): every animation the author has (theirs, the project's, the downloaded clips), opened on the
  animation bench, edited with the tracks, saved, *Make it mine* for a downloaded clip (Q5). A character's own *poses* are the character's, in
  World (§4.2).

Clay › Library's Figures, Props and Sets go to World; its Lights and Cameras were never assets of their own (they are added in a scene).

### 5.3 A shot is its scene

**One scene per shot, strictly** (Q2). Creating either creates the other (the author: "if someone creates a scene, that should automatically create
a shot, and also the other way around"):

- ＋ on the shot rail, *New shot* in Shots or in the Flow: one sheet asks the name and where the scene starts — empty · at a World place · a copy of
  another shot's scene — then makes the shot node, its scene and its camera together. *Another angle* is a new shot whose scene is a copy; a later
  edit of either does not reach the other.
- There is no "new scene" that is not a new shot, and Clay's scene picker goes: the shot rail is the picker. Deleting a shot deletes its scene (asked
  first), and the other way around.
- **The scene's length is the shot's** (Q2b): one timeline, no separate range. Every render — the animatic, the passes, the stills, Process, Final —
  reads the whole scene; trimming is the cut's, in Episode.
- **The length** is 5 s by default (the project's default) and **20 s at most** (Q3; D181 Q4, `sceneLength.ts:5`).
- **The size and the rate** are the project's format by default and the shot's fields, the same for every render of it.

### 5.4 Scene: Build | Record, and the shot's settings

Build and Record are today's Clay scene editor (C1–C3, D181–D184): the outliner, the viewport with its gizmo bar, the camera pill and the PiP, the
Inspector for the one selected thing, the tracks (blocks and corrections, the path as an object, keys on rows). **Record** writes the animatic (the lit
clay through the shot's camera), a still (*Capture*) and the passes (depth, pose, masks).

**What a scene holds** (Q22): the characters as their shells (D183), the World props, the place's set (its box set or a picture's relief), lights,
the camera, **blocks** (a box with its sizes as fields — the scene's own simple geometry), and **image planes** (a background from a picture). The
preset sets and the stand-in furniture go; a table is a World prop.

**The shot's settings move here from Shots' header**, so a shot is set up in one place:

| Setting | Today (Shots) | In Clay |
| --- | --- | --- |
| name, version ▾, *New version*, *Mark final* | Shots header | the shot header (versions hold the process and the final; the scene is one, with its undo — Q17) |
| description | Shots header | the shot header (a line under the name) |
| lines and their voices, *Extend to the lines* | Shots header, the lines editor | the **Lines** track, its editor (words, voice, speed, *Voice again*) in the Inspector (Q19) |
| camera | Shots header | the camera's row in the outliner |
| range | Shots header | gone — the scene is the shot (Q2b) |
| cast, with what each still owes | Shots header (read from the stage) | the outliner (a figure without a shell shows as a ghost, D183, with a link to World › Clay) |
| the size and the rate | fixed per path (1920×1080@24 for stages made from Shots; F16 for the final) | the shot's fields, the project's default (P16) |
| the words of the shot's pictures | Shots header (*Show the words*) | Process, where the models read them |
| the Still's settings (method, model, references, count) | Clay, kept only in the browser | Process's Still, kept on the shot |

### 5.5 Process — the shot's footage

"Processing should have animation generation part, but it should not allow creating animations without the clay foundation — so the models here
should be either v2v, or i2v."

**The rule (G4):** every clip a shot makes starts from the shot's clay. A v2v step reads the clay's animatic or passes (depth, pose, masks); an i2v
step starts from a still whose lineage goes back to this shot's clay (a *Capture*, redrawn and edited as needed). A picture from elsewhere is
refused as a start; free image to video lives in World › Sketches only (Q8).

Process is the generation, as an ordered list of steps; each step has its model tiles and every parameter shown (§9 G2), its state (owed · running ·
✓ · stale since the scene changed) and its output.

| Step | What exists today | Input |
| --- | --- | --- |
| **Source** | the animatic, the passes, a still captured from the clay (Record) | the scene |
| **Still** | the clay still redrawn (Klein, FLUX.2, … on the clay pass, with the references) | a captured still |
| **Generate** | *Layered* — the plate (projected, filled, set, or LTX on the depth), each character by Wan Animate on its pose in its window (D163), props, shadows; the hybrid (D184: exact figures layered over a generated plate) · *One pass* — the whole frame from the passes (LTX-2.3 IC-LoRA on depth or pose, with beats; or Wan Animate) · *From a still* — i2v from the redrawn still (Wan 2.2, Fun-Camera with the clay camera's move, LTX-2.3, H3) · ***Speaking*** and ***Extend***, marked experimental (Q12): the S2V talking close-up from a still and a line; a clip continued past its end, the extension reading no clay | the source, the still |

The centre is the player with the clay ⇄ AI wipe, and the Windows view (D165) for a layered character. The foot is *Perform the owed ▶* with its
minutes, then *Final ▸*.

### 5.6 Final — the composition

Final is today's Final level, moved whole (Q9): the EffectCraft composition of the shot's layers — depth order, blends, mattes, parents; the
**passes** (*Clean up* — Wan 2.2 low-noise v2v; *Creative* — LTX; *Face*, D164; *Lip-sync*), each with its run form; the **effects** (the 21 curated
tiles, every parameter behind its "more"); the **voice** (the lines laid, lip-sync per speaker); the **output** (the size, the rate — RIFE to 24 —,
the render settings) and *Render the finished shot ▶*, *Mark final ✓*. The centre is the compositor's viewer, the timeline its layer lanes and audio
rows. The final is the one thing Episode reads.

### 5.7 Copying a shot's processing

*Copy to other shots…* picks shots on the shot rail and asks, with two ticks, what to copy (Q6b): **Process** (the steps, their models and settings,
the words' structure) and/or **Final** (the passes, the effects, the voice's options, the output) — never the outputs. The copy is a snapshot (Q6):
changing the source later changes nothing else, a copy again updates, and the copy remembers its source. A layered process's characters are matched by
who they are (the same character in both shots) and by order for the rest; what cannot be matched is listed before the copy.

## 6. Shots — the overview

Shots answers "what happens, and how far is each shot?" and holds the episode's order. It has **no settings of a shot** (they are in Clay):

- **The Flow** — the story graph (canvas | list): shots, lines, choices, conditions, the route, the **sequences** (the Flow's groups of shots in one
  place and time, renamed from "scenes", with the words their shots share — Q10); *New shot* (with its scene); reordering; the variables.
- **The storyboard** — the route's cards in order, each with its current picture (the final, else the processed take, else the animatic) and its
  state dots; ▶ *Play the storyboard* (C4).
- **The card** — a read-only ledger of what the shot owns (description, lines, scene, cast, animatic, process, final), each row a state and one
  fact; a double-click or *Open in Clay ▸* opens the shot in Clay.

Gone from Shots: the levels Clay · Performance · Final, the shot header's editors, the recipe template select, the stage picker.

## 7. Episode — the cut

Today's cut editor on FilmCraft (D126, CE1–CE5) with the VST3 host's channel strips (D127): the route's finals in order, assembled from the Flow, the
cut tools, sound, colour, captions, delivery (Resolve, EDL, FCPXML, SRT, the movie). It reads each shot's final. The author will refine this layer
once everything before it is in order ("I'm happy to refine this part when we have everything in order up to this point"); proto02 only keeps it
working.

## 8. The Bin

As built (D159, C6): every creation in its home, the homes by kind (a closed vocabulary per class), a sequence of frames one tile, the kinds' verbs,
the drawer. The kinds follow the moves: a character's body, shell, skeleton and poses under its World home; a shot's animatic, passes, takes and
final under its shot home.

## 9. The rules

### 9.1 The author's guidelines (2026-11-10)

| # | Guideline | What it means in practice |
| --- | --- | --- |
| **G1** | **No hard-coded templates.** "There should be no templates in the tool which cannot be recreated by using the commands of the tools themselves." | A shipped preset is allowed only when it is plain data the UI can make, see and edit itself (a pose is joint angles the pose editor sets; a light is a light; a block is a box with sizes). A template that sets values no control can set, or runs a path no command reaches, goes. [05](05-inventory.md) §B lists every one. |
| **G2** | **Every generation exposes its parameters.** "This should also apply to using generations with baked in parameters … every generation should have their parameters exposed at least." | Every ▶ that queues a job has a run form, inline above it (Q13): the model tiles (one tile when one model can do it, so the model is still named), every parameter of the recipe with the default the worker runs (T8) and its measured reason as the ? help, the prompt's lead sentences as editable text, the count and the seeds, the cost; the settings kept on the thing they make (Q16). A parameter left out is listed with its reason in the exposure audit, as D60's audit does for Settings. [05](05-inventory.md) §A lists every job. |
| **G3** | **Templating and quick access are not a priority.** "The whole templating and quick access management part … should not be a priority at this moment — and perhaps investigated later, when the functionality exist properly for all transactions." | No new preset, template or quick-access work in proto02. The author's own saved presets keep working as they are (Q18); a later study takes them up. |
| **G4** | **A shot's clips start from its clay.** | §5.5: v2v from the animatic or the passes, i2v from a still descended from the clay; a free clip only in World › Sketches (Q8). |
| **G5** | **A scene and a shot are one.** | §5.3: one each, created and deleted together. |
| **G6** | **One home per thing.** | §3: no *Open in X* between two homes of the same thing. |

### 9.2 The house rules — unchanged

CLAUDE.md 1–11: 16 GB first and measured on the rig; ComfyUI for inference only; mouse-first; files are truth, indexes rebuildable; display ==
reality; no native dialogs; licences read against EU terms; small drafts by default; commits in the house style; one job on the GPU at a time;
help behind a ?.

## 10. The records

| Record | Today | proto02 |
| --- | --- | --- |
| an entity version | the Cast profile's version: its pictures by role, and on the same record the body, the shell, the skeleton's offsets, the poses, the prop's model, the place's set | **unchanged** — the 3D already lives on the version, so moving the UI back to World moves no file; the run forms' settings are added to it (Q16) |
| a scene | a stage (`stages/<id>.json`) with `purpose` (`stage`, `bench`, `lineup`, `animation`); a stage may have no shot, or several | a `stage`-purpose stage belongs to **exactly one** shot; benches stay internal records of World's and the workshop's benches |
| a shot | a Flow node holding its shot; each version names its stage, camera, stage revision, range, words, method and recipe runs | each version names its scene and its revision, and holds its **process** and **final** settings (the steps, their models and parameters) in place of `range`, `method` and the recipe template id; a copy records its source |
| the Flow's group | a scene group (`scn_*` in `story/flow/scenes.json`) with words of its own | a **sequence**, the same record renamed (Q10) |
| a final | the EffectCraft composition, its passes and render settings, per final | unchanged, opened as the shot's Final mode |

## 11. What this supersedes, and what it keeps

**Supersedes:** D181's Library kinds Figures / Props / Sets in Clay and World = Make | Edit (World becomes Make | Edit | Clay); D181's shot page as
the place a shot is set up (Shots becomes the overview, Clay the shot's home); **D157 Q2's and D181 Q3's coverage** (one scene per shot, strictly);
the shot's range inside its stage (RC2a; the scene is the shot); D157's Performance and Final as Shots levels (they become Clay's Process and Final);
the recipe templates of RC0 / D96 (each shot's process and final are its own, copied between shots by the author); D190's place of the skeleton
panel (it moves with the figure, unchanged inside); the stage's preset sets and stand-ins; the A-pose buttons of CA0 / D161 (Make's framing is the
one way, D177's frame).

**Keeps:** D110 / D111 (one 3D scene, split into layers as a method), D141 (poses by contacts and IK), D142's bench as Clay's engine opened for an
entity, D163–D165, D178 (stale only when what it reads changed), D182 (the workshop), D183 (shells only), D184 (the hybrid), D186 (the model card
where the picture is made), D187–D191 and D196 (the rig), D88's experiments (kept as such, Q12), every decision about models, licences and the
engine.
