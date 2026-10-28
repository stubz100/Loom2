// D93 (C8): a Stage figure bound to a Cast character — the Inspector's tiles (the characters by their heroes), one figure per character (a
// second binding moves it), the Outliner's tag, "Bind to a character ▸", the mentions the Render tab sends (left to right), and Make frame ▸
// in Stage's pre-binding of the speakers.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Profile, ProfileVersion, StageDoc, StageObject } from '../../api/types'
import { useStory } from '../story/storyStore'
import { BoundTag, FigureCharacter } from './FigureBinding'
import { bindItems } from './stageCommands'
import { st, useStage } from './stageStore'

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_test_clip_id: null, shell_asset_id: null, shell_from: null, poses: {}, from_idea: null, height_m: null, place_set: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null, appearance: '', outfit: '',
  colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v })
const prof = (id: string, name: string, cls: Profile['cls'], versions: ProfileVersion[]): Profile => ({ id, name, cls, current: versions[0].id, schema_version: 2, revision: 0, voice_id: null, created_at: '', updated_at: '', versions })
const MARA = prof('prf_m', 'Mara', 'character', [ver({ group_id: 'grp_m', hero_asset_id: 'ast_hm' }), ver({ id: 'v2', label: 'winter', group_id: 'grp_m2', hero_asset_id: 'ast_hm2' })])
const INES = prof('prf_i', 'Ines', 'character', [ver({ group_id: 'grp_i', hero_asset_id: 'ast_hi' })])
const HARBOUR = prof('prf_h', 'Harbour', 'place', [ver({ group_id: 'grp_h' })])
const fig = (id: string, x: number, extra: Partial<StageObject> = {}): StageObject => ({ id, kind: 'mannequin', name: id, preset: 'adult', asset_id: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, transform: { pos: [x, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1, pose: { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null }, billboard: false, profile_id: null, version: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null, ...extra })
const DOC = { schema_version: 1, id: 'stg_1', name: 'Quay', size: { w: 1920, h: 1080, fps: 24 }, objects: [fig('fig_r', 1.2), fig('fig_l', -1.2)],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1',
  keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' } as unknown as StageDoc
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const obj = (id: string) => useStage.getState().current!.objects.find((o) => o.id === id)!

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('not stubbed', { status: 500 })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useStory.setState({ profiles: [MARA, INES, HARBOUR], profilesLoaded: true })
  useStage.setState({ current: DOC, selected: 'fig_l', undo: [], redo: [] })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers(); vi.unstubAllGlobals()
  useStory.setState({ profiles: [], profilesLoaded: false }); useStage.setState({ current: null, selected: null })
})

describe('D93 (C8) a figure bound to a character', () => {
  it('the Inspector shows the characters by their heroes; a pick binds the figure, a second figure taking the same character moves it', () => {
    const el = render(<FigureCharacter o={obj('fig_l')} />)
    const tiles = [...el.querySelectorAll('[aria-label="the figure\'s character"] button')]
    expect(tiles.map((t) => t.getAttribute('aria-label'))).toEqual(['Mara', 'Ines', 'no character'])        // characters only, no places
    expect(tiles[0].querySelector('img')!.getAttribute('src')).toContain('ast_hm')
    act(() => (tiles[0] as HTMLButtonElement).click())
    expect(obj('fig_l')).toMatchObject({ profile_id: 'prf_m', version: null })
    render(<FigureCharacter o={obj('fig_l')} />)
    expect(el.querySelector('select[aria-label="the character\'s version"]')).not.toBeNull()                  // Mara has two versions: a costume can be pinned
    st().bindFigure('fig_l', 'prf_m', 'v2')
    st().bindFigure('fig_r', 'prf_m')
    expect([obj('fig_l').profile_id, obj('fig_r').profile_id]).toEqual([null, 'prf_m'])                        // one figure per character
    st().bindFigure('fig_l', 'prf_i')
    expect(st().figureMentions()).toEqual([{ profile_id: 'prf_i', figure: 'fig_l' }, { profile_id: 'prf_m', figure: 'fig_r' }])   // left to right on screen
    const tag = render(<BoundTag o={obj('fig_r')} />)
    expect(tag.querySelector('.bound-tag')!.textContent).toBe('Mara'); expect(tag.querySelector('.bound-tag img')!.getAttribute('src')).toContain('ast_hm')
    st().bindFigure('fig_r', null)
    expect(obj('fig_r').profile_id).toBeNull()
    expect(useStage.getState().undo.length).toBe(5)                                                             // every binding is an undoable edit
  })
  it("CS2: a figure bound to a character with a shell casts the shell's shadow; bound elsewhere or unbound, it does not", () => {
    useStory.setState({ profiles: [{ ...MARA, versions: [ver({ group_id: 'grp_m', shell_asset_id: 'ast_shell' }), MARA.versions[1]] }, INES, HARBOUR] })
    st().bindFigure('fig_l', 'prf_m')
    expect(obj('fig_l').shadow_proxy).toBe('ast_shell')
    st().bindFigure('fig_l', 'prf_m', 'v2')
    expect(obj('fig_l').shadow_proxy).toBe('ast_shell')                                                         // v2 has no shell: the figure keeps the one it has
    st().bindFigure('fig_l', 'prf_i')
    expect(obj('fig_l').shadow_proxy).toBeNull()                                                                // Ines' figure: not Mara's shadow
    st().bindFigure('fig_r', 'prf_m'); st().bindFigure('fig_r', null)
    expect(obj('fig_r').shadow_proxy).toBeNull()
  })
  it('"Bind to a character ▸": the characters (the bound one checked), then unbind and open in Cast; a prop has none', () => {
    st().bindFigure('fig_l', 'prf_i')
    const [menu] = bindItems() as { label: string; items: { label?: string; checked?: boolean; cmd?: string }[] }[]
    expect(menu.label).toBe('Bind to a character')
    expect(menu.items.filter((x) => x.label).map((x) => [x.label, !!x.checked])).toEqual([['Mara', false], ['Ines', true]])
    expect(menu.items.filter((x) => x.cmd).map((x) => x.cmd)).toEqual(['stage.figure.unbind', 'stage.figure.openInCast', 'stage.figure.skeleton', 'stage.skeleton.hold', 'stage.skeleton.cast'])   // CS2: the bench; CS3: skeleton keys
    useStage.setState({ current: { ...DOC, objects: [{ ...fig('crate', 0), kind: 'prop' }] }, selected: 'crate' })
    expect(bindItems()).toEqual([])
  })
  it('Make frame ▸ in Stage binds the speakers left to right when the counts match, else leaves it to the author', () => {
    expect(st().prebindSpeakers([MARA, INES])).toBe(2)
    expect([obj('fig_l').profile_id, obj('fig_r').profile_id]).toEqual(['prf_m', 'prf_i'])
    expect(st().prebindSpeakers([MARA])).toBeNull()
  })
  it('D93 follow-up: a newly bound figure wears the pin of the node; a figure already bound to that character keeps its own version', () => {
    expect(st().prebindSpeakers([{ ...MARA, version: 'v2' }, INES])).toBe(2)
    expect([obj('fig_l').version, obj('fig_r').version]).toEqual(['v2', null])
    expect(st().prebindSpeakers([{ ...MARA, version: 'v3' }, { ...INES, version: 'v4' }])).toBe(2)
    expect([obj('fig_l').version, obj('fig_r').version]).toEqual(['v2', null])          // already bound: kept (the Stage binding is the author's)
  })
})
