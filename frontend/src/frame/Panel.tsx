import { useSession } from '../store/session'
import { useSuite, useSuiteRail } from './suiteRegistry'

export function Panel() {
  const open = useSession((s) => s.ui.panelOpen)
  const suite = useSuite()
  const { tabs, active } = useSuiteRail()
  const tab = tabs.find((t) => t.id === active)
  if (!open) return <aside className="panel closed" />
  return (
    <aside className="panel">
      <div className="head">{tab?.label ?? suite.id}</div>
      <div className="body">{suite.Panel({ tab: active })}</div>
      {suite.primary && <div className="foot"><button className="primary" disabled={suite.primary.disabled} onClick={suite.primary.run}>{suite.primary.label}</button></div>}
    </aside>
  )
}
