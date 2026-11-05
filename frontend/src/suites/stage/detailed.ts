// CA1 (proto01_animate 01 §9a, the author's answer 1): the **Detailed** level of a figure — the starter set's skinned mannequin (65 bones:
// spine ×3, clavicles, fingers, feet) that *follows* the figure's 12-joint tree. The 12 joints stay the driver: picking, the gizmo, IK,
// keys, library clips and the pose pass's markers work on them unchanged (the Simple level blocks; Detailed refines). Each frame the
// mannequin's mapped bones are set so that each points along its figure limb — the inverse of the retargeter (motion/retarget.ts) — the
// pelvis sits at the figure's root, the segment lengths follow the figure's body, and the bones the figure does not have (fingers, wrists,
// feet, clavicles, the spine between) take their own rotations (`extra`, keyed like the joints: hand presets, a wrist turn).
// proto01_UIcast CS1 (S1, CB5): one body — the mannequin follows the whole fit (torso, shoulders, hips, neck, head, forearms, shins), so the
// hand and foot points it carries start at the figure's wrist and ankle points; (S2) its fingers rest as the character's hands do.
import * as THREE from 'three'
import type { Joint, Limbs } from './builders'
import { buildClayHand, fingerPoints, shapeOf, shownFingers, type HandShapes, type PalmFrame } from './clayHand'
import { LINKS, RIGS, norm, type Part, type RigName } from './motion/retarget'

export interface Detailed {
  object: THREE.Object3D                              // the mannequin, placed beside the figure's joint tree (the same parent)
  bones: Map<string, THREE.Object3D>                  // by normalised name
  /** Pose the mannequin after the figure's joints (world transforms read from them); `extra`: bone name → Euler degrees YXZ on its rest. */
  follow: (J: Record<Joint, THREE.Object3D>, extra?: Record<string, number[]> | null) => void
  /** A hand preset as `extra` turns of that hand's finger bones (by the rig's own bone names); `curl` scales it (S2's rest hand), `spread`
   *  fans the fingers at their knuckles and `thumb` opens the thumb from the palm, in degrees (CS2). */
  handPreset: (side: 'r' | 'l', preset: HandPreset, curl?: number, spread?: number, thumb?: number) => Record<string, number[]>
  /** D101: markers on the mannequin's hands and feet for the pose pass (null when the rig has no fingers): COCO-WholeBody's feet (left big
   *  toe, small toe, heel, then the right's), OpenPose's 21 points per hand. */
  wholebody: { feet: THREE.Object3D[]; left: THREE.Object3D[]; right: THREE.Object3D[] } | null
  /** CS3 (proto01_UIcast 06 §2.5): drawn as its hands only — the character's shell is its body, and Pixal3D's hands are mittens, so the
   *  hand rig keeps its fingers. Each skinned mesh keeps the triangles whose three corners are weighted mostly (≥ 0.5) to a hand's bones;
   *  false gives the whole mannequin back. A cut of the geometry, so every pass (an override material) draws the hands alone too. RG2
   *  (D187 R3): a character with its own hands (`handShape`) is drawn with its clay hands instead — the mannequin then shows nothing. */
  handsOnly: (on: boolean) => void
  /** RG2: the clay hands built from the character's hand shape (empty without one). */
  clayHands: THREE.Mesh[]
}

export const HAND_PRESETS = ['open', 'relaxed', 'fist', 'point', 'grip', 'pinch'] as const
export type HandPreset = (typeof HAND_PRESETS)[number]
const FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky'] as const
/** D191: a thumb curls toward the palm's side, and for each unit of it this much across the palm (toward the pinky) and toward the fingers — a
 *  fist's thumb lies over the fingers, a pinch's meets the index (char01: 0.52 palms apart, was 1.37). */
const THUMB_ACROSS = 0.35
const THUMB_UP = 0.6
type Finger = (typeof FINGER_NAMES)[number]
/** Curl in degrees per finger joint (knuckle, middle, tip) for each preset; the thumb's three joints too. */
const CURL: Record<HandPreset, Record<Finger, [number, number, number]>> = {
  open: { thumb: [0, 0, 0], index: [0, 0, 0], middle: [0, 0, 0], ring: [0, 0, 0], pinky: [0, 0, 0] },
  relaxed: { thumb: [10, 15, 10], index: [22, 35, 15], middle: [26, 40, 18], ring: [30, 42, 20], pinky: [32, 45, 20] },   // CS1 (S2): a hand at rest, curled as people hold it (was 12–25°: near flat)
  fist: { thumb: [30, 40, 40], index: [85, 95, 60], middle: [85, 95, 60], ring: [85, 95, 60], pinky: [85, 95, 60] },
  point: { thumb: [30, 40, 30], index: [0, 0, 0], middle: [85, 95, 60], ring: [85, 95, 60], pinky: [85, 95, 60] },
  grip: { thumb: [25, 30, 20], index: [55, 65, 35], middle: [55, 65, 35], ring: [55, 65, 35], pinky: [55, 65, 35] },
  pinch: { thumb: [35, 30, 25], index: [40, 45, 25], middle: [15, 20, 10], ring: [18, 22, 12], pinky: [20, 25, 12] },
}

/** The rig's own name of a finger joint (k = 1 knuckle … 3 tip joint). */
export function fingerBone(rig: RigName, side: 'r' | 'l', finger: Finger, k: number): string {
  if (rig === 'unreal') return k === 4 ? `${finger}_04_leaf_${side}` : `${finger}_0${k}_${side}`
  if (rig === 'rigify') return finger === 'thumb' ? `DEF-thumb.0${k}.${side.toUpperCase()}` : `DEF-f_${finger}.0${k}.${side.toUpperCase()}`
  const S = side === 'r' ? 'Right' : 'Left'
  return `mixamorig:${S}Hand${finger[0].toUpperCase()}${finger.slice(1)}${k}`
}

const rad = THREE.MathUtils.degToRad
/** The default dummy's leg (hip joint → ankle, builders.ts at ×1): the size the starter mannequin's head is drawn for. */
const DEFAULT_LEG = 0.87
/** What a figure's body gives its Detailed mannequin beyond the limb lengths (body.ts; none: the default adult, relaxed hands). */
export interface DetailedBody { hands?: number; feet?: number; head?: number; handRest?: { preset: HandPreset; curl: number; spread?: number; thumb?: number } | null; feetOut?: number
  handShape?: HandShapes | null }                                         // RG2 (D187): the character's own hands (body.hand_shape)

function bonesOf(root: THREE.Object3D): Map<string, THREE.Object3D> {
  const m = new Map<string, THREE.Object3D>()
  root.traverse((o) => { if (o.name) { const k = norm(o.name); if (!m.has(k)) m.set(k, o) } })
  return m
}

/**
 * A follower around a loaded mannequin (a clone of the starter set's scene: its SkinnedMesh and bones). `parent` is the object the
 * figure's joint tree hangs from (the figure's own frame); `limbs` are the figure's limb lengths (builders.mannequin), so the
 * mannequin's segments are scaled to the figure's body.
 */
export function makeDetailed(mannequin: THREE.Object3D, rig: RigName, parent: THREE.Object3D, J: Record<Joint, THREE.Object3D>, limbs: Limbs,
                             size: DetailedBody = {}): Detailed {
  const bones = bonesOf(mannequin)
  const part = (p: Part) => bones.get(norm(RIGS[rig][p]))!
  for (const p of Object.keys(RIGS[rig]) as Part[]) if (!part(p)) throw new Error(`the mannequin has no bone for ${p} (${RIGS[rig][p]})`)
  const object = new THREE.Group()
  object.name = 'detailed'
  object.add(mannequin)
  parent.add(object)
  // rest, in the mannequin's own space: its facing (right shoulder at −X, as the figure) and its hip height against the figure's
  mannequin.updateMatrixWorld(true)
  const pos = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3()).applyMatrix4(new THREE.Matrix4().copy(mannequin.matrixWorld).invert())
  const right = pos(part('r_upper')).sub(pos(part('l_upper'))).setY(0)
  object.quaternion.setFromUnitVectors(right.lengthSq() > 1e-8 ? right.normalize() : new THREE.Vector3(-1, 0, 0), new THREE.Vector3(-1, 0, 0))
  parent.updateMatrixWorld(true)
  const inFig = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3()).applyMatrix4(new THREE.Matrix4().copy(parent.matrixWorld).invert())
  const ankle = new THREE.Vector3(0, -limbs.shin, 0).applyMatrix4(J.r_knee.matrixWorld).applyMatrix4(new THREE.Matrix4().copy(parent.matrixWorld).invert())
  const figLeg = inFig(J.r_hip).distanceTo(inFig(J.r_knee)) + inFig(J.r_knee).distanceTo(ankle)
  const srcLeg = pos(part('r_thigh')).distanceTo(pos(part('r_calf'))) + pos(part('r_calf')).distanceTo(pos(part('r_foot')))
  object.scale.setScalar(srcLeg > 1e-6 ? figLeg / srcLeg : 1)
  object.updateMatrixWorld(true)
  // segment lengths onto the figure's: each mapped bone's child moved along its own offset
  const seg: [Part, Part, Joint, Joint | null][] = [['r_upper', 'r_lower', 'r_shoulder', 'r_elbow'], ['l_upper', 'l_lower', 'l_shoulder', 'l_elbow'],
    ['r_thigh', 'r_calf', 'r_hip', 'r_knee'], ['l_thigh', 'l_calf', 'l_hip', 'l_knee']]
  for (const [a, b, ja, jb] of seg) {
    const want = inFig(J[ja]).distanceTo(inFig(J[jb!]))
    const have = inFig(part(a)).distanceTo(inFig(part(b)))
    if (have > 1e-6) part(b).position.multiplyScalar(want / have)
  }
  object.updateMatrixWorld(true)
  // S1: the rest of the body onto the figure's — its joint offsets (`J[…].position`) do not change with the pose (the pose turns the joints)
  const off = (j: Joint) => J[j].position
  const put = (b: THREE.Object3D, figPoint: THREE.Vector3) => {
    b.parent!.updateWorldMatrix(true, false)
    b.position.copy(b.parent!.worldToLocal(figPoint.clone().applyMatrix4(parent.matrixWorld)))
    object.updateMatrixWorld(true)
  }
  const H = inFig(part('hips'))
  const torsoHave = inFig(part('neck')).distanceTo(H), torsoWant = off('spine').length() + off('neck').length()   // the pelvis → the neck joint
  if (torsoHave > 1e-6) {                                                   // the spine chain's offsets scaled: the chest and neck rise or sink
    for (let b: THREE.Object3D | null = part('neck'); b && b !== part('hips'); b = b.parent) b.position.multiplyScalar(torsoWant / torsoHave)
    object.updateMatrixWorld(true)
  }
  const N = inFig(part('neck'))
  for (const [p, j] of [['r_upper', 'r_shoulder'], ['l_upper', 'l_shoulder']] as const) {   // the shoulders: each joint's place against the neck joint
    const d = off(j).clone().sub(off('neck'))                               // in the spine's frame: (±half the shoulders' width, −0.04·torso, 0)
    put(part(p), new THREE.Vector3(N.x + d.x, N.y + d.y, inFig(part(p)).z))
  }
  for (const [p, j] of [['r_thigh', 'r_hip'], ['l_thigh', 'l_hip']] as const) {             // the hips: each joint's place against the pelvis
    put(part(p), new THREE.Vector3(H.x + off(j).x, H.y + off(j).y, inFig(part(p)).z))
  }
  const headHave = inFig(part('head')).distanceTo(N)                        // the neck: the head's pivot a neck's length above it (S3: 0.12 · neck)
  if (headHave > 1e-6) { part('head').position.multiplyScalar(off('head').length() / headHave); object.updateMatrixWorld(true) }
  const ends: [Part, Part, number][] = [['r_lower', 'r_hand', limbs.forearm], ['l_lower', 'l_hand', limbs.forearm], ['r_calf', 'r_foot', limbs.shin], ['l_calf', 'l_foot', limbs.shin]]
  for (const [a, b, len] of ends) {                                         // the forearms and shins: the hand at the wrist point, the foot at the ankle
    const have = inFig(part(a)).distanceTo(inFig(part(b)))
    if (have > 1e-6) part(b).position.multiplyScalar(len / have)
  }
  part('head').scale.multiplyScalar((size.head ?? 1) * (DEFAULT_LEG / Math.max(1e-6, figLeg)))   // the head at the character's size, not its legs'
  // CA1b (D104): the hands and feet at the character's size (the body's factors; the markers below ride on these bones)
  for (const p of ['r_hand', 'l_hand'] as Part[]) part(p).scale.multiplyScalar(size.hands ?? 1)
  for (const p of ['r_foot', 'l_foot'] as Part[]) part(p).scale.multiplyScalar(size.feet ?? 1)
  object.updateMatrixWorld(true)
  // RG2 (D187 R2, R5): the character's own hands — each finger's bones moved to its knuckle, its direction and its lengths, in palm lengths
  // of the rig's palm at the character's size (`hands`, fitted from the A-pose's palm); the curl axes, the presets and the guide's markers
  // below are then the character's. A finger keeps the rig's own lift off the palm (a thumb stands off it) and its knuckle's depth.
  type Chain = { bones: THREE.Object3D[]; points: THREE.Vector3[] }
  const shaped: Partial<Record<'r' | 'l', { pf: PalmFrame; chains: Partial<Record<Finger, Chain>> }>> = {}
  if (size.handShape) for (const side of ['r', 'l'] as const) {
    const hand = part(side === 'r' ? 'r_hand' : 'l_hand')
    const fb = (f: Finger, k: number) => bones.get(norm(fingerBone(rig, side, f, k)))
    const m1 = fb('middle', 1), i1 = fb('index', 1), p1 = fb('pinky', 1), t2 = fb('thumb', 2) ?? fb('thumb', 1)
    if (!m1 || !i1 || !p1 || !t2) continue
    const W = inFig(hand), L = W.distanceTo(inFig(m1))
    if (L < 1e-6) continue
    const ey = inFig(m1).sub(W).normalize()
    const ex = inFig(i1).sub(inFig(p1))
    ex.addScaledVector(ey, -ex.dot(ey)).normalize()
    if (inFig(t2).sub(W).dot(ex) < 0) ex.negate()                            // +x toward the thumb, as the shape is read (hands.py)
    const pf: PalmFrame = { wrist: W, ex, ey, n: ex.clone().cross(ey).normalize(), L }
    const shape = shapeOf(size.handShape, side)
    const chains: Partial<Record<Finger, Chain>> = {}
    for (const f of FINGER_NAMES) {
      const fs = shape.fingers[f], js = [1, 2, 3].map((k) => fb(f, k))
      if (!fs || js.some((b) => !b)) continue
      const k0 = inFig(js[0]!), lift = inFig(js[1]!).sub(k0).normalize().dot(pf.n), depth = k0.clone().sub(W).dot(pf.n)
      const pts = fingerPoints(fs, pf, lift, depth)
      js.forEach((b, k) => put(b!, pts[k]))
      const leaf = fb(f, 4)
      if (leaf) put(leaf, pts[3])
      chains[f] = { bones: js as THREE.Object3D[], points: pts }
    }
    shaped[side] = { pf, chains }
  }
  // rest rotations and directions in the figure's frame
  const figInv = new THREE.Quaternion()
  const restRot = new Map<string, THREE.Quaternion>()
  const restLocal = new Map<string, THREE.Quaternion>()
  mannequin.traverse((o) => { restLocal.set(o.uuid, o.quaternion.clone()) })
  const rotIn = (o: THREE.Object3D) => { parent.getWorldQuaternion(figInv).invert(); return figInv.clone().multiply(o.getWorldQuaternion(new THREE.Quaternion())) }
  for (const p of Object.keys(RIGS[rig]) as Part[]) restRot.set(p, rotIn(part(p)))
  // the spine chain, base to chest: the figure's spine is one straight segment, so every bone of the chain takes the same turn
  const spineChain: THREE.Object3D[] = []
  for (let b: THREE.Object3D | null = part('chest'); b; b = b.parent) { spineChain.unshift(b); if (b === part('spineBase')) break }
  const spineRest = new Map(spineChain.map((b) => [b.uuid, rotIn(b)]))
  const align = new Map<Joint, THREE.Quaternion>()
  for (const l of LINKS) {
    const dir = l.to === l.bone ? new THREE.Vector3(0, 1, 0).applyQuaternion(restRot.get(l.bone)!) : inFig(part(l.to)).sub(inFig(part(l.from ?? l.bone)))
    align.set(l.joint, dir.lengthSq() > 1e-10 ? new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(...l.rest), dir.normalize()) : new THREE.Quaternion())
  }
  align.set('head', align.get('neck')!.clone())
  const alignInv = new Map([...align].map(([k, q]) => [k, q.clone().invert()]))
  const linked = new Set(LINKS.map((l) => norm(RIGS[rig][l.bone])).concat(norm(RIGS[rig].hips), spineChain.map((b) => norm(b.name))))
  const parentWorldQ = new THREE.Quaternion(), figQ = new THREE.Quaternion(), tmp = new THREE.Quaternion()
  const restHand: Record<string, number[]> = {}                             // S2: filled once the curl axes are known (below)
  // RG2b (D188 F3, F5): each foot's turn at the ankle and the ball (a pose's extra r_ankle, r_ball, l_ankle, l_ball — the clips' foot turns,
  // rig-independent): about the foot's own side-to-side axis, toes down + at the ankle, toes up + at the ball; filled below, read by follow
  const footAxes: Partial<Record<'r' | 'l', { foot: THREE.Object3D; ankle: THREE.Vector3; ball: THREE.Object3D | null; toe: THREE.Vector3 | null }>> = {}

  /** Set a bone's world rotation (given in the figure's frame) through its parent's current world rotation. */
  const setWorld = (b: THREE.Object3D, inFigRot: THREE.Quaternion) => {
    parent.getWorldQuaternion(figQ)
    b.parent!.updateWorldMatrix(true, false)
    b.parent!.getWorldQuaternion(parentWorldQ)
    b.quaternion.copy(parentWorldQ.invert().multiply(figQ.clone().multiply(inFigRot)))
    b.updateMatrixWorld(true)
  }

  const follow = (Jt: Record<Joint, THREE.Object3D>, extra?: Record<string, number[]> | null) => {
    // the bones of their own first (they sit between and below the mapped ones): rest, or rest × the keyed turn
    mannequin.traverse((o) => {
      const k = norm(o.name)
      if (!o.name || linked.has(k)) return
      const r = restLocal.get(o.uuid)
      if (!r) return
      const e = extra?.[o.name] ?? extra?.[k] ?? restHand[o.name]
      o.quaternion.copy(r)
      if (e) o.quaternion.multiply(tmp.setFromEuler(new THREE.Euler(rad(e[0]), rad(e[1]), rad(e[2]), 'YXZ')))
    })
    for (const side of ['r', 'l'] as const) {                               // RG2b: the feet's own turns, on their rest (and their turn out)
      const fa = footAxes[side]
      if (!fa) continue
      const a = extra?.[`${side}_ankle`]?.[0], b = extra?.[`${side}_ball`]?.[0]
      if (a) fa.foot.quaternion.multiply(tmp.setFromAxisAngle(fa.ankle, rad(a)))
      if (b && fa.ball && fa.toe) fa.ball.quaternion.multiply(tmp.setFromAxisAngle(fa.toe, rad(b)))
    }
    parent.updateMatrixWorld(true)
    // the pelvis: the figure root's turn and place
    const hips = part('hips')
    setWorld(hips, rotIn(Jt.root).multiply(restRot.get('hips')!))
    const rootW = Jt.root.getWorldPosition(new THREE.Vector3())
    hips.parent!.updateWorldMatrix(true, false)
    hips.position.copy(hips.parent!.worldToLocal(rootW))
    hips.updateMatrixWorld(true)
    // each mapped bone along its figure limb, parents first
    const spineTurn = rotIn(Jt.spine).multiply(alignInv.get('spine')!)
    for (const b of spineChain) setWorld(b, spineTurn.clone().multiply(spineRest.get(b.uuid)!))
    for (const l of LINKS) if (l.joint !== 'spine') setWorld(part(l.bone), rotIn(Jt[l.joint]).multiply(alignInv.get(l.joint)!).multiply(restRot.get(l.bone)!))
  }
  // the curl axis of each finger joint, in its own rest frame: across the finger, square to the palm's side (the palm's normal, turned per
  // side so that a positive curl closes the hand). D191: the palm's one normal for every finger — it was index → pinky × the finger's own
  // way, which for a thumb read spread wide (char01's 61°) lies along the palm and curled the thumb back toward the wrist; the thumb now
  // curls toward the palm, across it and toward the fingers (THUMB_ACROSS, THUMB_UP)
  const curlAxis = new Map<string, THREE.Vector3>()
  const fanAxis = new Map<string, THREE.Vector3>()                          // CS2: the palm's normal in each knuckle's rest frame (the fingers' spread)
  for (const side of ['r', 'l'] as const) {
    const hand = part(side === 'r' ? 'r_hand' : 'l_hand')
    const b = (f: Finger, k: number) => bones.get(norm(fingerBone(rig, side, f, k)))
    const i1 = b('index', 1), p1 = b('pinky', 1), m1 = b('middle', 1)
    if (!i1 || !p1) continue
    const across = inFig(i1).sub(inFig(p1))
    const up = (m1 ? inFig(m1) : inFig(i1).lerp(inFig(p1), 0.5)).sub(inFig(hand)).normalize()            // the wrist to the knuckles
    const normal = (side === 'r' ? across.clone().cross(up) : up.clone().cross(across)).normalize()     // the palm's side
    const toPinky = across.clone().addScaledVector(up, -across.dot(up)).normalize().negate()
    for (const f of FINGER_NAMES) for (const k of [1, 2, 3]) {
      const bone = b(f, k), next = b(f, k + 1) ?? bone?.children[0]
      if (!bone) continue
      const d = (next ? inFig(next) : inFig(bone).add(inFig(bone).sub(inFig(b(f, k - 1) ?? hand)))).sub(inFig(bone)).normalize()
      const toward = f === 'thumb' ? normal.clone().addScaledVector(toPinky, THUMB_ACROSS).addScaledVector(up, THUMB_UP) : normal.clone()
      const palm = toward.addScaledVector(d, -toward.dot(d))
      if (palm.lengthSq() < 1e-8) continue                                    // a finger along the palm's normal: no curl to give it
      const axisFig = d.clone().cross(palm.normalize()).normalize()
      const restQ = rotIn(bone)
      curlAxis.set(bone.name, axisFig.applyQuaternion(restQ.clone().invert()))
      if (k === 1) fanAxis.set(bone.name, normal.clone().addScaledVector(d, -normal.dot(d)).normalize().applyQuaternion(restQ.clone().invert()))   // spread about the palm's normal
    }
  }
  const FAN: Record<Finger, number> = { thumb: 0, index: 1, middle: 0, ring: -1, pinky: -2 }   // CS2: each finger's share of the spread
  const handPreset = (side: 'r' | 'l', preset: HandPreset, curl = 1, spread = 0, thumb = 0) => {
    const out: Record<string, number[]> = {}
    for (const f of FINGER_NAMES) for (const k of [1, 2, 3]) {
      const name = fingerBone(rig, side, f, k)
      const bone = bones.get(norm(name))
      const axis = bone && curlAxis.get(bone.name)
      if (!bone || !axis) continue
      const fan = k === 1 ? fanAxis.get(bone.name) : undefined
      const open = f === 'thumb' ? thumb : (FAN[f] * spread) / 2
      const q = new THREE.Quaternion().setFromAxisAngle(axis, rad(CURL[preset][f][k - 1] * curl))
      if (fan && open) q.premultiply(new THREE.Quaternion().setFromAxisAngle(fan, rad(side === 'r' ? -open : open)))
      const e = new THREE.Euler().setFromQuaternion(q, 'YXZ')
      out[bone.name] = [e.x, e.y, e.z].map((v) => Math.round(THREE.MathUtils.radToDeg(v) * 100) / 100 || 0)   // no −0
    }
    return out
  }
  // S2: the hands at rest — the character's (relaxed unless its body says), never the GLB's flat, fanned hand; a key's finger turns win
  const rest = size.handRest ?? { preset: 'relaxed' as HandPreset, curl: 1 }
  Object.assign(restHand, handPreset('r', rest.preset, rest.curl, rest.spread ?? 0, rest.thumb ?? 0), handPreset('l', rest.preset, rest.curl, rest.spread ?? 0, rest.thumb ?? 0))
  if (size.feetOut) for (const side of ['r', 'l'] as const) {               // CS2: the feet turned out at rest, about the figure's up
    const foot = part(side === 'r' ? 'r_foot' : 'l_foot')
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(rotIn(foot).invert())
    const e = new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromAxisAngle(up, rad(side === 'r' ? -size.feetOut : size.feetOut)), 'YXZ')
    restHand[foot.name] = [e.x, e.y, e.z].map((v) => Math.round(THREE.MathUtils.radToDeg(v) * 100) / 100 || 0)
  }
  // D101: hand and foot markers, placed at their rest places and carried by their bones
  const markerAt = (bone: THREE.Object3D, figPoint: THREE.Vector3) => {
    const m = new THREE.Object3D()
    bone.updateMatrixWorld(true)
    m.position.copy(bone.worldToLocal(figPoint.clone().applyMatrix4(parent.matrixWorld)))
    bone.add(m)
    return m
  }
  const toeBones: Record<RigName, (s: 'r' | 'l') => [string, string | null]> = {
    unreal: (s) => [`ball_${s}`, `ball_leaf_${s}`], rigify: (s) => [`DEF-toe.${s.toUpperCase()}`, null],
    mixamo: (s) => [`mixamorig:${s === 'r' ? 'Right' : 'Left'}ToeBase`, `mixamorig:${s === 'r' ? 'Right' : 'Left'}Toe_End`],
  }
  for (const side of ['r', 'l'] as const) {                                 // RG2b: the side-to-side axes, in each bone's rest frame
    const foot = part(side === 'r' ? 'r_foot' : 'l_foot')
    const ball = bones.get(norm(toeBones[rig](side)[0])) ?? null
    const fwd = (ball ? inFig(ball) : inFig(foot).add(new THREE.Vector3(0, 0, 0.1))).sub(inFig(foot)).setY(0)
    if (fwd.lengthSq() < 1e-10) fwd.set(0, 0, 1)
    const across = fwd.normalize().clone().cross(new THREE.Vector3(0, -1, 0)).normalize()   // turning about it takes the forward down
    footAxes[side] = { foot, ankle: across.clone().applyQuaternion(rotIn(foot).invert()), ball, toe: ball ? across.clone().negate().applyQuaternion(rotIn(ball).invert()) : null }
  }
  let wholebody: Detailed['wholebody'] = null
  const hasFingers = (['r', 'l'] as const).every((s) => FINGER_NAMES.every((f) => bones.get(norm(fingerBone(rig, s, f, 3)))))
  if (hasFingers) {
    const hands = { r: [] as THREE.Object3D[], l: [] as THREE.Object3D[] }
    for (const side of ['r', 'l'] as const) {
      const hand = part(side === 'r' ? 'r_hand' : 'l_hand')
      hands[side].push(markerAt(hand, inFig(hand)))
      for (const f of FINGER_NAMES) {
        const js = [1, 2, 3].map((k) => bones.get(norm(fingerBone(rig, side, f, k)))!)
        for (const j of js) hands[side].push(markerAt(j, inFig(j)))
        const leaf = bones.get(norm(fingerBone(rig, side, f, 4)))
        const tip = shaped[side]?.chains[f]?.points[3] ?? (leaf ? inFig(leaf) : inFig(js[2]).add(inFig(js[2]).sub(inFig(js[1])).multiplyScalar(0.8)))
        hands[side].push(markerAt(js[2], tip))
        if (size.handShape && !shownFingers(shapeOf(size.handShape, side)).includes(f)) for (const m of hands[side].slice(-4)) m.userData.hidden = true   // Q4: the guide leaves it out
      }
    }
    const feet: THREE.Object3D[] = []
    const mid = inFig(part('hips'))
    const fs = (size.feet ?? 1) * (figLeg / DEFAULT_LEG)                   // CS1: the toes' and heel's offsets at the foot's size, as the bones are
    for (const side of ['l', 'r'] as const) {
      const foot = part(side === 'r' ? 'r_foot' : 'l_foot')
      const [ballName, leafName] = toeBones[rig](side)
      const ball = bones.get(norm(ballName)) ?? foot
      const leaf = leafName ? bones.get(norm(leafName)) : undefined
      const fwd = inFig(ball).sub(inFig(foot)).setY(0)
      if (fwd.lengthSq() < 1e-8) fwd.set(0, 0, 1)
      fwd.normalize()
      const tipPoint = leaf ? inFig(leaf) : inFig(ball).add(fwd.clone().multiplyScalar(0.05 * fs))
      const medial = new THREE.Vector3(Math.sign(mid.x - inFig(foot).x) || (side === 'l' ? -1 : 1), 0, 0)
      const ground = Math.min(inFig(ball).y, tipPoint.y)
      feet.push(markerAt(leaf ?? ball, tipPoint.clone().add(medial.clone().multiplyScalar(0.02 * fs))))                     // big toe
      feet.push(markerAt(ball, inFig(ball).lerp(tipPoint, 0.6).add(medial.clone().multiplyScalar(-0.03 * fs))))            // small toe
      feet.push(markerAt(foot, inFig(foot).setY(ground).add(fwd.clone().multiplyScalar(-0.05 * fs))))                       // heel
    }
    wholebody = { feet, left: hands.l, right: hands.r }
  }
  // RG2 (D187 R3): the clay hands on the shaped bones, hidden until the figure is drawn as its shell (handsOnly)
  const clayMat = ((): THREE.Material => { let mat: THREE.Material | null = null; mannequin.traverse((o) => { const m = o as THREE.Mesh; if (!mat && m.isMesh) mat = Array.isArray(m.material) ? m.material[0] : m.material }); return mat ?? new THREE.MeshLambertMaterial({ color: 0xb4b4b8 }) })()
  const figScale = parent.getWorldScale(new THREE.Vector3()).x
  const toLocal = (bone: THREE.Object3D, figPoint: THREE.Vector3) => { bone.updateWorldMatrix(true, false); return bone.worldToLocal(figPoint.clone().applyMatrix4(parent.matrixWorld)) }
  const scaleOf = (bone: THREE.Object3D) => figScale / Math.max(1e-9, bone.getWorldScale(new THREE.Vector3()).x)
  const clayHands: THREE.Mesh[] = []
  for (const side of ['r', 'l'] as const) {
    const sh = shaped[side]
    if (size.handShape && sh) clayHands.push(...buildClayHand(shapeOf(size.handShape, side), sh.pf, part(side === 'r' ? 'r_hand' : 'l_hand'), sh.chains, toLocal, scaleOf, clayMat))
  }
  for (const m of clayHands) { m.visible = false; m.castShadow = true; m.receiveShadow = true }
  const handBones = new Set<THREE.Object3D>()
  for (const h of [part('r_hand'), part('l_hand')]) h.traverse((b) => { handBones.add(b) })
  const whole = new Map<THREE.BufferGeometry, THREE.BufferAttribute | null>()
  const owned = new WeakSet<THREE.Mesh>()
  const handsOnly = (on: boolean) => {
    object.traverse((o) => {
      const m = o as THREE.SkinnedMesh
      if (!m.isSkinnedMesh) return
      if (!owned.has(m)) {                                                     // RG2: the clones share one geometry (SkeletonUtils) — this figure's
        const src = m.geometry, own = new THREE.BufferGeometry()               // cut must not cut the others': its own index over the shared attributes
        for (const k of Object.keys(src.attributes)) own.setAttribute(k, src.attributes[k])
        own.setIndex(src.index); for (const gr of src.groups) own.addGroup(gr.start, gr.count, gr.materialIndex)
        own.boundingBox = src.boundingBox?.clone() ?? null; own.boundingSphere = src.boundingSphere?.clone() ?? null
        m.geometry = own; owned.add(m)
      }
      const g = m.geometry
      if (!whole.has(g)) whole.set(g, g.index)
      const full = whole.get(g) ?? null
      if (!on) { g.setIndex(full); return }
      if (clayHands.length) { g.setIndex([]); return }                     // RG2: its own clay hands stand in for the mannequin's
      const si = g.attributes.skinIndex, sw = g.attributes.skinWeight, n = g.attributes.position.count
      const hand = m.skeleton.bones.map((b) => handBones.has(b))
      const weight = new Float32Array(n)
      for (let v = 0; v < n; v++) for (let k = 0; k < 4; k++) if (hand[si.getComponent(v, k)]) weight[v] += sw.getComponent(v, k)
      const tri = full ? Array.from(full.array as ArrayLike<number>) : Array.from({ length: n }, (_, i) => i)
      const kept: number[] = []
      for (let t = 0; t + 2 < tri.length; t += 3) if (weight[tri[t]] >= 0.5 && weight[tri[t + 1]] >= 0.5 && weight[tri[t + 2]] >= 0.5) kept.push(tri[t], tri[t + 1], tri[t + 2])
      g.setIndex(kept)
    })
    for (const m of clayHands) m.visible = on
  }
  follow(J)
  return { object, bones, follow, handPreset, wholebody, handsOnly, clayHands }
}
