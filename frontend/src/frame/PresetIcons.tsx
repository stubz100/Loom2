// D90 (02 §6.3, R3): one component for every preset row in the app — prompt-field presets, aspect and size, angle moves, styles, motion
// chips. Each preset is a small icon tile; its words live in the tooltip and the accessible name, and a section may show them under the
// tiles when the reader asks (`showText`). D92: no lettered tiles — every item carries a drawn glyph (`icon`, required); a picture (`img`)
// covers it when there is one, and `busy` marks a tile whose picture is being made (the glyph shows meanwhile).
import type { ReactNode } from 'react'
import './presetIcons.css'

export interface PresetIcon {
  id: string
  label: string                                   // the words: tooltip, aria-label and the optional caption
  icon: ReactNode                                 // a glyph (presetGlyphs.tsx) — shown while there is no picture, never letters (D92)
  img?: string | null                             // a sample image (a style's face, a generated swatch, a hero)
  busy?: boolean                                  // D92: its picture is being made
  hint?: string                                   // extra tooltip line (e.g. "default", the words of a named entry)
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
          <button key={p.id} type="button" className={`preset-icon${on ? ' active' : ''}${p.img ? ' img' : ' glyph'}${p.busy ? ' busy' : ''}`} aria-pressed={on} disabled={p.disabled}
            title={[p.label, p.hint, p.busy ? 'its picture is being made…' : ''].filter(Boolean).join('\n')} aria-label={p.label} data-id={p.id}
            onClick={(e) => onPick(p.id, e)} onContextMenu={onContext ? (e) => { e.preventDefault(); onContext(p.id, e) } : undefined}>
            <span className="tile">{p.img ? <img src={p.img} alt="" draggable={false} /> : p.icon}{p.busy && <i className="busy-mark" aria-hidden="true" />}{p.badge && <i className="badge-corner">{p.badge}</i>}</span>
            {showText && <span className="cap">{p.label}</span>}
          </button>
        )
      })}
    </div>
  )
}
