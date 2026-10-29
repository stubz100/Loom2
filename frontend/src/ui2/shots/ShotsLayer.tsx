// U4 (D157, proto01_UI2 04 §2): Shots — what happens, shot by shot, refined level by level. The storyboard strip shows the route's shots
// with their level dots; the rail is Flow, then the open shot's Clay · Performance · Final; the left column is the shot's header (§2.1) and
// the level's sections; the centre the level's viewer. U4a–c: the frame, the strip, the header, the Flow and Clay; Performance and Final are U6.
import { lazy, Suspense, useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { DOT } from './route'
import { useRouteRows } from './scene'
import { ShotHeader } from './ShotHeader'
import { LEVELS, startShots, useShots } from './shotsStore'
import './shotsCommands'
import '../world/world.css'
import './shots.css'

// the reused parts load with their level (the Flow's canvas; Clay's three.js)
const FlowCanvas = lazy(() => import('../../suites/story/flow/FlowCanvas').then((m) => ({ default: m.FlowCanvas })))
const StoryInspector = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.Inspector })))
const ClayColumn = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: () => <m.ClayColumn tab="scene" /> })))
const ClayStrip = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Strip })))
const ClayStage = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Stage })))
const ClayFoot = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.ClayFoot })))

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
  })}</nav>
}

function Centre() {
  const level = useShots((s) => s.level)
  const v = useStory((st) => st.shotVersion())
  if (level === 'flow') return <Suspense fallback={null}><div className="s-flow"><FlowCanvas onOpen={(id) => useShots.getState().open(id, 'clay')} paneItems={[...NEW_SHOT, { sep: true }]} /></div></Suspense>
  if (level === 'clay') return v?.stage_id
    ? <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip s-clay-strip"><ClayStrip /></div><div className="s-clay"><ClayStage /></div></Suspense>
    : <div className="w-empty">No scene yet <CommandButton id="shots.scene.new" text /></div>
  return <div className="w-empty">{level === 'performance' ? 'Performance' : 'Final'} — not built yet <Help text="U6 (proto01_UI2 04 §4–5): the clay made into footage, then the shot assembled with its voice and processing." /></div>
}

export function ShotsLayer() {
  const project = useSession((s) => s.project)
  const level = useShots((s) => s.level)
  const staged = useStory((st) => !!st.shotVersion()?.stage_id)
  useEffect(() => startShots(), [])
  if (!project?.open) return <div className="w-layer"><nav className="w-rail" /><section className="w-centre wide"><div className="w-empty">Open or create a project</div></section></div>
  const clay = level === 'clay' && staged
  return (
    <div className="s-layer" data-testid="shots-layer" data-level={level}>
      <Storyboard />
      <div className={`w-layer s-body${level === 'flow' ? '' : ' no-insp'}`}>
        <Rail />
        <section className="w-left"><ShotHeader />
          <div className="w-panel">{clay ? <Suspense fallback={null}><ClayColumn /></Suspense> : null}</div>
          {clay && <div className="s-foot"><Suspense fallback={null}><ClayFoot /></Suspense><CommandButton id="shots.toPerformance" text /></div>}
        </section>
        <section className="w-centre"><Centre /></section>
        {level === 'flow' && <aside className="w-insp s-insp"><Suspense fallback={null}><StoryInspector /></Suspense></aside>}
      </div>
    </div>
  )
}
