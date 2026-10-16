// D90 (02 §6.3): every built-in preset whose meaning is geometry has a drawn glyph — none falls back to a monogram by accident.
import { describe, expect, it } from 'vitest'
import { BUILTIN } from '../suites/generate/fieldPresets'
import { aspectGlyph, glyphFor, monogram, tierGlyph } from './presetGlyphs'

describe('preset glyphs', () => {
  it('draws every built-in camera, composition and position preset', () => {
    for (const f of ['camera.distance', 'camera.angle', 'camera.lens', 'camera.depth_of_field', 'camera.f-number', 'composition', 'subject.position'] as const)
      for (const v of BUILTIN[f]) expect(glyphFor(f, v), `${f}: ${v}`).not.toBeNull()
  })
  it('draws the five angle moves, aspects and tiers', () => {
    for (const m of ['topdown', 'left45', 'right45', 'closeup', 'wide']) expect(glyphFor('move', m)).not.toBeNull()
    expect(aspectGlyph(16, 9)).toBeTruthy()
    for (const t of ['thumb', 'draft', 'full', 'custom'] as const) expect(tierGlyph(t)).toBeTruthy()
  })
  it('leaves looks to swatches and gives a monogram', () => {
    expect(glyphFor('lighting', 'moonlight')).toBeNull()
    expect(monogram('golden hour rim light')).toBe('GH')
  })
})
