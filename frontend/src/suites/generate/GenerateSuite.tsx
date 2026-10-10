// Generate suite (09): Prompt (tree / JSON / text with the exact serialisation preview, per-field preset menus,
// optional subjects, the reference images inside the prompt), Model (with ComfyUI's advanced configuration),
// Size & Batch, Presets; results on the Catalogue grid filtered to this suite; interim tiles with live previews.
import { Boxes, Bookmark, Images, ListPlus, Plus, SlidersHorizontal, Trash2, Wand2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { handleKeyFor, markUsed, registerCommands, runCommand, sep } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { askText, useSession } from '../../store/session'
import { CatalogueStoreCtx } from '../catalogue/catalogueContext'
import { useGenerateResults } from '../catalogue/catalogueStore'
import { Inspector as CatInspector, Stage as CatStage, Strip as CatStrip } from '../catalogue/CatalogueSuite'
import { appendValue, FIELD_LABEL, presetMenu, type FieldKey } from './fieldPresets'
import { useGenerate, type Panel as PanelState, type Subject } from './generateStore'
import './generate.css'
import { assetIds, onlyAssets, useDropTarget } from '../../frame/drag'

const ASPECTS: [string, number, number][] = [['16:9', 16, 9], ['1:1', 1, 1], ['3:2', 3, 2], ['2:3', 2, 3], ['9:16', 9, 16], ['21:9', 21, 9]]
const snap16 = (n: number) => Math.max(64, Math.round(n / 16) * 16)

// ------------------------------------------------------------------ Prompt: one field = input + ✦ preset menu
function PresetButton({ field, current, onApply, onSaveStart }: { field: FieldKey; current: string; onApply: (v: string) => void; onSaveStart: () => void }) {
  const snippets = useGenerate((g) => g.snippets)
  const del = useGenerate((g) => g.deleteSnippet)
  return (
    <button type="button" className="preset-btn" title={`Presets for ${FIELD_LABEL[field]}`} aria-label={`presets for ${FIELD_LABEL[field]}`}
      onClick={(e) => showMenu(e, presetMenu(field, current, snippets, onApply, onSaveStart, (name) => void del(name)))}>
      <ListPlus size={14} />
    </button>
  )
}

function Field({ label, field, value, onChange, multiline, placeholder, rows }: { label?: string; field: FieldKey; value: string; onChange: (v: string) => void; multiline?: boolean; placeholder?: string; rows?: number }) {
  const [naming, setNaming] = useState<string | null>(null)
  const save = useGenerate((g) => g.saveSnippet)
  const commit = () => { if (naming?.trim()) void save({ name: naming.trim(), field, text: value }); setNaming(null) }
  return (
    <>
      <label>{label ?? FIELD_LABEL[field]}</label>
      <div className="field">
        <div className="row">
          {multiline
            ? <textarea value={value} rows={rows} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
            : <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />}
          <PresetButton field={field} current={value} onApply={(v) => onChange(appendValue(value, v, field))} onSaveStart={() => setNaming('')} />
        </div>
        {naming !== null && (
          <div className="saver">
            <input type="text" autoFocus value={naming} placeholder={`name this ${FIELD_LABEL[field]} preset`} onChange={(e) => setNaming(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setNaming(null) }} />
            <button className="primary" disabled={!naming.trim()} onClick={commit}>Save</button>
            <button className="quiet" onClick={() => setNaming(null)}>Cancel</button>
          </div>
        )}
      </div>
    </>
  )
}

function SubjectCard({ i, s }: { i: number; s: Subject }) {
  const g = useGenerate()
  const set = (patch: Partial<Subject>) => g.setSubject(i, patch)
  return (
    <div className="subject">
      <div className="head"><b>subject {i + 1}</b><button className="quiet" title="Remove this subject" onClick={() => g.removeSubject(i)}><X size={12} /> remove</button></div>
      <Field label="description" field="subject.description" multiline rows={2} value={s.description} onChange={(v) => set({ description: v })} placeholder='who/what; literal text in quotes; bind colours here ("a #F2A93B brass compass")' />
      <Field label="position" field="subject.position" value={s.position ?? ''} onChange={(v) => set({ position: v })} placeholder="where in frame" />
      <Field label="action" field="subject.action" value={s.action ?? ''} onChange={(v) => set({ action: v })} />
      <Field label="pose" field="subject.pose" value={s.pose ?? ''} onChange={(v) => set({ pose: v })} />
      <label>color_match</label>
      <select value={s.color_match ?? 'exact'} onChange={(e) => set({ color_match: e.target.value })}><option value="exact">exact</option><option value="approximate">approximate</option><option value="">—</option></select>
    </div>
  )
}

/** Reference slots (FLUX.2 unified editing): up to 10 on dev, 4 on Klein; the prompt refers to "reference image N". */
function RefSlots() {
  const g = useGenerate()
  const p = g.panel
  const cap = useSession((s) => s.capabilities?.models[p.model_id])
  const max = cap?.max_refs ?? 4
  const slots = Array.from({ length: Math.min(10, Math.max(max, p.refs.length)) }, (_, i) => p.refs[i])
  const { ref: dropRef, over } = useDropTarget(onlyAssets, (d) => assetIds(d).slice(0, max - p.refs.length).forEach((id) => g.addRef(id)))
  return (
    <>
      <div ref={dropRef} className="ref-slots">
        {slots.map((r, i) => (
          <div key={i} className={`ref-slot${over ? ' over' : ''}`} title={r ? `reference image ${i + 1}` : `drop a Catalogue tile here, or select one and press R · reference ${i + 1}`}
            onContextMenu={(e) => { if (!r) return; showMenu(e, [
              { label: 'Remove reference', icon: X, run: () => g.removeRef(r.asset_id) },
              { label: 'Move first', disabled: i === 0, run: () => g.moveRef(i, 0) },
              { label: 'Move left', disabled: i === 0, run: () => g.moveRef(i, i - 1) },
              { label: 'Move right', disabled: i >= p.refs.length - 1, run: () => g.moveRef(i, i + 1) },
              sep, { cmd: 'gen.clearRefs' },
            ]) }}>
            {r ? <>
              <img src={api.thumbUrl(r.asset_id, 256)} alt="" />
              <span className="n">{i + 1}</span>
              <button className="quiet x" title="Remove" onClick={() => g.removeRef(r.asset_id)}>✕</button>
              {i > 0 && <button className="quiet mv" title="Move left" onClick={() => g.moveRef(i, i - 1)}>◀</button>}
            </> : <span className="empty">{i + 1}</span>}
          </div>
        ))}
      </div>
      <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr', marginTop: 6 }}>
        <label>downscale</label>
        <div>
          <select value={p.ref_max_px} onChange={(e) => g.set({ ref_max_px: Number(e.target.value) })}><option value={512}>≤ 512²</option><option value={768}>≤ 768²</option><option value={1024}>≤ 1024² (default)</option><option value={0}>original size</option></select>
          <span className="disabled-why"> a 1024² reference ≈ 4 096 tokens</span>
        </div>
      </div>
      {p.refs.length >= 2 && p.model_id === 'klein-9b' && <p className="disabled-why">Klein 9B-KV is suggested for ≥ 2 references (2.5× faster multi-ref) — coming in M5.</p>}
    </>
  )
}

function PromptTab() {
  const g = useGenerate()
  const p = g.panel
  const t = p.tree
  const pv = g.preview
  const cap = useSession((s) => s.capabilities?.models[p.model_id])
  const wc = pv?.word_count ?? 0
  const counterClass = wc === 0 ? '' : wc >= 30 && wc <= 80 ? 'ok' : wc > 120 ? 'warn' : ''
  const cam = (patch: Partial<NonNullable<typeof t.camera>>) => g.setCamera(patch)
  return (
    <div>
      <div className="segmented" style={{ marginBottom: 10 }}>
        {(['tree', 'json', 'text'] as const).map((m) => <button key={m} className={p.prompt_mode === m ? 'active' : ''} onClick={() => { if (m === 'json' && p.prompt_mode === 'tree') g.treeToJson(); else g.set({ prompt_mode: m }) }}>{m === 'tree' ? 'Tree' : m === 'json' ? 'JSON' : 'Text'}</button>)}
        <span className={`counter ${counterClass}`} style={{ padding: '4px 8px' }}>{wc} words · ≈{pv?.token_estimate ?? 0} tokens {wc > 120 ? '· over the 512-token comfort zone' : wc && (wc < 30 || wc > 80) ? '· ideal 30–80' : ''}</span>
      </div>
      {p.prompt_mode === 'tree' && (
        <div className="gen-form gen-tree">
          <Field field="scene" multiline rows={2} value={t.scene ?? ''} onChange={(v) => g.setTree({ scene: v })} placeholder="overall scene description" />
          <details open className="refs-block">
            <summary>reference images · {p.refs.length} of {cap?.max_refs ?? 4} on {cap?.label ?? p.model_id} — subjects can say "reference image 1"</summary>
            <RefSlots />
          </details>
          <h5>subjects · optional</h5>
          {(t.subjects ?? []).map((s, i) => <SubjectCard key={i} i={i} s={s} />)}
          <div className="full"><button onClick={g.addSubject} title="Add a subject card"><Plus size={12} /> subject</button></div>
          <h5>look</h5>
          <Field field="style" value={t.style ?? ''} onChange={(v) => g.setTree({ style: v })} placeholder="artistic style" />
          <label>color_palette</label>
          <div className="swatches">
            {(t.color_palette ?? []).map((c, i) => <span key={i} className="swatch" style={{ background: c }} title={c}><input type="color" value={/^#[0-9a-f]{6}$/i.test(c) ? c : '#888888'} onChange={(e) => { const pal = [...(t.color_palette ?? [])]; pal[i] = e.target.value.toUpperCase(); g.setTree({ color_palette: pal }) }} /><i onClick={() => g.setTree({ color_palette: (t.color_palette ?? []).filter((_, j) => j !== i) })}>×</i></span>)}
            <button title="Add a colour" onClick={() => g.setTree({ color_palette: [...(t.color_palette ?? []), '#F2A93B'] })}>+</button>
          </div>
          <span className="hint">bind colours to objects in the subject descriptions; the palette alone is weak</span>
          <Field field="lighting" value={t.lighting ?? ''} onChange={(v) => g.setTree({ lighting: v })} />
          <Field field="mood" value={t.mood ?? ''} onChange={(v) => g.setTree({ mood: v })} />
          <Field field="background" value={t.background ?? ''} onChange={(v) => g.setTree({ background: v })} />
          <Field field="composition" value={t.composition ?? ''} onChange={(v) => g.setTree({ composition: v })} />
          <h5>camera</h5>
          <Field label="angle" field="camera.angle" value={t.camera?.angle ?? ''} onChange={(v) => cam({ angle: v })} />
          <Field label="lens" field="camera.lens" value={t.camera?.lens ?? ''} onChange={(v) => cam({ lens: v })} />
          <Field label="depth of field" field="camera.depth_of_field" value={t.camera?.depth_of_field ?? ''} onChange={(v) => cam({ depth_of_field: v })} />
          <Field label="f-number" field="camera.f-number" value={t.camera?.['f-number'] ?? ''} onChange={(v) => cam({ 'f-number': v })} />
          <Field label="distance" field="camera.distance" value={t.camera?.distance ?? ''} onChange={(v) => cam({ distance: v })} />
          <h5>extras</h5>
          <Field label="lead text" field="text" value={p.text} onChange={(v) => g.set({ text: v })} placeholder="optional sentence prepended for Klein (prose mode)" />
          {cap && !cap.distilled
            ? <Field field="negative" value={p.negative} onChange={(v) => g.set({ negative: v })} placeholder="CFG-capable variant: negatives are honoured" />
            : <><label>negative</label><span className="disabled-why">hidden: {cap?.distilled ? 'distilled variants ignore negatives (CFG 1)' : 'dev runs guidance-distilled without CFG'}</span></>}
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
          <details open className="refs-block" style={{ marginTop: 10 }}>
            <summary>reference images · {p.refs.length} of {cap?.max_refs ?? 4}</summary>
            <RefSlots />
          </details>
        </div>
      )}
      {p.prompt_mode === 'text' && (
        <div>
          <textarea value={p.text} onChange={(e) => g.set({ text: e.target.value })} rows={8} style={{ width: '100%' }} placeholder="plain prompt" />
          <details open className="refs-block" style={{ marginTop: 10 }}>
            <summary>reference images · {p.refs.length} of {cap?.max_refs ?? 4}</summary>
            <RefSlots />
          </details>
        </div>
      )}
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
  // D31: the encoder weights behind the prompt — a picker only where the model has an alternate (Klein 9B: Q4_K_M GGUF default, fp8)
  const teOpts = cap?.te_options ?? []
  const teEff = teOpts.find((o) => (p.te_id ? o.id === p.te_id : o.default))
  const teGguf = !!teEff?.gguf
  useEffect(() => {
    if (p.te_id && cap && !teOpts.some((o) => o.id === p.te_id)) g.set({ te_id: null })        // a persisted choice from another model
    else if (teGguf && p.te_device) g.set({ te_device: null })                                  // CLIPLoaderGGUF has no device input
  }, [p.te_id, p.te_device, cap, teGguf]) // eslint-disable-line react-hooks/exhaustive-deps
  const order = ['flux2-dev-fp8mixed', 'klein-9b', 'klein-base-9b', 'klein-9b-kv', 'klein-4b', 'klein-base-4b']
  const shiftCustom = p.base_shift !== null || p.max_shift !== null
  const modelShift = caps?.advanced?.model_shift[p.model_id.startsWith('klein') ? 'klein' : p.model_id] ?? 2.02
  const nodeDefaults = caps?.advanced?.shift_node_defaults ?? { base: 0.5, max: 1.15 }
  const flux2 = caps?.advanced?.flux2_schedule ?? 'flux2'
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
        {cap?.turbo && <><label>Turbo LoRA</label><div><label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={p.turbo} onChange={(e) => g.set({ turbo: e.target.checked, steps: null })} /> 8-step Turbo (≈ 40 s vs 65 s at Draft)</label>
          {p.turbo && <span className="disabled-why"> · strength <input type="number" step={0.05} min={0} max={2} value={p.turbo_strength} onChange={(e) => g.set({ turbo_strength: Number(e.target.value) })} style={{ width: 64 }} /></span>}</div></>}
        <label>steps</label>
        <div><input type="number" min={1} max={200} value={p.steps ?? pv?.steps ?? cap?.steps ?? 20} disabled={!!cap?.distilled} onChange={(e) => g.set({ steps: Number(e.target.value) })} style={{ width: 90 }} />
          {cap?.distilled ? <span className="disabled-why"> fixed at {cap.steps} for distilled {cap.label}</span> : <span className="disabled-why"> {p.turbo ? 'Turbo preset 8' : 'dev 20–28; base Klein 20–50'}{p.steps !== null && <button className="quiet" onClick={() => g.set({ steps: null })}>reset</button>}</span>}</div>
        <label>guidance</label>
        <div><input type="number" step={0.1} min={0} max={10} value={p.guidance ?? pv?.guidance ?? cap?.guidance ?? 4} onChange={(e) => g.set({ guidance: Number(e.target.value) })} style={{ width: 90 }} /><span className="disabled-why"> dev 3–4.5 · Klein 1.0</span></div>
        <label>CFG</label>
        <div><input type="number" step={0.1} min={1} max={10} value={p.cfg ?? pv?.cfg ?? cap?.cfg ?? 1} disabled={!!cap?.distilled || p.model_id === 'flux2-dev-fp8mixed'} onChange={(e) => g.set({ cfg: Number(e.target.value) })} style={{ width: 90 }} />
          <span className="disabled-why"> {cap?.distilled ? 'fixed at 1.0 (distilled)' : p.model_id === 'flux2-dev-fp8mixed' ? 'dev is guidance-distilled: CFG stays 1.0' : 'base: 3–5, negatives work'}</span></div>
        <label>sampler</label>
        <div><select value={p.sampler ?? ''} onChange={(e) => g.set({ sampler: e.target.value || null })}><option value="">preset ({cap?.sampler ?? 'euler'})</option>{caps?.samplers.map((x) => <option key={x}>{x}</option>)}</select>
          <span className="disabled-why"> {caps?.samplers.length ?? 0} samplers from the engine · res_multistep is the author's ComfyUI setting; euler is what E0 measured</span></div>
        <label>scheduler</label>
        <div><select value={p.scheduler ?? ''} onChange={(e) => g.set({ scheduler: e.target.value || null })}><option value="">preset ({cap?.scheduler ?? 'simple'})</option>{caps?.schedulers.map((x) => <option key={x} value={x}>{x === flux2 ? `${x} · resolution-shifted sigmas (BFL)` : x}</option>)}</select>
          <span className="disabled-why"> {p.scheduler === flux2 ? 'Flux2Scheduler through the custom sampler path (the inpaint graphs use it); CFG > 1 keeps the negative via CFGGuider' : 'sgm_uniform pairs with res_multistep'}</span></div>
        <label>seed</label>
        <div><div className="segmented">{(['random', 'fixed', 'increment'] as const).map((m) => <button key={m} className={p.seed_mode === m ? 'active' : ''} onClick={() => g.set({ seed_mode: m })}>{m}</button>)}</div>
          {p.seed_mode !== 'random' && <input type="number" value={p.seed} onChange={(e) => g.set({ seed: Number(e.target.value) })} style={{ width: 130, marginLeft: 6 }} />}
          {p.seed_mode !== 'random' && <button className="quiet" title="Random seed" onClick={() => g.set({ seed: Math.floor(Math.random() * 2 ** 31) })}>🎲</button>}</div>
      </div>
      <details className="advanced" open={shiftCustom || !!p.weight_dtype || !!p.te_device || !!p.te_id || p.tiled_vae}>
        <summary>Advanced · ComfyUI model and decode settings</summary>
        <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
          <label>shift</label>
          <div>
            <div className="segmented"><button className={!shiftCustom ? 'active' : ''} onClick={() => g.set({ base_shift: null, max_shift: null })}>model default ({modelShift})</button><button className={shiftCustom ? 'active' : ''} onClick={() => g.set({ base_shift: nodeDefaults.base, max_shift: nodeDefaults.max })}>custom</button></div>
            {shiftCustom && <span className="disabled-why"> base <input type="number" step={0.05} min={0} max={10} value={p.base_shift ?? nodeDefaults.base} onChange={(e) => g.set({ base_shift: Number(e.target.value) })} style={{ width: 64 }} /> max <input type="number" step={0.05} min={0} max={10} value={p.max_shift ?? nodeDefaults.max} onChange={(e) => g.set({ max_shift: Number(e.target.value) })} style={{ width: 64 }} /></span>}
            <span className="hint" style={{ gridColumn: 'auto' }}>ModelSamplingFlux: the shift grows with image size between base (256 tokens) and max (4 096); the model's own value is a constant</span>
          </div>
          <label>weight dtype</label>
          <div><select value={p.weight_dtype ?? ''} onChange={(e) => g.set({ weight_dtype: e.target.value || null })}><option value="">preset ({pv?.weight_dtype ?? 'default'})</option>{caps?.weight_dtypes.map((x) => <option key={x}>{x}</option>)}</select>
            <span className="disabled-why"> UNETLoader: fp8_e4m3fn_fast uses the fp8 matmul path — a speed candidate to measure on gfx1201</span></div>
          <label>text encoder</label>
          <div>{teOpts.length > 1 && <select value={p.te_id ?? ''} title="Which weights encode the prompt (D31)" onChange={(e) => g.set({ te_id: e.target.value || null })}>{teOpts.map((o) => <option key={o.id} value={o.default ? '' : o.id}>{o.default ? `preset · ${o.label}` : o.label}{o.health === 'missing' ? ' (not fetched)' : ''}</option>)}</select>}
            {teOpts.length > 1 && ' '}<select value={p.te_device ?? ''} disabled={teGguf} title={teGguf ? 'a GGUF encoder loads on the GPU (CLIPLoaderGGUF has no device input)' : 'where the encoder runs'} onChange={(e) => g.set({ te_device: e.target.value || null })}><option value="">{teGguf ? 'GPU' : 'preset (GPU)'}</option>{!teGguf && caps?.te_devices.filter((x) => x !== 'default').map((x) => <option key={x} value={x}>{x === 'cpu' ? 'cpu · saves VRAM, ≈ 170 s per new prompt (E0)' : x}</option>)}</select>
            {teOpts.length > 1 && <span className="hint" style={{ gridColumn: 'auto' }}>{teGguf ? 'Q4_K_M stays resident beside the 9B transformer — a cold tiled refine takes 279 s instead of 1157 s (2026-10-07)' : 'the fp8 encoder makes the 9B transformer stream on a cold engine'}</span>}</div>
          <label>decode</label>
          <div><label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={p.tiled_vae} onChange={(e) => g.set({ tiled_vae: e.target.checked })} /> tiled VAE decode</label>
            {p.tiled_vae && <span className="disabled-why"> · tile <input type="number" step={32} min={64} max={4096} value={p.tile_size} onChange={(e) => g.set({ tile_size: Number(e.target.value) })} style={{ width: 72 }} /> px</span>}
            <span className="hint" style={{ gridColumn: 'auto' }}>VAEDecodeTiled trades a little time for VRAM headroom on the Full tier (D13)</span></div>
        </div>
      </details>
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

// ------------------------------------------------------------------ Presets: whole-panel presets + the field presets saved from the ✦ menus
function PresetsTab() {
  const g = useGenerate()
  useEffect(() => { void g.loadPresets(); void g.loadSnippets() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div>
      <div style={{ display: 'flex', gap: 6 }}><button className="primary" onClick={() => runCommand('gen.savePreset')}>Save panel preset… <kbd>Ctrl+S</kbd></button></div>
      <div className="lib-tree" style={{ marginTop: 8 }}>
        {g.presets.map((pr) => <div key={pr.name} style={{ display: 'flex', gap: 4 }}><button style={{ flex: 1 }} className={g.lastPreset === pr.name ? 'active' : ''} onClick={() => g.applyPreset(pr.name)}><span>{pr.name}</span><span className="n">{pr.panel.model_id}</span></button><button className="quiet" title="Delete preset" onClick={() => void g.deletePreset(pr.name)}>✕</button></div>)}
        {!g.presets.length && <span style={{ color: 'var(--fg3)' }}>No panel presets in this project yet.</span>}
      </div>
      <h4 style={{ margin: '14px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>FIELD PRESETS</h4>
      <div className="preset-list">
        {g.snippets.map((s) => <div className="row" key={`${s.field}:${s.name}`}><span className="f">{FIELD_LABEL[s.field as FieldKey] ?? s.field}</span><b>{s.name}</b><span className="t" title={s.text}>{s.text}</span><button className="quiet" title="Remove" onClick={() => void g.deleteSnippet(s.name)}><Trash2 size={12} /></button></div>)}
        {!g.snippets.length && <span style={{ color: 'var(--fg3)', fontSize: 12 }}>None yet — the <ListPlus size={11} style={{ verticalAlign: -1 }} /> icon next to any prompt field offers "Save current text as preset".</span>}
      </div>
    </div>
  )
}

function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  const caps = useSession((s) => s.capabilities)
  const refresh = useGenerate((g) => g.refreshPreview)
  useEffect(() => { if (project?.open) { void refresh(); void useGenerate.getState().loadSnippets() } }, [project?.path, refresh])   // C23: the ✦ menus need the field presets
  // C3 (D26): a persisted model this build does not offer (dev under `open`) falls back to Klein 4B, else the first model listed
  useEffect(() => { const g = useGenerate.getState(); if (caps && !caps.models[g.panel.model_id]) { const next = caps.models['klein-4b'] ? 'klein-4b' : Object.keys(caps.models)[0]; if (next) g.set({ model_id: next, turbo: false }) } }, [caps])
  if (!project?.open) return <span style={{ color: 'var(--fg3)' }}>Open or create a project.</span>
  if (tab === 'model') return <ModelTab />
  if (tab === 'size') return <SizeTab />
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
      <button className="primary" disabled={!!reason} onClick={() => runCommand('gen.generate')} title="Generate (Ctrl+Enter)">Generate {g.panel.count} ▶</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button disabled={!!reason} onClick={() => runCommand('gen.stage')} title="Stage: add to the queue, run later (Ctrl+Shift+Enter)">Stage</button>
        {missing.length > 0 && <button onClick={() => s.setSuite('models')}>Fetch {missing.reduce((a, m) => a + (m.approx_gb ?? 0), 0).toFixed(0)} GB</button>}
      </div>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * g.panel.count)} s · {pv?.width}×{pv?.height} · {pv?.steps} st{pv?.turbo ? ' turbo' : ''}{pv?.scheduler === 'flux2' ? ' · flux2 schedule' : ''}</>}</div>
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
  { id: 'gen.savePreset', scope: 'generate', label: 'Save panel preset…', icon: Bookmark, keys: 'Ctrl+S', placement: ['panel'], run: () => { const g = useGenerate.getState(); void askText({ title: 'Save panel preset', text: 'Saves every field of the panel under this name; an existing preset of the same name is replaced.', initial: g.lastPreset ?? '', placeholder: 'preset name' }).then((n) => { if (n) void g.savePreset(n) }) } },
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
    { id: 'presets', label: 'Presets', icon: <Bookmark size={18} /> }],
  Panel, Strip: withResults(StripWithKeys), Stage: withResults(Stage), Inspector: withResults(CatInspector),
  PrimaryAction,
}

export type { Asset, PanelState, Subject }
