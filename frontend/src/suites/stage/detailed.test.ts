// CA1: the Detailed level follows the figure — a synthetic Unreal-named mannequin (T-pose, facing +Z) beside a figure posed by presets: every
// mapped bone points along its figure limb, the pelvis sits at the figure's root, the segments take the figure's lengths, and a bone the
// figure does not have (a finger) takes its own keyed turn.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from './body'
import { applyPose, mannequin, POSES } from './builders'
import { makeDetailed } from './detailed'

function synthetic(): THREE.Object3D {
  const root = new THREE.Group(); root.name = 'Armature'
  const bone = (name: string, parent: THREE.Object3D, x: number, y: number, z: number) => { const b = new THREE.Bone(); b.name = name; b.position.set(x, y, z); parent.add(b); return b }
  const pelvis = bone('pelvis', root, 0, 1, 0)
  const sp1 = bone('spine_01', pelvis, 0, 0.1, 0), sp2 = bone('spine_02', sp1, 0, 0.15, 0), sp3 = bone('spine_03', sp2, 0, 0.15, 0)
  const neck = bone('neck_01', sp3, 0, 0.2, 0); bone('Head', neck, 0, 0.1, 0)
  for (const [side, sx] of [['r', -1], ['l', 1]] as const) {
    const cl = bone(`clavicle_${side}`, sp3, sx * 0.05, 0.15, 0)
    const up = bone(`upperarm_${side}`, cl, sx * 0.15, 0, 0), low = bone(`lowerarm_${side}`, up, sx * 0.3, 0, 0)
    const hand = bone(`hand_${side}`, low, sx * 0.25, 0, 0)
    const i1 = bone(`index_01_${side}`, hand, sx * 0.08, 0, 0.02); const i2 = bone(`index_02_${side}`, i1, sx * 0.04, 0, 0); bone(`index_03_${side}`, i2, sx * 0.03, 0, 0)
    bone(`pinky_01_${side}`, hand, sx * 0.08, 0, -0.03)
    const th = bone(`thigh_${side}`, pelvis, sx * 0.1, -0.05, 0), calf = bone(`calf_${side}`, th, 0, -0.45, 0); bone(`foot_${side}`, calf, 0, -0.45, 0)
  }
  return root
}

const dir = (a: THREE.Object3D, b: THREE.Object3D) => b.getWorldPosition(new THREE.Vector3()).sub(a.getWorldPosition(new THREE.Vector3())).normalize()

describe('the Detailed level follows the figure (CA1)', () => {
  it.each(['stand', 'walk', 'point', 'sit', 'crouch'])('posed by the %s preset', (name) => {
    const mat = new THREE.MeshBasicMaterial()
    const fig = mannequin(mat, POSES[name])
    const holder = new THREE.Group(); holder.add(fig.root)
    holder.rotation.y = 0.7                                                     // a figure turned on the stage
    holder.updateMatrixWorld(true)
    const d = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs)
    const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
    holder.updateMatrixWorld(true)
    // every mapped limb points where the figure's points
    const pairs: [string, string, keyof typeof fig.joints, keyof typeof fig.joints | 'wrist' | 'ankle'][] = [
      ['upperarm_r', 'lowerarm_r', 'r_shoulder', 'r_elbow'], ['upperarm_l', 'lowerarm_l', 'l_shoulder', 'l_elbow'],
      ['thigh_r', 'calf_r', 'r_hip', 'r_knee'], ['thigh_l', 'calf_l', 'l_hip', 'l_knee'], ['lowerarm_r', 'hand_r', 'r_elbow', 'wrist'], ['calf_l', 'foot_l', 'l_knee', 'ankle']]
    for (const [ba, bb, ja, jb] of pairs) {
      const end = jb === 'wrist' ? fig.markers[4] : jb === 'ankle' ? fig.markers[13] : fig.joints[jb]
      const want = dir(fig.joints[ja], end), have = dir(b(ba), b(bb))
      expect(have.angleTo(want), `${name}: ${ba}`).toBeLessThan(0.01)
    }
    expect(dir(b('spine_01'), b('neck_01')).angleTo(dir(fig.joints.spine, fig.joints.neck))).toBeLessThan(0.01)
    expect(b('pelvis').getWorldPosition(new THREE.Vector3()).distanceTo(fig.joints.root.getWorldPosition(new THREE.Vector3()))).toBeLessThan(1e-4)
    // the segments take the figure's lengths
    const len = (a: THREE.Object3D, c: THREE.Object3D) => a.getWorldPosition(new THREE.Vector3()).distanceTo(c.getWorldPosition(new THREE.Vector3()))
    expect(len(b('thigh_r'), b('calf_r'))).toBeCloseTo(len(fig.joints.r_hip, fig.joints.r_knee), 4)
    expect(len(b('upperarm_l'), b('lowerarm_l'))).toBeCloseTo(len(fig.joints.l_shoulder, fig.joints.l_elbow), 4)
  })

  it("CS3: drawn as its hands only for a figure whose shell is its body, whole again after", () => {
    const rig = synthetic()
    const bones: THREE.Bone[] = []; rig.traverse((o) => { if ((o as THREE.Bone).isBone) bones.push(o as THREE.Bone) })
    const at = (n: string) => bones.findIndex((b) => b.name === n)
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(new Array(18).fill(0).map((_, i) => i * 0.01), 3))
    g.setIndex([0, 1, 2, 3, 4, 5])
    const hand = at('index_02_r'), torso = at('spine_02')                       // a finger's triangle and the chest's
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute([hand, 0, 0, 0, hand, 0, 0, 0, hand, 0, 0, 0, torso, 0, 0, 0, torso, 0, 0, 0, torso, 0, 0, 0], 4))
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute([1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0], 4))
    const skin = new THREE.SkinnedMesh(g, new THREE.MeshBasicMaterial()); rig.add(skin); skin.bind(new THREE.Skeleton(bones))
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root); holder.updateMatrixWorld(true)
    const d = makeDetailed(rig, 'unreal', holder, fig.joints, fig.limbs)
    d.handsOnly(true)
    expect(Array.from(g.index!.array)).toEqual([0, 1, 2])
    d.handsOnly(false)
    expect(Array.from(g.index!.array)).toEqual([0, 1, 2, 3, 4, 5])
  })
  it('keeps following when the pose changes, and turns a bone of its own', () => {
    const mat = new THREE.MeshBasicMaterial()
    const fig = mannequin(mat, POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root)
    const d = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs)
    const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
    const finger = () => dir(b('hand_r'), b('index_01_r'))
    const before = finger().clone()
    applyPose(fig.joints, POSES.wave)
    holder.updateMatrixWorld(true)
    d.follow(fig.joints, { index_01_r: [0, 0, 0], hand_r: [0, 0, 60] })
    expect(dir(b('upperarm_r'), b('lowerarm_r')).angleTo(dir(fig.joints.r_shoulder, fig.joints.r_elbow))).toBeLessThan(0.01)
    expect(finger().angleTo(before)).toBeGreaterThan(0.3)                       // the wrist's own turn moved the finger
  })

  it('closes a fist toward the palm (a T-pose hand, palm down)', () => {
    const mat = new THREE.MeshBasicMaterial()
    const fig = mannequin(mat, POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root)
    const d = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs)
    const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
    const fist = d.handPreset('r', 'fist')
    expect(Object.keys(fist)).toEqual(expect.arrayContaining(['index_01_r', 'index_02_r']))
    expect(d.handPreset('r', 'open').index_01_r).toEqual([0, 0, 0])
    // the hand as it hangs: measure the curl in the hand's own frame (toward its palm side)
    const tipIn = () => b('hand_r').worldToLocal(b('index_03_r').getWorldPosition(new THREE.Vector3()))
    d.follow(fig.joints, d.handPreset('r', 'open'))                            // the open hand asked for: a key's turns win over the rest hand
    const open = tipIn()
    d.follow(fig.joints, fist)
    const closed = tipIn()
    expect(closed.distanceTo(new THREE.Vector3())).toBeLessThan(open.distanceTo(new THREE.Vector3()) - 0.02)   // the fingertip comes in
    expect(closed.y).toBeLessThan(open.y - 0.02)                                 // … toward the palm (the hand's −Y in a palm-down T-pose)
  })

  it("carries the hands' and feet's markers for the pose pass (D101) when the rig has fingers", () => {
    const rig = synthetic()
    const add = (name: string, parent: string, x: number, y: number, z: number) => { const b = new THREE.Bone(); b.name = name; b.position.set(x, y, z); rig.getObjectByName(parent)!.add(b) }
    for (const [s, sx] of [['r', -1], ['l', 1]] as const) {
      for (const [f, z] of [['thumb', 0.04], ['middle', 0], ['ring', -0.015]] as const) {
        add(`${f}_01_${s}`, `hand_${s}`, sx * 0.08, 0, z); add(`${f}_02_${s}`, `${f}_01_${s}`, sx * 0.04, 0, 0); add(`${f}_03_${s}`, `${f}_02_${s}`, sx * 0.03, 0, 0)
      }
      add(`pinky_02_${s}`, `pinky_01_${s}`, sx * 0.03, 0, 0); add(`pinky_03_${s}`, `pinky_02_${s}`, sx * 0.02, 0, 0)
      add(`index_04_leaf_${s}`, `index_03_${s}`, sx * 0.02, 0, 0)
      add(`ball_${s}`, `foot_${s}`, 0, -0.05, 0.12); add(`ball_leaf_${s}`, `ball_${s}`, 0, 0, 0.06)
    }
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root)
    const d = makeDetailed(rig, 'unreal', holder, fig.joints, fig.limbs)
    expect(d.wholebody).not.toBeNull()
    const wb = d.wholebody!
    expect([wb.left.length, wb.right.length, wb.feet.length]).toEqual([21, 21, 6])
    const at = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())
    const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
    expect(at(wb.right[0]).distanceTo(at(b('hand_r')))).toBeLessThan(1e-5)          // the wrist is the hand bone
    expect(at(wb.right[8]).distanceTo(at(b('index_04_leaf_r')))).toBeLessThan(1e-5)  // the index tip is its leaf bone
    applyPose(fig.joints, POSES.wave); holder.updateMatrixWorld(true); d.follow(fig.joints, {})
    expect(at(wb.right[0]).distanceTo(at(b('hand_r')))).toBeLessThan(1e-5)          // and they move with it
    expect(at(wb.feet[2]).y).toBeLessThan(at(b('foot_l')).y)                         // the heel sits below the ankle
    const noFingers = makeDetailed(synthetic(), 'unreal', new THREE.Group(), mannequin(new THREE.MeshBasicMaterial()).joints, fig.limbs)
    expect(noFingers.wholebody).toBeNull()
  })
})

describe('one body (proto01_UIcast CS1 · S1, S2)', () => {
  const at = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())
  it.each(['stand', 'walk', 'point', 'sit'])('the hand starts at the wrist point, the foot at the ankle; shoulders, hips, neck and head where the figure has them (%s)', (name) => {
    const body = { ...DEFAULT_BODY, torso: 1.2, shoulders: 0.85, hips: 1.1, neck: 1.5, legs: 0.85, arms: 0.95, head: 0.9, elbow: 0.55, knee: 0.48 }
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES[name], undefined, body)
    const holder = new THREE.Group(); holder.add(fig.root); holder.rotation.y = -0.4; holder.updateMatrixWorld(true)
    const d = makeDetailed(synthetic(), 'unreal', fig.joints.root.parent!, fig.joints, fig.limbs, { head: body.head })
    const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
    holder.updateMatrixWorld(true)
    const near = (bone: string, o: THREE.Object3D) => expect(at(b(bone)).distanceTo(at(o)), `${name}: ${bone}`).toBeLessThan(2e-3)
    near('hand_r', fig.markers[4]); near('hand_l', fig.markers[7])                 // CB5: the hand's points began 0.033 of the height below the wrist
    near('foot_r', fig.markers[10]); near('foot_l', fig.markers[13])
    near('upperarm_r', fig.joints.r_shoulder); near('upperarm_l', fig.joints.l_shoulder)
    near('thigh_r', fig.joints.r_hip); near('thigh_l', fig.joints.l_hip)
    near('neck_01', fig.joints.neck); near('Head', fig.joints.head)
  })
  it("rests the fingers as the character does (relaxed unless its body says), a key's turns winning", () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root)
    const tip = (d: ReturnType<typeof makeDetailed>) => { const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
      return b('hand_r').worldToLocal(at(b('index_03_r'))).length() }
    const relaxed = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs)
    relaxed.follow(fig.joints, {})
    const atRest = tip(relaxed)
    relaxed.follow(fig.joints, relaxed.handPreset('r', 'open'))
    expect(atRest).toBeLessThan(tip(relaxed) - 1e-3)                               // the GLB's flat hand is never the rest
    const fist = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs, { handRest: { preset: 'fist', curl: 1 } })
    fist.follow(fig.joints, {})
    expect(tip(fist)).toBeLessThan(atRest - 0.01)                                  // the character's own rest
    const flat = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs, { handRest: { preset: 'relaxed', curl: 0 } })
    flat.follow(fig.joints, {})
    expect(tip(flat)).toBeCloseTo(tip(relaxed), 4)                                 // curl 0: the open hand
  })
})

describe("the hands' and feet's rest rows (proto01_UIcast CS2)", () => {
  const at = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())
  it('the spread fans the fingers apart at the knuckles; the thumb opens; the feet turn out', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root)
    const gap = (spread: number) => {
      const d = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs, { handRest: { preset: 'open', curl: 1, spread } })
      const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
      d.follow(fig.joints, {}); holder.updateMatrixWorld(true)
      return at(b('index_03_r')).distanceTo(at(b('pinky_01_r')))
    }
    expect(gap(20)).toBeGreaterThan(gap(0) + 0.005)                                  // the index fans away from the pinky
    const turn = (out: number) => {
      const d = makeDetailed(synthetic(), 'unreal', holder, fig.joints, fig.limbs, { feetOut: out })
      d.follow(fig.joints, {}); holder.updateMatrixWorld(true)
      const b = (n: string) => d.bones.get(n.replace(/[_\s.:-]/g, '').toLowerCase())!
      return b('foot_r').getWorldQuaternion(new THREE.Quaternion())
    }
    expect(turn(20).angleTo(turn(0))).toBeCloseTo((20 * Math.PI) / 180, 2)          // the foot turned 20° about the figure's up
  })
})
