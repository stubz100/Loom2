// The review of 2026-11-06 — the 2D editor's items: K64 (a pixel operation on a text layer rasterises it first, asked), K66 (the histogram
// and the thumbnails keyed on what they are made of), K67 (history's byte budget), K94 (a late candidate re-adds no discarded one) and K116
// (an AI result keeps the active layer someone chose, undo puts the active layer back, a stale candidate strip, a layer under a free
// transform, the tools' pointer and footprint). LayerPixels is a fake (jsdom has no 2D canvas); the orchestrator a stubbed fetch.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'

vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1; destroyed = false
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx = { drawImage: () => undefined, save: () => undefined, restore: () => undefined, clearRect: () => undefined, fillRect: () => undefined } as unknown as CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) { this.width = width; this.height = height; this.grey = grey }
    static fromRaw(width: number, height: number, _bytes: Uint8Array, channels: 1 | 4) { return new FakePixels(width, height, channels === 1) }
    refresh() { this.version++ }
    beginStroke() { /* tiles */ }
    touch() { /* tiles */ }
    endStroke() { return [{ x: 0, y: 0, data: { width: this.width, height: this.height } }] }
    restore() { this.version++; return [] }
    thumbnail() { return 'data:' }
    destroy() { this.destroyed = true }
  }
  return { ...real, LayerPixels: FakePixels }
})

import { candidatesIn, findNode, historyBytes, trimHistory, useEditor, type DocumentStack, type HistoryEntry, type Node } from './editorStore'
import { cachedThumbnail, LayerPixels } from './layerPixels'
import { histogramKey } from './propsEditors'
import { toolCursor, toolFootprint } from './tools'

const raster = (id: string, extra: Partial<Node> = {}): Node => ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 64, h: 64, ...extra })
const group = (id: string, children: Node[], extra: Partial<Node> = {}): Node => ({ kind: 'group', id, name: id, opacity: 1, blend: 'pass-through', visible: true, locked: false, clip: false, mask: null, children, ...extra })
const stack = (layers: Node[], extra: Partial<DocumentStack> = {}): DocumentStack => ({ schema_version: 1, id: 'doc_1', name: 'Doc', w: 256, h: 256, background: 'transparent', source_asset_id: null,
  created_at: '', saved_at: null, revision: 3, layers, has_selection: false, meta: {}, ...extra })
const ed = () => useEditor.getState()
const TEXT = { content: 'Title', font: 'Inter', size: 20, colour: '#fff', weight: 'normal', italic: false, outline: null, align: 'left', leading: 1.2, tracking: 0, box: null } as unknown as Node['text']
const open = (layers: Node[], activeId: string | null) => {
  const pixels = new Map<string, LayerPixels>()
  const add = (ns: Node[]) => ns.forEach((n) => { if (n.kind === 'raster') pixels.set(n.id, new LayerPixels(n.w ?? 64, n.h ?? 64)); if (n.children) add(n.children) })
  add(layers)
  useEditor.setState({ doc: stack(layers), pixels, masks: new Map(), history: [], future: [], selection: null, transform: null, candidates: null, candPreview: null, activeId, selectedIds: activeId ? [activeId] : [], editingMask: false, docDirty: false, editingText: null, revision: 0 })
}
let answer = true
beforeEach(() => {
  answer = true
  useSession.setState({ toasts: [], askConfirm: vi.fn(async () => answer) } as never)
})

describe('K67 history keeps a byte budget besides its 200 entries', () => {
  const entry = (label: string, w: number, h: number): HistoryEntry => ({ label, layerId: 'a', kind: 'image', tiles: [{ x: 0, y: 0, data: { width: w, height: h } as ImageData }], at: 0 })
  it('counts the tiles and the canvases an entry swaps', () => {
    const e = { ...entry('t', 10, 10), swap: { layerId: 'a', lp: { width: 4, height: 4 } as LayerPixels, mask: { width: 2, height: 2 } as LayerPixels } }
    expect(historyBytes(e)).toBe(400 + 64 + 16)
  })
  it('drops the oldest past the budget, never the newest', () => {
    const h = ['a', 'b', 'c', 'd'].map((l) => entry(l, 16, 16))       // 1 KiB each
    const t = trimHistory(h, 200, 2048 + 100)
    expect(t.kept.map((e) => e.label)).toEqual(['c', 'd'])
    expect(t.dropped.map((e) => e.label)).toEqual(['a', 'b'])
    expect(trimHistory([entry('huge', 4096, 4096)], 200, 10).kept).toHaveLength(1)
    expect(trimHistory(h, 3, 1e9).kept.map((e) => e.label)).toEqual(['b', 'c', 'd'])
  })
  it('pushHistory keeps 200 entries at most', () => {
    open([raster('a')], 'a')
    for (let i = 0; i < 205; i++) ed().pushHistory({ label: `s${i}`, layerId: 'a', kind: 'image', tiles: [], at: i * 10_000 })
    expect(ed().history).toHaveLength(200)
    expect(ed().history[0].label).toBe('s5')
  })
})

describe('K116 undo puts the active layer back', () => {
  it('undoing a new layer goes back to the layer that was active, not the top one; redo to the new one', () => {
    open([raster('top'), raster('mid'), raster('low')], 'mid')
    const n = ed().addLayer('raster')!
    expect(ed().activeId).toBe(n.id)
    ed().undo()
    expect(ed().activeId).toBe('mid')
    ed().redo()
    expect(ed().activeId).toBe(n.id)
  })
  it('without a record, the nearest layer below the gone one', () => {
    open([raster('top'), raster('mid'), raster('low')], 'mid')
    ed().pushHistory({ label: 'x', layerId: 'mid', kind: 'image', tiles: [], stack: stack([raster('top'), raster('low')]), at: 0 })
    ed().undo()
    expect(ed().activeId).toBe('low')
  })
})

describe('K116 the candidate strip follows undo; K94 a late candidate re-adds no discarded one', () => {
  it('an undone pick brings the strip back; a strip naming a group the stack lacks goes', () => {
    open([group('AI inpaint', [raster('c1'), raster('c2', { visible: false })], { id: 'grp' }), raster('a')], 'c1')
    useEditor.setState({ candidates: { group: 'grp', ids: ['c1', 'c2'] } })
    ed().pickCandidate('c2')
    expect(ed().candidates).toBeNull()
    ed().undo()
    expect(ed().candidates).toEqual({ group: 'grp', ids: ['c1', 'c2'] })
    expect(candidatesIn(stack([raster('a')]), { group: 'grp', ids: ['c1', 'c2'] })).toBeNull()
  })

  it('a result arriving keeps the active layer someone chose (nothing was sent from here); a later candidate joins without the picked-away one', async () => {
    const server = stack([group('grp', [raster('c1'), raster('c2'), raster('c3')], { name: 'AI inpaint' }), raster('a')])
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : String(input))
      const px = /\/layers\/([^/]+)\/pixels$/.exec(url.pathname)
      if (px) return new Response(new Uint8Array(64 * 64 * 4), { headers: { 'x-loom-width': '64', 'x-loom-height': '64', 'x-loom-channels': '4' } })
      if (url.pathname === '/documents/doc_1') return Response.json(server)
      return new Response('not stubbed', { status: 500 })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    useSession.setState({ backend: { host: '127.0.0.1', port: 8766, token: 't' } } as never)
    open([group('grp', [raster('c1')], { name: 'AI inpaint' }), raster('a')], 'a')   // c2 was picked away here
    await ed().mergeServerLayers(['c3'], 'grp')
    expect(findNode(ed().doc, 'grp')!.children!.map((n) => n.id)).toEqual(['c1', 'c3'])
    expect(ed().candidates).toEqual({ group: 'grp', ids: ['c1', 'c3'] })
    expect(ed().activeId).toBe('a')
    vi.unstubAllGlobals()
  })
})

describe('K64 a pixel operation on a text layer rasterises it first, asking', () => {
  afterEach(() => { useSession.setState({ toasts: [] }) })
  it('Clear asks; no leaves the text and the pixels alone; yes rasterises (its own step), then clears', async () => {
    open([raster('t', { text: TEXT })], 't')
    answer = false
    ed().clearSelected()
    await Promise.resolve(); await Promise.resolve()
    expect(findNode(ed().doc, 't')!.text).toBeTruthy()
    expect(ed().history).toEqual([])
    answer = true
    ed().clearSelected()
    await vi.waitFor(() => expect(ed().history.map((e) => e.label)).toEqual(['rasterize text', 'clear']))
    expect(findNode(ed().doc, 't')!.text ?? null).toBeNull()
    ed().undo(); ed().undo()
    expect(findNode(ed().doc, 't')!.text).toBeTruthy()
  })
  it('a layer that is not text runs at once; merging drops the base\'s block', () => {
    open([raster('a'), raster('t', { text: TEXT })], 'a')
    ed().clearSelected()
    expect(ed().history.map((e) => e.label)).toEqual(['clear'])
    ed().mergeNodes(['a', 't'])
    expect(findNode(ed().doc, 't')!.text ?? null).toBeNull()
  })
})

describe('K116 a layer under an open free transform moves with the box only', () => {
  it('a panel x / y on the transformed layer is refused, saying why', () => {
    open([raster('a')], 'a')
    useEditor.setState({ transform: { nodeId: 'a', rect: [0, 0, 64, 64], quad: [{ x: 0, y: 0 }, { x: 64, y: 0 }, { x: 64, y: 64 }, { x: 0, y: 64 }], pivot: { x: 32, y: 32 }, interp: 'bicubic', mode: 'free', selection: false } })
    ed().updateNode('a', { x: 5 }, 'nudge')
    expect(findNode(ed().doc, 'a')!.x).toBe(0)
    expect(ed().history).toEqual([])
    expect(useSession.getState().toasts.at(-1)?.text).toContain('free transform')
    ed().updateNode('a', { name: 'renamed' }, 'rename')                  // anything else still goes
    expect(findNode(ed().doc, 'a')!.name).toBe('renamed')
  })
})

describe('K66 the histogram and the thumbnails are keyed on what they are made of', () => {
  it('the histogram below a Levels layer keeps its key through the layer\'s own scrub; a stroke below changes it', () => {
    open([{ kind: 'adjustment', id: 'lv', name: 'Levels', opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, type: 'levels', params: { gamma: 1 } } as Node, raster('a')], 'lv')
    const k0 = histogramKey('lv')
    ed().updateNode('lv', { params: { gamma: 1.4 } })
    expect(histogramKey('lv')).toBe(k0)
    ed().pixels.get('a')!.refresh()
    expect(histogramKey('lv')).not.toBe(k0)
  })
  it('a thumbnail is made again only when the canvas version moved', () => {
    const lp = { version: 3, thumbnail: vi.fn(() => 'data:x') }
    cachedThumbnail(lp, 64); cachedThumbnail(lp, 64)
    expect(lp.thumbnail).toHaveBeenCalledTimes(1)
    lp.version = 4
    cachedThumbnail(lp, 64); cachedThumbnail(lp, 48)
    expect(lp.thumbnail).toHaveBeenCalledTimes(3)
  })
})

describe('K116 a pointer and a footprint per tool', () => {
  it('the cursor follows the tool; a transform takes the default; the footprint is the tool\'s diameter', () => {
    expect([toolCursor('move'), toolCursor('hand'), toolCursor('text'), toolCursor('zoom'), toolCursor('zoom', { alt: true }), toolCursor('brush'), toolCursor('lasso')])
      .toEqual(['move', 'grab', 'text', 'zoom-in', 'zoom-out', 'crosshair', 'crosshair'])
    expect(toolCursor('brush', { transform: true })).toBe('default')
    const s = { brush: { size: 48 }, healSize: 40, quickSize: 30 }
    expect([toolFootprint('brush', s), toolFootprint('eraser', s), toolFootprint('heal', s), toolFootprint('quick', s), toolFootprint('marquee', s)]).toEqual([48, 48, 40, 30, 0])
  })
})
