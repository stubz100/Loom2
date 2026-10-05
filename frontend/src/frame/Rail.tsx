import { Boxes, Cpu, Filter, FolderTree, Library, PanelLeft, PanelRight, Settings, SlidersHorizontal, Wand2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { useSession } from '../store/session'
import { useSuiteRail } from './suiteRegistry'

export interface RailTab { id: string; label: string; key?: string; icon: ReactNode }

export const DEFAULT_RAIL: Record<string, RailTab[]> = {
  catalogue: [{ id: 'library', label: 'Library', icon: <Library size={18} /> }, { id: 'filters', label: 'Filters', icon: <Filter size={18} /> }, { id: 'collections', label: 'Collections', icon: <FolderTree size={18} /> }],
  generate: [{ id: 'prompt', label: 'Prompt', icon: <Wand2 size={18} /> }, { id: 'params', label: 'Parameters', icon: <SlidersHorizontal size={18} /> }],
  edit: [{ id: 'tools', label: 'Tools', icon: <Wand2 size={18} /> }],
  animate: [{ id: 'inputs', label: 'Inputs', icon: <Boxes size={18} /> }],
  models: [{ id: 'roster', label: 'Roster', icon: <Boxes size={18} /> }, { id: 'engine', label: 'Engine', icon: <Cpu size={18} /> }],
}

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
