# 01 · Catalogue — functional inventory and placement

Status: **implemented 2026-10-07** (slices 1–7 of §13; the Generate pass, slice 8, and the later items of slice 9 are open). The author's
decisions of the same day are applied (§11, §12). First
of the design passes over the shipped MVP UI (Catalogue first, the other suites after). Source of truth for "today": the code at
`4e0db08`: `frontend/src/suites/catalogue/` (`CatalogueSuite.tsx`, `catalogueCommands.ts`, `catalogueStore.ts`, `Loupe.tsx`,
`Tile.tsx`), `frontend/src/frame/`, `orchestrator/loom2/catalogue.py`. Specs it revises: [08](../proto01/08-ui-suite-catalogue.md),
[07](../proto01/07-ui-frame.md) §2–§3. Decision: D34 in [13](../proto01/13-decision-log-and-open-questions.md).
Mockups (Claude Design canvas, private to the author): https://claude.ai/artifact/LHE9qZknAZddiPhPfpRJiM — sorting layout,
two groups side by side, strip slots, Inspector states, lineage view.

**Shared parts:** the Catalogue's Strip, Stage and Inspector are also Generate's results view (`GenerateSuite.tsx:14`, `:466`, the
same components on a second store). Every change below lands in Generate too unless it is scoped to the Catalogue on purpose (§9).

## 1. Why

The functions are right; their placement is not. Most functions have three to six visible homes, the left panel holds four
tabs for what is essentially one query, the strip changes shape when something is selected, and the two things that would
make the Catalogue more than a grid (organising assets, seeing lineage) have no real surface. This document lists every
function, where it lives today, and gives it **one** visible home (§6). The right-click menu and a key are the only allowed
extra routes, as D32 already requires.

The author's direction (§11, §12): the generated items are the centre of everything, handled like photos in an album.
Every new item lands in **Unprocessed**. From there it is dragged onto a page and arranged freely; each arrangement is a
**group**; a collapsed group is dragged onto another page like a photo, and so on. An item lives in **one** place at a time
(a duplicate is made when it is wanted in two). Groups are the **only** organising structure; everything the current group-by
modes and smart collections did is done with filters. The Stage can **split** to show two places at once (two groups, or a
group and Unprocessed) and items are dragged between them.

## 2. What is on screen today

| Region | Contents now |
| --- | --- |
| **Rail** | 4 tabs: Library · Filters · Collections · Import (+ the global toggles) |
| **Panel · Library** | 9 smart folders with counts (All, Today, Last session, Images, Clips, Documents, Imported, Rejected, Trash); *Empty trash* when in Trash; a **Collections** list (drop target) + "+ new collection" |
| **Panel · Filters** | Search, State (all/none/keep/reject), Suite, Model, Rating ≥, Aspect, Children, Created (two date inputs), Tags (cloud of 24), *Clear filters*, *Save as smart collection* — in an 84 px label grid |
| **Panel · Collections** | the same collection list again, with ✎ rename, ◈→▣ convert, ✕ delete (two-step) |
| **Panel · Import** | path textarea, Files…, Folder…, Import, drop zone, help line |
| **Panel foot** | "Import files…" — switches the rail to the Import tab (`CatalogueSuite.tsx:451`) |
| **Strip, nothing selected** | group ▾, expand/collapse all, all/keep/reject, sort ▾, read-only filter chips, "N assets", ⊖ zoom slider ⊕, fit/fill |
| **Strip, selection** | the above **plus** ▣ N, 11 command icons (keep, reject, clear, loupe, edit, reference, pin, select all, clear selection), tag input, "+ collection" select, trash (or restore / purge / empty trash), "Compare N", unpin all — inserted between the spacer and the zoom |
| **Stage** | virtualised grid; group header = ▸ + 28×20 px cover + "Batch 1a2b3c4d" + model + prompt excerpt + count + full date-time |
| **Loupe / Compare** | their own bottom bar (prev/next, facts, fit, 1:1, pin, keep, reject, edit, reference, close), **under the grid Strip, which stays** |
| **Inspector** | 4 tabs: Info (thumb, id, kind, size, created, model, seed, some params, time, keep/reject, stars, tag chips, 9 verb buttons) · Params (prompt JSON, every param, graph/job/session ids, Copy prompt, Load into Panel, All → Re-run) · Lineage (parents and children, one level, as ids) · Tags (input, chips, recent tags) |
| **Right-click** | tile / loupe (17 entries), empty grid (8), group header (5) |

## 3. Inventory

**Count** = visible homes today (excluding keys and the `Ctrl+K` palette). **→** = new home (detail in §6). *ctx* = right-click
menu. Rows in **bold** are the worst duplications or gaps. *Pane* = one half of the Stage when it is split (§6c).

### A. Scope — which assets are shown

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| A1 | All / Today / Last session | Library folders | 1 | All = **Library** (Places); Today, Last session = presets of the **Date** chip |
| A2 | Kind: Images / Clips / Documents | Library folders (`kind`, `has_document`) | 1 | **Type** chip |
| A3 | Imported | Library folder; Filters · Suite = import (same set) | 2 | **Source** chip (Imported is one value) |
| **A4** | **Rejected** | **Library folder; Strip all/keep/reject; Filters · State** | **3** | **State** chip only |
| A5 | State all/none/keep/reject | Strip (3 values, no "none"); Filters (4 values); same `q.state` | 2 | State chip |
| A6 | Search | Filters tab only (`F` opens the panel on it) | 1 | query bar search field (always visible) |
| A7 | Source suite | Filters | 1 | Source chip |
| A8 | Model | Filters | 1 | Model chip |
| A9 | Rating ≥ | Filters | 1 | Rating chip |
| A10 | Aspect | Filters | 1 | "More ▸" in the Filter menu |
| A11 | Has derivations | Filters | 1 | "More ▸" |
| A12 | Created date range | Filters (two native date inputs, side by side) | 1 | Date chip (Today, Last session, 7 days, 30 days, range…) |
| A13 | Tags (any) | Filters tag cloud (top 24) | 1 | Tags chip (autocomplete) |
| **A14** | **Active filter chips** | **Strip, read-only: one cannot be removed on its own** | 1 | the chips *are* the filters: click = edit, ✕ = remove |
| A15 | Clear filters | Filters tab; empty-grid state | 2 | query bar ✕ (when any chip); empty-grid state |
| **A16** | **Lineage root scope** (`root_id`) | **set by Inspector · Lineage "Show as tree"; no chip; cleared only by "All roots" in that tab** | 1 hidden | replaced by the Lineage view (G6); never a hidden filter |
| A17 | Open a collection | Library list; Collections tab | 2 | Places · group tree → opens the group's page in the active pane |
| A18 | Trash | Library folder | 1 | Places: Trash (bottom of the panel) |
| A19 | Batch / session scope | Generate only (`batch_id`, `session_id` in the query) | — | **Batch** chip, set by tile *ctx* "Show this batch"; session = Date chip preset |

### B. Organise

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| B1 | New collection | Library "+ new collection" | 1 | **New group**: select items on a page → *Group* (Inspector button, page *ctx*, `Ctrl+G`); "+" on the Places tree; tile *ctx* "Move to group ▸ New group…" |
| B2 | Save filters as smart collection | Filters tab | 1 | **removed** (one group type, §11 #3) |
| B3 | Rename / delete / convert | Collections tab only | 1 | rename, ungroup, delete, set cover, duplicate: *ctx* on the card or tree entry; Inspector when the group is selected. Convert removed |
| **B4** | **Add to collection** | **drag onto Library entry; Strip "+ collection" select. Not in *ctx*, not in the Inspector** | 2 | **move**: drag onto a page (either pane), a card or a tree entry; tile *ctx* "Move to group ▸"; Inspector · Location |
| **B5** | **Remove from collection** | **API exists (`POST /collections/{cid}/assets/remove`), no UI** | 0 | on a page: *ctx* "Back to Unprocessed" / `Del`; drag into the Unprocessed pane |
| **B6** | **Order inside a collection** | **none (`collection_assets` has no position)** | 0 | free position, size and stacking on the page (§6c) |
| **B7** | **Album layout, nesting** | **none** | 0 | pages, cards, groups inside groups (§6c) |
| B8 | Duplicate (new) | none | — | tile / card *ctx* "Duplicate"; Inspector · Actions; `Ctrl+D`. The copy appears next to the original (§12 a) |
| B9 | Inbox of new items (new) | none (Today / Last session only approximated it) | — | **Unprocessed** (Places, top): every new generation, edit render, clip, extracted frame and import lands here (§12 e) |

### C. View

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| C1 | Group mode (Batch, Lineage, Session, Model, None) | Strip select; grid *ctx*; header *ctx*; `G` | 2 | **removed**: Batch chip (A19), Date chip, Model chip, Lineage view (G6) |
| C2 | Expand / collapse all | Strip icons (grouped only); grid *ctx*; header *ctx* | 2 | **removed** (no sections in the grids) |
| C3 | Expand / collapse one | header click; header *ctx* | 1 | **removed**; a card opens as a page (double-click) |
| C4 | Sort | Strip select | 1 | Strip · Sort ▾ (fixed slot); applies to grid panes |
| C5 | Count | Strip text | 1 | Strip, next to the query (fixed slot) |
| C6 | Tile size / page zoom | Strip ⊖ slider ⊕; `[` `]` | 1 | Strip right end (kept), for the active pane: tile size in a grid, zoom + Fit on a page |
| C7 | Fit / fill thumbnails | Strip text toggle | 1 | **Settings · Catalogue only** (§11 #6) |
| C8 | Tile caption (model · seed) | fixed on every tile | 1 | Settings · Catalogue: **off by default** (§11 #7), prompt, model · seed |
| C9 | Badges (state, clip, doc, derived, stars, pin) | tile | 1 | tile (kept); the ⤷ badge becomes a button (G6) |
| C10 | Split Stage (new) | none | — | Strip · Split ▾ (single / side by side / stacked); Places entry and card *ctx* "Open in other pane"; drag a tree entry onto a pane (§12 e) |

### D. Selection

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| D1 | Click / Ctrl / Shift / arrows | Stage | 1 | kept in grids; on a page click / Ctrl / marquee (arrows nudge) |
| D2 | Select all / clear | Strip bar; grid *ctx*; `Ctrl+A` / `Esc` | 2 | Strip selection chip (✕ clears); grid and page *ctx* (select all) |
| D3 | Selection count | Strip "▣ N" | 1 | Strip selection chip (fixed slot) |
| D4 | Marquee on empty space | promised in 07 §3b, **not built** | 0 | grids and pages — essential on pages |
| D5 | Select a group | none | 0 | click its card |

### E. Judge

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| **E1** | **Keep / Reject / Clear** | **Strip bar; Inspector Info; tile *ctx*; loupe bar** | **4** | Inspector · Judge; *ctx*; loupe bar (focus mode hides the Inspector) |
| E2 | Rate | Inspector stars; *ctx* Rate ▸ | 2 | Inspector · Judge; *ctx* |
| **E3** | **Add tag** | **Strip tag input; Inspector · Tags tab; `T` focuses `#insp-tag`, which exists only on the Tags tab** | 2 (+broken) | Inspector · Tags section (always rendered); *ctx* Tag… |
| E4 | Remove tag | Inspector Info chips ✕; Tags tab chips ✕ | 2 | Inspector · Tags section |
| E5 | Recent tags | Tags tab list; Filters tag cloud (same data) | 2 | autocomplete of the tag field; Tags filter chip |

### F. Look and compare

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| F1 | Open loupe | double-click; Strip icon; Inspector verb; *ctx*; `Enter` | 3 | double-click (a tile; on a card it opens the page); Inspector · Actions; *ctx* |
| F2 | Loupe prev / next / fit / 1:1 / close | loupe bar | 1 | loupe bar (kept) |
| **F3** | **Pin for compare** | **Strip icon; Inspector verb; *ctx*; loupe button (hand-rolled, not the command)** | **4** | Inspector · Actions; *ctx*; loupe bar (as the command) |
| F4 | Open compare | Strip "Compare N"; *ctx* | 2 | Strip · **Compare tray** chip (fixed slot, pinned thumbs + Open) |
| F5 | Unpin all | Strip; grid *ctx*; compare bar | 3 | Compare tray ✕; compare bar |
| F6 | Wipe / difference / 2–4 up / swap | compare bar | 1 | kept. Image *Compare* (pixels, locked zoom) stays distinct from the *Split* Stage (places side by side) |
| **F7** | **Grid Strip stays above the loupe and compare** | sort, zoom, filters do nothing there | — | loupe / compare **replace** the Strip with their own bar |

### G. Route to other suites, and lineage

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| G1 | Open in Edit | Strip; Inspector; *ctx*; loupe bar; drag to the Edit tab | 4 | Inspector · Actions; *ctx*; loupe bar; drag (kept) |
| G2 | Animate start / end | Inspector; *ctx*; drag to the Animate tab (`cat.animate` declares `strip` but the strip does not render it) | 2 | Inspector · Actions ("Animate ▸ start / end"); *ctx* |
| G3 | Use as reference | Strip; Inspector; *ctx*; loupe bar; drag to Generate | 4 | Inspector · Actions; *ctx*; loupe bar; drag |
| **G4** | **Re-run** | **Inspector Info verb; Inspector Params "All → Re-run"; *ctx*** | **3 (2 in one panel)** | Inspector · Actions; *ctx* |
| G5 | Variations; Load into Generate; Copy prompt; Reveal | Inspector (verbs / Params); *ctx* (some) | 1–2 | Inspector · Actions (primary row + "⋯" for Reveal, Copy prompt); *ctx* |
| **G6** | **See an asset's lineage** | **⤷ badge (not clickable); Inspector Lineage tab, one level, ids; group-by Lineage = the same flat tile rows as Batch; `GET /lineage/tree/{root}` exists and nothing calls it** | — | **Lineage view** in a pane (§6c) + Inspector · Lineage path (§6e) |

### H. Delete

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| H1 | Move to trash | Strip; Inspector verb; *ctx*; `Del` | 3 | Inspector · Actions "⋯"; *ctx*; `Del` in a grid (on a page `Del` sends the item back to Unprocessed) |
| H2 | Restore | Strip (in Trash); Inspector; *ctx* | 3 | Inspector; *ctx* — back to its former place if that group still exists, else Unprocessed |
| H3 | Delete permanently | Strip; *ctx* | 2 | Inspector (in Trash); *ctx* |
| **H4** | **Empty trash** | **Library button; Strip button; *ctx* / palette entry that only shows a toast saying "use the button"** | 3 (one dead end) | the Trash view's empty-state / header button; *ctx* on Places · Trash; the command runs the two-step itself |

### I. Information about an asset

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| **I1** | **Model / seed / size / time** | **tile caption; tile tooltip; loupe bar; Inspector Info; compare cell tag** | **5** | Inspector (full); tile tooltip (glance); loupe bar (while looking). Caption off by default |
| I2 | Steps, guidance, … | Inspector Info (subset); Params (all) | 2 | Inspector · Details (one table) |
| I3 | Prompt | Params (pretty-printed raw JSON); group header excerpt | 2 | Inspector · Prompt section (scene first, JSON on demand) |
| **I4** | **Ids (asset, job, session, graph hash)** | **Inspector Info's first row; lineage rows; group labels "Batch 1a2b3c4d"** | 3 | Inspector · Details only, with copy buttons. Never as a label |

### J. Import

| # | Function | Today | Count | → New home |
| --- | --- | --- | --- | --- |
| **J1** | **Import files / folder** | **Rail Import tab (textarea + Files… + Folder… + Import); panel foot "Import files…" (only switches tabs)** | 2 | Strip · **Import** button (split: Files… / Folder… / Paths…), opens the OS picker directly; grid *ctx*; empty state. Imports land in Unprocessed |
| J2 | Drop to import | only the Import tab's drop zone, and only as text paths to confirm | 1 | drop anywhere on a pane (dropped on a page, the imports are placed there instead of Unprocessed) |
| J3 | Paste paths | Import tab textarea | 1 | "Import ▾ → Paths…" (AskDialog), for the browser dev build |

### Duplication in numbers

69 rows describe today's functions (B8, B9 and C10 are new); **30 have two or more visible homes today**, 5 have four or more
(keep / reject, pin, Edit, reference, model · seed · size); 5 needed functions have **no home** (B5, B6, B7, D4, D5) and two exist
only in a weak form (lineage, G6; drop-to-import, J2). After the change every row has one visible home plus, where it acts on an
object, that object's right-click menu.

## 4. The author's points, traced

| Point | Cause | Resolution |
| --- | --- | --- |
| 1a Library = filters by time, type, action | 9 folders mix a place (All, Trash) with conditions (Today, Images, Rejected, …) | Places hold only places: Unprocessed, Library, the group tree, Trash (§6a); every condition becomes a chip |
| 1b Filters overflow, too many types | 12 controls in a 296 px column (320 px panel − padding), label column 84 px + 12 px gap; the side-by-side native date inputs are the likely overflow (not measured) | filters leave the panel: one query bar over the full Stage width, chips added only when used (§6b) |
| 1c Collections in a cramped separate tab | the list exists twice (Library, Collections tab), management only in the tab | groups: a tree in Places, each opens as a full-Stage page, two at once in a split (§6c) |
| 1d Import tab + foot button | a whole tab for one action; the foot button only switches to that tab | one Import button in the Strip + drop on any pane (J1–J3) |
| 2a fit/fill, all/keep/reject, grouping | fit/fill sits among query controls; the state segment duplicates A4/A5; group-by modes are filters in disguise | fit/fill → Settings; state → chip; group-by modes → chips and the Lineage view; groups = album pages |
| 2b Selected strip is busy and shifts | selection inserts ~16 controls; conditional chips, "Compare N" and "Unpin all" change widths | fixed slots, selection = one chip; actions live in the Inspector (§6b, §6e) |
| 2c Grid fine, but no room to organise | collections are only filters; no order, layout or nesting | Unprocessed → album pages with free arrangement and nested groups, split Stage to work between two places (§6c) |
| 2d Group header | 28×20 px cover, id fragment as title, full date-time with seconds | group headers disappear with the group-by modes; a group is a **card** with a real cover and its name (§6c) |
| 2e Lineage obscured | Inspector shows one level as ids; the tree endpoint is unused; group-by Lineage draws no tree | Lineage view + ancestry path in the Inspector (§6c, §6e) |

## 5. Placement rules

- **R1. One visible home per function.** Its object's right-click menu and a key are the only extra routes (D32). The palette
  follows from the registry.
- **R2. The left panel holds places, the strip holds conditions.** A place is somewhere you go back to (Unprocessed, the
  Library, a group, Trash). A condition narrows what you see (state, type, date, model, rating, batch). Conditions never get
  their own panel.
- **R3. One organising structure: the group.** Groups are made by hand, arranged by hand and nest. Anything computed
  (batch, day, model, lineage, "4★ keepers") is a filter or a view, never a stored grouping.
- **R4. An item lives in one place.** Unprocessed or exactly one group. Dragging moves it; *Duplicate* makes a second item.
- **R5. The strip has fixed slots** and serves the **active pane**. Every control sits in the same position with or without a
  selection; a slot that is empty stays reserved. Selection changes the content of one chip, never the layout.
- **R6. Actions on assets live in the Inspector** (single and bulk) **and the object's menu.** The strip carries no per-asset
  actions.
- **R7. Information once in full, once at a glance.** Full in the Inspector; at a glance in the tooltip (and the caption, if the
  user turns it on in Settings). Ids only under Details.
- **R8. Loupe, Compare and the Lineage view replace the strip** with their own bar; they do not stack under it.
- **R9. View preferences that are set once live in Settings**, not in the working surface (fit / fill, caption).

## 6. Proposed placement

### 6a. Rail and Panel — "Places"

The rail keeps **one** Catalogue tab (Places); the frame's global toggles stay. The Panel can narrow to ~220 px.

```
PLACES
  Unprocessed                38
  Library                 4 213
ALBUM                         +
  ▾ Act 1                    24
      Alley                   9
      Throne room             8
  ▸ Characters               31
  ▸ Hero shots               12
──────────────
  Trash                      14
```

- **Unprocessed** is the inbox: every new item (generations, Edit renders, clips, extracted frames, imports) lands here and
  stays until it is placed in a group or trashed. It is a grid, newest first, with the query bar.
- **Library** is every asset in the project wherever it lives: the search-everything grid. The Inspector shows where each one is.
- **Album** is the group tree. "Album" itself is the root page; its children are the top-level groups. Click opens a group in
  the active pane; drop tiles or cards on an entry to move them into that group; drag an entry onto another to move the group
  there; drag an entry onto a pane to open it there.
- Right-click on an entry: open, open in other pane, rename, set cover, duplicate, ungroup, delete (with Undo).
- Removed from the panel: every smart folder except Library and Trash (→ chips), the Filters, Collections and Import tabs, the
  foot button, the Empty-trash button (→ the Trash view).

### 6b. Strip — query bar + view, fixed slots, for the active pane

```
grid pane active:
[Unprocessed         ][🔍 alley  (State: keep ✕) (Date: today ✕) + Filter][✕] 38 │ Sort: newest ▾ │ [ selection ] [ compare ] │ Split ▾ │ Import ▾ │ ⊖━━●━━⊕
page pane active:
[Album › Act 1 › Alley][🔍 alley  (State: keep ✕) + Filter][✕]  9 │ Sort: newest ▾ │ [ selection ] [ compare ] │ Split ▾ │ Import ▾ │ ⊖━━●━━⊕ Fit
```

| Slot | Contents | Notes |
| --- | --- | --- |
| Place | the active pane's place: "Unprocessed", "Library", "Trash" (+ Empty trash), or a page's breadcrumb (each crumb opens that page) | when the panel is collapsed, click = the Places tree as a menu |
| Query | search field, active filter chips, "+ Filter" menu (State, Type, Source, Model, Rating, Date, Tags, Batch, More ▸ aspect / derivations), ✕ clear | in a grid pane it filters; on a page it **highlights** matches (the rest dims), never hides or moves anything; chips beyond the width fold into "+N"; the strip may wrap to two rows (07 §2 allows two) |
| Count | total for the query in the active pane | |
| Sort | one compact dropdown | grid panes only (disabled on a page) |
| **Selection** | empty, or "3 selected ✕" | reserved width; ✕ clears |
| **Compare tray** | empty, or up to 4 pinned mini-thumbs + "Compare" | reserved width; ✕ unpins all |
| Split | single / side by side / stacked, swap panes | |
| Import | split button: Files… / Folder… / Paths… | lands in Unprocessed |
| Zoom | ⊖ slider ⊕ — tile size in a grid pane, page zoom + Fit on a page | |

Each pane remembers its own place, query, sort and zoom; the strip shows the active pane's (the one last clicked, outlined).
The strip spans the **full width right of the rail**, above Places, the Stage and the Inspector (a change to 07 §2, to be
confirmed in the other suites' passes): at 1440 px every slot fits in one row; narrower windows wrap to two rows.
Not in the strip any more: group ▾, expand / collapse, the state segment, fit / fill, the selection icons, tag input,
"+ collection".

### 6c. Stage — grids, album pages, split

**Terms**

| Term | Meaning |
| --- | --- |
| Unprocessed | the inbox grid: every item not yet placed in a group (and not trashed) |
| Library | every asset of the project, wherever it lives; a grid for searching |
| Group | a named, hand-made arrangement of items; an item is an asset or another group |
| Page | a group opened in a pane: an endless canvas where its items sit at free positions, sizes and stacking order |
| Card | a group shown collapsed on its parent's page: a cover, its name and count; dragged, resized and stacked like a photo |
| Album | the project's root page; the top-level groups sit on it as cards |
| Pane | one half of a split Stage; it shows any place: a page, Unprocessed, Library, Trash, a lineage tree |

**Grid panes** (Unprocessed, Library, Trash) keep what works today (virtualisation, keyboard by row, zoom) but are flat: no group
headers. Captions off by default. Tile right-click adds "Show this batch" (sets the Batch chip), "Move to group ▸", "Duplicate",
"Show lineage".

**Split Stage**

```
┌ Album › Act 1 ───────────────────────────────────────────────── ⋯ ┐   ← pane header (place, ⋯ = swap / close / open elsewhere)
│   ┌──────────┐   ┌────────┐                 ╔═══════════╗          │
│   │  photo   │   │ photo  │    ┌──────┐     ║ ▓▓ ▓▓ ▓▓  ║ ← card   │
│   └──────────┘   └────────┘    │photo │     ║ Alley · 9 ║          │
│                ┌─────────────────────┐      ╚═══════════╝          │
│                │     photo (large)   │                              │
│                └─────────────────────┘                              │
├ Unprocessed · 38 ═══════════════════════════════════ (drag to resize) ⋯ ┤
│  ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢    │
│  ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢ ▢                                        │
└─────────────────────────────────────────────────────────────────────┘
```

- **Single** (default), **stacked** (a page above Unprocessed: the everyday sorting layout) or **side by side** (two groups, or a
  group and Unprocessed, to compare and move items between them). The divider is draggable; the layout is remembered per project.
- Dragging between panes **moves** items (R4); `Ctrl`+drag duplicates.
- Each pane has a thin header (its place and a ⋯ menu: swap, close this pane, open the other place here). The panes share one
  selection model and one Inspector (07 §3b); the Inspector follows the last selection.

**A page**

| Action (mouse first) | How | Also |
| --- | --- | --- |
| Place an item | drag from the other pane (Unprocessed, Library, another page) onto the page; drag tiles onto a Places tree entry or a card | tile *ctx* "Move to group ▸" (placed at the next free spot) |
| Move | drag; multi-select drag | arrows nudge |
| Resize | corner handle of the selected item (aspect kept) | |
| Stacking | *ctx* Bring to front / Send to back | |
| Select | click, Ctrl+click, **marquee** on empty page space | *ctx* Select all |
| Pan / zoom | scroll bars, wheel scrolls, middle-drag or Space+drag pans, Ctrl+wheel zooms (07 §4) | Strip zoom slot + Fit |
| **Group** | select items → Inspector "Group" / page *ctx* "Group" / `Ctrl+G`: they become a new group, its card appears where they were, the items keep their relative layout on the new page | |
| Ungroup | card *ctx* / Inspector / `Ctrl+Shift+G`: the card dissolves into its items on the current page | |
| Open a group | double-click the card | Places tree; breadcrumb back; `Esc` / `Backspace` to the parent |
| Move a group into another | drag its card onto another card, a tree entry or the other pane | |
| Duplicate | *ctx* / Inspector / `Ctrl+D` / `Ctrl`+drag: a copy next to the original (a group duplicates with its contents) | |
| Back to Unprocessed | `Del` / *ctx* "Back to Unprocessed" / drag into an Unprocessed pane | |
| Delete a group | card *ctx* / Inspector: the group goes, its items return to Unprocessed (Undo toast); nothing is trashed | |
| Undo / redo | `Ctrl+Z` / `Ctrl+Shift+Z`; *ctx* "Undo …"; toasts for removals | page edits are suite-scoped undo (07 §4) |

- A **card** shows a fan of its first three items (or the chosen cover), the name and the item count. No ids, no timestamps —
  this is what replaces the group header of 2d. Opening a card **in place** as a frame on the parent page comes later (§12 c).
- Loupe, keep / reject, rate, tag, Edit, Animate, reference work on page items exactly as on grid tiles; the Inspector follows the
  selection.
- Trashing an asset takes it off its page; Restore puts it back if the group still exists, else in Unprocessed.

**Lineage view** (uses `GET /lineage/tree/{root}`), opened in the active pane:

```
 root ──inpaint──▶ ▢ ──refine──▶ ▢ ──extract──▶ ▢ ▢ ▢
   │
   └──variation──▶ ▢ ──inpaint──▶ ▢
```

- Root on the left, derivations to the right, one row per branch, edge labels from `lineage.kind`; the opened asset is
  highlighted. Nodes are normal tiles (selection, menu, drag onto a page in the other pane); each shows a small location hint
  (Unprocessed / its group's name) because the branches of one lineage are usually spread over several groups.
- Duplicates are not lineage: a duplicate is the same picture in a second place, not a derivation (§8).
- Entry: the ⤷ badge (becomes a button), Inspector · Lineage "Open tree", tile *ctx* "Show lineage". It replaces A16's hidden
  `root_id` filter and the Lineage group mode. Closes with `Esc` / its bar's Back, like the loupe.

**Loupe / Compare** keep their bars; the strip is hidden while they are open (F7). The loupe's pin uses the `cat.pin` command.

### 6d. Settings · Catalogue (new section in the Settings modal)

Thumbnail fit / fill · Tile caption: **off** (default) / prompt / model · seed. Remembered in the UI layout memory (07 §1.7), not
in project data.

### 6e. Inspector — one column, the single home for the selection

One scrolling column with collapsible sections (collapsed state remembered), no tabs (§11 #5):

| Section | One asset | Several selected | A card (group) selected |
| --- | --- | --- | --- |
| Header | preview, "klein-9b · 1024×1024 · today 14:02" | stacked thumbs, "N selected" | cover, name (editable), "9 items · 1 group" |
| Judge | keep / reject / clear, stars | same, applies to all | — |
| Tags | chips with ✕, add field with autocomplete | add to all; chips = tags all share | — |
| Location | "Album › Act 1 › Alley" (click opens it, in the other pane when split) or "Unprocessed"; "Move to ▾"; Duplicate | "Move to ▾"; on a page: **Group** | Open, Open in other pane, Ungroup, Duplicate, Set cover, Delete group |
| Actions | Edit · Animate ▸ (start / end) · Reference · Re-run · Variations · Load into Generate · Pin · Loupe; ⋯ Reveal, Copy prompt, Trash | Reference · Pin · Trash | — |
| Lineage | ancestry path root → … → this as thumbnails (click to go), children / branch count, "Open tree" | — | — |
| Prompt | scene first, the JSON tree on demand, copy | — | — |
| Details | seed, steps, guidance, size, bytes, time, model variant, encoder; ids (asset, job, session, graph) with copy; "duplicate of …" when it is one | — | id, created |

Removed: the tabs, the duplicate Re-run in Params, the id as the first Info row.

### 6f. Right-click menus

| Menu | Holds |
| --- | --- |
| Tile (any pane) / loupe | as today + Move to group ▸, Duplicate, Show this batch, Show lineage, Copy prompt; on a page also Back to Unprocessed, Bring to front / Send to back, Group (with a selection) |
| Card | Open, Open in other pane, Rename, Set cover, Duplicate, Ungroup, Delete group, Bring to front / Send to back |
| Empty grid pane | Import…, Select all |
| Empty page | Select all, Fit, Undo / Redo |
| Pane header ⋯ | Swap panes, Close this pane, Open … here ▸ (Unprocessed, Library, a group) |
| Places entry | Open, Open in other pane; rename, set cover, duplicate, ungroup, delete (groups); Empty trash (Trash) |

## 7. Selected vs not selected — the same strip

```
not selected:
[Unprocessed][🔍 alley  (State: keep ✕) + Filter][✕] 38 │ Sort: newest ▾ │                │            │ Split ▾ │ Import ▾ │ ⊖━━●━━⊕
3 selected, 2 pinned:
[Unprocessed][🔍 alley  (State: keep ✕) + Filter][✕] 38 │ Sort: newest ▾ │ 3 selected ✕   │ ▢▢ Compare │ Split ▾ │ Import ▾ │ ⊖━━●━━⊕
```

## 8. Backend impact

| Need | Change |
| --- | --- |
| Filters as chips | none: `AssetQuery` has every field (`kind`, `suite`, `model_id`, `rating_min`, `tags_any`, `aspect`, `has_children`, dates, `batch_id`, `session_id`). Date presets resolve on the server like B11's `today` (local midnight) |
| Unprocessed | a query, not a stored list: assets with no placement and not trashed (`placed = 0` in the index); a new place value `unprocessed` replacing the folder list; its count in the Places tree |
| Lineage view | none: `GET /lineage/tree/{root_id}` returns items + edges with `kind`; add each item's location (group id / name) for the hint |
| Group-by modes retired | `GET /assets/groups`, `GROUP_KEY`, `group_by` / `group_key` and the folder list in `counts()` go (after Generate stops using batch groups, §9) |
| **Groups (new)** | **atomic JSON records** `groups/<id>.json` in the project, like asset manifests: `{id, name, cover_id?, created_at, updated_at, revision, items: [{kind: "asset" \| "group", id, x, y, w, z}]}`; the root `groups/album.json`. The SQLite index caches placements (`group_items`, unique per item) for counts, Unprocessed and "where is this asset", rebuilt from the files. Today's collections live **only** in SQLite: they survive `rebuild()` but not the loss of the index — arrangements are hours of hand work and must be files |
| Group rules | an item (asset or group) has **at most one** placement; moving it removes the old one in the same write; no cycles; deleting a group returns its assets to Unprocessed and its sub-groups' assets too, never trashes. A rebuild that finds an item placed twice (hand-edited files) keeps the most recent placement and logs it |
| **Duplicate (new)** | `POST /assets/{id}/duplicate` → a new asset id with a **copy of the file** (D30: disk is cheap) and a manifest that records `duplicate_of`; params, prompt, tags, state and rating copied; **no lineage edge** (the lineage view stays about derivations; the Inspector shows "duplicate of …"). Placed next to the original. `POST /groups/{id}/duplicate` deep-copies a group (its assets duplicated, sub-groups recursively) |
| Group API | `GET /groups/tree`; `GET /groups/{id}` (items + asset summaries); `POST /groups`; `PATCH /groups/{id}` (name, cover); `PATCH /groups/{id}/items` (one request per drag end: move / resize / z / add / remove, with `revision` → 409 when stale, as the editor's stack revision does, C1/C20); `POST /groups/move {items, to_group, positions}` for moves across pages and to / from Unprocessed (one transaction, both files); `POST /groups/{id}/group {item_ids}` → new child keeping relative positions; `POST /groups/{id}/ungroup`; `DELETE /groups/{id}`; WS `group.changed` |
| Asset field | `Asset.collection_ids` → `group_id` (one, or null = Unprocessed) |
| Migration | manual collections → groups (members as a tidy grid in added order), placed as cards on the album page; smart collections → frozen into groups with their members at migration time. An asset in several collections stays in the oldest and is **duplicated** into the others, so nothing arranged is lost; the count goes to the journal. Then the `collections` tables and endpoints go |

## 9. Generate shares the Strip, Stage and Inspector

Generate wraps the Catalogue strip with its own "show: this batch / session / all" segment (`GenerateSuite.tsx:401`) and its
results store groups by batch. With group-by retired, Generate shows a flat grid scoped by the Batch chip / Date preset (its three
choices become the Place slot), keeps the fixed-slot strip without Split and Import, and gets the same Inspector (including Move to
group, so results can be filed without leaving Generate). Its results are Unprocessed items until filed. To be confirmed in the
Generate pass.

## 10. Side findings (bugs found while making the inventory)

1. `cat.tag` (`T`, "Tag…" in menus) focuses `#insp-tag`, which only exists while the Inspector's Tags tab is open; on the Info
   tab it does nothing visible (`catalogueCommands.ts:31`, `CatalogueSuite.tsx:439`). Fixed by 6e (the field is always there).
2. `cat.emptyTrash` from the menu or palette only shows a toast telling the user to use the button (`catalogueCommands.ts:48–49`).
3. "Show as tree" sets `root_id` with no chip; it is cleared only by "All roots" inside an asset's Lineage tab (A16).
4. The strip's state segment has no "none" while the Filters tab's does; both write `q.state`.
5. `cat.animate` declares the `strip` placement but the strip never renders it (the dev audit cannot catch this because the
   Inspector renders it).
6. The loupe's pin button is hand-rolled instead of `cat.pin` (label and behaviour can drift).
7. Marquee selection (07 §3b) was never built.
8. Not the Catalogue: the decision log has two rows numbered **D31** (`13-decision-log-and-open-questions.md:48–49`).
9. Small grey text (`--fg3: #747474`) is about 4.0:1 on the panel background (`#171717`), under the 4.5:1 minimum for 12 px
   text; the mockups use `#8c8c8c` (about 5.3:1). **Fixed 2026-10-07** with the theme switch (07 §7).

## 11. Decisions (author, 2026-10-07) — layout

| # | Question | Decision |
| --- | --- | --- |
| 1 | Filters as chips in a query bar, or a filter drawer? | **chips** |
| 2 | How are assets organised? | **photo album**: items dragged and arranged freely on pages; each arrangement is a group; a collapsed group is dragged onto another page like a photo, and so on. The only grouping; batch / session / model / lineage grouping becomes filters |
| 3 | Albums vs saved searches? | **one type only: groups**; no smart collections or saved searches |
| 4 | Session vs Day group mode | **moot** (group-by modes retired) |
| 5 | Inspector: one column or tabs? | **one column** |
| 6 | Where does fit / fill live? | **Settings only** |
| 7 | Tile caption default | **off** |
| 8 | Focus mode leaves triage to menus, keys and the loupe bar | **acceptable** |

## 12. Decisions (author, 2026-10-07) — the album model

| # | Question | Decision |
| --- | --- | --- |
| a | Can one asset sit in several groups? | **no — one place only; a Duplicate command makes a second item** |
| b | Endless canvas or fixed-size sheets? | **endless canvas** |
| c | Cards that open in place as frames on the parent page? | **yes, later**; double-click opens the page first |
| d | Free rotation? | **no** |
| e | Where do new items land? | **Unprocessed**, where all new generations land; the Stage **splits** to show two groups, or a group and Unprocessed, side by side |
| f | Captions / notes on page items | **yes, later** |
| g | Tidy tools (align, distribute, arrange as grid) | **yes, later**, in the page menu |

Defaults that follow from these (proposed, **accepted by the author 2026-10-07**): imports, Edit renders, clips and extracted frames land in
Unprocessed too; rejected items stay in Unprocessed until trashed or placed (the State chip hides them); dragging between panes
moves, `Ctrl`+drag duplicates; on a page the query bar highlights instead of hiding; the default split is stacked (page above,
Unprocessed below).

## 13. Slices

Implemented 2026-10-07 (journal 90 of that day): 1–7 in the order groups backend (5) → Places + strip (1, 2) → Inspector (3) →
lineage view (4) → split Stage (6) → pages (7). Open: 8 (Generate keeps the older strip and its batch group-by until its pass) and 9.

1. **Clean-up**: §10 fixes 1–6; remove the duplicate homes the new layout does not need (strip selection icons, state segment,
   fit / fill → Settings, Import tab, foot button, Collections and Filters tabs).
2. **Places + query bar** (6a, 6b): fixed-slot strip, chips, Batch chip, Import button, drop on the grid; group-by modes retired
   in the Catalogue (Generate keeps them until slice 8).
3. **Inspector** (6e): one column, Location and Lineage sections.
4. **Lineage view** (6c): independent of the groups work.
5. **Groups backend** (§8): records, index, Unprocessed, move / duplicate, API, migration of collections, tests.
6. **Split Stage** (6c): two panes, pane headers, active-pane strip, drag between panes.
7. **Pages** (6c): canvas, cards, Group / Ungroup, nesting, undo, the Places tree; headed check on the rig.
8. **Generate pass** (§9) and removal of the group-by code.
9. Later: in-place frames (§12 c), captions / notes (§12 f), tidy tools (§12 g).
