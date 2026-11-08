// W23: the project's variables are a section of the Flow's left column (D157, proto01_UI2 04 §7); W2: the synopsis is the Project menu's
// Notes, edited in a multi-line dialog (Enter is a new line, Ctrl+Enter keeps it).
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import type { World } from '../../api/types'
import { AskDialog } from '../../frame/AskDialog'
import { askText } from '../../store/session'
import { FlowVariables } from './StoryParts'
import './storyCommands'
import { useStory } from './storyStore'

let root: Root | null = null
let host: HTMLDivElement | null = null
const mount = (el: React.ReactElement) => { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host); act(() => root!.render(el)) }
afterEach(() => { act(() => root?.unmount()); host?.remove(); root = null; host = null })

describe('the walkthrough-2 register: the Flow and the project', () => {
  it('W23: the variables, each editable, and Add variable, in the Flow\'s column', () => {
    useStory.setState({ world: { logline: '', synopsis: '', styles: [], default_style: null, spine: [], sample_scene: '',
      variables: [{ name: 'has_letter', type: 'bool', values: [], default: false }, { name: 'mood', type: 'enum', values: ['calm', 'storm'], default: 'calm' }] } as unknown as World })
    mount(<FlowVariables />)
    const rows = host!.querySelectorAll('[data-testid="flow-variables"] .var-row')
    expect(rows.length).toBe(2)
    expect((rows[1].querySelector('input[aria-label="enum values"]') as HTMLInputElement).value).toBe('calm, storm')
    expect(host!.querySelector('[data-testid="flow-variables"] .adder button')?.textContent).toContain('Add variable')
  })
  it('W2: a multi-line ask keeps its line breaks; Enter is a new line, not OK', async () => {
    mount(<AskDialog />)
    let answer: string | null | undefined
    act(() => { void askText({ title: 'Notes · the synopsis', initial: 'One.\nTwo.', multiline: true, allowEmpty: true }).then((v) => { answer = v }) })
    const ta = host!.querySelector('textarea') as HTMLTextAreaElement
    expect(ta.value).toBe('One.\nTwo.')
    act(() => { ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
    expect(answer).toBeUndefined()                                                              // still open
    await act(async () => { ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true })) })
    expect(answer).toBe('One.\nTwo.')
  })

  it("K79, K80: a name and an enum's values are typed whole and kept on blur; a name taken is refused; K81: the Shot templates listed with their verbs", () => {
    const vars = [{ name: 'has_letter', type: 'bool', values: [], default: false }, { name: 'mood', type: 'enum', values: ['calm'], default: 'calm' }]
    useStory.setState({ world: { logline: '', synopsis: '', styles: [], default_style: null, spine: [], sample_scene: '', revision: 1, variables: vars } as unknown as World,
      shotTemplates: [{ id: 'tpl_1', name: 'Two-shot', node_type: 'shot', lines: [], route: null, camera: null }] as never })
    mount(<FlowVariables />)
    const type = (el: HTMLInputElement, v: string) => act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(el, v)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    })
    const blur = (el: HTMLInputElement) => act(() => { el.dispatchEvent(new FocusEvent('focusout', { bubbles: true })) })
    const name = () => host!.querySelectorAll<HTMLInputElement>('input[aria-label="variable name"]')[0]
    type(name(), 'has_lett')
    expect(useStory.getState().world!.variables[0].name).toBe('has_letter')                   // not renamed per keystroke
    expect(name().value).toBe('has_lett')
    type(name(), 'has_key'); blur(name())
    expect(useStory.getState().world!.variables.map((v) => v.name)).toEqual(['has_key', 'mood'])
    type(name(), 'mood'); blur(name())
    expect(useStory.getState().world!.variables.map((v) => v.name)).toEqual(['has_key', 'mood'])   // two of one name refused
    const values = host!.querySelector<HTMLInputElement>('input[aria-label="enum values"]')!
    type(values, 'calm, ')
    expect(values.value).toBe('calm, ')                                                        // the comma stays while typing
    type(values, 'calm, storm'); blur(values)
    expect(useStory.getState().world!.variables[1].values).toEqual(['calm', 'storm'])
    const row = host!.querySelector('[data-testid="flow-templates"] [data-template="tpl_1"]')!
    expect(row.textContent).toContain('Two-shot')
    expect([...row.querySelectorAll('button')].map((b) => b.getAttribute('aria-label'))).toEqual(['New Shot from Two-shot', 'Rename Two-shot', 'Delete Two-shot'])
  })
})
