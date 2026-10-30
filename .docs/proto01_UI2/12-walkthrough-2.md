<!-- markdownlint-disable MD024 -->
# 12 · The walkthrough on the new UI: W1–W65

The author asked, 2026-10-30: "Can you run the same project assembly workflow on the new UI as you did on the old one? Please make sure you don't
skip the clay layer."

"The Last Ferry" was built again from an empty project on the new shell (code at `f696d2b`):

- the project `F:/loom2-projects/ux-walk2-last-ferry`, with its app state in `F:/loom2-projects/_ux-walk2-state` (the author's `.loom2_state`
  was not touched);
- its own orchestrator on 8766 and `vite preview` of the production build on 1420, driven in a visible Edge over CDP;
- the real engine, one job at a time (rule 10).

Every shot went through **Clay → Performance (the layered final shot) → Final**. The first walkthrough's register is [08](08-register.md) §1.

What was built:

- **World:**
  - the Look (*Harbour noir*);
  - Ines and Tomas: Sheet, casting, hero and references, A-pose front and back picked in Build, the body fitted, Kokoro voices;
  - The letter with a Pixal3D model;
  - Harbour pier (fitted as Open ground) and Town street (a Street), each with its set picture, set and fills.
- **Shots:**
  - the Flow: Start → Arrival → The ferryman → The seal (two voiced lines) → Choice → *She boards* → Departure | Stay;
  - Arrival, The ferryman and The seal as one scene with three cameras (coverage); Departure and Stay in scenes of their own.
- **Clay:**
  - figures bound to the characters;
  - clip blocks from the starter library (a jog along a drawn path, idles, the UAL2 lantern and rail loops, a walk);
  - cameras by number and the letter parented to Ines.
- **Performance and Final:** every shot split, performed (Wan Animate), matted, assembled, composed, rendered and marked final; The seal's lines laid
  on the lanes.
- **Episode, Edit and Bin:**
  - Episode: *Assemble from the Flow…* (the *Board the ferry* route), the Resolve export and the movie;
  - Edit: a text layer on the pier's set picture, saved into its bin;
  - the Bin.

86 jobs, one of them failed (the body fit of W9), about 63 min of job time. Lip-sync was not run: it is experimental at about 16 min a line, and
Tomas's line is over its 4.8 s limit.

## 1. What stood out

- **W43 — the final shot assembled clay mannequins**, not the performances. The set builder's *picture's camera* aims 1 m ahead, and
  `depthRange()` takes the camera's distance to its target (`passes.ts:35`, `engine.ts:1197`). Near was 0.6 m and far 3 m, so every depth pass was
  black, no actor mask was found, and the comp mattes were empty. Nothing flagged it. Moving the target 10 m out fixed the shot.
- **W40 — a final takes the stage's range, not the shot's** (`finalShot.ts:92`, `:140`, `:590`). In D157's coverage, every shot of a shared
  scene would get the same stretch. I set the stage's range by hand before each final; that bumped the stage's revision, which turned the other
  shots of the scene stale (W56).
- **W46, W58 — Wan Animate breaks on a small figure and on a figure cut by the frame:**
  - Tomas, 60 px tall, got a giant ghost of his face as the background and an inverted matte;
  - Ines in The seal's over-the-shoulder became a giant hand with her ring and an eye;
  - both cards read "done · 1✓".
- **W21, W65 — the places' pictures and fills:**
  - the set pictures came out letterboxed, and the bars are projected into every plate;
  - the pier's Fill gave four backdrop panels the identical picture (one seed), each a second pier;
  - the floor was filled with a perspective pier.
- **W9 — D162's A-pose through Make** (FLUX.2 dev, 16:9) cut Ines at the thighs, so the body fit failed. Build's Klein make gave whole figures.
- **W23, W2 — the variables and the synopsis have no home** in the new shell: D157's *Notes* and the Shots section were never built.
- **Works now** (from the first walkthrough):
  - the estimate with references (F27);
  - the newest final first (F41);
  - a figure performed from behind (F42, D158);
  - the shot held for its lines (F39);
  - clip names and masters in the Resolve export (F40);
  - the Look's own sample scene (F3);
  - Clay rendering.

## 2. The register

| # | Where | Finding |
| --- | --- | --- |
| W1 | frame | (= F1) With no project, the centre says "Open or create a project" and has no button |
| W2 | Project menu | The synopsis has no place: D157 Q1's *Notes* field was never built; Story › World went with B2b |
| W3 | World › Make | Opening Make logs a 422 for `GET /loras?model_id=` (asked before the panel has a model) |
| W4 | World › Make | The art-style placeholder says "the Story style" |
| W5 | World › Make | One field in two places: the framing words (`tree.composition`) are also Look › composition |
| W6 | World | (≈ F23) A picture's Inspector shows the raw FLUX.2 JSON prompt |
| W7 | World › Build | Three empty slot cards push the pictures to pick from below the fold |
| W8 | World › Make | The A-pose make sends the Look's fog style beside "a plain light grey studio background"; each reference note repeats the whole Sheet (360 words, 511 tokens) |
| W9 | World › Make | **D162's A-pose front (FLUX.2 dev, 960×544) cut Ines at the thighs, 2 of 2;** the pick ran the body fit, which failed. The toast names a job id, not the body fit; the slot keeps the front |
| W10 | World › Build | The run buttons give neither the model, the count nor the time before they queue |
| W11 | World › Build | Klein's A-poses: one picture of three Ines side by side; T-pose arms on most; nothing flags them |
| W12 | World | **The Inspector cannot be cleared by mouse:** after a tile's selection the entity's voice, versions and Delete are gone (nothing calls `select(null)`) |
| W13 | World | A reference's prompt is a ~300-word block (the Sheet, then "Image N shows …" ×4) |
| W14 | World | (≈ F17) New voice… overflows the 300 px Inspector sideways |
| W15 | World › Make | A new entity's Make starts from the last entity's panel (Tomas ran 2 pictures, Ines's count) |
| W16 | World | (≈ F12) A prop gets a character's copy (body and set; "rain gear, aged 60"; "a scar over the left eyebrow") |
| W17 | World, Clay | Old names: "Back to Cast", "Animate places it", "Cast props", "Open in Animate", "the Story style" |
| W18 | World › Build | The letter's Pixal3D model is a thick block; nothing for flat props |
| W19 | World › Build | The open pier was fitted as a Room with a ceiling; Room is the default |
| W20 | World › Build | Open ground gives 12 faces, 11 of them backdrop panels; Fill queues them all (its toast gives the total) |
| W21 | World › Build | **Fill: one seed for every face**, so four backdrop panels got the byte-identical picture (three from ComfyUI's cache in < 1 s); each panel painted a second pier; the floor got a perspective pier |
| W22 | World › Build | The street's projected road is a darker trapezoid against the filled cobbles (no tone match) |
| W23 | Shots › Flow | **The variables have no home:** D157's "section of the left column" was never built; "Declare them in World"; *+ set* lists none |
| W24 | Shots › Flow | (= F20) A new node lands on the last one; Fit zooms to 2×; the light minimap covers the node |
| W25 | Shots | One text, two names: the header's *description* is the Inspector's *action* |
| W26 | Shots | Two "scenes": the header's "no scene yet" (the stage) beside the Inspector's "scene: Arrival" (the Flow group) |
| W27 | Shots | The lines are edited in two places; the Board picker lists every Bin page of the project |
| W28 | Shots › Flow | (= F19) A Choice offers shot verbs; an untitled node is headed by its raw id |
| W29 | Shots › Flow | *New shot in a new scene* leaves the Flow for the new shot's empty Clay |
| W30 | Shots › Flow | **The same item ignores the click point and splices the node after the current shot**, rewiring The seal → Choice silently |
| W31 | Shots | Times are UTC shown as local ("created 15:15" at 16:15 CET) |
| W32 | Shots | Coverage cameras are named "Camera 1 2", "Camera 1 2 2" |
| W33 | Shots | Departure's Inspector offers lip-sync for The seal's lines |
| W34 | Clay | (= F35) A figure from Figures + lands where the centre ray hits: (0.13, 1.77, −30) on the backdrop, in the air |
| W35 | Clay | A scene at a place starts with an unbound "1.75 m for scale" mannequin; its chip is disabled |
| W36 | Clay | A bound figure keeps its name ("1.75 m for scale" for Tomas, down to the layer names) |
| W37 | Clay | A prop lands at the active camera's own position; its parent lists figures, not a hand |
| W38 | Clay | The prop's height goes to the flat model's thickness: a 1 m box until scaled by hand |
| W39 | Performance | The method card says Final shot, the Recipe says Image to video; the empty centre says "Animate" |
| W40 | Performance | **A final takes the stage's range, not the shot's** (`finalShot.ts:92`, `:140`, `:590`) |
| W41 | Performance | The Recipe says the plate and the animation reference are "missing" after both are made |
| W42 | Performance | One final's owed time is "≈ 4 min" on the card and "≈ 7 min" on the foot |
| W43 | Performance | **The assembly showed clay mannequins:** all depth passes black from `depthRange(\|pos − target\|)` with the picture camera's 1 m target; empty comp mattes; nothing flagged |
| W44 | Performance | A prop layer's beauty is the whole set, opaque |
| W45 | Performance | (= F44) The composition poll logs a 404 per final |
| W46 | Performance | **A small, far figure:** the reference at ~20 px, a giant ghost face as background, an inverted matte, a pale box with a hole in the shot; "done · 1✓" |
| W47 | Performance | Ines's layer reference lost her head with the grey background |
| W48 | Final | *Make the composition* leaves it closed; the toast says "Open in Final" while in Final |
| W49 | Final | **The render becomes the shot's clip on the server, but the page keeps the old version:** *Mark the shot final ✓* stays locked with no reason; a reload unlocks it |
| W50 | Performance | The Clips card opens on the oldest final, or on another shot's; a final offers *Variations* and *Try the other model* |
| W51 | Performance | With the Bin drawer open the player overflows its transport |
| W52 | Shots | The storyboard drops a stale shot's picture (black thumbnails, !●●) |
| W53 | Performance | In a shared scene every final of the stage is listed under every shot; the foot reads "Arrival · the next step" on The ferryman |
| W54 | Performance | A figure never in the shot gets a layer, and Assemble waits until it is performed on an empty pose |
| W55 | Performance | The Open-ground floor is black from the coverage camera: a black band in The ferryman's plate |
| W56 | Shots | Any edit to a shared stage stales every shot of the scene (Arrival ●●● → !●●) |
| W57 | Bin | Imports fills with working files: layer references, pose guides, face bakes (61 after World and three finals) |
| W58 | Performance | **A figure cut by the frame becomes a monster:** The seal's over-the-shoulder Ines as a giant hand and eye; "done · 1✓ 2✓ 3✓" |
| W59 | World › Edit | The mode switch's Edit stays greyed with a picture selected (the Inspector's Edit works); the save toast offers "Open … in World" while there |
| W60 | Departure | The ferry is painted on the baked backdrop; nothing lets a part of a set move |
| W61 | Episode | "2 of 4 clips not final shots" for four shots marked final (the stale ones) |
| W62 | Episode | The Clips list names nothing ("composition · 121f @ 24", "wan22 · 9f @ 16" …) |
| W63 | Episode | The Resolve export names clips after their shots and points at the masters (F40 fixed); the lines are named by asset id |
| W64 | World › Edit | Esc while typing a text is its ✕: the layer is thrown away |
| W65 | World › Build | **The set pictures came out letterboxed** (the Look's "cinematic … film grain"); the bars are projected into every plate; nothing checks for them |

## 3. Measured

| What | Time |
| --- | --- |
| The style sample (Lumina Image 2, cold) | 53 s |
| FLUX.2 dev casting image, 0 references | 37–44 s (the session's first, 80 s) |
| FLUX.2 dev A-pose, 4 references (promised 149 s) | 150–156 s |
| Klein 9B A-pose / back view | 16–56 s |
| Pixal3D model | 257 s |
| MoGe2 set fit | 2.6 s |
| Fill, a face (Klein inpaint) | 9–53 s (identical inputs < 1 s, W21) |
| Kokoro line (CPU) | 10–29 s |
| Wan Animate, one character, 49–77 frames | 99–127 s a batch (The seal: 3 batches a character) |
| Matte | 18–27 s (169 frames: 62 s) |
| Assembly (CPU) | 14–23 s (169 frames: 62 s) |
| Composition render (CPU) | 3–8 s |
| The movie (CPU, 21.7 s at 1080p, −16 LUFS) | 8.5 s |

## 4. The first walkthrough's findings, now

Fixed or gone: F3, F24 / F30 (a shot's cast is its scene's), F25 / F26 / F29 (the For trip is gone), F27, F37 (the toast says the range stays),
F39, F40, F41, F42. Partly: F11 / F12 (no coverage grid; a character's copy, W16), F13 (greyed). Still: F1 (W1), F2, F17 (W14), F19 (W28), F20 (W24),
F23 (W6), F35 (W34, W37), F43 (W55), F44 (W45).
