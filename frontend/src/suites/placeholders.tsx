// Suites that arrive in later milestones keep their frame slots so the frame can be judged whole (07 §1.1).
import type { SuiteDef } from '../frame/suiteRegistry'
import { DEFAULT_RAIL } from '../frame/Rail'
import { useSession } from '../store/session'

export function placeholderSuite(id: string, title: string, milestone: string, doc: string): SuiteDef {
  return {
    id, rail: DEFAULT_RAIL[id] ?? [],
    Panel: ({ tab }) => <span style={{ color: 'var(--fg3)' }}>{title} · {tab} — arrives in {milestone} ({doc}).</span>,
    Strip: () => <span>{title}</span>,
    Stage: () => {
      const project = useSession((s) => s.project)
      return <div className="placeholder"><div><h2>{title}</h2>{project?.open ? `arrives in ${milestone} — see ${doc}` : 'open or create a project to begin'}</div></div>
    },
    Inspector: () => <span style={{ color: 'var(--fg3)' }}>Nothing selected.</span>,
  }
}
