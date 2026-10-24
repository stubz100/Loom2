// D125 (SP3): the Shots board's order (the Flow's routes, the branches naming their rows) and its cells (what each route owes, what is done).
import { describe, expect, it } from 'vitest'
import type { FlowGraph, FlowNode, Shot, ShotVersion } from '../../api/types'
import { bareNode, cellsOf, flowOrder, hasWork, lengthLine, nextStep, routeOf, type CellInput } from './board'

const node = (id: string, type: FlowNode['type'], extra: Partial<FlowNode> = {}): FlowNode =>
  ({ id, type, title: id, lines: [], options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, place_id: null, speaker_versions: {}, colour: null, revision: 0, schema_version: 1, created_at: '', updated_at: '', ...extra }) as FlowNode
const ver = (extra: Partial<ShotVersion> = {}): ShotVersion =>
  ({ id: 'v1', state: 'open', stage_id: null, camera_id: null, stage_revision: null, frame_asset_id: null, clip_id: null, takes: [], derived_from: null, created_at: '', finalized_at: null, recipe: null, ...extra }) as ShotVersion
const shot = (id: string, owner: string | null, v: Partial<ShotVersion> = {}): Shot =>
  ({ id, name: id, owner_node: owner, current: 'v1', versions: [ver(v)], revision: 0, schema_version: 1, created_at: '', updated_at: '' }) as Shot
const none: CellInput = { clipAudio: () => false, finals: [], cuts: [], busy: () => new Set() }

describe('the board\'s order (D125 SP3)', () => {
  const nodes = {
    start: node('start', 'start'), arrival: node('arrival', 'shot', { shot_id: 's_arr' }), reunion: node('reunion', 'dialogue', { shot_id: 's_reu' }),
    choice: node('choice', 'choice', { title: 'Stay or go', options: [{ id: 'stay', label: 'Stay', require: null, set: [] }, { id: 'leave', label: 'Leave', require: null, set: [] }] }),
    talk: node('talk', 'dialogue', { shot_id: 's_talk' }), door: node('door', 'shot', { shot_id: 's_door' }), lone: node('lone', 'shot', { shot_id: 's_lone' }),
  }
  const graph = { start: 'start', edges: [{ from: 'start', port: 'out', to: 'arrival' }, { from: 'arrival', port: 'out', to: 'reunion' }, { from: 'reunion', port: 'out', to: 'choice' },
    { from: 'choice', port: 'opt:leave', to: 'door' }, { from: 'choice', port: 'opt:stay', to: 'talk' }] } as unknown as FlowGraph
  const shots = ['s_door', 's_free', 's_talk', 's_lone', 's_reu', 's_arr'].map((id) => shot(id, id === 's_free' ? null : Object.values(nodes).find((n) => n.shot_id === id)!.id))
  it('walks the routes from the Start, the options in their order, then the shots off the routes and the unbound ones', () => {
    const rows = flowOrder(graph, nodes, shots)
    expect(rows.map((r) => r.shot.id)).toEqual(['s_arr', 's_reu', 's_talk', 's_door', 's_lone', 's_free'])
    expect(rows.map((r) => r.group)).toEqual([null, null, 'Stay or go ▸ Stay', 'Stay or go ▸ Leave', 'Not on a route', 'Unbound'])
  })
  it('RC2a: a bare Shot node is nothing but its shot, off the routes; a shot has work once it has a source, a take or a second version', () => {
    expect(bareNode(nodes.lone, graph)).toBe(true)
    expect(bareNode(nodes.door, graph)).toBe(false)                                         // on a route
    expect(bareNode(node('x', 'dialogue'), graph)).toBe(false)                              // a Dialogue is in the story
    expect(bareNode(node('y', 'shot', { place_id: 'prf_quay' }), graph)).toBe(false)        // a place of its own
    expect(hasWork(shot('a', null))).toBe(false)
    expect(hasWork(shot('b', null, { takes: [{ kind: 'image', id: 'ast_1', at: '' }] }))).toBe(true)
    expect(hasWork(shot('c', null, { stage_id: 'stg', camera_id: 'cam' }))).toBe(true)
    expect(hasWork({ versions: [ver(), ver({ id: 'v2' })] })).toBe(true)
  })
})

describe('the board\'s cells (D125 SP3)', () => {
  it('reads a route\'s owed steps, and what is done', () => {
    const s = shot('s', 'n', { frame_asset_id: 'ast_f' })
    const c = cellsOf(s, s.versions[0], node('n', 'shot'), none)
    expect(routeOf(s.versions[0])).toBe('i2v')
    expect([c.lines.state, c.voice.state, c.frame.state, c.stage.state, c.clip.state, c.final.state, c.approved.state, c.cut.state]).toEqual(['na', 'na', 'done', 'na', 'owed', 'na', 'owed', 'owed'])
    expect(nextStep(c)).toBe('clip')
  })
  it('a dialogue: its lines, its voices (a changed line is stale), lip-sync owed on the dialogue route', () => {
    const s = shot('s', 'n', { recipe: { template: 'dialogue', steps: [] } })
    const n = node('n', 'dialogue', { lines: [{ speaker: null, text: 'Hi.', audio_asset_id: 'ast_a', audio_text: 'Hi.' }, { speaker: null, text: 'Go, then.', audio_asset_id: 'ast_b', audio_text: 'Go.' }] })
    const c = cellsOf(s, s.versions[0], n, none)
    expect(c.lines).toEqual({ state: 'done', text: '2' })
    expect(c.voice).toEqual({ state: 'stale', text: '1 changed' })
    expect(c.lipsync.state).toBe('owed')
    expect(nextStep(c)).toBe('voice')
  })
  it('the clay route owes a stage and a final; a final on its camera counts; the lane marks an old take changed', () => {
    const s = shot('s', 'n', { recipe: { template: 'clay2', steps: [] }, stage_id: 'stg', camera_id: 'cam', clip_id: 'clp_new' })
    const x: CellInput = { ...none, finals: [{ shot_id: null, stage_id: 'stg', camera_id: 'cam', clip_id: 'clp_asm', layers: [{ status: 'done' }, { status: 'done' }] as never }],
      cuts: [{ clips: [{ shot_id: 's', shot_version: 'v1', clip_id: 'clp_old' }] }], clipAudio: (id) => id === 'clp_new' }
    const c = cellsOf(s, s.versions[0], node('n', 'dialogue'), x)
    expect(c.stage.state).toBe('done')
    expect(c.final).toEqual({ state: 'done', text: 'assembled' })
    expect(c.lipsync.state).toBe('done')
    expect(c.cut).toEqual({ state: 'stale', text: 'changed' })
    expect(c.frame.state).toBe('na')
  })
  it('a running job shows on its step', () => {
    const s = shot('s', 'n')
    const c = cellsOf(s, s.versions[0], node('n', 'shot'), { ...none, busy: () => new Set(['clip']) })
    expect(c.clip.state).toBe('running')
  })
})

describe('a Shot card\'s length (RC2b, D96)', () => {
  it('says where the length comes from and warns past the guide', () => {
    expect(lengthLine(undefined, 30)).toBeNull()
    expect(lengthLine({ length_s: null, length_from: null }, 30)).toBeNull()
    expect(lengthLine({ length_s: 12.34, length_from: 'clip' }, 30)).toEqual({ text: '12.3 s', over: false, title: '12.3 s (its clip)' })
    const long = lengthLine({ length_s: 95, length_from: 'final' }, 30)!
    expect(long.text).toBe('1 min 35 s'); expect(long.over).toBe(true); expect(long.title).toContain('past about 30 s')
  })
})
