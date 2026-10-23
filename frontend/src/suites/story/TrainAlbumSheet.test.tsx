// D122: "Train a LoRA on this album…" — the sheet counts the album's images, shares the Cast block's options, refuses under the trainer's
// floor and queues the job on the album (POST /groups/{gid}/train) with the options, then closes.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'
import { useStory } from './storyStore'
import { TrainAlbumSheet } from './TrainAlbumSheet'
import { useTrainAlbum } from './trainAlbum'

const B = { host: '127.0.0.1', port: 8766, token: 't' }
const TRAIN = { available: true, why: null, min_refs: 4, lr: 1e-4, ranks: [8, 16, 32], resolutions: [512, 768], steps: { min: 100, max: 5000, default: 1000 },
  bases: [{ model_id: 'base-a', label: 'Base A', health: 'present', offload: false, vram_gb: 13.6, s_per_it: 1.07 }] }
const img = (id: string, kind = 'image') => [id, { id, kind, trashed_at: null }]
let images = 4
let posted: { url: string; body: Record<string, unknown> } | null = null
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const flush = async () => { for (let i = 0; i < 4; i++) await act(async () => { await Promise.resolve() }) }

beforeEach(() => {
  posted = null
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const req = input instanceof Request ? input : new Request(String(input))
    const url = new URL(req.url)
    if (req.method === 'GET' && url.pathname === '/groups/grp_a')
      return Response.json({ group: { id: 'grp_a', name: 'Neon alleys', items: [] }, assets: Object.fromEntries([...Array.from({ length: images }, (_, i) => img(`a${i}`)), img('v1', 'video')]), groups: {} })
    if (req.method === 'POST' && url.pathname === '/groups/grp_a/train') {
      posted = { url: url.pathname, body: await req.json() }
      return Response.json({ job_id: 'job_1', trigger: 'neonalleys_1a2b', model_id: 'base-a', staged: true })
    }
    return new Response('not stubbed', { status: 500 })
  }))
  setBackend(B)
  useSession.setState({ backend: B, capabilities: { train: TRAIN } as never, refreshAll: vi.fn(async () => undefined) as never, toast: vi.fn() as never })
  useStory.setState({ loadProfiles: vi.fn(async () => undefined) as never, trainOpts: { model_id: null, steps: 300, rank: 16, resolution: 512, name: '', setting: '', stage: true } })
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host)
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.unstubAllGlobals()
  useTrainAlbum.setState({ album: null })
})

describe('D122 Train a LoRA on this album…', () => {
  it('counts the images (not the clips), shows the shared options and queues the job on the album, then closes', async () => {
    act(() => root!.render(<TrainAlbumSheet />))
    expect(host!.querySelector('.train-album')).toBeNull()                                      // closed until an album asks
    act(() => useTrainAlbum.getState().open('grp_a', 'Neon alleys'))
    await flush()
    expect(host!.querySelector('.train-album .head')!.textContent).toContain('Train a LoRA on Neon alleys')
    expect(host!.querySelector('.train-album .foot .estimate')!.textContent).toBe('4 images on the album')
    expect(host!.querySelector('input[aria-label="lora name"]')!.getAttribute('placeholder')).toBe('Neon alleys')
    const go = [...host!.querySelectorAll('.train-album .foot button')].find((b) => b.textContent === 'Train ▶') as HTMLButtonElement
    expect(go.disabled).toBe(false)
    await act(async () => { go.click() })
    await flush()
    expect(posted).toMatchObject({ url: '/groups/grp_a/train', body: { model_id: 'base-a', steps: 300, rank: 16, resolution: 512, stage: true } })
    expect(useTrainAlbum.getState().album).toBeNull()
  })

  it('refuses below the trainer floor and says how many the album has', async () => {
    images = 3
    act(() => root!.render(<TrainAlbumSheet />))
    act(() => useTrainAlbum.getState().open('grp_a', 'Neon alleys'))
    await flush()
    expect(host!.querySelector('.train-album .foot .estimate')!.textContent).toBe('3 images on the album')
    expect(host!.querySelector('.train-album .kv')!.textContent).toContain('3 of 4 images')
    const go = [...host!.querySelectorAll('.train-album .foot button')].find((b) => b.textContent === 'Train ▶') as HTMLButtonElement
    expect(go.disabled).toBe(true)
    images = 4
  })
})
