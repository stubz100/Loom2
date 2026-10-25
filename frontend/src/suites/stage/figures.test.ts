// D93 (C8): the figures' screen order (the camera's own projection: figure 1 is the left-most), the figure mentions a StageShot sends
// (visible bound figures only), and Make frame ▸ in Stage's pre-binding of the speakers when the counts match.
import { describe, expect, it } from 'vitest'
import type { StageObject } from '../../api/types'
import { figureMentions, figuresByScreen, prebind, screenX } from './figures'

const fig = (id: string, x: number, extra: Partial<StageObject> = {}): StageObject => ({ id, kind: 'mannequin', name: id, preset: 'adult', asset_id: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, transform: { pos: [x, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1, pose: { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {} }, billboard: false, profile_id: null, version: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null, ...extra })
const CAM = { pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0 }

describe('screenX / figuresByScreen', () => {
  it('left is negative, right positive; behind the camera is null; the order follows the camera, not the document', () => {
    expect(screenX([-1.2, 0, 0], CAM)!).toBeLessThan(0)
    expect(screenX([1.2, 0, 0], CAM)!).toBeGreaterThan(0)
    expect(screenX([0, 0, 9], CAM)).toBeNull()
    const back = { pos: [0, 1.5, -5], target: [0, 1, 0], roll: 0 }                       // the reverse shot: left and right swap
    expect(screenX([-1.2, 0, 0], back)!).toBeGreaterThan(0)
    expect(screenX([-1.2, 0, 0], { ...CAM, roll: 180 })!).toBeGreaterThan(0)            // upside down: so does the roll
    const objs = [fig('b', 1.2), { ...fig('crate', -3), kind: 'prop' as const }, fig('a', -1.2), fig('c', 0, { transform: { pos: [0, 0, 9], rot: [0, 0, 0], scale: [1, 1, 1] } })]
    expect(figuresByScreen(objs, CAM).map((o) => o.id)).toEqual(['a', 'b', 'c'])        // props are not figures; behind the camera last
    expect(figuresByScreen(objs, back).map((o) => o.id)).toEqual(['b', 'c', 'a'])           // c stands in front of this camera, in the middle
  })
})

describe('figureMentions', () => {
  it('the visible bound figures, left to right, with a pinned version', () => {
    const objs = [fig('r', 1, { profile_id: 'prf_i' }), fig('l', -1, { profile_id: 'prf_m', version: 'v2' }), fig('free', 0), fig('hid', -2, { profile_id: 'prf_j', visible: false })]
    expect(figureMentions(objs, CAM)).toEqual([{ profile_id: 'prf_m', figure: 'l', version: 'v2' }, { profile_id: 'prf_i', figure: 'r' }])
    expect(figureMentions([], CAM)).toEqual([])
  })
})

describe('prebind (Make frame ▸ in Stage)', () => {
  it('the speakers to the figures in screen order when the counts match; a figure already bound to a speaker keeps it', () => {
    expect(prebind([fig('r', 1), fig('l', -1)], CAM, [{ id: 'prf_m' }, { id: 'prf_j' }])).toEqual({ l: 'prf_m', r: 'prf_j' })
    expect(prebind([fig('r', 1, { profile_id: 'prf_m' }), fig('l', -1)], CAM, [{ id: 'prf_m' }, { id: 'prf_j' }])).toEqual({ r: 'prf_m', l: 'prf_j' })
    expect(prebind([fig('a', 0), fig('b', 1), fig('c', 2)], CAM, [{ id: 'prf_m' }, { id: 'prf_j' }])).toBeNull()      // 3 figures, 2 speakers: the author binds
    expect(prebind([fig('a', 0)], CAM, [])).toBeNull()
    expect(prebind([fig('a', 0), fig('h', 1, { visible: false })], CAM, [{ id: 'prf_m' }])).toEqual({ a: 'prf_m' })  // a hidden figure is not in the shot
  })
})
