# PhotoCraft study — documentation index

A study of **PhotoCraft** (`F:\source\repos\photocraft`, `main` at `b37bff98`, 2026-10-10, v0.6.0), written 2026-10-10 to improve
loom2's **Edit suite**. PhotoCraft is a clean-room, Photoshop-class raster editor in pure Rust (egui UI, wgpu compositor), built by
the people behind ArtCraft. Unlike ArtCraft, it is **MIT OR Apache-2.0**: its code may be ported or linked, not just its ideas.

Method: four research passes read the source directly (engine and compositing; tools and algorithms; UI and UX; formats, automation
and engineering practice), and a fifth inventoried loom2's Edit suite at `1cdc6d2`. Claims about loom2 that drive a proposal were
re-checked in the code before being written down; they are marked **verified**. Nothing in the PhotoCraft checkout was modified,
and nothing in it was built.

## Reading order

| # | Document | What it covers |
| --- | --- | --- |
| 01 | [Overview](01-overview.md) | what PhotoCraft is, crate layers, maturity (its own honest parity numbers), **licence and the four ways to reuse it** |
| 02 | [Engine and compositing](02-engine-and-compositing.md) | document model, copy-on-write tiles, Photoshop compositing semantics, blend math, GPU = CPU parity, history, jobs, colour |
| 03 | [Tools and algorithms](03-tools-and-algorithms.md) | selection (wand, quick select, magnetic lasso, refine edge, EDT modify), retouch (Poisson, PatchMatch, healing), brush engine, transforms and warps, filters |
| 04 | [UI patterns](04-ui-patterns.md) | layout, toolbar and options bar, Layers and Properties, context-menu contract, dialogs and previews, twenty mouse-first patterns |
| 05 | [Formats and practices](05-formats-and-practices.md) | the `psd` crate, `.pcraft`, codecs, automation (control channel, MCP), test corpora, ratcheting floors, `panic_hunt`, prefs audit |
| 06 | [loom2 Edit comparison and proposals](06-loom2-edit-comparison.md) | loom2's Edit suite today (with verified bugs and spec ≠ code), side-by-side, proposals PC1–PC26 with adoption mode, effort, waves and delivery sketches |

## Five things to know first

1. **The licence allows reuse.** Keep the notice "Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors" and the MIT or
   Apache text; the ArtCraft brand assets in `docs/brand/` are excluded. MIT and Apache are fine under D17 and for the `open` variant.
2. **Its best material for loom2 is algorithms, not code to embed.** Most wins are small ports to numpy or TypeScript (Photoshop
   blend formulas, Poisson paste-back, refine edge, brush accumulation, smoothing, colour to alpha). Linking whole crates
   (WASM or PyO3) is worth it only for two kernels: PatchMatch fill and graph-cut quick select. Each of those needs a spike and a
   decision first.
3. **Reading it found real bugs in loom2's compositor** (verified, 06 §2):
   - Clipping uses the alpha of everything below, not the base layer's, so a clipped layer over an opaque background is not
     clipped at all.
   - A pass-through group with opacity below 100 % renders isolated.
   - Adjustment layers ignore their blend mode.
   - Soft Light, Vivid Light and Hard Mix follow W3C rather than Photoshop.
   - Editor and server agree with each other, so `cmpdiag` could not catch these. PSD export writes `clipping`, so Photoshop shows
     something different from loom2.
4. **PhotoCraft is young and says so.** Its own verdict is "well below 50 %" Photoshop parity, 3 of 56 performance scenarios
   within budget, and very high churn. Pin a commit for anything ported.
5. **The proposals favour what loom2 uniquely needs:** AI results that blend in seamlessly (Poisson paste-back, match colour,
   refine edge, content-aware pre-fill), VRAM-free selection while ComfyUI holds the card, and mouse-first interaction patterns
   that serve D32.

## Conventions

- Proposals in 06 are proposals. Decisions belong in [`../proto01/13-decision-log-and-open-questions.md`](../proto01/13-decision-log-and-open-questions.md).
- Proposal ids are **PC1–PC26** so they don't collide with the ArtCraft study's P1–P19 or the E-series spikes. Spikes here are
  **S1–S3**.
- PhotoCraft paths are relative to its repository root; loom2 paths are relative to this repository. Facts are dated to the commits
  above.
