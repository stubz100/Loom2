import { Boxes, ChevronDown, FolderOpen, Menu } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { requestAppExit } from '../shell/tauri'
import { selectRunningJob, useSession } from '../store/session'
import { runCommand } from './commands'
import { THEMES } from './theme'

function useOutside(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose() }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [onClose])
  return ref
}

/** The top bar: ☰, Project ▾, the tabs (U1, D157: the shell's layers, through `tabs`), the status chips. */
export function TopBar({ tabs }: { tabs: ReactNode }) {
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
      <button className="quiet app-menu" onClick={() => setMenu(menu === 'app' ? null : 'app')} title="menu: Models & engine, settings, keys, theme…" aria-label="app menu"><Menu size={16} /></button>
      <nav className="tabs" aria-label="suites">
        <button className={`tab project-tab${menu === 'project' ? ' active' : ''}`} onClick={() => setMenu(menu === 'project' ? null : 'project')} aria-label="project menu"
          title={s.project?.open ? `Project: ${s.project.name} — new, open, close, recent` : 'Project: new, open, recent'}>
          <FolderOpen size={14} style={{ verticalAlign: '-2px' }} /> Project <span className="project-name">{s.project?.open ? s.project.name : 'none open'}</span> <ChevronDown size={14} style={{ verticalAlign: '-2px' }} />
        </button>
        <span className="tabs-sep" aria-hidden="true" />
        {tabs}
      </nav>
      <div className="spacer" />
      {menu === 'project' && (
        <div className="menu project-menu" style={{ left: 44 }}>
          <button onClick={() => { setMenu(null); s.setProjectDialog('new') }}>New project…</button>
          <button onClick={() => { setMenu(null); s.setProjectDialog('open') }}>Open project…</button>
          {s.project?.open && <button onClick={() => { setMenu(null); void s.closeProject() }}>Close {s.project.name}</button>}
          {s.recents.length > 0 && <div className="sep" />}
          {s.recents.length > 0 && <div className="label">Recent</div>}
          {s.recents.map((r) => <button key={r} onClick={() => { setMenu(null); void s.openProject(r) }} title={r}>{r.split(/[\\/]/).pop()}</button>)}
        </div>
      )}
      <span className="chip" onClick={() => s.openModels({ tab: 'engine' })} title={`${engine?.version?.comfyui_version ? `ComfyUI ${engine.version.comfyui_version}` : 'engine'} — open Models & engine`}>
        <i className={`dot ${engineDot}`} /> engine {engineText}
      </span>
      <span className="chip" onClick={() => s.setUi({ dockOpen: !s.ui.dockOpen })}><i className={`dot ${running ? 'busy' : ''}`} /> {jobsText}</span>
      <span className="chip" title="project drive"><i className={`dot ${s.project?.open && (s.project.free_space_gb ?? 99) < 20 ? 'warn' : ''}`} /> {disk}</span>
      <span className="chip" onClick={() => s.openModels({ missing: missing > 0 })} title="open Models & engine"><i className={`dot ${missing ? 'warn' : 'ok'}`} /> {missing ? `${missing} weights missing` : 'weights ok'}</span>
      {menu === 'app' && (
        <div className="menu app-menu-list" style={{ left: 8 }}>
          <button onClick={() => { setMenu(null); s.openModels() }}><Boxes size={14} style={{ verticalAlign: '-2px' }} /> Models & engine…</button>
          {s.project?.open && <button onClick={() => { setMenu(null); runCommand('global.start.newDocument') }}>New document…</button>}{/* D95 (UX0 #3): open a blank document in Image · Edit */}
          <div className="sep" />
          <button onClick={() => { setMenu(null); s.openSettings(true) }}>Settings… <kbd>Ctrl+,</kbd></button>
          <button onClick={() => { setMenu(null); s.setHelp(true) }}>Commands and keys <kbd>?</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.palette') }}>Command palette <kbd>Ctrl+K</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.dock') }}>{s.ui.dockOpen ? 'Hide dock' : 'Show dock'} <kbd>`</kbd></button>
          <button onClick={() => { setMenu(null); s.setUi({ theme: s.ui.theme === 'light' ? 'dark' : 'light' }) }}>Theme: {THEMES.find(([t]) => t === s.ui.theme)?.[1] ?? 'Dark'}</button>
          <button onClick={() => { setMenu(null); s.setUi({ density: s.ui.density === 'compact' ? 'comfortable' : 'compact' }) }}>Density: {s.ui.density}</button>
          <div className="sep" />
          <button onClick={() => { setMenu(null); void s.refreshAll() }}>Refresh state</button>
          {import.meta.env.DEV && <button onClick={() => { setMenu(null); window.open('/spikes.html', '_blank') }}>M0 spike harness (dev)</button>}
          <div className="sep" />
          <button onClick={() => { setMenu(null); void requestAppExit() }}>Quit (graceful)</button>
          <div className="label">loom2 {s.health?.version ?? ''} · {s.health?.variant ?? ''} · ws {s.wsStatus}</div>
        </div>
      )}
    </header>
  )
}
