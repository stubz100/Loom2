# Third-party notices

Code in this repository that was ported from, or closely follows, third-party source. Each ported file carries a header comment
naming the source path and commit. Dependencies installed by package managers (npm, uv) carry their own licences and are not
listed here; model weights are governed by the licence register in `.docs/proto01/04-model-strategy.md` (D17).

## PhotoCraft

- Source: PhotoCraft (`https://github.com/storytold/photocraft`), commit `b37bff98` (2026-10-10)
- Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors
- Licence: MIT OR Apache-2.0, at your option (used here under the MIT licence, reproduced below). The ArtCraft name, wordmark and
  logos are not covered and are not used.
- Study: `.docs/photocraft/`

| loom2 file | Ported from | Decision |
| --- | --- | --- |
| `orchestrator/loom2/compose.py` (blend formulas, clipping groups, pass-through mixing, adjustment blend) | `crates/color/src/blend.rs`, `crates/compose/src/psblend.rs`, `crates/compose/src/lib.rs` | D39 |
| `frontend/src/suites/edit/blendModes.ts` (blend formulas) | `crates/color/src/blend.rs`, `crates/compose/src/psblend.rs` | D39 |
| `orchestrator/loom2/compose.py` `_exposure`, `frontend/src/suites/edit/adjustFilters.ts` (Exposure in linear light) | `crates/compose/src/adjust.rs` | D40 |
| `orchestrator/tests/psd_oracle.py` (method: merged-image oracle, 2/255, ratcheting floor) | `crates/io/tests/corpus.rs` | D40 |
| `frontend/src/suites/edit/psdExport.ts` `fixLevelsBlocks` (the Levels block layout) | `crates/io/src/adjust_map.rs` | D41 |
| `frontend/src/suites/edit/selectionOps.ts` (EDT, expand / contract / border / smooth / feather, wand rules in `EditorCanvas.tsx`) | `crates/algo/src/selection.rs`, `selection/distance.rs`, `selection_blur.rs` | D44 |
| `orchestrator/loom2/maskops.py` (bounded EDT, expand / contract) | `crates/algo/src/selection.rs`, `selection/distance.rs` | D44 |
| `orchestrator/loom2/matting.py` (guided filter, smart radius, refine order) | `crates/algo/src/matting.rs` | D45 |
| `orchestrator/loom2/poisson.py` (membrane solve, seamless clone) | `crates/algo/src/poisson.rs` | D47 |
| `orchestrator/loom2/tone.py` (Lab statistics, match colour) | `crates/algo/src/tone.rs` | D48 |
| `orchestrator/loom2/compose.py` `_color_to_alpha`, `frontend/src/suites/edit/adjustFilters.ts` (colour to alpha) | `crates/algo/src/color_to_alpha.rs` | D49 |

The psd-tools test files (`bench/corpus/psd-tools/`, fetched, never committed) are MIT, Copyright (c) 2019 Kota Yamaguchi;
the corpus pins were taken from PhotoCraft's `xtask/psd-tools-corpus.sha256`.

```
MIT License

Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
