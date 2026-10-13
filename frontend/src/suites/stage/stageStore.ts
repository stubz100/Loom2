// P13 / ST1 (D81): the Stage suite's state — the project's stages (`stages/<id>.json` on the server), the open document, selection, the
// tool and view, a command-pattern undo stack over the document, and debounced saves that carry the document's revision (409 → reload,
// the change is lost and the toast says so). The three.js engine (engine.ts) renders from this store and reports edits back to it;
// project data never lives in the engine or in component state.
import { create } from 'zustand'
import { api, ApiError, http, sha256Hex, unwrap } from '../../api/client'
import { isDocumentPreview, type Asset, type DocumentPreview, type Job, type StageCamera, type StageDoc, type StageObject } from '../../api/types'
import { useSession } from '../../store/session'
import { clipFrames, EMPTY_KEYS, keyedFrames as keyedFramesOf, keyframesOf, sampleDoc, withKey, withoutKey, type CameraKey, type Keyframes, type ObjectKey } from './anim'
import { JOINTS, MANNEQUIN_PRESETS, POSES } from './builders'
import { mirrorJoints } from './ik'
import type { Keypoint } from './passes'

export interface PoseDef { preset?: string | null; joints: Record<string, number[]> }
// ---- ST3 (16 §3e / §7): the Shot tab ----
export interface ShotRef { asset_id: string; note?: string | null }
export interface ShotState { method: string; prompt_text: string; refs: ShotRef[]; count: number; tier: 'draft' | 'full'; use_as_is: boolean }
export interface RenderedPasses { size: { w: number; h: number }; blobs: Record<string, Blob>; keypoints: number[][][]; legend: Record<string, string> }
/** The document's record of a camera's rendered passes (stages/<id>.json `passes[]`). */
export interface PassesEntry { camera_id: string; revision: number; size: { w: number; h: number }; assets: Record<string, string>; keypoints: unknown[]; legend: Record<string, unknown>; rendered_at?: string }
export const DEFAULT_SHOT: ShotState = { method: 'clay', prompt_text: '', refs: [], count: 1, tier: 'draft', use_as_is: false }
const snap16 = (v: number) => Math.max(16, Math.round(v / 16) * 16)
const snap32 = (v: number) => Math.max(32, Math.round(v / 32) * 32)
// ---- ST4 (16 §8): keyframes and the clip ----
export type GuideKind = 'depth' | 'pose'
/** A rendered pass sequence recorded under a camera's passes entry (`guides[kind]`). */
export interface GuideEntry { asset_id: string; frames: number; fps: number; size: { w: number; h: number }; range: { start: number; end: number }; revision: number; rendered_at?: string }
export type SequenceRenderer = (frames: { cam: StageCamera; doc: StageDoc }[], w: number, h: number, kind: GuideKind, restoreDoc: StageDoc, onProgress?: (done: number, total: number) => void) => Promise<{ blobs: Blob[]; keypoints: Keypoint[][][] }>
/** A result of this stage: a shot carries `stage_id` in its params, a clip (ST4) only its job's origin. */
const ofStage = (a: Asset, stageId: string): boolean => (a.params as { stage_id?: string }).stage_id === stageId || (a.origin?.suite === 'stage' && a.origin?.ref === stageId)
const withCameraKey = (d: StageDoc, camId: string, key: CameraKey): StageDoc => { const k = keyframesOf(d); return { ...d, keyframes: { ...k, camera: { ...k.camera, [camId]: withKey(k.camera[camId], key) } } } }
const withObjectKey = (d: StageDoc, id: string, key: ObjectKey): StageDoc => { const k = keyframesOf(d); return { ...d, keyframes: { ...k, objects: { ...k.objects, [id]: withKey(k.objects[id], key) } } } }
/** The full joint map a figure shows: the preset's angles under the figure's own edits (ST2). */
export function effectiveJoints(o: StageObject): Record<string, number[]> {
  const preset = POSES[o.pose?.preset ?? 'stand'] ?? POSES.stand
  const out: Record<string, number[]> = {}
  for (const j of JOINTS) out[j] = [...(o.pose?.joints?.[j] ?? preset.j[j] ?? [0, 0, 0])]
  return out
}

export type Tool = 'select' | 'move' | 'rotate' | 'scale'
export type View = 'free' | 'camera'
export type Kind = StageObject['kind']
export interface Transform { pos: number[]; rot: number[]; scale: number[] }

const newId = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`
const NAMES: Record<string, string> = { mannequin: 'Figure', set: 'Set', prop: 'Prop', plane: 'Image', mesh: 'Mesh', light: 'Light' }

interface StageState {
  stages: StageDoc[]
  current: StageDoc | null
  selected: string | null
  tool: Tool
  snap: boolean
  view: View
  guides: boolean
  undo: StageDoc[]; redo: StageDoc[]
  saving: boolean
  frameRequest: { ids: string[] | null; n: number }         // the viewport frames these (null = everything) when n changes
  selectedJoint: string | null                              // ST2: the joint the rotate gizmo is on
  userPoses: Record<string, PoseDef>                        // ST2: the project's saved poses (stages/poses.json)
  selectJoint: (j: string | null) => void
  setJoints: (id: string, joints: Record<string, number[]>) => void
  applyPose: (id: string, preset: string | null, joints?: Record<string, number[]>) => void
  mirrorPose: (id: string) => void
  resetPose: (id: string) => void
  loadPoses: () => Promise<void>
  savePose: (name: string, id: string) => Promise<void>
  deletePose: (name: string) => Promise<void>
  // ST3: the Shot tab — passes rendered by the viewport, uploaded as assets; the StageShot job; its results
  shot: ShotState
  shotPreview: DocumentPreview | null
  shotPreviewError: string | null
  rendering: boolean
  shots: Asset[]                                            // this stage's stage-shot results, newest first
  passRenderer: ((cam: StageCamera, w: number, h: number) => Promise<RenderedPasses>) | null   // the mounted viewport registers it
  setShot: (patch: Partial<ShotState>) => void
  addShotRef: (assetId: string) => void
  removeShotRef: (assetId: string) => void
  refreshShotPreview: () => Promise<void>
  passesEntry: () => PassesEntry | null                     // the active camera's passes, if rendered
  passesStale: () => boolean                                // the document moved on since they were rendered (or a save is pending)
  shotSize: () => [number, number]                          // the recipe size: the tier's height at the project's aspect, snapped to 16
  renderPasses: () => Promise<boolean>
  generateShot: () => Promise<Job[] | null>
  loadShots: () => Promise<void>
  onAssetCreated: (a: Asset) => void
  // ST4: keyframes (the document's `keyframes` and `range`), the frame the viewport shows, the pass sequence and the clip
  frame: number
  playing: boolean
  guideKind: GuideKind
  shotStart: string | null                                  // the shot (a stage-shot image) the clip starts from
  rendered: { done: number; total: number } | null         // sequence progress
  sequenceRenderer: SequenceRenderer | null                 // the mounted viewport registers it
  keys: () => Keyframes
  keyedFrames: () => number[]
  sampledDoc: () => StageDoc | null                         // the document at `frame` (what the viewport shows)
  setFrame: (f: number) => void
  setPlaying: (on: boolean) => void
  setRange: (start: number, end: number) => void
  keyCamera: () => void
  keyObject: (id: string) => void
  removeKeyAt: (frame: number) => void
  setGuideKind: (k: GuideKind) => void
  setShotStart: (id: string | null) => void
  guideEntry: () => GuideEntry | null
  guideSize: () => [number, number]                         // the clip model's grid at the project's aspect
  renderGuide: () => Promise<boolean>
  animateShot: () => Promise<Job[] | null>
  load: () => Promise<void>
  create: (name: string) => Promise<StageDoc | null>
  open: (id: string | null) => Promise<void>
  rename: (name: string) => Promise<void>
  destroy: () => Promise<void>
  /** Apply a document edit (undoable) and save. */
  apply: (fn: (doc: StageDoc) => StageDoc, label: string) => void
  undoEdit: () => void
  redoEdit: () => void
  select: (id: string | null) => void
  setTool: (t: Tool) => void
  setSnap: (on: boolean) => void
  setView: (v: View) => void
  setGuides: (on: boolean) => void
  addObject: (kind: Kind, preset?: string | null, pos?: number[], assetId?: string | null) => string | null
  updateObject: (id: string, patch: Partial<StageObject>) => void
  setTransform: (id: string, t: Transform) => void
  removeObject: (id: string) => void
  duplicateObject: (id: string) => void
  addCamera: () => void
  updateCamera: (id: string, patch: Partial<StageCamera>) => void
  removeCamera: (id: string) => void
  setActiveCamera: (id: string) => void
  frameView: (ids: string[] | null) => void                // frame the selection (or everything) in the viewport
  object: (id: string | null) => StageObject | undefined
  activeCamera: () => StageCamera | undefined
}

let saveTimer: number | null = null
let saveSeq = 0

async function save(get: () => StageState, set: (p: Partial<StageState>) => void): Promise<void> {
  const cur = get().current
  if (!cur) return
  const seq = ++saveSeq
  set({ saving: true })
  try {
    const next = await unwrap(http.PUT('/stages/{st_id}', { params: { path: { st_id: cur.id } }, body: cur as never }))
    if (seq === saveSeq && get().current?.id === cur.id) {
      set({ current: { ...get().current!, revision: next.revision, updated_at: next.updated_at }, stages: get().stages.map((s) => (s.id === next.id ? next : s)) })
    }
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) {
      useSession.getState().toast('The stage changed elsewhere — reloaded; your last change was not saved', 'error')
      await get().open(cur.id)
    } else useSession.getState().toast(`Stage not saved: ${err.detail ?? e}`, 'error')
  } finally { if (seq === saveSeq) set({ saving: false }) }
}

function schedule(get: () => StageState, set: (p: Partial<StageState>) => void): void {
  if (saveTimer) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300)
}

/** ST3: a pending or in-flight save completes before the passes are rendered, so they carry the document's real revision. */
async function flushSave(get: () => StageState, set: (p: Partial<StageState>) => void): Promise<void> {
  if (saveTimer) { window.clearTimeout(saveTimer); saveTimer = null; await save(get, set) }
  for (let i = 0; i < 100 && get().saving; i++) await new Promise((r) => window.setTimeout(r, 50))
}

let shotPreviewSeq = 0

export const useStage = create<StageState>()((set, get) => ({
  stages: [], current: null, selected: null, tool: 'select', snap: false, view: 'free', guides: true, undo: [], redo: [], saving: false,
  frameRequest: { ids: null, n: 0 }, selectedJoint: null, userPoses: {},
  shot: DEFAULT_SHOT, shotPreview: null, shotPreviewError: null, rendering: false, shots: [], passRenderer: null,
  frame: 0, playing: false, guideKind: 'depth', shotStart: null, rendered: null, sequenceRenderer: null,

  // ---- ST4: keyframes and the clip ----
  keys: () => { const cur = get().current; return cur ? keyframesOf(cur) : EMPTY_KEYS },
  keyedFrames: () => { const cur = get().current; return cur ? keyedFramesOf(keyframesOf(cur), cur.active_camera) : [] },
  sampledDoc: () => { const cur = get().current; return cur ? sampleDoc(cur, get().frame) : null },
  setFrame: (f) => set({ frame: Math.max(0, Math.min(100000, Math.round(f))) }),
  setPlaying: (playing) => set({ playing }),
  setRange: (start, end) => { const s = Math.max(0, Math.round(start)); const e = Math.max(s + 1, Math.round(end)); get().apply((d) => ({ ...d, range: { start: s, end: e } }), 'range') },
  keyCamera: () => {
    const sd = get().sampledDoc(); const cam = sd?.cameras.find((c) => c.id === sd.active_camera)
    if (!sd || !cam) return
    get().apply((d) => withCameraKey(d, cam.id, { frame: get().frame, ease: 'ease', pos: [...cam.pos], target: [...cam.target], focal_mm: cam.focal_mm }), 'key camera')
  },
  keyObject: (id) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id)
    if (!o) return
    get().apply((d) => withObjectKey(d, id, { frame: get().frame, ease: 'ease', transform: { pos: [...o.transform.pos], rot: [...o.transform.rot], scale: [...o.transform.scale] }, pose: o.pose ? { preset: o.pose.preset, joints: { ...o.pose.joints } } : null }), 'key object')
  },
  removeKeyAt: (frame) => get().apply((d) => {
    const k = keyframesOf(d)
    const camera = Object.fromEntries(Object.entries(k.camera).map(([id, ks]) => [id, d.active_camera === id ? withoutKey(ks, frame) : ks]).filter(([, ks]) => (ks as CameraKey[]).length))
    const objects = Object.fromEntries(Object.entries(k.objects).map(([id, ks]) => [id, withoutKey(ks, frame)]).filter(([, ks]) => (ks as ObjectKey[]).length))
    return { ...d, keyframes: { camera, objects } }
  }, 'remove keys'),
  setGuideKind: (guideKind) => set({ guideKind }),
  setShotStart: (shotStart) => set({ shotStart }),
  guideEntry: () => { const e = get().passesEntry() as (PassesEntry & { guides?: Record<string, GuideEntry> }) | null; return e?.guides?.[get().guideKind] ?? null },
  guideSize: () => {
    const cur = get().current
    const aspect = cur ? cur.size.w / Math.max(1, cur.size.h) : 16 / 9
    const base = useSession.getState().capabilities?.stage?.clip?.size
    const h = base && base.length === 2 ? base[1] : 576
    return [snap32(h * aspect), snap32(h)]
  },
  renderGuide: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera(), render = get().sequenceRenderer
    if (!cur || !cam) { s.toast('No camera to render the sequence from', 'error'); return false }
    if (!render) { s.toast('The viewport is not ready to render', 'error'); return false }
    set({ rendering: true, rendered: { done: 0, total: 0 } })
    try {
      await flushSave(get, set)
      const doc = get().current
      if (!doc) return false
      const kind = get().guideKind
      const { start } = doc.range
      const n = clipFrames(doc.range.start, doc.range.end, 8)
      const frames = Array.from({ length: n }, (_, i) => { const d = sampleDoc(doc, start + i); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d } })
      const [w, h] = get().guideSize()
      const out = await render(frames, w, h, kind, sampleDoc(doc, get().frame), (done, total) => set({ rendered: { done, total } }))
      const shas: string[] = []
      for (const blob of out.blobs) {
        const sha = await sha256Hex(await blob.arrayBuffer())
        await api.putBlob(sha, blob)
        shas.push(sha)
      }
      const next = await unwrap(http.POST('/stages/{st_id}/guide', { params: { path: { st_id: doc.id } },
        body: { camera_id: cam.id, revision: doc.revision, kind, fps: doc.size.fps, size: { w, h }, range: { start, end: start + n - 1 }, frames: shas, keypoints: out.keypoints as never } }))
      set({ current: next, stages: get().stages.map((x) => (x.id === next.id ? next : x)) })
      s.toast(`${kind === 'depth' ? 'Depth' : 'Pose'} sequence rendered: ${n} frames at ${w}×${h}, ${doc.size.fps} fps`, 'success')
      return true
    } catch (e) { s.toast(`Render sequence failed: ${(e as ApiError).detail ?? e}`, 'error'); return false } finally { set({ rendering: false, rendered: null }) }
  },
  animateShot: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera(), g = get().guideEntry(), start = get().shotStart
    const model = s.capabilities?.stage?.clip?.model_id
    if (!cur || !cam || !g || !start || !model) { s.toast(!g ? 'Render the sequence first' : !start ? 'Pick a shot to start from (click one of the results)' : 'No clip model in this build', 'error'); return null }
    const recipe = { kind: 'i2v', model_id: model, start_asset: start, prompt_text: get().shot.prompt_text.trim(), frames: g.frames, fps: g.fps, width: g.size.w, height: g.size.h,
      preset: 'draft', guide: { asset_id: g.asset_id, kind: get().guideKind, strength: 1.0 }, seeds: [0] }
    try {
      const jobs = await unwrap(http.POST('/jobs', { body: { recipe: recipe as never, stage: false, origin: { suite: 'stage', surface: 'clip', ref: cur.id, payload: { camera_id: cam.id } } } }))
      s.toast(`Queued the clip of ${cam.name}: ${g.frames} frames on the ${get().guideKind} sequence`, 'success')
      return jobs.jobs
    } catch (e) { s.toast(`Animate failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },

  // ---- ST3: the Shot tab ----
  setShot: (patch) => { set({ shot: { ...get().shot, ...patch } }); void get().refreshShotPreview() },
  addShotRef: (assetId) => { const refs = get().shot.refs; if (refs.some((r) => r.asset_id === assetId)) return; get().setShot({ refs: [...refs, { asset_id: assetId, note: null }] }) },
  removeShotRef: (assetId) => get().setShot({ refs: get().shot.refs.filter((r) => r.asset_id !== assetId) }),
  passesEntry: () => { const cur = get().current; const cam = get().activeCamera(); if (!cur || !cam) return null; return ((cur.passes as unknown as PassesEntry[]).find((p) => p.camera_id === cam.id)) ?? null },
  passesStale: () => { const e = get().passesEntry(); const cur = get().current; if (!e || !cur) return true; return cur.revision > e.revision + 1 || saveTimer !== null || get().saving },
  shotSize: () => {
    const cur = get().current
    const aspect = cur ? cur.size.w / Math.max(1, cur.size.h) : 16 / 9
    const h = get().shot.tier === 'full' ? (cur?.size.h ?? 1080) : 720
    return [snap16(h * aspect), snap16(h)]
  },
  refreshShotPreview: async () => {
    const cur = get().current, cam = get().activeCamera()
    if (!cur || !cam) { set({ shotPreview: null, shotPreviewError: null }); return }
    const seq = ++shotPreviewSeq
    const sh = get().shot
    const entry = get().passesEntry()
    const [width, height] = get().shotSize()
    const recipe = { kind: 'stage_shot', stage_id: cur.id, camera_id: cam.id, passes: entry?.assets ?? { clay: 'pending', pose: 'pending' }, method: sh.method,
      prompt_text: sh.prompt_text.trim(), refs: sh.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })), seeds: [0], width, height }
    try {
      const pv = await unwrap(http.POST('/recipes/preview', { body: { recipe: recipe as never } }))
      if (seq === shotPreviewSeq) set({ shotPreview: isDocumentPreview(pv) ? pv : null, shotPreviewError: null })
    } catch (e) {
      if (seq === shotPreviewSeq) set({ shotPreview: null, shotPreviewError: (e as ApiError).detail ?? String(e) })
    }
  },
  renderPasses: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera(), render = get().passRenderer
    if (!cur || !cam) { s.toast('No camera to render the passes from', 'error'); return false }
    if (!render) { s.toast('The viewport is not ready to render', 'error'); return false }
    set({ rendering: true })
    try {
      await flushSave(get, set)
      const doc = get().current
      if (!doc) return false
      const [w, h] = get().shotSize()
      const out = await render(cam, w, h)
      const passes: Record<string, string> = {}
      for (const [name, blob] of Object.entries(out.blobs)) {
        const sha = await sha256Hex(await blob.arrayBuffer())
        await api.putBlob(sha, blob)
        passes[name] = sha
      }
      const next = await unwrap(http.POST('/stages/{st_id}/passes', { params: { path: { st_id: doc.id } },
        body: { camera_id: cam.id, revision: doc.revision, size: out.size, passes, keypoints: out.keypoints as never, legend: out.legend as never } }))
      set({ current: next, stages: get().stages.map((x) => (x.id === next.id ? next : x)) })
      s.toast(`Passes rendered for ${cam.name} at ${w}×${h}`, 'success')
      void get().refreshShotPreview()
      return true
    } catch (e) { s.toast(`Render passes failed: ${(e as ApiError).detail ?? e}`, 'error'); return false } finally { set({ rendering: false }) }
  },
  generateShot: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera()
    if (!cur || !cam) return null
    let entry = get().passesEntry()
    if (!entry || (get().passesStale() && !get().shot.use_as_is)) {
      if (!(await get().renderPasses())) return null
      entry = get().passesEntry()
    }
    if (!entry) return null
    const sh = get().shot
    const [width, height] = get().shotSize()
    const recipe = { kind: 'stage_shot', stage_id: cur.id, camera_id: cam.id, passes: entry.assets, method: sh.method, prompt_text: sh.prompt_text.trim(),
      refs: sh.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })), seeds: Array.from({ length: Math.max(1, Math.min(4, sh.count)) }, () => 0), width, height }
    try {
      const jobs = await unwrap(http.POST('/jobs', { body: { recipe: recipe as never, stage: false, origin: { suite: 'stage', surface: 'shot', ref: cur.id, payload: { camera_id: cam.id } } } }))
      s.toast(`Queued ${jobs.jobs.length} shot${jobs.jobs.length > 1 ? 's' : ''} of ${cam.name}`, 'success')
      return jobs.jobs
    } catch (e) { s.toast(`Shot failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },
  loadShots: async () => {
    const cur = get().current
    if (!cur) { set({ shots: [] }); return }
    try {
      const r = await unwrap(http.GET('/assets', { params: { query: { suite: 'stage', sort: 'created_desc', limit: 60 } } }))
      set({ shots: (r.items as Asset[]).filter((a) => a.lineage_kind === 'stage-shot' && ofStage(a, cur.id)) })
    } catch { set({ shots: [] }) }
  },
  onAssetCreated: (a) => {
    const cur = get().current
    if (!cur || a.lineage_kind !== 'stage-shot' || !ofStage(a, cur.id) || get().shots.some((x) => x.id === a.id)) return
    set({ shots: [a, ...get().shots] })
  },

  selectJoint: (j) => set({ selectedJoint: j }),
  setJoints: (id, joints) => {
    const o = get().object(id)
    if (!o || JSON.stringify(effectiveJoints(o)) === JSON.stringify(joints)) return        // a gizmo click without a turn commits nothing (no undo entry)
    get().apply((d) => ({ ...d, objects: d.objects.map((x) => (x.id === id ? { ...x, pose: { preset: x.pose?.preset ?? 'stand', joints } } : x)) }), 'pose')
  },
  applyPose: (id, preset, joints = {}) => { get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, pose: { preset: preset ?? 'stand', joints } } : o)) }), 'pose preset'); set({ selectedJoint: null }) },
  mirrorPose: (id) => { const o = get().object(id); if (o) get().setJoints(id, mirrorJoints(effectiveJoints(o))) },
  resetPose: (id) => get().applyPose(id, 'stand', {}),
  loadPoses: async () => { try { set({ userPoses: (await unwrap(http.GET('/stages/poses'))).poses as unknown as Record<string, PoseDef> }) } catch { set({ userPoses: {} }) } },
  savePose: async (name, id) => {
    const o = get().object(id)
    if (!o || !name.trim()) return
    const poses = { ...get().userPoses, [name.trim()]: { preset: o.pose?.preset ?? 'stand', joints: effectiveJoints(o) } }
    try { set({ userPoses: (await unwrap(http.PUT('/stages/poses', { body: { poses: poses as never } }))).poses as unknown as Record<string, PoseDef> }); useSession.getState().toast(`Pose "${name.trim()}" saved to the project`, 'success') }
    catch (e) { useSession.getState().toast(`Save pose failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  deletePose: async (name) => {
    const poses = { ...get().userPoses }
    delete poses[name]
    try { set({ userPoses: (await unwrap(http.PUT('/stages/poses', { body: { poses: poses as never } }))).poses as unknown as Record<string, PoseDef> }) }
    catch (e) { useSession.getState().toast(`Delete pose failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },

  load: async () => { try { set({ stages: (await unwrap(http.GET('/stages'))).items }) } catch { set({ stages: [] }) } },
  create: async (name) => {
    try {
      const st = await unwrap(http.POST('/stages', { body: { name } }))
      set({ stages: [st, ...get().stages] })
      await get().open(st.id)
      return st
    } catch (e) { useSession.getState().toast(`New stage failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },
  open: async (id) => {
    if (!id) { set({ current: null, selected: null, undo: [], redo: [] }); return }
    try {
      const st = await unwrap(http.GET('/stages/{st_id}', { params: { path: { st_id: id } } }))
      set({ current: st, selected: null, undo: [], redo: [], stages: get().stages.some((s) => s.id === st.id) ? get().stages.map((s) => (s.id === st.id ? st : s)) : [st, ...get().stages],
        shot: { ...get().shot, refs: [], use_as_is: false }, shots: [], frame: st.range?.start ?? 0, playing: false, shotStart: null })
      void get().loadShots(); void get().refreshShotPreview()
    } catch (e) { useSession.getState().toast(`Open stage failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  rename: async (name) => { const cur = get().current; if (!cur || !name.trim()) return; set({ current: { ...cur, name: name.trim() } }); await save(get, set) },
  destroy: async () => {
    const cur = get().current
    if (!cur) return
    try {
      await unwrap(http.DELETE('/stages/{st_id}', { params: { path: { st_id: cur.id } } }))
      set({ stages: get().stages.filter((s) => s.id !== cur.id) })
      await get().open(null)
    } catch (e) { useSession.getState().toast(`Delete failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },

  apply: (fn, label) => {
    const cur = get().current
    if (!cur) return
    const next = fn(cur)
    if (next === cur) return
    set({ current: next, undo: [...get().undo.slice(-63), cur], redo: [] })
    schedule(get, set)
    void label
  },
  undoEdit: () => { const u = get().undo; const cur = get().current; if (!u.length || !cur) return; set({ current: { ...u[u.length - 1], revision: cur.revision }, undo: u.slice(0, -1), redo: [...get().redo, cur] }); schedule(get, set) },
  redoEdit: () => { const r = get().redo; const cur = get().current; if (!r.length || !cur) return; set({ current: { ...r[r.length - 1], revision: cur.revision }, redo: r.slice(0, -1), undo: [...get().undo, cur] }); schedule(get, set) },
  select: (id) => set({ selected: id, selectedJoint: null }),
  setTool: (tool) => set({ tool }),
  setSnap: (snap) => set({ snap }),
  setView: (view) => set({ view }),
  setGuides: (guides) => set({ guides }),

  addObject: (kind, preset = null, pos, assetId = null) => {
    const cur = get().current
    if (!cur) return null
    const id = newId(kind === 'mannequin' ? 'fig' : kind)
    const n = cur.objects.filter((o) => o.kind === kind).length + 1
    const name = `${NAMES[kind] ?? kind} ${n}`
    const scale = kind === 'mannequin' ? (MANNEQUIN_PRESETS[preset ?? 'adult']?.scale ?? 1) : 1
    const o: StageObject = { id, kind, name, preset, asset_id: assetId, transform: { pos: pos ?? [0, 0, 0], rot: [0, 0, 0], scale: [scale, scale, scale] }, parent: null,
      locked: false, visible: true, colour_id: (cur.objects.length % 12) + 1, pose: kind === 'mannequin' ? { preset: 'stand', joints: {} } : null, billboard: kind === 'plane' }
    get().apply((d) => ({ ...d, objects: [...d.objects, o] }), 'add')
    set({ selected: id })
    return id
  },
  updateObject: (id, patch) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, ...patch } : o)) }), 'edit'),
  setTransform: (id, t) => {
    const cur = get().current
    if (cur && keyframesOf(cur).objects[id]?.length) {                   // ST4: a keyed object takes the edit as a key at this frame
      const o = get().sampledDoc()?.objects.find((x) => x.id === id)
      get().apply((d) => withObjectKey(d, id, { frame: get().frame, ease: 'ease', transform: t, pose: o?.pose ? { preset: o.pose.preset, joints: { ...o.pose.joints } } : null }), 'key object')
      return
    }
    get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, transform: t } : o)) }), 'transform')
  },
  removeObject: (id) => {
    get().apply((d) => {
      const gone = new Set<string>([id])
      let grew = true
      while (grew) { grew = false; for (const o of d.objects) if (o.parent && gone.has(o.parent) && !gone.has(o.id)) { gone.add(o.id); grew = true } }
      return { ...d, objects: d.objects.filter((o) => !gone.has(o.id)) }
    }, 'remove')
    if (get().selected === id) set({ selected: null })
  },
  duplicateObject: (id) => {
    const src = get().object(id)
    if (!src) return
    const nid = newId(src.kind === 'mannequin' ? 'fig' : src.kind)
    const copy: StageObject = { ...src, id: nid, name: `${src.name} copy`, transform: { ...src.transform, pos: [src.transform.pos[0] + 0.6, src.transform.pos[1], src.transform.pos[2]] }, locked: false }
    get().apply((d) => ({ ...d, objects: [...d.objects, copy] }), 'duplicate')
    set({ selected: nid })
  },
  addCamera: () => {
    const cur = get().current
    if (!cur) return
    const base = get().activeCamera()
    const id = newId('cam')
    const cam: StageCamera = { id, name: `Camera ${cur.cameras.length + 1}`, pos: base ? [...base.pos] : [0, 1.5, 4], target: base ? [...base.target] : [0, 1, 0], roll: 0, focal_mm: base?.focal_mm ?? 35, sensor_mm: 36 }
    get().apply((d) => ({ ...d, cameras: [...d.cameras, cam], active_camera: id }), 'add camera')
  },
  updateCamera: (id, patch) => {
    const cur = get().current
    const keyed = 'pos' in patch || 'target' in patch || 'focal_mm' in patch
    if (cur && keyed && keyframesOf(cur).camera[id]?.length) {           // ST4: a keyed camera takes a move as a key at this frame
      const cam = get().sampledDoc()?.cameras.find((c) => c.id === id)
      if (cam) { get().apply((d) => withCameraKey(d, id, { frame: get().frame, ease: 'ease', pos: [...(patch.pos ?? cam.pos)], target: [...(patch.target ?? cam.target)], focal_mm: patch.focal_mm ?? cam.focal_mm }), 'key camera'); return }
    }
    get().apply((d) => ({ ...d, cameras: d.cameras.map((c) => (c.id === id ? { ...c, ...patch } : c)) }), 'camera')
  },
  removeCamera: (id) => get().apply((d) => {
    if (d.cameras.length <= 1) return d
    const cameras = d.cameras.filter((c) => c.id !== id)
    return { ...d, cameras, active_camera: d.active_camera === id ? cameras[0].id : d.active_camera }
  }, 'remove camera'),
  setActiveCamera: (id) => get().apply((d) => (d.active_camera === id ? d : { ...d, active_camera: id }), 'active camera'),
  frameView: (ids) => set({ frameRequest: { ids, n: get().frameRequest.n + 1 } }),
  object: (id) => (id ? get().current?.objects.find((o) => o.id === id) : undefined),
  activeCamera: () => { const c = get().current; return c?.cameras.find((x) => x.id === c.active_camera) ?? c?.cameras[0] },
}))

export const st = () => useStage.getState()
