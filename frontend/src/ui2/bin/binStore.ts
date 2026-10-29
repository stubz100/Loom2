// U8 (D157, proto01_UI2 05 §2): the Bin as a place — the tree of homes with their counts (GET /bin/tree), the open home's things with
// their roles and everything below it (GET /bin/homes/{id}/items), the Trash, a search across every home (GET /bin/search), a kind filter
// and the selection. It reads again when the records say a thing landed, moved or went to the Trash.
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import type { BinThing, BinNode } from '../../api/types'
import { onRecords } from '../../store/records'

export type KindFilter = 'all' | 'pictures' | 'clips' | 'audio' | 'models'
export const FILTERS: [KindFilter, string][] = [['all', 'all'], ['pictures', 'pictures'], ['clips', 'clips'], ['audio', 'audio'], ['models', 'models']]
const KINDS: Record<Exclude<KindFilter, 'all'>, string[]> = { pictures: ['image', 'mask', 'document-render'], clips: ['video'], audio: ['audio'], models: ['mesh'] }
export const passes = (it: BinThing, f: KindFilter): boolean => f === 'all' || KINDS[f].includes(it.asset.kind)
/** The roles as a tile's badge and the Inspector say them. */
export const ROLE_LABEL: Record<string, string> = { hero: '★ hero', reference: 'ref', a_pose_front: 'A-pose front', a_pose_back: 'A-pose back', set_picture: 'set picture',
  model: 'model', candidate: '', final: 'final', frame: 'frame', clip: 'clip', sample: 'sample', board: 'board' }
export const TRASH = 'trash'

/** Every home in the tree by id (its role pages too: a page id → its home). */
export function homesById(homes: BinNode[]): Map<string, BinNode> {
  const out = new Map<string, BinNode>()
  const walk = (n: BinNode) => { out.set(n.id, n); n.pages.forEach((p) => out.set(p, n)); n.children.forEach(walk) }
  homes.forEach(walk)
  return out
}

/** A home's path as the author reads it: an id segment (an entity, a shot, a cut) by its home's name — `world/character/Ines/v1`. */
export function pathLabel(homes: BinNode[], path: string): string {
  const byPath = new Map<string, BinNode>()
  const walk = (n: BinNode) => { byPath.set(n.path, n); n.children.forEach(walk) }
  homes.forEach(walk)
  const parts = path.split('/')
  return parts.map((seg, i) => (/^(prf|sht|tl)_/.test(seg) ? byPath.get(parts.slice(0, i + 1).join('/'))?.name ?? seg : seg)).join('/')
}

interface BinState {
  homes: BinNode[]; trash: number
  open: string | null                       // a home's id, `trash`, or null (a search)
  items: BinThing[]; path: string; query: string; filter: KindFilter; selected: string | null; loading: boolean
  expanded: Record<string, boolean>
  loadTree: () => Promise<void>
  openHome: (id: string) => Promise<void>
  search: (q: string) => Promise<void>
  reload: () => Promise<void>
  setFilter: (f: KindFilter) => void
  select: (id: string | null) => void
  toggle: (id: string) => void
}

let seq = 0
export const useBin = create<BinState>()((set, get) => ({
  homes: [], trash: 0, open: null, items: [], path: '', query: '', filter: 'all', selected: null, loading: false, expanded: { },
  loadTree: async () => {
    const t = await unwrap(http.GET('/bin/tree'))
    const first = !get().homes.length
    set({ homes: t.homes, trash: t.trash, ...(first ? { expanded: Object.fromEntries(t.homes.map((h) => [h.id, true])) } : {}) })
    if (get().open === null && !get().query && t.homes.length) await get().openHome(t.homes[0].id)
  },
  openHome: async (id) => {
    const n = ++seq
    set({ open: id, query: '', loading: true })
    try {
      const r = id === TRASH
        ? { items: (await unwrap(http.GET('/assets', { params: { query: { folder: 'trash', limit: 500 } } }))).items.map((asset) => ({ asset, roles: [], home_id: null, path: TRASH })), path: TRASH }
        : await unwrap(http.GET('/bin/homes/{gid}/items', { params: { path: { gid: id } } }))
      if (n !== seq) return
      set({ items: r.items, path: r.path, selected: r.items.some((x) => x.asset.id === get().selected) ? get().selected : null })
    } finally { if (n === seq) set({ loading: false }) }
  },
  search: async (q) => {
    if (!q.trim()) { set({ query: '' }); const o = get().open; if (o) await get().openHome(o); else await get().loadTree(); return }
    const n = ++seq
    set({ query: q, loading: true })
    try {
      const r = await unwrap(http.GET('/bin/search', { params: { query: { q } } }))
      if (n !== seq) return
      set({ open: null, items: r.items, path: '', selected: null })
    } finally { if (n === seq) set({ loading: false }) }
  },
  reload: async () => {
    await get().loadTree()
    const { open, query } = get()
    if (query) await get().search(query); else if (open) await get().openHome(open)
  },
  setFilter: (filter) => set({ filter }),
  select: (selected) => set({ selected }),
  toggle: (id) => set({ expanded: { ...get().expanded, [id]: !get().expanded[id] } }),
}))

let soon: number | null = null
/** Mounted with the layer: the tree, the first home, and a read again (once, shortly) when a thing lands, moves or goes. */
export function startBin(): () => void {
  void useBin.getState().loadTree()
  const off = onRecords('ui2.bin', ['group.changed', 'asset.created', 'asset.deleted', 'asset.updated'], () => {
    if (soon !== null) window.clearTimeout(soon)
    soon = window.setTimeout(() => { soon = null; void useBin.getState().reload() }, 300)
  })
  return () => { off(); if (soon !== null) window.clearTimeout(soon) }
}
