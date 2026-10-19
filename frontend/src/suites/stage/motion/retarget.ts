// CA1 (D94, proto01_animate 01 step 5): a library clip retargeted onto the Stage figure — pure three.js maths, no DOM, no store.
//
// The figure has 12 joints (builders.JOINTS); a source rig (Quaternius' Rigify DEF- or Unreal names, Mixamo's mixamorig) has 50–65 bones.
// Each figure joint follows one source bone: its rotation away from the source's rest pose ("delta") is applied to the figure joint's own
// rest, after the rest directions are aligned (a T-pose arm along X and the figure's hanging arm along −Y are the same limb). The spine
// follows the chest; the clavicles, wrists, ankles, toes and fingers fold into their neighbours (01 step 5: the pose pass needs none of
// them). The hips' travel is the **root motion**, scaled by the hip heights, so a 1.2 m child takes shorter steps than the source.
// The source's facing is read from its rest pose (the right shoulder against the left) and turned to the figure's (+Z), so a rig that
// faces another way still walks forward.
import * as THREE from 'three'
import type { Joint } from '../builders'
import { eulerDeg } from '../ik'

export type RigName = 'rigify' | 'unreal' | 'mixamo'
type Part = 'hips' | 'spineBase' | 'chest' | 'neck' | 'head' | 'r_upper' | 'r_lower' | 'r_hand' | 'l_upper' | 'l_lower' | 'l_hand'
  | 'r_thigh' | 'r_calf' | 'r_foot' | 'l_thigh' | 'l_calf' | 'l_foot'

/** Bone names per rig, as written in the files (matched after three.js's sanitising: no '.', ':', spaces; case-blind). */
export const RIGS: Record<RigName, Record<Part, string>> = {
  rigify: { hips: 'DEF-hips', spineBase: 'DEF-spine.001', chest: 'DEF-spine.003', neck: 'DEF-neck', head: 'DEF-head',
    r_upper: 'DEF-upper_arm.R', r_lower: 'DEF-forearm.R', r_hand: 'DEF-hand.R', l_upper: 'DEF-upper_arm.L', l_lower: 'DEF-forearm.L', l_hand: 'DEF-hand.L',
    r_thigh: 'DEF-thigh.R', r_calf: 'DEF-shin.R', r_foot: 'DEF-foot.R', l_thigh: 'DEF-thigh.L', l_calf: 'DEF-shin.L', l_foot: 'DEF-foot.L' },
  unreal: { hips: 'pelvis', spineBase: 'spine_01', chest: 'spine_03', neck: 'neck_01', head: 'Head',
    r_upper: 'upperarm_r', r_lower: 'lowerarm_r', r_hand: 'hand_r', l_upper: 'upperarm_l', l_lower: 'lowerarm_l', l_hand: 'hand_l',
    r_thigh: 'thigh_r', r_calf: 'calf_r', r_foot: 'foot_r', l_thigh: 'thigh_l', l_calf: 'calf_l', l_foot: 'foot_l' },
  mixamo: { hips: 'mixamorig:Hips', spineBase: 'mixamorig:Spine', chest: 'mixamorig:Spine2', neck: 'mixamorig:Neck', head: 'mixamorig:Head',
    r_upper: 'mixamorig:RightArm', r_lower: 'mixamorig:RightForeArm', r_hand: 'mixamorig:RightHand', l_upper: 'mixamorig:LeftArm', l_lower: 'mixamorig:LeftForeArm', l_hand: 'mixamorig:LeftHand',
    r_thigh: 'mixamorig:RightUpLeg', r_calf: 'mixamorig:RightLeg', r_foot: 'mixamorig:RightFoot', l_thigh: 'mixamorig:LeftUpLeg', l_calf: 'mixamorig:LeftLeg', l_foot: 'mixamorig:LeftFoot' },
}

/** A bone name as three.js keeps it (PropertyBinding.sanitizeNodeName drops '.', ':', '/', brackets and turns spaces into '_'), case-blind. */
export const norm = (s: string) => s.replace(/[\s.:/[\]_-]/g, '').toLowerCase()

/** The figure joint, the source bone it follows, the bone its direction points to, and the figure joint's rest direction. */
const LINKS: { joint: Joint; bone: Part; to: Part; from?: Part; rest: [number, number, number]; parent: Joint | null }[] = [
  { joint: 'spine', bone: 'chest', to: 'neck', from: 'spineBase', rest: [0, 1, 0], parent: 'root' },     // the chest's twist, the whole spine's direction
  { joint: 'neck', bone: 'neck', to: 'head', rest: [0, 1, 0], parent: 'spine' },
  { joint: 'head', bone: 'head', to: 'head', rest: [0, 1, 0], parent: 'neck' },
  { joint: 'r_shoulder', bone: 'r_upper', to: 'r_lower', rest: [0, -1, 0], parent: 'spine' },
  { joint: 'r_elbow', bone: 'r_lower', to: 'r_hand', rest: [0, -1, 0], parent: 'r_shoulder' },
  { joint: 'l_shoulder', bone: 'l_upper', to: 'l_lower', rest: [0, -1, 0], parent: 'spine' },
  { joint: 'l_elbow', bone: 'l_lower', to: 'l_hand', rest: [0, -1, 0], parent: 'l_shoulder' },
  { joint: 'r_hip', bone: 'r_thigh', to: 'r_calf', rest: [0, -1, 0], parent: 'root' },
  { joint: 'r_knee', bone: 'r_calf', to: 'r_foot', rest: [0, -1, 0], parent: 'r_hip' },
  { joint: 'l_hip', bone: 'l_thigh', to: 'l_calf', rest: [0, -1, 0], parent: 'root' },
  { joint: 'l_knee', bone: 'l_calf', to: 'l_foot', rest: [0, -1, 0], parent: 'l_hip' },
]

export interface MotionFrame { joints: Record<Joint, number[]>; offset: [number, number, number] }
export interface Retargeted { rig: RigName; fps: number; duration: number; frames: MotionFrame[]; travel: number }
export interface RetargetOptions {
  fps: number                                    // the stage's rate (24)
  start?: number; end?: number                   // trim, seconds of the source clip
  speed?: number                                 // 1 = as made; 0.5 = half speed (twice the frames)
  hip?: number                                   // the figure's hip above its ankles, metres (0.91 for the default dummy)
  inPlace?: boolean                              // drop the horizontal travel (a path gives it instead, CA1 step 3)
}

/** Which rig a set of bone names is (the one whose every mapped bone is present), or null. */
export function detectRig(names: Iterable<string>): RigName | null {
  const have = new Set([...names].map(norm))
  for (const rig of Object.keys(RIGS) as RigName[]) if (Object.values(RIGS[rig]).every((n) => have.has(norm(n)))) return rig
  return null
}

function bonesOf(root: THREE.Object3D, rig: RigName): Record<Part, THREE.Object3D> {
  const byName = new Map<string, THREE.Object3D>()
  root.traverse((o) => { const k = norm(o.name); if (!byName.has(k)) byName.set(k, o) })
  return Object.fromEntries((Object.entries(RIGS[rig]) as [Part, string][]).map(([p, n]) => [p, byName.get(norm(n))!])) as Record<Part, THREE.Object3D>
}

/** World pose of the mapped bones in the source root's space, turned to the figure's facing by `turn`. */
function snapshot(root: THREE.Object3D, bones: Record<Part, THREE.Object3D>, turn: THREE.Quaternion) {
  root.updateMatrixWorld(true)
  const inv = new THREE.Matrix4().copy(root.matrixWorld).invert()
  const m = new THREE.Matrix4(), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3()
  const pos = {} as Record<Part, THREE.Vector3>, rot = {} as Record<Part, THREE.Quaternion>
  for (const [part, b] of Object.entries(bones) as [Part, THREE.Object3D][]) {
    m.multiplyMatrices(inv, b.matrixWorld).decompose(p, q, s)
    pos[part] = p.clone().applyQuaternion(turn)
    rot[part] = turn.clone().multiply(q)
  }
  return { pos, rot }
}

/** The clip, sampled at the stage's rate and retargeted onto the figure's 12 joints, with its root motion. */
export function retarget(root: THREE.Object3D, clip: THREE.AnimationClip, opts: RetargetOptions): Retargeted {
  const names: string[] = []
  root.traverse((o) => names.push(o.name))
  const rig = detectRig(names)
  if (!rig) throw new Error('the clip\'s skeleton is not one the library knows (Quaternius Rigify / Unreal names, or Mixamo)')
  const bones = bonesOf(root, rig)
  // rest pose: the file's own node transforms, before the clip plays
  const mixer = new THREE.AnimationMixer(root)
  const identity = new THREE.Quaternion()
  const rest0 = snapshot(root, bones, identity)
  // facing: the figure looks along +Z with its right hand at −X; the source's right minus left shoulder gives its right
  const right = rest0.pos.r_upper.clone().sub(rest0.pos.l_upper).setY(0).normalize()
  const turn = new THREE.Quaternion().setFromUnitVectors(right.lengthSq() > 0.5 ? right : new THREE.Vector3(-1, 0, 0), new THREE.Vector3(-1, 0, 0))
  const rest = snapshot(root, bones, turn)
  const restInv = Object.fromEntries(Object.entries(rest.rot).map(([k, q]) => [k, q.clone().invert()])) as Record<Part, THREE.Quaternion>
  // rest alignment: the figure joint's rest direction onto the source bone's rest direction
  const align = new Map<Joint, THREE.Quaternion>()
  for (const l of LINKS) {
    const from = new THREE.Vector3(...l.rest)
    const dir = l.to === l.bone ? new THREE.Vector3(0, 1, 0).applyQuaternion(rest.rot[l.bone]) : rest.pos[l.to].clone().sub(rest.pos[l.from ?? l.bone])
    align.set(l.joint, dir.lengthSq() > 1e-10 ? new THREE.Quaternion().setFromUnitVectors(from, dir.normalize()) : new THREE.Quaternion())
  }
  if (align.has('head')) align.set('head', align.get('neck')!.clone())          // the head's own axis varies by rig: it follows the neck's alignment
  // scale: hip above the ankles, source against the figure
  const srcHip = rest.pos.hips.y - Math.min(rest.pos.r_foot.y, rest.pos.l_foot.y)
  const s = srcHip > 1e-6 ? (opts.hip ?? 0.91) / srcHip : 1
  const action = mixer.clipAction(clip)
  action.setLoop(THREE.LoopOnce, 1)                                          // a looping action wraps to its first frame at the clip's end
  action.clampWhenFinished = true
  action.play()
  const speed = Math.max(0.05, opts.speed ?? 1)
  const t0 = Math.max(0, Math.min(clip.duration, opts.start ?? 0)), t1 = Math.max(t0, Math.min(clip.duration, opts.end ?? clip.duration))
  const n = Math.max(1, Math.round(((t1 - t0) / speed) * opts.fps) + 1)
  const frames: MotionFrame[] = []
  let start: THREE.Vector3 | null = null
  for (let i = 0; i < n; i++) {
    const t = Math.min(t1, t0 + (i / opts.fps) * speed)
    mixer.setTime(t)
    const now = snapshot(root, bones, turn)
    const world = new Map<Joint, THREE.Quaternion>()
    world.set('root', now.rot.hips.clone().multiply(restInv.hips))             // the hips' turn from rest is the root joint's
    for (const l of LINKS) {
      const q = now.rot[l.bone].clone().multiply(restInv[l.bone]).multiply(align.get(l.joint)!)
      if (l.to !== l.bone) {                                                   // swing onto where the source segment really points (several bones fold
        const want = now.pos[l.to].clone().sub(now.pos[l.from ?? l.bone])      // into one, a child offset may move); the twist stays the bone's
        const have = new THREE.Vector3(...l.rest).applyQuaternion(q)
        if (want.lengthSq() > 1e-10) q.premultiply(new THREE.Quaternion().setFromUnitVectors(have.normalize(), want.normalize()))
      }
      world.set(l.joint, q)
    }
    const joints = {} as Record<Joint, number[]>
    joints.root = eulerDeg(world.get('root')!)
    for (const l of LINKS) {
      const local = world.get(l.parent!)!.clone().invert().multiply(world.get(l.joint)!)
      joints[l.joint] = eulerDeg(local)
    }
    start ??= now.pos.hips.clone()
    const d = now.pos.hips.clone().sub(start)
    const up = now.pos.hips.y - rest.pos.hips.y
    frames.push({ joints, offset: [opts.inPlace ? 0 : d.x * s, up * s, opts.inPlace ? 0 : d.z * s] })
  }
  mixer.stopAllAction(); mixer.uncacheRoot(root)
  root.updateMatrixWorld(true)
  const last = frames[frames.length - 1].offset
  return { rig, fps: opts.fps, duration: (n - 1) / opts.fps, frames, travel: Math.hypot(last[0], last[2]) }
}
