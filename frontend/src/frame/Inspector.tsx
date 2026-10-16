import { useSession } from '../store/session'
import { Resizer } from './Resizer'
import { useSuite } from './suiteRegistry'

export function Inspector() {
  const open = useSession((s) => s.ui.inspectorOpen)
  const suite = useSuite()
  if (!open) return <aside className="inspector closed" />
  const SuiteInspector = suite.Inspector
  return (
    <aside className="inspector">
      <Resizer side="inspector" />
      <div className="head">Inspector</div>
      <div className="body"><SuiteInspector key={suite.id} /></div>
    </aside>
  )
}
