// D71 (ArtCraft P15): one way to reach a suite with an asset and a tool already chosen — the quick-action cards (empty states, the
// Catalogue Inspector's "Start from this image") and the `?tool=` / `?ai=` / `?sel=` deep links. Edit's code is lazy (D69), so its
// stores come through dynamic imports.
import type { AiOp, SelMode } from '../suites/edit/aiPanelStore'
import { TOOL_IDS, type Tool } from '../suites/edit/tools'
import { useSession } from '../store/session'

export interface OpenWith { suite: 'edit' | 'generate' | 'animate'; tool?: Tool; aiOp?: AiOp; selMode?: SelMode; slot?: 'start' | 'end' | 'ref' }

const AI_OPS: AiOp[] = ['select', 'inpaint', 'refine', 'upscale', 'outpaint']
const SEL_MODES: SelMode[] = ['subject', 'text', 'points', 'box']

/** Open `assetId` (or nothing) in a suite with a tool, an AI operation and a slot chosen. An AI operation selects the AI tool and its panel. */
export async function openWith(assetId: string | null, o: OpenWith): Promise<void> {
  const s = useSession.getState()
  if (o.suite === 'edit') {
    const [{ useEditor }, { useAiPanel }, { setRailTab }] = await Promise.all([import('../suites/edit/editorStore'), import('../suites/edit/aiPanelStore'), import('./suiteRegistry')])
    if (assetId) await useEditor.getState().openFromAsset(assetId)
    else s.setSuite('edit')
    const tool = o.tool ?? (o.aiOp ? 'ai' : undefined)
    if (tool) useEditor.getState().setTool(tool)
    if (o.aiOp) { useAiPanel.getState().set({ op: o.aiOp, ...(o.selMode ? { selMode: o.selMode } : {}) }); setRailTab('edit', 'ai') }
  } else if (o.suite === 'animate') {
    const { useAnimate } = await import('../suites/animate/animateStore')
    const a = useAnimate.getState()
    if (assetId && o.slot === 'end') a.setEnd(assetId, true)
    else if (assetId) a.setStart(assetId, true)
    else s.setSuite('animate')
  } else {
    const { useGenerate } = await import('../suites/generate/generateStore')
    if (assetId) useGenerate.getState().addRef(assetId)
    else s.setSuite('generate')
  }
}

/** `?suite=edit&tool=ai&ai=select&sel=subject` (optionally `&asset=<id>`): what `openWith` should do for a deep link, or null. */
export function deepLinkOf(q: URLSearchParams): { assetId: string | null; o: OpenWith } | null {
  const tool = q.get('tool'), ai = q.get('ai'), sel = q.get('sel')
  if (q.get('suite') !== 'edit' || (!tool && !ai)) return null
  const o: OpenWith = { suite: 'edit' }
  if (tool && (TOOL_IDS as readonly string[]).includes(tool)) o.tool = tool as Tool
  if (ai && (AI_OPS as string[]).includes(ai)) o.aiOp = ai as AiOp
  if (sel && (SEL_MODES as string[]).includes(sel)) o.selMode = sel as SelMode
  return o.tool || o.aiOp ? { assetId: q.get('asset'), o } : null
}
