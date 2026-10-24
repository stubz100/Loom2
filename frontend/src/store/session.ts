// One zustand store for session, project, engine, queue, models, settings, events and frame UI state (06 §8).
// Project data never lives in component state; layout memory persists per suite in localStorage (07 §1.7).
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ApiError, EventsSocket, http, setBackend, setMediaKey, unwrap } from '../api/client'
import type { Asset, Backend, Capabilities, EngineState, EventFrame, FetchState, HealthInfo, Job, JobOrigin, ModelEntry, ProjectInfo, QueueState, Settings, Suite, UnlistedFile } from '../api/types'
import type { Theme } from '../frame/theme'
import { discoverBackend } from '../shell/tauri'
import { DEV_HOOKS } from '../devHooks'

/** A toast's one button (Undo, Play, …); a bare function passed to `toast()` is an Undo. */
export interface ToastAction { label: string; run: () => void }
export interface Toast { id: number; kind: 'info' | 'success' | 'error'; text: string; action?: ToastAction; sticky?: boolean }
export interface Banner { id: string; text: string; action?: { label: string; run: () => void }; kind?: 'info' | 'warn' | 'error' }

interface UiState {
  suite: Suite; panelOpen: boolean; inspectorOpen: boolean; dockOpen: boolean; focusMode: boolean; density: 'comfortable' | 'compact'; theme: Theme
  thumbFit: 'fit' | 'fill'; caption: 'off' | 'prompt' | 'model'                  // Settings · Catalogue (D34)
  editKeepAliveMin?: number                                                     // D69: a hidden Edit / Animate stage is released after this long
  panelWidth: number; inspectorWidth: number; dismissedBanners: string[]
  panelWidths?: Record<string, number>; inspectorWidths?: Record<string, number>   // D90 (02 §3.1): dragged widths per suite; absent = the suite's default
  imageLast?: 'generate' | 'edit'                                              // D95 (IM1): the Image tab returns to the mode last open under it (Make or Edit)
  dockTab?: 'queue' | 'bin'                                                     // D95 (AN1, 04 C1): the Dock shows the render queue or the Bin
  animateLast?: 'animate' | 'stage' | 'final'                                  // D95 (AN1) → D121: the Animate tab returns to the level last open (Performance, Clay or Final)
  pick?: BinPick | null                                                        // a pick started from a panel (the author, 2026-10-22): the Bin's tiles show its button top right
  graph?: boolean                                                              // RC1 (D96): Animate's Graph — the shot's recipe over the mode's viewer
}

/** A pick started from a panel's button ("Add image plane…", "Set from an image…"): the Bin verb it stands for, the command whose icon the
 *  tiles' corner button carries, the label the button says. The corner click runs the verb and ends the pick; ✕ in the Bin's bar or a suite change ends it too. */
export interface BinPick { verb: string; cmd: string; label: string }

export interface SessionState {
  backend: Backend | null; backendError: string | null; wsStatus: 'open' | 'closed'
  health: HealthInfo | null; project: ProjectInfo | null; recents: string[]
  engine: EngineState | null; queue: QueueState | null; jobs: Record<string, Job>; previews: Record<string, string>
  models: ModelEntry[]; unlisted: UnlistedFile[]; fetches: Record<string, FetchState>
  settings: Settings | null; capabilities: Capabilities | null
  events: EventFrame[]; toasts: Toast[]; settingsOpen: boolean; projectDialog: 'new' | 'open' | null; helpOpen: boolean
  ask: AskRequest | null                                   // in-app confirm / prompt (07 §1: no native dialogs)
  ui: UiState
  selectedModel: string | null
  init: () => Promise<void>
  refreshAll: () => Promise<void>
  setSuite: (s: Suite) => void
  setUi: (patch: Partial<UiState>) => void
  openProject: (path: string) => Promise<void>
  createProject: (path: string, name: string) => Promise<void>
  closeProject: () => Promise<void>
  submitJob: (recipe: Record<string, unknown>, origin?: JobOrigin) => Promise<Job[]>
  cancelJob: (id: string) => Promise<void>
  releaseJob: (id: string) => Promise<void>
  deleteJob: (id: string) => Promise<void>
  pauseQueue: (paused: boolean) => Promise<void>
  engineAction: (action: 'start' | 'stop' | 'restart' | 'free') => Promise<void>
  scanModels: () => Promise<void>
  fetchModel: (id: string) => Promise<void>
  verifyModel: (id: string) => Promise<{ sha256: string; matches_ledger: boolean | null }>
  saveSettings: (patch: Partial<Settings> | Record<string, unknown>) => Promise<void>
  toast: (text: string, kind?: Toast['kind'], action?: (() => void) | ToastAction) => void
  askConfirm: (o: AskOptions) => Promise<boolean>
  askText: (o: AskOptions) => Promise<string | null>
  resolveAsk: (value: string | boolean | null) => void
  dismissToast: (id: number) => void
  dismissBanner: (id: string) => void
  openSettings: (open: boolean) => void
  setProjectDialog: (d: 'new' | 'open' | null) => void
  setHelp: (open: boolean) => void
  modelsSheet: ModelsSheetState | null                     // D90 (02 §7): Models & engine is a sheet in ☰, not a suite
  openModels: (o?: ModelsSheetState) => void
  closeModels: () => void
  selectModel: (id: string | null) => void
  banners: () => Banner[]
}

/** D90 (02 §7): which tab of Models & engine opens, and whether the roster shows only the missing weights (every Fetch link does). */
export interface ModelsSheetState { tab?: 'roster' | 'engine'; missing?: boolean }

export interface AskOptions { title: string; text?: string; initial?: string; placeholder?: string; okLabel?: string; danger?: boolean; allowEmpty?: boolean; check?: string; checkOn?: boolean }   // allowEmpty: an empty answer is one (D123's lens: MoGe reads it); D125: a confirm's one checkbox
export interface AskRequest extends AskOptions { kind: 'confirm' | 'prompt'; resolve: (v: string | boolean | null) => void }

let socket: EventsSocket | null = null
let toastSeq = 1

export const useSession = create<SessionState>()(
  persist(
    (set, get) => ({
      backend: null, backendError: null, wsStatus: 'closed', health: null, project: null, recents: [], engine: null, queue: null, jobs: {}, previews: {},
      models: [], unlisted: [], fetches: {}, settings: null, capabilities: null, events: [], toasts: [], settingsOpen: false, projectDialog: null, helpOpen: false, ask: null, modelsSheet: null,
      ui: { suite: 'catalogue', panelOpen: true, inspectorOpen: true, dockOpen: false, focusMode: false, density: 'comfortable', theme: 'dark', thumbFit: 'fit', caption: 'off', panelWidth: 320, inspectorWidth: 340, dismissedBanners: [] },
      selectedModel: null,

      init: async () => {
        try {
          const b = await discoverBackend()
          setBackend(b)
          setMediaKey((await unwrap(http.GET('/session'))).media_key)      // D67: before any <img> asks for a thumbnail
          set({ backend: b, backendError: null })
        } catch (e) {
          set({ backendError: (e as Error).message })
          return
        }
        const q0 = new URLSearchParams(location.search)
        const deep = q0.get('suite') === 'animate' && q0.get('tab') === 'sequence' ? 'story' : q0.get('suite')   // 17 SY4: the Sequence tab moved to Story · Episode
        if (deep && ['catalogue', 'generate', 'edit', 'animate', 'stage', 'final', 'story', 'models'].includes(deep)) get().setSuite(deep as Suite)
        else if (get().ui.suite === 'models') set({ ui: { ...get().ui, suite: 'catalogue' } })   // D90: a remembered Models suite lands in the Catalogue
        try {
          await get().refreshAll()
        } catch (e) {                                                   // B21: a failing first fetch shows the Retry banner, not the crash overlay
          set({ backendError: (e as ApiError).detail ?? (e as Error).message })
          return
        }
        const start = get().health?.start_suite
        if (!deep && start && ['catalogue', 'generate', 'edit', 'animate', 'stage', 'final', 'story', 'models'].includes(start)) get().setSuite(start as Suite)
        socket?.close()
        let everOpen = false
        socket = new EventsSocket(
          (f) => applyEvent(f, set, get),
          ({ header, payload }) => {
            const jobId = String(header.job_id ?? '')
            const old = get().previews[jobId]
            if (old) URL.revokeObjectURL(old)
            set({ previews: { ...get().previews, [jobId]: URL.createObjectURL(payload) } })
          },
          (s) => {
            const reconnected = s === 'open' && everOpen
            if (s === 'open') everOpen = true
            set({ wsStatus: s })
            if (reconnected) {                                          // B21: fetch what the socket missed instead of assuming nothing happened
              void get().refreshAll().catch(() => undefined)
              void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().resync())
            }
          },
        )
        socket.connect()
      },

      refreshAll: async () => {
        const [health, project, projects, engine, settings, capabilities, models] = await Promise.all([
          unwrap(http.GET('/health')), unwrap(http.GET('/project')), unwrap(http.GET('/projects')),
          unwrap(http.GET('/engine')), unwrap(http.GET('/settings')), unwrap(http.GET('/capabilities')),
          unwrap(http.GET('/models')),
        ])
        set({ health, project, recents: projects.recents, engine, settings, capabilities, models: models.items, fetches: models.fetches })
        if (project.open) {
          const [queue, jobs] = await Promise.all([unwrap(http.GET('/queue')), unwrap(http.GET('/jobs'))])
          set({ queue, jobs: Object.fromEntries(jobs.items.map((j) => [j.id, j])) })
        } else {
          set({ queue: null, jobs: {} })
        }
      },

      setSuite: (suite) => {
        if (suite === 'models') { get().openModels({ missing: true }); return }   // D90 (02 §7): the old routes (the Fetch buttons) open the sheet on the missing weights
        set({ ui: { ...get().ui, suite, pick: null, ...(suite === 'generate' || suite === 'edit' ? { imageLast: suite } : {}), ...(suite === 'animate' || suite === 'stage' || suite === 'final' ? { animateLast: suite } : {}) } })
      },
      openModels: (o = {}) => set({ modelsSheet: { tab: o.tab ?? 'roster', missing: !!o.missing } }),
      closeModels: () => set({ modelsSheet: null }),
      setUi: (patch) => set({ ui: { ...get().ui, ...patch } }),

      openProject: async (path) => {
        const project = await unwrap(http.POST('/project/open', { body: { path } }))
        set({ project, projectDialog: null })
        await get().refreshAll()
        get().toast(`Opened ${project.name}`, 'success')
      },
      createProject: async (path, name) => {
        const project = await unwrap(http.POST('/project', { body: { path, name } }))
        set({ project, projectDialog: null })
        await get().refreshAll()
        void import('../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'world'); get().setSuite('story') })   // D125: a new project starts with its bible
        get().toast(`Created ${project.name}`, 'success')
      },
      closeProject: async () => {
        await unwrap(http.POST('/project/close'))
        set({ project: { open: false }, queue: null, jobs: {} })
      },

      submitJob: async (recipe, origin) => {
        const r = await unwrap(http.POST('/jobs', { body: { recipe, origin } }))
        set({ jobs: { ...get().jobs, ...Object.fromEntries(r.jobs.map((j) => [j.id, j])) } })
        return r.jobs
      },
      cancelJob: async (id) => { await unwrap(http.POST('/jobs/{job_id}/cancel', { params: { path: { job_id: id } } })) },
      releaseJob: async (id) => { await unwrap(http.POST('/jobs/{job_id}/release', { params: { path: { job_id: id } } })) },
      deleteJob: async (id) => {
        await unwrap(http.DELETE('/jobs/{job_id}', { params: { path: { job_id: id } } }))
        const jobs = { ...get().jobs }; delete jobs[id]; set({ jobs })
      },
      pauseQueue: async (paused) => { set({ queue: await unwrap(paused ? http.POST('/queue/pause') : http.POST('/queue/unpause')) }) },
      engineAction: async (action) => {
        try {
          if (action === 'free') await unwrap(http.POST('/engine/free'))
          else set({ engine: await unwrap(http.POST(action === 'start' ? '/engine/start' : action === 'stop' ? '/engine/stop' : '/engine/restart')) })
          get().toast(`Engine ${action}`, 'success')
        } catch (e) { get().toast(`Engine ${action} failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },

      scanModels: async () => {
        const r = await unwrap(http.POST('/models/scan'))
        set({ models: r.items, unlisted: r.unlisted })
      },
      fetchModel: async (id) => {
        const st = await unwrap(http.POST('/models/fetch', { body: { model_id: id } }))
        set({ fetches: { ...get().fetches, [id]: st } })
      },
      verifyModel: (id) => unwrap(http.POST('/models/{model_id}/verify', { params: { path: { model_id: id } } })),
      saveSettings: async (patch) => {
        const settings = await unwrap(http.PUT('/settings', { body: patch }))
        set({ settings })
        await get().scanModels()
        get().toast('Settings saved', 'success')
      },

      toast: (text, kind = 'info', act) => {
        const id = toastSeq++
        const action = typeof act === 'function' ? { label: 'Undo', run: act } : act
        const kept = get().toasts.filter((t) => t.text !== text || t.action)        // a repeated message replaces its older copy
        set({ toasts: [...kept, { id, kind, text, action, sticky: kind === 'error' }].slice(-3) })   // at most three on screen (review U15)
        if (kind !== 'error') setTimeout(() => get().dismissToast(id), 6000)
      },
      dismissToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
      askConfirm: (o) => new Promise<boolean>((resolve) => { get().ask?.resolve(null); set({ ask: { ...o, kind: 'confirm', resolve: (v) => resolve(v === true || v === 'checked') } }) }),
      askText: (o) => new Promise<string | null>((resolve) => { get().ask?.resolve(null); set({ ask: { ...o, kind: 'prompt', resolve: (v) => resolve(typeof v === 'string' ? v : null) } }) }),
      resolveAsk: (value) => { const a = get().ask; set({ ask: null }); a?.resolve(value) },
      dismissBanner: (id) => set({ ui: { ...get().ui, dismissedBanners: [...get().ui.dismissedBanners, id] } }),
      openSettings: (settingsOpen) => set({ settingsOpen }),
      setProjectDialog: (projectDialog) => set({ projectDialog }),
      setHelp: (helpOpen) => set({ helpOpen }),
      selectModel: (selectedModel) => set({ selectedModel }),

      banners: () => {
        const s = get()
        const out: Banner[] = []
        if (s.backendError) out.push({ id: 'backend', kind: 'error', text: `Orchestrator unavailable: ${s.backendError}`, action: { label: 'Retry', run: () => void s.init() } })
        for (const [i, note] of (s.queue?.recovery ?? []).entries()) out.push({ id: `recovery-${i}`, kind: 'error', text: note })
        if (s.queue?.paused && s.queue.resumed_unclean) out.push({ id: 'resumed', kind: 'warn', text: 'Queue paused — resumed from last session with the interrupted job re-queued.', action: { label: 'Resume', run: () => void s.pauseQueue(false) } })
        else if (s.queue?.paused) out.push({ id: 'paused', text: 'Queue paused.', action: { label: 'Resume', run: () => void s.pauseQueue(false) } })
        if (s.engine && !s.engine.running && s.engine.last_error) out.push({ id: 'engine', kind: 'error', text: `Engine down: ${s.engine.last_error}`, action: { label: 'Restart', run: () => void s.engineAction('restart') } })
        const missing = s.models.filter((m) => m.health === 'missing' && !m.retired)
        if (missing.length && s.project?.open) out.push({ id: 'weights', kind: 'warn', text: `${missing.length} roster weight${missing.length > 1 ? 's' : ''} missing on disk.`, action: { label: 'Show the missing weights', run: () => s.openModels({ missing: true }) } })
        const free = s.project?.open ? s.project.free_space_gb : null
        if (free != null && free < 20) out.push({ id: 'disk', kind: free < 8 ? 'error' : 'warn', text: `Disk: ${free} GB free on the project drive.` })
        return out.filter((b) => !s.ui.dismissedBanners.includes(b.id) || b.kind === 'error')
      },
    }),
    { name: 'loom2.ui', partialize: (s) => ({ ui: s.ui }),
      // field by field: a layout saved before a UI field existed (e.g. theme) keeps that field's default
      merge: (persisted, current) => ({ ...current, ui: { ...current.ui, ...((persisted as { ui?: Partial<UiState> } | undefined)?.ui ?? {}) } }) },
  ),
)

/** Routes one WebSocket frame (D38: `EventFrame` is the generated union, so each case sees its own `data` type). Exported for the unit
 *  suite (D68); the app calls it only from the event socket. */
export function applyEvent(f: EventFrame, set: (p: Partial<SessionState>) => void, get: () => SessionState): void {
  const s = get()
  set({ events: [...s.events.slice(-199), f] })
  switch (f.type) {
    case 'job.created':
    case 'job.updated': {
      const job = f.data
      set({ jobs: { ...s.jobs, [job.id]: job } })
      if (f.type === 'job.updated' && ['done', 'failed', 'cancelled'].includes(job.status) && s.previews[job.id]) {   // C29: the preview's blob URL dies with the job
        URL.revokeObjectURL(s.previews[job.id]); const previews = { ...s.previews }; delete previews[job.id]; set({ previews })
      }
      if (f.type === 'job.updated' && (job.status === 'done' || job.status === 'failed')) {
        s.toast(job.status === 'done' ? `Job ${job.id.slice(4)} done in ${job.wall_s} s` : `Job ${job.id.slice(4)} failed: ${job.error}`, job.status === 'done' ? 'success' : 'error')
        void unwrap(http.GET('/queue')).then((queue) => set({ queue })).catch(() => undefined)
        void unwrap(http.GET('/project')).then((project) => set({ project })).catch(() => undefined)
      }
      if (job.status === 'running' || job.status === 'queued') void unwrap(http.GET('/queue')).then((queue) => set({ queue })).catch(() => undefined)
      break
    }
    case 'job.progress': {
      const { id, progress, text } = f.data
      const job = s.jobs[id]
      if (job) set({ jobs: { ...s.jobs, [id]: { ...job, progress, progress_text: text } } })
      break
    }
    case 'job.deleted': { const jobs = { ...s.jobs }; delete jobs[f.data.id]; set({ jobs }); break }
    case 'queue.state': set({ queue: f.data }); break
    case 'preset_icons.changed': void import('../suites/generate/swatches').then((m) => m.useSwatches.getState().load()); break   // D90 (02 §6.3): a swatch was made or removed
    case 'engine.state': set({ engine: { ...(s.engine ?? {}), ...f.data } }); break
    case 'engine.vram_pressure': {                                     // D69: a GPU job needs the memory a hidden stage holds
      void import('../frame/stageKeep').then((m) => {
        const gone = m.useStageKeep.getState().releaseHidden(s.ui.suite, `the engine had ${f.data.free_gb} GB free for job ${f.data.job_id}`)
        if (gone.length) s.toast(`Released the hidden ${gone.map((id) => (id === 'edit' ? 'editor canvas' : id === 'animate' ? 'player' : id)).join(' and ')} to give the GPU job room — it reloads when you return`, 'info')
      })
      break
    }
    case 'model.fetch': {
      const st = f.data
      set({ fetches: { ...s.fetches, [st.model_id]: st } })
      if (st.status === 'done') { s.toast(`Fetched ${st.name}`, 'success'); void s.scanModels() }
      if (st.status === 'failed') s.toast(`Fetch failed: ${st.error}`, 'error')
      break
    }
    case 'project.opened': set({ project: f.data }); break
    case 'project.closed': set({ project: { open: false } }); break
    case 'catalogue.changed':
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) { const st = h.getState(); void st.load(); void st.refreshMeta() } })
      break
    case 'group.changed':                                         // D34: placements moved; the tree, counts and open views follow
      void import('../suites/catalogue/albumStore').then((m) => void m.useAlbum.getState().load())
      void import('../suites/story/storyStore').then((m) => m.useStory.getState().onGroupChanged(((f.data as { ids?: string[] } | null)?.ids) ?? []))   // 17 SY1: a version's pages
      void import('../suites/generate/generateStore').then((m) => m.mentionsMoved({ groups: ((f.data as { ids?: string[] } | null)?.ids) ?? [] }))   // D93: a mentioned set grew → the preview's references
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) { const st = h.getState(); void st.refreshMeta(); if (st.q.folder === 'unprocessed' || st.q.group_id) void st.load({ keepSelection: true }) } })
      break
    case 'asset.created': case 'asset.updated': case 'asset.deleted':
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) h.getState().applyEvent(f) })
      if (f.type === 'asset.created' && (f.data as { origin?: { suite?: string } } | null)?.origin?.suite === 'stage')      // ST3: a shot or a pass of a stage
        void import('../suites/stage/stageStore').then((m) => m.useStage.getState().onAssetCreated(f.data as never))
      break
    case 'clip.updated':
      void import('../suites/animate/animateStore').then((m) => m.useAnimate.getState().onClipUpdated(f.data))
      break
    case 'clip.ready':
      void import('../suites/animate/animateStore').then((m) => m.useAnimate.getState().onClipReady(f.data))
      break
    case 'document.changed':
      void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().onDocumentChanged(f.data))
      break
    case 'story.changed':                                         // 17 (D85): the world (later profiles, shots, the flow) moved on the server
      void import('../suites/story/storyStore').then((m) => m.useStory.getState().onChanged(f.data as never))
      { const d = f.data as { kind?: string; id?: string } | null; if (d?.kind === 'shot' && d.id) { const id = d.id; void import('../suites/story/recipeTick').then((m) => m.useRecipeTick.getState().bump(id)) } }   // RC0: an open recipe refetches
      void import('../suites/catalogue/albumStore').then((m) => void m.useAlbum.getState().loadUsedBy())      // D92 §4.2: a version, style, board or entry may name another group
      void import('../suites/generate/generateStore').then((m) => { const d = f.data as { kind?: string; id?: string } | null; if (d?.kind === 'profile' && d.id) m.mentionsMoved({ profile: d.id }) })   // D93: a linked character got a hero
      break
    case 'lora.changed':                                          // 18 (D86) LT2: a LoRA trained or deleted — the registry and the versions' slots moved
      void import('../suites/story/storyStore').then((m) => m.useStory.getState().onLoraChanged(f.data as never))
      void import('../suites/generate/generateStore').then((m) => { const g = m.useGenerate.getState(); void g.loadLoras(g.panel.model_id) })
      break
    default: break
  }
}

export const selectRunningJob = (s: SessionState): Job | null => (s.queue?.running ? s.jobs[s.queue.running] ?? null : null)
export const selectJobsByStatus = (s: SessionState) => {
  const all = Object.values(s.jobs).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  return { running: all.filter((j) => j.status === 'running'), queued: all.filter((j) => j.status === 'queued'), recent: all.filter((j) => ['done', 'failed', 'cancelled'].includes(j.status)) }
}
export type { Asset }

/** The frames whose `type` can be one of T (an `asset.*` frame's type is itself a union). */
type FrameOf<T extends EventFrame['type'], F = EventFrame> = F extends { type: infer U } ? ([Extract<U, T>] extends [never] ? never : F) : never
/** D66: subscribe to WebSocket frames of the given types (album pages patch their records on `group.changed` and `asset.*`). Every frame
 *  lands in `events` with one `set` before it is routed, and zustand calls listeners synchronously, so the newest entry is the frame. */
export function onEvents<T extends EventFrame['type']>(types: readonly T[], cb: (f: FrameOf<T>) => void): () => void {
  return useSession.subscribe((s, prev) => {
    if (s.events === prev.events) return
    const f = s.events[s.events.length - 1]
    if (f && (types as readonly string[]).includes(f.type)) cb(f as FrameOf<T>)
  })
}

/** In-app confirm (resolves false when cancelled) and text prompt (null when cancelled) — the only dialogs besides OS file pickers. */
export const askConfirm = (o: AskOptions): Promise<boolean> => useSession.getState().askConfirm(o)
export const askText = (o: AskOptions): Promise<string | null> => useSession.getState().askText(o)
/** D125: a confirm with one checkbox (`o.check`) — null when cancelled, else whether the box was ticked. */
export const askConfirmCheck = (o: AskOptions & { check: string }): Promise<{ checked: boolean } | null> =>
  new Promise((resolve) => { const s = useSession.getState(); s.ask?.resolve(null); useSession.setState({ ask: { ...o, kind: 'confirm', resolve: (v) => resolve(v === true || v === 'checked' ? { checked: v === 'checked' } : null) } }) })

if (DEV_HOOKS) {                                                       // dev: the headed check switches suites and feeds event frames (D69 release)
  const w = window as unknown as { __loom2Session?: typeof useSession; __loom2ApplyEvent?: (f: EventFrame) => void }
  w.__loom2Session = useSession
  w.__loom2ApplyEvent = (f) => applyEvent(f, useSession.setState, useSession.getState)
}
