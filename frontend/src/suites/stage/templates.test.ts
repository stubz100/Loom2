// D119 (SC2): stage templates in the store — the current arrangement (set, props, meshes, planes, lights; not the figures) saved under a
// name through /project/stage-templates, added to a stage with new ids (parents inside the template kept), deleted.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc, StageObject } from '../../api/types'
import { st, TEMPLATE_KINDS, useStage } from './stageStore'

const OBJ = (id: string, kind: StageObject['kind'], name: string, extra: Partial<StageObject> = {}): StageObject => ({
  id, kind, name, preset: null, asset_id: null, transform: { pos: [1, 0, 2], rot: [0, 0, 0], scale: [1, 1, 1] }, parent: null, locked: false, visible: true, colour_id: 1,
  pose: null, billboard: true, profile_id: null, version: null, body: null, detail: null, shadow_proxy: null, path: null, light: null, ...extra } as StageObject)
const DOC = { schema_version: 2, id: 'stg_1', name: 'Room', size: { w: 1920, h: 1080, fps: 24 },
  objects: [OBJ('set_1', 'set', 'Set 1', { preset: 'room' }), OBJ('prop_1', 'prop', 'Prop 1', { preset: 'crate', parent: 'set_1' }), OBJ('fig_1', 'mannequin', 'Figure 1'), OBJ('light_1', 'light', 'Light 1')],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1', ambient: null,
  keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' } as unknown as StageDoc
let put: unknown[] = []

beforeEach(() => {
  put = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(String(input), init)                     // openapi-fetch hands a Request
    if (req.url.includes('/project/stage-templates')) {
      if (req.method === 'PUT') { const body = JSON.parse(await req.text()); put.push(body); return new Response(JSON.stringify({ schema_version: 1, templates: body.templates }), { status: 200, headers: { 'content-type': 'application/json' } }) }
      return new Response(JSON.stringify({ schema_version: 1, templates: [] }), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    return new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })        // the stage's own saves
  }))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useStage.setState({ current: DOC, selected: null, selectedCamera: null, stageSelected: false, templates: [], undo: [], redo: [] })
})
afterEach(() => { vi.unstubAllGlobals(); useStage.setState({ current: null, templates: [] }) })

describe('stage templates (D119 SC2)', () => {
  it('saves the arrangement without the figures and keeps a parent inside it', async () => {
    await st().saveTemplate('Kitchen')
    expect(put).toHaveLength(1)
    const t = (put[0] as { templates: { name: string; objects: StageObject[] }[] }).templates[0]
    expect(t.name).toBe('Kitchen')
    expect(t.objects.map((o) => o.kind)).toEqual(['set', 'prop', 'light'])
    expect(t.objects.every((o) => TEMPLATE_KINDS.has(o.kind))).toBe(true)
    expect(t.objects[1].parent).toBe('set_1')                                                // the crate stays on its set
    expect(useStage.getState().templates.map((x) => x.name)).toEqual(['Kitchen'])
  })

  it('adds a template with new ids, the parent remapped, and selects the last object; deletes it', async () => {
    await st().saveTemplate('Kitchen')
    st().applyTemplate('Kitchen')
    const cur = useStage.getState().current!
    expect(cur.objects).toHaveLength(7)
    const added = cur.objects.slice(4)
    expect(added.map((o) => o.kind)).toEqual(['set', 'prop', 'light'])
    expect(new Set(added.map((o) => o.id)).size).toBe(3)
    expect(added.every((o) => !['set_1', 'prop_1', 'light_1'].includes(o.id))).toBe(true)
    expect(added[1].parent).toBe(added[0].id)                                                  // the parent inside the template follows the new id
    expect(useStage.getState().selected).toBe(added[2].id)
    await st().deleteTemplate('Kitchen')
    expect(useStage.getState().templates).toEqual([])
    expect((put[1] as { templates: unknown[] }).templates).toEqual([])
  })
})
