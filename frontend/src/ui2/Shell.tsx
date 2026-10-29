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
import { Help } from '../frame/Help'
import { HelpOverlay } from '../frame/HelpOverlay'
import { ModelsSheet } from '../frame/ModelsSheet'
import { ProjectDialog } from '../frame/ProjectDialog'
import { SettingsModal } from '../frame/SettingsModal'
import { applyTheme } from '../frame/theme'
import { Toasts } from '../frame/Toasts'
import { TopBar } from '../frame/TopBar'
import { useKeyboardMap } from '../frame/useKeyboardMap'
import { followNavigation, LAYERS, useLayer } from './layers'
import { ShotsLayer } from './shots/ShotsLayer'
import { WorldLayer } from './world/WorldLayer'
import { KeyHosts } from '../frame/keyHosts'
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

/** What a layer says until its wave builds it: its name and a few words (rule 11: the why behind the ?). */
const PENDING: Record<string, [string, string]> = {
  world: ['World', 'Characters, props and places, made and readied for Clay — wave U3 (03-ui-world.md).'],
  shots: ['Shots', 'The Flow, and each shot refined through Clay, Performance and Final — waves U4–U6 (04-ui-shots.md).'],
  episode: ['Episode', 'The cut of the shots’ finals — wave U7 (05-ui-episode-and-bin.md).'],
  bin: ['Bin', 'Every asset in its home — wave U8 (05-ui-episode-and-bin.md).'],
}

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
  useEffect(() => { document.body.classList.toggle('density-compact', ui.density === 'compact') }, [ui.density])
  useEffect(() => { applyTheme(ui.theme) }, [ui.theme])
  const [name, why] = PENDING[layer]
  return (
    <div className="frame ui2" data-layer={layer}>
      <TopBar tabs={<LayerTabs />} />
      <Banner />
      <main className={`ui2-layer${layer === 'world' || layer === 'shots' ? ' filled' : ''}`} aria-label={name}>
        {layer === 'world' ? <WorldLayer /> : layer === 'shots' ? <ShotsLayer /> : <div className="ui2-pending"><b>{name}</b><span>not built yet <Help text={why} /></span></div>}
      </main>
      <Dock />
      <Toasts />
      <ContextMenuHost />
      <CommandPalette />
      {settingsOpen && <SettingsModal />}
      {projectDialog && <ProjectDialog mode={projectDialog} />}
      {helpOpen && <HelpOverlay />}
      <ModelsSheet />
      <AskDialog />
      <KeyHosts />
    </div>
  )
}
