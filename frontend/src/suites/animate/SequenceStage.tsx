// P17 (D83): the Sequence stage — the preview (Mediabunny sinks per clip, the frame the lane shows at the playhead, two frames mixed
// mid-dissolve), the transport, and the lane itself: a ruler, one block per clip (px per tick), the dissolve shaded, trim handles at
// both edges, a dissolve grip, the playhead; Ctrl+wheel zooms. Lifted from the E13 view (frontend/src/spikes/e13Timeline.ts).
import { ALL_FORMATS, CanvasSink, Input, UrlSource } from 'mediabunny'
import { useEffect, useMemo, useRef, type PointerEvent as ReactPointerEvent } from 'react'
import { api } from '../../api/client'
import type { Clip } from '../../api/types'
import { CommandRow } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { useAnimate } from './animateStore'
import { at, duration, starts, tc, ticks, type Lane } from './lane'
import { laneMenu } from './sequenceCommands'
import { useSequence } from './sequenceStore'

/** One Mediabunny sink per clip proxy, opened on demand and kept for the stage's life. */
class Sinks {
  private sinks = new Map<string, Promise<CanvasSink | null>>()
  private inputs: Input[] = []
  get(clip: Clip): Promise<CanvasSink | null> {
    let p = this.sinks.get(clip.id)
    if (!p) {
      const input = new Input({ source: new UrlSource(api.fileUrl(`/clips/${clip.id}/proxy.mp4`)), formats: ALL_FORMATS })
      this.inputs.push(input)
      p = input.getPrimaryVideoTrack().then(async (t) => (t && (await t.canDecode()) ? new CanvasSink(t, { poolSize: 3 }) : null)).catch(() => null)
      this.sinks.set(clip.id, p)
    }
    return p
  }
  dispose(): void { this.inputs.forEach((i) => i.dispose()); this.inputs = []; this.sinks.clear() }
}

function Preview({ lane, w, h, byId }: { lane: Lane; w: number; h: number; byId: Map<string, Clip> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const sinksRef = useRef<Sinks | null>(null)
  const seqRef = useRef(0)
  const playhead = useSequence((s) => s.playhead)
  useEffect(() => { sinksRef.current = new Sinks(); return () => { sinksRef.current?.dispose(); sinksRef.current = null } }, [])
  useEffect(() => {
    const c = canvasRef.current, sinks = sinksRef.current
    if (!c || !sinks) return
    const what = at(lane, playhead, starts(lane))
    const seq = ++seqRef.current
    const frameOf = async (i: number, local: number) => {
      const clip = byId.get(lane.clips[i].source)
      if (!clip) return null
      const s = await sinks.get(clip)
      const wrapped = s ? await s.getCanvas((local + 0.5) / clip.fps) : null
      return wrapped?.canvas ?? null
    }
    void (async () => {
      const ctx = c.getContext('2d')
      if (!ctx) return
      if (!what) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, c.width, c.height); return }
      const a = await frameOf(what.a.i, what.a.local)
      const b = what.b ? await frameOf(what.b.i, what.b.local) : null
      if (seq !== seqRef.current) return
      ctx.globalAlpha = 1
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, c.width, c.height)
      if (a) ctx.drawImage(a, 0, 0, c.width, c.height)
      if (b) { ctx.globalAlpha = what.mix ?? 0; ctx.drawImage(b, 0, 0, c.width, c.height); ctx.globalAlpha = 1 }
    })()
  }, [lane, playhead, byId])
  return <canvas ref={canvasRef} className="anim-canvas seq-canvas" width={w} height={h} />
}

/** rAF playback at the lane's fps; stops at the end. */
function usePlayback(lane: Lane | null) {
  const playing = useSequence((s) => s.playing)
  useEffect(() => {
    if (!playing || !lane) return
    const d = duration(lane)
    let raf = 0
    let last = performance.now()
    let acc = 0
    const step = (t: number) => {
      acc += (t - last) * lane.fps / 1000; last = t
      const n = Math.floor(acc)
      if (n > 0) {
        acc -= n
        const s = useSequence.getState()
        if (s.playhead + n >= d - 1) { s.setPlayhead(d - 1); s.togglePlay(false); return }
        s.setPlayhead(s.playhead + n)
      }
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [playing, lane])
}

function LaneView({ lane, byId }: { lane: Lane; byId: Map<string, Clip> }) {
  const ref = useRef<HTMLDivElement>(null)
  const ppf = useSequence((s) => s.pxPerFrame)
  const selected = useSequence((s) => s.selected)
  const playhead = useSequence((s) => s.playhead)
  const s = starts(lane)
  const total = duration(lane)
  const tickAt = (clientX: number) => { const r = ref.current!.getBoundingClientRect(); return Math.max(0, Math.min(total - 1, Math.round((clientX - r.left + ref.current!.scrollLeft) / ppf))) }
  const scrub = (e: ReactPointerEvent) => {
    const sq = useSequence.getState()
    sq.togglePlay(false); sq.setPlayhead(tickAt(e.clientX))
    const move = (ev: PointerEvent) => sq.setPlayhead(tickAt(ev.clientX))
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  /** Drag a clip edge: the pointer's travel in ticks becomes source frames at the clip's own rate. */
  const trimDrag = (i: number, edge: 'in' | 'out') => (e: ReactPointerEvent) => {
    e.stopPropagation(); e.preventDefault()
    const x0 = e.clientX
    const c = lane.clips[i]
    const clip = byId.get(c.source)
    const rate = (c.fps ?? lane.fps) / lane.fps
    let applied = 0
    const move = (ev: PointerEvent) => {
      const want = Math.round(((ev.clientX - x0) / ppf) * rate)
      if (want !== applied) { useSequence.getState().trimClip(i, edge, want - applied, clip?.frames ?? c.out); applied = want }
    }
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    useSequence.getState().select(i)
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const dissolveDrag = (i: number) => (e: ReactPointerEvent) => {
    e.stopPropagation(); e.preventDefault()
    const x0 = e.clientX, start = lane.overlaps[i]
    const move = (ev: PointerEvent) => useSequence.getState().setDissolve(i, start - Math.round((ev.clientX - x0) / ppf))
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    useSequence.getState().select(i)
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const major = Math.max(1, Math.round(lane.fps * (ppf < 1 ? 5 : ppf < 3 ? 2 : 1)))
  const marks: number[] = []
  for (let f = 0; f <= total; f += major) marks.push(f)
  return (
    <div className="seq-lane-wrap" ref={ref} onWheel={(e) => { if (e.ctrlKey) { e.preventDefault(); useSequence.getState().zoom(e.deltaY < 0 ? 1.25 : 0.8) } }}
      onContextMenu={(e) => { e.preventDefault(); showMenu(e, laneMenu(false)) }}>
      <div className="seq-ruler" style={{ width: Math.max(1, total * ppf) }} onPointerDown={scrub}>
        {marks.map((f) => <div key={f} className="tick" style={{ left: f * ppf }}><span>{tc(f, lane.fps)}</span></div>)}
      </div>
      <div className="seq-lane" style={{ width: Math.max(1, total * ppf) }} onPointerDown={(e) => { if (e.target === e.currentTarget) scrub(e) }}>
        {lane.clips.map((c, i) => {
          const ov = i > 0 ? lane.overlaps[i] : 0
          const clip = byId.get(c.source)
          const missing = !clip
          return (
            <div key={c.id} className={`seq-clip${selected === i ? ' selected' : ''}${missing ? ' missing' : ''}`}
              style={{ left: s[i] * ppf, width: ticks(lane, c) * ppf, zIndex: i }}
              title={`${c.source} · frames ${c.in}–${c.out}${c.fps ? ` @ ${c.fps} fps` : ''}${missing ? ' — clip missing from the project' : ''}`}
              onPointerDown={(e) => { e.stopPropagation(); useSequence.getState().select(i); useSequence.getState().togglePlay(false); useSequence.getState().setPlayhead(tickAt(e.clientX)) }}
              onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); useSequence.getState().select(i); showMenu(e, laneMenu(true)) }}>
              {ov > 0 && <i className="seq-ov" style={{ width: ov * ppf }} title={`dissolve · ${ov} frames (drag to change)`} onPointerDown={dissolveDrag(i)} />}
              <b>{clip ? `${clip.model_id.split('-')[0]} · ${c.out - c.in}f` : c.source}</b>
              <span className="seq-h l" onPointerDown={trimDrag(i, 'in')} title="trim in (drag)" />
              <span className="seq-h r" onPointerDown={trimDrag(i, 'out')} title="trim out (drag)" />
            </div>
          )
        })}
        <div className="seq-play" style={{ left: playhead * ppf }} />
      </div>
    </div>
  )
}

export function SequenceStage() {
  const current = useSequence((s) => s.current)
  const lane = useSequence((s) => s.lane)
  const playhead = useSequence((s) => s.playhead)
  const playing = useSequence((s) => s.playing)
  const clips = useAnimate((s) => s.clips)
  const byId = useMemo(() => new Map(clips.map((c) => [c.id, c])), [clips])
  usePlayback(lane)
  if (!current || !lane) {
    return <div className="anim-empty"><h2>Sequence</h2>pick a sequence in the panel, or make one — clips from the bin go on one lane; a clip dragged over the one before it dissolves.</div>
  }
  const total = duration(lane)
  const what = at(lane, playhead, starts(lane))
  return (
    <div className="anim-stage seq-stage">
      <div className="anim-view">
        {lane.clips.length ? <Preview lane={lane} w={current.w} h={current.h} byId={byId} /> : <div className="anim-empty">an empty lane — add a clip from the Clips bin (the panel), or <b>Add the current clip</b></div>}
      </div>
      <div className="transport">
        <CommandRow ids={['anim.seq.home', 'anim.seq.stepBack', 'anim.seq.play', 'anim.seq.stepForward', 'anim.seq.end']} labels={{ 'anim.seq.play': playing ? 'Pause' : 'Play' }} />
        <span className="counter">{tc(playhead, lane.fps)} / {tc(total, lane.fps)} · tick {playhead}{what ? ` · ${lane.clips[what.a.i].source.replace(/^clp_/, '')} f${what.a.local}${what.b ? ` ⇢ ${lane.clips[what.b.i].source.replace(/^clp_/, '')} f${what.b.local} (${Math.round((what.mix ?? 0) * 100)} %)` : ''}` : ''}</span>
        <span className="spacer" />
        <CommandRow ids={['anim.seq.undo', 'anim.seq.redo', 'gap', 'anim.seq.zoomOut', 'anim.seq.zoomIn']} />
      </div>
      <LaneView lane={lane} byId={byId} />
    </div>
  )
}
