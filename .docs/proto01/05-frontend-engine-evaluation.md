# 05 · Frontend engine evaluation — shell, canvas engine, video, data transfer

Research date 2026-10-04 (web sources listed at the end). Question answered: what loom2's frontend should
be built on so that (a) an image catalogue of thousands of PNGs, (b) a Photoshop-like layered inpaint /
refine editor and (c) an image-to-video suite with frame-accurate scrubbing are all fast and pleasant on
Windows 11 with a Python diffusion backend.

## 1. Criteria

| # | Criterion | Why it matters for loom2 |
| --- | --- | --- |
| C1 | GPU-accelerated 2D compositing (blend modes, masks, filters) at 2K–8K | layers × 8K images are hundreds of MB of pixels; CPU compositing cannot hit 60 fps |
| C2 | Large-image tiling + partial uploads | WebGPU's default `maxTextureDimension2D` is 8192; one 8K RGBA8 surface is 256 MB |
| C3 | Brush latency with pen pressure/tilt | the whole point of the inpaint suite is painting masks comfortably |
| C4 | Undo / history for raster edits | Photoshop-like expectation |
| C5 | PSD / ORA import-export | hand-off to Photoshop/Krita |
| C6 | Frame-accurate video decode/scrub | start/end frame picking, frame extraction for the i2v suite |
| C7 | Big-buffer exchange with Python (50–200 MB images, masks, latents) | every generation round-trips pixels |
| C8 | Developer velocity with an AI coding assistant | one developer, many suites |
| C9 | Windows packaging and GPU-driver robustness on AMD | the only target today |

## 2. Shell: Tauri 2 vs Electron vs native

| | Tauri 2 (WebView2) | Electron | PySide6 / Qt native | Rust GUI (egui / iced / Slint) |
| --- | --- | --- | --- | --- |
| Engine on this rig | Evergreen WebView2 = Edge 154 → WebGPU (D3D12), WebCodecs, OffscreenCanvas all present | Bundled Chromium 150 (Electron 43) with WebGPU HW-accelerated | QRhiWidget (D3D12/Vulkan) inside a widget tree | wgpu viewport trivial (egui) |
| Bundle / idle RAM | ~3–10 MB / ~40–50 MB | ~85–200 MB / ~120–170 MB | ~100+ MB with Qt + torch | 3–5 MB |
| Big-buffer IPC | `invoke` takes/returns `ArrayBuffer`, `Channel<ArrayBuffer>` streams Rust→JS, **but ~200 ms per 10 MB on Windows WebView2** (vs 5 ms on macOS); events are JSON-only; custom-protocol responses cannot chunk-stream | `MessagePort` + transferables ≈ 3–5 ms/MB; utility process | in-process numpy → zero-copy | in-process |
| Large files to `<img>` / `<video>` | `asset://` streams with Range (multi-range fixed in #15838) | `file://` or `protocol.handle` streams | n/a | n/a |
| Pen input | Chromium PointerEvents: pressure/tilt/twist, `pointerrawupdate`, `getCoalescedEvents`, `getPredictedEvents`, `desynchronized` canvases, Delegated Ink Trails | same Chromium stack | QTabletEvent (WinTab / Ink) | winit pen support uneven |
| Python backend | sidecar (what loom did) or PyTauri in-process (PyO3, 1.4k★) | spawn + loopback | same process | spawn + loopback |
| Velocity (C8) | React/TS ecosystem, hot reload | same | Widgets/QML slower; two languages in one process with torch | docking/trees/text/a11y all expensive |
| Verdict | **primary** | **drop-in fallback** | only if measured brush latency on the web stack fails | no |

Key finding: **the Tauri problem on Windows is IPC throughput, not rendering.** loom already moved images over
loopback HTTP from the Python process, which sidesteps IPC entirely. The Graphite editor abandoned its
Tauri build for a CEF + native-wgpu hybrid, which is a warning against mixing a webview UI with a native GPU
viewport, not against web rendering itself.

Decision: **Tauri 2 shell, frontend kept shell-agnostic** (no `@tauri-apps/api` imports inside canvas or
suite code; a thin `shell/` adapter owns dialogs, window state and sidecar status) so that switching to
Electron is a one-week job if WebView2 or AMD driver issues bite.

## 3. Canvas / rendering engine for the layered editor

| Library | Status (2026-10) | GPU | Fit |
| --- | --- | --- | --- |
| **PixiJS v8** | 48k★ MIT, v8.22 (2026-10-01) added storage/3D textures, sRGB views | WebGPU + WebGL2 with auto-fallback | **Chosen.** `RenderTexture` per layer tile, inherited blend modes, 20+ Photoshop blend modes via `advanced-blend-modes`, alpha/sprite masks, filter chains, custom shaders. Powers Gradio's ImageEditor. |
| Konva | 14.8k★, 10.7 | Canvas2D | InvokeAI's choice; a Konva "layer" is a full-stage canvas (~41 MB at 1080p HiDPI, warns above 5). Wrong primitive for Photoshop layers. |
| Fabric.js | 31k★, 7.4 | Canvas2D | vector/object editor; its own README points to PixiJS for raster. |
| tldraw / Excalidraw | 50k★ / 131k★ | DOM/SVG, Canvas2D | infinite vector canvases; tldraw needs a paid licence in production. |
| Polotno / Pintura / Filerobot / miniPaint | commercial / jQuery-era | Canvas2D | crop-filter editors, no non-destructive masks or 8K pens. |
| Three.js / OGL / raw WebGPU | — | WebGL2 / WebGPU | full control; the fallback if PixiJS abstractions fight the compositor. |
| Rust-WASM: image-rs, photon-rs, Vello 0.11, wgpu | active | WASM / WebGPU | good for **pixel kernels** off the main thread (16-bit filters, ORA/PSD codec, flood fill); Vello is vector-centric. |

### 3a. Existing AI-editor canvases to learn from

- **ComfyUI-InpaintCanvas** (GPL-3, Canvas2D, 28★, 2026-09): the exact feature list loom2 wants — Krita-style
  layer stack (reorder, merge, lock, alpha-lock, solo, blend modes), layer + transparency masks, selection
  (rect/ellipse/lasso/polygon/magic wand/SAM2/text), brush/eraser/clone/heal/smudge, non-destructive filter
  layers (curves, levels, LUT), warp, PSD + ORA export, pen pressure, result stitched back as a new layer with
  colour matching. Use as the **feature and UX reference**; GPL and Canvas2D rule out embedding.
- **ComfyUI-FastMask** (MIT): dirty-rect rAF loop that sleeps when idle, ≤2048 px preview-resolution painting
  with full-res export, lazy 256² tile snapshots for 40-step undo, CSS-transform zoom/pan. **Lift this
  brush/undo skeleton.**
- **InvokeAI unified canvas** (Apache-2.0, React + Konva, 6.14): entity/adapter split (`RasterLayer`,
  `ControlLayer`, `RegionalGuidance`, `InpaintMask`), server-side virtual flattening before generation,
  drop-zone UX. Copy the **document model**, not the renderer.
- **Krita + krita-ai-diffusion** (GPL-3, 10.7k★): the gold standard when you do not own the paint UI. Its
  transport (binary PNG over WebSocket with an 8-byte header; HTTP cache endpoint "typically faster for large
  images") confirms the loopback-HTTP conclusion in §5.
- **ComfyUI mask editor**: mask/paint/base layers, GPU brush, undo — a minimal bar to exceed.
- **libmypaint** (ISC, C): the one reusable brush *engine* (dab model, pressure curves); port the dab model to
  TS/WASM rather than bind it.
- **Graphite** (Rust/WASM): raster still experimental in 2026; not embeddable.

Verdict: nothing MIT-licensed, GPU-accelerated and layer-mask-capable exists to embed. **loom2 writes its own
compositor on PixiJS v8**, borrowing the document model from InvokeAI, the brush/undo skeleton from FastMask
and the feature list from InpaintCanvas. Budget 4–8 weeks before it feels like Photoshop.

### 3b. Compositor design constraints (from the research)

- Tiles: raster layers are grids of **2048² RenderTexture tiles** (stay under the 8192 default limit; request
  16384 as an optional limit). Krita uses 64² data tiles / 256² GL textures with a 16 px border.
- Memory: ten 8K layers as full textures = 2.5 GB; tiles + culling + evicting far tiles to CPU/IndexedDB keep
  this bounded. Live painting happens on a ≤2K preview surface and is committed to tiles at full res.
- Blend modes: native PixiJS modes are free; the Photoshop "advanced" set costs one render pass each —
  acceptable per layer, not per brush dab.
- Masks: single-channel textures applied in a custom filter; paint masks, rasterised lasso/polygon, and
  SAM-derived masks from the backend all land in the same representation.
- Adjustment layers: PixiJS/pixi-filters shaders for live preview; the **exact 16-bit version is applied in
  Python on commit/export**, so preview and master can differ slightly by design (documented).
- Brush: dab-based engine in a Worker on an OffscreenCanvas (2D or WebGL2), driven by `pointerrawupdate` +
  coalesced + predicted events, main canvas `desynchronized: true`, Delegated Ink Trail for the last segment.
- History: command log + 256² dirty-tile snapshots; document metadata via an immutable store with undo.
- Secure context: Tauri's default `http://tauri.localhost` is a secure context, so `navigator.gpu` works;
  COOP/COEP via `app.security.headers` enables `SharedArrayBuffer` for worker ↔ main tile sharing.

## 4. Video playback and frame accuracy

- `HTMLVideoElement` cannot guarantee frame-accurate seeks; `requestVideoFrameCallback` exposes `mediaTime`
  / `presentedFrames` for stepping and playback sync.
- **WebCodecs via Mediabunny** (7.2k★, MPL-2.0): demux + `VideoDecoder`; `CanvasSink.getCanvas(ts)` with a
  pooled ring buffer for scrubbing, `samplesAtTimestamps()` to avoid re-decoding, MP4/MOV/WebM/MKV. Chosen
  for the i2v suite's scrubber, stepping and frame extraction.
- Alternatives: WebAV (MIT, editor SDK), mp4box.js (serial only), ffmpeg.wasm (slow universal fallback).
- Backend: **TorchCodec** `seek_mode="exact"` (CPU decode on AMD) for canonical frame pulls; PyAV only seeks to
  keyframes. PNG/EXR sequence masters are transcoded by the backend into an MP4/WebM proxy that the UI scrubs;
  originals stay for extraction. This matches loom's R161 (lossless master + proxy).

## 5. Backend ↔ frontend big-buffer transfer

| Path | Measured / expected | Use for |
| --- | --- | --- |
| **Loopback HTTP from the Python sidecar** (`fetch` → `ArrayBuffer` → `writeTexture`) | uvicorn + httptools/uvloop streams ≈ 1.5 GB/s on 128 MB–1 GB bodies; a 200 MB float16 latent ≈ 0.1–0.3 s dominated by Python copies | **all pixels, masks, latents** as raw octet-stream / `.npy`, with `Range` for tiles and `Cache-Control` for thumbnails; never base64 (+33 % and a decode pass) |
| WebSocket binary | ~20–30k msg/s at 1 KB in Python | progress events, previews, small masks; Acly's header + PNG framing as the template |
| Tauri IPC (`invoke` with `ArrayBuffer`) | ≈ 20 ms/MB on Windows | metadata, commands, tiny masks only |
| Electron MessagePort | 3–5 ms/MB | only if the shell is switched |
| `SharedArrayBuffer` | zero-copy inside the webview with COOP/COEP | worker ↔ main brush tiles |
| `multiprocessing.shared_memory` / `np.memmap` | zero-copy between Python processes | decode/thumbnail workers → API process |
| Arrow IPC | zero-copy tables | catalogue metadata and batch result tables, not images |
| Thumbnails | pyvips ≈ 10× Pillow for batch | pre-generated WebP thumbs + SQLite index of PNG `tEXt` metadata so the grid never touches a 20 MB PNG |

Rule: **pixels never cross the shell's IPC.** They go Python → loopback HTTP → GPU texture.

## 6. File formats

- **ORA (OpenRaster)** = project format: zip of PNGs + `stack.xml`, native to Krita/GIMP/MyPaint, 16-bit PNG
  per layer, masks as grey PNGs; Python `pyora` or an own writer.
- **PSD** = export (and import): `ag-psd` (724★) reads and writes groups, blend modes, opacity, clipping,
  basic masks, effects — **8-bit only, no PSB, no 16-bit**; `psd-tools` in Python for import/compose.

## 7. Catalogue grid

**TanStack Virtual** (7.1k★ MIT, headless, grid + dynamic sizes, 10–15 kB) for the virtualised grid;
Masonic if a masonry layout is wanted. Selection / keep-reject state lives in the backend's SQLite catalogue,
not in component state (loom lost masks and selections that lived only in session state).

## 8. Recommendation

**#1 (chosen): Tauri 2 + React/TS + PixiJS v8 tiled compositor + Python FastAPI sidecar over loopback HTTP.**

- Shell: Tauri 2, Evergreen WebView2 (optionally a fixed-version runtime for determinism), COOP/COEP headers,
  IPC only for commands and metadata, frontend code shell-agnostic.
- Backend transport: FastAPI/uvicorn (httptools + uvloop); raw octet-stream with Range for pixels; WebSocket
  for events/progress/preview; shared memory between Python worker processes.
- Editor: PixiJS v8 (`preference: 'webgpu'`, WebGL2 fallback, a "force WebGL2" setting); 2048² tiles; dab
  brush engine in a Worker at ≤2K preview resolution committed at full res; 256² dirty-tile undo; masks as
  single-channel textures; adjustment layers previewed in shaders and committed exactly in Python; ORA
  project format, PSD export via ag-psd; "AI inpaint" = selection → backend → new raster layer with mask.
- Catalogue: TanStack Virtual + pyvips WebP thumbnails + SQLite metadata + Arrow for large tables.
- Video: Mediabunny `CanvasSink` scrubbing, `requestVideoFrameCallback` sync, TorchCodec exact seeks in the
  backend, PNG-sequence masters with MP4 proxies.

**#2 (fallback): Electron with the identical frontend.** Known-good Chromium, 3–5 ms/MB MessagePort, stream
protocol handlers; costs +80–180 MB bundle and +100 MB RAM. Reachable in about a week if the frontend stays
shell-agnostic.

**#3 (only if brush latency fails the bar): PySide6 + QRhiWidget, backend in-process.** Zero-copy numpy ↔ GPU
and QTabletEvent, but a hand-written D3D12/Vulkan tile compositor, slower UI velocity and painful packaging.

**Hedge for suite (b):** if the compositor becomes the schedule sink, ship (a) and (c) and let Krita +
krita-ai-diffusion drive loom2's backend through a thin ComfyUI-compatible adapter, the way Acly's
tooling-nodes do. It is the only path where "Photoshop-like" is free.

## 9. Risks and the spikes that retire them

| Risk | Spike (before suite-b implementation starts) | Pass bar |
| --- | --- | --- |
| WebView2 WebGPU on AMD RDNA4 drivers | PixiJS v8 WebGPU hello-compositor in Tauri 2 on this rig; toggle WebGL2 | 60 fps compositing 6 × 4K layers with 3 advanced blend modes on both backends — **PASS 2026-10-05**: 3.0 ms median / 4.1 ms p95 per composite (WebGPU, offscreen target, inside WebView2), WebGL2 ≤ 1 ms; display-limited to 30 fps on the author's 29 Hz monitor |
| Brush latency | FastMask-style worker brush with `pointerrawupdate` + predicted events, measured with a **mouse** (no pen hardware yet, D19); Delegated Ink and pressure paths implemented but untested until a tablet exists | event→commit latency at the rAF floor (median ≤ 1.5 frames, p95 ≤ 2) at 2K preview, no dropped dabs at fast mouse strokes (reworded 2026-10-05: the old "≤ 1 frame" was below the theoretical minimum of a rAF-driven renderer) |
| Loopback throughput | serve a 200 MB float16 latent and an 8K PNG from FastAPI; upload a 64 MB mask | ≥ 500 MB/s end-to-end into a GPU texture — **PASS 2026-10-05**: 782 MiB/s (Edge) / 695 MiB/s (WebView2) for 8K raw RGBA → WebGPU texture; 1.0–1.3 GiB/s single fetch, ≈ 2 GiB/s with 4 parallel ranges; needs 4 MiB response chunks (64 KiB gave 329–422 MiB/s) |
| VRAM blow-up | 10 × 8K layers with tiling + eviction | < 3 GB GPU memory, no stutter on pan/zoom |
| PSD fidelity | ORA → PSD via ag-psd → Photoshop/Krita round-trip | layers, masks, blend modes, opacity preserved (8-bit) |
| Frame-accurate scrub | Mediabunny `CanvasSink` on a 121-frame 24 fps MP4 | every frame reachable, step time < 50 ms — **PASS 2026-10-05**: 0 wrong frames (pixel-coded) in 3 × 222 seeks; GOP 24 random 17 ms, **GOP 6 ≈ 10 ms**, intra 7 ms, in Edge and WebView2 |

## Sources

WebView2/WebGPU: web.dev/blog/webgpu-supported-major-browsers · learn.microsoft.com/…/release-notes/153 ·
github.com/MicrosoftEdge/WebView2Feedback/discussions/4138 · MDN GPUSupportedLimits
Tauri: v2.tauri.app/reference/javascript/api/namespacecore · github.com/orgs/tauri-apps/discussions/11915 ·
github.com/tauri-apps/tauri/issues/13405 · discussions/5690 · v2.tauri.app/reference/config ·
github.com/pytauri/pytauri
Electron: github.com/ZacWalk/electron-bench
Canvas: github.com/pixijs/pixijs/releases · pixijs.com/8.x/guides/components/filters ·
konvajs.org/docs/performance/All_Performance_Tips.html · github.com/tldraw/tldraw/blob/main/LICENSE.md ·
github.com/linebender/vello
AI canvases: github.com/invoke-ai/InvokeAI · github.com/Acly/krita-ai-diffusion ·
github.com/Acly/comfyui-tooling-nodes · github.com/DenRakEiw/ComfyUI-InpaintCanvas ·
github.com/zaum/ComfyUI-FastMask · github.com/Azornes/Comfyui-LayerForge · docs.comfy.org/interface/maskeditor ·
github.com/GraphiteEditor/Graphite · lwn.net/Articles/1051242 · github.com/mypaint/libmypaint ·
community.kde.org/Krita/Tile_Data_Format
Native: doc.qt.io/qtforpython-6/PySide6/QtWidgets/QRhiWidget.html · avaloniaui.net/blog/vello-poc ·
github.com/emilk/egui · github.com/iced-rs/iced
Pen: w3.org/TR/pointerevents3 · github.com/MicrosoftEdge/MSEdgeExplainers/…/WebInkEnhancement
Video: web.dev/articles/requestvideoframecallback-rvfc · github.com/Vanilagy/mediabunny ·
mediabunny.dev/guide/media-sinks · meta-pytorch.org/torchcodec
Transfer: github.com/fedirz/fastapi-file-upload-benchmark · github.com/Kludex/uvicorn/issues/443 ·
arrow.apache.org/docs/python/ipc.html
Formats/grid: github.com/Agamnentzar/ag-psd · openraster.org · github.com/TanStack/virtual
