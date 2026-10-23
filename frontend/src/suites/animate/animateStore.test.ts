// D68 (ArtCraft P6): Animate's recipe and size rules against a capabilities fixture (D65: geometry comes from the model specs).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Capabilities, Clip } from '../../api/types'
import { useSession } from '../../store/session'
import { DEFAULT_PANEL, modelRules, recipeFor, sizeFor, useAnimate, visibleClips, type AnimPanel } from './animateStore'

// one model with its own tier table (spec geometry), one that falls back to the family tables, no beats vs beats
const CAPS = {
  defaults: { i2v: 'vid-geo' },
  models: {},
  i2v: {
    models: {
      'vid-geo': { order: 1, short: 'Geo', family: 'geo', fps: 16, frames: 81, frame_step: 4, size_mult: 16, size: [832, 480],
        geometry: { tiers: { draft: [832, 480], hd: [1280, 720], portrait: [480, 832], square: [624, 624] } }, recipes: {} },
      'vid-fam': { order: 2, short: 'Fam', family: 'fam', fps: 24, frames: 97, frame_step: 8, size_mult: 32, size: [768, 512],
        recipes: { beats: true } },
    },
    tiers: { draft: { fam: [768, 448] }, hd: { fam: [1216, 704] } },
    portrait: { fam: [448, 768] },
    square: { fam: [576, 576] },
  },
} as unknown as Capabilities

beforeEach(() => useSession.setState({ capabilities: CAPS }))
afterEach(() => { useSession.setState({ capabilities: null }); vi.useRealTimers() })

describe('modelRules / sizeFor', () => {
  it('reads a model spec’s own tiers', () => {
    expect(modelRules('vid-geo')).toMatchObject({ fps: 16, frames: 81, step: 4, mult: 16, draft: [832, 480], hd: [1280, 720], portrait: [480, 832], square: [624, 624], beats: false })
    expect(sizeFor('vid-geo', 'draft', 'landscape', [1, 1])).toEqual([832, 480])
    expect(sizeFor('vid-geo', 'hd', 'landscape', [1, 1])).toEqual([1280, 720])
    expect(sizeFor('vid-geo', 'draft', 'portrait', [1, 1])).toEqual([480, 832])
    expect(sizeFor('vid-geo', 'hd', 'portrait', [1, 1])).toEqual([720, 1280])
    expect(sizeFor('vid-geo', 'draft', 'square', [1, 1])).toEqual([624, 624])
  })
  it('falls back to the family tables when the spec has no tiers', () => {
    expect(modelRules('vid-fam')).toMatchObject({ fps: 24, frames: 97, step: 8, mult: 32, draft: [768, 448], hd: [1216, 704], portrait: [448, 768], square: [576, 576], beats: true })
    expect(sizeFor('vid-fam', 'hd', 'portrait', [1, 1])).toEqual([704, 1216])
  })
  it('keeps a custom size and uses neutral rules for an unknown model', () => {
    expect(sizeFor('vid-geo', 'custom', 'portrait', [999, 555])).toEqual([999, 555])
    expect(modelRules('nope')).toMatchObject({ fps: 16, frames: 81, draft: [832, 480], short: 'nope', beats: false })
  })
})

describe('recipeFor', () => {
  const p: AnimPanel & { start: string } = { ...DEFAULT_PANEL, start: 'ast_s', end: '', prompt: 'slow push-in', negative: 'blur', use_negative: false,
    model_id: 'vid-geo', frames: 81, fps: 16, width: 832, height: 480, seed_mode: 'increment', seed: 10, count: 3, beats: [{ frame: 40, asset_id: 'ast_b', strength: 0.6 }] }

  it('builds the I2V recipe with seeds per the seed mode', () => {
    const r = recipeFor(p)
    expect(r).toMatchObject({ kind: 'i2v', model_id: 'vid-geo', start_asset: 'ast_s', end_asset: null, prompt_text: 'slow push-in', negative: null, frames: 81, fps: 16, width: 832, height: 480 })
    expect(r.seeds).toEqual([10, 11, 12])
    expect(recipeFor({ ...p, seed_mode: 'fixed' }).seeds).toEqual([10, 10, 10])
    expect(recipeFor({ ...p, seed_mode: 'random' }).seeds).toEqual([0, 0, 0])
    expect(recipeFor(p, [5]).seeds).toEqual([5])
  })
  it('sends the negative only when it is switched on, and the end frame when there is one', () => {
    expect(recipeFor({ ...p, use_negative: true }).negative).toBe('blur')
    expect(recipeFor({ ...p, end: 'ast_e' }).end_asset).toBe('ast_e')
  })
  it('sends beats only to a model that takes them', () => {
    expect(recipeFor(p).beats).toEqual([])
    expect(recipeFor({ ...p, model_id: 'vid-fam' }).beats).toEqual(p.beats)
  })
  it('resolves an empty or stale model to the i2v default (D65)', () => {
    expect(recipeFor({ ...p, model_id: '' }).model_id).toBe('vid-geo')
    expect(recipeFor({ ...p, model_id: 'gone' }).model_id).toBe('vid-geo')
  })
})

describe('panel size snapping', () => {
  beforeEach(() => { vi.useFakeTimers(); useAnimate.setState({ panel: { ...DEFAULT_PANEL, model_id: 'vid-geo', width: 1000, height: 700 } }) })

  it('setModel adopts the model’s fps, frames and tier size, and refuses a model the capabilities do not offer', () => {
    useAnimate.getState().setModel('vid-fam')
    expect(useAnimate.getState().panel).toMatchObject({ model_id: 'vid-fam', fps: 24, frames: 97, width: 768, height: 448 })
    useAnimate.getState().setModel('not-offered')
    expect(useAnimate.getState().panel.model_id).toBe('vid-fam')
  })
  it('setTier snaps to the tier and orientation, custom keeps the size', () => {
    const an = useAnimate.getState()
    an.setTier('hd', 'portrait')
    expect(useAnimate.getState().panel).toMatchObject({ tier: 'hd', orientation: 'portrait', width: 720, height: 1280 })
    useAnimate.getState().setTier('custom')
    expect(useAnimate.getState().panel).toMatchObject({ tier: 'custom', orientation: 'portrait', width: 720, height: 1280 })
    useAnimate.getState().setTier('draft', 'square')
    expect(useAnimate.getState().panel).toMatchObject({ width: 624, height: 624 })
  })
})

describe('visibleClips (D90 02 §9, A16)', () => {
  const clip = (id: string, prompt: string, asset_id: string | null = `ast_${id}`) => ({ id, prompt, asset_id, model_id: 'vid-geo', seed: 7 }) as unknown as Clip
  const clips = [clip('a', 'she walks to the gate'), clip('b', 'rain on the gate'), clip('c', 'a dog runs'), clip('d', 'no asset yet', null)]
  const ids = (cs: Clip[]) => cs.map((c) => c.id)
  it('hides the trashed ones once the live set is known, then filters by words (D122: no keep / reject)', () => {
    expect(ids(visibleClips(clips, null, { q: '' }))).toEqual(['a', 'b', 'c', 'd'])
    expect(ids(visibleClips(clips, { ast_a: true, ast_c: true }, { q: '' }))).toEqual(['a', 'c', 'd'])     // b is in the Trash
    expect(ids(visibleClips(clips, null, { q: 'the GATE' }))).toEqual(['a', 'b'])
    expect(ids(visibleClips(clips, null, { q: 'seed 7 dog' }))).toEqual(['c'])
  })
})
