# 02 · The efficient workflow: the same episode with the same functions

Status: **research proposal, 2026-10-23; nothing decided or built.** It makes the reference episode of
[01](01-current-workflow.md) §0.1 again. Every generation, edit, stage, pass and export is one loom2 has today. What changes is three
things: the order of the work, where each step is started from, and how its result comes back. [03](03-comparison.md) compares the two
workflows; [04](04-story-structure-and-ui.md) turns this one into Story's structure and UI.

## 0. The brief and the boundary

**The brief** (the author, 2026-10-23): devise an efficient workflow for creating an episode from scratch, *using the current
functionality of loom2*, and compare it with today's. Keep changes to Image's and Animate's menus to the justified ones.

**What may be new.** Each item this workflow needs is tagged with one of four kinds:

| Tag | Meaning | Example |
| --- | --- | --- |
| **view** | a new view or control over records and commands that exist | the Shots board's cells |
| **orchestration** | a command that calls existing routes in order | *Assemble from the Flow…* |
| **rule** | a changed default or condition | *Mark final* at any size |
| **fix** | a defect of 01 §5, or a context that is lost | the final shot carries its Story shot |

**What is not new.** No new model, job kind, custom node or pass. Delivery still ends with an export to Resolve (01 §6). The gaps there
are listed for a later wave in 04 §7.

## 1. Eight principles, each from 01's register

| # | Principle | Removes |
| --- | --- | --- |
| P1 | **The shot is the unit.** Every making step starts from a shot and comes back to it. A visual Flow node has its shot from the start | WF6, WF12, WF16, WF20 |
| P2 | **Story follows the production order:** World → Cast → Flow → Shots → Episode. Tools (the Catalogue, Image's presets) sit after it, not inside it | WF1, WF3, WF4 |
| P3 | **One state per shot, seen across the episode.** A board shows what every shot has and still owes | WF5, WF22, WF30 |
| P4 | **A maker opened for a shot is visibly in that shot's context** until the author goes back, and every verb in it honours that context | WF10, WF11, WF13, WF14, WF17, WF21 |
| P5 | **Choose where you look.** The frame is picked among the results in Image; the clip among the clips in Animate | WF12, WF20 |
| P6 | **Approval is a decision, not a size check.** *Mark final* marks the take the author wants; the size is a delivery question | WF24 |
| P7 | **The cut is derived from the script, then edited.** It follows the shots' approved takes | WF25, WF26 |
| P8 | **Repeated verbs work on the episode:** make the Flow from the spine, voice every line, export once | WF2, WF9, WF27 |

## 2. The workflow at a glance

```
Story › World      the bible and the spine ─────────────── Make the Flow from the spine ▸
Story › Cast       who and where; each version's readiness for the shots it is in
Story › Flow       the script: nodes, lines, places; Voice all lines ▸; a visual node is a shot
Story › Shots      the board: every shot × its steps; a cell opens the maker for that shot
                      ├─ Image › Make     the frame: Generate ▶, then "Use as <shot>'s frame", ← back
                      └─ Animate          the stage, the clip, the final shot: "Use …", ← back
                   Approve: Mark final, at any size
Story › Episode    Assemble from the Flow ▸ (a cut per route) · dissolves · Export for Resolve ▶
DaVinci Resolve    conform, grade, mix, titles, master (unchanged: 01 §6)
```

The author stays in **Story** and leaves it only to make a picture or a clip. Each trip out starts from a cell of the board and ends with
a *Use as …* verb and *← Back to <shot>*.

## 3. Step by step, with the clicks

The counting rules are 01 §0.2. The tags in brackets point at the items of §5.

### 3.1 Project — 3 clicks

**Project ▾** › *New project…* + *Create* (3). A project without a story opens on **Story › World** [S2]. (Today: 4.)

### 3.2 The bible — Story › World — 7 clicks

1. Logline, synopsis typed; *Add style* + *Make a sample image* (2); *Add beat* ×3 (3).
2. **Make the Flow from the spine…** + OK (2) [S4]: a Start node and one Shot node per beat, laid out in a row, connected in the spine's
   order, each with its shot (P1). Beats already turned into nodes are skipped. *Make a Flow node from this beat* stays for one beat.

World reads as the bible: Logline · Synopsis · Spine · Styles · Variables, with Image's Library and Saved panels after them under one
*Presets* heading [S3]. (Today: 21.)

### 3.3 Characters, a place, a prop — Story › Cast — 68 clicks

The making is unchanged: the hero from a result (*Make a character / place / prop…*), *Expand in Image…* (D115), the candidates, the
animation reference, the body fit, the voice, *Mark final*. What changes is that the version page says **what the version still owes for
the shots it is in** [S5]:

```
Mara · v1   Hero ✓ › Sheet ✓ › References 9 ✓ › Animation reference ✗ › Body ✗ › Voice ✗ › LoRA – › Final ○
In 3 shots:  Reunion (clay: animation reference, body) · Mara close (lip-sync: voice) · Talk
```

Each item is its verb (*Make an animation reference*, *Fit the body*, *Voice ▸*, *Train a LoRA…*, *Mark final*), so nothing is
remembered. Two small savings: a candidate's ✓ menu offers *as the animation reference* (1 instead of 2), and *Create* in the voice form
gives the voice to the character it was opened from (no second select).

Per character: hero 6, Expand 12, animation reference and body 3, voice 3, final 2 = **26**. Two characters 52, the Tavern 6, the
Lantern 10 (hero 6, animation reference 2, 3D model 2). Props are a class of the Cast workspace with their 3D model section [S1].
(Today: 77.)

### 3.4 The script and the voices — Story › Flow — 37 clicks

1. *Reunion* becomes a Dialogue with its two lines (8). *Talk* (a Dialogue, two lines: 8) and *Stay or go* (a Choice, two options: 4)
   from the palette.
2. **Where** is set once, on *Arrival* (2), and its *also for the 2 nodes after it* (1) gives Reunion and The door the Tavern. A node
   added or connected later takes the place of the visual node before it [S7].
3. **Voice all lines (4)** on the Flow strip (1) [S8]: one job per voice for every unvoiced or changed line of the episode.
4. **The close-ups from the wide, after the voices:** select *Reunion*, *Duplicate node* (1), drag it into place (1), ✕ the other
   speaker's line (1) — three clicks each, six for both. *Duplicate node* already copies the lines **with their spoken audio**
   (`storyStore.ts:862`), so nothing is typed or voiced twice. This is today's function used in the right order; it does not solve
   coverage in general (04 §6, decision 9).
5. The connections: one right-click to delete Reunion → The door (2) and five handle drags (5).
6. No *New shot for this node…*: every visual node has its shot already (P1) [S6].

8 + 12 + 3 + 1 + 6 + 7 = **37** for script and voices. (Today: 64 + 8 = 72.)

### 3.5 The board — Story › Shots

Rail *Shots*. The board lists the six shots **in the route's order** (*Arrival, Reunion, Mara close, Ines close, Stay or go ▸ Talk / The
door*), one row each, with a cell per step [S9]:

| Shot | Lines | Voice | Frame | Stage | Clip | Final | Lip-sync | Approved | In cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Arrival | – | – | ○ | – | ○ | – | – | ○ | ○ |
| Reunion | 2 | ✓ | – | ○ | – | ○ | ○ | ○ | ○ |
| Mara close | 1 | ✓ | ○ | – | – | – | ○ | ○ | ○ |
| … | | | | | | | | | |

A cell shows its state (✓ done, ○ owed, ◐ running, ! stale, – not used by this shot's route) and **is the verb**: a click on *Arrival ›
Frame* is *Make frame in Image* for Arrival; on *Reunion › Stage* it is *Block it on a stage…*. The route of a shot (its recipe template,
RC0) is set by the first making verb the author picks for it; it decides which cells are owed. The selected row opens **the shot page**
under the board: its versions, the player, its takes (✓ use), its node's lines and place, and its recipe with *Run stale…* [S10].

### 3.6 Frames — 16 clicks (4 shots × 4)

For *Arrival*, *Mara close*, *Ines close*, *Talk*:

1. The board's **Frame** cell (1). Image › Make opens **on the For chip**, the source on *Prompt*, the panel holding this shot's content
   only: its subjects, its scene, its board's references. The look, the model and the size stay as the author last left them (they are
   the production's, not the shot's) [I1].
2. *Generate 4 ▶* (1).
3. On the chosen result, **Use as Mara close's frame** (1): a ✓ on the tile while the chip is set, also in its right-click menu and the
   Inspector [I2].
4. **← Back to Mara close** (1). It ends the For context [I3].

(Today: 36.)

### 3.7 Clips, Image to video — 6 clicks (2 × 3)

For *Arrival* and *Talk*: the **Clip** cell (1), *Animate ▶* (1), *← Back* (1). The first clip fills the empty slot. To choose another:
**Use as Talk's clip** on its row in the Clips section (+1) [A4]. (Today: 10.)

### 3.8 Lip-sync on the close-ups (S2V, experimental) — 6 clicks (2 × 3)

The **Lip-sync** cell (1), *Queue the job* (1); when the take lands, ✓ in the board's take strip (1). The cell's tooltip carries the
limits (English, a line of at most 4.8 s, a frame first). (Today: 10.)

### 3.9 A stage clip (The door) — 12 clicks

1. The **Stage** cell: **Link a stage camera…** (1) — a small sheet: the stage (the Tavern) and *a new camera* or an existing one (2)
   [S11]. The shot's version now points at that stage and camera; no new shot, nothing to unbind or delete.
2. Animate › Clay opens on that camera with the For chip. Frame it (≈ 2), *Set from view* (1).
3. The **Frame** cell, which now reads *from the stage* (1): Image › From a stage on that camera, *Render passes* + *Render frame ▶* (2).
4. The **Clip** cell (1): Animate › Performance › **Stage clip** with the shot's frame as the start [A2]. *Render clip ▶* (1). *← Back*
   (1).

(Today: 33.)

### 3.10 The clay final shot (Reunion) — 37 clicks, no dead end

1. The **Stage** cell: **Block it on a stage…** (1) + OK (1) [S11]: a new stage named after the shot, its camera linked to the shot's
   version, the For chip set, Animate › Clay open. The set (1); two figures (4); each bound (2); a motion per figure (6); the camera (4);
   *Render passes ▶* (1). **20**
2. The **Final** cell (1): Performance › *Final shot*; *Make the final shot…* + OK (2), now **for Reunion v1** [A1]; *Make the plate*,
   *Perform* ×2, *Assemble the shot*, *Make the composition*, *Open in Final* (6). **9**
3. Final: Mara's layer, *Passes*, *Lip-sync* (3); *Attach a line…* now lists Reunion's voiced lines; Mara's line (2); *Run the pass* (1);
   *Render the finished shot ▶* (1). The render **lands as Reunion's take** [A1]. **7**
4. *← Back to Reunion* (1); the board shows the take. **1**

20 + 9 + 7 + 1 = **37**. The levels are switched by the cells, not by hand. (Today: 49 and two dead ends.)

### 3.11 Approval — 12 clicks, all of them succeed

The **Approved** cell, or *Mark final* on the shot page, and its confirm (2 × 6). It marks the version final **at any size** [S12]: it
fixes the take the Flow and the Episode bind. The size is checked where it matters, at export: the checklist says "4 clips below the
format (832×480 …)". (Today: 12 clicks and none succeeds.)

### 3.12 The cut — Story › Episode — 10 clicks per route, 3 for the next

**Assemble from the Flow…** (1): the sheet asks at each Choice which option this cut follows (*Stay*) (1), OK (1) [S13]. The lane gets
each shot of the route, in order, at its approved take (else the current one), stamped as today. Two dissolves (6). *Play* (1).

The *Leave* route: *Assemble from the Flow…* again with *Leave* (3). When a shot gets a new approved take, its lane clip is marked
**changed** and *Update* swaps it (RC3's rule). (Today: 20 per route.)

### 3.13 Delivery — 3 clicks

**Export for Resolve ▶** (1): the FCPXML with markers and the voice lane, the EDL, the SRT and `markers.txt`, in one folder named after
the cut; the checklist asks once, only when something is listed (1) [S14]. *Render draft* (1). Finishing stays in Resolve (01 §6).

### 3.14 The total

| Phase | Clicks today (01) | Clicks here |
| --- | --- | --- |
| Project | 4 | 3 |
| World | 21 | 7 |
| Cast | 77 | 68 |
| Flow and voices | 72 | 37 |
| Frames (4) | 36 | 16 |
| Image to video (2) | 10 | 6 |
| Lip-sync S2V (2) | 10 | 6 |
| Stage clip | 33 | 12 |
| Final shot | 49 | 37 |
| Approval (6) | 12 | 12 |
| Cut (one route) | 20 | 10 |
| Delivery | 7 | 3 |
| **Episode** | **≈ 351** | **≈ 217** |

[03](03-comparison.md) breaks this down by cause and adds the tab switches, the dead ends and the things the author must know.

## 4. What can be done better today, before any change

The workflow above needs the changes of §5. Five habits save time with the app as it is:

1. **Give each Dialogue node its place and speakers before *Make frame*.** The pre-fill then links the scene and one subject card per
   speaker (`makeFor.ts:55-68`).
2. **Voice a scene's master node, then *Duplicate node* for its coverage.** The copies keep the spoken lines; delete the lines a
   close-up does not need.
3. **Press the For chip's ✕ after *Back to <shot>*** before making anything else in Image or Animate (WF13).
4. **Make the stage and its camera before the shot,** then *New shot from this camera…* and bind that shot in the Flow. This avoids the
   duplicate-and-delete of 01 §2.9 — the node is created without a shot, and its shot is bound instead of spawned.
5. **Keep the final shot's render** in mind: it does not reach the shot (WB1, WB2). Until the fix, note its clip id; the shot cannot take
   it from the UI.

## 5. What this workflow needs

Story items are the substance of [04](04-story-structure-and-ui.md). The Image and Animate items are **only the ones the round trip
cannot do without**; each says which friction it removes.

### Story

| # | Item | Tag | Removes |
| --- | --- | --- | --- |
| S1 | The rail in production order: **World · Cast · Flow · Shots · Episode**, then the **Catalogue**; Props a class of Cast | view | WF4 |
| S2 | A project without a story opens on World | rule | WF1 |
| S3 | World: the bible first; Library and Saved panels under one *Presets* heading at the end | view | WF3 |
| S4 | *Make the Flow from the spine…* | orchestration | WF2 |
| S5 | The version's readiness row and *In N shots* | view | WF5 |
| S6 | A visual node has its shot from the start | rule | WF6 |
| S7 | A new or connected node takes the place of the visual node before it; setting a place offers *also for the N nodes after it* | rule | WF8 |
| S8 | *Voice all lines (N)* for the episode | orchestration | WF9 |
| S9 | The Shots board: the shots in route order × their steps; each cell is its verb | view | WF22, WF30 |
| S10 | The shot page under the board: versions, player, takes, the node's lines and place, the recipe | view | (RC2's direction) |
| S11 | *Link a stage camera…* and *Block it on a stage…* on a shot (the version's source set by a route) | orchestration + a route | WF16 |
| S12 | *Mark final* at any size; the size listed by the export checklist | rule | WF24 |
| S13 | *Assemble from the Flow…*; the lane marks a shot's newer approved take as changed, *Update* swaps it | orchestration | WF25, WF26 |
| S14 | *Export for Resolve ▶*: one folder, one checklist | orchestration | WF27 |
| S15 | The Episode's explanation behind its ? | rule (D116) | WF28 |

### Image — justified changes only

| # | Change | Tag | Why it is needed |
| --- | --- | --- | --- |
| I1 | *Make frame ▸* lands on the For chip and the *Prompt* source, with the shot's own content reset (subjects, scene, references); look, model and size kept | fix | without it the first thing seen is the wrong shot's leftovers, and the chip that says what is being made is off screen (WF10, WF11) |
| I2 | **Use as <shot>'s frame** on a result while the For chip is set (the tile's ✓, its right-click, the Inspector) | view | picking the frame is the point of *Make frame*; today it costs a trip to Story and back per shot (WF12) |
| I3 | *← Back to <shot>* ends the For context | rule | a context left on silently turns later work into takes of the wrong shot (WF13) |
| I4 | Re-run, Variations and New angle honour the For chip while it is set | fix | the chip promises "every image made here" (WF14) |

### Animate — justified changes only

| # | Change | Tag | Why it is needed |
| --- | --- | --- | --- |
| A1 | *Make the final shot…* carries the For shot and version; the assembly and the render record the take with the version | fix | WB1, WB2: the final shot never reaches its shot, and its *Lip-sync* pass can never find a line |
| A2 | *Make clip ▸ on the stage* opens Performance › *Stage clip* with the For chip, the shot's frame as the start | fix | it lands in Clay today, out of context (WF17) |
| A3 | In Clay › Camera, while the For chip names a shot: **Use this camera for <shot>** (and *New shot from this camera…* only without one) | view + the S11 route | today the only link makes a second shot (WF16) |
| A4 | **Use as <shot>'s clip** on a clip's row while the For chip is set; *Make a shot from this clip…* hidden then | view | the clip is chosen where it is played; a second shot is never wanted there (WF20) |

**Unchanged:** Image's column, Edit, the New angle sheet and Expand; Animate's three modes, their sections and cards, the Final editor,
the stepper. Two confusions stay for later because they are not on the round trip: what "shot" means inside Animate's Shot head (WF21)
and the stage-only stepper (WF22). The board (S9) shows the Story shot's state instead.
