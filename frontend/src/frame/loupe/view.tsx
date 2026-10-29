// The loupe's viewer (08 §3c; moved out of the Catalogue for the Bin, B1 / D159): zoom and pan at any scale (Ctrl+wheel about the pointer,
// a drag pans), Fit and 1:1; a clip or a spoken line plays (D90 B10). The Bin's large view, its compare and the detached window (D155) draw
// with it.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { LoupeMedia } from './media'
import './loupe.css'

export interface Xf { s: number; x: number; y: number }

export function useZoomPan(fitFor: { w: number; h: number } | null) {
  const [xf, setXf] = useState<Xf>({ s: 1, x: 0, y: 0 })
  const ref = useRef<HTMLDivElement>(null)
  const fit = useCallback(() => {
    const el = ref.current
    if (!el || !fitFor) return
    const s = Math.min(el.clientWidth / fitFor.w, el.clientHeight / fitFor.h)   // fit may upscale: the loupe is for looking
    setXf({ s, x: (el.clientWidth - fitFor.w * s) / 2, y: (el.clientHeight - fitFor.h * s) / 2 })
  }, [fitFor])
  const one = useCallback(() => {
    const el = ref.current
    if (!el || !fitFor) return
    setXf({ s: 1, x: (el.clientWidth - fitFor.w) / 2, y: (el.clientHeight - fitFor.h) / 2 })
  }, [fitFor])
  useEffect(() => { fit() }, [fit])
  const onWheel = (e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    const el = ref.current!
    const r = el.getBoundingClientRect()
    const px = e.clientX - r.left, py = e.clientY - r.top
    const k = Math.exp(-e.deltaY * 0.0015)
    setXf((t) => { const s = Math.max(0.05, Math.min(32, t.s * k)); return { s, x: px - (px - t.x) * (s / t.s), y: py - (py - t.y) * (s / t.s) } })
  }
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)
  const onPointerDown = (e: React.PointerEvent) => { drag.current = { x: e.clientX, y: e.clientY, ox: xf.x, oy: xf.y }; (e.target as Element).setPointerCapture?.(e.pointerId) }
  const onPointerMove = (e: React.PointerEvent) => { if (drag.current) setXf((t) => ({ ...t, x: drag.current!.ox + e.clientX - drag.current!.x, y: drag.current!.oy + e.clientY - drag.current!.y })) }
  const onPointerUp = () => { drag.current = null }
  return { xf, setXf, ref, fit, one, handlers: { onWheel, onPointerDown, onPointerMove, onPointerUp } }
}

export const xfStyle = (xf: Xf) => ({ transform: `translate(${xf.x}px, ${xf.y}px) scale(${xf.s})` })

/** D90 (B10): a clip plays in a <video>, a spoken line in an <audio> under its thumbnail — never an <img> of a file it cannot show. */
export function Playable({ m }: { m: LoupeMedia }) {
  if (m.kind === 'video') return <video key={m.src} className="loupe-media" src={m.src} poster={m.poster} controls preload="metadata" aria-label="the clip" />
  if (m.kind === 'audio') return <div className="loupe-audio"><img src={m.poster} alt="" draggable={false} /><audio key={m.src} src={m.src} controls preload="metadata" aria-label="the spoken line" /></div>
  return null
}
