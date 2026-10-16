// D90 (02 §7): Models & engine — a sheet over the frame opened from ☰, the engine and weights chips, the banner and every Fetch button
// (those open it on the missing weights). The roster and engine parts are the old Models suite's, loaded on first open (D69).
import { X } from 'lucide-react'
import { lazy, Suspense, useEffect } from 'react'
import { useSession } from '../store/session'

const Body = lazy(() => import('../suites/models/ModelsSuite').then((m) => ({ default: m.ModelsSheetBody })))

export function ModelsSheet() {
  const sheet = useSession((s) => s.modelsSheet)
  const open = useSession((s) => s.openModels)
  const close = useSession((s) => s.closeModels)
  useEffect(() => {
    if (!sheet) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape' && !useSession.getState().ask) { e.preventDefault(); e.stopImmediatePropagation(); close() } }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [sheet, close])
  if (!sheet) return null
  const tab = sheet.tab ?? 'roster'
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal models-sheet" role="dialog" aria-label="Models & engine" onClick={(e) => e.stopPropagation()}>
        <div className="head">
          Models &amp; engine
          <span className="segmented" style={{ marginLeft: 12 }}>
            <button className={tab === 'roster' ? 'active' : ''} onClick={() => open({ ...sheet, tab: 'roster' })}>Roster</button>
            <button className={tab === 'engine' ? 'active' : ''} onClick={() => open({ ...sheet, tab: 'engine' })}>Engine</button>
          </span>
          <span className="spacer" />
          <button className="quiet" onClick={close} title="Close (Esc)" aria-label="Close"><X size={16} /></button>
        </div>
        <div className="body"><Suspense fallback={<p className="muted" style={{ padding: 16 }}>Loading…</p>}><Body tab={tab} missing={!!sheet.missing} /></Suspense></div>
      </div>
    </div>
  )
}
