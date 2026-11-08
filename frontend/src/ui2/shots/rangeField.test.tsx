// Review K95: the shot's range fields — a blur without typing leaves a range that follows the stage alone (it pinned the stage's range on
// the shot); typed numbers are set on blur.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'

const scene = vi.hoisted(() => ({ setRange: vi.fn(async () => undefined) }))
vi.mock('./scene', async (orig) => ({ ...(await orig<typeof import('./scene')>()), setRange: scene.setRange }))
const { RangeField } = await import('./ShotHeader')

let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
afterEach(() => { if (root) act(() => root!.unmount()); host?.remove(); host = null; root = null; scene.setRange.mockClear() })
const render = (el: React.ReactElement) => { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host); act(() => root!.render(el)); return host }
const type = (el: HTMLInputElement, v: string) => act(() => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })) })
const blur = (el: HTMLElement) => act(() => { el.dispatchEvent(new FocusEvent('focusout', { bubbles: true })) })

describe("the shot's range (K95)", () => {
  it('a blur without typing pins nothing; a typed end is set', () => {
    const h = render(<RangeField start={0} end={47} fps={24} whole />)
    const [a, b] = [...h.querySelectorAll('input')] as HTMLInputElement[]
    blur(a); blur(b)
    expect(scene.setRange).not.toHaveBeenCalled()
    type(b, '60'); blur(b)
    expect(scene.setRange).toHaveBeenCalledWith({ start: 0, end: 60 })
  })
})
