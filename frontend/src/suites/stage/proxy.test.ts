// proto01_UIcast E36: the shell's two weightings — proximity (E23d) and bone heat over the surface (Pinocchio). A tube along two segments
// blends smoothly from one to the other; a sheet hanging between two "legs" (a skirt's hem) follows the surface it hangs from, where
// proximity hands each half to the nearer leg across empty space.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from './body'
import { mannequin, POSES } from './builders'
import { A_POSE, bindProxy, collapseHands, FACE_LANDMARKS, HAND_M, handRegion, heatWeights, proximityWeights, type Segment } from './proxy'

const soup = (geo: THREE.BufferGeometry) => (geo.index ? geo.toNonIndexed() : geo).attributes.position as THREE.BufferAttribute
const weightOf = (s: { idx: Uint16Array; wts: Float32Array }, i: number, seg: number) => { let w = 0; for (let k = 0; k < 4; k++) if (s.idx[i * 4 + k] === seg) w += s.wts[i * 4 + k]; return w }

describe("the shell's weights (E36)", () => {
  const tube = new THREE.CylinderGeometry(0.05, 0.05, 1, 12, 40, true)        // y from −0.5 to 0.5
  const pos = soup(tube)
  const segs: Segment[] = [{ j: 'r_hip', a: new THREE.Vector3(0, 0.5, 0), b: new THREE.Vector3(0, 0, 0) }, { j: 'r_knee', a: new THREE.Vector3(0, 0, 0), b: new THREE.Vector3(0, -0.5, 0) }]
  it('bone heat sums to one, blends across the joint and holds each end to its segment', () => {
    const s = heatWeights(pos, segs)
    for (let i = 0; i < pos.count; i += 7) expect(s.wts[i * 4] + s.wts[i * 4 + 1] + s.wts[i * 4 + 2] + s.wts[i * 4 + 3]).toBeCloseTo(1, 4)
    const at = (y: number) => { let best = 0, d = Infinity; for (let i = 0; i < pos.count; i++) { const dy = Math.abs(pos.getY(i) - y); if (dy < d) { d = dy; best = i } } return best }
    expect(weightOf(s, at(0.45), 0)).toBeGreaterThan(0.9)
    expect(weightOf(s, at(-0.45), 1)).toBeGreaterThan(0.9)
    const mid = weightOf(s, at(0), 0)
    expect(mid).toBeGreaterThan(0.2); expect(mid).toBeLessThan(0.8)                // a blend at the knee, not a cut
  })
  it('a sheet between two legs follows the surface it hangs from', () => {
    // a skirt: a strip across the hips (y 0.5) hanging to y −0.3, the legs apart at x ±0.15 — its hem's middle is as near the left leg as
    // the right; heat keeps it with the hips it hangs from, proximity splits it between the legs
    const skirt = new THREE.PlaneGeometry(0.6, 0.8, 24, 32)
    skirt.translate(0, 0.1, 0.12)
    const sp = soup(skirt)
    const legs: Segment[] = [{ j: 'root', a: new THREE.Vector3(-0.2, 0.5, 0), b: new THREE.Vector3(0.2, 0.5, 0) },
      { j: 'r_hip', a: new THREE.Vector3(-0.15, 0.45, 0), b: new THREE.Vector3(-0.15, -0.45, 0) }, { j: 'l_hip', a: new THREE.Vector3(0.15, 0.45, 0), b: new THREE.Vector3(0.15, -0.45, 0) }]
    const heat = heatWeights(sp, legs), prox = proximityWeights(sp, legs)
    let hem = 0, d = Infinity
    for (let i = 0; i < sp.count; i++) { const dd = Math.hypot(sp.getX(i), sp.getY(i) + 0.3); if (dd < d) { d = dd; hem = i } }
    expect(weightOf(heat, hem, 0)).toBeGreaterThan(weightOf(prox, hem, 0))                       // more of the hips than proximity gives it
    expect(Math.abs(weightOf(heat, hem, 1) - weightOf(heat, hem, 2))).toBeLessThan(0.2)          // and the legs share it (the triangulation leans a little)
  })
})

describe('the shell as the figure (CS3)', () => {
  it("folds the shell's hands into the wrists, not the coat beside them — the wrist is the hand's length back from the forearm segment's end", () => {
    const segs: Segment[] = [{ j: 'r_elbow', a: new THREE.Vector3(0, 1, 0), b: new THREE.Vector3(0, 0.7 - HAND_M, 0) },   // a forearm hanging down: its segment ends at the fingertips (segmentEnd), the wrist at 0.7
      { j: 'r_hip', a: new THREE.Vector3(0.15, 0.9, 0), b: new THREE.Vector3(0.15, 0.4, 0) }]
    const pos = new THREE.BufferAttribute(new Float32Array([0, 0.6, 0, -0.1, 0.68, 0, 0.12, 0.62, 0, 0, 0.85, 0.03, 0, 0.5, 0.01]), 3)   // the hand (along the segment), the sleeve's side, the coat, the forearm, the fingertips' end
    expect(collapseHands(pos, segs)).toBe(2)
    expect([pos.getX(0), pos.getY(0), pos.getZ(0)]).toEqual([0, expect.closeTo(0.7, 6), 0])              // the hand, to the wrist — not to the fingertips
    expect([pos.getX(4), pos.getY(4), pos.getZ(4)]).toEqual([0, expect.closeTo(0.7, 6), 0])
    expect(pos.getY(1)).toBeCloseTo(0.68, 6); expect(pos.getX(2)).toBeCloseTo(0.12, 6); expect(pos.getY(3)).toBeCloseTo(0.85, 6)
  })
  it("measures the forearm's line in the picture's plane: a hand reaching in front of it still folds (the shell has depth, the skeleton none)", () => {
    const segs: Segment[] = [{ j: 'r_elbow', a: new THREE.Vector3(0, 1, 0), b: new THREE.Vector3(0, 0.7 - HAND_M, 0) }]
    const ahead = () => new THREE.BufferAttribute(new Float32Array([0, 0.62, 0.15, 0, 0.62, 0.45]), 3)       // a hand 15 cm in front of the plane; a thing 45 cm in front
    expect(collapseHands(ahead(), segs)).toBe(0)                                                               // in 3D the hand is 62° off the forearm's line
    const pos = ahead()
    expect(collapseHands(pos, segs, new THREE.Vector3(0, 0, 1))).toBe(1)                                       // in the plane it is on it; the far thing stays
    expect([pos.getX(0), pos.getY(0), pos.getZ(0)]).toEqual([0, expect.closeTo(0.7, 6), 0]); expect(pos.getZ(1)).toBeCloseTo(0.45, 6)
  })
  it("folds exactly the picture's hands when they are known: the outline of their keypoints, wider beyond the wrist than around the cuff", () => {
    const toFigure = (px: number, py: number) => new THREE.Vector3(px / 1000, (1000 - py) / 1000, 0)              // 1 mm a pixel, the floor at y 1000
    const hand = [[0, 300, 1], [-20, 340, 1], [0, 360, 1], [20, 340, 1], [0, 380, 1], [-10, 370, 1]]                // the wrist at y 0.70, the hand hanging to 0.62
    const inHand = handRegion([hand, undefined], toFigure)!
    expect(inHand(new THREE.Vector3(0, 0.66, 0.2))).toBe(true)                                                  // inside (its depth is not read)
    expect(inHand(new THREE.Vector3(0.045, 0.64, 0))).toBe(true)                                                // 2.5 cm off the outline, beside the fingers
    expect(inHand(new THREE.Vector3(0, 0.56, 0))).toBe(true)                                                    // 6 cm past the fingertips' keypoint: Pixal3D's hands are fuller
    expect(inHand(new THREE.Vector3(0, 0.66 + 0.1, 0))).toBe(false)                                             // 6 cm up the forearm, behind the wrist: the cuff stays
    expect(inHand(new THREE.Vector3(0.2, 0.66, 0))).toBe(false)
    expect(handRegion([[[0, 0, 0.1], [1, 1, 0.2]]], toFigure)).toBeNull()                                       // unseen points: no region
    const segs: Segment[] = [{ j: 'r_elbow', a: new THREE.Vector3(0, 1, 0), b: new THREE.Vector3(0, 0.7 - HAND_M, 0) }, { j: 'r_hip', a: new THREE.Vector3(0.15, 0.9, 0), b: new THREE.Vector3(0.15, 0.4, 0) }]
    const pos = new THREE.BufferAttribute(new Float32Array([0, 0.64, 0.18, 0, 0.73, 0, 0.13, 0.62, 0]), 3)     // the hand in front, the cuff, the coat beside
    expect(collapseHands(pos, segs, new THREE.Vector3(0, 0, 1), inHand)).toBe(1)
    expect([pos.getX(0), pos.getY(0), pos.getZ(0)]).toEqual([0, expect.closeTo(0.7, 6), 0])                       // to the skeleton's wrist, where the hand rig's hand is
    expect(pos.getY(1)).toBeCloseTo(0.73, 6); expect(pos.getX(2)).toBeCloseTo(0.13, 6)                           // the cuff kept; the coat is nearest the hip
  })
  it("puts the pose pass's face on the shell's surface, with the head, and undoes it", () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, A_POSE, DEFAULT_BODY)
    const root = new THREE.Group(); root.add(fig.root); root.updateMatrixWorld(true)
    const statue = new THREE.Group(); statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.8, 0.3, 4, 18, 3).translate(0, 0.9, 0)))   // a block as tall as the figure
    const px = bindProxy(statue, fig.joints, fig.limbs, root, { preset: 'stand', joints: A_POSE }, { visible: true })
    const front = Math.max(...Array.from({ length: px.meshes[0].geometry.attributes.position.count }, (_, i) => px.meshes[0].geometry.attributes.position.getZ(i)))
    const at = (k: number) => fig.markers[k].getWorldPosition(new THREE.Vector3())
    const nose = at(0).clone(), ear = at(16).clone()
    const undo = px.landmark(FACE_LANDMARKS.map(([k, ray]) => ({ m: fig.markers[k], ray })), { preset: 'stand', joints: A_POSE })
    root.updateMatrixWorld(true)
    expect(at(0).z).toBeCloseTo(front, 3); expect(at(0).y).toBeCloseTo(nose.y, 4)               // onto the block's face, at the nose's height
    expect(Math.abs(at(16).x)).toBeGreaterThan(Math.abs(ear.x))                                  // the ear out to the block's side
    fig.joints.neck.rotation.y = 0.6; root.updateMatrixWorld(true)
    expect(at(0).distanceTo(fig.joints.head.getWorldPosition(new THREE.Vector3()))).toBeCloseTo(nose.clone().setZ(front).distanceTo(fig.joints.head.getWorldPosition(new THREE.Vector3())), 1)   // it turns with the head
    undo(); fig.joints.neck.rotation.y = 0; root.updateMatrixWorld(true)
    expect(at(0).distanceTo(nose)).toBeLessThan(1e-6)
  })
})
