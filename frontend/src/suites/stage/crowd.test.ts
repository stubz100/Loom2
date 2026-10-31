// D173: a crowd on a set's face — its frame at a stage frame (looping), and its plane over the stretch.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { clipFrame, crowdPlane, LIFT, PACKED } from './crowd'
import { normalOf, setFaces } from './placeSet'

describe('D173: a crowd on a face', () => {
  it("plays the clip's frames at its own rate, looping over all but the last", () => {
    expect(clipFrame(0, 16, 81)).toBe(0)
    expect(clipFrame(24, 16, 81)).toBe(16)                                     // one second of stage frames, sixteen of the clip's
    expect(clipFrame(1.5, 16, 81)).toBe(1)                                     // a final at 16 fps steps the stage 1.5 frames at a time
    expect(clipFrame(120, 16, 81)).toBe(0)                                     // 5 s: the eightieth frame is the first again
    expect(clipFrame(144, 16, 81)).toBe(16)
    expect(clipFrame(-3, 16, 81)).toBe(0)
  })
  it("stands over the stretch along the face, its whole height, just inside it", () => {
    const f = setFaces({ kind: 'street', sizes: { width: 5.5, length: 30, pavement: 2, height_l: 5, height_r: 5 } }).find((x) => x.id === 'facade_right')!
    const n = normalOf(f)
    const p = crowdPlane(f, n, 3.2, 14.4)
    expect(p.w).toBeCloseTo(11.2, 6)
    expect(p.h).toBeCloseTo(f.h, 6)
    const expected = f.origin.clone().addScaledVector(f.u, 8.8).addScaledVector(f.v, f.h / 2).addScaledVector(n, 0.002)
    expect(p.centre.distanceTo(expected)).toBeLessThan(1e-9)
    expect(crowdPlane(f, n, -2, 99).w).toBeCloseTo(f.w, 6)                     // clamped to the face
    expect(crowdPlane(f, n, 10, 4).w).toBe(0)
    expect(new THREE.Vector3().subVectors(p.centre, f.origin).dot(n)).toBeCloseTo(0.002, 6)
  })
  it("D174: a walkers' packed clip is its colour on the left half and its mask on the right, a millimetre over the crowd", () => {
    expect(PACKED.colour).toEqual({ repeat: [0.5, 1], offset: [0, 0] })
    expect(PACKED.mask).toEqual({ repeat: [0.5, 1], offset: [0.5, 0] })
    expect(LIFT.walkers).toBeGreaterThan(LIFT.crowd)
  })
})
