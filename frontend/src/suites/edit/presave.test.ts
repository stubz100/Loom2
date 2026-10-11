// D70 (ArtCraft P10): the editor's pre-save state machine. `sync()` sends the stack and the dirty layers to the server's open
// document (what AI jobs read) without writing the .ora or toasting; a stroke that lands during a flight re-dirties its layer; `save()`
// writes the .ora only when it lags, quietly for autosave. LayerPixels is a fake (no 2D canvas in jsdom); the orchestrator is a stub.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'
import { useEditor, type DocumentStack, type Node } from './editorStore'
import { LayerPixels } from './layerPixels'

vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx = { drawImage: () => undefined } as unknown as CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) { this.width = width; this.height = height; this.grey = grey }
    static fromRaw(width: number, height: number, _bytes: Uint8Array, channels: 1 | 4) { return new FakePixels(width, height, channels === 1) }
    toRaw() { return new Uint8Array(this.width * this.height * (this.grey ? 1 : 4)) }
    refresh() { this.version++ }
    destroy() { /* nothing on the GPU */ }
  }
  return { ...real, LayerPixels: FakePixels }
})

const B = { host: '127.0.0.1', port: 8766, token: 'test-token' }
const raster = (id: string): Node => ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 8, h: 8 })
const stack = (revision = 3): DocumentStack => ({ schema_version: 1, id: 'doc_1', name: 'Doc', w: 8, h: 8, background: 'transparent', source_asset_id: null,
  created_at: '2026-10-11T08:00:00', saved_at: '2026-10-11T08:00:00', revision, layers: [raster('a'), raster('b')], has_selection: false, meta: {} })

/** The orchestrator's document routes; a layer upload can be held open to land a "stroke" during the flight. */
function orchestrator() {
  const calls: string[] = []
  let rev = 3
  let hold: (() => void) | null = null
  let holdNext = false
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : null
    const url = new URL(req ? req.url : String(input))
    const method = (req?.method ?? init?.method ?? 'GET').toUpperCase()
    calls.push(`${method} ${url.pathname}`)
    if (method === 'PUT' && url.pathname === '/documents/doc_1') { rev += 1; return Response.json({ ...stack(rev), missing_pixels: [], missing_masks: [] }) }
    if (method === 'PUT' && /\/layers\/[^/]+\/pixels$/.test(url.pathname)) {
      if (holdNext) { holdNext = false; await new Promise<void>((r) => { hold = r }) }
      return Response.json({ layer: 'x', kind: 'image', w: 8, h: 8 })
    }
    if (method === 'POST' && url.pathname === '/documents/doc_1/save') return Response.json(stack(rev))
    if (method === 'PUT' && url.pathname === '/documents/doc_1/selection') return Response.json({ w: 0, h: 0 })
    return new Response('not stubbed', { status: 500 })
  }))
  setBackend(B)
  useSession.setState({ backend: B, toasts: [] })
  // the selection rides each flush when it changed (D70); these tests watch the stack and layers — one test below covers the selection
  const docCalls = () => calls.filter((c) => !c.endsWith('/selection'))
  return { calls, docCalls, holdNextUpload: () => { holdNext = true }, release: () => hold?.() }
}

function open() {
  const pixels = new Map<string, LayerPixels>([['a', new LayerPixels(8, 8)], ['b', new LayerPixels(8, 8)]])
  useEditor.setState({ doc: stack(), pixels, masks: new Map(), docDirty: false, saving: false })
  return pixels
}

describe('D70 pre-save', () => {
  let o: ReturnType<typeof orchestrator>
  beforeEach(() => { o = orchestrator() })

  it('sync sends nothing when nothing is dirty', async () => {
    open()
    expect(await useEditor.getState().sync()).toBe(true)
    expect(o.docCalls()).toEqual([])
  })

  it('sync sends the stack and only the dirty layers, adopts the server revision, writes no .ora and toasts nothing', async () => {
    const px = open()
    px.get('b')!.dirty = true
    useEditor.setState({ docDirty: true })
    expect(await useEditor.getState().sync()).toBe(true)
    expect(o.docCalls()).toEqual(['PUT /documents/doc_1', 'PUT /documents/doc_1/layers/b/pixels'])
    expect(useEditor.getState().doc!.revision).toBe(4)                 // the next PUT builds on the server's revision (no 409)
    expect(useEditor.getState().docDirty).toBe(false)
    expect(px.get('b')!.dirty).toBe(false)
    expect(useSession.getState().toasts).toEqual([])
  })

  it('a stroke during a flight re-dirties its layer and rides the next sync', async () => {
    const px = open()
    px.get('a')!.dirty = true
    useEditor.setState({ docDirty: true })
    o.holdNextUpload()
    const flight = useEditor.getState().sync()
    await vi.waitFor(() => expect(o.calls).toContain('PUT /documents/doc_1/layers/a/pixels'))
    px.get('a')!.dirty = true                                            // the stroke lands while the upload is in flight
    useEditor.setState({ docDirty: true })
    o.release()
    await flight
    expect(px.get('a')!.dirty).toBe(true)
    o.calls.length = 0
    await useEditor.getState().sync()
    expect(o.docCalls()).toEqual(['PUT /documents/doc_1', 'PUT /documents/doc_1/layers/a/pixels'])
  })

  it('concurrent syncs share one flight', async () => {
    const px = open()
    px.get('a')!.dirty = true
    useEditor.setState({ docDirty: true })
    await Promise.all([useEditor.getState().sync(), useEditor.getState().sync(), useEditor.getState().sync()])
    expect(o.docCalls().filter((c) => c === 'PUT /documents/doc_1')).toHaveLength(1)
  })

  it('save writes the .ora only when it lags the open document; a quiet save shows no toast', async () => {
    const px = open()
    px.get('a')!.dirty = true
    useEditor.setState({ docDirty: true })
    expect(await useEditor.getState().save({ quiet: true })).toBe(true)
    expect(o.docCalls()).toEqual(['PUT /documents/doc_1', 'PUT /documents/doc_1/layers/a/pixels', 'POST /documents/doc_1/save'])
    expect(useSession.getState().toasts).toEqual([])
    o.calls.length = 0
    expect(await useEditor.getState().save()).toBe(true)                // clean and in sync with the file: no request, a toast for the user
    expect(o.docCalls()).toEqual([])
    expect(useSession.getState().toasts.map((t) => t.text)).toEqual(['Saved'])
  })

  it('the selection is uploaded when it changed and not again', async () => {
    open()
    useEditor.setState({ selection: new LayerPixels(8, 8, true) })
    await useEditor.getState().sync()
    await useEditor.getState().sync()
    expect(o.calls.filter((c) => c.endsWith('/selection'))).toEqual(['PUT /documents/doc_1/selection'])
    useEditor.getState().selection!.refresh()                            // a new marquee: the version moves
    await useEditor.getState().sync()
    expect(o.calls.filter((c) => c.endsWith('/selection'))).toHaveLength(2)
  })
})
