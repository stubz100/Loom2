// D93 (A2) "Add to Cast ▸" (proto01_UIcast CF5: it was "Add to character"): the profile the image was made for comes first under "made
// for", then characters, props and places; each profile offers the hero, the reference set and the candidates as per-item entries that set
// the profile (and the version, and the Bin's tile) around the command; a profile with several open versions offers each; one with every
// version final says why it takes nothing.
import { describe, expect, it } from 'vitest'
import type { Profile } from '../../api/types'
import type { MenuItem } from '../../frame/commands'
import { addToCastItems, castTarget, madeFor, onProfile } from './addToCast'

const p = (id: string, name: string, cls: Profile['cls'], state: 'open' | 'final' = 'open'): Profile => ({
  id, name, cls, current: 'v1', schema_version: 1, revision: 1, voice_id: null, created_at: '', updated_at: '',
  versions: [{ id: 'v1', state, group_id: `grp_${id}`, candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_test_clip_id: null, shell_asset_id: null, shell_from: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null, label: 'v1', appearance: '', outfit: '', colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null }],
})
const PROFILES = [p('lamp', 'Lantern', 'prop'), p('dock', 'Harbour', 'place'), p('mara', 'Mara', 'character'), p('ines', 'Ines', 'character', 'final')]
const words = (items: MenuItem[]) => items.map((i) => ('heading' in i ? `# ${i.heading}` : 'label' in i ? i.label : 'cmd' in i ? i.cmd : '—'))

describe('D93 (A2) Add to Cast ▸', () => {
  it('lists characters, then props, then places, each under its heading', () => {
    expect(words(addToCastItems(PROFILES, []))).toEqual(['# Characters', 'Mara · v1', 'Ines · v1', '# Props', 'Lantern · v1', '# Places', 'Harbour · v1'])
  })
  it('puts the profile the image was made for first, under "made for"', () => {
    const items = addToCastItems(PROFILES, madeFor({ params: { recipe: { mentions: [{ profile_id: 'lamp' }, { profile_id: 'ines', subject: 0 }] } } } as never))
    expect(words(items)).toEqual(['# made for', 'Ines · v1', 'Lantern · v1', '# Characters', 'Mara · v1', '# Places', 'Harbour · v1'])   // the subject-linked one first
  })
  it('each profile offers the three ways in as commands set on it; a final version says why', () => {
    const mara = addToCastItems(PROFILES, []).find((i) => 'label' in i && i.label === 'Mara · v1') as { items: MenuItem[] }
    expect(mara.items.map((i) => ('cmd' in i ? [i.cmd, i.label] : null))).toEqual([['cat.addTo.hero', 'as the hero'], ['cat.addTo.reference', 'into the reference set'], ['cat.addTo.candidate', 'as a candidate']])
    const on = (mara.items[0] as { on: ReturnType<typeof onProfile> }).on
    expect(on(() => castTarget.pid)).toBe('mara')                                     // the command's when / run see the profile …
    expect(castTarget.pid).toBeUndefined()                                            // … and only then
    const ines = addToCastItems(PROFILES, []).find((i) => 'label' in i && i.label === 'Ines · v1') as { items: MenuItem[] }
    expect(words(ines.items)).toEqual(['# every version is final — make a new version to add to it'])
  })
  it('an empty Cast says how to start one; made-for ids of deleted profiles are skipped', () => {
    expect(words(addToCastItems([], ['gone']))).toEqual(['# Nothing in the Cast yet — "Make a character… / place… / prop…" starts one'])
    expect(madeFor(undefined)).toEqual([])
  })
  it("several open versions: each its own entry, the version and the Bin's tile set around the command (CF5)", () => {
    const two = p('kai', 'Kai', 'character')
    two.versions = [{ ...two.versions[0] }, { ...two.versions[0], id: 'v2', label: 'v2' }, { ...two.versions[0], id: 'v3', label: 'v3', state: 'final' }]
    two.current = 'v2'
    const kai = addToCastItems([two], [], ['ast_bin']).find((i) => 'label' in i && i.label === 'Kai') as { items: MenuItem[] }
    expect(words(kai.items)).toEqual(['v1', 'v2 (current)'])                          // the final v3 takes nothing
    const v1 = (kai.items[0] as { items: MenuItem[] }).items
    const on = (v1[1] as { on: ReturnType<typeof onProfile> }).on
    expect(on(() => ({ ...castTarget }))).toEqual({ pid: 'kai', vid: 'v1', ids: ['ast_bin'] })
    expect(castTarget).toEqual({ pid: undefined, vid: undefined, ids: undefined })
  })
})
