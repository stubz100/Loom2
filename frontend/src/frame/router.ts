// U1 (D157, proto01_UI2 06 §5.3): the router seam — where the author is, and the one way to go elsewhere. A place is still named as the
// old shell named it, a suite and its rail tab (`ui.suite`); stores and commands call `navigate`, and the shell (B2, D159: the only one)
// maps the call onto its layers. A leaf module: it imports the session store
// only, so a store reaches it with a static import (the suite registry imports the suites, which is why they reached the rail dynamically).
import { create } from 'zustand'
import type { Suite } from '../api/types'
import { useSession } from '../store/session'
import { DEFAULT_RAIL } from './railTabs'

/** A place in the old shell: a suite and, when named, the rail tab (the panel section) it opens on. U3f: `layer` — the new shell's layer
 *  it is in when that is not the suite's own (World's *See in clay* is the stage suite on the World layer). */
export interface Place { suite: Suite; tab?: string; layer?: Layer }

/** D157 (02 §1): the new shell's four layers. */
export type Layer = 'world' | 'shots' | 'episode' | 'bin'

interface RailState { active: Record<string, string>; setActive: (suite: string, tab: string) => void }
/** The rail tab each suite opens on (a session's memory, not persisted). */
export const useRailState = create<RailState>()((set, get) => ({ active: {}, setActive: (suite, tab) => set({ active: { ...get().active, [suite]: tab } }) }))

/** Remember the tab a suite opens on, without going there (a column's scroll, a section switch inside the suite on screen). */
export const setRailTab = (suite: string, tab: string): void => useRailState.getState().setActive(suite, tab)

/** The suite's rail tabs and the one it is on — the section a suite's parts show (Story's World · Cast · Flow · Shots · Episode). */
export function useSuiteRail() {
  const suite = useSession((s) => s.ui.suite)
  const tabs = DEFAULT_RAIL[suite] ?? []
  const active = useRailState((r) => r.active[suite]) ?? tabs[0]?.id ?? ''
  const setActive = useRailState((r) => r.setActive)
  return { tabs, active, setActive: (tab: string) => setActive(suite, tab) }
}

type Listener = (p: Place) => void
const listeners = new Set<Listener>()
/** The new shell hears every navigation, with the tab resolved; returns the unsubscribe. */
export function onNavigate(fn: Listener): () => void {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}

/** Go to a place: its tab first (so the suite opens on it), then its suite. */
export function navigate(p: Place): void {
  if (p.tab) setRailTab(p.suite, p.tab)
  useSession.getState().setSuite(p.suite)
  const at: Place = { suite: p.suite, tab: p.tab ?? useRailState.getState().active[p.suite], ...(p.layer ? { layer: p.layer } : {}) }
  for (const fn of listeners) fn(at)
}

/** Where the old shell is now. */
export function currentPlace(): Place {
  const suite = useSession.getState().ui.suite
  return { suite, tab: useRailState.getState().active[suite] }
}

/** D157 (02 §1): the layer an old place belongs to — Image's Make and Edit and Story's World and Cast are World; Animate's three levels and
 *  Story's Flow and Shots are Shots; Story's Episode is Episode; the Catalogue is the Bin. */
export function layerOf(p: Place): Layer {
  if (p.layer) return p.layer
  switch (p.suite) {
    case 'animate': case 'stage': case 'final': return 'shots'
    case 'catalogue': return 'bin'
    case 'story': return p.tab === 'flow' || p.tab === 'shots' ? 'shots' : p.tab === 'episode' ? 'episode' : 'world'
    default: return 'world'
  }
}
