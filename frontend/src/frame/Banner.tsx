import { X } from 'lucide-react'
import { useSession } from '../store/session'

export function Banner() {
  const s = useSession()
  const banners = s.banners()
  const b = banners[0]
  if (!b) return <div style={{ gridArea: 'banner' }} />
  return (
    <div className={`banner ${b.kind ?? 'info'}`} role="status">
      <span>{b.text}</span>
      {banners.length > 1 && <span className="badge">+{banners.length - 1}</span>}
      <span className="spacer" />
      {b.action && <button className="primary" onClick={b.action.run}>{b.action.label}</button>}
      {b.kind !== 'error' && <button className="quiet" onClick={() => s.dismissBanner(b.id)} aria-label="dismiss"><X size={14} /></button>}
    </div>
  )
}
