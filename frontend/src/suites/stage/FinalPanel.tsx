// D111 (PS5): the final shot in Animate's Shot section — *Make the final shot…* splits the finished scene into layers (their passes rendered
// here and stored with the final); the stage's finals listed with their layers. PS5b: the plate's still (*Make the plate*) and its
// projection along the camera path, which runs here when the still lands. PS5c–f add the characters, mattes, assembly and re-takes.
import { useEffect } from 'react'
import { api } from '../../api/client'
import type { Final, FinalLayer } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { useFinals } from './finalShot'
import { useStage } from './stageStore'

const KIND_LABEL: Record<string, string> = { plate: 'plate', figure: 'character', prop: 'prop', shadows: 'shadows' }
const METHOD_LABEL: Record<string, string> = { projected: 'the set, projected', move: 'Wan Animate', rendered: 'its 3D model', drawn: 'drawn on its model', stage: "Stage's" }
const POLL_MS = 3000

function statusText(l: FinalLayer, projecting: boolean): string {
  if (l.kind === 'plate') {
    if (projecting) return 'projecting…'
    if (l.status === 'queued') return 'the still is queued'
    if (l.status === 'running') return l.still_asset_id ? 'projecting next' : 'making the still'
  }
  return l.status === 'passes' ? 'passes ready' : l.status === 'done' ? `done · ${l.frames_done} frames` : l.status
}

function LayerRow({ f, l }: { f: Final; l: FinalLayer }) {
  const projecting = useFinals((s) => s.projecting === f.id)
  const plate = l.kind === 'plate'
  const menu = plate ? [{ label: l.still_asset_id ? 'Make the plate again' : 'Make the plate', run: () => void useFinals.getState().plate(f.id), disabled: l.status === 'queued' },
    { label: 'Project the plate again', run: () => void useFinals.getState().project(f.id), disabled: !l.still_asset_id || projecting }] : []
  return (
    <li data-kind={l.kind} data-id={l.id} title={`${l.name} — ${KIND_LABEL[l.kind]}, ${METHOD_LABEL[l.method] ?? l.method}; passes: ${Object.entries(l.passes).map(([k, n]) => `${k} ${n}`).join(', ')}`}
      onContextMenu={menu.length ? (e) => { e.preventDefault(); e.stopPropagation(); showMenu(e, menu) } : undefined}>
      <span className="kind">{KIND_LABEL[l.kind]}</span>
      <span className="name">{plate && l.still_asset_id ? <img className="still" src={api.thumbUrl(l.still_asset_id, 256)} alt="" /> : null}{l.name}</span>
      <span className={`status s-${l.status}`}>{statusText(l, projecting)}</span>
      {plate && (l.status === 'passes' || l.status === 'failed') && <button className="quiet" onClick={() => void useFinals.getState().plate(f.id)} title="A Klein Stage shot of the bare set at the first frame, with the Shot tab's prompt and references (no people, no objects: they are layers)">Make the plate</button>}
    </li>
  )
}

function FinalRow({ f }: { f: Final }) {
  return (
    <div className="final-row" data-id={f.id} onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ label: 'Delete this final', danger: true, run: () => void useFinals.getState().remove(f.id) }]) }}>
      <div className="final-head"><b>{f.name}</b><span className="hint">{f.frames} frames at {f.rate} fps · {f.size.w}×{f.size.h} · frames {f.range.start}–{f.range.end}</span></div>
      <ul className="final-layers">{f.layers.map((l) => <LayerRow key={l.id} f={f} l={l} />)}</ul>
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
    <div className="final-section">
      <h4>Final shot <span className="hint">the finished scene split into layers — the plate, each character, each prop, the shadows</span></h4>
      <div className="verbs"><CommandButton id="stage.final.make" text label={making ? 'Splitting…' : 'Make the final shot…'} /></div>
      {making && <div className="final-progress"><progress max={making.total} value={making.done} /><span className="hint">{making.what} · {making.done} / {making.total}</span></div>}
      {mine.map((f) => <FinalRow key={f.id} f={f} />)}
    </div>
  )
}
