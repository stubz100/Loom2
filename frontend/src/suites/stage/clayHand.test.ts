// RG2 (D187 R2, R3, R5): a character's own hands on the Detailed level — a synthetic Unreal-named mannequin with five fingers a hand: the
// finger bones moved to the shape's knuckles and lengths (the guide's 21 points follow), the left mirrored from the right, a hidden finger's
// points not drawn, the clay hand built on the bones and shown only as the shell's hands; without a shape, nothing changes.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { mannequin, POSES } from './builders'
import { HIDDEN, shownFingers, type HandShape, type HandShapes } from './clayHand'
import { makeDetailed } from './detailed'
import { projectMarkers } from './passes'

const FINGERS = ['thumb', 'index', 'middle', 'ring', 'pinky'] as const

function synthetic(thumbLift = 0): THREE.Object3D {
  const root = new THREE.Group(); root.name = 'Armature'
  const bone = (name: string, parent: THREE.Object3D, x: number, y: number, z: number) => { const b = new THREE.Bone(); b.name = name; b.position.set(x, y, z); parent.add(b); return b }
  const pelvis = bone('pelvis', root, 0, 1, 0)
  const sp1 = bone('spine_01', pelvis, 0, 0.1, 0), sp2 = bone('spine_02', sp1, 0, 0.15, 0), sp3 = bone('spine_03', sp2, 0, 0.15, 0)
  const neck = bone('neck_01', sp3, 0, 0.2, 0); bone('Head', neck, 0, 0.1, 0)
  for (const [side, sx] of [['r', -1], ['l', 1]] as const) {
    const cl = bone(`clavicle_${side}`, sp3, sx * 0.05, 0.15, 0)
    const up = bone(`upperarm_${side}`, cl, sx * 0.15, 0, 0), low = bone(`lowerarm_${side}`, up, sx * 0.3, 0, 0)
    const hand = bone(`hand_${side}`, low, sx * 0.25, 0, 0)
    // a T-pose hand along ±X, palm down: the thumb forward (+z), the pinky back
    const base: Record<string, [number, number]> = { thumb: [0.03, 0.04], index: [0.09, 0.025], middle: [0.095, 0.005], ring: [0.09, -0.015], pinky: [0.08, -0.035] }
    for (const f of FINGERS) {
      const [x, z] = base[f]
      let b = bone(`${f}_01_${side}`, hand, sx * x, 0, z)
      b = bone(`${f}_02_${side}`, b, sx * 0.035, f === 'thumb' ? -thumbLift : 0, f === 'thumb' ? 0.01 : 0)   // D191: a thumb may stand off the palm (below it), as the mannequin's
      b = bone(`${f}_03_${side}`, b, sx * 0.025, 0, 0)
      bone(`${f}_04_leaf_${side}`, b, sx * 0.02, 0, 0)
    }
    const th = bone(`thigh_${side}`, pelvis, sx * 0.1, -0.05, 0), calf = bone(`calf_${side}`, th, 0, -0.45, 0)
    const foot = bone(`foot_${side}`, calf, 0, -0.45, 0); const ball = bone(`ball_${side}`, foot, 0, -0.04, 0.12); bone(`ball_leaf_${side}`, ball, 0, 0, 0.05)
  }
  return root
}

/** A ghoul's hand: every finger 1.4× the human default, three a hand counted (`count`), a claw. */
function ghoul(count: 3 | 4 | 5 = 5, claw = 0.2): HandShape {
  const human: Record<string, { base: number[]; angle: number; len: number }> = {
    thumb: { base: [0.3, 0.28], angle: 45, len: 0.77 }, index: { base: [0.27, 0.96], angle: 8, len: 0.67 }, middle: { base: [0, 1], angle: 0, len: 0.73 },
    ring: { base: [-0.2, 0.95], angle: -8, len: 0.64 }, pinky: { base: [-0.38, 0.86], angle: -16, len: 0.48 } }
  const fingers = Object.fromEntries(FINGERS.map((f) => { const h = human[f]; const L = h.len * (f === 'thumb' ? 1 : 1.4)
    return [f, { base: h.base, angle: h.angle, lengths: [L * 0.45, L * 0.3, L * 0.25], width: 0.14, claw: null }] }))
  return { count, palm_width: 0.66, claw, fingers }
}

function build(shape: HandShapes | null, thumbLift = 0) {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand)
  const holder = new THREE.Group(); holder.add(fig.root)
  holder.updateMatrixWorld(true)
  const d = makeDetailed(synthetic(thumbLift), 'unreal', holder, fig.joints, fig.limbs, { handShape: shape })
  holder.updateMatrixWorld(true)
  return { d, fig, holder }
}
const W = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())

describe('RG2: the character\'s own hands', () => {
  it('the guide\'s points stand at the shape\'s knuckles and lengths, the left the right mirrored', () => {
    const { d } = build({ right: ghoul(), left: null })
    for (const side of ['right', 'left'] as const) {
      const m = d.wholebody![side], palm = W(m[0]).distanceTo(W(m[9]))         // the wrist to the middle knuckle: the rig's palm
      const len = (i: number) => W(m[i]).distanceTo(W(m[i + 1])) + W(m[i + 1]).distanceTo(W(m[i + 2])) + W(m[i + 2]).distanceTo(W(m[i + 3]))
      expect(len(9) / palm, side).toBeCloseTo(0.73 * 1.4, 2)                   // the middle finger, in palms
      expect(len(5) / palm, side).toBeCloseTo(0.67 * 1.4, 2)
      expect(len(1) / palm, side).toBeCloseTo(0.77, 2)                         // the thumb kept
      expect(W(m[5]).distanceTo(W(m[17])) / palm).toBeCloseTo(Math.hypot(0.27 + 0.38, 0.96 - 0.86), 2)   // the knuckles' spread
    }
    const r = d.wholebody!.right, l = d.wholebody!.left
    expect(W(r[12]).distanceTo(W(r[0]))).toBeCloseTo(W(l[12]).distanceTo(W(l[0])), 5)    // mirrored
  })

  it('a hidden finger is not drawn (Q4) and the clay hand has no piece of it', () => {
    const { d } = build({ right: ghoul(4), left: null })
    const cam = new THREE.OrthographicCamera(-2, 2, 2, -2, 0.1, 10); cam.position.set(0, 1, 5); cam.lookAt(0, 1, 0); cam.updateMatrixWorld(true)
    const [right] = projectMarkers([d.wholebody!.right], cam, 512, 512)
    expect(right.slice(17).every((p) => p[2] === 0)).toBe(true)                // the pinky's four points
    expect(right.slice(0, 17).every((p) => p[2] === 1)).toBe(true)
    expect(shownFingers(ghoul(4))).toEqual(['thumb', 'index', 'middle', 'ring']); expect(HIDDEN[3]).toEqual(['ring', 'pinky'])
    // 4 fingers × 3 capsules + 4 claws + the palm, a hand
    expect(d.clayHands.length).toBe(2 * (4 * 3 + 4 + 1))
  })

  it('the clay hand rides on its bones and shows only as the shell\'s hands', () => {
    const { d, fig, holder } = build({ right: ghoul(5, 0), left: null })
    expect(d.clayHands.length).toBe(2 * (5 * 3 + 1))                           // no claw
    expect(d.clayHands.every((m) => !m.visible)).toBe(true)
    d.handsOnly(true)
    expect(d.clayHands.every((m) => m.visible)).toBe(true)
    const tip = d.wholebody!.right[12], cap = d.clayHands.find((m) => m.parent?.name === 'middle_03_r')!
    const before = W(tip).distanceTo(W(cap))
    d.follow(fig.joints, d.handPreset('r', 'fist')); holder.updateMatrixWorld(true)   // a fist: the capsule turns with its bone
    expect(W(tip).distanceTo(W(cap))).toBeCloseTo(before, 5)
    d.handsOnly(false)
    expect(d.clayHands.every((m) => !m.visible)).toBe(true)
  })

  it('D191: a thumb read spread wide curls into the palm, across it and toward the fingers — not back toward the wrist', () => {
    const spread = ghoul(5, 0); spread.fingers.thumb = { ...spread.fingers.thumb!, angle: 65 }
    const { d, fig, holder } = build({ right: spread, left: null }, 0.03)
    for (const side of ['r', 'l'] as const) {
      const marks = side === 'r' ? d.wholebody!.right : d.wholebody!.left
      const at = (preset: 'open' | 'fist') => { d.follow(fig.joints, { ...d.handPreset('r', preset), ...d.handPreset('l', preset) }); holder.updateMatrixWorld(true); return marks.map(W) }
      const open = at('open'), fist = at('fist')
      const palm = open[0].distanceTo(open[9]), ey = open[9].clone().sub(open[0]).normalize()
      const ex = open[5].clone().sub(open[17]); ex.addScaledVector(ey, -ex.dot(ey)).normalize()     // toward the thumb's side
      const n = fist[8].clone().sub(open[8]); n.addScaledVector(ey, -n.dot(ey)).addScaledVector(ex, -n.dot(ex)).normalize()   // the palm's side: where the index curls
      const moved = fist[4].clone().sub(open[4])
      expect(moved.dot(n) / palm, `${side}: into the palm`).toBeGreaterThan(0.02)
      expect(-moved.dot(ex) / palm, `${side}: across it`).toBeGreaterThan(0.3)
      expect(moved.dot(ey) / palm, `${side}: not back toward the wrist`).toBeGreaterThan(-0.3)
    }
  })

  it('without a shape the mannequin\'s hands stay as they were', () => {
    const plain = build(null).d, again = build(null).d
    expect(plain.clayHands).toEqual([])
    expect(W(plain.wholebody!.right[12]).distanceTo(W(again.wholebody!.right[12]))).toBeLessThan(1e-9)
    const shaped = build({ right: ghoul(), left: null }).d
    expect(W(shaped.wholebody!.right[12]).distanceTo(W(plain.wholebody!.right[12]))).toBeGreaterThan(0.01)
  })
})
