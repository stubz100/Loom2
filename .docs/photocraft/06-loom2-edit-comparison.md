# 06 · loom2 Edit suite vs PhotoCraft — comparison and proposals

Compares loom2 at `1cdc6d2` (2026-10-10, offline suite 125 passed) with PhotoCraft at `b37bff98`. Everything in §5–§8 is a
**proposal**. Nothing becomes a decision until the author enters it in [13](../proto01/13-decision-log-and-open-questions.md).

The proposals respect the standing constraints:
- 16 GB AMD/ROCm rig (T1);
- ComfyUI for inference only (D2, D15);
- mouse-first, keys as accelerators (D19, D32);
- display == reality (T8);
- files are truth;
- 8-bit sRGB small drafts (D18);
- EU licensing (D17), `full`/`open` variants (D26).

## 1. Two different editors

| | PhotoCraft | loom2 Edit |
| --- | --- | --- |
| Purpose | general Photoshop replacement | correcting and compositing AI output for storyboards |
| Scope | 627 menu commands, CMYK/Lab, 8/16/32-bit, effects, smart objects, type, 17 languages | layers, groups, masks, 8 adjustments, 4 filters, selections, AI inpaint/outpaint/refine/upscale/segment |
| Smart tools | classical (graph cuts, GrabCut, PatchMatch, live-wire) | AI (SAM 3, BiRefNet, Klein / FLUX.2 inpaint) |
| Compositor | CPU oracle (Rust) + WGSL GPU path, fitted to Photoshop | `compose.py` (numpy) + Pixi GLSL/WGSL shaders, fitted to each other (W3C) |
| Proof | Photoshop merged images as oracle, ratcheting floors, GPU = CPU grid | `cmpdiag` (GPU vs exact per feature), M4/M5 acceptance on the rig |
| Maturity | broad, young, perf budgets mostly unmet | narrow, measured on the rig, fast (7 ms p95 at 6×4K) |

**loom2 is ahead where it counts for its purpose:** AI operations with candidates and recipes on layers, region planning, revision
merging, and a measured, fast GPU preview that matches its exact flatten.

**PhotoCraft is ahead on:**
- Photoshop fidelity;
- the manual toolset (selection, brush, transform, retouch);
- panel ergonomics;
- the algorithms that make AI output *blend in*.

## 2. Verified findings: bugs and spec ≠ code

Each item was re-checked in loom2's code during this study.

| # | Finding | Evidence | Consequence |
| --- | --- | --- | --- |
| F1 | **Clipping uses the alpha of everything below, not the base layer's.** A clipped layer over an opaque background is not clipped at all. | `compose.py` `Renderer._layer_alpha`: `a * below[..., 3]`, where `below` is the accumulated backdrop; `blendModes.ts` `-clip` variants: `front.a * back.a`. | The UI says "clip to the layer below" (`EditSuite.tsx:546`). PSD export writes `clipping: n.clip`, so Photoshop shows a different image. The only test (`test_documents_m4.py:71`) clips to a base that *is* the whole backdrop, so it can't see the difference. |
| F2 | **A pass-through group with opacity < 1 renders isolated.** | `compose.py` `render_nodes`: pass-through only when opacity is 1; same rule in `EditorCanvas.tsx:337`. | Adjustments inside a semi-transparent pass-through group stop reaching the layers below. Photoshop mixes the pass-through result against the original backdrop by opacity × mask. |
| F3 | **Adjustment and filter layers ignore their blend mode.** | `compose.py`: the adjustment branch never reads `mode`. | The blend dropdown is shown for adjustment layers but does nothing (a T8 violation). Photoshop applies `blend(mode, backdrop, adjusted)`. |
| F4 | **Soft Light (where cs > ½ and cb ≤ ¼), Vivid Light and Hard Mix follow W3C, not Photoshop;** Burn/Dodge have no edge tolerance. | `compose.py` `_soft_light`, `_vivid_light`, `_hard_mix`; same in `blendModes.ts`. | Visible differences from Photoshop. `cmpdiag` already reports hard-mix max 193 at its threshold flip, which the `EDGE` rule addresses. |
| F5 | **Brush opacity is per dab, not per stroke.** | `layerPixels.ts` `makeDab(…, b.opacity)`, `EditorCanvas.tsx` `stamp`: `globalAlpha = flow` per dab. | Overlapping dabs in one stroke build past the opacity setting. A 50 % brush can paint 100 %. |
| F6 | **Selection edits are not undoable.** | `editorStore.ts` `selectAll` (l.843), `invertSelection`, `featherSelection`, marquee, lasso and wand never call `pushHistory`. | A misclick with a selection tool destroys a careful AI Select result with no way back. |
| F7 | **PSD export skips adjustment layers although ag-psd 31.0.2 can write them.** | `psdExport.ts:1`; `ag-psd/dist/psd.d.ts` has `levels`, `curves`, `hue/saturation`, `exposure`, `color balance`, `black & white`, `invert`, `brightness/contrast`. | Spec 10 says "rasterised"; the code skips them with a toast. Also: fill opacity is dropped, pass-through is not mapped, and `locked` is written as `transparencyProtected`. |
| F8 | **AI paste-back is alpha-feather only, and results carry no layer mask.** | `edit_ai.py` `assemble_layer`. | Colour and exposure drift show as halos. Spec 10 promises "match colour to surroundings" and "kept as a layer with mask"; neither exists. |
| F9 | **`fsio` replaces files once, with no retry.** | `fsio.py` `atomic_write_bytes`: a single `os.replace`. | On Windows, antivirus and the indexer can briefly lock the target, and the save fails. |
| F10 | **Every pointer move re-uploads the whole layer texture.** | `layerPixels.ts` `refresh()` → `texture.source.update()`. | Brush latency grows with document size (M7: 33 ms p50 on 4K, display-bound today). |

**Further spec ≠ code items reported by the inventory pass** (not individually re-verified; see spec 10):
- no autosave sidecar or crash recovery (autosave overwrites the ORA);
- spec claims "16-bit PNG layers", the code is 8-bit;
- no rulers, snap or split compare; no history thumbnails or snapshots;
- no curves/levels UI (curves are JSON text, interpolated linearly);
- wand has no "sample all layers"; marquee has no feather or fixed ratio; no polygonal lasso;
- Ctrl+Enter is not registered; no layer drag-reorder; no flatten visible / rasterise / export layer PNG;
- no pen input plumbing; no tile eviction; no "keep all hidden".

## 3. Where loom2's Edit suite is weakest, for this user

From the inventory, ranked by daily impact on a mouse-only storyboard artist:

1. **Selection toolset and its undo** (F6): thin manual tools (no modify, intersect, polygonal lasso, refine edge), a hard-edged
   one-layer wand.
2. **No clipboard and no floating selection:** no copy/cut/paste, layer via copy, copy merged, or OS image paste/drop into Edit.
   Compositing pieces of several generations needs these.
3. **Transform:** scale/rotate on one raster layer only; no skew, distort or perspective; no numbers; destructive on every apply.
4. **Masks:**
   - created unlinked, with no link toggle;
   - paintable only on raster layers;
   - no density or feather;
   - AI results bake their mask into alpha (F8).
5. **Brush:** opacity semantics (F5); smoothing lags with no catch-up; no Shift-line or eyedrop while painting; no lock
   transparency; whole-texture upload (F10).
6. **AI blend-in:** no colour match or seamless blend (F8); Remove fills with mid-grey; results land at the top of the stack.
7. **Adjustments UX:** JSON fields for curves and colour balance; no histogram.
8. **Layers panel ergonomics:** no drag reorder or nesting, no multi-select.

## 4. Side-by-side

| Area | PhotoCraft | loom2 | Gap → proposal |
| --- | --- | --- | --- |
| Clip / pass-through / adjustment semantics | Photoshop-fitted | W3C-style, three bugs (F1–F3) | PC1, PC2 |
| Blend formulas | Photoshop-fitted (`psblend.rs`) | W3C (F4) | PC3 |
| Proof against Photoshop | PSD merged-image oracle, floors | none (GPU vs numpy only) | PC4 |
| PSD export | full builder (unproven adjustments) | rasters, groups, masks, blends; no adjustments (F7) | PC5 |
| Atomic writes | Windows rename retry + failure injection | single `os.replace` (F9) | PC6 |
| Undo | whole-document `Arc` states, coalesce keys, selection is document state | 256² tile snapshots, stack clones, selection outside history (F6) | PC7 (PC19 later) |
| Selection modify | EDT expand/contract/border, smooth, cosine-series feather | feather only (CSS blur); AI Select has expand/feather | PC8 |
| Refine edge / matting | guided filter + smart radius + decontaminate | none | PC9 |
| Clipboard | copy/cut/paste, layer via copy/cut, floating selection | none | PC10 |
| AI paste-back | n/a (no AI) — but Poisson, match colour exist | alpha feather only (F8) | PC11, PC12 |
| Line-art extraction | colour to alpha | none | PC13 |
| Content-aware fill / healing | PatchMatch + Poisson, spot heal, patch, CA move | AI Remove only (20 s, GPU) | S1 → PC14, PC15 |
| Brush semantics | stroke buffer, opacity once, small-tip AA, deterministic | per-dab opacity (F5), round dab | PC16 |
| Smoothing | pulled string, catch-up, zoom-adjusted | per-event lerp | PC17 |
| Masks | linked, density, feather, any layer, targeting brackets | unlinked, raster-only painting | PC18 |
| Texture upload | per-tile by `Arc` identity, damage rects | whole texture per move (F10) | PC19 |
| Layers panel | drag/nest, multi-select, eye sweep, footer drop, press menus | buttons + context menu, single selection | PC20 |
| Properties | sections, inline Curves/Levels with histogram, quick actions | auto sliders, JSON text fields | PC21 |
| Mouse-first kit | latched modifiers, ✓/⊘ in options bar, popup value fields, hover preview | strong command registry, tooltips with keys, palette | PC22 |
| Transform | homography (skew/distort/perspective), warp, puppet, prefilter | scale/rotate, destructive | PC23 |
| Interactive smart select | quick selection (graph cut), magnetic lasso | AI Select (needs the GPU) | S2 → PC24 |
| T8 audit, route fuzz | prefs audit, `panic_hunt` | contract tests (D38), no fuzz | PC25, PC26 |

## 5. Proposals

**Route:** *port* = rewrite from the Rust in numpy or TS/WGSL with an attribution header; *idea* = no code; *crate* = link
`photocraft-algo` (WASM or PyO3) after a spike and a decision. Effort is in focused author+AI days at planning rates (the ratios
are the useful part, as in the ArtCraft plans).

| Id | Proposal | Fixes | Route | Effort | Value |
| --- | --- | --- | --- | --- | --- |
| **PC1** | Photoshop clipping groups (base isolated, clipped layers atop, unit blends with the base's mode) in `compose.py` and the editor | F1 | port (`compose/src/lib.rs`) | 2 | **high** — correctness, PSD parity |
| **PC2** | Pass-through opacity/mask mixing; adjustment-layer blend mode | F2, F3 | port | 1 | high — correctness |
| **PC3** | Photoshop blend formulas: Soft Light (cs > ½, cb ≤ ¼), Vivid Light extremes, Hard Mix edges, `EDGE` tolerance; optionally Darker/Lighter Color | F4 | port (`psblend.rs`, `color/blend.rs`, `compose.wgsl`) | 0.5 | high — cheap |
| **PC4** | Photoshop oracle for `compose.py` (psd-tools corpus, pinned + hashed, ratcheting floor) + a GPU = numpy parity grid in the headed check | proof | idea + psd-tools | 2 | high — locks in PC1–PC3 |
| **PC5** | PSD export: adjustment layers via ag-psd, fill opacity, pass-through, lock fix, filters rasterised; read-back test with psd-tools | F7 | idea | 1.5 | medium-high |
| **PC6** | `fsio` Windows rename retry with backoff + failure-injection tests | F9 | port (`format/src/atomic.rs`) | 0.5 | medium — cheap durability |
| **PC7** | Selection edits in history; coalesce keys so one slider drag or mask-density drag is one step | F6 | idea | 1 | **high** — daily friction |
| **PC8** | Manual selection toolkit: EDT expand/contract/border/smooth, Gaussian feather, intersect mode, polygonal lasso, marquee feather + fixed ratio, wand alpha rule + contiguous + sample merged + AA edges, select layer transparency, cursor intent badges; numpy EDT replaces `MaxFilter` in `edit_ai` | §3.1 | port (`selection/*.rs`) | 3 | **high** |
| **PC9** | Refine Edge (guided filter, smart radius, smooth/feather/contrast/shift, decontaminate) on any selection and as an AI Select option | §3.1 | port to numpy (`matting.rs`) | 2 | **high** — makes AI masks usable on hair and soft edges |
| **PC10** | Clipboard and floating selection: copy, cut, paste, paste in place, copy merged, layer via copy/cut, OS image paste and drop into Edit | §3.2 | idea | 3 | **high** — compositing |
| **PC11** | Seamless AI paste-back (Poisson clone through an eroded mask before the feather) as a recipe option; results get an editable layer mask instead of baked alpha | F8 | port (`poisson.rs`) | 2 | **high** — AI-specific |
| **PC12** | Match colour (Lab mean/std, masked) as the spec's "match colour to surroundings" option and as a candidate action | F8 | port (`tone.rs`) | 1 | medium-high |
| **PC13** | Colour to Alpha filter (line art → transparent ink) | — | port (`color_to_alpha.rs`) | 0.5 | medium-high — storyboards |
| **S1** | Spike: `photocraft-algo` as a PyO3 wheel; measure content-aware fill quality as a Remove pre-fill on `bench/inpaint`, CPU time on the rig, wheel build in CI | — | crate | 2 | gate for PC14–PC15 |
| **PC14** | Content-aware pre-fill for AI Remove + a GPU-free quick Remove for small areas | §3.6 | crate (PyO3) | 2 | high, if S1 passes |
| **PC15** | Spot Healing brush (stroke → mask → orchestrator heal verb) | §3.5 | crate (PyO3) | 1.5 | high, if S1 passes |
| **PC16** | Brush model: per-stroke coverage canvas, opacity applied once, selection clip, lock transparency, `(1−t²)⁴` falloff, small-tip supersampling | F5 | port (`paint/render.rs`) | 3 | **high** |
| **PC17** | Smoothing (pulled string, catch-up, zoom-adjusted) + Shift straight line + eyedrop while painting, both reachable by mouse | §3.5 | port (`paint/dynamics.rs`) | 1.5 | high — mouse feel |
| **PC18** | Masks: linked by default with a link toggle, paint/fill on any node kind, density + feather (non-destructive), apply mask, mask from transparency, targeting brackets | §3.4 | port + idea | 3 | high |
| **PC19** | Partial texture uploads by dirty rect (and later tile identity for undo and damage) | F10 | idea | 3 | medium — latency at 4K |
| **PC20** | Layers panel: drag reorder and nesting, multi-select, eye sweep, drop-on-footer, right-click acts on the set | §3.8 | idea | 3 | medium-high |
| **PC21** | Properties: inline Curves (spline) and Levels with histogram, colour-balance sliders, sections + quick actions | §3.7 | idea + port (`compose/adjust.rs` curve LUT) | 3 | medium-high |
| **PC22** | Mouse-first kit: latched Shift/Alt/Ctrl buttons, ✓/⊘ in the strip during transform/crop (Ctrl+Enter registered), press menus, popup value fields, hover-preview blend modes; audit menus against the seven-rule contract | D32 | idea | 3 | high — D32 |
| **PC23** | Transform: skew, distort, perspective (homography), numeric fields, prefilter before downscale, transform selection contents and groups | §3.3 | port (`transform.rs`) | 3 | medium-high |
| **S2** | Spike: `photocraft-algo` to wasm32 in a Worker; measure bundle size and per-stroke latency of quick select on a 4K document | — | crate | 2 | gate for PC24 |
| **PC24** | Quick Selection brush and Magnetic Lasso (VRAM-free) | §3.1 | crate (WASM) | 3 | medium-high, if S2 passes |
| **PC25** | Settings-that-do-nothing audit: every Settings field and `/capabilities` parameter must reach the worker (T8) | T8 | idea | 0.5 | medium |
| **PC26** | Route fuzz (`panic_hunt` over the OpenAPI routes: junk bodies → 4xx, never 500 or a hang) | — | idea | 1 | medium |

**Later, unnumbered:** Puppet Warp (ARAP, TS + Pixi mesh, 4–5 d); mesh warp and liquify; Lens Blur with a ComfyUI depth map;
multiband seams for tiled refine (needs tile compositing to move out of the ComfyUI graph); mask → vector path; a GrabCut band
re-cut of low-resolution AI masks; dithered gradients; flatting bucket fill; S3, a 16-bit PSD writer via the `psd` crate if loom2
ever leaves 8-bit.

**Not worth copying:**
- Select Subject, Focus Area and Sky (BiRefNet and SAM 3 are better);
- seam carving (954 s on 24 MP);
- the text engine, layer effects, CMYK/Lab, the plug-in ABI, the 17-language i18n;
- the egui dock (loom2's frame already has its own layout);
- ABR brush import (third-party licences).

## 6. Waves

| Wave | Proposals | Theme | Effort | Depends on |
| --- | --- | --- | --- | --- |
| **PE1 · Fidelity** | PC3, PC1, PC2, PC4, PC5, PC6 | the compositor matches Photoshop and proves it; PSD carries everything | ≈ 7.5 d | — |
| **PE2 · Selection** | PC7, PC8, PC9, PC10 | selections you can trust, refine and reuse | ≈ 9 d | PE1 not required |
| **PE3 · AI blend-in** | PC11, PC12, PC13, then S1 → PC14, PC15 | AI results that sit in the plate | ≈ 3.5 d + 2 d spike + 3.5 d | PC8's numpy EDT (for PC11's eroded mask) |
| **PE4 · Paint and masks** | PC16, PC17, PC18, PC19 | a brush that behaves; masks like Photoshop | ≈ 10.5 d | PC7 (coalesce keys) |
| **PE5 · Panels and mouse kit** | PC22, PC20, PC21 | D32 everywhere in Edit | ≈ 9 d | PC7; PC2 (adjustment blend shown honestly) |
| **PE6 · Transform and smart select** | PC23, S2 → PC24 | geometry and VRAM-free selection | ≈ 3 d + 2 d spike + 3 d | PC10 (floating selection for transform selection) |
| **with H3** | PC25, PC26 | safety and T8 | ≈ 1.5 d | ArtCraft H3 (P9, P6) |

**Order relative to the ArtCraft waves:** H2 (engine pipeline) is next in that plan. PE1 is small, fixes correctness bugs that
affect saved documents and PSD exports, and does not touch the files H2 changes (`queue.py`, `graphs.py`, `recipes.py`), so it can
run before or alongside H2. PE2–PE5 touch only the Edit suite and `edit_ai.py`. PE3's recipe options (PC11, PC12) touch `recipes.py`
and should follow H2's plan/finalize split if H2 runs first. The author decides the interleaving.

```
PE1: PC3 ─► PC1 ─► PC2 ─► PC4 ─► PC5      PC6 (any time)
PE2: PC7 ─► PC8 ─► PC9      PC10
PE3: PC11 ─► PC12      PC13      S1 ─► PC14 ─► PC15
PE4: PC16 ─► PC17      PC18      PC19
PE5: PC22 ─► PC20 ─► PC21
PE6: PC23      S2 ─► PC24
```

## 7. Delivery sketches

Each plan follows the shape used in [../artcraft/08](../artcraft/08-delivery-plans.md): goal → design → slices → tests and
acceptance → risks. Ported files carry the attribution header from [01 §4](01-overview.md), and the first port adds
`THIRD_PARTY_NOTICES.md`.

### PE1 · Fidelity

**PC3 · Photoshop blend formulas.**
- **Design:** port `soft_light_ps`, `vivid_light_ps`, `hard_mix_ps` and the `EDGE` checks in `color_burn` / `color_dodge` to
  `compose.py` and to both shader dialects in `blendModes.ts`.
- **Slices:** (1) `compose.py` + unit tests; (2) shaders + `cmpdiag`.
- **Tests:**
  - corner-value tests taken from PhotoCraft's own tests (white over black, black over white, `cb` one rounding step below 1);
  - a sweep of `cb, cs` on a 17×17 grid against the Rust formulas, transcribed as expected values.
- **Acceptance:** `cmpdiag` p99 ≤ 1 on every mode; the hard-mix max no longer at 193.
- **Risk:** saved documents using these three modes render slightly differently. Journal it.

**PC1 · Clipping groups.**
- **Design.** In `Renderer.render_nodes`, walk runs of `[base, clipped…]`:
  - render the base isolated (onto transparent);
  - composite each clipped layer **atop**: blend over the base as if it were opaque, keep the base's alpha;
  - blend the unit into the backdrop with the base's mode, opacity and mask;
  - a clipped adjustment applies to the unit, not the backdrop.
- **Editor:** each clip run becomes a document-sized pass (like an isolated group), with an atop shader in place of the `-clip`
  variants.
- **What this replaces:** a stack that relied on today's rule ("clip to everything below") renders differently. Since the UI label
  and PSD export already promise Photoshop's rule, treat this as a bug fix. Stamp `compose_version: 2` in `loom2.json` so a changed
  render can be explained.
- **Slices:** (1) `compose.py` + tests; (2) editor passes + `cmpdiag` cases (clip over opaque bg, clip to a half-alpha base over a
  bg, clipped adjustment, clipped group); (3) docs (spec 10 §3).
- **Tests:** replace the misleading case at `test_documents_m4.py:71` with a base-over-background case. Add a PSD round trip: export
  and flatten with psd-tools' composite, compare with `compose.py` once PC4 lands.
- **Acceptance:** the new tests pass; `cmpdiag` p99 ≤ 1 on all clip cases; a hand-check in Photoshop or Krita of an exported PSD
  with clipping.
- **Risk:** pass count and VRAM for documents with many clip runs; measure with `edit_headed_check.py perf`.

**PC2 · Pass-through mixing and adjustment blend.**
- **Design:**
  - **Pass-through with opacity < 1 or a mask:** render the children into a copy of the backdrop, then lerp against the original
    backdrop by `opacity × mask`, premultiplied.
  - **Adjustment:** `blended = blend(mode, backdrop, adjusted)`, then `backdrop += (blended − backdrop) × k`, keeping backdrop
    alpha.
  - **Filter layers:** keep `normal` unless a mode is set.
  - **Editor:** the pass-through mix is one extra pass; the adjustment filter takes the blend function as a uniform-selected branch
    (the blend library already exists).
- **Tests:** a group at 50 % opacity containing a Levels layer over a background must darken the background at half strength;
  multiply-mode Levels.
- **Acceptance:** `cmpdiag` cases added and passing.

**PC4 · Photoshop oracle and parity grid.**
- **Design:**
  - `scripts/fetch_corpus.py` downloads a pinned subset of psd-tools' test PSDs (MIT; pins and SHA-256 in a JSON next to it) into
    an ignored folder;
  - `orchestrator/tests/test_compose_oracle.py` (pytest marker `corpus`, skipped when absent, **failing when the marker is
    selected and the corpus is missing**) builds a loom2 stack from each PSD's layers (psd-tools as a dev dependency, MIT);
  - it flattens with `compose.py` and compares with the embedded merged image at premultiplied max ≤ 2/255;
  - a floor file records the pass count ("raise, never lower");
  - files using features loom2 lacks are listed as out of scope, not failed.
- **Parity grid:** extend `edit_headed_check.py cmpdiag` with seeded noise layers × every mode × {plain, masked, clipped, in an
  isolated group, in a pass-through group at 50 %}.
- **Acceptance:** the floor recorded in the journal; the grid passes at p99 ≤ 1.
- **Risk:** the corpus subset must stay small; pick the `blend-modes`, `clipping-mask`, `group` and `adjustment` files.

**PC5 · PSD export completeness.**
- **Design.** In `psdExport.ts`:
  - map the eight adjustment types to ag-psd's `adjustment` objects (curves points, levels, hue/sat master, colour balance tone
    ranges, exposure, B&W weights, invert, brightness/contrast) with the layer's mask, clip and blend;
  - rasterise filter layers through the exact flatten of the layers below (a `POST /documents/{id}/render?until=<id>` helper) or
    keep skipping them with the existing warning;
  - write `fillOpacity`, map group pass-through to `pass through`, and stop writing `locked` as `transparencyProtected`.
- **Tests:** an offline test that reads the exported bytes back with psd-tools and checks layer kinds, adjustment parameters, clip
  and fill.
- **Acceptance:** a manual open in Photoshop or Krita, journalled, also closes spec 10 §14's outstanding check.

**PC6 · Windows rename retry.**
- **Design:** `fsio._replace(src, dst)` retries `os.replace` on `PermissionError` 7× with backoff from 10 ms; all atomic helpers use
  it.
- **Tests:** monkeypatch `os.replace` to fail N times, then succeed; fail always → the original error, and the temp file is
  removed.
- **Acceptance:** the offline suite passes.

### PE2 · Selection

**PC7 · Selection in history; coalesce keys.**
- **Design:**
  - a history entry kind `selection` holding the before/after selection tiles (reuse `LayerPixels.touch` on the selection canvas);
  - all selection commands push it, and quick-mask strokes already do;
  - `pushHistory` takes an optional `coalesce` key, and consecutive entries with the same key and the same gesture merge;
  - sliders pass `<command>:<pointerdown id>`.
- **Tests:** once the frontend harness exists (ArtCraft P6), store tests; until then a `tour` step in the headed check (select,
  invert, undo, undo → original selection).
- **Acceptance:** every selection command is undoable; one opacity drag is one history row.

**PC8 · Manual selection toolkit.**
- **Design:**
  - `selectionOps.ts` in a Worker: FH-EDT, expand, contract, border, smooth and Gaussian feather on the grey selection, with
    commands, Selection panel buttons, a canvas right-click menu with a selection, and numeric popup fields;
  - marquee: intersect mode, feather px, fixed ratio / fixed size;
  - lasso: polygonal mode (click points; double-click or ✓ closes, ⊘ cancels);
  - wand: per-channel tolerance including alpha, transparent pixels match regardless of hidden RGB, contiguous toggle, sample
    merged (reads the GPU composite as the eyedropper does), anti-aliased edges;
  - **Load layer transparency as selection** from the layer row menu and thumbnail.
  - Orchestrator: `edit_ai.dilate` uses a numpy EDT (round, fractional) instead of `MaxFilter`.
- **Slices:** EDT + modify commands → marquee/lasso modes → wand → numpy EDT.
- **Tests:** EDT against brute force on random masks (TS and Python); expand by r of a single pixel is a disc.
- **Acceptance:** the headed `tour` exercises each command by mouse.

**PC9 · Refine Edge.**
- **Design:**
  - `orchestrator/loom2/matting.py`: guided filter (cumsum box means, batched 3×3 inverse), smart radius, band blend via the PC8
    EDT, smooth / feather / contrast / shift edge, decontaminate (writes an RGB-corrected copy only when asked);
  - route `POST /documents/{id}/selection/refine` with params from `/capabilities` (T8), running on the document flatten in a
    thread;
  - UI: a Selection-panel "Refine edge…" with live preview on a downsampled proxy (settle-cancel, 04 §6), and a "refine" checkbox in
    AI Select that runs it after segmentation.
- **Tests:** a synthetic hair-like image (thin dark strands on a light background) with a binary mask: after refine, the mask
  gradient correlates with the image edges; hard edges stay hard.
- **Acceptance:** rig: refine on a 1080p BiRefNet result in < 1 s, journalled with before/after crops.
- **Risk:** 4K speed in numpy. Restrict work to boundary tiles, as PhotoCraft does.

**PC10 · Clipboard and floating selection.**
- **Design:**
  - commands copy, cut, paste, paste in place, copy merged, layer via copy, layer via cut; an internal clipboard of `LayerPixels` +
    offset, mirrored to the OS clipboard as PNG;
  - paste creates a new layer at the viewport centre or in place, selected and ready to transform;
  - OS image paste and file drop into the Edit canvas create a layer (the file is ingested into the Catalogue first, so lineage
    holds);
  - all with right-click and toolbar placements (D32).
- **Tests:** headed `tour` step.
- **Risk:** the WebView2 clipboard permission for image read. Fall back to the internal clipboard with a toast.

### PE3 · AI blend-in

**PC11 · Seamless paste-back; results with masks.**
- **Design:**
  - `poisson.py`: membrane solve by cascadic multigrid + red-black SOR (`FINE_ITERS 30`, ω 1.7, tolerance 2e-5);
  - `assemble_layer(…, blend="feather"|"seamless")`: in seamless mode, erode the mask by the feather radius, clone the AI result
    onto the original crop through it, then apply the feathered alpha as today;
  - the option appears in the AI panel and the recipe (T8: default shown = default run, listed in `/capabilities`);
  - separately, result layers store the paste-back alpha as a **linked layer mask** (feathered) over opaque RGB, so a seam can be
    repainted with the brush. Old documents keep working, since a layer without a mask renders as before.
- **Tests:** a synthetic plate with a gradient and an AI result offset in brightness by +20: seamless reduces the boundary step
  below 2 levels; feather leaves it.
- **Acceptance:** rig, m5 bench task 02 (inpaint) side by side, journalled.
- **Risk:** Poisson can bleed strong edges that cross the mask boundary. Keep "feather" as the default until the bench says
  otherwise.

**PC12 · Match colour.**
- **Design:** `tone.py` `match_color(src, ref, src_mask, ref_mask, strength)` in Lab. It runs as the spec's "match colour to
  surroundings" option (reference = a ring around the mask in the original), and as a candidate-strip action "Match to plate".
  The first version bakes the result into the candidate layer, with undo.
- **Tests:** match of a tinted copy returns within 1 level of the original's mean.

**PC13 · Colour to Alpha.**
- **Design:** a new filter type `color_to_alpha{color, transparency, opacity}` in `compose.py` and `adjustFilters.ts` (a shader
  port), plus a one-click command "Ink from white" (the line-art preset).
- **Tests:** unmixing a known composite of black ink at α 0.5 over white returns black at α 0.5.

**S1 · PyO3 spike.**
- **Questions:**
  1. Does a maturin abi3 wheel of a small wrapper over `photocraft-algo` (pinned to `b37bff98`) build on Windows MSVC py3.13 and in
     CI?
  2. On the rig, what do `content_aware::fill` and `inpaint::complete` cost on 1080p holes typical of Remove?
  3. On `bench/inpaint`, is Remove with a content-aware pre-fill (ICM at denoise 1.0, and at 0.6–0.8) visibly better than
     mid-grey, as judged by the author on candidate sheets?
- **Exit:** a journal entry with numbers and sheets, and a D-number recording go or no-go.

**PC14 · Content-aware pre-fill and quick Remove** (after S1 go).
- `edit_ai` fills the hole with `content_aware.fill` before upload in Remove mode.
- A "Quick remove (no GPU)" mode returns the content-aware result directly as a candidate layer, in about a second.

**PC15 · Spot Healing** (after S1 go).
- A brush tool whose stroke becomes a mask, sent to `POST /documents/{id}/heal`. It runs `spot_heal` (synthesise over dilate-2,
  Poisson over dilate-1) and inserts the result as a new layer above the target, so it stays non-destructive.

### PE4 · Paint and masks

**PC16 · Brush model.**
- **Design.** A per-stroke **coverage canvas** (alpha only, layer-sized or tiled):
  - dabs draw `source-over` at alpha = flow (`(1−t²)⁴` falloff with a hardness core; radius < 3 px supersampled 4×4 when the dab
    is built);
  - on each move, the touched rect of the layer is recomposited as `pre-stroke ⊕ colour × coverage × opacity × selection`, honouring
    a new lock-transparency flag;
  - the eraser and mask painting use the same buffer with `destination-out` or a value target;
  - on the GPU later, the same model maps to fixed-function blending (03 §3).
- **Tests:** headed `paint` check: a scribble with 50 % opacity and 100 % flow never exceeds 50 % coverage; 1 px lines don't bead.
- **Acceptance:** `edit_headed_check.py perf` brush latency on 4K not worse than M7 (33 ms p50).

**PC17 · Smoothing and modifiers.**
- **Design:**
  - port `Smoother` (pulled string and exponential modes, catch-up and catch-up-on-end, zoom-adjusted) and `PathWalker`;
  - an rAF feed while the pointer is held still;
  - Shift-click draws a straight line from the last point;
  - Alt-click picks colour while a painting tool is active.
  - Both modifiers come with a mouse path: latched modifier buttons (PC22), and a "line" toggle plus an eyedropper chip in the
    brush options.
- **Tests:** unit tests of `Smoother` against PhotoCraft's `dynamics` tests (same inputs → same points).

**PC18 · Masks.**
- **Design:**
  - `addMask` creates a **linked**, layer-sized mask; a chain toggle sits between the thumbnails and in Properties;
  - `paintTarget` accepts masks on any node kind;
  - `MaskRef` gains `density` and `feather` (document schema 1 → 2, defaults 1 and 0, migration by defaults) in `documents.py`,
    `compose.py` (`1 − density·(1 − v)`, Gaussian feather σ = feather px) and the editor (the mask pass samples a feathered copy);
  - commands Apply mask and Mask from transparency;
  - targeting brackets on the active thumbnail; the trash and Properties follow the target.
- **Tests:** `compose.py` density and feather unit tests; `cmpdiag` cases.

**PC19 · Partial texture uploads.**
- **Design:** `LayerPixels.refresh(rect?)` uploads only the dirty rect (Pixi v8 `TextureSource.update` replaced by a sub-region
  upload on WebGPU, `texSubImage2D` on WebGL2). Tile identity for undo and damage (02 §5) stays a later step.
- **Acceptance:** `perf`: brush latency on an 8K document stays within 10 % of 4K.

### PE5 · Panels and the mouse kit

**PC22 · Mouse-first kit.**
- Latched Shift / Alt / Ctrl buttons in the strip (they modify the next pointer gesture and show their state).
- ✓ / ⊘ in the strip during transform and crop; register Ctrl+Enter.
- Press menus for "Add adjustment ▾" and "Add filter ▾".
- A popup value field component for opacity, fill and brush numbers.
- Hover-preview and wheel-step on the blend dropdown (a single history step on choose).
- An audit of `editCommands.ts` menus against the seven-rule contract (04 §5), especially "a row in a multi-selection acts on the
  set" and "no clickable no-ops".

**PC20 · Layers panel.**
- Multi-select (click, Ctrl, Shift), with the selection used by group, delete, duplicate, merge, visibility and move.
- Drag to reorder and into or out of groups, with an insertion line and edge auto-scroll.
- Eye sweep.
- Drop on the footer's trash, new and group buttons.
- One history step per gesture.

**PC21 · Properties.**
- **Curves** editor: click to add, drag out to delete, per channel, histogram of the image below. Monotone cubic interpolation
  through a `curve_lut` port, with `interp: "spline"` on new curves; existing `linear` curves keep rendering as they are.
- **Levels** with a histogram and triangle sliders.
- **Colour balance** as three slider rows per tone range.
- Collapsible sections, and quick actions per kind.

### PE6 · Transform and smart select

**PC23 · Transform.**
- Port `Homography::rect_to_quad` / `inverse`. Ctrl-corner distorts; skew and perspective are menu modes.
- Numeric X / Y / W / H / angle fields in the strip; interpolation choice.
- Prefilter by a real downscale below 50 %.
- **Transform selection contents** creates a floating layer (PC10).
- **Transform a group** transforms its rasters together.
- The apply still bakes, but from the original pixels while the transform is open (no compounding).

**S2 · WASM spike.**
- Build a wasm-bindgen wrapper over `segment::quick` and `magnetic` (single-threaded).
- Measure the gzipped size and the per-stroke latency on 1080p and 4K in a Worker.
- Exit: journal + D-number.

**PC24 · Quick Selection and Magnetic Lasso** (after S2 go).
- Tools Q-select and magnetic lasso, sharing the Worker; add/subtract via the options bar and latched modifiers.

### With H3

**PC25 · Settings audit.**
- `scripts/settings_audit.py` lists every Settings field, `/capabilities` parameter and recipe default.
- It fails if a field is never read by the code path that runs jobs (static scan, with an allow-list for UI-only fields).
- Wired into CI next to `agents_check.py`.

**PC26 · Route fuzz.**
- `test_route_fuzz.py` iterates the OpenAPI document: for every route, four junk bodies and path params. It asserts no 500, and a
  response within 4 s, against the fake-ComfyUI services fixture.

## 8. Decisions to record before starting

- **A wave, when started:** one D-number per wave or per proposal group, as H1 did (D35–D38).
- **PC1–PC3** change how existing documents render. Record that this is a bug fix toward Photoshop semantics, and the
  `compose_version` stamp.
- **PC18** bumps the document schema (`DOC_SCHEMA_VERSION` 1 → 2).
- **S1 and S2** each end in a go or no-go D-number. A go adds a Rust build to the orchestrator (S1) or the frontend (S2), which is a
  stack change under the house rules.
- **Any port** adds `THIRD_PARTY_NOTICES.md` and the per-file header (01 §4).
