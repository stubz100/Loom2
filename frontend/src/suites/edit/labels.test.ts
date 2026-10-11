// D68 (ArtCraft P6): one spelling per name across menus, layer rows and the Properties title (review U6).
import { describe, expect, it } from 'vitest'
import { blendLabel, typeLabel } from './labels'

describe('typeLabel', () => {
  it('uses the house spelling for known types', () => {
    expect(typeLabel('hue_saturation')).toBe('Hue/Saturation')
    expect(typeLabel('color_balance')).toBe('Colour balance')
    expect(typeLabel('color_to_alpha')).toBe('Colour to alpha')
    expect(typeLabel('black_white')).toBe('Black & white')
  })
  it('turns an unknown type into sentence case, and nothing into nothing', () => {
    expect(typeLabel('high_pass')).toBe('High pass')
    expect(typeLabel('noise')).toBe('Noise')
    expect(typeLabel(undefined)).toBe('')
    expect(typeLabel('')).toBe('')
  })
})

describe('blendLabel', () => {
  it('names blend modes as Photoshop does', () => {
    expect(blendLabel('normal')).toBe('Normal')
    expect(blendLabel('color-burn')).toBe('Color Burn')
    expect(blendLabel('pass-through')).toBe('Pass Through')
    expect(blendLabel('linear-dodge')).toBe('Linear Dodge')
  })
})
