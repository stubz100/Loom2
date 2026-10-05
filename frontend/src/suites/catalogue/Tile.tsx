import { memo } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'

export interface TileProps {
  a: Asset; size: number; fill: boolean; selected: boolean; primary: boolean; pinned: number
  onClick: (e: React.MouseEvent, id: string) => void; onDouble: (id: string) => void; dragIds?: () => string[]; onContext?: (e: React.MouseEvent, id: string) => void
}

export const Tile = memo(function Tile({ a, size, fill, selected, primary, pinned, onClick, onDouble, dragIds, onContext }: TileProps) {
  const thumb = api.thumbUrl(a.id, size > 256 ? 512 : 256)
  const stateBadge = a.state === 'keep' ? '✓' : a.state === 'reject' ? '✗' : null
  const derived = a.root_id && a.root_id !== a.id
  return (
    <div className={`tile${selected ? ' selected' : ''}${primary ? ' primary' : ''}${a.state === 'reject' ? ' reject' : ''}${fill ? ' fill' : ''}`}
      data-id={a.id} tabIndex={-1} onClick={(e) => onClick(e, a.id)} onDoubleClick={() => onDouble(a.id)} onContextMenu={(e) => onContext?.(e, a.id)} draggable
      onDragStart={(e) => { const ids = selected ? (dragIds?.() ?? [a.id]) : [a.id]; e.dataTransfer.setData('text/loom2-assets', ids.join(',')); e.dataTransfer.effectAllowed = 'copy' }}
      title={`${a.model_id ?? a.suite} · seed ${a.seed ?? '—'} · ${a.w ?? '?'}×${a.h ?? '?'} · ${new Date(a.created_at).toLocaleTimeString()}`}>
      <div className="thumb">
        {a.thumb_status === 'done' || a.thumb_status === 'pending' ? <img src={thumb} alt="" loading="lazy" decoding="async" draggable={false} /> : <span className="missing">no thumbnail</span>}
      </div>
      <div className="badges">
        {stateBadge && <span className={`badge-dot ${a.state}`}>{stateBadge}</span>}
        {a.kind === 'video' && <span className="badge-dot" title="clip">🎬</span>}
        {a.has_document && <span className="badge-dot" title="has document">✎</span>}
        {derived && <span className="badge-dot" title="derived from another asset">⤷</span>}
      </div>
      {a.rating > 0 && <span className="stars">{'★'.repeat(a.rating)}</span>}
      {pinned > 0 && <span className="pin">C{pinned}</span>}
      <div className="label"><span>{a.model_id ?? a.suite}</span><span style={{ marginLeft: 'auto' }}>{a.seed ?? ''}</span></div>
    </div>
  )
})
