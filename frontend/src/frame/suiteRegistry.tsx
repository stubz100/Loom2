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
import { DEFAULT_RAIL, STORY_RAIL, type GroupRailTab, type RailTab } from './railTabs'

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
  panelTitle?: string                     // D90: a one-column Panel (Generate) names the suite, not the rail button it scrolled to
}

export const SUITE_DEFS: Record<string, SuiteDef> = {
  catalogue: CatalogueSuite, generate: GenerateSuite,
  edit: lazySuite({ id: 'edit', rail: DEFAULT_RAIL.edit, keepAlive: true }, () => import('../suites/edit/EditSuite').then((m) => m.EditSuite), ['Panel', 'Strip', 'Stage', 'Inspector', 'PrimaryAction']),
  animate: lazySuite({ id: 'animate', rail: DEFAULT_RAIL.animate, keepAlive: true }, () => import('../suites/animate/AnimateSuite').then((m) => m.AnimateSuite), ['Panel', 'Strip', 'Stage', 'Inspector', 'PrimaryAction']),
  models: lazySuite({ id: 'models', rail: DEFAULT_RAIL.models }, () => import('../suites/models/ModelsSuite').then((m) => m.ModelsSuite), ['Panel', 'Strip', 'Stage', 'Inspector']),
  stage: lazySuite({ id: 'stage', rail: DEFAULT_RAIL.stage, keepAlive: true }, () => import('../suites/stage/StageSuite').then((m) => m.StageSuite), ['Panel', 'Strip', 'Stage', 'Inspector', 'PrimaryAction']),   // P13 / ST1 (D81): three.js, its own WebGL2 canvas
  story: lazySuite({ id: 'story', rail: DEFAULT_RAIL.story }, () => import('../suites/story/StorySuite').then((m) => m.StorySuite), ['Panel', 'Strip', 'Stage', 'Inspector', 'PrimaryAction']),   // 17 (D85): no GPU stage, nothing kept alive
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
  const s0 = q.get('suite'), t0 = q.get('tab')
  const [s, t] = s0 === 'animate' && t0 === 'sequence' ? ['story', 'episode'] : [s0, t0]    // 17 SY4 (D85): the Sequence tab moved to Story · Episode (one release of redirect)
  if (s && t && SUITE_DEFS[s]?.rail.some((r) => r.id === t)) useRailState.getState().setActive(s, t)
  // D71: ?suite=edit&tool=ai&ai=select[&sel=subject][&asset=<id>] — Edit with that tool / AI operation chosen (frame/openWith.ts)
  if (q.get('tool') || q.get('ai')) void import('./openWith').then((m) => { const d = m.deepLinkOf(q); if (d) void m.openWith(d.assetId, d.o) })
}

export function useSuiteRail() {
  const suite = useSession((s) => s.ui.suite)
  const tabs = SUITE_DEFS[suite]?.rail ?? DEFAULT_RAIL[suite] ?? []
  const active = useRailState((r) => r.active[suite]) ?? tabs[0]?.id ?? ''
  const setActive = useRailState((r) => r.setActive)
  return { tabs, active, setActive: (tab: string) => setActive(suite, tab) }
}

/** D90: the rail the frame shows — the Story tab's six workspaces across the Story and Catalogue suites, else the suite's own tabs. */
export function useRailEntries(): { entries: GroupRailTab[]; isActive: (e: GroupRailTab) => boolean; open: (e: GroupRailTab) => void } {
  const suite = useSession((s) => s.ui.suite)
  const active = useRailState((r) => r.active)
  const own = SUITE_DEFS[suite]?.rail ?? DEFAULT_RAIL[suite] ?? []
  const entries = suite === 'story' || suite === 'catalogue' ? STORY_RAIL : own.map((t) => ({ ...t, suite }))
  const activeOf = (s: string) => active[s] ?? (SUITE_DEFS[s]?.rail ?? DEFAULT_RAIL[s] ?? [])[0]?.id
  return {
    entries,
    isActive: (e) => e.suite === suite && activeOf(e.suite) === e.id,
    open: (e) => { useRailState.getState().setActive(e.suite, e.id); if (e.suite !== suite) useSession.getState().setSuite(e.suite as never) },
  }
}

export function useSuite(): SuiteDef {
  const suite = useSession((s) => s.ui.suite)
  return SUITE_DEFS[suite]
}
