// RG2 (D187 R3; proto01_rig 00 §4): the clay hand — a character's own hand built from its hand skeleton (body.hand_shape, read from its
// hand picture, hands.py): a palm slab between the wrist and the knuckles, each finger tapered capsules of its own length and width, a claw a
// cone at the tip. Every piece rides on the bone it belongs to (the mannequin's finger bones, moved to the character's knuckles and lengths
// by detailed.ts), so it poses with the same presets and keys; a hidden finger (Q4's count) is not built. Drawn on a shell in place of the
// mannequin's human hand (handsOnly), in clay like the shell.
import * as THREE from 'three'
import { ConvexGeometry } from 'three/examples/jsm/geometries/ConvexGeometry.js'

export type FingerName = 'thumb' | 'index' | 'middle' | 'ring' | 'pinky'
export const FINGERS: readonly FingerName[] = ['thumb', 'index', 'middle', 'ring', 'pinky']
/** One finger of a hand shape (hands.Finger): in palm lengths, in the palm's frame (+x toward the thumb). */
export interface FingerShape { base: number[]; angle: number; lengths: number[]; width: number; claw: number | null }
/** One hand's shape (hands.HandShape). */
export interface HandShape { count: 3 | 4 | 5; palm_width: number; claw: number; fingers: Partial<Record<FingerName, FingerShape>> }
/** Both hands (hands.Hands): the left mirrored from the right while it is null (Q2). */
export interface HandShapes { right: HandShape; left?: HandShape | null }

/** Q4: the fingers a count hides — three long fingers and a thumb is four. */
export const HIDDEN: Record<3 | 4 | 5, FingerName[]> = { 5: [], 4: ['pinky'], 3: ['ring', 'pinky'] }
export const shownFingers = (s: HandShape): FingerName[] => FINGERS.filter((f) => !HIDDEN[s.count ?? 5]?.includes(f))
/** A side's shape: its own, else the right's (mirrored by the palm's frame). */
export const shapeOf = (h: HandShapes, side: 'r' | 'l'): HandShape => (side === 'l' && h.left ? h.left : h.right)

const TAPER = [1, 0.9, 0.8]                                                    // a finger's segments narrow toward the tip
const PALM_DEPTH = 0.3                                                         // the palm's thickness, in palm lengths (a human's ≈ 3 cm for 10)

/** The palm's frame in the figure's frame: the wrist, the way to the middle knuckle (`ey`), across toward the thumb (`ex`), the normal. */
export interface PalmFrame { wrist: THREE.Vector3; ex: THREE.Vector3; ey: THREE.Vector3; n: THREE.Vector3; L: number }

/** A finger's joints in the figure's frame from its shape: the base, then each segment's end along its direction (the angle in the palm's
 *  plane; `lift` the rig's own share of the palm's normal in the finger's direction, so a thumb keeps standing off the palm). */
export function fingerPoints(f: FingerShape, pf: PalmFrame, lift = 0, depth = 0): THREE.Vector3[] {
  const a = THREE.MathUtils.degToRad(f.angle)
  const dir = pf.ey.clone().multiplyScalar(Math.cos(a)).addScaledVector(pf.ex, Math.sin(a)).multiplyScalar(Math.sqrt(Math.max(0, 1 - lift * lift)))
    .addScaledVector(pf.n, lift).normalize()
  const p = pf.wrist.clone().addScaledVector(pf.ex, f.base[0] * pf.L).addScaledVector(pf.ey, f.base[1] * pf.L).addScaledVector(pf.n, depth)
  const out = [p.clone()]
  for (const s of f.lengths) { p.addScaledVector(dir, s * pf.L); out.push(p.clone()) }
  return out
}

/** A capsule from `a` to `b` (both in `bone`'s local frame) of `radius` (local units), added to the bone. */
function capsule(bone: THREE.Object3D, a: THREE.Vector3, b: THREE.Vector3, radius: number, material: THREE.Material): THREE.Mesh {
  const d = b.clone().sub(a), len = d.length()
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(Math.max(1e-4, radius), Math.max(1e-4, len), 4, 10), material)
  m.position.copy(a).addScaledVector(d, 0.5)
  if (len > 1e-9) m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize())
  m.userData.clayHand = true
  bone.add(m)
  return m
}

/** A claw: a cone from the tip `a` along `dir` (local), `length` and `radius` in local units. */
function claw(bone: THREE.Object3D, a: THREE.Vector3, dir: THREE.Vector3, length: number, radius: number, material: THREE.Material): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.ConeGeometry(Math.max(1e-4, radius), Math.max(1e-4, length), 10), material)
  m.position.copy(a).addScaledVector(dir, length / 2)
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize())
  m.userData.clayHand = true
  bone.add(m)
  return m
}

/**
 * Build one clay hand on its bones. `hand` is the hand bone (the wrist), `chains[f]` the finger's three bones (knuckle, middle, end) with
 * its tip point; all positions are given in the figure's frame (`toLocal` turns one into a bone's local frame, `scaleOf` the bone's local
 * units per metre). Returns the meshes (to show or hide together).
 */
export function buildClayHand(shape: HandShape, pf: PalmFrame, hand: THREE.Object3D, chains: Partial<Record<FingerName, { bones: THREE.Object3D[]; points: THREE.Vector3[] }>>,
                              toLocal: (bone: THREE.Object3D, figPoint: THREE.Vector3) => THREE.Vector3, scaleOf: (bone: THREE.Object3D) => number,
                              material: THREE.Material): THREE.Mesh[] {
  const out: THREE.Mesh[] = []
  const shown = shownFingers(shape)
  for (const f of shown) {
    const c = chains[f], fs = shape.fingers[f]
    if (!c || !fs || c.points.length < 4) continue
    for (let k = 0; k < 3; k++) {
      const bone = c.bones[k], s = scaleOf(bone)
      out.push(capsule(bone, toLocal(bone, c.points[k]), toLocal(bone, c.points[k + 1]), (fs.width * pf.L * TAPER[k] * s) / 2, material))
    }
    const len = (fs.claw ?? shape.claw) * pf.L
    if (len > 1e-4) {
      const bone = c.bones[2], s = scaleOf(bone)
      const a = toLocal(bone, c.points[3]), dir = a.clone().sub(toLocal(bone, c.points[2])).normalize()
      out.push(claw(bone, a, dir, len * s, (fs.width * pf.L * TAPER[2] * 0.45 * s), material))
    }
  }
  // the palm: the hull of the wrist's two sides and the shown fingers' bases (the thumb's root too), a palm's depth thick
  const half = (PALM_DEPTH * pf.L) / 2
  const wristHalf = 0.4 * shape.palm_width * pf.L
  const pts: THREE.Vector3[] = [pf.wrist.clone().addScaledVector(pf.ex, wristHalf), pf.wrist.clone().addScaledVector(pf.ex, -wristHalf)]
  for (const f of [...shown]) {
    const c = chains[f]
    if (!c) continue
    pts.push(f === 'thumb' ? c.points[0].clone().lerp(c.points[1], 0.35) : c.points[0].clone())
  }
  const local: THREE.Vector3[] = []
  for (const p of pts) for (const sgn of [1, -1]) local.push(toLocal(hand, p.clone().addScaledVector(pf.n, sgn * half)))
  if (local.length >= 8) {
    try {
      const m = new THREE.Mesh(new ConvexGeometry(local), material)
      m.userData.clayHand = true
      hand.add(m)
      out.push(m)
    } catch { /* a degenerate hull (all points in a line): no palm, the fingers stand */ }
  }
  return out
}
