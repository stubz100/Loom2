// The album (D34, proto01_design/01 §6a, §6c): the group tree for the Places panel and the group verbs. The pages themselves
// (free arrangement) are loaded by the Stage; this store keeps the tree, which nodes are expanded, and calls the API.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { http, unwrap } from '../../api/client'
import type { AlbumNode as ApiAlbumNode, PathStep as ApiPathStep } from '../../api/types'
import { useSession } from '../../store/session'

export const ALBUM_ID = 'album'

export type AlbumNode = ApiAlbumNode
export interface ItemRef { kind: 'asset' | 'group'; id: string }
export type PathStep = ApiPathStep

interface AlbumState {
  tree: AlbumNode | null
  expanded: Record<string, boolean>
  load: () => Promise<void>
  toggle: (id: string, open?: boolean) => void
  find: (id: string) => AlbumNode | null
  pathOf: (id: string) => PathStep[]
  create: (name: string, parentId?: string) => Promise<string>
  rename: (id: string, name: string) => Promise<void>
  setCover: (id: string, assetId: string) => Promise<void>
  remove: (id: string) => Promise<number>
  ungroup: (id: string) => Promise<void>
  duplicate: (id: string) => Promise<void>
  move: (items: ItemRef[], to: string | null, positions?: { x: number; y: number; w?: number }[]) => Promise<void>
  duplicateAssets: (ids: string[]) => Promise<string[]>
}

const err = (what: string) => (e: unknown) => { useSession.getState().toast(`${what} failed: ${(e as Error).message}`, 'error'); throw e }

export const useAlbum = create<AlbumState>()(persist((set, get) => ({
  tree: null, expanded: {},
  load: async () => { try { set({ tree: await unwrap(http.GET('/groups/tree')) }) } catch { /* no project yet */ } },
  toggle: (id, open) => set({ expanded: { ...get().expanded, [id]: open ?? !get().expanded[id] } }),
  find: (id) => {
    const walk = (n: AlbumNode | null): AlbumNode | null => { if (!n) return null; if (n.id === id) return n; for (const c of n.children) { const f = walk(c); if (f) return f } return null }
    return walk(get().tree)
  },
  pathOf: (id) => {
    const walk = (n: AlbumNode, trail: PathStep[]): PathStep[] | null => {
      const here = [...trail, { id: n.id, name: n.name }]
      if (n.id === id) return here
      for (const c of n.children) { const f = walk(c, here); if (f) return f }
      return null
    }
    const t = get().tree
    return (t && walk(t, [])) ?? []
  },
  create: async (name, parentId = ALBUM_ID) => {
    const g = await unwrap(http.POST('/groups', { body: { name, parent_id: parentId } })).catch(err('New group'))
    get().toggle(parentId, true)
    await get().load()
    return g.id
  },
  rename: async (id, name) => { await unwrap(http.PATCH('/groups/{gid}', { params: { path: { gid: id } }, body: { name } })).catch(err('Rename')); await get().load() },
  setCover: async (id, assetId) => { await unwrap(http.PATCH('/groups/{gid}', { params: { path: { gid: id } }, body: { cover_id: assetId } })).catch(err('Set cover')); await get().load() },
  remove: async (id) => { const r = await unwrap(http.DELETE('/groups/{gid}', { params: { path: { gid: id } } })).catch(err('Delete group')); await get().load(); return r.unprocessed.length },
  ungroup: async (id) => { await unwrap(http.POST('/groups/{gid}/ungroup', { params: { path: { gid: id } } })).catch(err('Ungroup')); await get().load() },
  duplicate: async (id) => { await unwrap(http.POST('/groups/{gid}/duplicate', { params: { path: { gid: id } } })).catch(err('Duplicate')); await get().load() },
  move: async (items, to, positions) => { await unwrap(http.POST('/groups/move', { body: { items, to, positions } })).catch(err('Move')); await get().load() },
  duplicateAssets: async (ids) => (await unwrap(http.POST('/assets/duplicate', { body: { ids } })).catch(err('Duplicate'))).ids,
}), { name: 'loom2.album', partialize: (s) => ({ expanded: s.expanded }) as never }))

/** Every group as a flat list with its depth, for "Move to group ▸" menus. */
export function flatGroups(tree: AlbumNode | null): { node: AlbumNode; depth: number }[] {
  const out: { node: AlbumNode; depth: number }[] = []
  const walk = (n: AlbumNode, d: number) => { for (const c of n.children) { out.push({ node: c, depth: d }); walk(c, d + 1) } }
  if (tree) walk(tree, 0)
  return out
}
