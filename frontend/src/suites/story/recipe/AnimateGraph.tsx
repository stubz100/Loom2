// RC1 (D96, proto01_animate 28; UX0 W6): Animate's Graph — the For chip's shot's recipe over the viewer of whichever mode is on (the mode's
// column stays). A node opens where it is made: Story › Cast for a character or its animation reference, Clay's Motion on its figure and
// Camera, Performance's Final shot card for the plate and the layers, Final's Layers for the composition and the finish, Final's Output
// for the take (graph.targetOf). The Graph stays on until its pill or 4 turns it off.
import { useState } from 'react'
import { CommandButton } from '../../../frame/CommandButton'
import { Help } from '../../../frame/Help'
import { forLabel, useMakeFor } from '../../../store/origin'
import { ROUTE_LABEL } from '../board'
import { RecipeGraph } from './RecipeGraph'
import { targetOf, type ShotGraph } from './graph'
import { openTarget } from './openTarget'

export default function AnimateGraph() {
  const f = useMakeFor((s) => s.animate)
  const [g, setG] = useState<ShotGraph | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  if (!f) return (
    <div className="recipe-overlay" data-testid="animate-graph">
      <div className="recipe-strip"><b>Graph</b><span className="spacer" /><CommandButton id="anim.level.graph" text label="Close the graph" /></div>
      <div className="recipe-empty"><span>No shot. <Help text="The Graph shows a Story shot's recipe. Animate opened for a shot — a cell of Story › Shots, Make clip ▸ on a shot — names it in the For chip." /></span></div>
    </div>
  )
  return (
    <div className="recipe-overlay" data-testid="animate-graph">
      <div className="recipe-strip">
        <b>{forLabel(f)}</b>
        {g && <span>{ROUTE_LABEL[g.route] ?? g.route}</span>}
        {g && <span className={g.stale ? 'warn' : ''}>{g.stale ? `${g.stale} stale` : 'nothing stale'}{g.owed ? ` · ${g.owed} owed` : ''}</span>}
        <Help text="The shot's recipe: what it is made of, from its characters to its take. Stale: an input changed since it was made — and everything after it. A click opens a node where it is made; Run stale makes the steps the server can make again." />
        <span className="spacer" />
        <CommandButton id="anim.for.runStale" text />
        <CommandButton id="anim.level.graph" text label="Close the graph" />
      </div>
      <div className="recipe-body">
        <RecipeGraph shotId={f.shot_id} version={f.version} picked={picked} onLoad={setG}
          onPick={(n, gr) => { setPicked(n.id); openTarget(targetOf(n, gr), f.shot_id, f.version) }} />
      </div>
    </div>
  )
}
