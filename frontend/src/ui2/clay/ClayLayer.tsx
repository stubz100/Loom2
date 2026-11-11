// C0 (D181, propo02 04 §4.3): Clay — the scenes of the story, and the animations. The rail is Animations · Scenes. Animations is the
// workshop (D182): every animation as a tile, one opened on the animation bench. Scenes is the editor on a scene (a stage), opened from a
// shot card with the way back. RS1 (D197, proto02 01 §4.2): an entity's 3D — the body, the shell, the skeleton, a prop's model, a place's
// set, their bench and the line-up — is World's Clay mode (ui2/world/WorldClay.tsx); the Library's Figures / Props / Sets are gone.
import { Clapperboard, Film } from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { useRailState } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { NoProject } from '../NoProject'
import { Part } from '../Part'
import { shotsOnStage, startClay, useClay, useOpenScene, useScenes } from './clayStore'
import { sceneSeconds } from '../../suites/stage/sceneLength'
import { Help } from '../../frame/Help'
import './clayCommands'
import '../world/world.css'
import './clay.css'

// the editor's parts load with the scene (three.js)
const ClayColumn = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: ({ tab }: { tab: string }) => <m.ClayColumn tab={tab} /> })))
const ClayStrip = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Strip })))
const ClayStage = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Stage })))
const ClayFoot = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.ClayFoot })))
const SelectionInspector = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.SelectionInspector })))   // C1: one selected thing, one editor
const AnimationsGrid = lazy(() => import('./AnimationsGrid').then((m) => ({ default: m.AnimationsGrid })))   // D182 (C2b): the author's animations as tiles

const RAIL = [{ id: 'library', cmd: 'clay.rail.library', Icon: Film }, { id: 'scenes', cmd: 'clay.rail.scenes', Icon: Clapperboard }] as const

function Rail() {
  const rail = useClay((s) => s.rail)
  return <nav className="w-rail" aria-label="Clay">{RAIL.map(({ id, cmd, Icon }) => {
    const c = command(cmd)
    if (!c) return null
    return <button key={id} className={`w-rail-btn${rail === id ? ' active' : ''}`} title={c.hint ? `${c.label} — ${c.hint}` : c.label} aria-label={c.label} data-rail={id}
      disabled={!isEnabled(c)} onClick={() => runCommand(cmd)}><Icon size={18} /></button>
  })}</nav>
}

function LibraryHeader() {
  const view = useClay((s) => s.view)
  const animation = useClay((s) => s.animation)
  return (
    <div className="w-head" data-testid="clay-library-header">
      {view !== 'animation' && <div className="w-head-row"><span className="w-val">your animations, the project's, the downloaded clips</span><span className="spacer" /><CommandButton id="clay.anim.new" text /></div>}
      {view === 'animation' && animation && <div className="w-head-row c-anim-head" data-testid="clay-animation-header"><AnimationName animation={animation} /><TryOn key={animation.kind === 'template' ? animation.id : `${animation.file}:${animation.clip}`} /><span className="spacer" />
        <CommandButton id="clay.anim.save" text /><CommandButton id="clay.anim.saveAs" text /><CommandButton id="clay.anim.mine" text /><CommandButton id="clay.anim.back" text label="Back" /></div>}
    </div>
  )
}

/** D183 (C2c): the bench figure wears a character's shell for this animation — or the dummy (an animation is nobody's). */
function TryOn() {
  const profiles = useStory((s) => s.profiles)
  const [who, setWho] = useState<string | null>(null)
  useEffect(() => {                                                          // review K113: followed, not read once at the mount (the bench opens after it)
    let live = true, off: (() => void) | null = null
    void import('../../suites/stage/animationBench').then((m) => { if (live) off = m.watchTryOn(setWho) })
    return () => { live = false; off?.() }
  }, [])
  const chars = profiles.filter((p) => p.cls === 'character')
  const pick = (id: string | null) => void import('../../suites/stage/animationBench').then((m) => m.tryOn(id))
  const items = (): MenuItem[] => [{ label: 'the dummy', checked: !who, run: () => pick(null) },
    ...chars.map((p) => ({ label: `${p.name}${p.versions.find((v) => v.id === p.current)?.shell_asset_id ? '' : ' · no shell yet'}`, checked: who === p.id, run: () => pick(p.id) }))]
  const name = who ? chars.find((p) => p.id === who)?.name ?? '…' : 'the dummy'
  return <MenuButton label={`Try it on · ${name}`} items={items} text />
}

function AnimationName({ animation }: { animation: import('../../suites/stage/animationBench').AnimRef }) {
  const [name, setName] = useState<string>(animation.kind === 'clip' ? animation.clip : '…')
  useEffect(() => { let live = true; void import('../../suites/stage/animationBench').then((m) => m.nameOf(animation)).then((n) => { if (live) setName(n) }); return () => { live = false } }, [animation])
  return <b className="c-anim-name" title={animation.kind === 'clip' ? 'a downloaded clip — Make it mine to keep an edited copy' : 'an animation of your own'}>{name}{animation.kind === 'clip' ? <small> · downloaded</small> : null}</b>
}

/** The Library: the animations' tiles, or the one open on the animation bench (Clay's editor on it). */
function Library() {
  const view = useClay((s) => s.view)
  const bench = view === 'animation'
  return <>
    <section className="w-left" data-testid="clay-library">
      <LibraryHeader />
      <div className="w-panel">{bench ? <Suspense fallback={null}><ClayColumn tab="scene" /></Suspense>
        : <span className="hint" data-testid="clay-kind-hint">Pick an animation <Help text="An animation is yours to edit: open one on the bench, pose the figure at the frames you want, Save. A downloaded clip becomes yours with Make it mine." /></span>}</div>
    </section>
    <section className="w-centre">
      {bench ? <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip w-edit-strip"><ClayStrip /></div><div className="w-edit-stage" data-testid="clay-animation-bench"><ClayStage /></div></Suspense>
        : <Part label="The animations" fallback={<div className="w-empty">Reading the animations…</div>}><AnimationsGrid /></Part>}
    </section>
    {bench ? <Part label="The selection" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp" data-testid="clay-inspector"><SelectionInspector /></aside></Part>
      : <aside className="w-insp" data-testid="clay-inspector"><h4>Animations</h4><span className="w-val">A tile opens on the bench; its right-click renames, duplicates or removes it.</span></aside>}
  </>
}

/** Scenes: the scene open in the editor (a picker of the project's scenes with the shots each serves), the way back to the shot, then the
 *  editor's column and foot. */
function ScenesHeader() {
  const scene = useOpenScene()
  const scenes = useScenes(true)
  const shots = useStory((s) => s.shots)
  const nodes = useStory((s) => s.flowNodes)
  const from = useClay((s) => s.from)
  const label = (sh: { name: string; owner_node?: string | null }) => (sh.owner_node && nodes[sh.owner_node]?.title) || sh.name   // the storyboard's name for the shot
  const fromShot = from ? shots.find((s) => s.id === from.shot) : undefined
  const menu = (): MenuItem[] => [...scenes.map((s) => ({ label: `${s.name}${shotsOnStage(s.id, shots).length ? ` · ${shotsOnStage(s.id, shots).map(label).join(', ')}` : ''}`, checked: s.id === scene?.id, run: () => void useClay.getState().openScene(s.id, null) })),   // picked here: no shot to go back to
    { sep: true }, { cmd: 'stage.new' }]
  const on = scene ? shotsOnStage(scene.id, shots) : []
  return (
    <div className="w-head c-scene-head" data-testid="clay-scene-header">
      <div className="w-head-row">
        <MenuButton label={scene ? scene.name : scenes.length ? 'Pick a scene' : 'No scene yet'} items={menu} text />
        {scene && <span className="w-val" title="the scene's length (its Inspector sets it)">{sceneSeconds(scene)} s</span>}{/* C3 (Q4) */}
        <span className="spacer" />
        {from && <CommandButton id="clay.scene.back" text label={fromShot ? `← ${label(fromShot)}` : '← Back to the shot'} />}
      </div>
      {scene && <span className="c-scene-shots">{on.length ? `the camera of ${on.map(label).join(', ')}` : 'no shot on it yet'}{scene.purpose && scene.purpose !== 'stage' ? ` · ${scene.purpose}` : ''}</span>}
    </div>
  )
}

function Scenes() {
  const tab = useRailState((r) => r.active.stage) ?? 'scene'
  const project = useSession((s) => s.project)
  useEffect(() => { void useStory.getState().loadShots(); void useStory.getState().loadFlow() }, [project?.path])   // eslint-disable-line react-hooks/exhaustive-deps -- the shots on each scene, named by their nodes
  return <>
    <section className="w-left" data-testid="clay-scenes">
      <ScenesHeader />
      <div className="w-panel"><Suspense fallback={null}><ClayColumn tab={tab} /></Suspense></div>
      <div className="c-left-foot"><Suspense fallback={null}><ClayFoot /></Suspense></div>
    </section>
    <section className="w-centre">
      <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip w-edit-strip"><ClayStrip /></div><div className="w-edit-stage" data-testid="clay-scene"><ClayStage /></div></Suspense>
    </section>
    <Part label="The selection" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp" data-testid="clay-inspector"><SelectionInspector /></aside></Part>{/* C1 (26 §2 rule 3) */}
  </>
}

export function ClayLayer() {
  const rail = useClay((s) => s.rail)
  const project = useSession((s) => s.project)
  useEffect(() => startClay(), [])
  if (!project?.open) return <div className="w-layer"><Rail /><section className="w-centre wide"><NoProject /></section></div>
  return (
    <div className="w-layer c-layer" data-testid="clay-layer" data-rail={rail}>
      <Rail />
      {rail === 'library' ? <Library /> : <Scenes />}
    </div>
  )
}
