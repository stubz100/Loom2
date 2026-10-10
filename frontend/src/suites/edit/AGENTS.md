# frontend/src/suites/edit — notes for coding agents

Verified at ceb638d on 2026-10-10. Specs: `.docs/proto01/10-ui-suite-edit.md` (layout, tools, AI panel, acceptance),
`.docs/proto01/05-frontend-engine-evaluation.md` (why PixiJS v8). Decisions D3, D4, D5, D7, D22, D31 (compositing), D33, D39 (Photoshop compositing semantics), D40 (Photoshop oracle), D41 (PSD export), D43 (selection history), D44 (selection toolkit), D45 (Refine Edge), D46 (clipboard), D47–D49 (paste-back, match colour, colour to alpha), D50 / D51 (brush, smoothing), D52 (masks), D53 (partial uploads), D54 (mask mechanics from PhotoCraft), D55 (mouse-first kit), D56 (layers panel), D57 (properties, spline curves), D58 (free transform), D59 (Quick Selection, Magnetic Lasso).

## Files

| File | Owns |
| --- | --- |
| `EditorCanvas.tsx` | the PixiJS `Application`: WebGPU preferred, WebGL2 fallback, render on demand, render-texture passes, overlays, pointer input, drop target |
| `editorStore.ts` | document stack, tools, selection, history, persistence against `/documents/*` (stack revision, 409 merge), AI runs and candidates, autosave |
| `layerPixels.ts` | `LayerPixels`: a 2D canvas per raster layer or mask (the CPU truth), its Pixi texture, 256² tile snapshots for undo, raw RGBA transfer |
| `blendModes.ts` | 24 blend modes (W3C formula, Photoshop's Soft / Vivid Light, Hard Mix, Burn / Dodge edges) as `BlendModeFilter` subclasses (GLSL + WGSL) with alternate `-b` names; `w3c-opaque` for clip-run bases; `BLEND_GL` / `BLEND_WGSL` (`w3_blendBy`) for the adjustment filters |
| `adjustFilters.ts` | adjustment and filter layers previewed as per-layer filters |
| `brushEngine.ts` | D50 / D51: per-stroke coverage buffer recomposited from the undo snapshots (`LayerPixels.preStroke`), tip falloff, `PathWalker`, pulled-string `Smoother` |
| `maskDerived.ts` | D52: a mask as it renders (feather = three-box Gaussian, then density), cached per mask canvas and re-derived around a stroke's damaged rect only |
| `widgets.tsx` | D55: `ValueField` (type, scrub, ▾ pop-up slider; one gesture = one `onStart` / `onCommit`), `BlendSelect` (wheel steps, hover previews through `blendPreview`), `LatchButton` |
| `curves.ts` | D57: PhotoCraft's natural-spline curve LUT (4096 entries, flat ends, clamped) — the same code as `compose.spline_lut`; the shader table and the Curves editor use it |
| `propsEditors.tsx` | D57: Properties sections, the histogram of the layers below, Levels / Curves / Colour balance editors |
| `smartselect/` | D59: `pcwasm.wasm` (PhotoCraft's quick select + magnetic lasso, committed with `pcwasm.pin.json`), `worker.ts` (the module in a Worker, C ABI), `client.ts` (requests, image cache by key), `source.ts` (active layer or composite), `magnetic.ts` (the lasso's fastening / closing rules) |
| `selectionOps.ts` | selection value (red × alpha), tile diffs for selection history, EDT, expand / contract / border / smooth / feather, combine by mode (D43, D44) |
| `transform.ts` | D58: PhotoCraft's free transform — `Homography` (rect → quad, inverse), `warpRaster` (nearest / bilinear / Catmull-Rom on premultiplied pixels, area prefilter below 50 %), `warpGray` (masks, the selection, flattened onto their default), split / composite for selection lifts, `hitTest` / `applyDrag` for the box |
| `aiPanelStore.ts` | AI panel UI state (op, mode, prompt, candidates, encoder `teId`) |
| `psdExport.ts` | PSD export via ag-psd (lazy-loaded): adjustment layers, fill, clip, locks, pass-through (D41); `fixLevelsBlocks` repairs ag-psd's Levels block in place; checked by `edit_headed_check.py psd` with psd-tools |
| `editCommands.ts` / `EditSuite.tsx` | commands, tool table, panels, the AI tab |

## Invariants

1. **The preview is the truth the user paints against.** `orchestrator/loom2/compose.py` is the exact compositor; the GPU preview must match it
   (acceptance: p99 ≤ 3/255 on a stack of every mode, ≤ 1 per feature). `scripts/m4_acceptance.py` and the `/documents/{id}/compare`
   endpoint measure it; `scripts/m4_compositor_diag.py` and `edit_headed_check.py cmpdiag` debug it.
2. **Never use Pixi's built-in advanced blends, sprite masks or `cacheAsTexture` for layers.** A sprite mask plus an advanced blend gives
   the blend a transparent backdrop; `cacheAsTexture` applies alpha and blend per child. Masked layers and isolated groups render through
   their own RenderTextures; two adjacent layers with the same mode alternate between the `mode` and `mode-b` names so they never batch.
   A sprite mask is only ever applied inside a pass to a sprite without a blend filter (`withMask`, the clip run's alpha mask).
3. **Layers are 8-bit in the ORA** (Pillow writes no RGBA16); 16-bit is post-MVP.
4. **Pixels never cross Tauri IPC.** Layers move as raw RGBA over loopback HTTP (`PUT/GET /documents/{id}/layers/{lid}/pixels?kind=image|mask`,
   `X-Loom-Width/Height/Channels`), the selection as one byte per pixel (`PUT /documents/{id}/selection?w&h`).
5. **Stack writes carry the document revision.** A stale PUT returns 409; the store resyncs, merges server layers (AI results added while
   editing) and re-PUTs — never replace the server stack blindly (review C1 / C20).
6. **AI jobs read the saved document.** `runAi` saves first, uploads the selection, then posts `/documents/{id}/ai`; results come back as
   `document.changed {added, group}` and land as candidate layers in a per-batch "AI" group (the variant strip: `1–4` / Enter picks).
7. **Destroy what you create.** Rebuilding the scene destroys sprites and passes but keeps `LayerPixels` textures (they live in the store);
   unmount destroys the app (`app.destroy(true, {children: true})`, review C21).
8. **Clipping groups are passes, not a shader variant (D39).** `buildClipRun`: the base's content (pixels × mask) renders into a pass,
   is drawn `w3c-opaque` into a second pass with the clipped layers over it, that pass is masked by the base's alpha
   (`setMask({channel: 'alpha'})`) in a third, and the unit blends with the base's mode and opacity × fill. A pass-through group below
   100 % or masked renders a copy of its target's earlier content (`prefixOf`) into a pass, its children over that, and draws the
   result at opacity × mask. Moving or transforming a layer must `markPassesDirty()`: it may sit inside a pass.
9. **Selection changes go through `editSelection` (D43).** It diffs the selection before / after by tile and records presence, so undo
   restores "no selection" too. Tools build a document-sized shape and call `applySelectionShape(shape, mode, label, feather)`; read
   values with `selectionValues()` / `toRaw()` (red × alpha), never the red channel alone.
10. **`Ctrl+V` is not a registry key path (D46).** The key handler lets it through so the browser fires `paste` (which carries images
   from other apps without a permission prompt); `handleKeyFor` would `preventDefault` it. The Paste command keeps `Ctrl+V` as its
   displayed accelerator and its mouse path tries `navigator.clipboard.read()` before the editor's own clipboard.
11. **A mask renders through `derivedMask` (D52).** Anything that shows or bakes a mask (the scene's mask sprites, merge down, Apply mask)
   takes `derivedMask(raw, node.mask)`, never the raw canvas, so density and feather match `compose.derived_mask` (same box radii, same
   rounding). The tools paint the raw mask; `LayerPixels.version` / `takeDamage()` tell the cache what to re-derive, so every write to a
   mask must end in `refresh()` or `refreshRect()`. Outside its extent a mask reads `mask.default` (D54): `maskSprite` pads with a pass
   when the content reaches past the extent, `maskAlphaCanvas` does the same for baking.
12. **Mask target and colours (D54).** `editingMask` is app-wide; a store subscription clears it when the active layer has no mask and
   swaps `brush.color / background` with `otherColours` whenever the live target changes between pixels and a mask (or Quick Mask) —
   so tools just read `brush`; mask strokes paint `lumaOf(colour)`, never a fixed white / black. Persisted state keeps the image pair in
   `brush` and the mask pair in `maskColours`.
13. **Canvas gestures read `mods(e)`, not `e.shiftKey` (D55).** `mods` ORs the strip's latched ⇧ / Ctrl / Alt into the event; a new
   canvas modifier gesture must go through it so it stays reachable by mouse. The blend dropdown's hover preview is `blendPreview`
   (rendered, never recorded) — the scene renders `doc` with it applied.
14. **Layer commands act on `targetIds()` (D56).** The selection counts only while it holds the active layer; `targetIds()` returns it
   top-level only and in panel order (or just the active layer). Group, duplicate, merge, delete, visibility and lock use it; the panel's
   drag, eye sweep and footer drops call `moveNodesTo` / `deleteNodes` / `duplicateNodes` / `groupNodes`, one history step per gesture
   (stack-only entries with one coalesce key merge across layers). Layer rows must not select text (`user-select: none`): a text
   selection turns a row drag into a native drag and the pointer stream ends in `pointercancel`.
15. **A transform is a rect, a quad and a pivot (D58).** Never accumulate: drags compute from the quad at the drag's start, the
   preview is a `PerspectiveMesh` per moving raster over canvases captured at `beginTransform` (`transformPreview`), and apply
   (`bakeTransform`) resamples each target once from its current pixels — one history step with `swap` / `more` / `selSwap`.
16. **`smartselect/pcwasm.wasm` is a committed build artifact (D59).** Never edit or rebuild it casually: `scripts/build_pcwasm.py` rebuilds it
   from `frontend/wasm/pcwasm` against the PhotoCraft checkout beside this repository at the pinned commit and records the SHA-256 that CI checks. WebAssembly needs
   `'wasm-unsafe-eval'` in the Tauri CSP (`csp_check.py` probes the Worker under the production policy).

## Renderer selection

`EditorCanvas.tsx` initialises Pixi with `preference: 'webgpu'`; with the `auto` preference a post-init probe (`rendersPixels`) checks that
the WebGPU renderer actually draws, and swaps to WebGL2 when it does not (D3 amendment). The strip badge forces either; `?renderer=` and
`&probe=0` deep-link it for checks.

## Checking changes

- Headless Edge **cannot present WebGPU**: use `scripts/edit_headed_check.py` (visible Edge over CDP, Vite on 1420) — modes `render`, `paint`,
  `tour`, `cmpdiag`, `grid` (D40: every mode × plain / masked / clipped / isolated / pass-through 50 %), `brush` (PE4), `selection` (PE2), `psd`, `animate`, `perf`. `perf` budgets: 6×4K composite p95 ≤ 16.7 ms (measured 7.1 ms, M7).
- Rig acceptance for the AI verbs: `scripts/m5_acceptance.py`.
- `npm run build` must stay clean; `window.__loom2Editor` / `__loom2App` are exposed in dev builds for the checks.
