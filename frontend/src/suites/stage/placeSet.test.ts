// proto01_UIcast CW6 (04 §2): a set's faces — each kind's parts, every face's normal looking into the space, a room's faces closing the box.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { normalOf, placeSet, setFaces } from './placeSet'
import { coverageShares, FACADE_COS, UNSEEN_COS, unseenCos } from './setBake'

describe("a place's set (CW6)", () => {
  it("builds a room's faces looking in, the front wall off by default", () => {
    const faces = setFaces({ kind: 'room', sizes: { width: 5, depth: 6, height: 2.8 } })
    expect(faces.map((f) => f.id).sort()).toEqual(['ceiling', 'floor', 'wall_back', 'wall_left', 'wall_right'])
    for (const f of faces) {
      const centre = f.origin.clone().addScaledVector(f.u, f.w / 2).addScaledVector(f.v, f.h / 2)
      const inside = new THREE.Vector3(0, 1.4, 0).sub(centre)
      expect(normalOf(f).dot(inside)).toBeGreaterThan(0)                                   // each face looks at the room's middle
    }
    const back = faces.find((f) => f.id === 'wall_back')!
    expect([back.w, back.h]).toEqual([5, 2.8])
    expect(back.origin.z).toBeCloseTo(-3, 6)
  })
  it("lays out a street, a corridor and open ground; a part turned off is left out", () => {
    const street = setFaces({ kind: 'street', sizes: { width: 12, length: 30, pavement: 2, height_l: 9, height_r: 6 }, parts: { end: false } })
    expect(street.map((f) => f.id)).toEqual(['road', 'pavement_left', 'pavement_right', 'facade_left', 'facade_right'])
    expect(street.find((f) => f.id === 'road')!.w).toBe(8)
    expect(street.find((f) => f.id === 'facade_right')!.h).toBe(6)
    const corridor = setFaces({ kind: 'corridor', sizes: { width: 2, height: 2.6, length: 12 } })
    expect(corridor.find((f) => f.id === 'wall_left')!.w).toBe(12)
    const ground = setFaces({ kind: 'ground', sizes: {} })
    expect(ground.filter((f) => f.id.startsWith('backdrop_'))).toHaveLength(12)
    for (const f of ground.filter((x) => x.id.startsWith('backdrop_'))) expect(normalOf(f).dot(f.origin.clone().negate().setY(0).normalize())).toBeGreaterThan(0.9)
  })
  it('draws each face where its frame says', () => {
    const g = placeSet({ kind: 'room', sizes: { width: 4, depth: 4, height: 3 } }, new THREE.MeshBasicMaterial())
    g.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(g)
    expect(box.min.toArray().map((v) => +v.toFixed(3) || 0)).toEqual([-2, 0, -2])
    expect(box.max.toArray().map((v) => +v.toFixed(3))).toEqual([2, 3, 2])
    const back = g.children.find((c) => c.userData.face === 'wall_back')!
    expect(new THREE.Vector3(0, 0, 1).applyQuaternion(back.quaternion).z).toBeCloseTo(1, 6)    // facing in (+Z)
  })
})

describe("D170: a street's fronts seen off square are the Fill's (place_sets.unseen_cos's twin)", () => {
  it('counts a facade texel under a cosine of 0.7 as unseen, every other face under 0.05', () => {
    expect(unseenCos('facade_left')).toBe(FACADE_COS)
    expect(FACADE_COS).toBe(0.7)
    expect([unseenCos('road'), unseenCos('wall_left'), unseenCos('floor'), unseenCos('end')]).toEqual([UNSEEN_COS, UNSEEN_COS, UNSEEN_COS, UNSEEN_COS])
    const px = new Uint8Array([10, 0, 0, 255, 100, 0, 0, 255, 160, 0, 0, 255, 230, 0, 0, 255])   // cosines 0.04, 0.39, 0.63, 0.90; every pixel fine
    expect(coverageShares(px)).toEqual({ seen: 0.75, bad: 0.25 })
    expect(coverageShares(px, unseenCos('facade_right'))).toEqual({ seen: 0.75, bad: 0.75 })    // the picture saw it, the Fill takes it
  })
})
