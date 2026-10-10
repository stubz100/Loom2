# 02 · Engine and compositing

Where `docs/architecture.md` describes a target design that the code has not reached, this chapter follows the code. The main
differences:
- there is no shared draw-op plan: the CPU compositor walks the tree directly, and the GPU crate has its own planner that mirrors it;
- history stores whole documents, not op diffs;
- there is no engine thread;
- sample types are U8, U16 and F32 only;
- the GPU compositor is one WGSL uber-shader.

## 1. Document model (`crates/doc/src/lib.rs`)

- **`Document`:**
  - size, DPI, colour mode and sample depth as runtime data, plus an optional ICC profile;
  - layers bottom-to-top (PSD order);
  - alpha channels (saved selections);
  - `selection: Option<Surface>`, a grey coverage surface with no vector outline;
  - quick mask, which is part of the document, so entering and leaving it are history steps;
  - paths, layer comps and more.
- **`Layer`:**
  - `visible`, `locks`, `blend`, `opacity`, `fill_opacity`, `clipped`;
  - `mask: Option<LayerMask>` and `vector_mask`;
  - `effects`, `blend_if`, `advanced` (knockout, blend clipped as group, …), `excluded_channels`;
  - `psd_blocks`, unknown PSD data kept verbatim for a lossless round trip.
- **`LayerContent`:** `Raster`, `Group{children, expanded, artboard}`, `Adjustment`, `Fill`, `Text`, `Shape`, `Smart`.
  - Smart filters are stored as **command id + JSON params**, the same ids the menus use.
- **`LayerMask{surface, enabled, linked, density, feather}`:**
  - effective value `1 − density·(1 − v)`;
  - feather is a Gaussian (σ = feather px, approximated by three box blurs) fitted against the psd-tools corpus;
  - linked by default.
- **Adjustments** (`doc/src/adjust.rs`): Brightness/Contrast, Levels, Curves, Exposure, Vibrance, Hue/Saturation with six hue
  ranges, Color Balance, Black & White, Photo Filter, Channel Mixer, Color Lookup, Invert, Posterize, Threshold, Gradient Map,
  Selective Color, plus `Unsupported` (kept raw).

## 2. Raster storage: copy-on-write tiles (`crates/raster/src/lib.rs`)

- `Surface{format, default_pixel, tiles: BTreeMap<TileCoord, Arc<Tile>>}` with 256² tiles. Missing tiles read as the default pixel,
  and coordinates are i32, so layers can extend off-canvas.
- **Copy-on-write:** `tile_mut()` calls `Arc::make_mut`, so a tile is copied only when it is touched *and* shared. Cloning a
  document costs O(layers + tile pointers).
  - `fill_rect` shares one `Arc` across all fully covered tiles.
  - `translated()` reuses tiles outright for tile-aligned moves.
  - `prune()` drops all-default tiles.
- **Pointer identity replaces version counters.** `Arc::ptr_eq` decides GPU re-upload, keys the effect-map and mask caches,
  drives history byte accounting and computes undo damage. Caches hold the keyed tiles alive so addresses can't be reused.
- **Straight (not premultiplied) alpha** at every depth; samples are normalised floats at the API.
- **`Interrupt`** (`raster/src/interrupt.rs`): a `Copy` struct with a cancel predicate and a progress callback. Algorithms check
  it once per tile or band. This is why the `algo` kernels are cancellable.

## 3. CPU compositor: the oracle (`crates/compose`)

`render(doc, rect)` renders 256² tiles in parallel (rayon) into straight-alpha f32. Effect maps are prepared once before tiling,
and band rendering bounds peak memory on export.

### 3.1 Photoshop semantics (`composite_layer_plain`, `compose/src/lib.rs` ~l.1106)

| Construct | PhotoCraft (fitted to Photoshop) |
| --- | --- |
| **Clipping** | The base renders **isolated**. Each clipped layer composites **atop**: it blends as if the base were opaque, and the result keeps the base's alpha. The finished base+clip unit then blends into the backdrop with the **base's** mode and opacity. `blend_clipped_as_group = false` composites each clipped layer in its own mode. |
| **Pass-through group** | Children composite straight into the backdrop. With opacity < 1 or a mask, the result is mixed against a **copy of the original backdrop** by `opacity × mask` (a premultiplied mix, stored straight). At fill < 100 % or with effects the group renders isolated, as Photoshop does. Layers clipped to a pass-through group are added as "isolated with clip" minus "isolated without". |
| **Isolated group** | Children composite onto transparent, then the result blends like a layer. |
| **Adjustment layer** | `adjusted = apply(adj, backdrop)`. Clipped layers composite onto `adjusted`. Then `blended = blend_rgb(layer.blend, backdrop, adjusted)` and `backdrop += (blended − backdrop) × opacity × fill × mask`. **The adjustment's own blend mode applies**, and **backdrop alpha is unchanged**. |
| **Rounding** | After every adjustment layer the result is quantised to the document depth (255 steps at 8 bit). On one psd-tools file this cut mismatched pixels from 9.6 % to 5.1 %. |
| **Dissolve** | Coverage from a hash of document coordinates, so it is stable under tiling. |
| **Blend-If, knockout, excluded channels** | Applied against the pre-layer backdrop. These are not relevant to loom2. |

### 3.2 Blend math (`crates/color/src/blend.rs`, `crates/compose/src/psblend.rs`)

The generic reference is W3C Compositing Level 1. Photoshop-specific overrides were derived from Photoshop's composites in the
psd-tools `blend-modes/*.psd` files:

- **Soft Light** (`soft_light_ps`): `cs ≤ ½: 2·cb·cs + cb²(1−2cs)`; otherwise `2·cb(1−cs) + √cb·(2cs−1)`. The lower half is
  algebraically the W3C formula; **the upper half differs** (W3C uses a piecewise `D(cb)` there).
- **Vivid Light** (`vivid_light_ps`): the **source** extremes win. `cs = 0` gives 0 even over white, and `cs = 1` gives 1 even
  over black. The generic Burn/Dodge let the backdrop extremes win.
- **Hard Mix** (`hard_mix_ps`): 1 where the *generic* vivid light ≥ 0.5 − 1e-6, else 0. For interior values this is `cb + cs ≥ 1`;
  the asymmetric edges (black over white → white, white over black → black) match Photoshop.
- **Color Burn / Dodge, `EDGE = 1e-4`:** a backdrop within 1e-4 of 0 or 1 counts as exact. Otherwise a value that should be 1
  can come out one rounding step lower (and differently on the GPU), flipping the result by up to 255 levels.
- **Non-separable modes:** W3C SetLum / SetSat / ClipColor with luminance weights 0.3 / 0.59 / 0.11.
- **Extra modes:** Darker Color and Lighter Color complete Photoshop's 27 modes.
- **Compositing formula:** `αo·Co = (1−αs)·αb·Cb + (1−αb)·αs·Cs + αs·αb·B(Cb,Cs)` on straight inputs.

### 3.3 Adjustments (`compose/src/adjust.rs`)

- **Curves:** 4096-entry LUTs from a spline through the points. loom2 interpolates linearly.
- **Levels:** quantised to the document depth.
- **Linearisation:** sRGB for colour documents; γ 1.732 for grey; a pure 2.2 power for Exposure. All were fitted on the corpus.
- **Hue/Saturation:** uses hue-range tables.

### 3.4 How parity with Photoshop is proved

Every PSD embeds Photoshop's merged composite, which is a **free oracle**.
- `crates/io/tests/corpus.rs` flattens each file and compares it with that image. A file passes at a premultiplied max difference
  ≤ 2/255; Dissolve gets its own block-statistics metric.
- The suite enforces **ratcheting pass floors** ("raise, never lower"): psd-tools 236/309, mixed 146/170, Photoshop-authored
  133/256.
- The corpora are pinned by hash and fetched on demand (`xtask/src/corpus_pins.rs`), never committed.
- `cargo run -p photocraft-io --example oracle_diff -- file.psd 0 png diff.png` writes ours | Photoshop | heatmap side by side.

## 4. GPU compositor (`crates/gpu`)

- **Planner** (`plan.rs`): turns the document into a linear list of passes over abstract accumulator slots (ping-pong, recycled
  when unreferenced). Each kernel is a fragment entry point in `compose.wgsl` (1,207 lines): `fs_content`, `fs_mask`, `fs_blend`,
  `fs_atop` (clip), `fs_adjust`, `fs_adjmix`, `fs_lerp` (pass-through mix), plus the effect kernels.
- **Shader-side blending.** All blending reads the backdrop texture; there is no fixed-function blending. The WGSL blend
  functions are line-for-line ports of the Rust ones, with the same `EDGE` constant.
- **Accumulators are `Rgba32Float`.** Posterize, Threshold, Hard Mix and Dissolve must land on the same side of their thresholds as
  the CPU. `Rgba16Float` is the fallback where 32-bit float can't be rendered.
- **Paging.** Layers live in 2048² page textures; only 256² tiles whose `Arc` changed are re-uploaded. An LRU keeps pages under
  4 GB.
- **Bounded submits.** Work is flushed every 512 MB of uploads or 1 Gpx of pass work, so the Windows GPU watchdog (TDR) never
  resets the device. On device loss, `health.rs` switches permanently to the CPU path.
- **GPU = CPU guarantee** (`gpu/tests/parity.rs`, about 96 tests):
  - seeded noise layers across every mode, adjustment, and group/clip/mask/fill combination, at tolerance 1/255 + 4ε premultiplied;
  - each case runs twice, once with a simulated 256 px texture limit, to catch page and chunk seams.
- **Incremental recompositing.**
  - Commands set `last_damage`.
  - Undo and redo compute damage by pairing layers by id and diffing tile pointers (`layer_multi_cmds::step_damage`). Structural
    changes return "redraw everything".
  - The canvas grows the damage by each effect's reach and recomposites only that rect.

## 5. History (`crates/ops`)

- **Model.** `History{undo: VecDeque<HistoryState{label, doc: Arc<Document>, layers}>, redo, max_states 50, max_bytes}`. Undo
  swaps `Arc`s; there are no pixel copies and no diffs, because copy-on-write tiles do the work. Each step costs only the tiles it
  touched.
- **Memory accounting** (`ops/src/tiles.rs`): refcounts tile pointers across retained states and counts only tiles not shared with
  the current document. `trim()` evicts the oldest states over the byte budget.
- **Layer targeting.** Each state also restores the active and selected layers, as Photoshop does.
- **Coalescing.** A command may carry `"coalesce": "<key>"`; consecutive edits with the same key fold into one step. This is how
  a slider drag, a mask-density drag or a typing session becomes one undo step.

## 6. Engine, jobs and previews

- **`Session::edit(label, |doc, active| …)`** clones the `Arc` document, mutates the clone, swaps it in, records history, bumps the
  revision and sets damage.
- **Registry** (`engine/src/commands.rs`): `CommandSpec{id, label, menu, shortcut, params, enabled, run, journal}`.
  `disabled_reason_with` explains why a command is greyed (including "a job is running on this doc").
- **Jobs** (`engine/src/jobs.rs`):
  - long commands run on a worker over a snapshot, and the result is applied as **one undo step**;
  - progress is monotonic (`fetch_max` on the f32 bits); `stage(lo, hi, msg, …)` maps an algorithm's `Interrupt` onto a sub-range;
  - edits, undo and redo are disabled on that document while a job runs.
- **Adjustment preview** (`ui-egui/src/adjust_preview.rs`):
  - a destructive Image › Adjustments dialog previews as a **temporary clipped adjustment layer** with a fixed id, so only uniforms
    change per slider tick and the GPU keeps its resources;
  - OK runs the real command;
  - `unsupported()` lists exactly when the preview would differ from the result, and then falls back to running the real command
    on a proxy.

## 7. Colour (`crates/cms`)

- A dependency-free ICC v2/v4 engine with all four intents and black-point compensation, tested against `moxcms`.
- The display transform (document profile → monitor profile, plus proof colours and gamut warning) is **baked into a 33³ 3D LUT
  applied in the canvas shader's last pass**. Document pixels never change.
- For loom2 (8-bit sRGB by design, D18) only the LUT-in-the-last-pass idea matters, and only if ICC display ever becomes a goal.
