// D111 (PS5): the final shot in Animate's Shot section — *Make the final shot…* splits the finished scene into layers (their passes rendered
// here and stored with the final); the stage's finals listed with their layers. PS5b: the plate's still (*Make the plate*) and its
// projection along the camera path, which runs here when the still lands. PS5c–f add the characters, mattes, assembly and re-takes.
import { useEffect } from 'react'
import { Help } from '../../frame/Help'
import { api } from '../../api/client'
import type { Final, FinalLayer } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, runCommand } from '../../frame/commands'
import { useSession } from '../../store/session'
import { showMenu } from '../../frame/ContextMenu'
import { assembling, batchCount, nextFinalStep, readyToAssemble, rendering, useFinals } from './finalShot'
import { useStage } from './stageStore'

const KIND_LABEL: Record<string, string> = { plate: 'plate', figure: 'character', prop: 'prop', shadows: 'shadows' }
const METHOD_LABEL: Record<string, string> = { projected: 'the set, projected', move: 'Wan Animate', rendered: 'its 3D model', drawn: 'drawn on its model', stage: "Stage's" }
const POLL_MS = 3000

function statusText(l: FinalLayer, projecting: boolean, frames: number): string {
  if (l.kind === 'plate') {
    if (projecting) return 'projecting…'
    if (l.status === 'queued') return 'the still is queued'
    if (l.status === 'running') return l.still_asset_id ? 'projecting next' : 'making the still'
  }
  if (l.kind === 'figure' && l.status === 'running' && l.frames_done === frames) return 'matting (SAM 3)'   // PS5d
  if (l.kind === 'figure' && (l.status === 'queued' || l.status === 'running')) {         // PS5c: the batch at work
    const k = l.batches.filter((b) => b.clip_id).length
    return `performing · batch ${k + 1} of ${batchCount(frames)}`
  }
  if (l.status === 'failed') return `failed${l.error ? `: ${l.error}` : ''}`
  return l.status === 'passes' ? 'passes ready' : l.status === 'done' ? `done · ${l.frames_done} frames` : l.status
}

function LayerRow({ f, l }: { f: Final; l: FinalLayer }) {
  const projecting = useFinals((s) => s.projecting === f.id)
  const plate = l.kind === 'plate'
  const working = l.status === 'queued' || l.status === 'running'
  const retake = () => void useFinals.getState().perform(f.id, l.id, l.seed + 1)
  const menu = plate ? [{ label: l.still_asset_id ? 'Make the plate again' : 'Make the plate', run: () => void useFinals.getState().plate(f.id), disabled: l.status === 'queued' },
    { label: 'Project the plate again', run: () => void useFinals.getState().project(f.id), disabled: !l.still_asset_id || projecting }]
    : l.kind === 'figure' ? [{ label: l.batches.length ? 'Re-take this layer (a new seed)' : 'Perform this layer', run: l.batches.length ? retake : () => void useFinals.getState().perform(f.id, l.id), disabled: working },
      { label: 'Matte it again', run: () => void useFinals.getState().matte(f.id, l.id), disabled: working || l.frames_done !== f.frames }] : []
  return (
    <li data-kind={l.kind} data-id={l.id} title={`${l.name} — ${KIND_LABEL[l.kind]}, ${METHOD_LABEL[l.method] ?? l.method}; passes: ${Object.entries(l.passes).map(([k, n]) => `${k} ${n}`).join(', ')}`}
      onContextMenu={menu.length ? (e) => { e.preventDefault(); e.stopPropagation(); showMenu(e, menu) } : undefined}>
      <span className="kind">{KIND_LABEL[l.kind]}</span>
      <span className="name">{plate && l.still_asset_id ? <img className="still" src={api.thumbUrl(l.still_asset_id, 256)} alt="" /> : null}{l.name}</span>
      <span className={`status s-${l.status}`}>{statusText(l, projecting, f.frames)}</span>
      {plate && (l.status === 'passes' || l.status === 'failed') && <button className="quiet" onClick={() => void useFinals.getState().plate(f.id)} title="A Klein Stage shot of the bare set at the first frame, with the Shot tab's prompt and references (no people, no objects: they are layers)">Make the plate</button>}
      {l.kind === 'figure' && !working && <button className="quiet" onClick={l.status === 'done' ? retake : () => void useFinals.getState().perform(f.id, l.id)}
        title={l.status === 'done' ? 'Perform it again with a new seed (the other layers stay)' : "The figure's character (its animation reference, placed where the figure starts) performs its pose sequence through Wan Animate, in 77-frame batches"}>
        {l.status === 'done' ? 'Re-take' : 'Perform'}</button>}
    </li>
  )
}

function FinalRow({ f }: { f: Final }) {
  useFinals((s) => s.finals)                                                   // re-render as the poll reloads (the assembly job's state)
  const busy = assembling(f.id)
  const ready = readyToAssemble(f)
  const comp = useFinals((s) => s.compositions[f.id]) ?? null                   // AE1: the composition, once made
  const rendersNow = rendering(f.id)
  return (
    <div className="final-row" data-id={f.id} onContextMenu={(e) => { e.preventDefault(); showMenu(e, [
      { label: 'Assemble the shot', run: () => void useFinals.getState().assemble(f.id), disabled: !ready || busy },
      { label: 'Play the shot in Animate', run: () => useFinals.getState().play(f.id), disabled: !f.clip_id }, { sep: true },
      { label: comp ? 'Make the composition again' : 'Make the composition', run: () => void useFinals.getState().compose(f.id), disabled: !f.assembled_at || busy },
      { label: 'Open in Final', run: () => useFinals.getState().openFinal(f.id), disabled: !comp },
      { label: comp?.clip_id ? 'Render the finished shot again' : 'Render the finished shot', run: () => void useFinals.getState().render(f.id), disabled: !comp || rendersNow }, { sep: true },
      { label: 'Delete this final', danger: true, run: () => void useFinals.getState().remove(f.id) }]) }}>
      <div className="final-head"><b>{f.name}</b><span className="hint">{f.frames} frames at {f.rate} fps · {f.size.w}×{f.size.h} · frames {f.range.start}–{f.range.end}</span></div>
      <ul className="final-layers">{f.layers.map((l) => <LayerRow key={l.id} f={f} l={l} />)}</ul>
      <div className="final-foot">
        <div className="verbs">
        <button className={ready && !f.clip_id ? 'primary' : 'quiet'} disabled={!ready || busy} onClick={() => void useFinals.getState().assemble(f.id)}
          title={ready ? 'Composite the layers into the shot: the plate under the shadows, the props and characters in depth order, each character on her shadow' : 'Make every layer first: the plate, and each character performed and matted'}>
          {busy ? 'Assembling…' : f.clip_id ? 'Assemble again' : 'Assemble the shot'}</button>
        {f.clip_id && <button className="quiet" data-play onClick={() => useFinals.getState().play(f.id)} title="Play the assembled shot in Animate">Play ▶</button>}
        {f.assembled_at && <button className={comp ? 'quiet' : 'primary'} data-compose disabled={busy} onClick={() => void useFinals.getState().compose(f.id)}
          title={comp ? 'Write the composition afresh from the layers and the assembly (the edits are dropped)' : 'An EffectCraft composition beside the final: the plate, the shadows, each prop, each character over her matte at her contact offset — the shot to finish by hand'}>
          {comp ? 'Make the composition again' : 'Make the composition'}</button>}
        {comp && <button className="quiet" data-open-final onClick={() => useFinals.getState().openFinal(f.id)} title="Scrub and play the composition at Animate's Final level">Open in Final</button>}
        {comp && <button className={comp.clip_id ? 'quiet' : 'primary'} data-render disabled={rendersNow} onClick={() => void useFinals.getState().render(f.id)}
          title="effectcraft-cli renders the composition at Best and Full on the CPU (RIFE to 24 fps at F16); the clip becomes the final's and a take on its shot">
          {rendersNow ? 'Rendering…' : comp.clip_id ? 'Render again' : 'Render the finished shot'}</button>}
        </div>
        {comp && <span className="hint" data-comp-rev>composition · revision {comp.revision}{comp.stale ? ' · stale: the final changed' : ''}{comp.clip_id ? ` · rendered at revision ${comp.rendered_revision}` : ''}</span>}
        {f.assembly && <span className="hint">{f.assembly.frames as number} frames{f.assembly.conform ? ' · 24 fps (RIFE)' : ''} · offsets {Object.entries((f.assembly.offsets_px ?? {}) as Record<string, number[]>).map(([k, v]) => `${k} ${v[0]}/${v[1]}`).join(', ') || '—'}</span>}
      </div>
    </div>
  )
}

export function FinalSection() {
  const current = useStage((s) => s.current)
  const finals = useFinals((s) => s.finals)
  const making = useFinals((s) => s.making)
  useEffect(() => { void useFinals.getState().load() }, [current?.id])
  useEffect(() => { const t = window.setInterval(() => void useFinals.getState().tick(), POLL_MS); return () => window.clearInterval(t) }, [])
  if (!current) return null
  const mine = finals.filter((f) => f.stage_id === current.id)
  return (
    <details className="step final-section" data-step="final" open>
      <summary><span className="tw" aria-hidden="true">▸</span><b>Final shot</b><Help text="The finished scene split into layers — the plate, each character, each prop, the shadows — performed, matted, assembled, then finished by hand at the Final level." />
        <span className="state hint">{mine.length ? `${mine.length} final${mine.length === 1 ? '' : 's'}` : 'none yet'}</span>
        <span className="verb" onClick={(e) => e.preventDefault()}><CommandButton id="stage.final.make" text label={making ? 'Splitting…' : 'Make the final shot…'} /></span></summary>
      <div className="step-body">
        {making && <div className="final-progress"><progress max={making.total} value={making.done} /><span className="hint">{making.what} · {making.done} / {making.total}</span></div>}
        {mine.map((f) => <FinalRow key={f.id} f={f} />)}
      </div>
    </details>
  )
}

/** D121 (proto01_animate 26 §5.3): Performance › Final shot's foot — the stage's newest final's next step (`stage.final.next`), or why it waits. */
export function FinalShotFoot() {
  const current = useStage((s) => s.current)
  useFinals((s) => s.finals); useFinals((s) => s.making); useFinals((s) => s.compositions)    // re-render as the final moves on
  useSession((s) => s.jobs)
  markUsed('stage.final.next')
  const step = nextFinalStep(current?.id ?? null)
  return (
    <div>
      <button className="primary" disabled={!step.run} onClick={() => runCommand('stage.final.next')} title="The final shot's next step: make it, the plate, each character, the assembly, the composition, then the Final level (Ctrl+Enter)">{step.label}</button>
      <div className="estimate">{step.why ? <span style={{ color: 'var(--fg3)' }}>{step.why}</span> : <span>{current ? `${current.name} · the next step` : ''}</span>}</div>
    </div>
  )
}
