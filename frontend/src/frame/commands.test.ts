// D68 (ArtCraft P6): the chord parser and matcher every key path goes through, the key labels, and the registry's dispatch rules.
import { describe, expect, it, vi } from 'vitest'
import { handleKeyFor, isEnabled, keyLabel, matchChord, parseChord, registerCommands, runCommand, titleFor, type Command } from './commands'

const key = (k: string, mods: { ctrl?: boolean; shift?: boolean; alt?: boolean; meta?: boolean } = {}) =>
  new KeyboardEvent('keydown', { key: k, ctrlKey: !!mods.ctrl, shiftKey: !!mods.shift, altKey: !!mods.alt, metaKey: !!mods.meta, cancelable: true })

describe('parseChord', () => {
  it('reads modifiers in any case and order, and lower-cases the key', () => {
    expect(parseChord('Ctrl+Shift+Z')).toEqual({ ctrl: true, shift: true, alt: false, key: 'z' })
    expect(parseChord('shift+alt+ctrl+K')).toEqual({ ctrl: true, shift: true, alt: true, key: 'k' })
    expect(parseChord('Cmd+S')).toEqual({ ctrl: true, shift: false, alt: false, key: 's' })
    expect(parseChord('Option+X').alt).toBe(true)
  })
  it('maps the spelled-out key names to KeyboardEvent.key values', () => {
    expect(parseChord('Esc').key).toBe('escape')
    expect(parseChord('Del').key).toBe('delete')
    expect(parseChord('Space').key).toBe(' ')
    expect(parseChord('Up').key).toBe('arrowup')
    expect(parseChord('Ctrl+Minus').key).toBe('-')
  })
  it("treats a trailing '+' as the plus key", () => {
    expect(parseChord('Ctrl++')).toEqual({ ctrl: true, shift: false, alt: false, key: '+' })
  })
})

describe('matchChord', () => {
  it('needs exactly the listed modifiers for letters and digits', () => {
    expect(matchChord(key('z', { ctrl: true }), 'Ctrl+Z')).toBe(true)
    expect(matchChord(key('Z', { ctrl: true, shift: true }), 'Ctrl+Z')).toBe(false)
    expect(matchChord(key('Z', { ctrl: true, shift: true }), 'Ctrl+Shift+Z')).toBe(true)
    expect(matchChord(key('z'), 'Ctrl+Z')).toBe(false)
    expect(matchChord(key('z', { ctrl: true }), 'Z')).toBe(false)
    expect(matchChord(key('z', { ctrl: true, alt: true }), 'Ctrl+Z')).toBe(false)
    expect(matchChord(key('1', { ctrl: true }), 'Ctrl+1')).toBe(true)
    expect(matchChord(key('2', { ctrl: true }), 'Ctrl+1')).toBe(false)
  })
  it('counts Meta as Ctrl (macOS keyboards)', () => {
    expect(matchChord(key('k', { meta: true }), 'Ctrl+K')).toBe(true)
  })
  it('lets Shift change punctuation unless the chord asks for it', () => {
    expect(matchChord(key('['), '[')).toBe(true)
    expect(matchChord(key('[', { shift: true }), '[')).toBe(true)
    expect(matchChord(key('['), 'Shift+[')).toBe(false)
    expect(matchChord(key('[', { shift: true }), 'Shift+[')).toBe(true)
    expect(matchChord(key('?', { shift: true }), '?')).toBe(true)
    expect(matchChord(key(']'), '[')).toBe(false)
  })
  it('matches named keys case-insensitively and with exact Shift', () => {
    expect(matchChord(key('Delete'), 'Delete')).toBe(true)
    expect(matchChord(key('Delete', { shift: true }), 'Delete')).toBe(false)
    expect(matchChord(key('Escape'), 'Esc')).toBe(true)
    expect(matchChord(key(' '), 'Space')).toBe(true)
    expect(matchChord(key('Enter', { ctrl: true, shift: true }), 'Ctrl+Shift+Enter')).toBe(true)
    expect(matchChord(key('Enter', { ctrl: true }), 'Ctrl+Shift+Enter')).toBe(false)
    expect(matchChord(key('ArrowLeft', { shift: true }), 'Shift+ArrowLeft')).toBe(true)
  })
})

describe('keyLabel / titleFor', () => {
  it('shortens key names for tooltips and menus', () => {
    expect(keyLabel(undefined)).toBe('')
    expect(keyLabel('Delete')).toBe('Del')
    expect(keyLabel('Escape')).toBe('Esc')
    expect(keyLabel('Shift+ArrowLeft')).toBe('Shift+←')
    expect(keyLabel('ArrowUp')).toBe('↑')
    expect(keyLabel('Ctrl+Shift+Z')).toBe('Ctrl+Shift+Z')
  })
  it('appends the shortcut to the label only when there is one', () => {
    const base = { id: 't.x', scope: 'models', label: 'Do it', placement: ['toolbar'], run: () => undefined } satisfies Command
    expect(titleFor(base)).toBe('Do it')
    expect(titleFor({ ...base, keys: 'Delete' })).toBe('Do it (Del)')
    expect(titleFor({ ...base, keys: 'Ctrl+D' }, 'Other')).toBe('Other (Ctrl+D)')
  })
})

describe('dispatch', () => {
  // the test registry uses the `models` scope, which registers nothing of its own
  const ran: string[] = []
  let polygonOpen = false, transformOpen = false
  registerCommands([
    { id: 't.close', scope: 'models', label: 'Close polygon', keys: 'Enter', placement: ['strip'], when: () => polygonOpen, run: () => ran.push('close') },
    { id: 't.apply', scope: 'models', label: 'Apply transform', keys: 'Enter', alt: ['Ctrl+Enter'], placement: ['strip'], when: () => transformOpen, run: () => ran.push('apply') },
    { id: 't.boom', scope: 'models', label: 'Throws in when', keys: 'B', placement: ['context'], when: () => { throw new Error('no doc') }, run: () => ran.push('boom') },
  ])

  it('runs the first enabled match and skips disabled ones (two commands may share a key with exclusive whens)', () => {
    ran.length = 0
    transformOpen = true; polygonOpen = false
    const e = key('Enter')
    expect(handleKeyFor('models', e)).toBe(true)
    expect(e.defaultPrevented).toBe(true)
    polygonOpen = true; transformOpen = false
    expect(handleKeyFor('models', key('Enter'))).toBe(true)
    expect(ran).toEqual(['apply', 'close'])
  })
  it('matches alternate chords and leaves unhandled keys alone', () => {
    ran.length = 0
    transformOpen = true; polygonOpen = false
    expect(handleKeyFor('models', key('Enter', { ctrl: true }))).toBe(true)
    transformOpen = false
    const e = key('Enter')
    expect(handleKeyFor('models', e)).toBe(false)
    expect(e.defaultPrevented).toBe(false)
    expect(handleKeyFor('global', key('Enter'))).toBe(false)
    expect(ran).toEqual(['apply'])
  })
  it('treats a throwing `when` as disabled', () => {
    ran.length = 0
    expect(isEnabled({ id: 'x', scope: 'models', label: 'x', placement: ['context'], when: () => { throw new Error('x') }, run: vi.fn() })).toBe(false)
    expect(handleKeyFor('models', key('b'))).toBe(false)
    expect(runCommand('t.boom')).toBe(false)
    expect(runCommand('t.missing')).toBe(false)
    transformOpen = true
    expect(runCommand('t.apply')).toBe(true)
    expect(ran).toEqual(['apply'])
  })
})
