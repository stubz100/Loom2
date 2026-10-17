# 02 · Animation from clay — implementation plan

Status: **proposal, 2026-10-17; revised the same evening after the author's six notes** (01 §8). It follows the reviewed pipeline in
[01](01-clay-animation.md). The order:

1. The author refines 01.
2. A licence check for the motion sources (§2).
3. Three spikes (§3).
4. A decision: a D-number (§4).
5. The build waves (§5).

Each wave ends measured on the rig, as every wave has ("no milestone closes with rig owed").

## 1. Principles

- **Two proxies before the final** (01 §1): the clay (Stage) and the performance (Wan Animate). Post-processing is the render.
- **One figure per Wan Animate run** (E19). A shot is assembled from layers that share one Stage document, camera and frame range.
- **Stage is the single source** of motion, camera, masks, depth order and shadow direction. Everything downstream is derived and
  re-derivable: delete a layer's clip and re-take it alone; with W2, one batch of it.
- **Cost before running** (D79's pattern): a shot shows its batches × layers × minutes, and runs staged unless the author says run now.
- **Results are takes on the Story shot** (D93 `for_shot`), with lineage to the stage revision, the pose sequences and the reference.
- **Display == reality (T8):** the batch plan and the frames per batch the UI shows are what the jobs run.
- **Licences (D17 / D26):** motion clips the author downloads stay in the author's local folder. Only clips with a verified open licence
  ship.

## 2. Licence check for the motion (≈ 1 h, no download)

- Re-read Adobe's live terms and Mixamo FAQ for: use in films, local storage, a local library, and pose sequences from the clips fed to a
  generative model. Record the reading in the licence ledger (D17).
- Verify the licence of a starter library to ship (Quaternius' *Universal Animation Library*, reported as CC0; others if it is not), and
  what it holds (acting moves: sit, point, talk, wave, pick up).
- Nothing is fetched without the author's yes.

## 3. Spikes first

### E23a · One layer: the frame rate and the weld (≈ ½ day of work, ≈ 1.5 h of rig time)

The question: on a long single-character shot, which frame rate (F16 or F24) and which weld (W1 chain or W2 keyframe starts) give clean
joins with the identity held?

**The shot.** About 10 s, Mara alone in E22's set:

- she walks along a path (the walk from the old loom's local `mixamo_animations/Walking.fbx`, retargeted by spike code; or keys written
  programmatically), then turns and points;
- a locked-off camera, so the plate is not a variable;
- Move mode (CN4's), with the animation reference made by hand to 01 step 2's rules (16:9, full body, A-pose, colours bound).

**Arms** (2 seeds each, the same seeds across arms):

| Arm | Frame rate | Weld | Batches |
| --- | --- | --- | --- |
| F16·W1 | poses resampled to 16 fps, RIFE to 24 | chain: `continue_motion` = the last 5 frames | 3 |
| F16·W2 | 16 fps | keyframe starts: a Stage keyframe still (Exact pose, the binding) as a 1-frame `continue_motion`, crossfade over the overlap | 3 |
| F24·W1 | Stage's 24 fps poses as they are | chain | 4 |
| F24·W2 | 24 fps | keyframe starts | 4 |

**Measures and bars:**

| Measure | How | Bar |
| --- | --- | --- |
| Pose fidelity | PCK@0.1 against Stage's keypoints | ≥ 0.8 (E19) |
| Identity | FaceSim every 8th frame against the reference; the drop from batch 1 to the last batch | drop ≤ 0.05 |
| Joins | seam ratio at each join (E17's metric); appearance difference over the overlap (LPIPS in the figure's mask) | seam ≤ 1.5 (E17) |
| Motion speed (F24) | by eye: do hair and cloth look slowed down? | the author's eye |
| Interpolation (F16) | ghosting on fast limbs after RIFE | by eye |
| Time and VRAM | per batch, per shot | peak ≤ 14.5 GB |

**For the author:** `compare.mp4` (the four arms side by side), the joins as strips (the 10 frames around each join), and a contact sheet.

### E23b · Two layers: Move against Replace (≈ 1 day of work, ≈ 2–3 h of rig time)

The question (note 3): which Wan Animate mode does the app use? It runs with E23a's frame rate and weld.

**The shot.** E22's set and characters (Mara and Ines), about 10 s:

- **Mara** walks along a path and turns.
- **Ines** sits down and points.
- **The camera** makes a slow dolly-in with a slight pan.

**Arms:**

| Arm | Plate | Per layer | Assembly |
| --- | --- | --- | --- |
| **M · Move** | projected onto the set along the camera path (2.5D) | Wan Animate *Move*: the animation reference + the pose sequence | per-frame SAM 3 matte guided by Stage's mask sequence, depth order from Stage, a Stage shadow pass multiplied onto the plate |
| **R · Replace** | the same plate video | Wan Animate with `background_video` = the plate (or the previous layer's result) + `character_mask` = the figure's mask sequence | far → near chain; only the masked region (dilated, feathered) is pasted back each time |
| **R2 · Replace, depth-guided plate** (if time allows) | a plate video from the empty set's depth sequence (Stage's IC-LoRA *Render clip*) | as R | as R |

**Measures and bars** (bars from E17 / E19 / E21 where they exist):

| Measure | How | Bar |
| --- | --- | --- |
| Pose fidelity | PCK@0.1 of each layer against Stage's keypoints | ≥ 0.8 (E19) |
| Identity | FaceSim per character, every 8th frame; drop across joins | ≤ 0.05 |
| Joins | seam ratio at each join | ≤ 1.5 (E17) |
| Background | flicker in the background region; drift of the plate under a pasted layer (R) | ≤ the plate's own |
| Light | the luminance step at the layer edge (E21's band step); by eye | ≤ E21 (b) |
| Shadows | coverage under the feet against Stage's shadow pass | by eye |
| Time and VRAM | per run, per shot | a 10 s two-character shot ≤ 45 min at Draft; peak ≤ 14.5 GB |

**For the author:** a contact sheet per arm, the clips, and `compare.mp4` (M | R | R2).

### E24 · Post-processing (≈ 1.5 days, ≈ 4–6 h of rig time, partly overnight) — on E23b's best arm

The question: which post-processing, at which stage, makes the performance the final without flicker, while staying faithful and keeping
the shadows and light? Every idea of 01 step 8 is an arm. The three stages are tested **separately** (note 4), and then the best of each
together.

**Before it:** the FLUX.2 dev RAM-pressure slowness (owed, journal 2026-10-17 18:03) is investigated. Otherwise A4 / C5 on dev are only
measured on keyframes.

| Stage | Arms (01 step 8) | Run on |
| --- | --- | --- |
| **A · layer pass** | A0 none · A1 the amount per layer (plate none, characters low, hero more) · A2 low-σ v2v per layer (Wan low expert σ 0.1 / 0.2; LTX-2.3), a model per layer · A3 face-crop refine (Klein 9B + references) · A4 per-frame i2i with neighbours as references (FLUX.2 dev: the frame ± 2 + the animation reference, up to 10; Klein 9B KV: up to 4) · A5 keyframe refine every 8th frame + optical-flow propagation | each character layer of the E23b shot |
| **B · image stream** | B1 RIFE 16 → 24 · B2 native 24 (from E23a) · B3 refined keyframes + in-betweens from them · B4 another rate (25 fps, by interpolation) | the best A |
| **C · final polish** | C0 none · C1 Wan low-expert v2v σ 0.1 / 0.2 · C2 LTX-2.3 v2v, low strength · C3 structure-locked v2v (LTX-2.3 + IC-LoRA depth from the shot's Stage depth sequence, from the flattened clip at a low strength) · C5 FLUX.2 dev with neighbours over the flattened frames (keyframes only unless dev is fixed). C4 (Wan VACE) only if the author approves the download | the flattened shot, after A0 and after the best A |

**Measures:**

- **temporal stability:** optical-flow warping error between consecutive frames, flicker in static regions;
- **faithfulness:** SSIM / LPIPS to the input outside the faces;
- **shadows and light kept:** the shadow regions' luminance and outline against the input, and against Stage's shadow pass;
- **detail:** sharpness, high-frequency energy;
- **identity:** FaceSim;
- **time** per 10 s.

**Bar:** an arm goes in only if it improves detail, identity or light, *and* its warping error and flicker are no worse than the
baseline's, *and* its faithfulness outside the faces stays high (SSIM ≥ 0.9 to the input; to confirm on the baseline).

## 4. Decision gate

After E23a, E23b and E24, a D-number records, with the numbers:

- the frame rate (F16 / F24);
- the weld (W1 / W2 / W3);
- the mode (Move / Replace);
- the plate method(s);
- the post-processing per stage (A / B / C), or none.

Only then the waves below, trimmed to what the decision keeps.

## 5. Build waves (CA · clay animation)

Rough effort in working days; each wave ends with its tests and a rig check. CA0 and CA1 do not depend on the decision and can start in
parallel with the spikes.

| Wave | Content | Effort | Acceptance (rig) |
| --- | --- | --- | --- |
| **CA0 · The animation reference in Cast** (note 6) | per Cast version: *Make an animation reference* (16:9, full body, A-pose, plain background, colours bound, Klein 9B with the sheet's references), shown beside the coverage grid; an optional back view; an optional test animation (a turn on the spot); lineage; commands and menus (D32) | 1.5–2 | three characters × two versions: the reference animates in the test with PCK ≥ 0.8 and no ghost or crop |
| **CA1 · The motion library** (note 5) | an FBX / glTF importer (three.js loaders): bone mapping (Mixamo names and the starter set's), rest-pose correction, scale, retargeting onto the mannequin's 12 joints, the hips' translation as root motion, baked to keys at 24 fps; a **local motion folder** in Settings (outside the repo, never bundled) and a **starter set** that ships (per §2); a library browser with previews on the mannequin; **root motion along a path** drawn on the floor; **foot lock**; trim, speed, **blend** from one clip into the next; presets and keys by hand stay | 5–6 | a walk along a curved path into a turn and a point, from the library, in < 2 min of clicks; feet do not slide (≤ 2 cm); a Mixamo FBX from the local folder imports and plays |
| **CA2 · Layers and light** | a Layers panel in Stage (figures and props → layers, the plate = the set; a held prop joins its holder); a **key light** with its direction matched to the plate; a **shadow pass** per figure (Move) | 2 | the shadow pass lines up with the plate's light by eye on 3 plates |
| **CA3 · The plate** | the plate still from the empty set and the shot camera (Clay reference, the World style) as an app action; the **2.5D projection** along the camera path (three.js); per the decision, the **depth-guided plate video** | 3 | a dolly-in and a pan without visible stretching at Draft; the projected plate's frames match the still plate at frame 1 |
| **CA4 · The batch planner** | shot range → batches at the decided rate (F16: resampled; F24: as keyed), 77 frames, 5 carried / 72 new; per figure: pose and mask sequences; per batch: the plate frames and (W2) a **keyframe still** per figure (Exact pose with the binding, the reference and the previous still as references); the plan with its cost; staged by default | 2–3 | a 10 s shot plans 3 (F16) or 4 (F24) batches per layer; the frames per batch the UI shows are what the jobs get (T8) |
| **CA5 · Layer jobs** | one Wan Animate job per layer per batch (Move or Replace per the decision), started from the previous batch (W1) or the keyframe still (W2); origin and lineage; **re-take one layer or one batch** | 3 | a 10 s two-character shot runs end to end on the queue; a re-take of one layer (or one batch, W2) leaves the rest untouched |
| **CA6 · Assembly** | Replace: the masked paste chain far → near · Move: the per-frame matte (SAM 3 guided by Stage's masks), depth order per frame, the shadow pass; joins crossfaded; PNG-sequence master per layer with alpha + h264 proxy | 3 | seams and joins within E23's bars on the acceptance shot |
| **CA7 · The final** | what E24 keeps, per stage: the **layer pass** (amount and model per layer), the **image stream** (rate, in-betweens), the **final polish**; each a step with its cost, re-runnable alone; the result as a **take on the Story shot** (D93) with lineage | 3–4 | the take plays in Story › Shots and exports through the Episode; its metrics within E24's bars |
| **CA8 · UI** | Stage › an **Animate shot** panel: the batches on the timeline, the layers list with per-layer status and preview, Run all / Re-take layer / Re-take batch, the post stages with their amounts per layer, the cost; Story shot **Make clip ▸ in Stage (animated)** | 3 | the author's click-through of one shot from Cast to Episode |

**Total:** about 26–30 working days after the spikes, plus the spikes' ≈ 3 days.

**Later, not in this plan:**

- a finer mannequin rig (chest, wrists, ankles, hands) and hands in the pose pass;
- pose from a reference video;
- HD (1280×720) Wan Animate runs;
- a face video for expressions, and lip-sync (D88's S2V), in this route.

## 6. Tests and rig acceptance

- **Offline (pytest / Vitest):**
  - the batch planner's arithmetic (frames, overlap, F16 / F24, the stride);
  - the retargeting (a known clip onto the mannequin: joint angles, root motion, foot lock);
  - the mask and pose resampling;
  - the compositor on synthetic layers;
  - the cost estimate;
  - the take's lineage;
  - a fake-engine run of a 2-layer, 2-batch shot, W1 and W2.
- **End-to-end smoke:** import a clip → key a shot → plan → run on the fake engine → the take appears on the shot.
- **Rig:** `scripts/ca_acceptance.py`. The E23b shot through the app: PCK, FaceSim drop across joins, seam ratios, flicker, time,
  VRAM — the E23 bars; then the kept post stages against E24's bars.

## 7. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Authoring motion is slow | the library first (CA1), presets and keys by hand for the rest |
| The motion's licence | Mixamo stays in the author's local folder; only verified open clips ship (§2) |
| The coarse rig loses hands and feet | the COCO-18 guide does not need them; a finer rig later |
| Pose-driven motion looks stiff | library clips carry natural timing; a post stage only if E24 earns it |
| Faces small at Draft | the animation reference at a good size; a face-crop refine (A3) if it wins |
| Joins visible | W1 or W2 by E23a's numbers, a crossfade over the overlap; re-take one batch (W2) |
| Light mismatch (Move) | Replace mode if E23b confirms its relighting; else the shadow pass + the final polish (C3) |
| The plate stretches on bigger moves | the depth-guided plate video for those shots |
| GPU time | Draft first; stage the shot's runs (they queue overnight); re-take only what failed; FLUX.2 dev per frame only if its RAM-pressure slowness is fixed |

## 8. Open questions

See [01 §7](01-clay-animation.md#7-questions-for-the-author). The answers shape CA1 (the library), CA3 (camera moves), CA4 (joins, the
rate) and CA7 (the post stages and the time budget).
