// D154: a text layer's layout — pure, measured by a fake advance (10 px a character), no canvas.
import { describe, expect, it } from 'vitest'
import { fontString, psdFontName } from './textFonts'
import { layoutText, padOf, TEXT_DEFAULTS, textLayerName, type TextBlock } from './textRaster'

const measure = (s: string) => s.length * 10
const block = (extra: Partial<TextBlock> = {}): TextBlock => ({ ...TEXT_DEFAULTS, size: 20, leading: 1.5, ...extra })

describe('layoutText (D154)', () => {
  it('point text takes the widest line plus the pad, one line per newline, the baseline 0.8 em below each line top', () => {
    const t = block({ content: 'Scene 1\nthe alley' })
    const l = layoutText(t, measure)
    const pad = padOf(t)
    expect(pad).toBe(2)                                                   // no outline: max(2, 8 % of 20) = 2
    expect(l.lineHeight).toBe(30)
    expect(l.lines.map((x) => x.text)).toEqual(['Scene 1', 'the alley'])
    expect(l.w).toBe(90 + 2 * pad)                                         // "the alley" = 9 characters
    expect(l.h).toBe(2 * 30 + 2 * pad)
    expect(l.lines[0]).toMatchObject({ x: pad, y: pad + 16 })
    expect(l.lines[1].y).toBe(pad + 30 + 16)
  })
  it('tracking widens a line by one gap per character pair; the outline widens the pad', () => {
    const t = block({ content: 'abc', tracking: 5, outline: { width: 8, colour: '#000' } })
    const l = layoutText(t, measure)
    expect(padOf(t)).toBe(6)                                              // 8 / 2 + max(2, 1.6) → ceil(6)
    expect(l.lines[0].width).toBe(30 + 2 * 5)
    expect(l.w).toBe(40 + 12)
  })
  it('centre and right alignment place the line inside the width', () => {
    const c = layoutText(block({ content: 'ab\nabcd', align: 'center' }), measure)
    expect(c.w).toBe(44)
    expect(c.lines[0].x).toBe((44 - 20) / 2)
    expect(c.lines[1].x).toBe((44 - 40) / 2)
    const r = layoutText(block({ content: 'ab\nabcd', align: 'right' }), measure)
    expect(r.lines[0].x).toBe(44 - 2 - 20)
  })
  it('paragraph text wraps words to the box and takes the box size; a word wider than the box breaks by characters', () => {
    const t = block({ content: 'one two three four', box: [84, 200] })     // 80 px of text a line
    const l = layoutText(t, measure)
    expect([l.w, l.h]).toEqual([84, 200])
    expect(l.lines.map((x) => x.text)).toEqual(['one two', 'three', 'four'])
    const long = layoutText(block({ content: 'abcdefghijkl', box: [54, 100] }), measure)   // 50 px a line: 5 characters
    expect(long.lines.map((x) => x.text)).toEqual(['abcde', 'fghij', 'kl'])
    expect(layoutText(block({ content: 'ab cd', box: [200, 50] }), measure).lines).toHaveLength(1)
  })
  it('an empty block still lays out one empty line of the pad and line height', () => {
    const l = layoutText(block({ content: '' }), measure)
    expect(l.lines).toHaveLength(1)
    expect([l.w, l.h]).toEqual([4, 34])
  })
})

describe('the fonts and the names (D154)', () => {
  it('the font shorthand carries the style, the weight, the size and a fallback', () => {
    expect(fontString('Courier Prime', 24, 'bold', true)).toBe('italic 700 24px "Courier Prime", sans-serif')
    expect(fontString('Inter', 48, 'normal', false)).toBe('400 48px "Inter", sans-serif')
  })
  it('the PSD font name is the bundled stem or the system family without spaces, plus the face', () => {
    expect(psdFontName('Courier Prime', 'bold', true)).toBe('CourierPrime-BoldItalic')
    expect(psdFontName('Inter', 'normal', false)).toBe('Inter-Regular')
    expect(psdFontName('Segoe UI', 'normal', true)).toBe('SegoeUI-Italic')
  })
  it('the layer name is the first words, trimmed', () => {
    expect(textLayerName('  Scene 1 —  the alley  ')).toBe('Scene 1 — the alley')
    expect(textLayerName('')).toBe('Text')
    expect(textLayerName('a'.repeat(40))).toBe(`${'a'.repeat(23)}…`)
  })
})
