// M15 (the market walk): a clip's facing shown before it is applied — its own turn, and the words as the shot's camera sees it.
import { describe, expect, it } from 'vitest'
import { azimuth, clipYaw, facingWords } from './facing'
import type { MotionFrame } from './retarget'

const f = (root: number): MotionFrame => ({ offset: [0, 0, 0], joints: { root: [0, root, 0] } }) as unknown as MotionFrame

describe('M15: the facing of a clip before it is applied', () => {
  it('the clip turns the figure by its root\'s mean yaw', () => {
    expect(clipYaw([f(0), f(0)])).toBeCloseTo(0)
    expect(clipYaw([f(170), f(-170)])).toBeCloseTo(180)                              // a mean across ±180 is 180, not 0
    expect(clipYaw([])).toBe(0)
  })
  it('in words through the shot camera: towards it, away, to its left or right', () => {
    const cam = azimuth([0, 0, 0], [0, 1.6, 5])                                        // the camera in front (+Z)
    expect(cam).toBeCloseTo(0)
    expect(facingWords(0, cam)).toBe('faces the camera')
    expect(facingWords(180, cam)).toBe('faces away from the camera')                   // Bram's counter behind him: the aisle is the camera's way
    expect(facingWords(90, cam)).toBe('faces right in the shot')                       // +X is the camera's right
    expect(facingWords(-90, cam)).toBe('faces left in the shot')
    expect(facingWords(90, azimuth([0, 0, 0], [5, 1.6, 0]))).toBe('faces the camera') // the camera at +X
  })
})
