// One zustand store for session, project, engine, queue, models, settings, events and frame UI state (06 §8).
// Project data never lives in component state; layout memory persists per suite in localStorage (07 §1.7).
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, ApiError, EventsSocket, setBackend } from '../api/client'
import type { Asset, Backend, Capabilities, EngineState, EventFrame, FetchState, HealthInfo, Job, ModelEntry, ProjectInfo, QueueState, Settings, Suite } from '../api/types'
import { discoverBackend } from '../shell/tauri'

export interface Toast { id: number; kind: 'info' | 'success' | 'error'; text: string; undo?: () => void; sticky?: boolean }
export interface Banner { id: string; text: string; action?: { label: string; run: () => void }; kind?: 'info' | 'warn' | 'error' }

interface UiState {
  suite: Suite; panelOpen: boolean; inspectorOpen: boolean; dockOpen: boolean; focusMode: boolean; density: 'comfortable' | 'compact'
  panelWidth: number; inspectorWidth: number; dismissedBanners: string[]
}

export interface SessionState {
  backend: Backend | null; backendError: string | null; wsStatus: 'open' | 'closed'
  health: HealthInfo | null; project: ProjectInfo | null; recents: string[]
  engine: EngineState | null; queue: QueueState | null; jobs: Record<string, Job>; previews: Record<string, string>
  models: ModelEntry[]; unlisted: { folder: string; name: string; path: string; size: number }[]; fetches: Record<string, FetchState>
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
      ui: { suite: 'catalogue', panelOpen: true, inspectorOpen: true, dockOpen: false, focusMode: false, density: 'comfortable', panelWidth: 320, inspectorWidth: 340, dismissedBanners: [] },
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
          api.get<HealthInfo>('/health'), api.get<ProjectInfo>('/project'), api.get<{ last: string | null; recents: string[] }>('/projects'),
          api.get<EngineState>('/engine'), api.get<Settings>('/settings'), api.get<Capabilities>('/capabilities'),
          api.get<{ items: ModelEntry[]; fetches: Record<string, FetchState> }>('/models'),
        ])
        set({ health, project, recents: projects.recents, engine, settings, capabilities, models: models.items, fetches: models.fetches })
        if (project.open) {
          const [queue, jobs] = await Promise.all([api.get<QueueState>('/queue'), api.get<{ items: Job[] }>('/jobs')])
          set({ queue, jobs: Object.fromEntries(jobs.items.map((j) => [j.id, j])) })
        } else {
          set({ queue: null, jobs: {} })
        }
      },

      setSuite: (suite) => set({ ui: { ...get().ui, suite } }),
      setUi: (patch) => set({ ui: { ...get().ui, ...patch } }),

      openProject: async (path) => {
        const project = await api.post<ProjectInfo>('/project/open', { path })
        set({ project, projectDialog: null })
        await get().refreshAll()
        get().toast(`Opened ${project.name}`, 'success')
      },
      createProject: async (path, name) => {
        const project = await api.post<ProjectInfo>('/project', { path, name })
        set({ project, projectDialog: null })
        await get().refreshAll()
        get().toast(`Created ${project.name}`, 'success')
      },
      closeProject: async () => {
        await api.post('/project/close')
        set({ project: { open: false }, queue: null, jobs: {} })
      },

      submitJob: async (recipe) => {
        const r = await api.post<{ jobs: Job[] }>('/jobs', { recipe })
        set({ jobs: { ...get().jobs, ...Object.fromEntries(r.jobs.map((j) => [j.id, j])) } })
        return r.jobs
      },
      cancelJob: async (id) => { await api.post(`/jobs/${id}/cancel`) },
      releaseJob: async (id) => { await api.post(`/jobs/${id}/release`) },
      deleteJob: async (id) => {
        await api.del(`/jobs/${id}`)
        const jobs = { ...get().jobs }; delete jobs[id]; set({ jobs })
      },
      pauseQueue: async (paused) => { set({ queue: await api.post<QueueState>(paused ? '/queue/pause' : '/queue/unpause') }) },
      engineAction: async (action) => {
        try {
          const r = await api.post<EngineState>(`/engine/${action}`)
          if (action !== 'free') set({ engine: r })
          get().toast(`Engine ${action}`, 'success')
        } catch (e) { get().toast(`Engine ${action} failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },

      scanModels: async () => {
        const r = await api.post<{ items: ModelEntry[]; unlisted: SessionState['unlisted'] }>('/models/scan')
        set({ models: r.items, unlisted: r.unlisted })
      },
      fetchModel: async (id) => {
        const st = await api.post<FetchState>('/models/fetch', { model_id: id })
        set({ fetches: { ...get().fetches, [id]: st } })
      },
      verifyModel: (id) => api.post(`/models/${id}/verify`),
      saveSettings: async (patch) => {
        const settings = await api.put<Settings>('/settings', patch)
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
        if (s.queue?.paused && s.queue.resumed_unclean) out.push({ id: 'resumed', kind: 'warn', text: 'Queue paused — resumed from last session with the interrupted job re-queued.', action: { label: 'Resume', run: () => void s.pauseQueue(false) } })
        else if (s.queue?.paused) out.push({ id: 'paused', text: 'Queue paused.', action: { label: 'Resume', run: () => void s.pauseQueue(false) } })
        if (s.engine && !s.engine.running && s.engine.last_error) out.push({ id: 'engine', kind: 'error', text: `Engine down: ${s.engine.last_error}`, action: { label: 'Restart', run: () => void s.engineAction('restart') } })
        const missing = s.models.filter((m) => m.health === 'missing' && !m.retired)
        if (missing.length && s.project?.open) out.push({ id: 'weights', kind: 'warn', text: `${missing.length} roster weight${missing.length > 1 ? 's' : ''} missing on disk.`, action: { label: 'Open Models', run: () => s.setSuite('models') } })
        if (s.project?.open && s.project.free_space_gb !== undefined && s.project.free_space_gb < 20) out.push({ id: 'disk', kind: s.project.free_space_gb < 8 ? 'error' : 'warn', text: `Disk: ${s.project.free_space_gb} GB free on the project drive.` })
        return out.filter((b) => !s.ui.dismissedBanners.includes(b.id) || b.kind === 'error')
      },
    }),
    { name: 'loom2.ui', partialize: (s) => ({ ui: s.ui }) },
  ),
)

function applyEvent(f: EventFrame, set: (p: Partial<SessionState>) => void, get: () => SessionState): void {
  const d = f.data as Record<string, unknown>
  const s = get()
  set({ events: [...s.events.slice(-199), f] })
  switch (f.type) {
    case 'job.created':
    case 'job.updated': {
      const job = d as unknown as Job
      set({ jobs: { ...s.jobs, [job.id]: job } })
      if (f.type === 'job.updated' && (job.status === 'done' || job.status === 'failed')) {
        s.toast(job.status === 'done' ? `Job ${job.id.slice(4)} done in ${job.wall_s} s` : `Job ${job.id.slice(4)} failed: ${job.error}`, job.status === 'done' ? 'success' : 'error')
        void api.get<QueueState>('/queue').then((queue) => set({ queue })).catch(() => undefined)
        void api.get<ProjectInfo>('/project').then((project) => set({ project })).catch(() => undefined)
      }
      if (job.status === 'running' || job.status === 'queued') void api.get<QueueState>('/queue').then((queue) => set({ queue })).catch(() => undefined)
      break
    }
    case 'job.progress': {
      const id = String(d.id)
      const job = s.jobs[id]
      if (job) set({ jobs: { ...s.jobs, [id]: { ...job, progress: Number(d.progress), progress_text: String(d.text ?? '') } } })
      break
    }
    case 'job.deleted': { const jobs = { ...s.jobs }; delete jobs[String(d.id)]; set({ jobs }); break }
    case 'queue.state': set({ queue: d as unknown as QueueState }); break
    case 'engine.state': set({ engine: { ...(s.engine ?? {}), ...(d as unknown as EngineState) } }); break
    case 'model.fetch': {
      const st = d as unknown as FetchState
      set({ fetches: { ...s.fetches, [st.model_id]: st } })
      if (st.status === 'done') { s.toast(`Fetched ${st.name}`, 'success'); void s.scanModels() }
      if (st.status === 'failed') s.toast(`Fetch failed: ${st.error}`, 'error')
      break
    }
    case 'project.opened': set({ project: d as unknown as ProjectInfo }); break
    case 'project.closed': set({ project: { open: false } }); break
    case 'catalogue.changed':
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const st of [m.useCatalogue.getState(), m.useGenerateResults.getState()]) { void st.load(); void st.refreshMeta() } })
      break
    case 'asset.created': case 'asset.updated': case 'asset.deleted':
      void import('../suites/catalogue/catalogueStore').then((m) => { m.useCatalogue.getState().applyEvent(f); m.useGenerateResults.getState().applyEvent(f) })
      break
    case 'document.changed':
      void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().onDocumentChanged(d as { id: string; added?: string[]; group?: string; w?: number; h?: number; job_id?: string }))
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
