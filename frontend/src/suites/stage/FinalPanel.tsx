// D111 (PS5): the final shot in Animate's Shot section — *Make the final shot…* splits the finished scene into layers (their passes rendered
// here and stored with the final); the stage's finals listed with their layers. PS5b–f add each layer's frames, status and re-takes.
import { useEffect } from 'react'
import type { Final } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { useFinals } from './finalShot'
import { useStage } from './stageStore'

const KIND_LABEL: Record<string, string> = { plate: 'plate', figure: 'character', prop: 'prop', shadows: 'shadows' }
const METHOD_LABEL: Record<string, string> = { projected: 'the set, projected', move: 'Wan Animate', rendered: 'its 3D model', drawn: 'drawn on its model', stage: "Stage's" }

function FinalRow({ f }: { f: Final }) {
  return (
    <div className="final-row" data-id={f.id} onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ label: 'Delete this final', danger: true, run: () => void useFinals.getState().remove(f.id) }]) }}>
      <div className="final-head"><b>{f.name}</b><span className="hint">{f.frames} frames at {f.rate} fps · {f.size.w}×{f.size.h} · frames {f.range.start}–{f.range.end}</span></div>
      <ul className="final-layers">{f.layers.map((l) => (
        <li key={l.id} data-kind={l.kind} title={`${l.name} — ${KIND_LABEL[l.kind]}, ${METHOD_LABEL[l.method] ?? l.method}; passes: ${Object.entries(l.passes).map(([k, n]) => `${k} ${n}`).join(', ')}`}>
          <span className="kind">{KIND_LABEL[l.kind]}</span><span className="name">{l.name}</span><span className={`status s-${l.status}`}>{l.status === 'passes' ? 'passes ready' : l.status}</span>
        </li>))}</ul>
    </div>
  )
}

export function FinalSection() {
  const current = useStage((s) => s.current)
  const finals = useFinals((s) => s.finals)
  const making = useFinals((s) => s.making)
  useEffect(() => { void useFinals.getState().load() }, [current?.id])
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
