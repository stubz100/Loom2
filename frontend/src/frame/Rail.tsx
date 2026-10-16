import { useSession } from '../store/session'
import { CommandButton } from './CommandButton'
import { useRailEntries } from './suiteRegistry'

export function Rail() {
  const s = useSession()
  const { entries, isActive, open } = useRailEntries()
  return (
    <nav className="rail" aria-label="rail">
      {entries.map((t) => (
        <button key={`${t.suite}.${t.id}`} className={isActive(t) && s.ui.panelOpen ? 'active' : ''} title={`${t.label}${t.key ? ` (${t.key})` : ''}`} aria-label={t.label}
          onClick={() => { if (isActive(t)) s.setUi({ panelOpen: !s.ui.panelOpen }); else { open(t); s.setUi({ panelOpen: true }) } }}>
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
