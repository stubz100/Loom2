// Icon buttons bound to registry commands: label + shortcut in the tooltip, disabled from `when`, and the
// command marked as mouse-reachable for the dev audit (07 §3c).
import { command, isEnabled, markUsed, runCommand, titleFor, type IconType, type MenuItem } from './commands'
import { openPressMenu } from './ContextMenu'
import { useKeymap } from './keymap'

/** A toolbar button that opens a menu (e.g. "add adjustment ▾") — a press menu (D55): press, drag onto an item, release; or click
 * to open it and click an item. */
export function MenuButton({ label, icon: Icon, items, text, size = 16 }: { label: string; icon?: IconType; items: () => MenuItem[]; text?: boolean; size?: number }) {
  return (
    <button type="button" className="cmd-btn" title={`${label} — press and drag to an entry, or click`} aria-label={label} aria-haspopup="menu"
      onPointerDown={(e) => openPressMenu(e, items)} onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') openPressMenu({ button: 0, currentTarget: e.currentTarget, preventDefault: () => e.preventDefault() }, items, true) }}>
      {Icon ? <Icon size={size} /> : null}{(text || !Icon) && <span>{label}</span>}<span className="caret">▾</span>
    </button>
  )
}

export function CommandButton({ id, active, text, size = 16, className = '', label, drop }: { id: string; active?: boolean; text?: boolean; size?: number; className?: string; label?: string; drop?: string }) {
  useKeymap((k) => k.version)                                          // D72: re-render the tooltip after a remap
  const c = command(id)
  if (!c) return null
  markUsed(id)
  const Icon = c.icon
  return (
    <button type="button" className={`cmd-btn${active ? ' active' : ''}${c.danger ? ' danger' : ''} ${className}`} title={titleFor(c, label)} aria-label={label ?? c.label} disabled={!isEnabled(c)} data-drop={drop} onClick={() => runCommand(id)}>
      {Icon ? <Icon size={size} /> : null}{(text || !Icon) && <span>{label ?? c.label}</span>}
    </button>
  )
}

/** D71 (P15): a quick-action card (empty states, "Start from this image") bound to a registry command: icon, label, a one-line hint. */
export function CommandCard({ id, hint, label }: { id: string; hint?: string; label?: string }) {
  useKeymap((k) => k.version)                                          // D72: re-render the tooltip after a remap
  const c = command(id)
  if (!c) return null
  markUsed(id)
  const Icon = c.icon
  return (
    <button type="button" className="quick-card" title={titleFor(c, label)} disabled={!isEnabled(c)} onClick={() => runCommand(id)}>
      {Icon ? <Icon size={22} /> : null}<span className="qc-label">{label ?? c.label}</span>{hint && <span className="qc-hint">{hint}</span>}
    </button>
  )
}

export function CommandRow({ ids, active, className = '', drops, labels }: { ids: (string | 'gap')[]; active?: string; className?: string; drops?: Record<string, string>; labels?: Record<string, string> }) {
  return <span className={`cmd-row ${className}`}>{ids.map((id, i) => id === 'gap' ? <span key={i} className="gap" /> : <CommandButton key={id} id={id} active={active === id} drop={drops?.[id]} label={labels?.[id]} />)}</span>
}
