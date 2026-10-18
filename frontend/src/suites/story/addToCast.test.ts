// D93 (A2) "Add to character ▸": the profile the image was made for comes first under "made for", then characters, props and places; each
// profile offers the hero, the reference set and the candidates as per-item entries that set the profile around the command; a final
// version says why it takes nothing.
import { describe, expect, it } from 'vitest'
import type { Profile } from '../../api/types'
import type { MenuItem } from '../../frame/commands'
import { addToCastItems, castTarget, madeFor, onProfile } from './addToCast'

const p = (id: string, name: string, cls: Profile['cls'], state: 'open' | 'final' = 'open'): Profile => ({
  id, name, cls, current: 'v1', schema_version: 1, revision: 1, voice_id: null, created_at: '', updated_at: '',
  versions: [{ id: 'v1', state, group_id: `grp_${id}`, candidates_group_id: null, hero_asset_id: null, body: null, label: 'v1', appearance: '', outfit: '', colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null }],
})
const PROFILES = [p('lamp', 'Lantern', 'prop'), p('dock', 'Harbour', 'place'), p('mara', 'Mara', 'character'), p('ines', 'Ines', 'character', 'final')]
const words = (items: MenuItem[]) => items.map((i) => ('heading' in i ? `# ${i.heading}` : 'label' in i ? i.label : 'cmd' in i ? i.cmd : '—'))

describe('D93 (A2) Add to character ▸', () => {
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
    expect(words(ines.items)[0]).toBe('# v1 is final — make a new version to add to it')
  })
  it('an empty Cast says how to start one; made-for ids of deleted profiles are skipped', () => {
    expect(words(addToCastItems([], ['gone']))).toEqual(['# No characters yet — "Make a character…" starts one'])
    expect(madeFor(undefined)).toEqual([])
  })
})
