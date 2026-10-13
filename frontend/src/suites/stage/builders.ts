// P13 / ST1 (D81): the things a stage is made of, as three.js objects — the procedural mannequin of E10 (a joint tree with COCO-18
// markers; no licence question, proven to carry a blocking), the three E10 sets, primitive props, and image planes from Catalogue
// assets. Pure builders: no DOM, no store. Lifted from frontend/src/spikes/e10Stage.ts; the pose presets are the ones E10 scored.
import * as THREE from 'three'

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

/** Set a mannequin's joint rotations (degrees; joints a pose leaves out go back to rest). */
export function applyPose(J: Record<Joint, THREE.Object3D>, pose: Pose, joints?: Record<string, number[]>): void {
  for (const n of JOINTS) {
    const e = (joints?.[n] as Euler3 | undefined) ?? pose.j[n] ?? [0, 0, 0]
    J[n].rotation.set(rad(e[0]), rad(e[1]), rad(e[2]), 'YXZ')
  }
  J.root.position.y = pose.rootY ?? 0.95
}

export interface Mannequin { root: THREE.Object3D; joints: Record<Joint, THREE.Object3D>; markers: THREE.Object3D[] }

/** One posed mannequin (1.75 m) and its COCO-18 marker objects (nose, neck, shoulders, elbows, wrists, hips, knees, ankles, eyes, ears). */
export function mannequin(mat: THREE.Material, pose: Pose = POSES.stand, joints?: Record<string, number[]>): Mannequin {
  const J = Object.fromEntries(JOINTS.map((n) => [n, new THREE.Object3D()])) as Record<Joint, THREE.Object3D>
  const root = J.root
  const marker = (parent: THREE.Object3D, x: number, y: number, z: number) => { const o = new THREE.Object3D(); o.position.set(x, y, z); parent.add(o); return o }
  const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.16, 0.18), mat); root.add(pelvis)
  root.add(J.spine); J.spine.position.set(0, 0.06, 0)
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.42, 0.2), mat); torso.position.y = 0.22; J.spine.add(torso)
  J.spine.add(J.neck); J.neck.position.set(0, 0.44, 0)
  J.neck.add(J.head); J.head.position.set(0, 0.06, 0)
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 20, 14), mat); head.position.y = 0.1; head.scale.set(0.9, 1.1, 1); J.head.add(head)
  const neckMarker = marker(J.neck, 0, 0, 0)
  const nose = marker(J.head, 0, 0.08, 0.11), rEye = marker(J.head, -0.035, 0.12, 0.09), lEye = marker(J.head, 0.035, 0.12, 0.09)
  const rEar = marker(J.head, -0.095, 0.1, 0), lEar = marker(J.head, 0.095, 0.1, 0)
  const arm = (shoulder: Joint, elbow: Joint, side: number) => {
    J.spine.add(J[shoulder]); J[shoulder].position.set(side * 0.21, 0.4, 0)
    limb(J[shoulder], 0.29, 0.055, mat)
    J[shoulder].add(J[elbow]); J[elbow].position.set(0, -0.29, 0)
    limb(J[elbow], 0.27, 0.045, mat)
    return [marker(J[shoulder], 0, 0, 0), marker(J[elbow], 0, 0, 0), marker(J[elbow], 0, -0.27, 0)]
  }
  const [rS, rE, rW] = arm('r_shoulder', 'r_elbow', -1), [lS, lE, lW] = arm('l_shoulder', 'l_elbow', 1)
  const leg = (hip: Joint, knee: Joint, side: number) => {
    root.add(J[hip]); J[hip].position.set(side * 0.1, -0.04, 0)
    limb(J[hip], 0.44, 0.07, mat)
    J[hip].add(J[knee]); J[knee].position.set(0, -0.44, 0)
    limb(J[knee], 0.43, 0.055, mat)
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.06, 0.24), mat); foot.position.set(0, -0.44, 0.06); J[knee].add(foot)
    return [marker(J[hip], 0, 0, 0), marker(J[knee], 0, 0, 0), marker(J[knee], 0, -0.43, 0)]
  }
  const [rH, rK, rA] = leg('r_hip', 'r_knee', -1), [lH, lK, lA] = leg('l_hip', 'l_knee', 1)
  applyPose(J, pose, joints)
  return { root, joints: J, markers: [nose, neckMarker, rS, rE, rW, lS, lE, lW, rH, rK, rA, lH, lK, lA, rEye, lEye, rEar, lEar] }
}

export const SET_PRESETS = ['room', 'street', 'deck', 'empty'] as const
/** The E10 sets: a floor and a few blocks that read as a room, a street or a deck; `empty` is a floor alone. */
export function set(kind: string, mat: THREE.Material): THREE.Group {
  const g = new THREE.Group()
  const box = (w: number, h: number, d: number, x: number, y: number, z: number) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); g.add(m) }
  if (kind === 'street') { box(9, 0.02, 30, 0, -0.01, -5); box(0.3, 5, 30, -3.6, 2.5, -5); box(0.3, 5, 30, 3.6, 2.5, -5); box(1.0, 2.2, 0.4, -3.2, 1.1, -2) }
  else if (kind === 'room') { box(9, 0.02, 9, 0, -0.01, 0); box(9, 3.2, 0.2, 0, 1.6, -3.2); box(0.2, 3.2, 9, -4, 1.6, 0); box(1.2, 0.8, 0.8, 1.9, 0.4, -1.8); box(0.45, 0.48, 0.45, 0, 0.24, 0) }
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
