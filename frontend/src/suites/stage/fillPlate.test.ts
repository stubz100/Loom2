// D135 (PF1): the plate projected and filled — the pure picks Stage makes from the projector's coverage: the keyframes a frame is made
// from, the most head-on keyframe per pixel, the bad pixels (unseen, or magnified past twice), the composite and the heal's frame.
import { describe, expect, it } from 'vitest'
import { HEAL_LEFT, KEY_BAD, badMask, bestOf, compose, healPick, stackAround, stackBefore } from './fillPlate'

const grey = (vals: number[]) => { const a = new Uint8ClampedArray(vals.length * 4); vals.forEach((v, i) => { a[i * 4] = v; a[i * 4 + 3] = 255 }); return a }
const rgba = (cols: [number, number, number][]) => { const a = new Uint8ClampedArray(cols.length * 4); cols.forEach((c, i) => a.set([...c, 255], i * 4)); return a }

describe('D135 (PF1) the keyframes a frame is made from', () => {
  it('walks on from the keyframes at or before it, the most recent first, three at most', () => {
    expect(stackBefore([0, 19, 26, 31], 31)).toEqual([31, 26, 19])
    expect(stackBefore([0, 19, 26, 31], 20)).toEqual([19, 0])
  })
  it('takes the nearer of the two around a frame first, then the other, then the ones before', () => {
    expect(stackAround([0, 16, 32, 48], 20)).toEqual([16, 32, 0])          // 4 after 16, 12 before 32
    expect(stackAround([0, 16, 32, 48], 30)).toEqual([32, 16, 0])
    expect(stackAround([0, 16, 32, 48], 48)).toEqual([48, 32, 16])         // a keyframe: itself first
    expect(stackAround([0, 16], 3)).toEqual([0, 16])
  })
})

describe('D135 (PF1) the pixels', () => {
  it('takes each pixel from the keyframe that saw it most head-on', () => {
    const { best, who } = bestOf([grey([200, 10, 0]), grey([100, 120, 0])], 3)
    expect([...best]).toEqual([200, 120, 0])
    expect([...who]).toEqual([0, 1, -1])
    const out = compose([rgba([[1, 1, 1], [2, 2, 2], [3, 3, 3]]), rgba([[9, 9, 9], [8, 8, 8], [7, 7, 7]])], best, who)
    expect([out[0], out[4], out[8]]).toEqual([1, 8, 3])                     // the third: seen by none — the first layer's (clamped) colour
  })
  it('calls a pixel bad when no keyframe saw it, or when the frame sees it more than twice as head-on as the best did below 70°', () => {
    const best = new Uint8Array([0, 60, 60, 200])                           // unseen · grazing · grazing · head-on
    const self = grey([200, 200, 100, 255])                                 // the frame: head-on · head-on · less · head-on
    const { mask, share } = badMask(best, self)
    expect([...mask]).toEqual([255, 255, 0, 0])
    expect(share).toBe(0.5)
  })
  it('places a keyframe past 8 % and heals the worst frame left above 0.5 %, never a keyframe itself', () => {
    expect(KEY_BAD).toBe(0.08)
    expect(healPick([null, 0.001, 0.02, 0.004, null, 0.03], [0, 4])).toBe(5)
    expect(healPick([null, 0.001, HEAL_LEFT, null], [0, 3])).toBeNull()
  })
})
