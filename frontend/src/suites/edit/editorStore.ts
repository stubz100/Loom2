// Edit suite state (10): the open document (stack + pixels), view, tools and options, selection, history,
// and persistence against /documents. Pixels live in LayerPixels (canvas + texture); the store holds references.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, ApiError } from '../../api/client'
import { useSession } from '../../store/session'
import { LayerPixels, selectionAlphaCanvas, type TileSnapshot } from './layerPixels'
import { isIdentity, resample, type Xform } from './transform'

export type NodeKind = 'raster' | 'group' | 'adjustment' | 'filter'
export interface MaskRef { enabled: boolean; linked: boolean; x: number; y: number }
export interface Node {
  kind: NodeKind; id: string; name: string; opacity: number; blend: string; visible: boolean; locked: boolean; clip: boolean; mask: MaskRef | null
  x?: number; y?: number; w?: number; h?: number; fill?: number; recipe?: Record<string, unknown> | null; lineage_asset_id?: string | null
  passthrough?: boolean; children?: Node[]
  type?: string; params?: Record<string, unknown>
}
export interface DocumentStack {
  schema_version: number; id: string; name: string; w: number; h: number; background: string; source_asset_id: string | null
  created_at: string; saved_at: string | null; revision: number; layers: Node[]; has_selection: boolean; meta: Record<string, unknown>
}
export interface DocSummary { id: string; name: string; w: number; h: number; saved_at: string | null; source_asset_id: string | null; layers: number; path: string; open: boolean }
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
}

export interface CompareResult { mean: number; p99: number; max: number; rgb_mean: number; rgb_p99: number; rgb_max: number; w: number; h: number; at: string }
export interface BrushOptions { size: number; hardness: number; opacity: number; flow: number; spacing: number; smoothing: number; color: string; background: string }
export interface BrushPreset { name: string; size: number; hardness: number; opacity: number; flow: number; spacing: number; smoothing: number; builtin?: boolean }
export interface HistoryEntry { label: string; layerId: string; kind: 'image' | 'mask'; tiles: TileSnapshot[]; stack?: DocumentStack; at: number; swap?: { layerId: string; lp: LayerPixels; mask: LayerPixels | null } }
type ViewKeys = 'zoom' | 'pan' | 'overlay' | 'before' | 'pixelGrid' | 'quickMask' | 'marqueeShape' | 'selectionMode' | 'tolerance' | 'fillMode'

export interface EditorState {
  doc: DocumentStack | null; docDirty: boolean; loading: boolean; saving: boolean; error: string | null
  activeId: string | null; editingMask: boolean
  tool: Tool; brush: BrushOptions; marqueeShape: 'rect' | 'ellipse'; selectionMode: 'replace' | 'add' | 'subtract'; tolerance: number; fillMode: 'solid' | 'linear' | 'radial'
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
  runAi: (recipe: Record<string, unknown>, stage?: boolean) => Promise<void>
  onDocumentChanged: (d: { id: string; added?: string[]; group?: string; w?: number; h?: number; job_id?: string; batch_id?: string | null; selection?: boolean; shift?: { left: number; top: number } | null }) => void
  mergeServerLayers: (added: string[], group?: string, shift?: { left: number; top: number }) => Promise<void>
  pickCandidate: (keepId: string | null) => void
  // AI Select (10 §4, A tool): the prompt collected on the canvas, and the selection the segment job writes on the server
  aiPrompt: { points: { x: number; y: number; label: 1 | 0 }[]; box: [number, number, number, number] | null }
  setAiPrompt: (p: Partial<EditorState['aiPrompt']>) => void
  loadSelectionFromServer: () => Promise<void>
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
  setActive: (id: string | null, mask?: boolean) => void
  updateNode: (id: string, patch: Partial<Node>, label?: string) => void
  addLayer: (kind?: NodeKind, extra?: Partial<Node>) => Node | null
  deleteNode: (id: string) => void
  duplicateNode: (id: string) => void
  moveNode: (id: string, dir: 'up' | 'down') => void
  mergeDown: (id: string) => void
  groupActive: () => void
  solo: (id: string) => void
  addMask: (id: string, fromSelection?: boolean) => void
  removeMask: (id: string) => void
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
  selectAll: () => void
  invertSelection: () => void
  featherSelection: (px: number) => void
  loadSelectionFromMask: () => void
}

const DEFAULT_BRUSH: BrushOptions = { size: 48, hardness: 0.8, opacity: 1, flow: 0.6, spacing: 0.15, smoothing: 0.4, color: '#f0a63a', background: '#111111' }

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
  if (!maskHintShown) { maskHintShown = true; useSession.getState().toast('Editing the mask: paint white to show the layer, black to hide it — B brush · E eraser · G fill. Click the layer thumbnail to edit its pixels again.', 'info') }
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
      /** Replace the stack, mark dirty, and record the previous stack as one undoable step. */
      const commit = (next: DocumentStack, before: DocumentStack, label: string, layerId: string, extra: Partial<EditorState> = {}) => {
        set({ doc: next, docDirty: true, revision: get().revision + 1, ...extra })
        get().pushHistory({ label, layerId, kind: 'image', tiles: [], stack: before, at: Date.now() })
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
        walk(next.layers, (n) => { if (n.kind === 'raster') { n.x = (n.x ?? 0) + dx; n.y = (n.y ?? 0) + dy; if (n.mask && !n.mask.linked) { n.mask.x += dx; n.mask.y += dy } } })
        const sel = get().selection
        let selection: LayerPixels | null = null
        if (sel) { selection = new LayerPixels(w, h, true); selection.ctx.drawImage(sel.canvas, dx, dy); selection.refresh(); sel.destroy() }
        commit(next, before, label, doc.id, { selection })
        get().requestFit()
      }
      return {
        doc: null, docDirty: false, loading: false, saving: false, error: null, activeId: null, editingMask: false,
        tool: 'brush', brush: DEFAULT_BRUSH, marqueeShape: 'rect', selectionMode: 'replace', tolerance: 32, fillMode: 'solid',
        zoom: 1, pan: { x: 0, y: 0 }, fitRequested: 0, overlay: true, before: false, pixelGrid: false, quickMask: false,
        history: [], future: [], renderer: '', rendererPref: 'auto', rendererEpoch: 0, cursor: null, pixels: new Map(), masks: new Map(), selection: null, revision: 0, extractor: null, lastCompare: null,
        transform: null,
        aiBatch: null, candidates: null, aiPrompt: { points: [], box: null },

        runAi: async (recipe, stage = false) => {
          const { doc, selection } = get()
          const s = useSession.getState()
          if (!doc) return
          try {
            if (!(await get().save())) return                               // the job reads the saved document
            const b = s.backend!
            const body = selection ? (selection.toRaw() as BodyInit) : new Uint8Array(0)
            const r0 = await fetch(`http://${b.host}:${b.port}/documents/${doc.id}/selection?w=${selection?.width ?? 0}&h=${selection?.height ?? 0}`,
              { method: 'PUT', headers: { 'X-Loom-Token': b.token, 'Content-Type': 'application/octet-stream' }, body })
            if (!r0.ok) throw new Error(`selection upload ${r0.status}`)
            const r = await api.post<{ jobs: { id: string; batch_id: string | null }[] }>(`/documents/${doc.id}/ai`, { recipe, stage })
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
          if (d.added?.length) void get().mergeServerLayers(d.added, d.group, d.shift ?? undefined)
        },
        setAiPrompt: (p) => set({ aiPrompt: { ...get().aiPrompt, ...p }, revision: get().revision + 1 }),
        loadSelectionFromServer: async () => {
          const doc = get().doc
          if (!doc) return
          try {
            const b = useSession.getState().backend!
            const res = await fetch(`http://${b.host}:${b.port}/documents/${doc.id}/selection`, { headers: { 'X-Loom-Token': b.token } })
            if (res.status === 404) { get().clearSelection(); return }
            if (!res.ok) throw new Error(`selection ${res.status}`)
            const w = Number(res.headers.get('x-loom-width')), h = Number(res.headers.get('x-loom-height'))
            const sel = LayerPixels.fromRaw(w, h, new Uint8Array(await res.arrayBuffer()), 1)
            get().selection?.destroy()
            set({ selection: sel, quickMask: false, revision: get().revision + 1 })
            useSession.getState().toast('AI Select: selection updated', 'success')
          } catch (e) { useSession.getState().toast(`Could not load the selection: ${(e as Error).message}`, 'error') }
        },
        mergeServerLayers: async (added, group, shift) => {
          const doc = get().doc
          if (!doc) return
          try {
            const server = await api.get<DocumentStack>(`/documents/${doc.id}`)
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
              if (dx || dy) walk(next.layers, (n) => { if (n.kind === 'raster') { n.x = (n.x ?? 0) + dx; n.y = (n.y ?? 0) + dy; if (n.mask && !n.mask.linked) { n.mask.x += dx; n.mask.y += dy } } })
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
            const doc = await api.get<DocumentStack>(`/documents/${id}`)
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
            const existing = (await api.get<{ items: DocSummary[] }>('/documents')).items.find((d) => d.source_asset_id === assetId)
            const doc = existing ?? await api.post<DocumentStack>('/documents', { from_asset: assetId })
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
            const doc = await api.post<DocumentStack>('/documents', { w, h, name: name ?? 'Untitled', background: 'transparent' })
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
        listDocuments: async () => (await api.get<{ items: DocSummary[] }>('/documents')).items,
        deleteDocument: async (id) => {
          if (get().doc?.id === id) get().closeDocument()
          await api.del(`/documents/${id}`)
          useSession.getState().toast('Document deleted', 'info')
        },

        save: async () => {
          const { doc, pixels, masks } = get()
          if (!doc) return false
          // B14: clear the flags *before* the uploads — a stroke that lands meanwhile re-dirties the document and its
          // layer and rides the next save; a failure below puts the document flag back
          set({ saving: true, docDirty: false })
          try {
            type Reply = DocumentStack & { missing_pixels?: string[]; missing_masks?: string[] }
            let stack = doc
            let server: Reply
            try { server = await api.put<Reply>(`/documents/${doc.id}`, stack) }
            catch (e) {
              if (!(e instanceof ApiError) || e.status !== 409) throw e
              await get().resync()                                 // C1: an AI result landed since this stack's revision — merge it, then save the merged stack
              const merged = get().doc
              if (!merged || merged.id !== doc.id) return false
              stack = merged
              server = await api.put<Reply>(`/documents/${doc.id}`, stack)
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
            const saved = await api.post<DocumentStack>(`/documents/${doc.id}/save`)
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
            const server = await api.get<DocumentStack>(`/documents/${doc.id}`)
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
            const r = await api.post<{ asset: { id: string } }>(`/documents/${doc.id}/flatten`, { to_catalogue: true })
            useSession.getState().toast(`Saved to Catalogue as ${r.asset.id}`, 'success')
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
            const { bytes, skipped } = buildPsd(doc, pixels, masks, merged)
            download(new Blob([bytes], { type: 'image/vnd.adobe.photoshop' }), `${doc.name}.psd`)
            useSession.getState().toast(skipped.length ? `PSD written; ${skipped.length} adjustment/filter layer${skipped.length > 1 ? 's' : ''} skipped (${skipped.join(', ')})` : 'PSD written', skipped.length ? 'info' : 'success')
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
        setActive: (id, mask = false) => { const editing = mask && !!findNode(get().doc, id)?.mask; set({ activeId: id, editingMask: editing, ...(editing && !get().editingMask ? maskEditExtras(get().tool) : {}) }) },
        updateNode: (id, patch, label) => {
          const doc = get().doc
          if (!doc) return
          const before = clone(doc)
          const next = clone(doc)
          walk(next.layers, (n) => { if (n.id === id) { Object.assign(n, patch); return true } })
          if (label) commit(next, before, label, id)
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
            tc.drawImage(selectionAlphaCanvas(m), off.x - (top.x ?? 0), off.y - (top.y ?? 0))
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
        addMask: (id, fromSelection = false) => {
          const doc = get().doc
          const n = findNode(doc, id)
          if (!doc || !n || n.mask) return
          const before = clone(doc)
          const lp = new LayerPixels(doc.w, doc.h, true)
          const sel = get().selection
          // B16: the selection canvas is transparent where nothing is selected, so its *alpha* (white = selected) goes over black
          lp.ctx.fillStyle = fromSelection && sel ? '#000000' : '#ffffff'; lp.ctx.fillRect(0, 0, doc.w, doc.h)
          if (fromSelection && sel) lp.ctx.drawImage(selectionAlphaCanvas(sel), 0, 0)
          lp.refresh(); lp.dirty = true
          get().masks.set(id, lp)
          const next = clone(doc)
          // the mask covers the document and is unlinked at the document origin, so layer x/y need no compensation
          walk(next.layers, (m) => { if (m.id === id) { m.mask = { enabled: true, linked: false, x: 0, y: 0 }; return true } })
          commit(next, before, fromSelection && sel ? 'mask from selection' : 'add mask', id, { activeId: id, editingMask: true, ...maskEditExtras(get().tool) })
        },
        removeMask: (id) => {
          const doc = get().doc
          if (!doc) return
          const before = clone(doc)
          const next = clone(doc)                                   // B18: the mask canvas stays for undo (gc drops it later)
          walk(next.layers, (m) => { if (m.id === id) { m.mask = null; return true } })
          commit(next, before, 'remove mask', id, { editingMask: false })
        },
        resizeCanvas: (w, h, ax = 0.5, ay = 0.5) => {
          const doc = get().doc
          if (!doc) return
          setCanvas(Math.round(w), Math.round(h), Math.round((w - doc.w) * ax), Math.round((h - doc.h) * ay), 'canvas size')
        },
        cropToSelection: () => {
          const sel = get().selection
          if (!sel) return
          const d = sel.ctx.getImageData(0, 0, sel.width, sel.height).data
          let x0 = sel.width, y0 = sel.height, x1 = -1, y1 = -1
          for (let y = 0; y < sel.height; y++) for (let x = 0; x < sel.width; x++) if (d[(y * sel.width + x) * 4] > 127) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y }
          if (x1 < 0) return
          setCanvas(x1 - x0 + 1, y1 - y0 + 1, -x0, -y0, 'crop')
          get().clearSelection()
        },
        clearSelected: () => {
          const { doc, activeId, selection, editingMask } = get()
          const n = findNode(doc, activeId)
          if (!doc || !n || n.kind !== 'raster' || n.locked) return
          const lp = editingMask ? get().masks.get(n.id) : get().pixels.get(n.id)
          if (!lp) return
          const off = editingMask ? maskOffset(n) : { x: n.x ?? 0, y: n.y ?? 0 }
          lp.beginStroke(); lp.touch(0, 0, lp.width, lp.height)
          const ctx = lp.ctx
          ctx.save()
          if (selection) {
            const a = selectionAlphaCanvas(selection)                 // alpha = selected amount
            if (editingMask) { const tc = a.getContext('2d')!; tc.globalCompositeOperation = 'source-in'; tc.fillStyle = '#000000'; tc.fillRect(0, 0, a.width, a.height); ctx.globalCompositeOperation = 'source-over' }
            else ctx.globalCompositeOperation = 'destination-out'
            ctx.drawImage(a, -off.x, -off.y)
          } else if (editingMask) { ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, lp.width, lp.height) }
          else ctx.clearRect(0, 0, lp.width, lp.height)
          ctx.restore()
          lp.refresh(); lp.dirty = true
          get().pushHistory({ label: 'clear', layerId: n.id, kind: editingMask ? 'mask' : 'image', tiles: lp.endStroke(), at: Date.now() })
          set({ docDirty: true, revision: get().revision + 1 })
        },

        // ---- history ---------------------------------------------------------------------------------
        pushHistory: (e) => {
          const h = get().history, f = get().future
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
            const target = e.layerId === 'selection' ? get().selection : e.kind === 'mask' ? get().masks.get(e.layerId) : get().pixels.get(e.layerId)
            if (target) redoEntry.tiles = target.restore(e.tiles)
          }
          if (e.swap) redoEntry.swap = swapPixels(e.swap)
          if (e.stack) set({ doc: e.stack, activeId: findNode(e.stack, get().activeId) ? get().activeId : e.stack.layers[0]?.id ?? null })
          set({ history: h.slice(0, -1), future: [...get().future, redoEntry], docDirty: true, transform: null, revision: get().revision + 1 })
        },
        redo: () => {
          const f = get().future
          if (!f.length) return
          const e = f[f.length - 1]
          const undoEntry: HistoryEntry = { ...e, tiles: [], stack: e.stack && get().doc ? clone(get().doc!) : undefined, swap: undefined }
          if (e.tiles.length) {
            const target = e.layerId === 'selection' ? get().selection : e.kind === 'mask' ? get().masks.get(e.layerId) : get().pixels.get(e.layerId)
            if (target) undoEntry.tiles = target.restore(e.tiles)
          }
          if (e.swap) undoEntry.swap = swapPixels(e.swap)
          if (e.stack) set({ doc: e.stack, activeId: findNode(e.stack, get().activeId) ? get().activeId : e.stack.layers[0]?.id ?? null })
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
        selectAll: () => { const sel = get().ensureSelection(); sel.ctx.fillStyle = '#ffffff'; sel.ctx.fillRect(0, 0, sel.width, sel.height); sel.refresh(); set({ revision: get().revision + 1 }) },
        invertSelection: () => {
          const sel = get().ensureSelection()
          const img = sel.ctx.getImageData(0, 0, sel.width, sel.height)
          for (let i = 0; i < img.data.length; i += 4) { const v = 255 - img.data[i]; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255 }
          sel.ctx.putImageData(img, 0, 0); sel.refresh()
          set({ revision: get().revision + 1 })
        },
        featherSelection: (px) => {
          const sel = get().selection
          if (!sel || px <= 0) return
          const tmp = document.createElement('canvas'); tmp.width = sel.width; tmp.height = sel.height
          tmp.getContext('2d')!.drawImage(sel.canvas, 0, 0)
          const ctx = sel.ctx
          ctx.save(); ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, sel.width, sel.height)
          ctx.filter = `blur(${px}px)`; ctx.drawImage(tmp, 0, 0); ctx.restore()
          sel.refresh()
          set({ revision: get().revision + 1 })
        },
        loadSelectionFromMask: () => {
          const n = findNode(get().doc, get().activeId)
          const m = n?.mask ? get().masks.get(n.id) : null
          if (!n || !m) { useSession.getState().toast('The active layer has no mask', 'info'); return }
          const sel = get().ensureSelection()
          const off = maskOffset(n)
          sel.ctx.fillStyle = '#000000'; sel.ctx.fillRect(0, 0, sel.width, sel.height)
          sel.ctx.drawImage(m.canvas, off.x, off.y)
          sel.refresh()
          set({ revision: get().revision + 1 })
        },
      }
    },
    { name: 'loom2.edit', partialize: (s) => ({ tool: s.tool, brush: s.brush, overlay: s.overlay, pixelGrid: s.pixelGrid, tolerance: s.tolerance, fillMode: s.fillMode, rendererPref: s.rendererPref, brushPresets: s.brushPresets }) as never },
  ),
)

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
