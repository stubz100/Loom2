// The walkthrough-2 register's client fixes: W6 a Tree prompt read as words, W9 a job's toast named by what it is, W49 a disabled command's reason.
import { describe, expect, it } from 'vitest'
import { registerCommands, whyTitle, type Command } from '../frame/commands'
import { jobLabel } from '../store/session'
import { readablePrompt } from './promptText'

describe('the walkthrough-2 register (client)', () => {
  it('W6: a Tree prompt reads as labelled lines; other text stays as it is', () => {
    const tree = JSON.stringify({ scene: 'a stone quay at dusk', subjects: [{ description: 'Ines, a courier', position: 'left', action: 'walking' }, { description: 'Tomas' }],
      lighting: 'low sun', camera: { angle: 'eye level', lens: '35mm' }, color_palette: ['#112233', 'teal'] })
    expect(readablePrompt(tree)).toBe('scene: a stone quay at dusk\nsubject 1: Ines, a courier; left; walking\nsubject 2: Tomas\nlighting: low sun\ncolours: #112233, teal\ncamera: eye level, 35mm')
    expect(readablePrompt('a cat on a mat')).toBe('a cat on a mat')
    expect(readablePrompt('{not json')).toBe('{not json')
    expect(readablePrompt('{"other": 1}')).toBe('{"other": 1}')
  })
  it('W9: a job is named by its surface in its toast, else by its id', () => {
    expect(jobLabel({ id: 'job_00000007', origin: { surface: 'body_fit' } })).toBe('The body fit')
    expect(jobLabel({ id: 'job_00000007', origin: null })).toBe('Job 00000007')
  })
  it('W49: a disabled command says why in its tooltip; an enabled one does not', () => {
    let on = false
    const c: Command = { id: 'test.w49', scope: 'global', label: 'Mark final', placement: ['panel'], when: () => on, why: () => 'no clip yet', run: () => {} }
    registerCommands([c])
    expect(whyTitle(c)).toBe('Mark final — no clip yet')
    on = true
    expect(whyTitle(c)).toBe('Mark final')
  })
})
