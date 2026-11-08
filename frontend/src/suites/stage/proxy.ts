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

/** The hand's length past the wrist on the forearm's segment (segmentEnd: the hand rides on the forearm). */
export const HAND_M = 0.18

/** Each joint's segment, from the joint to where its part ends, in the joint's own frame (−Y down the limb). */
function segmentEnd(j: Joint, limbs: Limbs): THREE.Vector3 {
  switch (j) {
    case 'r_shoulder': case 'l_shoulder': return new THREE.Vector3(0, -limbs.upper_arm, 0)
    case 'r_elbow': case 'l_elbow': return new THREE.Vector3(0, -limbs.forearm - HAND_M, 0)       // the hand rides on the forearm
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
  /** D191: how far the shell was moved along the figure's facing to sit on its joints (metres, + ahead). */
  depth: number
  /** RG2b: the shoe's ankle and ball turned by a pose's extra (r_ankle, r_ball, l_ankle, l_ball; degrees, toes down + at the ankle, up + at
   *  the ball); nothing without a rigged foot. `points` the rig's ankle, ball and toe a foot (world, at bind) for the tests and the bench. */
  feet: (extra?: Record<string, number[]> | null) => void
  footPoints: Partial<Record<'r' | 'l', { ankle: THREE.Vector3; ball: THREE.Vector3 | null; toe: THREE.Vector3; heel: THREE.Vector3; rigged: boolean; missed: number }>>
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
/** D191: how far to move a shell along the figure's facing (metres, + ahead) so that the most of `points` (the joints, in the figure's frame)
 *  lie inside it as insideShell sees it — between where a line along the figure's depth through each enters the shell and leaves it — the
 *  move centred among them (the largest least margin), the smallest move among equals; 0 when no line meets the shell. `geoms` are placed
 *  (world), `toFigure` takes the world into the figure's frame. */
export function depthFit(geoms: THREE.BufferGeometry[], points: THREE.Vector3[], toFigure: THREE.Matrix4, reach = 0.35): number {
  const front = points.map(() => -Infinity), back = points.map(() => Infinity)
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3()
  for (const g of geoms) {
    const pos = g.attributes.position
    for (let i = 0; i + 2 < pos.count; i += 3) {
      a.fromBufferAttribute(pos, i).applyMatrix4(toFigure); b.fromBufferAttribute(pos, i + 1).applyMatrix4(toFigure); c.fromBufferAttribute(pos, i + 2).applyMatrix4(toFigure)
      const x0 = Math.min(a.x, b.x, c.x), x1 = Math.max(a.x, b.x, c.x), y0 = Math.min(a.y, b.y, c.y), y1 = Math.max(a.y, b.y, c.y)
      const det = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
      if (Math.abs(det) < 1e-14) continue                                      // edge-on to the depth: no crossing
      for (let k = 0; k < points.length; k++) {
        const p = points[k]
        if (p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) continue
        const u = ((b.y - c.y) * (p.x - c.x) + (c.x - b.x) * (p.y - c.y)) / det, v = ((c.y - a.y) * (p.x - c.x) + (a.x - c.x) * (p.y - c.y)) / det, w = 1 - u - v
        if (u < 0 || v < 0 || w < 0) continue
        const z = u * a.z + v * b.z + w * c.z
        if (z > front[k]) front[k] = z
        if (z < back[k]) back[k] = z
      }
    }
  }
  // the shell moved by s holds point k when back + s ≤ z ≤ front + s: s within [z − front, z − back]
  const spans = points.map((p, k) => (front[k] > back[k] ? [p.z - front[k], p.z - back[k]] : null)).filter((x): x is number[] => !!x)
  if (!spans.length) return 0
  let best = { n: -1, margin: -Infinity, s: 0 }
  for (let s = -reach; s <= reach + 1e-9; s += 0.002) {
    let n = 0, margin = Infinity
    for (const [lo, hi] of spans) if (s >= lo && s <= hi) { n++; margin = Math.min(margin, s - lo, hi - s) }
    if (n > best.n || (n === best.n && (margin > best.margin + 1e-6 || (Math.abs(margin - best.margin) <= 1e-6 && Math.abs(s) < Math.abs(best.s))))) best = { n, margin, s }
  }
  return Math.round(best.s * 1000) / 1000
}

/** RG2b (D188 F2, F3; D189): a foot's shape as the version keeps it (hands.FootShape) — in foot lengths, seen from the side. */
export interface FootShape { pitch: number; ankle_up: number; ankle_at: number; heel_up: number; toe_up: number; ball_at: number; length_leg: number | null; stiff?: boolean
  /** RG3 (F4): the heel, the ball and the toe placed by hand — metres from the ankle in the figure's frame (+x its left, +z ahead), the
   *  right foot's; the left mirrored while linked. Trusted: the shoe is rigged to them without the reach check. */
  place?: { heel: number[]; ball: number[]; toe: number[] } | Record<string, number[]> | null }
export interface FootShapes { right: FootShape; left?: FootShape | null }
/** RG2b: a foot's length when its shape was not read on a whole figure — this share of the leg (hip → ankle) at ×1 feet (a 0.87 m leg, 26 cm). */
export const FOOT_PER_LEG = 0.3
/** RG2b: how near the shell's surface a placed foot's ball and toe must lie for its shoe to be rigged (metres). */
export const FOOT_REACH = 0.06
/** Review K113: the shoe bent (`bend` turns the foot's bones) — each of the foot's points' move from the shoe as it stands: the heel and the
 *  ball ride the ankle's bone, the toe the ball's (a stiff sole's: the ankle's). The view drew the points where the flat shoe has them. */
export function bentFoot(root: THREE.Object3D, side: 'r' | 'l', bend: () => void): Record<'heel' | 'ball' | 'toe', THREE.Matrix4> {
  const ankle = root.getObjectByName(`${side}_ankle_rig`), ball = root.getObjectByName(`${side}_ball_rig`)
  root.updateMatrixWorld(true)
  const was = { ankle: ankle?.matrixWorld.clone(), ball: ball?.matrixWorld.clone() }
  bend(); root.updateMatrixWorld(true)
  const moved = (o: THREE.Object3D | undefined, w: THREE.Matrix4 | undefined) => (o && w ? o.matrixWorld.clone().multiply(w.clone().invert()) : new THREE.Matrix4())
  const ma = moved(ankle, was.ankle)
  return { heel: ma, ball: ma, toe: ball ? moved(ball, was.ball) : ma }
}
export interface BindOptions {
  weights?: Weighting; stance?: Record<string, number[]> | null; visible?: boolean
  /** CS3 (06 §2.5): the character's hand rig draws the hands — the shell's own (Pixal3D's mittens) collapse into the wrists. */
  hands?: boolean
  /** D140: the points the figure was fitted to (its reference's) and the figure's 18 markers — with the GLB's figure box (the cut-out
   *  Pixal3D was given, `extras.loom2.figure_box`) the shell is placed by its picture. */
  points?: { pose?: number[][]; canvas?: number[]; hand_left?: number[][]; hand_right?: number[][] } | null; markers?: THREE.Object3D[]
  /** RG2b (D188 F3): the character's own feet — the shell's shoe rigged at an ankle and a ball placed from them (a stiff sole at the ankle
   *  alone), turned by a pose's r_ankle / r_ball (feet()); `size` the body's feet factor. Without, the shoe rides on the shin as before. */
  feet?: { shape: FootShapes; size?: number } | null
}

/** D140: the shell's placement from its picture, in the figure's own frame (it faces +Z, its left at +X, its floor at y 0): the figure
 *  box's bottom — the soles — on the floor and SDPose's nose on the figure's nose, so a bun or a hat stands above the head as the picture
 *  has it and the arms where it has them (E36 scaled the shell from the floor to the head's top + 0.16 instead: the bench's overlay showed
 *  the dancer's arms 8 cm low under her bun). Not by the ankles: SDPose's sit ≈ 10 cm over the soles (the ankle bone, the shoe), the
 *  dummy's 4 cm. Null without a box, a nose or the markers. */
function pictureFrame(model: THREE.Object3D, figureRoot: THREE.Object3D, root: THREE.Object3D, opts: BindOptions): PictureFrame | null {
  const fb = (model.userData?.loom2 as { figure_box?: number[] } | undefined)?.figure_box
  const nose = opts.points?.pose?.[0]
  if (!fb || fb.length < 6 || !nose || (nose[2] ?? 0) < 0.3 || !opts.markers?.length) return null
  const inv = figureRoot.matrixWorld.clone().invert()
  const at = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3()).applyMatrix4(inv)
  const cv = opts.points?.canvas, kx = cv?.length === 2 ? cv[0] / fb[4] : 1, ky = cv?.length === 2 ? cv[1] / fb[5] : 1   // the fit's picture size against the matte's
  const [x0, y0, x1, y1] = [fb[0] * kx, fb[1] * ky, fb[2] * kx, fb[3] * ky]
  const n = at(opts.markers[0])
  if (!(y1 > nose[1]) || n.y <= 0) return null
  const k = n.y / (y1 - nose[1])                                             // metres per pixel: the nose's height over the soles
  const z = at(root).z
  return { box: [x0, y0, x1, y1], k, toFigure: (px, py) => new THREE.Vector3(n.x + (px - nose[0]) * k, (y1 - py) * k, z) }   // the picture's x runs as the figure's (facing the camera)
}
/** D140: the picture's pixels in the figure's own frame — the nose on the figure's nose, the soles on its floor, `k` metres a pixel. */
interface PictureFrame { box: number[]; k: number; toFigure: (px: number, py: number) => THREE.Vector3 }

function placeByPicture(pf: PictureFrame | null, box: THREE.Box3, figureRoot: THREE.Object3D): THREE.Matrix4 | null {
  const size = box.getSize(new THREE.Vector3())
  if (!pf || size.y < 1e-6) return null
  const [x0, y0, x1, y1] = pf.box
  const s = ((y1 - y0) * pf.k) / size.y
  const c = pf.toFigure((x0 + x1) / 2, y1)
  return figureRoot.matrixWorld.clone().multiply(new THREE.Matrix4().compose(new THREE.Vector3(c.x, 0, c.z), new THREE.Quaternion(), new THREE.Vector3(s, s, s))
    .multiply(new THREE.Matrix4().makeTranslation(-(box.min.x + box.max.x) / 2, -box.min.y, -(box.min.z + box.max.z) / 2)))
}

/** The hands of the shell's own picture as regions of the figure's picture plane (its x, y): each hand's keypoints (SDPose wholebody,
 *  21 a hand, the wrist first) seen with confidence, their convex hull grown by `margin` around the wrist and by `far` beyond it, toward
 *  the fingers — the keypoints are the joints' centres and Pixal3D's hands are fuller (on Followed the man's hangs 5 cm below its outline,
 *  Nora's 3.5 cm), while the sleeve's cuff behind the wrist is kept. A predicate on a point of the figure's frame (its z is not read: the
 *  hands' depth is the shell's own). Null without a hand's points. */
export function handRegion(hands: (number[][] | undefined)[], toFigure: (px: number, py: number) => THREE.Vector3, margin = 0.03, far = 0.07): ((p: THREE.Vector3) => boolean) | null {
  const regions = hands.map((pts) => (pts ?? []).filter((q) => (q[2] ?? 0) >= 0.3).map((q) => { const v = toFigure(q[0], q[1]); return [v.x, v.y] as [number, number] }))
    .filter((pts) => pts.length >= 5).map((pts) => {
      const w = pts[0], cx = pts.reduce((a, q) => a + q[0], 0) / pts.length, cy = pts.reduce((a, q) => a + q[1], 0) / pts.length
      const L = Math.hypot(cx - w[0], cy - w[1]) || 1
      return { hull: hull2d(pts), w, dir: [(cx - w[0]) / L, (cy - w[1]) / L] }                  // the wrist and the way the hand points
    })
  if (!regions.length) return null
  return (p) => regions.some(({ hull, w, dir }) => {
    if (inside2d(hull, p.x, p.y)) return true
    const e = edge2d(hull, p.x, p.y)
    return e <= margin || (e <= far && (p.x - w[0]) * dir[0] + (p.y - w[1]) * dir[1] > 0)
  })
}
function hull2d(pts: [number, number][]): [number, number][] {                // Andrew's monotone chain
  const a = [...pts].sort((m, n) => m[0] - n[0] || m[1] - n[1])
  const cross = (o: number[], p: number[], q: number[]) => (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
  const lower: [number, number][] = [], upper: [number, number][] = []
  for (const p of a) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop(); lower.push(p) }
  for (const p of [...a].reverse()) { while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop(); upper.push(p) }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)]
}
function inside2d(h: [number, number][], x: number, y: number): boolean {
  if (h.length < 3) return false
  let sign = 0
  for (let i = 0; i < h.length; i++) {
    const [ax, ay] = h[i], [bx, by] = h[(i + 1) % h.length]
    const c = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    if (c !== 0) { if (sign === 0) sign = Math.sign(c); else if (Math.sign(c) !== sign) return false }
  }
  return true
}
function edge2d(h: [number, number][], x: number, y: number): number {
  let best = Infinity
  for (let i = 0; i < h.length; i++) {
    const [ax, ay] = h[i], [bx, by] = h[(i + 1) % h.length], dx = bx - ax, dy = by - ay
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / Math.max(1e-12, dx * dx + dy * dy)))
    best = Math.min(best, Math.hypot(x - (ax + t * dx), y - (ay + t * dy)))
  }
  return best
}

/** The shell's hands into the skeleton's wrists, where the hand rig's hands are drawn (CS3). A vertex whose nearest part is a forearm
 *  moves to that forearm's wrist when it is in `inHand` — the hands of the shell's own picture (handRegion: its keypoints' outline, so
 *  exactly the hand wherever the fitted skeleton's wrist sits) — or, without the picture's hands, when it is beyond the wrist, within
 *  25 cm of it and along the forearm's line (not a coat's side beside a hanging hand). The first fold folded nothing (the author,
 *  2026-11-04: "the clay shells have 2 hands"): the forearm's segment ends at the fingertips (the hand rides on it, HAND_M) while it
 *  measured "beyond" from that end; the skeleton is fitted flat in the picture's plane while the shell's hands have depth (Nora's reach
 *  19 cm in front of it, the man's 29) — so the line is measured in that plane, `depth` being the figure's facing axis (its local +z in
 *  the world), and the depth itself only bounded; and the shell's own wrist is not the skeleton's (Nora's hand starts 5 cm before it,
 *  the man's at it), which only the picture's hands tell. */
const DEPTH_M = 0.3
const HAND_DEPTH_M = 0.4                                                       // the picture's hands: a hand reaching forward (the man's, 29 cm)
export function collapseHands(pos: THREE.BufferAttribute, segs: Segment[], depth?: THREE.Vector3, inHand?: ((world: THREE.Vector3) => boolean) | null): number {
  const fore = segs.filter((g) => g.j === 'r_elbow' || g.j === 'l_elbow')
  const v = new THREE.Vector3(), d = new THREE.Vector3(), wrist = new THREE.Vector3(), axis = new THREE.Vector3()
  const flat = (x: THREE.Vector3) => (depth ? x.addScaledVector(depth, -x.dot(depth)) : x)       // into the picture's plane
  let n = 0
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i)
    let best = Infinity, near: Segment | null = null
    for (const g of segs) { const dist = pointSegment(v, g.a, g.b); if (dist < best) { best = dist; near = g } }
    if (!near || !fore.includes(near)) continue
    const ab = near.b.clone().sub(near.a), L = ab.length()
    if (L < 1e-6) continue
    wrist.copy(near.b).addScaledVector(ab, -Math.min(HAND_M, L * 0.5) / L)            // the wrist: the hand's length back from the segment's end
    d.copy(v).sub(wrist)
    if (depth && Math.abs(d.dot(depth)) > (inHand ? HAND_DEPTH_M : DEPTH_M)) continue
    if (inHand) {                                                              // the picture's hands known: exactly what they cover, wherever the skeleton's wrist sits
      if (!inHand(v)) continue
      pos.setXYZ(i, wrist.x, wrist.y, wrist.z); n++
      continue
    }
    flat(d); flat(axis.copy(ab))
    if (d.dot(axis) <= 0 || d.length() > 0.25 || d.angleTo(axis) > THREE.MathUtils.degToRad(50)) continue
    pos.setXYZ(i, wrist.x, wrist.y, wrist.z); n++
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
  const pf = pictureFrame(model, figureRoot, J.root, opts)
  const place = placeByPicture(pf, box, figureRoot) ?? new THREE.Matrix4().compose(new THREE.Vector3(centre.x, floorY, centre.z), turn, new THREE.Vector3(s, s, s))
    .multiply(new THREE.Matrix4().makeTranslation(-mid.x, -box.min.y, -mid.z))
  const region = opts.hands && pf ? handRegion([opts.points?.hand_left, opts.points?.hand_right], pf.toFigure) : null   // the shell's own hands, from its picture
  const toFig = figureRoot.matrixWorld.clone().invert(), tmp = new THREE.Vector3()
  const inHand = region ? (w: THREE.Vector3) => region(tmp.copy(w).applyMatrix4(toFig)) : null
  const placed: THREE.BufferGeometry[] = []                                // the shell's geometry, placed (and its mittens folded), before weighting
  model.traverse((o) => {
    const m = o as THREE.Mesh
    if (!m.isMesh || !m.geometry) return
    const g = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone())
    g.applyMatrix4(place.clone().multiply(m.matrixWorld))
    for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal' && !(opts.visible && k === 'color')) g.deleteAttribute(k)
    placed.push(g)
  })
  // D191: the depth — the front places the shell by its picture, but its depth was its box's middle, which hands held forward pull forward
  // (char01's shell sat 12 cm behind its skeleton, 9 joints outside it); it is set where the most joints lie inside it, centred among them
  const facing = new THREE.Vector3(0, 0, 1).transformDirection(figureRoot.matrixWorld)   // the figure faces its +z
  const toFigure = figureRoot.matrixWorld.clone().invert()
  const inner = [...JOINTS.map((j) => J[j]), ...[10, 13].map((k) => opts.markers?.[k]).filter((x): x is THREE.Object3D => !!x)]
    .map((o) => o.getWorldPosition(new THREE.Vector3()).applyMatrix4(toFigure))
  const depth = depthFit(placed, inner, toFigure)
  if (depth) { const t = facing.clone().multiplyScalar(depth); for (const g of placed) g.translate(t.x, t.y, t.z) }
  if (opts.hands) for (const g of placed) collapseHands(g.attributes.position as THREE.BufferAttribute, segs, facing, inHand)
  const reach = (p: THREE.Vector3): number => {                            // how far the shell's surface is from a point
    let best = Infinity
    const v = new THREE.Vector3()
    for (const g of placed) { const a = g.attributes.position; for (let i = 0; i < a.count; i++) { const d2 = v.fromBufferAttribute(a, i).distanceToSquared(p); if (d2 < best) best = d2 } }
    return Math.sqrt(best)
  }
  // RG2b (D188 F2, F3): the shoe rigged — an ankle at the shin's end (the figure's ankle marker, placed by hand when D183 placed it) and a
  // ball, both from the foot's shape in foot lengths; the shin's segment then ends at the ankle, the foot's two (one for a stiff sole, D189)
  // follow it; bone heat weighs the shoe to them as to the rest (E62 c: 99th-percentile stretch 1.02–1.24 at 30° where the points sit right).
  // Only where the foot so placed lands on the shell — its ball and toe within FOOT_REACH of its surface: under a robe or a trouser hem, or a
  // foot turned out or splayed (the ghoul's: its low geometry 13 cm outward and behind the ankle), the points miss the shoe (E62 c), the
  // shoe would hang on the ankle alone, and it rides on the shin as before until its foot is placed by hand (RG3, the Feet & legs view)
  const footRig: { side: 'r' | 'l'; ankle: THREE.Bone; ball: THREE.Bone | null; axis: THREE.Vector3 }[] = []
  const footPoints: Proxy['footPoints'] = {}
  const extraSegs: Segment[] = []
  if (opts.feet?.shape) {
    const fwd = new THREE.Vector3(0, 0, 1).transformDirection(figureRoot.matrixWorld).setY(0)
    if (fwd.lengthSq() < 1e-10) fwd.set(0, 0, 1)
    fwd.normalize()
    const floor = new THREE.Vector3().applyMatrix4(figureRoot.matrixWorld).y
    const down = new THREE.Vector3(0, -1, 0), across = fwd.clone().cross(down).normalize()
    for (const side of ['r', 'l'] as const) {
      const shape = side === 'l' && opts.feet.shape.left ? opts.feet.shape.left : opts.feet.shape.right
      const knee = J[side === 'r' ? 'r_knee' : 'l_knee'], hip = J[side === 'r' ? 'r_hip' : 'l_hip']
      const marker = opts.markers?.[side === 'r' ? 10 : 13]
      const A = marker ? marker.getWorldPosition(new THREE.Vector3()) : new THREE.Vector3(0, -limbs.shin, 0).applyMatrix4(knee.matrixWorld)
      const kneeW = knee.getWorldPosition(new THREE.Vector3())
      const leg = hip.getWorldPosition(new THREE.Vector3()).distanceTo(kneeW) + kneeW.distanceTo(A)
      // the foot's length: the shell's own sole when it has one in the foot's corridor (on the floor, within 6 cm of the ankle's line, ahead —
      // E62 c found Nora's toe so), the toe at its 98th percentile ahead; else from the shape (on a whole figure) or the leg
      const ahead: number[] = []
      const rel = new THREE.Vector3()
      for (const g of placed) { const a = g.attributes.position; for (let i = 0; i < a.count; i++) {
        rel.fromBufferAttribute(a, i).sub(A)
        const t = rel.dot(fwd)
        if (rel.y + A.y < floor + 0.025 && Math.abs(rel.dot(across)) < 0.06 && t > 0 && t < 0.45) ahead.push(t)   // a sole touches the floor (a hem does not)
      } }
      ahead.sort((x, y) => x - y)
      const toeAhead = ahead.length >= 20 ? ahead[Math.floor(0.98 * (ahead.length - 1))] : 0
      const L = toeAhead > 0.03 ? toeAhead / Math.max(0.3, 1 - shape.ankle_at) : shape.length_leg ? shape.length_leg * leg : FOOT_PER_LEG * leg * (opts.feet.size ?? 1)
      const heel = A.clone().addScaledVector(fwd, -shape.ankle_at * L); heel.y = floor + shape.heel_up * L
      const toe = heel.clone().addScaledVector(fwd, L); toe.y = floor + shape.toe_up * L
      const ballP = heel.clone().lerp(toe, shape.ball_at); ballP.y = floor + 0.03
      const place = shape.place as Record<'heel' | 'ball' | 'toe', number[]> | null | undefined
      if (place?.heel && place.ball && place.toe) {                          // RG3 (F4): placed by hand on the shell — the author's, trusted
        const q = figureRoot.getWorldQuaternion(new THREE.Quaternion())
        const at = (k: 'heel' | 'ball' | 'toe') => { const o = new THREE.Vector3(...place[k]); if (side === 'l' && !opts.feet?.shape.left) o.x = -o.x; return A.clone().add(o.applyQuaternion(q)) }
        heel.copy(at('heel')); ballP.copy(at('ball')); toe.copy(at('toe'))
      }
      // D191: a placed foot measured too (the shell may have moved since it was placed): near the surface, and its toe at the sole's tip
      const missed = Math.max(reach(toe), reach(ballP), place?.heel && toeAhead > 0.03 ? Math.abs(toe.clone().sub(A).dot(fwd) - toeAhead) : 0)
      if (!place?.heel && missed > FOOT_REACH) { footPoints[side] = { ankle: A.clone(), ball: ballP.clone(), toe: toe.clone(), heel: heel.clone(), rigged: false, missed }; continue }
      const k = segs.findIndex((g) => g.j === knee.name || g.j === (side === 'r' ? 'r_knee' : 'l_knee'))
      if (k >= 0) segs[k] = { ...segs[k], b: A.clone() }
      knee.updateMatrixWorld(true)
      const ankle = new THREE.Bone(); ankle.name = `${side}_ankle_rig`; knee.add(ankle); ankle.position.copy(knee.worldToLocal(A.clone()))
      ankle.updateMatrixWorld(true)
      const way = toe.clone().sub(heel).setY(0)                              // the foot's own way (a placed foot may turn out)
      const side2side = way.lengthSq() > 1e-6 ? way.normalize().cross(down).normalize() : across
      const axis = side2side.clone().applyQuaternion(ankle.getWorldQuaternion(new THREE.Quaternion()).invert())   // the side-to-side axis, in its frame
      let ball: THREE.Bone | null = null
      if (shape.stiff) extraSegs.push({ j: side === 'r' ? 'r_knee' : 'l_knee', a: A.clone(), b: toe.clone() })
      else {
        ball = new THREE.Bone(); ball.name = `${side}_ball_rig`; ankle.add(ball); ball.position.copy(ankle.worldToLocal(ballP.clone())); ball.updateMatrixWorld(true)
        extraSegs.push({ j: side === 'r' ? 'r_knee' : 'l_knee', a: A.clone(), b: ballP.clone() }, { j: side === 'r' ? 'r_knee' : 'l_knee', a: ballP.clone(), b: toe.clone() })
      }
      footRig.push({ side, ankle, ball, axis })
      footPoints[side] = { ankle: A.clone(), ball: ball ? ballP.clone() : null, toe: toe.clone(), heel: heel.clone(), rigged: true, missed }
    }
  }
  const footBones = footRig.flatMap((f) => (f.ball ? [f.ankle, f.ball] : [f.ankle]))
  const bones = [...JOINTS.map((j) => J[j]), ...footBones]
  const skeleton = new THREE.Skeleton(bones as unknown as THREE.Bone[])
  skeleton.calculateInverses()                                             // the bind pose: the stance, now
  const material = opts.visible ? new THREE.MeshLambertMaterial({ color: 0xb4b4b8 }) : new THREE.MeshBasicMaterial({ color: 0x888888, colorWrite: false, depthWrite: false })
  const meshes: THREE.SkinnedMesh[] = []
  for (const g of placed) {
    const all = [...segs, ...extraSegs]                                      // RG2b: the feet's segments after the twelve, as their bones are
    const { idx, wts } = (opts.weights ?? 'heat') === 'heat' ? heatWeights(g.attributes.position, all) : proximityWeights(g.attributes.position, all)
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4))
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(wts, 4))
    const sm = new THREE.SkinnedMesh(g, material)
    sm.bind(skeleton, new THREE.Matrix4())
    sm.castShadow = true; sm.receiveShadow = !!opts.visible
    sm.frustumCulled = false
    sm.userData.proxy = !opts.visible
    meshes.push(sm)
  }
  const ms = performance.now() - t0
  // back to the figure's own pose
  applyPose(J, POSES[pose?.preset ?? 'stand'] ?? POSES.stand, pose?.joints, pose?.ground ?? 0)
  figureRoot.updateMatrixWorld(true)
  const landmark = (list: Landmark[], now: { preset?: string | null; joints?: Record<string, number[]>; ground?: number } | null, follow?: () => void) => {
    applyPose(J, POSES.stand, opts.stance ?? A_POSE)                       // the bind pose: the geometry's own positions
    feet(null)                                                             // RG2b: the shoe at its bind too
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
  const rad = THREE.MathUtils.degToRad
  const feet = (extra?: Record<string, number[]> | null) => {
    for (const f of footRig) {
      f.ankle.quaternion.setFromAxisAngle(f.axis, rad(extra?.[`${f.side}_ankle`]?.[0] ?? 0))
      f.ball?.quaternion.setFromAxisAngle(f.axis.clone().negate(), rad(extra?.[`${f.side}_ball`]?.[0] ?? 0))   // toes up +
    }
  }
  return { meshes, segments: segs, ms, landmark, feet, footPoints, depth,
    dispose: () => { for (const m of meshes) { m.geometry.dispose(); m.removeFromParent() } for (const f of footRig) f.ankle.removeFromParent(); material.dispose() } }
}
