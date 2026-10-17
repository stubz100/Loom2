// D92: the World library → Generate's tiles (an entry's own drawing, its picture or its field's glyph — busy while being made, never
// letters), a field's entries in order, a move within a field; and a subject card ↔ a Cast profile (the description defaults to the
// version's stub, the profile mention is recorded with the card's index, unlinking drops it, the link survives a stored recipe).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement, type ReactNode } from 'react'
import type { Capabilities, LibraryEntry, Profile } from '../../api/types'
import { fieldGlyph, glyphFor } from '../../frame/presetGlyphs'
import { useSession } from '../../store/session'
import { cleanTree, DEFAULT_PANEL, mentionsInUse, panelFromRecipe, recipeFromPanel, useGenerate } from '../generate/generateStore'
import { entriesOf, entryTile, moveWithinField } from './libraryStore'
import { useStory } from './storyStore'

const html = (n: ReactNode) => renderToStaticMarkup(createElement('div', null, n))
const E = (id: string, field: string, text: string, name = text): LibraryEntry => ({ id, field, name, text, source: 'user', group_id: null })
const LIB = { entries: [E('l1', 'lighting', 'moonlight'), E('m1', 'mood', 'eerie'), E('l2', 'lighting', 'violet dusk', 'dusk'), E('c1', 'camera.distance', 'close-up'), E('n1', 'negative', 'blurry, low detail', 'blur'), E('n2', 'negative', 'cartoonish'), E('l3', 'lighting', 'firelight')] }

describe('D92 the library as tiles', () => {
  const url = (f: string, v: string) => (f === 'lighting' && v === 'moonlight' ? '/preset-icons/k1/file' : null)
  const busy = (f: string, v: string) => f === 'lighting' && v === 'violet dusk'
  it('a field\'s entries in the library\'s order', () => {
    expect(entriesOf(LIB, 'lighting').map((e) => e.id)).toEqual(['l1', 'l2', 'l3'])
    expect(entriesOf(null, 'lighting')).toEqual([])
  })
  it('a look shows its picture, else its field\'s glyph (busy while the picture is made); geometry and built-in negatives their drawings', () => {
    const [moon, dusk, fire] = entriesOf(LIB, 'lighting').map((e) => entryTile(e, url, busy))
    expect(moon).toMatchObject({ id: 'l1', label: 'moonlight', text: 'moonlight', img: '/preset-icons/k1/file', busy: false, hint: undefined })
    expect(dusk).toMatchObject({ label: 'dusk', text: 'violet dusk', img: null, busy: true, hint: 'violet dusk' })   // the name labels it, the words are the hint
    expect(fire).toMatchObject({ img: null, busy: false })
    expect(html(dusk.icon)).toBe(html(fieldGlyph('lighting')))
    const close = entryTile(LIB.entries[3], () => '/never', () => true)
    expect(close.img).toBeNull()
    expect(close.busy).toBe(false)                                                    // geometry: a drawing, never a picture
    expect(html(close.icon)).toBe(html(glyphFor('camera.distance', 'close-up')))
    const [blur, own] = entriesOf(LIB, 'negative').map((e) => entryTile(e, () => '/never', () => true))
    expect(html(blur.icon)).toBe(html(glyphFor('negative', 'blurry, low detail')))
    expect(html(own.icon)).toBe(html(fieldGlyph('negative')))                         // a new negative: the generic mark, no picture
    expect(own.img).toBeNull()
    for (const t of LIB.entries.map((e) => entryTile(e, url, busy))) expect(html(t.icon), t.id).toMatch(/^<div><svg/)   // never letters
  })
  it('moves an entry within its field only, swapping places in the whole list', () => {
    expect(moveWithinField(LIB.entries, 'l2', 1)).toEqual(['l1', 'm1', 'l3', 'c1', 'n1', 'n2', 'l2'])
    expect(moveWithinField(LIB.entries, 'l2', -1)).toEqual(['l2', 'm1', 'l1', 'c1', 'n1', 'n2', 'l3'])
    expect(moveWithinField(LIB.entries, 'l1', -1)).toBeNull()
    expect(moveWithinField(LIB.entries, 'gone', 1)).toBeNull()
  })
})

const CAPS = { defaults: { t2i: 'fixture-model' }, models: { 'fixture-model': { order: 1, short: 'M', turbo: false, recipes: {} } } } as unknown as Capabilities
const prof = (id: string, name: string, stub: string, cls = 'character'): Profile =>
  ({ id, name, cls, current: 'v2', versions: [{ id: 'v1', group_id: `${id}_g1`, stub: 'old', hero_asset_id: null }, { id: 'v2', group_id: `${id}_g2`, stub, hero_asset_id: 'ast_h' }] }) as unknown as Profile
const MARA = prof('prf_m', 'Mara', 'Mara, a wiry courier in a grey coat')
const BOX = prof('prf_b', 'Compass', 'a brass compass with a cracked glass', 'prop')

describe('D92 a subject card is a Cast profile', () => {
  beforeEach(() => {
    vi.useFakeTimers()                                                                 // the panel's preview request never leaves
    useSession.setState({ capabilities: CAPS })
    useStory.setState({ profiles: [MARA, BOX], profilesLoaded: true })
    useGenerate.setState({ panel: { ...DEFAULT_PANEL, model_id: 'fixture-model', prompt_mode: 'tree', tree: { ...DEFAULT_PANEL.tree, subjects: [] }, mentions: [] } })
  })
  afterEach(() => { vi.useRealTimers(); useSession.setState({ capabilities: null }); useStory.setState({ profiles: [], profilesLoaded: false }) })
  const g = () => useGenerate.getState()

  it('linking fills the description with the current version\'s stub and records the profile mention with the card', () => {
    g().addSubject()
    g().linkSubject(0, MARA)
    const p = g().panel
    expect(p.tree.subjects![0]).toMatchObject({ profile_id: 'prf_m', description: 'Mara, a wiry courier in a grey coat' })
    expect(p.mentions).toEqual([{ group_id: 'prf_m_g2', name: 'Mara', profile_id: 'prf_m' }])
    expect(mentionsInUse(p)).toHaveLength(1)                                           // in use without an @name in the text
    const r = recipeFromPanel(p)
    expect(r.mentions).toEqual([{ group_id: 'prf_m_g2', name: 'Mara', profile_id: 'prf_m', subject: 0 }])
    expect(r.prompt_json).toEqual({ subjects: [{ description: 'Mara, a wiry courier in a grey coat', color_match: 'exact' }] })   // the link is not prompt text
    expect(cleanTree(p.tree)).toEqual(r.prompt_json)
  })
  it('a typed description stays; re-linking replaces the last stub and the last mention', () => {
    g().addSubject()
    g().setSubject(0, { description: 'a tired traveller' })
    g().linkSubject(0, MARA)
    expect(g().panel.tree.subjects![0].description).toBe('a tired traveller')
    g().setSubject(0, { description: 'Mara, a wiry courier in a grey coat' })
    g().linkSubject(0, BOX)
    expect(g().panel.tree.subjects![0]).toMatchObject({ profile_id: 'prf_b', description: 'a brass compass with a cracked glass' })
    expect(g().panel.mentions).toEqual([{ group_id: 'prf_b_g2', name: 'Compass', profile_id: 'prf_b' }])
  })
  it('unlinking (or the mention chip\'s ×) ends the link and the mention; the words stay', () => {
    g().useAsSubject(MARA)
    expect(g().panel.tree.subjects).toHaveLength(1)
    g().useAsSubject(MARA)
    expect(g().panel.tree.subjects).toHaveLength(1)                                    // already a subject: not twice
    g().unlinkSubject(0)
    expect(g().panel.tree.subjects![0].profile_id).toBeUndefined()
    expect(g().panel.tree.subjects![0].description).toBe('Mara, a wiry courier in a grey coat')
    expect(g().panel.mentions).toEqual([])
    expect(recipeFromPanel(g().panel).mentions).toEqual([])
    g().linkSubject(0, MARA)
    g().removeMention('prf_m_g2')
    expect(g().panel.tree.subjects![0].profile_id).toBeUndefined()
  })
  it('Cast\'s "Use as a subject" turns a Text prompt into the Tree with the card, and a stored recipe brings the link back', () => {
    useGenerate.setState({ panel: { ...g().panel, prompt_mode: 'text', text: 'at the gate' } })
    g().useAsSubject(BOX)
    expect(g().panel.prompt_mode).toBe('tree')
    expect(g().panel.tree.subjects![0].profile_id).toBe('prf_b')
    const back = panelFromRecipe({ ...recipeFromPanel(g().panel), mentions: [{ group_id: 'prf_b_g2', name: 'Compass', profile_id: 'prf_b', subject: 0, revision: 3 }] })
    expect(back.tree!.subjects![0].profile_id).toBe('prf_b')
    expect(back.mentions).toEqual([{ group_id: 'prf_b_g2', name: 'Compass', profile_id: 'prf_b' }])
  })
})
