// D119 (SC2): the preset panel behind the + — closed by default with the chosen tiles beside the +, the + opens it with every tile, a
// tile picks and becomes the verbs' focus, Save the current asks a name in place, Esc and a click outside close it.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PresetPanel } from './PresetPanel'
import type { PresetIcon } from './PresetIcons'

const glyph = <svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" /></svg>
const ITEMS: PresetIcon[] = [{ id: 'a', label: 'soft light', icon: glyph }, { id: 'b', label: 'hard light', icon: glyph }, { id: 'c', label: 'rim light', icon: glyph }]
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
const click = (el: Element) => act(() => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })) })

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.useRealTimers()
})

describe('the preset panel (D119 SC2)', () => {
  it('shows only the + and the chosen tiles until opened; the + opens every tile and closes again', () => {
    const picks: string[] = []
    const h = render(<PresetPanel label="lighting presets" items={ITEMS} selected={['a']} chosen={[ITEMS[0]]} onPick={(id) => picks.push(id)} />)
    expect(h.querySelectorAll('[data-preset-panel]')).toHaveLength(0)
    expect(h.querySelectorAll('.preset-icon')).toHaveLength(1)                                   // the chosen one beside the +
    expect(h.querySelector('[data-preset-panel-btn]')?.getAttribute('aria-expanded')).toBe('false')
    click(h.querySelector('[data-preset-panel-btn]')!)
    const panel = h.querySelector('[data-preset-panel]')!
    expect(panel).not.toBeNull()
    expect(panel.querySelectorAll('.preset-icon')).toHaveLength(3)
    expect(panel.querySelector('.preset-icon.active')?.getAttribute('aria-label')).toBe('soft light')
    click(panel.querySelectorAll('.preset-icon')[1])
    expect(picks).toEqual(['b'])
    click(h.querySelector('[data-preset-panel-btn]')!)
    expect(h.querySelectorAll('[data-preset-panel]')).toHaveLength(0)
  })

  it('the verbs follow the tile last clicked; Save the current asks a name in place and hands it over; Esc closes', () => {
    const saved: string[] = []
    const h = render(<PresetPanel label="lighting presets" items={ITEMS} onPick={() => {}} onSave={(n) => { saved.push(n) }} verbs={(f) => <span data-verbs>{f ?? 'none'}</span>} />)
    click(h.querySelector('[data-preset-panel-btn]')!)
    expect(h.querySelector('[data-verbs]')?.textContent).toBe('none')
    click(h.querySelectorAll('[data-preset-panel] .preset-icon')[2])
    expect(h.querySelector('[data-verbs]')?.textContent).toBe('c')
    click(h.querySelector('.pp-save button')!)
    const input = h.querySelector<HTMLInputElement>('.pp-save input')!
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'evening')
    act(() => { input.dispatchEvent(new Event('input', { bubbles: true })) })
    act(() => { input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
    expect(saved).toEqual(['evening'])
    expect(h.querySelector('.pp-save input')).toBeNull()
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })
    expect(h.querySelectorAll('[data-preset-panel]')).toHaveLength(0)
  })

  it('a click outside closes it; the empty words show when there is nothing', () => {
    const h = render(<PresetPanel label="brushes" items={[]} onPick={() => {}} empty="No brushes saved yet." />)
    click(h.querySelector('[data-preset-panel-btn]')!)
    expect(h.querySelector('[data-preset-panel] .hint')?.textContent).toBe('No brushes saved yet.')
    act(() => { document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })) })
    expect(h.querySelectorAll('[data-preset-panel]')).toHaveLength(0)
  })
})
