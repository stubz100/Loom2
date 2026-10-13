// ST3: the pass maths (16 §12: "keypoint projection, depth normalisation … are modules with Vitest tests").
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { COCO, COLOURS, depthRange, hslToHex, LIMBS, maskColour, projectPoints } from './passes'

const cam = () => { const c = new THREE.PerspectiveCamera(40, 16 / 9, 0.05, 500); c.position.set(0, 1, 4); c.lookAt(0, 1, 0); c.updateProjectionMatrix(); c.updateMatrixWorld(); return c }

describe('passes', () => {
  it('has the OpenPose COCO-18 order, 17 limbs and 18 colours', () => {
    expect(COCO).toHaveLength(18); expect(COCO[0]).toBe('nose'); expect(COCO[1]).toBe('neck'); expect(COCO[17]).toBe('l_ear')
    expect(LIMBS).toHaveLength(17); expect(COLOURS).toHaveLength(18)
  })
  it('projects the target to the frame centre, a point off to the right to the right half, one behind the camera as invisible', () => {
    const kp = projectPoints([[new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 1, 0), new THREE.Vector3(0, 1, 6)]], cam(), 1280, 720)
    expect(kp[0][0][0]).toBeCloseTo(640, 0); expect(kp[0][0][1]).toBeCloseTo(360, 0); expect(kp[0][0][2]).toBe(1)
    expect(kp[0][1][0]).toBeGreaterThan(640); expect(kp[0][1][2]).toBe(1)
    expect(kp[0][2][2]).toBe(0)
  })
  it('keeps a point just outside the frame invisible', () => {
    const kp = projectPoints([[new THREE.Vector3(40, 1, 0)]], cam(), 1280, 720)
    expect(kp[0][0][2]).toBe(0)
  })
  it('normalises depth around the subject', () => {
    expect(depthRange(4)).toEqual({ near: 2.4, far: 12 })
    expect(depthRange(0.2)).toEqual({ near: 0.3, far: 1 })
  })
  it('gives distinct hex mask colours', () => {
    const cs = Array.from({ length: 12 }, (_, i) => maskColour(i))
    expect(new Set(cs).size).toBe(12)
    for (const c of cs) expect(c).toMatch(/^#[0-9a-f]{6}$/)
    expect(hslToHex(0, 1, 0.5)).toBe('#ff0000'); expect(hslToHex(120, 1, 0.5)).toBe('#00ff00')
  })
})
