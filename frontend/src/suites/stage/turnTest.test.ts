// proto01_UIcast CS1 (S4): the turn test starts in the reference's own stance — its arms' angles read from SDPose's points.
import { describe, expect, it } from 'vitest'
import { stanceOf } from './proxy'

const person = (armOut: number, foreOut = armOut) => {                    // a figure facing the picture: its right side on the picture's left
  const r = (deg: number) => (deg * Math.PI) / 180
  const pose: number[][] = Array.from({ length: 18 }, () => [0, 0, 0.9])
  const sh = (x: number) => [x, 100, 0.9]
  pose[2] = sh(80); pose[5] = sh(120)
  pose[3] = [80 - 30 * Math.sin(r(armOut)), 100 + 30 * Math.cos(r(armOut)), 0.9]; pose[4] = [pose[3][0] - 28 * Math.sin(r(foreOut)), pose[3][1] + 28 * Math.cos(r(foreOut)), 0.9]
  pose[6] = [120 + 30 * Math.sin(r(armOut)), 100 + 30 * Math.cos(r(armOut)), 0.9]; pose[7] = [pose[6][0] + 28 * Math.sin(r(foreOut)), pose[6][1] + 28 * Math.cos(r(foreOut)), 0.9]
  return { pose }
}

describe("the turn test's stance (S4)", () => {
  it('the arms as the reference holds them, out from hanging down', () => {
    const s = stanceOf(person(22))
    expect(s.r_shoulder[2]).toBeCloseTo(-22, 0); expect(s.l_shoulder[2]).toBeCloseTo(22, 0)      // the A-pose: the stand presets' signs
    expect(s.r_elbow[2]).toBeCloseTo(0, 0)
    const down = stanceOf(person(4, 10))                                                          // A1's: arms down, the hands a little out
    expect(down.r_shoulder[2]).toBeCloseTo(-4, 0); expect(down.r_elbow[2]).toBeCloseTo(-6, 0); expect(down.l_elbow[2]).toBeCloseTo(6, 0)
  })
  it('falls back to the A-pose without points, or with an arm not found', () => {
    expect(stanceOf(null).r_shoulder).toEqual([0, 0, -22])
    const p = person(10); p.pose[3][2] = 0.1
    const s = stanceOf(p)
    expect(s.r_shoulder).toEqual([0, 0, -22]); expect(s.l_shoulder[2]).toBeCloseTo(10, 0)
  })
})
