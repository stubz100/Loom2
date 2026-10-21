// AP1 thin (D114): the Final level's frame policy — ½ while scrubbing, full at rest, frames kept by (revision, frame, size), the idle fill,
// a new revision dropping the cache, the chip's text.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'
import { chipText, useComposition } from './compositionStore'

const FINAL = { id: 'fin_1', name: 'Shot', rate: 16, frames: 8, size: { w: 832, h: 480 }, layers: [], assembled_at: 'now', revision: 3 }
let comp = { final_id: 'fin_1', revision: 0, stale: false, clip_id: null, rendered_revision: null, layers: [], stack: [] }
const calls: string[] = []

function fakeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = input instanceof Request ? input.url : String(input)               // openapi-fetch sends a Request; the frames a URL string
  calls.push(url.replace(/^https?:\/\/[^/]+/, ''))
  if (url.endsWith('/finals/fin_1')) return Promise.resolve(new Response(JSON.stringify(FINAL), { status: 200, headers: { 'content-type': 'application/json' } }))
  if (url.endsWith('/finals/fin_1/composition')) return Promise.resolve(new Response(JSON.stringify(comp), { status: 200, headers: { 'content-type': 'application/json' } }))
  if (url.endsWith('/finals/fin_1/composition/layers')) return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'content-type': 'application/json' } }))
  if (url.includes('/composition/frame')) return Promise.resolve(new Response(new Uint8Array([1, 2, 3]), { status: 200 }))   // bytes, not jsdom's Blob (no stream())
  return Promise.resolve(new Response('{"detail":"nope"}', { status: 404 }))
}
const frames = () => calls.filter((u) => u.includes('/composition/frame')).map((u) => u.split('?')[1])
const settled = () => new Promise((r) => setTimeout(r, 0))

describe('AP1 thin: the composition viewer', () => {
  beforeEach(() => {
    calls.length = 0
    comp = { ...comp, revision: 0 }
    vi.stubGlobal('fetch', vi.fn(fakeFetch))
    Object.assign(URL, { createObjectURL: vi.fn(() => `blob:${Math.random()}`), revokeObjectURL: vi.fn() })
    setBackend({ host: '127.0.0.1', port: 1, token: 't' } as never)
    useSession.setState({ jobs: {} } as never)
    useComposition.setState({ finalId: null, final: null, comp: null, frame: 0, shown: null, filled: 0, playing: false })   // a fresh viewer; the open drops the module's cache
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('opens at ½ (frame 0), scrubs at ½, shows the full frame at rest, and keeps what it got', async () => {
    const s = useComposition.getState()
    await s.open('fin_1')
    expect(useComposition.getState().level).toBe('final')
    expect(frames()).toEqual(['t=0&side=416'])                                 // ½ of 832
    await vi.waitFor(() => { expect(useComposition.getState().error).toBeNull(); expect(useComposition.getState().shown).toMatchObject({ frame: 0, side: 'half', revision: 0 }) })
    useComposition.getState().setFrame(3)
    await vi.waitFor(() => expect(useComposition.getState().shown).toMatchObject({ frame: 3, side: 'half' }))
    expect(frames().at(-1)).toBe('t=0.1875&side=416')
    useComposition.getState().settle()                                          // what the rest timer calls
    await vi.waitFor(() => expect(useComposition.getState().shown).toMatchObject({ frame: 3, side: 'full' }))
    expect(frames().at(-1)).toBe('t=0.1875&side=0')
    const n = frames().length
    useComposition.getState().setFrame(3)                                       // the same frame again: nothing fetched, the full one stays
    await settled()
    expect(frames().length).toBe(n)
    expect(useComposition.getState().shown?.side).toBe('full')
    expect(chipText(useComposition.getState())).toBe('25 %')                        // frames 0 and 3 at ½ of 8: the number alone (UX9 U2)
  })

  it('fills the shot at ½ while idle, not while a job runs, and drops the cache on a new revision', async () => {
    const s = useComposition.getState()
    await s.open('fin_1')
    await vi.waitFor(() => { expect(useComposition.getState().error).toBeNull(); expect(useComposition.getState().shown).not.toBeNull() })
    useSession.setState({ jobs: { j: { id: 'j', status: 'running' } } } as never)
    await useComposition.getState().tick()
    expect(frames().length).toBe(1)                                             // D97 / D113: on demand only
    useSession.setState({ jobs: {} } as never)
    for (let i = 0; i < 7; i++) await useComposition.getState().tick()
    expect(frames().length).toBe(8)                                             // every frame at ½
    expect(useComposition.getState().error).toBeNull()
    expect(useComposition.getState().filled).toBe(8)
    await useComposition.getState().tick()
    expect(frames().length).toBe(8)                                             // nothing left to fill
    comp = { ...comp, revision: 1 }                                             // an edit landed: what was cached is stale
    await useComposition.getState().reload()
    await vi.waitFor(() => expect(useComposition.getState().shown).toMatchObject({ revision: 1 }))
    expect(useComposition.getState().filled).toBe(1)
  })
})
