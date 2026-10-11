// D68 (ArtCraft P6): session.applyEvent routes every WebSocket frame — session state for jobs, queue, engine and project; the suite
// stores (mocked here with spies) for catalogue, album, clip and document frames — and onEvents hands frames to subscribers.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../api/client'
import type { EventFrame, Job } from '../api/types'
import { applyEvent, onEvents, useSession } from './session'

const spies = vi.hoisted(() => {
  const store = (q: Record<string, unknown>) => {
    const state = { q, load: vi.fn(async () => undefined), refreshMeta: vi.fn(async () => undefined), applyEvent: vi.fn() }
    return { getState: () => state, state }
  }
  const album = { load: vi.fn(async () => undefined) }
  const animate = { onClipReady: vi.fn(), onClipUpdated: vi.fn() }
  const editor = { onDocumentChanged: vi.fn() }
  return {
    grid: store({ folder: 'all' }), unprocessed: store({ folder: 'unprocessed' }), page: store({ folder: 'all', group_id: 'grp_1' }), album, animate, editor,
    albumLoad: album.load, onClipReady: animate.onClipReady, onClipUpdated: animate.onClipUpdated, onDocumentChanged: editor.onDocumentChanged,
  }
})
vi.mock('../suites/catalogue/catalogueStore', () => ({ allCatalogueStores: () => [spies.grid, spies.unprocessed, spies.page] }))
vi.mock('../suites/catalogue/albumStore', () => ({ useAlbum: { getState: () => spies.album } }))
vi.mock('../suites/animate/animateStore', () => ({ useAnimate: { getState: () => spies.animate } }))
vi.mock('../suites/edit/editorStore', () => ({ useEditor: { getState: () => spies.editor } }))

let seq = 0
const frame = (type: string, data: unknown) => ({ type, data, seq: ++seq, t: 0 }) as unknown as EventFrame
const route = (f: EventFrame) => applyEvent(f, useSession.setState, useSession.getState)
const job = (id: string, status: string, extra: Record<string, unknown> = {}) => ({ id, status, created_at: '2026-10-11T10:00:00', progress: 0, wall_s: 12, error: null, ...extra }) as unknown as Job
const INITIAL = useSession.getState()

const requested: string[] = []
beforeEach(() => {
  useSession.setState({ ...INITIAL, events: [], jobs: {}, previews: {}, toasts: [], queue: null, engine: null, project: null })
  requested.length = 0
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(input instanceof Request ? input.url : String(input)).pathname
    requested.push(path)
    if (path === '/queue') return Response.json({ paused: false, counts: { queued: 0 }, running: null })
    if (path === '/project') return Response.json({ open: true, name: 'Fixture' })
    return new Response('not stubbed', { status: 500 })
  }))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  for (const s of [spies.grid, spies.unprocessed, spies.page]) Object.values(s.state).forEach((v) => typeof v === 'function' && (v as ReturnType<typeof vi.fn>).mockClear())
  for (const f of [spies.albumLoad, spies.onClipReady, spies.onClipUpdated, spies.onDocumentChanged]) f.mockClear()
})

describe('applyEvent: session state', () => {
  it('keeps the newest 200 frames', () => {
    for (let i = 0; i < 205; i++) route(frame('queue.state', { paused: false, counts: {}, n: i }))
    const ev = useSession.getState().events
    expect(ev).toHaveLength(200)
    expect((ev[199].data as unknown as { n: number }).n).toBe(204)
  })
  it('tracks jobs: created, progress (known jobs only), deleted', () => {
    route(frame('job.created', job('job_00000001', 'queued')))
    route(frame('job.progress', { id: 'job_00000001', progress: 0.5, text: 'step 4/8', node: null }))
    route(frame('job.progress', { id: 'job_unknown', progress: 0.9, text: 'x', node: null }))
    expect(useSession.getState().jobs.job_00000001).toMatchObject({ status: 'queued', progress: 0.5, progress_text: 'step 4/8' })
    expect(useSession.getState().jobs).not.toHaveProperty('job_unknown')
    route(frame('job.deleted', { id: 'job_00000001' }))
    expect(useSession.getState().jobs).toEqual({})
  })
  it('on a finished job: toasts, refreshes queue and project, and frees its preview', async () => {
    const revoke = vi.fn()
    const orig = URL.revokeObjectURL
    URL.revokeObjectURL = revoke
    try {
      useSession.setState({ previews: { job_00000002: 'blob:preview' } })
      route(frame('job.updated', job('job_00000002', 'done')))
      expect(revoke).toHaveBeenCalledWith('blob:preview')
      expect(useSession.getState().previews).toEqual({})
      expect(useSession.getState().toasts.at(-1)).toMatchObject({ kind: 'success', text: 'Job 00000002 done in 12 s' })
      await vi.waitFor(() => expect(useSession.getState().project).toMatchObject({ open: true, name: 'Fixture' }))
      expect(useSession.getState().queue).toMatchObject({ paused: false })
      expect(requested.sort()).toEqual(['/project', '/queue'])
    } finally { URL.revokeObjectURL = orig }
  })
  it('a failed job toasts as an error that stays', () => {
    route(frame('job.updated', job('job_00000003', 'failed', { error: 'OOM' })))
    expect(useSession.getState().toasts.at(-1)).toMatchObject({ kind: 'error', text: 'Job 00000003 failed: OOM', sticky: true })
  })
  it('sets queue, merges engine state, follows the project', () => {
    route(frame('queue.state', { paused: true, counts: { queued: 2 } }))
    expect(useSession.getState().queue).toMatchObject({ paused: true })
    useSession.setState({ engine: { running: false, last_error: 'old' } as never })
    route(frame('engine.state', { running: true }))
    expect(useSession.getState().engine).toMatchObject({ running: true, last_error: 'old' })
    route(frame('project.opened', { open: true, name: 'P' }))
    expect(useSession.getState().project).toMatchObject({ open: true, name: 'P' })
    route(frame('project.closed', {}))
    expect(useSession.getState().project).toEqual({ open: false })
  })
})

describe('applyEvent: suite stores', () => {
  it('hands asset frames to every catalogue store', async () => {
    const f = frame('asset.updated', { id: 'ast_1' })
    route(f)
    await vi.waitFor(() => { for (const s of [spies.grid, spies.unprocessed, spies.page]) expect(s.state.applyEvent).toHaveBeenCalledWith(f) })
  })
  it('reloads every catalogue store on catalogue.changed', async () => {
    route(frame('catalogue.changed', { reason: 'import' }))
    await vi.waitFor(() => { for (const s of [spies.grid, spies.unprocessed, spies.page]) { expect(s.state.load).toHaveBeenCalledTimes(1); expect(s.state.refreshMeta).toHaveBeenCalledTimes(1) } })
  })
  it('on group.changed reloads the album, every store’s counts, and only the views that show placements', async () => {
    route(frame('group.changed', { ids: ['grp_1'] }))
    await vi.waitFor(() => { expect(spies.albumLoad).toHaveBeenCalled(); for (const s of [spies.grid, spies.unprocessed, spies.page]) expect(s.state.refreshMeta).toHaveBeenCalled() })
    expect(spies.grid.state.load).not.toHaveBeenCalled()
    expect(spies.unprocessed.state.load).toHaveBeenCalledWith({ keepSelection: true })
    expect(spies.page.state.load).toHaveBeenCalledWith({ keepSelection: true })
  })
  it('routes clip frames to Animate and document frames to Edit', async () => {
    const ready = { clip_id: 'clp_1', asset_id: 'ast_c', job_id: 'job_1', fps: 16, frames: 81, w: 832, h: 480 }
    // one frame at a time: under vitest 5.0.2 a second dynamic import of a vi.mock'ed module that starts while the first is still in
    // flight resolves to the real module (reproduced 2026-10-11), so two clip frames routed back to back would reach the real store
    route(frame('clip.ready', ready))
    await vi.waitFor(() => expect(spies.onClipReady).toHaveBeenCalledWith(ready))
    route(frame('clip.updated', { id: 'clp_1' }))
    await vi.waitFor(() => expect(spies.onClipUpdated).toHaveBeenCalledWith({ id: 'clp_1' }))
    route(frame('document.changed', { id: 'doc_1', added: ['lyr_ai'] }))
    await vi.waitFor(() => expect(spies.onDocumentChanged).toHaveBeenCalledWith({ id: 'doc_1', added: ['lyr_ai'] }))
  })
  it('ignores frames it does not know, apart from recording them', () => {
    route(frame('hello', { version: 'x' }))
    expect(useSession.getState().events.at(-1)!.type).toBe('hello')
    expect(requested).toEqual([])
  })
})

describe('onEvents', () => {
  it('delivers the frames of the asked types until unsubscribed', () => {
    const got: string[] = []
    // frames that route to no suite store (a store frame starts a dynamic import; see the clip test for why those go one at a time)
    const off = onEvents(['queue.state', 'project.closed'], (f) => got.push(f.type))
    route(frame('queue.state', { paused: false, counts: {} }))
    route(frame('engine.state', { running: true }))
    route(frame('project.closed', {}))
    off()
    route(frame('queue.state', { paused: true, counts: {} }))
    expect(got).toEqual(['queue.state', 'project.closed'])
  })
})
