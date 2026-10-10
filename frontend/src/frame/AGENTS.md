# frontend/src/frame — notes for coding agents

Verified at 07cb440 on 2026-10-10. Specs: `.docs/proto01/07-ui-frame.md` (regions, selection, verbs, keys, states),
`.docs/proto01_design/01-catalogue-inventory.md` (D34 redesign). Decisions D32 (mouse-first) and D34 (groups, pointer drags).

The frame is the shell every suite lives in: TopBar, Banner, Rail, Panel, Strip, Stage, Inspector, Dock, Toasts, plus the
context menu host, command palette, settings, project dialog, help overlay and AskDialog (`Frame.tsx`).

## Suites plug in through `suiteRegistry.tsx`

A suite is a `SuiteDef {id, rail, Panel, Strip, Stage, Inspector, primary?, wideStrip?, PrimaryAction?}` in `SUITE_DEFS`. The frame
places the components; it knows nothing about a suite's internals. Deep links: `?suite=` and `?tab=` (rail tab). Panel, Strip, Stage and
Inspector are keyed by the suite id, so switching suites remounts them (P5 in `.docs/artcraft/08-delivery-plans.md` plans keep-alive for Edit
and Animate).

## Rule 1 — every action is a command (`commands.ts`, D32)

- Register with `registerCommands([...])`. A `Command` has `id`, `scope`, `label`, optional `icon`, optional `keys` (+ `alt` chords),
  `when` (enabled predicate), `run`, and a **non-empty `placement` tuple** (`context`, `toolbar`, `strip`, `panel`, `inspector`, `topbar`,
  `rail`, `dock`). The type makes a keyboard-only command impossible.
- Render with `CommandButton.tsx` / `CommandRow` and menu items `cmdItem(id)`. Tooltips and menu entries show the key via `titleFor` /
  `keyLabel`; the help overlay (`HelpOverlay.tsx`, `?`) and the palette (`CommandPalette.tsx`, Ctrl+K) read the same registry.
- Keys are dispatched by `useKeyboardMap.ts` (global) and the suites' key hooks via `handleKeyFor(scope, e)`. Never add a raw `keydown`
  listener for a user action that has no command.
- The dev build marks rendered commands (`markUsed`) and can list commands with no mouse home (`unusedCommands`); `window.__loom2Commands`
  exposes the registry to the headed checks.

## Rule 2 — drags go through `drag.ts`, never HTML5 drag and drop

WebView2 with Tauri's OS file-drop handler enabled (needed to import dropped files with their paths, `shell/tauri.ts listenFileDrop`)
delivers **no HTML5 drag events inside the page**. All internal drags use the pointer-event manager:

- sources call `beginDrag(e, () => payload)` (starts after 5 px; a click stays a click), or `carry(payload, x, y)` to hand over a pointer that
  is already moving (album pages do this when the pointer leaves the page);
- targets use `useDropTarget(accept, drop)` → `{ref, over}`, or `registerDropTarget(el, {accept, drop, over})`;
- payloads are `{items: [{kind: 'asset' | 'group', id}], from?, thumb?, label?}`; `assetIds` / `onlyAssets` help; Esc cancels; the click after a
  drop is swallowed.

Current drop sites: TopBar suite tabs (Edit opens, Generate adds references, Animate sets start/end), Generate reference slots, Animate
slots and beats, the Edit canvas and empty stage, Places rows, pane bodies, album pages.

## Rule 3 — no native dialogs

`window.confirm` / `window.prompt` throw in WebView2 ("dialog.confirm not allowed"). Use `askConfirm(opts)` / `askText(opts)` from
`frontend/src/store/session.ts` (rendered by `AskDialog.tsx`; Enter confirms, Esc resolves `false` / `null`). Destructive actions that are
undoable ask nothing and offer Undo in the toast.

## Rule 4 — colours are theme tokens

Every colour in the app's CSS is a custom property defined in `frame.css` for `:root` (dark) and `:root[data-theme="light"]`. `theme.ts`
(`THEMES`, `applyTheme`, `CANVAS_COLOURS`) switches them; `ui.theme` persists in `loom2.ui`; `?theme=light|dark` deep-links. Don't add colour
literals; image content (brush colours, overlays on images) is the exception.

## State

`frontend/src/store/session.ts` holds the app-wide store (backend, health, project, engine, queue, jobs, previews, capabilities, toasts,
banners, the ask dialog, persisted `ui` layout) and `applyEvent()`, which routes WebSocket frames to the suite stores. Project data never lives
in component state. `frontend/src/api/client.ts` is the only HTTP / WebSocket client; `frontend/src/shell/tauri.ts` is the only module that
imports `@tauri-apps/*`.

## Checks

`npm run build` (tsc + vite) and `npm run lint`. There are no frontend unit tests yet (P6 adds them); interactive checks run through
`scripts/edit_headed_check.py tour` in a visible Edge window against the Vite dev server.
