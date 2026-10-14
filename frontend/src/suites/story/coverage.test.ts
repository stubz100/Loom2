import { describe, expect, it } from 'vitest'
import { readiness, coverageGrid, rowsCovered, thinCells } from './coverage'

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

describe('readiness (18 §3d, LT2)', () => {
  const shots = ['close-up', 'medium', 'cowboy', 'full body']
  const angles = ['front', 'three-quarter left', 'three-quarter right', 'profile left', 'profile right', 'back']
  const cell = (shot: string, angle: string, expression = 'neutral') => ({ params: { coverage_cell: { shot, angle, expression, take: 1 } } })
  it('scores an empty set as too few and a full spread as strong, with its sentences', () => {
    const none = readiness([], shots, angles, false)
    expect(none.score).toBe(0)
    expect(none.summary).toBe('too few references')
    const few = readiness([cell('close-up', 'front'), cell('medium', 'front'), { params: {} }], shots, angles, true)
    expect(few.refs).toBe(3)
    expect(few.summary).toBe('too few references')
    const many = [...shots.flatMap((s) => angles.map((a) => cell(s, a))), ...['smiling', 'angry'].map((e) => cell('close-up', 'front', e))]
    const strong = readiness(many, shots, angles, true)
    expect(strong.rows).toBe(4)
    expect(strong.anglesCovered).toBe(6)
    expect(strong.expressions).toBe(3)
    expect(strong.score).toBeGreaterThanOrEqual(80)
    expect(strong.summary).toBe('strong')
    expect(strong.lines[0]).toMatch(/^26 references/)
    expect(strong.lines[5]).toBe('26 of 26 carry a coverage cell (their captions)')
  })
  it('is a thin set with one row and no cells', () => {
    const r = readiness([{ params: {} }, { params: {} }, { params: {} }, { params: {} }, { params: {} }], shots, angles, true)
    expect(r.rows).toBe(0)
    expect(r.celled).toBe(0)
    expect(r.summary).toBe('thin')
  })
})
