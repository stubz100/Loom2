// C0 (D181, propo02 04 §4.3): Clay's commands (rule 3: every action a command with a mouse home; keys are accelerators). They act on the
// Library's open asset (the Story store's selection) and on the scene open in the editor.
import { ArrowLeft, Boxes, Clapperboard, Globe, Hammer, Users } from 'lucide-react'
import { registerCommands } from '../../frame/commands'
import { navigate } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { classOfKind, kindOfClass, useClay } from './clayStore'

const c = () => useClay.getState()
const sy = () => useStory.getState()
const open = () => !!useSession.getState().project?.open

registerCommands([
  { id: 'clay.rail.library', scope: 'clay', label: 'Library', icon: Boxes, placement: ['rail'], when: open,
    hint: 'the 3D assets made from World\'s pictures — figures, props, sets, lights, cameras, animations — each with what it still needs', run: () => c().setRail('library') },
  { id: 'clay.rail.scenes', scope: 'clay', label: 'Scenes', icon: Clapperboard, placement: ['rail'], when: open,
    hint: 'the scenes the shots are cameras on, in the editor', run: () => c().setRail('scenes') },
  // D142 → C0: the bench and the line-up are the Library's own viewer
  { id: 'clay.bench.open', scope: 'clay', label: 'Bench ▶', icon: Hammer, placement: ['panel', 'inspector', 'context'],
    hint: "Clay opened for this asset: its figure (a prop: its model at its height beside a 1.75 m figure; a place: its set from the picture's camera) on a scene of its own, with all of Clay's tools",
    when: () => { const p = sy().profile(); const v = sy().version(); return c().view !== 'bench' && !!p && !!v && (p.cls === 'character' || (p.cls === 'prop' && !!v.model_asset_id) || (p.cls === 'place' && !!v.place_set)) },
    run: () => void c().openBench() },
  { id: 'clay.lineup', scope: 'clay', label: 'Line-up ▶', icon: Users, placement: ['panel', 'context'], hint: "this kind's characters or props side by side at their sizes (twelve at most)",
    when: () => { const cls = classOfKind(c().kind); return c().rail === 'library' && !!cls && cls !== 'place' && sy().profiles.some((p) => p.cls === cls) },
    run: () => void c().openLineup() },
  { id: 'clay.bench.close', scope: 'clay', label: 'Back to the Library', icon: ArrowLeft, placement: ['panel', 'strip'], when: () => c().view === 'bench', run: () => c().closeBench() },
  { id: 'clay.asset.world', scope: 'clay', label: 'Open in World ▸', icon: Globe, placement: ['panel', 'inspector', 'context'], hint: 'its pictures: the sheet, the hero, the references, the A-pose',
    when: () => !!c().asset, run: () => { const a = c().asset; if (!a) return; void import('../world/worldStore').then((m) => { navigate({ suite: 'generate' }); m.useWorld.getState().pick(a.profile, a.version) }) } },
  /** World's readiness items for the 3D (the body, the model, the set) open the Library on the entity. */
  { id: 'clay.asset.open', scope: 'global', label: 'Open in Clay ▸', icon: Hammer, placement: ['panel', 'inspector'], hint: "the entity's 3D in Clay's Library: its body and shell, its model, its set",
    when: () => !!sy().profile(), run: () => { const p = sy().profile(); if (p) c().openLibrary(kindOfClass(p.cls), p.id, sy().versionId ?? p.current) } },
  { id: 'clay.scene.back', scope: 'clay', label: 'Back to the shot', icon: ArrowLeft, placement: ['panel'], when: () => !!c().from, run: () => void c().backToShot() },
])
