// B1 (D159, proto01_UI2 11 §3): the Bin's verbs of where you are — D95's, moved out of the Catalogue's drawer. In the Dock's drawer a tile's
// double-click does the likely one for the place the author is in (a reference in Make, a layer in Edit, the start frame in Performance,
// an image plane or a set on Clay's stage), its right-click lists them all, then a picture's World verbs and the Bin's own. A pick started
// from a panel (session.ui.pick: "Add image plane…") names one of them: the tiles that have it show its corner button.
import type { Asset } from '../../api/types'
import type { MenuItem } from '../../frame/commands'
import { editPresence } from '../../frame/editPresence'
import { navigate } from '../../frame/router'
import { askText, useSession } from '../../store/session'
import { addToCastMenu, madeFor } from '../../suites/story/addToCast'
import { castPropMenu } from '../../suites/story/castProp'
import { madeForIdea, prototypeMenu } from '../../suites/story/prototype'
import { profilesForMentions } from '../../suites/story/storyStore'

/** A verb of where you are: a menu entry that is also the double-click; a pick names one by `id` (session.ui.pick). */
export interface Verb { id: string; label: string; run: () => void }

const openInEdit = (id: string) => void import('../world/editAnywhere').then((m) => m.editAnywhere(id))   // B2a: in World's Edit, saved beside it when it is no entity's
const addLayer = (id: string) => void import('../../suites/edit/editorStore').then((m) => m.useEditor.getState().addLayerFromAsset(id))
const asReference = (id: string) => void import('../../suites/generate/generateStore').then((m) => m.useGenerate.getState().addRef(id))
const asStart = (id: string) => void import('../../suites/animate/animateStore').then((m) => m.useAnimate.getState().setStart(id, true))
const asEnd = (id: string) => void import('../../suites/animate/animateStore').then((m) => m.useAnimate.getState().setEnd(id, true))
const playClip = (a: Asset) => void import('../../suites/animate/animateStore').then(async (m) => {
  const clip = (a.params as { clip_id?: string } | undefined)?.clip_id
  const an = m.useAnimate.getState()
  navigate({ suite: 'animate' })
  if (clip) { await an.loadClips(); an.select(clip) }
})

/** An image plane, a set from a picture or a 3D model on the open stage, at the viewport's centre (Clay). */
function onStage(kind: 'plane' | 'set' | 'mesh', id: string): void {
  void Promise.all([import('../../suites/stage/stageStore'), import('../../suites/stage/stageCommands')]).then(([s, c]) => {
    if (kind === 'set') { void s.st().setFromImage(id); return }                              // SC3 (D120): MoGe's relief with the picture's camera
    if (!s.st().addObject(kind, null, c.viewport.centre?.() ?? [0, 0, 0], id)) useSession.getState().toast('Open a shot in Clay first', 'info')
  })
}

/** The verbs of a tile for the place the author is in (the session's suite), the likely one first. A trashed thing has none here: its
 *  verbs are the Bin's (Restore, Delete permanently…). */
export function verbsHere(a: Asset, suite: string): Verb[] {
  if (a.trashed_at) return []
  if (a.kind === 'video') return [{ id: 'play', label: 'Play in Performance', run: () => playClip(a) }]
  if (a.kind === 'mesh') return suite === 'stage' ? [{ id: 'stage.mesh', label: 'Add to the stage (a 3D model)', run: () => onStage('mesh', a.id) }] : []
  if (a.kind !== 'image') return []
  const layer: Verb[] = suite === 'edit' && editPresence.hasDoc ? [{ id: 'edit.layer', label: 'Add as a layer', run: () => addLayer(a.id) }] : []
  const stage: Verb[] = suite === 'stage' ? [{ id: 'stage.plane', label: 'Add to the stage (image plane)', run: () => onStage('plane', a.id) },
    { id: 'stage.set', label: 'Add to the stage (a set from this image)', run: () => onStage('set', a.id) }] : []
  const rest: Verb[] = [{ id: 'reference', label: 'Use as a reference (Make)', run: () => asReference(a.id) }, { id: 'edit.open', label: 'Open in Edit', run: () => openInEdit(a.id) },
    { id: 'start', label: 'Set as the start frame (Performance)', run: () => asStart(a.id) }, { id: 'end', label: 'Use as the end frame (Performance)', run: () => asEnd(a.id) }]
  const first = suite === 'animate' || suite === 'stage' ? rest[2] : suite === 'generate' ? rest[0] : null
  return [...layer, ...stage, ...(first ? [first] : []), ...rest.filter((x) => x !== first)]
}

/** A picture becomes the hero of a new World entity, which World then opens (D157: World holds Characters · Props · Places). */
export function makeEntity(cls: 'character' | 'place' | 'prop', assetId: string): void {
  void askText({ title: `Make a ${cls} from this picture`, text: 'The picture becomes its hero, in its version\'s bin.', placeholder: `${cls} name` })
    .then(async (name) => {
      if (!name?.trim()) return
      const m = await import('../../suites/story/storyStore')
      const p = await m.useStory.getState().createProfile(name.trim(), cls, assetId)
      if (!p) return
      navigate({ suite: 'generate' })
      void import('../world/worldStore').then((w) => w.useWorld.getState().pick(p.id))
    })
}

/** A picture's World verbs (CW1's Prototype ▸, A2's Add to ‹entity› ▸, a new entity from it), a 3D model's prop verb. */
export function worldItems(a: Asset): MenuItem[] {
  if (a.trashed_at) return []
  if (a.kind === 'mesh') return [castPropMenu(a)]
  if (a.kind !== 'image') return []
  return [prototypeMenu([a.id], madeForIdea(a)), addToCastMenu(profilesForMentions(), madeFor(a), [a.id], 'bin'),
    { label: 'Make an entity from it', items: (['character', 'place', 'prop'] as const).map((cls): MenuItem => ({ label: `Make a ${cls}…`, run: () => makeEntity(cls, a.id) })) }]
}
