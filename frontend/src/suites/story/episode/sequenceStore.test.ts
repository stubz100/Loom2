// P17 (D83): the document ↔ lane conversions and the clip-bin drop rule.
import { describe, expect, it } from 'vitest'
import type { Clip, Timeline } from '../../../api/types'
import { laneDrop } from '../../../frame/dropRules'
import { clipsOf, laneClipFrom, laneOf } from './sequenceStore'

const tl = { id: 'tl_1', name: 'S', fps: 24, w: 1920, h: 1080, revision: 2, schema_version: 1, created_at: '', updated_at: '',
  clips: [{ id: 'a', clip_id: 'clp_a', in: 0, out: 120, fps: 24 }, { id: 'b', clip_id: 'clp_b', in: 5, out: 81, fps: 16 }], overlaps: [0, 12] } as unknown as Timeline
const clip = (id: string, fps: number, frames: number, asset_id = `ast_${id}`) => ({ id, fps, frames, asset_id, model_id: 'm', w: 64, h: 48 } as unknown as Clip)

describe('sequence conversions', () => {
  it('keeps a clip rate only when it differs from the lane and round-trips the rows', () => {
    const lane = laneOf(tl)
    expect(lane.clips[0]).toEqual({ id: 'a', source: 'clp_a', in: 0, out: 120 })
    expect(lane.clips[1]).toEqual({ id: 'b', source: 'clp_b', in: 5, out: 81, fps: 16 })
    const none = { shot_id: null, shot_version: null, node_id: null }                              // SY4: the stamps ride along, null when a plain clip
    expect(clipsOf(lane)).toEqual([{ id: 'a', clip_id: 'clp_a', in: 0, out: 120, fps: null, ...none }, { id: 'b', clip_id: 'clp_b', in: 5, out: 81, fps: 16, ...none }])
  })
  it("a shot version's clip keeps its stamps through the lane and back (17 §3e)", () => {
    const stamped = { ...tl, clips: [{ ...tl.clips[0], shot_id: 'sht_1', shot_version: 'v2', node_id: 'node_9' }] }
    const lane = laneOf(stamped)
    expect(lane.clips[0].shot).toEqual({ id: 'sht_1', version: 'v2', node: 'node_9' })
    expect(clipsOf(lane)[0]).toMatchObject({ shot_id: 'sht_1', shot_version: 'v2', node_id: 'node_9' })
    expect(laneClipFrom(clip('clp_w', 24, 10), 24, { id: 'sht_1', version: 'v1', node: null }).shot).toEqual({ id: 'sht_1', version: 'v1', node: null })
  })
  it('a new lane clip takes the whole Catalogue clip', () => {
    const c = laneClipFrom(clip('clp_w', 16, 81), 24)
    expect(c).toMatchObject({ source: 'clp_w', in: 0, out: 81, fps: 16 })
    expect(laneClipFrom(clip('clp_l', 24, 121), 24).fps).toBeUndefined()
  })
  it('the bin drop takes clips by asset or clip id and refuses everything else', () => {
    const clips = [clip('clp_a', 24, 10), clip('clp_b', 16, 20)]
    expect(laneDrop({ items: [{ kind: 'asset', id: 'ast_clp_a', media: 'video' }] }, clips)).toEqual({ take: [clips[0]], verdict: { ok: true, label: 'Add to the end of the sequence' } })
    expect(laneDrop({ items: [{ kind: 'asset', id: 'clp_b' }, { kind: 'asset', id: 'ast_clp_a' }] }, clips).take.map((c) => c.id)).toEqual(['clp_b', 'clp_a'])
    expect(laneDrop({ items: [{ kind: 'asset', id: 'ast_image', media: 'image' }] }, clips).verdict).toEqual({ ok: false, reason: 'Only clips go on the lane' })
    expect(laneDrop({ items: [{ kind: 'group', id: 'g' }] }, clips).verdict).toEqual({ ok: false })
  })
})
