// D110 (PS1): props have their own Story tab beside Cast — a profile lives on the tab of its class, and Props shares Cast's verbs.
import { describe, expect, it } from 'vitest'
import { inTab, latestModelJob, modelSource, modelStale, tabOfClass } from './storyStore'
import type { Job } from '../../api/types'
import { ownedBy } from './storyKeys'

describe('the Props tab (D110 PS1)', () => {
  it('puts a prop on Props and a character or a place on Cast', () => {
    expect(tabOfClass('prop')).toBe('props')
    expect(tabOfClass('character')).toBe('cast')
    expect(tabOfClass('place')).toBe('cast')
  })
  it('shows each profile on its own tab only', () => {
    expect(inTab({ cls: 'prop' }, 'props')).toBe(true)
    expect(inTab({ cls: 'prop' }, 'cast')).toBe(false)
    expect(inTab({ cls: 'character' }, 'props')).toBe(false)
    expect(inTab({ cls: 'place' }, 'cast')).toBe(true)
  })
  it('gives Props the Cast version page\'s commands', () => {
    expect(ownedBy('props', { id: 'story.cast.makeAnimRef' })).toBe(true)
    expect(ownedBy('props', { id: 'story.world.remove' })).toBe(false)
  })
})

describe('the prop\'s 3D model (D110 PS2)', () => {
  const v = (p: Partial<{ anim_ref_asset_id: string | null; hero_asset_id: string | null; model_asset_id: string | null; model_from: string | null }>) =>
    ({ anim_ref_asset_id: null, hero_asset_id: null, model_asset_id: null, model_from: null, ...p })
  it('is made from the animation reference, else the hero', () => {
    expect(modelSource(v({ anim_ref_asset_id: 'ast_ref', hero_asset_id: 'ast_hero' }))).toBe('ast_ref')
    expect(modelSource(v({ hero_asset_id: 'ast_hero' }))).toBe('ast_hero')
    expect(modelSource(v({}))).toBeNull()
  })
  it('is stale once the image it was made from is no longer the source', () => {
    expect(modelStale(v({ hero_asset_id: 'ast_hero', model_asset_id: 'ast_m', model_from: 'ast_hero' }))).toBe(false)
    expect(modelStale(v({ anim_ref_asset_id: 'ast_ref', hero_asset_id: 'ast_hero', model_asset_id: 'ast_m', model_from: 'ast_hero' }))).toBe(true)
    expect(modelStale(v({ hero_asset_id: 'ast_hero' }))).toBe(false)
  })
  it('finds the version\'s latest model job by its origin', () => {
    const job = (id: string, created: string, version: string, surface = 'prop_model') =>
      ({ id, kind: 'image_to_mesh', created_at: created, status: 'running', origin: { suite: 'story', surface, ref: 'prf_c', payload: { version } } }) as unknown as Job
    const jobs = { a: job('a', '1', 'v1'), b: job('b', '2', 'v1'), c: job('c', '3', 'v2'), d: job('d', '4', 'v1', 'mesh') }
    expect(latestModelJob(jobs, 'prf_c', 'v1')?.id).toBe('b')
    expect(latestModelJob(jobs, 'prf_c', 'v3')).toBeUndefined()
  })
})
