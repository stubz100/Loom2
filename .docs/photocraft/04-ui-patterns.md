# 04 · UI patterns

PhotoCraft's UI (`crates/ui-egui/src`) is immediate-mode egui, so none of it moves to React as code. What moves is **behaviour**:
many modules open with a `//!` header stating the Photoshop behaviour they reproduce, which makes them a good spec source. Its UI
rules live in `docs/ui-design.md` (layout grammar, themes, interaction models) and `docs/context-menu-parity.md` (the right-click
contract).

## 1. Layout

- **Shell** (`panels.rs`):
  - the menu bar;
  - a 36 pt **options bar** that changes per tool;
  - a left **toolbar** of flyout slots;
  - document tabs (`name @ zoom % (layer, RGB/8)`);
  - a right **dock** of tab-strip groups (Properties | Adjustments, Layers | Channels | Paths, …) with an icon rail beside it;
  - a status bar (editable zoom field, colour mode and depth, size, layer count, last message).
- **Dock** (`dock.rs`):
  - six groups, each with a default and a compact height; content scrolls inside a group and never sizes it;
  - the last expanded group fills the rest;
  - drag the gap between groups to resize, double-click a tab to collapse, drag a tab strip to reorder;
  - the layout serialises as named workspaces, and "Lock Workspace" freezes it.
- **Tab strips** (`tab_strip.rs`): tabs shrink with "…", then overflow into a » menu. The selected tab always stays visible.
- **Themes** (`theme.rs`):
  - eight themes built from one `Tokens` struct, with the rule "never hard-code a colour in a widget";
  - `cursor_outline()` is theme-independent black/white for drawing over pixels.

## 2. Toolbar, options bar and canvas feedback

- **Flyout tool groups:** each slot shows its **last-used** tool; right-click or a 0.35 s long press opens the group, listing key
  letters right-aligned. Edit › Toolbar hides tools.
- **Options bar per tool** (`panels.rs::options_bar`):
  - Marquee: 4 mode icons (new / add / subtract / intersect), Feather, Anti-alias, Style (Normal / Fixed Ratio / Fixed Size with a
    swap icon), and a "Select and Mask…" pill.
  - Wand: Tolerance, Anti-alias, Contiguous, Sample All Layers.
  - Move: Auto-Select [Layer/Group], Show Transform Controls, align icons.
  - Brush: preset chip, Mode, Opacity, Flow, Smoothing with an options menu, and pressure toggles.
  - **During Free Transform the bar is replaced** by X, Y, W %, a link toggle, H %, angle, interpolation and a warp toggle, then
    **✓ commit (Enter)** and **⊘ cancel (Esc)**.
  - Crop, Type and Transform get the same commit/cancel buttons.
- **One-line hints** for simple tools ("Drag to draw a gradient") in the roomier themes.
- **Canvas feedback:**
  - Marching ants in black and white, so they read on any pixels.
  - A **selection-intent badge** beside the cursor (`+`, `−`, `×`): taken from the options-bar mode, overridden by held modifiers.
  - **Selection-move badges:** move outline, scissors for cut-and-move, a second arrow for Alt-copy.
  - The **brush cursor** is an OS custom cursor bitmap, so it tracks the pointer independently of canvas FPS.
  - **Alt + right-drag** resizes the brush horizontally and changes hardness vertically.

## 3. Layers panel

- **Header:**
  - a kind filter;
  - a Blend dropdown, where **the mouse wheel steps the mode** and **hovering a mode previews it live** (`blend_preview.rs`);
    choosing commits one history step;
  - Opacity and Fill as **popup value fields** (type, scrub, or press ▾ and drag a pop-up slider; one drag = one undo step);
  - five lock icons.
- **Row anatomy:**
  - eye column, with **eye sweep**: drag down the eyes to apply the first eye's new state to every row passed, in one step;
  - indentation per group depth;
  - layer thumbnail, then mask thumbnails, each with a **link chain** (click toggles "moves with layer") and a red X when disabled;
  - **corner brackets** around the targeted thumbnail (pixels or mask);
  - the name, with right-hand indicators laid out right to left and the least important dropped first when narrow.
- **Selection:** click replaces, Ctrl-click toggles, Shift-click selects a range. **Ctrl-click a thumbnail loads it as a
  selection.**
- **Drag and drop:**
  - reorder rows, with edge auto-scroll;
  - **drop a row on a footer button**: Trash deletes, New duplicates, Folder groups; the target button gets an accent outline;
  - a dragged row inside the selection carries the whole selection.
- **Footer:**
  - Trash, which becomes "Delete Layer Mask" when a mask is targeted;
  - New, Group;
  - Adjustment ▾ and fx ▾ as **press menus**: press, drag onto an item, release to choose; a plain click leaves the menu open;
  - Mask, Link.
- **Context menu** (`layer_menu_ui.rs`): a pure data model in Photoshop order, trimmed to the layer kind. Labels pluralise with a
  multi-selection, and items whose command doesn't exist are skipped rather than shown dead.

## 4. Properties

- **Collapsible sections** with a chevron header (`props_layout.rs`) and a compact field grid with short glyph labels.
- **The panel follows the target:**
  - no layer → Document properties;
  - a mask targeted → **Density % and Feather px** (one drag = one coalesced undo step);
  - an adjustment → its inline editor.
- **Inline adjustment editors** (`adjust_editors.rs`, `tone.rs`):
  - **Levels:** a histogram with three triangle input sliders, numeric fields and Auto.
  - **Curves:** click to add a point, drag it out to delete, a histogram of the image *below*.
  - **Hue/Sat:** gradient tracks.
  - Then "Clip to layer below" and "Reset to defaults". One drag = one coalesced step.
- **Quick Actions:** full-width buttons, two per row when wide, filtered to commands that are currently enabled.

## 5. Context-menu contract (`docs/context-menu-parity.md`)

Seven rules, directly applicable to loom2's `commands.ts`:

1. Hit-test the most specific target first: modal handle → text → canvas → row/icon → tab → empty.
2. Snapshot the target and the selection when the menu opens. **A row inside a multi-selection acts on the set; a row outside it
   becomes the target first.**
3. Build items from a pure menu model (label, command id, params, enabled, reason). **Never show a clickable no-op**: disable it
   with a reason, or omit it.
4. A secondary click never paints, transforms or commits.
5. Anchor at the pointer and clamp to the viewport; separators only between non-empty groups.
6. Use the same command id and enablement as the menu bar.
7. Test each menu model on its own.

**Canvas menus are tool- and state-dependent** (`canvas_tool_menu.rs`):
- **Selection tools, with a selection:** Deselect, Inverse, Feather…, Select and Mask…, Layer via Copy/Cut, Transform Selection,
  Fill…, Stroke…, Content-Aware Fill….
- **During Free Transform:** the transform modes, current one checked.
- **Painting tools:** a brush quick picker.
- **Move tool:** **the layers with visible pixels under the pointer**; choosing one selects it.

## 6. Dialogs and previews

- **Filter dialogs are generated from the engine's parameter specs** (`filter_dialog.rs`).
  - The preview runs **the same command on a downsampled proxy**, with pixel parameters scaled, so the preview matches the result.
  - `filter_preview_worker.rs` keeps one preview in flight. While a slider moves, the running preview finishes, so the canvas keeps
    updating; once values settle for 150 ms a stale preview is cancelled.
- **Modal adjustments** preview as a temporary clipped adjustment layer (02 §6). Tests check the preview within 1/255 of the
  destructive result, and `unsupported()` lists where it can't match.
- **Export As:** format, quality, scale, the resulting pixel size, and an **estimated file size** from encoding a small proxy.
- **Jobs and notices:**
  - status-bar progress with Cancel;
  - a modal progress dialog only after a short delay;
  - at most three non-blocking notice cards.
- **Dialog rules:** platform-ordered buttons; the first numeric field is focused with its text selected; Preferences has Apply / OK
  / Cancel, with Apply disabled while nothing differs.

## 7. Discoverability

- **`menu_catalog.rs`:** Photoshop's full menu tree as data (path, label, default shortcut, command id). Items light up when the
  command exists; `cargo xtask parity` generates `docs/parity.md` with a never-lower floor.
- **Command palette** (`palette.rs`): fuzzy search over every command, tool and panel. An empty query shows the 8 most recent
  commands. Help › Search shows each result's menu path, which teaches where things live.
- **Tooltips append the live shortcut**, aware of user overrides (`shortcuts::tip_label`).
- **Latched modifiers** (`workspace_ui.rs::sticky_mods`): an on-screen panel of sticky Shift / Ctrl / Alt, so every modifier
  gesture can be done with the mouse alone.

## 8. Twenty patterns, ranked for a mouse-first React editor

| # | Pattern | Source | Serves |
| --- | --- | --- | --- |
| 1 | **Latched modifier buttons** (sticky Shift/Ctrl/Alt on screen) | `workspace_ui.rs::sticky_mods` | D32 directly: no modifier-only gestures |
| 2 | **Commit ✓ / cancel ⊘ in the options bar during modal operations**, tooltips naming Enter/Esc | `transform_tool.rs`, `panels.rs` (Crop) | D32: modal ops never keyboard-only |
| 3 | **Context menus as data models sharing enablement with buttons**, no dead entries | `layer_menu_ui.rs`, `canvas_tool_menu.rs`, `enable_rules.rs` | `commands.ts` |
| 4 | **Right-click on a multi-selection acts on the set** | `context-menu-parity.md` rule 2 | bulk ops by mouse |
| 5 | **Tool- and state-dependent canvas menu** (incl. layers under the pointer) | `canvas_tool_menu.rs`, `layer_pick_ui.rs` | D32 |
| 6 | **Coalesce keys**: one slider drag = one undo step | `mask_props_ui.rs`, `panels.rs::pct_action` | usable History |
| 7 | **Press menus** (press–drag–release; click keeps open) | `press_menu.rs` | one gesture per action |
| 8 | **Popup value field** (type, scrub, or ▾-drag a slider) | `widgets::popup_value_field` | "presets behind one icon per field" |
| 9 | **Hover-preview in dropdowns** + wheel steps (blend mode) | `blend_preview.rs` | try before commit |
| 10 | **Drop a layer row on a footer button** (delete / duplicate / group) | `panels.rs::footer_drop` | pure-mouse layer ops |
| 11 | **Eye-column sweep** in one step | `panels.rs::eye_sweep` | bulk visibility |
| 12 | **Mask link chain + targeting brackets**; footer and Properties follow the target | `mask_thumbs_ui.rs`, `mask_props_ui.rs` | clarity about what a stroke affects |
| 13 | **Properties sections + Quick Actions** | `props_layout.rs` | per-kind actions one click away |
| 14 | **Inline Curves / Levels editors with histogram** | `adjust_editors.rs`, `tone.rs` | replaces JSON text fields |
| 15 | **Live proxy preview with settle-cancel** | `filter_preview_worker.rs` | T8 (preview = result) |
| 16 | **Dialogs generated from parameter specs** | `filter_dialog.rs` | `/capabilities` defaults |
| 17 | **Selection intent / move cursor badges** | `tool_feedback.rs` | shows what a press will do |
| 18 | **Flyout tool slots showing the last-used tool** | `panels.rs::slot_tool` | compact rail |
| 19 | **Tooltips with live shortcuts + palette with recents and menu paths** | `shortcuts.rs`, `palette.rs` | keys stay accelerators |
| 20 | **Status-bar job progress, delayed modal, notice cards** | `jobs_ui.rs`, `notices.rs` | the Dock job queue |

loom2 already has the foundations of several of these: tooltips with keys, a palette (`Ctrl+K`), right-click menus, and a toast
system with Undo.
