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
