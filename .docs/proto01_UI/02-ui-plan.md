# 02 · A more usable loom2: the UI plan

Status: **proposal, 2026-10-16. Not built and not yet decided.** It reorganises the UI the inventory in
[01](01-function-inventory.md) describes, following the author's direction of 2026-10-16 (§1). It changes the shape of the app, so it
needs a decision in [13](../proto01/13-decision-log-and-open-questions.md) before any work. That would be **D90**: §12 lists what D90
has to settle. It revises [03](../proto01/03-vision-scope-and-mvp.md) T3 ("suites, not stages"), [07](../proto01/07-ui-frame.md) §1–§2
(the top bar and the suite order), [17](../proto01/17-ui-suite-story.md) §2 (Story as one suite among seven) and
[proto01_design/01](../proto01_design/01-catalogue-inventory.md) (the Catalogue as a top-level suite).

Ids in brackets point at rows of 01: C48 is a Catalogue function, X4 a cross-suite concept, B2 a bug.

## 1. The author's direction (2026-10-16)

| # | Direction | What it changes |
| --- | --- | --- |
| R1 | **Story is the first menu and holds the highest level** (as in the original loom). | Story moves from sixth tab to first and becomes the home of the project. |
| R2 | **Styles are shown as images.** The style description is text that clogs the UI without informing (a loom feature). | Each style gets a sample image. Styles are picked from images, and their text is edited in one place only. |
| R3 | **In Generate, every preset is a small icon,** with no text descriptions. | Field presets, aspect, tier, styles, panel presets and angle moves all become icons. Words go to tooltips and accessible labels. |
| R4 | **Generate's left panel is one long scrolling panel, not split into tabs,** about 30 % wide and resizable by dragging. | The rail tabs Prompt / Model / Size & Batch / Presets / New angle become sections of one column. The Panel gets a drag handle. |
| R5 | **The Catalogue moves under Story, after Cast,** because it collects assets into logical groups. Those groups are used in Flow and wherever else it makes sense. | The Catalogue becomes a Story workspace. "Group" becomes the one collection idea of the whole app. |
| R6 | **Models moves into the ☰ menu.** | Models stops being a suite. |
| R7 | *"Is all the functionality coherent? We might have built several applications in one."* | Answered in §2; the rest of the plan acts on the answer. |

What the original loom shows (studied for this plan, `F:\source\repos\stubz-002-tripo-sf\loom\loom-loreweave-studio`):

- **Styles were visual.** loom kept one sample image per style, copied into `bible/styles/<id>.png` with the prompt and model that made
  it. Styles were edited on one page as a grid of 108 px tiles. Generation picked them from an image popover, with the fragment only in
  a tooltip, after the author's request of 2026-08-08: "would it be possible to select the style by only using the images?". loom v2
  later regressed to a name `<select>`. That is the mistake not to repeat.
- **Story came first in v2's layout.** loom v2 had World as the first top tab, while v1 (the one in daily use) put Assets first. In both,
  Story's power came from **inheritance**: its default style applied to every generation and its spine characters seeded assets.
- **Icon presets came from generated mannequins.** loom's pose cells were 256² renders of a neutral mannequin, picked as an on/off icon
  grid. Every other preset was a dropdown.
- **One column with the action pinned at the bottom.** loom v2's composer was a single scrolling column with Generate and *Preview* (a
  dry run showing the resolved prompt) pinned at the foot, 320 px wide and drag-resizable from 260 to 420.
- **What went wrong** ([02](../proto01/02-loom-retrospective.md)): Story's objects were *mandatory* structure, essential meaning lived in
  tooltips, and most of the planned Story level was never built. The real project used Story only for styles and poses. This plan keeps
  Story first but **not mandatory**: a project with no world, cast or shots still works, starting in its Catalogue.

## 2. Is loom2 one application or several? (R7)

**Short answer.** Underneath, loom2 is one application: one asset store, one job queue, one model registry, lineage on every file,
and origins on every job. On screen it is **nine applications sharing a window**. The fear is justified, but the cause is the
presentation more than the feature set.

| "Application" | What it resembles | Size today |
| --- | --- | --- |
| Catalogue | Lightroom-style library: albums, free pages, loupe, compare, lineage | 43 commands, ≈ 80 functions |
| Generate | a ComfyUI-style form for text-to-image | 5 rail tabs, ≈ 40 fields, 11 commands |
| Edit | a Photoshop clone with an AI panel | 79 commands, 14 tools, 4 Inspector tabs |
| Animate | an image-to-video generator with a frame-accurate player | 36 commands, 5 rail tabs |
| Stage | a 3D previz tool: blocking, posing, IK, cameras, keyframes, its own still and clip generation | 38 commands, 5 rail tabs, a second timeline |
| Story · World / Cast / Shots | a story bible, a casting and LoRA studio, a shot list | 69 commands across five tabs |
| Story · Flow | an articy-style branching-narrative editor with variables and conditions | 9 node types |
| Story · Episode | a single-lane editor with EDL, FCPXML and SRT export | a third transport |
| Models | a model downloader and engine console | no commands |

**Signs it reads as several applications** (all from [01](01-function-inventory.md)):

1. **The same job is built several times, each with its own controls.**
   - Making a still exists in six places (X1).
   - Reference images in four (X4).
   - Model pickers in five forms (X7).
   - Presets of six kinds (X8).
   - "How many and which seed" under three names (X6).
   - Four transports with different keys (X11).
2. **Words change meaning between neighbouring screens** (01 §11.5). "Stage" is a suite and a button; "Shot", "Preset", "Refine" and
   "Keep" each mean two or three things. Keys change meaning between suites (01 §11.7).
3. **There are three narrative structures and no stated relation between them.** The World *spine* (beats), the Flow *graph* (nodes,
   choices, variables) and the Episode *lane* (an ordered cut). A beat can become a Flow node; a shot can sit in a node and on the lane.
   Nothing says which one is the story.
4. **The makers don't know what they are making for.** Open Generate from a shot and the result lands in *Unprocessed*, not on the shot.
   Story can't make a shot's frame or clip itself (Y41). It can only send you to Stage or Animate, and nothing brings you back.
5. **Each suite has its own idea of a collection.** Catalogue groups, Cast reference sets (which *are* groups underneath), Animate's clip
   list, Episode's bins, Shots' takes, Edit's documents, Stage's results.

**Verdict.** The features mostly belong to one pipeline, *storyboard pre-production*:

> world and style → cast → shots (frame, then clip) → episode cut

But the UI presents them as peers, so every suite looks like a product of its own. The fix is **hierarchy, context and shared parts**,
not deletion:

- **Hierarchy.** Story is the *what*: the plan, the collections, the shots, the cut. The makers (Generate, Edit, Animate, Stage) are the
  *how*.
- **Context.** A maker opened for something knows what it is for, and its result goes back there (§5).
- **Shared parts.** One component and one word for each concept that recurs (§8).

**Features weakly tied to that pipeline.** These are the reason the app *feels* like several products. The author decides their fate
(§10); the plan only makes them recede:

- Flow's interactive-fiction machinery: variables, conditions, choices.
- Edit's deep retouching set: curves, levels, colour balance, magnetic lasso, quick mask, PSD layers.
- Stage's keyframe animation and its two clip pipelines, which overlap Animate.
- Generate's JSON prompt mode and Animate's keyframe beats.

## 3. The new structure

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ ☰  ▸ Harbour Tales ▾ │ STORY · Generate · Edit · Animate · Stage          ● engine  ● 2 queued │
├────┬──────────────────────┬────────────────────────────────────────────────┬──────────────────┤
│ 🌐 │ Panel (resizable)    │ Strip                                          │ Inspector        │
│ 👥 │                      ├────────────────────────────────────────────────┤ (resizable)      │
│ ▦  │                      │ Centre                                         │                  │
│ 🎬 │                      │                                                │                  │
│ ⑂  │                      │                                                │                  │
│ 🎞 │                      │                                                │                  │
│    ├──────────────────────┤                                                │                  │
│    │ Foot (primary)       │                                                │                  │
└────┴──────────────────────┴────────────────────────────────────────────────┴──────────────────┘
  Story rail: World · Cast · Catalogue · Shots · Flow · Episode
```

**Top bar** (07 §1 revised):

| Slot | Today | Planned |
| --- | --- | --- |
| Far left | Project ▾ | **☰** (app menu, moved from the far right): **Models & engine…** · Settings · Commands and keys · Palette · Focus · Dock · Theme · Density · Refresh · Quit (the spike harness only in dev builds) |
| Then | 7 suite tabs | **Project ▾** with the open project's name (New, Open, Close, Recent — kept where it was, built 2026-10-16), then **Story · Generate · Edit · Animate · Stage** |
| Keys | Ctrl+1 2 3 4 6 7 5 | **Ctrl+1–5 in tab order**, and Alt+1–6 for Story's workspaces |
| Right | 4 chips | the same chips. "engine" and "weights" open Models & engine on the right tab, filtered |

- **Story** (Ctrl+1) is the app's landing place and the project's home. A new project opens on World with one card row: *Add a style ·
  Cast from an image · Import images · Generate an image*.
- **The Catalogue** becomes Story's third workspace (R5). Every way into it still works: `?suite=catalogue` redirects for one release,
  and Alt+3 and a palette command open it directly.
- **Models** becomes a full-height sheet over the frame (R6). See §7.
- **The makers keep their own tabs.** They are where the work is done, and Edit, Animate and Stage keep their WebGL / WebGPU canvases
  alive (D69). They stop being *destinations*: every Story object has a **Make ▸** button that opens the right maker in context (§5).

### 3.1 Panels the user can resize (R4, all suites)

- The Panel and the Inspector get a drag handle on their inner edge. A double-click on the handle restores the suite's default width.
- Widths are stored per suite. `ui.panelWidth` and `ui.inspectorWidth` already exist in the session store; they become per-suite and
  gain a setter.
- Default Panel width: **Generate 30 % of the window** (min 300 px, max 45 %); the other suites 320 px. The Inspector defaults to 340 px.
- The Panel still collapses from its rail button and Ctrl+B.

## 4. Story and its workspaces

| Workspace | Keeps from today | Changes |
| --- | --- | --- |
| **World** | logline, synopsis, spine | **Styles become an image grid** (§4.1). The spine gets a stated job: *the outline the shots hang off*. Variables move to Flow, the only place they are used. |
| **Cast** | profiles, versions, Expand, curate, lock, LoRA training, voices | Gains every LoRA verb that Models' Trained table duplicates (X14). The hero and the Expand cells use icon grids like loom's pose cells (§6.3). |
| **Catalogue** | everything in 01 §3 | It is "the album of the story": Places shows the **groups** first (Album), then Unprocessed, Library and Trash. Group cards gain a *used by* line (a profile, a style, a shot, a node). See §4.2. |
| **Shots** | versions, takes, finalize, lip-sync | Gains **Make frame ▸** (Generate · Stage) and **Make clip ▸** (Animate · Stage) on the shot board. Results come back as takes (§5). |
| **Flow** | graph, play, validate, shot binding | Nodes can carry a **group** (§4.2). Edges can be deleted (B3). Keys work on the canvas (B2). Variables live here. |
| **Episode** | lane, preview, exports | Drop on the lane (B7). Episode / sequence named once (§8). The bins read from Shots and the Catalogue, not from Animate's store. |

### 4.1 Styles as images (R2)

- **Each style has a sample image.** It uses the existing `StoryStyle.group_id` (in the schema today, "a reference album, a later
  slice"). The style's group holds its samples, and the group's cover is the style's face.
- **Make sample** renders the style with a fixed preview prompt (a person, a place and an object in one frame) as one queued Draft job.
  It uses an open-licence model (Klein 4B or Z-Image), so both variants can make it. The user can also drop any image on a style tile to
  make it a sample or the cover.
- **World › Styles is the only place a style is written.**
  - It is a grid of tiles: sample, name, ★ for the project default.
  - Click a tile and the Inspector shows its editor. The fragment and negative textareas sit there, folded under the sample.
- **Everywhere else a style is only picked**: Generate's Style section, Cast's Expand, Stage's Shot.
  - The picker is a strip of 48 px sample tiles with ★ marking the default.
  - The name and fragment appear only as the tooltip and the accessible label.
  - A "none" tile turns the style off.
- **Every result records the style id it ran under.** That is already true through the recipe. Once styles have faces, the Catalogue's
  Inspector can show the style's face beside the prompt.

### 4.2 Groups as the one collection (R5)

Today a group is a Catalogue album, and a Cast reference set is secretly one. The plan makes the group the **only** collection in the
app and gives it a role wherever a set of images matters:

| Where | A group is used as |
| --- | --- |
| Cast | a profile version's reference set and its candidates (as today) |
| World › Styles | a style's samples; its cover is the style's face |
| Shots | a shot version's **takes**. Today takes are a list on the version; they become a group, so they can be compared and judged with the Catalogue's tools. |
| Flow | a node's **board**: references, mood, location photos. Drop a group card from the Places tree onto a node; the node card shows its cover. A Dialogue or Shot node's board seeds *Make frame ▸* with references. |
| Generate | references: drop a group, or **@mention** it (works today, D73). The Reference section shows the group as one cover tile with a count. |
| Episode | a sequence's bin can be "everything in group X" |

On the screen this needs only two new things:

- a **group chip** (cover, name, count), used everywhere a group is referenced;
- the **used by** line on a group in the Catalogue.

## 5. Makers in context: "Make ▸" and "For: …"

- Every Story object offers **Make ▸**: a shot (frame, clip), a profile (Expand, more candidates), a style (sample), a Flow node (frame for
  its shot).
- **Make** opens the maker with a **For** chip at the top of its Panel, e.g. "For: Shot 12 · v3 ✕". The maker is pre-filled from the
  object: the prompt stub, the board's references, the World's style, the project format.
- **While the For chip is set, the results also go to the object**: a shot's takes, a profile's candidates, a style's samples. They
  still appear in the Catalogue as today. A **← Back to Shot 12** button sits beside the chip, and the Dock's "Go to origin" uses the
  same link.
- **Opened from its tab, a maker has no For chip** and behaves exactly as today. This keeps Story *not mandatory*, as the retrospective
  asked.

Context is the single change that does most to make the makers feel like parts of one application. The plumbing already exists: job
origins (D66), shot versions with frames and takes, profile versions with candidate groups. What is missing is the chip and the routing.

## 6. Generate as one panel (R3, R4)

### 6.1 The single column

```
┌ Panel · Generate ───────────────────────────── ⇔ ┐   sticky jump bar: icons for each section, highlighted as you scroll
│ [✎][▣][🎨][☀][📷][👤][⚙][▭]                     │
│ For: Shot 12 · v3  ✕   ← back                    │   only with context (§5)
│ PROMPT          Tree ▪ Text ▪ JSON   42 words    │
│  scene ___________________________________ @     │
│ REFERENCES      [▣][▣][▣][+]  [Mara ▦ 27]        │   groups as one tile with a count
│ STYLE           [▣][▣][▣★][▣][▣][⊘]              │   sample tiles, no text (§4.1)
│ LOOK            lighting [☀][☁][🕯][🌙][⧉]…      │   icon grids (§6.3)
│                 mood [◐][◑]…   palette [■■■ +]   │
│ CAMERA          angle [icons]  distance [icons]  │
│                 lens [24][35][50][85]  dof […]   │
│ SUBJECTS ▸      (folded; + subject)              │
│ MODEL           [FLUX dev][Klein 9B][Krea]…      │   compact cards: icon + short name
│ SAMPLING ▸      (folded: steps, guidance, …)     │
│ LORAS ▸         (folded unless a slot is used)   │
│ SIZE            [▭16:9][□][▯]  [S][M][L]  ×4     │   aspect and tier as shapes; count as a stepper
│ ADVANCED ▸      (folded)                         │
├──────────────────────────────────────────────────┤
│ Generate 4 ▶     Queue     Preview     ≈ 1 min   │   pinned foot
└──────────────────────────────────────────────────┘
```

- **Section order follows the work:** what (prompt, references), how it looks (style, look, camera), with what (model, sampling,
  LoRAs), how big and how many, everything else.
- **Fields hide when the model can't use them,** instead of being disabled or ignored. This also fixes B12: the negative prompt shows in
  every mode or in none; the tier size is re-applied on a model change; shift is hidden where it breaks.
- **Preview** shows the resolved prompt (style fragment and LoRA triggers included) and the estimate. Today that is the "Serialisation
  preview" section.
- **Text, Tree and JSON stay**, as a small switch inside the Prompt section. JSON becomes a fold-out "edit as JSON" for those who want
  it (§10).
- **New angle leaves Generate** (01 G33–G35). It is an operation *on an image*, so it joins the image's actions (§9) with its own small
  sheet: source, move icons, count, ▶. The single panel then has one Generate button and no second Foot.
- **Saved panels** (today's Presets tab) become a row of tiles at the top of the column, each showing the thumbnail of its last output.
  ⊕ saves the current panel, and a tile's ⋯ menu renames or deletes it.

### 6.2 Fixes carried with it

- **B4:** Ctrl+Enter respects the disabled reasons.
- **B12:** see §6.1.
- **The model's reference limit is enforced at the slots**, and models with no references hide the section.
- **"Stage" (the button) becomes "Queue"** (§8).

### 6.3 Icons instead of words (R3)

There are three sources, all local, all re-makeable:

| Kind | Used for | How the icon is made |
| --- | --- | --- |
| **Schematic glyphs** (SVG, shipped) | aspect, tier, camera distance / shot size, lens, depth of field, composition, subject position, angle moves | drawn once: a frame with a figure at the shot size, a lens's field of view as a wedge, thirds lines, … |
| **Mannequin renders** (made locally) | pose, camera angle, shot size in Cast's Expand cells | rendered by the **Stage suite's own three.js mannequin** with clay shading, as loom made its pose cells but with no GPU job: Stage already has the figures, poses and cameras (S5, S19) |
| **Sample swatches** (generated locally, once) | lighting, mood, background, style, the user's own presets | a **preset icon pack**: one staged Draft job per preset on an open-licence model, stored in app state (not the project), re-made per item from its ⋯ menu. A user preset gets its swatch when it is saved. |

**The rules for every icon:**

- 40–48 px tiles, wrapping.
- The **word** lives in the tooltip and the `aria-label`.
- The selected state is an accent border, as loom's cells had.
- Multi-select where the field appends: lighting, mood and composition. Single-select where it replaces: lens, distance, depth of field.
- A *text* toggle in the section header shows the words under the icons for anyone who wants them. It is off by default.

Icons are not only for Generate. The same component replaces:

- Animate's motion chips;
- the Angle move pad;
- Stage's pose presets;
- Expand's coverage cells;
- Edit's brush presets.

## 7. Models & engine in ☰ (R6)

- **A sheet over the frame,** not a suite. Its tabs:
  - **Roster:** the table, filters and Fetch.
  - **Engine:** status and Start / Stop / Restart / Free VRAM.
  - **Disk:** unlisted files and *delete weights*. Both are missing today (M3, M7).
- **Every Fetch button opens it filtered to the missing models,** with *Fetch all missing*: Generate's Foot, Animate, the Angle sheet,
  Stage's Shot, the weights chip and the banner. The engine chip opens the Engine tab.
- **Trained LoRAs leave Models** and live only in Story › Cast (X14).
- **Every action in the sheet becomes a command** (M1 in 01 §8), so it reaches ⌘K and the keyboard map.

## 8. One word, one component

### 8.1 Vocabulary (01 §11.5)

| Today | Planned | Why |
| --- | --- | --- |
| "Stage" (the button) | **Queue** | frees "Stage" for the 3D suite |
| Stage suite › "Shot" tab, "Generate the shot" | **Render**, "Render frame" | a *shot* is a Story shot |
| Stage › "Animate ▶" | **Render clip** | not the Animate suite |
| Cast "Lock" / Shots "Finalize" | **Final** (one verb, one badge) | the same sign-off |
| Episode / sequence | **Episode** for the workspace, **cut** for one sequence | |
| count / candidates / clips | **Count** | |
| presets (six kinds) | **Saved panels** (whole-panel memories) and **presets** (icon values) | |
| "Release" ×3 | **Run now** (a staged job) · **Unbind** (a shot from a node) | |
| Keep (×3 meanings) | **Keep / Reject** judge an asset everywhere; Cast's keep becomes **Add to the reference set**; Edit's becomes **Use candidate** | |
| Refine edge / Refine / tiled refine | **Refine edge** · **Refine** · **Upscale (detailed)** | |
| "Remove background…" (it only selects) | **Select subject…** | it does what it says |
| Compare preview with exact flatten (Edit) | moved to a developer menu | developer-facing (01 §11.6) |

### 8.2 Shared components

Each component replaces several builds listed in 01 §10:

| Component | Replaces |
| --- | --- |
| **ModelPicker** (compact cards; health; the For chip's default) | Generate cards, Animate cards, Edit AI selects, the Angle method select, Stage method cards (X7) |
| **CountSeed** (count stepper + seed random / fixed / step) | X6 |
| **PresetIcons** (§6.3) | field presets, motion chips, move pad, pose presets, brush presets |
| **ReferenceTray** (slots + groups, the model's limit, notes) | Generate slots, Stage Shot deck, Animate start / end (X4) |
| **RunBar** (Run ▶ · Queue · Preview · estimate · reason) | every Foot, and Edit's AI buttons |
| **Transport** (one key set: Space, ← →, Shift+← →, I / O, Home / End, J / K / L) | Animate, Stage, Episode, Flow play (X11) |
| **Judge** (Keep, Reject, Clear, stars) | X9 |
| **Open in ▸** (one menu of the other suites for any asset) | the per-suite send verbs (X17) |
| **GroupChip** | §4.2 |

### 8.3 Commands and keys

- **Every action is a command.** That includes Edit's AI runs, Generate's fields and Models' actions (01 §11.2).
- **The dev audit checks declared placements** against what is rendered, and covers every scope (01 §11.3).
- **Settings › Keyboard and the commandAudit test include Stage and Story** (01 §11.7).
- **One key, one meaning across the app** wherever 01 §11.7 shows a clash. The transport keys come from the shared Transport.

## 9. The makers, briefly

| Maker | Changes |
| --- | --- |
| **Generate** | §6. Its results view becomes the Catalogue's current grid and strip, scoped to "this batch / session / all", instead of the old copy (X18, B13). |
| **Edit** | **AI runs become commands** and appear in the canvas menu beside the selection: *Inpaint selection…, Refine…, Select subject*. The AI tab stays. **New angle** joins Refine, Upscale and Outpaint in the AI tab as "Angle". The deep retouching set (curves, levels, colour balance, magnetic lasso, quick mask) moves under the Toolbox's *More tools* and Add adjustment ▾, so the first screen shows the storyboard essentials: move, select, AI select, brush, eraser, fill, crop, AI. Fix B9 (Crop has no gesture) and B18. |
| **Animate** | The **Clips** tab becomes a Catalogue view (type: clip, with delete and filters) shared with Episode's bin (X12). Extend and Lip-sync live together under one **Experimental** fold in the clip Inspector (X3). Lip-sync stays reachable from the shot, through Make clip ▸. |
| **Stage** | The vocabulary of §8.1. Fix B1 (keys while typing). Keyframes and the two clip pipelines stay, under the Render tab's *Clip* fold. |

## 10. Feature triage (the author decides)

What should be visible on the first screen of each workspace, and what should recede. "Recede" means folded, in More, or behind an
Advanced fold; nothing is removed by this plan.

| Feature | Serves the storyboard pipeline? | Recommendation |
| --- | --- | --- |
| World styles, logline, spine | yes: inherited by everything | **front**: World is the landing page |
| Cast: Expand, curate, lock, LoRA | yes: character consistency | **front** |
| Voices (Kokoro, Qwen3 cloning) | partly: needed for lip-sync and audio lanes | recede into Cast's Inspector fold (as now) |
| Catalogue albums, pages, compare, lineage | yes | **front**, as Story › Catalogue |
| Shots with versions and takes | yes: the unit of the storyboard | **front**, gaining Make ▸ |
| Flow graph | partly: a branching story is a game / interactive need, not a storyboard need | **ask** (§12 Q3): keep it front for branching projects, or recede behind a project option "branching story" |
| Flow variables / conditions / choices | interactive fiction only | recede with the graph |
| Episode lane and exports | yes: the deliverable | **front** |
| Generate: Tree prompt, references, styles, models | yes | **front** (§6) |
| Generate: JSON mode | power use | recede to "edit as JSON" |
| Edit: AI select, inpaint, refine, upscale, outpaint, new angle | yes: fixing frames | **front** |
| Edit: curves, levels, colour balance, magnetic lasso, quick mask, filters, PSD | photo retouching beyond storyboarding | recede to *More tools* |
| Animate: model, prompt, start / end, player, extract | yes | **front** |
| Animate: beats, compare, onion, J / K / L shuttle | power use | recede |
| Stage: blocking, cameras, poses, Render frame | yes: previz is pre-production | **front** |
| Stage: keyframes, Render clip (IC-LoRA, Wan Animate) | overlaps Animate | recede under the Render tab's *Clip* fold; **ask** (§12 Q5) whether clips should be made only in Animate |
| Experimental: Extend, Lip-sync | yes, but immature (D88) | one Experimental fold |
| Models & engine | infrastructure | ☰ (§7) |

## 11. Delivery waves

Each wave ends with the offline suite, Vitest, the smoke scenarios under `full` and `open`, the headed tour, and a journal entry. The
waves are ordered so the app is usable after every one.

| Wave | Content | Size |
| --- | --- | --- |
| **UI0: bugs first** | B1–B19 from 01 §11.1. B1 (Stage Delete while typing) and B2 (Story keys across tabs) can lose work today. | small |
| **UI1: frame** | ☰ on the left with Project and Models; tab order Story · Generate · Edit · Animate · Stage with Ctrl+1–5; the Catalogue as Story's third workspace (the registry delegates that rail tab's Panel, Strip, Centre and Inspector to the Catalogue's parts, wide strip included); Models & engine as a sheet with filtered Fetch links; resizable Panel and Inspector per suite; `?suite=catalogue` and `?suite=models` redirects; the smoke scenarios updated for the new tab order. | medium |
| **UI2: Generate as one column** | §6.1–§6.2 with the existing controls; New angle moves to the image actions; saved-panel tiles. | medium |
| **UI3: icons and visual styles** | §4.1 (style samples, the style grid and pickers) and §6.3 (glyph set, mannequin renders from Stage, the preset icon pack). Measure the icon pack's one-time cost on the rig. | medium (+ a rig run) |
| **UI4: context** | §5 (Make ▸, the For chip, results routed to takes / candidates / samples, Back) and §4.2 (groups on Flow nodes, takes as a group, used-by). | medium |
| **UI5: one word, one component** | §8: the renamings, the shared components, every action a command, the audit and key work. | large: it touches every suite |
| **UI6: the makers** | §9 and whatever the author decides in §10. | medium |

## 12. What D90 has to decide

1. **Accept the structure** (§3): Story first and the project's home, the Catalogue as Story's third workspace, Models in ☰, the makers
   as tabs opened in context. This reverses 03 T3 and 02's "Story only as an optional layer". The plan keeps Story *not mandatory*
   (§5): a project with no story works from its Catalogue.
2. **The landing workspace.** World (as planned) or Catalogue? Today's habit is the Catalogue. A project with no world yet could open on
   the Catalogue automatically.
3. **Flow.** A front workspace for every project, or shown only for projects marked as branching (§10)?
4. **New angle.** In Edit's AI tab as "Angle" (§9), or as a sheet on any image (§6.1)? The plan proposes both routes on one component.
5. **Clips.** Should Stage keep its own clip rendering (IC-LoRA, Wan Animate), or should every clip be made in Animate, with Stage
   handing over its passes (§10)?
6. **Edit's depth.** Is it acceptable that the retouching set recedes behind *More tools* (§9)?
7. **Icons.** Text off by default, with the *text* toggle per section (§6.3)? And may the preset icon pack be generated on first use,
   staged, at roughly one Draft job per preset? Its count and time to be measured in UI3.
