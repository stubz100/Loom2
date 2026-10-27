// The review of 2026-10-27, V66: an `asset.created` frame lands in a list only when the asset belongs to it — its kind, suite and folder
// are checked (a clip never joins Generate's results or an images folder; a documents or imported folder asks the server).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Asset } from '../../api/types'
import { createCatalogueStore } from './catalogueStore'

const asset = (id: string, extra: Partial<Asset> = {}): Asset => ({ id, kind: 'image', suite: 'generate', created_at: '2026-10-27T00:00:00Z', trashed_at: null, tags: [], thumb_status: 'done', ...extra }) as unknown as Asset
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
const frame = (type: string, data: unknown) => ({ seq: 1, type, data }) as never

describe('asset.created in a catalogue store (V66)', () => {
  const requested: string[] = []
  beforeEach(() => {
    requested.length = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(String(input), init)
      const path = new URL(req.url).pathname
      requested.push(path)
      if (path === '/assets/counts') return json({ trash: 0, unprocessed: 1, all: 3 })
      if (path === '/assets/tags') return json({ items: [] })
      if (path === '/assets') return json({ items: [], total: 0, next: null })
      return new Response('not stubbed', { status: 500 })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('a list of one suite or kind takes only what belongs to it', () => {
    const results = createCatalogueStore('test.created.v66a', { suite: 'generate', group: 'none', sort: 'created_desc' } as never)
    results.setState({ items: [asset('old')], total: 1 })
    results.getState().applyEvent(frame('asset.created', asset('clip', { kind: 'video', suite: 'animate' })))   // Animate's clip
    expect(results.getState().items.map((a) => a.id)).toEqual(['old'])
    expect(results.getState().total).toBe(1)
    results.getState().applyEvent(frame('asset.created', asset('mine', { suite: 'generate' })))
    expect(results.getState().items.map((a) => a.id)).toEqual(['mine', 'old'])
    expect(results.getState().total).toBe(2)
    const videos = createCatalogueStore('test.created.v66b', { folder: 'all', kind: 'video', group: 'none', sort: 'created_desc' } as never)
    videos.setState({ items: [], total: 0 })
    videos.getState().applyEvent(frame('asset.created', asset('pic')))
    expect(videos.getState().items).toEqual([])
    videos.getState().applyEvent(frame('asset.created', asset('clip2', { kind: 'video' })))
    expect(videos.getState().items.map((a) => a.id)).toEqual(['clip2'])
  })

  it('the images and clips folders take their kind; documents and imported ask the server', async () => {
    const images = createCatalogueStore('test.created.v66c', { folder: 'images', group: 'none', sort: 'created_desc' } as never)
    images.setState({ items: [], total: 0 })
    images.getState().applyEvent(frame('asset.created', asset('clip', { kind: 'video' })))
    expect(images.getState().items).toEqual([])
    images.getState().applyEvent(frame('asset.created', asset('pic')))
    expect(images.getState().items.map((a) => a.id)).toEqual(['pic'])
    const imported = createCatalogueStore('test.created.v66d', { folder: 'imported', group: 'none', sort: 'created_desc' } as never)
    imported.setState({ items: [], total: 0 })
    requested.length = 0
    imported.getState().applyEvent(frame('asset.created', asset('pic2')))
    expect(imported.getState().items).toEqual([])                                     // not prepended blindly …
    await Promise.resolve()
    expect(requested).toContain('/assets')                                            // … the list is asked for what belongs there
  })
})
