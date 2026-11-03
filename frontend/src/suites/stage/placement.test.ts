// C1 (D181, P7 / F35): where a thing added to a scene lands, and which way it faces.
import { describe, expect, it } from 'vitest'
import type { StageObject } from '../../api/types'
import { cameraFloorPoint, faceCamera, landing, presetDrop } from './placement'

const obj = (pos: number[], kind: StageObject['kind'] = 'mannequin') => ({ transform: { pos, rot: [0, 0, 0], scale: [1, 1, 1] }, kind, visible: true })

describe('C1: the landing point', () => {
  it("meets the floor along the camera's line of sight, 1.5–6 m out; a level or upward camera has no floor ahead", () => {
    expect(cameraFloorPoint({ pos: [0, 1.6, 5], target: [0, 1.0, 2] })).toEqual([0, 0, -1])                  // 0.6 m down over 3 m: the floor at 8 m, capped at 6 m out
    expect(cameraFloorPoint({ pos: [0, 1.6, 5], target: [0, 0, 1] })).toEqual([0, 0, 1])                     // the floor 4 m out: as it is
    expect(cameraFloorPoint({ pos: [0, 1.6, 0], target: [0, 1.6, -10] })).toBeNull()
    expect(cameraFloorPoint({ pos: [0, 1.6, 0], target: [0, 2, -10] })).toBeNull()
    expect(cameraFloorPoint({ pos: [0.3, 1.45, -10], target: [0.5, 1.2, -14] })![2]).toBeCloseTo(-16, 1)     // the walk's camera: nearly level, the floor 23 m off — 6 m out instead
    expect(cameraFloorPoint({ pos: [0, 1.6, 0], target: [0, 0, -0.5] })![2]).toBe(-1.5)                      // steep: no nearer than 1.5 m
    expect(cameraFloorPoint({ pos: [2, 3, 2], target: [2, 0, 2] })).toEqual([2, 0, 2])                        // straight down
  })
  it("puts the first thing on the camera's floor point and the next ones beside it, to the camera's right then left", () => {
    const cam = { pos: [0, 1.6, 5], target: [0, 0, 1] }
    const first = landing(cam, [], [9, 0, 9])
    expect(first).toEqual([0, 0, 1])
    const second = landing(cam, [obj(first)], [9, 0, 9])
    expect(second[0]).toBeCloseTo(0.7, 3); expect(second[2]).toBeCloseTo(1, 3)                                // the camera looks down −Z: its right is +X
    const third = landing(cam, [obj(first), obj(second)], [9, 0, 9])
    expect(third[0]).toBeCloseTo(-0.7, 3)
    expect(landing(null, [], [1, 0, 2])).toEqual([1, 0, 2])                                                   // no camera: the viewport's centre
    expect(landing(cam, [obj(first, 'set'), obj(first, 'light')], [9, 0, 9])).toEqual(first)                  // a set or a light does not take the spot
  })
  it('faces the camera: the yaw of (camera − figure), +Z = 0', () => {
    expect(faceCamera([0, 0, -5], [0, 1.6, 5])).toBe(0)
    expect(faceCamera([0, 0, 0], [5, 1.6, 0])).toBe(90)
    expect(faceCamera([0, 0, 0], [0, 1.6, -5])).toBe(180)
  })
  it('reads a dragged preset tile', () => {
    expect(presetDrop('figures:char:prf_1')).toEqual({ group: 'figures', id: 'char:prf_1' })
    expect(presetDrop('standins:crate')).toEqual({ group: 'standins', id: 'crate' })
    expect(presetDrop('adult')).toBeNull()
  })
})
