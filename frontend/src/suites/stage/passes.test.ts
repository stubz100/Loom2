// ST3: the pass maths (16 §12: "keypoint projection, depth normalisation … are modules with Vitest tests").
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { COCO, COLOURS, depthRange, depthRangeFor, drawnPoints, facesAway, headFacing, hslToHex, LIMBS, maskColour, projectPoints, type Keypoint } from './passes'

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
    // D167 (W43): the figures decide — the set builder's picture camera aims 1 m ahead, the figures stand 5–10 m off
    expect(depthRangeFor(1, [5, 7, 10])).toEqual({ near: 3, far: 30 })
    expect(depthRangeFor(4, [4])).toEqual(depthRange(4))                                    // a target on the figure: as before
    expect(depthRangeFor(4, [])).toEqual(depthRange(4))                                     // no figure: the target
    expect(depthRangeFor(4, [0.01, -2])).toEqual(depthRange(4))                             // behind the camera or on it: not counted
  })
  it('gives distinct hex mask colours', () => {
    const cs = Array.from({ length: 12 }, (_, i) => maskColour(i))
    expect(new Set(cs).size).toBe(12)
    for (const c of cs) expect(c).toMatch(/^#[0-9a-f]{6}$/)
    expect(hslToHex(0, 1, 0.5)).toBe('#ff0000'); expect(hslToHex(120, 1, 0.5)).toBe('#00ff00')
  })
})

describe('the pose pass of a figure facing away (D158, E42)', () => {
  const kp = (away: boolean, eyes = true): Keypoint[] => {
    const k: Keypoint[] = Array.from({ length: 18 }, () => [0, 0, 0] as Keypoint)
    k[0] = [64, 20, 1]
    k[2] = away ? [74, 30, 1] : [54, 30, 1]; k[5] = away ? [54, 30, 1] : [74, 30, 1]
    if (eyes) { k[14] = away ? [70, 18, 1] : [58, 18, 1]; k[15] = away ? [58, 18, 1] : [70, 18, 1] }
    k[16] = [76, 20, 1]; k[17] = [52, 20, 1]
    return k
  }
  it('faces away by its eyes, else its shoulders, and then draws no nose or eyes — the ears and the shoulders stay', () => {
    expect(facesAway(kp(true))).toBe(true); expect(facesAway(kp(false))).toBe(false)
    expect(facesAway(kp(true, false))).toBe(true)
    const drawn = drawnPoints(kp(true))
    expect([0, 14, 15].map((i) => drawn[i][2])).toEqual([0, 0, 0])
    expect([2, 5, 16, 17].map((i) => drawn[i][2])).toEqual([1, 1, 1, 1])
    expect(drawnPoints(kp(false))).toEqual(kp(false))                                      // facing the camera: as before
  })
})

describe('a head read by its ears (D166, E44): the twin of finals.head_facing / drawn_points', () => {
  const head = (nose: number, earR: number, earL: number, eyeR: number, eyeL: number): Keypoint[] => {
    const k: Keypoint[] = Array.from({ length: 18 }, () => [64, 60, 1] as Keypoint)
    k[0] = [nose, 20, 1]; k[1] = [64, 40, 1]; k[2] = [56, 42, 1]; k[5] = [72, 42, 1]
    k[14] = [eyeR, 17, 1]; k[15] = [eyeL, 17, 1]; k[16] = [earR, 19, 1]; k[17] = [earL, 19, 1]
    return k
  }
  it('a side profile is neither front nor away and shows its near side; a profile turned away keeps the nose and the near ear', () => {
    expect(headFacing(head(56, 66, 67, 59, 58))).toEqual({ kind: 'side', near: 'left' })
    expect(headFacing(head(72, 62, 61, 69, 70))).toEqual({ kind: 'side', near: 'right' })
    expect(headFacing(head(72, 74, 64, 66, 62))).toEqual({ kind: 'away_profile', near: 'right' })
    expect(headFacing(head(64, 52, 76, 58, 70)).kind).toBe('front')
    expect(headFacing(head(64, 52, 76, 70, 58)).kind).toBe('away')
    const side = drawnPoints(head(56, 66, 67, 59, 58))
    expect([0, 15, 17].map((i) => side[i][2])).toEqual([1, 1, 1]); expect([14, 16].map((i) => side[i][2])).toEqual([0, 0])
    const turned = drawnPoints(head(72, 74, 64, 66, 62))
    expect([0, 16].map((i) => turned[i][2])).toEqual([1, 1]); expect([14, 15, 17].map((i) => turned[i][2])).toEqual([0, 0, 0])
    const blind = head(56, 66, 67, 59, 58); blind[1] = [64, 40, 0]
    expect(headFacing(blind).kind).toBe('away')                                                // no neck in view: D158 decides
  })
})
