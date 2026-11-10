<!-- markdownlint-disable MD013 MD024 -->
# 05 · The inventory: every generation and every template, against G1 and G2

Written 2026-11-10 at `79ebcfc`, read-only; the verdicts amended the same day to the author's answers ([06](06-answers.md): A4, A18, A36, A37,
A40, B8, B20). §A lists every job the queue runs (the 19 recipe kinds of `orchestrator/loom2/recipes.py:625`, by the
surface that launches them) and the CPU / client makers beside them; §B every template, preset or canned option set the author sees. Each row ends
with its **verdict** against the author's guidelines ([01](01-application.md) §9.1) and the wave of [03](03-plan.md) that acts on it.

Paths: **O/** `orchestrator/loom2/`, **F/** `frontend/src/`, **S/** `orchestrator/loom2/models/specs/`, **DL** the decision log's line.

**Verdicts.** *ok* — meets the rule. *expose* — the parameters exist in the recipe or the code and get a run form (G2). *tile* — more than one model
could run it; the model tiles go on its form. *convert* — the template becomes an ordinary item the author can see, edit and remove. *remove* —
fails G1 or is a leftover of an earlier decision. *model's own* — the vocabulary is the model's (a LoRA's moves, a node's presets), not a template.
*parked* — quick-access machinery, left as it is (G3).

**One model today** (so the form shows one tile): mesh — `pixal3d-int8`; set — `moge2-vitl`; keypoints — `sdpose-wholebody`; pose-driven video —
`wan22-animate-fp8`; lip-sync — `wan22-s2v-fp8`; depth-guided video — LTX-2.3 (the only spec with `guide_lora`); instruct — `qwen-edit-2509`;
SAM 3. **Where ModelCards is used today:** World's Make (`F/suites/generate/GenerateColumn.tsx:450`), Edit's AI tab (`F/suites/edit/EditSuite.tsx:551–602`),
the Angle sheet (`AngleTab.tsx:62`), Clay's Still (`F/suites/stage/StageParts.tsx:669`), the plate (`FinalPanel.tsx:225`), the set's Fills
(`F/suites/story/CastSet.tsx:31`), the rig pictures (`RigPanel.tsx:140`), Settings (`F/frame/SettingsModal.tsx:74`).

## A. The generations

### A.1 World — pictures

| # | Job | Models · tiles? | Launched from | The author sets | Fixed in code | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | t2i — Make's *Give ‹X› a look ▶*, Sketches' *Make n sketches ▶* | every t2i spec · **yes** | `F/ui2/world/WorldMake.tsx:103–105`, `WorldSketches.tsx:53–55`, the Bin's Re-run / Variations | the prompt (tree / JSON / text), framing words, references, the Look, the camera, the model, steps, guidance, CFG, sampler, scheduler, turbo, dtype, encoder, shift, tiled VAE, size, count, seeds | panel defaults only | **ok** — the pattern for the rest |
| A2 | t2i — the A-pose / back / side / prop view / set picture **buttons** (*Make reference candidates ▶*) | the Make card if it takes references, else Klein 9B · no tile on the button | `F/suites/story/CastParts.tsx:100–102` (World via `WorldRefs.tsx:61`); `storyCommands.ts:394–395, 465–468, 520–521` | nothing | count 2 (`storyStore.ts:705`); **720 px tall at the project's 16:9** (`O/routes/story.py:413–415`) — not D177's 2:3; seeds 0..n−1; Draft; the sheet plus a fixed sentence (`O/story.py:1033–1059`) | **remove** the buttons — Make's reference framing (A1 with the chip on) is the one way, and already makes 2:3 (`F/ui2/world/make.ts:64–72`) · RS2 |
| A3 | t2i — the hand and feet pictures | any t2i · **yes** (`RigPanel.tsx:140`) | the skeleton panel; Make's framing chip; Sketches' chips | words, model, count 1–4 | 1024² (`O/story.py:1030`); seed i; the framing chips **switch the model to Klein** (`WorldMake.tsx:51–52`, `WorldSketches.tsx:34`) | **expose** — the switch shown as the card changing, the author's to undo (D190) · RS2 |
| A4 | t2i ×N — Expand (coverage cells) | the panel's model | Image's Poses section, reached only in **Sketches** (`F/suites/generate/Poses.tsx:33–44`) | cells, expressions, all of A1 | the cell vocabulary (`O/story.py:785–815`) | **ok** — kept in Sketches as a free tool (the author, Q21), though D157 took it out of World |
| A5 | t2i — the Look's style sample | Settings › Samples · tile in Settings, not at the use | `story.world.styleSample` (`storyCommands.ts:229–243`) | the sample scene | 768 px, seed 90 (`styleSamples.ts:10–12, 68–70`) | **expose** — model, size, seed on the Look · RS9 |
| A6 | t2i — preset swatch icons | the sample model | PresetPanel → `swatches.ts:49` → `O/routes/preset_icons.py:42–57` | the swatch scene (Settings) | seed 90, 256 px (`O/preset_icons.py:30–31`) | **parked** (G3) |
| A7 | t2i ×8 — the LoRA identity check | the LoRA's base | `storyCommands.ts:572–574` — no mounted surface | nothing | cells, seeds 1001+i, 544 tall | **remove** with A42 (D157) · RS8 |
| A8 | t2i → keypoints → mesh — Ideas' *Make the clay ▶* | the card or Klein | `F/suites/story/ideasStore.ts:76` — not mounted in the shell | the model | 720 tall 16:9, seed 0, a fixed prompt (`O/ideas.py:318–333`) | **remove** (dead path since D157 folded ideas into Sketches) · RS8 |
| A9 | i2i · inpaint · outpaint · instruct · upscale · segment — Edit's AI tab | **yes**, per operation | World's Edit; the Bin's Open / Upscale in Edit / Select subject | mode, prompt, refs, encoder, LanPaint order, margin, sizes, feather, expand, blend, grow, strength, source, match colour, tiled refine, count, seed | I2I `steps` (`O/recipes.py:128`), Inpaint / Instruct `max_pixels` (`:155`, `:357`); SeedVR2 ×2 only, one step (D153) | **expose** the three fields · RS9 |
| A10 | reangle — *New angle* | **yes** (`AngleTab.tsx:62`) | the Angle sheet, the Bin, Edit | move, method / model, sentence, count | the five moves (`generateStore.ts:278–282`) | **ok** (the moves are *model's own*) |

### A.2 World — the 3D (today in Clay › Library; World › Clay after RS1)

| # | Job | Models · tiles? | Launched from | The author sets | Fixed in code | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| A11 | image_to_mesh — **the character's shell** | `pixal3d-int8` only · no | *Make the shell ▶* (`ClayLayer.tsx:178`, `storyCommands.ts:461–464`), *Make the shells (n)* (`ClayLayer.tsx:132–148`), the skeleton panel, a ghost figure; **queued by itself after a body fit** (D183, `O/engine/finishers.py:985–987`) | **nothing** — the route has no body (`O/routes/story.py:527–556`) | resolution 1024, faces 50 000, seed 0 (`O/recipes.py:436–438`); `/capabilities.mesh` publishes [1024, 1536], unused (`O/capabilities.py:296`) | **expose + tile** — resolution, faces, seeds, the source; kept on the version so the automatic run uses them ([04](04-questions.md) Q16) · RS2 |
| A12 | image_to_mesh — the prop's model | Pixal3D · no | *Make the 3D model…* (`storyCommands.ts:505–511`) | nothing (the source: the reference, else the hero) | as A11 | **expose + tile** · RS2 |
| A13 | image_to_mesh — the Bin's *Make a 3D prop…* | Pixal3D · no | `F/ui2/bin/binCommands.ts:148–159` | nothing | as A11 | **expose + tile** · RS2 |
| A14 | image_to_mesh — a set's things that move | Pixal3D · no | `PlaceThingsSheet.tsx:145–147`; the stage's *Make the things* (`thingsStore.ts:107`) | nothing | recipe defaults | **expose + tile** · RS2 |
| A15 | keypoints — **the body fit** | SDPose · no | *Fit the body…*; **by itself** when the front is picked on an untouched body (`O/routes/story.py:1245–1249`) | nothing (drags refit on the CPU) | boxes on, inset 1.0, matte off (`O/recipes.py:518–521`) | **expose** behind the form's "more", or allow-listed with its reason (a measurement, not a picture) · RS9 |
| A16 | keypoints — the hand / feet read | SDPose + BiRefNet · no | by itself on the pick; *Read the hand ▶ / feet* | nothing | boxes off, the insets, matte on (`O/story.py:902–911`) | as A15 · RS9 |
| A17 | image_to_set — **the place's *Build the set ▶*** (MoGe-2) | `moge2-vitl` · no | `CastSet.tsx:93` → `setBuilder.ts:67–73` | the camera height; after the fit the kind, sizes, parts | lens = MoGe's reading, relief `cut`, decimation 2 (`O/recipes.py:449–451`, `O/routes/story.py:785`) | **expose + tile** — lens, relief (cut / sheet), decimation · RS2 |
| A18 | image_to_set — a stage's set from any picture (the Bin's *set* verb), rebuild | MoGe-2 · no | `F/ui2/bin/verbs.ts:33` → `stageStore.ts:1071–1105` | the lens | relief `cut` (`stageStore.ts:1091`) | **expose** — kept as a scene's background from an image (the author, Q22): lens, relief, decimation · RS9 |
| A19 | the set's bake (client, CPU) | — | by itself after a fit; *Bake again ▶* | nothing | texel per kind (`setBake.ts:28`, `O/place_sets.py:33–39`) | **expose** the texel · RS2 |
| A20 | inpaint — the set faces' Fills | **yes** (`CastSet.tsx:23–34`) | *Fill … ▶* per face | model, material per face | expand 6, feather 8, seed per face; the prompt's lead (`O/place_sets.py:155–181, 286–287`) | **expose** the lead, expand, feather, seeds · RS2 |
| A21 | i2i + i2v — **the crowd** on a face | refine: the set's card; the loop: the i2v default (Wan) · **no**, though LTX and H3 also do first–last frame | the face row's *Crowd ▶* (`CastSet.tsx:204–213`) | from / to metres, "who is there" | strength 0.6, match colour, the people and motion words, 81 f at 16 fps, Draft, seed not sent (`O/place_sets.py:43–47, 559–560, 640–650`) | **expose + tile** · RS2 |
| A22 | inpaint + i2v + matte — **the walkers** (experimental) | as A21 + SAM 3 | `CastSet.tsx:239–249` | from / to, words | feather 4, 0.75×1.9 m, spacing 1.9 m, `person:20`, threshold 0.4 (`O/place_sets.py:48–57, 687`) | **expose + tile** · RS2 |
| A23 | segment (SAM 3 points) — pick a thing | SAM 3 | the things sheet's canvas | the points | threshold 0.5, refine 2 (`O/recipes.py:214–215`) | **ok** (interactive); threshold exposed in RS9 |
| A24 | inpaint — the set picture cleaned under its things | the set's card; the stage path **no model_id** (`O/routes/stages.py:504`) | `storyCommands.ts:532–537` | nothing | the clean prompt, feather 8, grow 14 (`O/place_things.py:28, 282, 344`; `O/set_things.py:25`) | **expose + tile** · RS2 |
| A39 | i2v — the turn test | Wan Animate · no | *Test in motion ▶*, `CastParts.tsx:104` | confirm only | 77 f at 16 fps, the prompt, Draft, seed 0, pose 1.0 (`O/routes/story.py:1217–1219`) | **expose** · RS2 |

### A.3 Clay and Process — the shot

| # | Job | Models · tiles? | Launched from | The author sets | Fixed in code | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| A25 | the passes render (client) | — | *Render passes ▶* (`StageParts.tsx:657`), the guide's *Render sequence*, the final's layers | the still's tier (Draft 720 / Full) | the pass set and colours (`passes.ts:6–13`) | **expose** the size and rate as the shot's (RS4) |
| A46 | the animatic, *Record ▶* (client) | — | Record mode (`stageCommands.ts:202–206`) | indirectly: range, tier, fps | the beauty render (`animatic.ts:24–55`) | as A25 · RS4 |
| A26 | stage_shot — **Clay's Still** | **yes** (`StageParts.tsx:669–671`) | the Still section, *Render frame ▶* | method, model, references, prompt, Draft / Full, count 1–4 | the lead sentences and negative (`O/engine/graphs.py:1109–1117`); exact pose 30 steps, CFG 4, the pose LoRA (`S/klein.toml:59`) | **expose** the lead, steps, CFG; keep on the shot (PG9) · RS6 |
| A27 | stage_shot — the plate's still | **yes** (shared with the Still) | `FinalPanel.tsx:129, 159` | model, the Still's prompt and refs | seed 0, 720 short side, `PLATE_LEAD`, beats every 5 s (`O/finals.py:28–32, 619–623`) | **expose** · RS6 |
| A28 | i2v (LTX + IC-LoRA) — the plate generated along the path | LTX-2.3 · one | the plate's method chip (`FinalPanel.tsx:122–123`) | the choice only | Draft, depth 1.0, 8k+1 f, lead + tail, beat strength 1.0 (`O/finals.py:29, 33, 557–603`) | **expose** · RS6 |
| A29 | inpaint — the plate's keyframe Fills | the plate's card if it fills, else the default | by itself from the client (`fillPlate.ts:144`) | heal on / off | expand 48, feather 32 (D135); the keyframe thresholds; the method chosen by itself (`finalShot.ts:74, 80–85`) | **expose**, the choice shown with its reason · RS6 |
| A30 | *Make the final shot…* (the layers split) | — | `FinalPanel.tsx:242` | confirm; *exact* per figure | **rate 16** (`stageCommands.ts:191`, `finalShot.ts:710`); size from Wan Animate's spec | **expose** — the Output's size and rate (P16) · RS6 |
| A31 | i2v (Wan Animate) — **a character layer's performance** | `wan22-animate-fp8` · one | *Perform* / *Re-take* (`FinalPanel.tsx:130, 160–162`), *Perform the owed layers ▶* (`shotsCommands.ts:32–35`) | the seed only by re-taking | Draft; the sheet + back words + tail (`O/routes/finals.py:516`); window 480×848; 77-f batches, carry 5; pose 1.0; the front / back / side reference picked by itself (`O/finals.py:26–27, 266, 382, 626–634`) | **expose** — the most-used hidden job · RS6 |
| A32 | matte_sequence — a character's matte | SAM 3 (BiRefNet under `open`) | by itself; *Matte it again* | nothing | text `person`, threshold 0.4 | **expose** · RS6 |
| A33 | layer_pass — *Clean up* / *Creative* | Clean up = the first Wan spec; Creative = LTX · no | Final › Passes (`FinalEditor.tsx:204–221`) | preset, strength 0.02–0.9, this layer / everything below | `PASS_PROMPT` (`O/engine/graphs.py:1526`) | **expose + tile** · RS6 |
| A34 | layer_pass — **the face pass** | Wan Animate · one | the Face tile, the owed run | the head boxes (D165) | strength 0.10, `FACE_PROMPT`, crop 512, the size band (`O/owed.py:22–26, 110`; `O/heads.py:15–20`) | **expose** · RS6 |
| A35 | layer_pass — lip-sync (S2V head → Wan Animate head, LatentSync) | three · the "mouth" choice | `FinalEditor.tsx:27, 209–218` | the mouth; a line attached | the prompts; 77-f windows; LatentSync 25 fps, 20 steps (`O/lipsync.py:27–28`) | **expose** · RS6 |
| A36 | i2v (S2V) — the shot-level talking head (*Speaking*, experimental) | S2V · one | the Flow Inspector's LipsyncBlock (`StoryParts.tsx:929`) | the line, draft / fast | the prompt, `stage: true`, ≤ 77 f, 16 fps | **expose** — kept as Process's *Speaking*, marked experimental (Q12), its start a still from the shot's clay · RS6 |
| A37 | i2v — Image to video (*From the start still*) | Wan, Fun-Camera, LTX, H3 · **its own grid**, not ModelCards | `AnimateSuite.tsx:321, 342–356` | start / end, prompt, motion chips, negative, beats, preset, camera move and speed, steps / CFG / shift, tier, size, frames, fps, seed, count | the preset's split, low-expert CFG, LoRAs (`O/engine/graphs.py:316`); the stock negatives; **any picture as the start** | **expose + tile**; in a shot the start restricted to the shot's clay (G4); the free panel moved to World › Sketches (Q8) · RS6 |
| A38 | i2v — the stage clip (*One pass*) | the method's model · **no pick** (IC-LoRA or Wan Animate) | `StageParts.tsx:773–813` | method, guide, start still, prompt | Draft, guide 1.0, seed 0; the anchors by themselves (`stageStore.ts:743–762`) | **expose + tile** · RS6 |
| A40 | i2v — *Extend* a clip (experimental, D88) | the clip's own | `animateCommands.ts:151, 183–195` | the prompt | everything else copied from the clip | **expose** — kept as Process's *Extend*, marked experimental (Q12); the step says its frames past the scene read no clay · RS6 |
| A41 | tts — voice a line, a node, the episode | Kokoro or Qwen3-TTS by the voice's tier · no tile | 🎙, *Voice all lines* (`ShotHeader.tsx:141`); voices in World's Inspector | the voice; a new voice's tier, Kokoro voice, reference clip, transcript, consent | **speed 1** (`storyStore.ts:942, 951, 959`; the API allows 0.5–2) | **expose** the speed, the model shown · RS4 |
| A43 | assemble_final (CPU) | — | `FinalPanel.tsx:196–198` | nothing | RIFE v4.6 from F16 to 24 by itself (`O/engine/finishers.py:1461–1483`) | **expose** the rate in Output · RS6 |
| A44 | comp_render (EffectCraft, CPU) | — | `FinalPanel.tsx:204–206` | the render settings (`RenderSettingsBlock.tsx`) | — | **ok** |

### A.4 Episode, and the rest

| # | Job | Verdict |
| --- | --- | --- |
| A42 | train_lora — reachable only from the palette (`story.cast.train`, `storyCommands.ts:567–569`), its block not mounted in the shell; lr and seed fixed | **remove** the palette reach — D157 took LoRA training out (Q21) · RS8 |
| A45 | render — the cut's draft, the movie (delivery, captions), the conform (no parameters, by itself on Assemble) | **ok** for now — Episode is deferred |
| A47 | CPU makers with no model — frame extract, animation thumbnails, clay views, the unturned shell copy, guide videos | **ok** |

## B. The templates, presets and canned option sets

| # | What | Where | Holds | The author's own? | Recreatable? | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | the prompt fields' vocabulary (field presets) | `O/library_seed.json` seeded per project (`O/library.py:94–96`) | scenes, actions, poses, styles, light, mood, background, composition, camera | **yes** — save, edit, remove | yes (words) | **ok**, *parked* (G3) |
| B2 | swatch scenes and seed | `O/config.py:179–189`, `O/preset_icons.py:30–31` | a scene per field, seed 90, 256 px | scenes yes | yes | *parked* |
| B3 | preset glyphs | `F/frame/presetGlyphs.tsx` | icons | — | cosmetic | **ok** |
| B4 | the style sample's defaults | `O/config.py:178`, `styleSamples.ts:10–12` | prompt, seed 90, 768 px | prompt yes | yes | **expose** (A5) · RS9 |
| B5 | the class framings | `F/ui2/world/make.ts:7–23` | three per class | words editable | yes | **ok** |
| B6 | the reference framings and their sentences | `make.ts:29–34`, `O/story.py:1033–1059`, `O/hands.py:141–144` | A-pose front / back / side, hand, feet, prop view, set picture | words editable (D169) | **partly** — the chip also sets 2:3 or 1024², forces Klein for parts, routes to the candidates | **expose** what the chip sets, as fields · RS2 |
| B7 | the A-pose buttons' baked make | `storyStore.ts:705`, `O/routes/story.py:413–415` | count 2, 16:9 at 720, seeds 0..n | no | approximately, through B6 | **remove** (A2) · RS2 |
| B8 | Expand's coverage presets | `O/story.py:785–815`, `Poses.tsx:43` | five presets over a fixed vocabulary | cells one by one | cells yes (a preset is a pick of cells) | **ok**, *parked* — Expand kept in Sketches (Q21) |
| B9 | the LoRA check's cells | `O/routes/story.py:1414–1415` | four cells | no | no | **remove** (A7) · RS8 |
| B10 | **the shot recipe templates** | `O/shot_recipe.py:76–95` | `i2v`, `stage`, `clay1`, `clay2`, `dialogue` | select only | **no** | **remove** — the chain replaces them · RS7 |
| B11 | shot templates | `O/routes/story.py:2190–2247` | nothing ships | **yes** | yes | **ok** |
| B12 | **the performance methods / cards** | `O/story.py:367`, `shotsStore.ts:63–66, 114–115`, `AnimateSuite.tsx:285–289` | Layered, One pass, From the start still (+ Speaking) | no | no | **convert** — the chain's Generate step kinds, each with its form · RS6 |
| B13 | the video presets in the specs | `S/wan22.toml`, `S/ltx23.toml`, `S/h3.toml` | draft / motion / quality / fast: steps, split, CFG high / low, shift, LoRA on / off | pick; steps / CFG / shift overridable | **partly** — split, low CFG, the LoRAs not settable | **expose** — a preset fills fields the author can change · RS6 |
| B14 | Image to video's saved panels | `O/library.py:243–292` | nothing ships | **yes** | yes | **ok** (Q18) |
| B15 | Make's saved panels | `O/library.py:187–212` | nothing ships | **yes** | yes | **ok** (Q18) |
| B16 | stage templates | `O/library.py:266–286` | nothing ships | **yes** | yes | **ok** (Q18) |
| B17 | the built-in poses and their words | `F/suites/stage/builders.ts:15–27`, `poseWords.ts:3–6` | ten poses | own poses yes; built-ins not deletable | yes (joints + Save) | **ok** |
| B18 | the hand presets | `F/suites/stage/detailed.ts:34` | open, relaxed, fist, point, grip, pinch | no save | to be checked: the finger bones (D187) may pose them by hand | check in RS8 |
| B19 | the mannequin presets | `builders.ts:173` | adult 1.75 m, child 0.7× (the bench) | no | partly (sizes) | **ok** (the workshop's dummy, D183) |
| B20 | **the stage's preset sets and stand-ins** | `builders.ts:142–171` | sets room / street / deck / empty; stand-ins crate / stool / table / pole / block | no | **no** — fixed geometry, nothing models it | **remove**, except the **block** (a box with its sizes as fields): "stand-in presets should all be props … the scene geometry should be simple — built from blocks" (Q22) · RS8 |
| B21 | the set builder's kinds | `F/suites/stage/placeSet.ts:18–31` | room, corridor, street, ground with default sizes and parts | sizes and parts editable | — the fit's own models | **ok** |
| B22 | the Fill's prompt leads and nouns | `O/place_sets.py:58–63, 155–181` | a lead + a noun per face | the material overrides the noun | no | **expose** (A20) · RS2 |
| B23 | the crowd's and walkers' words | `O/place_sets.py:46–57` | people, motion, walkers | "who" overrides | no | **expose** (A21–A22) · RS2 |
| B24 | the clean prompts | `O/set_things.py:25`, `O/place_things.py:282` | the clean instruction | no | no | **expose** (A24) · RS2 |
| B25 | **baked prompt leads** | the stage still `O/engine/graphs.py:1109–1117`; reangle `:999`; passes `:1526, 1609–1611`; plate and character `O/finals.py:27–35, 266`; lip-sync `O/routes/story.py:2678`; turn test `:1218` | fixed sentences added to every prompt | no | no | **expose** — each form shows its lead as editable text with the default · RS2, RS6 |
| B26 | the reangle moves | `generateStore.ts:278–282` | five | no | — | *model's own* (the angles LoRA) |
| B27 | the Fun-Camera moves | `animateStore.ts:20–22` | nine × speed | no | — | *model's own* (the node's presets) |
| B28 | the motion chips | `animateStore.ts:46` | ten phrases | no | yes (words) | **ok**, *parked* |
| B29 | the layer pass presets | `FinalEditor.tsx:23–28`, `compositionStore.ts:36` | four passes with default strengths | strength | partly | **convert** — the chain's pass steps, each with its form · RS6 |
| B30 | the light looks | `LightControls.tsx:11–17` | window, sun, lamp | sliders | yes | **ok** |
| B31 | the lens chips | `StageParts.tsx:62` | 24 / 35 / 50 / 85 mm | — | yes | **ok** |
| B32 | aspects and size tiers | `GenerateColumn.tsx:40`, the specs | the aspects; draft / hd / portrait / square | custom size | yes | **ok** |
| B33 | the curated effects | `F/suites/animate/Effects.tsx:14–36` | **21** effects, a few dials each, "the rest keep the engine's defaults" (`:1–4`) | no | partly | **expose** — an effect's every parameter behind its "more" · RS9 |
| B34 | the grade's looks and LUTs | `GradeControls.tsx:41–44` (FilmCraft's) | the engine's presets, LUTs | LUT import | partly | **ok** for now (Episode deferred) |
| B35 | the brushes | `EditSuite.tsx:54, 310–330` | built-ins, not deletable | **yes** | yes | **ok** |
| B36 | the downloaded animation clips + *Make it mine* | `O/motion.py:1–4, 42` (CC0) | mocap clips, read-only | own animations: everything (D182) | — imported data, not a template | **ok** |
| B37 | the Kokoro voices | `VoicesBlock.tsx:59` | the model's voices | cloning is the author's | — | *model's own* |
| B38 | the lip-sync presets | `S/wan22.toml:100–102` | draft / fast | choice | no | **expose** (A35) · RS6 |
| B39 | the training option lists | `O/capabilities.py:215`, `storyStore.ts:67` | ranks, resolutions, lr, steps | — | — | **remove** with A42 · RS8 |
| B40 | the render settings' defaults | `O/recipes.py:561–571` | quality, size, motion blur, blending, depth, alpha, ProRes | all exposed | yes | **ok** |
| B41 | the stage still's methods | `O/recipes.py:341`, `S/klein.toml:44, 59` | clay / refcontrol: LoRA, 30 steps, CFG 4 | choice only | no | **expose** (A26) · RS6 |
| B42 | the inpaint modes | `O/recipes.py:147` | fill, fill_match, fill_hero, remove, outpaint, quick_remove | choice | — operations, not presets | **ok**; their hidden fields in A9 |
| B43 | the plate methods and their automatic choice | `O/finals.py:48`, `finalShot.ts:74, 80–85` | projected / filled / generated / picture / set; 12° / 1.15 | switchable after | no | **expose** — the choice and its reason shown, the author's to make · RS6 |
| B44 | the scene's length | `sceneLength.ts:4–5` | 5 s default, 20 s cap | the length up to the cap | — | Q3 · RS3 |
| B45 | the sample model's default | `S/klein.toml:14` | Klein 4B | Settings | yes | **ok** |

## C. Where a parameter was hidden on purpose

The decisions that say so, so RS2 / RS6 / RS9 can show the parameter **and keep its reason as the field's ? help** rather than undo the measurement:

| Decision | What it fixed, and why |
| --- | --- |
| D84 (DL:102), `O/recipes.py:436` | the mesh upsample at 1024 ("1536 is the template's own, slower"); DecimateMesh at 50 k |
| D153 (DL:171) | SeedVR2 at ×2 only (×4 over-textures), colour match always; the clip path not offered (18 min) |
| D48 (DL:66) | match colour not offered on Inpaint (no drift to measure) |
| D184 (DL:202) | Wan Animate's replacement mode not offered; Fun-Camera's node has presets only |
| D173 (DL:191) | the crowd on the Draft preset (Motion was no more reliable at twice the time) |
| D174 (DL:192) | the walkers' geometry and `person:20` |
| D143 (DL:161) | the camera height the author's; the texel per kind fixed |
| D135 (DL:153) | the keyframe Fill at expand 48, feather 32 |
| D176, D177 (DL:194–195) | a reference make leaves the Look out; the A-pose framings at 2:3 (the panel only — the buttons still send 16:9, A2) |
| D183 (DL:201) | the shell queued by itself after a fit |
| D193 (DL:211) | H3's fixed fps (its sound's rate); no negative or shift where the graph has none; no 768p (21 min) |
| D96 (DL:114) | the principle already: "templates prefill and hide nothing — no feature is sacrificed for simplicity" |
| D186, D190 (DL:204, 208) | the model card at every image-making surface; "we should always enable a model picker" |

The rule for the run forms follows from these: **a measured default stays the default and its measurement becomes the field's ? help; the field
itself is shown.** Where a value is not offered because the model cannot do it (H3's fps), the field shows the value, disabled, with the reason.
