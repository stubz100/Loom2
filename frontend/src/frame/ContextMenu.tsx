// Right-click menus (07 §3c): one store holds the open menu; any element opens one with `showMenu(e, items)`.
// Items are commands from the registry (label, icon, shortcut and enabled state come from there) or ad-hoc
// entries. Keyboard: ↑ ↓ move, → opens a submenu, ← closes it, Enter runs, Esc closes. Shift+F10 / the Menu key
// re-dispatch a contextmenu event at the focused element (useKeyboardMap), so every menu is reachable without a mouse.
import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { create } from 'zustand'
import { command, isEnabled, keyLabel, markUsed, type IconType, type MenuItem } from './commands'
import './menu.css'

interface MenuState { open: { x: number; y: number; items: MenuItem[] } | null; show: (x: number, y: number, items: MenuItem[]) => void; hide: () => void }
export const useMenu = create<MenuState>()((set) => ({ open: null, show: (x, y, items) => set({ open: { x, y, items } }), hide: () => set({ open: null }) }))

/** Open a context menu at the pointer (or at an element for keyboard-triggered menus). */
export function showMenu(e: ReactMouseEvent | MouseEvent | { clientX: number; clientY: number }, items: MenuItem[]): void {
  if ('preventDefault' in e) { e.preventDefault(); (e as ReactMouseEvent).stopPropagation?.() }
  useMenu.getState().show(e.clientX, e.clientY, items)
}

type Resolved =
  | { kind: 'item'; label: string; icon?: IconType; keys?: string; run: () => void; disabled: boolean; danger?: boolean; checked?: boolean }
  | { kind: 'sep' } | { kind: 'heading'; label: string } | { kind: 'sub'; label: string; icon?: IconType; items: MenuItem[] }

function resolve(it: MenuItem): Resolved | null {
  if ('sep' in it) return { kind: 'sep' }
  if ('heading' in it) return { kind: 'heading', label: it.heading }
  if ('items' in it) return { kind: 'sub', label: it.label, icon: it.icon, items: it.items }
  if ('cmd' in it) {
    const c = command(it.cmd)
    if (!c) return null
    markUsed(c.id)
    return { kind: 'item', label: it.label ?? c.label, icon: c.icon, keys: c.keys, run: c.run, disabled: !isEnabled(c), danger: c.danger }
  }
  return { kind: 'item', label: it.label, icon: it.icon, keys: it.keys, run: it.run, disabled: !!it.disabled, danger: it.danger, checked: it.checked }
}

function MenuList({ items, x, y, depth, onClose }: { items: MenuItem[]; x: number; y: number; depth: number; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ x, y })
  const [focus, setFocus] = useState(-1)
  const [sub, setSub] = useState<number | null>(null)
  const rows = items.map(resolve).filter(Boolean) as Resolved[]
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const nx = Math.min(x, window.innerWidth - r.width - 6), ny = Math.min(y, window.innerHeight - r.height - 6)
    setPos({ x: Math.max(4, nx), y: Math.max(4, ny) })
  }, [x, y, items])
  useEffect(() => {
    if (depth !== 0) return
    const onKey = (e: KeyboardEvent) => {
      const sel = rows.map((r, i) => (r.kind === 'item' && !r.disabled) || r.kind === 'sub' ? i : -1).filter((i) => i >= 0)
      if (!sel.length) return
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const at = sel.indexOf(focus)
        const next = e.key === 'ArrowDown' ? sel[(at + 1) % sel.length] : sel[(at - 1 + sel.length) % sel.length]
        setFocus(next); setSub(null)
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        const r = rows[focus]
        if (r?.kind === 'item') { r.run(); onClose() } else if (r?.kind === 'sub') setSub(focus)
      } else if (e.key === 'ArrowRight') { const r = rows[focus]; if (r?.kind === 'sub') { e.preventDefault(); setSub(focus) } }
      else if (e.key === 'ArrowLeft') { if (sub !== null) { e.preventDefault(); setSub(null) } }
      else if (e.key === 'Escape') { e.preventDefault(); onClose() }
    }
    window.addEventListener('keydown', onKey, { capture: true })
    return () => window.removeEventListener('keydown', onKey, { capture: true })
  }, [rows, focus, sub, depth, onClose])
  return (
    <div className="ctx-menu" ref={ref} style={{ left: pos.x, top: pos.y }} role="menu" onContextMenu={(e) => e.preventDefault()}>
      {rows.map((r, i) => {
        if (r.kind === 'sep') return <div key={i} className="sep" />
        if (r.kind === 'heading') return <div key={i} className="heading">{r.label}</div>
        const Icon = r.icon
        if (r.kind === 'sub') return (
          <div key={i} className={`item sub${focus === i ? ' focus' : ''}`} role="menuitem" onMouseEnter={() => { setFocus(i); setSub(i) }} onClick={(e) => { e.stopPropagation(); setSub(i) }}>
            <span className="ic">{Icon ? <Icon size={14} /> : null}</span><span className="lbl">{r.label}</span><span className="arrow">▸</span>
            {sub === i && ref.current && <MenuList items={r.items} x={pos.x + ref.current.offsetWidth - 4} y={pos.y + (ref.current.children[i] as HTMLElement).offsetTop - 4} depth={depth + 1} onClose={onClose} />}
          </div>
        )
        return (
          <button key={i} type="button" className={`item${r.disabled ? ' disabled' : ''}${r.danger ? ' danger' : ''}${focus === i ? ' focus' : ''}`} role="menuitem" disabled={r.disabled}
            onMouseEnter={() => { setFocus(i); setSub(null) }} onClick={(e) => { e.stopPropagation(); if (r.disabled) return; r.run(); onClose() }}>
            <span className="ic">{r.checked ? '✓' : Icon ? <Icon size={14} /> : null}</span><span className="lbl">{r.label}</span>{r.keys && <kbd>{keyLabel(r.keys)}</kbd>}
          </button>
        )
      })}
    </div>
  )
}

export function ContextMenuHost() {
  const open = useMenu((s) => s.open)
  const hide = useMenu((s) => s.hide)
  useEffect(() => {
    if (!open) return
    const close = () => hide()
    const onDown = (e: PointerEvent) => { if (!(e.target as HTMLElement)?.closest('.ctx-menu')) hide() }
    window.addEventListener('pointerdown', onDown, { capture: true })
    window.addEventListener('wheel', close, { passive: true })
    return () => { window.removeEventListener('pointerdown', onDown, { capture: true }); window.removeEventListener('wheel', close) }
  }, [open, hide])
  if (!open) return null
  return <MenuList items={open.items} x={open.x} y={open.y} depth={0} onClose={hide} />
}
