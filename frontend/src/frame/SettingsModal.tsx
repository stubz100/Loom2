import { KeyboardSettings } from './KeyboardSettings'
import { Help } from './Help'
import { Fragment, useState } from 'react'
import type { Settings } from '../api/types'
import { useSession } from '../store/session'
import { sampleValue } from '../suites/story/styleSamples'
import { ModelCards } from './ModelCards'
import { ROLE_NAMES, STRIP, TRACK_ROLES } from '../suites/story/episode/cut'
import { About } from './About'
import { THEMES, type Theme } from './theme'
import { LISTS, listsInto, type ListField } from './settingsLists'

export function SettingsModal() {
  const s = useSession()
  // the edits; until the first one the draft is the settings as loaded — opened before they arrive (right after a start), the dialog
  // showed nothing and stayed open invisibly (seen in CI, 2026-10-11); now it says so and fills in when they come
  const [edits, setDraft] = useState<Settings | null>(null)
  const draft = edits ?? (s.settings ? structuredClone(s.settings) : null)
  const [busy, setBusy] = useState(false)
  // review K72: the list fields' text as typed — split on blur and on Save, so a trailing `;`, space or `,` (a second tree, a flag, a
  // "Program Files" path) can be typed; re-joined per keystroke it vanished
  const [texts, setTexts] = useState<Partial<Record<ListField, string>>>({})
  if (!draft) return (
    <div className="modal-backdrop" onClick={() => s.openSettings(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}><div className="head">Settings</div><div className="body"><p className="muted">Loading the settings…</p></div></div>
    </div>
  )
  const set = (patch: Partial<Settings>) => setDraft({ ...draft, ...patch })
  const listProps = (f: ListField) => ({ value: texts[f] ?? LISTS[f].join(draft), onChange: (e: React.ChangeEvent<HTMLInputElement>) => setTexts({ ...texts, [f]: e.target.value }),
    onBlur: () => { if (texts[f] === undefined) return; setDraft(listsInto(draft, { [f]: texts[f] })); const rest = { ...texts }; delete rest[f]; setTexts(rest) } })
  const setEngine = (patch: Partial<Settings['engine']>) => setDraft({ ...draft, engine: { ...draft.engine, ...patch } })
  const setAudio = (patch: Partial<Settings['audio']>) => setDraft({ ...draft, audio: { ...draft.audio, ...patch } })
  const save = async () => {
    setBusy(true)
    const d = listsInto(draft, texts)                                         // review K72: what is still being typed counts
    try {
      await s.saveSettings({ models_root: d.models_root, mounted_model_trees: d.mounted_model_trees, vram_budget_gb: d.vram_budget_gb, hf_home: d.hf_home,
        thumbnail_sizes: d.thumbnail_sizes, log_level: d.log_level, samples: d.samples, h3_licence_confirmed: !!d.h3_licence_confirmed, motion: d.motion, audio: d.audio, vsthost: { folders: d.vsthost.folders }, engine: { flags: d.engine.flags, restart_every_jobs: d.engine.restart_every_jobs, port: d.engine.port, health_timeout_s: d.engine.health_timeout_s,
          stall_timeout_s: d.engine.stall_timeout_s, reserve_vram_gb: d.engine.reserve_vram_gb, vram_headroom_gb: d.engine.vram_headroom_gb } })
      s.openSettings(false)
    } finally { setBusy(false) }
  }
  return (
    <div className="modal-backdrop" onClick={() => s.openSettings(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="head">Settings<span className="spacer" /><span className="badge">{draft.variant} variant · read-only (D26)</span></div>
        <div className="body form">
          <h4>Weights</h4>
          <label>Models root <Help text={"ComfyUI layout: diffusion_models/, text_encoders/, vae/, loras/… (D1)"} /></label><input type="text" value={draft.models_root} onChange={(e) => set({ models_root: e.target.value })} />
          <label>Mounted trees <Help text={"Read-only ComfyUI model trees, `;` separated (the D:\\comfyui backup)"} /></label><input type="text" aria-label="mounted trees" {...listProps('trees')} />
          <label>HF_HOME <Help text={"Holds the Hugging Face token used for gated repos"} /></label><input type="text" value={draft.hf_home} onChange={(e) => set({ hf_home: e.target.value })} />
          <h4>Engine</h4>
          <label>VRAM budget (GB)</label><input type="number" min={4} max={64} step={0.5} value={draft.vram_budget_gb} onChange={(e) => set({ vram_budget_gb: Number(e.target.value) })} />
          <label>Engine port</label><input type="number" value={draft.engine.port} onChange={(e) => setEngine({ port: Number(e.target.value) })} />
          <label>Flags <Help text={"E0/E7 defaults: --use-pytorch-cross-attention --disable-pinned-memory --preview-method none; MIOpen stays off"} /></label><input type="text" aria-label="engine flags" {...listProps('flags')} />
          <label>Restart every N jobs <Help text={"0 = never (HIP launch-failure mitigation, 06 §10)"} /></label><input type="number" min={0} value={draft.engine.restart_every_jobs} onChange={(e) => setEngine({ restart_every_jobs: Number(e.target.value) })} />
          <label>Health timeout (s)</label><input type="number" min={10} value={draft.engine.health_timeout_s} onChange={(e) => setEngine({ health_timeout_s: Number(e.target.value) })} />
          <label>Stall timeout (s) <Help text={"No engine event for this long while a job runs → the job fails, the engine restarts, the queue pauses (TDR watchdog, 06 §10)"} /></label><input type="number" min={60} value={draft.engine.stall_timeout_s ?? 420} onChange={(e) => setEngine({ stall_timeout_s: Number(e.target.value) })} />
          <label>Reserve VRAM (GB) <Help text={"ComfyUI --reserve-vram: headroom for the desktop and the editor's WebGPU canvas"} /></label><input type="number" min={0} max={8} step={0.5} value={draft.engine.reserve_vram_gb ?? 1.5} onChange={(e) => setEngine({ reserve_vram_gb: Number(e.target.value) })} />
          <label>Job headroom (GB) <Help text={"ComfyUI --vram-headroom: VRAM kept free for a job's activations so they never spill to shared memory (FLUX.2 dev with references ran 4× slower without it)"} /></label><input type="number" min={0} max={10} step={0.5} value={draft.engine.vram_headroom_gb ?? 5} onChange={(e) => setEngine({ vram_headroom_gb: Number(e.target.value) })} />
          <h4>App <Help text={"The pen pressure curve appears when a pen is detected (D19). Project format defaults arrive with their suites."} /></h4>
          <label>Theme <Help text={"Applies at once and is remembered on this machine, like the density"} /></label>
          <select value={s.ui.theme} onChange={(e) => s.setUi({ theme: e.target.value as Theme })}>{THEMES.map(([t, l]) => <option key={t} value={t}>{l}</option>)}</select>
          <label>Density</label>
          <select value={s.ui.density} onChange={(e) => s.setUi({ density: e.target.value as 'comfortable' | 'compact' })}><option value="comfortable">comfortable</option><option value="compact">compact</option></select>
          <h4>Engine output</h4>
          <label>Thumbnail sizes</label><input type="text" aria-label="thumbnail sizes" {...listProps('thumbs')} />
          <label>Log level</label>
          <select value={draft.log_level} onChange={(e) => set({ log_level: e.target.value })}>{['DEBUG', 'INFO', 'WARNING', 'ERROR'].map((l) => <option key={l}>{l}</option>)}</select>
          <h4 id="settings-samples">Samples</h4>
          {/* D90 (02 §4.1, §6.3): the scenes the style samples and the look-preset icons are rendered on; blank = the default again */}
          <label>Sample model <Help text={"The model \"Make a sample image\" and the look-preset icons render on (D91) — a small, quick one is enough to show a look; one this build does not offer falls back to the default"} /></label>
          {/* D186: the one card — the sample models, the default first; the default picked clears the setting */}
          <ModelCards label="sample model" testId="settings-sample-models" time
            items={(s.capabilities?.sample_models ?? []).map((m) => ({ id: m.id, label: m.default ? `${m.label} · default` : m.label, license: m.license, health: m.health, seconds: m.seconds }))}
            value={sampleValue(draft.samples.model_id, s.capabilities?.sample_models) || s.capabilities?.sample_models?.find((m) => m.default)?.id}
            onPick={(id) => set({ samples: { ...draft.samples, model_id: s.capabilities?.sample_models?.find((m) => m.id === id)?.default ? null : id } })} />
          <label>Style sample <Help text={"The scene every style is rendered on by \"Make a sample image\" — its fragment is appended; the same scene for every style keeps the samples comparable"} /></label>
          <textarea rows={2} aria-label="style sample prompt" value={draft.samples.style_prompt} onChange={(e) => set({ samples: { ...draft.samples, style_prompt: e.target.value } })} />
          {Object.entries(draft.samples.swatch_prompts).map(([field, t]) => (
            <Fragment key={field}>
              <label>Icon · {field}</label>
              <input type="text" aria-label={`${field} icon scene`} value={t} onChange={(e) => set({ samples: { ...draft.samples, swatch_prompts: { ...draft.samples.swatch_prompts, [field]: e.target.value } } })} />
            </Fragment>
          ))}
          <span className="hint">Icon scenes <Help text={`The scenes of Image's look-preset icons; {value} is the preset (added at the end when left out). Clear a field and Save to get its default back. Existing samples and icons stay — remake one from its right-click menu.`} /></span>
          <h4 id="settings-motion">Motion</h4>
          {/* CA1 (proto01_animate 02 §5): the motion library's folders — the CC0 starter set ships; the local folder is the author's own */}
          <label>Local motion folder <Help text={"Your own downloads (Mixamo FBX at 24 fps, without skin; glb / gltf) — listed in Clay's motion library's Motion library, never bundled or copied; Adobe's terms keep Mixamo clips out of anything that trains or tests AI"} /></label>
          <input type="text" aria-label="local motion folder" value={draft.motion.local_dir} placeholder="e.g. F:/loom2-motion-mixamo" onChange={(e) => set({ motion: { ...draft.motion, local_dir: e.target.value } })} />
          <label>Starter set folder <Help text={"The CC0 clips that ship with loom2 (Quaternius' Universal Animation Library 1 and 2)"} /></label>
          <input type="text" aria-label="starter motion folder" value={draft.motion.starter_dir} placeholder="blank = <models root>/motion" onChange={(e) => set({ motion: { ...draft.motion, starter_dir: e.target.value } })} />
          <h4 id="settings-audio">Audio</h4>
          {/* D127 (proto01_animate 30 §16): the loudness the movie and the Episode's mix are brought to, and each track role's strip */}
          <label>Loudness target <Help text={"The movie and the Episode's mix are brought to this integrated loudness (ITU-R BS.1770): −16 LUFS for online delivery, −23 for EBU R128 broadcast; \"as mixed\" leaves the mix alone"} /></label>
          <div className="row strip-row">
            <input type="number" aria-label="loudness target" min={-36} max={-6} step={0.5} disabled={draft.audio.loudness_lufs === null} value={draft.audio.loudness_lufs ?? -16}
              onChange={(e) => setAudio({ loudness_lufs: Number(e.target.value) })} /><span>LUFS</span><span className="spacer" />
            <label className="chk"><input type="checkbox" checked={draft.audio.loudness_lufs === null} onChange={(e) => setAudio({ loudness_lufs: e.target.checked ? null : -16 })} /> as mixed</label>
          </div>
          {TRACK_ROLES.map((role) => (
            <Fragment key={role}>
              <label>{ROLE_NAMES[role]} track {role === 'dialogue' && <Help text={"A new cut's A1, A2 and A3 are the dialogue, music and effects tracks with these settings; a track's right-click › Role sets them on any audio track. Gain −36…+36 dB (before the track's effects), volume −96 (silent)…+18 dB, pan −100 (100 % left)…0 (50 / 50)…+100 (100 % right), width 0 (mono)…100 (as recorded)…200 % (wider)"} />}</label>
              <div className="row strip-row">
                {(['gain_db', 'volume_db', 'pan', 'width'] as const).map((k) => (
                  <label key={k}><span>{k === 'gain_db' ? 'gain' : k === 'volume_db' ? 'volume' : k}</span>
                    <input type="number" aria-label={`${role} ${k.replace('_db', '')}`} min={STRIP[k][0]} max={STRIP[k][1]} step={k === 'pan' || k === 'width' ? 5 : 0.5} value={draft.audio[role][k]}
                      onChange={(e) => setAudio({ [role]: { ...draft.audio[role], [k]: Number(e.target.value) } })} /></label>
                ))}
              </div>
            </Fragment>
          ))}
          <label>VST3 folders <Help text={"Your own folders of VST3 effects, `;` separated, beside the system's (C:\\Program Files\\Common Files\\VST3) — loom2's own host scans them once and again when a bundle changes"} /></label>
          <input type="text" aria-label="VST3 folders" placeholder="none — the system's folder only" {...listProps('vst')} />
          <h4 id="settings-keyboard">Keyboard</h4>
          <KeyboardSettings />
          <h4>Licences</h4>
          <label>MiniMax H3 <Help text={"H3's community licence excludes the EU; MiniMax answered that an individual without income from it needs no authorization (D192). Ticked, the H3 card appears in Image to video's models (D193). Should you earn from it or work through an organisation, the licence is read again."} /></label><label className="chk"><input type="checkbox" checked={!!draft.h3_licence_confirmed} onChange={(e) => set({ h3_licence_confirmed: e.target.checked })} /> I use H3 as an individual without income from it — MiniMax's answer (D192)</label>
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
