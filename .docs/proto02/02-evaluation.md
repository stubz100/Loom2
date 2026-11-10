<!-- markdownlint-disable MD013 MD024 -->
# 02 · Where loom2 is: the evaluation against the four steps

Written 2026-11-10 at `79ebcfc` (the working tree also holds D196, built and tested but not committed — §12). Read-only: nothing in the code was
changed. Every claim cites the file it was read from; the two inventories behind §9 and §10 are in [05](05-inventory.md).

**Method.** The shell (`frontend/src/ui2`), the parts it mounts (`frontend/src/suites/*`), the orchestrator's records and routes
(`orchestrator/loom2`), the model specs and the decision log (D157–D196) were read against the target in [01](01-application.md). Findings are
numbered **PG1–PG28** (proto02 gap) so the plan ([03](03-plan.md)) can name them; 03 §3 says where each is fixed.

## 1. The state in one table

| Area | The author wants | Today | Gap |
| --- | --- | --- | --- |
| World's modes | Make · Edit · Clay | Make · Edit (D181); the 3D is in Clay › Library | **large, but a re-housing** (PG1–PG4) |
| A character's 3D | figure, shell, skeleton, poses, all in World | figure and skeleton in Clay › Library; poses saved from a scene's pose editor | re-housing + a Poses section (PG3) |
| The shell's generation | its parameters and the model tiles shown | one button, nothing exposed (PG5) | a run form |
| *Open in Clay* / *Open in World* | gone | both present (PG2) | remove |
| Clay as the shot bench | every shot setting in Clay; a thin shot graph on top | Clay › Scenes is a stage picker; the shot's settings are in Shots' header (PG8, PG9) | **large** |
| Scene ⇄ shot | one, created together | a shot from Shots makes a stage; a stage from Clay makes no shot; deletes do not cascade (PG6) | **medium**, records + routes |
| The length | "15 s?" | 5 s default, **20 s cap** (PG7) | a constant, if changed |
| Shots | overview + the episode's order | the Flow + storyboard + the shot's levels and settings (PG10) | slimming |
| Process | v2v / i2v on the clay, chains copyable | Performance (three method cards) and Final (EffectCraft) as Shots levels; Image to video takes any picture; nothing copies (PG11–PG14) | **largest** |
| EffectCraft | "doesn't seem to be part of loom2 anymore" | **still wired and reachable** — Shots › Final, after a Layered performance (PG12) | discoverability, then the chain |
| Episode | cut + post | FilmCraft cut editor with sound and colour, reachable (§8) | none now (deferred by the author) |
| Generations | every parameter exposed | 24 of 47 jobs are a button with nothing to set; prompt leads hidden everywhere ([05](05-inventory.md) §A, PG15, PG22, PG24, PG25) | a run form per job + an audit |
| Templates | none that the tool cannot recreate | fixed recipe templates, method cards, preset sets and stand-ins, hidden preset fields ([05](05-inventory.md) §B, PG16, PG23) | remove or convert |

## 2. World

`frontend/src/ui2/world/WorldLayer.tsx` — the rail (Characters · Props · Places │ Look · Sketches), the header (entity ▾, version ▾, readiness), the
mode switch **Make | Edit** (`:181–188`), the bin as the centre, the Inspector.

- **PG1 · World has no 3D.** C0 (D181) moved Build's body, model and set to Clay's Library (`WorldLayer.tsx:24–25`, the comment). The readiness
  line still lists the pictures World makes (`readiness.ts`) and Clay's Library has its own (`ui2/clay/readiness.ts`), so an entity's state is told
  in two places.
- **PG2 · The two jumps.** World's header carries *Open in Clay ▸* (`WorldLayer.tsx:87`, command `clay.asset.open` at
  `ui2/clay/clayCommands.ts:32`); Clay's builder, its Inspector and the skeleton panel carry *Open in World ▸* (`ClayLayer.tsx:181, 201`;
  `suites/stage/RigPanel.tsx:65`; command `clay.asset.world` at `clayCommands.ts:29`). This is the "switch" the author names.
- **PG3 · A character's poses have no home of their own.** A pose is made in a scene's (or the bench's) pose editor and saved with
  *Save for ‹character›…* (`suites/stage/stageCommands.ts:126`, `StageParts.tsx:550–551`), listed read-only in the skeleton screen
  (`SkeletonBench.tsx:601`). The records are the version's (`/story/profiles/{pid}/versions/{vid}/poses/{name}`), so a Poses section needs no new
  record.
- **PG4 · The 3D already lives on the version.** The body (`CastBody`), the shell (`shell_asset_id`), the skeleton's offsets, the poses, the
  prop's model and the place's set are fields of the Cast version (`orchestrator/loom2/story.py`, `body.py`). D181 §4.6 proposed library records
  of their own (`clay/<kind>/<id>.json`); **they were not built**. So moving the 3D back to World is a UI move with no data migration.

**What is in Clay's Library today, to move** (`ClayLayer.tsx:173–242`): the Figure | Skeleton switch (D190, `:236–242`), `CastBody` with
*Make the shell ▶* (`:177–178`), `PropModel` (`CastParts.tsx`), `PlaceSetSection` (`CastSet.tsx`: *Build*, *Bake*, *Fill*, *Clear*, the set
picture), *Make the shells (n)* (`:132–148`), *Bench ▶* and *Line-up ▶* (`:117`, D142), the skeleton bench and its parts (`:221–229`). The bench is
Clay's own engine on a bench stage (`clayStore.ts:100–108` → `stageStore.openBench`), so it can be mounted in World's centre as it is mounted in
Clay's.

## 3. The 3D generations

- **PG5 · The shell is a button.** *Make the shell ▶* (`suites/story/storyCommands.ts:461–464`) posts to
  `/story/profiles/{pid}/versions/{vid}/shell`, which submits `{"kind": "image_to_mesh", "asset_id", "model_id"}` and nothing else
  (`orchestrator/loom2/routes/story.py:552`). The recipe takes **resolution** (1024 | 1536), **faces** (2000–700 000, default 50 000) and **seeds**
  (`recipes.py:428–438`); none reaches the UI. The prop's model (`routes/story.py:659`), an idea's shell (`ideas.py:426`) and a set's moving thing
  (`place_things.py:249`) are the same. *Make the shells (n)* queues them all at once with the same nothing (`ClayLayer.tsx:138–145`).
- **One model.** `pixal3d-int8` is the only spec with `recipes.mesh` (`models/specs/pixal3d.toml`). TripoSR was dropped and its files deleted (D136
  U5), Hunyuan3D is excluded by its licence (rule 7), TRELLIS.2 appears only as Pixal3D's VAEs. So the author is right: there is no other model
  today. The form still shows the one tile, so the model is named and a second one has a place to land.
- **The set's relief** (`image_to_set`, MoGe-2) is submitted with the lens and the relief settings from the stage route (`routes/stages.py:374`)
  but with the source only from the place's set route (`routes/story.py:785`).

## 4. Clay today

`frontend/src/ui2/clay/ClayLayer.tsx` — the rail **Library · Scenes** (`:40`).

- **Library** — the kinds Figures · Props · Sets · Lights · Cameras · Animations (`clayStore.ts:17`). Lights and Cameras are a note ("added in a
  scene", `:84–91`); Animations is the workshop (D182, `AnimationsGrid.tsx`). The three entity kinds are World's entities' 3D (§2).
- **Scenes** — a header with a picker of every stage of purpose `stage` (`:254–276`), *New stage…* in it (`:263`), the scene's length, *← Back to
  the shot* when opened from one; the column of the scene editor (Scene · Motion · Camera · Still, `StageParts.tsx:197–217`), the viewport, the
  tracks, the Inspector; the foot *Render passes ▶* and Record (`StageParts.tsx:289–305, 1267–1270`).
- **PG8 · Clay is not shot-shaped.** It opens a stage, not a shot: the header names the stage and lists the shots on it, a stage picked from the
  menu has "no shot to go back to" (`:262`), and the shot's own settings are not here (§6).
- **PG9 · Settings that are nobody's.** The Still form (method, model, image 1, the references, the prompt, Draft | Full, the count) and the stage
  clip's settings are client state (`stageStore.ts:121, 404, 564`): reset when a stage opens, kept per shot only once a job has recorded them. The
  Image to video panel is kept per browser (`animateStore.ts:469`).

## 5. A scene and a shot

There are **two things called "scene"**: Clay's scene is a stage (`stages/<id>.json`, `stages.py:353–373`); the Flow's scene is a scene group
(`scn_*` in `story/flow/scenes.json`, `story.py:631–642`) with words of its own and an optional `stage_id` set only while empty
(`story.py:1914–1922`). A shot version points at a stage, a camera, a stage revision and its own range (`story.py:348–370`).

- **PG6 · Created together one way only.**
  - *＋ New shot* in Shots makes the node, a scene group, a stage (the place's built set from its picture's camera, else empty) and a camera in one
    call (`ui2/shots/shotsStore.ts:265–281` → `routes/story.py:2327–2341` → `story.py:2054–2115`, `stages.py:576–594`).
  - *New stage…* in Clay makes a bare stage and no shot (`ClayLayer.tsx:263` → `stageCommands.ts:47–48` → `routes/stages.py:73–80`); the header
    then says "no shot on it yet" (`:273`). A camera's *New shot from this camera…* makes a shot node outside every route with no scene group
    (`stageCommands.ts:98–101` → `story.py:1188–1205`).
  - The Flow's *Add Shot*, *Make the Flow from the spine*, *Duplicate node* and a deleted shot leave a shot with no stage ("No scene yet",
    `ShotsLayer.tsx:116`).
  - Deleting a stage leaves its shots pointing at it (`stages.py:820–826`); deleting a shot leaves its stage and camera.
- **Coverage** works: *New shot in the same scene*, *Same scene as…*, *New Shot from this Shot* (`shotsCommands.ts:46–49`, `ShotHeader.tsx:123`,
  `story.py:2221–2265`); one camera serves one shot (a taken camera is copied, `story.py:1286–1293`).
- **D181 Q3 was not built:** no `shots/<nn>/scene.json`; bench, line-up and animation-bench stages remain stages with a `purpose`
  (`stages.py:312, 552–653`), kept out of the pickers by a filter (`clayStore.ts:187`, `routes/stages.py:33–37`).
- **PG27 · Two ranges.** The stage's range (Clay's timeline) and the shot's range (Shots' header) both exist; the stage clip renders the stage's
  (`stageStore.ts:694`), the final and the animatic the shot's (`finalShot.ts:89–94`, `animatic.ts:18`).
- **PG7 · The length is 5 s by default and 20 s at most** — `SCENE_SECONDS_DEFAULT = 5`, `SCENE_SECONDS_MAX = 20`
  (`suites/stage/sceneLength.ts:4–5`), the project default `ProjectRecord.scene_seconds` `ge=1, le=20` (`workspace.py:52`), checked in
  `stages.check` (`stages.py:469–477`) and on the shot's range (`routes/story.py:1637–1654`). It was answered as D181 Q4 (2026-11-03: "5 s default,
  20 s cap"). **15 s was never recorded.**
- **PG26 · The size disagrees by path.** Clay's *New stage…* uses the project's format (`routes/stages.py:77–78`); a stage made by *New shot* or a
  re-scene gets 1920×1080 at 24 fps written in the code (`stages.py:589, 668`).

## 6. Shots today

`frontend/src/ui2/shots/ShotsLayer.tsx` — the storyboard strip on top (cards with Clay · Performance · Final dots, *＋ New shot*, *▶ Play*), the rail
**Flow · Clay · Performance · Final · Graph** (`shotsStore.ts:12–15`), the shot header and the level's column.

- **PG10 · Shots is where a shot is set up.** The header (`ShotHeader.tsx:100–167`) holds the version menu, the description, the lines and voices,
  the scene menu, the camera menu, the range, *Extend to the lines*, the cast, and the animatic, performance and final rows; `ShotWords.tsx` the
  words. The Flow's Inspector holds more (`StoryParts.tsx:893–990, 1206–1254`): the source, the linked stage, *Make frame ▸*, *Make clip ▸*, the
  recipe template select, *Run stale*, the S2V lip-sync block.
- The rail's *Clay* is a jump to the Clay layer (`shotsStore.ts:177–184` → `clayStore.openScene`); Performance and Final are Animate's old suites
  mounted on the open shot (`ShotsLayer.tsx:28–35`), shown only when the shot has a stage (`:116, 131`).

## 7. Performance and Final — and EffectCraft

**The methods** are `layered | one_pass | start_still | speaking` on the shot version (`story.py:367`); the ledger's menu offers three
(`shotsStore.ts:114–115`) and maps them to Performance's cards Final shot / Stage clip / Image to video (`:61–66`).

| Method | The card | What it runs | From the clay? |
| --- | --- | --- | --- |
| Layered | Final shot (`FinalPanel.tsx`) | the plate (projected · filled · generated by LTX on the depth · a picture · the set), each figure by Wan Animate in 77-frame batches in its window, matted, identity-checked; props, shadows; *Assemble*, *Make the composition*, *Render* | yes |
| — the hybrid (D184) | inside Layered | a figure not marked *exact* rides on the generated plate (`FigureBinding.tsx:58–59`, `finalShot.ts:97–107`) | yes |
| One pass | Stage clip (`StageParts.tsx:732–813`) | LTX-2.3 IC-LoRA on depth or pose from a start still with anchor beats, or Wan Animate | yes |
| From the start still | Image to video (`AnimateSuite.tsx:44–236`) | Wan 2.2 I2V, Fun-Camera, LTX-2.3, H3 from start / end slots | **any picture in the Bin** (PG13) |
| Speaking | — | Wan 2.2 S2V | in the record, **not in the menu** (PG14) |

- **PG11 · Performance and Final are two levels of another layer**, with the method as three cards on the page, the recipe template select and a
  stage picker that opens any stage whatever the shot (`ShotStepper.tsx:69–87, 120–129`). D181 §5 said these go; they did not.
- **PG12 · EffectCraft is in loom2.** The Final level is EffectCraft's compositor (`suites/animate/FinalSuite.tsx`, `FinalEditor.tsx`): Layers
  with Properties / Masks / Effects (21 tiles, `Effects.tsx:15–38`) / Passes (*Clean up* — Wan 2.2 low-noise v2v; *Creative* — LTX; *Face*; *Lip-sync*;
  on a layer or on everything below as a processing layer, `FinalEditor.tsx:151–251`, `routes/finals.py:957–1084`); Voice and lip-sync; Output (the
  render settings, *Render the finished shot ▶* on effectcraft-cli on the CPU). The sidecar is pinned (`engine/effectcraft.pin.json`, v0.12.0,
  `scripts/build_effectcraft.py --check`), the session in `orchestrator/loom2/effectcraft.py`, the routes in `routes/finals.py:1244–1513`. **No
  decision removed it** (D157 keeps D110–D114; D159 removed only the Catalogue and the old shell). Why it reads as gone: it is reached only through
  Shots › Final, which needs a shot with a stage and a composition, which is made only by *Make the composition* after a Layered performance —
  the One pass and From the start still methods never reach it.
- **PG13 · A clip without clay.** Image to video takes its start and end from any picture (`AnimateSuite.tsx:44–110`); Fun-Camera, LTX and H3
  likewise. S2V takes any picture (`routes/story.py:2683–2730`). Against G4.
- **PG28 · The final's size and rate are not fields.** The layers render at Wan Animate's short side at the project's aspect (848×480 at 16:9) and F16
  (`finalShot.ts:339–348`, `stageCommands.ts:191`), RIFE to 24 at the render (`finalShot.ts:20–32`); D181 / P16 asked for fields.

## 8. Episode

`ui2/episode/EpisodeLayer.tsx` mounts the FilmCraft cut editor (D126; `suites/story/episode/*`) beside the route's finals with their states. Reachable
and working: *Assemble from the Flow*, *Assemble again*, *Update to the approved take*; the cut tools (select, ripple, roll, slip, slide, razor,
speed, freeze, dissolves, dips); the channel strip and VST3 chains (D127, `StripControls.tsx`, `EffectPicker.tsx`); the grade with *Match to…*
(`GradeControls.tsx`); captions; *Export for Resolve*, EDL, FCPXML, SRT; *Render draft*, *Render the movie* (H.264 or ProRes). The pins are checked in
CI (`build_filmcraft.py --check`, `build_vsthost.py --check`). Nothing here blocks proto02; the author defers its refinement.

## 9. The generations and their parameters

[05](05-inventory.md) §A lists every job kind the queue runs: what it makes, its models, where it is launched and what the author can set.

- **PG15 · Buttons that run with parameters nobody sees.** The pattern is the same everywhere it occurs: the recipe has parameters, the route or the
  store submits a fixed subset, and the button has no form. Of the 47 rows in 05 §A, **24 are a button with nothing to set** (five of them CPU work:
  the bake, the passes, the assembly, the conform, the animatic) and 11 more set only part of what runs. The heaviest, by how often they run: a character layer's performance by Wan Animate (A31: the preset, the prompt's tail, the
  window, the batches, the pose strength — the seed only by re-taking), the shell and every other Pixal3D job (A11–A14), the body fit (A15), the
  plate's three automatic paths (A28–A29), the face pass (A34), the matte (A32), the turn test (A39).
- **PG22 · Two A-pose makes that disagree.** Make's reference framing makes a 2:3 portrait (D177, `F/ui2/world/make.ts:64–72`); the buttons
  *Make reference candidates ▶ / back / side* send 720 px tall at the project's 16:9 (`O/routes/story.py:413–415`), two at seeds 0 and 1, Draft —
  the frame D177 was decided against (Ines cut at the thighs).
- **PG24 · Hidden words in the prompts.** Fixed lead sentences are added to the stage still, the plate, a character's performance, the passes, the
  face pass, lip-sync, the reangle, the turn test, the Fills, the crowd and the clean (05 §B22–B25). *Show the words* shows some after the fact;
  none can be changed before the run.
- **PG25 · More than one model, no tile.** The crowd's and walkers' loop always runs the i2v default though LTX and H3 also do first–last frame
  (A21); the stage clip's model is fixed per method (A38); *Clean up* runs the first Wan spec (A33); Image to video picks from its own grid, not
  ModelCards (A37); the hand and feet chips switch the model to Klein by themselves (A3).
- The surfaces that already meet G2 are the ones built since D160 / D186: World's Make (the model cards, the settings, the count, the seeds), Edit's
  AI tab, the Image to video panel, Clay's Still. They are the pattern for the rest.

## 10. The templates

[05](05-inventory.md) §B lists every template, preset and canned option set, with whether the author can make, edit and remove their own and whether
it could be made with the tool's commands.

- **PG16 · Templates the tool cannot recreate.** Of the 45 rows in 05 §B, the ones that fail G1:
  - the **recipe templates** — a fixed server list `i2v`, `stage`, `clay1`, `clay2`, `dialogue` (`orchestrator/loom2/shot_recipe.py:76–95`),
    chosen per shot version and steering *Run stale* (B10);
  - the **performance methods** as three cards (B12), and the layer passes' four presets (B29) — step kinds dressed as presets;
  - the **video presets** whose split, low-expert CFG and LoRAs no field reaches (B13), the stage still's methods (B41);
  - the **baked prompt leads** (B22–B25);
  - the **A-pose buttons' make** (B7) and the reference chips' side effects (B6);
  - the **stage's preset sets and stand-ins** — room, street, deck; crate, stool, table, pole, block — fixed geometry nothing in loom2 can model
    (B20);
  - leftovers of D157 (Expand's coverage presets, the LoRA check, the training lists; B8, B9, B39).
- **PG23 · Leftovers of earlier decisions.** D157 took Expand and LoRA training out: Expand is still reached through Image's Poses section in
  World › Sketches (`F/suites/generate/Poses.tsx`), training through the palette (`story.cast.train`, `storyCommands.ts:567–569`); the Ideas board's
  *Make the clay ▶* is code no layer mounts (`ideasStore.ts:76`); the Bin's *set* verb makes a set from any picture on a stage, outside any place
  (`verbs.ts:33`, A18).
- **What already complies.** The author's own saved things are made with the tool's commands and pass G1: saved poses and a character's poses,
  stage templates (`/project/stage-templates`), shot templates (`story/shot_templates.json`), Image to video presets (`/project/animate-presets`),
  the author's animations (D182).

## 11. Half-wired and drifting

From the reading, beside the PG items:

| # | What | Where |
| --- | --- | --- |
| PG17 | the stage picker in Performance's / Final's Shot section opens any stage, whatever the shot | `ShotStepper.tsx:69–87` |
| PG18 | *New shot in a new scene* and *in the same scene* are still two entries (D181 asked for one sheet) | `shotsCommands.ts:43–49` |
| PG19 | the Flow's scene group and the shot's stage can drift apart (the group's stage is set only while empty) | `story.py:1914–1922` |
| PG20 | a stage can exist with no shot; a deleted stage leaves shots pointing at it; a deleted shot leaves its stage | §5 |
| PG21 | nothing copies a shot's processing to another shot: *New Shot from this Shot* copies the recipe template's id only; compositions, passes and render settings are per final | `story.py:2246`; `compositions.py:414–458` |

## 12. The working tree and the checks

- **Uncommitted when read:** D196 (a shell's sole and leg stance; journal 2026-11-08 15:42) — 18 files changed and five new, its checks green
  (offline 894, Vitest 811, e2e 92 / 92), the author's look in Clay owed. **Committed 2026-11-10 as `36acbf3`** on the author's answer to
  [04](04-questions.md) Q14, after offline 894 and Vitest 811 + 3 skipped were run again.
- **The checks every wave keeps green** (CLAUDE.md): offline ≈ 894, Vitest ≈ 811, typecheck + build, lint (63 warnings as before), the settings audit
  (326 / 0), model literals 0, agents 0, the API contract, the e2e 92 / 92 alone (≈ 7.5 min). The e2e scenarios drive today's layout; every wave that
  moves a part ports the scenarios that reach it (C0's port took twenty-one).
