// D111 (PS5a): the final's frames at the shot's rate and its layers — the plate, each visible figure and prop (a 3D model, a stand-in, an
// image plane), the shadows; hidden objects, sets, lights and cameras make no layer of their own.
import { describe, expect, it } from 'vitest'
import type { StageDoc, StageObject } from '../../api/types'
import { batchCount, framesAt, planFinal } from './finalShot'

const obj = (id: string, kind: StageObject['kind'], extra: Partial<StageObject> = {}): StageObject => ({ id, kind, name: id, preset: null, asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  parent: null, locked: false, visible: true, colour_id: 1, pose: null, billboard: false, profile_id: null, version: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, things: [], things_document_id: null, ...extra })
const doc = (objects: StageObject[], range = { start: 0, end: 48 }) => ({ objects, range }) as unknown as StageDoc

describe('D111 (PS5a) planning the final', () => {
  it('samples every frame at F24 and every 1.5th at F16 (finals.py frames_at)', () => {
    expect(framesAt(0, 3, 24)).toEqual([0, 1, 2, 3])
    expect(framesAt(0, 240, 16)).toHaveLength(161)
    expect(framesAt(0, 3, 16)).toEqual([0, 1.5, 3])
    expect(framesAt(5, 4, 16)).toEqual([])
  })
  it('makes one layer per visible figure and prop, between the plate and the shadows', () => {
    const p = planFinal(doc([obj('set_a', 'set', { name: 'Room' }), obj('light_1', 'light'), obj('fig_m', 'mannequin', { name: 'Mara', profile_id: 'prf_m' }),
      obj('chest', 'mesh', { name: 'Chest', profile_id: 'prf_c', version: 'v2' }), obj('box', 'prop'), obj('gone', 'mannequin', { visible: false }), obj('card', 'plane')]), 16)
    expect(p.times).toHaveLength(33)
    expect(p.layers.map((l) => `${l.kind}:${l.id}`)).toEqual(['plate:plate', 'figure:fig_m', 'prop:chest', 'prop:box', 'prop:card', 'shadows:shadows'])
    expect(p.layers[0].name).toBe('Room')
    expect(p.layers[1]).toMatchObject({ object_id: 'fig_m', profile_id: 'prf_m' })
    expect(p.layers[2]).toMatchObject({ object_id: 'chest', profile_id: 'prf_c', version: 'v2' })
  })
  it("counts a performance's batches as the server plans them (77 frames, 5 carried)", () => {
    expect([9, 77, 78, 149, 150, 161].map(batchCount)).toEqual([1, 1, 2, 2, 3, 3])
  })
})
