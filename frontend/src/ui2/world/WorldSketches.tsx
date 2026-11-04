// U3d (D157, proto01_UI2 03 §7): World's Sketches — the brainstorm's pictures that belong to no one yet, in `bin/world/sketches`. Free
// pictures are made with Image's whole column (the full prompt, the Library's words, here only) in a Make context of their own; a sketch's
// *Prototype ▸* makes a draft entity of a class from it — the picture becomes its hero. RG1 (D187 Q1, D188): a hand and a feet framing
// to sketch hands and shoes freely — the reference framings' sentences, square, on Klein; the words are the author's own.
import { useEffect } from 'react'
import { api } from '../../api/client'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { PART_PX } from './make'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import type { MenuItem } from '../../frame/commands'
import { makeContext, useGenerate } from '../../suites/generate/generateStore'
import { GenerateColumn } from '../../suites/generate/GenerateColumn'
import { BinGrid } from '../bin/BinGrid'
import { useSketches } from './sketches'
import type { Asset } from '../../api/types'
import '../../suites/generate/generate.css'
import '../bin/bin.css'

const MENU: MenuItem[] = [{ cmd: 'world.sketch.character' }, { cmd: 'world.sketch.prop' }, { cmd: 'world.sketch.place' }, { sep: true }, { cmd: 'world.sketch.trash' }]

// B2a's *From a stage* foot is gone (D186): a still of a stage is made in Clay's *Still* section, beside the scene it renders
/** RG1 (D187 Q1, D188): the framings a hand or the feet are sketched with — a chip fills the framing words with the reference's sentence and
 *  sets the square frame and Klein (E62 a: the clean close-up); nothing is queued, the words stay the author's to write. */
function SketchFramings() {
  const refs = useSession((s) => s.capabilities?.story?.references?.character)
  const words = useGenerate((s) => s.panel.tree.composition ?? '')
  const klein = useSession((s) => s.capabilities?.story?.model_id)
  const chips = ([['hand', 'a hand'], ['feet', 'feet & shoes']] as const).filter(([k]) => !!refs?.[k])
  if (!chips.length) return null
  const put = (k: 'hand' | 'feet') => {
    const g = useGenerate.getState()
    g.setTree({ composition: refs?.[k] ?? '' })
    g.set({ width: PART_PX, height: PART_PX, tier: 'custom' })
    if (klein && g.panel.model_id !== klein) g.setModel(klein)
  }
  return (
    <div className="w-field w-sketch-framing" data-testid="sketch-framings"><span>framing <Help text="A hand alone, palm to the camera, or the feet and shoes from the side — the words a character's hand or feet picture is made with, square, on Klein. Write the hand or the shoes in the prompt; nothing is queued here." /></span>
      <div className="w-chips left">{chips.map(([k, label]) => <button key={k} className={words.trim() === refs?.[k]?.trim() ? 'active' : ''} aria-pressed={words.trim() === refs?.[k]?.trim()} onClick={() => put(k)}>{label}</button>)}</div>
    </div>
  )
}

export function SketchColumn() {
  const pv = useGenerate((s) => s.preview)
  const count = useGenerate((s) => s.panel.count)
  useEffect(() => { makeContext.enter('world/sketches') }, [])
  const secs = pv?.estimate.seconds ? Math.round(pv.estimate.seconds * count) : null
  return (
    <div className="w-sketch-col" data-testid="world-sketches">
      <SketchFramings />
      <div className="w-sketch-gen"><GenerateColumn tab="prompt" /></div>
      <div className="w-foot"><CommandButton id="world.sketch.make" text label={`Make ${count} sketch${count === 1 ? '' : 'es'} ▶${secs ? ` ≈ ${secs < 90 ? `${secs} s` : `${Math.round(secs / 60)} min`}` : ''}`} /></div>
    </div>
  )
}

const keyOf = (a: Asset) => a.id
const more = () => void useSketches.getState().more()

export function SketchCentre() {
  const items = useSketches((s) => s.items)
  const selected = useSketches((s) => s.selected)
  const loading = useSketches((s) => s.loading)
  useEffect(() => { void useSketches.getState().load() }, [])
  return (
    <div className="w-bin">
      <div className="w-bin-head"><span className="w-path">bin/world/sketches</span><span className="spacer" /><CommandButton id="world.ideas.fold" text /></div>
      {items.length ? <BinGrid items={items} keyOf={keyOf} onEnd={more} render={(a) => (   /* B4: windowed, a page at a time — every free thing lives here */
        <button className={`w-tile${selected === a.id ? ' selected' : ''}`} data-id={a.id} title={a.prompt_text ?? ''} onClick={() => useSketches.getState().select(a.id)}
          onContextMenu={(e) => { useSketches.getState().select(a.id); showMenu(e, MENU) }}>
          <img src={api.thumbUrl(a.id, 256)} alt="" draggable={false} />
        </button>)} />
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
