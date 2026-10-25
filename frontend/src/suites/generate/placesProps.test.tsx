// D93 phase C (C6, C7): a Cast place as the scene — its tiles, the link (the words typed before become this shot's line), the mention sent
// with `scene`, the version chip, unlinking leaves the words; a Cast prop held by a subject card — "holds ▸", the mention with `held_by`, the
// card kept for it alone, JSON mode bakes "holding …" in; Make frame ▸'s pre-fill as linked cards per speaker in Tree mode with the place;
// the Preview's lines for the scene and a held prop; a stored recipe brings both links back.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Binding, Capabilities, Profile, ProfileVersion } from '../../api/types'
import { useSession } from '../../store/session'
import { useStory } from '../story/storyStore'
import { HoldsChip, SceneField } from './GenerateColumn'
import { cleanTree, DEFAULT_PANEL, heldWords, linkedSceneWords, panelFromRecipe, recipeFromPanel, useGenerate } from './generateStore'
import { bindingLines, composedLines, keptSubject, slotsOf } from './subjectCast'

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_test_clip_id: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null, appearance: '', outfit: '',
  colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v })
const prof = (id: string, name: string, cls: Profile['cls'], versions: ProfileVersion[]): Profile => ({ id, name, cls, current: versions[versions.length - 1].id, schema_version: 2, revision: 0, voice_id: null, created_at: '', updated_at: '', versions })
const MARA = prof('prf_m', 'Mara', 'character', [ver({ group_id: 'grp_m', appearance: 'Mara, a wiry courier', hero_asset_id: 'ast_hm' })])
const INES = prof('prf_i', 'Ines', 'character', [ver({ group_id: 'grp_i', appearance: 'a lighthouse keeper', hero_asset_id: 'ast_hi' })])
const HARBOUR = prof('prf_h', 'Harbour', 'place', [ver({ id: 'v1', label: 'day', group_id: 'grp_h1', appearance: 'a stone quay in sunlight', hero_asset_id: 'ast_hh1' }),
  ver({ id: 'v2', label: 'night', group_id: 'grp_h2', appearance: 'a stone quay at night', outfit: 'never sent', marks: 'a broken lamp post', hero_asset_id: 'ast_hh2' })])
const COMPASS = prof('prf_c', 'Compass', 'prop', [ver({ group_id: 'grp_c', appearance: 'a brass compass with a cracked glass', hero_asset_id: 'ast_hc' })])
const CAPS = { defaults: { t2i: 'fixture-model' }, models: { 'fixture-model': { order: 1, short: 'M', turbo: false, recipes: { t2i: true }, max_refs: 4 } } } as unknown as Capabilities
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const g = () => useGenerate.getState()

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('not stubbed', { status: 500 })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useSession.setState({ capabilities: CAPS })
  useStory.setState({ profiles: [MARA, INES, HARBOUR, COMPASS], profilesLoaded: true })
  useGenerate.setState({ panel: { ...DEFAULT_PANEL, model_id: 'fixture-model', prompt_mode: 'tree', text: '', tree: { ...DEFAULT_PANEL.tree, scene: '', subjects: [] }, mentions: [] }, preview: null })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.unstubAllGlobals()
  useSession.setState({ capabilities: null }); useStory.setState({ profiles: [], profilesLoaded: false })
})

describe('D93 (C6) a Cast place is the scene', () => {
  it('the scene row shows the places by their heroes; a pick links it — the words typed become this shot\'s line, the server composes the scene', () => {
    g().setTree({ scene: 'rain on the stones' })
    const el = render(<SceneField />)
    const tiles = el.querySelectorAll('[aria-label="the scene from the Cast\'s places"] img')
    expect([...tiles].map((t) => t.getAttribute('src'))).toEqual([expect.stringContaining('ast_hh2')])     // only the places, at their current version
    g().linkScene(HARBOUR)
    expect(g().panel.tree.scene_link).toEqual({ profile_id: 'prf_h', note: 'rain on the stones' })
    const r = recipeFromPanel(g().panel)
    expect(r.prompt_json).toEqual({})                                                                     // no scene words of the card's own: the server composes them
    expect(r.mentions).toEqual([{ group_id: 'grp_h2', name: 'Harbour', profile_id: 'prf_h', scene: true, shot: { outfit: '', note: 'rain on the stones' } }])
    expect(linkedSceneWords(g().panel.tree.scene_link!)).toBe('a stone quay at night, a broken lamp post, rain on the stones')   // a place wears nothing
    render(<SceneField />)
    expect(el.querySelector('.scene-linked .subject-sheet')!.textContent).toContain('a stone quay at night')
    expect(el.querySelector('.scene-linked .subject-sheet')!.textContent).not.toContain('never sent')
    expect(el.querySelector('.scene-linked .version-chip')!.textContent).toContain('v2 · night')
  })
  it('the chip pins a version (its set and sheet), the slots show the binding, unlink leaves the composed words, a stored recipe brings the link back', () => {
    g().linkScene(HARBOUR)
    g().setSceneLink({ version: 'v1' })
    expect(recipeFromPanel(g().panel).mentions).toEqual([{ group_id: 'grp_h1', name: 'Harbour', profile_id: 'prf_h', scene: true, version: 'v1' }])
    const b: Binding = { subject: null, role: 'scene', name: 'Harbour', profile_id: 'prf_h', version: 'v1', refs: [3, 4], span: 'reference images 3–4', skipped: 1 }
    useGenerate.setState({ preview: { bindings: [b], mentions: [] } as never })
    const el = render(<SceneField />)
    expect(el.querySelector('.scene-linked .subject-slots')!.textContent).toBe('refs 3–4 · 1 left out')
    expect(slotsOf([b], -1, 'scene')).toMatchObject({ label: 'refs 3–4' });  expect(slotsOf([b], 0)).toBeNull()
    const back = panelFromRecipe({ ...recipeFromPanel(g().panel), prompt_json: { scene: 'a stone quay in sunlight' } })
    expect(back.tree?.scene_link).toEqual({ profile_id: 'prf_h', version: 'v1', note: '' });  expect(back.tree?.scene).toBe('')
    g().unlinkScene()
    expect(g().panel.tree).toMatchObject({ scene: 'a stone quay in sunlight', scene_link: undefined });  expect(g().panel.mentions).toEqual([])
  })
})

describe('D93 (C6) a subject card holds a Cast prop', () => {
  it('holds ▸ links the prop: its mention says the holder, a card with nothing else is still sent, the chip says it, put down drops it', () => {
    g().addSubject()
    expect(keptSubject(g().panel.tree.subjects![0])).toBe(false)
    g().holdProp(0, COMPASS)
    expect(keptSubject(g().panel.tree.subjects![0])).toBe(true)
    expect(recipeFromPanel(g().panel).mentions).toEqual([{ group_id: 'grp_c', name: 'Compass', profile_id: 'prf_c', held_by: 0 }])
    expect(cleanTree(g().panel.tree)).toEqual({ subjects: [{ color_match: 'exact' }] })                     // the link is the mention's, the words the server's
    const el = render(<HoldsChip i={0} s={g().panel.tree.subjects![0]} />)
    expect(el.querySelector('.holds-chip')!.textContent).toContain('holds Compass')
    expect(el.querySelector('.holds-chip img')!.getAttribute('src')).toContain('ast_hc')
    g().holdProp(0, null)
    expect(g().panel.mentions).toEqual([]);  expect(g().panel.tree.subjects![0].holds).toBeUndefined()
    render(<HoldsChip i={0} s={g().panel.tree.subjects![0]} />)
    expect(el.querySelector('.holds-btn')!.textContent).toContain('holds ▸')
  })
  it('a linked subject holding a prop: the holder is its index among the cards sent; JSON mode writes "holding …" in; a stored recipe brings it back', () => {
    g().addSubject(); g().addSubject(); g().linkSubject(1, MARA)                                           // a blank card first: not sent
    g().holdProp(1, COMPASS)
    expect(recipeFromPanel(g().panel).mentions).toEqual([{ group_id: 'grp_m', name: 'Mara', profile_id: 'prf_m', subject: 0 }, { group_id: 'grp_c', name: 'Compass', profile_id: 'prf_c', held_by: 0 }])
    expect(heldWords({ profile_id: 'prf_c' })).toBe('a brass compass with a cracked glass')
    const back = panelFromRecipe({ ...recipeFromPanel(g().panel), prompt_json: { subjects: [{ description: 'Mara, a wiry courier', holding: 'a brass compass with a cracked glass' }] } })
    expect(back.tree?.subjects?.[0]).toMatchObject({ profile_id: 'prf_m', holds: { profile_id: 'prf_c' }, description: '' })
    g().treeToJson()
    expect(JSON.parse(g().panel.json_text).subjects).toEqual([{ description: 'Mara, a wiry courier, holding a brass compass with a cracked glass', color_match: 'exact' }])
  })
})

describe('D93 (C7) Make frame ▸ from a Dialogue node', () => {
  it('one linked card per speaker (a version, an action, a pose) in Tree mode, the scene linked to the place; the mentions follow', () => {
    useGenerate.setState({ panel: { ...g().panel, prompt_mode: 'text', text: 'old words' } })
    g().applyFrame({ text: 'At the gate', place: 'prf_h', subjects: [{ profile_id: 'prf_m', action: 'saying Hi there', pose: 'pointing' }, { profile_id: 'prf_i' }] })
    const p = g().panel
    expect(p.prompt_mode).toBe('tree');  expect(p.text).toBe('At the gate')
    expect(p.tree.subjects!.map((s) => [s.profile_id, s.description, s.action, s.pose])).toEqual([['prf_m', '', 'saying Hi there', 'pointing'], ['prf_i', '', '', '']])
    expect(p.tree.scene_link).toEqual({ profile_id: 'prf_h', note: '' })
    const r = recipeFromPanel(p)
    expect(r.mentions).toEqual([{ group_id: 'grp_m', name: 'Mara', profile_id: 'prf_m', subject: 0 }, { group_id: 'grp_i', name: 'Ines', profile_id: 'prf_i', subject: 1 },
      { group_id: 'grp_h2', name: 'Harbour', profile_id: 'prf_h', scene: true }])
    expect(r.prompt_json).toEqual({ subjects: [{ action: 'saying Hi there', pose: 'pointing', color_match: 'exact' }, { color_match: 'exact' }] })
  })
  it('D125 (I1): the next shot replaces the last one\'s content — its subjects, scene, framing, lead text and references — and keeps the look, model and size', () => {
    g().applyFrame({ text: 'At the gate', place: 'prf_h', subjects: [{ profile_id: 'prf_m' }] })
    g().set({ refs: [{ asset_id: 'ast_board' }], tree: { ...g().panel.tree, style: 'ink wash', background: 'fog', composition: 'low', camera: { angle: 'low', lens: '85mm', depth_of_field: '', 'f-number': '', distance: 'close-up' } }, width: 1280, height: 720 })
    const model = g().panel.model_id
    g().applyFrame({ text: null, place: null, subjects: [] })                  // an unbound shot: nothing of its own
    const p = g().panel
    expect(p.tree.subjects).toEqual([]); expect(p.tree.scene_link).toBeUndefined(); expect(p.tree.background).toBe(''); expect(p.tree.composition).toBe('')
    expect(p.tree.camera?.distance).toBe(''); expect(p.tree.camera?.lens).toBe('')
    expect(p.text).toBe(''); expect(p.refs).toEqual([]); expect(p.mentions ?? []).toEqual([])
    expect(p.tree.style).toBe('ink wash'); expect(p.model_id).toBe(model); expect([p.width, p.height]).toEqual([1280, 720])
  })
  it('the Preview says what the scene and a held prop composed and got', () => {
    expect(composedLines([{ scene: true, name: 'Harbour', composed: 'a stone quay' }, { held_by: 1, name: 'Compass', composed: 'a brass compass' }, { subject: 0, name: 'Mara', composed: 'Mara, a courier' }]))
      .toEqual(['the scene · Harbour: a stone quay', 'subject 2 holds · Compass: holding a brass compass', 'subject 1 · Mara: Mara, a courier'])
    expect(bindingLines([{ subject: 1, role: 'held', name: 'Compass', profile_id: 'prf_c', version: 'v1', refs: [4], span: 'reference image 4', skipped: 0 },
      { subject: null, role: 'scene', name: 'Harbour', profile_id: 'prf_h', version: 'v2', refs: [], span: null, skipped: 2 }], 4))
      .toEqual(['subject 2 holds · Compass → reference image 4', 'the scene · Harbour → no reference images · 2 of its set left out (the model takes 4)'])
  })
})
