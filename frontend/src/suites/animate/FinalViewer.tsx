// AP1 thin / AE2 / AE3 (proto01_animate 20 §2, D114): Animate's Final level — the composition's frames in the viewer, scrubbed by the
// slider and the transport (commands, D32), played from the page's cache, the chip saying how much is cached (a number alone, UX9 U2).
// A drag on the frame moves the selected layer (one `layer.nudge`), or draws a mask with the rectangle / ellipse tool (one `layer.addMask`),
// or, with the points tool, clicks lay a shape's points (one `mask.new`). The selected layer's masks are drawn over the frame (UX9 U3), the
// selected one brighter, its points draggable (one `mask.setVertex` each). The lanes under the transport are the layers' bars (AE2d). The
// Before toggle shows the frame with every effect off (AE3).
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { fmtTime } from './animateStore'
import { chipText, maskPathD, snapTime, useComposition } from './compositionStore'
import { Timeline as TimelineView, TransportBar, type BarDrag, type TLRow } from './Timeline'

interface Drag { x0: number; y0: number; dx: number; dy: number; box: DOMRect; vbox: DOMRect }                 // the frame's and the view's boxes at the press
interface VertexDrag { uid: number; index: number; x0: number; y0: number; dx: number; dy: number }

export function FinalViewer() {
  const finalId = useComposition((s) => s.finalId)
  const final = useComposition((s) => s.final)
  const comp = useComposition((s) => s.comp)
  const shown = useComposition((s) => s.shown)
  const frame = useComposition((s) => s.frame)
  const playing = useComposition((s) => s.playing)
  const filled = useComposition((s) => s.filled)
  const fetching = useComposition((s) => s.fetching)
  const error = useComposition((s) => s.error)
  const busy = useSession((s) => Object.values(s.jobs).some((j) => j.status === 'running'))
  const selected = useComposition((s) => s.selected)
  const selName = useComposition((s) => s.layers.find((l) => l.id === s.selected)?.name)
  const editing = useComposition((s) => s.busy)                           // an edit in flight (the engine round-trip and the reloads)
  const maskTool = useComposition((s) => s.maskTool)
  const before = useComposition((s) => s.before)
  const img = useRef<HTMLImageElement>(null)
  const view = useRef<HTMLDivElement>(null)
  const poly = useComposition((s) => s.poly)                               // the points tool's points so far, in comp pixels (the store clears them with the tool)
  const [drag, setDrag] = useState<Drag | null>(null)
  useEffect(() => { const t = window.setInterval(() => void useComposition.getState().tick(), 250); return () => window.clearInterval(t) }, [])
  useEffect(() => () => useComposition.getState().togglePlay(false), [])
  useEffect(() => {                                                       // Esc drops the points tool's shape
    if (maskTool !== 'poly') return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') useComposition.getState().setMaskTool('off') }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [maskTool])
  // the image element fills the view and the picture is centred in it (object-fit contain): where the picture is, in client pixels
  const picture = (box: DOMRect) => pictureRect(box, final?.size.w ?? 1, final?.size.h ?? 1)
  const scaleOf = () => { const el = img.current; return el && final ? picture(el.getBoundingClientRect()).scale : 1 }
  // AE2: a drag on the frame — the selected layer moved (one `layer.nudge` in comp pixels on release; her matte follows, parented to her),
  // or, with a mask tool on, a rectangle or ellipse mask drawn (AE2c); with the points tool, a click lays a point (UX9 U3)
  const onDown = (e: ReactPointerEvent<HTMLImageElement>) => {
    if (selected === null || e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    const box = e.currentTarget.getBoundingClientRect()
    setDrag({ x0: e.clientX, y0: e.clientY, dx: 0, dy: 0, box, vbox: view.current?.getBoundingClientRect() ?? box })
  }
  const onMove = (e: ReactPointerEvent<HTMLImageElement>) => { if (drag) setDrag({ ...drag, dx: e.clientX - drag.x0, dy: e.clientY - drag.y0 }) }
  const onUp = (e: ReactPointerEvent<HTMLImageElement>) => {
    if (!drag) return
    const pic = picture(drag.box), scale = pic.scale
    setDrag(null)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    const cp = useComposition.getState()
    if (maskTool === 'object') {                                                      // D116: a click names the thing to matte (layer pixels)
      if (Math.abs(drag.dx) > 3 || Math.abs(drag.dy) > 3) return
      void cp.objectMatte(toLayer([(drag.x0 - pic.left) * scale, (drag.y0 - pic.top) * scale]))
      return
    }
    if (maskTool === 'poly') {
      if (Math.abs(drag.dx) > 3 || Math.abs(drag.dy) > 3) return                     // a drag is not a point
      const x = (drag.x0 - pic.left) * scale, y = (drag.y0 - pic.top) * scale
      const first = poly[0]
      if (first && poly.length >= 3 && Math.hypot(first[0] - x, first[1] - y) * (1 / scale) < 10) { void cp.addPolyMask(poly.map(toLayer)); cp.setMaskTool('off'); return }
      cp.setPoly([...poly, [x, y]])
      return
    }
    if (maskTool !== 'off') {
      const x = Math.min(drag.x0, drag.x0 + drag.dx) - pic.left, y = Math.min(drag.y0, drag.y0 + drag.dy) - pic.top
      const w = Math.abs(drag.dx), h = Math.abs(drag.dy)
      if (w >= 4 && h >= 4) { void cp.addMask([Math.round(x * scale), Math.round(y * scale), Math.round(w * scale), Math.round(h * scale)], maskTool); cp.setMaskTool('off') }
      return
    }
    const dx = Math.round(drag.dx * scale), dy = Math.round(drag.dy * scale)
    if (dx || dy) void cp.nudge(dx, dy)
  }
  const onDouble = () => { if (maskTool === 'poly' && poly.length >= 3) { void useComposition.getState().addPolyMask(poly.map(toLayer)); useComposition.getState().setMaskTool('off') } }
  // the selected layer's own pixels sit at (position − anchor) in the composition: masks are in the layer's pixels
  const off = layerOffset()
  const toLayer = ([x, y]: [number, number]): [number, number] => [x - off[0], y - off[1]]
  if (!finalId || !final) {
    return <div className="anim-stage final-viewer"><div className="anim-view"><div className="anim-empty"><h2>Final</h2>no final open — open one in the Shot section <Help text="Performance › Final shot makes a final: the scene split into layers, performed, matted and assembled; Make the composition, then Open it here." /></div></div></div>
  }
  if (!comp) {
    return <div className="anim-stage final-viewer" data-final={final.id}><div className="anim-view"><div className="anim-empty"><h2>{final.name}</h2>no composition yet — Make the composition in the Shot section</div></div></div>
  }
  const n = final.frames
  const ghost = drag && (maskTool === 'rect' || maskTool === 'ellipse')
    ? { left: Math.min(drag.x0, drag.x0 + drag.dx) - drag.vbox.left, top: Math.min(drag.y0, drag.y0 + drag.dy) - drag.vbox.top, width: Math.abs(drag.dx), height: Math.abs(drag.dy) } : null
  const side = shown?.side ?? 'half'
  return (
    <div className="anim-stage final-viewer" data-final={final.id} data-editing={editing ? 'true' : undefined}>
      <div ref={view} className={`anim-view final-view${maskTool !== 'off' ? ' masking' : ''}`}>
        {shown ? <div className="frame-box">
          <img ref={img} className={`final-frame ${selected !== null ? 'movable' : ''}`} src={before ?? shown.url} alt="" draggable={false} data-side={shown.side} data-before={before ? 'true' : undefined}
            title={selected !== null ? (maskTool === 'poly' ? 'Click the points of the shape; click the first again to close' : maskTool === 'object' ? `Click the thing on ${selName ?? 'the layer'} to matte` : maskTool !== 'off' ? `Drag to draw the ${maskTool === 'rect' ? 'rectangle' : 'ellipse'} mask on ${selName ?? 'the layer'}` : `Drag to move ${selName ?? 'the selected layer'}`) : undefined}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={() => setDrag(null)} onDoubleClick={onDouble} />
          {selected !== null && <MaskOverlay w={final.size.w} h={final.size.h} offset={off} poly={poly} scaleOf={scaleOf} />}
        </div> : <div className="anim-overlay">loading the first frame…</div>}
        {ghost ? <div className={`mask-ghost ${maskTool}`} style={ghost} /> : drag && maskTool === 'off' && (drag.dx || drag.dy) ? <div className="drag-ghost" style={{ transform: `translate(${drag.dx}px, ${drag.dy}px)` }}><span>{selName}: {Math.round(drag.dx)}, {Math.round(drag.dy)} px</span></div> : null}
        <span className="final-chip" data-side={side} data-busy={busy ? 'true' : undefined} data-fetching={fetching ? 'true' : undefined}
          title={`${Math.round((100 * filled) / Math.max(1, n))} % of the shot cached for playback · shown at ${side === 'full' ? 'full size' : 'half size'}${busy ? ' · a job runs: frames on demand only' : ''}${before ? ' · before: every effect off' : ''}`}>
          {before ? 'before' : chipText({ filled, final })}</span>
        {error && <div className="anim-overlay err">preview: {error}</div>}
      </div>
      <TransportBar className="final-transport" frame={frame} last={n - 1} playing={playing} onFrame={(f) => useComposition.getState().setFrame(f)} counter={`frame ${frame} / ${n - 1} · ${fmtTime(frame, final.rate)}`}>
        <CommandButton id="anim.final.before" active={!!before} />
        <span className="hint" data-comp-state>composition · revision {comp.revision}{comp.stale ? ' · stale: the final changed, make it again' : ''}{comp.clip_id ? ` · rendered at revision ${comp.rendered_revision}` : ''}</span>
      </TransportBar>
      <Lanes rate={final.rate} frames={n} />
    </div>
  )
}

/** Where the picture sits inside the image element (contain-fit, centred); `scale` is comp pixels per css pixel. */
function pictureRect(box: DOMRect, w: number, h: number) {
  const k = Math.min(box.width / Math.max(1, w), box.height / Math.max(1, h))
  const pw = w * k, ph = h * k
  return { left: box.left + (box.width - pw) / 2, top: box.top + (box.height - ph) / 2, width: pw, height: ph, scale: k > 0 ? 1 / k : 1 }
}

/** The selected layer's pixels sit at (position − anchor) in the composition (the contact offset, D107). */
function layerOffset(): [number, number] {
  const props = useComposition.getState().props
  const pos = props.find((p) => p.path === 'transform/position')?.value as number[] | undefined
  const anc = props.find((p) => p.path === 'transform/anchor')?.value as number[] | undefined
  return [Number(pos?.[0] ?? 0) - Number(anc?.[0] ?? 0), Number(pos?.[1] ?? 0) - Number(anc?.[1] ?? 0)]
}

/** UX9 U3: the selected layer's masks drawn over the frame — the selected one brighter, its points draggable; the points tool's shape. */
function MaskOverlay({ w, h, offset, poly, scaleOf }: { w: number; h: number; offset: [number, number]; poly: [number, number][]; scaleOf: () => number }) {
  const masks = useComposition((s) => s.masks)
  const selectedMask = useComposition((s) => s.selectedMask)
  const view = useComposition((s) => s.maskView)
  const busy = useComposition((s) => s.busy)
  const [vd, setVd] = useState<VertexDrag | null>(null)
  const k = scaleOf()
  const r = 4 * k                                                         // a handle 4 css px wide, in comp pixels
  const start = (e: ReactPointerEvent<SVGCircleElement>, uid: number, index: number) => {
    if (e.button !== 0 || busy) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    useComposition.getState().selectMask(uid)
    setVd({ uid, index, x0: e.clientX, y0: e.clientY, dx: 0, dy: 0 })
  }
  const move = (e: ReactPointerEvent<SVGCircleElement>) => { if (vd) setVd({ ...vd, dx: e.clientX - vd.x0, dy: e.clientY - vd.y0 }) }
  const end = (e: ReactPointerEvent<SVGCircleElement>) => {
    if (!vd) return
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    const m = masks.find((x) => x.uid === vd.uid)
    const v = m?.vertices[vd.index]
    setVd(null)
    if (!m || !v || (Math.abs(vd.dx) < 2 && Math.abs(vd.dy) < 2)) return
    void useComposition.getState().moveVertex(vd.uid, vd.index, [v[0] + vd.dx * k, v[1] + vd.dy * k])
  }
  return (
    <svg className={`mask-overlay ${view}`} viewBox={`0 0 ${w} ${h}`} width="100%" height="100%" aria-label="masks" data-view={view}>
      {masks.map((m) => {
        const sel = m.uid === selectedMask
        const verts = vd && vd.uid === m.uid ? m.vertices.map((p, i) => (i === vd.index ? [p[0] + vd.dx * k, p[1] + vd.dy * k] as [number, number] : p)) : m.vertices
        const d = maskPathD({ ...m, vertices: verts }, offset[0], offset[1])
        const fillD = view === 'fill' && m.inverted ? `M 0 0 H ${w} V ${h} H 0 Z ${d}` : d                   // Fill: an inverted mask covers the frame but the shape
        return (
          <g key={m.uid} className={`mask${sel ? ' selected' : ''}${m.inverted ? ' inverted' : ''}`} data-mask={m.uid}>
            <path d={fillD} fillRule="evenodd" vectorEffect="non-scaling-stroke" onClick={() => useComposition.getState().selectMask(m.uid)} />
            {sel && verts.map((p, i) => <circle key={i} cx={p[0] + offset[0]} cy={p[1] + offset[1]} r={r} className="vertex" data-index={i}
              onPointerDown={(e) => start(e, m.uid, i)} onPointerMove={move} onPointerUp={end} onPointerCancel={() => setVd(null)} />)}
          </g>
        )
      })}
      {poly.length > 0 && <g className="mask drawing">
        <path d={`M ${poly.map((p) => `${p[0]} ${p[1]}`).join(' L ')}`} vectorEffect="non-scaling-stroke" />
        {poly.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={i === 0 ? r * 1.5 : r} className={i === 0 ? 'vertex first' : 'vertex'} />)}
      </g>}
    </svg>
  )
}

/** AE2d → D121 (AW2): the layers as lanes of the one timeline — a bar per layer over the shot (drag to move, the ends to trim, Alt-drag to slip;
 *  in frames of the shot, written back in seconds), the selected layer's keys on its lane, a line's waveform on its bar, the playhead. */
function Lanes({ rate, frames }: { rate: number; frames: number }) {
  const layers = useComposition((s) => s.layers)
  const selected = useComposition((s) => s.selected)
  const frame = useComposition((s) => s.frame)
  const keysOf = useComposition((s) => s.keysOf)
  const busy = useComposition((s) => s.busy)
  const audioOf = useComposition((s) => s.audioOf)
  const step = 1 / rate
  const duration = frames / rate
  const keyFrames = selected === null ? [] : [...new Set(Object.values(keysOf).flat().map((k) => Math.round(k.time * rate)))]
  const rows: TLRow[] = layers.map((l) => {
    const sel = selected === l.id
    const audio = audioOf(l.id)                                            // D118 (AE4b): a line's bar shows its waveform
    return { id: String(l.id), className: `lane${audio ? ' audio' : ''}`, selected: sel, data: { lane: String(l.id) }, title: audio ? `${l.name} · ${audio.text}` : l.name,
      label: <span className="lane-name">{audio ? '🔊 ' : ''}{l.name}</span>,
      onSelect: () => useComposition.getState().select(sel ? null : l.id),
      bars: [{ id: 'bar', from: Math.round(l.in * rate), to: Math.round(l.out * rate), drag: !busy, style: audio ? { backgroundImage: `url(${api.thumbUrl(audio.asset_id, 256)})` } : undefined,
        title: `${l.name}: ${l.in.toFixed(2)}–${l.out.toFixed(2)} s · drag to move, the ends to trim, Alt-drag to slip` }],
      keys: sel ? keyFrames.map((f) => ({ frame: f, title: `key at ${(f / rate).toFixed(2)} s` })) : [] }
  })
  const onBarDrag = (row: string, _bar: string, mode: BarDrag, delta: number) => {
    const l = layers.find((x) => String(x.id) === row)
    if (!l || busy) return
    const cp = useComposition.getState(), d = snapTime(delta / rate, rate)
    cp.select(l.id)
    if (mode === 'move') void cp.setTiming(l.id, { delta: d })
    else if (mode === 'in') void cp.setTiming(l.id, { in: Math.max(0, Math.min(l.out - step, l.in + d)) })
    else if (mode === 'out') void cp.setTiming(l.id, { out: Math.max(l.in + step, Math.min(duration, l.out + d)) })
    else void cp.slip(l.id, d)
  }
  return <TimelineView className="final-lanes" span={[0, frames]} fps={rate} frame={frame} onSeek={(f) => useComposition.getState().setFrame(Math.min(frames - 1, f))} rows={rows} onBarDrag={onBarDrag} />
}
