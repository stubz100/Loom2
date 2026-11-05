// RG2b (D188 F3, F5; D189): the feet turn — a clip's foot turns read rig-independently (the ankle against the shin, the ball against the
// foot), carried on the keys as a pose's extra (baked, thinned, mirrored), turning the Detailed figure's feet (the guide's toes) and a
// shell's rigged shoe at its ankle and ball (a stiff sole at the ankle only).
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from './body'
import { mannequin, POSES } from './builders'
import { mirrorFeet } from './blocks'
import { makeDetailed } from './detailed'
import { bakeKeys, thinKeys } from './motion/bake'
import { feetExtra, retarget } from './motion/retarget'
import { A_POSE, bindProxy, type FootShape } from './proxy'

const rad = THREE.MathUtils.degToRad

function rig() {
  const root = new THREE.Group(); root.name = 'Armature'
  const bone = (name: string, parent: THREE.Object3D, x: number, y: number, z: number) => { const b = new THREE.Bone(); b.name = name; b.position.set(x, y, z); parent.add(b); return b }
  const pelvis = bone('pelvis', root, 0, 1, 0)
  const sp1 = bone('spine_01', pelvis, 0, 0.1, 0), sp3 = bone('spine_03', sp1, 0, 0.3, 0)
  const neck = bone('neck_01', sp3, 0, 0.2, 0); bone('Head', neck, 0, 0.1, 0)
  for (const [side, sx] of [['r', -1], ['l', 1]] as const) {
    const up = bone(`upperarm_${side}`, sp3, sx * 0.2, 0.15, 0), low = bone(`lowerarm_${side}`, up, sx * 0.3, 0, 0); bone(`hand_${side}`, low, sx * 0.25, 0, 0)
    const th = bone(`thigh_${side}`, pelvis, sx * 0.1, -0.05, 0), calf = bone(`calf_${side}`, th, 0, -0.45, 0)
    const foot = bone(`foot_${side}`, calf, 0, -0.45, 0); const ball = bone(`ball_${side}`, foot, 0, -0.04, 0.12); bone(`ball_leaf_${side}`, ball, 0, 0, 0.05)
  }
  return root
}
const about = (axis: THREE.Vector3, deg: number) => new THREE.Quaternion().setFromAxisAngle(axis, rad(deg))
const X = new THREE.Vector3(1, 0, 0)

describe('RG2b: a clip\'s foot turns', () => {
  it('the ankle against the shin (toes down +) and the ball against the foot (toes up +), whatever the knee does', () => {
    const root = rig()
    const down20 = about(X, 20), up30 = about(X, -30), bend = about(X, -40)
    const clip = new THREE.AnimationClip('roll', 1, [
      new THREE.QuaternionKeyframeTrack('foot_r.quaternion', [0, 1], [0, 0, 0, 1, ...down20.toArray()]),
      new THREE.QuaternionKeyframeTrack('ball_r.quaternion', [0, 1], [0, 0, 0, 1, ...up30.toArray()]),
      new THREE.QuaternionKeyframeTrack('calf_l.quaternion', [0, 1], [0, 0, 0, 1, ...bend.toArray()]),   // the left knee bends, its foot rides along
    ])
    const r = retarget(root, clip, { fps: 4, hip: 0.91 })
    const last = r.frames[r.frames.length - 1].feet!
    expect(r.frames[0].feet).toEqual({ r: [expect.closeTo(0, 3), expect.closeTo(0, 3)], l: [expect.closeTo(0, 3), expect.closeTo(0, 3)] })
    expect(last.r[0]).toBeCloseTo(20, 1); expect(last.r[1]).toBeCloseTo(30, 1)
    expect(last.l[0]).toBeCloseTo(0, 1); expect(last.l[1]).toBeCloseTo(0, 1)
  })

  it('ride on the keys as extra — baked, kept by the thinning, swapped by a mirror', () => {
    const frames = [0, 10, 20, 10, 0].map((a) => ({ joints: { root: [0, 0, 0] } as never, offset: [0, 0, 0] as [number, number, number], feet: { r: [a, a / 2] as [number, number], l: [0, 0] as [number, number] } }))
    expect(feetExtra(frames[2])).toEqual({ r_ankle: [20, 0, 0], r_ball: [10, 0, 0], l_ankle: [0, 0, 0], l_ball: [0, 0, 0] })
    const keys = bakeKeys(frames, { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, 0)
    expect(keys[2].pose!.extra!.r_ankle).toEqual([20, 0, 0])
    expect(thinKeys(keys).map((k) => k.frame)).toEqual([0, 2, 4])                // only the feet move: their turns keep the middle key
    expect(mirrorFeet({ r_ankle: [5, 0, 0], l_ball: [7, 0, 0], foot_r: [1, 2, 3] })).toEqual({ l_ankle: [5, 0, 0], r_ball: [7, 0, 0], foot_r: [1, 2, 3] })
    expect(feetExtra({})).toBeUndefined()
  })
})

describe('RG2b: the feet turn on the figure', () => {
  it('the Detailed figure\'s toes (the guide\'s) go down with the ankle and up with the ball', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root); holder.updateMatrixWorld(true)
    const d = makeDetailed(rig(), 'unreal', holder, fig.joints, fig.limbs)
    const toe = () => { holder.updateMatrixWorld(true); return d.wholebody ? d.wholebody.feet[3].getWorldPosition(new THREE.Vector3()) : d.bones.get('ballleafr')!.getWorldPosition(new THREE.Vector3()) }
    d.follow(fig.joints, null); const rest = toe()
    d.follow(fig.joints, { r_ankle: [30, 0, 0] }); const down = toe()
    d.follow(fig.joints, { r_ball: [30, 0, 0] }); const up = toe()
    expect(down.y).toBeLessThan(rest.y - 0.02)
    expect(up.y).toBeGreaterThan(rest.y + 0.005)
    d.follow(fig.joints, { l_ankle: [30, 0, 0] })
    expect(toe().distanceTo(rest)).toBeLessThan(1e-6)                            // the other foot's turn leaves this one
  })

  it('a shell\'s shoe bends at its ankle and ball from the foot\'s shape; a stiff sole at the ankle only', () => {
    const shape: FootShape = { pitch: 6, ankle_up: 0.44, ankle_at: 0.2, heel_up: 0.05, toe_up: 0.05, ball_at: 0.72, length_leg: null }
    const bound = (stiff: boolean) => {
      const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, A_POSE, DEFAULT_BODY)
      const root = new THREE.Group(); root.add(fig.root); root.updateMatrixWorld(true)
      const statue = new THREE.Group()
      statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.7, 0.25, 6, 30, 4).translate(0, 0.95, 0)))   // the body
      for (const x of [-0.09, 0.09]) statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.1, 0.3, 3, 3, 10).translate(x, 0.05, 0.07)))   // the shoes, toes forward
      const px = bindProxy(statue, fig.joints, fig.limbs, root, { preset: 'stand', joints: A_POSE }, { visible: true, markers: fig.markers, feet: { shape: { right: { ...shape, stiff } } } })
      for (const m of px.meshes) root.add(m)
      return { px, root }
    }
    const { px, root } = bound(false)
    const toe = px.footPoints.r!.toe
    const nearest = () => {                                                      // the shell's vertex nearest the right toe, skinned now
      let best = Infinity, at = new THREE.Vector3()
      root.updateMatrixWorld(true)
      for (const m of px.meshes) {
        m.skeleton.update()
        const p = new THREE.Vector3()
        for (let i = 0; i < m.geometry.attributes.position.count; i++) {
          const rest = new THREE.Vector3().fromBufferAttribute(m.geometry.attributes.position, i)
          const dist = rest.distanceTo(toe)
          if (dist < best) { best = dist; m.getVertexPosition(i, p); at = p.clone() }
        }
      }
      return at
    }
    expect(px.footPoints.r!.ball).not.toBeNull()
    px.feet(null); const rest = nearest()
    px.feet({ r_ankle: [30, 0, 0] }); const down = nearest()
    px.feet({ r_ball: [30, 0, 0] }); const up = nearest()
    expect(down.y).toBeLessThan(rest.y - 0.02)                                   // toes down at the ankle
    expect(up.y).toBeGreaterThan(rest.y + 0.01)                                  // toes up at the ball
    const stiff = bound(true)
    expect(stiff.px.footPoints.r!.ball).toBeNull()
    stiff.px.feet(null)
    const before = stiff.px.meshes.map((m) => m.skeleton.bones.length)
    expect(before.every((n) => n === 12 + 2)).toBe(true)                        // the twelve and an ankle a foot (the left the right mirrored, stiff too)
    px.dispose(); stiff.px.dispose()
  })

  it('a foot whose ball and toe miss the shell (a robe, a hem, a splayed foot) is not rigged: the shoe rides on the shin as before', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, A_POSE, DEFAULT_BODY)
    const root = new THREE.Group(); root.add(fig.root); root.updateMatrixWorld(true)
    const statue = new THREE.Group()
    statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.7, 0.25, 6, 30, 4).translate(0, 0.95, 0)))
    statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.05, 0.2, 5, 2, 4).translate(0, 0.025, -0.25)))   // cloth on the floor behind, no shoes
    for (const x of [-0.6, 0.6]) statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.1).translate(x, 0.6, 0.3)))   // the box kept centred where the body is
    const shape: FootShape = { pitch: 6, ankle_up: 0.44, ankle_at: 0.2, heel_up: 0.05, toe_up: 0.05, ball_at: 0.72, length_leg: null }
    const px = bindProxy(statue, fig.joints, fig.limbs, root, { preset: 'stand', joints: A_POSE }, { visible: true, markers: fig.markers, feet: { shape: { right: shape } } })
    expect(px.footPoints.r!.rigged).toBe(false); expect(px.footPoints.r!.missed).toBeGreaterThan(0.06)
    expect(px.meshes[0].skeleton.bones.length).toBe(12)                         // the twelve alone
    px.feet({ r_ankle: [30, 0, 0] })                                             // a turn does nothing
    px.dispose()
  })
})
