import type { Suite } from '../api/types'
import { useSession } from '../store/session'
import type { TopTab } from './railTabs'

/** D90 (02 §3): a top tab opens its suite; the Story tab returns to the workspace last open under it (Story's own or the Catalogue), and
 *  D95 (IM1) the Image tab to its mode last open (Make = the generate suite, Edit = the edit suite), and (AN1) Animate to its level last
 *  open (Performance = the animate suite, Clay = the stage suite). */
export function openTopTab(t: TopTab): void {
  const s = useSession.getState()
  if (t.suites.includes(s.ui.suite)) return
  s.setSuite((t.id === 'story' ? s.ui.storyLast ?? 'catalogue' : t.id === 'image' ? s.ui.imageLast ?? 'generate' : t.id === 'animate' ? s.ui.animateLast ?? 'animate' : t.id) as Suite)
}

/** The suite a tab's pointer-over preloads (D69): Image's Edit is the lazy one; Animate's level last open (AN1). */
export const preloadOf = (t: TopTab): string => (t.id === 'image' ? 'edit' : t.id === 'animate' ? useSession.getState().ui.animateLast ?? 'animate' : t.id)
