// The Catalogue components (grid, loupe, compare, inspector, strip) read their store through this context so
// other suites can host them on a different store instance (Generate shows its own results, 09 §4).
// `activeCatalogue` points at whichever instance is on screen, for the registry commands (07 §3c).
import { createContext, useContext, useEffect } from 'react'
import type { StoreApi, UseBoundStore } from 'zustand'
import { useCatalogue, type CatalogueState } from './catalogueStore'

export type CatalogueHook = UseBoundStore<StoreApi<CatalogueState>>
export const CatalogueStoreCtx = createContext<CatalogueHook>(useCatalogue)
export const activeCatalogue: { current: CatalogueHook } = { current: useCatalogue }
/** True inside a Catalogue pane: the split decides which pane is active, not which one mounted last. */
export const InPaneCtx = createContext(false)

export function useCat(): CatalogueState
export function useCat<T>(selector: (s: CatalogueState) => T): T
export function useCat<T>(selector?: (s: CatalogueState) => T) {
  const hook = useContext(CatalogueStoreCtx)
  return selector ? hook(selector) : hook()
}

/** Mounted by the grid: the commands act on the store instance that is on screen. */
export function useActiveCatalogue(): void {
  const hook = useContext(CatalogueStoreCtx)
  const inPane = useContext(InPaneCtx)
  useEffect(() => { if (inPane) return; activeCatalogue.current = hook; return () => { if (activeCatalogue.current === hook) activeCatalogue.current = useCatalogue } }, [hook, inPane])
}
