// B2a (D159, 11 §7): the deep links the shell follows at start — `?suite=edit&tool=…&ai=…&sel=…&asset=…` (D71: the editor with a tool or
// an AI operation chosen) opens World's Edit on that picture (frame/openWith's `deepLinkOf`); B2: `?suite=edit&doc=<id>` (the CSP check, the
// acceptance loops) opens World's Edit as a free edit, where Edit's own deep link opens the document. The other places come by the hash
// (layers.ts).
import { deepLinkOf } from '../frame/openWith'
import { navigate } from '../frame/router'

let done = false
export async function followDeepLink(): Promise<void> {
  if (done) return
  done = true
  const q = new URLSearchParams(location.search)
  if (q.get('suite') === 'edit' && q.get('doc') && !q.get('asset')) {         // no entity: a free edit, saved to Imports
    const { useWorld } = await import('./world/worldStore')
    useWorld.getState().setRail('sketches')
    useWorld.setState({ mode: 'edit', free: { id: '', home: null, name: 'imports' } })
    navigate({ suite: 'edit' })
    return
  }
  const d = deepLinkOf(q)
  if (!d) return
  if (d.assetId) { const { editAnywhere } = await import('./world/editAnywhere'); await editAnywhere(d.assetId, d.o); return }
  const { openWith } = await import('../frame/openWith')
  await openWith(null, d.o)
}
