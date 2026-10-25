// proto01_UIcast CW3–CW5 (D142; 06 §2.7, 03 §4): Clay's verbs for Cast's things — a character's card adds its figure bound (or selects the
// one already there); a free copy keeps the body as it is; a bound mesh takes its prop's height; the line-up's figures posed at once.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Profile, ProfileVersion, StageDoc, StageObject } from '../../api/types'
import { useStory } from '../story/storyStore'
import { st, useStage } from './stageStore'

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null,
  anim_ref_back_asset_id: null, anim_test_clip_id: null, shell_asset_id: null, shell_from: null, poses: {}, from_idea: null, height_m: null, model_asset_id: null, model_from: null, body_fit_from: null,
  body_points: null, anim_ref_note: null, appearance: '', outfit: '', colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v })
const prof = (id: string, name: string, cls: Profile['cls'], v: Partial<ProfileVersion>) => ({ id, name, cls, current: 'v1', schema_version: 3, revision: 0, voice_id: null, created_at: '', updated_at: '', versions: [ver(v)] }) as unknown as Profile
const INES = prof('prf_i', 'Ines', 'character', { body: { height_m: 1.58 } as never })
const CUP = prof('prf_c', 'Cup', 'prop', { model_asset_id: 'ast_glb', height_m: 0.1 })
const obj = (id: string, kind: StageObject['kind'], extra: Partial<StageObject> = {}): StageObject => ({ id, kind, name: id, preset: kind === 'mannequin' ? 'adult' : null, asset_id: null,
  transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1, pose: kind === 'mannequin' ? { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {} } : null,
  billboard: false, profile_id: null, version: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null,
  things: [], things_document_id: null, height_m: null, place_set: null, ...extra }) as StageObject
const DOC = (objects: StageObject[]) => ({ schema_version: 3, id: 'stg_1', name: 'Quay', purpose: 'stage', bound: null, size: { w: 1920, h: 1080, fps: 24 }, objects,
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1', keyframes: { camera: {}, objects: {} },
  range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' }) as unknown as StageDoc
const objects = () => useStage.getState().current!.objects

describe("Cast's things in Clay (CW3–CW5)", () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })))   // the stage's own saves
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    useStory.setState({ profiles: [INES, CUP] })
  })
  afterEach(() => { vi.unstubAllGlobals(); useStage.setState({ current: null, selected: null }); useStory.setState({ profiles: [] }) })

  it("adds a character's figure bound and named — once: the card selects it after", () => {
    useStage.setState({ current: DOC([]), selected: null, undo: [], redo: [] })
    st().placeCharacter('prf_i', [1, 0, 0])
    expect(objects()).toHaveLength(1)
    expect(objects()[0]).toMatchObject({ kind: 'mannequin', name: 'Ines', profile_id: 'prf_i' })
    expect(objects()[0].body?.height_m).toBe(1.58)
    st().select(null); st().placeCharacter('prf_i')
    expect(objects()).toHaveLength(1)
    expect(useStage.getState().selected).toBe(objects()[0].id)
  })
  it('makes a free copy beside a bound figure: its body as it is, no character', () => {
    useStage.setState({ current: DOC([obj('fig_1', 'mannequin', { name: 'Ines', profile_id: 'prf_i', body: INES.versions[0].body, shadow_proxy: 'ast_shell' })]), selected: 'fig_1', undo: [], redo: [] })
    st().freeCopy('fig_1')
    const copy = objects()[1]
    expect(copy).toMatchObject({ name: 'Ines (free)', profile_id: null, version: null, shadow_proxy: 'ast_shell' })
    expect(copy.body?.height_m).toBe(1.58)
    expect(copy.transform.pos[0]).toBeCloseTo(0.8, 5)
    expect(useStage.getState().selected).toBe(copy.id)
  })
  it("gives a bound mesh its prop's height, and a free one the author's", () => {
    useStage.setState({ current: DOC([obj('mesh_1', 'mesh', { asset_id: 'ast_glb', profile_id: 'prf_c' }), obj('mesh_2', 'mesh', { asset_id: 'ast_other' })]), undo: [], redo: [] })
    st().syncBodies()
    expect(objects()[0].height_m).toBe(0.1)
    st().setHeight('mesh_2', 0.75); st().setHeight('mesh_1', 3)
    expect(objects()[1].height_m).toBe(0.75)
    expect(objects()[0].height_m).toBe(0.1)                                                            // a bound one's is Cast's
  })
  it('poses every figure at once (the line-up)', () => {
    useStage.setState({ current: DOC([obj('fig_1', 'mannequin'), obj('fig_2', 'mannequin'), obj('set_1', 'set', { preset: 'lineup' })]), undo: [], redo: [] })
    st().poseAll('sit')
    expect(objects().filter((o) => o.kind === 'mannequin').map((o) => o.pose?.preset)).toEqual(['sit', 'sit'])
  })
})
