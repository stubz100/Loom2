// RG5 check (D191; the author: "figure image and shell are not aligned 100%"): how the shell sits on the skeleton in depth — the front view
// places it by its picture (the nose, the soles), the depth by its bounding box's middle, which the hands held forward pull forward. For each
// joint the shell's depth through it (a ray along −Z: where it enters and leaves) and the joint's place in it (0 the front, 1 the back); the
// joints outside; the offset that puts the hips' section on the hips; the joints outside after it. The browser half of
// engine/spikes/rg5_depth.cjs (the GLB handed over as base64, no orchestrator asset needed).
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DEFAULT_BODY, type Body } from '../suites/stage/body'
import { JOINTS, mannequin, POSES } from '../suites/stage/builders'
import { bindProxy, insideShell, stanceOf } from '../suites/stage/proxy'

export interface RG5Input { body: Body; points: Record<string, unknown> | null; glb: string; shift?: number | null }

export async function shellDepth(input: RG5Input): Promise<Record<string, unknown>> {
  const body = { ...DEFAULT_BODY, ...input.body } as Body
  const bin = Uint8Array.from(atob(input.glb), (c) => c.charCodeAt(0)).buffer
  const gltf = await new GLTFLoader().parseAsync(bin, '')
  const stance = stanceOf(input.points as never)
  const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const fig = mannequin(clay, POSES.stand, stance, body)
  const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
  const px = bindProxy(gltf.scene, fig.joints, fig.limbs, g, { preset: 'stand', joints: stance }, { stance, visible: true, points: input.points as never, markers: fig.markers })
  const plain = px.meshes.map((m) => new THREE.Mesh(m.geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })))
  plain.forEach((m) => m.updateMatrixWorld(true))
  const named: [string, THREE.Vector3][] = [...JOINTS.map((j) => [j, fig.joints[j].getWorldPosition(new THREE.Vector3())] as [string, THREE.Vector3]),
    ['r_ankle', fig.markers[10].getWorldPosition(new THREE.Vector3())], ['l_ankle', fig.markers[13].getWorldPosition(new THREE.Vector3())]]
  const through = (p: THREE.Vector3) => {
    const hits = new THREE.Raycaster(new THREE.Vector3(p.x, p.y, p.z + 50), new THREE.Vector3(0, 0, -1)).intersectObjects(plain, false)
    return hits.length ? { front: hits[0].point.z, back: hits[hits.length - 1].point.z } : null
  }
  const rows: Record<string, unknown> = {}
  const offs: Record<string, number> = {}
  for (const [k, p] of named) {
    const t = through(p)
    if (!t) { rows[k] = 'no shell through it'; continue }
    const mid = (t.front + t.back) / 2
    offs[k] = mid - p.z
    rows[k] = { z: +p.z.toFixed(3), front: +t.front.toFixed(3), back: +t.back.toFixed(3), at: +((t.front - p.z) / Math.max(1e-6, t.front - t.back)).toFixed(2), off_cm: +((mid - p.z) * 100).toFixed(1), inside: insideShell(plain, p) }
  }
  const outside = (dz: number) => named.filter(([, p]) => !insideShell(plain, p.clone().add(new THREE.Vector3(0, 0, dz)))).map(([k]) => k)
  const hips = ['root', 'r_hip', 'l_hip'].map((k) => offs[k]).filter((x) => x !== undefined)
  const hipOff = hips.length ? hips.reduce((a, x) => a + x, 0) / hips.length : 0
  const box = new THREE.Box3(); for (const m of plain) box.expandByObject(m)
  const root = named[0][1]
  return { rows, box_mid_z_cm: +(((box.min.z + box.max.z) / 2 - root.z) * 100).toFixed(1), depth_cm: +((box.max.z - box.min.z) * 100).toFixed(1),
    outside_now: outside(0), hip_off_cm: +(hipOff * 100).toFixed(1), outside_hip_aligned: outside(hipOff),
    ...(input.shift != null ? { outside_shift: outside(input.shift) } : {}) }
}
