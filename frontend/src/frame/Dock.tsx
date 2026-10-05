import { ChevronUp, Pause, Play, X } from 'lucide-react'
import { useMemo } from 'react'
import type { Job } from '../api/types'
import { useSession } from '../store/session'

function JobRow({ j }: { j: Job }) {
  const cancelJob = useSession((s) => s.cancelJob)
  const deleteJob = useSession((s) => s.deleteJob)
  const label = `${j.kind} · ${String((j.recipe as { model_id?: string }).model_id ?? '')} · seed ${j.seed}`
  return (
    <div className={`job ${j.status}`}>
      <span>{label}</span>
      <span className="meta">{j.status === 'running' ? j.progress_text : j.status}{j.wall_s ? ` · ${j.wall_s}s` : ''}</span>
      {(j.status === 'running' || j.status === 'queued') && <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>}
      {j.error && <div className="err">{j.error}</div>}
      <span className="meta">{j.id}</span>
      <span>
        {(j.status === 'running' || j.status === 'queued') && <button className="quiet" title="cancel" onClick={() => void cancelJob(j.id)}><X size={14} /></button>}
        {['done', 'failed', 'cancelled'].includes(j.status) && <button className="quiet" title="remove" onClick={() => void deleteJob(j.id)}><X size={14} /></button>}
      </span>
    </div>
  )
}

export function Dock() {
  const jobs = useSession((s) => s.jobs)
  const queue = useSession((s) => s.queue)
  const project = useSession((s) => s.project)
  const previews = useSession((s) => s.previews)
  const open = useSession((s) => s.ui.dockOpen)
  const setUi = useSession((s) => s.setUi)
  const pauseQueue = useSession((s) => s.pauseQueue)
  // derived in a memo, never in a selector: a selector returning a fresh object re-renders forever
  const { running, queued, recent } = useMemo(() => {
    const all = Object.values(jobs).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    return { running: all.filter((j) => j.status === 'running'), queued: all.filter((j) => j.status === 'queued'), recent: all.filter((j) => ['done', 'failed', 'cancelled'].includes(j.status)) }
  }, [jobs])
  const active = running[0]
  const preview = active ? previews[active.id] : undefined
  return (
    <footer className={`dock${open ? ' open' : ''}`}>
      <div className="line" onClick={() => setUi({ dockOpen: !open })}>
        <ChevronUp size={14} style={{ transform: open ? 'rotate(180deg)' : undefined }} />
        {active ? (
          <>
            <span>Running: {String((active.recipe as { model_id?: string }).model_id ?? active.kind)} {active.progress_text}</span>
            <span className="bar"><i style={{ width: `${Math.round(active.progress * 100)}%` }} /></span>
            <span>{Math.round(active.progress * 100)}%</span>
          </>
        ) : <span>{project?.open ? (queue?.paused ? 'Queue paused' : 'Idle') : 'No project'}</span>}
        <span>· Queued {queued.length} · Recent {recent.length}</span>
        <span className="spacer" />
        {project?.open && (
          <button className="quiet" onClick={(e) => { e.stopPropagation(); void pauseQueue(!queue?.paused) }} title={queue?.paused ? 'resume queue' : 'pause queue'}>
            {queue?.paused ? <Play size={14} /> : <Pause size={14} />}
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
