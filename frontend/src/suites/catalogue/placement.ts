// D90 (B17): where the selected assets sit — a group id (the Album page included), or null for Unprocessed — as `/groups/where` last said
// (the Inspector asks it for every selection); cleared whenever the album tree changes (a move, a group made or removed), so the
// `cat.toUnprocessed` command and the Inspector's "Back to Unprocessed" read one answer.
import { useAlbum } from './albumStore'
import type { Query } from './catalogueStore'

const known = new Map<string, string | null>()

export function notePlacements(r: Record<string, { group_id: string } | null | undefined>): void {
  for (const [id, v] of Object.entries(r)) known.set(id, v?.group_id ?? null)
}
export const clearPlacements = (): void => known.clear()

/** Every one of `ids` is placed in a group: always on a group's page, never in Unprocessed or the Trash, elsewhere as `/groups/where` said
 *  (unknown counts as not placed). */
export function allPlaced(ids: string[], q: Pick<Query, 'folder' | 'group_id'>): boolean {
  if (!ids.length || q.folder === 'trash') return false
  if (q.group_id) return true
  if (q.folder === 'unprocessed') return false
  return ids.every((id) => !!known.get(id))
}

useAlbum.subscribe((s, p) => { if (s.tree !== p.tree) known.clear() })
