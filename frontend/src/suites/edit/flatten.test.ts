// D90 (UI6, owed): Edit › Flatten image — the pure rules (when it runs, the name, the stack) and the store's run against a stubbed
// orchestrator: sync first, the exact flatten fetched raw, one raster layer, one undo step that brings every layer back.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { command, isEnabled, type MenuItem } from '../../frame/commands'
import { useSession } from '../../store/session'
import { canvasMenu, layerMenu } from './editCommands'
import { useEditor, type DocumentStack, type Node } from './editorStore'
import { flattenBlocker, flattenCounts, flattenedName, flattenedStack } from './flatten'

vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1; bytes: Uint8Array | null = null
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx = { drawImage: () => undefined } as unknown as CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) { this.width = width; this.height = height; this.grey = grey }
    static fromRaw(width: number, height: number, bytes: Uint8Array, channels: 1 | 4) { const p = new FakePixels(width, height, channels === 1); p.bytes = bytes; return p }
    toRaw() { return this.bytes ?? new Uint8Array(this.width * this.height * (this.grey ? 1 : 4)) }
    refresh() { this.version++ }
    destroy() { /* nothing on the GPU */ }
  }
  return { ...real, LayerPixels: FakePixels }
})

const B = { host: '127.0.0.1', port: 8766, token: 'test-token' }
const raster = (id: string, extra: Partial<Node> = {}): Node => ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 4, h: 2, ...extra })
const stack = (layers: Node[], extra: Partial<DocumentStack> = {}): DocumentStack => ({ schema_version: 1, id: 'doc_1', name: 'Doc', w: 4, h: 2, background: '#203040', source_asset_id: null,
  created_at: '2026-10-17T08:00:00', saved_at: '2026-10-17T08:00:00', revision: 3, layers, has_selection: false, meta: {}, ...extra })
const cmds = (items: MenuItem[]): string[] => items.flatMap((x) => ('cmd' in x && x.cmd ? [x.cmd] : 'items' in x && x.items ? cmds(x.items) : []))

const FLAT = Uint8Array.from({ length: 4 * 2 * 4 }, (_, i) => (i * 37) % 256)

function orchestrator() {
  const calls: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    const method = input instanceof Request ? input.method : init?.method ?? 'GET'
    calls.push(`${method} ${url.pathname}`)
    if (url.pathname === '/documents/doc_1' && method === 'PUT') {
      const body = input instanceof Request ? await input.json() : JSON.parse(String(init?.body))
      return Response.json({ ...body, revision: body.revision + 1, missing_pixels: [], missing_masks: [] })
    }
    if (url.pathname === '/documents/doc_1/export') {
      expect(JSON.parse(String(init?.body))).toEqual({ format: 'raw' })
      return new Response(FLAT.slice(), { headers: { 'x-loom-width': '4', 'x-loom-height': '2', 'x-loom-channels': '4' } })
    }
    if (url.pathname.includes('/pixels') || url.pathname.endsWith('/selection')) return Response.json({})
    return new Response('not stubbed', { status: 500 })
  })
  vi.stubGlobal('fetch', fetchMock)
  setBackend(B)
  useSession.setState({ backend: B, toasts: [] })
  return calls
}

describe('flatten rules', () => {
  it('runs on anything but one plain full-canvas layer', () => {
    expect(flattenBlocker(null)).toBe('no document')
    expect(flattenBlocker(stack([]))).toBe('no layers')
    expect(flattenBlocker(stack([raster('a')]))).toBe('the document is one layer already')
    expect(flattenBlocker(stack([raster('a', { opacity: 0.5 })]))).toBeNull()
    expect(flattenBlocker(stack([raster('a', { blend: 'multiply' })]))).toBeNull()
    expect(flattenBlocker(stack([raster('a', { mask: { enabled: true, linked: true, x: 0, y: 0 } })]))).toBeNull()
    expect(flattenBlocker(stack([raster('a', { x: 1 })]))).toBeNull()
    expect(flattenBlocker(stack([{ ...raster('g'), kind: 'group', children: [raster('a')] }]))).toBeNull()
    expect(flattenBlocker(stack([raster('a'), raster('b')]))).toBeNull()
  })
  it('names the layer after the bottom pixel layer, else Background; counts folded and hidden layers', () => {
    expect(flattenedName(stack([raster('top'), raster('Paper')]))).toBe('Paper')
    expect(flattenedName(stack([raster('top'), { ...raster('adj'), kind: 'adjustment', type: 'invert' }]))).toBe('Background')
    const doc = stack([raster('a', { visible: false }), { ...raster('g'), kind: 'group', visible: false, children: [raster('b')] }, raster('c', { lineage_asset_id: 'ast_1' })])
    expect(flattenCounts(doc)).toEqual({ layers: 4, hidden: 2 })
    const next = flattenedStack(doc, 'lyr_flat')
    expect(next.layers).toEqual([expect.objectContaining({ id: 'lyr_flat', kind: 'raster', name: 'c', x: 0, y: 0, w: 4, h: 2, opacity: 1, blend: 'normal', mask: null, lineage_asset_id: 'ast_1' })])
    expect(next).toMatchObject({ id: 'doc_1', background: '#203040', revision: 3, name: 'Doc' })
    expect(doc.layers).toHaveLength(3)                                     // the input is not touched
  })
})

describe('Flatten image', () => {
  beforeEach(() => { useEditor.setState({ doc: null, history: [], future: [], pixels: new Map(), masks: new Map(), selection: null, docDirty: false, transform: null }) })

  it('is in the canvas menu\'s Layer ▸ and the layers footer\'s More ▾ (the layer menu), enabled when there is something to fold', () => {
    useEditor.setState({ doc: stack([raster('a')]), activeId: 'a' })
    expect(cmds(canvasMenu())).toContain('edit.layer.flatten')
    expect(cmds(layerMenu())).toContain('edit.layer.flatten')
    expect(isEnabled(command('edit.layer.flatten')!)).toBe(false)
    useEditor.setState({ doc: stack([raster('a'), raster('b')]) })
    expect(isEnabled(command('edit.layer.flatten')!)).toBe(true)
  })

  it('syncs, takes the server\'s exact flatten as one layer, marks the document dirty and undoes in one step', async () => {
    const calls = orchestrator()
    const before = stack([{ ...raster('g'), kind: 'group', blend: 'screen', children: [raster('a', { blend: 'multiply' })] }, { ...raster('adj'), kind: 'adjustment', type: 'invert' }, raster('Paper')])
    useEditor.setState({ doc: before, activeId: 'a', docDirty: true })
    await useEditor.getState().flattenImage()
    const st = useEditor.getState()
    expect(calls.indexOf('PUT /documents/doc_1')).toBeLessThan(calls.indexOf('POST /documents/doc_1/export'))   // the server flattens what is on screen
    expect(st.doc!.layers).toHaveLength(1)
    const flat = st.doc!.layers[0]
    expect(flat).toMatchObject({ kind: 'raster', name: 'Paper', w: 4, h: 2, x: 0, y: 0 })
    expect((st.pixels.get(flat.id) as unknown as { bytes: Uint8Array }).bytes).toEqual(FLAT)
    expect(st.pixels.get(flat.id)!.dirty).toBe(true)
    expect(st.docDirty).toBe(true)
    expect(st.activeId).toBe(flat.id)
    expect(st.history.at(-1)?.label).toBe('flatten image')
    expect(useSession.getState().toasts.at(-1)?.text).toMatch(/^Flattened 4 layers into "Paper"/)
    st.undo()
    expect(useEditor.getState().doc!.layers.map((n) => n.id)).toEqual(['g', 'adj', 'Paper'])
    useEditor.getState().redo()
    expect(useEditor.getState().doc!.layers.map((n) => n.id)).toEqual([flat.id])
  })

  it('says so and changes nothing on one plain layer', async () => {
    orchestrator()
    useEditor.setState({ doc: stack([raster('a')]), activeId: 'a' })
    await useEditor.getState().flattenImage()
    expect(useEditor.getState().history).toHaveLength(0)
    expect(useSession.getState().toasts.at(-1)?.text).toMatch(/^Nothing to flatten/)
  })
})
