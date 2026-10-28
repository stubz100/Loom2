// D154: the PSD type layer written beside a text layer's pixels.
import { describe, expect, it } from 'vitest'
import type { Node } from './editorStore'
import { psdTextData } from './psdExport'
import { TEXT_DEFAULTS } from './textRaster'

describe('psdTextData (D154)', () => {
  it('names the font by its face, puts the first baseline where the rasteriser drew it, counts tracking in thousandths of an em', () => {
    const n: Node = { kind: 'raster', id: 't', name: 'Title', opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 100, y: 50, w: 200, h: 60,
      text: { ...TEXT_DEFAULTS, content: 'Title', font: 'Courier Prime', size: 40, colour: '#ff8000', align: 'center', leading: 1.5, tracking: 4, weight: 'bold', italic: true, outline: { width: 3, colour: '#000000' } } }
    const d = psdTextData(n)
    expect(d.text).toBe('Title')
    expect(d.transform).toEqual([1, 0, 0, 1, 100 + 5, 50 + 5 + 32])        // pad = ceil(3 / 2 + max(2, 40 × 0.08)) = ceil(4.7) = 5
    expect(d.style).toMatchObject({ font: { name: 'CourierPrime-BoldItalic' }, fontSize: 40, fillColor: { r: 255, g: 128, b: 0 }, autoLeading: false, leading: 60, tracking: 100, strokeFlag: true, strokeColor: { r: 0, g: 0, b: 0 }, outlineWidth: 3 })
    expect(d.paragraphStyle).toEqual({ justification: 'center' })
  })
  it('without an outline the stroke fields stay out', () => {
    const n: Node = { kind: 'raster', id: 't', name: 'a', opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 10, h: 10, text: { ...TEXT_DEFAULTS, content: 'a', size: 20 } }
    const d = psdTextData(n)
    expect(d.style).not.toHaveProperty('strokeFlag')
    expect(d.transform).toEqual([1, 0, 0, 1, 2, 2 + 16])
  })
})
