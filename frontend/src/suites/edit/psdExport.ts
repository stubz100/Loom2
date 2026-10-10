// PSD export through ag-psd (10 §7): layers, groups (pass-through or isolated), masks, blend modes, opacity, fill, clipping, locks,
// adjustment layers, 8-bit. D41: adjustment layers are written as Photoshop adjustment layers (ag-psd `adjustment` records) with their
// mask, clip, blend and opacity. Levels, Curves, Exposure and Invert carry over exactly; Hue/Saturation (master), Colour Balance,
// Brightness/Contrast (legacy) and Black & White keep their settings, but Photoshop's maths for them differ from compose.py's, so
// those look slightly different there (the export reports them). Filter layers have no Photoshop equivalent and are skipped with
// a warning (10 §15); the merged image still contains them.
import { writePsd, type AdjustmentLayer, type Layer, type Psd } from 'ag-psd'
import type { DocumentStack, Node } from './editorStore'
import type { LayerPixels } from './layerPixels'

const PSD_BLEND: Record<string, NonNullable<Layer['blendMode']>> = {
  normal: 'normal', dissolve: 'dissolve', darken: 'darken', multiply: 'multiply', 'color-burn': 'color burn', 'linear-burn': 'linear burn', lighten: 'lighten', screen: 'screen',
  'color-dodge': 'color dodge', 'linear-dodge': 'linear dodge', overlay: 'overlay', 'soft-light': 'soft light', 'hard-light': 'hard light', 'vivid-light': 'vivid light',
  'linear-light': 'linear light', 'pin-light': 'pin light', 'hard-mix': 'hard mix', difference: 'difference', exclusion: 'exclusion', subtract: 'subtract', divide: 'divide',
  hue: 'hue', saturation: 'saturation', color: 'color', luminosity: 'luminosity', 'pass-through': 'pass through',
}

// D41: ag-psd 31.0.2 writes the Levels block ('levl') as a version word plus 63 records — the 632 bytes Photoshop uses, but
// without the 'Lvls' header Photoshop puts after the 29th record, so psd-tools refuses the file. Photoshop's layout of those
// 632 bytes: version 2, 29 records, 'Lvls', version 3, a total count of 62, the remaining 33 records, 2 bytes of padding
// (the format PhotoCraft's crates/io/src/adjust_map.rs reads). Rewrite the tail of each block in place; nothing moves.
export function fixLevelsBlocks(bytes: ArrayBuffer): number {
  const u8 = new Uint8Array(bytes)
  const view = new DataView(bytes)
  const sig = [0x38, 0x42, 0x49, 0x4d, 0x6c, 0x65, 0x76, 0x6c]          // '8BIMlevl'
  let fixed = 0
  for (let i = 0; i + 12 + 632 <= u8.length; i++) {
    if (u8[i] !== 0x38 || !sig.every((c, k) => u8[i + k] === c)) continue
    const at = i + 12
    if (view.getUint32(i + 8) < 632 || view.getUint16(at) !== 2) continue
    let o = at + 2 + 29 * 10
    if (u8[o] === 0x4c && u8[o + 1] === 0x76) continue                    // already has 'Lvls'
    for (const c of [0x4c, 0x76, 0x6c, 0x73]) u8[o++] = c                 // 'Lvls'
    view.setUint16(o, 3); o += 2
    view.setUint16(o, 62); o += 2
    for (let r = 0; r < 33; r++, o += 10) { view.setInt16(o, 0); view.setInt16(o + 2, 255); view.setInt16(o + 4, 0); view.setInt16(o + 6, 255); view.setInt16(o + 8, 100) }
    view.setUint16(o, 0)
    fixed++
  }
  return fixed
}

/** Adjustment types whose Photoshop rendering differs from loom2's (same settings, different maths). */
const APPROXIMATE = new Set(['hue_saturation', 'color_balance', 'brightness_contrast', 'black_white'])

// Photoshop's default hue ranges for the six colour bands (a, b, c, d in degrees)
const HUE_RANGES: [string, number, number, number, number][] = [
  ['reds', 315, 345, 15, 45], ['yellows', 15, 45, 75, 105], ['greens', 75, 105, 135, 165],
  ['cyans', 135, 165, 195, 225], ['blues', 195, 225, 255, 285], ['magentas', 255, 285, 315, 345],
]

const num = (p: Record<string, unknown>, k: string, d: number) => { const v = Number(p[k]); return Number.isFinite(v) ? v : d }
const points = (v: unknown) => (Array.isArray(v) ? (v as [number, number][]).map(([a, b]) => ({ input: Math.round(Number(a)), output: Math.round(Number(b)) })) : undefined)
const triplet = (v: unknown) => { const t = Array.isArray(v) ? (v as number[]) : [0, 0, 0]; return { cyanRed: Math.round(Number(t[0] ?? 0)), magentaGreen: Math.round(Number(t[1] ?? 0)), yellowBlue: Math.round(Number(t[2] ?? 0)) } }

/** loom2 adjustment params → the Photoshop adjustment record (compose.py's parameter meanings, 10 §3). */
export function psdAdjustment(type: string, p: Record<string, unknown>): AdjustmentLayer | null {
  switch (type) {
    case 'levels': {
      const ch = { shadowInput: num(p, 'in_black', 0), highlightInput: num(p, 'in_white', 255), shadowOutput: num(p, 'out_black', 0), highlightOutput: num(p, 'out_white', 255), midtoneInput: num(p, 'gamma', 1) }
      return { type: 'levels', rgb: ch }
    }
    case 'curves': return { type: 'curves', rgb: points(p.rgb), red: points(p.r), green: points(p.g), blue: points(p.b) }
    case 'exposure': return { type: 'exposure', exposure: num(p, 'exposure', 0), offset: num(p, 'offset', 0), gamma: num(p, 'gamma', 1) }
    case 'invert': return { type: 'invert' }
    case 'hue_saturation': {
      const adj: Record<string, unknown> = { type: 'hue/saturation', master: { a: 0, b: 0, c: 0, d: 0, hue: Math.round(num(p, 'hue', 0)), saturation: Math.round(num(p, 'saturation', 0)), lightness: Math.round(num(p, 'lightness', 0)) } }
      for (const [k, a, b, c, d] of HUE_RANGES) adj[k] = { a, b, c, d, hue: 0, saturation: 0, lightness: 0 }
      return adj as unknown as AdjustmentLayer
    }
    case 'color_balance': return { type: 'color balance', shadows: triplet(p.shadows), midtones: triplet(p.midtones), highlights: triplet(p.highlights), preserveLuminosity: false }
    case 'brightness_contrast': return { type: 'brightness/contrast', brightness: Math.round(num(p, 'brightness', 0)), contrast: Math.round(num(p, 'contrast', 0)), useLegacy: true }
    case 'black_white': return { type: 'black & white', reds: Math.round(num(p, 'r', 40)), yellows: 60, greens: Math.round(num(p, 'g', 60)), cyans: 60, blues: Math.round(num(p, 'b', 20)), magentas: 80 }
    default: return null
  }
}

export function buildPsd(doc: DocumentStack, pixels: Map<string, LayerPixels>, masks: Map<string, LayerPixels>, merged?: HTMLCanvasElement): { bytes: ArrayBuffer; skipped: string[]; approximate: string[] } {
  const skipped: string[] = []
  const approximate: string[] = []
  const conv = (nodes: Node[]): Layer[] => {
    const out: Layer[] = []
    for (let i = nodes.length - 1; i >= 0; i--) {              // ORA is top-first, PSD children are bottom-first
      const n = nodes[i]
      const base: Layer = { name: n.name, opacity: n.opacity, blendMode: PSD_BLEND[n.blend] ?? 'normal', hidden: !n.visible, clipping: n.clip }
      if (n.locked) base.protected = { transparency: true, composite: true, position: true }   // the editor's lock blocks paint and move: Lock All
      else if (n.lock_alpha) base.protected = { transparency: true }                              // D50
      if (n.mask) {
        const m = masks.get(n.id)
        if (m) {
          const left = (n.mask.linked ? (n.x ?? 0) : 0) + n.mask.x, top = (n.mask.linked ? (n.y ?? 0) : 0) + n.mask.y
          base.mask = { canvas: m.canvas, left, top, right: left + m.width, bottom: top + m.height, disabled: !n.mask.enabled, positionRelativeToLayer: false }
        }
      }
      if (n.kind === 'raster') {
        const lp = pixels.get(n.id)
        if (!lp) continue
        out.push({ ...base, fillOpacity: n.fill ?? 1, left: n.x ?? 0, top: n.y ?? 0, right: (n.x ?? 0) + lp.width, bottom: (n.y ?? 0) + lp.height, canvas: lp.canvas })
      } else if (n.kind === 'group') {
        // compose.py's rule: pass-through when flagged and Normal / Pass Through and not clipped; otherwise isolated in its mode
        const passthrough = (n.passthrough ?? true) && (n.blend === 'normal' || n.blend === 'pass-through') && !n.clip
        out.push({ ...base, blendMode: passthrough ? 'pass through' : (PSD_BLEND[n.blend === 'pass-through' ? 'normal' : n.blend] ?? 'normal'), opened: true, children: conv(n.children ?? []) })
      } else if (n.kind === 'adjustment') {
        const adjustment = psdAdjustment(n.type ?? '', n.params ?? {})
        if (!adjustment) { skipped.push(`${n.name} (adjustment ${n.type ?? ''})`); continue }
        if (APPROXIMATE.has(n.type ?? '')) approximate.push(`${n.name} (${(n.type ?? '').replace('_', ' ')})`)
        out.push({ ...base, adjustment })
      } else {
        skipped.push(`${n.name} (${n.kind} ${n.type ?? ''})`.trim())
      }
    }
    return out
  }
  const psd: Psd = { width: doc.w, height: doc.h, children: conv(doc.layers), canvas: merged }
  const bytes = writePsd(psd, { generateThumbnail: true })
  fixLevelsBlocks(bytes)
  return { bytes, skipped, approximate }
}
