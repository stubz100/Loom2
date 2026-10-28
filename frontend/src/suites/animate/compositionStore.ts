// AP1 thin (proto01_animate 20 §2, D114): the Final level's viewer — a final's composition shown frame by frame from
// `GET /finals/{id}/composition/frame?t&side`: ½ size while scrubbing (T1: 25 fps measured in E27), the full frame once the playhead
// rests (T2 ≈ 60 ms); the frames it got are kept by (revision, frame, size), so playback after a first pass is real time (T3) and an
// idle fill walks the shot at ½ while nothing else is asked — paused while the queue runs a job (D97 / D113: the session renders on
// demand only then). The chip says what is shown ("½ · cached 62 %") and always matches the frame (T8). The full AP1 (a sidecar over
// EffectCraft's frame server, the disk cache, the resolution and Fast Previews menus) comes after AE2.
import { create } from 'zustand'
import { baseUrl, getBackend, http, unwrap } from '../../api/client'
import type { Composition, Final } from '../../api/types'
import { useSession } from '../../store/session'
import { registerTransport } from './transport'
import { contextSlot } from '../../store/contexts'

export type Side = 'half' | 'full'
export const REST_MS = 300                 // the playhead still this long: the full frame
const FULL_KEEP = 12                       // full frames kept (≈ 1.2 MB each at 832×480); every ½ frame of the shot is kept (≈ 150 KB)

export interface Shown { url: string; frame: number; side: Side; revision: number }
/** AE2: a layer as the engine reports it (top to bottom). */
export interface CompLayer { id: number; index: number; name: string; type?: string; blendMode: string; trackMatte: { layer: number; kind: string } | null; parent: number | null; in: number; out: number; start: number; switches: Record<string, unknown> }
/** AE2: a property of the selected layer (its flat path) and its keyframes. */
export interface FlatProp { path: string; type: string; value: unknown; keys?: number }
export interface PropKey { time: number; value: unknown; in?: string; out?: string }
export const EDITABLE = ['transform/anchor', 'transform/position', 'transform/scale', 'transform/rotation', 'transform/opacity'] as const
export type Arrange = 'front' | 'forward' | 'backward' | 'back'
/** AE2c: a mask of the selected layer, as the engine's property tree reports it — its outline (vertices and tangents, in the layer's
 *  pixels) drawn on the frame, its vertices dragged there (UX9 U3). */
export interface MaskInfo { uid: number; name: string; path: string; feather: number; opacity: number; expansion: number; mode: string; inverted: boolean
  vertices: [number, number][]; inTangents: [number, number][]; outTangents: [number, number][]; closed: boolean; animated: boolean }
export type MaskTool = 'off' | 'rect' | 'ellipse' | 'poly' | 'object'
export type MaskView = 'lines' | 'fill'
export type EditorTab = 'props' | 'masks' | 'effects' | 'passes'
/** D118 (AE4a): a pass on a layer — the preset and its strength; AE4c: Face and Lip-sync (the head as its own layer, E29b; no strength). */
export type PassPreset = 'cleanup' | 'creative' | 'face' | 'lipsync'
export const PASS_LABEL: Record<PassPreset, string> = { cleanup: 'Clean up', creative: 'Creative', face: 'Face', lipsync: 'Lip-sync' }
export const PASS_STRENGTH: Record<PassPreset, number> = { cleanup: 0.1, creative: 0.35, face: 0.5, lipsync: 0.5 }
export type PassMouth = 'head' | 'model'
/** AE4e: a pass on the layer's own frames, or over the stack from the selected layer down — a processing layer above it. */
export type PassScope = 'layer' | 'below'
export type ProcessingRec = NonNullable<Final['processing']>[number]
export interface Take { id: string; preset: string; strength: number; model_id?: string; job_id?: string; frames?: number; seed?: number; made_at?: string; head?: boolean; mouth?: PassMouth; lines?: { layer: number | null; text: string | null; f0: number; f1: number }[] }
/** D118 (AE4b): a voiced line of the shot, as GET /finals/{fid}/lines reports it. */
export interface FinalLine { node_id: string; index: number; speaker: string | null; speaker_name: string | null; text: string; audio_asset_id: string; duration_s: number | null; layer_id: string | null }
export type AudioLayer = Composition['audio'][number]
export const MASK_MODES = ['Add', 'Subtract', 'Intersect', 'Lighten', 'Darken', 'Difference', 'None']
interface TreeNode { path?: string; name?: string; uid?: number; type?: string; value?: unknown; mask?: { inverted?: boolean; mode?: string }; children?: TreeNode[] }
/** The masks of a layer's property tree (`masks/mask`, `masks/mask#2` …): uid, name, feather (one number: the x), opacity, expansion, mode, inverted. */
export function masksOf(tree: TreeNode | undefined): MaskInfo[] {
  const group = tree?.children?.find((g) => g.path === 'masks')
  return (group?.children ?? []).filter((m) => m.uid !== undefined).map((m) => {
    const leaf = (k: string) => m.children?.find((c) => (c.path ?? '').endsWith(`/${k}`))?.value
    const feather = leaf('feather')
    const pathChild = m.children?.find((c) => (c.path ?? '').endsWith('/path')) as (TreeNode & { animated?: boolean; keys?: number }) | undefined
    const pv = ((pathChild?.value as { v?: Record<string, unknown> } | undefined)?.v ?? {}) as { closed?: boolean; vertices?: number[][]; in_tangents?: number[][]; out_tangents?: number[][] }
    const pts = (xs?: number[][]): [number, number][] => (xs ?? []).map((p) => [Number(p[0] ?? 0), Number(p[1] ?? 0)])
    return { uid: m.uid!, name: m.name ?? 'Mask', path: m.path ?? '', feather: Array.isArray(feather) ? Number(feather[0]) : Number(feather ?? 0),
      opacity: Number(leaf('opacity') ?? 100), expansion: Number(leaf('expansion') ?? 0), mode: m.mask?.mode ?? 'Add', inverted: !!m.mask?.inverted,
      vertices: pts(pv.vertices), inTangents: pts(pv.in_tangents), outTangents: pts(pv.out_tangents), closed: pv.closed !== false,
      animated: !!(pathChild?.animated || pathChild?.keys) }                                  // D116: keyed — from the layer, or tracked
  })
}
/** A mask's outline as an SVG path (the layer's pixels, moved by `dx, dy` into the composition's): cubic segments from the tangents. */
export function maskPathD(m: Pick<MaskInfo, 'vertices' | 'inTangents' | 'outTangents' | 'closed'>, dx = 0, dy = 0): string {
  const v = m.vertices
  if (!v.length) return ''
  const f = (n: number) => Math.round(n * 100) / 100
  let d = `M ${f(v[0][0] + dx)} ${f(v[0][1] + dy)}`
  const n = v.length
  for (let i = 0; i < (m.closed ? n : n - 1); i++) {
    const j = (i + 1) % n
    const o = m.outTangents[i] ?? [0, 0], t = m.inTangents[j] ?? [0, 0]
    d += ` C ${f(v[i][0] + o[0] + dx)} ${f(v[i][1] + o[1] + dy)} ${f(v[j][0] + t[0] + dx)} ${f(v[j][1] + t[1] + dy)} ${f(v[j][0] + dx)} ${f(v[j][1] + dy)}`
  }
  return m.closed ? `${d} Z` : d
}
/** AE2d: seconds snapped to the composition's frames. */
export const snapTime = (sec: number, rate: number): number => Math.round(sec * rate) / rate
/** AE3: an effect on the selected layer, as the engine's property tree reports it. */
export interface EffectInfo { uid: number; name: string; id: string; path: string; enabled: boolean }
export interface EffectParam { id: string; name: string; type: string; default?: unknown; min?: number; max?: number; decimals?: number; options?: { label: string; value: number }[] }
/** AE3: the engine's definition of an effect (`list_effects`). */
export interface EffectDef { id: string; name: string; category?: string; gpu?: boolean; params: EffectParam[] }
export function effectsOf(tree: TreeNode | undefined): EffectInfo[] {
  const group = tree?.children?.find((g) => g.path === 'effects')
  return (group?.children ?? []).filter((e) => e.uid !== undefined).map((e) => ({ uid: e.uid!, name: e.name ?? 'Effect', id: (e as { effect?: string }).effect ?? '', path: e.path ?? '', enabled: (e as { enabled?: boolean }).enabled !== false }))
}
const detail = (e: unknown): string => (e as { detail?: string }).detail ?? (e as Error).message ?? String(e)

interface CompState {
  finalId: string | null
  final: Final | null
  comp: Composition | null
  frame: number
  playing: boolean
  shown: Shown | null
  fetching: boolean
  filled: number                           // ½ frames cached at this revision
  error: string | null
  /** Show this final's composition at the Final level (its record and composition loaded, the first frame asked for); the level itself is
   *  the `final` suite (D121) — the caller switches to it. */
  open: (finalId: string) => Promise<void>
  /** Load the final and its composition again; a new revision drops the cached frames. */
  reload: () => Promise<void>
  setFrame: (n: number) => void
  step: (d: number) => void
  home: () => void
  end: () => void
  togglePlay: (on?: boolean) => void
  /** The playhead at rest: the full frame (what the rest timer calls). */
  settle: () => void
  /** The idle fill: the next ½ frame not cached, while nothing plays, nothing is in flight and no job runs. */
  tick: () => Promise<void>
  // ---- AE2: the editor ----
  layers: CompLayer[]
  selected: number | null
  props: FlatProp[]
  keysOf: Record<string, PropKey[]>
  uidOf: Record<string, number | string>
  busy: boolean
  loadLayers: () => Promise<void>
  select: (id: number | null) => void
  loadProps: () => Promise<void>
  /** One engine command on the composition, saved; then the viewer and the lists follow the new revision. */
  command: (id: string, params: Record<string, unknown>, what: string) => Promise<boolean>
  /** Several commands as one edit (one revision). */
  batch: (steps: { id: string; params?: Record<string, unknown> }[], what: string) => Promise<boolean>
  /** A property of the selected layer set, or keyed at `time`. */
  setProp: (path: string, value: unknown, time?: number) => Promise<boolean>
  nudge: (dx: number, dy: number) => Promise<boolean>
  undo: () => Promise<boolean>
  redo: () => Promise<boolean>
  layerSwitch: (id: number, name: string, value: boolean) => Promise<boolean>
  setBlend: (id: number, mode: string) => Promise<boolean>
  setMatte: (id: number, matte: number | null, kind: string) => Promise<boolean>
  setParent: (id: number, parent: number | null) => Promise<boolean>
  arrange: (id: number, to: Arrange) => Promise<boolean>
  /** A keyframe on the selected layer's property at the playhead — added, or the one there removed. */
  keyToggle: (path: string) => Promise<boolean>
  keyEase: (path: string, time: number, how: 'ease' | 'hold' | 'linear') => Promise<boolean>
  keyDelete: (path: string, time: number) => Promise<boolean>
  // ---- AE2c: masks ----
  masks: MaskInfo[]
  maskTool: MaskTool
  selectedMask: number | null                       // the mask's uid: its outline brighter on the frame, its vertices draggable
  poly: [number, number][]                          // the points tool's points so far, in comp pixels (cleared with the tool)
  setPoly: (points: [number, number][]) => void
  editorTab: EditorTab                              // UX9 U1: the editor sits under the selected layer's row — which part of it is open
  setEditorTab: (tab: EditorTab) => void
  selectMask: (uid: number | null) => void
  setMaskTool: (tool: MaskTool) => void
  loadMasks: () => Promise<void>
  /** A rectangle or ellipse mask on the selected layer, `rect` in comp pixels [x, y, w, h]. */
  addMask: (rect: [number, number, number, number], shape: 'rect' | 'ellipse') => Promise<boolean>
  /** A mask from points clicked on the frame (`mask.new`), in the layer's pixels. */
  addPolyMask: (points: [number, number][]) => Promise<boolean>
  /** One vertex of a mask moved (`mask.setVertex`), in the layer's pixels. */
  moveVertex: (uid: number, index: number, point: [number, number]) => Promise<boolean>
  // ---- D116: more masks ----
  maskView: MaskView                                // the overlay: outlines, or the masks filled
  setMaskView: (view: MaskView) => void
  /** The selected layer's visible content at the playhead traced into a mask (the server reads the layer's footage); `follow` keys it on every frame. */
  maskFromLayer: (follow: boolean) => Promise<boolean>
  /** EffectCraft tracks what is inside the selected mask from the playhead to the end of the shot (`track.mask`, classical, one undo step). */
  trackMask: () => Promise<boolean>
  /** EffectCraft's Object Matte on the selected layer from a click (layer pixels): applied at the playhead, propagated over the whole shot. */
  objectMatte: (point: [number, number]) => Promise<boolean>
  // ---- D118 (AE4a): passes on the selected layer ----
  passPreset: PassPreset
  passStrength: number
  passMouth: PassMouth                                   // AE4d (lipsync): the talking head drives the mouth, or the lip-sync model redraws it
  passScope: PassScope                                   // AE4e: this layer, or the stack from it down
  setPass: (preset: PassPreset, strength?: number) => void
  setMouth: (mouth: PassMouth) => void
  setScope: (scope: PassScope) => void
  pointLayerId: () => string | null                      // AE4e: the final layer the selected engine layer stands for (any kind but a processing layer)
  processingOf: (layer: number) => ProcessingRec | null  // the final's record behind an engine layer (a stable reference: a selector's result)
  processingStale: (layer: number) => boolean
  runProcessingAgain: () => Promise<boolean>
  removeProcessing: (pid: string) => Promise<boolean>
  /** The final's layer behind the selected composition layer (null for a matte or the shadows). */
  finalLayerId: () => string | null
  /** A pass queued on the selected layer's final layer (a GPU job); its take lands as the layer's source and the composition syncs. */
  runPass: (point?: string) => Promise<boolean>
  /** The take the layer shows (null: its original frames); the composition swaps the footage in the same call. */
  useTake: (take: string | null) => Promise<boolean>
  dropTake: (take: string) => Promise<boolean>
  /** Every layer whose source moved on the final swapped in the composition (called when a pass's job lands). */
  syncSources: () => Promise<void>
  // ---- D118 (AE4b): the line as an audio layer ----
  /** The audio layer behind an engine layer id, when it is one. */
  audioOf: (layer: number) => AudioLayer | null
  /** The shot's voiced lines (GET /finals/{fid}/lines). */
  loadLines: () => Promise<FinalLine[]>
  /** A line attached at the playhead as an audio layer bound to its speaker's layer. */
  attachLine: (line: FinalLine) => Promise<boolean>
  removeAudio: (layer: number) => Promise<boolean>
  setMaskField: (uid: number, field: 'feather' | 'opacity' | 'expansion', value: number) => Promise<boolean>
  setMaskMode: (uid: number, mode: string) => Promise<boolean>
  invertMask: (uid: number, value: boolean) => Promise<boolean>
  removeMask: (uid: number) => Promise<boolean>
  // ---- AE2d: timing ----
  /** A layer's in / out trimmed, or moved by `delta` seconds (`layer.timing`). */
  setTiming: (id: number, patch: { in?: number; out?: number; delta?: number }) => Promise<boolean>
  /** The layer's footage slid under its in / out (`layer.slip`). */
  slip: (id: number, delta: number) => Promise<boolean>
  // ---- AE3: effects ----
  effects: EffectInfo[]
  fxValues: Record<string, unknown>                 // the selected layer's effect parameters by path (`effects/#1/blurriness`)
  catalog: Record<string, EffectDef>                 // the engine's definitions of the curated effects, by name
  before: string | null                              // the Before frame (every effect off) while comparing
  loadCatalog: (names: string[]) => Promise<void>
  addEffect: (name: string) => Promise<boolean>
  toggleEffect: (uid: number, value: boolean) => Promise<boolean>
  resetEffect: (uid: number) => Promise<boolean>
  removeEffect: (uid: number) => Promise<boolean>
  /** The frame with every effect off (nothing saved), shown while on. */
  compareBefore: (on: boolean) => Promise<void>
}

const cache = new Map<string, string>()
const fullKeys: string[] = []
let wanted: { frame: number; side: Side } | null = null
let inflight: Promise<void> | null = null
let restTimer: number | null = null
let playTimer: number | null = null

const key = (rev: number, frame: number, side: Side) => `${rev}:${frame}:${side}`
/** The jobs the page knows: one running means the session renders on demand only (D97 / D113). */
export const queueBusy = (): boolean => Object.values(useSession.getState().jobs).some((j) => j.status === 'running')

const seenPasses = new Set<string>()                                           // D118: the pass jobs already synced into the composition

function clearCache(): void {
  for (const u of cache.values()) URL.revokeObjectURL(u)
  cache.clear()
  fullKeys.length = 0
}

async function fetchFrame(final: Final, revision: number, frame: number, side: Side): Promise<string | null> {
  const b = getBackend()
  if (!b) return null
  const px = side === 'half' ? Math.round(Math.max(final.size.w, final.size.h) / 2) : 0
  const res = await fetch(`${baseUrl()}/finals/${final.id}/composition/frame?t=${frame / final.rate}&side=${px}`, { headers: { 'X-Loom-Token': b.token } })
  if (!res.ok) throw new Error(`frame ${frame}: ${res.status}`)
  const url = URL.createObjectURL(await res.blob())
  const k = key(revision, frame, side)
  const old = cache.get(k)
  if (old) URL.revokeObjectURL(old)
  cache.set(k, url)
  if (side === 'full') {
    fullKeys.push(k)
    while (fullKeys.length > FULL_KEEP) {
      const drop = fullKeys.shift()!
      const u = cache.get(drop)
      if (u) { URL.revokeObjectURL(u); cache.delete(drop) }
    }
  }
  return url
}

/** The chip's text: how much of the shot is cached, as a number alone (UX9 U2: the words flickered). The size shown and a running job
 *  are the chip's attributes, styled, not words. */
export function chipText(s: Pick<CompState, 'filled' | 'final'>): string {
  const n = s.final?.frames ?? 0
  return `${n ? Math.round((100 * s.filled) / n) : 0} %`
}

export const useComposition = create<CompState>((set, get) => {
  const show = (frame: number, side: Side): boolean => {
    const { comp } = get()
    if (!comp) return false
    const url = cache.get(key(comp.revision, frame, side))
    if (!url) return false
    if (get().frame === frame && (side === 'full' || get().shown?.frame !== frame || get().shown?.side !== 'full')) set({ shown: { url, frame, side, revision: comp.revision } })
    return true
  }
  const count = (): number => {
    const { comp, final } = get()
    if (!comp || !final) return 0
    let n = 0
    for (let i = 0; i < final.frames; i++) if (cache.has(key(comp.revision, i, 'half'))) n++
    return n
  }
  const pump = (): void => {
    if (inflight) return
    inflight = (async () => {
      try {
        while (wanted) {
          const { final, comp } = get()
          const w = wanted
          if (!final || !comp) { wanted = null; break }
          if (cache.has(key(comp.revision, w.frame, w.side))) { wanted = null; show(w.frame, w.side); break }
          set({ fetching: true })
          try {
            await fetchFrame(final, comp.revision, w.frame, w.side)
            set({ error: null, filled: count() })
          } catch (e) { set({ error: (e as Error).message }) }
          if (wanted === w) wanted = null
          show(w.frame, w.side)
        }
      } finally { inflight = null; set({ fetching: false }) }
    })()
  }
  const request = (frame: number, side: Side): void => {
    if (show(frame, side)) return
    if (side === 'half' && show(frame, 'full')) return            // a full frame already here says more than a half one would
    wanted = { frame, side }
    pump()
  }
  const stopPlay = (): void => { if (playTimer !== null) { window.clearTimeout(playTimer); playTimer = null } }
  const armRest = (): void => {
    if (restTimer !== null) window.clearTimeout(restTimer)
    restTimer = window.setTimeout(() => { restTimer = null; get().settle() }, REST_MS)
  }
  /** After an edit: the composition again (its revision moved: the cache dropped, the frame asked again), the lists, the properties. */
  const edited = async (): Promise<void> => {
    await get().reload()
    await Promise.all([get().loadProps(), get().loadMasks()])
  }
  const run = async <T,>(what: string, call: () => Promise<T>): Promise<boolean> => {
    if (!get().finalId) return false
    set({ busy: true })
    try { await call(); await edited(); return true } catch (e) { useSession.getState().toast(`${what}: ${detail(e)}`, 'error'); return false } finally { set({ busy: false }) }
  }
  return {
    finalId: null, final: null, comp: null, frame: 0, playing: false, shown: null, fetching: false, filled: 0, error: null,
    layers: [], selected: null, props: [], keysOf: {}, uidOf: {}, busy: false, masks: [], maskTool: 'off', selectedMask: null, poly: [], maskView: 'lines', editorTab: 'props', passPreset: 'cleanup', passStrength: 0.1, passMouth: 'head', passScope: 'layer', effects: [], fxValues: {}, catalog: {}, before: null,
    loadLayers: async () => {
      const fid = get().finalId
      if (!fid || !get().comp) { set({ layers: [] }); return }
      try {
        const r = await unwrap(http.GET('/finals/{fid}/composition/layers', { params: { path: { fid } } }))
        const layers = r.items as unknown as CompLayer[]
        set({ layers })
        if (get().selected !== null && !layers.some((l) => l.id === get().selected)) set({ selected: null, props: [], keysOf: {}, uidOf: {} })
      } catch (e) { set({ error: detail(e) }) }
    },
    select: (id) => { set({ selected: id, props: [], keysOf: {}, uidOf: {}, masks: [], effects: [], fxValues: {}, selectedMask: null, maskTool: 'off', poly: [] }); if (id !== null) { void get().loadProps(); void get().loadMasks() } },
    loadProps: async () => {
      const fid = get().finalId, sel = get().selected
      if (!fid || sel === null) return
      try {
        const r = await unwrap(http.GET('/finals/{fid}/composition/layers/{lid}', { params: { path: { fid, lid: String(sel) } } })) as { properties?: FlatProp[] }
        const props = (r.properties ?? []).filter((p) => (EDITABLE as readonly string[]).includes(p.path))
        const fxValues = Object.fromEntries((r.properties ?? []).filter((p) => p.path.startsWith('effects/')).map((p) => [p.path, p.value]))   // AE3: the effects' dials
        if (get().selected === sel) set({ fxValues })
        const keysOf: Record<string, PropKey[]> = {}
        const uidOf: Record<string, number | string> = {}
        await Promise.all(props.map(async (p) => {
          const k = await unwrap(http.GET('/finals/{fid}/composition/layers/{lid}/property', { params: { path: { fid, lid: String(sel) }, query: { path: p.path } } })) as { keys?: PropKey[]; uid?: number | string }
          keysOf[p.path] = k.keys ?? []
          if (k.uid !== undefined) uidOf[p.path] = k.uid
        }))
        if (get().selected === sel) set({ props, keysOf, uidOf })
      } catch (e) { set({ error: detail(e) }) }
    },
    command: (id, params, what) => run(what, () => unwrap(http.POST('/finals/{fid}/composition/command', { params: { path: { fid: get().finalId! } }, body: { id, params } }))),
    batch: (steps, what) => run(what, () => unwrap(http.POST('/finals/{fid}/composition/batch', { params: { path: { fid: get().finalId! } }, body: { steps: steps.map((s) => ({ id: s.id, params: s.params ?? {} })) } }))),
    setProp: (path, value, time) => {
      const sel = get().selected
      if (sel === null) return Promise.resolve(false)
      return run('Set the property', () => unwrap(http.POST('/finals/{fid}/composition/property', { params: { path: { fid: get().finalId! } }, body: { layer: sel, path, value, time: time ?? null } })))
    },
    nudge: (dx, dy) => { const sel = get().selected; return sel === null ? Promise.resolve(false) : get().command('layer.nudge', { x: dx, y: dy, layers: [sel] }, 'Move the layer') },
    undo: () => get().command('edit.undo', {}, 'Undo'),
    redo: () => get().command('edit.redo', {}, 'Redo'),
    layerSwitch: (id, name, value) => get().command('layer.setSwitch', { layers: [id], switch: name, value }, 'Switch the layer'),
    setBlend: (id, mode) => get().command('layer.setBlendMode', { layers: [id], mode }, 'Blend mode'),
    setMatte: (id, matte, kind) => get().command('layer.setTrackMatte', { layer: id, matte, kind }, 'Track matte'),
    setParent: (id, parent) => get().command('layer.setParent', { layers: [id], parent }, 'Parent'),
    arrange: (id, to) => get().command('layer.arrange', { layers: [id], to }, 'Arrange the layers'),
    keyToggle: (path) => {
      const sel = get().selected, f = get().final
      if (sel === null || !f) return Promise.resolve(false)
      return get().batch([{ id: 'time.set', params: { time: get().frame / f.rate } }, { id: 'prop.toggleKey', params: { layer: sel, path } }], 'Keyframe')
    },
    keyEase: (path, time, how) => {
      const sel = get().selected
      if (sel === null) return Promise.resolve(false)
      const step = how === 'ease' ? { id: 'keys.easyEase' } : how === 'hold' ? { id: 'keys.toggleHold' } : { id: 'keys.interpolation', params: { interpolation: 'linear' } }
      return get().batch([{ id: 'keys.select', params: { keys: [{ layer: sel, prop: get().uidOf[path] ?? path, time }] } }, step], 'Keyframe')
    },
    keyDelete: (path, time) => {
      const sel = get().selected
      if (sel === null) return Promise.resolve(false)
      return get().batch([{ id: 'keys.select', params: { keys: [{ layer: sel, prop: get().uidOf[path] ?? path, time }] } }, { id: 'keys.delete' }], 'Delete the keyframe')
    },
    // ---- AE2c: masks ----
    setMaskTool: (maskTool) => set({ maskTool, poly: [] }),
    setPoly: (poly) => set({ poly }),
    setEditorTab: (editorTab) => set({ editorTab }),
    selectMask: (selectedMask) => set({ selectedMask }),
    addPolyMask: (points) => {
      const sel = get().selected
      if (sel === null || points.length < 3) return Promise.resolve(false)
      return get().command('mask.new', { layer: sel, vertices: points.map(([x, y]) => [Math.round(x), Math.round(y)]), closed: true }, 'Mask')
    },
    moveVertex: (uid, index, point) => get().command('mask.setVertex', { layer: get().selected, mask: uid, index, point: [Math.round(point[0]), Math.round(point[1])] }, 'Mask vertex'),
    // ---- D116: more masks ----
    setMaskView: (maskView) => set({ maskView }),
    maskFromLayer: async (follow) => {
      const s = get()
      if (s.selected === null || !s.finalId || !s.final || s.busy) return false
      set({ busy: true })
      try {
        const r = await http.POST('/finals/{fid}/composition/layers/{lid}/mask_from_content', { params: { path: { fid: s.finalId, lid: String(s.selected) } }, body: { t: s.frame / s.final.rate, follow, tolerance: 1.5, max_points: 160 } })
        if (r.error) { useSession.getState().toast(`Mask from the layer: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
        const res = (r.data as { result?: { points?: number; frames?: number } }).result
        useSession.getState().toast(`Mask from the layer: ${res?.points ?? 0} points${follow ? `, following over ${res?.frames ?? 1} frames` : ''}`, 'success')
        await edited()
        return true
      } finally { set({ busy: false }) }
    },
    trackMask: async () => {
      const s = get()
      if (s.selected === null || s.selectedMask === null || !s.final) return false
      const t = s.frame / s.final.rate
      const ok = await get().batch([{ id: 'time.set', params: { time: t } }, { id: 'track.mask', params: { layer: s.selected, mask: s.selectedMask, method: 'positionScaleRotation', direction: 'forward', wait: true } }], 'Follow the motion')
      if (ok) useSession.getState().toast('The mask follows the motion from the playhead to the end', 'success')
      return ok
    },
    // ---- D118 (AE4a): passes ----
    setPass: (preset, strength) => set({ passPreset: preset, passStrength: strength ?? PASS_STRENGTH[preset] }),
    setMouth: (mouth) => set({ passMouth: mouth }),
    setScope: (scope) => set({ passScope: scope }),
    pointLayerId: () => { const s = get(); const cl = s.comp?.layers.find((l) => l.layer === s.selected); return cl && cl.kind !== 'processing' ? cl.id : null },
    processingOf: (layer) => {
      const s = get()
      const pid = Object.entries(s.comp?.processing ?? {}).find(([, eid]) => eid === layer)?.[0]
      return (pid ? (s.final?.processing ?? []).find((p) => p.id === pid) : undefined) ?? null
    },
    processingStale: (layer) => {
      const s = get()
      const pid = Object.entries(s.comp?.processing ?? {}).find(([, eid]) => eid === layer)?.[0]
      return !!pid && !!s.comp?.processing_stale?.[pid]
    },
    runProcessingAgain: async () => {
      const s = get()
      const proc = s.selected !== null ? s.processingOf(s.selected) : null
      if (!proc) return false
      set({ passScope: 'below', passPreset: proc.preset as PassPreset, passStrength: proc.strength })
      return get().runPass(proc.above)
    },
    removeProcessing: async (pid) => {
      const s = get()
      if (!s.finalId) return false
      set({ busy: true })
      try {
        const r = await http.DELETE('/finals/{fid}/processing/{pid}', { params: { path: { fid: s.finalId, pid } } })
        if (r.error) { useSession.getState().toast(`Processing layer: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
        await edited()
        return true
      } finally { set({ busy: false }) }
    },
    finalLayerId: () => { const s = get(); const cl = s.comp?.layers.find((l) => l.layer === s.selected); return cl && (cl.kind === 'figure' || cl.kind === 'plate') ? cl.id : null },
    runPass: async (point) => {
      const s = get()
      const below = s.passScope === 'below'
      const lid = point ?? (below ? s.pointLayerId() : s.finalLayerId())
      if (!s.finalId || !lid) { useSession.getState().toast(below ? 'Pick the layer the processing starts from' : 'A pass runs on a character layer or the plate', 'info'); return false }
      const r = await http.POST('/finals/{fid}/layers/{lid}/pass', { params: { path: { fid: s.finalId, lid } }, body: { preset: s.passPreset, strength: s.passStrength, mouth: s.passMouth, scope: s.passScope } })
      if (r.error) { useSession.getState().toast(`Pass: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
      useSession.getState().toast(below ? `${PASS_LABEL[s.passPreset]} pass queued over the stack from the layer down — a processing layer lands above it`
        : `${PASS_LABEL[s.passPreset]} pass queued on the layer — its take lands as the layer's source`
        + (s.passPreset === 'face' || s.passPreset === 'lipsync' ? ' (several jobs: the head in batches, then the paste)' : ''), 'success')
      void get().reload()
      return true
    },
    useTake: async (take) => {
      const s = get()
      const lid = s.finalLayerId()
      if (!s.finalId || !lid) return false
      set({ busy: true })
      try {
        const r = await http.POST('/finals/{fid}/layers/{lid}/source', { params: { path: { fid: s.finalId, lid } }, body: { take } })
        if (r.error) { useSession.getState().toast(`Take: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
        await edited()
        return true
      } finally { set({ busy: false }) }
    },
    dropTake: async (take) => {
      const s = get()
      const lid = s.finalLayerId()
      if (!s.finalId || !lid) return false
      set({ busy: true })
      try {
        const r = await http.DELETE('/finals/{fid}/layers/{lid}/takes/{take}', { params: { path: { fid: s.finalId, lid, take } } })
        if (r.error) { useSession.getState().toast(`Take: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
        await edited()
        return true
      } finally { set({ busy: false }) }
    },
    // ---- D118 (AE4b): the line as an audio layer ----
    audioOf: (layer) => get().comp?.audio.find((a) => a.layer === layer) ?? null,
    loadLines: async () => {
      const fid = get().finalId
      if (!fid) return []
      const r = await http.GET('/finals/{fid}/lines', { params: { path: { fid } } })
      return r.error ? [] : ((r.data as { items: FinalLine[] }).items ?? [])
    },
    attachLine: async (line) => {
      const s = get()
      if (!s.finalId || !s.final) return false
      set({ busy: true })
      try {
        const r = await http.POST('/finals/{fid}/composition/audio', { params: { path: { fid: s.finalId } },
          body: { asset_id: line.audio_asset_id, layer_id: line.layer_id, node_id: line.node_id, index: line.index, t: s.frame / s.final.rate } })
        if (r.error) { useSession.getState().toast(`Line: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
        useSession.getState().toast(`${line.speaker_name ?? 'The line'} attached at the playhead — move it on its lane`, 'success')
        await edited()
        return true
      } finally { set({ busy: false }) }
    },
    removeAudio: async (layer) => {
      const s = get()
      if (!s.finalId) return false
      set({ busy: true })
      try {
        const r = await http.DELETE('/finals/{fid}/composition/audio/{layer}', { params: { path: { fid: s.finalId, layer } } })
        if (r.error) { useSession.getState().toast(`Line: ${(r.error as { detail?: string }).detail ?? 'refused'}`, 'error'); return false }
        if (s.selected === layer) set({ selected: null })
        await edited()
        return true
      } finally { set({ busy: false }) }
    },
    syncSources: async () => {
      const s = get()
      if (!s.finalId || !s.comp) return
      const r = await http.POST('/finals/{fid}/composition/sync', { params: { path: { fid: s.finalId } } })
      if (!r.error) await edited()
    },
    objectMatte: async (point) => {
      const s = get()
      if (s.selected === null || !s.final) return false
      const frame = s.frame
      const ok = await get().batch([
        { id: 'objectMatte.apply', params: { layer: s.selected, point: [Math.round(point[0]), Math.round(point[1])], frame, before: frame, after: Math.max(0, s.final.frames - 1 - frame) } },
        { id: 'objectMatte.propagate', params: { layer: s.selected, wait: true } }], 'Object matte')
      if (ok) { useSession.getState().toast('Object Matte on the layer: an effect, listed under Effects; it follows the thing across the shot', 'success'); set({ maskTool: 'off' }) }
      return ok
    },
    loadMasks: async () => {
      const fid = get().finalId, sel = get().selected
      if (!fid || sel === null) return
      try {
        const r = await unwrap(http.GET('/finals/{fid}/composition/layers/{lid}', { params: { path: { fid, lid: String(sel) }, query: { tree: true } } })) as { properties?: TreeNode }
        if (get().selected === sel) {
          const masks = masksOf(r.properties)
          set({ masks, effects: effectsOf(r.properties), selectedMask: masks.some((m) => m.uid === get().selectedMask) ? get().selectedMask : masks.length ? masks[masks.length - 1].uid : null })   // one tree read: the masks and the effects; the newest mask selected
        }
      } catch (e) { set({ error: detail(e) }) }
    },
    // ---- AE3: effects ----
    loadCatalog: async (names) => {
      const fid = get().finalId
      if (!fid || !names.length) return
      try {
        const r = await unwrap(http.GET('/finals/{fid}/composition/effects', { params: { path: { fid }, query: { names: names.join(',') } } }))
        const defs = r.items as unknown as EffectDef[]
        set({ catalog: Object.fromEntries(defs.map((d) => [d.name, d])) })
      } catch (e) { set({ error: detail(e) }) }
    },
    addEffect: (name) => { const sel = get().selected; return sel === null ? Promise.resolve(false) : get().command('effect.apply', { effect: name, layers: [sel] }, name) },
    toggleEffect: (uid, value) => get().command('effect.toggle', { layer: get().selected, effect: uid, value }, 'Effect'),
    resetEffect: (uid) => get().command('effect.reset', { layer: get().selected, effect: uid }, 'Reset the effect'),
    removeEffect: (uid) => get().command('effect.remove', { layer: get().selected, effect: uid }, 'Remove the effect'),
    compareBefore: async (on) => {
      const old = get().before
      if (old) { URL.revokeObjectURL(old); set({ before: null }) }
      if (!on) return
      const { final, comp, frame, shown } = get()
      const b = getBackend()
      if (!final || !comp || !b) return
      const px = shown?.side === 'full' ? 0 : Math.round(Math.max(final.size.w, final.size.h) / 2)
      try {
        const res = await fetch(`${baseUrl()}/finals/${final.id}/composition/frame?t=${frame / final.rate}&side=${px}&before=true`, { headers: { 'X-Loom-Token': b.token } })
        if (!res.ok) throw new Error(`before: ${res.status}`)
        const url = URL.createObjectURL(await res.blob())
        if (get().frame === frame && get().comp?.revision === comp.revision) set({ before: url }); else URL.revokeObjectURL(url)
      } catch (e) { set({ error: (e as Error).message }) }
    },
    addMask: (rect, shape) => {
      const sel = get().selected
      if (sel === null) return Promise.resolve(false)
      return get().command('layer.addMask', { layer: sel, shape, rect }, 'Mask')
    },
    setMaskField: (uid, field, value) => get().command('layer.mask.set', { layer: get().selected, mask: uid, field, value }, 'Mask'),
    setMaskMode: (uid, mode) => get().command('layer.mask.mode', { layer: get().selected, mask: uid, mode }, 'Mask mode'),
    invertMask: (uid, value) => get().command('layer.mask.invert', { layer: get().selected, mask: uid, value }, 'Mask'),
    removeMask: (uid) => get().command('layer.mask.remove', { layer: get().selected, mask: uid }, 'Remove the mask'),
    // ---- AE2d: timing ----
    setTiming: (id, patch) => get().command('layer.timing', { layers: [id], ...patch }, 'Timing'),
    slip: (id, delta) => get().command('layer.slip', { layers: [id], delta }, 'Slip'),
    open: async (finalId) => {
      if (get().finalId !== finalId) { get().togglePlay(false); set({ finalId, frame: 0, shown: null, comp: null, final: null }) }
      await get().reload()
    },
    reload: async () => {
      const id = get().finalId
      if (!id) return
      try {
        const final = await unwrap(http.GET('/finals/{fid}', { params: { path: { fid: id } } }))
        let comp: Composition | null = null
        try { comp = await unwrap(http.GET('/finals/{fid}/composition', { params: { path: { fid: id } } })) } catch { comp = null }
        if (comp?.revision !== get().comp?.revision || get().final?.id !== final.id) {
          clearCache(); wanted = null
          if (get().before) URL.revokeObjectURL(get().before!)
          set({ shown: null, filled: 0, before: null })
        }
        set({ final, comp, error: null, frame: Math.min(get().frame, Math.max(0, final.frames - 1)) })
        if (comp) { request(get().frame, 'half'); armRest() }
        void get().loadLayers()
      } catch (e) { set({ error: (e as Error).message }) }
    },
    setFrame: (n) => {
      const f = get().final
      const frame = Math.max(0, Math.min(f ? f.frames - 1 : 0, Math.round(n)))
      if (get().before) { URL.revokeObjectURL(get().before!); set({ before: null }) }   // the Before frame was this frame's
      set({ frame })
      request(frame, 'half')
      if (!get().playing) armRest()
    },
    step: (d) => { get().togglePlay(false); get().setFrame(get().frame + d) },
    home: () => { get().togglePlay(false); get().setFrame(0) },
    end: () => { get().togglePlay(false); get().setFrame((get().final?.frames ?? 1) - 1) },
    togglePlay: (on) => {
      const next = on ?? !get().playing
      if (next === get().playing) return
      set({ playing: next })
      stopPlay()
      if (!next) { armRest(); return }
      const period = 1000 / (get().final?.rate ?? 16)
      const loop = async (): Promise<void> => {
        if (!get().playing) return
        const t0 = performance.now()
        const n = get().final?.frames ?? 0
        const frame = n ? (get().frame + 1) % n : 0
        set({ frame })
        if (!show(frame, 'half') && !show(frame, 'full')) {       // not here yet: the clock waits for it (a first pass runs as fast as the frames come)
          wanted = { frame, side: 'half' }
          pump()
          while (inflight && get().playing && get().frame === frame) await inflight
        }
        if (!get().playing) return
        playTimer = window.setTimeout(() => void loop(), Math.max(0, period - (performance.now() - t0)))
      }
      playTimer = window.setTimeout(() => void loop(), period)
    },
    settle: () => { if (!get().playing && get().comp) request(get().frame, 'full') },
    tick: async () => {
      const { final, comp, playing, finalId } = get()
      if (finalId && comp) {                                                   // D118: a pass's job landed — the composition takes the layer's new source
        for (const j of Object.values(useSession.getState().jobs)) {
          if (j.kind === 'layer_pass' && j.origin?.ref === finalId && j.status === 'done' && !seenPasses.has(j.id)) { seenPasses.add(j.id); void get().syncSources() }
        }
      }
      if (!final || !comp || playing || inflight || wanted || queueBusy()) return
      for (let i = 0; i < final.frames; i++) {
        const frame = (get().frame + i) % final.frames
        if (!cache.has(key(comp.revision, frame, 'half'))) {
          set({ fetching: true })
          inflight = fetchFrame(final, comp.revision, frame, 'half').then(() => { set({ filled: count(), error: null }) }).catch((e: Error) => set({ error: e.message }))
            .finally(() => { inflight = null; set({ fetching: false }); if (wanted) pump() })   // V85: a seek asked during the idle fill is served now, not at the 300 ms settle
          await inflight
          return
        }
      }
    },
  }
})

// D121 (AW2): the Final level's transport — the composition's frames; the selected layer's keys as the marks (no work area at Final)
{
  const c = () => useComposition.getState()
  registerTransport('final', {
    ready: () => !!c().comp && !!c().final, playing: () => c().playing, play: (on) => c().togglePlay(on),
    frame: () => c().frame, seek: (f) => c().setFrame(f), step: (d) => c().step(d), home: () => c().home(), end: () => c().end(),
    marks: () => { const rate = c().final?.rate ?? 16; return Object.values(c().keysOf).flat().map((k) => Math.round(k.time * rate)) },
  })
}

/** U1 (D157, 06 §5.3): the composition per context (Shots: a shot version's final) — the final a context had open is opened again on returning. */
export const compositionContext = contextSlot<string | null>(() => useComposition.getState().finalId, (id) => { if (id && useComposition.getState().finalId !== id) void useComposition.getState().open(id) })
