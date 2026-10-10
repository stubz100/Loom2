# 05 · Formats, automation and engineering practice

## 1. The `psd` crate (`crates/psd`, about 13.8k lines)

A standalone PSD/PSB reader and writer. It has no workspace dependencies (only `thiserror` and pure-Rust `flate2`) and is checked
for wasm32. It does not composite: "the caller supplies the merged composite".

- **Reading:**
  - an unmodified file writes back **byte for byte**: channel data keeps its encoding and unknown blocks stay raw;
  - lazy decoding;
  - `layer_tree()` tolerates malformed nesting;
  - depths 1/8/16/32, all colour modes, PSB.
- **Writing** (`builder.rs`): `PsdBuilder::new(w,h).depth(8|16).icc_profile(…).resolution(…)`, then `push_layer(LayerSpec)`,
  `begin_group` / `end_group` and `composite(…)`.
  - `LayerSpec` carries blend (27 modes + pass-through), opacity, `fill_opacity`, visible, clipping, an 8-bit mask, and
    **`extra_blocks` appended verbatim**, which is how adjustment layers are attached.
  - `GroupSpec` has no mask or extra blocks.
- **Adjustment encoders** live one level up, in `crates/io/src/adjust_map.rs` (1,160 lines, 16 keys: `levl curv hue2 brit nvrt thrs
  post expA vibA blnc mixr grdm phfl selc blwh clrL`). `write(adj)` returns ready-to-attach blocks.
  - **Caveat:** PhotoCraft has not validated its exports in third-party editors, so treat these encodings as plausible, not proven.
- **Tests:**
  - synthetic files for every depth × mode × compression;
  - truncation at every offset must return `Err`;
  - property tests must never panic;
  - cargo-fuzz targets (CI runs them only on manual dispatch);
  - the 170 + 309 corpus files must parse and rewrite byte-exactly.

**loom2 does not need it for adjustment layers.** loom2's PSD export (`psdExport.ts`) uses ag-psd 31.0.2, and that version
already models adjustment layers in its `Layer.adjustment` field: `brightness/contrast`, `levels`, `curves`, `exposure`,
`hue/saturation`, `color balance`, `black & white`, `invert` and more. That covers all eight of loom2's adjustment types (**verified**
in `node_modules/ag-psd/dist/psd.d.ts`). loom2 skips them by choice ("no raster of their own"), not because the library can't write
them.

The crate stays relevant for two later needs:
- 16-bit PSD with ICC, if loom2 ever leaves 8-bit sRGB;
- a lossless PSD *import* that round-trips unknown data.

## 2. `.pcraft` and atomic writes (`crates/format`)

**Layout:** a ZIP of stored entries, or a directory with the same layout:
- `manifest.json`, a versioned document tree;
- `tiles/<blake3>.zst`, content-addressed 256² tiles;
- `blobs/<blake3>.zst`;
- an optional thumbnail and preview.

**Ideas that apply to loom2's ORA and records:**
- **A separate on-disk model.** `manifest.rs` is a serde model kept apart from the in-memory document, built so that it **fails to
  compile when a document struct gains a field**. Nothing is silently dropped; new fields get `#[serde(default)]`.
- **Migrations as a list of steps.** `migrate.rs` holds `STEPS: &[fn(&mut Value)]`, each lifting raw JSON from n to n+1. A file that
  is too new returns `TooNew{found, supported}`.
- **Non-finite values are rejected** with a path-specific message (`finite.rs`).
- **Incremental saves.** A writer kept per open document compresses only the tiles that changed.
- **Crash recovery.** `Autosaver` and `RecoveryStore` use per-launch keys. An entry is removed only on save or close, so a second
  crash loses nothing. loom2's autosave overwrites the real ORA, and spec 10's sidecar and recovery offer do not exist.
- **Atomic writes with a Windows rename retry** (`atomic.rs`):
  - temp file in the same directory, `sync_all`, rename;
  - **on Windows the rename is retried 7× from 10 ms on `PermissionDenied`**, because antivirus and the search indexer briefly
    lock files;
  - failure-injection tests: mid-write `StorageFull`, rename failure, read-only directory, locked target.
  - loom2's `fsio.py` calls `os.replace` once with no retry (**verified**).

**Codecs** (`crates/codecs`):
- `caps(format)` and `fidelity_warnings(img, fmt)` say exactly what an export will lose ("16-bit will be reduced to 8-bit"), using
  the same encode plan as the encoder itself.
- That is a T8-style "display == reality" contract for exports.

**OpenRaster:** not supported anywhere in PhotoCraft.

## 3. Automation

- **Command registry** (02 §6), with about 627 menu items wired. UI, CLI, TCP control and MCP all dispatch by id.
- **Control channel** (`docs/control-protocol.md`):
  - loopback only, authenticated by a 256-bit token read from a file (not argv);
  - methods: `engine.execute`, `ui.inspect`, `ui.set` (unknown fields rejected before anything changes), `ui.menu.invoke`,
    `ui.dialog.open/set/confirm`, `ui.pointer` (with simulated pressure and tilt), `ui.screenshot`, `ui.gpu.simulateLoss`;
  - **every ambient-path command is refused** unless it lies under the configured read and write roots (cap-std handles).
- **MCP** (`crates/automation`, rmcp, stdio):
  - tools for documents, commands and jobs;
  - every tool carries a title and all four annotation hints; schemas set `additionalProperties: false`;
  - progress is throttled to ≤ 10/s, and cancellation is supported;
  - `tests/agent_tasks.rs` runs 10 realistic tasks purely over MCP and verifies through `doc_inspect` and pixels.
- **Headless screenshots:** `cargo run -p photocraft-ui-egui --example snapshot -- --script '[["ui.set",…]]'` renders the real UI
  offscreen. AGENTS.md rule 6: verify UI changes by looking at the PNG.

For loom2 this is context, not a proposal. loom2's API is already a typed HTTP contract (D38), and an MCP surface would be a
separate decision.

## 4. Engineering practices

| Practice | PhotoCraft | Fit for loom2 |
| --- | --- | --- |
| **Pinned, hash-verified corpora, never committed** | `xtask/src/corpus_pins.rs`, `*.sha256`; opt-in locally, but a missing corpus *fails* when opted in; CI always runs them, cached by the pin hash | **Adopt** for a `compose.py` Photoshop oracle (PC4): psd-tools test files (MIT), fetched by a script, behind a pytest marker |
| **Ratcheting floors** | `Source{pass_floor, roundtrip_floor}`, "raise, never lower" | **Adopt** with PC4 |
| **Performance budgets that never invent a number** | `perf/budgets.toml`: `budget_ms`, `enforce` set only once met, `not_measurable` reasons; `baseline.json` records the machine class; regressions over 15 % fail only on the same machine class | Fits house rule 1. A light version: rig timings and VRAM peaks per model in TOML, with a generated table |
| **Settings-that-do-nothing audit** | `xtask/src/scorecard.rs::prefs_audit`: a static scan that every preference field is read somewhere (46 of 146 unread at the time of reading) | **Adopt** (PC25): T8 says every displayed default must be what the worker runs |
| **`panic_hunt`** | `engine/tests/panic_hunt.rs`, 57 lines: every command × 4 adversarial param sets, each on its own thread with a 4 s timeout, in the pre-merge gate | **Adopt** (PC26) over the D38 OpenAPI routes: junk bodies must give 4xx, never 500 or a hang |
| **Never-crash rules** | no unwrap/expect/panic outside tests; checked arithmetic; poison-tolerant locks; a last-resort catch around dispatch that keeps the document; every crash fix ships with a regression test | PC26 covers the Python analogue (no 500s) |
| **GPU = CPU parity grid** | `gpu/tests/parity.rs`, seeded noise × every mode/structure, run twice with a small texture limit | **Adopt** (PC4) through `edit_headed_check.py`, since headless Edge can't present WebGPU |
| **Layering check** | `cargo xtask layers` | Optional: import-linter / dependency-cruiser, or an `agents_check.py` extension |
| **Bundle size gate** | the web build fails above 24 MiB | Optional: a Vite bundle-size gate |
| **Agent conventions** | AGENTS.md read order, a "before you finish" checklist, a devlog for resuming crashed sessions | Already close to loom2's CLAUDE.md + journal (D35) |
