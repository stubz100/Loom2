// The review of 2026-10-27: V84 — a render's reply lands on the document as it is now (an edit made during the render stays and rides
// the new revision); V88 — removing a parent takes its selected child out of the selection too.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc, StageObject } from '../../api/types'
import { takeRendered, useStage } from './stageStore'

const obj = (id: string, kind: StageObject['kind'], extra: Partial<StageObject> = {}): StageObject => ({ id, kind, name: id, preset: kind === 'mannequin' ? 'adult' : null, asset_id: null,
  transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1,
  pose: kind === 'mannequin' ? { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {} } : null,
  billboard: false, profile_id: null, version: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null,
  plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null, ...extra }) as unknown as StageObject
const DOC = (objects: StageObject[], extra: Partial<StageDoc> = {}) => ({ schema_version: 3, id: 'stg_1', name: 'Quay', purpose: 'stage', bound: null, size: { w: 1920, h: 1080, fps: 24 }, objects,
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1', keyframes: { camera: {}, objects: {} },
  range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '', ...extra }) as unknown as StageDoc

describe('stage fixes (V84, V88)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  })
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); useStage.setState({ current: null, selected: null, stages: [], undo: [], redo: [] }) })

  it('V84: the reply replaces the document when nothing changed meanwhile, and only adds its passes and revision when something did', () => {
    const rendered = DOC([obj('crate', 'prop')])
    useStage.setState({ current: rendered, stages: [rendered] })
    const reply = DOC([obj('crate', 'prop')], { passes: [{ camera_id: 'cam_1', revision: 1 }], group_id: 'grp_p', revision: 2, updated_at: 'later' })
    takeRendered(reply, rendered, useStage.getState, useStage.setState)
    expect(useStage.getState().current).toBe(reply)
    const again = useStage.getState().current!
    useStage.setState({ current: again })
    useStage.getState().apply((d) => ({ ...d, objects: [...d.objects, obj('stool', 'prop')] }), 'add')   // an edit during the next render
    const edited = useStage.getState().current!
    const reply2 = DOC([obj('crate', 'prop')], { passes: [{ camera_id: 'cam_1', revision: 2 }], group_id: 'grp_p', revision: 3, updated_at: 'latest' })
    takeRendered(reply2, again, useStage.getState, useStage.setState)
    const cur = useStage.getState().current!
    expect(cur.objects.map((o) => o.id)).toEqual(['crate', 'stool'])                      // the edit stays …
    expect(cur.passes).toEqual(reply2.passes)
    expect(cur.revision).toBe(3)                                                              // … on the reply's revision
    expect(cur).not.toBe(edited)
    expect(useStage.getState().stages[0]).toBe(reply2)
  })

  it('V88: a selected child goes with its removed parent', () => {
    useStage.setState({ current: DOC([obj('fig_1', 'mannequin'), obj('cup', 'prop', { parent: 'fig_1' }), obj('crate', 'prop')]), selected: 'cup', undo: [], redo: [] })
    useStage.getState().removeObject('fig_1')
    expect(useStage.getState().current!.objects.map((o) => o.id)).toEqual(['crate'])
    expect(useStage.getState().selected).toBeNull()
    useStage.setState({ selected: 'crate' })
    useStage.getState().removeObject('nothing')
    expect(useStage.getState().selected).toBe('crate')
  })
})
