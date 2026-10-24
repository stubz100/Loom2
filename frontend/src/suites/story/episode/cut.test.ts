// CE2 (D126): a gesture on the tracks as the FilmCraft command it asks for.
import { describe, expect, it } from 'vitest'
import type { CutItem, CutTrack, CutTracks } from '../../../api/types'
import { clampTrim, dragStep, gripAt, itemAt, razorStep, TICK, trackRef, transitionStep } from './cut'

const item = (id: number, start: number, duration: number, kind: CutItem['kind'] = 'take'): CutItem =>
  ({ id, item: id + 100, name: `c${id}.png`, kind, start, duration, source_in: 0, speed: 1, reverse: false, enabled: true, hold: false } as unknown as CutItem)
const track = (id: number, items: CutItem[]): CutTrack => ({ id, kind: 'video', name: `T${id}`, locked: false, muted: false, enabled: true, items, transitions: [] } as unknown as CutTrack)
const v1 = track(1, [item(10, 0, 20), item(11, 20, 30)])
const v2 = track(2, [])
const a1 = { ...track(3, [item(12, 0, 10, 'line')]), kind: 'audio' } as CutTrack
const cut = { sequence: 9, fps: 24, w: 64, h: 36, duration: 50, video: [v1, v2], audio: [a1], undo: 0, redo: 0 } as unknown as CutTracks

describe('the editor\'s gestures as FilmCraft commands', () => {
  it('names tracks as FilmCraft does and finds the clip under a frame', () => {
    expect([trackRef(cut, v1), trackRef(cut, v2), trackRef(cut, a1)]).toEqual(['V1', 'V2', 'A1'])
    expect(itemAt(v1, 19)?.id).toBe(10)
    expect(itemAt(v1, 20)?.id).toBe(11)
    expect(itemAt(v1, 50)).toBeNull()
    expect([gripAt(2, 100), gripAt(50, 100), gripAt(97, 100), gripAt(3, 9)]).toEqual(['in', 'body', 'out', 'body'])
  })
  it('Select moves (across tracks of one kind) and trims; Ripple trims and closes up', () => {
    expect(dragStep(cut, 'select', v1, v1.items[1], 'body', 5, v2)).toEqual({ id: 'timeline.move', params: { moves: [{ clip: 11, track: 2, time: (25 * TICK) / 24 }], insert: false } })
    expect(dragStep(cut, 'select', v1, v1.items[1], 'body', 0, a1)).toBeNull()                     // a picture never lands on an audio track
    expect(dragStep(cut, 'select', v1, v1.items[0], 'out', -4)).toEqual({ id: 'timeline.trim', params: { clip: 10, edge: 'out', mode: 'regular', deltaFrames: -4 } })
    expect(dragStep(cut, 'ripple', v1, v1.items[0], 'out', -4)?.params?.mode).toBe('ripple')
    expect(dragStep(cut, 'ripple', v1, v1.items[0], 'body', 4)).toBeNull()
    expect(dragStep(cut, 'select', v1, v1.items[0], 'body', 0)).toBeNull()
  })
  it('Roll moves the edit point between two clips that touch; Slip and Slide take the body', () => {
    expect(dragStep(cut, 'roll', v1, v1.items[0], 'out', 3)).toEqual({ id: 'timeline.roll', params: { left: 10, right: 11, deltaFrames: 3 } })
    expect(dragStep(cut, 'roll', v1, v1.items[1], 'in', -50)).toEqual({ id: 'timeline.roll', params: { left: 10, right: 11, deltaFrames: -19 } })   // the left keeps a frame
    expect(dragStep(cut, 'roll', v1, v1.items[0], 'in', 3)).toBeNull()                              // nothing before the first clip
    expect(dragStep(cut, 'slip', v1, v1.items[0], 'body', 6)).toEqual({ id: 'timeline.slip', params: { clip: 10, deltaFrames: 6 } })
    expect(dragStep(cut, 'slide', v1, v1.items[1], 'body', -2)).toEqual({ id: 'timeline.slide', params: { clip: 11, deltaFrames: -2 } })
  })
  it('Razor cuts inside a clip only; a trim keeps a frame; a transition fits the clip', () => {
    expect(razorStep(cut, v1, 25)).toEqual({ id: 'timeline.razor', params: { time: (25 * TICK) / 24, track: 1 } })
    expect(razorStep(cut, v1, 20)).toBeNull()
    expect(razorStep(cut, v2, 5)).toBeNull()
    expect([clampTrim(v1.items[0], 'in', 40), clampTrim(v1.items[0], 'out', -40)]).toEqual([19, -19])
    expect(transitionStep(item(1, 0, 8), 'cross_dissolve', 'in').params).toMatchObject({ frames: 7, edge: 'in', effect: 'cross_dissolve' })
  })
})
