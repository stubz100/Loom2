// U4 (D157, proto01_UI2 04 §8): Shots' commands (rule 3: every action a command with a mouse home; keys are accelerators). They act on the
// shot the header shows (the Story store's selection) and the level the rail shows.
import { Box, Clapperboard, GitBranch, List, MonitorPlay, Plus, SquarePlus, Text, Workflow } from 'lucide-react'
import { registerCommands } from '../../frame/commands'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { rescene } from './scene'
import { newShot, useShots, type ShotLevel } from './shotsStore'

const open = () => !!useSession.getState().project?.open
const shot = () => useStory.getState().shot()
const level = (id: ShotLevel) => () => useShots.getState().setLevel(id)

registerCommands([
  // B2a (D159, 11 §7): the Flow's two views; the shot's recipe graph over its level (Animate's Graph)
  { id: 'shots.flow.canvas', scope: 'shots', label: 'The Flow as a canvas', icon: GitBranch, placement: ['strip'], when: open, run: () => useShots.getState().setFlowView('canvas') },
  { id: 'shots.flow.list', scope: 'shots', label: 'The Flow as a list', icon: List, placement: ['strip'], hint: "the shots in the Flow's order with their steps, by scene, searched (the Shots board)", when: open,
    run: () => useShots.getState().setFlowView('list') },
  { id: 'shots.graph', scope: 'shots', label: 'Graph', icon: Workflow, placement: ['rail'], hint: "the shot's recipe — what it is made of, what is stale; a node opens where it is made",
    when: () => !!shot() && useShots.getState().level !== 'flow', run: () => { const s = useSession.getState(); s.setUi({ graph: !s.ui.graph }) } },
  { id: 'shots.level.flow', scope: 'shots', label: 'Flow', icon: GitBranch, placement: ['rail'], when: open, run: level('flow'), hint: 'the story\'s graph — its shots, lines and choices' },
  { id: 'shots.level.clay', scope: 'shots', label: 'Clay', icon: Box, placement: ['rail'], when: () => !!shot(), run: level('clay'), hint: 'the shot\'s scene through its camera: blocking, poses, the camera\'s moves' },
  { id: 'shots.level.performance', scope: 'shots', label: 'Performance', icon: Clapperboard, placement: ['rail'], when: () => !!shot(), run: level('performance') },
  { id: 'shots.level.final', scope: 'shots', label: 'Final', icon: MonitorPlay, placement: ['rail'], when: () => !!shot(), run: level('final') },
  // 04 §2.1: the header's scene menu (the same scene as the shot before is the menu's own entry: it names that shot)
  { id: 'shots.scene.new', scope: 'shots', label: 'New scene', icon: SquarePlus, placement: ['panel'], when: () => useStory.getState().shotVersion()?.state === 'open',
    hint: "a scene and a stage of this shot's own — its place's set when the shot has a place, else an empty stage",
    run: () => void rescene('new').then((ok) => { if (ok) useShots.getState().reopen() }) },
  { id: 'shots.words.toggle', scope: 'shots', label: 'Show the words', icon: Text, placement: ['panel'], when: () => !!shot(),
    hint: "what the shot's pictures are told, part by part, with where each part comes from", run: () => useShots.getState().toggleWords() },
  { id: 'shots.toPerformance', scope: 'shots', label: 'To Performance ▸', icon: Clapperboard, placement: ['panel'], when: () => !!shot(), run: level('performance') },
  { id: 'shots.performOwed', scope: 'shots', label: 'Perform the owed layers ▶', icon: Clapperboard, placement: ['panel'], when: () => !!useShots.getState().owed,
    hint: "the shot's final's plate and every character layer not performed yet, queued in turn (one GPU job at a time)",
    run: () => { const o = useShots.getState().owed; if (!o) return
      void import('../../suites/stage/finalShot').then(async ({ useFinals }) => {
        if (o.plate) await useFinals.getState().plate(o.fid)
        for (const lid of o.figures) await useFinals.getState().perform(o.fid, lid)
      }) } },
  { id: 'shots.toFinal', scope: 'shots', label: 'To Final ▸', icon: MonitorPlay, placement: ['panel'], when: () => !!shot(), run: level('final') },
  // G12 (04 §7): a new shot after the open one
  { id: 'shots.new.scene', scope: 'shots', label: 'New shot in a new scene', icon: SquarePlus, placement: ['strip', 'context'], when: open,
    hint: 'a Shot node after this one, with a scene and a stage of its own — the place\'s set when the shot before has a place',
    run: () => void newShot('new') },
  { id: 'shots.new.same', scope: 'shots', label: 'New shot in the same scene', icon: Plus, placement: ['strip', 'context'],
    when: () => { const v = useStory.getState().shotVersion(); return open() && !!v?.stage_id && !!v.camera_id },
    hint: 'coverage: a new camera on this shot\'s stage, copied from its camera with its keys',
    run: () => void newShot('same') },
])
