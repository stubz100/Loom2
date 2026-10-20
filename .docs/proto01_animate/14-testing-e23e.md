# 14 · Looking at E23e — shadows that start at the character's feet (for the author)

About 5 minutes. You saw the characters sit slightly off their shadows. Wan Animate places a character near the dummy, not exactly on
it: measured on the floor, Mara is 5.5 cm away (median; 90 % of frames within 15 cm) and Ines 11.6 cm (within 14 cm). The files are
local, under `engine/spikes/out/e23e/` (not in git).

## What was tried

1. **The shadow follows the character.** The pose detector finds where Wan actually put each character's feet in every frame, and
   Stage moves the dummy (or the character-shaped mesh) there before it renders the shadow. The card is cast from those feet too.
2. **The character follows the mesh.** Wan's Replace mode is asked to fill the mesh's silhouette with the character, so she stands
   exactly where the mesh and its shadow are.

## compare.mp4 (≈ 3 min)

24 fps, six panels, the same characters (seed 20261021):

| | left | middle | right |
| --- | --- | --- | --- |
| **top** | the dummy's shadow, as before | the dummy's shadow, moved to the feet | the card, cast from the feet |
| **bottom** | the mesh's shadow, as before | **the mesh's shadow, moved to the feet** | Replace inside the mesh |

- **Check:** in the middle column, do the shadows now start at the boots, compared with the left?
- **Check:** the bottom right (Replace): the characters sit on their shadows, but a dark outline is left around them (most on Ines'
  pointing arm). Is it usable?

## What the measures say

- **Moving the shadow** helps Mara most. The gap from her boots to the shadow halves (49 → 26 px for the dummy, 40 → 26 for the
  mesh); what remains is the shadow's faint first stretch, under this low side light. Ines' shadows already started at her feet.
- **Replace inside the mesh** follows the poses less well (Mara 0.74, Ines 0.91, against 0.98–1.0 in Move). It leaves the blank fill
  on 27 % of Ines' silhouette, where the mesh's jacket stretches when she sits.

## 3. Your nudge: nudge.mp4 (≈ 2 min)

Your idea was to move the character, not the shadow. Mara's ankles sit on the dummy's within 2 px, but her boots reach lower than
the dummy's thin feet, and the shadow starts at the dummy's soles. Aligning the soles gives one offset per character: **Mara 3 px
right and 12 px up**, as you saw.

`nudge.mp4` shows six panels:

| | left | middle | right |
| --- | --- | --- | --- |
| **top** | the mesh's shadow, as before | the character nudged (one offset) | the character nudged (per frame) |
| **bottom** | the dummy's shadow, as before | the character nudged (one offset) | the character nudged (per frame) |

- **Check:** do Mara's boots now meet the start of her shadow?

**My recommendation:**

- Leave the shadows where Stage casts them.
- Give each character layer a contact offset: proposed from the two anchor pins (the dummy's soles, the character's soles), draggable in the editor, one per shot by default.
- Don't take up Replace.

## Notes

| Check | Answer |
| --- | --- |
| Do the moved shadows start at the feet? | Superseded by the nudge |
| Replace inside the mesh usable? | Not taken up |
| The nudged version right? | Yes: "the nudge helped" (2026-10-20) → D107 |

Ticked off by the author, 2026-10-20.
