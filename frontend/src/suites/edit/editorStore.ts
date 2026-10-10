// Edit suite state (10): the open document (stack + pixels), view, tools and options, selection, history,
// and persistence against /documents. Pixels live in LayerPixels (canvas + texture); the store holds references.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ApiError, http, unwrap } from '../../api/client'
import type { DocSummary as ApiDocSummary, Document as ApiDocument, DocumentChangedData, DocumentRecipe, RefineEdgeParams } from '../../api/types'
import { useSession } from '../../store/session'
import { LayerPixels, lumaOf, selectionAlphaCanvas, type TileSnapshot } from './layerPixels'
import { border, changedTiles, combine, contract, expand, feather, selectionValues, smooth, writeSelection, type SelectionMode } from './selectionOps'
import { maskAlphaCanvas } from './maskDerived'
import { isIdentity, resample, type Xform } from './transform'

export type NodeKind = 'raster' | 'group' | 'adjustment' | 'filter'
export interface MaskRef { enabled: boolean; linked: boolean; x: number; y: number; density?: number; feather?: number; default?: number }   // D52: density 0–1, feather σ px; D54: the value outside the extent
/** D54: how a new mask starts (PhotoCraft Reveal All / Hide All / Reveal Selection / Hide Selection). */
export type MaskInit = 'reveal' | 'hide' | 'revealSelection' | 'hideSelection'
export interface Node {
  kind: NodeKind; id: string; name: string; opacity: number; blend: string; visible: boolean; locked: boolean; clip: boolean; mask: MaskRef | null
  x?: number; y?: number; w?: number; h?: number; fill?: number; recipe?: Record<string, unknown> | null; lineage_asset_id?: string | null
  lock_alpha?: boolean            // D50: painting keeps the layer's transparency
  passthrough?: boolean; children?: Node[]
  type?: string; params?: Record<string, unknown>
}
export interface DocumentStack {
  schema_version: number; id: string; name: string; w: number; h: number; background: string; source_asset_id: string | null
  created_at: string; saved_at: string | null; revision: number; layers: Node[]; has_selection: boolean; meta: Record<string, unknown>
}
export type DocSummary = ApiDocSummary
/** The editor works on a flat node model (every field optional, one `kind` tag) rather than the server's discriminated layer union;
 *  this is the one place a server document becomes that model (D38: the API side of the boundary is typed). */
const asStack = (d: ApiDocument): DocumentStack => d as unknown as DocumentStack
const asBody = (s: DocumentStack): { [key: string]: unknown } => s as unknown as { [key: string]: unknown }
export type Tool = 'move' | 'marquee' | 'lasso' | 'wand' | 'ai' | 'brush' | 'eraser' | 'fill' | 'eyedropper' | 'crop' | 'hand' | 'zoom'
export const TOOL_KEYS: Record<string, Tool> = { v: 'move', m: 'marquee', l: 'lasso', w: 'wand', a: 'ai', b: 'brush', e: 'eraser', g: 'fill', i: 'eyedropper', c: 'crop', h: 'hand', z: 'zoom' }
export const BLEND_MODES = ['normal', 'dissolve', 'darken', 'multiply', 'color-burn', 'linear-burn', 'lighten', 'screen', 'color-dodge', 'linear-dodge', 'overlay', 'soft-light', 'hard-light',
  'vivid-light', 'linear-light', 'pin-light', 'hard-mix', 'difference', 'exclusion', 'subtract', 'divide', 'hue', 'saturation', 'color', 'luminosity']
/** Default parameters per adjustment / filter type; names and scales match orchestrator/loom2/compose.py. */
export const ADJUSTMENT_DEFAULTS: Record<string, Record<string, unknown>> = {
  levels: { in_black: 0, in_white: 255, gamma: 1, out_black: 0, out_white: 255 },
  curves: { rgb: [[0, 0], [255, 255]] },
  hue_saturation: { hue: 0, saturation: 0, lightness: 0 },
  color_balance: { shadows: [0, 0, 0], midtones: [0, 0, 0], highlights: [0, 0, 0] },
  brightness_contrast: { brightness: 0, contrast: 0 },
  exposure: { exposure: 0, offset: 0, gamma: 1 },
  black_white: { r: 40, g: 60, b: 20 },
  invert: {},
}
export const FILTER_DEFAULTS: Record<string, Record<string, unknown>> = {
  gaussian_blur: { radius: 2 }, sharpen: { amount: 100, radius: 1, threshold: 0 }, noise: { amount: 10, seed: 0, monochrome: true }, high_pass: { radius: 3 },
  color_to_alpha: { colour: '#ffffff', transparency_threshold: 0, opacity_threshold: 100 },      // D49
}

export interface CompareResult { mean: number; p99: number; max: number; rgb_mean: number; rgb_p99: number; rgb_max: number; w: number; h: number; at: string }
export interface BrushOptions { size: number; hardness: number; opacity: number; flow: number; spacing: number; smoothing: number; color: string; background: string }
export interface BrushPreset { name: string; size: number; hardness: number; opacity: number; flow: number; spacing: number; smoothing: number; builtin?: boolean }
export interface HistoryEntry {
  label: string; layerId: string; kind: 'image' | 'mask'; tiles: TileSnapshot[]; stack?: DocumentStack; at: number; swap?: { layerId: string; lp: LayerPixels; mask: LayerPixels | null }
  /** D43: a selection edit — whether a selection existed before and after it (undo / redo restore its presence too). */
  sel?: { had: boolean; has: boolean }
  /** D43: consecutive entries with the same key within a couple of seconds merge into one history row (one gesture). */
  coalesce?: string
}
export type SelectionModify = 'expand' | 'contract' | 'border' | 'smooth' | 'feather'
type ViewKeys = 'zoom' | 'pan' | 'overlay' | 'before' | 'pixelGrid' | 'quickMask' | 'marqueeShape' | 'selectionMode' | 'tolerance' | 'fillMode' | 'maskView'
  | 'latched' | 'blendPreview'
  | 'marqueeFeather' | 'marqueeStyle' | 'marqueeW' | 'marqueeH' | 'lassoKind' | 'wandContiguous' | 'wandMerged' | 'wandAA' | 'selModifyPx' | 'brushLine' | 'pickOnce'

export interface EditorState {
  doc: DocumentStack | null; docDirty: boolean; loading: boolean; saving: boolean; error: string | null
  activeId: string | null; editingMask: boolean
  // D54: the inactive colour pair (the image pair while a mask is the target, the mask pair otherwise) and which pair is live;
  // maskView 'gray' shows the active layer's mask alone
  otherColours: { color: string; background: string }; maskPairActive: boolean; maskView: 'off' | 'gray'
  // D55: latched modifiers (the strip's ⇧ / Ctrl / Alt; canvas tools read them OR'ed with the keyboard, until clicked off) and the
  // blend mode the dropdown is hovering (the canvas renders it; nothing is recorded)
  latched: { shift: boolean; ctrl: boolean; alt: boolean }; blendPreview: { id: string; mode: string } | null
  // D56: the layer selection (it counts only while it holds the active layer) and the Shift-click anchor
  selectedIds: string[]; anchorId: string | null
  tool: Tool; brush: BrushOptions; marqueeShape: 'rect' | 'ellipse'; selectionMode: SelectionMode; tolerance: number; fillMode: 'solid' | 'linear' | 'radial'
  // D44: selection tool options — marquee feather and style, lasso kind (and the open polygon), wand switches, the modify amount
  marqueeFeather: number; marqueeStyle: 'normal' | 'ratio' | 'size'; marqueeW: number; marqueeH: number
  lassoKind: 'freehand' | 'polygon'; lassoPoly: { x: number; y: number }[] | null
  wandContiguous: boolean; wandMerged: boolean; wandAA: boolean
  selModifyPx: number
  brushLine: boolean; pickOnce: boolean          // D51: straight-line strokes; the next click picks the colour
  /** D45: the user's Refine Edge settings over /capabilities.refine_edge.defaults (empty = the server's defaults, T8). */
  refineEdge: Partial<RefineEdgeParams>
  /** D46: the editor's clipboard — the copied pixels and where they came from (document coordinates). */
  clipboard: { canvas: HTMLCanvasElement; x: number; y: number } | null
  zoom: number; pan: { x: number; y: number }; fitRequested: number; overlay: boolean; before: boolean; pixelGrid: boolean; quickMask: boolean
  history: HistoryEntry[]; future: HistoryEntry[]
  renderer: string; cursor: { x: number; y: number } | null
  rendererPref: 'auto' | 'webgpu' | 'webgl'; rendererEpoch: number     // D3: auto = WebGPU with a pixel probe, WebGL2 if it draws nothing
  pixels: Map<string, LayerPixels>; masks: Map<string, LayerPixels>; selection: LayerPixels | null
  revision: number
  extractor: (() => HTMLCanvasElement | null) | null
  lastCompare: CompareResult | null
  compareWithExact: () => Promise<CompareResult | null>
  // AI (10 §4, M5): jobs run on the saved server document; results arrive as layers via document.changed
  aiBatch: string | null                      // batch id of the last AI run (its candidates form the strip)
  candidates: { group: string; ids: string[] } | null
  runAi: (recipe: DocumentRecipe, stage?: boolean) => Promise<void>
  onDocumentChanged: (d: DocumentChangedData) => void
  mergeServerLayers: (added: string[], group?: string, shift?: { left: number; top: number }) => Promise<void>
  pickCandidate: (keepId: string | null) => void
  // AI Select (10 §4, A tool): the prompt collected on the canvas, and the selection the segment job writes on the server
  aiPrompt: { points: { x: number; y: number; label: 1 | 0 }[]; box: [number, number, number, number] | null }
  setAiPrompt: (p: Partial<EditorState['aiPrompt']>) => void
  loadSelectionFromServer: (label?: string) => Promise<void>
  // free transform (10 §4): live numbers for the preview; applied by resampling the layer (and a linked mask)
  transform: Xform | null
  beginTransform: () => void
  setTransform: (patch: Partial<Xform>) => void
  applyTransform: () => void
  cancelTransform: () => void
  flipLayer: (axis: 'h' | 'v') => void
  rotateLayer: (deg: number) => void
  // documents
  openDocument: (id: string) => Promise<void>
  openFromAsset: (assetId: string) => Promise<void>
  addLayerFromAsset: (assetId: string) => Promise<void>
  newDocument: (w: number, h: number, name?: string) => Promise<void>
  closeDocument: () => void
  listDocuments: () => Promise<DocSummary[]>
  deleteDocument: (id: string) => Promise<void>
  save: () => Promise<boolean>
  resync: () => Promise<void>
  saveToCatalogue: () => Promise<void>
  exportPng: () => Promise<void>
  exportPsd: () => Promise<void>
  // tools / view
  setTool: (t: Tool) => void
  setBrush: (p: Partial<BrushOptions>) => void
  brushPresets: BrushPreset[]
  saveBrushPreset: (name: string) => void
  deleteBrushPreset: (name: string) => void
  applyBrushPreset: (p: BrushPreset) => void
  setView: (p: Partial<Pick<EditorState, ViewKeys>>) => void
  requestFit: () => void
  zoomTo: (z: number) => void
  setRenderer: (r: string) => void
  setRendererPref: (p: 'auto' | 'webgpu' | 'webgl') => void
  setCursor: (c: { x: number; y: number } | null) => void
  setExtractor: (f: EditorState['extractor']) => void
  // stack
  /** `mask` true / false targets the mask / the pixels (thumbnail clicks); left out (a row click) keeps the current target when the
   * layer has a mask — adjustment and filter rows target their mask (D54). */
  setActive: (id: string | null, mask?: boolean) => void
  updateNode: (id: string, patch: Partial<Node>, label?: string, coalesce?: string) => void
  addLayer: (kind?: NodeKind, extra?: Partial<Node>) => Node | null
  deleteNode: (id: string) => void
  duplicateNode: (id: string) => void
  moveNode: (id: string, dir: 'up' | 'down') => void
  mergeDown: (id: string) => void
  groupActive: () => void
  solo: (id: string) => void
  addMask: (id: string, how?: MaskInit) => void
  /** D56 (PhotoCraft layer_multi_cmds): click replaces, Ctrl-click toggles (never empties), Shift-click selects the range from the anchor. */
  selectLayer: (id: string, how?: 'replace' | 'toggle' | 'range') => void
  /** The layers a layer command acts on: the selection when it holds the active layer, else the active layer — top-level only (a
   * selected layer inside a selected group goes with its group), in panel order (top first). */
  targetIds: () => string[]
  deleteNodes: (ids: string[]) => void
  duplicateNodes: (ids: string[]) => void
  groupNodes: (ids: string[]) => void
  mergeNodes: (ids: string[]) => void
  setPropsFor: (ids: string[], patch: Partial<Node>, label: string) => void
  /** Reorder: the layers go above / below the target row, or into a group (at its top); `copy` drops duplicates. One history step. */
  moveNodesTo: (ids: string[], targetId: string, where: 'above' | 'below' | 'into', copy?: boolean) => void
  removeMask: (id: string) => void
  toggleMaskLink: (id: string) => void
  applyMask: (id: string) => void
  maskFromTransparency: (id: string) => void
  resizeCanvas: (w: number, h: number, ax?: number, ay?: number) => void
  cropToSelection: () => void
  clearSelected: () => void
  // history
  pushHistory: (e: HistoryEntry) => void
  undo: () => void
  redo: () => void
  touch: () => void
  bump: () => void
  // selection
  ensureSelection: () => LayerPixels
  clearSelection: () => void
  /** D43: run a selection change as one undoable step (tiles that changed, and whether a selection exists before / after). */
  editSelection: (label: string, fn: () => void, coalesce?: string) => void
  /** D44: combine a document-sized shape (values 0–255) into the selection by mode, feathered first when asked; one undo step. */
  applySelectionShape: (shape: Uint8Array, mode: SelectionMode, label: string, featherPx?: number) => void
  selectLayerAlpha: (id: string) => void
  setLassoPoly: (pts: { x: number; y: number }[] | null) => void
  setRefineEdge: (p: Partial<RefineEdgeParams> | null) => void
  // D46 clipboard: copy / cut the selected pixels of the active layer (or of the composite), paste as a new layer
  copySelection: (opts?: { merged?: boolean; cut?: boolean }) => boolean
  pasteClipboard: (inPlace?: boolean) => Promise<void>
  /** A DOM paste (Ctrl+V): an image from the OS clipboard, or the editor's own clipboard. */
  pasteFromEvent: (files: File[]) => Promise<void>
  layerVia: (cut: boolean) => void
  addImageLayer: (img: CanvasImageSource & { width: number; height: number }, name: string, at?: { x: number; y: number }, lineage?: string) => string | null
  dropFiles: (paths: string[]) => Promise<void>
  /** D49: Colour to Alpha with white on the active raster layer, destructively (one undo step) — line art becomes ink. */
  inkFromWhite: () => void
  refineParams: () => RefineEdgeParams
  refineSelection: () => Promise<void>
  closeLassoPoly: (mode?: SelectionMode) => void
  deselect: () => void
  modifySelection: (op: SelectionModify, px: number) => void
  selectAll: () => void
  invertSelection: () => void
  featherSelection: (px: number) => void
  loadSelectionFromMask: () => void
}

const DEFAULT_BRUSH: BrushOptions = { size: 48, hardness: 0.8, opacity: 1, flow: 0.6, spacing: 0.15, smoothing: 0.4, color: '#f0a63a', background: '#111111' }

/** D56 helpers: ids in panel order (top first, a group before its children), each id's parent group, the top-level subset of ids. */
function walkOrder(doc: DocumentStack): string[] { const out: string[] = []; walk(doc.layers, (n) => { out.push(n.id) }); return out }
function parentMap(doc: DocumentStack): Map<string, string | null> {
  const m = new Map<string, string | null>()
  const rec = (ns: Node[], p: string | null) => ns.forEach((n) => { m.set(n.id, p); if (n.children) rec(n.children, n.id) })
  rec(doc.layers, null)
  return m
}
function topLevel(doc: DocumentStack, ids: string[]): string[] {
  const pm = parentMap(doc), set = new Set(ids)
  return ids.filter((id) => { for (let p = pm.get(id) ?? null; p; p = pm.get(p) ?? null) if (set.has(p)) return false; return true })
}
/** A deep copy of a node with fresh ids, its pixels and masks copied too (`named`: "… copy"). */
function copyNode(n: Node, pixels: Map<string, LayerPixels>, masks: Map<string, LayerPixels>, named: boolean): Node {
  const c: Node = { ...JSON.parse(JSON.stringify(n)), id: newId(n.kind === 'group' ? 'grp' : 'lyr'), name: named ? `${n.name} copy` : n.name }
  const dup = (src: LayerPixels | undefined, grey: boolean) => { if (!src) return null; const lp = new LayerPixels(src.width, src.height, grey); lp.ctx.drawImage(src.canvas, 0, 0); lp.refresh(); lp.dirty = true; return lp }
  if (n.kind === 'raster') { const lp = dup(pixels.get(n.id), false); if (lp) pixels.set(c.id, lp) }
  if (n.mask) { const m = dup(masks.get(n.id), true); if (m) masks.set(c.id, m) }
  if (n.children) c.children = n.children.map((k) => copyNode(k, pixels, masks, false))
  return c
}

function walk(nodes: Node[], fn: (n: Node, parent: Node[] | null, index: number) => boolean | void, parent: Node[] | null = null): boolean {
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i]
    if (fn(n, parent ?? nodes, i)) return true
    if (n.children && walk(n.children, fn, n.children)) return true
  }
  return false
}
export function findNode(doc: DocumentStack | null, id: string | null): Node | null {
  if (!doc || !id) return null
  let out: Node | null = null
  walk(doc.layers, (n) => { if (n.id === id) { out = n; return true } })
  return out
}
function findParent(doc: DocumentStack, id: string): { list: Node[]; index: number } | null {
  let out: { list: Node[]; index: number } | null = null
  walk(doc.layers, (n, parent, i) => { if (n.id === id) { out = { list: parent ?? doc.layers, index: i }; return true } })
  return out
}
export function countRasters(doc: DocumentStack): number { let n = 0; walk(doc.layers, (x) => { if (x.kind === 'raster') n++ }); return n }
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))
const newId = (p: string) => `${p}_${Math.random().toString(16).slice(2, 10)}`
// 10 §6: entering mask editing from a tool that cannot paint or select (Move, Crop, Zoom, Hand, Eyedropper) switches to the
// brush, so the first click paints the mask instead of dragging the layer; a one-time toast explains white/black.
const PAINTS_MASK: Tool[] = ['brush', 'eraser', 'fill', 'marquee', 'lasso', 'wand', 'ai']
let maskHintShown = false
const maskEditExtras = (tool: Tool): { tool?: Tool } => {
  if (!maskHintShown) { maskHintShown = true; useSession.getState().toast('Editing the mask — the mask colours are live: the brush paints the foreground (black hides, white shows), the eraser the background; X swaps them. Click the layer thumbnail to edit its pixels again.', 'info') }
  return PAINTS_MASK.includes(tool) ? {} : { tool: 'brush' }
}
let openSeq = 0                                                   // C31: the latest openDocument() wins; a superseded load frees what it fetched
const download = (blob: Blob, name: string) => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000) }
const maskOffset = (n: Node) => ({ x: (n.mask?.linked ? (n.x ?? 0) : 0) + (n.mask?.x ?? 0), y: (n.mask?.linked ? (n.y ?? 0) : 0) + (n.mask?.y ?? 0) })

async function fetchRaw(docId: string, lid: string, kind: 'image' | 'mask'): Promise<LayerPixels | null> {
  const b = useSession.getState().backend!
  const res = await fetch(`http://${b.host}:${b.port}/documents/${docId}/layers/${lid}/pixels?kind=${kind}&raw=1`, { headers: { 'X-Loom-Token': b.token } })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`pixels ${lid}: ${res.status}`)
  const w = Number(res.headers.get('x-loom-width')), h = Number(res.headers.get('x-loom-height')), ch = Number(res.headers.get('x-loom-channels')) as 1 | 4
  return LayerPixels.fromRaw(w, h, new Uint8Array(await res.arrayBuffer()), ch)
}

async function putRaw(docId: string, lid: string, kind: 'image' | 'mask', lp: LayerPixels): Promise<void> {
  const b = useSession.getState().backend!
  const res = await fetch(`http://${b.host}:${b.port}/documents/${docId}/layers/${lid}/pixels?kind=${kind}&w=${lp.width}&h=${lp.height}`,
    { method: 'PUT', headers: { 'X-Loom-Token': b.token, 'Content-Type': 'application/octet-stream' }, body: lp.toRaw() as BodyInit })
  if (!res.ok) throw new Error(`upload ${lid}: ${res.status} ${await res.text()}`)
}

/** A stack snapshot restored by undo / redo keeps the server bookkeeping of the current stack: its old `revision` would make
 * the next save a 409, and the resync that follows merges back server layers the snapshot lacks — re-adding an undone layer. */
function keepServerState(stack: DocumentStack, cur: DocumentStack | null): DocumentStack {
  return cur ? { ...stack, revision: cur.revision, saved_at: cur.saved_at } : stack
}

/** D49 Colour to Alpha with white as the key, in place on straight RGBA bytes (compose.py `_color_to_alpha`): a = max over the
 * channels of (255 − P) / 255, Q = 255 − (255 − P) / a, alpha × a — black ink at 50 % over paper becomes black at alpha 50 %. */
function unmixWhite(d: Uint8ClampedArray): void {
  for (let i = 0; i < d.length; i += 4) {
    const a = Math.max(255 - d[i], 255 - d[i + 1], 255 - d[i + 2]) / 255
    if (a <= 0) { d[i + 3] = 0; continue }
    for (let c = 0; c < 3; c++) d[i + c] = Math.round(255 - (255 - d[i + c]) / a)
    d[i + 3] = Math.round(d[i + 3] * a)
  }
}

/** D46: the PNG size last written to the OS clipboard — a paste of the same size is our own copy (and keeps its position). */
let osClipboardSize = -1

export const useEditor = create<EditorState>()(
  persist(
    (set, get) => {
      /** Put the history entry's canvases back and return the ones they replaced (so redo is the same operation). */
      const swapPixels = (s: NonNullable<HistoryEntry['swap']>): NonNullable<HistoryEntry['swap']> => {
        const cur = get().pixels.get(s.layerId) ?? null
        get().pixels.set(s.layerId, s.lp); s.lp.dirty = true
        let curMask: LayerPixels | null = null
        if (s.mask) { curMask = get().masks.get(s.layerId) ?? null; get().masks.set(s.layerId, s.mask); s.mask.dirty = true }
        return { layerId: s.layerId, lp: cur ?? s.lp, mask: curMask }
      }
      /** Destroy the canvases that only these (dropped) history entries referenced: swapped-out transform sources. */
      const releaseEntries = (entries: HistoryEntry[]) => {
        const live = new Set<LayerPixels>([...get().pixels.values(), ...get().masks.values()])
        for (const e of entries) {
          if (!e.swap) continue
          if (!live.has(e.swap.lp)) e.swap.lp.destroy()
          if (e.swap.mask && !live.has(e.swap.mask)) e.swap.mask.destroy()
        }
      }
      /** Drop pixel / mask canvases no stack (current, undo or redo) refers to any more — deleted layers, picked-over candidates, removed masks. */
      const gcPixels = () => {
        const nodes = new Set<string>(), maskIds = new Set<string>()
        const add = (d: DocumentStack | undefined) => { if (d) walk(d.layers, (n) => { nodes.add(n.id); if (n.mask) maskIds.add(n.id) }) }
        add(get().doc ?? undefined); get().history.forEach((e) => add(e.stack)); get().future.forEach((e) => add(e.stack))
        for (const [id, lp] of get().pixels) if (!nodes.has(id)) { lp.destroy(); get().pixels.delete(id) }
        for (const [id, lp] of get().masks) if (!maskIds.has(id)) { lp.destroy(); get().masks.delete(id) }
      }
      /** The editor's selection → the server document (raw grey bytes; an empty body clears it). Jobs and Refine Edge read it there. */
      const uploadSelection = async () => {
        const { doc, selection } = get()
        const b = useSession.getState().backend!
        if (!doc) return
        const body = selection ? (selection.toRaw() as BodyInit) : new Uint8Array(0)
        const r0 = await fetch(`http://${b.host}:${b.port}/documents/${doc.id}/selection?w=${selection?.width ?? 0}&h=${selection?.height ?? 0}`,
          { method: 'PUT', headers: { 'X-Loom-Token': b.token, 'Content-Type': 'application/octet-stream' }, body })
        if (!r0.ok) throw new Error(`selection upload ${r0.status}`)
      }
      /** D43: the selection canvas an undo / redo restores into — a blank one when there is none (no selection = all zero). */
      const selectionFor = (e: HistoryEntry): LayerPixels | null => {
        const doc = get().doc
        if (get().selection || !e.sel || !doc) return get().selection
        const sel = new LayerPixels(doc.w, doc.h, true)
        set({ selection: sel })
        return sel
      }
      const setSelectionPresence = (present: boolean) => {
        if (present || !get().selection) return
        get().selection!.destroy()
        set({ selection: null, quickMask: false })
      }
      /** Replace the stack, mark dirty, and record the previous stack as one undoable step. */
      const commit = (next: DocumentStack, before: DocumentStack, label: string, layerId: string, extra: Partial<EditorState> = {}, coalesce?: string) => {
        set({ doc: next, docDirty: true, revision: get().revision + 1, ...extra })
        get().pushHistory({ label, layerId, kind: 'image', tiles: [], stack: before, at: Date.now(), coalesce })
      }
      /** Bake `t` into the layer's pixels (and its linked mask); the old canvases ride along in history for undo. */
      const resampleLayer = (t: Xform, label: string) => {
        const doc = get().doc
        const n = findNode(doc, t.nodeId)
        const lp = n ? get().pixels.get(n.id) : undefined
        if (!doc || !n || !lp) return
        const before = clone(doc)
        const r = resample(lp.canvas, t, n.x ?? 0, n.y ?? 0)
        const nlp = LayerPixels.fromImage(r.canvas); nlp.dirty = true
        const oldMask = get().masks.get(n.id) ?? null
        let newMask: LayerPixels | null = null
        let maskPatch: Partial<Node> = {}
        if (n.mask?.linked && oldMask) {
          const m = resample(oldMask.canvas, t, (n.x ?? 0) + n.mask.x, (n.y ?? 0) + n.mask.y)
          newMask = LayerPixels.fromImage(m.canvas); newMask.dirty = true
          // keep it grey: fromImage makes an RGBA canvas, the mask flag only changes what toRaw() uploads
          Object.defineProperty(newMask, 'grey', { value: true })
          maskPatch = { mask: { ...n.mask, x: m.x - r.x, y: m.y - r.y } }
          get().masks.set(n.id, newMask)
        }
        get().pixels.set(n.id, nlp)
        const next = clone(doc)
        walk(next.layers, (m) => { if (m.id === n.id) { Object.assign(m, { x: r.x, y: r.y, w: nlp.width, h: nlp.height }, maskPatch); return true } })
        set({ doc: next, docDirty: true, revision: get().revision + 1 })
        get().pushHistory({ label, layerId: n.id, kind: 'image', tiles: [], stack: before, at: Date.now(), swap: { layerId: n.id, lp, mask: newMask ? oldMask : null } })
      }
      const setCanvas = (w: number, h: number, dx: number, dy: number, label: string) => {
        const doc = get().doc
        if (!doc || w < 1 || h < 1) return
        const before = clone(doc)
        const next = clone(doc)
        next.w = w; next.h = h
        walk(next.layers, (n) => { if (n.kind === 'raster') { n.x = (n.x ?? 0) + dx; n.y = (n.y ?? 0) + dy } if (n.mask && !n.mask.linked) { n.mask.x += dx; n.mask.y += dy } })   // unlinked masks on every kind (as queue.py shifts them)
        const sel = get().selection
        let selection: LayerPixels | null = null
        if (sel) { selection = new LayerPixels(w, h, true); selection.ctx.drawImage(sel.canvas, dx, dy); selection.refresh(); sel.destroy() }
        commit(next, before, label, doc.id, { selection })
        get().requestFit()
      }
      return {
        doc: null, docDirty: false, loading: false, saving: false, error: null, activeId: null, editingMask: false,
        otherColours: { color: '#000000', background: '#ffffff' }, maskPairActive: false, maskView: 'off',
        latched: { shift: false, ctrl: false, alt: false }, blendPreview: null, selectedIds: [], anchorId: null,
        tool: 'brush', brush: DEFAULT_BRUSH, marqueeShape: 'rect', selectionMode: 'replace', tolerance: 32, fillMode: 'solid',
        marqueeFeather: 0, marqueeStyle: 'normal', marqueeW: 16, marqueeH: 9, lassoKind: 'freehand', lassoPoly: null, wandContiguous: true, wandMerged: false, wandAA: true, selModifyPx: 4, refineEdge: {}, clipboard: null, brushLine: false, pickOnce: false,
        zoom: 1, pan: { x: 0, y: 0 }, fitRequested: 0, overlay: true, before: false, pixelGrid: false, quickMask: false,
        history: [], future: [], renderer: '', rendererPref: 'auto', rendererEpoch: 0, cursor: null, pixels: new Map(), masks: new Map(), selection: null, revision: 0, extractor: null, lastCompare: null,
        transform: null,
        aiBatch: null, candidates: null, aiPrompt: { points: [], box: null },

        runAi: async (recipe, stage = false) => {
          const { doc } = get()
          const s = useSession.getState()
          if (!doc) return
          try {
            if (!(await get().save())) return                               // the job reads the saved document
            await uploadSelection()
            const r = await unwrap(http.POST('/documents/{doc_id}/ai', { params: { path: { doc_id: doc.id } }, body: { recipe, stage } }))
            const jobs = r.jobs
            set({ aiBatch: jobs[0]?.batch_id ?? jobs[0]?.id ?? null, candidates: null })
            s.toast(stage ? `Staged ${jobs.length} AI job${jobs.length > 1 ? 's' : ''}` : `Queued ${jobs.length} AI job${jobs.length > 1 ? 's' : ''} — results arrive as layers`, 'info')
            void s.refreshAll()
          } catch (e) { s.toast(`AI job failed to start: ${(e as ApiError).detail ?? (e as Error).message}`, 'error') }
        },
        onDocumentChanged: (d) => {
          const doc = get().doc
          if (!doc || d.id !== doc.id) return
          if (d.selection) { void get().loadSelectionFromServer(); return }
          if (d.added?.length) void get().mergeServerLayers(d.added, d.group ?? undefined, d.shift ?? undefined)
        },
        setAiPrompt: (p) => set({ aiPrompt: { ...get().aiPrompt, ...p }, revision: get().revision + 1 }),
        loadSelectionFromServer: async (label = 'AI select') => {
          const doc = get().doc
          if (!doc) return
          try {
            const b = useSession.getState().backend!
            const res = await fetch(`http://${b.host}:${b.port}/documents/${doc.id}/selection`, { headers: { 'X-Loom-Token': b.token } })
            if (res.status === 404) { get().deselect(); return }
            if (!res.ok) throw new Error(`selection ${res.status}`)
            const w = Number(res.headers.get('x-loom-width')), h = Number(res.headers.get('x-loom-height'))
            const sel = LayerPixels.fromRaw(w, h, new Uint8Array(await res.arrayBuffer()), 1)
            get().editSelection(label, () => { get().selection?.destroy(); set({ selection: sel, quickMask: false }) })
            if (label === 'AI select') useSession.getState().toast('AI Select: selection updated', 'success')
          } catch (e) { useSession.getState().toast(`Could not load the selection: ${(e as Error).message}`, 'error') }
        },
        mergeServerLayers: async (added, group, shift) => {
          const doc = get().doc
          if (!doc) return
          try {
            const server = asStack(await unwrap(http.GET('/documents/{doc_id}', { params: { path: { doc_id: doc.id } } })))
            const pixels = get().pixels, masks = get().masks
            await Promise.all(added.map(async (lid) => {
              const lp = await fetchRaw(doc.id, lid, 'image')
              if (lp) pixels.set(lid, lp)
              const n = findNode(server, lid)
              if (n?.mask) { const m = await fetchRaw(doc.id, lid, 'mask'); if (m) masks.set(lid, m) }
            }))
            const cur = get().doc
            if (!cur || cur.id !== doc.id) return
            const before = clone(cur)
            // C20: merge the server's additions into the *local* stack instead of adopting the server's — layers added, moved or
            // renamed while the job ran survive. When outpaint grew the canvas, shift local layers like the server shifted its own.
            const next = clone(cur)
            const grown = server.w !== cur.w || server.h !== cur.h
            let dx = shift?.left ?? 0, dy = shift?.top ?? 0
            if (grown && !shift) {                                           // resync path: infer the shift from a layer both sides have
              const pair: { s: Node; l: Node }[] = []
              walk(server.layers, (s) => { const l = findNode(cur, s.id); if (s.kind === 'raster' && l?.kind === 'raster') { pair.push({ s, l }); return true } })
              if (pair[0]) { dx = (pair[0].s.x ?? 0) - (pair[0].l.x ?? 0); dy = (pair[0].s.y ?? 0) - (pair[0].l.y ?? 0) }
            }
            if (grown) {
              next.w = server.w; next.h = server.h
              if (dx || dy) walk(next.layers, (n) => { if (n.kind === 'raster') { n.x = (n.x ?? 0) + dx; n.y = (n.y ?? 0) + dy } if (n.mask && !n.mask.linked) { n.mask.x += dx; n.mask.y += dy } })   // unlinked masks on every kind (as queue.py shifts them)
            }
            const gnode = group ? findNode(server, group) : null
            if (gnode) {
              const local = findNode(next, gnode.id)
              if (local?.children) {                                           // later candidates join the group that is already here
                const have = new Set(local.children.map((c) => c.id))
                gnode.children?.forEach((c, i) => { if (!have.has(c.id)) local.children!.splice(Math.min(i, local.children!.length), 0, clone(c)) })
              } else next.layers.unshift(clone(gnode))
            } else for (const lid of [...added].reverse()) { const n = findNode(server, lid); if (n && !findNode(next, lid)) next.layers.unshift(clone(n)) }
            next.revision = server.revision; next.saved_at = server.saved_at
            let selection = get().selection
            if (grown && selection) { const sel = new LayerPixels(server.w, server.h, true); sel.ctx.drawImage(selection.canvas, dx, dy); sel.refresh(); selection.destroy(); selection = sel }
            const ids = gnode?.children?.map((c) => c.id) ?? added
            set({ doc: next, selection, candidates: ids.length > 1 ? { group: group ?? '', ids } : null, activeId: added[0], editingMask: false, revision: get().revision + 1 })
            get().pushHistory({ label: 'AI result', layerId: added[0], kind: 'image', tiles: [], stack: before, at: Date.now() })
            if (grown) get().requestFit()
            useSession.getState().toast(ids.length > 1 ? `Candidate ${ids.indexOf(added[0]) + 1} of ${ids.length} arrived — pick with 1–4 or the strip` : 'AI layer added', 'success')
          } catch (e) { useSession.getState().toast(`Could not load the AI result: ${(e as Error).message}`, 'error') }
        },
        pickCandidate: (keepId) => {
          const c = get().candidates
          const doc = get().doc
          if (!c || !doc) return
          if (keepId === null) {                                            // keep all (hidden except the visible one)
            set({ candidates: null })
            return
          }
          const before = clone(doc)
          const next = clone(doc)
          const g = findNode(next, c.group)
          if (g?.children) {
            for (const ch of g.children) ch.visible = ch.id === keepId
            g.children = g.children.filter((ch) => ch.id === keepId)
            // B18: the other candidates' canvases stay in the maps for undo; gc drops them when the history entry goes
          }
          set({ doc: next, candidates: null, activeId: keepId, docDirty: true, revision: get().revision + 1 })
          get().pushHistory({ label: 'pick candidate', layerId: keepId, kind: 'image', tiles: [], stack: before, at: Date.now() })
        },

        beginTransform: () => {
          const n = findNode(get().doc, get().activeId)
          const lp = n?.kind === 'raster' ? get().pixels.get(n.id) : undefined
          if (!n || !lp || n.locked) { useSession.getState().toast('Free transform needs an unlocked raster layer', 'info'); return }
          set({ transform: { nodeId: n.id, cx: (n.x ?? 0) + lp.width / 2, cy: (n.y ?? 0) + lp.height / 2, w: lp.width, h: lp.height, sx: 1, sy: 1, rot: 0 }, tool: 'move' })
        },
        setTransform: (patch) => { const t = get().transform; if (t) set({ transform: { ...t, ...patch } }) },
        cancelTransform: () => set({ transform: null, revision: get().revision + 1 }),
        applyTransform: () => {
          const t = get().transform
          const n = t ? findNode(get().doc, t.nodeId) : null
          if (!t || !n) { set({ transform: null }); return }
          if (isIdentity(t, n.x ?? 0, n.y ?? 0)) { get().cancelTransform(); return }
          resampleLayer(t, 'free transform')
          set({ transform: null })
        },
        flipLayer: (axis) => {
          const n = findNode(get().doc, get().activeId)
          const lp = n?.kind === 'raster' ? get().pixels.get(n.id) : undefined
          if (!n || !lp || n.locked) return
          resampleLayer({ nodeId: n.id, cx: (n.x ?? 0) + lp.width / 2, cy: (n.y ?? 0) + lp.height / 2, w: lp.width, h: lp.height, sx: axis === 'h' ? -1 : 1, sy: axis === 'v' ? -1 : 1, rot: 0 }, axis === 'h' ? 'flip horizontal' : 'flip vertical')
        },
        rotateLayer: (deg) => {
          const n = findNode(get().doc, get().activeId)
          const lp = n?.kind === 'raster' ? get().pixels.get(n.id) : undefined
          if (!n || !lp || n.locked) return
          resampleLayer({ nodeId: n.id, cx: (n.x ?? 0) + lp.width / 2, cy: (n.y ?? 0) + lp.height / 2, w: lp.width, h: lp.height, sx: 1, sy: 1, rot: deg * Math.PI / 180 }, `rotate ${deg}°`)
        },

        /** GPU composite vs the orchestrator's exact flatten (10 §14 item 1); PixiJS un-premultiplies on extract. */
        compareWithExact: async () => {
          if (get().docDirty && !(await get().save())) return null       // the exact flatten runs on the saved document
          const { doc, extractor } = get()
          const c = doc && extractor ? extractor() : null
          if (!doc || !c) return null
          try {
            const img = c.getContext('2d')!.getImageData(0, 0, doc.w, doc.h)
            const b = useSession.getState().backend!
            const res = await fetch(`http://${b.host}:${b.port}/documents/${doc.id}/compare?w=${doc.w}&h=${doc.h}`,
              { method: 'POST', headers: { 'X-Loom-Token': b.token, 'Content-Type': 'application/octet-stream' }, body: img.data as BodyInit })
            if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
            const r = await res.json() as CompareResult
            set({ lastCompare: r })
            useSession.getState().toast(`Preview vs exact: mean ${r.rgb_mean.toFixed(2)} · p99 ${r.rgb_p99} · max ${r.rgb_max} (0–255)`, r.rgb_p99 <= 2 ? 'success' : 'info')
            return r
          } catch (e) { useSession.getState().toast(`Compare failed: ${(e as Error).message}`, 'error'); return null }
        },

        // ---- documents -----------------------------------------------------------------------------
        openDocument: async (id) => {
          get().closeDocument()
          const seq = ++openSeq
          set({ loading: true, error: null })
          try {
            const doc = asStack(await unwrap(http.GET('/documents/{doc_id}', { params: { path: { doc_id: id } } })))
            const pixels = new Map<string, LayerPixels>(); const masks = new Map<string, LayerPixels>()
            const rasters: Node[] = []; const masked: Node[] = []
            walk(doc.layers, (n) => { if (n.kind === 'raster') rasters.push(n); if (n.mask) masked.push(n) })   // masks sit on any node kind
            await Promise.all([
              ...rasters.map(async (n) => { const lp = await fetchRaw(id, n.id, 'image'); if (lp) pixels.set(n.id, lp) }),
              ...masked.map(async (n) => { const m = await fetchRaw(id, n.id, 'mask'); if (m) masks.set(n.id, m) }),
            ])
            if (seq !== openSeq) { pixels.forEach((p) => p.destroy()); masks.forEach((p) => p.destroy()); return }   // C31: another document was opened meanwhile
            const first = rasters[0]?.id ?? null
            // an AI candidate group left unpicked (several children, one visible) resumes its strip
            const top = doc.layers[0]
            const candidates = top?.kind === 'group' && top.name.startsWith('AI ') && (top.children?.length ?? 0) > 1 && top.children!.filter((c) => c.visible).length <= 1
              ? { group: top.id, ids: top.children!.map((c) => c.id) } : null
            set({ doc, pixels, masks, activeId: first, editingMask: false, docDirty: false, history: [], future: [], selection: null, quickMask: false, candidates, transform: null, revision: get().revision + 1 })
            get().requestFit()
          } catch (e) { if (seq === openSeq) set({ error: (e as ApiError).detail ?? (e as Error).message }) }
          finally { if (seq === openSeq) set({ loading: false }) }
        },
        openFromAsset: async (assetId) => {
          const s = useSession.getState()
          try {
            const existing = (await unwrap(http.GET('/documents'))).items.find((d) => d.source_asset_id === assetId)
            const doc = existing ?? asStack(await unwrap(http.POST('/documents', { body: { from_asset: assetId } })))
            s.setSuite('edit')
            await get().openDocument(doc.id)
            s.toast(existing ? 'Opened the asset\'s document' : 'Document created from the asset', 'success')
          } catch (e) { s.toast(`Open in Edit failed: ${(e as ApiError).detail ?? e}`, 'error') }
        },
        /** A Catalogue asset dropped on an open document becomes a new raster layer above the active one (10 §7 import). */
        addLayerFromAsset: async (assetId) => {
          const doc = get().doc
          if (!doc) { await get().openFromAsset(assetId); return }
          try {
            const b = useSession.getState().backend!
            const res = await fetch(`http://${b.host}:${b.port}/assets/${assetId}/file`, { headers: { 'X-Loom-Token': b.token } })
            if (!res.ok) throw new Error(`asset ${res.status}`)
            const bmp = await createImageBitmap(await res.blob())
            const node = get().addLayer('raster', { name: `import ${assetId.slice(-6)}`, lineage_asset_id: assetId, x: 0, y: 0, w: bmp.width, h: bmp.height })
            if (!node) return
            const lp = LayerPixels.fromImage(bmp); lp.dirty = true
            get().pixels.get(node.id)?.destroy(); get().pixels.set(node.id, lp)
            set({ revision: get().revision + 1 })
            useSession.getState().toast('Asset added as a layer', 'success')
          } catch (e) { useSession.getState().toast(`Could not add the asset: ${(e as Error).message}`, 'error') }
        },
        newDocument: async (w, h, name) => {
          try {
            const doc = asStack(await unwrap(http.POST('/documents', { body: { w, h, name: name ?? 'Untitled', background: 'transparent' } })))
            await get().openDocument(doc.id)
            get().addLayer('raster', { name: 'Layer 1' })
            set({ history: [], future: [] })
          } catch (e) { useSession.getState().toast(`New document failed: ${(e as ApiError).detail ?? e}`, 'error') }
        },
        closeDocument: () => {
          releaseEntries([...get().history, ...get().future])              // B19: swapped-out transform canvases
          get().pixels.forEach((p) => p.destroy()); get().masks.forEach((p) => p.destroy()); get().selection?.destroy()
          set({ doc: null, pixels: new Map(), masks: new Map(), selection: null, activeId: null, history: [], future: [], docDirty: false, error: null, candidates: null, transform: null })
        },
        listDocuments: async () => (await unwrap(http.GET('/documents'))).items,
        deleteDocument: async (id) => {
          if (get().doc?.id === id) get().closeDocument()
          await unwrap(http.DELETE('/documents/{doc_id}', { params: { path: { doc_id: id } } }))
          useSession.getState().toast('Document deleted', 'info')
        },

        save: async () => {
          const { doc, pixels, masks } = get()
          if (!doc) return false
          // B14: clear the flags *before* the uploads — a stroke that lands meanwhile re-dirties the document and its
          // layer and rides the next save; a failure below puts the document flag back
          set({ saving: true, docDirty: false })
          try {
            type Reply = DocumentStack & { missing_pixels: string[]; missing_masks: string[] }
            const put = async (s: DocumentStack): Promise<Reply> => {
              const r = await unwrap(http.PUT('/documents/{doc_id}', { params: { path: { doc_id: doc.id } }, body: asBody(s) }))
              return { ...asStack(r), missing_pixels: r.missing_pixels, missing_masks: r.missing_masks }
            }
            let stack = doc
            let server: Reply
            try { server = await put(stack) }
            catch (e) {
              if (!(e instanceof ApiError) || e.status !== 409) throw e
              await get().resync()                                 // C1: an AI result landed since this stack's revision — merge it, then save the merged stack
              const merged = get().doc
              if (!merged || merged.id !== doc.id) return false
              stack = merged
              server = await put(stack)
            }
            const rasters = new Set<string>(), masked = new Set<string>()
            walk(stack.layers, (n) => { if (n.kind === 'raster') rasters.add(n.id); if (n.mask) masked.add(n.id) })
            const upload = async (map: Map<string, LayerPixels>, kind: 'image' | 'mask', inStack: Set<string>, missing: string[] | undefined) => {
              const need = new Set(missing ?? [])
              for (const [lid, lp] of map) {
                if (!inStack.has(lid)) continue                      // B12: deleted here (kept for undo) and dropped by the server
                if (!lp.dirty && !need.has(lid)) continue            // B15: the server has no bytes for it → upload even when clean
                lp.dirty = false
                try { await putRaw(doc.id, lid, kind, lp) } catch (e) { lp.dirty = true; throw e }
              }
            }
            await upload(pixels, 'image', rasters, server.missing_pixels)
            await upload(masks, 'mask', masked, server.missing_masks)
            const saved = asStack(await unwrap(http.POST('/documents/{doc_id}/save', { params: { path: { doc_id: doc.id } } })))
            const cur = get().doc
            if (cur && cur.id === doc.id) set({ doc: { ...cur, saved_at: saved.saved_at, revision: saved.revision } })
            useSession.getState().toast('Saved', 'success')
            return true
          } catch (e) {
            set({ docDirty: true })
            useSession.getState().toast(`Save failed: ${(e as ApiError).detail ?? (e as Error).message}`, 'error')
            return false
          } finally { set({ saving: false }) }
        },
        resync: async () => {
          // B21: after a WebSocket reconnect, layers an AI job added while we were offline are merged like a live event
          const doc = get().doc
          if (!doc) return
          try {
            const server = asStack(await unwrap(http.GET('/documents/{doc_id}', { params: { path: { doc_id: doc.id } } })))
            const local = new Set<string>(); walk(doc.layers, (n) => { local.add(n.id) })
            const added: string[] = []
            walk(server.layers, (n) => { if (n.kind === 'raster' && !local.has(n.id)) added.push(n.id) })
            if (!added.length) {                                   // nothing new: just take the server's revision so the next save is accepted
              const cur = get().doc
              if (cur && cur.id === doc.id && cur.revision !== server.revision) set({ doc: { ...cur, revision: server.revision } })
              return
            }
            const group = server.layers.find((t) => t.kind === 'group' && t.children?.some((c) => added.includes(c.id)))?.id
            await get().mergeServerLayers(added, group)
          } catch { /* the next event or save reconciles */ }
        },
        saveToCatalogue: async () => {
          const { doc } = get()
          if (!doc) return
          if (!(await get().save())) return                          // the flatten runs on the saved document
          try {
            const r = await unwrap(http.POST('/documents/{doc_id}/flatten', { params: { path: { doc_id: doc.id } }, body: { to_catalogue: true } }))
            useSession.getState().toast('asset' in r ? `Saved to Catalogue as ${r.asset.id}` : 'Flattened', 'success')
          } catch (e) { useSession.getState().toast(`Save to Catalogue failed: ${(e as ApiError).detail ?? e}`, 'error') }
        },
        exportPng: async () => {
          const { doc } = get()
          if (!doc) return
          if (!(await get().save())) return
          const b = useSession.getState().backend!
          const res = await fetch(`http://${b.host}:${b.port}/documents/${doc.id}/export`, { method: 'POST', headers: { 'X-Loom-Token': b.token, 'Content-Type': 'application/json' }, body: JSON.stringify({ format: 'png' }) })
          if (!res.ok) { useSession.getState().toast(`Export failed: ${res.status}`, 'error'); return }
          download(await res.blob(), `${doc.name}.png`)
        },
        exportPsd: async () => {
          const { doc, pixels, masks, extractor } = get()
          if (!doc) return
          try {
            const { buildPsd } = await import('./psdExport')
            const merged = extractor?.() ?? undefined
            const { bytes, skipped, approximate } = buildPsd(doc, pixels, masks, merged)
            download(new Blob([bytes], { type: 'image/vnd.adobe.photoshop' }), `${doc.name}.psd`)
            const notes = [
              skipped.length ? `${skipped.length} filter layer${skipped.length > 1 ? 's' : ''} skipped (Photoshop has no filter layers; the merged image includes them): ${skipped.join(', ')}` : '',
              approximate.length ? `Photoshop renders ${approximate.join(', ')} with its own maths, slightly differently` : '',
            ].filter(Boolean)
            useSession.getState().toast(notes.length ? `PSD written. ${notes.join('. ')}` : 'PSD written', notes.length ? 'info' : 'success')
          } catch (e) { useSession.getState().toast(`PSD export failed: ${(e as Error).message}`, 'error') }
        },

        // ---- tools / view ------------------------------------------------------------------------
        setTool: (tool) => set({ tool }),
        setBrush: (p) => set({ brush: { ...get().brush, ...p } }),
        brushPresets: [],
        saveBrushPreset: (name) => { const b = get().brush; const p: BrushPreset = { name, size: b.size, hardness: b.hardness, opacity: b.opacity, flow: b.flow, spacing: b.spacing, smoothing: b.smoothing }
          set({ brushPresets: [...get().brushPresets.filter((x) => x.name !== name), p] }) },
        deleteBrushPreset: (name) => set({ brushPresets: get().brushPresets.filter((x) => x.name !== name) }),
        applyBrushPreset: (p) => set({ brush: { ...get().brush, size: p.size, hardness: p.hardness, opacity: p.opacity, flow: p.flow, spacing: p.spacing, smoothing: p.smoothing } }),
        setView: (p) => set(p),
        requestFit: () => set({ fitRequested: get().fitRequested + 1 }),
        zoomTo: (z) => {
          const { doc, zoom, pan } = get()
          z = Math.max(0.02, Math.min(64, z))
          if (!doc) { set({ zoom: z }); return }
          const cx = pan.x + (doc.w / 2) * zoom, cy = pan.y + (doc.h / 2) * zoom
          set({ zoom: z, pan: { x: cx - (doc.w / 2) * z, y: cy - (doc.h / 2) * z } })
        },
        setRenderer: (renderer) => set({ renderer }),
        setRendererPref: (p) => set({ rendererPref: p, rendererEpoch: get().rendererEpoch + 1 }),   // the canvas remounts on the epoch
        setCursor: (cursor) => set({ cursor }),
        setExtractor: (extractor) => set({ extractor }),

        // ---- stack -----------------------------------------------------------------------------------
        setActive: (id, mask) => {
          const n = findNode(get().doc, id)
          const editing = !!n?.mask && (mask ?? (n.kind === 'adjustment' || n.kind === 'filter' ? true : get().editingMask))
          set({ activeId: id, editingMask: editing, ...(editing && !get().editingMask ? maskEditExtras(get().tool) : {}),
            ...(id && get().selectedIds.includes(id) ? {} : { selectedIds: id ? [id] : [], anchorId: id }) })
        },
        selectLayer: (id, how = 'replace') => {
          const { doc, activeId } = get()
          if (!doc || !findNode(doc, id)) return
          const cur = activeId && get().selectedIds.includes(activeId) ? get().selectedIds : activeId ? [activeId] : []
          if (how === 'toggle' && cur.includes(id)) {
            if (cur.length < 2) return                                   // the selection keeps at least the clicked layer
            const next = cur.filter((x) => x !== id)
            set({ selectedIds: next, anchorId: id })
            if (activeId === id) get().setActive(next[next.length - 1])
            return
          }
          if (how === 'toggle') { set({ selectedIds: [...cur, id], anchorId: id }); get().setActive(id); return }
          if (how === 'range') {
            const order = walkOrder(doc), a = order.indexOf(get().anchorId ?? activeId ?? id), b = order.indexOf(id)
            const [i, j] = a < 0 ? [b, b] : [Math.min(a, b), Math.max(a, b)]
            set({ selectedIds: order.slice(i, j + 1) })
            get().setActive(id)
            return
          }
          set({ selectedIds: [id], anchorId: id })
          get().setActive(id)
        },
        targetIds: () => {
          const { doc, activeId, selectedIds } = get()
          if (!doc || !activeId) return []
          const sel = selectedIds.filter((x) => findNode(doc, x))
          const ids = sel.length > 1 && sel.includes(activeId) ? sel : [activeId]
          const order = walkOrder(doc)
          return topLevel(doc, ids).sort((p, q) => order.indexOf(p) - order.indexOf(q))
        },
        deleteNodes: (ids) => {
          const doc = get().doc
          if (!doc || !ids.length) return
          if (ids.length === 1) { get().deleteNode(ids[0]); return }
          const before = clone(doc)
          const next = clone(doc)
          const order = walkOrder(doc), gone = new Set(ids)
          const firstAt = Math.min(...ids.map((x) => order.indexOf(x)))
          for (const id of ids) { const p = findParent(next, id); if (p) p.list.splice(p.index, 1) }
          const left = walkOrder(next)
          const nextActive = order.slice(firstAt).find((x) => !gone.has(x) && left.includes(x)) ?? left[0] ?? null
          commit(next, before, `delete ${ids.length} layers`, ids[0], { activeId: nextActive, editingMask: false, selectedIds: nextActive ? [nextActive] : [], anchorId: nextActive })
        },
        duplicateNodes: (ids) => {
          const doc = get().doc
          if (!doc || !ids.length) return
          const before = clone(doc)
          const next = clone(doc)
          const copies: string[] = []
          for (const id of ids) {
            const p = findParent(next, id)
            if (!p) continue
            const c = copyNode(p.list[p.index], get().pixels, get().masks, ids.length === 1)
            p.list.splice(p.index, 0, c)                               // above its original
            copies.push(c.id)
          }
          const act = copies[ids.indexOf(get().activeId ?? '')] ?? copies[0]
          commit(next, before, ids.length > 1 ? `duplicate ${ids.length} layers` : 'duplicate layer', act, { activeId: act, selectedIds: copies, anchorId: act, editingMask: false })
        },
        groupNodes: (idsIn) => {
          const doc = get().doc
          if (!doc || !idsIn.length) return
          const order = walkOrder(doc)
          const ids = topLevel(doc, idsIn).sort((p, q) => order.indexOf(p) - order.indexOf(q))
          const before = clone(doc)
          const next = clone(doc)
          const nodes = ids.map((x) => findNode(next, x)).filter(Boolean) as Node[]
          const group: Node = { kind: 'group', id: newId('grp'), name: 'Group', opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, passthrough: true, children: nodes }
          const top = findParent(next, ids[0])!
          top.list.splice(top.index, 1, group)                           // the group takes the topmost layer's place
          // the others leave their old places (the walk skips the new group, which now holds them)
          const strip = (list: Node[]) => { for (let i = list.length - 1; i >= 0; i--) { const n = list[i]; if (n === group) continue; if (ids.includes(n.id)) list.splice(i, 1); else if (n.children) strip(n.children) } }
          strip(next.layers)
          commit(next, before, ids.length > 1 ? `group ${ids.length} layers` : 'group', group.id, { activeId: group.id, selectedIds: [group.id], anchorId: group.id, editingMask: false })
        },
        mergeNodes: (ids) => {
          const doc = get().doc
          if (!doc || !ids.length) return
          if (ids.length === 1) { get().mergeDown(ids[0]); return }
          const nodes = ids.map((x) => findNode(doc, x)).filter(Boolean) as Node[]
          if (nodes.some((n) => n.kind !== 'raster')) { useSession.getState().toast('Merge layers merges raster layers only — rasterise or deselect the others', 'info'); return }
          const shown = nodes.filter((n) => n.visible)                   // hidden layers are discarded (Photoshop, PhotoCraft)
          if (!shown.length) { useSession.getState().toast('All the selected layers are hidden', 'info'); return }
          const base = shown[shown.length - 1]                            // the bottom visible layer keeps its place and id
          const x0 = Math.min(...shown.map((n) => n.x ?? 0)), y0 = Math.min(...shown.map((n) => n.y ?? 0))
          const x1 = Math.max(...shown.map((n) => (n.x ?? 0) + (n.w ?? 0))), y1 = Math.max(...shown.map((n) => (n.y ?? 0) + (n.h ?? 0)))
          const out = new LayerPixels(x1 - x0, y1 - y0)
          for (const n of [...shown].reverse()) {                        // bottom to top, isolated (like merge down: canvas blends)
            const lp = get().pixels.get(n.id)
            if (!lp) continue
            let src: HTMLCanvasElement = lp.canvas
            const m = n.mask?.enabled ? get().masks.get(n.id) : undefined
            if (m && n.mask) {
              const tmp = document.createElement('canvas'); tmp.width = lp.width; tmp.height = lp.height
              const tc = tmp.getContext('2d')!
              tc.drawImage(lp.canvas, 0, 0); tc.globalCompositeOperation = 'destination-in'
              const off = maskOffset(n)
              tc.drawImage(maskAlphaCanvas(m, n.mask, off.x, off.y, n.x ?? 0, n.y ?? 0, lp.width, lp.height), 0, 0)
              src = tmp
            }
            out.ctx.save()
            out.ctx.globalAlpha = n.opacity * (n.fill ?? 1)
            out.ctx.globalCompositeOperation = n === base ? 'source-over' : canvasBlend(n.blend)
            out.ctx.drawImage(src, (n.x ?? 0) - x0, (n.y ?? 0) - y0)
            out.ctx.restore()
          }
          out.refresh(); out.dirty = true
          const before = clone(doc)
          const next = clone(doc)
          for (const n of nodes) if (n.id !== base.id) { const p = findParent(next, n.id); if (p) p.list.splice(p.index, 1) }
          walk(next.layers, (n) => { if (n.id === base.id) { Object.assign(n, { x: x0, y: y0, w: x1 - x0, h: y1 - y0, opacity: 1, fill: 1, blend: 'normal', mask: null, clip: false, name: nodes[0].name }); return true } })
          const old = get().pixels.get(base.id)!, oldMask = base.mask ? get().masks.get(base.id) ?? null : null
          get().pixels.set(base.id, out)
          set({ doc: next, activeId: base.id, selectedIds: [base.id], anchorId: base.id, editingMask: false, docDirty: true, revision: get().revision + 1 })
          get().pushHistory({ label: `merge ${nodes.length} layers`, layerId: base.id, kind: 'image', tiles: [], stack: before, at: Date.now(), swap: { layerId: base.id, lp: old, mask: oldMask } })
        },
        setPropsFor: (ids, patch, label) => {
          const doc = get().doc
          if (!doc || !ids.length) return
          const before = clone(doc)
          const next = clone(doc)
          const set1 = new Set(ids)
          walk(next.layers, (n) => { if (set1.has(n.id)) Object.assign(n, patch) })
          commit(next, before, label, ids[0])
        },
        moveNodesTo: (ids, targetId, where, copy = false) => {
          const doc = get().doc
          if (!doc || !ids.length) return
          const moving = topLevel(doc, ids)
          if (moving.includes(targetId) && (!copy || where === 'into')) return     // dropped on itself
          // the destination (the group for 'into', else the target's parent) and its ancestors must not be among the moved layers
          const pm = parentMap(doc)
          for (let p = where === 'into' ? targetId : pm.get(targetId) ?? null; p; p = pm.get(p) ?? null) {
            if (moving.includes(p)) { useSession.getState().toast('A group cannot go inside itself', 'info'); return }
          }
          const before = clone(doc)
          const next = clone(doc)
          let nodes = moving.map((x) => findNode(next, x)!).filter(Boolean)
          if (copy) nodes = nodes.map((n) => copyNode(n, get().pixels, get().masks, false))
          else for (const id of moving) { const p = findParent(next, id); if (p) p.list.splice(p.index, 1) }
          const t = findNode(next, targetId), tp = findParent(next, targetId)
          if (!t || !tp) return
          if (where === 'into' && t.kind === 'group') t.children = [...nodes, ...(t.children ?? [])]
          else tp.list.splice(where === 'above' ? tp.index : tp.index + 1, 0, ...nodes)
          const ids2 = nodes.map((n) => n.id)
          commit(next, before, copy ? (ids2.length > 1 ? `duplicate ${ids2.length} layers` : 'duplicate layer') : 'reorder layers', ids2[0],
            copy ? { activeId: ids2[0], selectedIds: ids2, anchorId: ids2[0] } : {})
        },
        updateNode: (id, patch, label, coalesce) => {
          const doc = get().doc
          if (!doc) return
          const before = clone(doc)
          const next = clone(doc)
          walk(next.layers, (n) => { if (n.id === id) { Object.assign(n, patch); return true } })
          if (label) commit(next, before, label, id, {}, coalesce)
          else set({ doc: next, docDirty: true, revision: get().revision + 1 })
        },
        addLayer: (kind = 'raster', extra = {}) => {
          const doc = get().doc
          if (!doc) return null
          const before = clone(doc)
          const type = extra.type ?? (kind === 'adjustment' ? 'levels' : 'gaussian_blur')
          const node: Node = { kind, id: newId('lyr'), name: extra.name ?? (kind === 'raster' ? `Layer ${countRasters(doc) + 1}` : kind === 'group' ? 'Group' : type.replace('_', ' ')),
            opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, ...(kind === 'raster' ? { x: 0, y: 0, w: doc.w, h: doc.h, fill: 1 } : {}),
            ...(kind === 'group' ? { passthrough: true, children: [] } : {}), ...(kind === 'adjustment' ? { type, params: extra.params ?? clone(ADJUSTMENT_DEFAULTS[type] ?? {}) } : {}),
            ...(kind === 'filter' ? { type, params: extra.params ?? clone(FILTER_DEFAULTS[type] ?? {}) } : {}), ...extra }
          const next = clone(doc)
          const at = get().activeId ? findParent(next, get().activeId!) : null
          if (at) at.list.splice(at.index, 0, node); else next.layers.unshift(node)
          if (kind === 'raster') { const lp = new LayerPixels(doc.w, doc.h); lp.dirty = true; get().pixels.set(node.id, lp) }
          commit(next, before, `add ${node.name}`, node.id, { activeId: node.id, editingMask: false })
          return node
        },
        deleteNode: (id) => {
          const doc = get().doc
          if (!doc) return
          const before = clone(doc)
          const next = clone(doc)
          const p = findParent(next, id)
          if (!p) return
          p.list.splice(p.index, 1)
          const nextActive = p.list[p.index]?.id ?? p.list[p.index - 1]?.id ?? next.layers[0]?.id ?? null
          commit(next, before, 'delete layer', id, { activeId: nextActive, editingMask: false })
        },
        duplicateNode: (id) => {
          const doc = get().doc
          const n = findNode(doc, id)
          if (!doc || !n) return
          const before = clone(doc)
          const copy: Node = { ...clone(n), id: newId('lyr'), name: `${n.name} copy` }
          if (n.kind === 'raster') { const src = get().pixels.get(id); if (src) { const lp = new LayerPixels(src.width, src.height); lp.ctx.drawImage(src.canvas, 0, 0); lp.refresh(); lp.dirty = true; get().pixels.set(copy.id, lp) } }
          if (n.mask) { const m = get().masks.get(id); if (m) { const lp = new LayerPixels(m.width, m.height, true); lp.ctx.drawImage(m.canvas, 0, 0); lp.refresh(); lp.dirty = true; get().masks.set(copy.id, lp) } }
          const next = clone(doc)
          const p = findParent(next, id)!
          p.list.splice(p.index, 0, copy)
          commit(next, before, 'duplicate layer', copy.id, { activeId: copy.id })
        },
        moveNode: (id, dir) => {
          const doc = get().doc
          if (!doc) return
          const before = clone(doc)
          const next = clone(doc)
          const p = findParent(next, id)
          if (!p) return
          const j = dir === 'up' ? p.index - 1 : p.index + 1
          if (j < 0 || j >= p.list.length) return
          const [n] = p.list.splice(p.index, 1); p.list.splice(j, 0, n)
          commit(next, before, `move layer ${dir}`, id)
        },
        mergeDown: (id) => {
          const doc = get().doc
          if (!doc) return
          const p = findParent(doc, id)
          if (!p || p.index + 1 >= p.list.length) return
          const top = p.list[p.index], below = p.list[p.index + 1]
          if (top.kind !== 'raster' || below.kind !== 'raster') { useSession.getState().toast('Merge down needs two raster layers', 'info'); return }
          const a = get().pixels.get(top.id), b = get().pixels.get(below.id)
          if (!a || !b) return
          const before = clone(doc)
          const tiles = b.snapshotAll()
          b.ctx.save()
          b.ctx.globalAlpha = top.opacity * (top.fill ?? 1)
          b.ctx.globalCompositeOperation = canvasBlend(top.blend)
          const m = top.mask?.enabled ? get().masks.get(top.id) : undefined
          if (m) {
            // apply the mask to a copy of the top layer first
            const tmp = document.createElement('canvas'); tmp.width = a.width; tmp.height = a.height
            const tc = tmp.getContext('2d')!
            tc.drawImage(a.canvas, 0, 0)
            tc.globalCompositeOperation = 'destination-in'
            const off = maskOffset(top)
            tc.drawImage(maskAlphaCanvas(m, top.mask!, off.x, off.y, top.x ?? 0, top.y ?? 0, a.width, a.height), 0, 0)   // D52 / D54: as it renders
            b.ctx.drawImage(tmp, (top.x ?? 0) - (below.x ?? 0), (top.y ?? 0) - (below.y ?? 0))
          } else b.ctx.drawImage(a.canvas, (top.x ?? 0) - (below.x ?? 0), (top.y ?? 0) - (below.y ?? 0))
          b.ctx.restore()
          b.refresh(); b.dirty = true
          const next = clone(doc)
          findParent(next, id)!.list.splice(p.index, 1)
          set({ doc: next, activeId: below.id, editingMask: false, docDirty: true, revision: get().revision + 1 })
          get().pushHistory({ label: 'merge down', layerId: below.id, kind: 'image', tiles, stack: before, at: Date.now() })
        },
        groupActive: () => {
          const doc = get().doc
          const id = get().activeId
          if (!doc || !id) return
          const before = clone(doc)
          const next = clone(doc)
          const p = findParent(next, id)
          if (!p) return
          const [n] = p.list.splice(p.index, 1)
          const group: Node = { kind: 'group', id: newId('grp'), name: 'Group', opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, passthrough: true, children: [n] }
          p.list.splice(p.index, 0, group)
          commit(next, before, 'group', group.id, { activeId: group.id, editingMask: false })
        },
        solo: (id) => {
          const doc = get().doc
          if (!doc || !findParent(doc, id)) return
          const before = clone(doc)
          const next = clone(doc)
          const list = findParent(next, id)!.list
          const othersHidden = list.every((n) => n.id === id || !n.visible)
          for (const n of list) n.visible = othersHidden ? true : n.id === id
          commit(next, before, othersHidden ? 'show all' : 'solo', id)
        },
        addMask: (id, how = 'reveal') => {
          const doc = get().doc
          const n = findNode(doc, id)
          if (!doc || !n || n.mask) return
          const sel = get().selection
          if ((how === 'revealSelection' || how === 'hideSelection') && !sel) how = how === 'revealSelection' ? 'reveal' : 'hide'
          const before = clone(doc)
          // D52: a raster layer's mask is layer-sized and linked (it moves and transforms with the layer, Photoshop's default);
          // groups, adjustments and filters get a document-sized mask, unlinked at the document origin
          const px = n.kind === 'raster' ? get().pixels.get(id) : undefined
          const w = px?.width ?? doc.w, h = px?.height ?? doc.h
          const ox = px ? (n.x ?? 0) : 0, oy = px ? (n.y ?? 0) : 0
          const lp = new LayerPixels(w, h, true)
          // D54 (PhotoCraft): reveal all = white with default 255; hide all = black, default 0; reveal selection = the selection over
          // black, default 0; hide selection = white with the selection black, default 255. B16: the selection canvas is
          // transparent where nothing is selected, so its *alpha* (white = selected) is drawn
          const white = how === 'reveal' || how === 'hideSelection'
          lp.ctx.fillStyle = white ? '#ffffff' : '#000000'; lp.ctx.fillRect(0, 0, w, h)
          if (sel && how === 'revealSelection') lp.ctx.drawImage(selectionAlphaCanvas(sel), -ox, -oy)
          if (sel && how === 'hideSelection') {
            const a = selectionAlphaCanvas(sel), ac = a.getContext('2d')!
            ac.globalCompositeOperation = 'source-in'; ac.fillStyle = '#000000'; ac.fillRect(0, 0, a.width, a.height)
            lp.ctx.drawImage(a, -ox, -oy)
          }
          lp.refresh(); lp.dirty = true
          get().masks.set(id, lp)
          const next = clone(doc)
          walk(next.layers, (m) => { if (m.id === id) { m.mask = { enabled: true, linked: !!px, x: 0, y: 0, density: 1, feather: 0, default: white ? 255 : 0 }; return true } })
          const label = { reveal: 'add mask', hide: 'add mask (hide all)', revealSelection: 'mask from selection', hideSelection: 'mask hiding the selection' }[how]
          commit(next, before, label, id, { activeId: id, editingMask: true, ...maskEditExtras(get().tool) })
          if (how === 'hideSelection') get().deselect()                // PhotoCraft's Hide Selection drops the selection
        },
        removeMask: (id) => {
          const doc = get().doc
          if (!doc) return
          const before = clone(doc)
          const next = clone(doc)                                   // B18: the mask canvas stays for undo (gc drops it later)
          walk(next.layers, (m) => { if (m.id === id) { m.mask = null; return true } })
          commit(next, before, 'remove mask', id, { editingMask: false })
        },
        toggleMaskLink: (id) => {
          const doc = get().doc
          const n = findNode(doc, id)
          if (!doc || !n?.mask) return
          const before = clone(doc)
          const next = clone(doc)
          // D52: the mask stays where it is on the canvas; its offset converts between layer-relative (linked) and document coordinates
          walk(next.layers, (m) => {
            if (m.id !== id || !m.mask) return false
            const lx = m.x ?? 0, ly = m.y ?? 0
            m.mask = m.mask.linked ? { ...m.mask, linked: false, x: m.mask.x + lx, y: m.mask.y + ly } : { ...m.mask, linked: true, x: m.mask.x - lx, y: m.mask.y - ly }
            return true
          })
          commit(next, before, n.mask.linked ? 'unlink mask' : 'link mask', id)
        },
        applyMask: (id) => {
          const doc = get().doc
          const n = findNode(doc, id)
          const lp = n?.kind === 'raster' ? get().pixels.get(id) : undefined
          const m = n?.mask ? get().masks.get(id) : undefined
          if (!doc || !n?.mask || !lp || !m) { useSession.getState().toast('Apply mask needs a raster layer with a mask', 'info'); return }
          if (n.locked) { useSession.getState().toast('Layer is locked', 'info'); return }
          const before = clone(doc)
          const tiles = lp.snapshotAll()
          // D52: the layer's alpha × the mask as it renders (density, feather); outside the mask's extent nothing shows, as in compose.py
          const off = maskOffset(n)
          const a = maskAlphaCanvas(m, n.mask, off.x, off.y, n.x ?? 0, n.y ?? 0, lp.width, lp.height)   // D54: the default outside the extent
          lp.ctx.save(); lp.ctx.globalCompositeOperation = 'destination-in'; lp.ctx.drawImage(a, 0, 0); lp.ctx.restore()
          lp.refresh(); lp.dirty = true
          const next = clone(doc)
          walk(next.layers, (x) => { if (x.id === id) { x.mask = null; return true } })
          set({ doc: next, editingMask: false, docDirty: true, revision: get().revision + 1 })
          get().pushHistory({ label: 'apply mask', layerId: id, kind: 'image', tiles, stack: before, at: Date.now() })
        },
        maskFromTransparency: (id) => {
          const doc = get().doc
          const n = findNode(doc, id)
          const lp = n?.kind === 'raster' ? get().pixels.get(id) : undefined
          if (!doc || !n || !lp || n.mask) { useSession.getState().toast('Mask from transparency needs a raster layer without a mask', 'info'); return }
          if (n.locked) { useSession.getState().toast('Layer is locked', 'info'); return }
          const before = clone(doc)
          const tiles = lp.snapshotAll()
          // D52 (Photoshop Layer › Layer Mask › From Transparency): the alpha becomes a linked layer-sized mask, the layer turns opaque
          const img = lp.ctx.getImageData(0, 0, lp.width, lp.height)
          const mask = new LayerPixels(lp.width, lp.height, true)
          const mi = mask.ctx.createImageData(lp.width, lp.height)
          for (let j = 0; j < img.data.length; j += 4) { const a = img.data[j + 3]; mi.data[j] = mi.data[j + 1] = mi.data[j + 2] = a; mi.data[j + 3] = 255; img.data[j + 3] = 255 }
          mask.ctx.putImageData(mi, 0, 0); mask.refresh(); mask.dirty = true
          lp.ctx.putImageData(img, 0, 0); lp.refresh(); lp.dirty = true
          get().masks.set(id, mask)
          const next = clone(doc)
          walk(next.layers, (x) => { if (x.id === id) { x.mask = { enabled: true, linked: true, x: 0, y: 0, density: 1, feather: 0, default: 0 }; return true } })
          set({ doc: next, editingMask: true, docDirty: true, revision: get().revision + 1 })
          get().pushHistory({ label: 'mask from transparency', layerId: id, kind: 'image', tiles, stack: before, at: Date.now() })
        },
        resizeCanvas: (w, h, ax = 0.5, ay = 0.5) => {
          const doc = get().doc
          if (!doc) return
          setCanvas(Math.round(w), Math.round(h), Math.round((w - doc.w) * ax), Math.round((h - doc.h) * ay), 'canvas size')
        },
        cropToSelection: () => {
          const sel = get().selection
          if (!sel) return
          const d = selectionValues(sel)
          let x0 = sel.width, y0 = sel.height, x1 = -1, y1 = -1
          for (let y = 0; y < sel.height; y++) for (let x = 0; x < sel.width; x++) if (d[y * sel.width + x] > 127) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y }
          if (x1 < 0) return
          setCanvas(x1 - x0 + 1, y1 - y0 + 1, -x0, -y0, 'crop')
          get().clearSelection()
        },
        clearSelected: () => {
          const { doc, activeId, selection, editingMask } = get()
          const n = findNode(doc, activeId)
          if (!doc || !n || n.locked || (n.kind !== 'raster' && !(editingMask && n.mask))) return
          const lp = editingMask ? get().masks.get(n.id) : get().pixels.get(n.id)
          if (!lp) return
          const off = editingMask ? maskOffset(n) : { x: n.x ?? 0, y: n.y ?? 0 }
          lp.beginStroke(); lp.touch(0, 0, lp.width, lp.height)
          const ctx = lp.ctx
          ctx.save()
          const g = lumaOf(get().brush.background), bg = `rgb(${g}, ${g}, ${g})`   // D54: a mask clears to the background colour's grey
          if (selection) {
            const a = selectionAlphaCanvas(selection)                 // alpha = selected amount
            if (editingMask) { const tc = a.getContext('2d')!; tc.globalCompositeOperation = 'source-in'; tc.fillStyle = bg; tc.fillRect(0, 0, a.width, a.height); ctx.globalCompositeOperation = 'source-over' }
            else ctx.globalCompositeOperation = 'destination-out'
            ctx.drawImage(a, -off.x, -off.y)
          } else if (editingMask) { ctx.fillStyle = bg; ctx.fillRect(0, 0, lp.width, lp.height) }
          else ctx.clearRect(0, 0, lp.width, lp.height)
          ctx.restore()
          lp.refresh(); lp.dirty = true
          get().pushHistory({ label: 'clear', layerId: n.id, kind: editingMask ? 'mask' : 'image', tiles: lp.endStroke(), at: Date.now() })
          set({ docDirty: true, revision: get().revision + 1 })
        },

        // ---- history ---------------------------------------------------------------------------------
        pushHistory: (e) => {
          const h = get().history, f = get().future
          const last = h[h.length - 1]
          // D56: stack-only entries of one gesture merge across layers too (an eye sweep) — the oldest stack is the whole before-state
          const sameRow = last && (last.layerId === e.layerId || (!e.tiles.length && !last.tiles.length && !!e.stack && !!last.stack))
          if (e.coalesce && last && last.coalesce === e.coalesce && sameRow && e.at - last.at < 2000 && !e.swap && !last.swap) {
            // D43: one gesture, one row — the older entry already holds the before-state of its tiles; add the tiles it lacks
            const have = new Set(last.tiles.map((t) => `${t.x},${t.y}`))
            const merged: HistoryEntry = { ...last, at: e.at, tiles: [...last.tiles, ...e.tiles.filter((t) => !have.has(`${t.x},${t.y}`))], stack: last.stack ?? e.stack,
              sel: last.sel && e.sel ? { had: last.sel.had, has: e.sel.has } : last.sel ?? e.sel }
            set({ history: [...h.slice(0, -1), merged], future: [] })
            if (f.length) { releaseEntries(f); gcPixels() }
            return
          }
          const dropped = [...h.slice(0, Math.max(0, h.length - 199)), ...f]
          set({ history: [...h.slice(-199), e], future: [] })
          if (dropped.length) { releaseEntries(dropped); gcPixels() }      // B19: canvases only history referenced go with it
        },
        undo: () => {
          const h = get().history
          if (!h.length) return
          const e = h[h.length - 1]
          const redoEntry: HistoryEntry = { ...e, tiles: [], stack: e.stack && get().doc ? clone(get().doc!) : undefined, swap: undefined }
          if (e.tiles.length) {
            const target = e.layerId === 'selection' ? selectionFor(e) : e.kind === 'mask' ? get().masks.get(e.layerId) : get().pixels.get(e.layerId)
            if (target) redoEntry.tiles = target.restore(e.tiles)
          }
          if (e.sel) setSelectionPresence(e.sel.had)
          if (e.swap) redoEntry.swap = swapPixels(e.swap)
          if (e.stack) set({ doc: keepServerState(e.stack, get().doc), activeId: findNode(e.stack, get().activeId) ? get().activeId : e.stack.layers[0]?.id ?? null })
          set({ history: h.slice(0, -1), future: [...get().future, redoEntry], docDirty: true, transform: null, revision: get().revision + 1 })
        },
        redo: () => {
          const f = get().future
          if (!f.length) return
          const e = f[f.length - 1]
          const undoEntry: HistoryEntry = { ...e, tiles: [], stack: e.stack && get().doc ? clone(get().doc!) : undefined, swap: undefined }
          if (e.tiles.length) {
            const target = e.layerId === 'selection' ? selectionFor(e) : e.kind === 'mask' ? get().masks.get(e.layerId) : get().pixels.get(e.layerId)
            if (target) undoEntry.tiles = target.restore(e.tiles)
          }
          if (e.sel) setSelectionPresence(e.sel.has)
          if (e.swap) undoEntry.swap = swapPixels(e.swap)
          if (e.stack) set({ doc: keepServerState(e.stack, get().doc), activeId: findNode(e.stack, get().activeId) ? get().activeId : e.stack.layers[0]?.id ?? null })
          set({ future: f.slice(0, -1), history: [...get().history, undoEntry], docDirty: true, transform: null, revision: get().revision + 1 })
        },
        touch: () => set({ docDirty: true }),
        bump: () => set({ revision: get().revision + 1 }),

        // ---- selection (a document-sized grey canvas; white = selected) --------------------------------
        ensureSelection: () => {
          const doc = get().doc!
          let sel = get().selection
          if (!sel) { sel = new LayerPixels(doc.w, doc.h, true); set({ selection: sel }) }
          return sel
        },
        clearSelection: () => { get().selection?.destroy(); set({ selection: null, quickMask: false, revision: get().revision + 1 }) },
        editSelection: (label, fn, coalesce) => {
          const doc = get().doc
          if (!doc) return
          const prev = get().selection
          const beforeImg = prev ? prev.ctx.getImageData(0, 0, prev.width, prev.height) : null
          const before = prev ? selectionValues(prev) : null
          fn()
          const cur = get().selection
          const after = cur ? selectionValues(cur) : null
          const sameSize = (!prev || (prev.width === doc.w && prev.height === doc.h)) && (!cur || (cur.width === doc.w && cur.height === doc.h))
          const tiles = sameSize ? changedTiles(doc.w, doc.h, before, after, beforeImg) : []
          if (sameSize && (tiles.length || !!prev !== !!cur)) get().pushHistory({ label, layerId: 'selection', kind: 'image', tiles, at: Date.now(), sel: { had: !!prev, has: !!cur }, coalesce })
          set({ revision: get().revision + 1 })
        },
        applySelectionShape: (shape, mode, label, featherPx = 0) => {
          const doc = get().doc
          if (!doc || shape.length !== doc.w * doc.h) return
          const s = featherPx > 0 ? feather(shape, doc.w, doc.h, featherPx) : shape
          get().editSelection(label, () => {
            const cur = get().selection ? selectionValues(get().selection!) : null
            writeSelection(get().ensureSelection(), combine(cur, s, mode))
          })
        },
        selectLayerAlpha: (id) => {
          const doc = get().doc
          const n = findNode(doc, id)
          const lp = n?.kind === 'raster' ? get().pixels.get(n.id) : null
          if (!doc || !n || !lp) { useSession.getState().toast('Layer transparency needs a raster layer', 'info'); return }
          const c = document.createElement('canvas'); c.width = doc.w; c.height = doc.h
          const cx = c.getContext('2d', { willReadFrequently: true })!
          cx.drawImage(lp.canvas, n.x ?? 0, n.y ?? 0)
          const d = cx.getImageData(0, 0, doc.w, doc.h).data
          const shape = new Uint8Array(doc.w * doc.h)
          for (let i = 0, j = 3; i < shape.length; i++, j += 4) shape[i] = d[j]
          get().applySelectionShape(shape, 'replace', `select "${n.name}" transparency`)
        },
        setLassoPoly: (pts) => set({ lassoPoly: pts, revision: get().revision + 1 }),
        setRefineEdge: (p) => set({ refineEdge: p === null ? {} : { ...get().refineEdge, ...p } }),
        copySelection: (opts = {}) => {
          const { doc, selection } = get()
          const s = useSession.getState()
          if (!doc) return false
          const n = findNode(doc, get().activeId)
          let src: HTMLCanvasElement | null = null, ox = 0, oy = 0
          if (opts.merged) src = get().extractor?.() ?? null
          else if (n?.kind === 'raster') { src = get().pixels.get(n.id)?.canvas ?? null; ox = n.x ?? 0; oy = n.y ?? 0 }
          if (!src) { s.toast(opts.merged ? 'The composite is not available yet' : 'Copy needs a raster layer (or Copy merged)', 'info'); return false }
          // the region: the selection's bounding box (or the whole source) within the source
          let x0 = ox, y0 = oy, x1 = ox + src.width, y1 = oy + src.height
          const v = selection ? selectionValues(selection) : null
          if (v) {
            let bx0 = doc.w, by0 = doc.h, bx1 = -1, by1 = -1
            for (let y = 0; y < doc.h; y++) for (let x = 0; x < doc.w; x++) if (v[y * doc.w + x]) { if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; if (y < by0) by0 = y; if (y > by1) by1 = y }
            if (bx1 < 0) { s.toast('The selection is empty', 'info'); return false }
            x0 = Math.max(x0, bx0); y0 = Math.max(y0, by0); x1 = Math.min(x1, bx1 + 1); y1 = Math.min(y1, by1 + 1)
          }
          if (x1 <= x0 || y1 <= y0) { s.toast('Nothing selected on this layer', 'info'); return false }
          const out = document.createElement('canvas'); out.width = x1 - x0; out.height = y1 - y0
          const cx = out.getContext('2d')!
          cx.drawImage(src, ox - x0, oy - y0)
          if (selection) { cx.globalCompositeOperation = 'destination-in'; cx.drawImage(selectionAlphaCanvas(selection), -x0, -y0) }  // soft selections copy soft
          set({ clipboard: { canvas: out, x: x0, y: y0 } })
          // mirrored to the OS clipboard as PNG (best effort: WebView2 may refuse); its size tells a later paste whether it is ours
          out.toBlob((blob) => {
            if (!blob) return
            osClipboardSize = blob.size
            try { void navigator.clipboard?.write?.([new ClipboardItem({ 'image/png': blob })]).catch(() => undefined) } catch { /* no async clipboard */ }
          }, 'image/png')
          if (opts.cut) get().clearSelected()
          s.toast(`${opts.cut ? 'Cut' : 'Copied'} ${out.width}×${out.height} px${opts.merged ? ' (merged)' : ''}`, 'info')
          return true
        },
        addImageLayer: (img, name, at, lineage) => {
          const doc = get().doc
          if (!doc) return null
          const x = at ? Math.round(at.x) : Math.round((doc.w - img.width) / 2), y = at ? Math.round(at.y) : Math.round((doc.h - img.height) / 2)
          const node = get().addLayer('raster', { name, x, y, w: img.width, h: img.height, ...(lineage ? { lineage_asset_id: lineage } : {}) })
          if (!node) return null
          const lp = new LayerPixels(img.width, img.height)
          lp.ctx.drawImage(img, 0, 0); lp.refresh(); lp.dirty = true
          get().pixels.get(node.id)?.destroy(); get().pixels.set(node.id, lp)
          set({ revision: get().revision + 1 })
          return node.id
        },
        pasteClipboard: async (inPlace = false) => {
          const s = useSession.getState()
          if (!get().doc) return
          if (!inPlace) {
            try {                                                         // an image copied in another app wins over our own clipboard
              for (const item of (await navigator.clipboard.read())) {
                const type = item.types.find((t) => t.startsWith('image/'))
                if (!type) continue
                const blob = await item.getType(type)
                if (blob.size === osClipboardSize && get().clipboard) break   // our own copy: paste it with what we know
                get().addImageLayer(await createImageBitmap(blob), 'Pasted image')
                return
              }
            } catch { /* permission refused or no async clipboard: the editor's own clipboard */ }
          }
          const c = get().clipboard
          if (!c) { s.toast('Nothing to paste: copy a selection first (Ctrl+C), or paste an image with Ctrl+V', 'info'); return }
          get().addImageLayer(c.canvas, inPlace ? 'Pasted in place' : 'Pasted', inPlace ? { x: c.x, y: c.y } : undefined)
        },
        pasteFromEvent: async (files) => {
          if (!get().doc) return
          const img = files.find((f) => f.type.startsWith('image/'))
          if (img && !(img.size === osClipboardSize && get().clipboard)) { get().addImageLayer(await createImageBitmap(img), 'Pasted image'); return }
          await get().pasteClipboard(false)
        },
        layerVia: (cut) => {
          const n = findNode(get().doc, get().activeId)
          if (n?.kind !== 'raster' || !get().selection) { useSession.getState().toast(`Layer via ${cut ? 'cut' : 'copy'} needs a selection on a raster layer`, 'info'); return }
          if (!get().copySelection({ cut })) return
          const c = get().clipboard!
          get().addImageLayer(c.canvas, `${n.name} (${cut ? 'cut' : 'copy'})`, { x: c.x, y: c.y })
        },
        inkFromWhite: () => {
          const n = findNode(get().doc, get().activeId)
          const lp = n?.kind === 'raster' && !n.locked ? get().pixels.get(n.id) : null
          if (!n || !lp) { useSession.getState().toast('Ink from white needs an unlocked raster layer', 'info'); return }
          lp.beginStroke(); lp.touch(0, 0, lp.width, lp.height)
          const img = lp.ctx.getImageData(0, 0, lp.width, lp.height)
          unmixWhite(img.data)
          lp.ctx.putImageData(img, 0, 0); lp.refresh(); lp.dirty = true
          get().pushHistory({ label: 'ink from white', layerId: n.id, kind: 'image', tiles: lp.endStroke(), at: Date.now() })
          set({ docDirty: true, revision: get().revision + 1 })
        },
        dropFiles: async (paths) => {
          const s = useSession.getState()
          if (!get().doc || !paths.length) return
          try {                                                           // D46: through the Catalogue first, so the layer has lineage
            const r = await unwrap(http.POST('/assets/import', { body: { paths } }))
            for (const a of r.items) await get().addLayerFromAsset(a.id)
            void s.refreshAll()
          } catch (e) { s.toast(`Could not import: ${(e as ApiError).detail ?? (e as Error).message}`, 'error') }
        },
        refineParams: () => {
          const d = useSession.getState().capabilities?.refine_edge?.defaults
          return { radius: 10, smart_radius: true, smooth: 0, feather: 0, contrast: 0, shift_edge: 0, ...(d ?? {}), ...get().refineEdge } as RefineEdgeParams
        },
        refineSelection: async () => {
          const { doc, selection } = get()
          const s = useSession.getState()
          if (!doc || !selection) { s.toast('Refine Edge needs a selection', 'info'); return }
          try {
            if (!(await get().save())) return                               // the guide is the server's exact composite
            await uploadSelection()
            const r = await unwrap(http.POST('/documents/{doc_id}/selection/refine', { params: { path: { doc_id: doc.id } }, body: get().refineParams() }))
            await get().loadSelectionFromServer('refine edge')
            s.toast(`Edge refined in ${(r.ms / 1000).toFixed(1)} s`, 'success')
          } catch (e) { s.toast(`Refine Edge failed: ${(e as ApiError).detail ?? (e as Error).message}`, 'error') }
        },
        closeLassoPoly: (mode) => {
          const doc = get().doc, pts = get().lassoPoly
          set({ lassoPoly: null })
          if (!doc || !pts || pts.length < 3) { set({ revision: get().revision + 1 }); return }
          const c = document.createElement('canvas'); c.width = doc.w; c.height = doc.h
          const cx = c.getContext('2d', { willReadFrequently: true })!
          cx.fillStyle = '#ffffff'; cx.beginPath(); cx.moveTo(pts[0].x, pts[0].y); for (const q of pts.slice(1)) cx.lineTo(q.x, q.y); cx.closePath(); cx.fill()
          const d = cx.getImageData(0, 0, doc.w, doc.h).data
          const shape = new Uint8Array(doc.w * doc.h)
          for (let i = 0, j = 3; i < shape.length; i++, j += 4) shape[i] = d[j]
          get().applySelectionShape(shape, mode ?? get().selectionMode, 'polygonal lasso', get().marqueeFeather)
        },
        deselect: () => { if (get().selection) get().editSelection('deselect', () => get().clearSelection()) },
        selectAll: () => get().editSelection('select all', () => { const sel = get().ensureSelection(); sel.ctx.fillStyle = '#ffffff'; sel.ctx.fillRect(0, 0, sel.width, sel.height); sel.refresh() }),
        invertSelection: () => get().editSelection('invert selection', () => {
          const sel = get().ensureSelection()
          const v = selectionValues(sel)
          for (let i = 0; i < v.length; i++) v[i] = 255 - v[i]
          writeSelection(sel, v)
        }),
        featherSelection: (px) => get().modifySelection('feather', px),
        modifySelection: (op, px) => {
          const sel = get().selection
          if (!sel || !(px > 0)) return
          get().editSelection(`${op} selection ${px} px`, () => {
            const v = selectionValues(sel)
            const fn = { expand, contract, border, smooth, feather }[op]
            writeSelection(sel, fn(v, sel.width, sel.height, px))
          })
        },
        loadSelectionFromMask: () => {
          const n = findNode(get().doc, get().activeId)
          const m = n?.mask ? get().masks.get(n.id) : null
          if (!n || !m) { useSession.getState().toast('The active layer has no mask', 'info'); return }
          get().editSelection('load mask as selection', () => {
            const sel = get().ensureSelection()
            const off = maskOffset(n)
            sel.ctx.fillStyle = '#000000'; sel.ctx.fillRect(0, 0, sel.width, sel.height)
            sel.ctx.drawImage(m.canvas, off.x, off.y)
            sel.refresh()
          })
        },
      }
    },
    { name: 'loom2.edit',
      // D54: the image pair is stored as `brush`, the mask pair as `maskColours`, whichever is live
      merge: (p, c) => { const q = (p ?? {}) as Partial<EditorState> & { maskColours?: { color: string; background: string } }; return { ...c, ...q, otherColours: q.maskColours ?? c.otherColours } },
      partialize: (s) => ({ tool: s.tool, brush: s.maskPairActive ? { ...s.brush, ...s.otherColours } : s.brush, maskColours: s.maskPairActive ? { color: s.brush.color, background: s.brush.background } : s.otherColours, overlay: s.overlay, pixelGrid: s.pixelGrid, tolerance: s.tolerance, fillMode: s.fillMode, rendererPref: s.rendererPref, brushPresets: s.brushPresets,
      marqueeFeather: s.marqueeFeather, marqueeStyle: s.marqueeStyle, marqueeW: s.marqueeW, marqueeH: s.marqueeH, lassoKind: s.lassoKind, wandContiguous: s.wandContiguous, wandMerged: s.wandMerged, wandAA: s.wandAA, selModifyPx: s.selModifyPx, refineEdge: s.refineEdge }) as never },
  ),
)

/** D54 (PhotoCraft sync_mask_targets / ToolState::target_mask): the mask target needs a mask (undo, delete, another layer clear it);
 * the grey view forces it; and the colour pairs swap whenever the live target changes between pixels and a mask (or Quick Mask). */
useEditor.subscribe((s) => {
  const n = findNode(s.doc, s.activeId)
  const patch: Partial<EditorState> = {}
  if (s.editingMask && !n?.mask) patch.editingMask = false
  if (s.maskView !== 'off' && !n?.mask) patch.maskView = 'off'
  if (s.maskView === 'gray' && n?.mask && !s.editingMask) patch.editingMask = true
  const editing = patch.editingMask ?? s.editingMask
  const want = (editing && !!n?.mask) || s.quickMask
  if (want !== s.maskPairActive) {
    patch.brush = { ...s.brush, color: s.otherColours.color, background: s.otherColours.background }
    patch.otherColours = { color: s.brush.color, background: s.brush.background }
    patch.maskPairActive = want
  }
  if (Object.keys(patch).length) useEditor.setState(patch)
})

/** B20: autosave (10 §7) and the unsaved-changes toast (10 §12) run for the app's lifetime, not only while the Edit strip is mounted. */
let autosaveStarted = false
export function ensureEditorAutosave(): void {
  if (autosaveStarted) return
  autosaveStarted = true
  setInterval(() => { const st = useEditor.getState(); if (st.doc && st.docDirty && !st.saving) void st.save() }, 120_000)
  useSession.subscribe((s, prev) => { if (prev.ui.suite === 'edit' && s.ui.suite !== 'edit' && useEditor.getState().docDirty) s.toast('Unsaved changes in Edit — autosave runs every 2 min, Ctrl+S saves now', 'info') })
}

/** Canvas2D composite op for merge-down (the exact set lives in Python; this covers the common modes). */
export function canvasBlend(mode: string): GlobalCompositeOperation {
  const map: Record<string, GlobalCompositeOperation> = { normal: 'source-over', multiply: 'multiply', screen: 'screen', overlay: 'overlay', darken: 'darken', lighten: 'lighten',
    'color-dodge': 'color-dodge', 'color-burn': 'color-burn', 'hard-light': 'hard-light', 'soft-light': 'soft-light', difference: 'difference', exclusion: 'exclusion',
    hue: 'hue', saturation: 'saturation', color: 'color', luminosity: 'luminosity' }
  return map[mode] ?? 'source-over'
}

export { walk }
