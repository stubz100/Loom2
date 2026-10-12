// E10 Stage → image spike (ArtCraft 08 §7, D74), the browser half: renders the frozen blockings of bench/stage/scenes.json into the
// conditioning passes a method can use — clay (grey Lambert), linear-disparity depth (a custom shader, not MeshDepthMaterial: near is
// white, far black, linear in 1/z), view-space normals, and an OpenPose COCO-18 skeleton drawn from the figures' own joints — plus the exact
// 2D keypoints the result is scored against (PCK@0.1). Figures are procedural mannequins (primitives on a joint tree, no licence question,
// no Mixamo asset), posed by presets. The runner (frontend/e2e/spikes/e10.run.mjs) writes the passes to engine/spikes/out/e10/passes/.
import * as THREE from 'three'

export interface Figure { pose: string; pos: [number, number, number]; yaw: number }
interface SceneDef { id: string; set: string; camera: { pos: [number, number, number]; target: [number, number, number]; fov: number }; figures: Figure[]; prompt: string }
type Euler3 = [number, number, number]
interface ScenesDoc { size: [number, number]; scenes: SceneDef[] }
let W = 1024, H = 576

// ---------------------------------------------------------------- the mannequin: a joint tree and COCO-18 markers
// figure space: y up, facing +z; its right side at −x. Arms and legs hang along −y at rest.
const JOINTS = ['root', 'spine', 'neck', 'head', 'r_shoulder', 'r_elbow', 'l_shoulder', 'l_elbow', 'r_hip', 'r_knee', 'l_hip', 'l_knee'] as const
export type Joint = (typeof JOINTS)[number]
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

// COCO-18 order: nose, neck, r_shoulder, r_elbow, r_wrist, l_shoulder, l_elbow, l_wrist, r_hip, r_knee, r_ankle, l_hip, l_knee, l_ankle,
// r_eye, l_eye, r_ear, l_ear
const COCO = ['nose', 'neck', 'r_shoulder', 'r_elbow', 'r_wrist', 'l_shoulder', 'l_elbow', 'l_wrist', 'r_hip', 'r_knee', 'r_ankle', 'l_hip', 'l_knee', 'l_ankle', 'r_eye', 'l_eye', 'r_ear', 'l_ear'] as const
const LIMBS: [number, number][] = [[1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7], [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13], [1, 0], [0, 14], [14, 16], [0, 15], [15, 17]]
const COLOURS = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0], [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255], [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]

const rad = THREE.MathUtils.degToRad
function limb(parent: THREE.Object3D, length: number, radius: number, mat: THREE.Material): void {
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(radius, Math.max(0.01, length - 2 * radius), 6, 12), mat)
  m.position.y = -length / 2
  parent.add(m)
}

/** One posed mannequin and its COCO-18 marker objects (world positions after updateMatrixWorld). */
/** Set a mannequin's joint rotations (degrees; joints a pose leaves out go back to rest) — E11 re-poses per frame. */
export function applyPose(J: Record<Joint, THREE.Object3D>, pose: Pose, yaw: number): void {
  for (const n of JOINTS) { const e = pose.j[n] ?? [0, 0, 0]; J[n].rotation.set(rad(e[0]), rad(e[1]), rad(e[2]), 'YXZ') }
  J.root.rotation.y += rad(yaw)
  J.root.position.y = pose.rootY ?? 0.95
}

export function mannequin(fig: Figure, mat: THREE.Material): { root: THREE.Object3D; markers: THREE.Object3D[]; joints: Record<Joint, THREE.Object3D> } {
  const pose = POSES[fig.pose] ?? POSES.stand
  const J = Object.fromEntries(JOINTS.map((n) => [n, new THREE.Object3D()])) as Record<Joint, THREE.Object3D>
  const root = J.root
  root.position.set(fig.pos[0], 0, fig.pos[2])
  applyPose(J, pose, fig.yaw)
  const marker = (parent: THREE.Object3D, x: number, y: number, z: number) => { const o = new THREE.Object3D(); o.position.set(x, y, z); parent.add(o); return o }
  // torso: pelvis → spine (chest) → neck → head
  const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.16, 0.18), mat); root.add(pelvis)
  root.add(J.spine); J.spine.position.set(0, 0.06, 0)
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.42, 0.2), mat); torso.position.y = 0.22; J.spine.add(torso)
  J.spine.add(J.neck); J.neck.position.set(0, 0.44, 0)
  J.neck.add(J.head); J.head.position.set(0, 0.06, 0)
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 20, 14), mat); head.position.y = 0.1; head.scale.set(0.9, 1.1, 1); J.head.add(head)
  const neckMarker = marker(J.neck, 0, 0, 0)
  const nose = marker(J.head, 0, 0.08, 0.11), rEye = marker(J.head, -0.035, 0.12, 0.09), lEye = marker(J.head, 0.035, 0.12, 0.09)
  const rEar = marker(J.head, -0.095, 0.1, 0), lEar = marker(J.head, 0.095, 0.1, 0)
  // arms
  const arm = (shoulder: Joint, elbow: Joint, side: number) => {
    J.spine.add(J[shoulder]); J[shoulder].position.set(side * 0.21, 0.4, 0)
    limb(J[shoulder], 0.29, 0.055, mat)
    J[shoulder].add(J[elbow]); J[elbow].position.set(0, -0.29, 0)
    limb(J[elbow], 0.27, 0.045, mat)
    return [marker(J[shoulder], 0, 0, 0), marker(J[elbow], 0, 0, 0), marker(J[elbow], 0, -0.27, 0)]
  }
  const [rS, rE, rW] = arm('r_shoulder', 'r_elbow', -1), [lS, lE, lW] = arm('l_shoulder', 'l_elbow', 1)
  // legs
  const leg = (hip: Joint, knee: Joint, side: number) => {
    root.add(J[hip]); J[hip].position.set(side * 0.1, -0.04, 0)
    limb(J[hip], 0.44, 0.07, mat)
    J[hip].add(J[knee]); J[knee].position.set(0, -0.44, 0)
    limb(J[knee], 0.43, 0.055, mat)
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.06, 0.24), mat); foot.position.set(0, -0.44, 0.06); J[knee].add(foot)
    return [marker(J[hip], 0, 0, 0), marker(J[knee], 0, 0, 0), marker(J[knee], 0, -0.43, 0)]
  }
  const [rH, rK, rA] = leg('r_hip', 'r_knee', -1), [lH, lK, lA] = leg('l_hip', 'l_knee', 1)
  return { root, joints: J, markers: [nose, neckMarker, rS, rE, rW, lS, lE, lW, rH, rK, rA, lH, lK, lA, rEye, lEye, rEar, lEar] }
}

export function set(kind: string, mat: THREE.Material): THREE.Object3D {
  const g = new THREE.Group()
  const box = (w: number, h: number, d: number, x: number, y: number, z: number) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); g.add(m) }
  if (kind === 'street') { box(9, 0.02, 30, 0, -0.01, -5); box(0.3, 5, 30, -3.6, 2.5, -5); box(0.3, 5, 30, 3.6, 2.5, -5); box(1.0, 2.2, 0.4, -3.2, 1.1, -2) }
  else if (kind === 'room') { box(9, 0.02, 9, 0, -0.01, 0); box(9, 3.2, 0.2, 0, 1.6, -3.2); box(0.2, 3.2, 9, -4, 1.6, 0); box(1.2, 0.8, 0.8, 1.9, 0.4, -1.8); box(0.45, 0.48, 0.45, 0, 0.24, 0) }
  else { box(12, 0.06, 6, 0, -0.03, 0); box(12, 0.08, 0.08, 0, 1.0, -2.6); box(12, 0.08, 0.08, 0, 1.0, 2.6); const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.15, 7, 16), mat); mast.position.set(2.6, 3.5, -1.6); g.add(mast) }
  return g
}

export const DEPTH = new THREE.ShaderMaterial({
  uniforms: { near: { value: 1.0 }, far: { value: 20.0 } },
  vertexShader: 'varying float vZ; void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vZ = -mv.z; gl_Position = projectionMatrix * mv; }',
  fragmentShader: 'uniform float near; uniform float far; varying float vZ; void main(){ float d = clamp((1.0 / max(vZ, near) - 1.0 / far) / (1.0 / near - 1.0 / far), 0.0, 1.0); gl_FragColor = vec4(vec3(d), 1.0); }',
})

/** Each figure's 18 markers projected to pixels; visible when in front of the camera and inside the frame. */
export function project(figMarkers: THREE.Object3D[][], cam: THREE.Camera): [number, number, number][][] {
  return figMarkers.map((ms) => ms.map((m) => {
    const v = m.getWorldPosition(new THREE.Vector3()).project(cam)
    const x = (v.x + 1) / 2 * W, y = (1 - v.y) / 2 * H
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10, v.z < 1 && x >= 0 && x < W && y >= 0 && y < H ? 1 : 0] as [number, number, number]
  }))
}

/** OpenPose COCO-18, as ControlNet preprocessors draw it: limbs as soft ellipses, joints as dots, on black. */
export function drawPose(keypoints: [number, number, number][][], w = W, h = H): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = w; c.height = h
  const g = c.getContext('2d')!
  g.fillStyle = '#000'; g.fillRect(0, 0, w, h)
  for (const kp of keypoints) {
    LIMBS.forEach(([a, b], k) => {
      if (!kp[a][2] || !kp[b][2]) return
      const [x1, y1] = kp[a], [x2, y2] = kp[b]
      g.save(); g.globalAlpha = 0.6; g.fillStyle = `rgb(${COLOURS[k].join(',')})`
      g.translate((x1 + x2) / 2, (y1 + y2) / 2); g.rotate(Math.atan2(y2 - y1, x2 - x1))
      g.beginPath(); g.ellipse(0, 0, Math.hypot(x2 - x1, y2 - y1) / 2, 4, 0, 0, Math.PI * 2); g.fill(); g.restore()
    })
    kp.forEach(([x, y, v], k) => { if (!v) return; g.fillStyle = `rgb(${COLOURS[k].join(',')})`; g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2); g.fill() })
  }
  return c
}

/** Resize the module's frame (E11 renders at its own size). */
export function setFrame(w: number, h: number): void { W = w; H = h }

export interface ScenePasses { id: string; prompt: string; passes: Record<'clay' | 'depth' | 'normal' | 'pose', string>; keypoints: [number, number, number][][] }

export function renderScenes(doc: ScenesDoc): ScenePasses[] {
  ;[W, H] = doc.size
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  renderer.setPixelRatio(1); renderer.setSize(W, H)
  const out: ScenePasses[] = []
  for (const sd of doc.scenes) {
    const scene = new THREE.Scene()
    const clay = new THREE.MeshLambertMaterial({ color: 0xd8d8d8 })
    scene.add(set(sd.set, clay))
    const figs = sd.figures.map((f) => mannequin(f, clay))
    figs.forEach((f) => scene.add(f.root))
    scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 1.6))
    const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(-3, 6, 5); scene.add(sun)
    const cam = new THREE.PerspectiveCamera(sd.camera.fov, W / H, 0.1, 100)
    cam.position.set(...sd.camera.pos); cam.lookAt(new THREE.Vector3(...sd.camera.target)); cam.updateMatrixWorld()
    scene.updateMatrixWorld(true)
    // depth normalised around the subject: near / far from the camera's distance to its target (ControlNet depth maps are per image)
    const dist = cam.position.distanceTo(new THREE.Vector3(...sd.camera.target))
    DEPTH.uniforms.near.value = Math.max(0.3, dist * 0.6); DEPTH.uniforms.far.value = dist * 3   // the subject mid-grey, the foreground bright
    const shot = (material: THREE.Material | null, bg: number) => { scene.overrideMaterial = material; scene.background = new THREE.Color(bg); renderer.render(scene, cam); return renderer.domElement.toDataURL('image/png') }
    const passes = { clay: shot(null, 0xb8b8b8), depth: shot(DEPTH, 0x000000), normal: shot(new THREE.MeshNormalMaterial(), 0x8080ff), pose: '' }
    const keypoints = project(figs.map((f) => f.markers), cam)
    const c = drawPose(keypoints)
    passes.pose = c.toDataURL('image/png')
    out.push({ id: sd.id, prompt: sd.prompt, passes, keypoints })
    scene.traverse((o) => { if ((o as THREE.Mesh).geometry) (o as THREE.Mesh).geometry.dispose() })
  }
  renderer.dispose()
  return out
}

/** The scenes come from the runner (bench/stage/scenes.json, read in Node: it lies outside the dev server's root). */
export async function runE10(mount: HTMLElement, out: HTMLElement) {
  const doc = (window as unknown as { __e10Input?: ScenesDoc }).__e10Input
  if (!doc) { out.textContent = 'E10: run through frontend/e2e/spikes/e10.run.mjs (it supplies bench/stage/scenes.json)'; return }
  const scenes = renderScenes(doc)
  const grid = document.createElement('div'); grid.style.cssText = 'display:grid;grid-template-columns:repeat(4,1fr);gap:4px'
  for (const s of scenes) for (const k of ['clay', 'depth', 'normal', 'pose'] as const) { const im = new Image(); im.src = s.passes[k]; im.style.width = '100%'; im.title = `${s.id} ${k}`; grid.append(im) }
  mount.replaceChildren(grid)
  ;(window as unknown as { __e10?: unknown }).__e10 = { size: [W, H], coco: COCO, scenes }
  out.textContent = `E10: ${scenes.length} scenes rendered (clay, depth, normal, pose) — the runner saves them`
}
