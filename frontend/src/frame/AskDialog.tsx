// In-app confirm / text prompt (07 §1: no native dialogs except OS file pickers — WebView2 routes window.confirm /
// window.prompt to a Tauri plugin that is not allowed, so they crash). Enter confirms, Escape cancels; the promise
// behind it resolves with true / the text, or null when cancelled.
import { useEffect, useRef, useState } from 'react'
import { useSession } from '../store/session'

export function AskDialog() {
  const ask = useSession((s) => s.ask)
  const resolve = useSession((s) => s.resolveAsk)
  const [value, setValue] = useState('')
  const okRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { setValue(ask?.initial ?? ''); if (ask?.kind === 'confirm') okRef.current?.focus() }, [ask])
  if (!ask) return null
  const canOk = ask.kind === 'confirm' || value.trim().length > 0
  const ok = () => { if (canOk) resolve(ask.kind === 'prompt' ? value.trim() : true) }
  const cancel = () => resolve(null)
  return (
    <div className="modal-backdrop" onClick={cancel}>
      <div className="modal ask" role="dialog" aria-modal="true" aria-label={ask.title} onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); cancel() } else if (e.key === 'Enter') { e.stopPropagation(); ok() } }}>
        <div className="head">{ask.title}</div>
        <div className="body">
          {ask.text && <p className="ask-text">{ask.text}</p>}
          {ask.kind === 'prompt' && <input type="text" autoFocus value={value} placeholder={ask.placeholder} onChange={(e) => setValue(e.target.value)} onFocus={(e) => e.target.select()} />}
        </div>
        <div className="foot">
          <button onClick={cancel}>Cancel</button>
          <button ref={okRef} className={ask.danger ? 'danger' : 'primary'} disabled={!canOk} onClick={ok}>{ask.okLabel ?? 'OK'}</button>
        </div>
      </div>
    </div>
  )
}
