// Spike E62 c (D188, proto01_rig 00 §9): does a shell's own shoe hold up when it bends at an ankle and a ball? The browser half of
// engine/spikes/e62_feet.cjs, loaded on the dev page. For one character (its body, the points its body was fitted to, its shell):
//   · binds the shell as the shots do (bindProxy: bone heat, in the reference's stance, placed by its picture);
//   · finds each foot on the shell — the ankle at the shin's end, the heel and the toe the shell's backmost and foremost points below the
//     ankle within 30 cm of it, the ball 72 % of the way from heel to toe, 3 cm over the sole;
//   · adds an ankle bone and a ball bone to each leg and weighs the whole shell again by bone heat over the 12 segments (the shin now
//     ending at the ankle) and the four new ones;
//   · bends them — the ankle 30° toes down and 20° toes up, the ball 30° (the heel lifted, the toes on the floor: a step's push-off) — and
//     measures the stretch of the shoe's triangles against the rest pose (each triangle's longest edge, posed over rest), rendering the side
//     view of the right foot for the sheet.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DEFAULT_BODY } from '../suites/stage/body'
import { applyPose, JOINTS, mannequin, POSES, type Body, type Joint } from '../suites/stage/builders'
import { bindProxy, heatWeights, stanceOf, type Segment } from '../suites/stage/proxy'

export interface E62FeetInput { name: string; body: Body; points: { pose?: number[][]; canvas?: number[] } | null; meshUrl: string }

const world = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())

export async function bendFeet(input: E62FeetInput): Promise<Record<string, unknown>> {
  const out: Record<string, unknown> = { name: input.name }
  const body = { ...DEFAULT_BODY, ...input.body, hand_rest: { ...DEFAULT_BODY.hand_rest, ...(input.body.hand_rest ?? {}) } } as Body
  const stanceJ = stanceOf(input.points as never)
  const mat = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const fig = mannequin(mat, POSES.stand, stanceJ, body)
  const J = fig.joints
  const holder = new THREE.Group(); holder.add(fig.root)
  const scene = new THREE.Scene(); scene.add(holder)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x555555, 1.5)); const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(3, 2, 1.5); scene.add(key)
  holder.updateMatrixWorld(true)
  fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
  const gltf = await new GLTFLoader().loadAsync(input.meshUrl)
  const px = bindProxy(gltf.scene, J, fig.limbs, holder, { preset: 'stand', joints: stanceJ }, { stance: stanceJ, visible: true, hands: true, points: input.points, markers: fig.markers })
  // the bind pose again: the stance, where px's positions are
  applyPose(J, POSES.stand, stanceJ); holder.updateMatrixWorld(true)
  const allPos: THREE.Vector3[] = []
  for (const m of px.meshes) { const p = m.geometry.attributes.position; for (let i = 0; i < p.count; i++) allPos.push(new THREE.Vector3().fromBufferAttribute(p, i)) }
  const fwd = new THREE.Vector3(0, 0, 1).transformDirection(holder.matrixWorld)
  const feet: Record<'r' | 'l', { ankle: THREE.Object3D; ball: THREE.Object3D; A: THREE.Vector3; B: THREE.Vector3; T: THREE.Vector3; H: THREE.Vector3 }> = {} as never
  for (const side of ['r', 'l'] as const) {
    const knee = J[`${side}_knee` as Joint]
    const A = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(knee.matrixWorld)
    const near = allPos.filter((p) => p.y < A.y + 0.04 && Math.hypot(p.x - A.x, p.z - A.z) < 0.35 && Math.abs(p.x - A.x) < 0.1)
    if (!near.length) throw new Error(`no shoe under the ${side} ankle`)
    const along = (p: THREE.Vector3) => p.clone().sub(A).dot(fwd)
    const sorted = [...near].sort((a, b) => along(a) - along(b))
    const T = sorted[Math.floor(sorted.length * 0.98)].clone()          // the toe and the heel: the far ends along the facing, not one stray vertex
    const H = sorted[Math.floor(sorted.length * 0.02)].clone()
    const sole = Math.min(...near.map((p) => p.y))
    const B = H.clone().lerp(T, 0.72); B.y = sole + 0.03; B.x = A.x
    const ankle = new THREE.Bone(); knee.add(ankle); ankle.position.copy(knee.worldToLocal(A.clone()))
    ankle.updateMatrixWorld(true)
    const ball = new THREE.Bone(); ankle.add(ball); ball.position.copy(ankle.worldToLocal(B.clone()))
    feet[side] = { ankle, ball, A, B, T: T.setX(A.x), H }
  }
  holder.updateMatrixWorld(true)
  // the segments: the 12, the shins now ending at the ankles, then each foot's ankle → ball and ball → toe
  const segs: Segment[] = px.segments.map((s) => (s.j === 'r_knee' ? { ...s, b: feet.r.A.clone() } : s.j === 'l_knee' ? { ...s, b: feet.l.A.clone() } : s))
  const extra: { bone: THREE.Object3D; seg: Segment }[] = []
  for (const side of ['r', 'l'] as const) {
    extra.push({ bone: feet[side].ankle, seg: { j: 'r_knee' as Joint, a: feet[side].A.clone(), b: feet[side].B.clone() } })
    extra.push({ bone: feet[side].ball, seg: { j: 'r_knee' as Joint, a: feet[side].B.clone(), b: feet[side].T.clone() } })
  }
  const bones = [...JOINTS.map((j) => J[j]), ...extra.map((x) => x.bone)]
  const skeleton = new THREE.Skeleton(bones as unknown as THREE.Bone[])
  skeleton.calculateInverses()
  const meshes: THREE.SkinnedMesh[] = []
  const t0 = performance.now()
  for (const m of px.meshes) {
    const g = m.geometry.clone()
    const { idx, wts } = heatWeights(g.attributes.position, [...segs, ...extra.map((x) => x.seg)])
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4))
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(wts, 4))
    const sm = new THREE.SkinnedMesh(g, mat); sm.bind(skeleton, new THREE.Matrix4()); sm.frustumCulled = false
    meshes.push(sm); scene.add(sm)
  }
  out.weigh_ms = Math.round(performance.now() - t0)
  // the shoe's triangles: those with a corner weighted to an ankle or a ball bone
  const footBone = new Set([12, 13, 14, 15])
  const restOf = meshes.map((sm) => { const p = sm.geometry.attributes.position; return Array.from({ length: p.count }, (_, i) => new THREE.Vector3().fromBufferAttribute(p, i)) })
  const inFoot = meshes.map((sm) => { const si = sm.geometry.attributes.skinIndex, sw = sm.geometry.attributes.skinWeight
    return Array.from({ length: si.count }, (_, i) => [0, 1, 2, 3].some((k) => footBone.has(si.getComponent(i, k)) && sw.getComponent(i, k) > 0.05)) })
  const dominant: Record<string, number> = {}                                  // which bone each shoe vertex follows most
  for (const sm of meshes) {
    const si = sm.geometry.attributes.skinIndex, sw = sm.geometry.attributes.skinWeight
    for (let i = 0; i < si.count; i++) {
      let best = 0, bi = -1
      for (let k = 0; k < 4; k++) if (sw.getComponent(i, k) > best) { best = sw.getComponent(i, k); bi = si.getComponent(i, k) }
      const name = bi >= 12 ? ['r_ankle', 'r_ball', 'l_ankle', 'l_ball'][bi - 12] : null
      if (name) dominant[name] = (dominant[name] ?? 0) + 1
    }
  }
  out.dominant = dominant
  out.points = { r: { A: feet.r.A.toArray().map((x) => +x.toFixed(3)), B: feet.r.B.toArray().map((x) => +x.toFixed(3)), T: feet.r.T.toArray().map((x) => +x.toFixed(3)), H: feet.r.H.toArray().map((x) => +x.toFixed(3)) } }
  const stretch = (): { p50: number; p99: number; max: number; tris: number } => {
    const r: number[] = []
    meshes.forEach((sm, mi) => {
      const p = sm.geometry.attributes.position, idx = sm.geometry.index
      const tri = (t: number, k: number) => (idx ? idx.getX(t * 3 + k) : t * 3 + k)
      const nt = (idx ? idx.count : p.count) / 3
      const v = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()]
      for (let t = 0; t < nt; t++) {
        const ids = [tri(t, 0), tri(t, 1), tri(t, 2)]
        if (!ids.some((i) => inFoot[mi][i])) continue
        ids.forEach((i, k) => sm.getVertexPosition(i, v[k]))
        const e0 = Math.max(restOf[mi][ids[0]].distanceTo(restOf[mi][ids[1]]), restOf[mi][ids[1]].distanceTo(restOf[mi][ids[2]]), restOf[mi][ids[2]].distanceTo(restOf[mi][ids[0]]))
        const e1 = Math.max(v[0].distanceTo(v[1]), v[1].distanceTo(v[2]), v[2].distanceTo(v[0]))
        if (e0 > 1e-5) r.push(e1 / e0)
      }
    })
    r.sort((a, b) => a - b)
    const q = (x: number) => +(r[Math.min(r.length - 1, Math.floor(x * r.length))] ?? 1).toFixed(2)
    return { p50: q(0.5), p99: q(0.99), max: +(r[r.length - 1] ?? 1).toFixed(2), tris: r.length }
  }
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); renderer.setSize(360, 300)
  scene.background = new THREE.Color(0xb8b8b8)
  const cam = new THREE.PerspectiveCamera(30, 360 / 300, 0.05, 20)
  const views: Record<string, string> = {}
  const snap = (name: string) => {
    holder.updateMatrixWorld(true)
    const A = world(feet.r.ankle)
    const side = new THREE.Vector3(-1, 0, 0).transformDirection(holder.matrixWorld)       // the figure's right side
    const mid = feet.r.H.clone().lerp(feet.r.T, 0.5); mid.y = A.y
    cam.position.copy(mid).addScaledVector(side, 0.9).add(new THREE.Vector3(0, 0.02, 0)); cam.lookAt(mid.x, mid.y - 0.01, mid.z)
    renderer.render(scene, cam)
    views[name] = renderer.domElement.toDataURL('image/png').split(',')[1]
  }
  const results: Record<string, unknown> = {}
  const bend = (name: string, ankleDeg: number, ballDeg: number) => {
    applyPose(J, POSES.stand)
    for (const s of ['r', 'l'] as const) { feet[s].ankle.rotation.set(THREE.MathUtils.degToRad(ankleDeg), 0, 0); feet[s].ball.rotation.set(THREE.MathUtils.degToRad(ballDeg), 0, 0) }
    holder.updateMatrixWorld(true)
    results[name] = stretch()
    snap(name)
  }
  bend('rest', 0, 0)
  bend('ankle_toes_down_30', 30, 0)
  bend('ankle_toes_up_20', -20, 0)
  bend('ball_push_off_30', 0, -30)
  out.feet = { r: { ankle_y: +feet.r.A.y.toFixed(3), heel_to_toe: +feet.r.H.distanceTo(feet.r.T).toFixed(3) }, l: { ankle_y: +feet.l.A.y.toFixed(3), heel_to_toe: +feet.l.H.distanceTo(feet.l.T).toFixed(3) } }
  out.stretch = results
  out.views = views
  renderer.dispose(); px.dispose()
  return out
}
