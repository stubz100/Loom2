// AE2 (proto01_animate 20 §2, D114): the editor's Layers section at the Final level — the composition's layers top to bottom (visible, solo,
// lock, blend mode, track matte, parent, the order) and, **under the selected layer's row** (UX9 U1: so it is plain which layer is being
// changed), its editor with three parts: Properties (transform and opacity, a keyframe at the playhead, each key's ease / hold), Masks
// (drawn on the frame: rectangle, ellipse, the pen, from the layer's content, EffectCraft's object matte; mode, inverted, feather, opacity,
// expansion; tracked) and Effects (Effects.tsx). Every action is one engine command on the composition (a mouse home here, the toolbar's
// commands and the row's right-click menu too, D32); the viewer follows the new revision. Help hides behind ? (D116).
import { useState } from 'react'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { sep, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { fmtTime } from './animateStore'
import { EffectsBody } from './Effects'
import { useSession } from '../../store/session'
import { MASK_MODES, PASS_LABEL, useComposition, type CompLayer, type EditorTab, type FlatProp, type MaskInfo, type PassMouth, type PassPreset, type PropKey, type Take } from './compositionStore'

const BLEND_MODES = ['Normal', 'Multiply', 'Screen', 'Overlay', 'Add', 'Darken', 'Lighten', 'Soft Light', 'Hard Light', 'Difference']
const MATTE_KINDS: [string, string][] = [['luma', 'luma'], ['lumaInverted', 'luma inverted'], ['alpha', 'alpha'], ['alphaInverted', 'alpha inverted']]
const LABELS: Record<string, string> = { 'transform/anchor': 'Anchor', 'transform/position': 'Position', 'transform/scale': 'Scale', 'transform/rotation': 'Rotation', 'transform/opacity': 'Opacity' }
const TABS: [EditorTab, string, string][] = [['props', 'Properties', 'transform, opacity, keyframes'], ['masks', 'Masks', 'shapes that keep or cut parts of the layer'], ['effects', 'Effects', 'colour, blur, grain, mattes, mood'],
  ['passes', 'Passes', "AI passes over the layer's frames: clean-up, creative, the face pass, lip-sync"]]
// D118 (AE4a): the passes as tiles; AE4c (E29b): Face and Lip-sync — the head as its own layer, rendered at 512 px and pasted back
const PASSES: { id: PassPreset; label: string; hint: string; strength: number; head?: boolean }[] = [
  { id: 'cleanup', label: 'Clean up', hint: "Wan 2.2's low-noise expert over the layer at a low strength: cleaner hands and surfaces (E24 A2); about 15 min for 81 frames", strength: 0.1 },
  { id: 'creative', label: 'Creative', hint: "LTX-2.3 locked to the layer's Stage depth: a repaint of the surfaces — for creative upgrades, it distorts (E24 C3); about 2 min", strength: 0.35 },
  { id: 'face', label: 'Face', hint: "The head tracked from the Stage's keypoints, rendered at 512 px by Wan Animate from the character's reference and pasted back under a grown, feathered mask: a sharp, recognisable face (E29b); the layer's matte follows; about 5 min for 77 frames, in batches", strength: 0.5, head: true },
  { id: 'lipsync', label: 'Lip-sync', hint: "The face pass with the lines attached to this layer: a talking head of the reference per line (S2V, English) drives the mouth; about 10 min per line window plus the face pass. Attach a line first (Layers › Attach a line…)", strength: 0.5, head: true },
]
const PASSES_HELP = "A pass is a job that reads the layer's frames and writes a new version — a take — which the layer shows as its source; the original stays, "
  + 'and any take can be shown again or dropped. The composition keeps the layer\'s transforms, masks, effects and keys across a swap. Before compares nothing here: '
  + 'pick Original to see the layer as performed. A pass runs on the GPU like any job, one at a time; the Dock shows it. Face and Lip-sync run as several jobs '
  + '(the talking head per line, the head in 77-frame batches, then the paste); the take lands after the last.'
const MASK_TOOLS_HELP = 'Rectangle and ellipse: drag on the frame. Pen: click the points of a shape, the first again (or a double-click) closes it, Esc drops it. '
  + "From the layer: what is visible on the layer at the playhead — a character's silhouette, a prop, the shadows — traced into a mask that follows across the shot. "
  + "Object: click a thing on the frame; EffectCraft's Object Matte cuts the layer to it and follows it (an effect, under Effects). "
  + 'Follow the motion: EffectCraft tracks what is inside the selected mask from the playhead to the end. Fill: the masks as filled areas instead of outlines.'
const MASKS_HELP = 'A mask is a shape on the layer. Add keeps what is inside and hides the rest; Subtract cuts the inside away; Intersect keeps only what this mask '
  + 'and the ones above it share — the masks apply in order. Inverted swaps inside and outside. Feather softens the edge over that many pixels, expand grows or '
  + 'shrinks it, opacity is how much the mask counts. The outlines show on the frame while the layer is selected: drag a point to reshape, click an outline to select. '
  + "A character's own cut-out is not a mask but her track matte (the Layers row), made by SAM 3 when the layer was performed."
const cp = () => useComposition.getState()

/** The engine's matte kind ("Luma Matte", "Alpha Inverted Matte") as the command's word. */
function matteKind(kind: string): string {
  const k = kind.toLowerCase()
  return `${k.includes('luma') ? 'luma' : 'alpha'}${k.includes('invert') ? 'Inverted' : ''}`
}

const shown = (v: number) => String(Math.round(v * 100) / 100)

/** A number typed, committed on Enter or blur (the engine round-trip per edit, not per keystroke); the parent keys it by the value, so a
 *  value that moved (an edit, an undo, another frame) remounts it fresh. */
export function NumField({ value, step = 1, onCommit, label }: { value: number; step?: number; onCommit: (v: number) => void; label: string }) {
  const [draft, setDraft] = useState(shown(value))
  const commit = () => { const v = Number(draft); if (Number.isFinite(v) && v !== value) onCommit(v); else setDraft(shown(value)) }
  return <input type="number" step={step} value={draft} aria-label={label} onChange={(e) => setDraft(e.target.value)} onBlur={commit}
    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit() } }} />
}

// ------------------------------------------------------------------ Properties
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

function PropertiesBody() {
  const props = useComposition((s) => s.props)
  const keysOf = useComposition((s) => s.keysOf)
  return (
    <div className="comp-props">
      <div className="verbs"><CommandRow ids={['anim.final.key.position', 'anim.final.key.opacity']} /><Help text="Drag the layer on the frame to move it. ◆ keys a property at the playhead; each key can be eased, held or linear." /></div>
      {props.map((p) => <PropRow key={p.path} p={p} keys={keysOf[p.path] ?? []} />)}
      {!props.length && <span className="hint">reading…</span>}
    </div>
  )
}

// ------------------------------------------------------------------ Masks
/** AE2c: one mask of the selected layer — feather, opacity, expansion, mode, inverted, follow (D116), remove (each one engine command). */
function MaskRow({ m }: { m: MaskInfo }) {
  const busy = useComposition((s) => s.busy)
  const selected = useComposition((s) => s.selectedMask === m.uid)
  return (
    <li className={`comp-mask${selected ? ' selected' : ''}`} data-mask={m.uid} data-animated={m.animated ? 'true' : undefined} onClick={() => cp().selectMask(m.uid)}>
      <span className="name" title="Selected: its outline is brighter on the frame; drag its points there">{m.name} <span className="hint">· {m.vertices.length} points</span>{m.animated && <span className="keyed" title="The shape is keyed over the shot: it follows">· follows</span>}</span>
      <select value={MASK_MODES.includes(m.mode) ? m.mode : 'Add'} title="Mode: Add keeps what is inside, Subtract cuts it, Intersect keeps only what every mask shares" disabled={busy} onClick={(e) => e.stopPropagation()} onChange={(e) => void cp().setMaskMode(m.uid, e.target.value)}>
        {MASK_MODES.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <label className="inv" title="Inside and outside swapped"><input type="checkbox" checked={m.inverted} disabled={busy} onChange={(e) => void cp().invertMask(m.uid, e.target.checked)} /> inverted</label>
      <span className="fields">
        <label title="The edge softened over this many pixels">feather <NumField key={`f:${m.feather}`} value={m.feather} step={1} onCommit={(v) => void cp().setMaskField(m.uid, 'feather', Math.max(0, v))} label={`${m.name} feather`} /></label>
        <label title="How much the mask counts, 0–100">opacity <NumField key={`o:${m.opacity}`} value={m.opacity} step={1} onCommit={(v) => void cp().setMaskField(m.uid, 'opacity', Math.max(0, Math.min(100, v)))} label={`${m.name} opacity`} /></label>
        <label title="The edge grown (or shrunk, negative) by this many pixels">expand <NumField key={`e:${m.expansion}`} value={m.expansion} step={1} onCommit={(v) => void cp().setMaskField(m.uid, 'expansion', v)} label={`${m.name} expansion`} /></label>
      </span>
      <button type="button" className="quiet" title="Follow the motion: EffectCraft tracks what is inside this mask from the playhead to the end and keys its shape on every frame" disabled={busy}
        onClick={(e) => { e.stopPropagation(); cp().selectMask(m.uid); void cp().trackMask() }}>follow</button>
      <button type="button" className="quiet danger" title="Remove this mask" disabled={busy} onClick={(e) => { e.stopPropagation(); void cp().removeMask(m.uid) }}>×</button>
    </li>
  )
}

function MasksBody() {
  const masks = useComposition((s) => s.masks)
  const tool = useComposition((s) => s.maskTool)
  const view = useComposition((s) => s.maskView)
  return (
    <div className="comp-masks">
      <div className="verbs">
        <CommandRow ids={['anim.final.mask.rect', 'anim.final.mask.ellipse', 'anim.final.mask.poly', 'anim.final.mask.layer', 'anim.final.mask.object', 'gap', 'anim.final.mask.track']} active={tool === 'off' ? undefined : `anim.final.mask.${tool}`} />
        <CommandButton id="anim.final.mask.view" active={view === 'fill'} />
        <Help text={MASK_TOOLS_HELP} />
      </div>
      {masks.length ? <>
        <div className="list-head"><span>{masks.length} mask{masks.length === 1 ? '' : 's'}, applied in order</span><Help text={MASKS_HELP} /></div>
        <ul className="comp-mask-list">{masks.map((m) => <MaskRow key={m.uid} m={m} />)}</ul>
      </> : <span className="hint">No mask on this layer. <Help text={MASKS_HELP} /></span>}
    </div>
  )
}

// ------------------------------------------------------------------ Passes (D118, AE4a)
const when = (iso?: string) => (iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '')

/** AE4e: the Passes part on a processing layer — what it is, whether the layers below changed since, run again or drop it. */
function ProcessingBody({ layer }: { layer: number }) {
  const r = useComposition((s) => s.processingOf(layer))
  const stale = useComposition((s) => s.processingStale(layer))
  const point = useComposition((s) => s.comp?.layers.find((l) => l.id === r?.above)?.name)
  if (!r) return null
  return (
    <div className="comp-passes comp-processing" data-processing={r.id} data-stale={stale ? 'true' : undefined}>
      <span className="hint">{PASS_LABEL[r.preset as PassPreset] ?? r.preset} · {r.strength} · over everything from {point ?? r.above} down · {when(r.made_at)}
        {stale && <strong className="stale" title="A layer below changed since this was rendered: run the pass again to catch up"> · stale</strong>}</span>
      <div className="verbs">
        <CommandRow ids={['anim.final.proc.again', 'anim.final.proc.remove']} />
        <Help text="A processing layer is a pass over the picture as composited from its layer down, frozen as footage above that layer. The layers below stay editable; when one changes, this reads stale until you run it again (the same pass and strength). It takes the same passes as a layer: Clean up, Creative." />
      </div>
    </div>
  )
}

function PassesBody() {
  const finalId = useComposition((s) => s.finalId)
  const selected = useComposition((s) => s.selected)
  const proc = useComposition((s) => (s.selected !== null ? s.processingOf(s.selected) : null))
  const lid = useComposition((s) => s.finalLayerId())
  const point = useComposition((s) => s.pointLayerId())
  const scope = useComposition((s) => s.passScope)
  const layer = useComposition((s) => s.final?.layers.find((x) => x.id === s.finalLayerId()))
  const pointLayer = useComposition((s) => s.final?.layers.find((x) => x.id === s.pointLayerId()))
  const existing = useComposition((s) => (s.final?.processing ?? []).find((p) => p.above === s.pointLayerId()))
  const preset = useComposition((s) => s.passPreset)
  const strength = useComposition((s) => s.passStrength)
  const busy = useComposition((s) => s.busy)
  const target = scope === 'below' ? point : lid
  const running = useSession((s) => Object.values(s.jobs).find((j) => j.kind === 'layer_pass' && j.origin?.ref === finalId && (j.origin?.payload as { layer?: string } | undefined)?.layer === target && (j.status === 'queued' || j.status === 'running')))
  const hasLine = useComposition((s) => !!s.comp?.audio.some((a) => a.final_layer === s.finalLayerId()))
  const mouth = useComposition((s) => s.passMouth)
  const mm = useSession((s) => (s.capabilities?.experimental as { mouth_model?: { available: boolean; why: string | null; seconds_per_77: number; licence: string } } | undefined)?.mouth_model)
  if (proc && selected !== null) return <ProcessingBody layer={selected} />
  if (!point) return <span className="hint">Not on this layer. <Help text="A pass runs on a character layer or the plate, or over the stack from any layer down (a processing layer) — a matte is made with its character, the shadows come from the Stage." /></span>
  const below = scope === 'below'
  const takes = (!below && layer ? (layer.takes ?? []) : []) as unknown as Take[]
  const source = (!below && layer ? layer.source : null) ?? null
  const isFigure = !below && layer?.kind === 'figure'
  const off = (p: typeof PASSES[number]) => below ? !!p.head : (!lid || (p.head && !isFigure) || (p.id === 'lipsync' && !hasLine))
  const head = !below && PASSES.find((p) => p.id === preset)?.head
  return (
    <div className="comp-passes" data-layer={target ?? point} data-scope={scope}>
      <div className="pass-scope">
        <span className="segmented" role="group" aria-label="what the pass runs over" data-scope={scope}>
          <button type="button" className={!below ? 'active' : ''} aria-pressed={!below} title="The pass over this layer's own frames; its take becomes the layer's source" onClick={() => cp().setScope('layer')}>this layer</button>
          <button type="button" className={below ? 'active' : ''} aria-pressed={below} title={`The pass over the picture as composited from ${pointLayer?.name ?? 'this layer'} down, frozen as a processing layer above it (stale when a layer below changes)`} onClick={() => cp().setScope('below')}>everything below</button>
        </span>
        <Help text="This layer: the pass reads the layer's frames and writes a take it shows. Everything below: the composition is rendered with only this layer and the ones under it, the pass runs over that picture, and the result sits above this layer as a processing layer — the layers below stay editable, the processing layer reads stale when one of them changes (run it again). Clean up and Creative run both ways; Face and Lip-sync need a character layer." />
      </div>
      <div className="pass-tiles" role="radiogroup" aria-label="the pass">
        {PASSES.map((p) => <button key={p.id} type="button" className={`pass-tile${preset === p.id ? ' active' : ''}`} role="radio" aria-checked={preset === p.id} disabled={off(p)} data-pass={p.id}
          title={off(p) ? (below || (p.head && !isFigure) ? 'The face pass renders a character\'s head: a character layer, not the stack below' : !lid ? 'A pass on this layer: a character layer or the plate — or everything below' : 'Attach a line to this layer first (Layers › Attach a line…)') : p.hint}
          onClick={() => !off(p) && cp().setPass(p.id, p.strength)}>{p.label}</button>)}
      </div>
      {preset === 'lipsync' && !below && <div className="pass-mouth">
        <span className="hint">mouth</span>
        <span className="segmented" role="group" aria-label="the mouth" data-mouth={mouth}>
          <button type="button" className={mouth === 'head' ? 'active' : ''} aria-pressed={mouth === 'head'} title="A talking head of the reference speaks the line (S2V) and drives the mouth as Wan Animate's face video (E29b L2h)" onClick={() => cp().setMouth('head')}>talking head</button>
          <button type="button" className={mouth === 'model' ? 'active' : ''} aria-pressed={mouth === 'model'} disabled={!mm?.available}
            title={mm?.available ? `LatentSync 1.5 redraws the mouth on the rendered head (E29b L3a: the most natural to the eye) — about ${Math.round(mm.seconds_per_77)} s per 77 frames, the engine stopped meanwhile. ${mm.licence}` : (mm?.why ?? 'the lip-sync model is not set up (scripts/lipsync-setup.ps1)')}
            onClick={() => mm?.available && cp().setMouth('model')}>the model</button>
        </span>
        <Help text="Two ways to move the mouth. The talking head: S2V speaks the line as a close-up of the reference and Wan Animate follows that face (the mouth can look exaggerated at this size). The model: the head is rendered calm, then LatentSync redraws the mouth from the line — a separate tool in its own venv, the engine stopped while it runs; full variant only (its weights are OpenRAIL++)." />
      </div>}
      <div className="verbs">
        {!head && <label title="How much the pass is let change the picture (0.02–0.9)">strength <NumField key={`s:${strength}`} value={strength} step={0.05} onCommit={(v) => cp().setPass(preset, Math.max(0.02, Math.min(0.9, v)))} label="pass strength" /></label>}
        <CommandRow ids={['anim.final.pass.run']} />
        {running && <span className="hint" data-pass-running>{running.status === 'queued' ? 'queued' : `${Math.round((running.progress ?? 0) * 100)} %`} · {running.progress_text ?? 'the pass runs'}</span>}
        <Help text={PASSES_HELP} />
      </div>
      {below && existing && <span className="hint" data-existing-processing={existing.id}>A processing layer from here down exists ({PASS_LABEL[existing.preset as PassPreset] ?? existing.preset} · {existing.strength}); running again replaces it.</span>}
      {!below && <ul className="take-list">
        <li className={`take${source === null ? ' shown' : ''}`} data-take="original">
          <span className="name">Original <span className="hint">· as performed</span></span>
          {source !== null ? <button type="button" className="quiet" title="Show the original frames" disabled={busy} onClick={() => void cp().useTake(null)}>✓ show</button> : <span className="hint">shown</span>}
        </li>
        {takes.map((t) => (
          <li key={t.id} className={`take${source === t.id ? ' shown' : ''}`} data-take={t.id}>
            <span className="name">{PASS_LABEL[t.preset as PassPreset] ?? t.preset} <span className="hint">· {t.head ? (t.lines?.length ? `${t.lines.length} line${t.lines.length === 1 ? '' : 's'}${(t.mouth as PassMouth | undefined) === 'model' ? ', the model' : ''}` : (t.mouth as PassMouth | undefined) === 'model' ? "the model's mouth" : 'the head') : t.strength} · {when(t.made_at)}</span></span>
            {source !== t.id ? <button type="button" className="quiet" title="Show this take" disabled={busy} onClick={() => void cp().useTake(t.id)}>✓ show</button> : <span className="hint">shown</span>}
            <button type="button" className="quiet danger" title="Drop this take (its frames too)" disabled={busy} onClick={() => void cp().dropTake(t.id)}>×</button>
          </li>))}
      </ul>}
    </div>
  )
}

// ------------------------------------------------------------------ Layers
function LayerEditor({ l }: { l: CompLayer }) {
  const tab = useComposition((s) => s.editorTab)
  return (
    <div className="layer-editor" data-layer={l.id} onClick={(e) => e.stopPropagation()}>
      <span className="segmented" role="group" aria-label="What to edit">
        {TABS.map(([id, label, hint]) => <button key={id} type="button" className={tab === id ? 'active' : ''} aria-pressed={tab === id} title={hint} onClick={() => cp().setEditorTab(id)}>{label}</button>)}
      </span>
      {tab === 'props' ? <PropertiesBody /> : tab === 'masks' ? <MasksBody /> : tab === 'effects' ? <EffectsBody /> : <PassesBody />}
    </div>
  )
}

/** D118 (AE4b): the shot's voiced lines as a picker — a menu at the pointer; a line attaches at the playhead, bound to its speaker's layer. */
async function pickLine(at: { clientX: number; clientY: number }): Promise<void> {
  const lines = await cp().loadLines()
  const items: MenuItem[] = lines.length
    ? lines.map((ln) => ({ label: `${ln.speaker_name ?? 'someone'}: "${ln.text.length > 40 ? `${ln.text.slice(0, 40)}…` : ln.text}"${ln.duration_s ? ` · ${ln.duration_s.toFixed(1)} s` : ''}${ln.layer_id ? '' : ' · no layer of theirs here'}`,
        run: () => { void cp().attachLine(ln) } }))
    : [{ label: 'No voiced line in this shot — voice one in Story · Flow (🎙)', disabled: true, run: () => {} }]
  showMenu(at, items)
}

/** D118 (AE4b): an audio layer's row — the line, where it plays, remove; no blend, matte or parent. */
function AudioRow({ l, a }: { l: CompLayer; a: NonNullable<ReturnType<typeof cp>['comp']>['audio'][number] }) {
  const selected = useComposition((s) => s.selected === l.id)
  const busy = useComposition((s) => s.busy)
  const menu = (): MenuItem[] => [{ cmd: 'anim.final.trimIn' }, { cmd: 'anim.final.trimOut' }, sep, { label: 'Remove the line', danger: true, run: () => { void cp().removeAudio(l.id) } }]
  return (
    <li className={`audio${selected ? ' selected' : ''}`} data-layer={l.id} data-audio={a.asset_id} data-index={l.index} onClick={() => cp().select(selected ? null : l.id)}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); cp().select(l.id); showMenu(e, menu()) }}>
      <span className="sw on" title="A spoken line: it plays where its bar sits on the lanes">🔊</span>
      <span className="name" title={`${a.text || l.name} · plays ${l.in.toFixed(2)}–${l.out.toFixed(2)} s`}>{l.name}</span>
      <span className="hint">{l.in.toFixed(2)}–{l.out.toFixed(2)} s</span>
      <button type="button" className="quiet danger" title="Remove the line from the composition" disabled={busy} onClick={(e) => { e.stopPropagation(); void cp().removeAudio(l.id) }}>×</button>
    </li>
  )
}

function LayerRow({ l }: { l: CompLayer }) {
  const selected = useComposition((s) => s.selected === l.id)
  const layers = useComposition((s) => s.layers)
  const busy = useComposition((s) => s.busy)
  const audio = useComposition((s) => s.audioOf(l.id))
  const proc = useComposition((s) => s.processingOf(l.id))
  const stale = useComposition((s) => s.processingStale(l.id))
  if (audio) return <AudioRow l={l} a={audio} />
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
    { cmd: 'anim.final.mask.rect' }, { cmd: 'anim.final.mask.ellipse' }, { cmd: 'anim.final.mask.poly' }, { cmd: 'anim.final.mask.layer' }, { cmd: 'anim.final.mask.object' },
    { cmd: 'anim.final.mask.track' }, { cmd: 'anim.final.mask.view' }, sep,
    { cmd: 'anim.final.trimIn' }, { cmd: 'anim.final.trimOut' }, { cmd: 'anim.final.before' }, { cmd: 'anim.final.pass.run' }, { cmd: 'anim.final.proc.again' }, { cmd: 'anim.final.proc.remove' }, sep,
    { cmd: 'anim.final.undo' }, { cmd: 'anim.final.redo' },
  ]
  return (
    <li className={selected ? 'selected' : ''} data-layer={l.id} data-index={l.index} data-processing={proc ? 'true' : undefined} data-stale={stale ? 'true' : undefined}
      onClick={() => cp().select(selected ? null : l.id)} onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); cp().select(l.id); showMenu(e, menu()) }}>
      <button type="button" className={`sw ${on('video') ? 'on' : ''}`} title="Video: the layer is shown" disabled={busy} aria-pressed={on('video')}
        onClick={(e) => { e.stopPropagation(); void cp().layerSwitch(l.id, 'video', !on('video')) }}>◉</button>
      <button type="button" className={`sw ${on('solo') ? 'on' : ''}`} title="Solo: only the soloed layers are shown" disabled={busy} aria-pressed={on('solo')}
        onClick={(e) => { e.stopPropagation(); void cp().layerSwitch(l.id, 'solo', !on('solo')) }}>S</button>
      <button type="button" className={`sw ${on('locked') ? 'on' : ''}`} title="Lock: the layer cannot be changed" disabled={busy} aria-pressed={on('locked')}
        onClick={(e) => { e.stopPropagation(); void cp().layerSwitch(l.id, 'lock', !on('locked')) }}>🔒</button>
      <span className="name" title={`${l.name} · ${l.type ?? 'layer'} · in ${l.in.toFixed(2)} s, out ${l.out.toFixed(2)} s`}>{l.name}{stale && <strong className="stale" title="A layer below changed since this processing layer was rendered: run it again (Passes)"> · stale</strong>}</span>
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
      {selected && <LayerEditor l={l} />}
    </li>
  )
}

export function LayersSection() {
  const level = useComposition((s) => s.level)
  const comp = useComposition((s) => s.comp)
  const layers = useComposition((s) => s.layers)
  if (level !== 'final' || !comp) return <span className="hint">Not at the Final level. <Help text="In the Shot section, a final shot's Open in Final opens its composition here: the layers, each one's properties, masks and effects." /></span>
  return (
    <div className="comp-layers">
      <div className="verbs"><CommandRow ids={['anim.final.undo', 'anim.final.redo', 'gap', 'anim.final.layer.up', 'anim.final.layer.down', 'anim.final.layer.hide', 'anim.final.layer.solo', 'anim.final.layer.lock', 'gap', 'anim.final.trimIn', 'anim.final.trimOut']} />
        <button type="button" className="quiet" data-attach-line title="Attach a voiced line of this shot as an audio layer at the playhead (D118): move it on its lane, trim its ends; the render carries it"
          onClick={(e) => { const at = { clientX: e.clientX, clientY: e.clientY }; void pickLine(at) }}>Attach a line…</button>
        <Help text="Top to bottom as composited. Click a row to open its editor under it (Properties · Masks · Effects · Passes); click again to fold it. A row's right-click menu orders it. A line attached here is an audio layer: it plays where its bar sits on the lanes, and the lip-sync pass reads it." /></div>
      <ul className="comp-layer-list">{layers.map((l) => <LayerRow key={l.id} l={l} />)}</ul>
    </div>
  )
}
