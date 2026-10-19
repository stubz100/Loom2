// CA1: foot lock — a synthetic walk in place (the hips swing the legs, the swing leg's knee bends) slides its planted feet; locked, the
// root travels forward instead and the planted foot holds within the 2 cm bar (02 §5); a body's longer legs take longer steps.
import { describe, expect, it } from 'vitest'
import { DEFAULT_BODY } from '../body'
import type { Joint } from '../builders'
import { footLock, footSlide, stance } from './footlock'
import type { MotionFrame } from './retarget'

/** Two strides in place at 24 fps: the hips swing ±25°, the swinging leg's knee bends up to 50° (so the other foot is the lower one). */
function walkInPlace(n = 48): MotionFrame[] {
  const out: MotionFrame[] = []
  for (let i = 0; i < n; i++) {
    const ph = (i / 24) * Math.PI * 2                                          // one stride a second
    const swing = 25 * Math.sin(ph)
    const zero = [0, 0, 0]
    const joints = Object.fromEntries((['root', 'spine', 'neck', 'head', 'r_shoulder', 'r_elbow', 'l_shoulder', 'l_elbow'] as Joint[]).map((j) => [j, zero])) as Record<Joint, number[]>
    // negative X pitches a leg forward; the leg moving forward is in swing (its knee bends), the other carries the weight
    joints.r_hip = [-swing, 0, 0]; joints.l_hip = [swing, 0, 0]
    joints.r_knee = [Math.max(0, Math.cos(ph)) * 50, 0, 0]; joints.l_knee = [Math.max(0, -Math.cos(ph)) * 50, 0, 0]
    out.push({ joints, offset: [0, 0, 0] })
  }
  return out
}

describe('foot lock (CA1)', () => {
  it('finds the planted foot, alternating', () => {
    const s = stance(walkInPlace())
    expect(s.filter((x) => x === 'r').length).toBeGreaterThanOrEqual(8)
    expect(s.filter((x) => x === 'l').length).toBeGreaterThanOrEqual(8)
  })

  it('turns a walk in place into travel with the planted foot still', () => {
    const raw = walkInPlace()
    expect(footSlide(raw)).toBeGreaterThan(0.1)                              // in place, the planted foot slides back a stride
    const locked = footLock(raw)
    expect(footSlide(locked)).toBeLessThan(0.02)                             // 02 §5's bar
    const travel = locked[locked.length - 1].offset[2] - locked[0].offset[2]
    expect(Math.abs(travel)).toBeGreaterThan(0.5)                            // two strides of travel
    expect(Math.abs(locked[10].offset[0])).toBeLessThan(1e-6)                // straight ahead: no sideways drift
    expect(locked.map((f) => f.offset[1])).toEqual(raw.map((f) => f.offset[1]))   // the height is the clip's
  })

  it('takes longer steps on longer legs', () => {
    const raw = walkInPlace()
    const short = footLock(raw)
    const tall = footLock(raw, { ...DEFAULT_BODY, height_m: 2.2, legs: 1.3 })
    const dist = (f: MotionFrame[]) => Math.abs(f[f.length - 1].offset[2] - f[0].offset[2])
    expect(dist(tall)).toBeGreaterThan(dist(short) * 1.2)
  })
})
