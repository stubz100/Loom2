// The AI panel's settings (10 §4): one small store shared by the AI tab and the A-tool options so both views edit
// the same values; it is UI state only (not persisted) — recipes carry everything that matters into the manifest.
import { create } from 'zustand'

export type AiOp = 'select' | 'inpaint' | 'refine' | 'upscale' | 'outpaint'
export type SelMode = 'subject' | 'text' | 'points' | 'box'
export type SelOp = 'replace' | 'add' | 'subtract' | 'intersect'

export interface AiPanelState {
  op: AiOp; mode: 'fill' | 'fill_match' | 'fill_hero' | 'remove' | 'quick_remove'; prompt: string; candidates: number; seedMode: 'random' | 'fixed'; seed: number
  margin: number; minSize: number; feather: number; expand: number; promptMode: 'image_first' | 'prompt_first'
  refineModel: string; strength: number; refineSource: 'visible' | 'active' | 'selection'
  upscaleModel: string; upscaleSource: 'visible' | 'active'; asLayer: boolean
  refineTiled: boolean; tiledModel: string; tiledStrength: number; tile: number; overlap: number
  pad: { left: number; top: number; right: number; bottom: number }; outpaintHero: boolean
  teId: string | null                        // D31: text encoder behind the Klein 9B recipes (null = the preset's Q4_K_M GGUF; 'qwen3-8b-fp8mixed' = fp8)
  // AI Select (M5 slice 2): BiRefNet subject matte or SAM 3 text / points / box, joined with the selection
  selModel: 'birefnet' | 'sam3'; selMode: SelMode; selText: string; selThreshold: number; selOp: SelOp; selExpand: number; selFeather: number
  selRefine: boolean                         // D45: run Refine Edge (the Selection panel's settings) on the result
  blend: 'feather' | 'seamless'              // D47: paste-back — feather only, or Poisson-cloned onto the plate inside the feather
  matchColour: boolean                       // D48 (Refine): map the result's colour statistics onto the original's
  prefill: boolean                           // D62 (Remove): the hole content-aware filled before the engine sees it
}

export const AI_DEFAULT: AiPanelState = {
  op: 'inpaint', mode: 'fill', prompt: '', candidates: 4, seedMode: 'random', seed: 1, margin: 25, minSize: 1024, feather: 8, expand: 0, promptMode: 'image_first',
  refineModel: 'klein-base-9b', strength: 0.3, refineSource: 'visible', upscaleModel: 'realesrgan-x2', upscaleSource: 'visible', asLayer: true,
  refineTiled: false, tiledModel: 'klein-base-9b', tiledStrength: 0.25, tile: 1024, overlap: 128,
  pad: { left: 0, top: 0, right: 256, bottom: 0 }, outpaintHero: false, teId: null,
  selModel: 'birefnet', selMode: 'subject', selText: '', selThreshold: 0.5, selOp: 'replace', selExpand: 0, selFeather: 2, selRefine: false, blend: 'feather', matchColour: false, prefill: false,
}

export const useAiPanel = create<AiPanelState & { set: (p: Partial<AiPanelState>) => void }>()((set) => ({ ...AI_DEFAULT, set: (p) => set(p) }))
if (import.meta.env.DEV) (globalThis as unknown as { __loom2AiPanel?: unknown }).__loom2AiPanel = useAiPanel   // read by edit_headed_check.py kit (D63)
