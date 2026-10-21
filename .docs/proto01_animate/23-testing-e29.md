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

## Notes

| Check | Answer |
| --- | --- |
| Is the mouth readable in `l2.mp4` at all? | |
| Q25: (a), (b) or (c)? | |
