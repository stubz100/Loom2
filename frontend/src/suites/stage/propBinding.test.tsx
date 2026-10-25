// D110 (PS3): a Cast prop placed in the scene — Animate's library places its 3D model bound to the prop; the mesh follows the version's
// model (a pinned version, a remade model); the Inspector binds a mesh to a prop or unbinds it; a prop without a model opens in Story.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Profile, ProfileVersion, StageDoc, StageObject } from '../../api/types'
import { useStory } from '../story/storyStore'
import { BoundTag, LibraryProps, MeshProp } from './FigureBinding'
import { castModel, st, useStage } from './stageStore'

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_test_clip_id: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null, appearance: '', outfit: '',
  colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v })
const prof = (id: string, name: string, cls: Profile['cls'], versions: ProfileVersion[]): Profile => ({ id, name, cls, current: versions[0].id, schema_version: 2, revision: 0, voice_id: null, created_at: '', updated_at: '', versions })
const CHEST = prof('prf_c', 'Chest', 'prop', [ver({ hero_asset_id: 'ast_hc', model_asset_id: 'ast_m1' }), ver({ id: 'v2', label: 'burnt', model_asset_id: 'ast_m2' })])
const LAMP = prof('prf_l', 'Lamp', 'prop', [ver({ hero_asset_id: 'ast_hl' })])                                // no model yet
const MARA = prof('prf_m', 'Mara', 'character', [ver({ hero_asset_id: 'ast_hm' })])
const DOC = { schema_version: 2, id: 'stg_1', name: 'Room', size: { w: 1920, h: 1080, fps: 24 }, objects: [] as StageObject[],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1',
  keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' } as unknown as StageDoc
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const meshes = () => useStage.getState().current!.objects.filter((o) => o.kind === 'mesh')

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('not stubbed', { status: 500 })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useStory.setState({ profiles: [CHEST, LAMP, MARA], profilesLoaded: true })
  useStage.setState({ current: DOC, selected: null, undo: [], redo: [] })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers(); vi.unstubAllGlobals()
  useStory.setState({ profiles: [], profilesLoaded: false }); useStage.setState({ current: null, selected: null })
})

describe('D110 (PS3) props in the scene', () => {
  it('the library lists the props (not the characters); a click places the model bound to the prop, one without a model is not placed', () => {
    const el = render(<LibraryProps centre={() => [1, 0, 2]} />)
    act(() => (el.querySelector('[data-preset-panel-btn]') as HTMLButtonElement).click())             // the Scene's Props +: the panel
    const cards = [...el.querySelectorAll('[data-preset-panel] button.preset-icon')]
    expect(cards.map((c) => c.getAttribute('aria-label'))).toEqual(['Chest', 'Lamp'])
    expect(cards[0].querySelector('img')!.getAttribute('src')).toContain('ast_m1')                            // the model's view
    expect(cards[1].textContent).toContain('!')                                                               // no model: the badge
    act(() => (cards[0] as HTMLButtonElement).click())
    expect(meshes()).toHaveLength(1)
    expect(meshes()[0]).toMatchObject({ name: 'Chest', asset_id: 'ast_m1', profile_id: 'prf_c', version: null, transform: { pos: [1, 0, 2] } })
    expect(st().placeProp('prf_l')).toBeNull()                                                                // no model: nothing placed
    expect(st().placeProp('prf_m')).toBeNull()                                                                // a character is not a prop
    expect(meshes()).toHaveLength(1)
  })
  it('a pinned version brings its own model; a remade model follows; unbinding keeps the mesh', () => {
    const id = st().placeProp('prf_c')!
    st().bindProp(id, 'prf_c', 'v2')
    expect(meshes()[0]).toMatchObject({ asset_id: 'ast_m2', version: 'v2' })
    expect(castModel('prf_c', null)).toBe('ast_m1')
    act(() => { useStory.setState({ profiles: [{ ...CHEST, versions: [CHEST.versions[0], { ...CHEST.versions[1], model_asset_id: 'ast_m3' }] }, LAMP, MARA] }) })
    expect(meshes()[0].asset_id).toBe('ast_m3')                                                               // the remade model, through the profiles' subscription
    st().bindProp(id, null)
    expect(meshes()[0]).toMatchObject({ profile_id: null, version: null, asset_id: 'ast_m3' })
  })
  it('the Inspector binds a mesh to a prop with a model; the Outliner tag shows the prop', () => {
    const id = st().addObject('mesh', null, [0, 0, 0], 'ast_other')!
    const el = render(<MeshProp o={meshes()[0]} />)
    const tiles = [...el.querySelectorAll('[aria-label="the mesh\'s prop"] button')]
    expect(tiles.map((t) => t.getAttribute('aria-label'))).toEqual(['Chest', 'no prop'])                      // props with a model only
    act(() => (tiles[0] as HTMLButtonElement).click())
    expect(meshes()[0]).toMatchObject({ id, profile_id: 'prf_c', asset_id: 'ast_m1' })
    const tag = render(<BoundTag o={meshes()[0]} />)
    expect(tag.textContent).toContain('Chest')
    expect(tag.querySelector('img')!.getAttribute('src')).toContain('ast_m1')
  })
})
