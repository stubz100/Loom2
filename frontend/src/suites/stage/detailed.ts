// CA1 (proto01_animate 01 §9a, the author's answer 1): the **Detailed** level of a figure — the starter set's skinned mannequin (65 bones:
// spine ×3, clavicles, fingers, feet) that *follows* the figure's 12-joint tree. The 12 joints stay the driver: picking, the gizmo, IK,
// keys, library clips and the pose pass's markers work on them unchanged (the Simple level blocks; Detailed refines). Each frame the
// mannequin's mapped bones are set so that each points along its figure limb — the inverse of the retargeter (motion/retarget.ts) — the
// pelvis sits at the figure's root, the segment lengths follow the figure's body, and the bones the figure does not have (fingers, wrists,
// feet, clavicles, the spine between) take their own rotations (`extra`, keyed like the joints: hand presets, a wrist turn).
import * as THREE from 'three'
import type { Joint, Limbs } from './builders'
import { LINKS, RIGS, norm, type Part, type RigName } from './motion/retarget'

export interface Detailed {
  object: THREE.Object3D                              // the mannequin, placed beside the figure's joint tree (the same parent)
  bones: Map<string, THREE.Object3D>                  // by normalised name
  /** Pose the mannequin after the figure's joints (world transforms read from them); `extra`: bone name → Euler degrees YXZ on its rest. */
  follow: (J: Record<Joint, THREE.Object3D>, extra?: Record<string, number[]> | null) => void
  /** A hand preset as `extra` turns of that hand's finger bones (by the rig's own bone names). */
  handPreset: (side: 'r' | 'l', preset: HandPreset) => Record<string, number[]>
  /** D101: markers on the mannequin's hands and feet for the pose pass (null when the rig has no fingers): COCO-WholeBody's feet (left big
   *  toe, small toe, heel, then the right's), OpenPose's 21 points per hand. */
  wholebody: { feet: THREE.Object3D[]; left: THREE.Object3D[]; right: THREE.Object3D[] } | null
}

export const HAND_PRESETS = ['open', 'relaxed', 'fist', 'point', 'grip', 'pinch'] as const
export type HandPreset = (typeof HAND_PRESETS)[number]
const FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky'] as const
type Finger = (typeof FINGER_NAMES)[number]
/** Curl in degrees per finger joint (knuckle, middle, tip) for each preset; the thumb's three joints too. */
const CURL: Record<HandPreset, Record<Finger, [number, number, number]>> = {
  open: { thumb: [0, 0, 0], index: [0, 0, 0], middle: [0, 0, 0], ring: [0, 0, 0], pinky: [0, 0, 0] },
  relaxed: { thumb: [5, 10, 5], index: [12, 18, 10], middle: [15, 20, 10], ring: [18, 22, 12], pinky: [20, 25, 12] },
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
                             size: { hands?: number; feet?: number } = {}): Detailed {
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
  // CA1b (D104): the hands and feet at the character's size (the body's factors; the markers below ride on these bones)
  for (const p of ['r_hand', 'l_hand'] as Part[]) part(p).scale.multiplyScalar(size.hands ?? 1)
  for (const p of ['r_foot', 'l_foot'] as Part[]) part(p).scale.multiplyScalar(size.feet ?? 1)
  object.updateMatrixWorld(true)
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
      const e = extra?.[o.name] ?? extra?.[k]
      o.quaternion.copy(r)
      if (e) o.quaternion.multiply(tmp.setFromEuler(new THREE.Euler(rad(e[0]), rad(e[1]), rad(e[2]), 'YXZ')))
    })
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
  // the curl axis of each finger joint, in its own rest frame: across the finger and the palm's normal (index → pinky × the finger's way,
  // turned per side so that a positive curl closes the hand)
  const curlAxis = new Map<string, THREE.Vector3>()
  for (const side of ['r', 'l'] as const) {
    const hand = part(side === 'r' ? 'r_hand' : 'l_hand')
    const b = (f: Finger, k: number) => bones.get(norm(fingerBone(rig, side, f, k)))
    const i1 = b('index', 1), p1 = b('pinky', 1)
    if (!i1 || !p1) continue
    const across = inFig(i1).sub(inFig(p1))
    for (const f of FINGER_NAMES) for (const k of [1, 2, 3]) {
      const bone = b(f, k), next = b(f, k + 1) ?? bone?.children[0]
      if (!bone) continue
      const d = (next ? inFig(next) : inFig(bone).add(inFig(bone).sub(inFig(b(f, k - 1) ?? hand)))).sub(inFig(bone)).normalize()
      const palm = side === 'r' ? across.clone().cross(d) : d.clone().cross(across)
      const axisFig = d.clone().cross(palm.normalize()).normalize()
      const restQ = rotIn(bone)
      curlAxis.set(bone.name, axisFig.applyQuaternion(restQ.clone().invert()))
    }
  }
  const handPreset = (side: 'r' | 'l', preset: HandPreset) => {
    const out: Record<string, number[]> = {}
    for (const f of FINGER_NAMES) for (const k of [1, 2, 3]) {
      const name = fingerBone(rig, side, f, k)
      const bone = bones.get(norm(name))
      const axis = bone && curlAxis.get(bone.name)
      if (!bone || !axis) continue
      const q = new THREE.Quaternion().setFromAxisAngle(axis, rad(CURL[preset][f][k - 1]))
      const e = new THREE.Euler().setFromQuaternion(q, 'YXZ')
      out[bone.name] = [e.x, e.y, e.z].map((v) => Math.round(THREE.MathUtils.radToDeg(v) * 100) / 100 || 0)   // no −0
    }
    return out
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
        const tip = leaf ? inFig(leaf) : inFig(js[2]).add(inFig(js[2]).sub(inFig(js[1])).multiplyScalar(0.8))
        hands[side].push(markerAt(js[2], tip))
      }
    }
    const feet: THREE.Object3D[] = []
    const mid = inFig(part('hips'))
    for (const side of ['l', 'r'] as const) {
      const foot = part(side === 'r' ? 'r_foot' : 'l_foot')
      const [ballName, leafName] = toeBones[rig](side)
      const ball = bones.get(norm(ballName)) ?? foot
      const leaf = leafName ? bones.get(norm(leafName)) : undefined
      const fwd = inFig(ball).sub(inFig(foot)).setY(0)
      if (fwd.lengthSq() < 1e-8) fwd.set(0, 0, 1)
      fwd.normalize()
      const tipPoint = leaf ? inFig(leaf) : inFig(ball).add(fwd.clone().multiplyScalar(0.05))
      const medial = new THREE.Vector3(Math.sign(mid.x - inFig(foot).x) || (side === 'l' ? -1 : 1), 0, 0)
      const ground = Math.min(inFig(ball).y, tipPoint.y)
      feet.push(markerAt(leaf ?? ball, tipPoint.clone().add(medial.clone().multiplyScalar(0.02))))                          // big toe
      feet.push(markerAt(ball, inFig(ball).lerp(tipPoint, 0.6).add(medial.clone().multiplyScalar(-0.03))))                 // small toe
      feet.push(markerAt(foot, inFig(foot).setY(ground).add(fwd.clone().multiplyScalar(-0.05))))                            // heel
    }
    wholebody = { feet, left: hands.l, right: hands.r }
  }
  follow(J)
  return { object, bones, follow, handPreset, wholebody }
}
