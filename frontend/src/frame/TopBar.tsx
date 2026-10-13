import { ChevronDown, Menu } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Suite } from '../api/types'
import { requestAppExit } from '../shell/tauri'
import { selectRunningJob, useSession } from '../store/session'
import { runCommand } from './commands'
import { preloadSuite } from './lazySuite'
import { THEMES } from './theme'
import { onlyAssets, useDropTarget, type DragPayload, type DropVerdict } from './drag'
import { editOpenDrop, startDrop } from './dropRules'
import { dropRefs, refDropFor } from '../suites/generate/generateStore'

export const SUITES: { id: Suite; label: string; key: string }[] = [
  { id: 'catalogue', label: 'Catalogue', key: '1' }, { id: 'generate', label: 'Generate', key: '2' }, { id: 'edit', label: 'Edit', key: '3' },
  { id: 'animate', label: 'Animate', key: '4' }, { id: 'stage', label: 'Stage', key: '6' }, { id: 'story', label: 'Story', key: '7' }, { id: 'models', label: 'Models', key: '5' },
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

/** What a quick drop on a suite tab does (D71): Edit opens the first image, Generate adds references (capped), Animate starts. */
function tabDrop(id: string, p: DragPayload): DropVerdict | null {
  if (id === 'edit') return editOpenDrop(p).verdict
  if (id === 'generate') return refDropFor(p).verdict
  if (id === 'animate') return startDrop(p, { tab: true }).verdict
  return null
}

const SPRING_MS = 600

/** A suite tab; Edit, Generate and Animate take dropped tiles (frame/drag.ts). D71: a drag resting on one for 600 ms switches to that suite
 *  and carries on, so a tile reaches a particular slot there; a quick drop does the tab's own verb. */
function SuiteTab({ t, active, onOpen }: { t: (typeof SUITES)[number]; active: boolean; onOpen: () => void }) {
  const { ref, over } = useDropTarget((p) => onlyAssets(p) && !!tabDrop(t.id, p)?.ok, (p) => {
    if (t.id === 'edit') { const id = editOpenDrop(p).open; if (id) void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(id)) }
    else if (t.id === 'generate') dropRefs(p)
    else if (t.id === 'animate') {
      const r = startDrop(p, { tab: true })
      void import('../suites/animate/animateStore').then((m) => {
        const a = m.useAnimate.getState()
        if (r.play) void a.loadAsset(r.play).then((asset) => {             // a clip plays (as the tile menu's Animate does)
          const clip = (asset?.params as { clip_id?: string } | undefined)?.clip_id
          useSession.getState().setSuite('animate'); if (clip) void a.loadClips().then(() => a.select(clip))
        })
        else if (r.start) { a.setStart(r.start, true); if (r.end) a.setEnd(r.end) }
      })
    }
  }, (p) => { const v = tabDrop(t.id, p); return v && (active || !v.ok ? v : { ...v, label: `${v.label} — or hold to open ${t.label}` }) })
  const open = useRef(onOpen)
  useLayoutEffect(() => { open.current = onOpen })                       // TopBar re-renders on every session change: keep the timer running
  useEffect(() => {
    if (!over || active) return
    const timer = window.setTimeout(() => open.current(), SPRING_MS)
    return () => window.clearTimeout(timer)
  }, [over, active])
  return (
    <button ref={ref} className={`tab${active ? ' active' : ''}${over ? ' drop-over' : ''}${over && !active ? ' spring' : ''}`} onClick={onOpen} onPointerEnter={() => preloadSuite(t.id)} title={`${t.label} (Ctrl+${t.key})${t.id === 'edit' ? ' · drop a Catalogue tile here to open it' : t.id === 'generate' ? ' · drop tiles here as references' : t.id === 'animate' ? ' · drop a tile here as the start frame (two tiles: start and end)' : ''}`}>
      {t.label}<kbd>Ctrl+{t.key}</kbd>
    </button>
  )
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
        {SUITES.map((t) => <SuiteTab key={t.id} t={t} active={s.ui.suite === t.id} onOpen={() => s.setSuite(t.id)} />)}
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
          <button onClick={() => { setMenu(null); s.openSettings(true) }}>Settings… <kbd>Ctrl+,</kbd></button>
          <button onClick={() => { setMenu(null); s.setHelp(true) }}>Commands and keys <kbd>?</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.palette') }}>Command palette <kbd>Ctrl+K</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.focus') }}>{s.ui.focusMode ? 'Leave focus mode' : 'Focus mode'} <kbd>Tab</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.dock') }}>{s.ui.dockOpen ? 'Hide dock' : 'Show dock'} <kbd>`</kbd></button>
          <button onClick={() => { setMenu(null); s.setUi({ theme: s.ui.theme === 'light' ? 'dark' : 'light' }) }}>Theme: {THEMES.find(([t]) => t === s.ui.theme)?.[1] ?? 'Dark'}</button>
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
