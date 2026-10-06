# 07 · UI frame — the shell every suite lives in

Status: proposed for approval before any frontend code. Inherits what worked in loom v2 (kb-loom-ui D1–D10)
and fixes what did not (02 §4b). Engine decisions: 05.

## 1. Principles

1. **Design the frame first.** Every control in every suite has a named home: Rail, Panel, Strip, Stage,
   Inspector, Dock, Banner. No floating bars, no controls "absorbed" by the stage.
2. **Keyboard-first, pen-aware.** Every verb has a key; navigation follows the *visual* grid; no hover-only
   affordances; no native dialogs except OS file pickers. Confirmations and one-line text prompts use the frame's own
   **AskDialog** (`askConfirm` / `askText` in the session store: Enter confirms, Escape cancels, the promise resolves
   false / null on cancel) — `window.confirm` / `window.prompt` crash in WebView2 ("dialog.confirm not allowed",
   found 2026-10-06) and are banned. Deleting a layer asks nothing: it is undoable and the toast offers Undo.
3. **One selection model, one asset tile, one job dock** shared by all suites.
4. **Display == reality.** Parameter controls are generated from the backend's capabilities; defaults shown are
   the defaults run.
5. **Nothing destructive on one click.** Second click or an Undo toast.
6. **Type ≥ 12 px, 8 px grid, dark neutral theme, one accent.** Density toggle (comfortable / compact).
7. **Layout memory per suite** (panel widths, collapsed state, zoom) in `localStorage`; project data never
   lives in component state.

## 2. Frame regions

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Top bar  [Catalogue] [Generate] [Edit] [Animate] [Models]   ProjectName ▾   ● engine  ▣ 2 jobs  ▤ disk 61%  ☰ │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ Banner slot (sticky): "Queue paused — resumed from last session  [Resume]"                 │
├────┬──────────────────┬───────────────────────────────────────────────────┬─────────────────┤
│ R  │ Panel (tabs)     │ Strip   view ◉ grid ○ loupe ○ compare   zoom ───●──  │ Inspector (tabs)│
│ a  │ 280–480 px,      ├───────────────────────────────────────────────────┤ 300–420 px      │
│ i  │ collapsible,     │                                                   │                 │
│ l  │ resizable        │                 Stage                             │                 │
│    │                  │   (suite surface: grid · canvas · player)         │                 │
│ 48 │ primary action   │                                                   │                 │
│ px │ pinned at foot   │                                                   │                 │
├────┴──────────────────┴───────────────────────────────────────────────────┴─────────────────┤
│ Dock  ▸ Running: klein-9b t2i 3/4  ████████░░ 72%  00:41   · Queued 2 · Recent 12          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Region | Role | Rules |
| --- | --- | --- |
| **Top bar** | suite tabs, project switcher (recents, New, Open, Close), status cluster (engine chip: resident model + VRAM; jobs; disk; models health), app menu | the only place that changes suite; status chips open the Dock / Models |
| **Banner slot** | one sticky, dismissible banner at a time: queue paused, disk warning/hard-stop, weights missing (with Fetch), engine down (with Restart), GPU fallback (WebGL2) | never a modal; carries its action |
| **Rail** (48 px) | suite-specific icon tabs that switch the Panel's content (e.g. Catalogue: Library · Filters · Collections; Edit: the toolbox) | tooltips show name + key; never carries semantics only |
| **Panel** | the suite's input side: forms, trees, tool options, filters; the primary action button is pinned at its foot | collapsible to the Rail; resizable 280–480 px |
| **Strip** | one row over the Stage: view switch, zoom/fit, filters relevant to the Stage, selection count + bulk actions | may wrap to two rows at narrow widths, never more |
| **Stage** | the suite's main surface (virtual grid, PixiJS canvas, video player) | owns pan/zoom gestures: Ctrl+wheel zoom, Space+drag pan, wheel scroll |
| **Inspector** | details and actions for the current selection: tabs per suite | 300–420 px, collapsible; controls wrap, never overflow |
| **Dock** | job queue: collapsed one-liner; expanded = Active (progress, preview, ETA, Cancel) · Queued (reorder, pause) · Recent (open result); in Animate it also hosts the timeline | expands to 160–320 px; `` ` `` toggles |
| **Toasts** | bottom-right, with Undo where applicable | auto-dismiss 6 s; errors persist until dismissed |

## 3. Shared components

### 3a. Asset tile
Thumbnail (WebP pyramid), aspect-correct; badges: tier dot (Iterate/Quality/Hero), state (✓ keep / ✗ reject),
rating stars, 🎬 video (poster + hover-scrub), ✎ has document, ⤷ has children; hover shows model · seed · time;
selection ring; double-click → Loupe; Enter → suite default verb. Interim tiles (previews during generation)
show progress and the preview JPEG.

### 3b. Selection model
Single click selects; Ctrl adds; Shift ranges by visual order; marquee on empty space; arrows move by measured
columns; Home/End; `Ctrl+A`; Esc clears. The Inspector always reflects the primary selection and shows "N
selected" bulk actions when more than one.

### 3c. Cross-suite verbs (context menu, Inspector, and keys)
**Operating rule (D32, 2026-10-05):** every action is reachable with the mouse — an icon/button where the user
looks (strip, toolbar, panel, Inspector) and/or the **right-click menu of the object** it acts on; keyboard
shortcuts and modifier-clicks are accelerators only and are shown in tooltips and menu entries. Every action is a
*command* in one registry (`frontend/src/frame/commands.ts`: label, icon, shortcut, enabled predicate, and a
non-empty list of mouse placements — a keyboard-only command cannot be registered); keys, toolbars, menus, the
`?` overlay and the `Ctrl+K` palette all read from it, and the dev build logs commands no menu or toolbar has
rendered. Right-click menus exist on: Catalogue tiles, group headers and empty grid space, the loupe, Generate
reference slots, Edit layer rows and the canvas (tool-aware), and Dock job rows. `Shift+F10` / the Menu key
open the menu of the focused item.

| Verb | Key | Effect |
| --- | --- | --- |
| Send to Edit | `E` | opens the asset in Edit (creates a document if none) |
| Send to Animate as start / end | `Shift+A` / `Shift+Z` | fills the Animate inputs |
| Use as reference | `R` | adds to Generate's reference slots |
| Re-run / Variations | `Ctrl+R` / `V` | opens Generate with the asset's parameters (same seed / new seeds) |
| Keep / Reject / Clear | `K` / `X` / `U` | state |
| Rate | `1–5`, `0` | rating |
| Tag | `T` | tag picker |
| Compare | `C` | pins the asset for comparison |
| Delete | `Del` ×2 | removes asset + manifest + lineage edge + thumbs |
| Reveal in folder | `Ctrl+Shift+R` | OS explorer |

### 3d. Parameter controls
Generated from `/capabilities`: int/float sliders with typed input, enums as segmented controls or selects,
flags as switches, images as drop slots. Disabled controls show *why* ("fixed at 4 steps for distilled
Klein"). Advanced controls are behind a disclosure, remembered per suite.

### 3e. Command palette
`Ctrl+K`: every verb and navigation target, fuzzy-searchable; shows the key binding.

## 4. Global keyboard map

| Key | Action |
| --- | --- |
| `Ctrl+1…5` | switch suite (Catalogue, Generate, Edit, Animate, Models) |
| `Ctrl+K` | command palette (built 2026-10-05, generated from the registry) |
| `Shift+F10` / Menu key | right-click menu of the focused item |
| `` ` `` | toggle Dock (also: Rail icon, Dock line) |
| `Tab` | hide/show Panel + Inspector (focus mode) |
| `Ctrl+B` / `Ctrl+I` | toggle Panel / Inspector |
| `Ctrl+,` | Settings |
| `?` | keyboard overlay for the current suite |
| `Ctrl+Z` / `Ctrl+Shift+Z` | undo / redo (suite-scoped) |
| `Esc` | close overlay / clear selection / cancel tool |
| `Space` (hold) | pan on the Stage |
| `Ctrl+wheel`, `Ctrl+0`, `Ctrl+1` | zoom, fit, 1:1 |

## 5. Feedback and states

- **Engine states** (chip + banner): starting · idle (no model) · resident `<model>` (VRAM used) · busy · down.
- **Job states**: staged → queued → running (progress, ETA from engine estimate × measured history) → done ·
  failed (log tail inline, "Open log") · cancelled.
- **Disk**: chip shows project cap and disk free; warn < 5 %, hard-stop < 2 % blocks new jobs with a banner.
- **Weights**: a job needing missing weights shows an inline "Fetch N GB" action; fetch runs as a job with a
  byte meter in the Dock.
- **Loading**: skeleton tiles, never spinners over content.

## 6. Settings (modal, `Ctrl+,`)
Models root + mounted ComfyUI tree; HF token; VRAM budget; engine flags (attention backend, pinned memory,
restart-every-N); GPU renderer (auto / WebGL2); density; pen pressure curve (shown only when a pen is detected,
D19); "Apache-clean only"; **licence confirmations** (MiniMax H3 application filed, D17); project format
defaults (target 16:9 1920×1080 @ 24 fps, default tier Draft, D18); log level.

## 7. Visual language
Graphite neutrals (`#111 → #2a2a2a` surfaces), one accent for primary actions and selection (amber, as in loom
— confirmed, D20), semantic colours for keep (green), reject (red), warning (amber),
error (red). Typography: UI sans at 13 px base, 12 px minimum, monospace for seeds/ids/JSON. Icons: one
consistent set (Lucide). Motion: 120 ms ease for panels, none for tiles.

## 8. Open questions
- Whether the Models suite is a full tab (proposed) or a Settings page.
- Multi-window: a detachable Loupe/Player window for a second monitor (post-MVP).
