<!-- markdownlint-disable MD013 MD024 -->
# 03 · The plan: from today to the four steps

Written 2026-11-10; **amended the same day to the author's answers ([06](06-answers.md)) — D197 recorded, RS0 done — and again on the
author's ask to plan the fixes of the findings too: wave RS0b (the findings that are faults today, fixed before the restructure) and §3, where every
finding PG1–PG28 is fixed.** The waves are named **RS0–RS10** (restructure). Each ends usable in the shell the author runs (D181 Q10's rule: in place, wave by wave, no `?ui=` fork), with its checks
green, its e2e scenarios ported, the screenshots of every section it touched sent, and its journal entry.

## 1. The principles of the order

1. **Re-house before re-design.** Most of what the author asks for exists and is in the wrong place (02 §1). The first waves move working parts
   (World's Clay mode, the shot's settings) so the author works in the new shape early; the new parts (the copy, the forms everywhere) come after.
2. **Records before screens where records change.** Two things change records: one scene per shot (RS3) and a shot's process and final settings as
   a record (RS7). Each gets its migration of the existing projects (the author's stubz002 and propo02's Followed) in the same wave — a dry run
   first, its list sent, written on the author's word.
3. **The two rules run through every wave.** G2 (parameters exposed) is built once as a part (RS2) and applied in the wave that touches each
   generation; G1 (templates) is one sweep (RS8) after the recipe templates are gone (RS7).
4. **One GPU job at a time.** Only RS0b's one A-pose make, RS2's, RS6's and RS7's rig checks and the spikes use the GPU, each alone (rule 10).

## 2. The waves

| Wave | What | Closes | Depends on | Size |
| --- | --- | --- | --- | --- |
| **RS0** ✓ | D197 recorded from the answers; 01 / 03 / 05 amended; D196 committed as it was (Q14); the offline checks re-run | — | the answers | done 2026-11-10 |
| **RS0b** | **The findings that are faults today, fixed in the shell as it is** (none waits on the restructure; each would otherwise keep making wrong records for weeks): **(1)** the A-pose route (`POST /story/profiles/{pid}/versions/{vid}/anim-ref`, `routes/story.py:396–415`) makes a character's front, back and side at D177's 2:3 portrait of about the same pixels (Make's `to23`, `make.ts:64–67`, mirrored on the server) for every caller — the buttons, the slot's right-click, the readiness warnings — while a prop's view and a set picture stay 16:9 and a hand or feet picture 1024²; its docstring's "16:9" corrected; the A-poses already made at 16:9 in stubz002 and Followed listed for the author, kept unless remade (PG22). **(2)** A stage made by *New shot*, a re-scene or a copy takes the project's format: `StageStore.scene_stage` / `create` read the workspace's format when no size is given, the `{1920, 1080, 24}` literal gone (`stages.py:589, 668`); the stages whose size or rate differs from the project's listed for the author, none changed by itself (a rate change re-times the keys) (PG26). **(3)** Until RS3 removes the range, the stage clip renders the open shot's range as the final and the animatic do (`stageStore.ts:690–700`, `guideFrames`), so a shot's three renders agree (PG27). **(4)** Until RS3's cascade, a stage a shot still uses cannot be deleted — a 409 naming the shots (`routes/stages.py:644–650`) (PG20). **(5)** The record put straight: D181's row in 13 and propo02 05's status note that §4.6's records (`shots/<nn>/scene.json`, `clay/<kind>/<id>.json`) and §5's removals (Final as a level, the method cards, the stage picker, the two *New shot* entries) were **not built**, and that D197 supersedes them (PG4) | PG4 (the record), PG20 (interim), PG22, PG26, PG27 (interim) | RS0 | S |
| **RS1** | **World › Clay.** The mode rail Make · Edit · Clay; Clay's Library page for the entity moved whole into it — a character's Figure, Shell, Skeleton (D190's switch folded into sections), **Poses** (the bench in pose mode, *Save for ‹character›*, the list with stills, rename, remove), Test; a prop's Model and Height; a place's set with its crowd and walkers (Q15); the bench in World's centre; the line-up from the class rail (Q20); one readiness line; *Open in Clay ▸* and *Open in World ▸* removed; Clay › Library's Figures / Props / Sets kinds removed | PG1–PG4 | RS0 | M |
| **RS2** | **The run form.** One part for every ▶ that queues a job, inline above it (Q13): the model tiles (`ModelCards`, one tile when one model), every recipe parameter with its default from `/capabilities` (T8) and its measured reason as the ? help ([05](05-inventory.md) §C), the prompt's lead as editable text, count, seeds, the cost; the settings kept on the thing (Q16); the **exposure audit** (`scripts/exposure_audit.py`, CI): every recipe field is in a form or on an allow-list with its reason. Applied to World's generations ([05](05-inventory.md) §A.1–A.2): the shell (also when queued by itself after a fit), the prop's model and the moving things (resolution, faces, seeds, the source); the set's relief (lens, relief, decimation) and its bake's texel; the Fills', the crowd's, the walkers' and the clean's leads and settings with the loop's model tiles; the turn test; the A-pose buttons removed so Make's framing is the one way (PG22); the chips' side effects shown as fields (PG25) | PG5, PG15 (World), PG22, PG24 (World) | RS1 | M |
| **RS3** | **A shot is its scene.** One scene per shot, strictly (Q2): *New shot* anywhere makes node + scene + camera in one sheet (name; empty · at a place · a copy of another shot's scene); *another angle* is a new shot on a copy; Clay's *New stage…* and a camera's *New shot from this camera…* go; a delete takes both (asked first); **the scene's length is the shot's** (Q2b) — the shot's range field goes and every render reads the scene; the project's format for every new scene (RS0b's fix kept, now through the one *New shot* sheet); the cap stays 20 s (Q3); the Flow's scene group renamed *sequence* (Q10) and its `stage_id` dropped — a sequence groups shots and owns no scene, so it can no longer drift from them (PG19). **Migration:** every scene shared by several shots split into one copy per shot (each keeps its camera; its finals keep the revision they were made from); each shot's scene cut to its old range, keys and blocks shifted to start at 0; a stage with no shot given one, or listed for the author to delete; a shot with no stage given an empty scene; dangling links cut | PG6, PG7, PG18–PG20 | RS0 | M–L |
| **RS4** | **Clay is the shot bench.** The shot rail (the Flow's shots and forks, state dots, ＋; Q4); the rail Shot · Animations (Q5); the shot header (name ▾, version ▾, *New version*, *Mark final*, the description, the length, the size and the rate) with the modes **Scene · Process · Final** (Q9); the shot's settings moved from Shots' header — the Lines track with its editor and the voice's speed (Q19, A41), the camera in the outliner, the cast in the outliner; the Still form and the stage clip's settings kept on the shot, and the Image to video panel's kept per shot, not per browser (PG9); Process and Final mounted as they are, from Shots, under the new header — **without** the Shot section's stage picker (which opened any stage, whatever the shot) and the recipe template select (PG17, PG11); Clay › Scenes' picker gone | PG8, PG9, PG10 (the settings), PG17 | RS3 | L |
| **RS5** | **Shots is the overview.** The Flow (canvas \| list, with its sequences) and the storyboard with Play; the card a read-only ledger with *Open in Clay ▸*; the levels Clay · Performance · Final, the shot header's editors, the recipe template select and the stage picker removed from Shots; the Episode's finals list opens Clay | PG10, PG11 (Shots side), PG17 | RS4 | M |
| **RS6** | **Process and Final, made whole.** First, **Final for every method** (PG12): today only a *Layered* performance's *Make the composition* reaches the EffectCraft compositor; a One pass clip, an i2v clip and a Speaking clip each become the composition's footage layer (with their matte where one exists), so every shot can be finished in Final. Process: the steps Source → Still → Generate, Performance's three method cards re-housed as Generate's kinds, *Speaking* and *Extend* as kinds marked experimental (Q12); every step's run form from [05](05-inventory.md) §A.3 — a character layer's performance first (A31), the plate's automatic paths shown as a choice with its reason (A28–A29, B43), the video presets' hidden fields (B13), the prompt leads (B25); G4 in the routes and the panels: an i2v start / end must descend from the shot's clay (lineage), a picture from elsewhere refused; **free image to video moved to World › Sketches** (Q8). Final: the compositor as it is, its passes with run forms and model tiles (A33–A35), the effects' every parameter behind "more" (B33), the output's size and rate as fields — the F16 in the code (`stageCommands.ts:191`, `finalShot.ts:710`) and RIFE's automatic 24 become the shot's rate (P16, A30, A43, PG28) | PG11–PG14, PG15 (Clay), PG24, PG25, PG28 | RS4 | L |
| **RS7** | **A shot's processing as a record, and its copy.** `ShotVersion.process` and `.final_settings` (the steps, their models and parameters; the composition's passes, effects, voice options, output — no outputs) in place of `method` and the recipe template id, the old recipe runs kept as history; *Copy to other shots…* on the shot rail (several shots picked) with the two ticks **Process** / **Final** (Q6b), a snapshot that remembers its source (Q6), characters matched by who they are, the unmatched listed first; the recipe graph (RC1) draws the steps. **Migration:** each version's method and recorded runs become its process | PG16 (recipe templates), PG21 | RS6 | M |
| **RS8** | **The template sweep (G1).** What RS2 / RS6 / RS7 did not already take from [05](05-inventory.md) §B: the stand-ins (crate, stool, table, pole) and the preset sets (room, street, deck, empty) removed — **blocks** stay as the scene's simple geometry, a box with its sizes as fields (Q22); scenes holding a removed kind get a block of its bounds in its place (listed first); *Train a LoRA…*'s palette reach, the LoRA check and the old Ideas board's *Make the clay* path removed (Q21; Expand stays in Sketches); the hand presets checked (B18); the author's own presets left as they are (Q18); no new template or quick-access work (G3) — the parked study recorded as an open question | PG16, PG23 | RS7 | S–M |
| **RS9** | **The run form everywhere else.** The exposure audit's allow-list driven to the parameters with a reason: Edit's AI tools' hidden fields (A9), the style sample (A5), the body fit's and the hands' reads (A15–A16, or allow-listed as measurements), SAM 3's threshold (A23), a picture's relief as a scene's background (A18, kept — Q22) | PG15 (rest) | RS2 | M |
| **RS10** | **Episode reads the finals.** The cut's V1 takes each shot's final; *Assemble from the Flow* follows the shot rail's order; nothing else (the author's later study) | — | RS7 | S |

Sizes: **S** a few days, **M** about a week, **L** about two weeks, author + AI; the C-waves of D181 were estimated the same way and built faster,
so these are upper bounds. The total is roughly ten weeks before any spike.

```
RS0 ✓ ── RS0b ─┬─ RS1 ── RS2 ─────────────── RS9
               └─ RS3 ── RS4 ─┬─ RS5
                              └─ RS6 ── RS7 ─┬─ RS8
                                             └─ RS10
```

RS1–RS2 and RS3–RS4 can run side by side (World and Clay touch different files), but — the author's rule since the last review ("fewer agents") —
one agent works the frontend of a wave at a time.

## 3. Every finding, and where it is fixed

Each gap of [02](02-evaluation.md) with the wave that fixes it and the fix in a line. *Interim* marks a fault RS0b stops now that a later wave
removes for good.

| # | The finding | Fixed in | The fix |
| --- | --- | --- | --- |
| PG1 | World has no 3D; an entity's state told in two places | RS1 | World › Clay; one readiness line |
| PG2 | *Open in Clay ▸* / *Open in World ▸* | RS1 | both commands removed |
| PG3 | a character's poses have no home | RS1 | World › Clay › Poses |
| PG4 | D181's records (`scene.json`, `clay/<kind>/`) never built, the record says built | RS0b | D181's row and propo02 05 corrected; D197 supersedes; nothing to migrate (the 3D is on the version) |
| PG5 | the shell is a button | RS2 | its run form: tile, source, resolution, faces, seeds, the cost; the automatic shell runs the version's settings |
| PG6 | a scene and a shot made together one way only | RS3 | one *New shot* sheet everywhere; *New stage…* and *New shot from this camera…* go; the cascade |
| PG7 | the cap is 20 s, not 15 s | — | answered (Q3): kept |
| PG8 | Clay opens a stage, not a shot | RS4 | the shot rail and the shot header |
| PG9 | the Still's and the stage clip's settings live in the browser | RS4 | kept on the shot, the Image to video panel's too |
| PG10 | Shots is where a shot is set up | RS4, RS5 | the settings to Clay; Shots read-only |
| PG11 | Performance and Final are levels of another layer, with cards, a template select, a stage picker | RS4, RS6 | mounted under Clay's shot header without the picker and the select; the cards become Generate's kinds |
| PG12 | EffectCraft reached only after a *Layered* performance | RS6 | Final for every method: a One pass, i2v or Speaking clip becomes the composition's footage layer |
| PG13 | a clip from any picture | RS6 | G4 in the routes (lineage to the shot's clay); free image to video moved to Sketches |
| PG14 | *Speaking* in the record, not in the menu | RS6 | a Generate kind, marked experimental (Q12) |
| PG15 | 24 of 47 jobs a button with nothing to set | RS2, RS6, RS9 | the run form, wave by wave; the exposure audit in CI |
| PG16 | templates the tool cannot recreate | RS7, RS8 | the recipe templates replaced by the shot's own process / final; the sweep of 05 §B |
| PG17 | the stage picker opens any stage | RS4 | not mounted under Clay's header |
| PG18 | two *New shot* entries | RS3 | one sheet |
| PG19 | the Flow's scene group and the shot's stage drift | RS3 | the group a *sequence* with no `stage_id` |
| PG20 | orphan stages; a deleted stage leaves shots pointing at it | RS0b (interim), RS3 | now: a stage in use cannot be deleted (409 naming the shots); then the cascade and the migration |
| PG21 | nothing copies a shot's processing | RS7 | *Copy to other shots…*, Process / Final ticked |
| PG22 | the A-pose buttons make 16:9 against D177's 2:3 | RS0b, RS2 | now: the route makes 2:3 for every caller, the 16:9 ones listed; then the buttons go (Make's framing the one way) |
| PG23 | D157's leftovers | RS8 | training and the Ideas path removed; Expand kept (Q21) |
| PG24 | hidden prompt leads | RS2, RS6 | each run form shows its lead as editable text with the default |
| PG25 | more than one model, no tile | RS2, RS6 | tiles on the crowd's loop, the stage clip, *Clean up*; Image to video on `ModelCards`; the Klein switch shown |
| PG26 | a stage made from Shots is 1920×1080 @ 24 whatever the project | RS0b | the project's format when no size is given; the differing stages listed |
| PG27 | the stage clip renders the stage's range, the final and the animatic the shot's | RS0b (interim), RS3 | now: the stage clip renders the shot's range; then one timeline (Q2b) |
| PG28 | the final's size and rate are not fields (F16 in the code) | RS6 | the shot's size and rate in Final's Output |

## 4. What each wave proves on the rig

| Wave | The check | GPU |
| --- | --- | --- |
| RS0b | one A-pose front made through the button on char01 at 2:3 (GPU, alone); a *New shot* in a 1280×720 @ 16 project gets that format; the lists of 16:9 A-poses and differing stages sent; a shot's stage clip and final cover the same frames; deleting a stage in use refused | one make |
| RS1 | stubz002's char01 and its place, and Followed's Nora and the street, opened in World › Clay; every section works as it did in Clay's Library; a pose made and saved on Nora's bench | no |
| RS2 | a shell made at 1536 and 100 000 faces against the 1024 / 50 000 default on char01: the minutes, the peak VRAM, the look — the defaults stay unless the author prefers the other | yes, alone |
| RS3 | the migration's dry run on both projects, its list sent (the scenes split, the ranges cut, the orphans); then a new shot from Shots, from the shot rail and from the Flow, each with its scene; *another angle*; a delete each way | no |
| RS4 | Followed's shot 1 set up end to end in Clay without opening Shots: the lines, the camera, the size, a Record | no |
| RS5 | Shots shows both projects' shots read-only; Play; every card opens its shot in Clay | no |
| RS6 | Followed's shot 1 processed three ways (layered, one pass, from a still) and finished in Final, each output marked; an i2v from a Bin picture refused in the shot and made in Sketches | yes, alone |
| RS7 | shot 1's process and final copied to shot 2 and run; the migration of both projects' recipe runs | yes, alone |
| RS8 | 05 §B's rows each checked off; a scene with a removed stand-in shown with its block | no |
| RS9 | the exposure audit at zero unexplained | no |
| RS10 | Followed's cut assembled from the two finished shots and rendered | CPU |

## 5. Spikes

None is needed to start: every step Process and Final need exists (02 §7). Three widen them, each with its weights read against D17 / D26 before any
download, and run alone on the GPU:

- **E67 · A scene's background in 3D from images** (the author, Q22: "we should also look into creating scene background 3D from images, if this is
  possible"). Today a background is a picture's relief (MoGe-2, a single depth surface that tears where the picture saw nothing) or the box set
  fitted from the set picture (D143). The spike first surveys, without downloading, the local ways that fit 16 GB and the EU licences: a layered
  depth picture whose hidden parts are filled with the Fills loom2 has; a single picture turned into a 3D Gaussian scene; several views of the place
  made with the reangle or a camera-orbit clip and reconstructed together; a panorama made from the set picture and lifted to depth. Each is judged
  on what Clay needs: a camera that moves a metre or two without tearing, depth for the passes, a floor the figures stand on, and the minutes. The
  survey goes to the author with its downloads listed for approval; then the measurements on Followed's street. **When:** the survey any time (no
  GPU); the measurements after RS3, on the author's word.
- **E65 · v2v straight from the animatic** (after RS7, on the author's word — Q7). Today's v2v steps read the passes (LTX IC-LoRA, Wan Animate) or a
  layer (*Clean up*). A step that redraws the lit animatic itself — Wan 2.2's VACE or Fun-Control on the pinned ComfyUI's core nodes, if v0.39.0 has
  them (no custom node, rule 2) — would be the plainest "v2v on the clay". Measured on Followed's shot 1 against E59's three ways.
- **E66 · the clip upscaler** (after RS7, on the author's word). SeedVR2's clip path was measured at 18 min and not offered (D153); a final's output
  may want it once the drafts are approved.

## 6. What is not in proto02

- Templates, presets and quick access as a feature (G3) — parked; RS8 only removes what breaks G1.
- Episode's refinement — the author's later study (01 §7).
- Several episodes in one project (Q11) — a study of its own if wanted.
- The licence-bound post-MVP items (video references / H3's own, 16-bit, ICC, sd.cpp, LTX-2.5) — unchanged in the backlog.
- The in-app fetch's stall restart (the K register's one open item).
