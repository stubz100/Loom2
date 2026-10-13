import { describe, expect, it } from 'vitest'
import { coverageGrid, rowsCovered, thinCells } from './coverage'

const SHOTS = ['close-up', 'portrait', 'waist-up', 'full-body']
const ANGLES = ['front', 'three-quarter left', 'back']
const cell = (shot: string, angle: string) => ({ params: { coverage_cell: { shot, angle, expression: 'neutral', take: 1 } } })

describe('coverage grid (17 §3b)', () => {
  it('counts the kept references per shot × angle and keeps the uncelled ones apart', () => {
    const g = coverageGrid([cell('close-up', 'front'), cell('close-up', 'front'), cell('waist-up', 'back'), { params: {} }, { params: null }], SHOTS, ANGLES)
    expect(g.counts['close-up'].front).toBe(2)
    expect(g.counts['waist-up'].back).toBe(1)
    expect(g.total).toBe(5)
    expect(g.uncelled).toBe(2)
    expect(rowsCovered(g)).toEqual(['close-up', 'waist-up'])
    expect(thinCells(g)).toHaveLength(SHOTS.length * ANGLES.length - 2)
  })
  it('adds a cell outside the vocabulary as a new row or column instead of dropping it', () => {
    const g = coverageGrid([cell('extreme close-up', 'low angle')], SHOTS, ANGLES)
    expect(g.shots).toContain('extreme close-up')
    expect(g.angles).toContain('low angle')
    expect(g.counts['extreme close-up']['low angle']).toBe(1)
  })
  it('an empty set covers nothing', () => {
    const g = coverageGrid([], SHOTS, ANGLES)
    expect(rowsCovered(g)).toEqual([])
    expect(thinCells(g)).toHaveLength(12)
  })
})
