# frontend/src/suites/edit — notes for coding agents

Verified at ceb638d on 2026-10-10. Specs: `.docs/proto01/10-ui-suite-edit.md` (layout, tools, AI panel, acceptance),
`.docs/proto01/05-frontend-engine-evaluation.md` (why PixiJS v8). Decisions D3, D4, D5, D7, D22, D31 (compositing), D33, D39 (Photoshop compositing semantics), D40 (Photoshop oracle), D41 (PSD export), D43 (selection history), D44 (selection toolkit), D45 (Refine Edge), D46 (clipboard).

## Files

| File | Owns |
| --- | --- |
| `EditorCanvas.tsx` | the PixiJS `Application`: WebGPU preferred, WebGL2 fallback, render on demand, render-texture passes, overlays, pointer input, drop target |
| `editorStore.ts` | document stack, tools, selection, history, persistence against `/documents/*` (stack revision, 409 merge), AI runs and candidates, autosave |
| `layerPixels.ts` | `LayerPixels`: a 2D canvas per raster layer or mask (the CPU truth), its Pixi texture, 256² tile snapshots for undo, raw RGBA transfer |
| `blendModes.ts` | 24 blend modes (W3C formula, Photoshop's Soft / Vivid Light, Hard Mix, Burn / Dodge edges) as `BlendModeFilter` subclasses (GLSL + WGSL) with alternate `-b` names; `w3c-opaque` for clip-run bases; `BLEND_GL` / `BLEND_WGSL` (`w3_blendBy`) for the adjustment filters |
| `adjustFilters.ts` | adjustment and filter layers previewed as per-layer filters |
| `selectionOps.ts` | selection value (red × alpha), tile diffs for selection history, EDT, expand / contract / border / smooth / feather, combine by mode (D43, D44) |
| `transform.ts` | free-transform maths (corners, handles, hit tests, resample) |
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

## Renderer selection

`EditorCanvas.tsx` initialises Pixi with `preference: 'webgpu'`; with the `auto` preference a post-init probe (`rendersPixels`) checks that
the WebGPU renderer actually draws, and swaps to WebGL2 when it does not (D3 amendment). The strip badge forces either; `?renderer=` and
`&probe=0` deep-link it for checks.

## Checking changes

- Headless Edge **cannot present WebGPU**: use `scripts/edit_headed_check.py` (visible Edge over CDP, Vite on 1420) — modes `render`, `paint`,
  `tour`, `cmpdiag`, `grid` (D40: every mode × plain / masked / clipped / isolated / pass-through 50 %), `selection` (PE2), `psd`, `animate`, `perf`. `perf` budgets: 6×4K composite p95 ≤ 16.7 ms (measured 7.1 ms, M7).
- Rig acceptance for the AI verbs: `scripts/m5_acceptance.py`.
- `npm run build` must stay clean; `window.__loom2Editor` / `__loom2App` are exposed in dev builds for the checks.
