// D90 (02 §6.3): every built-in preset whose meaning is geometry has a drawn glyph. D92: no lettered tiles — every library field (and the
// other kinds: a saved panel, a style, a Cast profile, a free subject) has a glyph of its own, the built-in negatives are drawn, and the
// vocabulary checked is the server's seed itself (orchestrator/loom2/library_seed.json, the one source).
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement, type ReactNode } from 'react'
import seed from '../../../orchestrator/loom2/library_seed.json'
import { FIELD_LABEL } from '../suites/generate/fieldPresets'
import { aspectGlyph, FIELD_GLYPHS, fieldGlyph, glyphFor, tierGlyph, tileGlyph } from './presetGlyphs'

const SEED = seed.fields as Record<string, (string | string[])[]>
const words = (f: string) => (SEED[f] ?? []).map((it) => (typeof it === 'string' ? it : it[1]))
const html = (n: ReactNode) => renderToStaticMarkup(createElement('div', null, n))

describe('preset glyphs', () => {
  it('draws every built-in camera, composition and position preset of the seed', () => {
    for (const f of ['camera.distance', 'camera.angle', 'camera.lens', 'camera.depth_of_field', 'camera.f-number', 'composition', 'subject.position'])
      for (const v of words(f)) expect(glyphFor(f, v), `${f}: ${v}`).not.toBeNull()
  })
  it('draws the five angle moves, aspects and tiers', () => {
    for (const m of ['topdown', 'left45', 'right45', 'closeup', 'wide']) expect(glyphFor('move', m)).not.toBeNull()
    expect(aspectGlyph(16, 9)).toBeTruthy()
    for (const t of ['thumb', 'draft', 'full', 'custom'] as const) expect(tierGlyph(t)).toBeTruthy()
  })
  it('D92: draws the built-in negatives and leaves looks to their pictures', () => {
    for (const v of words('negative')) expect(glyphFor('negative', v), v).not.toBeNull()
    expect(glyphFor('negative', 'my own negative')).toBeNull()
    expect(glyphFor('lighting', 'moonlight')).toBeNull()
  })
  it('D92: every field and kind has a glyph, and a tile always gets one — an svg drawing, no letters but a lens or an f-number', () => {
    for (const f of [...Object.keys(FIELD_LABEL), 'panel', 'palette', 'character', 'prop', 'place', 'free']) expect(FIELD_GLYPHS, f).toContain(f)
    for (const f of Object.keys(SEED)) expect(FIELD_GLYPHS, f).toContain(f)
    expect(html(tileGlyph('lighting', 'violet dusk'))).toBe(html(fieldGlyph('lighting')))
    expect(html(tileGlyph('negative', 'my own negative'))).toBe(html(fieldGlyph('negative')))
    expect(html(fieldGlyph('nonsense'))).toBe(html(fieldGlyph('negative')))            // anything unknown: the generic mark, never letters
    for (const f of FIELD_GLYPHS) expect(html(fieldGlyph(f)), f).toMatch(/^<div><svg[^>]*>(?!.*<text)/)
    expect(html(glyphFor('camera.lens', 'anamorphic'))).not.toContain('<text')                 // the "ana" letters are gone
  })
})
