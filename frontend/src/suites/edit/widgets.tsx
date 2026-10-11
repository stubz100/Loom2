// Mouse-first value widgets for the Edit panels (D55; PhotoCraft ui-egui widgets.rs popup_value_field / dropdown_wheel_hovered and
// blend_preview.rs @ b37bff98, MIT OR Apache-2.0 — behaviour ported, code written for React).
//
// ValueField: type a number (applied as you type; arithmetic such as 50/2 on Enter), scrub by dragging on the number (right or up
// raises; 0.5 per px, 0.01 for ranges up to 10; Shift ÷10), arrow keys step 1 (Shift ×10, Ctrl ÷10; from the nearest whole unit), or press the ▾ and drag a
// pop-up slider in one gesture (a click on ▾ leaves the slider open). onStart / onCommit bracket each gesture — one undo step.
//
// BlendSelect: a dropdown whose closed button steps the mode with the mouse wheel and whose open list previews the hovered mode on
// the canvas (through onPreview — nothing is recorded) and commits on click; each choice is one history step.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { parseNum } from './parseNum'

const clampTo = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
const SLIDER_W = 160
const ARROW_W = 14

/** A pop-up's place on the page, next to its anchor: rendered through a portal with fixed positioning, so a scrolling panel never
 * clips it; below the anchor, or above when the space below is short; inside the window horizontally. Follows scrolls and resizes. */
function usePopupPlace(anchor: RefObject<HTMLElement | null>, open: boolean, size: { w?: number; h: number; align: 'left' | 'right' }) {
  const [place, setPlace] = useState<{ left: number; top: number; width: number; maxHeight: number } | null>(null)
  useLayoutEffect(() => {
    if (!open) return
    const at = () => {
      const el = anchor.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const width = size.w ?? r.width
      const below = window.innerHeight - r.bottom - 6, above = r.top - 6
      const up = below < Math.min(size.h, 120) && above > below
      const maxHeight = Math.max(40, Math.min(size.h, up ? above : below))
      const left = clampTo(size.align === 'right' ? r.right - width : r.left, 4, window.innerWidth - width - 4)
      setPlace({ left, width, maxHeight, top: up ? r.top - 2 - maxHeight : r.bottom + 2 })
    }
    at()
    window.addEventListener('scroll', at, true); window.addEventListener('resize', at)
    return () => { window.removeEventListener('scroll', at, true); window.removeEventListener('resize', at) }
  }, [open, anchor, size.w, size.h, size.align])
  return open ? place : null
}

export interface ValueFieldProps {
  label: string
  /** Stored value; `scale` converts it to what the field shows (0.5 × 100 → 50 %). */
  value: number; min: number; max: number; scale?: number; unit?: string
  /** Stored-value granularity (64 → multiples of 64 from `min`); omitted: free to 1/10000. */
  step?: number
  onChange: (v: number) => void
  onStart?: () => void; onCommit?: () => void
  disabled?: boolean; title?: string
  /** No grid label of its own (the row around it names it); `label` still names the field for assistive tech and tooltips. */
  bare?: boolean
}

export function ValueField({ label, value, min, max, scale = 1, unit, step, onChange, onStart, onCommit, disabled, title, bare }: ValueFieldProps) {
  const lo = min * scale, hi = max * scale
  const fine = hi - lo <= 10 && !(step !== undefined && step * scale >= 1)    // whole-number fields (candidates 1–4) show no decimals
  const shown = value * scale
  const fmt = (v: number) => (fine ? v.toFixed(2) : String(Math.round(v * 100) / 100))
  const [text, setText] = useState<string | null>(null)
  const [popup, setPopup] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const pop = useRef<HTMLDivElement>(null)
  const place = usePopupPlace(wrap, popup, { w: SLIDER_W, h: 26, align: 'right' })
  const typing = useRef<number | null>(null)                          // F11: the shown value when typing began — one gesture until Enter / blur
  const typed = (v: number) => { if (typing.current === null) { typing.current = shown; onStart?.() } set(v) }
  const endTyping = () => { if (typing.current !== null) { typing.current = null; onCommit?.() } }
  const snap = (v: number) => (step ? Math.min(max, Math.max(min, min + Math.round((v - min) / step) * step)) : v)
  const set = (display: number) => onChange(snap(clampTo(Math.round(display * 10000) / 10000, lo, hi) / scale))
  useEffect(() => {                                                  // the slider pop-up closes on a press outside it
    if (!popup) return
    const off = (e: PointerEvent) => { if (!wrap.current?.contains(e.target as Node) && !pop.current?.contains(e.target as Node)) setPopup(false) }
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
    if (e.key === 'Enter') { const v = parseNum(e.currentTarget.value); if (v !== null) typed(v); endTyping(); setText(null); e.currentTarget.blur(); return }
    if (e.key === 'Escape') { if (typing.current !== null) set(typing.current); endTyping(); setText(null); e.currentTarget.blur(); return }
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
      {!bare && <label>{label}</label>}
      <div className={`vfield${disabled ? ' disabled' : ''}`} ref={wrap} title={title ?? `${label}: drag the number to scrub (Shift: fine), type a value or a sum, ↑ ↓ step; ▾ drag for a slider`}>
        <input className="vfield-num" value={text ?? fmt(shown)} disabled={disabled} aria-label={label}
          onPointerDown={onNumDown} onChange={(e) => { setText(e.target.value); const v = Number(e.target.value); if (e.target.value.trim() !== '' && Number.isFinite(v)) typed(v) }}
          onBlur={(e) => { const v = parseNum(e.target.value); if (text !== null && v !== null && v !== shown) typed(v); endTyping(); setText(null) }} onKeyDown={onKey} />
        {unit ? <i className="vfield-unit">{unit}</i> : null}
        <button type="button" className="vfield-arrow" aria-label={`${label} slider`} title={`${label}: press and drag, or click for a slider`} disabled={disabled} onPointerDown={onArrowDown}>▾</button>
        {popup && place && createPortal(
          <div className="vfield-pop" ref={pop} onPointerDown={onTrack} style={{ left: place.left, top: place.top, width: SLIDER_W }}>
            <div className="vfield-track"><div className="vfield-knob" style={{ left: `calc(7px + ${f} * (100% - 14px))` }} /></div>
          </div>, document.body)}
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
  const place = usePopupPlace(btn, open, { h: 320, align: 'left' })
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
      {open && place && createPortal(
        <div className="blend-list" ref={list} role="listbox" style={{ left: place.left, top: place.top, width: place.width, maxHeight: place.maxHeight }} onPointerLeave={() => onPreview(null)}>
          {options.map((o) => (
            <div key={o.value} role="option" aria-selected={o.value === value} className={`blend-opt${o.value === value ? ' current' : ''}`}
              onPointerEnter={() => onPreview(o.value === value ? null : o.value)} onClick={() => { onPreview(null); if (o.value !== value) onChoose(o.value); setOpen(false) }}>{o.label}</div>
          ))}
        </div>, document.body)}
    </div>
  )
}

/** A latched-modifier toggle for the strip (D55). */
export function LatchButton({ on, label, title, onToggle }: { on: boolean; label: ReactNode; title: string; onToggle: () => void }) {
  return <button type="button" className={`quiet latch${on ? ' active' : ''}`} aria-pressed={on} title={title} onClick={onToggle}>{label}</button>
}
