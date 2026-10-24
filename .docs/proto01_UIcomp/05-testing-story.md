# 05 · Trying the new Story (for the author)

About 15 minutes; no GPU job is needed until the optional steps marked ⚙ (each queues one job, one at a time, D97). D125 (doc 04): the top
bar is **Story · Image · Animate · Catalogue**; Story's rail is **World · Cast · Flow · Shots · Episode**, the order of the work; a
Dialogue or Shot node *is* its shot; **Shots** is a board of every shot against its steps, and a cell does its step; Image and Animate
open on the shot and hand their results back to it; the Episode is assembled from the Flow and exported for Resolve in one go. This is
your click-through: your notes decide what changes next. Wherever a small **?** sits beside an item, hover it for the words.

Start with `scripts/dev.ps1` and a **new project** (it opens on World), or a copy of one you have.

## 1. World and the Flow from the spine (≈ 2 min)

- World's sections are **Logline · Synopsis · Spine · Styles · Variables**, then **Presets** (the Library and Saved panels) at the end.
- Write a logline and add three or four beats to the **Spine** (a title and a line each).
- The foot is **Make the Flow from the spine ▶** (also the icon in the Spine heading, and a beat's right-click). It asks with the count;
  say yes. The Flow opens: a Start, then one **Shot node per beat**, in a row and connected in the spine's order.
- Back on World the foot no longer offers it: every beat has its node. Add a beat — it offers one again.
- **Check:** is a Shot node per beat the right start, or should a beat become a Dialogue node when its line is speech?

## 2. Flow — a node is its shot (≈ 3 min)

- Add a **Dialogue** node (the strip, or right-click the canvas) and write two lines with speakers. It has its shot at once; its card
  shows the shot's steps as small pills (voice · frame · clip · approved).
- Click a node: the Inspector is **one panel** — the node's fields, then its shot's (version, frame, clip, recipe), then the node's verbs.
  Renaming the node renames its shot until you rename the shot by hand.
- Connect a node after one that has a place (*where*): it takes that place. *Also for the nodes after it* (the where field) carries it on.
- **Delete node** asks once, with one checkbox: *Delete its shot <name> too* (its frames and clips stay in the Catalogue).
- The strip's **Voice all lines (N)** counts every line of the episode not voiced yet, or changed since. ⚙ Press it (pick a voice under
  a node's lines first if a speaker has none).
- **Check:** is one panel for node and shot clear, or do you miss the separate shot Inspector? Are the pills on the cards readable?

## 3. Cast — what each version owes (≈ 2 min)

- **Cast** has *all · characters · places · props*. Each row now says what its current version owes for its shots: *3 owed for 2 shots*,
  *ready for 2 shots*, *in no shot*.
- Open a character: under the strip the **readiness row** — Hero · Sheet · References · Animation reference · Body · Voice · LoRA · Final
  (a place has fewer; a prop has a 3D model instead of a body). ✓ done, ○ a shot needs it, – nothing needs it yet. Each item is its verb:
  click one. Hover an item: it says which shots need it.
- **In N shots** on the page lists those shots with their route and what each still needs; a click opens the shot on the board.
- The foot is the next owed step (*Make an animation reference ▶ · for Arrival*), Expand as before when nothing is owed.
- **New voice…** in the Inspector: the voice you make there is this character's (a second one too).
- **Check:** are the items and their order right? Should Final be owed by every shot, or only when you mark the shot final?

## 4. Shots — the board (≈ 3 min)

- **Shots** is a table: every shot in the Flow's order (a Choice's branches as group rows) against **Lines · Voice · Frame · Stage · Clip ·
  Final · Lip-sync · Approved · In cut**. ✓ done, ○ owed (a click does it), ◐ running, ! its input changed, – not on this shot's route
  (the route is the recipe template — the Inspector changes it).
- Click a shot's row: its page sits under the board. The foot is that shot's **next step** (Ctrl+Enter).
- Click a **Stage** cell on a shot without a stage: **Link a stage camera…** picks a stage and camera for this shot (no second shot), or
  **A new stage for it…** makes one named after the shot and opens Animate › Clay on it.
- The panel's filter: *all · owes a step · stale · not approved*.
- **Check:** are these the right columns, in the right order? Is a click on a cell doing the step what you expect, or would you rather a
  cell only select and the foot do?

## 5. Image and Animate for a shot (≈ 3 min)

- Click a shot's **Frame** cell: Image › Make opens on **Prompt** with the **For chip** at the column's head — it stays there however far
  the column scrolls. The panel holds *this* shot's content (its line, its speakers as subjects, its place as the scene, its board as
  references); the last shot's is gone; your look, model and size stay.
- ⚙ **Generate**. The first result fills the frame (a *frame ✓* badge on its tile). Hover another: **✓** makes it the frame; its
  right-click and the Inspector say **Use as <shot>'s frame** too. **← Back to <shot>** returns and ends the For context.
- On a linked shot, the **Clip** cell opens Animate › Performance on **Stage clip** for the shot; the **Final** cell opens the final shot.
- In **Clay › Camera** with the chip: **Use this camera for <shot>** (*New shot from this camera…* only without a chip). In
  **Performance**, a played clip: **Use as <shot>'s clip** on the transport.
- ⚙ *Make the final shot* with the chip says the finished shot becomes the shot's take; its assembly lands as a take, its render as the
  clip (checked on the rig, journal 2026-10-24 01:25).
- **Check:** does Image's landing feel right (Prompt, the chip in view)? Is anything of the last shot you *wanted* kept now cleared?

## 6. Episode — the cut from the Flow (≈ 2 min)

- The Episode's foot (no cut open) is **Assemble from the Flow…**: the sheet asks at each Choice which option this cut follows, says how
  many shots it will hold (and which have no clip yet), and names the cut after the route (*Episode 1 · Stay*). Assemble.
- **Approved** on the board marks a version final at any size; the export's checklist lists clips below the format as a note.
- Give a shot on the lane a newer take (use another clip as its clip): its lane clip shows **changed · Update**; the checklist lists it;
  *Update* swaps it and keeps the trims. **Assemble again…** (the Inspector) rebuilds the cut from its route, keeping trims and dissolves.
- **Export for Resolve ▶** asks once (only when something is listed) and writes one folder named after the cut: the FCPXML with markers
  and the voice lane, the EDL, the SRT and markers.txt. The single exports are still under *one file*.
- **Check:** import the folder into Resolve — does it conform? Is a cut per route right?

## Notes

| Check | Answer |
| --- | --- |
| The top bar with the Catalogue as the fourth tab: right? | |
| Make the Flow from the spine: Shot nodes per beat, or Dialogue for speech? | |
| One panel for a node and its shot: clear? | |
| The cards' step pills: readable, useful? | |
| Cast's readiness items and order; Final owed by every shot? | |
| The board's columns and their order; a cell click doing the step? | |
| Image's landing for a shot; anything wrongly cleared? | |
| Use this camera / Use as clip: found where you looked? | |
| Assemble from the Flow; a cut per route; changed · Update? | |
| Export for Resolve: does Resolve take the folder? | |
