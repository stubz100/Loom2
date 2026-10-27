// The review of 2026-10-27: V69 — a per-item menu entry's item is set around its run only (never left set after the menu closes, so the
// palette never acts on a stale item); V77 — the shot details keep the same clip map when nothing was missing (a new map made Flow
// re-measure its nodes mid-drag).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { onStoryItem, storyItem } from './storyCommands'
import { useStory } from './storyStore'

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })

describe('per-item menu entries (V69)', () => {
  it('the item is there for the run and gone after it, also when the run throws', () => {
    const on = onStoryItem({ take: { kind: 'clip', id: 'clp_1' } })
    expect(storyItem.take).toBeUndefined()
    expect(on(() => storyItem.take?.id)).toBe('clp_1')
    expect(storyItem.take).toBeUndefined()
    expect(() => on(() => { throw new Error('refused') })).toThrow('refused')
    expect(storyItem.take).toBeUndefined()
    const face = onStoryItem({ face: 'floor' })
    expect(face(() => storyItem.face)).toBe('floor')
    expect(storyItem.face).toBeUndefined()
  })
})

describe('the shot details (V77)', () => {
  const requested: string[] = []
  beforeEach(() => {
    requested.length = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : String(input)).pathname
      requested.push(path)
      if (path === '/stages') return json({ items: [{ id: 'stg_1', name: 'Kitchen', revision: 3 }] })
      if (path.startsWith('/clips/')) return json({ id: path.slice(7), asset_id: 'ast_c', frames: 81, w: 832, h: 480 })
      return new Response('not stubbed', { status: 500 })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('keeps the same clip map when nothing was missing, and grows it when something was', async () => {
    const map = { clp_known: { id: 'clp_known', asset_id: 'ast_k', frames: 9, w: 1, h: 1 } }
    const shot = (clip: string) => ({ id: 'sh_1', name: 'S', current: 'v1', versions: [{ id: 'v1', clip_id: clip, takes: [] }] })
    useStory.setState({ shots: [shot('clp_known')], shotId: 'sh_1', shotVersionId: 'v1', clipsById: map as never } as never)
    await useStory.getState().loadShotDetails()
    expect(useStory.getState().clipsById).toBe(map)                                   // the very same object: no re-measure
    expect(useStory.getState().stagesLite).toEqual([{ id: 'stg_1', name: 'Kitchen', revision: 3 }])
    useStory.setState({ shots: [shot('clp_new')] } as never)
    await useStory.getState().loadShotDetails()
    expect(useStory.getState().clipsById).not.toBe(map)
    expect(Object.keys(useStory.getState().clipsById).sort()).toEqual(['clp_known', 'clp_new'])
    expect(requested.filter((p) => p.startsWith('/clips/'))).toEqual(['/clips/clp_new'])
  })
})
