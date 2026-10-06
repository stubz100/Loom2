// Edit suite (10): toolbox and tool options in the Panel, zoom/overlay strip, PixiJS stage, inspector with
// Layers / Properties / History / Info; Save · Save to Catalogue · Export as the pinned primary actions.
import { Brush, Eye, EyeOff, Files, Lasso, Lock, LockOpen, SlidersHorizontal, Sparkles } from 'lucide-react'
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import { CommandButton, CommandRow, MenuButton } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { setRailTab, type SuiteDef } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import { adjustmentMenu, filterMenu, layerMenu } from './editCommands'
import { EditorCanvas } from './EditorCanvas'
import { BLEND_MODES, countRasters, ensureEditorAutosave, findNode, useEditor, walk, type DocSummary, type DocumentStack, type Node, type Tool } from './editorStore'
import { useAiPanel, type AiOp, type AiPanelState } from './aiPanelStore'
import './edit.css'

const TOOLS: { key: string; tool: Tool; label: string; later?: string }[] = [
  { key: 'V', tool: 'move', label: 'Move' }, { key: 'M', tool: 'marquee', label: 'Marquee' }, { key: 'L', tool: 'lasso', label: 'Lasso' }, { key: 'W', tool: 'wand', label: 'Magic wand' },
  { key: 'A', tool: 'ai', label: 'AI select' }, { key: 'B', tool: 'brush', label: 'Brush' }, { key: 'E', tool: 'eraser', label: 'Eraser' }, { key: 'G', tool: 'fill', label: 'Fill / gradient' },
  { key: 'I', tool: 'eyedropper', label: 'Eyedropper' }, { key: 'C', tool: 'crop', label: 'Crop / canvas' }, { key: 'H', tool: 'hand', label: 'Hand' }, { key: 'Z', tool: 'zoom', label: 'Zoom' },
]
/** min, max, step for the numeric adjustment / filter parameters (names from compose.py). */
const PARAM_RANGES: Record<string, [number, number, number]> = {
  in_black: [0, 255, 1], in_white: [0, 255, 1], out_black: [0, 255, 1], out_white: [0, 255, 1], gamma: [0.1, 5, 0.01],
  hue: [-180, 180, 1], saturation: [-100, 100, 1], lightness: [-100, 100, 1], brightness: [-100, 100, 1], contrast: [-100, 100, 1],
  exposure: [-5, 5, 0.01], offset: [-0.5, 0.5, 0.001], r: [0, 100, 1], g: [0, 100, 1], b: [0, 100, 1],
  radius: [0, 100, 0.1], amount: [0, 500, 1], threshold: [0, 255, 1], seed: [0, 99999, 1],
}
const BRUSH_PRESETS = [
  { name: 'hard round', hardness: 1, flow: 1, opacity: 1, spacing: 0.1, smoothing: 0.3 }, { name: 'soft round', hardness: 0.5, flow: 0.6, opacity: 1, spacing: 0.15, smoothing: 0.4 },
  { name: 'airbrush', hardness: 0.05, flow: 0.12, opacity: 1, spacing: 0.06, smoothing: 0.5 }, { name: 'inker', hardness: 0.95, flow: 1, opacity: 1, spacing: 0.04, smoothing: 0.75 },
]
const pct = (v: number) => `${Math.round(v * 100)} %`
const ed = () => useEditor.getState()
/** Mirrors edit_ai._engine_size: ≥ min on the longer side, ≤ max, ≤ 1 MP, multiples of 16. */
function planSize(w: number, h: number, minSize: number, maxSize: number, maxPixels = 1048576): { w: number; h: number; scale: number } {
  const longer = Math.max(w, h)
  let s = 1
  if (minSize && longer < minSize) s = minSize / longer
  if (maxSize && longer * s > maxSize) s = maxSize / longer
  if (maxPixels && w * h * s * s > maxPixels) s = Math.sqrt(maxPixels / (w * h))
  const r16 = (n: number) => Math.max(16, Math.ceil(n / 16) * 16)
  return { w: r16(w * s), h: r16(h * s), scale: s }
}
const snapshot = (d: DocumentStack): DocumentStack => JSON.parse(JSON.stringify(d))

function Slider({ label, value, min, max, step = 1, fmt, onChange, onStart, onCommit }: { label: string; value: number; min: number; max: number; step?: number; fmt?: (v: number) => string; onChange: (v: number) => void; onStart?: () => void; onCommit?: () => void }) {
  return (
    <>
      <label>{label}</label>
      <div className="slider">
        <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} onPointerDown={onStart} onPointerUp={onCommit} onKeyDown={(e) => { if (!e.repeat) onStart?.() }} onKeyUp={onCommit} />
        <span className="val">{fmt ? fmt(value) : String(Math.round(value * 1000) / 1000)}</span>
      </div>
    </>
  )
}

function Swatches() {
  const b = useEditor((s) => s.brush)
  return (
    <div className="swatch-pair">
      <span className="sw" style={{ background: b.color }} title="foreground"><input type="color" value={b.color} onChange={(e) => ed().setBrush({ color: e.target.value })} /></span>
      <span className="sw" style={{ background: b.background }} title="background"><input type="color" value={b.background} onChange={(e) => ed().setBrush({ background: e.target.value })} /></span>
      <CommandButton id="edit.colour.swap" /><CommandButton id="edit.colour.default" />
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Tool options
function Toolbox() {
  const tool = useEditor((s) => s.tool)
  return (
    <div className="toolbox">
      {TOOLS.map((x) => { markUsed(`edit.tool.${x.tool}`); return <button key={x.tool} className={`tool${tool === x.tool ? ' active' : ''}${x.later ? ' later' : ''}`} title={`${x.label} (${x.key})${x.later ? ` · arrives in ${x.later}` : ''}`} onClick={() => runCommand(`edit.tool.${x.tool}`)}><b>{x.key}</b><span>{x.label}</span></button> })}
    </div>
  )
}

function ToolOptions() {
  const tool = useEditor((s) => s.tool)
  const b = useEditor((s) => s.brush)
  const marqueeShape = useEditor((s) => s.marqueeShape)
  const mode = useEditor((s) => s.selectionMode)
  const tolerance = useEditor((s) => s.tolerance)
  const fillMode = useEditor((s) => s.fillMode)
  const doc = useEditor((s) => s.doc)
  const hasSel = useEditor((s) => !!s.selection)
  const activeId = useEditor((s) => s.activeId)
  const transforming = useEditor((s) => !!s.transform)
  const [cv, setCv] = useState({ w: 0, h: 0, ax: 0.5, ay: 0.5 })
  useEffect(() => { if (doc) setCv((c) => ({ ...c, w: doc.w, h: doc.h })) }, [doc?.w, doc?.h]) // eslint-disable-line react-hooks/exhaustive-deps
  const set = (p: Partial<typeof b>) => ed().setBrush(p)
  const nudge = (dx: number, dy: number) => { const n = findNode(doc, activeId); if (n?.kind === 'raster') ed().updateNode(n.id, { x: (n.x ?? 0) + dx, y: (n.y ?? 0) + dy }, 'nudge') }
  const modeSeg = <div className="segmented">{(['replace', 'add', 'subtract'] as const).map((m) => <button key={m} className={mode === m ? 'active' : ''} onClick={() => ed().setView({ selectionMode: m })}>{m}</button>)}</div>
  return (
    <div>
      <Toolbox />
      <h4 className="sect">{TOOLS.find((x) => x.tool === tool)?.label}</h4>
      {(tool === 'brush' || tool === 'eraser') && (
        <div className="tool-opts">
          <Slider label="size" value={b.size} min={1} max={512} fmt={(v) => `${v} px`} onChange={(v) => set({ size: v })} />
          <Slider label="hardness" value={b.hardness} min={0} max={1} step={0.01} fmt={pct} onChange={(v) => set({ hardness: v })} />
          <Slider label="opacity" value={b.opacity} min={0} max={1} step={0.01} fmt={pct} onChange={(v) => set({ opacity: v })} />
          <Slider label="flow" value={b.flow} min={0.01} max={1} step={0.01} fmt={pct} onChange={(v) => set({ flow: v })} />
          <Slider label="spacing" value={b.spacing} min={0.02} max={1} step={0.01} fmt={pct} onChange={(v) => set({ spacing: v })} />
          <Slider label="smoothing" value={b.smoothing} min={0} max={1} step={0.01} fmt={pct} onChange={(v) => set({ smoothing: v })} />
          {tool === 'brush' && <><label>colour</label><Swatches /></>}
          <label /><CommandRow ids={['edit.brush.smaller', 'edit.brush.larger', 'edit.brush.softer', 'edit.brush.harder']} />
          <span className="hint full">[ ] size · Shift+[ ] hardness · 0–9 opacity · X swap · D defaults · pressure controls appear once a pen is detected (D19)</span>
        </div>
      )}
      {tool === 'marquee' && <div className="tool-opts"><label>shape</label><div className="segmented">{(['rect', 'ellipse'] as const).map((m) => <button key={m} className={marqueeShape === m ? 'active' : ''} onClick={() => ed().setView({ marqueeShape: m })}>{m}</button>)}</div><label>mode</label>{modeSeg}<span className="hint full">Shift adds, Alt subtracts while dragging</span></div>}
      {tool === 'lasso' && <div className="tool-opts"><label>mode</label>{modeSeg}<span className="hint full">freehand; Shift adds, Alt subtracts</span></div>}
      {tool === 'wand' && <div className="tool-opts"><label>mode</label>{modeSeg}<Slider label="tolerance" value={tolerance} min={0} max={255} onChange={(v) => ed().setView({ tolerance: v })} /><span className="hint full">contiguous on the active raster layer</span></div>}
      {tool === 'fill' && <div className="tool-opts"><label>mode</label><div className="segmented">{(['solid', 'linear', 'radial'] as const).map((m) => <button key={m} className={fillMode === m ? 'active' : ''} onClick={() => ed().setView({ fillMode: m })}>{m}</button>)}</div><label>colour</label><Swatches /><Slider label="opacity" value={b.opacity} min={0} max={1} step={0.01} fmt={pct} onChange={(v) => set({ opacity: v })} /><span className="hint full">{fillMode === 'solid' ? 'click fills the selection, or the whole layer (mask: white) when nothing is selected' : `drag from the foreground colour to the background colour (${fillMode}); limited to the selection when there is one; on a mask: white → black`}</span></div>}
      {tool === 'move' && (
        <div className="tool-opts">
          <label>nudge</label><div className="nudge"><button onClick={() => nudge(0, -1)}>▲</button><button onClick={() => nudge(-1, 0)}>◀</button><button onClick={() => nudge(1, 0)}>▶</button><button onClick={() => nudge(0, 1)}>▼</button></div>
          <label>transform</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{transforming ? <CommandRow ids={['edit.transform.apply', 'edit.transform.cancel']} /> : <CommandButton id="edit.transform" text />}<CommandRow ids={['edit.layer.flipH', 'edit.layer.flipV', 'edit.layer.rot270', 'edit.layer.rot90']} /></div>
          <span className="hint full">{transforming ? 'drag inside to move, handles to scale (Shift keeps the ratio), outside to rotate (Shift snaps 15°); Enter / double-click applies, Esc cancels' : 'drag the active raster layer on the canvas; Ctrl+T enters free transform'}</span>
        </div>
      )}
      {tool === 'crop' && (
        <div className="tool-opts">
          <label>canvas</label><div><input type="number" value={cv.w} min={1} max={16384} onChange={(e) => setCv({ ...cv, w: Number(e.target.value) })} style={{ width: 76 }} /> × <input type="number" value={cv.h} min={1} max={16384} onChange={(e) => setCv({ ...cv, h: Number(e.target.value) })} style={{ width: 76 }} /></div>
          <label>anchor</label><div className="anchor">{[0, 0.5, 1].map((ay) => [0, 0.5, 1].map((ax) => <button key={`${ax}-${ay}`} className={cv.ax === ax && cv.ay === ay ? 'active' : ''} onClick={() => setCv({ ...cv, ax, ay })}>•</button>))}</div>
          <label /><div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}><button disabled={!doc || (cv.w === doc.w && cv.h === doc.h)} onClick={() => ed().resizeCanvas(cv.w, cv.h, cv.ax, cv.ay)}>Resize canvas</button><button disabled={!hasSel} onClick={() => ed().cropToSelection()}>Crop to selection</button></div>
          <span className="hint full">layers keep their pixels; a smaller canvas only hides what lies outside</span>
        </div>
      )}
      {tool === 'eyedropper' && <p className="hint">Click the canvas to pick the composited colour into the foreground swatch.</p>}
      {tool === 'hand' && <p className="hint">Drag to pan. Space + drag pans with any tool; middle mouse too.</p>}
      {tool === 'zoom' && <p className="hint">Click zooms in, Alt-click out; Ctrl+wheel zooms anywhere; Ctrl+0 fit, Ctrl+1 1:1.</p>}
      {tool === 'ai' && <SelectControls compact />}
    </div>
  )
}

function BrushesTab() {
  const b = useEditor((s) => s.brush)
  return (
    <div>
      <div className="brush-presets">
        {BRUSH_PRESETS.map((p) => <button key={p.name} className={Math.abs(b.hardness - p.hardness) < 0.01 && Math.abs(b.flow - p.flow) < 0.01 ? 'active' : ''} onClick={() => ed().setBrush({ hardness: p.hardness, flow: p.flow, opacity: p.opacity, spacing: p.spacing, smoothing: p.smoothing })}>
          <span className="dab" style={{ background: `radial-gradient(circle, ${b.color} ${Math.round(p.hardness * 100)}%, transparent 100%)`, opacity: Math.max(0.35, p.flow) }} />{p.name}
        </button>)}
      </div>
      <p className="hint">Presets set hardness, flow, spacing and smoothing; size and colour stay. Saving custom presets and the pen pressure curve arrive with the tablet (D19).</p>
    </div>
  )
}

function SelectionTab() {
  const hasSel = useEditor((s) => !!s.selection)
  const quickMask = useEditor((s) => s.quickMask)
  const activeId = useEditor((s) => s.activeId)
  const doc = useEditor((s) => s.doc)
  const [feather, setFeather] = useState(4)
  const n = findNode(doc, activeId)
  void n
  return (
    <div className="tool-opts">
      <label>select</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.sel.all', 'edit.sel.none', 'edit.sel.invert'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <label>feather</label><div style={{ display: 'flex', gap: 6, alignItems: 'center' }}><input type="number" min={0} max={200} value={feather} onChange={(e) => setFeather(Number(e.target.value))} style={{ width: 70 }} /> px <button disabled={!hasSel} onClick={() => ed().featherSelection(feather)}>apply</button></div>
      <label>quick mask</label><button className={quickMask ? 'active' : ''} onClick={() => runCommand('edit.sel.quickMask')} title="Quick mask (Q)">{quickMask ? 'painting the selection (red = unselected)' : 'paint the selection with the brush'}</button>
      <label>mask</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.mask.fromSelection', 'edit.mask.load', 'edit.sel.crop'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <span className="hint full">Expand / contract and the AI selectors (SAM, BiRefNet) arrive in M5.</span>
    </div>
  )
}

// AI panel settings live in aiPanelStore.ts (shared with the A-tool options)

/** AI Select (10 §4, M5 slice 2): shared by the AI tab's Select operation and the A tool's options. */
function SelectControls({ compact = false }: { compact?: boolean }) {
  const p = useAiPanel()
  const setP = p.set
  const models = useSession((s) => s.models)
  const aiPrompt = useEditor((s) => s.aiPrompt)
  const doc = useEditor((s) => s.doc)
  const health = (id: string) => models.find((m) => m.id === id)?.health ?? 'missing'
  const sam = p.selModel === 'sam3'
  const pos = aiPrompt.points.filter((q) => q.label === 1).length, neg = aiPrompt.points.length - pos
  const reason = !doc ? 'no document' : health(p.selModel) === 'missing' ? `weights missing: fetch ${p.selModel} in Models`
    : sam && p.selMode === 'text' && !p.selText.trim() ? 'type what to select' : sam && p.selMode === 'points' && !pos ? 'click the subject on the canvas (Alt-click excludes)'
    : sam && p.selMode === 'box' && !aiPrompt.box ? 'drag a box on the canvas' : null
  const run = (stage = false) => void ed().runAi({ kind: 'segment', model_id: p.selModel, mode: sam ? p.selMode : 'subject', text: p.selText, points: aiPrompt.points, box: aiPrompt.box,
    threshold: p.selThreshold, op: p.selOp, expand: p.selExpand, feather: p.selFeather, seeds: [0] }, stage)
  return (
    <div className="tool-opts">
      <label>model</label><div className="segmented"><button className={!sam ? 'active' : ''} onClick={() => setP({ selModel: 'birefnet', selMode: 'subject' })}>Subject · BiRefNet</button><button className={sam ? 'active' : ''} onClick={() => setP({ selModel: 'sam3', selMode: p.selMode === 'subject' ? 'text' : p.selMode })}>SAM 3</button></div>
      {sam && <>
        <label>prompt</label><div className="segmented">{(['text', 'points', 'box'] as const).map((m) => <button key={m} className={p.selMode === m ? 'active' : ''} onClick={() => setP({ selMode: m })}>{m}</button>)}</div>
        {p.selMode === 'text' && <><label>text</label><input type="text" value={p.selText} placeholder='"the woman in the green cloak"' onChange={(e) => setP({ selText: e.target.value })} /></>}
        {p.selMode === 'points' && <><label>points</label><div>{pos} include · {neg} exclude <button className="quiet" disabled={!aiPrompt.points.length} onClick={() => ed().setAiPrompt({ points: [] })}>clear</button></div></>}
        {p.selMode === 'box' && <><label>box</label><div>{aiPrompt.box ? `${aiPrompt.box[2] - aiPrompt.box[0]}×${aiPrompt.box[3] - aiPrompt.box[1]} at ${aiPrompt.box[0]},${aiPrompt.box[1]}` : 'none'} <button className="quiet" disabled={!aiPrompt.box} onClick={() => ed().setAiPrompt({ box: null })}>clear</button></div></>}
        <Slider label="threshold" value={p.selThreshold} min={0.05} max={0.95} step={0.05} fmt={(v) => v.toFixed(2)} onChange={(v) => setP({ selThreshold: v })} />
      </>}
      <label>combine</label><div className="segmented">{(['replace', 'add', 'subtract', 'intersect'] as const).map((m) => <button key={m} className={p.selOp === m ? 'active' : ''} onClick={() => setP({ selOp: m })}>{m}</button>)}</div>
      <Slider label="expand" value={p.selExpand} min={-64} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ selExpand: v })} />
      <Slider label="feather" value={p.selFeather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ selFeather: v })} />
      <label /><div style={{ display: 'flex', gap: 6 }}><button className="primary" disabled={!!reason} onClick={() => run(false)} title="AI Select">Select ▶</button>{!compact && <button disabled={!!reason} onClick={() => run(true)}>Stage</button>}</div>
      {reason && <span className="hint full">{reason}</span>}
      <span className="hint full">{sam ? 'A tool on the canvas: click adds an include point, Alt-click an exclude point, drag draws a box · the mask joins the selection as chosen (SAM 3 ≈ 3 s warm)' : 'BiRefNet matte of the main subject (≈ 2 s warm) · for a background swap: Select, then invert the selection (Selection panel) and Inpaint'}</span>
    </div>
  )
}

function AiTab() {
  const p = useAiPanel()
  const setP = p.set
  const doc = useEditor((s) => s.doc)
  const hasSel = useEditor((s) => !!s.selection)
  const activeId = useEditor((s) => s.activeId)
  const active = findNode(doc, activeId)
  const models = useSession((s) => s.models)
  const jobs = useSession((s) => s.jobs)
  const running = useMemo(() => Object.values(jobs).filter((j) => (j.recipe as { document_id?: string }).document_id === doc?.id && ['running', 'queued', 'staged'].includes(j.status)), [jobs, doc?.id])
  const health = (id: string) => models.find((m) => m.id === id)?.health ?? 'missing'
  const seeds = () => { const n = Math.max(1, Math.min(4, p.candidates)); return Array.from({ length: n }, (_, i) => (p.seedMode === 'random' ? Math.floor(Math.random() * 2 ** 31) : p.seed + i)) }
  const hero = p.op === 'inpaint' ? p.mode === 'fill_hero' : p.op === 'outpaint' ? p.outpaintHero : p.op === 'refine' ? p.refineModel === 'flux2-dev-fp8mixed' : false
  const revision = useEditor((s) => s.revision)
  // the engine image the orchestrator will build (edit_ai.plan_region): shown so a big region is a conscious choice
  const engineSize = useMemo(() => {
    const st = ed(); const sel = st.selection; const d = st.doc
    if (!d) return null
    if (p.op === 'outpaint') { const w = d.w + p.pad.left + p.pad.right, h = d.h + p.pad.top + p.pad.bottom; return planSize(w, h, 0, 2048) }
    if (p.op !== 'inpaint' || !sel) return null
    const img = sel.ctx.getImageData(0, 0, sel.width, sel.height).data
    let x0 = sel.width, y0 = sel.height, x1 = -1, y1 = -1
    for (let y = 0; y < sel.height; y++) for (let x = 0; x < sel.width; x++) if (img[(y * sel.width + x) * 4] > 0) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y }
    if (x1 < 0) return null
    const m = Math.max(32, Math.round(Math.max(x1 + 1 - x0, y1 + 1 - y0) * p.margin / 100))
    const w = Math.min(d.w, Math.ceil((x1 + 1 - x0 + 2 * m) / 16) * 16), h = Math.min(d.h, Math.ceil((y1 + 1 - y0 + 2 * m) / 16) * 16)
    return planSize(w, h, p.minSize, 2048)
  }, [revision, p.op, p.margin, p.minSize, p.pad]) // eslint-disable-line react-hooks/exhaustive-deps
  const reason = !doc ? 'no document' : p.op === 'select' ? null : p.op === 'inpaint' && !hasSel ? 'select the region to repaint first (M, L, W, Q or AI select)'
    : p.op === 'refine' && p.refineSource === 'selection' && !hasSel ? 'no selection' : (p.op === 'refine' || p.op === 'upscale') && (p.op === 'refine' ? p.refineSource : p.upscaleSource) === 'active' && active?.kind !== 'raster' ? 'the active layer is not a raster layer'
    : p.op === 'upscale' && health(p.upscaleModel) === 'missing' ? `weights missing: fetch ${p.upscaleModel} in Models` : p.op === 'outpaint' && !Object.values(p.pad).some((v) => v > 0) ? 'set at least one side' : null
  const run = (stage = false) => {
    const base = { seeds: seeds(), prompt_text: p.prompt }
    if (p.op === 'inpaint') void ed().runAi({ kind: 'inpaint', mode: p.mode, model_id: 'klein-9b', margin_pct: p.margin, min_size: p.minSize, feather: p.feather, expand: p.expand, prompt_mode: p.promptMode, ...base }, stage)
    else if (p.op === 'outpaint') void ed().runAi({ kind: 'inpaint', mode: 'outpaint', model_id: p.outpaintHero ? 'flux2-dev-fp8mixed' : 'klein-9b', outpaint: p.pad, feather: p.feather, prompt_mode: p.promptMode, ...base }, stage)
    else if (p.op === 'refine') void ed().runAi({ kind: 'i2i', model_id: p.refineModel, source: p.refineSource, layer_id: activeId, strength: p.strength, margin_pct: p.margin, feather: p.feather, ...base }, stage)
    else void ed().runAi({ kind: 'upscale', model_id: p.upscaleModel, source: p.upscaleSource, layer_id: activeId, as_layer: p.asLayer, seeds: p.refineTiled ? seeds().slice(0, 1) : [0],
      refine: p.refineTiled, refine_model_id: p.tiledModel, strength: p.tiledStrength, tile: p.tile, overlap: p.overlap, prompt_text: p.prompt }, stage)
  }
  const ops: [AiOp, string][] = [['select', 'Select'], ['inpaint', 'Inpaint'], ['refine', 'Refine'], ['upscale', 'Upscale'], ['outpaint', 'Outpaint']]
  return (
    <div>
      <div className="segmented" style={{ marginBottom: 10 }}>{ops.map(([k, l]) => <button key={k} className={p.op === k ? 'active' : ''} onClick={() => setP({ op: k, candidates: k === 'inpaint' || k === 'outpaint' || k === 'refine' ? (hero ? 2 : 4) : 1 })}>{l}</button>)}</div>
      {p.op === 'select' && <SelectControls />}
      {p.op !== 'select' && <div className="tool-opts">
        {p.op === 'inpaint' && <>
          <label>mode</label><select value={p.mode} onChange={(e) => { const mode = e.target.value as AiPanelState['mode']; setP({ mode, candidates: mode === 'fill_hero' ? 2 : 4 }) }}>
            <option value="fill">Fill — Klein + LanPaint (default)</option><option value="fill_match">Fill-Match — Klein ICM, continues texture</option><option value="fill_hero">Fill Hero — FLUX.2 dev + LanPaint (slow, best detail)</option><option value="remove">Remove — background-only prompt</option>
          </select>
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder={p.mode === 'remove' ? 'what is behind: "wet cobblestones and a brick wall"' : 'what to paint there'} onChange={(e) => setP({ prompt: e.target.value })} />
          {p.mode !== 'fill_match' && p.mode !== 'remove' && <><label>LanPaint</label><div className="segmented"><button className={p.promptMode === 'image_first' ? 'active' : ''} onClick={() => setP({ promptMode: 'image_first' })}>image first</button><button className={p.promptMode === 'prompt_first' ? 'active' : ''} onClick={() => setP({ promptMode: 'prompt_first' })}>prompt first</button></div></>}
          <Slider label="margin" value={p.margin} min={0} max={100} fmt={(v) => `${v} %`} onChange={(v) => setP({ margin: v })} />
          <Slider label="min size" value={p.minSize} min={512} max={2048} step={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ minSize: v })} />
          <Slider label="feather" value={p.feather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ feather: v })} />
          <Slider label="expand" value={p.expand} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ expand: v })} />
        </>}
        {p.op === 'outpaint' && <>
          <label>grow</label><div className="pad-grid">{(['left', 'top', 'right', 'bottom'] as const).map((k) => <label key={k}>{k}<input type="number" min={0} max={2048} step={16} value={p.pad[k]} onChange={(e) => setP({ pad: { ...p.pad, [k]: Math.max(0, Number(e.target.value)) } })} /></label>)}</div>
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder="what continues beyond the edge" onChange={(e) => setP({ prompt: e.target.value })} />
          <label>model</label><div className="segmented"><button className={!p.outpaintHero ? 'active' : ''} onClick={() => setP({ outpaintHero: false, candidates: 4 })}>Klein + LanPaint</button><button className={p.outpaintHero ? 'active' : ''} onClick={() => setP({ outpaintHero: true, candidates: 2 })}>dev (hero)</button></div>
          <Slider label="feather" value={p.feather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ feather: v })} />
        </>}
        {p.op === 'refine' && <>
          <label>model</label><select value={p.refineModel} onChange={(e) => setP({ refineModel: e.target.value, candidates: e.target.value === 'flux2-dev-fp8mixed' ? 2 : 4 })}><option value="klein-base-9b">Klein 9B base (CFG, negatives)</option><option value="flux2-dev-fp8mixed">FLUX.2 dev + Turbo</option></select>
          <label>on</label><div className="segmented">{(['visible', 'active', 'selection'] as const).map((s) => <button key={s} className={p.refineSource === s ? 'active' : ''} onClick={() => setP({ refineSource: s })}>{s}</button>)}</div>
          <Slider label="strength" value={p.strength} min={0.1} max={0.8} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => setP({ strength: v })} />
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder="defaults to the source asset's prompt when empty" onChange={(e) => setP({ prompt: e.target.value })} />
          {p.refineSource === 'selection' && <Slider label="feather" value={p.feather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ feather: v })} />}
        </>}
        {p.op === 'upscale' && <>
          <label>model</label><select value={p.upscaleModel} onChange={(e) => setP({ upscaleModel: e.target.value })}><option value="realesrgan-x2">Real-ESRGAN 2× {health('realesrgan-x2') === 'missing' ? '(not fetched)' : ''}</option><option value="realesrgan-x4">Real-ESRGAN 4× {health('realesrgan-x4') === 'missing' ? '(not fetched)' : ''}</option></select>
          <label>on</label><div className="segmented">{(['visible', 'active'] as const).map((s) => <button key={s} className={p.upscaleSource === s ? 'active' : ''} onClick={() => setP({ upscaleSource: s })}>{s}</button>)}</div>
          <label>result</label><label className="chk"><input type="checkbox" checked={p.asLayer} onChange={(e) => setP({ asLayer: e.target.checked })} /> also add a 1× detail layer (the full-size image goes to the Catalogue)</label>
          <label>refine</label><label className="chk"><input type="checkbox" checked={p.refineTiled} onChange={(e) => setP({ refineTiled: e.target.checked })} /> tiled refine after the upscale (10 §4: re-sample every tile at low strength)</label>
          {p.refineTiled && <>
            <label>model</label><select value={p.tiledModel} onChange={(e) => setP({ tiledModel: e.target.value })}><option value="klein-base-9b">Klein 9B base</option><option value="flux2-dev-fp8mixed">FLUX.2 dev + Turbo (slow)</option></select>
            <Slider label="strength" value={p.tiledStrength} min={0.05} max={0.6} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => setP({ tiledStrength: v })} />
            <Slider label="tile" value={p.tile} min={512} max={2048} step={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ tile: v })} />
            <Slider label="overlap" value={p.overlap} min={0} max={256} step={16} fmt={(v) => `${v} px`} onChange={(v) => setP({ overlap: v })} />
            <label>prompt</label><textarea value={p.prompt} rows={2} placeholder="what the image shows (helps the refine keep its subject)" onChange={(e) => setP({ prompt: e.target.value })} />
          </>}
        </>}
        {p.op !== 'upscale' && <>
          <Slider label="candidates" value={p.candidates} min={1} max={4} onChange={(v) => setP({ candidates: v })} />
          <label>seed</label><div><div className="segmented">{(['random', 'fixed'] as const).map((m) => <button key={m} className={p.seedMode === m ? 'active' : ''} onClick={() => setP({ seedMode: m })}>{m}</button>)}</div>{p.seedMode === 'fixed' && <input type="number" value={p.seed} onChange={(e) => setP({ seed: Number(e.target.value) })} style={{ width: 120, marginLeft: 6 }} />}</div>
        </>}
      </div>}
      {p.op !== 'select' && <div style={{ display: 'flex', gap: 6, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="primary" disabled={!!reason} onClick={() => run(false)} title="Ctrl+Enter">AI ▶ {ops.find(([k]) => k === p.op)?.[1]}{p.op !== 'upscale' ? ` ×${p.candidates}` : ''}</button>
        <button disabled={!!reason} onClick={() => run(true)} title="add to the queue as staged">Stage</button>
        {running.length > 0 && <span className="kind">{running.filter((j) => j.status === 'running').length ? `running · ${Math.round((running.find((j) => j.status === 'running')?.progress ?? 0) * 100)} %` : `${running.length} queued`}</span>}
      </div>}
      {reason && <p className="hint" style={{ marginTop: 6 }}>{reason}</p>}
      {engineSize && <p className="hint" style={{ marginTop: 6 }}>engine image ≈ {engineSize.w}×{engineSize.h} ({engineSize.scale > 1.01 ? `upscaled ×${engineSize.scale.toFixed(2)}` : engineSize.scale < 0.99 ? `downscaled ×${engineSize.scale.toFixed(2)} to stay within 1 MP` : '1:1'})</p>}
      {p.op !== 'select' && <p className="hint" style={{ marginTop: 8 }}>Runs on the saved document; results come back as layers in an "AI" group with the recipe attached. {hero ? 'Hero / dev: ≈ 4–5 min per candidate.' : p.op === 'upscale' && p.refineTiled ? 'Tiled refine: ≈ 30–45 s per 1024² tile on Klein base.' : 'Klein: ≈ 20–35 s per candidate incl. model swap (E8).'}</p>}
    </div>
  )
}

function CandidateStrip() {
  const cands = useEditor((s) => s.candidates)
  const revision = useEditor((s) => s.revision)
  const doc = useEditor((s) => s.doc)
  const thumbs = useMemo(() => { const st = ed(); const m = new Map<string, string>(); cands?.ids.forEach((id) => { const lp = st.pixels.get(id); if (lp) m.set(id, lp.thumbnail(96)) }); return m }, [cands, revision]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!cands || !doc) return null
  const g = findNode(doc, cands.group)
  return (
    <div className="cand-strip">
      <span className="muted">{g?.name ?? 'candidates'} — pick one (1–4, Enter keeps the visible one) or keep all:</span>
      {cands.ids.map((id, i) => { const n = findNode(doc, id); return (
        <button key={id} className={`cand${n?.visible ? ' on' : ''}`} title={`candidate ${i + 1} · seed ${(n?.recipe as { seed?: number } | undefined)?.seed ?? '?'}`} onMouseEnter={() => { const st = ed(); st.updateNode(id, { visible: true }); cands.ids.filter((o) => o !== id).forEach((o) => st.updateNode(o, { visible: false })) }} onClick={() => ed().pickCandidate(id)}>
          {thumbs.get(id) ? <img src={thumbs.get(id)} alt="" /> : <span className="muted">…</span>}<b>{i + 1}</b>
        </button>
      ) })}
      <button className="quiet" onClick={() => ed().pickCandidate(null)}>keep all</button>
    </div>
  )
}

function DocumentsTab() {
  const [items, setItems] = useState<DocSummary[]>([])
  const docId = useEditor((s) => s.doc?.id)
  const savedAt = useEditor((s) => s.doc?.saved_at)
  const [form, setForm] = useState({ w: 1920, h: 1080, name: 'Untitled' })
  const refresh = () => { void ed().listDocuments().then(setItems).catch(() => undefined) }
  useEffect(refresh, [docId, savedAt])
  return (
    <div>
      <div className="tool-opts">
        <label>new</label><div><input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ width: 120 }} /> <input type="number" value={form.w} step={16} min={64} max={8192} onChange={(e) => setForm({ ...form, w: Number(e.target.value) })} style={{ width: 70 }} /> × <input type="number" value={form.h} step={16} min={64} max={8192} onChange={(e) => setForm({ ...form, h: Number(e.target.value) })} style={{ width: 70 }} /></div>
        <label /><button onClick={() => void ed().newDocument(form.w, form.h, form.name)}>New document</button>
      </div>
      <h4 className="sect">DOCUMENTS IN THIS PROJECT</h4>
      <div className="doc-list">
        {items.map((d) => (
          <div key={d.id} className={`doc-row${d.id === docId ? ' active' : ''}`} onClick={() => { if (d.id !== docId) void ed().openDocument(d.id) }}>
            <img src={api.fileUrl(`/documents/${d.id}/thumbnail`)} alt="" loading="lazy" onError={(e) => { (e.target as HTMLImageElement).style.visibility = 'hidden' }} />
            <div className="t"><b>{d.name}</b><span className="kind">{d.w}×{d.h} · {d.layers} layer{d.layers === 1 ? '' : 's'} · {d.saved_at ? new Date(d.saved_at).toLocaleString() : 'unsaved'}{d.open ? ' · open' : ''}</span></div>
            <button className="quiet" title="delete the .ora" onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete document "${d.name}"? The .ora file is removed.`)) void ed().deleteDocument(d.id).then(refresh) }}>✕</button>
          </div>
        ))}
        {!items.length && <span className="muted">No documents yet. Select an asset in the Catalogue and press E.</span>}
      </div>
    </div>
  )
}

function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  if (!project?.open) return <span className="muted">Open or create a project.</span>
  if (tab === 'brushes') return <BrushesTab />
  if (tab === 'selection') return <SelectionTab />
  if (tab === 'ai') return <AiTab />
  if (tab === 'documents') return <DocumentsTab />
  return <ToolOptions />
}

function PrimaryAction() {
  const doc = useEditor((s) => s.doc)
  const dirty = useEditor((s) => s.docDirty)
  const saving = useEditor((s) => s.saving)
  if (!doc) return <div className="estimate"><span className="muted">no document open</span></div>
  markUsed('edit.save')
  return (
    <div>
      <button className="primary" disabled={saving} onClick={() => runCommand('edit.save')} title="Save (⌃S)">{saving ? 'Saving…' : dirty ? 'Save •' : 'Save'}</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        <CommandButton id="edit.saveToCatalogue" text /><CommandButton id="edit.exportPng" text /><CommandButton id="edit.exportPsd" text /><CommandButton id="edit.close" text />
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip / Stage
function Strip() {
  useEditKeys()
  const doc = useEditor((s) => s.doc)
  const dirty = useEditor((s) => s.docDirty)
  const zoom = useEditor((s) => s.zoom)
  const pixelGrid = useEditor((s) => s.pixelGrid)
  const overlay = useEditor((s) => s.overlay)
  const before = useEditor((s) => s.before)
  const quickMask = useEditor((s) => s.quickMask)
  const cursor = useEditor((s) => s.cursor)
  const renderer = useEditor((s) => s.renderer)
  const transforming = useEditor((s) => !!s.transform)
  const [zt, setZt] = useState<string | null>(null)
  const apply = () => { if (zt !== null) { const v = parseFloat(zt); if (v > 0) ed().zoomTo(v / 100) } setZt(null) }
  return (
    <>
      <span>{doc ? `${doc.name}${dirty ? ' •' : ''} · ${doc.w}×${doc.h}` : 'Edit'}</span>
      {transforming && <><span style={{ color: 'var(--accent)' }}>free transform</span><CommandRow ids={['edit.transform.apply', 'edit.transform.cancel']} /></>}
      <CommandRow ids={['edit.undo', 'edit.redo', 'gap', 'edit.view.zoomOut']} />
      <input className="edit-strip-zoom" value={zt ?? String(Math.round(zoom * 100))} onChange={(e) => setZt(e.target.value)} onBlur={apply} onKeyDown={(e) => { if (e.key === 'Enter') apply() }} disabled={!doc} /><span style={{ marginLeft: -4 }}>%</span>
      <CommandRow ids={['edit.view.zoomIn', 'edit.view.fit']} />
      <CommandButton id="edit.view.100" text />
      <label className="chk" title="Pixel grid (shown from 800 %)"><input type="checkbox" checked={pixelGrid} onChange={() => { markUsed('edit.view.grid'); runCommand('edit.view.grid') }} /> pixel grid</label>
      <label className="chk" title="Mask overlay (⌥\)"><input type="checkbox" checked={overlay} onChange={() => { markUsed('edit.view.overlay'); runCommand('edit.view.overlay') }} /> mask overlay</label>
      <button className={`quiet${before ? ' active' : ''}`} onPointerDown={() => ed().setView({ before: true })} onPointerUp={() => ed().setView({ before: false })} onPointerLeave={() => { if (before) ed().setView({ before: false }) }} disabled={!doc} title="Before: hold to hide the active layer (hold \)">before</button>
      <button className={`quiet${quickMask ? ' active' : ''}`} onClick={() => { markUsed('edit.view.before'); runCommand('edit.sel.quickMask') }} disabled={!doc} title="Quick mask (Q)">quick mask</button>
      <span className="spacer" />
      {cursor && <span className="mono">{cursor.x}, {cursor.y}</span>}
      <span className="badge-renderer">{renderer}</span>
    </>
  )
}

function RecentDocuments() {
  const [items, setItems] = useState<DocSummary[]>([])
  useEffect(() => { void ed().listDocuments().then((x) => setItems(x.slice(0, 8))).catch(() => undefined) }, [])
  if (!items.length) return null
  return <p style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>{items.map((d) => <button key={d.id} onClick={() => void ed().openDocument(d.id)}>{d.name} <span className="kind">{d.w}×{d.h}</span></button>)}</p>
}

function Stage() {
  const project = useSession((s) => s.project)
  const doc = useEditor((s) => s.doc)
  const loading = useEditor((s) => s.loading)
  const error = useEditor((s) => s.error)
  if (!project?.open) return <div className="placeholder"><div><h2>Edit</h2>open or create a project to begin</div></div>
  if (!doc) return (
    <div className="edit-empty"><div>
      <h2>Edit</h2>
      {loading ? <p>loading document…</p> : <>
        <p>Select an asset in the Catalogue and press <kbd>E</kbd>, or start empty.</p>
        <p><button onClick={() => void ed().newDocument(1920, 1080)}>New 1920×1080 document</button> <button onClick={() => useSession.getState().setSuite('catalogue')}>Open the Catalogue</button></p>
        <RecentDocuments />
      </>}
      {error && <p style={{ color: 'var(--error)' }}>{error}</p>}
    </div></div>
  )
  return <><EditorCanvas /><CandidateStrip /></>
}

// ------------------------------------------------------------------ Inspector
function LayersTab() {
  const doc = useEditor((s) => s.doc)!
  const activeId = useEditor((s) => s.activeId)
  const editingMask = useEditor((s) => s.editingMask)
  const revision = useEditor((s) => s.revision)
  const hasSel = useEditor((s) => !!s.selection)
  const thumbs = useMemo(() => { const st = ed(); const m = new Map<string, string>(); st.pixels.forEach((lp, id) => m.set(id, lp.thumbnail(64))); st.masks.forEach((lp, id) => m.set('m:' + id, lp.thumbnail(48))); return m }, [revision]) // eslint-disable-line react-hooks/exhaustive-deps
  const before = useRef<DocumentStack | null>(null)
  const active = findNode(doc, activeId)
  const start = () => { before.current = snapshot(doc) }
  const commit = (label: string) => { if (before.current && active) { ed().pushHistory({ label, layerId: active.id, kind: 'image', tiles: [], stack: before.current, at: Date.now() }); before.current = null } }
  const rows = (nodes: Node[], depth: number): ReactNode => nodes.map((n) => (
    <div key={n.id}>
      <div className={`layer-row${n.id === activeId ? ' active' : ''}${n.visible ? '' : ' hidden'}`} style={{ marginLeft: depth * 14 }} tabIndex={0} onClick={() => ed().setActive(n.id, false)}
        onDoubleClick={() => runCommand('edit.layer.rename')} onContextMenu={(e) => { ed().setActive(n.id, false); showMenu(e, layerMenu()) }}>
        <button className={`eye${n.visible ? ' on' : ''}`} title="visibility · Alt-click: solo" onClick={(e) => { e.stopPropagation(); if (e.altKey) ed().solo(n.id); else ed().updateNode(n.id, { visible: !n.visible }, n.visible ? 'hide layer' : 'show layer') }}>{n.visible ? <Eye size={14} /> : <EyeOff size={14} />}</button>
        <button className={`lock${n.locked ? ' on' : ''}`} title="lock" onClick={(e) => { e.stopPropagation(); ed().updateNode(n.id, { locked: !n.locked }) }}>{n.locked ? <Lock size={12} /> : <LockOpen size={12} />}</button>
        {n.kind === 'raster' ? <img className="thumb" src={thumbs.get(n.id)} alt="" /> : <span className="thumb kind-box">{n.kind === 'group' ? '▣' : n.kind === 'adjustment' ? '◐' : 'fx'}</span>}
        <span className="name">{n.name}<br /><span className="kind">{n.kind === 'raster' ? `${n.w}×${n.h}` : n.kind === 'group' ? `${n.children?.length ?? 0} · ${n.passthrough ? 'pass-through' : 'isolated'}` : n.type}{n.clip ? ' · clip' : ''}{n.blend !== 'normal' ? ` · ${n.blend}` : ''}{n.opacity < 1 ? ` · ${Math.round(n.opacity * 100)} %` : ''}</span></span>
        {n.mask
          ? <img className={`thumb mask-thumb${editingMask && n.id === activeId ? ' editing' : ''}${n.mask.enabled ? '' : ' off'}`} src={thumbs.get('m:' + n.id)} alt="" title="mask · click to edit · Shift-click to disable" onClick={(e) => { e.stopPropagation(); if (e.shiftKey) ed().updateNode(n.id, { mask: { ...n.mask!, enabled: !n.mask!.enabled } }, 'toggle mask'); else ed().setActive(n.id, true) }} />
          : <span className="mask-box" title={hasSel ? 'add a mask from the selection' : 'add a mask'} onClick={(e) => { e.stopPropagation(); ed().addMask(n.id, hasSel) }}>+◐</span>}
      </div>
      {n.kind === 'group' && n.children && rows(n.children, depth + 1)}
    </div>
  ))
  return (
    <div>
      <div className="layers">{rows(doc.layers, 0)}</div>
      {active && (
        <div className="tool-opts" style={{ marginTop: 10 }}>
          <label>blend</label><select value={active.blend} onChange={(e) => ed().updateNode(active.id, { blend: e.target.value }, 'blend mode')}>{BLEND_MODES.map((m) => <option key={m}>{m}</option>)}</select>
          <Slider label="opacity" value={active.opacity} min={0} max={1} step={0.01} fmt={pct} onStart={start} onChange={(v) => ed().updateNode(active.id, { opacity: v })} onCommit={() => commit('opacity')} />
          {active.kind === 'raster' && <Slider label="fill" value={active.fill ?? 1} min={0} max={1} step={0.01} fmt={pct} onStart={start} onChange={(v) => ed().updateNode(active.id, { fill: v })} onCommit={() => commit('fill')} />}
          {active.kind === 'group' && <><label>group</label><div className="segmented"><button className={active.passthrough ? 'active' : ''} onClick={() => ed().updateNode(active.id, { passthrough: true }, 'group mode')}>pass-through</button><button className={!active.passthrough ? 'active' : ''} onClick={() => ed().updateNode(active.id, { passthrough: false }, 'group mode')}>isolated</button></div></>}
          <label>clip</label><label className="chk"><input type="checkbox" checked={active.clip} onChange={(e) => ed().updateNode(active.id, { clip: e.target.checked }, 'clip')} /> clip to the layer below</label>
        </div>
      )}
      <div className="layer-actions">
        <CommandRow ids={['edit.layer.new', 'edit.layer.newGroup', 'edit.layer.group']} />
        <MenuButton label="Add adjustment" icon={SlidersHorizontal} items={adjustmentMenu} />
        <MenuButton label="Add filter" icon={Sparkles} items={filterMenu} />
        <CommandRow ids={['gap', 'edit.layer.duplicate', 'edit.layer.mergeDown', 'edit.layer.up', 'edit.layer.down', 'gap', active?.mask ? 'edit.mask.remove' : 'edit.mask.add', 'edit.layer.visibility', 'edit.layer.lock', 'gap', 'edit.layer.delete']} />
        <MenuButton label="More" items={layerMenu} />
      </div>
    </div>
  )
}

function PropertiesTab() {
  const doc = useEditor((s) => s.doc)!
  const activeId = useEditor((s) => s.activeId)
  const before = useRef<DocumentStack | null>(null)
  const n = findNode(doc, activeId)
  if (!n) return <span className="muted">Select a layer.</span>
  const start = () => { before.current = snapshot(doc) }
  const commit = (label: string) => { if (before.current) { ed().pushHistory({ label, layerId: n.id, kind: 'image', tiles: [], stack: before.current, at: Date.now() }); before.current = null } }
  if (n.kind === 'raster') return (
    <dl className="kv">
      <dt>name</dt><dd>{n.name}</dd>
      <dt>position</dt><dd><input type="number" value={n.x ?? 0} onFocus={start} onChange={(e) => ed().updateNode(n.id, { x: Number(e.target.value) })} onBlur={() => commit('move layer')} style={{ width: 76 }} /> , <input type="number" value={n.y ?? 0} onFocus={start} onChange={(e) => ed().updateNode(n.id, { y: Number(e.target.value) })} onBlur={() => commit('move layer')} style={{ width: 76 }} /></dd>
      <dt>size</dt><dd>{n.w}×{n.h}</dd>
      <dt>lineage</dt><dd className="mono">{n.lineage_asset_id ?? '—'}</dd>
      <dt>recipe</dt><dd>{n.recipe ? <>
        <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          <button onClick={() => { const r = { ...n.recipe } as Record<string, unknown>; delete r.seed; delete r.job_id; delete r.batch_id; delete r.region; delete r.document_id; void ed().runAi({ ...r, seeds: [Math.floor(Math.random() * 2 ** 31)] }) }} title="runs the same recipe on the current document with a new seed (the selection must still cover the region)">Re-run (new seed)</button>
          <button className="quiet" onClick={() => void navigator.clipboard?.writeText(JSON.stringify(n.recipe, null, 2))}>copy JSON</button>
        </div>
        <pre className="recipe">{JSON.stringify(n.recipe, null, 1)}</pre></> : <span className="muted">— AI layers carry their recipe (seed, region, model)</span>}</dd>
      {n.mask && <><dt>mask</dt><dd>{n.mask.enabled ? 'enabled' : 'disabled'} · {n.mask.linked ? 'linked' : 'unlinked'} · offset {n.mask.x}, {n.mask.y}</dd></>}
    </dl>
  )
  if (n.kind === 'group') return <dl className="kv"><dt>group</dt><dd>{n.children?.length ?? 0} children · {n.passthrough ? 'pass-through' : 'isolated'}</dd></dl>
  const params = n.params ?? {}
  const setParam = (k: string, v: unknown) => ed().updateNode(n.id, { params: { ...params, [k]: v } })
  return (
    <div>
      <div className="tool-opts">
        <label>type</label><span>{n.type}</span>
        {Object.entries(params).map(([k, v]) => {
          if (typeof v === 'number') { const [min, max, step] = PARAM_RANGES[k] ?? [-100, 100, 1]; return <Slider key={k} label={k.replace('_', ' ')} value={v} min={min} max={max} step={step} onStart={start} onChange={(x) => setParam(k, x)} onCommit={() => commit(`${n.type} ${k}`)} /> }
          if (typeof v === 'boolean') return <Fragment key={k}><label>{k}</label><input type="checkbox" checked={v} onChange={(e) => { start(); setParam(k, e.target.checked); setTimeout(() => commit(`${n.type} ${k}`)) }} /></Fragment>
          return <Fragment key={k}><label>{k}</label><input type="text" defaultValue={JSON.stringify(v)} onFocus={start} onBlur={(e) => { try { setParam(k, JSON.parse(e.target.value)); commit(`${n.type} ${k}`) } catch { useSession.getState().toast(`${k}: not valid JSON`, 'error') } }} /></Fragment>
        })}
        {!Object.keys(params).length && <span className="hint full">no parameters</span>}
      </div>
      <p className="hint">Previewed on the canvas with the compositor's own formulas (blur exact up to radius 4, strided above; noise approximate); rendered exactly in the orchestrator on Save to Catalogue / Export (10 §3).</p>
    </div>
  )
}

function HistoryTab() {
  const history = useEditor((s) => s.history)
  const future = useEditor((s) => s.future)
  const stepBack = (i: number) => { const n = history.length - 1 - i; for (let k = 0; k < n; k++) ed().undo() }
  const stepFwd = (j: number) => { const n = future.length - j; for (let k = 0; k < n; k++) ed().redo() }
  const what = (e: { tiles: unknown[]; stack?: unknown }) => e.tiles.length ? `${e.tiles.length} tile${e.tiles.length > 1 ? 's' : ''}` : e.stack ? 'stack' : ''
  return (
    <div className="history-list">
      {future.map((e, j) => <button key={`f${j}`} className="future" onClick={() => stepFwd(j)}>{e.label} <span className="kind">{what(e)} · redo</span></button>)}
      {[...history].reverse().map((e, r) => { const i = history.length - 1 - r; return <button key={`h${i}`} className={r === 0 ? 'current' : ''} onClick={() => stepBack(i)}>{e.label} <span className="kind">{what(e)} · {new Date(e.at).toLocaleTimeString()}</span></button> })}
      <button className="quiet" disabled={!history.length} onClick={() => stepBack(-1)}>◂ back to the opened state</button>
      {!history.length && !future.length && <div className="muted">No steps yet. Undo Ctrl+Z · redo Ctrl+Shift+Z; strokes keep 256² tile snapshots, stack edits keep the layer tree.</div>}
    </div>
  )
}

function InfoTab() {
  const doc = useEditor((s) => s.doc)!
  const renderer = useEditor((s) => s.renderer)
  const cursor = useEditor((s) => s.cursor)
  const dirty = useEditor((s) => s.docDirty)
  const revision = useEditor((s) => s.revision)
  const cmp = useEditor((s) => s.lastCompare)
  const mem = useMemo(() => { const st = ed(); let b = 0; st.pixels.forEach((lp) => { b += lp.width * lp.height * 4 }); st.masks.forEach((lp) => { b += lp.width * lp.height * 4 }); if (st.selection) b += st.selection.width * st.selection.height * 4; return b }, [revision]) // eslint-disable-line react-hooks/exhaustive-deps
  let total = 0; walk(doc.layers, () => { total++ })
  return (
    <dl className="kv">
      <dt>document</dt><dd className="mono">{doc.id}</dd>
      <dt>name</dt><dd>{doc.name}</dd>
      <dt>size</dt><dd>{doc.w}×{doc.h} · background {doc.background}</dd>
      <dt>layers</dt><dd>{countRasters(doc)} raster · {total} nodes</dd>
      <dt>source</dt><dd>{doc.source_asset_id ? <><img className="insp-thumb" src={api.thumbUrl(doc.source_asset_id, 256)} alt="" /><span className="mono">{doc.source_asset_id}</span></> : '—'}</dd>
      <dt>saved</dt><dd>{doc.saved_at ? new Date(doc.saved_at).toLocaleString() : 'never'}{dirty ? ' · unsaved changes' : ''}</dd>
      <dt>colour</dt><dd>sRGB · 8-bit layers (16-bit post-MVP, 10 §15)</dd>
      <dt>memory</dt><dd>{(mem / 1048576).toFixed(0)} MB CPU canvases + the GPU copies</dd>
      <dt>renderer</dt><dd>{renderer || '—'}</dd>
      <dt>cursor</dt><dd className="mono">{cursor ? `${cursor.x}, ${cursor.y}` : '—'}</dd>
      <dt>preview vs exact</dt><dd><CommandButton id="edit.compare" text />{cmp && <div className="kind">RGB mean {cmp.rgb_mean.toFixed(2)} · p99 {cmp.rgb_p99} · max {cmp.rgb_max} · with alpha p99 {cmp.p99} · {new Date(cmp.at).toLocaleTimeString()}</div>}</dd>
    </dl>
  )
}

function Inspector() {
  const [tab, setTab] = useState<'layers' | 'properties' | 'history' | 'info'>('layers')
  const hasDoc = useEditor((s) => !!s.doc)
  if (!hasDoc) return <span className="muted">No document.</span>
  return (
    <div>
      <div className="tabs2">{(['layers', 'properties', 'history', 'info'] as const).map((t) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === 'layers' && <LayersTab />}
      {tab === 'properties' && <PropertiesTab />}
      {tab === 'history' && <HistoryTab />}
      {tab === 'info' && <InfoTab />}
    </div>
  )
}

// ------------------------------------------------------------------ keys (10 §10), autosave (10 §7), unsaved-changes toast (10 §12)
function useEditKeys() {
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const s = useSession.getState()
      if (s.ui.suite !== 'edit') return
      if ((e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable]')) return
      const st = ed()
      const k = e.key
      if (k === '\\' && !e.altKey) { e.preventDefault(); st.setView({ before: true }); return }              // hold: before
      if (k === 'Escape') { if (st.transform) st.cancelTransform(); else if (st.quickMask) st.setView({ quickMask: false }); else if (st.selection) st.clearSelection(); return }
      if (st.candidates && !e.ctrlKey && !e.altKey) {                                                   // 10 §10: 1–4 pick, Enter keeps the visible one
        if (/^[1-4]$/.test(k)) { const id = st.candidates.ids[Number(k) - 1]; if (id) st.pickCandidate(id); return }
        if (k === 'Enter' && !st.transform) { const vis = st.candidates.ids.find((id) => findNode(st.doc, id)?.visible) ?? st.candidates.ids[0]; st.pickCandidate(vis); return }
      }
      if (!e.ctrlKey && !e.metaKey && !e.altKey && /^[0-9]$/.test(k)) { st.setBrush({ opacity: k === '0' ? 1 : Number(k) / 10 }); return }
      // every other key is an accelerator for a registry command; a handled key stops here so the global
      // suite switch (Ctrl+1/2, 07 §4) yields to the view keys of 10 §5 while a document is open
      if (handleKeyFor('edit', e)) e.stopImmediatePropagation()
    }
    const up = (e: KeyboardEvent) => { if (e.key === '\\') ed().setView({ before: false }) }
    window.addEventListener('keydown', down, { capture: true })
    window.addEventListener('keyup', up)
    // deep links for the verification loop (07 §1.7): ?doc=<id> opens that document once the project is open;
    // &verify=1 then compares the GPU composite with the exact flatten (10 §14 item 1)
    const q = new URLSearchParams(location.search)
    const deep = q.get('doc')
    let unsubDeep = () => {}
    if (deep) {
      const tryOpen = () => {
        const st = ed()
        if (!useSession.getState().project?.open || st.doc || st.loading) return false
        void st.openDocument(deep).then(() => {
          if (q.get('verify')) setTimeout(() => void ed().compareWithExact(), 2000)
          const tab = q.get('tab'); if (tab) setRailTab('edit', tab)                                      // dev: open a panel section
          if (q.get('sel') === 'all') ed().selectAll()                                                   // dev: marching ants
          if (q.get('sel') === 'half') { const s = ed().ensureSelection(); s.ctx.fillStyle = '#fff'; s.ctx.beginPath(); s.ctx.ellipse(s.width / 2, s.height / 2, s.width / 3, s.height / 3, 0, 0, Math.PI * 2); s.ctx.fill(); s.refresh(); ed().bump() }
          if (q.get('xform')) { ed().beginTransform(); ed().setTransform({ rot: 0.25, sx: 0.8, sy: 0.9 }) }   // dev: transform box
        })
        return true
      }
      if (!tryOpen()) unsubDeep = useSession.subscribe(() => { if (tryOpen()) unsubDeep() })
    }
    ensureEditorAutosave()                                       // B20: survives suite switches (this hook unmounts with the strip)
    return () => { window.removeEventListener('keydown', down, { capture: true }); window.removeEventListener('keyup', up); unsubDeep() }
  }, [])
}

export const EditSuite: SuiteDef = {
  id: 'edit',
  rail: [{ id: 'tools', label: 'Tool options', icon: <SlidersHorizontal size={18} /> }, { id: 'brushes', label: 'Brushes', icon: <Brush size={18} /> }, { id: 'selection', label: 'Selection', icon: <Lasso size={18} /> },
    { id: 'ai', label: 'AI', icon: <Sparkles size={18} /> }, { id: 'documents', label: 'Documents', icon: <Files size={18} /> }],
  Panel, Strip, Stage, Inspector, PrimaryAction,
}
