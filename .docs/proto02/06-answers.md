<!-- markdownlint-disable MD013 -->
# 06 · The author's answers → D197

The author answered [04](04-questions.md) on 2026-11-10, in four rounds, the same session the documents were written. Seven answers went against the
recommendation (**bold** in the first column), one was written in the author's own words (Q22), and two follow-ups were asked after the first round
(Q2b, Q6b). [01](01-application.md), [03](03-plan.md) and [05](05-inventory.md) are amended to them; the decision is **D197** in
[13](../proto01/13-decision-log-and-open-questions.md).

| # | The question | The answer | What it settles |
| --- | --- | --- | --- |
| Q1 | the top rail's order | World · Clay · Shots · Episode · Bin (as recommended) | `layers.ts` unchanged |
| **Q2** | coverage — one scene for several shots? | **strictly one scene per shot** | *another angle* copies the scene; D157 Q2's and D181 Q3's coverage go; RS3's migration splits every shared scene into one per shot |
| Q2b | a shot's own range inside its scene | **the scene's length is the shot's** (as recommended) | one timeline; the shot's range field goes; every render reads the scene; trimming is the cut's (Episode); the migration cuts each shot's scene to its old range, the keys shifted to start at 0 |
| **Q3** | the length cap | **keep 20 s** (5 s default) | `SCENE_SECONDS_MAX` unchanged |
| Q4 | the shot rail | the shots and the forks, the logic nodes as small diamonds (as recommended) | RS4's rail |
| Q5 | poses and animations | a character's poses in World › Clay; the animation workshop in Clay (as recommended) | RS1, RS4 |
| Q6 | a copied chain | a snapshot (as recommended): never the outputs; copy again to update; the source remembered | RS7 |
| **Q6b** | what a copy carries | **chosen per copy**: the copy sheet has two ticks, *Process* and *Final* | the chain record keeps the two parts apart |
| Q7 | new v2v spikes | after RS7, on the author's word (as recommended) | E65, E66 wait |
| **Q8** | a clip from a free picture | **allowed in World › Sketches** (a mood test), never in a shot | Sketches gains image to video; inside a shot every clip starts from its clay (G4) |
| **Q9** | Performance and Final in Clay | **two modes, Process \| Final** | the shot's modes are Scene · Process · Final; Process makes the footage, Final is the EffectCraft compositor with its passes |
| Q10 | "scene" twice | the Flow's group renamed **sequence** (as recommended) | RS3 |
| Q11 | episodes | one episode per project (as recommended) | no records change |
| **Q12** | *Speaking* and *Extend* | **kept, marked experimental** | Process's Generate offers both with the label; an extension's frames past the scene read no clay, and the step says so |
| Q13 | where a run form sits | inline above its ▶ (as recommended) | RS2's part |
| Q14 | D196 | committed as it is before RS0 (as recommended) | done 2026-11-10 |
| Q15 | crowds and walkers | with the place, World › Clay (as recommended) | RS1 |
| Q16 | what a run form remembers | per thing — the version, the shot (as recommended) | RS2 |
| Q17 | shot versions | in Clay's header; the scene one per shot with its undo (as recommended) | RS4 |
| Q18 | the author's own presets | keep working, no new work (as recommended) | RS8 leaves them |
| Q19 | the lines | a Lines track in Clay (as recommended) | RS4 |
| Q20 | the line-up | kept (as recommended) | RS1 |
| **Q21** | D157's leftovers | **keep Expand in Sketches**; remove *Train a LoRA…*'s palette reach and the old Ideas board's *Make the clay* path | RS8 |
| Q22 | the stage's preset sets and stand-ins | in the author's words, below | RS8, E67 |

**Q22, the author's words:** "Stand-in presets should all be props — these presets can be removed. The scene geometry should be simple — built from
blocks. Otherwise, I believe we can set the clay background from an image, and there is a box set where the floor/walls/etc… can be set from the image
also. However, we should also look into creating scene background 3D from images (if this is possible)."

What it settles:

- The stand-ins (crate, stool, table, pole) and the preset sets (room, street, deck, empty) go; a thing in a scene is a World prop.
- A scene's own geometry is **blocks**: a box with its sizes as fields, added and edited with the scene's commands.
- **A background from an image stays** — the image plane, and a picture's relief as a stage's set (today's *set* verb, 05 A18, which is no longer
  removed).
- **The box set stays** — the place's set fitted from its set picture (the floor, the walls, the kind, the sizes; D143).
- **A new spike, E67 — a scene's background in 3D from images**, added to [03](03-plan.md) §4.
