// Catalogue suite state (08): query, paged items / server-side groups, selection, tile zoom, loupe and compare.
// Project data stays on the orchestrator; this store caches pages and applies live events.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { http, unwrap, type AssetQueryParams } from '../../api/client'
import type { Asset, EventFrame, GroupHeader as ApiGroupHeader } from '../../api/types'
import { useSession } from '../../store/session'

export type Folder = 'all' | 'unprocessed' | 'today' | 'last_session' | 'images' | 'clips' | 'documents' | 'imported' | 'rejected' | 'trash'
export type DatePreset = 'today' | 'last_session' | '7d' | '30d'
export type GroupMode = 'none' | 'batch' | 'lineage' | 'session' | 'model'
export type Sort = 'created_desc' | 'created_asc' | 'rating_desc' | 'model' | 'size_desc'

export interface Query {
  folder: Folder; state: 'all' | 'none' | 'keep' | 'reject'; kind?: 'image' | 'video' | 'mask' | 'document-render'; suite?: string; model_id?: string
  rating_min: number; tags_any: string[]; aspect?: 'landscape' | 'portrait' | 'square'; has_children?: boolean; search: string
  sort: Sort; group: GroupMode; collection_id?: string; root_id?: string; created_from?: string; created_to?: string; batch_id?: string; session_id?: string
  group_id?: string; date_preset?: DatePreset; has_document?: boolean
  batch_label?: string; root_label?: string                       // chip labels only, never sent
}
export type GroupHeader = ApiGroupHeader

const DEFAULT_QUERY: Query = { folder: 'all', state: 'all', rating_min: 0, tags_any: [], search: '', sort: 'created_desc', group: 'batch' }

/** The store's query as GET /assets parameters: empty strings and unset fields are left out; booleans are sent when set, `false`
 *  included (D38 fix: "No derivations" sent nothing before, so its chip showed every asset). */
function queryOf(q: Query, extra: Partial<AssetQueryParams> = {}): AssetQueryParams {
  const out: AssetQueryParams = { folder: q.folder, state: q.state, sort: q.sort, group: q.group }
  const text = (v: string | undefined) => (v ? v : undefined)
  Object.assign(out, {
    kind: q.kind, suite: text(q.suite), model_id: text(q.model_id), rating_min: q.rating_min > 0 ? q.rating_min : undefined,
    tags_any: q.tags_any.length ? q.tags_any : undefined, aspect: q.aspect, has_children: q.has_children, has_document: q.has_document,
    search: text(q.search.trim()), collection_id: text(q.collection_id), root_id: text(q.root_id), created_from: text(q.created_from), created_to: text(q.created_to),
    batch_id: text(q.batch_id), session_id: text(q.session_id), group_id: text(q.group_id), date_preset: q.date_preset,
  }, extra)
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v !== undefined)) as AssetQueryParams
}

export interface CatalogueState {
  q: Query
  items: Asset[]; nextCursor: string | null; total: number | null; loading: boolean; error: string | null
  groups: GroupHeader[]; groupItems: Record<string, Asset[]>; expanded: Record<string, boolean>; groupLoading: Record<string, boolean>; groupErrors: Record<string, string>
  counts: Record<string, number>; tagCloud: { tag: string; count: number }[]
  selected: string[]; primary: string | null; anchor: string | null
  tile: number
  loupe: string | null; compare: string[]; compareOpen: boolean
  lineage: string | null                                         // the asset whose lineage tree the Stage shows (D34)
  groupSel: string[]                                             // selected cards on a page (D34)
  pageZoom: number; fitSeq: number                               // a page's zoom; fitSeq++ asks the page to fit its content
  pendingDelete: number | null
  setQuery: (patch: Partial<Query>) => Promise<void>
  load: (opts?: { keepSelection?: boolean }) => Promise<void>
  loadMore: () => Promise<void>
  loadGroup: (key: string) => Promise<void>
  toggleGroup: (key: string, open?: boolean) => void
  expandAll: (open: boolean) => void
  retryGroup: (key: string) => void
  refreshMeta: () => Promise<void>
  visibleOrder: () => string[]
  byId: (id: string) => Asset | undefined
  select: (id: string, mode: 'single' | 'toggle' | 'range') => void
  selectAll: () => void
  clearSelection: () => void
  setState: (ids: string[], state: 'none' | 'keep' | 'reject') => Promise<void>
  setRating: (ids: string[], rating: number) => Promise<void>
  setTags: (ids: string[], tags: string[]) => Promise<void>
  trash: (ids: string[]) => Promise<void>
  restore: (ids: string[]) => Promise<void>
  purge: (ids: string[]) => Promise<void>
  emptyTrash: () => Promise<number>
  purging: boolean
  setTile: (n: number) => void
  openLoupe: (id: string | null) => void
  openLineage: (id: string | null) => void
  selectGroups: (ids: string[]) => void
  setPageZoom: (z: number) => void
  requestFit: () => void
  setCompareOpen: (open: boolean) => void
  togglePin: (id: string) => void
  clearCompare: () => void
  importPaths: (paths: string[]) => Promise<number>
  applyEvent: (f: EventFrame) => void
}

const MAX_INFLIGHT = 6
let inflight = 0
const waiting: (() => void)[] = []
async function limited<T>(fn: () => Promise<T>): Promise<T> {
  if (inflight >= MAX_INFLIGHT) await new Promise<void>((resolve) => waiting.push(resolve))
  inflight++
  try { return await fn() } finally { inflight--; waiting.shift()?.() }
}

export function createCatalogueStore(name: string, defaults: Partial<Query> = {}) {
  const DEFAULT_Q: Query = { ...DEFAULT_QUERY, ...defaults }
  let loadSeq = 0            // B13: per store — the Catalogue and Generate results reload independently on the same event
  return create<CatalogueState>()(
  persist(
    (set, get) => ({
      q: DEFAULT_Q, items: [], nextCursor: null, total: null, loading: false, error: null,
      groups: [], groupItems: {}, expanded: {}, groupLoading: {}, groupErrors: {}, counts: {}, tagCloud: [],
      selected: [], primary: null, anchor: null, tile: 192, loupe: null, compare: [], compareOpen: false, lineage: null, groupSel: [], pageZoom: 1, fitSeq: 0, pendingDelete: null,

      setQuery: (patch) => { set({ q: { ...get().q, ...patch }, ...('group_id' in patch || 'folder' in patch ? { groupSel: [], lineage: null, loupe: null } : {}) }); return get().load() },

      load: async (opts) => {
        const seq = ++loadSeq
        const q = get().q
        set({ loading: true, error: null, ...(opts?.keepSelection ? {} : { selected: [], primary: null, anchor: null }) })   // B22
        try {
          if (q.group === 'none') {
            const page = await unwrap(http.GET('/assets', { params: { query: queryOf(q, { limit: 200 }) } }))
            if (seq !== loadSeq) return
            set({ items: page.items, nextCursor: page.next_cursor, total: page.total, groups: [], groupItems: {} })
          } else {
            const groups = await unwrap(http.GET('/assets/groups', { params: { query: queryOf(q) } }))
            if (seq !== loadSeq) return
            const expanded = { ...get().expanded }
            groups.slice(0, 6).forEach((g) => { if (expanded[g.key] === undefined) expanded[g.key] = true })
            set({ groups, groupItems: {}, groupErrors: {}, items: [], nextCursor: null, total: groups.reduce((n, g) => n + g.count, 0), expanded })
            // expanded groups load when they scroll into view (Stage); the first few are warmed here
            groups.filter((g) => expanded[g.key]).slice(0, 6).forEach((g) => void get().loadGroup(g.key))
          }
        } catch (e) {
          set({ error: (e as Error).message })
        } finally {
          if (seq === loadSeq) set({ loading: false })
        }
      },

      loadMore: async () => {
        const { q, nextCursor, loading } = get()
        if (!nextCursor || loading || q.group !== 'none') return
        set({ loading: true })
        try {
          const page = await unwrap(http.GET('/assets', { params: { query: queryOf(q, { limit: 200, cursor: nextCursor }) } }))
          set({ items: [...get().items, ...page.items], nextCursor: page.next_cursor })
        } finally { set({ loading: false }) }
      },

      loadGroup: async (key) => {
        const { q } = get()
        if (get().groupItems[key] || get().groupLoading[key] || get().groupErrors[key]) return
        set({ groupLoading: { ...get().groupLoading, [key]: true } })
        const seq = loadSeq
        try {
          // at most MAX_INFLIGHT group fetches at a time: "expand all" on 10k assets must not open thousands of connections
          const page = await limited(() => unwrap(http.GET('/assets', { params: { query: queryOf({ ...q, group: 'none' }, { group_by: q.group, group_key: key, limit: 1000 }) } })))
          if (seq !== loadSeq) return                               // the query changed meanwhile
          set({ groupItems: { ...get().groupItems, [key]: page.items } })
        } catch (e) {
          if (seq === loadSeq) {
            set({ groupErrors: { ...get().groupErrors, [key]: (e as Error).message } })
            if (!get().error) set({ error: `Could not load a group: ${(e as Error).message}` })
          }
        } finally {
          const gl = { ...get().groupLoading }; delete gl[key]; set({ groupLoading: gl })
        }
      },

      toggleGroup: (key, open) => {
        const now = open ?? !get().expanded[key]
        set({ expanded: { ...get().expanded, [key]: now } })
        if (now) void get().loadGroup(key)
      },
      expandAll: (open) => {
        const expanded: Record<string, boolean> = {}
        get().groups.forEach((g) => { expanded[g.key] = open })
        set({ expanded, groupErrors: {}, error: null })             // items load as the groups scroll into view (Stage)
      },
      retryGroup: (key) => { const ge = { ...get().groupErrors }; delete ge[key]; set({ groupErrors: ge, error: null }); void get().loadGroup(key) },

      refreshMeta: async () => {
        const [counts, tags] = await Promise.all([unwrap(http.GET('/assets/counts')), unwrap(http.GET('/assets/tags'))])
        set({ counts, tagCloud: tags.items })
      },

      visibleOrder: () => {
        const s = get()
        if (s.q.group === 'none') return s.items.map((a) => a.id)
        const out: string[] = []
        for (const g of s.groups) if (s.expanded[g.key]) for (const a of s.groupItems[g.key] ?? []) out.push(a.id)
        return out
      },
      byId: (id) => {
        const s = get()
        return s.items.find((a) => a.id === id) ?? Object.values(s.groupItems).flat().find((a) => a.id === id)
      },

      select: (id, mode) => {
        const s = get()
        if (s.groupSel.length && mode !== 'toggle') set({ groupSel: [] })
        if (mode === 'single') { set({ selected: [id], primary: id, anchor: id }); return }
        if (mode === 'toggle') {
          const has = s.selected.includes(id)
          const selected = has ? s.selected.filter((x) => x !== id) : [...s.selected, id]
          set({ selected, primary: has ? (selected[selected.length - 1] ?? null) : id, anchor: id })
          return
        }
        const order = s.visibleOrder()
        const a = order.indexOf(s.anchor ?? id), b = order.indexOf(id)
        if (a < 0 || b < 0) { set({ selected: [id], primary: id, anchor: id }); return }
        const [lo, hi] = a < b ? [a, b] : [b, a]
        set({ selected: order.slice(lo, hi + 1), primary: id })
      },
      selectAll: () => { const order = get().visibleOrder(); set({ selected: order, primary: order[0] ?? null }) },
      clearSelection: () => set({ selected: [], primary: null, groupSel: [] }),

      setState: async (ids, state) => { await patchMany(ids, { state }, set, get) },
      setRating: async (ids, rating) => { await patchMany(ids, { rating }, set, get) },
      setTags: async (ids, tags) => { await patchMany(ids, { tags }, set, get); void get().refreshMeta() },
      trash: async (ids) => {
        await unwrap(http.POST('/assets/trash', { body: { ids } }))
        removeLocal(ids, set, get)
        void get().refreshMeta()
        useSession.getState().toast(`Moved ${ids.length} to Trash`, 'info', () => void get().restore(ids))
      },
      restore: async (ids) => { await unwrap(http.POST('/assets/restore', { body: { ids } })); await get().load(); void get().refreshMeta() },
      purge: async (ids) => { await unwrap(http.POST('/assets/purge', { body: { ids } })); removeLocal(ids, set, get); void get().refreshMeta() },
      purging: false,
      emptyTrash: async () => {
        set({ purging: true })
        try {
          const r = await unwrap(http.POST('/assets/purge', { body: { ids: null } }))   // every trashed asset, files and index rows
          await get().load(); void get().refreshMeta()
          return r.purged
        } finally { set({ purging: false }) }
      },

      setTile: (n) => set({ tile: Math.max(96, Math.min(512, Math.round(n))) }),
      openLoupe: (id) => set({ loupe: id, ...(id ? { selected: [id], primary: id, anchor: id, compareOpen: false, lineage: null } : {}) }),
      setCompareOpen: (compareOpen) => set({ compareOpen, ...(compareOpen ? { loupe: null, lineage: null } : {}) }),
      selectGroups: (ids) => set({ groupSel: ids, ...(ids.length ? { selected: [], primary: null } : {}) }),
      setPageZoom: (z) => set({ pageZoom: Math.max(0.1, Math.min(4, z)) }),
      requestFit: () => set({ fitSeq: get().fitSeq + 1 }),
      openLineage: (id) => set({ lineage: id, ...(id ? { loupe: null, compareOpen: false, selected: [id], primary: id, anchor: id } : {}) }),
      togglePin: (id) => {
        const c = get().compare
        set({ compare: c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-4) })
      },
      clearCompare: () => set({ compare: [], compareOpen: false }),

      importPaths: async (paths) => {
        const r = await unwrap(http.POST('/assets/import', { body: { paths } }))
        await get().load(); void get().refreshMeta()
        return r.items.length
      },

      applyEvent: (f) => {
        const s = get()
        const d = f.data as unknown as Asset & { id: string }
        if (f.type === 'asset.updated') {
          const upd = (a: Asset) => (a.id === d.id ? (d as Asset) : a)
          if (d.trashed_at && s.q.folder !== 'trash') { removeLocal([d.id], set, get); return }
          set({ items: s.items.map(upd), groupItems: Object.fromEntries(Object.entries(s.groupItems).map(([k, v]) => [k, v.map(upd)])) })
        } else if (f.type === 'asset.deleted') {
          removeLocal([d.id], set, get)
        } else if (f.type === 'asset.created') {
          if (s.q.folder === 'trash' || s.q.search || s.q.collection_id || s.q.group_id) return      // new items land in Unprocessed (D34)
          if (s.q.group === 'none') {
            if (s.q.sort === 'created_desc') set({ items: [d as Asset, ...s.items], total: (s.total ?? 0) + 1 })
          } else {
            void s.load({ keepSelection: true })                   // B22: a landing batch must not clear what the user is selecting
          }
          void s.refreshMeta()
        }
      },
    }),
    { name, partialize: (s) => ({ tile: s.tile, q: { sort: s.q.sort, group: s.q.group } }) as never,
      merge: (persisted, current) => { const p = (persisted ?? {}) as Partial<CatalogueState> & { q?: Partial<Query> }; return { ...current, tile: p.tile ?? current.tile, q: { ...current.q, ...(p.q ?? {}) } } } },
  ),
  )
}

// D34: a fresh key — the Catalogue has no group-by any more, and opens on Unprocessed
export const useCatalogue = createCatalogueStore('loom2.catalogue.v2', { folder: 'unprocessed', group: 'none' })
/** The second pane of a split Stage (D34, proto01_design/01 §6c): its own place, query, selection and zoom. */
export const useCataloguePane2 = createCatalogueStore('loom2.catalogue.pane2', { folder: 'unprocessed', group: 'none' })
/** Generate's result grid: the same machinery filtered to this suite, grouped by batch (09 §4). */
export const useGenerateResults = createCatalogueStore('loom2.generate-results', { suite: 'generate', group: 'batch' })
/** Every live catalogue store, for events that reload them all. */
export const allCatalogueStores = () => [useCatalogue, useCataloguePane2, useGenerateResults]

async function patchMany(ids: string[], changes: Record<string, unknown>, set: (p: Partial<CatalogueState>) => void, get: () => CatalogueState) {
  if (!ids.length) return
  const r = await unwrap(http.PATCH('/assets/bulk', { body: { ids, changes } }))
  const by = Object.fromEntries(r.items.map((a) => [a.id, a]))
  const s = get()
  const upd = (a: Asset) => by[a.id] ?? a
  set({ items: s.items.map(upd), groupItems: Object.fromEntries(Object.entries(s.groupItems).map(([k, v]) => [k, v.map(upd)])) })
}

function removeLocal(ids: string[], set: (p: Partial<CatalogueState>) => void, get: () => CatalogueState) {
  const s = get()
  const gone = new Set(ids)
  set({
    items: s.items.filter((a) => !gone.has(a.id)),
    groupItems: Object.fromEntries(Object.entries(s.groupItems).map(([k, v]) => [k, v.filter((a) => !gone.has(a.id))])),
    groups: s.groups.map((g) => ({ ...g, count: g.count - (s.groupItems[g.key] ?? []).filter((a) => gone.has(a.id)).length })).filter((g) => g.count > 0),
    selected: s.selected.filter((x) => !gone.has(x)), primary: s.primary && gone.has(s.primary) ? null : s.primary,
    total: s.total === null ? null : Math.max(0, s.total - ids.length),
    compare: s.compare.filter((x) => !gone.has(x)), loupe: s.loupe && gone.has(s.loupe) ? null : s.loupe,
  })
}

export const selectedOrPrimary = (s: CatalogueState): string[] => (s.selected.length ? s.selected : s.primary ? [s.primary] : [])
