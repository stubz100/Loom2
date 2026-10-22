// D119 (SC2): one preset panel for every preset in the app — behind the item's + (the author, 2026-10-22: "keep the + sign, which expands
// into a small panel when clicked on, containing all presets as small icons and all functions related to presets"). Beside the + only
// the chosen presets' tiles stay (`chosen`); the panel holds every tile (frame/PresetIcons — glyphs or pictures, never letters, D92), the
// words toggle, *Save the current as a preset…* (a name typed in place) and the host's verbs for the tile last clicked (`verbs(id)`:
// a CommandRow of the host's own commands, so every verb is a button — D32). Mouse-first: the + opens and closes it; Esc and a click
// outside close it; a tile's right-click keeps its menu.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Plus, X } from 'lucide-react'
import { PresetIcons, type PresetIcon } from './PresetIcons'
import './presetPanel.css'

export interface PresetPanelProps {
  label: string                                   // the group's accessible name ("lighting presets")
  items: PresetIcon[]
  selected?: string[] | string | null
  onPick: (id: string, e: React.MouseEvent) => void
  onContext?: (id: string, e: React.MouseEvent) => void
  /** The host's verbs for the tile last clicked in the panel (null: none yet) — a CommandRow of its commands. */
  verbs?: (focused: string | null) => ReactNode
  /** "Save the current as a preset…": the host saves under the name typed. */
  onSave?: (name: string) => void | Promise<unknown>
  saveLabel?: string
  canSave?: boolean
  saveWhy?: string                                // why it cannot save now (the button's title)
  showText?: boolean
  onShowText?: (on: boolean) => void
  size?: number
  empty?: ReactNode                               // the panel's words when there is no preset
  chosen?: PresetIcon[]                           // the tiles shown beside the + (the ones in use); a click there picks them as in the panel
  title?: string                                  // the + button's tooltip
  className?: string
  tools?: ReactNode                               // extra controls in the panel's head (the host's)
}

export function PresetPanel({ label, items, selected, onPick, onContext, verbs, onSave, saveLabel = 'Save the current as a preset…', canSave = true, saveWhy, showText, onShowText,
  size = 40, empty, chosen, title, className, tools }: PresetPanelProps) {
  const [open, setOpen] = useState(false)
  const [naming, setNaming] = useState<string | null>(null)
  const [focused, setFocused] = useState<string | null>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const [at, setAt] = useState<{ left: number; top: number } | null>(null)
  useLayoutEffect(() => {                                                // under the +, inside the window (a panel is never clipped by its column)
    if (!open || !btn.current) return
    const r = btn.current.getBoundingClientRect()
    const w = Math.min(360, window.innerWidth - 16)
    const left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8))
    const h = panel.current?.getBoundingClientRect().height ?? 240
    const top = r.bottom + 4 + h > window.innerHeight - 8 ? Math.max(8, r.top - 4 - h) : r.bottom + 4
    setAt({ left, top })
  }, [open, items.length, naming, focused, showText])
  useEffect(() => {
    if (!open) return
    const down = (e: PointerEvent) => { const t = e.target as Node; if (panel.current?.contains(t) || btn.current?.contains(t)) return; setOpen(false) }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false) } }
    window.addEventListener('pointerdown', down, true)
    window.addEventListener('keydown', key, true)
    return () => { window.removeEventListener('pointerdown', down, true); window.removeEventListener('keydown', key, true) }
  }, [open])
  const commit = () => { if (naming !== null && onSave) { void onSave(naming.trim()); setNaming(null) } }
  return (
    <span className={`preset-panel-host${className ? ` ${className}` : ''}`}>
      {chosen && chosen.length > 0 && <PresetIcons label={`${label} in use`} size={Math.round(size * 0.8)} items={chosen} selected={chosen.map((c) => c.id)} onPick={onPick} onContext={onContext} />}
      <button ref={btn} type="button" className={`preset-btn${open ? ' open' : ''}`} title={title ?? `${label}: the presets and what to do with them`} aria-label={label} aria-haspopup="dialog" aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen(!open) }} data-preset-panel-btn><Plus size={13} /></button>
      {open && (
        <div ref={panel} className="preset-panel" role="dialog" aria-label={label} data-preset-panel style={at ? { left: at.left, top: at.top } : { visibility: 'hidden' }}
          onClick={(e) => e.stopPropagation()} onContextMenu={(e) => e.stopPropagation()}>
          <div className="pp-head"><b>{label}</b><span className="spacer" />
            {onShowText && <button type="button" className={`quiet${showText ? ' active' : ''}`} aria-pressed={!!showText} title="The words under the tiles" onClick={() => onShowText(!showText)}>words</button>}
            {tools}
            <button type="button" className="quiet" title="Close" aria-label="close the presets" onClick={() => setOpen(false)}><X size={13} /></button></div>
          {items.length
            ? <PresetIcons label={label} size={size} showText={showText} items={items} selected={selected}
                onPick={(id, e) => { setFocused(id); onPick(id, e) }} onContext={(id, e) => { setFocused(id); onContext?.(id, e) }} />
            : <p className="hint">{empty ?? 'No presets yet.'}</p>}
          {onSave && (naming === null
            ? <div className="pp-save"><button type="button" className="quiet" disabled={!canSave} title={canSave ? saveLabel : (saveWhy ?? 'nothing to save yet')} onClick={() => setNaming('')}><Plus size={12} /> {saveLabel}</button></div>
            : <div className="pp-save saver">
                <input type="text" autoFocus value={naming} aria-label={`a name for the new preset`} placeholder="a name for it" onChange={(e) => setNaming(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { e.stopPropagation(); setNaming(null) } }} />
                <button type="button" className="primary" onClick={commit}>Save</button>
                <button type="button" className="quiet" onClick={() => setNaming(null)}>Cancel</button>
              </div>)}
          {verbs && <div className="pp-verbs" data-focused={focused ?? undefined}>{verbs(focused)}</div>}
        </div>
      )}
    </span>
  )
}
