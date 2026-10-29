// Generate suite state (09): the Panel (prompt tree / JSON / text, model, sampling, size, batch, references,
// presets), the live preview from /recipes/preview, and the verbs other suites call (reference, re-run, variations).
import { create } from 'zustand'
import { DEV_HOOKS } from '../../devHooks'
import { persist } from 'zustand/middleware'
import { ApiError, http, unwrap } from '../../api/client'
import { isDocumentPreview, isT2IPreview, type Asset, type Capabilities, type DocumentPreview, type Job, type JobOrigin, type T2IPreview, type T2IRecipe } from '../../api/types'
import type { components } from '../../api/schema'
import { defaultModel, resolveModel } from '../../store/modelCaps'
import type { DragPayload } from '../../frame/drag'
import { runCommand, type OnItem } from '../../frame/commands'
import { refDrop } from '../../frame/dropRules'
import { FOR_SHOT, forLabel, originFor, useMakeFor, withIdea } from '../../store/origin'
import { askConfirm, useSession } from '../../store/session'
import { profilesForMentions as profilesNow, styleFor } from '../story/storyStore'
import type { Profile } from '../../api/types'
import { castOrigin, keptSubject, needsLook, sentIndex } from './subjectCast'
import { adoptDescription, composeSheet, versionOf } from './sheet'
import { navigate } from '../../frame/router'
import { contextSlot } from '../../store/contexts'

/** A subject card of the Tree prompt. D92: `profile_id` links it to a Cast character or prop — its version's reference set and LoRA ride on
 *  the profile mention the link records (never sent in the prompt itself). D93 (B4): a linked card has no words of its own — the server
 *  composes its description from the version's sheet (`version`: the chip's pick, else the current one, B5) and this shot's override
 *  (`shot_outfit`, `shot_note`); `description` is a free card's. */
export interface Subject { description: string; position?: string; action?: string; pose?: string; color_match?: string; profile_id?: string; version?: string; shot_outfit?: string; shot_note?: string; holds?: HeldProp }
/** D93 (C6): a Cast prop a subject card holds — "holding <its clause>", its references bound to the subject (the server composes both). */
export interface HeldProp { profile_id: string }
/** D93 (C6): the Tree's scene linked to a Cast place — its sheet (at the chip's version) + this shot's line is the scene, composed by the server. */
export interface SceneLink { profile_id: string; version?: string; note?: string }
/** D93 (B4): the card fields that ride on the mention, never in the prompt's subject object. */
const LINK_KEYS = new Set(['profile_id', 'version', 'shot_outfit', 'shot_note', 'holds'])
export interface Camera { angle?: string; lens?: string; depth_of_field?: string; 'f-number'?: string; distance?: string }
export interface Tree { scene?: string; scene_link?: SceneLink; subjects?: Subject[]; style?: string; color_palette?: string[]; lighting?: string; mood?: string; background?: string; composition?: string; camera?: Camera }
export type PromptMode = 'tree' | 'json' | 'text'
export type SeedMode = 'random' | 'fixed' | 'increment'
export interface RefSlot { asset_id: string; note?: string }
/** D73: an @mention of an album group — the server turns it into references (the cover first, then page order) when the panel previews or
 *  submits, and stamps the group's revision into the recipe. */
export interface MentionRef { group_id: string; name: string; profile_id?: string }
/** LT1 (18 §3e): one entry of the LoRA slots' picker, as GET /loras lists it for the panel's model. */
export type LoraOption = components['schemas']['LoraOption']   // D85: a Story profile (the server swaps its current version's group in)

export interface Panel {
  prompt_mode: PromptMode; tree: Tree; json_text: string; text: string; negative: string
  model_id: string; steps: number | null; guidance: number | null; cfg: number | null; sampler: string | null; scheduler: string | null; turbo: boolean
  // ComfyUI configuration surfaced 2026-10-06 (null = the model preset's value; see /capabilities)
  turbo_strength: number; weight_dtype: string | null; te_device: string | null; te_id: string | null; base_shift: number | null; max_shift: number | null; tiled_vae: boolean; tile_size: number
  seed_mode: SeedMode; seed: number; count: number
  width: number; height: number; tier: 'thumb' | 'draft' | 'full' | 'custom'
  refs: RefSlot[]; ref_max_px: number
  mentions?: MentionRef[]
  loras: { model_id: string; strength: number }[]
  auto_lora: boolean                                        // LT3 (18 §3f): a profile mention adds its version's LoRA + trigger; off = this prompt without
  style_id?: string | null                                  // D85: a Story style id; null = none; absent = the world's default style
}

/** Every prompt string of the panel (the Text field, the tree's fields, the JSON text) — where an @mention can be written. */
function promptStrings(p: Panel): string[] {
  const out: string[] = [p.text]
  const walk = (v: unknown) => { if (typeof v === 'string') out.push(v); else if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v === 'object') Object.values(v).forEach(walk) }
  if (p.prompt_mode === 'tree') walk(p.tree)
  if (p.prompt_mode === 'json') out.push(p.json_text)
  return out
}
/** D92: the Tree subject card linked to a profile (its index), or -1. */
export const linkedSubject = (p: Panel, profileId: string | undefined): number => (profileId && p.prompt_mode === 'tree' ? (p.tree.subjects ?? []).findIndex((s) => s.profile_id === profileId) : -1)
/** D93 (C6): the subject card holding a prop (its index), or -1. */
export const holderOf = (p: Panel, profileId: string | undefined): number => (profileId && p.prompt_mode === 'tree' ? (p.tree.subjects ?? []).findIndex((s) => s.holds?.profile_id === profileId) : -1)
/** D93 (C6): the place linked to the Tree's scene is this profile. */
export const sceneOf = (p: Panel, profileId: string | undefined): boolean => !!profileId && p.prompt_mode === 'tree' && p.tree.scene_link?.profile_id === profileId
/** A profile the Tree links somewhere (a subject card, a held prop, the scene). */
const linkedAnywhere = (p: Panel, profileId: string | undefined): boolean => linkedSubject(p, profileId) >= 0 || holderOf(p, profileId) >= 0 || sceneOf(p, profileId)
/** D73: the mentions still written somewhere in the prompt as `@name` (deleting the text drops the mention); D92: and the profile mentions a
 *  Tree subject card is linked to; D93 (C6): a held prop's and the scene's place. */
export function mentionsInUse(p: Panel): MentionRef[] {
  const text = promptStrings(p).join('\n')
  return (p.mentions ?? []).filter((m) => text.includes('@' + m.name) || linkedAnywhere(p, m.profile_id))
}
/** The panel's mentions without the profile mentions nothing links or writes any more (after a link changed). */
function pruned(p: Panel): MentionRef[] {
  const text = promptStrings(p).join('\n')
  return (p.mentions ?? []).filter((m) => !m.profile_id || linkedAnywhere(p, m.profile_id) || text.includes('@' + m.name))
}
const unmention = (s: string, name: string) => s.split('@' + name).join(name)

export type Preview = T2IPreview                          // D38: the server's t2i preview reply
/** A saved panel (09 §3e). D92: its picture is its most recent result (`thumb_asset_id`, kept by the server). */
export interface Preset { name: string; panel: Panel; saved_at: string; thumb_asset_id?: string | null }

/** A fresh subject card; subjects are optional — none by default (2026-10-06). */
export const NEW_SUBJECT: Subject = { description: '', position: '', action: '', pose: '', color_match: 'exact' }
const EMPTY_TREE: Tree = { scene: '', subjects: [], style: '', color_palette: [], lighting: '', mood: '', background: '', composition: '', camera: { angle: '', lens: '', depth_of_field: '', 'f-number': '', distance: '' } }
export const DEFAULT_PANEL: Panel = {
  prompt_mode: 'tree', tree: EMPTY_TREE, json_text: '', text: '', negative: '',
  model_id: '', steps: null, guidance: null, cfg: null, sampler: null, scheduler: null, turbo: true,
  turbo_strength: 1, weight_dtype: null, te_device: null, te_id: null, base_shift: null, max_shift: null, tiled_vae: false, tile_size: 512,
  seed_mode: 'random', seed: 1, count: 4, width: 960, height: 544, tier: 'draft', refs: [], ref_max_px: 1024, loras: [], auto_lora: true,
}

/** Drop empty leaves so the JSON sent is compact (04 §3c). */
export function cleanTree(t: Tree): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(t)) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v)) {
      if (k === 'subjects') {
        const subs = (v as Subject[]).filter(keptSubject).map((s) => Object.fromEntries(Object.entries(s).filter(([k, x]) => !LINK_KEYS.has(k) && !(k === 'description' && s.profile_id) && x !== '' && x != null)))   // D92: the link is the mention's, not the prompt's; D93 (B4): a linked card's words are the server's to compose
        if (subs.length) out[k] = subs
      } else if (v.length) out[k] = v
    } else if (k === 'scene_link' || (k === 'scene' && t.scene_link?.profile_id)) {
      continue                                                                           // D93 (C6): the place's link rides on its mention; its scene is the server's
    } else if (typeof v === 'object') {
      const o = Object.fromEntries(Object.entries(v as Record<string, string>).filter(([, x]) => x !== '' && x != null))
      if (Object.keys(o).length) out[k] = o
    } else out[k] = v
  }
  return out
}

/** Known fields back into the tree form; unknown keys are kept in `extra` (lossless for schema fields). */
export function treeFromJson(j: Record<string, unknown>): Tree {
  const t: Tree = { ...EMPTY_TREE, subjects: [] }
  const str = (x: unknown) => (typeof x === 'string' ? x : x == null ? '' : JSON.stringify(x))
  for (const k of ['scene', 'style', 'lighting', 'mood', 'background', 'composition'] as const) if (k in j) t[k] = str(j[k])
  if (Array.isArray(j.subjects)) t.subjects = (j.subjects as Record<string, unknown>[]).map((s) => ({ description: str(s.description), position: str(s.position), action: str(s.action), pose: str(s.pose), color_match: str(s.color_match ?? 'exact') }))
  if (Array.isArray(j.color_palette)) t.color_palette = (j.color_palette as unknown[]).map(str)
  if (j.camera && typeof j.camera === 'object') { const c = j.camera as Record<string, unknown>; t.camera = { angle: str(c.angle), lens: str(c.lens), depth_of_field: str(c.depth_of_field), 'f-number': str(c['f-number']), distance: str(c.distance) } }
  return t
}

/** D65: the panel's model, or the variant's t2i default while the panel holds none ('' before the capabilities arrived). */
export function panelModel(p: Panel): string {
  return resolveModel(p.model_id, 't2i', (id) => !!useSession.getState().capabilities?.models[id])
}

export type ModelCap = Capabilities['models'][string]
/** D90 (B12): the model honours a negative prompt — the server's `negative_used` rule (distilled variants run at CFG 1 and drop it). */
export const honoursNegative = (cap: ModelCap | undefined): boolean => !cap?.distilled
/** D90 (B12): the panel model's reference limit (`max_refs`; 0 = it takes none). */
export const maxRefsOf = (p: Panel): number => useSession.getState().capabilities?.models[panelModel(p)]?.max_refs ?? 4

/** D90 (B12): what picking a model changes besides the id — Turbo only where the model has it, the tier's size for the new model's family
 *  (a custom size stays), and no base / max shift where the graph has no ModelSamplingFlux (the compiler refuses one). */
/** V70 (T8): a panel naming a model this build does not offer (a retired model's preset or asset) used to be *sent* resolved to the
 *  default while the column *read* it unresolved — the job ran on the default, the grid showed no card, the refs and size read the
 *  wrong family. The panel takes the resolved model (with its tier size), and a toast says so. */
function settleModel(get: () => GenerateState, set: (p: Partial<GenerateState>) => void): void {
  const caps = useSession.getState().capabilities
  const p = get().panel
  if (!caps || !p.model_id || caps.models[p.model_id]) return
  const id = panelModel(p)
  if (!id || id === p.model_id) return
  set({ panel: { ...p, ...modelPatch(p, id) } })
  useSession.getState().toast(`${p.model_id} is not in this build — ${id} runs`, 'info')
}

export function modelPatch(p: Panel, id: string): Partial<Panel> {
  const caps = useSession.getState().capabilities
  const cap = caps?.models[id]
  const wh = p.tier !== 'custom' && cap ? caps?.tiers?.[p.tier]?.[id] ?? caps?.tiers?.[p.tier]?.[cap.family] : undefined   // V16: the model's own tier, else its family's
  return { model_id: id, turbo: cap?.turbo ? p.turbo : false, ...(wh ? { width: wh[0], height: wh[1] } : {}), ...(cap?.flux_shift === false ? { base_shift: null, max_shift: null } : {}) }
}

/** D90 (B4): why the panel cannot be submitted now (the Foot's disabled reason, and the `when` of gen.generate / gen.stage), or null. */
export function submitBlock(g: Pick<GenerateState, 'preview' | 'previewError'>, projectOpen: boolean): string | null {
  const pv = g.preview, missing = pv?.missing ?? []
  return !projectOpen ? 'no project' : g.previewError ? g.previewError : !pv ? 'preparing…' : !pv.serialized_prompt ? 'empty prompt'
    : missing.length ? `weights missing: ${missing.map((m) => m.model_id).join(', ')}` : pv.estimate.vram_fit === 'over' ? 'VRAM estimate exceeds the budget' : null
}

// ---- D115: Expand — the poses as the coverage cells ----
export type RunMode = 'generate' | 'expand'
export interface PoseCell { shot: string; angle: string; expression: string }
/** The chosen cells (a tile is a shot size and an angle; each cell one expression) and the expressions a new tile takes. */
export interface PoseSet { cells: PoseCell[]; expressions: string[] }

/** The cells an Expand runs, in the coverage's order (shot sizes, then angles, then expressions). */
export function expandCells(poses: PoseSet, shots: string[], angles: string[], expressions: string[]): PoseCell[] {
  const idx = (xs: string[], x: string) => { const i = xs.indexOf(x); return i < 0 ? xs.length : i }
  const seen = new Set<string>()
  return poses.cells.filter((c) => { const k = `${c.shot}|${c.angle}|${c.expression}`; if (seen.has(k)) return false; seen.add(k); return true })
    .sort((a, b) => idx(shots, a.shot) - idx(shots, b.shot) || idx(angles, a.angle) - idx(angles, b.angle) || idx(expressions, a.expression) - idx(expressions, b.expression))
}

/** D115: the panel's recipe for one cell, the pose content replaced — every subject's action, pose and position dropped, the linked
 *  (else the first) subject's pose the cell's expression, the composition the shot's phrase, the camera's angle the angle's; in Text mode
 *  the cell's sentence is appended to the text; a JSON prompt is read as a tree first. Everything else (the model, size, style, LoRAs,
 *  references, the sheet) is the panel's. */
export function recipeForCell(p: Panel, cell: PoseCell, phrases: { shots: Record<string, string>; angles: Record<string, string> }, seeds?: number[]): T2IRecipe {
  const shot = phrases.shots[cell.shot] ?? cell.shot, angle = phrases.angles[cell.angle] ?? cell.angle
  const sentence = `${shot}, ${angle}, ${cell.expression} expression`
  if (p.prompt_mode === 'text') return recipeFromPanel({ ...p, text: [p.text.trim().replace(/[.\s]+$/, ''), sentence].filter(Boolean).join('. ') + '.' }, seeds)
  let tree = p.tree
  if (p.prompt_mode === 'json') { try { tree = treeFromJson(JSON.parse(p.json_text || '{}')) } catch { tree = EMPTY_TREE } }
  const subs = (tree.subjects ?? []).map((s) => ({ ...s, action: '', pose: '', position: '' }))
  const at = Math.max(0, subs.findIndex((s) => !!s.profile_id))
  if (subs[at]) subs[at] = { ...subs[at], pose: `${cell.expression} expression` }
  const next: Tree = { ...tree, subjects: subs, composition: shot, camera: { ...tree.camera, angle } }
  return recipeFromPanel({ ...p, prompt_mode: 'tree', tree: next }, seeds)
}

export function recipeFromPanel(p: Panel, seeds?: number[]): T2IRecipe {
  const model_id = panelModel(p)
  const cap = useSession.getState().capabilities?.models[model_id]
  const shift = cap?.flux_shift !== false                                // D90 (B12): a persisted override never reaches a graph without the node
  let prompt_json: Record<string, unknown> | undefined
  if (p.prompt_mode === 'tree') prompt_json = cleanTree(p.tree)
  else if (p.prompt_mode === 'json') { try { prompt_json = JSON.parse(p.json_text || '{}') } catch { prompt_json = undefined } }
  const seedList = seeds ?? Array.from({ length: p.count }, (_, i) => (p.seed_mode === 'random' ? 0 : p.seed_mode === 'fixed' ? p.seed : p.seed + i))
  return {
    kind: 't2i', model_id, prompt_mode: p.prompt_mode, prompt_json, prompt_text: p.prompt_mode === 'text' ? p.text : (p.prompt_mode === 'tree' ? p.text : ''), negative: honoursNegative(cap) ? p.negative : '',
    width: p.width, height: p.height, steps: p.steps, guidance: p.guidance, cfg: p.cfg, sampler: p.sampler, scheduler: p.scheduler, turbo: p.turbo && (cap?.turbo ?? true),
    turbo_strength: p.turbo_strength, weight_dtype: p.weight_dtype, te_device: p.te_device, te_id: p.te_id, base_shift: shift ? p.base_shift : null, max_shift: shift ? p.max_shift : null, tiled_vae: p.tiled_vae, tile_size: p.tile_size,
    seeds: seedList, refs: p.refs.map((r) => ({ asset_id: r.asset_id, note: r.note })), ref_max_px: p.ref_max_px, loras: p.loras, auto_lora: p.auto_lora,
    mentions: mentionsInUse(p).map((m) => { const li = linkedSubject(p, m.profile_id), si = sentIndex(p.tree.subjects ?? [], li), s = p.tree.subjects?.[li]   // D85: a profile mention names its profile; D92: and the card it links (D93: its index among the subjects sent)
      const shot = s && (s.shot_outfit?.trim() || s.shot_note?.trim()) ? { outfit: s.shot_outfit?.trim() ?? '', note: s.shot_note?.trim() ?? '' } : null   // D93 (B4): this shot's words; (B5) the chip's version
      const base = { group_id: m.group_id, name: m.name, ...(m.profile_id ? { profile_id: m.profile_id } : {}) }
      if (si >= 0) return { ...base, subject: si, ...(s?.version ? { version: s.version } : {}), ...(shot ? { shot } : {}) }
      const hi = sentIndex(p.tree.subjects ?? [], holderOf(p, m.profile_id))                 // D93 (C6): a prop held by that card (its index among the subjects sent)
      if (hi >= 0) return { ...base, held_by: hi }
      const sc = sceneOf(p, m.profile_id) ? p.tree.scene_link : undefined                    // D93 (C6): the place of the scene, its version and this shot's line
      if (sc) return { ...base, scene: true, ...(sc.version ? { version: sc.version } : {}), ...(sc.note?.trim() ? { shot: { outfit: '', note: sc.note.trim() } } : {}) }
      return base }),
    style_id: styleFor(p.style_id),                                                                    // D85: resolved to its fragment by the server at preview and submit
  }
}

export function panelFromRecipe(r: Record<string, unknown>, keepSeeds = false): Partial<Panel> {
  const out: Partial<Panel> = {
    model_id: String(r.model_id ?? defaultModel('t2i')), prompt_mode: (r.prompt_mode as PromptMode) ?? (r.prompt_json ? 'tree' : 'text'),
    text: String(r.prompt_text ?? ''), negative: String(r.negative ?? ''), width: Number(r.width ?? 960), height: Number(r.height ?? 544),
    steps: (r.steps as number | null) ?? null, guidance: (r.guidance as number | null) ?? null, cfg: (r.cfg as number | null) ?? null,
    sampler: (r.sampler as string | null) ?? null, scheduler: (r.scheduler as string | null) ?? null, turbo: Boolean(r.turbo), tier: 'custom',
    turbo_strength: Number(r.turbo_strength ?? 1), weight_dtype: (r.weight_dtype as string | null) ?? null, te_device: (r.te_device as string | null) ?? null, te_id: (r.te_id as string | null) ?? null,
    base_shift: (r.base_shift as number | null) ?? null, max_shift: (r.max_shift as number | null) ?? null, tiled_vae: Boolean(r.tiled_vae), tile_size: Number(r.tile_size ?? 512),
    // D73: the references a mention gave are the server's to resolve again; the mentions come back unstamped (resolved at today's revision)
    refs: Array.isArray(r.refs) ? (r.refs as { asset_id?: string; note?: string; mention?: string | null }[]).filter((x) => x.asset_id && !x.mention).map((x) => ({ asset_id: x.asset_id!, note: x.note })) : [],
    mentions: Array.isArray(r.mentions) ? (r.mentions as { group_id: string; name?: string | null; profile_id?: string | null }[]).filter((m) => m.group_id && m.name).map((m) => ({ group_id: m.group_id, name: m.name!, ...(m.profile_id ? { profile_id: m.profile_id } : {}) })) : [],
    ref_max_px: Number(r.ref_max_px ?? 1024), auto_lora: r.auto_lora === undefined ? true : Boolean(r.auto_lora),
    // LT3: a slot a mention added comes back from the mention (the server adds it again at today's version), not from the stored slots
    loras: ((r.loras as Panel['loras']) ?? []).filter((l) => !(Array.isArray(r.mentions) && (r.mentions as { lora?: string | null }[]).some((m) => m.lora === l.model_id))),
    style_id: (r.style_id as string | null | undefined) ?? null,                                     // D85: a stored recipe's style (null = it ran without one)
  }
  if (r.prompt_json && typeof r.prompt_json === 'object') { out.tree = treeFromJson(r.prompt_json as Record<string, unknown>); out.json_text = JSON.stringify(r.prompt_json, null, 2) }
  for (const m of (Array.isArray(r.mentions) ? r.mentions : []) as { profile_id?: string | null; subject?: number | null; version?: string | null; shot?: { outfit?: string; note?: string } | null; held_by?: number | null; scene?: boolean | null }[]) {   // D92: a subject's profile link comes back
    const s = m.profile_id && typeof m.subject === 'number' ? out.tree?.subjects?.[m.subject] : undefined
    if (s) Object.assign(s, { profile_id: m.profile_id!, description: '', ...(m.version ? { version: m.version } : {}), shot_outfit: m.shot?.outfit ?? '', shot_note: m.shot?.note ?? '' })   // D93 (B4, B5): the version it ran with and its shot words; the composed text was the sheet's
    const h = m.profile_id && typeof m.held_by === 'number' ? out.tree?.subjects?.[m.held_by] : undefined
    if (h) h.holds = { profile_id: m.profile_id! }                                         // D93 (C6): the prop it held (its "holding" words were the server's)
    if (m.profile_id && m.scene && out.tree) out.tree = { ...out.tree, scene: '', scene_link: { profile_id: m.profile_id, ...(m.version ? { version: m.version } : {}), note: m.shot?.note ?? '' } }   // D93 (C6): the scene's place
  }
  if (keepSeeds && Array.isArray(r.seeds) && r.seeds.length) { out.seed_mode = 'fixed'; out.seed = Number(r.seeds[0]); out.count = 1 }
  return out
}

/** D66: a submission from the Generate panel; its results show as "this batch" in Generate's grid. */
export const GENERATE_ORIGIN: JobOrigin = { suite: 'generate', surface: 'results' }

// ---- P14 (D82): the Angle tab — a new viewpoint of one asset; the server picks E12's method per move (`auto`) and says which
export type Move = 'left45' | 'right45' | 'topdown' | 'closeup' | 'wide'
export type AngleMethod = 'auto' | 'angles_lora' | 'klein_prompt'
export interface AngleState { asset_id: string | null; move: Move; method: AngleMethod; prompt_text: string; count: number }
export const MOVES: { id: Move; label: string; hint: string }[] = [
  { id: 'left45', label: 'Rotate left 45°', hint: 'the camera orbits to the subject\'s left' }, { id: 'right45', label: 'Rotate right 45°', hint: 'the camera orbits to the subject\'s right' },
  { id: 'topdown', label: 'Top-down', hint: 'from above, looking straight down' }, { id: 'closeup', label: 'Close-up', hint: 'in to the face and shoulders' },
  { id: 'wide', label: 'Wide', hint: 'back, the whole scene around the subject' },
]
export const DEFAULT_ANGLE: AngleState = { asset_id: null, move: 'left45', method: 'auto', prompt_text: '', count: 1 }
export const ANGLE_ORIGIN: JobOrigin = { suite: 'generate', surface: 'angle' }
/** The `reangle` recipe body: one seed per candidate (random), the move and the method as chosen (`auto` resolves on the server). */
export function reangleRecipe(a: AngleState): { kind: 'reangle'; asset_id: string; move: Move; method: AngleMethod; prompt_text: string; seeds: number[] } {
  if (!a.asset_id) throw new Error('no source')
  return { kind: 'reangle', asset_id: a.asset_id, move: a.move, method: a.method, prompt_text: a.prompt_text.trim(), seeds: Array.from({ length: Math.max(1, Math.min(4, a.count)) }, () => 0) }
}
/** The batch a job belongs to, as Generate's "this batch" view names it (a single job is its own batch). */
export const batchOf = (j: Pick<Job, 'id' | 'batch_id'>): string => j.batch_id ?? j.id

export interface GenerateState {
  panel: Panel; preview: Preview | null; previewError: string | null; previewing: boolean
  presets: Preset[]; lastPreset: string | null
  /** D92: the saved panel applied (or saved) in this session — a job made from it becomes its picture (origin `saved_panel`). */
  appliedPreset: string | null
  show: 'batch' | 'session' | 'all'; lastBatch: string | null; pinned: string[]
  angle: AngleState; anglePreview: DocumentPreview | null; anglePreviewError: string | null
  angleOpen: boolean                                       // D90 (02 §6.1): New angle is a sheet on an image, not a Generate tab
  source: 'prompt' | 'stage'                               // D95 (AN1, UX0 #5): Make from the prompt, or From a stage (stills; the stage is edited in Animate)
  presetText: Record<string, boolean>                      // D90 (02 §6.3): the sections that show the words under their preset icons
  setPresetText: (section: string, on: boolean) => void
  /** LT1: what the slots may hold for the panel's model (GET /loras); loadLoras prunes slots that do not fit after a model change. */
  lorasAvailable: LoraOption[]
  loadLoras: (modelId: string) => Promise<void>
  setAngle: (patch: Partial<AngleState>) => void
  refreshAnglePreview: () => Promise<void>
  /** P14: queue the new angle(s) of the source; results land in Generate's batch strip with lineage `reangle`. */
  generateAngle: (origin?: JobOrigin) => Promise<Job[] | null>
  set: (patch: Partial<Panel>) => void
  setTree: (patch: Partial<Tree>) => void
  setSubject: (i: number, patch: Partial<Subject>) => void
  addSubject: () => void
  removeSubject: (i: number) => void
  /** D92: link a subject card to a Cast profile (its current version): the profile mention is recorded so its reference set and LoRA follow
   *  (mentions.py). D93 (B4): the card copies nothing — the sheet is read from Cast at every preview and submit; words typed in the card
   *  before go to "this shot". `unlinkSubject` ends it: the composed words stay as a free card's description. */
  linkSubject: (i: number, profile: Profile) => void
  unlinkSubject: (i: number) => void
  /** D93 (B5): the version (costume) a linked card uses — undefined follows the profile's current one; the mention moves to its set. */
  setSubjectVersion: (i: number, version: string | undefined) => void
  /** D92 (Cast's "Use as a subject in Generate"): the Tree prompt with a subject card linked to the profile. */
  useAsSubject: (profile: Profile) => void
  /** D93 (C6): a subject card holds a Cast prop ("holding …", its references bound to the card) — or puts it down (`null`). */
  holdProp: (i: number, profile: Profile | null) => void
  /** D93 (C6): the Tree's scene linked to a Cast place (its sheet + this shot's line, composed by the server; the words typed in the scene go to
   *  the line); `unlinkScene` leaves the composed words as the scene. */
  linkScene: (profile: Profile) => void
  unlinkScene: () => void
  setSceneLink: (patch: Partial<Omit<SceneLink, 'profile_id'>>) => void
  /** D93 (C7): Make frame ▸ from a Dialogue / Shot node — the Tree with one linked card per speaker (their versions; the first line as the
   *  first speaker's action), the scene linked to the node's place. D125 (I1): it replaces the last shot's content (subjects, scene,
   *  framing, lead text, references); the look, the model and the size stay. */
  applyFrame: (pre: FramePrefill) => void
  /** D93 (A1): "Give <name> a look" / "More looks for <name>" on a linked card — the panel's images as the version's candidates (the page
   *  made when it has none); the description must say the look first (`castAsk` marks the card and its field takes the focus). */
  castLook: (i: number) => Promise<Job[] | null>
  castAsk: number | null
  /** D115: how the foot runs — Generate as always, or Expand: one job per pose cell with the prompt's pose and action replaced. */
  run: RunMode
  poses: PoseSet
  setRun: (run: RunMode) => void
  setPoses: (poses: PoseSet) => void
  /** A tile (a shot size and an angle) on or off; on, it takes the chosen expressions. */
  toggleTile: (shot: string, angle: string) => void
  /** An expression on or off for every chosen tile. */
  toggleExpression: (x: string) => void
  /** Expand ▶: one job per cell as one batch — on the linked character's candidates page when the prompt links one. */
  expand: (stage?: boolean) => Promise<Job[] | null>
  setCamera: (patch: Partial<Camera>) => void
  treeToJson: () => void
  jsonToTree: () => boolean
  refreshPreview: () => Promise<void>
  /** `origin` (D66) says where the request was made; the panel's own submissions default to Generate's results — or, while the For chip
   *  is set (D90, 02 §5), to the shot version it names. */
  generate: (stage?: boolean, origin?: JobOrigin, said?: { text: string; action?: { label: string; run: () => void } }) => Promise<Job[] | null>
  variations: (asset: Asset, n?: number, origin?: JobOrigin) => Promise<void>
  rerun: (asset: Asset, origin?: JobOrigin) => Promise<void>
  loadFromAsset: (asset: Asset, keepSeeds?: boolean) => void
  addRef: (assetId: string) => void
  /** D90 (B12): add references up to the model's `max_refs`; a toast says what did not fit. Returns how many were added. */
  addRefs: (assetIds: string[]) => number
  /** D90 (B12): pick the panel's model (see `modelPatch`). */
  setModel: (id: string) => void
  removeRef: (assetId: string) => void
  setRefNote: (assetId: string, note: string) => void
  addMention: (m: MentionRef) => void
  removeMention: (groupId: string) => void
  moveRef: (from: number, to: number) => void
  setShow: (s: GenerateState['show']) => void
  togglePinned: (id: string) => void
  loadPresets: () => Promise<void>
  savePreset: (name: string) => Promise<void>
  applyPreset: (name: string) => void
  deletePreset: (name: string) => Promise<void>
  /** D92: World's Rename… of a saved panel (its picture goes with it). */
  renamePreset: (from: string, to: string) => Promise<boolean>
}

/** D93 (A1): the subject card a per-item command acts on (its button sets it first; the run clears it, so the palette never acts on a
 *  stale card — D90's per-item pattern). */
export const subjectItem: { i?: number } = {}
export function runOnSubject(i: number, id: string): boolean {
  subjectItem.i = i
  try { return runCommand(id) } finally { subjectItem.i = undefined }
}
/** D93 (B5): a menu entry on one card (the version chip's "Edit the sheet in Cast") — the card set around the command's `when` and `run`. */
export const onSubject = (i: number): OnItem => (f) => { subjectItem.i = i; try { return f() } finally { subjectItem.i = undefined } }

/** D92: the newest result of a Generate job (a saved panel's picture when it is saved). */
export function latestResult(jobs: Record<string, Job>): string | null {
  const ids = (x: Job) => (x.result as { asset_ids?: string[] } | null)?.asset_ids ?? []
  const j = Object.values(jobs).filter((x) => x.origin?.suite === 'generate' && x.kind === 't2i' && x.status === 'done' && ids(x).length)
    .sort((a, b) => ((a.finished_at ?? a.created_at) < (b.finished_at ?? b.created_at) ? 1 : -1))[0]
  return j ? ids(j)[0] : null
}
/** D93 (B4): a linked card's description as the server will compose it (from the Story store's copy of the profile) — JSON mode bakes it in. */
/** D93: drop the links to Cast profiles and album groups the open project does not have — a panel remembered from another project
 *  would otherwise block the preview ("mentioned profile … does not exist"). A card keeps its words (its "this shot" line joins the
 *  description), the scene keeps its line; the count is of distinct profiles / groups dropped. */
export function withoutForeignLinks(p: Panel, profiles: ReadonlySet<string>, groups?: ReadonlySet<string>): { patch: Pick<Panel, 'tree' | 'mentions'>; dropped: number } {
  const gone = new Set<string>()
  const foreign = (id?: string) => !!id && !profiles.has(id) && (gone.add(id), true)
  const subjects = (p.tree.subjects ?? []).map((s) => {
    let out = s
    if (foreign(s.profile_id)) out = { ...out, profile_id: undefined, version: undefined, shot_outfit: undefined, shot_note: undefined, description: [s.description, s.shot_note].map((x) => x?.trim()).filter(Boolean).join(', ') }
    if (out.holds && foreign(out.holds.profile_id)) out = { ...out, holds: undefined }
    return out
  })
  let tree: Tree = p.tree.subjects ? { ...p.tree, subjects } : { ...p.tree }
  if (tree.scene_link && foreign(tree.scene_link.profile_id)) tree = { ...tree, scene: tree.scene_link.note ?? '', scene_link: undefined }
  const mentions = (p.mentions ?? []).filter((m) => (m.profile_id ? !foreign(m.profile_id) : !(groups && !groups.has(m.group_id) && (gone.add(m.group_id), true))))
  return { patch: { tree, mentions }, dropped: gone.size }
}

export function linkedWords(s: Subject, profiles: Profile[] = profilesNow()): string | null {
  const p = s.profile_id ? profiles.find((x) => x.id === s.profile_id) : undefined
  return p ? composeSheet(versionOf(p, s.version), { outfit: s.shot_outfit, note: s.shot_note }, p.name, p.cls) : null
}
/** D93 (C6): the scene a linked place composes (its sheet + this shot's line), as the server will. */
export function linkedSceneWords(link: SceneLink, profiles: Profile[] = profilesNow()): string | null {
  const p = profiles.find((x) => x.id === link.profile_id)
  return p ? composeSheet(versionOf(p, link.version), { note: link.note }, p.name, p.cls) : null
}
/** D93 (C6): a held prop's clause (its current version's sheet), as the server says it after "holding". */
export function heldWords(h: HeldProp, profiles: Profile[] = profilesNow()): string | null {
  const p = profiles.find((x) => x.id === h.profile_id)
  return p ? composeSheet(versionOf(p), null, p.name, p.cls) : null
}
/** D93 (C7): what Make frame ▸ puts into the Tree (makeFor.ts framePrefill): one linked card per speaker, the node's place, the lead text. */
export interface FramePrefill { text: string | null; subjects: { profile_id: string; version?: string; action?: string; pose?: string }[]; place: string | null }

let previewTimer: number | null = null
let previewSeq = 0
let anglePreviewSeq = 0

/** D71 (P11): references from a drag (the slots, the Generate tab): images only, no duplicates, capped by the model's `max_refs`. */
export function refDropFor(p: DragPayload) {
  const g = useGenerate.getState()
  return refDrop(g.panel.refs.map((r) => r.asset_id), p, maxRefsOf(g.panel))
}
/** Add a drag's references; a toast says what did not fit or was skipped. */
export function dropRefs(p: DragPayload): void {
  const { take, verdict } = refDropFor(p)
  take.forEach((id) => useGenerate.getState().addRef(id))
  if (verdict.ok && verdict.label?.includes(' · ')) useSession.getState().toast(verdict.label.replace(/^Add/, 'Added'), 'info')
}

export const useGenerate = create<GenerateState>()(
  persist(
    (set, get) => ({
      panel: DEFAULT_PANEL, preview: null, previewError: null, previewing: false, presets: [], lastPreset: null, appliedPreset: null, show: 'batch', lastBatch: null, pinned: [], castAsk: null, run: 'generate', poses: { cells: [], expressions: ['neutral'] },
      angle: DEFAULT_ANGLE, anglePreview: null, anglePreviewError: null, lorasAvailable: [], angleOpen: false, source: 'prompt', presetText: {},
      setPresetText: (section, on) => set({ presetText: { ...get().presetText, [section]: on } }),

      loadLoras: async (modelId) => {
        try {
          const r = await unwrap(http.GET('/loras', { params: { query: { model_id: modelId } } }))
          if (get().panel.model_id !== modelId) return                                            // the model moved on while this answered
          const fits = new Set(r.items.filter((o) => o.fits).map((o) => o.id))
          const kept = get().panel.loras.filter((l) => fits.has(l.model_id))
          set({ lorasAvailable: r.items })
          if (kept.length !== get().panel.loras.length) get().set({ loras: kept })               // a persisted slot from another model
        } catch { set({ lorasAvailable: [] }) }
      },

      setAngle: (patch) => { set({ angle: { ...get().angle, ...patch } }); void get().refreshAnglePreview() },
      refreshAnglePreview: async () => {
        const a = get().angle
        if (!a.asset_id) { set({ anglePreview: null, anglePreviewError: null }); return }
        const seq = ++anglePreviewSeq
        try {
          const pv = await unwrap(http.POST('/recipes/preview', { body: { recipe: reangleRecipe(a) } }))
          if (seq === anglePreviewSeq) set({ anglePreview: isDocumentPreview(pv) ? pv : null, anglePreviewError: null })
        } catch (e) {
          if (seq === anglePreviewSeq) set({ anglePreview: null, anglePreviewError: (e as ApiError).detail ?? String(e) })
        }
      },
      generateAngle: async (asked) => {
        const inImage = ['generate', 'edit'].includes(useSession.getState().ui.suite)   // D125 (I4): opened inside Image, the For chip's shot gets it
        const origin = asked ?? (inImage ? originFor('generate', ANGLE_ORIGIN) : ANGLE_ORIGIN)
        const s = useSession.getState()
        try {
          const jobs = await unwrap(http.POST('/jobs', { body: { recipe: reangleRecipe(get().angle), stage: false, origin } }))
          const batch = jobs.jobs[0] ? batchOf(jobs.jobs[0]) : null
          set({ lastBatch: batch, show: 'batch' })
          const f = origin.surface === FOR_SHOT ? useMakeFor.getState().generate : null
          s.toast(`Queued ${jobs.jobs.length} new angle${jobs.jobs.length > 1 ? 's' : ''}${f ? ` for ${forLabel(f)} — they land as its takes` : ''}`, 'success')
          await s.refreshAll()
          return jobs.jobs
        } catch (e) { s.toast(`New angle failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
      },

      set: (patch) => { set({ panel: { ...get().panel, ...patch } }); if (patch.model_id !== undefined) settleModel(get, set); schedulePreview(get) },
      setTree: (patch) => { get().set({ tree: { ...get().panel.tree, ...patch } }) },
      setSubject: (i, patch) => { const subs = [...(get().panel.tree.subjects ?? [])]; subs[i] = { ...subs[i], ...patch }; get().setTree({ subjects: subs }) },
      addSubject: () => get().setTree({ subjects: [...(get().panel.tree.subjects ?? []), { ...NEW_SUBJECT }] }),
      removeSubject: (i) => get().setTree({ subjects: (get().panel.tree.subjects ?? []).filter((_, j) => j !== i) }),
      linkSubject: (i, profile) => {
        const p = get().panel, subs = [...(p.tree.subjects ?? [])], cur = subs[i]
        const v = profile.versions.find((x) => x.id === profile.current)
        if (!cur || !v) return
        const was = cur.profile_id ?? null
        const typed = was ? '' : cur.description.trim()                                     // D93 (B4): a free card's words go to "this shot"; nothing is copied
        subs[i] = { ...cur, profile_id: profile.id, description: '', version: undefined, shot_outfit: was ? cur.shot_outfit : '', shot_note: was ? cur.shot_note : (adoptDescription(typed, v, profile.name)?.note ?? '') }
        const text = promptStrings(p).join('\n')
        const others = (p.mentions ?? []).filter((m) => m.group_id !== v.group_id && m.profile_id !== profile.id
          && !(was && m.profile_id === was && !subs.some((s) => s.profile_id === was) && !text.includes('@' + m.name)))
        get().set({ tree: { ...p.tree, subjects: subs }, mentions: [...others, { group_id: v.group_id, name: profile.name, profile_id: profile.id }] })
      },
      unlinkSubject: (i) => {
        const p = get().panel, subs = [...(p.tree.subjects ?? [])], cur = subs[i]
        if (!cur?.profile_id) return
        const pid = cur.profile_id
        subs[i] = { ...cur, profile_id: undefined, version: undefined, shot_outfit: undefined, shot_note: undefined, description: linkedWords(cur) ?? cur.description }   // D93 (B4): the composed words stay
        const text = promptStrings(p).join('\n')
        get().set({ tree: { ...p.tree, subjects: subs }, mentions: (p.mentions ?? []).filter((m) => m.profile_id !== pid || subs.some((s) => s.profile_id === pid) || text.includes('@' + m.name)) })
      },
      setSubjectVersion: (i, version) => {
        const p = get().panel, subs = [...(p.tree.subjects ?? [])], cur = subs[i]
        const prof = cur?.profile_id ? profilesNow().find((x) => x.id === cur.profile_id) : undefined
        const v = versionOf(prof, version)
        if (!cur || !prof || !v) return
        subs[i] = { ...cur, version: version && version !== prof.current ? version : undefined }   // the current one: follow the current one
        get().set({ tree: { ...p.tree, subjects: subs }, mentions: (p.mentions ?? []).map((m) => (m.profile_id === prof.id ? { ...m, group_id: v.group_id } : m)) })
      },
      useAsSubject: (profile) => {
        if (get().panel.prompt_mode === 'json' && !get().jsonToTree()) return
        if (get().panel.prompt_mode !== 'tree') get().set({ prompt_mode: 'tree' })
        if (linkedSubject(get().panel, profile.id) >= 0) return                 // already a subject
        const subs = get().panel.tree.subjects ?? []
        const free = subs.findIndex((s) => !s.profile_id && !(s.description || s.action || s.pose || s.position || '').trim())
        const at = free >= 0 ? free : subs.length
        if (at === subs.length) get().addSubject()
        get().linkSubject(at, profile)
      },
      holdProp: (i, profile) => {
        const p = get().panel, subs = [...(p.tree.subjects ?? [])], cur = subs[i]
        if (!cur || p.prompt_mode !== 'tree') return
        subs[i] = { ...cur, holds: profile ? { profile_id: profile.id } : undefined }
        const v = profile ? versionOf(profile) : undefined
        const next = { ...p, tree: { ...p.tree, subjects: subs } }
        const ms = pruned(next).filter((m) => !(profile && m.profile_id === profile.id))
        get().set({ tree: next.tree, mentions: profile && v ? [...ms, { group_id: v.group_id, name: profile.name, profile_id: profile.id }] : ms })
      },
      linkScene: (profile) => {
        const p = get().panel
        const v = versionOf(profile)
        if (!v) return
        if (p.prompt_mode === 'json' && !get().jsonToTree()) return
        const t = get().panel.tree, was = t.scene_link
        const note = was ? was.note ?? '' : (t.scene ?? '').trim()               // the scene typed before becomes this shot's line (another place keeps the line)
        const tree: Tree = { ...t, scene: '', scene_link: { profile_id: profile.id, note } }
        const next = { ...get().panel, prompt_mode: 'tree' as const, tree }
        get().set({ prompt_mode: 'tree', tree, mentions: [...pruned(next).filter((m) => m.profile_id !== profile.id), { group_id: v.group_id, name: profile.name, profile_id: profile.id }] })
      },
      unlinkScene: () => {
        const p = get().panel, link = p.tree.scene_link
        if (!link) return
        const tree: Tree = { ...p.tree, scene: linkedSceneWords(link) ?? '', scene_link: undefined }
        get().set({ tree, mentions: pruned({ ...p, tree }) })
      },
      setSceneLink: (patch) => {
        const p = get().panel, link = p.tree.scene_link
        if (!link) return
        const next: SceneLink = { ...link, ...patch }
        const prof = profilesNow().find((x) => x.id === link.profile_id)
        if ('version' in patch && prof && (!patch.version || patch.version === prof.current)) delete next.version   // the current one: follow it
        const v = versionOf(prof, next.version)
        get().set({ tree: { ...p.tree, scene_link: next }, ...('version' in patch && v ? { mentions: (p.mentions ?? []).map((m) => (m.profile_id === link.profile_id ? { ...m, group_id: v.group_id } : m)) } : {}) })
      },
      applyFrame: (pre) => {
        if (get().panel.prompt_mode === 'json' && !get().jsonToTree()) return
        const p = get().panel
        const profiles = profilesNow()
        const cards: Subject[] = pre.subjects.map((x) => ({ ...NEW_SUBJECT, description: '', profile_id: x.profile_id, ...(x.version ? { version: x.version } : {}), action: x.action ?? '', pose: x.pose ?? '', shot_outfit: '', shot_note: '' }))
        const place = pre.place ? profiles.find((x) => x.id === pre.place) : undefined
        // D125 (I1): the shot's own content replaces the last shot's — its subjects, scene, framing, lead text and references go; the look,
        // the model and the size stay
        const base: Tree = { ...p.tree, subjects: [], scene: '', background: '', composition: '', camera: { ...EMPTY_TREE.camera } }
        delete base.scene_link
        const tree: Tree = { ...base, ...(cards.length ? { subjects: cards } : {}), ...(place ? { scene_link: { profile_id: place.id, note: '' } } : {}) }
        const linked = [...pre.subjects.map((x) => x.profile_id), ...(place ? [place.id] : [])]
        const mentions = linked.flatMap((id) => { const pr = profiles.find((x) => x.id === id); const sub = pre.subjects.find((x) => x.profile_id === id); const v = versionOf(pr, sub?.version)
          return pr && v ? [{ group_id: v.group_id, name: pr.name, profile_id: pr.id }] : [] })
        const prompt_mode = cards.length || place ? 'tree' as const : p.prompt_mode
        const next = { ...p, prompt_mode, tree, text: pre.text ?? '', refs: [] }
        const words = promptStrings(next).join('\n')
        get().set({ prompt_mode, tree, text: next.text, refs: [], mentions: [...(p.mentions ?? []).filter((m) => !linked.includes(m.profile_id ?? '') && words.includes('@' + m.name)), ...mentions] })
      },
      castLook: async (i) => {
        const p = get().panel, sub = p.tree.subjects?.[i], ss = useSession.getState()
        const prof = sub?.profile_id ? profilesNow().find((x) => x.id === sub.profile_id) : undefined
        const v = versionOf(prof, sub?.version)                                 // D93 (B5): the version the card uses
        if (!sub || !prof || !v || p.prompt_mode !== 'tree') return null
        if (v.state !== 'open') { ss.toast(`${prof.name} ${v.id} is final — make a new version to cast it again`, 'error'); return null }
        if (needsLook(composeSheet(v), prof.name)) {                           // the casting run renders the sheet: ask for it first (B4: it is written in Cast)
          set({ castAsk: i })
          window.setTimeout(() => (document.getElementById(`gen-subject-sheet-${i}`) as HTMLElement | null)?.focus(), 30)
          return null
        }
        set({ castAsk: null })
        const { useStory } = await import('../story/storyStore')
        const gid = await useStory.getState().ensureCandidates(prof.id, v.id)
        if (!gid) return null
        return get().generate(false, withIdea(castOrigin(prof.id, v.id, gid)), {                 // V76: a look made under the idea chip is the idea's too
          text: ` — they land as ${prof.name}'s candidates (add ✓ the good ones to the reference set, make one the hero)`,
          action: { label: `Open ${prof.name} in Cast`, run: () => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: prof.id, version: v.id })) } })
      },
      // ---- D115: Expand ----
      setRun: (run) => set({ run }),
      setPoses: (poses) => set({ poses }),
      toggleTile: (shot, angle) => {
        const ps = get().poses
        const on = ps.cells.some((c) => c.shot === shot && c.angle === angle)
        const ex = ps.expressions.length ? ps.expressions : ['neutral']
        set({ poses: { ...ps, cells: on ? ps.cells.filter((c) => !(c.shot === shot && c.angle === angle)) : [...ps.cells, ...ex.map((expression) => ({ shot, angle, expression }))] } })
      },
      toggleExpression: (x) => {
        const ps = get().poses
        const on = ps.expressions.includes(x)
        const tiles = Array.from(new Set(ps.cells.map((c) => `${c.shot}|${c.angle}`))).map((k) => k.split('|') as [string, string])
        const cells = on ? ps.cells.filter((c) => c.expression !== x)
          : [...ps.cells, ...tiles.filter(([shot, angle]) => !ps.cells.some((c) => c.shot === shot && c.angle === angle && c.expression === x)).map(([shot, angle]) => ({ shot, angle, expression: x }))]
        set({ poses: { cells, expressions: on ? ps.expressions.filter((e) => e !== x) : [...ps.expressions, x] } })
      },
      expand: async (stage = false) => {
        const ss = useSession.getState(), st = ss.capabilities?.story
        let p = get().panel
        const cells = expandCells(get().poses, st?.coverage?.shots ?? [], st?.coverage?.angles ?? [], st?.coverage?.expressions ?? [])
        if (!cells.length) { ss.toast('Pick at least one pose in the Poses section', 'error'); return null }
        const phrases = (st?.coverage?.phrases ?? { shots: {}, angles: {} }) as { shots: Record<string, string>; angles: Record<string, string> }
        const sub = p.prompt_mode === 'tree' ? (p.tree.subjects ?? []).find((x) => !!x.profile_id) : undefined   // the linked character: its candidates
        const prof = sub?.profile_id ? profilesNow().find((x) => x.id === sub.profile_id) : undefined
        const v = versionOf(prof, sub?.version)
        let origin = originFor('generate', GENERATE_ORIGIN)
        if (prof && v) {
          if (v.state !== 'open') { ss.toast(`${prof.name} ${v.id} is final — make a new version to expand it`, 'error'); return null }
          const { useStory } = await import('../story/storyStore')
          const gid = await useStory.getState().ensureCandidates(prof.id, v.id)
          if (!gid) return null
          origin = withIdea(castOrigin(prof.id, v.id, gid))                                  // CW2: the idea chip's stamp stays
        }
        const n = cells.length * p.count
        if (n > 8) {
          const secs = (st?.seconds ?? 0) * n
          const ok = await askConfirm({ title: `Expand ${prof?.name ?? 'the subject'}?`, okLabel: `Queue ${n} jobs`,
            text: `${cells.length} pose${cells.length === 1 ? '' : 's'} × ${p.count}: ${n} images${prof && v ? ` as ${prof.name} ${v.id}'s candidates` : ''} — ${secs ? `about ${Math.max(1, Math.round(secs / 60))} min with the model loaded` : 'time unknown'}.` })
          if (!ok) return null
        }
        p = get().panel                                                                        // V75: what the panel holds now — edits made with the dialog up run
        const items = cells.map((cell) => ({ recipe: recipeForCell(p, cell, phrases) as unknown as Record<string, unknown>, origin: { ...origin, payload: { ...(origin.payload ?? {}), cell } } }))
        try {
          const jobs = await unwrap(http.POST('/jobs/batch', { body: { items, stage } }))
          const batch = jobs.jobs[0] ? batchOf(jobs.jobs[0]) : null
          set({ lastBatch: batch, show: 'batch' })
          ss.toast(`${stage ? 'Queued for later' : 'Queued'}: ${jobs.jobs.length} image${jobs.jobs.length === 1 ? '' : 's'} for ${cells.length} pose${cells.length === 1 ? '' : 's'}` +
            (prof ? ` — they land as ${prof.name}'s candidates in Cast` : ''), 'success')
          await ss.refreshAll()
          if (p.seed_mode === 'increment') get().set({ seed: p.seed + p.count })
          return jobs.jobs
        } catch (e) { ss.toast(`Expand failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
      },
      setCamera: (patch) => get().setTree({ camera: { ...get().panel.tree.camera, ...patch } }),
      treeToJson: () => {                                                      // D93 (B4): JSON has no links — a linked card's composed words are written in
        const t = get().panel.tree
        const held = (s: Subject) => { const w = s.holds ? heldWords(s.holds) : null; return w ? { description: [s.description.trim(), `holding ${w}`].filter(Boolean).join(', ') } : {} }   // D93 (C6)
        get().set({ json_text: JSON.stringify(cleanTree({ ...t, ...(t.scene_link ? { scene: linkedSceneWords(t.scene_link) ?? '', scene_link: undefined } : {}),
          subjects: (t.subjects ?? []).map((s) => { const own = s.profile_id ? { ...s, profile_id: undefined, description: linkedWords(s) ?? '' } : s; return { ...own, ...held(own), holds: undefined } }) }), null, 2), prompt_mode: 'json' })
      },
      jsonToTree: () => {
        try { const j = JSON.parse(get().panel.json_text || '{}'); get().set({ tree: treeFromJson(j), prompt_mode: 'tree' }); return true }
        catch { useSession.getState().toast('JSON is not valid', 'error'); return false }
      },

      refreshPreview: async () => {
        const seq = ++previewSeq
        set({ previewing: true })
        try {
          const pv = await unwrap(http.POST('/recipes/preview', { body: { recipe: recipeFromPanel(get().panel) } }))
          if (seq === previewSeq) set({ preview: isT2IPreview(pv) ? pv : null, previewError: null })
        } catch (e) {
          if (seq === previewSeq) set({ previewError: (e as ApiError).detail ?? String(e) })
        } finally { if (seq === previewSeq) set({ previewing: false }) }
      },

      generate: async (stage = false, asked, said) => {
        const s = useSession.getState()
        const base = asked ?? originFor('generate', GENERATE_ORIGIN)              // D90 (02 §5): the For chip's shot gets the results as takes
        const lp = asked ? null : get().appliedPreset                             // D92: made from an applied saved panel — its picture follows the result
        const origin = lp ? { ...base, payload: { ...(base.payload ?? {}), saved_panel: lp } } : base
        const f = origin.surface === FOR_SHOT ? useMakeFor.getState().generate : null
        try {
          const jobs = await unwrap(http.POST('/jobs', { body: { recipe: recipeFromPanel(get().panel), stage, origin } }))
          const batch = jobs.jobs[0] ? batchOf(jobs.jobs[0]) : null
          set({ lastBatch: batch, show: 'batch' })
          s.toast((stage ? `Queued ${jobs.jobs.length} job${jobs.jobs.length > 1 ? 's' : ''} for later` : `Queued ${jobs.jobs.length} image${jobs.jobs.length > 1 ? 's' : ''}`) + (f ? ` for ${forLabel(f)} — they land as its takes` : said?.text ?? ''), 'success', said?.action)
          await s.refreshAll()
          if (get().panel.seed_mode === 'increment') get().set({ seed: get().panel.seed + get().panel.count })
          return jobs.jobs
        } catch (e) { s.toast(`Generate failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
      },
      variations: async (asset, n = 4, origin) => {
        const r = (asset.params?.recipe as Record<string, unknown> | undefined)
        if (!r) { useSession.getState().toast('This asset has no recipe to vary', 'error'); return }
        get().loadFromAsset(asset, false)
        get().set({ seed_mode: 'random', count: n })
        navigate({ suite: 'generate' })
        await get().generate(false, origin)
      },
      rerun: async (asset, origin) => {
        if (!asset.params?.recipe) { useSession.getState().toast('This asset has no recipe to re-run', 'error'); return }
        get().loadFromAsset(asset, true)
        navigate({ suite: 'generate' })
        await get().generate(false, origin)
      },
      loadFromAsset: (asset, keepSeeds = false) => {
        const r = asset.params?.recipe as Record<string, unknown> | undefined
        if (!r) return
        get().set(panelFromRecipe(r, keepSeeds))
        useSession.getState().toast('Panel loaded from asset', 'info')
      },
      addRef: (assetId) => { get().addRefs([assetId]) },
      addRefs: (assetIds) => {
        const p = get().panel, s = useSession.getState()
        const max = maxRefsOf(p), fresh = [...new Set(assetIds)].filter((id) => !p.refs.some((r) => r.asset_id === id))
        const take = fresh.slice(0, Math.max(0, max - p.refs.length))
        if (fresh.length > take.length) {                              // D90 (B12): the model's limit, said rather than sent and refused
          const label = s.capabilities?.models[panelModel(p)]?.label ?? 'this model'
          s.toast(!max ? `${label} takes no reference images` : take.length ? `Added ${take.length}; ${fresh.length - take.length} over the limit of ${max} references on ${label}` : `All ${max} reference slots are full on ${label}`, take.length ? 'info' : 'error')
        }
        if (take.length) { get().set({ refs: [...p.refs, ...take.map((asset_id) => ({ asset_id }))] }); navigate({ suite: 'generate' }) }
        return take.length
      },
      setModel: (id) => get().set(modelPatch(get().panel, id)),
      removeRef: (assetId) => get().set({ refs: get().panel.refs.filter((r) => r.asset_id !== assetId) }),
      setRefNote: (assetId, note) => get().set({ refs: get().panel.refs.map((r) => (r.asset_id === assetId ? { ...r, note: note || undefined } : r)) }),
      addMention: (m) => { const ms = get().panel.mentions ?? []; if (!ms.some((x) => x.group_id === m.group_id)) get().set({ mentions: [...ms, m] }) },
      removeMention: (groupId) => {                                     // the chip's ×: the mention goes, its @name reads as plain text
        const p = get().panel
        const m = (p.mentions ?? []).find((x) => x.group_id === groupId)
        if (!m) return
        const fix = (v: unknown): unknown => (typeof v === 'string' ? unmention(v, m.name) : Array.isArray(v) ? v.map(fix) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, fix(x)])) : v)
        const tree = fix(p.tree) as Tree
        if (m.profile_id) tree.subjects = (tree.subjects ?? []).map((s) => (s.profile_id === m.profile_id ? { ...s, profile_id: undefined } : s.holds?.profile_id === m.profile_id ? { ...s, holds: undefined } : s))   // D92: the card's link goes with it; D93 (C6): a held prop too
        if (m.profile_id && tree.scene_link?.profile_id === m.profile_id) { tree.scene = linkedSceneWords(tree.scene_link) ?? ''; tree.scene_link = undefined }   // D93 (C6): the scene keeps its words
        get().set({ mentions: (p.mentions ?? []).filter((x) => x.group_id !== groupId), text: unmention(p.text, m.name), tree, json_text: unmention(p.json_text, m.name) })
      },
      moveRef: (from, to) => { const refs = [...get().panel.refs]; const [x] = refs.splice(from, 1); refs.splice(to, 0, x); get().set({ refs }) },
      setShow: (show) => set({ show }),
      togglePinned: (id) => set({ pinned: get().pinned.includes(id) ? get().pinned.filter((x) => x !== id) : [...get().pinned, id].slice(-6) }),

      loadPresets: async () => {
        try { const r = await unwrap(http.GET('/project/presets')); set({ presets: r.presets as unknown as Preset[], lastPreset: r.last ?? null }) } catch { set({ presets: [], lastPreset: null }) }
      },
      savePreset: async (name) => {
        const thumb = latestResult(useSession.getState().jobs) ?? get().presets.find((p) => p.name === name)?.thumb_asset_id ?? null   // D92: the panel's most recent result is its picture
        const presets = [...get().presets.filter((p) => p.name !== name), { name, panel: get().panel, saved_at: new Date().toISOString(), thumb_asset_id: thumb }]
        const r = await unwrap(http.PUT('/project/presets', { body: { presets, last: name } as never }))
        set({ presets: r.presets as unknown as Preset[], lastPreset: name, appliedPreset: name })
        useSession.getState().toast(`Preset "${name}" saved`, 'success')
      },
      applyPreset: (name) => { const p = get().presets.find((x) => x.name === name); if (p) { get().set({ ...p.panel }); set({ lastPreset: name, appliedPreset: name }) } },
      deletePreset: async (name) => {
        const presets = get().presets.filter((p) => p.name !== name)
        const r = await unwrap(http.PUT('/project/presets', { body: { presets, last: get().lastPreset === name ? null : get().lastPreset } as never }))
        set({ presets: r.presets as unknown as Preset[], lastPreset: r.last ?? null, ...(get().appliedPreset === name ? { appliedPreset: null } : {}) })
      },
      renamePreset: async (from, to) => {
        const name = to.trim()
        if (!name || name === from) return false
        if (get().presets.some((p) => p.name === name)) { useSession.getState().toast(`A saved panel is already called "${name}"`); return false }
        const presets = get().presets.map((p) => (p.name === from ? { ...p, name } : p))
        try {
          const r = await unwrap(http.PUT('/project/presets', { body: { presets, last: get().lastPreset === from ? name : get().lastPreset } as never }))
          set({ presets: r.presets as unknown as Preset[], lastPreset: r.last ?? null, ...(get().appliedPreset === from ? { appliedPreset: name } : {}) })
          return true
        } catch (e) { useSession.getState().toast(`Not renamed: ${(e as ApiError).detail ?? e}`); return false }
      },
    }),
    { name: 'loom2.generate', partialize: (s) => ({ panel: s.panel, show: s.show, presetText: s.presetText }) as never,
      // a panel persisted before a field existed gets that field's default (new engine options, 2026-10-06)
      merge: (persisted, current) => { const p = (persisted ?? {}) as Partial<GenerateState>; return { ...current, ...p, panel: { ...DEFAULT_PANEL, ...(p.panel ?? {}) } } } },
  ),
)

/** D93: a mentioned set or profile moved on the server (a hero added, references kept) — the preview resolves the mentions again, so the
 *  subject cards' slots and the casting offer follow. */
export function mentionsMoved(what: { groups?: string[]; profile?: string }): void {
  const ms = mentionsInUse(useGenerate.getState().panel)
  if (ms.some((m) => (what.groups ?? []).includes(m.group_id) || (!!what.profile && m.profile_id === what.profile))) schedulePreview(useGenerate.getState)
}

function schedulePreview(get: () => GenerateState) {
  if (previewTimer) window.clearTimeout(previewTimer)
  previewTimer = window.setTimeout(() => { previewTimer = null; void get().refreshPreview() }, 250)
}

if (DEV_HOOKS) (window as unknown as { __loom2Generate?: typeof useGenerate }).__loom2Generate = useGenerate   // dev: the e2e sets the panel (U3d)

// V70: the capabilities arrive after the remembered panel — a model this build does not offer is settled then
useSession.subscribe((s, prev) => { if (s.capabilities && s.capabilities !== prev.capabilities) settleModel(useGenerate.getState, useGenerate.setState) })

/** U1 (D157, 06 §5.3): the Make panel per context (World: an entity version, a sketch) — saved on leaving, restored on returning. */
export const makeContext = contextSlot<Panel>(() => structuredClone(useGenerate.getState().panel), (p) => useGenerate.getState().set(p))
