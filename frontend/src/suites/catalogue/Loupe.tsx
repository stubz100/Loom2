// Loupe and Compare (08 §3c): zoom/pan at any scale, prev/next, facts strip; 2-up / 4-up with locked zoom/pan,
// wipe slider and difference toggle. One transform shared by every cell in Compare.
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { useCatalogue } from './catalogueStore'

interface Xf { s: number; x: number; y: number }

function useZoomPan(fitFor: { w: number; h: number } | null) {
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

const style = (xf: Xf) => ({ transform: `translate(${xf.x}px, ${xf.y}px) scale(${xf.s})` })

export function Loupe({ asset }: { asset: Asset }) {
  const c = useCatalogue()
  const order = c.visibleOrder()
  const idx = order.indexOf(asset.id)
  const dims = asset.w && asset.h ? { w: asset.w, h: asset.h } : null
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, textarea')) return
      if (e.key === 'ArrowLeft' && idx > 0) c.openLoupe(order[idx - 1])
      else if (e.key === 'ArrowRight' && idx < order.length - 1) c.openLoupe(order[idx + 1])
      else if (e.key === 'Escape') c.openLoupe(null)
      else if (e.ctrlKey && e.key === '0') { e.preventDefault(); fit() }
      else if (e.ctrlKey && e.key === '1') { e.preventDefault(); one() }
      else return
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [c, idx, order, fit, one])
  const pinned = c.compare.indexOf(asset.id) + 1
  return (
    <div className="loupe">
      <div className="view" ref={ref} {...handlers}>
        <img src={api.assetUrl(asset.id)} alt="" style={style(xf)} draggable={false} />
      </div>
      <div className="facts">
        <span>{idx + 1} / {order.length}</span>
        <span>{asset.model_id ?? asset.suite}</span>
        <span>{asset.w}×{asset.h}</span>
        <span>seed {asset.seed ?? '—'}</span>
        <span>{new Date(asset.created_at).toLocaleString()}</span>
        <span>{asset.state !== 'none' ? asset.state : ''} {asset.rating ? '★'.repeat(asset.rating) : ''}</span>
        <span className="spacer" />
        <span>{Math.round(xf.s * 100)}%</span>
        <button className="quiet" onClick={fit}>Fit</button>
        <button className="quiet" onClick={one}>1:1</button>
        <button className="quiet" onClick={() => c.togglePin(asset.id)}>{pinned ? `Unpin C${pinned}` : 'Pin for compare (C)'}</button>
        <button className="quiet" onClick={() => c.openLoupe(null)}>Close (Esc)</button>
      </div>
    </div>
  )
}

export function Compare({ assets }: { assets: Asset[] }) {
  const c = useCatalogue()
  const [wipe, setWipe] = useState(0.5)
  const [diff, setDiff] = useState(false)
  const [two, setTwo] = useState(true)
  const dims = assets[0]?.w && assets[0]?.h ? { w: assets[0].w!, h: assets[0].h! } : null
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  const shown = two ? assets.slice(0, 2) : assets.slice(0, 4)
  const swap = () => { if (assets.length >= 2) { c.clearCompare(); [assets[1], assets[0], ...assets.slice(2)].forEach((a) => c.togglePin(a.id)) } }
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, textarea')) return
      if (e.key === 'Escape') c.setCompareOpen(false)
      else if (e.key === 'Tab') { e.preventDefault(); swap() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })
  const cols = shown.length <= 2 ? shown.length : 2
  return (
    <div className="compare">
      <div className="cells" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {shown.map((a, i) => (
          <div key={a.id} className={`cell${diff && i > 0 ? ' diff' : ''}`} ref={i === 0 ? ref : undefined} {...handlers}>
            {diff && i > 0 && <img src={api.assetUrl(shown[0].id)} alt="" style={style(xf)} draggable={false} />}
            <img className={diff && i > 0 ? 'over' : ''} src={api.assetUrl(a.id)} alt="" style={{ ...style(xf), ...(two && i === 1 && !diff ? { clipPath: `inset(0 0 0 ${wipe * 100}%)` } : {}) }} draggable={false} />
            {two && i === 1 && !diff && <div className="wipe" style={{ left: `${wipe * 100}%` }} />}
            <span className="tag">{String.fromCharCode(65 + i)} · {a.model_id ?? a.suite} · seed {a.seed ?? '—'}</span>
          </div>
        ))}
      </div>
      <div className="bar">
        <span>Compare {shown.length}-up · zoom/pan locked</span>
        {two && !diff && <><span>wipe</span><input type="range" min={0} max={1} step={0.01} value={wipe} onChange={(e) => setWipe(Number(e.target.value))} /></>}
        <label><input type="checkbox" checked={diff} onChange={(e) => setDiff(e.target.checked)} /> difference</label>
        <button className="quiet" onClick={() => setTwo(!two)} disabled={assets.length < 3}>{two ? '4-up' : '2-up'}</button>
        <button className="quiet" onClick={swap}>Swap (Tab)</button>
        <span className="spacer" />
        <span>{Math.round(xf.s * 100)}%</span>
        <button className="quiet" onClick={fit}>Fit</button>
        <button className="quiet" onClick={one}>1:1</button>
        <button className="quiet" onClick={() => c.setCompareOpen(false)}>Back (Esc)</button>
        <button className="quiet" onClick={() => c.clearCompare()}>Unpin all</button>
      </div>
    </div>
  )
}
