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

## 5 · Status

- **2026-10-20 (journal 2026-10-20 17:37):** AE1 steps 1–2 built — the pin and `scripts/build_effectcraft.py`, Settings › effectcraft, the client
  `loom2/effectcraft.py` with the fake `tests/fake_effectcraft.py`; 7 tests; the real binary answers a one-layer frame in 7–8 ms.
