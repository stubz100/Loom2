# 23 · Looking at E29 — lip-sync in the clay route (for the author)

About 5 minutes. Spike E29 (01 §11, 02 §3; journal 2026-10-21 18:55) asked whether a Stage-performed character layer can speak a line.
Everything is under `engine\spikes\out\e29\` (nothing in the project; the files stay until a decision). The line is E20's English draft
voice `en1` (4.6 s) on the PS5 rig's shot: Mara walking in and turning, 77 frames at 16 fps, 832×480.

## 1. The three clips (≈ 3 min)

| File | What it is | The numbers |
| --- | --- | --- |
| `l1.mp4` | **L1 · S2V as the layer**: Wan 2.2 S2V from her padded animation reference and the line, meant to be the layer itself | the walk is gone — S2V reframed her as a talking head to camera, the body does its own thing (PCK 0.00 against Stage's pose); the mouth barely follows (sync r 0.19, bar ≥ 0.5); her look drifts (FaceSim 0.06–0.12, the baseline's 0.23–0.29); 925 s |
| `l2_head.mp4` | the **S2V talking head** of her face alone (512×512, the same line) — the driving video of L2 | **the mouth follows the line** (sync r 0.60: the first lip-sync in loom2 over the bar); 554 s |
| `l2.mp4` | **L2 · the talking head drives Wan Animate's face** (`face_video`) while the body follows Stage's pose pass | the walk is kept exactly (PCK 0.972, the baseline's 0.972); the mouth moves with the words but faintly (sync r 0.33 — her face is ≈ 20 px tall in this shot); the look changes a little (FaceSim 0.07–0.18); 306 s on top of the head |

- **Look at `l2.mp4` at 2× or 4×**: with the face that small, is the mouth readable at all? Play it beside `l2_head.mp4` (the head
  the face came from) and `engine\spikes\out\ps5\mara_fast.mp4` (the layer without speech).
- **Look at `l1.mp4`** only to see why S2V cannot be the layer: it is a different shot.
- `sheet.jpg`: six frames of each (L0 the baseline, L1, L2).

## 2. What it means (≈ 1 min)

- **L1 is out**: S2V ignores the Stage pose (as 01 §11 feared) and loses the look.
- **L2 is the route in this family**: the body obeys Stage, the face obeys the talking head — mechanically it works, and the head's own
  sync (0.60) shows the line is understood. What the layer keeps of it depends on how big the face is: in a full shot at 832×480 the mouth
  is a few pixels. **On a close shot (the Stage camera near the face) it should read** — that run is owed once a close shot exists on the
  rig (E29b, half a day).
- **L3** (a lip-sync post model over the finished layer: LatentSync, MuseTalk or the like) would be a new custom node — a decision with a
  licence check first (house rule 2, D17).

## 3. The question (Q25)

Which way for lip-sync in the clay route?

- **(a)** L2 as the clay route's lip-sync, EXPERIMENTAL like D88's: a Dialogue line on a Shot makes the talking head (S2V, ≈ 9 min) and
  the character's layer is performed with it; used on close shots; E29b measures it on one first.
- **(b)** L3: approve a lip-sync post model after its licence is read — one more spike, one more node.
- **(c)** No lip-sync in the clay route for now: the voice plays over the shot; the mouth is left to the post stage later.

## 4. E29b — the head as its own layer (D117, ≈ 4 min)

Your two ideas, run the same evening (journal 2026-10-21 22:14): the head cropped from the layer by Stage's keypoints (a tracked, smoothed box),
worked on at 512×512, pasted back with a feathered edge. Everything under `engine\spikes\out\e29b\`; every measure is on the head crop
now, so the mouth counts at its real size.

| File | What it is | The numbers |
| --- | --- | --- |
| `h0.mp4` | the layer's own head crop, upscaled (no speech) — the baseline | identity 0.25–0.30 (a blurry, smeared face: the Move layer's head is ≈ 100 px) |
| `calm_head.mp4` | the S2V talking head with a quieter prompt (the driving face for the c arms) | **sync r 0.66** (E29's head 0.60); a little calmer (articulation 14.3 vs 14.6); 510 s |
| `l2c.mp4` | E29's L2 with the calmer head (the full layer) — `l2c_head.mp4` its crop | sync r 0.47 on the crop (E29's 0.33 was measured on the tiny full frame); the face mushy, identity 0.04–0.17 |
| **`l2h.mp4`** | **the head as a layer**: Wan Animate on the head crop of the pose pass with your reference's head and E29's face video, pasted back — `l2h_head.mp4` the head alone | **identity 0.42–0.61 (from 0.25–0.30)** — a sharp, recognisable face where the layer had a smear; sync r 0.31, the mouth more exaggerated (articulation 33.9 vs 26.9 at rest); the body untouched (PCK 0.972), the seam faint (1.3); 329 s |
| `l2hc.mp4` | the same with the calmer head | identity 0.47–0.60; sync r 0.32; articulation 33.4; 316 s |
| `l3a.mp4` | **L3 · LatentSync 1.5** (ByteDance; code Apache-2.0, the weights OpenRAIL++ — `full` variant only) on the head-crop clip at 25 fps, pasted back — `l3a_head.mp4` the head alone | **sync r 0.33** by the mouth-energy proxy (Animate's 0.32 — on a moving head the proxy counts the head's own motion and cannot separate the two; the static S2V heads score 0.60–0.66 for that reason); identity 0.48–0.56 (kept); seam 1.5; **104 s**; to the eye the most natural mouth of the heads — open on the vowels without Animate's bared teeth: look at `l3a_head.mp4` beside `l2hc_head.mp4` |

- **Look at `l2h.mp4` beside `h0.mp4` and E29's `l2.mp4`**: the head-as-a-layer run gives Mara a face — sharp, with her glasses — on top
  of the lip movement. That is worth more than the lip-sync itself: a **head pass** at 512² for every character layer.
- **Look at `l3a.mp4`** (if it ran): a lip-sync model repaints only the mouth of the crop — does it read better than Animate's mouth, and
  does the face stay hers?
- `sheet.jpg`: three frames of each head (h0, l2c, l2h, l2hc, l3a).

The mouth's exaggeration: the driving head is the lever (the native Animate node has no face strength; the field's wrappers add one), and
a quieter S2V prompt only did a little. A lip-sync model on the head layer's output (l2h → L3) is the next thing to try if L3 reads well.

**Q25 again:** (a) the head layer for every character (the face pass), with L2's face video for lines — and L3 on top if it reads
better; (b) the head layer, lines by L3 only; (c) something else you saw in the clips.

## Notes

| Check | Answer |
| --- | --- |
| Is the mouth readable in `l2.mp4` at all? | |
| Q25: (a), (b) or (c)? | answered 2026-10-21 → D117, E29b |
| E29b: the head layer as a face pass — yes? L3's mouth better than Animate's? | |
