// E13 (D74): the single-lane model — positions, what shows at a frame (cuts and dissolves), ripple trims keeping the invariants,
// timecodes, and the EDL / FCPXML a Resolve import reads.
import { describe, expect, it } from 'vitest'
import { at, duration, len, starts, tc, toEDL, toFCPXML, trim, type Lane } from './e13Lane'

const clip = (id: string, source: number, i: number, o: number) => ({ id, source, in: i, out: o })
const lane: Lane = { fps: 24, clips: [clip('a', 0, 0, 120), clip('b', 1, 10, 110), clip('c', 2, 0, 48)], overlaps: [0, 12, 0] }
const srcLen = () => 120

describe('positions and lookup', () => {
  it('places clips end to end, a dissolve pulling the next one in', () => {
    expect(starts(lane)).toEqual([0, 108, 208])
    expect(duration(lane)).toBe(256)
  })
  it('shows one clip on a cut and two mid-dissolve, the incoming weight rising', () => {
    expect(at(lane, 0)).toEqual({ a: { i: 0, local: 0 } })
    expect(at(lane, 107)).toEqual({ a: { i: 0, local: 107 } })
    const mid = at(lane, 114)!
    expect(mid.a).toEqual({ i: 0, local: 114 })
    expect(mid.b).toEqual({ i: 1, local: 16 })
    expect(mid.mix).toBeCloseTo(6.5 / 12)
    expect(at(lane, 120)).toEqual({ a: { i: 1, local: 22 } })           // the dissolve is over
    expect(at(lane, 208)).toEqual({ a: { i: 2, local: 0 } })            // a cut
    expect(at(lane, 256)).toBeNull()
    expect(at(lane, -1)).toBeNull()
  })
})

describe('ripple trims', () => {
  it('moves the edge within the source and ripples everything after', () => {
    const t = trim(lane, 0, 'out', -20, srcLen)
    expect(len(t.clips[0])).toBe(100)
    expect(starts(t)).toEqual([0, 88, 188])
    expect(lane.clips[0].out).toBe(120)                                 // the input is not changed
  })
  it('never leaves the source, never empties a clip, never lets a dissolve outgrow a neighbour', () => {
    expect(trim(lane, 0, 'out', 50, srcLen).clips[0].out).toBe(120)
    expect(trim(lane, 1, 'in', -50, srcLen).clips[1].in).toBe(0)
    expect(len(trim(lane, 2, 'in', 500, srcLen).clips[2])).toBe(1)
    const short = trim(lane, 1, 'out', -95, srcLen)                       // clip b: 5 frames → the 12-frame dissolve shrinks to 4
    expect(len(short.clips[1])).toBe(5)
    expect(short.overlaps[1]).toBe(4)
  })
})

describe('export', () => {
  it('timecodes are HH:MM:SS:FF', () => {
    expect(tc(0, 24)).toBe('00:00:00:00')
    expect(tc(24 * 3661 + 5, 24)).toBe('01:01:01:05')
  })
  it('an EDL has an event per clip, a dissolve where clips overlap, and records end at the duration', () => {
    const edl = toEDL(lane, 'E13', (s) => `CLIP${s}`)
    expect(edl).toMatch(/^TITLE: E13\nFCM: NON-DROP FRAME/)
    expect(edl).toMatch(/002 {2}CLIP1 {4}V {5}D {4}012 00:00:00:10 00:00:04:14 00:00:04:12 00:00:08:16/)
    expect(edl.match(/^00\d {2}/gm)).toHaveLength(4)                     // three events, the dissolve as a cut + D pair
    expect(edl).toContain(`00:00:08:16 00:00:10:16`)                    // the last record out = 256 frames
  })
  it('FCPXML: well formed, one asset per source, a cross dissolve where clips overlap, the sequence as long as the lane', () => {
    const xml = toFCPXML(lane, 'E13 & co', (s) => ({ name: `c0${s}.mp4`, src: `file:///F:/clips/c0${s}.mp4`, frames: 120 }), 640, 360)
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    expect(doc.querySelector('parsererror')).toBeNull()
    expect(doc.querySelectorAll('asset')).toHaveLength(3)
    expect(doc.querySelectorAll('spine > asset-clip')).toHaveLength(3)
    expect(doc.querySelector('spine > transition')?.getAttribute('duration')).toBe('12/24s')
    expect(doc.querySelector('sequence')?.getAttribute('duration')).toBe('256/24s')
    expect(doc.querySelector('event')?.getAttribute('name')).toBe('E13 & co')
  })
})
