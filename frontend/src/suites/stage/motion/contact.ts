// AP1 (proto01_UIcast 06 §2.9; E39 → D141): the feet on the floor — the vertical contact the foot lock (footlock.ts, horizontal) leaves out.
// E39 found a clip's or a preset's deep knee bends 3–7 cm off the floor already on the default adult, and a character's proportions move
// that (the root's height scales with the hip, the knee's angle does not know the leg's halves). Pure: forward kinematics on an off-screen
// figure (builders.mannequin with the figure's body), no render, no store.
//   · a clip: through each stance the figure raised or lowered so the planted foot's lowest point meets the floor (its standing height),
//     eased between stances; then a foot still under the floor (a crouch's second foot) bent up onto it by two-bone IK (ik.ts, as Stage's
//     IK handle bends a leg, the knee keeping its way);
//   · a pose: the drop that sets its lower foot on the floor, the other bent up the same way.
import * as THREE from 'three'
import type { Body } from '../body'
import { applyPose, mannequin, POSES, type Mannequin } from '../builders'
import { solveTwoBone } from '../ik'
import { stance } from './footlock'
import type { MotionFrame } from './retarget'

const EASE = 2                                                              // frames each side the stances' heights are eased over
const UNDER_M = 0.003                                                       // a foot this far under the floor is bent up onto it

const ankleY = (fig: Mannequin, side: 'r' | 'l') => new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints[side === 'r' ? 'r_knee' : 'l_knee'].matrixWorld).y
const rad = THREE.MathUtils.degToRad

function posed(fig: Mannequin, joints: Record<string, number[]> | undefined, offset: [number, number, number], preset = 'stand'): void {
  applyPose(fig.joints, POSES[preset] ?? POSES.stand, joints)
  fig.root.position.set(offset[0], offset[1], offset[2])
  fig.root.updateMatrixWorld(true)
}

/** The figure's ankles standing (the floor's height for each foot). */
function standing(fig: Mannequin): { r: number; l: number } {
  posed(fig, undefined, [0, 0, 0])
  return { r: ankleY(fig, 'r'), l: ankleY(fig, 'l') }
}

/** A leg bent so its ankle is at height `y`, its knee bending the way it already does; the hip's and knee's turns (degrees YXZ). */
function legTo(fig: Mannequin, side: 'r' | 'l', y: number): { hip: number[]; knee: number[] } {
  const upper = fig.joints[side === 'r' ? 'r_hip' : 'l_hip'], lower = fig.joints[side === 'r' ? 'r_knee' : 'l_knee'], parent = upper.parent!
  const ankle = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(lower.matrixWorld).setY(y)
  const target = parent.worldToLocal(ankle.clone()), knee = parent.worldToLocal(lower.getWorldPosition(new THREE.Vector3()))
  const bend = knee.clone().sub(upper.position.clone().add(target).multiplyScalar(0.5))
  const s = solveTwoBone(upper.position, target, fig.limbs.thigh, fig.limbs.shin, bend.lengthSq() > 1e-8 ? bend : new THREE.Vector3(0, 0, 1))
  upper.rotation.set(rad(s.upper[0]), rad(s.upper[1]), rad(s.upper[2]), 'YXZ'); lower.rotation.set(rad(s.lower[0]), rad(s.lower[1]), rad(s.lower[2]), 'YXZ')
  fig.root.updateMatrixWorld(true)
  return { hip: s.upper.map((v) => Math.round(v * 100) / 100), knee: s.lower.map((v) => Math.round(v * 100) / 100) }
}

/** A clip's frames with their feet on the floor: the height through each stance, a foot under the floor bent up (the foot lock first). */
export function footContact(frames: MotionFrame[], body?: Body | null): MotionFrame[] {
  if (frames.length < 2) return frames
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const rest = standing(fig)
  const down = stance(frames, body)
  const shift = new Array<number>(frames.length).fill(NaN)
  for (let i = 0; i < frames.length;) {                                      // each stance: the planted foot's lowest point onto the floor
    const foot = down[i]
    let j = i
    while (j < frames.length && down[j] === foot) j++
    if (foot) {
      let low = Infinity
      for (let k = i; k < j; k++) { posed(fig, frames[k].joints, frames[k].offset); low = Math.min(low, ankleY(fig, foot) - rest[foot]) }
      for (let k = i; k < j; k++) shift[k] = -low
    }
    i = j
  }
  for (let i = 0; i < shift.length; i++) if (Number.isNaN(shift[i])) shift[i] = i > 0 ? shift[i - 1] : (shift.find((x) => !Number.isNaN(x)) ?? 0)   // the air keeps the last stance's
  const eased = shift.map((_, i) => { let sum = 0, n = 0; for (let k = Math.max(0, i - EASE); k <= Math.min(shift.length - 1, i + EASE); k++) { sum += shift[k]; n++ } return sum / n })
  return frames.map((f, i) => {
    const offset: [number, number, number] = [f.offset[0], f.offset[1] + eased[i], f.offset[2]]
    posed(fig, f.joints, offset)
    const joints = { ...f.joints }
    for (const side of ['r', 'l'] as const) {
      if (ankleY(fig, side) - rest[side] < -UNDER_M) {
        const t = legTo(fig, side, rest[side])
        joints[side === 'r' ? 'r_hip' : 'l_hip'] = t.hip; joints[side === 'r' ? 'r_knee' : 'l_knee'] = t.knee
      }
    }
    return { joints, offset: [offset[0], Math.round(offset[1] * 1e4) / 1e4, offset[2]] }
  })
}

/** A pose on its feet: the drop (metres, the root moved down; negative raises it) that sets its lower foot on the floor, and the other leg
 *  bent up where it would go under. `joints` as the figure's pose (the preset's own where it gives none). */
export function poseContact(preset: string, joints: Record<string, number[]> | undefined, body?: Body | null): { ground: number; joints: Record<string, number[]> } {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const rest = standing(fig)
  posed(fig, joints, [0, 0, 0], preset)
  const low = Math.min(ankleY(fig, 'r') - rest.r, ankleY(fig, 'l') - rest.l)
  posed(fig, joints, [0, -low, 0], preset)
  const out = { ...(joints ?? {}) }
  for (const side of ['r', 'l'] as const) {
    if (ankleY(fig, side) - rest[side] < -UNDER_M) {
      const t = legTo(fig, side, rest[side])
      out[side === 'r' ? 'r_hip' : 'l_hip'] = t.hip; out[side === 'r' ? 'r_knee' : 'l_knee'] = t.knee
    }
  }
  return { ground: Math.round(low * 1e4) / 1e4, joints: out }
}
