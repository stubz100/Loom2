// D123 (SC3c): the things store — a click sends every point so far (SAM 3 needs one on the thing first), the find's mask is read back when
// its job lands; Make follows the Fill's result (the rebuild, then the models) and reloads the stage as each lands.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc } from '../../api/types'
import { useSession } from '../../store/session'
import { useStage } from './stageStore'
import { useThings } from './thingsStore'

const B = { host: '127.0.0.1', port: 8766, token: 't' }
const DOC = { id: 'stg_1', objects: [{ id: 'set_1', kind: 'set', preset: 'image', name: 'Picture set', plate_asset_id: 'ast_pic', things: [] }], cameras: [] } as unknown as StageDoc
let sent: { path: string; body: unknown }[] = []
const job = (id: string, status: string, result: Record<string, unknown> | null = null, kind = 'segment') => ({ id, kind, status, result, error: null })
const land = (jobs: Record<string, unknown>) => useSession.setState({ jobs: { ...useSession.getState().jobs, ...jobs } as never })

beforeEach(() => {
  sent = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(String(input), init)
    const url = new URL(req.url)
    if (req.method === 'GET' && url.pathname === '/assets/ast_pic') return Response.json({ id: 'ast_pic', w: 4, h: 2 })
    if (req.method === 'GET' && url.pathname === '/documents/doc_1/selection') return new Response(new Uint8Array([0, 255, 255, 0, 0, 0, 0, 0]))
    if (req.method === 'GET' && url.pathname === '/stages/stg_1/sets/set_1/things/shadows') { sent.push({ path: url.pathname, body: null }); return new Response(new Uint8Array([0, 0, 0, 255, 255, 0, 0, 0])) }
    if (req.method === 'POST' && url.pathname.endsWith('/things/find')) { sent.push({ path: url.pathname, body: await req.json() }); return Response.json({ job_id: 'job_find', document_id: 'doc_1' }) }
    if (req.method === 'POST' && url.pathname.endsWith('/things/make')) return Response.json({ clean_job_id: 'job_clean', models: [{ thing_id: 'thg_1', cutout_id: 'ast_cut' }] })
    return new Response('not stubbed', { status: 500 })
  }))
  setBackend(B)
  useSession.setState({ backend: B, jobs: {}, toast: vi.fn() as never })
  useStage.setState({ current: DOC, open: vi.fn(async () => undefined) as never, flush: vi.fn(async () => undefined) as never })
  useThings.setState({ setId: null, size: null, points: [], mode: 1, job: null, docId: null, mask: null, shadows: null, making: [] })
})
afterEach(() => vi.unstubAllGlobals())

describe('D123 the things store', () => {
  it('a click sends every point so far — nothing before one is on the thing — and the mask is read back when the find lands', async () => {
    await useThings.getState().open('set_1')
    expect(useThings.getState().size).toEqual({ w: 4, h: 2 })
    await useThings.getState().addPoint(0.4, 0.6, 0)                                  // "not it" alone: SAM 3 needs a point on the thing
    expect(sent).toEqual([])
    await useThings.getState().addPoint(1.2, 0.2, 1)
    expect(sent).toEqual([{ path: '/stages/stg_1/sets/set_1/things/find', body: { points: [{ x: 0, y: 1, label: 0 }, { x: 1, y: 0, label: 1 }] } }])
    expect(useThings.getState()).toMatchObject({ job: 'job_find', docId: 'doc_1' })
    land({ job_find: job('job_find', 'done') })
    await vi.waitFor(() => expect(Array.from(useThings.getState().mask ?? [])).toEqual([0, 255, 255, 0, 0, 0, 0, 0]))
    expect(useThings.getState().job).toBeNull()
  })

  it('D124: the shadows the clean will take are read when the sheet opens on a thing still to make — none asked for without one', async () => {
    await useThings.getState().open('set_1')
    expect(sent.filter((x) => x.path.endsWith('/shadows'))).toHaveLength(0)                    // nothing kept: nothing to ask
    useStage.setState({ current: { ...DOC, objects: [{ ...DOC.objects[0], things: [{ id: 'thg_1', name: 'Crate', mask_asset_id: 'ast_m', mesh_asset_id: null }] }] } as unknown as StageDoc })
    await useThings.getState().open('set_1')
    expect(Array.from(useThings.getState().shadows ?? [])).toEqual([0, 0, 0, 255, 255, 0, 0, 0])
  })

  it('Make follows the Fill: the rebuild and the models join when it lands, the stage reloads as each lands', async () => {
    await useThings.getState().make('set_1')
    expect(useThings.getState().making).toEqual(['job_clean'])
    land({ job_clean: job('job_clean', 'done', { next_job_id: 'job_rebuild', next_job_ids: ['job_rebuild', 'job_model'] }, 'inpaint') })
    await vi.waitFor(() => expect(useThings.getState().making).toEqual(['job_rebuild', 'job_model']))
    expect(useStage.getState().open).toHaveBeenCalledWith('stg_1')
    land({ job_rebuild: job('job_rebuild', 'done', null, 'image_to_set') })
    await vi.waitFor(() => expect(useThings.getState().making).toEqual(['job_model']))
    land({ job_model: job('job_model', 'done', null, 'image_to_mesh') })
    await vi.waitFor(() => expect(useThings.getState().making).toEqual([]))
    expect(useSession.getState().toast).toHaveBeenLastCalledWith(expect.stringContaining('The things are made'), 'success')
    expect((useStage.getState().open as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBe(3)
  })
})
