// CA1: baking along a floor path (the travel laid along it, facing its way, stopping at its end), blending in from what the figure was
// doing, a loop repeated with its travel continuing — and the world-space slide of a foot-locked walk laid along a curve.
import { describe, expect, it } from 'vitest'
import type { Joint } from '../builders'
import { bakeAlongPath, bakeKeys, blendIn, repeatLoop } from './bake'
import { footLock, keySlide } from './footlock'
import { measure } from './path'
import { walkAlong } from './walkpath'
import type { MotionFrame } from './retarget'

const still = (z: number): MotionFrame => ({ joints: { root: [0, 0, 0], r_hip: [0, 0, 0] } as Record<Joint, number[]>, offset: [0, 0, z] })
const base = { pos: [1, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }

function walkInPlace(n = 48): MotionFrame[] {
  const out: MotionFrame[] = []
  for (let i = 0; i < n; i++) {
    const ph = (i / 24) * Math.PI * 2, swing = 25 * Math.sin(ph), zero = [0, 0, 0]
    const joints = Object.fromEntries((['root', 'spine', 'neck', 'head', 'r_shoulder', 'r_elbow', 'l_shoulder', 'l_elbow'] as Joint[]).map((j) => [j, zero])) as Record<Joint, number[]>
    joints.r_hip = [-swing, 0, 0]; joints.l_hip = [swing, 0, 0]
    joints.r_knee = [Math.max(0, Math.cos(ph)) * 50, 0, 0]; joints.l_knee = [Math.max(0, -Math.cos(ph)) * 50, 0, 0]
    out.push({ joints, offset: [0, 0, 0] })
  }
  return out
}

describe('baking a clip (CA1)', () => {
  it('lays the travel along the path, facing its way, and stops at its end', () => {
    const frames = Array.from({ length: 30 }, (_, i) => still(i * 0.1))           // 0.1 m a frame, 2.9 m in all
    const keys = bakeAlongPath(frames, base, 5, [[0, 0], [2, 0]])               // a 2 m path along +X
    expect(keys[0].transform.pos[0]).toBeCloseTo(0); expect(keys[0].frame).toBe(5)
    expect(keys[10].transform.pos[0]).toBeCloseTo(1); expect(keys[10].transform.rot[1]).toBeCloseTo(90)
    expect(keys.length).toBe(21)                                                // 2 m reached at the 21st frame: the rest dropped
    expect(keys[keys.length - 1].transform.pos[0]).toBeCloseTo(2)
  })

  it('eases in from what the figure was doing', () => {
    const keys = bakeKeys(Array.from({ length: 10 }, () => ({ ...still(0), joints: { root: [0, 0, 0], r_hip: [-40, 0, 0] } as Record<Joint, number[]> })), base, 0)
    const blended = blendIn(keys, () => ({ r_hip: [0, 0, 0] }), 4)
    expect(blended[0].pose!.joints.r_hip[0]).toBeCloseTo(-8)                    // 1/5 of the way
    expect(blended[3].pose!.joints.r_hip[0]).toBeCloseTo(-32)                   // 4/5
    expect(blended[4].pose!.joints.r_hip[0]).toBe(-40)                          // then the clip's own
    expect(blendIn(keys, () => null, 4)[0].pose!.joints.r_hip[0]).toBe(-40)     // nothing before: the clip as it is
  })

  it('repeats a loop with its travel continuing', () => {
    const loop = Array.from({ length: 5 }, (_, i) => still(i * 0.25))           // a 1 m cycle
    const r = repeatLoop(loop, 3)
    expect(r.length).toBe(13)
    expect(r[r.length - 1].offset[2]).toBeCloseTo(3)
  })

  it('walks a curve by steering: the planted foot within 2 cm, the figure near the path, to its end', () => {
    const path: [number, number][] = [[0, 0], [0, 2], [2, 3], [3, 5]]
    const walk = footLock(walkInPlace())
    const per = Math.abs(walk[walk.length - 1].offset[2] - walk[0].offset[2])
    const locked = footLock(repeatLoop(walkInPlace(), Math.ceil(measure(path).length / per) + 1))
    const keys = walkAlong(locked, base, 0, path)
    expect(keys[keys.length - 1].transform.rot[1]).not.toBeCloseTo(keys[0].transform.rot[1])   // it turned
    expect(keySlide(keys)).toBeLessThan(0.02)                                                   // 02 §5's bar
    const end = keys[keys.length - 1].transform.pos
    expect(Math.hypot(end[0] - 3, end[2] - 5)).toBeLessThan(0.6)                                // it got there
    const m = measure(path)
    const toSeg = (x: number, z: number) => Math.min(...m.points.slice(1).map(([bx, bz], i) => {
      const [ax, az] = m.points[i], vx = bx - ax, vz = bz - az, l2 = vx * vx + vz * vz
      const t = l2 ? Math.max(0, Math.min(1, ((x - ax) * vx + (z - az) * vz) / l2)) : 0
      return Math.hypot(x - ax - vx * t, z - az - vz * t)
    }))
    const off = Math.max(...keys.map((k) => toSeg(k.transform.pos[0], k.transform.pos[2])))
    expect(off).toBeLessThan(0.35)                                                              // never far from the path
  })
})
