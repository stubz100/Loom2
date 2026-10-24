// CE2 (D126): a gesture on the tracks as the FilmCraft command it asks for.
import { describe, expect, it } from 'vitest'
import type { CutItem, CutTrack, CutTracks } from '../../../api/types'
import { clampTrim, dragStep, gripAt, itemAt, razorStep, TICK, trackRef, transitionStep, underSceneGrade } from './cut'

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

describe('sound (CE3)', () => {
  it('fades either edge, sets a gain, ducks the music under the lines and evens the dialogue out', async () => {
    const { db, duckSteps, evenDialogueSteps, fadeStep, gainStep } = await import('./cut')
    const music = item(20, 0, 30, 'sound')
    const cutWithSound = { ...cut, audio: [a1, { ...a1, id: 4, items: [music] } as CutTrack] } as CutTracks
    expect(fadeStep(music, 'out')).toEqual({ id: 'sequence.applyAudioTransition', params: { clip: 20, frames: 12, edge: 'out' } })
    expect(gainStep(music, -6)).toEqual({ id: 'clip.audioGain', params: { clips: [20], db: -6, mode: 'set' } })
    expect(duckSteps(cutWithSound, [music]).map((s) => [s.id, s.params])).toEqual([
      ['essentialSound.setType', { clips: [12], type: 'dialogue' }], ['essentialSound.setType', { clips: [20], type: 'music' }], ['essentialSound.generateDucking', { clips: [20] }]])
    expect(duckSteps({ ...cutWithSound, audio: [{ ...a1, items: [] } as CutTrack] } as CutTracks, [music])).toEqual([])   // no line: nothing to duck under
    expect(evenDialogueSteps(cutWithSound)[1]).toEqual({ id: 'essentialSound.autoMatch', params: { clips: [12], target: -23 } })
    expect([db(-6), db(3), db(0), db(-10.36)]).toEqual(['−6 dB', '+3 dB', '0 dB', '−10.4 dB'])
  })
})

describe('the channel strip (D127)', () => {
  it('reads as the author wrote it and takes typed values inside the ranges', async () => {
    const { dialogueOf, panLabel, stripLabel, stripValue, volumeLabel, widthLabel } = await import('./cut')
    expect([panLabel(-100), panLabel(0), panLabel(-40), panLabel(100)]).toEqual(['100 % L', '50 % L · 50 % R', '70 % L · 30 % R', '100 % R'])
    expect([volumeLabel(-96), volumeLabel(18), widthLabel(0), widthLabel(150)]).toEqual(['−∞ dB', '+18 dB', 'mono', '150 %'])
    expect(stripLabel({ gain_db: 0, volume_db: 0, pan: 0, width: 100 })).toBe('')
    expect(stripLabel({ gain_db: -6, volume_db: -96, pan: -40, width: 150 })).toBe('gain −6 dB · vol −∞ dB · 70 % L · 30 % R · width 150 %')
    expect([stripValue('gain_db', '−48'), stripValue('volume_db', '-inf'), stripValue('volume_db', '+20 dB'), stripValue('width', '120 %'), stripValue('pan', 'left'), stripValue('pan', '  ')])
      .toEqual([-36, -96, 18, 120, null, null])
    // a sound on a dialogue track counts as dialogue (ducking and evening out take it)
    const talk = item(30, 0, 10, 'sound')
    const t = { ...cut, audio: [{ ...a1, role: 'dialogue', items: [item(12, 0, 10, 'line'), talk] } as CutTrack, { ...a1, id: 5, role: 'music', items: [item(31, 0, 10, 'sound')] } as CutTrack] } as CutTracks
    expect(dialogueOf(t).map((i) => i.id)).toEqual([12, 30])
  })
})

describe('the strip sliders (D127)', () => {
  it('give the volume a fader taper and the others their detents', async () => {
    const { detent, faderDb, faderPos } = await import('./cut')
    expect([faderDb(0), faderDb(0.25), faderDb(1), faderDb(faderPos(0)), faderDb(faderPos(-6)), faderDb(faderPos(12.5))]).toEqual([-96, -30, 18, 0, -6, 12.5])
    expect(faderPos(-96)).toBe(0)
    expect([detent('gain_db', 0.4), detent('gain_db', -0.6), detent('pan', -2), detent('width', 97), detent('width', 90)]).toEqual([0, -0.6, 0, 100, 90])
  })
})

describe('captions (CE5)', () => {
  it('move by the body, trim by an edge, a caption a frame long at least', async () => {
    const { captionStep } = await import('./cut')
    const cap = { id: 7, duration: 10 }
    expect(captionStep(cap, 'body', 5.4)).toEqual({ id: 'captions.move', params: { captions: [7], deltaFrames: 5 } })
    expect(captionStep(cap, 'in', 30)).toEqual({ id: 'captions.trim', params: { caption: 7, edge: 'in', deltaFrames: 9 } })
    expect(captionStep(cap, 'out', -30)).toEqual({ id: 'captions.trim', params: { caption: 7, edge: 'out', deltaFrames: -9 } })
    expect(captionStep(cap, 'body', 0.2)).toBeNull()
  })
})

describe('a scene grade over a take (RC2f)', () => {
  it('finds an adjustment clip on the Grade track over the take', () => {
    const adj = { id: 9, kind: 'adjustment', start: 100, duration: 200 } as unknown as CutItem
    const t = { video: [{ id: 1, name: 'V1', items: [] }, { id: 2, name: 'Grade', items: [adj] }], audio: [] } as unknown as CutTracks
    expect(underSceneGrade(t, { start: 150, duration: 50 })).toBe(true)
    expect(underSceneGrade(t, { start: 300, duration: 50 })).toBe(false)                     // after it
    expect(underSceneGrade({ ...t, video: [t.video[0], { ...t.video[1], name: 'V2' }] } as CutTracks, { start: 150, duration: 50 })).toBe(false)   // not the Grade track
  })
})
