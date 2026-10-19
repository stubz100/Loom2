// CA1: the floor path — smoothed with its ends kept, measured by arc length, a distance along it giving a point and the facing.
import { describe, expect, it } from 'vitest'
import { along, measure, smooth } from './path'

describe('the floor path (CA1)', () => {
  it('keeps its ends and rounds its corners', () => {
    const s = smooth([[0, 0], [0, 2], [2, 2]])
    expect(s[0]).toEqual([0, 0]); expect(s[s.length - 1]).toEqual([2, 2])
    expect(s.length).toBeGreaterThan(3)
    expect(s.some(([x, z]) => x > 0.1 && z < 1.99 && z > 1.2)).toBe(true)     // the corner is cut
  })

  it('walks a straight line exactly and faces along it', () => {
    const m = measure([[0, 0], [0, 4]])
    expect(m.length).toBeCloseTo(4, 6)
    const a = along(m, 1.5)
    expect(a.pos[0]).toBeCloseTo(0); expect(a.pos[1]).toBeCloseTo(1.5); expect(a.yaw).toBeCloseTo(0)
    expect(along(measure([[0, 0], [3, 0]]), 1).yaw).toBeCloseTo(90)             // +X is a quarter turn left of +Z
    expect(along(m, 9).pos[1]).toBeCloseTo(4)                                  // held at its end
  })

  it('turns the facing round a bend', () => {
    const m = measure([[0, 0], [0, 3], [3, 3]])
    expect(along(m, 0.5).yaw).toBeCloseTo(0, 0)
    expect(along(m, m.length - 0.3).yaw).toBeCloseTo(90, 0)
    const mid = along(m, m.length / 2).yaw
    expect(mid).toBeGreaterThan(10); expect(mid).toBeLessThan(80)
  })
})
