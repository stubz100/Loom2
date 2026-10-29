import { ChevronUp, ClipboardCopy, LocateFixed, Pause, Play, X } from 'lucide-react'
import { lazy, Suspense, useMemo } from 'react'
import type { Job } from '../api/types'
import { canGoToOrigin, goToOrigin, originLabel } from '../store/origin'
import { useSession } from '../store/session'
import { sep, type MenuItem } from './commands'
import { showMenu } from './ContextMenu'
import { useLayer } from '../ui2/layers'

const BinDrawer = lazy(() => import('../ui2/bin/BinDrawer'))               // U8 (D157, 05 §2.3): the Bin's drawer, its homes' tree

function JobRow({ j }: { j: Job }) {
  const cancelJob = useSession((s) => s.cancelJob)
  const deleteJob = useSession((s) => s.deleteJob)
  const releaseJob = useSession((s) => s.releaseJob)
  const label = `${j.kind} · ${String((j.recipe as { model_id?: string }).model_id ?? '')} · seed ${j.seed}`
  const live = j.status === 'running' || j.status === 'queued'
  const hasOrigin = canGoToOrigin(j)                          // D66: switch to the suite the job came from and show its batch, clip, document or group
  const originTitle = hasOrigin ? `Go to origin: ${originLabel(j.origin)}` : `Go to origin: ${j.origin ? 'submitted through the API' : originLabel(null)}`
  const menu = (): MenuItem[] => [
    { label: 'Go to origin', icon: LocateFixed, disabled: !hasOrigin, run: () => goToOrigin(j) },
    sep,
    { label: 'Cancel job', icon: X, disabled: !live, run: () => void cancelJob(j.id) },
    { label: 'Run now', icon: Play, disabled: j.status !== 'staged', run: () => void releaseJob(j.id) },
    { label: 'Remove from the list', icon: X, disabled: live, run: () => void deleteJob(j.id) },
    sep,
    { label: 'Copy job id', icon: ClipboardCopy, run: () => void navigator.clipboard?.writeText(j.id) },
    { label: 'Copy recipe JSON', icon: ClipboardCopy, run: () => void navigator.clipboard?.writeText(JSON.stringify(j.recipe, null, 2)) },
  ]
  return (
    <div className={`job ${j.status}`} tabIndex={0} onContextMenu={(e) => showMenu(e, menu())}>
      <span>{label}</span>
      <span className="meta">{j.status === 'running' ? j.progress_text : j.status}{j.wall_s ? ` · ${j.wall_s}s` : ''}</span>
      {(j.status === 'running' || j.status === 'queued') && <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>}
      {j.error && <div className="err">{j.error}</div>}
      <span className="meta">{j.id}</span>
      <span>
        <button className="quiet" title={originTitle} aria-label="Go to origin" disabled={!hasOrigin} onClick={() => goToOrigin(j)}><LocateFixed size={14} /></button>
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
  const layer = useLayer((s) => s.layer)
  const binHere = layer !== 'bin'                                       // U8: offered in World, Shots and Episode (the Bin is its own layer)
  const tab = useSession((s) => (binHere ? s.ui.dockTab ?? 'queue' : 'queue'))
  const pick = (t: 'queue' | 'bin') => (e: React.MouseEvent) => { e.stopPropagation(); setUi({ dockTab: t, dockOpen: open && tab === t ? false : true }) }
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
        {binHere && <span className="segmented dock-tabs" role="group" aria-label="Dock">
          <button className={tab === 'queue' ? 'active' : ''} onClick={pick('queue')} title="The render queue">Queue</button>
          <button className={tab === 'bin' ? 'active' : ''} onClick={pick('bin')} title="The Bin in a drawer — drag a tile where it is used">Bin</button>
        </span>}
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
      {open && tab === 'bin' && <Suspense fallback={null}><BinDrawer /></Suspense>}
      {open && tab === 'queue' && (
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
