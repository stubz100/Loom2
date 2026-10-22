# 20 · The animation editor on EffectCraft's engine — the build of phase 4 (D114)

Status: **the plan, 2026-10-20 (D114), written from spike E27's numbers (journal 2026-10-20 16:19) and a reading of EffectCraft's
code at the pin.** The waves are 03 §7's (AE1, AP1, AE2, AE3); this document says how they are cut, what the first slice is, and the
facts the build rests on. 07's status section holds the order.

The author's direction (2026-10-20): *"I'd rather build out the effectcraft engine in animate — same way as image/edit, and how we
planned it."* So: loom2's own React UI, in Animate's one column, on EffectCraft's engine running beside the orchestrator. Nothing of
EffectCraft's egui UI is used.

## 1 · What E27 settled, and what the code says

| Fact | Where it comes from | What it means for the build |
| --- | --- | --- |
| `effectcraft-cli mcp` is a complete headless session: every engine command, `render_frame` (PNG, longest side `max_side`), `save_project`, `open_project`, undo / redo, over JSON-RPC on stdio, one message a line | E27; `crates/automation` | the orchestrator drives one such session; no Rust of our own in the first slice |
| the session keeps a **layer cache** by content: after an edit to one layer, the other layers of the frame come from the cache (warm 38 ms against cold 63 ms at full) | `Session.layer_cache`; E27's warm/cold | an edit re-renders in about half a cold frame |
| a cold frame costs ≈ 30 ms of footage fetch for 7 layers plus 26 ms (CPU) or 14 ms (GPU) of compositing; ½ size 40 ms, ¼ 34 ms | E27 bench | T1 and T2 pass without a cache; T3 at full needs frames kept |
| the headless session has **no RAM preview and no disk cache**; those live in the web build's workers over `effectcraft_engine::remote::FrameServer` (diff sync by revision, raw premultiplied RGBA8, GPU multi-pass, layer prefetch) | `remote.rs`, `apps/effectcraft-web/src/frames.rs` | the page keeps the frames it got (T3), until AP1's full form adds a sidecar over `FrameServer` |
| the `.ecproj` is JSON (schema 2); footage saved with a **relative path is found next to the project file** (#652) | `commands/file.rs`, `doc_path.rs` | the composition lives in the final's folder and names its footage relatively, so the project directory moves as one |
| `file.saveCopy {path}` writes a copy without changing the session's file | `file_more.rs` | save through a temp copy, then `fsio.replace` (house rule 4) |
| the project's renderer is a setting: `file.projectSettings {renderer: gpu\|software}`; the CLI's `--gpu` attaches the GPU compositor; `RAYON_NUM_THREADS` caps the CPU pool | `file.rs`, `main.rs`; E27 busy | D113: beside a job, `software` and ≤ 4 threads, frames on demand only |
| `effectcraft-cli render` (Best, Full, PNG) equals the session's frames, 0/255; 81 frames in 2.2 s on the CPU | E27 R2 | the final render is a CPU queue job; it never needs the GPU |
| the composition as the assembly made it matches `final_assembly` to 1/255 | E27 R3 | the composition writer and the assembly share one rule set |
| release build: the CLI 3 min 33 s, 88 MB; rustc ≥ 1.95; git dependencies on `storytold/craft-libs` | E27 | pinned commit + a build script; the binary is not committed (`engine/tools/` is git-ignored, like RIFE) |
| EffectCraft publishes releases with `effectcraft-cli` inside the Windows MSI | `docs/agents.md` | a fetch route for CI exists if building there proves too slow |

## 2 · The pieces

### AE1 · the composition (3–4 days)

1. **The pin and the build.** `engine/effectcraft.pin.json` (repository, commit, version, the binary's sha256);
   `scripts/build_effectcraft.py` builds `effectcraft-cli` from the checkout beside this repository at the pin into
   `engine/tools/effectcraft/<commit>/`, and `--check` (CI) verifies the pin's shape and, when the binary is there, its hash; the
   installer job builds it. `Settings.effectcraft` (the binary's path, the CPU thread cap) through the D60 audit.
2. **The client.** `orchestrator/loom2/effectcraft.py`: one session over stdio (E27's `Mcp` as product code: start, a call with a
   timeout, a command, a frame, save a copy, stop; one request at a time; its log under the state dir; restarted when it dies); the
   project opened on demand. A fake, `orchestrator/tests/fake_effectcraft.py`, speaks the same methods (a JSON project it edits, a
   flat-colour PNG a frame, a PNG sequence on `render`) for the offline suite and the e2e, the way `fake_comfy.py` stands in for the engine.
3. **The record.** One composition per final: `finals/<fid>/comp.ecproj` beside `comp.json` (`schema_version`, `final_id`, `revision`,
   the EffectCraft version, `edited_at`, lineage: the final's layers and their frames). Written from the final by E27's `comp` step made
   product code — the plate; Stage's shadow ratio on Multiply; each prop with its depth alpha; each character over her matte as a luma
   track matte parented to her, both at her contact offset — **reading the offsets, the order and the mattes from the assembly's own
   result** (`Final.assembly`, PS5e), so the automatic composite and the composition agree by construction and `final_assembly` stays
   the one place the rules live. Routes: `POST /finals/{fid}/composition` (make, or remake from the layers), `GET …/composition`,
   `POST …/composition/command` (one engine command; the revision bumps; saved through a temp copy), `GET …/composition/frame?t=&side=`
   (a PNG; the media key, as the layer frames).
4. **`comp_render`.** A CPU queue job (`warm_group` cpu, as `assemble_final`): `effectcraft-cli render` at Best and Full into a PNG
   sequence, then a clip (master, proxy, asset with lineage to the composition and the final) that becomes the final's clip and a Story
   take when the final was made for a shot. The cost shown as E27 measured it (≈ 3 s for 81 frames at 832×480).
5. **From a single clip** (small, at the end of AE1 or in AE2): a composition with one layer from any Animate clip, so the editor
   opens on a plain clip too.

*Accepted when:* a composition is written, rendered and reopened byte-identical; the render equals the preview (0/255, E27's bar).

### AP1 · the preview, thin first (≈ 2 days now; the rest after AE2)

**Thin (in the first slice):**

- the viewer at Animate's **Final** level asks `…/frame?t&side` while scrubbing at ½ (T1: 25 fps measured) and at full once the playhead
  rests (T2: ≈ 60 ms); the frames it got are kept in memory by (revision, time, size), so playback after a first pass is real time (T3)
  and an **idle fill** walks the work area at ½ while nothing else is asked;
- the status chip on the viewer says what is shown ("½ · cached 62 %"), always matching the frame (T8);
- **one GPU job at a time:** while the queue runs a job the session renders with `renderer: software` on ≤ 4 threads and the idle fill
  pauses (D113); when the queue is idle the session may use the GPU (`--gpu`, Vulkan).

**Full (after AE2):** a small sidecar of ours over `FrameServer` (raw RGBA over loopback, diff sync by revision, GPU Auto, the disk cache
in `<project>/_cache/preview/`, proxies), built by the same script; the viewer resolution (Auto · Full · Half · Third · Quarter) and Fast
Previews menus; the budgets in Settings › Animate.

### AE2 · viewer and timeline (6–8 days)

The Final level joins `AnimateLevels` (Clay · Performance · **Final**). Animate's one column gains the editor's sections: **Layers**
(rows: name, visibility, solo, lock, blend mode, track matte, parent; drag to reorder), **Properties** (transform, opacity, keys with
ease and hold by right-click), **Masks** (the pen), and the timeline's layer bars (trim, slip, move) under the one transport. Undo and
redo go through the engine's history. Every action is a command with a mouse placement (D32) that becomes one `…/command` call.

### AE3 · effects and colour (3–4 days)

About 20 curated effects as icon presets with their parameters in the column; Curves, Levels and Lumetri basic with a before / after.
Then **UX9**, the review after the build.

## 3 · The first slice (≈ 1 week)

AE1 steps 1–4 and AP1 thin. What it gives: the rig's final shot (doc 18) opened at Animate's Final level, scrubbed at ½, played from the
cache, rendered to a clip by *Render the finished shot*. No editing control yet beyond *Make the composition* and the render. The
viewer's feel can be judged then, before AE2's controls are designed.

## 4 · Rules and risks

- **EffectCraft is alpha.** The pin holds it; the writer uses the engine's commands, never the JSON directly, so a schema change costs a
  pin move, not a rewrite. A project saved by a newer EffectCraft is opened with repairs and a notice (`file.open`); the record keeps
  the version that wrote it.
- **One session, one request at a time.** The session is the orchestrator's; frames and commands queue behind each other (a frame is
  ≈ 60 ms). A second session only if the measurements ask for it.
- **Memory.** The CPU session held 1.07 GB on the 7-layer shot (E27), beside the engine's own RAM use; a budget in Settings when AP1's
  caches arrive.
- **Relative footage without `..`:** the composition sits at the final's root, its footage below it.
- **Two composites, one rule set:** `final_assembly` makes the automatic composite and is the reference; the composition writer reads
  its result. A rule changed in one place changes both.
- **No native dialogs, mouse first, files are truth** as everywhere (CLAUDE.md).

## 6 · AE4 — passes on layers (D118)

The post stage as the author shaped it after E24 and E29b: processing attached to a layer, the result a new footage version the layer
takes as its source; the line as an audio layer with the lanes' timing; processing layers over the stack after. Four steps, each with
its tests, a commit and a rig run:

| Step | What | Where |
| --- | --- | --- |
| **AE4a · the pass job and the source swap** | a `layer_pass` recipe `{final_id, layer_id, preset, strength, line?, seeds}` and `run_layer_pass`: the layer's frames (a figure's `frames/`, a prop's RGBA under `comp/`, the plate's) through the pass's graph, written as `passes/<pass id>/NNNN.png` under the layer; the layer record keeps `takes: [{id, preset, strength, line, job_id, frames, made_at}]` and `source` (the active take or the original); the composition's footage item swapped by `file.replaceFootage` (the layer keeps its transforms, masks, effects and keys); **Clean up** and **Creative** first (E24's graphs moved into `engine/graphs.py` as `build_layer_pass`); the editor's **Passes** part under the layer's row: the presets as tiles, the strength, Run, the takes listed with ✓ use / ×, the stale mark; `POST /finals/{fid}/layers/{lid}/pass`, `POST …/source` | orchestrator recipes / finishers / finals / compositions / routes; frontend FinalEditor + compositionStore |
| **AE4b · the line as an audio layer** | the shot's Dialogue lines with audio (CN2) listed for the character; **Attach a line…** imports the WAV into the composition and adds it as an audio layer named for the character and the line, bound by a record on the composition (`audio: [{layer, final_layer, asset_id, line}]`), placed at the playhead; the lanes draw audio layers with a waveform; move / trim / slip as the picture layers; the pass reads the timing | compositions, routes, FinalViewer lanes, a dialog |
| **AE4c · the face pass** | Face and Lip-sync: the head box from the layer's keypoints (E29b's tracker), the head crop of the pose pass and of the reference, Wan Animate at 512² in 77-frame batches chained like PS5c, the S2V head per line window as the face video (Lip-sync), the rendered head matted (SAM 3 / BiRefNet, PS5d's path), grown and feathered, pasted back; the result a take like any pass | finishers (the head pipeline from e29b), graphs, finals |
| **AE4d · the lip-sync model as a tool** | LatentSync in its own venv (`tools/lipsync/`, a setup script like voices), the Lip-sync preset's second option "mouth by the model" on the rendered head; the weights fetched on demand with the licence note; `open` variant: not offered | scripts, finishers, capabilities |
| **AE4e · processing layers** | the same passes over the flattened stack below a point (the engine renders it with the layers below only), a frozen adjustment layer, stale when the layers below change | compositions, finishers, FinalEditor |

Each step runs on the rig's final (`engine/spikes/out/ps5`) before it closes; the author's look follows doc 21's pattern.

## 5 · Status

- **2026-10-20 (journal 2026-10-20 17:37):** AE1 steps 1–2 built — the pin and `scripts/build_effectcraft.py`, Settings › effectcraft, the client
  `loom2/effectcraft.py` with the fake `tests/fake_effectcraft.py`; 7 tests; the real binary answers a one-layer frame in 7–8 ms.
- **2026-10-20 (journal 2026-10-20 18:03):** AE1 step 3 built — the assembly writes the composition's footage and the stack; `loom2/compositions.py`
  (`comp.ecproj` + `comp.json` per final, relative footage, make / command / property / frame, stale, make again) and its five routes;
  on the rig's final the composition matches the assembly to 1/255 through product code and is made in 0.06 s.
- **2026-10-20 (journal 2026-10-20 18:14):** AE1 step 4 built — `comp_render`, the finished shot as a CPU queue job through `effectcraft-cli render`
  (the final's clip and a Story take; the composition records the rendered revision). Step 5 (a composition from a single clip) waits
  for AE2.
- **2026-10-20 (journal 2026-10-20 18:33):** AP1 thin built — the Final level in Animate (`FinalViewer`, `compositionStore`): ½ while scrubbing, full at
  rest, playback and an idle fill from the page's cache (paused while a job runs), the chip; the panel's *Make the composition*, *Open in
  Final*, *Render the finished shot*. **The first slice is complete.** Next: the author's look (doc 21), then AE2.
- **2026-10-20 (journal 2026-10-20 19:17):** AE2 a–b built — Layers (switches, blend, matte, parent, order, undo / redo) and Properties (transform
  and opacity, keyframes at the playhead with ease / hold / linear) in the column at the Final level; a drag in the viewer moves the
  selected layer; the engine's reads and one-save batches behind them. Next: AE2c masks, AE2d the timeline's bars.
- **2026-10-20 (journal 2026-10-20 22:02):** an aside from the author's try — D115, Image's Expand (the poses as tiles, one job per cell, the
  results as the character's candidates; Cast's Expand… jumps there). AE2c–d resume after it.
- **2026-10-21 (journal 2026-10-21 10:06):** AE2 c–d built — masks drawn on the frame (rectangle / ellipse; mode, inverted, feather, opacity,
  expansion, remove) and the layers' lanes under the transport (move, trim, slip by drag; the keys; the playhead). **AE2 is complete.**
  Next: AE3 effects and colour.
- **2026-10-21 (journal 2026-10-21 10:32):** AE3 built — 21 curated effects as tiles with their dials (the engine's definitions behind them),
  on / off, reset, remove, and the viewer's Before toggle. **Phase 4's build is complete.** Next: UX9 after the author's looks.
- **2026-10-21 (journal 2026-10-21 13:58):** UX9 begun with the author's first look at doc 21 — U1 the selected layer's editor (Properties · Masks ·
  Effects) under its row instead of three sections; U2 the chip a number alone and the picture at one size at ½ and full; U3 the masks
  drawn over the frame with draggable points, a points tool (`mask.new`), *How masks work*; EffectCraft's roto brush, object matte and
  tracking noted for the author. Next: the looks at 15, 17, 18, 19, then the rest of the register.
- **2026-10-21 (journal 2026-10-21 16:42):** D116 — help behind a ? (house rule 11; Animate and Stage swept), the masks grown (pen icon, marching
  outlines, Lines | Fill, from the layer's content keyed over the shot, EffectCraft's mask tracking and Object Matte), the Performance panel
  a tree of the shot's steps with their verbs in the foot above Render frame. Next: the author's look; the ? sweep over the other suites.
- **2026-10-22 (journal 2026-10-22 07:58):** D118 — AE4 as passes on layers (§6): the face pass with lip-sync, clean-up, creative; the line as an audio
  layer with the lanes' timing; processing layers after. Building AE4a.
- **2026-10-22 (journal 2026-10-22 08:37):** AE4a built — the `layer_pass` recipe (Clean up on Wan 2.2's low-noise expert, Creative on LTX-2.3 locked to
  the layer's depth; E24's graphs in `engine/graphs.py`), the take recorded on the layer as its source, the composition's footage swapped
  by `file.replaceFootage`, the Passes part under the layer's row. Next: AE4b, the line as an audio layer.
- **2026-10-22 (journal 2026-10-22 09:11):** AE4b built — the shot's voiced lines listed (`GET /finals/{fid}/lines`), a line attached at the playhead as an
  audio layer bound to its speaker's layer (the WAV copied under the final, `file.import` + `layer.addItem`), its row and its lane with the
  waveform, the lanes' move / trim / slip as for a picture layer, the render mixing the lines into the proxy. Next: AE4c, the face pass.
- **2026-10-22 (journal 2026-10-22 10:11):** AE4c built — Face and Lip-sync as presets of the `layer_pass` recipe run in steps (`PassStep`: the S2V talking
  head per line window, Wan Animate on the head crop in 77-frame batches, the paste), the head tracked from the layer's keypoints
  (`loom2/heads.py`, E29b's tracker), the rendered head matted in the same graph and pasted back under a grown, feathered mask, the take's
  own matte followed by the assembly and the composition. Next: AE4d, LatentSync as a tool.
- **2026-10-22 (journal 2026-10-22 13:13):** AE4d built — LatentSync 1.5 as a tool in its own venv (`tools/lipsync/`, `scripts/lipsync-setup.ps1`, `full`
  only), the Lip-sync preset's second mouth (`LayerPass.mouth = model`): the chain renders the heads calm, then the `mouth` step runs the
  model with the engine stopped on the kept heads and the layer's lines, back under the heads' silhouettes, then the paste. Next: AE4e,
  processing layers.
- **2026-10-22 (journal 2026-10-22 13:40):** AE4e built — processing layers: `LayerPass.scope = below` renders the composition from the layer down apart
  (`compositions.below_copy` + `effectcraft-cli render`), runs the pass over it and freezes the result as footage the composition brings in
  above that layer on sync (`Final.processing`, `Composition.processing`, stale by the layers' signature; run again replaces, remove drops).
  **AE4 is complete.** Next: the author's looks at doc 21 (§4: the passes, the line on the lanes, Face / Lip-sync, the two mouths, the
  processing layers).
- **2026-10-22 (journal 2026-10-22 13:59):** AE4's follow-ups — `plan_batches` sizes the last Animate batch to the frames owed plus the carry (an 81-frame
  shot: 77 + 9 instead of 77 + 77; the face passes and PS5c's performances alike); a stale processing layer asks before the finished
  shot is rendered (Render anyway), the job's log names it.
