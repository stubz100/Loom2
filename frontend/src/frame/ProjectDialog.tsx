import { FolderOpen } from 'lucide-react'
import { useState } from 'react'
import { ApiError } from '../api/client'
import { isTauri, pickFolder } from '../shell/tauri'
import { useSession } from '../store/session'

export function ProjectDialog({ mode }: { mode: 'new' | 'open' }) {
  const s = useSession()
  const [path, setPath] = useState(mode === 'open' ? (s.recents[0] ?? '') : (s.recents[0] ? s.recents[0].replace(/[\\/][^\\/]+$/, '/') : ''))   // C27: next to the last project
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const submit = async () => {
    setBusy(true); setErr(null)
    try { if (mode === 'new') await s.createProject(path, name); else await s.openProject(path) }
    catch (e) { setErr((e as ApiError).detail ?? String(e)) }
    finally { setBusy(false) }
  }
  const browse = async () => {
    const picked = await pickFolder(mode === 'new' ? 'Choose an empty folder for the new project' : 'Open a loom2 project folder', path)
    if (picked) {
      setPath(picked)
      if (mode === 'new' && !name) setName(picked.split(/[\\/]/).filter(Boolean).pop() ?? '')
    }
  }
  return (
    <div className="modal-backdrop" onClick={() => s.setProjectDialog(null)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="head">{mode === 'new' ? 'New project' : 'Open project'}<span className="spacer" /><button className="quiet" onClick={() => s.setProjectDialog(null)}>Close</button></div>
        <div className="body form">
          <label>Folder</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <input type="text" value={path} onChange={(e) => setPath(e.target.value)} placeholder="F:/loom2-projects/my-film" autoFocus style={{ flex: 1 }} />
            {isTauri() && <button onClick={() => void browse()} title="Browse (OS folder picker)"><FolderOpen size={16} /></button>}
          </div>
          <span className="hint">{mode === 'new' ? 'An empty (or new) folder on the work disk. Weights never live here.' : 'A folder containing project.json.'}</span>
          {mode === 'new' && <><label>Name</label><input type="text" value={name} onChange={(e) => setName(e.target.value)} /></>}
          {mode === 'new' && <><label>Format</label><span className="hint" style={{ gridColumn: 2, marginTop: 0 }}>16:9 · 1920×1080 @ 24 fps · default tier Draft (D18)</span></>}
          {err && <div style={{ gridColumn: '1 / -1', color: 'var(--error)' }}>{err}</div>}
        </div>
        <div className="foot">
          <button onClick={() => s.setProjectDialog(null)}>Cancel</button>
          <button className="primary" disabled={busy || !path || (mode === 'new' && !name)} onClick={() => void submit()}>{mode === 'new' ? 'Create' : 'Open'}</button>
        </div>
      </div>
    </div>
  )
}
