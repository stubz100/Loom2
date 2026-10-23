# 03 · Today against the efficient workflow

Status: **research, 2026-10-23.** It compares [01](01-current-workflow.md) (today) with [02](02-efficient-workflow.md) (the efficient
workflow) on the same reference episode, and says what the difference means for Story ([04](04-story-structure-and-ui.md)).

## 1. The numbers

| Phase | Clicks today | Efficient | Saved | Tab switches today → efficient | Dead ends today |
| --- | --- | --- | --- | --- | --- |
| Project | 4 | 3 | 1 | 0 → 0 | |
| World | 21 | 7 | 14 | 0 → 0 | |
| Cast (2 characters, a place, a prop) | 77 | 68 | 9 | 12 → 12 | |
| Flow and voices | 72 | 37 | 35 | 0 → 0 | |
| Frames (4) | 36 | 16 | 20 | 8 → 8 | |
| Image to video (2) | 10 | 6 | 4 | 4 → 4 | |
| Lip-sync S2V (2) | 10 | 6 | 4 | 0 → 0 | |
| Stage clip | 33 | 12 | 21 | 6 → 4 | |
| Final shot | 49 | 37 | 12 | 4 → 2 | 2 (the line, the take) |
| Approval (6) | 12 | 12 | 0 | 0 → 0 | 1 (the size gate) |
| Cut (one route) | 20 | 10 | 10 | 0 → 0 | |
| Delivery | 7 | 3 | 4 | 0 → 0 | |
| **Episode** | **≈ 351** | **≈ 217** | **≈ 134 (38 %)** | **34 → 30** | **3 → 0** |

Beyond the clicks:

| Measure | Today | Efficient |
| --- | --- | --- |
| Animate levels switched by hand | 5 | 0 (a board cell opens the right level and card) |
| Shots created only to be deleted (the stage link workaround) | 2 | 0 |
| Shots that can be marked final | 0 of 6 | 6 of 6 |
| Things the author must know because nothing says so (01 §4, **hidden**) | 7 | 2 (WF23 the Clay range sets a final's length; WF29 finishing is in Resolve) |
| Where the episode's state can be seen | nowhere; *Validate* lists non-final shots | the Shots board |
| Lines typed twice / voiced twice (coverage) | 2 / 2 | 0 / 0 (voice, then *Duplicate node*) |
| Ways a maker's work silently goes to the wrong shot | 3 (the For context left on; leaked panel; ignored chip) | 0 |

**Tab switches barely change**, and that is expected: making a picture is Image's job and making a clip is Animate's. What changes is
that each switch is a jump *with* its context (a board cell → the maker on that shot → *← Back*), not a search for the place to go.

## 2. Where the difference comes from

The 134 clicks, split by the suite whose change saves them:

| Cause | Clicks | Share | Items |
| --- | --- | --- | --- |
| **Story's structure and verbs** | ≈ 119 | 89 % | the Flow from the spine (14); a visual node is a shot, the place carried, voices for the episode, coverage by duplicate (35); board cells instead of row › menu › entry (16); the stage link (S11: 30); the cut assembled from the Flow and the export in one (14); the Cast readiness row (9); the start on World (1) |
| **Image** | ≈ 12 | 9 % | I1: no scrolling to the chip, nothing leaked to reset (3 per frame) |
| **Animate** | ≈ 3 | 2 % | A2: *Make clip ▸ on the stage* on its card (4), less A1's lip-sync pass, which costs clicks because it now works (−1) |

Two things follow.

1. **The efficiency is in Story.** Nine tenths of the saving is Story's structure: the order of its workspaces, the shot as its unit,
   a board that is the entrance to every making step, and verbs that act on the episode. Image and Animate need almost nothing for
   speed.
2. **Image and Animate need changes for correctness, not speed.** Their eight items (02 §5) remove the dead ends and the wrong-shot
   risks: picking the frame or the clip where it is seen (I2, A4), keeping the context visible and honoured and ending it (I1, I3, I4),
   linking a camera instead of duplicating a shot (A3), and the final shot that reaches its shot (A1). Each is a verb or a fix on an
   existing section, not a new section.

## 3. Route by route

| Route | Today | Efficient |
| --- | --- | --- |
| **A frame** | Shots › row › *Make frame ▾* › *in Image* · scroll to the chip · undo the leftovers · *Generate* · the first result wins · *← Back* · Takes ✓ | board cell · *Generate* · *Use as <shot>'s frame* · *← Back* |
| **Image to video** | row › *Make clip ▾* › *in Animate* · *Animate ▶* · *← Back* | board cell · *Animate ▶* · *← Back* |
| **Lip-sync (S2V)** | row › *Make clip ▾* › *Lip-sync ▶* · queue · Takes ✓ | board cell · queue · ✓ in the board's take strip |
| **Stage clip** | Animate › Clay › stage › camera · *New shot from this camera…* (a new shot) · Flow: unbind, bind · Shots: delete the old shot · *Make frame ▾ › from the stage* · Story › *Make clip ▾ › on the stage* (lands in Clay) · Performance › Stage clip · start · *Render clip* · Story | board cell *Link a stage camera…* · frame the camera · Frame cell (From a stage) · Clip cell (the Stage clip card, the frame as start) · *Render clip* · *← Back* |
| **Clay final shot** | Animate › Clay › *New stage…* … *Render passes* · *New shot from this camera…* · the re-bind · Performance › Final shot … *Open in Final* · the lip-sync pass finds no line · *Render the finished shot* · the render never reaches the shot | board cell *Block it on a stage…* … *Render passes* · Final cell … *Open in Final* · the lip-sync pass on Mara's line · *Render the finished shot* (a take of Reunion) · *← Back* |
| **Approval** | *Mark final*: refused below 1920×1080 | *Mark final*: the take is approved; the export lists clips below the format |
| **The cut** | *New cut* · + each shot · reorder by hand · dissolves · a second cut by hand | *Assemble from the Flow…* (the route) · dissolves · the next route in 3 clicks; newer takes marked *changed* |
| **Delivery** | three exports, three checklists | *Export for Resolve ▶*, one checklist |

## 4. What the comparison says Story must be

These are the requirements [04](04-story-structure-and-ui.md) turns into a structure and screens.

| # | Requirement | Because |
| --- | --- | --- |
| R1 | **Story is the production spine.** Its rail is the order of the work: World → Cast → Flow → Shots → Episode. The Catalogue and Image's presets are tools, after it | WF1, WF3, WF4 |
| R2 | **The shot is Story's central object.** The Flow's visual nodes are shots; the Shots workspace lists them in the route's order; every trip to a maker starts at a shot and ends at it | WF6, WF16, WF20 |
| R3 | **Story shows state at three scales:** a shot (its steps), a character (its readiness for the shots it is in), the episode (the board, the cut's *changed* marks) | WF5, WF22, WF26, WF30 |
| R4 | **Story orchestrates; Image and Animate make.** Story never generates by itself: its cells open the maker in context, and its few episode verbs queue exactly the jobs the makers would (voices, the cut, the export) | the brief: no new functions |
| R5 | **Story owns the cut and the hand-off to Resolve,** and approval is the author's decision, not a size | WF24, WF25, WF27 |
| R6 | **Image and Animate keep their structure.** They need a For context that is visible, honoured and ended, and a *Use as <shot>'s …* verb | WF10–WF14, WF17, WF20 |

What the comparison does **not** ask for: a new suite, a second shot editor in Story (Animate stays the shot editor, D96), the recipe
graph (RC1 stays as planned), or any change to Image's column, Edit, or Animate's three modes.
