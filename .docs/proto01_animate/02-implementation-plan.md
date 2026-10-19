# 02 · Animation from clay — implementation plan

Status: **proposal, 2026-10-17; revised after the author's notes of 2026-10-17 and 2026-10-18** (01 §8–§11). It follows the reviewed pipeline in
[01](01-clay-animation.md). The order:

1. The author refines 01.
2. A licence check for the motion sources (§2).
3. The spikes (§3): the pipeline, post-processing, the dummies, props and lip-sync.
4. A decision: a D-number (§4).
5. The build waves (§5).

Each wave ends measured on the rig, as every wave has ("no milestone closes with rig owed").

## 1. Principles

- **Two proxies before the final** (01 §1): the clay (Stage) and the performance (Wan Animate). Post-processing is the render.
- **One figure per Wan Animate run** (E19). A shot is assembled from layers that share one Stage document, camera and frame range.
- **Stage is the single source** of motion, camera, masks, depth order and shadow direction. Everything downstream is derived and
  re-derivable: delete a layer's clip and re-take it alone (a batch re-take re-runs the batches after it: joins are seamless).
- **Cost before running** (D79's pattern): a shot shows its batches × layers × minutes, and runs staged unless the author says run now.
- **Results are takes on the Story shot** (D93 `for_shot`), with lineage to the stage revision, the pose sequences and the reference.
- **Display == reality (T8):** the batch plan and the frames per batch the UI shows are what the jobs run.
- **Licences (D17 / D26):** motion clips the author downloads stay in the author's local folder. Only clips with a verified open licence
  ship.
- **One job on the GPU at a time (D97):** spikes and rig runs one after another; the build order is in [07](07-build-order.md).
- **Everything is kept, inside the project directory** (the author, 2026-10-18): batch masters, layers, start stills, takes,
  compositions and caches. A retention setting may come later; nothing is pruned now.

## 2. Licence check for the motion

- **Done (2026-10-17):** the starter set. Quaternius' *Universal Animation Library* 1 and 2 [Standard] are CC0 1.0 (each archive's
  `License.txt`); fetched with the author's yes to `F:/loom2-models/motion/` (`SOURCES.md` holds the URLs and sha256). 87 clips and
  skinned mannequins with fingers and feet (01 step 5, §9).
- **Done (2026-10-18): Adobe's Mixamo terms read.**
  - The FAQ allows the characters and animations royalty-free in personal, commercial and non-profit projects, films and games
    included.
  - The **Mixamo Additional Terms §1** (2021-06-23): *"You will not … use the Services or Software (or any content, data, output, or
    other information received or derived from the Services or Software) to directly or indirectly create, train, test, or otherwise
    improve any machine learning algorithms or artificial intelligence systems, including … models, or weights."*
  - **Consequence:**
    - spikes, rig checks, tests and the development of loom2 use **CC0 motion only**;
    - Mixamo clips are the author's own creative input at use time, in their local folder;
    - frames made from Mixamo-driven clips must never train a LoRA (LT wave, D86).

  This is a reading for D17, not legal advice. The author decides.

## 3. Spikes first

### E23a · One layer: the frame rate and seamless joins (≈ ½ day of work, ≈ 1.5 h of rig time)

The question: on a long single-character shot, which frame rate (F16 or F24) gives seamless W1 joins (no crossfade, the author 2026-10-18) with the identity held, and how much do they drift (W3 repairs)?

> **Run 2026-10-19** (journal 12:13, `engine/spikes/e23a_joins.py`).
>
> - Pose and identity are equal at F16 and F24, and F24 costs a third more GPU time.
> - W1 is seamless inside motion (local ratio 0.83–1.04) but pops inside a still hold (7.7–11×).
> - W3 as a per-frame refine made the hold worse (7.65 → 16.2).
>
> Proposed: F16 + RIFE, with the batch planner placing joins in motion (Q20). The author's look is in 09.

**The shot.** About 10 s, Mara alone in E22's set:

- she walks along a path (the CC0 starter set's `Walk_Loop`, retargeted onto the dummy by spike code; never a Mixamo clip, §2),
  then turns and points (keys);
- a locked-off camera, so the plate is not a variable;
- Move mode (CN4's), with the animation reference made by hand to 01 step 2's rules (16:9, full body, A-pose, colours bound).

**Arms** (2 seeds each, the same seeds across arms):

| Arm | Frame rate | Weld | Batches |
| --- | --- | --- | --- |
| F16 | poses resampled to 16 fps, RIFE to 24 | W1: `continue_motion` = the last 5 frames, dropped from the next batch's output; a plain cut | 3 |
| F24 | Stage's 24 fps poses as they are | W1 | 4 |
| W3 | the arm with the worst join | a healing patch over the ± 4 frames around it, the start still and the animation reference as references | — |

**Measures and bars:**

| Measure | How | Bar |
| --- | --- | --- |
| Pose fidelity | PCK@0.1 against Stage's keypoints | ≥ 0.8 (E19) |
| Identity | FaceSim every 8th frame against the reference; the drop from batch 1 to the last batch | drop ≤ 0.05 |
| Joins | seam ratio at each join (E17's metric), no crossfade; drift = appearance difference between the frames either side of a join (LPIPS in the figure's mask) | seam ≤ 1.5 (E17) and no jump visible to the author |
| Motion speed (F24) | by eye: do hair and cloth look slowed down? | the author's eye |
| Interpolation (F16) | ghosting on fast limbs after RIFE | by eye |
| Time and VRAM | per batch, per shot | peak ≤ 14.5 GB |

**For the author:** `compare.mp4` (the arms side by side), the joins as strips (the 10 frames around each join), and a contact sheet.

### E23b · Two layers: Move against Replace (≈ 1 day of work, ≈ 2–3 h of rig time)

The question (note 3): which Wan Animate mode does the app use? It runs with E23a's frame rate and weld.

> **Run 2026-10-19** (journal 16:32, `engine/spikes/e23b_layers.py`).
>
> - **Move:** PCK 0.99–1.0, seamless joins. The reference's ghost is cut by the Stage-guided SAM 3 matte.
> - **Replace:** needs the region blanked black (Wan 2.2's own preprocessing), keeps the black around dark clothes (PCK 0.75–0.83) and pops at a join, but integrates light best where the character covers the region.
>
> R2 was left out (the Render clip covers 5 s). Proposed: Move (Q21). The author's look is in 10.

**The shot.** E22's set and characters (Mara and Ines), about 10 s:

- **Mara** walks along a path and turns.
- **Ines** sits down and points.
- **The camera** makes a slow dolly-in with a slight pan (small moves first; larger moves are not ruled out, 2026-10-18: R2's
  depth-guided plate is needed for them).

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

Times are measured here, not estimated before (the author). FLUX.2 dev is tried where it matters (A6, the healing patch) and Klein 9B
for per-frame work; the dev RAM-pressure slowness (owed, journal 2026-10-17 18:03) is worth fixing first, because it inflates every dev
number.

| Stage | Arms (01 step 8) | Run on |
| --- | --- | --- |
| **A · layer pass** | A0 none · A1 the amount per layer (plate none, characters low, hero more) · A2 low-σ v2v per layer (Wan low expert σ 0.1 / 0.2; LTX-2.3), a model per layer · A3 face-crop refine (Klein 9B + references) · A4 per-frame i2i with neighbours as references (Klein 9B KV: up to 4; FLUX.2 dev: the frame ± 2 + the animation reference, up to 10) · A5 keyframe refine every 8th frame + optical-flow propagation · A6 a healing patch: a region over a frame range (a hand, a face at a join) with FLUX.2 dev | each character layer of the E23b shot |
| **B · image stream** | B1 RIFE 16 → 24 · B2 native 24 (from E23a) · B3 refined keyframes + in-betweens from them (B4, other rates, later: delivery is 24 fps) | the best A |
| **C · final polish** | C0 none · C1 Wan low-expert v2v σ 0.1 / 0.2 · C2 LTX-2.3 v2v, low strength · C3 structure-locked v2v (LTX-2.3 + IC-LoRA depth from the shot's Stage depth sequence, from the flattened clip at a low strength) · C5 Klein 9B or FLUX.2 dev with neighbours over the flattened frames, or A6 patches on them. C4 (Wan VACE) only if the author approves the download | the flattened shot, after A0 and after the best A |

**Measures:**

- **temporal stability:** optical-flow warping error between consecutive frames, flicker in static regions;
- **faithfulness:** SSIM / LPIPS to the input outside the faces;
- **shadows and light kept:** the shadow regions' luminance and outline against the input, and against Stage's shadow pass;
- **detail:** sharpness, high-frequency energy;
- **identity:** FaceSim;
- **time** per 10 s.

**Bar:** an arm goes in only if it improves detail, identity or light, *and* its warping error and flicker are no worse than the
baseline's, *and* its faithfulness outside the faces stays high (SSIM ≥ 0.9 to the input; to confirm on the baseline).

### E25 · Hands and feet in the guide (≈ ½ day) — before CA1 builds the Detailed dummy (01 §9a)

One character, the starter set's skinned mannequin playing a clip with clear hand action (`PickUp_Table`, `Idle_Talking`), Wan Animate
driven by COCO-18 alone vs COCO-18 + hands (21 points each) + feet (6). Measured: hand PCK against Stage's hand points, fingers by eye,
foot sliding. It decides whether the pose pass draws hands; the Detailed dummy is useful for posing and clay stills either way.

### E26 · A non-human performance (≈ 1 day) — only if the author wants creatures soon (01 §9b, N3)

One quadruped clip from a CC0 rigged animal, its depth (+ mask) sequence from Stage driving LTX-2.3 + IC-LoRA depth (exists) vs Wan VACE
with depth (a download, a decision), with the creature's reference image. Bars as E23: identity, the shape kept, the background stable.

### E28 · Props as layers (≈ 1 day) — 01 §10

In E22's set: one rigid prop moved by keys (a box slid along the floor: P1, a cut-out in the composition), one opening door (P2:
depth-guided, LTX-2.3 + IC-LoRA depth from the door's Stage depth and mask sequence, with its reference), and one cup held by Mara (P1
parented to the hand vs P3 drawn inside her Wan Animate layer). Measured: the shape kept, identity against the prop's reference, the
contact with the hand, the shadow, time.

### E29 · Lip-sync in the clay route (≈ 1 day) — 01 §11

One character, one English line of about 4 s, in a Stage shot with body motion: L1 (S2V as the layer) against L2 (an S2V talking head
as Wan Animate's face video, the body following the Stage pose); L3 (a lip-sync post model) only if the author approves a candidate,
since it would be a new custom node. Measured: lip-sync (E18's r), body PCK against Stage (must not drop for L2), identity, time.

## 4. Decision gate

After E23a, E23b and E24, a D-number records, with the numbers:

- the frame rate (F16 / F24);
- the frame rate's seams and drift (W1, with W3 repairs where needed);
- the prop methods (E28: P1 / P2 / P3) and the lip-sync route (E29: L1 / L2 / L3);
- the mode (Move / Replace);
- the plate method(s);
- the post-processing per stage (A / B / C), or none;
- the dummy: hands in the pose pass or not (E25); Simple / Detailed per figure (01 §9a).

Only then the waves below, trimmed to what the decision keeps.

## 5. Build waves (CA · clay animation)

Rough effort in working days; each wave ends with its tests and a rig check. CA0 and CA1 do not depend on the decision and can start in
parallel with the spikes.

| Wave | Content | Effort | Acceptance (rig) |
| --- | --- | --- | --- |
| **CA0 · The animation reference in Cast** (note 6) | the **body on the Cast sheet** (height, build, proportions, attachments) that shapes the figure's dummy (01 §9); per Cast version (characters and **props**, 01 §10): *Make an animation reference* (16:9, full body, A-pose, plain background, colours bound, Klein 9B with the sheet's references), shown beside the coverage grid; an optional back view; an optional test animation (a turn on the spot); lineage; commands and menus (D32) | 1.5–2 | three characters × two versions: the reference animates in the test with PCK ≥ 0.8 and no ghost or crop |
| **CA1 · The motion library** (note 5) | the **Detailed dummy** as a second editing level on the same figure (the starter set's skinned mannequin, male / female: block with the Simple dummy, refine hands, feet and finer motion on the Detailed one; keys map between them; 01 §9a; proportion controls for humanoid creatures, §9b N1) with hand presets; an FBX (binary and ASCII) / glTF importer for the Mixamo rig (65 `mixamorig:` bones, centimetres, 24 fps) and the Quaternius rigs (three.js loaders): bone mapping (Mixamo names and the starter set's), rest-pose correction, scale, retargeting onto the mannequin's 12 joints, the hips' translation as root motion, baked to keys at 24 fps; a **local motion folder** in Settings (outside the repo, never bundled) and a **starter set** that ships (per §2); a library browser with previews on the mannequin; **root motion along a path** drawn on the floor; **foot lock**; trim, speed, **blend** from one clip into the next; presets and keys by hand stay | 7–9 | a walk along a curved path into a turn and a point, from the library, in < 2 min of clicks; feet do not slide (≤ 2 cm); a Mixamo FBX from the local folder imports and plays |
| **CA2 · Layers and light** | a Layers panel in Stage (figures and props → layers, the plate = the set); **props bound to Cast props** like figures, moved by transform keys and **parented to a hand** when held (01 §10); a **key light** with its direction matched to the plate; a **shadow pass** per figure and prop (Move); the prop performance method E28 keeps (P1 cut-out / P2 depth-guided / P3 with the holder) | 3 | the shadow pass lines up with the plate's light by eye on 3 plates; a held cup stays in the hand through a walk |
| **CA3 · The plate** | the plate still from the empty set and the shot camera (Clay reference, the World style) as an app action; the **2.5D projection** along the camera path (three.js) for small moves; the **depth-guided plate video** for large ones (camera moves have no limit, 2026-10-18) | 3–4 | a dolly-in and a pan without visible stretching at Draft; an orbit with the depth-guided plate; the projected plate's frames match the still plate at frame 1 |
| **CA4 · The batch planner** | shot range → batches at the decided rate (F16: resampled; F24: as keyed), 77 frames, 5 carried / 72 new; per figure: pose and mask sequences; per batch: the plate frames; per figure a **start still** for batch 1 (Exact pose with the binding); W1 joins (5 frames carried, dropped from the next batch, no blend); the plan with its cost; staged by default | 2–3 | a 10 s shot plans 3 (F16) or 4 (F24) batches per layer; the frames per batch the UI shows are what the jobs get (T8) |
| **CA5 · Layer jobs** | one Wan Animate job per layer per batch (Move or Replace per the decision), started from the previous batch (W1); origin and lineage; **re-take one layer**, or a batch and the ones after it; a **W3 repair** (a healing patch around a join) when a seam shows | 3 | a 10 s two-character shot runs end to end on the queue; a re-take of one layer leaves the other layers untouched |
| **CA6 · Assembly** | Replace: the masked paste chain far → near · Move: the per-frame matte (SAM 3 guided by Stage's masks), depth order per frame, the shadow pass; batch joins are plain cuts (no crossfade, the author); PNG-sequence master per layer with alpha + h264 proxy | 3 | seams and joins within E23's bars on the acceptance shot |
| **CA7 · The final** | what E24 keeps, per stage: the **layer pass** (amount and model per layer), the **image stream** (rate, in-betweens), the **final polish**; each a step with its cost, re-runnable alone; the result as a **take on the Story shot** (D93) with lineage | 3–4 | the take plays in Story › Shots and exports through the Episode; its metrics within E24's bars |
| **CA8 · UI** | Stage › an **Animate shot** panel: the batches on the timeline, the layers list with per-layer status and preview, Run all / Re-take layer / Re-take batch, the post stages with their amounts per layer, the cost; Story shot **Make clip ▸ in Stage (animated)** | 3 | the author's click-through of one shot from Cast to Episode |

**Doc [03](03-image-and-animate-suites.md) (2026-10-18, proposed) changes this plan:**

- the clay waves are built into a re-housed Animate suite (UX0, IM1 and AN1 first);
- CA6 writes an EffectCraft composition (AE1) instead of a flat clip;
- CA8 folds into AN1 and AE2;
- CA7's post stages run as layer passes in the editor (AE4);
- a UI/UX review comes before (UX0) and after (UX9) the build.

**Total:** about 30–35 working days after the spikes, plus the spikes' ≈ 5.5 days (E23a/b, E24, E25, E28, E29; E26 another day if creatures
are wanted). A
non-human route (N3, depth-guided) is not in these waves; it follows E26 if the author wants it.

**Later, not in this plan:**

- non-human creatures that are not humanoid (01 §9b N3, after E26);
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
  - a fake-engine run of a 2-layer, 2-batch shot with W1 joins (the carried frames dropped, no blend).
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
| Joins visible | W1 by construction; W3 repairs a visible seam with a healing patch around the join; never a crossfade (the author) |
| Light mismatch (Move) | Replace mode if E23b confirms its relighting; else the shadow pass + the final polish (C3) |
| The plate stretches on bigger moves | the depth-guided plate video for those shots |
| GPU time | Draft first; stage the shot's runs (they queue overnight); re-take only what failed; FLUX.2 dev per frame only if its RAM-pressure slowness is fixed |

## 8. Open questions

See [01 §7](01-clay-animation.md#7-questions-for-the-author). The answers shape CA1 (the library), CA3 (camera moves), CA4 (joins, the
rate) and CA7 (the post stages and the time budget).
