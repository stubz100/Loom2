// AE2 (proto01_animate 20 §2, D114): the editor's sections in Animate's column at the Final level — Layers (the composition's layers top to
// bottom: visible, solo, lock, blend mode, track matte, parent, the order) and Properties (the selected layer's transform and opacity, a
// keyframe at the playhead, each key's ease / hold). Every action is one engine command on the composition (a mouse home here, the
// toolbar's commands and the row's right-click menu too, D32); the viewer follows the new revision.
import { useState } from 'react'
import { CommandRow } from '../../frame/CommandButton'
import { sep, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { fmtTime } from './animateStore'
import { MASK_MODES, useComposition, type CompLayer, type FlatProp, type MaskInfo, type PropKey } from './compositionStore'

const BLEND_MODES = ['Normal', 'Multiply', 'Screen', 'Overlay', 'Add', 'Darken', 'Lighten', 'Soft Light', 'Hard Light', 'Difference']
const MATTE_KINDS: [string, string][] = [['luma', 'luma'], ['lumaInverted', 'luma inverted'], ['alpha', 'alpha'], ['alphaInverted', 'alpha inverted']]
const LABELS: Record<string, string> = { 'transform/anchor': 'Anchor', 'transform/position': 'Position', 'transform/scale': 'Scale', 'transform/rotation': 'Rotation', 'transform/opacity': 'Opacity' }
const cp = () => useComposition.getState()

function LayerRow({ l }: { l: CompLayer }) {
  const selected = useComposition((s) => s.selected === l.id)
  const layers = useComposition((s) => s.layers)
  const busy = useComposition((s) => s.busy)
  const sw = l.switches
  const on = (k: string) => !!sw[k]
  const others = layers.filter((o) => o.id !== l.id)
  const menu = (): MenuItem[] => [                                        // the registry's commands act on the selected layer (the row selects itself first)
    { cmd: 'anim.final.layer.hide', label: on('video') ? 'Hide the layer' : 'Show the layer' }, { cmd: 'anim.final.layer.solo', label: on('solo') ? 'Solo off' : 'Solo' },
    { cmd: 'anim.final.layer.lock', label: on('locked') ? 'Unlock' : 'Lock' }, sep,
    { cmd: 'anim.final.layer.up' }, { cmd: 'anim.final.layer.down' },
    { label: 'To the front', run: () => { void cp().arrange(l.id, 'front') }, disabled: l.index === 1 },
    { label: 'To the back', run: () => { void cp().arrange(l.id, 'back') }, disabled: l.index === layers.length }, sep,
    { cmd: 'anim.final.key.position' }, { cmd: 'anim.final.key.opacity' }, sep,
    { cmd: 'anim.final.mask.rect' }, { cmd: 'anim.final.mask.ellipse' }, { cmd: 'anim.final.trimIn' }, { cmd: 'anim.final.trimOut' }, sep,
    { cmd: 'anim.final.undo' }, { cmd: 'anim.final.redo' },
  ]
  return (
    <li className={selected ? 'selected' : ''} data-layer={l.id} data-index={l.index} onClick={() => cp().select(selected ? null : l.id)}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); cp().select(l.id); showMenu(e, menu()) }}>
      <button type="button" className={`sw ${on('video') ? 'on' : ''}`} title="Video: the layer is shown" disabled={busy} aria-pressed={on('video')}
        onClick={(e) => { e.stopPropagation(); void cp().layerSwitch(l.id, 'video', !on('video')) }}>◉</button>
      <button type="button" className={`sw ${on('solo') ? 'on' : ''}`} title="Solo: only the soloed layers are shown" disabled={busy} aria-pressed={on('solo')}
        onClick={(e) => { e.stopPropagation(); void cp().layerSwitch(l.id, 'solo', !on('solo')) }}>S</button>
      <button type="button" className={`sw ${on('locked') ? 'on' : ''}`} title="Lock: the layer cannot be changed" disabled={busy} aria-pressed={on('locked')}
        onClick={(e) => { e.stopPropagation(); void cp().layerSwitch(l.id, 'lock', !on('locked')) }}>🔒</button>
      <span className="name" title={`${l.name} · ${l.type ?? 'layer'} · in ${l.in.toFixed(2)} s, out ${l.out.toFixed(2)} s`}>{l.name}</span>
      <select className="blend" value={l.blendMode} title="Blend mode" disabled={busy} onClick={(e) => e.stopPropagation()}
        onChange={(e) => void cp().setBlend(l.id, e.target.value)}>
        {(BLEND_MODES.includes(l.blendMode) ? BLEND_MODES : [l.blendMode, ...BLEND_MODES]).map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      <select className="matte" value={l.trackMatte ? String(l.trackMatte.layer) : ''} title="Track matte: the layer whose luma or alpha cuts this one" disabled={busy} onClick={(e) => e.stopPropagation()}
        onChange={(e) => void cp().setMatte(l.id, e.target.value ? Number(e.target.value) : null, l.trackMatte ? matteKind(l.trackMatte.kind) : 'luma')}>
        <option value="">no matte</option>{others.map((o) => <option key={o.id} value={o.id}>matte: {o.name}</option>)}
      </select>
      {l.trackMatte && <select className="matte-kind" value={matteKind(l.trackMatte.kind)} title="Matte kind" disabled={busy} onClick={(e) => e.stopPropagation()}
        onChange={(e) => void cp().setMatte(l.id, l.trackMatte!.layer, e.target.value)}>{MATTE_KINDS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}
      <select className="parent" value={l.parent === null ? '' : String(l.parent)} title="Parent: this layer moves with it" disabled={busy} onClick={(e) => e.stopPropagation()}
        onChange={(e) => void cp().setParent(l.id, e.target.value ? Number(e.target.value) : null)}>
        <option value="">no parent</option>{others.map((o) => <option key={o.id} value={o.id}>parent: {o.name}</option>)}
      </select>
    </li>
  )
}

/** The engine's matte kind ("Luma Matte", "Alpha Inverted Matte") as the command's word. */
function matteKind(kind: string): string {
  const k = kind.toLowerCase()
  return `${k.includes('luma') ? 'luma' : 'alpha'}${k.includes('invert') ? 'Inverted' : ''}`
}

export function LayersSection() {
  const level = useComposition((s) => s.level)
  const comp = useComposition((s) => s.comp)
  const layers = useComposition((s) => s.layers)
  if (level !== 'final' || !comp) return <span className="hint">The composition's layers, at the Final level — in the Shot section, a final shot's <b>Open in Final</b>.</span>
  return (
    <div className="comp-layers">
      <div className="verbs"><CommandRow ids={['anim.final.undo', 'anim.final.redo', 'gap', 'anim.final.layer.up', 'anim.final.layer.down', 'anim.final.layer.hide', 'anim.final.layer.solo', 'anim.final.layer.lock', 'gap', 'anim.final.trimIn', 'anim.final.trimOut']} /></div>
      <ul className="comp-layer-list">{layers.map((l) => <LayerRow key={l.id} l={l} />)}</ul>
      <span className="hint">Top to bottom as composited. A row's right-click menu orders it; drag the selected layer in the viewer to move it.</span>
    </div>
  )
}

const shown = (v: number) => String(Math.round(v * 100) / 100)

/** A number typed, committed on Enter or blur (the engine round-trip per edit, not per keystroke); the parent keys it by the value, so a
 *  value that moved (an edit, an undo, another frame) remounts it fresh. */
function NumField({ value, step = 1, onCommit, label }: { value: number; step?: number; onCommit: (v: number) => void; label: string }) {
  const [draft, setDraft] = useState(shown(value))
  const commit = () => { const v = Number(draft); if (Number.isFinite(v) && v !== value) onCommit(v); else setDraft(shown(value)) }
  return <input type="number" step={step} value={draft} aria-label={label} onChange={(e) => setDraft(e.target.value)} onBlur={commit}
    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit() } }} />
}

function PropRow({ p, keys }: { p: FlatProp; keys: PropKey[] }) {
  const frame = useComposition((s) => s.frame)
  const rate = useComposition((s) => s.final?.rate ?? 16)
  const busy = useComposition((s) => s.busy)
  const t = frame / rate
  const atKey = keys.some((k) => Math.abs(k.time - t) < 1e-6)
  const vec = Array.isArray(p.value) ? (p.value as number[]) : null
  const scalar = typeof p.value === 'number' ? p.value : 0
  const label = LABELS[p.path] ?? p.path
  const setVec = (i: number, v: number) => { const next = [...(vec ?? [0, 0, 0])]; next[i] = v; void cp().setProp(p.path, next) }
  return (
    <div className="prop-row" data-path={p.path}>
      <button type="button" className={`key ${atKey ? 'on' : ''}`} title={atKey ? 'Remove the keyframe at the playhead' : 'Keyframe at the playhead'} disabled={busy}
        aria-pressed={atKey} onClick={() => void cp().keyToggle(p.path)}>◆</button>
      <span className="label">{label}{keys.length ? <span className="hint"> · {keys.length} key{keys.length === 1 ? '' : 's'}</span> : null}</span>
      <span className="fields">
        {vec ? <><NumField key={`x:${vec[0]}`} value={vec[0]} onCommit={(v) => setVec(0, v)} label={`${label} x`} /><NumField key={`y:${vec[1]}`} value={vec[1]} onCommit={(v) => setVec(1, v)} label={`${label} y`} /></>
          : <NumField key={`v:${scalar}`} value={scalar} step={p.path.endsWith('opacity') ? 1 : 0.5} onCommit={(v) => void cp().setProp(p.path, v)} label={label} />}
      </span>
      {keys.length > 0 && <ul className="keys">{keys.map((k) => (
        <li key={k.time} className={Math.abs(k.time - t) < 1e-6 ? 'here' : ''}>
          <button type="button" className="quiet" title="Go to this key" onClick={() => cp().setFrame(Math.round(k.time * rate))}>{fmtTime(Math.round(k.time * rate), rate)}</button>
          <span className="hint">{k.out === 'hold' ? 'hold' : k.in === 'bezier' || k.in === 'autoBezier' ? 'ease' : 'linear'}</span>
          <button type="button" className="quiet" title="Easy ease" disabled={busy} onClick={() => void cp().keyEase(p.path, k.time, 'ease')}>ease</button>
          <button type="button" className="quiet" title="Hold (the value stays till the next key)" disabled={busy} onClick={() => void cp().keyEase(p.path, k.time, 'hold')}>hold</button>
          <button type="button" className="quiet" title="Linear" disabled={busy} onClick={() => void cp().keyEase(p.path, k.time, 'linear')}>linear</button>
          <button type="button" className="quiet danger" title="Delete this keyframe" disabled={busy} onClick={() => void cp().keyDelete(p.path, k.time)}>×</button>
        </li>))}</ul>}
    </div>
  )
}

/** AE2c: one mask of the selected layer — feather, opacity, expansion, mode, inverted, remove (each one engine command). */
function MaskRow({ m }: { m: MaskInfo }) {
  const busy = useComposition((s) => s.busy)
  return (
    <li className="comp-mask" data-mask={m.uid}>
      <span className="name">{m.name}</span>
      <select value={MASK_MODES.includes(m.mode) ? m.mode : 'Add'} title="Mask mode" disabled={busy} onChange={(e) => void cp().setMaskMode(m.uid, e.target.value)}>
        {MASK_MODES.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <label className="inv"><input type="checkbox" checked={m.inverted} disabled={busy} onChange={(e) => void cp().invertMask(m.uid, e.target.checked)} /> inverted</label>
      <span className="fields">
        <label>feather <NumField key={`f:${m.feather}`} value={m.feather} step={1} onCommit={(v) => void cp().setMaskField(m.uid, 'feather', Math.max(0, v))} label={`${m.name} feather`} /></label>
        <label>opacity <NumField key={`o:${m.opacity}`} value={m.opacity} step={1} onCommit={(v) => void cp().setMaskField(m.uid, 'opacity', Math.max(0, Math.min(100, v)))} label={`${m.name} opacity`} /></label>
        <label>expand <NumField key={`e:${m.expansion}`} value={m.expansion} step={1} onCommit={(v) => void cp().setMaskField(m.uid, 'expansion', v)} label={`${m.name} expansion`} /></label>
      </span>
      <button type="button" className="quiet danger" title="Remove this mask" disabled={busy} onClick={() => void cp().removeMask(m.uid)}>×</button>
    </li>
  )
}

export function MasksSection() {
  const level = useComposition((s) => s.level)
  const comp = useComposition((s) => s.comp)
  const selected = useComposition((s) => s.selected)
  const layer = useComposition((s) => s.layers.find((l) => l.id === s.selected))
  const masks = useComposition((s) => s.masks)
  const tool = useComposition((s) => s.maskTool)
  if (level !== 'final' || !comp) return <span className="hint">The selected layer's masks, at the Final level.</span>
  if (selected === null || !layer) return <span className="hint">Select a layer in Layers, then draw a mask on the frame with the rectangle or ellipse tool.</span>
  return (
    <div className="comp-masks" data-layer={selected}>
      <h5>{layer.name}</h5>
      <div className="verbs"><CommandRow ids={['anim.final.mask.rect', 'anim.final.mask.ellipse']} active={tool === 'off' ? undefined : `anim.final.mask.${tool}`} /></div>
      {tool !== 'off' && <span className="hint">Drag on the frame to draw the {tool === 'rect' ? 'rectangle' : 'ellipse'}; the tool turns off once the mask is made.</span>}
      {masks.length ? <ul className="comp-mask-list">{masks.map((m) => <MaskRow key={m.uid} m={m} />)}</ul> : <span className="hint">No mask on this layer.</span>}
    </div>
  )
}

export function PropertiesSection() {
  const level = useComposition((s) => s.level)
  const comp = useComposition((s) => s.comp)
  const selected = useComposition((s) => s.selected)
  const layer = useComposition((s) => s.layers.find((l) => l.id === s.selected))
  const props = useComposition((s) => s.props)
  const keysOf = useComposition((s) => s.keysOf)
  if (level !== 'final' || !comp) return <span className="hint">The selected layer's properties, at the Final level.</span>
  if (selected === null || !layer) return <span className="hint">Select a layer in Layers — or drag a selected layer in the viewer to move it.</span>
  return (
    <div className="comp-props" data-layer={selected}>
      <h5>{layer.name}</h5>
      <div className="verbs"><CommandRow ids={['anim.final.key.position', 'anim.final.key.opacity']} /></div>
      {props.map((p) => <PropRow key={p.path} p={p} keys={keysOf[p.path] ?? []} />)}
      {!props.length && <span className="hint">reading…</span>}
    </div>
  )
}
