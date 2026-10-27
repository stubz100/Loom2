// The review of 2026-10-27, V68: the frame's Ctrl chords (Ctrl+B, Ctrl+I, Ctrl+,, Ctrl+1–4) answer outside fields only; the menu key and
// the palette answer everywhere (D72); a field or a modal keeps every other key.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const spies = vi.hoisted(() => ({ handleKeyFor: vi.fn(() => true), toggle: vi.fn(), setHelp: vi.fn() }))
vi.mock('./commands', () => ({
  command: (id: string) => (id === 'global.palette' ? { id, keys: 'Ctrl+K' } : id === 'global.contextMenu' ? { id, keys: 'Shift+F10' } : undefined),
  matchesCommand: (e: KeyboardEvent, c: { keys: string }) => (c.keys === 'Ctrl+K' ? e.ctrlKey && e.key === 'k' : e.shiftKey && e.key === 'F10'),
  handleKeyFor: spies.handleKeyFor,
}))
vi.mock('./CommandPalette', () => ({ usePalette: { getState: () => ({ open: false, toggle: spies.toggle }) } }))
vi.mock('./globalCommands', () => ({}))
vi.mock('../store/session', () => ({ useSession: { getState: () => ({ helpOpen: true, setHelp: spies.setHelp, settingsOpen: false, projectDialog: null }) } }))

import { onGlobalKeydown } from './useKeyboardMap'

const key = (init: KeyboardEventInit, target: Element) => {
  const e = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init })
  Object.defineProperty(e, 'target', { value: target })
  return e
}

describe('global keys in fields (V68)', () => {
  let input: HTMLInputElement, grid: HTMLDivElement
  beforeEach(() => {
    spies.handleKeyFor.mockClear(); spies.toggle.mockClear(); spies.setHelp.mockClear()
    document.body.innerHTML = '<input id="f"><div class="cat-grid" tabindex="0"></div>'
    input = document.querySelector('input')!
    grid = document.querySelector('.cat-grid')!
  })

  it('a Ctrl chord in a field is the field’s; outside it is the frame’s', () => {
    onGlobalKeydown(key({ key: 'b', ctrlKey: true }, input))
    onGlobalKeydown(key({ key: '1', ctrlKey: true }, input))
    expect(spies.handleKeyFor).not.toHaveBeenCalled()
    onGlobalKeydown(key({ key: 'b', ctrlKey: true }, grid))
    expect(spies.handleKeyFor).toHaveBeenCalledWith('global', expect.objectContaining({ key: 'b', ctrlKey: true }))
  })

  it('the palette answers in a field; Escape and plain keys do not', () => {
    onGlobalKeydown(key({ key: 'k', ctrlKey: true }, input))
    expect(spies.toggle).toHaveBeenCalledTimes(1)
    onGlobalKeydown(key({ key: 'Escape' }, input))
    onGlobalKeydown(key({ key: 'Tab' }, input))
    expect(spies.setHelp).not.toHaveBeenCalled()
    expect(spies.handleKeyFor).not.toHaveBeenCalled()
    onGlobalKeydown(key({ key: 'Escape' }, grid))
    expect(spies.setHelp).toHaveBeenCalledWith(false)
  })
})
