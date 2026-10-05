// PSD export through ag-psd (10 §7): layers, groups, masks, blend modes, opacity, clipping, 8-bit. Adjustment
// and filter layers have no raster of their own in the editor; they are skipped with a warning (10 §15).
import { writePsd, type Layer, type Psd } from 'ag-psd'
import type { DocumentStack, Node } from './editorStore'
import type { LayerPixels } from './layerPixels'

const PSD_BLEND: Record<string, NonNullable<Layer['blendMode']>> = {
  normal: 'normal', dissolve: 'dissolve', darken: 'darken', multiply: 'multiply', 'color-burn': 'color burn', 'linear-burn': 'linear burn', lighten: 'lighten', screen: 'screen',
  'color-dodge': 'color dodge', 'linear-dodge': 'linear dodge', overlay: 'overlay', 'soft-light': 'soft light', 'hard-light': 'hard light', 'vivid-light': 'vivid light',
  'linear-light': 'linear light', 'pin-light': 'pin light', 'hard-mix': 'hard mix', difference: 'difference', exclusion: 'exclusion', subtract: 'subtract', divide: 'divide',
  hue: 'hue', saturation: 'saturation', color: 'color', luminosity: 'luminosity',
}

export function buildPsd(doc: DocumentStack, pixels: Map<string, LayerPixels>, masks: Map<string, LayerPixels>, merged?: HTMLCanvasElement): { bytes: ArrayBuffer; skipped: string[] } {
  const skipped: string[] = []
  const conv = (nodes: Node[]): Layer[] => {
    const out: Layer[] = []
    for (let i = nodes.length - 1; i >= 0; i--) {              // ORA is top-first, PSD children are bottom-first
      const n = nodes[i]
      const base: Layer = { name: n.name, opacity: n.opacity, blendMode: PSD_BLEND[n.blend] ?? 'normal', hidden: !n.visible, clipping: n.clip, transparencyProtected: n.locked }
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
        out.push({ ...base, left: n.x ?? 0, top: n.y ?? 0, right: (n.x ?? 0) + lp.width, bottom: (n.y ?? 0) + lp.height, canvas: lp.canvas })
      } else if (n.kind === 'group') {
        out.push({ ...base, opened: true, children: conv(n.children ?? []) })
      } else {
        skipped.push(`${n.name} (${n.kind} ${n.type ?? ''})`.trim())
      }
    }
    return out
  }
  const psd: Psd = { width: doc.w, height: doc.h, children: conv(doc.layers), canvas: merged }
  return { bytes: writePsd(psd, { generateThumbnail: true }), skipped }
}
