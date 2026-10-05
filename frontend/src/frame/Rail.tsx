import { useSession } from '../store/session'
import { CommandButton } from './CommandButton'
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
      <CommandButton id="global.focus" active={s.ui.focusMode} size={18} />
      <CommandButton id="global.panel" active={s.ui.panelOpen} size={18} />
      <CommandButton id="global.inspector" active={s.ui.inspectorOpen} size={18} />
      <CommandButton id="global.dock" active={s.ui.dockOpen} size={18} />
      <CommandButton id="global.settings" size={18} />
    </nav>
  )
}
