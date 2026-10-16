import type { Suite } from '../api/types'
import { useSession } from '../store/session'
import type { TopTab } from './railTabs'

/** D90 (02 §3): a top tab opens its suite; the Story tab returns to the workspace last open under it (Story's own or the Catalogue). */
export function openTopTab(t: TopTab): void {
  const s = useSession.getState()
  if (t.suites.includes(s.ui.suite)) return
  s.setSuite((t.id === 'story' ? s.ui.storyLast ?? 'catalogue' : t.id) as Suite)
}
