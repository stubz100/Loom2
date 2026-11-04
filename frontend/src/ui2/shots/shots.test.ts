// U4 (D157, proto01_UI2 04): Shots' place in the hash, the old suite each level reads with, the levels old places are, the storyboard's cards.
import { describe, expect, it } from 'vitest'
import type { FlowGraph, FlowNode, Profile, Shot, ShotVersion } from '../../api/types'
import { boardPlaylist, nextLevel, routeRows, type RouteRow } from './route'
import { animaticState, cameraUsers, castOf, type StageLite } from './scene'
import { clampLength, sceneLength, sceneSeconds } from '../../suites/stage/sceneLength'
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
    expect([levelOf({ suite: 'stage' }), levelOf({ suite: 'animate' }), levelOf({ suite: 'final' }), levelOf({ suite: 'story', tab: 'flow' })]).toEqual([null, 'performance', 'final', 'flow'])   // C0 (D181): the stage suite is Clay's layer
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
    const withCards = routeRows({ flowGraph: graph, flowNodes: nodes, shots, finals: [], cuts: [], clipsById: {}, cards: { s_b: { take_asset_id: 'ast_take' } as never } })
    expect(withCards[1].thumb).toBe('ast_take')                                                       // W52: its clips not loaded, the board's take
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
  const stage: StageLite = { id: 'stg', name: 'Pier', revision: 3, fps: 24, range: { start: 0, end: 96 }, length: 120, cameras: [{ id: 'c1', name: 'Camera 1' }, { id: 'c2', name: 'Camera 1 2' }],
    objects: [{ id: 'o1', kind: 'mannequin', name: 'Figure 1', profile_id: 'prf_ines', version: null, visible: true }, { id: 'o2', kind: 'mannequin', name: 'Figure 2', profile_id: null, version: null, visible: true },
      { id: 'o3', kind: 'mesh', name: 'Lantern', profile_id: 'prf_lamp', version: 'v1', visible: true }, { id: 'o4', kind: 'mesh', name: 'Crate', profile_id: null, version: null, visible: true },
      { id: 'o5', kind: 'set', name: 'Pier', profile_id: null, version: null, visible: true }] }
  it('names the shot that looks through each camera', () => {
    expect(cameraUsers('stg', [shot('Wide', null, { stage_id: 'stg', camera_id: 'c1' }), shot('Close', null, { stage_id: 'stg', camera_id: 'c2' }), shot('Away', null, { stage_id: 'other', camera_id: 'c9' })])).toEqual({ c1: 'Wide', c2: 'Close' })
  })
  it('the cast: the figures, bound or not, and the World props, each with what it lacks for Clay', () => {
    const pv = (extra: object) => ({ id: 'v1', hero_asset_id: 'ast_h', anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_ref_side_asset_id: null, body_fit_from: null, model_asset_id: null, height_m: null, place_set: null, ...extra })
    const profiles = [{ id: 'prf_ines', name: 'Ines', cls: 'character', voice_id: null, current: 'v1', versions: [pv({ anim_ref_asset_id: 'ast_a', body_fit_from: 'ast_a', shell_asset_id: 'ast_s' })] },   // C0: the Library counts the shell too
      { id: 'prf_lamp', name: 'Lantern', cls: 'prop', voice_id: null, current: 'v1', versions: [pv({})] }] as unknown as Profile[]
    expect(castOf(stage, profiles).map((m) => [m.name, m.cls, m.line])).toEqual([['Ines', 'character', 'Ready for Clay'], ['Figure 2', null, 'not bound to World'], ['Lantern', 'prop', '2 to go']])
  })
})

describe('the owed work (U6c, D164)', () => {
  it("the newest final of the shot version and the server's count of what it owes: the queued items' minutes, the listed ones' why", async () => {
    const { owedOf, owedTitle } = await import('./shotsStore')
    const fin = (id: string, at: string, extra = {}) => ({ id, shot_id: 'sht_a', shot_version: 'v1', created_at: at, ...extra })
    const item = (kind: string, layer: string, name: string, extra = {}) => ({ kind, layer, name, queue: true, after: false, why: null, seconds: 200, ...extra }) as never
    const owed = {
      f_old: { final_id: 'f_old', items: [item('perform', 'fig', 'Tomas')], seconds: 200, band: [48, 220] },
      f_new: { final_id: 'f_new', band: [48, 220], seconds: 660, items: [item('plate', 'plate', 'Pier', { seconds: 60 }), item('perform', 'fig', 'Tomas'), item('face', 'fig', 'Tomas', { after: true, seconds: 400 }),
        item('lipsync', 'ines', 'Ines', { queue: false, why: 'it is seen from behind', seconds: null })] },
    }
    const finals = [fin('f_old', '1'), fin('f_new', '2'), fin('f_other', '3', { shot_id: 'sht_b' })]
    const o = owedOf(finals, owed as never, 'sht_a', 'v1')!
    expect([o.fid, o.queued, o.minutes, o.extra]).toEqual(['f_new', 3, 11, 'the plate and the face work'])  // 660 s; W42: what it adds to the card's performances (lip-sync not queued)
    expect(owedTitle(o).split('\n')).toEqual(['The plate · ≈ 1 min', 'Tomas: performance · ≈ 3 min', 'Tomas: face pass (after its performance) · ≈ 7 min',
      'Ines: lip-sync — not queued: it is seen from behind'])
    expect(owedOf(finals, { f_new: { ...owed.f_new, items: [] } } as never, 'sht_a', 'v1')).toBeNull()                 // nothing owed
    expect(owedOf(finals, {} as never, 'sht_a', 'v1')).toBeNull()                                                     // not counted yet
    expect(owedOf(finals, owed as never, 'sht_a', 'v2')).toBeNull()                                                   // v1's finals are not v2's
    expect(owedOf([fin('f_a1', '1', { shot_version: null })], { f_a1: owed.f_old } as never, 'sht_a', 'v2')).toEqual(expect.objectContaining({ fid: 'f_a1' }))   // one made before A1 names no version
  })
  it("an owed run's toast counts what it queued now and after a matte, and names what was refused", async () => {
    const { owedRunText } = await import('../../suites/stage/finalShot')
    expect(owedRunText([{ kind: 'perform', job_id: 'j1' }, { kind: 'perform', job_id: 'j2' }, { kind: 'face', job_id: null }, { kind: 'lipsync', job_id: 'j3' }], []))
      .toBe('Queued: 2 performances, 1 face pass after its matte, 1 lip-sync')
    expect(owedRunText([], [{ kind: 'face', layer: 'fig', why: 'Tomas has no matte yet — matte it first' }])).toBe('Nothing queued · face pass of fig refused: Tomas has no matte yet — matte it first')
  })
})

describe('Record and the scene\'s length (C3, D181)', () => {
  it('reads the animatic row\'s state: none, current, stale once the scene\'s revision moved past the recording', () => {
    const a = { stage_id: 'stg_1', stage_revision: 4 }
    expect(animaticState(null, { id: 'stg_1', revision: 9 })).toBe('none')
    expect(animaticState(a, null)).toBe('current')
    expect(animaticState(a, { id: 'stg_1', revision: 4 })).toBe('current')
    expect(animaticState(a, { id: 'stg_1', revision: 5 })).toBe('stale')
    expect(animaticState(a, { id: 'stg_2', revision: 50 })).toBe('current')                 // another scene: nothing to compare
  })
  it('reads a scene\'s length: as set, else what it spans (a scene from before C3), never below its range nor past 20 s', () => {
    expect(sceneLength({ length: 120, range: { start: 0, end: 119 }, size: { fps: 24 } })).toBe(120)
    expect(sceneLength({ length: 0, range: { start: 0, end: 120 }, size: { fps: 24 } })).toBe(121)
    expect(sceneLength({ length: 0, range: { start: 0, end: 30 }, size: { fps: 24 } })).toBe(120)
    expect(sceneSeconds({ length: 36, range: { start: 0, end: 10 }, size: { fps: 24 } })).toBe('1.5')
    expect(clampLength({ length: 120, range: { start: 0, end: 150 }, size: { fps: 24 } }, 2)).toBe(151)
    expect(clampLength({ length: 120, range: { start: 0, end: 10 }, size: { fps: 24 } }, 99)).toBe(480)
  })
})

describe('the storyboard plays (C4, 04 §4.4)', () => {
  const row = (id: string, v: Partial<ShotVersion>, n: number): RouteRow => ({ shot: shot(id, null, v), node: null, group: null, n, label: id, v: shot(id, null, v).versions[0], thumb: null, dots: { clay: 'na', performance: 'na', final: 'na' } })
  it("plays each card's current picture in order — the render, else the take, else the animatic, else the still — for the shot's length", () => {
    const rows = [row('a', { clip_id: 'clp_r' }, 1), row('b', { clip_id: 'clp_t' }, 2), row('c', { animatic: { clip_id: 'clp_a', asset_id: 'ast_a', frames: 48, fps: 24, size: {}, stage_id: 'stg', stage_revision: 1, recorded_at: '' } } as Partial<ShotVersion>, 3), row('d', { frame_asset_id: 'ast_f' }, 4), row('e', {}, 5)]
    const clips = { clp_r: { asset_id: 'ast_r', frames: 241, fps: 24, model_id: 'composition' }, clp_t: { asset_id: 'ast_t', frames: 161, fps: 16, model_id: 'test-animate' } }
    const list = boardPlaylist(rows, clips, { a: { length_s: 10.04 }, b: { length_s: 10.06 } })
    expect(list.map((x) => [x.n, x.kind, x.asset, x.seconds])).toEqual([[1, 'final', 'ast_r', 10.04], [2, 'performance', 'ast_t', 10.06], [3, 'animatic', 'ast_a', 2], [4, 'still', 'ast_f', 2], [5, 'none', null, 2]])
  })
})
