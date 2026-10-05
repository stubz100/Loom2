import { ChevronUp, Pause, Play, X } from 'lucide-react'
import type { Job } from '../api/types'
import { selectJobsByStatus, useSession } from '../store/session'

function JobRow({ j }: { j: Job }) {
  const s = useSession()
  const label = `${j.kind} · ${String((j.recipe as { model_id?: string }).model_id ?? '')} · seed ${j.seed}`
  return (
    <div className={`job ${j.status}`}>
      <span>{label}</span>
      <span className="meta">{j.status === 'running' ? j.progress_text : j.status}{j.wall_s ? ` · ${j.wall_s}s` : ''}</span>
      {(j.status === 'running' || j.status === 'queued') && <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>}
      {j.error && <div className="err">{j.error}</div>}
      <span className="meta">{j.id}</span>
      <span>
        {(j.status === 'running' || j.status === 'queued') && <button className="quiet" title="cancel" onClick={() => void s.cancelJob(j.id)}><X size={14} /></button>}
        {['done', 'failed', 'cancelled'].includes(j.status) && <button className="quiet" title="remove" onClick={() => void s.deleteJob(j.id)}><X size={14} /></button>}
      </span>
    </div>
  )
}

export function Dock() {
  const s = useSession()
  const { running, queued, recent } = useSession(selectJobsByStatus)
  const active = running[0]
  const preview = active ? s.previews[active.id] : undefined
  const open = s.ui.dockOpen
  return (
    <footer className={`dock${open ? ' open' : ''}`}>
      <div className="line" onClick={() => s.setUi({ dockOpen: !open })}>
        <ChevronUp size={14} style={{ transform: open ? 'rotate(180deg)' : undefined }} />
        {active ? (
          <>
            <span>Running: {String((active.recipe as { model_id?: string }).model_id ?? active.kind)} {active.progress_text}</span>
            <span className="bar"><i style={{ width: `${Math.round(active.progress * 100)}%` }} /></span>
            <span>{Math.round(active.progress * 100)}%</span>
          </>
        ) : <span>{s.project?.open ? (s.queue?.paused ? 'Queue paused' : 'Idle') : 'No project'}</span>}
        <span>· Queued {queued.length} · Recent {recent.length}</span>
        <span className="spacer" />
        {s.project?.open && (
          <button className="quiet" onClick={(e) => { e.stopPropagation(); void s.pauseQueue(!s.queue?.paused) }} title={s.queue?.paused ? 'resume queue' : 'pause queue'}>
            {s.queue?.paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
        )}
      </div>
      {open && (
        <div className="cols">
          <div className="col">
            <h4>Active</h4>
            {active ? <>{preview && <img className="preview" src={preview} alt="preview" />}<JobRow j={active} /></> : <span className="meta">nothing running</span>}
          </div>
          <div className="col"><h4>Queued</h4>{queued.map((j) => <JobRow key={j.id} j={j} />)}</div>
          <div className="col"><h4>Recent</h4>{recent.slice(0, 12).map((j) => <JobRow key={j.id} j={j} />)}</div>
        </div>
      )}
    </footer>
  )
}
