// D110 (PS1) → D125 (#2): props are the third class of Cast — one class switch (all · characters · places · props), the same version page
// and verbs.
import { describe, expect, it } from 'vitest'
import { latestModelJob, modelSource, modelStale, revealClass, useStory } from './storyStore'
import type { Job } from '../../api/types'
import { ownedBy } from './storyKeys'

describe('props in Cast (D125 #2)', () => {
  it('moves the class switch to a profile it would hide, and leaves "all" alone', () => {
    useStory.setState({ castFilter: 'character' })
    revealClass('prop')
    expect(useStory.getState().castFilter).toBe('prop')
    revealClass('prop')
    expect(useStory.getState().castFilter).toBe('prop')
    useStory.setState({ castFilter: 'all' })
    revealClass('place')
    expect(useStory.getState().castFilter).toBe('all')
  })
  it('gives a prop the Cast version page\'s commands', () => {
    expect(ownedBy('cast', { id: 'story.cast.makeAnimRef' })).toBe(true)
    expect(ownedBy('cast', { id: 'story.cast.makeModel' })).toBe(true)
    expect(ownedBy('cast', { id: 'story.world.remove' })).toBe(false)
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
