// Each suite contributes its rail tabs, panel, strip, stage and inspector to the frame (07 §2). The registry
// keeps the frame generic: suites register React components; the frame places them.
// D69: Edit, Animate and Models load on first use (their Pixi, Mediabunny and editor code stay out of the startup bundle). Commands register
// at import (D32: Help, menus and accelerators list them before the first visit): Animate's load with the frame; Edit's import the editor
// store, which owns Pixi textures, so they register with Edit's code, preloaded on the first idle moment after startup (below).
import type { ComponentType } from 'react'
import { create } from 'zustand'
import { useSession } from '../store/session'
import '../suites/animate/animateCommands'
import { CatalogueSuite } from '../suites/catalogue/CatalogueSuite'
import { GenerateSuite } from '../suites/generate/GenerateSuite'
import { lazySuite, preloadSuite } from './lazySuite'
import { DEFAULT_RAIL, type RailTab } from './railTabs'

export interface SuiteDef {
  id: string
  rail: RailTab[]
  Panel: ComponentType<{ tab: string }>
  Strip: ComponentType
  Stage: ComponentType
  Inspector: ComponentType
  primary?: { label: string; run: () => void; disabled?: boolean }
  wideStrip?: boolean                     // the strip spans panel, stage and inspector (Catalogue, D34)
  keepAlive?: boolean                     // D69: the Stage stays mounted (hidden) after the first visit — see frame/stageKeep.ts
  PrimaryAction?: ComponentType
}

export const SUITE_DEFS: Record<string, SuiteDef> = {
  catalogue: CatalogueSuite, generate: GenerateSuite,
  edit: lazySuite({ id: 'edit', rail: DEFAULT_RAIL.edit, keepAlive: true }, () => import('../suites/edit/EditSuite').then((m) => m.EditSuite), ['Panel', 'Strip', 'Stage', 'Inspector', 'PrimaryAction']),
  animate: lazySuite({ id: 'animate', rail: DEFAULT_RAIL.animate, keepAlive: true }, () => import('../suites/animate/AnimateSuite').then((m) => m.AnimateSuite), ['Panel', 'Strip', 'Stage', 'Inspector', 'PrimaryAction']),
  models: lazySuite({ id: 'models', rail: DEFAULT_RAIL.models }, () => import('../suites/models/ModelsSuite').then((m) => m.ModelsSuite), ['Panel', 'Strip', 'Stage', 'Inspector']),
}

// Edit's code (and with it its commands) loads on the first idle moment after startup — after the Catalogue's first paint, before the usual
// next step (Open in Edit) — so the first open does not wait for the chunk; Animate and Models load on a pointer over their tab or on use.
{
  const idle = window.requestIdleCallback ?? ((f: () => void) => window.setTimeout(f, 200))
  idle(() => preloadSuite('edit'))
}

interface RailState { active: Record<string, string>; setActive: (suite: string, tab: string) => void }
const useRailState = create<RailState>()((set, get) => ({ active: {}, setActive: (suite, tab) => set({ active: { ...get().active, [suite]: tab } }) }))

export const setRailTab = (suite: string, tab: string) => useRailState.getState().setActive(suite, tab)

// ?suite=X&tab=Y opens that panel section at launch (07 §1.7 deep links; scripts/csp_check.py and the acceptance loops use it)
{
  const q = new URLSearchParams(location.search)
  const s = q.get('suite'), t = q.get('tab')
  if (s && t && SUITE_DEFS[s]?.rail.some((r) => r.id === t)) useRailState.getState().setActive(s, t)
}

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
