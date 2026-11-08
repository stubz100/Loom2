// The review of 2026-11-06, Clay's Inspector: K59 — the fields, Reset transform and Stand it here read the object (and the camera) as keyed at
// the playhead; K60 / K93 — a number is typed whole and committed on blur or Enter ("-90" became 90, a range end of 48 became 25); K93 — the
// Things sheet takes the focus, so a key under it is the sheet's.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc, StageObject } from '../../api/types'
import { runCommand } from '../../frame/commands'
import { keyframesOf } from './anim'
import { NumField } from './NumField'
import { SelectionInspector } from './StageParts'
import './stageCommands'
import { st, useStage } from './stageStore'
import { ThingsSheet } from './ThingsSheet'
import { useThings } from './thingsStore'

const T = (pos: number[], rot = [0, 0, 0]) => ({ pos, rot, scale: [1, 1, 1] })
const OBJ = (id: string, kind: StageObject['kind'], extra: Partial<StageObject> = {}): StageObject => ({ id, kind, name: id, preset: kind === 'mannequin' ? 'adult' : null, asset_id: null,
  transform: T([0, 0, 0]), parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1,
  pose: kind === 'mannequin' ? { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null } : null, billboard: false, profile_id: null, version: null, body: null,
  detail: null, shadow_proxy: null, path: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null, ...extra } as unknown as StageObject)
const CAM = { id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
/** A figure keyed from x 0 at frame 0 to x 4 at frame 40 (linear), turned 90° there; the camera keyed from z 5 to z 9. */
const DOC = () => ({ schema_version: 4, id: 'stg_1', name: 'Quay', purpose: 'stage', bound: null, size: { w: 1920, h: 1080, fps: 24 }, objects: [OBJ('fig', 'mannequin'), OBJ('crate', 'prop')],
  cameras: [CAM], active_camera: 'cam_1', ambient: null, tracks: {}, length: 0,
  keyframes: { camera: { cam_1: [{ frame: 0, ease: 'linear', pos: [0, 1.5, 5], target: [0, 1, 0], focal_mm: 35 }, { frame: 40, ease: 'linear', pos: [0, 1.5, 9], target: [0, 1, 0], focal_mm: 35 }] },
    objects: { fig: [{ frame: 0, ease: 'linear', transform: T([0, 0, 0]) }, { frame: 40, ease: 'linear', transform: T([4, 0, 2], [0, 90, 0]) }] } },
  range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' }) as unknown as StageDoc

let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
/** React listens to the native input event; the value goes through the prototype's setter so React sees the change. */
const type = (el: HTMLInputElement, v: string) => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(el, v)
  act(() => { el.dispatchEvent(new Event('input', { bubbles: true })) })
}
const blur = (el: HTMLInputElement) => act(() => { el.dispatchEvent(new FocusEvent('focusout', { bubbles: true })) })
const enter = (el: HTMLInputElement) => act(() => { el.focus(); el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
const field = (h: HTMLElement, label: string) => h.querySelector(`input[aria-label="${label}"]`) as HTMLInputElement
const figKeys = () => keyframesOf(st().current!).objects.fig

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useStage.setState({ current: DOC(), selected: null, selectedCamera: null, stageSelected: false, undo: [], redo: [], mode: 'build', frame: 20, menuAt: null })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers(); vi.unstubAllGlobals()
  useStage.setState({ current: null, selected: null, selectedCamera: null, frame: 0, menuAt: null })
  useThings.setState({ setId: null, size: null })
})

describe('K60 / K93: a number typed whole', () => {
  it('commits on blur, not per keystroke — "-90" stays -90', () => {
    const onCommit = vi.fn()
    const h = render(<NumField label="n" value={12} onCommit={onCommit} />)
    const el = field(h, 'n')
    expect(el.value).toBe('12')
    for (const t of ['', '-9', '-90']) type(el, t)                                            // the "-" alone reads as '' in a number field
    expect(onCommit).not.toHaveBeenCalled()
    blur(el)
    expect(onCommit).toHaveBeenCalledTimes(1)
    expect(onCommit).toHaveBeenCalledWith(-90)
  })
  it('Enter commits; a blank or unchanged text commits nothing', () => {
    const onCommit = vi.fn()
    const h = render(<NumField label="n" value={25} onCommit={onCommit} digits={0} />)
    const el = field(h, 'n')
    type(el, '4'); type(el, '48')
    enter(el)
    expect(onCommit).toHaveBeenCalledWith(48)                                                  // was 25: "4" clamped on the way, with a toast
    onCommit.mockClear()
    type(el, ''); blur(el)
    type(el, '25'); blur(el)
    expect(onCommit).not.toHaveBeenCalled()
  })
})

describe('K59: the Inspector reads the object at the playhead', () => {
  it('shows the keyed place and writes a typed y with the keyed x and z (no snap back to the start)', () => {
    useStage.setState({ selected: 'fig' })
    const h = render(<SelectionInspector />)
    expect(field(h, 'position x').value).toBe('2')                                             // frame 20 of 0 → 4 (was 0, the unkeyed base)
    expect(field(h, 'position z').value).toBe('1')
    expect(field(h, 'rotation y').value).toBe('45')
    type(field(h, 'position y'), '0.5')
    expect(figKeys()).toHaveLength(2)                                                          // nothing yet: typed, not committed
    blur(field(h, 'position y'))
    const k = figKeys().find((x) => x.frame === 20)!
    expect(k.transform).toEqual({ pos: [2, 0.5, 1], rot: [0, 45, 0], scale: [1, 1, 1] })
    expect(st().undo).toHaveLength(1)                                                          // one step, not one per keystroke
  })
  it('a rotation of -90 typed is -90', () => {
    useStage.setState({ selected: 'crate' })
    const h = render(<SelectionInspector />)
    const el = field(h, 'rotation y')
    for (const t of ['', '-9', '-90']) type(el, t)
    blur(el)
    expect(st().object('crate')!.transform.rot).toEqual([0, -90, 0])
    expect(st().undo).toHaveLength(1)
  })
  it('the camera\'s editor shows where the keyed camera is at the playhead', () => {
    useStage.setState({ selectedCamera: 'cam_1' })
    const h = render(<SelectionInspector />)
    expect(field(h, 'position z').value).toBe('7')                                             // frame 20 of z 5 → 9 (was 5)
    type(field(h, 'position y'), '2'); blur(field(h, 'position y'))
    const k = keyframesOf(st().current!).camera.cam_1.find((x) => x.frame === 20)!
    expect(k.pos).toEqual([0, 2, 7])
  })
  it('Reset transform and Stand it here start from the keyed place and turn', () => {
    useStage.setState({ selected: 'fig' })
    expect(runCommand('stage.object.reset')).toBe(true)
    expect(figKeys().find((x) => x.frame === 20)!.transform).toEqual({ pos: [2, 0, 1], rot: [0, 0, 0], scale: [1, 1, 1] })
    useStage.setState({ frame: 30, menuAt: [5, 0, -1] })
    expect(runCommand('stage.object.standHere')).toBe(true)
    expect(figKeys().find((x) => x.frame === 30)!.transform).toEqual({ pos: [5, 0, -1], rot: [0, 45, 0], scale: [1, 1, 1] })   // its turn at frame 30 kept (0 at the reset's key, 90 at 40)
  })
})

describe('K93: the Things sheet owns its keys', () => {
  it('takes the focus when it opens', () => {
    useStage.setState({ current: { ...DOC(), objects: [OBJ('set_1', 'set', { preset: 'image', plate_asset_id: 'ast_plate' } as never)] } as StageDoc })
    useThings.setState({ setId: 'set_1', size: { w: 1920, h: 1080 } })
    const h = render(<ThingsSheet />)
    const sheet = h.querySelector('.modal.things-sheet') as HTMLElement
    expect(sheet).not.toBeNull()
    expect(document.activeElement).toBe(sheet)                                               // a Ctrl+Z here is the sheet's, not the stage's undo
  })
})
