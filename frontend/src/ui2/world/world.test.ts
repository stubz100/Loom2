// U3 (D157, proto01_UI2 03 §2, §5): World's pure parts — the readiness line per class, the role filter, the hash's place.
import { describe, expect, it } from 'vitest'
import type { ProfileVersion } from '../../api/types'
import { readiness } from './readiness'
import { passes, placeOfHash } from './worldStore'
import { activeFraming, FRAMINGS, refTree, to169 } from './make'

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
    const bram = readiness({ cls: 'character', voice_id: null }, v({ anim_ref_asset_id: 'b', body_fit_from: 'b', body: { figure: 'male', height_m: 1.78, build: 'heavy' } as never }), 1)
    expect(bram.items.find((x) => x.id === 'body')!.detail).toBe('♂ 1.78 m · heavy')                       // D168: what the body is
    expect(readiness({ cls: 'character', voice_id: null }, v({ body: { figure: 'male', height_m: 1.78, build: 'heavy' } as never }), 1).items.find((x) => x.id === 'body')!.detail).toBeUndefined()
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

describe('U3d: a prototype\'s name from its sketch', () => {
  it('takes the prompt\'s first words, a JSON prompt\'s subject, else the class', async () => {
    const { nameFrom } = await import('./sketches')
    expect(nameFrom('an old lighthouse keeper, weathered face, at dusk', 'character')).toBe('An old lighthouse keeper')
    expect(nameFrom(JSON.stringify({ subjects: [{ description: 'a rusted ferry bell' }], scene: 'x' }), 'prop')).toBe('A rusted ferry bell')
    expect(nameFrom('', 'place')).toBe('place')
    expect(nameFrom('{broken', 'prop')).toBe('prop')
  })
})

describe('U3e: the Look\'s words', () => {
  it('adds a preset once, after a comma', async () => {
    const { withWords } = await import('./look')
    expect(withWords('', 'film noir')).toBe('film noir')
    expect(withWords('muted teal palette', 'film noir')).toBe('muted teal palette, film noir')
    expect(withWords('muted teal palette, Film Noir', 'film noir')).toBe('muted teal palette, Film Noir')
    expect(withWords('a', '  ')).toBe('a')
  })
})

describe('D162: the framing row', () => {
  const refs = { character: { front: 'Full-body character reference, facing the camera', back: 'Full-body character reference, seen from behind' }, place: { front: 'The place itself, empty' } }
  it('knows which framing the words are — a class framing, a reference framing, or words of the author', () => {
    expect(activeFraming('character', FRAMINGS.character[0].tree.composition!, refs)).toEqual({ id: 'portrait', ref: null })
    expect(activeFraming('character', 'Full-body character reference, seen from behind', refs)?.ref).toMatchObject({ id: 'apose_back', side: 'back' })
    expect(activeFraming('character', 'three-quarter view from below', refs)).toBeNull()                 // the author's own words
    expect(activeFraming('character', '  ', refs)).toBeNull()
    expect(activeFraming('prop', 'The object alone', {})).toBeNull()                                     // a build without the sentence
  })
  it('writes a reference framing as its sentence and its camera, and makes the frame 16:9', () => {
    expect(refTree('character', 'A-pose words', { angle: 'low' })).toEqual({ composition: 'A-pose words', camera: { angle: 'low', distance: 'full shot' } })
    expect(refTree('place', 'empty place', {}).camera).toEqual({ distance: 'wide shot', angle: 'eye level' })
    const [w, h] = to169(1024, 1024)
    expect(w % 16 + h % 16).toBe(0)
    expect(Math.abs(w / h - 16 / 9)).toBeLessThan(0.02)
    expect(Math.abs(w * h - 1024 * 1024) / (1024 * 1024)).toBeLessThan(0.03)                             // about the same pixels
  })
})

