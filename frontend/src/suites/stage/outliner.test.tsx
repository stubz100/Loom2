// D119 (SC1): the scene outliner — the stage, its objects and its cameras as rows; the selected row's editor under it; a camera row
// selects the camera as an object and makes it the active one; the stage row opens the frame and the ambient.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc, StageObject } from '../../api/types'
import { OutlinerTab } from './StageParts'
import { st, useStage } from './stageStore'

const OBJ = (id: string, kind: StageObject['kind'], name: string, extra: Partial<StageObject> = {}): StageObject => ({
  id, kind, name, preset: kind === 'set' ? 'room' : kind === 'mannequin' ? 'adult' : null, asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, parent: null,
  locked: false, visible: true, colour_id: 1, pose: kind === 'mannequin' ? { preset: 'stand', joints: {} } : null, billboard: true, profile_id: null, version: null, body: null,
  detail: null, shadow_proxy: null, path: null, light: null, ...extra } as StageObject)
const DOC = { schema_version: 2, id: 'stg_1', name: 'Room', size: { w: 1920, h: 1080, fps: 24 }, objects: [OBJ('set_1', 'set', 'Set 1'), OBJ('fig_1', 'mannequin', 'Figure 1')],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }, { id: 'cam_2', name: 'Camera 2', pos: [2, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 50, sensor_mm: 36 }],
  active_camera: 'cam_1', ambient: null, keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' } as unknown as StageDoc
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const click = (el: Element) => act(() => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })) })

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('not stubbed', { status: 500 })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useStage.setState({ current: DOC, selected: null, selectedCamera: null, stageSelected: false, undo: [], redo: [] })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers(); vi.unstubAllGlobals()
  useStage.setState({ current: null, selected: null, selectedCamera: null, stageSelected: false })
})

describe('the scene outliner (D119 SC1)', () => {
  it('lists the stage, the objects and the cameras as rows, the active camera starred, nothing open', () => {
    const h = render(<OutlinerTab />)
    expect(h.querySelectorAll('.outl-row[data-row="stage"]')).toHaveLength(1)
    expect([...h.querySelectorAll('.outl-row[data-row="object"] .name')].map((n) => n.textContent)).toEqual(['Figure 1', 'Set 1'])   // grouped by kind: figures, then sets
    expect([...h.querySelectorAll('.lib-row[data-group]')].map((n) => n.getAttribute('data-group'))).toEqual(['figures', 'sets', 'props', 'standins', 'meshes', 'lights', 'planes', 'cameras', 'templates'])
    expect(h.querySelector('.lib-row[data-group="figures"] .lib-label')?.textContent).toContain('Figures · 1')
    expect([...h.querySelectorAll('.outl-row[data-row="camera"] .name')].map((n) => n.textContent)).toEqual(['Camera 1', 'Camera 2'])
    expect(h.querySelector('.outl-row[data-row="camera"].cam-active .name')?.textContent).toBe('Camera 1')
    expect(h.querySelectorAll('.row-editor')).toHaveLength(0)
    expect(h.querySelector('.head .hint')?.textContent).toBe('2 objects · 2 cameras')
  })

  it('a camera row selects the camera as an object, makes it active and opens its editor; a second click closes it', () => {
    const h = render(<OutlinerTab />)
    click(h.querySelectorAll('.outl-row[data-row="camera"]')[1])
    expect(useStage.getState().selectedCamera).toBe('cam_2')
    expect(useStage.getState().selected).toBeNull()
    expect(useStage.getState().current!.active_camera).toBe('cam_2')
    const ed = h.querySelector('.outl-row[data-row="camera"].active .row-editor')!
    expect(ed.querySelector('h4')?.textContent).toContain('Camera 2')
    expect(ed.querySelectorAll('.vec')).toHaveLength(2)                                      // position, target
    expect(ed.querySelector('.focals button.active')?.textContent).toBe('50')
    expect([...ed.querySelectorAll('.verbs button')].map((b) => b.textContent)).toContain('Look through')
    click(h.querySelectorAll('.outl-row[data-row="camera"]')[1])
    expect(useStage.getState().selectedCamera).toBeNull()
    expect(h.querySelectorAll('.row-editor')).toHaveLength(0)
  })

  it('an object row opens its editor with the transform and the kind\'s fields; selecting an object drops the camera selection', () => {
    const h = render(<OutlinerTab />)
    click(h.querySelectorAll('.outl-row[data-row="camera"]')[0])
    click(h.querySelectorAll('.outl-row[data-row="object"]')[0])                                   // the figure comes first now (its group)
    expect(useStage.getState().selected).toBe('fig_1')
    expect(useStage.getState().selectedCamera).toBeNull()
    const ed = h.querySelector('.outl-row[data-row="object"].active .row-editor')!
    expect(ed.querySelector('h4')?.textContent).toContain('Figure 1')
    expect(ed.querySelectorAll('.vec')).toHaveLength(3)                                      // position, rotation, scale
    expect(ed.querySelector('select')).not.toBeNull()                                         // the pose preset
    expect(h.querySelectorAll('.row-editor')).toHaveLength(1)
  })

  it('the stage row opens the frame, the contents and the ambient; the store says the stage is selected', () => {
    const h = render(<OutlinerTab />)
    click(h.querySelector('.outl-row[data-row="stage"]')!)
    expect(useStage.getState().stageSelected).toBe(true)
    const ed = h.querySelector('.outl-row[data-row="stage"] .row-editor')!
    expect(ed.textContent).toContain('1920×1080 @ 24 fps')
    expect(ed.textContent).toContain('2 objects · 2 cameras')
    expect(ed.querySelector('input[aria-label="ambient light"]')).not.toBeNull()
    st().select('set_1')
    expect(useStage.getState().stageSelected).toBe(false)
  })

  it('moveCamera moves the target along with the position', () => {
    st().moveCamera('cam_1', [1, 2.5, 6])
    const c = useStage.getState().current!.cameras[0]
    expect(c.pos).toEqual([1, 2.5, 6])
    expect(c.target).toEqual([1, 2, 1])
  })
})
