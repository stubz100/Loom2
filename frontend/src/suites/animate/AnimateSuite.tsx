// Animate suite (11): Panel (Inputs / Model / Length & Size / Presets / Clips), Strip (view, speed, loop, onion, counter),
// Stage (Mediabunny player · filmstrip · compare, transport, timeline with in/out, S/E, beats and harvested pins, live
// jobs), Inspector (Clip / Frames / Lineage). Every action is a registry command (animateCommands.ts, D32).
import { Bookmark, Boxes, Clock, Film, Image as ImageIcon, Lock, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { api } from '../../api/client'
import type { Clip, I2vModelCaps } from '../../api/types'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { askText, useSession } from '../../store/session'
import { playerMenu } from './animateCommands'
import { fmtTime, MODEL_RULES, modelRules, MOTION_CHIPS, useAnimate, type AnimPanel } from './animateStore'
import { Player } from './Player'
import './animate.css'
import { assetIds, onlyAssets, useDropTarget } from '../../frame/drag'

const an = () => useAnimate.getState()
const EMPTY_PINS: { frame: number; asset_id: string }[] = []

// ------------------------------------------------------------------ Panel · Inputs (11 §3a)
function Slot({ which }: { which: 'start' | 'end' }) {
  const id = useAnimate((s) => s.panel[which])
  const asset = useAnimate((s) => (id ? s.assets[id] : undefined))
  const set = (v: string | null) => (which === 'start' ? an().setStart(v) : an().setEnd(v))
  const { ref, over } = useDropTarget(onlyAssets, (p) => { const ids = assetIds(p); set(ids[0]); if (which === 'start' && ids[1] && !an().panel.end) an().setEnd(ids[1]) })
  return (
    <div ref={ref} className={`slot${over ? ' over' : ''}`}
      title={which === 'start' ? 'Start frame: drop a Catalogue tile, or Shift+A on a tile in the Catalogue' : 'End frame (optional): drop a tile, or Shift+Z in the Catalogue — enables first/last-frame mode'}>
      <span className="tag">{which === 'start' ? 'S' : 'E'}</span>
      {id ? <>
        <img src={api.thumbUrl(id, 512)} alt="" />
        <span className="meta">{asset ? `${asset.w}×${asset.h}${asset.kind === 'video' ? ' · a clip (use a frame)' : ''}` : id}</span>
        <button className="quiet x" title={`Clear ${which} frame`} aria-label={`Clear ${which} frame`} onClick={() => set(null)}><X size={14} /></button>
      </> : <span className="cap">{which === 'start' ? 'start frame' : 'end frame (optional)'}<br /><small>{which === 'start' ? 'drop a tile · Shift+A' : 'drop a tile · Shift+Z'}</small></span>}
    </div>
  )
}

function InputsTab() {
  const p = useAnimate((s) => s.panel)
  const assets = useAnimate((s) => s.assets)
  const isLtx = p.model_id === 'ltx23-distilled-fp8'
  const { ref: beatRef, over: beatOver } = useDropTarget(onlyAssets, (d) => { const ids = assetIds(d); ids.forEach((id, k) => an().addBeat(id, Math.round(an().panel.frames * (k + 1) / (ids.length + 1)))) })
  return (
    <div className="anim-form">
      <div className="slots full"><Slot which="start" /><span className="slot-swap"><CommandButton id="anim.swap" /></span><Slot which="end" /></div>
      {p.end && !isLtx && <span className="hint">First/last-frame on Wan: a large pose or composition gap morphs mid-clip — try LTX beats or a shorter clip when it does (11 §3a).</span>}
      <label>prompt</label>
      <div>
        <textarea value={p.prompt} onChange={(e) => an().set({ prompt: e.target.value })} placeholder="motion, camera, mood — e.g. she turns toward the window, soft push-in" />
        <div className="chip-row">{MOTION_CHIPS.map((c) => <button key={c} onClick={() => an().set({ prompt: (p.prompt ? p.prompt.replace(/[\s,]*$/, '') + ', ' : '') + c })} title="append to the prompt">{c}</button>)}</div>
      </div>
      <label>negative</label>
      <div>
        <label className="chk"><input type="checkbox" checked={p.use_negative} onChange={(e) => an().set({ use_negative: e.target.checked })} /> write my own</label>
        {p.use_negative ? <textarea value={p.negative} onChange={(e) => an().set({ negative: e.target.value })} placeholder="what to avoid" /> : <span className="hint">{isLtx ? 'LTX uses a short stock negative (blurry, distorted, static, watermark).' : 'Wan uses its official negative list (over-exposure, static frames, extra fingers, …); it only matters above CFG 1 (Motion / Quality).'}</span>}
      </div>
      {isLtx && <>
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
            drop frames here as mid-clip keyframes (strength 0.3–1.0, drag the marker on the timeline)
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
  const models: [string, I2vModelCaps | undefined][] = Object.keys(MODEL_RULES).filter((id) => !caps || caps.models[id]).map((id) => [id, caps?.models[id]])   // C3: the open build lists Wan only
  const cur = caps?.models[p.model_id]
  const h3 = useSession((s) => !!s.settings?.h3_licence_confirmed)
  const presetLabel = (k: string) => cur?.presets[k] ?? k
  return (
    <div className="anim-form">
      <label>model</label>
      <div className="model-grid">
        {models.map(([id, m]) => {
          const r = modelRules(id)
          return <button key={id} className={`model-card${p.model_id === id ? ' active' : ''}`} onClick={() => an().setModel(id)}>
            <b>{r.short === 'Wan' ? 'Wan (faithful)' : 'LTX (fast, beats)'}</b>
            <small>{m?.label ?? id}</small>
            <small>{r.frames} f @ {r.fps} fps · {r.draft[0]}×{r.draft[1]}{id === 'ltx23-distilled-fp8' ? ' · keyframe beats' : ' · FLF'}</small>
            <span className={`badge ${m?.health ?? 'missing'} health`}>{m ? (m.health === 'missing' ? `fetch ${m.approx_gb} GB` : m.health) : '…'}</span>
          </button>
        })}
        <button className={`model-card locked${h3 ? ' confirmed' : ''}`} disabled title={h3 ? 'Licence confirmed (D17) — the H3 graph and weights arrive post-MVP (04 §5b)' : 'MiniMax H3 unlocks once Settings records that the EU licence application is filed (D17)'}>
          <b>{h3 ? null : <Lock size={12} />} H3 (hero)</b><small>MiniMax H3 FL2VA · 864×480 · 5 s · ≈ 13 min</small>
          <small>{h3 ? 'licence confirmed · graph + weights post-MVP (04 §5b)' : 'locked: confirm the licence application in Settings (D17)'}</small>
        </button>
      </div>
      <label>preset</label>
      <div className="segmented">{(['draft', 'motion', 'quality'] as const).map((k) => <button key={k} className={p.preset === k ? 'active' : ''} onClick={() => an().set({ preset: k, steps: null, cfg: null })} title={presetLabel(k)}>{k}</button>)}</div>
      <span className="hint">{presetLabel(p.preset)}</span>
      <h4 className="full sect">advanced</h4>
      <label>steps</label>
      <div className="row"><input type="number" min={1} max={60} placeholder="preset" value={p.steps ?? ''} onChange={(e) => an().set({ steps: e.target.value === '' ? null : Number(e.target.value) })} /><span className="hint" style={{ margin: 0 }}>empty = the preset's steps{p.model_id === 'wan22-i2v-high-fp8' ? ' (split high / low in the same ratio)' : ''}</span></div>
      {p.model_id === 'wan22-i2v-high-fp8' && <>
        <label>CFG</label>
        <div className="row"><input type="number" min={1} max={12} step={0.5} placeholder={p.preset === 'draft' ? '1 (distilled)' : '3.5'} value={p.cfg ?? ''} onChange={(e) => an().set({ cfg: e.target.value === '' ? null : Number(e.target.value) })} disabled={p.preset === 'draft'} /><span className="hint" style={{ margin: 0 }}>high expert only; Draft runs at CFG 1</span></div>
      </>}
      <label>shift</label>
      <div className="row"><input type="number" min={0.5} max={12} step={0.5} placeholder={p.model_id === 'wan22-i2v-high-fp8' ? (p.preset === 'quality' ? '8' : '5') : 'scheduler'} value={p.shift ?? ''} onChange={(e) => an().set({ shift: e.target.value === '' ? null : Number(e.target.value) })} /></div>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Length & Size (11 §3c)
function EstimateLine() {
  const pv = useAnimate((s) => s.preview)
  const err = useAnimate((s) => s.previewError)
  const count = useAnimate((s) => s.panel.count)
  const setSuite = useSession((s) => s.setSuite)
  if (err) return <div className="estimate-line"><span className="missing">{err}</span></div>
  if (!pv) return <div className="estimate-line">preparing…</div>
  const secs = pv.estimate.seconds ?? 0
  return (
    <div className="estimate-line">
      <span>runs at <b>{pv.width}×{pv.height}</b> · <b>{pv.frames}</b> f @ {pv.fps} fps ({(pv.frames / pv.fps).toFixed(1)} s)</span>
      <span>{pv.label}</span>
      <span>≈ <b>{Math.round(secs / 60)} min</b>{count > 1 ? ` × ${count}` : ''} <small>({pv.estimate.source})</small></span>
      {pv.missing.length > 0 && <span className="missing">missing: {pv.missing.map((m) => m.model_id).join(', ')} <button onClick={() => setSuite('models')}>Fetch {pv.missing.reduce((a, m) => a + (m.approx_gb ?? 0), 0).toFixed(0)} GB</button></span>}
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
      <label>clips</label>
      <div className="row"><input type="number" min={1} max={8} value={p.count} onChange={num('count', 1, 8)} /><span className="hint" style={{ margin: 0 }}>variations per Animate (new seeds)</span></div>
      <div className="full"><EstimateLine /></div>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Presets · Clips
function PresetsTab() {
  const presets = useAnimate((s) => s.presets)
  const last = useAnimate((s) => s.lastPreset)
  return (
    <div>
      <button className="primary" onClick={() => void askText({ title: 'Save Animate preset', text: 'Model, preset, size, frames, seed mode and prompt — frames and beats are not saved.', initial: last ?? '', placeholder: 'preset name' }).then((n) => { if (n) an().savePreset(n) })}>Save panel preset…</button>
      <div style={{ display: 'grid', gap: 4, marginTop: 8 }}>
        {presets.map((pr) => <div key={pr.name} style={{ display: 'flex', gap: 4 }}><button style={{ flex: 1 }} className={last === pr.name ? 'active' : ''} onClick={() => an().applyPreset(pr.name)}><span>{pr.name}</span> <small>{MODEL_RULES[pr.panel.model_id]?.short} · {pr.panel.preset} · {pr.panel.width}×{pr.panel.height}</small></button><button className="quiet" title="Delete preset" aria-label="Delete preset" onClick={() => an().deletePreset(pr.name)}><X size={14} /></button></div>)}
        {!presets.length && <span className="hint">No presets yet.</span>}
      </div>
    </div>
  )
}

function ClipsTab() {
  const clips = useAnimate((s) => s.clips)
  const current = useAnimate((s) => s.current)
  const assets = useAnimate((s) => s.assets)
  return (
    <div className="clip-list">
      {clips.map((c) => {
        const a = c.asset_id ? assets[c.asset_id] : undefined
        return <button key={c.id} className={`clip-row${c.id === current ? ' active' : ''}`} onClick={() => an().select(c.id)} title={c.prompt}>
          {c.asset_id ? <img src={api.thumbUrl(c.asset_id, 256)} alt="" /> : <span />}
          <span>{c.prompt || '(no prompt)'}<small>{MODEL_RULES[c.model_id]?.short ?? c.model_id} · {c.preset} · {c.frames} f @ {c.fps} · seed {c.seed}{a?.state && a.state !== 'none' ? ` · ${a.state}` : ''}</small></span>
        </button>
      })}
      {!clips.length && <span className="hint">No clips in this project yet.</span>}
    </div>
  )
}

function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  const caps = useSession((s) => s.capabilities?.i2v)
  useEffect(() => { if (project?.open) an().refreshPreview() }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (caps && !caps.models[an().panel.model_id]) an().setModel('wan22-i2v-high-fp8') }, [caps])   // C3: a persisted LTX panel under `open`
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  if (tab === 'model') return <ModelTab />
  if (tab === 'length') return <LengthTab />
  if (tab === 'presets') return <PresetsTab />
  if (tab === 'clips') return <ClipsTab />
  return <InputsTab />
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
      <button className="primary" disabled={!!reason} onClick={() => runCommand('anim.animate')} title={`Animate (⌃↵) ${eta}`}>Animate {p.count > 1 ? `${p.count} ` : ''}▶ {eta}</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}><button disabled={!!reason} onClick={() => runCommand('anim.stage')} title="Stage: add to the queue, run later (⌃⇧↵)">Stage</button>{reason && <span className="disabled-why">{reason}</span>}</div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip (11 §4)
export function useAnimateKeys() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'animate') return
      if ((e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable], .modal')) return
      if (handleKeyFor('animate', e)) e.stopImmediatePropagation()
    }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [])
}

function Strip() {
  const view = useAnimate((s) => s.view)
  const speed = useAnimate((s) => s.speed)
  const loop = useAnimate((s) => s.loop)
  const onion = useAnimate((s) => s.onion)
  const frame = useAnimate((s) => s.frame)
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  return (
    <>
      <CommandRow ids={['anim.view.player', 'anim.view.filmstrip', 'anim.view.compare']} active={`anim.view.${view}`} />
      <span className="spacer" />
      {clip && <span className="counter" style={{ fontFamily: 'var(--mono)' }}>frame {frame} / {clip.frames - 1} · {fmtTime(frame, clip.fps)} · {clip.frames} f · {clip.w}×{clip.h} @ {clip.fps} fps</span>}
      <span className="spacer" />
      <label>speed <select value={String(speed)} onChange={(e) => useAnimate.setState({ speed: Number(e.target.value) })}>{[-2, -1, 0.25, 0.5, 1, 1.5, 2].map((v) => <option key={v} value={String(v)}>{v < 0 ? `◀ ${-v}×` : `${v}×`}</option>)}</select></label>
      <CommandButton id="anim.loop" active={loop} />
      <CommandButton id="anim.onion" active={onion} />
    </>
  )
}
function StripWithKeys() { useAnimateKeys(); return <Strip /> }

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
            {clips.filter((c) => c.id !== clip.id).map((c) => <option key={c.id} value={c.id}>{MODEL_RULES[c.model_id]?.short ?? c.model_id} · {c.prompt.slice(0, 32) || c.id} · seed {c.seed}</option>)}
          </select>
          {b && <span>frame {frameB} (synced by time)</span>}
        </div>
      </div>
    </div>
  )
}

function Transport({ clip }: { clip: Clip }) {
  const frame = useAnimate((s) => s.frame)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const busy = useAnimate((s) => s.busy)
  return (
    <div className="transport">
      <CommandRow ids={['anim.home', 'anim.back10', 'anim.stepBack', 'anim.play', 'anim.stepForward', 'anim.fwd10', 'anim.end']} />
      <span className="counter">frame {frame} / {clip.frames - 1} · {fmtTime(frame, clip.fps)}</span>
      <CommandRow ids={['anim.setIn', 'anim.setOut', 'anim.clearInOut']} />
      <span>{inPoint !== null || outPoint !== null ? `in ${inPoint ?? 0} · out ${outPoint ?? clip.frames - 1}` : 'whole clip'}</span>
      <span className="spacer" />
      <CommandRow ids={['anim.extractFrame', 'anim.sendToEdit']} />
      {busy && <span>{busy}…</span>}
    </div>
  )
}

function Timeline({ clip }: { clip: Clip }) {
  const frame = useAnimate((s) => s.frame)
  const inPoint = useAnimate((s) => s.inPoint)
  const outPoint = useAnimate((s) => s.outPoint)
  const pins = useAnimate((s) => s.pins[clip.id]) ?? EMPTY_PINS
  const ref = useRef<HTMLDivElement>(null)
  const N = clip.frames
  const pct = (f: number) => `${(f / Math.max(1, N - 1)) * 100}%`
  const frameAt = (clientX: number) => { const r = ref.current!.getBoundingClientRect(); return Math.max(0, Math.min(N - 1, Math.round(((clientX - r.left) / r.width) * (N - 1)))) }
  const drag = (which: 'in' | 'out') => (e: ReactPointerEvent) => {
    e.stopPropagation(); e.preventDefault()
    const move = (ev: PointerEvent) => { const f = frameAt(ev.clientX); const s = useAnimate.getState(); useAnimate.setState(which === 'in' ? { inPoint: Math.min(f, s.outPoint ?? N - 1) } : { outPoint: Math.max(f, s.inPoint ?? 0) }) }
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const minor = N > 200 ? 8 : N > 100 ? 4 : 2
  const ticks: number[] = []
  for (let f = 0; f < N; f += minor) ticks.push(f)
  return (
    <div className="timeline" ref={ref} onContextMenu={(e) => showMenu(e, playerMenu())}>
      <div className="ruler" onPointerDown={(e) => { an().togglePlay(false); an().setFrame(frameAt(e.clientX)); const move = (ev: PointerEvent) => an().setFrame(frameAt(ev.clientX)); const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }; window.addEventListener('pointermove', move); window.addEventListener('pointerup', up) }} title="click or drag to scrub" />
      <div className="range" style={{ left: pct(inPoint ?? 0), width: `calc(${pct(outPoint ?? N - 1)} - ${pct(inPoint ?? 0)})` }} />
      {ticks.map((f) => <div key={f} className={`tick${f % clip.fps === 0 ? ' major' : ''}`} style={{ left: pct(f) }}>{f % clip.fps === 0 && <span>{f / clip.fps}s</span>}</div>)}
      <div className="marker" style={{ left: pct(0) }} title="start frame">S</div>
      {clip.end_asset_id && <div className="marker" style={{ left: pct(N - 1) }} title="end frame (FLF)">E</div>}
      {clip.beats.map((b, i) => <div key={i} className="marker beat" style={{ left: pct(b.frame) }} title={`beat at ${b.frame} · strength ${b.strength}`}>♦</div>)}
      {pins.map((p) => <div key={p.asset_id} className="marker pin" style={{ left: pct(p.frame), top: 2 }} title={`extracted frame ${p.frame} — click to go there`} onClick={() => an().setFrame(p.frame)}>▼</div>)}
      {inPoint !== null && <div className="handle in" style={{ left: pct(inPoint) }} onPointerDown={drag('in')} title="in point (drag)" />}
      {outPoint !== null && <div className="handle out" style={{ left: pct(outPoint) }} onPointerDown={drag('out')} title="out point (drag)" />}
      <div className="head" style={{ left: pct(frame) }} />
    </div>
  )
}

function Interim() {
  const jobs = useSession((s) => s.jobs)
  const list = useMemo(() => Object.values(jobs).filter((j) => j.kind === 'i2v' && ['running', 'queued', 'staged'].includes(j.status)).sort((a, b) => (a.status === 'running' ? -1 : b.status === 'running' ? 1 : a.created_at < b.created_at ? -1 : 1)), [jobs])
  if (!list.length) return null
  return (
    <div className="anim-interim">
      {list.map((j) => { const r = j.recipe as { model_id?: string; frames?: number; prompt_text?: string }; return <div key={j.id} className="card">
        <span>{MODEL_RULES[r.model_id ?? '']?.short ?? r.model_id} · {r.frames} f · seed {j.seed} · {j.status === 'running' ? j.progress_text : j.status}</span>
        <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>
        <span>{(r.prompt_text ?? '').slice(0, 60)}</span>
      </div> })}
    </div>
  )
}

function Stage() {
  const project = useSession((s) => s.project)
  const clips = useAnimate((s) => s.clips)
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  const view = useAnimate((s) => s.view)
  const frame = useAnimate((s) => s.frame)
  const onion = useAnimate((s) => s.onion)
  const running = useSession((s) => Object.values(s.jobs).some((j) => j.kind === 'i2v' && j.status === 'running'))
  useEffect(() => { if (project?.open) void an().loadClips() }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  // deep link ?clip=<id> (the headed check and the verification loop)
  useEffect(() => { const q = new URLSearchParams(location.search).get('clip'); if (q && clips.some((c) => c.id === q) && an().current !== q) an().select(q) }, [clips])
  usePlayback()
  if (!project?.open) return <div className="placeholder"><div><h2>Animate</h2>open or create a project to begin</div></div>
  return (
    <div className="anim-stage">
      <div className="anim-view" onContextMenu={(e) => { if (clip) showMenu(e, playerMenu()) }}>
        {!clip ? <div className="anim-empty"><h2>Animate</h2>{running ? 'rendering the first clip — it opens here when the proxy is ready' : 'set a start frame (Shift+A on a Catalogue tile, or drop it on the Inputs slot), write the motion, Animate ▶'}</div>
          : view === 'player' ? <Player clip={clip} frame={frame} onion={onion} /> : view === 'filmstrip' ? <Filmstrip clip={clip} /> : <Compare clip={clip} />}
      </div>
      {clip && <Transport clip={clip} />}
      {clip && <Timeline clip={clip} />}
      <Interim />
    </div>
  )
}

// ------------------------------------------------------------------ Inspector (11 §6)
function ClipTab({ clip }: { clip: Clip }) {
  const asset = useAnimate((s) => (clip.asset_id ? s.assets[clip.asset_id] : undefined))
  const caps = useSession((s) => s.capabilities?.i2v)
  const facesim = useSession((s) => s.capabilities?.facesim)
  const wall = (clip.timings as { wall_s?: number }).wall_s
  return (
    <div>
      <div className="verbs">{['anim.keep', 'anim.reject', 'anim.variations', 'anim.rerun', 'anim.tryOther', 'anim.toCatalogue'].map((id) => <CommandButton key={id} id={id} text />)}</div>
      <dl className="kv">
        <dt>state</dt><dd>{asset ? <span className={`badge ${asset.state}`}>{asset.state}</span> : '—'}</dd>
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
        <dt>extend</dt><dd><CommandButton id="anim.useAsStart" text /> <span className="hint">native extension waits for LTX-2.3 (post-MVP)</span></dd>
      </dl>
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
      {!pins.length && <span className="hint">Extract frame (F) or Extract range (Shift+F) — frames land in the Catalogue with frame-extract lineage and open in Edit.</span>}
    </div>
  )
}

function LineageTab({ clip }: { clip: Clip }) {
  const clips = useAnimate((s) => s.clips)
  const siblings = clips.filter((c) => c.id !== clip.id && ((clip.batch_id && c.batch_id === clip.batch_id) || c.start_asset_id === clip.start_asset_id))
  return (
    <dl className="kv">
      <dt>sources</dt><dd className="insp-thumbs"><img src={api.thumbUrl(clip.start_asset_id, 256)} alt="" title={`start ${clip.start_asset_id}`} />{clip.end_asset_id && <img src={api.thumbUrl(clip.end_asset_id, 256)} alt="" title={`end ${clip.end_asset_id}`} />}</dd>
      <dt>extracted</dt><dd className="insp-thumbs">{clip.extracted_asset_ids.map((id) => <img key={id} src={api.thumbUrl(id, 256)} alt="" title={id} />)}{!clip.extracted_asset_ids.length && <span className="hint">none yet</span>}</dd>
      <dt>siblings</dt><dd>{siblings.length ? siblings.map((c) => <button key={c.id} className="quiet" onClick={() => an().select(c.id)} title={c.prompt}>{MODEL_RULES[c.model_id]?.short ?? c.model_id} · seed {c.seed}</button>) : <span className="hint">no other clips from this start frame</span>}</dd>
      <dt>asset</dt><dd className="mono">{clip.asset_id ?? '—'}</dd>
    </dl>
  )
}

function Inspector() {
  const [tab, setTab] = useState<'clip' | 'frames' | 'lineage'>('clip')
  const clip = useAnimate((s) => s.clips.find((c) => c.id === s.current))
  if (!clip) return <span className="hint">No clip selected — clips appear here as they finish, or pick one in the Clips panel.</span>
  return (
    <div>
      <div className="tabs2">{(['clip', 'frames', 'lineage'] as const).map((t) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === 'clip' && <ClipTab clip={clip} />}
      {tab === 'frames' && <FramesTab clip={clip} />}
      {tab === 'lineage' && <LineageTab clip={clip} />}
    </div>
  )
}

export const AnimateSuite: SuiteDef = {
  id: 'animate',
  rail: [{ id: 'inputs', label: 'Inputs', icon: <ImageIcon size={18} /> }, { id: 'model', label: 'Model', icon: <Boxes size={18} /> }, { id: 'length', label: 'Length & Size', icon: <Clock size={18} /> },
    { id: 'presets', label: 'Presets', icon: <Bookmark size={18} /> }, { id: 'clips', label: 'Clips', icon: <Film size={18} /> }],
  Panel, Strip: StripWithKeys, Stage, Inspector, PrimaryAction,
}
