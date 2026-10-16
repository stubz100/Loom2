// Loupe and Compare (08 §3c): zoom/pan at any scale, prev/next, facts strip; 2-up / 4-up with locked zoom/pan,
// wipe slider and difference toggle. One transform shared by every cell in Compare.
import { Ellipsis, Film, FolderInput, Star } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Asset } from '../../api/types'
import { CommandButton, CommandRow, MenuButton } from '../../frame/CommandButton'
import { handleKeyFor, runCommand } from '../../frame/commands'
import { catView } from './viewKeys'
import { showMenu } from '../../frame/ContextMenu'
import { moveToMenu, rateMenu, tileMenu } from './catalogueCommands'
import type { MenuItem } from '../../frame/commands'
import { useCat } from './catalogueContext'
import { loupeMedia, type LoupeMedia } from './media'

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

/** D90 (B10): a clip plays in a <video>, a spoken line in an <audio> under its thumbnail — never an <img> of a file it cannot show. */
function Playable({ m }: { m: LoupeMedia }) {
  if (m.kind === 'video') return <video key={m.src} className="loupe-media" src={m.src} poster={m.poster} controls preload="metadata" aria-label="the clip" />
  if (m.kind === 'audio') return <div className="loupe-audio"><img src={m.poster} alt="" draggable={false} /><audio key={m.src} src={m.src} controls preload="metadata" aria-label="the spoken line" /></div>
  return null
}

export function Loupe({ asset }: { asset: Asset }) {
  const c = useCat()
  const order = c.visibleOrder()
  const idx = order.indexOf(asset.id)
  // memoised: a fresh object per render would recreate `fit`, whose mount effect sets state → an endless re-render loop
  const dims = useMemo(() => (asset.w && asset.h ? { w: asset.w, h: asset.h } : null), [asset.w, asset.h])
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  const m = loupeMedia(asset)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, textarea')) return
      if (e.key === 'Escape') c.openLoupe(null)
      else if (e.ctrlKey && handleKeyFor('catalogue', e)) return                     // D72: Ctrl+0 / Ctrl+1 are cat.loupe.fit / .one
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') handleKeyFor('catalogue', e)
      else if (!e.ctrlKey && !e.metaKey && !e.altKey) { if (!c.selected.includes(asset.id)) c.select(asset.id, 'single'); handleKeyFor('catalogue', e) }
      else return
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [c, idx, order, fit, one, asset.id])
  useEffect(() => { catView.fit = fit; catView.one = one; return () => { catView.fit = undefined; catView.one = undefined } }, [fit, one])   // D72
  const pinned = c.compare.indexOf(asset.id) + 1
  const subItems = (m: MenuItem): MenuItem[] => ('items' in m ? m.items : [])
  return (
    <div className="loupe" tabIndex={0} onContextMenu={(e) => { if (!c.selected.includes(asset.id)) c.select(asset.id, 'single'); showMenu(e, tileMenu()) }}>
      <div className={`view${m.zoom ? '' : ' play'}`} ref={ref} {...(m.zoom ? handlers : {})}>
        {m.zoom ? <img src={m.src} alt="" style={style(xf)} draggable={false} /> : <Playable m={m} />}
      </div>
      <div className="facts">
        <CommandButton id="cat.prev" /><span>{idx + 1} / {order.length}</span><CommandButton id="cat.next" />
        <span>{asset.model_id ?? asset.suite}</span>
        {asset.kind !== 'audio' && <span>{asset.w}×{asset.h}</span>}
        {asset.duration_s ? <span>{asset.duration_s} s</span> : null}
        <span>seed {asset.seed ?? '—'}</span>
        <span>{new Date(asset.created_at).toLocaleString()}</span>
        <span>{asset.state !== 'none' ? asset.state : ''} {asset.rating ? '★'.repeat(asset.rating) : ''}</span>
        <span className="spacer" />
        {m.zoom ? <><span>{Math.round(xf.s * 100)}%</span><CommandButton id="cat.loupe.fit" text label="Fit" /><CommandButton id="cat.loupe.one" text label="1:1" /></>
          : m.kind === 'video' && m.clipId ? <CommandButton id="cat.animate" text label="Play in Animate" /> : null}
        <button className="quiet" onClick={() => c.openLoupe(null)}>Close (Esc)</button>
      </div>
      {/* D71 (P11): the loupe is the send-to hub — every verb of the tile menu on one bar; the secondary ones fold into More when narrow.
          The verbs act on the selection, so a press here selects the loupe's asset first (as its right-click and keys do). */}
      <div className="hub" role="toolbar" aria-label="Send this image" onPointerDownCapture={() => { if (!c.selected.includes(asset.id) || c.selected.length > 1) c.select(asset.id, 'single') }}>
        <CommandRow ids={['cat.keep', 'cat.reject']} />
        <span className="secondary"><CommandButton id="cat.unstate" /></span>
        <span className="secondary"><MenuButton label="Rate" icon={Star} items={() => subItems(rateMenu())} /></span>
        <span className="gap" />
        <CommandButton id="cat.edit" text label="Edit" />
        <CommandButton id="cat.reference" text label="Reference" />
        <CommandButton id="cat.start.angle" text label="New angle" />
        <MenuButton label="Animate" icon={Film} text items={() => [{ cmd: 'cat.animate', label: 'As the start frame' }, { cmd: 'cat.animateEnd', label: 'As the end frame' }]} />
        <span className="gap secondary" />
        <span className="secondary"><CommandRow ids={['cat.rerun', 'cat.variations', 'cat.duplicate']} /></span>
        <span className="secondary"><MenuButton label="Move to group" icon={FolderInput} items={() => subItems(moveToMenu())} /></span>
        <span className="secondary"><CommandRow ids={['cat.lineage', 'cat.reveal']} /></span>
        <span className="secondary"><CommandButton id="cat.pin" text label={pinned ? `Unpin C${pinned}` : 'Pin'} /></span>
        <span className="spacer" />
        <MenuButton label="More" icon={Ellipsis} items={tileMenu} />
      </div>
    </div>
  )
}

export function Compare({ assets }: { assets: Asset[] }) {
  const c = useCat()
  const [wipe, setWipe] = useState(0.5)
  const [diff, setDiff] = useState(false)
  const [two, setTwo] = useState(true)
  const w0 = assets[0]?.w, h0 = assets[0]?.h
  const dims = useMemo(() => (w0 && h0 ? { w: w0, h: h0 } : null), [w0, h0])
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  const shown = two ? assets.slice(0, 2) : assets.slice(0, 4)
  const swap = () => { if (assets.length >= 2) { c.clearCompare(); [assets[1], assets[0], ...assets.slice(2)].forEach((a) => c.togglePin(a.id)) } }
  useEffect(() => { catView.swap = swap; return () => { catView.swap = undefined } })                // D72: cat.compare.swap (Tab, the Swap button)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, textarea')) return
      if (e.key === 'Escape') c.setCompareOpen(false)
      else if (e.key === 'Tab') { e.preventDefault(); e.stopImmediatePropagation(); runCommand('cat.compare.swap') }   // D72: before the global Tab (focus mode)
    }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  })
  const cols = shown.length <= 2 ? shown.length : 2
  return (
    <div className="compare">
      <div className="cells" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {shown.map((a, i) => {
          const m = loupeMedia(a), base = loupeMedia(shown[0])
          const dif = diff && i > 0 && m.zoom && base.zoom, wiped = two && i === 1 && !diff && m.zoom && base.zoom   // D90 (B10): difference and wipe are for two images
          return (
            <div key={a.id} className={`cell${dif ? ' diff' : ''}`} ref={i === 0 ? ref : undefined} {...(m.zoom ? handlers : {})}>
              {dif && <img src={base.src} alt="" style={style(xf)} draggable={false} />}
              {m.zoom ? <img className={dif ? 'over' : ''} src={m.src} alt="" style={{ ...style(xf), ...(wiped ? { clipPath: `inset(0 0 0 ${wipe * 100}%)` } : {}) }} draggable={false} /> : <Playable m={m} />}
              {wiped && <div className="wipe" style={{ left: `${wipe * 100}%` }} />}
              <span className="tag">{String.fromCharCode(65 + i)} · {a.model_id ?? a.suite} · seed {a.seed ?? '—'}</span>
            </div>
          )
        })}
      </div>
      <div className="bar">
        <span>Compare {shown.length}-up · zoom/pan locked</span>
        {two && !diff && <><span>wipe</span><input type="range" min={0} max={1} step={0.01} value={wipe} onChange={(e) => setWipe(Number(e.target.value))} /></>}
        <label><input type="checkbox" checked={diff} onChange={(e) => setDiff(e.target.checked)} /> difference</label>
        <button className="quiet" onClick={() => setTwo(!two)} disabled={assets.length < 3}>{two ? '4-up' : '2-up'}</button>
        <CommandButton id="cat.compare.swap" text label="Swap" />
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
