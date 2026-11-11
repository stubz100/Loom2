// RS1 (D197, proto02 01 §4.2): World › Clay's pure parts — the hash's Clay place, the parts each class has, what can stand on a bench, the
// one readiness line (the pictures, then the 3D), and the store's mode kept from one entity to the next.
import { afterEach, describe, expect, it } from 'vitest'
import type { Profile, ProfileVersion } from '../../api/types'
import { useStory } from '../../suites/story/storyStore'
import { entityReadiness } from './readiness'
import { benchable, benchShown, CLAY_TABS, placeOfHash, useWorld } from './worldStore'

const v = (extra: Partial<ProfileVersion> = {}): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_r', candidates_group_id: null, hero_asset_id: null,
  appearance: '', outfit: '', colours: [], marks: '', body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_ref_side_asset_id: null, body_fit_from: null, model_asset_id: null, height_m: null,
  shell_asset_id: null, place_set: null, ...extra }) as unknown as ProfileVersion
const prof = (id: string, cls: Profile['cls'], ver = v()): Profile => ({ id, name: id, cls, current: 'v1', versions: [ver], voice_id: null }) as unknown as Profile

afterEach(() => { useWorld.setState({ rail: 'character', mode: 'make', clayTab: 'build', lineup: false, benchFor: null, selected: null }); useStory.setState({ profiles: [], profileId: null, versionId: null, skeleton: false }) })

describe('RS1: the place', () => {
  it("reads the Clay mode and its part from the hash; the builder is the part when none is named", () => {
    expect(placeOfHash('#world/character/prf_1/v1/clay')).toEqual({ rail: 'character', entity: 'prf_1', version: 'v1', clay: 'build' })
    expect(placeOfHash('#world/character/prf_1/v1/clay/skeleton')).toMatchObject({ clay: 'skeleton' })
    expect(placeOfHash('#world/character/prf_1/v1/clay/poses')).toMatchObject({ clay: 'poses' })
    expect(placeOfHash('#world/place/prf_2/v1/clay/nonsense')).toMatchObject({ clay: 'build' })
    expect(placeOfHash('#world/character/prf_1/v1')).toEqual({ rail: 'character', entity: 'prf_1', version: 'v1' })
  })
  it('a character has Figure · Skeleton · Poses · Bench; a prop Model · Bench; a place Set · Bench', () => {
    expect(CLAY_TABS.character.map((t) => `${t.id}:${t.label}`)).toEqual(['build:Figure', 'skeleton:Skeleton', 'poses:Poses', 'bench:Bench'])
    expect(CLAY_TABS.prop.map((t) => t.label)).toEqual(['Model', 'Bench'])
    expect(CLAY_TABS.place.map((t) => t.label)).toEqual(['Set', 'Bench'])
  })
  it('a character always stands on a bench; a prop with its model; a place with its set', () => {
    expect(benchable({ cls: 'character' }, v())).toBe(true)
    expect([benchable({ cls: 'prop' }, v()), benchable({ cls: 'prop' }, v({ model_asset_id: 'm' }))]).toEqual([false, true])
    expect([benchable({ cls: 'place' }, v()), benchable({ cls: 'place' }, v({ place_set: { faces: [], sources: [] } as never }))]).toEqual([false, true])
    expect(benchable(undefined, undefined)).toBe(false)
    const set = v({ place_set: { faces: [], sources: [] } as never })
    expect([benchShown({ cls: 'place' }, set, 'build'), benchShown({ cls: 'place' }, set, 'bench')]).toEqual([false, true])   // a place's bench only when asked for (D142)
    expect([benchShown({ cls: 'character' }, v(), 'build'), benchShown({ cls: 'character' }, v(), 'skeleton')]).toEqual([true, false])
  })
})

describe('RS1: one readiness line', () => {
  it('a character: the pictures, then the body and the shell — counted together', () => {
    const r = entityReadiness({ cls: 'character', voice_id: null }, v(), 0)
    expect(r.items.map((x) => x.id)).toEqual(['hero', 'references', 'a_pose_front', 'a_pose_back', 'a_pose_side', 'hand_picture', 'feet_picture', 'voice', 'body', 'shell'])
    expect(r.line).toBe('5 to go')
    const done = entityReadiness({ cls: 'character', voice_id: null }, v({ hero_asset_id: 'h', anim_ref_asset_id: 'a', body_fit_from: 'a', shell_asset_id: 's' }), 2)
    expect(done.line).toBe('Ready for a scene')
  })
  it("a prop: its hero, model and height; a place: its set picture, the set built, the faces filled — no picture said twice", () => {
    expect(entityReadiness({ cls: 'prop', voice_id: null }, v({ hero_asset_id: 'h' }), 1).items.map((x) => `${x.id}:${x.state}`)).toEqual(['hero:done', 'reference:optional', 'model:owed', 'height:owed'])
    expect(entityReadiness({ cls: 'place', voice_id: null }, v(), 0).items.map((x) => x.id)).toEqual(['set_picture', 'set', 'faces'])
  })
})

describe('RS1: the mode', () => {
  it('Clay stays the mode from one entity to the next; a part the class has not falls back to its builder; Skeleton follows the part', () => {
    useStory.setState({ profiles: [prof('prf_a', 'character'), prof('prf_b', 'character'), prof('prf_p', 'prop')], profileId: 'prf_a', versionId: 'v1' })
    useWorld.getState().setClayTab('skeleton')
    expect([useWorld.getState().mode, useWorld.getState().clayTab, useStory.getState().skeleton]).toEqual(['clay', 'skeleton', true])
    useWorld.getState().pick('prf_b')
    expect([useWorld.getState().mode, useWorld.getState().clayTab]).toEqual(['clay', 'skeleton'])
    useWorld.getState().pick('prf_p')                                              // a prop has no skeleton
    expect([useWorld.getState().mode, useWorld.getState().clayTab, useStory.getState().skeleton]).toEqual(['clay', 'build', false])
    useWorld.getState().setMode('make')
    useWorld.getState().pick('prf_a')
    expect(useWorld.getState().mode).toBe('make')
  })
  it('openClay lands on the entity, in Clay, on the part asked', () => {
    useStory.setState({ profiles: [prof('prf_a', 'character'), prof('prf_s', 'place')], profileId: 'prf_a', versionId: 'v1' })
    useWorld.getState().openClay('prf_s', 'v1', 'poses')                           // a place has no poses: its builder
    expect([useStory.getState().profileId, useWorld.getState().rail, useWorld.getState().mode, useWorld.getState().clayTab]).toEqual(['prf_s', 'place', 'clay', 'build'])
    expect(location.hash).toBe('#world/place/prf_s/v1/clay')
    useWorld.getState().openClay('prf_a', 'v1', 'poses')
    expect(location.hash).toBe('#world/character/prf_a/v1/clay/poses')
  })
})
