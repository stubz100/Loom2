// Free transform (D58; PhotoCraft crates/algo/src/transform.rs, resample.rs, crates/engine/src/transform_cmds.rs and
// crates/ui-egui/src/transform_tool.rs @ b37bff98, Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors, MIT OR Apache-2.0).
//
// The state is a source frame `rect` (document px), the quad its corners map to (clockwise from top-left) and a reference point; the
// mapping is always rebuilt as the homography rect → quad, so scale, rotate, skew, distort and perspective are one thing. Drags are
// computed from the quad at the start of the drag (nothing accumulates); apply resamples the original pixels once — inverse mapping at
// pixel centres, nearest / bilinear / Catmull-Rom bicubic on premultiplied pixels, transparent outside — after a real downscale when
// the transform shrinks below 50 %.
export interface Pt { x: number; y: number }
export type Quad = [Pt, Pt, Pt, Pt]
export type Interp = 'bicubic' | 'bilinear' | 'nearest'
export type TransformMode = 'free' | 'skew' | 'distort' | 'perspective'
export interface Xform {
  nodeId: string
  rect: [number, number, number, number]          // x0, y0, x1, y1 — integer document px
  quad: Quad
  pivot: Pt
  interp: Interp
  mode: TransformMode
  selection: boolean                               // transform the selected pixels only (lifted, warped, composited back)
}

// ---- homography ------------------------------------------------------------------------------------------------
/** 3×3 row-major, column vectors: [x', y', w'] = H · [x, y, 1]. */
export class Homography {
  readonly m: number[]
  constructor(m: number[]) { this.m = m }
  static readonly IDENTITY = new Homography([1, 0, 0, 0, 1, 0, 0, 0, 1])
  apply(x: number, y: number): Pt {
    const m = this.m, w = m[6] * x + m[7] * y + m[8]
    return { x: (m[0] * x + m[1] * y + m[2]) / w, y: (m[3] * x + m[4] * y + m[5]) / w }
  }
  /** this · o (o applied first). */
  mul(o: Homography): Homography {
    const a = this.m, b = o.m, r = new Array(9).fill(0)
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) r[i * 3 + j] += a[i * 3 + k] * b[k * 3 + j]
    return new Homography(r)
  }
  inverse(): Homography | null {
    const m = this.m
    const c = [
      m[4] * m[8] - m[5] * m[7], m[2] * m[7] - m[1] * m[8], m[1] * m[5] - m[2] * m[4],
      m[5] * m[6] - m[3] * m[8], m[0] * m[8] - m[2] * m[6], m[2] * m[3] - m[0] * m[5],
      m[3] * m[7] - m[4] * m[6], m[1] * m[6] - m[0] * m[7], m[0] * m[4] - m[1] * m[3],
    ]
    const det = m[0] * c[0] + m[1] * c[3] + m[2] * c[6]
    if (Math.abs(det) < 1e-12) return null
    return new Homography(c.map((v) => v / det))
  }
  /** Unit square → quad (Heckbert's closed form; corners (0,0), (1,0), (1,1), (0,1)). */
  static squareToQuad(q: Quad): Homography | null {
    const [{ x: x0, y: y0 }, { x: x1, y: y1 }, { x: x2, y: y2 }, { x: x3, y: y3 }] = q
    const sx = x0 - x1 + x2 - x3, sy = y0 - y1 + y2 - y3
    if (Math.abs(sx) < 1e-12 && Math.abs(sy) < 1e-12) return new Homography([x1 - x0, x3 - x0, x0, y1 - y0, y3 - y0, y0, 0, 0, 1])
    const dx1 = x1 - x2, dx2 = x3 - x2, dy1 = y1 - y2, dy2 = y3 - y2
    const den = dx1 * dy2 - dx2 * dy1
    if (Math.abs(den) < 1e-12) return null
    const g = (sx * dy2 - dx2 * sy) / den, h = (dx1 * sy - sx * dy1) / den
    return new Homography([x1 - x0 + g * x1, x3 - x0 + h * x3, x0, y1 - y0 + g * y1, y3 - y0 + h * y3, y0, g, h, 1])
  }
  /** Rectangle (x0, y0, x1, y1) onto a quad (clockwise from top-left); null when degenerate. */
  static rectToQuad(r: readonly number[], quad: Quad): Homography | null {
    const w = r[2] - r[0], h = r[3] - r[1]
    if (w <= 0 || h <= 0) return null
    const sq = Homography.squareToQuad(quad)
    return sq ? sq.mul(new Homography([1 / w, 0, -r[0] / w, 0, 1 / h, -r[1] / h, 0, 0, 1])) : null
  }
  /** Approximate linear scale near (x, y): √|Jacobian det| by ±0.5 px central differences. */
  localScale(x: number, y: number): number {
    const e = 0.5, a = this.apply(x - e, y), b = this.apply(x + e, y), c = this.apply(x, y - e), d = this.apply(x, y + e)
    const jx = [b.x - a.x, b.y - a.y], jy = [d.x - c.x, d.y - c.y]
    return Math.sqrt(Math.abs(jx[0] * jy[1] - jx[1] * jy[0]))
  }
  /** The six numbers of an affine map [a, b, c, d, e, f] — (x, y) → (a·x + c·y + e, b·x + d·y + f) — as a homography. */
  static affine(a: number, b: number, c: number, d: number, e: number, f: number): Homography { return new Homography([a, c, e, b, d, f, 0, 0, 1]) }
}

export const rectCorners = (r: readonly number[]): Quad => [{ x: r[0], y: r[1] }, { x: r[2], y: r[1] }, { x: r[2], y: r[3] }, { x: r[0], y: r[3] }]
export const quadOf = (t: Xform): Quad => t.quad
export const homographyOf = (t: Xform): Homography | null => Homography.rectToQuad(t.rect, t.quad)
export const isIdentity = (t: Xform) => rectCorners(t.rect).every((c, i) => Math.abs(c.x - t.quad[i].x) < 1e-9 && Math.abs(c.y - t.quad[i].y) < 1e-9)

// ---- resampling --------------------------------------------------------------------------------------------------
export interface Raster { data: Float32Array; w: number; h: number; x: number; y: number }     // premultiplied RGBA 0..1 at document (x, y)

export function premultiply(rgba: Uint8ClampedArray, w: number, h: number, x: number, y: number): Raster {
  const d = new Float32Array(w * h * 4)
  for (let i = 0; i < d.length; i += 4) {
    const a = rgba[i + 3] / 255
    d[i] = (rgba[i] / 255) * a; d[i + 1] = (rgba[i + 1] / 255) * a; d[i + 2] = (rgba[i + 2] / 255) * a; d[i + 3] = a
  }
  return { data: d, w, h, x, y }
}
/** Straight 8-bit RGBA (colour un-premultiplied and clamped; round half up as PhotoCraft stores U8). */
export function toStraight8(r: Raster): Uint8ClampedArray {
  const out = new Uint8ClampedArray(r.w * r.h * 4), d = r.data
  for (let i = 0; i < d.length; i += 4) {
    const a = Math.min(1, Math.max(0, d[i + 3]))
    if (a <= 0) continue
    for (let c = 0; c < 3; c++) out[i + c] = Math.floor(Math.min(1, Math.max(0, d[i + c] / a)) * 255 + 0.5)
    out[i + 3] = Math.floor(a * 255 + 0.5)
  }
  return out
}

function catmullRom(t: number, w: Float64Array) {
  const t2 = t * t, t3 = t2 * t
  w[0] = -0.5 * t3 + t2 - 0.5 * t; w[1] = 1.5 * t3 - 2.5 * t2 + 1; w[2] = -1.5 * t3 + 2 * t2 + 0.5 * t; w[3] = 0.5 * t3 - 0.5 * t2
}
/** Keys cubic (a = −0.5), the resize kernel. */
function keys(x: number): number {
  x = Math.abs(x)
  return x < 1 ? 1.5 * x * x * x - 2.5 * x * x + 1 : x < 2 ? -0.5 * x * x * x + 2.5 * x * x - 4 * x + 2 : 0
}
/** PhotoCraft resize_surface (bicubic): separable, positions about the document origin, the kernel stretched by 1 / scale when
 * shrinking (an area-like filter), weights normalised; premultiplied in, premultiplied out. */
export function resizeRaster(src: Raster, f: number): Raster {
  const x0 = Math.floor(src.x * f), y0 = Math.floor(src.y * f), x1 = Math.ceil((src.x + src.w) * f), y1 = Math.ceil((src.y + src.h) * f)
  const ow = Math.max(1, x1 - x0), oh = Math.max(1, y1 - y0)
  const stretch = f < 1 ? 1 / f : 1, support = 2 * stretch
  const pass = (n: number, start: number, len: number, srcStart: number) => {
    // for each output index o: the source taps (absolute index − srcStart) and normalised weights
    const taps: { i0: number; w: Float64Array }[] = []
    for (let o = 0; o < n; o++) {
      const u = (start + o + 0.5) / f - 0.5
      const i0 = Math.ceil(u - support), i1 = Math.floor(u + support)
      const w = new Float64Array(i1 - i0 + 1)
      let sum = 0
      for (let i = i0; i <= i1; i++) { const v = keys((i - u) / stretch); w[i - i0] = v; sum += v }
      if (sum !== 0) for (let k = 0; k < w.length; k++) w[k] /= sum
      taps.push({ i0: i0 - srcStart, w })
    }
    void len
    return taps
  }
  const tx = pass(ow, x0, src.w, src.x), ty = pass(oh, y0, src.h, src.y)
  const mid = new Float32Array(ow * src.h * 4)
  for (let y = 0; y < src.h; y++) for (let o = 0; o < ow; o++) {
    const { i0, w } = tx[o]
    let r = 0, g = 0, b = 0, a = 0
    for (let k = 0; k < w.length; k++) {
      const sx = i0 + k
      if (sx < 0 || sx >= src.w) continue
      const j = (y * src.w + sx) * 4, wk = w[k]
      r += src.data[j] * wk; g += src.data[j + 1] * wk; b += src.data[j + 2] * wk; a += src.data[j + 3] * wk
    }
    const q = (y * ow + o) * 4
    mid[q] = r; mid[q + 1] = g; mid[q + 2] = b; mid[q + 3] = a
  }
  const out = new Float32Array(ow * oh * 4)
  for (let o = 0; o < oh; o++) {
    const { i0, w } = ty[o]
    for (let x = 0; x < ow; x++) {
      let r = 0, g = 0, b = 0, a = 0
      for (let k = 0; k < w.length; k++) {
        const sy = i0 + k
        if (sy < 0 || sy >= src.h) continue
        const j = (sy * ow + x) * 4, wk = w[k]
        r += mid[j] * wk; g += mid[j + 1] * wk; b += mid[j + 2] * wk; a += mid[j + 3] * wk
      }
      const q = (o * ow + x) * 4
      const al = Math.min(1, Math.max(0, a))                          // alpha clamped; colour kept ≤ alpha so it un-premultiplies within 0..1
      out[q] = Math.min(al, Math.max(0, r)); out[q + 1] = Math.min(al, Math.max(0, g)); out[q + 2] = Math.min(al, Math.max(0, b)); out[q + 3] = al
    }
  }
  return { data: out, w: ow, h: oh, x: x0, y: y0 }
}

/** PhotoCraft warp_surface: the source (premultiplied, at its document position) through `h`, onto a raster covering the warped
 * corners plus a pixel. Inverse mapping at pixel centres; outside the source reads transparent; colour un-premultiplied and clamped. */
export function warpRaster(srcIn: Raster, hIn: Homography, interp: Interp): Raster | null {
  let src = srcIn, h = hIn
  if (src.w <= 0 || src.h <= 0) return null
  const scale = h.localScale(src.x + src.w / 2, src.y + src.h / 2)
  if (interp !== 'nearest' && scale < 0.5 && scale > 0) {               // pre-reduce: bicubic alone aliases below ~50 %
    const f = Math.min(1, 2 ** Math.ceil(Math.log2(scale)))
    src = resizeRaster(src, f)
    h = h.mul(new Homography([1 / f, 0, 0, 0, 1 / f, 0, 0, 0, 1]))
  }
  const inv = h.inverse()
  if (!inv) return null
  const cs = rectCorners([src.x, src.y, src.x + src.w, src.y + src.h]).map((c) => h.apply(c.x, c.y))
  if (cs.some((c) => !Number.isFinite(c.x) || !Number.isFinite(c.y))) return null
  const lim = 1 << 20
  const bx0 = Math.max(-lim, Math.floor(Math.min(...cs.map((c) => c.x)))) - 1, by0 = Math.max(-lim, Math.floor(Math.min(...cs.map((c) => c.y)))) - 1
  const bx1 = Math.min(lim, Math.ceil(Math.max(...cs.map((c) => c.x)))) + 1, by1 = Math.min(lim, Math.ceil(Math.max(...cs.map((c) => c.y)))) + 1
  const W = bx1 - bx0, H = by1 - by0
  const out = new Float32Array(W * H * 4)
  const s = src.data, sw = src.w, sh = src.h, sx0 = src.x, sy0 = src.y
  const m = inv.m
  const wx = new Float64Array(4), wy = new Float64Array(4)
  const acc = new Float64Array(4)
  for (let y = 0; y < H; y++) {
    const py = by0 + y + 0.5
    for (let x = 0; x < W; x++) {
      const px = bx0 + x + 0.5
      const w = m[6] * px + m[7] * py + m[8]
      const u = (m[0] * px + m[1] * py + m[2]) / w - 0.5 - sx0, v = (m[3] * px + m[4] * py + m[5]) / w - 0.5 - sy0   // source-local
      if (u < -1 || v < -1 || u > sw || v > sh) continue
      acc[0] = acc[1] = acc[2] = acc[3] = 0
      if (interp === 'nearest') {
        const ix = Math.floor(u + 0.5), iy = Math.floor(v + 0.5)
        if (ix < 0 || iy < 0 || ix >= sw || iy >= sh) continue
        const j = (iy * sw + ix) * 4
        acc[0] = s[j]; acc[1] = s[j + 1]; acc[2] = s[j + 2]; acc[3] = s[j + 3]
      } else if (interp === 'bilinear') {
        const ix = Math.floor(u), iy = Math.floor(v), fx = u - ix, fy = v - iy
        for (let dy = 0; dy < 2; dy++) {
          const yy = iy + dy
          if (yy < 0 || yy >= sh) continue
          const ky = dy ? fy : 1 - fy
          for (let dx = 0; dx < 2; dx++) {
            const xx = ix + dx
            if (xx < 0 || xx >= sw) continue
            const k = ky * (dx ? fx : 1 - fx), j = (yy * sw + xx) * 4
            acc[0] += s[j] * k; acc[1] += s[j + 1] * k; acc[2] += s[j + 2] * k; acc[3] += s[j + 3] * k
          }
        }
      } else {
        const ix = Math.floor(u), iy = Math.floor(v)
        catmullRom(u - ix, wx); catmullRom(v - iy, wy)
        for (let j = 0; j < 4; j++) {
          const yy = iy - 1 + j
          if (yy < 0 || yy >= sh) continue
          for (let i = 0; i < 4; i++) {
            const xx = ix - 1 + i
            if (xx < 0 || xx >= sw) continue
            const k = wx[i] * wy[j], q = (yy * sw + xx) * 4
            acc[0] += s[q] * k; acc[1] += s[q + 1] * k; acc[2] += s[q + 2] * k; acc[3] += s[q + 3] * k
          }
        }
      }
      const al = Math.min(1, Math.max(0, acc[3]))
      if (al <= 0) continue
      const o = (y * W + x) * 4
      out[o] = Math.min(al, Math.max(0, acc[0])); out[o + 1] = Math.min(al, Math.max(0, acc[1])); out[o + 2] = Math.min(al, Math.max(0, acc[2])); out[o + 3] = al
    }
  }
  return { data: out, w: W, h: H, x: bx0, y: by0 }
}

/** Straight-alpha Normal "over" of `top` onto `base` (both premultiplied rasters); the result covers both. */
export function compositeOver(base: Raster, top: Raster): Raster {
  const x0 = Math.min(base.x, top.x), y0 = Math.min(base.y, top.y), x1 = Math.max(base.x + base.w, top.x + top.w), y1 = Math.max(base.y + base.h, top.y + top.h)
  const out: Raster = { data: new Float32Array((x1 - x0) * (y1 - y0) * 4), w: x1 - x0, h: y1 - y0, x: x0, y: y0 }
  const blit = (r: Raster, over: boolean) => {
    for (let y = 0; y < r.h; y++) for (let x = 0; x < r.w; x++) {
      const i = (y * r.w + x) * 4, o = ((y + r.y - y0) * out.w + (x + r.x - x0)) * 4
      const ta = r.data[i + 3]
      if (!over) { out.data[o] = r.data[i]; out.data[o + 1] = r.data[i + 1]; out.data[o + 2] = r.data[i + 2]; out.data[o + 3] = ta; continue }
      if (ta <= 0) continue
      const k = 1 - ta                                                   // premultiplied over = the straight-alpha formula
      out.data[o] = r.data[i] + out.data[o] * k; out.data[o + 1] = r.data[i + 1] + out.data[o + 1] * k
      out.data[o + 2] = r.data[i + 2] + out.data[o + 2] * k; out.data[o + 3] = ta + out.data[o + 3] * k
    }
  }
  blit(base, false); blit(top, true)
  return out
}

/** PhotoCraft split_selected: the selected part (alpha × k) and the rest (alpha × (1 − k)); `k(x, y)` in document px gives 0..1. */
export function splitSelected(src: Raster, k: (x: number, y: number) => number): { lifted: Raster; rest: Raster } {
  const lifted: Raster = { ...src, data: new Float32Array(src.data.length) }, rest: Raster = { ...src, data: new Float32Array(src.data.length) }
  for (let y = 0; y < src.h; y++) for (let x = 0; x < src.w; x++) {
    const i = (y * src.w + x) * 4, f = k(src.x + x, src.y + y)
    for (let c = 0; c < 4; c++) { lifted.data[i + c] = src.data[i + c] * f; rest.data[i + c] = src.data[i + c] * (1 - f) }
  }
  return { lifted, rest }
}

/** PhotoCraft warp_gray(_selected): a grey surface (a mask, the selection) through `h`, flattened onto its default value — the part that
 * moves (all of it, or the selected part k) leaves the default behind. Values 0..255 at document (x, y); the result covers the old
 * extent and the warped one. */
export function warpGray(vals: Uint8Array, w: number, h: number, x: number, y: number, hom: Homography, interp: Interp, def: number, k?: (x: number, y: number) => number): { vals: Uint8Array; w: number; h: number; x: number; y: number } {
  const lifted: Raster = { data: new Float32Array(w * h * 4), w, h, x, y }
  const rest = new Float32Array(w * h)
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const p = j * w + i, v = vals[p] / 255, f = k ? k(x + i, y + j) : 1
    lifted.data[p * 4] = v * f; lifted.data[p * 4 + 3] = f                // grey in R, premultiplied by the lift
    rest[p] = v * (1 - f) + (def / 255) * f
  }
  const moved = warpRaster(lifted, hom, interp)
  const x0 = Math.min(x, moved?.x ?? x), y0 = Math.min(y, moved?.y ?? y)
  const x1 = Math.max(x + w, moved ? moved.x + moved.w : x + w), y1 = Math.max(y + h, moved ? moved.y + moved.h : y + h)
  const W = x1 - x0, H = y1 - y0
  const out = new Float32Array(W * H).fill(def / 255)
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) out[(j + y - y0) * W + (i + x - x0)] = rest[j * w + i]
  if (moved) for (let j = 0; j < moved.h; j++) for (let i = 0; i < moved.w; i++) {
    const q = (j * moved.w + i) * 4, a = moved.data[q + 3]
    if (a <= 0) continue
    const o = (j + moved.y - y0) * W + (i + moved.x - x0)
    out[o] = moved.data[q] + out[o] * (1 - a)                           // premultiplied grey over the rest
  }
  const res = new Uint8Array(W * H)
  for (let p = 0; p < res.length; p++) res[p] = Math.floor(Math.min(1, Math.max(0, out[p])) * 255 + 0.5)
  return { vals: res, w: W, h: H, x: x0, y: y0 }
}

// ---- the box: hit testing and drags (transform_tool.rs) -----------------------------------------------------------
export type Hit = { kind: 'corner'; i: number } | { kind: 'edge'; i: number } | { kind: 'pivot' } | { kind: 'inside' } | { kind: 'outside' }
const lerp = (a: Pt, b: Pt, t: number): Pt => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t })
/** Edge i runs from corner i to corner i + 1 (0 top, 1 right, 2 bottom, 3 left); its handle sits at the image of the edge's middle. */
export function edgeHandles(t: Xform): Pt[] {
  const h = Homography.squareToQuad(t.quad)
  if (!h) return t.quad.map((c, i) => lerp(c, t.quad[(i + 1) % 4], 0.5))
  return [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]].map(([u, v]) => h.apply(u, v))
}
export function insideQuad(q: Quad, p: Pt): boolean {                     // even-odd
  let inside = false
  for (let i = 0, j = 3; i < 4; j = i++) {
    const a = q[i], b = q[j]
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside
  }
  return inside
}
export function hitTest(t: Xform, p: Pt, tol: number): Hit {
  let best: Hit | null = null, bd = tol
  t.quad.forEach((c, i) => { const d = Math.hypot(c.x - p.x, c.y - p.y); if (d <= bd) { bd = d; best = { kind: 'corner', i } } })
  edgeHandles(t).forEach((c, i) => { const d = Math.hypot(c.x - p.x, c.y - p.y); if (d <= bd) { bd = d; best = { kind: 'edge', i } } })
  const dp = Math.hypot(t.pivot.x - p.x, t.pivot.y - p.y)
  if (dp <= bd) best = { kind: 'pivot' }
  if (best) return best
  return insideQuad(t.quad, p) ? { kind: 'inside' } : { kind: 'outside' }
}

/** The reference point keeps its place inside the box when the quad changes. */
export function carryPivot(q0: Quad, q1: Quad, pivot0: Pt): Pt {
  const h0 = Homography.squareToQuad(q0), h1 = Homography.squareToQuad(q1)
  const inv = h0?.inverse()
  if (!h0 || !h1 || !inv) return pivot0
  const u = inv.apply(pivot0.x, pivot0.y), p = h1.apply(u.x, u.y)
  return Number.isFinite(p.x) && Number.isFinite(p.y) ? p : pivot0
}
const turn = (q: Quad, i: number) => { const a = q[(i + 3) % 4], b = q[i], c = q[(i + 1) % 4]; return (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x) }
/** Distort / perspective may not fold the box: past a convex start, the move stops at the furthest convex point (40 bisections). */
export function keepConvex(q0: Quad, q: Quad): Quad {
  const t0 = [0, 1, 2, 3].map((i) => turn(q0, i))
  const sign = Math.sign(t0[0])
  if (!sign || t0.some((v) => Math.sign(v) !== sign)) return q                // a degenerate / non-convex start is left free
  const minTurn = 1e-3 * Math.min(...t0.map(Math.abs))
  const ok = (qq: Quad) => [0, 1, 2, 3].every((i) => turn(qq, i) * sign > minTurn)
  if (ok(q)) return q
  const at = (f: number): Quad => q0.map((c, i) => lerp(c, q[i], f)) as Quad
  let lo = 0, hi = 1
  for (let n = 0; n < 40; n++) { const mid = (lo + hi) / 2; if (ok(at(mid))) lo = mid; else hi = mid }
  return at(lo)
}
export interface DragMods { shift: boolean; alt: boolean; ctrl: boolean }
/** A menu mode turns a plain handle drag into that mode's gesture (PhotoCraft mode_mods). */
export function modeMods(mode: TransformMode, hit: Hit, m: DragMods): DragMods {
  if ((mode === 'skew' && hit.kind === 'edge') || (mode === 'distort' && hit.kind === 'corner')) return { ...m, ctrl: true }
  if (mode === 'perspective' && hit.kind === 'corner') return { ctrl: true, alt: true, shift: true }
  return m
}
const rot = (p: Pt, c: Pt, a: number): Pt => { const cs = Math.cos(a), sn = Math.sin(a), dx = p.x - c.x, dy = p.y - c.y; return { x: c.x + dx * cs - dy * sn, y: c.y + dx * sn + dy * cs } }
/** One drag step, always from the quad and pivot at the drag's start (PhotoCraft apply_drag). */
export function applyDrag(t: Xform, hit: Hit, quad0: Quad, pivot0: Pt, start: Pt, p: Pt, mIn: DragMods): Pick<Xform, 'quad' | 'pivot'> {
  const m = modeMods(t.mode, hit, mIn)
  const dx = p.x - start.x, dy = p.y - start.y
  const move = (q: Quad, ddx: number, ddy: number) => q.map((c) => ({ x: c.x + ddx, y: c.y + ddy })) as Quad
  if (hit.kind === 'inside') {
    let mx = dx, my = dy
    if (m.shift) { const a = Math.round(Math.atan2(dy, dx) / (Math.PI / 4)) * (Math.PI / 4), d = Math.hypot(dx, dy); mx = Math.cos(a) * d; my = Math.sin(a) * d }
    return { quad: move(quad0, mx, my), pivot: { x: pivot0.x + mx, y: pivot0.y + my } }
  }
  if (hit.kind === 'pivot') return { quad: quad0, pivot: p }
  if (hit.kind === 'outside') {
    let da = Math.atan2(p.y - pivot0.y, p.x - pivot0.x) - Math.atan2(start.y - pivot0.y, start.x - pivot0.x)
    if (m.shift) { const base = Math.atan2(quad0[1].y - quad0[0].y, quad0[1].x - quad0[0].x), s = Math.PI / 12; da = Math.round((base + da) / s) * s - base }
    return { quad: quad0.map((c) => rot(c, pivot0, da)) as Quad, pivot: pivot0 }
  }
  if (hit.kind === 'corner' && m.ctrl && m.alt && m.shift) {             // perspective: the corner and its neighbour move mirrored
    const i = hit.i, horizontal = Math.abs(dx) >= Math.abs(dy)
    const j = horizontal ? [1, 0, 3, 2][i] : [3, 2, 1, 0][i]
    const mx = horizontal ? dx : 0, my = horizontal ? 0 : dy
    const q = quad0.map((c) => ({ ...c })) as Quad
    q[i] = { x: q[i].x + mx, y: q[i].y + my }; q[j] = { x: q[j].x - mx, y: q[j].y - my }
    const kq = keepConvex(quad0, q)
    return { quad: kq, pivot: carryPivot(quad0, kq, pivot0) }
  }
  if (hit.kind === 'corner' && m.ctrl) {                                 // distort: one corner
    const q = quad0.map((c) => ({ ...c })) as Quad
    q[hit.i] = { x: q[hit.i].x + dx, y: q[hit.i].y + dy }
    const kq = keepConvex(quad0, q)
    return { quad: kq, pivot: carryPivot(quad0, kq, pivot0) }
  }
  if (hit.kind === 'edge' && m.ctrl) {                                   // skew: the edge's two corners (Shift along the edge, Alt symmetric)
    const i = hit.i, j = (i + 1) % 4
    let mx = dx, my = dy
    if (m.shift) { const ex = quad0[j].x - quad0[i].x, ey = quad0[j].y - quad0[i].y, l2 = ex * ex + ey * ey || 1, k = (dx * ex + dy * ey) / l2; mx = ex * k; my = ey * k }
    const q = quad0.map((c) => ({ ...c })) as Quad
    q[i] = { x: q[i].x + mx, y: q[i].y + my }; q[j] = { x: q[j].x + mx, y: q[j].y + my }
    if (m.alt) { const a = (i + 2) % 4, b = (i + 3) % 4; q[a] = { x: q[a].x - mx, y: q[a].y - my }; q[b] = { x: q[b].x - mx, y: q[b].y - my } }
    return { quad: q, pivot: carryPivot(quad0, q, pivot0) }
  }
  // scale, in the box's own unit frame — proportional by default (Shift frees it), Alt about the reference point
  const h = Homography.squareToQuad(quad0), inv = h?.inverse()
  if (!h || !inv) return { quad: quad0, pivot: pivot0 }
  const uv = inv.apply(p.x, p.y), pv = inv.apply(pivot0.x, pivot0.y)
  const r = [0, 0, 1, 1]
  const sel: Record<string, [[boolean, boolean], [boolean, boolean]]> = {
    'corner0': [[true, false], [true, false]], 'corner1': [[false, true], [true, false]], 'corner2': [[false, true], [false, true]], 'corner3': [[true, false], [false, true]],
    'edge0': [[false, false], [true, false]], 'edge1': [[false, true], [false, false]], 'edge2': [[false, false], [false, true]], 'edge3': [[true, false], [false, false]],
  }
  const [mu, mv] = sel[`${hit.kind}${(hit as { i: number }).i}`]
  if (mu[0]) r[0] = uv.x; if (mu[1]) r[2] = uv.x; if (mv[0]) r[1] = uv.y; if (mv[1]) r[3] = uv.y
  if (m.alt) {
    if (mu[0]) r[2] = 2 * pv.x - r[0]; if (mu[1]) r[0] = 2 * pv.x - r[2]
    if (mv[0]) r[3] = 2 * pv.y - r[1]; if (mv[1]) r[1] = 2 * pv.y - r[3]
  }
  const corner = hit.kind === 'corner'
  if (!corner && !m.shift) {                                             // an edge scales proportionally about the box middle (Alt: the pivot)
    if (mu[0] || mu[1]) { const k = Math.abs(r[2] - r[0]), c = m.alt ? pv.y : 0.5; r[1] = c - k / 2; r[3] = c + k / 2 }
    else { const k = Math.abs(r[3] - r[1]), c = m.alt ? pv.x : 0.5; r[0] = c - k / 2; r[2] = c + k / 2 }
  }
  if (corner && !m.shift) {                                              // a corner: proportional, the larger axis wins
    const sx = r[2] - r[0], sy = r[3] - r[1]
    const k = Math.max(Math.abs(sx), Math.abs(sy))
    const nx = k * (Math.sign(sx) || 1), ny = k * (Math.sign(sy) || 1)
    const ax = m.alt ? pv.x : mu[0] ? r[2] : r[0], ay = m.alt ? pv.y : mv[0] ? r[3] : r[1]
    const fx = m.alt ? 0.5 : mu[0] ? 1 : 0, fy = m.alt ? 0.5 : mv[0] ? 1 : 0
    r[0] = ax - nx * fx; r[2] = r[0] + nx; r[1] = ay - ny * fy; r[3] = r[1] + ny
  }
  const quad = [h.apply(r[0], r[1]), h.apply(r[2], r[1]), h.apply(r[2], r[3]), h.apply(r[0], r[3])] as Quad
  return { quad, pivot: m.alt ? pivot0 : carryPivot(quad0, quad, pivot0) }
}

/** The strip's readout: W / H as a share of the source frame, the angle of the top edge (degrees). */
export function readout(t: Xform): { sx: number; sy: number; angle: number } {
  const [q0, q1, , q3] = t.quad
  return { sx: Math.hypot(q1.x - q0.x, q1.y - q0.y) / (t.rect[2] - t.rect[0]), sy: Math.hypot(q3.x - q0.x, q3.y - q0.y) / (t.rect[3] - t.rect[1]), angle: (Math.atan2(q1.y - q0.y, q1.x - q0.x) * 180) / Math.PI }
}
/** Scale the box in its own frame about the reference point. */
export function scaleAboutPivot(t: Xform, kx: number, ky: number): Quad {
  const h = Homography.squareToQuad(t.quad), inv = h?.inverse()
  if (!h || !inv) return t.quad
  const pv = inv.apply(t.pivot.x, t.pivot.y)
  return [[0, 0], [1, 0], [1, 1], [0, 1]].map(([u, v]) => h.apply(pv.x + (u - pv.x) * kx, pv.y + (v - pv.y) * ky)) as Quad
}
export const rotateAboutPivot = (t: Xform, deg: number): Quad => t.quad.map((c) => rot(c, t.pivot, (deg * Math.PI) / 180)) as Quad

/** Dev builds: the headed check exercises the maths in the page. */
if (import.meta.env.DEV) (globalThis as unknown as { __loom2Transform?: unknown }).__loom2Transform = { Homography, warpRaster, premultiply, toStraight8, resizeRaster, rectCorners, applyDrag, warpGray, insideQuad, hitTest }
