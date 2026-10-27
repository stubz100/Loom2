// The review of 2026-10-27, V67: the queue and project fetched after a job frame — a reply that lands after a newer `queue.state` /
// `project.*` frame or a later fetch is dropped, never overwriting the newer state.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../api/client'
import type { EventFrame, Job } from '../api/types'
import { applyEvent, useSession } from './session'

vi.mock('../suites/catalogue/catalogueStore', () => ({ allCatalogueStores: () => [] }))
vi.mock('../suites/catalogue/albumStore', () => ({ useAlbum: { getState: () => ({ load: vi.fn(), loadUsedBy: vi.fn() }) } }))
vi.mock('../suites/animate/animateStore', () => ({ useAnimate: { getState: () => ({ onClipReady: vi.fn(), onClipUpdated: vi.fn() }) } }))
vi.mock('../suites/edit/editorStore', () => ({ useEditor: { getState: () => ({ onDocumentChanged: vi.fn(), resync: vi.fn() }) } }))

let seq = 0
const frame = (type: string, data: unknown) => ({ type, data, seq: ++seq, t: 0 }) as unknown as EventFrame
const route = (f: EventFrame) => applyEvent(f, useSession.setState, useSession.getState)
const job = (id: string, status: string) => ({ id, status, created_at: '2026-10-27T10:00:00', progress: 0, wall_s: 1, error: null }) as unknown as Job
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
const settle = () => new Promise<void>((r) => setTimeout(r, 0))                       // a macrotask: the client's reply handling drains

describe('late replies (V67)', () => {
  const held: { path: string; resolve: (r: Response) => void }[] = []
  beforeEach(() => {
    held.length = 0
    useSession.setState({ events: [], jobs: {}, previews: {}, toasts: [], queue: null, project: null })
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : String(input)).pathname
      return new Promise<Response>((resolve) => held.push({ path, resolve }))
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('a queue reply that lands after a queue.state frame is dropped', async () => {
    route(frame('job.updated', job('job_a', 'queued')))                                   // → GET /queue in flight
    await settle()
    expect(held.map((h) => h.path)).toEqual(['/queue'])
    route(frame('queue.state', { paused: false, counts: { queued: 2 }, running: null }))  // the state itself, newer
    held[0].resolve(json({ paused: true, counts: { queued: 9 }, running: null }))        // the old reply, late
    await settle()
    expect(useSession.getState().queue).toEqual({ paused: false, counts: { queued: 2 }, running: null })
  })

  it('of two fetches only the later one lands; the project follows the same rule', async () => {
    route(frame('job.updated', job('job_a', 'running')))
    route(frame('job.updated', job('job_b', 'running')))
    await settle()
    expect(held.map((h) => h.path)).toEqual(['/queue', '/queue'])
    held[1].resolve(json({ paused: false, counts: { queued: 1 }, running: 'job_b' }))     // the later fetch answers first …
    await settle()
    held[0].resolve(json({ paused: false, counts: { queued: 7 }, running: 'job_a' }))     // … the earlier one after it: dropped
    await settle()
    expect(useSession.getState().queue).toEqual({ paused: false, counts: { queued: 1 }, running: 'job_b' })
    held.length = 0
    route(frame('job.updated', { ...job('job_b', 'done'), wall_s: 3 }))                    // → GET /queue and GET /project
    await settle()
    const project = held.find((h) => h.path === '/project')!
    route(frame('project.closed', {}))
    project.resolve(json({ open: true, name: 'Old' }))
    await settle()
    expect(useSession.getState().project).toEqual({ open: false })
  })
})
