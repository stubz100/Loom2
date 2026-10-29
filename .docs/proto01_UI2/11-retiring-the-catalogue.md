# 11 · Retiring the Catalogue, and a Bin that holds up

Status: **study, 2026-10-29**, at `5914638`; **answered the same day → D159** (§6). The old shell goes too, so the waves are re-ordered
(§5).

The author, 2026-10-29: *"We need to get rid of the catalogue and make the bin more robust."*

## 1. What "the Catalogue" is

- **It is the UI** (`frontend/src/suites/catalogue/`, 3,410 lines):
  - the Catalogue tab: Places, the strip with its filter chips, the windowed grid, the loupe, compare, lineage, two panes, and album
    pages with a free layout;
  - the Dock's Bin of D95 (`Bin.tsx`).
- **Its places** are Unprocessed (things on no page), the Library (everything), the album's pages and the Trash.
- **It is not the asset index.** `orchestrator/loom2/catalogue.py` (the SQLite index and the manifests behind every `/assets` route) stays.
  The Bin reads from it too. So does the album's storage (`groups.py`), which is how homes and pages are kept.

## 2. What depends on it

| Where | What it takes from the Catalogue | What becomes of it |
| --- | --- | --- |
| `frame/suiteRegistry.tsx` | the Catalogue tab | goes |
| `frame/Dock.tsx` | D95's drawer (the new shell wraps it in `ui2/bin/BinDrawer.tsx`) | the Bin's own drawer |
| `frame/DetachedLoupe.tsx` | the loupe's zoom and pan, `loupeMedia`, `catalogue.css` | moves to `frame/loupe/` |
| `store/records.ts:37–67` | the events fanned out to the Catalogue's stores and the album's | the Bin's and the album's |
| `store/origin.ts:140` | *Go to origin* opens a Catalogue place | the thing's home in the Bin, selected |
| `suites/generate/GenerateSuite.tsx:12–14` | Image's results grid is the Catalogue's Stage, Strip and Inspector | old shell only: goes with it (World's Make shows its results in the version's bin) |
| `useMentions`, `StoryParts`, `StyleTiles`, `StyleWorld`, `FlowCanvas`, `storyCommands` | `albumStore`: pages as references, boards, styles | `albumStore` moves to `store/` (the pages stay; they are the Bin's storage) |
| `e2e/smoke.spec.ts` | 27 of 92 scenarios open the Catalogue | rewritten onto the Bin |

## 3. What the Bin lacks, against the Catalogue

| The Catalogue's | The Bin today | Proposed |
| --- | --- | --- |
| multi-select, *Select all*, the keyboard (arrows, Enter, Space) | one at a time, mouse only | keep |
| bulk move, tag, trash | one thing | keep |
| the verbs of where you are: reference, Edit, animate from this frame / end frame, the shot's frame, re-run, variations, load in Image, recipe, the starts (select subject, upscale, angle, shot, 3D prop) | in the drawer only (D95's); not in the layer | one verb set for both |
| the loupe: zoom, pan, 1:1, previous / next, *Detach* | the large view without zoom; *Detach ↗* | adapt: the loupe's zoom and pan in the large view |
| compare (pin 2–4, swap) | none | keep (Q3) |
| lineage, *used by* | none | keep, in the Inspector |
| *Import…*, a file dropped from the OS | none: a file dropped on the new shell does nothing | into the open home (Imports when none) |
| duplicate, reveal in the folder | none | keep |
| *Delete permanently…*, *Empty trash…* | in the drawer only | keep |
| grouping by batch, lineage, session, model | none (*same run* in the Inspector) | drop (Q3) |
| tile size | none | keep |
| filters: kind, date, model, aspect, size, tags | kind and search | drop date, aspect and size (Q3) |
| two panes | none | drop (Q3) |
| pages: new, rename, ungroup, delete, duplicate, a free layout | none | pages inside homes (Q2); the free layout dropped (Q3) |
| Unprocessed, the Library | Imports shows the unplaced things | retired (Q4) |

## 4. What is not robust in today's Bin

Found while reading U8a's code and measuring it.

| # | What | Where |
| --- | --- | --- |
| R1 | **Pages outside every home are invisible.** On the copy of The Last Ferry, *Stage · Stay* (10 pictures) is an album page in no home. Neither the tree nor Imports shows those 10: they are placed, so they are not unplaced. | `bins.tree`, `bins.home_items` walk homes only |
| R2 | **A home sends everything at once, and the grid draws every tile.** On a 3,000-asset project the *shots* home sends 2,000 things in 304 ms. The page then draws 2,000 tiles, with no paging and no windowing. | `bins.py:257`, `BinLayer.tsx:86` |
| R3 | **Every asset event reloads the tree and the open home,** 300 ms after the last. A batch of 20 is up to 20 full reloads with a full redraw. | `binStore.ts:97` |
| R4 | **Imports' count and its list part ways past 2,000** (the list is the newest 2,000). | `bins.py:198` |
| R5 | **Homes go stale.** A deleted shot or entity leaves its home under its old name. A rename reaches the home only when a job next lands for it. | `story.py` `delete_shot`, `delete_profile`; `bins.home` |
| R6 | **Move to… can break a role.** Moving a version's hero, a reference or an A-pose out of its home leaves the record pointing at a thing no longer in its bin. Nothing warns. | `binCommands.ts` `moveTo` |
| R7 | **There are two Bins.** The layer (its own store and verbs) and the drawer (the Catalogue's D95 Bin with the homes as its places) differ in their verbs, their selection and their stores. The drawer still needs the Catalogue. | `ui2/bin/`, `suites/catalogue/Bin.tsx` |
| R8 | **A layer opened from the Bin must read its records first.** The shot case was fixed in U8a. *Its version in World* and *its cut* rely on their layer having loaded already. | `binCommands.ts` `belongs` |
| R9 | **A file dropped from the OS does nothing in the new shell.** Only the Catalogue listened for it. | `CatalogueSuite.tsx:155` |
| R10 | ***Empty trash*** **and** ***Delete permanently*** **are only in the drawer.** | `catalogueCommands.ts` `bin.*` |

Measured at 3,000 assets (2,000 in 30 shot homes, 1,000 on no page), with
`C:\Users\stubz\AppData\Local\Temp\claude\f--source-repos-stubz003-loom2\1c844ca1-d2dd-4901-a45c-07c1ff638790\scratchpad\bin_perf.py`:

| Read | Time | Things returned |
| --- | --- | --- |
| tree | 73 ms | — |
| the shots home | 304 ms | 2,000 |
| Imports | 46 ms | 1,000 |
| search | 13 ms | 200 |
| the drawer's page | 9 ms | 200 |

The server holds up. The page does not: every tile is drawn, and a reload comes on every event.

## 5. The plan

D159 re-orders the waves: the old shell goes with the Catalogue, before the two moves of records.

| Wave | What | Size |
| --- | --- | --- |
| **B0 · a Bin that holds up** — built 2026-10-29 | R2–R6, R8 (detail below; R1 comes with B3) | M |
| **B1 · one Bin, every verb** — built 2026-10-29 | R7, R9, R10 and §3's *keep* rows (detail below) | L |
| **B2 · the old shell and the Catalogue removed** | the new UI the only one; the Catalogue's code and its last users (detail below) | L |
| **B3 · pages in homes** | every album page placed in a home once (detail below) | S |
| **B4 · Unprocessed retired** | every thing without an owner lands in a home (detail below) | S |

**B0 · a Bin that holds up:**

- A home's listing is paged on the server (newest first, a cursor), and the grid is windowed (the Catalogue's
  `@tanstack/react-virtual`).
- The events are applied in place. The server sends a `bin.changed` with the homes that changed (06 §4 already asked for it). A thing
  landing in the open home is inserted, not reloaded, and the server keeps the counts per home.
- Imports' count is its list (R4).
- Homes follow their records (R5). A rename renames the home. A delete marks it *gone* and offers to move its things on.
- *Move to…* says which role a thing would lose, and asks (R6, Q5).
- Every page is in a home (R1, with B2).
- A layer opened from the Bin reads its records first (R8).

**B1 · one Bin, every verb:**

- **One verb set.** `ui2/bin/verbs.ts`: D95's verbs of where you are, plus the Bin's own (open where it belongs, move, tag, trash). The
  layer's tiles and the drawer's both use it.
- **Its own drawer.** The drawer becomes the Bin's: its tree and the windowed grid, with no Catalogue code (R7).
- **Selection:** multi-select (click, Shift, Ctrl, *Select all*), and bulk move, tag and trash.
- **The keyboard:** arrows move; Enter opens where it belongs; Space shows the thing large; Delete trashes.
- **The large view:** the loupe's zoom, pan, 1:1, previous and next.
- **Compare:** pin 2–4 things.
- **The Inspector:** lineage and *used by*.
- ***Import…*** **and a file dropped from the OS** land in the open home (R9).
- **The rest:** duplicate, reveal, *Delete permanently…*, *Empty trash…* (R10), tile size.

**B2 · the old shell and the Catalogue removed (D159):**

- The new UI is the only one: `?ui=2` is no longer needed, and ☰'s *Try the new UI* and *Back to the current UI* go.
- These go: the old frame, its tabs and rail, the suites' wrappers the layers do not use, the Catalogue tab, `CatalogueSuite`, Places,
  `PageView`, the panes, the strip, D95's drawer, and the per-pane stores.
- These move: the loupe's parts to `frame/loupe/`; `albumStore` to `store/album.ts`.
- The events and *Go to origin* point at the Bin. The Bin's commands take the scope `bin`.
- Every old-shell e2e scenario moves onto the new shell where its feature lives, or is dropped with the feature D157 dropped. Each
  old-shell feature the new shell does not reach is listed in the journal.

**B3 · pages in homes:**

- Each album page goes into a home once: a stage's page into its shot's home; a page that is nobody's into Sketches.
- Pages are folders inside a home: *New page…*, *Rename…*, *Delete* (its things go to the home).
- The album root goes.

**B4 · Unprocessed retired:**

- Every thing without an owner lands in a home:
  - Image's free work → Sketches;
  - an import → the home it was dropped on, else Imports;
  - a stage's own pass → its stage's shot.
- The unplaced things are moved once.
- `folder=unprocessed` and the Library leave the UI.

B3 and B4 each move records once: a migration with a mark, as U2's `bins.json`.

## 6. Questions for the author

The author's answers (2026-10-29), recorded as D159, are in the last column.

| # | Question | Proposed | Answered |
| --- | --- | --- | --- |
| Q1 | When does the Catalogue go? With the old shell, after the click-through of [10](10-trying-the-new-ui.md)? Or now? Now means the old shell loses its Catalogue tab, and Image's results grid in the old shell is rebuilt on the Bin's grid. | with the old shell; B0–B3 now | now, from both shells, and the old shell with it |
| Q2 | Album pages that sit in no home: fold each into a home as a named page inside it, or keep a top-level *Pages*? | into homes | as proposed |
| Q3 | Which of the Catalogue's go? Grouping modes, two panes, the date, aspect and size chips, and the free page layout. | drop all four; keep compare, lineage, tile size | as proposed |
| Q4 | A thing with no owner: Image's free work → Sketches; an import → the home it is dropped on, else Imports? | yes | as proposed (Sketches) |
| Q5 | Moving a thing that holds a role (hero, reference, A-pose) out of its home: ask, refuse, or let it carry the role? | ask, naming the role it loses | as proposed |
| Q6 | Keep "Bin" as the place's name, and "catalogue" only inside the code for the asset index? | yes | Bin; the frontend's Catalogue code deleted |

## 7. What the new UI does not reach yet (found for B2, 2026-10-29)

Mapping the 79 old-shell e2e scenarios onto the new shell found these features, built in the old shell, that nothing in the new one
opens. D157 dropped none of them (it keeps the Flow's List view, Q11). Deleting the old shell now would lose them, so B2 builds them into
the new UI first (B2a), moves the scenarios onto it, then removes the old shell (B2b). **The author, 2026-10-29: build all three groups (World's tools, Shots' views, the Bin's quick starts) before the old shell goes.**

| Where | What | The old part | Size |
| --- | --- | --- | --- |
| World | the body editor: height, build, attachments, the figure's sliders, ♀ / ♂, hands at rest | `CastBody` (Cast's sheet) | M |
| World | bound colours on the sheet | Cast's sheet | S |
| World | a prop's height, edited | Cast's sheet (World's header shows it only) | S |
| World | the skeleton bench: the reference's points and the figure's, Fit again, the version's poses | `SkeletonBench` | M |
| World | the test animation: a turn on the spot, performed with the reference | `story.cast.testAnimRef` | M |
| World | *Use as the A-pose front / back* on a creation | Cast's tile menu | S |
| World | the place set builder: the overlay, the handles, the kind, the face materials, *Bake again* | `PlaceSetSection` | M |
| World | the Line-up ▶ and *Send to a stage* | Cast | M |
| World | a prop's turning 3D model | Cast's prop page | S |
| World | Edit's own foot: the *Save •* mark, Export PNG / PSD, Close | Image · Edit's foot | S |
| Shots | the Flow's List view: by scene, a search, the shot's Recipe section, *Voice all lines (N)* | `ShotsBoard` | L |
| Shots | *Play* the Flow | `PlayView` | M |
| Shots | the recipe graph over a shot's levels, *Open its recipe* in the Flow | `AnimateGraph`, `FlowRecipe` | M |
| Shots | a still from the stage: the frame form with *Render frame* | Image · Make › From a stage (`ShotTab`) | M |
| Shots | Clay's *Prototype ▸* makes an idea (the ideas store is folded into Sketches) | Clay | S |
| Bin | *New angle…* | `AngleSheet` | S |
| Bin | the quick starts on a picture: *Select subject…*, *Upscale…*, *Make a 3D prop…*; the deep link into Edit with an AI operation | `cat.start.*`, `openWith` | M |
| Bin | *Add to ‹entity› ▸* on the Bin's own commands (today the Catalogue's `cat.addTo.*`) | `addToCast` | S |
| Everywhere | a part whose code fails to load says so and recovers, instead of taking the shell down | `lazySuite`'s boundary | S |

The scenarios split as: about 55 move onto the new shell, about 15 are covered by new-shell ones already, and about 12 go with what D157
and D159 dropped (the tabs as drop targets, the For chip, the album's pages, Expand, LoRA training, the ideas store, the Catalogue's loupe
hub and grouping).

**B2a done (2026-10-29):** all 19 are in the new UI, and every scenario of `e2e/smoke.spec.ts` runs on the new shell. The Bin's wave
moved 17 and dropped 4, World's moved 19 and dropped 4, and Shots' moved 36 and dropped 3. Only `e2e/perf.spec.ts` still opens the
Catalogue; it moves with B2b.

**B2b done (2026-10-29):** the shell is the only UI. The old frame, the suites' wrappers, the Catalogue and the per-pane stores are gone,
`albumStore` is `store/album.ts`, and the events and *Go to origin* point at the Bin (the journal lists the rest). Owed: the headed editor
check and the browser steps of seven older acceptance scripts still drive the old shell's DOM, and move onto the shell before their next
run. **B3 done (2026-10-29):** every album page is in a home (bins schema 3), and a page is a folder of its home. **B4 done (2026-10-29):** no thing stays on no page (bins schema 4); a free thing lives in the
Sketches, an import in Imports, a stage's with its shot. D159's waves are done.
