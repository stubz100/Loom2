// D68 (ArtCraft P6): the Generate panel's prompt tree ↔ JSON and panel ↔ recipe conversions. Model ids come from a capabilities
// fixture (D65: the app names none; a test fixture may).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Capabilities } from '../../api/types'
import { useSession } from '../../store/session'
import type { Job } from '../../api/types'
import { cleanTree, DEFAULT_PANEL, latestResult, panelFromRecipe, recipeFromPanel, treeFromJson, withoutForeignLinks, type Panel, type Tree } from './generateStore'

const CAPS = {
  defaults: { t2i: 'fixture-turbo' },
  models: {
    'fixture-turbo': { order: 1, short: 'Turbo', turbo: true, recipes: {} },
    'fixture-plain': { order: 2, short: 'Plain', turbo: false, recipes: {} },
  },
} as unknown as Capabilities

beforeEach(() => useSession.setState({ capabilities: CAPS }))
afterEach(() => useSession.setState({ capabilities: null }))

const FULL_JSON = {
  scene: 'a harbour at dawn', style: 'ink wash', lighting: 'low sun', mood: 'quiet', background: 'fog', composition: 'rule of thirds',
  subjects: [{ description: 'a fisher', position: 'left', action: 'mending a net', pose: 'kneeling', color_match: 'exact' }],
  color_palette: ['#223344', '#ddeeff'],
  camera: { angle: 'low', lens: '35mm', depth_of_field: 'shallow', 'f-number': 'f/2.8', distance: 'medium' },
}

describe('cleanTree', () => {
  it('drops empty leaves, empty lists, blank subjects and an empty camera', () => {
    const t: Tree = { scene: 'x', style: '', subjects: [{ description: '  ', position: '', action: '' }, { description: 'cat', position: '', color_match: 'exact' }], color_palette: [], camera: { angle: '', lens: '' }, mood: undefined }
    expect(cleanTree(t)).toEqual({ scene: 'x', subjects: [{ description: 'cat', color_match: 'exact' }] })
  })
  it('keeps a subject that has only an action or a pose', () => {
    expect(cleanTree({ subjects: [{ description: '', action: 'runs' }] })).toEqual({ subjects: [{ action: 'runs' }] })
  })
  it('keeps a partly filled camera', () => {
    expect(cleanTree({ camera: { angle: 'top', lens: '' } })).toEqual({ camera: { angle: 'top' } })
  })
})

describe('treeFromJson', () => {
  it('round-trips every schema field through cleanTree', () => {
    expect(cleanTree(treeFromJson(FULL_JSON))).toEqual(FULL_JSON)
  })
  it('fills a missing colour match with exact and stringifies non-strings', () => {
    const t = treeFromJson({ scene: 3, subjects: [{ description: 'dog' }], color_palette: [1, 'red'], lighting: { k: 1 } })
    expect(t.scene).toBe('3')
    expect(t.lighting).toBe('{"k":1}')
    expect(t.subjects).toEqual([{ description: 'dog', position: '', action: '', pose: '', color_match: 'exact' }])
    expect(t.color_palette).toEqual(['1', 'red'])
  })
  it('starts from an empty tree (unknown keys are ignored, no shared subject list)', () => {
    const a = treeFromJson({ weather: 'rain' }), b = treeFromJson({})
    expect(cleanTree(a)).toEqual({})
    a.subjects!.push({ description: 'x' })
    expect(b.subjects).toEqual([])
  })
})

describe('recipeFromPanel ↔ panelFromRecipe', () => {
  const panel: Panel = { ...DEFAULT_PANEL, prompt_mode: 'tree', tree: treeFromJson(FULL_JSON), text: 'extra words', negative: 'blur', model_id: 'fixture-turbo',
    steps: 8, guidance: 3.5, cfg: null, sampler: 'euler', scheduler: null, turbo: true, turbo_strength: 0.8, te_id: 'enc-q4', tiled_vae: true, tile_size: 768,
    seed_mode: 'increment', seed: 41, count: 3, width: 1280, height: 720, refs: [{ asset_id: 'ast_1', note: 'face' }], ref_max_px: 768, loras: [{ model_id: 'lora-x', strength: 0.6 }] }

  it('builds the recipe the server compiles', () => {
    const r = recipeFromPanel(panel)
    expect(r.kind).toBe('t2i')
    expect(r.model_id).toBe('fixture-turbo')
    expect(r.prompt_json).toEqual(FULL_JSON)
    expect(r.seeds).toEqual([41, 42, 43])
    expect(r.refs).toEqual([{ asset_id: 'ast_1', note: 'face' }])
    expect(r.turbo).toBe(true)
  })
  it('round-trips: a panel loaded from a recipe builds the same recipe', () => {
    const r = recipeFromPanel(panel)
    const back: Panel = { ...DEFAULT_PANEL, ...panelFromRecipe(r as unknown as Record<string, unknown>) }
    expect(recipeFromPanel(back, r.seeds)).toEqual(r)
    expect(back.tier).toBe('custom')
    expect(JSON.parse(back.json_text)).toEqual(FULL_JSON)
  })
  it('keeps the first seed on request (re-run), otherwise leaves the seed mode alone', () => {
    const r = recipeFromPanel(panel) as unknown as Record<string, unknown>
    expect(panelFromRecipe(r, true)).toMatchObject({ seed_mode: 'fixed', seed: 41, count: 1 })
    expect(panelFromRecipe(r)).not.toHaveProperty('seed_mode')
  })
  it('follows the seed mode', () => {
    expect(recipeFromPanel({ ...panel, seed_mode: 'random' }).seeds).toEqual([0, 0, 0])
    expect(recipeFromPanel({ ...panel, seed_mode: 'fixed' }).seeds).toEqual([41, 41, 41])
    expect(recipeFromPanel(panel, [7]).seeds).toEqual([7])
  })
  it('resolves the model from the capabilities: empty or stale ids take the t2i default (D65)', () => {
    expect(recipeFromPanel({ ...panel, model_id: '' }).model_id).toBe('fixture-turbo')
    expect(recipeFromPanel({ ...panel, model_id: 'retired-model' }).model_id).toBe('fixture-turbo')
    expect(recipeFromPanel({ ...panel, model_id: 'fixture-plain' }).model_id).toBe('fixture-plain')
    expect(panelFromRecipe({}).model_id).toBe('fixture-turbo')
  })
  it('asks for turbo only where the model has it', () => {
    expect(recipeFromPanel({ ...panel, model_id: 'fixture-plain' }).turbo).toBe(false)
    expect(recipeFromPanel({ ...panel, turbo: false }).turbo).toBe(false)
  })
  it('sends JSON mode as parsed JSON, or none when it does not parse; text mode sends no JSON', () => {
    expect(recipeFromPanel({ ...panel, prompt_mode: 'json', json_text: '{"scene":"s"}' }).prompt_json).toEqual({ scene: 's' })
    expect(recipeFromPanel({ ...panel, prompt_mode: 'json', json_text: '{oops' }).prompt_json).toBeUndefined()
    const t = recipeFromPanel({ ...panel, prompt_mode: 'text', text: 'only words' })
    expect(t.prompt_json).toBeUndefined()
    expect(t.prompt_text).toBe('only words')
    expect(recipeFromPanel({ ...panel, prompt_mode: 'json', json_text: '{}' }).prompt_text).toBe('')
  })
})

// D73 (ArtCraft P12): @mentions go into the recipe only while their @name is written somewhere in the prompt; a stored recipe comes back
// with its mentions unstamped and without the references they gave (the server resolves them again); removing a chip leaves the name as
// plain text; notes are set per reference.
describe('@mentions and notes', () => {
  const hero = { group_id: 'grp_hero', name: 'hero' }, tavern = { group_id: 'grp_tavern', name: 'Old tavern' }
  it('sends only the mentions the prompt still names, from any field of the mode in use', () => {
    const text: Panel = { ...DEFAULT_PANEL, prompt_mode: 'text', text: '@hero walks in', mentions: [hero, tavern] }
    expect(recipeFromPanel(text).mentions).toEqual([hero])
    const tree: Panel = { ...DEFAULT_PANEL, prompt_mode: 'tree', tree: { scene: 'at the @Old tavern', subjects: [{ description: '@hero' }] }, mentions: [hero, tavern] }
    expect(recipeFromPanel(tree).mentions).toEqual([hero, tavern])
    expect(recipeFromPanel({ ...DEFAULT_PANEL, mentions: undefined }).mentions).toEqual([])          // a panel persisted before D73
  })
  it('loads a stored recipe: explicit references stay, the mentions come back unstamped', () => {
    const stored = { kind: 't2i', model_id: 'fixture-turbo', prompt_mode: 'text', prompt_text: '@hero', mentions: [{ ...hero, revision: 4, asset_ids: ['ast_a'] }],
      refs: [{ asset_id: 'ast_x', note: 'the lamp' }, { asset_id: 'ast_a', note: 'hero', mention: 'grp_hero' }] }
    const p = panelFromRecipe(stored)
    expect(p.refs).toEqual([{ asset_id: 'ast_x', note: 'the lamp' }])
    expect(p.mentions).toEqual([hero])
  })
  it('a removed chip leaves the name as plain text everywhere; notes are set per reference', async () => {
    const { useGenerate } = await import('./generateStore')
    useGenerate.setState({ panel: { ...DEFAULT_PANEL, prompt_mode: 'tree', text: '@hero', json_text: '{"scene":"@hero"}', tree: { scene: '@hero by the fire', subjects: [{ description: 'tall @hero' }] }, mentions: [hero, tavern], refs: [{ asset_id: 'ast_1' }] } })
    const g = useGenerate.getState()
    g.removeMention('grp_hero')
    g.setRefNote('ast_1', 'the lamp')
    const p = useGenerate.getState().panel
    expect(p.mentions).toEqual([tavern])
    expect([p.text, p.json_text, p.tree.scene, p.tree.subjects?.[0].description]).toEqual(['hero', '{"scene":"hero"}', 'hero by the fire', 'tall hero'])
    expect(p.refs).toEqual([{ asset_id: 'ast_1', note: 'the lamp' }])
    useGenerate.getState().setRefNote('ast_1', '')
    expect(useGenerate.getState().panel.refs).toEqual([{ asset_id: 'ast_1', note: undefined }])
  })
})

// P14 (D82): the Angle tab's recipe — one random seed per candidate, the move and the method as chosen
describe('reangleRecipe', () => {
  it('builds the reangle body and refuses without a source', async () => {
    const { reangleRecipe, DEFAULT_ANGLE } = await import('./generateStore')
    const r = reangleRecipe({ ...DEFAULT_ANGLE, asset_id: 'ast_1', move: 'wide', count: 3, prompt_text: ' a harbour ' })
    expect(r).toEqual({ kind: 'reangle', asset_id: 'ast_1', move: 'wide', method: 'auto', prompt_text: 'a harbour', seeds: [0, 0, 0] })
    expect(reangleRecipe({ ...DEFAULT_ANGLE, asset_id: 'ast_1', count: 9 }).seeds).toHaveLength(4)
    expect(() => reangleRecipe(DEFAULT_ANGLE)).toThrow()
  })
})

// D90 (B12 / B4): what the panel sends follows the model — the negative where it is honoured, the shift where the graph has
// ModelSamplingFlux, references up to max_refs, the tier's size on a model change — and Ctrl+Enter is gated by the Foot's reason
describe('the model decides (D90)', () => {
  const MODELS = {
    defaults: { t2i: 'fx-flux' },
    tiers: { draft: { flux2: [960, 544], zimage: [1024, 576] }, full: { flux2: [1920, 1088], zimage: [1920, 1088] } },
    models: {
      'fx-flux': { order: 1, family: 'flux2', label: 'Fx Flux', turbo: true, distilled: false, flux_shift: true, max_refs: 2, recipes: {} },
      'fx-zimage': { order: 2, family: 'zimage', label: 'Fx Z', turbo: false, distilled: false, flux_shift: false, max_refs: 0, recipes: {} },
      'fx-distilled': { order: 3, family: 'flux2', label: 'Fx Distilled', turbo: false, distilled: true, flux_shift: true, max_refs: 4, recipes: {} },
    },
  } as unknown as Capabilities
  beforeEach(() => useSession.setState({ capabilities: MODELS }))

  it('sends the negative only where the model honours one, the shift only where the graph has ModelSamplingFlux', async () => {
    const { honoursNegative } = await import('./generateStore')
    const p: Panel = { ...DEFAULT_PANEL, prompt_mode: 'text', text: 'x', negative: 'blur', base_shift: 0.7, max_shift: 1.3 }
    expect(recipeFromPanel({ ...p, model_id: 'fx-flux' })).toMatchObject({ negative: 'blur', base_shift: 0.7, max_shift: 1.3 })
    expect(recipeFromPanel({ ...p, model_id: 'fx-distilled' }).negative).toBe('')
    expect(recipeFromPanel({ ...p, model_id: 'fx-zimage' })).toMatchObject({ negative: 'blur', base_shift: null, max_shift: null })
    expect(honoursNegative(MODELS.models['fx-distilled'])).toBe(false)
  })
  it('a model change re-applies the tier size for its family, keeps a custom size, clears a shift it cannot take and Turbo it lacks', async () => {
    const { modelPatch } = await import('./generateStore')
    const p: Panel = { ...DEFAULT_PANEL, model_id: 'fx-flux', tier: 'full', width: 1920, height: 1088, base_shift: 0.6, max_shift: 1.2, turbo: true }
    expect(modelPatch({ ...p, tier: 'draft' }, 'fx-zimage')).toEqual({ model_id: 'fx-zimage', turbo: false, width: 1024, height: 576, base_shift: null, max_shift: null })
    expect(modelPatch({ ...p, tier: 'custom', width: 800, height: 600 }, 'fx-distilled')).toEqual({ model_id: 'fx-distilled', turbo: false })
    expect(modelPatch(p, 'fx-flux')).toEqual({ model_id: 'fx-flux', turbo: true, width: 1920, height: 1088 })
  })
  it('addRefs takes references up to max_refs and says what did not fit; none on a model that takes none', async () => {
    const { useGenerate } = await import('./generateStore')
    const toasts: string[] = [], toast = useSession.getState().toast
    useSession.setState({ toast: (t: string) => { toasts.push(t) } })
    useGenerate.setState({ panel: { ...DEFAULT_PANEL, model_id: 'fx-flux', refs: [] } })
    expect(useGenerate.getState().addRefs(['a', 'b', 'c'])).toBe(2)
    expect(useGenerate.getState().panel.refs.map((r) => r.asset_id)).toEqual(['a', 'b'])
    expect(toasts.pop()).toMatch(/1 over the limit of 2/)
    expect(useGenerate.getState().addRefs(['a'])).toBe(0)                            // already there: no toast
    expect(toasts).toEqual([])
    useGenerate.getState().addRef('d')
    expect(toasts.pop()).toMatch(/All 2 reference slots are full/)
    useGenerate.setState({ panel: { ...DEFAULT_PANEL, model_id: 'fx-zimage', refs: [] } })
    expect(useGenerate.getState().addRefs(['a'])).toBe(0)
    expect(toasts.pop()).toMatch(/takes no reference images/)
    useSession.setState({ toast })
  })
  it("submitBlock gives the Foot's reason, which also gates Ctrl+Enter and Stage (B4)", async () => {
    const { submitBlock } = await import('./generateStore')
    const pv = { serialized_prompt: 'a harbour', missing: [], estimate: { vram_fit: 'ok' } } as never
    expect(submitBlock({ preview: pv, previewError: null }, false)).toBe('no project')
    expect(submitBlock({ preview: null, previewError: 'bad size' }, true)).toBe('bad size')
    expect(submitBlock({ preview: null, previewError: null }, true)).toBe('preparing…')
    expect(submitBlock({ preview: { ...(pv as object), serialized_prompt: '' } as never, previewError: null }, true)).toBe('empty prompt')
    expect(submitBlock({ preview: { ...(pv as object), missing: [{ model_id: 'w1' }] } as never, previewError: null }, true)).toBe('weights missing: w1')
    expect(submitBlock({ preview: { ...(pv as object), estimate: { vram_fit: 'over' } } as never, previewError: null }, true)).toMatch(/VRAM/)
    expect(submitBlock({ preview: pv, previewError: null }, true)).toBeNull()
  })
})

describe("D92 a saved panel's picture", () => {
  const job = (id: string, finished: string, extra: Partial<Job> = {}): Job => ({ id, kind: 't2i', status: 'done', created_at: '2026-10-17T08:00:00Z', finished_at: finished,
    origin: { suite: 'generate', surface: 'results', ref: null, payload: null }, result: { asset_ids: [`ast_${id}`] }, ...extra }) as unknown as Job
  it("is the newest done Generate image — not a failed job, another suite's or a clip", () => {
    const jobs = Object.fromEntries([
      job('a', '2026-10-17T08:01:00Z'), job('b', '2026-10-17T08:03:00Z'), job('c', '2026-10-17T08:05:00Z', { status: 'failed' } as Partial<Job>),
      job('d', '2026-10-17T08:06:00Z', { origin: { suite: 'story', surface: 'expand', ref: null, payload: null } } as Partial<Job>), job('e', '2026-10-17T08:07:00Z', { kind: 'i2v' } as Partial<Job>),
    ].map((j) => [j.id, j]))
    expect(latestResult(jobs)).toBe('ast_b')
    expect(latestResult({})).toBeNull()
  })
})

describe('D93 (A3) the linked subject the server reads', () => {
  it("is the card's index among the subjects sent — a blank card before it does not shift the binding; the link comes back", () => {
    const panel: Panel = { ...DEFAULT_PANEL, model_id: 'fixture-turbo', prompt_mode: 'tree', tree: { subjects: [{ description: '' }, { description: 'Mara, a courier', profile_id: 'prf_m' }] },
      mentions: [{ group_id: 'grp_m', name: 'Mara', profile_id: 'prf_m' }] }
    const r = recipeFromPanel(panel)
    expect((r.prompt_json as { subjects: unknown[] }).subjects).toEqual([{}])                    // D93 (B4): a linked card sends no words — the server composes its sheet
    expect(r.mentions).toEqual([{ group_id: 'grp_m', name: 'Mara', profile_id: 'prf_m', subject: 0 }])
    expect(panelFromRecipe(r as unknown as Record<string, unknown>).tree?.subjects?.[0].profile_id).toBe('prf_m')
  })
})

describe('withoutForeignLinks (D93)', () => {
  it('drops links to profiles and groups the open project lacks, keeping the words', () => {
    const p: Panel = { ...DEFAULT_PANEL, prompt_mode: 'tree', tree: {
      scene_link: { profile_id: 'prf_gone_place', note: 'rain at dusk' },
      subjects: [{ description: '', profile_id: 'prf_gone', shot_note: 'soaked, hood up', holds: { profile_id: 'prf_here_prop' } }, { description: 'a dog', profile_id: 'prf_here' }],
    }, mentions: [{ group_id: 'g1', name: 'Gone', profile_id: 'prf_gone' }, { group_id: 'g2', name: 'Here', profile_id: 'prf_here' }, { group_id: 'g_album_gone', name: 'Harbour' }, { group_id: 'g_album', name: 'Docks' }] }
    const { patch, dropped } = withoutForeignLinks(p, new Set(['prf_here', 'prf_here_prop']), new Set(['g_album', 'g2']))
    expect(dropped).toBe(3)                                                   // prf_gone, prf_gone_place, g_album_gone
    expect(patch.tree.subjects?.[0]).toMatchObject({ profile_id: undefined, description: 'soaked, hood up', holds: { profile_id: 'prf_here_prop' } })
    expect(patch.tree.subjects?.[1].profile_id).toBe('prf_here')
    expect(patch.tree).toMatchObject({ scene: 'rain at dusk', scene_link: undefined })
    expect(patch.mentions?.map((m) => m.name)).toEqual(['Here', 'Docks'])
    expect(withoutForeignLinks(p, new Set(['prf_gone', 'prf_gone_place', 'prf_here', 'prf_here_prop'])).dropped).toBe(0)   // nothing foreign
  })
})
