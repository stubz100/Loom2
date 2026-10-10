// Brush engine (D50, D51; PhotoCraft crates/paint/src/render.rs and dynamics.rs @ b37bff98, Copyright (c) 2026 ArtCraft Team and the
// PhotoCraft contributors, MIT OR Apache-2.0).
//
// Photoshop's opacity / flow model: dabs accumulate into a per-stroke coverage buffer, c ← c + flow·f·(1 − c) (f = the tip falloff), so
// flow builds coverage towards 1; the layer is then recomposited from its pre-stroke pixels as colour × coverage × opacity × selection
// over the touched area. Overlapping dabs therefore never exceed the stroke's opacity (the old Canvas2D dabs baked opacity into every
// dab and used flow as globalAlpha, so a 50 % brush reached 100 %). The pre-stroke pixels are the tile snapshots the layer keeps for
// undo anyway.
//
// Tip: a hard core of hardness·r, then (1 − t²)⁴ — Gaussian-like, exactly 0 at the rim, no exp(). Tips under 3 px radius are sampled
// 4×4 per pixel so thin lines do not bead.
//
// Smoothing: a pulled string — the brush follows the pointer only when the string (smoothing × 100 screen px, divided by zoom) is
// taut; while the pointer rests the brush catches up, and on release it finishes at the pointer.
import type { LayerPixels } from './layerPixels'

export interface StrokeSpec {
  lp: LayerPixels
  kind: 'image' | 'mask'          // a mask (or the quick-mask selection) stores grey values
  erase: boolean
  colour: [number, number, number]
  size: number; hardness: number; opacity: number; flow: number; spacing: number
  lockAlpha: boolean
  offset: { x: number; y: number }      // the target's position in the document
  selection: Uint8Array | null          // document-sized selection values (0–255), clipping the paint; null = everywhere
  docW: number
}

type Rect = { x0: number; y0: number; x1: number; y1: number }

export class Stroke {
  readonly s: StrokeSpec
  private cov: Float32Array
  private dirty: Rect | null = null
  private all: Rect | null = null
  private readonly w: number
  private readonly h: number

  constructor(spec: StrokeSpec) {
    this.s = spec
    this.w = spec.lp.width; this.h = spec.lp.height
    this.cov = new Float32Array(this.w * this.h)
    spec.lp.beginStroke()
  }

  /** The area painted so far (layer coordinates), for a caller that wants to know what changed. */
  get bounds(): Rect | null { return this.all }

  private grow(r: Rect) {
    const add = (a: Rect | null): Rect => (a ? { x0: Math.min(a.x0, r.x0), y0: Math.min(a.y0, r.y0), x1: Math.max(a.x1, r.x1), y1: Math.max(a.y1, r.y1) } : { ...r })
    this.dirty = add(this.dirty); this.all = add(this.all)
  }

  /** One dab centred at (x, y) in layer pixels. */
  dab(x: number, y: number): void {
    const { size, hardness, flow } = this.s
    const r = Math.max(0.5, size / 2)
    const core = Math.min(0.999, Math.max(0, hardness)) * r
    const x0 = Math.max(0, Math.floor(x - r)), y0 = Math.max(0, Math.floor(y - r))
    const x1 = Math.min(this.w, Math.ceil(x + r) + 1), y1 = Math.min(this.h, Math.ceil(y + r) + 1)
    if (x1 <= x0 || y1 <= y0) return
    const fall = (d: number) => {
      if (d >= r) return 0
      if (d <= core) return 1
      const t = (d - core) / (r - core)
      const u = 1 - t * t
      return u * u * u * u
    }
    const ss = r < 3 ? 4 : 1                                            // small tips: 4×4 sub-pixel area samples
    const cov = this.cov, W = this.w
    for (let py = y0; py < y1; py++) {
      for (let px = x0; px < x1; px++) {
        let f = 0
        if (ss === 1) f = fall(Math.hypot(px + 0.5 - x, py + 0.5 - y))
        else {
          for (let sy = 0; sy < ss; sy++) for (let sx = 0; sx < ss; sx++) f += fall(Math.hypot(px + (sx + 0.5) / ss - x, py + (sy + 0.5) / ss - y))
          f /= ss * ss
        }
        if (f <= 0) continue
        const i = py * W + px
        const v = flow * f
        cov[i] += v * (1 - cov[i])
      }
    }
    this.grow({ x0, y0, x1, y1 })
  }

  /** Recomposite what changed since the last flush from the pre-stroke pixels and upload it. */
  flush(): void {
    const d = this.dirty
    if (!d) return
    this.dirty = null
    const { lp, kind, erase, colour, opacity, lockAlpha, offset, selection, docW } = this.s
    const w = d.x1 - d.x0, h = d.y1 - d.y0
    lp.touch(d.x0, d.y0, d.x1 - 1, d.y1 - 1)                           // undo snapshots = the pre-stroke pixels
    const pre = lp.preStroke(d.x0, d.y0, w, h)
    const out = new ImageData(w, h)
    const a = pre.data, o = out.data, cov = this.cov, W = this.w
    const [cr, cg, cb] = colour
    for (let yy = 0; yy < h; yy++) {
      const ly = d.y0 + yy
      for (let xx = 0; xx < w; xx++) {
        const lx = d.x0 + xx
        const j = (yy * w + xx) * 4
        let k = cov[ly * W + lx] * opacity
        if (selection) {
          const dx = lx + offset.x, dy = ly + offset.y
          k *= dx >= 0 && dy >= 0 && dx < docW && dy * docW + dx < selection.length ? selection[dy * docW + dx] / 255 : 0
        }
        const r = a[j], g = a[j + 1], b = a[j + 2], al = a[j + 3]
        if (k <= 0) { o[j] = r; o[j + 1] = g; o[j + 2] = b; o[j + 3] = al; continue }
        if (kind === 'mask') {                                           // grey values: towards white (paint) or black (erase)
          const v0 = al === 255 ? r : (r * al) / 255
          const v = v0 + ((erase ? 0 : 255) - v0) * k
          o[j] = o[j + 1] = o[j + 2] = Math.round(v); o[j + 3] = 255
        } else if (erase) {
          o[j] = r; o[j + 1] = g; o[j + 2] = b; o[j + 3] = Math.round(al * (1 - k))
        } else if (lockAlpha) {                                          // the colour changes, the coverage stays
          o[j] = Math.round(r + (cr - r) * k); o[j + 1] = Math.round(g + (cg - g) * k); o[j + 2] = Math.round(b + (cb - b) * k); o[j + 3] = al
        } else {                                                         // source-over of colour at alpha k, straight alpha out
          const ab = al / 255, ao = k + ab * (1 - k)
          if (ao <= 0) { o[j] = o[j + 1] = o[j + 2] = o[j + 3] = 0; continue }
          o[j] = Math.round((cr * k + r * ab * (1 - k)) / ao); o[j + 1] = Math.round((cg * k + g * ab * (1 - k)) / ao); o[j + 2] = Math.round((cb * k + b * ab * (1 - k)) / ao)
          o[j + 3] = Math.round(ao * 255)
        }
      }
    }
    lp.ctx.putImageData(out, d.x0, d.y0)
    lp.refreshRect(d.x0, d.y0, d.x1, d.y1)
  }

  /** Discard what was painted (back to the pre-stroke pixels) and start the coverage over — the straight-line preview. */
  reset(): void {
    if (!this.all) return
    const d = this.all
    lpRestore(this.s.lp, d)
    this.cov.fill(0)
    this.dirty = null
  }
}

function lpRestore(lp: LayerPixels, d: Rect) {
  const pre = lp.preStroke(d.x0, d.y0, d.x1 - d.x0, d.y1 - d.y0)
  lp.ctx.putImageData(pre, d.x0, d.y0)
  lp.refreshRect(d.x0, d.y0, d.x1, d.y1)
}

/** Dabs every `step` px along a polyline, carrying the remainder across segments (PhotoCraft PathWalker). */
export class PathWalker {
  private rest = 0
  private readonly step: number
  constructor(step: number) { this.step = step }
  walk(a: { x: number; y: number }, b: { x: number; y: number }, emit: (x: number, y: number) => void): void {
    const dx = b.x - a.x, dy = b.y - a.y
    const len = Math.hypot(dx, dy)
    if (len <= 0) return
    let t = this.step - this.rest
    while (t <= len) { emit(a.x + (dx * t) / len, a.y + (dy * t) / len); t += this.step }
    this.rest = (this.rest + len) % this.step
  }
}

/** Pulled-string smoothing (D51): the brush point moves only when the pointer is farther than the string; `catchUp` pulls it towards
 * the pointer while the pointer rests (call it every frame), `finish` jumps to the pointer at release. */
export class Smoother {
  brush: { x: number; y: number }
  private target: { x: number; y: number }
  private readonly stringLen: number
  constructor(start: { x: number; y: number }, stringLen: number) { this.brush = { ...start }; this.target = { ...start }; this.stringLen = stringLen }
  /** A new pointer position; returns the brush point after it (unchanged while the string is slack). */
  push(p: { x: number; y: number }): { x: number; y: number } {
    this.target = { ...p }
    const dx = p.x - this.brush.x, dy = p.y - this.brush.y
    const d = Math.hypot(dx, dy)
    if (d > this.stringLen) { const f = (d - this.stringLen) / d; this.brush = { x: this.brush.x + dx * f, y: this.brush.y + dy * f } }
    return this.brush
  }
  /** While the pointer rests: move a share of the way to it (≈ 0.3 s to settle at 60 Hz). Returns the new point, or null when settled. */
  catchUp(share = 0.18): { x: number; y: number } | null {
    const dx = this.target.x - this.brush.x, dy = this.target.y - this.brush.y
    if (Math.hypot(dx, dy) < 0.5) return null
    this.brush = { x: this.brush.x + dx * share, y: this.brush.y + dy * share }
    return this.brush
  }
  finish(): { x: number; y: number } { this.brush = { ...this.target }; return this.brush }
}
