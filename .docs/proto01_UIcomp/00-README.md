# proto01_UIcomp · An episode from scratch: today's workflow, an efficient one, and what it means for Story

Status: **research, 2026-10-23; accepted the same day → D125.** Read from the code at `0a943c2`. The author accepted every
recommendation of [04](04-story-structure-and-ui.md) §9 except one: the Catalogue becomes the fourth top tab (Story · Image · Animate ·
Catalogue) instead of staying under Story. Built in waves SP0 → SP7 (04 §8), 2026-10-23; A1 checked on the rig 2026-10-24; the author's
click-through is [05](05-testing-story.md).

## The request

The author, 2026-10-23:

> Image and Animate are comprehensive generation/editing suites with comprehensive functionality, but their connection to Story is not
> clear. […] Can we then record the current workflow for story creation from start to a fully post-processed episode in loom2 — what menu
> options should we use, and how we'd navigate through the application. We should devise an efficient workflow, using the current
> functionality of loom2 for the same reason — creating a story episode from scratch — and compare the two. This should define the
> structure and UI of Story. […] Keep the changes to Image/Animate menus to justified only.

## The documents

| # | Document | What it holds |
| --- | --- | --- |
| 01 | [Today's workflow](01-current-workflow.md) | a reference episode made with today's app, phase by phase: every tab, section, menu and label, with the clicks counted and 24 screenshots; the friction register WF1–WF30; three defects WB1–WB3 |
| 02 | [The efficient workflow](02-efficient-workflow.md) | the same episode with the same functions: eight principles, the steps and their clicks, five habits that help today, and the list of what it needs (Story S1–S15, Image I1–I4, Animate A1–A4) |
| 03 | [The comparison](03-comparison.md) | the numbers side by side, where the difference comes from, route by route, and the six requirements for Story (R1–R6) |
| 04 | [Story: structure and UI](04-story-structure-and-ui.md) | the rail, the shot as the unit, the For-context contract, the states, five wireframes, the commands, the justified Image and Animate changes, the delivery gaps, a build plan, 14 decisions with recommendations |
| 05 | [Trying the new Story](05-testing-story.md) | the author's click-through of the built waves SP0–SP7 (≈ 15 min), with a notes table |

`img/cur-*.jpg` are screenshots of today's app (the fake engine; flat-colour pictures). `img/ui-*.jpg` are wireframes of the proposal,
rendered from `mock/story-mock.html` (a static mock, not the app).

## The reference episode

Two characters, a place and a prop. A script of eight nodes with a Choice. Six shots, one per making route:

- Image to video, twice;
- lip-sync (S2V) on two close-ups;
- a stage clip;
- the clay final shot with a lip-sync pass.

Then two cuts (one per branch), exported for Resolve. 01 §0.1 has the details.

## What was found

1. **Today the episode takes about 351 clicks and 34 tab switches; the efficient workflow about 217 and 30** — 38 % fewer clicks with
   the same functions (03 §1).
2. **Nine tenths of the saving is Story's structure:**
   - the rail in the order of the work;
   - a Flow node that is its shot;
   - a board of every shot and what it owes, whose cells open the makers in context;
   - verbs that act on the episode.

   Image and Animate need four changes each, for **correctness** rather than speed (03 §2).
3. **Three dead ends today**, all on the clay route and approval:
   - the final shot's render never becomes a take of its Story shot;
   - its *Lip-sync* pass can never find a line;
   - no shot of the episode can be marked final, because no route renders the 1920×1080 the gate wants.

   The first two are defects (WB1, WB2), worth fixing on their own (01 §5).
4. **A shot cannot be pointed at a stage camera.** *New shot from this camera…* always makes a new shot, so a node's shot is replaced by
   unbinding, binding and deleting (WF16).
5. **The weak joint is the For context**, the bridge from a Story shot to a maker:
   - it lands scrolled out of view;
   - the last shot's subjects and references are still in the panel;
   - it stays on after *Back to the shot*;
   - re-runs, variations and New angle ignore it;
   - nothing in Image or Animate picks the frame or the clip for the shot.

   See WF10–WF14 and WF20.
6. **Nothing shows the episode's state** — what each shot has and still owes (WF30). The proposed Shots board does.
7. **Story's order is not the work's order.** The Catalogue sits between Props and Shots, Shots before Flow, and World mixes the bible
   with Image's presets (WF3, WF4).
8. **"Fully post-processed" ends in Resolve.** loom2 finishes each shot (the Final level's passes) and exports the cut. The episode's
   conform, grade, mix and master render are Resolve's, and that round trip is still unverified. These gaps are listed for a later wave
   (04 §7).

## The proposal in one picture

```
Story   World ─▶ Cast ─▶ Flow ─▶ Shots (the board) ─▶ Episode ─▶ Export for Resolve ▶   (Catalogue: its own top tab, D125)
                                   │  a cell = a verb for that shot
                                   ├─▶ Image › Make     Generate ▶ · Use as <shot>'s frame · ← Back
                                   └─▶ Animate          the stage · Use this camera · the clip · the final shot · Use as <shot>'s clip · ← Back
```

Image and Animate keep their modes, sections and cards. They get the For context done right (I1, I3, I4, A2), two *Use as …* verbs
(I2, A4), *Use this camera for <shot>* (A3), and the final shot's fix (A1).

## Method

- **Story suite:** read from the code.
- **Image, Animate and the backend:** mapped by three helper reads. Their load-bearing claims were checked against the code:
  - WB1 and WB2 (`finalShot.ts:350`, `finishers.py:1005,1099`, `story.py:827-831`);
  - the size gate and the tiers (`story.py:326-340`, `models/specs/wan*.toml`, `ltx23.toml`);
  - *Duplicate node* copying the spoken lines (`storyStore.ts:859-862`).
- **Screenshots:** a throwaway Playwright walk on the e2e build with the fake engine, then deleted.
- **Counting rules:** those of UX0 (01 §0.2). Counts come from the code paths, not from timing on the rig.
