# 01 · PhotoCraft overview

## 1. What it is

PhotoCraft is a desktop and web raster editor that aims at Photoshop parity: the same menus (627 of 627 menu items are wired to
commands), the same layer model, the same blend arithmetic, and PSD as a first-class format. It is a **clean-room
reimplementation**. Algorithms come from published papers, and constants were fitted by treating Photoshop as a black box (for
example the PSD files' embedded merged composites). It contains no Adobe code.

| | |
| --- | --- |
| Repository | `F:\source\repos\photocraft`, `main` at `b37bff98` (2026-10-10) |
| Version | 0.6.0 (0.2.0 shipped 2026-10-05; about 96 PRs in two days at the time of reading) |
| Language | Rust edition 2024, MSRV 1.95; `unsafe_code = "forbid"` everywhere except the tablet crate |
| UI | egui / eframe, immediate mode (`crates/ui-egui`) |
| GPU | wgpu 30, WGSL compositor (`crates/gpu`); WebGPU on the web with a WebGL2 fallback |
| Web build | the whole app compiled to wasm: 18.8 MiB raw, 5.6 MiB brotli. **No JavaScript API.** |
| AI / ML | none. An `ml` crate is planned in `docs/architecture.md` but does not exist; all "smart" selection is classical. |
| Licence | **MIT OR Apache-2.0**; `NOTICE`: "Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors" |

## 2. Crate layers

The layering is enforced by `cargo xtask layers` (`xtask/src/layers.rs`): a crate may depend only on lower layers. Nothing below
L6 may touch egui, winit or rfd, and L0–L5 must pass `cargo check --target wasm32-unknown-unknown` (`cargo xtask wasm`).

| Layer | Crates | Role |
| --- | --- | --- |
| L0 | `geom`, `cms`, `color`, `raster`; standalone `psd`, `codecs`, `raw` | geometry, ICC, pixel formats and blend math, copy-on-write tiles |
| L1 | `doc` | pure-data document model |
| L2 | `ops`, `algo`, `paint`, `text`, `vector` | history, filters and selection algorithms, brushes, type, paths |
| L3 | `compose` (CPU oracle), `gpu` (wgpu), `format` (`.pcraft`) | compositing and the native format |
| L4 | `io`, `plugins` | file formats, wasm plug-ins (wasmi) |
| L5 | `engine` | `Session` plus the command registry |
| L6 | `ui-egui`, `automation` (MCP) | UI shell and agent access |

Every action is a JSON command (`crates/engine/src/*_cmds.rs`) dispatched by id from the UI, the CLI, a TCP control channel and
MCP. That is the same idea as loom2's command registry (D32), taken further: menus, buttons, scripts and agents share one id
space and one enablement rule.

## 3. Maturity, in its own words

PhotoCraft is unusually honest about itself (`docs/roadmap.md`, `docs/scorecard.md`):

- "Real Photoshop parity is still **well below 50 %**"; "a professional could switch" is put at 25–35 %. First users found broken
  basics that the scorecard counted as live.
- **PSD rendering fidelity:** 146/170 on its mixed corpus, 236/309 on psd-tools, 133/256 on Photoshop-authored files (pass =
  premultiplied max difference ≤ 2/255 against Photoshop's own merged image).
- **Performance:** 3 of 56 tracked scenarios are within budget; for example an opacity change takes 276 ms p50 against a 20 ms
  target, and a 150-layer nudge crashes the GPU compositor.
- **Exports are not checked in third-party editors** (scorecard FILE-216-4). Its adjustment-layer encodings are plausible, not
  proven.

**What is mature enough to rely on:** the `psd` crate's container layer (byte-stable on 478 of 479 public files), the codecs, the
atomic-write and file-format patterns, the blend formulas fitted against Photoshop, and the classical algorithms in `algo`, which
are deterministic, panic-free and tested against oracles. **What is not:** the GPU path, performance, text, effects parity and
smart filters.

## 4. Licence and the four ways to reuse it

MIT OR Apache-2.0 allows copying, porting and linking, including in the `open` variant (D26) and under EU terms (D17). Conditions:

- keep the copyright line and the licence text with any copied or ported code;
- don't use the ArtCraft name, wordmark or logos (`docs/brand/`, separately licensed);
- third-party assets bundled with PhotoCraft (Inter and JetBrains Mono under OFL, Lucide icons under ISC, the SCOWL word list) carry
  their own licences (`NOTICE`, `ATTRIBUTION.md`).

loom2 has no third-party notices file yet. Any proposal that ports code adds `THIRD_PARTY_NOTICES.md` at the root with a PhotoCraft
row, plus a header comment in each ported file naming the source path and commit:

```python
# Ported from PhotoCraft crates/algo/src/poisson.rs @ b37bff98
# Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors. MIT OR Apache-2.0.
```

The four adoption modes used in 06:

| Mode | What it means | When it fits | Cost |
| --- | --- | --- | --- |
| **Port** | rewrite the algorithm in numpy (orchestrator) or TypeScript/WGSL (editor), following the Rust structure so its tests can serve as oracles | most algorithms: they are short, use flat buffers and have no dependencies | hours to days; no stack change |
| **WASM crate** | build `photocraft-algo` (or `psd`) for `wasm32-unknown-unknown` behind a small wasm-bindgen wrapper, run it in a Web Worker | kernels that must react per pointer move and are hard to port (graph cut, live-wire) | adds a Rust → wasm build to the frontend; this machine has cargo 1.96 but no wasm32 target installed |
| **PyO3 crate** | a `maturin` abi3 wheel wrapping `photocraft-algo` for the orchestrator | heavy CPU kernels that are too slow in numpy (PatchMatch completion, banded graph cut) | adds a Rust wheel to the orchestrator build and CI; the Tauri shell already needs a Rust toolchain, so the toolchain exists |
| **Idea** | no code; adopt the pattern or contract | UI behaviour (egui code can't move to React), test practice, file-format rules | design time only |

Adding a crate is a stack change. Under the house rules it is a decision recorded in 13 *before* the work, with a rig measurement.

## 5. Strengths and weaknesses, from loom2's point of view

**Strengths worth borrowing:**
- blend arithmetic and group/clip/adjustment semantics fitted to Photoshop, with a free oracle (PSD merged images) and ratcheting
  pass floors in CI;
- a large set of correct, deterministic classical algorithms (Poisson, PatchMatch, guided-filter matting, graph cuts, EDT, ARAP)
  written against flat buffers;
- a brush engine with Photoshop's opacity/flow semantics and good mouse smoothing;
- explicit UI contracts (context-menu dispatch rules, coalesced drags, commit/cancel buttons for modal operations) that suit a
  mouse-first editor;
- engineering habits that suit loom2's tenets: "never invent a number" performance budgets, a settings-that-do-nothing audit, a
  whole-registry fuzz test, atomic writes with a Windows rename retry.

**Weaknesses to avoid copying:**
- performance budgets mostly unmet, and a GPU path that still falls back to the CPU for many features;
- scope far beyond a storyboard tool (CMYK, Lab, layer styles, smart objects, 17 UI languages);
- no AI: its "smart" tools are classical, which for loom2 makes them complements to BiRefNet and SAM 3, not replacements;
- immature parts (text, effects, smart filters) that churn daily.
