// U3 (D157, proto01_UI2 03 §2, §5): World's pure parts — the readiness line per class, the role filter, the hash's place.
import { describe, expect, it } from 'vitest'
import type { ProfileVersion } from '../../api/types'
import { readiness } from './readiness'
import { passes, placeOfHash } from './worldStore'

const v = (extra: Partial<ProfileVersion> = {}): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_r', candidates_group_id: null, hero_asset_id: null,
  appearance: '', outfit: '', colours: [], marks: '', body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, body_fit_from: null, model_asset_id: null, height_m: null,
  place_set: null, ...extra }) as unknown as ProfileVersion

describe('U3: the readiness line', () => {
  it('a character owes its hero, references, A-pose front and body fit; the back view and the voice are optional', () => {
    const r = readiness({ cls: 'character', voice_id: null }, v(), 0)
    expect(r.items.map((x) => `${x.id}:${x.state}`)).toEqual(['hero:owed', 'references:owed', 'a_pose_front:owed', 'a_pose_back:optional', 'body:owed', 'voice:optional'])
    expect(r.line).toBe('4 to go')
    const done = readiness({ cls: 'character', voice_id: 'vce_1' }, v({ hero_asset_id: 'a', anim_ref_asset_id: 'b', body_fit_from: 'b' }), 3)
    expect([done.line, done.items.find((x) => x.id === 'references')!.detail]).toEqual(['Ready for Clay', '3'])
  })
  it('a prop owes its hero, model and height; a place its set picture, set and filled faces', () => {
    expect(readiness({ cls: 'prop', voice_id: null }, v({ hero_asset_id: 'a', height_m: 0.3 }), 1).line).toBe('1 to go')
    const faces = [{ filled: true, bad: 0.4 }, { filled: false, bad: 0 }, { filled: false, bad: 0.2 }]
    const place = readiness({ cls: 'place', voice_id: null }, v({ place_set: { kind: 'street', faces, sources: [{ asset_id: 'p' }] } as never }), 0)
    expect(place.items.map((x) => `${x.id}:${x.state}${x.detail ? `:${x.detail}` : ''}`)).toEqual(['set_picture:done', 'set:done', 'faces:owed:67 %'])
  })
})

describe('U3: the bin', () => {
  it('filters by role (references include the hero; A-pose both views)', () => {
    expect(passes({ roles: ['hero'] }, 'reference')).toBe(true)
    expect(passes({ roles: ['a_pose_back'] }, 'a_pose')).toBe(true)
    expect(passes({ roles: ['candidate'] }, 'reference')).toBe(false)
    expect(passes({ roles: [] }, 'all')).toBe(true)
  })
  it('reads its place from the hash', () => {
    expect(placeOfHash('#world/place/prf_1/v2')).toEqual({ rail: 'place', entity: 'prf_1', version: 'v2' })
    expect(placeOfHash('#world')).toEqual({ rail: 'character', entity: null, version: null })
    expect(placeOfHash('#shots/sht_1')).toBeNull()
  })
})
