// D180 (W60): a built set's thing as a stage object — its model at its base, else its card standing on the floor, through the set's turn.
import { describe, expect, it } from 'vitest'
import { onStage, thingFields, type Thing } from './placeThings'

const ferry: Thing = { id: 'pth_1', name: 'Ferry', card_asset_id: 'ast_card', mesh_asset_id: null, base: [2, 0, -30], width_m: 8, height_m: 6, yaw_deg: 5 }
const set = { transform: { pos: [10, 0, 0], rot: [0, 90, 0], scale: [1, 1, 1] }, profile_id: 'prf_pier' }

describe('D180: a set thing on the stage', () => {
  it('carries the set frame through the set object (its turn about y, its place)', () => {
    expect(onStage(set, [0, 0, -1])).toEqual([9, 0, 0])                             // 90°: −z in the set is −x on the stage
    expect(onStage({ transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } }, [2, 0, -30])).toEqual([2, 0, -30])
  })
  it('a card: the cut-out on a plane its width wide, its bottom on the floor, facing the camera', () => {
    const f = thingFields(ferry, { transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, profile_id: 'p' })
    expect(f).toMatchObject({ kind: 'plane', asset_id: 'ast_card', billboard: false, name: 'Ferry' })
    const s = f.transform!.scale[0]
    expect(s).toBeCloseTo(8 / 1.6)
    const k = (6 / 8) / (0.9 / 1.6)
    expect(f.transform!.pos[1] + s * (0.9 - (0.9 * k) / 2)).toBeCloseTo(0, 2)       // its bottom at the base
    expect(f.transform!.rot[1]).toBe(5)
  })
  it('a model: at its base, its height the thing\'s, turned with the set', () => {
    const f = thingFields({ ...ferry, mesh_asset_id: 'ast_glb' }, set)
    expect(f).toMatchObject({ kind: 'mesh', asset_id: 'ast_glb', height_m: 6 })
    expect(f.transform!.pos).toEqual(onStage(set, ferry.base))
    expect(f.transform!.rot[1]).toBe(95)
  })
})
