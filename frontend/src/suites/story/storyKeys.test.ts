// D90 (B2): a Story tab dispatches its own commands only, and never while a field (or a modal) has the key.
import { describe, expect, it } from 'vitest'
import { registerCommands } from '../../frame/commands'
import { ownedBy, storyKey, typing } from './storyKeys'

const ran: string[] = []
registerCommands([
  { id: 'story.world.tRemove', scope: 'story', label: 'remove', keys: 'Delete', placement: ['context'], run: () => ran.push('world') },
  { id: 'story.flow.tDeleteEdge', scope: 'story', label: 'delete edge', keys: 'Delete', placement: ['context'], run: () => ran.push('flow') },
  { id: 'story.episode.tUndo', scope: 'story', label: 'undo', keys: 'Ctrl+Z', placement: ['toolbar'], run: () => ran.push('episode') },
])
const key = (k: string, target: EventTarget = document.body, ctrl = false) => { const e = new KeyboardEvent('keydown', { key: k, ctrlKey: ctrl, cancelable: true }); Object.defineProperty(e, 'target', { value: target }); return e }

describe('Story keys (D90 B2)', () => {
  it('maps every tab to its own id prefix', () => {
    expect(ownedBy('world', { id: 'story.world.remove' })).toBe(true)
    expect([ownedBy('episode', { id: 'story.cut.tool.razor' }), ownedBy('flow', { id: 'story.cut.tool.razor' })]).toEqual([true, false])   // CE2: the cut's editor answers on the Episode
    expect(ownedBy('cast', { id: 'story.world.remove' })).toBe(false)
    expect(ownedBy('shots', { id: 'story.shot.finalize' })).toBe(true)
    expect(ownedBy('flow', { id: 'story.flow.play' })).toBe(true)
    expect(ownedBy('episode', { id: 'story.episode.undo' })).toBe(true)
    expect(ownedBy('world', { id: 'story.episode.undo' })).toBe(false)
  })
  it('runs the tab\'s command for a shared key and nothing on another tab', () => {
    ran.length = 0
    expect(storyKey('flow', key('Delete'))).toBe(true)
    expect(storyKey('world', key('Delete'))).toBe(true)
    expect(storyKey('cast', key('Delete'))).toBe(false)
    expect(storyKey('shots', key('Delete'))).toBe(false)
    expect(storyKey('world', key('z', document.body, true))).toBe(false)
    expect(storyKey('episode', key('z', document.body, true))).toBe(true)
    expect(ran).toEqual(['flow', 'world', 'episode'])
  })
  it('leaves keys typed into fields, selects, editable text and modals alone', () => {
    const host = document.createElement('div'); document.body.append(host)
    host.innerHTML = '<input><textarea></textarea><select></select><div contenteditable="true"><span></span></div><div class="modal"><button></button></div><button class="plain"></button>'
    for (const sel of ['input', 'textarea', 'select', '[contenteditable] span', '.modal button']) expect(typing(host.querySelector(sel))).toBe(true)
    expect(typing(host.querySelector('button.plain'))).toBe(false)
    ran.length = 0
    expect(storyKey('world', key('Delete', host.querySelector('input')!))).toBe(false)
    expect(ran).toEqual([])
    host.remove()
  })
})
