import { ChevronDown, Menu } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Suite } from '../api/types'
import { requestAppExit } from '../shell/tauri'
import { selectRunningJob, useSession } from '../store/session'
import { runCommand } from './commands'

export const SUITES: { id: Suite; label: string; key: string }[] = [
  { id: 'catalogue', label: 'Catalogue', key: '1' }, { id: 'generate', label: 'Generate', key: '2' }, { id: 'edit', label: 'Edit', key: '3' },
  { id: 'animate', label: 'Animate', key: '4' }, { id: 'models', label: 'Models', key: '5' },
]

function useOutside(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose() }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [onClose])
  return ref
}

export function TopBar() {
  const s = useSession()
  const [menu, setMenu] = useState<'project' | 'app' | null>(null)
  const ref = useOutside(() => setMenu(null))
  const running = useSession(selectRunningJob)
  const engine = s.engine
  const engineDot = !engine?.running ? 'down' : running ? 'busy' : 'ok'
  const engineText = !engine ? '…' : !engine.running ? (engine.last_error ? 'down' : 'off') : running ? `busy ${Math.round((running.progress ?? 0) * 100)}%` : `idle${engine.vram_free_gb !== undefined ? ` · ${engine.vram_free_gb} GB free` : ''}`
  const counts = s.queue?.counts ?? {}
  const jobsText = `${counts.running ?? 0} running · ${counts.queued ?? 0} queued`
  const missing = s.models.filter((m) => m.health === 'missing' && !m.retired).length
  const disk = s.project?.open ? `disk ${s.project.free_space_gb} GB free` : 'no project'
  return (
    <header className="top" ref={ref}>
      <nav className="tabs" aria-label="suites">
        {SUITES.map((t) => (
          <button key={t.id} className={`tab${s.ui.suite === t.id ? ' active' : ''}`} onClick={() => s.setSuite(t.id)} title={`${t.label} (Ctrl+${t.key})${t.id === 'edit' ? ' · drop a Catalogue tile here to open it' : t.id === 'generate' ? ' · drop tiles here as references' : t.id === 'animate' ? ' · drop a tile here as the start frame (two tiles: start and end)' : ''}`}
            onDragOver={(e) => { if (e.dataTransfer.types.includes('text/loom2-assets') && (t.id === 'edit' || t.id === 'generate' || t.id === 'animate')) { e.preventDefault(); e.dataTransfer.dropEffect = 'link' } }}
            onDrop={(e) => { const ids = (e.dataTransfer.getData('text/loom2-assets') || '').split(',').filter(Boolean); if (!ids.length) return; e.preventDefault()
              if (t.id === 'edit') void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(ids[0]))
              else if (t.id === 'generate') void import('../suites/generate/generateStore').then((m) => ids.forEach((id) => m.useGenerate.getState().addRef(id)))
              else if (t.id === 'animate') void import('../suites/animate/animateStore').then((m) => { const a = m.useAnimate.getState(); a.setStart(ids[0], true); if (ids[1]) a.setEnd(ids[1]) }) }}>
            {t.label}<kbd>⌃{t.key}</kbd>
          </button>
        ))}
      </nav>
      <div className="spacer" />
      <button className="quiet" onClick={() => setMenu(menu === 'project' ? null : 'project')} title="project">
        {s.project?.open ? s.project.name : 'No project'} <ChevronDown size={14} style={{ verticalAlign: '-2px' }} />
      </button>
      {menu === 'project' && (
        <div className="menu" style={{ right: 330 }}>
          <button onClick={() => { setMenu(null); s.setProjectDialog('new') }}>New project…</button>
          <button onClick={() => { setMenu(null); s.setProjectDialog('open') }}>Open project…</button>
          {s.project?.open && <button onClick={() => { setMenu(null); void s.closeProject() }}>Close {s.project.name}</button>}
          {s.recents.length > 0 && <div className="sep" />}
          {s.recents.length > 0 && <div className="label">Recent</div>}
          {s.recents.map((r) => <button key={r} onClick={() => { setMenu(null); void s.openProject(r) }} title={r}>{r.split(/[\\/]/).pop()}</button>)}
        </div>
      )}
      <span className="chip" onClick={() => s.setSuite('models')} title={engine?.version?.comfyui_version ? `ComfyUI ${engine.version.comfyui_version}` : 'engine'}>
        <i className={`dot ${engineDot}`} /> engine {engineText}
      </span>
      <span className="chip" onClick={() => s.setUi({ dockOpen: !s.ui.dockOpen })}><i className={`dot ${running ? 'busy' : ''}`} /> {jobsText}</span>
      <span className="chip" title="project drive"><i className={`dot ${s.project?.open && (s.project.free_space_gb ?? 99) < 20 ? 'warn' : ''}`} /> {disk}</span>
      <span className="chip" onClick={() => s.setSuite('models')}><i className={`dot ${missing ? 'warn' : 'ok'}`} /> {missing ? `${missing} weights missing` : 'weights ok'}</span>
      <button className="quiet" onClick={() => setMenu(menu === 'app' ? null : 'app')} title="menu" aria-label="app menu"><Menu size={16} /></button>
      {menu === 'app' && (
        <div className="menu" style={{ right: 8 }}>
          <button onClick={() => { setMenu(null); s.openSettings(true) }}>Settings… <kbd>⌃,</kbd></button>
          <button onClick={() => { setMenu(null); s.setHelp(true) }}>Commands and keys <kbd>?</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.palette') }}>Command palette <kbd>⌃K</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.focus') }}>{s.ui.focusMode ? 'Leave focus mode' : 'Focus mode'} <kbd>Tab</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.dock') }}>{s.ui.dockOpen ? 'Hide dock' : 'Show dock'} <kbd>`</kbd></button>
          <button onClick={() => { setMenu(null); s.setUi({ density: s.ui.density === 'compact' ? 'comfortable' : 'compact' }) }}>Density: {s.ui.density}</button>
          <div className="sep" />
          <button onClick={() => { setMenu(null); void s.refreshAll() }}>Refresh state</button>
          <button onClick={() => { setMenu(null); window.open('/spikes.html', '_blank') }}>M0 spike harness</button>
          <div className="sep" />
          <button onClick={() => { setMenu(null); void requestAppExit() }}>Quit (graceful)</button>
          <div className="label">loom2 {s.health?.version ?? ''} · {s.health?.variant ?? ''} · ws {s.wsStatus}</div>
        </div>
      )}
    </header>
  )
}
