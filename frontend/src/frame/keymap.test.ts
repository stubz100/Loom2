// D72 (ArtCraft P16): remappable keys — an override replaces a command's chords and every reader (dispatch, tooltips) follows; a remap
// that collides where both commands can fire is refused with the other command's name; fixed keys are refused; overrides persist under
// `loom2.keys` with a schema version (a bare map from before is migrated) and survive a reload (a fresh registry re-applies them).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Command } from './commands'

const cmd = (id: string, scope: Command['scope'], keys?: string, extra: Partial<Command> = {}): Command =>
  ({ id, scope, label: id.replace(/^\w+\./, ''), keys, placement: ['toolbar'], run: vi.fn(), ...extra })
const key = (k: string, mods: Partial<Pick<KeyboardEvent, 'ctrlKey' | 'shiftKey' | 'altKey' | 'metaKey'>> = {}) =>
  new KeyboardEvent('keydown', { key: k, ...mods })

/** A fresh registry and keymap (a reload): modules re-evaluated, storage kept. */
async function boot() {
  vi.resetModules()
  const commands = await import('./commands')
  const keymap = await import('./keymap')
  commands.registerCommands([
    cmd('cat.keep', 'catalogue', 'K'), cmd('cat.reject', 'catalogue', 'X'), cmd('cat.next', 'catalogue', 'ArrowRight'),
    cmd('edit.brush', 'edit', 'B'), cmd('global.help', 'global', '?'), cmd('global.find', 'global', 'Ctrl+F', { alt: ['F3'] }),
  ])
  return { commands, keymap }
}

beforeEach(() => { localStorage.clear() })

describe('remap', () => {
  it('Keep to G: the command answers to G, not K, and its tooltip says G', async () => {
    const { commands, keymap } = await boot()
    expect(keymap.remap('cat.keep', 'G')).toEqual({ ok: true })
    const keep = commands.command('cat.keep')!
    expect(keep.keys).toBe('G')
    expect(commands.titleFor(keep)).toBe('keep (G)')
    expect(commands.handleKeyFor('catalogue', key('k'))).toBe(false)
    expect(commands.handleKeyFor('catalogue', key('g'))).toBe(true)
    expect(keep.run).toHaveBeenCalledTimes(1)
    expect(commands.defaultKeysOf('cat.keep')).toEqual({ keys: 'K', alt: undefined })
  })
  it('refuses a key another command answers to where both can fire, naming it', async () => {
    const { commands, keymap } = await boot()
    const r = keymap.remap('cat.keep', 'X')
    expect(r).toMatchObject({ ok: false, reason: expect.stringContaining('“reject”') })
    expect(r.ok === false && r.conflict?.id).toBe('cat.reject')
    expect(commands.command('cat.keep')!.keys).toBe('K')
    expect(keymap.remap('cat.keep', '?')).toMatchObject({ ok: false, conflict: { id: 'global.help' } })      // global answers everywhere
    expect(keymap.remap('cat.keep', 'F3')).toMatchObject({ ok: false, conflict: { id: 'global.find' } })     // alternate chords count
    expect(keymap.remap('edit.brush', 'X')).toEqual({ ok: true })                                           // other suites do not collide
  })
  it('refuses fixed keys, both ways', async () => {
    const { commands, keymap } = await boot()
    expect(commands.command('cat.next')!.fixed).toBe(true)                                                   // ArrowRight: marked at registration
    expect(keymap.remap('cat.next', 'N')).toMatchObject({ ok: false, reason: expect.stringContaining('keeps its key') })
    for (const k of ['Escape', 'Space', 'Tab', 'ArrowUp']) expect(keymap.remap('cat.keep', k)).toMatchObject({ ok: false, reason: 'Arrows, Esc, Space and Tab are fixed keys' })
    expect(keymap.remap('cat.keep', 'Shift+Tab')).toEqual({ ok: true })                                      // with a modifier it is an ordinary chord
  })
  it('null leaves the command without a key; reset brings its own back; remapping to its own key drops the override', async () => {
    const { commands, keymap } = await boot()
    keymap.remap('global.find', null)
    expect(commands.command('global.find')).toMatchObject({ keys: undefined, alt: undefined })
    keymap.resetKey('global.find')
    expect(commands.command('global.find')).toMatchObject({ keys: 'Ctrl+F', alt: ['F3'] })
    keymap.remap('cat.keep', 'G'); keymap.remap('cat.keep', 'k')
    expect(keymap.useKeymap.getState().overrides).toEqual({})
  })
})

describe('persistence', () => {
  it('survives a reload, and applies to commands that register later (lazy suites)', async () => {
    let { keymap } = await boot()
    keymap.remap('cat.keep', 'G'); keymap.remap('global.find', null)
    expect(JSON.parse(localStorage.getItem('loom2.keys')!)).toEqual({ schema_version: 1, keys: { 'cat.keep': 'G', 'global.find': null } })
    const again = await boot(); keymap = again.keymap
    expect(again.commands.command('cat.keep')!.keys).toBe('G')
    again.commands.registerCommands([cmd('anim.play', 'animate', 'P')])
    keymap.remap('anim.play', 'O')
    const third = await boot()
    third.commands.registerCommands([cmd('anim.play', 'animate', 'P')])
    expect(third.commands.command('anim.play')!.keys).toBe('O')
  })
  it('migrates a bare map, drops junk, and resets everything', async () => {
    localStorage.setItem('loom2.keys', JSON.stringify({ 'cat.keep': 'J', 'cat.reject': 7, 'global.help': null }))
    const { commands, keymap } = await boot()
    expect(commands.command('cat.keep')!.keys).toBe('J')
    expect(commands.command('cat.reject')!.keys).toBe('X')
    expect(commands.command('global.help')!.keys).toBeUndefined()
    keymap.resetAllKeys()
    expect(localStorage.getItem('loom2.keys')).toBeNull()
    expect(commands.command('cat.keep')!.keys).toBe('K')
  })
  it('a broken store means no overrides', async () => {
    localStorage.setItem('loom2.keys', '{not json')
    const { commands } = await boot()
    expect(commands.command('cat.keep')!.keys).toBe('K')
  })
})

describe('chordFromEvent', () => {
  it('records letters, modifiers, named and punctuation keys; ignores lone modifiers', async () => {
    const { keymap } = await boot()
    expect(keymap.chordFromEvent(key('g'))).toBe('G')
    expect(keymap.chordFromEvent(key('K', { ctrlKey: true, shiftKey: true }))).toBe('Ctrl+Shift+K')
    expect(keymap.chordFromEvent(key('F2', { altKey: true }))).toBe('Alt+F2')
    expect(keymap.chordFromEvent(key('?', { shiftKey: true }))).toBe('?')
    expect(keymap.chordFromEvent(key(' '))).toBe('Space')
    expect(keymap.chordFromEvent(key('Shift', { shiftKey: true }))).toBeNull()
  })
})
