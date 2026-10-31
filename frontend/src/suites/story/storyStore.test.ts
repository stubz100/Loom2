// D90: the lip-sync window check on voiced lines (B6) and the pending profile body a typed name and stub share (B14).
import { describe, expect, it } from 'vitest'
import type { FlowNode } from '../../api/types'
import { freeSpot, mergeProfileBody, voicedLines } from './storyStore'

const node = (id: string, lines: FlowNode['lines']): FlowNode => ({
  schema_version: 1, id, type: 'shot', title: id, lines, options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, place_id: null, speaker_versions: {}, colour: null, beat_id: null, scene_id: null, own: [],
  revision: 0, created_at: '', updated_at: '',
})
const line = (text: string, audio: string | null) => ({ speaker: null, text, audio_asset_id: audio, audio_text: text })

describe('voicedLines (D90 B6)', () => {
  const nodes = { a: node('a', [line('short', 'ast_s'), line('long', 'ast_l'), line('silent', null)]), own: node('own', [line('unknown', 'ast_u')]) }
  it("W33: a shot's own node's lines only (Departure offered The seal's); a shot outside the Flow, every voiced line; lines with no audio skipped", () => {
    expect(voicedLines(nodes, 'own').map((l) => `${l.node_id}:${l.index}`)).toEqual(['own:0'])
    expect(voicedLines(nodes, null).map((l) => `${l.node_id}:${l.index}`)).toEqual(['a:0', 'a:1', 'own:0'])
  })
  it('marks a line past the window by its audio duration; an unknown duration or window is offered', () => {
    const secs = { ast_s: 3.1, ast_l: 6.2 }
    const got = voicedLines(nodes, 'a', secs, 4.81)
    expect(got.map((l) => [l.index, l.too_long, l.seconds])).toEqual([[0, false, 3.1], [1, true, 6.2]])
    expect(voicedLines(nodes, 'own', secs, 4.81).map((l) => [l.index, l.too_long, l.seconds])).toEqual([[0, false, null]])
    expect(voicedLines(nodes, 'a', secs, null).some((l) => l.too_long)).toBe(false)
  })
})

describe('mergeProfileBody (D90 B14)', () => {
  it('keeps the later field and merges the versions by id', () => {
    expect(mergeProfileBody({ name: 'Mara', versions: [{ id: 'v1', stub: 'a' }] }, { versions: [{ id: 'v1', stub: 'ab' }, { id: 'v2', stub: 'x' }] }))
      .toEqual({ name: 'Mara', versions: [{ id: 'v1', stub: 'ab' }, { id: 'v2', stub: 'x' }] })
    expect(mergeProfileBody({ name: 'Ma' }, { name: 'Mara', cls: 'place' })).toEqual({ name: 'Mara', cls: 'place' })
    expect(mergeProfileBody({ versions: [{ id: 'v1', stub: 's' }] }, { versions: [{ id: 'v1', hero_asset_id: 'ast_h' }] })).toEqual({ versions: [{ id: 'v1', stub: 's', hero_asset_id: 'ast_h' }] })
  })
})

describe('freeSpot (W24 = F20)', () => {
  it('puts a new Flow node where no node is: the spot asked, else the next free one beside it', () => {
    expect(freeSpot({ x: 100, y: 100 }, [])).toEqual({ x: 100, y: 100 })
    expect(freeSpot({ x: 100, y: 100 }, [{ x: 110, y: 90 }])).toEqual({ x: 360, y: 100 })               // it landed on the last one
    expect(freeSpot({ x: 100, y: 100 }, [{ x: 100, y: 100 }, { x: 360, y: 100 }])).toEqual({ x: 620, y: 100 })
  })
})
