// D66 "Go to origin": a job's `origin {suite, surface, ref?, payload?}` names where it was started; this switches to that suite and shows
// the thing it was started on. Like `applyEvent`, it reaches the suite stores through dynamic imports, so the frame (the Dock) stays
// ignorant of suite internals.
import type { Job } from '../api/types'
import { useSession } from './session'

type Origin = NonNullable<Job['origin']>

const SUITE_LABEL: Record<Origin['suite'], string> = { generate: 'Generate', edit: 'Edit', animate: 'Animate', catalogue: 'Catalogue', stage: 'Stage', api: 'API' }

/** False for jobs without an origin (queued before D66) and for jobs submitted through the API by a script (no suite to go to). */
export const canGoToOrigin = (j: Pick<Job, 'origin'>): boolean => !!j.origin && j.origin.suite !== 'api'

/** A short description for tooltips: "Generate · results", "Edit · ai · doc_…". */
export function originLabel(o: Origin | null | undefined): string {
  if (!o) return 'no origin (queued before origins were recorded)'
  return [SUITE_LABEL[o.suite], o.surface, o.ref].filter(Boolean).join(' · ')
}

export function goToOrigin(j: Job): void {
  const o = j.origin
  if (!o || !canGoToOrigin(j)) return
  const s = useSession.getState()
  switch (o.suite) {
    case 'generate':                                              // the job's batch in Generate's results ("this batch")
      s.setSuite('generate')
      void import('../suites/generate/generateStore').then((m) => m.useGenerate.setState({ lastBatch: m.batchOf(j), show: 'batch' }))
      break
    case 'animate':                                               // the clip the job was started on, when there was one
      s.setSuite('animate')
      if (o.ref) { const ref = o.ref; void import('../suites/animate/animateStore').then((m) => { const an = m.useAnimate.getState(); void an.loadClips().then(() => an.select(ref)) }) }
      break
    case 'edit':                                                  // the document the AI request ran on
      s.setSuite('edit')
      if (o.ref) { const ref = o.ref; void import('../suites/edit/editorStore').then((m) => { const ed = m.useEditor.getState(); if (ed.doc?.id !== ref) void ed.openDocument(ref) }) }
      break
    case 'catalogue':                                             // the group page (or, without one, the folder) in the active pane
      s.setSuite('catalogue')
      void import('../suites/catalogue/split').then((m) => {
        const sp = m.useSplit.getState()
        const c = m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState()
        const folder = typeof o.payload?.folder === 'string' ? o.payload.folder : null
        if (o.ref) m.openPlace(c, { group: o.ref })
        else if (folder) void c.setQuery({ folder: folder as typeof c.q.folder, group_id: undefined, collection_id: undefined })
      })
      break
    default: break
  }
}
