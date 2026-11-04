// D186: the one model card — the cards render from the capabilities' models, the active one is marked, a click picks, an unwired one
// is off; the Make column's filter and the default-first order the other surfaces use.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Capabilities } from '../api/types'
import { ModelCards } from './ModelCards'
import { defaultFirstItems, imageModelItems } from './modelCardItems'

const CAPS = { models: {
  dev: { order: 0, label: 'FLUX.2 dev · JSON', family: 'flux2', hint: 'slow, best adherence', license: 'flux-nc', health: 'present', wired: true, distilled: false, recipes: { t2i: true, inpaint: ['fill', 'outpaint'] } },
  klein: { order: 1, label: 'Klein 9B', family: 'klein', hint: null, license: 'flux-nc', health: 'missing', wired: true, distilled: true, recipes: { t2i: true, inpaint: ['fill', 'remove'] } },
  sd35: { order: 24, label: 'SD 3.5 Large', family: 'sd3', hint: null, license: 'sai', health: 'present', wired: false, distilled: false, recipes: { t2i: false, i2i: true } },
} } as unknown as Capabilities

let host: HTMLDivElement | null = null
afterEach(() => { host?.remove(); host = null })

describe('D186: ModelCards', () => {
  it('renders a card per item with its health dot and tooltip, marks the pick, and picks on click; an off card is disabled', () => {
    const onPick = vi.fn()
    host = document.createElement('div'); document.body.appendChild(host)
    const root = createRoot(host)
    act(() => root.render(<ModelCards items={[...imageModelItems(CAPS, (c) => !!c.recipes.t2i), { id: 'sd35', label: 'SD 3.5 Large', off: true, offWhy: 'not in this build' }]} value="klein" onPick={onPick} time />))
    const cards = [...host.querySelectorAll<HTMLButtonElement>('.model-card')]
    expect(cards.map((c) => c.dataset.model)).toEqual(['dev', 'klein', 'sd35'])                         // the server's order
    expect(cards.map((c) => c.classList.contains('active'))).toEqual([false, true, false])
    expect(cards[0].title).toBe('slow, best adherence · flux-nc · present')                              // hint · licence · health
    expect(cards[1].querySelector('.dot')!.classList.contains('warn')).toBe(true)                       // weights missing
    expect(cards[1].title).toContain('distilled')
    expect(cards[2].disabled && cards[2].classList.contains('off') && cards[2].title).toBe('not in this build')
    act(() => cards[0].click())
    expect(onPick).toHaveBeenCalledWith('dev')
    act(() => cards[2].click())
    expect(onPick).toHaveBeenCalledTimes(1)                                                              // an off card picks nothing
    act(() => root.unmount())
  })
  it('says so when there is nothing to pick', () => {
    host = document.createElement('div'); document.body.appendChild(host)
    const root = createRoot(host)
    act(() => root.render(<ModelCards items={[]} value={null} onPick={() => {}} />))
    expect(host.textContent).toContain('No model for this in this build')
    act(() => root.unmount())
  })
  it('imageModelItems filters the capabilities in order; defaultFirstItems leads with the default', () => {
    const items = imageModelItems(CAPS, (c) => Array.isArray(c.recipes.inpaint) && c.recipes.inpaint.includes('fill'))
    expect(items.map((m) => [m.id, m.off])).toEqual([['dev', false], ['klein', false]])
    expect(defaultFirstItems(items, 'klein').map((m) => m.id)).toEqual(['klein', 'dev'])
    expect(defaultFirstItems(items, 'nope').map((m) => m.id)).toEqual(['dev', 'klein'])
    expect(imageModelItems(CAPS, (c) => !!c.recipes.i2i).map((m) => [m.id, m.off, m.offWhy])).toEqual([['sd35', true, 'not available in this build']])
  })
})
