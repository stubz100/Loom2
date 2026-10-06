# 11 · Suite C — Animate (image-to-video) — UI document

Status: proposed; approval gates M6. Models: 04 §5 (Wan 2.2 I2V-A14B primary, LTX-2.3 secondary, MiniMax H3
opt-in). Video stack: 05 §4 (Mediabunny scrubbing, PNG-sequence masters + MP4 proxy).

## 1. Purpose
Turn a storyboard frame into a 3–5 s clip from a start image with a prompt, or between a start and an end
image, judge character consistency, and harvest frames back into the Catalogue / Edit.

## 2. Layout

```
Rail: [Inputs] [Model] [Length & Size] [Presets]
┌────────────────────────┬──────────────────────────────────────────────────┬──────────────────┐
│ Panel · Inputs         │ Strip: ◉ player ○ filmstrip ○ compare   speed 1× ▾  onion ☐ loop ◉  │ Inspector        │
│ Start frame            ├──────────────────────────────────────────────────┤ Clip · Frames ·  │
│ ┌──────────┐           │                                                  │ Lineage          │
│ │  [img]   │ ✕ swap ⇄  │                                                  │ wan2.2-a14b Q5   │
│ └──────────┘           │                 Player (Mediabunny)              │ 81 f · 16 fps    │
│ End frame (optional)   │                                                  │ 576×320… 6 m 12 s│
│ ┌──────────┐           │                                                  │ seed 4021        │
│ │  [img]   │ ✕        │                                                  │ ───────────────  │
│ └──────────┘           │                                                  │ Keep ✓ Reject ✗  │
│ Prompt                 │   ◀◀  ◀  ▶  ▶  ▶▶     frame 37 / 81   00:02.31   │ Variations (new  │
│ "she turns toward…"    ├──────────────────────────────────────────────────┤  seed) · Re-run  │
│ motion chips: pan ▾ …  │ Dock · Timeline                                  │ Extract frame ⤓  │
│ Model ◉ Wan (faithful) │ ▮S ░░░░▯░░░░▯░░░░▯░░░░▯░░░░▯░░░░▯░░░░▯░░░░ ▮E     │ Extract range ⤓  │
│       ○ LTX (fast)     │ in ──────────────── out      [extract 5 frames]  │ Send frame to    │
│       ○ H3 (hero) 🔒   │ Jobs ▸ running wan i2v 3/8 ███░░ ETA 4:10        │  Edit            │
│ [ Animate ▶ ] ~6 min   │                                                  │ Compare with…    │
└────────────────────────┴──────────────────────────────────────────────────┴──────────────────┘
```

## 3. Panel

### 3a. Inputs
- **Start frame** slot (required): drop from Catalogue (`Shift+A` anywhere), Edit (flattened), or OS file.
  Shows size and aspect; auto-fit to the clip size with letterbox/crop choice.
- **End frame** slot (optional): enables first-last-frame mode; **swap** button; a warning when the two frames
  differ strongly in pose/composition ("large gap → expect morphing on Wan; try LTX beats or shorter clips").
- **Prompt**: text (motion, camera, mood); **motion chips** insert phrases (slow push-in, orbit left, handheld,
  wind in hair, turns to camera, walks left→right). Negative prompt only where the model uses it (Wan with
  CFG > 1; hidden otherwise with a reason).
- **Reference images** (post-MVP; SkyReels/Phantom/H3 Ref2VA).

### 3b. Model
- **Wan (faithful)** — Wan 2.2 I2V-A14B GGUF Q5_K_M + Lightning 4-step LoRAs. Shows: 81 frames @ 16 fps
  (≈ 5 s), 480p/576p presets, FLF via the same weights. Advanced: Lightning strength high/low (0.7 / 1.0),
  steps 4+4, CFG 2.5 (high expert), shift, "no Lightning (quality, 20+20 steps)".
- **LTX (fast, beats)** — LTX-2.3 distilled GGUF Q4_K_M. Shows: 121 frames @ 24 fps, 8 steps; **beats**:
  optional mid keyframes (drop frames onto the timeline at chosen indices with a strength slider 0.3–1.0).
- **H3 (hero)** — MiniMax H3 FL2VA, unlocked once Settings records that the EU licence application is filed
  (D17); shows 864×480, 5 s, ≈ 13 min.
- Health per model (ready / fetch N GB) and the licence badge.

### 3c. Length & Size
**Tiers** (D18, 04 §9c) bound to the start frame's aspect, snapped to the model's rule (Wan ×16, 4n+1 frames;
LTX ×32, 8n+1 frames): **Draft** (default) Wan 832×480 @ 16 fps 81 f · LTX 1024×576 @ 24 fps 121 f · H3 864×480;
**HD** Wan 1280×720 (slow) · LTX 1280×704; **Full (FHD)** LTX two-stage (base + 2× spatial upscaler → 1920×1088
→ crop 1080); Wan/H3 FHD = Draft/HD + frame upscale (post-MVP). Duration readout; seed; estimate line (ETA from
history, VRAM fit). Portrait and square variants (480×832, 640×640, 576×1024) when the start frame is not 16:9.

### 3d. Presets
Save/load Panel state; "last used" per project.

Foot: **[Animate ▶]** (`Ctrl+Enter`), **Stage** (queue later). Disabled with reasons as in 09.

## 4. Stage · Player
- Mediabunny-decoded proxy with **frame-accurate** stepping; transport: `Space` play/pause, `,`/`.` step,
  `J`/`K`/`L` shuttle, `Home`/`End`, `I`/`O` set in/out, `Shift+,`/`.` ±10 frames; frame counter and timecode;
  loop; speed 0.25–2×; **onion skin** overlays the start (and end) still at 30 % to judge drift (`N` toggle).
- **Filmstrip** view: every k-th frame as thumbnails (k from zoom) with the in/out range; click → frame.
- **Compare** view: two clips side-by-side or wipe, synchronised by normalised time (different frame counts
  allowed); compare a clip against its start/end stills.
- Live job: while rendering, the Stage shows step progress and (where the engine emits them) preview frames;
  Wan previews are coarse latent decodes, labelled as such.

## 5. Dock · Timeline
Frames ruler with **S** and **E** markers (end only in FLF mode); in/out handles; keyframe "beats" for LTX
(draggable markers with strength); extracted frames show as pins; the jobs list sits below (collapsible).

## 6. Inspector
- **Clip**: model/format, frames/fps/size, seed, prompt, time, start/end thumbnails, Keep/Reject/Rate/Tags;
  **Variations** (new seed), **Re-run**, **Try on LTX / Wan** (same inputs, other model), **Extend** (post-MVP:
  last frame → new clip; LTX-2.3 native extension later).
- **Frames**: current frame readout, **Extract frame** (`F`) → asset in Catalogue with lineage
  `frame-extract` (from the PNG master, not the proxy), **Extract range** (every k-th between in/out, max 24),
  **Send frame to Edit** (`E`). Extracted frames carry the clip's prompt, model and frame index.
- **Lineage**: start/end source assets, extracted children, sibling variations.

## 7. Workflows
1. **Animate a board**: Catalogue → `Shift+A` on the hero → prompt "she turns toward the window, soft push-in"
   → Wan → Animate → ~6 min → play, onion skin to check drift → Keep → Extract frame at 37 → Send to Edit.
2. **Two boards (FLF)**: start + end (`Shift+Z`) → Wan → check mid-clip morphing with filmstrip → if bad,
   Try on LTX with a mid beat at frame 60 (strength 0.5) → Compare both.
3. **Hero clip**: unlock H3 in Settings → same inputs → Stage overnight.
4. **Frame harvest**: in/out around a good motion → Extract range (every 8th) → curate in Catalogue.

## 8. States
Weights missing (Fetch; Wan Q5 + umT5 ≈ 28 GB); long ETA warning (> 5 min: "Stage instead?"); proxy
encoding after the master lands (poster shown, scrub enabled when ready); engine restart between jobs
(HIP stability policy) shown as "restarting engine" in the Dock; RDNA4 colour-corruption guard: Wan 5B is
hidden by default (04 §5b).

## 9. Keyboard
`Ctrl+Enter` animate · `Space` play · `,`/`.` frame step · `J`/`K`/`L` shuttle · `I`/`O` in/out · `F` extract
frame · `Shift+F` extract range · `N` onion skin · `E` send frame to Edit · `C` compare · `V` variations ·
`K`/`X` keep/reject (on the clip) · `Shift+A`/`Shift+Z` set start/end from the Catalogue.

## 10. Data and API
`POST /jobs` with `I2V{model_id, start_asset, end_asset?, prompt_text, negative?, frames, fps, width, height,
seeds, preset: draft|motion|quality, steps?, cfg?, shift?, beats?: [{frame, asset_id, strength}]}` (implemented 2026-10-06:
the preset replaces per-knob Lightning fields — Draft = Lightning 2 + 2, Motion = undistilled high expert, Quality = 10 + 10;
`/recipes/preview` returns the snapped size / frames and the ETA) → clip in `clips/<id>/`
(master PNG sequence + `proxy.mp4` + `clip.json`); `GET /clips/{id}/proxy.mp4` (Range) for the player;
`GET /clips/{id}/frames/{n}.png` and `POST /clips/{id}/extract {frames[]}` for harvesting (TorchCodec exact
seek on the master if PNGs are pruned); WS `job.progress` (step, preview frame), `clip.ready`, `proxy.ready`.

## 11. Acceptance checklist
- [ ] Wan 2.2 I2V Q5 + Lightning renders an 81-frame 480p clip on the rig; time and peak VRAM recorded.
- [ ] FLF on the same weights reaches the end image on the bench tasks; morphing noted.
- [ ] LTX-2.3 distilled renders 121 frames @ 24 fps with one mid beat; time recorded.
- [ ] Player steps every frame exactly (frame counter matches the PNG master); compare syncs two clips.
- [ ] Extracted frames appear in the Catalogue with lineage and open in Edit.
- [ ] Identity check: ArcFace FaceSim across the clip shown as an advisory number in Clip info (never blocks).

## 12. Open questions
- Default resolution for Wan on this rig (480p vs 576p) after measurement.
- Whether to show Wan's latent previews at all (may mislead) or only step progress.
- Audio (LTX generates audio): off for MVP; expose later as a toggle.
- fps conform (Wan 16 fps → project 24 fps): decided by spike E9 (D27); until then masters keep native fps and
  the player shows the clip's own fps.
- H3 eligibility: the user confirms territory/licence before the option unlocks (Q1 in 13).
