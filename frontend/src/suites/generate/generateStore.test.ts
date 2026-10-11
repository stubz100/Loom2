// D68 (ArtCraft P6): the Generate panel's prompt tree ↔ JSON and panel ↔ recipe conversions. Model ids come from a capabilities
// fixture (D65: the app names none; a test fixture may).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Capabilities } from '../../api/types'
import { useSession } from '../../store/session'
import { cleanTree, DEFAULT_PANEL, panelFromRecipe, recipeFromPanel, treeFromJson, type Panel, type Tree } from './generateStore'

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
