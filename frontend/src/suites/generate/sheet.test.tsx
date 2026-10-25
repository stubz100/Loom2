// D93 phase B: the character sheet. (B4) the composition rule — the server's cases, shared (orchestrator/tests/fixtures/sheet_compose.json);
// an old panel's copied description adopted as "this shot"; Cast's sheet saved after a pause, the fields typed together in one PATCH with the
// revision, one save at a time; a linked card shows the sheet (no copied words), sends none, and follows a Cast edit. (B5) the version chip:
// its menu, and a pick that moves the mention to that version's set, its sheet and its name.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import cases from '../../../../orchestrator/tests/fixtures/sheet_compose.json'
import { setBackend } from '../../api/client'
import type { Capabilities, Profile, ProfileVersion } from '../../api/types'
import { useSession } from '../../store/session'
import { useStory } from '../story/storyStore'
import { SubjectCard } from './GenerateColumn'
import { DEFAULT_PANEL, linkedWords, recipeFromPanel, useGenerate } from './generateStore'
import { adoptDescription, composeSheet, versionItems, versionName, versionOf } from './sheet'

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_test_clip_id: null, shell_asset_id: null, shell_from: null, poses: {}, from_idea: null, height_m: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null, appearance: '', outfit: '',
  colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v })
const MARA: Profile = { id: 'prf_m', name: 'Mara', cls: 'character', current: 'v2', schema_version: 2, revision: 3, voice_id: null, created_at: '', updated_at: '',
  versions: [ver({ id: 'v1', label: 'rain gear', group_id: 'grp_m1', appearance: 'Mara, a wiry woman', outfit: 'a yellow oilskin', colours: [{ hex: '#F2A93B', object: 'oilskin' }], hero_asset_id: 'ast_h1' }),
    ver({ id: 'v2', label: 'winter', group_id: 'grp_m2', appearance: 'Mara, a wiry woman', outfit: 'a padded parka', marks: 'round glasses', hero_asset_id: 'ast_h2' })] }

describe('D93 (B4) the composition rule', () => {
  it.each(cases.cases.map((c) => [c.case, c] as const))('%s — as the server composes it', (_, c) => {
    expect(composeSheet(c.sheet as Partial<ProfileVersion>, c.shot, c.name, (c as { cls?: string }).cls)).toBe(c.out)
  })
  it('an old panel\'s copied description: a plain copy goes, words beyond the appearance go to "this shot"', () => {
    const v = MARA.versions[1]
    expect(adoptDescription('Mara, a wiry woman.', v, 'Mara')).toEqual({ note: '' })
    expect(adoptDescription('Mara', v, 'Mara', 'laughing')).toEqual({ note: 'laughing' })
    expect(adoptDescription('Mara, a wiry woman, soaked, hood up', v, 'Mara')).toEqual({ note: 'soaked, hood up' })
    expect(adoptDescription('a tired traveller', v, 'Mara', 'at night')).toEqual({ note: 'at night, a tired traveller' })
    expect(adoptDescription('', v, 'Mara')).toBeNull()
  })
})

describe('D93 (B5) versions', () => {
  it('the chip\'s version: the picked one, else the current; its name says the label', () => {
    expect(versionOf(MARA)?.id).toBe('v2')
    expect(versionOf(MARA, 'v1')?.id).toBe('v1')
    expect(versionOf(MARA, 'v9')?.id).toBe('v2')                                       // a version gone: the current one
    expect(versionName(MARA.versions[0])).toBe('v1 · rain gear')
    expect(versionName(ver({ id: 'v3', label: 'v3' }))).toBe('v3')
  })
  it('the chip\'s menu checks the version in use; picking the current one follows it', () => {
    const pick = vi.fn()
    const items = versionItems(MARA, 'v1', pick, [{ cmd: 'gen.subject.editSheet' }])
    const rows = items.filter((x): x is { label: string; run: () => void; checked?: boolean } => 'run' in x)
    expect(rows.map((r) => [r.label, !!r.checked])).toEqual([['v1 · rain gear', true], ['v2 · winter · current', false]])
    rows[1].run(); rows[0].run()
    expect(pick.mock.calls).toEqual([[undefined], ['v1']])
    expect(items.at(-1)).toEqual({ cmd: 'gen.subject.editSheet' })
  })
})

// ---- the store and the card ---------------------------------------------------------------------------------------------------------
const CAPS = { defaults: { t2i: 'fixture-model' }, models: { 'fixture-model': { order: 1, short: 'M', turbo: false, recipes: { t2i: true }, max_refs: 4 } } } as unknown as Capabilities
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const patches: { url: string; body: Record<string, unknown> }[] = []
let release: (() => void) | null = null

beforeEach(() => {
  vi.useFakeTimers()
  patches.length = 0
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(String(input), init)
    const path = new URL(req.url).pathname
    if (req.method === 'PATCH' && path === '/story/profiles/prf_m') {
      const body = JSON.parse(await req.text()) as { revision: number; versions?: { id: string }[] }
      patches.push({ url: path, body })
      if (patches.length === 1) await new Promise<void>((r) => { release = r })                  // the first save is slow: the next one waits for it
      const cur = useStory.getState().profiles.find((p) => p.id === 'prf_m')!
      return Response.json({ ...cur, revision: body.revision + 1, versions: cur.versions.map((v) => ({ ...v, ...(body.versions?.find((x) => x.id === v.id) ?? {}) })) })
    }
    return new Response('not stubbed', { status: 500 })
  }))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useSession.setState({ capabilities: CAPS })
  useStory.setState({ profiles: [MARA], profilesLoaded: true, profileId: 'prf_m', versionId: 'v2' })
  useGenerate.setState({ panel: { ...DEFAULT_PANEL, model_id: 'fixture-model', prompt_mode: 'tree', tree: { ...DEFAULT_PANEL.tree, subjects: [] }, mentions: [] }, preview: null })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers(); vi.unstubAllGlobals()
  useSession.setState({ capabilities: null }); useStory.setState({ profiles: [], profilesLoaded: false, profileId: null, versionId: null })
})

describe('D93 (B4) Cast\'s sheet saves after a pause, one save at a time', () => {
  it('fields typed together go in one PATCH with the revision; what is typed during a save goes next, with the revision it returned', async () => {
    const st = useStory.getState()
    st.setSheet({ outfit: 'a padded' })
    st.setSheet({ outfit: 'a padded parka, red' })
    st.setSheet({ colours: [{ hex: '#C0392B', object: 'scarf' }] })
    expect(useStory.getState().profiles[0].versions[1]).toMatchObject({ outfit: 'a padded parka, red', colours: [{ hex: '#C0392B', object: 'scarf' }] })   // shown at once
    await vi.advanceTimersByTimeAsync(399)
    expect(patches).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(1)
    expect(patches).toHaveLength(1)
    expect(patches[0].body).toEqual({ revision: 3, versions: [{ id: 'v2', outfit: 'a padded parka, red', colours: [{ hex: '#C0392B', object: 'scarf' }] }] })
    useStory.getState().setSheet({ marks: 'round glasses, a scar' })                   // typed while the first save runs
    await vi.advanceTimersByTimeAsync(500)
    expect(patches).toHaveLength(1)                                                    // one at a time
    release?.()
    await vi.advanceTimersByTimeAsync(10)
    expect(patches).toHaveLength(2)
    expect(patches[1].body).toEqual({ revision: 4, versions: [{ id: 'v2', marks: 'round glasses, a scar' }] })
    expect(useStory.getState().profiles[0].versions[1].marks).toBe('round glasses, a scar')
  })
  it('a final version takes only its label', async () => {
    useStory.setState({ profiles: [{ ...MARA, versions: [MARA.versions[0], { ...MARA.versions[1], state: 'final' }] }] })
    useStory.getState().setSheet({ outfit: 'x' })
    expect(useStory.getState().profiles[0].versions[1].outfit).toBe('a padded parka')
    useStory.getState().setSheet({ label: 'winter 2' })
    expect(useStory.getState().profiles[0].versions[1].label).toBe('winter 2')
  })
})

describe('D93 (B4, B5) a linked card', () => {
  const render = (i = 0) => {
    const s = useGenerate.getState().panel.tree.subjects![i]
    if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
    act(() => root!.render(<SubjectCard i={i} s={s} />))
    return host
  }
  it('shows the sheet from Cast, copies no words, sends none, and follows a Cast edit', () => {
    useGenerate.getState().useAsSubject(MARA)
    const card = render()
    expect(card.querySelector('textarea')).toBeNull()                                  // no description field: nothing copied to edit
    expect(card.querySelector('.subject-sheet')!.textContent).toContain('a padded parka')
    expect(card.querySelector('.version-chip')!.textContent).toContain('v2 · winter')
    const sub = useGenerate.getState().panel.tree.subjects![0]
    expect(sub.description).toBe('')
    expect(recipeFromPanel(useGenerate.getState().panel).prompt_json).toEqual({ subjects: [{ color_match: 'exact' }] })
    // Cast edits the outfit: the card (and the words the server will compose) follow — the panel holds the link, not a copy
    act(() => useStory.getState().setSheet({ outfit: 'a long grey coat' }))
    render()
    expect(card.querySelector('.subject-sheet')!.textContent).toContain('a long grey coat')
    expect(linkedWords(useGenerate.getState().panel.tree.subjects![0])).toBe('Mara, a wiry woman, wearing a long grey coat, round glasses')
    // this shot's override: an outfit for this shot only (the sheet's struck through) and a line after the sheet
    act(() => useGenerate.getState().setSubject(0, { shot_outfit: 'a yellow oilskin', shot_note: 'soaked, hood up' }))
    render()
    expect(card.querySelector('.sheet-row.over')!.textContent).toContain('a long grey coat')
    expect(linkedWords(useGenerate.getState().panel.tree.subjects![0])).toBe('Mara, a wiry woman, wearing a yellow oilskin, round glasses, soaked, hood up')
    expect(recipeFromPanel(useGenerate.getState().panel).mentions).toEqual([{ group_id: 'grp_m2', name: 'Mara', profile_id: 'prf_m', subject: 0, shot: { outfit: 'a yellow oilskin', note: 'soaked, hood up' } }])
  })
  it('the version chip switches the version: the mention\'s set, the sheet shown, the version sent', () => {
    useGenerate.getState().useAsSubject(MARA)
    useGenerate.getState().setSubjectVersion(0, 'v1')
    const card = render()
    expect(card.querySelector('.version-chip')!.textContent).toContain('v1 · rain gear')
    expect(card.querySelector('.version-chip')!.className).toContain('pinned')
    expect(card.querySelector('.subject-sheet')!.textContent).toContain('a yellow oilskin')
    expect(card.querySelector('.subject-sheet img, .linked-to img')!.getAttribute('src')).toContain('ast_h1')   // v1's hero
    const r = recipeFromPanel(useGenerate.getState().panel)
    expect(r.mentions).toEqual([{ group_id: 'grp_m1', name: 'Mara', profile_id: 'prf_m', subject: 0, version: 'v1' }])
    useGenerate.getState().setSubjectVersion(0, undefined)                             // back to the current one: follows it again
    expect(recipeFromPanel(useGenerate.getState().panel).mentions).toEqual([{ group_id: 'grp_m2', name: 'Mara', profile_id: 'prf_m', subject: 0 }])
  })
  it('an old panel\'s copied stub in a linked card is adopted: the copy goes, extra words become "this shot"', () => {
    useGenerate.setState({ panel: { ...useGenerate.getState().panel, tree: { ...DEFAULT_PANEL.tree, subjects: [{ description: 'Mara, a wiry woman, soaked', profile_id: 'prf_m' }] },
      mentions: [{ group_id: 'grp_m2', name: 'Mara', profile_id: 'prf_m' }] } })
    render()
    expect(useGenerate.getState().panel.tree.subjects![0]).toMatchObject({ description: '', shot_note: 'soaked' })
  })
})
