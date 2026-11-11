// C0 (D181, propo02 04 §4.3): Clay's commands (rule 3: every action a command with a mouse home; keys are accelerators). They act on the
// Library's animations and on the scene open in the editor. RS1 (D197): an entity's 3D, its bench and the line-up are World's Clay mode
// (world.mode.clay, world.clay.*, world.lineup) — *Open in Clay ▸* and *Open in World ▸* are gone (one home per thing).
import { ArrowLeft, Clapperboard, Copy, FilePlus, Film, Hammer, Library, Pencil, Save, SaveAll, Trash2 } from 'lucide-react'
import { askConfirm, askText } from '../../store/session'
import { registerCommands } from '../../frame/commands'
import { useSession } from '../../store/session'
import { useClay } from './clayStore'

const c = () => useClay.getState()
const open = () => !!useSession.getState().project?.open

registerCommands([
  { id: 'clay.rail.library', scope: 'clay', label: 'Animations', icon: Film, placement: ['rail'], when: open,
    hint: "the animation workshop: your animations, the project's and the downloaded clips — opened on the bench, edited, saved", run: () => c().setRail('library') },
  { id: 'clay.rail.scenes', scope: 'clay', label: 'Scenes', icon: Clapperboard, placement: ['rail'], when: open,
    hint: 'the scenes the shots are cameras on, in the editor', run: () => c().setRail('scenes') },
  { id: 'clay.scene.back', scope: 'clay', label: 'Back to the shot', icon: ArrowLeft, placement: ['panel'], when: () => !!c().from, run: () => void c().backToShot() },
  // D182 (C2b): the animation workshop — the tiles' verbs act on the animation under the right-click (animSel); the bench's on the one open
  { id: 'clay.anim.new', scope: 'clay', label: 'New animation…', icon: FilePlus, placement: ['panel', 'context'], hint: 'a figure standing still over a few seconds, on the bench: pose it at the frames you want, then Save',
    when: () => c().rail === 'library' && c().view === 'page',
    run: () => void import('../../suites/stage/animationBench').then(async (m) => { const a = await m.askNewAnimation(); if (!a) return; const t = await m.newAnimation(a.name, a.seconds); if (t) void c().openAnimation({ kind: 'template', id: t.id }) }) },
  { id: 'clay.anim.open', scope: 'clay', label: 'Open on the bench', icon: Hammer, placement: ['context'], hint: 'a figure plays it as its one clip; edit it there and Save',
    when: () => !!c().animSel && c().view === 'page', run: () => { const r = c().animSel; if (r) void c().openAnimation(r) } },
  { id: 'clay.anim.save', scope: 'clay', label: 'Save', icon: Save, placement: ['panel'], hint: "the bench's track — the clip, its corrections and keys over the range — written over the animation",
    when: () => c().view === 'animation' && c().animation?.kind === 'template', run: () => void import('../../suites/stage/animationBench').then((m) => m.saveAnimationOver()) },
  { id: 'clay.anim.saveAs', scope: 'clay', label: 'Save as…', icon: SaveAll, placement: ['panel'], hint: "a new animation of the project's from the bench's track",
    when: () => c().view === 'animation', run: () => void askText({ title: 'Save as a new animation', placeholder: 'its name' }).then(async (name) => { if (!name?.trim()) return
      const m = await import('../../suites/stage/animationBench'); const t = await m.saveAnimationAs(name.trim()); if (t) useClay.setState({ animation: { kind: 'template', id: t.id }, animSel: { kind: 'template', id: t.id } }) }) },
  { id: 'clay.anim.mine', scope: 'clay', label: 'Make it mine', icon: Library, placement: ['panel', 'context'], hint: "a copy of this downloaded clip as an animation of your own (its file and licence kept) — edit it and Save",
    when: () => (c().view === 'animation' ? c().animation?.kind === 'clip' : c().animSel?.kind === 'clip'),
    run: () => void import('../../suites/stage/animationBench').then(async (m) => {
      if (c().view !== 'animation') { const r = c().animSel; if (r) await c().openAnimation(r) }
      const t = await m.makeMine(); if (t) useClay.setState({ animation: { kind: 'template', id: t.id }, animSel: { kind: 'template', id: t.id } }) }) },
  { id: 'clay.anim.back', scope: 'clay', label: 'Back to the Library', icon: ArrowLeft, placement: ['panel', 'strip'], when: () => c().view === 'animation', run: () => c().closeAnimation() },
  { id: 'clay.anim.rename', scope: 'clay', label: 'Rename…', icon: Pencil, placement: ['context', 'inspector'], when: () => c().animSel?.kind === 'template',
    run: () => { const r = c().animSel; if (!r || r.kind !== 'template') return
      void import('../../suites/stage/animationBench').then(async (m) => { const name = await askText({ title: 'Rename the animation', initial: await m.nameOf(r) }); if (name?.trim()) await m.renameAnimation(r, name.trim()) }) } },
  { id: 'clay.anim.duplicate', scope: 'clay', label: 'Duplicate', icon: Copy, placement: ['context', 'inspector'], hint: "a copy of the project's, named after it", when: () => c().animSel?.kind === 'template',
    run: () => { const r = c().animSel; if (r) void import('../../suites/stage/animationBench').then((m) => m.duplicateAnimation(r)) } },
  { id: 'clay.anim.toLibrary', scope: 'clay', label: 'To my library', icon: Library, placement: ['context', 'inspector'], hint: 'every project has it under Mine',
    when: () => c().animSel?.kind === 'template' && !!clayLib().items.some((x) => x.id === (c().animSel as { id: string }).id) && !clayLib().library.some((x) => x.id === (c().animSel as { id: string }).id),
    run: () => { const r = c().animSel; if (r) void import('../../suites/stage/animationBench').then((m) => m.animationToLibrary(r)) } },
  { id: 'clay.anim.remove', scope: 'clay', label: 'Remove', icon: Trash2, placement: ['context', 'inspector'], danger: true, when: () => c().animSel?.kind === 'template',
    run: () => { const r = c().animSel; if (!r) return
      void import('../../suites/stage/animationBench').then(async (m) => { const ok = await askConfirm({ title: `Remove ${await m.nameOf(r)}?`, okLabel: 'Remove', danger: true, text: 'From the project, or from your library — the scenes that play it keep their clips.' })
        if (ok) { await m.removeAnimation(r); if (JSON.stringify(c().animation) === JSON.stringify(r)) c().closeAnimation(); c().selectAnimation(null) } }) } },
])

/** The templates as loaded (the commands' `when` reads them; no hook). */
function clayLib(): { items: { id: string }[]; library: { id: string }[] } {
  return templatesState()
}
let templatesState: () => { items: { id: string }[]; library: { id: string }[] } = () => ({ items: [], library: [] })
void import('../../suites/stage/blockEdit').then((m) => { templatesState = () => m.useTemplates.getState() })
