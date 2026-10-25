// CS2: the skeleton bench's arithmetic — the picture ↔ figure mapping, the red ticks, the rows in centimetres, a blue point dragged.
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from './body'
import { cropOf, disagreements, dragFactor, lengthCm, outside, pictureMap, ROWS, setLocked, unlock, type XY } from './skeleton'

// a figure on its front plane (metres, y up) and the same figure in a picture (pixels, y down, 400 px per metre, the feet at y 700)
const FIG: XY[] = [[0, 1.6], [0, 1.43], [-0.2, 1.43], [-0.24, 1.15], [-0.26, 0.86], [0.2, 1.43], [0.24, 1.15], [0.26, 0.86], [-0.1, 0.95], [-0.1, 0.5], [-0.1, 0.07],
  [0.1, 0.95], [0.1, 0.5], [0.1, 0.07], [-0.035, 1.64], [0.035, 1.64], [-0.095, 1.62], [0.095, 1.62]]
const PIC = FIG.map(([x, y]) => [400 + x * 400, 700 - y * 400, 0.9])

describe('the skeleton bench (CS2)', () => {
  it('maps the picture onto the figure and back by the nose and the ankles', () => {
    const m = pictureMap(PIC, FIG)!
    expect(m.scale).toBeCloseTo(1 / 400, 9)
    const f = m.toFig([PIC[4][0], PIC[4][1]]); expect(f[0]).toBeCloseTo(FIG[4][0], 6); expect(f[1]).toBeCloseTo(FIG[4][1], 6)
    const p = m.toPic(FIG[12]); expect(p[0]).toBeCloseTo(PIC[12][0], 6); expect(p[1]).toBeCloseTo(PIC[12][1], 6)
    expect(pictureMap([[0, 0, 0]], FIG)).toBeNull()                                            // no nose, no map
  })
  it('ticks the pairs more than 3 % of the height apart', () => {
    expect(disagreements(PIC, FIG)).toEqual([])
    const moved = PIC.map((r) => [...r]); moved[8][1] += 40                                      // SDPose put a hip 40 px low (a coat)
    const d = disagreements(moved, FIG)
    expect(d.map((x) => x.k)).toEqual([8]); expect(d[0].off).toBeCloseTo(40 / (1.53 * 400), 2)
  })
  it('gives each part in centimetres at the height, and an adult range', () => {
    expect(lengthCm(DEFAULT_BODY, 'neck')).toBeCloseTo(12.1, 1)                                // ×1 an adult's neck (S3)
    expect(lengthCm({ ...DEFAULT_BODY, neck: 1.54 }, 'neck')).toBeGreaterThan(17)             // Mara's
    expect(lengthCm({ ...DEFAULT_BODY, height_m: 1.2 }, 'shin')).toBeLessThan(lengthCm(DEFAULT_BODY, 'shin'))
    const neck = ROWS.find((r) => r.key === 'neck')!
    expect(outside({ ...DEFAULT_BODY, neck: 1.54 }, neck)).toBe(true); expect(outside(DEFAULT_BODY, neck)).toBe(false)
  })
  it('crops the reference to the figure, inside the picture', () => {
    const [x, y, w, h] = cropOf({ pose: PIC }, 1280, 720)!
    const fy = Math.min(...PIC.map((q) => q[1])), ly = Math.max(...PIC.map((q) => q[1]))
    expect(y).toBeLessThan(fy); expect(y + h).toBeGreaterThan(ly); expect(x).toBeGreaterThanOrEqual(0); expect(w).toBeLessThan(400)   // a tall crop, not the 16:9 picture
    expect(cropOf({ pose: [[0, 0, 0], [5, 5, 0.1]] }, 1280, 720)).toBeNull()
  })
  it('sets the part a blue point ends where it is dropped', () => {
    const elbow = dragFactor(DEFAULT_BODY, FIG, 3, [-0.25, 1.1])!                              // the right elbow down the arm
    expect(elbow.factor).toBe('elbow'); expect(elbow.value).toBeGreaterThan(0.55)
    const wrist = dragFactor(DEFAULT_BODY, FIG, 7, [0.27, 0.76])!                              // the left wrist 10 cm lower: a longer arm
    expect(wrist.factor).toBe('arms'); expect(wrist.value).toBeGreaterThan(1.1)
    expect(dragFactor(DEFAULT_BODY, FIG, 2, [-0.25, 1.43])).toEqual({ factor: 'shoulders', value: 1.25 })
    expect(dragFactor(DEFAULT_BODY, FIG, 1, [0, 1.4])).toBeNull()                               // the neck point ends no part
    const locked = setLocked(DEFAULT_BODY, 'elbow', 0.56)
    expect(locked.locks).toEqual(['elbow']); expect(setLocked(locked, 'elbow', 0.5).locks).toEqual(['elbow'])
    expect(unlock(locked, 'elbow').locks).toEqual([])
  })
})
