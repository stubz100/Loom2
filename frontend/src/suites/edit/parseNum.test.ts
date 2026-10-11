// D68 (ArtCraft P6): what a typed ValueField accepts (D55): numbers and a little arithmetic, anything else is refused.
import { describe, expect, it } from 'vitest'
import { parseNum } from './parseNum'

describe('parseNum', () => {
  it('reads plain numbers, a decimal comma, exponents and spaces', () => {
    expect(parseNum('42')).toBe(42)
    expect(parseNum(' 7 ')).toBe(7)
    expect(parseNum('.5')).toBe(0.5)
    expect(parseNum('1,5')).toBe(1.5)
    expect(parseNum('1e3')).toBe(1000)
    expect(parseNum('-5')).toBe(-5)
  })
  it('evaluates + − × ÷ with precedence and parentheses', () => {
    expect(parseNum('50/2')).toBe(25)
    expect(parseNum('3x4')).toBe(12)
    expect(parseNum('2+3*4')).toBe(14)
    expect(parseNum('(1+2)*3')).toBe(9)
    expect(parseNum('2--3')).toBe(5)
    expect(parseNum('10-2-3')).toBe(5)
    expect(parseNum('100/4/5')).toBe(5)
  })
  it('refuses text, unbalanced or dangling expressions and non-finite results', () => {
    for (const t of ['', '   ', 'abc', '12px', '(1+2', '1+', '*3', '1/0']) expect(parseNum(t), t).toBeNull()
  })
})
