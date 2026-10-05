import { useEffect } from 'react'
import { useSession } from '../store/session'
import { Banner } from './Banner'
import { CommandPalette } from './CommandPalette'
import { unusedCommands, type Scope } from './commands'
import { ContextMenuHost } from './ContextMenu'
import { Dock } from './Dock'
import { HelpOverlay } from './HelpOverlay'
import { Inspector } from './Inspector'
import { Panel } from './Panel'
import { ProjectDialog } from './ProjectDialog'
import { Rail } from './Rail'
import { SettingsModal } from './SettingsModal'
import { Stage } from './Stage'
import { Strip } from './Strip'
import { Toasts } from './Toasts'
import { TopBar } from './TopBar'
import { useKeyboardMap } from './useKeyboardMap'
import './frame.css'

export function Frame() {
  const init = useSession((s) => s.init)
  const ui = useSession((s) => s.ui)
  const settingsOpen = useSession((s) => s.settingsOpen)
  const projectDialog = useSession((s) => s.projectDialog)
  const helpOpen = useSession((s) => s.helpOpen)
  useKeyboardMap()
  useEffect(() => { void init() }, [init])
  useEffect(() => { document.body.classList.toggle('density-compact', ui.density === 'compact') }, [ui.density])
  // dev audit (07 §3c): commands of the current suite that no menu or toolbar has rendered yet
  useEffect(() => {
    if (!import.meta.env.DEV) return
    const t = setTimeout(() => { const u = unusedCommands(ui.suite as Scope); if (u.length) console.info(`[commands] not yet shown by a menu/toolbar in ${ui.suite}: ${u.map((c) => c.id).join(', ')}`) }, 4000)
    return () => clearTimeout(t)
  }, [ui.suite])
  // dev deep links for the headless verification loop: &ctx=<css selector> opens that element's context menu,
  // &help=1 the commands overlay, &palette=1 the command palette
  useEffect(() => {
    if (!import.meta.env.DEV) return
    const p = new URLSearchParams(location.search)
    const t = setTimeout(() => {
      const sel = p.get('ctx')
      if (sel) {
        const probe = document.createElement('div'); probe.id = 'dev-probe'; probe.style.display = 'none'; document.body.appendChild(probe)
        window.addEventListener('error', (ev) => { probe.textContent += ` error:${ev.message}` })
        const el = document.querySelector(sel) as HTMLElement | null
        probe.textContent = el ? `found ${sel}` : `missing ${sel}`
        if (el) { const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: r.left + Math.min(40, r.width / 2), clientY: r.top + Math.min(30, r.height / 2) })) }
        setTimeout(() => void import('./ContextMenu').then((m) => { const o = m.useMenu.getState().open; probe.textContent += ` open:${!!o} items:${o?.items.length ?? 0} at:${o?.x},${o?.y}` }), 300)
      }
      if (p.get('help')) useSession.getState().setHelp(true)
      if (p.get('menu')) void import('./ContextMenu').then((m) => m.useMenu.getState().show(400, 300, [{ label: 'dev menu probe', run: () => undefined }, { cmd: 'global.help' }]))
      if (p.get('palette')) void import('./CommandPalette').then((m) => m.usePalette.getState().toggle())
    }, 3000)
    return () => clearTimeout(t)
  }, [])
  const style = { '--panel-w': `${ui.panelWidth}px`, '--inspector-w': `${ui.inspectorWidth}px` } as React.CSSProperties
  return (
    <div className={`frame${ui.focusMode ? ' focus' : ''}`} style={style}>
      <TopBar />
      <Banner />
      <Rail />
      <Panel />
      <div className="center">
        <Strip />
        <Stage />
      </div>
      <Inspector />
      <Dock />
      <Toasts />
      <ContextMenuHost />
      <CommandPalette />
      {settingsOpen && <SettingsModal />}
      {projectDialog && <ProjectDialog mode={projectDialog} />}
      {helpOpen && <HelpOverlay />}
    </div>
  )
}
