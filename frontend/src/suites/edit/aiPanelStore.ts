// The AI panel's settings (10 §4): one small store shared by the AI tab and the A-tool options so both views edit
// the same values; it is UI state only — recipes carry everything that matters into the manifest. D95 (IM1, UX0 #22): the operation last
// chosen is remembered in this browser (a per-viewer convenience; nothing breaks without it).
import { create } from 'zustand'
import { DEV_HOOKS } from '../../devHooks'

export type AiOp = 'select' | 'inpaint' | 'refine' | 'upscale' | 'outpaint' | 'instruct'
export type SelMode = 'subject' | 'text' | 'points' | 'box'
export type SelOp = 'replace' | 'add' | 'subtract' | 'intersect'
/** D152: a reference image in the AI tab's deck (Generate's shape: a Catalogue asset and what it shows). */
export interface AiRef { asset_id: string; note?: string }

export interface AiPanelState {
  op: AiOp; mode: 'fill' | 'fill_match' | 'fill_hero' | 'remove' | 'quick_remove'; prompt: string; candidates: number; seedMode: 'random' | 'fixed'; seed: number
  margin: number; minSize: number; feather: number; expand: number; promptMode: 'image_first' | 'prompt_first'
  refineModel: string; strength: number; refineSource: 'visible' | 'active' | 'selection'
  upscaleModel: string; upscaleSource: 'visible' | 'active'; asLayer: boolean
  refineTiled: boolean; tiledModel: string; tiledStrength: number; tile: number; overlap: number
  pad: { left: number; top: number; right: number; bottom: number }; outpaintHero: boolean
  teId: string | null                        // D31: text encoder behind the recipes (null = the model's default; else one of its te_options)
  // AI Select (M5 slice 2): a subject matte tool or a prompted one (text / points / box), joined with the selection.
  // D65: model ids come from /capabilities — '' (or null) means the recipe kind's default for this variant, resolved when used.
  selModel: string | null; selMode: SelMode; selText: string; selThreshold: number; selOp: SelOp; selExpand: number; selFeather: number
  selRefine: boolean                         // D45: run Refine Edge (the Selection panel's settings) on the result
  blend: 'feather' | 'seamless'              // D47: paste-back — feather only, or Poisson-cloned onto the plate inside the feather
  matchColour: boolean                       // D48 (Refine): map the result's colour statistics onto the original's
  prefill: boolean                           // D62 (Remove): the hole content-aware filled before the engine sees it
  instructSource: 'visible' | 'active'       // D151 (Instruct): the whole picture, or the active layer alone
  refs: AiRef[]                              // D152: the reference deck — sent with inpaint / outpaint / refine where the model takes references
  refMaxPx: number                           // D152: references are downscaled to fit this square before upload
}

export const AI_DEFAULT: AiPanelState = {
  op: 'inpaint', mode: 'fill', prompt: '', candidates: 4, seedMode: 'random', seed: 1, margin: 25, minSize: 1024, feather: 8, expand: 0, promptMode: 'image_first',
  refineModel: '', strength: 0.3, refineSource: 'visible', upscaleModel: '', upscaleSource: 'visible', asLayer: true,
  refineTiled: false, tiledModel: '', tiledStrength: 0.25, tile: 1024, overlap: 128,
  pad: { left: 0, top: 0, right: 256, bottom: 0 }, outpaintHero: false, teId: null,
  selModel: null, selMode: 'subject', selText: '', selThreshold: 0.5, selOp: 'replace', selExpand: 0, selFeather: 2, selRefine: false, blend: 'feather', matchColour: false, prefill: false, instructSource: 'visible', refs: [], refMaxPx: 1024,
}

const OP_KEY = 'loom2.edit.aiOp'
const OPS: AiOp[] = ['select', 'inpaint', 'refine', 'upscale', 'outpaint', 'instruct']
function lastOp(): AiOp {
  try { const v = localStorage.getItem(OP_KEY) as AiOp | null; return v && OPS.includes(v) ? v : AI_DEFAULT.op } catch { return AI_DEFAULT.op }
}

/** D152: the deck's verbs (Generate's: add in order, remove, move, clear). */
export interface AiRefVerbs { addRefs: (assetIds: string[]) => void; removeRef: (assetId: string) => void; moveRef: (from: number, to: number) => void; clearRefs: () => void; setRefNote: (assetId: string, note: string) => void }
export const useAiPanel = create<AiPanelState & AiRefVerbs & { set: (p: Partial<AiPanelState>) => void }>()((set, get) => ({
  ...AI_DEFAULT, op: lastOp(),
  set: (p) => { if (p.op) { try { localStorage.setItem(OP_KEY, p.op) } catch { /* private window: not remembered */ } } set(p) },
  addRefs: (ids) => { const have = new Set(get().refs.map((r) => r.asset_id)); const fresh = [...new Set(ids)].filter((id) => !have.has(id)); if (fresh.length) set({ refs: [...get().refs, ...fresh.map((asset_id) => ({ asset_id }))] }) },
  removeRef: (id) => set({ refs: get().refs.filter((r) => r.asset_id !== id) }),
  moveRef: (from, to) => { const refs = [...get().refs]; if (from < 0 || from >= refs.length || to < 0 || to >= refs.length) return; const [x] = refs.splice(from, 1); refs.splice(to, 0, x); set({ refs }) },
  clearRefs: () => set({ refs: [] }),
  setRefNote: (id, note) => set({ refs: get().refs.map((r) => (r.asset_id === id ? { ...r, note: note || undefined } : r)) }),
}))
if (DEV_HOOKS) (globalThis as unknown as { __loom2AiPanel?: unknown }).__loom2AiPanel = useAiPanel   // read by edit_headed_check.py kit (D63)
