// D129 (HP1): a held thing on its figure's hand — at the wrist with a zero offset, following the arm as the pose changes, and the gizmo's
// world move turned back into a place on the hand.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { applyPose, mannequin, POSES } from './builders'
import { canHold, HAND_MARKER, heldWorld, holders, onHand, transformOf } from './held'
import type { StageObject } from '../../api/types'

const at = (m: THREE.Matrix4) => new THREE.Vector3().setFromMatrixPosition(m)
const wrist = (fig: ReturnType<typeof mannequin>, k: number) => { fig.root.updateMatrixWorld(true); return new THREE.Vector3().setFromMatrixPosition(fig.markers[k].matrixWorld) }
const zero = { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }

describe('a prop held in a hand (D129)', () => {
  it('sits on the wrist and follows the arm', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial())
    const holder = new THREE.Group(); holder.position.set(1, 0, -2); holder.add(fig.root)
    const hand = fig.markers[HAND_MARKER.r_hand]
    expect(at(heldWorld(hand, zero)).distanceTo(wrist(fig, 4))).toBeLessThan(1e-6)
    const before = at(heldWorld(hand, zero))
    applyPose(fig.joints, POSES.wave)                                                              // the right arm up
    const after = at(heldWorld(hand, zero))
    expect(after.y - before.y).toBeGreaterThan(0.5)                                                // up with the hand
    expect(after.distanceTo(wrist(fig, 4))).toBeLessThan(1e-6)
    expect(at(heldWorld(fig.markers[HAND_MARKER.l_hand], zero)).distanceTo(wrist(fig, 7))).toBeLessThan(1e-6)
  })
  it('an offset rides with the hand; a world move comes back as its place on the hand', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial())
    const hand = fig.markers[HAND_MARKER.r_hand]
    const local = { pos: [0, -0.04, 0.03], rot: [10, 20, 30], scale: [1, 1, 1] }
    const w = heldWorld(hand, local)
    const back = onHand(hand, w)
    back.pos.forEach((v, i) => expect(v).toBeCloseTo(local.pos[i], 3))
    back.rot.forEach((v, i) => expect(v).toBeCloseTo(local.rot[i], 1))
    const t = transformOf(w)
    expect(t.pos).toHaveLength(3)
  })
  it('a prop, a stand-in or an image plane can be held, in a visible figure\'s hand', () => {
    expect(['mesh', 'prop', 'plane'].every((k) => canHold({ kind: k as StageObject['kind'] }))).toBe(true)
    expect(canHold({ kind: 'mannequin' }) || canHold({ kind: 'light' }) || canHold({ kind: 'set' })).toBe(false)
    const o = (id: string, kind: StageObject['kind'], visible = true) => ({ id, kind, visible }) as StageObject
    expect(holders([o('a', 'mannequin'), o('b', 'mannequin', false), o('c', 'mesh')]).map((x) => x.id)).toEqual(['a'])
  })
})
