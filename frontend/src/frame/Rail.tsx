import { PanelLeft, PanelRight, Settings } from 'lucide-react'
import { useSession } from '../store/session'
import { useSuiteRail } from './suiteRegistry'

export function Rail() {
  const s = useSession()
  const { tabs, active, setActive } = useSuiteRail()
  return (
    <nav className="rail" aria-label="rail">
      {tabs.map((t) => (
        <button key={t.id} className={active === t.id && s.ui.panelOpen ? 'active' : ''} title={`${t.label}${t.key ? ` (${t.key})` : ''}`}
          onClick={() => { if (active === t.id) s.setUi({ panelOpen: !s.ui.panelOpen }); else { setActive(t.id); s.setUi({ panelOpen: true }) } }}>
          {t.icon}
        </button>
      ))}
      <div className="spacer" />
      <button title="Toggle panel (Ctrl+B)" onClick={() => s.setUi({ panelOpen: !s.ui.panelOpen })}><PanelLeft size={18} /></button>
      <button title="Toggle inspector (Ctrl+I)" onClick={() => s.setUi({ inspectorOpen: !s.ui.inspectorOpen })}><PanelRight size={18} /></button>
      <button title="Settings (Ctrl+,)" onClick={() => s.openSettings(true)}><Settings size={18} /></button>
    </nav>
  )
}
