// The Catalogue components (grid, loupe, compare, inspector, strip) read their store through this context so
// other suites can host them on a different store instance (Generate shows its own results, 09 §4).
import { createContext, useContext } from 'react'
import type { StoreApi, UseBoundStore } from 'zustand'
import { useCatalogue, type CatalogueState } from './catalogueStore'

export type CatalogueHook = UseBoundStore<StoreApi<CatalogueState>>
export const CatalogueStoreCtx = createContext<CatalogueHook>(useCatalogue)

export function useCat(): CatalogueState
export function useCat<T>(selector: (s: CatalogueState) => T): T
export function useCat<T>(selector?: (s: CatalogueState) => T) {
  const hook = useContext(CatalogueStoreCtx)
  return selector ? hook(selector) : hook()
}
