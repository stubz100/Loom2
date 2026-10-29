// B1 (D159): one tile for the Bin's layer and its drawer — a click selects (Ctrl adds, Shift a range), a right-click opens the verbs on the
// selection, a drag carries the selection (or this tile) wherever a thing goes (frame/drag), the role as a badge, the compare pin as a
// letter, and a pick's corner button (the drawer).
import type { ReactNode } from 'react'
import { api } from '../../api/client'
import type { BinThing } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import type { MenuItem } from '../../frame/commands'
import { beginDrag, mediaOf } from '../../frame/drag'
import { ROLE_LABEL, selectedThings, TRASH, useBin } from './binStore'

const badgeOf = (it: BinThing): string | undefined => it.roles.map((r) => ROLE_LABEL[r]).find(Boolean)

export function BinTile({ it, menu, onDouble, corner }: {
  it: BinThing; menu: (it: BinThing) => MenuItem[]; onDouble: () => void; corner?: { icon?: ReactNode; label: string; run: () => void }
}) {
  const id = it.asset.id
  const sel = useBin((s) => s.selection.includes(id))
  const primary = useBin((s) => s.selected === id)
  const pin = useBin((s) => s.pins.findIndex((a) => a.id === id) + 1)
  const badge = badgeOf(it)
  return (
    <button className={`w-tile${sel || primary ? ' selected' : ''}${primary ? ' primary' : ''}`} data-id={id} title={it.asset.prompt_text ?? it.path}
      onClick={(e) => useBin.getState().select(id, e.shiftKey ? 'range' : e.ctrlKey || e.metaKey ? 'toggle' : 'single')}
      onDoubleClick={onDouble}
      onContextMenu={(e) => { e.preventDefault(); const s = useBin.getState(); if (!s.selection.includes(id)) s.select(id); showMenu(e, menu(it)) }}
      onPointerDown={(e) => beginDrag(e, () => {
        if (useBin.getState().open === TRASH || it.asset.trashed_at) return null
        const s = useBin.getState()
        const list = s.selection.includes(id) ? selectedThings() : [it]                  // the selection, when the tile is in it
        return { items: list.map((x) => ({ kind: 'asset' as const, id: x.asset.id, media: mediaOf(x.asset.kind) })), thumb: api.thumbUrl(id, 256), from: 'bin',
          label: list.length > 1 ? `${list.length} things` : undefined }
      })}>
      {it.asset.kind === 'audio' ? <span className="b-audio">♪ {it.asset.prompt_text || 'sound'}</span> : <img src={api.thumbUrl(id, 256)} alt="" draggable={false} />}
      {badge && <span className="w-badge">{badge}</span>}
      {pin > 0 && <span className="b-pin" title="pinned for compare">{String.fromCharCode(64 + pin)}</span>}
      {corner && <span className="b-corner" role="button" tabIndex={-1} title={corner.label} aria-label={corner.label}
        onClick={(e) => { e.stopPropagation(); corner.run() }} onDoubleClick={(e) => e.stopPropagation()}>{corner.icon ?? '＋'}</span>}
    </button>
  )
}
