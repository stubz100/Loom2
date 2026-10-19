# 09 · Looking at E23a — frame rate and joins (for the author)

About 5 minutes of looking. These are the two things spike E23a cannot measure. Your answer settles Q20 (decision log) before E23b
runs. The files are local, under `engine/spikes/out/e23a/` (not in git).

## 1. F16 or F24 (≈ 3 min)

Open `compare.mp4`. It is 10 s at 24 fps in a 2 × 2 grid:

- **Left:** F16, made at 16 fps and conformed to 24 by RIFE (D27's tool).
- **Right:** F24, made at 24 fps.
- **Rows:** two seeds.

Play it at full speed, then step through the walk with the arrow keys.

- **F24:** do the hair, the braids and the skirt look slowed down, floaty or dragged?
- **F16:** after RIFE, do you see ghosting or smearing on the legs and arms while she walks?
- **Overall:** which walk would you rather have as the performance to post-process?

The measured part is a tie: the poses are followed equally well and the identity holds in both. F24 costs a third more GPU time for a
10 s shot. **My recommendation is F16, unless F24's motion looks clearly better to you.**

## 2. The joins (≈ 2 min)

The joins are plain cuts with no crossfade (W1).

| File | Join |
| --- | --- |
| `runs/F24_s20261019/chain.mp4` | 3.2 s (walking), 6.2 s (as she stops), **9.2 s (while she holds the point)** |
| `runs/F16_s20261019/rife24.mp4` | 4.8 s (at the path's corner), **9.3 s (in the hold)** |

`joins.jpg` shows the 10 frames around each join, with a red line at the cut.

- **Check:** can you see the joins while she walks?
- **Check:** in the hold, is there a small jump or "settle" at the bold join? The measure says the whole figure shifts by about 1 px
  and the skirt changes tint slightly.

`heal.jpg` and `runs/F24_s20261019/healed.mp4` show W3, a per-frame refine around the hold join. It made the flicker worse, so I
propose that the batch planner places the joins where the figure moves instead.

## Notes

| Check | Answer |
| --- | --- |
| F16 or F24 | |
| Ghosting (F16) / slow motion (F24) | |
| Joins visible while walking? | |
| Pop in the hold visible? | |
