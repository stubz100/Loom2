import { describe, expect, it } from 'vitest'
import type { FlowGraph, FlowNode } from '../../../api/types'
import { optionsAvailable, startPlay, stepPlay } from './play'

const node = (id: string, type: FlowNode['type'], extra: Partial<FlowNode> = {}): FlowNode => ({
  schema_version: 1, id, type, title: id, lines: [], options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, place_id: null, speaker_versions: {}, colour: null,
  revision: 0, created_at: '', updated_at: '', ...extra,
})
const graph = (start: string | null, edges: [string, string, string][]): FlowGraph => ({
  schema_version: 1, nodes: [], edges: edges.map(([from, port, to]) => ({ from, port, to })), start, revision: 0, updated_at: '',
})
const VARS = [{ name: 'met', type: 'bool' as const, values: [], default: false }, { name: 'door', type: 'enum' as const, values: ['open', 'shut'], default: 'shut' }]

describe('play (17 §3d)', () => {
  const nodes: Record<string, FlowNode> = Object.fromEntries([
    node('s', 'start'), node('hello', 'dialogue', { lines: [{ speaker: null, audio_asset_id: null, audio_text: null, text: 'Hi.' }] }),
    node('pick', 'choice', { options: [{ id: 'go', label: 'Go', require: null, set: [{ var: 'met', value: true }] }, { id: 'stay', label: 'Stay', require: { var: 'met', value: true }, set: [] }] }),
    node('q', 'condition', { cond: { var: 'met', op: 'eq', value: true } }), node('yes', 'shot'), node('no', 'shot'), node('act', 'action', { set: [{ var: 'door', value: 'open' }] }),
    node('jump', 'jump', { target: 'hello' }), node('note', 'comment'),
  ].map((n) => [n.id, n]))
  const g = graph('s', [['s', 'out', 'hello'], ['hello', 'out', 'pick'], ['pick', 'opt:go', 'q'], ['pick', 'opt:stay', 'note'], ['q', 'then', 'yes'], ['q', 'else', 'no'], ['yes', 'out', 'act'], ['act', 'out', 'jump']])

  it('starts at the first waiting node with the defaults', () => {
    const p = startPlay(g, nodes, VARS)
    expect(p.node).toBe('hello'); expect(p.waiting).toBe('next'); expect(p.vars).toEqual({ met: false, door: 'shut' }); expect(p.trail).toEqual(['s', 'hello'])
  })
  it('a choice offers only the options whose requirement holds, applies the pick and takes the condition branch', () => {
    let p = stepPlay(startPlay(g, nodes, VARS), g, nodes)
    expect(p.node).toBe('pick'); expect(p.waiting).toBe('choice')
    expect(optionsAvailable(nodes.pick, p.vars).map((o) => o.id)).toEqual(['go'])             // Stay needs met
    expect(stepPlay(p, g, nodes, 'stay')).toBe(p)                                              // not offered: nothing happens
    p = stepPlay(p, g, nodes, 'go')
    expect(p.vars.met).toBe(true); expect(p.node).toBe('yes')                                 // the condition took then
    p = stepPlay(p, g, nodes)                                                                   // yes → act (sets door) → jump → hello
    expect(p.node).toBe('hello'); expect(p.vars.door).toBe('open'); expect(p.trail.slice(-3)).toEqual(['act', 'jump', 'hello'])
    p = stepPlay(stepPlay(p, g, nodes), g, nodes, 'stay')                                      // met now: Stay offered; it leads to a comment = the end
    expect(p.ended).toBe(true); expect(p.node).toBeNull()
  })
  it('ends without a start, at a dangling edge and on a loop of pass-through nodes', () => {
    expect(startPlay(graph(null, []), nodes, VARS).ended).toBe(true)
    expect(stepPlay(startPlay(graph('s', [['s', 'out', 'hello']]), nodes, VARS), graph('s', [['s', 'out', 'hello']]), nodes).ended).toBe(true)
    const loop = { a: node('a', 'start'), b: node('b', 'hub'), c: node('c', 'hub') }
    const lg = graph('a', [['a', 'out', 'b'], ['b', 'out', 'c'], ['c', 'out', 'b']])
    const p = startPlay(lg, loop, [])
    expect(p.ended).toBe(true); expect(p.steps).toBeGreaterThan(1000)
  })
})
