// The review of 2026-11-06 (register K1–K96): K8 — a job that moves a profile on while a sheet field is typed (a hand read, a Fill's face,
// a shell landing) no longer throws the typed words away: they go again on the new revision; a body (one object a fit also writes) stays
// a conflict. K74: a reload while a field waits shows the typed text, not the server's older value.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'
import { useStory } from './storyStore'

type V = { id: string; state: string; appearance: string; body: unknown }
let server: { revision: number; versions: V[] }
const profile = () => ({ id: 'prf_1', name: 'Mara', cls: 'character', current: 'v1', revision: server.revision, versions: server.versions.map((v) => ({ ...v })) })
const patches: { revision: number; body: Record<string, unknown> }[] = []

beforeEach(() => {
  server = { revision: 1, versions: [{ id: 'v1', state: 'open', appearance: '', body: null }] }
  patches.length = 0
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : null
    const url = new URL(req ? req.url : String(input))
    const method = (req?.method ?? init?.method ?? 'GET').toUpperCase()
    if (method === 'GET' && url.pathname === '/story/profiles') return Response.json({ items: [profile()] })
    if (method === 'PATCH' && url.pathname === '/story/profiles/prf_1') {
      const body = JSON.parse(await (req ? req.text() : String(init?.body))) as { revision: number; versions?: Partial<V>[] }
      patches.push({ revision: body.revision, body })
      if (body.revision !== server.revision) return Response.json({ detail: 'stale' }, { status: 409 })
      for (const pv of body.versions ?? []) Object.assign(server.versions.find((v) => v.id === pv.id)!, pv)
      server.revision += 1
      return Response.json(profile())
    }
    if (method === 'PUT' && url.pathname === '/story/profiles/prf_1/versions/v1/shell') { server.revision += 1; return Response.json(profile()) }   // a route that answers with the profile
    return Response.json({ items: [] })
  }))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useSession.setState({ toasts: [] })
  useStory.setState({ profiles: [profile()] as never, profileId: 'prf_1', versionId: 'v1' })
})

describe('K8 profile saves', () => {
  it('typed words survive a job that moved the profile on meanwhile', async () => {
    useStory.getState().setSheet({ appearance: 'red cloak' })
    server.revision = 2                                                  // a hand read landed: the server is one ahead of what was typed on
    await useStory.getState().settleProfiles()
    expect(patches.map((p) => p.revision)).toEqual([1, 2])              // refused once, sent again on the new revision
    expect(server.versions[0].appearance).toBe('red cloak')
    expect(useStory.getState().profiles[0].versions[0].appearance).toBe('red cloak')
    expect(useSession.getState().toasts.map((t) => t.text)).toEqual([])
  })

  it('a body is a real conflict: not sent again', async () => {
    useStory.getState().setSheet({ body: { height_m: 1.6 } as never })
    server.revision = 2                                                  // a fit wrote the body
    await useStory.getState().settleProfiles()
    expect(patches.map((p) => p.revision)).toEqual([1])
    expect(useSession.getState().toasts.map((t) => t.text)).toEqual([expect.stringContaining('not saved')])
  })

  it('a reload while a field waits keeps the typed text on screen', async () => {
    useStory.getState().setSheet({ appearance: 'grey hood' })
    await useStory.getState().loadProfiles()                             // a story.changed from a job, the edit still waiting
    expect(useStory.getState().profiles[0].versions[0].appearance).toBe('grey hood')
    await useStory.getState().settleProfiles()
    expect(server.versions[0].appearance).toBe('grey hood')
  })

  it('K75: a route answering with the profile (a shell picked) keeps the typed words on screen', async () => {
    useStory.getState().setSheet({ hand_words: 'long thin fingers' } as never)
    await useStory.getState().setShell('ast_shell')
    expect((useStory.getState().profiles[0].versions[0] as unknown as { hand_words: string }).hand_words).toBe('long thin fingers')
    await useStory.getState().settleProfiles()
    expect((server.versions[0] as unknown as { hand_words: string }).hand_words).toBe('long thin fingers')
  })
})
