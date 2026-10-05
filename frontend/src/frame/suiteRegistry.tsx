// Each suite contributes its rail tabs, panel, strip, stage and inspector to the frame (07 §2). The registry
// keeps the frame generic: suites register React components; the frame places them.
import type { ReactNode } from 'react'
import { create } from 'zustand'
import { useSession } from '../store/session'
import { AnimateSuite } from '../suites/animate/AnimateSuite'
import { CatalogueSuite } from '../suites/catalogue/CatalogueSuite'
import { EditSuite } from '../suites/edit/EditSuite'
import { GenerateSuite } from '../suites/generate/GenerateSuite'
import { ModelsSuite } from '../suites/models/ModelsSuite'
import { DEFAULT_RAIL, type RailTab } from './railTabs'

export interface SuiteDef {
  id: string
  rail: RailTab[]
  Panel: (p: { tab: string }) => ReactNode
  Strip: () => ReactNode
  Stage: () => ReactNode
  Inspector: () => ReactNode
  primary?: { label: string; run: () => void; disabled?: boolean }
}

export const SUITE_DEFS: Record<string, SuiteDef> = {
  catalogue: CatalogueSuite, generate: GenerateSuite, edit: EditSuite, animate: AnimateSuite, models: ModelsSuite,
}

interface RailState { active: Record<string, string>; setActive: (suite: string, tab: string) => void }
const useRailState = create<RailState>()((set, get) => ({ active: {}, setActive: (suite, tab) => set({ active: { ...get().active, [suite]: tab } }) }))

export function useSuiteRail() {
  const suite = useSession((s) => s.ui.suite)
  const tabs = SUITE_DEFS[suite]?.rail ?? DEFAULT_RAIL[suite] ?? []
  const active = useRailState((r) => r.active[suite]) ?? tabs[0]?.id ?? ''
  const setActive = useRailState((r) => r.setActive)
  return { tabs, active, setActive: (tab: string) => setActive(suite, tab) }
}

export function useSuite(): SuiteDef {
  const suite = useSession((s) => s.ui.suite)
  return SUITE_DEFS[suite]
}
