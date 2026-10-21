// AP1 thin / AE2 (proto01_animate 20 §2, D114): Animate's Final level — the composition's frames in the viewer, scrubbed by the slider and
// the transport (commands, D32), played from the page's cache, the chip saying what is shown. A drag on the frame moves the selected layer
// (one `layer.nudge`), or draws a mask with the rectangle / ellipse tool (AE2c, one `layer.addMask`). The lanes under the transport are
// the layers' bars (AE2d): dragged to move, their ends to trim, Alt-drag to slip — one `layer.timing` / `layer.slip` on release; the
// selected layer's keys sit on its bar; a click on a lane selects the layer.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { CommandRow } from '../../frame/CommandButton'
import { useSession } from '../../store/session'
import { fmtTime } from './animateStore'
import { chipText, snapTime, useComposition, type CompLayer } from './compositionStore'

interface Drag { x0: number; y0: number; dx: number; dy: number; box: DOMRect; vbox: DOMRect }                 // the frame's and the view's boxes at the press
interface LaneDrag { id: number; mode: 'move' | 'in' | 'out' | 'slip'; x0: number; dx: number; l: CompLayer; width: number }   // the track's width at the press

export function FinalViewer() {
  const finalId = useComposition((s) => s.finalId)
  const final = useComposition((s) => s.final)
  const comp = useComposition((s) => s.comp)
  const shown = useComposition((s) => s.shown)
  const frame = useComposition((s) => s.frame)
  const filled = useComposition((s) => s.filled)
  const fetching = useComposition((s) => s.fetching)
  const error = useComposition((s) => s.error)
  const busy = useSession((s) => Object.values(s.jobs).some((j) => j.status === 'running'))
  const selected = useComposition((s) => s.selected)
  const selName = useComposition((s) => s.layers.find((l) => l.id === s.selected)?.name)
  const maskTool = useComposition((s) => s.maskTool)
  const before = useComposition((s) => s.before)
  const img = useRef<HTMLImageElement>(null)
  const view = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  useEffect(() => { const t = window.setInterval(() => void useComposition.getState().tick(), 250); return () => window.clearInterval(t) }, [])
  useEffect(() => () => useComposition.getState().togglePlay(false), [])
  // AE2: a drag on the frame — the selected layer moved (one `layer.nudge` in comp pixels on release; her matte follows, parented to her),
  // or, with a mask tool on, a rectangle or ellipse mask drawn (AE2c)
  const onDown = (e: ReactPointerEvent<HTMLImageElement>) => {
    if (selected === null || e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    const box = e.currentTarget.getBoundingClientRect()
    setDrag({ x0: e.clientX, y0: e.clientY, dx: 0, dy: 0, box, vbox: view.current?.getBoundingClientRect() ?? box })
  }
  const onMove = (e: ReactPointerEvent<HTMLImageElement>) => { if (drag) setDrag({ ...drag, dx: e.clientX - drag.x0, dy: e.clientY - drag.y0 }) }
  const onUp = (e: ReactPointerEvent<HTMLImageElement>) => {
    if (!drag) return
    const el = img.current
    const scale = el && final ? final.size.w / Math.max(1, el.clientWidth) : 1
    setDrag(null)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    const cp = useComposition.getState()
    if (maskTool !== 'off') {
      const x = Math.min(drag.x0, drag.x0 + drag.dx) - drag.box.left, y = Math.min(drag.y0, drag.y0 + drag.dy) - drag.box.top
      const w = Math.abs(drag.dx), h = Math.abs(drag.dy)
      if (w >= 4 && h >= 4) { void cp.addMask([Math.round(x * scale), Math.round(y * scale), Math.round(w * scale), Math.round(h * scale)], maskTool); cp.setMaskTool('off') }
      return
    }
    const dx = Math.round(drag.dx * scale), dy = Math.round(drag.dy * scale)
    if (dx || dy) void cp.nudge(dx, dy)
  }
  if (!finalId || !final) {
    return <div className="anim-stage final-viewer"><div className="anim-view"><div className="anim-empty"><h2>Final</h2>no final open — in the Shot section: make the final shot, assemble it, <b>Make the composition</b>, then <b>Open in Final</b></div></div></div>
  }
  if (!comp) {
    return <div className="anim-stage final-viewer" data-final={final.id}><div className="anim-view"><div className="anim-empty"><h2>{final.name}</h2>no composition yet — assemble the shot, then <b>Make the composition</b> in the Shot section</div></div></div>
  }
  const n = final.frames
  const ghost = drag && maskTool !== 'off'
    ? { left: Math.min(drag.x0, drag.x0 + drag.dx) - drag.vbox.left, top: Math.min(drag.y0, drag.y0 + drag.dy) - drag.vbox.top, width: Math.abs(drag.dx), height: Math.abs(drag.dy) } : null
  return (
    <div className="anim-stage final-viewer" data-final={final.id}>
      <div ref={view} className={`anim-view final-view${maskTool !== 'off' ? ' masking' : ''}`}>
        {shown ? <img ref={img} className={`final-frame ${selected !== null ? 'movable' : ''}`} src={before ?? shown.url} alt="" draggable={false} data-side={shown.side} data-before={before ? 'true' : undefined}
          title={selected !== null ? (maskTool !== 'off' ? `Drag to draw the ${maskTool === 'rect' ? 'rectangle' : 'ellipse'} mask on ${selName ?? 'the layer'}` : `Drag to move ${selName ?? 'the selected layer'}`) : undefined}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={() => setDrag(null)} />
          : <div className="anim-overlay">loading the first frame…</div>}
        {ghost ? <div className={`mask-ghost ${maskTool}`} style={ghost} /> : drag && (drag.dx || drag.dy) ? <div className="drag-ghost" style={{ transform: `translate(${drag.dx}px, ${drag.dy}px)` }}><span>{selName}: {Math.round(drag.dx)}, {Math.round(drag.dy)} px</span></div> : null}
        <span className="final-chip" title="What is on screen: the size shown (½ while scrubbing, full at rest) and how much of the shot is cached for playback">{before ? 'before · ' : ''}{chipText({ shown, filled, final, fetching }, busy)}</span>
        {error && <div className="anim-overlay err">preview: {error}</div>}
      </div>
      <div className="transport final-transport">
        <CommandRow ids={['anim.final.home', 'anim.final.stepBack', 'anim.final.play', 'anim.final.stepForward', 'anim.final.end', 'gap', 'anim.final.before']} active={before ? 'anim.final.before' : undefined} />
        <span className="counter">frame {frame} / {n - 1} · {fmtTime(frame, final.rate)}</span>
        <input className="final-scrub" type="range" min={0} max={n - 1} step={1} value={frame} aria-label="frame"
          onChange={(e) => useComposition.getState().setFrame(Number(e.target.value))} />
        <span className="hint" data-comp-state>composition · revision {comp.revision}{comp.stale ? ' · stale: the final changed, make it again' : ''}{comp.clip_id ? ` · rendered at revision ${comp.rendered_revision}` : ''}</span>
      </div>
      <Lanes rate={final.rate} duration={n / final.rate} />
    </div>
  )
}

/** AE2d: the layers' bars over the shot — dragged to move, the ends to trim, Alt-drag to slip; the selected layer's keys; the playhead. */
function Lanes({ rate, duration }: { rate: number; duration: number }) {
  const layers = useComposition((s) => s.layers)
  const selected = useComposition((s) => s.selected)
  const frame = useComposition((s) => s.frame)
  const keysOf = useComposition((s) => s.keysOf)
  const busy = useComposition((s) => s.busy)
  const track = useRef<HTMLDivElement>(null)
  const [ld, setLd] = useState<LaneDrag | null>(null)
  const pct = (t: number) => `${(Math.max(0, Math.min(duration, t)) / duration) * 100}%`
  const secOf = (px: number, width: number) => (px / Math.max(1, width)) * duration
  const step = 1 / rate
  const start = (e: ReactPointerEvent<HTMLElement>, l: CompLayer, mode: LaneDrag['mode']) => {
    if (e.button !== 0 || busy) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    useComposition.getState().select(l.id)
    setLd({ id: l.id, mode: e.altKey && mode === 'move' ? 'slip' : mode, x0: e.clientX, dx: 0, l, width: track.current?.clientWidth ?? 1 })
  }
  const move = (e: ReactPointerEvent<HTMLElement>) => { if (ld) setLd({ ...ld, dx: e.clientX - ld.x0 }) }
  const end = () => {
    if (!ld) return
    const d = snapTime(secOf(ld.dx, ld.width), rate)
    setLd(null)
    if (Math.abs(d) < step / 2) return
    const cp = useComposition.getState(), l = ld.l
    if (ld.mode === 'move') void cp.setTiming(l.id, { delta: d })
    else if (ld.mode === 'in') void cp.setTiming(l.id, { in: Math.max(0, Math.min(l.out - step, l.in + d)) })
    else if (ld.mode === 'out') void cp.setTiming(l.id, { out: Math.max(l.in + step, Math.min(duration, l.out + d)) })
    else void cp.slip(l.id, d)
  }
  const keyTimes = selected === null ? [] : Array.from(new Set(Object.values(keysOf).flat().map((k) => Math.round(k.time * rate) / rate)))
  return (
    <div className="final-lanes" role="list" aria-label="layers over time" onPointerMove={move} onPointerUp={end} onPointerCancel={() => setLd(null)}>
      {layers.map((l, i) => {
        const d = ld && ld.id === l.id ? snapTime(secOf(ld.dx, ld.width), rate) : 0
        const lin = ld?.id === l.id && (ld.mode === 'move' || ld.mode === 'in') ? l.in + d : l.in
        const lout = ld?.id === l.id && (ld.mode === 'move' || ld.mode === 'out') ? l.out + d : l.out
        const sel = selected === l.id
        return (
          <div key={l.id} className={`lane${sel ? ' selected' : ''}`} data-lane={l.id} role="listitem" onClick={() => useComposition.getState().select(sel ? null : l.id)}>
            <span className="lane-name" title={l.name}>{l.name}</span>
            <div className="lane-track" ref={i === 0 ? track : undefined}>
              <div className={`bar${ld?.id === l.id ? ' dragging' : ''}`} style={{ left: pct(lin), width: `calc(${pct(lout)} - ${pct(lin)})` }}
                title={`${l.name}: ${lin.toFixed(2)}–${lout.toFixed(2)} s · drag to move, the ends to trim, Alt-drag to slip`} onPointerDown={(e) => start(e, l, 'move')}>
                <span className="h h-in" onPointerDown={(e) => start(e, l, 'in')} />
                <span className="h h-out" onPointerDown={(e) => start(e, l, 'out')} />
                {sel && keyTimes.map((t) => <i key={t} className="key" style={{ left: `${((t - lin) / Math.max(step, lout - lin)) * 100}%` }} title={`key at ${t.toFixed(2)} s`} />)}
              </div>
              <div className="playhead" style={{ left: pct(frame / rate) }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
