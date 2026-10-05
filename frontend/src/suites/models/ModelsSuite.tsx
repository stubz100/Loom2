import { useState } from 'react'
import { create } from 'zustand'
import type { ModelEntry } from '../../api/types'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { DEFAULT_RAIL } from '../../frame/Rail'
import { revealPath } from '../../shell/tauri'
import { useSession } from '../../store/session'

interface ModelsUi { family: string; showRetired: boolean; search: string; set: (p: Partial<ModelsUi>) => void }
const useModelsUi = create<ModelsUi>()((set) => ({ family: 'all', showRetired: false, search: '', set: (p) => set(p) }))

const gb = (n: number | null | undefined) => (n == null ? '—' : `${(n / 2 ** 30).toFixed(2)} GB`)

function ModelsPanel({ tab }: { tab: string }) {
  const s = useSession()
  const ui = useModelsUi()
  if (tab === 'engine') {
    const e = s.engine
    return (
      <div>
        <dl className="kv">
          <dt>state</dt><dd>{!e ? '…' : e.running ? `running (pid ${e.pid}, up ${Math.round(e.uptime_s ?? 0)} s)` : 'stopped'}</dd>
          <dt>responding</dt><dd>{String(e?.responding ?? false)}</dd>
          <dt>ComfyUI</dt><dd>{e?.version?.comfyui_version ?? '—'}</dd>
          <dt>torch</dt><dd>{e?.version?.pytorch_version ?? '—'}</dd>
          <dt>VRAM</dt><dd>{e?.vram_free_gb !== undefined ? `${e.vram_free_gb} / ${e.vram_total_gb} GB free` : '—'}</dd>
          <dt>jobs since start</dt><dd>{e?.jobs_since_start ?? 0} · restarts {e?.restarts ?? 0}</dd>
          <dt>job object</dt><dd>{String(e?.job_object ?? false)}</dd>
          <dt>log</dt><dd>{e?.log ?? '—'}</dd>
          {e?.last_error && <><dt>last error</dt><dd style={{ color: 'var(--error)' }}>{e.last_error}</dd></>}
        </dl>
        <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
          <button onClick={() => void s.engineAction('start')} disabled={e?.running}>Start</button>
          <button onClick={() => void s.engineAction('stop')} disabled={!e?.running}>Stop</button>
          <button onClick={() => void s.engineAction('restart')}>Restart</button>
          <button onClick={() => void s.engineAction('free')} disabled={!e?.running} title="unload models, free VRAM">Free VRAM</button>
        </div>
      </div>
    )
  }
  const families = ['all', ...new Set(s.models.map((m) => m.family))]
  return (
    <div className="form" style={{ gridTemplateColumns: '90px 1fr' }}>
      <label>Family</label>
      <select value={ui.family} onChange={(e) => ui.set({ family: e.target.value })}>{families.map((f) => <option key={f}>{f}</option>)}</select>
      <label>Search</label><input type="text" value={ui.search} onChange={(e) => ui.set({ search: e.target.value })} placeholder="name, repo, role…" />
      <label>Retired</label><input type="checkbox" checked={ui.showRetired} onChange={(e) => ui.set({ showRetired: e.target.checked })} style={{ justifySelf: 'start' }} />
      <span className="hint">Retired entries were struck by a spike and deleted (D30); they can be re-fetched.</span>
      <label>Root</label><span className="mono" style={{ fontSize: 11 }}>{s.settings?.models_root}</span>
      <label>Unlisted</label><span>{s.unlisted.length} file{s.unlisted.length === 1 ? '' : 's'} on disk without a roster entry</span>
    </div>
  )
}

function ModelsStrip() {
  const s = useSession()
  const n = s.models.filter((m) => !m.retired)
  const counts = { verified: n.filter((m) => m.health === 'verified').length, present: n.filter((m) => m.health === 'present').length, missing: n.filter((m) => m.health === 'missing').length }
  return (
    <>
      <span>Roster: {n.length} entries · <span className="badge verified">{counts.verified} verified</span> <span className="badge present">{counts.present} present</span> <span className="badge missing">{counts.missing} missing</span></span>
      <span className="spacer" />
      <button onClick={() => void s.scanModels()}>Rescan disk</button>
    </>
  )
}

function ModelsStage() {
  const s = useSession()
  const ui = useModelsUi()
  const rows = s.models.filter((m) => (ui.showRetired || !m.retired) && (ui.family === 'all' || m.family === ui.family) &&
    (!ui.search || `${m.name} ${m.repo} ${m.role} ${m.id}`.toLowerCase().includes(ui.search.toLowerCase())))
  if (!s.models.length) return <div className="placeholder"><div><h2>No roster loaded</h2>waiting for the orchestrator…</div></div>
  return (
    <table className="grid">
      <thead><tr><th>Model</th><th>Family / role</th><th>Licence</th><th>Size</th><th>Health</th><th></th></tr></thead>
      <tbody>
        {rows.map((m) => {
          const f = s.fetches[m.id]
          const fetching = f && ['queued', 'downloading', 'hashing'].includes(f.status)
          return (
            <tr key={m.id} className={s.selectedModel === m.id ? 'selected' : ''} onClick={() => s.selectModel(m.id)}>
              <td><div>{m.name}</div><div className="mono" style={{ color: 'var(--fg3)', fontSize: 11 }}>{m.id}</div></td>
              <td>{m.family} / {m.role}</td>
              <td>{m.license}{m.variants.includes('open') && <> <span className="badge open">open</span></>}</td>
              <td>{m.size ? gb(m.size) : m.approx_gb ? `≈ ${m.approx_gb} GB` : '—'}</td>
              <td>
                <span className={`badge ${m.health}`}>{m.health}</span>
                {fetching && <> <span className="meter"><i style={{ width: `${Math.round((f.progress ?? 0) * 100)}%` }} /></span> <span className="mono">{gb(f.bytes_done)} · {f.status}</span></>}
                {f?.status === 'failed' && <span style={{ color: 'var(--error)' }}> {f.error}</span>}
              </td>
              <td style={{ whiteSpace: 'nowrap' }}>
                {m.health !== 'present' && m.health !== 'verified' && m.repo && !fetching && <button onClick={(e) => { e.stopPropagation(); void s.fetchModel(m.id) }}>Fetch{m.approx_gb ? ` ${m.approx_gb} GB` : ''}</button>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function ModelsInspector() {
  const s = useSession()
  const m: ModelEntry | undefined = s.models.find((x) => x.id === s.selectedModel)
  const [verify, setVerify] = useState<string | null>(null)
  if (!m) return <span style={{ color: 'var(--fg3)' }}>Select a roster entry.</span>
  return (
    <div>
      <h3 style={{ margin: '0 0 8px' }}>{m.name}</h3>
      <dl className="kv">
        <dt>id</dt><dd className="mono">{m.id}</dd>
        <dt>folder</dt><dd>{m.folder}</dd>
        <dt>family / role</dt><dd>{m.family} / {m.role}</dd>
        <dt>licence</dt><dd>{m.license}</dd>
        <dt>variants</dt><dd>{m.variants.join(', ')}</dd>
        <dt>source</dt><dd className="mono">{m.repo ? `${m.repo} :: ${m.file}` : '—'}</dd>
        <dt>path</dt><dd className="mono">{m.path ?? '—'}</dd>
        <dt>tree</dt><dd className="mono">{m.source_tree ?? '—'}</dd>
        <dt>size</dt><dd>{gb(m.size)}</dd>
        <dt>sha256</dt><dd className="mono">{m.sha256 ?? '— (not in the ledger)'}</dd>
        {m.note && <><dt>note</dt><dd>{m.note}</dd></>}
        {m.retired && <><dt>retired</dt><dd>{m.retired}</dd></>}
      </dl>
      <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
        {m.path && <button onClick={() => void s.verifyModel(m.id).then((r) => setVerify(`${r.sha256.slice(0, 16)}… ${r.matches_ledger === null ? '(no ledger entry)' : r.matches_ledger ? 'matches the ledger' : 'DIFFERS from the ledger'}`))}>Verify sha256</button>}
        {m.path && <button onClick={() => void revealPath(m.path!)}>Reveal</button>}
      </div>
      {verify && <div className="mono" style={{ marginTop: 8 }}>{verify}</div>}
    </div>
  )
}

export const ModelsSuite: SuiteDef = {
  id: 'models', rail: DEFAULT_RAIL.models,
  Panel: ModelsPanel, Strip: ModelsStrip, Stage: ModelsStage, Inspector: ModelsInspector,
}
