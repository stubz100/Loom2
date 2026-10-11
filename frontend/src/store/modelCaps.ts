// D65: model knowledge lives in the backend specs and reaches the panels through /capabilities — the suites name no model ids.
// These helpers read the session's capabilities (models, i2v.models, tools, defaults) so every panel derives its choices the same way.
import type { Capabilities } from '../api/types'
import { useSession } from './session'

type Caps = Capabilities | null | undefined
const now = (): Caps => useSession.getState().capabilities

/** A capability map's entries in the server's `order` (ties by id). */
export function byOrder<T extends { order: number }>(m: Record<string, T> | null | undefined): [string, T][] {
  return Object.entries(m ?? {}).sort((a, b) => a[1].order - b[1].order || a[0].localeCompare(b[0]))
}

/** The default model for a recipe kind (t2i, i2i, inpaint, upscale, segment, i2v) for this session's variant; '' before caps load. */
export function defaultModel(kind: string, caps: Caps = now()): string {
  return caps?.defaults?.[kind] ?? ''
}

/** `id` when the capabilities offer it and `ok` accepts it, else the recipe kind's default (lazy resolution of '' / stale ids). */
export function resolveModel(id: string | null | undefined, kind: string, ok: (id: string) => boolean, caps: Caps = now()): string {
  if (id && (!caps || ok(id))) return id
  return defaultModel(kind, caps) || id || ''
}

/** The short name of any model or tool the capabilities list (job rows, clip rows); the id itself when unknown. */
export function shortName(id: string | null | undefined, caps: Caps = now()): string {
  if (!id) return ''
  return caps?.models?.[id]?.short ?? caps?.i2v?.models?.[id]?.short ?? caps?.tools?.[id]?.short ?? id
}

/** The first tool (in order) whose AI Select modes include `mode` ('subject' = the matte, 'text' / 'points' / 'box' = prompted). */
export function segmentTool(mode: string, caps: Caps = now()): string | null {
  return byOrder(caps?.tools).find(([, t]) => t.recipes.segment?.includes(mode))?.[0] ?? null
}

/** The image model behind Fill Hero / Outpaint hero (recipes.inpaint_hero); null where none is offered (e.g. under `open`). */
export function heroModel(caps: Caps = now()): string | null {
  return byOrder(caps?.models).find(([, m]) => m.recipes.inpaint_hero)?.[0] ?? null
}

/** Ids in `order`, the recipe kind's default first (the Edit panel's model lists keep their default at the top). */
export function defaultFirst(ids: string[], kind: string, caps: Caps = now()): string[] {
  const d = defaultModel(kind, caps)
  return d && ids.includes(d) ? [d, ...ids.filter((x) => x !== d)] : ids
}
