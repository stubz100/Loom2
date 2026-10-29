# frontend/src/frame — notes for coding agents

Verified at bf2c576 on 2026-10-29 (B2 of D159). Specs: `.docs/proto01/07-ui-frame.md` (selection, verbs, keys, states),
`.docs/proto01_UI2/02-structure.md` (the layers), `.docs/proto01_UI2/11-retiring-the-catalogue.md` (the Bin). Decisions D32 (mouse-first),
D34 (groups, pointer drags), D157 (the new UI) and D159 (the old shell and the Catalogue gone).

This folder holds the services the shell (`frontend/src/ui2/Shell.tsx`, the only one since B2) is built from: TopBar, Banner, Dock, Toasts,
the context menu host, the command palette, settings, the project dialog, the help overlay and AskDialog, plus the command registry, the
router, the drag manager and the loupe.

## The layers place the suites' parts

The shell's four layers (World · Shots · Episode · Bin, `ui2/layers.ts`) place the parts a suite's code exports — `SuiteParts {Panel, Strip,
Stage, Inspector, PrimaryAction?}` (`suiteParts.ts`): Shots' Performance and Final are `AnimateSuite` and `FinalSuite`, World's Edit is
`EditSuite`, Clay is `StageParts`, the Flow and Episode are `StoryParts`. A layer loads them lazily (`React.lazy` in the layer) and unmounts
what it does not show; `useStageActive()` (`stageKeep.ts`) is true unless a host says otherwise.

- **Places.** The hash names a layer's place (`#world/<class>/<profile>/<version>`, `#shots/<shot>/<level>`, `#episode`, `#bin`). A suite and
  its rail tab still name a place inside the code (`navigate({ suite, tab })`); the shell maps it onto its layer (`layerOf`), and a
  `?suite=` deep link or the dev start suite (`scripts/dev.ps1 -Suite`) lands there unless the hash names a place. `?suite=edit&doc=<id>`
  opens World's Edit on the document; `?suite=edit&tool=…&ai=…&asset=…` is `ui2/deepLinks.ts`. The rail tabs in `railTabs.tsx` are the
  sections of a suite's column (`useSuiteRail` in `router.ts`).
- **A level's keys are its reach (D121).** Shots' Clay, Performance and Final are the `stage`, `animate` and `final` suites: `setReach` in
  `commands.ts`, registered in `animateCommands.ts` — Clay the stage scope and the animate scope's shared commands (the one transport,
  `anim.level.*`, the Shot head's `anim.step.*`), Performance the animate scope but `anim.final.*`, Final `anim.final.*` and the shared ones.
  The Bin layer is the `catalogue` suite in `ui.suite`; its reach is the `bin` scope (`ui2/bin/binCommands.ts`). The level's key hook
  (`handleKeysAt`), the help overlay, the palette and the dev audit (`commandsAt`) read the one list; `commandAudit.test.ts` fails on a chord
  two scopes of one reach share.
- **Error boundaries.** `ErrorBoundary.tsx` wraps the app, each layer and each lazily loaded part (`ui2/Part.tsx`): a render error or a chunk
  that failed to load says where it happened instead of blanking the window; Try again re-imports, and a chunk failure offers Reload first.

## Rule 1 — every action is a command (`commands.ts`, D32)

- Register with `registerCommands([...])`. A `Command` has `id`, `scope`, `label`, optional `icon`, optional `keys` (+ `alt` chords),
  `when` (enabled predicate), `run`, and a **non-empty `placement` tuple** (`context`, `toolbar`, `strip`, `panel`, `inspector`, `topbar`,
  `rail`, `dock`). The type makes a keyboard-only command impossible.
- Render with `CommandButton.tsx` / `CommandRow` and menu items `cmdItem(id)`. Tooltips and menu entries show the key via `titleFor` /
  `keyLabel`; the help overlay (`HelpOverlay.tsx`, `?`) and the palette (`CommandPalette.tsx`, Ctrl+K) read the same registry, through
  `commandsAt(suite)`: what the suite's keys reach.
- `MenuButton` is a **press menu** (D55, PhotoCraft `press_menu.rs`): the press opens it, releasing that press over an entry chooses it,
  releasing anywhere else leaves it open (a click then chooses); a press on the open menu's button closes it. `openPressMenu` in
  `ContextMenu.tsx` owns the gesture; plain `showMenu` (right-click menus) is unchanged.
- Keys are dispatched by `useKeyboardMap.ts` (global: `onGlobalKeydown` — the menu key and the palette answer everywhere, every other
  global key, the Ctrl chords included, only outside a field or a modal, V68) and the suites' key hooks via `handleKeyFor(scope, e)` (a suite
  with a reach: `handleKeysAt(suite, e)`). Never add a raw `keydown`
  listener for a user action that has no command; a hook that must see a key first (a hold, a capture-phase claim) matches it with
  `matchesCommand(e, command(id))`, never a literal key — the user may have remapped it. The one hold still on a literal is the editor's
  Space (the hand tool's accelerator, `EditorCanvas.tsx`): it ignores fields, modals and a hidden editor and lets go on `blur` (V93).
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
  `sequenceCommands.ts`, the selected model for `models.*`); the run clears it, so the palette never acts on a stale item. D93: a menu
  entry does the same with `{ cmd, on }` — `on` wraps the command's `when` and `run` with its item set (`onProfile` in `story/addToCast.ts`,
  `onStoryItem({ take | face })` and `markerMenu(id)` in Story, `onBinTile` in the Bin). A right-click menu never sets the item before
  `showMenu` (V69: it stayed set after the menu closed, and the palette ran the verb on the last right-clicked item).
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

Current drop sites: the Generate column's reference slots, Performance's start and end slots, the Edit canvas and its empty stage, the
Bin's homes (a tile dropped on a home moves it; a heading refuses, saying why) and its grid (an OS file), the Shots storyboard.

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
banners, the ask dialog, persisted `ui` layout) and `applyEvent()`, which keeps the session's own frames and publishes the rest to
`frontend/src/store/records.ts` (U1, D157): the records layer owns the fan-out — today's holders by dynamic import, and any store may
`onRecords(id, kinds, h)`; a reconnect publishes `resync`. Project data never lives
in component state. `frontend/src/api/client.ts` is the only HTTP / WebSocket client (`EventsSocket` keeps the last frame it applied and the
hub's run; a reconnect's auth names them and the hello replays the missed frames through `applyEvent` in order, or says `gap` and the
session fetches and reloads the lists — V65; the queue and project fetched after a job frame are applied only when nothing newer
arrived meanwhile — V67); `frontend/src/shell/tauri.ts` is the only module that imports `@tauri-apps/*`. Media URLs come only from `api.fileUrl` / `api.thumbUrl` / `api.assetUrl`, which append the read-only media key (D67: an `<img>`
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

## The shell's seams (U1, D157)

The UI2 plan (`.docs/proto01_UI2`) built the shell (`frontend/src/ui2/Shell.tsx`) beside the old one, which B2 (D159) removed, on four seams —
keep them when adding code:

- **Navigate, never set the suite.** `router.ts` has `navigate({ suite, tab? })` (the tab first, then the suite, then the listeners),
  `setRailTab` (the rail state lives here), `currentPlace()`, `onNavigate` and `layerOf` (a place's layer). Only the router calls
  `setSuite` (and the session at launch, for a place the hash names); `router.test.ts` fails on any other caller. The layer follows every
  navigation and the hash (`ui2/layers.ts`).
- **Keys are the shell's.** A suite's key hook mounts through `registerKeyHost(id, Host)` (`keyHosts.tsx`) at its module's load, and
  the shell renders `<KeyHosts />`; a host checks `ui.suite` itself. Never mount a key hook inside a Strip.
- **Records are shared through the records layer.** Episode reads clips through `frontend/src/store/clips.ts`, not Animate's store.
- **Singletons have context slots.** `frontend/src/store/contexts.ts`'s `contextSlot(read, write)`: `makeContext` (the Make panel),
  `stageContext` (the open stage), `compositionContext` (the composition) keep a context's state on leaving and restore it on returning.

## The detached loupe (D155)

`?view=loupe` makes `App.tsx` render `DetachedLoupe.tsx` (lazy) instead of the shell: a second window — `openDetached` in `loupeLink.ts` opens a
`WebviewWindow` labelled `loupe` in the shell (the capability in `src-tauri/capabilities/default.json` names the label and its window permissions)
or a `window.open` popup in a browser, with the browser's token / port in the URL. The windows talk over one `BroadcastChannel` (`loom2-loupe`):
the Bin (`ui2/bin/binStore.ts`) publishes `show` with `followedAsset(loupe, primary)` and answers `hello`; the detached view follows unless held. It boots
with `discoverBackend` + `setBackend` + the media key only (no session init, no events socket) and reuses the loupe's `useZoomPan` / `Playable`.

## Checks

`npm run build` (tsc + vite), `npm run lint`, **`npm test`** (Vitest + jsdom, `src/**/*.test.ts(x)`, 590+ tests in ≈ 8 s — incl. `commandAudit.test.ts`, the
D32 audit: every registered command needs a mouse placement, a chord shared within a scope needs an allow-list entry with its reason;
D90: a command that declares `context` must be named as `{ cmd: 'id' }` / `cmdItem('id')` in some menu, a hand `markUsed('id')` needs the
id rendered or run in the same file, and Animate, the Stage timeline and the Episode lane keep one transport key set)
and **`npm run build:e2e && npm run test:e2e`** (Playwright on Edge, WebGL2, against `vite preview` of `dist-e2e/`, a real orchestrator
and `orchestrator/tests/fake_comfy.py` as a process — `e2e/global-setup.ts`, both started with `--parent-pid` so a killed run leaves
nothing behind (V54); 80+ scenarios in ≈ 6 min, run alone — it flakes under load; dev hooks stay in the e2e build through `src/devHooks.ts`).
`npm run perf` measures startup to the Bin's first tile, the Bin ↔ World's Edit switches, Edit re-entry and the Bin's scroll pacing into `bench/perf/<date>.json`;
`scripts/perf_compare.py` diffs the last two. Pure code goes in its own module (not a component file) so it can be tested; WebGPU and
pixel-exact editor checks stay in `scripts/edit_headed_check.py` (a visible Edge window against the Vite dev server).
