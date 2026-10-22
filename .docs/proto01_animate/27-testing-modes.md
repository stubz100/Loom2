# 27 · Trying Animate's three modes (for the author)

About 10 minutes, no GPU job needed (the last step queues one, optional). D121 (doc 26): Animate's levels became modes — **Clay**,
**Performance** and **Final** each have their own column, rail, strip, viewer and foot; the **Shot** section heads all three with the stage
and its steps; **one transport and one timeline** under every viewer; the camera's chrome sits on the viewport. This is UX9: your
click-through, and your notes decide what changes next. Wherever a small **?** sits beside an item, hover it for the words.

## 1. Clay — compose (≈ 3 min)

- `scripts/dev.ps1`, open a project with a stage (or **New stage…** in the foot), Animate ▸ **Clay**.
- The column is only **Shot · Scene · Motion · Camera**. In Shot: the **stage** picker (no more list of every stage) and the **stepper** —
  passes · frame · clip · final · composition · render, each a dot (hollow not yet, filled done, amber stale, pulsing running).
- The foot is **Render passes ▶** (Ctrl+Enter). Press it: the *passes* dot fills.
- Select a figure: a **Pose Figure 1** pill appears over the viewport. Press it — the joint pickers show; **Done posing** (or a click on the
  floor) hides them. The Motion section no longer switches pose mode by being on screen.
- Top right of the viewport, the **camera pill**: *Free view · ★ Camera 1 · 35 mm*. Click it to look through; click again to come back. Its
  lens menu (the aperture icon) picks another camera and sets the lens — the focal length shows large for a moment.
- Bottom right, in the free view, the **picture-in-picture** of the active camera; move a figure and watch it follow. Click it to look
  through. The strip's PiP button (or the pill's menu) turns it off.
- **Check:** is the stepper's row the rig you wanted (21 §4b), or should the step's verb sit on it too? Is the PiP the right size and
  place? Should it stay on by default?

## 2. The timeline (≈ 2 min)

- Under the viewport: one transport (the same buttons at every level) and a ruler. The **range** is the bright band — drag its ends.
- **Key camera** at frame 0, type 30 in the frame field, move the camera, **Key camera** again: a row *camera · Camera 1* with two
  diamonds. Drag a diamond to another frame; right-click it to remove it; click it to go there. A motion clip applied to a figure shows as a
  bar on the figure's row.
- Keys: Space plays, ← / → step, Home / End the range's ends, Alt+← / → the previous / next key — the same at every level.
- **Check:** are the rows the right ones (the camera and each keyed object)? Do you miss the old single scrubber anywhere?

## 3. Performance — make the moving picture (≈ 3 min)

- The **Performance** switch at the start of the strip (or 2). The column is **Shot · Performance · Clips**.
- The Performance section's three cards: **Image to video** (the form you know; foot *Animate ▶*), **Stage clip** (the stage's sequence
  animated from one of its frames; foot *Render clip ▶*, which renders the sequence first when it is missing or stale), **Final shot** (the
  layered route; the foot is the **next step**: *Make the final shot…*, *Make the plate*, *Perform <name>*, *Assemble*, *Make the
  composition*, *Open in Final*).
- The stage's frames are made in **Image › From a stage** now — the Stage clip card's *Make a frame ▸* and the stepper's *frame* dot go
  there; a frame clicked there is the clip's start here.
- In **Clips**, click a clip: it plays, and its details open **under its row** (the facts and verbs, the harvested frames, the lineage);
  click the row again to fold them. The Selection section is gone.
- **Check:** are *Image to video · Stage clip · Final shot* the right three cards and names? Is the final shot's "next step" foot what you
  want, or would you rather press each step in its row as before (both still work)?

## 4. Final — finish (≈ 2 min)

- The **Final** switch (or 3). The column is **Shot · Layers · Output**. Under the stepper, the stage's finals — **Open** one (or *Make the
  composition* when it is assembled). Layers is the editor you know; **Output** says what was rendered and from which revision; the foot is
  **Render the finished shot ▶** (Ctrl+Enter).
- The lanes are the same timeline as Clay's: drag a bar, its ends, Alt-drag to slip.
- **Check:** is anything you need at Final still only at Performance? Does Output say enough?

## Notes

| Check | Answer |
| --- | --- |
| Three modes: the right cut? | |
| The stepper: right, or the verbs on it too? | |
| The pose pill instead of the Motion section: right? | |
| The camera pill and the PiP: right place, size, on by default? | |
| The timeline's rows: right? Missing anything of the old scrubbers? | |
| The cards' names and the final shot's next-step foot? | |
| Frames in Image › From a stage — still right with the stepper's jump? | |
| A clip's details under its row instead of Selection? | |
| Final: anything missing, Output enough? | |
