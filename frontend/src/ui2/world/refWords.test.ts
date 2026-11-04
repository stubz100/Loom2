// RG1 (D187, D188): the hand and feet pictures — their words (the server's cases, shared: orchestrator/tests/fixtures/ref_words.json), the
// run's recipe (the framing's sentence and the picture's own words; no subject, no mention, no Look — E62 a), the square frame, the slot's
// read state.
import { afterEach, describe, expect, it } from 'vitest'
import cases from '../../../../orchestrator/tests/fixtures/ref_words.json'
import type { Job, Profile, ProfileVersion } from '../../api/types'
import { DEFAULT_PANEL, recipeFromPanel, type Panel } from '../../suites/generate/generateStore'
import { partRead } from '../../suites/story/partRead'
import { useStory } from '../../suites/story/storyStore'
import { partOf, PART_PX, refFrame, refTree } from './make'
import { partPrompt, partWords, sheetWords } from './refWords'

const v = (extra: Partial<ProfileVersion> = {}): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_r', candidates_group_id: null, hero_asset_id: null,
  appearance: 'a gaunt grey ghoul with long bony fingers and black claws', outfit: 'a tattered robe', colours: [], marks: '', body: null,
  anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_ref_side_asset_id: null, hand_ref_asset_id: null, feet_ref_asset_id: null, hand_words: '', feet_words: '',
  hand_points: null, feet_points: null, hand_note: null, feet_note: null, ...extra }) as unknown as ProfileVersion
const GHOUL = (ver: ProfileVersion): Profile => ({ id: 'prf_g', name: 'Grisk', cls: 'character', current: 'v1', schema_version: 2, revision: 0, voice_id: null, created_at: '', updated_at: '', versions: [ver] }) as unknown as Profile
const HAND = 'A right hand alone, seen from the front with the palm facing the camera, the fingers straight and spread apart, the whole hand and the wrist inside the picture, plain light grey background, soft even studio light'

afterEach(() => useStory.setState({ profiles: [], profilesLoaded: false }))

describe('RG1: the pictures\' words', () => {
  it('the sheet\'s clauses about the hand or the feet, as the server picks them', () => {
    for (const c of cases.cases) {
      expect(sheetWords(c.appearance, c.outfit, c.marks, 'hand')).toBe(c.hand)
      expect(sheetWords(c.appearance, c.outfit, c.marks, 'feet')).toBe(c.feet)
    }
  })
  it('the author\'s own words first; the prompt is the sentence, then the words after a colon (hands.part_prompt)', () => {
    expect(partWords(v(), 'hand')).toBe('a gaunt grey ghoul, long bony fingers and black claws')   // what it is leads (the rig)
    expect(partWords(v({ hand_words: ' four long fingers ' }), 'hand')).toBe('four long fingers')
    expect(partWords(v(), 'feet')).toBe('a gaunt grey ghoul, a tattered robe')
    expect(partPrompt(HAND, ' long bony fingers. ')).toBe(`${HAND}: long bony fingers.`)
    expect(partPrompt(`${HAND}.`, '')).toBe(`${HAND}.`)
  })
})

describe('RG1: the hand and feet framings in World\'s Make', () => {
  it('a square 1024 frame, the sentence alone as the framing words (no camera)', () => {
    expect(partOf('hand')).toBe('hand'); expect(partOf('apose_front')).toBeNull(); expect(partOf(null)).toBeNull()
    expect(refFrame('character', 960, 544, 'hand')).toEqual([PART_PX, PART_PX])
    expect(refTree('character', HAND, DEFAULT_PANEL.tree.camera, 'hand')).toEqual({ composition: HAND })
  })
  it('the run sends the words about the hand alone — no subject, no mention, no Look (E62 a: they drew the whole person)', () => {
    useStory.setState({ profiles: [GHOUL(v({ hand_words: 'long thin grey fingers' }))], profilesLoaded: true })
    const panel: Panel = { ...DEFAULT_PANEL, prompt_mode: 'tree', ref_framing: 'hand', style_id: 'sty_noir',
      tree: { ...DEFAULT_PANEL.tree, composition: HAND, subjects: [{ ...(DEFAULT_PANEL.tree.subjects?.[0] ?? {}), description: '', profile_id: 'prf_g', version: 'v1' } as never] },
      mentions: [{ group_id: 'grp_r', name: 'Grisk', profile_id: 'prf_g' }] }
    const r = recipeFromPanel(panel)
    expect([r.prompt_mode, r.prompt_text, r.prompt_json, r.mentions, r.style_id]).toEqual(['text', `${HAND}: long thin grey fingers.`, undefined, [], null])
    const a = recipeFromPanel({ ...panel, ref_framing: 'apose_front' })                     // an A-pose still carries its subject
    expect([a.prompt_mode, a.mentions?.length]).toEqual(['tree', 1])
  })
})

describe('RG1: the slot says what the read saw', () => {
  const job = (status: string): Record<string, Job> => ({ j1: { id: 'j1', status, origin: { suite: 'story', surface: 'hand_fit', ref: 'prf_g', payload: { version: 'v1' } } } as unknown as Job })
  it('reading, read (its count and middle finger), not read (the note), or not read yet', () => {
    const shape = { right: { count: 4, palm_width: 0.6, claw: 0, fingers: { middle: { base: [0, 1], angle: 0, lengths: [0.4, 0.3, 0.2], width: 0.14, claw: null } } }, left: null }
    const read = v({ hand_ref_asset_id: 'ast_h', hand_points: { from: 'ast_h' }, body: { hand_shape: shape } as never })
    expect(partRead(read, 'hand', job('running'), 'prf_g').state).toBe('reading')
    expect(partRead(read, 'hand', job('done'), 'prf_g')).toEqual({ state: 'read', text: '4 fingers · middle 0.90 palms' })
    expect(partRead(v({ hand_ref_asset_id: 'ast_h', hand_note: 'no hand found in the picture' }), 'hand', {}, 'prf_g')).toEqual({ state: 'failed', text: 'not read', note: 'no hand found in the picture' })
    expect(partRead(v({ hand_ref_asset_id: 'ast_2', hand_points: { from: 'ast_h' } }), 'hand', {}, 'prf_g').state).toBe('unread')   // a newer picture
    const feet = v({ anim_ref_side_asset_id: 'ast_s', feet_points: { from: 'ast_s' }, body: { foot_shape: { right: { pitch: 6.4 }, left: null } } as never })
    expect(partRead(feet, 'feet', {}, 'prf_g')).toEqual({ state: 'read', text: 'read from the side view · pitch 6°' })
  })
})
