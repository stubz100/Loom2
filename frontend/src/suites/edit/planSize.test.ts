// D68 (ArtCraft P6): the AI panel's engine size must be the size the orchestrator runs (T8). The expected values come from
// orchestrator/loom2/edit_ai.py _engine_size called with the same arguments (2026-10-11).
import { describe, expect, it } from 'vitest'
import { planSize } from './planSize'

const ORCHESTRATOR: [args: [number, number, number, number], w: number, h: number][] = [
  [[512, 288, 768, 2048], 768, 432],       // small region: up to the model's minimum on the longer side
  [[100, 60, 0, 2048], 112, 64],           // rounded up to multiples of 16
  [[10, 10, 0, 2048], 16, 16],             // never below 16
  [[4096, 4096, 0, 2048], 1024, 1024],     // capped by the 1 MP budget
  [[1920, 1080, 1024, 2048], 1360, 768],   // the 16-rounding overshoots 1 MP: stepped down
  [[3000, 1000, 0, 2048], 1760, 592],
  [[1000, 1100, 0, 2048], 976, 1072],
]

describe('planSize', () => {
  it.each(ORCHESTRATOR)('matches edit_ai._engine_size for %j', (args, w, h) => {
    expect(planSize(...args)).toMatchObject({ w, h })
  })
  it('stays within the pixel budget and the size limit', () => {
    for (const [w, h] of [[1920, 1080], [3000, 1000], [999, 1001], [5000, 300], [1234, 4321]]) {
      const p = planSize(w, h, 0, 2048)
      expect(p.w * p.h, `${w}×${h}`).toBeLessThanOrEqual(1048576)
      expect(Math.max(p.w, p.h)).toBeLessThanOrEqual(2048)
      expect((p.w % 16) + (p.h % 16)).toBe(0)
    }
  })
  it('leaves a region that already fits at scale 1', () => {
    expect(planSize(640, 480, 0, 2048)).toEqual({ w: 640, h: 480, scale: 1 })
  })
})
