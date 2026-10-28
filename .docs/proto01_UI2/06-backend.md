<!-- markdownlint-disable MD024 -->
# 06 · The backend, read against the new UI

Read from the code at `e8ce296` by four read-only surveys (World and the Bin, Shots, Episode and the services, the frontend). Their load-bearing claims
were checked against the code where this study relies on them. Paths are relative to `orchestrator/loom2/` unless they start with `frontend/`.

**The verdicts:**

- **keep:** works as it is behind the new UI;
- **adapt:** same record, a field or a rule changes;
- **new:** does not exist;
- **retire:** goes, or becomes internal.

## 1. World

### 1.1 Entities: Cast profiles

A profile (`story.py:244-277`, `story/profiles/prf_*.json`, schema 3) has a class (character, place, prop), versions and a **voice on the profile**
(`:252`, not on the version). A version (`story.py:164-221`) holds:

| Field | Written by | New home | Verdict |
| --- | --- | --- | --- |
| `appearance`, `outfit`, `colours`, `marks` (the sheet) | create, PATCH (read-only once final) | the header ([03](03-ui-world.md) §2) | **keep** (colours and marks shown inside appearance) |
| `body`, `body_fit_from`, `body_points` | the keypoints finisher (`engine/finishers.py:906-933`), `body/refit` | the header's body | **keep** |
| `hero_asset_id` | create, `add_assets` role=hero (`:2259-2305`), PATCH (which skips the cover logic) | the hero role | **adapt**: PATCH must go through `add_assets` |
| `group_id` (reference set), `candidates_group_id` | create (`:1941`), `ensure_candidates` (`:2248-2257`) | the bin's role pages (§1.2) | **adapt** |
| `anim_ref_asset_id`, `anim_ref_back_asset_id` | the `anim_ref` finisher (first result if empty, `finishers.py:131-137`), PUT `anim-ref` | the A-pose roles | **keep**. A place's *set picture* reuses `anim_ref_asset_id` (`place_sets.py:43-45`); worth a field of its own (**adapt**) |
| `shell_asset_id`, `model_asset_id`, `height_m` | MeshFinisher (`finishers.py:789-881`), `model/import` | the header's 3D model, the body | **keep** |
| `place_set` (faces, sources) | `set/fit`, bake, Fill (`place_sets.py:80`, `:227-302`) | the header's set | **keep** |
| `poses{}` | PUT `poses/{name}` | Clay's pose library | **keep** |
| `lora`, `trigger` | the trainer | the Inspector's LoRA | **keep** |
| `from_idea`, `derived_from` | `set_kept_from_idea`, `new_version` | — | `from_idea` is write-only (**retire**); `derived_from` **keep** (lineage) |

**Two traps for the new header:**

- `new_version` copies only the sheet, the poses and the place set (`story.py:2213`). The anim refs, the body points, the shell, the model and the LoRA
  are **not** carried, and the reference set is deep-copied as new files (`:2210`). The header must say what a new version starts without, or the copy
  must carry them (Q6).
- `delete_profile` (`:2307`) leaves its groups and pictures behind in the album. A bin's delete must delete or trash the bin.

### 1.2 The Bin: groups, homes, roles, batches

**Today:**

- An asset's place is its **album placement**: one group, enforced by moving (`groups.py:250-275`).
- An asset with no placement is *Unprocessed* (`catalogue.py:445`).
- Groups nest, but **carry no kind or role** (`groups.py:49-70`).
- A role exists only because a record points at a group or an asset: the version's `group_id`, a style's `group_id`, a Flow board (`usedby.py:34-62`).
- Every backend-made group sits on the album root, found by its display name.

**Where the World layer's products land today** (the walkthrough's chaos, explained):

| Product | Lands in |
| --- | --- |
| Expand, the casting run, the A-pose | the candidates page (AssetFinisher's `origin.payload.group_id`, the only generic hook, `finishers.py:138-145`) |
| Prop models, character shells | **Unprocessed**, stamped `suite="generate"`, so they show in Image's results (`finishers.py:779`) |
| The set fit's relief, the bake and coverage images, Fill's faces | **Unprocessed** (`routes/story.py:831-834`, `place_sets.py:242`) |
| The anim-test clip | **Unprocessed**, while its guide video goes to candidates (`routes/story.py:950`) |
| Voice lines | **Unprocessed** (`voices.py:274-285`) |
| The LoRA check page | on the album root, found by name (`routes/story.py:1120`) |

**Who reads the version's pages directly** (and would break if the pages were dissolved into one flat bin):

- mentions: references in page order, cover first (`mentions.py:30-40`, `43-196`);
- the trainer (`trainer.py:95-98`);
- Cast readiness (`routes/story.py:182-184`);
- shot staleness keyed on the group's revision (`shot_recipe.py:130-147`);
- `usedby`, ideas and the stage pages;
- the frontend's mentions, Cast and catalogue places.

**The recommendation: a bin is a group tree; roles are its child pages; the UI shows one grid.**

- **new:** a bin group per home, with a `path` and a `kind`: `world/character/<profile>/<version>`, `shots/<shot>/<version>`, `episode/<cut>`,
  `world/look`, `world/sketches`, `imports`. GroupRecord gains `kind` and `path` (schema bump); the path is computed from ids, so a rename does not
  break it.
- **adapt:** a version's reference set and candidates pages become **children of its bin** (`kind: role`, `role: reference | candidates`). Every reader
  above keeps reading `v.group_id` unchanged. *Make it the hero* and *Use as a reference* move the picture between the bin's child pages, as `add_assets`
  does today. The UI shows the union with role badges ([03](03-ui-world.md) §5), so to the author a picture "stays in the bin and gains a role".
- **adapt: every finisher writes a home.** The generic hook (`origin.payload.group_id`) moves from AssetFinisher into a shared ingest step, so meshes,
  clips, set bakes, fills, voice lines and the LoRA check all land in their owner's bin. `origin` already names the owner (profile and version, shot
  and version, cut).
- **retire:** *Unprocessed* as a place (an asset without an owner lands in `world/sketches` or `imports`), the frontend's *Library* folder, and the
  vestigial collections (SQLite tables with no routes, kept for the D34 migration, `groups.py:152-184`).
- **migration:**
  1. make the bin tree;
  2. move each version's two pages under it;
  3. sort Unprocessed assets by their `origin` into their owners' bins (the rest into `imports`);
  4. move style sample groups under `world/look`, Flow boards under their shot.

  The migration is idempotent, run at open like `migrate_rc2` (`story.py:1814-1882`).

**Batches: retire the grouping, keep the field.**

- `batch_id` is load-bearing in two places:
  - the queue (a multi-seed submit, `queue.py:316-328`);
  - Edit, where an AI run's candidates share the layer group `grp_<batch_id>`, excluded from the engine's own input (`finishers.py:253-283`,
    `pipeline.py:407`).
- What goes is its role on screen:
  - the `group=batch` headers of `/assets/groups` (`catalogue.py:548-566`);
  - Generate's *this batch* strip (`GenerateSuite.tsx:99-123`);
  - the Catalogue's *Show this batch*.
- The Inspector keeps *Same run* (the batch's siblings).

### 1.3 Story › World and the Library

| Record | Read by | Verdict |
| --- | --- | --- |
| `logline`, `synopsis` | nothing but the editor (`StoryParts.tsx:448-452`) | **retire** (or a Project note, Q1) |
| `spine[]` and `FlowNode.beat_id` | *Make the Flow from the spine* only | **retire**; keep `beat_id` readable for old projects |
| `styles[]`, `default_style` | T2I's `style_id` / `style_text` (`recipes.py:113-114`, resolved at submit, `queue.py:302-303`); staleness stamp `style:<id>`; Expand and the A-pose take a style | **keep** as the *Look* (a project record; World's page goes, the record stays in `story/world.json`) |
| `variables[]` | `validate_flow` (`story.py:626-636`), Flow play, Episode's route walk | **keep**, shown in Shots › Flow |
| the Library (`story/library.json`, 17 fields, 119 seeds) | the frontend's preset popovers only (no recipe reads it) | **adapt:** subject and look fields stay with World's Make and the Look; lighting, camera, lens, distance and composition become Clay's light and camera presets; pose and action become Clay's pose presets |
| Saved panels (`generate/presets.json`), Animate panels | Image; Animate | **keep** with Make; **retire** Animate panels with the Image-to-video card |
| Shot templates (`story/shot_templates.json`: a node type, words, a route, a camera with keys) | the Flow | **adapt** into *stage templates* that keep cameras and figures (§2.3) |

### 1.4 Ideas, voices, LoRAs, sets

- **Ideas** (`ideas.py`: an idea with its own page, variants, a clay chain, *Keep* into a profile): **retire as a store**, fold into draft entities and
  World › Sketches ([03](03-ui-world.md) §7). The clay chain (A-pose → keypoints → mesh) is the same as an entity's and is reused. Migration: each idea
  becomes a draft profile of its class; its variants become candidates in that profile's bin.
- **Voices** (`voices.py`, a profile's `voice_id`): **keep**.
- **LoRAs** (`loras.py`, `trainer.py`): **keep**. A LoRA check lands in the version's bin.
- **Place sets** (`place_sets.py`: fit, bake, Fill): **keep**. `set_things.py` belongs to a stage's picture set (Clay), not to World.

## 2. Shots

### 2.1 One node type for a shot

**Shot and Dialogue nodes hold identical fields** (`FlowNode`, `story.py:414-440`). Both get a shot (`create_node`, `:1297-1312`), and a PATCH may
switch between them. All the difference is in behaviour, behind `type == "dialogue"` filters:

- voicing a whole episode (`routes/story.py:2116`, `episodeVerbs.ts:38`);
- the recipe graph's speakers and lines (`shot_graph.py:114`, `:135`);
- a final's lines for the composition and lip-sync (`routes/finals.py:1150`);
- the board's Lines and Voice cells (`board.ts:22`, `:88-94`);
- the Make prefill (speakers → subjects, the title as the text, `makeFor.ts:30-71`).

**Verdict: adapt, no data migration.**

1. Drop `dialogue` from `NODE_TYPES` / `VISUAL_TYPES` (`story.py:383-385`).
2. Read old `dialogue` files as `shot`.
3. Change the filters to "a shot with lines".

A merged node keeps both `text` (the action) and `lines` (the speech). About 28 backend tests and 9 Vitest files name `dialogue`, plus the e2e.

### 2.2 Shots and their recipes

**RC2's state: one record, two identities.**

- The shot lives inside its node's file (`ShotPart`, `story.py:468-492`).
- It still has its own id (`sht_*`, kept because finals, cuts, origins and manifests name it), its own revision, the `shot_id` / `shot_version` copied
  onto the node, and its own route family (`/story/shots/*` beside `/story/flow/nodes/*`).

**Verdict: keep the two ids internally.** The new UI addresses a shot by its node and never shows the `sht` id. Finishing RC2 (one id) would touch every
record that names a shot, for no gain the author sees.

**The five recipe templates** (`shot_recipe.py:84-95`: `i2v`, `stage`, `clay1`, `clay2`, `dialogue`):

- `default_template` picks `i2v` unless the version already has a stage (`:98-99`), which is why the walkthrough's shots went around Clay;
- `clay1` and `clay2` are the same steps;
- `dialogue`'s voice step is still "planned";
- *Run stale* never re-runs a clay step: `stale_plan` reads the frame and clip steps only (`:317-330`), and the clay states come from the recipe graph
  (`shot_graph.py:313-326`).

**Verdict: adapt.** There is one template, `clay`, with steps:

1. passes;
2. performance per layer;
3. final;
4. approval.

The old routes become Performance *methods* (§2.6). The recipe graph (RC1) already reads finals per part (`stage_stamps`). *Run stale* learns the clay
steps, so a changed stage re-plans its layers. The review's Run-stale seed bug (the whole `seeds` list replayed, [08](08-register.md)) is fixed with it.

### 2.3 Scenes and stages

**Today:**

- A version points at a stage camera (`ShotVersion.stage_id`, `camera_id`, `stage_revision`, `story.py:305-321`). The stage holds no pointer back.
- Results reach shots by fanning out over the camera (`record_stage_result`, `story.py:1096-1111`).
- A stage has **one range for all its cameras** (`stages.py:246`).
- Siblings made by *New Shot from this Shot* share the stage and copy the camera (`story.py:1655-1709`). `own_stage` copies a stage (`:1573-1592`).
- Flow *scenes* (`story/flow/scenes.json`) are a separate grouping of nodes, with cast pins and a grade.

**What "a shot is a camera on its scene's stage" needs** ([04](04-ui-shots.md) §1):

| Need | Change | Verdict |
| --- | --- | --- |
| a scene record that owns its stage | `Scene.stage_id`; the scene's members are the shots on that stage | **adapt** (`scenes.json`) |
| a stage made with the shot | `create_node(type=shot)` makes the stage (from the place, a template, or the previous shot's) and a camera, in one call | **adapt** (`story.py:1297-1312`) |
| each shot its own camera | a camera serves at most one shot; `set_source` refuses a second (today it allows any stage) | **adapt** |
| each shot its own range | `ShotPart.range {start, end}` on the scene's timeline. The final already copies a range from the stage (`finals.py:112-135`) | **new** field |
| a stage that knows its shots | derived from the scene; `record_stage_result`'s fan-out and `final_for`'s camera fallback become direct lookups | **adapt** |
| versions that do not drift | a version pins `stage_revision` (exists). A stale mark follows a later change | **keep** |
| bench and line-up stages kept out | `purpose` already separates them (`routes/stages.py:31-35`); refuse them as a shot's scene | **keep** + a guard |
| **migration** | each shot without a stage gets one (an empty set from its place, a camera at eye level). Shots sharing a camera get their own. Orphan stages stay as free stages under `Bin › imports` | **new** (at open, idempotent) |

### 2.4 Animation: clip blocks and templates

**Today:**

- Animation is `keyframes` in the stage record (untyped on the backend, `stages.py:245`):
  - camera keys;
  - object keys with poses (joints, Detailed `extra`, ground, pins, contacts, gaze);
  - skeleton keys.
- **A clip is not stored as a clip.** `applyMotion` bakes the retargeted, thinned keys into the object's keys and extends the range
  (`stageStore.ts:475-487`, `motion/motionStore.ts:56-89`). The timeline shows dense runs of keys as bars (`timelineMath.ts:31-45`).

**Clip blocks (new):** the stage gains `tracks`, one per animated object, each a list of blocks.

```
{id, source: {kind: library | template, id, clip}, start, trim_in, trim_out, loops, speed, blend_in, blend_out, in_place, foot_lock, path?}
```

The existing keys stay as the track's key layer on top. The client evaluates blocks and keys into poses at play and render time with today's retarget,
foot lock and contact code. Applying a clip adds a block instead of baking. *Bake to keys* keeps the old behaviour. Schema 4 migration: today's baked
keys stay as key layers.

**Templates (new):** the second survey weighed two stores.

| Option | What it costs |
| --- | --- |
| **Stage-key JSON** (`ObjectKey[]`) | applies through `applyMotion` as it is. Keeps the Detailed bones, ground and pins. Needs re-basing to frame 0 and the start position and yaw, the root re-scaled to another body's hip, contact re-run (D141), and foreign contacts and gaze dropped |
| **GLB** in the motion folder | needs a write route (none), a GLTF exporter (none) and a rig with rigify, unreal or mixamo bone names. Loses `extra`, pins, contacts, gaze and ground, re-adds retarget and foot-lock error, lives outside the project, and its id breaks on rename |

**Recommendation: JSON.**

- A template is `{name, rig: "mannequin", frames, fps, keys: ObjectKey[], from: {stage, object, range}}`.
- It is stored in the project (`stages/animations.json`, revision-guarded like `poses.json`).
- *Save to my library* copies it into app state (`<state>/animations/`), so it is available in every project (Q4).
- The motion library lists a third source, *Mine*. The scanner's `local_dir` keeps importing GLB / FBX, and gains an *Import…* button that copies a file
  into it (**new** route).

This supersedes the GLB idea of [01](01-evaluation.md) §9.

### 2.5 Finals: Performance and Final

**Today:**

- A final (`finals.py:112-135`, `finals/<id>/final.json`) has layers: plate, figure, prop, shadows (`:34`), each with method, passes, takes, status and
  jobs.
- Its jobs:
  - the plate still is `stage_shot` clay;
  - the plate is projected, filled or generated;
  - each figure is Wan Animate in 77-frame batches;
  - then `matte_sequence`, `assemble_final` and `comp_render`.
- The composition is EffectCraft's (`compositions.py`, `finals/<id>/comp.ecproj`).
- The passes are `layer_pass`: cleanup, creative, face and lip-sync (`routes/finals.py:652-802`).
- **Two lip-syncs:**
  - the shot's whole-frame S2V (`routes/story.py:2162-2220`);
  - the final's layer pass, as an S2V head or LatentSync (`lipsync.py`).

**The two levels map onto this without new records:**

| Level | Reads and writes | Verdict |
| --- | --- | --- |
| Performance | the final's layers and their takes; the layer jobs; FaceSim on a figure take (it exists for clips) | **adapt**: a final per shot version (not per stage), created with the shot, so the level always has one |
| Final | the composition, mattes, passes (lip-sync per speaking layer), `comp_render` | **keep** |
| the shot's final | `comp_render`'s clip, today a take with `use=None` (fills an empty slot, `finishers.py:1341`) | **adapt**: it is *the* final of the version; a take records its kind (`final`) and its final id |

**Fixes the new levels need:**

- the foot acts on its shot's final, not on `.at(-1)` of the stage's newest-first list (`finalShot.ts:607-610`, F41);
- the plate warns when the built set has unfilled faces (F43);
- the plate's prompt is composed from the shot (§2.8).

### 2.6 The other making routes, as Performance methods

| Method | Today | Verdict |
| --- | --- | --- |
| One pass | the stage clip: `I2V` with `guide` {depth (LTX IC-LoRA) \| pose (Wan Animate)} from `/stages/{id}/guide` (`recipes.py:255-291`) | **keep**; its result becomes a take of the shot version (today it fans out by camera) |
| From the start still | `I2V` (Wan 2.2, LTX, Fun-Camera) from a `stage_shot` still | **adapt**: the start is the shot's own still. The camera move is derived from the clay camera's keys when one of the nine moves matches; otherwise the method says it cannot follow the camera |
| Speaking close-up | the shot-level S2V lip-sync | **adapt** into the method; the final's lip-sync pass stays the default |
| Image › From a stage | `stage_shot` stills (`recipes.py:360-378`) | **adapt**: the shot's *Stills* (start still, boards); no separate trip |

The review's finding stays to fix: a camera move must be refused on a model without the camera flag (`graphs.py:151-152`).

### 2.7 Creating a shot

**new:** one route, `POST /story/flow/shots`, that makes the node, its shot part, its scene (new or existing), the stage (from a place, a stage template,
or a copy) and its camera, and connects it after a given node. It replaces three client loops today: *Make the Flow from the spine*, *Block it on a
stage…* and *New shot from this camera…*. Stage templates (`stages/templates.json`, objects only) gain cameras and figures, so a template is a whole
starting arrangement (§1.3).

### 2.8 The words of a shot's pictures

**new:** a server-side composer, `shot_prompt(shot, purpose)`, for the plate, the start still, the stills and the performance prompts. It reads:

1. the Look;
2. the bound place's sheet;
3. the visible cast's sheets, references and LoRAs (the stage masks);
4. the Clay lights as words;
5. the scene's words;
6. the shot's description;
7. the shot's own extra words.

It replaces three things:

- the fixed plate prompt (`routes/finals.py:196-243`: "The room is empty…", F38);
- the client-side prefills (`makeFor.ts`);
- `stage_prompt` in the graphs.

It returns its parts with their sources, so the UI can show them ([04](04-ui-shots.md) §6). Lights need a words function per kind (Window, Sun, Lamp),
colour and direction.

## 3. Episode

**Today**, the cut is FilmCraft's project (`cuts.py`, `timelines/<id>/cut.fcproj`), with `loom2.*` metadata on its items (shot, version, node, clip,
line). The rest:

- **Undo and redo:** snapshots, 50 deep.
- **Assembling is frontend-only:** `walkRoute` + `assembleLane` (`assemble.ts:16-60`), saved by a PUT that runs `Cuts.write`.
  - `Cuts.write` **clears V1 and A1's lines and rebuilds them** (`cuts.py:567-602`).
  - So *Assemble again* loses V1's speed changes, holds and per-clip grades, and the author's moved lines, without a warning.
- **What it takes from a clip:** the PNG master when the clip is at the cut's rate, otherwise the H.264 proxy (`cuts.py:1239-1256`).
  - So the 16 fps Wan clips enter as proxies, which is F40's cause.
  - The movie conforms them with RIFE, but changes the live cut without an undo step or a revision bump (`finishers.py:1679-1712`).
- **Sound:** V1 is placed without its sound (`cuts.py:589-590`). A final's own mixed lines never reach the cut; A1's lines come from the nodes.
- **What it never reads:** `finals/`. A take has no kind and no final id, so "is this a finished final" is not known to the cut.

| Change | Verdict |
| --- | --- |
| Episode reads each shot version's **final** (the take kind of §2.5); the Finals list in route order | **adapt** |
| A backend `POST /timelines/{id}/assemble {route picks}` that places only what changed, keeping V1's edits; the frontend walk stays for the preview | **new** (fixes the destructive rebuild) |
| A shot with lines held to its lines, or listed (F39) | **adapt** in assemble |
| Clips named after their shots (FilmCraft `clip.rename`); a 16 fps final conformed by RIFE *before* it lands, as an undoable step | **adapt** |
| `sync_lines` bumps the revision and broadcasts (review) | **adapt** |
| A per-cut lock held across a change (the FilmCraft session switches projects between requests, review) | **adapt** |
| Cut capabilities in `/capabilities` (FilmCraft and VST availability, strip and grade ranges, today duplicated in `cut.ts:160`, `:177`, rule 5) | **adapt** |
| Retire: the legacy lane and `SequenceStage`; RC3's movie render where FilmCraft is built; `suite="animate", surface="sequence"` origins; the sequence-tab redirect | **retire** |

## 4. The services every layer uses

- **The queue** (`queue.py`): kinds, warm groups (with the 600 s fairness), staging and release, cancel, persistence and resume. **keep.**
  - `GET /jobs` ignores `limit` (it returned every job in the walkthrough); worth fixing for the dock (**adapt**).
  - The estimate ignores references (`engine/graphs.py:1829-1845`, F27); it must count them (**adapt**).
- **`/capabilities`:** **keep**, with the cut's section (§3) and the Look's sample scene per project (**adapt**).
- **Events** (`WS /events`): `story.changed`, `final.updated`, `timeline.updated`, `stage.updated`, `group.changed`… **keep**, plus `bin.changed`
  when homes move (**new**).
- **Settings:** the sample scene moves into the project (F3); FilmCraft's and EffectCraft's settings stay hidden; everything else **keep**.
- **Safety and concurrency from the review** ([08](08-register.md) §2). The new UI makes more calls per click, so these get worse, not better, and are
  fixed in its first wave:
  - ids validated on every path parameter;
  - `_LOCK` in the profile, world, graph and idea read-modify-writes;
  - the per-cut lock;
  - voice results matched by line, not by index;
  - the detached loupe window not closing the app.

## 5. The frontend: what is mounted, what is rewritten

The frontend is about 39,600 lines of code in its suites and frame, with about 7,900 lines of tests. Vitest: 597 passed, 3 skipped. The survey's verdict
per area:

### 5.1 Mounted as they are

| Piece | Lines | Why it lifts out cleanly |
| --- | --- | --- |
| Edit: `EditorCanvas`, `editorStore` and the leaf modules (layers, blend modes, filters, brushes, selection, transform, text, PSD, AI recipes) | ≈ 7,800 | the cleanest suite: no static imports from other suites. One open document at a time, which is what World's and Shots' Edit need |
| Stage: `engine.ts` (three.js, picking, gizmos, passes, projection) and the pure modules (builders, Detailed figure, proxy, IK, held, anim, place sets, bake, Fill, skeleton) | ≈ 3,500 | imports only its own modules and the API |
| Motion: retarget, foot lock, contact, bake, walk path, library | ≈ 1,200 | pure maths, the base of clip blocks (§2.4) |
| The timeline (`Timeline.tsx`, `timelineMath.ts`), the player (`Player.tsx`) | ≈ 270 | driven by props, used by every level |
| Final: `FinalEditor`, `Effects`, `FinalViewer`, `compositionStore` | ≈ 1,400 | one composition at a time |
| Episode: `CutStage`, `cut.ts`, `SequencePanel`, `GradeControls`, `StripControls`, `EffectPicker`, `assemble`, `sequenceStore` / `sequenceCommands` | ≈ 1,800 | the FilmCraft editor; only its clip list comes from `animateStore` |
| The Catalogue's store factory (`createCatalogueStore`, four instances today) and its grid, loupe, page view, panes, lineage and Inspector | ≈ 2,000 | a bin is one more instance with a `group_id` |
| World's entity editors (`CastSheet`, `CastBody`, `CastSet`, `setBuilder`, Voices, Training) and `FlowCanvas`, `play.ts` | ≈ 1,200 | small, self-contained |
| The frame's generic parts: commands, `CommandButton`, `ContextMenu`, keymap and its remapping, drag and drop rules, theme, Toasts, AskDialog, Help, ErrorBoundary, lazy parts, keep-alive, dialogs | ≈ 1,500 | generic |
| The API client, types and the generated schema | — | the only client |

### 5.2 Kept, with their couplings cut

| Piece | The coupling | The cut |
| --- | --- | --- |
| `generateStore` + `GenerateColumn` (the Make panel) | one persisted panel for the whole app; it switches suites itself; it imports `storyStore` | a **panel per context key** (an entity version, a sketch), saved and restored when the header changes; navigation through the shell's router |
| `stageStore` + Clay's parts (`StageParts`, `ShotStepper`) | one open stage; `open()` calls `setSuite('stage')`; the Viewport is not exported; the sections are tied to Clay's rail | the scene opened by the shot; the Viewport exported; sections mounted by the Shots layer |
| `animateStore`, `AnimateSuite`, `finalShot` (`useFinals`), `FinalPanel` | cross-wired with Stage and each other; three levels share `setReach` and keys; `transport()` reads the level from `ui.suite` | the levels are the shot's; the transport takes its level from the shot view |
| `storyStore` (1,288), `StoryParts` (1,313), `storyCommands` (213 commands) | one suite dispatched on its tab; records mixed with selection and filters | **split** into records (profiles, flow, shots, scenes, voices) and each layer's own view state; the views extracted from `StoryParts` |
| `session.ts`, `origin.ts` | `ui.suite` is the only "where am I"; the For context; navigation as a map of today's suites | a router (§5.3); the For context **retired** |
| The Dock and its Bin; `catalogueCommands` | the Bin's verbs per suite (`BIN_SUITES`); send-to verbs name the old suites | verbs per layer |
| `TopBar` | spring-loaded tabs with Image and Animate drop verbs; imports `generateStore` | the four layer tabs; drop verbs move to the layers |

### 5.3 What the new shell must do first

The survey's ten obstacles reduce to four seams. Each is done before any layer is built:

1. **A router instead of `ui.suite`.** There are 37 reads of `ui.suite` and 80 `setSuite` / 27 `setRailTab` calls in 27 files. Stores open their own
   suite. The key hooks of Generate, Edit, Animate, Final and Clay return early unless `ui.suite` matches. The new shell has one `place` (layer, entity
   or shot, level) and one `navigate(place)`:
   - stores stop navigating, and commands call `navigate`;
   - key hooks are scoped by the place;
   - the reused parts read the place through a small adapter, so `ui.suite` keeps working for the old UI during the transition.
2. **Keys and side effects mounted by the shell, not inside Strip components.** `useEditKeys`, which also does paste, deep links and autosave, and the
   other key hooks live in Strips today. A shell without those Strips would silently lose keys and autosave.
3. **A records layer** shared by the layers: profiles, flow, shots, scenes, clips, finals, cuts. It owns the WebSocket fan-out, which today goes to a
   fixed list of eight suite stores in `session.applyEvent`. Episode stops reading clips from `animateStore`.
4. **Context instances for the singletons:** the Make panel per entity, the open stage per shot, the composition per final. Each is a store keyed by its
   context, or the singleton with an explicit save and restore.

**Kept as they are, because the API depends on them:** the closed unions `Suite`, `Scope` and `JobOrigin.suite` (D38's contract, *Go to origin*,
the origins in manifests). The new UI maps its places onto them.

**Tests:**

- About 85 Vitest files test pure logic and carry over.
- 10 component-render files carry over with their components.
- 8 pin today's layout (`commandAudit`, `stageKeep`, `modes`, `timeline`'s transport, `origin`, `openWith`, `storyKeys`, part of `propsTab`).
- In the e2e, 89 of 90 `openApp` calls use a `?suite=` deep link, and 49 of the 79 scenarios use tab, rail, region or mode selectors. **The e2e is
  rewritten alongside the shell**, scenario by scenario, as each layer reaches parity.

**Vestigial, to drop with the old shell:**

- the sequence-tab and props redirects;
- the `models` suite;
- `placeholders.tsx`;
- the `OutlinerTab` alias;
- the legacy Episode lane;
- two of the five playback paths and one of the three timeline renderers;
- the duplicate record views: an asset has three, a clip three, a shot five.

## 6. The gap, in one table

| # | Change | Layer | Kind | Size |
| --- | --- | --- | --- | --- |
| G1 | Bin tree: GroupRecord `kind` / `path`; the version's pages as role children; every finisher writes a home; Unprocessed sorted; migration | World, Bin | adapt + migration | L |
| G2 | The Look as the project's record; the sample scene per project | World | adapt | S |
| G3 | Library split: look and subject words in World; light, camera and pose presets in Clay | World, Shots | adapt | M |
| G4 | Ideas folded into draft entities and Sketches; migration | World | retire + migration | M |
| G5 | One Shot node type (no data migration) | Shots | adapt | S |
| G6 | Scene owns its stage; a shot is a camera + `range`; one camera per shot; migration | Shots | adapt + new + migration | L |
| G7 | One `clay` recipe template; Run stale re-plans clay steps; the seeds bug | Shots | adapt | M |
| G8 | Clip blocks on stage tracks (schema 4) | Shots | new | L |
| G9 | Animation templates (JSON, project + app library); motion *Import…* | Shots | new | M |
| G10 | A final per shot version; the take kind `final` and its id; the foot's final | Shots | adapt | M |
| G11 | Performance methods from the old routes; the camera move from the clay camera | Shots | adapt | M |
| G12 | `POST /story/flow/shots` (node + scene + stage + camera in one) | Shots | new | S |
| G13 | `shot_prompt()`: the words from World and Clay; lights as words | Shots | new | M |
| G14 | Episode reads finals; backend assemble that keeps edits; lines held; names and conform | Episode | adapt + new | M |
| G15 | The review's safety and concurrency fixes; the estimate with references; `/jobs` limit | all | adapt | M |
| G16 | Expand and LoRA training retired (D157, Q6): the trainer, the LoRA registry and check, `lora` / `trigger`, the auto-LoRA, Expand and `coverage_cell` | World | retire, at U8 | M |
| G17 | Lights as templates with an editor (D157, Q10): kinds, temperature, intensity, size, falloff, shadows, words; *Save as a light template* | Shots | adapt + new | M |
