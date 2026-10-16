// D90 (02 §6.3, R3): one component for every preset row in the app — prompt-field presets, aspect and size, angle moves, styles, motion
// chips. Each preset is a small icon tile (a glyph, a sample image, or a monogram while it has neither); its words live in the tooltip and
// the accessible name, and a section may show them under the tiles when the reader asks (`showText`).
import type { ReactNode } from 'react'
import { monogram } from './presetGlyphs'
import './presetIcons.css'

export interface PresetIcon {
  id: string
  label: string                                   // the words: tooltip, aria-label and the optional caption
  icon?: ReactNode                                // a glyph (presetGlyphs.tsx)
  img?: string | null                             // a sample image (a style's face, a generated swatch)
  hint?: string                                   // extra tooltip line (e.g. "default", "yours")
  badge?: string                                  // a corner mark (★ for a default)
  disabled?: boolean
}

interface Props {
  items: PresetIcon[]
  selected?: string[] | string | null
  onPick: (id: string, e: React.MouseEvent) => void
  onContext?: (id: string, e: React.MouseEvent) => void
  size?: number                                   // tile size in px (40 by default; styles use 48)
  showText?: boolean
  label?: string                                  // the group's accessible name
}

export function PresetIcons({ items, selected, onPick, onContext, size = 40, showText = false, label }: Props) {
  const sel = new Set(Array.isArray(selected) ? selected : selected ? [selected] : [])
  return (
    <div className={`preset-icons${showText ? ' with-text' : ''}`} role="group" aria-label={label} style={{ '--tile': `${size}px` } as React.CSSProperties}>
      {items.map((p) => {
        const on = sel.has(p.id)
        return (
          <button key={p.id} type="button" className={`preset-icon${on ? ' active' : ''}${p.img ? ' img' : p.icon ? ' glyph' : ' mono'}`} aria-pressed={on} disabled={p.disabled}
            title={p.hint ? `${p.label}\n${p.hint}` : p.label} aria-label={p.label}
            onClick={(e) => onPick(p.id, e)} onContextMenu={onContext ? (e) => { e.preventDefault(); onContext(p.id, e) } : undefined}>
            <span className="tile">{p.img ? <img src={p.img} alt="" draggable={false} /> : p.icon ?? <span className="mono-text">{monogram(p.label)}</span>}{p.badge && <i className="badge-corner">{p.badge}</i>}</span>
            {showText && <span className="cap">{p.label}</span>}
          </button>
        )
      })}
    </div>
  )
}
