# 10 · Looking at E23b — Move against Replace (for the author)

About 5 minutes of looking. Your answer settles Q21 (decision log). The files are local, under `engine/spikes/out/e23b/` (not in git).

## What you are looking at

The shot is 10 s in E21's room. Mara (black bob, grey coat) walks from the back and turns to Ines. Ines (yellow jacket) sits down on
the grey stool and points at Mara. The camera moves in slowly.

Both versions use the same poses, the same plate and the same seeds. They differ only in how the two characters are made:

- **Move:** each character is made alone on a plain ground, then cut out and stacked over the room.
- **Replace:** each character is drawn straight into the room's video, one after the other.

## 1. compare.mp4 (≈ 3 min)

It is 24 fps in a 2 × 2 grid:

- **Left:** Move.
- **Right:** Replace.
- **Rows:** two seeds.

- **Check (Replace):** look at Ines. She is lit by the room and sits on the stool. Does she look better than in Move?
- **Check (Replace):** look at Mara. A black shape is left around her (her dark coat and hair hide where the blanked region was not
  filled). This is the main problem with Replace.
- **Check (Move):** do the cut-out characters look pasted on? Their light is their own, and the shadows are a simple stand-in.
  Post-processing (E24) is meant to fix this.
- **Check (both):** do you see the batch joins at 4.8 s and 9.3 s? The measure finds Move seamless. Replace pops at 9.3 s in the
  first seed.

## 2. The numbers in short

| | Move | Replace |
| --- | --- | --- |
| Poses followed | 0.99–1.0 | Mara 0.75–0.83 (the black), Ines 0.92 |
| Joins | seamless | one visible pop |
| A retake of one character | alone | the later layers too |
| GPU time for the shot | 14–17 min | 14–15 min |

**My recommendation is Move for the app.** Replace's better light could come back later as an "integrate" pass on a finished Move
layer.

## Notes

| Check | Answer |
| --- | --- |
| Move or Replace | |
| Replace's Ines better? | |
| Move looks pasted on? | |
| Joins visible? | |
