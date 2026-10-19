// CA1: the retargeter on the real starter set (Quaternius UAL 1 + 2, CC0) — every figure limb and the spine point exactly where the source's
// segment points, at every frame of seven clips (walks, sitting, a climb, aiming, harvesting). Opt-in: the starter set is not in CI and the
// run takes ≈ 20 s. LOOM2_MOTION_STARTER=F:/loom2-models/motion npx vitest run src/suites/stage/motion/retarget.starter.test.ts
import { existsSync, readFileSync } from 'node:fs'
import * as THREE from 'three'
import { expect, it } from 'vitest'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { applyPose, mannequin, POSES } from '../builders'
import { RIGS, norm, retarget } from './retarget'
const STARTER = process.env.LOOM2_MOTION_STARTER ?? ''
const files = [`${STARTER}/quaternius-ual1/Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb`,
  `${STARTER}/quaternius-ual2/Universal Animation Library 2 [Standard]/Unreal-Godot/UAL2_Standard.glb`]
// our joint → [source bone, source child] for the direction compare
const PAIRS: Record<string, [string, string, string]> = {   // our joint, our child joint (or marker index), src parts
  r_shoulder: ['r_elbow', 'r_upper', 'r_lower'], r_elbow: ['', 'r_lower', 'r_hand'], r_hip: ['r_knee', 'r_thigh', 'r_calf'], r_knee: ['', 'r_calf', 'r_foot'],
  l_shoulder: ['l_elbow', 'l_upper', 'l_lower'], l_hip: ['l_knee', 'l_thigh', 'l_calf'], spine: ['neck', 'spineBase', 'neck'],
}
it.skipIf(!STARTER || !existsSync(files[0]))("the starter set's clips: every segment points where the source's does", async () => {
  const mat = new THREE.MeshBasicMaterial()
  for (const f of files) {
    const b = readFileSync(f); const ab = new ArrayBuffer(b.length); new Uint8Array(ab).set(b)
    const g = await new GLTFLoader().parseAsync(ab, '')
    const names = new Map<string, THREE.Object3D>(); g.scene.traverse((o) => names.set(norm(o.name), o))
    const rig = f.includes('UAL2') ? 'unreal' : 'rigify'
    const bone = (part: string) => names.get(norm((RIGS as any)[rig][part]))!
    for (const name of ['Walk_Loop', 'Sitting_Enter', 'Idle_Loop', 'Walk_Carry_Loop', 'ClimbUp_1m_RM', 'Pistol_Aim_Neutral', 'Farm_Harvest']) {
      const c = g.animations.find((x) => x.name === name)
      if (!c) continue
      const r = retarget(g.scene, c, { fps: 24, hip: 0.91 })
      // replay the source to compare world directions frame by frame

      const fig = mannequin(mat, POSES.stand)
      const errs: Record<string, number> = {}
      // turn: source right → our right (-X)
      g.scene.updateMatrixWorld(true)
      const pr = new THREE.Vector3(), pl = new THREE.Vector3()
      bone('r_upper').getWorldPosition(pr); bone('l_upper').getWorldPosition(pl)
      const right = pr.clone().sub(pl).setY(0).normalize()
      const turn = new THREE.Quaternion().setFromUnitVectors(right, new THREE.Vector3(-1, 0, 0))
      const mixer = new THREE.AnimationMixer(g.scene); const a = mixer.clipAction(c); a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; a.play()
      for (let i = 0; i < r.frames.length; i++) {
        mixer.setTime(Math.min(c.duration, i / 24)); g.scene.updateMatrixWorld(true)
        applyPose(fig.joints, POSES.stand, r.frames[i].joints); fig.root.updateMatrixWorld(true)
        for (const [j, [child, sp, sc]] of Object.entries(PAIRS)) {
          const s0 = new THREE.Vector3(), s1 = new THREE.Vector3(); bone(sp).getWorldPosition(s0); bone(sc).getWorldPosition(s1)
          const sd = s1.sub(s0).applyQuaternion(turn).normalize()
          const o0 = new THREE.Vector3(); (fig.joints as any)[j].getWorldPosition(o0)
          let o1: THREE.Vector3
          if (child) { o1 = new THREE.Vector3(); (fig.joints as any)[child].getWorldPosition(o1) }
          else { o1 = new THREE.Vector3(0, -0.27, 0); (fig.joints as any)[j].localToWorld(o1) }
          const od = o1.sub(o0).normalize()
          const deg = (Math.acos(Math.max(-1, Math.min(1, sd.dot(od)))) * 180) / Math.PI
          errs[j] = Math.max(errs[j] ?? 0, deg)
        }
      }
      console.log(f.split('/').pop()!.slice(0, 12), name.padEnd(18), 'max direction error °', Object.entries(errs).map(([k, v]) => `${k} ${v.toFixed(1)}`).join(' · '))
      for (const [j, v] of Object.entries(errs)) expect(v, `${name} · ${j}`).toBeLessThan(0.5)
    }
  }
}, 180000)

it.skipIf(!STARTER || !existsSync(files[0]))("the starter set's walks in place, foot-locked: forward travel, the planted foot within 2 cm", async () => {
  const { footLock, footSlide } = await import('./footlock')
  const b = readFileSync(files[0]); const ab = new ArrayBuffer(b.length); new Uint8Array(ab).set(b)
  const g = await new GLTFLoader().parseAsync(ab, '')
  for (const name of ['Walk_Loop', 'Walk_Formal_Loop', 'Jog_Fwd_Loop']) {
    const c = g.animations.find((x) => x.name === name)!
    const r = retarget(g.scene, c, { fps: 24, hip: 0.91 })
    const locked = footLock(r.frames)
    const travel = locked[locked.length - 1].offset[2] - locked[0].offset[2]
    console.log(name, 'slide raw', footSlide(r.frames).toFixed(3), 'locked', footSlide(locked).toFixed(3), 'travel', travel.toFixed(2), 'm in', (r.frames.length / 24).toFixed(2), 's')
    expect(footSlide(locked), name).toBeLessThan(0.02)
    expect(travel, name).toBeGreaterThan(0.5)
  }
}, 180000)

it.skipIf(!STARTER || !existsSync(files[0]))("the starter set's Walk_Loop along a curved path: the planted foot within 2 cm", async () => {
  const { footLock, keySlide } = await import('./footlock')
  const { repeatLoop } = await import('./bake')
  const { walkAlong } = await import('./walkpath')
  const b = readFileSync(files[0]); const ab = new ArrayBuffer(b.length); new Uint8Array(ab).set(b)
  const g = await new GLTFLoader().parseAsync(ab, '')
  const r = retarget(g.scene, g.animations.find((x) => x.name === 'Walk_Loop')!, { fps: 24, hip: 0.91 })
  const keys = walkAlong(footLock(repeatLoop(r.frames, 6)), { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, 0, [[0, 0], [0, 2], [2, 3.5], [3, 5.5]])
  const end = keys[keys.length - 1].transform.pos
  console.log('Walk_Loop on a curve: slide', keySlide(keys).toFixed(3), 'frames', keys.length, 'end', end[0].toFixed(2), end[2].toFixed(2))
  expect(keySlide(keys)).toBeLessThan(0.02)
}, 180000)
