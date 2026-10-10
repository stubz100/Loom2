// Settings · About (D36): which build this is — app version, the checkout commit the orchestrator runs from, the commit the
// shell was built from, the pinned engine and custom nodes, schema versions — plus the state / logs / models folders and a
// "Copy diagnostics" button that puts all of it (and the engine and queue state) on the clipboard for a bug report.
import { useEffect, useState } from 'react'
import { http, unwrap } from '../api/client'
import type { VersionInfo } from '../api/types'
import { isTauri, revealPath } from '../shell/tauri'
import { useSession } from '../store/session'

export function About() {
  const s = useSession()
  const [info, setInfo] = useState<VersionInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    unwrap(http.GET('/version')).then((v) => { if (live) setInfo(v) }).catch((e) => { if (live) setError(String(e)) })
    return () => { live = false }
  }, [])
  if (error) return <span className="hint">version unavailable: {error}</span>
  if (!info) return <span className="hint">reading version…</span>

  const checkout = info.git ? `${info.git.describe ?? info.git.sha}${info.git.dirty ? ' (uncommitted changes)' : ''}` : 'not a git checkout'
  const shell = info.shell ? `${info.shell.version} · ${info.shell.git_sha ?? '?'} · built ${info.shell.build_time ?? '?'}` : 'no shell (browser)'
  const running = info.engine.running ? String(info.engine.running.comfyui_version ?? 'running') : 'not running'
  const copy = async () => {
    const report = { version: info, health: s.health, engine: s.engine, queue: s.queue, ui: { suite: s.ui.suite, theme: s.ui.theme }, at: new Date().toISOString() }
    const text = JSON.stringify(report, null, 2)
    try { await navigator.clipboard.writeText(text); s.toast('Diagnostics copied to the clipboard', 'success') } catch { s.toast('Could not reach the clipboard', 'error') }
  }
  const reveal = (path: string) => (isTauri() ? <button onClick={() => void revealPath(path)}>Reveal</button> : null)
  return (
    <>
      <label>Version</label><span>{info.app} · {info.variant} variant</span>
      <label>Checkout</label><span className="mono">{checkout}</span>
      <label>Shell build</label><span className="mono">{shell}</span>
      <label>Engine</label><span className="mono">ComfyUI {info.engine.pin ?? '?'} pinned · {running}</span>
      <label>Custom nodes</label><span className="mono">{info.nodes.map((n) => `${n.name} ${n.commit}`).join(' · ') || 'none'}</span>
      <label>Schemas</label><span className="mono">{Object.entries(info.schemas).map(([k, v]) => `${k} ${v}`).join(' · ')}</span>
      <label>App state</label><span className="mono row">{info.paths.state} {reveal(info.paths.state)}</span>
      <label>Logs</label><span className="mono row">{info.paths.logs} {reveal(info.paths.logs)}</span>
      <label>Models root</label><span className="mono row">{info.paths.models_root} {reveal(info.paths.models_root)}</span>
      <label>Diagnostics</label><span><button onClick={() => void copy()}>Copy diagnostics</button></span>
      <span className="hint">versions, engine and queue state as JSON — paste it into a bug report or the journal</span>
    </>
  )
}
