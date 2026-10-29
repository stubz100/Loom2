// B1 (D159, 11 §3): the Bin's large view and its compare. The large view shows the selected thing over the grid — a picture with the loupe's
// zoom and pan (Ctrl+wheel about the pointer, a drag pans, Fit, 1:1), a clip or a sound playing — with the previous and the next of the home;
// Esc or Space closes it. Compare puts the two to four pinned things side by side, zoom and pan locked together, with a wipe and a
// difference for two pictures; Tab swaps the first two.
import { useEffect, useMemo, useState } from 'react'
import type { Asset } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { handleKeyFor } from '../../frame/commands'
import { loupeMedia } from '../../frame/loupe/media'
import { Playable, useZoomPan, xfStyle } from '../../frame/loupe/view'
import { loupeView } from './binCommands'
import { useBin } from './binStore'

/** The window's keys while a view is open: Esc closes; the Bin's keys (← →, Ctrl+0, Tab, Space) run their commands. */
function useViewKeys(close: () => void): void {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, textarea, .modal')) return
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return }
      if (handleKeyFor('bin', e)) { e.preventDefault(); e.stopPropagation() }
    }
    window.addEventListener('keydown', h, true)
    return () => window.removeEventListener('keydown', h, true)
  }, [close])
}

export function BinLoupe() {
  const viewing = useBin((s) => s.viewing)
  const it = useBin((s) => s.items.find((x) => x.asset.id === s.selected))
  const index = useBin((s) => s.items.findIndex((x) => x.asset.id === s.selected))
  const count = useBin((s) => s.items.length)
  if (!viewing || !it) return null
  return <LoupeOf a={it.asset} index={index} count={count} />
}

function LoupeOf({ a, index, count }: { a: Asset; index: number; count: number }) {
  const pinned = useBin((s) => s.pins.some((x) => x.id === a.id))
  const dims = useMemo(() => (a.w && a.h ? { w: a.w, h: a.h } : null), [a.w, a.h])
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  const m = loupeMedia(a)
  useViewKeys(closeView)
  useEffect(() => { loupeView.fit = fit; loupeView.one = one; return () => { loupeView.fit = undefined; loupeView.one = undefined } }, [fit, one])
  return (
    <div className="loupe b-loupe" data-testid="bin-loupe">
      <div className={`view${m.zoom ? '' : ' play'}`} ref={ref} {...(m.zoom ? handlers : {})} onDoubleClick={closeView}>
        {m.zoom ? <img src={m.src} alt="" style={xfStyle(xf)} draggable={false} /> : <Playable m={m} />}
      </div>
      <div className="facts">
        <CommandButton id="bin.loupe.prev" /><span>{index + 1} / {count}</span><CommandButton id="bin.loupe.next" />
        <span>{a.model_id ?? a.suite}</span>
        {a.kind !== 'audio' && a.w ? <span>{a.w}×{a.h}</span> : null}
        {a.duration_s ? <span>{a.duration_s} s</span> : null}
        {a.seed != null && <span>seed {a.seed}</span>}
        <span className="spacer" />
        {m.zoom && <><span>{Math.round(xf.s * 100)}%</span><CommandButton id="bin.loupe.fit" text /><CommandButton id="bin.loupe.one" text /></>}
        <CommandButton id="bin.item.pin" text label={pinned ? 'Unpin' : 'Pin'} />
        <CommandButton id="bin.item.detach" text />
        <button className="quiet" onClick={closeView}>Back (Esc)</button>
      </div>
    </div>
  )
}
const closeView = () => useBin.getState().view(false)

export function BinCompare() {
  const comparing = useBin((s) => s.comparing)
  const pins = useBin((s) => s.pins)
  if (!comparing || pins.length < 2) return null
  return <CompareOf assets={pins} />
}

const closeCompare = () => useBin.getState().compare(false)

function CompareOf({ assets }: { assets: Asset[] }) {
  const [wipe, setWipe] = useState(0.5)
  const [diff, setDiff] = useState(false)
  const [two, setTwo] = useState(true)
  const w0 = assets[0]?.w, h0 = assets[0]?.h
  const dims = useMemo(() => (w0 && h0 ? { w: w0, h: h0 } : null), [w0, h0])
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  const shown = two ? assets.slice(0, 2) : assets.slice(0, 4)
  useViewKeys(closeCompare)
  const cols = shown.length <= 2 ? shown.length : 2
  return (
    <div className="compare b-compare" data-testid="bin-compare">
      <div className="cells" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {shown.map((a, i) => {
          const m = loupeMedia(a), base = loupeMedia(shown[0])
          const dif = diff && i > 0 && m.zoom && base.zoom, wiped = two && i === 1 && !diff && m.zoom && base.zoom   // D90 (B10): for two pictures
          return (
            <div key={a.id} className={`cell${dif ? ' diff' : ''}`} ref={i === 0 ? ref : undefined} {...(m.zoom ? handlers : {})}>
              {dif && <img src={base.src} alt="" style={xfStyle(xf)} draggable={false} />}
              {m.zoom ? <img className={dif ? 'over' : ''} src={m.src} alt="" style={{ ...xfStyle(xf), ...(wiped ? { clipPath: `inset(0 0 0 ${wipe * 100}%)` } : {}) }} draggable={false} /> : <Playable m={m} />}
              {wiped && <div className="wipe" style={{ left: `${wipe * 100}%` }} />}
              <span className="tag">{String.fromCharCode(65 + i)} · {a.model_id ?? a.suite}{a.seed != null ? ` · seed ${a.seed}` : ''}</span>
            </div>
          )
        })}
      </div>
      <div className="bar">
        <span>{shown.length}-up</span>
        {two && !diff && <><span>wipe</span><input type="range" min={0} max={1} step={0.01} value={wipe} onChange={(e) => setWipe(Number(e.target.value))} aria-label="wipe" /></>}
        <label><input type="checkbox" checked={diff} onChange={(e) => setDiff(e.target.checked)} /> difference</label>
        <button className="quiet" onClick={() => setTwo(!two)} disabled={assets.length < 3}>{two ? '4-up' : '2-up'}</button>
        <CommandButton id="bin.compare.swap" text label="Swap" />
        <span className="spacer" />
        <span>{Math.round(xf.s * 100)}%</span>
        <button className="quiet" onClick={fit}>Fit</button>
        <button className="quiet" onClick={one}>1:1</button>
        <CommandButton id="bin.unpinAll" text />
        <button className="quiet" onClick={closeCompare}>Back (Esc)</button>
      </div>
    </div>
  )
}
