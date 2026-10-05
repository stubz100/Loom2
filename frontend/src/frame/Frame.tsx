import { useEffect } from 'react'
import { useSession } from '../store/session'
import { Banner } from './Banner'
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
      {settingsOpen && <SettingsModal />}
      {projectDialog && <ProjectDialog mode={projectDialog} />}
      {helpOpen && <HelpOverlay />}
    </div>
  )
}
