// proto01_UIcast CW6 (04 §3 step 4; D143): the set builder's picture view — the set's edges over its picture, from the camera it was
// matched to, and the drags that fit it the fSpy way with the lens and the camera held: a wall's foot dragged along the floor moves that
// wall, a wall's top dragged up or down sets the height. After a drag the set is centred again (placeSet.ts lays every kind out about its
// origin), the camera moved with it. The camera's height scales the whole fit (MoGe's scale runs short, D143). Pure.
import * as THREE from 'three'
import { vfovFor } from './builders'
import { SET_KIND_SIZES, setFaces, type PlaceSetDoc, type SetKind } from './placeSet'

export interface SourceCam { pos: number[]; target: number[]; roll: number; focal_mm: number; sensor_mm: number }
/** A face's outline in the picture: points in pixels of a `w` × `h` picture (y down); empty when the face is behind the camera. */
export interface Outline { id: string; points: [number, number][] }
/** An edge the author drags: a wall's foot (moves the wall along `axis`) or its top (the height). `a`, `b` in picture pixels. */
export interface Handle { id: string; face: string; edge: 'foot' | 'top'; axis: 'x' | 'z' | 'y'; side: 'min' | 'max'; size?: string; a: [number, number]; b: [number, number]; assumed: boolean }
export interface Extents { x0: number; x1: number; z0: number; z1: number }

const MIN_SIZE = 0.5
const NEAR = 0.05

/** The picture's camera, as Stage builds a shot camera. */
export function sourceCamera(cam: SourceCam, aspect: number): THREE.PerspectiveCamera {
  const c = new THREE.PerspectiveCamera(vfovFor(cam.focal_mm, cam.sensor_mm, aspect), aspect, NEAR, 500)
  c.position.set(cam.pos[0], cam.pos[1], cam.pos[2]); c.up.set(0, 1, 0); c.lookAt(cam.target[0], cam.target[1], cam.target[2])
  c.rotateZ(THREE.MathUtils.degToRad(cam.roll)); c.updateProjectionMatrix(); c.updateMatrixWorld()
  return c
}

const sizesOf = (ps: PlaceSetDoc) => ({ ...SET_KIND_SIZES[ps.kind], ...ps.sizes })

/** The set's floor plan about its origin (a room's, a corridor's or a street's walls); null for open ground. */
export function extents(ps: PlaceSetDoc): Extents | null {
  const s = sizesOf(ps)
  if (ps.kind === 'ground') return null
  const w = s.width, d = ps.kind === 'room' ? s.depth : s.length
  return { x0: -w / 2, x1: w / 2, z0: -d / 2, z1: d / 2 }
}

/** A polygon in world space clipped to what lies in front of the camera, then projected to picture pixels. */
function project(pts: THREE.Vector3[], c: THREE.PerspectiveCamera, w: number, h: number): [number, number][] {
  const view = pts.map((p) => p.clone().applyMatrix4(c.matrixWorldInverse))
  const out: THREE.Vector3[] = []
  for (let i = 0; i < view.length; i++) {                                  // Sutherland–Hodgman against z = −near (the camera looks down −Z)
    const a = view[i], b = view[(i + 1) % view.length]
    const ina = a.z <= -NEAR, inb = b.z <= -NEAR
    if (ina) out.push(a)
    if (ina !== inb) out.push(a.clone().lerp(b, (-NEAR - a.z) / (b.z - a.z)))
  }
  return out.map((p) => {
    const n = p.clone().applyMatrix4(c.projectionMatrix)
    return [+((n.x * 0.5 + 0.5) * w).toFixed(2), +((0.5 - n.y * 0.5) * h).toFixed(2)] as [number, number]
  })
}

/** Every face of the set outlined over the picture (w × h pixels). */
export function outlines(ps: PlaceSetDoc, cam: SourceCam, w: number, h: number): Outline[] {
  const c = sourceCamera(cam, w / h)
  return setFaces(ps).map((f) => {
    const corners = [f.origin.clone(), f.origin.clone().addScaledVector(f.u, f.w), f.origin.clone().addScaledVector(f.u, f.w).addScaledVector(f.v, f.h), f.origin.clone().addScaledVector(f.v, f.h)]
    return { id: f.id, points: project(corners, c, w, h) }
  })
}

const inFrame = ([x, y]: [number, number], w: number, h: number) => x >= -1 && x <= w + 1 && y >= -1 && y <= h + 1

/** The edges to drag, as they lie on the picture — only those it shows; `assumed` (the fit's names) marks the ones it guessed (D143: those
 *  are offered first, dashed). */
export function handles(ps: PlaceSetDoc, cam: SourceCam, w: number, h: number, assumed: string[] = []): Handle[] {
  const e = extents(ps)
  if (!e) return []
  const s = sizesOf(ps)
  const street = ps.kind === 'street'
  const c = sourceCamera(cam, w / h)
  const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z)
  const out: Handle[] = []
  const add = (id: string, face: string, edge: Handle['edge'], axis: Handle['axis'], side: Handle['side'], p: THREE.Vector3, q: THREE.Vector3, name: string, size?: string) => {
    const seg = segment(p, q, c, w, h)
    if (!seg) return
    const [a, b] = seg
    if (!inFrame(a, w, h) && !inFrame(b, w, h) && !crosses(a, b, w, h)) return
    out.push({ id, face, edge, axis, side, size, a, b, assumed: assumed.includes(name) })
  }
  const hl = street ? s.height_l : s.height, hr = street ? s.height_r : s.height, hb = street ? Math.max(s.height_l, s.height_r) : s.height
  add('back', street ? 'end' : 'wall_back', 'foot', 'z', 'min', V(e.x0, 0, e.z0), V(e.x1, 0, e.z0), street ? 'length' : 'back')
  add('left', street ? 'facade_left' : 'wall_left', 'foot', 'x', 'min', V(e.x0, 0, e.z1), V(e.x0, 0, e.z0), 'left')
  add('right', street ? 'facade_right' : 'wall_right', 'foot', 'x', 'max', V(e.x1, 0, e.z0), V(e.x1, 0, e.z1), 'right')
  add('top_back', street ? 'end' : 'wall_back', 'top', 'y', 'min', V(e.x0, hb, e.z0), V(e.x1, hb, e.z0), 'height', street ? 'both' : 'height')
  add('top_left', street ? 'facade_left' : 'wall_left', 'top', 'y', 'min', V(e.x0, hl, e.z1), V(e.x0, hl, e.z0), 'height', street ? 'height_l' : 'height')
  add('top_right', street ? 'facade_right' : 'wall_right', 'top', 'y', 'max', V(e.x1, hr, e.z0), V(e.x1, hr, e.z1), 'height', street ? 'height_r' : 'height')
  return out
}

/** A segment's part in front of the camera, projected (null when it is all behind). */
function segment(p: THREE.Vector3, q: THREE.Vector3, c: THREE.PerspectiveCamera, w: number, h: number): [[number, number], [number, number]] | null {
  let a = p.clone().applyMatrix4(c.matrixWorldInverse), b = q.clone().applyMatrix4(c.matrixWorldInverse)
  if (a.z > -NEAR && b.z > -NEAR) return null
  if (a.z > -NEAR) a = a.clone().lerp(b, (-NEAR - a.z) / (b.z - a.z))
  else if (b.z > -NEAR) b = b.clone().lerp(a, (-NEAR - b.z) / (a.z - b.z))
  const px = (v: THREE.Vector3): [number, number] => { const n = v.clone().applyMatrix4(c.projectionMatrix); return [+((n.x * 0.5 + 0.5) * w).toFixed(2), +((0.5 - n.y * 0.5) * h).toFixed(2)] }
  return [px(a), px(b)]
}

/** A segment crossing the frame with both ends outside it (a long wall's foot). */
function crosses(a: [number, number], b: [number, number], w: number, h: number): boolean {
  for (let t = 0.1; t < 1; t += 0.1) if (inFrame([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], w, h)) return true
  return false
}

/** The set's sizes and its camera for a floor plan (and the heights), centred on the origin again — the camera keeps its place in the
 *  room, so it moves by what the centre moved. */
function recentre(ps: PlaceSetDoc, cam: SourceCam, e: Extents, heights: Record<string, number>): { set: PlaceSetDoc; camera: SourceCam } {
  const cx = (e.x0 + e.x1) / 2, cz = (e.z0 + e.z1) / 2
  const r = (v: number) => +v.toFixed(3)
  const W = r(e.x1 - e.x0), D = r(e.z1 - e.z0)
  const sizes = ps.kind === 'room' ? { ...ps.sizes, width: W, depth: D, ...heights } : { ...ps.sizes, width: W, length: D, ...heights }
  const move = (p: number[]) => [+(p[0] - cx).toFixed(4), p[1], +(p[2] - cz).toFixed(4)]
  return { set: { ...ps, sizes }, camera: { ...cam, pos: move(cam.pos), target: move(cam.target) } }
}

/** A handle dragged to a point on the picture (pixels): the ray from the camera through it meets the floor (a foot) or the wall's plane
 *  (a top); the wall moves there, never closer than half a metre to its opposite (nor past the camera, for a foot), the height at least
 *  1 m. Null when the ray misses (a foot dragged above the horizon). */
export function dragTo(ps: PlaceSetDoc, cam: SourceCam, w: number, h: number, hd: Handle, pt: [number, number]): { set: PlaceSetDoc; camera: SourceCam } | null {
  const e = extents(ps)
  if (!e) return null
  const c = sourceCamera(cam, w / h)
  const ndc = new THREE.Vector3((pt[0] / w) * 2 - 1, 1 - (pt[1] / h) * 2, 0.5).unproject(c)
  const o = c.position.clone(), dir = ndc.sub(o).normalize()
  if (hd.edge === 'foot') {
    if (dir.y >= -1e-4) return null
    const t = -o.y / dir.y, hit = o.clone().addScaledVector(dir, t)
    const next = { ...e }
    const cx = cam.pos[0], cz = cam.pos[2]
    if (hd.axis === 'x' && hd.side === 'min') next.x0 = Math.min(hit.x, next.x1 - MIN_SIZE, cx - 0.1)
    if (hd.axis === 'x' && hd.side === 'max') next.x1 = Math.max(hit.x, next.x0 + MIN_SIZE, cx + 0.1)
    if (hd.axis === 'z' && hd.side === 'min') next.z0 = Math.min(hit.z, next.z1 - MIN_SIZE, cz - 0.1)
    return recentre(ps, cam, next, {})
  }
  const wallX = hd.face.endsWith('left') ? e.x0 : hd.face.endsWith('right') ? e.x1 : null
  let t: number
  if (wallX !== null) { if (Math.abs(dir.x) < 1e-5) return null; t = (wallX - o.x) / dir.x }
  else { if (Math.abs(dir.z) < 1e-5) return null; t = (e.z0 - o.z) / dir.z }
  if (t <= 0) return null
  const y = Math.max(1, +o.clone().addScaledVector(dir, t).y.toFixed(3))
  const heights = hd.size === 'both' ? { height_l: y, height_r: y } : { [hd.size ?? 'height']: y }
  return recentre(ps, cam, e, heights)
}

const LENGTHS: Record<SetKind, string[]> = { room: ['width', 'depth', 'height'], corridor: ['width', 'height', 'length'], street: ['width', 'length', 'pavement', 'height_l', 'height_r'], ground: [] }

/** The camera's height set (D143: MoGe's scale runs short; the camera's height is what fixes it): the fit scales with it, the set's sizes
 *  and the camera's place alike. Open ground has no measured size: only the camera rises or falls. */
export function rescale(ps: PlaceSetDoc, cam: SourceCam, height: number): { set: PlaceSetDoc; camera: SourceCam } {
  const k = height / Math.max(0.05, cam.pos[1])
  if (ps.kind === 'ground') {
    const dy = height - cam.pos[1]
    return { set: ps, camera: { ...cam, pos: [cam.pos[0], height, cam.pos[2]], target: [cam.target[0], cam.target[1] + dy, cam.target[2]] } }
  }
  const sizes = { ...ps.sizes }
  for (const key of LENGTHS[ps.kind]) if (typeof sizes[key] === 'number') sizes[key] = +(sizes[key] * k).toFixed(3)
  const sc = (p: number[]) => p.map((v) => +(v * k).toFixed(4))
  return { set: { ...ps, sizes }, camera: { ...cam, pos: sc(cam.pos), target: sc(cam.target) } }
}

/** Another kind for the same picture, one click (D143): a room and a corridor share the floor plan; a street keeps the width and runs
 *  two thirds ahead of the camera (set_fit's rule); open ground stands the camera at its middle. */
export function changeKind(ps: PlaceSetDoc, cam: SourceCam, kind: SetKind): { set: PlaceSetDoc; camera: SourceCam } {
  if (kind === ps.kind) return { set: ps, camera: cam }
  const e = extents(ps)
  const s = sizesOf(ps)
  const height = ps.kind === 'street' ? Math.max(s.height_l, s.height_r) : ps.kind === 'ground' ? 3 : s.height
  const base: PlaceSetDoc = { ...ps, kind, sizes: { ...SET_KIND_SIZES[kind] }, parts: {}, faces: [] }
  if (kind === 'ground' || !e) {
    const dx = cam.pos[0], dz = cam.pos[2]
    const shifted = { ...cam, pos: [0, cam.pos[1], 0], target: [cam.target[0] - dx, cam.target[1], cam.target[2] - dz] }
    if (kind === 'ground') return { set: base, camera: shifted }
    const d = SET_KIND_SIZES[kind]
    const w = d.width, len = kind === 'room' ? d.depth : d.length
    return recentre(base, shifted, { x0: -w / 2, x1: w / 2, z0: -len * 2 / 3, z1: len / 3 }, kind === 'street' ? { height_l: d.height_l, height_r: d.height_r } : { height: d.height })
  }
  if (kind === 'street') {
    const L = SET_KIND_SIZES.street.length
    return recentre({ ...base, sizes: { ...base.sizes, pavement: SET_KIND_SIZES.street.pavement } }, cam, { x0: e.x0, x1: e.x1, z0: cam.pos[2] - L * 2 / 3, z1: cam.pos[2] + L / 3 }, { height_l: height, height_r: height })
  }
  return recentre(base, cam, e, { height })
}

/** What the faces were baked for: a change of the set or of its camera makes the bake stale. */
export function bakeKey(ps: PlaceSetDoc, cam: SourceCam): string {
  const r = (v: number) => Math.round(v * 1000) / 1000
  const sizes = Object.fromEntries(Object.entries(ps.sizes).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, r(v)]))
  const parts = Object.fromEntries(Object.entries(ps.parts ?? {}).sort(([a], [b]) => a.localeCompare(b)))
  return JSON.stringify({ k: ps.kind, s: sizes, p: parts, c: [...cam.pos, ...cam.target, cam.roll, cam.focal_mm].map(r) })
}
