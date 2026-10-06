# 10 · Suite B — Edit (layered inpaint / refine) — UI document

Status: proposed; approval gates M4 (editor core) and M5 (AI operations). Engine: PixiJS v8 compositor per
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
| Raster layer | pixels (tiled), bounds/offset, opacity, fill, blend mode, visible, locked (pixels / position / all), clipping (clip to layer below), **mask** (optional, soft 8-bit, linked/unlinked, enabled) |
| Group | children, opacity, blend (pass-through default), mask |
| Adjustment layer (non-destructive) | Levels · Curves · Hue/Saturation · Colour Balance · Brightness/Contrast · Exposure · Black & White · Invert; mask; blend/opacity |
| Filter layer (non-destructive) | Gaussian blur · Sharpen (unsharp) · Noise · High-pass; mask |
| Selection | document-wide soft channel (0–255), marching-ants outline, Quick Mask view |
| Layer metadata | origin recipe for AI layers (model, prompt, seed, region, denoise), lineage asset id |

Blend modes (Photoshop set): Normal, Dissolve, Darken, Multiply, Colour Burn, Linear Burn, Lighten, Screen,
Colour Dodge, Linear Dodge (Add), Overlay, Soft Light, Hard Light, Vivid Light, Linear Light, Pin Light,
Hard Mix, Difference, Exclusion, Subtract, Divide, Hue, Saturation, Colour, Luminosity.

Working precision is 8-bit in the compositor and, in M4, in the ORA layers too (Pillow writes no RGBA16; 16-bit
layers are post-MVP, §15). The canvas composite is **exact** for layers, groups, masks, clip and all 24
deterministic blend modes: the editor registers its own W3C/Photoshop blend shaders (D31, PixiJS's built-in set
measured and replaced) and renders masked layers and isolated groups through render-texture passes; measured
p99 ≤ 1/255 per feature and 3/255 over a 25-layer stack against the Python flatten (`scripts/m4_acceptance.py`,
Info tab "compare"). Dissolve is seeded noise and only ≈. Adjustment/filter layers are previewed on the canvas
with the same formulas (per-channel types through a 256-entry LUT, the rest in the shader; Gaussian blur exact
up to a 12-tap radius and strided above; noise is a hash approximation of the seeded normal noise — measured
p99 ≤ 1/255 for every type) and **re-rendered exactly in Python on save/export** (05 §3b); "preview ≈" therefore
only applies to noise, large blur radii and dissolve.

## 4. Toolbox (Rail) and Panel · Tool options

| Key | Tool | Options (Panel) | MVP |
| --- | --- | --- | --- |
| `V` | Move / Transform (free transform with handles, `Ctrl+T`) | snap, constrain, interpolation | M4 |
| `M` | Marquee rectangle / ellipse (flyout) | mode add/subtract/intersect, feather, fixed ratio | M4 |
| `L` | Lasso / Polygonal lasso (flyout) | mode, feather, anti-alias | M4 |
| `W` | Magic wand | tolerance, contiguous, sample all layers | M4 |
| `A` | **AI Select** (SAM 3): click / box / text prompt; **Subject** (BiRefNet matte) — click adds an include point, Alt-click an exclude point, drag a box; the mask joins the selection (replace / add / subtract / intersect) with expand and feather | model, SAM prompt mode, threshold, combine, expand, feather | M5 ✓ (2026-10-06) |
| `B` | Brush (paints on the active layer, or on its mask / the selection in Quick Mask) | size, hardness, opacity, flow, spacing, pressure → size/opacity/flow, smoothing, colour | M4 |
| `E` | Eraser | as brush | M4 |
| `G` | Fill / Gradient | mode solid / linear / radial (foreground → background colour, mask: white → black), colour, opacity; limited to the selection | M4 (gradient M5 ✓) |
| `I` | Eyedropper | sample size | M4 |
| `C` | Crop / Canvas size | ratio presets, delete cropped vs hide | M4 |
| `H` / `Space` | Hand (pan) | | M4 |
| `Z` | Zoom | scrubby zoom | M4 |
| `S` / `J` | Clone stamp / Healing brush | | post-MVP |
| `T` | Text | | post-MVP |

### Panel · Brushes
Preset list (hard round, soft round, airbrush, textured) with preview strokes; save current as preset; pen
pressure curve (also in Settings).

### Panel · Selection
Feather, expand/contract (px), smooth, grow/shrink similar, invert (`Ctrl+Shift+I`), select all/none,
**Save selection as mask on active layer**, **Load selection from layer mask**, **Quick Mask** (`Q`): paint the
selection as a red overlay with the brush. The AI selectors (SAM 3, BiRefNet) live in the `A` tool and the AI panel's **Select** operation.

### Panel · AI
The AI panel is the heart of the suite; it always operates on the **current selection** (or the whole
document when none) and returns **new layers**.

| Operation | Modes | Controls | Result |
| --- | --- | --- | --- |
| **Inpaint** | Fill (Klein + LanPaint, default) · Fill-Match (Klein ICM/ReferenceLatent, conservative texture continuation) · Fill Hero (FLUX.2 dev + LanPaint, slow) · Remove (Klein ICM with the hole neutralised in the reference and a background-only prompt, E8b) — E8 2026-10-05 dropped Fill Pro (FLUX.1 Fill) and deferred Edit by instruction (Qwen) post-MVP | prompt (text or compact tree), candidates 1–4 (**default 4 on Klein, 2 on dev**, D22), seed, **region**: context margin % (default 25), min working size (auto-upscale small regions to ≥ 1024 px), paste-back feather px, "match colour to surroundings", mask expand px | N candidate layers in a **variant strip** over the canvas; pick one (`1–4`, Enter) → kept as a layer with mask; others discarded (or "keep all hidden") |
| **Refine** (i2i) | Klein base · dev · Klein distilled "enhance" instruction | strength 0.15–0.6 (schedule semantics exact), prompt (defaults to the source asset's prompt), on: active layer / visible / selection | new layer above |
| **Upscale** | Real-ESRGAN 2× / 4× · **Tiled refine** after the upscale (Klein base or dev; tile 1024, overlap 128, strength 0.25; one engine graph: `ImageCrop` → `KSampler` at low denoise → `ImageCompositeMasked` through a feathered `SolidMask`) · SeedVR2 (post-MVP) | model, refine on/off, refine model, strength, tile, overlap, prompt | Catalogue asset at the new size (lineage to the source) and optionally a 1× detail layer |
| **AI Select / Remove background** | **Subject** = BiRefNet matte (core `LoadBackgroundRemovalModel` + `RemoveBackground`, `BiRefNet-general.safetensors`); **SAM 3** text / points / box (core `SAM3_Detect` on the `sam3.pt` checkpoint, its text encoder comes with it) | model, prompt mode, threshold, combine op, expand, feather | the document **selection** (`PUT`/`GET /documents/{id}/selection`); "Save selection as mask" turns it into a layer mask; for a background swap: Select → invert → Inpaint (bench task 03) |
| **Outpaint** | Fill (Klein + LanPaint) · Fill Hero (dev + LanPaint) | expand canvas by px per side, prompt | canvas grows, new layer fills the margin |

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

## 7. Files
- **Open from Catalogue** (`E` anywhere): creates `documents/<id>.ora` with one background layer (or opens the
  existing document linked to the asset).
- **Save** (`Ctrl+S`) → ORA (16-bit PNG layers, masks as grey PNGs, `stack.xml` + loom2 extension block with
  recipes and blend modes beyond ORA's core set). Autosave every 2 min to a sidecar; crash recovery offers it.
- **Save to Catalogue** (`Ctrl+Shift+S`): flattens (exact 16-bit path in Python) → new asset with lineage to
  the source and link to the document; thumbnails refresh.
- **Export** (`Ctrl+Shift+E`): PNG (flattened, metadata embedded), **PSD** (ag-psd: layers, groups, masks, blend
  modes, opacity; 8-bit; adjustment layers rasterised with a warning), layer PNGs, selection as PNG mask.
- **Import** layer from file or Catalogue (drop onto canvas → new layer, placed and transformable).

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

`Ctrl+Z`/`Ctrl+Shift+Z` undo/redo · `Ctrl+D` deselect · `Ctrl+Shift+I` invert selection · `Q` quick mask ·
`Ctrl+J` duplicate layer · `Ctrl+G` group · `Ctrl+E` merge down · `Ctrl+Shift+E` export · `Ctrl+T` transform ·
`Ctrl+Shift+N` new layer · `Alt+click` eye = solo · `\` mask overlay / before · `Ctrl+Enter` run AI ·
`1–4` pick candidate · `Delete` clear selection pixels · `X` swap colours · `D` default colours.

## 11. Performance budgets (from 05 §9 spikes)
The stage renders **on demand** (one frame per change: stroke, view, stack, transform, ants tick) — nothing is
drawn while idle, so adjustment/filter shaders cost nothing between edits.

60 fps compositing 6 × 4K layers with 3 advanced blend modes; brush ≤ 1 frame visible lag at 2K preview; 10 ×
8K layers < 3 GB GPU memory with tile eviction; inpaint round-trip (upload region + mask, engine, paste-back,
new layer) ≤ engine time + 1.5 s for a 1024² region; ORA save of a 4K 8-layer document < 3 s.

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
- Whether adjustment layers export to PSD as true adjustment layers (ag-psd supports some) or rasterised.
