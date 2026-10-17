// D90 (02 §6.3): the preset swatch pack — one small generated sample per *look* preset (lighting, mood, background, style words, scene,
// subject words), kept in app state by the server (`/preset-icons`, routes/preset_icons.py). This store is the client's index: which
// field + value has a swatch, its URL (cache-busted by `updated_at`), and the verb that queues the missing ones. D92: a library entry of a
// look field gets its picture by itself — `autoPicture` queues one small job (run now) when the entry is added or its words change and
// it has none; `swatchBusy` says a tile's picture is being made (its field's glyph shows meanwhile, with a busy mark).
import { create } from 'zustand'
import { api, http, unwrap, type ApiError } from '../../api/client'
import type { Job } from '../../api/types'
import { glyphFor } from '../../frame/presetGlyphs'
import { useSession } from '../../store/session'

/** The fields whose presets are pictures (a look), not geometry — the rest get drawn glyphs (frame/presetGlyphs.tsx). D92: the subject's
 *  action and pose and the lead text too; a negative never (a picture of a negative is meaningless). */
export const SWATCH_FIELDS: ReadonlySet<string> = new Set(['scene', 'style', 'lighting', 'mood', 'background', 'subject.description', 'subject.action', 'subject.pose', 'text'])
/** D92: an entry is shown by a generated picture — a look field's words without a drawing of their own. */
export const needsPicture = (field: string, value: string): boolean => SWATCH_FIELDS.has(field) && !glyphFor(field, value) && !!value.trim()

/** D92: a swatch job for field + value still waiting or running (the tile's busy mark; no second job while one runs). */
export function swatchJob(jobs: Record<string, Job>, field: string, value: string): Job | undefined {
  return Object.values(jobs).find((j) => j.origin?.surface === 'swatch' && ['staged', 'queued', 'running'].includes(j.status)
    && (j.origin.payload as { field?: string; value?: string } | null)?.field === field && (j.origin.payload as { value?: string } | null)?.value === value)
}

interface SwatchItem { key: string; field: string; value: string; updated_at: string }
interface SwatchState {
  items: Record<string, SwatchItem>                // by `${field}\n${value}`
  loaded: boolean
  load: () => Promise<void>
  url: (field: string, value: string) => string | null
  make: (items: { field: string; value: string }[]) => Promise<number>
  /** D92: queue the picture of a new or re-worded look entry when it has none and none is being made; quiet when there is nothing to do. */
  autoPicture: (field: string, value: string) => Promise<void>
}

const id = (field: string, value: string) => `${field}\n${value}`

export const useSwatches = create<SwatchState>()((set, get) => ({
  items: {}, loaded: false,
  load: async () => {
    try {
      const r = await unwrap(http.GET('/preset-icons'))
      set({ items: Object.fromEntries(r.items.map((i) => [id(i.field, i.value), i])), loaded: true })
    } catch { set({ loaded: true }) }
  },
  url: (field, value) => { const it = get().items[id(field, value)]; return it ? api.fileUrl(`/preset-icons/${it.key}/file?v=${encodeURIComponent(it.updated_at)}`) : null },
  make: async (items) => {
    if (!items.length) return 0
    try {
      const r = await unwrap(http.POST('/preset-icons/make', { body: { items, stage: false } }))
      void useSession.getState().refreshAll()                                   // the busy marks read the jobs
      return r.items.length
    } catch (e) { useSession.getState().toast(`Sample icons failed: ${(e as ApiError).detail ?? e}`, 'error'); return 0 }
  },
  autoPicture: async (field, value) => {
    const v = value.trim()
    if (!needsPicture(field, v) || get().url(field, v) || swatchJob(useSession.getState().jobs, field, v)) return
    if (!useSession.getState().capabilities?.sample_models?.length) return     // no sample model in this build: the glyph stays
    await get().make([{ field, value: v }])
  },
}))
