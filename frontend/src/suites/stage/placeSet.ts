// proto01_UIcast CW6 (04 §2): a place's set — a few faces with sizes in one of four kinds. Pure: the faces' frames (a corner, two axes,
// a size) are what the engine draws, what the bake renders straight on (one texture a face) and what the picture view outlines. Every
// kind is centred on its own origin, as the fit (orchestrator/loom2/set_fit.py) centres it; each face's normal (u × v) looks into the
// space, so a camera inside sees its front.
import * as THREE from 'three'

export type SetKind = 'room' | 'street' | 'corridor' | 'ground'
export interface PlaceSetDoc { kind: SetKind; sizes: Record<string, number>; parts?: Record<string, boolean>; faces?: { id: string; texture_asset_id?: string | null; texel_m?: number }[] }
export interface Face { id: string; origin: THREE.Vector3; u: THREE.Vector3; v: THREE.Vector3; w: number; h: number }

export const SET_KIND_SIZES: Record<SetKind, Record<string, number>> = {
  room: { width: 5, depth: 6, height: 2.8 },
  corridor: { width: 2, height: 2.6, length: 12 },
  street: { width: 12, length: 30, pavement: 2, height_l: 9, height_r: 9 },
  ground: { size: 40, backdrop: 30, height: 12 },
}
/** The parts a kind has, and which are on by default (a room's front wall off: the camera usually stands there). */
export const SET_KIND_PARTS: Record<SetKind, Record<string, boolean>> = {
  room: { floor: true, ceiling: true, wall_back: true, wall_left: true, wall_right: true, wall_front: false },
  corridor: { floor: true, ceiling: true, wall_left: true, wall_right: true, wall_back: true, wall_front: false },
  street: { road: true, pavement_left: true, pavement_right: true, facade_left: true, facade_right: true, end: true },
  ground: { floor: true, backdrop: true },
}
const KERB = 0.12
const BACKDROP_FACETS = 12

const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z)
const face = (id: string, origin: THREE.Vector3, u: THREE.Vector3, v: THREE.Vector3, w: number, h: number): Face => ({ id, origin, u, v, w, h })

/** A box's six faces looking in (a room, a corridor): x ∈ [−w/2, w/2], z ∈ [−d/2, d/2], y ∈ [0, h]. */
function box(w: number, d: number, h: number): Face[] {
  return [
    face('floor', V(-w / 2, 0, d / 2), V(1, 0, 0), V(0, 0, -1), w, d),
    face('ceiling', V(-w / 2, h, -d / 2), V(1, 0, 0), V(0, 0, 1), w, d),
    face('wall_back', V(-w / 2, 0, -d / 2), V(1, 0, 0), V(0, 1, 0), w, h),
    face('wall_front', V(w / 2, 0, d / 2), V(-1, 0, 0), V(0, 1, 0), w, h),
    face('wall_left', V(-w / 2, 0, d / 2), V(0, 0, -1), V(0, 1, 0), d, h),
    face('wall_right', V(w / 2, 0, -d / 2), V(0, 0, 1), V(0, 1, 0), d, h),
  ]
}

/** A set's faces that are on, each in its own frame (metres). */
export function setFaces(ps: PlaceSetDoc): Face[] {
  const s = { ...SET_KIND_SIZES[ps.kind], ...ps.sizes }
  const on = { ...SET_KIND_PARTS[ps.kind], ...(ps.parts ?? {}) }
  let all: Face[]
  if (ps.kind === 'room') all = box(s.width, s.depth, s.height)
  else if (ps.kind === 'corridor') all = box(s.width, s.length, s.height)
  else if (ps.kind === 'street') {
    const W = s.width, L = s.length, p = Math.min(s.pavement, W / 2 - 0.5), road = W - 2 * p
    all = [
      face('road', V(-road / 2, 0, L / 2), V(1, 0, 0), V(0, 0, -1), road, L),
      face('pavement_left', V(-W / 2, KERB, L / 2), V(1, 0, 0), V(0, 0, -1), p, L),
      face('pavement_right', V(W / 2 - p, KERB, L / 2), V(1, 0, 0), V(0, 0, -1), p, L),
      face('facade_left', V(-W / 2, 0, L / 2), V(0, 0, -1), V(0, 1, 0), L, s.height_l),
      face('facade_right', V(W / 2, 0, -L / 2), V(0, 0, 1), V(0, 1, 0), L, s.height_r),
      face('end', V(-W / 2, 0, -L / 2), V(1, 0, 0), V(0, 1, 0), W, Math.max(s.height_l, s.height_r)),
    ]
  } else {
    const R = s.backdrop, n = BACKDROP_FACETS, side = 2 * R * Math.tan(Math.PI / n)
    all = [face('floor', V(-s.size / 2, 0, s.size / 2), V(1, 0, 0), V(0, 0, -1), s.size, s.size)]
    for (let k = 0; k < n; k++) {                                            // a ring of facets facing in (a cylinder's backdrop, bakeable flat)
      const a = (k / n) * Math.PI * 2, mid = V(Math.sin(a) * R, 0, -Math.cos(a) * R)
      const u = V(Math.cos(a), 0, Math.sin(a))                                 // along the ring; u × v points at the centre
      all.push(face(`backdrop_${k}`, mid.clone().addScaledVector(u, -side / 2), u, V(0, 1, 0), side, s.height))
    }
  }
  return all.filter((f) => on[f.id.replace(/_\d+$/, '')] !== false)
}

/** A face's outward normal into the space (u × v). */
export const normalOf = (f: Face) => new THREE.Vector3().crossVectors(f.u, f.v).normalize()

/** The set drawn: a plane mesh per face (its own UVs 0..1 across the face), named by the face (`userData.face`). */
export function placeSet(ps: PlaceSetDoc, mat: THREE.Material, textured?: (id: string) => THREE.Material | null): THREE.Group {
  const g = new THREE.Group()
  for (const f of setFaces(ps)) {
    const geo = new THREE.PlaneGeometry(f.w, f.h)
    const m = new THREE.Mesh(geo, textured?.(f.id) ?? mat)
    const n = normalOf(f)
    const basis = new THREE.Matrix4().makeBasis(f.u, f.v, n)                  // the plane's +X along u, +Y along v, facing n
    m.quaternion.setFromRotationMatrix(basis)
    m.position.copy(f.origin).addScaledVector(f.u, f.w / 2).addScaledVector(f.v, f.h / 2)
    m.userData.face = f.id
    g.add(m)
  }
  return g
}
