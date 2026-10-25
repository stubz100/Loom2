// proto01_UIcast CW1–CW2 (06 §2.1–2.2): Image's For chip on an idea stamps `for_idea` on Image's own origin (a shot's For takes over, and
// the other way round); Prototype ▸ offers the three new ideas and the ideas made-for first; a variant's clay in words.
import { afterEach, describe, expect, it } from 'vitest'
import { originFor, useMakeFor } from '../../store/origin'
import { clayWords, focusOf, useIdeas, type Idea } from './ideasStore'
import { madeForIdea, prototypeItems } from './prototype'

const idea = (id: string, name: string, extra: Partial<Idea> = {}): Idea => ({ schema_version: 1, id, cls: 'character', name, note: '', focus: null, group_id: 'grp', variants: [], kept: [], made_for: [],
  revision: 1, created_at: '', updated_at: '', ...extra }) as Idea

describe('ideas (CW1–CW2)', () => {
  afterEach(() => { useMakeFor.setState({ generate: null, animate: null, idea: null }); useIdeas.setState({ ideas: [], loaded: false }) })
  it("stamps the idea on Image's own origin while its chip is on; a shot's chip and an idea's exclude each other", () => {
    const fb = { suite: 'generate' as const, surface: 'results', ref: null, payload: { saved_panel: 'x' } }
    expect(originFor('generate', fb)).toEqual(fb)
    useMakeFor.getState().setIdea({ idea_id: 'ida_1', name: 'Rain girl' })
    expect(originFor('generate', fb)).toEqual({ ...fb, payload: { saved_panel: 'x', for_idea: 'ida_1' } })
    expect(originFor('animate', { suite: 'animate', surface: 'clip', ref: null })).toEqual({ suite: 'animate', surface: 'clip', ref: null })   // Image's only
    useMakeFor.getState().set('generate', { kind: 'shot', shot_id: 'sht_1', version: 'v1', name: 'Shot 1' })
    expect(useMakeFor.getState().idea).toBeNull()
    expect(originFor('generate', fb).surface).toBe('for_shot')
    useMakeFor.getState().setIdea({ idea_id: 'ida_1', name: 'Rain girl' })
    expect(useMakeFor.getState().generate).toBeNull()
  })
  it('offers Prototype ▸: the three new ideas, then the idea the picture was made for first', () => {
    useIdeas.setState({ loaded: true, ideas: [idea('ida_a', 'Ash'), idea('ida_b', 'Birch'), idea('ida_c', 'Cedar')] })
    const items = prototypeItems(['ast_1'], madeForIdea({ origin: { suite: 'generate', surface: 'results', ref: null, payload: { for_idea: 'ida_b' } } }))
    expect(items.slice(0, 3).map((m) => ('label' in m ? m.label : ''))).toEqual(['New character idea', 'New prop idea', 'New place idea'])
    const add = items[3] as { label: string; items: ({ heading: string } | { label: string })[] }
    expect(add.label).toBe('Add to an idea')
    expect(add.items.map((m) => ('heading' in m ? `# ${m.heading}` : m.label))).toEqual(['# made for', 'Birch · character', '# the newest', 'Ash · character', 'Cedar · character'])
  })
  it("says a variant's clay in words and finds the variant in focus", () => {
    const v = (id: string, clay: unknown) => ({ id, asset_id: `ast_${id}`, made_from: { asset_id: null, prompt: '', model: null, seed: null, for_idea: null }, clay, note: '', created_at: '' })
    const i = idea('ida_1', 'x', { variants: [v('a', null), v('b', { step: 'done', shell_asset_id: 'ast_s' })] as never, focus: 'a' })
    expect(focusOf(i)?.id).toBe('a')
    expect(focusOf({ ...i, focus: null })?.id).toBe('b')
    expect(clayWords(i.variants[0])).toBe('no clay yet')
    expect(clayWords(i.variants[1])).toBe('figure and shell')
    expect(clayWords(v('c', { step: 'failed', error: 'cancelled' }) as never)).toBe('stopped: cancelled')
  })
})
