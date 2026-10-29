// U8 (D157, proto01_UI2 05 §2): the Bin as a place — the tree of homes with their counts (GET /bin/tree), the open home's things with
// their roles and everything below it (GET /bin/homes/{id}/items), the Trash, a search across every home (GET /bin/search), a kind filter
// and the selection. B0 (D159, 11 §4): a home is read a page at a time (the grid asks for the next as it scrolls near the end), the kind
// chips filter on the server, and the records' frames are applied where they land — a thing changed or deleted in place, the open home read
// again (its loaded window, one request) only when a frame touches it, the tree's counts and names once, shortly after.
// B1 (D159): one Bin — the layer and the Dock's drawer read this one store. A selection of many (a click, Ctrl, Shift, Select all; the
// verbs act on all of it), up to four things pinned for compare, the tile size, and `reveal`: a thing opened in its home, selected.
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import type { Asset, BinThing, BinNode } from '../../api/types'
import { onLoupe, postLoupe } from '../../frame/loupeLink'
import { onRecords } from '../../store/records'

export type KindFilter = 'all' | 'pictures' | 'clips' | 'audio' | 'models'
export const FILTERS: [KindFilter, string][] = [['all', 'all'], ['pictures', 'pictures'], ['clips', 'clips'], ['audio', 'audio'], ['models', 'models']]
type Kind = Asset['kind']
const KINDS: Record<Exclude<KindFilter, 'all'>, Kind[]> = { pictures: ['image', 'mask', 'document-render'], clips: ['video'], audio: ['audio'], models: ['mesh'] }
export const kindsOf = (f: KindFilter): Kind[] => (f === 'all' ? [] : KINDS[f])
export const passes = (it: BinThing, f: KindFilter): boolean => f === 'all' || KINDS[f].includes(it.asset.kind)
/** The roles as a tile's badge and the Inspector say them. */
export const ROLE_LABEL: Record<string, string> = { hero: '★ hero', reference: 'ref', a_pose_front: 'A-pose front', a_pose_back: 'A-pose back', set_picture: 'set picture',
  model: 'model', candidate: '', final: 'final', frame: 'frame', clip: 'clip', sample: 'sample', board: 'board' }
/** A role in a sentence (Move's question). */
export const ROLE_WORDS: Record<string, string> = { hero: 'the hero', reference: 'a reference', a_pose_front: 'the A-pose (front)', a_pose_back: 'the A-pose (back)',
  set_picture: "the set's picture", model: 'the 3D model', final: 'the final', frame: "the shot's frame", clip: "the shot's clip", sample: "a style's sample", board: 'the board' }
export const TRASH = 'trash'
/** B1: the tree's headings — they hold no things (a move or an import into one is refused, or goes to Imports). */
export const HEADINGS = new Set(['world', 'world/character', 'world/prop', 'world/place', 'shots', 'episode'])
export const PAGE = 200
export const TILE = { min: 90, max: 320, step: 30, layer: 150, drawer: 110 }
const TILE_KEY = 'loom2.bin.tile'
const readTile = (): number => { try { const n = Number(localStorage.getItem(TILE_KEY)); return n >= TILE.min && n <= TILE.max ? n : TILE.layer } catch { return TILE.layer } }

/** Every home in the tree by id (its role pages too: a page id → its home). */
export function homesById(homes: BinNode[]): Map<string, BinNode> {
  const out = new Map<string, BinNode>()
  const walk = (n: BinNode) => { out.set(n.id, n); n.pages.forEach((p) => out.set(p, n)); n.children.forEach(walk) }
  homes.forEach(walk)
  return out
}

/** The page ids a home's listing reads: the home, its role pages, every home under it with theirs. */
export function subtreeIds(n: BinNode): Set<string> {
  const out = new Set<string>()
  const walk = (x: BinNode) => { out.add(x.id); x.pages.forEach((p) => out.add(p)); x.children.forEach(walk) }
  walk(n)
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
  items: BinThing[]; path: string; query: string; filter: KindFilter; loading: boolean
  selected: string | null                   // the thing the Inspector shows (the last clicked)
  selection: string[]                       // B1: every thing selected (the verbs act on all of them), the selected one among them
  pins: Asset[]                             // B1: up to four things pinned for compare (from any home)
  comparing: boolean
  tile: number                              // B1: the layer's tile size (px, its smallest side)
  total: number | null                      // B0: the open home's count (with its first page)
  next: string | null                       // B0: the cursor of its next page, null at the end
  expanded: Record<string, boolean>
  viewing: boolean                          // U8b: the selected thing seen large over the grid (Esc or a click closes it)
  view: (on: boolean) => void
  loadTree: () => Promise<void>
  openHome: (id: string) => Promise<void>
  loadMore: () => Promise<void>
  search: (q: string) => Promise<void>
  reload: () => Promise<void>
  refresh: (what: { tree?: boolean; home?: boolean }) => Promise<void>
  patch: (a: Asset) => void
  drop: (id: string) => void
  setFilter: (f: KindFilter) => void
  select: (id: string | null, how?: 'single' | 'toggle' | 'range') => void
  selectAll: () => void
  pin: (a: Asset) => void
  unpinAll: () => void
  compare: (on: boolean) => void
  swap: () => void
  setTile: (px: number) => void
  reveal: (id: string) => Promise<boolean>
  toggle: (id: string) => void
}

type Page = { items: BinThing[]; path: string; total: number | null; next: string | null }

/** A page of the open place: a home's (GET /bin/homes/{id}/items) or the Trash's (GET /assets?folder=trash). */
async function readPage(id: string, filter: KindFilter, cursor: string | null, limit: number): Promise<Page> {
  const kinds = kindsOf(filter)
  if (id === TRASH) {
    const r = await unwrap(http.GET('/assets', { params: { query: { folder: 'trash', limit, cursor: cursor ?? undefined, kinds } } }))
    return { items: r.items.map((asset) => ({ asset, roles: [], home_id: null, path: TRASH })), path: TRASH, total: r.total ?? null, next: r.next_cursor ?? null }
  }
  const r = await unwrap(http.GET('/bin/homes/{gid}/items', { params: { path: { gid: id }, query: { limit, cursor: cursor ?? undefined, kinds } } }))
  return { items: r.items, path: r.path, total: r.total ?? null, next: r.next_cursor ?? null }
}

let seq = 0
let more: Promise<void> | null = null
export const useBin = create<BinState>()((set, get) => ({
  homes: [], trash: 0, open: null, items: [], path: '', query: '', filter: 'all', selected: null, selection: [], pins: [], comparing: false, tile: readTile(),
  loading: false, total: null, next: null, expanded: { }, viewing: false,
  view: (viewing) => set({ viewing: viewing && !!get().selected }),
  loadTree: async () => {
    const t = await unwrap(http.GET('/bin/tree'))
    const first = !get().homes.length
    set({ homes: t.homes, trash: t.trash, ...(first ? { expanded: Object.fromEntries(t.homes.map((h) => [h.id, true])) } : {}) })
    const open = get().open
    if (open && open !== TRASH && !homesById(t.homes).has(open)) set({ open: null, items: [], path: '', total: 0, next: null, selected: null, selection: [] })   // its home went (rehomed)
    if (get().open === null && !get().query && t.homes.length) await get().openHome(t.homes[0].id)
  },
  openHome: async (id) => {
    const n = ++seq
    set({ open: id, query: '', loading: true })
    try {
      const r = await readPage(id, get().filter, null, PAGE)
      if (n !== seq) return
      set({ items: r.items, path: r.path, total: r.total, next: r.next, ...kept(r.items, get()) })
    } finally { if (n === seq) set({ loading: false }) }
  },
  loadMore: async () => {
    const { open, next, query } = get()
    if (!open || !next || query) return
    if (more) return more
    const n = seq
    more = (async () => {
      try {
        const r = await readPage(open, get().filter, next, PAGE)
        if (n !== seq || get().open !== open) return
        const have = new Set(get().items.map((x) => x.asset.id))
        set({ items: [...get().items, ...r.items.filter((x) => !have.has(x.asset.id))], next: r.next })
      } finally { more = null }
    })()
    return more
  },
  search: async (q) => {
    if (!q.trim()) { set({ query: '' }); const o = get().open; if (o) await get().openHome(o); else await get().loadTree(); return }
    const n = ++seq
    set({ query: q, loading: true })
    try {
      const r = await unwrap(http.GET('/bin/search', { params: { query: { q } } }))
      if (n !== seq) return
      set({ open: null, items: r.items, path: '', total: r.items.length, next: null, selected: null, selection: [] })
    } finally { if (n === seq) set({ loading: false }) }
  },
  reload: () => get().refresh({ tree: true, home: true }),
  refresh: async ({ tree, home }) => {
    if (tree) await get().loadTree()
    if (!home) return
    const { open, query } = get()
    if (query) { await get().search(query); return }
    if (!open) return
    const n = ++seq                                                  // the loaded window read again in one request (the scroll stays)
    const r = await readPage(open, get().filter, null, Math.min(2000, Math.max(PAGE, get().items.length)))
    if (n !== seq) return
    set({ items: r.items, path: r.path, total: r.total, next: r.next, ...kept(r.items, get()) })
  },
  patch: (a) => {
    const { items, open } = get()
    const i = items.findIndex((x) => x.asset.id === a.id)
    if (i < 0) return
    if (!!a.trashed_at !== (open === TRASH)) { get().drop(a.id); return }     // trashed (or restored): it leaves this place
    set({ items: items.map((x, j) => (j === i ? { ...x, asset: a } : x)) })
  },
  drop: (id) => {
    const { items, selected, selection, total } = get()
    if (!items.some((x) => x.asset.id === id)) return
    set({ items: items.filter((x) => x.asset.id !== id), total: total !== null ? Math.max(0, total - 1) : null, selection: selection.filter((x) => x !== id),
      ...(selected === id ? { selected: null, viewing: false } : {}) })
  },
  setFilter: (filter) => { if (filter === get().filter) return; set({ filter }); const o = get().open; if (o && !get().query) void get().openHome(o) },
  select: (id, how = 'single') => {
    const { items, selection, selected } = get()
    let next: string[]
    if (!id) next = []
    else if (how === 'toggle') next = selection.includes(id) ? selection.filter((x) => x !== id) : [...selection, id]
    else if (how === 'range' && selected) {
      const order = items.map((x) => x.asset.id), a = order.indexOf(selected), b = order.indexOf(id)
      next = a < 0 || b < 0 ? [id] : [...new Set([...selection, ...order.slice(Math.min(a, b), Math.max(a, b) + 1)])]
    } else next = [id]
    const primary = id && next.includes(id) ? id : next[next.length - 1] ?? null
    set({ selection: next, selected: primary, ...(primary ? {} : { viewing: false }) })
    postLoupe({ type: 'show', assetId: primary })                                     // D155: the detached loupe follows
  },
  selectAll: () => { const ids = get().items.map((x) => x.asset.id); const cur = get().selected; set({ selection: ids, selected: cur && ids.includes(cur) ? cur : ids[0] ?? null }) },
  pin: (a) => { const p = get().pins; set({ pins: p.some((x) => x.id === a.id) ? p.filter((x) => x.id !== a.id) : [...p, a].slice(-4) }) },
  unpinAll: () => set({ pins: [], comparing: false }),
  compare: (on) => set({ comparing: on && get().pins.length >= 2 }),
  swap: () => { const p = get().pins; if (p.length >= 2) set({ pins: [p[1], p[0], ...p.slice(2)] }) },
  setTile: (px) => {
    const tile = Math.max(TILE.min, Math.min(TILE.max, Math.round(px)))
    set({ tile })
    try { localStorage.setItem(TILE_KEY, String(tile)) } catch { /* a private window keeps it for the session */ }
  },
  reveal: async (id) => {
    const r = await unwrap(http.GET('/bin/things/{aid}', { params: { path: { aid: id } } })).catch(() => null)
    if (!r) return false
    if (!get().homes.length) await get().loadTree()
    const home = r.asset.trashed_at ? TRASH : r.home_id
    if (!home) return false
    if (get().filter !== 'all') set({ filter: 'all' })
    if (get().open !== home || get().query) await get().openHome(home)
    for (let i = 0; i < 10 && get().next && !get().items.some((x) => x.asset.id === id); i++) await get().loadMore()   // its page, at most 2,000 in
    if (!get().items.some((x) => x.asset.id === id)) return false
    get().select(id)
    return true
  },
  toggle: (id) => set({ expanded: { ...get().expanded, [id]: !get().expanded[id] } }),
}))

/** What stays of the selection when the open place is read again: the things still in it. */
function kept(items: BinThing[], s: Pick<BinState, 'selected' | 'selection'>): Pick<BinState, 'selected' | 'selection'> {
  const ids = new Set(items.map((x) => x.asset.id))
  const selection = s.selection.filter((x) => ids.has(x))
  return { selection, selected: s.selected && ids.has(s.selected) ? s.selected : selection[selection.length - 1] ?? null }
}

/** The things selected, in the grid's order (the verbs' subject): the selection, else the one the Inspector shows. */
export function selectedThings(s: Pick<BinState, 'items' | 'selection' | 'selected'> = useBin.getState()): BinThing[] {
  const ids = new Set(s.selection.length ? s.selection : s.selected ? [s.selected] : [])
  return s.items.filter((x) => ids.has(x.asset.id))
}

/** Whether a frame touches the open place: a change of one of its pages, a thing landing on no page while the imports are open, the
 *  record of the open home renamed or its roles changed. */
export function touches(f: { type: string; data?: unknown }, s: Pick<BinState, 'open' | 'homes' | 'query'>): boolean {
  if (s.query) return f.type !== 'story.changed' && f.type !== 'timeline.updated'
  if (!s.open) return false
  if (s.open === TRASH) return f.type === 'asset.updated' || f.type === 'asset.created'
  const node = homesById(s.homes).get(s.open)
  if (!node) return false
  const d = (f.data ?? {}) as { ids?: string[]; id?: string }
  if (f.type === 'group.changed') { const mine = subtreeIds(node); return (d.ids ?? []).some((g) => mine.has(g)) }
  if (f.type === 'asset.created') return node.path === 'imports'               // a thing on no page; one landing in a home comes as group.changed
  if (f.type === 'story.changed') return !!d.id && subtreeHasRecord(node, d.id)    // a hero or a frame chosen: the badges move
  return false
}
const subtreeHasRecord = (n: BinNode, id: string): boolean => n.path.split('/').includes(id) || n.children.some((k) => subtreeHasRecord(k, id))

let soon: number | null = null
let want: { tree?: boolean; home?: boolean } = {}
let users = 0
let stop: (() => void) | null = null
/** Mounted with the layer and with the drawer (B1: one store, started once for both): the tree, the first home, and the records' frames
 *  applied (B0: in place, the reads batched shortly after). Returns the cleanup; the last one stops it. */
export function startBin(): () => void {
  users += 1
  if (users === 1) stop = listen()
  else void useBin.getState().loadTree()
  return () => { users -= 1; if (users === 0) { stop?.(); stop = null } }
}

function listen(): () => void {
  void useBin.getState().loadTree()
  void import('../../suites/story/storyStore').then((m) => { if (!m.useStory.getState().profiles.length) void m.useStory.getState().loadProfiles() })   // B2a: Add to World ▸ lists them
  const off = onRecords('ui2.bin', ['group.changed', 'asset.created', 'asset.deleted', 'asset.updated', 'story.changed', 'timeline.updated'], (f) => {
    const s = useBin.getState()
    if (f.type === 'asset.updated') s.patch(f.data as Asset)
    if (f.type === 'asset.deleted') s.drop(String((f.data as { id?: string } | null)?.id ?? ''))
    want = { tree: true, home: want.home || touches(f, s) }
    if (soon !== null) window.clearTimeout(soon)
    soon = window.setTimeout(() => { soon = null; const w = want; want = {}; void useBin.getState().refresh(w) }, 300)
  })
  const offLoupe = onLoupe((m) => { if (m.type === 'hello') postLoupe({ type: 'show', assetId: useBin.getState().selected }) })   // a window opened: what it shows
  return () => { off(); offLoupe(); if (soon !== null) window.clearTimeout(soon); want = {} }
}
