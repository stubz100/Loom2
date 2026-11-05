// RG5 check (D191; the author: "the clay hands twist their thumbs backwards on hand poses"): where each preset takes a character's
// fingertips — the thumb's and the index's — in the open hand's palm frame (ex toward the thumb, ey toward the middle knuckle, n the palm's
// side: where a curled index goes). A thumb curling backwards moves its tip to −n. On the real starter mannequin; optional close-ups.
// The browser half of engine/spikes/rg5_thumb.cjs.
import * as THREE from 'three'
import { DEFAULT_BODY, type Body } from '../suites/stage/body'
import { mannequin, POSES } from '../suites/stage/builders'
import type { HandShapes } from '../suites/stage/clayHand'
import { HAND_PRESETS, makeDetailed } from '../suites/stage/detailed'
import { HAND_EDGES } from '../suites/stage/passes'
import { stanceOf } from '../suites/stage/proxy'

export interface RG5ThumbInput { body: Body; points: Record<string, unknown> | null; own: boolean; views?: boolean }

export async function thumbCurl(input: RG5ThumbInput): Promise<Record<string, unknown>> {
  const { mannequinClone } = await import('../suites/stage/motion/mannequins')
  const body = { ...DEFAULT_BODY, ...input.body } as Body
  const shape = input.own ? ((input.body as { hand_shape?: HandShapes | null }).hand_shape ?? null) : null
  const stance = stanceOf(input.points as never)
  const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const fig = mannequin(clay, POSES.stand, stance, body)
  const holder = new THREE.Group(); holder.add(fig.root); holder.updateMatrixWorld(true)
  fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
  const { root, rig } = await mannequinClone(body.figure ?? 'female', clay)
  const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head, handRest: { preset: 'open', curl: 1 }, feetOut: body.feet_out, handShape: shape })
  d.handsOnly(!!shape)
  const scene = new THREE.Scene(); scene.add(holder); scene.background = new THREE.Color(0x1d1e22)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.5)); const key = new THREE.DirectionalLight(0xffffff, 1.3); key.position.set(1, 2, 3); scene.add(key)
  const out: Record<string, unknown> = {}, views: Record<string, string> = {}
  const pointsOf = (side: 'r' | 'l', preset: (typeof HAND_PRESETS)[number]) => {
    d.follow(fig.joints, { ...d.handPreset('r', preset), ...d.handPreset('l', preset) }); holder.updateMatrixWorld(true)
    return (side === 'r' ? d.wholebody!.right : d.wholebody!.left).map((m) => m.getWorldPosition(new THREE.Vector3()))
  }
  const renderer = input.views ? new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }) : null
  renderer?.setSize(360, 360)
  for (const side of ['r', 'l'] as const) {
    const open = pointsOf(side, 'open'), fist = pointsOf(side, 'fist')
    const W = open[0], ey = open[9].clone().sub(W).normalize()
    const ex = open[5].clone().sub(open[17]); ex.addScaledVector(ey, -ex.dot(ey)).normalize()
    const n = ex.clone().cross(ey).normalize()
    if (fist[8].clone().sub(open[8]).dot(n) < 0) n.negate()                  // the palm's side: where a curled index goes
    const L = W.distanceTo(open[9])
    const rows: Record<string, unknown> = {}
    for (const preset of HAND_PRESETS) {
      const p = pointsOf(side, preset)
      const rel = (i: number) => { const v = p[i].clone().sub(W); return [v.dot(ex) / L, v.dot(ey) / L, v.dot(n) / L].map((x) => +x.toFixed(2)) }
      const mv = (i: number) => { const v = p[i].clone().sub(open[i]); return [v.dot(ex) / L, v.dot(ey) / L, v.dot(n) / L].map((x) => +x.toFixed(2)) }
      // the thumb's last segment against the palm's side: + it points into the palm, − away from it
      const seg = p[4].clone().sub(p[3]).normalize()
      rows[preset] = { thumb_tip: rel(4), thumb_moved: mv(4), index_moved: mv(8), thumb_tip_to_index_tip: +(p[4].distanceTo(p[8]) / L).toFixed(2), last_seg_n: +seg.dot(n).toFixed(2) }
      if (renderer && side === 'r' && ['open', 'relaxed', 'fist', 'pinch'].includes(preset)) {
        const centre = W.clone().lerp(open[12], 0.5)
        const dots = new THREE.Group()
        p.forEach((q) => { const s = new THREE.Mesh(new THREE.SphereGeometry(0.003, 8, 6), new THREE.MeshBasicMaterial({ color: 0x3a8bff, depthTest: false })); s.position.copy(q); s.renderOrder = 10; dots.add(s) })
        const seg2: number[] = []; for (const [a, b] of HAND_EDGES) seg2.push(...p[a].toArray(), ...p[b].toArray())
        const lines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(seg2, 3)), new THREE.LineBasicMaterial({ color: 0xffc94a, depthTest: false })); lines.renderOrder = 9
        scene.add(dots, lines)
        const cam = new THREE.PerspectiveCamera(30, 1, 0.01, 20)
        for (const [view, dir] of [['palm', n], ['thumbside', ex], ['edge', ex.clone().add(n).normalize()]] as const) {
          cam.position.copy(centre).addScaledVector(dir, Math.max(0.3, L * 3.2)); cam.up.copy(ey).negate(); cam.lookAt(centre)
          renderer.render(scene, cam)
          views[`${preset}_${view}`] = renderer.domElement.toDataURL('image/png').split(',')[1]
        }
        scene.remove(dots, lines)
      }
    }
    out[side] = rows
  }
  renderer?.dispose()
  return { measures: out, views }
}
