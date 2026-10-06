import { useState } from 'react'
import type { Settings } from '../api/types'
import { useSession } from '../store/session'

export function SettingsModal() {
  const s = useSession()
  const [draft, setDraft] = useState<Settings | null>(s.settings ? structuredClone(s.settings) : null)
  const [busy, setBusy] = useState(false)
  if (!draft) return null
  const set = (patch: Partial<Settings>) => setDraft({ ...draft, ...patch })
  const setEngine = (patch: Partial<Settings['engine']>) => setDraft({ ...draft, engine: { ...draft.engine, ...patch } })
  const save = async () => {
    setBusy(true)
    try {
      await s.saveSettings({ models_root: draft.models_root, mounted_model_trees: draft.mounted_model_trees, vram_budget_gb: draft.vram_budget_gb, hf_home: draft.hf_home,
        thumbnail_sizes: draft.thumbnail_sizes, log_level: draft.log_level, engine: { flags: draft.engine.flags, restart_every_jobs: draft.engine.restart_every_jobs, port: draft.engine.port, health_timeout_s: draft.engine.health_timeout_s,
          stall_timeout_s: draft.engine.stall_timeout_s, reserve_vram_gb: draft.engine.reserve_vram_gb } })
      s.openSettings(false)
    } finally { setBusy(false) }
  }
  return (
    <div className="modal-backdrop" onClick={() => s.openSettings(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="head">Settings<span className="spacer" /><span className="badge">{draft.variant} variant · read-only (D26)</span></div>
        <div className="body form">
          <h4>Weights</h4>
          <label>Models root</label><input type="text" value={draft.models_root} onChange={(e) => set({ models_root: e.target.value })} />
          <span className="hint">ComfyUI layout: diffusion_models/, text_encoders/, vae/, loras/… (D1)</span>
          <label>Mounted trees</label><input type="text" value={draft.mounted_model_trees.join(';')} onChange={(e) => set({ mounted_model_trees: e.target.value.split(';').map((x) => x.trim()).filter(Boolean) })} />
          <span className="hint">read-only ComfyUI model trees, `;` separated (the D:\comfyui backup)</span>
          <label>HF_HOME</label><input type="text" value={draft.hf_home} onChange={(e) => set({ hf_home: e.target.value })} />
          <span className="hint">holds the Hugging Face token used for gated repos</span>
          <h4>Engine</h4>
          <label>VRAM budget (GB)</label><input type="number" min={4} max={64} step={0.5} value={draft.vram_budget_gb} onChange={(e) => set({ vram_budget_gb: Number(e.target.value) })} />
          <label>Engine port</label><input type="number" value={draft.engine.port} onChange={(e) => setEngine({ port: Number(e.target.value) })} />
          <label>Flags</label><input type="text" value={draft.engine.flags.join(' ')} onChange={(e) => setEngine({ flags: e.target.value.split(/\s+/).filter(Boolean) })} />
          <span className="hint">E0/E7 defaults: --use-pytorch-cross-attention --disable-pinned-memory --preview-method none; MIOpen stays off</span>
          <label>Restart every N jobs</label><input type="number" min={0} value={draft.engine.restart_every_jobs} onChange={(e) => setEngine({ restart_every_jobs: Number(e.target.value) })} />
          <span className="hint">0 = never (HIP launch-failure mitigation, 06 §10)</span>
          <label>Health timeout (s)</label><input type="number" min={10} value={draft.engine.health_timeout_s} onChange={(e) => setEngine({ health_timeout_s: Number(e.target.value) })} />
          <label>Stall timeout (s)</label><input type="number" min={60} value={draft.engine.stall_timeout_s ?? 420} onChange={(e) => setEngine({ stall_timeout_s: Number(e.target.value) })} />
          <span className="hint">no engine event for this long while a job runs → the job fails, the engine restarts, the queue pauses (TDR watchdog, 06 §10)</span>
          <label>Reserve VRAM (GB)</label><input type="number" min={0} max={8} step={0.5} value={draft.engine.reserve_vram_gb ?? 1.5} onChange={(e) => setEngine({ reserve_vram_gb: Number(e.target.value) })} />
          <span className="hint">ComfyUI --reserve-vram: headroom for the desktop and the editor's WebGPU canvas</span>
          <h4>App</h4>
          <h4>Licences</h4>
          <label>MiniMax H3</label><label className="chk"><input type="checkbox" checked={!!draft.h3_licence_confirmed} onChange={(e) => set({ h3_licence_confirmed: e.target.checked })} /> the EU community-licence application is filed (D17)</label>
          <span className="hint">Records the confirmation that unlocks the H3 hero tier in Animate once its graph and weights land (04 §5b). Licence checks are read against EU terms.</span>
          <label>Thumbnail sizes</label><input type="text" value={draft.thumbnail_sizes.join(',')} onChange={(e) => set({ thumbnail_sizes: e.target.value.split(',').map(Number).filter(Boolean) })} />
          <label>Log level</label>
          <select value={draft.log_level} onChange={(e) => set({ log_level: e.target.value })}>{['DEBUG', 'INFO', 'WARNING', 'ERROR'].map((l) => <option key={l}>{l}</option>)}</select>
          <label>Density</label>
          <select value={s.ui.density} onChange={(e) => s.setUi({ density: e.target.value as 'comfortable' | 'compact' })}><option value="comfortable">comfortable</option><option value="compact">compact</option></select>
          <span className="hint">Pen pressure curve appears when a pen is detected (D19). Licence confirmations (D17) and project format defaults arrive with their suites.</span>
        </div>
        <div className="foot">
          <button onClick={() => s.openSettings(false)}>Cancel</button>
          <button className="primary" disabled={busy} onClick={() => void save()}>Save</button>
        </div>
      </div>
    </div>
  )
}
