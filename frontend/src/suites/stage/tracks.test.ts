// U5d (D157; proto01_UI2 04 §3.2, §2.1): the lines at their place on the scene's timeline (F39) and a figure's back to the camera (F42).
import { describe, expect, it } from 'vitest'
import type { StageDoc } from '../../api/types'
import { awayStretches, LINE_GAP_FRAMES, linesOutlast, lineSpans } from './tracks'

describe('the lines\' track (U5d, F39)', () => {
  const lines = [{ text: 'Do you know whose seal this is?', speaker: 'prf_ines', audio_asset_id: 'ast_a' }, { text: '', speaker: null, audio_asset_id: null },
    { text: 'A heron. I have not seen it in years.', speaker: 'prf_tomas', audio_asset_id: null }]
  it('lays the lines one after another from the shot\'s start, as long as their voices, an unvoiced one by its words', () => {
    const spans = lineSpans(lines, { ast_a: 2.5 }, 10, 24)
    expect(spans.map((s) => [s.index, s.from, s.to, s.estimated])).toEqual([[0, 10, 69, false], [2, 70 + LINE_GAP_FRAMES, 70 + LINE_GAP_FRAMES + Math.round((9 / 2.6) * 24) - 1, true]])
  })
  it('says when the lines outlast the shot, and to where its range would go', () => {
    const spans = lineSpans(lines, { ast_a: 2.5 }, 0, 24)
    expect(linesOutlast(spans, { start: 0, end: 96 })).toBe(spans[1].to)
    expect(linesOutlast(spans, { start: 0, end: 400 })).toBeNull()
    expect(linesOutlast([], { start: 0, end: 10 })).toBeNull()
  })
})

describe('a figure\'s back to the camera (U5d, F42)', () => {
  const cam = { id: 'cam', name: 'Camera 1', pos: [0, 1.5, 4], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
  const fig = { id: 'fig', kind: 'mannequin', name: 'Ines', visible: true, pose: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } }
  const turn = (yaw: number) => ({ frame: 0, ease: 'linear', transform: { pos: [0, 0, 0], rot: [0, yaw, 0], scale: [1, 1, 1] } })
  it('marks the frames where the figure turns its back to the camera (yaw 0 faces it, +Z)', () => {
    const doc = { id: 'stg', objects: [fig], cameras: [cam], tracks: {}, size: { w: 1920, h: 1080, fps: 24 }, range: { start: 0, end: 20 },
      keyframes: { camera: {}, objects: { fig: [turn(0), { ...turn(180), frame: 10 }, { ...turn(180), frame: 15 }, { ...turn(0), frame: 20 }] } } } as unknown as StageDoc
    const away = awayStretches(doc, 'fig', 'cam', 0, 20)
    expect(away.length).toBe(1)
    const [a, b] = away[0]
    expect(a).toBeGreaterThan(5); expect(a).toBeLessThan(10); expect(b).toBeGreaterThanOrEqual(15); expect(b).toBeLessThan(20)
    expect(awayStretches({ ...doc, keyframes: { camera: {}, objects: {} } } as unknown as StageDoc, 'fig', 'cam', 0, 20)).toEqual([])   // facing the camera throughout
  })
})
