// D129 (HP1, proto01_animate 31 §2): a held prop — its own 3D model (or stand-in, or image plane) in a figure's hand, never drawn into the
// character. The object keeps `parent` (the figure) and `parent_joint` (which hand); its transform is then local to that hand: the figure's
// wrist marker (COCO-18's wrist, at the forearm's end, turning with it). Pure three.js maths for the engine and the tests.
import * as THREE from 'three'
import type { StageObject } from '../../api/types'

export type Hand = 'r_hand' | 'l_hand'
export const HAND_LABEL: Record<Hand, string> = { r_hand: 'right hand', l_hand: 'left hand' }
/** The figure's marker a hand is (builders.ts `mannequin`: markers[4] the right wrist, markers[7] the left). */
export const HAND_MARKER: Record<Hand, number> = { r_hand: 4, l_hand: 7 }

type Transform = StageObject['transform']
const rad = THREE.MathUtils.degToRad, deg = THREE.MathUtils.radToDeg

export const matrixOf = (t: Transform): THREE.Matrix4 =>
  new THREE.Matrix4().compose(new THREE.Vector3(t.pos[0], t.pos[1], t.pos[2]), new THREE.Quaternion().setFromEuler(new THREE.Euler(rad(t.rot[0]), rad(t.rot[1]), rad(t.rot[2]))),
    new THREE.Vector3(t.scale[0], t.scale[1], t.scale[2]))

export function transformOf(m: THREE.Matrix4): Transform {
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3()
  m.decompose(p, q, s)
  const e = new THREE.Euler().setFromQuaternion(q)
  return { pos: [p.x, p.y, p.z].map((v) => +v.toFixed(4)), rot: [deg(e.x), deg(e.y), deg(e.z)].map((v) => +v.toFixed(2)), scale: [s.x, s.y, s.z].map((v) => +v.toFixed(4)) }
}

/** The held thing's world matrix: its local transform on the hand as the figure stands now. */
export function heldWorld(hand: THREE.Object3D, local: Transform): THREE.Matrix4 {
  hand.updateWorldMatrix(true, false)
  return hand.matrixWorld.clone().multiply(matrixOf(local))
}

/** The local transform (on the hand) of a thing at `world` — a gizmo's move of a held thing, or a thing put into the hand where it stands. */
export function onHand(hand: THREE.Object3D, world: THREE.Matrix4): Transform {
  hand.updateWorldMatrix(true, false)
  return transformOf(hand.matrixWorld.clone().invert().multiply(world))
}

/** The figures a thing can be put in the hand of (the stage's visible mannequins), and whether a thing can be held at all. */
export const canHold = (o: Pick<StageObject, 'kind'>): boolean => o.kind === 'mesh' || o.kind === 'prop' || o.kind === 'plane'
export const holders = (objects: StageObject[]): StageObject[] => objects.filter((o) => o.kind === 'mannequin' && o.visible)
