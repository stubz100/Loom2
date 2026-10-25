// E23d (D105): a figure's shadow proxy — a mesh shaped like its character (the app's image → mesh job on the animation reference, D84),
// bound to the figure's twelve joints so it follows every pose, and seen only by the light: it casts the character's outline into Stage's
// shadows while the dummy casts nothing. "It doesn't have to be perfect, just a dummy to cast close enough shadows" (the author).
//
// The binding: the figure posed in the reference's stance; the mesh scaled to the figure's height, stood on the floor under it, its
// left-right axis turned onto the figure's (front and back cast the same shadow); each vertex weighted to the figure's limb segments — a
// THREE.SkinnedMesh whose bones are the figure's joints. Two weightings (proto01_UIcast E36, D136 U6: the shell is the character's clay):
//   proximity  each vertex to its two nearest segments by inverse squared distance (E23d's)
//   heat       the default (E36 → D138: on eight shells 0.2–4.3 % of the triangles stretched past 2× in a walk, a sit and a crouch against
//              proximity's 3.3–14.8 %; 0.5–1.2 s a bind for 50k triangles against 30 ms) — Pinocchio's bone heat: per segment, the steady heat on the mesh's surface graph with each vertex warmed by its nearest
//              segment (weight 1/d²) — (L + H) w = H p, solved by conjugate gradients; the four largest kept. It follows the surface, so a
//              coat's hem or a long skirt between the legs is not pulled by the nearer leg across empty space.
// Unseen: its material writes no colour and no depth (the viewport shows only its shadow); the passes, which override every material,
// render twice — once with the proxies for the shadow map, once without them and that map kept (engine.shotWith).
import * as THREE from 'three'
import { applyPose, JOINTS, POSES, type Joint, type Limbs } from './builders'


/** The reference's stance when its points are not known: arms a little away from the body (proto01_animate 01 step 2). */
export const A_POSE: Record<string, number[]> = { r_shoulder: [0, 0, -22], l_shoulder: [0, 0, 22], r_elbow: [0, 0, 0], l_elbow: [0, 0, 0] }
export type StancePoints = { pose?: number[][] } | null | undefined

/** S4: the arms as the reference holds them, from SDPose's body points (OpenPose-18: 2–4 the right shoulder, elbow, wrist — on the picture's
 *  left for a figure facing it — 5–7 the left's): each upper arm's swing out from hanging down, each forearm's on from it, in the picture's
 *  plane (the front view). Missing points: A_POSE. */
export function stanceOf(points: StancePoints): Record<string, number[]> {
  const p = points?.pose
  if (!p || p.length < 8) return A_POSE
  const seen = (i: number) => (p[i]?.[2] ?? 0) >= 0.3
  const out: Record<string, number[]> = { ...A_POSE }
  for (const [s, e, wr, side] of [[2, 3, 4, -1], [5, 6, 7, 1]] as const) {
    if (!seen(s) || !seen(e) || !seen(wr)) continue
    const out1 = (a: number, b: number) => Math.atan2(side * (p[b][0] - p[a][0]), p[b][1] - p[a][1]) * 180 / Math.PI   // outward from straight down
    const upper = out1(s, e), fore = out1(e, wr)
    const name = side < 0 ? 'r' : 'l'
    out[`${name}_shoulder`] = [0, 0, +(side * upper).toFixed(1)]
    out[`${name}_elbow`] = [0, 0, +(side * (fore - upper)).toFixed(1)]
  }
  return out
}

/** CS2: the points of the Cast version a shell was made for — the stage's store answers (it knows the versions), so a shell binds in its
 *  reference's stance wherever it is drawn (the viewport, the passes, the bench). */
let pointsOfShell: (assetId: string) => StancePoints = () => null
export const setShellPoints = (fn: (assetId: string) => StancePoints) => { pointsOfShell = fn }
export const shellStance = (assetId: string) => stanceOf(pointsOfShell(assetId))
export const shellPoints = (assetId: string) => pointsOfShell(assetId) as BindOptions['points']

/** Each joint's segment, from the joint to where its part ends, in the joint's own frame (−Y down the limb). */
function segmentEnd(j: Joint, limbs: Limbs): THREE.Vector3 {
  switch (j) {
    case 'r_shoulder': case 'l_shoulder': return new THREE.Vector3(0, -limbs.upper_arm, 0)
    case 'r_elbow': case 'l_elbow': return new THREE.Vector3(0, -limbs.forearm - 0.18, 0)          // the hand rides on the forearm
    case 'r_hip': case 'l_hip': return new THREE.Vector3(0, -limbs.thigh, 0)
    case 'r_knee': case 'l_knee': return new THREE.Vector3(0, -limbs.shin - 0.06, 0.08)              // the foot rides on the shin
    case 'spine': return new THREE.Vector3(0, 0.42, 0)
    case 'neck': return new THREE.Vector3(0, 0.12, 0)                                                // CS1 (S3): the neck joint to the head's pivot at ×1
    case 'head': return new THREE.Vector3(0, 0.16, 0)                                                // the pivot (the jaw) to the head's top
    case 'root': return new THREE.Vector3(0, -0.04, 0)
  }
}

function pointSegment(p: THREE.Vector3, a: THREE.Vector3, b: THREE.Vector3): number {
  const ab = b.clone().sub(a), t = Math.max(0, Math.min(1, p.clone().sub(a).dot(ab) / Math.max(1e-9, ab.lengthSq())))
  return p.distanceTo(a.clone().addScaledVector(ab, t))
}

export type Weighting = 'proximity' | 'heat'
export interface Segment { j: Joint; a: THREE.Vector3; b: THREE.Vector3 }
interface Skin { idx: Uint16Array; wts: Float32Array }

/** E23d: each vertex to its two nearest segments, by inverse squared distance. */
export function proximityWeights(pos: THREE.BufferAttribute | THREE.InterleavedBufferAttribute, segs: Segment[]): Skin {
  const n = pos.count, idx = new Uint16Array(n * 4), wts = new Float32Array(n * 4), p = new THREE.Vector3()
  for (let i = 0; i < n; i++) {
    p.fromBufferAttribute(pos, i)
    let b0 = 0, d0 = Infinity, b1 = 0, d1 = Infinity
    segs.forEach((sg, k) => {
      const d = pointSegment(p, sg.a, sg.b)
      if (d < d0) { b1 = b0; d1 = d0; b0 = k; d0 = d } else if (d < d1) { b1 = k; d1 = d }
    })
    const w0 = 1 / (d0 * d0 + 1e-4), w1 = 1 / (d1 * d1 + 1e-4)
    idx[i * 4] = b0; idx[i * 4 + 1] = b1
    wts[i * 4] = w0 / (w0 + w1); wts[i * 4 + 1] = w1 / (w0 + w1)
  }
  return { idx, wts }
}

/** E36: bone heat over the surface (Pinocchio). `pos` is a triangle soup (non-indexed): vertices are joined by their position (0.1 mm),
 *  the graph's edges weighted 1 / length² (the same units as H's 1 / d², so no constant to tune), one SPD system for every segment. */
export function heatWeights(pos: THREE.BufferAttribute | THREE.InterleavedBufferAttribute, segs: Segment[], maxIter = 600): Skin {
  const n = pos.count
  const ids = new Int32Array(n), keyOf = new Map<string, number>(), xs: number[] = []
  const p = new THREE.Vector3()
  for (let i = 0; i < n; i++) {
    p.fromBufferAttribute(pos, i)
    const k = `${Math.round(p.x * 1e4)},${Math.round(p.y * 1e4)},${Math.round(p.z * 1e4)}`
    let id = keyOf.get(k)
    if (id === undefined) { id = xs.length / 3; keyOf.set(k, id); xs.push(p.x, p.y, p.z) }
    ids[i] = id
  }
  const m = xs.length / 3
  const edges = new Map<number, number>()
  for (let t = 0; t + 2 < n; t += 3) for (const [a, b] of [[ids[t], ids[t + 1]], [ids[t + 1], ids[t + 2]], [ids[t + 2], ids[t]]]) {
    if (a === b) continue
    const lo = Math.min(a, b), hi = Math.max(a, b), key = lo * m + hi
    if (edges.has(key)) continue
    const dx = xs[lo * 3] - xs[hi * 3], dy = xs[lo * 3 + 1] - xs[hi * 3 + 1], dz = xs[lo * 3 + 2] - xs[hi * 3 + 2]
    edges.set(key, 1 / (dx * dx + dy * dy + dz * dz + 1e-8))
  }
  const ea = new Int32Array(edges.size), eb = new Int32Array(edges.size), ew = new Float64Array(edges.size)
  let e = 0
  for (const [key, w] of edges) { ea[e] = Math.floor(key / m); eb[e] = key - ea[e] * m; ew[e] = w; e++ }
  // the nearest segment and its heat at every vertex
  const near = new Int32Array(m), H = new Float64Array(m), diag = new Float64Array(m)
  for (let v = 0; v < m; v++) {
    p.set(xs[v * 3], xs[v * 3 + 1], xs[v * 3 + 2])
    let best = 0, d = Infinity
    segs.forEach((sg, k) => { const dk = pointSegment(p, sg.a, sg.b); if (dk < d) { d = dk; best = k } })
    near[v] = best; H[v] = 1 / (d * d + 1e-4)
  }
  for (let k = 0; k < ea.length; k++) { diag[ea[k]] += ew[k]; diag[eb[k]] += ew[k] }
  for (let v = 0; v < m; v++) diag[v] += H[v]
  const mul = (x: Float64Array, out: Float64Array) => {                    // (L + H) x
    for (let v = 0; v < m; v++) out[v] = diag[v] * x[v]
    for (let k = 0; k < ea.length; k++) { const a = ea[k], b = eb[k], w = ew[k]; out[a] -= w * x[b]; out[b] -= w * x[a] }
  }
  const W = segs.map((_, s) => {                                             // conjugate gradients, Jacobi-preconditioned
    const b = new Float64Array(m); for (let v = 0; v < m; v++) if (near[v] === s) b[v] = H[v]
    const x = new Float64Array(m); for (let v = 0; v < m; v++) x[v] = near[v] === s ? 1 : 0
    const r = new Float64Array(m), z = new Float64Array(m), q = new Float64Array(m), Ax = new Float64Array(m)
    mul(x, Ax); for (let v = 0; v < m; v++) { r[v] = b[v] - Ax[v]; z[v] = r[v] / diag[v] }
    const d = Float64Array.from(z)
    let rz = 0, bn = 0; for (let v = 0; v < m; v++) { rz += r[v] * z[v]; bn += b[v] * b[v] }
    for (let it = 0; it < maxIter; it++) {
      mul(d, q)
      let dq = 0; for (let v = 0; v < m; v++) dq += d[v] * q[v]
      const alpha = rz / Math.max(1e-30, dq)
      let rr = 0
      for (let v = 0; v < m; v++) { x[v] += alpha * d[v]; r[v] -= alpha * q[v]; rr += r[v] * r[v] }
      if (rr <= 1e-10 * bn) break
      let rz2 = 0; for (let v = 0; v < m; v++) { z[v] = r[v] / diag[v]; rz2 += r[v] * z[v] }
      const beta = rz2 / Math.max(1e-30, rz); rz = rz2
      for (let v = 0; v < m; v++) d[v] = z[v] + beta * d[v]
    }
    return x
  })
  // the four largest per joined vertex, normalised, onto every soup vertex
  const top = new Uint16Array(m * 4), topW = new Float32Array(m * 4)
  for (let v = 0; v < m; v++) {
    const order = W.map((w, s) => [Math.max(0, w[v]), s] as [number, number]).sort((a, b) => b[0] - a[0]).slice(0, 4)
    const sum = order.reduce((acc, [w]) => acc + w, 0) || 1
    order.forEach(([w, s], k) => { top[v * 4 + k] = s; topW[v * 4 + k] = sum > 0 ? w / sum : (k === 0 ? 1 : 0) })
    if (!order.some(([w]) => w > 0)) { top[v * 4] = near[v]; topW[v * 4] = 1 }
  }
  const idx = new Uint16Array(n * 4), wts = new Float32Array(n * 4)
  for (let i = 0; i < n; i++) for (let k = 0; k < 4; k++) { idx[i * 4 + k] = top[ids[i] * 4 + k]; wts[i * 4 + k] = topW[ids[i] * 4 + k] }
  return { idx, wts }
}

export interface Proxy {
  meshes: THREE.SkinnedMesh[]; dispose: () => void; segments: Segment[]; ms: number
  /** CS3 (06 §2.5): the pose pass's points as landmarks on the shell — each marker moved, in the bind pose, onto the shell's outermost
   *  surface along its ray within 25 cm (`front`: the nose, the eyes, the toes; `back`: the heels; `right` / `left`: the ears), where it
   *  stays with its joint; `now` is the figure's pose to return to; `follow` moves what follows the joints (the Detailed mannequin, which
   *  carries the feet's markers). Returns the undo. */
  landmark: (list: Landmark[], now: { preset?: string | null; joints?: Record<string, number[]>; ground?: number } | null, follow?: () => void) => () => void
}
export type Landmark = { m: THREE.Object3D; ray: 'front' | 'back' | 'right' | 'left' }
/** The COCO-18 markers SDPose reads on the surface: the nose and eyes from the front, the ears from the sides. */
export const FACE_LANDMARKS: [number, Landmark['ray']][] = [[0, 'front'], [14, 'front'], [15, 'front'], [16, 'right'], [17, 'left']]
/** detailed.ts's feet markers (each side's big toe, small toe, heel). */
export const FEET_LANDMARKS: Landmark['ray'][] = ['front', 'front', 'back', 'front', 'front', 'back']

/** CS2 (06 §2.4): whether a point lies inside a shell's volume as the front view sees it — between where a ray along −Z through it enters
 *  the shell and where it leaves. `meshes`: plain meshes on the bound geometry (the bind pose's world positions, E36's check). */
export function insideShell(meshes: THREE.Mesh[], p: THREE.Vector3): boolean {
  const hits = new THREE.Raycaster(new THREE.Vector3(p.x, p.y, p.z + 50), new THREE.Vector3(0, 0, -1)).intersectObjects(meshes, false)
  return hits.length > 0 && p.z <= hits[0].point.z + 1e-3 && p.z >= hits[hits.length - 1].point.z - 1e-3
}
export interface BindOptions {
  weights?: Weighting; stance?: Record<string, number[]> | null; visible?: boolean
  /** CS3 (06 §2.5): the character's hand rig draws the hands — the shell's own (Pixal3D's mittens) collapse into the wrists. */
  hands?: boolean
  /** D140: the points the figure was fitted to (its reference's) and the figure's 18 markers — with the GLB's figure box (the cut-out
   *  Pixal3D was given, `extras.loom2.figure_box`) the shell is placed by its picture. */
  points?: { pose?: number[][]; canvas?: number[] } | null; markers?: THREE.Object3D[]
}

/** D140: the shell's placement from its picture, in the figure's own frame (it faces +Z, its left at +X, its floor at y 0): the figure
 *  box's bottom — the soles — on the floor and SDPose's nose on the figure's nose, so a bun or a hat stands above the head as the picture
 *  has it and the arms where it has them (E36 scaled the shell from the floor to the head's top + 0.16 instead: the bench's overlay showed
 *  the dancer's arms 8 cm low under her bun). Not by the ankles: SDPose's sit ≈ 10 cm over the soles (the ankle bone, the shoe), the
 *  dummy's 4 cm. Null without a box, a nose or the markers. */
function placeByPicture(model: THREE.Object3D, box: THREE.Box3, figureRoot: THREE.Object3D, root: THREE.Object3D, opts: BindOptions): THREE.Matrix4 | null {
  const fb = (model.userData?.loom2 as { figure_box?: number[] } | undefined)?.figure_box
  const nose = opts.points?.pose?.[0]
  if (!fb || fb.length < 6 || !nose || (nose[2] ?? 0) < 0.3 || !opts.markers?.length) return null
  const inv = figureRoot.matrixWorld.clone().invert()
  const at = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3()).applyMatrix4(inv)
  const cv = opts.points?.canvas, kx = cv?.length === 2 ? cv[0] / fb[4] : 1, ky = cv?.length === 2 ? cv[1] / fb[5] : 1   // the fit's picture size against the matte's
  const [x0, y0, x1, y1] = [fb[0] * kx, fb[1] * ky, fb[2] * kx, fb[3] * ky]
  const n = at(opts.markers[0])
  const size = box.getSize(new THREE.Vector3())
  if (!(y1 > nose[1]) || n.y <= 0 || size.y < 1e-6) return null
  const k = n.y / (y1 - nose[1])                                             // metres per pixel: the nose's height over the soles
  const s = ((y1 - y0) * k) / size.y
  const x = n.x + ((x0 + x1) / 2 - nose[0]) * k                              // the picture's x runs as the figure's (facing the camera)
  return figureRoot.matrixWorld.clone().multiply(new THREE.Matrix4().compose(new THREE.Vector3(x, 0, at(root).z), new THREE.Quaternion(), new THREE.Vector3(s, s, s))
    .multiply(new THREE.Matrix4().makeTranslation(-(box.min.x + box.max.x) / 2, -box.min.y, -(box.min.z + box.max.z) / 2)))
}

/** The shell's hands into its wrists: a vertex whose nearest part is a forearm, beyond the wrist, within 25 cm of it and along the
 *  forearm's line (not a coat's side beside a hanging hand), moves to the wrist. */
export function collapseHands(pos: THREE.BufferAttribute, segs: Segment[]): number {
  const fore = segs.filter((g) => g.j === 'r_elbow' || g.j === 'l_elbow')
  const v = new THREE.Vector3(), d = new THREE.Vector3()
  let n = 0
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i)
    let best = Infinity, near: Segment | null = null
    for (const g of segs) { const dist = pointSegment(v, g.a, g.b); if (dist < best) { best = dist; near = g } }
    if (!near || !fore.includes(near)) continue
    const ab = near.b.clone().sub(near.a), L = ab.length()
    d.copy(v).sub(near.b)
    if (d.dot(ab) <= 0 || d.length() > 0.25 || d.angleTo(ab) > THREE.MathUtils.degToRad(50) || L < 1e-6) continue
    pos.setXYZ(i, near.b.x, near.b.y, near.b.z); n++
  }
  pos.needsUpdate = true
  return n
}

/** Bind `model` (a loaded GLB scene, not in the scene graph) to the figure; returns the skinned meshes, to be added to the scene's root.
 *  `stance`: the reference's (stanceOf; E23d's A-pose without it); `visible`: a clay material the cameras see (the shell, U6). */
export function bindProxy(model: THREE.Object3D, J: Record<Joint, THREE.Object3D>, limbs: Limbs, figureRoot: THREE.Object3D,
                          pose: { preset?: string | null; joints?: Record<string, number[]>; ground?: number } | null, opts: BindOptions = {}): Proxy {
  const t0 = performance.now()
  // the figure in the reference's stance, its world-space segments and extent
  applyPose(J, POSES.stand, opts.stance ?? A_POSE)
  figureRoot.updateMatrixWorld(true)
  const segs: Segment[] = JOINTS.map((j) => { const a = J[j].getWorldPosition(new THREE.Vector3()); const b = segmentEnd(j, limbs).applyMatrix4(J[j].matrixWorld); return { j, a, b } })
  const floorY = Math.min(...segs.map((s) => s.b.y)) - 0.03
  const topY = J.head.getWorldPosition(new THREE.Vector3()).y + 0.16
  const centre = J.root.getWorldPosition(new THREE.Vector3())
  const right = J.r_shoulder.getWorldPosition(new THREE.Vector3()).sub(J.l_shoulder.getWorldPosition(new THREE.Vector3())).setY(0).normalize()
  // the model: its own transforms baked, placed by its picture where it carries its figure box (D140, placeByPicture), else scaled from
  // the floor to the head's top + 0.16; turned onto the figure's facing. It is made from the front animation reference, so it faces +Z
  // with the character's left at +X: its +X goes onto the figure's left (−right). (E23d took the wider horizontal axis for the left-right
  // one; E36's Skink — a snout and a tail — is deeper than wide and was bound turned 90°.)
  model.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(model, true)                  // SC3d: its vertices (a turned box would overstate the height)
  const size = box.getSize(new THREE.Vector3()), mid = box.getCenter(new THREE.Vector3())
  const s = (topY - floorY) / Math.max(1e-6, size.y)
  const turn = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1, 0, 0), right.clone().negate())
  const place = placeByPicture(model, box, figureRoot, J.root, opts) ?? new THREE.Matrix4().compose(new THREE.Vector3(centre.x, floorY, centre.z), turn, new THREE.Vector3(s, s, s))
    .multiply(new THREE.Matrix4().makeTranslation(-mid.x, -box.min.y, -mid.z))
  const bones = JOINTS.map((j) => J[j])
  const skeleton = new THREE.Skeleton(bones as unknown as THREE.Bone[])
  skeleton.calculateInverses()                                             // the bind pose: the stance, now
  const material = opts.visible ? new THREE.MeshLambertMaterial({ color: 0xb4b4b8 }) : new THREE.MeshBasicMaterial({ color: 0x888888, colorWrite: false, depthWrite: false })
  const meshes: THREE.SkinnedMesh[] = []
  model.traverse((o) => {
    const m = o as THREE.Mesh
    if (!m.isMesh || !m.geometry) return
    const g = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone())
    g.applyMatrix4(place.clone().multiply(m.matrixWorld))
    for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal' && !(opts.visible && k === 'color')) g.deleteAttribute(k)
    if (opts.hands) collapseHands(g.attributes.position as THREE.BufferAttribute, segs)
    const { idx, wts } = (opts.weights ?? 'heat') === 'heat' ? heatWeights(g.attributes.position, segs) : proximityWeights(g.attributes.position, segs)
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4))
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(wts, 4))
    const sm = new THREE.SkinnedMesh(g, material)
    sm.bind(skeleton, new THREE.Matrix4())
    sm.castShadow = true; sm.receiveShadow = !!opts.visible
    sm.frustumCulled = false
    sm.userData.proxy = !opts.visible
    meshes.push(sm)
  })
  const ms = performance.now() - t0
  // back to the figure's own pose
  applyPose(J, POSES[pose?.preset ?? 'stand'] ?? POSES.stand, pose?.joints, pose?.ground ?? 0)
  figureRoot.updateMatrixWorld(true)
  const landmark = (list: Landmark[], now: { preset?: string | null; joints?: Record<string, number[]>; ground?: number } | null, follow?: () => void) => {
    applyPose(J, POSES.stand, opts.stance ?? A_POSE)                       // the bind pose: the geometry's own positions
    figureRoot.updateMatrixWorld(true); follow?.(); figureRoot.updateMatrixWorld(true)
    const plain = meshes.map((m) => new THREE.Mesh(m.geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })))
    const side = J.r_shoulder.getWorldPosition(new THREE.Vector3()).sub(J.l_shoulder.getWorldPosition(new THREE.Vector3())).setY(0).normalize()   // the figure's right
    const fwd = new THREE.Vector3(0, 1, 0).cross(side).normalize()
    const out = { front: fwd, back: fwd.clone().negate(), right: side, left: side.clone().negate() }
    const before = list.map(({ m }) => m.position.clone())
    const ray = new THREE.Raycaster()
    for (const { m, ray: r } of list) {
      const p = m.getWorldPosition(new THREE.Vector3()), o = out[r]
      ray.set(p.clone().addScaledVector(o, 0.5), o.clone().negate())
      const hits = ray.intersectObjects(plain, false).filter((h) => h.point.distanceTo(p) < 0.25)
      if (!hits.length) continue
      const top = hits.reduce((a, h) => (h.point.clone().sub(p).dot(o) > a.point.clone().sub(p).dot(o) ? h : a))   // the outermost surface that way
      m.position.copy(m.parent!.worldToLocal(top.point.clone()))
    }
    plain.forEach((m) => (m.material as THREE.Material).dispose())
    applyPose(J, POSES[now?.preset ?? 'stand'] ?? POSES.stand, now?.joints, now?.ground ?? 0)
    figureRoot.updateMatrixWorld(true); follow?.(); figureRoot.updateMatrixWorld(true)
    return () => list.forEach(({ m }, i) => { m.position.copy(before[i]) })
  }
  return { meshes, segments: segs, ms, landmark, dispose: () => { for (const m of meshes) { m.geometry.dispose(); m.removeFromParent() } material.dispose() } }
}
