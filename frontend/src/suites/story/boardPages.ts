// W27: the pages a Flow node's Board may be — World's (the Look, the characters, the props, the places) and the node's own shot's, not every
// page of the project (the other shots', the Episode's, Imports).
import type { BinNode } from '../../api/types'

/** The group ids a Board may be, from the Bin's homes; null while they are not known (every page offered). */
export function boardPages(homes: BinNode[] | null | undefined, shotId: string | null | undefined): Set<string> | null {
  if (!homes?.length) return null
  const out = new Set<string>()
  const own = (p: string) => p === 'world' || p.startsWith('world/') || (!!shotId && (p === `shots/${shotId}` || p.startsWith(`shots/${shotId}/`)))
  const walk = (h: BinNode, keep: boolean) => {
    const k = keep || own(h.path)
    if (k) out.add(h.id)
    for (const c of h.children) walk(c, k)
  }
  for (const h of homes) walk(h, false)
  return out
}
