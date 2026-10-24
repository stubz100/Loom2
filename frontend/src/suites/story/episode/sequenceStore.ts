// P17 (D83): the Sequence tab's state — the project's sequences (`timelines/<id>.json` on the server), the open one as a lane, the
// playhead, a command-pattern undo stack, and debounced saves that carry the document's revision (409 → reload, the change is lost
// and the toast says so). Project data lives here and on disk, never in component state.
import { create } from 'zustand'
import { ApiError, http, unwrap } from '../../../api/client'
import type { Clip, CutEdited, CutTracks, Job, Timeline, TimelineClipIn, TrackRole, TrackStrip, VstPlugin, VstPluginList } from '../../../api/types'
import { useSession } from '../../../store/session'
import { DEV_HOOKS } from '../../../devHooks'
import { append, at, duration, move, remove, setOverlap, starts, trim, type Lane, type LaneClip, chainIn } from './lane'
import { endOf, type CutTool, type Step } from './cut'

export type ExportFormat = 'edl' | 'fcpxml' | 'srt' | 'resolve'          // D125 (S14): resolve = the three and markers.txt in one folder named after the cut

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
export function laneClipFrom(clip: Clip, laneFps: number, shot?: { id: string; version: string; node: string | null }, startAt = 0): LaneClip {
  return { id: `${clip.id}-${Date.now().toString(36)}`, source: clip.id, in: startAt, out: clip.frames, ...(clip.fps !== laneFps ? { fps: clip.fps } : {}), ...(shot ? { shot } : {}) }
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
  /** D125 (S13): the Assemble sheet — a new cut from a route (`tlId` null) or the open cut assembled again from its route. */
  assembleFor: { tlId: string | null } | null
  setAssembleFor: (v: { tlId: string | null } | null) => void
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
  /** P17's draft (a silent clip) or, RC3, the movie (`movie`: an MP4 with the voice lane in the cut's folder and the Catalogue). */
  render: (movie?: boolean) => Promise<void>
  // ---- CE2 (D126, proto01_animate 30 §12): a FilmCraft cut's tracks and the editor's changes, each a FilmCraft command on the server
  tracks: CutTracks | null
  tool: CutTool
  selClip: number | null                  // a clip on the tracks (FilmCraft's id)
  selTrack: number | null                 // D127: a track (its header clicked): the Inspector shows its strip; a clip's selection clears it
  cutBusy: boolean
  loadTracks: () => Promise<void>
  cutEdit: (steps: Step[]) => Promise<boolean>
  cutPlace: (body: { clip_id?: string; asset_id?: string; shot_id?: string | null; shot_version?: string | null; node_id?: string | null; track: string | number; frame: number }) => Promise<boolean>
  cutReplace: (clip: number, take: { clip_id: string; shot_id?: string | null; shot_version?: string | null; node_id?: string | null }) => Promise<boolean>
  cutUndo: (redo?: boolean) => Promise<void>
  /** D127: an audio track's strip (what changes; the rest stays) and its role (Settings › Audio's strip for it). */
  cutStrip: (track: number, change: Partial<TrackStrip>) => Promise<boolean>
  cutRole: (track: number, role: TrackRole | null) => Promise<boolean>
  /** AU4: an audio track's chain — add an effect, remove, move, bypass — and an effect's own editor (it answers when its window closes). */
  cutFx: (track: number, change: { op: 'add' | 'remove' | 'move' | 'bypass'; plugin?: Pick<VstPlugin, 'bundle' | 'uid' | 'name' | 'vendor'>; fx?: string; to?: number; bypass?: boolean }) => Promise<boolean>
  cutFxEditor: (track: number, fx: string) => Promise<void>
  fxOpen: string | null                   // the effect whose window is open
  fxPicker: number | null                 // the track the effect list is open for
  fxPlugins: VstPluginList | null         // the installed effects (loaded when the list first opens; the server keeps the scan)
  fxScanning: boolean
  /** The list opens for `track` (none: closes); the installed effects are fetched the first time, or scanned again on `rescan`. */
  setFxPicker: (track: number | null, rescan?: boolean) => void
  setTool: (tool: CutTool) => void
  selectClip: (id: number | null) => void
  selectTrack: (id: number | null) => void
}

/** CE2: the open cut is a FilmCraft project (edited by commands, its tracks read from it). */
export const isCut = (): boolean => !!useSequence.getState().current?.file

let saveTimer: number | null = null
let saveSeq = 0

async function save(get: () => SequenceState, set: (p: Partial<SequenceState>) => void): Promise<void> {
  const { current, lane } = get()
  if (!current || !lane) return
  const seq = ++saveSeq
  set({ saving: true })
  try {
    const next = await unwrap(http.PUT('/timelines/{tl_id}', { params: { path: { tl_id: current.id } }, body: { ...current, clips: clipsOf(lane), overlaps: lane.overlaps } }))
    if (seq === saveSeq && get().current?.id === current.id) {
      set({ current: next, timelines: get().timelines.map((t) => (t.id === next.id ? next : t)) })
      if (next.file) {                                                           // CE2: an Assemble (or a cut's first change) rewrote V1 — its lane is
        set({ lane: laneOf(next) })                                              // the server's now (FilmCraft's clip ids: Update and the badges need them)
        await get().loadTracks()
      }
    }
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) {                                                  // the document moved under us: take the server's, drop the edit
      useSession.getState().toast('The cut changed elsewhere — reloaded; your last change was not saved', 'error')
      await get().open(current.id)
    } else useSession.getState().toast(`Cut not saved: ${err.detail ?? e}`, 'error')
  } finally { if (seq === saveSeq) set({ saving: false }) }
}

/** CE2: a reply of the editor's routes — the record, the lane it shows and the tracks, together. */
function applyCut(r: CutEdited, set: (p: Partial<SequenceState>) => void, get: () => SequenceState): void {
  set({ current: r.timeline, lane: laneOf(r.timeline), tracks: r.tracks, timelines: get().timelines.map((t) => (t.id === r.timeline.id ? r.timeline : t)),
    playhead: Math.min(get().playhead, Math.max(0, Math.ceil(r.tracks.duration) - 1)) })
  if (get().selClip !== null && ![...r.tracks.video, ...r.tracks.audio].some((tr) => tr.items.some((i) => i.id === get().selClip))) set({ selClip: null })
  if (get().selTrack !== null && ![...r.tracks.video, ...r.tracks.audio].some((tr) => tr.id === get().selTrack)) set({ selTrack: null })
}

/** CE2: one of the editor's calls — the cut's revision as its base; a stale base reloads the cut, FilmCraft's refusal is said as it is. */
async function cutCall(get: () => SequenceState, set: (p: Partial<SequenceState>) => void, call: (id: string, revision: number) => Promise<CutEdited>): Promise<boolean> {
  const cur = get().current
  if (!cur?.file) return false
  set({ cutBusy: true })
  try {
    applyCut(await call(cur.id, cur.revision), set, get)
    return true
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) { useSession.getState().toast('The cut changed elsewhere — reloaded; your last change was not made', 'error'); await get().open(cur.id) }
    else useSession.getState().toast(`${err.detail ?? e}`, 'error')
    return false
  } finally { set({ cutBusy: false }) }
}

export const useSequence = create<SequenceState>()((set, get) => ({
  timelines: [], current: null, lane: null, selected: null, playhead: 0, playing: false, pxPerFrame: 3, undo: [], redo: [], saving: false, lastExport: null, assembleFor: null,
  tracks: null, tool: 'select', selClip: null, selTrack: null, cutBusy: false, fxOpen: null, fxPicker: null, fxPlugins: null, fxScanning: false,

  load: async () => {
    try { set({ timelines: (await unwrap(http.GET('/timelines'))).items }) } catch { set({ timelines: [] }) }
  },
  create: async (name) => {
    try {
      const tl = await unwrap(http.POST('/timelines', { body: { name } }))
      set({ timelines: [tl, ...get().timelines] })
      await get().open(tl.id)
      return tl
    } catch (e) { useSession.getState().toast(`New cut failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },
  open: async (id) => {
    if (!id) { set({ current: null, lane: null, selected: null, playhead: 0, playing: false, undo: [], redo: [], tracks: null, selClip: null, selTrack: null }); return }
    try {
      const tl = await unwrap(http.GET('/timelines/{tl_id}', { params: { path: { tl_id: id } } }))
      set({ current: tl, lane: laneOf(tl), selected: null, playhead: 0, playing: false, undo: [], redo: [], tracks: null, selClip: null, selTrack: null,
        timelines: get().timelines.some((t) => t.id === tl.id) ? get().timelines.map((t) => (t.id === tl.id ? tl : t)) : [tl, ...get().timelines] })
      if (tl.file) await get().loadTracks()
    } catch (e) { useSession.getState().toast(`Open cut failed: ${(e as ApiError).detail ?? e}`, 'error') }
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
  undoEdit: () => { if (isCut()) { void get().cutUndo(); return } const u = get().undo; if (!u.length || !get().lane) return; set({ lane: u[u.length - 1], undo: u.slice(0, -1), redo: [...get().redo, get().lane!] }); if (saveTimer) window.clearTimeout(saveTimer); saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300) },
  redoEdit: () => { if (isCut()) { void get().cutUndo(true); return } const r = get().redo; if (!r.length || !get().lane) return; set({ lane: r[r.length - 1], redo: r.slice(0, -1), undo: [...get().undo, get().lane!] }); if (saveTimer) window.clearTimeout(saveTimer); saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300) },

  addClip: (clip) => { if (isCut()) { void get().cutPlace({ clip_id: clip.id, track: 'V1', frame: endOf(get().tracks?.video[0]) }); return } const fps = get().lane?.fps ?? 24; get().apply((l) => append(l, laneClipFrom(clip, fps, undefined, chainIn(l, clip.chained_from, clip.overlap, clip.frames))), 'add clip'); set({ selected: (get().lane?.clips.length ?? 1) - 1 }) },
  addShot: (clip, shot) => {
    if (isCut()) { void get().cutPlace({ clip_id: clip.id, shot_id: shot.id, shot_version: shot.version, node_id: shot.node, track: 'V1', frame: endOf(get().tracks?.video[0]) }); return }
    const fps = get().lane?.fps ?? 24; get().apply((l) => append(l, laneClipFrom(clip, fps, shot, chainIn(l, clip.chained_from, clip.overlap, clip.frames))), 'add shot'); set({ selected: (get().lane?.clips.length ?? 1) - 1 }) },
  removeClip: (i) => { get().apply((l) => remove(l, i), 'remove clip'); set({ selected: null }) },
  moveClip: (from, to) => { get().apply((l) => move(l, from, to), 'move clip'); set({ selected: to }) },
  trimClip: (i, edge, delta, sourceLen) => get().apply((l) => trim(l, i, edge, delta, () => sourceLen), 'trim'),
  setDissolve: (i, frames) => get().apply((l) => setOverlap(l, i, frames), 'dissolve'),
  select: (i) => set({ selected: i }),
  setAssembleFor: (assembleFor) => set({ assembleFor }),
  setPlayhead: (f) => { const d = get().lane ? duration(get().lane!) : 0; set({ playhead: Math.max(0, Math.min(Math.max(0, d - 1), Math.round(f))) }) },
  togglePlay: (on) => set({ playing: on ?? !get().playing }),
  zoom: (factor) => set({ pxPerFrame: Math.max(0.25, Math.min(24, get().pxPerFrame * factor)) }),
  exportAs: async (format) => {
    const cur = get().current
    if (!cur) return
    try {
      const r = await unwrap(http.POST('/timelines/{tl_id}/export', { params: { path: { tl_id: cur.id } }, body: { format } }))
      set({ lastExport: { format, path: r.path } })
      if (format === 'resolve') { useSession.getState().toast(`For Resolve: ${r.text.split('\n').length} files in ${r.path}${r.audio ? ` · ${r.audio} spoken line${r.audio === 1 ? '' : 's'} on the audio lane` : ''}`, 'success'); return }
      useSession.getState().toast(`${format.toUpperCase()} written: ${r.path}${r.audio ? ` · ${r.audio} spoken line${r.audio === 1 ? '' : 's'} on the audio lane` : ''}`, 'success')
    } catch (e) { useSession.getState().toast(`Export failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  render: async (movie = false) => {
    const cur = get().current
    if (!cur) return
    const s = useSession.getState()
    try {
      await unwrap(http.POST('/timelines/{tl_id}/render', { params: { path: { tl_id: cur.id } }, body: { movie } }))
      s.toast(movie ? 'Movie queued — an MP4 in the cut\'s folder and the Catalogue when it is done (CPU, no engine)'
        : 'Draft render queued — the clip lands in the Clips bin when it is done (CPU, no engine)', 'success')
      await s.refreshAll()
    } catch (e) { s.toast(`Render failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },

  loadTracks: async () => {
    const cur = get().current
    if (!cur?.file) { set({ tracks: null }); return }
    try { set({ tracks: await unwrap(http.GET('/timelines/{tl_id}/tracks', { params: { path: { tl_id: cur.id } } })) }) }
    catch (e) { useSession.getState().toast(`The cut's tracks: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  cutEdit: (steps) => cutCall(get, set, (id, revision) => unwrap(http.POST('/timelines/{tl_id}/edit', { params: { path: { tl_id: id } }, body: { revision, steps: steps.map((s) => ({ id: s.id, params: s.params ?? {} })) } }))),
  cutPlace: (body) => cutCall(get, set, (id, revision) => unwrap(http.POST('/timelines/{tl_id}/place', { params: { path: { tl_id: id } }, body: { revision, insert: false, ...body } }))),
  cutReplace: (clip, take) => cutCall(get, set, (id, revision) => unwrap(http.POST('/timelines/{tl_id}/replace', { params: { path: { tl_id: id } }, body: { revision, clip, ...take } }))),
  cutUndo: async (redo = false) => {
    await cutCall(get, set, (id, revision) => unwrap(redo ? http.POST('/timelines/{tl_id}/redo', { params: { path: { tl_id: id } }, body: { revision } })
      : http.POST('/timelines/{tl_id}/undo', { params: { path: { tl_id: id } }, body: { revision } })))
  },
  cutStrip: (track, change) => cutCall(get, set, (id, revision) => unwrap(http.POST('/timelines/{tl_id}/strip', { params: { path: { tl_id: id } }, body: { revision, track, ...change } }))),
  cutRole: (track, role) => cutCall(get, set, (id, revision) => unwrap(http.POST('/timelines/{tl_id}/role', { params: { path: { tl_id: id } }, body: { revision, track, role } }))),
  cutFx: (track, change) => cutCall(get, set, (id, revision) => unwrap(http.POST('/timelines/{tl_id}/fx', { params: { path: { tl_id: id } }, body: { revision, track, ...change } }))),
  cutFxEditor: async (track, fx) => {
    const cur = get().current
    if (!cur?.file || get().fxOpen) return
    set({ fxOpen: fx })                                                       // the window is the author's: no busy state, other edits go on
    try { applyCut(await unwrap(http.POST('/timelines/{tl_id}/fx/editor', { params: { path: { tl_id: cur.id } }, body: { track, fx } })), set, get) }
    catch (e) { useSession.getState().toast(`${(e as ApiError).detail ?? e}`, 'error') }
    finally { set({ fxOpen: null }) }
  },
  setFxPicker: (track, rescan = false) => {
    set({ fxPicker: track })
    if (track === null || get().fxScanning || (get().fxPlugins && !rescan)) return
    set({ fxScanning: true })
    void unwrap(http.GET('/audio/plugins', { params: { query: { rescan } } })).then((r) => set({ fxPlugins: r }))
      .catch((e) => set({ fxPlugins: { available: false, plugins: [], failed: [], error: String((e as ApiError).detail ?? e) } })).finally(() => set({ fxScanning: false }))
  },
  setTool: (tool) => set({ tool }),
  selectClip: (id) => {                                                       // a take on V1 is the lane's clip too (Update, the Inspector)
    const k = id === null ? -1 : (get().lane?.clips.findIndex((c) => c.id === String(id)) ?? -1)
    set({ selClip: id, selected: k >= 0 ? k : null, ...(id !== null ? { selTrack: null } : {}) })
  },
  selectTrack: (id) => set({ selTrack: id, ...(id !== null ? { selClip: null, selected: null } : {}) }),
}))

export const seqActive = (): boolean => !!useSequence.getState().current

/** RC3: the cut's newest movie job in the session — running (with its progress), done (the file, the cut's revision it read) or failed. */
export interface MovieState { status: 'running' | 'done' | 'failed'; progress: number; path: string | null; file: string | null; revision: number | null; assetId: string | null }
export function lastMovie(jobs: Record<string, Job>, tlId: string): MovieState | null {
  const mine = Object.values(jobs).filter((j) => {
    const r = j.recipe as { kind?: string; movie?: boolean; timeline_id?: string }
    return r.kind === 'render' && r.movie === true && r.timeline_id === tlId && ['queued', 'running', 'done', 'failed'].includes(j.status)
  }).sort((a, b) => b.created_at.localeCompare(a.created_at))
  const j = mine[0]
  if (!j) return null
  const res = (j.result ?? {}) as { path?: string; file?: string; revision?: number; asset_ids?: string[] }
  return { status: j.status === 'done' ? 'done' : j.status === 'failed' ? 'failed' : 'running', progress: j.progress ?? 0, path: res.path ?? null, file: res.file ?? null,
    revision: res.revision ?? null, assetId: res.asset_ids?.[0] ?? null }
}
// dev: scripts/sy_acceptance.py drives the lane through the store (the smoke test uses the buttons)
if (DEV_HOOKS) (window as unknown as { __loom2Sequence?: typeof useSequence }).__loom2Sequence = useSequence
/** What the lane shows at the playhead (for the preview and the Inspector). */
export function shownNow(): ReturnType<typeof at> {
  const { lane, playhead } = useSequence.getState()
  return lane ? at(lane, playhead, starts(lane)) : null
}
