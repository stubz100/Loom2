// U4 (D157, proto01_UI2 04 §2): Shots — what happens, shot by shot, refined level by level. The storyboard strip shows the route's shots
// with their level dots; the rail is Flow, then the open shot's Clay · Performance · Final; the left column is the shot's header (§2.1) and
// the level's sections; the centre the level's viewer. U4a–c: the frame, the strip, the header, the Flow and Clay; Performance and Final are U6.
import { lazy, Suspense, useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { DOT } from './route'
import { useRouteRows } from './scene'
import { ShotHeader } from './ShotHeader'
import { LEVELS, owedTitle, startShots, useShots } from './shotsStore'
import './shotsCommands'
import '../world/world.css'
import './shots.css'

// the reused parts load with their level (the Flow's canvas; Clay's three.js)
const ShotsFlow = lazy(() => import('./ShotsFlow').then((m) => ({ default: m.ShotsFlow })))   // B2a: the canvas or its List view, Play, a node's recipe
const BoardPanel = lazy(() => import('../../suites/story/ShotsBoard').then((m) => ({ default: m.BoardPanel })))
const AnimateGraph = lazy(() => import('../../suites/story/recipe/AnimateGraph'))   // B2a (RC1b): the shot's recipe over its level
const StoryInspector = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.Inspector })))
const ClayColumn = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: () => <m.ClayColumn tab="scene" /> })))
const ClayStrip = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Strip })))
const ClayStage = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Stage })))
const ClayFoot = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.ClayFoot })))
// U6b (04 §4–5): Performance and Final — Animate's two other modes, mounted as they are on the open shot (the For chip its version)
const PerfColumn = lazy(() => import('../../suites/animate/AnimateSuite').then((m) => ({ default: () => <m.AnimateSuite.Panel tab="performance" /> })))
const PerfStrip = lazy(() => import('../../suites/animate/AnimateSuite').then((m) => ({ default: m.AnimateSuite.Strip })))
const PerfStage = lazy(() => import('../../suites/animate/AnimateSuite').then((m) => ({ default: m.AnimateSuite.Stage })))
const PerfFoot = lazy(() => import('../../suites/animate/AnimateSuite').then((m) => ({ default: m.AnimateSuite.PrimaryAction! })))
const FinalColumn = lazy(() => import('../../suites/animate/FinalSuite').then((m) => ({ default: () => <m.FinalSuite.Panel tab="layers" /> })))
const FinalStrip = lazy(() => import('../../suites/animate/FinalSuite').then((m) => ({ default: m.FinalSuite.Strip })))
const FinalStage = lazy(() => import('../../suites/animate/FinalSuite').then((m) => ({ default: m.FinalSuite.Stage })))
const FinalFoot = lazy(() => import('../../suites/animate/FinalSuite').then((m) => ({ default: m.FinalSuite.PrimaryAction! })))

const NEW_SHOT: MenuItem[] = [{ cmd: 'shots.new.scene' }, { cmd: 'shots.new.same' }]

function Storyboard() {
  const route = useRouteRows()
  const shotId = useStory((s) => s.shotId)
  return (
    <div className="s-board" data-testid="shots-storyboard" onContextMenu={(e) => { if (e.target === e.currentTarget) showMenu(e, NEW_SHOT) }}>
      {route.map((r) => (
        <button key={r.shot.id} className={`s-card${shotId === r.shot.id ? ' active' : ''}`} data-id={r.shot.id} title={r.group ? `${r.group} · ${r.label}` : r.label}
          onClick={() => useShots.getState().open(r.shot.id)} onContextMenu={(e) => { useShots.getState().open(r.shot.id); showMenu(e, NEW_SHOT) }}>
          <span className="s-thumb">{r.thumb ? <img src={api.thumbUrl(r.thumb, 256)} alt="" draggable={false} /> : null}</span>
          <span className="s-name"><b>{r.n}</b> {r.label}</span>
          <span className="s-dots" title="Clay · Performance · Final">{DOT[r.dots.clay]}{DOT[r.dots.performance]}{DOT[r.dots.final]}</span>
        </button>
      ))}
      <div className="s-new"><MenuButton label="＋ New shot" items={() => NEW_SHOT} text /></div>
    </div>
  )
}

function Rail() {
  const level = useShots((s) => s.level)
  useStory((s) => s.shotId)                                               // the levels of a shot enable with the selection
  return <nav className="w-rail" aria-label="Shots">{LEVELS.map((l, i) => {
    const c = command(`shots.level.${l.id}`)
    if (!c) return null
    const Icon = c.icon!
    return <div key={l.id} style={{ display: 'contents' }}>
      {i === 1 && <div className="w-rail-sep" />}
      <button className={`w-rail-btn${level === l.id ? ' active' : ''}`} title={c.hint ? `${c.label} — ${c.hint}` : c.label} aria-label={c.label} data-level={l.id}
        disabled={!isEnabled(c)} onClick={() => runCommand(c.id)}><Icon size={18} /></button>
    </div>
  })}<div className="w-rail-sep" /><GraphToggle /></nav>
}

/** B2a (RC1b): the shot's recipe graph over the level — on and off from the rail. */
function GraphToggle() {
  const on = useSession((s) => !!s.ui.graph)
  useShots((s) => s.level)
  const c = command('shots.graph')
  if (!c) return null
  const Icon = c.icon!
  return <button className={`w-rail-btn${on ? ' active' : ''}`} title={`${c.label} — ${c.hint}`} aria-label={c.label} aria-pressed={on} data-level="graph"
    disabled={!isEnabled(c)} onClick={() => runCommand(c.id)}><Icon size={18} /></button>
}

function Centre() {
  const level = useShots((s) => s.level)
  const graph = useSession((s) => !!s.ui.graph)                                       // B2a: the Graph over the level (the rail's toggle)
  const v = useStory((st) => st.shotVersion())
  if (level === 'flow') return <Suspense fallback={null}><ShotsFlow paneItems={[...NEW_SHOT, { sep: true }]} /></Suspense>
  if (level === 'clay') return v?.stage_id
    ? <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip s-clay-strip"><ClayStrip /></div><div className="s-clay"><ClayStage />{graph && <AnimateGraph />}</div></Suspense>
    : <div className="w-empty">No scene yet <CommandButton id="shots.scene.new" text /></div>
  if (!v?.stage_id) return <div className="s-clay"><div className="w-empty">No scene yet <CommandButton id="shots.scene.new" text /></div>{graph && <Suspense fallback={null}><AnimateGraph /></Suspense>}</div>   // the recipe needs no scene
  const [Strip, Stage] = level === 'performance' ? [PerfStrip, PerfStage] : [FinalStrip, FinalStage]
  return <Suspense fallback={<div className="w-empty">Loading {level === 'performance' ? 'Performance' : 'Final'}…</div>}>
    <div className="strip s-clay-strip" data-testid={`shots-${level}-strip`}><Strip /></div><div className="s-clay" data-testid={`shots-${level}`}><Stage />{graph && <AnimateGraph />}</div>
  </Suspense>
}

/** The level's column and foot under the header (Clay's, Performance's or Final's), the way on to the next level beside the foot's verb. */
function LevelColumn() {
  const level = useShots((s) => s.level)
  const owed = useShots((s) => s.owed)
  const staged = useStory((st) => !!st.shotVersion()?.stage_id)
  const list = useShots((s) => s.flowView === 'list')
  if (level === 'flow') return <div className="w-panel">{list && <Suspense fallback={null}><BoardPanel /></Suspense>}</div>   // B2a: the List view's filters and order
  if (!staged) return <div className="w-panel" />
  const [Col, Foot, next] = level === 'clay' ? [ClayColumn, ClayFoot, 'shots.toPerformance'] : level === 'performance' ? [PerfColumn, PerfFoot, 'shots.toFinal'] : [FinalColumn, FinalFoot, 'story.shot.finalize']
  return <>
    <div className="w-panel"><Suspense fallback={null}><Col /></Suspense></div>
    <div className="s-foot"><Suspense fallback={null}><Foot /></Suspense>
      {(level === 'performance' || level === 'final') && owed && <span className="s-owed-work" data-owed={owed.queued} title={owedTitle(owed)}>
        {!!owed.queued && <CommandButton id="shots.performOwed" text label={`Perform the owed layers ▶ · ≈ ${owed.minutes} min on the GPU`} />}
        {owed.items.length > owed.queued && <span className="hint" data-owed-listed={owed.items.length - owed.queued}>{owed.items.length - owed.queued} not queued</span>}</span>}
      <CommandButton id={next} text label={level === 'final' ? 'Mark the shot final ✓' : undefined} /></div>
  </>
}

export function ShotsLayer() {
  const project = useSession((s) => s.project)
  const level = useShots((s) => s.level)
  useEffect(() => startShots(), [])
  if (!project?.open) return <div className="w-layer"><nav className="w-rail" /><section className="w-centre wide"><div className="w-empty">Open or create a project</div></section></div>
  return (
    <div className="s-layer" data-testid="shots-layer" data-level={level}>
      <Storyboard />
      <div className={`w-layer s-body${level === 'flow' ? '' : ' no-insp'}`}>
        <Rail />
        <section className="w-left"><ShotHeader /><LevelColumn /></section>
        <section className="w-centre"><Centre /></section>
        {level === 'flow' && <aside className="w-insp s-insp"><Suspense fallback={null}><StoryInspector /></Suspense></aside>}
      </div>
    </div>
  )
}
