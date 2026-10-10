// Mouse-first value widgets for the Edit panels (D55; PhotoCraft ui-egui widgets.rs popup_value_field / dropdown_wheel_hovered and
// blend_preview.rs @ b37bff98, MIT OR Apache-2.0 — behaviour ported, code written for React).
//
// ValueField: type a number (applied as you type; arithmetic such as 50/2 on Enter), scrub by dragging on the number (right or up
// raises; 0.5 per px, 0.01 for ranges up to 10; Shift ÷10), arrow keys step 1 (Shift ×10, Ctrl ÷10; from the nearest whole unit), or press the ▾ and drag a
// pop-up slider in one gesture (a click on ▾ leaves the slider open). onStart / onCommit bracket each gesture — one undo step.
//
// BlendSelect: a dropdown whose closed button steps the mode with the mouse wheel and whose open list previews the hovered mode on
// the canvas (through onPreview — nothing is recorded) and commits on click; each choice is one history step.
import { useEffect, useRef, useState, type ReactNode } from 'react'

const clampTo = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
const SLIDER_W = 160
const ARROW_W = 14

/** + − × ÷ and parentheses over numbers; null when the text is not such an expression. */
function parseNum(text: string): number | null {
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

export interface ValueFieldProps {
  label: string
  /** Stored value; `scale` converts it to what the field shows (0.5 × 100 → 50 %). */
  value: number; min: number; max: number; scale?: number; unit?: string
  onChange: (v: number) => void
  onStart?: () => void; onCommit?: () => void
  disabled?: boolean; title?: string
}

export function ValueField({ label, value, min, max, scale = 1, unit, onChange, onStart, onCommit, disabled, title }: ValueFieldProps) {
  const lo = min * scale, hi = max * scale
  const fine = hi - lo <= 10
  const shown = value * scale
  const fmt = (v: number) => (fine ? v.toFixed(2) : String(Math.round(v * 100) / 100))
  const [text, setText] = useState<string | null>(null)
  const [popup, setPopup] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const set = (display: number) => onChange(clampTo(Math.round(display * 10000) / 10000, lo, hi) / scale)
  useEffect(() => {                                                  // the slider pop-up closes on a press outside it
    if (!popup) return
    const off = (e: PointerEvent) => { if (!wrap.current?.contains(e.target as Node)) setPopup(false) }
    window.addEventListener('pointerdown', off, { capture: true })
    return () => window.removeEventListener('pointerdown', off, { capture: true })
  }, [popup])

  /** Scrub on the number: a press that moves more than 3 px is a scrub (one gesture), one that does not focuses the box for typing. */
  const onNumDown = (e: React.PointerEvent<HTMLInputElement>) => {
    if (disabled || e.button !== 0 || document.activeElement === e.currentTarget) return
    e.preventDefault()
    const input = e.currentTarget, x0 = e.clientX, y0 = e.clientY, v0 = shown
    let scrubbing = false
    const move = (ev: PointerEvent) => {
      const d = ev.clientX - x0 - (ev.clientY - y0)
      if (!scrubbing && Math.abs(ev.clientX - x0) + Math.abs(ev.clientY - y0) < 3) return
      if (!scrubbing) { scrubbing = true; onStart?.(); document.body.style.cursor = 'ew-resize' }
      set(v0 + d * (fine ? 0.01 : 0.5) / (ev.shiftKey ? 10 : 1))
    }
    const up = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
      document.body.style.cursor = ''
      if (scrubbing) onCommit?.()
      else { input.focus(); input.select() }
    }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { const v = parseNum(e.currentTarget.value); if (v !== null) { onStart?.(); set(v); onCommit?.() } setText(null); e.currentTarget.blur(); return }
    if (e.key === 'Escape') { setText(null); e.currentTarget.blur(); return }
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return
    e.preventDefault()
    let step = fine ? 0.01 : 1
    if (e.shiftKey) step *= 10
    if (e.ctrlKey || e.metaKey) step = Math.max(0.01, step / 10)
    const unit = fine ? 0.01 : 1
    const base = Math.round(shown / unit) * unit                       // to whole units first (55.4 + 1 = 56; 25 + 10 = 35)
    onStart?.(); set(base + (e.key === 'ArrowUp' ? step : -step)); onCommit?.()
    setText(null)
  }
  /** ▾: press and drag sets the value along the pop-up slider in one gesture; a click toggles the pop-up. */
  const onArrowDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (disabled || e.button !== 0) return
    e.preventDefault()
    const x0 = e.clientX, v0 = shown
    let dragging = false
    const move = (ev: PointerEvent) => {
      if (!dragging && Math.abs(ev.clientX - x0) < 3) return
      if (!dragging) { dragging = true; onStart?.(); setPopup(true) }
      set(v0 + ((ev.clientX - x0) / (SLIDER_W - ARROW_W)) * (hi - lo))
    }
    const up = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
      if (dragging) { onCommit?.(); setPopup(false) } else setPopup((p) => !p)
    }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  /** The pop-up slider: click or drag on the track, one gesture each. */
  const onTrack = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const at = (x: number) => set(lo + clampTo((x - r.left - 7) / (r.width - 14), 0, 1) * (hi - lo))
    onStart?.(); at(e.clientX)
    e.currentTarget.setPointerCapture(e.pointerId)
    const el = e.currentTarget
    const move = (ev: PointerEvent) => at(ev.clientX)
    const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); onCommit?.() }
    el.addEventListener('pointermove', move); el.addEventListener('pointerup', up)
  }
  const f = hi > lo ? (shown - lo) / (hi - lo) : 0
  return (
    <>
      <label>{label}</label>
      <div className={`vfield${disabled ? ' disabled' : ''}`} ref={wrap} title={title ?? `${label}: drag the number to scrub (Shift: fine), type a value or a sum, ↑ ↓ step; ▾ drag for a slider`}>
        <input className="vfield-num" value={text ?? fmt(shown)} disabled={disabled} aria-label={label}
          onPointerDown={onNumDown} onChange={(e) => { setText(e.target.value); const v = Number(e.target.value); if (e.target.value.trim() !== '' && Number.isFinite(v)) { onStart?.(); set(v); onCommit?.() } }}
          onBlur={(e) => { const v = parseNum(e.target.value); if (text !== null && v !== null && v !== shown) { onStart?.(); set(v); onCommit?.() } setText(null) }} onKeyDown={onKey} />
        {unit ? <i className="vfield-unit">{unit}</i> : null}
        <button type="button" className="vfield-arrow" aria-label={`${label} slider`} title={`${label}: press and drag, or click for a slider`} disabled={disabled} onPointerDown={onArrowDown}>▾</button>
        {popup && (
          <div className="vfield-pop" onPointerDown={onTrack} style={{ width: SLIDER_W }}>
            <div className="vfield-track"><div className="vfield-knob" style={{ left: `calc(7px + ${f} * (100% - 14px))` }} /></div>
          </div>
        )}
      </div>
    </>
  )
}

export interface BlendOption { value: string; label: string }

/** D55: the blend-mode dropdown — wheel over the closed button steps the mode, hovering an open entry previews it, a click chooses. */
export function BlendSelect({ value, options, onChoose, onPreview, disabled }: { value: string; options: BlendOption[]; onChoose: (v: string) => void; onPreview: (v: string | null) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const btn = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const wheelAcc = useRef(0)
  const idx = Math.max(0, options.findIndex((o) => o.value === value))
  const step = (d: number) => { const j = clampTo(idx + d, 0, options.length - 1); if (j !== idx) onChoose(options[j].value) }
  useEffect(() => {                                                  // a non-passive wheel listener so the panel does not scroll
    const el = btn.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (disabled) return
      e.preventDefault()
      // one mode per wheel notch (≈ 100 px, or 3 lines); a trackpad's small deltas accumulate to the same distance
      wheelAcc.current += e.deltaMode === 1 ? e.deltaY * 33 : e.deltaMode === 2 ? e.deltaY * 100 : e.deltaY
      const n = Math.trunc(wheelAcc.current / 100)
      if (n) { wheelAcc.current -= n * 100; step(Math.sign(n)) }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })
  useEffect(() => {
    if (!open) return
    const off = (e: PointerEvent) => { if (!list.current?.contains(e.target as Node) && !btn.current?.contains(e.target as Node)) { setOpen(false); onPreview(null) } }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setOpen(false); onPreview(null) } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); step(e.key === 'ArrowDown' ? 1 : -1) } else if (e.key === 'Enter') setOpen(false)
    }
    window.addEventListener('pointerdown', off, { capture: true }); window.addEventListener('keydown', key, { capture: true })
    list.current?.querySelector('.current')?.scrollIntoView({ block: 'nearest' })
    return () => { window.removeEventListener('pointerdown', off, { capture: true }); window.removeEventListener('keydown', key, { capture: true }) }
  })
  return (
    <div className="blend-select">
      <button type="button" ref={btn} className="blend-btn" disabled={disabled} aria-haspopup="listbox" aria-expanded={open}
        title="Blend mode — the wheel steps through the modes; open the list and hover a mode to preview it on the canvas"
        onClick={() => { setOpen((o) => !o); onPreview(null) }}>{options[idx]?.label ?? value}<span className="caret">▾</span></button>
      {open && (
        <div className="blend-list" ref={list} role="listbox" onPointerLeave={() => onPreview(null)}>
          {options.map((o) => (
            <div key={o.value} role="option" aria-selected={o.value === value} className={`blend-opt${o.value === value ? ' current' : ''}`}
              onPointerEnter={() => onPreview(o.value === value ? null : o.value)} onClick={() => { onPreview(null); if (o.value !== value) onChoose(o.value); setOpen(false) }}>{o.label}</div>
          ))}
        </div>
      )}
    </div>
  )
}

/** A latched-modifier toggle for the strip (D55). */
export function LatchButton({ on, label, title, onToggle }: { on: boolean; label: ReactNode; title: string; onToggle: () => void }) {
  return <button type="button" className={`quiet latch${on ? ' active' : ''}`} aria-pressed={on} title={title} onClick={onToggle}>{label}</button>
}
