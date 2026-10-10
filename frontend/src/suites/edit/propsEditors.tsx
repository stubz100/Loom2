// Properties editors (D57; PhotoCraft ui-egui props_layout.rs, adjust_editors.rs, point_curve.rs and tone.rs @ b37bff98, MIT OR
// Apache-2.0 — behaviour ported, code written for React): collapsible sections, the histogram of the layers below an adjustment,
// Levels (histogram, triangle sliders, Auto), Curves (click adds, drag off / Ctrl-click / right-click / Delete removes, per channel,
// PhotoCraft's spline) and Colour balance (a tone range, three gradient slider rows). Every gesture is one undo step: `start` takes
// the before-state, `commit` records it.
import { useMemo, useRef, useState, type ReactNode } from 'react'
import { canvasBlend, useEditor, type Node } from './editorStore'
import { cachedLut, type CurvePoints } from './curves'
import { ValueField } from './widgets'

// ---- sections -----------------------------------------------------------------------------------------------
const OPEN = new Map<string, boolean>()                              // open state per section id, for the session (PhotoCraft: egui temp memory)
export function Section({ id, title, children, extra }: { id: string; title: string; children: ReactNode; extra?: ReactNode }) {
  const [open, setOpen] = useState(OPEN.get(id) ?? true)
  return (
    <div className="props-section">
      <button type="button" className="props-head" aria-expanded={open} onClick={() => { OPEN.set(id, !open); setOpen(!open) }}>
        <span className="chev">{open ? '▾' : '▸'}</span><span>{title}</span>{extra}
      </button>
      {open && <div className="props-body">{children}</div>}
    </div>
  )
}

// ---- histogram of what lies below a layer ----------------------------------------------------------------------
export interface Hist { rgb: Uint32Array; r: Uint32Array; g: Uint32Array; b: Uint32Array }
/** 256-bin histograms of the visible raster layers below `id` (panel order), composited on the CPU at ≤ 384 px with canvas blends —
 * a guide for Levels / Curves, not the exact composite (adjustments below are not applied). RGB is the plain mean of R, G and B
 * (PhotoCraft tone.rs); fully transparent pixels are skipped. */
function histogramBelow(id: string): Hist | null {
  const st = useEditor.getState(), doc = st.doc
  if (!doc) return null
  const order: Node[] = [], parent = new Map<string, Node | null>()
  const rec = (ns: Node[], p: Node | null) => ns.forEach((n) => { order.push(n); parent.set(n.id, p); if (n.children) rec(n.children, n) })
  rec(doc.layers, null)
  const at = order.findIndex((n) => n.id === id)
  if (at < 0) return null
  const shown = (n: Node): boolean => n.visible && (parent.get(n.id) ? shown(parent.get(n.id)!) : true)
  const below = order.slice(at + 1).filter((n) => n.kind === 'raster' && shown(n))
  const s = Math.min(1, 384 / Math.max(doc.w, doc.h))
  const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(doc.w * s)); c.height = Math.max(1, Math.round(doc.h * s))
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  if (doc.background && doc.background !== 'transparent') { ctx.fillStyle = doc.background; ctx.fillRect(0, 0, c.width, c.height) }
  ctx.scale(s, s)
  for (const n of [...below].reverse()) {
    const lp = st.pixels.get(n.id)
    if (!lp) continue
    ctx.globalAlpha = n.opacity * (n.fill ?? 1); ctx.globalCompositeOperation = canvasBlend(n.blend)
    ctx.drawImage(lp.canvas, n.x ?? 0, n.y ?? 0)
  }
  const d = ctx.getImageData(0, 0, c.width, c.height).data
  const h: Hist = { rgb: new Uint32Array(256), r: new Uint32Array(256), g: new Uint32Array(256), b: new Uint32Array(256) }
  for (let i = 0; i < d.length; i += 4) {
    if (!d[i + 3]) continue
    h.r[d[i]]++; h.g[d[i + 1]]++; h.b[d[i + 2]]++; h.rgb[Math.round((d[i] + d[i + 1] + d[i + 2]) / 3)]++
  }
  return h
}
function useHistogram(id: string): Hist | null {
  const revision = useEditor((s) => s.revision)
  return useMemo(() => histogramBelow(id), [id, revision]) // eslint-disable-line react-hooks/exhaustive-deps
}
/** Bars scaled so the 251st-smallest bin × 1.1 reaches the top (PhotoCraft draw_histogram: spikes saturate instead of flattening the rest). */
function HistogramBars({ bins, w, h, colour = 'var(--fg3)' }: { bins: Uint32Array | null; w: number; h: number; colour?: string }) {
  const path = useMemo(() => {
    if (!bins) return ''
    const top = Math.max(1, [...bins].sort((a, b) => a - b)[250] * 1.1)
    let p = ''
    for (let i = 0; i < 256; i++) { const v = Math.min(1, bins[i] / top) * h; if (v > 0) p += `M${(i + 0.5) * w / 256} ${h}V${h - v}` }
    return p
  }, [bins, w, h])
  return <path d={path} stroke={colour} strokeWidth={w / 256 + 0.2} opacity={0.55} />
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
type Params = Record<string, unknown>
export interface EditorProps { id: string; params: Params; set: (p: Params) => void; start: () => void; commit: (label: string) => void }

// ---- Levels ----------------------------------------------------------------------------------------------------
const W = 256
export function LevelsEditor({ id, params, set, start, commit }: EditorProps) {
  const hist = useHistogram(id)
  const num = (k: string, d: number) => { const v = Number(params[k]); return Number.isFinite(v) ? v : d }
  const ib = num('in_black', 0), iw = num('in_white', 255), g = num('gamma', 1), ob = num('out_black', 0), ow = num('out_white', 255)
  const gx = ib + (iw - ib) * 0.5 ** g                                // the grey triangle sits where 0.5^gamma of the input span is
  const svgIn = useRef<SVGSVGElement>(null), svgOut = useRef<SVGSVGElement>(null)
  const valueAt = (el: SVGSVGElement | null, x: number) => { const r = el!.getBoundingClientRect(); return clamp(((x - r.left) / r.width) * 255, 0, 255) }
  const dragInput = (e: React.PointerEvent<SVGSVGElement>) => {
    const v0 = valueAt(svgIn.current, e.clientX)
    const handles: [string, number][] = [['in_black', ib], ['gamma', gx], ['in_white', iw]]
    const which = handles.reduce((a, b) => (Math.abs(b[1] - v0) < Math.abs(a[1] - v0) ? b : a))[0]   // the nearest triangle
    start()
    const apply = (x: number) => {
      const v = valueAt(svgIn.current, x)
      if (which === 'in_black') set({ ...params, in_black: Math.round(Math.min(v, iw - 2)) })
      else if (which === 'in_white') set({ ...params, in_white: Math.round(Math.max(v, ib + 2)) })
      else { const t = clamp((v - ib) / Math.max(1, iw - ib), 0.01, 0.99); set({ ...params, gamma: Math.round(clamp(Math.log(t) / Math.log(0.5), 0.01, 9.99) * 100) / 100 }) }
    }
    apply(e.clientX)
    track(e, apply, () => commit(`levels ${which.replace('_', ' ')}`))
  }
  const dragOutput = (e: React.PointerEvent<SVGSVGElement>) => {
    const v0 = valueAt(svgOut.current, e.clientX)
    const which = Math.abs(v0 - ob) <= Math.abs(v0 - ow) ? 'out_black' : 'out_white'
    start()
    const apply = (x: number) => set({ ...params, [which]: Math.round(valueAt(svgOut.current, x)) })
    apply(e.clientX)
    track(e, apply, () => commit(`levels ${which.replace('_', ' ')}`))
  }
  const auto = () => {                                               // clip 0.1 % at each end of the composite histogram, gamma 1
    if (!hist) return
    const total = hist.rgb.reduce((a, b) => a + b, 0), cut = total / 1000
    let lo = 0, acc = 0
    while (lo < 254 && (acc += hist.rgb[lo]) <= cut) lo++
    let hi = 255; acc = 0
    while (hi > lo + 2 && (acc += hist.rgb[hi]) <= cut) hi--
    start(); set({ ...params, in_black: lo, in_white: hi, gamma: 1 }); commit('auto levels')
  }
  const tri = (x: number, fill: string) => <path d={`M${x * W / 255} 1 L${x * W / 255 - 5.5} 10 L${x * W / 255 + 5.5} 10 Z`} fill={fill} stroke="var(--fg3)" strokeWidth={0.8} />
  return (
    <div className="tone-editor">
      <svg className="tone-hist" viewBox={`0 0 ${W} 110`} width="100%" height={110} preserveAspectRatio="none"><HistogramBars bins={hist?.rgb ?? null} w={W} h={110} /></svg>
      <svg ref={svgIn} className="tone-handles" viewBox={`-6 0 ${W + 12} 12`} width="100%" height={14} onPointerDown={dragInput}>{tri(ib, '#000')}{tri(gx, '#808080')}{tri(iw, '#fff')}</svg>
      <div className="tool-opts tone-fields">
        <ValueField label="input black" value={ib} min={0} max={253} onStart={start} onChange={(v) => set({ ...params, in_black: Math.round(Math.min(v, iw - 2)) })} onCommit={() => commit('levels input black')} />
        <ValueField label="gamma" value={g} min={0.01} max={9.99} onStart={start} onChange={(v) => set({ ...params, gamma: Math.round(v * 100) / 100 })} onCommit={() => commit('levels gamma')} />
        <ValueField label="input white" value={iw} min={2} max={255} onStart={start} onChange={(v) => set({ ...params, in_white: Math.round(Math.max(v, ib + 2)) })} onCommit={() => commit('levels input white')} />
      </div>
      <div className="tone-bar" />
      <svg ref={svgOut} className="tone-handles" viewBox={`-6 0 ${W + 12} 12`} width="100%" height={14} onPointerDown={dragOutput}>{tri(ob, '#000')}{tri(ow, '#fff')}</svg>
      <div className="tool-opts tone-fields">
        <ValueField label="output black" value={ob} min={0} max={255} onStart={start} onChange={(v) => set({ ...params, out_black: Math.round(v) })} onCommit={() => commit('levels output black')} />
        <ValueField label="output white" value={ow} min={0} max={255} onStart={start} onChange={(v) => set({ ...params, out_white: Math.round(v) })} onCommit={() => commit('levels output white')} />
        <label /><button type="button" className="auto-btn" style={{ justifySelf: 'start' }} onClick={auto} disabled={!hist} title="black and white points at 0.1 % clipping of the layers below; gamma 1">Auto</button>
      </div>
    </div>
  )
}

/** Pointer capture for a press: `apply` on every move, `done` on release. */
function track(e: React.PointerEvent<Element>, apply: (x: number, y: number) => void, done: () => void) {
  const el = e.currentTarget as Element
  el.setPointerCapture(e.pointerId)
  const move = (ev: PointerEvent) => apply(ev.clientX, ev.clientY)
  const up = () => { el.removeEventListener('pointermove', move as EventListener); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up); done() }
  el.addEventListener('pointermove', move as EventListener); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up)
}

// ---- Curves ----------------------------------------------------------------------------------------------------
const CH = [['rgb', 'RGB', 'var(--fg)'], ['r', 'Red', '#e5484d'], ['g', 'Green', '#46a758'], ['b', 'Blue', '#3e8ef7']] as const
type ChKey = 'rgb' | 'r' | 'g' | 'b'
const IDENT: CurvePoints = [[0, 0], [255, 255]]
const MAX_POINTS = 16, MIN_GAP = 2, HIT = 9, DRAG_OFF = 12
const S = 256                                                         // graph units (0..255 maps onto 0..S)
/** The curve as a polyline: spline curves through PhotoCraft's LUT, curves from before D57 as their straight segments. */
function curvePath(points: CurvePoints, spline: boolean): string {
  if (!spline) {
    const pts = [...points].sort((a, b) => a[0] - b[0])
    const ext: CurvePoints = [[0, pts[0][1]], ...pts, [255, pts[pts.length - 1][1]]]
    return ext.map(([x, y], i) => `${i ? 'L' : 'M'}${x * S / 255} ${S - y * S / 255}`).join('')
  }
  const t = cachedLut(points)
  let p = ''
  for (let k = 0; k <= 128; k++) { const x = k / 128, i = Math.round(x * (t.length - 1)); p += `${k ? 'L' : 'M'}${x * S} ${S - t[i] * S}` }
  return p
}
export function CurvesEditor({ id, params, set, start, commit }: EditorProps) {
  const hist = useHistogram(id)
  const [ch, setCh] = useState<ChKey>('rgb')
  const [sel, setSel] = useState<number | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const spline = params.interp === 'spline'
  const ptsOf = (k: ChKey): CurvePoints => (Array.isArray(params[k]) && (params[k] as CurvePoints).length >= 2 ? (params[k] as CurvePoints).map((q) => [q[0], q[1]] as [number, number]).sort((a, b) => a[0] - b[0]) : IDENT)
  const pts = ptsOf(ch)
  /** Writes the channel's points; editing a pre-D57 linear curve turns the layer into a spline (PhotoCraft has only splines). */
  const write = (next: CurvePoints) => set({ ...params, interp: 'spline', [ch]: next })
  const toUnits = (x: number, y: number) => { const r = svg.current!.getBoundingClientRect(); return { vx: ((x - r.left) / r.width) * 255, vy: 255 - ((y - r.top) / r.height) * 255, out: x < r.left - DRAG_OFF || x > r.right + DRAG_OFF || y < r.top - DRAG_OFF || y > r.bottom + DRAG_OFF } }
  const canDelete = (list: CurvePoints, i: number) => i > 0 && i < list.length - 1 && list.length > 2
  /** Inputs stay strictly between the neighbours (endpoints within 0..255), whole levels. */
  const moveTo = (list: CurvePoints, i: number, vx: number, vy: number): CurvePoints => {
    const lo = i > 0 ? list[i - 1][0] + 1 : 0, hi = i < list.length - 1 ? list[i + 1][0] - 1 : 255
    const next = list.map((q) => [q[0], q[1]] as [number, number])
    next[i] = [Math.round(clamp(vx, lo, hi)), Math.round(clamp(vy, 0, 255))]
    return next
  }
  const onDown = (e: React.PointerEvent<SVGSVGElement>) => {
    e.preventDefault(); svg.current?.focus()
    const { vx, vy } = toUnits(e.clientX, e.clientY)
    const r = svg.current!.getBoundingClientRect(), k = r.width / 255
    const near = pts.findIndex(([px, py]) => Math.hypot((px - vx) * k, (py - vy) * k) <= HIT)
    if (near >= 0 && (e.button === 2 || e.ctrlKey || e.metaKey)) {    // Ctrl-click or right-click removes a point
      if (canDelete(pts, near)) { start(); write(pts.filter((_, j) => j !== near)); commit('curves remove point'); setSel(null) }
      return
    }
    if (e.button !== 0) return
    let list = pts, i = near
    start()
    if (i < 0) {
      const close = pts.findIndex(([px]) => Math.abs(px - vx) < MIN_GAP)
      if (close >= 0) i = close
      else if (pts.length < MAX_POINTS) { list = [...pts, [Math.round(clamp(vx, 0, 255)), Math.round(clamp(vy, 0, 255))] as [number, number]].sort((a, b) => a[0] - b[0]); i = list.findIndex(([px]) => px === Math.round(clamp(vx, 0, 255))); write(list) }
      else { commit('curves'); return }
    }
    setSel(i)
    const grabX = list[i][0] - vx, grabY = list[i][1] - vy
    let removed: [number, number] | null = null
    track(e, (x, y) => {
      const u = toUnits(x, y)
      if (u.out && canDelete(list, i) && !removed) { removed = list[i]; list = list.filter((_, j) => j !== i); write(list); setSel(null); return }   // dragged off: removed
      if (removed && !u.out) { list = [...list, removed].sort((a, b) => a[0] - b[0]); i = list.indexOf(removed); removed = null; setSel(i) }       // back in: reinserted
      if (removed) return
      list = moveTo(list, i, u.vx + grabX, u.vy + grabY); write(list)
    }, () => commit(removed ? 'curves remove point' : 'curves'))
  }
  const onKey = (e: React.KeyboardEvent<SVGSVGElement>) => {
    if (sel === null) return
    if ((e.key === 'Delete' || e.key === 'Backspace') && canDelete(pts, sel)) { e.preventDefault(); start(); write(pts.filter((_, j) => j !== sel)); commit('curves remove point'); setSel(null); return }
    const step = e.shiftKey ? 10 : 1
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] }[e.key]
    if (!d) return
    e.preventDefault(); start(); write(moveTo(pts, sel, pts[sel][0] + d[0], pts[sel][1] + d[1])); commit('curves nudge')
  }
  const k = S / 255
  return (
    <div className="tone-editor">
      <div className="segmented curves-ch">{CH.map(([key, label]) => <button key={key} type="button" className={ch === key ? 'active' : ''} onClick={() => { setCh(key); setSel(null) }}>{label}</button>)}</div>
      <svg ref={svg} className="curves-graph" viewBox={`-5 -5 ${S + 10} ${S + 10}`} tabIndex={0} onPointerDown={onDown} onKeyDown={onKey} onContextMenu={(e) => e.preventDefault()}
        aria-label="Curves: click adds a point · drag it off the graph, Ctrl-click or right-click removes it · arrows nudge">
        <rect x={0} y={0} width={S} height={S} fill="var(--bg2)" stroke="var(--line2)" />
        <HistogramBars bins={hist ? hist[ch] : null} w={S} h={S} colour={ch === 'rgb' ? 'var(--fg3)' : CH.find((c) => c[0] === ch)![2]} />
        {[64, 128, 192].map((v) => <g key={v}><line x1={v * k} y1={0} x2={v * k} y2={S} stroke="var(--line)" /><line x1={0} y1={v * k} x2={S} y2={v * k} stroke="var(--line)" /></g>)}
        <line x1={0} y1={S} x2={S} y2={0} stroke="var(--line2)" strokeDasharray="3 3" />
        {ch === 'rgb' && CH.slice(1).filter(([key]) => Array.isArray(params[key])).map(([key, , colour]) => <path key={key} d={curvePath(ptsOf(key), spline)} fill="none" stroke={colour} strokeWidth={1} opacity={0.6} />)}
        <path d={curvePath(pts, spline)} fill="none" stroke={CH.find((c) => c[0] === ch)![2]} strokeWidth={1.6} />
        {pts.map(([x, y], i) => <rect key={i} x={x * k - 3.5} y={S - y * k - 3.5} width={7} height={7} fill={i === sel ? 'var(--accent)' : 'var(--bg2)'} stroke="var(--fg)" strokeWidth={1} />)}
      </svg>
      <div className="tool-opts tone-fields">
        {sel !== null && pts[sel] ? <>
          <ValueField label="input" value={pts[sel][0]} min={0} max={255} onStart={start} onChange={(v) => write(moveTo(pts, sel, v, pts[sel][1]))} onCommit={() => commit('curves input')} />
          <ValueField label="output" value={pts[sel][1]} min={0} max={255} onStart={start} onChange={(v) => write(moveTo(pts, sel, pts[sel][0], v))} onCommit={() => commit('curves output')} />
        </> : <span className="hint full">Click to add a point · drag it off the graph, Ctrl-click or right-click to remove it · arrows nudge (Shift ×10)</span>}
        {!spline && <span className="hint full">An older curve with straight lines between its points; editing it turns it into a smooth curve like Photoshop's.</span>}
      </div>
    </div>
  )
}

// ---- Colour balance ----------------------------------------------------------------------------------------------
const ROWS = [['Cyan', 'Red', 'rgb(0,190,210)', 'rgb(225,40,40)'], ['Magenta', 'Green', 'rgb(210,40,190)', 'rgb(40,190,60)'], ['Yellow', 'Blue', 'rgb(230,210,30)', 'rgb(40,80,230)']] as const
const TONES = ['shadows', 'midtones', 'highlights'] as const
export function ColorBalanceEditor({ params, set, start, commit }: EditorProps) {
  const [tone, setTone] = useState<(typeof TONES)[number]>('midtones')
  const vals = (Array.isArray(params[tone]) ? params[tone] : [0, 0, 0]) as number[]
  const setRow = (i: number, v: number) => { const next = [0, 1, 2].map((j) => (j === i ? Math.round(v) : Number(vals[j]) || 0)); set({ ...params, [tone]: next }) }
  return (
    <div className="tone-editor">
      <div className="segmented">{TONES.map((t) => <button key={t} type="button" className={tone === t ? 'active' : ''} onClick={() => setTone(t)}>{t}</button>)}</div>
      {ROWS.map(([a, b, ca, cb], i) => (
        <div key={a} className="cb-row" title="double-click resets the row">
          <span>{a}</span>
          <input type="range" min={-100} max={100} step={1} value={Number(vals[i]) || 0} style={{ background: `linear-gradient(90deg, ${ca}, ${cb})` }}
            onPointerDown={start} onChange={(e) => setRow(i, Number(e.target.value))} onPointerUp={() => commit(`colour balance ${tone}`)}
            onKeyDown={(e) => { if (!e.repeat) start() }} onKeyUp={() => commit(`colour balance ${tone}`)} onDoubleClick={() => { start(); setRow(i, 0); commit(`colour balance ${tone}`) }} />
          <span>{b}</span><span className="val">{Number(vals[i]) || 0}</span>
        </div>
      ))}
    </div>
  )
}

