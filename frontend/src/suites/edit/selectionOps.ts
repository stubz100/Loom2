// Selection maths (D43, D44): one definition of the selection value, tile diffs for history, and the modify operations.
//
// The selection is a document-sized grey LayerPixels. Tools draw white with partial alpha onto it (anti-aliased marquee and lasso
// edges, subtract via destination-out) while feather / invert / load write opaque grey; the selected amount of a pixel is
// therefore red × alpha / 255, which reads both encodings correctly (a fully transparent pixel reads 0).
//
// Expand / contract / border use an exact Euclidean distance transform (Felzenszwalb & Huttenlocher 2012), so growth is round and
// fractional: expand(v, r) = max(v, clamp(r + 1 − d)), contract = 1 − expand(1 − v), border = expand − contract. Feather is a
// Gaussian with σ = r / 2 (Photoshop's feather radius), as three box passes. Ported from PhotoCraft crates/algo/src/selection.rs,
// selection/distance.rs and selection_blur.rs @ b37bff98; Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors,
// MIT OR Apache-2.0.
import { TILE, type LayerPixels, type TileSnapshot } from './layerPixels'

/** The selected amount (0–255) of every pixel. */
export function selectionValues(sel: LayerPixels): Uint8Array {
  const d = sel.ctx.getImageData(0, 0, sel.width, sel.height).data
  const out = new Uint8Array(sel.width * sel.height)
  for (let i = 0, j = 0; i < out.length; i++, j += 4) out[i] = d[j + 3] === 255 ? d[j] : Math.round((d[j] * d[j + 3]) / 255)
  return out
}

/** Write values (0–255) as opaque grey. */
export function writeSelection(sel: LayerPixels, v: Uint8Array): void {
  const img = sel.ctx.createImageData(sel.width, sel.height)
  const d = img.data
  for (let i = 0, j = 0; i < v.length; i++, j += 4) { d[j] = d[j + 1] = d[j + 2] = v[i]; d[j + 3] = 255 }
  sel.ctx.putImageData(img, 0, 0)
  sel.refresh(); sel.dirty = true
}

/** Tiles whose selected amount differs between `before` and `after` (null = no selection = all zero), as snapshots of the
 * `before` canvas content — what undo restores. */
export function changedTiles(w: number, h: number, before: Uint8Array | null, after: Uint8Array | null, beforeImg: ImageData | null): TileSnapshot[] {
  const out: TileSnapshot[] = []
  for (let ty = 0; ty * TILE < h; ty++) for (let tx = 0; tx * TILE < w; tx++) {
    const x0 = tx * TILE, y0 = ty * TILE, tw = Math.min(TILE, w - x0), th = Math.min(TILE, h - y0)
    let diff = false
    for (let y = y0; y < y0 + th && !diff; y++) for (let x = x0; x < x0 + tw; x++) {
      const i = y * w + x
      if ((before ? before[i] : 0) !== (after ? after[i] : 0)) { diff = true; break }
    }
    if (!diff) continue
    const data = new ImageData(tw, th)
    if (beforeImg) for (let y = 0; y < th; y++) data.data.set(beforeImg.data.subarray(((y0 + y) * w + x0) * 4, ((y0 + y) * w + x0 + tw) * 4), y * tw * 4)
    out.push({ x: x0, y: y0, data })
  }
  return out
}

// ---- distance transform -----------------------------------------------------------------------------------------
const INF = 1e20

/** 1-D squared distance transform of f (Felzenszwalb & Huttenlocher), in place into d. */
function dt1(f: Float64Array, n: number, d: Float64Array, v: Int32Array, z: Float64Array): void {
  let k = 0
  v[0] = 0; z[0] = -INF; z[1] = INF
  for (let q = 1; q < n; q++) {
    let s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k])
    while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]) }
    k++; v[k] = q; z[k] = s; z[k + 1] = INF
  }
  k = 0
  for (let q = 0; q < n; q++) { while (z[k + 1] < q) k++; const dq = q - v[k]; d[q] = dq * dq + f[v[k]] }
}

/** Euclidean distance from every pixel to the nearest pixel where `inside` is true (0 inside). */
export function edt(inside: Uint8Array, w: number, h: number): Float32Array {
  const n = Math.max(w, h)
  const f = new Float64Array(n), d = new Float64Array(n), z = new Float64Array(n + 1), v = new Int32Array(n)
  const grid = new Float64Array(w * h)
  for (let i = 0; i < w * h; i++) grid[i] = inside[i] ? 0 : INF
  for (let x = 0; x < w; x++) {                                         // columns
    for (let y = 0; y < h; y++) f[y] = grid[y * w + x]
    dt1(f, h, d, v, z)
    for (let y = 0; y < h; y++) grid[y * w + x] = d[y]
  }
  const out = new Float32Array(w * h)
  for (let y = 0; y < h; y++) {                                         // rows
    for (let x = 0; x < w; x++) f[x] = grid[y * w + x]
    dt1(f, w, d, v, z)
    for (let x = 0; x < w; x++) out[y * w + x] = Math.sqrt(d[x])
  }
  return out
}

// ---- modify -------------------------------------------------------------------------------------------------------
const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x)

/** Grow by r px: round and fractional (a selected pixel's distance is 0, so a 1-px dot grows into a disc of radius r). */
export function expand(v: Uint8Array, w: number, h: number, r: number): Uint8Array {
  if (r <= 0) return v.slice()
  const inside = new Uint8Array(v.length)
  for (let i = 0; i < v.length; i++) inside[i] = v[i] >= 128 ? 1 : 0
  const d = edt(inside, w, h)
  const out = new Uint8Array(v.length)
  for (let i = 0; i < v.length; i++) out[i] = Math.max(v[i], Math.round(clamp01(r + 1 - d[i]) * 255))
  return out
}

export function contract(v: Uint8Array, w: number, h: number, r: number): Uint8Array {
  const inv = new Uint8Array(v.length)
  for (let i = 0; i < v.length; i++) inv[i] = 255 - v[i]
  const g = expand(inv, w, h, r)
  for (let i = 0; i < g.length; i++) g[i] = 255 - g[i]
  return g
}

/** A band of width r centred on the selection edge. */
export function border(v: Uint8Array, w: number, h: number, r: number): Uint8Array {
  const half = r / 2
  const a = expand(v, w, h, half), b = contract(v, w, h, half)
  const out = new Uint8Array(v.length)
  for (let i = 0; i < v.length; i++) out[i] = Math.max(0, a[i] - b[i])
  return out
}

/** Box blur (radius r, edge-clamped) of a float plane, horizontal then vertical, cost independent of r. */
function boxBlur(src: Float32Array, w: number, h: number, r: number): Float32Array {
  if (r < 1) return src
  const tmp = new Float32Array(src.length), out = new Float32Array(src.length)
  const n = 2 * r + 1
  for (let y = 0; y < h; y++) {
    const row = y * w
    let acc = 0
    for (let k = -r; k <= r; k++) acc += src[row + Math.min(w - 1, Math.max(0, k))]
    for (let x = 0; x < w; x++) {
      tmp[row + x] = acc / n
      acc += src[row + Math.min(w - 1, x + r + 1)] - src[row + Math.max(0, x - r)]
    }
  }
  for (let x = 0; x < w; x++) {
    let acc = 0
    for (let k = -r; k <= r; k++) acc += tmp[Math.min(h - 1, Math.max(0, k)) * w + x]
    for (let y = 0; y < h; y++) {
      out[y * w + x] = acc / n
      acc += tmp[Math.min(h - 1, y + r + 1) * w + x] - tmp[Math.max(0, y - r) * w + x]
    }
  }
  return out
}

/** Box radii whose three passes approximate a Gaussian of standard deviation sigma (Kovesi). */
function boxesForGauss(sigma: number): number[] {
  const n = 3
  const wIdeal = Math.sqrt((12 * sigma * sigma) / n + 1)
  let wl = Math.floor(wIdeal); if (wl % 2 === 0) wl--
  const wu = wl + 2
  const m = Math.round((12 * sigma * sigma - n * wl * wl - 4 * n * wl - 3 * n) / (-4 * wl - 4))
  return Array.from({ length: n }, (_, i) => ((i < m ? wl : wu) - 1) / 2)
}

/** Gaussian blur of values with σ = sigma (three box passes). */
export function gaussian(v: Uint8Array, w: number, h: number, sigma: number): Uint8Array {
  if (sigma <= 0) return v.slice()
  let f: Float32Array = new Float32Array(v.length)
  for (let i = 0; i < v.length; i++) f[i] = v[i]
  for (const r of boxesForGauss(sigma)) f = boxBlur(f, w, h, Math.max(0, Math.round(r)))
  const out = new Uint8Array(v.length)
  for (let i = 0; i < v.length; i++) out[i] = Math.round(f[i])
  return out
}

/** Photoshop's Feather: a Gaussian with σ = radius / 2. */
export function feather(v: Uint8Array, w: number, h: number, radius: number): Uint8Array { return gaussian(v, w, h, radius / 2) }

/** Smooth: blur by r, then re-threshold at half — removes specks and jaggies, keeps the edge hard. */
export function smooth(v: Uint8Array, w: number, h: number, r: number): Uint8Array {
  if (r <= 0) return v.slice()
  let f: Float32Array = new Float32Array(v.length)
  for (let i = 0; i < v.length; i++) f[i] = v[i]
  f = boxBlur(f, w, h, Math.round(r))
  const out = new Uint8Array(v.length)
  for (let i = 0; i < v.length; i++) out[i] = f[i] >= 127.5 ? 255 : 0
  return out
}

export type SelectionMode = 'replace' | 'add' | 'subtract' | 'intersect'

/** The mode a pointer gesture means: Shift adds, Alt subtracts, Shift+Alt intersects (Photoshop); otherwise the options' mode. */
export function modeFor(e: { shiftKey: boolean; altKey: boolean }, fallback: SelectionMode): SelectionMode {
  return e.shiftKey && e.altKey ? 'intersect' : e.shiftKey ? 'add' : e.altKey ? 'subtract' : fallback
}

/** Combine a new shape (values) into the current selection by mode. */
export function combine(cur: Uint8Array | null, shape: Uint8Array, mode: SelectionMode): Uint8Array {
  if (!cur) return mode === 'replace' || mode === 'add' ? shape.slice() : new Uint8Array(shape.length)   // nothing to subtract from or intersect with
  if (mode === 'replace') return shape.slice()
  const out = new Uint8Array(shape.length)
  for (let i = 0; i < out.length; i++) {
    const a = cur[i], b = shape[i]
    out[i] = mode === 'add' ? Math.max(a, b) : mode === 'subtract' ? Math.round((a * (255 - b)) / 255) : Math.min(a, b)
  }
  return out
}
