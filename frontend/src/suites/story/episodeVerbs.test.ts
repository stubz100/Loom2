// D125 (SP7): Make the Flow from the spine (the beats not yet made, a row, the spine's order where the ports are free) and Voice all
// lines' count (unvoiced or changed since).
import { describe, expect, it } from 'vitest'
import type { FlowNode, StoryBeat } from '../../api/types'
import { linesToVoice, spineEdges, spineRow, spineTodo } from './episodeVerbs'

const beat = (id: string): StoryBeat => ({ id, title: id, line: '' })
const node = (id: string, extra: Partial<FlowNode> = {}): FlowNode => ({ id, type: 'shot', title: id, lines: [], beat_id: null, ...extra }) as FlowNode
const spine = ['b1', 'b2', 'b3'].map(beat)

describe('Make the Flow from the spine (D125 S4)', () => {
  it('skips a beat already made into a node', () => {
    expect(spineTodo(spine, [node('n2', { beat_id: 'b2' })]).map((b) => b.id)).toEqual(['b1', 'b3'])
  })
  it('lays the row under the Flow, the Start first when it needs one', () => {
    expect(spineRow([], 2, true)).toEqual({ start: { x: 0, y: 0 }, beats: [{ x: 280, y: 0 }, { x: 560, y: 0 }] })
    expect(spineRow([{ id: 'a', x: 40, y: 300 }], 1, false)).toEqual({ start: null, beats: [{ x: 280, y: 500 }] })
  })
  it('connects the Start and the beats in the spine\'s order, joins a beat made before, and leaves a taken port alone', () => {
    const made = { b1: 'n1', b2: 'n2', b3: 'n3' }
    expect(spineEdges(spine, spine, [], made, 'start')).toEqual([{ from: 'start', port: 'out', to: 'n1' }, { from: 'n1', port: 'out', to: 'n2' }, { from: 'n2', port: 'out', to: 'n3' }])
    expect(spineEdges(spine, [spine[0], spine[2]], [], made, 'start')).toEqual([{ from: 'start', port: 'out', to: 'n1' }, { from: 'n1', port: 'out', to: 'n2' }, { from: 'n2', port: 'out', to: 'n3' }])
    expect(spineEdges(spine, [spine[0]], [{ from: 'start', port: 'out', to: 'other' }], made, 'start')).toEqual([{ from: 'n1', port: 'out', to: 'n2' }])
  })
})

describe('Voice all lines (D125 S8)', () => {
  it("counts the Shots' lines not voiced yet or changed since (U2: a Dialogue is a Shot with lines; a Note's never count)", () => {
    const l = (text: string, audio: string | null = null, said: string | null = null) => ({ speaker: null, text, audio_asset_id: audio, audio_text: said })
    const nodes = [node('d', { type: 'shot', lines: [l('Hi.'), l('Done.', 'ast_1', 'Done.'), l('Now. ', 'ast_2', 'Now.'), l('Changed.', 'ast_3', 'Before.'), l('  ')] }), node('s', { lines: [l('A Shot speaks too.')] }), node('c', { type: 'comment', lines: [l('A note never.')] })]
    expect(linesToVoice(nodes)).toBe(3)
  })
})
