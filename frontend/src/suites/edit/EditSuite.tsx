// Edit suite (10): toolbox and tool options in the Panel, zoom/overlay strip, PixiJS stage, inspector with
// Layers / Properties / History / Info; Save · Save to Catalogue · Export as the pinned primary actions.
import { Brush, Eye, EyeOff, Files, Lasso, Link2, Lock, LockOpen, SlidersHorizontal, Sparkles, Unlink2 } from 'lucide-react'
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { api } from '../../api/client'
import { CommandButton, CommandRow, MenuButton } from '../../frame/CommandButton'
import { command, handleKeyFor, isEnabled, markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { setRailTab, type SuiteDef } from '../../frame/suiteRegistry'
import { askConfirm, useSession } from '../../store/session'
import { adjustmentMenu, filterMenu, layerMenu } from './editCommands'
import { BlendSelect, LatchButton, ValueField } from './widgets'
import { ColorBalanceEditor, CurvesEditor, LevelsEditor, Section } from './propsEditors'
import { readout, rotateAboutPivot, scaleAboutPivot, type Interp, type TransformMode } from './transform'
import { magnetic } from './smartselect/magnetic'
import { probe as probeSmartSelect } from './smartselect/client'
import { EditorCanvas } from './EditorCanvas'
import { ADJUSTMENT_DEFAULTS, BLEND_MODES, countRasters, ensureEditorAutosave, FILTER_DEFAULTS, findNode, useEditor, walk, type BrushPreset, type DocSummary, type DocumentStack, type Node, type Tool } from './editorStore'
import { useAiPanel, type AiOp, type AiPanelState } from './aiPanelStore'
import './edit.css'
import { assetIds, onlyAssets, useDropTarget } from '../../frame/drag'

const TOOLS: { key: string; tool: Tool; label: string; later?: string }[] = [
  { key: 'V', tool: 'move', label: 'Move' }, { key: 'M', tool: 'marquee', label: 'Marquee' }, { key: 'L', tool: 'lasso', label: 'Lasso' }, { key: 'W', tool: 'wand', label: 'Magic wand' }, { key: '', tool: 'quick', label: 'Quick selection' },
  { key: 'A', tool: 'ai', label: 'AI select' }, { key: 'B', tool: 'brush', label: 'Brush' }, { key: 'E', tool: 'eraser', label: 'Eraser' }, { key: 'G', tool: 'fill', label: 'Fill / gradient' },
  { key: 'I', tool: 'eyedropper', label: 'Eyedropper' }, { key: 'C', tool: 'crop', label: 'Crop / canvas' }, { key: 'H', tool: 'hand', label: 'Hand' }, { key: 'Z', tool: 'zoom', label: 'Zoom' },
]
/** min, max, step for the numeric adjustment / filter parameters (names from compose.py). */
const PARAM_RANGES: Record<string, [number, number, number]> = {
  in_black: [0, 255, 1], in_white: [0, 255, 1], out_black: [0, 255, 1], out_white: [0, 255, 1], gamma: [0.1, 5, 0.01],
  hue: [-180, 180, 1], saturation: [-100, 100, 1], lightness: [-100, 100, 1], brightness: [-100, 100, 1], contrast: [-100, 100, 1],
  exposure: [-5, 5, 0.01], offset: [-0.5, 0.5, 0.001], r: [0, 100, 1], g: [0, 100, 1], b: [0, 100, 1],
  radius: [0, 100, 0.1], amount: [0, 500, 1], threshold: [0, 255, 1], seed: [0, 99999, 1],
  transparency_threshold: [0, 100, 1], opacity_threshold: [0, 100, 1],                      // D49 colour to alpha (%)
}
const BRUSH_PRESETS: BrushPreset[] = [
  { name: 'hard round', size: 48, hardness: 1, flow: 1, opacity: 1, spacing: 0.1, smoothing: 0.3, builtin: true },
  { name: 'soft round', size: 64, hardness: 0.5, flow: 0.6, opacity: 1, spacing: 0.15, smoothing: 0.4, builtin: true },
  { name: 'airbrush', size: 120, hardness: 0.05, flow: 0.12, opacity: 1, spacing: 0.06, smoothing: 0.5, builtin: true },
  { name: 'pencil', size: 6, hardness: 1, flow: 1, opacity: 0.9, spacing: 0.08, smoothing: 0.2, builtin: true },
  { name: 'inker', size: 10, hardness: 0.95, flow: 1, opacity: 1, spacing: 0.04, smoothing: 0.75, builtin: true },
  { name: 'marker', size: 36, hardness: 0.9, flow: 0.5, opacity: 0.6, spacing: 0.1, smoothing: 0.3, builtin: true },
  { name: 'wash', size: 160, hardness: 0.2, flow: 0.08, opacity: 0.5, spacing: 0.1, smoothing: 0.6, builtin: true },
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

/** Range + value. With `num` the value is also an editable number field: `scale` 100 shows a 0–1 value as a percentage, `unit` is its suffix. */
function Slider({ label, value, min, max, step = 1, fmt, onChange, onStart, onCommit, num, scale = 1, unit }: { label: string; value: number; min: number; max: number; step?: number; fmt?: (v: number) => string; onChange: (v: number) => void; onStart?: () => void; onCommit?: () => void; num?: boolean; scale?: number; unit?: string }) {
  const clamp = (v: number) => Math.min(max, Math.max(min, v))
  return (
    <>
      <label>{label}</label>
      <div className="slider">
        <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} onPointerDown={onStart} onPointerUp={onCommit} onKeyDown={(e) => { if (!e.repeat) onStart?.() }} onKeyUp={onCommit} />
        {num
          ? <span className="num"><input type="number" min={min * scale} max={max * scale} step={step * scale} value={Math.round(value * scale * 100) / 100} onChange={(e) => { const v = Number(e.target.value); if (Number.isFinite(v)) onChange(clamp(v / scale)) }} />{unit ? <i>{unit}</i> : null}</span>
          : <span className="val">{fmt ? fmt(value) : String(Math.round(value * 1000) / 1000)}</span>}
      </div>
    </>
  )
}

function Swatches() {
  const b = useEditor((s) => s.brush)
  const forMask = useEditor((s) => s.maskPairActive)
  return (
    <div className={`swatch-pair${forMask ? ' for-mask' : ''}`} title={forMask ? 'the mask colours (D54): painted as grey — black hides, white shows; X swaps' : undefined}>
      {forMask && <span className="hint">mask</span>}
      <span className="sw" style={{ background: b.color }} title="foreground"><input type="color" value={b.color} onChange={(e) => ed().setBrush({ color: e.target.value })} /></span>
      <span className="sw" style={{ background: b.background }} title="background"><input type="color" value={b.background} onChange={(e) => ed().setBrush({ background: e.target.value })} /></span>
      <CommandButton id="edit.colour.swap" /><CommandButton id="edit.colour.default" />
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Tool options
/** D59: Quick Selection's options (PhotoCraft retouch_ui): the brush diameter, sample all layers; every stroke adds, Alt subtracts. */
function QuickOptions() {
  const size = useEditor((s) => s.quickSize)
  const all = useEditor((s) => s.quickSampleAll)
  return (
    <div className="tool-opts">
      <ValueField label="size" value={size} min={1} max={5000} unit="px" title="brush diameter — [ and ] change it" onChange={(v) => ed().setView({ quickSize: Math.max(1, Math.round(v)) })} />
      <label /><label className="chk" title="look at every visible layer instead of the active one"><input type="checkbox" checked={all} onChange={(e) => ed().setView({ quickSampleAll: e.target.checked })} /> sample all layers</label>
      <span className="hint full">paint over what you want: the selection grows to its edges (computed when you let go); every stroke adds, Alt subtracts. Runs on the CPU in a Worker — no GPU.</span>
    </div>
  )
}
/** D59: the Magnetic Lasso's detection options (PhotoCraft magnetic_lasso_ui): width, contrast, frequency. */
function MagneticOptions() {
  const w = useEditor((s) => s.magWidth), c = useEditor((s) => s.magContrast), f = useEditor((s) => s.magFrequency)
  return (
    <>
      <ValueField label="width" value={w} min={1} max={256} unit="px" title="detection width: the border follows only edges this close to the pointer ([ and ] change it)" onChange={(v) => ed().setView({ magWidth: Math.round(v) })} />
      <ValueField label="contrast" value={c} min={1} max={100} unit="%" title="steps weaker than this are not edges" onChange={(v) => ed().setView({ magContrast: Math.round(v) })} />
      <ValueField label="frequency" value={f} min={0} max={100} title="how often points are placed along the border" onChange={(v) => ed().setView({ magFrequency: Math.round(v) })} />
    </>
  )
}

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
  const sv = useEditor(useShallow((s) => ({ marqueeFeather: s.marqueeFeather, marqueeStyle: s.marqueeStyle, marqueeW: s.marqueeW, marqueeH: s.marqueeH, lassoKind: s.lassoKind, lassoOpen: !!s.lassoPoly, wandContiguous: s.wandContiguous, wandMerged: s.wandMerged, wandAA: s.wandAA })))
  const tolerance = useEditor((s) => s.tolerance)
  const fillMode = useEditor((s) => s.fillMode)
  const doc = useEditor((s) => s.doc)
  const hasSel = useEditor((s) => !!s.selection)
  const activeId = useEditor((s) => s.activeId)
  const transforming = useEditor((s) => !!s.transform)
  const [cv, setCv] = useState({ w: 0, h: 0, ax: 0.5, ay: 0.5 })
  useEffect(() => { if (doc) setCv((c) => ({ ...c, w: doc.w, h: doc.h })) }, [doc?.w, doc?.h]) // eslint-disable-line react-hooks/exhaustive-deps
  const set = (p: Partial<typeof b>) => ed().setBrush(p)
  const nudge = (dx: number, dy: number) => { const n = findNode(doc, activeId); if (n?.kind === 'raster') ed().updateNode(n.id, { x: (n.x ?? 0) + dx, y: (n.y ?? 0) + dy }, 'nudge', `nudge:${n.id}`) }   // D43: a run of nudges is one step
  const modeSeg = <div className="segmented">{(['replace', 'add', 'subtract', 'intersect'] as const).map((m) => <button key={m} className={mode === m ? 'active' : ''} title={{ replace: 'new selection', add: 'add (Shift)', subtract: 'subtract (Alt)', intersect: 'intersect (Shift+Alt)' }[m]} onClick={() => ed().setView({ selectionMode: m })}>{m}</button>)}</div>
  const featherField = <><label>feather</label><span className="num"><input type="number" min={0} max={250} value={sv.marqueeFeather} onChange={(e) => ed().setView({ marqueeFeather: Math.max(0, Number(e.target.value) || 0) })} style={{ width: 64 }} /><i>px</i></span></>
  return (
    <div>
      <Toolbox />
      <h4 className="sect">{TOOLS.find((x) => x.tool === tool)?.label}</h4>
      {(tool === 'brush' || tool === 'eraser') && (
        <div className="tool-opts">
          <BrushControls />
          {tool === 'brush' && <><label>colour</label><Swatches /></>}
          <label /><CommandRow ids={['edit.brush.smaller', 'edit.brush.larger', 'edit.brush.softer', 'edit.brush.harder']} />
          <span className="hint full">[ ] size · Shift+[ ] hardness · 0–9 opacity · X swap · D defaults · pressure controls appear once a pen is detected (D19)</span>
        </div>
      )}
      {tool === 'marquee' && <div className="tool-opts"><label>shape</label><div className="segmented">{(['rect', 'ellipse'] as const).map((m) => <button key={m} className={marqueeShape === m ? 'active' : ''} onClick={() => ed().setView({ marqueeShape: m })}>{m}</button>)}</div><label>mode</label>{modeSeg}{featherField}
        <label>style</label><div className="segmented">{(['normal', 'ratio', 'size'] as const).map((m) => <button key={m} className={sv.marqueeStyle === m ? 'active' : ''} title={{ normal: 'drag any rectangle', ratio: 'fixed ratio W : H', size: 'fixed size W × H px, hanging from the pointer' }[m]} onClick={() => ed().setView({ marqueeStyle: m })}>{m === 'ratio' ? 'fixed ratio' : m === 'size' ? 'fixed size' : m}</button>)}</div>
        {sv.marqueeStyle !== 'normal' && <><label>{sv.marqueeStyle === 'ratio' ? 'W : H' : 'W × H'}</label><span className="num"><input type="number" min={1} value={sv.marqueeW} onChange={(e) => ed().setView({ marqueeW: Math.max(1, Number(e.target.value) || 1) })} style={{ width: 64 }} /> {sv.marqueeStyle === 'ratio' ? ':' : '×'} <input type="number" min={1} value={sv.marqueeH} onChange={(e) => ed().setView({ marqueeH: Math.max(1, Number(e.target.value) || 1) })} style={{ width: 64 }} /></span></>}
        <span className="hint full">Shift adds, Alt subtracts, Shift+Alt intersects while dragging</span></div>}
      {tool === 'lasso' && <div className="tool-opts"><label>kind</label><div className="segmented">{(['freehand', 'polygon', 'magnetic'] as const).map((m) => <button key={m} className={sv.lassoKind === m ? 'active' : ''} onClick={() => ed().setView({ lassoKind: m })}>{m}</button>)}</div><label>mode</label>{modeSeg}{featherField}
        {sv.lassoKind === 'magnetic' && <MagneticOptions />}
        {sv.lassoOpen && <><label>{sv.lassoKind === 'magnetic' ? 'border' : 'polygon'}</label><span><CommandButton id="edit.sel.polyClose" text /> {sv.lassoKind === 'magnetic' && <CommandButton id="edit.sel.magBack" text />} <CommandButton id="edit.sel.polyCancel" text /></span></>}
        <span className="hint full">{sv.lassoKind === 'polygon' ? 'click to add corners; click the first corner, double-click or ✓ to close' : sv.lassoKind === 'magnetic' ? 'click on an edge, then move along it — the border snaps to the edge and drops points as it goes; click to place a point, Alt-click a straight segment (Alt-drag: freehand), Backspace removes a point; click the first point, double-click or ✓ to close' : 'drag a freehand outline'}; Shift adds, Alt subtracts, Shift+Alt intersects</span></div>}
      {tool === 'quick' && <QuickOptions />}
      {tool === 'wand' && <div className="tool-opts"><label>mode</label>{modeSeg}<Slider label="tolerance" value={tolerance} min={0} max={255} onChange={(v) => ed().setView({ tolerance: v })} />
        <label>sample</label><div className="segmented"><button className={!sv.wandMerged ? 'active' : ''} onClick={() => ed().setView({ wandMerged: false })}>active layer</button><button className={sv.wandMerged ? 'active' : ''} onClick={() => ed().setView({ wandMerged: true })}>all layers</button></div>
        <label /><span><label className="chk"><input type="checkbox" checked={sv.wandContiguous} onChange={(e) => ed().setView({ wandContiguous: e.target.checked })} /> contiguous</label> <label className="chk"><input type="checkbox" checked={sv.wandAA} onChange={(e) => ed().setView({ wandAA: e.target.checked })} /> anti-alias</label></span>
        <span className="hint full">tolerance per channel including alpha; transparent pixels match each other whatever their hidden colour</span></div>}
      {tool === 'fill' && <div className="tool-opts"><label>mode</label><div className="segmented">{(['solid', 'linear', 'radial'] as const).map((m) => <button key={m} className={fillMode === m ? 'active' : ''} onClick={() => ed().setView({ fillMode: m })}>{m}</button>)}</div><label>colour</label><Swatches /><Slider label="opacity" value={b.opacity} min={0} max={1} step={0.01} fmt={pct} onChange={(v) => set({ opacity: v })} /><span className="hint full">{fillMode === 'solid' ? 'click fills the selection, or the whole layer (mask: white) when nothing is selected' : `drag from the foreground colour to the background colour (${fillMode}); limited to the selection when there is one; on a mask: white → black`}</span></div>}
      {tool === 'move' && (
        <div className="tool-opts">
          <label>nudge</label><div className="nudge"><button onClick={() => nudge(0, -1)}>▲</button><button onClick={() => nudge(-1, 0)}>◀</button><button onClick={() => nudge(1, 0)}>▶</button><button onClick={() => nudge(0, 1)}>▼</button></div>
          <label>transform</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{transforming ? <CommandRow ids={['edit.transform.apply', 'edit.transform.cancel']} /> : <CommandButton id="edit.transform" text />}<CommandRow ids={['edit.layer.flipH', 'edit.layer.flipV', 'edit.layer.rot270', 'edit.layer.rot90']} /></div>
          <span className="hint full">{transforming ? 'drag inside to move, a corner or edge to scale (in proportion — Shift frees it, Alt from the reference point), outside to rotate (Shift snaps 15°); Ctrl-drag a corner to distort, an edge to skew, Ctrl+Alt+Shift a corner for perspective (or pick the mode in the strip); Alt-click places the reference point; Enter / double-click applies, Esc cancels' : 'drag the active raster layer on the canvas; Ctrl+T enters free transform'}</span>
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

/** The brush itself (10 §4): size in px with a number field, the rest in %; shared by the Tool options and the Brushes tab. */
function BrushControls() {
  const b = useEditor((s) => s.brush)
  const line = useEditor((s) => s.brushLine)
  const pickOnce = useEditor((s) => s.pickOnce)
  const set = (p: Partial<typeof b>) => ed().setBrush(p)
  return (
    <>
      <ValueField label="size" value={b.size} min={1} max={1024} unit="px" onChange={(v) => set({ size: Math.max(1, Math.round(v)) })} />
      <ValueField label="hardness" value={b.hardness} min={0} max={1} scale={100} unit="%" onChange={(v) => set({ hardness: v })} />
      <ValueField label="opacity" value={b.opacity} min={0} max={1} scale={100} unit="%" onChange={(v) => set({ opacity: v })} />
      <ValueField label="flow" value={b.flow} min={0.01} max={1} scale={100} unit="%" onChange={(v) => set({ flow: v })} />
      <ValueField label="spacing" value={b.spacing} min={0.02} max={1} scale={100} unit="%" onChange={(v) => set({ spacing: v })} />
      <ValueField label="smoothing" value={b.smoothing} min={0} max={1} scale={100} unit="%" onChange={(v) => set({ smoothing: v })} />
      <label /><span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}><CommandButton id="edit.brush.line" text active={line} /> <CommandButton id="edit.brush.pick" text active={pickOnce} /></span>
      <span className="hint full">smoothing pulls the brush on a string (it catches up when you pause); Shift-click draws a straight line from the last stroke; Alt-click picks a colour</span>
    </>
  )
}

function BrushesTab() {
  const b = useEditor((s) => s.brush)
  const mine = useEditor((s) => s.brushPresets)
  const [naming, setNaming] = useState<string | null>(null)
  const presets = [...BRUSH_PRESETS, ...mine]
  const isActive = (p: BrushPreset) => p.size === b.size && Math.abs(b.hardness - p.hardness) < 0.005 && Math.abs(b.flow - p.flow) < 0.005 && Math.abs(b.opacity - p.opacity) < 0.005 && Math.abs(b.spacing - p.spacing) < 0.005
  return (
    <div>
      <div className="brush-presets">
        {presets.map((p) => <div key={p.name} className="row"><button className={isActive(p) ? 'active' : ''} onClick={() => ed().applyBrushPreset(p)} title={`${p.size} px · hardness ${Math.round(p.hardness * 100)} % · opacity ${Math.round(p.opacity * 100)} % · flow ${Math.round(p.flow * 100)} %`}>
          <span className="dab" style={{ width: Math.max(8, Math.min(26, p.size / 6)), height: Math.max(8, Math.min(26, p.size / 6)), background: `radial-gradient(circle, ${b.color} ${Math.round(p.hardness * 100)}%, transparent 100%)`, opacity: Math.max(0.35, Math.min(1, p.flow + 0.3)) }} /><span>{p.name}</span><span className="n">{p.size} px</span>
        </button>{!p.builtin && <button className="quiet" title="Delete preset" onClick={() => ed().deleteBrushPreset(p.name)}>✕</button>}</div>)}
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
        {naming === null ? <button onClick={() => setNaming('')}>Save current as preset…</button> : <>
          <input type="text" autoFocus value={naming} placeholder="preset name" onChange={(e) => setNaming(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && naming.trim()) { ed().saveBrushPreset(naming.trim()); setNaming(null) } if (e.key === 'Escape') setNaming(null) }} style={{ width: 140 }} />
          <button className="primary" disabled={!naming.trim()} onClick={() => { ed().saveBrushPreset(naming.trim()); setNaming(null) }}>Save</button><button className="quiet" onClick={() => setNaming(null)}>Cancel</button></>}
      </div>
      <h4 className="sect">Current brush</h4>
      <div className="tool-opts">
        <BrushControls />
        <label>colour</label><Swatches />
      </div>
      <p className="hint">Type a diameter or any value directly in the number fields. Pressure → size / opacity / flow and the pen curve appear once a pen is detected (D19).</p>
    </div>
  )
}

function SelectionTab() {
  const quickMask = useEditor((s) => s.quickMask)
  const px = useEditor((s) => s.selModifyPx)
  return (
    <div className="tool-opts">
      <label>select</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.sel.all', 'edit.sel.none', 'edit.sel.invert', 'edit.sel.fromLayer'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <label>amount</label><span className="num"><input type="number" min={1} max={500} value={px} onChange={(e) => ed().setView({ selModifyPx: Math.max(1, Math.min(500, Number(e.target.value) || 1)) })} style={{ width: 70 }} /><i>px</i></span>
      <label>modify</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['expand', 'contract', 'border', 'smooth', 'feather'].map((op) => <CommandButton key={op} id={`edit.sel.${op}`} text label={op} />)}</div>
      <label>quick mask</label><button className={quickMask ? 'active' : ''} onClick={() => runCommand('edit.sel.quickMask')} title="Quick mask (Q)">{quickMask ? 'painting the selection (red = unselected)' : 'paint the selection with the brush'}</button>
      <label>mask</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.mask.fromSelection', 'edit.mask.load', 'edit.sel.crop'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <RefineEdgeControls />
      <span className="hint full">expand / contract grow round by the amount; border makes a band that wide around the edge; smooth removes specks and jaggies; feather softens with Photoshop's radius. Every change, and every selection tool, is one undo step.</span>
    </div>
  )
}

/** D45 Refine Edge: settings over /capabilities.refine_edge (ranges and defaults from the server, T8); one undo step per run. */
function RefineEdgeControls() {
  const caps = useSession((s) => s.capabilities?.refine_edge)
  useEditor((s) => s.refineEdge)                                         // re-render when a setting changes
  const p = ed().refineParams()
  const range = (k: string, d: [number, number, number]) => (caps?.ranges?.[k] as [number, number, number] | undefined) ?? d
  const row = (k: 'radius' | 'smooth' | 'feather' | 'contrast' | 'shift_edge', label: string, d: [number, number, number], unit: string) => {
    const [min, max, step] = range(k, d)
    return <Slider key={k} label={label} value={p[k] ?? 0} min={min} max={max} step={step} fmt={(v) => `${v}${unit}`} onChange={(v) => ed().setRefineEdge({ [k]: v })} />
  }
  return (
    <>
      <h4 className="sect full">refine edge</h4>
      {row('radius', 'radius', [0, 64, 0.5], ' px')}
      <label /><label className="chk" title="adapt the band to the edge's softness: hard edges stay hard, hair gets a wide band"><input type="checkbox" checked={!!p.smart_radius} onChange={(e) => ed().setRefineEdge({ smart_radius: e.target.checked })} /> smart radius</label>
      {row('smooth', 'smooth', [0, 100, 1], '')}
      {row('feather', 'feather', [0, 64, 0.5], ' px')}
      {row('contrast', 'contrast', [0, 100, 1], ' %')}
      {row('shift_edge', 'shift edge', [-100, 100, 1], ' %')}
      <label /><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}><CommandButton id="edit.sel.refine" text /><button className="quiet" onClick={() => ed().setRefineEdge(null)} title="the server's defaults">reset</button></div>
    </>
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
  const open = useSession((s) => s.capabilities?.variant === 'open')          // C3 (D26): SAM 3 is full only
  const sam = p.selModel === 'sam3' && !open
  const pos = aiPrompt.points.filter((q) => q.label === 1).length, neg = aiPrompt.points.length - pos
  const reason = !doc ? 'no document' : health(sam ? 'sam3' : 'birefnet') === 'missing' ? `weights missing: fetch ${sam ? 'sam3' : 'birefnet'} in Models`
    : sam && p.selMode === 'text' && !p.selText.trim() ? 'type what to select' : sam && p.selMode === 'points' && !pos ? 'click the subject on the canvas (Alt-click excludes)'
    : sam && p.selMode === 'box' && !aiPrompt.box ? 'drag a box on the canvas' : null
  const run = (stage = false) => void ed().runAi({ kind: 'segment', model_id: sam ? 'sam3' : 'birefnet', mode: sam ? p.selMode : 'subject', text: p.selText, points: aiPrompt.points, box: aiPrompt.box,
    threshold: p.selThreshold, op: p.selOp, expand: p.selExpand, feather: p.selFeather, edge_refine: p.selRefine ? ed().refineParams() : null, seeds: [0] }, stage)
  return (
    <div className="tool-opts">
      <label>model</label><div className="segmented"><button className={!sam ? 'active' : ''} onClick={() => setP({ selModel: 'birefnet', selMode: 'subject' })}>Subject · BiRefNet</button>{!open && <button className={sam ? 'active' : ''} onClick={() => setP({ selModel: 'sam3', selMode: p.selMode === 'subject' ? 'text' : p.selMode })}>SAM 3</button>}</div>
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
      <label /><label className="chk" title="soft, image-aware edges after the mask joins the selection — the Selection panel's Refine edge settings (D45)"><input type="checkbox" checked={p.selRefine} onChange={(e) => setP({ selRefine: e.target.checked })} /> refine edge</label>
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
  // C3 (D26): the open build has no dev, no Klein 9B and no SAM 3 — the panel's choices map onto the open models
  const open = useSession((s) => s.capabilities?.variant === 'open')
  const mode = open && p.mode === 'fill_hero' ? 'fill' : p.mode
  const capModels = useSession((s) => s.capabilities?.models)
  const teId = (mid: string) => (p.teId && capModels?.[mid]?.te_options?.some((o) => o.id === p.teId) ? p.teId : undefined)   // D31: only where it pairs
  const refineModel = open ? 'klein-base-4b' : p.refineModel
  const tiledModel = open ? 'klein-base-4b' : p.tiledModel
  const kleinId = open ? 'klein-4b' : 'klein-9b'
  const hero = !open && (p.op === 'inpaint' ? p.mode === 'fill_hero' : p.op === 'outpaint' ? p.outpaintHero : p.op === 'refine' ? p.refineModel === 'flux2-dev-fp8mixed' : false)
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
    if (p.op === 'inpaint') void ed().runAi({ kind: 'inpaint', mode, model_id: kleinId, te_id: teId(kleinId), margin_pct: p.margin, min_size: p.minSize, feather: p.feather, expand: p.expand, blend: p.blend, prompt_mode: p.promptMode, ...base }, stage)
    else if (p.op === 'outpaint') void ed().runAi({ kind: 'inpaint', mode: 'outpaint', model_id: hero ? 'flux2-dev-fp8mixed' : kleinId, te_id: teId(hero ? 'flux2-dev-fp8mixed' : kleinId), outpaint: p.pad, feather: p.feather, prompt_mode: p.promptMode, ...base }, stage)
    else if (p.op === 'refine') void ed().runAi({ kind: 'i2i', model_id: refineModel, te_id: teId(refineModel), source: p.refineSource, layer_id: activeId, strength: p.strength, margin_pct: p.margin, feather: p.feather, match_colour: p.matchColour, ...base }, stage)
    else void ed().runAi({ kind: 'upscale', model_id: p.upscaleModel, source: p.upscaleSource, layer_id: activeId, as_layer: p.asLayer, seeds: p.refineTiled ? seeds().slice(0, 1) : [0],
      refine: p.refineTiled, refine_model_id: tiledModel, te_id: p.refineTiled ? teId(tiledModel) : undefined, strength: p.tiledStrength, tile: p.tile, overlap: p.overlap, prompt_text: p.prompt }, stage)
  }
  const ops: [AiOp, string][] = [['select', 'Select'], ['inpaint', 'Inpaint'], ['refine', 'Refine'], ['upscale', 'Upscale'], ['outpaint', 'Outpaint']]
  return (
    <div>
      <div className="segmented" style={{ marginBottom: 10 }}>{ops.map(([k, l]) => <button key={k} className={p.op === k ? 'active' : ''} onClick={() => setP({ op: k, candidates: k === 'inpaint' || k === 'outpaint' || k === 'refine' ? (hero ? 2 : 4) : 1 })}>{l}</button>)}</div>
      {p.op === 'select' && <SelectControls />}
      {p.op !== 'select' && <div className="tool-opts">
        {p.op === 'inpaint' && <>
          <label>mode</label><select value={mode} onChange={(e) => { const m = e.target.value as AiPanelState['mode']; setP({ mode: m, candidates: m === 'fill_hero' ? 2 : 4 }) }}>
            <option value="fill">Fill — Klein + LanPaint (default)</option><option value="fill_match">Fill-Match — Klein ICM, continues texture</option>{!open && <option value="fill_hero">Fill Hero — FLUX.2 dev + LanPaint (slow, best detail)</option>}<option value="remove">Remove — background-only prompt</option>
          </select>
          <EncoderPick model={kleinId} />
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder={p.mode === 'remove' ? 'what is behind: "wet cobblestones and a brick wall"' : 'what to paint there'} onChange={(e) => setP({ prompt: e.target.value })} />
          {p.mode !== 'fill_match' && p.mode !== 'remove' && <><label>LanPaint</label><div className="segmented"><button className={p.promptMode === 'image_first' ? 'active' : ''} onClick={() => setP({ promptMode: 'image_first' })}>image first</button><button className={p.promptMode === 'prompt_first' ? 'active' : ''} onClick={() => setP({ promptMode: 'prompt_first' })}>prompt first</button></div></>}
          <Slider label="margin" value={p.margin} min={0} max={100} fmt={(v) => `${v} %`} onChange={(v) => setP({ margin: v })} />
          <Slider label="min size" value={p.minSize} min={512} max={2048} step={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ minSize: v })} />
          <Slider label="feather" value={p.feather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ feather: v })} />
          <Slider label="expand" value={p.expand} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ expand: v })} />
          <label>blend</label><div className="segmented"><button className={p.blend === 'feather' ? 'active' : ''} title="the result fades in over the feather" onClick={() => setP({ blend: 'feather' })}>feather</button><button className={p.blend === 'seamless' ? 'active' : ''} title="Poisson-blend the result into the plate: it keeps its texture but takes the plate's colour and light at the seam — best for removals and continuing a texture; it also pulls an intended colour change towards the old colour near the edge (D47)" onClick={() => setP({ blend: 'seamless' })}>seamless</button></div>
          <span className="hint full">results land with a layer mask: paint it (click the mask thumbnail) to adjust the seam</span>
        </>}
        {p.op === 'outpaint' && <>
          <label>grow</label><div className="pad-grid">{(['left', 'top', 'right', 'bottom'] as const).map((k) => <label key={k}>{k}<input type="number" min={0} max={2048} step={16} value={p.pad[k]} onChange={(e) => setP({ pad: { ...p.pad, [k]: Math.max(0, Number(e.target.value)) } })} /></label>)}</div>
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder="what continues beyond the edge" onChange={(e) => setP({ prompt: e.target.value })} />
          <label>model</label><div className="segmented"><button className={!hero ? 'active' : ''} onClick={() => setP({ outpaintHero: false, candidates: 4 })}>Klein + LanPaint</button>{!open && <button className={hero ? 'active' : ''} onClick={() => setP({ outpaintHero: true, candidates: 2 })}>dev (hero)</button>}</div>
          <EncoderPick model={hero ? 'flux2-dev-fp8mixed' : kleinId} />
          <Slider label="feather" value={p.feather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ feather: v })} />
        </>}
        {p.op === 'refine' && <>
          <label>model</label><select value={refineModel} onChange={(e) => setP({ refineModel: e.target.value, candidates: e.target.value === 'flux2-dev-fp8mixed' ? 2 : 4 })}>{open ? <option value="klein-base-4b">Klein 4B base (CFG, negatives)</option> : <><option value="klein-base-9b">Klein 9B base (CFG, negatives)</option><option value="flux2-dev-fp8mixed">FLUX.2 dev + Turbo</option></>}</select>
          <EncoderPick model={refineModel} />
          <label>on</label><div className="segmented">{(['visible', 'active', 'selection'] as const).map((s) => <button key={s} className={p.refineSource === s ? 'active' : ''} onClick={() => setP({ refineSource: s })}>{s}</button>)}</div>
          <Slider label="strength" value={p.strength} min={0.1} max={0.8} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => setP({ strength: v })} />
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder="defaults to the source asset's prompt when empty" onChange={(e) => setP({ prompt: e.target.value })} />
          {p.refineSource === 'selection' && <Slider label="feather" value={p.feather} min={0} max={64} fmt={(v) => `${v} px`} onChange={(v) => setP({ feather: v })} />}
          <label /><label className="chk" title="undo the refine's colour drift: the result's colour statistics are mapped onto the original's — around the selection, or over the whole image / layer (D48)"><input type="checkbox" checked={p.matchColour} onChange={(e) => setP({ matchColour: e.target.checked })} /> match colour to the original</label>
        </>}
        {p.op === 'upscale' && <>
          <label>model</label><select value={p.upscaleModel} onChange={(e) => setP({ upscaleModel: e.target.value })}><option value="realesrgan-x2">Real-ESRGAN 2× {health('realesrgan-x2') === 'missing' ? '(not fetched)' : ''}</option><option value="realesrgan-x4">Real-ESRGAN 4× {health('realesrgan-x4') === 'missing' ? '(not fetched)' : ''}</option></select>
          <label>on</label><div className="segmented">{(['visible', 'active'] as const).map((s) => <button key={s} className={p.upscaleSource === s ? 'active' : ''} onClick={() => setP({ upscaleSource: s })}>{s}</button>)}</div>
          <label>result</label><label className="chk"><input type="checkbox" checked={p.asLayer} onChange={(e) => setP({ asLayer: e.target.checked })} /> also add a 1× detail layer (the full-size image goes to the Catalogue)</label>
          <label>refine</label><label className="chk"><input type="checkbox" checked={p.refineTiled} onChange={(e) => setP({ refineTiled: e.target.checked })} /> tiled refine after the upscale (10 §4: re-sample every tile at low strength)</label>
          {p.refineTiled && <>
            <label>model</label><select value={tiledModel} onChange={(e) => setP({ tiledModel: e.target.value })}>{open ? <option value="klein-base-4b">Klein 4B base</option> : <><option value="klein-base-9b">Klein 9B base</option><option value="flux2-dev-fp8mixed">FLUX.2 dev + Turbo (slow)</option></>}</select>
            <EncoderPick model={tiledModel} />
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
            <button className="quiet" title="delete the .ora" onClick={(e) => { e.stopPropagation(); void askConfirm({ title: 'Delete document?', text: `"${d.name}" and its .ora file are removed from the project. This cannot be undone.`, okLabel: 'Delete document', danger: true }).then((ok) => { if (ok) void ed().deleteDocument(d.id).then(refresh) }) }}>✕</button>
          </div>
        ))}
        {!items.length && <span className="muted">No documents yet. Select an asset in the Catalogue and press E.</span>}
      </div>
    </div>
  )
}

/** D31: the text encoder behind a Klein 9B recipe — rendered only where the model has an alternate (Q4_K_M GGUF default, fp8). */
function EncoderPick({ model }: { model: string }) {
  const opts = useSession((s) => s.capabilities?.models[model]?.te_options)
  const teId = useAiPanel((s) => s.teId)
  const setP = useAiPanel((s) => s.set)
  if (!opts || opts.length < 2) return null
  const value = teId && opts.some((o) => o.id === teId) ? teId : ''
  return <><label>encoder</label><select value={value} title="Text encoder weights (D31): the Q4_K_M GGUF stays resident beside the 9B transformer; the fp8 encoder makes it stream on a cold engine" onChange={(e) => setP({ teId: e.target.value || null })}>
    {opts.map((o) => <option key={o.id} value={o.default ? '' : o.id}>{o.default ? `preset · ${o.label}` : o.label}{o.health === 'missing' ? ' (not fetched)' : ''}</option>)}
  </select></>
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
/** D58: the free transform's options in the strip (PhotoCraft transform_fields): the reference point, W / H (linked), the angle, the
 * interpolation and the mode, with ✓ / ⊘. */
function TransformBar() {
  const t = useEditor((s) => s.transform)
  const [link, setLink] = useState(true)
  if (!t) return null
  const ro = readout(t)
  const set = ed().setTransform
  const move = (dx: number, dy: number) => set({ quad: t.quad.map((c) => ({ x: c.x + dx, y: c.y + dy })) as typeof t.quad, pivot: { x: t.pivot.x + dx, y: t.pivot.y + dy } })
  const scale = (kx: number, ky: number) => { if (Number.isFinite(kx) && Number.isFinite(ky) && kx > 0 && ky > 0) set({ quad: scaleAboutPivot(t, kx, ky) }) }
  return (
    <span className="xform-bar">
      <span style={{ color: 'var(--accent)' }}>transform</span>
      <ValueField label="X" value={t.pivot.x} min={-300000} max={300000} unit="px" title="the reference point (Alt-click the canvas to place it)" onChange={(v) => move(v - t.pivot.x, 0)} />
      <ValueField label="Y" value={t.pivot.y} min={-300000} max={300000} unit="px" title="the reference point (Alt-click the canvas to place it)" onChange={(v) => move(0, v - t.pivot.y)} />
      <ValueField label="W" value={ro.sx * 100} min={0.1} max={100000} unit="%" onChange={(v) => { const k = v / 100 / ro.sx; scale(k, link ? k : 1) }} />
      <button type="button" className={`quiet latch${link ? ' active' : ''}`} aria-pressed={link} title="keep W and H in proportion" onClick={() => setLink(!link)}>⛓</button>
      <ValueField label="H" value={ro.sy * 100} min={0.1} max={100000} unit="%" onChange={(v) => { const k = v / 100 / ro.sy; scale(link ? k : 1, k) }} />
      <ValueField label="angle" value={Math.round(ro.angle * 100) / 100} min={-180} max={180} unit="°" onChange={(v) => set({ quad: rotateAboutPivot(t, v - ro.angle) })} />
      <select value={t.interp} title="interpolation for the apply" onChange={(e) => set({ interp: e.target.value as Interp })}>
        <option value="bicubic">bicubic</option><option value="bilinear">bilinear</option><option value="nearest">nearest neighbour</option>
      </select>
      <span className="segmented" title="what a plain handle drag does (Ctrl / Ctrl+Alt+Shift do the same without the mode)">
        {(['free', 'skew', 'distort', 'perspective'] as TransformMode[]).map((m) => <button key={m} className={t.mode === m ? 'active' : ''} onClick={() => set({ mode: m })}>{m}</button>)}
      </span>
      <CommandRow ids={['edit.transform.apply', 'edit.transform.cancel']} />
    </span>
  )
}

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
  const rendererPref = useEditor((s) => s.rendererPref)
  const transforming = useEditor((s) => !!s.transform)
  const polyOpen = useEditor((s) => !!s.lassoPoly)
  const latched = useEditor((s) => s.latched)
  const [zt, setZt] = useState<string | null>(null)
  const apply = () => { if (zt !== null) { const v = parseFloat(zt); if (v > 0) ed().zoomTo(v / 100) } setZt(null) }
  return (
    <>
      <span>{doc ? `${doc.name}${dirty ? ' •' : ''} · ${doc.w}×${doc.h}` : 'Edit'}</span>
      {transforming && <TransformBar />}
      {polyOpen && <><span style={{ color: 'var(--accent)' }}>polygon</span><CommandRow ids={['edit.sel.polyClose', 'edit.sel.polyCancel']} /></>}
      <span className="latches" title="Latched modifiers: each stays on for every canvas gesture until clicked again (no keyboard needed)">
        {(['shift', 'ctrl', 'alt'] as const).map((k) => <LatchButton key={k} on={latched[k]} label={k === 'shift' ? '⇧' : k === 'ctrl' ? 'Ctrl' : 'Alt'}
          title={`Latch ${k === 'shift' ? 'Shift' : k === 'ctrl' ? 'Ctrl' : 'Alt'}: canvas gestures act as if it were held, until clicked again`} onToggle={() => { markUsed(`edit.latch.${k}`); runCommand(`edit.latch.${k}`) }} />)}
      </span>
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
      <button className="quiet badge-renderer" onClick={() => ed().setRendererPref(rendererPref === 'auto' ? 'webgl' : rendererPref === 'webgl' ? 'webgpu' : 'auto')}
        title={`Renderer: ${renderer || 'starting…'} · preference ${rendererPref} — click to cycle auto → WebGL2 → WebGPU (D3: auto probes WebGPU and falls back to WebGL2 when it draws nothing)`}>
        {renderer || '…'}{rendererPref !== 'auto' ? ` · ${rendererPref === 'webgl' ? 'forced WebGL2' : 'forced WebGPU'}` : ''}
      </button>
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
  const epoch = useEditor((s) => s.rendererEpoch)
  if (!project?.open) return <div className="placeholder"><div><h2>Edit</h2>open or create a project to begin</div></div>
  if (!doc) return (
    <EmptyDrop><div>
      <h2>Edit</h2>
      {loading ? <p>loading document…</p> : <>
        <p>Select an asset in the Catalogue and press <kbd>E</kbd>, drop a tile here or on the Edit tab, or start empty.</p>
        <p><button onClick={() => void ed().newDocument(1920, 1080)}>New 1920×1080 document</button> <button onClick={() => useSession.getState().setSuite('catalogue')}>Open the Catalogue</button></p>
        <RecentDocuments />
      </>}
      {error && <p style={{ color: 'var(--error)' }}>{error}</p>}
    </div></EmptyDrop>
  )
  return <><EditorCanvas key={epoch} /><CandidateStrip /></>
}

// ------------------------------------------------------------------ Inspector
// ---- D56: layer-panel gestures (PhotoCraft panels.rs layer_drag_and_drop, footer_drop, eye_sweep, layer_drag_edge_scroll) -------
let suppressRowClick = false
/** A press on a row that moves 4 px becomes a drag: an insertion line above / below a row, an outline on a group's middle (into) or on a
 * footer button (delete / duplicate / group); the panel scrolls near its edges; Alt on release drops copies. One history step. */
function startRowDrag(e: React.PointerEvent<HTMLElement>, id: string) {
  if (e.button !== 0 || (e.target as HTMLElement).closest('button, img, .mask-box, .mask-wrap, input')) return
  window.getSelection()?.removeAllRanges()                          // a text selection would turn the press into a native drag (pointercancel)
  const x0 = e.clientX, y0 = e.clientY
  let dragging = false, raf = 0, lx = x0, ly = y0
  let target: { id: string; where: 'above' | 'below' | 'into' } | null = null, footer: string | null = null
  let ghost: HTMLDivElement | null = null
  let scroller: HTMLElement | null = e.currentTarget.parentElement
  while (scroller && !(scroller.scrollHeight > scroller.clientHeight && /auto|scroll/.test(getComputedStyle(scroller).overflowY))) scroller = scroller.parentElement
  const st = ed()
  const sel = st.targetIds()
  const ids = sel.length > 1 && sel.includes(id) ? sel : [id]       // a row inside the selection carries the set
  const clear = () => document.querySelectorAll('.drop-above, .drop-below, .drop-into, .drop-target').forEach((el) => el.classList.remove('drop-above', 'drop-below', 'drop-into', 'drop-target'))
  const hit = (x: number, y: number) => {
    clear(); target = null; footer = null
    const el = document.elementFromPoint(x, y) as HTMLElement | null
    const btn = el?.closest('[data-drop]') as HTMLElement | null
    if (btn) { footer = btn.dataset.drop!; btn.classList.add('drop-target'); return }
    const row = el?.closest('.layer-row[data-id]') as HTMLElement | null
    if (!row) return
    const r = row.getBoundingClientRect(), f = (y - r.top) / r.height
    const where = row.dataset.kind === 'group' && f > 0.3 && f < 0.7 ? 'into' : f < 0.5 ? 'above' : 'below'
    target = { id: row.dataset.id!, where }
    row.classList.add(`drop-${where}`)
  }
  const edge = () => {                                                // edge auto-scroll: zone min(32, ¼ height), 80–600 px/s
    if (scroller) {
      const b = scroller.getBoundingClientRect(), zone = Math.min(32, b.height * 0.25)
      const dir = ly < b.top + zone ? -Math.min(1, (b.top + zone - ly) / zone) : ly > b.bottom - zone ? Math.min(1, (ly - b.bottom + zone) / zone) : 0
      if (dir && lx >= b.left && lx <= b.right) { scroller.scrollTop += Math.sign(dir) * (80 + 520 * Math.abs(dir)) / 60; hit(lx, ly) }
    }
    raf = requestAnimationFrame(edge)
  }
  const move = (ev: PointerEvent) => {
    lx = ev.clientX; ly = ev.clientY
    if (!dragging) {
      if (Math.hypot(lx - x0, ly - y0) < 4) return
      dragging = true
      ghost = document.createElement('div'); ghost.className = 'layer-ghost'
      ghost.textContent = ids.length > 1 ? `${ids.length} layers` : findNode(st.doc, id)?.name ?? ''
      document.body.appendChild(ghost)
      raf = requestAnimationFrame(edge)
    }
    if (ghost) { ghost.style.left = `${lx + 12}px`; ghost.style.top = `${ly + 8}px`; ghost.classList.toggle('copy', ev.altKey) }
    hit(lx, ly)
  }
  const up = (ev: PointerEvent) => {
    window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up)
    cancelAnimationFrame(raf); ghost?.remove(); clear()
    if (!dragging || ev.type === 'pointercancel') return
    suppressRowClick = true; setTimeout(() => { suppressRowClick = false })
    const s = ed()
    if (footer === 'delete') s.deleteNodes(ids)
    else if (footer === 'duplicate') s.duplicateNodes(ids)
    else if (footer === 'group') s.groupNodes(ids)
    else if (target) s.moveNodesTo(ids, target.id, target.where, ev.altKey)
  }
  window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up)
}
/** Eye sweep: the press toggles that row's eye; dragging over more rows gives each the same state — one history step for the sweep. */
function startEyeSweep(e: React.PointerEvent<HTMLElement>, n: Node) {
  e.stopPropagation()
  if (e.button !== 0) return
  if (e.altKey) { ed().solo(n.id); return }
  const v = !n.visible, key = `eye-sweep:${Date.now()}`, label = v ? 'show layers' : 'hide layers'
  ed().updateNode(n.id, { visible: v }, label, key)
  const done = new Set([n.id])
  let py = e.clientY
  const move = (ev: PointerEvent) => {
    const a = Math.min(py, ev.clientY), b = Math.max(py, ev.clientY)   // every row the pointer passed, so a fast sweep skips none
    py = ev.clientY
    document.querySelectorAll<HTMLElement>('.layer-row[data-id]').forEach((row) => {
      const r = row.getBoundingClientRect(), id = row.dataset.id!
      if (done.has(id) || r.bottom < a || r.top > b) return
      done.add(id)
      if (findNode(ed().doc, id)?.visible !== v) ed().updateNode(id, { visible: v }, label, key)
    })
  }
  const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
  window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
}

function LayersTab() {
  const doc = useEditor((s) => s.doc)!
  const activeId = useEditor((s) => s.activeId)
  const selectedIds = useEditor((s) => s.selectedIds)
  const editingMask = useEditor((s) => s.editingMask)
  const revision = useEditor((s) => s.revision)
  const hasSel = useEditor((s) => !!s.selection)
  const thumbs = useMemo(() => { const st = ed(); const m = new Map<string, string>(); st.pixels.forEach((lp, id) => m.set(id, lp.thumbnail(64))); st.masks.forEach((lp, id) => m.set('m:' + id, lp.thumbnail(48))); return m }, [revision]) // eslint-disable-line react-hooks/exhaustive-deps
  const before = useRef<DocumentStack | null>(null)
  const active = findNode(doc, activeId)
  const multi = !!activeId && selectedIds.length > 1 && selectedIds.includes(activeId)
  const start = () => { before.current = snapshot(doc) }
  const commit = (label: string) => { if (before.current && active) { ed().pushHistory({ label, layerId: active.id, kind: 'image', tiles: [], stack: before.current, at: Date.now() }); before.current = null } }
  const rows = (nodes: Node[], depth: number): ReactNode => nodes.map((n) => (
    <div key={n.id}>
      <div className={`layer-row${n.id === activeId ? ' active' : ''}${multi && selectedIds.includes(n.id) ? ' selected' : ''}${n.visible ? '' : ' hidden'}`} style={{ marginLeft: depth * 14 }} tabIndex={0}
        data-id={n.id} data-kind={n.kind} title="click: select · Ctrl-click: add / remove · Shift-click: range · drag: reorder, into a group, or onto the trash / new / group button"
        onPointerDown={(e) => startRowDrag(e, n.id)} onDragStart={(e) => e.preventDefault()}
        onClick={(e) => { if (suppressRowClick) return; ed().selectLayer(n.id, e.ctrlKey || e.metaKey ? 'toggle' : e.shiftKey ? 'range' : 'replace') }}
        onDoubleClick={() => runCommand('edit.layer.rename')} onContextMenu={(e) => { if (!(multi && selectedIds.includes(n.id))) ed().selectLayer(n.id); showMenu(e, layerMenu()) }}>
        <button className={`eye${n.visible ? ' on' : ''}`} title="visibility · drag down the eyes to sweep · Alt-click: solo" onPointerDown={(e) => startEyeSweep(e, n)}
          onClick={(e) => { e.stopPropagation(); if (e.detail === 0) ed().updateNode(n.id, { visible: !n.visible }, n.visible ? 'hide layer' : 'show layer') }}>{n.visible ? <Eye size={14} /> : <EyeOff size={14} />}</button>
        <button className={`lock${n.locked ? ' on' : ''}`} title="lock" onClick={(e) => { e.stopPropagation(); ed().updateNode(n.id, { locked: !n.locked }) }}>{n.locked ? <Lock size={12} /> : <LockOpen size={12} />}</button>
        {n.kind === 'raster' ? <img className={`thumb${n.mask && n.id === activeId && !editingMask ? ' target' : ''}`} src={thumbs.get(n.id)} alt="" title={n.mask ? 'click: paint the pixels · Ctrl-click: select layer transparency' : 'Ctrl-click: select layer transparency'} onClick={(e) => { e.stopPropagation(); if (e.ctrlKey || e.metaKey) ed().selectLayerAlpha(n.id); else { ed().setActive(n.id, false); ed().setView({ maskView: 'off' }) } }} /> : <span className="thumb kind-box">{n.kind === 'group' ? '▣' : n.kind === 'adjustment' ? '◐' : 'fx'}</span>}
        <span className="name">{n.name}<br /><span className="kind">{n.kind === 'raster' ? `${n.w}×${n.h}` : n.kind === 'group' ? `${n.children?.length ?? 0} · ${n.passthrough ? 'pass-through' : 'isolated'}` : n.type}{n.clip ? ' · clip' : ''}{n.blend !== 'normal' ? ` · ${n.blend}` : ''}{n.opacity < 1 ? ` · ${Math.round(n.opacity * 100)} %` : ''}</span></span>
        {n.mask && <button className={`mask-link${n.mask.linked ? ' on' : ''}`} title={n.mask.linked ? 'linked: the mask moves and transforms with the layer · click to unlink' : 'unlinked: the mask stays put · click to link'} onClick={(e) => { e.stopPropagation(); ed().toggleMaskLink(n.id) }}>{n.mask.linked ? <Link2 size={11} /> : <Unlink2 size={11} />}</button>}
        {n.mask
          ? <span className={`mask-wrap${n.mask.enabled ? '' : ' off'}`}><img className={`thumb mask-thumb${editingMask && n.id === activeId ? ' editing' : ''}`} src={thumbs.get('m:' + n.id)} alt="" title="mask · click: paint the mask · Alt-click: show it alone · Ctrl-click: load as selection · Shift-click: disable"
              onClick={(e) => {
                e.stopPropagation()
                if (e.shiftKey) { ed().updateNode(n.id, { mask: { ...n.mask!, enabled: !n.mask!.enabled } }, n.mask!.enabled ? 'disable mask' : 'enable mask'); return }
                ed().setActive(n.id, true)
                if (e.ctrlKey || e.metaKey) ed().loadSelectionFromMask()
                else if (e.altKey) ed().setView({ maskView: ed().maskView === 'gray' ? 'off' : 'gray' })
              }} /></span>
          : <span className="mask-box" title={hasSel ? 'add a mask revealing the selection · Alt-click: hiding it' : 'add a mask (reveal all) · Alt-click: hide all'} onClick={(e) => { e.stopPropagation(); ed().setActive(n.id); ed().addMask(n.id, hasSel ? (e.altKey ? 'hideSelection' : 'revealSelection') : (e.altKey ? 'hide' : 'reveal')) }}>+◐</span>}
      </div>
      {n.kind === 'group' && n.children && rows(n.children, depth + 1)}
    </div>
  ))
  return (
    <div>
      <div className="layers">{rows(doc.layers, 0)}</div>
      {editingMask && active?.mask && <div className="mask-hint">Editing the <b>mask</b> of “{active.name}” with the mask colours: the brush paints the foreground (black hides, white shows), the eraser the background — X swaps them; G fills, Delete clears to the background. Alt-click the mask thumbnail to see it alone.{' '}
        {active.kind === 'raster' && <button className="quiet" onClick={() => { ed().setActive(active.id, false); ed().setView({ maskView: 'off' }) }}>Edit pixels instead</button>}</div>}
      {active && (
        <div className="tool-opts" style={{ marginTop: 10 }}>
          <label>blend</label><BlendSelect value={active.blend} options={(active.kind === 'group' ? ['pass-through', ...BLEND_MODES] : BLEND_MODES).map((m) => ({ value: m, label: m.replace('-', ' ') }))}
            onChoose={(m) => ed().updateNode(active.id, { blend: m }, 'blend mode')} onPreview={(m) => ed().setView({ blendPreview: m ? { id: active.id, mode: m } : null })} />
          <ValueField label="opacity" value={active.opacity} min={0} max={1} scale={100} unit="%" onStart={start} onChange={(v) => ed().updateNode(active.id, { opacity: v })} onCommit={() => commit('opacity')} />
          {active.kind === 'raster' && <ValueField label="fill" value={active.fill ?? 1} min={0} max={1} scale={100} unit="%" onStart={start} onChange={(v) => ed().updateNode(active.id, { fill: v })} onCommit={() => commit('fill')} />}
          {active.kind === 'group' && <><label>group</label><div className="segmented"><button className={active.passthrough ? 'active' : ''} onClick={() => ed().updateNode(active.id, { passthrough: true }, 'group mode')}>pass-through</button><button className={!active.passthrough ? 'active' : ''} onClick={() => ed().updateNode(active.id, { passthrough: false }, 'group mode')}>isolated</button></div></>}
          <label>clip</label><label className="chk"><input type="checkbox" checked={active.clip} onChange={(e) => ed().updateNode(active.id, { clip: e.target.checked }, 'clip')} /> clip to the layer below</label>
          {active.mask && <MaskOptions n={active} />}
        </div>
      )}
      <div className="layer-actions">
        <CommandRow ids={['edit.layer.new', 'edit.layer.newGroup', 'edit.layer.group']} drops={{ 'edit.layer.new': 'duplicate', 'edit.layer.newGroup': 'group', 'edit.layer.group': 'group' }} />
        <MenuButton label="Add adjustment" icon={SlidersHorizontal} items={adjustmentMenu} />
        <MenuButton label="Add filter" icon={Sparkles} items={filterMenu} />
        <CommandRow ids={['gap', 'edit.layer.duplicate', 'edit.layer.mergeDown', 'edit.layer.up', 'edit.layer.down', 'gap', active?.mask ? 'edit.mask.remove' : 'edit.mask.add', 'edit.layer.visibility', 'edit.layer.lock', 'gap', 'edit.layer.delete']} drops={{ 'edit.layer.duplicate': 'duplicate', 'edit.layer.delete': 'delete' }} />
        {multi && <span className="hint">{ed().targetIds().length} layers selected</span>}
        <MenuButton label="More" items={layerMenu} />
      </div>
    </div>
  )
}

const pushStackEntry = (label: string, layerId: string, stack: DocumentStack) => ed().pushHistory({ label, layerId, kind: 'image', tiles: [], stack, at: Date.now() })

/** D52: the active layer's mask — enable, link, density, feather; Apply / Load / Remove (Layers tab and Properties, any node kind). */
function MaskOptions({ n }: { n: Node }) {
  const doc = useEditor((s) => s.doc)!
  const before = useRef<DocumentStack | null>(null)
  const m = n.mask
  if (!m) return null
  const start = () => { before.current = snapshot(doc) }
  const commit = (label: string) => { if (before.current) { pushStackEntry(label, n.id, before.current); before.current = null } }
  return (
    <>
      <label>mask</label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <label className="chk" title="Shift-click the mask thumbnail"><input type="checkbox" checked={m.enabled} onChange={() => ed().updateNode(n.id, { mask: { ...m, enabled: !m.enabled } }, m.enabled ? 'disable mask' : 'enable mask')} /> on</label>
        <label className="chk" title="a linked mask moves and transforms with the layer (the chain left of the mask thumbnail)"><input type="checkbox" checked={m.linked} onChange={() => ed().toggleMaskLink(n.id)} /> linked</label>
        {(n.kind === 'raster' ? ['edit.mask.apply', 'edit.mask.load', 'edit.mask.remove'] : ['edit.mask.load', 'edit.mask.remove']).map((id) => <CommandButton key={id} id={id} text />)}
      </div>
      <ValueField label="density" value={m.density ?? 1} min={0} max={1} scale={100} unit="%" onStart={start} onChange={(v) => ed().updateNode(n.id, { mask: { ...m, density: v } })} onCommit={() => commit('mask density')} />
      <ValueField label="feather" value={m.feather ?? 0} min={0} max={250} unit="px" onStart={start} onChange={(v) => ed().updateNode(n.id, { mask: { ...m, feather: v } })} onCommit={() => commit('mask feather')} />
    </>
  )
}

/** D57: quick actions per layer kind (PhotoCraft props_layout.rs), shown only while they can run. */
const QUICK: Record<string, string[]> = {
  raster: ['edit.sel.fromLayer', 'edit.transform', 'edit.mask.fromTransparency', 'edit.layer.lockAlpha', 'edit.layer.inkFromWhite', 'edit.layer.duplicate'],
  group: ['edit.layer.ungroup', 'edit.layer.duplicate'],
  adjustment: [], filter: [],
}
const KIND_LABEL: Record<string, string> = { raster: 'Pixel layer', group: 'Group', adjustment: 'Adjustment', filter: 'Filter' }

/** D57: the Properties panel follows the active layer — sections (PhotoCraft props_layout.rs), inline Levels / Curves / Colour balance
 * editors with the histogram of the layers below, the mask, the AI recipe and quick actions. */
function PropertiesTab() {
  const doc = useEditor((s) => s.doc)!
  const activeId = useEditor((s) => s.activeId)
  useEditor((s) => s.revision)                                        // quick actions re-evaluate their enablement
  const before = useRef<DocumentStack | null>(null)
  const n = findNode(doc, activeId)
  if (!n) return <span className="muted">Select a layer.</span>
  const start = () => { before.current = snapshot(doc) }
  const commit = (label: string) => { if (before.current) { pushStackEntry(label, n.id, before.current); before.current = null } }
  const quick = (QUICK[n.kind] ?? []).filter((id) => { const c = command(id); return !!c && isEnabled(c) })
  const params = n.params ?? {}
  const setParams = (p: Record<string, unknown>) => ed().updateNode(n.id, { params: p })
  const setParam = (k: string, v: unknown) => setParams({ ...params, [k]: v })
  const editorProps = { id: n.id, params, set: setParams, start, commit }
  const editor = n.kind === 'adjustment' && n.type === 'levels' ? <LevelsEditor key={n.id} {...editorProps} />
    : n.kind === 'adjustment' && n.type === 'curves' ? <CurvesEditor key={n.id} {...editorProps} />
    : n.kind === 'adjustment' && n.type === 'color_balance' ? <ColorBalanceEditor key={n.id} {...editorProps} />
    : null
  const defaults = n.kind === 'adjustment' ? ADJUSTMENT_DEFAULTS[n.type ?? ''] : n.kind === 'filter' ? FILTER_DEFAULTS[n.type ?? ''] : undefined
  return (
    <div className="props">
      <div className="props-title"><b>{n.name}</b><span className="kind">{KIND_LABEL[n.kind]}{n.type ? ` · ${n.type.replace('_', ' ')}` : ''}</span></div>
      {n.kind === 'raster' && (
        <Section id="layer" title="Layer">
          <div className="tool-opts">
            <ValueField label="x" value={n.x ?? 0} min={-100000} max={100000} unit="px" onStart={start} onChange={(v) => ed().updateNode(n.id, { x: Math.round(v) })} onCommit={() => commit('move layer')} />
            <ValueField label="y" value={n.y ?? 0} min={-100000} max={100000} unit="px" onStart={start} onChange={(v) => ed().updateNode(n.id, { y: Math.round(v) })} onCommit={() => commit('move layer')} />
            <label>size</label><span>{n.w}×{n.h}</span>
            <label>lineage</label><span className="mono">{n.lineage_asset_id ?? '—'}</span>
          </div>
        </Section>
      )}
      {n.kind === 'group' && (
        <Section id="group" title="Group">
          <div className="tool-opts">
            <label>layers</label><span>{n.children?.length ?? 0}</span>
            <label>mode</label><div className="segmented"><button className={n.passthrough ? 'active' : ''} onClick={() => ed().updateNode(n.id, { passthrough: true }, 'group mode')}>pass-through</button><button className={!n.passthrough ? 'active' : ''} onClick={() => ed().updateNode(n.id, { passthrough: false }, 'group mode')}>isolated</button></div>
          </div>
        </Section>
      )}
      {(n.kind === 'adjustment' || n.kind === 'filter') && (
        <Section id="adjustment" title={(n.type ?? '').replace('_', ' ')}>
          {editor ?? (
            <div className="tool-opts">
              {Object.entries(params).map(([k, v]) => {
                if (typeof v === 'number') { const [min, max, step] = PARAM_RANGES[k] ?? [-100, 100, 1]; return <Slider key={k} label={k.replace('_', ' ')} value={v} min={min} max={max} step={step} onStart={start} onChange={(x) => setParam(k, x)} onCommit={() => commit(`${n.type} ${k}`)} /> }
                if (typeof v === 'boolean') return <Fragment key={k}><label>{k.replace('_', ' ')}</label><input type="checkbox" checked={v} onChange={(e) => { start(); setParam(k, e.target.checked); commit(`${n.type} ${k}`) }} /></Fragment>
                if (typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v)) return <Fragment key={k}><label>{k}</label><input type="color" value={v} onFocus={start} onChange={(e) => setParam(k, e.target.value)} onBlur={() => commit(`${n.type} ${k}`)} /></Fragment>
                return null                                            // D57: no JSON text fields — structured values have their own editors
              })}
              {!Object.keys(params).length && <span className="hint full">no parameters</span>}
            </div>
          )}
          <div className="tool-opts" style={{ marginTop: 8 }}>
            <label>clip</label><label className="chk"><input type="checkbox" checked={n.clip} onChange={(e) => ed().updateNode(n.id, { clip: e.target.checked }, 'clip')} /> clip to the layer below</label>
            <label /><button type="button" className="quiet" disabled={!defaults} onClick={() => { if (defaults) { start(); setParams(JSON.parse(JSON.stringify(defaults))); commit(`${n.type} reset`) } }}>Reset to defaults</button>
          </div>
          <p className="hint">Previewed on the canvas with the compositor's own formulas; rendered exactly in the orchestrator on Save to Catalogue / Export (10 §3).{editor && n.type !== 'color_balance' ? ' The histogram shows the visible pixel layers below this one.' : ''}</p>
        </Section>
      )}
      {n.mask && (
        <Section id="mask" title="Layer mask">
          <div className="tool-opts"><MaskOptions n={n} /></div>
          <span className="hint">offset {n.mask.x}, {n.mask.y} ({n.mask.linked ? 'from the layer' : 'in the document'})</span>
        </Section>
      )}
      {n.kind === 'raster' && n.recipe && (
        <Section id="recipe" title="AI recipe">
          <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <button onClick={() => { const r = { ...n.recipe } as Record<string, unknown>; delete r.seed; delete r.job_id; delete r.batch_id; delete r.region; delete r.document_id; void ed().runAi({ ...r, seeds: [Math.floor(Math.random() * 2 ** 31)] }) }} title="runs the same recipe on the current document with a new seed (the selection must still cover the region)">Re-run (new seed)</button>
            <button className="quiet" onClick={() => void navigator.clipboard?.writeText(JSON.stringify(n.recipe, null, 2))}>copy JSON</button>
          </div>
          <pre className="recipe">{JSON.stringify(n.recipe, null, 1)}</pre>
        </Section>
      )}
      {quick.length > 0 && (
        <Section id="quick" title="Quick actions">
          <div className="quick-grid">{quick.map((id) => <CommandButton key={id} id={id} text />)}</div>
        </Section>
      )}
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
      if ((e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable], .modal')) return
      const st = ed()
      const k = e.key
      if (k === '\\' && !e.altKey) { e.preventDefault(); st.setView({ before: true }); return }              // hold: before
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && k.toLowerCase() === 'v') return             // D46: let the browser's paste event carry the clipboard
      if (magnetic.active && (k === 'Backspace' || k === 'Delete')) { e.preventDefault(); void magnetic.removeLast(); return }   // D59
      if (st.transform && k.startsWith('Arrow') && !e.ctrlKey && !e.altKey) {                        // D58: arrows nudge the box (Shift 10 px)
        e.preventDefault()
        const d = e.shiftKey ? 10 : 1, dx = k === 'ArrowLeft' ? -d : k === 'ArrowRight' ? d : 0, dy = k === 'ArrowUp' ? -d : k === 'ArrowDown' ? d : 0
        const t = st.transform
        st.setTransform({ quad: t.quad.map((c) => ({ x: c.x + dx, y: c.y + dy })) as typeof t.quad, pivot: { x: t.pivot.x + dx, y: t.pivot.y + dy } })
        return
      }
      if (k === 'Escape') { if (st.lassoPoly) st.setLassoPoly(null); else if (st.transform) st.cancelTransform(); else if (st.quickMask) st.setView({ quickMask: false }); else if (st.selection) st.deselect(); return }
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
    const paste = (e: ClipboardEvent) => {                              // D46: Ctrl+V — an image from another app, or the editor's clipboard
      if (useSession.getState().ui.suite !== 'edit' || !ed().doc) return
      if (e.target instanceof Element && e.target.closest('input, textarea, [contenteditable], .modal')) return   // the target may be the window
      e.preventDefault()
      void ed().pasteFromEvent(Array.from(e.clipboardData?.files ?? []))
    }
    window.addEventListener('paste', paste)
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
          if (q.get('verify')) {                                                                        // wait for the renderer (GPU init is slow headless), then compare
            const t0 = Date.now(); const tick = () => { if (ed().extractor) void ed().compareWithExact(); else if (Date.now() - t0 < 30000) setTimeout(tick, 250) }; setTimeout(tick, 500)
          }
          const tab = q.get('tab'); if (tab) setRailTab('edit', tab)                                      // dev: open a panel section
          if (q.get('sel') === 'all') ed().selectAll()                                                   // dev: marching ants
          if (q.get('wasmprobe')) void probeSmartSelect().then(() => console.info('smart-select worker ready'), (err) => console.error('smart-select worker failed', err))   // D59: csp_check
          if (q.get('sel') === 'half') { const s = ed().ensureSelection(); s.ctx.fillStyle = '#fff'; s.ctx.beginPath(); s.ctx.ellipse(s.width / 2, s.height / 2, s.width / 3, s.height / 3, 0, 0, Math.PI * 2); s.ctx.fill(); s.refresh(); ed().bump() }
          if (q.get('xform')) { ed().beginTransform(); const t = ed().transform; if (t) ed().setTransform({ quad: rotateAboutPivot({ ...t, quad: scaleAboutPivot(t, 0.8, 0.9) }, 14) }) }   // dev: transform box
        })
        return true
      }
      if (!tryOpen()) unsubDeep = useSession.subscribe(() => { if (tryOpen()) unsubDeep() })
    }
    ensureEditorAutosave()                                       // B20: survives suite switches (this hook unmounts with the strip)
    return () => { window.removeEventListener('keydown', down, { capture: true }); window.removeEventListener('keyup', up); window.removeEventListener('paste', paste); unsubDeep() }
  }, [])
}

/** The empty Edit stage takes a dropped tile and opens it (frame/drag.ts). */
function EmptyDrop({ children }: { children: React.ReactNode }) {
  const { ref, over } = useDropTarget(onlyAssets, (p) => void ed().openFromAsset(assetIds(p)[0]))
  return <div ref={ref} className={`edit-empty${over ? ' drop-over' : ''}`}>{children}</div>
}

export const EditSuite: SuiteDef = {
  id: 'edit',
  rail: [{ id: 'tools', label: 'Tool options', icon: <SlidersHorizontal size={18} /> }, { id: 'brushes', label: 'Brushes', icon: <Brush size={18} /> }, { id: 'selection', label: 'Selection', icon: <Lasso size={18} /> },
    { id: 'ai', label: 'AI', icon: <Sparkles size={18} /> }, { id: 'documents', label: 'Documents', icon: <Files size={18} /> }],
  Panel, Strip, Stage, Inspector, PrimaryAction,
}
