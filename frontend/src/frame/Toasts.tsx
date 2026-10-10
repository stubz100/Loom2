import { X } from 'lucide-react'
import { useSession } from '../store/session'

export function Toasts() {
  const toasts = useSession((s) => s.toasts)
  const dismiss = useSession((s) => s.dismissToast)
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          <span className="toast-text">{t.text}</span>
          {t.undo && <button onClick={() => { t.undo?.(); dismiss(t.id) }}>Undo</button>}
          <button className="quiet" onClick={() => dismiss(t.id)} aria-label="dismiss"><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}
