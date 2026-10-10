// Icon buttons bound to registry commands: label + shortcut in the tooltip, disabled from `when`, and the
// command marked as mouse-reachable for the dev audit (07 §3c).
import { command, isEnabled, markUsed, runCommand, titleFor, type IconType, type MenuItem } from './commands'
import { showMenu } from './ContextMenu'

/** A toolbar button that opens a menu (e.g. "add adjustment ▾"). */
export function MenuButton({ label, icon: Icon, items, text, size = 16 }: { label: string; icon?: IconType; items: () => MenuItem[]; text?: boolean; size?: number }) {
  return (
    <button type="button" className="cmd-btn" title={label} aria-label={label} aria-haspopup="menu"
      onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); showMenu({ clientX: r.left, clientY: r.bottom + 2 }, items()) }}>
      {Icon ? <Icon size={size} /> : null}{(text || !Icon) && <span>{label}</span>}<span style={{ fontSize: 9, marginLeft: 2 }}>▾</span>
    </button>
  )
}

export function CommandButton({ id, active, text, size = 16, className = '', label }: { id: string; active?: boolean; text?: boolean; size?: number; className?: string; label?: string }) {
  const c = command(id)
  if (!c) return null
  markUsed(id)
  const Icon = c.icon
  return (
    <button type="button" className={`cmd-btn${active ? ' active' : ''}${c.danger ? ' danger' : ''} ${className}`} title={titleFor(c)} aria-label={c.label} disabled={!isEnabled(c)} onClick={() => runCommand(id)}>
      {Icon ? <Icon size={size} /> : null}{(text || !Icon) && <span>{label ?? c.label}</span>}
    </button>
  )
}

export function CommandRow({ ids, active, className = '' }: { ids: (string | 'gap')[]; active?: string; className?: string }) {
  return <span className={`cmd-row ${className}`}>{ids.map((id, i) => id === 'gap' ? <span key={i} className="gap" /> : <CommandButton key={id} id={id} active={active === id} />)}</span>
}
