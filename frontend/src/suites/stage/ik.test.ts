// P13 / ST2 (D81): the two-bone solver reaches what it can, bends the right way, and the mirror swaps sides.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { CHAINS, forwardTwoBone, mirrorJoints, solveTwoBone } from './ik'

const v = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z)

describe('solveTwoBone', () => {
  it('puts the end on a reachable target (arm, forward and up)', () => {
    const c = CHAINS.r_arm
    const root = v(-0.21, 0.4, 0), target = v(-0.1, 0.5, 0.35)
    const s = solveTwoBone(root, target, c.a, c.b, v(...c.bend))
    const fk = forwardTwoBone(root, s.upper, s.lower, c.a, c.b)
    expect(fk.end.distanceTo(target)).toBeLessThan(0.002)
    expect(fk.mid.z).toBeGreaterThan(root.z - 0.05)                           // the elbow bows forward, not back through the torso
    expect(s.reach).toBeLessThan(1)
  })
  it('points straight at an unreachable target', () => {
    const c = CHAINS.l_leg
    const root = v(0.1, -0.04, 0), target = v(0.1, -0.04, 3)
    const s = solveTwoBone(root, target, c.a, c.b, v(...c.bend))
    const fk = forwardTwoBone(root, s.upper, s.lower, c.a, c.b)
    expect(s.reach).toBe(1)
    expect(fk.end.distanceTo(root)).toBeCloseTo(c.a + c.b, 3)
    expect(fk.end.z).toBeGreaterThan(0.8)
    expect(Math.abs(s.lower[0])).toBeLessThan(3)                               // a straight knee (the clamp leaves a hair of bend)
  })
  it('bends a knee backward for a foot pulled up behind', () => {
    const c = CHAINS.r_leg
    const root = v(-0.1, -0.04, 0), target = v(-0.1, -0.5, -0.3)
    const s = solveTwoBone(root, target, c.a, c.b, v(...c.bend))
    const fk = forwardTwoBone(root, s.upper, s.lower, c.a, c.b)
    expect(fk.end.distanceTo(target)).toBeLessThan(0.002)
    expect(fk.mid.z).toBeLessThan(target.z + 0.3)                              // the knee is behind the hip line, not in front of the body
  })
  it('a target straight below gives a hanging limb', () => {
    const c = CHAINS.l_arm
    const root = v(0.21, 0.4, 0), target = v(0.21, 0.4 - (c.a + c.b) + 0.001, 0)
    const s = solveTwoBone(root, target, c.a, c.b, v(...c.bend))
    expect(Math.abs(s.upper[0])).toBeLessThan(10)
    expect(Math.abs(s.lower[0])).toBeLessThan(10)
  })
})

describe('mirrorJoints', () => {
  it('swaps left and right and flips Y and Z', () => {
    const m = mirrorJoints({ r_shoulder: [-88, 10, -4], l_shoulder: [0, 0, 8], head: [0, -15, 5], spine: [14, 0, 0] })
    expect(m.l_shoulder).toEqual([-88, -10, 4])
    expect(m.r_shoulder).toEqual([0, 0, -8])
    expect(m.head).toEqual([0, 15, -5])
    expect(m.spine).toEqual([14, 0, 0])
    expect(mirrorJoints(mirrorJoints({ r_elbow: [-110, 3, 2] }))).toEqual({ r_elbow: [-110, 3, 2] })
  })
})
