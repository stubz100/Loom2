// D121 (proto01_animate 26 §5.1 rule 3, AW2): the one timeline under Animate's viewer, at every level — a ruler with its seconds (a click
// or a drag scrubs), the work area (Clay's range, the clip's in / out) with its two handles, the playhead through every row, and the rows the
// level gives it: Clay a row per camera and keyed object (a motion clip's bake as a bar, single keys as diamonds you drag), Performance the
// clip with its start / end, beats and harvested frames, Final a lane per layer (drag to move, the ends to trim, Alt-drag to slip). Above it
// the one transport: the same command buttons and the frame field at every level, the level's own verbs after them.
import { useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react'
import { CommandRow } from '../../frame/CommandButton'
import { deltaFrames, frameAt, pct, ticks, type Span } from './timelineMath'
import './timeline.css'

export interface TLBar { id: string; from: number; to: number; label?: ReactNode; title?: string; className?: string; style?: CSSProperties; drag?: boolean; data?: Record<string, string> }
export interface TLKey { frame: number; title?: string; className?: string }
export interface TLMarker { frame: number; glyph: string; title: string; className?: string; onClick?: () => void }
export interface TLRow {
  id: string; label: ReactNode; title?: string; selected?: boolean; className?: string; data?: Record<string, string>
  bars?: TLBar[]; keys?: TLKey[]; markers?: TLMarker[]
  onSelect?: () => void; onMenu?: (e: ReactMouseEvent) => void
}
export type BarDrag = 'move' | 'in' | 'out' | 'slip'

interface Props {
  className?: string
  span: Span
  fps: number
  frame: number
  onSeek: (frame: number) => void
  /** The work area (Clay's range, the clip's in / out): a band on the ruler, its ends dragged. */
  work?: { from: number; to: number; title?: string; onChange?: (from: number, to: number) => void } | null
  rows: TLRow[]
  onBarDrag?: (row: string, bar: string, mode: BarDrag, delta: number) => void
  /** A key dragged to another frame (keys are drawn draggable only when this is given). */
  onKeyDrag?: (row: string, from: number, to: number) => void
  onKeyMenu?: (e: ReactMouseEvent, row: string, frame: number) => void
  onMenu?: (e: ReactMouseEvent) => void
  children?: ReactNode
}

type Drag =
  | { kind: 'bar'; row: string; bar: string; mode: BarDrag; x0: number; dx: number; width: number }
  | { kind: 'key'; row: string; frame: number; x0: number; dx: number; width: number }
  | { kind: 'work'; end: 'from' | 'to'; frame: number }

export function Timeline({ className = '', span, fps, frame, onSeek, work, rows, onBarDrag, onKeyDrag, onKeyMenu, onMenu, children }: Props) {
  const ruler = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const moved = useRef(false)                                            // a drag's own click does not select the row
  const at = (clientX: number) => { const r = ruler.current!.getBoundingClientRect(); return frameAt(clientX, r.left, r.width, span) }
  const scrub = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    onSeek(at(e.clientX))
    const move = (ev: PointerEvent) => onSeek(at(ev.clientX))
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const grab = (e: ReactPointerEvent<HTMLElement>, d: Drag) => {
    if (e.button !== 0) return
    e.stopPropagation(); e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    setDrag(d)
  }
  const move = (e: ReactPointerEvent<HTMLElement>) => {
    if (!drag) return
    if (drag.kind === 'work') setDrag({ ...drag, frame: at(e.clientX) })
    else setDrag({ ...drag, dx: e.clientX - drag.x0 })
  }
  const release = (e: ReactPointerEvent<HTMLElement>) => {
    const d = drag
    setDrag(null)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    if (!d) return
    moved.current = d.kind !== 'work' && Math.abs(d.dx) >= 3
    if (d.kind === 'work') {
      if (!work?.onChange) return
      const from = d.end === 'from' ? Math.min(d.frame, work.to - 1) : work.from
      const to = d.end === 'to' ? Math.max(d.frame, work.from + 1) : work.to
      if (from !== work.from || to !== work.to) work.onChange(from, to)
      return
    }
    const df = deltaFrames(d.dx, d.width, span)
    if (d.kind === 'bar') { if (df) onBarDrag?.(d.row, d.bar, d.mode, df); return }
    if (Math.abs(d.dx) < 3) { onSeek(d.frame); return }                       // a click on a key goes to it
    if (df) onKeyDrag?.(d.row, d.frame, Math.max(span[0], d.frame + df))
  }
  const width = (e: ReactPointerEvent<HTMLElement>) => (e.currentTarget.closest('.tl-track') as HTMLElement | null)?.clientWidth ?? 1
  const shown = (row: string, b: TLBar): [number, number] => {
    if (drag?.kind !== 'bar' || drag.row !== row || drag.bar !== b.id) return [b.from, b.to]
    const df = deltaFrames(drag.dx, drag.width, span)
    return drag.mode === 'move' ? [b.from + df, b.to + df] : drag.mode === 'in' ? [Math.min(b.to - 1, b.from + df), b.to] : drag.mode === 'out' ? [b.from, Math.max(b.from + 1, b.to + df)] : [b.from, b.to]
  }
  const keyAt = (row: string, f: number) => (drag?.kind === 'key' && drag.row === row && drag.frame === f ? f + deltaFrames(drag.dx, drag.width, span) : f)
  const wf = work ? (drag?.kind === 'work' && drag.end === 'from' ? Math.min(drag.frame, work.to - 1) : work.from) : 0
  const wt = work ? (drag?.kind === 'work' && drag.end === 'to' ? Math.max(drag.frame, work.from + 1) : work.to) : 0
  const handlers = { onPointerMove: move, onPointerUp: release, onPointerCancel: () => setDrag(null) }
  return (
    <div className={`tl ${className}`} onContextMenu={onMenu}>
      <div className="tl-row tl-ruler-row">
        <span className="tl-label" />
        <div className="tl-track tl-ruler ruler" ref={ruler} onPointerDown={scrub} title="click or drag to scrub">
          {work && <div className="tl-work range" style={{ left: pct(wf, span), width: `calc(${pct(wt, span)} - ${pct(wf, span)})` }} title={work.title} />}
          {ticks(span, fps).map((t) => <div key={t.frame} className={`tick${t.major ? ' major' : ''}`} style={{ left: pct(t.frame, span) }}>{t.label && <span>{t.label}</span>}</div>)}
          {work?.onChange && <>
            <span className="tl-handle handle in" style={{ left: pct(wf, span) }} title={`${work.title ?? 'the work area'}: its start (drag)`} onPointerDown={(e) => grab(e, { kind: 'work', end: 'from', frame: work.from })} {...handlers} />
            <span className="tl-handle handle out" style={{ left: pct(wt, span) }} title={`${work.title ?? 'the work area'}: its end (drag)`} onPointerDown={(e) => grab(e, { kind: 'work', end: 'to', frame: work.to })} {...handlers} />
          </>}
          <div className="tl-head head" style={{ left: pct(frame, span) }} />
        </div>
      </div>
      {children}
      {rows.map((r) => (
        <div key={r.id} className={`tl-row${r.selected ? ' selected' : ''}${r.className ? ` ${r.className}` : ''}`} data-row={r.id} {...dataOf(r.data)} title={r.title}
          onClick={() => { if (moved.current) { moved.current = false; return } r.onSelect?.() }} onContextMenu={r.onMenu}>
          <span className="tl-label">{r.label}</span>
          <div className="tl-track">
            {r.bars?.map((b) => {
              const [f, t] = shown(r.id, b)
              return (
                <div key={b.id} className={`tl-bar bar${b.className ? ` ${b.className}` : ''}${drag?.kind === 'bar' && drag.bar === b.id && drag.row === r.id ? ' dragging' : ''}`} {...dataOf(b.data)}
                  style={{ ...b.style, left: pct(f, span), width: `calc(${pct(t, span)} - ${pct(f, span)})` }} title={b.title}
                  onPointerDown={b.drag ? (e) => grab(e, { kind: 'bar', row: r.id, bar: b.id, mode: e.altKey ? 'slip' : 'move', x0: e.clientX, dx: 0, width: width(e) }) : undefined} {...(b.drag ? handlers : {})}>
                  {b.label}
                  {b.drag && <><span className="h h-in" onPointerDown={(e) => grab(e, { kind: 'bar', row: r.id, bar: b.id, mode: 'in', x0: e.clientX, dx: 0, width: width(e) })} {...handlers} />
                    <span className="h h-out" onPointerDown={(e) => grab(e, { kind: 'bar', row: r.id, bar: b.id, mode: 'out', x0: e.clientX, dx: 0, width: width(e) })} {...handlers} /></>}
                </div>
              )
            })}
            {r.keys?.map((k) => (
              <i key={k.frame} className={`tl-key key-mark${k.frame === frame ? ' here' : ''}${k.className ? ` ${k.className}` : ''}${onKeyDrag ? ' draggable' : ''}`} style={{ left: pct(keyAt(r.id, k.frame), span) }} title={k.title ?? `key at frame ${k.frame}`}
                onPointerDown={(e) => grab(e, { kind: 'key', row: r.id, frame: k.frame, x0: e.clientX, dx: 0, width: width(e) })} {...handlers}
                onContextMenu={onKeyMenu ? (e) => { e.preventDefault(); e.stopPropagation(); onKeyMenu(e, r.id, k.frame) } : undefined} />
            ))}
            {r.markers?.map((m, i) => <span key={`${m.frame}.${i}`} className={`tl-marker marker${m.className ? ` ${m.className}` : ''}`} style={{ left: pct(m.frame, span) }} title={m.title}
              onClick={m.onClick ? (e) => { e.stopPropagation(); m.onClick!() } : undefined}>{m.glyph}</span>)}
            <div className="tl-line playhead" style={{ left: pct(frame, span) }} />
          </div>
        </div>
      ))}
    </div>
  )
}

const dataOf = (d?: Record<string, string>) => Object.fromEntries(Object.entries(d ?? {}).map(([k, v]) => [`data-${k}`, v]))

/** The one transport above the timeline: the same command buttons at every level (anim.*, the level's transport), the frame field, the
 *  counter, then the level's own verbs. */
export function TransportBar({ className = '', frame, last, counter, onFrame, children, playing }: { className?: string; frame: number; last: number; counter: ReactNode; onFrame: (f: number) => void; children?: ReactNode; playing?: boolean }) {
  return (
    <div className={`transport tl-transport ${className}`}>
      <CommandRow ids={['anim.home', 'anim.prevKey', 'anim.back10', 'anim.stepBack', 'anim.play', 'anim.stepForward', 'anim.fwd10', 'anim.nextKey', 'anim.end']} active={playing ? 'anim.play' : undefined} />
      <input className="frame-field" type="number" min={0} max={last} value={frame} aria-label="frame" title="the frame the viewer shows" onChange={(e) => onFrame(Number(e.target.value) || 0)} />
      <span className="counter">{counter}</span>
      {children}
    </div>
  )
}
