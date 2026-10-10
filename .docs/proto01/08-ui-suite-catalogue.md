# 08 · Suite D — Catalogue (UI document)

Status: **implemented — M2 closed 2026-10-05**, extended through M6 (Empty trash, drops onto Edit / Animate, clips folder); amendments dated inline. Originally: proposed; approval gates M2. Frame: 07. Data model: 06 §5. Lessons applied: loom's grouped view,
keyboard-by-row, loupe + compare, and branching derivations were right; virtualisation, thumbnails, video
tiles and persistent selection state were missing (02 §4b).

**Redesigned (2026-10-07, D34, implemented the same day):** the current layout and organisation (Places, filter chips, album pages,
split Stage, one-column Inspector, lineage view) are specified in
[`../proto01_design/01-catalogue-inventory.md`](../proto01_design/01-catalogue-inventory.md); this document records the MVP layout
and stays valid for the data model, API, keyboard and performance budgets.

## 1. Purpose
Browse, group, judge and route every asset the project produces or imports: generated images, edited
renders, clips and extracted frames. It is the hub the other suites read from and write to.

## 2. Layout

```
Rail: [Library] [Filters] [Collections] [Import]
┌────────────────┬──────────────────────────────────────────────────────────┬──────────────────┐
│ Panel          │ Strip: group ▾ Batch | Lineage | Session | Model | None   │ Inspector        │
│ Library tree   │        state ◉all ○keep ○reject   sort ▾ newest   ▣ 3 sel │ Info · Params ·  │
│ ├ All (4 213)  ├──────────────────────────────────────────────────────────┤ Lineage · Tags   │
│ ├ Today (38)   │ ▾ Batch · klein-9b · "alley rain" · 8 images · 14:02      │                  │
│ ├ Images       │ ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐          │ [thumb]          │
│ ├ Clips        │ │ ✓  ││    ││ ✗  ││    ││ ✓  ││    ││    ││    │          │ klein-9b · 1024² │
│ ├ Documents    │ └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘          │ seed 8812 · 4 st │
│ ├ Imported     │ ▸ Lineage · ast_7f3 → inpaint → refine (3)  [cover card] │ 6.4 s · 14:02    │
│ └ Trash        │ ▾ Batch · flux2-dev · "throne room" · 4 images · 13:40    │ ─────────────    │
│ Collections    │ ┌────┐┌────┐┌────┐┌────┐                                  │ Keep ✓  Reject ✗ │
│ ├ Hero shots ★ │ │    ││    ││    ││    │                                  │ ★★★★☆  tags…     │
│ ├ Alley seq.   │ └────┘└────┘└────┘└────┘                                  │ Send to Edit     │
│ └ + new        │                      … virtualised …                      │ Send to Animate  │
│ [Import files] │                                                          │ Re-run · Variations│
└────────────────┴──────────────────────────────────────────────────────────┴──────────────────┘
Dock: jobs
```

## 3. Regions and controls

### 3a. Panel
- **Library** tab: smart folders (All, Today, Last session, Images, Clips, Documents, Imported, Rejected,
  Trash) with counts; collections (manual) and smart collections (saved filters) with drag-to-add.
- **Filters** tab: suite (Generate/Edit/Animate/Import), model tier + variant, state (keep/reject/none),
  rating ≥, tags (and/or), aspect, size range, has document / has children / is frame-of-clip, date range,
  prompt text search (full-text over prompt JSON and text), seed. Active filters show as chips in the Strip.
- **Collections** tab: list, rename, delete (second click), convert smart → manual.
- **Import**: drop zone + "Import files/folder…" (OS picker). Imports copy into `assets/` with a sidecar
  manifest (`suite: import`, source path, EXIF/PNG metadata parsed: ComfyUI/A1111 prompts if present).
- Foot: **[Import]** primary action.

### 3b. Strip
Group mode: **Batch** (one job batch = one group, header shows model · prompt excerpt · count · time) ·
**Lineage** (derivation trees: a root asset with its children drawn left → right as a chain, fan-outs one row
per branch; collapsed = cover card with count) · **Session** (by app session) · **Model** · **None** (flat).
Groups collapse/expand (click header, `←/→`); an expanded group spans all columns. State filter segmented
control; sort (newest, oldest, rating, model, size); selection count with bulk actions (Keep, Reject, Tag,
Add to collection, Delete); zoom slider (tile 96–512 px) and Fit/Fill toggle for thumbnails.

### 3c. Stage
- **Virtualised grid** (TanStack Virtual), responsive `auto-fill` columns from the zoom slider; group headers
  are sticky; keyboard moves by measured columns.
- Tiles per 07 §3a; video tiles show the poster and scrub on hover; document tiles show the flattened render
  with a ✎ badge.
- **Loupe** (`Enter` / double-click): fills the Stage; zoom/pan at any scale (1:1, fit, Ctrl+wheel);
  prev/next (`←/→`); facts strip (model · size · seed · time · state); `C` pins for compare; `Esc` back.
- **Compare**: 2-up or 4-up with locked zoom/pan; A/B wipe slider; "difference" toggle; swap (`Tab`);
  comparing a frame against its clip's start/end stills is supported.

### 3d. Inspector
- **Info**: thumbnail, kind, dimensions, created, suite, model (tier + variant + format), seed, steps,
  guidance, time, file size; state/rating/tags editors; verbs (07 §3c).
- **Params**: the full prompt (JSON tree rendered read-only with copy; text fallback), parameters table,
  references used (thumbnails), engine graph hash; **Reuse** buttons: prompt → Generate, seed → Generate,
  all → Re-run.
- **Lineage**: parents (with verbs) and children grouped by kind (inpaint, refine, frame-extract, variation);
  click navigates; "Show as tree" switches the Stage to the Lineage group of this root.
- **Tags**: tag editor with autocomplete and recent tags; bulk mode for multi-selection.

## 4. Workflows

1. **Triage a batch**: batch group expanded → arrows move, `K`/`X` mark, `Enter` loupe, `C` compare two,
   `1–5` rate. Rejected tiles dim; "show rejected" toggle in the Strip.
2. **Follow a derivation**: Lineage group → cover card → expand → chain shows the original, the inpaint
   layer render, the refine; Inspector Lineage lists the same with verbs.
3. **Build a hero set**: filter rating ≥ 4 and keep → save as smart collection "Hero shots".
4. **Route**: `E` to Edit, `Shift+A` to Animate as start, `R` as reference, `Ctrl+R` re-run.
5. **Import references**: drop a folder; imported assets appear under Imported with parsed metadata.
6. **Clean up**: select rejected → Delete (second click) → toast with Undo (soft-delete to Trash for 30 days,
   purge on demand or by disk guard warning).

## 5. States
Empty project (hint + Import + "Generate your first image"); indexing (thumbnails pending → skeleton with
progress); filter yields nothing (clear-filters action); asset file missing on disk (tile badge, "Locate /
Remove"); clip proxy still encoding (poster only).

## 6. Keyboard (suite-specific; global in 07 §4)
Every key below is a registry command (07 §3c) that is also in the **tile's right-click menu** (loupe, edit,
keep/reject/clear, rate ▸, tag, reference, re-run, variations, animate, pin/compare, reveal, trash/restore), the
**strip's selection bar** (icons appear when tiles are selected: keep/reject/clear, loupe, edit, reference, pin,
select all/none, tag, collection, trash), the **grid's right-click menu** (select all/none, group by ▸,
expand/collapse all, search), the **group header menu** and the **Inspector verbs**. The loupe has ◀ ▶ buttons
and the same tile menu.

`←↑→↓` move · `Home/End` · `Shift+arrows` extend · `Ctrl+A` all in group · `Enter` loupe · `Esc` back ·
`C` compare · `K`/`X`/`U` state · `1–5`/`0` rating · `T` tag · `E` edit · `Shift+A`/`Shift+Z` animate start/end ·
`R` reference · `Ctrl+R` re-run · `V` variations · `Del` ×2 delete · `G` cycle group mode · `F` focus filter
search · `[`/`]` tile size.

## 7. Data and API
Reads: `GET /assets?filter&sort&cursor` (paged, 200 per page, prefetch next), `GET /thumbs/{id}/{256|512|1024}`,
`GET /lineage/{id}`, `GET /collections`. Writes: `PATCH /assets/{id}` (state, rating, tags), `POST /collections`,
`POST /assets/import`, `DELETE /assets/{id}`. Live: WS `asset.created|updated|deleted`, `thumb.ready`.
Full-text search runs in SQLite FTS5 over prompt text/JSON and tags.

## 8. Performance budgets
10 000 assets: first paint < 1 s on a warm index; scroll at 60 fps (tiles are WebP thumbs only; originals load
only in Loupe); thumbnail generation by a CPU worker (pyvips) within 2 s of asset creation; group headers and
counts computed server-side.

## 9. Acceptance checklist
- [x] 10k synthetic assets scroll smoothly in all group modes; keyboard navigation follows visual rows — 2026-10-07 `edit_headed_check.py perf`: every display frame over 3 s of scrolling on 10 009 assets, 0 long frames; first paint 14 ms on the warm index (grouping modes were checked by eye in M2) —
  2026-10-05: virtualised rows render in every mode (`scripts/make_synthetic_assets.py`, queries ≤ 60 ms);
  FPS to be confirmed interactively on the rig.
- [x] Batch triage round-trip: states, ratings and tags persist across restart (SQLite), not in session state —
  manifests + index (`PATCH /assets/bulk`), tested.
- [x] Lineage view shows a generate → inpaint → refine → frame-extract chain correctly after the suites exist — 2026-10-07: import → Wan clip (`animate`) → three `frame-extract` children, five assets in `/lineage/tree`; generate → inpaint / refine edges were verified by the M5 acceptance (lineage to the source asset)
  (roots, edges and the Lineage group exist; chain layout pending).
- [x] Import parses ComfyUI PNG metadata into Params — `tools/pngmeta.py` (ComfyUI `prompt`, A1111 `parameters`), tested.
- [x] Compare locks zoom/pan across 2 and 4 images; wipe works — plus a difference toggle and swap.
- [~] Delete is two-step with Undo (done); Trash purge respects the disk guard (purge exists, guard wiring in M3).

## 10. Open questions
- Masonry vs uniform grid (proposed: uniform with aspect-fit, masonry as an option later).
- Duplicate hints (dHash within a batch only, advisory) in MVP or later.
- Should documents (ORA) appear as assets (proposed: yes, via their last flattened render).

## 11. Trash (added 2026-10-06)
The Trash folder lists trashed assets; selected ones can be restored or deleted permanently. **Empty trash** (Library
panel under the folders, the strip's selection bar, the grid's right-click menu, `Ctrl+K`) deletes every trashed asset in
one request — a **two-step button** (the first click arms it for 4 s: "Click again: delete N permanently"), no native
dialog (07 §1.2/§1.5). Above 50 assets the server emits one `catalogue.changed {purged}` event and the grids reload, instead
of one `asset.deleted` frame per asset. Catalogue tiles can also be **dropped on the Edit tab** (opens the asset as a
document), **on the Edit stage** (adds it as a layer to the open document) and **on the Generate tab** (adds references).
