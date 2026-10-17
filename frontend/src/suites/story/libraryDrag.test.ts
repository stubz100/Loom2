// D92 (owed): World › Library's drag reorder — the order a drop makes (within the field; the other fields keep their places), the side
// of a tile a drop lands on, and the store's move: the row reorders at once and the whole order goes to PUT /story/library/order.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Library, LibraryEntry } from '../../api/types'
import { useSession } from '../../store/session'
import { sideOf } from './libraryDrag'
import { moveToInField, useLibrary } from './libraryStore'

const E = (id: string, field: string, text: string): LibraryEntry => ({ id, field, name: text, text, source: 'user', group_id: null })
const ENTRIES = [E('l1', 'lighting', 'moonlight'), E('m1', 'mood', 'eerie'), E('l2', 'lighting', 'dusk'), E('c1', 'camera.distance', 'close-up'), E('l3', 'lighting', 'firelight')]
const B = { host: '127.0.0.1', port: 8766, token: 't' }

describe('moveToInField', () => {
  it('puts the entry before / after another of its field; the other fields keep their places', () => {
    expect(moveToInField(ENTRIES, 'l3', 'l1', 'before')).toEqual(['l3', 'm1', 'l1', 'c1', 'l2'])
    expect(moveToInField(ENTRIES, 'l1', 'l3', 'after')).toEqual(['l2', 'm1', 'l3', 'c1', 'l1'])
    expect(moveToInField(ENTRIES, 'l1', 'l2', 'after')).toEqual(['l2', 'm1', 'l1', 'c1', 'l3'])
  })
  it('refuses another field, itself, an unknown id and a drop that changes nothing', () => {
    expect(moveToInField(ENTRIES, 'l1', 'm1', 'before')).toBeNull()
    expect(moveToInField(ENTRIES, 'l1', 'l1', 'after')).toBeNull()
    expect(moveToInField(ENTRIES, 'gone', 'l1', 'after')).toBeNull()
    expect(moveToInField(ENTRIES, 'l1', 'l2', 'before')).toBeNull()                 // already right before it
  })
  it('the left half of a tile is before, the right half after', () => {
    expect(sideOf(10, { left: 0, width: 56 })).toBe('before')
    expect(sideOf(30, { left: 0, width: 56 })).toBe('after')
  })
})

describe('useLibrary.moveTo', () => {
  let sent: unknown = null
  beforeEach(() => {
    sent = null
    const lib: Library = { schema_version: 1, entries: ENTRIES, revision: 4, created_at: '', updated_at: '' }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const req = input as Request
      expect(new URL(req.url).pathname).toBe('/story/library/order')
      sent = await req.json()
      const ids = (sent as { ids: string[] }).ids
      return Response.json({ ...lib, entries: ids.map((x) => ENTRIES.find((e) => e.id === x)), revision: 5 })
    }))
    setBackend(B)
    useSession.setState({ backend: B, toasts: [] })
    useLibrary.setState({ library: lib })
  })
  it('sends the whole order with the revision and keeps the server\'s answer', async () => {
    await useLibrary.getState().moveTo('l3', 'l1', 'before')
    expect(sent).toEqual({ ids: ['l3', 'm1', 'l1', 'c1', 'l2'], revision: 4 })
    expect(useLibrary.getState().library!.revision).toBe(5)
    expect(useLibrary.getState().library!.entries.map((e) => e.id)).toEqual(['l3', 'm1', 'l1', 'c1', 'l2'])
  })
  it('a drop on another field sends nothing', async () => {
    await useLibrary.getState().moveTo('l3', 'm1', 'before')
    expect(sent).toBeNull()
  })
})
