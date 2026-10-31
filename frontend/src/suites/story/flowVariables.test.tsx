// W23: the project's variables are a section of the Flow's left column (D157, proto01_UI2 04 §7); W2: the synopsis is the Project menu's
// Notes, edited in a multi-line dialog (Enter is a new line, Ctrl+Enter keeps it).
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import type { World } from '../../api/types'
import { AskDialog } from '../../frame/AskDialog'
import { askText } from '../../store/session'
import { FlowVariables } from './StoryParts'
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
})
