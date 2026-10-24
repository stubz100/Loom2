// RC1 (D96, proto01_animate 28): the recipe graph in Story — in the Flow in place of the canvas (a node's *Open its recipe*), and on the shot
// page under the board. A node opens where it is made (openTarget); *Open the graph in Animate* sets the For chip and turns Animate's Graph on.
import { CommandButton } from '../../../frame/CommandButton'
import { Help } from '../../../frame/Help'
import { useStory } from '../storyStore'
import { RecipeGraph } from './RecipeGraph'
import { targetOf } from './graph'
import { openTarget } from './openTarget'

/** The Flow's in-place graph: the node's shot at the version the node shows. */
export function FlowRecipe() {
  const nid = useStory((s) => s.flowRecipe)
  const nodes = useStory((s) => s.flowNodes)
  const shots = useStory((s) => s.shots)
  const n = nid ? nodes[nid] : undefined
  const s = n?.shot_id ? shots.find((x) => x.id === n.shot_id) : undefined
  const vid = n?.shot_version ?? s?.current
  return (
    <div className="recipe-pane" data-testid="flow-recipe">
      <div className="recipe-strip">
        <CommandButton id="story.flow.recipeClose" text />
        {n && s ? <span><b>{n.title || s.name}</b> · {s.name} {vid}</span> : <span>No shot.</span>}
        <span className="spacer" />
        <CommandButton id="story.shot.graphInAnimate" text />
      </div>
      <div className="recipe-body">{s && vid ? <RecipeGraph shotId={s.id} version={vid} onPick={(x, g) => openTarget(targetOf(x, g), s.id, vid)} /> : null}</div>
    </div>
  )
}

/** The shot page's Recipe section: the graph of the version the page shows. */
export function ShotRecipe({ shotId, version }: { shotId: string; version: string }) {
  return (
    <section className="shot-recipe">
      <h3>Recipe <Help text={"What the shot is made of, from its characters to its take: each part done, stale (an input changed since — and everything after it), owed or running. A click opens a part where it is made."} /></h3>
      <div className="recipe-box"><RecipeGraph shotId={shotId} version={version} onPick={(x, g) => openTarget(targetOf(x, g), shotId, version)} /></div>
    </section>
  )
}
