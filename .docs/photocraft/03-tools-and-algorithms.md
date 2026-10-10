# 03 · Tools and algorithms

**Why these crates are easy to reuse.** `photocraft-algo` depends only on `geom`, `color`, `raster`, `serde` and `rustfft` (plus
`rayon` natively), and `photocraft-paint` only on `geom`, `color`, `raster` and `serde`. Both build for wasm32. They contain no
`unsafe` and no panics, and they treat every input as hostile.

**Inputs.** Most kernels take plain buffers: interleaved `w × h × ch` `f32` 0..1 plus `&[bool]` or `&[f32]` masks. Examples:
`inpaint::complete`, `poisson::seamless_clone`, `content_aware::fill`, `matting::refine_buffer`, `selection::expand`,
`selection::feather`, `selection::wand_region`. The others read through a `segment::Sampler` trait; `ImageSampler` in
`segment/mod.rs` is the template for wrapping a numpy or JS buffer.

**Selection type.** PhotoCraft's selection is an 8-bit grey coverage surface, which maps directly onto loom2's one-byte-per-pixel
selection (`PUT /documents/{id}/selection`).

Value ratings below are **for loom2** (a mouse-driven storyboard editor that composites AI output), not in general.

## 1. Selection

| Tool | Source | How it works | Value | Route |
| --- | --- | --- | --- | --- |
| **Refine Edge / Select and Mask** | `algo/src/matting.rs` (746 lines) | **Guided filter** (He–Sun–Tang) of the binary mask with the image as guide, using O(1) box means. It is blended in only within `radius` of the boundary, using an EDT of the boundary. **Smart radius** (`edge_width`) estimates the transition width per pixel as luminance range ÷ max gradient, so hard edges stay hard and hair gets a wide band. Then, in Photoshop order: smooth, feather (σ = feather/2), contrast, shift edge (grey morphology). Only 256² tiles near the boundary are processed. **Decontaminate colours** pulls fringe pixels (0.02 < α < 0.98) toward the normalised-convolution average of nearby fully selected pixels. | **High.** It is the natural post-process for BiRefNet and SAM 3 masks: it snaps upscaled masks to real edges, gives hair a soft edge, and removes background colour spill from cut-outs. | Port to numpy (cumsum box means, batched 3×3 inverse). Needs an EDT: a numpy Felzenszwalb–Huttenlocher (FH) EDT, or scipy. |
| **Modify: expand / contract / border / smooth / feather** | `selection/distance.rs`, `selection_blur.rs` | **EDT:** Felzenszwalb–Huttenlocher, separable. **Expand:** `max(v, clamp(r+1−d))`, round and fractional. **Contract** is expand of the inverse; **border** is expand minus contract. **Smooth:** running-sum box blur, then re-threshold. **Feather:** Gaussian σ = r/2; wide radii use a fitted 5-term cosine series with O(1) sliding sums. Feather r50 on 24 MP takes 122 ms. | **Medium-high.** loom2's `edit_ai.dilate` uses PIL `MaxFilter`, a square element that is slow at large radii, and loom2 has no manual modify at all. | TS port (FH-EDT ≈ 100 lines) for the editor; the same in numpy for `edit_ai`. |
| **Magic wand** | `selection.rs::wand_region` | Scanline flood (contiguous, 4-connected) or a global match. **Tolerance is per channel including alpha, and fully transparent pixels match regardless of their hidden RGB.** Anti-aliasing touches only edge pixels inside the touched bbox. Sample Merged happens at engine level. Grow / Similar use the selected pixels' min/max box widened by tolerance. | Medium. loom2 has a hard-edged wand on one layer. | TS port, ≈ 150 lines. |
| **Quick Selection** | `segment/quick.rs` (258), `segment/maxflow.rs` (363) | One Boykov–Jolly min cut (Boykov–Kolmogorov max-flow) on an 8-connected grid. The brush footprint is hard foreground; there is an area cost beyond it and contrast-sensitive edge weights. Constants were fitted to Photoshop 25.4 masks. It works in a window around the stroke that doubles while the cut touches its edge; above 512² it runs at half resolution, with a banded coarse-to-fine cut for large windows. | **High for loom2 specifically.** It is mouse-first "paint to select", it runs on the CPU and **uses no VRAM**, so it works while ComfyUI holds the card. | WASM crate in a Worker (BK max-flow is fiddly to port). Spike S2. |
| **Magnetic Lasso** | `algo/src/magnetic.rs` (602) | Mortensen–Barrett live-wire: Dijkstra over pixels, with link costs for edge centre, edge strength, direction, length and pull toward the pointer path. The search is confined to a corridor around the pointer path, and pixels are fetched lazily in cached 128² blocks. Auto-fastening and frequency live in the UI. | Medium-high: precise mouse outlines of characters and props. | Same WASM bundle, or a TS port (≈ 600 lines). |
| **Object Selection** | `segment/grabcut.rs` | GrabCut (GMM K = 5, 8 iterations) in a rectangle, then island cleanup, then **`finish_region`**: a full-resolution graph-cut re-cut of only the boundary band, in parallel 192² tiles. | Low as a tool (SAM 3 box prompts are better). **The band re-cut is valuable on its own** for sharpening any low-resolution AI mask. | PyO3, later. |
| **Colour Range** | `selection.rs` | A CIELAB box spanned by samples, with a/b weighted ×3 and a B-spline falloff. It matches Photoshop 2024 to about half a level. Also hue range and tone range. | Medium: re-colouring props and skies. | TS or numpy port, a few hours. |
| **Polygon / lasso fill** | `selection::polygon` | Even-odd fill with exact horizontal coverage on 4 sub-rows. | Low-medium (anti-aliased lasso). | TS port, trivial. |
| **Marching ants** | `ui-egui/src/outline.rs` | Mask boundary traced at **display** resolution (step = power of two of 1/zoom), cached by mask fingerprint and quantised viewport. Dashes are phased in screen space. | Medium. loom2 traces on the CPU at document resolution. | TS port, or a WGSL edge shader on the mask texture. |
| Select Subject, Focus Area, Sky | `segment/subject.rs`, `focus.rs`, `sky.rs` | Saliency heuristics plus GrabCut. | Low: BiRefNet is far better. | Skip. |

## 2. Retouching

| Tool | Source | How it works | Value | Route |
| --- | --- | --- | --- | --- |
| **Poisson seamless clone** | `algo/src/poisson.rs` (328) | Pérez cloning written as `f = g + h`, where `h` is the membrane (harmonic) interpolant of the boundary mismatch. It is solved by **cascadic multigrid + SOR** (halve recursively, solve, prolong, a few sweeps per level; ω 1.7), "a 300 px dab in a few ms". | **High: AI paste-back.** `edit_ai.assemble_layer` uses alpha = feathered mask only (**verified**), so VAE colour drift and exposure mismatch show as halos. Cloning the AI result onto the original crop through an eroded mask *before* the alpha feather fixes the low-frequency drift and keeps the AI texture. | Port to numpy (red-black Gauss–Seidel vectorises well), ≈ 150 lines. |
| **Content-Aware Fill / completion** | `algo/src/inpaint.rs`, `content_aware.rs` | Wexler–Shechtman–Irani multiscale EM with a PatchMatch nearest-neighbour field. The coarsest level starts from a membrane fill. Rotation, scale and mirror adaptation; low-frequency colour adaptation toward the membrane interpolation; a sampling-area mask. Deterministic and cancellable. 218 ms on 10 MP. | **High**, for two reasons: (1) a GPU-free Remove for wires, small objects and AI glitches that never evicts the loaded model; (2) **a pre-fill for AI Remove**. Today loom2's Remove fills the hole with mid-grey; a content-aware pre-fill gives the diffusion model coherent context. | PyO3 crate (PatchMatch is too slow in pure numpy). Spike S1. |
| **Spot Healing** | `engine/src/retouch_cmds.rs::spot_heal_surface` | Region = stroke bbox plus margin. Synthesise over the hole dilated by 2 (this makes the Poisson boundary non-trivial), then `seamless_clone` on the hole dilated by 1, composited through stroke coverage. 157 ms per stroke on 10 MP. | High: cleans AI seams and artefacts with a mouse brush. | Brush → mask → orchestrator verb, on top of S1's crate. |
| **Healing brush, Patch, Content-Aware Move** | `retouch_cmds.rs`, `retouch_cmds/patch.rs`, `content_aware_move.rs` | All composed from the same two kernels. Content-Aware Move pastes at an offset, re-synthesises an edge band and fills the vacated area, excluding the moved content so no ghost appears. | Medium-high: nudging a character or prop is a common storyboard edit. | After S1. |
| **Match Color** | `algo/src/tone.rs` (`lab_stats`, `match_color`) | Lab mean and standard-deviation transfer, optionally masked. | **Medium-high.** It harmonises an AI insert or candidate with the plate. Spec 10 promises "match colour to surroundings", but it does not exist (**verified**: no such option in the AI panel or recipes). | Port to numpy, ≈ 0.5 day. |
| **Colour to Alpha** | `algo/src/color_to_alpha.rs` (236) | The exact unmix `a = max_i a_i`, `Q = C + (P−C)/a`, with transparency and opacity thresholds. | **High for storyboards:** it turns scanned or AI line art on white into a transparent ink layer with no fringe. | Port, about an hour (a filter type in `compose.py` + `adjustFilters.ts`, or a one-shot command). |
| **Multiband (Laplacian pyramid) blend** | `algo/src/pyramid.rs` | Burt–Adelson. | Medium: hides tiled-refine seams better than linear feathering, but loom2 composites tiles inside the ComfyUI graph today. | numpy, if tile compositing moves to the orchestrator. |
| Clone stamp, history brush, dodge/burn/sponge, blur/smudge, red eye, mixer | `paint/src/retouch.rs`, `algo/src/retouch.rs`, `redeye.rs`, `paint/src/mixer.rs` | `per_dab(e, spacing) = 1−(1−e)^spacing` makes strength independent of spacing. | Low to medium. AI layers plus masks already "paint back the original". | Later, per need. |

## 3. Brush engine (`crates/paint`)

**Data model** (`brush.rs`):
- `BrushSettings` holds size, hardness, spacing (or time-based "speed spacing"), opacity, flow, tip (round / sampled), angle,
  roundness, Shape Dynamics, Scattering, Texture, Dual Brush, Colour Dynamics, Transfer, build-up, smoothing and seed.
- `StrokePoint` follows W3C Pointer Events fields (pressure, tiltX/Y, twist, time). A mouse reports pressure 1, so pen support
  later maps straight from `PointerEvent`.

**Smoothing** (`dynamics.rs`, 695 lines). This is the biggest feel improvement for mouse drawing.
- **Pulled string (lazy mouse).** The string length is `amount × 100` screen px, divided by zoom when "adjust for zoom" is on. The
  brush moves only when the string is taut.
- **Exponential mode.** Every 16 ms of stroke time, the brush moves a fraction `1 − amount` (amount capped at 0.95) toward the
  pointer, in ≤ 64 sub-steps per input, so the feel does not depend on the device report rate.
- **Catch-up.** While the pointer pauses, the canvas keeps feeding the held point. **Catch-up on end** finishes the stroke at the
  last pointer position.
- **`PathWalker`.** Emits dabs every `step_len` px along the polyline and carries the remainder across segments. It also emits
  time-based airbrush steps.

**Accumulation and compositing** (`render.rs`). Photoshop's opacity/flow semantics:
- Dabs accumulate into a sparse per-stroke **coverage buffer** (64² f32 tiles) as `c ← c + v·(ceil − c)`, so flow builds toward
  each dab's opacity ceiling. Wet edges use `max`.
- The whole buffer composites **once onto the pre-stroke pixels** at stroke opacity, clipped by the selection and by lock
  transparency.
- Result: overlapping dabs within one stroke never exceed the stroke's opacity.
- **loom2 today (verified, `EditorCanvas.tsx` `stamp`, `layerPixels.ts` `makeDab`):** opacity is baked into each dab and flow is
  `globalAlpha` per dab, so overlapping dabs build past the opacity setting.

**Tip.**
- Falloff (`lib.rs::tip_falloff`): a hard core of `hardness·r`, then `(1−t²)⁴`. That tracks a Gaussian, reaches exactly 0 and
  needs no `exp`.
- **Tips under 3 px radius use 4×4 sub-pixel area sampling**, so thin lines don't bead.

**Determinism** (`rng.rs`): counter-based randomness, `mix64(seed ^ mix64(index·K1 ^ stream·K2))`, with one stream per jittered
quantity. A dab depends only on the seed and its index, so a stroke recorded as data re-renders bit-exactly.

**A GPU mapping.** `c + v·(ceil − c)` = `v·ceil + c·(1 − v)`, which is fixed-function blending (source factor = constant `ceil`,
destination factor = one-minus-source-alpha). Dabs can therefore be instanced quads into an `r16float` stroke texture. A simpler
step that also works on loom2's Canvas2D layers:
- draw dabs `source-over` at alpha = flow into a per-stroke **coverage canvas** (the ceiling is constant at 1 when nothing jitters
  opacity);
- recomposite `pre-stroke ⊕ colour × coverage × opacity` over the dirty rect on each move.

**Not relevant:** the tablet crate (WebView2 PointerEvents already carry pressure), ABR import (third-party brush licences are a
minefield).

## 4. Transforms, warps and fills

| Feature | Source | Note for loom2 | Value | Route |
| --- | --- | --- | --- | --- |
| **Free transform with homography** | `algo/src/transform.rs` | `Homography::rect_to_quad`; inverse mapping per destination tile with premultiplied bicubic sampling. **It pre-reduces with a real resize before large downscales**, because "bicubic alone aliases below ~50 %". loom2's `transform.ts` has scale/rotate only, resamples through Canvas2D "high", and every apply resamples destructively. | Medium-high | TS port: skew, distort, perspective, numeric fields, prefilter on downscale. |
| **Puppet Warp** | `algo/src/puppet.rs` (966) | Triangle ARAP (Liu 2008): local rotations, then a global Jacobi-preconditioned CG; pins are stiff soft constraints. Re-posing a cut-out character's arm before an AI refine pass is a strong pre-AI edit. | Medium-high | TS solver + Pixi mesh, 4–5 days. |
| **Warp, Perspective Warp, Liquify** | `warp.rs`, `perspective.rs`, `liquify.rs` | Warp is a subdivided mesh, which Pixi `MeshPlane` renders on the GPU. Liquify is an inverse displacement field on a grid with replayable strokes. | Medium | Later. |
| **Gradient** | `algo/src/paint.rs` | Five shapes; **dithered by default** to break banding. | Low-medium; the dither is about 10 lines. | Port. |
| **Paint bucket** | `bucket_fill_region_src` | "Boundary from the visible composite, paint into the target layer". This is the flatting variant for filling under line art on its own layer. loom2's fill ignores the click point and fills the whole selection or layer. | Medium | TS (wand region + fill). |
| **Seam carving** | `algo/src/seam.rs` | 954 s on 24 MP. | Avoid. | — |

## 5. Filters worth knowing

- **Gaussian blur** for radius > 4: three running-sum box passes, so cost doesn't depend on the radius.
- **Reduce Noise** (`denoise.rs`): a guided filter on luminance plus guided chroma smoothing. It is a cheap cleanup of grainy AI
  output and reuses the refine-edge guided filter.
- **Lens Blur with a depth map** (`blur2.rs`, shaped kernels as spans over row prefix sums): depth of field on storyboard frames
  when paired with a ComfyUI depth map. Medium value.
- **Surface Blur, Smart Sharpen, Median, Dust & Scratches, motion blur via FFT:** standard; low value for loom2.

## 6. Vector and type (brief)

- **`vector/src/trace.rs`:** mask → path, using marching squares at 0.5, corners where the direction turns more than 60° and
  Schneider cubic fitting. It turns AI masks into smooth, editable outlines or SVG. Medium value; about 450 lines to port.
- **`crates/text`:** parley shaping, PSD `TySh` round trip and warp styles. Low value for loom2: Canvas text plus ag-psd is enough,
  and annotation may live in the Story suite.
