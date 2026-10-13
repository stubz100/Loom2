// P17 (D83): the Sequence tab's state — the project's sequences (`timelines/<id>.json` on the server), the open one as a lane, the
// playhead, a command-pattern undo stack, and debounced saves that carry the document's revision (409 → reload, the change is lost
// and the toast says so). Project data lives here and on disk, never in component state.
import { create } from 'zustand'
import { ApiError, http, unwrap } from '../../../api/client'
import type { Clip, Timeline, TimelineClipIn } from '../../../api/types'
import { useSession } from '../../../store/session'
import { append, at, duration, move, remove, setOverlap, starts, trim, type Lane, type LaneClip } from './lane'

export type ExportFormat = 'edl' | 'fcpxml' | 'srt'

/** The server document as the pure lane the view and the maths use. */
export function laneOf(tl: Timeline): Lane {
  return { fps: tl.fps, clips: tl.clips.map((c) => ({ id: c.id, source: c.clip_id, in: c.in, out: c.out, ...(c.fps && c.fps !== tl.fps ? { fps: c.fps } : {}),
    ...(c.shot_id && c.shot_version ? { shot: { id: c.shot_id, version: c.shot_version, node: c.node_id ?? null } } : {}) })), overlaps: [...tl.overlaps] }
}
/** The lane back into the document's clip rows. */
export function clipsOf(lane: Lane): TimelineClipIn[] {
  return lane.clips.map((c) => ({ id: c.id, clip_id: c.source, in: c.in, out: c.out, fps: c.fps ?? null, shot_id: c.shot?.id ?? null, shot_version: c.shot?.version ?? null, node_id: c.shot?.node ?? null }))
}
/** A new lane clip from a Catalogue clip: the whole clip, its own rate kept when it differs from the lane's. */
export function laneClipFrom(clip: Clip, laneFps: number, shot?: { id: string; version: string; node: string | null }): LaneClip {
  return { id: `${clip.id}-${Date.now().toString(36)}`, source: clip.id, in: 0, out: clip.frames, ...(clip.fps !== laneFps ? { fps: clip.fps } : {}), ...(shot ? { shot } : {}) }
}

interface SequenceState {
  timelines: Timeline[]
  current: Timeline | null
  lane: Lane | null
  selected: number | null                 // clip index on the lane
  playhead: number
  playing: boolean
  pxPerFrame: number
  undo: Lane[]; redo: Lane[]
  saving: boolean
  lastExport: { format: ExportFormat; path: string } | null
  load: () => Promise<void>
  create: (name: string) => Promise<Timeline | null>
  open: (id: string | null) => Promise<void>
  rename: (name: string) => Promise<void>
  destroy: () => Promise<void>
  /** Apply a lane edit (undoable) and save. */
  apply: (fn: (lane: Lane) => Lane, label: string) => void
  undoEdit: () => void
  redoEdit: () => void
  addClip: (clip: Clip) => void
  /** 17 §3e: a shot version's clip, stamped with the shot, its version and its owner node (the Shots bin). */
  addShot: (clip: Clip, shot: { id: string; version: string; node: string | null }) => void
  removeClip: (i: number) => void
  moveClip: (from: number, to: number) => void
  trimClip: (i: number, edge: 'in' | 'out', delta: number, sourceLen: number) => void
  setDissolve: (i: number, frames: number) => void
  select: (i: number | null) => void
  setPlayhead: (f: number) => void
  togglePlay: (on?: boolean) => void
  zoom: (factor: number) => void
  exportAs: (format: ExportFormat) => Promise<void>
  /** P17 slice 2: the draft render as a CPU job; the clip lands in the bin and the Catalogue when it is done. */
  render: () => Promise<void>
}

let saveTimer: number | null = null
let saveSeq = 0

async function save(get: () => SequenceState, set: (p: Partial<SequenceState>) => void): Promise<void> {
  const { current, lane } = get()
  if (!current || !lane) return
  const seq = ++saveSeq
  set({ saving: true })
  try {
    const next = await unwrap(http.PUT('/timelines/{tl_id}', { params: { path: { tl_id: current.id } }, body: { ...current, clips: clipsOf(lane), overlaps: lane.overlaps } }))
    if (seq === saveSeq && get().current?.id === current.id) set({ current: next, timelines: get().timelines.map((t) => (t.id === next.id ? next : t)) })
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) {                                                  // the document moved under us: take the server's, drop the edit
      useSession.getState().toast('The sequence changed elsewhere — reloaded; your last change was not saved', 'error')
      await get().open(current.id)
    } else useSession.getState().toast(`Sequence not saved: ${err.detail ?? e}`, 'error')
  } finally { if (seq === saveSeq) set({ saving: false }) }
}

export const useSequence = create<SequenceState>()((set, get) => ({
  timelines: [], current: null, lane: null, selected: null, playhead: 0, playing: false, pxPerFrame: 3, undo: [], redo: [], saving: false, lastExport: null,

  load: async () => {
    try { set({ timelines: (await unwrap(http.GET('/timelines'))).items }) } catch { set({ timelines: [] }) }
  },
  create: async (name) => {
    try {
      const tl = await unwrap(http.POST('/timelines', { body: { name } }))
      set({ timelines: [tl, ...get().timelines] })
      await get().open(tl.id)
      return tl
    } catch (e) { useSession.getState().toast(`New sequence failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },
  open: async (id) => {
    if (!id) { set({ current: null, lane: null, selected: null, playhead: 0, playing: false, undo: [], redo: [] }); return }
    try {
      const tl = await unwrap(http.GET('/timelines/{tl_id}', { params: { path: { tl_id: id } } }))
      set({ current: tl, lane: laneOf(tl), selected: null, playhead: 0, playing: false, undo: [], redo: [], timelines: get().timelines.some((t) => t.id === tl.id) ? get().timelines.map((t) => (t.id === tl.id ? tl : t)) : [tl, ...get().timelines] })
    } catch (e) { useSession.getState().toast(`Open sequence failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  rename: async (name) => {
    const cur = get().current
    if (!cur || !name.trim()) return
    set({ current: { ...cur, name: name.trim() } })
    await save(get, set)
  },
  destroy: async () => {
    const cur = get().current
    if (!cur) return
    try {
      await unwrap(http.DELETE('/timelines/{tl_id}', { params: { path: { tl_id: cur.id } } }))
      set({ timelines: get().timelines.filter((t) => t.id !== cur.id) })
      await get().open(null)
    } catch (e) { useSession.getState().toast(`Delete failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },

  apply: (fn, label) => {
    const lane = get().lane
    if (!lane) return
    const next = fn(lane)
    if (next === lane) return
    set({ lane: next, undo: [...get().undo.slice(-63), lane], redo: [], playhead: Math.min(get().playhead, Math.max(0, duration(next) - 1)) })
    if (saveTimer) window.clearTimeout(saveTimer)
    saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300)
    void label
  },
  undoEdit: () => { const u = get().undo; if (!u.length || !get().lane) return; set({ lane: u[u.length - 1], undo: u.slice(0, -1), redo: [...get().redo, get().lane!] }); if (saveTimer) window.clearTimeout(saveTimer); saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300) },
  redoEdit: () => { const r = get().redo; if (!r.length || !get().lane) return; set({ lane: r[r.length - 1], redo: r.slice(0, -1), undo: [...get().undo, get().lane!] }); if (saveTimer) window.clearTimeout(saveTimer); saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300) },

  addClip: (clip) => { const fps = get().lane?.fps ?? 24; get().apply((l) => append(l, laneClipFrom(clip, fps)), 'add clip'); set({ selected: (get().lane?.clips.length ?? 1) - 1 }) },
  addShot: (clip, shot) => { const fps = get().lane?.fps ?? 24; get().apply((l) => append(l, laneClipFrom(clip, fps, shot)), 'add shot'); set({ selected: (get().lane?.clips.length ?? 1) - 1 }) },
  removeClip: (i) => { get().apply((l) => remove(l, i), 'remove clip'); set({ selected: null }) },
  moveClip: (from, to) => { get().apply((l) => move(l, from, to), 'move clip'); set({ selected: to }) },
  trimClip: (i, edge, delta, sourceLen) => get().apply((l) => trim(l, i, edge, delta, () => sourceLen), 'trim'),
  setDissolve: (i, frames) => get().apply((l) => setOverlap(l, i, frames), 'dissolve'),
  select: (i) => set({ selected: i }),
  setPlayhead: (f) => { const d = get().lane ? duration(get().lane!) : 0; set({ playhead: Math.max(0, Math.min(Math.max(0, d - 1), Math.round(f))) }) },
  togglePlay: (on) => set({ playing: on ?? !get().playing }),
  zoom: (factor) => set({ pxPerFrame: Math.max(0.25, Math.min(24, get().pxPerFrame * factor)) }),
  exportAs: async (format) => {
    const cur = get().current
    if (!cur) return
    try {
      const r = await unwrap(http.POST('/timelines/{tl_id}/export', { params: { path: { tl_id: cur.id } }, body: { format } }))
      set({ lastExport: { format, path: r.path } })
      useSession.getState().toast(`${format.toUpperCase()} written: ${r.path}`, 'success')
    } catch (e) { useSession.getState().toast(`Export failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  render: async () => {
    const cur = get().current
    if (!cur) return
    const s = useSession.getState()
    try {
      await unwrap(http.POST('/timelines/{tl_id}/render', { params: { path: { tl_id: cur.id } } }))
      s.toast('Draft render queued — the clip lands in the Clips bin when it is done (CPU, no engine)', 'success')
      await s.refreshAll()
    } catch (e) { s.toast(`Render failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
}))

export const seqActive = (): boolean => !!useSequence.getState().current
/** What the lane shows at the playhead (for the preview and the Inspector). */
export function shownNow(): ReturnType<typeof at> {
  const { lane, playhead } = useSequence.getState()
  return lane ? at(lane, playhead, starts(lane)) : null
}
