// CA0 (01 §9): a body from the Cast sheet shapes the dummy — the figure stands at the sheet's height with its feet on the floor, the IK
// chains use its own limbs, and without a body the dummy is E10's, unchanged.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY, bodyDims, type Body } from './body'
import { mannequin, POSES } from './builders'
import { figureChain, LIMB } from './ik'

const mat = new THREE.MeshBasicMaterial()
const box = (o: THREE.Object3D) => { o.updateWorldMatrix(true, true); return new THREE.Box3().setFromObject(o) }
const markerY = (o: THREE.Object3D, m: THREE.Object3D) => { o.updateWorldMatrix(true, true); return m.getWorldPosition(new THREE.Vector3()).y }

describe('the body on the dummy (CA0)', () => {
  it('leaves the default dummy as it was', () => {
    const m = mannequin(mat, POSES.stand)
    expect(m.root).toBe(m.joints.root)                                       // no height wrapper
    expect(m.limbs).toEqual({ upper_arm: LIMB.upper_arm, forearm: LIMB.forearm, thigh: LIMB.thigh, shin: LIMB.shin })
    expect(bodyDims(null).scale).toBe(1)
    expect(m.joints.root.position.y).toBeCloseTo(0.95, 5)
  })

  it.each([
    ['a tall broad adult', { ...DEFAULT_BODY, height_m: 2.0, build: 'broad' as const }],
    ['a child with a big head', { ...DEFAULT_BODY, height_m: 1.2, head: 1.4, legs: 0.8 }],
    ['an ogre', { ...DEFAULT_BODY, height_m: 2.6, build: 'heavy' as const, arms: 1.3, legs: 0.9, shoulders: 1.5 }],
  ])('%s stands at its height with its feet on the floor', (_, b: Body) => {
    const m = mannequin(mat, POSES.stand, undefined, b)
    const bb = box(m.root)
    expect(bb.max.y).toBeGreaterThan(b.height_m - 0.06)                     // the head's top (the sphere is stretched ×1.1: a little over)
    expect(bb.max.y).toBeLessThan(b.height_m + 0.06)
    expect(bb.min.y).toBeGreaterThan(-0.05)                                  // the feet on the floor
    expect(bb.min.y).toBeLessThan(0.05)
    const ankle = markerY(m.root, m.markers[10]), nose = markerY(m.root, m.markers[0])
    expect(ankle).toBeLessThan(0.1)
    expect(nose).toBeGreaterThan(b.height_m * 0.8)
  })

  it('gives the IK the figure\'s own bones', () => {
    const b = { ...DEFAULT_BODY, arms: 1.3, legs: 0.8 }
    const m = mannequin(mat, POSES.stand, undefined, b)
    expect(figureChain(m.limbs, 'r_arm').a).toBeCloseTo(0.29 * 1.3, 5)
    expect(figureChain(m.limbs, 'l_leg').b).toBeCloseTo(0.43 * 0.8, 5)
    expect(figureChain(m.limbs, 'r_arm').upper).toBe('r_shoulder')
  })

  it('carries attachments on their joints, outside the pose markers', () => {
    const plain = mannequin(mat, POSES.stand, undefined, DEFAULT_BODY)
    const tailed = mannequin(mat, POSES.stand, undefined, { ...DEFAULT_BODY, attachments: [{ kind: 'tail', joint: null, size: 1, note: '' }, { kind: 'horns', joint: null, size: 1, note: '' }] })
    expect(tailed.markers).toHaveLength(18)
    expect(tailed.joints.root.children.length).toBe(plain.joints.root.children.length + 1)   // the tail on the hips
    expect(tailed.joints.head.children.length).toBe(plain.joints.head.children.length + 2)   // two horns on the head
  })
})

describe('×1 an adult (proto01_UIcast CS1 · S3)', () => {
  it('a body of before, converted (neck = (neck + head) / 2), keeps every head point where it was', () => {
    const head = 0.889, before = 2.317                                               // Mara's fit on the old dummy
    const m = mannequin(mat, POSES.stand, undefined, { ...DEFAULT_BODY, head, neck: (before + head) / 2 })
    const y = (k: number) => { m.joints.root.updateWorldMatrix(true, true); return m.joints.neck.worldToLocal(m.markers[k].getWorldPosition(new THREE.Vector3())).y }
    expect(y(0)).toBeCloseTo(0.06 * before + 0.08 * head, 5)                        // the nose over the neck joint, as rig 1 drew it
    expect(y(14)).toBeCloseTo(0.06 * before + 0.12 * head, 5)                       // an eye
    expect(y(16)).toBeCloseTo(0.06 * before + 0.1 * head, 5)                        // an ear
    expect(bodyDims({ ...DEFAULT_BODY, head, neck: (before + head) / 2 }).top).toBeCloseTo(0.07 + 0.88 + 0.06 + 0.44 + 0.06 * before + 0.221 * head, 5)
  })
  it('the elbow and knee factors place the joints along their limbs; ×1 is the old dummy exactly', () => {
    const d = bodyDims({ ...DEFAULT_BODY, elbow: 0.6, knee: 0.45 })
    expect(d.limbs.upper_arm / (d.limbs.upper_arm + d.limbs.forearm)).toBeCloseTo(0.6, 6)
    expect(d.limbs.thigh / (d.limbs.thigh + d.limbs.shin)).toBeCloseTo(0.45, 6)
    expect(d.limbs.upper_arm + d.limbs.forearm).toBeCloseTo(0.56, 6)
    expect(bodyDims(DEFAULT_BODY).limbs).toEqual({ upper_arm: 0.29, forearm: 0.27, thigh: 0.44, shin: 0.43 })
  })
})
