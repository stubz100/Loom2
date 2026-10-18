# 01 · Animation from clay — the pipeline, reviewed

Status: **proposal, 2026-10-17; revised after the author's notes of 2026-10-17 and 2026-10-18** (§8 lists them; §9 the dummies, §10
props, §11 lip-sync). For the author to refine; no decision yet (00).

## 1. The idea

Every character is animated alone, precisely, and the shot is assembled from the pieces. A shot passes through **two models of itself**
before it is final:

1. **The clay.** Stage's mannequins are keyed in 3D, with a keyed camera. This fixes the motion, positions, facing and framing, but has
   no look.
2. **The performance.** Wan 2.2 Animate turns "this character's animation reference + this figure's pose sequence" into one clip per
   character. The clip has the motion with the character's body, clothes and face, roughly lit, over a plate that moves with the camera.
3. **The final.** Post-processing renders the performance into the finished shot: detail, faces, and one light with real shadows across
   the layers.

In the author's words (note 1): *"use the wan-animate output as we are using the Stage clay dummies — a model of the final version."*
Two things follow:

- **Wan Animate's bar is motion and identity, not finish.**
- **Post-processing (step 8) is a required stage, the "render", not an optional polish.** Its spike (E24) carries as much weight as the
  pipeline's (E23).

**Why this route.** Our video models animate *one* character well, but not two from one prompt:

- E21 and E22 showed that one prompt makes the two characters take turns.
- Layers animated separately cannot touch each other.

Stage gives exact positions, paths, facing and camera moves. Wan Animate follows a Stage pose pass closely: E19 measured PCK 0.80–1.0
over 77 frames, and CN4 (D87) built it into Stage as the "Wan Animate" clip method. What is missing is the assembly: several characters,
several batches, a moving background, the joins, and the final render.

## 2. The workflow, step by step

The author's eight steps, with steps 3 and 4 swapped (note 2). ✔ means it works as described, ✎ means a change, ⚠ means a risk.

### 1) Set up the World, templates and styles — ✔

This exists: World, the Library (D92) and styles as images. The shot's **World style** applies to *both* the plate and the character's
animation reference. Otherwise the layers come out in two visual styles.

### 2) Generate the characters, each with its animation reference — ✔ + one new piece (note 6)

This exists: Cast characters (D85), Give a look / Add to character (D93 A), the character sheet and versions as costumes (D93 B).

**New: the animation reference is made at casting, as part of the character**, not when a shot is animated. It is one image per Cast
version (costume):

- **Full body, front-facing, a neutral A-pose** (arms a little away from the body, so they do not merge with the torso), on a plain
  background.
- **Made in the clip's aspect (16:9), the figure centred and padded.** The node centre-crops the reference to the clip's size, so a
  portrait reference loses its head and feet. E19 also showed that a cropped reference paints a ghost into the background.
- **Made from the version's sheet and references**: Klein 9B with references, the costume colours bound (D93 B; the E21 still drifted a
  jacket from yellow to olive). Cast shows it beside the coverage grid, with a command *Make an animation reference*, or a full-body
  cell marked as the reference.
- **Optional: a back view** from the sheet. Wan Animate takes one reference and invents the back when a character turns away. When a
  Shot starts with the character facing away, the back view can be its start still (step 6).
- **Optional: a test at casting.** A short test animation (a turn on the spot, 77 frames, ≈ 5 min) shows whether the reference animates
  well before any shot depends on it.

### 3) Create a Stage and add the characters and the set — ✔ mostly exists (was step 4)

This exists: figures bound to Cast characters with a version (D93 C8), sets, props, image planes, cameras.

New pieces:

- **The set's blocks come first.** The background in step 4 is generated from them.
- **A key light** whose direction matches the plate's light. It is used for a shadow pass (Move mode, step 7).
- **Layers:** which objects go into which layer. By default each figure is its own layer and the set is the plate. A held prop belongs to
  its character's layer.

### 4) Generate the background from the Stage — ✎ (was step 3)

The plate is generated **from the Stage set**, not on its own. A background made on its own does not match the Stage camera: perspective,
lens, horizon and floor differ, so the characters stand on the wrong ground at the wrong scale. The steps:

1. Render the **empty set's clay and depth pass** from the shot camera.
2. Generate the **plate still** from it with the Clay reference method in the World style. E21 did this; the perspective then matches the
   mannequins exactly.

**Camera moves.** One still plate cannot move with the camera; there would be no parallax. The moving plate is derived after step 5,
when the camera keys exist. There are three options, by size of move:

| Camera move | Plate | Cost |
| --- | --- | --- |
| none (locked off) | the plate still | one image (≈ 15 s) |
| small: pan, tilt, a short dolly | the plate **projected onto the set's blocks** and re-rendered along the camera path in Stage (2.5D camera projection: three.js, no GPU job) | seconds; edges can stretch where the camera sees behind objects |
| large: an orbit, a long move | a **plate video** guided by the empty set's depth sequence (Stage's existing *Render clip* with the IC-LoRA depth guide) | ≈ 2–5 min per batch; the background may "breathe" |

### 5) Draft the animation and camera moves in Stage — ✔ exists, ✎ a motion library (note 5)

This exists:

- keyframes for every object's position and rotation;
- **joint poses keyed over time**, interpolated between keys;
- camera keys (position, target, focal length) with linear or eased transitions;
- timeline playback (ST4, D81).

**Authoring is the bottleneck**: keying every joint of a walk by hand is slow. The author's answer is a **motion library**: clips
imported and retargeted onto the mannequin. Presets and keys by hand stay for fine-tuning.

**The library in the old loom repo, examined** (`F:\source\repos\stubz-002-tripo-sf\Godot4-MixamoLibraries`):

- **What it is.** The folder keeps the old name, but the checkout is catprisbrey's *Godot4-OpenAnimationLibraries*
  (github.com/catprisbrey/Godot4-OpenAnimationLibraries, last commit 2025-01-18).
- **What it holds.** Its `FORMER-README.md` says the Mixamo libraries were **removed**, because Adobe's terms (6.2.E) forbid making
  databases from their content. What is left is game sets:
  - *MeleeLib*: idle, walk, run, strafes, sprint, attacks, rolls, ladders, open a door / chest / gate, hurt, die;
  - *ShooterLib*: aims, crouch, prone, hands up, arrests, choke takedowns, equip moves;
  - a locomotion set marked faulty: idle, walk, run, turn left / right, jump.
- **Its format.** Godot binary resources (`.res`, zstd-compressed) on Godot's humanoid skeleton.
- **Verdict: not usable as it is.**
  - **No licence is declared**, so all rights are reserved by default. The old loom's notes (`kb-character.md`) call these libraries
    "CC0", but the repository itself says nothing of the kind.
  - Some clips still carry Mixamo's `mixamo_com` track.
  - It holds few acting moves: no sit, point, talk, gesture or pick up.

**The old loom already had the right pattern** beside it: a `mixamo_animations/` folder for Mixamo FBX files downloaded by hand.
It holds `Walking.fbx` and `Crouched Walking.fbx`. These are the author's own downloads, used locally; E23 can use the walk for Mara
without committing it.

**Where the motion can come from:**

| Source | What it holds | Terms | Use in loom2 |
| --- | --- | --- | --- |
| **Mixamo** (Adobe, a free account) | thousands of clips, acting included (sitting, talking, pointing, waving, walk variants), as FBX | free in your own films and games, no credit needed; you may **not redistribute the raw files** or build a library or dataset of them for others (Adobe's Mixamo FAQ; to be re-read against the live terms before we rely on it, D17) | the author downloads clips with their own account into a **local motion folder** outside the repo and the installers, and loom2 imports from it. Never bundled, never in CI, never a default of the `open` variant |
| **the starter set: Quaternius' *Universal Animation Library* 1 and 2 [Standard]** (fetched 2026-10-17 to `F:/loom2-models/motion/`, provenance and sha256 in its `SOURCES.md`) | 87 clips (below; plus a rest pose in each) and **skinned mannequins with fingers and feet**: a male (UAL1: 53 joints, Rigify `DEF-` names; UAL2: 65 joints, Unreal names) and a female on the same rig; glb and fbx | **CC0 1.0**, verified in each archive's `License.txt` | the clips that ship with loom2, in both variants; the mannequins are a candidate for a detailed dummy (§9) |
| the old Godot libraries above | game moves | none declared | not used |

**What the starter set holds** (clip names as in the files):

| For storyboards | Clips |
| --- | --- |
| standing, talking, reacting | Idle, Idle_Talking, Idle_FoldArms, Idle_TalkingPhone, Idle_No, Yes, Hit_Chest, Hit_Head, Hit_Knockback |
| moving | Walk, Walk_Formal, Walk_Carry, Jog, Sprint, Crouch_Fwd, Crouch_Idle, Push, Roll, Slide, Jump (start / loop / land), ClimbUp_1m, Swim |
| sitting, lying | Sitting_Enter, Sitting_Idle, Sitting_Talking, Sitting_Exit, LayToIdle, Death01, Driving |
| hands at work | PickUp_Table, Interact, Chest_Open, Consume, OverhandThrow, Fixing_Kneeling, Farm (harvest, plant, water), TreeChopping |
| action | punches, sword, shield, pistol, spell, melee hooks |
| other | Dance, Zombie (idle, walk, scratch), A_TPose (the rest pose) |

**Missing** for our shots: pointing, waving, turning on the spot, a step back. These stay pose presets and keys by hand until another
CC0 source or the author's Mixamo folder covers them.

**Getting Mixamo clips** (the author's own downloads):

1. Sign in at **https://www.mixamo.com** with a free Adobe account.
2. Pick a character (*X Bot* or *Y Bot* is fine; only the motion is kept) and search the *Animations* tab.
3. Download with these settings: *Format* FBX (binary or ASCII; both load), *Skin* **Without Skin**, *Frames per second* **24** (the
   project's rate), *Keyframe reduction* none.
   Untick *In Place* for walks, so the clip keeps its root motion.
4. Save the files into a local motion folder outside the repo, e.g. `F:/loom2-motion-mixamo/`, like the old loom's `mixamo_animations/`.

**Checked 2026-10-18: the author's first downloads load.** Seven clips in `mixamo/` (git-ignored) load in three.js's FBXLoader:

- FBX 7.7 ASCII, without skin;
- **65 `mixamorig:` bones** (spine ×3, fingers, toes), centimetres, Y up, **24 fps**;
- 0.7–13.8 s long;
- root motion kept where it should be: *Start Walking* +1.99 m forward, *Slow Jog Backwards* −1.26 m, *Zombie Stand Up* hips +0.65 m.
  *Body Block*, *Hip Hop Dancing* and *Double Dagger Stab* stay in place.

The importer scales them by 0.01.

**One by one is the only official way.** Unofficial browser scripts that bulk-download with your session exist, but they use Mixamo's
undocumented API and may conflict with Adobe's terms on automated access. Not recommended.

**Clips worth fetching first** (what the starter set lacks): pointing, waving, turns on the spot (left / right 90° and 180°),
stepping back, sitting down / standing up from a chair, talking gestures (several), nodding / shaking the head, looking around,
picking up / putting down, opening a door, a walk start and stop, a run start and stop, a phone call, reacting (surprise, laughing,
crying).

**The importer** (Stage is three.js, which has FBX and glTF loaders):

1. Load the clip and map its bones (Mixamo names `mixamorig:Hips`, …).
2. Correct the rest pose (T-pose → the mannequin's) and scale to the 1.75 m mannequin.
3. Retarget onto the mannequin's joints, keeping the hips' translation as **root motion**.
4. Bake to Stage keys at 24 fps, thinned.

On top of the clips:

- root motion along a **path drawn on the floor**;
- **foot lock**;
- trim, speed, and a **blend** from one clip into the next (a walk into a turn).

**A limit of the mannequin.** It has 12 joints: root, spine, neck, head, shoulders, elbows, hips and knees.

- On import, a spine chain collapses into one joint, and wrists, ankles, toes and fingers are dropped.
- The COCO-18 pose pass that guides Wan Animate needs none of them: its wrist and ankle points are the ends of the limbs. So the guide
  is unaffected, but foot roll and hand gestures are lost.
- A detailed dummy with hands and feet, and dummies for non-human characters, are an open question with proposed solutions in §9.

### 6) Keyframes and batches — ✎ revised (note 1)

**What the node can and cannot do.** Read from the pinned engine's `WanAnimateToVideo`:

- **`length`** is on a 4n+1 grid: 73, 77, 81, …
- **One output frame per pose frame.** The pose video sets the timing; nothing in the node knows the frame rate.
- **`continue_motion`** takes *any* images and places them as the batch's **fixed first frames**: the last
  `continue_motion_max_frames` of them, which can be 1, 5, 9, …
  - The node's own use is the previous batch's last frames, to make long videos.
  - It can equally be **a still**: a Stage keyframe still as a one-frame start.
- **There is no end-frame input.** Only the first frames can be fixed. Replace mode keeps the *background* from `background_video`, not
  the character.

**The frame rate: two ways, to measure (E23a).** The author's question was whether 72 frames could cover 3 s of Stage's 24 fps. They
can, if the pose sequence is fed at 24 fps:

| | **F16** | **F24** |
| --- | --- | --- |
| the pose sequence | resampled to 16 fps (Wan's training rate) | Stage's 24 fps frames as they are |
| one batch of 77 frames | 4.8 s | 3.2 s; with 5 frames carried over, **72 new frames = exactly 3 s of Stage** |
| to 24 fps | RIFE (D27): interpolated frames, ghosting risk on fast limbs | nothing to do; every frame is generated |
| GPU time per second of shot | 1× | 1.5× |
| the risk | interpolation | the model's motion prior is 16 fps: hair, cloth and secondary motion may move as if slowed down |

**Welding the batches.** The author asked: *"if Wan Animate follows the animation well, the welding of the batches should not be a big
problem, with the Stage-keyframe addition — or is it?"*

Mostly not, with one caveat:

- **The geometry welds by construction.** Both sides of a join are driven by the same Stage frames, and Wan Animate follows them
  (PCK 0.80–1.0, E19). The body is where Stage puts it on both sides.
- **The identity is re-anchored in every batch.** Wan Animate reads the animation reference in every batch. E17's chains lost the face
  because I2V continuations had only the previous frames to go on; here the reference is always present.
- **The caveat: appearance can drift.** Cloth folds, hair, colour and light drift over 72 frames. That is what a join shows, and what
  the weld must hide.

**No crossfade at a batch join** (the author, 2026-10-18). A batch join must be seamless, a continuous shot. Crossfades happen only
between Shots, in the cut. That settles the weld:

| | **W1 · chain** (the weld) | W2 · keyframe starts (retired for joins) |
| --- | --- | --- |
| batch N+1 starts from | the last 5 frames of batch N (`continue_motion`); those 5 frames are dropped from batch N+1's output, so the join is a plain cut inside continuous motion | a Stage keyframe still at the batch's first frame |
| the join | continuous by construction | needs a blend, because batch N's end never equals the still. It would be a crossfade, so it is not used |
| a re-take | that batch and every batch after it (the price of a seamless shot) | any batch alone |
| the risk | slow drift over a long Shot (cloth, hair, light) | — |

- **W3 repairs drift where it shows.** If E23a finds drift or a visible seam, the keyframe still for that frame becomes the reference
  of a healing patch (step 8, A6) over the few frames around the join. The join is repaired, not blended.
- **Keyframe stills stay useful** as batch 1's start (the first frame's exact look, pose and light), as the back view when a figure
  starts turned away, and as the references of W3.

E23a measures W1's seams and drift at F16 and F24, and tries W3 on the worst join.

**Batches for a 10 s shot (240 Stage frames), per layer:**

| | Batches | Wan Animate time per layer | Two characters |
| --- | --- | --- | --- |
| F16 | 3 (160 model frames, stride 72) | ≈ 15 min | ≈ 30 min |
| F24 | 4 (240 frames, stride 72) | ≈ 20 min | ≈ 40 min |
| a start still | one per layer for batch 1 (Exact pose ≈ 74 s warm) | + ≈ 1 min | + ≈ 2 min |

### 7) Wan Animate, layer by layer — Move and Replace, compared (note 3)

Wan Animate has two modes, and the choice decides how much compositing is needed. Spike E23b runs both on the **same shot, layers and
batches** and scores them side by side (02 §2).

| | **Move** (CN4 today) | **Replace** (the node's background-video input) |
| --- | --- | --- |
| Inputs per layer | the animation reference + the figure's pose sequence | the same + **the plate video** + **the figure's mask sequence** (Stage renders both) |
| Output | the character over its reference's background | the character **inside the plate**, relit by the model to the scene |
| Assembly | matte each layer per frame (SAM 3 per frame worked in E21; Stage's mask pass guides it), stack in depth order | chain the layers: plate → far figure → near figure, each run inserting one character into the previous result. **Paste back only the masked region** (dilated, feathered), so the background never drifts |
| Light and shadows | the character keeps its reference's light; shadows come from a Stage shadow pass | the model relights the character to the scene; contact shadows may come for free |
| The start still | on the reference's plain background | inside the plate |
| Risk | the light does not match; edges | each run re-renders the frame (hence the masked paste); the relighting is not measured on our engine yet |

**What E23b scores in both modes:**

- pose fidelity (PCK);
- identity (FaceSim);
- how the edges and the light sit (the band step at the layer edge);
- shadows against Stage's shadow pass;
- the background's stability (flicker, drift under a pasted layer);
- time and VRAM.

**Not possible in one run:** two figures in one pose pass. E19 measured that two overlapping figures are read as hands over a face. So
one figure per layer, always.

### 8) Post-processing — everything worth testing (note 4)

Following the author's note, post-processing is **three separate stages**, each tested on its own:

- **A · the layer pass**: per layer, before flattening.
- **B · the image stream**: the frames as files, and time.
- **C · the final polish**: one pass over the flattened shot.

**Measured so far.** E21 ran a Wan 2.2 low-noise v2v at σ 0.3 over a flattened clip. There was no visible gain, the background flicker
came back (0 → 0.94), faces got slightly worse (FaceSim −0.05), and it added 4–5 min per shot. Lower strengths and other models are
untested.

**A · The layer pass**

| # | What | Notes |
| --- | --- | --- |
| A0 | nothing | the baseline |
| A1 | **a different amount per layer**: the plate none (a still or a projection is stable by construction), the characters low, the hero more than the extras | the author's idea; the layer stack makes it free |
| A2 | a low-σ v2v per layer: the Wan 2.2 low-noise expert or LTX-2.3, **a different model per layer** if one suits faces and another cloth | on a Move layer, the layer's own background is re-rendered too; only the matte is kept |
| A3 | a **face-crop refine** per character per frame (the crop at ×2, Klein 9B with the character's references, pasted back feathered) | small faces are the weakest part at Draft size |
| A4 | per-frame image-to-image with the **neighbouring frames as references**: **Klein 9B (KV)** with up to 4 images (the frame, its neighbours, the animation reference), the faster model; **FLUX.2 dev** with up to 10 (the frame, its neighbours ± 2, the animation reference, and near a join the keyframe still, W3) | the author's idea. The neighbours pull each frame towards the detail of the frames around it, against flicker |
| A5 | **keyframe refine + propagation**: refine every 8th–12th frame (A3 or A4), and carry the change to the frames between along the optical flow (OpenCV, "EbSynth-style", no new engine node) | the flicker-safe variant of A4 |
| A6 | **a healing patch**: A4 on **a region over a frame range only**, e.g. a hand in frames 40–60, a face around a join, a sleeve that changed colour. The region is masked, refined with neighbours as references (FLUX.2 dev where it matters most, Klein 9B otherwise), and pasted back feathered | the author's idea. The whole shot does not have to pass through FLUX.2 dev: it repairs what the other stages leave |

Times are measured in the spikes, not estimated here (the author, 2026-10-17): first see what each spike gives.

**B · The image stream** (frames as files)

| # | What | Notes |
| --- | --- | --- |
| B1 | 16 → 24 fps with RIFE | exists (D27), with F16 |
| B2 | native 24 fps | F24; no interpolation (E23a) |
| B3 | refine the keyframes, then make the in-betweens from the refined frames (RIFE or flow) | combines with A5 |
| B4 | other delivery rates: up by interpolation (25, 30 fps), down by dropping frames | **later**: the delivery rate is 24 fps (the author, 2026-10-17), the project default |
| B5 | the master as PNG sequences with alpha, per layer | the layer pass and re-takes work on files; the h264 proxy stays for playback |

**C · The final polish** (one pass over the flattened shot, kept separate from A)

The requirement (note 4): the **most accurate and faithful** polish, one that **keeps the shadows and the lighting**.

| # | What | Notes |
| --- | --- | --- |
| C0 | nothing | the baseline |
| C1 | Wan 2.2 low-noise expert v2v at σ 0.1 / 0.2 | E21 measured σ 0.3 |
| C2 | LTX-2.3 v2v at a low strength | LTX broke the blocking as I2V (E22); as a low-strength v2v it starts from the shot |
| C3 | **structure-locked v2v**: LTX-2.3 with its IC-LoRA depth guide (Stage's *Render clip* guide, D76), fed the shot's own Stage depth sequence, starting from the flattened clip at a low strength (if the pinned engine's core nodes allow it) | holds the geometry and where the shadows fall while it unifies the light. The candidate I expect most from |
| C4 | Wan VACE v2v with a depth or pose control | Apache-2.0, but not installed: a download, so a decision |
| C5 | A4 over the flattened frames (Klein 9B or FLUX.2 dev with neighbours), or A6 on the flattened frames (a healing patch where the polish left a fault) | |

**Measures for C:**

- **faithfulness:** SSIM / LPIPS to the input outside the faces;
- **shadows and light kept:** the shadow regions' luminance and outline against the input;
- **temporal stability:** optical-flow warping error, flicker in static regions;
- **identity:** FaceSim;
- **time.**

**The last step of every route:** the batch joins are cuts inside continuous motion (no crossfade, W1), conform to the delivery rate (B1 / B2 / B4), and deliver the clip as a **take on
the Story shot** (D93's `for_shot`). The Episode exports it as today.

## 3. The refined pipeline

```
Story ─ World style · Cast characters (sheet, versions, an animation reference per version: 16:9, full body, A-pose)
  │
Stage ─ set from blocks + shot camera ─► empty-set clay/depth pass ─► PLATE still (Clay reference, the World style)
  │      figures bound to characters (D93 C), a key light matching the plate, layers
  │      motion: the library (imported, retargeted) + presets + keys by hand · camera keys        (24 fps timeline)
  │      moving plate: projection (small moves) / depth-guided plate video (large moves)
  │
Batch planner ─ F16 or F24 (E23a) · 77 frames, 5 carried / 72 new · W1 chain, seamless (no crossfade)
  │             per batch: plate frames; per figure: pose and mask sequences, a start still, a shadow pass (Move)
  │             the cost shown before anything runs (D79's pattern)
  │
THE PERFORMANCE ─ per layer, per batch: Wan Animate (Move or Replace, E23b), one figure per run
  │
Assembly ─ Replace: masked paste, far → near   |   Move: per-frame matte (SAM 3 guided by Stage's mask), depth order, shadow pass
  │         batch joins: plain cuts in continuous motion (W1; W3 repairs a visible seam)
  │
THE FINAL (E24) ─ A layer pass (per layer, its own amount) ─► B image stream (rate, in-betweens) ─► C final polish (flattened)
  │
a take on the Story shot ─► Episode
```

## 4. What exists and what is new

| Piece | Exists | New |
| --- | --- | --- |
| Characters, sheets, versions | D85, D93 A/B | **the animation reference per version, at casting** (16:9, A-pose, colours bound); an optional back view and test animation |
| Sets, figures bound to characters, cameras | ST1–ST3, D93 C8 | layers, a key light |
| Keyframes: transforms, joint poses, camera | ST4 | **the motion library**: an FBX / glTF importer with retargeting, root motion along a path, foot lock, blends; a local motion folder; a starter set |
| Pose / depth / mask passes per figure, sequences | ST3/ST4, CN4 | 16 or 24 fps, batches with overlap |
| Wan Animate from a pose sequence (Move), one figure | CN4 (D87) | Replace mode (plate video + mask); chaining (W1), seamless; W3 repairs |
| Keyframe stills of one figure in its pose | Exact pose with the binding (D78, D93 C) | per batch, in the plate (Replace) |
| Plate from the empty set | E21 (spike code) | in the app; 2.5D projection along the camera path; a depth-guided plate video |
| Per-frame masks | E21 (SAM 3 per frame, spike code) | in the app (for Move) |
| Compositor | E21 (spike code, 16 s CPU per shot) | in the app, depth order per frame, shadow pass |
| Post-processing | E21 (Wan v2v, spike code) | the layer pass, the image stream and the final polish (whatever E24 keeps) |
| 16 → 24 fps conform | D27 (export) | per take; or none with F24 |
| Takes on a Story shot | D93 | — |

## 5. What it rests on (measured)

| Measurement | Source |
| --- | --- |
| Wan Animate follows a Stage pose pass: PCK 0.80–1.0, 77 frames in 264–297 s at 832×480; one figure per pass (two overlapping figures fail) | E19, CN4 (19 §2, §6) |
| A reference image cropped instead of padded paints a ghost into the background; the node centre-crops the reference to the clip's size | E19; `WanAnimateToVideo` in the pinned engine |
| `continue_motion` fixes the first frames of a batch with any images (1, 5, 9, …); there is no end-frame input | `WanAnimateToVideo` in the pinned engine |
| Chained I2V continuations lose the face at the first join (Wan + RIFE weld kept it better than LTX guide frames) | E17 |
| A plate from the empty set's clay pass matches the figures' perspective; per-frame SAM 3 masks follow a gesturing character; a merged layer keeps each character's identity (± 0.004 vs alone) with invisible seams | E21 |
| A σ 0.3 Wan v2v pass over a merged clip: no visible gain, flicker back, faces −0.05, +4–5 min | E21 |
| Wan Animate with a drawn pose: gestures smaller and faces weaker than plain I2V | E21 (*banim*) |
| Two characters from one prompt take turns; layers act at once but cannot touch; Wan at Draft does not really walk; LTX-2.3 breaks the blocking | E22 |
| Peak VRAM of Wan Animate 12.8–13.5 GB; plate and stills ≤ 12.3 GB | E21 |
| The Exact pose method has one reference slot (enough for a one-figure keyframe still) | journal 2026-10-17 18:03 |
| FLUX.2 dev takes up to 10 references, Klein up to 4; dev runs 290–560 s an image under RAM pressure today | `models/specs`; journal 2026-10-17 18:03 |

## 6. Risks

- **Authoring the motion.** The library (step 5) is the mitigation. Its licence decides what ships: Mixamo stays in the author's local
  folder.
- **The coarse rig.** No wrists, ankles or fingers: hand gestures and foot roll are lost on import (§9).
- **Non-human characters.** Wan Animate's guide is a human skeleton; creatures need another dummy and possibly another guide (§9).
- **Liveliness.** Pose-driven motion is exact but can look stiff, with smaller gestures than free I2V (E21 banim). Faces and expressions
  come only from the model, because the mannequin has none.
- **Joins.** Appearance drift across W1's joins over a long Shot. Unmeasured on our engine; W3 repairs it.
- **F24.** Secondary motion may look slowed down, because the model's prior is 16 fps.
- **Light integration.** Move keeps the reference's light; Replace's relighting is unmeasured.
- **Hands and held props.** The mannequin has no fingers. A prop held across a join may change.
- **Camera moves.** The projected plate stretches where the camera sees behind objects; a depth-guided plate video may breathe.
- **Post-processing.** Flicker (A4 / C5 without temporal care). Time is measured per stage in E24; FLUX.2 dev is the slow model, which
  is why it is used as a healing patch (A6) where it matters, and Klein 9B where speed does.

## 7. Questions for the author

Answered by the notes of 2026-10-17 (§8):

- ~~motion authoring~~ → a motion library, imported (note 5);
- ~~one reference per shot or per batch~~ → one animation reference per version, made at casting (note 6); keyframe stills per batch
  were tested as W2, now retired for joins (no crossfades, 2026-10-18);
- ~~post-processing priority~~ → test everything, in three separate stages (note 4).

Answered in the second round (2026-10-17):

- ~~a CC0 starter library~~ → fetched: Quaternius' UAL 1 + 2 (step 5). Mixamo: the author downloads clips as in step 5.
- ~~the delivery rate~~ → 24 fps, the project default. 25 fps would only matter for a European TV broadcast master (PAL); for
  pre-production, festivals and streaming 24 is the norm. B4 is later.
- ~~the time budget~~ → judged after the spikes, not before. FLUX.2 dev is a healing patch where it matters (A6), Klein 9B the faster
  per-frame option.

Answered in the third round (2026-10-18):

- **Camera moves:** small moves first, but **no limit**. The projected plate covers small moves; the depth-guided plate video is
  needed for large ones and stays in the plan (CA3).
- **Joins:** **no crossfades at batch joins**; crossfades only between Shots, in the cut. The weld is W1 (step 6), with W3 repairs.
- **Size:** **Draft (832×480) first, HD later.**
- **Props:** **exactly like characters, except the skeleton** (§10).
- **Lip-sync:** **test it in this route** (§11, spike E29).
- **Dummies:** two editing levels; humanoids are enough for now; the Cast sheet carries the body (§9).

Nothing in this section is open now.

## 8. The author's notes of 2026-10-17 and where they went

| Note | Reflection | Where |
| --- | --- | --- |
| 1 · Wan Animate's output is a model of the final, like the clay; 72 frames = 3 s of Stage at 24 fps?; Stage keyframes for the welding | Agreed. The performance is the second proxy, and post-processing becomes the render. 72 new frames per batch cover exactly 3 s if the poses are fed at 24 fps (F24); the node has no frame rate of its own. The welding: the geometry welds by construction and the identity is re-anchored in every batch, so the risk left is appearance drift. Keyframe stills can start every batch through `continue_motion` (W2), which also makes each batch re-takeable alone | §1, step 6; E23a |
| 2 · Swap steps 3 and 4 | Done: the Stage with its set comes first, the background is generated from it. The *moving* plate still comes after the camera keys (step 5) | steps 3, 4 |
| 3 · Compare the two modes of step 7 | E23b compares Move and Replace on the same shot, layers and batches, with one scoring | step 7; 02 §2 |
| 4 · Test every post-processing idea; a different amount and v2v model per layer; FLUX.2 dev with neighbouring frames as references; the image stream for frame rates and in-betweens; the layer pass separate from a final faithful polish that keeps shadows and light | All listed, in three stages: A layer pass (A1 the amount per layer, A2 models per layer, A4 neighbours as references), B image stream (B1–B5), C final polish (C1–C5, with C3 the structure-locked candidate). Times are measured in the spikes (note 10) | step 8; E24 |
| 5 · The Mixamo library in the old loom repo | The checkout is catprisbrey's Godot libraries (game moves, no licence; the Mixamo files were removed for Adobe's terms), so not usable. Mixamo itself is free to use in your own films but not to redistribute, so: an importer in loom2, Mixamo clips in your local folder (the old loom's `mixamo_animations/` already holds a walk), a CC0 starter set shipped (fetched in the second round, note 8) | step 5; CA1 |
| 6 · Animation references at casting | Agreed: one per Cast version, made at casting, at 16:9, with an optional back view and test animation | step 2; CA0 |
| 7 · *(second round)* A detailed dummy with hands and feet, optional; dummies for non-human characters | An open question with proposed solutions | §9 |
| 8 · *(second round)* Get the open starter library; where to get Mixamo | Fetched (CC0, UAL 1 + 2, with skinned mannequins); the Mixamo steps written down | step 5 |
| 9 · *(second round)* 24 fps is the default; why 25? | 24 stays; 25 matters only for a European TV master | §7, B4 |
| 11 · *(third round, 2026-10-18)* Camera moves: small first, no limit · no crossfades at batch joins (only between Shots) · Draft first · props like characters without a skeleton · test lip-sync · two-level dummy, humanoids now, the body on the Cast sheet | W1 is the weld (W2 retired, W3 repairs); the depth-guided plate stays; §10 props (P1–P3, E28); §11 lip-sync (L1–L3, E29); §9 answers | steps 4, 6; §7; §9–§11 |
| 10 · *(second round)* Times after the spikes; FLUX.2 dev as a healing patch on some areas; Klein 9B the faster option | Agreed: time estimates removed, A6 added, Klein 9B named first for per-frame work | step 8 |

## 9. A detailed dummy, and dummies for non-human characters (answered 2026-10-18)

The author (2026-10-17): *"Is it possible to upgrade the clay dummy to have proper hands and feet? Perhaps optional, if we want to focus
on detailed hand / feet animation. We might also need to think about customising dummies for non-human animation (monsters, aliens …)."*

Yes to both, with limits that come from the guide, not from Stage.

**What decides it: the guide Wan Animate reads.**

- Wan Animate is driven by a **human pose skeleton**. Ours is COCO-18: body only, no hands, no feet. Wan's own preprocessing draws a
  DWPose-style skeleton, which adds **21 points per hand** (and the face); COCO-WholeBody adds **6 foot points**.
- A detailed dummy therefore helps twice: in Stage (the poses look right, hands can hold things), and possibly in the guide, *if* Wan
  Animate follows drawn fingers. **That is untested**; a short spike settles it (below).
- A **non-human** character works through Wan Animate only if its body can be read as a human skeleton. Otherwise it needs a different
  guide (depth, silhouette) and a different video model.

### 9a · Hands and feet — three ways

| | **H1 · Detailed dummy from the starter set** | **H2 · Extend today's dummy** | **H3 · Both, a detail level per figure** |
| --- | --- | --- | --- |
| What | Quaternius' CC0 skinned mannequins (fetched; male and female, the same rig): 65 joints with spine ×3, clavicles, **fingers (4 bones each), foot + ball** | add wrists, ankles and toes, and "mitten" hands (a thumb + the four fingers as one) to the procedural 12-joint dummy | *Simple* (today's, fast to pose by hand) or *Detailed* (H1) per figure, switchable; the keys map between them |
| Library clips | play **natively**, no retargeting loss (they were made on this rig) | retargeted; fingers collapse into the mitten | natively on Detailed; retargeted on Simple |
| Hand poses | hand presets (open, relaxed, fist, point, grip, pinch) as finger keys; the clips' own finger motion | open / closed / point only | as H1 |
| The pose pass | COCO-18 + hands (21 points each, OpenPose hand order) + feet (6) | COCO-18 + a wrist direction + feet | per figure |
| Proportions | male and female builds; bone scaling for height and build (from the Cast sheet) | the procedural sizes, already parametric | both |
| Cost | medium: a skinned glb in Stage, a joint-picking and posing UI for 65 joints (IK helps: the hands and feet are chain ends) | small | H1 + a mapping |

**Proposal: H3**, with H1 as the Detailed level. The starter set's clips then play without loss on Detailed figures, and Simple stays for
blocking. The Simple dummy keeps E10's clay-reference results (PCK 0.86), so it should not be replaced blindly. Clay, depth and mask
passes of the skinned mannequin are re-checked with the Klein clay reference before it becomes a default.

**Spike E25 (½ day; before CA1 builds the Detailed level):** one character, one clip with clear hand action (PickUp_Table, Idle_Talking),
Wan Animate driven by COCO-18 alone vs COCO-18 + hands + feet. Measured: hand PCK against Stage's hand points, finger counts by eye,
foot sliding. If the hands do not help the guide, Detailed is still worth having for posing and the clay stills, but the pose pass stays
body-only.

### 9b · Non-human characters — by body plan

| Body plan | Examples | Dummy | Guide and model |
| --- | --- | --- | --- |
| **N1 · Humanoid, other proportions** | an orc, a grey alien, a robot, a child, a giant | the human dummy with **proportion controls**: limb lengths, head size, torso, hands; extra parts as rigid attachments that follow a bone (tail, horns, wings folded, antennae) | **Wan Animate as today.** The skeleton stays human, and the reference image gives the look. Attachments are not in the pose pass, so their motion is the model's guess (a tail sways or not) |
| **N2 · Humanoid + moving extras** | wings that flap, a tail that whips, tentacle arms | N1 + extra bone chains on the attachments (keyed or procedural) | Wan Animate for the body; the extras need the **depth / mask guide** of the dummy as a second signal: either a depth-guided pass over the layer (LTX IC-LoRA depth, as Stage's *Render clip* does), or the extras as their own layer |
| **N3 · Not humanoid** | a dog, a horse, a dragon, a spider, a snake, a blob | an imported **rigged model** (glb) posed by its own bones; CC0 animated animals and monsters exist (Quaternius has several packs; to verify); or image → mesh (Pixal3D, full variant only) and an auto-rig (Puppeteer, Apache-2.0 code, in the old loom repo; its weights' licence and UniRig's to check) | **not Wan Animate**: a human pose skeleton cannot describe a quadruped. The guide is the dummy's **depth (+ mask) sequence**, driving a depth-guided video model with the creature's reference: LTX-2.3 + IC-LoRA depth (exists, D76), or Wan VACE with depth control (a download, a decision). Then layered like any other figure |

**Proposal:** N1 first. It is small (bone scaling + attachments) and covers most monsters and aliens in a storyboard. N3 is a separate
route, the depth-guided performance, which needs its own spike (E26) before any build: one quadruped clip from a CC0 rigged animal,
LTX IC-LoRA depth vs Wan VACE depth, against the bars of E23 (identity, the shape kept, background stable).

**Answered by the author, 2026-10-18:**

1. **Two editing levels on one figure.** H3 is refined as one figure with two levels, not a per-figure choice:
   - the **Simple** dummy blocks the coarse movement;
   - the **Detailed** dummy (the starter set's skinned mannequin, 65 joints) refines hands, feet and the finer movement.

   Keys made on Simple map onto Detailed (the shared joints). Refining adds the fingers, wrists, feet and the spine chain. The pose pass
   uses the Detailed figure once it is refined (E25 decides whether it also draws hands).
2. **Humanoids are enough for now (N1):** proportion controls and attachments. N2 and N3 are later.
3. **Yes, the Cast sheet carries the body:** height, build, proportions and attachments shape the figure's dummy (CA0).

## 10. Props — exactly like characters, except the skeleton

The author (2026-10-18): props *"are going to [work] exactly like characters, except for the skeleton."*

| Characters | Props |
| --- | --- |
| a Cast character with versions and a sheet | a **Cast prop** with versions and a sheet (Cast already has props, D85: "Make a character / place / prop") |
| an animation reference per version (full body, 16:9) | an animation reference per version: the prop alone, centred and padded, 16:9, from a three-quarter view |
| a Stage figure bound to the character (D93 C8) | a Stage **prop object bound to the Cast prop**, the same binding |
| motion from the skeleton: library clips, keys, root paths | motion from **transform keys** only (position, rotation, scale) and **parenting**: a held prop is parented to the holder's hand (the Detailed dummy's hand bone) |
| its own layer | **its own layer**; when held, its own layer parented to the hand, or drawn inside the holder's layer |
| Wan Animate (pose-driven) | **no pose skeleton**, so another performance method (below) |

**How a prop is performed** (spike E28 measures which):

- **P1 · rigid, as a cut-out.** A prop that only moves (a cup carried, a box slid) is its reference still, cut out, and animated by its
  transform keys in the composition (EffectCraft), lit by the shadow pass. No video generation, so it is cheap. It cannot show a new side.
- **P2 · depth-guided.** A prop that turns or changes (a door opening, a car turning, a book opened) uses its depth and mask sequence
  from Stage to drive a depth-guided video model (LTX-2.3 + IC-LoRA depth, which exists; D76), with its reference. This is the N3
  route of §9b, for an object.
- **P3 · with its holder.** A small held prop drawn inside the character's layer by Wan Animate. It is in the reference image, but the
  pose guide does not know it, so it may drift. It is measured, not assumed.

**Spike E28 (≈ 1 day):** one rigid prop (P1), one opening door (P2) and one held cup (P1 parented vs P3), in E22's set. Measured: the
shape kept, identity against the prop's reference, the contact with the hand, the shadow, time.

## 11. Lip-sync in this route — to test (spike E29)

The author (2026-10-18): *"we should test lip-sync."* What exists:

- **D88's experimental lip-sync:** Wan 2.2 S2V, English, ≤ 4.8 s, sync r 0.635 at Fast, 282 s.
- **Wan Animate's own *face video* input:** a driving video of a face moves the character's expressions while the pose guide moves the
  body.

Three routes for a talking layer:

| Route | How | Risk |
| --- | --- | --- |
| **L1 · S2V as the layer** | the character's talking clip from S2V (its animation reference + the voiced line), used as that character's layer | S2V does not follow the Stage pose: the body moves its own way |
| **L2 · S2V drives Wan Animate's face** | an S2V talking head of the character (or a cropped face from L1) is the **face video** of the Wan Animate run, whose body follows the Stage pose | two runs per batch; does the mouth survive Wan Animate? |
| **L3 · a lip-sync post pass** | a dedicated mouth-replacement model over the finished layer | a new custom node, so a decision (house rule 2) with a licence check |

**Spike E29 (≈ 1 day):** one character, one English line of about 4 s, in a Stage shot with body motion. L1 against L2, and L3 only if
the author approves a candidate. Measured: lip-sync (E18's metric r), body PCK against the Stage pose (must not drop for L2), identity,
time.
