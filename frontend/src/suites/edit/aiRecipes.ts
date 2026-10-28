// D90 (02 §9): Edit's AI runs as commands. The AI tab's recipes and its disabled reasons live here, outside the component, so the
// `edit.ai.*` commands (Ctrl+K, the canvas menu's AI ▸, Settings › Keyboard) are enabled exactly when the tab's buttons are and send the
// same recipe. Pure: the caller hands in the panel settings, the capabilities and the document facts (aiCtx in editCommands.ts).
import type { Capabilities, DocumentRecipe } from '../../api/types'
import { byOrder, defaultFirst, heroModel, resolveModel, segmentTool } from '../../store/modelCaps'
import type { AiOp, AiPanelState } from './aiPanelStore'

export interface AiCtx {
  p: AiPanelState
  caps: Capabilities | null | undefined
  /** a model's or tool's health ('missing' when the weights are not fetched or it is unknown) */
  health: (id: string) => string
  doc: { w: number; h: number } | null
  hasSel: boolean
  activeId: string | null
  activeKind: string | null
  aiPrompt: { points: { x: number; y: number; label: 1 | 0 }[]; box: [number, number, number, number] | null }
  /** D45: the Selection panel's Refine edge settings (AI Select's "refine edge") */
  refineParams: () => Record<string, unknown>
}

/** The operations with a run of their own (Select has its own controls); the label of the tab's run button. */
export const AI_OP_LABEL: Record<AiOp, string> = { select: 'Select', inpaint: 'Inpaint', refine: 'Refine', upscale: 'Upscale', outpaint: 'Outpaint', instruct: 'Instruct' }

/** D152: the graphs that take reference images (`ReferenceLatent`): the FLUX.2 family — dev and Klein; the creative families take none. */
const FLUX_FAMILIES = ['flux2', 'klein']
/** C3 (D26) / D65: the models the AI tab offers and resolves — every one from /capabilities (open: Klein 4B, no hero, no SAM 3). */
export function aiModels({ p, caps }: Pick<AiCtx, 'p' | 'caps'>) {
  const capModels = caps?.models
  const contentAware = !!caps?.content_aware?.available                                  // D62: the native extension is installed
  const heroId = heroModel(caps)                                                          // Fill Hero / Outpaint hero (recipes.inpaint_hero)
  const mode = (!heroId && p.mode === 'fill_hero') || (!contentAware && p.mode === 'quick_remove') ? 'fill' : p.mode
  const i2iIds = defaultFirst(byOrder(capModels).filter(([, m]) => m.recipes.i2i).map(([id]) => id), 'i2i', caps)
  const upIds = defaultFirst(byOrder(caps?.tools).filter(([, t]) => t.recipes.upscale_factor != null).map(([id]) => id), 'upscale', caps)
  const refineModel = resolveModel(p.refineModel, 'i2i', (id) => i2iIds.includes(id), caps)
  const tiledIds = i2iIds.filter((id) => capModels?.[id]?.tiled_refine)                 // D89: the creative families refine, they do not tile
  const tiledModel = resolveModel(p.tiledModel, 'i2i', (id) => tiledIds.includes(id), caps)
  const upscaleModel = resolveModel(p.upscaleModel, 'upscale', (id) => upIds.includes(id), caps)
  const kleinId = resolveModel(null, 'inpaint', () => false, caps)                       // the variant's inpaint default
  const isHero = (id: string) => !!capModels?.[id]?.recipes.inpaint_hero
  const heroFor = (op: AiOp) => !!heroId && (op === 'inpaint' ? p.mode === 'fill_hero' : op === 'outpaint' ? p.outpaintHero : op === 'refine' ? isHero(refineModel) : false)
  const outpaintId = heroFor('outpaint') && heroId ? heroId : kleinId
  const teId = (mid: string) => (p.teId && capModels?.[mid]?.te_options?.some((o) => o.id === p.teId) ? p.teId : undefined)   // D31: only where it pairs
  const refsMax = (mid: string) => (FLUX_FAMILIES.includes(capModels?.[mid]?.family ?? '') ? capModels?.[mid]?.max_refs ?? 0 : 0)   // D152: ReferenceLatent is the FLUX.2 family's
  const instructModel = caps?.instruct?.default ?? null                                  // D151: the build's edit-by-instruction model (null: none offered)
  const instructHealth = instructModel ? caps?.instruct?.models?.[instructModel]?.health ?? 'missing' : 'missing'
  return { contentAware, heroId, mode, i2iIds, upIds, refineModel, tiledIds, tiledModel, upscaleModel, kleinId, isHero, heroFor, outpaintId, teId, instructModel, instructHealth, refsMax }
}

/** The candidate count an operation starts with when the tab switches to it (hero models are slow: 2). */
export const opCandidates = (c: Pick<AiCtx, 'p' | 'caps'>, op: AiOp): number => op === 'inpaint' || op === 'outpaint' || op === 'refine' ? (aiModels(c).heroFor(op) ? 2 : 4) : op === 'instruct' ? 2 : 1   // D151: ≈ 32 s a candidate

/** AI Select with the panel's tool and prompt (D63 / D65): the subject matte by default, a prompted tool (text / points / box) where offered. */
export function selectPlan(c: AiCtx) {
  const { p, caps, aiPrompt } = c
  const subjectId = segmentTool('subject', caps), promptId = segmentTool('text', caps)
  const toolId = resolveModel(p.selModel, 'segment', (id) => !!caps?.tools[id]?.recipes.segment?.length, caps) || subjectId || ''
  const toolModes = caps?.tools[toolId]?.recipes.segment ?? []
  const sam = toolModes.some((m) => m !== 'subject')                                      // a prompted tool: text / points / box
  const pos = aiPrompt.points.filter((q) => q.label === 1).length
  const reason = !c.doc ? 'no document' : !toolId ? 'no AI Select model offered' : c.health(toolId) === 'missing' ? `weights missing: fetch ${toolId} in Models`
    : sam && p.selMode === 'text' && !p.selText.trim() ? 'type what to select in find' : sam && p.selMode === 'points' && !pos ? 'click the subject on the canvas (Alt-click excludes)'
    : sam && p.selMode === 'box' && !aiPrompt.box ? 'drag a box on the canvas' : null
  const recipe = (): DocumentRecipe => ({ kind: 'segment', model_id: toolId, mode: sam ? p.selMode : 'subject', text: p.selText, points: aiPrompt.points, box: aiPrompt.box,
    threshold: p.selThreshold, op: p.selOp, expand: p.selExpand, feather: p.selFeather, edge_refine: p.selRefine ? c.refineParams() : null, seeds: [0] }) as DocumentRecipe
  return { subjectId, promptId, toolId, toolModes, sam, reason, recipe }
}

/** "Select subject" (02 §8.1): the subject matte whatever the panel's prompt mode, joined with the panel's combine / expand / feather. */
export function subjectPlan(c: AiCtx) {
  const { p } = c
  const toolId = segmentTool('subject', c.caps) ?? ''
  const reason = !c.doc ? 'no document' : !toolId ? 'no subject matte offered' : c.health(toolId) === 'missing' ? `weights missing: fetch ${toolId} in Models` : null
  const recipe = (): DocumentRecipe => ({ kind: 'segment', model_id: toolId, mode: 'subject', text: '', points: [], box: null,
    threshold: p.selThreshold, op: p.selOp, expand: p.selExpand, feather: p.selFeather, edge_refine: p.selRefine ? c.refineParams() : null, seeds: [0] }) as DocumentRecipe
  return { toolId, reason, recipe }
}

/** Why the operation cannot run now (the tab shows it under its buttons), or null. */
export function aiReason(c: AiCtx, op: AiOp): string | null {
  if (op === 'select') return selectPlan(c).reason
  const { p } = c
  const m = aiModels(c)
  return !c.doc ? 'no document' : op === 'inpaint' && !c.hasSel ? 'select the region to repaint first (M, L, W, Q or AI select)'
    : op === 'refine' && p.refineSource === 'selection' && !c.hasSel ? 'no selection'
    : (op === 'refine' || op === 'upscale') && (op === 'refine' ? p.refineSource : p.upscaleSource) === 'active' && c.activeKind !== 'raster' ? 'the active layer is not a raster layer'
    : op === 'upscale' && !m.upscaleModel ? 'no upscaler offered' : op === 'upscale' && c.health(m.upscaleModel) === 'missing' ? `weights missing: fetch ${m.upscaleModel} in Models`
    : op === 'outpaint' && !Object.values(p.pad).some((v) => v > 0) ? 'set at least one side'
    : op === 'instruct' && !m.instructModel ? 'no edit-by-instruction model in this build'                                              // D151
    : op === 'instruct' && m.instructHealth === 'missing' ? `weights missing: fetch ${m.instructModel} in Models`
    : op === 'instruct' && p.instructSource === 'active' && c.activeKind !== 'raster' ? 'the active layer is not a raster layer'
    : op === 'instruct' && !p.prompt.trim() ? 'say what to change' : null
}

/** The seeds of one run: `candidates` of them, random or counting up from the fixed seed. */
export function aiSeeds(p: AiPanelState, random: () => number = Math.random): number[] {
  const n = Math.max(1, Math.min(4, p.candidates))
  return Array.from({ length: n }, (_, i) => (p.seedMode === 'random' ? Math.floor(random() * 2 ** 31) : p.seed + i))
}

/** The recipe a run sends — the same object the tab's preview plans (D64). */
export function aiRecipe(c: AiCtx, op: AiOp, seeds: number[] = aiSeeds(c.p)): DocumentRecipe {
  if (op === 'select') return selectPlan(c).recipe()
  const { p, activeId } = c
  const m = aiModels(c)
  const base = { seeds, prompt_text: p.prompt }
  const deck = (mid: string) => (m.refsMax(mid) > 0 && p.refs.length ? { refs: p.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })), ref_max_px: p.refMaxPx } : {})   // D152
  const inpaintModel = m.mode === 'fill_hero' && m.heroId ? m.heroId : m.kleinId
  if (op === 'inpaint') return { kind: 'inpaint', mode: m.mode, model_id: m.kleinId, te_id: m.teId(m.kleinId), margin_pct: p.margin, min_size: p.minSize, feather: p.feather, expand: p.expand, blend: p.blend, prompt_mode: p.promptMode, prefill: m.mode === 'remove' && p.prefill && m.contentAware, ...(m.mode === 'remove' || m.mode === 'quick_remove' ? {} : deck(inpaintModel)), ...base } as DocumentRecipe
  if (op === 'outpaint') return { kind: 'inpaint', mode: 'outpaint', model_id: m.outpaintId, te_id: m.teId(m.outpaintId), outpaint: p.pad, feather: p.feather, prompt_mode: p.promptMode, ...deck(m.outpaintId), ...base } as DocumentRecipe
  if (op === 'refine') return { kind: 'i2i', model_id: m.refineModel, te_id: m.teId(m.refineModel), source: p.refineSource, layer_id: activeId, strength: p.strength, margin_pct: p.margin, feather: p.feather, match_colour: p.matchColour, ...deck(m.refineModel), ...base } as DocumentRecipe
  if (op === 'instruct') return { kind: 'instruct', model_id: m.instructModel ?? '', source: p.instructSource, layer_id: activeId, ...base } as DocumentRecipe   // D151
  return { kind: 'upscale', model_id: m.upscaleModel, source: p.upscaleSource, layer_id: activeId, as_layer: p.asLayer, seeds: p.refineTiled ? seeds.slice(0, 1) : [0],
    refine: p.refineTiled, refine_model_id: m.tiledModel, te_id: p.refineTiled ? m.teId(m.tiledModel) : undefined, strength: p.tiledStrength, tile: p.tile, overlap: p.overlap, prompt_text: p.prompt } as DocumentRecipe
}

/** An AI layer's recipe made runnable again with a new seed (Properties › AI recipe › Re-run): the per-run fields are dropped. */
export function rerunRecipe(recipe: Record<string, unknown>, seed: number): DocumentRecipe {
  const r = { ...recipe }
  delete r.seed; delete r.job_id; delete r.batch_id; delete r.region; delete r.document_id
  return { ...r, seeds: [seed] } as unknown as DocumentRecipe
}
