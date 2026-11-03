// U3 (D157, proto01_UI2 03 §2, §5): World's pure parts — the readiness line per class, the role filter, the hash's place.
import { describe, expect, it } from 'vitest'
import type { ProfileVersion } from '../../api/types'
import { carriedThings, readiness, sheetDrift } from './readiness'
import { passes, placeOfHash } from './worldStore'
import { activeFraming, FRAMINGS, REF_FRAMINGS, refFrame, refTree, to169, to23 } from './make'
import { DEFAULT_PANEL, recipeFromPanel } from '../../suites/generate/generateStore'

const v = (extra: Partial<ProfileVersion> = {}): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_r', candidates_group_id: null, hero_asset_id: null,
  appearance: '', outfit: '', colours: [], marks: '', body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_ref_side_asset_id: null, body_fit_from: null, model_asset_id: null, height_m: null,
  place_set: null, ...extra }) as unknown as ProfileVersion

describe('U3 → C0: the readiness line (the pictures; the 3D is Clay\'s, clay.test.ts)', () => {
  it('a character owes its hero, references and A-pose front; the back and side views and the voice are optional', () => {
    const r = readiness({ cls: 'character', voice_id: null }, v(), 0)
    expect(r.items.map((x) => `${x.id}:${x.state}`)).toEqual(['hero:owed', 'references:owed', 'a_pose_front:owed', 'a_pose_back:optional', 'a_pose_side:optional', 'voice:optional'])
    expect(r.line).toBe('3 to go')
    const done = readiness({ cls: 'character', voice_id: 'vce_1' }, v({ hero_asset_id: 'a', anim_ref_asset_id: 'b' }), 3)
    expect([done.line, done.items.find((x) => x.id === 'references')!.detail]).toEqual(['Pictures done', '3'])
    expect(readiness({ cls: 'character', voice_id: null }, v({ body_fit_from: 'b' }), 1).items.some((x) => x.id === 'body')).toBe(false)   // C0: the body is the Library's
  })
  it('a prop owes its hero (its reference view optional); a place its set picture', () => {
    expect(readiness({ cls: 'prop', voice_id: null }, v({ height_m: 0.3 }), 1).line).toBe('1 to go')
    expect(readiness({ cls: 'prop', voice_id: null }, v({ hero_asset_id: 'a' }), 1).line).toBe('Pictures done')
    const place = readiness({ cls: 'place', voice_id: null }, v({ place_set: { kind: 'street', faces: [], sources: [{ asset_id: 'p' }] } as never }), 0)
    expect(place.items.map((x) => `${x.id}:${x.state}`)).toEqual(['set_picture:done'])
    expect(readiness({ cls: 'place', voice_id: null }, v(), 0).line).toBe('1 to go')
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
  it('D175: a character has a side view among its reference framings', () => {
    expect(REF_FRAMINGS.character.map((f) => f.id)).toEqual(['apose_front', 'apose_back', 'apose_side'])
    expect(activeFraming('character', 'in profile, facing left', { character: { side: 'in profile, facing left' } })?.ref).toMatchObject({ id: 'apose_side', side: 'side' })
  })
  it('D169: a reference framing switched on stays on while its words are edited; off is off; a panel from before reads the words', () => {
    expect(activeFraming('place', 'a long row of stalls seen straight on from across the aisle', refs, 'set_picture')?.ref).toMatchObject({ id: 'set_picture', side: 'front' })
    expect(activeFraming('place', '', refs, 'set_picture')?.id).toBe('set_picture')                     // even with the words cleared
    expect(activeFraming('place', 'The place itself, empty', refs, null)).toBeNull()                    // turned off: the sentence is words
    expect(activeFraming('place', 'The place itself, empty', refs)?.id).toBe('set_picture')             // absent: D162's reading
    expect(activeFraming('character', FRAMINGS.character[0].tree.composition!, refs, null)).toEqual({ id: 'portrait', ref: null })
    expect(activeFraming('character', 'x', refs, 'set_picture')).toBeNull()                             // another class's reference
    expect(activeFraming('prop', 'x', refs, 'reference')).toBeNull()                                    // no sentence for it on this build
  })
  it('writes a reference framing as its sentence and its camera, and makes the frame 16:9', () => {
    expect(refTree('character', 'A-pose words', { angle: 'low' })).toEqual({ composition: 'A-pose words', camera: { angle: 'low', distance: 'full shot' } })
    expect(refTree('place', 'empty place', {}).camera).toEqual({ distance: 'wide shot', angle: 'eye level' })
    const [w, h] = to169(1024, 1024)
    expect(w % 16 + h % 16).toBe(0)
    expect(Math.abs(w / h - 16 / 9)).toBeLessThan(0.02)
    expect(Math.abs(w * h - 1024 * 1024) / (1024 * 1024)).toBeLessThan(0.03)                             // about the same pixels
  })
  it("D177 (W9): an A-pose framing makes a tall 2:3 frame, a prop's view and a set picture 16:9", () => {
    const [w, h] = to23(960, 544)
    expect(w % 16 + h % 16).toBe(0)
    expect(Math.abs(w / h - 2 / 3)).toBeLessThan(0.02)
    expect(Math.abs(w * h - 960 * 544) / (960 * 544)).toBeLessThan(0.04)
    expect(refFrame('character', 960, 544)).toEqual([w, h])
    expect(refFrame('prop', 960, 544)).toEqual(to169(960, 544))
  })
  it("D176 (W8): a reference make leaves the Look's style out; a set picture keeps it", () => {
    const panel = { ...DEFAULT_PANEL, style_id: 'sty_noir' } as never
    expect(recipeFromPanel(panel).style_id).toBe('sty_noir')
    expect(recipeFromPanel({ ...(panel as object), ref_framing: 'apose_front' } as never).style_id).toBeNull()
    expect(recipeFromPanel({ ...(panel as object), ref_framing: 'reference' } as never).style_id).toBeNull()
    expect(recipeFromPanel({ ...(panel as object), ref_framing: 'set_picture' } as never).style_id).toBe('sty_noir')
  })
})


describe('the market walk small items (M3, M4)', () => {
  it('M3: a picture whose prompt bound another colour, or none, disagrees with the sheet — said as a warning, not counted', () => {
    const bram = v({ colours: [{ hex: '#E8E4DA', object: 'rubber apron' }] })
    const tree = '{"subjects":[{"description":"a heavy-set man, wearing a long white rubber apron, #C0392B rubber apron, a faded tattoo"}]}'
    expect(sheetDrift(bram, tree)).toEqual(['rubber apron #C0392B, the sheet #E8E4DA'])
    expect(sheetDrift(bram, 'a heavy-set man, #e8e4da rubber apron. Full-body character reference')).toEqual([])   // a sentence after it, any case
    expect(sheetDrift(bram, 'a heavy-set man')).toEqual(['no rubber apron colour (the sheet #E8E4DA)'])
    expect(sheetDrift(bram, null)).toEqual([])                                                                      // an import says nothing
    expect(sheetDrift(v({ colours: [{ hex: '', object: 'coat' }] }), 'a man')).toEqual([])                         // M1: not picked, not sent
    const r = readiness({ cls: 'character', voice_id: null }, { ...bram, hero_asset_id: 'h', anim_ref_asset_id: 'a', body_fit_from: 'a' } as ProfileVersion, 1,
      { hero: tree, a_pose_front: 'a heavy-set man, #E8E4DA rubber apron' })
    expect(r.items.filter((x) => x.state === 'warn').map((x) => x.label)).toEqual(['hero ≠ sheet'])
    expect(r.line).toBe('Pictures done')
  })
  it('M4: the things the words have a character carry — not what it wears, not its marks', () => {
    expect(carriedThings({ appearance: 'a small elderly woman in her seventies', outfit: 'a long dark-red wool coat, a wicker shopping basket on her arm' })).toEqual(['a wicker shopping basket'])
    expect(carriedThings({ appearance: 'a lamplighter carrying a brass lantern', outfit: 'an umbrella in his left hand' })).toEqual(['a brass lantern'])   // "left" is not read
    expect(carriedThings({ appearance: 'a man with a ring on his hand, a tattoo on his arm', outfit: 'a canvas shoulder bag' })).toEqual([])
    const r = readiness({ cls: 'character', voice_id: null }, v({ outfit: 'a wicker shopping basket on her arm' }), 0)
    expect(r.items.find((x) => x.id === 'carried')).toMatchObject({ label: 'carried: wicker shopping basket', state: 'warn' })
  })
  it('W11: a T-pose is fitted but said (more than one figure is the Library\'s body item, clay.test.ts)', () => {
    const tp = readiness({ cls: 'character', voice_id: null }, v({ anim_ref_asset_id: 'a', body_fit_from: 'a', anim_ref_note: 't_pose' } as never), 1)
    expect(tp.items.find((x) => x.id === 'tpose')).toMatchObject({ state: 'warn' })
  })
})
