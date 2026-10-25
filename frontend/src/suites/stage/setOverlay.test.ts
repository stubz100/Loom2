// proto01_UIcast CW6 (04 §3 step 4; D143): the set builder's overlay — the set's edges on its picture, a wall's foot or top dragged to a
// point of the picture, the camera's height scaling the fit, another kind in one click.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { bakeKey, changeKind, dragTo, extents, handles, outlines, rescale, sourceCamera, type SourceCam } from './setOverlay'
import type { PlaceSetDoc } from './placeSet'

const W = 1280, H = 720
const room: PlaceSetDoc = { kind: 'room', sizes: { width: 5, depth: 6, height: 2.8 } }
const cam: SourceCam = { pos: [0.3, 1.6, 2], target: [0.1, 1.3, -3], roll: 0, focal_mm: 24, sensor_mm: 36 }
const px = (c: SourceCam, p: THREE.Vector3): [number, number] => { const n = p.clone().project(sourceCamera(c, W / H)); return [(n.x * 0.5 + 0.5) * W, (0.5 - n.y * 0.5) * H] }

describe("the set builder's overlay (CW6)", () => {
  it("outlines the faces the camera sees and clips the floor behind it", () => {
    const o = Object.fromEntries(outlines(room, cam, W, H).map((x) => [x.id, x.points]))
    for (const [x, y] of o.wall_back) { expect(x).toBeGreaterThan(0); expect(x).toBeLessThan(W); expect(y).toBeGreaterThan(0); expect(y).toBeLessThan(H) }
    expect(o.floor.length).toBeGreaterThanOrEqual(4)                                          // clipped where it runs behind the camera
    const hs = handles(room, cam, W, H, ['height'])
    expect(hs.map((h) => h.id)).toEqual(expect.arrayContaining(['back', 'left', 'right', 'top_back']))
    expect(hs.find((h) => h.id === 'top_back')!.assumed).toBe(true)
    expect(hs.find((h) => h.id === 'back')!.assumed).toBe(false)
  })
  it("moves the back wall to where its foot is dragged, the camera keeping its place in the room", () => {
    const back = handles(room, cam, W, H).find((h) => h.id === 'back')!
    const r = dragTo(room, cam, W, H, back, px(cam, new THREE.Vector3(0.2, 0, -4)))!
    expect(r.set.sizes.depth).toBeCloseTo(7, 2)                                               // the front stays at +3: the back at −4
    const e = extents(r.set)!
    expect(e.z0).toBeCloseTo(-3.5, 2)
    expect(r.camera.pos[2]).toBeCloseTo(2 + 0.5, 3)                                           // the centre moved 0.5 m back: the camera is 0.5 m further from it
    expect(r.camera.target[2] - r.camera.pos[2]).toBeCloseTo(cam.target[2] - cam.pos[2], 6)   // the camera's aim unchanged
    const right = handles(room, cam, W, H).find((h) => h.id === 'right')!
    const s = dragTo(room, cam, W, H, right, px(cam, new THREE.Vector3(3.1, 0, -1)))!
    expect(s.set.sizes.width).toBeCloseTo(5.6, 2)
  })
  it("sets the height from a wall's top dragged; a foot dragged above the horizon does nothing", () => {
    const top = handles(room, cam, W, H).find((h) => h.id === 'top_back')!
    const r = dragTo(room, cam, W, H, top, px(cam, new THREE.Vector3(0, 3.2, -3)))!
    expect(r.set.sizes.height).toBeCloseTo(3.2, 2)
    expect(r.camera.pos).toEqual(cam.pos)
    const back = handles(room, cam, W, H).find((h) => h.id === 'back')!
    expect(dragTo(room, cam, W, H, back, [W / 2, 2])).toBeNull()
  })
  it("scales the fit by the camera's height and changes the kind in one step", () => {
    const r = rescale(room, cam, 1.8)
    expect(r.set.sizes).toEqual({ width: 5.625, depth: 6.75, height: 3.15 })
    expect(r.camera.pos[1]).toBeCloseTo(1.8, 6)
    const st = changeKind(room, cam, 'street')
    expect(st.set.kind).toBe('street')
    expect(st.set.sizes.width).toBe(5)
    expect(st.set.sizes.length).toBe(30)
    expect(st.camera.pos[2] - extents(st.set)!.z0).toBeCloseTo(20, 3)                         // two thirds of the street ahead of the camera
    const co = changeKind(room, cam, 'corridor')
    expect(co.set.sizes).toMatchObject({ width: 5, length: 6, height: 2.8 })
    expect(bakeKey(room, cam)).not.toBe(bakeKey(r.set, r.camera))
    expect(bakeKey(room, cam)).toBe(bakeKey({ ...room, faces: [{ id: 'floor' }] }, cam))       // the faces are what a bake makes, not what it is for
  })
})
