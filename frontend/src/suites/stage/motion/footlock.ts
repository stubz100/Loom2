// CA1 (proto01_animate 01 step 5: "foot lock"; 02 §5's bar: feet do not slide more than 2 cm): a retargeted clip's root moved so that the
// foot on the ground stays where it was planted. Pure: forward kinematics on an off-screen figure (builders.mannequin with the figure's
// body), no render, no store.
//
// The **planted** foot is the lower one (each against its own lowest point in the clip): it stays planted until the other is clearly lower
// (1 cm), so the heel-to-toe roll at push-off does not hand the weight over early. Only when both feet are well off the ground (a jog's
// flight, a jump) is neither planted, and the root carries its last velocity. Frame by frame the root takes the opposite of the planted
// ankle's horizontal drift, so the planted foot holds still — an in-place walk loop (Quaternius' `Walk_Loop`) thereby gains its natural
// forward travel from the feet, and a clip with root motion loses its residual sliding. The height is left as the clip has it.
import * as THREE from 'three'
import type { Body } from '../body'
import { applyPose, mannequin, POSES, type Mannequin } from '../builders'
import type { MotionFrame } from './retarget'

const FLIGHT_M = 0.12                                                       // both ankles this far above their lowest: neither foot is down
const HANDOVER_M = 0.01                                                     // the other foot takes the weight once it is this much lower

/** Off-screen forward kinematics: both ankles (world, metres) of the figure for a frame's joints and root offset. */
export function ankles(fig: Mannequin, f: MotionFrame): { r: THREE.Vector3; l: THREE.Vector3 } {
  applyPose(fig.joints, POSES.stand, f.joints)
  fig.root.position.set(f.offset[0], f.offset[1], f.offset[2])
  fig.root.updateMatrixWorld(true)
  return {
    r: new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.r_knee.matrixWorld),
    l: new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.l_knee.matrixWorld),
  }
}

/** Which foot is down at each frame (null: neither — a jump, a fall). */
export function stance(frames: MotionFrame[], body?: Body | null): ('r' | 'l' | null)[] {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const a = frames.map((f) => ankles(fig, f))
  const lowR = Math.min(...a.map((x) => x.r.y)), lowL = Math.min(...a.map((x) => x.l.y))
  const out: ('r' | 'l' | null)[] = []
  let prev: 'r' | 'l' | null = null
  for (const x of a) {
    const hr = x.r.y - lowR, hl = x.l.y - lowL
    let pick: 'r' | 'l' | null
    if (hr > FLIGHT_M && hl > FLIGHT_M) pick = null
    else if (prev === 'r') pick = hl < hr - HANDOVER_M ? 'l' : 'r'
    else if (prev === 'l') pick = hr < hl - HANDOVER_M ? 'r' : 'l'
    else pick = hr <= hl ? 'r' : 'l'
    out.push(pick)
    prev = pick
  }
  return out
}

/** The frames with their root moved so the locked foot never drifts sideways; the joints and heights as they were. */
export function footLock(frames: MotionFrame[], body?: Body | null): MotionFrame[] {
  if (frames.length < 2) return frames
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const down = stance(frames, body)
  const out: MotionFrame[] = []
  let ox = 0, oz = 0, vx = 0, vz = 0
  let prevAnkle: THREE.Vector3 | null = null
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i]
    const foot = down[i]
    if (!foot && i > 0) { ox += vx; oz += vz }                              // in the air: the root keeps its last pace
    const shifted = { ...f, offset: [f.offset[0] + ox, f.offset[1], f.offset[2] + oz] as [number, number, number] }
    if (foot && i > 0 && down[i - 1] === foot && prevAnkle) {
      const now = ankles(fig, shifted)[foot]
      const dx = now.x - prevAnkle.x, dz = now.z - prevAnkle.z
      ox -= dx; oz -= dz                                                    // undo the planted foot's drift
      vx = (frames[i].offset[0] - frames[i - 1].offset[0]) - dx; vz = (frames[i].offset[2] - frames[i - 1].offset[2]) - dz
      shifted.offset = [f.offset[0] + ox, f.offset[1], f.offset[2] + oz]
    }
    out.push(shifted)
    prevAnkle = foot ? ankles(fig, shifted)[foot] : null
  }
  return out
}

/** The largest horizontal drift of a planted foot over any stance (metres) — the 2 cm bar's measure. */
export function footSlide(frames: MotionFrame[], body?: Body | null): number {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const down = stance(frames, body)
  let worst = 0
  let plant: THREE.Vector3 | null = null
  for (let i = 0; i < frames.length; i++) {
    const foot = down[i]
    if (!foot) { plant = null; continue }
    const p = ankles(fig, frames[i])[foot]
    if (i === 0 || down[i - 1] !== foot || !plant) { plant = p; continue }
    worst = Math.max(worst, Math.hypot(p.x - plant.x, p.z - plant.z))
  }
  return worst
}

/** CA1: the largest drift of a planted foot over the baked keys themselves, in world space — the keys' placement (a path's turns included)
 *  and joints posed on an off-screen figure, frame by frame. The acceptance's measure (02 §5: ≤ 2 cm). */
export function keySlide(keys: { transform: { pos: number[]; rot: number[]; scale: number[] }; pose?: { joints: Record<string, number[]> } | null }[], body?: Body | null): number {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const holder = new THREE.Group(); holder.add(fig.root)
  const world = keys.map((k) => {
    applyPose(fig.joints, POSES.stand, k.pose?.joints)
    holder.position.set(k.transform.pos[0], k.transform.pos[1], k.transform.pos[2])
    holder.rotation.set(THREE.MathUtils.degToRad(k.transform.rot[0] ?? 0), THREE.MathUtils.degToRad(k.transform.rot[1] ?? 0), THREE.MathUtils.degToRad(k.transform.rot[2] ?? 0))
    holder.scale.set(k.transform.scale[0] ?? 1, k.transform.scale[1] ?? 1, k.transform.scale[2] ?? 1)
    holder.updateMatrixWorld(true)
    return { r: new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.r_knee.matrixWorld), l: new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.l_knee.matrixWorld) }
  })
  const lowR = Math.min(...world.map((w) => w.r.y)), lowL = Math.min(...world.map((w) => w.l.y))
  let prev: 'r' | 'l' | null = null, plant: THREE.Vector3 | null = null, worst = 0
  for (const w of world) {
    const hr = w.r.y - lowR, hl = w.l.y - lowL
    const foot: 'r' | 'l' | null = hr > 0.12 && hl > 0.12 ? null : prev === 'r' ? (hl < hr - 0.01 ? 'l' : 'r') : prev === 'l' ? (hr < hl - 0.01 ? 'r' : 'l') : hr <= hl ? 'r' : 'l'
    if (!foot) { prev = null; plant = null; continue }
    const p = w[foot]
    if (foot !== prev || !plant) plant = p.clone()
    else worst = Math.max(worst, Math.hypot(p.x - plant.x, p.z - plant.z))
    prev = foot
  }
  return worst
}

