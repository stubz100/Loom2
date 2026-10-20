// AP1 thin (proto01_animate 20 §2, D114): Animate's Final level — the composition's frames in the viewer, scrubbed by the slider and
// the transport (commands, D32), played from the page's cache, the chip saying what is shown. The editing controls come with AE2.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { CommandRow } from '../../frame/CommandButton'
import { useSession } from '../../store/session'
import { fmtTime } from './animateStore'
import { chipText, useComposition } from './compositionStore'

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
  const img = useRef<HTMLImageElement>(null)
  const [drag, setDrag] = useState<{ x0: number; y0: number; dx: number; dy: number } | null>(null)
  useEffect(() => { const t = window.setInterval(() => void useComposition.getState().tick(), 250); return () => window.clearInterval(t) }, [])
  useEffect(() => () => useComposition.getState().togglePlay(false), [])
  // AE2: drag the selected layer in the viewer — one `layer.nudge` in comp pixels on release (her matte follows: it is parented to her)
  const onDown = (e: ReactPointerEvent<HTMLImageElement>) => {
    if (selected === null || e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    setDrag({ x0: e.clientX, y0: e.clientY, dx: 0, dy: 0 })
  }
  const onMove = (e: ReactPointerEvent<HTMLImageElement>) => { if (drag) setDrag({ ...drag, dx: e.clientX - drag.x0, dy: e.clientY - drag.y0 }) }
  const onUp = (e: ReactPointerEvent<HTMLImageElement>) => {
    if (!drag) return
    const el = img.current
    const scale = el && final ? final.size.w / Math.max(1, el.clientWidth) : 1
    const dx = Math.round(drag.dx * scale), dy = Math.round(drag.dy * scale)
    setDrag(null)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    if (dx || dy) void useComposition.getState().nudge(dx, dy)
  }
  if (!finalId || !final) {
    return <div className="anim-stage final-viewer"><div className="anim-view"><div className="anim-empty"><h2>Final</h2>no final open — in the Shot section: make the final shot, assemble it, <b>Make the composition</b>, then <b>Open in Final</b></div></div></div>
  }
  if (!comp) {
    return <div className="anim-stage final-viewer" data-final={final.id}><div className="anim-view"><div className="anim-empty"><h2>{final.name}</h2>no composition yet — assemble the shot, then <b>Make the composition</b> in the Shot section</div></div></div>
  }
  const n = final.frames
  return (
    <div className="anim-stage final-viewer" data-final={final.id}>
      <div className="anim-view final-view">
        {shown ? <img ref={img} className={`final-frame ${selected !== null ? 'movable' : ''}`} src={shown.url} alt="" draggable={false} data-side={shown.side}
          title={selected !== null ? `Drag to move ${selName ?? 'the selected layer'}` : undefined} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={() => setDrag(null)} />
          : <div className="anim-overlay">loading the first frame…</div>}
        {drag && (drag.dx || drag.dy) ? <div className="drag-ghost" style={{ transform: `translate(${drag.dx}px, ${drag.dy}px)` }}><span>{selName}: {Math.round(drag.dx)}, {Math.round(drag.dy)} px</span></div> : null}
        <span className="final-chip" title="What is on screen: the size shown (½ while scrubbing, full at rest) and how much of the shot is cached for playback">{chipText({ shown, filled, final, fetching }, busy)}</span>
        {error && <div className="anim-overlay err">preview: {error}</div>}
      </div>
      <div className="transport final-transport">
        <CommandRow ids={['anim.final.home', 'anim.final.stepBack', 'anim.final.play', 'anim.final.stepForward', 'anim.final.end']} />
        <span className="counter">frame {frame} / {n - 1} · {fmtTime(frame, final.rate)}</span>
        <input className="final-scrub" type="range" min={0} max={n - 1} step={1} value={frame} aria-label="frame"
          onChange={(e) => useComposition.getState().setFrame(Number(e.target.value))} />
        <span className="hint" data-comp-state>composition · revision {comp.revision}{comp.stale ? ' · stale: the final changed, make it again' : ''}{comp.clip_id ? ` · rendered at revision ${comp.rendered_revision}` : ''}</span>
      </div>
    </div>
  )
}
