// D95 (AN1, proto01_animate 03 §4.1): the Animate tab's viewer levels — Clay (the stage suite: sets, figures, cameras, keys), Performance
// (the animate suite: the clip a model made) and, since AE1 / AP1 (D114), Final (the composition of a final shot, scrubbed and played) —
// at the start of the viewer strip of both suites. The registry's suite commands (D32) do the switching, so the palette and remapped keys
// reach them. Graph (the Shot's recipe, RC1) joins when it is built.
import { useSession } from '../store/session'
import { useComposition } from '../suites/animate/compositionStore'
import { markUsed, runCommand } from './commands'

export function AnimateLevels() {
  const suite = useSession((s) => s.ui.suite)
  const level = useComposition((s) => s.level)
  markUsed('global.suite.stage'); markUsed('stage.level.performance'); markUsed('anim.level.clay')
  markUsed('stage.level.final'); markUsed('anim.level.final'); markUsed('anim.level.performance')
  const clay = suite === 'stage'
  const perf = suite === 'animate' && level !== 'final'
  const fin = suite === 'animate' && level === 'final'
  return (
    <span className="segmented animate-levels" role="group" aria-label="Animate level">
      <button type="button" className={clay ? 'active' : ''} aria-pressed={clay} onClick={() => runCommand(suite === 'animate' ? 'anim.level.clay' : 'global.suite.stage')} title="Clay: the stage — set, figures, cameras, motion keys (1)">Clay</button>
      <button type="button" className={perf ? 'active' : ''} aria-pressed={perf} onClick={() => runCommand(suite === 'stage' ? 'stage.level.performance' : 'anim.level.performance')} title="Performance: the clips a model made from the stage or a start image (2)">Performance</button>
      <button type="button" className={fin ? 'active' : ''} aria-pressed={fin} onClick={() => runCommand(suite === 'stage' ? 'stage.level.final' : 'anim.level.final')} title="Final: the shot's composition — scrub it, play it, finish it (3)">Final</button>
    </span>
  )
}
