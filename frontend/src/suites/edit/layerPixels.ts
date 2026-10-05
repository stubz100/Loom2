// Pixel storage for one raster layer or mask (10 §3): a 2D canvas (the CPU truth, painted by the tools), a PixiJS
// texture refreshed from it, 256² tile snapshots for undo, and raw RGBA transfer to the orchestrator (06 §2).
import { Texture } from 'pixi.js'

export const TILE = 256

export interface TileSnapshot { x: number; y: number; data: ImageData }

export class LayerPixels {
  readonly canvas: HTMLCanvasElement
  readonly ctx: CanvasRenderingContext2D
  readonly texture: Texture
  dirty = false                 // changed since the last upload to the orchestrator
  private strokeTiles = new Map<string, TileSnapshot>()

  width: number
  height: number
  readonly grey: boolean
  constructor(width: number, height: number, grey = false) {
    this.width = width; this.height = height; this.grey = grey
    this.canvas = document.createElement('canvas')
    this.canvas.width = Math.max(1, width)
    this.canvas.height = Math.max(1, height)
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: true })!
    this.texture = Texture.from(this.canvas)
  }

  static fromRaw(width: number, height: number, bytes: Uint8Array, channels: 1 | 4): LayerPixels {
    const lp = new LayerPixels(width, height, channels === 1)
    const img = lp.ctx.createImageData(width, height)
    if (channels === 4) img.data.set(bytes)
    else for (let i = 0, j = 0; i < bytes.length; i++, j += 4) { img.data[j] = img.data[j + 1] = img.data[j + 2] = bytes[i]; img.data[j + 3] = 255 }
    lp.ctx.putImageData(img, 0, 0)
    lp.refresh()
    return lp
  }

  static fromImage(img: ImageBitmap | HTMLImageElement, width?: number, height?: number): LayerPixels {
    const lp = new LayerPixels(width ?? img.width, height ?? img.height)
    lp.ctx.drawImage(img, 0, 0)
    lp.refresh()
    return lp
  }

  /** Re-upload the canvas to the GPU (whole texture; tiles later if measured as the bottleneck). */
  refresh(): void { this.texture.source.update() }

  /** Raw bytes for `PUT …/pixels`: RGBA, or the red channel for masks. */
  toRaw(): Uint8Array {
    const img = this.ctx.getImageData(0, 0, this.width, this.height)
    if (!this.grey) return new Uint8Array(img.data.buffer, img.data.byteOffset, img.data.byteLength)
    const out = new Uint8Array(this.width * this.height)
    for (let i = 0, j = 0; i < out.length; i++, j += 4) out[i] = img.data[j]
    return out
  }

  // ---- undo: snapshot the tiles a stroke is about to touch, once per stroke ----------------------
  beginStroke(): void { this.strokeTiles.clear() }

  /** Call before painting anything inside the rect; captures untouched tiles. */
  touch(x0: number, y0: number, x1: number, y1: number): void {
    const tx0 = Math.max(0, Math.floor(x0 / TILE)), ty0 = Math.max(0, Math.floor(y0 / TILE))
    const tx1 = Math.min(Math.ceil(this.width / TILE) - 1, Math.floor(x1 / TILE)), ty1 = Math.min(Math.ceil(this.height / TILE) - 1, Math.floor(y1 / TILE))
    for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) {
      const key = `${tx},${ty}`
      if (this.strokeTiles.has(key)) continue
      const x = tx * TILE, y = ty * TILE
      const w = Math.min(TILE, this.width - x), h = Math.min(TILE, this.height - y)
      if (w <= 0 || h <= 0) continue
      this.strokeTiles.set(key, { x, y, data: this.ctx.getImageData(x, y, w, h) })
    }
  }

  /** The snapshots captured during this stroke (the history entry). */
  endStroke(): TileSnapshot[] { const out = [...this.strokeTiles.values()]; this.strokeTiles.clear(); return out }

  /** Swap tiles in and return what was there (so redo is the same operation). */
  restore(tiles: TileSnapshot[]): TileSnapshot[] {
    const before: TileSnapshot[] = []
    for (const t of tiles) {
      before.push({ x: t.x, y: t.y, data: this.ctx.getImageData(t.x, t.y, t.data.width, t.data.height) })
      this.ctx.putImageData(t.data, t.x, t.y)
    }
    this.refresh()
    this.dirty = true
    return before
  }

  snapshotAll(): TileSnapshot[] {
    this.beginStroke()
    this.touch(0, 0, this.width, this.height)
    return this.endStroke()
  }

  resize(width: number, height: number, dx = 0, dy = 0): void {
    const old = this.ctx.getImageData(0, 0, this.width, this.height)
    this.canvas.width = Math.max(1, width); this.canvas.height = Math.max(1, height)
    this.width = width; this.height = height
    this.ctx.putImageData(old, dx, dy)
    this.texture.source.resize(this.canvas.width, this.canvas.height)
    this.refresh()
    this.dirty = true
  }

  thumbnail(size = 48): string {
    const c = document.createElement('canvas')
    const s = Math.min(size / this.width, size / this.height, 1)
    c.width = Math.max(1, Math.round(this.width * s)); c.height = Math.max(1, Math.round(this.height * s))
    c.getContext('2d')!.drawImage(this.canvas, 0, 0, c.width, c.height)
    return c.toDataURL('image/png')
  }

  destroy(): void { this.texture.destroy(true) }
}

/** A canvas whose alpha is the selection/mask value (RGB white), for destination-out / source-in masking. */
export function selectionAlphaCanvas(src: LayerPixels): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = src.width; c.height = src.height
  const img = src.ctx.getImageData(0, 0, src.width, src.height)
  const d = img.data
  for (let i = 0; i < d.length; i += 4) { d[i + 3] = d[i]; d[i] = d[i + 1] = d[i + 2] = 255 }
  c.getContext('2d')!.putImageData(img, 0, 0)
  return c
}

/** A soft round dab: radial gradient from the colour at full alpha to transparent at the edge (hardness 0–1). */
export function makeDab(size: number, hardness: number, color: string, alpha: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  const d = Math.max(1, Math.ceil(size))
  c.width = d; c.height = d
  const ctx = c.getContext('2d')!
  const r = d / 2
  const g = ctx.createRadialGradient(r, r, 0, r, r, r)
  const inner = Math.max(0, Math.min(0.999, hardness))
  const [cr, cg, cb] = hexToRgb(color)
  g.addColorStop(0, `rgba(${cr},${cg},${cb},${alpha})`)
  g.addColorStop(inner, `rgba(${cr},${cg},${cb},${alpha})`)
  g.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)
  ctx.fillStyle = g
  ctx.fillRect(0, 0, d, d)
  return c
}

export function hexToRgb(hex: string): [number, number, number] {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim())
  if (!m) return [0, 0, 0]
  const n = parseInt(m[1], 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
