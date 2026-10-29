// U4 (D157, proto01_UI2 04): Shots' place in the hash, the old suite each level reads with, the levels old places are, the storyboard's cards.
import { describe, expect, it } from 'vitest'
import type { FlowGraph, FlowNode, Profile, Shot, ShotVersion } from '../../api/types'
import { nextLevel, routeRows } from './route'
import { cameraUsers, castOf, type StageLite } from './scene'
import { levelOf, placeOfHash, suiteOf } from './shotsStore'

const node = (id: string, type: FlowNode['type'], extra: Partial<FlowNode> = {}): FlowNode =>
  ({ id, type, title: id, lines: [], options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, place_id: null, speaker_versions: {}, colour: null, revision: 0, schema_version: 1, created_at: '', updated_at: '', ...extra }) as FlowNode
const ver = (extra: Partial<ShotVersion> = {}): ShotVersion =>
  ({ id: 'v1', state: 'open', stage_id: null, camera_id: null, stage_revision: null, frame_asset_id: null, clip_id: null, takes: [], derived_from: null, created_at: '', finalized_at: null, recipe: null, ...extra }) as ShotVersion
const shot = (id: string, owner: string | null, v: Partial<ShotVersion> = {}): Shot =>
  ({ id, name: id, owner_node: owner, current: 'v1', versions: [ver(v)], revision: 0, schema_version: 1, created_at: '', updated_at: '' }) as Shot

describe('Shots\' place (U4)', () => {
  it('reads #shots/<shot>/<level>, a level alone, and a shot alone as its Clay', () => {
    expect(placeOfHash('#shots')).toEqual({ shot: null, level: 'flow' })
    expect(placeOfHash('#shots/flow')).toEqual({ shot: null, level: 'flow' })
    expect(placeOfHash('#shots/shot_1/performance')).toEqual({ shot: 'shot_1', level: 'performance' })
    expect(placeOfHash('#shots/shot_1')).toEqual({ shot: 'shot_1', level: 'clay' })
    expect(placeOfHash('#world/character')).toBeNull()
  })
  it('a level reads with an old suite, and an old place lands on its level (Open the stage, Block it on a stage…)', () => {
    expect(['flow', 'clay', 'performance', 'final'].map((l) => suiteOf(l as never))).toEqual([{ suite: 'story', tab: 'flow' }, { suite: 'stage' }, { suite: 'animate' }, { suite: 'final' }])
    expect([levelOf({ suite: 'stage' }), levelOf({ suite: 'animate' }), levelOf({ suite: 'final' }), levelOf({ suite: 'story', tab: 'flow' })]).toEqual(['clay', 'performance', 'final', 'flow'])
    expect([levelOf({ suite: 'story', tab: 'cast' }), levelOf({ suite: 'generate' })]).toEqual([null, null])
  })
})

describe('the storyboard (U4)', () => {
  const nodes = { start: node('start', 'start'), a: node('a', 'shot', { shot_id: 's_a', title: 'The quay' }), b: node('b', 'shot', { shot_id: 's_b', title: '' }) }
  const graph = { start: 'start', edges: [{ from: 'start', port: 'out', to: 'a' }, { from: 'a', port: 'out', to: 'b' }] } as unknown as FlowGraph
  const shots = [shot('s_b', 'b'), shot('s_free', null), shot('s_a', 'a', { stage_id: 'stg', camera_id: 'cam', frame_asset_id: 'ast_f' })]
  const rows = routeRows({ flowGraph: graph, flowNodes: nodes, shots, finals: [], cuts: [], clipsById: {}, cards: {} })
  it('numbers the route\'s shots in the Flow\'s order, named after the node, an unbound shot left out', () => {
    expect(rows.map((r) => [r.n, r.shot.id, r.label])).toEqual([[1, 's_a', 'The quay'], [2, 's_b', 's_b']])
    expect(rows[0].thumb).toBe('ast_f')
  })
  it('the dots: Clay the stage, Performance the clip (owed on a stage route), Final the assembled shot; a shot opens on what it owes', () => {
    expect(rows[0].dots).toEqual({ clay: 'done', performance: 'owed', final: 'na' })
    expect(rows[1].dots.clay).toBe('na')
    expect(nextLevel(rows[0].dots)).toBe('performance')
    expect(nextLevel({ clay: 'owed', performance: 'owed', final: 'na' })).toBe('clay')
    expect(nextLevel({ clay: 'done', performance: 'na', final: 'owed' })).toBe('final')
  })
})

describe("the header's scene (U4c)", () => {
  const stage: StageLite = { id: 'stg', name: 'Pier', revision: 3, fps: 24, range: { start: 0, end: 96 }, cameras: [{ id: 'c1', name: 'Camera 1' }, { id: 'c2', name: 'Camera 1 2' }],
    objects: [{ id: 'o1', kind: 'mannequin', name: 'Figure 1', profile_id: 'prf_ines', version: null, visible: true }, { id: 'o2', kind: 'mannequin', name: 'Figure 2', profile_id: null, version: null, visible: true },
      { id: 'o3', kind: 'mesh', name: 'Lantern', profile_id: 'prf_lamp', version: 'v1', visible: true }, { id: 'o4', kind: 'mesh', name: 'Crate', profile_id: null, version: null, visible: true },
      { id: 'o5', kind: 'set', name: 'Pier', profile_id: null, version: null, visible: true }] }
  it('names the shot that looks through each camera', () => {
    expect(cameraUsers('stg', [shot('Wide', null, { stage_id: 'stg', camera_id: 'c1' }), shot('Close', null, { stage_id: 'stg', camera_id: 'c2' }), shot('Away', null, { stage_id: 'other', camera_id: 'c9' })])).toEqual({ c1: 'Wide', c2: 'Close' })
  })
  it('the cast: the figures, bound or not, and the World props, each with what it lacks for Clay', () => {
    const pv = (extra: object) => ({ id: 'v1', hero_asset_id: 'ast_h', anim_ref_asset_id: null, anim_ref_back_asset_id: null, body_fit_from: null, model_asset_id: null, height_m: null, place_set: null, ...extra })
    const profiles = [{ id: 'prf_ines', name: 'Ines', cls: 'character', voice_id: null, current: 'v1', versions: [pv({ anim_ref_asset_id: 'ast_a', body_fit_from: 'ast_a' })] },
      { id: 'prf_lamp', name: 'Lantern', cls: 'prop', voice_id: null, current: 'v1', versions: [pv({})] }] as unknown as Profile[]
    expect(castOf(stage, profiles).map((m) => [m.name, m.cls, m.line])).toEqual([['Ines', 'character', 'Ready for Clay'], ['Figure 2', null, 'not bound to World'], ['Lantern', 'prop', '2 to go']])
  })
})

describe('the owed layers (U6c)', () => {
  it('the newest final of the shot version, its plate and the character layers not performed yet, the GPU minutes by their batches', async () => {
    const { batchesOf, owedOf } = await import('./shotsStore')
    expect([batchesOf(65), batchesOf(77), batchesOf(100), batchesOf(149)]).toEqual([1, 1, 2, 2])
    const fin = (id: string, at: string, statuses: [string, string][], extra = {}) => ({ id, shot_id: 'sht_a', shot_version: 'v1', created_at: at, frames: 65,
      layers: statuses.map(([kind, status], i) => ({ id: `${kind}${i}`, kind, status })), ...extra })
    const finals = [fin('f_old', '1', [['plate', 'passes'], ['figure', 'passes']]), fin('f_new', '2', [['plate', 'done'], ['figure', 'passes'], ['figure', 'done'], ['prop', 'passes']]),
      fin('f_other', '3', [['figure', 'passes']], { shot_id: 'sht_b' })]
    expect(owedOf(finals, 'sht_a', 'v1')).toEqual({ fid: 'f_new', plate: false, figures: ['figure1'], minutes: 3 })
    expect(owedOf([fin('f', '1', [['plate', 'failed'], ['figure', 'passes'], ['figure', 'failed']])], 'sht_a', 'v1')!.minutes).toBe(8)   // 2 × 3.3 + 1
    expect(owedOf([fin('f', '1', [['plate', 'done'], ['figure', 'done']])], 'sht_a', 'v1')).toBeNull()
    expect(owedOf(finals, 'sht_a', 'v2')).toBeNull()                                                                  // v1's finals are not v2's
    expect(owedOf([fin('f_a1', '1', [['figure', 'passes']], { shot_version: null })], 'sht_a', 'v2')).toEqual(expect.objectContaining({ fid: 'f_a1' }))   // one made before A1 names no version: it counts
  })
})
