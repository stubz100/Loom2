// RS2 (D197 G2, proto02 02 PG22): a reference framing switched on in Make — the one way a reference picture is made. The server's sentence
// for the side becomes the framing words, the frame the side's (D177: an A-pose a 2:3 portrait; a hand or feet picture 1024²), and a part's
// model Klein (RG1, E62 a) — every one of them a field of Make's column the author sees and may change before the run. Nothing is queued.
// The buttons that made a reference with settings of their own (two pictures, 16:9, Draft) are gone; their commands turn the framing on.
import { useSession } from '../../store/session'
import { useGenerate } from '../../suites/generate/generateStore'
import type { ProfileClass } from '../../suites/story/storyStore'
import { partOf, REF_FRAMINGS, refFrame, refTree, type RefFraming } from './make'

export type RefSide = RefFraming['side']

/** Make's panel on the class's reference framing for `side`; false when the build has no sentence for it. */
export function frameReference(cls: ProfileClass, side: RefSide): boolean {
  const g = useGenerate.getState(), panel = g.panel
  const refs = useSession.getState().capabilities?.story?.references
  const f = REF_FRAMINGS[cls].find((x) => x.side === side)
  const sentence = refs?.[cls]?.[side]
  if (!f || !sentence) return false
  g.set({ ref_framing: f.id, ...(panel.prompt_mode === 'tree' ? {} : { prompt_mode: 'tree' as const }) })
  g.setTree(refTree(cls, sentence, panel.tree.camera, f.side))
  const [w, h] = refFrame(cls, panel.width, panel.height, f.side)
  if (w !== panel.width || h !== panel.height) g.set({ width: w, height: h, tier: 'custom' })
  const klein = useSession.getState().capabilities?.story?.model_id                 // RG1 (E62 a): Klein draws the clean close-up; the card may change it
  if (partOf(f.id) && klein && panel.model_id !== klein) g.setModel(klein)
  return true
}
