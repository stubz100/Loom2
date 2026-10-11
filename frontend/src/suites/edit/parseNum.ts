// What a ValueField (widgets.tsx, D55) accepts when typed: a number or a little arithmetic (50/2, 3x4, (1+2)*3, a decimal comma).
// Pure, so the unit suite (D68) can check it.

/** + − × ÷ and parentheses over numbers; null when the text is not such an expression. */
export function parseNum(text: string): number | null {
  const s = text.replace(/\s+/g, '').replace(/,/g, '.')
  if (!s) return null
  let i = 0
  const num = (): number | null => {
    if (s[i] === '(') { i++; const v = sum(); if (s[i] !== ')') return null; i++; return v }
    if (s[i] === '-') { i++; const v = num(); return v === null ? null : -v }
    const m = /^\d*\.?\d+(e[+-]?\d+)?/i.exec(s.slice(i)) ?? /^\d+\./.exec(s.slice(i))
    if (!m) return null
    i += m[0].length
    return parseFloat(m[0])
  }
  const prod = (): number | null => {
    let v = num()
    while (v !== null && (s[i] === '*' || s[i] === '/' || s[i] === 'x')) { const op = s[i++]; const r = num(); if (r === null) return null; v = op === '/' ? v / r : v * r }
    return v
  }
  const sum = (): number | null => {
    let v = prod()
    while (v !== null && (s[i] === '+' || s[i] === '-')) { const op = s[i++]; const r = prod(); if (r === null) return null; v = op === '+' ? v + r : v - r }
    return v
  }
  const v = sum()
  return v !== null && i === s.length && Number.isFinite(v) ? v : null
}
