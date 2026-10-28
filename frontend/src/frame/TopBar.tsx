import { Boxes, ChevronDown, FolderOpen, Menu } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { requestAppExit } from '../shell/tauri'
import { selectRunningJob, useSession } from '../store/session'
import { runCommand } from './commands'
import { preloadSuite } from './lazySuite'
import { THEMES } from './theme'
import { TOP_TABS, topTabOf, type TopTab } from './railTabs'
import { openTopTab, preloadOf } from './topTabs'
import { onlyAssets, useDropTarget, type DragPayload, type DropVerdict } from './drag'
import { editOpenDrop, layerDrop, startDrop } from './dropRules'
import { editPresence } from './editPresence'
import { dropRefs, refDropFor } from '../suites/generate/generateStore'
import { navigate, UI2 } from './router'

function useOutside(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose() }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [onClose])
  return ref
}

/** The verb a drop on the Image tab does, by the mode last open under it (D95, UX0 #3): in Make the tiles become references; in Edit they become
 *  layers of the open document, or the first image opens when none is open. */
type ImageDrop = 'refs' | 'layers' | 'open'
function imageDrop(): ImageDrop {
  const u = useSession.getState().ui
  if ((u.imageLast ?? 'generate') === 'generate') return 'refs'
  return editPresence.hasDoc ? 'layers' : 'open'
}

/** What a quick drop on a suite tab does (D71): Image adds references or layers (above), Animate starts. */
function tabDrop(id: string, p: DragPayload): DropVerdict | null {
  if (id === 'image') { const m = imageDrop(); return m === 'refs' ? refDropFor(p).verdict : m === 'layers' ? layerDrop(p).verdict : editOpenDrop(p).verdict }
  if (id === 'animate') return startDrop(p, { tab: true }).verdict
  return null
}

const SPRING_MS = 600

/** A suite tab; Edit, Generate and Animate take dropped tiles (frame/drag.ts). D71: a drag resting on one for 600 ms switches to that suite
 *  and carries on, so a tile reaches a particular slot there; a quick drop does the tab's own verb. */
function SuiteTab({ t, active, onOpen }: { t: TopTab; active: boolean; onOpen: () => void }) {
  const { ref, over } = useDropTarget((p) => onlyAssets(p) && !!tabDrop(t.id, p)?.ok, (p) => {
    if (t.id === 'image') {
      const m = imageDrop()
      if (m === 'refs') dropRefs(p)
      else if (m === 'layers') { const ids = layerDrop(p).take; void import('../suites/edit/editorStore').then((e) => ids.forEach((id) => void e.useEditor.getState().addLayerFromAsset(id))) }
      else { const id = editOpenDrop(p).open; if (id) void import('../suites/edit/editorStore').then((e) => e.useEditor.getState().openFromAsset(id)) }
    }
    else if (t.id === 'animate') {
      const r = startDrop(p, { tab: true })
      void import('../suites/animate/animateStore').then((m) => {
        const a = m.useAnimate.getState()
        if (r.play) void a.loadAsset(r.play).then((asset) => {             // a clip plays (as the tile menu's Animate does)
          const clip = (asset?.params as { clip_id?: string } | undefined)?.clip_id
          navigate({ suite: 'animate' }); if (clip) void a.loadClips().then(() => a.select(clip))
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
    <button ref={ref} className={`tab${active ? ' active' : ''}${over ? ' drop-over' : ''}${over && !active ? ' spring' : ''}`} onClick={onOpen} onPointerEnter={() => preloadSuite(preloadOf(t))} title={`${t.label} (Ctrl+${t.key})${t.id === 'image' ? ' · drop tiles here: references in Make, layers in Edit' : t.id === 'animate' ? ' · drop a tile here as the start frame (two tiles: start and end)' : ''}`}>
      {t.label}<kbd>Ctrl+{t.key}</kbd>
    </button>
  )
}

/** The top bar: ☰, Project ▾, the tabs (the suites', or U1 (D157) the new shell's layers through `tabs`), the status chips. */
export function TopBar({ tabs }: { tabs?: ReactNode } = {}) {
  const s = useSession()
  const [menu, setMenu] = useState<'project' | 'app' | null>(null)
  const top = topTabOf(s.ui.suite)?.id
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
        {tabs ?? TOP_TABS.map((t) => <SuiteTab key={t.id} t={t} active={top === t.id} onOpen={() => openTopTab(t)} />)}
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
          <button onClick={() => { setMenu(null); runCommand('global.focus') }}>{s.ui.focusMode ? 'Leave focus mode' : 'Focus mode'} <kbd>Tab</kbd></button>
          <button onClick={() => { setMenu(null); runCommand('global.dock') }}>{s.ui.dockOpen ? 'Hide dock' : 'Show dock'} <kbd>`</kbd></button>
          <button onClick={() => { setMenu(null); s.setUi({ theme: s.ui.theme === 'light' ? 'dark' : 'light' }) }}>Theme: {THEMES.find(([t]) => t === s.ui.theme)?.[1] ?? 'Dark'}</button>
          <button onClick={() => { setMenu(null); s.setUi({ density: s.ui.density === 'compact' ? 'comfortable' : 'compact' }) }}>Density: {s.ui.density}</button>
          <div className="sep" />
          <button onClick={() => { setMenu(null); runCommand('global.ui2') }}>{UI2 ? 'Back to the current UI' : 'Try the new UI'}</button>{/* U1 (D157, 07 §1) */}
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
