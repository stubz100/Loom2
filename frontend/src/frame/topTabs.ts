import type { Suite } from '../api/types'
import { useSession } from '../store/session'
import type { TopTab } from './railTabs'
import { navigate } from './router'

/** D90 (02 §3): a top tab opens its suite; D95 (IM1) the Image tab returns to its mode last open (Make = the generate suite, Edit = the edit
 *  suite), and (AN1) Animate to its level last open (Performance = the animate suite, Clay = the stage suite). D125: Story and the Catalogue
 *  are a suite each. */
export function openTopTab(t: TopTab): void {
  const s = useSession.getState()
  if (t.suites.includes(s.ui.suite)) return
  navigate({ suite: (t.id === 'image' ? s.ui.imageLast ?? 'generate' : t.id === 'animate' ? s.ui.animateLast ?? 'animate' : t.id) as Suite })
}

/** The suite a tab's pointer-over preloads (D69): Image's Edit is the lazy one; Animate's level last open (AN1). */
export const preloadOf = (t: TopTab): string => (t.id === 'image' ? 'edit' : t.id === 'animate' ? useSession.getState().ui.animateLast ?? 'animate' : t.id)
