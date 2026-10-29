// D125 (SP6): the cut from the Flow — a route's walk with the picks, its lane at the approved takes (trims and dissolves kept on Assemble
// again), a newer approved take marked changed and Update swapping it.
import { describe, expect, it } from 'vitest'
import type { FlowGraph, FlowNode, Shot, ShotVersion } from '../../../api/types'
import { assembleLane, laneChanges, routeLabel, routePicks, updateClip, walkRoute } from './assemble'

const node = (id: string, type: FlowNode['type'], extra: Partial<FlowNode> = {}): FlowNode =>
  ({ id, type, title: id, lines: [], options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, place_id: null, speaker_versions: {}, colour: null, revision: 0, schema_version: 1, created_at: '', updated_at: '', ...extra }) as FlowNode
const ver = (extra: Partial<ShotVersion> = {}): ShotVersion =>
  ({ id: 'v1', state: 'open', stage_id: null, camera_id: null, stage_revision: null, frame_asset_id: null, clip_id: null, takes: [], derived_from: null, created_at: '', finalized_at: null, recipe: null, ...extra }) as ShotVersion
const shot = (id: string, versions: Partial<ShotVersion>[], current = 'v1'): Shot =>
  ({ id, name: id, owner_node: null, current, versions: versions.map((v) => ver(v)), revision: 0, schema_version: 1, created_at: '', updated_at: '' }) as Shot

const nodes = {
  start: node('start', 'start'), arrival: node('arrival', 'shot', { shot_id: 's_arr' }), reunion: node('reunion', 'shot', { shot_id: 's_reu' }),
  choice: node('choice', 'choice', { title: 'Stay or go', options: [{ id: 'stay', label: 'Stay', require: null, set: [] }, { id: 'leave', label: 'Leave', require: null, set: [] }] }),
  talk: node('talk', 'shot', { shot_id: 's_talk' }), door: node('door', 'shot', { shot_id: 's_door' }),
}
const graph = { start: 'start', edges: [{ from: 'start', port: 'out', to: 'arrival' }, { from: 'arrival', port: 'out', to: 'reunion' }, { from: 'reunion', port: 'out', to: 'choice' },
  { from: 'choice', port: 'opt:stay', to: 'talk' }, { from: 'choice', port: 'opt:leave', to: 'door' }, { from: 'talk', port: 'out', to: 'arrival' }] } as unknown as FlowGraph
const clips = new Map([['c_arr', { id: 'c_arr', frames: 48, fps: 24 }], ['c_reu', { id: 'c_reu', frames: 33, fps: 16 }], ['c_reu2', { id: 'c_reu2', frames: 20, fps: 16 }],
  ['c_talk', { id: 'c_talk', frames: 24, fps: 24 }], ['c_door', { id: 'c_door', frames: 24, fps: 24 }]])
const shots = [shot('s_arr', [{ clip_id: 'c_arr' }]), shot('s_reu', [{ clip_id: 'c_reu', state: 'final' }, { id: 'v2', clip_id: 'c_reu2' }], 'v2'), shot('s_talk', [{ clip_id: 'c_talk' }]), shot('s_door', [{}])]

describe('the cut from the Flow (D125 S13)', () => {
  it('walks one route with the picks — the first option when none is picked; a node met again ends it', () => {
    const first = walkRoute(graph, nodes, [], {})
    expect(first.nodes.map((n) => n.id)).toEqual(['arrival', 'reunion', 'talk'])                       // talk → arrival loops: the route ends
    expect(routeLabel(first.choices)).toBe('Stay'); expect(routePicks(first.choices)).toEqual({ choice: 'stay' })
    expect(walkRoute(graph, nodes, [], { choice: 'leave' }).nodes.map((n) => n.id)).toEqual(['arrival', 'reunion', 'door'])
  })
  it('lays each shot at its approved take (the final version, else the current), stamped; a shot without a clip is named, not laid', () => {
    const { lane, missing } = assembleLane(walkRoute(graph, nodes, [], { choice: 'leave' }).nodes, shots, clips, 24)
    expect(lane.clips.map((c) => [c.source, c.shot?.version, c.shot?.node, c.out, c.fps])).toEqual([['c_arr', 'v1', 'arrival', 48, undefined], ['c_reu', 'v1', 'reunion', 33, 16]])
    expect(missing).toEqual(['s_door'])
  })
  it('Assemble again keeps the trims and the dissolve where the same shots follow each other', () => {
    const route = walkRoute(graph, nodes, [], {}).nodes
    const a = assembleLane(route, shots, clips, 24).lane
    const edited = { ...a, clips: a.clips.map((c, i) => (i === 0 ? { ...c, in: 4, out: 40 } : c)), overlaps: [0, 6, 0] }
    const again = assembleLane(route, shots, clips, 24, edited).lane
    expect([again.clips[0].in, again.clips[0].out]).toEqual([4, 40]); expect(again.overlaps).toEqual([0, 6, 0])
    const swapped = assembleLane([route[1], route[0], route[2]], shots, clips, 24, edited).lane
    expect(swapped.overlaps).toEqual([0, 0, 0])                                                         // the pairs changed: cuts
  })
  it('a newer approved take marks the clip changed; Update swaps it and keeps the trims within the new clip', () => {
    const { lane } = assembleLane(walkRoute(graph, nodes, [], {}).nodes, shots, clips, 24)
    expect(laneChanges(lane, shots)).toEqual([])
    const later = shots.map((s) => (s.id === 's_reu' ? { ...s, versions: [s.versions[0], { ...s.versions[1], state: 'final' }] } as Shot : s))
    const ch = laneChanges({ ...lane, clips: lane.clips.map((c, i) => (i === 1 ? { ...c, in: 2, out: 30 } : c)) }, later)
    expect(ch).toEqual([{ i: 1, name: 's_reu', version: 'v2', clip: 'c_reu2' }])
    const up = updateClip({ ...lane, clips: lane.clips.map((c, i) => (i === 1 ? { ...c, in: 2, out: 30 } : c)) }, ch[0], clips.get('c_reu2')!)
    expect([up.clips[1].source, up.clips[1].shot?.version, up.clips[1].in, up.clips[1].out]).toEqual(['c_reu2', 'v2', 2, 20])
  })
})
