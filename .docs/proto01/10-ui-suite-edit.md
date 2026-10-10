# 10 · Suite B — Edit (layered inpaint / refine) — UI document

Status: **implemented — M4 closed 2026-10-05, M5 closed 2026-10-06**; amendments dated inline (brushes, mask editing, dialogs, exact noise, headed checks). Originally: proposed; approval gates M4 (editor core) and M5 (AI operations). Engine: PixiJS v8 compositor per
05 §3b; models per 04 §4; flows per 06 §7.

## 1. Purpose
A Photoshop-like, non-destructive editor where AI operations are tools: select → inpaint → result arrives as
a new layer with its mask; refine, upscale and segment likewise. Documents are ORA files in the project;
flattened renders return to the Catalogue with lineage.

## 2. Layout

```
Rail = Toolbox (vertical, flyouts):  V M L W A B E G I C H Z   (see §4)
┌──────┬──────────────────┬───────────────────────────────────────────────────┬──────────────────┐
│ Tool │ Panel            │ Strip: 100% ▾  fit  1:1   ☐ pixel grid  mask overlay ◉  before/after │ Inspector        │
│ box  │ ◉ Tool options   ├───────────────────────────────────────────────────┤ Layers · Props · │
│  V   │ ○ AI             │                                                   │ History · Info   │
│  M   │ ○ Brushes        │                                                   │ ┌──────────────┐ │
│  L   │ ○ Selection      │                                                   │ │▣ inpaint 2 ◐ │ │
│  W   │                  │                                                   │ │▣ inpaint 1 ◐ │ │
│  A   │ Brush            │                 Canvas (PixiJS)                   │ │▤ Curves      │ │
│  B   │ size ──●── 48    │                                                   │ │▣ Background 🔒│ │
│  E   │ hardness ─●─ 80  │        [ selection marching ants ]                │ └──────────────┘ │
│  G   │ opacity ──●─ 100 │                                                   │ blend ▾ Normal   │
│  I   │ flow ─●──── 60   │                                                   │ opacity ──●─ 100 │
│  C   │ pressure: size ✓ │                                                   │ [+] [mask] [fx] │
│  H   │           opacity│                                                   │ [group] [🗑]      │
│  Z   │ [AI ▶ Inpaint]   │                                                   │                  │
└──────┴──────────────────┴───────────────────────────────────────────────────┴──────────────────┘
Dock: Running inpaint (klein-9b) 2/4 ████░░ · Recent
```

## 3. Document model (what the UI edits)

| Element | Properties |
| --- | --- |
| Document | name, width, height, background (transparent/colour), colour space sRGB (MVP), source asset link |
| Raster layer | pixels (tiled), bounds/offset, opacity, fill, blend mode, visible, locked (pixels / position / all), clipping (Photoshop clipping group with the nearest unclipped layer below, D39), **mask** (optional, soft 8-bit, linked/unlinked, enabled, density, feather — D52) |
| Group | children, opacity, blend (pass-through default; below 100 % or masked, a pass-through group is mixed against the backdrop by opacity × mask, D39), mask |
| Adjustment layer (non-destructive) | Levels · Curves · Hue/Saturation · Colour Balance · Brightness/Contrast · Exposure · Black & White · Invert; mask; blend/opacity (the result blends back in the layer's own mode, D39) |
| Filter layer (non-destructive) | Gaussian blur · Sharpen (unsharp) · Noise · High-pass; mask |
| Selection | document-wide soft channel (0–255), marching-ants outline, Quick Mask view |
| Layer metadata | origin recipe for AI layers (model, prompt, seed, region, denoise), lineage asset id |

Blend modes (Photoshop set): Normal, Dissolve, Darken, Multiply, Colour Burn, Linear Burn, Lighten, Screen,
Colour Dodge, Linear Dodge (Add), Overlay, Soft Light, Hard Light, Vivid Light, Linear Light, Pin Light,
Hard Mix, Difference, Exclusion, Subtract, Divide, Hue, Saturation, Colour, Luminosity.

**Compositing semantics (D39, 2026-10-10, from the PhotoCraft study):** the formulas are W3C's except Soft Light (Photoshop's √cb
where cs > ½ and cb ≤ ¼), Vivid Light (the source extremes win), Hard Mix (the thresholded generic vivid light) and Colour Burn /
Dodge (a backdrop within 1e-4 of 0 / 1 counts as exact). A layer followed by `clip` layers forms a **clipping group**: the base is
rendered alone (pixels × mask), each clipped layer blends onto it as if it were opaque and keeps its alpha, and the unit blends
into the backdrop with the base's mode and opacity × fill; a hidden base hides its group. Saved documents carry
`meta.compose_version: 3` (3 = Exposure in linear light through a 2.2 power, D40). Until 2026-10-10 a clipped layer was multiplied by the alpha of everything below it, so it was not
clipped at all over an opaque background.

**Proof against Photoshop (D40):** `orchestrator/tests/test_compose_oracle_d40.py` flattens a pinned subset of psd-tools' test PSDs
(83 files, `scripts/fetch_corpus.py`) with compose.py and compares with the merged image Photoshop stored in each, at premultiplied
max ≤ 2/255; files using features loom2 does not model (vector masks, fill layers, effects, the Hue/Sat-style adjustments whose maths
differ by design) are out of scope with the reason printed. 2026-10-10: 8 pass of 10 in scope (floor 8); known failures Curves (spline
vs linear, PC21) and Exposure (max 5/255: Photoshop rounds to 8 bits after each adjustment layer). The pre-D39 compositor passed 6.
The GPU side is held to compose.py by `edit_headed_check.py grid` (120 cases, p99 ≤ 1; ≤ 2 for Colour Dodge, Vivid Light and Divide,
which amplify the 8-bit rounding of the GPU backdrop).

Working precision is 8-bit in the compositor and, in M4, in the ORA layers too (Pillow writes no RGBA16; 16-bit
layers are post-MVP, §15). The canvas composite is **exact** for layers, groups, masks, clip and all 24
deterministic blend modes (one known approximation: a pass-through group below 100 % or masked is exact over an opaque backdrop
and approximate where the backdrop itself is semi-transparent, measured max 15/255 on such pixels): the editor registers its own W3C/Photoshop blend shaders (D31, PixiJS's built-in set
measured and replaced) and renders masked layers and isolated groups through render-texture passes; measured
p99 ≤ 1/255 per feature and 3/255 over a 25-layer stack against the Python flatten (`scripts/m4_acceptance.py`,
Info tab "compare"). Dissolve is seeded noise and only ≈. Adjustment/filter layers are previewed on the canvas
with the same formulas (per-channel types through a 256-entry LUT, the rest in the shader; Gaussian blur exact
up to a 12-tap radius and strided above; noise is a pure function of (seed, x, y) — one integer hash + Box-Muller
in both the shader and compose.py, exact since 2026-10-06 — measured p99 ≤ 1/255 for every type) and
**re-rendered exactly in Python on save/export** (05 §3b); "preview ≈" therefore only applies to large blur radii
and dissolve.

## 4. Toolbox (Rail) and Panel · Tool options

| Key | Tool | Options (Panel) | MVP |
| --- | --- | --- | --- |
| `V` | Move / Transform (free transform with handles, `Ctrl+T`) | snap, constrain, interpolation | M4 |
| `M` | Marquee rectangle / ellipse (flyout) | mode replace/add/subtract/intersect (Shift / Alt / Shift+Alt while dragging), feather, style normal / fixed ratio / fixed size (D44) | M4, PE2 |
| `L` | Lasso: freehand or polygonal (click corners; first corner, double-click, ✓ or Enter closes; ⊘ / Esc cancels) | mode, feather; anti-aliased edges (D44) | M4, PE2 |
| `W` | Magic wand | tolerance per channel incl. alpha (transparent pixels match each other), contiguous, sample active layer / all layers, anti-alias (D44) | M4, PE2 |
| `A` | **AI Select** (SAM 3): click / box / text prompt; **Subject** (BiRefNet matte) — click adds an include point, Alt-click an exclude point, drag a box; the mask joins the selection (replace / add / subtract / intersect) with expand and feather | model, SAM prompt mode, threshold, combine, expand, feather | M5 ✓ (2026-10-06) |
| `B` | Brush (paints on the active layer, or on its mask / the selection in Quick Mask) | size, hardness, opacity, flow, spacing, pressure → size/opacity/flow, smoothing, colour | M4 |
| | *Brush model (D50, D51, 2026-10-10):* opacity caps the whole stroke (dabs build coverage at the flow, the layer is recomposited from its pre-stroke pixels — a crossing stroke at 50 % stays at 50 %); painting is clipped to the selection; **lock transparency** per layer; small tips are supersampled; smoothing is a pulled string with catch-up; Shift-click draws a straight line from the last stroke, the **Straight lines** toggle does the same by drag; Alt-click or the **Pick colour** chip picks the composite colour | | PE4 |
| `E` | Eraser | as brush | M4 |
| `G` | Fill / Gradient | mode solid / linear / radial (foreground → background colour, mask: white → black), colour, opacity; limited to the selection | M4 (gradient M5 ✓) |
| `I` | Eyedropper | sample size | M4 |
| `C` | Crop / Canvas size | ratio presets, delete cropped vs hide | M4 |
| `H` / `Space` | Hand (pan) | | M4 |
| `Z` | Zoom | scrubby zoom | M4 |
| `S` / `J` | Clone stamp / Healing brush | | post-MVP |
| `T` | Text | | post-MVP |

### Panel · Brushes
Preset list — built-in hard round · soft round · airbrush · pencil · inker · marker · wash, each with its own diameter, plus
the user's **saved presets** ("Save current as preset…", persisted per browser, deletable) — with a dab preview; below it the
**current brush** in full: size (1–1024 px), hardness, opacity, flow, spacing, smoothing, colour. Every slider in the editor
has a **number field** beside it (px for size, % for the rest) so a value can be typed; the same controls appear in Tool
options for `B`/`E`, with `[` `]` / `Shift+[` `]` step buttons. The pen pressure curve arrives with the tablet (D19).

### Panel · Selection
One amount (px) drives **expand / contract / border / smooth / feather** (D44: round, fractional growth through an exact distance
transform; feather is a Gaussian with Photoshop's radius, σ = r / 2), select layer transparency (also Ctrl-click a layer thumbnail),
invert (`Ctrl+Shift+I`), select all/none; grow/shrink similar is not built. **Every selection change is one undo step** (D43, also
deselect and AI Select results). The selection's value is red × alpha of its canvas, so soft and anti-aliased edges survive.
Measured 2026-10-10 on a 4K selection: expand 16 px 0.30 s, contract 0.27 s, border 0.53 s, smooth 0.10 s, feather 0.2 s at any radius.
**Refine edge** (D45): radius (edge band), smart radius, smooth, feather, contrast, shift edge — defaults and ranges from
`/capabilities.refine_edge`, the panel keeps only the user's changes (Reset = the server's defaults). Runs on the server against the
document's exact composite (`POST /documents/{id}/selection/refine`; guided filter in the edge band, then Photoshop's post steps) and
lands as one undo step; AI Select can run it on its result (**refine edge** switch). It gives soft transitions where the image is soft
(blur, fur) and keeps hard edges nearly hard; it does not pull an offset mask onto the true edge or pick out 1-px strands. Rig
2026-10-10: 0.71–0.74 s on a 1080p BiRefNet matte.
**Save selection as mask on active layer**, **Load selection from layer mask**, **Quick Mask** (`Q`): paint the
selection as a red overlay with the brush. The AI selectors (SAM 3, BiRefNet) live in the `A` tool and the AI panel's **Select** operation.

### Panel · AI
The AI panel is the heart of the suite; it always operates on the **current selection** (or the whole
document when none) and returns **new layers**.

| Operation | Modes | Controls | Result |
| --- | --- | --- | --- |
| **Inpaint** | Fill (Klein + LanPaint, default) · Fill-Match (Klein ICM/ReferenceLatent, conservative texture continuation) · Fill Hero (FLUX.2 dev + LanPaint, slow) · Remove (Klein ICM with the hole neutralised in the reference and a background-only prompt, E8b) — E8 2026-10-05 dropped Fill Pro (FLUX.1 Fill) and deferred Edit by instruction (Qwen) post-MVP | encoder (D31: Q4_K_M GGUF default / fp8), prompt (text or compact tree), candidates 1–4 (**default 4 on Klein, 2 on dev**, D22), seed, **region**: context margin % (default 25), min working size (auto-upscale small regions to ≥ 1024 px), paste-back feather px, "match colour to surroundings", mask expand px | N candidate layers in a **variant strip** over the canvas; pick one (`1–4`, Enter) → kept as a layer with mask; others discarded (or "keep all hidden") |
| **Refine** (i2i) | Klein base · dev · Klein distilled "enhance" instruction | encoder (D31), strength 0.15–0.6 (schedule semantics exact), prompt (defaults to the source asset's prompt), on: active layer / visible / selection | new layer above |
| **Upscale** | Real-ESRGAN 2× / 4× · **Tiled refine** after the upscale (Klein base or dev; tile 1024, overlap 128, strength 0.25; one engine graph: `ImageCrop` → `KSampler` at low denoise → `ImageCompositeMasked` through a feathered `SolidMask`) · SeedVR2 (post-MVP) | model, refine on/off, refine model, encoder (D31), strength, tile, overlap, prompt | Catalogue asset at the new size (lineage to the source) and optionally a 1× detail layer |
| **AI Select / Remove background** | **Subject** = BiRefNet matte (core `LoadBackgroundRemovalModel` + `RemoveBackground`, `BiRefNet-general.safetensors`); **SAM 3** text / points / box (core `SAM3_Detect` on the `sam3.pt` checkpoint, its text encoder comes with it) | model, prompt mode, threshold, combine op, expand, feather | the document **selection** (`PUT`/`GET /documents/{id}/selection`); "Save selection as mask" turns it into a layer mask; for a background swap: Select → invert → Inpaint (bench task 03) |
| **Outpaint** | Fill (Klein + LanPaint) · Fill Hero (dev + LanPaint) | expand canvas by px per side, prompt | canvas grows, new layer fills the margin |

**Paste-back and blend-in (PE3, 2026-10-10).** Inpaint and Outpaint results (and a Refine of the selection) land as opaque pixels with a
**linked layer mask** holding the feathered selection, so the seam can be repainted with the brush (D47). Inpaint offers **blend:
feather | seamless** — seamless Poisson-clones the result onto the plate inside the feathered edge, so it keeps the AI texture but meets
the plate's colour and light (bench task 01: seam energy 1.00 → 0.07); it suits removals and texture continuation, and pulls an intended
colour change towards the old colour near the edge, so feather stays the default. Refine offers **match colour to the original** (D48):
the result's Lab statistics mapped onto the original's (ring around a selection, else the whole image / layer) — L* drift +2.3 → 0.0 on
the bench at strength 0.35. Inpaint has no such switch: its graphs composite the original outside the mask, so there is no drift on the
context to measure. Filters gain **Colour to Alpha** (colour, transparency / opacity thresholds; inside an isolated group above line art),
and the layer menu **Ink from white** applies it to the active layer in place (D49).

Every AI layer stores its recipe (visible in Layers → layer info and in History). Re-running an AI layer
with a new seed is one click.

Foot: **[AI ▶ <operation>]** primary (`Ctrl+Enter`), with the time/VRAM estimate line.

## 5. Strip (over the canvas)
Zoom % (input, `Ctrl+wheel`, `Ctrl+0` fit, `Ctrl+1` 1:1, `Ctrl+2` 200 %), pixel grid toggle (auto ≥ 800 %),
**mask overlay** (red tint on selection/mask, toggle `\`), **before/after** (hold `\` shows the layer below;
`Alt+\` toggles compare split), ruler toggle, snap toggle, renderer badge (WebGPU / WebGL2).

## 6. Inspector
- **Layers**: tree with thumbnails, visibility eye, lock, mask thumbnail (Alt-click shows mask only; Shift-click
  disables), blend mode select, opacity/fill sliders; drag to reorder/group; buttons: new layer, new group,
  add mask (from selection), add adjustment ▾, add filter ▾, duplicate, merge down, flatten visible, delete
  (second click). Right-click: convert to … , rasterise adjustment, export layer PNG.
- **Properties**: the active layer's adjustment/filter parameters (curves editor with channels, levels
  histogram, HSL sliders…), transform values, mask density/feather, AI recipe (model, prompt, seed, region)
  with **Re-run (new seed)**.
- **History**: ordered steps with thumbnails; click to step back; snapshots (`Ctrl+Alt+S`); non-linear history
  off (Photoshop-like linear) in MVP.
- **Info**: document size, colour space, memory (GPU tiles, CPU), source asset, saved state, cursor position
  and colour readout.

**Mask editing (2026-10-06).** Adding a mask, or clicking a mask thumbnail, enters mask editing: the thumbnail gets the
editing frame, a hint under the layer list says "paint white to show, black to hide" with an *Edit pixels instead*
button, and when the current tool cannot paint or select (Move, Crop, Zoom, Hand, Eyedropper) the **Brush** is selected,
so the first click paints the mask instead of dragging the layer. A one-time toast explains the same. **Delete layer**
deletes at once (undoable; the toast offers Undo) — no confirmation dialog anywhere in the suite (07 §1).

**Masks like Photoshop's (D52, 2026-10-10).** A raster layer's new mask is layer-sized and **linked** (it moves and transforms with the
layer); groups, adjustment and filter layers get a document-sized mask, and those masks are paintable too (brush, eraser, fill,
gradient, clear). A chain button between the name and the mask thumbnail links / unlinks without moving the mask on the canvas. The
active layer's mask shows **on / linked**, **density** (0–100 %: 1 − d·(1 − v)) and **feather** (Gaussian σ, 0–250 px) under the
blend controls in the Layers tab and in Properties, non-destructively — compose.py derives the same mask (three box passes, the editor's
blur, rounded alike) and PSD export writes both as the user mask's parameters. **Apply mask** bakes the mask as it renders into the
layer's alpha; **Mask from transparency** turns the alpha into a linked mask and the layer opaque. The thumbnail being painted carries
the accent frame; **Delete** while a mask is being edited removes the mask, not the layer. Documents are schema 2 (version-1 files load
with density 1 and feather 0).

## 7. Files
- **Open from Catalogue** (`E` anywhere): creates `documents/<id>.ora` with one background layer (or opens the
  existing document linked to the asset).
- **Save** (`Ctrl+S`) → ORA (16-bit PNG layers, masks as grey PNGs, `stack.xml` + loom2 extension block with
  recipes and blend modes beyond ORA's core set). Autosave every 2 min to a sidecar; crash recovery offers it.
- **Save to Catalogue** (`Ctrl+Shift+S`): flattens (exact 16-bit path in Python) → new asset with lineage to
  the source and link to the document; thumbnails refresh.
- **Export** (`Ctrl+Shift+E`): PNG (flattened, metadata embedded), **PSD** (ag-psd: layers, groups, masks, blend
  modes, opacity, fill, clipping, Lock All, pass-through groups; 8-bit; **adjustment layers as Photoshop adjustment layers**
  (D41: Levels, Curves, Exposure, Invert exact; Hue/Saturation, Colour Balance, Brightness/Contrast, Black & White keep their
  settings but Photoshop's maths differ — the export toast names them; filter layers have no Photoshop equivalent and are
  skipped with a warning, the merged image includes them); verified by reading the file back with psd-tools
  (`edit_headed_check.py psd`)), layer PNGs, selection as PNG mask.
- **Import** layer from file or Catalogue (drop onto canvas → new layer, placed and transformable). D46: an OS file dropped on the
  canvas is imported into the Catalogue first (lineage) and lands as a layer.
- **Clipboard** (D46): Copy (`Ctrl+C`, the selected pixels of the active layer — soft selections copy soft), Cut (`Ctrl+X`), Copy merged
  (`Ctrl+Shift+C`, the selected part of the composite), Paste (`Ctrl+V`, a new layer centred on the document — an image copied in
  another app wins over the editor's own copy), Paste in place (`Ctrl+Shift+V`), Layer via copy (`Ctrl+Alt+J`) / via cut (`Ctrl+Shift+J`);
  all in the canvas menu. Copies are mirrored to the OS clipboard as PNG; `Ctrl+V` reaches the editor as the browser's paste event, so
  images from other apps need no clipboard permission. Pasted bitmaps from other apps have no lineage (no file behind them).

## 8. Workflows
1. **Fix a hand**: open hero → `A` click the hand (SAM) → expand 8 px, feather 4 → AI · Inpaint · Fill, prompt
   "a hand resting on the sword hilt", 4 candidates → variant strip → pick → layer with mask; `\` to compare.
2. **Change costume**: `L` lasso the jacket → AI · Inpaint · Fill "a dark red leather jacket, same pose" (E8 task 02 passes on Klein + LanPaint) → pick →
   Curves adjustment clipped to it for tone.
3. **Background swap**: Remove background → invert selection → Fill "rain-soaked alley at night" → Refine
   whole document at 0.25 for cohesion → Save to Catalogue.
4. **Outpaint to 16:9**: Canvas size + Outpaint right 25 % → Fill → Crop.
5. **Hi-res detail**: zoom into a face region (small on canvas) → Inpaint Fill with min working size 1024 →
   paste-back at native scale.

## 9. Input — mouse-first, pen-ready (D19)
The author has no pen or touch hardware today, so the MVP is tuned and tested with a **mouse**: brush size,
opacity and hardness come from the options panel and keys (`[` `]`, `0–9`), stroke smoothing is on by default,
and the pressure controls in Tool options are hidden until a pen is detected. The engine is pen-ready at no
extra cost: PointerEvents carry pressure/tilt; `pointerrawupdate` + coalesced + predicted events feed the
worker brush; `desynchronized` canvas; Delegated Ink Trail for the last segment; **Windows Ink** is the agreed
strategy when a tablet is bought. Modifier conventions: `Alt` eyedrop while brushing, `Shift` straight lines, `[`/`]` size, `Shift+[`/`]` hardness,
`0–9` opacity, `Alt+right-drag` size/hardness HUD.

## 10. Keyboard (beyond 07 §4 and tool keys)
Every key here is a registry command (07 §3c) with a mouse home: the strip (undo, redo, zoom in/out, fit, 100 %,
pixel grid, mask overlay, before, quick mask), the Layers toolbar (new layer, new group, group active, add
adjustment ▸, add filter ▸, duplicate, merge down, up/down, add/remove mask, hide/show, lock, delete, More ▸),
the **layer row's right-click menu** (rename, hide/show, solo, lock, duplicate, merge, group, reorder, mask ▸,
delete — the Alt-click/Shift-click/double-click gestures are listed as hints), the **canvas right-click menu**
(undo/redo; selection, layer, view, tool and document submenus, with the selection items inline while a
selection or quick mask exists), the Selection panel (all/none/invert/feather/quick mask/mask from
selection/load mask/crop) and the Tool options (brush size/hardness steps, colour swap/defaults).

`Ctrl+Z`/`Ctrl+Shift+Z` undo/redo · `Ctrl+C`/`X`/`V` copy / cut / paste · `Ctrl+Shift+C`/`V` copy merged / paste in place · `Ctrl+D` deselect · `Ctrl+Shift+I` invert selection · `Q` quick mask ·
`Ctrl+J` duplicate layer · `Ctrl+G` group · `Ctrl+E` merge down · `Ctrl+Shift+E` export · `Ctrl+T` transform ·
`Ctrl+Shift+N` new layer · `Alt+click` eye = solo · `\` mask overlay / before · `Ctrl+Enter` run AI ·
`1–4` pick candidate · `Delete` clear selection pixels · `X` swap colours · `D` default colours.

## 11. Performance budgets (from 05 §9 spikes)
The stage renders **on demand** (one frame per change: stroke, view, stack, transform, ants tick) — nothing is
drawn while idle, so adjustment/filter shaders cost nothing between edits. The request coalesces into one animation
frame through a pending flag; a request made before the renderer exists is dropped (init renders once itself) and the
canvas's cleanup cancels a pending frame *and* clears the flag — the 2026-10-06 regression was exactly that flag staying set
after React StrictMode's first unmount, which silently swallowed every later frame (image invisible until a resize, zoom
and strokes applied but never drawn). `scripts/edit_headed_check.py` guards it in a visible Edge window (headless Chromium
cannot present WebGPU, so the headless screenshots say nothing about the stage).

60 fps compositing 6 × 4K layers with 3 advanced blend modes — **measured in-app 2026-10-07** (`edit_headed_check.py perf`): a full
re-render of 6 × 4K with multiply / screen / overlay / soft-light takes p50 5.8 ms · p95 7.1 ms on WebGPU (CPU submit + GPU
done), i.e. 60 fps with 2× headroom; brush ≤ 1 frame visible lag at 2K preview; 10 ×
8K layers < 3 GB GPU memory with tile eviction; inpaint round-trip (upload region + mask, engine, paste-back,
new layer) ≤ engine time + 1.5 s for a 1024² region; ORA save of a 4K 8-layer document < 3 s.

### 11a. Renderer fallback (D3, 2026-10-06)
After the PixiJS application initialises, a 4×4 white sprite is drawn and read back through the same `extract.canvas` path
the exact-compare uses. A renderer that initialised but yields no pixels — seen with WebGPU in headless Edge — is replaced by
WebGL2 and the strip's renderer badge reads "WebGL2 (fallback)" (a toast says so). The badge is a button: auto → forced
WebGL2 → forced WebGPU (persisted per browser); changing it remounts the canvas. Headed Edge (the same Chromium as WebView2)
renders on WebGPU without the fallback; the probe only ever trips in headless runs. A dev build also exposes
`window.__loom2App` and `window.__loom2Editor` for DevTools and the headed check.

## 12. States
No document (drop zone + "Open from Catalogue"); renderer fallback to WebGL2 (badge + banner once); engine busy
(AI button queues, Dock shows); document larger than GPU budget (banner: tiles evicted, zoom responsiveness
reduced); unsaved changes on suite switch (toast with Save, never a blocking modal, autosave covers it).

## 13. Data and API
As built in M4 (06 §2): `GET /documents` (list) · `POST /documents` (from asset, or w×h) · `GET/PUT /documents/{id}`
(the stack as JSON; `PUT` keeps the pixels of surviving layers) · `GET/PUT /documents/{id}/layers/{lid}/pixels?kind=image|mask&raw=1`
(raw RGBA or grey bytes with `X-Loom-Width/Height/Channels`; the editor uploads only dirty layers on save) ·
`POST /documents/{id}/save` (ORA) · `POST /documents/{id}/flatten {to_catalogue}` (exact, lineage + `has_document`) ·
`POST /documents/{id}/export` (png; PSD is written in the editor by ag-psd) · `POST /documents/{id}/compare`
(the editor's composite → per-channel delta vs the exact flatten, used by the acceptance and the Info tab) ·
`GET /documents/{id}/thumbnail` · `POST /documents/{id}/close` · `DELETE /documents/{id}`.
M5 adds `POST /documents/{id}/inpaint|refine|instruct-edit|upscale|outpaint` (recipes with region + paste-back
policy, returning new layers + masks) and `POST /documents/{id}/segment` (SAM points/box/text, BiRefNet).
Tiled uploads (PNG per tile or raw RGBA with Range) are deferred until a measured need: whole-layer raw RGBA
transfers run at loopback speed (52 MB of layers in < 1 s in the M4 acceptance).

## 14. Acceptance checklist
- [x] Layers, groups, masks, 24 blend modes, adjustment and filter layers render correctly vs a Python
      reference flatten (ΔE small on a test document) — M4: p99 ≤ 4/255 over 39 nodes.
- [~] Brush with pressure on the tablet meets the latency budget; undo/redo across 100 strokes is instant — undo/redo done (M4); the pen half waits for a tablet (D19).
- [x] Every Edit command runs once in a visible Edge window with a document open — tools, view, layers (incl. every adjustment and filter type), masks, selection, transform, brush, delete + Undo toast, undo/redo, save, Save to Catalogue, PNG and PSD export, exact compare, close with the in-app dialog — with the state checked after each and no page exception or crash overlay: `scripts/edit_headed_check.py tour`, 2026-10-06. `cmpdiag` compares GPU preview vs exact flatten per feature: 0–1/255 everywhere, the noise filter included once it shared compose.py's hash.
- [x] In a visible Edge window the stage shows the document at once, zooms, survives a resize, and a brush stroke / mask erase / layer eye toggle each change the pixels on screen — `scripts/edit_headed_check.py render|paint`, 2026-10-06 (stroke band 34.7/255, mask band 11.0/255, eye 45.5/255).
- [x] SAM click/box/text and BiRefNet produce masks on the canvas within 3 s — 2026-10-06: BiRefNet 2.3 s, SAM 3 point 3.3 s warm (text 33 s including the 3.4 GB checkpoint load); `scripts/m5_acceptance.py`.
- [x] Inpaint Fill / Fill-Match / Fill Hero / Remove each return candidate layers with masks; paste-back has no
      visible seam on the 5 bench tasks (04 §6) — tasks 01, 02, 04, 05 (2026-10-05/06) and 03 on the inverted BiRefNet matte (2026-10-06: subject alpha 0.027, background 0.996).
- [x] Refine at 0.25 on Klein base changes detail without reconstructing the input (schedule fix honoured) — 47 s on the 1200×544 composite; tiled refine ×2 in 439 s over 6 tiles.
- [x] ORA round-trip (save, reopen) is lossless (M4 acceptance); PSD export opens in Photoshop and Krita with structure intact — written by ag-psd; opening it in Photoshop/Krita stays a manual check.
- [x] Save to Catalogue creates an asset with lineage to the source and a link back to the document (M4 acceptance item 7).

## 15. Open questions
- 16-bit working mode in the compositor (post-MVP; needs `rgba16float` render textures).
- Colour management (ICC) — MVP is sRGB only.
- Clone/heal and text tools timing; whether warp/liquify is ever in scope.
- ~~Whether adjustment layers export to PSD as true adjustment layers (ag-psd supports some) or rasterised.~~ True adjustment layers (D41, 2026-10-10).
