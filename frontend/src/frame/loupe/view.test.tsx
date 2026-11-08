// The review of 2026-11-06 — the loupe's viewer: K94 (a drag's updater read a ref the release had cleared; React's wheel listener is passive,
// so Ctrl+wheel zoomed the window too) and K116 (the loupe never refitted when its box changed size).
import { act, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fitXf, useZoomPan } from './view'

let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null; vi.unstubAllGlobals()
  delete (HTMLElement.prototype as { clientWidth?: number }).clientWidth; delete (HTMLElement.prototype as { clientHeight?: number }).clientHeight   // jsdom's own (Element's) again
})

type Api = ReturnType<typeof useZoomPan>
function mount(dims: { w: number; h: number }, size: { w: number; h: number }) {
  const got: { api: Api | null } = { api: null }
  function View() { const z = useZoomPan(dims); const { ref, handlers } = z; useEffect(() => { got.api = z }); return <div ref={ref} {...handlers} data-testid="view" /> }
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host)
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get() { return size.w } })
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, get() { return size.h } })
  act(() => root!.render(<View />))
  return got
}

describe('the loupe view (K94, K116)', () => {
  it('fits centred, upscaling', () => {
    expect(fitXf(200, 100, { w: 100, h: 100 })).toEqual({ s: 1, x: 50, y: 0 })
    expect(fitXf(400, 400, { w: 100, h: 50 })).toEqual({ s: 4, x: 0, y: 100 })
  })

  it('a move and a release in one batch pan without reading the cleared drag', () => {
    const got = mount({ w: 100, h: 100 }, { w: 100, h: 100 })
    const h = got.api!.handlers
    const ev = (x: number) => ({ clientX: x, clientY: 0, pointerId: 1, target: document.body }) as unknown as React.PointerEvent
    expect(() => act(() => { h.onPointerDown(ev(0)); h.onPointerMove(ev(30)); h.onPointerUp() })).not.toThrow()
    expect(got.api!.xf.x).toBe(30)
  })

  it('Ctrl+wheel over the view cancels the browser zoom', () => {
    mount({ w: 100, h: 100 }, { w: 100, h: 100 })
    const el = host!.querySelector('[data-testid="view"]')!
    const e = new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true })
    el.dispatchEvent(e)
    expect(e.defaultPrevented).toBe(true)
    const plain = new WheelEvent('wheel', { deltaY: -100, bubbles: true, cancelable: true })
    el.dispatchEvent(plain)
    expect(plain.defaultPrevented).toBe(false)
  })

  it('a resize refits while it shows the fit, not after a zoom', () => {
    const cbs: (() => void)[] = []
    vi.stubGlobal('ResizeObserver', class { constructor(cb: () => void) { cbs.push(cb) } observe() {} disconnect() {} })
    const size = { w: 100, h: 100 }
    const got = mount({ w: 100, h: 100 }, size)
    expect(got.api!.xf.s).toBe(1)
    size.w = 200; size.h = 200
    act(() => cbs.forEach((cb) => cb()))
    expect(got.api!.xf.s).toBe(2)
    act(() => got.api!.one())
    size.w = 400; size.h = 400
    act(() => cbs.forEach((cb) => cb()))
    expect(got.api!.xf.s).toBe(1)                                       // 1:1 chosen: kept
  })
})
