// U1 (D157, proto01_UI2 02 §5, 07 §1): the new shell — a second entry of the same frontend (`?ui=2`) on the same records. In U1 it is the
// frame only: the top bar with the four layer tabs, the layer's place, the dock and the frame's services (toasts, menus, the palette, the
// dialogs, the keyboard map). The layers fill in from U3 (World), U4–U6 (Shots), U7 (Episode) and U8 (the Bin).
import { useEffect } from 'react'
import { useSession } from '../store/session'
import { AskDialog } from '../frame/AskDialog'
import { Banner } from '../frame/Banner'
import { CommandPalette } from '../frame/CommandPalette'
import { runCommand } from '../frame/commands'
import { ContextMenuHost } from '../frame/ContextMenu'
import { Dock } from '../frame/Dock'
import { ErrorBoundary } from '../frame/ErrorBoundary'
import { HelpOverlay } from '../frame/HelpOverlay'
import { ModelsSheet } from '../frame/ModelsSheet'
import { ProjectDialog } from '../frame/ProjectDialog'
import { SettingsModal } from '../frame/SettingsModal'
import { applyTheme } from '../frame/theme'
import { Toasts } from '../frame/Toasts'
import { TopBar } from '../frame/TopBar'
import { useKeyboardMap } from '../frame/useKeyboardMap'
import { followNavigation, LAYERS, useLayer } from './layers'
import { EpisodeLayer } from './episode/EpisodeLayer'
import { BinLayer } from './bin/BinLayer'
import { ShotsLayer } from './shots/ShotsLayer'
import { WorldLayer } from './world/WorldLayer'
import { KeyHosts } from '../frame/keyHosts'
import { AngleSheet } from '../suites/generate/AngleTab'
import '../frame/frame.css'
import './shell.css'

/** The layer tabs — each the global command its key runs (Ctrl+1–4), so the tab, the key, the palette and the help list agree. */
function LayerTabs() {
  const layer = useLayer((s) => s.layer)
  const ids = ['global.suite.story', 'global.suite.image', 'global.suite.animate', 'global.suite.catalogue']
  return <>{LAYERS.map((l, i) => (
    <button key={l.id} className={`tab${layer === l.id ? ' active' : ''}`} onClick={() => runCommand(ids[i])} title={`${l.label} (Ctrl+${l.key})`} data-layer={l.id}>
      {l.label}<kbd>Ctrl+{l.key}</kbd>
    </button>
  ))}</>
}

/** Each layer's name (the main region's label). */
const NAME: Record<string, string> = { world: 'World', shots: 'Shots', episode: 'Episode', bin: 'Bin' }

export function Shell() {
  const init = useSession((s) => s.init)
  const ui = useSession((s) => s.ui)
  const settingsOpen = useSession((s) => s.settingsOpen)
  const projectDialog = useSession((s) => s.projectDialog)
  const helpOpen = useSession((s) => s.helpOpen)
  const layer = useLayer((s) => s.layer)
  useKeyboardMap()
  useEffect(() => { void init() }, [init])
  useEffect(() => followNavigation(), [])
  useEffect(() => { void import('./deepLinks').then((m) => m.followDeepLink()) }, [])   // B2a: ?suite=edit&tool=…&ai=…&asset=… opens World's Edit
  useEffect(() => { document.body.classList.toggle('density-compact', ui.density === 'compact') }, [ui.density])
  useEffect(() => { applyTheme(ui.theme) }, [ui.theme])
  const name = NAME[layer]
  return (
    <div className="frame ui2" data-layer={layer}>
      <TopBar tabs={<LayerTabs />} />
      <Banner />
      <main className="ui2-layer filled" aria-label={name}>
        <ErrorBoundary key={layer} label={name}>{layer === 'world' ? <WorldLayer /> : layer === 'shots' ? <ShotsLayer /> : layer === 'episode' ? <EpisodeLayer /> : <BinLayer />}</ErrorBoundary>{/* B2a: a layer that fails says so; the shell stays */}
      </main>
      <Dock />
      <Toasts />
      <ContextMenuHost />
      <CommandPalette />
      {settingsOpen && <SettingsModal />}
      {projectDialog && <ProjectDialog mode={projectDialog} />}
      {helpOpen && <HelpOverlay />}
      <ModelsSheet />
      <AngleSheet />{/* B2a (D82): New angle… from the Bin */}
      <AskDialog />
      <KeyHosts />
    </div>
  )
}
