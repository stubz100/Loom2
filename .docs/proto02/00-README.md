<!-- markdownlint-disable MD013 -->
# loom2 · proto02 — the application again, and the way there

Started 2026-11-10 at `79ebcfc` (D196 built in the working tree, not committed). **Status: the evaluation and the plan written; the author
answered all 22 questions the same day ([06](06-answers.md)), the documents amended to them, D197 recorded, D196 committed as it was — RS0 done.
The plan then gained RS0b (the findings that are faults today, fixed first) and a table of where every finding is fixed (03 §3), on the
author's ask. RS0b built the same day (the A-pose frame, the stage's size, the clip's range, a used stage kept, D181's record). RS1 (World › Clay) built 2026-11-11. Next: RS2 (the run form) and RS3 (a shot is its scene). Nothing in the code was changed by proto02.**

## 1. The request

The author, 2026-11-10:

> My application in the local repository has been revised many times — finally I think it starts to come together, but some parts of it are still
> in complete disarray. The workflow I'd like to have:
>
> 1) prototyping in World — characters, props and places. They are working well up to image generation and editing. I'd like to move the Clay
> editing back here — and to extend the header rail (make – edit – clay), also take away the "open in clay" button
>    a) for character generation, everything to do with the character specifically in clay should be here — skeleton, posing, etc… Also, the clay
>    generation is a button click with no exposed parameters — every generation should have their parameters exposed at least (I believe there is
>    no other model here than pixal3d, but if there is, then we should also have the tiles to pick a different model). There should be no "open in
>    world" switch either
>    b) for place generation, the same — make – edit – clay.
>
> 2) Once my scene assets have been fully created and refined, I can start assembling the shot. Clay menu should be the editing bench to assemble
> each shot in detail — so every setting to do with shot settings should move here instead of the shot menu. Shot should only be a high level
> overview and a full assembly bench for each episode, but settings and details should all sit in clay. It would also be nice to see a thin rail at
> the top, where a simple graph of the shots are visible, and selectable. Shots and Clay scenes should be absolutely connected — if someone creates a
> scene, that should automatically create a shot, and also the other way around. Clay sets should be the place to create animations and everything
> beyond the char/prop/place prototyping — this is a place where small parts of the story should be constructed (I think we said a maximum of
> 15 seconds…? — please confirm).
>
> 3) A shot has a Clay part and a postprocess part also (like in world — you have make and edit). So once a shot was created, that should be
> regarded as a draft and the next step should be the postprocessing — we used to have this feature taken from effectcraft, but now it doesn't seem
> to be part of loom2 anymore… (can you check?) Processing should have animation generation part, but it should not allow creating animations
> without the clay foundation — so the models here should be either v2v, or i2v. We should be able to "copy" these processing chains to other shots,
> as they may have to be used across multiple, in order to keep an episode coherent.
>
> 4) once we have the shot created in clay and processed, we can assemble the final episode — this is only a video cutting and post-processing bench
> (I don't think we have gone this far with any of the projects yet, and I'm happy to refine this part when we have everything in order up to this
> point)
>
> Can you recreate the overall application description in .docs/proto02/ folder? Please make a thorough investigation in the current project as to
> where we are, and establish a development plan as to how to get into the above desired state. Also a few guidelines:
> - no hard coded templates — there should be no templates in the tool which cannot be recreated by using the commands of the tools themselves.
>   This should also apply to using generations with baked in parameters. The whole templating and quick access management part of the application
>   should not be a priority at this moment — and perhaps investigated later, when the functionality exist properly for all transactions.
> - Please construct the evaluation and plan documents before doing any changes, then ask questions relentlessly if something is unclear.

## 2. The documents

| # | Document | What it holds |
| --- | --- | --- |
| 01 | [The application](01-application.md) | **loom2 as the author wants it to work:** what it is, the four steps (World › Make · Edit · Clay → Clay's shot bench → Process → Episode, with Shots as the overview), the frame, each layer, the rules (the author's G1–G6 and the house rules), the records, what it would supersede |
| 02 | [The evaluation](02-evaluation.md) | **where loom2 is**, layer by layer, with every claim cited to the code; the gaps PG1–PG28 |
| 03 | [The plan](03-plan.md) | the waves **RS0–RS10** with **RS0b** (the findings that are faults today, fixed first), where every finding PG1–PG28 is fixed, the order, sizes, rig checks; the spikes E65–E67 |
| 04 | [The questions](04-questions.md) | **Q1–Q22** for the author, each with a recommendation and the wave that waits on it |
| 05 | [The inventory](05-inventory.md) | every generation (A1–A47) and every template (B1–B45) with its verdict against G1 / G2 and its wave; the parameters hidden on purpose and why |
| 06 | [The answers](06-answers.md) | the author's answers to Q1–Q22 and the two follow-ups → **D197** |

## 3. The short answers to the author's three checks

- **Is Pixal3D the only 3D model?** Yes. `pixal3d-int8` is the only spec that makes a mesh (`orchestrator/loom2/models/specs/pixal3d.toml`); TripoSR
  was dropped and deleted (D136), Hunyuan3D is excluded by its licence (rule 7). Its recipe already takes the resolution (1024 / 1536), the face
  count and the seeds (`recipes.py:428–438`); no button sends them (02 PG5).
- **15 seconds?** No — D181 Q4 recorded a **5 s default and a 20 s cap**, and the code enforces 20 s (`frontend/src/suites/stage/sceneLength.ts:5`,
  `orchestrator/loom2/workspace.py:15–16`). Asked (Q3), the author kept 20 s.
- **Is EffectCraft still in loom2?** Yes, wired and pinned (v0.12.0): it is the Final level's compositor — layers, masks, 21 effects, the passes
  (*Clean up*, *Creative*, *Face*, *Lip-sync*), the render. It reads as gone because it is reached only through Shots › Final, after a *Layered*
  performance's *Make the composition*; the One pass and Image to video methods never reach it (02 PG12).

## 4. Conventions

As proto01: numbered documents are specs, amended the same day an answer changes them; the decision (D197) is recorded in
[proto01 13](../proto01/13-decision-log-and-open-questions.md) before any code; measurements go to the [journal](../proto01/90-journal.md) with real
timestamps.
