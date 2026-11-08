// The review of 2026-11-06 (K register), Shots / Animate / Final: the presets and the panel per project (K68, K95), Try the other model (K71),
// the frame grid and the spec's own presets (K85), the panel settled when its model leaves /capabilities (K85), the Performance card's Queue
// (K95), a clip landing selected, the Final level's properties and masks at the playhead and the layer's transform (K116), the timeline's
// trim sent once and a key's click keeping the layer (K116), the Windows view's boxes (K95, K116), the colour dial committed on release (K116).
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Capabilities } from '../../api/types'
import { command, isEnabled } from '../../frame/commands'
import { useSession } from '../../store/session'
import { DEFAULT_PANEL, frameMin, modelRules, otherRecipe, useAnimate } from './animateStore'
import './animateCommands'
import { chainXf, deltaToLayer, layerXf, parentChain, toLayerPx, useComposition, xfAttr } from './compositionStore'
import { ColorField } from './Effects'
import { FinalLanes } from './FinalViewer'
import { useAnimRoute } from './routeStore'
import { Timeline } from './Timeline'
import { useWindows } from './windowsStore'

const CAPS = {
  defaults: { i2v: 'wan' },
  models: {},
  i2v: {
    models: {
      wan: { order: 1, short: 'Wan', family: 'wan', fps: 16, frames: 81, frame_step: 4, size_mult: 16, size: [832, 480], presets: { draft: 'Draft', motion: 'Motion', quality: 'Quality' },
        geometry: { tiers: { draft: [832, 480] } }, recipes: { flf: true } },
      cam: { order: 2, short: 'Camera', family: 'wan', fps: 16, frames: 81, frame_step: 4, size_mult: 16, size: [832, 480], presets: { motion: 'Motion' },
        geometry: { tiers: { draft: [832, 480] } }, recipes: { camera: true } },
      h3: { order: 3, short: 'H3', family: 'h3', fps: 24, frames: 124, frame_step: 17, size_mult: 32, size: [864, 480], takes_negative: false, presets: { draft: 'Draft', fast: 'Fast' },
        geometry: { frame_base: 5, fps_fixed: true, tiers: { draft: [864, 480] } }, recipes: { flf: true } },
    },
    tiers: { draft: {}, hd: {} }, portrait: {}, square: {},
  },
} as unknown as Capabilities
const withoutH3 = { ...CAPS, i2v: { ...CAPS.i2v!, models: { wan: CAPS.i2v!.models.wan, cam: CAPS.i2v!.models.cam } } } as unknown as Capabilities

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const settle = () => new Promise<void>((r) => setTimeout(r, 0))
type Call = { method: string; path: string; query: URLSearchParams; body: unknown }
let calls: Call[] = []
let reply: (c: Call) => Response | Promise<Response> = () => json({ detail: 'nope' }, 404)
function stubFetch(): void {
  calls = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : null
    const url = new URL(req ? req.url : String(input))
    const text = req ? await req.clone().text() : typeof init?.body === 'string' ? init.body : ''
    const c: Call = { method: (req?.method ?? init?.method ?? 'GET').toUpperCase(), path: url.pathname, query: url.searchParams, body: text ? JSON.parse(text) : null }
    calls.push(c)
    return reply(c)
  }))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' } as never)
}

beforeEach(() => { stubFetch(); vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }) })
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); reply = () => json({ detail: 'nope' }, 404) })

describe('the panel (K85, K71, K95, K68)', () => {
  beforeEach(() => useSession.setState({ capabilities: CAPS, project: { open: true, path: 'F:/a' } as never }))

  it('K85: the smallest frame count on a grid, and no endless walk on a step of 0 or none', () => {
    expect(frameMin({ base: 1, step: 4 })).toBe(9)
    expect(frameMin({ base: 5, step: 17 })).toBe(22)
    expect(frameMin({ base: 1, step: 0 })).toBe(9)
    expect(frameMin({ base: 1, step: null })).toBe(9)
    expect(frameMin({ base: 12, step: 4 })).toBe(12)
  })
  it("K85: a spec's preset key the order does not name is kept, after the named ones", () => {
    expect(modelRules('h3').presets).toEqual(['draft', 'fast'])
    expect(modelRules('wan').presets).toEqual(['draft', 'motion', 'quality'])
  })
  it('K71: Try the other model sends a camera move only to the camera model, a preset it has, no negative where it takes none', () => {
    const fromCam = { kind: 'i2v', model_id: 'cam', preset: 'motion', camera: { move: 'pan_left', speed: 1 }, negative: 'blur', steps: 30, cfg: 5, shift: 8, beats: [], seeds: [3] }
    expect(otherRecipe(fromCam, 'wan')).toMatchObject({ model_id: 'wan', camera: null, preset: 'motion', negative: 'blur', steps: null, cfg: null, shift: null, fps: 16, frames: 81, seeds: [0] })
    expect(otherRecipe(fromCam, 'h3')).toMatchObject({ model_id: 'h3', camera: null, preset: 'draft', negative: null, fps: 24, frames: 124, width: 864, height: 480 })
    expect(otherRecipe({ ...fromCam, model_id: 'wan', camera: null }, 'cam')).toMatchObject({ camera: { move: 'static', speed: 1 } })   // the camera model always runs one
  })
  it('K85: the panel left on a model /capabilities no longer lists takes the default with its own values', () => {
    useAnimate.getState().setModel('h3')
    expect(useAnimate.getState().panel).toMatchObject({ model_id: 'h3', fps: 24, frames: 124 })
    useSession.setState({ capabilities: withoutH3 })                                     // the licence unticked: H3 leaves the list
    expect(useAnimate.getState().panel).toMatchObject({ model_id: 'wan', fps: 16, frames: 81, width: 832, height: 480, preset: 'draft' })
  })
  it("K95: another project's open drops the panel's start, end and beats; the same project keeps them", () => {
    useAnimate.setState({ panel: { ...useAnimate.getState().panel, start: 'ast_s', end: 'ast_e', beats: [{ frame: 9, asset_id: 'ast_b', strength: 0.5 }] } })
    useSession.setState({ project: { open: false } as never })
    useSession.setState({ project: { open: true, path: 'F:/a' } as never })
    expect(useAnimate.getState().panel.start).toBe('ast_s')
    useSession.setState({ project: { open: true, path: 'F:/b' } as never })
    expect(useAnimate.getState().panel).toMatchObject({ start: null, end: null, beats: [] })
    expect(useAnimate.getState().panelProject).toBe('F:/b')
  })
  it("K68: an empty project's list never takes the open project's presets", async () => {
    vi.useRealTimers()
    reply = (c) => (c.path === '/project/animate-presets' && c.method === 'GET' ? json({ presets: [], last: null }) : json({}))
    useAnimate.setState({ presets: [{ name: 'A1', panel: DEFAULT_PANEL, saved_at: 'x' }], lastPreset: 'A1' })
    useSession.setState({ project: { open: true, path: 'F:/b' } as never })             // project B opened: A's list goes at once
    expect(useAnimate.getState().presets).toEqual([])
    useAnimate.setState({ presets: [{ name: 'A1', panel: DEFAULT_PANEL, saved_at: 'x' }] })   // even were they still listed
    await useAnimate.getState().loadPresets()
    expect(calls.filter((c) => c.method === 'PUT')).toEqual([])
    expect(useAnimate.getState().presets).toEqual([])
  })
  it('K95: Queue (Ctrl+Shift+Enter) is the Image to video card’s only', () => {
    useAnimate.setState({ panel: { ...useAnimate.getState().panel, start: 'ast_s' } })
    useAnimRoute.getState().set('i2v')
    expect(isEnabled(command('anim.stage')!)).toBe(true)
    useAnimRoute.getState().set('clip')
    expect(isEnabled(command('anim.stage')!)).toBe(false)
    useAnimRoute.getState().set('final')
    expect(isEnabled(command('anim.stage')!)).toBe(false)
    useAnimRoute.getState().set('i2v')
  })
  it('K116: a clip landing as the current one is selected — its stills and pins read, the player at its first frame', async () => {
    vi.useRealTimers()
    const clip = { id: 'clp_1', asset_id: 'ast_c', start_asset_id: 'ast_s', end_asset_id: null, extracted_asset_ids: [], frames: 81, fps: 16, beats: [] }
    reply = (c) => (c.path === '/clips' ? json({ items: [clip] }) : c.path === '/assets' ? json({ items: [], total: 0 }) : json({ detail: 'no' }, 404))
    useAnimate.setState({ clips: [], current: null, frame: 7, assets: {} })
    await useAnimate.getState().loadClips()
    await settle()
    expect(useAnimate.getState()).toMatchObject({ current: 'clp_1', frame: 0 })
    expect(calls.some((c) => c.path === '/assets/ast_s')).toBe(true)                 // select() read its start still (it never ran)
  })
})

describe('K68: the presets this browser kept before D95 move once', () => {
  it('into the first project whose list is empty, never into the next', async () => {
    vi.useRealTimers()
    localStorage.setItem('loom2.animate', JSON.stringify({ state: { panel: DEFAULT_PANEL, presets: [{ name: 'Old', panel: DEFAULT_PANEL, saved_at: 'x' }], lastPreset: 'Old' }, version: 0 }))
    vi.resetModules()
    const client = await import('../../api/client')
    const session = await import('../../store/session')
    const store = await import('./animateStore')
    client.setBackend({ host: '127.0.0.1', port: 8766, token: 't' } as never)
    reply = (c) => (c.path === '/project/animate-presets' && c.method === 'GET' ? json({ presets: [], last: null }) : json({}))
    expect(store.useAnimate.getState().presets).toEqual([])                          // never listed as a project's
    session.useSession.setState({ project: { open: true, path: 'F:/a' } as never })
    await store.useAnimate.getState().loadPresets()
    const puts = calls.filter((c) => c.method === 'PUT')
    expect(puts.map((c) => (c.body as { presets: { name: string }[] }).presets.map((p) => p.name))).toEqual([['Old']])
    expect(store.useAnimate.getState().presets.map((p) => p.name)).toEqual(['Old'])
    session.useSession.setState({ project: { open: true, path: 'F:/b' } as never })
    await store.useAnimate.getState().loadPresets()
    expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(1)                   // once
    localStorage.clear()
  })
})

describe('the Final level (K116)', () => {
  const FINAL = { id: 'fin_1', name: 'Shot', rate: 10, frames: 20, size: { w: 800, h: 400 }, layers: [], revision: 1 }
  beforeEach(() => {
    vi.useRealTimers()
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() })
    useSession.setState({ jobs: {} } as never)
    useComposition.setState({ finalId: 'fin_1', final: FINAL as never, comp: { final_id: 'fin_1', revision: 0 } as never, frame: 0, playing: false, selected: 2, props: [], propsAt: null, keysOf: {}, masks: [], busy: false })
  })

  it("places the layer's pixels by its transform, and back", () => {
    const xf = layerXf([{ path: 'transform/position', value: [400, 200, 0] }, { path: 'transform/anchor', value: [50, 100, 0] }, { path: 'transform/scale', value: [200, 50, 100] }, { path: 'transform/rotation', value: 90 }])
    expect(xf).toEqual({ pos: [400, 200], anchor: [50, 100], scale: [2, 0.5], rot: 90 })
    expect(xfAttr(xf)).toBe('translate(400 200) rotate(90) scale(2 0.5) translate(-50 -100)')
    const fwd = ([x, y]: [number, number]) => { const sx = (x - 50) * 2, sy = (y - 100) * 0.5; return [400 - sy, 200 + sx] as [number, number] }   // rotate 90°: (x, y) → (−y, x)
    const back = toLayerPx(xf, fwd([60, 140]))
    expect(back[0]).toBeCloseTo(60); expect(back[1]).toBeCloseTo(140)
    const d = deltaToLayer(xf, [0, 10])                                                 // 10 px down on the frame: along the layer's x, halved by its scale 2
    expect(d[0]).toBeCloseTo(5); expect(d[1]).toBeCloseTo(0)
    expect(layerXf([])).toEqual({ pos: [0, 0], anchor: [0, 0], scale: [1, 1], rot: 0 })
  })
  it('reads the properties at the playhead, again when it rests elsewhere, and sets a keyed one at the playhead', async () => {
    reply = (c) => {
      if (c.path === '/finals/fin_1/composition/layers/2') return json({ properties: [{ path: 'transform/position', type: 'vec3', value: [1, 1, 0] }] })
      if (c.path === '/finals/fin_1/composition/layers/2/property') { const t = Number(c.query.get('t')); return json({ value: [100 * t, 5, 0], keys: [{ time: 0, value: [0, 5, 0] }, { time: 1, value: [100, 5, 0] }], uid: 7 }) }
      if (c.path === '/finals/fin_1/composition/property') return json({ result: {}, composition: {} })
      return json({ detail: 'no' }, 404)
    }
    useComposition.setState({ frame: 5 })
    await useComposition.getState().loadProps()
    expect(calls.find((c) => c.path.endsWith('/property'))?.query.get('t')).toBe('0.5')
    expect(useComposition.getState()).toMatchObject({ propsAt: 5, props: [{ path: 'transform/position', value: [50, 5, 0] }] })
    useComposition.setState({ frame: 8 })
    useComposition.getState().settle()                                                   // the playhead rests on frame 8
    await vi.waitFor(() => expect(useComposition.getState().propsAt).toBe(8))
    expect(useComposition.getState().props[0].value).toEqual([80, 5, 0])
    useComposition.setState({ comp: null })                                              // the edit's reload is not this case's
    await useComposition.getState().setProp('transform/position', [10, 10, 0])
    expect(calls.find((c) => c.path === '/finals/fin_1/composition/property')?.body).toMatchObject({ layer: 2, path: 'transform/position', time: 0.8 })
  })
  it("places a parented layer's masks under its parents' transforms (her matte under her)", async () => {
    expect(parentChain([{ id: 2, parent: 1 }, { id: 1, parent: 3 }, { id: 3, parent: 2 }], 2)).toEqual([1, 3])   // a loop ends the chain
    const own = layerXf([{ path: 'transform/position', value: [10, 0, 0] }, { path: 'transform/anchor', value: [0, 0, 0] }])
    const parent = layerXf([{ path: 'transform/position', value: [400, 200, 0] }, { path: 'transform/anchor', value: [100, 100, 0] }, { path: 'transform/scale', value: [200, 200, 100] }, { path: 'transform/rotation', value: 90 }])
    const xf = chainXf(own, [parent])
    // the layer's (5, 0) → the parent's (15, 0) → (15 − 100, 0 − 100) · 2 = (−170, −200) turned 90°: (200, −170) + (400, 200)
    const fwd = toLayerPx(xf, [600, 30])
    expect(fwd[0]).toBeCloseTo(5); expect(fwd[1]).toBeCloseTo(0)
    expect(xfAttr(xf)).toBe('matrix(0 2 -2 0 600 20)')
    const d = deltaToLayer(xf, [0, 10]); expect(d[0]).toBeCloseTo(5); expect(d[1]).toBeCloseTo(0)
    expect(chainXf(own, [])).toBe(own)
    reply = (c) => {
      if (c.path === '/finals/fin_1/composition/layers/2') return json({ properties: [{ path: 'transform/position', type: 'vec3', value: [10, 0, 0] }] })
      if (c.path === '/finals/fin_1/composition/layers/2/property') return json({ value: [10, 0, 0], keys: [] })
      if (c.path === '/finals/fin_1/composition/layers/1/property') return json({ value: ({ 'transform/position': [400, 200, 0], 'transform/anchor': [100, 100, 0], 'transform/scale': [200, 200, 100], 'transform/rotation': 90 } as Record<string, unknown>)[c.query.get('path')!] })
      return json({ detail: 'no' }, 404)
    }
    useComposition.setState({ layers: [{ id: 2, parent: 1 }, { id: 1, parent: null }] as never, frame: 3 })
    await useComposition.getState().loadProps()
    expect(calls.filter((c) => c.path === '/finals/fin_1/composition/layers/1/property').every((c) => c.query.get('t') === '0.3')).toBe(true)
    expect(useComposition.getState().parentXfs).toEqual([parent])
  })
})

// ---------------------------------------------------------------------------------------------- components
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const pointer = (el: Element, type: string, x: number, extra: MouseEventInit = {}) => act(() => { el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, button: 0, ...extra })) })
afterEach(() => { if (root) act(() => root!.unmount()); host?.remove(); host = null; root = null })

describe('the one timeline (K116)', () => {
  beforeEach(() => {
    Object.assign(Element.prototype, { setPointerCapture: () => undefined, releasePointerCapture: () => undefined })
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 100 })
  })
  afterEach(() => { delete (HTMLElement.prototype as { clientWidth?: number }).clientWidth })

  it('sends a trim once (its handle sits inside its bar)', () => {
    const drags: unknown[] = []
    const h = render(<Timeline span={[0, 100]} fps={10} frame={0} onSeek={() => undefined} rows={[{ id: 'r', label: 'r', bars: [{ id: 'b', from: 10, to: 50, drag: true }] }]}
      onBarDrag={(...a) => drags.push(a)} />)
    const handle = h.querySelector('.h-in')!
    pointer(handle, 'pointerdown', 10)
    pointer(handle, 'pointermove', 30)
    pointer(handle, 'pointerup', 30)
    expect(drags).toEqual([['r', 'b', 'in', 20]])
  })
  it("Final: a click on a key of the selected layer's lane keeps the layer; its name folds it", () => {
    useComposition.setState({ finalId: 'fin_1', final: { id: 'fin_1', rate: 10, frames: 20, size: { w: 8, h: 4 } } as never, comp: null, frame: 0, selected: 3, busy: false,
      layers: [{ id: 3, index: 1, name: 'Nora', blendMode: 'Normal', trackMatte: null, parent: null, in: 0, out: 2, start: 0, switches: {} }], keysOf: { 'transform/position': [{ time: 1, value: [0, 0] }] } } as never)
    const h = render(<FinalLanes rate={10} frames={20} />)
    const key = h.querySelector('.tl-key')!
    pointer(key, 'pointerdown', 50); pointer(key, 'pointerup', 50); pointer(key, 'click', 50)
    expect(useComposition.getState().selected).toBe(3)
    pointer(h.querySelector('.lane-name')!, 'click', 5)
    expect(useComposition.getState().selected).toBeNull()
  })
})

describe('the Windows view (K95, K116)', () => {
  const boxes = (cx: number) => ({ final_id: 'fin_1', frames: 3, w: 800, h: 400, window: [480, 848], layers: [{ id: 'lay_1', name: 'Nora', fit: 'band',
    window: { mode: 'auto', keys: [], offer: [{ frame: 0, cx, cy: 200, h: 300 }], frames: [[cx - 85, 50, 170, 300], [cx - 85, 50, 170, 300], [cx - 85, 50, 170, 300]], misses: [], changed: false },
    head: { mode: 'none', keys: [], offer: [], frames: [], misses: [], changed: false } }] })
  beforeEach(() => { vi.useRealTimers(); useWindows.setState({ fid: null, data: null, frame: 0, sel: null, pending: null, busy: false }) })

  it("drops a slow read of the previous final's boxes", async () => {
    let release: (r: Response) => void = () => undefined
    reply = (c) => (c.path === '/finals/fin_old/boxes' ? new Promise<Response>((r) => { release = r }) : json(boxes(300)))
    const old = useWindows.getState().load('fin_old')
    await useWindows.getState().load('fin_1')
    release(json({ ...boxes(999), final_id: 'fin_old' }))
    await old
    expect(useWindows.getState()).toMatchObject({ fid: 'fin_1', data: { final_id: 'fin_1' } })
  })
  it('holds a dropped box where it was let go until the answer lands', async () => {
    reply = () => json(boxes(300))
    await useWindows.getState().load('fin_1')
    let release: (r: Response) => void = () => undefined
    reply = () => new Promise<Response>((r) => { release = r })
    const placed = useWindows.getState().place({ lid: 'lay_1', kind: 'window' }, { cx: 500, cy: 200, size: 300 })
    expect(useWindows.getState().pending).toMatchObject({ lid: 'lay_1', kind: 'window', frame: 0, box: { cx: 500 } })
    await settle()
    release(json(boxes(500)))
    await placed
    expect(useWindows.getState().pending).toBeNull()
    expect(useWindows.getState().data?.layers[0].window.frames[0][0]).toBe(415)
  })
})

describe("Effects' colour dial (K116)", () => {
  it('commits when the picker lets go, once — not on every move', () => {
    const sent: string[] = []
    const h = render(<ColorField value="#000000" label="tint" onCommit={(v) => sent.push(v)} />)
    const input = h.querySelector('input')!
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
    for (const v of ['#110000', '#220000', '#330000']) act(() => { setValue.call(input, v); input.dispatchEvent(new Event('input', { bubbles: true })) })
    expect(sent).toEqual([])
    act(() => { input.dispatchEvent(new Event('change', { bubbles: true })) })
    act(() => { input.dispatchEvent(new FocusEvent('focusout', { bubbles: true })) })
    expect(sent).toEqual(['#330000'])
  })
})
