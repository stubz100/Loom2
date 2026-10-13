// P13 / ST1 (D81): the Stage suite's state — the project's stages (`stages/<id>.json` on the server), the open document, selection, the
// tool and view, a command-pattern undo stack over the document, and debounced saves that carry the document's revision (409 → reload,
// the change is lost and the toast says so). The three.js engine (engine.ts) renders from this store and reports edits back to it;
// project data never lives in the engine or in component state.
import { create } from 'zustand'
import { ApiError, http, unwrap } from '../../api/client'
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import { useSession } from '../../store/session'
import { JOINTS, MANNEQUIN_PRESETS, POSES } from './builders'
import { mirrorJoints } from './ik'

export interface PoseDef { preset?: string | null; joints: Record<string, number[]> }
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
  frame: (ids: string[] | null) => void
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

export const useStage = create<StageState>()((set, get) => ({
  stages: [], current: null, selected: null, tool: 'select', snap: false, view: 'free', guides: true, undo: [], redo: [], saving: false,
  frameRequest: { ids: null, n: 0 }, selectedJoint: null, userPoses: {},

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
      set({ current: st, selected: null, undo: [], redo: [], stages: get().stages.some((s) => s.id === st.id) ? get().stages.map((s) => (s.id === st.id ? st : s)) : [st, ...get().stages] })
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
  setTransform: (id, t) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, transform: t } : o)) }), 'transform'),
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
  updateCamera: (id, patch) => get().apply((d) => ({ ...d, cameras: d.cameras.map((c) => (c.id === id ? { ...c, ...patch } : c)) }), 'camera'),
  removeCamera: (id) => get().apply((d) => {
    if (d.cameras.length <= 1) return d
    const cameras = d.cameras.filter((c) => c.id !== id)
    return { ...d, cameras, active_camera: d.active_camera === id ? cameras[0].id : d.active_camera }
  }, 'remove camera'),
  setActiveCamera: (id) => get().apply((d) => (d.active_camera === id ? d : { ...d, active_camera: id }), 'active camera'),
  frame: (ids) => set({ frameRequest: { ids, n: get().frameRequest.n + 1 } }),
  object: (id) => (id ? get().current?.objects.find((o) => o.id === id) : undefined),
  activeCamera: () => { const c = get().current; return c?.cameras.find((x) => x.id === c.active_camera) ?? c?.cameras[0] },
}))

export const st = () => useStage.getState()
