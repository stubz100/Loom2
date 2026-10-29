// B2a (D159, proto01_UI2 11 §7): Shots' Flow level — the canvas or its List view (D157 Q11: the Shots board, by scene, a search, each shot's
// steps, the picked shot's recipe under it), the Flow played through (Story's Play), a node's recipe in place of the canvas (*Open its recipe*), and the strip above them:
// the two views, the nodes to add, the problems, *Voice all lines (N)*, Validate, Play / Stop, Fit. A stage camera is linked from its sheet, as in Story.
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { runCommand } from '../../frame/commands'
import { FlowCanvas } from '../../suites/story/flow/FlowCanvas'
import { FlowRecipe, ShotRecipe } from '../../suites/story/recipe/StoryRecipe'
import { LinkStageSheet, ShotsBoard, VoiceAllButton } from '../../suites/story/ShotsBoard'
import { PlayView } from '../../suites/story/StoryParts'
import { useStory } from '../../suites/story/storyStore'
import type { MenuItem } from '../../frame/commands'
import { useShots } from './shotsStore'

export function ShotsFlow({ paneItems }: { paneItems: MenuItem[] }) {
  const play = useStory((s) => s.play)
  const recipe = useStory((s) => s.flowRecipe)
  const problems = useStory((s) => s.problems)
  const view = useShots((s) => s.flowView)
  const picked = useStory((s) => (s.shotId ? s.shots.find((x) => x.id === s.shotId) : undefined))
  return (
    <div className="s-flow-wrap">
      <div className="strip s-flow-strip" data-testid="shots-flow-strip">
        <span className="segmented" role="group" aria-label="the Flow as">
          <button className={view === 'canvas' ? 'active' : ''} onClick={() => runCommand('shots.flow.canvas')} title="the Flow's nodes and their routes">Canvas</button>
          <button className={view === 'list' ? 'active' : ''} onClick={() => runCommand('shots.flow.list')} title="the shots in the Flow's order, each with its steps (the Shots board)">List</button>
        </span>
        {recipe && <CommandButton id="story.flow.recipeClose" text />}
        {view === 'canvas' && !play && !recipe && <CommandRow ids={['story.flow.add.start', 'story.flow.add.shot', 'story.flow.add.choice', 'story.flow.add.condition', 'story.flow.add.action', 'story.flow.add.hub', 'story.flow.add.jump', 'story.flow.add.comment']} />}
        <span className="spacer" />
        {problems && <span className={`hint${problems.length ? ' warn' : ''}`}>{problems.length ? `${problems.length} problem${problems.length === 1 ? '' : 's'}` : 'valid'}</span>}
        <VoiceAllButton />
        <CommandButton id="story.flow.validate" />
        {play ? <CommandButton id="story.flow.stop" /> : <CommandButton id="story.flow.play" />}
        {view === 'canvas' && <CommandButton id="story.flow.fit" />}
      </div>
      <div className="s-flow">
        {play ? <PlayView /> : recipe ? <FlowRecipe /> : view === 'list' ? <div className="s-list shots-stage"><ShotsBoard />{picked && <ShotRecipe shotId={picked.id} version={picked.current} />}</div>
          : <FlowCanvas onOpen={(id) => useShots.getState().open(id, 'clay')} paneItems={paneItems} />}
      </div>
      <LinkStageSheet />
    </div>
  )
}
