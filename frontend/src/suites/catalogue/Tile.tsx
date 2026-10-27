import { memo } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { beginDrag, type DragItem, mediaOf } from '../../frame/drag'

export interface TileProps {
  a: Asset; size: number; fill: boolean; caption?: 'off' | 'prompt' | 'model'; selected: boolean; primary: boolean; pinned: number
  onClick: (e: React.MouseEvent, id: string) => void; onDouble: (id: string) => void; dragItems?: () => DragItem[]; onContext?: (e: React.MouseEvent, id: string) => void
  onLineage?: (id: string) => void
  onEdit?: (id: string) => void                                    // D95 (IM1, UX0): Image's results — ✎ Edit on the tile, opened in place
  corner?: { icon?: React.ReactNode; label: string; run: () => void }   // a pick started from a panel (the Bin): the verb's button top right, always shown
  onUse?: (id: string) => void; useLabel?: string                 // D125 (I2): Image's results with the For chip — ✓ Use as the shot's frame
  onPrototype?: (e: React.MouseEvent, id: string) => void          // proto01_UIcast CW1: the hover button 🧪 — Prototype ▸ (a picture into an idea)
  mark?: string                                                    // D125 (I2): "frame ✓" on the For chip's shot's current frame
  noDrag?: boolean                                                 // V58: a trashed tile is not used anywhere — it does not drag at all
}

/** The scene of a JSON prompt, else the prompt text, for the caption. */
const promptLine = (a: Asset) => ((a.prompt_json as { scene?: string } | null)?.scene ?? a.prompt_text ?? '').trim()

export const Tile = memo(function Tile({ a, size, fill, caption = 'off', selected, primary, pinned, onClick, onDouble, dragItems, onContext, onLineage, onEdit, corner, onUse, useLabel, mark, onPrototype, noDrag }: TileProps) {
  const thumb = api.thumbUrl(a.id, size > 256 ? 512 : 256)
  const derived = a.root_id && a.root_id !== a.id
  return (
    <div className={`tile${selected ? ' selected' : ''}${primary ? ' primary' : ''}${fill ? ' fill' : ''}`}
      data-id={a.id} tabIndex={-1} onClick={(e) => onClick(e, a.id)} onDoubleClick={() => onDouble(a.id)} onContextMenu={(e) => onContext?.(e, a.id)}
      onPointerDown={noDrag ? undefined : (e) => beginDrag(e, () => {   // a selected tile carries the selection, another one only itself
        const self: DragItem = { kind: 'asset', id: a.id, media: mediaOf(a.kind) }
        return { items: selected ? (dragItems?.() ?? [self]) : [self], thumb }
      })}
      title={`${a.model_id ?? a.suite} · seed ${a.seed ?? '—'} · ${a.w ?? '?'}×${a.h ?? '?'} · ${new Date(a.created_at).toLocaleTimeString()}`}>
      <div className="thumb">
        {a.thumb_status === 'done' || a.thumb_status === 'pending' ? <img src={thumb} alt="" loading="lazy" decoding="async" draggable={false} /> : <span className="missing">no thumbnail</span>}
      </div>
      <div className="badges">
        {mark && <span className="badge-mark" title="the shot version's frame">{mark}</span>}
        {a.kind === 'video' && <span className="badge-dot" title="clip">🎬</span>}
        {a.kind === 'mesh' && <span className="badge-dot" title="3D prop (GLB)">🧊</span>}
        {a.kind === 'audio' && <span className="badge-dot" title="a spoken line (audio)">🔊</span>}
        {a.has_document && <span className="badge-dot" title="has document">✎</span>}
        {derived && (onLineage
          ? <button className="badge-dot lin" title="derived from another asset: show the lineage" aria-label="Show lineage" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onLineage(a.id) }}>⤷</button>
          : <span className="badge-dot" title="derived from another asset">⤷</span>)}
      </div>
      {onEdit && a.kind === 'image' && <button type="button" className="tile-edit" title="Edit this image (Image · Edit, in place) — or double-click it, or E" aria-label="Edit" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onEdit(a.id) }}>✎ Edit</button>}
      {onPrototype && a.kind === 'image' && !a.trashed_at && <button type="button" className="tile-proto" title="Prototype ▸ — a new idea in Cast from this picture (a copy), or into an idea" aria-label="Prototype" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onPrototype(e, a.id) }}>🧪</button>}
      {onUse && a.kind === 'image' && <button type="button" className="tile-use" title={useLabel} aria-label={useLabel} onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onUse(a.id) }}>✓</button>}
      {corner && <button type="button" className="tile-pick" title={corner.label} aria-label={corner.label} onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); corner.run() }}>{corner.icon ?? '＋'}</button>}
      {pinned > 0 && <span className="pin">C{pinned}</span>}
      {caption === 'model' && <div className="label"><span>{a.model_id ?? a.suite}</span><span style={{ marginLeft: 'auto' }}>{a.seed ?? ''}</span></div>}
      {caption === 'prompt' && <div className="label"><span className="prompt">{promptLine(a) || a.model_id || a.suite}</span></div>}
    </div>
  )
})
