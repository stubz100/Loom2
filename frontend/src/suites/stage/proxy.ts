// E23d (D105): a figure's shadow proxy — a mesh shaped like its character (the app's image → mesh job on the animation reference, D84),
// bound to the figure's twelve joints so it follows every pose, and seen only by the light: it casts the character's outline into Stage's
// shadows while the dummy casts nothing. "It doesn't have to be perfect, just a dummy to cast close enough shadows" (the author).
//
// The binding: the figure posed in the reference's A-pose; the mesh scaled to the figure's height, stood on the floor under it, its
// left-right axis turned onto the figure's (front and back cast the same shadow); each vertex weighted to its two nearest limb segments by
// inverse squared distance — a THREE.SkinnedMesh whose bones are the figure's joints.
// Unseen: its material writes no colour and no depth (the viewport shows only its shadow); the passes, which override every material,
// render twice — once with the proxies for the shadow map, once without them and that map kept (engine.shotWith).
import * as THREE from 'three'
import { applyPose, JOINTS, POSES, type Joint, type Limbs } from './builders'

/** The reference's stance (turnTest.ts): arms a little away from the body. */
export const A_POSE: Record<string, number[]> = { r_shoulder: [0, 0, -22], l_shoulder: [0, 0, 22], r_elbow: [0, 0, 0], l_elbow: [0, 0, 0] }

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

export interface Proxy { meshes: THREE.SkinnedMesh[]; dispose: () => void }

/** Bind `model` (a loaded GLB scene, not in the scene graph) to the figure; returns the skinned meshes, to be added to the scene's root. */
export function bindProxy(model: THREE.Object3D, J: Record<Joint, THREE.Object3D>, limbs: Limbs, figureRoot: THREE.Object3D,
                          pose: { preset?: string | null; joints?: Record<string, number[]> } | null): Proxy {
  // the figure in the A-pose, its world-space segments and extent
  applyPose(J, POSES.stand, A_POSE)
  figureRoot.updateMatrixWorld(true)
  const segs = JOINTS.map((j) => { const a = J[j].getWorldPosition(new THREE.Vector3()); const b = segmentEnd(j, limbs).applyMatrix4(J[j].matrixWorld); return { j, a, b } })
  const fig = new THREE.Box3()
  for (const s of segs) { fig.expandByPoint(s.a); fig.expandByPoint(s.b) }
  const floorY = Math.min(...segs.map((s) => s.b.y)) - 0.03
  const topY = J.head.getWorldPosition(new THREE.Vector3()).y + 0.24
  const centre = J.root.getWorldPosition(new THREE.Vector3())
  const right = J.r_shoulder.getWorldPosition(new THREE.Vector3()).sub(J.l_shoulder.getWorldPosition(new THREE.Vector3())).setY(0).normalize()
  // the model: its own transforms baked, scaled to the figure's height, its wider horizontal axis onto the figure's left-right axis
  model.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(model, true)                  // SC3d: its vertices (a turned box would overstate the height)
  const size = box.getSize(new THREE.Vector3()), mid = box.getCenter(new THREE.Vector3())
  const s = (topY - floorY) / Math.max(1e-6, size.y)
  const wideAxis = size.x >= size.z ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 0, 1)
  // a mesh made from a front view faces +Z with the character's left at +X: its +X goes onto the figure's left (−right)
  const turn = new THREE.Quaternion().setFromUnitVectors(wideAxis, right.clone().negate())
  const place = new THREE.Matrix4().compose(new THREE.Vector3(centre.x, floorY, centre.z), turn, new THREE.Vector3(s, s, s))
    .multiply(new THREE.Matrix4().makeTranslation(-mid.x, -box.min.y, -mid.z))
  const bones = JOINTS.map((j) => J[j])
  const skeleton = new THREE.Skeleton(bones as unknown as THREE.Bone[])
  skeleton.calculateInverses()                                             // the bind pose: the A-pose, now
  const material = new THREE.MeshBasicMaterial({ color: 0x888888, colorWrite: false, depthWrite: false })
  const meshes: THREE.SkinnedMesh[] = []
  model.traverse((o) => {
    const m = o as THREE.Mesh
    if (!m.isMesh || !m.geometry) return
    const g = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone())
    g.applyMatrix4(place.clone().multiply(m.matrixWorld))
    for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal') g.deleteAttribute(k)
    const pos = g.attributes.position, n = pos.count
    const idx = new Uint16Array(n * 4), wts = new Float32Array(n * 4)
    const p = new THREE.Vector3()
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
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4))
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(wts, 4))
    const sm = new THREE.SkinnedMesh(g, material)
    sm.bind(skeleton, new THREE.Matrix4())
    sm.castShadow = true; sm.receiveShadow = false
    sm.frustumCulled = false
    sm.userData.proxy = true
    meshes.push(sm)
  })
  // back to the figure's own pose
  applyPose(J, POSES[pose?.preset ?? 'stand'] ?? POSES.stand, pose?.joints)
  figureRoot.updateMatrixWorld(true)
  return { meshes, dispose: () => { for (const m of meshes) { m.geometry.dispose(); m.removeFromParent() } material.dispose() } }
}
