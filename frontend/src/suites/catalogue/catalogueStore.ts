// Catalogue suite state (08): query, paged items / server-side groups, selection, tile zoom, loupe and compare.
// Project data stays on the orchestrator; this store caches pages and applies live events.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../../api/client'
import type { Asset, EventFrame } from '../../api/types'
import { useSession } from '../../store/session'

export type Folder = 'all' | 'today' | 'last_session' | 'images' | 'clips' | 'documents' | 'imported' | 'rejected' | 'trash'
export type GroupMode = 'none' | 'batch' | 'lineage' | 'session' | 'model'
export type Sort = 'created_desc' | 'created_asc' | 'rating_desc' | 'model' | 'size_desc'

export interface Query {
  folder: Folder; state: 'all' | 'none' | 'keep' | 'reject'; kind?: 'image' | 'video' | 'mask' | 'document-render'; suite?: string; model_id?: string
  rating_min: number; tags_any: string[]; aspect?: 'landscape' | 'portrait' | 'square'; has_children?: boolean; search: string
  sort: Sort; group: GroupMode; collection_id?: string; root_id?: string; created_from?: string; created_to?: string
}
export interface GroupHeader { key: string; label: string; count: number; first_created: string; last_created: string; cover_id: string; model_id: string | null; prompt_excerpt: string | null }
export interface Collection { id: string; name: string; kind: 'manual' | 'smart'; filter: Record<string, unknown> | null; created_at: string; updated_at: string; count: number }
interface Page { items: Asset[]; next_cursor: string | null; total: number | null }

const DEFAULT_QUERY: Query = { folder: 'all', state: 'all', rating_min: 0, tags_any: [], search: '', sort: 'created_desc', group: 'batch' }

function qs(q: Query, extra: Record<string, string | number | boolean | undefined> = {}): string {
  const p = new URLSearchParams()
  const put = (k: string, v: unknown) => { if (v !== undefined && v !== null && v !== '' && v !== false) p.append(k, String(v)) }
  put('folder', q.folder); put('state', q.state); put('kind', q.kind); put('suite', q.suite); put('model_id', q.model_id)
  if (q.rating_min > 0) put('rating_min', q.rating_min)
  q.tags_any.forEach((t) => p.append('tags_any', t))
  put('aspect', q.aspect); if (q.has_children !== undefined) put('has_children', q.has_children)
  put('search', q.search.trim()); put('sort', q.sort); put('group', q.group); put('collection_id', q.collection_id); put('root_id', q.root_id)
  put('created_from', q.created_from); put('created_to', q.created_to)
  for (const [k, v] of Object.entries(extra)) put(k, v)
  return p.toString()
}

export interface CatalogueState {
  q: Query
  items: Asset[]; nextCursor: string | null; total: number | null; loading: boolean; error: string | null
  groups: GroupHeader[]; groupItems: Record<string, Asset[]>; expanded: Record<string, boolean>; groupLoading: Record<string, boolean>
  counts: Record<string, number>; collections: Collection[]; tagCloud: { tag: string; count: number }[]
  selected: string[]; primary: string | null; anchor: string | null
  tile: number; fill: boolean
  loupe: string | null; compare: string[]; compareOpen: boolean
  pendingDelete: number | null
  setQuery: (patch: Partial<Query>) => Promise<void>
  load: () => Promise<void>
  loadMore: () => Promise<void>
  loadGroup: (key: string) => Promise<void>
  toggleGroup: (key: string, open?: boolean) => void
  expandAll: (open: boolean) => void
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
  setTile: (n: number) => void
  setFill: (fill: boolean) => void
  openLoupe: (id: string | null) => void
  setCompareOpen: (open: boolean) => void
  togglePin: (id: string) => void
  clearCompare: () => void
  createCollection: (name: string, kind?: 'manual' | 'smart', filter?: Record<string, unknown>) => Promise<Collection>
  renameCollection: (id: string, name: string) => Promise<void>
  deleteCollection: (id: string) => Promise<void>
  convertCollection: (id: string) => Promise<void>
  addToCollection: (id: string, ids: string[]) => Promise<void>
  importPaths: (paths: string[]) => Promise<number>
  applyEvent: (f: EventFrame) => void
}

let loadSeq = 0

export const useCatalogue = create<CatalogueState>()(
  persist(
    (set, get) => ({
      q: DEFAULT_QUERY, items: [], nextCursor: null, total: null, loading: false, error: null,
      groups: [], groupItems: {}, expanded: {}, groupLoading: {}, counts: {}, collections: [], tagCloud: [],
      selected: [], primary: null, anchor: null, tile: 192, fill: false, loupe: null, compare: [], compareOpen: false, pendingDelete: null,

      setQuery: (patch) => { set({ q: { ...get().q, ...patch } }); return get().load() },

      load: async () => {
        const seq = ++loadSeq
        const q = get().q
        set({ loading: true, error: null, selected: [], primary: null, anchor: null })
        try {
          if (q.group === 'none') {
            const page = await api.get<Page>(`/assets?${qs(q, { limit: 200 })}`)
            if (seq !== loadSeq) return
            set({ items: page.items, nextCursor: page.next_cursor, total: page.total, groups: [], groupItems: {} })
          } else {
            const groups = await api.get<GroupHeader[]>(`/assets/groups?${qs(q)}`)
            if (seq !== loadSeq) return
            const expanded = { ...get().expanded }
            groups.slice(0, 6).forEach((g) => { if (expanded[g.key] === undefined) expanded[g.key] = true })
            set({ groups, groupItems: {}, items: [], nextCursor: null, total: groups.reduce((n, g) => n + g.count, 0), expanded })
            for (const g of groups) if (expanded[g.key]) void get().loadGroup(g.key)
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
          const page = await api.get<Page>(`/assets?${qs(q, { limit: 200, cursor: nextCursor })}`)
          set({ items: [...get().items, ...page.items], nextCursor: page.next_cursor })
        } finally { set({ loading: false }) }
      },

      loadGroup: async (key) => {
        const { q } = get()
        if (get().groupItems[key] || get().groupLoading[key]) return
        set({ groupLoading: { ...get().groupLoading, [key]: true } })
        const field = { batch: 'batch_id', lineage: 'root_id', session: 'session_id', model: 'model_id' }[q.group as Exclude<GroupMode, 'none'>]
        try {
          const page = await api.get<Page>(`/assets?${qs({ ...q, group: 'none' }, { [field]: key, limit: 1000 })}`)
          set({ groupItems: { ...get().groupItems, [key]: page.items } })
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
        set({ expanded })
        if (open) get().groups.forEach((g) => void get().loadGroup(g.key))
      },

      refreshMeta: async () => {
        const [counts, collections, tags] = await Promise.all([
          api.get<Record<string, number>>('/assets/counts'), api.get<Collection[]>('/collections'), api.get<{ items: { tag: string; count: number }[] }>('/assets/tags'),
        ])
        set({ counts, collections, tagCloud: tags.items })
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
      clearSelection: () => set({ selected: [], primary: null }),

      setState: async (ids, state) => { await patchMany(ids, { state }, set, get) },
      setRating: async (ids, rating) => { await patchMany(ids, { rating }, set, get) },
      setTags: async (ids, tags) => { await patchMany(ids, { tags }, set, get); void get().refreshMeta() },
      trash: async (ids) => {
        await api.post('/assets/trash', { ids })
        removeLocal(ids, set, get)
        void get().refreshMeta()
        useSession.getState().toast(`Moved ${ids.length} to Trash`, 'info', () => void get().restore(ids))
      },
      restore: async (ids) => { await api.post('/assets/restore', { ids }); await get().load(); void get().refreshMeta() },
      purge: async (ids) => { await api.post('/assets/purge', { ids }); removeLocal(ids, set, get); void get().refreshMeta() },

      setTile: (n) => set({ tile: Math.max(96, Math.min(512, Math.round(n))) }),
      setFill: (fill) => set({ fill }),
      openLoupe: (id) => set({ loupe: id, ...(id ? { selected: [id], primary: id, anchor: id, compareOpen: false } : {}) }),
      setCompareOpen: (compareOpen) => set({ compareOpen, ...(compareOpen ? { loupe: null } : {}) }),
      togglePin: (id) => {
        const c = get().compare
        set({ compare: c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-4) })
      },
      clearCompare: () => set({ compare: [], compareOpen: false }),

      createCollection: async (name, kind = 'manual', filter) => {
        const c = await api.post<Collection>('/collections', { name, kind, filter })
        await get().refreshMeta()
        return c
      },
      renameCollection: async (id, name) => { await api.patch(`/collections/${id}`, { name }); await get().refreshMeta() },
      deleteCollection: async (id) => { await api.del(`/collections/${id}`); if (get().q.collection_id === id) get().setQuery({ collection_id: undefined }); await get().refreshMeta() },
      convertCollection: async (id) => { await api.patch(`/collections/${id}`, { kind: 'manual' }); await get().refreshMeta() },
      addToCollection: async (id, ids) => { await api.post(`/collections/${id}/assets`, { ids }); await get().refreshMeta(); useSession.getState().toast(`Added ${ids.length} to collection`, 'success') },
      importPaths: async (paths) => {
        const r = await api.post<{ items: Asset[] }>('/assets/import', { paths })
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
          if (s.q.folder === 'trash' || s.q.search || s.q.collection_id) return
          if (s.q.group === 'none') {
            if (s.q.sort === 'created_desc') set({ items: [d as Asset, ...s.items], total: (s.total ?? 0) + 1 })
          } else {
            void s.load()
          }
          void s.refreshMeta()
        }
      },
    }),
    { name: 'loom2.catalogue', partialize: (s) => ({ tile: s.tile, fill: s.fill, q: { sort: s.q.sort, group: s.q.group } }) as never,
      merge: (persisted, current) => { const p = (persisted ?? {}) as Partial<CatalogueState> & { q?: Partial<Query> }; return { ...current, tile: p.tile ?? current.tile, fill: p.fill ?? current.fill, q: { ...current.q, ...(p.q ?? {}) } } } },
  ),
)

async function patchMany(ids: string[], changes: Record<string, unknown>, set: (p: Partial<CatalogueState>) => void, get: () => CatalogueState) {
  if (!ids.length) return
  const r = await api.patch<{ items: Asset[] }>('/assets/bulk', { ids, changes })
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
