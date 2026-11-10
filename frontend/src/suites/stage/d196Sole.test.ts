// D196 (the author on char01: "the clay shell is still disproportionate … distorted hands and feet"): a shell's skeleton stands in its
// shoes and in its picture's legs. The sole lifts the dummy's ankles (the hip, the foot block to the floor, the Detailed foot dropped);
// the bind stance reads the legs' swing as it reads the arms'.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { bodyDims, DEFAULT_BODY, type Body } from './body'
import { mannequin, POSES } from './builders'
import { LEG_STANCE_MAX, stanceOf } from './proxy'

const r = (deg: number) => (deg * Math.PI) / 180
/** A figure facing the picture (its right side on the picture's left), the arms 22° out, each leg `out`° from straight down. */
const person = (out: number, shinOut = out) => {
  const pose: number[][] = Array.from({ length: 18 }, () => [0, 0, 0.9])
  pose[2] = [80, 100, 0.9]; pose[5] = [120, 100, 0.9]
  pose[3] = [80 - 30 * Math.sin(r(22)), 100 + 30 * Math.cos(r(22)), 0.9]; pose[4] = [pose[3][0] - 28 * Math.sin(r(22)), pose[3][1] + 28 * Math.cos(r(22)), 0.9]
  pose[6] = [120 + 30 * Math.sin(r(22)), 100 + 30 * Math.cos(r(22)), 0.9]; pose[7] = [pose[6][0] + 28 * Math.sin(r(22)), pose[6][1] + 28 * Math.cos(r(22)), 0.9]
  pose[8] = [90, 160, 0.9]; pose[11] = [110, 160, 0.9]
  pose[9] = [90 - 44 * Math.sin(r(out)), 160 + 44 * Math.cos(r(out)), 0.9]; pose[10] = [pose[9][0] - 43 * Math.sin(r(shinOut)), pose[9][1] + 43 * Math.cos(r(shinOut)), 0.9]
  pose[12] = [110 + 44 * Math.sin(r(out)), 160 + 44 * Math.cos(r(out)), 0.9]; pose[13] = [pose[12][0] + 43 * Math.sin(r(shinOut)), pose[12][1] + 43 * Math.cos(r(shinOut)), 0.9]
  return { pose }
}
const body = (sole: number): Body => ({ ...DEFAULT_BODY, height_m: 1.66, sole })

describe("the legs' stance (D196)", () => {
  it("reads each leg's swing out from the picture, with the arms' signs", () => {
    const s = stanceOf(person(6))
    expect(s.r_hip[2]).toBeCloseTo(-6, 0); expect(s.l_hip[2]).toBeCloseTo(6, 0)
    expect(s.r_knee[2]).toBeCloseTo(0, 0)
    expect(s.r_shoulder[2]).toBeCloseTo(-22, 0)                                                   // the arms as before
    const knock = stanceOf(person(8, 2))                                                          // the shins back toward each other
    expect(knock.r_knee[2]).toBeCloseTo(6, 0); expect(knock.l_knee[2]).toBeCloseTo(-6, 0)
  })
  it('holds a leg within LEG_STANCE_MAX, and leaves the legs straight without their points', () => {
    expect(stanceOf(person(60)).r_hip[2]).toBeCloseTo(-LEG_STANCE_MAX, 5)
    const p = person(6); p.pose[9][2] = 0.1
    expect(stanceOf(p).r_hip).toBeUndefined(); expect(stanceOf(p).l_hip[2]).toBeCloseTo(6, 0)
  })
  it('a straight-legged figure in its stance has its ankles where the picture has them', () => {
    const m = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, stanceOf(person(10)), body(0))
    m.root.updateMatrixWorld(true)
    const at = (k: number) => m.markers[k].getWorldPosition(new THREE.Vector3())
    const leg = at(8).distanceTo(at(10))
    expect(Math.abs(at(10).x - at(8).x) / leg).toBeCloseTo(Math.sin(r(10)), 2)                 // out by the picture's 10°
  })
})

describe('the sole (D196)', () => {
  it('stands the dummy higher, the height kept the author\'s', () => {
    const a = bodyDims(body(0)), b = bodyDims(body(0.12))
    expect(b.hip - a.hip).toBeCloseTo(0.12, 6)
    expect(b.top * b.scale).toBeCloseTo(1.66, 6)                                                  // the head's top where it was
    expect(b.limbs.shin * b.scale).toBeLessThan(a.limbs.shin * a.scale)                           // the legs shorter in metres: the shoe is under them
  })
  it("lifts the ankles by the sole and reaches the floor with the foot's block", () => {
    for (const sole of [0, 0.12]) {
      const m = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body(sole))
      m.root.updateMatrixWorld(true)
      const d = bodyDims(body(sole))
      const ankle = m.markers[10].getWorldPosition(new THREE.Vector3()).y
      expect(ankle).toBeCloseTo((0.03 + 0.01 * DEFAULT_BODY.legs + sole) * d.scale, 3)
      const box = new THREE.Box3().setFromObject(m.root)
      expect(box.min.y).toBeCloseTo(0, 3)                                                         // standing on the floor, not on the ankles
    }
  })
})
