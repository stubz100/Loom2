// RG2 check (D187 R3, R5): a character's right hand close up, on the real starter mannequin — with its own hand shape (body.hand_shape: the
// clay hand on the shaped bones, the guide's 21 points on them) and without (the mannequin's hand), open and at rest, with its shell bound as
// Clay binds it. The browser half of engine/spikes/rg2_hands.cjs, loaded on the dev page; returns PNGs and the measures.
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DEFAULT_BODY, type Body } from '../suites/stage/body'
import { applyPose, mannequin, POSES } from '../suites/stage/builders'
import type { HandShapes } from '../suites/stage/clayHand'
import { makeDetailed } from '../suites/stage/detailed'
import { HAND_EDGES } from '../suites/stage/passes'
import { bindProxy, stanceOf } from '../suites/stage/proxy'

export interface RG2Input { body: Body; points: { pose?: number[][]; canvas?: number[]; hand_left?: number[][]; hand_right?: number[][] } | null; meshUrl: string | null }

export async function handCloseUps(input: RG2Input): Promise<Record<string, unknown>> {
  const { mannequinClone } = await import('../suites/stage/motion/mannequins')
  const body = { ...DEFAULT_BODY, ...input.body, hand_rest: { ...DEFAULT_BODY.hand_rest, ...(input.body.hand_rest ?? {}) } } as Body
  const shape = (input.body as { hand_shape?: HandShapes | null }).hand_shape ?? null
  const stance = stanceOf(input.points as never)
  const shell = input.meshUrl ? await new GLTFLoader().loadAsync(input.meshUrl) : null
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); renderer.setSize(420, 420)
  const out: Record<string, unknown> = { views: {} as Record<string, string>, measures: {} as Record<string, unknown> }
  for (const own of [true, false]) {
    for (const preset of ['open', 'relaxed'] as const) {
      const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
      const fig = mannequin(clay, POSES.stand, stance, body)
      const holder = new THREE.Group(); holder.add(fig.root)
      const scene = new THREE.Scene(); scene.add(holder); scene.background = new THREE.Color(0x2a2a2e)
      scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.4)); const key = new THREE.DirectionalLight(0xffffff, 1.5); key.position.set(1, 2, 3); scene.add(key)
      holder.updateMatrixWorld(true)
      fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
      const { root, rig } = await mannequinClone(body.figure ?? 'female', clay)
      const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head,
        handRest: { ...body.hand_rest, preset }, feetOut: body.feet_out, handShape: own ? shape : null })
      if (shell) {
        const px = bindProxy(shell.scene.clone(true), fig.joints, fig.limbs, holder, { preset: 'stand', joints: stance }, { stance, visible: true, hands: true, points: input.points, markers: fig.markers })
        for (const m of px.meshes) { m.material = clay; m.userData.shell = true; scene.add(m) }
      }
      d.handsOnly(!!shell)
      applyPose(fig.joints, POSES.stand, stance); holder.updateMatrixWorld(true)
      d.follow(fig.joints, null); holder.updateMatrixWorld(true)
      // the guide's right hand: points and edges, drawn over everything
      const pts = d.wholebody!.right.map((m) => m.getWorldPosition(new THREE.Vector3()))
      const dots = new THREE.Group()
      const dotMat = new THREE.MeshBasicMaterial({ color: 0x3060ff, depthTest: false }), hidden = new THREE.MeshBasicMaterial({ color: 0xff3030, depthTest: false })
      pts.forEach((p, i) => { const s = new THREE.Mesh(new THREE.SphereGeometry(0.0035, 8, 6), d.wholebody!.right[i].userData.hidden ? hidden : dotMat); s.position.copy(p); s.renderOrder = 10; dots.add(s) })
      const seg: number[] = []; for (const [a, b] of HAND_EDGES) seg.push(...pts[a].toArray(), ...pts[b].toArray())
      const lines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(seg, 3)), new THREE.LineBasicMaterial({ color: 0xffd040, depthTest: false }))
      lines.renderOrder = 9
      scene.add(dots, lines)
      const wrist = pts[0], mid = pts[9]
      const centre = wrist.clone().lerp(pts[12], 0.5)
      const cam = new THREE.PerspectiveCamera(30, 1, 0.01, 20)
      const name = `${own ? 'own' : 'mannequin'}_${preset}`
      const normal = pts[5].clone().sub(pts[17]).cross(pts[9].clone().sub(wrist)).normalize()   // straight at the palm (or its back)
      for (const [view, dir] of [['front', new THREE.Vector3(0, 0, 1)], ['palm', normal]] as const) {
        cam.position.copy(centre).addScaledVector(dir, 0.62); cam.up.set(0, 1, 0); cam.lookAt(centre)
        scene.traverse((o) => { if (o.userData.shell) o.visible = view === 'front' })   // the palm's camera stands where the robe is
        renderer.render(scene, cam)
        ;(out.views as Record<string, string>)[`${name}_${view}`] = renderer.domElement.toDataURL('image/png').split(',')[1]
      }
      const palm = wrist.distanceTo(mid)
      const len = (i: number) => pts[i].distanceTo(pts[i + 1]) + pts[i + 1].distanceTo(pts[i + 2]) + pts[i + 2].distanceTo(pts[i + 3])
      ;(out.measures as Record<string, unknown>)[name] = { palm_cm: +(palm * 100).toFixed(1), middle_palms: +(len(9) / palm).toFixed(3), index_palms: +(len(5) / palm).toFixed(3),
        clay_pieces: d.clayHands.length, clay_shown: d.clayHands.filter((m) => m.visible).length }
      renderer.renderLists.dispose()
    }
  }
  renderer.dispose()
  return out
}
