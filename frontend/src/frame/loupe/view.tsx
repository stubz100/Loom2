// The loupe's viewer (08 §3c; moved out of the Catalogue for the Bin, B1 / D159): zoom and pan at any scale (Ctrl+wheel about the pointer,
// a drag pans), Fit and 1:1; a clip or a spoken line plays (D90 B10). The Bin's large view, its compare and the detached window (D155) draw
// with it.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { LoupeMedia } from './media'
import './loupe.css'

export interface Xf { s: number; x: number; y: number }

/** review K116: the transform that fits `fitFor` into a `w` × `h` view, centred (fit may upscale: the loupe is for looking). */
export function fitXf(w: number, h: number, fitFor: { w: number; h: number }): Xf {
  const s = Math.min(w / fitFor.w, h / fitFor.h)
  return { s, x: (w - fitFor.w * s) / 2, y: (h - fitFor.h * s) / 2 }
}

export function useZoomPan(fitFor: { w: number; h: number } | null) {
  const [xf, setXf] = useState<Xf>({ s: 1, x: 0, y: 0 })
  const ref = useRef<HTMLDivElement>(null)
  const fitted = useRef(true)                                          // review K116: the view shows the fit (no zoom or pan since) — a resize refits it
  const fit = useCallback(() => {
    const el = ref.current
    fitted.current = true
    if (!el || !fitFor || !el.clientWidth || !el.clientHeight) return  // not laid out yet: the resize observer fits it once it is
    setXf(fitXf(el.clientWidth, el.clientHeight, fitFor))
  }, [fitFor])
  const one = useCallback(() => {
    const el = ref.current
    if (!el || !fitFor) return
    fitted.current = false
    setXf({ s: 1, x: (el.clientWidth - fitFor.w) / 2, y: (el.clientHeight - fitFor.h) / 2 })
  }, [fitFor])
  useEffect(() => { fit() }, [fit])
  // review K116: the loupe refits when its box changes size (the window, full screen, the panels) while it shows the fit; the element is
  // looked up after every render, since a caller may hand the ref to another element (Compare's first cell is keyed by its asset)
  const observed = useRef<{ el: HTMLDivElement | null; ro: ResizeObserver | null }>({ el: null, ro: null })
  const fitRef = useRef(fit)
  useEffect(() => { fitRef.current = fit }, [fit])
  useEffect(() => {
    const el = ref.current, o = observed.current
    if (el === o.el || typeof ResizeObserver === 'undefined') return
    o.ro?.disconnect()
    o.el = el
    o.ro = el ? new ResizeObserver(() => { if (fitted.current) fitRef.current() }) : null
    if (el) o.ro!.observe(el)
  })
  useEffect(() => () => { observed.current.ro?.disconnect() }, [])
  // review K94: React's wheel listener is passive — its preventDefault did nothing, so Ctrl+wheel zoomed the whole window too; a capturing
  // listener that may cancel stops the browser's zoom over any element carrying these handlers (they mark it `data-zoompan`)
  useEffect(() => {
    const guard = (e: WheelEvent) => { if ((e.ctrlKey || e.metaKey) && (e.target as Element | null)?.closest?.('[data-zoompan]')) e.preventDefault() }
    window.addEventListener('wheel', guard, { capture: true, passive: false })
    return () => window.removeEventListener('wheel', guard, { capture: true })
  }, [])
  const onWheel = (e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    const el = ref.current
    if (!el) return
    fitted.current = false
    const r = el.getBoundingClientRect()
    const px = e.clientX - r.left, py = e.clientY - r.top
    const k = Math.exp(-e.deltaY * 0.0015)
    setXf((t) => { const s = Math.max(0.05, Math.min(32, t.s * k)); return { s, x: px - (px - t.x) * (s / t.s), y: py - (py - t.y) * (s / t.s) } })
  }
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)
  const onPointerDown = (e: React.PointerEvent) => { drag.current = { x: e.clientX, y: e.clientY, ox: xf.x, oy: xf.y }; (e.target as Element).setPointerCapture?.(e.pointerId) }
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current                                             // review K94: read now — the updater runs later, after a release may have cleared it
    if (!d) return
    fitted.current = false
    const x = d.ox + e.clientX - d.x, y = d.oy + e.clientY - d.y
    setXf((t) => ({ ...t, x, y }))
  }
  const onPointerUp = () => { drag.current = null }
  return { xf, setXf, ref, fit, one, handlers: { onWheel, onPointerDown, onPointerMove, onPointerUp, 'data-zoompan': '' } }
}

export const xfStyle = (xf: Xf) => ({ transform: `translate(${xf.x}px, ${xf.y}px) scale(${xf.s})` })

/** D90 (B10): a clip plays in a <video>, a spoken line in an <audio> under its thumbnail — never an <img> of a file it cannot show. */
export function Playable({ m }: { m: LoupeMedia }) {
  if (m.kind === 'video') return <video key={m.src} className="loupe-media" src={m.src} poster={m.poster} controls preload="metadata" aria-label="the clip" />
  if (m.kind === 'audio') return <div className="loupe-audio"><img src={m.poster} alt="" draggable={false} /><audio key={m.src} src={m.src} controls preload="metadata" aria-label="the spoken line" /></div>
  return null
}
