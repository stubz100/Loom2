// P14 (D82): the Angle tab — a new viewpoint of one Catalogue image. The five moves are E12's (D77): the rotations run the angles LoRA on
// Qwen-Image-Edit 2509, the framing moves run Klein with a strict-reference prompt; `auto` picks per move and the preview says which
// method runs and how long it took on the rig. Mouse-first (D32): every move is a button on the pad; the source arrives by drop, by the
// Catalogue's "New angle…" or by the loupe's hub.
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, runCommand } from '../../frame/commands'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { angleDrop } from '../../frame/dropRules'
import { useSession } from '../../store/session'
import { MOVES, useGenerate, type AngleMethod } from './generateStore'

/** The Panel's pinned action on the Angle tab: the verb, the missing-weights fetch, the estimate with the method that will run. */
export function AnglePrimary() {
  const g = useGenerate()
  const s = useSession()
  markUsed('gen.angle.generate')
  const pv = g.anglePreview
  const missing = pv?.missing ?? []
  const reason = !s.project?.open ? 'no project' : !g.angle.asset_id ? 'pick a source image' : g.anglePreviewError ? g.anglePreviewError : !pv ? 'preparing…'
    : missing.length ? `weights missing: ${missing.map((m) => m.model_id).join(', ')}` : pv.estimate.vram_fit === 'over' ? 'VRAM estimate exceeds the budget' : null
  return (
    <div>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('gen.angle.generate')} title="Queue the new angle">New angle{g.angle.count > 1 ? ` ×${g.angle.count}` : ''} ▶</button>
      {missing.length > 0 && <div style={{ marginTop: 6 }}><button onClick={() => s.setSuite('models')}>Fetch {missing.reduce((a, m) => a + (m.approx_gb ?? 0), 0).toFixed(0)} GB</button></div>}
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * g.angle.count)} s · {String(pv?.params?.label ?? '')}</>}</div>
    </div>
  )
}

export function AngleTab() {
  const g = useGenerate()
  const a = g.angle
  const caps = useSession((s) => s.capabilities)
  const rc = caps?.reangle
  const pv = g.anglePreview
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && angleDrop(d).ok, (d) => { const id = d.items.find((i) => i.kind === 'asset')?.id; if (id) g.setAngle({ asset_id: id }) }, angleDrop)
  const method = pv?.params?.method as string | undefined
  const methodCap = method && rc ? rc.methods[method] : undefined
  const seconds = pv?.estimate?.seconds ?? methodCap?.seconds ?? null
  return (
    <div className="angle-tab">
      <div ref={dropRef} className={`ref-slot source${over ? ' over' : ''}`} title={a.asset_id ? 'the source image' : 'drop a Catalogue tile here, or use "New angle…" on a tile'}>
        {a.asset_id ? <>
          <img src={api.thumbUrl(a.asset_id, 512)} alt="" />
          <CommandButton id="gen.angle.clear" className="quiet x" size={12} />
        </> : <span className="empty">source</span>}
      </div>
      <div className="angle-pad" role="group" aria-label="Camera move">
        <div className="row"><CommandButton id="gen.angle.topdown" text active={a.move === 'topdown'} /></div>
        <div className="row"><CommandButton id="gen.angle.left45" text active={a.move === 'left45'} /><CommandButton id="gen.angle.right45" text active={a.move === 'right45'} /></div>
        <div className="row"><CommandButton id="gen.angle.closeup" text active={a.move === 'closeup'} /><CommandButton id="gen.angle.wide" text active={a.move === 'wide'} /></div>
      </div>
      <p className="disabled-why">{MOVES.find((m) => m.id === a.move)?.hint}</p>
      <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
        <label>method</label>
        <div>
          <select value={a.method} onChange={(e) => g.setAngle({ method: e.target.value as AngleMethod })}>
            <option value="auto">Auto ({rc ? rc.methods[rc.auto[a.move] ?? '']?.short ?? rc.auto[a.move] : '…'})</option>
            {rc && Object.entries(rc.methods).map(([id, m]) => <option key={id} value={id}>{m.label}{m.seconds ? ` · ≈ ${Math.round(m.seconds)} s` : ''}</option>)}
          </select>
          {methodCap && <span className="disabled-why"> {methodCap.hint ?? methodCap.label}{methodCap.moves.includes(a.move) ? '' : ' — not measured for this move'}</span>}
        </div>
        <label>keep</label>
        <input value={a.prompt_text} onChange={(e) => g.setAngle({ prompt_text: e.target.value })} placeholder="optional: what the scene is, what must stay (one sentence)" />
        <label>candidates</label>
        <div className="angle-count"><button onClick={() => g.setAngle({ count: Math.max(1, a.count - 1) })} disabled={a.count <= 1} title="fewer candidates">−</button><span>{a.count}</span><button onClick={() => g.setAngle({ count: Math.min(4, a.count + 1) })} disabled={a.count >= 4} title="more candidates (up to 4)">+</button></div>
      </div>
      {!a.asset_id && <p className="disabled-why">Pick a source: right-click a Catalogue tile → Start from this image → New angle…, or drop a tile on the slot.</p>}
      {g.anglePreviewError && <p className="disabled-why">{g.anglePreviewError}</p>}
      {pv && pv.missing.length > 0 && <p className="disabled-why">Weights missing for this method: {pv.missing.map((m) => m.model_id).join(', ')} — Models › Fetch.</p>}
      {pv && seconds != null && <p className="disabled-why">{pv.params?.label as string} · ≈ {Math.round(seconds)} s each (measured 2026-10-12)</p>}
    </div>
  )
}
