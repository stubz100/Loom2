// P13 / ST2 (D81): posing maths, pure — the mannequin's limb lengths, the analytic two-bone IK that puts a hand or a foot on a target
// (16 §3d: "drag the hand, elbow and shoulder follow"), and the mirror of a pose. Angles are degrees in the YXZ order applyPose uses;
// a limb hangs along −Y at rest, its hinge is X: a negative X pitches it forward (E10's presets), so elbows bend toward +Z and knees
// toward −Z. `CCDIKSolver` is the fallback the plan names; this solver covers every two-bone case the mannequin has.
import * as THREE from 'three'
import { JOINTS, type Joint } from './builders'

export const LIMB = { upper_arm: 0.29, forearm: 0.27, thigh: 0.44, shin: 0.43 } as const
export type Chain = 'r_arm' | 'l_arm' | 'r_leg' | 'l_leg'
export const CHAINS: Record<Chain, { upper: Joint; lower: Joint; a: number; b: number; bend: [number, number, number] }> = {
  r_arm: { upper: 'r_shoulder', lower: 'r_elbow', a: LIMB.upper_arm, b: LIMB.forearm, bend: [0, 0, 1] },
  l_arm: { upper: 'l_shoulder', lower: 'l_elbow', a: LIMB.upper_arm, b: LIMB.forearm, bend: [0, 0, 1] },
  r_leg: { upper: 'r_hip', lower: 'r_knee', a: LIMB.thigh, b: LIMB.shin, bend: [0, 0, -1] },
  l_leg: { upper: 'l_hip', lower: 'l_knee', a: LIMB.thigh, b: LIMB.shin, bend: [0, 0, -1] },
}

const deg = THREE.MathUtils.radToDeg
const DOWN = new THREE.Vector3(0, -1, 0)

/** Degrees YXZ of a quaternion, rounded for the document. */
export function eulerDeg(q: THREE.Quaternion): [number, number, number] {
  const e = new THREE.Euler().setFromQuaternion(q, 'YXZ')
  return [+deg(e.x).toFixed(2), +deg(e.y).toFixed(2), +deg(e.z).toFixed(2)]
}

/**
 * Two-bone IK in the chain root's parent space: `root` is the upper joint's position, `target` the wanted end position (both in the
 * parent's local frame), `a` / `b` the bone lengths, `bend` the direction the middle joint bows toward. Returns the upper and lower
 * joints' rotations (degrees, YXZ) — the end lands on the target when it is within reach, else the chain points straight at it.
 */
export function solveTwoBone(root: THREE.Vector3, target: THREE.Vector3, a: number, b: number, bend: THREE.Vector3): { upper: [number, number, number]; lower: [number, number, number]; reach: number } {
  const toT = target.clone().sub(root)
  const dist = toT.length()
  const d = Math.max(1e-4, Math.min(a + b - 1e-4, dist))
  const dir = dist > 1e-6 ? toT.clone().normalize() : DOWN.clone()
  // the bend plane: spanned by the target direction and the bend hint (a fallback when they are parallel)
  let pole = bend.clone().normalize()
  if (Math.abs(pole.dot(dir)) > 0.999) pole = Math.abs(dir.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0)
  const n = new THREE.Vector3().crossVectors(dir, pole).normalize()           // the hinge axis
  const inPlane = new THREE.Vector3().crossVectors(n, dir).normalize()        // in the plane, toward the bend side
  const cosS = Math.max(-1, Math.min(1, (a * a + d * d - b * b) / (2 * a * d)))
  const bendAngle = Math.acos(cosS)
  const upperDir = dir.clone().multiplyScalar(Math.cos(bendAngle)).add(inPlane.clone().multiplyScalar(Math.sin(bendAngle))).normalize()
  const elbow = root.clone().add(upperDir.clone().multiplyScalar(a))
  const lowerDir = target.clone().sub(elbow)
  if (lowerDir.lengthSq() < 1e-10) lowerDir.copy(dir)
  lowerDir.normalize()
  // the upper bone's frame: its −Y points down the bone, its X is the hinge
  const yU = upperDir.clone().negate()
  const xU = n.clone()
  const zU = new THREE.Vector3().crossVectors(xU, yU).normalize()
  xU.crossVectors(yU, zU).normalize()
  const qUpper = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(xU, yU, zU))
  // the lower bone turns about the hinge inside the upper's frame
  const localLower = lowerDir.clone().applyQuaternion(qUpper.clone().invert())
  const angle = Math.atan2(-localLower.z, -localLower.y)                     // 0 = straight on; rotating −Y about X by θ gives (0, −cos θ, −sin θ)
  const qLower = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), angle)
  return { upper: eulerDeg(qUpper), lower: eulerDeg(qLower), reach: Math.min(1, dist / (a + b)) }
}

/** The pose seen in a mirror: left and right joints swap, Y and Z rotations change sign (the X pitch keeps). */
export function mirrorJoints(joints: Record<string, number[]>): Record<string, number[]> {
  const out: Record<string, number[]> = {}
  for (const j of JOINTS) {
    const src = j.startsWith('r_') ? ('l_' + j.slice(2)) as Joint : j.startsWith('l_') ? ('r_' + j.slice(2)) as Joint : j
    const v = joints[src]
    if (!v) continue
    out[j] = [v[0], -v[1] || 0, -v[2] || 0]
  }
  return out
}

/** Forward kinematics of one chain for the tests and the handles: the elbow / knee and the end position in the parent's space. */
export function forwardTwoBone(root: THREE.Vector3, upper: [number, number, number], lower: [number, number, number], a: number, b: number): { mid: THREE.Vector3; end: THREE.Vector3 } {
  const r = THREE.MathUtils.degToRad
  const qU = new THREE.Quaternion().setFromEuler(new THREE.Euler(r(upper[0]), r(upper[1]), r(upper[2]), 'YXZ'))
  const qL = new THREE.Quaternion().setFromEuler(new THREE.Euler(r(lower[0]), r(lower[1]), r(lower[2]), 'YXZ'))
  const mid = root.clone().add(DOWN.clone().multiplyScalar(a).applyQuaternion(qU))
  const end = mid.clone().add(DOWN.clone().multiplyScalar(b).applyQuaternion(qL).applyQuaternion(qU))
  return { mid, end }
}
