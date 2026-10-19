// CA1: retargeting onto the figure's 12 joints — a synthetic Unreal-named rig in a T-pose whose right arm comes down and whose hips travel
// a metre: the figure's right arm starts sideways and ends hanging, the left stays out, the travel scales by the hip heights; a rig facing
// another way still walks the figure forward (+Z); the baked keys sit where the figure stands and turn with it; thinning keeps what the
// in-between cannot rebuild.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { bakeKeys, thinKeys } from './bake'
import { detectRig, norm, retarget } from './retarget'

function rig(facing = 0) {
  const root = new THREE.Group(); root.name = 'Armature'
  root.rotation.y = facing
  const bone = (name: string, parent: THREE.Object3D, x: number, y: number, z: number) => { const b = new THREE.Bone(); b.name = name; b.position.set(x, y, z); parent.add(b); return b }
  const pelvis = bone('pelvis', root, 0, 1, 0)
  const sp1 = bone('spine_01', pelvis, 0, 0.1, 0), sp3 = bone('spine_03', sp1, 0, 0.3, 0)
  const neck = bone('neck_01', sp3, 0, 0.2, 0); bone('Head', neck, 0, 0.1, 0)
  for (const [side, sx] of [['r', -1], ['l', 1]] as const) {
    const up = bone(`upperarm_${side}`, sp3, sx * 0.2, 0.15, 0), low = bone(`lowerarm_${side}`, up, sx * 0.3, 0, 0); bone(`hand_${side}`, low, sx * 0.25, 0, 0)
    const th = bone(`thigh_${side}`, pelvis, sx * 0.1, -0.05, 0), calf = bone(`calf_${side}`, th, 0, -0.45, 0); bone(`foot_${side}`, calf, 0, -0.45, 0)
  }
  const down = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), Math.PI / 2)        // the T-pose right arm (−X) down to −Y
  const clip = new THREE.AnimationClip('Lower_and_walk', 1, [
    new THREE.QuaternionKeyframeTrack('upperarm_r.quaternion', [0, 1], [0, 0, 0, 1, down.x, down.y, down.z, down.w]),
    new THREE.VectorKeyframeTrack('pelvis.position', [0, 1], [0, 1, 0, 0, 1, 1]),
  ])
  return { root, clip }
}

/** The figure's joint direction in world space: the rest direction (−Y for an arm) turned by the joint's chain of local Eulers. */
function dirOf(chain: number[][], rest: [number, number, number]) {
  const q = new THREE.Quaternion()
  for (const e of chain) q.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(...e.map((d) => (d * Math.PI) / 180) as [number, number, number], 'YXZ')))
  return new THREE.Vector3(...rest).applyQuaternion(q)
}

describe('retargeting a clip onto the figure (CA1)', () => {
  it('knows the rigs by their bone names, as three.js keeps them', () => {
    expect(detectRig(['DEF-hips', 'DEF-spine001', 'DEF-spine003', 'DEF-neck', 'DEF-head', 'DEF-upper_armR', 'DEF-forearmR', 'DEF-handR', 'DEF-upper_armL', 'DEF-forearmL', 'DEF-handL',
      'DEF-thighR', 'DEF-shinR', 'DEF-footR', 'DEF-thighL', 'DEF-shinL', 'DEF-footL'])).toBe('rigify')
    expect(norm('mixamorig:RightArm')).toBe(norm('mixamorigRightArm'))
    expect(detectRig(['Hips', 'Spine'])).toBeNull()
  })

  it('brings the right arm down, keeps the left out, and scales the travel by the hips', () => {
    const { root, clip } = rig()
    const r = retarget(root, clip, { fps: 4, hip: 0.91 })
    expect(r.rig).toBe('unreal')
    expect(r.frames).toHaveLength(5)
    const at = (i: number, j: 'r_shoulder' | 'l_shoulder') => dirOf([r.frames[i].joints.root, r.frames[i].joints.spine, r.frames[i].joints[j]], [0, -1, 0])
    expect(at(0, 'r_shoulder').x).toBeLessThan(-0.99)                       // sideways (the T-pose) at the start …
    expect(at(4, 'r_shoulder').y).toBeLessThan(-0.99)                       // … hanging at the end
    expect(at(4, 'l_shoulder').x).toBeGreaterThan(0.99)                     // the left arm stays out
    const s = 0.91 / 0.95                                                   // hip above the ankles: figure 0.91, source 1 − 0.05 (the foot at 0.05)
    expect(r.frames[4].offset[2]).toBeCloseTo(1 * s, 3)
    expect(r.travel).toBeCloseTo(s, 3)
    expect(retarget(root, clip, { fps: 4, hip: 0.91, inPlace: true }).frames[4].offset[2]).toBe(0)
    expect(retarget(root, clip, { fps: 4, speed: 0.5 }).frames).toHaveLength(9)           // half speed, twice the frames
    expect(retarget(root, clip, { fps: 4, start: 0.5 }).frames).toHaveLength(3)           // trimmed
  })

  it('turns a rig that faces another way to the figure\'s facing', () => {
    const { root, clip } = rig(Math.PI / 2)                                 // the source faces +X (its right at +Z)
    const r = retarget(root, clip, { fps: 4, hip: 0.91 })
    expect(r.frames[4].offset[2]).toBeGreaterThan(0.9)                      // its walk is still the figure's forward
    expect(Math.abs(r.frames[4].offset[0])).toBeLessThan(1e-3)
  })

  it('bakes keys where the figure stands, turned with it, and thins them', () => {
    const { root, clip } = rig()
    const r = retarget(root, clip, { fps: 4, hip: 0.91 })
    const keys = bakeKeys(r.frames, { pos: [2, 0, 0], rot: [0, 90, 0], scale: [1, 1, 1] }, 10)
    expect(keys[0].frame).toBe(10)
    expect(keys[4].transform.pos[0]).toBeCloseTo(2 + r.travel, 3)           // facing +X: forward is +X
    expect(keys[4].transform.rot).toEqual([0, 90, 0])
    expect(thinKeys(keys).length).toBeLessThan(keys.length)
    const linear = keys.map((k, i) => ({ ...k, pose: { preset: 'stand', joints: { root: [0, 0, 0], spine: [0, 0, 0] } }, transform: { ...k.transform, pos: [i, 0, 0] } }))
    expect(thinKeys(linear).map((k) => k.frame)).toEqual([10, 14])           // a straight line keeps its ends
    const corner = linear.map((k, i) => ({ ...k, transform: { ...k.transform, pos: [i <= 2 ? i : 2, 0, i <= 2 ? 0 : i - 2] } }))
    expect(thinKeys(corner).map((k) => k.frame)).toEqual([10, 12, 14])      // a corner is kept
  })
})
