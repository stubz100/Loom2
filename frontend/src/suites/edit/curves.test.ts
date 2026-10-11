// D68 (ArtCraft P6): the Curves spline LUT (D57) and the exact per-channel maps the adjustment shader's table is filled from.
import { describe, expect, it } from 'vitest'
import { channelMap, curve } from './adjustFilters'
import { cachedLut, CURVE_LUT_N, lutAt, splineLut, type CurvePoints } from './curves'

describe('splineLut', () => {
  it('is the identity for a straight curve or too few points', () => {
    for (const pts of [[[0, 0], [255, 255]], [[10, 99]], []] as CurvePoints[]) {
      const t = splineLut(pts)
      expect(t.length).toBe(CURVE_LUT_N)
      expect(t[0]).toBeCloseTo(0, 6); expect(t[CURVE_LUT_N - 1]).toBeCloseTo(1, 6); expect(t[2048]).toBeCloseTo(2048 / 4095, 5)
    }
  })
  it('passes through its points, is flat beyond the first and last, and stays in 0..1', () => {
    const pts: CurvePoints = [[64, 32], [128, 160], [192, 224]]
    const t = splineLut(pts)
    for (const [x, y] of pts) expect(lutAt(t, x / 255)).toBeCloseTo(y / 255, 3)
    expect(lutAt(t, 0)).toBeCloseTo(32 / 255, 6)
    expect(lutAt(t, 1)).toBeCloseTo(224 / 255, 6)
    const wild = splineLut([[0, 0], [40, 255], [80, 0], [255, 255]])                // overshoots between points: clamped
    expect(Math.min(...wild)).toBeGreaterThanOrEqual(0); expect(Math.max(...wild)).toBeLessThanOrEqual(1)
  })
  it('is monotonic for a gentle S curve, and does not depend on point order', () => {
    const s: CurvePoints = [[0, 0], [64, 48], [192, 208], [255, 255]]
    const t = splineLut(s)
    for (let i = 1; i < t.length; i++) expect(t[i]).toBeGreaterThanOrEqual(t[i - 1])
    expect(splineLut([...s].reverse())).toEqual(t)
  })
  it('caches by value', () => {
    expect(cachedLut([[0, 10], [255, 200]])).toBe(cachedLut([[0, 10], [255, 200]]))
  })
  it('lutAt clamps its input and interpolates between entries', () => {
    const t = new Float32Array([0, 1])
    expect(lutAt(t, -1)).toBe(0); expect(lutAt(t, 2)).toBe(1); expect(lutAt(t, 0.25)).toBeCloseTo(0.25)
  })
})

describe('curve (straight segments, before D57)', () => {
  it('is the identity without points and flat beyond the ends', () => {
    expect(curve(0.3, undefined)).toBe(0.3)
    expect(curve(0.3, [])).toBe(0.3)
    expect(curve(0, [[128, 64]])).toBeCloseTo(64 / 255)
    expect(curve(1, [[128, 64]])).toBeCloseTo(64 / 255)
    expect(curve(0.5, [[0, 255], [255, 0]])).toBeCloseTo(0.5)
    expect(curve(0.25, [[0, 255], [255, 0]])).toBeCloseTo(0.75)
  })
})

describe('channelMap', () => {
  const xs = [0, 0.1, 0.5, 0.9, 1]
  it('maps neutral parameters to the identity', () => {
    const neutral: [string, Record<string, unknown>][] = [['levels', {}], ['exposure', {}], ['brightness_contrast', {}], ['curves', {}], ['curves', { interp: 'spline' }], ['unknown', {}]]
    for (const [type, p] of neutral) {
      const f = channelMap(type, p)
      for (const x of xs) expect(f(x, 0), `${type} ${x}`).toBeCloseTo(x, 4)
    }
  })
  it('levels: the input white point stretches, the output range compresses, gamma lifts the middle', () => {
    expect(channelMap('levels', { in_white: 128 })(0.5, 0)).toBeCloseTo(1, 2)
    expect(channelMap('levels', { out_black: 51, out_white: 204 })(0, 0)).toBeCloseTo(0.2)
    expect(channelMap('levels', { out_black: 51, out_white: 204 })(1, 0)).toBeCloseTo(0.8)
    expect(channelMap('levels', { gamma: 2 })(0.25, 0)).toBeCloseTo(0.5)
  })
  it('invert, and contrast pivots on mid grey', () => {
    expect(channelMap('invert', {})(0.2, 1)).toBeCloseTo(0.8)
    const c = channelMap('brightness_contrast', { contrast: 50 })
    expect(c(0.5, 0)).toBeCloseTo(0.5); expect(c(0.6, 0)).toBeGreaterThan(0.6)
  })
  it('curves: each channel before the master with splines (D57), the master first with straight lines before it', () => {
    const inv: CurvePoints = [[0, 255], [255, 0]], half: CurvePoints = [[0, 0], [255, 128]]
    const spline = channelMap('curves', { interp: 'spline', rgb: inv, r: half })
    expect(spline(1, 0)).toBeCloseTo(1 - 128 / 255, 3)          // red: halve, then invert
    expect(spline(1, 1)).toBeCloseTo(0, 3)                       // green: invert only
    const lines = channelMap('curves', { rgb: inv, r: half })
    expect(lines(1, 0)).toBeCloseTo(0, 3)                        // red: invert, then halve
  })
})
