import { memo } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { beginDrag } from '../../frame/drag'

export interface TileProps {
  a: Asset; size: number; fill: boolean; caption?: 'off' | 'prompt' | 'model'; selected: boolean; primary: boolean; pinned: number
  onClick: (e: React.MouseEvent, id: string) => void; onDouble: (id: string) => void; dragIds?: () => string[]; onContext?: (e: React.MouseEvent, id: string) => void
  onLineage?: (id: string) => void
}

/** The scene of a JSON prompt, else the prompt text, for the caption. */
const promptLine = (a: Asset) => ((a.prompt_json as { scene?: string } | null)?.scene ?? a.prompt_text ?? '').trim()

export const Tile = memo(function Tile({ a, size, fill, caption = 'off', selected, primary, pinned, onClick, onDouble, dragIds, onContext, onLineage }: TileProps) {
  const thumb = api.thumbUrl(a.id, size > 256 ? 512 : 256)
  const stateBadge = a.state === 'keep' ? '✓' : a.state === 'reject' ? '✗' : null
  const derived = a.root_id && a.root_id !== a.id
  return (
    <div className={`tile${selected ? ' selected' : ''}${primary ? ' primary' : ''}${a.state === 'reject' ? ' reject' : ''}${fill ? ' fill' : ''}`}
      data-id={a.id} tabIndex={-1} onClick={(e) => onClick(e, a.id)} onDoubleClick={() => onDouble(a.id)} onContextMenu={(e) => onContext?.(e, a.id)}
      onPointerDown={(e) => beginDrag(e, () => {                     // a selected tile carries the selection, another one only itself
        const ids = selected ? (dragIds?.() ?? [a.id]) : [a.id]
        return { items: ids.map((id) => ({ kind: 'asset' as const, id })), thumb }
      })}
      title={`${a.model_id ?? a.suite} · seed ${a.seed ?? '—'} · ${a.w ?? '?'}×${a.h ?? '?'} · ${new Date(a.created_at).toLocaleTimeString()}`}>
      <div className="thumb">
        {a.thumb_status === 'done' || a.thumb_status === 'pending' ? <img src={thumb} alt="" loading="lazy" decoding="async" draggable={false} /> : <span className="missing">no thumbnail</span>}
      </div>
      <div className="badges">
        {stateBadge && <span className={`badge-dot ${a.state}`}>{stateBadge}</span>}
        {a.kind === 'video' && <span className="badge-dot" title="clip">🎬</span>}
        {a.has_document && <span className="badge-dot" title="has document">✎</span>}
        {derived && (onLineage
          ? <button className="badge-dot lin" title="derived from another asset: show the lineage" aria-label="Show lineage" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onLineage(a.id) }}>⤷</button>
          : <span className="badge-dot" title="derived from another asset">⤷</span>)}
      </div>
      {a.rating > 0 && <span className="stars">{'★'.repeat(a.rating)}</span>}
      {pinned > 0 && <span className="pin">C{pinned}</span>}
      {caption === 'model' && <div className="label"><span>{a.model_id ?? a.suite}</span><span style={{ marginLeft: 'auto' }}>{a.seed ?? ''}</span></div>}
      {caption === 'prompt' && <div className="label"><span className="prompt">{promptLine(a) || a.model_id || a.suite}</span></div>}
    </div>
  )
})
