# 01 · Animation from clay — the pipeline, reviewed

Status: **proposal, 2026-10-17.** For the author to refine; no decision yet (00).

## 1. The idea

Every character is animated alone, precisely, and the shot is assembled from the pieces:

- the **motion** comes from Stage: mannequins keyed in 3D, with a keyed camera;
- each character's **look** comes from its Cast reference image;
- **Wan 2.2 Animate** turns "this character image + this pose sequence" into a clip of that character performing exactly that motion;
- the clips are layered over a background that moves with the same camera.

Why this route: our video models animate *one* character well, but not two from one prompt (E21, E22). Stage gives exact positions, paths,
facing and camera moves. Wan Animate follows a Stage pose pass closely: E19 measured PCK 0.80–1.0 over 77 frames, and CN4 (D87) built it
into Stage as the "Wan Animate" clip method. What is missing is the assembly: several characters, several batches, a moving background,
and the joins between them.

## 2. The author's workflow, step by step

The author's eight steps, each with a short review. ✔ means it works as described, ✎ means a change is suggested, ⚠ means a risk.

### 1) Set up the World, templates and styles — ✔

This exists: World, the Library (D92) and styles as images. One addition: the shot's **World style** should be applied to *both* the
background plate and the character references. Otherwise the layers come out in two visual styles.

### 2) Generate one or many characters — ✔ with one addition

This exists: Cast characters (D85), Give a look / Add to character (D93 A), the character sheet and versions as costumes (D93 B).

**Addition, an animation reference per version.** Wan Animate takes **one** image of the character. It works best with a **full-body,
front-facing, neutral pose on a plain background**, padded into the frame rather than cropped (E19: a cropped portrait painted a ghost into
the background).

- Cast's coverage grid already has full-body cells. A version should mark one of them as *the animation reference*, or Cast should offer
  "Make an animation reference": a full-body front shot from the version's sheet and references.
- Costume colours bound on the sheet (D93 B) keep the outfit stable. The E21 still drifted a jacket from yellow to olive.

### 3) Generate background images — ✎ generate them *from the Stage*, after step 4

A background generated on its own will not match the Stage camera: its perspective, lens, horizon and floor plane differ, so the
characters stand on the wrong ground, at the wrong scale.

Suggested order instead:

1. Build the set in Stage from blocks (walls, floor, table) with the shot's camera.
2. Render the **empty set's clay and depth pass** from that camera.
3. Generate the **plate** from it with the Clay reference method, as E21 did. The perspective then matches the mannequins exactly.

**Camera moves.** One still plate cannot move with the camera; there would be no parallax. Three options, by size of move:

| Camera move | Plate | Cost |
| --- | --- | --- |
| none (locked off) | one still plate | one image (≈ 15 s) |
| small: pan, tilt, a short dolly | the plate **projected onto the set's blocks** and re-rendered along the camera path in Stage (2.5D camera projection: three.js, no GPU job) | seconds; edges can stretch where the camera sees behind objects |
| large: an orbit, a long move | a **plate video** guided by the empty set's depth sequence (Stage's existing *Render clip* with the IC-LoRA depth guide) | ≈ 2–5 min per batch; the background may "breathe" |

The plate video can also be generated per batch from a plate keyframe, so the projection only has to cover one batch.

### 4) Create a Stage and add characters and background — ✔ mostly exists

This exists: figures bound to Cast characters with a version (D93 C8), sets, props, image planes, cameras.

New pieces:

- **The background as a projection** onto the set (step 3's small-move plate).
- **A key light** whose direction matches the plate's light. It is used for a shadow pass (§3, CA5).
- **Layers:** which objects go into which layer. By default each figure is its own layer and the set is the plate. A held prop belongs to
  its character's layer.

### 5) Draft animation and camera moves in Stage — ✔ exists, ✎ authoring is the bottleneck

This exists: keyframes for every object's position and rotation, **joint poses keyed over time** (interpolated between keys), and camera
keys (position, target, focal length) with linear or eased transitions, plus timeline playback (ST4, D81).

**The bottleneck is authoring.** Keying every joint of a walk by hand is slow, and it is what makes or breaks this route. Options, which
could be combined:

| Option | Effort to build | Effort to use | Notes |
| --- | --- | --- | --- |
| **Motion presets**: walk cycle, turn, sit down, stand up, pick up, point, wave, nod — keyframe templates dropped onto a figure, the walk following a path drawn on the floor (root motion), the feet held on the ground (foot lock) | medium | low | the natural next step after pose presets; no licence questions |
| **Motion import (BVH)**: a motion-capture file retargeted onto the mannequin rig | medium | low | depends on a motion library whose licence fits D17 / D26 |
| **Pose from a reference video**: estimate the pose of a filmed or found clip (DWPose / SAM 3 keypoints) and retarget it | high | low | very natural ("act it out on the phone"); estimation errors need cleaning |
| **Keys by hand** (today) | — | high | always available for fine-tuning |

### 6) Keyframes at the first and every 77th frame; per-batch animations from Stage — ✎ four corrections

The batch idea is right. Wan Animate makes **77 frames** per run (its spec: `frames = 77`, a 4n+1 grid), so a long shot is split into
batches. Four points change the details:

1. **Wan Animate has no end-frame input.** In the pinned engine's `WanAnimateToVideo` node it takes a reference image, a pose video, an
   optional face video, an optional background video with a character mask, and **`continue_motion`**: the last frames of the previous
   batch (default 5). So a batch's end cannot be pinned to a keyframe. Instead, **batch N+1 starts from batch N's last frames**, which is
   the node's own way to make long videos (`video_frame_offset`). A *start* keyframe per batch is still useful (point 3), but an *end*
   keyframe is not possible with this model.
2. **Frame units.** Stage's timeline runs at the project's **24 fps**; Wan Animate generates at **16 fps**. A 77-frame batch is
   **4.8 s ≈ 115 Stage frames**, not 77. So the batch planner:
   - resamples each figure's pose sequence to 16 fps;
   - plans batches in the model's frames;
   - converts the result back to 24 fps at the end (RIFE, as D27 already does for Wan clips).
3. **Overlap and stride.** With 5 frames of `continue_motion`, consecutive batches share 5 frames, so the stride is **72 frames**
   (4.5 s). The shared frames are crossfaded at the join. A 10 s shot is 3 batches per layer.
4. **A reference image per layer, not a new keyframe still per batch.** Changing the reference image between batches risks the face
   jumping at the join; E17 lost the face at the first join of a chained I2V clip. Suggested:
   - **one reference per character per shot** (the animation reference, step 2);
   - optionally, a **start-of-shot still** rendered from Stage for that figure alone (Clay or Exact pose with its binding, D93 C), when the
     first frame's look (pose, scale, light) must match the plate exactly.
   - Batches after the first carry their look forward through `continue_motion`.

"Everything animated separately, from the same Stage animation" works: every layer's pose sequence and the plate come from the same
document, the same camera keys and the same frame range, so they line up by construction.

### 7) First/last frames and the batch clay animations go to Wan Animate, layer by layer — ✎ two ways to run a layer

Wan Animate has two modes, and the choice decides how much compositing is needed:

| | **Move** (CN4 today) | **Replace** (the node's background-video input) |
| --- | --- | --- |
| Inputs per layer | the character image + its pose sequence | the character image + its pose sequence + **the plate video** + **the figure's mask sequence** (Stage renders both) |
| Output | the character over its reference image's background | the character **inside the plate**, relit by the model to the scene |
| Assembly | matte each layer per frame (SAM 3 per frame worked in E21; Stage's mask pass is the guide), stack in depth order | chain the layers: plate → far figure → near figure, each run inserting one character into the previous result; **paste back only the masked region**, so the background never drifts |
| Light and shadows | the character keeps its reference image's light; shadows come from a Stage shadow pass | the model relights the character to the scene; contact shadows may come for free |
| Risk | the light mismatch; edges | each run re-renders the frame (hence the masked paste); the relighting is not measured on our engine yet |

Replace looks like the better fit, but it is unmeasured. Spike E23 compares both (02 §2).

**Not possible in one run:** two figures in one pose pass. E19 measured that two overlapping figures were read as hands over a face.
So one figure per layer, always, which is what the author proposes anyway.

### 8) Post-processing — ⚠ the options, with what we already measured

**(a) A video-to-video pass, after flattening or per layer.** E21 tested one: Wan 2.2's low-noise expert at σ 0.3 over the flattened
clip.

- **Result:** no visible improvement; the background flicker came back (0 → 0.94); faces got slightly worse (FaceSim −0.05); 4–5 min
  per shot.
- **Lower strengths** (σ 0.1–0.2), or LTX as the v2v model, are untested.
- **Per layer before flattening** cannot harmonise anything, because light and edges only meet in the flattened frame. It could only
  repair a character's identity.
- **Verdict:** keep it as a candidate at low strength. If Replace mode (step 7) relights the characters already, (a) may not be needed.

**(b) Export frames and run a per-frame image-to-image refine (FLUX.2 dev, Klein 9B).**

- **What it does well:** the single-frame quality is excellent; our Refine keeps a composition at strength 0.3 (D89 measurements).
- **The problem is time.** Each frame is refined on its own, so hair, folds, textures and faces come out slightly differently on every
  frame. The result **flickers**, even with a fixed seed. Per-frame refine is the classic flicker source in AI video.
- **Mitigations to test:**
  - a very low strength (0.1–0.2) with the same noise on every frame;
  - **refine only keyframes** (every 8th–12th frame) and **carry the change to the frames between them along the motion** (optical-flow
    propagation, "EbSynth-style" — plain OpenCV, no new engine node);
  - **refine only the face crop** of each character per frame (small faces are the weakest part at Draft size), then paste it back
    feathered.
- **Per layer, then flatten, then again on the whole frame:** the per-layer pass can only repair identity, and every extra pass adds
  flicker.
- **Verdict:** promising for *detail and identity*, risky for *stability*. It needs measuring with temporal metrics before it goes in.

**(c) Suggested order of preference, to confirm in E24:**

1. Nothing: Replace mode plus a Stage shadow pass may be enough at Draft.
2. Face-crop refine per layer, if faces are the weak point.
3. Keyframe refine + flow propagation for detail.
4. A low-strength v2v pass only if the light still does not sit.

The last step of every route: conform 16 → 24 fps (RIFE, D27), crossfade the batch joins, deliver the clip as a **take on the Story shot**
(D93's `for_shot`), and the Episode exports as today.

## 3. The refined pipeline

```
Story ─ World style, Cast characters (sheet, versions, an animation reference per version)
  │
Stage ─ set from blocks + shot camera ─► empty-set clay/depth pass ─► PLATE (Clay reference, the World style)
  │      figures bound to characters (D93 C), key light matching the plate
  │      motion: presets / imported / keyed poses + camera keys          (24 fps timeline)
  │
Batch planner ─ shot range → batches of 77 model frames at 16 fps, 5-frame overlap (stride 72)
  │             per batch: the plate (still / projected / depth-guided video), per figure: pose sequence, mask sequence,
  │             shadow pass; the cost shown before anything runs (D79's pattern)
  │
Per layer, per batch ─ Wan Animate (Move or Replace — E23), continue_motion from the previous batch, one figure per run
  │
Assembly ─ Replace: masked paste, far → near    |    Move: per-frame matte (SAM 3 / Stage mask), depth order, shadow pass
  │
Post (E24) ─ none / face-crop refine / keyframe refine + flow / low-σ v2v
  │
Conform ─ 16 → 24 fps (RIFE), crossfaded joins ─► a take on the Story shot ─► Episode
```

## 4. What exists and what is new

| Piece | Exists | New |
| --- | --- | --- |
| Characters, sheets, versions | D85, D93 A/B | the animation reference per version |
| Sets, figures bound to characters, cameras | ST1–ST3, D93 C8 | layers, a key light |
| Keyframes: transforms, joint poses, camera | ST4 | motion presets, root motion along a path, foot lock (import / pose-from-video later) |
| Pose / depth / mask passes per figure, sequences | ST3/ST4, CN4 | resampling to 16 fps, batches with overlap |
| Wan Animate from a pose sequence (Move), one figure | CN4 (D87) | Replace mode (plate video + mask), `continue_motion` chaining |
| Plate from the empty set | E21 (spike code) | in the app; 2.5D projection along the camera path; a depth-guided plate video |
| Per-frame masks | E21 (SAM 3 per frame, spike code) | in the app (for Move) |
| Compositor | E21 (spike code, 16 s CPU per shot) | in the app, depth order per frame, shadow pass |
| 16 → 24 fps conform | D27 (export) | per take |
| Takes on a Story shot | D93 | — |

## 5. What it rests on (measured)

| Measurement | Source |
| --- | --- |
| Wan Animate follows a Stage pose pass: PCK 0.80–1.0, 77 frames in 264–297 s at 832×480; one figure per pass (two overlapping figures fail) | E19, CN4 (19 §2, §6) |
| A reference image cropped instead of padded paints a ghost into the background | E19 |
| Chained I2V continuations lose the face at the first join (Wan + RIFE weld kept it better than LTX guide frames) | E17 |
| A plate from the empty set's clay pass matches the figures' perspective; per-frame SAM 3 masks follow a gesturing character; a merged layer keeps each character's identity (± 0.004 vs alone) with invisible seams | E21 |
| A σ 0.3 Wan v2v pass over a merged clip: no visible gain, flicker back, faces −0.05, +4–5 min | E21 |
| Wan Animate with a drawn pose: gestures smaller and faces weaker than plain I2V | E21 (*banim*) |
| Peak VRAM of Wan Animate 12.8–13.5 GB; plate and stills ≤ 12.3 GB | E21 |
| The Exact pose method has one reference slot | journal 2026-10-17 18:03 |

**Time, as a rough guide:** a 10 s two-character shot at Draft = 3 batches × 2 layers × ≈ 5 min ≈ **30 min** of Wan Animate, plus the
plate (≈ 15 s) and assembly (≈ 1 min). Replace mode is probably similar per run.

## 6. Risks

- **Authoring the motion** is the real cost for the author, not the GPU time. Without presets the route is precise but slow to use.
- **Liveliness:** pose-driven motion is exact but can look stiff, with smaller gestures than free I2V (E21 banim). Faces and expressions
  come only from the model, because the mannequin has none.
- **Joins:** chaining with `continue_motion` is unmeasured on our engine. E17's chains lost the face, though those were I2V continuations
  without a pose guide.
- **Light integration:** Move keeps the reference image's light. Replace's relighting is unmeasured.
- **Hands and held props:** the mannequin has no fingers. A prop held across a batch join may change.
- **Camera moves:** the projected plate stretches where the camera sees behind objects; a depth-guided plate video may breathe.
- **Post-processing flicker** (8b) if used without temporal care.

## 7. Questions for the author

1. **Motion authoring:** presets first (walk, turn, sit, pick up, point, wave, nod), or importing motion (BVH; licence?), or pose from a
   video you film?
2. **Camera moves:** are small moves (pan, tilt, a short dolly) enough at first? They allow the cheap projected plate.
3. **Joins:** is a short crossfade (5 frames) at each 4.5 s join acceptable?
4. **Reference image:** one per character per shot, so the face stays the same, or one per batch, so pose and light match better?
5. **Post-processing priority:** faces and identity, light integration, or overall detail?
6. **Final size and time budget:** Draft (832×480) first and HD later, and how long may one 10 s shot take?
7. **Props:** a held prop goes in its character's layer; should free props (a door, a car) be their own layers?
8. **Faces and lip-sync:** do talking shots need lip-sync in this route soon? Wan Animate can take a *face video* to drive expressions,
   and S2V is the experimental lip-sync (D88).
