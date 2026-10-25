// Spike E39 (proto01_UIcast 06 §2.9; D136 U18, D137 stage 3): the starter poses and motion clips on characters' own skeletons. The browser
// half of engine/spikes/e39_poses.py, loaded on the dev page: for one character (its body, the points its body was fitted to, its shell)
//   · binds the shell to the figure as the shots do (bone heat, in the reference's stance, placed by its picture — D138, D140);
//   · poses it in every starter pose (builders.POSES) and plays the starter clips as Animate applies them (retargeted onto the 12 joints,
//     the root scaled to the character's hip, the foot lock with its body — motionStore.apply);
//   · measures, frame by frame: the planted foot's slide (footlock.footSlide, 02 §5's 2 cm bar), how far it floats or sinks against its
//     standing height, and a hand passing through the body — a fingertip (the wrist, on along the forearm by a hand's length) inside the
//     posed shell where the shell's nearest part is the torso or a leg, not that arm;
//   · renders a few frames of the shell for the sheet.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { bodyDims, DEFAULT_BODY } from '../suites/stage/body'
import { applyPose, JOINTS, mannequin, POSES, type Body, type Joint, type Mannequin } from '../suites/stage/builders'
import { footLock, footSlide, stance } from '../suites/stage/motion/footlock'
import { footContact } from '../suites/stage/motion/contact'
import { clipsOf, listFiles, retargetClip, type MotionClip } from '../suites/stage/motion/library'
import type { MotionFrame } from '../suites/stage/motion/retarget'
import { bindProxy, stanceOf } from '../suites/stage/proxy'
import { solveTwoBone } from '../suites/stage/ik'

export interface E39Input { name: string; body: Body; points: { pose?: number[][]; canvas?: number[] } | null; meshUrl: string | null; clips: string[] }
type Img = string
const ARM: Record<'r' | 'l', Joint[]> = { r: ['r_shoulder', 'r_elbow'], l: ['l_shoulder', 'l_elbow'] }
const HAND_M = 0.18                                                         // wrist → fingertip at 1.75 m

async function png(r: THREE.WebGLRenderer): Promise<Img> {
  const blob: Blob = await new Promise((res) => r.domElement.toBlob((b) => res(b!), 'image/png'))
  const u = new Uint8Array(await blob.arrayBuffer()); let s = ''
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000))
  return btoa(s)
}

/** The shell as posed now: its skinned vertices carried through the bones, as plain meshes to cast rays at, and each vertex's strongest joint. */
function posed(meshes: THREE.SkinnedMesh[]): { plain: THREE.Mesh[]; pos: Float32Array[]; joint: Uint8Array[] } {
  const v = new THREE.Vector3(), plain: THREE.Mesh[] = [], pos: Float32Array[] = [], joint: Uint8Array[] = []
  for (const m of meshes) {
    m.skeleton.update()
    const a = m.geometry.attributes.position, n = a.count, out = new Float32Array(n * 3), dom = new Uint8Array(n)
    const si = m.geometry.attributes.skinIndex, sw = m.geometry.attributes.skinWeight
    for (let i = 0; i < n; i++) {
      v.fromBufferAttribute(a, i); m.applyBoneTransform(i, v); out[i * 3] = v.x; out[i * 3 + 1] = v.y; out[i * 3 + 2] = v.z
      let best = 0
      for (let k = 1; k < 4; k++) if (sw.getComponent(i, k) > sw.getComponent(i, best)) best = k
      dom[i] = si.getComponent(i, best)
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(out, 3)); g.computeBoundingSphere()
    plain.push(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }))); pos.push(out); joint.push(dom)
  }
  return { plain, pos, joint }
}

/** Whether a point is inside the posed shell (an odd count of crossings along +X) and which joint owns the nearest shell vertex. */
function where(p: THREE.Vector3, s: ReturnType<typeof posed>): { inside: boolean; joint: Joint } {
  const hits = new THREE.Raycaster(p.clone(), new THREE.Vector3(1, 0, 0), 0, 50).intersectObjects(s.plain, false)
  let best = Infinity, j = 0
  for (let m = 0; m < s.pos.length; m++) {
    const a = s.pos[m]
    for (let i = 0; i < a.length; i += 3) {
      const d = (a[i] - p.x) ** 2 + (a[i + 1] - p.y) ** 2 + (a[i + 2] - p.z) ** 2
      if (d < best) { best = d; j = s.joint[m][i / 3] }
    }
  }
  return { inside: hits.length % 2 === 1, joint: JOINTS[j] }
}

/** The fingertips in the body: each hand's tip (the wrist, on along its forearm by a hand's length) inside the posed shell where its nearest
 *  part is not that arm's. */
function tipsInBody(fig: Mannequin, s: ReturnType<typeof posed>, height: number): ('r' | 'l')[] {
  const out: ('r' | 'l')[] = []
  for (const [side, wrist, elbow] of [['r', 4, 'r_elbow'], ['l', 7, 'l_elbow']] as const) {
    const w = fig.markers[wrist].getWorldPosition(new THREE.Vector3()), e = fig.joints[elbow].getWorldPosition(new THREE.Vector3())
    const tip = w.clone().add(w.clone().sub(e).normalize().multiplyScalar(HAND_M * height / 1.75))
    const at = where(tip, s)
    if (at.inside && !ARM[side].includes(at.joint)) out.push(side)
  }
  return out
}

const ankleY = (fig: Mannequin, side: 'r' | 'l') => new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints[side === 'r' ? 'r_knee' : 'l_knee'].matrixWorld).y

/** The vertical contact AP1 would add (the foot lock is horizontal): through each stance the root raised or lowered so the planted foot's
 *  lowest point meets the floor, eased over 4 frames into the next stance's; then each stance's contact again and the lowest either foot
 *  goes under the floor (a foot through it). */
/** A leg bent by two-bone IK (ik.ts, as Stage's IK handle bends it) so its ankle is at `y` (the floor's height for it), the knee bending the
 *  way it already does. */
function legTo(fig: Mannequin, holder: THREE.Group, side: 'r' | 'l', y: number): void {
  const upper = fig.joints[side === 'r' ? 'r_hip' : 'l_hip'], lower = fig.joints[side === 'r' ? 'r_knee' : 'l_knee'], parent = upper.parent!
  const ankle = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(lower.matrixWorld).setY(y)
  const target = parent.worldToLocal(ankle.clone()), knee = parent.worldToLocal(lower.getWorldPosition(new THREE.Vector3()))
  const bend = knee.clone().sub(upper.position.clone().add(target).multiplyScalar(0.5))
  const s = solveTwoBone(upper.position, target, fig.limbs.thigh, fig.limbs.shin, bend.lengthSq() > 1e-8 ? bend : new THREE.Vector3(0, 0, 1))
  upper.rotation.set(THREE.MathUtils.degToRad(s.upper[0]), THREE.MathUtils.degToRad(s.upper[1]), THREE.MathUtils.degToRad(s.upper[2]), 'YXZ')
  lower.rotation.set(THREE.MathUtils.degToRad(s.lower[0]), THREE.MathUtils.degToRad(s.lower[1]), THREE.MathUtils.degToRad(s.lower[2]), 'YXZ')
  holder.updateMatrixWorld(true)
}

function contactFix(fig: Mannequin, holder: THREE.Group, frames: MotionFrame[], down: ('r' | 'l' | null)[], rest: { r: number; l: number }): { stance_cm: number; under_cm: number; under_ik_cm: number } {
  const pose = (f: MotionFrame, dy: number) => { applyPose(fig.joints, POSES.stand, f.joints); fig.root.position.set(f.offset[0], f.offset[1] + dy, f.offset[2]); holder.updateMatrixWorld(true) }
  const shift = new Array<number>(frames.length).fill(0)
  for (let i = 0; i < frames.length;) {                                      // each stance: its lowest point
    const foot = down[i]
    let j = i
    while (j < frames.length && down[j] === foot) j++
    if (foot) { let low = Infinity; for (let k = i; k < j; k++) { pose(frames[k], 0); low = Math.min(low, ankleY(fig, foot) - rest[foot]) } for (let k = i; k < j; k++) shift[k] = -low }
    else for (let k = i; k < j; k++) shift[k] = NaN
    i = j
  }
  for (let i = 0; i < shift.length; i++) if (Number.isNaN(shift[i])) shift[i] = shift[i - 1] ?? 0      // the air keeps the last stance's
  const eased = shift.map((_, i) => { let sum = 0, n = 0; for (let k = Math.max(0, i - 2); k <= Math.min(shift.length - 1, i + 2); k++) { sum += shift[k]; n++ } return sum / n })
  let worstStance = 0, under = 0, underIk = 0
  for (let i = 0; i < frames.length; i++) {
    pose(frames[i], eased[i])
    const r = ankleY(fig, 'r') - rest.r, l = ankleY(fig, 'l') - rest.l
    under = Math.min(under, r, l)
    for (const side of ['r', 'l'] as const) if (ankleY(fig, side) - rest[side] < -0.003) legTo(fig, holder, side, rest[side])   // a foot through the floor: its leg bent up onto it
    underIk = Math.min(underIk, ankleY(fig, 'r') - rest.r, ankleY(fig, 'l') - rest.l)
    pose(frames[i], eased[i])
    const foot = down[i]
    if (foot && (i === 0 || down[i - 1] !== foot)) {                         // a new stance: its lowest after the fix
      let low = Infinity
      for (let k = i; k < frames.length && down[k] === foot; k++) { pose(frames[k], eased[k]); low = Math.min(low, ankleY(fig, foot) - rest[foot]) }
      worstStance = Math.max(worstStance, Math.abs(low))
      pose(frames[i], eased[i])
    }
  }
  return { stance_cm: Math.round(worstStance * 1000) / 10, under_cm: Math.round(under * 1000) / 10, under_ik_cm: Math.round(underIk * 1000) / 10 }
}

/** AP1's module (motion/contact.ts) on the same clip: each stance's contact and the lowest either foot goes under the floor. */
function grounded(fig: Mannequin, holder: THREE.Group, frames: MotionFrame[], down: ('r' | 'l' | null)[], rest: { r: number; l: number }): { stance_cm: number; under_cm: number } {
  let worst = 0, under = 0
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i]
    applyPose(fig.joints, POSES.stand, f.joints); fig.root.position.set(f.offset[0], f.offset[1], f.offset[2]); holder.updateMatrixWorld(true)
    under = Math.min(under, ankleY(fig, 'r') - rest.r, ankleY(fig, 'l') - rest.l)
    const foot = down[i]
    if (foot && (i === 0 || down[i - 1] !== foot)) {
      let low = Infinity
      for (let k = i; k < frames.length && down[k] === foot; k++) {
        const g = frames[k]; applyPose(fig.joints, POSES.stand, g.joints); fig.root.position.set(g.offset[0], g.offset[1], g.offset[2]); holder.updateMatrixWorld(true)
        low = Math.min(low, ankleY(fig, foot) - rest[foot])
      }
      worst = Math.max(worst, Math.abs(low))
    }
  }
  return { stance_cm: Math.round(worst * 1000) / 10, under_cm: Math.round(under * 1000) / 10 }
}

export async function measurePoses(input: E39Input): Promise<Record<string, unknown>> {
  const out: Record<string, unknown> = { name: input.name }
  const body = { ...DEFAULT_BODY, ...input.body, hand_rest: { ...DEFAULT_BODY.hand_rest, ...(input.body.hand_rest ?? {}) } } as Body, H = body.height_m   // a partial body (the baseline's) filled
  const stanceJ = stanceOf(input.points as never)
  const mat = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const fig = mannequin(mat, POSES.stand, stanceJ, body)
  const holder = new THREE.Group(); holder.add(fig.root)
  const scene = new THREE.Scene(); scene.add(holder)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x555555, 1.5)); const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(2, 3, 2.5); scene.add(key)
  holder.updateMatrixWorld(true)
  fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = !input.meshUrl })    // the shell alone, when there is one
  let meshes: THREE.SkinnedMesh[] = []
  if (input.meshUrl) {
    const gltf = await new GLTFLoader().loadAsync(input.meshUrl)
    const px = bindProxy(gltf.scene, fig.joints, fig.limbs, holder, { preset: 'stand', joints: stanceJ }, { stance: stanceJ, visible: true, hands: true, points: input.points, markers: fig.markers })
    meshes = px.meshes; for (const m of meshes) scene.add(m)
  }
  applyPose(fig.joints, POSES.stand); holder.updateMatrixWorld(true)
  const rest = { r: ankleY(fig, 'r'), l: ankleY(fig, 'l') }
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); renderer.setSize(300, 420)
  scene.background = new THREE.Color(0xb8b8b8)
  const cam = new THREE.PerspectiveCamera(30, 300 / 420, 0.1, 50)
  const shot = async (yaw: number, centre: THREE.Vector3) => { const d = H * 2.6; cam.position.set(centre.x + Math.sin(yaw) * d, H * 0.55, centre.z + Math.cos(yaw) * d); cam.lookAt(centre.x, H * 0.45, centre.z); renderer.render(scene, cam); return png(renderer) }
  const views: Record<string, Img> = {}
  try {
    // the starter poses: the feet against the standing height, a hand through the body
    const poses: Record<string, unknown> = {}
    for (const name of Object.keys(POSES)) {
      applyPose(fig.joints, POSES[name]); fig.root.position.x = 0; fig.root.position.z = 0; holder.updateMatrixWorld(true)
      const lowest = Math.min(ankleY(fig, 'r') - rest.r, ankleY(fig, 'l') - rest.l)
      const tips = meshes.length ? tipsInBody(fig, posed(meshes), H) : []
      poses[name] = { foot_cm: Math.round(lowest * 1000) / 10, hands_in_body: tips }
      if (['sit', 'crouch', 'arms_crossed', 'reach'].includes(name)) views[`pose_${name}`] = await shot(0.6, new THREE.Vector3())
    }
    out.poses = poses
    // the starter clips as Animate applies them
    const files = (await listFiles()).items.filter((f) => f.source === 'starter')
    const all: MotionClip[] = []
    for (const f of files) all.push(...await clipsOf(f))
    const dims = bodyDims(body), hip = (0.04 + dims.limbs.thigh + dims.limbs.shin) * dims.scale
    const clips: Record<string, unknown> = {}
    for (const name of input.clips) {
      const clip = all.find((c) => c.name === name)
      if (!clip) { clips[name] = { missing: true }; continue }
      const r = await retargetClip(clip, { fps: 24, hip })
      const locked: MotionFrame[] = footLock(r.frames, body)
      const down = stance(locked, body)
      let frames = 0, inBody = 0
      const phases: number[] = []                                           // each stance's contact: the planted foot's lowest against its standing height
      let phase = null as { foot: 'r' | 'l'; low: number } | null
      for (let i = 0; i < locked.length; i++) {
        const f = locked[i]
        applyPose(fig.joints, POSES.stand, f.joints); fig.root.position.set(f.offset[0], f.offset[1], f.offset[2]); holder.updateMatrixWorld(true)
        const foot = down[i]
        if (!foot || foot !== phase?.foot) { if (phase) phases.push(phase.low); phase = foot ? { foot, low: Infinity } : null }
        if (foot && phase) phase.low = Math.min(phase.low, ankleY(fig, foot) - rest[foot])
        if (i % 2) continue
        if (meshes.length) { frames++; if (tipsInBody(fig, posed(meshes), H).length) inBody++ }
        if (i === Math.floor(locked.length / 2) - (Math.floor(locked.length / 2) % 2)) views[`clip_${name}`] = await shot(0.6, fig.root.getWorldPosition(new THREE.Vector3()).setY(0))
      }
      if (phase) phases.push(phase.low)
      const cm = (x: number) => Math.round(x * 1000) / 10
      clips[name] = { frames: locked.length, slide_cm: cm(footSlide(locked, body)), stances: phases.length, float_cm: cm(Math.max(0, ...phases)), sink_cm: cm(Math.min(0, ...phases)),
        hands_in_body: frames ? Math.round((inBody / frames) * 1000) / 1000 : null, after_contact: contactFix(fig, holder, locked, down, rest),
        after_module: grounded(fig, holder, footContact(locked, body), down, rest) }
    }
    out.clips = clips
    out.views = views
    out.hip_m = Math.round(hip * 1000) / 1000
    return out
  } finally { renderer.dispose(); renderer.forceContextLoss() }
}

declare global { interface Window { __e39?: { measurePoses: typeof measurePoses } } }
window.__e39 = { measurePoses }
