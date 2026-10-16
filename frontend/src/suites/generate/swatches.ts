// D90 (02 §6.3): the preset swatch pack — one small generated sample per *look* preset (lighting, mood, background, style words, scene,
// subject words), kept in app state by the server (`/preset-icons`, routes/preset_icons.py). This store is the client's index: which
// field + value has a swatch, its URL (cache-busted by `updated_at`), and the verb that queues the missing ones.
import { create } from 'zustand'
import { api, http, unwrap, type ApiError } from '../../api/client'
import { useSession } from '../../store/session'

/** The fields whose presets are pictures (a look), not geometry — the rest get drawn glyphs (frame/presetGlyphs.tsx). */
export const SWATCH_FIELDS: ReadonlySet<string> = new Set(['scene', 'style', 'lighting', 'mood', 'background', 'subject.description', 'subject.action', 'subject.pose'])

interface SwatchItem { key: string; field: string; value: string; updated_at: string }
interface SwatchState {
  items: Record<string, SwatchItem>                // by `${field}\n${value}`
  loaded: boolean
  load: () => Promise<void>
  url: (field: string, value: string) => string | null
  make: (items: { field: string; value: string }[]) => Promise<number>
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
      return r.items.length
    } catch (e) { useSession.getState().toast(`Sample icons failed: ${(e as ApiError).detail ?? e}`, 'error'); return 0 }
  },
}))
