// Generate suite state (09): the Panel (prompt tree / JSON / text, model, sampling, size, batch, references,
// presets), the live preview from /recipes/preview, and the verbs other suites call (reference, re-run, variations).
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, ApiError } from '../../api/client'
import type { Asset, Job } from '../../api/types'
import { useSession } from '../../store/session'

export interface Subject { description: string; position?: string; action?: string; pose?: string; color_match?: string }
export interface Camera { angle?: string; lens?: string; depth_of_field?: string; 'f-number'?: string; distance?: string }
export interface Tree { scene?: string; subjects?: Subject[]; style?: string; color_palette?: string[]; lighting?: string; mood?: string; background?: string; composition?: string; camera?: Camera }
export type PromptMode = 'tree' | 'json' | 'text'
export type SeedMode = 'random' | 'fixed' | 'increment'
export interface RefSlot { asset_id: string; note?: string }

export interface Panel {
  prompt_mode: PromptMode; tree: Tree; json_text: string; text: string; negative: string
  model_id: string; steps: number | null; guidance: number | null; cfg: number | null; sampler: string | null; scheduler: string | null; turbo: boolean
  // ComfyUI configuration surfaced 2026-10-06 (null = the model preset's value; see /capabilities)
  turbo_strength: number; weight_dtype: string | null; te_device: string | null; te_id: string | null; base_shift: number | null; max_shift: number | null; tiled_vae: boolean; tile_size: number
  seed_mode: SeedMode; seed: number; count: number
  width: number; height: number; tier: 'thumb' | 'draft' | 'full' | 'custom'
  refs: RefSlot[]; ref_max_px: number
  loras: { model_id: string; strength: number }[]
}

export interface Preview {
  serialized_prompt: string; prompt_mode: string; width: number; height: number; steps: number; guidance: number; cfg: number; sampler: string; scheduler: string
  turbo: boolean; distilled: boolean; negative_used: boolean; word_count: number; token_estimate: number; refs: number; max_refs: number
  turbo_strength: number | null; weight_dtype: string; te_device: string; te_id: string; base_shift: number | null; max_shift: number | null; tiled_vae: boolean; tile_size: number | null
  missing: { model_id: string; health: string; approx_gb: number | null }[]; estimate: { seconds: number | null; source: string; vram_gb?: number; vram_budget_gb?: number; vram_fit?: 'ok' | 'tight' | 'over' }; count: number
}
export interface Preset { name: string; panel: Panel; saved_at: string }
export interface Snippet { name: string; field: string; text: string }

/** A fresh subject card; subjects are optional — none by default (2026-10-06). */
export const NEW_SUBJECT: Subject = { description: '', position: '', action: '', pose: '', color_match: 'exact' }
const EMPTY_TREE: Tree = { scene: '', subjects: [], style: '', color_palette: [], lighting: '', mood: '', background: '', composition: '', camera: { angle: '', lens: '', depth_of_field: '', 'f-number': '', distance: '' } }
export const DEFAULT_PANEL: Panel = {
  prompt_mode: 'tree', tree: EMPTY_TREE, json_text: '', text: '', negative: '',
  model_id: 'flux2-dev-fp8mixed', steps: null, guidance: null, cfg: null, sampler: null, scheduler: null, turbo: true,
  turbo_strength: 1, weight_dtype: null, te_device: null, te_id: null, base_shift: null, max_shift: null, tiled_vae: false, tile_size: 512,
  seed_mode: 'random', seed: 1, count: 4, width: 960, height: 544, tier: 'draft', refs: [], ref_max_px: 1024, loras: [],
}

/** Drop empty leaves so the JSON sent is compact (04 §3c). */
export function cleanTree(t: Tree): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(t)) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v)) {
      if (k === 'subjects') {
        const subs = (v as Subject[]).filter((s) => (s.description || s.action || s.pose || s.position || '').trim()).map((s) => Object.fromEntries(Object.entries(s).filter(([, x]) => x !== '' && x != null)))
        if (subs.length) out[k] = subs
      } else if (v.length) out[k] = v
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

export function recipeFromPanel(p: Panel, seeds?: number[]): Record<string, unknown> {
  let prompt_json: Record<string, unknown> | undefined
  if (p.prompt_mode === 'tree') prompt_json = cleanTree(p.tree)
  else if (p.prompt_mode === 'json') { try { prompt_json = JSON.parse(p.json_text || '{}') } catch { prompt_json = undefined } }
  const seedList = seeds ?? Array.from({ length: p.count }, (_, i) => (p.seed_mode === 'random' ? 0 : p.seed_mode === 'fixed' ? p.seed : p.seed + i))
  return {
    kind: 't2i', model_id: p.model_id, prompt_mode: p.prompt_mode, prompt_json, prompt_text: p.prompt_mode === 'text' ? p.text : (p.prompt_mode === 'tree' ? p.text : ''), negative: p.negative,
    width: p.width, height: p.height, steps: p.steps, guidance: p.guidance, cfg: p.cfg, sampler: p.sampler, scheduler: p.scheduler, turbo: p.turbo,
    turbo_strength: p.turbo_strength, weight_dtype: p.weight_dtype, te_device: p.te_device, te_id: p.te_id, base_shift: p.base_shift, max_shift: p.max_shift, tiled_vae: p.tiled_vae, tile_size: p.tile_size,
    seeds: seedList, refs: p.refs.map((r) => ({ asset_id: r.asset_id, note: r.note })), ref_max_px: p.ref_max_px, loras: p.loras,
  }
}

export function panelFromRecipe(r: Record<string, unknown>, keepSeeds = false): Partial<Panel> {
  const out: Partial<Panel> = {
    model_id: String(r.model_id ?? 'flux2-dev-fp8mixed'), prompt_mode: (r.prompt_mode as PromptMode) ?? (r.prompt_json ? 'tree' : 'text'),
    text: String(r.prompt_text ?? ''), negative: String(r.negative ?? ''), width: Number(r.width ?? 960), height: Number(r.height ?? 544),
    steps: (r.steps as number | null) ?? null, guidance: (r.guidance as number | null) ?? null, cfg: (r.cfg as number | null) ?? null,
    sampler: (r.sampler as string | null) ?? null, scheduler: (r.scheduler as string | null) ?? null, turbo: Boolean(r.turbo), tier: 'custom',
    turbo_strength: Number(r.turbo_strength ?? 1), weight_dtype: (r.weight_dtype as string | null) ?? null, te_device: (r.te_device as string | null) ?? null, te_id: (r.te_id as string | null) ?? null,
    base_shift: (r.base_shift as number | null) ?? null, max_shift: (r.max_shift as number | null) ?? null, tiled_vae: Boolean(r.tiled_vae), tile_size: Number(r.tile_size ?? 512),
    refs: Array.isArray(r.refs) ? (r.refs as { asset_id?: string; note?: string }[]).filter((x) => x.asset_id).map((x) => ({ asset_id: x.asset_id!, note: x.note })) : [],
    ref_max_px: Number(r.ref_max_px ?? 1024), loras: (r.loras as Panel['loras']) ?? [],
  }
  if (r.prompt_json && typeof r.prompt_json === 'object') { out.tree = treeFromJson(r.prompt_json as Record<string, unknown>); out.json_text = JSON.stringify(r.prompt_json, null, 2) }
  if (keepSeeds && Array.isArray(r.seeds) && r.seeds.length) { out.seed_mode = 'fixed'; out.seed = Number(r.seeds[0]); out.count = 1 }
  return out
}

export interface GenerateState {
  panel: Panel; preview: Preview | null; previewError: string | null; previewing: boolean
  presets: Preset[]; lastPreset: string | null; snippets: Snippet[]
  show: 'batch' | 'session' | 'all'; lastBatch: string | null; pinned: string[]
  set: (patch: Partial<Panel>) => void
  setTree: (patch: Partial<Tree>) => void
  setSubject: (i: number, patch: Partial<Subject>) => void
  addSubject: () => void
  removeSubject: (i: number) => void
  setCamera: (patch: Partial<Camera>) => void
  treeToJson: () => void
  jsonToTree: () => boolean
  refreshPreview: () => Promise<void>
  generate: (stage?: boolean) => Promise<Job[] | null>
  variations: (asset: Asset, n?: number) => Promise<void>
  rerun: (asset: Asset) => Promise<void>
  loadFromAsset: (asset: Asset, keepSeeds?: boolean) => void
  addRef: (assetId: string) => void
  removeRef: (assetId: string) => void
  moveRef: (from: number, to: number) => void
  setShow: (s: GenerateState['show']) => void
  togglePinned: (id: string) => void
  loadPresets: () => Promise<void>
  savePreset: (name: string) => Promise<void>
  applyPreset: (name: string) => void
  deletePreset: (name: string) => Promise<void>
  loadSnippets: () => Promise<void>
  saveSnippet: (s: Snippet) => Promise<void>
  deleteSnippet: (name: string) => Promise<void>
}

let previewTimer: number | null = null
let previewSeq = 0

export const useGenerate = create<GenerateState>()(
  persist(
    (set, get) => ({
      panel: DEFAULT_PANEL, preview: null, previewError: null, previewing: false, presets: [], lastPreset: null, snippets: [], show: 'batch', lastBatch: null, pinned: [],

      set: (patch) => { set({ panel: { ...get().panel, ...patch } }); schedulePreview(get) },
      setTree: (patch) => { get().set({ tree: { ...get().panel.tree, ...patch } }) },
      setSubject: (i, patch) => { const subs = [...(get().panel.tree.subjects ?? [])]; subs[i] = { ...subs[i], ...patch }; get().setTree({ subjects: subs }) },
      addSubject: () => get().setTree({ subjects: [...(get().panel.tree.subjects ?? []), { ...NEW_SUBJECT }] }),
      removeSubject: (i) => get().setTree({ subjects: (get().panel.tree.subjects ?? []).filter((_, j) => j !== i) }),
      setCamera: (patch) => get().setTree({ camera: { ...get().panel.tree.camera, ...patch } }),
      treeToJson: () => get().set({ json_text: JSON.stringify(cleanTree(get().panel.tree), null, 2), prompt_mode: 'json' }),
      jsonToTree: () => {
        try { const j = JSON.parse(get().panel.json_text || '{}'); get().set({ tree: treeFromJson(j), prompt_mode: 'tree' }); return true }
        catch { useSession.getState().toast('JSON is not valid', 'error'); return false }
      },

      refreshPreview: async () => {
        const seq = ++previewSeq
        set({ previewing: true })
        try {
          const pv = await api.post<Preview>('/recipes/preview', { recipe: recipeFromPanel(get().panel) })
          if (seq === previewSeq) set({ preview: pv, previewError: null })
        } catch (e) {
          if (seq === previewSeq) set({ previewError: (e as ApiError).detail ?? String(e) })
        } finally { if (seq === previewSeq) set({ previewing: false }) }
      },

      generate: async (stage = false) => {
        const s = useSession.getState()
        try {
          const jobs = await api.post<{ jobs: Job[] }>('/jobs', { recipe: recipeFromPanel(get().panel), stage })
          const batch = jobs.jobs[0]?.batch_id ?? jobs.jobs[0]?.id ?? null
          set({ lastBatch: batch, show: 'batch' })
          s.toast(stage ? `Staged ${jobs.jobs.length} job${jobs.jobs.length > 1 ? 's' : ''}` : `Queued ${jobs.jobs.length} image${jobs.jobs.length > 1 ? 's' : ''}`, 'success')
          await s.refreshAll()
          if (get().panel.seed_mode === 'increment') get().set({ seed: get().panel.seed + get().panel.count })
          return jobs.jobs
        } catch (e) { s.toast(`Generate failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
      },
      variations: async (asset, n = 4) => {
        const r = (asset.params?.recipe as Record<string, unknown> | undefined)
        if (!r) { useSession.getState().toast('This asset has no recipe to vary', 'error'); return }
        get().loadFromAsset(asset, false)
        get().set({ seed_mode: 'random', count: n })
        useSession.getState().setSuite('generate')
        await get().generate(false)
      },
      rerun: async (asset) => {
        if (!asset.params?.recipe) { useSession.getState().toast('This asset has no recipe to re-run', 'error'); return }
        get().loadFromAsset(asset, true)
        useSession.getState().setSuite('generate')
        await get().generate(false)
      },
      loadFromAsset: (asset, keepSeeds = false) => {
        const r = asset.params?.recipe as Record<string, unknown> | undefined
        if (!r) return
        get().set(panelFromRecipe(r, keepSeeds))
        useSession.getState().toast('Panel loaded from asset', 'info')
      },
      addRef: (assetId) => {
        const refs = get().panel.refs
        if (refs.some((r) => r.asset_id === assetId)) return
        get().set({ refs: [...refs, { asset_id: assetId }] })
        useSession.getState().setSuite('generate')
      },
      removeRef: (assetId) => get().set({ refs: get().panel.refs.filter((r) => r.asset_id !== assetId) }),
      moveRef: (from, to) => { const refs = [...get().panel.refs]; const [x] = refs.splice(from, 1); refs.splice(to, 0, x); get().set({ refs }) },
      setShow: (show) => set({ show }),
      togglePinned: (id) => set({ pinned: get().pinned.includes(id) ? get().pinned.filter((x) => x !== id) : [...get().pinned, id].slice(-6) }),

      loadPresets: async () => {
        try { const r = await api.get<{ presets: Preset[]; last: string | null }>('/project/presets'); set({ presets: r.presets ?? [], lastPreset: r.last ?? null }) } catch { set({ presets: [], lastPreset: null }) }
      },
      savePreset: async (name) => {
        const presets = [...get().presets.filter((p) => p.name !== name), { name, panel: get().panel, saved_at: new Date().toISOString() }]
        await api.put('/project/presets', { presets, last: name })
        set({ presets, lastPreset: name })
        useSession.getState().toast(`Preset "${name}" saved`, 'success')
      },
      applyPreset: (name) => { const p = get().presets.find((x) => x.name === name); if (p) { get().set({ ...p.panel }); set({ lastPreset: name }) } },
      deletePreset: async (name) => { const presets = get().presets.filter((p) => p.name !== name); await api.put('/project/presets', { presets, last: get().lastPreset === name ? null : get().lastPreset }); set({ presets }) },
      loadSnippets: async () => { try { set({ snippets: (await api.get<{ snippets: Snippet[] }>('/snippets')).snippets ?? [] }) } catch { set({ snippets: [] }) } },
      saveSnippet: async (sn) => { const snippets = [...get().snippets.filter((x) => !(x.name === sn.name && x.field === sn.field)), sn]; await api.put('/snippets', { snippets }); set({ snippets }) },
      deleteSnippet: async (name) => { const snippets = get().snippets.filter((x) => x.name !== name); await api.put('/snippets', { snippets }); set({ snippets }) },
    }),
    { name: 'loom2.generate', partialize: (s) => ({ panel: s.panel, show: s.show }) as never,
      // a panel persisted before a field existed gets that field's default (new engine options, 2026-10-06)
      merge: (persisted, current) => { const p = (persisted ?? {}) as Partial<GenerateState>; return { ...current, ...p, panel: { ...DEFAULT_PANEL, ...(p.panel ?? {}) } } } },
  ),
)

function schedulePreview(get: () => GenerateState) {
  if (previewTimer) window.clearTimeout(previewTimer)
  previewTimer = window.setTimeout(() => { previewTimer = null; void get().refreshPreview() }, 250)
}
