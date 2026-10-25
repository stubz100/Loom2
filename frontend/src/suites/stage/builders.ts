// P13 / ST1 (D81): the things a stage is made of, as three.js objects — the procedural mannequin of E10 (a joint tree with COCO-18
// markers; no licence question, proven to carry a blocking), the three E10 sets, primitive props, and image planes from Catalogue
// assets. Pure builders: no DOM, no store. Lifted from frontend/src/spikes/e10Stage.ts; the pose presets are the ones E10 scored.
import * as THREE from 'three'
import { BUILD_WIDTH, DEFAULT_BODY, bodyDims, type Body, type Limbs } from './body'

export { bodyDims, type Body, type Limbs } from './body'

export const JOINTS = ['root', 'spine', 'neck', 'head', 'r_shoulder', 'r_elbow', 'l_shoulder', 'l_elbow', 'r_hip', 'r_knee', 'l_hip', 'l_knee'] as const
export type Joint = (typeof JOINTS)[number]
type Euler3 = [number, number, number]
export interface Pose { rootY?: number; j: Partial<Record<Joint, Euler3>> }

// presets in degrees (x pitches a limb forward when negative for arms / legs; z swings an arm outwards: − right, + left)
export const POSES: Record<string, Pose> = {
  stand: { j: { r_shoulder: [0, 0, -8], l_shoulder: [0, 0, 8] } },
  point: { j: { r_shoulder: [-88, 0, -4], l_shoulder: [0, 0, 8], head: [0, -10, 0] } },
  arms_crossed: { j: { r_shoulder: [-25, 35, -8], r_elbow: [-110, 0, 0], l_shoulder: [-25, -35, 8], l_elbow: [-110, 0, 0] } },
  walk: { j: { r_hip: [-25, 0, 0], r_knee: [15, 0, 0], l_hip: [20, 0, 0], l_knee: [25, 0, 0], r_shoulder: [22, 0, -6], l_shoulder: [-22, 0, 6], l_elbow: [-20, 0, 0] } },
  run: { j: { spine: [14, 0, 0], r_hip: [-60, 0, 0], r_knee: [75, 0, 0], l_hip: [35, 0, 0], l_knee: [60, 0, 0], r_shoulder: [45, 0, -8], r_elbow: [-85, 0, 0], l_shoulder: [-55, 0, 8], l_elbow: [-85, 0, 0] } },
  reach: { j: { r_shoulder: [-165, 0, -10], l_shoulder: [-160, 0, 12], head: [-20, 0, 0] } },
  sit: { rootY: 0.5, j: { r_hip: [-88, 0, 0], r_knee: [88, 0, 0], l_hip: [-88, 0, 0], l_knee: [88, 0, 0], r_shoulder: [-40, 0, -4], r_elbow: [-35, 0, 0], l_shoulder: [-40, 0, 4], l_elbow: [-35, 0, 0] } },
  crouch: { rootY: 0.52, j: { spine: [35, 0, 0], r_hip: [-105, 0, 0], r_knee: [130, 0, 0], l_hip: [-95, 0, 0], l_knee: [125, 0, 0], r_shoulder: [-70, 0, -6], r_elbow: [-35, 0, 0], l_shoulder: [-55, 0, 6], l_elbow: [-40, 0, 0], head: [20, 0, 0] } },
  wave: { j: { r_shoulder: [0, 0, -150], r_elbow: [0, 0, 35], l_shoulder: [0, 0, 8], head: [0, -15, 0] } },
  look_left: { j: { neck: [0, 20, 0], head: [0, 45, 0], r_shoulder: [0, 0, -6], l_shoulder: [0, 0, 6] } },
}
export const POSE_NAMES = Object.keys(POSES)

const rad = THREE.MathUtils.degToRad
function limb(parent: THREE.Object3D, length: number, radius: number, mat: THREE.Material): void {
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(radius, Math.max(0.01, length - 2 * radius), 6, 12), mat)
  m.position.y = -length / 2
  parent.add(m)
}

/** Set a mannequin's joint rotations (degrees; joints a pose leaves out go back to rest). The root's height follows the figure's legs
 *  (CA0: `userData.hip`, the standing hip height; 0.95 for the default dummy). */
export function applyPose(J: Record<Joint, THREE.Object3D>, pose: Pose, joints?: Record<string, number[]>): void {
  for (const n of JOINTS) {
    const e = (joints?.[n] as Euler3 | undefined) ?? pose.j[n] ?? [0, 0, 0]
    J[n].rotation.set(rad(e[0]), rad(e[1]), rad(e[2]), 'YXZ')
  }
  const hip = (J.root.userData.hip as number | undefined) ?? 0.95
  J.root.position.y = (pose.rootY ?? 0.95) * (hip / 0.95)
}

export interface Mannequin { root: THREE.Object3D; joints: Record<Joint, THREE.Object3D>; markers: THREE.Object3D[]; limbs: Limbs }

/** One posed mannequin and its COCO-18 marker objects (nose, neck, shoulders, elbows, wrists, hips, knees, ankles, eyes, ears). Without a
 *  body it is E10's 1.75 m dummy, unchanged; with one (CA0) its lengths, widths and height follow the Cast sheet, and its attachments
 *  ride on their joints (in the clay, depth and mask passes; never in the pose pass — they carry no marker). */
export function mannequin(mat: THREE.Material, pose: Pose = POSES.stand, joints?: Record<string, number[]>, b?: Body | null): Mannequin {
  const J = Object.fromEntries(JOINTS.map((n) => [n, new THREE.Object3D()])) as Record<Joint, THREE.Object3D>
  const x = b ?? DEFAULT_BODY
  const { limbs, hip, scale } = bodyDims(b)
  const w = BUILD_WIDTH[x.build] ?? 1, t = x.torso, hd = x.head
  const root = J.root
  root.userData.hip = hip
  const marker = (parent: THREE.Object3D, mx: number, my: number, mz: number) => { const o = new THREE.Object3D(); o.position.set(mx, my, mz); parent.add(o); return o }
  const hp = x.hips ?? 1                                              // S7: the hips' width
  const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.32 * w * hp, 0.16, 0.18 * w), mat); root.add(pelvis)
  root.add(J.spine); J.spine.position.set(0, 0.06, 0)
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.38 * w * x.shoulders, 0.42 * t, 0.2 * w), mat); torso.position.y = 0.22 * t; J.spine.add(torso)
  // S3 (proto01_UIcast CS1): ×1 an adult's neck — 0.12 from the neck joint to the head's pivot at the jaw, the head's points 0.06·head lower on
  // it than before (the nose 0.02 over the pivot), so a body of before (neck′ = (neck + head) / 2, body.py rebase_body) stands where it stood
  const nk = 0.12 * (x.neck ?? 1), lean = THREE.MathUtils.degToRad(x.head_forward ?? 0)   // CS2: the head carried forward of the neck
  const shY = 0.44 * t - 0.04 * t * (x.shoulder_drop ?? 1)                 // CS2: the shoulders under the neck joint (×1: 0.4 · torso)
  J.spine.add(J.neck); J.neck.position.set(0, 0.44 * t, 0)
  J.neck.add(J.head); J.head.position.set(0, nk * Math.cos(lean), nk * Math.sin(lean))
  limb(J.head, nk + 0.04 * t, 0.045 * w, mat)                        // CB6: the neck, from the shoulders' line to the pivot (the Simple level drew none)
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11 * hd, 20, 14), mat); head.position.y = 0.04 * hd; head.scale.set(0.9, 1.1, 1); J.head.add(head)
  const neckMarker = marker(J.spine, 0, shY, 0)                       // CA1b (D104): OpenPose's neck is the shoulders' midpoint, as SDPose and DWPose read people
  const nose = marker(J.head, 0, 0.02 * hd, 0.11 * hd), rEye = marker(J.head, -0.035 * hd, 0.06 * hd, 0.09 * hd), lEye = marker(J.head, 0.035 * hd, 0.06 * hd, 0.09 * hd)
  const rEar = marker(J.head, -0.095 * hd, 0.04 * hd, 0), lEar = marker(J.head, 0.095 * hd, 0.04 * hd, 0)
  const sx = 0.21 * x.shoulders * (b ? 0.5 + 0.5 * w : 1)
  const arm = (shoulder: Joint, elbow: Joint, side: number) => {
    J.spine.add(J[shoulder]); J[shoulder].position.set(side * sx, shY, 0)
    limb(J[shoulder], limbs.upper_arm, 0.055 * w, mat)
    J[shoulder].add(J[elbow]); J[elbow].position.set(0, -limbs.upper_arm, 0)
    limb(J[elbow], limbs.forearm, 0.045 * w, mat)
    return [marker(J[shoulder], 0, 0, 0), marker(J[elbow], 0, 0, 0), marker(J[elbow], 0, -limbs.forearm, 0)]
  }
  const [rS, rE, rW] = arm('r_shoulder', 'r_elbow', -1), [lS, lE, lW] = arm('l_shoulder', 'l_elbow', 1)
  const leg = (hipJ: Joint, knee: Joint, side: number) => {
    root.add(J[hipJ]); J[hipJ].position.set(side * 0.1 * w * hp, -0.04, 0)
    limb(J[hipJ], limbs.thigh, 0.07 * w, mat)
    J[hipJ].add(J[knee]); J[knee].position.set(0, -limbs.thigh, 0)
    limb(J[knee], limbs.shin, 0.055 * w, mat)
    const fs = x.feet ?? 1
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.1 * w * fs, 0.06, 0.24 * fs), mat); foot.position.set(0, -limbs.shin - 0.01, 0.06 * fs); J[knee].add(foot)
    return [marker(J[hipJ], 0, 0, 0), marker(J[knee], 0, 0, 0), marker(J[knee], 0, -limbs.shin, 0)]
  }
  const [rH, rK, rA] = leg('r_hip', 'r_knee', -1), [lH, lK, lA] = leg('l_hip', 'l_knee', 1)
  if (b) for (const a of b.attachments) attach(J, a, mat, x)
  applyPose(J, pose, joints)
  let top: THREE.Object3D = root
  if (scale !== 1) { top = new THREE.Group(); top.add(root); top.scale.setScalar(scale) }     // the height: one uniform scale over the whole figure
  return { root: top, joints: J, markers: [nose, neckMarker, rS, rE, rW, lS, lE, lW, rH, rK, rA, lH, lK, lA, rEye, lEye, rEar, lEar], limbs }
}

/** CA0 (01 §9b N1): a rigid attachment on its joint (the kind's own place unless the sheet names one), in clay like the figure. */
function attach(J: Record<Joint, THREE.Object3D>, a: Body['attachments'][number], mat: THREE.Material, x: Body): void {
  const s = a.size, hd = x.head, t = x.torso
  const at = (j: string | null, fallback: Joint) => J[(j && (JOINTS as readonly string[]).includes(j) ? j : fallback) as Joint]
  const mesh = (geo: THREE.BufferGeometry, parent: THREE.Object3D, px: number, py: number, pz: number, rx = 0, rz = 0) => {
    const m = new THREE.Mesh(geo, mat); m.position.set(px, py, pz); m.rotation.set(rx, 0, rz); parent.add(m)
  }
  if (a.kind === 'horns') for (const side of [-1, 1]) mesh(new THREE.ConeGeometry(0.025 * s, 0.1 * s, 10), at(a.joint, 'head'), side * 0.06 * hd, 0.14 * hd + 0.04 * s, 0.02, 0, -side * 0.35)
  else if (a.kind === 'ears') for (const side of [-1, 1]) mesh(new THREE.SphereGeometry(0.035 * s, 10, 8), at(a.joint, 'head'), side * 0.11 * hd, 0.09 * hd, 0)
  else if (a.kind === 'antennae') for (const side of [-1, 1]) mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.16 * s, 6), at(a.joint, 'head'), side * 0.04 * hd, 0.16 * hd + 0.08 * s, 0, 0, -side * 0.3)
  else if (a.kind === 'hat') mesh(new THREE.CylinderGeometry(0.11 * hd, 0.13 * hd, 0.12 * s, 20), at(a.joint, 'head'), 0, 0.15 * hd + 0.05 * s, 0)
  else if (a.kind === 'wings') for (const side of [-1, 1]) mesh(new THREE.BoxGeometry(0.4 * s, 0.5 * s, 0.02), at(a.joint, 'spine'), side * 0.22 * s, 0.32 * t, -0.13, 0, side * 0.35)
  else if (a.kind === 'backpack') mesh(new THREE.BoxGeometry(0.3 * s, 0.36 * s, 0.14 * s), at(a.joint, 'spine'), 0, 0.24 * t, -0.17)
  else if (a.kind === 'tail') mesh(new THREE.CylinderGeometry(0.015 * s, 0.04 * s, 0.6 * s, 10), at(a.joint, 'root'), 0, -0.05 - 0.2 * s, -0.12 - 0.2 * s, -0.9)
  else mesh(new THREE.SphereGeometry(0.06 * s, 12, 10), at(a.joint, 'spine'), 0, 0.2, 0.12)
}

export const SET_PRESETS = ['room', 'street', 'deck', 'empty'] as const
/** The E10 sets, architecture only (D108: everything standing in a set is a prop): a room's floor and two walls, a street's road and
 *  façades, a deck with its rails and mast; `empty` is a floor alone. Schema-1 stages get the old blocks as props (stages.py migrate). */
export function set(kind: string, mat: THREE.Material): THREE.Group {
  const g = new THREE.Group()
  const box = (w: number, h: number, d: number, x: number, y: number, z: number) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); g.add(m) }
  if (kind === 'street') { box(9, 0.02, 30, 0, -0.01, -5); box(0.3, 5, 30, -3.6, 2.5, -5); box(0.3, 5, 30, 3.6, 2.5, -5) }
  else if (kind === 'room') { box(9, 0.02, 9, 0, -0.01, 0); box(9, 3.2, 0.2, 0, 1.6, -3.2); box(0.2, 3.2, 9, -4, 1.6, 0) }
  else if (kind === 'deck') {
    box(12, 0.06, 6, 0, -0.03, 0); box(12, 0.08, 0.08, 0, 1.0, -2.6); box(12, 0.08, 0.08, 0, 1.0, 2.6)
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.15, 7, 16), mat); mast.position.set(2.6, 3.5, -1); g.add(mast)
  } else { box(12, 0.02, 12, 0, -0.01, 0) }
  return g
}

export const PROP_PRESETS = ['crate', 'stool', 'table', 'pole', 'block'] as const
export function prop(kind: string, mat: THREE.Material): THREE.Object3D {
  const g = new THREE.Group()
  const add = (geo: THREE.BufferGeometry, y: number) => { const m = new THREE.Mesh(geo, mat); m.position.y = y; g.add(m) }
  if (kind === 'crate') add(new THREE.BoxGeometry(0.6, 0.6, 0.6), 0.3)
  else if (kind === 'stool') add(new THREE.CylinderGeometry(0.2, 0.2, 0.48, 16), 0.24)
  else if (kind === 'table') { add(new THREE.BoxGeometry(1.4, 0.05, 0.8), 0.75); add(new THREE.BoxGeometry(1.2, 0.72, 0.6), 0.36) }
  else if (kind === 'pole') add(new THREE.CylinderGeometry(0.06, 0.06, 3, 12), 1.5)
  else add(new THREE.BoxGeometry(1, 1, 1), 0.5)
  return g
}

export const MANNEQUIN_PRESETS: Record<string, { scale: number; label: string }> = { adult: { scale: 1, label: 'Adult (1.75 m)' }, child: { scale: 0.7, label: 'Child (1.2 m)' } }

/** The clay material the blocking is shown in (and the clay pass renders with, ST3). */
export const clay = () => new THREE.MeshLambertMaterial({ color: 0x9a9a9a })
export const setMaterial = () => new THREE.MeshLambertMaterial({ color: 0x8a8a90 })

/** Vertical field of view (degrees) for a focal length on a sensor whose width is `sensorMm`, at the frame aspect `w / h`. */
export function vfovFor(focalMm: number, sensorMm: number, aspect: number): number {
  return THREE.MathUtils.radToDeg(2 * Math.atan((sensorMm / aspect) / (2 * focalMm)))
}
