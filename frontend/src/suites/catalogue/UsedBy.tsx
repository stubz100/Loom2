// D92 §4.2: "used by: Mara v1 · references; Style · Ink wash" — each user a link that opens it (groupUsers.ts). In the page's header (`compact`) the first
// user and "+N"; the tooltip names them all and the card's Inspector lists every one.
import { Link2 } from 'lucide-react'
import { useAlbum } from './albumStore'
import { openUser, usedByText, userLabel, userPlace } from './groupUsers'

export function UsedBy({ gid, compact = false }: { gid: string; compact?: boolean }) {
  const users = useAlbum((s) => s.usedBy[gid])
  if (!users?.length) return compact ? null : <span className="muted">Nothing in Story or Stage uses this group.</span>
  const shown = compact ? users.slice(0, 1) : users
  return (
    <span className={`used-by${compact ? ' compact' : ''}`} data-testid="used-by" title={compact ? usedByText(users) : undefined}>
      {compact && <><Link2 size={12} className="ic" aria-hidden /><span className="lead">used by:</span></>}
      {shown.map((u, i) => (
        <span key={`${u.kind}:${u.id}:${u.version ?? ''}:${u.group_id}`}>
          <button type="button" className="link" onClick={() => openUser(u)} title={`Open in ${userPlace(u)}`}>{userLabel(u)}</button>{i < shown.length - 1 ? '; ' : ''}
        </span>
      ))}
      {compact && users.length > 1 && <span className="more">+{users.length - 1}</span>}
    </span>
  )
}
