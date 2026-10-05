// Generate suite (09): Prompt (tree / JSON / text with the exact serialisation preview), Model, Size & Batch,
// References, Presets; results on the Catalogue grid filtered to this suite; interim tiles with live previews.
import { Boxes, Bookmark, Images, SlidersHorizontal, Wand2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { handleKeyFor, markUsed, registerCommands, runCommand, sep } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import { CatalogueStoreCtx } from '../catalogue/catalogueContext'
import { useGenerateResults } from '../catalogue/catalogueStore'
import { Inspector as CatInspector, Stage as CatStage, Strip as CatStrip } from '../catalogue/CatalogueSuite'
import { useGenerate, type Panel as PanelState, type Subject } from './generateStore'
import './generate.css'

const ANGLES = ['eye level', 'low angle', 'high angle', 'bird\'s eye', 'worm\'s eye', 'dutch tilt', 'over the shoulder', 'three-quarter left', 'three-quarter right', 'profile', 'from behind']
const SHOTS = ['extreme close-up', 'close-up', 'medium close-up', 'medium shot', 'medium long shot', 'full shot', 'wide shot', 'establishing shot']
const POSES = ['standing', 'sitting', 'crouching', 'walking', 'running', 'leaning', 'turning back over the shoulder', 'arms crossed', 'reaching out', 'kneeling']
const LIGHTS = ['golden hour rim light', 'soft overcast', 'hard noon sun', 'neon rim light', 'single candle', 'moonlight', 'window light', 'firelight', 'studio key + fill', 'backlit silhouette']
const LENSES = ['24mm', '35mm', '50mm', '85mm', '135mm', 'anamorphic']
const ASPECTS: [string, number, number][] = [['16:9', 16, 9], ['1:1', 1, 1], ['3:2', 3, 2], ['2:3', 2, 3], ['9:16', 9, 16], ['21:9', 21, 9]]

const snap16 = (n: number) => Math.max(64, Math.round(n / 16) * 16)

function Chips({ items, onPick }: { items: string[]; onPick: (v: string) => void }) {
  return <div className="chip-row">{items.map((x) => <button key={x} type="button" onClick={() => onPick(x)}>{x}</button>)}</div>
}

// ------------------------------------------------------------------ Prompt
function PromptTab() {
  const g = useGenerate()
  const p = g.panel
  const t = p.tree
  const pv = g.preview
  const cap = useSession((s) => s.capabilities?.models[p.model_id])
  const wc = pv?.word_count ?? 0
  const counterClass = wc === 0 ? '' : wc >= 30 && wc <= 80 ? 'ok' : wc > 120 ? 'warn' : ''
  const append = (cur: string | undefined, v: string) => (cur ? `${cur}, ${v}` : v)
  return (
    <div>
      <div className="segmented" style={{ marginBottom: 10 }}>
        {(['tree', 'json', 'text'] as const).map((m) => <button key={m} className={p.prompt_mode === m ? 'active' : ''} onClick={() => { if (m === 'json' && p.prompt_mode === 'tree') g.treeToJson(); else g.set({ prompt_mode: m }) }}>{m === 'tree' ? 'Tree' : m === 'json' ? 'JSON' : 'Text'}</button>)}
        <span className={`counter ${counterClass}`} style={{ padding: '4px 8px' }}>{wc} words · ≈{pv?.token_estimate ?? 0} tokens {wc > 120 ? '· over the 512-token comfort zone' : wc && (wc < 30 || wc > 80) ? '· ideal 30–80' : ''}</span>
      </div>
      {p.prompt_mode === 'tree' && (
        <div className="gen-form">
          <label>scene</label><textarea value={t.scene ?? ''} onChange={(e) => g.setTree({ scene: e.target.value })} placeholder="overall scene description" />
          {(t.subjects ?? []).map((s, i) => (
            <div className="subject" key={i}>
              <div className="head"><b>subject {i + 1}</b><span className="spacer" />{(t.subjects?.length ?? 0) > 1 && <button className="quiet" onClick={() => g.removeSubject(i)}>remove</button>}</div>
              <label>description</label><textarea value={s.description} onChange={(e) => g.setSubject(i, { description: e.target.value })} placeholder='who/what; literal text in quotes; bind colours here ("a #F2A93B brass compass")' />
              <label>position</label><div><input type="text" value={s.position ?? ''} onChange={(e) => g.setSubject(i, { position: e.target.value })} placeholder="where in frame" /><Chips items={['left third', 'centre', 'right third', 'foreground', 'background', 'waist-up']} onPick={(v) => g.setSubject(i, { position: append(s.position, v) })} /></div>
              <label>action</label><input type="text" value={s.action ?? ''} onChange={(e) => g.setSubject(i, { action: e.target.value })} />
              <label>pose</label><div><input type="text" value={s.pose ?? ''} onChange={(e) => g.setSubject(i, { pose: e.target.value })} /><Chips items={POSES} onPick={(v) => g.setSubject(i, { pose: append(s.pose, v) })} /></div>
              <label>color_match</label><select value={s.color_match ?? 'exact'} onChange={(e) => g.setSubject(i, { color_match: e.target.value })}><option value="exact">exact</option><option value="approximate">approximate</option><option value="">—</option></select>
            </div>
          ))}
          <div className="full"><button onClick={g.addSubject}>+ subject</button></div>
          <label>style</label><input type="text" value={t.style ?? ''} onChange={(e) => g.setTree({ style: e.target.value })} placeholder="artistic style" />
          <label>color_palette</label>
          <div className="swatches">
            {(t.color_palette ?? []).map((c, i) => <span key={i} className="swatch" style={{ background: c }} title={c}><input type="color" value={/^#[0-9a-f]{6}$/i.test(c) ? c : '#888888'} onChange={(e) => { const pal = [...(t.color_palette ?? [])]; pal[i] = e.target.value.toUpperCase(); g.setTree({ color_palette: pal }) }} /><i onClick={() => g.setTree({ color_palette: (t.color_palette ?? []).filter((_, j) => j !== i) })}>×</i></span>)}
            <button onClick={() => g.setTree({ color_palette: [...(t.color_palette ?? []), '#F2A93B'] })}>+</button>
          </div>
          <span className="hint">bind colours to objects in the subject descriptions; the palette alone is weak</span>
          <label>lighting</label><div><input type="text" value={t.lighting ?? ''} onChange={(e) => g.setTree({ lighting: e.target.value })} /><Chips items={LIGHTS} onPick={(v) => g.setTree({ lighting: append(t.lighting, v) })} /></div>
          <label>mood</label><input type="text" value={t.mood ?? ''} onChange={(e) => g.setTree({ mood: e.target.value })} />
          <label>background</label><input type="text" value={t.background ?? ''} onChange={(e) => g.setTree({ background: e.target.value })} />
          <label>composition</label><input type="text" value={t.composition ?? ''} onChange={(e) => g.setTree({ composition: e.target.value })} />
          <label>camera</label>
          <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
            <label>angle</label><div><input type="text" value={t.camera?.angle ?? ''} onChange={(e) => g.setCamera({ angle: e.target.value })} /><Chips items={ANGLES} onPick={(v) => g.setCamera({ angle: append(t.camera?.angle, v) })} /></div>
            <label>lens</label><div><input type="text" value={t.camera?.lens ?? ''} onChange={(e) => g.setCamera({ lens: e.target.value })} /><Chips items={LENSES} onPick={(v) => g.setCamera({ lens: v })} /></div>
            <label>depth of field</label><input type="text" value={t.camera?.depth_of_field ?? ''} onChange={(e) => g.setCamera({ depth_of_field: e.target.value })} />
            <label>f-number</label><input type="text" value={t.camera?.['f-number'] ?? ''} onChange={(e) => g.setCamera({ 'f-number': e.target.value })} />
            <label>distance</label><div><input type="text" value={t.camera?.distance ?? ''} onChange={(e) => g.setCamera({ distance: e.target.value })} /><Chips items={SHOTS} onPick={(v) => g.setCamera({ distance: v })} /></div>
          </div>
          <label>lead text</label><input type="text" value={p.text} onChange={(e) => g.set({ text: e.target.value })} placeholder="optional sentence prepended for Klein (prose mode)" />
        </div>
      )}
      {p.prompt_mode === 'json' && (
        <div>
          <textarea value={p.json_text} onChange={(e) => g.set({ json_text: e.target.value })} rows={16} style={{ width: '100%', font: 'var(--mono)' }} spellCheck={false} />
          <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
            <button onClick={() => g.jsonToTree()}>to Tree</button>
            <button onClick={() => { try { g.set({ json_text: JSON.stringify(JSON.parse(p.json_text || '{}'), null, 2) }) } catch { /* keep */ } }}>pretty</button>
            <button onClick={() => { try { g.set({ json_text: JSON.stringify(JSON.parse(p.json_text || '{}')) }) } catch { /* keep */ } }}>compact</button>
            <button onClick={() => void navigator.clipboard?.readText().then((x) => { try { JSON.parse(x); g.set({ json_text: x }) } catch { useSession.getState().toast('Clipboard is not JSON', 'error') } })}>import clipboard</button>
          </div>
          {g.previewError && <div style={{ color: 'var(--error)', fontSize: 12, marginTop: 6 }}>{g.previewError}</div>}
        </div>
      )}
      {p.prompt_mode === 'text' && <textarea value={p.text} onChange={(e) => g.set({ text: e.target.value })} rows={8} style={{ width: '100%' }} placeholder="plain prompt" />}
      {cap && !cap.distilled ? (
        <div className="gen-form" style={{ marginTop: 10 }}><label>negative</label><input type="text" value={p.negative} onChange={(e) => g.set({ negative: e.target.value })} placeholder="CFG-capable variant: negatives are honoured" /></div>
      ) : <div className="disabled-why" style={{ marginTop: 8 }}>negative prompt hidden: {cap?.distilled ? 'distilled variants ignore negatives (CFG 1)' : 'dev runs guidance-distilled without CFG'}</div>}
      <details open style={{ marginTop: 10 }}>
        <summary style={{ color: 'var(--fg2)', cursor: 'pointer' }}>Serialisation preview · {pv?.prompt_mode ?? '…'} {pv ? `(${pv.prompt_mode === 'json' ? 'raw JSON inside the Mistral template' : pv.prompt_mode === 'prose' ? 'flattened prose for Klein' : 'plain text'})` : ''}</summary>
        <div className="preview-box">{pv?.serialized_prompt || (g.previewing ? '…' : '(empty prompt)')}</div>
      </details>
      <div style={{ marginTop: 8 }}><button disabled title="queues an LLM pass with BFL's upsampling prompt — optional in M3, not wired yet">Upsample ✨ (later)</button></div>
    </div>
  )
}

// ------------------------------------------------------------------ Model
function ModelTab() {
  const g = useGenerate()
  const p = g.panel
  const caps = useSession((s) => s.capabilities)
  const models = useSession((s) => s.models)
  const pv = g.preview
  const cap = caps?.models[p.model_id]
  const order = ['flux2-dev-fp8mixed', 'klein-9b', 'klein-base-9b', 'klein-9b-kv', 'klein-4b', 'klein-base-4b']
  return (
    <div>
      <div className="model-grid">
        {order.filter((m) => caps?.models[m]).map((m) => {
          const c = caps!.models[m]
          const r = models.find((x) => x.id === m)
          const off = !c.wired
          return (
            <button key={m} className={`model-card${p.model_id === m ? ' active' : ''}${off ? ' off' : ''}`} onClick={() => !off && g.set({ model_id: m, turbo: m === 'flux2-dev-fp8mixed' ? p.turbo : false })} disabled={off} title={off ? 'coming in M5' : undefined}>
              <span>{c.label}{m === 'flux2-dev-fp8mixed' ? ' · slow, best adherence' : ''}</span>
              <small>{r?.license ?? ''} · {c.health}{c.distilled ? ' · distilled' : ''}{off ? ' · coming in M5' : ''}</small>
            </button>
          )
        })}
      </div>
      <h4 style={{ margin: '12px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>SAMPLING</h4>
      <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
        {cap?.turbo && <><label>Turbo LoRA</label><div><label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={p.turbo} onChange={(e) => g.set({ turbo: e.target.checked, steps: null })} /> 8-step Turbo (≈ 40 s vs 65 s at Draft)</label></div></>}
        <label>steps</label>
        <div><input type="number" min={1} max={60} value={p.steps ?? pv?.steps ?? cap?.steps ?? 20} disabled={!!cap?.distilled} onChange={(e) => g.set({ steps: Number(e.target.value) })} style={{ width: 90 }} />
          {cap?.distilled ? <span className="disabled-why"> fixed at {cap.steps} for distilled {cap.label}</span> : <span className="disabled-why"> {p.turbo ? 'Turbo preset 8' : 'dev 20–28; base Klein 20–50'}{p.steps !== null && <button className="quiet" onClick={() => g.set({ steps: null })}>reset</button>}</span>}</div>
        <label>guidance</label>
        <div><input type="number" step={0.1} min={0} max={10} value={p.guidance ?? pv?.guidance ?? cap?.guidance ?? 4} onChange={(e) => g.set({ guidance: Number(e.target.value) })} style={{ width: 90 }} /><span className="disabled-why"> dev 3–4.5 · Klein 1.0</span></div>
        <label>CFG</label>
        <div><input type="number" step={0.1} min={1} max={10} value={p.cfg ?? pv?.cfg ?? cap?.cfg ?? 1} disabled={!!cap?.distilled || p.model_id === 'flux2-dev-fp8mixed'} onChange={(e) => g.set({ cfg: Number(e.target.value) })} style={{ width: 90 }} />
          <span className="disabled-why"> {cap?.distilled ? 'fixed at 1.0 (distilled)' : p.model_id === 'flux2-dev-fp8mixed' ? 'dev is guidance-distilled: CFG stays 1.0' : 'base: 3–5, negatives work'}</span></div>
        <label>sampler</label>
        <div><select value={p.sampler ?? ''} onChange={(e) => g.set({ sampler: e.target.value || null })}><option value="">preset ({cap?.sampler ?? 'euler'})</option>{caps?.samplers.map((x) => <option key={x}>{x}</option>)}</select>
          <select value={p.scheduler ?? ''} onChange={(e) => g.set({ scheduler: e.target.value || null })} style={{ marginLeft: 6 }}><option value="">preset ({cap?.scheduler ?? 'simple'})</option>{caps?.schedulers.map((x) => <option key={x}>{x}</option>)}</select>
          <span className="disabled-why"> res_multistep + sgm_uniform is the author's ComfyUI setting; euler + simple is what E0 measured</span></div>
        <label>seed</label>
        <div><div className="segmented">{(['random', 'fixed', 'increment'] as const).map((m) => <button key={m} className={p.seed_mode === m ? 'active' : ''} onClick={() => g.set({ seed_mode: m })}>{m}</button>)}</div>
          {p.seed_mode !== 'random' && <input type="number" value={p.seed} onChange={(e) => g.set({ seed: Number(e.target.value) })} style={{ width: 130, marginLeft: 6 }} />}
          {p.seed_mode !== 'random' && <button className="quiet" onClick={() => g.set({ seed: Math.floor(Math.random() * 2 ** 31) })}>🎲</button>}</div>
      </div>
      <h4 style={{ margin: '12px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>LORA SLOTS (D25)</h4>
      <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
        {[1, 2, 3, 4].map((n) => <><label key={`l${n}`}>slot {n}</label><div key={`v${n}`}><select disabled style={{ width: 160 }}><option>— post-MVP —</option></select> <input type="number" disabled value={1} style={{ width: 70 }} /></div></>)}
        <span className="hint">the recipe and manifest already carry loras[]; loading is wired post-MVP</span>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ Size & Batch
function SizeTab() {
  const g = useGenerate()
  const p = g.panel
  const caps = useSession((s) => s.capabilities)
  const fmt = useSession((s) => s.project?.format)
  const fam = p.model_id.startsWith('klein') ? 'klein' : 'flux2'
  const tiers = caps?.tiers ?? {}
  const aspect = fmt ? `${fmt.aspect[0]}:${fmt.aspect[1]}` : '16:9'
  const applyAspect = (aw: number, ah: number) => {
    const px = p.width * p.height
    const w = Math.sqrt(px * aw / ah)
    g.set({ width: snap16(w), height: snap16(w * ah / aw), tier: 'custom' })
  }
  const pv = g.preview
  return (
    <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
      <label>tier</label>
      <div className="tiers">
        {(['thumb', 'draft', 'full'] as const).map((t) => { const wh = tiers[t]?.[fam]; return wh ? <button key={t} className={p.tier === t ? 'active' : ''} onClick={() => g.set({ tier: t, width: wh[0], height: wh[1] })}>{t} {wh[0]}×{wh[1]}</button> : null })}
        <button className={p.tier === 'custom' ? 'active' : ''} onClick={() => g.set({ tier: 'custom' })}>custom</button>
      </div>
      <span className="hint">Draft is the default (D18); Full 1920×1088 auto-crops to 1080 later{fam === 'flux2' ? ' — on dev, prefer Draft + Refine/Upscale in Edit (≈ 280 s per Full image)' : ''}</span>
      <label>aspect</label>
      <div className="tiers">{ASPECTS.map(([n, aw, ah]) => <button key={n} className={Math.abs(p.width / p.height - aw / ah) < 0.02 ? 'active' : ''} onClick={() => applyAspect(aw, ah)}>{n}{n === aspect ? ' (project)' : ''}</button>)}</div>
      <label>size</label>
      <div><input type="number" step={16} min={64} max={2048} value={p.width} onChange={(e) => g.set({ width: snap16(Number(e.target.value)), tier: 'custom' })} style={{ width: 90 }} /> × <input type="number" step={16} min={64} max={2048} value={p.height} onChange={(e) => g.set({ height: snap16(Number(e.target.value)), tier: 'custom' })} style={{ width: 90 }} />
        <span className="disabled-why"> multiples of 16 · {Math.round(p.width * p.height / 1e4) / 100} MP · ≈{Math.round(p.width / 16 * p.height / 16)} latent tokens</span></div>
      <label>count</label>
      <div><input type="range" min={1} max={8} value={p.count} onChange={(e) => g.set({ count: Number(e.target.value) })} /> <b>{p.count}</b></div>
      <label>estimate</label>
      <div className="estimate"><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />{pv?.estimate.seconds ? `≈ ${Math.round(pv.estimate.seconds)} s per image · ${Math.round(pv.estimate.seconds * p.count)} s for ${p.count} · ${pv.estimate.source}` : '…'}{pv?.estimate.vram_gb ? ` · VRAM ≈ ${pv.estimate.vram_gb} GB of ${pv.estimate.vram_budget_gb ?? '?'}` : ''}</div>
    </div>
  )
}

// ------------------------------------------------------------------ References
function RefsTab() {
  const g = useGenerate()
  const p = g.panel
  const cap = useSession((s) => s.capabilities?.models[p.model_id])
  const max = cap?.max_refs ?? 4
  const [over, setOver] = useState(false)
  const slots = Array.from({ length: Math.max(max, p.refs.length) }, (_, i) => p.refs[i])
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setOver(false)
    const ids = (e.dataTransfer.getData('text/loom2-assets') || '').split(',').filter(Boolean)
    ids.slice(0, max - p.refs.length).forEach((id) => g.addRef(id))
  }
  return (
    <div>
      <div className={`ref-slots`} onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
        {slots.slice(0, Math.min(max, 10)).map((r, i) => (
          <div key={i} className={`ref-slot${over ? ' over' : ''}`} onContextMenu={(e) => { if (!r) return; showMenu(e, [
            { label: 'Remove reference', icon: X, run: () => g.removeRef(r.asset_id) },
            { label: 'Move first', disabled: i === 0, run: () => g.moveRef(i, 0) },
            { label: 'Move left', disabled: i === 0, run: () => g.moveRef(i, i - 1) },
            { label: 'Move right', disabled: i >= p.refs.length - 1, run: () => g.moveRef(i, i + 1) },
            sep, { cmd: 'gen.clearRefs' },
          ]) }}>
            {r ? <>
              <img src={api.thumbUrl(r.asset_id, 256)} alt="" />
              <span className="n">{i + 1}</span>
              <button className="quiet x" onClick={() => g.removeRef(r.asset_id)}>✕</button>
              {i > 0 && <button className="quiet" style={{ position: 'absolute', bottom: 4, left: 4 }} onClick={() => g.moveRef(i, i - 1)}>◀</button>}
            </> : <span>drop from the Catalogue · ref {i + 1}</span>}
          </div>
        ))}
      </div>
      <p className="hint" style={{ gridColumn: 'auto', marginTop: 8 }}>Up to {max} on {cap?.label ?? p.model_id}; the prompt refers to them as "reference image 1…". A 1024² reference costs ≈ 4 096 tokens.</p>
      <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
        <label>downscale</label>
        <select value={p.ref_max_px} onChange={(e) => g.set({ ref_max_px: Number(e.target.value) })}><option value={512}>≤ 512²</option><option value={768}>≤ 768²</option><option value={1024}>≤ 1024² (default)</option><option value={0}>original size</option></select>
      </div>
      {p.refs.length >= 2 && p.model_id === 'klein-9b' && <p className="disabled-why">Klein 9B-KV is suggested for ≥ 2 references (2.5× faster multi-ref) — coming in M5.</p>}
      <p className="disabled-why">Select assets in the Catalogue and press <kbd>R</kbd>, or drag tiles here.</p>
    </div>
  )
}

// ------------------------------------------------------------------ Presets
function PresetsTab() {
  const g = useGenerate()
  const [sn, setSn] = useState({ name: '', field: 'lighting', text: '' })
  useEffect(() => { void g.loadPresets(); void g.loadSnippets() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div>
      <div style={{ display: 'flex', gap: 6 }}><button className="primary" onClick={() => runCommand('gen.savePreset')}>Save preset… <kbd>⌃S</kbd></button></div>
      <div className="lib-tree" style={{ marginTop: 8 }}>
        {g.presets.map((pr) => <div key={pr.name} style={{ display: 'flex', gap: 4 }}><button style={{ flex: 1 }} className={g.lastPreset === pr.name ? 'active' : ''} onClick={() => g.applyPreset(pr.name)}><span>{pr.name}</span><span className="n">{pr.panel.model_id}</span></button><button className="quiet" onClick={() => void g.deletePreset(pr.name)}>✕</button></div>)}
        {!g.presets.length && <span style={{ color: 'var(--fg3)' }}>No presets in this project yet.</span>}
      </div>
      <h4 style={{ margin: '14px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>SNIPPETS</h4>
      <div className="lib-tree">{g.snippets.map((s) => <button key={s.name} onClick={() => g.insertSnippet(s)} title={s.text}><span>{s.name}</span><span className="n">→ {s.field}</span></button>)}</div>
      <div className="gen-form" style={{ gridTemplateColumns: '60px 1fr', marginTop: 8 }}>
        <label>name</label><input type="text" value={sn.name} onChange={(e) => setSn({ ...sn, name: e.target.value })} />
        <label>field</label><select value={sn.field} onChange={(e) => setSn({ ...sn, field: e.target.value })}>{['scene', 'style', 'lighting', 'mood', 'background', 'composition'].map((f) => <option key={f}>{f}</option>)}</select>
        <label>text</label><input type="text" value={sn.text} onChange={(e) => setSn({ ...sn, text: e.target.value })} />
        <label /><button disabled={!sn.name || !sn.text} onClick={() => { void g.saveSnippet(sn); setSn({ name: '', field: 'lighting', text: '' }) }}>Add snippet</button>
      </div>
    </div>
  )
}

function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  const refresh = useGenerate((g) => g.refreshPreview)
  useEffect(() => { if (project?.open) void refresh() }, [project?.path, refresh])
  if (!project?.open) return <span style={{ color: 'var(--fg3)' }}>Open or create a project.</span>
  if (tab === 'model') return <ModelTab />
  if (tab === 'size') return <SizeTab />
  if (tab === 'refs') return <RefsTab />
  if (tab === 'presets') return <PresetsTab />
  return <PromptTab />
}

/** The pinned primary action with its estimate and disabled reasons (09 §3 foot). */
function PrimaryAction() {
  const g = useGenerate()
  const s = useSession()
  markUsed('gen.generate'); markUsed('gen.stage'); markUsed('gen.savePreset')
  const pv = g.preview
  const missing = pv?.missing ?? []
  const reason = !s.project?.open ? 'no project' : g.previewError ? g.previewError : !pv ? 'preparing…' : !pv.serialized_prompt ? 'empty prompt'
    : missing.length ? `weights missing: ${missing.map((m) => m.model_id).join(', ')}` : pv.estimate.vram_fit === 'over' ? 'VRAM estimate exceeds the budget' : null
  return (
    <div>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('gen.generate')} title="Generate (⌃↵)">Generate {g.panel.count} ▶</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button disabled={!!reason} onClick={() => runCommand('gen.stage')} title="Stage: add to the queue, run later (⌃⇧↵)">Stage</button>
        {missing.length > 0 && <button onClick={() => s.setSuite('models')}>Fetch {missing.reduce((a, m) => a + (m.approx_gb ?? 0), 0).toFixed(0)} GB</button>}
      </div>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * g.panel.count)} s · {pv?.width}×{pv?.height} · {pv?.steps} st{pv?.turbo ? ' turbo' : ''}</>}</div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip / Stage / Inspector (results on the catalogue grid)
function Strip() {
  const g = useGenerate()
  const health = useSession((s) => s.health)
  const r = useGenerateResults()
  useEffect(() => {
    const patch = g.show === 'batch' ? { batch_id: g.lastBatch ?? undefined, session_id: undefined } : g.show === 'session' ? { batch_id: undefined, session_id: health?.session_id ?? undefined } : { batch_id: undefined, session_id: undefined }
    if (r.q.batch_id !== patch.batch_id || r.q.session_id !== patch.session_id) void r.setQuery(patch)
  }, [g.show, g.lastBatch, health?.session_id]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <span>show</span>
      <div className="segmented gen-strip-show">{(['batch', 'session', 'all'] as const).map((m) => <button key={m} className={g.show === m ? 'active' : ''} onClick={() => g.setShow(m)}>{m === 'batch' ? 'this batch' : m === 'session' ? 'session' : 'all'}</button>)}</div>
      <CatStrip />
    </>
  )
}

function Interim() {
  const jobs = useSession((s) => s.jobs)
  const previews = useSession((s) => s.previews)
  const cancel = useSession((s) => s.cancelJob)
  const release = useSession((s) => s.releaseJob)
  const list = useMemo(() => Object.values(jobs).filter((j) => j.kind === 't2i' && ['running', 'queued', 'staged'].includes(j.status)).sort((a, b) => (a.status === 'running' ? -1 : b.status === 'running' ? 1 : a.created_at < b.created_at ? -1 : 1)), [jobs])
  if (!list.length) return null
  return (
    <div className="interim">
      {list.map((j) => (
        <div className="card" key={j.id}>
          <div className="img">{previews[j.id] ? <img src={previews[j.id]} alt="" /> : <span style={{ color: 'var(--fg3)' }}>{j.status === 'running' ? j.progress_text || 'starting' : j.status}</span>}</div>
          <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>
          <div className="t"><span>{String((j.recipe as { model_id?: string }).model_id ?? '').replace('flux2-dev-fp8mixed', 'dev')} · {j.seed}</span>
            <span>{j.status === 'staged' ? <button className="quiet" onClick={() => void release(j.id)}>run</button> : <button className="quiet" onClick={() => void cancel(j.id)}>✕</button>}</span></div>
        </div>
      ))}
    </div>
  )
}

function Stage() {
  const project = useSession((s) => s.project)
  const r = useGenerateResults()
  useEffect(() => { if (project?.open) { void r.load(); void r.refreshMeta() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <div className="placeholder"><div><h2>Generate</h2>open or create a project to begin</div></div>
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <Interim />
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}><CatStage /></div>
    </div>
  )
}

const withResults = (C: React.ComponentType) => function Wrapped() { return <CatalogueStoreCtx.Provider value={useGenerateResults}><C /></CatalogueStoreCtx.Provider> }

registerCommands([
  { id: 'gen.generate', scope: 'generate', label: 'Generate', icon: Wand2, keys: 'Ctrl+Enter', placement: ['panel'], run: () => void useGenerate.getState().generate(false) },
  { id: 'gen.stage', scope: 'generate', label: 'Stage (add to the queue, run later)', icon: Boxes, keys: 'Ctrl+Shift+Enter', placement: ['panel'], run: () => void useGenerate.getState().generate(true) },
  { id: 'gen.savePreset', scope: 'generate', label: 'Save preset…', icon: Bookmark, keys: 'Ctrl+S', placement: ['panel'], run: () => { const g = useGenerate.getState(); const n = window.prompt('Preset name', g.lastPreset ?? ''); if (n) void g.savePreset(n) } },
  { id: 'gen.clearRefs', scope: 'generate', label: 'Clear references', icon: Images, placement: ['context', 'panel'], when: () => useGenerate.getState().panel.refs.length > 0, run: () => { const g = useGenerate.getState(); [...g.panel.refs].forEach((r) => g.removeRef(r.asset_id)) } },
])

export function useGenerateKeys() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'generate') return
      handleKeyFor('generate', e)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}

function StripWithKeys() { useGenerateKeys(); return <Strip /> }

export const GenerateSuite: SuiteDef = {
  id: 'generate',
  rail: [{ id: 'prompt', label: 'Prompt', icon: <Wand2 size={18} /> }, { id: 'model', label: 'Model', icon: <Boxes size={18} /> }, { id: 'size', label: 'Size & Batch', icon: <SlidersHorizontal size={18} /> },
    { id: 'refs', label: 'References', icon: <Images size={18} /> }, { id: 'presets', label: 'Presets', icon: <Bookmark size={18} /> }],
  Panel, Strip: withResults(StripWithKeys), Stage: withResults(Stage), Inspector: withResults(CatInspector),
  PrimaryAction,
}

export type { Asset, PanelState, Subject }
