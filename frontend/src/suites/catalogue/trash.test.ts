// The review of 2026-10-27, the Bin's Trash: V62 — a removal counts what the list held (the store and the broadcast both remove); V63 — a
// trash or a restore made in any store reaches every other one's list and Trash count; V64 — a page in flight belongs to its query.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Asset } from '../../api/types'
import { createCatalogueStore } from './catalogueStore'

const asset = (id: string, extra: Partial<Asset> = {}): Asset => ({ id, kind: 'image', suite: 'generate', created_at: '2026-10-27T00:00:00Z', trashed_at: null, tags: [], thumb_status: 'done', ...extra }) as unknown as Asset
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
const tick = () => new Promise<void>((r) => (globalThis as unknown as { setImmediate: (fn: () => void) => void }).setImmediate(r))
const settle = async () => { for (let i = 0; i < 6; i++) await tick() }
const frame = (type: string, data: unknown) => ({ seq: 1, type, data }) as never

describe("the Bin's Trash in the store", () => {
  const calls: { path: string; resolve: (r: Response) => void }[] = []
  beforeEach(() => {
    calls.length = 0
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(String(input), init)
      const path = new URL(req.url).pathname
      if (path === '/assets/counts') return json({ trash: 1, unprocessed: 0, all: 3 })
      if (path === '/assets/tags') return json({ items: [] })
      return new Promise<Response>((resolve) => calls.push({ path, resolve }))
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  })
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

  it('V62: a removal counts what the list held, so the store and the broadcast together take one off, not two', () => {
    const store = createCatalogueStore('test.trash.v62', { folder: 'all', group: 'none' })
    store.setState({ items: [asset('a'), asset('b')], total: 10 })
    store.getState().applyEvent(frame('asset.deleted', { id: 'zzz' }))              // not listed here (another page, another store's)
    expect(store.getState().total).toBe(10)
    store.getState().applyEvent(frame('asset.deleted', { id: 'a' }))
    store.getState().applyEvent(frame('asset.deleted', { id: 'a' }))                 // the broadcast after the store's own removal
    expect(store.getState().items.map((a) => a.id)).toEqual(['b'])
    expect(store.getState().total).toBe(9)
  })

  it('V63: a trash made elsewhere lands in a store on the Trash, a restore leaves it, and the counts follow once', async () => {
    const store = createCatalogueStore('test.trash.v63', { folder: 'trash', group: 'none' })
    store.setState({ items: [], total: 0, counts: {} })
    store.getState().applyEvent(frame('asset.updated', asset('a', { trashed_at: '2026-10-27T01:00:00Z' })))
    store.getState().applyEvent(frame('asset.updated', asset('b', { trashed_at: '2026-10-27T01:00:01Z' })))
    expect(store.getState().items.map((a) => a.id)).toEqual(['b', 'a'])
    expect(store.getState().total).toBe(2)
    const fetched = () => (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.length
    expect(fetched()).toBe(0)                                                        // the counts: one round trip after the frames, not one per frame
    await vi.advanceTimersByTimeAsync(260); await settle()
    expect(fetched()).toBe(2)                                                        // counts + tags
    expect(store.getState().counts.trash).toBe(1)
    store.getState().applyEvent(frame('asset.updated', asset('a', { trashed_at: null })))
    expect(store.getState().items.map((a) => a.id)).toEqual(['b'])
  })

  it('V63: a store on the Library drops a trashed asset and refreshes its count', async () => {
    const store = createCatalogueStore('test.trash.v63b', { folder: 'all', group: 'none' })
    store.setState({ items: [asset('a'), asset('b')], total: 5, counts: {} })
    store.getState().applyEvent(frame('asset.updated', asset('a', { trashed_at: '2026-10-27T01:00:00Z' })))
    expect(store.getState().items.map((a) => a.id)).toEqual(['b'])
    expect(store.getState().total).toBe(4)
    await vi.advanceTimersByTimeAsync(260); await settle()
    expect(store.getState().counts.trash).toBe(1)
  })

  it('V64: a page in flight belongs to its query — a newer load wins', async () => {
    const store = createCatalogueStore('test.trash.v64', { folder: 'all', group: 'none' })
    const first = store.getState().setQuery({ folder: 'all' })
    await settle()
    expect(calls).toHaveLength(1)
    calls[0].resolve(json({ items: [asset('a')], next_cursor: 'c1', total: 2 }))
    await first; await settle()
    expect(store.getState().items.map((a) => a.id)).toEqual(['a'])
    const more = store.getState().loadMore()                                         // the second page, in flight …
    await settle()
    expect(calls).toHaveLength(2)
    const second = store.getState().setQuery({ folder: 'unprocessed' })             // … while the author opens another place
    await settle()
    expect(calls).toHaveLength(3)
    calls[2].resolve(json({ items: [asset('u')], next_cursor: null, total: 1 }))
    await second; await settle()
    calls[1].resolve(json({ items: [asset('a2')], next_cursor: null, total: 2 }))   // the old page lands late
    await more; await settle()
    expect(store.getState().items.map((a) => a.id)).toEqual(['u'])
    expect(store.getState().nextCursor).toBeNull()
    expect(store.getState().loading).toBe(false)
  })
})
