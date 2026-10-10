// One zustand store for session, project, engine, queue, models, settings, events and frame UI state (06 §8).
// Project data never lives in component state; layout memory persists per suite in localStorage (07 §1.7).
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ApiError, EventsSocket, http, setBackend, unwrap } from '../api/client'
import type { Asset, Backend, Capabilities, EngineState, EventFrame, FetchState, HealthInfo, Job, ModelEntry, ProjectInfo, QueueState, Settings, Suite, UnlistedFile } from '../api/types'
import type { Theme } from '../frame/theme'
import { discoverBackend } from '../shell/tauri'

export interface Toast { id: number; kind: 'info' | 'success' | 'error'; text: string; undo?: () => void; sticky?: boolean }
export interface Banner { id: string; text: string; action?: { label: string; run: () => void }; kind?: 'info' | 'warn' | 'error' }

interface UiState {
  suite: Suite; panelOpen: boolean; inspectorOpen: boolean; dockOpen: boolean; focusMode: boolean; density: 'comfortable' | 'compact'; theme: Theme
  thumbFit: 'fit' | 'fill'; caption: 'off' | 'prompt' | 'model'                  // Settings · Catalogue (D34)
  panelWidth: number; inspectorWidth: number; dismissedBanners: string[]
}

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
  submitJob: (recipe: Record<string, unknown>) => Promise<Job[]>
  cancelJob: (id: string) => Promise<void>
  releaseJob: (id: string) => Promise<void>
  deleteJob: (id: string) => Promise<void>
  pauseQueue: (paused: boolean) => Promise<void>
  engineAction: (action: 'start' | 'stop' | 'restart' | 'free') => Promise<void>
  scanModels: () => Promise<void>
  fetchModel: (id: string) => Promise<void>
  verifyModel: (id: string) => Promise<{ sha256: string; matches_ledger: boolean | null }>
  saveSettings: (patch: Partial<Settings> | Record<string, unknown>) => Promise<void>
  toast: (text: string, kind?: Toast['kind'], undo?: () => void) => void
  askConfirm: (o: AskOptions) => Promise<boolean>
  askText: (o: AskOptions) => Promise<string | null>
  resolveAsk: (value: string | boolean | null) => void
  dismissToast: (id: number) => void
  dismissBanner: (id: string) => void
  openSettings: (open: boolean) => void
  setProjectDialog: (d: 'new' | 'open' | null) => void
  setHelp: (open: boolean) => void
  selectModel: (id: string | null) => void
  banners: () => Banner[]
}

export interface AskOptions { title: string; text?: string; initial?: string; placeholder?: string; okLabel?: string; danger?: boolean }
export interface AskRequest extends AskOptions { kind: 'confirm' | 'prompt'; resolve: (v: string | boolean | null) => void }

let socket: EventsSocket | null = null
let toastSeq = 1

export const useSession = create<SessionState>()(
  persist(
    (set, get) => ({
      backend: null, backendError: null, wsStatus: 'closed', health: null, project: null, recents: [], engine: null, queue: null, jobs: {}, previews: {},
      models: [], unlisted: [], fetches: {}, settings: null, capabilities: null, events: [], toasts: [], settingsOpen: false, projectDialog: null, helpOpen: false, ask: null,
      ui: { suite: 'catalogue', panelOpen: true, inspectorOpen: true, dockOpen: false, focusMode: false, density: 'comfortable', theme: 'dark', thumbFit: 'fit', caption: 'off', panelWidth: 320, inspectorWidth: 340, dismissedBanners: [] },
      selectedModel: null,

      init: async () => {
        try {
          const b = await discoverBackend()
          setBackend(b)
          set({ backend: b, backendError: null })
        } catch (e) {
          set({ backendError: (e as Error).message })
          return
        }
        const deep = new URLSearchParams(location.search).get('suite')
        if (deep && ['catalogue', 'generate', 'edit', 'animate', 'models'].includes(deep)) set({ ui: { ...get().ui, suite: deep as Suite } })
        try {
          await get().refreshAll()
        } catch (e) {                                                   // B21: a failing first fetch shows the Retry banner, not the crash overlay
          set({ backendError: (e as ApiError).detail ?? (e as Error).message })
          return
        }
        const start = get().health?.start_suite
        if (!deep && start && ['catalogue', 'generate', 'edit', 'animate', 'models'].includes(start)) set({ ui: { ...get().ui, suite: start as Suite } })
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

      setSuite: (suite) => set({ ui: { ...get().ui, suite } }),
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
        get().toast(`Created ${project.name}`, 'success')
      },
      closeProject: async () => {
        await unwrap(http.POST('/project/close'))
        set({ project: { open: false }, queue: null, jobs: {} })
      },

      submitJob: async (recipe) => {
        const r = await unwrap(http.POST('/jobs', { body: { recipe } }))
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

      toast: (text, kind = 'info', undo) => {
        const id = toastSeq++
        set({ toasts: [...get().toasts, { id, kind, text, undo, sticky: kind === 'error' }] })
        if (kind !== 'error') setTimeout(() => get().dismissToast(id), 6000)
      },
      dismissToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
      askConfirm: (o) => new Promise<boolean>((resolve) => { get().ask?.resolve(null); set({ ask: { ...o, kind: 'confirm', resolve: (v) => resolve(v === true) } }) }),
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
        if (missing.length && s.project?.open) out.push({ id: 'weights', kind: 'warn', text: `${missing.length} roster weight${missing.length > 1 ? 's' : ''} missing on disk.`, action: { label: 'Open Models', run: () => s.setSuite('models') } })
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

/** Routes one WebSocket frame (D38: `EventFrame` is the generated union, so each case sees its own `data` type). */
function applyEvent(f: EventFrame, set: (p: Partial<SessionState>) => void, get: () => SessionState): void {
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
    case 'engine.state': set({ engine: { ...(s.engine ?? {}), ...f.data } }); break
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
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) { const st = h.getState(); void st.refreshMeta(); if (st.q.folder === 'unprocessed' || st.q.group_id) void st.load({ keepSelection: true }) } })
      window.dispatchEvent(new CustomEvent('loom2:group-changed', { detail: f.data }))
      break
    case 'asset.created': case 'asset.updated': case 'asset.deleted':
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) h.getState().applyEvent(f) })
      window.dispatchEvent(new CustomEvent('loom2:asset-event', { detail: f }))           // album pages patch their asset records
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
    default: break
  }
}

export const selectRunningJob = (s: SessionState): Job | null => (s.queue?.running ? s.jobs[s.queue.running] ?? null : null)
export const selectJobsByStatus = (s: SessionState) => {
  const all = Object.values(s.jobs).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  return { running: all.filter((j) => j.status === 'running'), queued: all.filter((j) => j.status === 'queued'), recent: all.filter((j) => ['done', 'failed', 'cancelled'].includes(j.status)) }
}
export type { Asset }

/** In-app confirm (resolves false when cancelled) and text prompt (null when cancelled) — the only dialogs besides OS file pickers. */
export const askConfirm = (o: AskOptions): Promise<boolean> => useSession.getState().askConfirm(o)
export const askText = (o: AskOptions): Promise<string | null> => useSession.getState().askText(o)

if (import.meta.env.DEV) (window as unknown as { __loom2Session?: typeof useSession }).__loom2Session = useSession      // dev: the headed check switches suites
