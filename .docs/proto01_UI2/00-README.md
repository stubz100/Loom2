# proto01_UI2 · A new UI from the ground up: World · Shots · Episode, and a Bin

Status: **proposal, 2026-10-28; answered the same day → D157** ([09](09-answers.md)). The author agreed with every proposal, kept the synopsis as a
note (the logline goes), took Expand and LoRA training out altogether, and asked for a full light editor in Clay. U0 started the same day. Read from the
code at `e8ce296`, after a full walkthrough of the app on the same day ([08](08-register.md)).

## The request

The author, 2026-10-28, after the walkthrough:

> I think there are a lot of requirements that were inherited from the old loom, or were the result of a unfinished attempt to enhance the current
> functionality, therefore I would like to build a new UI - from to-down:
> 1) the main, high-level workflow should be a layer-by-layer refinement:
> a) first layer is an ideation draft, what currently is in world - characters, props, places. […] story/world needs to go […] Cast should have the 3
> options - characters/props/places […] There should be a picker rail for the 3 entinies […] and then it should be the same as in image - with the whole
> left panel with make/edit. The left panel should have a header […] Every creation should have a bin reference (like bin-world-character-Inez-v1
> (bin/world/type/name/version)) and all creations should be here - we should remove the batch grouping […] there is no point running specific details
> here - like light, or pose - these […] belong […] into clay instead. The purpose of this layer is to make sure everything is ready for Clay
> b) Clay and flow should be very closely connected - each shot should be a clay stage […] when you click on the shot, it should bring up the clay
> arrangement that is connected to it. Question: why do we have a shot and a dialogue option in flow? […] There should always be a clay composition to
> every shot […] A shot should have an animation editor suite also […] some parts of the timeline of these animations should be saved as own animation
> templates […] Performance should be a refining stage of clay (and not an animation generation place), and Final should be the place where the final shot
> comes together with voice and processing […]
> c) Episode then connects the flow finals and puts them into a filmcraft-like editor […]
>
> I think we have all the functionality to enable this workflow, but I think the current UI is so scrambled, that I'd advise you to start from scratch
> and build a brand new UI from the ground up. Can you evaluate my comments and propose a brand new UI, but also evaluate the backend functions alongside
> it? Please document it in .docs/proto01_UI2/ folder before do any changes

## The documents

| # | Document | What it holds |
| --- | --- | --- |
| 01 | [The direction, evaluated](01-evaluation.md) | the author's twelve points, each against the walkthrough and the code, with a verdict; what the direction leaves out and where it goes |
| 02 | [The structure](02-structure.md) | the three layers and the Bin; the records as the author sees them; one home per asset; context without chips; the frame |
| 03 | [World](03-ui-world.md) | the rail, the entity header per class, the readiness line, Make scoped to the entity, Edit, the bin and its roles, Look, Sketches, the commands |
| 04 | [Shots](04-ui-shots.md) | scenes and shots; the storyboard strip and the shot header; Clay and **the animation editor** (clip blocks, key layers, templates); Performance (methods, layers and takes); Final (voice, lip-sync); the words of a shot's pictures; the Flow with one shot node |
| 05 | [Episode and the Bin](05-ui-episode-and-bin.md) | the cut reads finals; four fixes; the Bin's tree, rules, screen and drawer |
| 06 | [The backend](06-backend.md) | every record and route the layers use, with keep / adapt / new / retire; the frontend's reuse map; the gap list G1–G15 |
| 07 | [The plan](07-plan.md) | built beside the old UI; the waves U0–U8 and spike E42; the risks; **the decisions Q1–Q13**; D157 as it would be recorded |
| 08 | [The registers](08-register.md) | the walkthrough's findings F1–F44 and its timings; the code review's FE, BE and RC findings |
| 09 | [The answers](09-answers.md) | **the author's answers (D157)** and what they change: no Expand and no LoRA; lights with templates and an editor; the synopsis as a note |
| 10 | [Trying the new UI](10-trying-the-new-ui.md) | **the author's click-through** of the built UI (U0–U8): what to try in each layer, the checks, what is not there yet |

`img/ui-*.jpg` are wireframes, rendered from `mock/ui2-mock.html` by `mock/render.cjs` (a static mock, not the app). Their pictures are the walkthrough's
own (`img/src/`); their numbers (scores, times, counts) are examples. **Dashed orange marks what is new.**

## What was found

1. **The author's direction is right, and its biggest gain is structural.** Today every making step is a trip out of Story and back on the *For* chip,
   and that joint is where most of the walkthrough's defects sat (F24–F29). In a layer UI the context is where the author is, so the chip and its leaks
   have nowhere to live ([01](01-evaluation.md) §1, [02](02-structure.md) §4).
2. **Two refinements of the direction:**
   - **One stage per *scene*, a camera per shot.** Coverage then shares one blocking; one shot per scene stays the default (Q2).
   - **Image to video kept as a Performance method fed by the clay**, so Clay still decides the motion (Q5).
3. **Shot and Dialogue nodes are the old loom's dialogue graph** (loom R134 / R146) with a Shot node added later (D96). They already hold identical
   fields, so the merge moves no data ([06](06-backend.md) §2.1).
4. **The backend has nearly everything.** What it lacks, in fifteen items (G1–G15), is mostly how things are *joined*:
   - a home for every asset;
   - a scene that owns its stage;
   - a shot's own range;
   - clips kept as clips (today a walk is baked into 329 keys);
   - animation templates;
   - one recipe template instead of five;
   - the words of a shot's pictures composed from World and Clay (today a preset set's plate reads "The room is empty");
   - Episode reading finals.
5. **"From scratch" means the shell, not the engines.** The frontend survey found the 3D stage engine, the Edit canvas, the timeline, the Final editor,
   the FilmCraft cut editor and the Catalogue store clean to mount. What has to go first are four seams:
   - `ui.suite` as the only "where am I" (37 reads, 80 `setSuite` calls in stores and commands);
   - key hooks living inside Strip components;
   - no shared records layer;
   - the singleton makers.
6. **Some defects are worth fixing now, whatever is decided (wave U0):**
   - Clay cannot render in a dev build since 2026-10-27 (F34);
   - the final shot's foot acts on the oldest final (F41);
   - closing the detached loupe ends the app (RC#1);
   - ids from URLs become paths (BE#1);
   - Run stale replays a whole batch with new seeds (BE#3);
   - the estimate ignores references: "≈ 42 s" ran 16 minutes (F27).

## The proposal in one picture

```
World  ─────────────▶  Shots  ───────────────────────────────────────────────▶  Episode  ──▶ Resolve · the movie
Characters · Props ·   the Flow (one shot node; Choice, Condition, Action…)      the cut of the finals,
Places │ Look ·         └ a shot = a camera on its scene's clay stage              one per route
Sketches                   Clay (arrange, animate: clip blocks, keys, templates)
 each: header + Make /     Performance (the clay made into footage: layers, takes)
 Edit + its bin            Final (composed with voice, lip-sync, effects) ──▶ the shot's final
                                                         Bin: every creation in its home — world/… · shots/… · episode/…
```

## Method

- **The walkthrough:** the app driven in Edge over CDP, step by step, with screenshots. It ran against its own orchestrator and state folder, the real
  engine, and a production build where the dev build could not show Clay.
- **The backend and the frontend:** mapped by four read-only surveys. Their load-bearing claims were read again in the code:
  - Shot vs Dialogue (`story.py:383-440`);
  - the stage's single range (`stages.py:246`);
  - the baked clip (`stageStore.ts:475-487`);
  - the bins' readers (`mentions.py`, `trainer.py:95`);
  - `Cuts.write` (`cuts.py:567-602`);
  - `nextFinalStep` (`finalShot.ts:607-610`);
  - the StrictMode canvas (`main.tsx`, `engine.ts:183`), reproduced in the page.
- **The code review:** four reviewers ([08](08-register.md) §2).
