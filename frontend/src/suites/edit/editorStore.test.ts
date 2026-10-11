// D68 (ArtCraft P6): editor store logic that needs no canvas — the node walk and the C20 merge of server layers (AI results) into
// the local stack. LayerPixels is replaced by a fake (jsdom has no 2D canvas); the orchestrator is a stubbed fetch.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'
import { countRasters, findNode, useEditor, walk, type DocumentStack, type Node } from './editorStore'

vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx = { drawImage: () => undefined } as unknown as CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) { this.width = width; this.height = height; this.grey = grey }
    static fromRaw(width: number, height: number, _bytes: Uint8Array, channels: 1 | 4) { return new FakePixels(width, height, channels === 1) }
    refresh() { this.version++ }
    destroy() { /* nothing on the GPU */ }
  }
  return { ...real, LayerPixels: FakePixels }
})

const B = { host: '127.0.0.1', port: 8766, token: 'test-token' }
const raster = (id: string, extra: Partial<Node> = {}): Node => ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 64, h: 64, ...extra })
const group = (id: string, children: Node[]): Node => ({ kind: 'group', id, name: id, opacity: 1, blend: 'pass-through', visible: true, locked: false, clip: false, mask: null, children })
const stack = (layers: Node[], extra: Partial<DocumentStack> = {}): DocumentStack => ({ schema_version: 1, id: 'doc_1', name: 'Doc', w: 256, h: 256, background: 'transparent', source_asset_id: null,
  created_at: '2026-10-11T08:00:00', saved_at: '2026-10-11T08:00:00', revision: 3, layers, has_selection: false, meta: {}, ...extra })

/** The orchestrator: GET /documents/doc_1 returns `server`; pixel GETs return raw bytes with their size headers. */
function orchestrator(server: () => DocumentStack) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    calls.push(`${url.pathname}${url.search}`)
    const px = /\/layers\/([^/]+)\/pixels$/.exec(url.pathname)
    if (px) {
      const kind = url.searchParams.get('kind')
      const n = findNode(server(), px[1])
      if (!n || (kind === 'mask' && !n.mask)) return new Response('missing', { status: 404 })
      const ch = kind === 'mask' ? 1 : 4
      return new Response(new Uint8Array((n.w ?? 1) * (n.h ?? 1) * ch), { headers: { 'x-loom-width': String(n.w), 'x-loom-height': String(n.h), 'x-loom-channels': String(ch) } })
    }
    if (url.pathname === '/documents/doc_1') return Response.json(server())
    return new Response('not stubbed', { status: 500 })
  })
  vi.stubGlobal('fetch', fetchMock)
  setBackend(B)                                   // the typed client binds fetch when it is created
  useSession.setState({ backend: B, toasts: [] })
  return calls
}

describe('walk / findNode', () => {
  const doc = stack([raster('a'), group('g', [raster('b'), group('h', [raster('c')])]), raster('d')])
  it('visits nodes in panel order, a group before its children, with the list each lives in', () => {
    const seen: string[] = []
    walk(doc.layers, (n, parent, i) => { seen.push(`${n.id}@${i}/${parent?.length}`) })
    expect(seen).toEqual(['a@0/3', 'g@1/3', 'b@0/2', 'h@1/2', 'c@0/1', 'd@2/3'])
  })
  it('stops at the first true', () => {
    const seen: string[] = []
    expect(walk(doc.layers, (n) => { seen.push(n.id); return n.id === 'b' })).toBe(true)
    expect(seen).toEqual(['a', 'g', 'b'])
  })
  it('finds nested nodes; null for unknown ids or no document', () => {
    expect(findNode(doc, 'c')?.id).toBe('c')
    expect(findNode(doc, 'x')).toBeNull()
    expect(findNode(null, 'a')).toBeNull()
    expect(findNode(doc, null)).toBeNull()
    expect(countRasters(doc)).toBe(4)
  })
})

describe('mergeServerLayers (C20: merge into the local stack, never adopt the server one)', () => {
  beforeEach(() => {
    useEditor.setState({ doc: null, pixels: new Map(), masks: new Map(), history: [], future: [], selection: null, transform: null, candidates: null, activeId: null, fitRequested: 0 })
  })

  it('adds the new layer on top and keeps local edits made while the job ran', async () => {
    const local = stack([raster('lyr_a', { name: 'renamed locally' }), raster('lyr_local')])
    const server = stack([raster('lyr_ai', { mask: { enabled: true, linked: true, x: 0, y: 0 } }), raster('lyr_a', { name: 'old name' })], { revision: 7, saved_at: '2026-10-11T09:00:00' })
    const calls = orchestrator(() => server)
    useEditor.setState({ doc: local })
    await useEditor.getState().mergeServerLayers(['lyr_ai'])
    const st = useEditor.getState()
    expect(st.doc!.layers.map((n) => `${n.id}:${n.name}`)).toEqual(['lyr_ai:lyr_ai', 'lyr_a:renamed locally', 'lyr_local:lyr_local'])
    expect(st.doc!.revision).toBe(7)
    expect(st.doc!.saved_at).toBe('2026-10-11T09:00:00')
    expect(st.pixels.has('lyr_ai')).toBe(true)
    expect(st.masks.get('lyr_ai')?.grey).toBe(true)
    expect(st.activeId).toBe('lyr_ai')
    expect(st.candidates).toBeNull()
    expect(st.history.at(-1)).toMatchObject({ label: 'AI result', layerId: 'lyr_ai' })
    expect(st.history.at(-1)!.stack!.layers.map((n) => n.id)).toEqual(['lyr_a', 'lyr_local'])   // undo restores the stack before the merge
    expect(calls).toContain('/documents/doc_1/layers/lyr_ai/pixels?kind=image&raw=1')
  })

  it('collects candidates into their AI group, later ones joining the group already here', async () => {
    let server = stack([group('grp_ai', [raster('cand_1')]), raster('lyr_a')])
    orchestrator(() => server)
    useEditor.setState({ doc: stack([raster('lyr_a')]) })
    await useEditor.getState().mergeServerLayers(['cand_1'], 'grp_ai')
    server = stack([group('grp_ai', [raster('cand_1'), raster('cand_2')]), raster('lyr_a')])
    await useEditor.getState().mergeServerLayers(['cand_2'], 'grp_ai')
    const st = useEditor.getState()
    expect(st.doc!.layers.map((n) => n.id)).toEqual(['grp_ai', 'lyr_a'])
    expect(findNode(st.doc, 'grp_ai')!.children!.map((n) => n.id)).toEqual(['cand_1', 'cand_2'])
    expect(st.candidates).toEqual({ group: 'grp_ai', ids: ['cand_1', 'cand_2'] })
  })

  it('shifts local layers and unlinked masks when outpaint grew the canvas', async () => {
    const local = stack([raster('lyr_a', { x: 5, y: 6 }), raster('lyr_m', { mask: { enabled: true, linked: false, x: 1, y: 2 } })])
    const server = stack([raster('lyr_out', { w: 320, h: 256 }), raster('lyr_a', { x: 37, y: 6 })], { w: 320, h: 256 })
    orchestrator(() => server)
    useEditor.setState({ doc: local })
    await useEditor.getState().mergeServerLayers(['lyr_out'], undefined, { left: 32, top: 0 })
    const d = useEditor.getState().doc!
    expect([d.w, d.h]).toEqual([320, 256])
    expect(findNode(d, 'lyr_a')).toMatchObject({ x: 37, y: 6 })
    expect(findNode(d, 'lyr_m')!.mask).toMatchObject({ x: 33, y: 2 })
    expect(useEditor.getState().fitRequested).toBeGreaterThan(0)
  })

  it('ignores a result for a document that is no longer open', async () => {
    orchestrator(() => stack([raster('lyr_ai')]))
    await useEditor.getState().mergeServerLayers(['lyr_ai'])
    expect(useEditor.getState().doc).toBeNull()
    expect(useEditor.getState().history).toEqual([])
  })
})
