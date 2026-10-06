# 15 · MVP click-through — the author's end-to-end pass (M7 slice 5)

Status: guide, written 2026-10-07 for the author's own run; the automated checks it leans on are listed per step so a
failure can be reproduced without the mouse. Budget ≈ 45 minutes with the engine warm. Start with `scripts/dev.ps1`
(the app) on a project of your own — not the acceptance projects — so the pass also covers "new project" state.

Mark each line **pass**, **pass with a note**, or **fail → journal**. Anything that needs more than one attempt to find
is a D32 (mouse-first) failure even when it works.

## 0. Frame (07)
- [ ] New project (folder picker is the only native dialog you ever see); the format line reads 16:9 · 1920×1080 @ 24 fps · Draft.
- [ ] Top bar chips: engine off → idle after the first job; running / queued counts; disk GB free; weights ok.
- [ ] `Ctrl+1…5` switch suites; `Ctrl+K` palette lists every command with its key; `?`/Help overlay shows the keys per suite.
- [ ] Right-click on a tile, a layer, the canvas, the player, the timeline — every menu item is a registry command.
- [ ] Settings → Licences shows the H3 toggle (D17); Settings → Engine shows the stall timeout and reserve VRAM.
- [ ] Banners: pause the queue → banner with Resume; stop the engine mid-idle → the chip reads off, nothing crashes.

## 1. Generate (09)
- [ ] Prompt tree with no subject → Generate 4 on dev Turbo: previews stream into the strip, 4 assets land with seed, params, lineage (`scripts/m3_acceptance.py` is the automated twin).
- [ ] Switch to Klein 4B: steps / CFG show disabled with the reason; the estimate line changes; Generate 1 — note the time (the pin-bump smoke on 2026-10-07 measured it).
- [ ] Drop a Catalogue tile into the prompt's reference slot; the token hint updates; Generate.
- [ ] A missing weight (temporarily move one file): the primary action is disabled with the reason and **Fetch** opens Models; put the file back, Rescan.
- [ ] Save a panel preset, change things, apply it back.

## 2. Catalogue (08)
- [ ] Group by batch / lineage / session / model; expand all on a large project stays responsive (10k measured: every display frame).
- [ ] Keep / Reject / rating / tags with the keys and with the inspector; filter by state; smart collection saved from the filter.
- [ ] Loupe: wheel zoom, pan, compare pin two images, wipe and difference.
- [ ] Trash: delete two tiles (two-step with Undo), **Empty trash** (two-step, no dialog).
- [ ] Drag a tile onto the Edit tab (opens as a document), onto the Generate tab (reference), onto the Animate tab (start frame).

## 3. Edit (10)
- [ ] Open a Catalogue image; paint with the brush (number fields for size / hardness), erase, undo / redo across 20 strokes.
- [ ] Add a mask from the Layers toolbar: the brush is selected automatically, the hint row explains white / black; paint black, the layer hides there.
- [ ] Marquee / lasso / wand selections; quick mask paints the selection; Delete clears pixels.
- [ ] Free transform with handles, flips, 90° rotations; apply.
- [ ] Adjustment and filter layers (levels, curves, blur, noise) — `Compare preview with the exact flatten` in Info reads p99 ≤ 2.
- [ ] AI: select a region → Fill (Klein + LanPaint) 2 candidates → candidate strip, pick one; Refine 0.25 on the visible composite; Upscale ×2 as a layer; AI Select → Subject (BiRefNet) then SAM 3 by text (`scripts/m5_acceptance.py` 24/24 is the twin).
- [ ] Save, Save to Catalogue (lineage back to the source), Export PNG and PSD; close with unsaved changes → the in-app dialog.
- [ ] Delete a layer: immediate, Undo in the toast.

## 4. Animate (11)
- [ ] Catalogue `Shift+A` on a frame → Animate opens with it as the start; `Shift+Z` on another → end frame; swap; clear.
- [ ] Wan Draft 480p 81 f: the estimate line says ≈ 4 min; Animate; the Interim card shows progress; the clip opens when its proxy is ready (`scripts/m6_acceptance.py` is the twin, 34/34 over the five bench tasks).
- [ ] Player: Space, `,` / `.`, Home / End, J / K / L shuttle, I / O in-out, onion skin, filmstrip, compare with the start still and with a second clip (`edit_headed_check.py animate` verifies frame-exactness).
- [ ] Extract frame (F) and Extract range (Shift+F) → Catalogue images with lineage; Send frame to Edit opens it there.
- [ ] Clip inspector: identity numbers (FaceSim), Keep / Reject, Variations, Re-run, Try the other model (LTX 1024×576 121 f with a beat).
- [ ] Models card for H3 reflects the Settings toggle.

## 5. Durability and recovery (12 §8, 03 §6)
- [ ] While a clip renders, end the app from the task manager; relaunch: the queue is paused with the job re-queued (`scripts/m7_durability.py` did this on 2026-10-07: 11/11).
- [ ] Resume; the clip finishes.
- [ ] Models suite: a verified weight shows its sha256; Settings → Catalogue rebuild re-indexes clips and documents.

## 6. What to record
One journal entry: date, the project used, each section's verdict, every "fail" or "note" with the exact step, and the
timings you saw next to the estimates. 12 §8 closes M7 on that entry.
