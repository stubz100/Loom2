<!-- markdownlint-disable MD024 -->
# 07 · The plan, the risks, the decisions

## 1. How it is built

**Beside the old UI, on the same backend and the same project files.**

- The new shell is a second entry of the same frontend (`?ui=2`, and a ☰ item *Try the new UI*). It reads and writes the records the old UI does.
- When the new UI reaches parity it becomes the default, then the old shell is deleted. That is a D-number of its own.
- During the transition every backend change keeps the old UI working, or is adapted in the old UI in the same wave.

**One rule for every wave:**

- its offline tests and Vitest;
- its e2e scenarios, written for the new shell;
- screenshots of what it touches, sent to the author;
- a rig run where a model is involved (rule 1);
- a journal entry.

## 2. The waves

| Wave | What | Gaps (06 §6) | Size | Needs |
| --- | --- | --- | --- | --- |
| **U0 · Fix first** | The defects that hurt today, in today's UI. They are worth fixing whatever is decided: Clay in dev builds (F34), the final foot's final (F41), the loupe closing the app, ids as paths, the Run-stale seeds, the estimate with references (F27), Animate's For leak (F29), the board's stale cells (FE#3), In-cut vs Episode (FE#2) | G15 (part) | M | — |
| **U1 · Seams** | No visible change. The router (`place`, `navigate`), stores stop navigating; key hooks mounted by the shell; the records layer and the event fan-out; context instances for Make, the stage and the composition; the empty `?ui=2` shell (top bar, layer tabs, dock) | 06 §5.3 | L | U0 |
| **U2 · Records** | One Shot node type; `POST /story/flow/shots`; the scene owns its stage, a shot is a camera and a range, one camera per shot, the migration; the bin tree with homes and roles, the migration; the Look as a record | G5, G12, G6, G1, G2 | L | U1 |
| **U3 · World** | The rail, the header per class, Make scoped to the entity (the Generate column as a context instance), Edit, the bin grid with roles, the Inspector, the readiness line, Look, Sketches; the Library split; ideas folded into drafts | G3, G4 | L | U2 |
| **U4 · Shots: Flow and Clay** | The storyboard strip, the Flow view, the shot header (lines, scene, cast), Clay on the scene through the shot's camera, the pose editor, the words of a shot's pictures | G13 | L | U2 |
| **U5 · The animation editor** | Clip blocks on tracks, the key layer, the camera, prop and lines tracks; templates; *Import…* for motion files; the range never moves by itself; the facing-away warning | G8, G9 | L | U4 |
| **E42 · Facing away** (spike) | Why a figure walking away from the camera is performed facing it, even with a back-view reference (F42, F43). Wan Animate's inputs (the back reference, the pose guide's facing, the prompt) measured on the walkthrough's Stay | — | S | GPU, alone |
| **U6 · Performance and Final** | A final per shot version; layers and takes, clay ⇄ AI, FaceSim per take; the methods (one pass, from the start still, speaking close-up); Final's voice and lip-sync; the shot's final | G10, G11 | L | U4, E42 |
| **U7 · Episode** | Reads finals; backend assemble that keeps edits; lines held; clips named; conform on landing; the cut's capabilities | G14 | M | U6 |
| **U8 · The Bin and parity** | The Bin tab and drawer; the e2e for every layer; the click-through by the author; the new UI the default; then the old shell removed | — | M | U3–U7 |

**U0 is built** (2026-10-28 23:34 and 2026-10-29 00:26 in the journal): every item above, with tests; e2e 79/79.

**U1 is built** (2026-10-29 00:43): the router, the key hosts, the records' fan-out and the context slots; the empty `?ui=2` shell.

**U2 is built** (2026-10-29 01:04 – 02:08): one Shot node (G5); the scene's stage, a shot's camera and range, *New shot* (G6, G12); the Look's sample scene (G2); the Bin's homes, its migration and every creation landing home (G1). Deferred: old projects' shared cameras and stageless shots to U4, retiring Unprocessed to U8.

**U3 is built** (2026-10-29 02:30 – 03:33): World in the new shell — the rail, the entity header and its readiness, one bin with roles, the Inspector, Make scoped to the entity, Edit on a creation, Look, Sketches, the Look's words (G3, its World part) and the ideas brought in (G4). Owed, small: the header's voice field, *Import GLB…*, the Inspector's entity facts, *See in clay ▶*.

**U4a–c** (2026-10-29 04:45): Shots in the new shell — the storyboard strip with its level dots, the rail, the shot header (lines; the scene, camera and range menus; the cast with its gaps), the Flow (a node's double-click opens Clay, *New shot* on the canvas), Clay on the shot's stage through its camera; older projects brought into "a shot is a camera of its own on its scene's stage" (U2's deferred migration). **U4d** (2026-10-29 05:15): the words of a shot's pictures (G13) — `shot_prompt` from the shot's records, part by part with their sources, *Show the words* in the header, the plate told its place. **U4 is built.** Owed to U5: the lines-outlast-the-range warning (F39); to U6: the start still and the performances take the composer's words; rig owed: one plate with the new words.

**The order.** U0 can start at once. U1 and U2 are the foundation. After them, U3 and U4 can run in either order: World first follows the work's order;
Shots first answers the author's biggest change sooner. U5 and U6 follow U4. Most of U7 can run once U6 has the shot's final.

## 3. What is reused

([06](06-backend.md) §5.)

**Mounted as they are:**

- the Stage engine and its 3D viewport;
- the Edit canvas and its tools;
- the motion maths;
- the timeline and the player;
- the Final editor, its viewer and the composition;
- the FilmCraft cut editor;
- the Catalogue's store and grid;
- the entity editors;
- the Flow canvas;
- the command registry and the menus.

**Rewritten:**

- the shell (grid, top bar, rails, the router);
- the layers' panels and headers;
- the storyboard strip;
- the Bin's tree;
- the Performance level's layers.

**Split:** `storyStore`, `StoryParts` and `storyCommands`, into records and per-layer views.

## 4. Risks

| Risk | What it costs | What reduces it |
| --- | --- | --- |
| **Migrations on the author's projects** (bins, scenes and stages, one node type, ideas) | a project opened by the new code can't go back | every migration idempotent and run at open, after a `project.json`-level backup copy of the records (`story/`, `groups/`, `stages/`), as `migrate_rc2` did. A dry-run report first on copies of `stubz001–003` and the rig projects |
| **Clay-first slows simple shots** | a two-second insert needs a stage | *New shot* copies the previous scene or a stage template; an insert is a prop on a set; *From the start still* keeps the fast image-to-video models inside the pipeline |
| **The body fit fails on the A-pose** | Clay figures with the default body | the A-pose recipe frames the whole figure (the walkthrough's A-pose had the feet on the frame's edge, F32b); the fit's failure shows on the header, not in a toast |
| **Two UIs on one backend** | double maintenance for a while | the old UI frozen to fixes; backend changes keep it working; parity measured by the e2e |
| **The e2e rewrite** | 49 of 79 scenarios use today's layout | scenarios written per layer as it lands (U3–U7), the old ones deleted with the old shell |
| **GPU time of the walkthrough-style checks** (rule 10) | headed WebGL / WebGPU checks during jobs | the screenshots on the e2e build with the fake engine; rig runs alone |

## 5. Decisions for the author

**Answered 2026-10-28 → D157** ([09](09-answers.md)): every recommendation was taken, with three changes. The synopsis is kept as a note and the logline
dropped (Q1). Expand and LoRA training are taken out altogether (Q6). Clay's light templates get a full editor (Q10).

| # | Question | Recommendation |
| --- | --- | --- |
| Q1 | Logline and synopsis: dropped, or kept as one *Notes* field in the Project menu? | a Notes field (nothing reads it, but the pitch is worth keeping) |
| Q2 | **One stage per shot (as asked), or one per scene with a camera per shot?** | **per scene**, one shot per scene by default: coverage shares the blocking and the animation ([01](01-evaluation.md) §6) |
| Q3 | Look and Sketches as rail items in World, beside the three classes? | yes |
| Q4 | Animation templates: the project's, or the author's in every project? | the project's, with *Save to my library* for every project |
| Q5 | Image to video: kept as a Performance method fed by the clay (*From the start still*), or dropped? | kept, as a method; Clay still decides the motion |
| Q6 | A new entity version: what does it carry from the last one? Today it carries only the sheet, poses and set | the sheet, the body, the A-pose references and the model; not the LoRA (it was trained on the old look) |
| Q7 | The ideas store: folded into draft entities and Sketches? | yes |
| Q8 | Episode's closed lists (two transitions at 12 frames, four caption styles): open them now? | when U7 touches them: a duration field and FilmCraft's other transitions |
| Q9 | Build beside the old UI (`?ui=2`) and switch at parity, or replace in place? | beside |
| Q10 | The Library's light, camera and pose entries: become Clay's presets, or go? | become Clay's presets (lights, lenses, poses) |
| Q11 | The Shots board: kept as a list view of the Flow, or gone? | kept as the Flow's *List* view |
| Q12 | Voice in the character's World header? | yes |
| Q13 | The order after U2: World first or Shots first? | World first: the order of the work, and every Shots wave needs ready entities to test with |

## 6. The decision, as it would be recorded

When the author answers, the decision log gets **D157**: *The UI is rebuilt as three layers, World · Shots · Episode, and a Bin (proto01_UI2)*. Its
text lists the answers to Q1–Q13 and the waves U0–U8, and names what it supersedes:

- **D90:** the Story-first tab structure;
- **D95:** the Image and Animate tabs;
- **D121:** Animate's modes as suites, which become the shot's levels;
- **D125:** Story's rail, the board as a workspace, the Catalogue tab, the For context;
- **D136 U1:** the separate ideas store;
- **D142:** the bench as a listed stage.

It keeps:

- **D96's** recipe and staleness model, in its one-template form;
- **D110** and **D111:** the scene as one 3D scene, split into layers;
- **D126 / D127:** the cut;
- **D141:** poses and clips fitted by contacts;
- **D97:** one job at a time.
