// C0 (D181, propo02 04 §4.3): Clay's pure parts — the hash's place, the 3D readiness per class, the shots a scene serves.
import { describe, expect, it } from 'vitest'
import type { ProfileVersion } from '../../api/types'
import { clayReadiness } from './readiness'
import { classOfKind, kindOfClass, placeOfHash, shotsOnStage } from './clayStore'

const v = (extra: Partial<ProfileVersion> = {}): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_r', candidates_group_id: null, hero_asset_id: null,
  appearance: '', outfit: '', colours: [], marks: '', body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_ref_side_asset_id: null, body_fit_from: null, model_asset_id: null, height_m: null,
  shell_asset_id: null, place_set: null, ...extra }) as unknown as ProfileVersion

describe('C0: the Clay readiness', () => {
  it('a figure owes its A-pose (a World picture), body and shell; the back view is optional', () => {
    const r = clayReadiness({ cls: 'character' }, v())
    expect(r.items.map((x) => `${x.id}:${x.state}`)).toEqual(['a_pose:owed', 'body:owed', 'shell:owed', 'back:optional'])
    expect([r.line, r.items[0].detail]).toEqual(['3 to go', '— in World'])
    const done = clayReadiness({ cls: 'character' }, v({ anim_ref_asset_id: 'a', body_fit_from: 'a', shell_asset_id: 's', body: { figure: 'male', height_m: 1.78, build: 'heavy' } as never }))
    expect([done.line, done.items.find((x) => x.id === 'body')!.detail]).toEqual(['Ready for a scene', '♂ 1.78 m · heavy'])   // D168: what the body is
    expect(clayReadiness({ cls: 'character' }, v({ anim_ref_asset_id: 'a', anim_ref_note: 'several' } as never)).items.find((x) => x.id === 'body')).toMatchObject({ state: 'owed', detail: '— the A-pose shows more than one figure' })   // W11
  })
  it('a prop owes its picture, model and height; a set its picture, build and fills', () => {
    expect(clayReadiness({ cls: 'prop' }, v({ hero_asset_id: 'a', height_m: 0.3 })).line).toBe('1 to go')
    const faces = [{ filled: true, bad: 0.4 }, { filled: false, bad: 0 }, { filled: false, bad: 0.2 }]
    const place = clayReadiness({ cls: 'place' }, v({ place_set: { kind: 'street', faces, sources: [{ asset_id: 'p' }] } as never }))
    expect(place.items.map((x) => `${x.id}:${x.state}${x.detail ? `:${x.detail}` : ''}`)).toEqual(['set_picture:done', 'set:done', 'faces:owed:67 %'])
    expect(clayReadiness({ cls: 'place' }, v()).items[0]).toMatchObject({ state: 'owed', detail: '— in World' })
  })
})

describe('C0: the Library and the scenes', () => {
  it('reads its place from the hash — the Library by kind, an asset, its bench; a scene', () => {
    expect(placeOfHash('#clay/library/set/prf_1/v2')).toMatchObject({ rail: 'library', kind: 'set', profile: 'prf_1', version: 'v2', bench: false })
    expect(placeOfHash('#clay/library/figure/prf_1/v1/bench')).toMatchObject({ kind: 'figure', profile: 'prf_1', version: 'v1', bench: true })
    expect(placeOfHash('#clay/library/prop')).toMatchObject({ kind: 'prop', profile: null, bench: false })
    expect(placeOfHash('#clay')).toMatchObject({ rail: 'library', kind: 'figure', profile: null })
    expect(placeOfHash('#clay/scene/stg_1')).toMatchObject({ rail: 'scenes', stage: 'stg_1' })
    expect(placeOfHash('#world/character/prf_1')).toBeNull()
  })
  it('maps a World class to its kind and back', () => {
    expect([kindOfClass('character'), kindOfClass('prop'), kindOfClass('place')]).toEqual(['figure', 'prop', 'set'])
    expect([classOfKind('set'), classOfKind('light'), classOfKind('animation')]).toEqual(['place', null, null])
  })
  it('names the shots whose current version is a camera on the scene', () => {
    const shots = [{ id: 's1', name: 'Arrival', current: 'v2', versions: [{ id: 'v1', stage_id: 'stg_a' }, { id: 'v2', stage_id: 'stg_b' }] },
      { id: 's2', name: 'The seal', current: 'v1', versions: [{ id: 'v1', stage_id: 'stg_a' }] }]
    expect(shotsOnStage('stg_a', shots).map((s) => s.name)).toEqual(['The seal'])
    expect(shotsOnStage('stg_b', shots).map((s) => s.name)).toEqual(['Arrival'])
  })
})
