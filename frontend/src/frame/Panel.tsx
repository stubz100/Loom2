import { useSession } from '../store/session'
import { useSuite, useSuiteRail } from './suiteRegistry'

export function Panel() {
  const open = useSession((s) => s.ui.panelOpen)
  const suite = useSuite()
  const { tabs, active } = useSuiteRail()
  const tab = tabs.find((t) => t.id === active)
  if (!open) return <aside className="panel closed" />
  const SuitePanel = suite.Panel
  return (
    <aside className="panel">
      <div className="head">{tab?.label ?? suite.id}</div>
      <div className="body"><SuitePanel key={suite.id} tab={active} /></div>
      {suite.PrimaryAction ? <div className="foot"><suite.PrimaryAction key={suite.id} /></div> : suite.primary && <div className="foot"><button className="primary" disabled={suite.primary.disabled} onClick={suite.primary.run}>{suite.primary.label}</button></div>}
    </aside>
  )
}
