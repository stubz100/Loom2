// Edit suite (10): toolbox and tool options in the Panel, zoom/overlay strip, PixiJS stage, inspector with
// Layers / Properties / History / Info; Save (the document and a Catalogue version, D95) · Export as the pinned primary actions.
import { Ellipsis, Eye, EyeOff, Link2, Lock, LockOpen, SlidersHorizontal, Sparkles, Trash2, Unlink2, X } from 'lucide-react'
import { Help } from '../../frame/Help'
import { PresetPanel } from '../../frame/PresetPanel'
import { Fragment, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { api, http, unwrap } from '../../api/client'
import { isDocumentPreview, type DocumentPreview, type DocumentRecipe } from '../../api/types'
import { CommandButton, CommandRow, MenuButton } from '../../frame/CommandButton'
import { command, handleKeyFor, isEnabled, markUsed, matchesCommand, parseChord, runCommand, sep, titleFor, type MenuItem } from '../../frame/commands'
import { useKeymap } from '../../frame/keymap'
import { openPressMenu, showMenu } from '../../frame/ContextMenu'
import { DEV_HOOKS } from '../../devHooks'
import { DEFAULT_RAIL } from '../../frame/railTabs'
import { setRailTab, type SuiteDef } from '../../frame/suiteRegistry'
import { useColumnSync } from '../../frame/columnSync'
import { useMakeFor } from '../../store/origin'
import { byOrder } from '../../store/modelCaps'
import { askConfirm, useSession } from '../../store/session'
import { adjustmentMenu, filterMenu, layerMenu, MORE_TOOLS, TOOLS as TOOL_TABLE } from './editCommands'
import { AI_OP_LABEL, aiModels, aiReason, aiRecipe, opCandidates, selectPlan, type AiCtx } from './aiRecipes'
import { AiRunButton, BlendSelect, LatchButton, RendererButton, ValueField } from './widgets'
import { blendLabel, typeLabel } from './labels'
import { ColorBalanceEditor, CurvesEditor, LevelsEditor, Section } from './propsEditors'
import { readout, rotateAboutPivot, scaleAboutPivot, type Interp, type TransformMode } from './transform'
import { magnetic } from './smartselect/magnetic'
import { probe as probeSmartSelect } from './smartselect/client'
import { EditorCanvas } from './EditorCanvas'
import { ADJUSTMENT_DEFAULTS, BLEND_MODES, countRasters, ensureEditorAutosave, FILTER_DEFAULTS, findNode, useEditor, walk, type BrushPreset, type DocSummary, type DocumentStack, type Node } from './editorStore'
import { useAiPanel, type AiOp, type AiPanelState } from './aiPanelStore'
import { planSize } from './planSize'
import './edit.css'
import './fonts.css'
import { fontFamilies, fontString } from './textFonts'
import { padOf, type TextBlock } from './textRaster'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { editOpenDrop, layerDrop, refDrop } from '../../frame/dropRules'
import { navigate } from '../../frame/router'
import { registerKeyHost } from '../../frame/keyHosts'

const TOOLS = TOOL_TABLE.map(([tool, label, key, icon]) => ({ tool, label, key, icon }))
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
const ed = () => useEditor.getState()
const snapshot = (d: DocumentStack): DocumentStack => JSON.parse(JSON.stringify(d))

/** Range + value. With `num` the value is also an editable number field: `scale` 100 shows a 0–1 value as a percentage, `unit` is its suffix. */
/** A labelled number in the grid: the same ValueField as everywhere else (scrub, type, ▾ slider). */
function Slider({ label, value, min, max, step, onChange, onStart, onCommit, scale, unit }: { label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void; onStart?: () => void; onCommit?: () => void; scale?: number; unit?: string }) {
  return <ValueField label={label} value={value} min={min} max={max} step={step} scale={scale} unit={unit} onChange={onChange} onStart={onStart} onCommit={onCommit} />
}

function Swatches() {
  const b = useEditor((s) => s.brush)
  const forMask = useEditor((s) => s.maskPairActive)
  return (
    <div className={`swatch-pair${forMask ? ' for-mask' : ''}`} title={forMask ? 'the mask colours: painted as grey — black hides, white shows; X swaps' : undefined}>
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
      <Help className="full" text={"Paint over what you want: the selection grows to its edges (computed when you let go); every stroke adds, Alt subtracts. Runs on the CPU in a Worker, no GPU."} />
    </div>
  )
}
/** D62: Spot Healing (PhotoCraft): the brush diameter and what it samples; the healed pixels go on a "Spot healing" layer. */
function HealOptions() {
  const size = useEditor((s) => s.healSize)
  const all = useEditor((s) => s.healSampleAll)
  const ok = useSession((s) => !!s.capabilities?.content_aware?.available)
  return (
    <div className="tool-opts">
      <ValueField label="size" value={size} min={1} max={1000} unit="px" title="brush diameter — [ and ] change it" onChange={(v) => ed().setView({ healSize: Math.max(1, Math.round(v)) })} />
      <label /><label className="chk" title="heal what you see (all visible layers); off: only the active layer"><input type="checkbox" checked={all} onChange={(e) => ed().setView({ healSampleAll: e.target.checked })} /> sample all layers</label>
      {ok ? <Help className="full" text={"Paint over a blemish: on release it is rebuilt from its surroundings (PatchMatch, then a Poisson blend) onto a \"Spot healing\" layer above — non-destructive, one undo step per stroke. CPU, no GPU."} /> : <span className="hint full">needs the native extension: uv sync --project orchestrator --extra native, then restart the orchestrator</span>}
    </div>
  )
}
/** D154: the Text tool's options — the look of the next text layer. */
function TextToolOptions() {
  const d = useEditor((s) => s.textDefaults)
  const set = (p: Partial<typeof d>) => ed().setTextDefaults(p)
  return (
    <div className="tool-opts text-opts">
      <label>font</label><FontSelect value={d.font} onChange={(font) => set({ font })} />
      <ValueField label="size" value={d.size} min={4} max={1000} unit="px" onChange={(v) => set({ size: Math.max(4, Math.round(v)) })} />
      <label>colour</label><div className="row"><input type="color" value={d.colour} onChange={(e) => set({ colour: e.target.value })} /><LatchButton on={d.weight === 'bold'} label={<b>B</b>} title="bold" onToggle={() => set({ weight: d.weight === 'bold' ? 'normal' : 'bold' })} /><LatchButton on={d.italic} label={<i>I</i>} title="italic" onToggle={() => set({ italic: !d.italic })} /></div>
      <label>outline</label><div className="row"><input type="checkbox" checked={!!d.outline} title="a stroke around the glyphs" onChange={(e) => set({ outline: e.target.checked ? { width: 2, colour: '#000000' } : null })} />{d.outline && <input type="color" value={d.outline.colour} onChange={(e) => set({ outline: { ...d.outline!, colour: e.target.value } })} />}</div>
      {d.outline && <ValueField label="outline px" value={d.outline.width} min={0} max={64} unit="px" onChange={(v) => set({ outline: { ...d.outline!, width: v } })} />}
      <Help className="full" text={"Click the canvas to place text, drag to draw a box that wraps. Type in place; ✓ or Ctrl+Enter keeps it, ✕ or Esc drops the change. Later: double-click the layer with the Move tool, or Edit text… on its right-click; the Properties tab edits every field. The pixels are the text as drawn — exports and the compositor see them; Rasterize text keeps the pixels and drops the editing."} />
    </div>
  )
}
/** D154: the font picker — the bundled families, or any family the system knows by name. */
function FontSelect({ value, onChange }: { value: string; onChange: (family: string) => void }) {
  const families = fontFamilies()
  const other = !families.includes(value)
  const [custom, setCustom] = useState(other ? value : '')
  return (
    <div className="row">
      <select value={other ? '__other' : value} onChange={(e) => { if (e.target.value === '__other') { const f = custom.trim() || 'Arial'; setCustom(f); onChange(f) } else onChange(e.target.value) }}>
        {families.map((f) => <option key={f} value={f} style={{ fontFamily: f }}>{f}</option>)}<option value="__other">a system font…</option>
      </select>
      {other && <input className="font-name" value={custom} placeholder="family name" title="a font installed on this computer, by its family name" onChange={(e) => setCustom(e.target.value)} onBlur={() => { if (custom.trim()) onChange(custom.trim()) }} onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); e.stopPropagation() }} />}
    </div>
  )
}
/** D154: a text layer's block in Properties — every field re-rasterises live; a scrub is one undo step. */
function TextSection({ n }: { n: Node }) {
  const t = n.text!
  const g = (gesture: 'start' | 'move' | 'end' | undefined, patch: Partial<TextBlock>, label?: string) => ed().setText(n.id, patch, gesture, label)
  return (
    <Section id="text" title="Text" extra={<CommandButton id="edit.text.edit" text />}>
      <div className="tool-opts text-opts">
        <label>text</label><textarea className="text-content" rows={3} value={t.content} spellCheck={false} onChange={(e) => g('move', { content: e.target.value })} onBlur={() => g('end', {}, 'edit text')} onKeyDown={(e) => e.stopPropagation()} />
        <label>font</label><FontSelect value={t.font} onChange={(font) => g(undefined, { font }, 'text font')} />
        <ValueField label="size" value={t.size} min={4} max={1000} unit="px" onStart={() => g('start', {})} onChange={(v) => g('move', { size: Math.max(4, Math.round(v)) })} onCommit={() => g('end', {}, 'text size')} />
        <label>colour</label><div className="row"><input type="color" value={t.colour} onFocus={() => g('start', {})} onChange={(e) => g('move', { colour: e.target.value })} onBlur={() => g('end', {}, 'text colour')} /><LatchButton on={t.weight === 'bold'} label={<b>B</b>} title="bold" onToggle={() => g(undefined, { weight: t.weight === 'bold' ? 'normal' : 'bold' }, 'text weight')} /><LatchButton on={t.italic} label={<i>I</i>} title="italic" onToggle={() => g(undefined, { italic: !t.italic }, 'text italic')} /></div>
        <label>align</label><div className="segmented">{(['left', 'center', 'right'] as const).map((a) => <button key={a} className={t.align === a ? 'active' : ''} onClick={() => g(undefined, { align: a }, 'text align')}>{a}</button>)}</div>
        <ValueField label="leading" value={t.leading} min={0.5} max={4} step={0.05} unit="×" onStart={() => g('start', {})} onChange={(v) => g('move', { leading: Math.round(v * 100) / 100 })} onCommit={() => g('end', {}, 'text leading')} />
        <ValueField label="tracking" value={t.tracking} min={-50} max={200} unit="px" onStart={() => g('start', {})} onChange={(v) => g('move', { tracking: Math.round(v) })} onCommit={() => g('end', {}, 'text tracking')} />
        <label>outline</label><div className="row"><input type="checkbox" checked={!!t.outline} onChange={(e) => g(undefined, { outline: e.target.checked ? { width: 2, colour: '#000000' } : null }, 'text outline')} />{t.outline && <input type="color" value={t.outline.colour} onFocus={() => g('start', {})} onChange={(e) => g('move', { outline: { ...t.outline!, colour: e.target.value } })} onBlur={() => g('end', {}, 'outline colour')} />}</div>
        {t.outline && <ValueField label="outline px" value={t.outline.width} min={0} max={64} unit="px" onStart={() => g('start', {})} onChange={(v) => g('move', { outline: { ...t.outline!, width: v } })} onCommit={() => g('end', {}, 'outline width')} />}
        {t.box && <><label>box</label><span>{t.box[0]}×{t.box[1]} px <button className="quiet" title="the text takes the size of its lines instead" onClick={() => g(undefined, { box: null }, 'point text')}>→ point text</button></span></>}
        <label /><div className="row"><CommandButton id="edit.text.rasterize" text /></div>
      </div>
    </Section>
  )
}
/** D154: the inline editor — a textarea at the layer's place and zoom in the layer's own font; the layer hides under it while it is open. */
function TextEditOverlay() {
  const id = useEditor((s) => s.editingText)
  const doc = useEditor((s) => s.doc)
  const zoom = useEditor((s) => s.zoom), pan = useEditor((s) => s.pan)
  useEditor((s) => s.revision)
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { if (id) { const el = ref.current; el?.focus(); el?.select() } }, [id])
  const n = id ? findNode(doc, id) : null
  if (!id || !n?.text) return null
  const t = n.text
  const pad = padOf(t)
  const style: CSSProperties = { left: pan.x + (n.x ?? 0) * zoom, top: pan.y + (n.y ?? 0) * zoom, width: n.w ?? 1, height: n.h ?? 1, transform: `scale(${zoom})`, transformOrigin: '0 0' }
  const ta: CSSProperties = { font: fontString(t.font, t.size, t.weight, t.italic), color: t.colour, lineHeight: `${Math.max(1, Math.round(t.size * t.leading))}px`, letterSpacing: `${t.tracking}px`, textAlign: t.align, padding: pad,
    ...(t.outline && t.outline.width > 0 ? { WebkitTextStroke: `${t.outline.width}px ${t.outline.colour}`, paintOrder: 'stroke fill' } : {}) }
  return (
    <div className={`text-edit${t.box ? ' box' : ''}`} style={style} onPointerDown={(e) => e.stopPropagation()}>
      <textarea ref={ref} value={t.content} style={ta} spellCheck={false} placeholder="type…" onChange={(e) => ed().setText(id, { content: e.target.value }, 'move')}
        onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ed().endTextEdit(true) } else if (e.key === 'Escape') { e.preventDefault(); ed().endTextEdit(false) } e.stopPropagation() }} />
      <div className="text-edit-bar" style={{ transform: `scale(${1 / zoom})`, transformOrigin: '0 0' }}><CommandButton id="edit.text.apply" /><CommandButton id="edit.text.cancel" /><Help text={"✓ or Ctrl+Enter keeps the text; ✕ or Esc drops the change. The font, size, colour and outline live in the Properties tab; a new text layer takes the Text tool's options."} /></div>
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

/** D90 (02 §9, §10): the storyboard essentials up front; Magic wand, Spot healing and Eyedropper behind More tools, whose slot shows the
 * active tool when it is one of them. Every tool keeps its key and its place in the canvas menu's Tool ▸. */
function Toolbox() {
  const tool = useEditor((s) => s.tool)
  useKeymap((k) => k.version)                                          // D72: the tooltips follow a remap
  const label = (x: (typeof TOOLS)[number]) => { const c = command(`edit.tool.${x.tool}`); return c ? titleFor(c, x.label) : x.label }
  const more = TOOLS.filter((x) => MORE_TOOLS.includes(x.tool)), shown = more.find((x) => x.tool === tool)
  const moreMenu = (): MenuItem[] => more.map((x) => ({ cmd: `edit.tool.${x.tool}`, label: x.label, checked: x.tool === tool }))
  return (
    <div className="toolbox">
      {TOOLS.filter((x) => !MORE_TOOLS.includes(x.tool)).map((x) => { markUsed(`edit.tool.${x.tool}`); return <button key={x.tool} className={`tool${tool === x.tool ? ' active' : ''}`} title={label(x)} onClick={() => runCommand(`edit.tool.${x.tool}`)}><b>{x.key || <x.icon size={14} />}</b><span>{x.label}</span></button> })}
      <button type="button" className={`tool more${shown ? ' active' : ''}`} aria-haspopup="menu" title={`${shown ? `${label(shown)} · ` : ''}More tools: ${more.map((x) => x.label).join(', ')} — press and drag to one, or click`}
        onPointerDown={(e) => openPressMenu(e, moreMenu)} onContextMenu={(e) => e.preventDefault()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') openPressMenu({ button: 0, currentTarget: e.currentTarget, preventDefault: () => e.preventDefault() }, moreMenu, true) }}>
        <b>{shown ? shown.key || <shown.icon size={14} /> : <Ellipsis size={14} />}</b><span>{shown ? shown.label : 'More tools'} ▾</span>
      </button>
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
  useEditor((s) => !!s.selection)                                      // D90 (B9): the crop commands' enabled state follows the selection
  const activeId = useEditor((s) => s.activeId)
  const transforming = useEditor((s) => !!s.transform)
  const [cv, setCv] = useState({ w: 0, h: 0, ax: 0.5, ay: 0.5 })
  useEffect(() => { if (doc) setCv((c) => ({ ...c, w: doc.w, h: doc.h })) }, [doc?.w, doc?.h]) // eslint-disable-line react-hooks/exhaustive-deps
  const set = (p: Partial<typeof b>) => ed().setBrush(p)
  const nudge = (dx: number, dy: number) => { const n = findNode(doc, activeId); if (n?.kind === 'raster') ed().updateNode(n.id, { x: (n.x ?? 0) + dx, y: (n.y ?? 0) + dy }, 'nudge', `nudge:${n.id}`) }   // D43: a run of nudges is one step
  const modeSeg = <div className="segmented">{(['replace', 'add', 'subtract', 'intersect'] as const).map((m) => <button key={m} className={mode === m ? 'active' : ''} title={{ replace: 'new selection', add: 'add (Shift)', subtract: 'subtract (Alt)', intersect: 'intersect (Shift+Alt)' }[m]} onClick={() => ed().setView({ selectionMode: m })}>{m}</button>)}</div>
  const featherField = <ValueField label="feather" value={sv.marqueeFeather} min={0} max={250} step={1} unit="px" onChange={(v) => ed().setView({ marqueeFeather: v })} />
  return (
    <div>
      <Toolbox />
      <h4 className="sect">{TOOLS.find((x) => x.tool === tool)?.label}</h4>
      {(tool === 'brush' || tool === 'eraser') && (
        <div className="tool-opts">
          <BrushControls />
          {tool === 'brush' && <><label>colour</label><Swatches /></>}
          <label /><CommandRow ids={['edit.brush.smaller', 'edit.brush.larger', 'edit.brush.softer', 'edit.brush.harder']} />
          <Help className="full" text={"[ ] size · Shift+[ ] hardness · 0–9 opacity · X swap · D defaults · pressure controls appear once a pen is detected."} />
        </div>
      )}
      {tool === 'marquee' && <div className="tool-opts"><label>shape</label><div className="segmented">{(['rect', 'ellipse'] as const).map((m) => <button key={m} className={marqueeShape === m ? 'active' : ''} onClick={() => ed().setView({ marqueeShape: m })}>{m}</button>)}</div><label>mode</label>{modeSeg}{featherField}
        <label>style</label><div className="segmented">{(['normal', 'ratio', 'size'] as const).map((m) => <button key={m} className={sv.marqueeStyle === m ? 'active' : ''} title={{ normal: 'drag any rectangle', ratio: 'fixed ratio W : H', size: 'fixed size W × H px, hanging from the pointer' }[m]} onClick={() => ed().setView({ marqueeStyle: m })}>{m === 'ratio' ? 'fixed ratio' : m === 'size' ? 'fixed size' : m}</button>)}</div>
        {sv.marqueeStyle !== 'normal' && <><ValueField label={sv.marqueeStyle === 'ratio' ? 'ratio W' : 'width'} value={sv.marqueeW} min={1} max={sv.marqueeStyle === 'ratio' ? 100 : 16384} step={1} unit={sv.marqueeStyle === 'ratio' ? undefined : 'px'} onChange={(v) => ed().setView({ marqueeW: v })} /><ValueField label={sv.marqueeStyle === 'ratio' ? 'ratio H' : 'height'} value={sv.marqueeH} min={1} max={sv.marqueeStyle === 'ratio' ? 100 : 16384} step={1} unit={sv.marqueeStyle === 'ratio' ? undefined : 'px'} onChange={(v) => ed().setView({ marqueeH: v })} /></>}
        <Help className="full" text={"Shift adds, Alt subtracts, Shift+Alt intersects while dragging."} /></div>}
      {tool === 'lasso' && <div className="tool-opts"><label>kind</label><div className="segmented">{(['freehand', 'polygon', 'magnetic'] as const).map((m) => <button key={m} className={sv.lassoKind === m ? 'active' : ''} onClick={() => ed().setView({ lassoKind: m })}>{m}</button>)}</div><label>mode</label>{modeSeg}{featherField}
        {sv.lassoKind === 'magnetic' && <MagneticOptions />}
        {sv.lassoOpen && <><label>{sv.lassoKind === 'magnetic' ? 'border' : 'polygon'}</label><span><CommandButton id="edit.sel.polyClose" text /> {sv.lassoKind === 'magnetic' && <CommandButton id="edit.sel.magBack" text />} <CommandButton id="edit.sel.polyCancel" text /></span></>}
        <Help className="full" text={`${sv.lassoKind === 'polygon' ? 'click to add corners; click the first corner, double-click or ✓ to close' : sv.lassoKind === 'magnetic' ? 'click on an edge, then move along it — the border snaps to the edge and drops points as it goes; click to place a point, Alt-click a straight segment (Alt-drag: freehand), Backspace removes a point; click the first point, double-click or ✓ to close' : 'drag a freehand outline'}; Shift adds, Alt subtracts, Shift+Alt intersects`} /></div>}
      {tool === 'quick' && <QuickOptions />}
      {tool === 'heal' && <HealOptions />}
      {tool === 'text' && <TextToolOptions />}
      {tool === 'wand' && <div className="tool-opts"><label>mode</label>{modeSeg}<Slider label="tolerance" value={tolerance} min={0} max={255} step={1} onChange={(v) => ed().setView({ tolerance: v })} />
        <label /><label className="chk" title="look at every visible layer instead of the active one"><input type="checkbox" checked={sv.wandMerged} onChange={(e) => ed().setView({ wandMerged: e.target.checked })} /> sample all layers</label>
        <label /><span><label className="chk"><input type="checkbox" checked={sv.wandContiguous} onChange={(e) => ed().setView({ wandContiguous: e.target.checked })} /> contiguous</label> <label className="chk"><input type="checkbox" checked={sv.wandAA} onChange={(e) => ed().setView({ wandAA: e.target.checked })} /> anti-alias</label></span>
        <Help className="full" text={"Tolerance per channel including alpha; transparent pixels match each other whatever their hidden colour."} /></div>}
      {tool === 'fill' && <div className="tool-opts"><label>mode</label><div className="segmented">{(['solid', 'linear', 'radial'] as const).map((m) => <button key={m} className={fillMode === m ? 'active' : ''} onClick={() => ed().setView({ fillMode: m })}>{m}</button>)}</div><label>colour</label><Swatches /><Slider label="opacity" value={b.opacity} min={0} max={1} step={0.01} scale={100} unit="%" onChange={(v) => set({ opacity: v })} /><span className="hint full">{fillMode === 'solid' ? 'click fills the selection, or the whole layer (mask: white) when nothing is selected' : `drag from the foreground colour to the background colour (${fillMode}); limited to the selection when there is one; on a mask: white → black`}</span></div>}
      {tool === 'move' && (
        <div className="tool-opts">
          <label>nudge</label><div className="nudge"><button onClick={() => nudge(0, -1)}>▲</button><button onClick={() => nudge(-1, 0)}>◀</button><button onClick={() => nudge(1, 0)}>▶</button><button onClick={() => nudge(0, 1)}>▼</button></div>
          <label>transform</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{transforming ? <CommandRow ids={['edit.transform.apply', 'edit.transform.cancel']} /> : <CommandButton id="edit.transform" text />}<CommandRow ids={['edit.layer.flipH', 'edit.layer.flipV', 'edit.layer.rot270', 'edit.layer.rot90']} /></div>
          <Help className="full" text={transforming ? 'drag inside to move, a corner or edge to scale (in proportion — Shift frees it, Alt from the reference point), outside to rotate (Shift snaps 15°); Ctrl-drag a corner to distort, an edge to skew, Ctrl+Alt+Shift a corner for perspective (or pick the mode in the strip); Alt-click places the reference point; Enter / double-click applies, Esc cancels' : 'drag the active raster layer on the canvas; Ctrl+T enters free transform'} />
        </div>
      )}
      {tool === 'crop' && (
        <div className="tool-opts">
          <ValueField label="width" value={cv.w} min={1} max={16384} step={1} unit="px" onChange={(v) => setCv({ ...cv, w: v })} />
          <ValueField label="height" value={cv.h} min={1} max={16384} step={1} unit="px" onChange={(v) => setCv({ ...cv, h: v })} />
          <label>anchor</label><div className="anchor">{[0, 0.5, 1].map((ay) => [0, 0.5, 1].map((ax) => <button key={`${ax}-${ay}`} className={cv.ax === ax && cv.ay === ay ? 'active' : ''} onClick={() => setCv({ ...cv, ax, ay })}>•</button>))}</div>
          <label /><div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}><button disabled={!doc || transforming || (cv.w === doc.w && cv.h === doc.h)} onClick={() => ed().resizeCanvas(cv.w, cv.h, cv.ax, cv.ay)}>Resize canvas</button><CommandButton id="edit.crop.apply" text /><CommandButton id="edit.crop.cancel" text /></div>
          <Help className="full" text={"Drag on the canvas to draw the crop rectangle (any selection crops too); Enter or a double-click inside applies it, Esc cancels — or set the canvas size above. Layers keep their pixels; a smaller canvas only hides what lies outside."} />
        </div>
      )}
      {tool === 'eyedropper' && <p className="hint">Eyedropper <Help text={"Click the canvas to pick the composited colour into the foreground swatch."} /></p>}
      {tool === 'hand' && <p className="hint">Hand <Help text={"Drag to pan. Space + drag pans with any tool; middle mouse too."} /></p>}
      {tool === 'zoom' && <p className="hint">Zoom <Help text={"Click zooms in, Alt-click out; Ctrl+wheel zooms anywhere; Ctrl+0 fit, Ctrl+1 1:1."} /></p>}
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
      <Help className="full" text={"Smoothing pulls the brush on a string (it catches up when you pause); Shift-click draws a straight line from the last stroke; Alt-click picks a colour."} />
    </>
  )
}

function BrushesTab() {
  const b = useEditor((s) => s.brush)
  const mine = useEditor((s) => s.brushPresets)
  const presets = [...BRUSH_PRESETS, ...mine]
  const isActive = (p: BrushPreset) => p.size === b.size && Math.abs(b.hardness - p.hardness) < 0.005 && Math.abs(b.flow - p.flow) < 0.005 && Math.abs(b.opacity - p.opacity) < 0.005 && Math.abs(b.spacing - p.spacing) < 0.005
  return (
    <div>
      {(() => {                                                          // D119 (SC2): the brushes behind the +, the one in use beside it
        const dab = (p: BrushPreset) => <span className="dab" style={{ width: Math.max(8, Math.min(26, p.size / 6)), height: Math.max(8, Math.min(26, p.size / 6)), background: `radial-gradient(circle, ${b.color} ${Math.round(p.hardness * 100)}%, transparent 100%)`, opacity: Math.max(0.35, Math.min(1, p.flow + 0.3)) }} />
        const items = presets.map((p) => ({ id: p.name, label: p.name, icon: dab(p), hint: `${p.size} px · hardness ${Math.round(p.hardness * 100)} % · opacity ${Math.round(p.opacity * 100)} % · flow ${Math.round(p.flow * 100)} %${p.builtin ? ' · built in' : ''}` }))
        const active = presets.find((p) => isActive(p))
        return (
          <div className="brush-presets">
            <PresetPanel label="brush presets" size={36} showText items={items} selected={active?.name ?? null} chosen={active ? items.filter((i) => i.id === active.name) : []}
              title="The brushes: pick one, save the current brush, delete yours" saveLabel="Save the current brush as a preset…" onSave={(name) => { if (name) ed().saveBrushPreset(name) }}
              onPick={(id) => { const p = presets.find((x) => x.name === id); if (p) ed().applyBrushPreset(p) }}
              verbs={(focused) => {
                const p = presets.find((x) => x.name === focused)
                if (!p) return <span className="hint">Click a brush: it is applied; yours can be deleted here.</span>
                return p.builtin ? <span className="hint">{p.name} is built in.</span> : <button type="button" className="quiet danger" onClick={() => ed().deleteBrushPreset(p.name)}>Delete “{p.name}”</button>
              }} />
            {active && <span className="hint">{active.name} · {active.size} px</span>}
          </div>)
      })()}
      <h4 className="sect">Current brush</h4>
      <div className="tool-opts">
        <BrushControls />
        <label>colour</label><Swatches />
      </div>
      <p className="hint"><Help text={"Type a diameter or any value directly in the number fields. Pressure → size / opacity / flow and the pen curve appear once a pen is detected."} /></p>
    </div>
  )
}

function SelectionTab() {
  const quickMask = useEditor((s) => s.quickMask)
  const px = useEditor((s) => s.selModifyPx)
  useEditor((s) => `${!!s.selection}${s.activeId}${!!s.clipboard}${!!s.transform}`)   // D90: the buttons' enabled state follows what their commands read
  return (
    <div className="tool-opts">
      <label>select</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.sel.all', 'edit.sel.none', 'edit.sel.invert', 'edit.sel.fromLayer'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <ValueField label="amount" value={px} min={1} max={500} step={1} unit="px" onChange={(v) => ed().setView({ selModifyPx: v })} />
      <label>modify</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['expand', 'contract', 'border', 'smooth', 'feather'].map((op) => <CommandButton key={op} id={`edit.sel.${op}`} text label={op[0].toUpperCase() + op.slice(1)} />)}</div>
      <label>Quick mask</label><button className={quickMask ? 'active' : ''} onClick={() => runCommand('edit.sel.quickMask')} title="Quick mask (Q)">{quickMask ? 'painting the selection (red = unselected)' : 'paint the selection with the brush'}</button>
      <label>mask</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.mask.fromSelection', 'edit.mask.load', 'edit.sel.crop'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      {/* D90 (01 §11.3): the clipboard's panel home (also the canvas menu); Ctrl+V still arrives as the browser's paste event (D46) */}
      <label>clipboard</label><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{['edit.copy', 'edit.cut', 'edit.copyMerged', 'edit.paste', 'edit.pasteInPlace', 'edit.layer.viaCopy', 'edit.layer.viaCut'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <RefineEdgeControls />
      <Help className="full" text={"Expand / contract grow round by the amount; border makes a band that wide around the edge; smooth removes specks and jaggies; feather softens with Photoshop's radius. Every change, and every selection tool, is one undo step."} />
    </div>
  )
}

/** D152: the reference deck in the AI tab — Generate's slots (drop a Catalogue tile, ✕, ◀, a right-click), the model's limit; a model that
 *  takes none says so. The images go in after the region's own (a character's face, a material the fill should match). */
function RefSlotsAi({ model }: { model: string }) {
  const p = useAiPanel()
  const caps = useSession((s) => s.capabilities)
  const max = aiModels({ p, caps }).refsMax(model)
  const current = p.refs.map((r) => r.asset_id)
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && refDrop(current, d, max).verdict.ok,
    (d) => { const { take, verdict } = refDrop(current, d, max); p.addRefs(take); if (verdict.ok && verdict.label?.includes(' · ')) useSession.getState().toast(verdict.label.replace(/^Add/, 'Added'), 'info') },
    (d) => refDrop(current, d, max).verdict)
  if (!max) return p.refs.length ? <><label /><p className="hint">{caps?.models[model]?.label ?? model} takes no reference images — the {p.refs.length} in the deck are not sent <CommandButton id="edit.ai.clearRefs" text /></p></> : null
  const slots = Array.from({ length: Math.min(10, Math.max(max, p.refs.length)) }, (_, i) => p.refs[i])
  return (
    <>
      <label>references</label>
      <div ref={dropRef} className="ref-slots ai-refs" data-max={max}>
        {slots.map((r, i) => (
          <div key={i} className={`ref-slot${over ? ' over' : ''}`} title={r ? `reference image ${i + 1}` : `drop a Catalogue tile here · reference ${i + 1} of ${max}`}
            onContextMenu={(e) => { if (!r) return; showMenu(e, [
              { label: 'Remove reference', icon: X, run: () => p.removeRef(r.asset_id) },
              { label: 'Move first', disabled: i === 0, run: () => p.moveRef(i, 0) },
              { label: 'Move left', disabled: i === 0, run: () => p.moveRef(i, i - 1) },
              { label: 'Move right', disabled: i >= p.refs.length - 1, run: () => p.moveRef(i, i + 1) },
              sep, { cmd: 'edit.ai.clearRefs' },
            ]) }}>
            {r ? <>
              <img src={api.thumbUrl(r.asset_id, 256)} alt="" />
              <span className="n">{i + 1}</span>
              <button className="quiet x" title="Remove" onClick={() => p.removeRef(r.asset_id)}>✕</button>
              {i > 0 && <button className="quiet mv" title="Move left" onClick={() => p.moveRef(i, i - 1)}>◀</button>}
            </> : <span className="empty">{i + 1}</span>}
          </div>
        ))}
      </div>
      {p.refs.length > 0 && <><label>downscale</label><div><select value={p.refMaxPx} onChange={(e) => p.set({ refMaxPx: Number(e.target.value) })} title="a 1024² reference ≈ 4 096 tokens"><option value={512}>≤ 512²</option><option value={768}>≤ 768²</option><option value={1024}>≤ 1024²</option></select> <CommandButton id="edit.ai.clearRefs" text /></div></>}
      <Help className="full" text={`Reference images go in after the region itself — a character's face, a material the fill should match. ${caps?.models[model]?.label ?? 'The model'} takes up to ${max}; drop Catalogue tiles on the slots, right-click a slot to move or remove one. The preview says how many go in.`} />
    </>
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
    return <Slider key={k} label={label} value={p[k] ?? 0} min={min} max={max} step={step} unit={unit.trim() || undefined} onChange={(v) => ed().setRefineEdge({ [k]: v })} />
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
      <label /><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}><CommandButton id="edit.sel.refine" text /><button className="quiet" onClick={() => ed().setRefineEdge(null)} title="the server's defaults">Reset</button></div>
    </>
  )
}

// AI panel settings live in aiPanelStore.ts (shared with the A-tool options)

/** AI Select (10 §4, M5 slice 2): shared by the AI tab's Select operation and the A tool's options. */
/** D90 (02 §9): the AI tab's inputs, reactive — the same AiCtx the `edit.ai.*` commands build from getState (editCommands.ts aiCtx), so a
 * button and its command agree on the reason and the recipe (aiRecipes.ts). */
function useAiCtx(): AiCtx & { p: ReturnType<typeof useAiPanel.getState>; doc: DocumentStack | null } {
  const p = useAiPanel()
  const caps = useSession((s) => s.capabilities)
  const models = useSession((s) => s.models)
  const doc = useEditor((s) => s.doc)
  const hasSel = useEditor((s) => !!s.selection)
  const activeId = useEditor((s) => s.activeId)
  const aiPrompt = useEditor((s) => s.aiPrompt)
  return { p, caps, health: (id) => models.find((m) => m.id === id)?.health ?? 'missing', doc, hasSel, activeId, activeKind: findNode(doc, activeId)?.kind ?? null, aiPrompt, refineParams: () => ({ ...ed().refineParams() }) }
}
function SelectControls({ compact = false }: { compact?: boolean }) {
  const c = useAiCtx()
  const { p, caps, aiPrompt } = c
  const setP = p.set
  // D65: the AI Select tools come from /capabilities.tools (recipes.segment); the subject matte is the default, a prompted tool
  // (text / points / box — SAM 3, full only under C3 / D26) appears where this build offers one
  const tools = byOrder(caps?.tools).filter(([, t]) => (t.recipes.segment ?? []).length > 0)
  const { subjectId, promptId, toolId, toolModes, sam, reason } = selectPlan(c)
  const promptModes = (['text', 'points', 'box'] as const).filter((m) => toolModes.includes(m))
  const pos = aiPrompt.points.filter((q) => q.label === 1).length, neg = aiPrompt.points.length - pos
  const run = () => runCommand('edit.ai.select')
  // D63: the find field leads — typing selects by prompt (SAM 3 text), clearing it in text mode goes back to the main subject
  const find = (text: string) => setP(text.trim() && promptId ? { selText: text, selModel: promptId, selMode: 'text' } : p.selMode === 'text' ? { selText: text, selModel: subjectId, selMode: 'subject' } : { selText: text })
  return (
    <div className="tool-opts">
      {promptId && <><label>find</label><input type="text" className="sel-find" value={p.selText} placeholder='what to select, e.g. "the crates" · empty: the main subject'
        title="SAM 3 finds what you describe · Enter runs Select" onChange={(e) => find(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && !reason) { e.preventDefault(); run() } }} /></>}
      <label>model</label><div className="segmented">{tools.map(([id, t]) => { const modes = t.recipes.segment ?? []
        return <button key={id} className={toolId === id ? 'active' : ''} onClick={() => setP({ selModel: id, selMode: (modes.includes('subject') ? 'subject' : modes.includes(p.selMode) ? p.selMode : modes[0]) as AiPanelState['selMode'] })}>{t.label}</button> })}</div>
      {sam && <>
        <label>prompt</label><div className="segmented">{promptModes.map((m) => <button key={m} className={p.selMode === m ? 'active' : ''} onClick={() => setP({ selMode: m })}>{m}</button>)}</div>
        {p.selMode === 'points' && <><label>points</label><div>{pos} include · {neg} exclude <button className="quiet" disabled={!aiPrompt.points.length} onClick={() => ed().setAiPrompt({ points: [] })}>Clear</button></div></>}
        {p.selMode === 'box' && <><label>box</label><div>{aiPrompt.box ? `${aiPrompt.box[2] - aiPrompt.box[0]}×${aiPrompt.box[3] - aiPrompt.box[1]} at ${aiPrompt.box[0]},${aiPrompt.box[1]}` : 'none'} <button className="quiet" disabled={!aiPrompt.box} onClick={() => ed().setAiPrompt({ box: null })}>clear</button></div></>}
        <Slider label="threshold" value={p.selThreshold} min={0.05} max={0.95} step={0.05} onChange={(v) => setP({ selThreshold: v })} />
      </>}
      <label>combine</label><div className="segmented">{(['replace', 'add', 'subtract', 'intersect'] as const).map((m) => <button key={m} className={p.selOp === m ? 'active' : ''} onClick={() => setP({ selOp: m })}>{m}</button>)}</div>
      <Slider label="expand" value={p.selExpand} min={-64} max={64} step={1} unit="px" onChange={(v) => setP({ selExpand: v })} />
      <Slider label="feather" value={p.selFeather} min={0} max={64} step={1} unit="px" onChange={(v) => setP({ selFeather: v })} />
      <label /><label className="chk" title="soft, image-aware edges after the mask joins the selection — the Selection panel's Refine edge settings"><input type="checkbox" checked={p.selRefine} onChange={(e) => setP({ selRefine: e.target.checked })} /> refine edge</label>
      <label /><div style={{ display: 'flex', gap: 6 }}><AiRunButton id="edit.ai.select" reason={reason} className="primary" title="AI Select">Select ▶</AiRunButton>{!compact && <AiRunButton id="edit.ai.stage" reason={reason} title="add to the queue and run it later — Run now in the Dock">Queue</AiRunButton>}</div>
      {reason && <span className="hint full">{reason}</span>}
      <Help className="full" text={sam ? 'A tool on the canvas: click adds an include point, Alt-click an exclude point, drag draws a box · the mask joins the selection as chosen (SAM 3 ≈ 3 s warm)' : 'BiRefNet matte of the main subject (≈ 2 s warm) · for a background swap: Select, then invert the selection (Selection panel) and Inpaint'} />
    </div>
  )
}

const fmtSeconds = (s: number) => (s >= 90 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`)
/** D64: the plan of the AI panel's recipe from /recipes/preview — ETA and VRAM fit, weights not fetched, contract problems; debounced. */
function useDocPreview(recipe: DocumentRecipe | null): DocumentPreview | null {
  const key = recipe ? JSON.stringify({ ...recipe, seeds: (recipe.seeds ?? [0]).map(() => 0) }) : ''   // fresh random seeds must not re-plan; the count stays
  const [pv, setPv] = useState<{ key: string; value: DocumentPreview } | null>(null)
  useEffect(() => {
    if (!key) return
    let live = true
    const t = setTimeout(() => {
      void unwrap(http.POST('/recipes/preview', { body: { recipe: JSON.parse(key) } })).then((r) => { if (live && isDocumentPreview(r)) setPv({ key, value: r }) }, () => {})
    }, 300)
    return () => { live = false; clearTimeout(t) }
  }, [key])
  return pv && pv.key === key ? pv.value : null
}

function AiTab() {
  const c = useAiCtx()
  const { p, doc, caps } = c
  const setP = p.set
  const jobs = useSession((s) => s.jobs)
  const running = useMemo(() => Object.values(jobs).filter((j) => (j.recipe as { document_id?: string }).document_id === doc?.id && ['running', 'queued', 'staged'].includes(j.status)), [jobs, doc?.id])
  const health = c.health
  // C3 (D26) / D65: every model comes from /capabilities — the defaults are the variant's (open: Klein 4B, no hero, no SAM 3); aiRecipes.ts
  const capModels = caps?.models
  const { contentAware, heroId, mode, i2iIds, upIds, refineModel, tiledIds, tiledModel, upscaleModel, kleinId, isHero, outpaintId } = aiModels(c)
  const hero = aiModels(c).heroFor(p.op)
  /** A refine model's name in the lists: the label's first part, + Turbo where the spec has one, the base models' CFG note. */
  const i2iName = (id: string, tiled = false) => { const m = capModels?.[id]; if (!m) return id
    const name = m.label.split(' · ')[0] + (m.turbo ? ' + Turbo' : '')
    return tiled ? name + (m.hint ? ` (${m.hint.split(',')[0]})` : '') : name + (!m.distilled && !m.cfg_fixed ? ' (CFG, negatives)' : '') }
  const fam = (id: string) => { const f = capModels?.[id]?.family ?? ''; return f.charAt(0).toUpperCase() + f.slice(1) }
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
  const reason = p.op === 'select' ? (doc ? null : 'no document') : aiReason(c, p.op)      // Select shows its own reason (SelectControls)
  /** D64: the recipe the preview plans — the one the run command sends (aiRecipes.ts; its random seeds don't re-plan). */
  const preview = useDocPreview(p.op === 'select' || !doc ? null : aiRecipe(c, p.op))
  const ops = Object.entries(AI_OP_LABEL) as [AiOp, string][]
  /** The tuning controls of an operation: a collapsible Advanced section (closed until opened; it remembers), its own label grid. */
  const advanced = (id: string, body: ReactNode) => <div className="full ai-advanced"><Section id={`ai-advanced-${id}`} title="Advanced" defaultOpen={false}><div className="tool-opts">{body}</div></Section></div>
  return (
    <div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
        <div className="segmented" style={{ flexWrap: 'wrap' }}>{ops.map(([k, l]) => <button key={k} className={p.op === k ? 'active' : ''} onClick={() => { if (k !== p.op) setP({ op: k, candidates: opCandidates(c, k) }) }}>{l}</button>)}</div>   {/* D151: six operations wrap in the narrow panel */}
        <CommandButton id="edit.ai.angle" text label="Angle ▸" />{/* D95 (UX0 #8): the New angle sheet, one implementation */}
      </div>
      {p.op === 'select' && <SelectControls />}
      {p.op !== 'select' && <div className="tool-opts">
        {p.op === 'inpaint' && <>
          <label>mode</label><select value={mode} onChange={(e) => { const m = e.target.value as AiPanelState['mode']; setP({ mode: m, candidates: m === 'fill_hero' ? 2 : 4 }) }}>
            <option value="fill" title="Klein + LanPaint (the default)">Fill</option><option value="fill_match" title="Klein ICM: continues the surrounding texture">Fill-Match · continues texture</option>{heroId && <option value="fill_hero" title={`${capModels?.[heroId]?.label.split(' · ')[0] ?? heroId} + LanPaint: slow, best detail`}>Fill Hero · slow, best detail</option>}<option value="remove" title="paints what is behind, from a background-only prompt">Remove</option>{contentAware && <option value="quick_remove" title="content-aware fill on the CPU: seconds, no GPU">Quick remove · CPU</option>}
          </select>
          {mode === 'remove' && contentAware && <><label /><label className="chk" title="the hole is content-aware filled (PhotoCraft, CPU) and the model starts from that instead of a grey hole — try it where Remove leaves an object's ghost"><input type="checkbox" checked={p.prefill} onChange={(e) => setP({ prefill: e.target.checked })} /> pre-fill the hole (content-aware)</label></>}
          {mode === 'quick_remove' && <Help className="full" text={"PhotoCraft's content-aware fill on the CPU — no model, no GPU, a few seconds; best on small or textured areas, it smears large ones."} />}
          {mode !== 'quick_remove' && mode !== 'remove' && <RefSlotsAi model={mode === 'fill_hero' && heroId ? heroId : kleinId} />}
          {mode !== 'quick_remove' && <><label>prompt</label><textarea value={p.prompt} rows={3} placeholder={p.mode === 'remove' ? 'what is behind: "wet cobblestones and a brick wall"' : 'what to paint there'} onChange={(e) => setP({ prompt: e.target.value })} />
</>}
          {advanced('inpaint', <>
          {mode !== 'quick_remove' && <EncoderPick model={kleinId} />}
          {p.mode !== 'fill_match' && p.mode !== 'remove' && p.mode !== 'quick_remove' && <><label>LanPaint</label><div className="segmented"><button className={p.promptMode === 'image_first' ? 'active' : ''} onClick={() => setP({ promptMode: 'image_first' })}>image first</button><button className={p.promptMode === 'prompt_first' ? 'active' : ''} onClick={() => setP({ promptMode: 'prompt_first' })}>prompt first</button></div></>}
          <Slider label="margin" value={p.margin} min={0} max={100} step={1} unit="%" onChange={(v) => setP({ margin: v })} />
          <Slider label="min size" value={p.minSize} min={512} max={2048} step={64} unit="px" onChange={(v) => setP({ minSize: v })} />
          <Slider label="feather" value={p.feather} min={0} max={64} step={1} unit="px" onChange={(v) => setP({ feather: v })} />
          <Slider label="expand" value={p.expand} min={0} max={64} step={1} unit="px" onChange={(v) => setP({ expand: v })} />
          <label>blend</label><div className="segmented"><button className={p.blend === 'feather' ? 'active' : ''} title="the result fades in over the feather" onClick={() => setP({ blend: 'feather' })}>feather</button><button className={p.blend === 'seamless' ? 'active' : ''} title="Poisson-blend the result into the plate: it keeps its texture but takes the plate's colour and light at the seam — best for removals and continuing a texture; it also pulls an intended colour change towards the old colour near the edge" onClick={() => setP({ blend: 'seamless' })}>seamless</button></div>
          <Help className="full" text={"Results land with a layer mask: paint it (click the mask thumbnail) to adjust the seam."} />
          </>)}
        </>}
        {p.op === 'outpaint' && <>
          <label>grow</label><div className="grow-grid">{(['left', 'top', 'right', 'bottom'] as const).map((k) => <span key={k} className="grow-cell"><small>{k}</small><ValueField bare label={`grow ${k}`} value={p.pad[k]} min={0} max={2048} step={16} unit="px" onChange={(v) => setP({ pad: { ...p.pad, [k]: v } })} /></span>)}</div>
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder="what continues beyond the edge" onChange={(e) => setP({ prompt: e.target.value })} />
          <RefSlotsAi model={outpaintId} />
          <label>model</label><div className="segmented"><button className={!hero ? 'active' : ''} onClick={() => setP({ outpaintHero: false, candidates: 4 })}>{fam(kleinId) || 'default'} + LanPaint</button>{heroId && <button className={hero ? 'active' : ''} onClick={() => setP({ outpaintHero: true, candidates: 2 })}>{capModels?.[heroId]?.short ?? heroId} (hero)</button>}</div>
          {advanced('outpaint', <>
          <EncoderPick model={outpaintId} />
          <Slider label="feather" value={p.feather} min={0} max={64} step={1} unit="px" onChange={(v) => setP({ feather: v })} />
          </>)}
        </>}
        {p.op === 'refine' && <>
          <label>model</label><select value={refineModel} onChange={(e) => setP({ refineModel: e.target.value, candidates: isHero(e.target.value) ? 2 : 4 })}>{i2iIds.map((id) => <option key={id} value={id}>{i2iName(id)}</option>)}</select>
          <label>on</label><div className="segmented">{(['visible', 'active', 'selection'] as const).map((s) => <button key={s} className={p.refineSource === s ? 'active' : ''} onClick={() => setP({ refineSource: s })}>{s}</button>)}</div>
          <Slider label="strength" value={p.strength} min={0.1} max={0.8} step={0.01} onChange={(v) => setP({ strength: v })} />
          <label>prompt</label><textarea value={p.prompt} rows={3} placeholder="defaults to the source asset's prompt when empty" onChange={(e) => setP({ prompt: e.target.value })} />
          <RefSlotsAi model={refineModel} />
          {advanced('refine', <>
          <EncoderPick model={refineModel} />
          {p.refineSource === 'selection' && <Slider label="feather" value={p.feather} min={0} max={64} step={1} unit="px" onChange={(v) => setP({ feather: v })} />}
          <label /><label className="chk" title="undo the refine's colour drift: the result's colour statistics are mapped onto the original's — around the selection, or over the whole image / layer"><input type="checkbox" checked={p.matchColour} onChange={(e) => setP({ matchColour: e.target.checked })} /> match colour to the original</label>
          </>)}
        </>}
        {p.op === 'instruct' && <>
          <label>on</label><div className="segmented">{(['visible', 'active'] as const).map((s) => <button key={s} className={p.instructSource === s ? 'active' : ''} onClick={() => setP({ instructSource: s })}>{s}</button>)}</div>
          <label>change</label><textarea value={p.prompt} rows={3} placeholder={'what to change: "make it dusk, the lamps lit", "snow on the street", "a lantern in her hand"'} onChange={(e) => setP({ prompt: e.target.value })} />
          <Help className="full" text={`${caps?.instruct?.models?.[caps.instruct.default ?? '']?.label ?? 'The edit model'} redraws the whole picture (or the active layer) from your instruction at about 1 megapixel and lands it as a new layer, ${caps?.instruct?.models?.[caps.instruct.default ?? '']?.seconds ?? 32} s a candidate. It follows meaning a mask cannot say — the time of day, the weather, a thing in a hand, a costume — and keeps the composition; for a precise area, Inpaint with a selection does better, and it does not remove things (Remove does).`} />
        </>}
        {p.op === 'upscale' && <>
          <label>model</label><select value={upscaleModel} onChange={(e) => setP({ upscaleModel: e.target.value })}>{upIds.map((id) => <option key={id} value={id}>{caps?.tools[id]?.label ?? id} {health(id) === 'missing' ? '(not fetched)' : ''}</option>)}</select>
          <label>on</label><div className="segmented">{(['visible', 'active'] as const).map((s) => <button key={s} className={p.upscaleSource === s ? 'active' : ''} onClick={() => setP({ upscaleSource: s })}>{s}</button>)}</div>
          <label>result</label><label className="chk"><input type="checkbox" checked={p.asLayer} onChange={(e) => setP({ asLayer: e.target.checked })} /> also add a 1× detail layer (the full-size image goes to the Catalogue)</label>
          <label>detail</label><label className="chk" title="re-samples every tile of the upscale at low strength (a tiled refine)"><input type="checkbox" checked={p.refineTiled} onChange={(e) => setP({ refineTiled: e.target.checked })} /> Upscale (detailed) — re-samples every tile at low strength</label>
          {p.refineTiled && <>
            <label>model</label><select value={tiledModel} onChange={(e) => setP({ tiledModel: e.target.value })}>{tiledIds.map((id) => <option key={id} value={id}>{i2iName(id, true)}</option>)}</select>
            <EncoderPick model={tiledModel} />
            <Slider label="strength" value={p.tiledStrength} min={0.05} max={0.6} step={0.01} onChange={(v) => setP({ tiledStrength: v })} />
            <Slider label="tile" value={p.tile} min={512} max={2048} step={64} unit="px" onChange={(v) => setP({ tile: v })} />
            <Slider label="overlap" value={p.overlap} min={0} max={256} step={16} unit="px" onChange={(v) => setP({ overlap: v })} />
            <label>prompt</label><textarea value={p.prompt} rows={2} placeholder="what the image shows (helps the refine keep its subject)" onChange={(e) => setP({ prompt: e.target.value })} />
          </>}
        </>}
        {p.op !== 'upscale' && <>
          <Slider label="count" value={p.candidates} min={1} max={4} step={1} onChange={(v) => setP({ candidates: v })} />
          <label>seed</label><div><div className="segmented">{(['random', 'fixed'] as const).map((m) => <button key={m} className={p.seedMode === m ? 'active' : ''} onClick={() => setP({ seedMode: m })}>{m}</button>)}</div>{p.seedMode === 'fixed' && <input type="number" value={p.seed} onChange={(e) => setP({ seed: Number(e.target.value) })} style={{ width: 120, marginLeft: 6 }} />}</div>
        </>}
      </div>}
      {p.op !== 'select' && <div style={{ display: 'flex', gap: 6, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <AiRunButton id={`edit.ai.${p.op}`} reason={reason} className="primary">AI ▶ {AI_OP_LABEL[p.op]}{p.op !== 'upscale' ? ` ×${p.candidates}` : ''}</AiRunButton>
        <AiRunButton id="edit.ai.stage" reason={reason} title="add to the queue and run it later — Run now in the Dock">Queue</AiRunButton>
        {running.length > 0 && <span className="kind">{running.filter((j) => j.status === 'running').length ? `running · ${Math.round((running.find((j) => j.status === 'running')?.progress ?? 0) * 100)} %` : `${running.length} queued`}</span>}
      </div>}
      {reason && <p className="hint" style={{ marginTop: 6 }}>{reason}</p>}
      {p.op !== 'select' && typeof preview?.params?.refs === 'number' && ((preview.params.refs as number) > 0 || (preview.params.refs_dropped as number) > 0) && (
        <p className={`hint${(preview.params.refs_dropped as number) > 0 ? ' warn' : ''}`} style={{ marginTop: 6 }}>references {preview.params.refs as number} of {preview.params.max_refs as number}{(preview.params.refs_dropped as number) > 0 ? ` — ${preview.params.refs_dropped as number} over the limit left out` : ''}</p>)}   {/* D152 */}
      {engineSize && <p className="hint" style={{ marginTop: 6 }}>engine image ≈ {engineSize.w}×{engineSize.h} ({engineSize.scale > 1.01 ? `upscaled ×${engineSize.scale.toFixed(2)}` : engineSize.scale < 0.99 ? `downscaled ×${engineSize.scale.toFixed(2)} to stay within 1 MP` : '1:1'})</p>}
      {p.op !== 'select' && <p className="hint" style={{ marginTop: 8 }}><Help text={"Runs on the saved document; results come back as layers in an \"AI\" group with the recipe attached."} />{preview?.estimate?.seconds != null ? ` ≈ ${fmtSeconds(preview.estimate.seconds)} per ${p.op === 'upscale' ? 'run' : 'candidate'} — ${preview.estimate.source}.` : ''}</p>}
      {p.op !== 'select' && preview && preview.missing.length > 0 && <p className="hint warn" style={{ marginTop: 6 }}>weights not fetched: {preview.missing.map((m) => m.model_id).join(', ')} — fetch them in Models</p>}
      {p.op !== 'select' && preview?.problems && preview.problems.length > 0 && <p className="hint warn" style={{ marginTop: 6 }} title={preview.problems.join('\n')}>the engine would refuse this recipe: {preview.problems[0]}{preview.problems.length > 1 ? ` (+${preview.problems.length - 1} more)` : ''}</p>}
    </div>
  )
}

function CandidateStrip() {
  const cands = useEditor((s) => s.candidates)
  const preview = useEditor((s) => s.candPreview)
  useKeymap((k) => k.version)                                          // D72: the tooltips follow a remap
  const revision = useEditor((s) => s.revision)
  const doc = useEditor((s) => s.doc)
  const thumbs = useMemo(() => { const st = ed(); const m = new Map<string, string>(); cands?.ids.forEach((id) => { const lp = st.pixels.get(id); if (lp) m.set(id, lp.thumbnail(96)) }); return m }, [cands, revision]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!cands || !doc) return null
  const g = findNode(doc, cands.group)
  return (
    <div className="cand-strip">
      <span className="muted">{g?.name ?? 'candidates'} — use one (1–4, Enter uses the one shown) or use all:</span>
      {cands.ids.map((id, i) => { const n = findNode(doc, id), cid = `edit.cand.${i + 1}`, c = command(cid), on = preview ? preview === id : !!n?.visible; if (c) markUsed(cid); return (
        // D90 (B18): hovering previews through `candPreview` (view only: no history, nothing dirty); a click runs the command (1–4, remappable)
        <button key={id} className={`cand${on ? ' on' : ''}`} title={`${c ? titleFor(c) : `Use candidate ${i + 1}`} · seed ${(n?.recipe as { seed?: number } | undefined)?.seed ?? '?'}`}
          onMouseEnter={() => ed().previewCandidate(id)} onMouseLeave={() => ed().previewCandidate(null)} onClick={() => { if (c) runCommand(cid); else ed().pickCandidate(id) }}>
          {thumbs.get(id) ? <img src={thumbs.get(id)} alt="" /> : <span className="muted">…</span>}<b>{i + 1}</b>
        </button>
      ) })}
      <CommandButton id="edit.cand.keep" text label="Use shown" />
      <button className="quiet" title="Use all: keep every candidate as a layer (the others hidden)" onClick={() => ed().pickCandidate(null)}>Use all</button>
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
        <label>new</label><input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <ValueField label="width" value={form.w} min={64} max={8192} step={16} unit="px" onChange={(v) => setForm({ ...form, w: v })} />
        <ValueField label="height" value={form.h} min={64} max={8192} step={16} unit="px" onChange={(v) => setForm({ ...form, h: v })} />
        <label /><button onClick={() => void ed().newDocument(form.w, form.h, form.name)}>New document</button>
      </div>
      <h4 className="sect">DOCUMENTS IN THIS PROJECT</h4>
      <div className="doc-list">
        {items.map((d) => (
          <div key={d.id} className={`doc-row${d.id === docId ? ' active' : ''}`} onClick={() => { if (d.id !== docId) void ed().openDocument(d.id) }}>
            <img src={api.fileUrl(`/documents/${d.id}/thumbnail`)} alt="" loading="lazy" onError={(e) => { (e.target as HTMLImageElement).style.visibility = 'hidden' }} />
            <div className="t"><b>{d.name}</b><span className="kind">{d.w}×{d.h} · {d.layers} layer{d.layers === 1 ? '' : 's'} · {d.saved_at ? new Date(d.saved_at).toLocaleString() : 'unsaved'}{d.open ? ' · open' : ''}</span></div>
            <button className="quiet icon-btn" title="Delete the document (its .ora file)" aria-label="delete document" onClick={(e) => { e.stopPropagation(); void askConfirm({ title: 'Delete document?', text: `"${d.name}" and its .ora file are removed from the project. This cannot be undone.`, okLabel: 'Delete document', danger: true }).then((ok) => { if (ok) void ed().deleteDocument(d.id).then(refresh) }) }}><Trash2 size={14} /></button>
          </div>
        ))}
        {!items.length && <span className="muted">No documents yet. In the Catalogue, select an image and choose Open in Edit (E).</span>}
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
  return <><label>encoder</label><select value={value} title="Text encoder weights: the Q4_K_M GGUF stays resident beside the 9B transformer; the fp8 encoder makes it stream on a cold engine" onChange={(e) => setP({ teId: e.target.value || null })}>
    {opts.map((o) => <option key={o.id} value={o.default ? '' : o.id}>{o.default ? `preset · ${o.label}` : o.label}{o.health === 'missing' ? ' (not fetched)' : ''}</option>)}
  </select></>
}

// D95 (IM1, UX0): Edit's five rail tabs are one scrolling column, like Image · Make's; the rail jumps to a section and follows the scroll
const EDIT_SECTIONS = ['tools', 'brushes', 'selection', 'ai', 'documents'] as const
const EDIT_SECTION: Record<(typeof EDIT_SECTIONS)[number], [string, () => React.ReactElement]> = {
  tools: ['Tool options', () => <ToolOptions />], brushes: ['Brushes', () => <BrushesTab />], selection: ['Selection', () => <SelectionTab />],
  ai: ['AI', () => <AiTab />], documents: ['Documents', () => <DocumentsTab />],
}

function EditColumn({ tab }: { tab: string }) {
  const host = useRef<HTMLDivElement>(null)
  useColumnSync(host, 'edit', EDIT_SECTIONS, 'edit-sec-', tab)
  return (
    <div ref={host} className="col-column edit-column">
      {EDIT_SECTIONS.map((id) => (
        <section key={id} id={`edit-sec-${id}`} className="col-sec">
          <h4 className="col-sec-head"><span>{EDIT_SECTION[id][0]}</span></h4>
          {EDIT_SECTION[id][1]()}
        </section>
      ))}
    </div>
  )
}

function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  if (!project?.open) return <span className="muted">Open or create a project.</span>
  return <EditColumn tab={tab} />
}

function PrimaryAction() {
  const doc = useEditor((s) => s.doc)
  const dirty = useEditor((s) => s.docDirty)
  const saving = useEditor((s) => s.saving)
  const forShot = useMakeFor((f) => !!f.generate)                       // D95 (UX0 #23): only while Image makes for a Shot (the For chip)
  if (!doc) return <div><span className="muted">no document open</span></div>
  markUsed('edit.save'); markUsed('edit.saveForShot')
  return (
    <div>
      <button className="primary" disabled={saving} onClick={() => runCommand('edit.save')} title="Save (Ctrl+S)">{saving ? 'Saving…' : dirty ? 'Save •' : 'Save'}</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        {forShot && <CommandButton id="edit.saveForShot" text />}<CommandButton id="edit.exportPng" text /><CommandButton id="edit.exportPsd" text /><CommandButton id="edit.close" text />
      </div>
    </div>
  )
}

/** F9 (D55): a Layers-panel gesture's modifiers — the keys held, or the strip's latches (mouse-only). */
function lm(e: { shiftKey: boolean; ctrlKey: boolean; metaKey: boolean; altKey: boolean }): { shift: boolean; ctrl: boolean; alt: boolean } {
  const l = useEditor.getState().latched
  return { shift: e.shiftKey || l.shift, ctrl: e.ctrlKey || e.metaKey || l.ctrl, alt: e.altKey || l.alt }
}

// ------------------------------------------------------------------ Strip / Stage
/** D58: the free transform's options in the strip (PhotoCraft transform_fields): the reference point, W / H (linked), the angle, the
 * interpolation and the mode, with ✓ / ⊘. */
function TransformBar() {
  const t = useEditor((s) => s.transform)
  const docW = useEditor((s) => s.doc?.w ?? 1000), docH = useEditor((s) => s.doc?.h ?? 1000)
  const [link, setLink] = useState(true)
  if (!t) return null
  const ro = readout(t)
  const set = ed().setTransform
  const move = (dx: number, dy: number) => set({ quad: t.quad.map((c) => ({ x: c.x + dx, y: c.y + dy })) as typeof t.quad, pivot: { x: t.pivot.x + dx, y: t.pivot.y + dy } })
  const scale = (kx: number, ky: number) => { if (Number.isFinite(kx) && Number.isFinite(ky) && kx > 0 && ky > 0) set({ quad: scaleAboutPivot(t, kx, ky) }) }
  return (
    <span className="xform-bar">
      <span style={{ color: 'var(--accent)' }}>transform</span>
      <span className="vpair"><ValueField label="X" value={t.pivot.x} min={-3 * docW} max={4 * docW} unit="px" title="the reference point (Alt-click the canvas to place it)" onChange={(v) => move(v - t.pivot.x, 0)} /></span>
      <span className="vpair"><ValueField label="Y" value={t.pivot.y} min={-3 * docH} max={4 * docH} unit="px" title="the reference point (Alt-click the canvas to place it)" onChange={(v) => move(0, v - t.pivot.y)} /></span>
      <span className="vpair"><ValueField label="W" value={ro.sx * 100} min={0.1} max={1000} unit="%" onChange={(v) => { const k = v / 100 / ro.sx; scale(k, link ? k : 1) }} />
      <button type="button" className={`quiet latch${link ? ' active' : ''}`} aria-pressed={link} title="keep W and H in proportion" onClick={() => setLink(!link)}>⛓</button></span>
      <span className="vpair"><ValueField label="H" value={ro.sy * 100} min={0.1} max={1000} unit="%" onChange={(v) => { const k = v / 100 / ro.sy; scale(link ? k : 1, k) }} /></span>
      <span className="vpair"><ValueField label="angle" value={Math.round(ro.angle * 100) / 100} min={-180} max={180} unit="°" onChange={(v) => set({ quad: rotateAboutPivot(t, v - ro.angle) })} /></span>
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
  const magneticOpen = useEditor((s) => !!s.lassoPoly && s.tool === 'lasso' && s.lassoKind === 'magnetic')   // D59: the border syncs lassoPoly
  const held = useRef<{ t: number; was: boolean } | null>(null)
  useKeymap((k) => k.version)
  const beforeCmd = command('edit.view.before')
  if (beforeCmd) markUsed(beforeCmd.id)
  // D90 (01 §11.3): the before button is the command — a click toggles; pressed and held (> 300 ms) it peeks until released
  const beforeDown = () => { held.current = { t: Date.now(), was: ed().before }; ed().setView({ before: true }) }
  const beforeUp = () => { const h = held.current; held.current = null; if (!h) return; if (Date.now() - h.t > 300) ed().setView({ before: false }); else { ed().setView({ before: h.was }); runCommand('edit.view.before') } }
  const cropping = useEditor((s) => s.tool === 'crop' && !!s.selection && !s.transform)   // D90 (B9)
  const latched = useEditor((s) => s.latched)
  const [zt, setZt] = useState<string | null>(null)
  const apply = () => { if (zt !== null) { const v = parseFloat(zt); if (v > 0) ed().zoomTo(v / 100) } setZt(null) }
  return (
    <>
      <span>{doc ? `${doc.name} · ${doc.w}×${doc.h}${dirty ? ' •' : ''}` : 'Edit'}</span>
      {transforming && <TransformBar />}
      {polyOpen && <><span style={{ color: 'var(--accent)' }}>{magneticOpen ? 'magnetic lasso' : 'polygon'}</span><CommandRow ids={magneticOpen ? ['edit.sel.polyClose', 'edit.sel.magBack', 'edit.sel.polyCancel'] : ['edit.sel.polyClose', 'edit.sel.polyCancel']} /></>}
      {cropping && !polyOpen && <><span style={{ color: 'var(--accent)' }}>crop</span><CommandRow ids={['edit.crop.apply', 'edit.crop.cancel']} /></>}
      <span className="latches" title="Latched modifiers: each stays on for every canvas gesture until clicked again (no keyboard needed)">
        {(['shift', 'ctrl', 'alt'] as const).map((k) => <LatchButton key={k} on={latched[k]} label={k === 'shift' ? 'Shift' : k === 'ctrl' ? 'Ctrl' : 'Alt'}
          title={`Latch ${k === 'shift' ? 'Shift' : k === 'ctrl' ? 'Ctrl' : 'Alt'}: canvas gestures act as if it were held, until clicked again`} onToggle={() => { markUsed(`edit.latch.${k}`); runCommand(`edit.latch.${k}`) }} />)}
      </span>
      <CommandRow ids={['edit.undo', 'edit.redo', 'gap', 'edit.view.zoomOut']} />
      <input className="edit-strip-zoom" value={zt ?? String(Math.round(zoom * 100))} onChange={(e) => setZt(e.target.value)} onBlur={apply} onKeyDown={(e) => { if (e.key === 'Enter') apply() }} disabled={!doc} /><span style={{ marginLeft: -4 }}>%</span>
      <CommandRow ids={['edit.view.zoomIn', 'edit.view.fit']} />
      <CommandButton id="edit.view.100" text />
      <label className="chk" title="Pixel grid (shown from 800 %)"><input type="checkbox" checked={pixelGrid} onChange={() => { markUsed('edit.view.grid'); runCommand('edit.view.grid') }} /> pixel grid</label>
      <label className="chk" title="Mask overlay (Alt+\)"><input type="checkbox" checked={overlay} onChange={() => { markUsed('edit.view.overlay'); runCommand('edit.view.overlay') }} /> mask overlay</label>
      <button className={`quiet${before ? ' active' : ''}`} aria-pressed={before} onPointerDown={beforeDown} onPointerUp={beforeUp} onPointerLeave={() => { if (held.current) { held.current = null; ed().setView({ before: false }) } }}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); runCommand('edit.view.before') } }}
        disabled={!doc} title={`${beforeCmd ? titleFor(beforeCmd) : 'Before'}: a click toggles; press and hold (or hold the key) to peek`}>before</button>
      <button className={`quiet${quickMask ? ' active' : ''}`} onClick={() => { markUsed('edit.sel.quickMask'); runCommand('edit.sel.quickMask') }} disabled={!doc} title="Quick mask (Q)">Quick mask</button>
      <span className="spacer" />
      {cursor && <span className="mono">{cursor.x}, {cursor.y}</span>}
      {/* D90 (01 §11.6): the renderer badge is developer-facing — dev builds only; everyone has it in Info › Diagnostics */}
      {DEV_HOOKS && <RendererButton className="quiet badge-renderer" renderer={renderer} pref={rendererPref} onCycle={ed().setRendererPref} />}
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
        <p><button onClick={() => void ed().newDocument(1920, 1080)}>New 1920×1080 document</button> <button onClick={() => navigate({ suite: 'catalogue' })}>Open the Catalogue</button></p>
        <RecentDocuments />
      </>}
      {error && <p style={{ color: 'var(--error)' }}>{error}</p>}
    </div></EmptyDrop>
  )
  return <><EditorCanvas key={epoch} /><TextEditOverlay /><CandidateStrip /></>
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
    if (ghost) { ghost.style.left = `${lx + 12}px`; ghost.style.top = `${ly + 8}px`; ghost.classList.toggle('copy', lm(ev).alt) }
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
    else if (target) s.moveNodesTo(ids, target.id, target.where, lm(ev).alt)
  }
  window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up)
}
/** Eye sweep: the press toggles that row's eye; dragging over more rows gives each the same state — one history step for the sweep. */
function startEyeSweep(e: React.PointerEvent<HTMLElement>, n: Node) {
  e.stopPropagation()
  if (e.button !== 0) return
  if (lm(e).alt) { ed().solo(n.id); return }
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
  // D71 (P11): Catalogue tiles dropped on the list become layers above the row they land on (on empty space: at the top)
  const { ref: dropRef, over: dropOver } = useDropTarget((p) => onlyAssets(p) && layerDrop(p).verdict.ok, (p, info) => {
    const row = (document.elementFromPoint(info.x, info.y) as HTMLElement | null)?.closest('.layer-row[data-id]') as HTMLElement | null
    ed().setActive(row?.dataset.id ?? null)                             // addLayer inserts above the active layer; each new one becomes active
    void (async () => { for (const id of layerDrop(p).take) await ed().addLayerFromAsset(id) })()
  }, (p) => layerDrop(p, 'at this row').verdict)
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
        onClick={(e) => { if (suppressRowClick) return; ed().selectLayer(n.id, lm(e).ctrl ? 'toggle' : lm(e).shift ? 'range' : 'replace') }}
        onDoubleClick={() => runCommand('edit.layer.rename')} onContextMenu={(e) => { if (!(multi && selectedIds.includes(n.id))) ed().selectLayer(n.id); showMenu(e, layerMenu()) }}>
        <button className={`eye${n.visible ? ' on' : ''}`} title="visibility · drag down the eyes to sweep · Alt-click: solo" onPointerDown={(e) => startEyeSweep(e, n)}
          onClick={(e) => { e.stopPropagation(); if (e.detail === 0) ed().updateNode(n.id, { visible: !n.visible }, n.visible ? 'hide layer' : 'show layer') }}>{n.visible ? <Eye size={14} /> : <EyeOff size={14} />}</button>
        <button className={`lock${n.locked ? ' on' : ''}`} title={multi && selectedIds.includes(n.id) ? `${n.locked ? 'unlock' : 'lock'} the ${ed().targetIds().length} selected layers` : 'lock'}
          onClick={(e) => { e.stopPropagation(); const ids = multi && selectedIds.includes(n.id) ? ed().targetIds() : [n.id]; ed().setPropsFor(ids, { locked: !n.locked }, n.locked ? 'unlock layers' : 'lock layers') }}>{n.locked ? <Lock size={12} /> : <LockOpen size={12} />}</button>
        {n.kind === 'raster' ? <img className={`thumb${n.mask && n.id === activeId && !editingMask ? ' target' : ''}`} src={thumbs.get(n.id)} alt="" title={n.mask ? 'click: paint the pixels · Ctrl-click: select layer transparency' : 'Ctrl-click: select layer transparency'} onClick={(e) => { e.stopPropagation(); if (lm(e).ctrl) ed().selectLayerAlpha(n.id); else { ed().setActive(n.id, false); ed().setView({ maskView: 'off' }) } }} /> : <span className="thumb kind-box">{n.kind === 'group' ? '▣' : n.kind === 'adjustment' ? '◐' : 'fx'}</span>}
        <span className="name">{n.name}<br /><span className="kind">{n.kind === 'raster' ? `${n.text ? 'T · ' : ''}${n.w}×${n.h}` : n.kind === 'group' ? `${n.children?.length ?? 0} · ${n.passthrough ? 'pass-through' : 'isolated'}` : typeLabel(n.type)}{n.clip ? ' · clip' : ''}{n.blend !== 'normal' ? ` · ${blendLabel(n.blend)}` : ''}{n.opacity < 1 ? ` · ${Math.round(n.opacity * 100)} %` : ''}</span></span>
        {n.mask && <button className={`mask-link${n.mask.linked ? ' on' : ''}`} title={n.mask.linked ? 'linked: the mask moves and transforms with the layer · click to unlink' : 'unlinked: the mask stays put · click to link'} onClick={(e) => { e.stopPropagation(); ed().toggleMaskLink(n.id) }}>{n.mask.linked ? <Link2 size={11} /> : <Unlink2 size={11} />}</button>}
        {n.mask
          ? <span className={`mask-wrap${n.mask.enabled ? '' : ' off'}`}><img className={`thumb mask-thumb${editingMask && n.id === activeId ? ' editing' : ''}`} src={thumbs.get('m:' + n.id)} alt="" title="mask · click: paint the mask · Alt-click: show it alone · Ctrl-click: load as selection · Shift-click: disable"
              onClick={(e) => {
                e.stopPropagation()
                if (lm(e).shift) { ed().updateNode(n.id, { mask: { ...n.mask!, enabled: !n.mask!.enabled } }, n.mask!.enabled ? 'disable mask' : 'enable mask'); return }
                ed().setActive(n.id, true)
                if (lm(e).ctrl) ed().loadSelectionFromMask()
                else if (lm(e).alt) ed().setView({ maskView: ed().maskView === 'gray' ? 'off' : 'gray' })
              }} /></span>
          : <span className="mask-box" title={hasSel ? 'add a mask revealing the selection · Alt-click: hiding it' : 'add a mask (reveal all) · Alt-click: hide all'} onClick={(e) => { e.stopPropagation(); ed().setActive(n.id); ed().addMask(n.id, hasSel ? (lm(e).alt ? 'hideSelection' : 'revealSelection') : (lm(e).alt ? 'hide' : 'reveal')) }}>+◐</span>}
      </div>
      {n.kind === 'group' && n.children && rows(n.children, depth + 1)}
    </div>
  ))
  return (
    <div>
      <div ref={dropRef} className={`layers${dropOver ? ' drop-over' : ''}`}>{rows(doc.layers, 0)}</div>
      {editingMask && active?.mask && <div className="mask-hint">Editing the <b>mask</b> of “{active.name}” with the mask colours: the brush paints the foreground (black hides, white shows), the eraser the background — X swaps them; G fills, Delete clears to the background. Alt-click the mask thumbnail to see it alone.{' '}
        {active.kind === 'raster' && <button className="quiet" onClick={() => { ed().setActive(active.id, false); ed().setView({ maskView: 'off' }) }}>Edit pixels instead</button>}</div>}
      {active && (
        <div className="tool-opts" style={{ marginTop: 10 }}>
          <label>blend</label><BlendSelect value={active.blend} options={(active.kind === 'group' ? ['pass-through', ...BLEND_MODES] : BLEND_MODES).map((m) => ({ value: m, label: blendLabel(m) }))}
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
        <CommandRow ids={['gap', 'edit.layer.duplicate', 'edit.layer.mergeDown', 'edit.layer.up', 'edit.layer.down', 'gap', active?.mask ? 'edit.mask.remove' : 'edit.mask.add', 'edit.layer.visibility', 'edit.layer.lock', 'gap', 'edit.layer.delete']} drops={{ 'edit.layer.duplicate': 'duplicate', 'edit.layer.delete': 'delete' }} labels={editingMask && active?.mask ? { 'edit.layer.delete': 'Delete layer mask' } : undefined} />
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
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <label className="chk" title="Shift-click the mask thumbnail"><input type="checkbox" checked={m.enabled} onChange={() => ed().updateNode(n.id, { mask: { ...m, enabled: !m.enabled } }, m.enabled ? 'disable mask' : 'enable mask')} /> on</label>
        <label className="chk" title="a linked mask moves and transforms with the layer (the chain left of the mask thumbnail)"><input type="checkbox" checked={m.linked} onChange={() => ed().toggleMaskLink(n.id)} /> linked</label>
      </div>
      <label /><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{(n.kind === 'raster' ? ['edit.mask.apply', 'edit.mask.load'] : ['edit.mask.load']).map((id) => <CommandButton key={id} id={id} text />)}</div>
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
      <div className="props-title"><b>{n.name}</b><span className="kind">{n.text ? 'Text layer' : KIND_LABEL[n.kind]}{n.type ? ` · ${typeLabel(n.type)}` : ''}</span></div>
      {n.kind === 'raster' && (
        <Section id="layer" title="Layer">
          <div className="tool-opts">
            <ValueField label="x" value={n.x ?? 0} min={-3 * doc.w} max={4 * doc.w} unit="px" onStart={start} onChange={(v) => ed().updateNode(n.id, { x: Math.round(v) })} onCommit={() => commit('move layer')} />
            <ValueField label="y" value={n.y ?? 0} min={-3 * doc.h} max={4 * doc.h} unit="px" onStart={start} onChange={(v) => ed().updateNode(n.id, { y: Math.round(v) })} onCommit={() => commit('move layer')} />
            <label>size</label><span>{n.w}×{n.h}</span>
            <label>lineage</label><span className="mono">{n.lineage_asset_id ?? '—'}</span>
          </div>
        </Section>
      )}
      {n.kind === 'raster' && n.text && <TextSection n={n} />}
      {n.kind === 'group' && (
        <Section id="group" title="Group">
          <div className="tool-opts">
            <label>layers</label><span>{n.children?.length ?? 0}</span>
            <label>mode</label><div className="segmented"><button className={n.passthrough ? 'active' : ''} onClick={() => ed().updateNode(n.id, { passthrough: true }, 'group mode')}>pass-through</button><button className={!n.passthrough ? 'active' : ''} onClick={() => ed().updateNode(n.id, { passthrough: false }, 'group mode')}>isolated</button></div>
          </div>
        </Section>
      )}
      {(n.kind === 'adjustment' || n.kind === 'filter') && (
        <Section id="adjustment" title={typeLabel(n.type)}>
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
            <label /><button type="button" className="quiet" style={{ justifySelf: 'start' }} disabled={!defaults} onClick={() => { if (defaults) { start(); setParams(JSON.parse(JSON.stringify(defaults))); commit(`${n.type} reset`) } }}>Reset to defaults</button>
          </div>
          <p className="hint"><Help text={`Previewed on the canvas with the compositor's own formulas; rendered exactly in the orchestrator on Save / Export.${editor && n.type !== 'color_balance' ? ' The histogram shows the visible pixel layers below this one.' : ''}`} /></p>
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
          {/* D90 (01 §11.2): commands, also in the layer menu of an AI layer */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}><CommandButton id="edit.ai.rerun" text /><CommandButton id="edit.ai.copyRecipe" text /></div>
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
  const rendererPref = useEditor((s) => s.rendererPref)
  const cursor = useEditor((s) => s.cursor)
  const dirty = useEditor((s) => s.docDirty)
  const revision = useEditor((s) => s.revision)
  const cmp = useEditor((s) => s.lastCompare)
  const mem = useMemo(() => { const st = ed(); let b = 0; st.pixels.forEach((lp) => { b += lp.width * lp.height * 4 }); st.masks.forEach((lp) => { b += lp.width * lp.height * 4 }); if (st.selection) b += st.selection.width * st.selection.height * 4; return b }, [revision]) // eslint-disable-line react-hooks/exhaustive-deps
  let total = 0; walk(doc.layers, () => { total++ })
  return (
    <div>
      <dl className="kv">
        <dt>name</dt><dd>{doc.name}</dd>
        <dt>size</dt><dd>{doc.w}×{doc.h} · background {doc.background}</dd>
        <dt>layers</dt><dd>{countRasters(doc)} raster · {total} nodes</dd>
        <dt>source</dt><dd>{doc.source_asset_id ? <img className="insp-thumb" src={api.thumbUrl(doc.source_asset_id, 256)} alt="" /> : '—'}</dd>
        <dt>saved</dt><dd>{doc.saved_at ? new Date(doc.saved_at).toLocaleString() : 'never'}{dirty ? ' · unsaved changes' : ''}</dd>
        <dt>colour</dt><dd>sRGB · 8-bit layers (16-bit later)</dd>
      </dl>
      {/* D90 (01 §11.6): ids, memory, the renderer and the exact-flatten check are developer-facing — folded (open in dev builds) */}
      <Section id="info-diagnostics" title="Diagnostics" defaultOpen={DEV_HOOKS}>
        <dl className="kv">
          <dt>document</dt><dd className="mono">{doc.id}</dd>
          {doc.source_asset_id && <><dt>source id</dt><dd className="mono">{doc.source_asset_id}</dd></>}
          <dt>memory</dt><dd>{(mem / 1048576).toFixed(0)} MB CPU canvases + the GPU copies</dd>
          <dt>renderer</dt><dd><RendererButton className="quiet" renderer={renderer} pref={rendererPref} onCycle={ed().setRendererPref} /></dd>
          <dt>cursor</dt><dd className="mono">{cursor ? `${cursor.x}, ${cursor.y}` : '—'}</dd>
          {DEV_HOOKS && <><dt>preview vs exact</dt><dd><CommandButton id="edit.compare" text />{cmp && <div className="kind">RGB mean {cmp.rgb_mean.toFixed(2)} · p99 {cmp.rgb_p99} · max {cmp.rgb_max} · with alpha p99 {cmp.p99} · {new Date(cmp.at).toLocaleTimeString()}</div>}</dd></>}
        </dl>
      </Section>
    </div>
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
      if ((e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable], .modal, .curves-graph')) return   // the Curves graph owns Delete / arrows (F8)
      const st = ed()
      const k = e.key
      const before = command('edit.view.before')                                                    // D72: hold its key (remappable) for before
      if (before && matchesCommand(e, before)) { e.preventDefault(); st.setView({ before: true }); return }
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && k.toLowerCase() === 'v') return             // D46: let the browser's paste event carry the clipboard
      if (magnetic.active && (k === 'Backspace' || k === 'Delete')) { e.preventDefault(); void magnetic.removeLast(); return }   // D59
      if (st.transform && k.startsWith('Arrow') && !e.ctrlKey && !e.altKey) {                        // D58: arrows nudge the box (Shift 10 px)
        e.preventDefault()
        const d = e.shiftKey ? 10 : 1, dx = k === 'ArrowLeft' ? -d : k === 'ArrowRight' ? d : 0, dy = k === 'ArrowUp' ? -d : k === 'ArrowDown' ? d : 0
        const t = st.transform
        st.setTransform({ quad: t.quad.map((c) => ({ x: c.x + dx, y: c.y + dy })) as typeof t.quad, pivot: { x: t.pivot.x + dx, y: t.pivot.y + dy } })
        return
      }
      if (k === 'Escape') { if (magnetic.active) magnetic.cancel(); else if (st.lassoPoly) st.setLassoPoly(null); else if (st.transform) st.cancelTransform(); else if (st.quickMask) st.setView({ quickMask: false }); else if (st.selection) st.deselect(); return }
      // every other key is an accelerator for a registry command; a handled key stops here so the global
      // suite switch (Ctrl+1/2, 07 §4) yields to the view keys of 10 §5 while a document is open
      if (handleKeyFor('edit', e)) e.stopImmediatePropagation()
    }
    const up = (e: KeyboardEvent) => { if (useSession.getState().ui.suite !== 'edit') return; const b = command('edit.view.before')?.keys; if (b && e.key.toLowerCase() === parseChord(b).key) ed().setView({ before: false }) }
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
        if (!useSession.getState().project?.open || useSession.getState().ui.suite !== 'edit' || st.doc || st.loading) return false   // U1: as when it mounted with Edit's strip
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
    ensureEditorAutosave()                                       // B20: survives suite switches (U1: the shell keeps this hook mounted)
    return () => { window.removeEventListener('keydown', down, { capture: true }); window.removeEventListener('keyup', up); window.removeEventListener('paste', paste); unsubDeep() }
  }, [])
}

// U1 (D157): the keys, paste, deep links and autosave are the shell's (frame/keyHosts.tsx), not the Strip's
registerKeyHost('edit', function EditKeys() { useEditKeys(); return null })

/** The empty Edit stage takes a dropped tile and opens it (frame/drag.ts). */
function EmptyDrop({ children }: { children: React.ReactNode }) {
  const { ref, over } = useDropTarget((p) => onlyAssets(p) && editOpenDrop(p).verdict.ok, (p) => { const id = editOpenDrop(p).open; if (id) void ed().openFromAsset(id) }, (p) => editOpenDrop(p).verdict)
  return <div ref={ref} className={`edit-empty${over ? ' drop-over' : ''}`}>{children}</div>
}

export const EditSuite: SuiteDef = {
  id: 'edit',
  rail: DEFAULT_RAIL.edit,
  Panel, Strip, Stage, Inspector, PrimaryAction, keepAlive: true,
}
