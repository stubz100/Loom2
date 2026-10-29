// U3d (D157, proto01_UI2 03 §7): World's Sketches — the brainstorm's pictures that belong to no one yet, in `bin/world/sketches`. Free
// pictures are made with Image's whole column (the full prompt, the Library's words, here only) in a Make context of their own; a sketch's
// *Prototype ▸* makes a draft entity of a class from it — the picture becomes its hero.
import { useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import type { MenuItem } from '../../frame/commands'
import { makeContext, useGenerate } from '../../suites/generate/generateStore'
import { GenerateColumn } from '../../suites/generate/GenerateColumn'
import { useSketches } from './sketches'
import '../../suites/generate/generate.css'

const MENU: MenuItem[] = [{ cmd: 'world.sketch.character' }, { cmd: 'world.sketch.prop' }, { cmd: 'world.sketch.place' }, { sep: true }, { cmd: 'world.sketch.trash' }]

export function SketchColumn() {
  const pv = useGenerate((s) => s.preview)
  const count = useGenerate((s) => s.panel.count)
  useEffect(() => { makeContext.enter('world/sketches') }, [])
  const secs = pv?.estimate.seconds ? Math.round(pv.estimate.seconds * count) : null
  return (
    <div className="w-sketch-col" data-testid="world-sketches">
      <div className="w-sketch-gen"><GenerateColumn tab="prompt" /></div>
      <div className="w-foot"><CommandButton id="world.sketch.make" text label={`Make ${count} sketch${count === 1 ? '' : 'es'} ▶${secs ? ` ≈ ${secs < 90 ? `${secs} s` : `${Math.round(secs / 60)} min`}` : ''}`} /></div>
    </div>
  )
}

export function SketchCentre() {
  const items = useSketches((s) => s.items)
  const selected = useSketches((s) => s.selected)
  const loading = useSketches((s) => s.loading)
  useEffect(() => { void useSketches.getState().load() }, [])
  return (
    <div className="w-bin">
      <div className="w-bin-head"><span className="w-path">bin/world/sketches</span></div>
      {items.length ? <div className="w-grid">{items.map((a) => (
        <button key={a.id} className={`w-tile${selected === a.id ? ' selected' : ''}`} data-id={a.id} title={a.prompt_text ?? ''} onClick={() => useSketches.getState().select(a.id)}
          onContextMenu={(e) => { useSketches.getState().select(a.id); showMenu(e, MENU) }}>
          <img src={api.thumbUrl(a.id, 256)} alt="" draggable={false} />
        </button>))}</div>
        : <div className="w-empty">{loading ? 'Reading the sketches…' : 'No sketches yet'}</div>}
    </div>
  )
}

export function SketchInspector() {
  const items = useSketches((s) => s.items)
  const selected = useSketches((s) => s.selected)
  const a = items.find((x) => x.id === selected)
  if (!a) return <aside className="w-insp"><span className="w-empty">Pick a sketch</span></aside>
  return (
    <aside className="w-insp" data-testid="world-sketch-inspector">
      <img className="w-preview" src={api.thumbUrl(a.id, 512)} alt="" />
      {a.prompt_text && <div className="w-prompt-block"><span>prompt</span><p className="w-prompt" title={a.prompt_text}>{a.prompt_text}</p></div>}
      <div className="w-verbs"><CommandButton id="world.sketch.character" text /><CommandButton id="world.sketch.prop" text /><CommandButton id="world.sketch.place" text /><CommandButton id="world.sketch.trash" text /></div>
    </aside>
  )
}
