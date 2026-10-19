import { KeyboardSettings } from './KeyboardSettings'
import { Fragment, useState } from 'react'
import type { Settings } from '../api/types'
import { useSession } from '../store/session'
import { sampleOptions, sampleValue } from '../suites/story/styleSamples'
import { About } from './About'
import { THEMES, type Theme } from './theme'

export function SettingsModal() {
  const s = useSession()
  // the edits; until the first one the draft is the settings as loaded — opened before they arrive (right after a start), the dialog
  // showed nothing and stayed open invisibly (seen in CI, 2026-10-11); now it says so and fills in when they come
  const [edits, setDraft] = useState<Settings | null>(null)
  const draft = edits ?? (s.settings ? structuredClone(s.settings) : null)
  const [busy, setBusy] = useState(false)
  if (!draft) return (
    <div className="modal-backdrop" onClick={() => s.openSettings(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}><div className="head">Settings</div><div className="body"><p className="muted">Loading the settings…</p></div></div>
    </div>
  )
  const set = (patch: Partial<Settings>) => setDraft({ ...draft, ...patch })
  const setEngine = (patch: Partial<Settings['engine']>) => setDraft({ ...draft, engine: { ...draft.engine, ...patch } })
  const save = async () => {
    setBusy(true)
    try {
      await s.saveSettings({ models_root: draft.models_root, mounted_model_trees: draft.mounted_model_trees, vram_budget_gb: draft.vram_budget_gb, hf_home: draft.hf_home,
        thumbnail_sizes: draft.thumbnail_sizes, log_level: draft.log_level, samples: draft.samples, motion: draft.motion, engine: { flags: draft.engine.flags, restart_every_jobs: draft.engine.restart_every_jobs, port: draft.engine.port, health_timeout_s: draft.engine.health_timeout_s,
          stall_timeout_s: draft.engine.stall_timeout_s, reserve_vram_gb: draft.engine.reserve_vram_gb, vram_headroom_gb: draft.engine.vram_headroom_gb } })
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
          <label>Job headroom (GB)</label><input type="number" min={0} max={10} step={0.5} value={draft.engine.vram_headroom_gb ?? 5} onChange={(e) => setEngine({ vram_headroom_gb: Number(e.target.value) })} />
          <span className="hint">ComfyUI --vram-headroom: VRAM kept free for a job's activations so they never spill to shared memory (FLUX.2 dev with references ran 4× slower without it)</span>
          <h4>App</h4>
          <label>Theme</label>
          <select value={s.ui.theme} onChange={(e) => s.setUi({ theme: e.target.value as Theme })}>{THEMES.map(([t, l]) => <option key={t} value={t}>{l}</option>)}</select>
          <span className="hint">applies at once and is remembered on this machine, like the density</span>
          <label>Density</label>
          <select value={s.ui.density} onChange={(e) => s.setUi({ density: e.target.value as 'comfortable' | 'compact' })}><option value="comfortable">comfortable</option><option value="compact">compact</option></select>
          <label>Keep Edit / Animate loaded</label>
          <select value={s.ui.editKeepAliveMin ?? 10} onChange={(e) => s.setUi({ editKeepAliveMin: Number(e.target.value) })}>{[2, 5, 10, 30, 60].map((m) => <option key={m} value={m}>{m} min after you leave</option>)}</select>
          <span className="hint">switching back is instant while loaded (D69); a GPU job short of VRAM releases them at once</span>
          <h4>Catalogue</h4>
          <label>Thumbnails</label>
          <select value={s.ui.thumbFit} onChange={(e) => s.setUi({ thumbFit: e.target.value as 'fit' | 'fill' })}><option value="fit">fit: the whole picture</option><option value="fill">fill: cropped to the tile</option></select>
          <label>Tile caption</label>
          <select value={s.ui.caption} onChange={(e) => s.setUi({ caption: e.target.value as 'off' | 'prompt' | 'model' })}><option value="off">off</option><option value="prompt">prompt</option><option value="model">model · seed</option></select>
          <span className="hint">the tooltip and the Inspector always show model, seed, size and time</span>
          <h4>Engine output</h4>
          <label>Thumbnail sizes</label><input type="text" value={draft.thumbnail_sizes.join(',')} onChange={(e) => set({ thumbnail_sizes: e.target.value.split(',').map(Number).filter(Boolean) })} />
          <label>Log level</label>
          <select value={draft.log_level} onChange={(e) => set({ log_level: e.target.value })}>{['DEBUG', 'INFO', 'WARNING', 'ERROR'].map((l) => <option key={l}>{l}</option>)}</select>
          <span className="hint">Pen pressure curve appears when a pen is detected (D19). Project format defaults arrive with their suites.</span>
          <h4 id="settings-samples">Samples</h4>
          {/* D90 (02 §4.1, §6.3): the scenes the style samples and the look-preset icons are rendered on; blank = the default again */}
          <label>Sample model</label>
          <select aria-label="sample model" value={sampleValue(draft.samples.model_id, s.capabilities?.sample_models)} onChange={(e) => set({ samples: { ...draft.samples, model_id: e.target.value || null } })}>
            {sampleOptions(s.capabilities?.sample_models).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <span className="hint">the model "Make a sample image" and the look-preset icons render on (D91) — a small, quick one is enough to show a look; one this build does not offer falls back to the default</span>
          <label>Style sample</label>
          <textarea rows={2} aria-label="style sample prompt" value={draft.samples.style_prompt} onChange={(e) => set({ samples: { ...draft.samples, style_prompt: e.target.value } })} />
          <span className="hint">the scene every style is rendered on by "Make a sample image" — its fragment is appended; the same scene for every style keeps the samples comparable</span>
          {Object.entries(draft.samples.swatch_prompts).map(([field, t]) => (
            <Fragment key={field}>
              <label>Icon · {field}</label>
              <input type="text" aria-label={`${field} icon scene`} value={t} onChange={(e) => set({ samples: { ...draft.samples, swatch_prompts: { ...draft.samples.swatch_prompts, [field]: e.target.value } } })} />
            </Fragment>
          ))}
          <span className="hint">the scenes of Image's look-preset icons; {'{value}'} is the preset (added at the end when left out). Clear a field and Save to get its default back. Existing samples and icons stay — remake one from its right-click menu.</span>
          <h4 id="settings-motion">Motion</h4>
          {/* CA1 (proto01_animate 02 §5): the motion library's folders — the CC0 starter set ships; the local folder is the author's own */}
          <label>Local motion folder</label>
          <input type="text" aria-label="local motion folder" value={draft.motion.local_dir} placeholder="e.g. F:/loom2-motion-mixamo" onChange={(e) => set({ motion: { ...draft.motion, local_dir: e.target.value } })} />
          <span className="hint">your own downloads (Mixamo FBX at 24 fps, without skin; glb / gltf) — listed in Animate's Motion library, never bundled or copied; Adobe's terms keep Mixamo clips out of anything that trains or tests AI</span>
          <label>Starter set folder</label>
          <input type="text" aria-label="starter motion folder" value={draft.motion.starter_dir} placeholder="blank = <models root>/motion" onChange={(e) => set({ motion: { ...draft.motion, starter_dir: e.target.value } })} />
          <span className="hint">the CC0 clips that ship with loom2 (Quaternius' Universal Animation Library 1 and 2)</span>
          <h4 id="settings-keyboard">Keyboard</h4>
          <KeyboardSettings />
          <h4>Licences</h4>
          <label>MiniMax H3</label><label className="chk"><input type="checkbox" checked={!!draft.h3_licence_confirmed} onChange={(e) => set({ h3_licence_confirmed: e.target.checked })} /> the EU community-licence application is filed (D17)</label>
          <span className="hint">Records the confirmation that unlocks the H3 hero tier in Animate once its graph and weights land (04 §5b). Licence checks are read against EU terms.</span>
          <h4>About</h4>
          <About />
        </div>
        <div className="foot">
          <button onClick={() => s.openSettings(false)}>Cancel</button>
          <button className="primary" disabled={busy} onClick={() => void save()}>Save</button>
        </div>
      </div>
    </div>
  )
}
