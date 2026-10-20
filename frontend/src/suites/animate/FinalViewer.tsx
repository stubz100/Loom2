// AP1 thin (proto01_animate 20 §2, D114): Animate's Final level — the composition's frames in the viewer, scrubbed by the slider and
// the transport (commands, D32), played from the page's cache, the chip saying what is shown. The editing controls come with AE2.
import { useEffect } from 'react'
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
  useEffect(() => { const t = window.setInterval(() => void useComposition.getState().tick(), 250); return () => window.clearInterval(t) }, [])
  useEffect(() => () => useComposition.getState().togglePlay(false), [])
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
        {shown ? <img className="final-frame" src={shown.url} alt="" draggable={false} data-side={shown.side} /> : <div className="anim-overlay">loading the first frame…</div>}
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
