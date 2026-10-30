// Animate suite (11): Panel (Inputs / Model / Length & Size / Presets / Clips), Strip (view, speed, loop, onion, counter),
// Stage (Mediabunny player · filmstrip · compare, transport, timeline with in/out, S/E, beats and harvested pins, live
// jobs), Inspector (Clip / Frames / Lineage). Every action is a registry command (animateCommands.ts, D32).
// D121 (proto01_animate 26 §5.3): this suite is Animate's Performance level, a mode of its own — its column (Shot · Performance · Clips ·
// Selection), the player, and the foot that follows the Performance card (Image to video · Stage clip · Final shot). Clay is the stage
// suite (StageParts.ClayColumn), Final the final suite (FinalSuite.tsx).
import { Help } from '../../frame/Help'
import { useStageActive } from '../../frame/stageKeep'
import { X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Clip } from '../../api/types'
import { CommandButton, CommandCard, CommandRow } from '../../frame/CommandButton'
import { useMakeFor } from '../../store/origin'
import { useStory } from '../story/storyStore'
import { PresetPanel } from '../../frame/PresetPanel'
import { fieldGlyph } from '../../frame/presetGlyphs'
import { handleKeysAt, markUsed, runCommand } from '../../frame/commands'
import { inField, primaryInField } from '../../frame/fieldKeys'
import { showMenu } from '../../frame/ContextMenu'
import { WindowsView } from './WindowsView'
import type { SuiteParts } from '../../frame/suiteParts'
import { byOrder, shortName } from '../../store/modelCaps'
import { useSession } from '../../store/session'
import { clipMenu, playerMenu } from './animateCommands'
import { CAMERA_MOVES, DEFAULT_CAMERA, fmtTime, modelRules, MOTION_CHIPS, useAnimate, visibleClips, type AnimPanel, type CameraMove } from './animateStore'
import { ClipFoot, StageClipCard, useStageLoad } from '../stage/StageParts'
import { ShotHead } from '../stage/ShotStepper'
import { FinalSection, FinalShotFoot } from '../stage/FinalPanel'
import { useAnimRoute, type AnimRoute } from './routeStore'
import { Player } from './Player'
import { Timeline as TimelineView, TransportBar, type TLMarker, type TLRow } from './Timeline'
import { AnimColumn, Sec } from './column'
import './animate.css'
import { onlyAssets, useDropTarget, type DragPayload } from '../../frame/drag'
import { beatDrop, endDrop, startDrop } from '../../frame/dropRules'
import { navigate } from '../../frame/router'
import { registerKeyHost } from '../../frame/keyHosts'

const an = () => useAnimate.getState()
const EMPTY_PINS: { frame: number; asset_id: string }[] = []

// ------------------------------------------------------------------ Panel · Inputs (11 §3a)
function Slot({ which }: { which: 'start' | 'end' }) {
  const id = useAnimate((s) => s.panel[which])
  const asset = useAnimate((s) => (id ? s.assets[id] : undefined))
  const set = (v: string | null) => (which === 'start' ? an().setStart(v) : an().setEnd(v))
  markUsed(which === 'start' ? 'anim.clearStart' : 'anim.clearEnd')     // D90 (01 §11.3): the ✕ and the slot's right-click run the command
  const verdict = (p: DragPayload) => (which === 'start' ? startDrop(p) : endDrop(p))   // D71: clips are not frames; the ghost says so
  const { ref, over } = useDropTarget((p) => onlyAssets(p) && verdict(p).verdict.ok, (p) => {
    if (which === 'end') { set(endDrop(p).end ?? null); return }
    const r = startDrop(p); set(r.start ?? null); if (r.end && !an().panel.end) an().setEnd(r.end)
  }, (p) => verdict(p).verdict)
  return (
    <div ref={ref} className={`slot${over ? ' over' : ''}`} onContextMenu={(e) => { if (id) showMenu(e, [which === 'start' ? { cmd: 'anim.clearStart' } : { cmd: 'anim.clearEnd' }, { cmd: 'anim.swap' }]) }}
      title={which === 'start' ? 'Start frame: drop a picture from the Bin, or Set as the start frame in its right-click menu' : 'End frame (optional): drop a picture from the Bin, or Use as the end frame in its right-click menu — enables first/last-frame mode'}>
      <span className="tag">{which === 'start' ? 'S' : 'E'}</span>
      {id ? <>
        <img src={api.thumbUrl(id, 512)} alt="" />
        <span className="meta">{asset ? `${asset.w}×${asset.h}${asset.kind === 'video' ? ' · a clip (use a frame)' : ''}` : id}</span>
        <button className="quiet x" title={`Clear ${which} frame`} aria-label={`Clear ${which} frame`} onClick={() => runCommand(which === 'start' ? 'anim.clearStart' : 'anim.clearEnd')}><X size={14} /></button>
      </> : <span className="cap">{which === 'start' ? 'start frame' : 'end frame (optional)'}<br /><small>{which === 'start' ? 'drop a tile · Shift+A' : 'drop a tile · Shift+Z'}</small></span>}
    </div>
  )
}

function InputsTab() {
  const p = useAnimate((s) => s.panel)
  const assets = useAnimate((s) => s.assets)
  const caps = useSession((s) => s.capabilities?.i2v)
  const cur = caps?.models[p.model_id]
  const beats = !!cur?.recipes.beats                                       // D65: keyframe beats where the spec says so
  const beatModel = byOrder(caps?.models).find(([, m]) => m.recipes.beats)?.[1]
  const cfgPresets = Object.values(cur?.preset_params ?? {}).filter((x) => (x.cfg_high ?? 1) > 1 || (x.cfg_low ?? 1) > 1).map((x) => x.label.split(' · ')[0])
  const { ref: beatRef, over: beatOver } = useDropTarget((d) => onlyAssets(d) && beatDrop(d).verdict.ok, (d) => { const ids = beatDrop(d).take; ids.forEach((id, k) => an().addBeat(id, Math.round(an().panel.frames * (k + 1) / (ids.length + 1)))) }, (d) => beatDrop(d).verdict)
  return (
    <div className="anim-form">
      <div className="slots full"><Slot which="start" /><span className="slot-swap"><CommandButton id="anim.swap" /></span><Slot which="end" /></div>
      {p.end && cur && !beats && <span className="hint">First/last-frame on {cur.short}: a large pose or composition gap morphs mid-clip — try {beatModel ? `${beatModel.short} beats` : 'a different end frame'} or a shorter clip when it does (11 §3a).</span>}
      <label>prompt</label>
      <div>
        <textarea value={p.prompt} onChange={(e) => an().set({ prompt: e.target.value })} placeholder="motion, camera, mood — e.g. she turns toward the window, soft push-in" />
        <div className="chip-row">{MOTION_CHIPS.map((c) => <button key={c} onClick={() => an().set({ prompt: (p.prompt ? p.prompt.replace(/[\s,]*$/, '') + ', ' : '') + c })} title="append to the prompt">{c}</button>)}</div>
      </div>
      <label>negative</label>
      <div>
        <label className="chk"><input type="checkbox" checked={p.use_negative} onChange={(e) => an().set({ use_negative: e.target.checked })} /> write my own</label>
        {p.use_negative ? <textarea value={p.negative} onChange={(e) => an().set({ negative: e.target.value })} placeholder="what to avoid" /> : <span className="hint">{cur ? `${cur.short} uses its stock negative list${cfgPresets.length ? `; it only matters above CFG 1 (${cfgPresets.join(' / ')})` : ''}.` : 'the model uses its stock negative list.'}</span>}
      </div>
      {beats && <>
        <label>beats</label>
        <div>
          <div className="beats">
            {p.beats.map((b, i) => <div key={i} className="beat">
              <input type="number" min={1} max={p.frames - 1} value={b.frame} onChange={(e) => an().set({ beats: p.beats.map((x, k) => k === i ? { ...x, frame: Math.max(1, Math.min(p.frames - 1, Number(e.target.value) || 1)) } : x) })} title="frame index" />
              <span className="row"><img src={api.thumbUrl(b.asset_id, 256)} alt="" /><small>{assets[b.asset_id] ? `${assets[b.asset_id].w}×${assets[b.asset_id].h}` : b.asset_id}</small></span>
              <input type="range" min={0.1} max={1} step={0.05} value={b.strength} onChange={(e) => an().set({ beats: p.beats.map((x, k) => k === i ? { ...x, strength: Number(e.target.value) } : x) })} title={`strength ${b.strength.toFixed(2)}`} />
              <button className="quiet" title="Remove beat" aria-label="Remove beat" onClick={() => an().removeBeat(i)}><X size={14} /></button>
            </div>)}
          </div>
          <div ref={beatRef} className={`slot${beatOver ? ' over' : ''}`} style={{ aspectRatio: 'auto', minHeight: 40, marginTop: 6 }}>
            drop frames here as mid-clip keyframes (strength 0.3–1.0; set each one's frame in its number field — the ♦ on the timeline shows where)
          </div>
        </div>
      </>}
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Model (11 §3b)
function ModelTab() {
  const p = useAnimate((s) => s.panel)
  const caps = useSession((s) => s.capabilities?.i2v)
  const models = byOrder(caps?.models)                                    // C3 / D65: what this build offers (the open build lists Wan only)
  const cur = caps?.models[p.model_id]
  const pp = cur?.preset_params[p.preset]                                 // D65: the preset's own steps / split / CFG / shift
  const loraHigh = !!pp?.lora_high
  const distilled = Object.entries(cur?.preset_params ?? {}).find(([, x]) => x.lora_high)     // the preset whose high expert runs a distilled LoRA
  const cap1 = (k: string) => k.charAt(0).toUpperCase() + k.slice(1)
  const presetLabel = (k: string) => cur?.presets[k] ?? k
  return (
    <div className="anim-form">
      <label>model</label>
      <div className="model-grid">
        {models.map(([id, m]) => {
          const r = modelRules(id)
          return <button key={id} className={`model-card${p.model_id === id ? ' active' : ''}`} onClick={() => an().setModel(id)}>
            <b>{m.short}{m.label.includes(' · ') ? ` (${m.label.split(' · ').slice(1).join(' · ')})` : ''}</b>
            <small>{m.label}</small>
            <small>{r.frames} f @ {r.fps} fps · {r.draft[0]}×{r.draft[1]}{m.recipes.beats ? ' · keyframe beats' : m.recipes.flf ? ' · FLF' : ''}</small>
            <span className={`badge ${m.health} health`}>{m.health === 'missing' ? `fetch ${m.approx_gb} GB` : m.health}</span>
          </button>
        })}
        {/* D99 (UX0 #15): the H3 hero card stays hidden until its graph and weights are wired (it was a permanently locked card) */}
      </div>
      <label>preset</label>
      <div className="segmented">{(['draft', 'motion', 'quality'] as const).map((k) => <button key={k} className={p.preset === k ? 'active' : ''} onClick={() => an().set({ preset: k, steps: null, cfg: null })} title={presetLabel(k)}>{k}</button>)}</div>
      <span className="hint">{presetLabel(p.preset)}</span>
      {cur?.recipes?.camera && <>
        <label>camera</label>
        <div className="row camera-move">
          <select aria-label="camera move" value={p.camera?.move ?? DEFAULT_CAMERA.move} onChange={(e) => an().set({ camera: { move: e.target.value as CameraMove, speed: p.camera?.speed ?? DEFAULT_CAMERA.speed } })}>
            {CAMERA_MOVES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <input type="number" aria-label="camera speed" min={0.1} max={3} step={0.1} value={p.camera?.speed ?? DEFAULT_CAMERA.speed} onChange={(e) => an().set({ camera: { move: p.camera?.move ?? DEFAULT_CAMERA.move, speed: Math.min(3, Math.max(0.1, Number(e.target.value) || 1)) } })} />
          <span>× speed</span>
          <Help text={"This model moves the camera as told (D156): a pan, a tilt, a zoom or a roll at a speed — the prompt alone does not move it. Static holds the camera. The clip's tone is matched to the start image on the way out."} />
        </div>
      </>}
      <h4 className="full sect">advanced</h4>
      <label>steps</label>
      <div className="row"><input type="number" min={1} max={60} placeholder="preset" value={p.steps ?? ''} onChange={(e) => an().set({ steps: e.target.value === '' ? null : Number(e.target.value) })} /><span className="hint" style={{ margin: 0 }}>empty = the preset's steps{pp?.split != null ? ' (split high / low in the same ratio)' : ''}</span></div>
      {pp?.cfg_high != null && <>
        <label>CFG</label>
        <div className="row"><input type="number" min={1} max={12} step={0.5} placeholder={loraHigh ? `${pp.cfg_high} (distilled)` : String(pp.cfg_high)} value={p.cfg ?? ''} onChange={(e) => an().set({ cfg: e.target.value === '' ? null : Number(e.target.value) })} disabled={loraHigh} /><span className="hint" style={{ margin: 0 }}>high expert only{distilled ? `; ${cap1(distilled[0])} runs at CFG ${distilled[1].cfg_high ?? 1}` : ''}</span></div>
      </>}
      <label>shift</label>
      <div className="row"><input type="number" min={0.5} max={12} step={0.5} placeholder={pp?.shift != null ? String(pp.shift) : 'scheduler'} value={p.shift ?? ''} onChange={(e) => an().set({ shift: e.target.value === '' ? null : Number(e.target.value) })} /></div>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Length & Size (11 §3c)
function EstimateLine() {
  const pv = useAnimate((s) => s.preview)
  const err = useAnimate((s) => s.previewError)
  const count = useAnimate((s) => s.panel.count)
  if (err) return <div className="estimate-line"><span className="missing">{err}</span></div>
  if (!pv) return <div className="estimate-line">preparing…</div>
  const secs = pv.estimate.seconds ?? 0
  return (
    <div className="estimate-line">
      <span>runs at <b>{pv.width}×{pv.height}</b> · <b>{pv.frames}</b> f @ {pv.fps} fps ({(pv.frames / pv.fps).toFixed(1)} s)</span>
      <span>{pv.label}</span>
      <span>≈ <b>{Math.round(secs / 60)} min</b>{count > 1 ? ` × ${count}` : ''} <small>({pv.estimate.source})</small></span>
      {pv.missing.length > 0 && <span className="missing">missing: {pv.missing.map((m) => m.model_id).join(', ')} <button onClick={() => navigate({ suite: 'models' })}>Fetch {pv.missing.reduce((a, m) => a + (m.approx_gb ?? 0), 0).toFixed(0)} GB</button></span>}
    </div>
  )
}

function LengthTab() {
  const p = useAnimate((s) => s.panel)
  useSession((s) => s.capabilities?.i2v)                                  // re-render when the server's rules arrive (C25)
  const r = modelRules(p.model_id)
  const num = (k: keyof AnimPanel, lo: number, hi: number) => (e: React.ChangeEvent<HTMLInputElement>) => an().set({ [k]: Math.max(lo, Math.min(hi, Number(e.target.value) || lo)) } as Partial<AnimPanel>)
  return (
    <div className="anim-form">
      <label>tier</label>
      <div className="tiers">{(['draft', 'hd', 'custom'] as const).map((t) => <button key={t} className={p.tier === t ? 'active' : ''} onClick={() => an().setTier(t)} title={t === 'draft' ? `${r.draft[0]}×${r.draft[1]} (D18)` : t === 'hd' ? `${r.hd[0]}×${r.hd[1]} — slow on 16 GB` : 'type a size'}>{t === 'hd' ? 'HD' : t}</button>)}</div>
      <label>orientation</label>
      <div className="segmented">{(['landscape', 'portrait', 'square'] as const).map((o) => <button key={o} className={p.orientation === o ? 'active' : ''} onClick={() => an().setTier(p.tier === 'custom' ? 'draft' : p.tier, o)}>{o}</button>)}</div>
      <label>size</label>
      <div className="row">
        <input type="number" min={128} max={1920} step={r.mult} value={p.width} onChange={(e) => an().set({ width: Number(e.target.value) || r.mult * 8, tier: 'custom' })} /> ×
        <input type="number" min={128} max={1920} step={r.mult} value={p.height} onChange={(e) => an().set({ height: Number(e.target.value) || r.mult * 8, tier: 'custom' })} />
        <span className="hint" style={{ margin: 0 }}>snaps to ×{r.mult}</span>
      </div>
      <label>frames</label>
      <div className="row"><input type="number" min={9} max={257} step={r.step} value={p.frames} onChange={num('frames', 9, 257)} /><span className="hint" style={{ margin: 0 }}>{r.step}n + 1 · {(p.frames / p.fps).toFixed(1)} s</span></div>
      <label>fps</label>
      <div className="row"><input type="number" min={8} max={48} value={p.fps} onChange={num('fps', 8, 48)} /><span className="hint" style={{ margin: 0 }}>native {r.fps}; the master keeps it, conform is an export step (D27)</span></div>
      <label>seed</label>
      <div className="row">
        <div className="segmented">{(['random', 'fixed', 'increment'] as const).map((m) => <button key={m} className={p.seed_mode === m ? 'active' : ''} onClick={() => an().set({ seed_mode: m })}>{m}</button>)}</div>
        {p.seed_mode !== 'random' && <input type="number" min={1} value={p.seed} onChange={num('seed', 1, 2 ** 31)} />}
      </div>
      <label>count</label>
      <div className="row"><input type="number" min={1} max={8} value={p.count} onChange={num('count', 1, 8)} /><span className="hint" style={{ margin: 0 }}>variations per Animate (new seeds)</span></div>
      <div className="full"><EstimateLine /></div>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Presets · Clips
/** D119 (SC2): the saved Animate panels behind a +, the one applied beside it; save, apply, delete in the panel. */
function PresetsTab() {
  const caps = useSession((s) => s.capabilities)
  const presets = useAnimate((s) => s.presets)
  const last = useAnimate((s) => s.lastPreset)
  const items = presets.map((pr) => ({ id: pr.name, label: pr.name, icon: fieldGlyph('panel'), hint: `${shortName(pr.panel.model_id, caps)} · ${pr.panel.preset} · ${pr.panel.width}×${pr.panel.height}` }))
  const cur = items.find((i) => i.id === last)
  return (
    <div className="anim-presets">
      <PresetPanel label="Animate presets" size={44} showText items={items} selected={last} chosen={cur ? [cur] : []}
        title="The saved panels: model, preset, size, frames, seed mode and prompt (frames and beats are not saved) — apply one, save the current, delete"
        empty="None yet — Save the current panel keeps it under a name." saveLabel="Save the current panel…" onSave={(name) => an().savePreset(name || `Panel ${presets.length + 1}`)}
        onPick={(id) => an().applyPreset(id)}
        verbs={(f) => (f ? <button type="button" className="quiet danger" onClick={() => an().deletePreset(f)}>Delete “{f}”</button> : <span className="hint">Click a panel: it is applied; it can be deleted here.</span>)} />
      <span className="hint">{presets.length ? `${presets.length} saved` : 'No presets yet.'}</span>
    </div>
  )
}

// D90 (02 §9, A16): the clips not in the Trash, filtered by words of the prompt (D122: no keep / reject); a row's right-click has the
// clip verbs, Move to trash among them (the Catalogue's semantics: Undo in the toast)
function ClipsTab() {
  const caps = useSession((s) => s.capabilities)
  const clips = useAnimate((s) => s.clips)
  const current = useAnimate((s) => s.current)
  const live = useAnimate((s) => s.clipLive)
  const filter = useAnimate((s) => s.clipFilter)
  useEffect(() => { void an().loadClipStates() }, [])                     // the states and the Trash may have moved in the Catalogue
  const shown = useMemo(() => visibleClips(clips, live, filter), [clips, live, filter])
  const total = live ? clips.filter((c) => !c.asset_id || live[c.asset_id]).length : clips.length
  const [folded, setFolded] = useState<string | null>(null)              // AW3: the clip whose editor its row's second click folded
  return (
    <div className="clip-list">
      <div className="clip-filter">
        <input type="search" value={filter.q} aria-label="search clips" placeholder="search the prompts" onChange={(e) => an().setClipFilter({ q: e.target.value })} />
      </div>
      {shown.map((c) => {
        const on = c.id === current
        return <div key={c.id} className={`clip-item${on ? ' active' : ''}`}>
          <button className={`clip-row${on ? ' active' : ''}`} data-id={c.id} aria-expanded={on ? folded !== c.id : undefined} onContextMenu={(e) => showMenu(e, clipMenu(c.id))}
            onClick={() => { if (on) setFolded(folded === c.id ? null : c.id); else { setFolded(null); an().select(c.id) } }} title={`${c.prompt} — click: in the player, its details under it (again: folded); right-click: its verbs`}>
            {c.asset_id ? <img src={api.thumbUrl(c.asset_id, 256)} alt="" /> : <span />}
            <span>{c.prompt || '(no prompt)'}<small>{shortName(c.model_id, caps)} · {c.preset} · {c.frames} f @ {c.fps} · seed {c.seed}</small></span>
          </button>
          {on && folded !== c.id && <div className="row-editor clip-editor"><ClipSelection /></div>}{/* AW3 (D121): the clip's editor under its row, as a layer's at Final */}
        </div>
      })}
      {!total ? <span className="hint">No clips in this project yet.</span> : !shown.length ? <span className="hint">No clip matches — {total} in all.</span> : null}
    </div>
  )
}

/** The form's preview and model default, kept current while Animate's column is up. */
function useAnimateLoad(): void {
  const project = useSession((s) => s.project)
  const caps = useSession((s) => s.capabilities?.i2v)
  useEffect(() => { if (project?.open) { an().refreshPreview(); void an().loadPresets() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  // C3 / D65: no model yet, or a persisted one this build does not offer (LTX under `open`) → the variant's i2v default
  const def = useSession((s) => s.capabilities?.defaults.i2v)
  useEffect(() => { if (caps && !caps.models[an().panel.model_id]) { const next = (def && caps.models[def] ? def : '') || byOrder(caps.models)[0]?.[0]; if (next) an().setModel(next) } }, [caps, def])
}

// D95 (AN1) → D121 (proto01_animate 26 §5.3): the Performance level's column — Shot · Performance · Clips (AW3: a clip's details under its row). The Performance
// section's cards are the ways to a moving picture; the foot follows the card. Clay's column is StageParts.ClayColumn, Final's FinalSuite.
const PERFORMANCE_SECTIONS = ['shot', 'performance', 'clips'] as const   // AW3: the clip's details open under its row (the Selection section is gone)

const CARDS: { id: AnimRoute; label: string; title: string }[] = [
  { id: 'i2v', label: 'Image to video', title: 'A clip from a start (and end) image: the prompt says the motion' },
  { id: 'clip', label: 'Stage clip', title: "The stage's sequence (depth or pose) animated from one of its frames — LTX-2.3's IC-LoRA, or Wan Animate with one figure" },
  { id: 'final', label: 'Final shot', title: "The layered route: the scene split into layers — the plate, each character performed by Wan Animate, the props, the shadows — matted, assembled and composed for the Final level" },
]

/** D121: Performance's cards — what the moving picture is made from; the card chosen is the method and names the foot's verb. */
function RouteSwitch() {
  const route = useAnimRoute((r) => r.route)
  return (
    <span className="segmented perf-cards" role="group" aria-label="Performance card">
      {CARDS.map((c) => <button key={c.id} type="button" className={route === c.id ? 'active' : ''} aria-pressed={route === c.id} onClick={() => useAnimRoute.getState().set(c.id)} title={c.title}>{c.label}</button>)}
    </span>
  )
}

/** The selected clip's editor, under its row in Clips (AW3, D121): what it is and its verbs, the frames harvested from it, its lineage (UX0 #17's three folds). */
function ClipSelection() {
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  if (!clip) return <span className="hint">No clip selected. <Help text="Clips appear in the Clips section as they finish." /></span>
  return (
    <div className="clip-selection">
      <details open><summary>Clip</summary><ClipTab clip={clip} /></details>
      <details><summary>Frames</summary><FramesTab clip={clip} /></details>
      <details><summary>Lineage</summary><LineageTab clip={clip} /></details>
    </div>
  )
}

function PerformanceColumnBody({ tab }: { tab: string }) {
  useStageLoad(); useAnimateLoad()
  const route = useAnimRoute((r) => r.route)
  return (
    <AnimColumn suite="animate" sections={PERFORMANCE_SECTIONS} tab={tab}>
      <Sec id="shot" title="Shot"><ShotHead stage={route !== 'i2v'} /></Sec>{/* AW3: the stage and its steps for the stage's cards */}
      <Sec id="performance" title="Performance" tools={<RouteSwitch />}>
        {route === 'i2v' ? <><InputsTab /><h4>Model</h4><ModelTab /><h4>Length &amp; size</h4><LengthTab /><h4>Presets</h4><PresetsTab /></>
          : route === 'clip' ? <StageClipCard /> : <FinalSection />}
      </Sec>
      <Sec id="clips" title="Clips"><ClipsTab /></Sec>
    </AnimColumn>
  )
}

export function PerformanceColumn({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  return <PerformanceColumnBody tab={tab} />
}

/** D121: the foot follows Performance's card — Animate ▶ / Queue for image to video, Render clip ▶ for the stage clip, the next step for the
 *  final shot. Ctrl+Enter is the card's verb (anim.run). */
export function PerformanceFoot() {
  const route = useAnimRoute((r) => r.route)
  return route === 'clip' ? <ClipFoot /> : route === 'final' ? <FinalShotFoot /> : <PrimaryAction />
}

function PrimaryAction() {
  const p = useAnimate((s) => s.panel)
  const pv = useAnimate((s) => s.preview)
  const err = useAnimate((s) => s.previewError)
  const project = useSession((s) => s.project)
  markUsed('anim.animate'); markUsed('anim.stage')
  const reason = !project?.open ? 'no project' : !p.start ? 'set a start frame' : err ? err : !pv ? 'preparing…' : pv.missing.length ? `weights missing: ${pv.missing.map((m) => m.model_id).join(', ')}` : null
  const eta = pv?.estimate.seconds ? `≈ ${Math.round(pv.estimate.seconds / 60)} min` : ''
  return (
    <div>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('anim.animate')} title={`Animate (Ctrl+Enter) ${eta}`}>Animate {p.count > 1 ? `${p.count} ` : ''}▶ {eta}</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}><button disabled={!!reason} onClick={() => runCommand('anim.stage')} title="Queue: add to the queue and run it later — Run now in the Dock (Ctrl+Shift+Enter)">Queue</button>{reason && <span className="disabled-why">{reason}</span>}</div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip (11 §4)
export function useAnimateKeys() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'animate') return
      if (document.querySelector('.ctx-menu')) return                     // D90: an open menu owns the arrows, Space and Enter
      if (inField(e)) { if (primaryInField(e, ['anim.run', 'anim.stage'])) e.stopImmediatePropagation(); return }   // D90 (B8): Ctrl+Enter from the prompt (D121: the card's verb)
      if (handleKeysAt('animate', e)) e.stopImmediatePropagation()   // D121: Performance's reach (animateCommands.ts) — Final's commands are its own mode's
    }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [])
}

function Strip() {
  const view = useAnimate((s) => s.view)
  const filmTrack = useAnimate((s) => s.filmTrack)
  const speed = useAnimate((s) => s.speed)
  const loop = useAnimate((s) => s.loop)
  const onion = useAnimate((s) => s.onion)
  const frame = useAnimate((s) => s.frame)
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  return (
    <>
      
      <CommandRow ids={['anim.view.player', 'anim.view.compare', 'anim.view.windows']} active={`anim.view.${view}`} />
      <CommandButton id="anim.view.filmstrip" active={filmTrack} />
      <span className="spacer" />
      {clip && view !== 'windows' && <span className="counter" style={{ fontFamily: 'var(--mono)' }}>frame {frame} / {clip.frames - 1} · {fmtTime(frame, clip.fps)} · {clip.frames} f · {clip.w}×{clip.h} @ {clip.fps} fps</span>}
      <span className="spacer" />
      <label>speed <select value={String(speed)} onChange={(e) => useAnimate.setState({ speed: Number(e.target.value) })}>{[-4, -2, -1, 0.25, 0.5, 1, 1.5, 2, 4].map((v) => <option key={v} value={String(v)}>{v < 0 ? `◀ ${-v}×` : `${v}×`}</option>)}</select></label>
      <CommandButton id="anim.loop" active={loop} />
      <CommandButton id="anim.onion" active={onion} />
    </>
  )
}
// U1 (D157): the keys are the shell's (frame/keyHosts.tsx), not the Strip's
registerKeyHost('animate', function AnimateKeys() { useAnimateKeys(); return null })

// ------------------------------------------------------------------ Stage (11 §4/§5)
function usePlayback() {
  const playing = useAnimate((s) => s.playing)
  const speed = useAnimate((s) => s.speed)
  const loop = useAnimate((s) => s.loop)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  useEffect(() => {
    if (!playing || !clip) return
    const [a, b] = [inPoint ?? 0, outPoint ?? clip.frames - 1]
    let raf = 0
    let t0 = performance.now()
    let f0 = useAnimate.getState().frame
    const tick = (t: number) => {
      const adv = Math.trunc(((t - t0) / 1000) * clip.fps * speed)
      let f = f0 + adv
      if (speed > 0 && f > b) { if (loop) { f0 = a; t0 = t; f = a } else { useAnimate.setState({ playing: false, frame: b }); return } }
      if (speed < 0 && f < a) { if (loop) { f0 = b; t0 = t; f = b } else { useAnimate.setState({ playing: false, frame: a }); return } }
      if (f !== useAnimate.getState().frame) useAnimate.setState({ frame: f })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, speed, loop, inPoint, outPoint, clip?.id, clip?.fps, clip?.frames]) // eslint-disable-line react-hooks/exhaustive-deps
}

function Filmstrip({ clip }: { clip: Clip }) {
  const frame = useAnimate((s) => s.frame)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const [a, b] = [inPoint ?? 0, outPoint ?? clip.frames - 1]
  const k = Math.max(1, Math.ceil(clip.frames / 40))
  const idx = useMemo(() => Array.from({ length: Math.ceil(clip.frames / k) }, (_, i) => Math.min(clip.frames - 1, i * k)), [clip.frames, k])
  return (
    <div className="filmstrip">
      {idx.map((n) => <button key={n} className={`${Math.abs(n - frame) < k ? 'cur' : ''}${n < a || n > b ? ' out' : ''}`} onClick={() => { an().togglePlay(false); an().setFrame(n) }} title={`frame ${n} · ${fmtTime(n, clip.fps)}`}>
        <img loading="lazy" src={api.fileUrl(`/clips/${clip.id}/frames/${n}.png?size=352`)} alt="" /><span>{n}</span>
      </button>)}
    </div>
  )
}

function Compare({ clip }: { clip: Clip }) {
  const caps = useSession((s) => s.capabilities)
  const frame = useAnimate((s) => s.frame)
  const onion = useAnimate((s) => s.onion)
  const clips = useAnimate((s) => s.clips)
  const other = useAnimate((s) => s.compareWith)
  const b = clips.find((c) => c.id === other)
  const frameB = b ? Math.round((frame / Math.max(1, clip.frames - 1)) * (b.frames - 1)) : 0
  return (
    <div className="anim-compare">
      <div className="side"><Player clip={clip} frame={frame} onion={onion} /><div className="cap">A · {clip.prompt.slice(0, 40) || clip.id} · frame {frame}</div></div>
      <div className="side">
        {b ? <Player clip={b} frame={frameB} /> : other === 'end' && clip.end_asset_id ? <img className="still" src={api.assetUrl(clip.end_asset_id)} alt="" /> : <img className="still" src={api.assetUrl(clip.start_asset_id)} alt="" />}
        <div className="cap">B ·
          <select value={other ?? 'start'} onChange={(e) => useAnimate.setState({ compareWith: e.target.value === 'start' ? null : e.target.value })}>
            <option value="start">start still</option>
            {clip.end_asset_id && <option value="end">end still</option>}
            {clips.filter((c) => c.id !== clip.id).map((c) => <option key={c.id} value={c.id}>{shortName(c.model_id, caps)} · {c.prompt.slice(0, 32) || c.id} · seed {c.seed}</option>)}
          </select>
          {b && <span>frame {frameB} (synced by time)</span>}
        </div>
      </div>
    </div>
  )
}

/** D121 (AW2): Performance's transport — the one transport (anim.*), the frame field and the counter, then the clip's in / out and its verbs. */
function Transport({ clip }: { clip: Clip }) {
  const frame = useAnimate((s) => s.frame)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const busy = useAnimate((s) => s.busy)
  const playing = useAnimate((s) => s.playing)
  return (
    <TransportBar frame={frame} last={clip.frames - 1} playing={playing} onFrame={(f) => { an().togglePlay(false); an().setFrame(f) }} counter={`frame ${frame} / ${clip.frames - 1} · ${fmtTime(frame, clip.fps)}`}>
      <CommandRow ids={['anim.setIn', 'anim.setOut', 'anim.clearInOut']} />
      <span>{inPoint !== null || outPoint !== null ? `in ${inPoint ?? 0} · out ${outPoint ?? clip.frames - 1}` : 'whole clip'}</span>
      <span className="spacer" />
      <CommandRow ids={['anim.extractFrame', 'anim.sendToEdit']} /><ClipShotVerb />
      {busy && <span>{busy}…</span>}
    </TransportBar>
  )
}

/** D121 (AW2): Performance's timeline — the one timeline: the in / out as the work area (its ends dragged), the clip's row with its start and
 *  end stills, its beats and its harvested frames (a click goes there). */
function Timeline({ clip }: { clip: Clip }) {
  const caps = useSession((s) => s.capabilities)
  const frame = useAnimate((s) => s.frame)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const pins = useAnimate((s) => s.pins[clip.id]) ?? EMPTY_PINS
  const N = clip.frames
  const markers: TLMarker[] = [{ frame: 0, glyph: 'S', title: 'start frame' },
    ...(clip.end_asset_id ? [{ frame: N - 1, glyph: 'E', title: 'end frame (FLF)' }] : []),
    ...clip.beats.map((b) => ({ frame: b.frame, glyph: '♦', title: `beat at ${b.frame} · strength ${b.strength}`, className: 'beat' })),
    ...pins.map((p) => ({ frame: p.frame, glyph: '▼', title: `extracted frame ${p.frame} — click to go there`, className: 'pin', onClick: () => { an().togglePlay(false); an().setFrame(p.frame) } }))]
  const rows: TLRow[] = [{ id: 'clip', label: shortName(clip.model_id, caps), title: clip.prompt, markers,
    bars: [{ id: 'clip', from: 0, to: N - 1, label: clip.prompt || '(no prompt)', title: `${clip.frames} f @ ${clip.fps} fps · seed ${clip.seed}` }] }]
  return <TimelineView className="timeline" span={[0, Math.max(1, N - 1)]} fps={clip.fps} frame={frame} onSeek={(f) => { an().togglePlay(false); an().setFrame(f) }}
    work={{ from: inPoint ?? 0, to: outPoint ?? N - 1, title: 'in / out', onChange: (a, b) => useAnimate.setState({ inPoint: a, outPoint: b }) }} rows={rows}
    onMenu={(e) => showMenu(e, playerMenu())} />
}

function Interim() {
  const caps = useSession((s) => s.capabilities)
  const jobs = useSession((s) => s.jobs)
  // D66: Animate's own jobs (origin suite 'animate'); jobs without an origin (queued before D66) keep showing
  const list = useMemo(() => Object.values(jobs).filter((j) => j.kind === 'i2v' && ['running', 'queued', 'staged'].includes(j.status) && (!j.origin || j.origin.suite === 'animate')).sort((a, b) => (a.status === 'running' ? -1 : b.status === 'running' ? 1 : a.created_at < b.created_at ? -1 : 1)), [jobs])
  if (!list.length) return null
  return (
    <div className="anim-interim">
      {list.map((j) => { const r = j.recipe as { model_id?: string; frames?: number; prompt_text?: string }; return <div key={j.id} className="card">
        <span>{shortName(r.model_id, caps)} · {r.frames} f · seed {j.seed} · {j.status === 'running' ? j.progress_text : j.status}</span>
        <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>
        <span>{(r.prompt_text ?? '').slice(0, 60)}</span>
      </div> })}
    </div>
  )
}

function Stage() {
  const project = useSession((s) => s.project)
  const active = useStageActive()
  useEffect(() => { if (!active && useAnimate.getState().playing) useAnimate.getState().togglePlay(false) }, [active])   // D69: hidden, kept alive: pause
  const clips = useAnimate((s) => s.clips)
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  const view = useAnimate((s) => s.view)
  const filmTrack = useAnimate((s) => s.filmTrack)
  const frame = useAnimate((s) => s.frame)
  const onion = useAnimate((s) => s.onion)
  const running = useSession((s) => Object.values(s.jobs).some((j) => j.kind === 'i2v' && j.status === 'running'))
  const startSet = useAnimate((s) => !!s.panel.start)
  const route = useAnimRoute((r) => r.route)                             // D121: the empty viewer says what the card wants
  useEffect(() => { if (project?.open) void an().loadClips() }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  // deep link ?clip=<id> (the headed check and the verification loop)
  useEffect(() => { const q = new URLSearchParams(location.search).get('clip'); if (q && clips.some((c) => c.id === q) && an().current !== q) an().select(q) }, [clips])
  usePlayback()
  if (!project?.open) return <div className="placeholder"><div><h2>Animate</h2>open or create a project to begin</div></div>
  if (view === 'windows') return <div className="anim-stage"><WindowsView /></div>          // D165: the final's frames, not a clip
  return (
    <div className="anim-stage">
      <div className="anim-view" onContextMenu={(e) => { if (clip) showMenu(e, playerMenu()) }}>
        {!clip ? <div className="anim-empty"><h2>Animate</h2>{running ? 'rendering the first clip — it opens here when the proxy is ready' : route === 'clip' ? 'pick a frame of the stage, then Render clip ▶ — the clip opens here' : route === 'final' ? "the final shot's steps are in the column — Play ▶ shows the assembled shot here" : <>set a start frame (a picture's Set as the start frame in the Bin, or drop it on Performance's start slot), write the motion, Animate ▶
          {!startSet && <div className="quick-cards"><CommandCard id="global.start.animate" hint="pick a still in the Bin" /></div>}</>}</div>
          : view === 'compare' ? <Compare clip={clip} /> : <Player clip={clip} frame={frame} onion={onion} />}
      </div>
      {clip && <Transport clip={clip} />}
      {clip && filmTrack && <Filmstrip clip={clip} />}{/* D99 (UX0 #14): the frames as a track over the timeline */}
      {clip && <Timeline clip={clip} />}
      <Interim />
    </div>
  )
}

// ------------------------------------------------------------------ Inspector (11 §6)
function ClipTab({ clip }: { clip: Clip }) {
  const caps = useSession((s) => s.capabilities?.i2v)
  const facesim = useSession((s) => s.capabilities?.facesim)
  const experimental = useSession((s) => s.capabilities?.experimental)
  const wall = (clip.timings as { wall_s?: number }).wall_s
  return (
    <div>
      <div className="verbs">{['anim.variations', 'anim.rerun', 'anim.tryOther', 'anim.toCatalogue', 'anim.trash'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <dl className="kv">
        <dt>model</dt><dd>{caps?.models[clip.model_id]?.label ?? clip.model_id} · {clip.preset}</dd>
        <dt>format</dt><dd>{clip.frames} f @ {clip.fps} fps · {clip.w}×{clip.h} · {(clip.frames / clip.fps).toFixed(1)} s</dd>
        <dt>seed</dt><dd className="mono">{clip.seed}</dd>
        <dt>prompt</dt><dd>{clip.prompt || '—'}</dd>
        <dt>rendered</dt><dd>{wall ? `${Math.round(wall)} s` : '—'} · proxy {(clip.proxy_bytes / 2 ** 20).toFixed(1)} MiB · {new Date(clip.created_at).toLocaleString()}</dd>
        <dt>frames</dt><dd className="insp-thumbs">
          <img src={api.thumbUrl(clip.start_asset_id, 256)} alt="" title="start frame — click to reuse as the next start" onClick={() => an().setStart(clip.start_asset_id)} />
          {clip.end_asset_id && <img src={api.thumbUrl(clip.end_asset_id, 256)} alt="" title="end frame — click to reuse as the next end" onClick={() => an().setEnd(clip.end_asset_id)} />}
          {clip.beats.map((b, i) => <img key={i} src={api.thumbUrl(b.asset_id, 256)} alt="" title={`beat at ${b.frame}`} />)}
        </dd>
        <dt>identity</dt><dd>
          {clip.identity?.status === 'ok' ? <><b>{clip.identity.mean?.toFixed(2)}</b> mean · min {clip.identity.min?.toFixed(2)} at frame {clip.identity.min_frame} · {clip.identity.with_face}/{clip.identity.sampled} frames with a face <span className="hint">(FaceSim, advisory; same person ≈ 0.45–0.7)</span></>
            : clip.identity ? <span className="hint">{clip.identity.status}</span> : facesim?.available ? <span className="hint">measuring…</span> : <span className="hint">FaceSim weights not fetched (scripts/fetch_facesim.py)</span>}
          {' '}<CommandButton id="anim.identity" text />
        </dd>
        <dt>clip</dt><dd className="mono">{clip.id}{clip.job_id ? ` · job ${clip.job_id}` : ''}</dd>
        <dt>next</dt><dd><CommandButton id="anim.useAsStart" text /></dd>
      </dl>
      {/* D90 (02 §9, X3): the experimental features together — Extend here, Lip-sync on the shot (Story · Shots: Make clip ▸ / the Inspector) */}
      <details className="anim-exp" open={!!clip.chained_from || !!clip.audio_asset_id}>
        <summary><span className="badge experimental">experimental</span> Extend · lip-sync</summary>
        <dl className="kv">
          <dt>extend</dt><dd><CommandButton id="anim.extend" text />{' '}
            {experimental?.extend.models[clip.model_id] ? <span className="hint">{experimental.extend.caveat}</span> : <span className="hint">this model does not continue clips</span>}</dd>
          {clip.chained_from && <><dt>continues</dt><dd className="mono">{clip.chained_from} · its first {clip.overlap} frame{clip.overlap === 1 ? '' : 's'} repeat the end of it</dd></>}
          <dt>lip-sync</dt><dd>{clip.audio_asset_id ? <><span className="badge experimental">lip-sync</span> the proxy carries the line</> : <span className="hint">made from a shot version with a voiced line: Shots › Make clip ▸ Lip-sync</span>}</dd>
        </dl>
      </details>
    </div>
  )
}

function FramesTab({ clip }: { clip: Clip }) {
  const frame = useAnimate((s) => s.frame)
  const every = useAnimate((s) => s.extractEvery)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const [a, b] = [inPoint ?? 0, outPoint ?? clip.frames - 1]
  const pins = useAnimate((s) => s.pins[clip.id]) ?? EMPTY_PINS
  const n = Math.min(24, Math.floor((b - a) / Math.max(1, every)) + 1)
  return (
    <div>
      <dl className="kv">
        <dt>current</dt><dd className="mono">frame {frame} · {fmtTime(frame, clip.fps)}</dd>
        <dt>range</dt><dd>{a} – {b} ({b - a + 1} frames)</dd>
      </dl>
      <div className="verbs"><CommandButton id="anim.extractFrame" text /><CommandButton id="anim.sendToEdit" text /></div>
      <div className="row" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <label>every</label><input type="number" min={1} max={64} value={every} onChange={(e) => useAnimate.setState({ extractEvery: Math.max(1, Number(e.target.value) || 1) })} style={{ width: 60 }} />
        <CommandButton id="anim.extractRange" text /><span className="hint">{n} frame{n === 1 ? '' : 's'} (max 24)</span>
      </div>
      <h4 className="sect">harvested ({pins.length})</h4>
      <div className="insp-thumbs">{[...pins].sort((x, y) => x.frame - y.frame).map((p) => <img key={p.asset_id} src={api.thumbUrl(p.asset_id, 256)} alt="" className={p.frame === frame ? 'cur' : ''} title={`frame ${p.frame} — click to go there`} onClick={() => an().setFrame(p.frame)} />)}</div>
      {!pins.length && <span className="hint">No frames extracted. <Help text="Extract frame (F) or Extract range (Shift+F): the frames land in the Bin with frame-extract lineage and open in Edit." /></span>}
    </div>
  )
}

function LineageTab({ clip }: { clip: Clip }) {
  const caps = useSession((s) => s.capabilities)
  const clips = useAnimate((s) => s.clips)
  const siblings = clips.filter((c) => c.id !== clip.id && ((clip.batch_id && c.batch_id === clip.batch_id) || c.start_asset_id === clip.start_asset_id))
  return (
    <dl className="kv">
      <dt>sources</dt><dd className="insp-thumbs"><img src={api.thumbUrl(clip.start_asset_id, 256)} alt="" title={`start ${clip.start_asset_id}`} />{clip.end_asset_id && <img src={api.thumbUrl(clip.end_asset_id, 256)} alt="" title={`end ${clip.end_asset_id}`} />}</dd>
      <dt>extracted</dt><dd className="insp-thumbs">{clip.extracted_asset_ids.map((id) => <img key={id} src={api.thumbUrl(id, 256)} alt="" title={id} />)}{!clip.extracted_asset_ids.length && <span className="hint">none yet</span>}</dd>
      <dt>siblings</dt><dd>{siblings.length ? siblings.map((c) => <button key={c.id} className="quiet" onClick={() => an().select(c.id)} title={c.prompt}>{shortName(c.model_id, caps)} · seed {c.seed}</button>) : <span className="hint">no other clips from this start frame</span>}</dd>
      <dt>asset</dt><dd className="mono">{clip.asset_id ?? '—'}</dd>
    </dl>
  )
}

export const AnimateSuite: SuiteParts = { Panel: PerformanceColumn, Strip, Stage, Inspector: () => null, PrimaryAction: PerformanceFoot }

/** D125 (A4): the clip's Story verb — with the For chip it becomes that shot's clip (no second shot), without one a shot is made from it. */
function ClipShotVerb() {
  const f = useMakeFor((s) => s.animate)
  useStory((s) => s.shots)                                            // used meanwhile: the verb's state follows
  return f ? <CommandButton id="anim.useClip" label={`Use as ${f.name}'s clip`} /> : <CommandButton id="anim.toShot" />
}
