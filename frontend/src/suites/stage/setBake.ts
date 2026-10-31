// proto01_UIcast CW6 (04 §4; E38): a built set skinned from a picture — each face rendered straight on (an orthographic camera filling it)
// with the picture cast from its matched camera, at a texel size; and the face's coverage: per texel, how squarely the picture saw it
// (red: the cosine, 0 outside its view) and how coarse the picture was there (green: the picture's pixel on the face in texels, ÷ 8).
// The mask a Fill takes (unseen or magnified) is read from the coverage. No occlusion: a set seen from inside its own box hides nothing of
// itself; what stands in a room is a prop (D108), and its pixels land on the wall behind it.
import * as THREE from 'three'
import { toBlob } from './passes'
import { isGround, normalOf, setFaces, type PlaceSetDoc } from './placeSet'
import { sourceCamera, type SourceCam } from './setOverlay'

export interface BakedFace { id: string; w: number; h: number; px: [number, number]; texel_m: number; texture: Blob; coverage: Blob; seen: number; bad: number }
export const COVERAGE_RATIO_SCALE = 8                                        // green × 8 = the picture's pixel on the face, in texels
/** D133's rule as E38 used it: a texel the picture saw at a cosine under 0.05, or through a pixel over two texels wide, is the Fill's. */
export const UNSEEN_COS = 0.05
export const COARSE_TEXELS = 2
/** D170 (E46): a street's fronts stand out from their face (stalls, steps, awnings); seen more than 45° off square they lie on it sheared,
 *  so a facade's texel under this cosine is the Fill's too (place_sets.FACADE_COS). */
export const FACADE_COS = 0.7
/** D172 (E48): what stands on the ground lies on it as a smear when seen at a slant, so outside a room a road's, a pavement's or a floor's
 *  texel under this cosine is the Fill's too (place_sets.GROUND_COS). */
export const GROUND_COS = 0.35
/** The cosine under which a face's texel counts as unseen (place_sets.unseen_cos): a facade's, the ground's outside a room, else 0.05. */
export function unseenCos(id: string, kind: PlaceSetDoc['kind'] = 'room'): number {
  if (id.split('_')[0] === 'facade') return FACADE_COS
  return isGround(id, kind) ? GROUND_COS : UNSEEN_COS
}
/** D143: the texel by kind — the picture's pixel on the faces measured 1.1–1.8 cm in rooms, 4.6 in corridors, 8–12 in streets. */
export const TEXEL_BY_KIND: Record<PlaceSetDoc['kind'], number> = { room: 0.01, corridor: 0.02, street: 0.04, ground: 0.04 }

/** A baked face's coverage read back (RGBA bytes): the share of texels the picture saw at all, and the share the Fill takes. */
export function coverageShares(px: Uint8ClampedArray | Uint8Array, unseen = UNSEEN_COS): { seen: number; bad: number } {
  let seen = 0, bad = 0
  const n = px.length / 4
  for (let i = 0; i < px.length; i += 4) {
    const cos = px[i] / 255, ratio = (px[i + 1] / 255) * COVERAGE_RATIO_SCALE
    if (cos >= UNSEEN_COS) seen++
    if (cos < unseen || ratio > COARSE_TEXELS) bad++
  }
  return { seen: n ? +(seen / n).toFixed(4) : 0, bad: n ? +(bad / n).toFixed(4) : 0 }
}

/** Every face of the set baked from one picture: its texture and its coverage at `texelM` (a face's side capped at `maxPx`). */
export async function bakeSet(ps: PlaceSetDoc, plate: TexImageSource & { width: number; height: number }, cam: SourceCam, texelM = 0.01, maxPx = 2048): Promise<BakedFace[]> {
  const aspect = plate.width / plate.height
  const pc = sourceCamera(cam, aspect)
  const projVP = new THREE.Matrix4().multiplyMatrices(pc.projectionMatrix, pc.matrixWorldInverse)
  const tex = new THREE.Texture(plate as HTMLImageElement)
  tex.colorSpace = THREE.NoColorSpace; tex.needsUpdate = true
  // the picture's pixel at a metre's distance (the image plane's width at 1 m over its pixels): ×d / cos is its footprint on a face
  const pxRad = (2 * Math.tan(THREE.MathUtils.degToRad(pc.fov) / 2) * aspect) / plate.width
  const uniforms = { plate: { value: tex }, projVP: { value: projVP }, projPos: { value: pc.position.clone() }, coverage: { value: 0 },
    pxRad: { value: pxRad }, texel: { value: texelM }, ratioScale: { value: COVERAGE_RATIO_SCALE } }
  const mat = new THREE.ShaderMaterial({
    uniforms, side: THREE.DoubleSide,
    vertexShader: 'varying vec4 vWorld; varying vec3 vNormal; void main() { vWorld = modelMatrix * vec4(position, 1.0); vNormal = mat3(modelMatrix) * normal; gl_Position = projectionMatrix * viewMatrix * vWorld; }',
    fragmentShader: 'uniform sampler2D plate; uniform mat4 projVP; uniform vec3 projPos; uniform float coverage; uniform float pxRad; uniform float texel; uniform float ratioScale; ' +
      'varying vec4 vWorld; varying vec3 vNormal; void main() { vec4 c = projVP * vWorld; vec2 p = c.xy / max(c.w, 1e-6) * 0.5 + 0.5; ' +
      'float inside = step(0.0, c.w) * step(0.0, p.x) * step(p.x, 1.0) * step(0.0, p.y) * step(p.y, 1.0); ' +
      'if (coverage > 0.0) { vec3 toCam = projPos - vWorld.xyz; float d = length(toCam); float facing = abs(dot(normalize(vNormal), toCam / d)); ' +
      'float foot = d * pxRad / max(facing, 0.02); gl_FragColor = vec4(inside * facing, inside * min(1.0, foot / texel / ratioScale), 0.0, 1.0); return; } ' +
      'gl_FragColor = inside > 0.0 ? vec4(texture2D(plate, p).rgb, 1.0) : vec4(0.0, 0.0, 0.0, 0.0); }',
  })
  const r = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, alpha: true })
  r.setPixelRatio(1)
  const scene = new THREE.Scene()
  const out: BakedFace[] = []
  try {
    for (const f of setFaces(ps)) {
      const n = normalOf(f)
      const centre = f.origin.clone().addScaledVector(f.u, f.w / 2).addScaledVector(f.v, f.h / 2)
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(f.w, f.h), mat)
      mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(f.u, f.v, n))
      mesh.position.copy(centre)
      scene.add(mesh)
      const scale = Math.max(1, Math.max(f.w, f.h) / texelM / maxPx)               // a face too big for maxPx: coarser texels
      const tx = texelM * scale
      const W = Math.max(1, Math.round(f.w / tx)), H = Math.max(1, Math.round(f.h / tx))
      const cam = new THREE.OrthographicCamera(-f.w / 2, f.w / 2, f.h / 2, -f.h / 2, 0.01, 10)
      cam.position.copy(centre).addScaledVector(n, 1); cam.up.copy(f.v); cam.lookAt(centre); cam.updateMatrixWorld()
      r.setSize(W, H, false)
      uniforms.texel.value = tx
      uniforms.coverage.value = 0
      r.setClearColor(0x000000, 0); r.clear(); r.render(scene, cam)
      const texture = await toBlob(r.domElement)
      uniforms.coverage.value = 1
      r.setClearColor(0x000000, 1); r.clear(); r.render(scene, cam)
      const gl = r.getContext(), buf = new Uint8Array(W * H * 4)
      gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, buf)
      const coverage = await toBlob(r.domElement)
      out.push({ id: f.id, w: f.w, h: f.h, px: [W, H], texel_m: +tx.toFixed(5), texture, coverage, ...coverageShares(buf, unseenCos(f.id, ps.kind)) })
      scene.remove(mesh); mesh.geometry.dispose()
    }
    return out
  } finally { mat.dispose(); tex.dispose(); r.dispose(); r.forceContextLoss() }
}
