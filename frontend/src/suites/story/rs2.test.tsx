// RS2 (D197 G2; Q13, Q16; PG22): the run form shows what an image → 3D job runs and the run sends it — the version's kept settings, a
// change as its draft, the body of the shell's POST; a reference's make is Make's framing switched on (no job of its own).
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Capabilities, Profile, ProfileVersion } from '../../api/types'
import { useSession } from '../../store/session'
import { useGenerate } from '../generate/generateStore'
import { frameReference } from '../../ui2/world/refFraming'
import { MeshRunForm } from './MeshRunForm'
import { meshKey, useStory } from './storyStore'

const v = (extra: Partial<ProfileVersion> = {}): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_r', candidates_group_id: null, hero_asset_id: null, mesh: null,
  anim_ref_asset_id: 'ast_a', body_fit_from: 'ast_a', shell_asset_id: null, ...extra }) as unknown as ProfileVersion
const prof = (ver: ProfileVersion): Profile => ({ id: 'prf_1', name: 'Mara', cls: 'character', current: 'v1', versions: [ver], voice_id: null }) as unknown as Profile
const MESH = { model_id: 'pixal3d-test', label: 'Pixal3D · image → mesh', short: 'Pixal3D', health: 'present', missing: [], seconds: 243, cold_seconds: 361, resolutions: [1024, 1536], faces: 50000,
  faces_min: 2000, faces_max: 700000, models: [{ id: 'pixal3d-test', label: 'Pixal3D · image → mesh', short: 'Pixal3D', hint: null, seconds: 243 }], licences: {}, approx_gb: 1 }

let host: HTMLDivElement | null = null
beforeEach(() => { useSession.setState({ capabilities: { mesh: MESH, story: { model_id: 'klein-test', references: { character: { front: 'Full-body character reference, front view.', back: 'From behind.' } } } } as unknown as Capabilities }) })
afterEach(() => { host?.remove(); host = null; vi.unstubAllGlobals(); useStory.setState({ profiles: [], profileId: null, versionId: null, meshDraft: {} }) })

const mount = (p: Profile) => {
  host = document.createElement('div'); document.body.appendChild(host)
  const root = createRoot(host)
  act(() => root.render(<MeshRunForm p={p} v={p.versions[0]} testId="shell-run-form" />))
  return host
}

describe('RS2: the image → 3D run form', () => {
  it('shows the one model as a tile and the measured defaults; a kept setting shows as kept', () => {
    const h = mount(prof(v()))
    expect([...h.querySelectorAll<HTMLElement>('.model-card')].map((c) => `${c.dataset.model}:${c.classList.contains('active')}`)).toEqual(['pixal3d-test:true'])
    expect(h.querySelector('[data-field="resolution"] button.active')!.textContent).toBe('1024')
    expect(h.querySelector<HTMLInputElement>('[data-field="faces"] input')!.value).toBe('50000')
    expect(h.querySelector<HTMLInputElement>('[data-field="seed"] input')!.value).toBe('0')
    expect(h.querySelector('.run-cost')!.textContent).toBe('≈ 4 min warm · 6 min cold')
    host!.remove()
    const kept = mount(prof(v({ mesh: { model_id: null, resolution: 1536, faces: 120000, seed: 7 } })))
    expect(kept.querySelector('[data-field="resolution"] button.active')!.textContent).toBe('1536')
    expect(kept.querySelector<HTMLInputElement>('[data-field="faces"] input')!.value).toBe('120000')
    expect(kept.querySelector('.run-cost')!.textContent).toContain('not measured yet')               // T8: no estimate invented for 1536
  })

  it("a change is the version's draft, and the make sends it as the job's settings", async () => {
    const p = prof(v())
    useStory.setState({ profiles: [p], profileId: 'prf_1', versionId: 'v1' })
    const h = mount(p)
    act(() => { [...h.querySelectorAll<HTMLButtonElement>('[data-field="resolution"] button')].find((b) => b.textContent === '1536')!.click() })
    expect(useStory.getState().meshDraft[meshKey('prf_1', 'v1')]).toEqual({ model_id: null, resolution: 1536, faces: 50000, seed: 0 })
    const sent: { url: string; body: unknown }[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(input, init)
      sent.push({ url: `${req.method} ${new URL(req.url).pathname}`, body: req.method === 'POST' ? await req.clone().json().catch(() => null) : null })
      return new Response(JSON.stringify({ job_id: 'job_1', source_asset_id: 'ast_a', model_id: 'pixal3d-test' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    await useStory.getState().makeShell()
    expect(sent[0]).toEqual({ url: 'POST /story/profiles/prf_1/versions/v1/shell', body: { model_id: null, resolution: 1536, faces: 50000, seed: 0 } })
    expect(useStory.getState().meshDraft[meshKey('prf_1', 'v1')]).toBeUndefined()                      // sent: the version keeps it now
    await useStory.getState().makeShell()
    expect(sent[1].body).toBeNull()                                                                    // no draft: the server runs what the version keeps
  })
})

describe('RS2 (PG22): a reference is framed in Make', () => {
  it("turns Make's framing on at D177's 2:3 for an A-pose and queues nothing", () => {
    useGenerate.getState().set({ width: 1280, height: 720, prompt_mode: 'tree', ref_framing: null })
    expect(frameReference('character', 'back')).toBe(true)
    const panel = useGenerate.getState().panel
    expect([panel.ref_framing, panel.width, panel.height]).toEqual(['apose_back', 784, 1168])
    expect(panel.tree.composition).toBe('From behind.')
    expect(frameReference('character', 'side')).toBe(false)                                            // no sentence for it in this build
  })
})
