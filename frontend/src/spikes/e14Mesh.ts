// E14 image → mesh spike (ArtCraft 08 §7, D74), the browser half: loads each generated GLB (served from public/spikes/e14/), renders
// four lit turntable views (front, right, back, left — the "plausible back" check on the sheets), the object's silhouette at the same
// four yaws (the generator's canonical front is not known, so the scorer keeps the best match) and counts triangles (the ≤ 50k bar).
// The runner (frontend/e2e/spikes/e14.run.mjs) writes them to engine/spikes/out/e14/views/; engine/spikes/e14_mesh.py score does the IoU.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

interface MeshIn { tag: string; url: string }
interface Input { meshes: MeshIn[]; size?: number }
export interface MeshViews { tag: string; faces: number; views: Record<string, string>; sil: Record<string, string>; error?: string }

declare global { interface Window { __e14Input?: Input; __e14?: { results: MeshViews[] } } }

const YAWS: Record<string, number> = { front: 0, right: 90, back: 180, left: 270 }
const SIL_YAWS = [0, 45, 90, 135, 180, 225, 270, 315]                      // silhouette candidates: the props were shot in three-quarter view…
const PITCHES = [0, 25, 45]                                              // …from above; the generator's canonical frame is not known
const FOV = 35

function triangles(root: THREE.Object3D): number {
  let n = 0
  root.traverse((o) => {
    const mesh = o as THREE.Mesh
    if (mesh.isMesh && mesh.geometry) n += (mesh.geometry.index ? mesh.geometry.index.count : mesh.geometry.attributes.position.count) / 3
  })
  return Math.round(n)
}

/** Centre the model on the origin, fit a perspective camera to its bounding sphere, shoot the lit views and the silhouettes. */
export async function renderMesh(renderer: THREE.WebGLRenderer, size: number, url: string): Promise<Omit<MeshViews, 'tag'>> {
  const gltf = await new GLTFLoader().loadAsync(url)
  const obj = gltf.scene
  const box = new THREE.Box3().setFromObject(obj)
  const radius = box.getSize(new THREE.Vector3()).length() / 2
  obj.position.sub(box.getCenter(new THREE.Vector3()))
  const pivot = new THREE.Group()
  pivot.add(obj)
  const scene = new THREE.Scene()
  scene.add(pivot, new THREE.AmbientLight(0xffffff, 1.2))
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(1, 2, 3)
  const fill = new THREE.DirectionalLight(0xffffff, 0.8)
  fill.position.set(-2, 1, -1)
  scene.add(key, fill)
  const cam = new THREE.PerspectiveCamera(FOV, 1, 0.01, 100)
  cam.position.set(0, 0, (radius / Math.tan(THREE.MathUtils.degToRad(FOV / 2))) * 1.15)
  cam.lookAt(0, 0, 0)
  renderer.setSize(size, size, false)
  const white = new THREE.MeshBasicMaterial({ color: 0xffffff })
  const views: Record<string, string> = {}
  const sil: Record<string, string> = {}
  scene.background = new THREE.Color(0x303030)
  for (const [name, yaw] of Object.entries(YAWS)) {
    pivot.rotation.set(0, THREE.MathUtils.degToRad(yaw), 0)
    renderer.render(scene, cam)
    views[name] = renderer.domElement.toDataURL('image/png')
  }
  scene.overrideMaterial = white
  scene.background = new THREE.Color(0x000000)
  for (const yaw of SIL_YAWS) {
    for (const pitch of PITCHES) {
      pivot.rotation.set(THREE.MathUtils.degToRad(pitch), THREE.MathUtils.degToRad(yaw), 0) // yaw first, then tipped towards the camera = seen from above
      renderer.render(scene, cam)
      sil[`${yaw}_${pitch}`] = renderer.domElement.toDataURL('image/png')
    }
  }
  return { faces: triangles(obj), views, sil }
}

export async function runE14(mount: HTMLElement, out: HTMLElement): Promise<void> {
  const input = window.__e14Input
  if (!input) {
    out.textContent = 'E14: no input (the runner sets window.__e14Input)'
    return
  }
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  mount.append(renderer.domElement)
  const results: MeshViews[] = []
  for (const m of input.meshes) {
    let r: MeshViews
    try {
      r = { tag: m.tag, ...(await renderMesh(renderer, input.size ?? 512, m.url)) }
    } catch (e) {
      r = { tag: m.tag, faces: 0, views: {}, sil: {}, error: String((e as Error).message ?? e) }
    }
    results.push(r)
    const line = document.createElement('div')
    line.textContent = `${m.tag}: ${r.error ?? `${r.faces} triangles`}`
    out.append(line)
  }
  window.__e14 = { results }
}
