// AP1 (proto01_UIcast 06 §2.9; E39 → D141): the feet on the floor — the vertical contact the foot lock (footlock.ts, horizontal) leaves out.
// E39 found a clip's or a preset's deep knee bends 3–7 cm off the floor already on the default adult, and a character's proportions move
// that (the root's height scales with the hip, the knee's angle does not know the leg's halves). Pure: forward kinematics on an off-screen
// figure (builders.mannequin with the figure's body), no render, no store.
//   · a clip: through each stance the figure raised or lowered so the planted foot's lowest point meets the floor (its standing height),
//     eased between stances; then a foot still under the floor (a crouch's second foot) bent up onto it by two-bone IK (ik.ts, as Stage's
//     IK handle bends a leg, the knee keeping its way);
//   · a pose: the drop that sets its lower foot on the floor, the other bent up the same way;
//   · AP1b, the pose editor's pins: a hand or a foot pinned where it is (the figure's own space) stays there while the rest of the pose
//     changes — its limb bent onto the pin by the same IK — and goes with the limb the author turns or drags.
import * as THREE from 'three'
import { BUILD_WIDTH, type Body } from '../body'
import { applyPose, mannequin, POSES, type Joint, type Mannequin } from '../builders'
import { CHAINS, eulerDeg, figureChain, type Chain } from '../ik'
import { stance } from './footlock'
import type { MotionFrame } from './retarget'

const EASE = 2                                                              // frames each side the stances' heights are eased over
const UNDER_M = 0.003                                                       // a foot this far under the floor is bent up onto it

const ankleY = (fig: Mannequin, side: 'r' | 'l') => new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints[side === 'r' ? 'r_knee' : 'l_knee'].matrixWorld).y

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

// The figure's own space: its root joint's parent's (Stage's holder — the object's transform; the world for a figure off-screen), the floor
// at y = 0. A pin lives there, so it stays put while the hips turn or drop.
const toWorld = (fig: Mannequin, v: THREE.Vector3) => (fig.root.parent ? fig.root.parent.localToWorld(v) : v)
const toOwn = (fig: Mannequin, v: THREE.Vector3) => (fig.root.parent ? fig.root.parent.worldToLocal(v) : v)

// a straight limb bends about its hinge (the lower joint's X) this way: a knee's shin back (+X, the crouch's), an elbow's forearm forward (−X)
const HINGE: Record<Chain, number> = { r_arm: -1, l_arm: -1, r_leg: 1, l_leg: 1 }

/** A limb bent so its end (the wrist, the ankle) reaches `target` (the figure's own space; out of reach: straight toward it). The middle joint
 *  opens or closes in the limb's own plane (law of cosines), then the upper joint swings by the least turn onto the target — the limb keeps
 *  its twist and its knee or elbow its way. The turns written on the figure. */
function reach(fig: Mannequin, chain: Chain, target: THREE.Vector3): void {
  const c = CHAINS[chain], upper = fig.joints[c.upper], lower = fig.joints[c.lower], b = figureChain(fig.limbs, chain).b
  fig.root.updateWorldMatrix(true, true)
  const end = () => new THREE.Vector3(0, -b, 0).applyMatrix4(lower.matrixWorld)
  const turnWorld = (o: THREE.Object3D, q: THREE.Quaternion) => {             // a world turn about the joint's own position
    const parentQ = o.parent!.getWorldQuaternion(new THREE.Quaternion())
    o.quaternion.copy(parentQ.clone().invert().multiply(q).multiply(parentQ).multiply(o.quaternion))
    o.updateMatrixWorld(true)
  }
  const T = toWorld(fig, target.clone())
  const A = upper.getWorldPosition(new THREE.Vector3()), B = lower.getWorldPosition(new THREE.Vector3()), C = end()
  const la = A.distanceTo(B), lb = B.distanceTo(C)
  const d = THREE.MathUtils.clamp(A.distanceTo(T), Math.abs(la - lb) + 1e-4, la + lb - 1e-4)
  const u = A.clone().sub(B).normalize(), w = C.clone().sub(B).normalize()
  const now = u.angleTo(w), want = Math.acos(THREE.MathUtils.clamp((la * la + lb * lb - d * d) / (2 * la * lb), -1, 1))
  let axis = new THREE.Vector3().crossVectors(u, w)                            // turning the lower bone about u × w opens the joint
  if (axis.length() < 1e-4) axis = new THREE.Vector3(-HINGE[chain], 0, 0).transformDirection(lower.matrixWorld)   // straight: about its hinge
  turnWorld(lower, new THREE.Quaternion().setFromAxisAngle(axis.normalize(), want - now))
  const from = end().sub(A).normalize(), to = T.clone().sub(A).normalize()
  turnWorld(upper, new THREE.Quaternion().setFromUnitVectors(from, to))
  fig.root.updateMatrixWorld(true)
}
const turns = (fig: Mannequin, j: Joint) => eulerDeg(fig.joints[j].quaternion)

/** A leg bent so its ankle is at height `y`, its knee bending the way it already does; the hip's and knee's turns (degrees YXZ). */
function legTo(fig: Mannequin, side: 'r' | 'l', y: number): { hip: number[]; knee: number[] } {
  const ankle = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints[side === 'r' ? 'r_knee' : 'l_knee'].matrixWorld).setY(y)
  reach(fig, side === 'r' ? 'r_leg' : 'l_leg', toOwn(fig, ankle))
  return { hip: turns(fig, side === 'r' ? 'r_hip' : 'l_hip'), knee: turns(fig, side === 'r' ? 'r_knee' : 'l_knee') }
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

// ---- AP1b: the pose editor's pins ------------------------------------------------------------------------------------------------------
export type End = 'r_hand' | 'l_hand' | 'r_foot' | 'l_foot'
export const ENDS: readonly End[] = ['r_hand', 'l_hand', 'r_foot', 'l_foot']
export const END_CHAIN: Record<End, Chain> = { r_hand: 'r_arm', l_hand: 'l_arm', r_foot: 'r_leg', l_foot: 'l_leg' }
/** The pinned ends: where each is held, [x, y, z] metres in the figure's own space (its transform aside: a pin moves with the figure). */
export type Pins = Partial<Record<End, number[]>>
/** The limb a joint belongs to (null for the root, spine, neck and head). */
export function chainOf(joint: string | null | undefined): Chain | null {
  return (Object.keys(CHAINS) as Chain[]).find((c) => CHAINS[c].upper === joint || CHAINS[c].lower === joint) ?? null
}

/** An end's position in the figure's own space (the wrist, the ankle). */
function endAt(fig: Mannequin, end: End): THREE.Vector3 {
  const c = figureChain(fig.limbs, END_CHAIN[end])
  return toOwn(fig, new THREE.Vector3(0, -c.b, 0).applyMatrix4(fig.joints[c.lower].matrixWorld))
}
const r4 = (v: THREE.Vector3) => [v.x, v.y, v.z].map((x) => Math.round(x * 1e4) / 1e4)

/** On a live figure (Stage's, while a joint turns): every pinned limb but `except` bent back onto its pin. */
export function holdPins(fig: Mannequin, pins: Pins | null | undefined, except?: Chain | null): void {
  fig.root.updateWorldMatrix(true, true)
  for (const end of ENDS) { const p = pins?.[end]; if (p && END_CHAIN[end] !== except) reach(fig, END_CHAIN[end], new THREE.Vector3(p[0], p[1], p[2])) }
}

function posedFigure(preset: string, joints: Record<string, number[]> | undefined, ground: number, body?: Body | null): Mannequin {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  applyPose(fig.joints, POSES[preset] ?? POSES.stand, joints, ground)
  fig.root.updateMatrixWorld(true)
  return fig
}

/** Where a pose's hands and feet are (the figure's own space) — what *Pin the feet* and *Pin the hands* hold. */
export function endsOf(preset: string, joints: Record<string, number[]> | undefined, ground: number, body?: Body | null): Record<End, number[]> {
  const fig = posedFigure(preset, joints, ground, body)
  return Object.fromEntries(ENDS.map((e) => [e, r4(endAt(fig, e))])) as Record<End, number[]>
}

/** A pose edit with its pins kept: the limb the author turned or dragged (`moved`) takes its pin along to where its end now is; every
 *  other pinned limb is bent back onto its pin. The joints come back with the pinned limbs' turns, the pins as they now are. */
export function pinPose(preset: string, joints: Record<string, number[]>, ground: number, pins: Pins, body: Body | null | undefined, moved: Chain | null): { joints: Record<string, number[]>; pins: Pins } {
  const fig = posedFigure(preset, joints, ground, body)
  const out = { ...joints }, held: Pins = {}
  for (const end of ENDS) {
    const p = pins[end]
    if (!p) continue
    const chain = END_CHAIN[end], c = CHAINS[chain]
    if (chain === moved) { held[end] = r4(endAt(fig, end)); continue }
    reach(fig, chain, new THREE.Vector3(p[0], p[1], p[2]))
    out[c.upper] = turns(fig, c.upper); out[c.lower] = turns(fig, c.lower); held[end] = [...p]
  }
  return { joints: out, pins: held }
}

/** The pose seen in a mirror: the pins swap sides, x changes sign (ik.mirrorJoints does the joints). */
export function mirrorPins(pins: Pins | null | undefined): Pins {
  const out: Pins = {}
  for (const end of ENDS) { const p = pins?.[end]; if (p) out[(end[0] === 'r' ? 'l' : 'r') + end.slice(1) as End] = [-p[0] || 0, p[1], p[2]] }
  return out
}

// ---- AP1b, the rest: the gaze and the arms clear of the torso --------------------------------------------------------------------------
const rad = THREE.MathUtils.degToRad
const clamp = THREE.MathUtils.clamp
/** How far a neck turns: the head's yaw to either side, its pitch up and down (degrees, in the spine's frame). */
export const GAZE_LIMITS = { yaw: 80, up: 35, down: 45 }
/** The head turned to look at `target` (the figure's own space), a third of the turn on the neck, within GAZE_LIMITS — the nose's way
 *  (+Z of the head) toward the point from the head's pivot. The turns written on the figure and returned (degrees YXZ); the pose's own
 *  neck and head give way. */
export function aimHead(fig: Mannequin, target: THREE.Vector3): { neck: number[]; head: number[] } {
  fig.root.updateWorldMatrix(true, true)
  const neck = fig.joints.neck, head = fig.joints.head
  const rest = () => ({ neck: turns(fig, 'neck'), head: turns(fig, 'head') })
  neck.rotation.set(0, 0, 0, 'YXZ'); head.rotation.set(0, 0, 0, 'YXZ')
  fig.root.updateMatrixWorld(true)
  const d = toWorld(fig, target.clone()).sub(head.getWorldPosition(new THREE.Vector3()))
  if (d.length() < 0.05) return rest()
  d.normalize().applyQuaternion(fig.joints.spine.getWorldQuaternion(new THREE.Quaternion()).invert())   // the spine's frame: +Z forward, +Y up, +X the figure's left
  const yaw = clamp(THREE.MathUtils.radToDeg(Math.atan2(d.x, d.z)), -GAZE_LIMITS.yaw, GAZE_LIMITS.yaw)
  const pitch = clamp(THREE.MathUtils.radToDeg(Math.atan2(-d.y, Math.hypot(d.x, d.z))), -GAZE_LIMITS.up, GAZE_LIMITS.down)
  const n = 1 / 3
  const whole = new THREE.Quaternion().setFromEuler(new THREE.Euler(rad(pitch), rad(yaw), 0, 'YXZ'))         // the look, in the spine's frame
  neck.quaternion.setFromEuler(new THREE.Euler(rad(pitch * n), rad(yaw * n), 0, 'YXZ'))
  head.quaternion.copy(neck.quaternion.clone().invert().multiply(whole))                                       // the rest, exactly: the face's +Z on the point
  fig.root.updateMatrixWorld(true)
  return { neck: turns(fig, 'neck'), head: turns(fig, 'head') }
}

const CLEAR_STEP = 3, CLEAR_MAX = 45, CLEAR_MARGIN = 0.02
/** An arm inside the torso or the hips — a preset made on the default body put on a broad one (E39's sitting hands) — swung at the
 *  shoulder, 3° at a time up to 45° in all, forward or outward, whichever takes the elbow, forearm and wrist further out of the figure's boxes
 *  (a margin of 2 cm), until they are clear. The shoulders' turns come back changed; nothing else. */
export function clearArms(preset: string, joints: Record<string, number[]>, ground: number, body: Body | null | undefined): Record<string, number[]> {
  if (!body) return joints
  const fig = posedFigure(preset, joints, ground, body)
  const w = BUILD_WIDTH[body.build] ?? 1, t = body.torso, hp = body.hips ?? 1, m = CLEAR_MARGIN
  const v = new THREE.Vector3()
  const depth = (p: THREE.Vector3): number => {                                   // how far inside the deeper box (0: clear)
    const s = fig.joints.spine.worldToLocal(p.clone()), r = fig.joints.root.worldToLocal(p.clone())
    const torso = Math.min(0.19 * w * body.shoulders + m - Math.abs(s.x), 0.21 * t + m - Math.abs(s.y - 0.22 * t), 0.1 * w + m - Math.abs(s.z))
    const pelvis = Math.min(0.16 * w * hp + m - Math.abs(r.x), 0.08 + m - Math.abs(r.y), 0.09 * w + m - Math.abs(r.z))
    return Math.max(0, torso, pelvis)
  }
  const out = { ...joints }
  for (const side of ['r', 'l'] as const) {
    const sh = `${side}_shoulder` as Joint, el = `${side}_elbow` as Joint, chain = `${side}_arm` as Chain
    const points = () => {
      fig.root.updateWorldMatrix(true, true)
      const b = figureChain(fig.limbs, chain).b
      const E = fig.joints[el].getWorldPosition(new THREE.Vector3()), W = v.set(0, -b, 0).clone().applyMatrix4(fig.joints[el].matrixWorld)
      return [E, W, E.clone().lerp(W, 0.5)]
    }
    const penetration = () => points().reduce((a, p) => a + depth(p), 0)
    let swung = 0
    while (penetration() > 0 && swung < CLEAR_MAX) {
      swung += CLEAR_STEP
      const e = turns(fig, sh)
      const tries: [number, number, number][] = [[e[0] - CLEAR_STEP, e[1], e[2]], [e[0], e[1], e[2] + (side === 'r' ? -CLEAR_STEP : CLEAR_STEP)]]   // forward, outward
      let best: [number, number, number] = tries[0], least = Infinity
      for (const tr of tries) { fig.joints[sh].rotation.set(rad(tr[0]), rad(tr[1]), rad(tr[2]), 'YXZ'); const d = penetration(); if (d < least) { least = d; best = tr } }
      fig.joints[sh].rotation.set(rad(best[0]), rad(best[1]), rad(best[2]), 'YXZ')
    }
    if (swung) out[sh] = turns(fig, sh)
  }
  return out
}
