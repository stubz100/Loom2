// Spike E36 (proto01_UIcast 03 §5, 06 §2.4; D137 stage 2): a character's clay dummy — its Pixal3D shell bound to its fitted skeleton.
// The browser half of engine/spikes/e36_shell.py, loaded on the dev page: for one character (its body, the points its body was fitted to,
// its shell's GLB) it
//   · binds the shell to the figure in the reference's stance, by proximity (E23d) and by bone heat (proxy.ts),
//   · checks the skeleton against the shell: each joint and marker cast along the view into the shell — inside its volume or not, its depth
//     against the shell's middle there (the side view), a face marker's against the shell's front (the guide's landmarks, U8),
//   · checks the fit's front points: the figure's markers against SDPose's on the reference (mapped by the nose and the ankles),
//   · poses it (walk, sit, point, crouch) and measures the triangles stretched or squashed past 2× (each weighting),
//   · renders the shell's front silhouette (the IoU, scored in Python against the reference's figure) and the sheet's views.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { applyPose, JOINTS, mannequin, POSES, type Body } from '../suites/stage/builders'
import { bindProxy, stanceOf, type Weighting } from '../suites/stage/proxy'

export interface E36Input { name: string; body: Body; points: { pose?: number[][]; canvas?: number[] } | null; meshUrl: string }
type Img = string                                                           // a PNG as base64

const COCO = ['nose', 'neck', 'r_shoulder', 'r_elbow', 'r_wrist', 'l_shoulder', 'l_elbow', 'l_wrist', 'r_hip', 'r_knee', 'r_ankle', 'l_hip', 'l_knee', 'l_ankle', 'r_eye', 'l_eye', 'r_ear', 'l_ear']
const POSED = ['walk', 'sit', 'point', 'crouch']

async function png(r: THREE.WebGLRenderer): Promise<Img> {
  const blob: Blob = await new Promise((res) => r.domElement.toBlob((b) => res(b!), 'image/png'))
  const u = new Uint8Array(await blob.arrayBuffer()); let s = ''
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000))
  return btoa(s)
}

/** The surface crossings of a ray along −Z through (x, y): the nearest's and the farthest's z (null when it misses the shell). */
function through(meshes: THREE.Mesh[], x: number, y: number): { front: number; back: number } | null {
  const ray = new THREE.Raycaster(new THREE.Vector3(x, y, 50), new THREE.Vector3(0, 0, -1))
  const hits = ray.intersectObjects(meshes, false)
  if (!hits.length) return null
  return { front: hits[0].point.z, back: hits[hits.length - 1].point.z }
}

export async function measureShell(input: E36Input): Promise<Record<string, unknown>> {
  const out: Record<string, unknown> = { name: input.name }
  const mat = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const stance = stanceOf(input.points as never)
  const gltf = await new GLTFLoader().loadAsync(input.meshUrl)
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  const scene = new THREE.Scene()
  scene.add(new THREE.AmbientLight(0xffffff, 1.1)); const key = new THREE.DirectionalLight(0xffffff, 1.8); key.position.set(1.5, 3, 2.5); scene.add(key)
  try {
    for (const weights of ['proximity', 'heat'] as Weighting[]) {
      const fig = mannequin(mat, POSES.stand, stance, input.body)
      const root = new THREE.Group(); root.add(fig.root); scene.add(root); root.updateMatrixWorld(true)
      fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })            // the shell alone is drawn
      const px = bindProxy(gltf.scene.clone(true), fig.joints, fig.limbs, root, { preset: 'stand', joints: stance }, { weights, stance, visible: true })
      for (const m of px.meshes) scene.add(m)
      root.updateMatrixWorld(true)
      const H = input.body.height_m
      const r: Record<string, unknown> = { bind_ms: Math.round(px.ms), triangles: px.meshes.reduce((a, m) => a + m.geometry.attributes.position.count / 3, 0) }
      // the bind pose: positions as bound (the skinned meshes sit at their bind)
      const bindPos = px.meshes.map((m) => Float32Array.from(m.geometry.attributes.position.array as ArrayLike<number>))
      if (weights === 'proximity') {
        // the skeleton against the shell (the bind pose, the stance): plain meshes on the same geometry for the rays
        const plain = px.meshes.map((m) => new THREE.Mesh(m.geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })))
        plain.forEach((m) => m.updateMatrixWorld(true))
        const joints = JOINTS.map((j) => {
          const p = fig.joints[j].getWorldPosition(new THREE.Vector3()), t = through(plain, p.x, p.y)
          return { j, inside: !!t && p.z <= t.front + 1e-3 && p.z >= t.back - 1e-3, depth_cm: t ? Math.round((p.z - (t.front + t.back) / 2) * 1000) / 10 : null }
        })
        const markers = fig.markers.map((mk, k) => {
          const p = mk.getWorldPosition(new THREE.Vector3()), t = through(plain, p.x, p.y)
          return { m: COCO[k], hit: !!t, inside: !!t && p.z <= t.front + 1e-3 && p.z >= t.back - 1e-3, mid_cm: t ? Math.round((p.z - (t.front + t.back) / 2) * 1000) / 10 : null,
            front_cm: t ? Math.round((p.z - t.front) * 1000) / 10 : null }
        })
        out.joints = joints; out.markers = markers
        { const bb = new THREE.Box3(); px.meshes.forEach((m) => bb.expandByObject(m)); const w = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())
          const r3 = (v: number) => Math.round(v * 1000) / 1000
          out.extent = { shell: { top: r3(bb.max.y), bottom: r3(bb.min.y), x: r3((bb.min.x + bb.max.x) / 2), zmin: r3(bb.min.z), zmax: r3(bb.max.z), w: r3(bb.max.x - bb.min.x) },
            figure: { head: r3(w(fig.joints.head).y), nose: r3(w(fig.markers[0]).y), neck: r3(w(fig.joints.neck).y), shoulder: r3(w(fig.joints.r_shoulder).y), r_elbow: [r3(w(fig.joints.r_elbow).x), r3(w(fig.joints.r_elbow).y)], ankle: r3(w(fig.markers[10]).y), root_z: r3(w(fig.joints.root).z) } } }
        // the front points: the figure's markers against SDPose's on the reference, mapped by the nose and the ankles' middle
        const pose = input.points?.pose
        if (pose && pose.length >= 14) {
          const P = (k: number) => new THREE.Vector2(pose[k][0], pose[k][1])
          const M = (k: number) => { const v = fig.markers[k].getWorldPosition(new THREE.Vector3()); return new THREE.Vector2(v.x, v.y) }
          const ankP = P(10).add(P(13)).multiplyScalar(0.5), ankM = M(10).add(M(13)).multiplyScalar(0.5)
          const hP = P(0).distanceTo(ankP), hM = M(0).distanceTo(ankM)
          const map = (k: number) => { const d = P(k).sub(ankP).multiplyScalar(hM / hP); return new THREE.Vector2(ankM.x + d.x, ankM.y - d.y) }   // the picture's y runs down; facing the camera, its x runs as the figure's
          const errs = COCO.map((m, k) => (pose[k]?.[2] ?? 0) >= 0.3 ? { m, err: M(k).distanceTo(map(k)) / hM } : null).filter((e): e is { m: string; err: number } => !!e)
          out.front = errs.map((e) => ({ m: e.m, err: Math.round(e.err * 1000) / 1000 }))
        }
        // the shell's front silhouette (orthographic, white on black) for the IoU
        renderer.setSize(512, 768)
        const box = new THREE.Box3(); px.meshes.forEach((m) => box.expandByObject(m))
        const c = box.getCenter(new THREE.Vector3()), sz = box.getSize(new THREE.Vector3())
        const half = Math.max(sz.y / 2, (sz.x / 2) * 1.5) * 1.05
        const ortho = new THREE.OrthographicCamera(-half / 1.5, half / 1.5, half, -half, 0.1, 100); ortho.position.set(c.x, c.y, 20); ortho.lookAt(c.x, c.y, 0)
        const white = new THREE.MeshBasicMaterial({ color: 0xffffff })
        const keepMat = px.meshes.map((m) => m.material); px.meshes.forEach((m) => { m.material = white })
        scene.background = new THREE.Color(0x000000); renderer.render(scene, ortho); out.silhouette = await png(renderer)
        px.meshes.forEach((m, i) => { m.material = keepMat[i] })
        out.height_m = H
      }
      // the poses: stretch, and the views
      const views: Record<string, Img> = {}
      renderer.setSize(384, 576)
      scene.background = new THREE.Color(0xb8b8b8)
      const cam = new THREE.PerspectiveCamera(30, 384 / 576, 0.1, 50)
      const look = (yaw: number) => { const d = H * 2.4; cam.position.set(Math.sin(yaw) * d, H * 0.55, Math.cos(yaw) * d); cam.lookAt(0, H * 0.48, 0) }
      look(0.5); renderer.render(scene, cam); views.bind = await png(renderer)
      const stretch: Record<string, { over2: number; under05: number; worst: number }> = {}
      for (const name of POSED) {
        applyPose(fig.joints, POSES[name], undefined); root.updateMatrixWorld(true)
        px.meshes.forEach((m) => { m.skeleton.update() })
        let over = 0, under = 0, tri = 0, worst = 1
        const v = new THREE.Vector3(), a = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()]
        px.meshes.forEach((m, mi) => {
          const pos = m.geometry.attributes.position, n = pos.count, posed = new Float32Array(n * 3)
          for (let i = 0; i < n; i++) { v.fromBufferAttribute(pos, i); m.applyBoneTransform(i, v); posed[i * 3] = v.x; posed[i * 3 + 1] = v.y; posed[i * 3 + 2] = v.z }
          const b0 = bindPos[mi]
          for (let t = 0; t + 2 < n; t += 3) {
            let hi = 0, lo = Infinity
            for (const [p, q] of [[t, t + 1], [t + 1, t + 2], [t + 2, t]]) {
              a[0].set(b0[p * 3], b0[p * 3 + 1], b0[p * 3 + 2]); a[1].set(b0[q * 3], b0[q * 3 + 1], b0[q * 3 + 2])
              const L0 = a[0].distanceTo(a[1]); if (L0 < 1e-6) continue
              a[0].set(posed[p * 3], posed[p * 3 + 1], posed[p * 3 + 2]); a[1].set(posed[q * 3], posed[q * 3 + 1], posed[q * 3 + 2])
              const ratio = a[0].distanceTo(a[1]) / L0; hi = Math.max(hi, ratio); lo = Math.min(lo, ratio)
            }
            tri++; if (hi > 2) over++; if (lo < 0.5) under++; worst = Math.max(worst, hi)
          }
        })
        stretch[name] = { over2: Math.round((over / Math.max(1, tri)) * 10000) / 10000, under05: Math.round((under / Math.max(1, tri)) * 10000) / 10000, worst: Math.round(worst * 100) / 100 }
        if (name !== 'point') { look(name === 'walk' ? 0.5 : 0.9); renderer.render(scene, cam); views[name] = await png(renderer) }
      }
      r.stretch = stretch; r.views = views
      out[weights] = r
      for (const m of px.meshes) scene.remove(m)
      px.dispose(); scene.remove(root)
    }
    return out
  } finally { renderer.dispose(); renderer.forceContextLoss() }
}

declare global { interface Window { __e36?: { measureShell: typeof measureShell } } }
window.__e36 = { measureShell }
