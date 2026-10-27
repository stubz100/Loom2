// V79 (the review of 2026-10-27): the stage's debounced saves go out one after another — a save that starts while one is in flight waits
// for its reply and carries the revision it gave, so the author's own edits never answer 409 to each other (the old sequence guard let
// the second PUT carry the pre-reply revision: a 409, the stage reloaded, the edit and both undo stacks lost).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc } from '../../api/types'
import { st, useStage } from './stageStore'

const DOC = () => ({ schema_version: 3, id: 'stg_1', name: 'Quay', purpose: 'stage', bound: null, size: { w: 1920, h: 1080, fps: 24 }, objects: [],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1', keyframes: { camera: {}, objects: {} },
  range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' }) as unknown as StageDoc

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
const tick = () => new Promise<void>((r) => (globalThis as unknown as { setImmediate: (fn: () => void) => void }).setImmediate(r))   // Node's, real under the fake timers
const settle = async () => { for (let i = 0; i < 8; i++) await tick() }

describe('the stage saves in order (V79)', () => {
  const puts: { body: Record<string, unknown>; resolve: (r: Response) => void }[] = []
  beforeEach(() => {
    puts.length = 0
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(String(input), init)
      if (req.method !== 'PUT') return json({})
      const body = JSON.parse(await req.text()) as Record<string, unknown>
      return new Promise<Response>((resolve) => puts.push({ body, resolve }))
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    useStage.setState({ current: DOC(), saving: false, undo: [], redo: [] })
  })
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); useStage.setState({ current: null }) })

  it('a second edit during a PUT waits for the reply and carries its revision', async () => {
    st().apply((d) => ({ ...d, name: 'A' }), 'rename')
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(puts).toHaveLength(1)
    expect(puts[0].body.revision).toBe(1)
    st().apply((d) => ({ ...d, name: 'B' }), 'rename')
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(puts).toHaveLength(1)                                                     // chained: not sent while the first is in flight
    expect(useStage.getState().saving).toBe(true)
    puts[0].resolve(json({ ...DOC(), name: 'A', revision: 2, updated_at: 't2' }))
    await settle()
    expect(puts).toHaveLength(2)
    expect(puts[1].body.revision).toBe(2)                                            // the revision the first reply gave …
    expect(puts[1].body.name).toBe('B')                                              // … with the newest document
    puts[1].resolve(json({ ...DOC(), name: 'B', revision: 3, updated_at: 't3' }))
    await settle()
    expect(useStage.getState().current?.revision).toBe(3)
    expect(useStage.getState().saving).toBe(false)
  })
})
