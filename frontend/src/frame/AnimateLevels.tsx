// D95 (AN1, proto01_animate 03 §4.1): the Animate tab's viewer levels — Clay (the stage suite: sets, figures, cameras, keys), Performance
// (the animate suite: the clip a model made) and, since AE1 / AP1 (D114), Final (the composition of a final shot, scrubbed and played) —
// at the start of the viewer strip. D121 (26 §5): each level is a mode — a suite of its own (stage · animate · final) with its own column,
// strip, viewer and foot — so the switch is the mode's pill (ArtCraft's Build | Record). The registry's commands (D32) do the switching, so
// the palette and remapped keys (1 · 2 · 3) reach them. Graph (the Shot's recipe, RC1) joins when it is built.
import { useSession } from '../store/session'
import { markUsed, runCommand } from './commands'

export function AnimateLevels() {
  const suite = useSession((s) => s.ui.suite)
  markUsed('global.suite.stage'); markUsed('stage.level.performance'); markUsed('anim.level.clay')
  markUsed('stage.level.final'); markUsed('anim.level.final'); markUsed('anim.level.performance')
  const clay = suite === 'stage', perf = suite === 'animate', fin = suite === 'final'
  return (
    <span className="segmented animate-levels" role="group" aria-label="Animate level">
      <button type="button" className={clay ? 'active' : ''} aria-pressed={clay} onClick={() => runCommand(clay ? 'global.suite.stage' : 'anim.level.clay')} title="Clay: compose the scene — set, figures, props, cameras, motion (1)">Clay</button>
      <button type="button" className={perf ? 'active' : ''} aria-pressed={perf} onClick={() => runCommand(clay ? 'stage.level.performance' : 'anim.level.performance')} title="Performance: make the moving picture — image to video, a clip from the stage, the final shot's layers (2)">Performance</button>
      <button type="button" className={fin ? 'active' : ''} aria-pressed={fin} onClick={() => runCommand(clay ? 'stage.level.final' : 'anim.level.final')} title="Final: finish the shot's composition — layers, masks, effects, passes, the render (3)">Final</button>
    </span>
  )
}
