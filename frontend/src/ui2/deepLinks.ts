// B2a (D159, 11 §7): the deep links the new shell follows at start — `?suite=edit&tool=…&ai=…&sel=…&asset=…` (D71: the editor with a tool or
// an AI operation chosen) opens World's Edit on that picture (frame/openWith's `deepLinkOf`). The other places come by the hash (layers.ts).
import { deepLinkOf } from '../frame/openWith'

let done = false
export async function followDeepLink(): Promise<void> {
  if (done) return
  done = true
  const d = deepLinkOf(new URLSearchParams(location.search))
  if (!d) return
  if (d.assetId) { const { editAnywhere } = await import('./world/editAnywhere'); await editAnywhere(d.assetId, d.o); return }
  const { openWith } = await import('../frame/openWith')
  await openWith(null, d.o)
}
