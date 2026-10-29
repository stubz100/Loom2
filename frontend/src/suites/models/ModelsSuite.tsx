import { useEffect } from 'react'
import type { ModelEntry } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, runCommand, titleFor, command } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { useSession } from '../../store/session'
import { rowMenu, useModelsUi } from './modelsCommands'   // D90 (01 §11.2): the sheet's actions are commands

const gb = (n: number | null | undefined) => (n == null ? '—' : `${(n / 2 ** 30).toFixed(2)} GB`)

import { TrainedTable } from './TrainedTable'

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
          <CommandButton id="models.engine.start" text label="Start" /><CommandButton id="models.engine.stop" text label="Stop" /><CommandButton id="models.engine.restart" text label="Restart" /><CommandButton id="models.engine.free" text />
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
      <label>Missing</label><label className="chk" style={{ justifySelf: 'start' }}><input type="checkbox" checked={ui.missingOnly} onChange={(e) => ui.set({ missingOnly: e.target.checked })} /> only the missing weights</label>
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
      {counts.missing > 0 && <CommandButton id="models.fetchAll" text />}
      <CommandButton id="models.rescan" text />
    </>
  )
}

function ModelsStage() {
  const s = useSession()
  const ui = useModelsUi()
  const rows = s.models.filter((m) => (ui.showRetired || !m.retired) && (!ui.missingOnly || m.health === 'missing') && (ui.family === 'all' || m.family === ui.family) &&
    (!ui.search || `${m.name} ${m.repo} ${m.role} ${m.id}`.toLowerCase().includes(ui.search.toLowerCase())))
  if (!s.models.length) return <div className="placeholder"><div><h2>No roster loaded</h2>waiting for the orchestrator…</div></div>
  const fetchCmd = command('models.fetch'); markUsed('models.fetch')                // each row's Fetch runs the command on that row
  return (
    <div>
    <table className="grid">
      <thead><tr><th>Model</th><th>Family / role</th><th>Licence</th><th>Size</th><th>Health</th><th></th></tr></thead>
      <tbody>
        {rows.map((m) => {
          const f = s.fetches[m.id]
          const fetching = f && ['queued', 'downloading', 'hashing'].includes(f.status)
          return (
            <tr key={m.id} className={s.selectedModel === m.id ? 'selected' : ''} data-id={m.id} onClick={() => s.selectModel(m.id)} onContextMenu={(e) => { s.selectModel(m.id); showMenu(e, rowMenu()) }}>
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
                {m.health !== 'present' && m.health !== 'verified' && m.repo && !fetching && <button title={fetchCmd ? titleFor(fetchCmd, `Fetch ${m.name}`) : undefined} onClick={(e) => { e.stopPropagation(); s.selectModel(m.id); runCommand('models.fetch') }}>Fetch{m.approx_gb ? ` ${m.approx_gb} GB` : ''}</button>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
    <TrainedTable />
    </div>
  )
}

function ModelsInspector() {
  const s = useSession()
  const m: ModelEntry | undefined = s.models.find((x) => x.id === s.selectedModel)
  const verify = useModelsUi((u) => (u.verify?.id === s.selectedModel ? u.verify.text : null))
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
        {m.path ? <><CommandButton id="models.verify" text /><CommandButton id="models.reveal" text /></> : <CommandButton id="models.fetch" text />}
      </div>
      {verify && <div className="mono" style={{ marginTop: 8 }}>{verify}</div>}
    </div>
  )
}

/** D90 (02 §7): Models & engine as a sheet over the frame — the roster (filters, table, the selected entry) or the engine. */
export function ModelsSheetBody({ tab, missing }: { tab: 'roster' | 'engine'; missing: boolean }) {
  const set = useModelsUi((u) => u.set)
  useEffect(() => { set({ missingOnly: missing }) }, [missing, set])
  if (tab === 'engine') return <div className="models-sheet-engine"><ModelsPanel tab="engine" /></div>
  return (
    <div className="models-sheet-grid">
      <aside><ModelsPanel tab="roster" /></aside>
      <section><div className="strip">{<ModelsStrip />}</div><div className="models-sheet-table"><ModelsStage /></div></section>
      <aside><ModelsInspector /></aside>
    </div>
  )
}
