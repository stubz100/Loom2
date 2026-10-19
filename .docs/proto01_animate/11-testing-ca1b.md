# 11 · Looking at CA1b — the skeletons fitted to the characters (for the author)

About 5 minutes. You asked for the skeletons to be refined for the characters: the girls looked short and stocky, with big hands and
feet (D103). The files are local, under `engine/spikes/out/ca1b/` (not in git).

## What changed

- **The proportions come from the character.** Each Cast version's body is now fitted to its animation reference: the head, neck,
  torso, shoulders, hips, limbs and hands are measured, and the height and build stay yours.
  - It runs by itself when a character's first reference is made.
  - **Cast › Body › Fit the body to the animation reference** runs it again. It is also in the reference's right-click menu.
- **The neck point** of the pose skeleton now sits between the shoulders, as the pose models expect. Heads no longer sink into the
  shoulders.
- **The legs** follow the clip's real foot direction. Feet no longer turn sideways, which made the boots look huge.

## 1. compare.mp4 (≈ 3 min)

E23b's Move shot in two versions, side by side at 24 fps, with the same seed and the same moves:

- **Left:** before, with the default dummy.
- **Right:** after, with both bodies fitted.

- **Check:** do Mara and Ines now look like their references, without a short neck or a stocky build?
- **Check:** are their hands and feet a normal size?
- **Check:** anything that looks worse on the right?

`sheet.jpg` shows a frame a second (before on top, after below).

## 2. The numbers in short

Measured on the made characters, as fractions of their height. The reference is the character as cast.

| | Nose to neck | Shoulders | Hands | Feet |
| --- | --- | --- | --- | --- |
| Mara: before → after (reference) | 0.14 → 0.17 (0.16) | 0.21 → 0.23 (0.23) | 0.13 → 0.09 (0.09) | 0.19 → 0.05 (0.04) |
| Ines: before → after (reference) | 0.09 → 0.15 (0.17) | 0.26 → 0.23 (0.23) | 0.15 → 0.14 (0.08) | 0.18 → 0.14 (0.05) |

Ines' hands and feet are measured while she sits down: her fingers are spread and her feet turned out. Please judge those by eye.

## Notes

| Check | Answer |
| --- | --- |
| Proportions like the references? | |
| Hands and feet a normal size? | |
| Anything worse? | |
