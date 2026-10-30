// D165: Performance's Windows view — the shot's final frame by frame (Clay's lit picture of it, the skeletons over it), each character's
// window (D163: Wan's portrait, resized never reshaped) and head box (D118: the face pass's and lip-sync's crop). Drag a box to move it,
// its corner to resize it: a key at the frame shown. The keys sit as diamonds under the frames. Every verb is a command with a button and a
// right-click item (rule 3); the explanation is behind the ? (rule 11).
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { api } from '../../api/client'
import type { LayerBoxes } from '../../api/types'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useStory } from '../story/storyStore'
import { useFinals } from '../stage/finalShot'
import { moved, rectOf, resized, type Box, type BoxKind } from './boxKeys'
import { finalFor, keysOf, shownBox, trackOf, useWindows } from './windowsStore'

const COLOURS = ['#f2a33a', '#4fc3f7', '#ba68c8', '#81c784', '#e57373', '#fff176']
const HELP = "Each character is performed in a window of its own (Wan's 480×848 shape) and its face pass and lip-sync work in a head box. "
  + 'Both start from the automatic tracking, shown as keys (diamonds). Drag a box to move it or its corner to resize it: that sets a key at '
  + 'the frame shown, and the frames between keys follow in straight lines. Right-click a box or a diamond for its verbs. No window performs '
  + 'the character at the frame; No face work takes its face pass and lip-sync off the owed list. A layer already performed needs a re-take '
  + 'to use a changed window.'

type Drag = { lid: string; kind: BoxKind; how: 'move' | 'size'; x: number; y: number; from: Box; box: Box }

export function WindowsView() {
  const finals = useFinals((s) => s.finals)
  const shot = useStory((s) => s.shot())
  const version = useStory((s) => s.shotVersion())
  const f = finalFor(finals, shot?.id, version?.id)
  const { data, frame, sel, skeletons, fid } = useWindows()
  const svg = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  useEffect(() => { if (!finals.length) void useFinals.getState().load() }, [finals.length])
  useEffect(() => { if (f) void useWindows.getState().load(f.id) }, [f?.id, f?.revision])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!f) return <div className="anim-empty"><h2>Windows</h2>make the shot's final first — its frames come from Clay</div>
  if (!data || fid !== f.id) return <div className="anim-empty"><h2>Windows</h2>reading the final's boxes…</div>
  if (!data.layers.length) return <div className="anim-empty"><h2>Windows</h2>no character in this final</div>
  const win = data.window as [number, number]
  const shadows = f.layers.some((l) => l.kind === 'shadows') ? 'shadows' : 'plate'
  // a margin round the frame as far as the boxes reach (a window may reach outside the frame: a figure cut by it, W58), at most 60 %
  const all = data.layers.flatMap((l) => [...l.window.frames, ...l.head.frames])
  const reach = (v: number, cap: number) => Math.min(cap * 0.6, Math.max(0, v)) + 8
  const pad = { l: reach(-Math.min(0, ...all.map((r) => r[0])), data.w), t: reach(-Math.min(0, ...all.map((r) => r[1])), data.h),
    r: reach(Math.max(0, ...all.map((r) => r[0] + r[2])) - data.w, data.w), b: reach(Math.max(0, ...all.map((r) => r[1] + r[3])) - data.h, data.h) }
  const W = data.w + pad.l + pad.r, H = data.h + pad.t + pad.b
  const place = { left: `${(pad.l / W) * 100}%`, top: `${(pad.t / H) * 100}%`, width: `${(data.w / W) * 100}%`, height: `${(data.h / H) * 100}%` }
  const point = (e: { clientX: number; clientY: number }) => {
    const m = svg.current?.getScreenCTM()
    if (!m) return { x: 0, y: 0 }
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse())
    return { x: p.x, y: p.y }
  }
  const start = (e: ReactPointerEvent, l: LayerBoxes, kind: BoxKind, how: Drag['how']) => {
    if (e.button !== 0) return
    const b = shownBox(l, kind, frame)
    if (!b) return
    e.stopPropagation()
    ;(e.target as Element).setPointerCapture(e.pointerId)
    useWindows.getState().select({ lid: l.id, kind })
    const p = point(e)
    setDrag({ lid: l.id, kind, how, x: p.x, y: p.y, from: b, box: b })
  }
  const move = (e: ReactPointerEvent) => {
    if (!drag) return
    const p = point(e)
    setDrag({ ...drag, box: drag.how === 'move' ? moved(drag.from, p.x - drag.x, p.y - drag.y) : resized(drag.from, drag.kind, p.x, p.y, win) })
  }
  const end = () => {
    if (!drag) return
    const d = drag
    setDrag(null)
    if (Math.abs(d.box.cx - d.from.cx) + Math.abs(d.box.cy - d.from.cy) + Math.abs(d.box.size - d.from.size) > 0.5) void useWindows.getState().place({ lid: d.lid, kind: d.kind }, d.box)
  }
  const menu = (e: React.MouseEvent, l: LayerBoxes, kind: BoxKind) => {
    e.preventDefault()
    e.stopPropagation()
    useWindows.getState().select({ lid: l.id, kind })
    showMenu(e, boxMenu(kind))
  }
  const selected = data.layers.find((l) => l.id === sel?.lid) ?? data.layers[0]
  const selKind: BoxKind = sel?.kind ?? 'window'
  return (
    <div className="win-view" data-testid="windows-view">
      <div className="win-bar">
        {data.layers.map((l, i) => <span key={l.id} className="win-who">
          {(['window', 'head'] as const).map((kind) => <button key={kind} type="button" className={`win-chip${sel?.lid === l.id && selKind === kind ? ' active' : ''}`} data-layer={l.id} data-kind={kind}
            data-mode={trackOf(l, kind).mode} style={{ borderColor: COLOURS[i % COLOURS.length] }} onClick={() => useWindows.getState().select({ lid: l.id, kind })}
            onContextMenu={(e) => menu(e, l, kind)} title={`${l.name}'s ${kind === 'window' ? 'window' : 'head box'} — ${modeText(l, kind)}`}>
            {kind === 'window' ? l.name : 'head'}{trackOf(l, kind).mode === 'keys' ? ' ◆' : trackOf(l, kind).mode === 'none' ? ' ✕' : ''}</button>)}
        </span>)}
        <span className="spacer" />
        <CommandRow ids={['anim.windows.key', 'anim.windows.deleteKey', 'anim.windows.auto']} />
        <CommandButton id="anim.windows.remove" label={selKind === 'window' ? 'No window (performed at the frame)' : 'No face work (the head box removed)'} />
        <CommandButton id="anim.windows.add" label={selKind === 'window' ? 'Add a window' : 'Add a head box'} />
        <CommandButton id="anim.windows.skeletons" active={skeletons} />
        <Help text={HELP} />
      </div>
      <div className="win-frame">
        <div className="win-pic" style={{ aspectRatio: `${W} / ${H}` }}>
          <img src={api.fileUrl(`/finals/${f.id}/layers/${shadows}/clay/${frame}`)} alt="" draggable={false} style={place} />
          {skeletons && data.layers.map((l) => <img key={l.id} className="win-pose" src={api.fileUrl(`/finals/${f.id}/layers/${l.id}/pose/${frame}`)} alt="" draggable={false} style={place} />)}
          <svg ref={svg} viewBox={`${-pad.l} ${-pad.t} ${W} ${H}`} onPointerMove={move} onPointerUp={end} onPointerCancel={end}>
            <rect className="win-edge" x={0} y={0} width={data.w} height={data.h}><title>the shot's frame</title></rect>
            {data.layers.map((l, i) => (['window', 'head'] as const).map((kind) => {
              const live = drag && drag.lid === l.id && drag.kind === kind ? drag.box : shownBox(l, kind, frame)
              if (!live) return null
              const [x, y, w, h] = rectOf(live, kind, win)
              const on = sel?.lid === l.id && selKind === kind
              const t = trackOf(l, kind)
              return <g key={`${l.id}:${kind}`} className={`win-box ${kind}${on ? ' on' : ''}`} data-layer={l.id} data-kind={kind} data-mode={t.mode}
                data-missed={t.misses.includes(frame) ? 'true' : undefined} style={{ color: COLOURS[i % COLOURS.length] }}>
                <rect x={x} y={y} width={w} height={h} strokeDasharray={t.mode === 'auto' ? '8 5' : undefined}
                  onPointerDown={(e) => start(e, l, kind, 'move')} onContextMenu={(e) => menu(e, l, kind)}>
                  <title>{`${l.name}'s ${kind === 'window' ? 'window' : 'head box'} — ${modeText(l, kind)}. Drag to move; the corner resizes; right-click for more`}</title>
                </rect>
                {on && <rect className="win-handle" x={x + w - 7} y={y + h - 7} width={14} height={14} onPointerDown={(e) => start(e, l, kind, 'size')} />}
              </g>
            }))}
          </svg>
        </div>
      </div>
      <div className="win-time">
        <input type="range" min={0} max={Math.max(0, data.frames - 1)} value={frame} aria-label="frame" onChange={(e) => useWindows.getState().setFrame(Number(e.target.value))} />
        <span className="counter">frame {frame} / {data.frames - 1}</span>
        <span className="win-warn" data-warn>{warning(selected)}</span>
        {(['window', 'head'] as const).map((kind) => <div key={kind} className="win-keys" data-kind={kind}>
          <span className="hint">{selected.name} · {kind === 'window' ? 'window' : 'head'}</span>
          <div className="win-track">
            {keysOf(selected, kind).map((k) => <button key={k.frame} type="button" className={`win-key${k.frame === frame ? ' at' : ''}${trackOf(selected, kind).mode !== 'keys' ? ' offer' : ''}`}
              style={{ left: `${(k.frame / Math.max(1, data.frames - 1)) * 100}%` }} data-frame={k.frame} title={`key at frame ${k.frame}${trackOf(selected, kind).mode !== 'keys' ? ' (automatic)' : ''}`}
              onClick={() => { useWindows.getState().select({ lid: selected.id, kind }); useWindows.getState().setFrame(k.frame) }}
              onContextMenu={(e) => { useWindows.getState().select({ lid: selected.id, kind }); useWindows.getState().setFrame(k.frame); e.preventDefault(); showMenu(e, boxMenu(kind)) }}>◆</button>)}
          </div>
        </div>)}
      </div>
    </div>
  )
}

function boxMenu(kind: BoxKind) {
  return [{ cmd: 'anim.windows.key' }, { cmd: 'anim.windows.deleteKey' }, { cmd: 'anim.windows.auto' },
    { cmd: 'anim.windows.remove', label: kind === 'window' ? 'No window (performed at the frame)' : 'No face work (the head box removed)' },
    { cmd: 'anim.windows.add', label: kind === 'window' ? 'Add a window' : 'Add a head box' }]
}

function modeText(l: LayerBoxes, kind: BoxKind): string {
  const t = trackOf(l, kind)
  if (t.mode === 'none') return kind === 'window' ? 'none: performed at the frame' : 'none: no face work'
  if (t.mode === 'keys') return `${t.keys.length} key${t.keys.length === 1 ? '' : 's'} set by hand`
  if (kind === 'window') return t.frames.length ? 'automatic' : 'automatic: none (the figure is large enough at the frame)'
  return `automatic (the head ${l.fit === 'band' ? 'gets the face pass' : l.fit === 'small' ? 'is too small for the face pass' : l.fit === 'large' ? 'needs no face pass' : l.fit === 'away' ? 'is seen from behind' : 'is outside the frame'})`
}

/** The selected layer's short warning: a window that leaves part of the figure out, a head box without the head, a change since performed. */
function warning(l: LayerBoxes): string {
  const parts: string[] = []
  if (l.window.misses.length) parts.push(`the window leaves part of ${l.name} out on ${l.window.misses.length} frame${l.window.misses.length === 1 ? '' : 's'}`)
  if (l.head.misses.length) parts.push(`the head box misses the head on ${l.head.misses.length}`)
  if (l.window.changed) parts.push('the window changed since it was performed — re-take')
  if (l.head.changed) parts.push('the head box changed since the face take')
  return parts.join(' · ')
}
