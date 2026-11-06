// The review of 2026-11-06 (register K1–K96): K7 — merge down covers both layers (it was drawn into the lower layer's own canvas, cropping
// the top to it), refuses a locked lower layer and a hidden top, keeps a linked mask in place and leaves no text block over merged pixels.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSession } from '../../store/session'

const draws: { into: string; x: number; y: number }[] = []
vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  let seq = 0
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1; readonly name = `px${seq++}`
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx: CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) {
      this.width = width; this.height = height; this.grey = grey
      const self = this  // eslint-disable-line @typescript-eslint/no-this-alias
      this.ctx = { save: () => undefined, restore: () => undefined, drawImage: (_src: unknown, x: number, y: number) => { draws.push({ into: self.name, x, y }) } } as unknown as CanvasRenderingContext2D
    }
    snapshotAll() { return [] }
    refresh() { this.version++ }
    destroy() { /* nothing on the GPU */ }
  }
  return { ...real, LayerPixels: FakePixels }
})

import { useEditor, type DocumentStack, type Node } from './editorStore'
import { LayerPixels } from './layerPixels'

const raster = (id: string, x: number, y: number, w: number, h: number, extra: Partial<Node> = {}): Node =>
  ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x, y, w, h, ...extra }) as Node
const open = (top: Node, below: Node) => {
  const doc = { schema_version: 1, id: 'doc_1', name: 'Doc', w: 200, h: 100, background: 'transparent', revision: 1, source_asset_id: null, meta: {},
    layers: [top, below] } as unknown as DocumentStack
  useEditor.setState({ doc, pixels: new Map([[top.id, new LayerPixels(top.w ?? 0, top.h ?? 0)], [below.id, new LayerPixels(below.w ?? 0, below.h ?? 0)]]),
    masks: new Map(), history: [], future: [], docDirty: false })
}

describe('K7 merge down', () => {
  beforeEach(() => { draws.length = 0; useSession.setState({ toasts: [] }) })

  it('covers the union of both layers, the lower layer keeping its place in the stack', () => {
    open(raster('top', 100, 0, 50, 50), raster('below', 0, 0, 20, 20, { opacity: 0.5 }))
    useEditor.getState().mergeDown('top')
    const { doc, pixels } = useEditor.getState()
    expect(doc!.layers.map((n) => n.id)).toEqual(['below'])
    expect(doc!.layers[0]).toMatchObject({ x: 0, y: 0, w: 150, h: 50, opacity: 0.5 })      // the top's area kept, the lower layer's opacity its own
    const out = pixels.get('below') as unknown as { width: number; height: number; name: string }
    expect([out.width, out.height]).toEqual([150, 50])
    expect(draws.filter((d) => d.into === out.name)).toEqual([{ into: out.name, x: 0, y: 0 }, { into: out.name, x: 100, y: 0 }])
    useEditor.getState().undo()
    expect(useEditor.getState().doc!.layers.map((n) => n.id)).toEqual(['top', 'below'])
  })

  it('refuses a locked lower layer and a hidden top', () => {
    open(raster('top', 0, 0, 10, 10), raster('below', 0, 0, 10, 10, { locked: true }))
    useEditor.getState().mergeDown('top')
    expect(useEditor.getState().doc!.layers).toHaveLength(2)
    open(raster('top', 0, 0, 10, 10, { visible: false }), raster('below', 0, 0, 10, 10))
    useEditor.getState().mergeDown('top')
    expect(useEditor.getState().doc!.layers).toHaveLength(2)
    expect(useSession.getState().toasts.map((t) => t.text)).toEqual([expect.stringContaining('locked'), expect.stringContaining('hidden')])
  })

  it('keeps a linked mask where it was and drops a text block', () => {
    const mask = { enabled: true, linked: true, x: 2, y: 3, density: 1, feather: 0 }
    open(raster('top', 0, 0, 10, 10), raster('below', 10, 20, 10, 10, { mask, text: { text: 'Title' } as unknown as Node['text'] }))
    useEditor.getState().mergeDown('top')
    const n = useEditor.getState().doc!.layers[0]
    expect([n.x, n.y]).toEqual([0, 0])
    expect([n.mask!.x, n.mask!.y]).toEqual([12, 23])                                         // 10 + 2, 20 + 3: the same place on the canvas
    expect(n.text ?? null).toBeNull()
  })
})
