// D95 (AN1, proto01_animate 03 §4.1): the Animate tab's viewer levels — Clay (the stage suite: sets, figures, cameras, keys), Performance
// (the animate suite: the clip a model made) and, since AE1 / AP1 (D114), Final (the composition of a final shot, scrubbed and played) —
// at the start of the viewer strip. D121 (26 §5): each level is a mode — a suite of its own (stage · animate · final) with its own column,
// strip, viewer and foot — so the switch is the mode's pill (ArtCraft's Build | Record). The registry's commands (D32) do the switching, so
// the palette and remapped keys (1 · 2 · 3) reach them — the same commands at every mode (anim.level.*, each mode's reach). RC1: Graph — the shot's recipe over the viewer of whichever mode is on (4).
import { useSession } from '../store/session'
import { markUsed, runCommand } from './commands'

export function AnimateLevels() {
  const suite = useSession((s) => s.ui.suite)
  markUsed('anim.level.clay'); markUsed('anim.level.performance'); markUsed('anim.level.final')
  const clay = suite === 'stage', perf = suite === 'animate', fin = suite === 'final'
  return (
    <span className="segmented animate-levels" role="group" aria-label="Animate level">
      <button type="button" className={clay ? 'active' : ''} aria-pressed={clay} onClick={() => runCommand('anim.level.clay')} title="Clay: compose the scene — set, figures, props, cameras, motion (1)">Clay</button>
      <button type="button" className={perf ? 'active' : ''} aria-pressed={perf} onClick={() => runCommand('anim.level.performance')} title="Performance: make the moving picture — image to video, a clip from the stage, the final shot's layers (2)">Performance</button>
      <button type="button" className={fin ? 'active' : ''} aria-pressed={fin} onClick={() => runCommand('anim.level.final')} title="Final: finish the shot's composition — layers, masks, effects, passes, the render (3)">Final</button>
    </span>
  )
}

/** RC1: the Graph pill beside the modes — the shot's recipe over the viewer (the mode's column stays). */
export function GraphPill() {
  const graph = useSession((s) => !!s.ui.graph)
  markUsed('anim.level.graph')
  return <button type="button" className={`graph-pill${graph ? ' active' : ''}`} aria-pressed={graph} onClick={() => runCommand('anim.level.graph')} title="Graph: the shot's recipe — what it is made of, what is stale; a node opens where it is made (4)">Graph</button>
}
