// P17 (D83): the single-lane model — positions, what shows at a tick (cuts, dissolves, a clip at another rate), the edits that keep
// the invariants, and the EDL text the server writes (the parity fixture of orchestrator/tests/test_timeline_d83.py).
import { describe, expect, it } from 'vitest'
import { append, at, chainIn, duration, len, move, remove, setOverlap, starts, tc, ticks, toEDL, trim, type Lane } from './lane'

const clip = (id: string, source: string, i: number, o: number, fps?: number) => ({ id, source, in: i, out: o, ...(fps ? { fps } : {}) })
const lane: Lane = { fps: 24, clips: [clip('a', 'clp_aaaa0001', 0, 120), clip('b', 'clp_bbbb0002', 10, 110), clip('c', 'clp_cccc0003', 0, 48)], overlaps: [0, 12, 0] }
const srcLen = () => 120

const PARITY_EDL = `TITLE: Parity
FCM: NON-DROP FRAME

001  aaaa0001 V     C        00:00:00:00 00:00:05:00 00:00:00:00 00:00:05:00
* FROM CLIP NAME: clp_aaaa0001

002  aaaa0001 V     C        00:00:04:12 00:00:04:12 00:00:04:12 00:00:04:12
002  bbbb0002 V     D    012 00:00:00:10 00:00:04:14 00:00:04:12 00:00:08:16
* FROM CLIP NAME: clp_bbbb0002

003  cccc0003 V     C        00:00:00:00 00:00:02:00 00:00:08:16 00:00:10:16
* FROM CLIP NAME: clp_cccc0003
`

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
    expect(at(lane, 120)).toEqual({ a: { i: 1, local: 22 } })
    expect(at(lane, 208)).toEqual({ a: { i: 2, local: 0 } })
    expect(at(lane, 256)).toBeNull()
    expect(at(lane, -1)).toBeNull()
  })
  it('a 16 fps clip on the 24 fps lane takes its duration in ticks and is scrubbed by nearest frame', () => {
    const mixed: Lane = { fps: 24, clips: [clip('w', 'clp_w', 0, 81, 16), clip('l', 'clp_l', 0, 121)], overlaps: [0, 24] }
    expect(ticks(mixed, mixed.clips[0])).toBe(122)
    expect(starts(mixed)).toEqual([0, 98])
    expect(duration(mixed)).toBe(219)
    expect(at(mixed, 0)).toEqual({ a: { i: 0, local: 0 } })
    expect(at(mixed, 3)).toEqual({ a: { i: 0, local: 2 } })                  // 3 ticks × 16 / 24 = 2 source frames
    expect(at(mixed, 97)!.a).toEqual({ i: 0, local: 64 })
    expect(at(mixed, 121)!.a.local).toBeLessThanOrEqual(80)                   // never past the clip's last frame
  })
})

describe('edits', () => {
  it('ripple trims keep ≥ 1 frame and dissolves shorter than both clips', () => {
    const t = trim(lane, 1, 'in', -20, srcLen)
    expect(t.clips[1].in).toBe(0)                                             // clamped at the source start
    const t2 = trim(lane, 1, 'out', -95, srcLen)
    expect(len(t2.clips[1])).toBe(5)
    expect(t2.overlaps[1]).toBe(4)                                            // 12 → shorter than the 5-frame clip
    expect(trim(lane, 2, 'out', 500, srcLen).clips[2].out).toBe(120)         // clamped at the source length
  })
  it('setOverlap, append, remove and move keep the first clip a cut', () => {
    expect(setOverlap(lane, 1, 200).overlaps[1]).toBe(99)                     // < min(ticks of a and b) = 100
    expect(setOverlap(lane, 2, 200).overlaps[2]).toBe(47)                     // < ticks of c = 48
    expect(setOverlap(lane, 0, 10).overlaps[0]).toBe(0)
    const l2 = append(lane, clip('d', 'clp_d', 0, 10))
    expect(l2.clips.length).toBe(4)
    expect(l2.overlaps).toEqual([0, 12, 0, 0])
    const l3 = remove(lane, 0)
    expect(l3.clips.map((c) => c.id)).toEqual(['b', 'c'])
    expect(l3.overlaps).toEqual([0, 0])                                       // b's dissolve had nothing to dissolve from
    const l4 = move(lane, 1, 0)
    expect(l4.clips.map((c) => c.id)).toEqual(['b', 'a', 'c'])
    expect(l4.overlaps).toEqual([0, 0, 0])
  })
})

describe('export', () => {
  it('timecodes and the EDL match the server (parity fixture)', () => {
    expect(tc(256, 24)).toBe('00:00:10:16')
    expect(tc(3600 * 24 + 25, 24)).toBe('01:00:01:01')
    expect(toEDL(lane, 'Parity')).toBe(PARITY_EDL)
  })
})

describe('D88 XE: a continuation after its parent starts past the overlap', () => {
  it('trims only when the lane ends on the clip it extends', () => {
    const l: Lane = { fps: 24, clips: [clip('a', 'clp_parent', 0, 121)], overlaps: [0] }
    expect(chainIn(l, 'clp_parent', 9, 121)).toBe(9)
    expect(chainIn(l, 'clp_other', 9, 121)).toBe(0)
    expect(chainIn(l, null, 9, 121)).toBe(0)
    expect(chainIn({ ...l, clips: [] }, 'clp_parent', 9, 121)).toBe(0)
    expect(chainIn(l, 'clp_parent', 121, 121)).toBe(0)                                            // never the whole clip
    expect(chainIn(null, 'clp_parent', 1, 81)).toBe(0)
  })
})
