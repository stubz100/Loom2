# 30 · RC4's study — FilmCraft for the cut editor

Status: **study, 2026-10-24; answered the same day → D126 (§10); CE1 built (§11); CE2 built (§13); CE3 built (§15); D127 (§16): the channel strip and VST3 chains — AU1 built (§17), AU2 built (§18), AU3 built (§19), AU4 built (§20) — D127 done; CE4 built (§21); CE5 built (§22) — D126's cut editor is built.** D96 planned RC4 as "FilmCraft reviewed as 03 reviewed EffectCraft
(what to reuse, how), then the multi-track cut editor that replaces the single-lane Episode" ([05](05-flow-nodes-as-shot-recipes.md)
§6), with O6 (a scene grade and shot-match in the cut, [06](06-continuity-across-shots.md)) attached. RC1–RC3 are built
([28](28-recipe-graph.md), [29](29-movie-render.md)); this is the study, measured where it could be (§3, the probe E32).

## 1. Where the Episode is

The Episode is the cut: about 1,240 lines of client code over `timelines/<id>.json` (D83, SY4, D125's SP6, RC3).

| It has | It lacks for a finished episode |
| --- | --- |
| one video lane; clips by their source frames; a dissolve as an overlap | more tracks: an insert, a title, an overlay over the shots |
| the cut assembled from a Flow route, a *changed* mark, *Update* | trims beyond in/out: roll, slip, slide, razor, ripple delete |
| the exports for Resolve (FCPXML with the voice lane, EDL, SRT, markers) | sound in the preview at all; music and effects; gain, ducking, loudness |
| the draft render and the movie (RC3: RIFE, the voice lane, an MP4) | the lines placed by hand (they are laid evenly across their clip) |
| a checklist | colour: a grade per scene, a shot matched to its neighbour (O6) |
| | captions styled or burned in; titles |

## 2. What FilmCraft is

Reviewed 2026-10-24 at `F:\source\repos\filmcraft` (v0.5.0, `764723f`, 2026-10-10):

- **A clean-room Premiere Pro in pure Rust**, EffectCraft's sibling in the ArtCraft family: 43 crates and 3 apps, about 322k lines,
  2,228 tests. 848 commits in 10 days (2026-09-30 → 10-10), mostly the owner's.
- **Licence:** MIT OR Apache-2.0. The ArtCraft marks in `docs/brand/` must not ship; fonts are OFL-1.1; symphonia (MPL-2.0, unmodified)
  decodes MP3 / FLAC. No GPL, no FFmpeg, no git dependencies. Its own H.264 and AAC encoders carry no note on codec patents.
- **Maturity: alpha.** Its ROADMAP gives ≈ 87 % of the feature list and ≈ 50–60 % "ready for real work" (correctness 60–70 %,
  performance 35–40 %). Pull requests are **not** gated by tests (CI only packages); the gates run locally.
- **The model is Premiere's:** a project of bins and items (media, sequences, subclips, adjustment layers, graphics); a sequence of
  video and audio **tracks** (any number), each of items with start, duration, source in, speed, link, effects, markers and gain;
  transitions between items (84 video, 3 audio); effects with keyframes; markers (comment, chapter …). Time is an integer tick
  (254,016,000,000 a second, exact for every frame and sample rate). Projects are `.fcproj` (versioned JSON, schema 13, migrated on load).
- **Every edit is a command** (`Session::execute(id, json)`, ≈ 650; undo by project snapshot): `timeline.place / trim / roll / slip /
  slide / razor`, `edit.rippleDelete`, `sequence.applyVideoTransition`, `clip.speedDuration`, `markers.addChapter`, `mixer.*`,
  `lumetri.*`, `captions.*` …
- **The engine is layered** like EffectCraft's (`cargo xtask layers`: no egui / winit below the UI); the engine crates build for
  wasm32, and a web build exists.
- **Rendering:** a CPU reference renderer (premultiplied linear f32) and a wgpu compositor for the app's monitors only, checked against
  it. **Every headless path (CLI, MCP, export) is CPU.** Playback in the app: quality steps full to ¹⁄₁₆, render previews in to out.
- **Export:** H.264 (its own encoder; CBR / VBR, not CRF), ProRes, DNxHR, APV, MXF, image sequences, WAV; AAC or PCM; loudness
  normalisation (R128, −23 LUFS by default); captions burned in or as SRT / VTT; reproducible byte for byte. No AV1 / VP9; HEVC only
  through NVENC or VideoToolbox (none on AMD).
- **Colour:** Lumetri (basic, creative, curves, wheels, HSL, vignette, input and look LUTs, 18 presets), **shot match**
  (`lumetri.applyMatch`: Oklab statistics with skin protection, solved into an editable grade), **adjustment layers** (a grade over the
  tracks beneath: a scene grade), scopes. Rec.709 / Rec.2100; no OCIO. CPU only.
- **Audio:** track mixer with automation, sends, submixes; clip gain and volume keys; ≈ 40 effects; R128 metering; **ducking**
  (`essentialSound.generateDucking`); constant-power crossfades. Resampling is linear only.
- **Captions:** SRT, WebVTT, SCC, TTML … in and out; caption tracks with styles; burn-in at export. Whisper transcription is an optional
  build feature (CPU, models fetched on first use).
- **Interchange:** FCPXML 1.9–1.11, EDL, FCP7 XML, OTIO, AAF / OMF, in and out.
- **Interfaces:** `filmcraft-cli` (`exec`, `run` a JSON-lines script, `import`, `export`, `render` one frame, `inspect`, `mcp`), an MCP
  server over stdio (headless) or bridged to the running app, and the app's loopback control port.
- **Its limits that matter here:**
  - **a 16 fps clip on a 24 fps sequence repeats frames** (frame sampling; "optical flow" is frame blending, and only when the speed
    changes): loom2 keeps RIFE (D27) and hands FilmCraft conformed media;
  - time remapping is stored but not rendered (constant speed and reverse work);
  - its FCPXML import ignores FCP's spatial conform (§3);
  - undo deep-clones the project (fine for an episode).
- **EffectCraft already uses FilmCraft's crates** (codecs, media, frame, colour, H.264 / ProRes / AAC encoders, interchange) pinned at
  `2c5ba7a` (10-03). The two are separate binaries; there is no dynamic link between them.
- **The user interface is egui.** As with EffectCraft, none of it can live in loom2's React app; its timeline, Lumetri panel and mixer
  are design references.

## 3. The probe (E32, measured 2026-10-24)

`filmcraft-cli` built in release from the checkout into a scratch target (2 min 31 s, 34.6 MB), a scratch data folder. **Decoding:** the
CLI decodes in hardware by default (Media Foundation on the card), and a `prefs.set` lasts only for its process; the first render, export
and session runs had used it. The figures below are re-measured with `playback.hardwareDecoding = off` in each process (software decoding,
CPU only) — the session numbers came out the same, and the parity too.

The input is the A1 rig's cut from RC3's measurement: the composition (121 f @ 24) dissolving over 12 ticks into Mara's
performance (77 f @ 16), two voiced lines on the first, at 1920×1080 @ 24.

**a · loom2's Resolve FCPXML, imported.** One sequence, 4 media linked, nothing offline, no warnings; the lines on A1 at 0 and 60 as
exported, the marker kept. But:

- **the dissolve is lost** — loom2 writes the next clip *overlapping* the previous one on the spine; FCPXML lays spine clips end to end
  and a transition straddles the cut on the clips' handles. FilmCraft put the second clip on V2 and made the dissolve a fade-out of the
  first. Resolve reads the same file (the author's Resolve check is still owed). **A defect in loom2's exporter: FC1**, fixed with this
  study (§7): the cut now sits in the overlap's middle, each clip trimmed to it and the rest its handle under the transition, a line
  in a given-up head riding the clip before. Re-exported, the A1 cut imports as **one track** — the clips 0–115 and 115–225, the
  Cross Dissolve from 109 for 12 frames between them, the lines on A1 — the same structure as the cut built by commands (b);
- the 832×480 proxies sit at native size in the 1920×1080 frame: FCP's default conform is *fit*, which FilmCraft's importer does not
  apply.

![FCPXML import: native size; mid-dissolve shows only the second clip](img/30-fc-probe-fcpxml.jpg)

**b · the same cut built by commands** (a new sequence, `file.import`, `timeline.place` ×4, `sequence.applyVideoTransition` 12 frames on
the second clip's head, `clip.scaleToFrameSize`): 225 frames, the dissolve from 109 for 12 frames on the cut at 115 — **loom2's lane
exactly**. Exported (`filmcraft-cli export --format h264`) it **matches loom2's own movie**: mean difference 1.5 / 4.1 / 0.4 levels on
frames 48 / 114 / 160 (the 16 fps clip frame-sampled there, RIFE-conformed in loom2's), the sound identical (both lines where RC3 puts
them, the same level).

![FilmCraft's export (top) and loom2's movie (bottom): frames 48, 114, 160](img/30-fc-probe-parity.jpg)

| | loom2's movie (RC3) | FilmCraft export |
| --- | --- | --- |
| H.264 + AAC, 225 frames at 1080p | 10.7 s (RIFE conform + x264 CRF 18) | **3.8 s** (17.6 MB) |
| ProRes 422 + PCM | — | 4.2 s (142 MB) |
| with a shot-match and a graded adjustment layer | — | 6.6 s |

**c · frames for the viewer.** One process a frame (cold, hardware decoding): 100–160 ms at any size. **One warm `filmcraft-cli mcp` session** (the way
`effectcraft.py` drives EffectCraft), `render_frame` as PNG:

| | ½ (960×540) scrub | ½ play | ¼ scrub | ¼ play |
| --- | --- | --- | --- | --- |
| the plain cut | 10 ms (p90 20) | 10 ms → 98 fps | 4 ms | 4 ms |
| + shot-match on one clip + a scene grade (adjustment layer, *Golden Dusk*) | 15 ms (p90 25) | 15 ms → 67 fps | 6 ms | 6 ms |

**d · O6 headless.** `lumetri.applyMatch` on Mara's clip against frame 48 of the composition: 0.24 s for the whole run, distance
0.052 → 0.036, an editable grade. An adjustment layer over the cut with a preset grades both shots.

![Before (top) and after (bottom): the scene grade over both shots; the matched clip pulled toward the room](img/30-fc-probe-grade.jpg)

Not measured: memory beside ComfyUI (FilmCraft's own figure: ≈ 1.4 GB RSS exporting 1080p), an episode-length cut, PNG-sequence masters
as the media.

## 4. How loom2 would use it

The EffectCraft precedent (D113, D114) is the pattern: **loom2 keeps its mouse-first React UI**; the sibling's engine runs as a pinned,
prebuilt `filmcraft-cli` beside the orchestrator — a session for the edits and the viewer's frames, the CLI for the render as a job.

| Route | What | Verdict |
| --- | --- | --- |
| **F1 · its own window** | loom2 writes the cut as a `.fcproj` (conformed media), *Finish in FilmCraft* opens the app on it; the movie comes back as a render | a working escape hatch, ≈ 2 days; the author edits outside loom2 in a keyboard-and-mouse Premiere UI, and nothing comes back but the file. **Later, optional** |
| **F2 · inside Story's Episode, on FilmCraft's engine** | loom2's multi-track editor (React); every edit a FilmCraft command in a warm session; the viewer's frames from it over loopback HTTP (§3c); the movie by `file.exportMedia` as a CPU job | **proposed** — D114's shape for the cut; the probe shows the commands reproduce loom2's lane and its movie |
| F3 · loom2's own editor, FilmCraft only for the export | the lane grown to tracks in TypeScript; FilmCraft renders at the end | not proposed: the grade, the match and the mix would show only after a render |
| F4 · the wasm build in the page | `filmcraft-web` (single-threaded, WebCodecs) as the viewer | not proposed now: 03 §5.2's R1 verdict holds (memory, CPU-side speed); kept open |

**What stays loom2's** under F2:

- **the cut's document** — `timelines/<id>.json` grows from one lane to tracks (a schema step), keeping the route, the shots' stamps,
  the *changed* mark and the lines' link to the Flow. The `.fcproj` is **built from it** by commands, like an index (rule 4: files are
  truth, indexes are rebuildable), and every edit goes to both: the document, and the same command to the warm session so the viewer
  follows without a rebuild. A FilmCraft result loom2 keeps (a shot-match's solved grade) is written back into the document as values;
- **RIFE** — a 16 fps shot is conformed once (D27) and FilmCraft gets the 24 fps frames;
- the masters, the Catalogue, lineage, the queue (D97), the mouse-first commands (D32).

## 5. What the cut editor does (first version)

- **Tracks:** V1 the shots (assembled from a route as today, *changed* / *Update*), V2 inserts and titles; A1 the dialogue (each spoken
  line its own clip, placed as today and then moved by hand — the line keeps its place), A2 music, A3 effects. More tracks by `+`.
- **Edits** (each a loom2 command with its mouse placement, running FilmCraft's): select, move, trim, roll, slip, slide, razor, ripple
  delete, dissolve / dip to black, constant speed, a freeze frame; snapping; undo by the document's stack.
- **Sound:** clip gain and volume keys on the clip; track volume; *Duck the music under the dialogue*; the movie's loudness at export.
- **Colour (O6):** *Grade the scene* — an adjustment layer over a scene group's shots with a preset or a LUT look; *Match to…* — a shot
  matched to a reference shot (FilmCraft's solve, editable).
- **Captions:** a caption track from the Dialogue lines (the SRT's text and timing); *Burn in* at export.
- **The viewer:** FilmCraft's frames at ½ (¼ while playing fast), sound in the page from the document's audio clips (Web Audio).
- **The movie:** FilmCraft's export as the queue's CPU job — H.264 for viewing, ProRes for Resolve, with loudness; the Catalogue video as
  RC3. RC3's `run_movie` stays as the fallback when FilmCraft is not built (like the composition render without EffectCraft).

Not in it: speed ramps (not rendered by FilmCraft), multicam, the audio mixer's automation modes, effects beyond the grade, F1.

## 6. The GPU rule and memory

- Every headless FilmCraft path is CPU (§2), so the session never takes the card. **Hardware decoding is switched off** at the
  session's start (`playback.hardwareDecoding = off`; Media Foundation decode would hold VRAM beside ComfyUI).
- As for EffectCraft (D113): while the queue runs a GPU job, the viewer renders on demand only; the movie is a queued CPU job (one job at
  a time, D97). The RIFE conform stays a short Vulkan step inside a queued job, as the final's assembly does.

## 7. A build plan

| Wave | Content | Days |
| --- | --- | --- |
| **FC1 · the FCPXML dissolve** ✓ with this study | spine clips end to end, the transition on the cut over the handles (§3a) | 0.5 |
| **CE1 · the engine** | `engine/filmcraft.pin.json` + `scripts/build_filmcraft.py` (`--check` in CI), `loom2/filmcraft.py` (the session, as `effectcraft.py`), a fake for the tests; the cut's `.fcproj` built by commands from the document, with conformed media; the movie by `file.exportMedia`; a rig check (memory beside ComfyUI, an episode-length cut) | 3 |
| **CE2 · tracks** ✓ built 2026-10-24 (§13) | the document's schema step to tracks; the multi-track timeline in Story · Episode (V1–V2, A1–A3, `+`); the edits as commands; the viewer's frames from the session | 4–5 |
| **CE3 · sound** ✓ built 2026-10-24 (§15) | the lines as A1 clips, music and effects from the Catalogue's audio, gain and volume keys, ducking, loudness at export; sound in the page | 2 |
| **CE4 · colour (O6)** | *Grade the scene* (adjustment layer per scene group), *Match to…*, presets and LUT looks | 2 |
| **CE5 · captions and delivery** | the caption track from the lines, burn-in, H.264 / ProRes presets; the Resolve folder kept | 1–2 |

**≈ 12–15 days**, each wave with its tests (offline on the fake, e2e on the fake, a rig check on the pinned binary), screenshots and
journal entry.

## 8. Risks

- **Alpha and moving fast:** 10 days of history, schema 13, no CI test gate. The pin, a fake in loom2's tests, the document as loom2's
  truth (a FilmCraft schema change costs a rebuild of the `.fcproj`, not the author's work) and a rig check per pin move.
- **Interchange gaps:** FCPXML import ignores spatial conform, so loom2 builds the cut by commands (§3b), not by import.
- **Frame rates:** FilmCraft repeats frames for a 16 fps clip; loom2 conforms first.
- **Codec patents:** FilmCraft's own H.264 / AAC encoders come without a licensing note. loom2 is the author's tool on one machine;
  noted, not a blocker for this use.
- **Build cost:** 2.5 min for the CLI in release on this machine (FilmCraft quotes 6–7 GB a full build); rebuilt only when the pin moves.
- **FC1 was a live defect** in the Resolve export since P17 (D83): any cut with a dissolve. Fixed now; the author's Resolve check owed
  since 2026-10-15 should use a fresh export.

## 9. Questions for the author — answered 2026-10-24 (D126)

The answers: **1 (a), 2 (b), 3 all, 4 yes in the first version, 5 FilmCraft's export, run inside loom2** ("not by using filmcraft itself": the author never opens FilmCraft's app). §10 is the plan as decided.


1. **Where is the cut edited?** **(a) inside Story · Episode on FilmCraft's engine (F2, recommended)**, as D114 did for the composition
   with EffectCraft; or (b) in FilmCraft's own window (F1), opened on the cut and rendered back.
2. **Which file is the cut's truth?** **(a) loom2's cut document, grown to tracks, with the FilmCraft project built from it
   (recommended)**; or (b) the `.fcproj` itself (every FilmCraft feature persists, but loom2 follows FilmCraft's schema).
3. **The first version's tracks:** **V1 shots, V2 inserts and titles, A1 dialogue, A2 music, A3 effects (recommended)** — or fewer?
4. **Colour in the first version** (O6: a grade per scene, a shot matched to another): **yes (recommended)**, or after sound?
5. **The movie:** **FilmCraft's export once it is built, RC3's render as the fallback (recommended)**; or keep RC3's as the only one.

## 10. As decided (D126)

**The cut is a FilmCraft project.** Each cut is `timelines/<id>/cut.fcproj`, written by FilmCraft (atomic saves, its own migrations).
Everything about the cut lives in it, loom2's links included, as item metadata (verified with the probe's build: `metadata.set` keeps any
field through a save):

| loom2's link | where in the project |
| --- | --- |
| a take's Story shot, version, Flow node, loom2 clip | the media item's `loom2.shot`, `loom2.version`, `loom2.node`, `loom2.clip` |
| a spoken line's Flow node and index | the audio item's `loom2.node`, `loom2.line` |
| the cut's route (D125 S13) | the sequence item's `loom2.route` (JSON) |

`timelines/<id>.json` stays as the cut's registry record (id, name, the file, the format, a revision for the client's 409s); the lanes
loom2 shows, assembles, marks *changed*, checks and exports are **read from the project** (V1's items and transitions → today's lane).
Today's cuts are converted once by commands. A 16 fps take enters conformed by RIFE (cached beside its master); the masters go in as PNG
sequences, not the proxies.

**The engine** is the pinned `filmcraft-cli` (`engine/filmcraft.pin.json`, built by `scripts/build_filmcraft.py` from the checkout
beside this repository; `--check` in CI), driven as one warm MCP session by `loom2/filmcraft.py` (as `effectcraft.py`), hardware decoding
off; a fake (`tests/fake_filmcraft.py`) for CI and the e2e; the real binary on the rig.

**The movie** is FilmCraft's `file.exportMedia` run as loom2's queued CPU job (H.264 or ProRes, loudness, captions burned in when asked),
into the cut's folder and the Catalogue as RC3. RC3's render stays where FilmCraft is not built.

| Wave | Content | Days |
| --- | --- | --- |
| **CE1 · the engine and the cut file** ✓ built 2026-10-24 (§11) | pin, build script, CI check, Settings › FilmCraft; the session and its fake; `cut.fcproj` per cut (made and converted by commands, conformed masters, the links as metadata); the lane read from it, every existing Episode verb on it (assemble, *changed*, update, exports, checklist, RC3's movie by FilmCraft's export); a rig check (the real binary, an episode-length cut, memory beside ComfyUI) | 4 |
| **CE2 · tracks** | the five tracks (V1 shots, V2 inserts and titles, A1 dialogue, A2 music, A3 effects; more by `+`); the edits as commands (move, trim, roll, slip, slide, razor, ripple delete, transitions, speed, freeze); the viewer's frames from the session | 4–5 |
| **CE3 · sound** | the lines as A1 clips (placed as today, then moved by hand), music and effects from the Catalogue, gain and volume keys, ducking, loudness; sound in the page | 2 |
| **CE4 · colour** ✓ built 2026-10-24 (§21) | *Grade the scene* (an adjustment layer over a scene group's shots), *Match to…*, presets and looks | 2 |
| **CE5 · captions and delivery** ✓ built 2026-10-24 (§22) | the caption track from the lines, burn-in, H.264 / ProRes presets, the Resolve folder from the project | 1–2 |

## 11. CE1 as built (2026-10-24)

- **The engine:** `engine/filmcraft.pin.json` (FilmCraft 0.5.0 at `764723f4`, 34,621,952 B), `scripts/build_filmcraft.py` (`--check` in
  CI; the release build takes 2 min 30 s), Settings › FilmCraft (`cli`, `threads`, `timeout_s`). The session (`loom2/filmcraft.py`) shares
  its process and requests with EffectCraft's in `loom2/mcp_session.py` (moved out of `effectcraft.py`); every start sets software
  decoding, scale-to-frame and the image-sequence rate. A fake (`tests/fake_filmcraft.py`) for the offline suite and the e2e; the suite
  never picks up a built binary (`LOOM2_FILMCRAFT_CLI` in `conftest.py`).
- **The cut file** (`loom2/cuts.py`): `lane()` reads V1 from the project's JSON without FilmCraft; `Cuts.write` rebuilds V1 and the lines
  on A1 by commands (cleared, placed end to end, dissolves on the cut, the route on the sequence, loom2's unused items deleted).
  **One project item per take as used** (the take with its shot's stamps): the e2e put one take on the lane as a shot and as a plain clip,
  and per-file stamps let the last write win. The store reads a cut's lane from its project; with FilmCraft built a new cut is a project
  and today's cut is converted on its first change; without it a converted cut is read, not changed (422).
- **A 16 fps take** enters as its proxy and is conformed by RIFE in the queued movie job, then swapped in (`clip.replaceFromBin`, the source
  in kept; the conformed frames cached in `clips/<id>/conform24/`): RIFE takes the card, so it never runs inside an edit (D97). RIFE
  numbers its frames from 1 — the import names the first one it wrote (found on the e2e; the tests' fake RIFE now numbers the same way).
- **A spoken line** that would overlap the one before it on A1 starts where that one ends (a track holds one clip at a time); the
  exports still lay the lines evenly until CE3.
- **The movie** of a FilmCraft cut is `filmcraft-cli run` (preferences, then `file.exportMedia`) in a process of its own, cancellable; the
  Catalogue copy carries `engine: filmcraft`. RC3's render stays for cuts that are not converted and where FilmCraft is not built.
- **On the rig** (`scripts/ce1_acceptance.py`, 14/14, a copy of the A1 project): converted in 0.26 s with the lane exact and both lines on
  A1; FilmCraft's movie in 5.9 s with Mara conformed (RC3's own render of the same lane: 12.0 s), the same 225 frames at 1920×1080 (mean
  difference 1.24 / 4.0 / 0.32 / 0.36 levels on frames 48 / 114 / 160 / 224) and the same sound; an edit round-trips; the export's peak
  memory 1.65 GB (4.0 s); warm frames at ½ 12.8 ms; software decoding in the session and the export.

## 12. CE2 · tracks — the plan (2026-10-24)

**The commands, probed on the real binary** (a copy of CE1's converted A1 cut): `timeline.setTrack {name}` names a track; a new
transition on an edit replaces the old (`dip_to_black` over the dissolve); ripple trim, roll, slip and slide move what Premiere's do; razor
splits and the dissolve follows the new piece; `timeline.move` across tracks takes its transition along; `clip.speedDuration` at 50 %
keeps the length; `clip.frameHold` splits and holds; `sequence.addTracks` adds V3 / A4; `edit.undo` undoes in the session;
`file.exportInterchange` writes FCPXML and EDL. **A ripple delete is refused** when a sync-locked track has a clip in the way (the
dialogue on A1) — FilmCraft's message goes to the author as it is. `edit.clear` takes clips, not a transition.

**What changes for a FilmCraft cut** (a cut that is still a record keeps today's single lane):

- **The tracks are read from the project** (`cuts.tracks()`: every track's items with their media, links, speed and hold; the
  transitions) and shown as the Episode's timeline: V tracks above, A tracks below, one row each, the dialogue lines as clips on A1.
- **Every edit is a FilmCraft command** through one route (`POST /timelines/{id}/edit`, a whitelist of the commands above, the record's
  revision guarding it like a PUT) — move, trim (ripple), roll, slip, slide, razor, ripple delete, lift, speed, freeze frame, a dissolve or
  a dip on an edit, a track's name, lock and mute, add a track. Undo and redo are FilmCraft's, in the session.
- **Placing** a Catalogue clip, picture or sound on a track (`POST /timelines/{id}/place`): imported once as a project item with its
  links, placed where it is dropped.
- **The Flow's verbs stay**: *Assemble* rebuilds V1 (it asks first, as now); *Update* swaps a take in place (`clip.replaceFromBin`), so the
  edits around it survive; the checklist and the *changed* marks read V1's takes in order.
- **The viewer** shows FilmCraft's frames from the session (`GET /timelines/{id}/frame`: ½ when still, ¼ while scrubbing or playing).
- **The exports** of a FilmCraft cut are FilmCraft's FCPXML and EDL (what the project holds: gaps, speed, every track), the SRT and the
  markers from the project's dialogue clips and takes; *Render draft* is FilmCraft's export to PNG → a clip.
- **Mouse-first (D32):** the edit tools (Select, Ripple, Roll, Slip, Slide, Razor) on the toolbar with Premiere's keys as accelerators;
  a clip's right-click (speed, freeze, dissolve / dip in and out, lift, ripple delete, move to track ▸, rename, update to the approved
  take); a track header's right-click (rename, lock, mute, add a track).

Slices: **CE2a** the server (tracks, the edit and place routes, frames, the exports and the draft for FilmCraft cuts, *Update* in place);
**CE2b** the timeline (tracks, tools, menus, drops); **CE2c** the viewer. Each with tests on the fake, the e2e and a rig check.

## 13. CE2 as built (2026-10-24)

**The server** (`loom2/cuts.py`, `routes/timelines.py`):

- `tracks()` reads every track of a FilmCraft cut from its project (clips with their kind — take, line, video, picture, sound,
  adjustment — their media, speed, hold and loom2's links; the transitions); `GET /timelines/{id}/tracks`.
- `POST /timelines/{id}/edit` runs the editor's steps in the session: a whitelist of FilmCraft's commands (`EDIT_COMMANDS`: move, trim,
  roll, slip, slide, razor, rate stretch, a track's settings, select, ripple delete, lift, transitions, close gap, add / delete tracks, speed,
  freeze, enable, rename) and `loom2.removeTransition` — **FilmCraft (764723f) has no command to delete a transition**: the clip it leads
  into is lifted and placed back with its attributes copied over (`edit.copy` / `edit.pasteAttributes`) and its speed set again.
- `POST /timelines/{id}/place` (a loom2 clip with its shot's stamps, or a Catalogue picture, sound or video; a sound only on an audio
  track, the rest only on a video track), `/replace` (*Update* in place: `clip.replaceFromBin`, the edits around it kept), `/undo`, `/redo`,
  `GET /timelines/{id}/frame` (the viewer's PNG).
- **The cut's undo is loom2's**: before every change the project is copied to `timelines/<id>/history/undo/` (50 kept); undo and redo
  restore a copy and reopen it. FilmCraft's own undo lives in its session (lost with it) and counted loom2's marker steps as edits — the
  first test showed an undo removing markers instead of the speed. Any change (Assemble included) is one step; a change FilmCraft refuses
  part-way is rolled back and leaves no step.
- **Chapter markers are loom2's**: after every change, one per named shot on V1 (a *run*: consecutive pieces of one node — a razored take
  is still one shot) at its start, so FilmCraft's FCPXML carries them (FilmCraft keeps no marker on a clip by command, and a sequence marker
  does not follow a clip). Hand-set markers come with CE5.
- **Exports of a FilmCraft cut**: the FCPXML and EDL are FilmCraft's own (`file.exportInterchange`: gaps, speed, every track; the lines on
  A1 as `lane="-1"` connected clips), the SRT and markers.txt from the project (a voiced line at its A1 clip, the others laid across their
  shot's run). Before an export or the movie, **a line voiced since the cut was made is brought onto A1** (`sync_lines`; a re-voiced line
  plays its new audio in place; a moved line stays) — one undo step, none when nothing changed.
- The draft of a FilmCraft cut is FilmCraft's export to PNG (the longer side 960) → a clip as before; a PUT that does not change the lane
  (a rename) leaves V1 alone; FilmCraft's refusal reaches the author in its own words (`edit failed: this edit would break sync: A1 is
  sync-locked and has a clip in the way …`).

**The client** (`episode/cut.ts`, `CutStage.tsx`, `sequenceStore.ts`, `sequenceCommands.ts`):

- A FilmCraft cut opens in **the tracks view**: FilmCraft's frame at the playhead (½ at rest, ¼ playing, the latest asked wins), the
  transport with the **tools** (Select V, Ripple trim B, Roll N, Slip Y, Slide U, Razor C — Premiere's keys as accelerators), undo and
  redo, add a video / audio track, zoom; every track as a row (V2 above V1 above A1 …): a take with its frames, a picture, a sound or a
  line with its waveform, the transitions shaded, the *changed · Update* badge on a take whose shot has a newer approved take.
- A drag asks for one edit when it ends (the tool and the grip decide which: `dragStep`); the razor cuts on a click; a clip's right-click:
  *Update*, Speed…, Freeze frame at the playhead, Dissolve in / out, Dip to black in / out, Remove the transition into it, Move to track ▸,
  Rename, Open the clip in the player, Lift, Ripple delete, Undo / Redo; a track header's: rename, lock, mute, add a track; the empty space's:
  play, exports, renders, Assemble again, rename / delete. A drop on a track places a take (stamped from the Shots bin), a picture or a sound
  where it falls. The Inspector shows the selected clip (track, place, source, speed, shot, the transition into it) with its verbs.
- The Flow's verbs stay: *Assemble* rebuilds V1 (it asks first), *Update* replaces in place; the lane after a save is the server's (its
  clip ids are FilmCraft's, which *Update* and the badges need — an e2e found the client's own lane ids there).

**Checks:** offline `test_cuts_ce2.py` (2) on the fake (which now does CE2's commands as the probe saw the real ones); `cut.test.ts` (4);
an e2e scenario on the tracks (razor, speed from the right-click, the cut's undo and redo, a ripple trim, a track renamed, the V key) and
the four Episode scenarios moved onto the tracks; the rig (`scripts/ce2_acceptance.py`, 13/13 on the real FilmCraft, A1's records): the
tracks, a named track, a stale base and a foreign command refused, the dissolve removed with the clip in place, razor, a move to V2 and
speed, the cut's undo of the whole change, FilmCraft's ripple-delete refusal in its words with the cut unchanged, *Update* in place, a
picture and a sound placed, the viewer's frame over HTTP 7.8 ms at ½, FilmCraft's FCPXML with the chapter marker, the draft through
FilmCraft (225 frames at 960×540 in 2.8 s); edits round-trip in 23–29 ms. CE1's rig check re-run: 14/14.

![The tracks view on A1's records](img/30-ce2-tracks.jpg)
![A clip's right-click](img/30-ce2-clip-menu.jpg)
![A track header's right-click](img/30-ce2-track-menu.jpg)
![The razor tool](img/30-ce2-razor.jpg)

## 14. CE3 · sound — the plan (2026-10-24)

**The commands, probed on the real binary** (a copy of CE2's A1 cut: a line on A1, a sound on A2): `clip.audioGain {db, mode: set}` sets a
clip's gain; `sequence.applyAudioTransition {clip, frames, edge}` puts a constant-power fade on a clip's head or tail (the `edge` the video
one takes; its listed signature omits it); `essentialSound.setType` (dialogue / music / sfx / ambience) then `essentialSound.generateDucking`
keys the music down 15 dB under the dialogue (volume keyframes on the music clip); `essentialSound.autoMatch` brought the line from
−15.6 to −23 LUFS by gain; `timeline.setTrack {volumeDb}` sets a track's volume. **A WAV mixdown of the 9.4 s cut takes 0.11 s** in the
session, with or without `loudnessLufs`.

**What CE3 adds:**

- **The lines are the author's**: the cut remembers the lines it has placed (`loom2.lines` on its sequence), so a line the author lifts
  stays out (the export's sync adds only lines never placed) and a line moved to another audio track keeps its subtitle there.
- **Volume**: a clip's *Gain…*, *Fade in*, *Fade out* (12 frames, constant power); a track's *Volume…*.
- **Ducking**: *Duck under the dialogue* on a music or effects clip or track — the lines typed dialogue, the clips music, FilmCraft's
  ducking keys them down; *Even out the dialogue* brings the lines to −23 LUFS (EBU R128 dialogue).
- **Loudness**: the movie is normalised to **−16 LUFS** by default (online delivery; EBU R128 broadcast is −23) — Settings › FilmCraft ›
  loudness, and *off* leaves the mix as it is. The page's mix uses the same, so what plays is what the movie will be.
- **Sound in the page**: FilmCraft's WAV mixdown of the cut (`GET /timelines/{id}/mix`, rendered on demand and kept per revision) plays
  with the picture; while it plays, its clock moves the playhead.

Slices: **CE3a** the server (the lines' registry, the mix, loudness, the audio verbs in the whitelist); **CE3b** the client (the verbs in the
menus and the Inspector, the mix in the viewer). Tests on the fake, an e2e step, a rig check (gain, fades, ducking, the mix and the movie's
loudness measured).

## 15. CE3 as built (2026-10-24)

- **The lines are the author's.** The cut records the lines it places (`loom2.lines` on its sequence); a placed line that is gone was lifted
  and stays out; a line is read on any audio track (moved to A2, its subtitle follows it). A lifted line's key first fell through to the
  re-voiced check with no clip — the test caught it.
- **Sound verbs** (`EDIT_COMMANDS` gained `clip.audioGain`, `essentialSound.setType` / `generateDucking` / `autoMatch`, `clipMixer.set`;
  the client builds the steps, `cut.ts`): a clip's *Gain…*, *Fade in*, *Fade out* (12 frames, constant power, either edge), *Duck under the
  dialogue* (a clip, or a whole track from its header), *Even out the dialogue (−23 LUFS)*, a track's *Volume…*. The tracks carry a clip's
  gain, sound type and whether it is ducked, a track's volume; the blocks and headers say them (−6 dB · ducked), a line shows its words.
- **Loudness**: Settings › FilmCraft › `loudness_lufs` (−16 by default; *None* leaves the mix as it is) normalises the movie and the page's mix.
- **The mix** (`GET /timelines/{id}/mix`): FilmCraft's WAV of every audio track at that loudness, kept per revision in
  `timelines/<id>/mix/` (the older go). The viewer loads it when the cut changes and, while playing, its clock moves the playhead.
- **Rig** (`scripts/ce3_acceptance.py`, 7/7, the real FilmCraft on A1's records, tones apart by band): the mix 9.38 s rendered in 115 ms
  (4 ms kept); a lifted line stays out; gain −6.00 dB and with the track's volume −12.00 dB (measured against the line — the mix is
  normalised as a whole, so the music alone moves less: the first check measured it alone and failed for that reason); fades −14 dB at the
  head and tail; the music ducked 16.4 dB where the line speaks; the line evened out by −10.4 dB; **the movie measured −16.0 LUFS**
  (ITU-R BS.1770-4, gated, in the script) for Settings' −16.
- Tests: `test_cuts_ce3.py` (2) on the fake (which mixes the audio tracks at their gains and volumes); `cut.test.ts` +1; the tracks e2e
  scenario's sound steps (Gain… and Fade in from the sound's right-click, the mix in the viewer).

![A sound selected: its gain, ducking and fades; a line by its words](img/30-ce3-sound.jpg)
![A sound's right-click](img/30-ce3-sound-menu.jpg)
![An audio track's header](img/30-ce3-track-menu.jpg)

## 16. D127 · the channel strip and VST3 chains (2026-10-24)

The author, after CE3: the loudness target and the tracks' default gain belong in the general Settings; every audio track has four
settings — **volume** −∞…+18 dB, **gain** −36…+36 dB, **pan** 100 % left…centre…100 % right, **width** 0 % (mono)…100 % (stereo)…200 %
(the Side boosted and the Mid slightly attenuated) — and **a chain of VST3 effects**.

**What FilmCraft has** (764723f): a track's fader (`volume_db`, −96…+15 dB) and pan (−100…+100); `mixer.addInsert` / `setInsert` /
`removeInsert` on a track's strip, pre- or post-fader, with its built-in effects — *Amplify* (gain −96…+24 dB) and *Stereo Width*
(0–200 %: the Side scaled, the Mid untouched); **no plugin hosting** (its ROADMAP: VST3 / AU / OpenFX "owner decision needed").
**Licences:** the VST 3 SDK has been MIT since 3.8 (Steinberg, October 2025); Spotify's Pedalboard is GPLv3 (its JUCE core GPL /
commercial).

**The four questions, answered (every recommendation):** loom2's own VST3 host · defaults per track role · the requested ranges exactly ·
the width law with the Mid attenuated.

**The strip, in order:** gain (Amplify, pre-fader; a second Amplify past +24) → the plugin chain (loom2's host) → width (Stereo Width,
patched) → volume (the fader; a post-fader Amplify past +15; −96 shown as −∞) → pan (the track's pan). In the project: the fader and the pan
on the track, the stages as inserts, the chain and the roles in the sequence's metadata.

**Printing:** FilmCraft cannot run a plugin, so a track with a chain is *printed* — its audio after the gain, alone (a working copy of the
project, the other tracks muted, the strip's later stages neutral) is rendered by FilmCraft, run through the chain by loom2's host, and placed
on a hidden companion track carrying the width, volume and pan; the source track keeps its clips and edits and is muted in the mix. A print is
stale when the track's clips, its gain or its chain change; the mix, the movie and the exports print first.

| Wave | Content |
| --- | --- |
| **AU1 · Settings and roles** ✓ built 2026-10-24 (§17) | Settings › Audio: the loudness target (moved from Settings › FilmCraft) and each role's four defaults (dialogue, music, effects); a new cut's A1–A3 named and set as those roles; a track's role from its header |
| **AU2 · the strip** ✓ built 2026-10-24 (§18) | the four settings on every audio track (the track's Inspector and header: sliders with numbers), stored as the fader, the pan and the inserts; the width patch (`engine/patches/filmcraft/`, the build script, a new pin); measured on the rig |
| **AU3 · the host** ✓ built 2026-10-24 (§19) | `engine/vsthost/` — a C++ host on the VST 3 SDK (the SDK fetched at a pinned tag by the build script), `scan`, `render` (a chain over a WAV, offline), `editor` (a plugin's window, its state saved); pinned like FilmCraft; tests with the SDK's own sample plugins |
| **AU4 · chains and printing** ✓ built 2026-10-24 (§20) | a track's chain in the Inspector (add from the scanned plugins, reorder, bypass, open the editor, remove); printing (the companion track, staleness, before the mix, the movie and the exports); the rig with the SDK's samples and one of the author's plugins |

## 17. AU1 as built (2026-10-24)

- **Settings › Audio** (`config.AudioSettings`): the loudness target (moved from Settings › FilmCraft; an app.json from before keeps the
  author's value, `Settings._loudness_moved`) with *as mixed*, and the strip of each role — dialogue 0 dB, music −6 dB, effects −3 dB of gain
  by default, volume 0, pan 0, width 100 %. `config.TrackStrip` brings any value inside the requested ranges (gain ±36, volume −96…+18, pan
  ±100, width 0–200).
- **The strip in the project** (`cuts.strip_steps`, `cuts.strip_of`): the gain as pre-fader Amplify stages (+30 = 24 + 6), the width as a
  Stereo Width after the track's other pre-fader effects, the volume as the fader up to +15 and a post-fader Amplify past it (+18 = 15 + 3),
  the pan on the track; a neutral stage is no insert, the author's own effects stay where they are, and FilmCraft's 5 slots are said in
  loom2's words when a strip would not fit. Read back from the project as it is (the floor −96 is −∞).
- **Roles** in the sequence's `loom2.roles`: a new cut's A1–A3 are Dialogue, Music and Effects with Settings' strips (a converted cut too);
  the header's right-click › *Role* names a track and sets its strip; *No role* keeps the strip. A sound on a dialogue track counts as
  dialogue for *Duck* and *Even out*.
- **The header's right-click** asks for *Gain…*, *Volume…* (−inf is silent), *Pan…* and *Width…*, each with its range and how it reads now;
  the header shows the strip away from neutral under the name (`gain −6 dB · 65 % L · 35 % R · width 140 %`, the whole in its tooltip), the
  Inspector's sound line too. Routes `POST /timelines/{id}/strip` (what changes; the rest stays) and `/role`; the cut's undo covers both.
- **Rig** (`scripts/au_acceptance.py --parts roles,strip`, 10/10, the real FilmCraft, a 440 / 660 Hz pair at −60 dBFS measured by band
  against the source): the roles on a new cut and the music's −6.04 dB in the mix; a neutral strip +0.01 dB; gain +30 with volume +18 heard
  as +47.99 dB; −∞ silent (peak 0); pan 100 % left: the left +0.00 dB, the right silent; width 0 %: both sides one past the first 50 ms
  (FilmCraft's Stereo Width glides to its setting over 20 ms from the render's start: 1.7e-3 there) and each tone −6.04 dB in both; undo;
  a strip change 20 ms (median). The first run failed three checks on the meter, not on FilmCraft: the Hann window reads a sine +1.76 dB, so
  the levels are now read against the source measured the same way, and the width check skips the glide. CE1 (14/14) and CE3 (7/7) re-run with the roles: CE3's music now sits on a Music track at −6 dB, its checks are relative and hold (gain −6.00, + volume −12.00, ducked 16.4 dB, the movie −16.0 LUFS).
- Tests: `test_cuts_au1.py` (3: the settings and the moved loudness, the steps around the author's effects, roles / strips / the mix on
  the fake — whose mixdown is now stereo, through the strip in FilmCraft's order); `cut.test.ts` +1; the tracks e2e scenario's strip and role
  steps and a Settings › Audio scenario.

![A new cut's roles; Music with its strip under the name](img/30-au1-tracks.jpg)
![An audio track's right-click: the strip and Role](img/30-au1-track-menu.jpg)
![Pan… with its range and how it reads now](img/30-au1-pan.jpg)
![Settings › Audio](img/30-au1-settings.jpg)

## 18. AU2 as built (2026-10-24)

- **The width law** (`engine/patches/filmcraft/0001-stereo-width-mid.patch`, 9 lines in FilmCraft's `essential.rs` with its test moved to
  the new law; to be offered upstream): past 100 % the mid's gain is 10^(−0.15 (w − 1)) — −3 dB at 200 %, −1.5 dB at 150 % — the side as
  before. `scripts/build_filmcraft.py` applies the folder's patches to the clean checkout at the pin, builds, takes them off again; the pin
  records each patch's sha256 (`--check` holds the folder and the pin to each other). The binary's hash moved (bc0dedd3…), its size did not.
  FilmCraft's own Essential Sound "Stereo Width" uses the same effect, so it follows the law too.
- **The track in the Inspector** (`StripControls.tsx`): a click on a header selects the track (a clip's selection clears it; the header
  shows it); an audio track shows its role (a list), gain, volume, pan and width as sliders with their values — FilmCraft takes a value when
  the slider is let go (or the key released), the changes queued one after another so keys pressed meanwhile are not lost (the first
  screenshot dropped them: the slider was disabled while FilmCraft answered); the value runs the typed ask; a double-click puts back the
  role's setting. The volume's slider has a fader's taper (the bottom quarter −∞…−30 dB, the rest −30…+18), gain, pan and width detents at
  0 dB, the centre and 100 %. *Reset to its role's settings* in the Inspector and the header's menu. A video track shows its verbs.
- **Rig** (`scripts/au_acceptance.py`, now 12/12 with `width`): on the patched FilmCraft, 440 Hz left / 660 Hz right — width 200 %: the left
  side's own tone +2.62 dB and the right's leaking in at −3.81 dB (the law: +2.63 / −3.79; FilmCraft's own would give +3.52 / −6.02); 150 %:
  +1.36 / −9.65 (law +1.37 / −9.65). The other ten checks unchanged.
- Tests: `cut.test.ts` +1 (the taper and the detents); the tracks e2e scenario's Inspector steps (a header's click, the width slider's End
  key committed, the role from its list). The fake's mixdown already followed the law (AU1).

![A track in the Inspector: role, gain, volume, pan, width](img/30-au2-inspector.jpg)
![The strip](img/30-au2-strip.jpg)

## 19. AU3 as built (2026-10-24)

- **The SDK**: Steinberg's VST 3 SDK `v3.8.1_build_84` (3cdf9ca5, 11 Aug 2026; LICENSE.txt: MIT, Steinberg Media Technologies GmbH),
  fetched shallow by `scripts/build_vsthost.py` into `engine/tools/vst3sdk` with only base, cmake, pluginterfaces and public.sdk (no VSTGUI);
  pinned in `engine/vsthost.pin.json` (the tag, the commit, the binary's hash and the host source's hash — CI's `--check` holds the pin to
  `engine/vsthost/CMakeLists.txt` and `src/`).
- **The host** (`engine/vsthost/`, ≈ 700 lines of C++ on the SDK's hosting classes; `loom2-vsthost.exe`, 693 KB, static runtime): `paths`,
  `scan`, `params`, `state`, `render`, `editor`, each one line of JSON. Rendering is offline 32-bit float with the main buses stereo, any
  side-chain off, the plug-in's latency taken off, the output as long as the input; the editor is the plug-in's own view in a Win32 window,
  its edits (`performEdit`) handed to the processor in one silent block before the state (component + controller, `L2VS`) is written.
  Two first builds failed on the build, not the host: the SDK's libraries use the static runtime (the host's target now too), and MSBuild
  took the native flags for a project when several targets were built in one call (one call per target now; the gain sample's target is
  `again-sample-accurate`).
- **loom2's side** (`loom2/vsthost.py`, Settings › Audio › VST3 folders, `GET /audio/plugins`): one process per request in the
  orchestrator's job object, a crash said as "the plug-in host stopped without an answer (exit code …) — a plug-in crashed; loom2 is fine";
  the scan per bundle, kept by path and modification time in `vst-scan.json`, instruments left out, a failed bundle listed with its reason.
- **Rig** (`scripts/au_acceptance.py --parts host,editor`, 7/7, plus the AU1–AU2 parts): the author's 314 bundles scanned, one process each,
  in 63 s (99 s cold the first time) — 304 effects, **no failure**, the kept scan 0.44 s; AGain Sample Accurate at 0.5 is the input × 0.5
  sample for sample (max error 0); ADelay at 0.25 s moves an impulse from 100 to 12100; the two in a chain in order (0.500 at 12100), a
  bypassed third skipped; the samples (built without VSTGUI) say they have no editor; **Kilohearts' kHs Gain** — one of the author's own —
  opened in the host's window (screenshot), closed by WM_CLOSE as the author would after 2.2 s, its state (554 B) written, read back
  (2083 parameters: Bypass Off, Gain +0.00 dB …) and its default passing the sound at +0.00 dB. Known: the host is not DPI-aware yet, so
  Windows scales a plug-in's window (soft at 150 %).
- Tests: `test_vsthost_au3.py` (3) on `tests/fake_vsthost.py` (the scan with an instrument and a crashing bundle, the cache and a rescan,
  state / params / editor, a chain with a bypass, a crash in a render, the route); the e2e's orchestrator runs the fake with two fake
  effects; the offline suite never runs a built host (`LOOM2_VSTHOST_CLI` in conftest).

![Kilohearts' kHs Gain in loom2's host window (the rig)](img/30-au3-editor.jpg)

## 20. AU4 as built (2026-10-24) — D127 done

- **A track's chain** (`loom2.chains` on the sequence; `POST /timelines/{id}/fx` add / remove / move / bypass, one change of the cut each):
  the Inspector lists the track's effects in order — on / bypassed, the effect's own window, earlier, later, away (each a command on the
  effect) — and *Add an effect…* (the Inspector and the header's right-click) opens the list of installed effects (`EffectPicker.tsx`:
  searchable by name, maker and kind; *Scan again*; the bundles that did not load behind a ?). The header says `… · 1 fx` (and *to print*).
- **The effect's window** (`POST /timelines/{id}/fx/editor`): loom2's host opens the plug-in's own editor; when the author closes it, its
  state is a new file of the cut's (`fx/<id>-<n>.vststate`) and the chain points at it — one change, so the cut's undo takes the settings
  back; no base revision (the author may go on editing while the window is open).
- **Printing** (`Cuts.sync_prints`, before the page's mix, the movie and the FCPXML / EDL): a track with an effect on is rendered alone at
  unity by FilmCraft in a process of its own on the saved project (the other tracks muted, its strip neutral, a custom range to its last
  sound + 8 s of tail within the cut; the project file untouched — probed: byte for byte), then its gain (in float: FilmCraft's WAV is
  16-bit, so a large gain is not baked in) and its chain by the host, and placed on a companion track the cut does not show; the source plays
  into a muted submix (*loom2 · printed sources*), the companion carries the source's width, volume, pan and mute (kept in step without
  printing again). A print is current while its key (the track's clips, media, gain and other pre-fader effects, the active chain with its
  state files, the span, the rate) is unchanged and its file is there; an undo that brings back an older cut prints again. The FCPXML / EDL of
  a cut with prints is exported by a process of its own with the printed sources deleted, so the print stands for its source. `_place` now
  hands FilmCraft the track's id (loom2's A-numbers leave the companions out, FilmCraft's do not).
- **The effect's window** opens centred on the monitor under the mouse (the first screenshot found it at Windows' default place, under the
  author's always-on-top overlay); the page reloads the tracks after a mix that printed (it showed *prints before the next mix* until then),
  and a print that cannot be made is said in a toast (the picture plays on).
- **Found on the rig**: the SDK's AGain Sample Accurate on its defaults printed **silence** — its processor starts its gain at 0 while its
  controller shows 1.0; the host now hands a default effect's controller values to its processor in the first block (read-only and
  program-change parameters left out); the fake FilmCraft read WAVs with the stdlib's `wave`, which refuses float — a print is float.
- **Rig** (`scripts/au_acceptance.py --parts print`, 6/6, the real FilmCraft and host, AGain then ADelay — its default a 1 s delay, all wet — on
  the music track, an impulse at 0.5 s): the page's mix has it only at **1.500 s at 0.401** (the role's −6 dB), nothing before (the source
  silent in its bus), print and mix in 0.22 s; the companion not shown, the print current; pan 100 % L reaches the print without printing
  again (the right silent, 0.13 s); the FCPXML names the print and not the source's file; **the movie** (a 2 s take at 24 fps) has its
  loudest at 1.500 s; ADelay bypassed prints again (the impulse back at 0.500 s). The whole script: 25/25.
- Tests: `test_cuts_au4.py` (2) on the fakes (add from the list, the editor's state, the print heard at −12.04 dB in all — the role's −6 and
  the effect's 0.5 —, the companion hidden and the bus muted, pan and mute mirrored without a new print, the FCPXML, bypass, undo, remove;
  without the host the mix says so); the fake FilmCraft gained submixes, routing, `sequence.deleteTrack`, a custom range and float WAVs; the
  tracks e2e scenario adds an effect from the list (the fake host's two), opens its window, bypasses it and waits for the print.

**D127 is done** (AU1–AU4). Left for later: the host is not DPI-aware (Windows scales a plug-in's window); a plug-in that wants a side-chain
gets none; an effect's tail past the cut's end is cut; FilmCraft's own Essential Sound width follows the patched law too.

![Add an effect: the author's 301 effects, found by "reverb"](img/30-au4-picker.jpg)
![The chain in the Inspector: kHs Reverb on the music, printed](img/30-au4-chain.jpg)
![The track's block](img/30-au4-inspector.jpg)
![kHs Reverb's own window, opened from the Inspector by loom2's host](img/30-au4-window.jpg)
![Settings › Audio with the VST3 folders](img/30-au4-settings.jpg)

## 21. CE4 as built (2026-10-24)

- **FilmCraft's colour, probed first** (764723f): 18 Lumetri presets in four folders, 8 built-in looks (and 9 camera-log input LUTs, left
  out of the list), `file.newAdjustmentLayer` + `timeline.place` for a scene grade, `effects.setParam {effect: "lumetri"}` for any value,
  `lumetri.setLook` (built in or an imported `.cube` / `.3dl`: `lut.import`), `lumetri.applyMatch` (the clip's colour wheels solved toward
  a reference frame of the sequence). **Found:** looks, matches and values act on a clip's *first* Lumetri, but `lumetri.applyPreset` always
  inserts *another* — stacked grades (a Monochrome preset survived a reset and greyed the next look on the rig). loom2 keeps one Lumetri per
  clip: a preset replaces the grade (said behind the ?), a reset removes every Lumetri on the clip.
- **The lists come from the engine** (`GET /colour/looks`, asked once a FilmCraft session); the Inspector's colour block for any selected
  video clip (a take, a picture, a scene's grade): *Apply a preset…* (by folder), the look (none, the built-in ones, *A LUT file…* — a
  path, imported into the cut's project), sliders for temperature, tint, exposure, contrast, highlights, shadows, saturation and the look's
  strength (committed on release, queued as the strip's), *Match its colour to…* (V1's other takes), *Grade its scene*, *Reset its colour*.
  A clip's block says *graded* or *matched*; the right-click has the same verbs (*Match its colour to ▸* lists the takes).
- **A scene** (`POST /timelines/{id}/grade/scene`): the run of V1's shots whose Flow nodes are at the same place (the Flow's scene groups
  come with RC2; until then a scene is the place — a shot with none is its own run) under one adjustment layer on the top *Grade* track,
  named after the place (*Grade · The room*), as shot until a preset, a look or a value; asked again, the same layer. It is a clip: the
  author trims or moves it like any other; video tracks added above it later are not graded.
- **Rig** (`scripts/ce4_acceptance.py`, 11/11, the real FilmCraft on the A1 project — the composition and Mara at one place): FilmCraft's
  18 presets and 8 looks; one layer over both shots (0–225 of 225 frames), the same on asking again; *Golden Dusk* warms both shots (red over
  blue +34.3 / +38.7 levels); exposure +1 brightens (+44.7); *Teal & Orange* changes the picture (13.3 levels); a LUT file of ours that
  swaps red and blue swaps them exactly (means 160.9 / 143.6 → 143.6 / 160.9); Mara matched to the composition (FilmCraft's distance
  0.0511 → 0.0357, the mean colours 89.7 → 79.5 apart); reset and undo; **the movie** carries the grade (mean difference to the viewer's
  frame 1.3 levels, 8.8 s); graded frames at ½ in 38.6 ms (median; 10 ms ungraded, E32). The first run's one failure (the LUT check) was
  the stacked presets above.
- Tests: `test_cuts_ce4.py` (1: the looks, the scene over two shots at one place, preset / values in range / look / LUT file / an unknown
  value refused, a preset replacing the grade with one Lumetri, a match, reset, undo); the fake FilmCraft gained FilmCraft's colour commands
  (its presets stack as the real ones); the tracks e2e scenario: a preset on a take, *Grade its scene* from the right-click (the Grade
  track, the layer selected), exposure by its slider, a look, a match from *Match its colour to ▸*, a reset.

![Before and after: the scene graded (Golden Dusk); Mara matched to the composition (the rig's own frames)](img/30-ce4-grades.jpg)
![The scene's grade selected: the Grade track, the viewer graded, the colour block](img/30-ce4-scene.jpg)
![The colour block](img/30-ce4-inspector.jpg)
![A take's right-click: Grade its scene, Match its colour to ▸, Reset its colour](img/30-ce4-menu.jpg)

## 22. CE5 as built (2026-10-24) — the cut editor's plan done

- **FilmCraft's captions and markers, probed first** (764723f): a caption track and its captions by `captions.*` (each caption with its own
  id, the track a style: size, box, anchor, outline), FilmCraft's viewer drawing them (`RenderOptions.captions`), an SRT out of them, and
  the export's `burnCaptions` and `captionSidecar` (srt / vtt beside the movie). Markers: `markers.add` (a comment marker), `markers.edit`
  by id, but **no delete by id** (`clearCurrent` takes every marker at the playhead).
- ***Captions from the lines*** (`POST /timelines/{id}/captions`; the Inspector, the tracks' right-click): the cut's caption track *Lines*,
  each Dialogue line where the SRT lays it — a voiced line where its clip sits on the audio tracks, the others across their shot
  (`cuts.line_cues`, shared with the SRT) — subtitles at the bottom on a box; made again, the track is replaced after a question (the cut's
  undo brings the edits back). The **caption row** sits above the pictures: a caption selected by a click (its text in the Inspector),
  moved by its body, trimmed by its edges, *Edit the caption…*, *Delete*, *Add a caption at the playhead…*; the header's right-click
  shows / hides them and picks a style (*Subtitles*, *Large*, *At the top*, *Clean*). The SRT export is the caption track's when there is one.
- **The author's markers**: *Add a marker at the playhead…* (the space's right-click, the toolbar), flags on the ruler (loom2's chapters
  grey, the author's in the accent), a flag's right-click renames or deletes it. loom2's chapter rebuild after every change keeps them
  (FilmCraft clears markers all at once, so they are added back); a deletion clears and re-adds the others. markers.txt lists both.
- **Delivery** (the Inspector's *movie as*; the render recipe's `delivery`, `burn_captions`, `captions_file`): H.264 (.mp4) to watch or
  ProRes 422 HQ (.mov) to finish, the captions burned in and / or beside it as SRT or WebVTT (FilmCraft's export writes them; loom2 puts
  them beside the movie in the cut's folder).
- **Rig** (`scripts/ce5_acceptance.py`, 8/8, the real FilmCraft on the A1 project, a Dialogue node with two lines, the first voiced):
  two captions — the voiced one exactly where its clip sits (0 + 34 frames), the other across its shot; FilmCraft's viewer draws them
  (6.7 levels in the bottom band, 0.00 above; none when hidden); a caption edited and moved, the SRT the caption track's; the author's marker
  kept through a change with the chapter rebuilt, renamed, in markers.txt (`warmer light — too dark here`) and FilmCraft's FCPXML, removed;
  **burned in**: 7.3 levels in the caption's band, 0.39 above it, 0.00 on a frame without a caption (5.9 s / 4.4 s for the two movies);
  **ProRes 422 HQ** .mov (codec prores, 166 MB for 9.4 s, 5.4 s) with the SRT and WebVTT beside it.
- Tests: `test_cuts_ce5.py` (captions from the lines, edited, the SRT from them, made again; the author's marker added, kept, renamed, in
  markers.txt, removed; a ProRes movie with the captions burned in and beside it), the fake FilmCraft's captions, markers and delivery (its
  caption handler first took every command and broke CE3's tests — it answers caption and marker commands only); `cut.test.ts` +1; the
  tracks e2e: a caption added from the space's right-click, edited, dragged; a marker added and deleted; the movie as ProRes with an SRT.

![The movie with the captions burned in (the rig)](img/30-ce5-burned.jpg)
![The caption row above the pictures, a caption selected, the viewer drawing it; an author's marker on the ruler](img/30-ce5-captions.jpg)
![The caption track's right-click and its styles](img/30-ce5-caption-menu.jpg)
![The movie's delivery](img/30-ce5-delivery.jpg)
