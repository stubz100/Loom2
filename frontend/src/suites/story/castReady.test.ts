// D125 (S5, SP5): Cast's readiness — the items by class, what each use needs, owed / done / open, the next owed item, the row's line.
import { describe, expect, it } from 'vitest'
import type { CastUse, ProfileVersion } from '../../api/types'
import { ITEMS_OF, needsOf, nextOwed, readinessOf, rowSummary, shotNeeds } from './castReady'

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null,
  anim_ref_back_asset_id: null, appearance: '', outfit: '', colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v } as unknown as ProfileVersion)
const use = (name: string, route: string, how: CastUse['how']): CastUse => ({ shot_id: `sht_${name}`, name, version: 'v1', route, how })

describe('Cast readiness (D125 S5)', () => {
  it('a class has its items: no animation reference, body or voice for a place; a 3D model instead of a body for a prop', () => {
    expect(ITEMS_OF.place).toEqual(['hero', 'sheet', 'refs', 'lora', 'final'])
    expect(ITEMS_OF.prop).toContain('model'); expect(ITEMS_OF.prop).not.toContain('body')
  })
  it('a use needs what its route and its part ask for', () => {
    expect(needsOf({ route: 'i2v', how: ['speaker'] }, 'character')).toEqual(['hero', 'sheet', 'refs', 'voice', 'final'])
    expect(needsOf({ route: 'clay1', how: ['figure'] }, 'character')).toEqual(['hero', 'sheet', 'refs', 'animref', 'body', 'final'])
    expect(needsOf({ route: 'stage', how: ['figure'] }, 'character')).not.toContain('body')
    expect(needsOf({ route: 'clay2', how: ['prop'] }, 'prop')).toEqual(['hero', 'sheet', 'refs', 'animref', 'model', 'final'])
    expect(needsOf({ route: 'i2v', how: ['place'] }, 'place')).toEqual(['hero', 'sheet', 'refs', 'final'])
    expect(needsOf({ route: 'i2v', how: [] }, 'prop')).toEqual(['hero', 'sheet', 'refs', 'model', 'final'])   // D128: every prop has a 3D model
  })
  it('owed when a shot needs it, open when none does, done when the version has it; the foot takes the first owed', () => {
    const uses = [use('Reunion', 'clay1', ['figure']), use('Talk', 'i2v', ['speaker'])]
    const cells = readinessOf({ cls: 'character', voice_id: null }, ver({ hero_asset_id: 'ast_h', appearance: 'a wiry courier' }), uses, 9)
    const at = Object.fromEntries(cells.map((c) => [c.item, c]))
    expect(at.hero.state).toBe('done'); expect(at.sheet.state).toBe('done'); expect(at.refs).toMatchObject({ state: 'done', text: '9' })
    expect(at.animref).toMatchObject({ state: 'owed', shots: ['Reunion'] }); expect(at.body.state).toBe('owed')
    expect(at.voice).toMatchObject({ state: 'owed', shots: ['Talk'] }); expect(at.lora.state).toBe('open'); expect(at.final.state).toBe('owed')
    expect(nextOwed(cells)?.item).toBe('animref')
    expect(rowSummary(cells, uses)).toBe('4 owed for 2 shots')
    expect(shotNeeds(uses[0], cells, 'character')).toEqual(['animation reference', 'body', 'final'])
  })
  it('a profile in no shot owes nothing; a ready one says so', () => {
    const cells = readinessOf({ cls: 'place', voice_id: null }, ver({}), [], undefined)
    expect(cells.every((c) => c.state === 'open')).toBe(true); expect(rowSummary(cells, [])).toBe('in no shot'); expect(nextOwed(cells)).toBeNull()
    const ready = readinessOf({ cls: 'place', voice_id: null }, ver({ hero_asset_id: 'h', appearance: 'a quay', state: 'final' }), [use('Talk', 'i2v', ['place'])], 3)
    expect(rowSummary(ready, [use('Talk', 'i2v', ['place'])])).toBe('ready for 1 shot')
  })
})
