# 01 · The author's direction, evaluated

The author's request of 2026-10-28 ([00](00-README.md)) is read here point by point against three sources:

- the walkthrough of the same day, in which "The Last Ferry" was built from an empty project through every workspace. Its findings F1–F44 and the code
  review's FE, BE and RC findings are listed in [08](08-register.md);
- the code at `e8ce296`;
- the backend survey of [06](06-backend.md).

Each point ends with a verdict: **agree**, **agree, refined** (the direction holds, with a change to how), or **open** (a decision for the author, listed again
in [07](07-plan.md) §5).

## 1. A layer-by-layer refinement as the whole workflow

**The direction.** World (what exists) → Shots (what happens, one clay stage per shot, refined Clay → Performance → Final) → Episode (the cut).

**What the walkthrough showed.** Today's app is organised by tool: Image, Animate and the Catalogue, with Story laid over them as a spine (D90, D125).
Every making step is a trip out of Story and back, carried by the *For* chip:

- the chip is the joint where most of the day's defects sat. Image kept the last shot's look (F25). Animate kept the last shot's prompt *and its camera
  move*, so The seal was queued with Departure's zoom-out (F29, review FE#1). The chip outlives its shot (FE#12). *Back* returns to the wrong place
  (FE#10);
- the trip lands on a panel that may be collapsed (F26);
- a Shot node knows no characters, so every trip to Image started without Ines, and Cast counted her in one shot when she was in four (F24, F30).

**Verdict: agree.** A layer UI removes the For chip by construction: the author is always *inside* an entity or a shot, and the maker is that entity's or
that shot's own panel. Context becomes structure. This is the largest single gain of the proposal, and the reason a new shell is better than patching the
chip.

## 2. World holds characters, props and places; Story › World goes

**What World holds today** (06 §1.3):

| Part | Read by | Where it goes |
| --- | --- | --- |
| Logline, synopsis | nothing (display only) | **dropped**, or one free *Notes* field in the Project menu (open, [07](07-plan.md) §5 Q1) |
| Spine (beats) | *Make the Flow from the spine*, once | **dropped.** The Flow is the script; a beat is a shot's description (F10: the spine is linear anyway) |
| Styles | every image recipe (`style_id`, `style_text`) | **kept as the project's *Look***. See below |
| Variables | Flow play, Choice and Condition | **moved to Shots** (the Flow owns its logic) |
| Library presets (119 entries, 17 fields) | Image's preset popovers | **split**: subject and look words stay with World's Make; lighting, camera, lens and composition go to Clay as real lights and cameras ([03](03-ui-world.md) §3, §6) |
| Saved panels, shot templates | Image; Flow | saved panels stay with Make; shot templates become *stage templates* in Shots |

**The Look.** A style is not an entity, but it is the one thing every picture in the project shares. It cannot vanish with World's page. Two homes fit:

- (a) a fourth rail item under a divider (*Characters · Props · Places · Look*);
- (b) a *Look* section in the Project menu.

**Recommendation:** (a). A style is made the same way as an entity's picture (a sample image on the sample scene), so it belongs in the same Make panel.

**Verdict: agree, refined.** World's page goes. Its four live parts are re-homed, and nothing a recipe reads is lost.

## 3. Cast becomes the same as Image: a rail of three, a Make / Edit panel with the entity's header

**What the walkthrough showed.** The Cast page mixed the sheet with every output: coverage grids, candidates, the animation reference, the set, the
3D model and training. It also gave places and props a character's grid (F11, F12). The right panel repeated Image's verbs (*Use as a subject in Image*,
*Expand in Image…*) and sent the author to Image to make anything. The casting run rendered the whole Image panel, so a second subject left on it would
have been filed as the cast character's candidate (F16).

**The proposal.** The rail picks the class. The left column is Image's Make / Edit, with a header holding the entity:

- character: name, version, appearance, outfit, body;
- prop: name, version, appearance, 3D model;
- place: name, version, appearance, the set.

The centre is the entity's bin; the right is the selected creation.

**Verdict: agree, refined in four places:**

1. **Voice belongs in the character's header.** It is part of the identity, and Shots needs it for every line. Kokoro's ten voices and cloning from a WAV
   stay as today.
2. **Colours and marks** fold into appearance (marks as words; colours as swatches on the appearance field), so the header stays at the author's five
   fields.
3. **Readiness for Clay** is the header's last line. This is the layer's purpose in the author's words:
   - a character: hero, references, the A-pose front and back, the body fitted, the voice;
   - a prop: hero, the 3D model and its height;
   - a place: the set picture, the set built, the faces filled.

   Today it is a row of eight items, several of them misleading (FE#9: References ✓ with only the hero; F14: a bare readiness score).
4. **The Make panel is scoped and reduced.**
   - The entity is the subject, fixed, and is the only subject. No second card can be left behind (F16).
   - The *Give it a look* run, *Expand* coverage and the A-pose reference are its verbs.
   - Lighting, camera, lens, composition, pose and action are not on it (§5).

## 4. Every creation in a bin `bin/world/<type>/<name>/<version>`; no batch grouping

**What the walkthrough showed.** One picture could live in four overlapping places:

- Image's results (by batch);
- the Catalogue's *Unprocessed* (the voice lines and the swatch landed there);
- a version's album pages (*reference set*, *candidates*);
- the style's sample group.

Making the hero *moved* the picture between groups (F15). The batch header showed a raw JSON prompt (F23). Nothing told the author where a thing would
land.

**The proposal: one home per asset**, the owner's bin, and roles inside it:

- `bin/world/character/Ines/v1`: hero ★, references, A-pose front and back, candidates (the default);
- `bin/world/place/Town street/v1`: set picture, faces;
- `bin/world/prop/The letter/v1`: hero, 3D model;
- `bin/world/look`: style samples;
- `bin/world/sketches`: free pictures not yet anyone's.

Shots and Episode follow the same rule (`bin/shots/<shot>/<version>/…`, `bin/episode/<cut>/…`, `bin/imports`), so the Catalogue becomes the **Bin**: one
tree of every home.

**Batches.** A batch is still needed by the queue (cancel a run of four, its progress) and by lineage (which seeds belong together). It stops being a way
to *show* things. The grids sort by time within a bin, and the job's run is a detail in the Inspector.

**Verdict: agree.** 06 §1.2 lists what it touches: groups become bins with a path, an asset gets a home, and roles replace the reference-set and
candidates pages.

## 5. World is for ideas; light and pose belong to Clay

**Verdict: agree.** Two technical exceptions stay in World because Clay needs them:

- the A-pose of the animation reference;
- the eye-level, empty view of a place's set picture.

Both are fixed recipes, not choices, so they add no controls.

The consequence is also an improvement. The words a shot's pictures are made from (the plate, the start still, the stills) are composed from the shot
itself:

- the place's sheet and the Look;
- the Clay lights as words (*Window · Sun · Lamp*, their colour and direction);
- the time of day.

Today the plate of a preset set was "The room is empty… bare walls and floor", even on a street, with the shot's scene and the World style unread
(F38). [04](04-ui-shots.md) §6 defines this composition.

## 6. A shot is a clay stage; clicking a shot opens its arrangement

**Today.** A shot and a stage are separate records joined by a version's `stage_id` / `camera_id`. Stages also exist on their own, as bench stages, the
line-up and free stages. A shot can live with no stage at all, on the *Image to video* route.

**Verdict: agree, refined: one stage per *scene*, one camera per shot.** A conversation is a master and its coverage: the same set, the same blocking
and the same animation seen through two or three cameras. If every shot owned its own copy of the stage, the blocking would be copied and drift apart
between the master and the close-up.

- Today's records already allow the refinement: a stage has several cameras, a shot version points at one, and RC2c's scene groups gather shots.
- The rule becomes: **a shot is a camera on its scene's stage, over a time range of that stage.** A scene with one shot is the author's one-to-one case.
- *New shot from this scene* adds a camera and a shot, sharing the stage.
- Clicking a shot opens its stage, through its camera, at its range.

Open for the author: Q2 in [07](07-plan.md) §5 (one stage per shot, as asked, or one per scene).

## 7. One node, with or without voice

**Why there are two.** The Flow's node set came from the old loom's dialogue graph (loom R134, R146: Dialogue · Choice · Condition · Hub · Jump · Note,
an interactive-story editor). The Shot node was added later, for visual beats (D96). D125 gave both a shot.

**The only differences in data** (06 §2.1):

- Dialogue carries `lines[]` with speakers;
- Shot carries one `text` description.

The walkthrough paid for the split: converting a Shot to a Dialogue hid its description (F9), and Image then used the node's *title* as the lead text
(F9b).

**Verdict: agree.** One **Shot** node: a description, an optional list of lines (speaker, words, voice), and its stage. The logic nodes stay as logic:
Start, Choice, Condition, Action, Hub, Jump and Note. The two types already hold identical fields, so no data moves: old `dialogue` files are read as
shots, and the type filters become "a shot with lines" (06 §2.1).

## 8. Always a clay composition: no route around Clay

**What happened in the walkthrough.** Four of the five shots took the *Image to video* route, a FLUX frame animated by Wan, because it is the default
template (`shot_recipe.py`, F24's trip). That is why the test bypassed Clay. Only "Stay" went through a stage.

**Verdict: agree.** Clay-first gives every shot a camera, a blocking, a place and continuity, and the board stops being a matrix of five routes. It has
three costs, and the design must answer each:

1. **Every character needs a body, every place a set, every prop a model.** World's readiness line (§3) makes that the gate to Clay, not a surprise
   inside it. The walkthrough's automatic body fit failed on a reference that did not show the whole figure, and said so only in a toast.
2. **A simple shot must still be quick.**
   - *New shot* copies the previous shot's stage, or starts from a stage template: a set and a camera.
   - An insert (the letter on a table) is a prop on a set with one camera.
3. **The image-to-video models are not lost.** They become one *Performance* method fed by the clay: the start still from the stage, the camera's
   move from the clay camera's keys (D156's Fun-Camera moves where they match), and the action from the shot's description. The motion is still
   decided in Clay.

## 9. An animation editor per shot; segments saved as templates

**Today**, Clay has the pieces:

- the CC0 motion library with retargeting and foot lock;
- walk along a path;
- the pose editor with pins, contacts and gaze;
- keys by hand (Shift+K);
- skeleton keys;
- one timeline with a row per object.

**What the walkthrough found**:

- applying a 1.3 s walk baked 329 keys and stretched the stage's range from 120 to 328 frames without saying so (F37);
- the clip list is a two-row box whose search does not search clips (F36);
- a figure walking away was rendered facing the camera, and nothing warned (F42).

**Verdict: agree.** The animation editor is the centre of Clay:

- **a track per figure**, with **clip blocks** that can be moved, trimmed, looped and blended, not baked keys: library clips, templates and walks along
  a path;
- **a key layer** over them, for poses and corrections;
- the camera's track.

*Save as animation…* on a selected range of a figure's track stores a template. Templates appear in the motion library beside the CC0 clips and the local
folder. 06 §2.4 weighs the storage. The recommendation is the stage's own key format (JSON) on the shared mannequin rig, because it applies through
today's `applyMotion` and keeps what a GLB would lose: the Detailed figure's bones, the ground, the pins and the contacts. Open: whether templates are
the project's or the author's across projects (Q4).

## 10. Performance refines the clay; Final assembles the shot

**Today**, Performance holds three cards: *Image to video*, *Stage clip* and *Final shot*. The final shot's steps are split across both levels:

- making, the plate and performing the layers are in Performance;
- the composition and the render are in Final.

**What the walkthrough found:**

- the next-step foot acted on the oldest final of the stage (F41);
- the plate's black faces reached the final without a warning (F43);
- a figure's identity score was shown, but only as a clip's fact (Departure: FaceSim 0.31).

**Verdict: agree.**

- **Performance** is where the clay becomes footage *without new motion*:
  - the plate (from the built set, filled, or generated);
  - each character's take (Wan Animate on its pose);
  - each prop's render;
  - or the one-pass methods (stage clip; image to video from the start still).

  Each layer has its takes, a clay | AI comparison, an identity score and *Re-take*.
- **Final** is the shot assembled as it was arranged:
  - the layers in depth order, mattes and shadows;
  - the shot's voice lines on its own audio rows;
  - lip-sync as a pass per speaking character;
  - the effects and the render.

  Its output is the shot's final, the one thing Episode reads.

## 11. Episode cuts the finals

**Verdict: agree.** The FilmCraft-backed editor exists (D126, CE1–CE5). The changes come from the walkthrough:

- the cut reads each shot's **final** (not "a clip");
- a shot with lines is held for its lines, or the checklist says it isn't (F39);
- clips are named after their shots and point at the masters (F40);
- the Assemble sheet counts the route's shots (F33).

## 12. "Start from scratch"

**What is true.**

- The backend has nearly everything this workflow needs (06 lists the gaps: the scene ↔ stage ↔ shot binding, bins, animation tracks and templates,
  the shot's prompt composition, and Look as a project record).
- The current shell carries ten weeks of layered decisions (D90 → D95 → D121 → D125 → D136), each patching the last. The For chip, the five routes, the
  three overlapping maker tabs and the board's nine columns are the sediment.

**What would be wasteful.** Rewriting the heavy engines would cost months and buy nothing the author asked for:

- the Stage engine and its 3D viewport;
- the Edit canvas on WebGPU;
- the Generate column's recipe building;
- the FinalEditor;
- the FilmCraft cut editor.

[06](06-backend.md) §5 lists each component with a verdict.

**Verdict: agree, refined.** The new UI starts from scratch:

- a new shell;
- three layers and a Bin;
- new navigation;
- new panels written for the layer they serve.

It *mounts* the proven engines and stores inside those panels, after the couplings listed in 06 §5.3 are cut. It is built beside the old UI (a second
entry, `?ui=2`) on the same backend and the same project files. The old UI is deleted when the new one reaches parity. The author's projects keep
working throughout.

## 13. What the direction leaves out, and where it goes

| Function today | Home in the new UI |
| --- | --- |
| Free image generation (Image › Make with no entity) | World › Sketches (`bin/world/sketches`), the same Make panel without an entity header |
| The ideas store (D136, *Prototype ▸*, *Keep*) | folded in: an entity starts as a draft (no hero yet); *Prototype ▸* on a sketch makes a draft entity from it |
| Edit (the image editor) | the same Edit panel, opened on any still in World, Shots (a plate, a start still) or the Bin |
| LoRA training | World › a character's bin: *Train on the references ▶* |
| New angle, Upscale, Instruct, Inpaint and Refine | Edit's AI verbs (unchanged) |
| The Shots board | a list view of the Flow in Shots (route order, three level states per shot), not a separate workspace |
| Models & engine, Settings, Keyboard map | ☰, unchanged |
| The queue | the Dock, unchanged; the Bin moves from the Dock to its own top tab and a drawer |
| The line-up, the bench | World's verbs on entities (*See in clay ▶* opens a temporary stage), never in the Flow |
