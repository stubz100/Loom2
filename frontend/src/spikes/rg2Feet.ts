// RG2b check (D188 F3, F5): a character walking a library clip, its right foot from the side at a few frames — its shell's shoe bent at
// the ankle and the ball from its foot shape (body.foot_shape) and the guide's heel and toes (the Detailed figure's feet, turned by the
// clip's foot turns), against the same frames with the feet held (no turns, as before RG2b). The browser half of
// engine/spikes/rg2_feet.cjs, loaded on the dev page; returns PNGs and the turns.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DEFAULT_BODY, type Body } from '../suites/stage/body'
import { applyPose, mannequin, POSES } from '../suites/stage/builders'
import { makeDetailed } from '../suites/stage/detailed'
import { feetExtra } from '../suites/stage/motion/retarget'
import { bindProxy, stanceOf, type FootShapes } from '../suites/stage/proxy'

export interface RG2FeetInput { body: Body; points: { pose?: number[][]; canvas?: number[] } | null; meshUrl: string; clip: string; frames: number[]; footShape?: FootShapes | null }

export async function feetWalking(input: RG2FeetInput): Promise<Record<string, unknown>> {
  const [{ mannequinClone }, lib] = await Promise.all([import('../suites/stage/motion/mannequins'), import('../suites/stage/motion/library')])
  const body = { ...DEFAULT_BODY, ...input.body, hand_rest: { ...DEFAULT_BODY.hand_rest, ...(input.body.hand_rest ?? {}) } } as Body
  const feetShape = input.footShape ?? (input.body as { foot_shape?: FootShapes | null }).foot_shape ?? null   // a shape given (not yet on the version) wins
  const stance = stanceOf(input.points as never)
  const files = (await lib.listFiles()).items
  let clip: Awaited<ReturnType<typeof lib.clipsOf>>[number] | undefined
  for (const f of files) { clip = (await lib.clipsOf(f).catch(() => [])).find((c) => c.name === input.clip); if (clip) break }
  if (!clip) throw new Error(`no clip ${input.clip}`)
  const r = await lib.retargetClip(clip, { fps: 24, hip: 0.91, inPlace: true })
  const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const fig = mannequin(clay, POSES.stand, stance, body)
  const holder = new THREE.Group(); holder.add(fig.root)
  const scene = new THREE.Scene(); scene.add(holder); scene.background = new THREE.Color(0x2a2a2e)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.4)); const key = new THREE.DirectionalLight(0xffffff, 1.5); key.position.set(-3, 2, 1); scene.add(key)
  holder.updateMatrixWorld(true)
  fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
  const { root, rig } = await mannequinClone(body.figure ?? 'female', clay)
  const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head, handRest: body.hand_rest, feetOut: body.feet_out })
  const shell = await new GLTFLoader().loadAsync(input.meshUrl)
  const px = bindProxy(shell.scene, fig.joints, fig.limbs, holder, { preset: 'stand', joints: stance }, { stance, visible: true, hands: true, points: input.points as never, markers: fig.markers,
    feet: feetShape ? { shape: feetShape, size: body.feet } : null })
  for (const m of px.meshes) { m.material = clay; scene.add(m) }
  d.handsOnly(true)
  // where the shell's own right foot is at bind: its vertices low and near the right ankle (percentiles of x, y, z)
  let shellFoot: unknown = null
  const A0 = px.footPoints.r?.ankle
  if (A0) {
    const low: THREE.Vector3[] = []
    for (const m of px.meshes) { const p = m.geometry.attributes.position; for (let v = 0; v < p.count; v++) { const q = new THREE.Vector3().fromBufferAttribute(p, v); if (q.y < A0.y + 0.06 && Math.abs(q.x - A0.x) < 0.2 && Math.abs(q.z - A0.z) < 0.45) low.push(q) } }
    const pct = (k: 'x' | 'y' | 'z', f: number) => { const s = low.map((q) => q[k]).sort((a, b) => a - b); return +(s[Math.floor(f * (s.length - 1))] ?? NaN).toFixed(3) }
    shellFoot = { n: low.length, x: [pct('x', 0.02), pct('x', 0.5), pct('x', 0.98)], y: [pct('y', 0.02), pct('y', 0.5)], z: [pct('z', 0.02), pct('z', 0.5), pct('z', 0.98)] }
  }
  const dotMat = new THREE.MeshBasicMaterial({ color: 0x3060ff, depthTest: false }), rigMat = new THREE.MeshBasicMaterial({ color: 0xffb020, depthTest: false })
  const dots = d.wholebody ? d.wholebody.feet.slice(3).map(() => { const s = new THREE.Mesh(new THREE.SphereGeometry(0.008, 10, 8), dotMat); s.renderOrder = 10; scene.add(s); return s }) : []
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); renderer.setSize(360, 300)
  const cam = new THREE.PerspectiveCamera(30, 360 / 300, 0.01, 20)
  const out: Record<string, unknown> = { shellFoot, views: {} as Record<string, string>, turns: [] as unknown[], frames: r.frames.length, footPoints: px.footPoints.r ? Object.fromEntries(Object.entries(px.footPoints.r).map(([k, v]) => [k, v instanceof THREE.Vector3 ? v.toArray().map((x) => +x.toFixed(3)) : v])) : null }
  void rigMat
  for (const turnsOn of [true, false]) for (const i of input.frames) {
    const f = r.frames[Math.min(i, r.frames.length - 1)]
    const extra = turnsOn ? feetExtra(f) ?? null : null
    applyPose(fig.joints, POSES.stand, f.joints); fig.root.position.y = f.offset[1]; holder.updateMatrixWorld(true)
    d.follow(fig.joints, extra); px.feet(extra); holder.updateMatrixWorld(true)
    if (d.wholebody) d.wholebody.feet.slice(3).forEach((m, k) => dots[k].position.copy(m.getWorldPosition(new THREE.Vector3())))
    const ankle = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.r_knee.matrixWorld)
    const target = ankle.clone().add(new THREE.Vector3(0, -0.04, 0.06))
    cam.position.copy(target).add(new THREE.Vector3(-0.9, 0.05, 0)); cam.lookAt(target)   // from the figure's right side
    renderer.render(scene, cam)
    ;(out.views as Record<string, string>)[`${turnsOn ? 'turned' : 'held'}_${i}`] = renderer.domElement.toDataURL('image/png').split(',')[1]
    // the shell's vertices nearest the rig's toe and ball (at bind), where they are now — and the bones they follow most
    const probe: Record<string, unknown> = {}
    for (const [name, at] of [['toe', px.footPoints.r?.toe], ['ball', px.footPoints.r?.ball]] as const) {
      if (!at) continue
      let best = Infinity, now = new THREE.Vector3(), bone = -1
      for (const m of px.meshes) {
        m.skeleton.update()
        const pos = m.geometry.attributes.position, si = m.geometry.attributes.skinIndex, sw = m.geometry.attributes.skinWeight
        for (let v = 0; v < pos.count; v++) {
          const dist = new THREE.Vector3().fromBufferAttribute(pos, v).distanceTo(at)
          if (dist < best) { best = dist; m.getVertexPosition(v, now); let w = 0; for (let k = 0; k < 4; k++) if (sw.getComponent(v, k) > w) { w = sw.getComponent(v, k); bone = si.getComponent(v, k) } }
        }
      }
      probe[name] = { off_cm: +(best * 100).toFixed(1), now: now.toArray().map((x) => +x.toFixed(3)), bone }
    }
    ;(out.turns as unknown[]).push({ frame: i, turned: turnsOn, r: f.feet?.r.map((v) => +v.toFixed(1)), probe })
  }
  renderer.dispose(); px.dispose()
  return out
}
