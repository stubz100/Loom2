// The split Stage (D34, proto01_design/01 §6c): single, stacked (a page above Unprocessed, the everyday sorting layout) or side by
// side (two groups, or a group and Unprocessed). Each pane is its own catalogue store — place, query, selection, zoom; the strip,
// Places and the Inspector follow the active pane (the one last clicked), and so do the registry commands.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { activeCatalogue, type CatalogueHook } from './catalogueContext'
import { useCatalogue, useCataloguePane2, type CatalogueState } from './catalogueStore'

export type SplitMode = 'single' | 'stacked' | 'side'
export type Place = 'unprocessed' | 'library' | 'trash' | { group: string }

interface SplitState {
  mode: SplitMode; active: 0 | 1; ratio: number
  setMode: (m: SplitMode) => void
  setActive: (i: 0 | 1) => void
  setRatio: (r: number) => void
}

export const useSplit = create<SplitState>()(persist((set) => ({
  mode: 'single', active: 0, ratio: 0.58,
  setMode: (mode) => set({ mode, ...(mode === 'single' ? { active: 0 } : {}) }),
  setActive: (active) => { set({ active }); activeCatalogue.current = paneStore(active) },
  setRatio: (ratio) => set({ ratio: Math.max(0.2, Math.min(0.8, ratio)) }),
}), { name: 'loom2.split', partialize: (s) => ({ mode: s.mode, ratio: s.ratio }) as never }))

export const paneStore = (i: 0 | 1): CatalogueHook => (i === 0 ? useCatalogue : useCataloguePane2)

/** The store of the pane the strip, Places and Inspector serve. */
export function useActivePaneStore(): CatalogueHook {
  const i = useSplit((s) => (s.mode === 'single' ? 0 : s.active))
  return paneStore(i)
}

/** Open a place in a pane's view. */
export function openPlace(c: CatalogueState, place: Place): void {
  if (place === 'unprocessed') void c.setQuery({ folder: 'unprocessed', group_id: undefined, collection_id: undefined })
  else if (place === 'library') void c.setQuery({ folder: 'all', group_id: undefined, collection_id: undefined })
  else if (place === 'trash') void c.setQuery({ folder: 'trash', group_id: undefined, collection_id: undefined })
  else void c.setQuery({ folder: 'all', group_id: place.group, collection_id: undefined })
}

/** Open a place in the other pane, splitting the Stage first (stacked) when it is single. */
export function openInOtherPane(place: Place): void {
  const sp = useSplit.getState()
  if (sp.mode === 'single') sp.setMode('stacked')
  const other = (sp.mode === 'single' ? 1 : sp.active === 0 ? 1 : 0) as 0 | 1
  openPlace(paneStore(other).getState(), place)
}

/** Swap what the two panes show (their places and queries). */
export function swapPanes(): void {
  const a = useCatalogue.getState().q, b = useCataloguePane2.getState().q
  void useCatalogue.getState().setQuery({ ...b })
  void useCataloguePane2.getState().setQuery({ ...a })
}
