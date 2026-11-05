// RG3 (D187 R4, D188 F4): the rigging screen's edits — the count, claws and a finger's length and width on the hand it names (the right
// while linked), Unlink and Link, a foot's numbers, stiff sole and placement; a placed foot's offsets (a left one mirrored while linked); a
// shell's shoe rigged to a placement by hand whatever its geometry.
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from './body'
import { mannequin, POSES } from './builders'
import type { HandShapes } from './clayHand'
import { A_POSE, bindProxy, type FootShapes } from './proxy'
import { footOf, handOf, humanHand, linkFeet, linkHands, linked, placeOffset, plainFoot, setClaw, setCount, setFinger, setFoot, unlinkFeet, unlinkHands } from './rigEdit'

describe('RG3: the hands\' edits', () => {
  it('a count, a claw and a finger\'s length (its segments scaled together) on the right while linked', () => {
    let h: HandShapes = { right: humanHand(), left: null }
    h = setCount(h, 'r', 4); h = setClaw(h, 'l', 0.25)                            // linked: the left's edit is the right's
    expect([h.right.count, h.right.claw, h.left]).toEqual([4, 0.25, null])
    const before = h.right.fingers.middle!.lengths
    h = setFinger(h, 'r', 'middle', { length: 1.0, width: 0.12 })
    const after = h.right.fingers.middle!.lengths
    expect(after.reduce((a, s) => a + s, 0)).toBeCloseTo(1.0, 2)
    expect(after[0] / after[2]).toBeCloseTo(before[0] / before[2], 2)          // the proportions kept
    expect(h.right.fingers.middle!.width).toBe(0.12)
    h = setFinger(h, 'r', 'index', { claw: 0.4 }); expect(h.right.fingers.index!.claw).toBe(0.4)
    h = setFinger(h, 'r', 'index', { claw: null }); expect(h.right.fingers.index!.claw).toBeNull()
  })
  it('Unlink copies the right into the left, edited apart from then; Link drops it', () => {
    let h = unlinkHands({ right: humanHand(), left: null })
    expect(linked(h)).toBe(false)
    h = setCount(h, 'l', 3)
    expect([handOf(h, 'r').count, handOf(h, 'l').count]).toEqual([5, 3])
    h = linkHands(h)
    expect([linked(h), handOf(h, 'l').count]).toEqual([true, 5])
  })
})

describe('RG3: the feet\'s edits', () => {
  it('a stiff sole, a number, a placement on the right while linked; the left its own once unlinked', () => {
    let f: FootShapes = { right: plainFoot(), left: null }
    f = setFoot(f, 'l', { stiff: true, ball_at: 0.8 })
    expect([f.right.stiff, f.right.ball_at, f.left]).toEqual([true, 0.8, null])
    f = unlinkFeet(f); f = setFoot(f, 'l', { stiff: false })
    expect([footOf(f, 'r').stiff, footOf(f, 'l').stiff]).toEqual([true, false])
    expect(linkFeet(f).left).toBeNull()
  })
  it('a dragged point as metres from the ankle; a left one mirrored onto the right\'s while linked', () => {
    expect(placeOffset([0.1, 0.02, 0.2], [0.1, 0.05, 0.0], 'r', true)).toEqual([0, -0.03, 0.2])
    expect(placeOffset([-0.12, 0.02, 0.2], [-0.1, 0.05, 0.0], 'l', true)).toEqual([0.02, -0.03, 0.2])
    expect(placeOffset([-0.12, 0.02, 0.2], [-0.1, 0.05, 0.0], 'l', false)).toEqual([-0.02, -0.03, 0.2])
    expect(placeOffset([0, 0, 2], [0, 0, 0], 'r', true)[2]).toBe(0.6)           // clamped as the server keeps it
  })
  it('a shoe placed by hand is rigged at the placed points, whatever the shell; the left mirrored', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, A_POSE, DEFAULT_BODY)
    const root = new THREE.Group(); root.add(fig.root); root.updateMatrixWorld(true)
    const statue = new THREE.Group(); statue.add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.7, 0.25, 6, 30, 4).translate(0, 0.95, 0)))   // no shoes at all
    const place = { heel: [0, -0.03, -0.05], ball: [0.01, -0.035, 0.12], toe: [0.01, -0.03, 0.2] }
    const px = bindProxy(statue, fig.joints, fig.limbs, root, { preset: 'stand', joints: A_POSE }, { visible: true, markers: fig.markers, feet: { shape: { right: { ...plainFoot(), place } } } })
    const r = px.footPoints.r!, l = px.footPoints.l!
    expect([r.rigged, l.rigged]).toEqual([true, true])
    expect(r.toe.clone().sub(r.ankle).toArray().map((x) => +x.toFixed(3))).toEqual([0.01, -0.03, 0.2])
    expect(l.toe.clone().sub(l.ankle).toArray().map((x) => +x.toFixed(3))).toEqual([-0.01, -0.03, 0.2])   // mirrored
    expect(px.meshes[0].skeleton.bones.length).toBe(12 + 4)
    px.dispose()
  })
})
