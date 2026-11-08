// Review K84: Settings' save is done once the PUT answers — the rescan and /capabilities run after it, side by side, their failure said on
// its own (the save looked failed and the dialog stayed open); a fresh /capabilities brings the cut's strip and grade ranges too.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../api/client'
import { useSession } from './session'

const cut = vi.hoisted(() => ({ applyCutRanges: vi.fn() }))
vi.mock('../suites/story/episode/cut', () => cut)

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
let caps: Response | null = null
const paths: string[] = []

describe('saveSettings (K84)', () => {
  beforeEach(() => {
    paths.length = 0
    cut.applyCutRanges.mockClear()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const req = input instanceof Request ? input : null
      const path = new URL(req ? req.url : String(input)).pathname
      paths.push(`${req?.method ?? 'GET'} ${path}`)
      if (path === '/settings') return json({ variant: 'full', models_root: 'F:/m' })
      if (path === '/models/scan') return json({ items: [], unlisted: [] })
      if (path === '/capabilities') return caps ?? json({ detail: 'down' }, 500)
      return json({ detail: 'no' }, 404)
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' } as never)
    useSession.setState({ toasts: [], settings: null, capabilities: null })
  })
  afterEach(() => { vi.unstubAllGlobals(); caps = null })

  it('a failing /capabilities after the PUT leaves the save saved, said apart', async () => {
    await expect(useSession.getState().saveSettings({ models_root: 'F:/m' })).resolves.toBeUndefined()
    expect(useSession.getState().settings).toMatchObject({ models_root: 'F:/m' })
    const toasts = useSession.getState().toasts.map((t) => [t.kind, t.text])
    expect(toasts[0]).toEqual(['success', 'Settings saved'])
    expect(toasts[1][0]).toBe('error')
    expect(paths).toEqual(expect.arrayContaining(['PUT /settings', 'POST /models/scan', 'GET /capabilities']))
  })
  it('a fresh /capabilities brings the cut ranges with it', async () => {
    caps = json({ models: {}, defaults: {}, cut: { strip: { gain_db: [-36, 36] }, grade: { exposure: [-3, 3] } } })
    await useSession.getState().saveSettings({ models_root: 'F:/m' })
    expect(useSession.getState().capabilities).toMatchObject({ cut: { strip: { gain_db: [-36, 36] } } })
    expect(cut.applyCutRanges).toHaveBeenCalledWith({ gain_db: [-36, 36] }, { exposure: [-3, 3] })
    expect(useSession.getState().toasts.map((t) => t.kind)).toEqual(['success'])
  })
})
