# 01 · Function inventory: every function and where it lives in the UI

Status: **inventory, 2026-10-16**. Read from the code at `bfd1988` (D89 built). Nothing is redesigned here: this document records what
exists and where it sits today, so that the reorganisation that follows can give each function one deliberate home. It extends to the
whole app what [proto01_design/01](../proto01_design/01-catalogue-inventory.md) did for the Catalogue on 2026-10-07. That earlier
document also describes a newer Catalogue than the one Generate still embeds (§4.4).

**D122 (2026-10-23):** C29 Keep / Reject, the ratings and the Inspector's Judge listed below are gone.

Sources: `frontend/src/frame/` (TopBar, Rail, Panel, Dock, Settings, Help, palette, drag rules, `openWith`, `origin`) and every suite under
`frontend/src/suites/`: their `*Commands.ts`, panels, strips, centre views, inspectors and context menus. Specs for intent:
[07](../proto01/07-ui-frame.md), [08](../proto01/08-ui-suite-catalogue.md)–[11](../proto01/11-ui-suite-animate.md),
[16](../proto01/16-ui-suite-stage.md), [17](../proto01/17-ui-suite-story.md).

## 0. How to read this

**Frame regions.** The frame names its centre region "Stage", which is also the name of a suite. To keep them apart, this document calls
the centre region the **Centre** and keeps "Stage" for the 3D suite.

| Region | Where | What it holds |
| --- | --- | --- |
| **TopBar** | top | Project menu, the seven suite tabs, the status chips, the ☰ app menu |
| **Rail** | far left | the suite's tabs (icons), then the global toggles: focus, panel, inspector, dock, settings |
| **Panel** | left | the content of the active rail tab |
| **Foot** | bottom of the Panel | the suite's primary action (`PrimaryAction`), the same on every rail tab of that suite |
| **Strip** | toolbar above the Centre | spans the full width in the Catalogue (`wideStrip`) |
| **Centre** | middle | the suite's main view |
| **Inspector** | right | details and verbs for the selection |
| **Dock** | bottom | the job queue |
| **ctx** | — | a right-click menu, also opened by Shift+F10 or the Menu key on the focused item |
| **⌘K** | — | the Ctrl+K command palette: every registered command of the current suite plus the global ones |

**Columns.** Each inventory table has these columns:

- **#**: a stable id for the reorganisation to refer to. The prefix names the area: F frame · C Catalogue · G Generate · E Edit ·
  A Animate · S Stage · Y Story · M Models.
- **Homes today**: every mouse route to the function. ⌘K and keys are not counted as homes.
- **n**: the number of those homes. **0** means the function is reachable only by key or palette, which breaks D32.
- **Command · key**: the registered command id (prefix only, e.g. `cat.keep`) and its default key. "—" means the control calls the store
  directly, so the function is **not** in ⌘K, Help or Settings › Keyboard.
- **⚠** marks a row with a problem; the problems are collected in §11.

**Scale today.** There are 302 registered commands (global 22 · Catalogue 43 · Generate 11 · Edit 79 · Animate 36 · Stage 38 · Story 69 ·
Models 4, plus suite-built ones such as Edit's per-tool and per-layer-type commands). At a rough count, around **150 further functions have
no command at all**: AI runs, model pickers, field editors, Models' buttons, drags. Seven suites have 27 rail tabs between them.

## 1. The app at a glance

| Suite | Tab (key) | Rail tabs | Foot (primary action) | Strip | Centre | Inspector |
| --- | --- | --- | --- | --- | --- | --- |
| Catalogue | 1st (Ctrl+1) | Places | — | place · query · sort · selection · compare tray · split · import · zoom (wide) | grid / group page / loupe / compare / lineage / split panes | One · Many · Group card · several cards · nothing |
| Generate | 2nd (Ctrl+2) | Prompt · Model · Size & Batch · Presets · New angle | Generate N ▶ · Stage · Fetch (Angle tab: New angle ▶) | "show" + the **old** Catalogue strip | live job cards + the Catalogue grid | the Catalogue Inspector |
| Edit | 3rd (Ctrl+3) | Tool options · Brushes · Selection · AI · Documents | Save · to Catalogue · PNG · PSD · Close | doc · transform bar · latches · undo · zoom · grid · before · quick mask · renderer | Pixi canvas + candidate strip | layers · properties · history · info |
| Animate | 4th (Ctrl+4) | Inputs · Model · Length & Size · Presets · Clips | Animate ▶ · Stage | view · frame counter · speed · loop · onion | player / filmstrip / compare + transport + timeline + job cards | clip · frames · lineage |
| Stage | 5th (**Ctrl+6**) | Library · Outliner · Cameras · Poses · Shot | New stage / Generate ▶ (Shot) / save state | view · guides · frame all · **timeline row** | three.js viewport + gizmo bar | object / camera / stage |
| Story | 6th (**Ctrl+7**) | World · Cast · Shots · Flow · Episode | per tab: save state · Expand ▶ · New shot · Play ▶ · Export ▶ | per tab | per tab: editor / version page / shot board / node graph / lane | per tab |
| Models | 7th (**Ctrl+5**) | Roster · Engine | — | roster counts · Rescan | roster table + trained LoRAs | the selected model entry |

## 2. Frame and global functions (F)

Files: `TopBar.tsx`, `Rail.tsx`, `globalCommands.ts`, `Dock.tsx`, `SettingsModal.tsx`, `KeyboardSettings.tsx`, `HelpOverlay.tsx`,
`CommandPalette.tsx`, `ProjectDialog.tsx`, `Banner.tsx`, `About.tsx`, `dropRules.ts`, `openWith.ts`, `store/origin.ts`.

### 2.1 Screen map

| Region | Contents |
| --- | --- |
| TopBar, left | **Project ▾** (folder icon, open project name) │ the suite tabs in the order Catalogue, Generate, Edit, Animate, Stage, Story, Models. The Edit, Generate and Animate tabs are drop targets, and holding a drag over a tab for 600 ms switches to that suite. |
| TopBar, right | chips: **engine** (state, VRAM free; click → Models) · **jobs** "N running · N queued" (click → toggle Dock) · **disk** free (no action) · **weights** "N missing / ok" (click → Models) · **☰** app menu |
| Project menu | New project… · Open project… · Close ‹name› · Recent (list) |
| ☰ app menu | Settings… · Commands and keys · Command palette · Focus mode · Show/Hide dock · Theme: ‹x› · Density: ‹x› │ Refresh state · **M0 spike harness** │ Quit (graceful) │ version · variant · ws status |
| Rail, bottom | Focus mode · Toggle panel · Toggle inspector · Toggle dock · Settings |
| Banner | one message at a time (+N), an optional action button (e.g. "Open Models"), dismiss |
| Dock line | running job + progress, or Idle / Queue paused / No project · "Queued N · Recent N" · pause/resume queue |
| Dock open | three columns: Active (live preview + row) · Queued · Recent (12). Each row: go to origin, cancel or remove; right-click → Go to origin │ Cancel job · Run now (release staged) · Remove from the list │ Copy job id · Copy recipe JSON |
| Settings modal | Weights (models root, mounted trees, HF_HOME) · Engine (VRAM budget, port, flags, restart every N jobs, health and stall timeouts, reserve VRAM) · App (theme, density, keep Edit/Animate loaded) · Catalogue (thumbnail fit/fill, tile caption) · Engine output (thumbnail sizes, log level) · **Keyboard** (search, record a key, clear, reset one, reset all) · Licences (MiniMax H3 confirmation) · About (versions, paths with Reveal, Copy diagnostics) │ Cancel · Save |
| Help overlay (`?`) | the current suite's commands and keys · global commands · fixed keys · gestures (Catalogue, Generate and Edit only) |
| Palette (Ctrl+K) | type to filter the suite + global commands; Enter runs the selected one |
| Project dialog | folder (+ Browse in Tauri) · name (new) · format note (16:9 · 1920×1080 @ 24 fps · Draft) · Create / Open |
| Toasts | bottom; some carry an Undo or Play action |

### 2.2 Inventory

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| F1 | New project | Project menu; Catalogue empty state (no project) | 2 | `global.project.new` | dialog |
| F2 | Open project | Project menu; Catalogue empty-state card | 2 | `global.project.open` | |
| F3 | Open a recent project | Project menu › Recent | 1 | — | |
| F4 | Close project | Project menu | 1 | — | |
| F5 | Switch suite | TopBar tabs | 1 | `global.suite.*` · Ctrl+1…7 | ⚠ tab order 1 2 3 4 **6 7 5**. Edit takes over Ctrl+1/Ctrl+2 as zoom while a document is open; the Catalogue loupe takes Ctrl+1 as 1:1 |
| F6 | Quick drop on a suite tab | drag tiles onto the Edit (open the first image), Generate (add references) or Animate (start / end frame, or play a clip) tab | 1 | — | gesture only; the tooltip explains it |
| F7 | Spring-load a suite | hold a drag on a tab for 600 ms | 1 | — | gesture only |
| F8 | Engine status → Models | TopBar engine chip | 1 | — | ⚠ opens Models on whichever tab was last open, not on Engine |
| F9 | Toggle the Dock | TopBar jobs chip; ☰ menu; Rail; Dock line click | 4 | `global.dock` · \` | |
| F10 | Weights status → Models | TopBar weights chip; banner "Open Models" | 2 | — | does not filter to the missing models |
| F11 | Disk free | TopBar disk chip | — | — | display only |
| F12 | Settings | ☰ menu; Rail | 2 | `global.settings` · Ctrl+, | |
| F13 | Commands and keys (Help) | ☰ menu | 1 | `global.help` · ? | |
| F14 | Command palette | ☰ menu | 1 | `global.palette` · Ctrl+K | |
| F15 | Focus mode (hide Panel and Inspector) | ☰ menu; Rail | 2 | `global.focus` · Tab | Tab also swaps the Compare view in the Catalogue |
| F16 | Toggle Panel / Inspector | Rail (each); clicking the active rail tab toggles the Panel | 2 / 1 | `global.panel` · Ctrl+B / `global.inspector` · Ctrl+I | |
| F17 | Theme | ☰ menu (toggles light/dark); Settings › App (full list) | 2 | — | |
| F18 | Density | ☰ menu; Settings › App | 2 | `global.density` | |
| F19 | Refresh state | ☰ menu | 1 | `global.refresh` | |
| F20 | M0 spike harness | ☰ menu | 1 | — | ⚠ developer leftover in a user menu |
| F21 | Quit (graceful) | ☰ menu | 1 | — | |
| F22 | Context menu of the focused item | (key) | 0 | `global.contextMenu` · Shift+F10 / Menu | ⚠ in the Catalogue grid it opens the empty-grid menu, because tiles never take focus |
| F23 | Quick actions: Generate an image · New document · Animate from an image | empty-state cards (Catalogue, Animate) | 1 each | `global.start.*` | ⚠ "Animate from an image" only switches to the Catalogue and shows a toast |
| F24 | Job: go to origin | Dock row icon; Dock row ctx | 2 | — | ⚠ Story jobs other than Expand only switch to Story |
| F25 | Job: cancel / remove / release staged | Dock row icons; Dock row ctx; Generate's job cards | 2–3 | — | release ("Run now") is in the ctx only |
| F26 | Job: copy id / recipe JSON | Dock row ctx | 1 | — | |
| F27 | Pause / resume the queue | Dock line | 1 | — | |
| F28 | Engine settings (budget, port, flags, restart, timeouts, reserve) | Settings › Engine | 1 | — | |
| F29 | Weight locations (models root, mounted trees, HF_HOME) | Settings › Weights | 1 | — | |
| F30 | Keep Edit / Animate loaded N min | Settings › App | 1 | — | |
| F31 | Catalogue thumbnail fit / caption | Settings › Catalogue | 1 | — | the only Catalogue options outside the suite |
| F32 | Thumbnail sizes, log level | Settings › Engine output | 1 | — | |
| F33 | Remap keys | Settings › Keyboard | 1 | — | ⚠ lists Global, Catalogue, Generate, Edit, Animate and Models; **Stage and Story are missing** |
| F34 | H3 licence confirmation | Settings › Licences | 1 | — | unlocks nothing yet: the H3 card in Animate stays disabled |
| F35 | About: versions, reveal folders, copy diagnostics | Settings › About | 1 | — | |
| F36 | Dismiss a banner / run its action | Banner | 1 | — | |
| F37 | Deep links `?suite=&tab=`, `?tool=&ai=&sel=&asset=` | URL | — | — | developer and checks only |

## 3. Catalogue (C)

Files (in `suites/catalogue/`): `CatalogueSuite.tsx` (CS), `CatalogueStrip.tsx` (CSt), `Places.tsx`, `Panes.tsx`, `PageView.tsx` (PV), `Loupe.tsx`,
`LineageView.tsx`, `Inspector.tsx` (Insp), `Tile.tsx`, `catalogueCommands.ts` (cc).

### 3.1 Screen map

| Region | State | Contents |
| --- | --- | --- |
| Rail | — | one tab: **Places** |
| Panel | — | Unprocessed (n) · Library (n) · **Album** + New group icon · the group tree (chevrons, counts) · Trash (n) |
| Foot | — | none |
| Strip (wide) | grid or page | **Place** (name, or breadcrumbs on a page, plus Empty trash in Trash) │ **Query** (search, filter chips, + Filter, clear, count) │ **Sort** (disabled on a page) │ "N selected ✕" │ **Compare tray** (≤ 4 thumbnails, Compare, ✕) │ **Split ▾** │ **Import** + ▾ │ **Zoom**: tile size on the grid, page zoom + Fit on a page |
| Strip | loupe / compare / lineage | collapses to "← Back" + Place |
| Centre | Unprocessed / Library / Trash | virtualised tile grid; optional group headers; empty state with quick cards; OS file drop imports |
| Centre | group page | free canvas: photos and group cards placed by hand, marquee, resize handle |
| Centre | loupe | image with zoom and pan · facts bar (‹ n/N ›, model, size, seed, date, state, zoom, Fit, 1:1, Close) · **hub** toolbar (Keep, Reject, [Clear], [Rate ▾], Edit, Reference, New angle, Animate ▾, [Re-run, Variations, Duplicate], [Move to group ▾], [Lineage, Reveal], [Pin], More ▾). The bracketed items hide below 760 px. |
| Centre | compare | 2-up / 4-up, zoom locked · wipe, difference, 2/4, Swap, zoom, Fit, 1:1, Back, Unpin all |
| Centre | lineage | a tree of cards with edge labels |
| Centre | split | two panes, stacked or side by side; each has a header with a ⋯ menu and a divider |
| Inspector | one asset | thumbnail · audio player · meta · **Judge** (Keep / Reject / ○, stars) · **Tags** · **Location** (breadcrumbs, Move to, Back to Unprocessed, Duplicate) · **Actions** (Edit, Animate ▾, Reference, Re-run, Variations, Load in Generate, Pin, More ▾) · **Start from this image** (9 cards) · **Lineage** path + Open tree · Prompt (folded) · Details (folded) |
| Inspector | several | thumbnail stack, Judge, shared tags, Location (Group these, Move to, Duplicate), Actions (Reference, Open in loupe, Trash / Restore / Delete, Clear selection) |
| Inspector | group card | cover fan, name, counts, Location, Open, Open in other pane, Ungroup, Duplicate, Delete group |
| ctx | tile (grid, page photo, loupe, lineage card) | Open in loupe, Open in Edit │ Move to group ▸, Back to Unprocessed, Duplicate, Show this batch, Show lineage │ Keep, Reject, Clear, Rate ▸, Tag… │ Use as reference, Re-run, Variations, Animate (start), Use as end frame │ **Start from this image ▸** (Remove background, Upscale, New angle, 3D prop, Animate (start), Variations │ Character, Place, Prop, Shot from clip) │ Pin, Open compare │ Reveal │ Trash, or Restore / Delete / Empty in Trash |
| ctx | empty grid | Import… │ Select all, Clear selection │ [Group by ▸, Expand all, Collapse all: only when already grouped] │ Search, Unpin all |
| ctx | group header | Collapse / Expand, Expand all, Collapse all │ Group by ▸ |
| ctx | page: photo / card / empty canvas | photo: the tile menu + Bring to front, Send to back, Group these…, Use as cover · card: Open, Open in other pane │ Rename, Duplicate, Ungroup │ front / back │ Delete group · canvas: New group here…, Select all, Fit │ Undo, Redo |
| ctx | Places rows | Unprocessed / Library: Open, Open in other pane · Album: New group… · group: Open, Open in other pane, New group inside… │ Rename, Duplicate, Ungroup │ Delete group · Trash: Empty trash… |

### 3.2 Inventory

**Places and navigation**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C1 | Open Unprocessed | Places row; row ctx; pane ⋯; Inspector "Unprocessed" link; page-error button | 5 | — | the default place |
| C2 | Open Library | Places row; row ctx; pane ⋯ | 3 | — | |
| C3 | Open Trash | Places row | 1 | — | ⚠ no ctx "Open" and no pane-menu entry, unlike the other places |
| C4 | Open the Album root page | Album heading; strip breadcrumb; Inspector breadcrumb | 3 | — | |
| C5 | Open a group page | Places row; row ctx; card double-click; card ctx; Inspector card "Open"; Inspector and strip breadcrumbs | 8+ | — · Enter on a card | |
| C6 | Open in the other pane | Places ctx (3 kinds); card ctx; Inspector card | 5 | — | splits the Centre first |
| C7 | Expand / collapse the group tree | Places chevrons | 1 | — | |
| C8 | Show this batch (filter) | tile ctx | 1 | `cat.showBatch` | ctx only |
| C9 | Back from loupe / compare / lineage | strip "← Back"; loupe "Close"; compare "Back" | 3 | `cat.closeLoupe` · Esc | ⚠ three labels; no Back button in **Generate**'s lineage view |
| C10 | Split: single / stacked / side by side | Strip Split ▾ | 1 | — | |
| C11 | Swap panes | Split ▾; pane ⋯ | 2 | — | |
| C12 | Close a pane | pane ⋯; Split ▾ › Single | 2 | — | |
| C13 | Resize panes | divider drag | 1 | — | gesture only |
| C14 | Drop onto a pane (to Unprocessed / to Trash) | pane drag target | 1 | — | gesture only |

**Search, filter, sort, display**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C15 | Search | Strip field; grid ctx › Search (focuses the field) | 2 | `cat.search` · F | |
| C16 | Add a filter: State, Type, Source, Model, Rating, Date, Tags, More (Aspect, Derivations) | Strip "+ Filter" | 1 | — | ⚠ Batch and Lineage chips can't be added here; the Lineage chip is set by no UI at all |
| C17 | Change / remove one filter | chip label menu; chip ✕ | 2 | — | |
| C18 | Clear search and filters | Strip ✕; empty-grid button | 2 | — | ⚠ filters persist across places |
| C19 | Sort | Strip select | 1 | — | disabled on a page |
| C20 | Group by (Batch, Lineage, Session, Model, None) | grid ctx (once grouped); header ctx | 2 | — | ⚠ in the Catalogue the only way **into** grouping is `cat.groupCycle` (G), which no menu or toolbar shows |
| C21 | Expand / collapse groups (one / all) | header click; header ctx; grid ctx | 3 | `cat.expandAll` / `cat.collapseAll` | only when grouped |
| C22 | Tile size | Strip − / slider / + | 1 | `cat.tileSmaller` / `cat.tileLarger` · [ ] | |
| C23 | Page zoom / Fit / pan | Strip zoom + Fit; canvas ctx › Fit; Ctrl+wheel; middle-drag or Space-drag | 2 | — | |
| C24 | Thumbnail fit, tile caption | Settings › Catalogue | 1 | — | outside the suite (F31) |

**Selection**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C25 | Select / toggle / range | click, Ctrl-click, Shift-click; arrows, Home, End on the grid | 1 | — | gesture |
| C26 | Marquee select | drag on empty page canvas | 1 | — | page only, not the grid |
| C27 | Select all | grid ctx; page canvas ctx | 2 | `cat.selectAll` · Ctrl+A | |
| C28 | Clear selection | strip pill ✕; grid ctx; Inspector "Clear selection"; click on empty page canvas | 4 | `cat.clearSelection` · Esc | |

**Judging**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C29 | Keep / Reject | tile ctx; loupe hub; Inspector Judge (one and several) | 3 | `cat.keep` · K / `cat.reject` · X | the Inspector buttons bypass the commands |
| C30 | Clear keep / reject | tile ctx; hub (secondary); Inspector "○" | 3 | `cat.unstate` · U | ⚠ three labels |
| C31 | Rate 0–5 | tile ctx › Rate ▸; hub › Rate ▾; Inspector stars | 3 | `cat.rate.0–5` · 0–5 | |
| C32 | Tag | Inspector field; tile ctx › Tag… (focuses the Inspector) | 2 | `cat.tag` · T | |
| C33 | Remove a tag | Inspector chip ✕ | 1 | — | |

**Organising (album, groups, pages)**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C34 | Move to group ▸ | tile ctx; hub (secondary); Inspector "Move to" (one and several) | 3 | — | |
| C35 | Move by drag | onto a Places row, a page, another pane, or past the edge of a page | 4+ | — · Ctrl+drop duplicates | |
| C36 | Back to Unprocessed | tile ctx; Inspector; Del on a page; drag onto Unprocessed | 4 | `cat.toUnprocessed` · Shift+Delete | ⚠ the command is enabled only on a page, but the Inspector button shows everywhere |
| C37 | Duplicate assets | tile ctx; hub; Inspector (one and several); Ctrl+drop | 5 | `cat.duplicate` · Ctrl+D | |
| C38 | New group | Places +; Album ctx "New group…"; row ctx "New group inside…"; canvas ctx "New group here…"; Move to ▸ "New group…" | 5 | — | ⚠ four labels |
| C39 | Group these (selection → new group) | page photo ctx (≥ 2 selected); Inspector "Group these" | 2 | — · Ctrl+G | |
| C40 | Rename group | Places ctx; card ctx; Inspector name field | 3 | — | |
| C41 | Duplicate group | Places ctx; card ctx; Inspector | 3 | — | |
| C42 | Ungroup | Places ctx; card ctx; Inspector | 3 | — · Ctrl+Shift+G (page focus) | |
| C43 | Delete group | Places ctx; card ctx; Inspector; Del on a selected card | 4 | — | always confirms |
| C44 | Set group cover | page photo ctx | 1 | — | ctx only; the Inspector only shows a hint |
| C45 | Move / resize items on a page | drag; corner handle; arrows nudge | 2 | — | |
| C46 | Bring to front / Send to back | photo and card ctx | 1 | — | ctx only |
| C47 | Undo / redo page layout | empty-canvas ctx | 1 | — · Ctrl+Z / Ctrl+Shift+Z | not in the photo or card menus |

**Viewing**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C48 | Open in loupe | tile double-click; page photo double-click; tile ctx; Inspector thumbnail double-click; Inspector More; Inspector (several) | 6 | `cat.loupe` · Enter | ⚠ shows clips and audio through `<img>` |
| C49 | Loupe zoom / pan / Fit / 1:1 | Ctrl+wheel and drag; facts bar | 1 | `cat.loupe.fit` · Ctrl+0 / `cat.loupe.one` · Ctrl+1 | |
| C50 | Previous / next | facts bar ‹ › | 1 | `cat.prev` / `cat.next` · ← → | |
| C51 | Pin for compare | tile ctx; hub; Inspector | 3 | `cat.pin` · C | ⚠ labels Pin / Pinned Cn / Unpin Cn / Pin for compare |
| C52 | Open compare | tile ctx; strip tray "Compare" | 2 | `cat.compare` · Shift+C | |
| C53 | Unpin all | grid ctx; strip tray ✕; compare bar | 3 | `cat.unpinAll` | |
| C54 | Compare: wipe, difference, 2/4-up, Swap, Fit, 1:1 | compare bar | 1 | `cat.compare.swap` · Tab | ⚠ Ctrl+0/1 do nothing here; Tab overrides focus mode |
| C55 | Lineage tree | tile ctx; hub; Inspector "Open tree"; tile ⤷ badge | 4 | `cat.lineage` · L | double-click a card re-roots the tree |
| C56 | Lineage path (select an ancestor) | Inspector › Lineage thumbnails | 1 | — | |
| C57 | Prompt JSON / Copy prompt | Inspector › Prompt; Inspector More | 2 | — | not in the tile menu |
| C58 | Copy ids | Inspector › Details | 1 | — | |
| C59 | Play an audio asset | Inspector audio player | 1 | — | |

**Send to another suite**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C60 | Open in Edit | tile ctx; hub; Inspector; Edit tab drop | 4 | `cat.edit` · E | |
| C61 | Use as reference in Generate | tile ctx; hub; Inspector (one and several); Generate tab drop; reference-slot drop | 6 | `cat.reference` · R | ⚠ ignores the model's reference limit |
| C62 | Re-run (same seed) | tile ctx; hub; Inspector | 3 | `cat.rerun` · Ctrl+R | ⚠ overwrites the Generate panel without asking |
| C63 | Variations (new seeds) | tile ctx **twice** (top level and Start ▸); hub; Inspector Actions; Inspector Start card | 5 | `cat.variations` · V | ⚠ doubled in the same menu and in the same Inspector |
| C64 | Load in Generate | Inspector Actions | 1 | — | not a command: not in ⌘K or any menu |
| C65 | Animate from this frame (start) | tile ctx **twice**; hub Animate ▾; Inspector Animate ▾; Inspector Start card; Animate tab drop | 6 | `cat.animate` · Shift+A | ⚠ four labels; on a clip it plays the clip instead |
| C66 | Use as end frame | tile ctx; hub Animate ▾; Inspector Animate ▾ | 3 | `cat.animateEnd` · Shift+Z | |
| C67 | Remove background → Edit AI Select | tile ctx Start ▸; Inspector card | 2 | `cat.start.removeBg` | ⚠ only selects the subject; it removes nothing |
| C68 | Upscale → Edit AI Upscale | tile ctx Start ▸; Inspector card | 2 | `cat.start.upscale` | |
| C69 | New angle → Generate Angle tab | tile ctx Start ▸; hub; Inspector card | 3 | `cat.start.angle` | |
| C70 | Make a 3D prop | tile ctx Start ▸; Inspector card | 2 | `cat.start.mesh` | confirms the cost; results land in **Generate**'s grid |
| C71 | Make a character / place / prop → Story Cast | tile ctx Start ▸; Inspector cards | 2 each | `cat.start.character` / `.place` / `.prop` | |
| C72 | Make a shot from this clip → Story Shots | tile ctx Start ▸ | 1 | `cat.start.shot` | ⚠ a clip-only action inside "Start from this **image**" |
| C73 | Reveal in folder | tile ctx; hub; Inspector More | 3 | `cat.reveal` · Ctrl+Shift+R | |

**Trash and import**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| C74 | Move to trash | tile ctx; Inspector More; Inspector (several); drag onto Trash row or pane | 5 | `cat.trash` · Delete | ⚠ **two toasts** (command + store); on a page Delete means Back to Unprocessed instead |
| C75 | Restore | tile ctx; Inspector; undo toast | 3 | `cat.restore` | |
| C76 | Delete permanently | tile ctx; Inspector More; Inspector "Delete…" | 3 | `cat.purge` | |
| C77 | Empty trash | strip (armed two-step button); Places Trash ctx; tile ctx | 3 | `cat.emptyTrash` | ⚠ the button arms twice; the menus open a dialog |
| C78 | Import | strip Import; grid ctx; empty-state card | 3 | `cat.import` | the strip button bypasses the command |
| C79 | Import Files / Folder / Paths | Strip Import ▾ | 1 | — | Files and Folder only in the Tauri shell |
| C80 | Import by OS file drop | drop on the grid | 1 | — | also active in Generate's results grid |

## 4. Generate (G)

Files (in `suites/generate/`): `GenerateSuite.tsx`, `AngleTab.tsx`, `LoraSlots.tsx`, `RefExtras.tsx`, `StylePicker.tsx`, `fieldPresets.ts`,
`useMentions.ts`, `generateStore.ts`, `store/modelCaps.ts`. Generate makes **text-to-image** (with optional reference images) and **new angle**
only. Refine, inpaint, outpaint and upscale exist only in Edit's AI panel (§5).

### 4.1 Screen map

| Region | Contents |
| --- | --- |
| Rail | Prompt · Model · Size & Batch · Presets · New angle |
| Panel › Prompt | Tree / JSON / Text switch + word and token counter · **style** select (Story world styles) · per mode: **Tree** (scene · reference images · subject cards · look: style, palette, lighting, mood, background, composition · camera: angle, lens, depth of field, f-number, distance · extras: lead text, negative) · **JSON** (textarea, to Tree, pretty, compact, import clipboard) · **Text** (textarea with @mentions) · in every mode: the reference block, the serialisation preview, a disabled "Upsample ✨ (later)" |
| Panel › Model | model cards · SAMPLING (Turbo LoRA, steps, guidance, CFG, sampler, scheduler, seed) · Advanced (shift, weight dtype, text encoder + device, tiled VAE) · LORA SLOTS (4) |
| Panel › Size & Batch | tier thumb / draft / full / custom · aspect (6) · W × H · count 1–8 · estimate |
| Panel › Presets | Save panel preset · panel presets (apply, ✕) · field presets (🗑 only) |
| Panel › New angle | source slot · moves (Top-down, Rotate L/R 45°, Close-up, Wide) · method · keep sentence · candidates 1–4 |
| Foot | **Generate N ▶** · **Stage** · Fetch N GB · reason or estimate. On the Angle tab: **New angle ×n ▶** · Fetch |
| Strip | "show: this batch / session / all" + the **old Catalogue strip** (group, all/keep/reject, sort, chips, and with a selection 11 verb icons + tag + trash, Compare, Unpin all, tile size) |
| Centre | **interim** job cards (t2i only: preview, progress, cancel / run) above the Catalogue grid (loupe, compare and lineage included) |
| Inspector | the Catalogue Inspector, on Generate's results |
| ctx | filled reference slot: Remove · Move first · Move left · Move right │ Clear references. The grid uses the Catalogue menus. |
| Popovers | field-preset menu (built-ins, yours, Remove ▸, Save current text…); @mention menu (Story profiles, then album groups) |

### 4.2 Inventory

**Prompt**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| G1 | Prompt mode Tree / JSON / Text | Prompt › switch | 1 | — | ⚠ "Tree" from JSON does not parse the JSON; only "to Tree" does |
| G2 | Word / token counter | Prompt | 1 | — | |
| G3 | Serialisation preview | Prompt (collapsible) | 1 | — | |
| G4 | Upsample ✨ | Prompt | 1 | — | ⚠ permanently disabled |
| G5 | Tree fields: scene, subject cards (description, position, action, pose, colour match), style, palette, lighting, mood, background, composition, angle, lens, depth of field, f-number, distance | Prompt › Tree | 1 each | — | add / remove subject cards; palette swatches use the native colour picker |
| G6 | Lead text | Prompt › Tree › extras | 1 | — | ⚠ **the same value as the Text-mode prompt** |
| G7 | Negative prompt | Prompt › Tree › extras (non-distilled models only) | 1 | — | ⚠ shown in Tree mode only, but **sent in every mode** |
| G8 | Field presets: apply / save / remove | ListPlus button on 16 fields; Presets tab (remove only) | 16+1 | — | app-wide, not per project; ⚠ remove deletes by name across every field |
| G9 | JSON edit · to Tree · pretty · compact · import clipboard | Prompt › JSON | 1 each | — | |
| G10 | Text prompt | Prompt › Text | 1 | — | |
| G11 | Style (Story world style) | Prompt › style select | 1 | — | ⚠ a different thing from the Tree "style" field |
| G12 | @mention (group or Story profile) | @ button or typing @ in multiline fields (scene, subject description, Text) | 3 | — | |
| G13 | Mention chips: stop mentioning, LoRA on/off | reference block chips | 1 | — | ⚠ the LoRA toggle on a chip switches it for the **whole panel** |

**References**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| G14 | Add a reference | drop on the slots; Generate tab drop; Catalogue `cat.reference` (C61) | 3+ | — | ⚠ models with 0 references (Krea, Z-Image, Chroma) still show the block |
| G15 | Remove a reference | slot ✕; slot ctx | 2 | — | |
| G16 | Reorder references | slot ◀; slot ctx (first, left, right) | 2 | — | Move right and Move first are in the ctx only |
| G17 | Clear references | slot ctx | 1 | `gen.clearRefs` | |
| G18 | Reference note | a row under each slot | 1 | — | |
| G19 | Reference downscale | under the slots | 1 | — | |
| G20 | Faster-model hint / dropped-references warning | under the slots | — | — | text only |

**Model and sampling**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| G21 | Pick a model | Model cards | 1 | — | ⚠ does not re-apply the tier size; the stale text "coming in M5" is still on cards |
| G22 | Turbo LoRA + strength | Model (FLUX.2 dev only) | 1 | — | |
| G23 | Steps / guidance / CFG | Model › SAMPLING | 1 each | — | ⚠ overrides survive model changes; only steps has a reset |
| G24 | Sampler / scheduler | Model › SAMPLING | 1 each | — | ⚠ the FLUX-only `flux2` scheduler is offered for every model |
| G25 | Seed: random / fixed / increment, value, 🎲 | Model › SAMPLING | 1 | — | |
| G26 | Shift, weight dtype, text encoder + device, tiled VAE | Model › Advanced | 1 each | — | ⚠ a custom shift breaks Z-Image and Chroma; the error shows only as the Foot's reason |
| G27 | LoRA slots 1–4 + strength + "+ trigger" | Model › LORA SLOTS | 1 | — | "+ trigger" in Text mode only; Story's "Use in Generate" replaces all four slots |

**Size, presets, angle, run**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| G28 | Tier / aspect / W × H | Size & Batch | 1 each | — | |
| G29 | Count 1–8 | Size & Batch; shown on the Generate button | 1 | — | the Angle tab uses a separate 1–4 stepper |
| G30 | Estimate (time, VRAM) | Size & Batch; Foot | 2 | — | |
| G31 | Save panel preset | Presets | 1 | `gen.savePreset` · Ctrl+S | saved per project |
| G32 | Apply / delete panel preset | Presets | 1 | — | delete has no confirmation |
| G33 | New angle: source | Angle slot drop; Catalogue `cat.start.angle` | 2 | `gen.angle.clear` (remove) | |
| G34 | New angle: move ×5, method, keep, candidates | Angle tab | 1 each | `gen.angle.*` (moves) | |
| G35 | New angle ▶ | Foot (Angle tab) | 1 | `gen.angle.generate` | ⚠ no job card in the Centre while it runs |
| G36 | **Generate** | Foot | 1 | `gen.generate` · Ctrl+Enter | ⚠ the command has no `when`, so the key and ⌘K submit even when the button is disabled |
| G37 | **Stage** (queue, run later) | Foot | 1 | `gen.stage` · Ctrl+Shift+Enter | the same issue as G36 |
| G38 | Fetch missing weights → Models | Foot "Fetch N GB" | 1 | — | ⚠ opens Models unfiltered |
| G39 | Cancel / release a running job | interim card ✕ / run | 1 | — | also in the Dock |
| G40 | Show this batch / session / all | Strip | 1 | — | |
| G41 | Results verbs | the Catalogue's strip, grid, Inspector and menus | — | `cat.*` | ⚠ `cat.*` commands are not in ⌘K while in Generate |

### 4.3 What the form shows per model (from `/capabilities`)

| Model | Turbo | Steps | Guidance | CFG | Negative | Text-encoder picker | Reference slots |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FLUX.2 dev | ✔ | edit | ✔ | fixed 1.0 | shown | — | 10 |
| Klein 9B / 9B KV | — | fixed 4 | ✔ | fixed | hidden | ✔ | 4 |
| Klein 9B base | — | edit | ✔ | edit | shown | ✔ | 4 |
| Klein 4B / 4B base | — | fixed 4 / edit | ✔ | fixed / edit | hidden / shown | — | 4 |
| Krea 2 Turbo / Raw | — | fixed 8 / edit | hidden | fixed / edit | hidden / shown | — | 0 |
| Z-Image, Chroma1-HD | — | edit | hidden | edit | shown | — | 0 |
| SD 3.5 Large | not offered (Refine only, in Edit) | | | | | | |

### 4.4 Reused from the Catalogue

Generate's Strip, Centre grid and Inspector are the Catalogue's components, run on a separate store of results. It uses the **older** strip
(group select, all/keep/reject, verb icons). The Catalogue's own strip has moved on: filters, compare tray, split. Side effects of the reuse:

- An OS file drop in Generate imports into *Unprocessed*.
- The empty state offers "Generate an image" while you are already in Generate.
- The Inspector's breadcrumbs and "Unprocessed" link turn Generate's Centre into an album page (§11.1).
- Meshes from "Make a 3D prop" appear here.

## 5. Edit (E)

Files (in `suites/edit/`): `editCommands.ts` (EC), `EditSuite.tsx`, `EditorCanvas.tsx`, `propsEditors.tsx`, `widgets.tsx`. Two menus recur
below: **LM** is the layer-row ctx, also opened by the layers footer's More ▾, and **CM** is the canvas ctx.

### 5.1 Screen map

| Region | Contents |
| --- | --- |
| Rail | Tool options · Brushes · Selection · AI · Documents |
| Panel › Tool options | **toolbox** (14 tools: Move V, Marquee M, Lasso L, Magic wand W, Quick selection, Spot healing J, AI select A, Brush B, Eraser E, Fill/gradient G, Eyedropper I, Crop/canvas C, Hand H, Zoom Z) + the options of the current tool |
| Panel › Brushes | 7 built-in + your presets · Save current as preset · current brush controls + colour swatches |
| Panel › Selection | Select all · Deselect · Invert · Layer transparency · amount · Expand · Contract · Border · Smooth · Feather · Quick mask · mask from selection · load mask · crop to selection · **Refine edge** block |
| Panel › AI | op: **Select / Inpaint / Refine / Upscale / Outpaint**, each with its own controls and Advanced section · candidates · seed · **AI ▶ op ×N** · **Stage** · hints |
| Panel › Documents | new-document form · the project's documents (open, delete) |
| Foot | **Save** · Save to Catalogue · Export PNG · Export PSD · Close |
| Strip | doc name/size · transform bar (while transforming) · polygon Close/Cancel (while open) · Shift / Ctrl / Alt latches · Undo · Redo · zoom − % + · Fit · 100 % · pixel grid · mask overlay · **before** (hold) · quick mask · cursor · renderer badge |
| Centre | the canvas · the candidate strip after an AI run (hover previews, click keeps, Keep all) · empty state (drop zone, New 1920×1080, Open the Catalogue, recent documents) |
| Inspector › layers | the layer tree (eye, lock, thumbnail, name, mask link, mask thumbnail) · active-layer block (blend, opacity, fill, group mode, clip, mask options) · footer (New, New group, Group, Add adjustment ▾, Add filter ▾, Duplicate, Merge down, Up, Down, Add/Remove mask, Hide, Lock, Delete, More ▾) |
| Inspector › properties | layer x/y · group mode · adjustment/filter editors (Levels, Curves, Colour balance, generic) + Reset · layer mask · **AI recipe** (Re-run new seed, Copy JSON) · quick actions |
| Inspector › history | steps (click to go), "back to the opened state" |
| Inspector › info | document facts · "Compare preview with the exact flatten" |
| LM | Rename · Hide, Solo, Lock · Duplicate, Merge, Group, Ungroup, Up, Down · Layer transparency, Ink from white, Lock transparency, **Transform ▸**, **Mask ▸** · Delete |
| CM | (transform heading) · (lasso heading) · Undo, Redo · **Selection** (Select all, Deselect, Invert, Modify ▸, Refine edge, Layer transparency, Quick mask, Clear, Crop, Mask from selection) · **Clipboard** (Layer via copy/cut, Copy, Cut, Copy merged, Paste, Paste in place) · **Layer ▸** · **View ▸** · **Tool ▸** (14) · **Document ▸** |

### 5.2 Inventory

**Document and history**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E1 | Save | Foot; CM › Document | 2 | `edit.save` · Ctrl+S | autosaves every 2 min |
| E2 | Save to Catalogue (flatten) | Foot; CM › Document | 2 | `edit.saveToCatalogue` · Ctrl+Shift+S | |
| E3 | Export PNG / PSD | Foot; CM › Document | 2 each | `edit.exportPng` · Ctrl+Shift+E / `edit.exportPsd` | |
| E4 | Close document | Foot; CM › Document | 2 | `edit.close` | confirms when dirty |
| E5 | Compare preview with exact flatten | Inspector › info; CM › Document | 2 | `edit.compare` | ⚠ a developer check shown to users |
| E6 | New document | Documents form; empty-state button; global quick action | 3 | — (`global.start.newDocument`) | no Edit command |
| E7 | Open document | Documents row; empty-state recents; Dock origin | 3 | — | |
| E8 | Delete document | Documents 🗑 | 1 | — | confirms |
| E9 | Open an asset as a document | Catalogue C60; tab / empty-stage drop; Animate "Send to Edit" | 4+ | `cat.edit` | |
| E10 | Add a tile / OS file as a layer | drop on the canvas or the layer list | 2 | — | gesture only |
| E11 | Undo / Redo | Strip; CM; history list | 3 | `edit.undo` · Ctrl+Z / `edit.redo` · Ctrl+Shift+Z | |
| E12 | Step to a history state / back to opened | Inspector › history | 1 | — | |

**Tools** (each in the toolbox and in CM › Tool ▸, so n = 2; the command is `edit.tool.<id>`)

| # | Function | Options and gestures | Command · key | Notes |
| --- | --- | --- | --- | --- |
| E13 | Move | drag the active raster layer; nudge ▲◀▶▼ buttons; transform, flip and rotate shortcuts | V | ⚠ no click-to-pick a layer; nudge buttons are not commands |
| E14 | Marquee | rect/ellipse · mode · feather · style (normal, ratio, size) | M | |
| E15 | Lasso | freehand / polygon / magnetic (width, contrast, frequency) · Close · Cancel · Remove last point | L | ⚠ labels "polygon" / "Close polygon" / "Close the border" / "border" |
| E16 | Magic wand | tolerance, sample all, contiguous, anti-alias | W | |
| E17 | Quick selection | size, sample all | **no key** | ⚠ Q is quick mask |
| E18 | Spot healing | size, sample all | J | needs the native extension |
| E19 | AI select | click = include point, Alt-click = exclude, drag = box; compact AI Select controls | A | |
| E20 | Brush / Eraser | size, hardness, opacity, flow, spacing, smoothing · ± size / hardness buttons · straight lines · pick colour · swatches | B / E | Shift-click draws a line; Alt-click picks a colour |
| E21 | Fill / gradient | solid / linear / radial, colour, opacity | G | |
| E22 | Eyedropper | click picks the composite colour | I | |
| E23 | Crop / canvas | canvas W/H + anchor · **Resize canvas** · Crop to selection | C | ⚠ **no canvas gesture**: clicking or dragging does nothing; it is only a form |
| E24 | Hand | drag; also Space-drag, middle-drag, wheel | H | |
| E25 | Zoom | click in, Alt-click out | Z | |

**Brush and colour**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E26 | Brush larger / smaller / harder / softer | brush and eraser options buttons | 1 | `edit.brush.*` · [ ] Shift+[ ] | [ and ] also size the quick-selection, heal and magnetic tools, which have no buttons |
| E27 | Brush opacity 10–100 % | — | **0** | `edit.brush.opacity.0–9` · 0–9 | ⚠ key only (the opacity field is the mouse route) |
| E28 | Brush presets apply / save / delete | Brushes tab | 1 | — | |
| E29 | Foreground / background colour, swap, default | swatches ×3 (brush, fill, Brushes tab) | 3 | `edit.colour.swap` · X / `edit.colour.default` · D | |

**Selection**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E30 | Select all / Deselect / Invert | Selection tab; CM | 2 | `edit.sel.all` · Ctrl+A / `.none` · Ctrl+D / `.invert` · Ctrl+Shift+I | Esc also deselects (not listed) |
| E31 | Select layer transparency | Selection tab; LM; CM; quick actions; Ctrl-click the thumbnail | 5 | `edit.sel.fromLayer` | |
| E32 | Expand / Contract / Border / Smooth / Feather by N px | Selection tab; CM › Modify | 2 | `edit.sel.*` | the amount field is in the Selection tab only |
| E33 | Refine edge (+ settings) | Selection tab; CM; AI Select checkbox | 3 | `edit.sel.refine` | |
| E34 | Quick mask | Strip; Selection tab; CM | 3 | `edit.sel.quickMask` · Q | ⚠ four labels |
| E35 | Clear selected pixels | CM | 1 | `edit.sel.clear` · Delete | ctx only |
| E36 | Crop to selection | Selection tab; CM; Crop tool options | 3 | `edit.sel.crop` | |
| E37 | Load mask as selection | Selection tab; mask options ×2; LM; Ctrl-click the mask | 5 | `edit.mask.load` | |

**Clipboard** (CM only, n = 1 each; ⚠ the commands claim a panel home that doesn't exist)

| # | Function | Command · key |
| --- | --- | --- |
| E38 | Copy · Cut · Copy merged | `edit.copy` · Ctrl+C · `edit.cut` · Ctrl+X · `edit.copyMerged` · Ctrl+Shift+C |
| E39 | Paste · Paste in place | `edit.paste` · Ctrl+V · `edit.pasteInPlace` · Ctrl+Shift+V |
| E40 | Layer via copy · Layer via cut | `edit.layer.viaCopy` · Ctrl+Alt+J · `edit.layer.viaCut` · Ctrl+Shift+J |

**Layers**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E41 | Select / multi-select layers | row click, Ctrl-click, Shift-click | 1 | — | |
| E42 | New layer | layers footer; CM › Layer | 2 | `edit.layer.new` · Ctrl+Shift+N | |
| E43 | New empty group | layers footer | 1 | `edit.layer.newGroup` | |
| E44 | Group / Ungroup | footer, LM, CM, row drops / LM, quick actions | 4 / 2 | `edit.layer.group` · Ctrl+G / `.ungroup` | the same icon for both |
| E45 | Duplicate | footer; LM; CM; quick actions; drop on Duplicate/New; Alt-drop | **6** | `edit.layer.duplicate` · Ctrl+J | |
| E46 | Merge down / merge selected | footer; LM; CM | 3 | `edit.layer.mergeDown` · Ctrl+E | no Flatten or Merge visible |
| E47 | Move up / down / reorder / into a group | footer; LM; row drag | 3 | `edit.layer.up` / `.down` | |
| E48 | Rename | LM; double-click | 2 | `edit.layer.rename` | |
| E49 | Hide / show · Solo | footer, LM, eye / LM, Alt-click eye | 3 / 2 | `edit.layer.visibility` / `.solo` | |
| E50 | Lock | footer; LM; row lock icon | 3 | `edit.layer.lock` | the row icon ignores multi-selection |
| E51 | Delete | footer; LM; CM; drop on 🗑 | 4 | `edit.layer.delete` · **no key** | undo toast |
| E52 | Lock transparency · Ink from white | LM; quick actions | 2 | `edit.layer.lockAlpha` / `.inkFromWhite` | ⚠ Ink from white repeats the Colour-to-alpha filter, destructively |
| E53 | Blend · opacity · fill · group mode · clip | layers active block (group mode and clip also in properties) | 1–2 | — | |
| E54 | Layer x / y | Inspector › properties | 1 | — | |
| E55 | Add adjustment layer (8 types) | footer ▾; CM › Layer | 2 | `edit.layer.adjustment.*` | |
| E56 | Add filter layer (5 types) | footer ▾; CM › Layer | 2 | `edit.layer.filter.*` | |
| E57 | Edit Levels / Curves / Colour balance / generic params · Reset | Inspector › properties | 1 | — | |

**Masks**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E58 | Add mask: reveal all / hide all / reveal selection / hide selection / from transparency | footer; LM › Mask; the "+◐" box (Alt variants); Selection tab; CM; quick actions | 2–4 each | `edit.mask.add` / `.hideAll` / `.fromSelection` / `.hideSelection` / `.fromTransparency` | ⚠ two vocabularies: "Add mask (hide all)" vs "Hide all" |
| E59 | Edit mask / pixels | LM; mask or raster thumbnail click; hint button | 4 | `edit.mask.edit` | |
| E60 | Show mask alone · enable/disable · link/unlink | LM; Alt/Shift-click the mask; chain icon; checkboxes ×2 | 2–4 | `edit.mask.view` / `.toggle` / `.link` | mask options appear in both layers and properties |
| E61 | Apply / remove mask · density · feather | mask options ×2; LM; footer | 2–3 | `edit.mask.apply` / `.remove` | |
| E62 | Mask overlay (rubylith) | Strip; CM › View | 2 | `edit.view.overlay` · Alt+\ | |

**Transform**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E63 | Free transform | Move options; quick actions; LM; CM › Layer | 4 | `edit.transform` · Ctrl+T | |
| E64 | Mode free / skew / distort / perspective | LM; CM heading; transform bar | 3 | `edit.transform.mode.*` | |
| E65 | Box gestures, X/Y/W/H/angle/interpolation | canvas; transform bar | 2 | — · arrows nudge | |
| E66 | Apply / Cancel | Move options; transform bar; LM; CM heading; CM › Layer; double-click (apply) | **6 / 5** | `edit.transform.apply` · Enter / `.cancel` · Esc | ⚠ CM lists Apply and Cancel twice |
| E67 | Flip H/V · rotate 90° CW/CCW · 180° | Move options (not 180°); LM; CM | 2–3 | `edit.layer.flip*` / `.rot*` | per layer only; there is no whole-image rotate, flip or Image size |

**View**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| E68 | Zoom in / out / Fit / 100 % / 200 % / typed % | Strip; CM › View; Zoom tool; Ctrl+wheel | 1–4 | `edit.view.*` · Ctrl++ Ctrl+- Ctrl+0 Ctrl+1 Ctrl+2 | ⚠ Ctrl+1/2 shadow the suite switch while a document is open; 200 % is ctx only |
| E69 | Pixel grid | Strip; CM › View | 2 | `edit.view.grid` | |
| E70 | Before (hide the active layer) | Strip (hold) | 1 | `edit.view.before` · \\ | ⚠ the button holds, the command toggles |
| E71 | Renderer auto / WebGL2 / WebGPU | Strip badge | 1 | — | developer-facing |
| E72 | Modifier latches Shift / Ctrl / Alt | Strip | 1 | `edit.latch.*` | |

**AI** (Panel › AI; ⚠ **none of these runs is a command**, so none is in ⌘K, CM or the keyboard map)

| # | Function | Homes today | n | Notes |
| --- | --- | --- | --- | --- |
| E73 | **AI Select** (model, find text, points, box, threshold, combine, expand, feather, refine edge) → Select ▶ / Stage | AI tab; A-tool options (compact); A-tool canvas clicks; Catalogue "Remove background" | 3 | |
| E74 | **Inpaint**: Fill / Fill-Match / Fill Hero / Remove / Quick remove (CPU), pre-fill, prompt, encoder, LanPaint, margin, feather, blend | AI tab | 1 | needs a selection |
| E75 | **Outpaint**: grow L/T/R/B, prompt, model, encoder, feather | AI tab | 1 | |
| E76 | **Refine** (i2i): model, target, strength, prompt, encoder, feather, match colour | AI tab | 1 | the only Refine in the app |
| E77 | **Upscale**: model, target, detail layer, tiled refine (model, encoder, strength, tile, overlap, prompt) | AI tab; Catalogue "Upscale in Edit" | 1 | |
| E78 | Candidates 1–4 · seed | AI tab | 1 | |
| E79 | Keep candidate N / Keep all / preview by hover | candidate strip | 1 | `edit.cand.1–4` · 1–4 exist but the strip doesn't use them; `edit.cand.keep` · Enter is key-only; ⚠ hovering changes layer visibility |
| E80 | Re-run with a new seed · Copy recipe JSON | Inspector › properties › AI recipe | 1 | |

## 6. Animate (A)

Files (in `suites/animate/`): `AnimateSuite.tsx`, `Player.tsx`, `animateCommands.ts`, `animateStore.ts`.

### 6.1 Screen map

| Region | Contents |
| --- | --- |
| Rail | Inputs · Model · Length & Size · Presets · Clips |
| Panel › Inputs | start **S** and end **E** slots (drop, ✕) + swap · prompt + 10 motion chips · negative ("write my own") · **beats** (LTX only: frame, strength, ✕, drop zone) |
| Panel › Model | video model cards (+ health / fetch) · locked **H3 (hero)** card · preset draft / motion / quality · advanced: steps, CFG, shift |
| Panel › Length & Size | tier · orientation · W×H · frames · fps · seed mode + seed · clips count 1–8 · estimate (+ Fetch N GB) |
| Panel › Presets | Save panel preset · list (apply, ✕) |
| Panel › Clips | every project clip (thumbnail, prompt, model, state); click selects |
| Foot | **Animate n ▶** · **Stage** · reason |
| Strip | Player / Filmstrip / Compare · frame counter · speed · Loop · Onion |
| Centre | player, filmstrip or compare (B = start still / end still / another clip) · **transport** (home, −10, −1, play, +1, +10, end · in, out, clear · Extract frame, Send to Edit, **Make a shot** · busy) · **timeline** (ruler scrub, in/out band and handles, S/E markers, beat ♦, harvested ▼, playhead) · interim job cards |
| Inspector › clip | Keep · Reject · Variations · Re-run · Try other · Show in Catalogue · facts · frames (click start/end = reuse) · identity (Measure) · **extend** (Extend ▶ experimental, Use frame as next start) · continues · line (lip-sync badge) |
| Inspector › frames | current frame · Extract frame · Send to Edit · every k + Extract range · harvested thumbnails |
| Inspector › lineage | sources · extracted · sibling clips |
| ctx | player and timeline: Play, Prev, Next, First, Last │ In, Out, Clear │ Extract frame, Extract range, Send to Edit, Use as next start, Extend ▶ │ Onion, Loop, Compare │ Keep, Reject, Variations, Re-run, Try other, Show in Catalogue. Slots, clip rows, beats and presets have **no** ctx. |

### 6.2 Inventory

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| A1 | Set start frame | S slot drop; Animate tab drop; Catalogue C65 | 3+ | (`cat.animate` · Shift+A) | ⚠ no "pick from Catalogue" on the slot itself |
| A2 | Set end frame | E slot drop; second image of a drop; Catalogue C66 | 3 | (`cat.animateEnd` · Shift+Z) | |
| A3 | Clear start / end | slot ✕ | 1 | `anim.clearStart` / `.clearEnd` | ⚠ the commands are rendered nowhere |
| A4 | Swap start / end | Inputs | 1 | `anim.swap` | |
| A5 | Reuse a clip's start / end as the next one | Inspector frame thumbnails | 1 | — | ⚠ hidden; only the tooltip says it |
| A6 | Prompt · motion chips · negative | Inputs | 1 | — | ⚠ Ctrl+Enter does nothing while typing in the prompt |
| A7 | Keyframe beats (add, frame, strength, remove) | Inputs (LTX) | 1 | — | ⚠ the hint says "drag the marker on the timeline", but the markers can't be dragged |
| A8 | Video model | Model cards | 1 | — | |
| A9 | H3 (hero) | Model (locked card) | 1 | — | ⚠ always disabled |
| A10 | Preset draft / motion / quality; steps / CFG / shift | Model | 1 | — | ⚠ "preset" also names the Presets tab |
| A11 | Tier / orientation / size / frames / fps / seed / clip count | Length & Size | 1 each | — | the clip count also drives `anim.variations` |
| A12 | Panel presets save / apply / delete | Presets | 1 | — | stored in the browser, not the project |
| A13 | **Animate ▶** | Foot | 1 | `anim.animate` · Ctrl+Enter | |
| A14 | **Stage** (run later) | Foot | 1 | `anim.stage` · Ctrl+Shift+Enter | |
| A15 | Fetch missing weights → Models | estimate line | 1 | — | |
| A16 | Select a clip | Clips row; lineage siblings; ready toast; Story, Catalogue, tab drop, origin | 7+ | — | ⚠ Clips has no delete, filter or ctx |
| A17 | View: Player / Filmstrip / Compare | Strip; ctx (Compare) | 1–2 | `anim.view.*` · C (compare) | |
| A18 | Play / step / ±10 / first / last | transport; ctx | 1–2 | `anim.play` · Space, `,` `.` `<` `>` Home End | |
| A19 | Shuttle J / K / L | — | **0** | `anim.shuttle*` · J K L | ⚠ key only; J/L set speeds the speed select can't show |
| A20 | Speed · Loop · Onion | Strip; ctx (Loop, Onion) | 1–2 | `anim.loop` / `anim.onion` · N | |
| A21 | Scrub | ruler drag; filmstrip; ▼ pins; harvested thumbnails | 4 | — | gesture |
| A22 | In / Out / Clear | transport; ctx; handle drag | 2–3 | `anim.setIn` · I / `.setOut` · O / `.clearInOut` | |
| A23 | Extract frame | transport; Inspector › frames; ctx | 3 | `anim.extractFrame` · F | |
| A24 | Extract range (every k) | Inspector › frames; ctx | 2 | `anim.extractRange` · Shift+F | k is set in the Inspector only |
| A25 | Send frame to Edit | transport; Inspector; ctx | 3 | `anim.sendToEdit` · E | |
| A26 | Use frame as next start | Inspector › extend; ctx | 2 | `anim.useAsStart` | the toast calls it "Extend, by hand" |
| A27 | **Extend ▶** (experimental, D88) | Inspector › extend; ctx | 2 | `anim.extend` | |
| A28 | Keep / Reject | Inspector; ctx | 2 | `anim.keep` · Shift+K / `.reject` · X | no "clear" (the Catalogue has one) |
| A29 | Variations / Re-run / Try the other model | Inspector; ctx | 2 | `anim.variations` · V / `.rerun` · Ctrl+R / `.tryOther` | |
| A30 | Measure identity (FaceSim) | Inspector › clip | 1 | `anim.identity` | |
| A31 | Make a shot from this clip → Story | transport | 1 | `anim.toShot` | |
| A32 | Show in Catalogue | Inspector; ctx | 2 | `anim.toCatalogue` | ⚠ opens a hidden "clips" folder scope (§11.6) |
| A33 | Lip-sync | — | 0 | — | lives in Story › Shots (Y43); Animate only shows a badge |

## 7. Stage (S): the 3D blocking suite

Files (in `suites/stage/`): `StageParts.tsx`, `stageCommands.ts`, `stageStore.ts`, `engine.ts`, `ik.ts`.

### 7.1 Screen map

| Region | Contents |
| --- | --- |
| Rail | Library · Outliner · Cameras · Poses · Shot |
| Panel › Library | Stages list (+ new, click opens) · **Figures** (Adult, Child) · **Sets** (room, street, deck, empty) · **Props** (crate, stool, table, pole, block) · **Meshes** (Catalogue 3D props) · hint: drop a tile on the viewport for an image plane |
| Panel › Outliner | objects (swatch, name, eye, lock; click, double-click, ctx) · cameras |
| Panel › Cameras | + camera · camera rows · focal presets + mm · roll · Look through · Set from view · Frame all · Delete · **New shot from this camera…** |
| Panel › Poses | 10 preset poses · saved poses · Mirror · Reset · Save pose · joint + x·y·z |
| Panel › Shot | method cards (Clay reference / Exact pose) · Image 1 (passes, Render passes, use stale) · reference deck (drop, note) · prompt · Draft/Full · candidates · prompt preview · **Results** (click = clip start) · **Clip**: IC-LoRA / Wan Animate, Depth / Pose, Render sequence, **Animate ▶**, clip thumbnails |
| Foot | New stage… / **Generate ×n ▶** (Shot tab) / save state |
| Strip, row 1 | Free / camera view · guides · Frame everything · stage name |
| Strip, row 2 | **timeline**: prev key, prev, play, next, next key · frame · scrub · range + fps · [ ] · Key camera · Key object · Remove keys |
| Centre | three.js viewport (orbit, pan, zoom) · transform gizmo · gizmo bar (Select, Move, Rotate, Scale, Snap, Undo, Redo) · framing guides · empty-stage cards |
| Inspector | object (name, transform, pose, faces camera, parent, Duplicate, Lock, Hide, Frame, Reset, Delete) · camera (only while the Cameras tab is open and nothing is selected) · stage (name, size, Rename, Delete) |
| ctx | object (viewport or Outliner): Frame, Duplicate, Lock, Hide, Reset │ pose verbs │ Delete │ Undo, Redo · empty viewport: Add ▸, Add camera │ tools, Snap │ Frame all │ Render passes, Generate the shot │ Key camera, Remove keys, Render sequence, Animate the shot │ Undo, Redo |

### 7.2 Inventory

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| S1 | New stage | Library +; Foot; empty Centre card | 3 | `stage.new` | |
| S2 | Open stage | Library row; Story `story.shot.openStage`; Dock origin | 3 | — | |
| S3 | Rename / delete stage | Inspector (stage view) | 1 | `stage.rename` / `stage.delete` | not offered from the Library list |
| S4 | Undo / Redo | gizmo bar; both ctx | 3 | `stage.undo` · Ctrl+Z / `.redo` · Ctrl+Shift+Z | |
| S5 | Add figure / set / prop | Library buttons; ctx › Add ▸; empty-stage cards | 2–3 | `stage.add.*` | |
| S6 | Add a mesh prop | Library card; drop a mesh on the viewport | 2 | — | not in Add ▸ |
| S7 | Add an image plane | drop an image on the viewport | 1 | — | ⚠ drag only |
| S8 | Select object | viewport click; Outliner row | 2 | — | no multi-select |
| S9 | Tools Select / Move / Rotate / Scale · Snap | gizmo bar; ctx | 2 | `stage.tool.*` · W G R S / `stage.snap` · Q | |
| S10 | Numeric transform · parent · faces camera | Inspector | 1 | — | |
| S11 | Reset transform · Duplicate · Delete | Inspector; object ctx | 2 | `stage.object.reset` / `.duplicate` · Ctrl+D / `.delete` · Delete | |
| S12 | Lock · Hide | Inspector; object ctx; Outliner icons | 3 | `stage.object.lock` · L / `.hide` · H | |
| S13 | Rename object / camera | double-click in Outliner / Cameras | 1 | — | ⚠ double-click only |
| S14 | Orbit / pan / zoom the free view | viewport mouse | 1 | — | ⚠ right-drag pan may also open the ctx; not in Help |
| S15 | Free / camera view · guides · Frame everything · Frame selection | Strip; Cameras tab; Inspector; ctx; Outliner double-click | 1–3 | `stage.view.*` · C, `stage.guides`, `stage.frameAll` · Home, `stage.frameSel` · F | |
| S16 | Add camera · set active · focal · roll · position / target | Cameras tab; Outliner; Inspector; ctx (add) | 1–2 | `stage.camera.add` | |
| S17 | Set camera from view · delete camera | Cameras tab; Inspector (set) | 1–2 | `stage.camera.setFromView` / `.delete` | |
| S18 | New shot from this camera → Story | Cameras tab; Shot tab header | 2 | `stage.camera.toShot` | ⚠ a Story "shot" is not the Stage "Shot" tab |
| S19 | Pose preset · saved poses · Mirror · Reset · Save | Poses tab; Inspector select; figure ctx | 1–2 | `stage.pose.mirror` · M / `.reset` / `.save` | |
| S20 | Select a joint / rotate (FK) / drag a hand or foot (IK) | viewport (pose mode); Poses tab fields | 1–2 | — | IK is gesture-only |
| S21 | Shot method · Image 1 passes · use stale | Shot tab; ctx (Render passes) | 1–2 | `stage.shot.passes` | |
| S22 | Shot references (add, remove, note) | Shot tab deck | 1 | — | ⚠ drag only; `stage.shot.clearRefs` is rendered nowhere |
| S23 | Prompt · Draft/Full · candidates | Shot tab | 1 | — | |
| S24 | **Generate the shot** | Foot (Shot tab); ctx | 2 | `stage.shot.generate` · Ctrl+Enter | the key works from any tab |
| S25 | Pick a result as the clip start | Shot results click | 1 | — | results have no other actions (open, Catalogue, Edit) |
| S26 | Timeline: play, frame, key, range | Strip row 2 | 1 | `stage.anim.*` · Space ← → Shift+← → [ ] | |
| S27 | Key camera / key object / remove keys | Strip row 2; ctx (camera, remove) | 1–2 | `stage.anim.keyCamera` · K / `.keyObject` · Shift+K / `.removeKey` | moving a keyed object auto-keys |
| S28 | Clip method · guide · **Render sequence** · **Animate ▶** | Shot tab › Clip; ctx | 2 | `stage.clip.guide` / `stage.clip.animate` | ⚠ "Animate ▶" here is not the Animate suite, but its clips land in Animate › Clips |

## 8. Models (M)

Files: `suites/models/ModelsSuite.tsx`, `TrainedTable.tsx`. ⚠ **None of the Models functions is a command.** They are all plain buttons,
with no ⌘K entry, key or ctx, which breaks D32 for a whole suite.

| Region | Contents |
| --- | --- |
| Rail | Roster · Engine |
| Panel › Roster | family filter · search · show retired · models root · "Unlisted: N files" |
| Panel › Engine | state, versions, VRAM, jobs, log path, last error · Start · Stop · Restart · Free VRAM |
| Strip | roster counts (verified / present / missing) · Rescan disk |
| Centre | roster table (model, family, licence, size, health, **Fetch**) · **Trained (this project)**: LoRA, base, steps, size, trigger, Show in Cast, Delete |
| Inspector | the selected entry: id, folder, licence, source, path, sha256 … · Verify sha256 · Reveal |

| # | Function | Homes today | n | Notes |
| --- | --- | --- | --- | --- |
| M1 | Open Models | tab; engine chip; weights chip; banner; Fetch buttons in Generate, Angle, Animate and Stage | 7+ | ⚠ none of them lands on a specific entry or tab |
| M2 | Filter by family · search · show retired | Roster | 1 | |
| M3 | Unlisted files | Roster (a count only) | 1 | ⚠ the files are never listed |
| M4 | Rescan disk | Strip | 1 | |
| M5 | Fetch weights | table row | 1 | ⚠ no cancel and no "fetch all missing" |
| M6 | Verify sha256 · Reveal | Inspector | 1 | in the browser build Reveal copies the path silently |
| M7 | Delete weights | — | 0 | ⚠ missing: the house rule says unneeded weights are deleted, but the UI can't do it |
| M8 | Engine Start / Stop / Restart / Free VRAM | Engine tab | 1 | |
| M9 | Engine log | Engine tab (path only) | 1 | no way to open it |
| M10 | Trained LoRAs: Show in Cast · Delete | Trained table | 1 | ⚠ repeats Story › Cast; "Show in Cast" may open another Story tab |

## 9. Story (Y)

Files (in `suites/story/`): `StoryParts.tsx`, `storyCommands.ts`, `storyStore.ts`, `TrainingBlock.tsx`, `VoicesBlock.tsx`, `LipsyncBlock.tsx`,
`flow/FlowCanvas.tsx`, `episode/SequencePanel.tsx`, `episode/SequenceStage.tsx`, `episode/sequenceCommands.ts`. Story has five
workspaces. Its Panel, Foot, Strip, Centre and Inspector all change with the rail tab.

### 9.1 Screen map

| Tab | Panel | Foot | Strip | Centre | Inspector | ctx |
| --- | --- | --- | --- | --- | --- | --- |
| **World** | sections (jump) · Add style / beat / variable | save state | "World" + format | editor: logline, synopsis, styles (★ default), spine beats (▲▼), variables | world (default style) · selected style / beat / variable | row: style (default, remove) · beat (earlier, later, make a Flow node, remove) · variable (remove) |
| **Cast** | class filter · search · profiles · New profile / place / prop | **Expand ▶** | name · version select (view) · New version · Lock · **Bootstrap** chain (Cast › Expand › Curate › Train › Lock) | version page: hero, prompt stub, coverage grid, candidates (✓ ✕) | profile (name, class, current version, @mention) · version · Expand, Lock, New version · open sets in the Catalogue · **Training** block · **Voice** block · candidate verbs · Delete | profile row · candidate card |
| **Shots** | shots grouped by Flow node · New shot | **New shot** + finalize state | name · version select · New version · Finalize · stale · Open in Stage · Open in Animate | shot board: versions, player, **takes** (✓ use) | shot (name, owner, current) · version fields · Finalize, New version, Open in Stage / Animate · **Lip-sync** block · Release, Delete | shot row only |
| **Flow** | node search · outline by type · variables | **Play ▶** / Stop | add ×9 node types · problems · Validate · Play · Fit | node graph (React Flow), or play mode (clip / frame / text, Next, choices, Restart, Stop) | validation list · or the node: type, title, per-type fields, **Lines**, **Options**, **Sets**, **Shot** binding, Duplicate, Delete | node · pane ("Add a node here", Validate, Play, Fit) · ⚠ edges have none |
| **Episode** | sequences (+) · **Shots bin** (+) · **Clips bin** (+, the drop target) | **Export ▶** (FCPXML) / New sequence | static text | preview canvas · transport (start, prev, play, next, end, undo, redo, zoom) · **lane** (scrub, blocks, trim handles, dissolve grip) | sequence (rename, delete) · checklist · export EDL / FCPXML / SRT / Render draft · selected clip (dissolve, earlier, later, open, remove) | clip block · empty lane |

### 9.2 Inventory

**World**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| Y1 | Logline · synopsis | editor | 1 | — | autosaves |
| Y2 | Add style / beat / variable | Panel Add; editor adders | 2 | `story.world.add*` | |
| Y3 | Edit style / beat | editor rows; Inspector | 2 | — | |
| Y4 | Edit a variable | editor row | 1 | — | ⚠ the Inspector is read-only for variables; a rename doesn't update Flow |
| Y5 | Default style | ★ on the row; Inspector select; Inspector button; row ctx | 4 | `story.world.defaultStyle` | read by Generate's style picker and by Cast's Expand |
| Y6 | Move beat earlier / later | ▲▼; Inspector; row ctx | 3 | `story.world.beatUp` / `.beatDown` · Ctrl+↑ / Ctrl+↓ | |
| Y7 | Make a Flow node from a beat | Inspector; row ctx | 2 | `story.world.beatToNode` | ⚠ the beat line goes into a field Shot nodes never show |
| Y8 | Remove style / beat / variable | row ✕; Inspector; row ctx | 3 | `story.world.remove` · Delete | ⚠ no confirmation; Delete fires on the Cast and Shots tabs too (§11.1) |

**Cast**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| Y9 | New character / place / prop | Panel; empty-state card (character); Catalogue C71 | 1–2 | `story.cast.new` / `.newPlace` / `.newProp` | ⚠ "New profile…" makes a character |
| Y10 | Filter, search, select a profile | Panel | 1 | — | |
| Y11 | View another version / set the current version | Strip select / Inspector select | 1 / 1 | — | ⚠ two selects that mean different things |
| Y12 | Rename · change class | Inspector | 1 | — | ⚠ sends a PATCH on every keystroke |
| Y13 | Prompt stub | Centre | 1 | — | |
| Y14 | **Expand** (coverage jobs) | Foot; Inspector; profile ctx; Bootstrap; Centre link | **5** | `story.cast.expand` · Ctrl+Enter | ⚠ always draft tier with a fixed model and 1 seed: a second t2i path beside Generate |
| Y15 | Pick candidates | click / Ctrl-click | 1 | — | |
| Y16 | Keep / Reject a candidate | card ✓ ✕; candidate ctx; Inspector | 3 | `story.cast.keep` · K / `.reject` · X | the kept references themselves are not shown in Story |
| Y17 | Make it the hero | candidate ctx; Inspector | 2 | `story.cast.setHero` | |
| Y18 | Lock version | Strip; Inspector; profile ctx; Bootstrap | 4 | `story.cast.lock` | |
| Y19 | New version (copy) | Strip; Inspector; profile ctx | 3 | `story.cast.newVersion` | ⚠ the same label as Y36 |
| Y20 | Open reference set / candidates in the Catalogue | Inspector; profile ctx; candidate ctx | 2–3 | `story.cast.openGroup` / `.openCandidates` | |
| Y21 | Delete profile | Inspector; profile ctx | 2 | `story.cast.delete` | |
| Y22 | Bootstrap chain | Strip | 1 | — | ⚠ disabled steps look clickable and do nothing |
| Y23 | Train a LoRA (base, steps, resolution, rank, name, staged) | Inspector › Training; Bootstrap "Train" | 2 | `story.cast.train` | |
| Y24 | Use the LoRA in Generate · Check identity · Delete LoRA | Inspector › Training | 1 each | `story.cast.useLora` / `.checkLora` / `.deleteLora` | Delete is also in Models (M10) |
| Y25 | Training job: release / resume / cancel | Inspector › Training | 1 | `story.cast.releaseTrain` / `.resumeTrain` / `.cancelTrain` | all three always shown, mostly disabled |
| Y26 | Assign a voice | Inspector › Voice | 1 | — | characters only |
| Y27 | New voice (Kokoro / Qwen3 cloning: clip, transcript, consent …) · Create | Inspector › Voice | 1 | `story.cast.newVoice` (toggles the form) | Create is not a command |
| Y28 | Delete voice | Inspector › Voice | 1 | `story.cast.deleteVoice` | ⚠ removes it from every character; no voice list anywhere |

**Shots**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| Y29 | New shot (empty) | Panel; Foot; empty-state card | 3 | `story.shot.new` | |
| Y30 | New shot from a Stage camera / an Animate clip / a Catalogue clip | S18, A31, C72 | 3 | — | three ways in from three suites |
| Y31 | Select a shot | Panel row | 1 | — | group headers show raw node ids |
| Y32 | View a version / set the current version | Strip select + version cards / Inspector select | 2 / 1 | — | |
| Y33 | Rename shot | Inspector | 1 | — | ⚠ a PATCH per keystroke |
| Y34 | Play the clip / show the frame | Centre player | 1 | — | |
| Y35 | Use a take | take card "✓ use" | 1 | — | no reject or delete for takes |
| Y36 | New version (copy) | Strip; Inspector; row ctx | 3 | `story.shot.newVersion` | |
| Y37 | Finalize | Strip; Inspector; row ctx | 3 | `story.shot.finalize` | ⚠ the same idea as Cast's "Lock" under another word |
| Y38 | Open in Stage / Open in Animate | Strip; Inspector; row ctx | 3 | `story.shot.openStage` / `.openAnimate` | the only way to make a frame or clip for a shot |
| Y39 | Release from its node | Inspector; row ctx | 2 | `story.shot.release` | the same as Flow's "Release the shot" (Y50), labelled differently |
| Y40 | Delete shot | Inspector; row ctx | 2 | `story.shot.delete` | |
| Y41 | Generate a frame or clip for a shot | — | 0 | — | not in Story: through Stage (S24, S28) or Animate |
| Y42 | Stale badge | Strip; version card; Inspector | 3 | — | advisory |
| Y43 | **Lip-sync ▶** (experimental, D88) | Inspector › Lip-sync block (open version only) | 1 | `story.shot.lipsync` | ⚠ the length check is hard-coded off; Extend lives in Animate (A27) |

**Flow**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| Y44 | Add a node (9 types) | Strip; pane ctx | 2 | `story.flow.add.*` | ⚠ "Add a node here" places the node in the wrong spot when the view is panned or zoomed |
| Y45 | Select · move · connect | canvas click / drag / handle drag; outline; problems list | 1–3 | — | gesture |
| Y46 | **Delete an edge** | — | **0** | — | ⚠ impossible (Delete key off, no edge ctx) |
| Y47 | Node type, title, note, jump, condition | Inspector | 1 | — | |
| Y48 | Dialogue lines: speaker, text, ▶ play, 🎙 voice one, voice all, fallback voice | Inspector › Lines; node ctx (voice all) | 1–2 | `story.flow.voiceAll` | voicing one line is not a command |
| Y49 | Choice options (label, requires) · Action sets | Inspector | 1 | — | ⚠ an option's `set` has no editor |
| Y50 | Bind a shot · New shot for this node · Open · Release | Inspector › Shot; node ctx | 1–2 | `story.flow.newShot` / `.openShot` / `.unbind` | binding is a select only |
| Y51 | Duplicate · Delete node | Inspector; node ctx | 2 | `story.flow.duplicate` / `.delete` | no Delete key, no Flow undo |
| Y52 | Validate | Strip; pane ctx | 2 | `story.flow.validate` | |
| Y53 | Play / Stop | Foot; Strip; pane ctx; play view | 3 | `story.flow.play` · P / `.stop` | ⚠ P doesn't work on the Flow tab; the Strip's Play ignores a missing Start node |
| Y54 | Play mode: Next, choices, Restart | Centre | 1 | — | voiced lines are not heard |
| Y55 | Fit · zoom · pan | Strip; pane ctx; React Flow controls; minimap | 2–3 | `story.flow.fit` · F | ⚠ F doesn't work on the Flow tab |

**Episode**

| # | Function | Homes today | n | Command · key | Notes |
| --- | --- | --- | --- | --- | --- |
| Y56 | New / open / rename / delete sequence | Panel +; Foot; Inspector; empty-lane ctx | 1–2 | `story.episode.new` / `.rename` / `.delete` | ⚠ the tab says "Episode", everything else says "sequence" |
| Y57 | Add a shot's clip (stamped) | Shots bin + | 1 | — | ⚠ uses the current version, not the final one |
| Y58 | Add a clip | Clips bin +; drop on the **Clips bin** | 2 | — | ⚠ the hint says "drag onto the lane", but the lane is not a drop target; a dragged shot card arrives unstamped |
| Y59 | Add Animate's current clip | empty-lane ctx | 1 | `story.episode.addCurrent` | ctx only |
| Y60 | Reorder | lane drag; Inspector Earlier / Later; clip ctx | 3 | `story.episode.moveLeft` / `.moveRight` | |
| Y61 | Trim in / out | lane edge handles | 1 | — | ⚠ drag only, with no fields |
| Y62 | Dissolve | Inspector; clip ctx; grip drag | 3 | `story.episode.dissolve` | the command toggles 12 frames ↔ 0 |
| Y63 | Open the clip in the player | Inspector; clip ctx | 2 | `story.episode.openClip` | ⚠ selects in Animate without switching suite |
| Y64 | Remove from sequence | Inspector; clip ctx | 2 | `story.episode.removeClip` | |
| Y65 | Undo / Redo | transport; ctx | 2 | `story.episode.undo` / `.redo` · Ctrl+Z | ⚠ the keys are not routed on Episode, but fire on World, Cast and Shots |
| Y66 | Play · step · start / end · scrub · zoom | transport; ruler; Ctrl+wheel | 1–2 | `story.episode.*` | no Space key; the preview has no sound |
| Y67 | Checklist | Inspector; Foot summary; export confirm | 3 | — | |
| Y68 | Export EDL / FCPXML + markers / SRT / Render draft | Inspector; empty-lane ctx; Foot (FCPXML only) | 2–3 | `story.episode.export*` / `.render` | the audio lane and markers have no in-app view |

## 10. Concepts that live in several suites

The sense of jumble comes less from any single suite than from the same idea being built several times, each time with its own
controls and words. This table is the starting point for deciding which suite **owns** each concept and which suites only link to it.

| # | Concept | Where it exists today | How the versions differ |
| --- | --- | --- | --- |
| X1 | **Make a still image** | Generate t2i (G36) · Generate New angle (G35) · Stage Shot (S24) · Story Cast Expand (Y14) and LoRA check (Y24) · Catalogue Re-run / Variations (C62, C63) · Edit AI (E73–E77) | Each has its own model picker, size, seed and candidate count. Expand uses a fixed model at draft size with 1 seed. Re-run and Variations overwrite Generate's panel. |
| X2 | **Change an existing image** (Refine, Inpaint, Outpaint, Upscale) | Edit › AI only; the Catalogue's Start cards route into it (C67, C68) | Generate cannot refine; its Size hint sends you to Edit. SD 3.5 exists only here. |
| X3 | **Make a clip** | Animate (A13) · Stage Clip "Animate ▶" (S28) · Animate Extend (A27) · Story Lip-sync (Y43) · Animate Variations / Re-run / Try other (A29) | Stage's IC-LoRA / Wan Animate clips land in Animate › Clips. The two experimental features sit in two suites (Extend in Animate, Lip-sync in Story). |
| X4 | **Reference images** | Generate slots (G14–G19) · Stage Shot deck (S22) · Animate start/end + beats (A1, A2, A7) · Story Cast reference sets, which are Catalogue groups (Y16, Y20) | The limits differ (per model / per method / fixed). Generate has notes and downscale; Stage has notes only. The drop rules differ. |
| X5 | **Run now vs "Stage" (queue for later)** | Generate Foot · Animate Foot · Edit AI · Story Train (staged by default) · Lip-sync (always staged) · Dock "Run now" | The same verb "Stage", not available everywhere, and released from different places. |
| X6 | **How many and which seed** | Generate count 1–8 + seed modes · Angle candidates 1–4 · Edit AI candidates 1–4 + seed · Stage candidates 1–4 · Animate clips 1–8 + seed modes · Expand: 1 | A slider, steppers and fields under three names: count, candidates, clips. |
| X7 | **Choose a model** | Generate cards · Animate cards · Edit AI per-operation selects · Angle method select · Stage method cards · Story (fixed, no picker) · text encoder in both Generate and Edit | Five different controls. |
| X8 | **Presets** | Generate panel presets (project) · Generate field presets (app-wide) · Animate panel presets (browser only) · Animate speed presets · Edit brush presets · Stage saved poses (project) | Six kinds, three storage scopes, one word. |
| X9 | **Judge a result** | Catalogue keep / reject / clear / rate (C29–C31) · Animate keep / reject, no clear (A28) · Cast keep = add to the reference set (Y16) · Story take "✓ use" (Y35) · Edit keep candidate N (E79) | Different verbs, meanings and keys (K vs Shift+K). |
| X10 | **Versions and sign-off** | Cast versions → **Lock** · Shot versions → **Finalize** · Stage revisions (autosave) · Edit history | Two words for the same sign-off idea. |
| X11 | **Timelines and transport** | Animate (`,` `.` I O J K L Space) · Stage (← → [ ] K Space) · Episode (buttons, no keys) · Flow play (Next ▸) | Four transports with different keys and controls. |
| X12 | **Lists of clips** | Animate › Clips · Episode Clips bin (the same data) · Catalogue (Type filter) · Story takes | Only the Catalogue can delete or filter clips. |
| X13 | **Missing weights → Fetch** | Generate Foot · Angle Foot · Animate estimate · Stage Shot text · TopBar chip · banner | Every one opens Models unfiltered (M1). |
| X14 | **LoRAs** | Generate LoRA slots (G27) · @mention auto-LoRA (G13) · Story Training (Y23–Y25) · Models Trained table (M10) | Delete exists in two places, and use is set in two places. |
| X15 | **Make a Story shot** | Story New shot (Y29) · Flow node (Y50) · Stage camera (S18) · Animate clip (A31) · Catalogue clip (C72) | Five entry points; Story itself cannot generate the shot's frame or clip (Y41). |
| X16 | **Where did this come from** | Catalogue lineage view + Inspector path (C55, C56) · Animate › lineage tab · Edit properties › AI recipe · Dock "Go to origin" (F24) | |
| X17 | **Send to another suite** | Catalogue → Edit, Generate, Animate, Story · Animate → Edit, Story, Catalogue · Story → Stage, Animate, Catalogue, Generate · Stage → Story · Models → Story | No common "Open in ▸" menu; each suite has its own labels. |
| X18 | **Results grid** | Catalogue (current strip) · Generate (the **old** Catalogue strip, §4.4) | Two generations of the same component. |

## 11. Findings

### 11.1 Bugs found while reading (fix whatever the reorganisation decides)

"Checked" means I confirmed it against the code for this document. "Reported" means a code read found it and it has not been reproduced.

| # | Bug | Where | Status |
| --- | --- | --- | --- |
| B1 | **Stage keys fire while you type.** The Stage key handler has no check for text fields, so typing in the Shot prompt, a note, a number field or a rename dialog switches tools, plays the timeline, and **Delete removes the selected object**. | `stage/StageParts.tsx:327` | checked |
| B2 | **Story keys ignore the open tab.** One key list serves World, Cast and Shots. Delete on Cast or Shots removes the World row still selected. P starts Flow play; Ctrl+Z undoes the Episode lane. Meanwhile P and F do nothing on Flow, and Ctrl+Z does nothing on Episode. | `story/StoryParts.tsx:433, 511, 569`; `storyCommands.ts:65` | checked |
| B3 | Flow edges cannot be deleted: the Delete key is turned off and edges have no menu. | `story/flow/FlowCanvas.tsx:93` | checked |
| B4 | Ctrl+Enter, Ctrl+Shift+Enter and ⌘K submit Generate while its button is disabled (empty prompt, missing weights, VRAM over), because the commands have no `when`. | `generate/GenerateSuite.tsx:462-463` | checked |
| B5 | Move to trash shows two toasts, each with its own Undo. | `catalogueCommands.ts:55`, `catalogueStore.ts:216` | checked |
| B6 | The lip-sync length check is hard-coded off (`too_long: false`), so lines over 4.8 s are offered. | `story/storyStore.ts:32` | checked |
| B7 | Episode: the drop target is the Clips bin in the Panel, not the lane its hint names. A dragged shot card arrives as an unstamped plain clip. | `episode/SequencePanel.tsx:25` | checked |
| B8 | Animate: Ctrl+Enter does nothing while the prompt has focus, though the button's tooltip advertises it. | `animate/AnimateSuite.tsx:261` | checked |
| B9 | Edit: the Crop / canvas tool has no canvas gesture. | `edit/EditorCanvas.tsx` (no `crop` branch) | checked |
| B10 | The loupe and compare show clips and audio through `<img>`. | `catalogue/Loupe.tsx:75, 140` | checked in code; the visible effect is not checked |
| B11 | Flow's "Add a node here" uses screen pixels as graph coordinates, so the node lands elsewhere once the view is panned or zoomed. | `flow/FlowCanvas.tsx:101`, `storyStore.ts:630` | reported |
| B12 | Generate: the negative prompt is hidden outside Tree mode but always sent. "Lead text" and the Text prompt are one value. A model change doesn't re-apply the tier size. A custom shift breaks Z-Image and Chroma. | `generateStore.ts:111`, `GenerateSuite.tsx:244` | reported |
| B13 | In Generate, the Inspector's breadcrumbs and "Unprocessed" link turn the results grid into an album page. | `catalogue/Inspector.tsx:108, 216` | reported |
| B14 | Story profile and shot names send a PATCH per keystroke with the revision, which risks 409 toasts and lost input. | `StoryParts.tsx:663, 706` | reported |
| B15 | Models › Trained › Show in Cast doesn't switch the Story rail to Cast. | `models/TrainedTable.tsx:27` | reported |
| B16 | Shift+F10 in the Catalogue grid opens the empty-grid menu, never the selected tile's menu. | `frame/useKeyboardMap.ts:12` | reported |
| B17 | `cat.toUnprocessed` is enabled only on a page, while the Inspector offers the same action everywhere. | `catalogueCommands.ts:73`, `Inspector.tsx:219` | reported |
| B18 | Hovering Edit's candidate strip changes layer visibility, which edits the document. | `edit/EditSuite.tsx:495` | reported |
| B19 | World "Make a Flow node from this beat" puts the beat line in a field Shot nodes never show. | `storyStore.ts:696` | reported |

### 11.2 Functions without a mouse home, or outside the command registry (D32)

**Key or palette only:**

- `cat.groupCycle` (G): the only way *into* grouping in the Catalogue.
- `anim.shuttle*` (J K L).
- `edit.brush.opacity.*` (0–9).
- `edit.cand.keep` (Enter).
- `global.contextMenu`, by design.

**Gesture or drag only:**

- Stage: image plane, shot references, IK handles, renaming objects and cameras.
- Episode: trim and dissolve length.
- Flow: connecting nodes.
- Catalogue: resizing panes.
- Animate: reusing a clip's start or end frame.

**Whole areas with no commands** (not in ⌘K, Help or Settings › Keyboard):

- Models (all of it).
- Edit's AI runs (Select ▶, AI ▶, Stage, Re-run new seed).
- Edit: Resize canvas, nudge, brush presets, documents.
- Generate: every form field, Load in Generate.
- Story: take "use", voice one line, the bins' +, bind shot, play-mode controls.

**Help's gesture list** covers only the Catalogue, Generate and Edit. **Settings › Keyboard** and the `commandAudit` test leave out Stage and
Story, so neither suite's keys can be remapped or conflict-checked.

### 11.3 Declared placements that are not rendered

Every command declares where it can be clicked (`placement`). Roughly 55 declarations name a home that does not exist. The dev audit can't
see this for two reasons: it checks only that a command was rendered *somewhere*, and Story and Stage mark their commands used by hand.

| Suite | Commands with a declared home that isn't there |
| --- | --- |
| Catalogue | `closeLoupe` (ctx), `prev` / `next` (ctx), `rate.*` (Inspector: the stars are plain buttons), `start.shot` (Inspector), `groupCycle` (strip, ctx) |
| Generate | `clearRefs` (panel) |
| Edit | `layer.newGroup` (ctx), `brush.pick` (ctx), `sel.magBack` (strip), `transform` (strip), the 7 clipboard commands (panel), `cand.*` (strip), `brush.opacity.*` (panel), `view.before` (strip: the button holds, the command toggles), `mask.apply` / `layer.lockAlpha` / `layer.inkFromWhite` (panel) |
| Animate | `clearStart` / `clearEnd` (rendered nowhere), `shuttle*` (ctx), `toShot` (Inspector, ctx), `identity` (ctx) |
| Stage | `new` / `rename` / `delete` / `camera.setFromView` / `camera.toShot` (ctx), `camera.delete` / `anim.keyObject` (Inspector), `shot.clearRefs` (rendered nowhere) |
| Story | `world.add*` ×3, `cast.new*` ×3, `cast.useLora` / `checkLora` / `deleteLora`, `shot.new`, `shot.lipsync`, `episode.new` (all ctx) · `cast.keep` / `reject` (toolbar) · `cast.train` (panel, ctx) · `episode.addCurrent` (panel) |

### 11.4 Duplication hotspots (five or more homes)

| Homes | Functions |
| --- | --- |
| 8+ | Open a group page (C5) |
| 6 | Use as reference (C61) · Animate from this frame (C65) · Open in loupe (C48) · Duplicate layer (E45) · Apply transform (E66) |
| 5 | Open Unprocessed (C1) · Open in other pane (C6) · Duplicate assets (C37) · New group (C38, 4 labels) · Variations (C63, doubled in the same menu) · Move to trash (C74) · Cancel transform (E66) · Select layer transparency (E31) · Load mask as selection (E37) · Expand (Y14) |

Edit also shows its mask options in both Inspector tabs, and its colour swatches three times.

### 11.5 One word, several meanings

| Word | Meanings today |
| --- | --- |
| **Stage** | the 3D suite · the frame's centre region · the "queue, run later" button (Generate, Animate, Edit AI) |
| **Shot** | the Stage suite's Shot tab and its generated stills · a Story shot (with versions and takes) · "Make a shot from this clip" |
| **Animate** | the suite · Stage's "Animate ▶" (IC-LoRA / Wan Animate) · the Catalogue's "Animate ▾" verbs |
| **Preset** | the six kinds in X8 · Animate's draft / motion / quality |
| **Refine** | AI Refine (i2i) · Refine edge (selection) · tiled refine (Upscale) |
| **Remove** | AI Inpaint "Remove" · "Quick remove · CPU" · "Remove background" (only selects) · Remove mask · Remove reference / filter / beat … |
| **Fill** | the Fill / gradient tool · a layer's fill opacity · Inpaint "Fill / Fill-Match / Fill Hero" |
| **Feather** | the selection modify step · the marquee / lasso option · the mask property · the AI option · the AI blend mode |
| **Release** | un-stage a job (Dock "Run now", Story training) · unbind a shot from a Flow node, under two labels |
| **Keep** | judge an asset · add a candidate to a reference set (Cast) · keep an AI candidate (Edit) |
| **Lock / Finalize** | the same sign-off for Cast versions and Shot versions |
| **Episode / Sequence** | the tab is Episode; the Panel, commands and toasts say sequence |
| **Style** | a Story world style (Generate's style picker) · the Tree prompt's "style" field |
| **Compare** | the Catalogue's A/B compare · Animate's compare view · Edit's "Compare preview with the exact flatten" |
| **Count** | count (Generate) · candidates (Angle, Edit, Stage) · clips (Animate, also a rail tab) |

### 11.6 Dead, hidden and developer-facing UI

**Dead or permanently disabled:**

- Generate's "Upsample ✨ (later)".
- Animate's H3 card, even with the licence confirmed.
- "coming in M5" on Generate model cards.
- The promise of pen-pressure controls in Edit.
- The Catalogue's "This page is empty" branch.
- The Lineage filter chip, which no UI sets.
- The Trash branch in Generate's strip.
- The stale `DEFAULT_RAIL.generate`.

**Developer-facing UI in user places:**

- ☰ › M0 spike harness.
- Edit's "Compare preview with the exact flatten", the renderer badge, and the memory and id rows in Info.
- Spec references in Story's visible text: "(SY3)", "R146", "18 §3d", "D27", "CN2".

**Hidden scopes:**

- Animate's "Show in Catalogue" opens a `clips` folder that no Places row shows, no chip names and "Clear filters" doesn't reset. The old
  folders today, last_session, images, imported and rejected survive the same way.
- Models shows a count of unlisted files but never lists them.

### 11.7 Keys that change meaning between suites

| Key | Meanings |
| --- | --- |
| K / Shift+K | Catalogue: keep · Animate: shuttle stop / keep · Stage: key camera / key object · Cast: keep |
| L | Catalogue: lineage · Animate: shuttle forward · Stage: lock · Edit: lasso |
| C | Catalogue: pin · Animate: compare · Stage: camera view · Edit: crop |
| F | Catalogue: search · Animate: extract frame · Stage: frame selection · Flow: fit (not working there) |
| E | Catalogue: open in Edit · Animate: send to Edit · Edit: eraser |
| Home | Animate: first frame · Stage: frame everything |
| Ctrl+D | Catalogue and Stage: duplicate · Edit: deselect |
| Ctrl+1 / Ctrl+2 | global suite switch · Catalogue loupe: 1:1 · Edit (document open): zoom 100 % / 200 % |
| Delete | Catalogue grid: trash · Catalogue page: back to Unprocessed · Edit: clear pixels (not delete layer) · Stage: delete object · Story: remove a World row (on any tab, B2) |
| Ctrl+Enter | the primary action in Generate, Animate, Stage (Shot) and Cast (Expand) — but not in Edit AI, Flow, Episode or Shots |
| Frame step | Animate `,` `.` · Stage ← → · Episode: buttons only |

## 12. Using this for the reorganisation

What I suggest, following the Catalogue pass (proto01_design/01), which worked:

1. **Fix the vocabulary first (§11.5).** One word per concept. Most of the "jumbled" feeling comes from the same word naming different
   things in neighbouring places.
2. **Give each cross-suite concept (§10) one owner.** The other suites link to the owner with an "Open in ▸" entry rather than rebuilding
   the controls.
3. **Give every row one home.** Write a `02-…` document with a "→ New home" column keyed by the ids above (F1…Y68). Allow one visible
   home plus the ctx and a key, as D32 and proto01_design/01 §1 already require. That is a change of direction, so it needs a D-number in
   13 before the work.
4. **Make the rule checkable.** Every action becomes a command (§11.2). The dev audit and `commandAudit.test.ts` should check *declared*
   placements against what is rendered and include Stage and Story (§11.3, §11.7). Then the next round of features can't quietly undo the
   reorganisation.

Questions only the author can answer, which decide most of the layout:

- Should Generate's results simply *be* the Catalogue (one results view, X18), or keep a Generate-only grid?
- Should Refine, Inpaint, Outpaint and Upscale stay in Edit only (X2), or also be reachable from a result in Generate or the Catalogue?
- Should a Story shot be able to make its own frame and clip (X15), or stay a hub that sends you to Stage and Animate?
- Should Extend and Lip-sync, both experimental, live together, and where (X3)?
- Should Animate › Clips and the Episode clips bin become one list (X12)?
- Should LoRA management live in Story › Cast, in Models, or both (X14)?
- Suite order and keys: should the tabs follow the work (Story → Stage → Generate → Edit → Animate → Episode?), and should Ctrl+1…7 follow the
  tab order (today Models is Ctrl+5 but last)?
