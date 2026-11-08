// review K60 / K93: a number typed whole. Clay's number fields committed on every keystroke — each keystroke an edit, a save and an undo step,
// and a value on its way read as a value: "-90" became 90 (the "-" alone reads as 0), a range end of 48 became 25 on the way and a toast. The
// text is the field's own while it is typed; it is committed by the input's native `change` — Enter, leaving the field, or a click on its
// arrows (rule 3: the mouse's way, at once) — never per keystroke (React's onChange is the `input` event). A blank or unreadable text leaves
// the value as it was.
import { useEffect, useRef, useState } from 'react'

const shown = (v: number, digits: number) => String(+v.toFixed(digits))

export function NumField({ value, onCommit, label, step, min, max, digits = 2, className }: { value: number; onCommit: (v: number) => void; label: string; step?: number; min?: number; max?: number
  digits?: number; className?: string }) {
  const [text, setText] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const latest = useRef({ value, onCommit, digits })
  useEffect(() => { latest.current = { value, onCommit, digits } })   // the native listener reads the props of the last render
  const pending = useRef<string | null>(null)                         // what is typed and not committed yet (read by the native listener)
  useEffect(() => {
    const el = input.current
    if (!el) return
    const commit = () => {
      const raw = pending.current ?? el.value
      pending.current = null
      setText(null)
      const { value: cur, onCommit: done, digits: d } = latest.current
      const v = Number(raw)
      if (raw.trim() !== '' && Number.isFinite(v) && v !== +cur.toFixed(d)) done(v)
    }
    el.addEventListener('change', commit)                              // Enter, blur after an edit, an arrow click
    return () => el.removeEventListener('change', commit)
  }, [])
  return <input ref={input} type="number" className={className} step={step} min={min} max={max} aria-label={label} value={text ?? shown(value, digits)}
    onChange={(e) => { pending.current = e.target.value; setText(e.target.value) }}
    onBlur={() => { if (pending.current !== null) input.current?.dispatchEvent(new Event('change')) }}
    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }} />
}
