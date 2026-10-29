// U7a (D157, proto01_UI2 05 §1): Episode — how the shots play together and what leaves loom2. Today's FilmCraft cut editor (D126, CE1–CE5)
// mounted as it is (Story's Episode tab: the cuts and the bins, the tracks, the Inspector, the foot), with the route's Finals listed in
// order beside it: each shot's final (✓ rendered, ○ not yet, ! stale since), and whether the shot is marked final; a click opens it in Shots.
import { lazy, Suspense, useEffect } from 'react'
import { navigate } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { useRouteRows } from '../shots/scene'
import '../world/world.css'
import './episode.css'

const Panel = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: () => <m.Panel tab="episode" /> })))
const Stage = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.Stage })))
const Foot = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.PrimaryAction })))
const Inspector = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.Inspector })))

const MARK: Record<string, [string, string]> = { done: ['✓', 'rendered'], stale: ['!', 'changed since its render'], owed: ['○', 'not rendered yet'], running: ['◐', 'rendering'] }

/** The route's shots in order with their finals (05 §1: the one thing a cut's V1 takes). */
function Finals() {
  const rows = useRouteRows()
  return (
    <div className="e-finals" data-testid="episode-finals">
      <h4>Finals</h4>
      {rows.length ? <ol>{rows.map((r) => {
        const state = r.dots.final === 'na' ? 'owed' : r.dots.final                     // D157: every shot owes a final (the old routes owed none)
        const [mark, why] = MARK[state] ?? MARK.owed
        const marked = r.v.state === 'final'
        return <li key={r.shot.id} data-id={r.shot.id} data-final={state}>
          <button className="link" title={`${r.label}: its final ${why}${marked ? ' · the shot is marked final' : ''} — open it in Shots`}
            onClick={() => { navigate({ suite: 'final' }); void import('../shots/shotsStore').then((m) => m.useShots.getState().open(r.shot.id, 'final')) }}>
            <span className={`e-mark m-${state}`}>{mark}</span> {r.n} · {r.label}</button>
          {marked && <span className="e-lock" title="marked final">final</span>}
        </li>
      })}</ol> : <span className="w-val">No shot on the route yet</span>}
    </div>
  )
}

export function EpisodeLayer() {
  const project = useSession((s) => s.project)
  useEffect(() => { navigate({ suite: 'story', tab: 'episode' }) }, [])                  // the cut editor's keys and reads come alive with its tab
  useEffect(() => { if (project?.open) { const st = useStory.getState(); void Promise.all([st.loadFlow(), st.loadShots()]).then(() => void useStory.getState().loadBoard()) } }, [project?.path])   // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <div className="e-layer"><section className="w-centre wide"><div className="w-empty">Open or create a project</div></section></div>
  return (
    <div className="e-layer" data-testid="episode-layer">
      <section className="w-left"><div className="w-panel"><Finals /><Suspense fallback={null}><Panel /></Suspense></div>
        <div className="s-foot"><Suspense fallback={null}><Foot /></Suspense></div></section>
      <section className="w-centre"><Suspense fallback={<div className="w-empty">Loading the cut…</div>}><div className="e-stage"><Stage /></div></Suspense></section>
      <aside className="w-insp"><Suspense fallback={null}><Inspector /></Suspense></aside>
    </div>
  )
}
