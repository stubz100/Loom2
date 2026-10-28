// D154: text layers in the editor store — a raster node with a `text` block whose pixels are its rasterisation; a field gesture is one
// undo row; the inline editor's apply / cancel; Rasterize text. The rasteriser is replaced by the pure layout (jsdom has no 2D canvas).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findNode, useEditor, type DocumentStack, type Node } from './editorStore'
import { layoutText, TEXT_DEFAULTS, type TextBlock } from './textRaster'

vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1; destroyed = false
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx = { drawImage: () => undefined } as unknown as CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) { this.width = width; this.height = height; this.grey = grey }
    static fromRaw(width: number, height: number, _bytes: Uint8Array, channels: 1 | 4) { return new FakePixels(width, height, channels === 1) }
    refresh() { this.version++ }
    destroy() { this.destroyed = true }
  }
  return { ...real, LayerPixels: FakePixels }
})
vi.mock('./textRaster', async (importOriginal) => {
  const real = await importOriginal<typeof import('./textRaster')>()
  return { ...real, rasterizeText: (t: TextBlock) => { const layout = real.layoutText(t, (s) => s.length * 10); return { canvas: {} as HTMLCanvasElement, w: layout.w, h: layout.h, layout } } }
})

const raster = (id: string, extra: Partial<Node> = {}): Node => ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 64, h: 64, ...extra })
const stack = (layers: Node[]): DocumentStack => ({ schema_version: 1, id: 'doc_t', name: 't', w: 320, h: 200, background: '#000', source_asset_id: null, created_at: '', saved_at: null, revision: 1, layers, has_selection: false, meta: {} })
const ed = () => useEditor.getState()
const textOf = (id: string) => findNode(ed().doc, id)!.text!

beforeEach(() => {
  useEditor.setState({ doc: stack([raster('bg')]), activeId: 'bg', history: [], future: [], pixels: new Map(), masks: new Map(), editingText: null, revision: 0,
    textDefaults: { font: 'Inter', size: 20, colour: '#ffffff', weight: 'normal', italic: false, outline: null } })
})

describe('text layers (D154)', () => {
  it('addTextLayer puts a raster node with the block above the active layer, named by its words, sized by the layout, with pixels', () => {
    const n = ed().addTextLayer({ x: 10.4, y: 20.6 }, null, { content: 'Scene 1' })!
    expect(n.kind).toBe('raster')
    expect(n.text).toMatchObject({ ...TEXT_DEFAULTS, size: 20, content: 'Scene 1', box: null })
    const l = layoutText(n.text!, (s) => s.length * 10)
    expect([n.x, n.y, n.w, n.h, n.name]).toEqual([10, 21, l.w, l.h, 'Scene 1'])
    expect(ed().doc!.layers.map((x) => x.id)).toEqual([n.id, 'bg'])
    expect(ed().pixels.get(n.id)!.width).toBe(l.w)
    expect(ed().history.map((e) => e.label)).toEqual(['add Scene 1'])
    const boxed = ed().addTextLayer({ x: 0, y: 0 }, [120, 60], { content: 'one two three' })!
    expect([boxed.w, boxed.h, boxed.text!.box]).toEqual([120, 60, [120, 60]])
  })
  it('a field gesture re-rasterises on every move and leaves one undo row; undo brings the block, the size and the old canvas back', () => {
    const n = ed().addTextLayer({ x: 0, y: 0 }, null, { content: 'ab' })!
    const lp0 = ed().pixels.get(n.id)!
    const w0 = n.w!
    ed().setText(n.id, {}, 'start')
    ed().setText(n.id, { size: 30 }, 'move')
    ed().setText(n.id, { size: 40 }, 'move')
    expect(ed().history).toHaveLength(1)                                   // still only the add
    expect(ed().pixels.get(n.id)).not.toBe(lp0)
    ed().setText(n.id, {}, 'end', 'text size')
    expect(ed().history.map((e) => e.label)).toEqual(['add ab', 'text size'])
    expect(textOf(n.id).size).toBe(40)
    expect(findNode(ed().doc, n.id)!.w).toBeGreaterThan(w0)
    expect(ed().history[1].swap?.lp).toBe(lp0)
    ed().undo()
    expect(textOf(n.id).size).toBe(20)
    expect(findNode(ed().doc, n.id)!.w).toBe(w0)
    expect(ed().pixels.get(n.id)).toBe(lp0)
    ed().redo()
    expect(textOf(n.id).size).toBe(40)
  })
  it('a one-shot change is its own row; an end with nothing changed adds none', () => {
    const n = ed().addTextLayer({ x: 0, y: 0 }, null, { content: 'ab' })!
    ed().setText(n.id, { align: 'center' }, undefined, 'text align')
    ed().setText(n.id, {}, 'end', 'edit text')
    expect(ed().history.map((e) => e.label)).toEqual(['add ab', 'text align'])
    expect(textOf(n.id).align).toBe('center')
  })
  it('the auto name follows the words until the layer is renamed', () => {
    const n = ed().addTextLayer({ x: 0, y: 0 }, null, { content: 'first' })!
    ed().setText(n.id, { content: 'second words' })
    expect(findNode(ed().doc, n.id)!.name).toBe('second words')
    ed().updateNode(n.id, { name: 'Title' })
    ed().setText(n.id, { content: 'third' })
    expect(findNode(ed().doc, n.id)!.name).toBe('Title')
  })
  it('the inline editor: apply keeps the typed text as one row; cancel reverts; an empty new layer is dropped', () => {
    const n = ed().addTextLayer({ x: 0, y: 0 })!                           // the tool's click: an empty block
    ed().beginTextEdit(n.id)
    expect(ed().editingText).toBe(n.id)
    ed().setText(n.id, { content: 'S' }, 'move'); ed().setText(n.id, { content: 'Sc' }, 'move'); ed().setText(n.id, { content: 'Scene' }, 'move')
    ed().endTextEdit(true)
    expect(ed().editingText).toBeNull()
    expect(textOf(n.id).content).toBe('Scene')
    expect(ed().history.map((e) => e.label)).toEqual(['add Text', 'edit text'])
    ed().beginTextEdit(n.id)
    ed().setText(n.id, { content: 'Scene 2' }, 'move')
    ed().endTextEdit(false)
    expect(textOf(n.id).content).toBe('Scene')                             // the cancel reverted it, no row
    expect(ed().history).toHaveLength(2)
    const empty = ed().addTextLayer({ x: 5, y: 5 })!
    ed().beginTextEdit(empty.id)
    ed().endTextEdit(false)
    expect(findNode(ed().doc, empty.id)).toBeNull()                         // nothing written: the layer goes
  })
  it('Rasterize text drops the block and keeps the pixels; undo brings the block back', () => {
    const n = ed().addTextLayer({ x: 0, y: 0 }, null, { content: 'ab' })!
    const lp = ed().pixels.get(n.id)
    ed().rasterizeTextLayer(n.id)
    expect(findNode(ed().doc, n.id)!.text).toBeNull()
    expect(ed().pixels.get(n.id)).toBe(lp)
    expect(ed().history.map((e) => e.label)).toEqual(['add ab', 'rasterize text'])
    ed().undo()
    expect(findNode(ed().doc, n.id)!.text?.content).toBe('ab')
  })
})
