// D52: a layer mask as it renders — feathered (a Gaussian of σ = feather px as three box passes, selectionOps.gaussian, rounded to
// 8 bits) and with density (1 − density·(1 − v), rounded) — in exactly the order and rounding of compose.py derived_mask, so the
// canvas and the orchestrator's flatten agree. The raw mask stays what the tools paint; the derived one is cached per mask canvas and
// recomputed only when the raw pixels (LayerPixels.version) or the parameters change — and then only around what a stroke touched: the
// damaged rect plus the blur's reach (3σ + 3 px bounds the three box radii), uploaded as a partial texture update.
import { LayerPixels, type Rect } from './layerPixels'
import { gaussian } from './selectionOps'

export interface MaskParams { density?: number; feather?: number; default?: number }

const density = (m: MaskParams) => Math.min(1, Math.max(0, m.density ?? 1))
const feather = (m: MaskParams) => Math.max(0, m.feather ?? 0)

/** True when the mask renders differently from its raw pixels. */
export const maskParamsActive = (m: MaskParams): boolean => density(m) < 1 || feather(m) > 0

/** The derived values of raw mask values (one byte per pixel). */
export function derivedValues(v: Uint8Array, w: number, h: number, m: MaskParams): Uint8Array {
  const f = feather(m), d = density(m)
  const out = f > 0 ? gaussian(v, w, h, f) : v.slice()
  if (d < 1) for (let i = 0; i < out.length; i++) out[i] = Math.round(255 - d * (255 - out[i]))
  return out
}

const cache = new WeakMap<LayerPixels, { version: number; density: number; feather: number; out: LayerPixels }>()

/** The mask to render: `raw` itself when the parameters are neutral, otherwise a cached derived grey canvas (same size and place). */
export function derivedMask(raw: LayerPixels, m: MaskParams): LayerPixels {
  if (!maskParamsActive(m)) return raw
  const d = density(m), f = feather(m)
  const c = cache.get(raw)
  const damage = raw.takeDamage()
  if (c && c.density === d && c.feather === f && c.out.width === raw.width && c.out.height === raw.height) {
    if (c.version === raw.version) return c.out
    if (damage && damage !== 'all') { updateRegion(raw, c.out, damage, m); c.version = raw.version; return c.out }
  }
  const v = derivedValues(raw.toRaw(), raw.width, raw.height, m)
  const out = c && c.out.width === raw.width && c.out.height === raw.height ? c.out : new LayerPixels(raw.width, raw.height, true)
  if (c && c.out !== out) c.out.destroy()
  const img = out.ctx.createImageData(raw.width, raw.height)
  for (let i = 0, j = 0; i < v.length; i++, j += 4) { img.data[j] = img.data[j + 1] = img.data[j + 2] = v[i]; img.data[j + 3] = 255 }
  out.ctx.putImageData(img, 0, 0)
  out.refresh()
  cache.set(raw, { version: raw.version, density: d, feather: f, out })
  return out
}

/** D54: the value a mask reads outside its extent — its default, through the density (compose.py's rounding). */
export const outsideValue = (m: MaskParams): number => Math.round(255 - density(m) * (255 - (m.default ?? 0)))

/** D54: a w×h canvas whose alpha is the mask as it renders over the region at document (rx, ry) — the derived mask where it has
 * pixels, its default elsewhere; `mx`, `my` is the mask's document position. For baking a mask into pixels (Apply, merge down). */
export function maskAlphaCanvas(raw: LayerPixels, m: MaskParams, mx: number, my: number, rx: number, ry: number, w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = Math.max(1, w); c.height = Math.max(1, h)
  const ctx = c.getContext('2d')!
  ctx.fillStyle = `rgba(255, 255, 255, ${outsideValue(m) / 255})`; ctx.fillRect(0, 0, w, h)
  ctx.clearRect(mx - rx, my - ry, raw.width, raw.height)
  const d = derivedMask(raw, m)
  const img = d.ctx.getImageData(0, 0, d.width, d.height)
  for (let i = 0; i < img.data.length; i += 4) { img.data[i + 3] = d.grey && img.data[i + 3] !== 255 ? Math.round((img.data[i] * img.data[i + 3]) / 255) : img.data[i]; img.data[i] = img.data[i + 1] = img.data[i + 2] = 255 }
  const t = document.createElement('canvas'); t.width = d.width; t.height = d.height
  t.getContext('2d')!.putImageData(img, 0, 0)
  ctx.drawImage(t, mx - rx, my - ry)
  return c
}

/** Re-derive around a changed rect `r`: the derived values change up to the blur's reach beyond it (the output region), and those
 * need the raw values up to the reach beyond that (the crop, exact inside the output; at the canvas edges the crop's clamping is the
 * canvas's own). Writes and uploads the output region only. */
function updateRegion(raw: LayerPixels, out: LayerPixels, r: Rect, m: MaskParams): void {
  const W = raw.width, H = raw.height
  const pad = feather(m) > 0 ? Math.ceil(3 * feather(m) + 3) : 0
  const x0 = Math.max(0, Math.floor(r.x0) - pad), y0 = Math.max(0, Math.floor(r.y0) - pad), x1 = Math.min(W, Math.ceil(r.x1) + pad), y1 = Math.min(H, Math.ceil(r.y1) + pad)
  if (x1 <= x0 || y1 <= y0) return
  const cx0 = Math.max(0, x0 - pad), cy0 = Math.max(0, y0 - pad), cx1 = Math.min(W, x1 + pad), cy1 = Math.min(H, y1 + pad)
  const cw = cx1 - cx0, ch = cy1 - cy0
  const v = derivedValues(raw.greyValues(cx0, cy0, cw, ch), cw, ch, m)
  const w = x1 - x0, h = y1 - y0
  const img = out.ctx.createImageData(w, h)
  for (let yy = 0; yy < h; yy++) for (let xx = 0; xx < w; xx++) {
    const g = v[(yy + y0 - cy0) * cw + (xx + x0 - cx0)], j = (yy * w + xx) * 4
    img.data[j] = img.data[j + 1] = img.data[j + 2] = g; img.data[j + 3] = 255
  }
  out.ctx.putImageData(img, x0, y0)
  out.refreshRect(x0, y0, x1, y1)
}
