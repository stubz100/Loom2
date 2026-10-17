# 02 · Animation from clay — implementation plan

Status: **proposal, 2026-10-17.** It follows the reviewed pipeline in [01](01-clay-animation.md). Order: the author refines 01 → two
spikes (§2) → a decision (D-number, §3) → the build waves (§4). Each wave ends measured on the rig, as every wave has ("no milestone
closes with rig owed").

## 1. Principles

- **One figure per Wan Animate run** (E19). A shot is assembled from layers that share one Stage document, camera and frame range.
- **Stage is the single source** of motion, camera, masks, depth order and shadow direction. Everything downstream is derived and
  re-derivable: delete a layer's clip and re-take it alone.
- **Cost before running** (D79's pattern): a shot shows its batches × layers × minutes and runs staged unless the author says run now.
- **Results are takes on the Story shot** (D93 `for_shot`), with lineage to the stage revision, the pose sequences and the reference.
- **Display == reality (T8):** the batch plan and the frames per batch the UI shows are what the jobs run.

## 2. Spikes first

### E23 · The core pipeline (≈ 1 day of work, ≈ 2–3 h of rig time)

The question: can a two-character shot with a camera move be animated layer by layer from one Stage document, across several batches,
with clean joins and the light sitting? And which Wan Animate mode should the app use?

**The shot.** E22's set and characters (Mara, Ines), about 10 s:

- **Mara** walks along a path and turns.
- **Ines** sits down and points.
- **The camera** makes a slow dolly-in with a slight pan.
- The motion is keyed with the existing joint keys; the spike may write keys programmatically, since presets do not exist yet.

**Arms:**

| Arm | Plate | Per layer | Assembly |
| --- | --- | --- | --- |
| **M · Move** | projected onto the set along the camera path (2.5D) | Wan Animate *Move*: reference (padded, full body) + the pose sequence at 16 fps | per-frame SAM 3 matte guided by Stage's mask sequence, depth order from Stage, a Stage shadow pass multiplied onto the plate |
| **R · Replace** | the same plate video | Wan Animate with `background_video` = the plate (or the previous layer's result) + `character_mask` = the figure's mask sequence | far → near chain; only the masked region (dilated, feathered) is pasted back each time |
| **R2 · Replace, depth-guided plate** (if time allows) | a plate video from the empty set's depth sequence (Stage's IC-LoRA *Render clip*) | as R | as R |

**Batching (all arms):** 77 frames at 16 fps, `continue_motion` = the last 5 frames of the previous batch, stride 72, crossfade at the
joins; conform to 24 fps at the end (RIFE, D27).

**Measures and bars** (bars from E17/E19/E21 where they exist):

| Measure | How | Bar |
| --- | --- | --- |
| Pose fidelity | PCK@0.1 of each layer against Stage's keypoints | ≥ 0.8 (E19) |
| Identity | FaceSim per character, every 8th frame, against the reference; drop vs batch 1 | drop ≤ 0.05 across joins |
| Joins | seam ratio at each batch join (E17's metric) | ≤ 1.5 (E17) |
| Background | flicker in the background region; drift of the plate under a pasted layer (R) | ≤ the plate's own |
| Light | the luminance step at the layer edge (E21's band step); by eye | ≤ E21 (b) |
| Shadows | coverage under the feet vs Stage's shadow pass | by eye |
| Time and VRAM | per run, per shot | a 10 s two-character shot ≤ 40 min at Draft; peak ≤ 14.5 GB |

For the author: a contact sheet per arm, the clips, and `compare.mp4` (M | R | R2).

### E24 · Post-processing (≈ 1 day, ≈ 2 h of rig time) — on E23's best arm

The question: which post-processing improves the shot without making it flicker?

| Arm | What |
| --- | --- |
| P0 | nothing (the baseline) |
| P1 | v2v over the flattened clip at σ 0.1 and 0.2 (Wan 2.2 low-noise expert as in E21; LTX v2v if the pinned engine offers it on core nodes) |
| P2 | per-frame image-to-image at strength 0.1–0.2, the same noise on every frame (Klein 9B; FLUX.2 dev for comparison) |
| P3 | keyframe-only refine (every 8th frame, Klein 9B at 0.2–0.3) + optical-flow propagation to the frames between (OpenCV, no new node) |
| P4 | face-crop refine per character per frame (the crop at ×2, Klein 9B with the character's references, pasted back feathered) |

**Measures:** temporal stability (optical-flow warping error between consecutive frames; flicker in static regions), detail (sharpness /
high-frequency energy), identity (FaceSim), faithfulness to the input (SSIM to P0 outside faces), time per 5 s.
**Bar:** an arm goes in only if it improves detail or identity *and* its warping error and flicker are no worse than P0's.

## 3. Decision gate

After E23 and E24: a D-number records the mode (Move or Replace), the plate method(s) and the post-processing (or none), with the
numbers. Only then the waves below, trimmed to what the decision keeps.

## 4. Build waves (CA · clay animation)

Rough effort in working days; each wave ends with its tests and a rig check.

| Wave | Content | Effort | Acceptance (rig) |
| --- | --- | --- | --- |
| **CA1 · Motion authoring** | motion presets as keyframe templates (walk cycle, turn, sit down, stand up, pick up, point, wave, nod); **root motion along a path** drawn on the floor; **foot lock**; preset speed and timing in the Inspector; commands and menus (D32) | 4–5 | a walk along a curved path with a turn and a point, made in < 2 min of clicks; feet do not slide (≤ 2 cm) |
| **CA2 · Layers and light** | a Layers panel in Stage (figures and props → layers, the plate = the set; a held prop joins its holder); a **key light** with its direction matched to the plate; a **shadow pass** per figure | 2 | the shadow pass lines up with the plate's light by eye on 3 plates |
| **CA3 · The plate** | the empty-set plate from the shot camera (Clay reference, the World style) as an app action; the **2.5D projection** along the camera path (three.js); per the decision, the **depth-guided plate video** | 3 | a dolly-in and a pan without visible stretching at Draft; the projected plate's frames match the still plate at frame 1 |
| **CA4 · The batch planner** | shot range → batches (77 model frames at 16 fps, 5-frame overlap, stride 72); per figure: the pose and mask sequences resampled to 16 fps; per batch: the plate frames; the plan with its cost; staged by default | 2 | a 10 s shot plans 3 batches per layer; the frames per batch the UI shows are what the jobs get (T8) |
| **CA5 · Layer jobs** | one Wan Animate job per layer per batch (Move or Replace per the decision), `continue_motion` from the previous batch, the animation reference padded (CN4's `pad_reference`); origin and lineage; **re-take one layer or one batch** | 3 | a 10 s two-character shot runs end to end on the queue; a re-take of one layer leaves the other untouched |
| **CA6 · Assembly** | Replace: the masked paste chain far → near · Move: the per-frame matte (SAM 3 guided by Stage's masks), depth order per frame, the shadow pass; joins crossfaded; PNG-sequence master + h264 proxy (the clip formats of today) | 3 | seams and joins within E23's bars on the acceptance shot |
| **CA7 · Post and conform** | the post-processing the decision keeps (E24); 16 → 24 fps (RIFE, D27); the result as a **take on the Story shot** (D93) with lineage | 2 | the take plays in Story › Shots and exports through the Episode |
| **CA8 · UI** | Stage › an **Animate shot** panel: the batches on the timeline, the layers list with per-layer status and preview, Run all / Re-take layer / Re-take batch, the cost; Story shot **Make clip ▸ in Stage (animated)**; the animation reference in Cast ("Make an animation reference") | 3–4 | the author's click-through of one shot from Cast to Episode |

**Total:** about 22–25 working days after the spikes, plus the spikes' 2 days. CA1 (motion authoring) can start in parallel with the
spikes, because it is needed whichever mode wins.

**Later, not in this plan:** motion import (BVH, after a licence check, D17/D26); pose from a reference video; HD (1280×720) Wan
Animate runs; a face video for expressions and lip-sync (D88's S2V) in this route.

## 5. Tests and rig acceptance

- **Offline (pytest / Vitest):**
  - the batch planner's arithmetic (frames, overlap, 24 ↔ 16 fps);
  - the mask and pose resampling;
  - the compositor on synthetic layers;
  - the cost estimate;
  - the take's lineage;
  - a fake-engine run of a 2-layer, 2-batch shot.
- **End-to-end smoke:** plan → run on the fake engine → the take appears on the shot.
- **Rig:** `scripts/ca_acceptance.py`. The E23 shot through the app: PCK, FaceSim drop across joins, seam ratios, flicker, time,
  VRAM — the E23 bars.

## 6. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Authoring motion is slow | CA1 presets and root motion first; imports later |
| Pose-driven motion looks stiff | presets with natural timing (ease, overlap); an optional low-σ v2v only if E24 earns it |
| Faces small at Draft | the animation reference padded at a good size; a face-crop refine (E24 P4) if it wins |
| Joins visible | the 5-frame overlap + crossfade; re-take a single batch |
| Light mismatch (Move) | Replace mode if E23 confirms its relighting; else the shadow pass + a low-σ v2v |
| The plate stretches on bigger moves | the depth-guided plate video for those shots |
| GPU time | Draft first; stage the shot's runs (they queue overnight); re-take only what failed |

## 7. Open questions

See [01 §7](01-clay-animation.md#7-questions-for-the-author). The answers shape CA1 (motion authoring), CA3 (camera moves), CA4 (joins,
references) and CA7 (post-processing).
