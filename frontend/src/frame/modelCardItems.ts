// D186: the model cards' items from /capabilities (D65: no model id in code) — beside ModelCards.tsx, which exports the component alone.
import type { Capabilities } from '../api/types'
import { byOrder } from '../store/modelCaps'

export interface ModelCardItem {
  id: string; label: string; hint?: string | null; license?: string | null; health?: string | null
  seconds?: number | null; measured?: boolean | null                  // the estimate, and whether it was measured on the rig for this job
  distilled?: boolean; off?: boolean; offWhy?: string | null          // off: offered by the roster but not wired in this build
}

type ImageCap = Capabilities['models'][string]
/** The image models of /capabilities that pass `keep`, in the server's order, as cards (the Make column's: every model that generates). */
export function imageModelItems(caps: Capabilities | null | undefined, keep: (c: ImageCap, id: string) => boolean): ModelCardItem[] {
  return byOrder(caps?.models).filter(([id, c]) => keep(c, id)).map(([id, c]) => ({
    id, label: c.label, hint: c.hint, license: c.license, health: c.health, distilled: !!c.distilled, off: !c.wired, offWhy: 'not available in this build' }))
}

/** `items` with `first` moved to the front (a recipe kind's default leads its list, as the Edit panel's lists did). */
export function defaultFirstItems(items: ModelCardItem[], first: string | null | undefined): ModelCardItem[] {
  const i = first ? items.findIndex((m) => m.id === first) : -1
  return i > 0 ? [items[i], ...items.slice(0, i), ...items.slice(i + 1)] : items
}
