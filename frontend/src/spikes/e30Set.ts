// E30 — a set from an image (D119, proto01_animate 25 §3), the browser half: each relief (MoGe's point map as a textured mesh, the camera
// that took the picture at the origin looking down -Z with MoGe's lens) and, for the props arm, E28c's Pixal3D models stood on it; the
// camera moved through the runner's list and, per move, the holes (pixels nothing covers) and the smear (a texel spread over more than
// three pixels) counted over the frame — the picture's own edge coming into view counted apart — plus the beauty / clay / depth passes as images for the sheet moves.
// The runner (frontend/e2e/spikes/e30.run.mjs) serves the GLBs from public/spikes/e30/ and writes the images and views.json.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

interface Move { name: string; pos: [number, number, number]; yaw: number; pitch: number }
interface Prop { tag: string; url: string; pos: [number, number, number]; scale: number; yaw: number }
interface Scene { tag: string; relief: string; fov_y: number; zrange: [number, number]; moves: Move[]; sheet: string[]; props: Prop[] }
interface Input { size: [number, number]; scenes: Scene[] }
export interface MoveResult { name: string; holes: number; holes_edge: number; holes_inner: number; smear: number; tear: number; images?: Record<string, string> }
export interface SceneResult { tag: string; faces: number; moves: MoveResult[]; error?: string }

declare global { interface Window { __e30Input?: Input; __e30?: { results: SceneResult[] } } }

const SMEAR_PPT = 3                                                      // pixels per texel above which a pixel counts as smeared

const VS = 'varying vec2 vUv; varying float vZ; void main() { vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.0); vZ = -mv.z; gl_Position = projectionMatrix * mv; }'
const coverMat = new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: 'void main() { gl_FragColor = vec4(1.0); }', side: THREE.DoubleSide })
const smearMat = new THREE.ShaderMaterial({
  uniforms: { texSize: { value: new THREE.Vector2(1, 1) } },
  vertexShader: VS,
  // the texel area under one pixel from the UV Jacobian (its determinant: a skirt stretched one way is caught, the max of the two
  // derivatives would miss it); the red channel carries the linear pixels-per-texel / 8 (1 texel per pixel → 0.125; 3 per texel → 0.375)
  fragmentShader: 'uniform vec2 texSize; varying vec2 vUv; void main() { vec2 dx = dFdx(vUv) * texSize; vec2 dy = dFdy(vUv) * texSize; float area = abs(dx.x * dy.y - dx.y * dy.x); float ppt = 1.0 / sqrt(max(area, 1e-8)); gl_FragColor = vec4(min(ppt / 8.0, 1.0), 0.0, 0.0, 1.0); }',
  side: THREE.DoubleSide,
})
const propSmearMat = new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: 'void main() { gl_FragColor = vec4(0.125, 0.0, 0.0, 1.0); }', side: THREE.DoubleSide })
const depthMat = new THREE.ShaderMaterial({
  uniforms: { zmin: { value: 0.1 }, zmax: { value: 10 } },
  vertexShader: VS,
  fragmentShader: 'uniform float zmin; uniform float zmax; varying float vZ; void main() { float d = 1.0 - clamp((vZ - zmin) / (zmax - zmin), 0.0, 1.0); gl_FragColor = vec4(d, d, d, 1.0); }',
  side: THREE.DoubleSide,
})
const clayMat = new THREE.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 0.9, metalness: 0, side: THREE.DoubleSide })

function meshesOf(root: THREE.Object3D): THREE.Mesh[] {
  const out: THREE.Mesh[] = []
  root.traverse((o) => { if ((o as THREE.Mesh).isMesh) out.push(o as THREE.Mesh) })
  return out
}

function triangles(ms: THREE.Mesh[]): number {
  let n = 0
  for (const m of ms) n += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3
  return Math.round(n)
}

/** Count the frame. Holes: pixels the coverage pass left black — those connected to the frame's border are the picture's own edge
 *  coming into view (`edge`: a pan or a truck shows what the picture never had), the others are tears inside it (`inner`: what was
 *  hidden behind something). Smear: pixels of the smear pass above the bar (a texel spread over more than SMEAR_PPT pixels). */
function count(gl: WebGL2RenderingContext, w: number, h: number, kind: 'holes' | 'smear'): { all: number; inner: number; edge: number } {
  const buf = new Uint8Array(w * h * 4)
  gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf)
  const bar = Math.round((SMEAR_PPT / 8) * 255)
  const hit = new Uint8Array(w * h)
  let all = 0
  for (let i = 0; i < w * h; i++) {
    const r = buf[i * 4]
    if (kind === 'holes' ? r < 8 : r > bar) { hit[i] = 1; all++ }
  }
  let edge = 0
  if (kind === 'holes' && all) {
    const stack: number[] = []
    for (let x = 0; x < w; x++) { stack.push(x, (h - 1) * w + x) }
    for (let y = 1; y < h - 1; y++) { stack.push(y * w, y * w + w - 1) }
    while (stack.length) {
      const i = stack.pop()!
      if (hit[i] !== 1) continue
      hit[i] = 2
      edge++
      const x = i % w, y = (i - x) / w
      if (x > 0) stack.push(i - 1)
      if (x < w - 1) stack.push(i + 1)
      if (y > 0) stack.push(i - w)
      if (y < h - 1) stack.push(i + w)
    }
  }
  const pct = (n: number) => (100 * n) / (w * h)
  return { all: pct(all), inner: pct(all - edge), edge: pct(edge) }
}

async function renderScene(renderer: THREE.WebGLRenderer, size: [number, number], sc: Scene): Promise<Omit<SceneResult, 'tag'>> {
  const [w, h] = size
  const loader = new GLTFLoader()
  const relief = (await loader.loadAsync(sc.relief)).scene
  const reliefMeshes = meshesOf(relief)
  const texture = (reliefMeshes[0].material as THREE.MeshStandardMaterial).map
  const beautyMat = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide })   // the picture itself, unlit: the plate of that camera
  const img = texture?.image as { width?: number; height?: number } | undefined
  const texSize = new THREE.Vector2(img?.width ?? 1024, img?.height ?? 576)
  const scene = new THREE.Scene()
  scene.add(relief)
  const propMeshes: THREE.Mesh[] = []
  const propBeauty = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>()
  for (const p of sc.props) {
    const g = (await loader.loadAsync(p.url)).scene
    const grp = new THREE.Group()
    grp.add(g)
    grp.position.set(...p.pos)
    grp.scale.setScalar(p.scale)
    grp.rotation.y = THREE.MathUtils.degToRad(p.yaw)
    scene.add(grp)
    for (const m of meshesOf(g)) { propMeshes.push(m); propBeauty.set(m, m.material) }
  }
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 1.4)
  key.position.set(-2, 3, 2)
  scene.add(key)
  const cam = new THREE.PerspectiveCamera(sc.fov_y, w / h, 0.02, 200)
  cam.rotation.order = 'YXZ'
  renderer.setSize(w, h, false)
  const gl = renderer.getContext() as WebGL2RenderingContext
  depthMat.uniforms.zmin.value = sc.zrange[0]
  depthMat.uniforms.zmax.value = sc.zrange[1]
  smearMat.uniforms.texSize.value.copy(texSize)
  const set = (reliefM: THREE.Material, propM: THREE.Material | 'own') => {
    for (const m of reliefMeshes) m.material = reliefM
    for (const m of propMeshes) m.material = propM === 'own' ? propBeauty.get(m)! : propM
  }
  const results: MoveResult[] = []
  for (const mv of sc.moves) {
    cam.position.set(...mv.pos)
    cam.rotation.set(THREE.MathUtils.degToRad(mv.pitch), THREE.MathUtils.degToRad(mv.yaw), 0)
    cam.updateMatrixWorld()
    scene.background = new THREE.Color(0x000000)
    set(coverMat, coverMat)
    renderer.render(scene, cam)
    const holes = count(gl, w, h, 'holes')
    set(smearMat, propSmearMat)
    renderer.render(scene, cam)
    const smear = count(gl, w, h, 'smear')
    const r: MoveResult = { name: mv.name, holes: +holes.all.toFixed(2), holes_edge: +holes.edge.toFixed(2), holes_inner: +holes.inner.toFixed(2), smear: +smear.all.toFixed(2), tear: +(holes.inner + smear.all).toFixed(2) }
    if (sc.sheet.includes(mv.name)) {
      const images: Record<string, string> = {}
      scene.background = new THREE.Color(0xff00ff)
      set(beautyMat, 'own')
      renderer.render(scene, cam)
      images.beauty = renderer.domElement.toDataURL('image/jpeg', 0.92)
      scene.background = new THREE.Color(0x303034)
      set(clayMat, clayMat)
      renderer.render(scene, cam)
      images.clay = renderer.domElement.toDataURL('image/jpeg', 0.92)
      scene.background = new THREE.Color(0x000000)
      set(depthMat, depthMat)
      renderer.render(scene, cam)
      images.depth = renderer.domElement.toDataURL('image/jpeg', 0.92)
      r.images = images
    }
    results.push(r)
  }
  const faces = triangles(reliefMeshes)
  scene.clear()
  relief.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) m.geometry.dispose() })
  texture?.dispose()
  return { faces, moves: results }
}

export async function runE30(mount: HTMLElement, out: HTMLElement): Promise<void> {
  const input = window.__e30Input
  if (!input) {
    out.textContent = 'E30: no input (the runner sets window.__e30Input)'
    return
  }
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true })
  mount.append(renderer.domElement)
  const results: SceneResult[] = []
  for (const sc of input.scenes) {
    let r: SceneResult
    try {
      r = { tag: sc.tag, ...(await renderScene(renderer, input.size, sc)) }
    } catch (e) {
      r = { tag: sc.tag, faces: 0, moves: [], error: String((e as Error).message ?? e) }
    }
    results.push(r)
    const line = document.createElement('div')
    const worst = r.moves.reduce((a, b) => (b.tear > a.tear ? b : a), { name: '—', tear: 0 } as MoveResult)
    line.textContent = `${sc.tag}: ${r.error ?? `${r.faces} triangles, worst ${worst.name} tear ${worst.tear} %`}`
    out.append(line)
  }
  window.__e30 = { results }
}
