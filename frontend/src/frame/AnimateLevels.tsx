// D95 (AN1, proto01_animate 03 §4.1): the Animate tab's viewer levels — Clay (the stage suite: sets, figures, cameras, keys) and Performance
// (the animate suite: the clip a model made), at the start of the viewer strip of both. The registry's suite commands (D32) do the switching,
// so the palette and remapped keys reach them. Final (the composition, AE1) and Graph (the Shot's recipe, RC1) join when they are built.
import { useSession } from '../store/session'
import { markUsed, runCommand } from './commands'

export function AnimateLevels() {
  const suite = useSession((s) => s.ui.suite)
  markUsed('global.suite.stage'); markUsed('global.animate.performance')
  return (
    <span className="segmented animate-levels" role="group" aria-label="Animate level">
      <button type="button" className={suite === 'stage' ? 'active' : ''} aria-pressed={suite === 'stage'} onClick={() => runCommand('global.suite.stage')} title="Clay: the stage — set, figures, cameras, motion keys">Clay</button>
      <button type="button" className={suite === 'animate' ? 'active' : ''} aria-pressed={suite === 'animate'} onClick={() => runCommand('global.animate.performance')} title="Performance: the clips a model made from the shot (image to video, pose- or depth-guided)">Performance</button>
    </span>
  )
}
