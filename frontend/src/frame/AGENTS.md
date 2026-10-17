# frontend/src/frame — notes for coding agents

Verified at 07cb440 on 2026-10-10. Specs: `.docs/proto01/07-ui-frame.md` (regions, selection, verbs, keys, states),
`.docs/proto01_design/01-catalogue-inventory.md` (D34 redesign). Decisions D32 (mouse-first) and D34 (groups, pointer drags).

The frame is the shell every suite lives in: TopBar, Banner, Rail, Panel, Strip, Stage, Inspector, Dock, Toasts, plus the
context menu host, command palette, settings, project dialog, help overlay and AskDialog (`Frame.tsx`).

## Suites plug in through `suiteRegistry.tsx`

A suite is a `SuiteDef {id, rail, Panel, Strip, Stage, Inspector, primary?, wideStrip?, keepAlive?, PrimaryAction?}` in `SUITE_DEFS`. The
frame places the components; it knows nothing about a suite's internals. Deep links: `?suite=` and `?tab=` (rail tab). Panel, Strip and
Inspector are keyed by the suite id, so switching suites remounts them.

- **Keep-alive (D69).** A `keepAlive` suite's Stage (Edit, Animate) stays mounted, hidden, after its first visit (`Stage.tsx`,
  `stageKeep.ts`). Inside it, `useStageActive()` says whether it is on screen: pause work while hidden, expect a 0 × 0 host, and redraw on
  return without resetting view state. The release policy (`useStageKeep.expire` / `releaseHidden`, on `ui.editKeepAliveMin` or the
  `engine.vram_pressure` event) unmounts hidden stages — so cleanup on unmount must still be complete.
- **Lazy suites (D69).** Edit, Animate and Models come from `lazySuite(meta, load, parts)` (`lazySuite.ts`): rail and flags are static
  (their rails live in `railTabs.tsx`), the components load on first render behind a skeleton, and render directly once loaded (a lazy
  boundary would add React's ≈ 300 ms reveal throttle). `preloadSuite(id)` runs on a pointer over a tab; Edit is preloaded at idle.
  Commands register at import: a command module a lazy suite owns loads with it — keep Pixi and Mediabunny out of eager modules.
- **Error boundaries.** `ErrorBoundary.tsx` wraps the app and every lazy suite part: a render error or a chunk that failed to load
  shows where it happened (the Stage explains, the panel says one line, strip / inspector / foot stay empty) instead of blanking the
  window. A failed load is not cached by `lazySuite` (Try again re-imports), but the browser keeps a failed module for the page, so a
  chunk failure offers Reload first.

## Rule 1 — every action is a command (`commands.ts`, D32)

- Register with `registerCommands([...])`. A `Command` has `id`, `scope`, `label`, optional `icon`, optional `keys` (+ `alt` chords),
  `when` (enabled predicate), `run`, and a **non-empty `placement` tuple** (`context`, `toolbar`, `strip`, `panel`, `inspector`, `topbar`,
  `rail`, `dock`). The type makes a keyboard-only command impossible.
- Render with `CommandButton.tsx` / `CommandRow` and menu items `cmdItem(id)`. Tooltips and menu entries show the key via `titleFor` /
  `keyLabel`; the help overlay (`HelpOverlay.tsx`, `?`) and the palette (`CommandPalette.tsx`, Ctrl+K) read the same registry.
- `MenuButton` is a **press menu** (D55, PhotoCraft `press_menu.rs`): the press opens it, releasing that press over an entry chooses it,
  releasing anywhere else leaves it open (a click then chooses); a press on the open menu's button closes it. `openPressMenu` in
  `ContextMenu.tsx` owns the gesture; plain `showMenu` (right-click menus) is unchanged.
- Keys are dispatched by `useKeyboardMap.ts` (global) and the suites' key hooks via `handleKeyFor(scope, e)`. Never add a raw `keydown`
  listener for a user action that has no command; a hook that must see a key first (a hold, a capture-phase claim) matches it with
  `matchesCommand(e, command(id))`, never a literal key — the user may have remapped it.
- **Keys are remappable (D72).** `keymap.ts` holds the user's overrides (`loom2.keys`, `keyStore.ts`); the registry keeps each command's
  own chords (`defaultKeysOf`) and writes the override into `keys` / `alt`, so every reader follows. A command whose own key is an
  unmodified Arrow, Esc, Space or Tab is `fixed` (listed, not remappable). Two commands that can fire in the same place (same scope, or
  either global) may share a chord only if the pair is in `keymap.ts SHARED_KEYS` with the reason they never fire together
  (`byDispatch` when a handler's order decides, not `when`); the audit test and the remap check both read that list. Settings ›
  Keyboard is `KeyboardSettings.tsx`.
- The dev build marks rendered commands (`markUsed`) and can list commands with no mouse home (`unusedCommands`); `window.__loom2Commands`
  exposes the registry to the headed checks.
- **Per-item commands (D90).** Commands take no arguments: a button on one item of a list (a take's ✓ use, a line's 🎙, a bin's +, a
  roster row's Fetch) sets the item first and runs the command (`storyItem` / `runOnItem` in `storyCommands.ts`, `binItem` in
  `sequenceCommands.ts`, the selected model for `models.*`); the run clears it, so the palette never acts on a stale item.
- **A modal owns its keys.** Every key hook skips targets inside `.modal`; a modal with commands of its own (Models & engine,
  `ModelsSheet.tsx`) takes the focus when it opens and dispatches its scope from its own `onKeyDown`.
- **One transport (D90, 02 §8.2).** Animate, the Stage timeline and the Episode lane: Space play / pause, ← / → one frame, Shift+← / →
  ten, Home / End first / last, I / O in / out where there is a range (Stage's previous / next key is Alt+← / →, Frame everything Shift+F).

## Rule 2 — drags go through `drag.ts`, never HTML5 drag and drop

WebView2 with Tauri's OS file-drop handler enabled (needed to import dropped files with their paths, `shell/tauri.ts listenFileDrop`)
delivers **no HTML5 drag events inside the page**. All internal drags use the pointer-event manager:

- sources call `beginDrag(e, () => payload)` (starts after 5 px; a click stays a click), or `carry(payload, x, y)` to hand over a pointer that
  is already moving (album pages do this when the pointer leaves the page);
- targets use `useDropTarget(accept, drop, describe?)` → `{ref, over}`, or `registerDropTarget(el, {accept, drop, over, describe})`;
- payloads are `{items: [{kind: 'asset' | 'group', id, media?}], from?, thumb?, label?}` — a source that knows the asset sets `media`
  (`'image' | 'video'`); `assetIds` / `onlyAssets` help; Esc cancels; the click after a drop is swallowed.
- **D71:** `describe(payload) → {ok, label?, reason?}` is shown on the ghost (✓ label / ✕ reason). Put the rule in `dropRules.ts` (pure,
  unit-tested) and use it for `accept`, `drop` and `describe` alike, so what the ghost says is what the drop does. A refusing target
  with a reason does not block an accepting parent (`resolveTarget`).

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

## Rule 5 — preset tiles never show letters (D92)

`PresetIcons.tsx` is the one tile row (prompt-field presets, aspect and size, styles, saved panels, Cast profiles, angle moves). Every item
carries a drawn glyph (`icon` is required; `presetGlyphs.tsx`: `glyphFor` for geometry and the built-in negatives, `fieldGlyph` for a
field or a kind, `tileGlyph` for both); a picture (`img`) covers it, `busy` marks a picture being made. The words are the tooltip and the
`aria-label` only; `PresetIcons.test.tsx` fails a tile without an svg or an img, or with text of its own.

## State

`frontend/src/store/session.ts` holds the app-wide store (backend, health, project, engine, queue, jobs, previews, capabilities, toasts,
banners, the ask dialog, persisted `ui` layout) and `applyEvent()`, which routes WebSocket frames to the suite stores. Project data never lives
in component state. `frontend/src/api/client.ts` is the only HTTP / WebSocket client; `frontend/src/shell/tauri.ts` is the only module that
imports `@tauri-apps/*`. Media URLs come only from `api.fileUrl` / `api.thumbUrl` / `api.assetUrl`, which append the read-only media key (D67: an `<img>`
cannot send the token header; every other request does); the event socket authenticates with its first message. A view that needs raw frames subscribes with `onEvents(types, cb)` (no `window` CustomEvents — D66 removed that
bus); a toast takes an `action {label, run}` (a bare function still means Undo).

**Models come from `/capabilities` (D65):** never write a model id — `frontend/src/store/modelCaps.ts` sorts `caps.models` / `caps.i2v.models`
/ `caps.tools` by `order`, reads `caps.defaults[kind]` (variant-aware) and finds tools by what they run (`recipes.segment`, `upscale_factor`).
`scripts/model_literals_check.py` (CI) fails on a quoted model id.

**Jobs carry an origin (D66):** every `POST /jobs` sends `origin {suite, surface, ref?, payload?}`; `frontend/src/store/origin.ts` turns it back
into a place (`goToOrigin`, the Dock's "Go to origin"). Interim strips list their own suite's jobs (and jobs from before D66).

**API calls are typed (D38):** `await unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id } } }))` — paths, parameters, bodies
and replies come from `frontend/src/api/schema.d.ts`, generated from the orchestrator. `frontend/src/api/types.ts` re-exports the reply types
(never hand-write an API shape). Bytes and URLs stay on `api.putBlob` / `api.thumbUrl` / `api.assetUrl` / `api.fileUrl`.

## Checks

`npm run build` (tsc + vite), `npm run lint`, **`npm test`** (Vitest + jsdom, `src/**/*.test.ts(x)`, ≈ 2 s — incl. `commandAudit.test.ts`, the
D32 audit: every registered command needs a mouse placement, a chord shared within a scope needs an allow-list entry with its reason;
D90: a command that declares `context` must be named as `{ cmd: 'id' }` / `cmdItem('id')` in some menu, a hand `markUsed('id')` needs the
id rendered or run in the same file, and Animate, the Stage timeline and the Episode lane keep one transport key set)
and **`npm run build:e2e && npm run test:e2e`** (Playwright on Edge, WebGL2, against `vite preview` of `dist-e2e/`, a real orchestrator
and `orchestrator/tests/fake_comfy.py` as a process — `e2e/global-setup.ts`; dev hooks stay in the e2e build through `src/devHooks.ts`).
`npm run perf` measures startup, suite switches, Edit re-entry and scroll pacing over 10 000 assets into `bench/perf/<date>.json`;
`scripts/perf_compare.py` diffs the last two. Pure code goes in its own module (not a component file) so it can be tested; WebGPU and
pixel-exact editor checks stay in `scripts/edit_headed_check.py` (a visible Edge window against the Vite dev server).
