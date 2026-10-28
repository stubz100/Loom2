<!-- markdownlint-disable MD024 -->
# 08 · The registers: the walkthrough, and the code review

**The walkthrough** (2026-10-28) built "The Last Ferry" from an empty project. It used the browser entry (`dev.ps1 -Browser`'s way, its own
orchestrator and state folder) and the real engine, one job at a time:

- 5 shots, 2 characters, 2 places, 1 prop;
- about 60 GPU jobs;
- 4 clips (one with a camera move);
- a Clay final shot;
- an Episode cut, the Resolve export and the movie.

**Fixed in U0** (2026-10-28 23:34 in the journal): F27, F29, F34, F41, FE#1, FE#2, FE#3, BE#1, BE#3 and RC#1. The rest wait for their wave.

The project is `F:/loom2-projects/ux-walk-last-ferry`. The full report, with screenshots, was published to the author as an artifact. Tests at the start
of the session: offline 692 passed; Vitest 597 passed and 3 skipped.

## 1. The walkthrough: F1–F44

| # | Where | Finding |
| --- | --- | --- |
| F1 | frame | With no project open, every suite says "open or create a project", but has no button for it |
| F2 | New project | The format is fixed text (`ProjectDialog.tsx:38`). The backend takes any aspect, size and fps (`workspace.py:22`), so there is no 25 fps, no 2.39:1 and no vertical project |
| F3 | World › Styles | The style sample is rendered on one app-wide scene ("A stealthy cyber spy … office"), whatever the story |
| F4 | World › Library | Adding a look entry queues a GPU picture job without saying so |
| F5 | frame | **Bug.** In focus mode the panel and Inspector keep their widths in zero-width grid columns: the panel covers the stage and the page scrolls sideways (`frame.css:46`, `:74`, `:129`) |
| F6 | frame | Tab, the key for moving between fields, toggles focus mode outside a field (remappable, but a surprise) |
| F7 | World › Library | Built-in look tiles are one identical glyph per field until their pictures are made |
| F8 | Flow | The outline lists nodes in no useful order |
| F9 | Flow | Shot → Dialogue keeps the description in the record but hides it. **F9b:** Image then uses the node's title as the lead text |
| F10 | World | *Make the Flow from the spine* is linear only |
| F11 | Cast | A place gets a character's coverage grid (close-up … full-body × front … back) |
| F12 | Cast | New prop / New place reuse the character's copy; a prop gets the portrait / full-body grid |
| F13 | Cast | A character's candidate offers *Use as the set picture* |
| F14 | Cast | Training readiness is a bare number (7 with one reference, 12 "thin" with four) |
| F15 | Cast | Making the hero moves the picture between pages; the hero then counts as a reference |
| F16 | Image | **Bug.** *Give ‹name› a look* renders the whole panel. A second subject left on it would be filed as the cast character's candidate (`generateStore.ts:575-590`) |
| F17 | Flow | The Dialogue Inspector scrolls sideways and cuts *Voice all lines* off |
| F18 | Image | The ten built-in lighting presets are identical suns in the popover until *words* is on |
| F19 | Flow | A Choice node offers shot verbs (New Shot from this Shot, Board, Scene) |
| F20 | Flow | A new node lands on top of the others; fit-to-view zooms the text down to about 6 px |
| F21 | Flow | *Validate* shows "5 problems" in orange, all advisory; the count can't be clicked |
| F22 | Flow | (works) wiring by mouse: an edge's right-click deletes it, handles drag, a Choice's options have their own ports |
| F23 | Image | A batch header shows the raw JSON prompt |
| F24 | Shots → Image | A Shot node has no "who is in it": every trip to Image started without the character, and re-entering the same shot forgot her again |
| F25 | Shots → Image | The last shot's look carried into the next (by design, D125) |
| F26 | frame | Clicking the active rail icon collapses the panel, globally; a For trip then lands with no Make column |
| F27 | Image | **Bug (rule 5).** The estimate ignores references: it promised ≈ 42 s for frames with 8–10 references at 1024² that ran 117 s per step (≈ 16 min an image). **F27b:** at 512², 10.5 s per step (≈ 90 s). Nothing warns or downscales (`engine/graphs.py:1829-1845`) |
| F28 | Shots board | A click anywhere on a row runs a cell's step, so selecting a row opened a trip to Image |
| F29 | Shots → Animate | **Bug, seen live (FE#1).** The seal's clip trip kept Departure's prompt *and* its Fun-Camera Zoom Out; the clip was queued with a camera move it should not have had |
| F30 | Cast | Cast counted Ines in one shot (as a speaker) when she was in four frames |
| F31 | Shots → Image | Props named in a line are not added: Ines holds a phone-like thing, not the letter |
| F32 | Cast | The first A-pose queues the body fit without saying so. It failed ("does not show the whole figure"), shown only in a toast. **F32b:** the A-pose candidates have the feet on the frame's bottom edge |
| F33 | Episode | The Assemble sheet's "2 shots · 2 without a clip yet" was for a route of four shots |
| F34 | Animate › Clay | **Bug, reproduced in isolation.** Clay cannot render in any dev build since V82 (8e52771). StrictMode remounts the viewport's effect on the same canvas after `forceContextLoss()`, so the second renderer gets a dead context ("Cannot read properties of null (reading 'precision')"). `scripts/dev.ps1` is affected; the e2e (a production build) is not |
| F35 | Clay | A new figure landed 2.11 m in the air, outside the shot camera's view |
| F36 | Clay | The motion library's clip list is two rows tall; its search filters files, not clips |
| F37 | Clay | Applying a walk along a path baked 329 keys and stretched the stage range from 120 to 328 frames without a word |
| F38 | Final shot | The plate of a preset set read "The room is empty: … bare walls and floor" (on a street), with no scene, no style and no frame: a concrete box. **F38b:** *Make it a Cast place…* exists only for image sets |
| F39 | Episode | A dialogue shot's clip (5.1 s) is shorter than its lines (10.2 s); Tomas's line and its subtitle play over the next shot |
| F40 | Episode | The EDL and FCPXML name every clip `proxy.mp4` and point at the proxies (the 16 fps clips are not at the cut's rate) |
| F41 | Final shot | **Bug.** The foot ("the newest final's next step") takes `.at(-1)` of a newest-first list: it performed and assembled Final 1, not Final 2 (`finalShot.ts:607-610`) |
| F42 | Final shot | A figure walking away was performed facing the camera; nothing warned |
| F43 | Final shot | With the built set, the plate showed black seams where faces were never filled; with a back view made, Ines still faced the camera |
| F44 | Final shot | The finals poll logs a 404 per final every 3 s; a composition render's toast quotes a seed |

**Measured on the rig during the walkthrough** (FLUX.2 dev unless said; draft sizes):

| What | Time |
| --- | --- |
| A casting image, 0 references | 42 s; the session's first, 85 s |
| A frame with 8–10 references at 1024² | 117 s per step (cancelled) |
| The same at 512² | 83–108 s |
| Klein 9B A-pose / set picture | 32–60 s / 11 s |
| Wan 2.2 Draft clip, 81 frames at 832×480 | 173–196 s |
| Fun-Camera Zoom Out | 183 s (the tone match took the first frame's MAE from 17.7 to 5.0) |
| Wan Animate, one character, 65 frames | 152–162 s |
| Matte | 27 s |
| Assembly (CPU) | 13 s |
| Composition render (CPU) | 3 s |
| The movie (CPU, 20 s at 1080p, −16 LUFS) | 20 s |

## 2. The code review (2026-10-28)

Four read-only reviewers, each finding read in the code. *Verified* means read by the study's author or seen in the walkthrough. *Reproduced* means a
reviewer ran it against a throwaway project.

### FE: the Story frontend

| # | Severity | Finding | Where |
| --- | --- | --- | --- |
| FE#1 | high, seen live | Animate's For trip keeps the last shot's start, prompt, beats and camera | `makeFor.ts:130-141` |
| FE#2 | high, verified | The board's *In cut* compares with the current version, Episode with the approved one | `board.ts:106-107` vs `episode/bin.ts:12-16` |
| FE#3 | high, seen live | The board never marks Frame, Stage, Clip, Final or Lip-sync stale | `board.ts:95-104` |
| FE#4 | medium | A cell's verb reads the selection after an await; a click can run on the wrong shot | `ShotsBoard.tsx:91` |
| FE#5 | medium | Cells ignore their command's `when`; a Voice click re-voices every line | `ShotsBoard.tsx:89` |
| FE#6 | perf | Whole-project fetches on every keystroke | `ShotsBoard.tsx:59`, `StoryParts.tsx:128` |
| FE#7 | medium | Store reloads have no sequence guard | `storyStore.ts:547-561` and others |
| FE#8 | medium | Idea edits are not chained (409s) | `ideasStore.ts:63-67` |
| FE#9 | medium | References ✓ with only the hero | `castReady.ts:36` |
| FE#10 | medium | *Back* always returns to Shots | `store/origin.ts:106-111` |
| FE#11 | low | The lip-sync line choice carries between shots | `storyStore.ts:446` |
| FE#12 | low | The For chip outlives its shot or version | `store/origin.ts:30-33` |
| FE#13 | cleanup | The Flow rebuilds every node on many changes | `FlowCanvas.tsx:127-146` |
| FE#14 | rule 11 | Four empty states are paragraphs on screen | `StoryParts.tsx:656`, `:744`; `Ideas.tsx:89`, `:127` |
| FE#15 | low | The board has no keys, though its foot promises Ctrl+Enter | `ShotsBoard.tsx:66` |

### BE: the Story backend

| # | Severity | Finding | Where |
| --- | --- | --- | --- |
| BE#1 | high, reproduced | Ids from URLs become paths; a `%5C` deleted `project.json` on a throwaway project | `timelines.py:359-366`, `:441-451`; `story.py:1190`, `:1396`; the same pattern in stages, voices, loras, ideas, groups, finals |
| BE#2 | high | One FilmCraft session, locked per request, not per operation: a movie render can act on another cut | `filmcraft.py:75-83`, `cuts.py:605-613` |
| BE#3 | high, verified | Run stale replays the whole `seeds` list: new random seeds, a batch re-run, chained clips × N | `shot_recipe.py:298-314`, `finishers.py:414-416` |
| BE#4 | high | Profile, world, graph and idea read-modify-writes take no lock | `story.py:1893`, `:1951-2305`, `:1402`; `ideas.py:189` |
| BE#5 | high | A cut's 409 check and its change are not atomic; a rollback can wipe an edit that answered 200 | `routes/timelines.py:210-220`, `cuts.py:628-648` |
| BE#6 | risk | `Cuts.write` has no rollback | `cuts.py:567-602` |
| BE#7 | high, verified | Voice results land by line index | `story.py:1362-1373` |
| BE#8 | risk | Voice jobs are submitted from a worker thread (V22's pattern) | `routes/story.py:2097` |
| BE#9 | high | `sync_lines` changes a cut without a revision bump | `cuts.py:1291-1338` |
| BE#10 | low | `patch_shot` can half-apply before a 422 | `story.py:958-985` |
| BE#11 | low | Voice all lines can queue partly; lip-sync accepts a missing asset | `routes/story.py:2127-2132`, `:2203-2212` |
| BE#12 | cleanup | Markers re-added at a hard-coded 24 fps | `cuts.py:1133` |

### RC: the commits since the last review (f68c6f0..e8ce296)

| # | Severity | Finding | Where |
| --- | --- | --- | --- |
| RC#1 | high, verified | Closing the detached loupe window shuts the app down (any window's CloseRequested) | `src-tauri/src/lib.rs:283-293` (D155) |
| RC#2 | high | Esc on an inline text edit restores the whole layer stack as it was | `editorStore.ts:342`, `:1654-1710` (D154) |
| RC#3 | high, reproduced | Fill Hero with more than 4 references fails at run time | `engine/pipeline.py:189-192`, `:299-300` (D152) |
| RC#4 | high | Pixel edits to a text layer are lost at its next text edit | `editorStore.ts:1657-1666` (D154) |
| RC#5 | medium | The PSD type layer is written as point text, anchored at the left | `psdExport.ts:84-93` (D154) |
| RC#6 | medium, reproduced | A camera move is accepted on any model | `engine/graphs.py:151-152`, `finishers.py:297-303` (D156) |
| RC#7 | medium | With split panes both answer the detached window | `CatalogueSuite.tsx:132-134` (D155) |
| RC#8–RC#12 | low | `refreshText` size; empty undo rows; the shared Tauri capability; TextBlock box unvalidated; V1 half fixed | `editorStore.ts:1673-1683`; `EditSuite.tsx:145`; `capabilities/default.json`; `documents.py:99`; `catalogue.py:617-634` |

Checked and correct: V7, V21, V22 / V30, V34, V36, V44, V55, V65, V79; D150's rollback; the tone-match maths; SeedVR2's wiring.
