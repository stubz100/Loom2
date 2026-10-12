// E11 Stage → video spike (ArtCraft 08 §7, D74), the browser half: five animated blockings (camera move + figure motion, 121 frames at
// 24 fps — LTX's 8n + 1) rendered per frame as OpenPose and depth passes, plus the clay frame 0 a first image is made from. Mannequins,
// sets and passes are E10's (e10Stage.ts). The runner (frontend/e2e/spikes/e11.run.mjs) writes them to engine/spikes/out/e11/<shot>/.
import * as THREE from 'three'
import { applyPose, DEPTH, drawPose, mannequin, POSES, project, set, setFrame, type Joint, type Pose } from './e10Stage'

const W = 1024, H = 576, FRAMES = 121, FPS = 24

type Lerp = (t: number) => { pose: Pose; pos: [number, number, number]; yaw: number }
interface Shot { id: string; set: string; prompt: string; figures: Lerp[]; camera: (t: number) => { pos: [number, number, number]; target: [number, number, number]; fov: number } }

const mix = (a: number, b: number, w: number) => a + (b - a) * w
const ease = (t: number) => t * t * (3 - 2 * t)
/** A gait at `hz` strides per second: legs and arms swing in opposition (walk ≈ 1, run ≈ 1.6 with bigger angles). */
function gait(t: number, hz: number, amp: number): Pose {
  const s = Math.sin(2 * Math.PI * hz * t * FRAMES / FPS), c = Math.cos(2 * Math.PI * hz * t * FRAMES / FPS)
  const j: Partial<Record<Joint, [number, number, number]>> = {
    r_hip: [-amp * s, 0, 0], l_hip: [amp * s, 0, 0], r_knee: [amp * 0.9 * Math.max(0, c), 0, 0], l_knee: [amp * 0.9 * Math.max(0, -c), 0, 0],
    r_shoulder: [amp * 0.8 * s, 0, -6], l_shoulder: [-amp * 0.8 * s, 0, 6], r_elbow: [-amp * 0.9, 0, 0], l_elbow: [-amp * 0.9, 0, 0],
  }
  if (amp > 40) j.spine = [12, 0, 0]
  return { j }
}
/** Blend two presets (joint by joint, missing joints at rest). */
function blend(a: Pose, b: Pose, w: number): Pose {
  const keys = new Set([...Object.keys(a.j), ...Object.keys(b.j)]) as Set<Joint>
  const j: Partial<Record<Joint, [number, number, number]>> = {}
  for (const k of keys) { const x = a.j[k] ?? [0, 0, 0], y = b.j[k] ?? [0, 0, 0]; j[k] = [mix(x[0], y[0], w), mix(x[1], y[1], w), mix(x[2], y[2], w)] }
  return { rootY: mix(a.rootY ?? 0.95, b.rootY ?? 0.95, w), j }
}

const SHOTS: Shot[] = [
  { id: 'walk_dolly', set: 'street', prompt: 'A young woman with long red braids in a green hooded wool cloak walks toward the camera down a rainy cobbled alley at night; the camera pulls back ahead of her, neon reflections.',
    figures: [(t) => ({ pose: gait(t, 0.9, 25), pos: [0, 0, -3 + 3.2 * t], yaw: 0 })],
    camera: (t) => ({ pos: [0, 1.55, 2.6 + 2.6 * t], target: [0, 1.1, -2 + 3 * t], fov: 42 }) },
  { id: 'turn_orbit', set: 'room', prompt: 'In a plain room with soft window light, a young woman with red braids in a green hood stands still and slowly turns her head to her left; the camera slowly circles around her.',
    figures: [(t) => ({ pose: blend(POSES.stand, POSES.look_left, ease(t)), pos: [0, 0, 0], yaw: 0 })],
    camera: (t) => { const a = THREE.MathUtils.degToRad(-20 + 40 * t); return { pos: [3 * Math.sin(a), 1.55, 3 * Math.cos(a)], target: [0, 1.3, 0], fov: 38 } } },
  { id: 'wave_static', set: 'deck', prompt: 'A grey-bearded sea captain in a navy coat stands on the deck of a boat at sunrise and waves to someone on the shore, steady medium shot.',
    figures: [(t) => { const w = Math.sin(2 * Math.PI * 1.2 * t * FRAMES / FPS); return { pose: { j: { r_shoulder: [0, 0, -150], r_elbow: [0, 0, 20 + 25 * w], l_shoulder: [0, 0, 8], head: [0, -15, 0] } }, pos: [0, 0, 0], yaw: 30 } }],
    camera: () => ({ pos: [1.2, 1.5, 3.4], target: [0, 1.2, 0], fov: 40 }) },
  { id: 'run_track', set: 'street', prompt: 'Two hooded figures in dark cloaks run along a narrow rainy alley at night, the camera panning to follow them, motion blur, cinematic.',
    figures: [(t) => ({ pose: gait(t, 1.6, 55), pos: [-2 + 4 * t, 0, 0], yaw: 90 }), (t) => ({ pose: gait(t + 0.13, 1.6, 55), pos: [-3 + 4 * t, 0, -1.2], yaw: 90 })],
    camera: (t) => ({ pos: [-0.5 + 1.5 * t, 1.2, 4.5], target: [-1.5 + 4 * t, 1.0, -0.5], fov: 45 }) },
  { id: 'crouch_crane', set: 'street', prompt: 'A young woman with red braids in a green cloak crouches down on wet cobblestones to pick something up while the camera cranes up above her, lantern light.',
    figures: [(t) => ({ pose: blend(POSES.stand, POSES.crouch, ease(Math.min(1, t * 1.4))), pos: [0, 0, 0], yaw: -20 })],
    camera: (t) => ({ pos: [0, 1.4 + 2.2 * ease(t), 3.0 - 0.4 * t], target: [0, 0.9 - 0.4 * t, 0], fov: 42 }) },
]

export interface ShotFrames { id: string; prompt: string; fps: number; size: [number, number]; clay0: string; pose: string[]; depth: string[]; keypoints: [number, number, number][][][] }

/** Render one shot: per frame the pose map and depth pass, plus frame 0 in clay. */
export function renderShot(i: number): ShotFrames {
  setFrame(W, H)
  const shot = SHOTS[i]
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  renderer.setPixelRatio(1); renderer.setSize(W, H)
  const scene = new THREE.Scene()
  const clay = new THREE.MeshLambertMaterial({ color: 0xd8d8d8 })
  scene.add(set(shot.set, clay))
  const figs = shot.figures.map((f) => { const s = f(0); const m = mannequin({ pose: 'stand', pos: s.pos, yaw: s.yaw }, clay); scene.add(m.root); return m })
  scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 1.6))
  const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(-3, 6, 5); scene.add(sun)
  const cam = new THREE.PerspectiveCamera(42, W / H, 0.1, 100)
  const out: ShotFrames = { id: shot.id, prompt: shot.prompt, fps: FPS, size: [W, H], clay0: '', pose: [], depth: [], keypoints: [] }
  for (let f = 0; f < FRAMES; f++) {
    const t = f / (FRAMES - 1)
    shot.figures.forEach((fn, k) => { const s = fn(t); figs[k].root.position.set(s.pos[0], 0, s.pos[2]); figs[k].root.rotation.set(0, 0, 0); applyPose(figs[k].joints, s.pose, s.yaw) })
    const c = shot.camera(t)
    cam.fov = c.fov; cam.updateProjectionMatrix(); cam.position.set(...c.pos); cam.lookAt(new THREE.Vector3(...c.target)); cam.updateMatrixWorld()
    scene.updateMatrixWorld(true)
    const dist = cam.position.distanceTo(new THREE.Vector3(...c.target))
    DEPTH.uniforms.near.value = Math.max(0.3, dist * 0.6); DEPTH.uniforms.far.value = dist * 3
    if (f === 0) { scene.overrideMaterial = null; scene.background = new THREE.Color(0xb8b8b8); renderer.render(scene, cam); out.clay0 = renderer.domElement.toDataURL('image/png') }
    scene.overrideMaterial = DEPTH; scene.background = new THREE.Color(0x000000); renderer.render(scene, cam)
    out.depth.push(renderer.domElement.toDataURL('image/png'))
    const kp = project(figs.map((m) => m.markers), cam)
    out.keypoints.push(kp)
    out.pose.push(drawPose(kp, W, H).toDataURL('image/png'))
  }
  scene.traverse((o) => { if ((o as THREE.Mesh).geometry) (o as THREE.Mesh).geometry.dispose() })
  renderer.dispose()
  return out
}

export async function runE11(mount: HTMLElement, out: HTMLElement) {
  ;(window as unknown as { __e11?: unknown }).__e11 = { shots: SHOTS.map((s) => s.id), render: renderShot }
  mount.textContent = `E11: ${SHOTS.length} shots × ${FRAMES} frames — the runner renders them one at a time`
  out.textContent = ''
}
