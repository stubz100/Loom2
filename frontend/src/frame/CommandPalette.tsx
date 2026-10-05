// Ctrl+K command palette (07 §3e): every registered command of the global scope and the current suite,
// filtered as you type, with its shortcut; Enter runs the highlighted one.
import { useEffect, useMemo, useRef, useState } from 'react'
import { create } from 'zustand'
import { useSession } from '../store/session'
import { commandsFor, isEnabled, keyLabel, markUsed, type Command, type Scope } from './commands'

interface PaletteState { open: boolean; toggle: () => void; close: () => void }
export const usePalette = create<PaletteState>()((set, get) => ({ open: false, toggle: () => set({ open: !get().open }), close: () => set({ open: false }) }))

export function CommandPalette() {
  const open = usePalette((s) => s.open)
  const close = usePalette((s) => s.close)
  const suite = useSession((s) => s.ui.suite)
  const [q, setQ] = useState('')
  const [at, setAt] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const all = useMemo(() => [...commandsFor(suite as Scope), ...commandsFor('global')], [suite, open]) // eslint-disable-line react-hooks/exhaustive-deps
  const list = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean)
    return all.filter((c) => words.every((w) => c.label.toLowerCase().includes(w) || c.id.includes(w) || (c.keys ?? '').toLowerCase().includes(w)))
  }, [all, q])
  useEffect(() => { if (open) { setQ(''); setAt(0); setTimeout(() => input.current?.focus(), 0) } }, [open])
  useEffect(() => { setAt(0) }, [q])
  if (!open) return null
  const run = (c: Command) => { close(); if (isEnabled(c)) c.run() }
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal palette" onClick={(e) => e.stopPropagation()}>
        <input ref={input} type="text" value={q} placeholder="Type a command…" onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setAt((i) => Math.min(list.length - 1, i + 1)) }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setAt((i) => Math.max(0, i - 1)) }
            else if (e.key === 'Enter') { e.preventDefault(); const c = list[at]; if (c) run(c) }
            else if (e.key === 'Escape') { e.preventDefault(); close() }
          }} />
        <div className="list">
          {list.slice(0, 40).map((c, i) => { markUsed(c.id); const Icon = c.icon; return (
            <button key={c.id} className={`item${i === at ? ' focus' : ''}${isEnabled(c) ? '' : ' disabled'}`} onMouseEnter={() => setAt(i)} onClick={() => run(c)}>
              <span className="ic">{Icon ? <Icon size={14} /> : null}</span><span className="lbl">{c.label}</span><span className="scope">{c.scope}</span>{c.keys && <kbd>{keyLabel(c.keys)}</kbd>}
            </button>
          ) })}
          {!list.length && <div className="muted" style={{ padding: 8 }}>No command matches.</div>}
        </div>
      </div>
    </div>
  )
}
