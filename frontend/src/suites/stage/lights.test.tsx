// D110 (PS4): the scene's lights — Add light puts a sun above and in front of a point, aimed at it, with its own settings; the Inspector's
// looks, strength, colour, softness, shadows and aim (a point, or an object); a light without settings shines as E23c's key; the ambient.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { StageDoc, StageObject } from '../../api/types'
import { AmbientControl, LightControls } from './LightControls'
import { NEW_LIGHT, st, useStage } from './stageStore'

const DOC = { schema_version: 2, id: 'stg_1', name: 'Room', size: { w: 1920, h: 1080, fps: 24 }, objects: [] as StageObject[],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1', ambient: null,
  keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' } as unknown as StageDoc
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const obj = (id: string) => useStage.getState().current!.objects.find((o) => o.id === id)!
/** React listens to the native input event; set the value through the prototype's setter so React sees the change. */
const type = (el: HTMLInputElement | HTMLSelectElement, v: string) => {
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, v)
  act(() => { el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true })) })
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('not stubbed', { status: 500 })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useStage.setState({ current: DOC, selected: null, undo: [], redo: [] })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers(); vi.unstubAllGlobals()
  useStage.setState({ current: null, selected: null })
})

describe('D110 (PS4) the lights of the scene', () => {
  it('Add light puts a sun above and in front of the point, aimed at it, with settings of its own', () => {
    const id = st().addLight([1, 0, -2])!
    expect(obj(id)).toMatchObject({ kind: 'light', transform: { pos: [-1.5, 3, 0] }, light: { ...NEW_LIGHT, target: [1, 1, -2] } })
  })
  it('the Inspector sets a look, the strength, colour, softness and shadows, and aims at an object', () => {
    const fig = st().addObject('mannequin', 'adult', [2, 0, 1])!
    const id = st().addLight()!
    const el = render(<LightControls o={obj(id)} />)
    act(() => ([...el.querySelectorAll('.looks button')].find((b) => b.textContent === 'Window') as HTMLButtonElement).click())
    expect(obj(id).light).toMatchObject({ intensity: 2.0, colour: '#fff1dc', softness: 0.7 })
    render(<LightControls o={obj(id)} />)
    type(el.querySelector('input[aria-label="light intensity"]') as HTMLInputElement, '4.5')
    expect(obj(id).light!.intensity).toBe(4.5)
    render(<LightControls o={obj(id)} />)
    act(() => (el.querySelector('input[aria-label="casts shadows"]') as HTMLInputElement).click())
    expect(obj(id).light!.shadows).toBe(false)
    render(<LightControls o={obj(id)} />)
    type(el.querySelector('select[aria-label="aim the light at an object"]') as HTMLSelectElement, fig)
    expect(obj(id).light!.target).toEqual([2, 1.2, 1])                                                       // a figure's chest
  })
  it('a light without settings shines as the first key light; the first edit gives it settings of its own', () => {
    const id = st().addLight()!
    st().updateObject(id, { light: null })
    const el = render(<LightControls o={obj(id)} />)
    expect(el.textContent).toContain('As the key light')                                              // D116: the why sits behind the ?
    expect(el.querySelector('[data-help]')?.getAttribute('title')).toContain('as the first key light did')
    expect((el.querySelector('input[aria-label="light intensity"]') as HTMLInputElement).value).toBe('2.3')
    type(el.querySelector('input[aria-label="shadow softness"]') as HTMLInputElement, '0.4')
    expect(obj(id).light).toMatchObject({ intensity: 2.3, softness: 0.4, shadows: true, target: [0, 1, 0] })
  })
  it('the ambient level defaults by the lights on the stage and can be set and reset', () => {
    const el = render(<AmbientControl />)
    expect((el.querySelector('input[aria-label="ambient light"]') as HTMLInputElement).value).toBe('1.1')    // no light
    act(() => { st().addLight() })
    render(<AmbientControl />)
    expect((el.querySelector('input[aria-label="ambient light"]') as HTMLInputElement).value).toBe('0.85')
    type(el.querySelector('input[aria-label="ambient light"]') as HTMLInputElement, '0.5')
    expect(useStage.getState().current!.ambient).toBe(0.5)
    render(<AmbientControl />)
    act(() => (el.querySelector('button') as HTMLButtonElement).click())
    expect(useStage.getState().current!.ambient).toBeNull()
  })
})
