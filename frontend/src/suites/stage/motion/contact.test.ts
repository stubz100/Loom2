// AP1 (D141): the feet on the floor — a pose's drop (E39: the default adult's crouch floats 10.7 cm, its sit sinks 2.6) and a clip's
// stances set on the floor, a foot still under it bent up by IK.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from '../body'
import { applyPose, mannequin, POSES } from '../builders'
import { footContact, poseContact } from './contact'
import type { MotionFrame } from './retarget'

const ankles = (preset: string, joints: Record<string, number[]> | undefined, offset: number[], ground = 0) => {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, DEFAULT_BODY)
  applyPose(fig.joints, POSES[preset], joints, ground); fig.root.position.set(offset[0], offset[1], offset[2]); fig.root.updateMatrixWorld(true)
  const y = (s: 'r' | 'l') => new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints[s === 'r' ? 'r_knee' : 'l_knee'].matrixWorld).y
  return { r: y('r'), l: y('l') }
}
const rest = ankles('stand', undefined, [0, 0, 0])

describe('the feet on the floor (AP1, D141)', () => {
  it('drops a pose onto its lower foot: a crouch comes down, a sit comes up, a stand stays', () => {
    expect(poseContact('stand', undefined, DEFAULT_BODY).ground).toBeCloseTo(0, 4)
    const crouch = poseContact('crouch', undefined, DEFAULT_BODY)
    expect(crouch.ground).toBeGreaterThan(0.08)                                                     // E39: 10.7 cm in the air
    const a = ankles('crouch', crouch.joints, [0, 0, 0], crouch.ground)
    expect(Math.min(a.r - rest.r, a.l - rest.l)).toBeCloseTo(0, 2)                                  // the lower foot on the floor (the stored angles' rounding: a millimetre)
    expect(Math.min(a.r - rest.r, a.l - rest.l)).toBeGreaterThan(-0.004)                            // and neither under it
    expect(poseContact('sit', undefined, DEFAULT_BODY).ground).toBeLessThan(0)                      // E39: a sit sinks — raised
  })
  it("sets a clip's stances on the floor and bends a foot still under it", () => {
    // a crouch held with the root at the standing height: both feet in the air — the clip lowered onto them
    const crouch = Object.fromEntries(Object.entries(POSES.crouch.j).map(([k, v]) => [k, [...(v as number[])]]))
    const frames: MotionFrame[] = Array.from({ length: 8 }, () => ({ joints: crouch as never, offset: [0, 0, 0] }))
    const out = footContact(frames, DEFAULT_BODY)
    for (const f of out) {
      const a = ankles('stand', f.joints, f.offset)
      expect(Math.min(a.r - rest.r, a.l - rest.l)).toBeCloseTo(0, 2)
      expect(Math.min(a.r - rest.r, a.l - rest.l)).toBeGreaterThan(-0.004)
    }
    expect(out[0].offset[1]).toBeLessThan(-0.05)                                                     // lowered
    expect(footContact(frames.slice(0, 1), DEFAULT_BODY)).toEqual(frames.slice(0, 1))             // one frame: as it is
  })
})
