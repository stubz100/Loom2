// D90 (02 §5, inventory F24): the For context of the makers (the origin their jobs carry while the chip is set) and where "Go to origin"
// places a Story job or a job made for a shot.
import { afterEach, describe, expect, it } from 'vitest'
import { FOR_SHOT, forLabel, forOrigin, originFor, originLabel, storyPlace, useMakeFor, type MakeFor } from './origin'

const F: MakeFor = { kind: 'shot', shot_id: 'sht_1', version: 'v3', name: 'Shot 12', node_id: 'node_9' }
afterEach(() => useMakeFor.setState({ generate: null, animate: null }))

describe('the For context (D90 02 §5)', () => {
  it('labels the chip and builds the for_shot origin with the maker’s own ref', () => {
    expect(forLabel(F)).toBe('Shot 12 · v3')
    expect(forOrigin(F, 'animate', 'clp_on_screen')).toEqual({ suite: 'animate', surface: FOR_SHOT, ref: 'clp_on_screen', payload: { shot_id: 'sht_1', version: 'v3', node_id: 'node_9' } })
    expect(forOrigin({ ...F, node_id: null }, 'generate').payload).toEqual({ shot_id: 'sht_1', version: 'v3' })
  })
  it('a maker without a chip submits with its own origin; with one, with the shot’s — each maker its own', () => {
    const own = { suite: 'generate' as const, surface: 'results' }
    expect(originFor('generate', own)).toBe(own)
    useMakeFor.getState().set('animate', F)
    expect(originFor('generate', own)).toBe(own)
    expect(originFor('animate', { suite: 'animate', surface: 'clip', ref: 'clp_1' })).toEqual(forOrigin(F, 'animate', 'clp_1'))
    useMakeFor.getState().set('animate', null)
    expect(originFor('animate', { suite: 'animate', surface: 'clip', ref: null }).surface).toBe('clip')
  })
})

describe('storyPlace (F24)', () => {
  it('places every Story surface and the jobs made for a shot', () => {
    expect(storyPlace({ suite: 'generate', surface: FOR_SHOT, ref: null, payload: { shot_id: 'sht_1', version: 'v2' } })).toEqual({ tab: 'shots', id: 'sht_1', version: 'v2' })
    expect(storyPlace({ suite: 'story', surface: 'expand', ref: 'prf_1', payload: { version: 'v1' } })).toEqual({ tab: 'cast', id: 'prf_1', version: 'v1' })
    expect(storyPlace({ suite: 'story', surface: 'train', ref: 'prf_1', payload: { version: 'v2' } })).toEqual({ tab: 'cast', id: 'prf_1', version: 'v2' })
    expect(storyPlace({ suite: 'story', surface: 'lora_check', ref: 'prf_1', payload: { version: 'v2', lora_id: 'lora_1' } })).toEqual({ tab: 'cast', id: 'prf_1', version: 'v2' })
    expect(storyPlace({ suite: 'story', surface: 'lipsync', ref: 'sht_2', payload: { version: 'v1' } })).toEqual({ tab: 'shots', id: 'sht_2', version: 'v1' })
    expect(storyPlace({ suite: 'story', surface: 'voice', ref: 'node_1', payload: { indexes: [0] } })).toEqual({ tab: 'flow', id: 'node_1' })
    expect(storyPlace({ suite: 'story', surface: 'style', ref: 'sty_1', payload: { group_id: 'grp_1' } })).toEqual({ tab: 'world', id: 'sty_1' })
  })
  it('leaves the other suites and unplaced origins alone', () => {
    expect(storyPlace({ suite: 'generate', surface: 'results', ref: null, payload: null })).toBeNull()
    expect(storyPlace({ suite: 'stage', surface: 'shot', ref: 'stg_1', payload: { camera_id: 'cam_1' } })).toBeNull()      // Stage's own "shot" stays Stage's
    expect(storyPlace({ suite: 'story', surface: 'expand', ref: null, payload: null })).toBeNull()
    expect(storyPlace({ suite: 'generate', surface: FOR_SHOT, ref: null, payload: {} })).toBeNull()
    expect(originLabel({ suite: 'generate', surface: FOR_SHOT, ref: null, payload: { shot_id: 'sht_1', version: 'v2' } })).toBe('World · Make · for a shot · sht_1 v2')
  })
})
