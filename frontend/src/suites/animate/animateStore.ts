// Animate suite state (11): the Panel (inputs, model, length, presets), the live preview from /recipes/preview, the
// clip list, the player (frame, playing, in/out, onion, compare) and the verbs other suites call (set start / end,
// open a clip). Clips arrive through `clip.ready` events (06 §7).
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ApiError, http, unwrap } from '../../api/client'
import { isI2VPreview, type Asset, type Clip, type ClipReadyData, type ClipUpdatedData, type I2VPreview, type I2VRecipe } from '../../api/types'
import { useSession } from '../../store/session'

export type AnimPreset = 'draft' | 'motion' | 'quality'
export interface Beat { frame: number; asset_id: string; strength: number }
export interface AnimPanel {
  start: string | null; end: string | null; prompt: string; negative: string; use_negative: boolean
  model_id: string; preset: AnimPreset; steps: number | null; cfg: number | null; shift: number | null
  tier: 'draft' | 'hd' | 'custom'; orientation: 'landscape' | 'portrait' | 'square'; width: number; height: number; frames: number; fps: number
  seed_mode: 'random' | 'fixed' | 'increment'; seed: number; count: number
  beats: Beat[]
}
export type AnimPreview = I2VPreview                       // D38: the server's i2v preview reply
export interface AnimPresetSaved { name: string; panel: AnimPanel; saved_at: string }
export type AnimView = 'player' | 'filmstrip' | 'compare'

/** 04 §9a / 11 §3c: native fps, Draft frame count, tier sizes and the frame rule per model (the server snaps anyway). */
export const MODEL_RULES: Record<string, { fps: number; frames: number; step: number; mult: number; draft: [number, number]; hd: [number, number]; portrait: [number, number]; square: [number, number]; short: string }> = {
  'wan22-i2v-high-fp8': { fps: 16, frames: 81, step: 4, mult: 16, draft: [832, 480], hd: [1280, 720], portrait: [480, 832], square: [640, 640], short: 'Wan' },
  'ltx23-distilled-fp8': { fps: 24, frames: 121, step: 8, mult: 32, draft: [1024, 576], hd: [1280, 704], portrait: [576, 1024], square: [640, 640], short: 'LTX' },
}
export const MOTION_CHIPS = ['slow push-in', 'orbit left', 'handheld camera', 'wind in hair', 'turns to camera', 'walks left to right', 'camera holds still', 'rain keeps falling', 'looks down, then back up', 'subtle breathing']
export const DEFAULT_PANEL: AnimPanel = {
  start: null, end: null, prompt: '', negative: '', use_negative: false,
  model_id: 'wan22-i2v-high-fp8', preset: 'draft', steps: null, cfg: null, shift: null,
  tier: 'draft', orientation: 'landscape', width: 832, height: 480, frames: 81, fps: 16, seed_mode: 'random', seed: 1, count: 1, beats: [],
}

/** C25: the server's rule for a model once the capabilities are loaded (`I2V_RULES` through `/capabilities.i2v`); the table above is
 * the fallback before that and the source of the short label. */
export function modelRules(id: string): (typeof MODEL_RULES)[string] {
  const base = MODEL_RULES[id] ?? MODEL_RULES['wan22-i2v-high-fp8']
  const caps = useSession.getState().capabilities?.i2v
  const m = caps?.models[id]
  if (!caps || !m) return base
  const fam = m.family
  const pair = (v: number[] | undefined, fallback: [number, number]): [number, number] => (v && v.length === 2 ? [v[0], v[1]] : fallback)
  return { ...base, fps: m.fps, frames: m.frames, step: m.frame_step, mult: m.size_mult, draft: pair(caps.tiers.draft?.[fam], base.draft), hd: pair(caps.tiers.hd?.[fam], base.hd),
    portrait: pair(caps.portrait?.[fam], base.portrait), square: pair(caps.square?.[fam], base.square) }
}

export function sizeFor(model_id: string, tier: AnimPanel['tier'], orientation: AnimPanel['orientation'], current: [number, number]): [number, number] {
  const r = modelRules(model_id)
  if (tier === 'custom') return current
  if (orientation === 'portrait') return tier === 'hd' ? [r.hd[1], r.hd[0]] : r.portrait
  if (orientation === 'square') return r.square
  return r[tier]
}

/** The I2V recipe (11 §10) the server compiles; seeds follow the seed mode (0 = the server picks one). */
/** The I2V recipe for a panel with a start frame (callers check `start` first: Animate asks for one, the preview uses a placeholder). */
export function recipeFor(p: AnimPanel & { start: string }, seeds?: number[]): I2VRecipe {
  const s = seeds ?? (p.seed_mode === 'random' ? Array.from({ length: p.count }, () => 0) : p.seed_mode === 'fixed' ? Array.from({ length: p.count }, () => p.seed) : Array.from({ length: p.count }, (_, i) => p.seed + i))
  return {
    kind: 'i2v', model_id: p.model_id, start_asset: p.start, end_asset: p.end || null, prompt_text: p.prompt, negative: p.use_negative ? p.negative : null,
    frames: p.frames, fps: p.fps, width: p.width, height: p.height, preset: p.preset, steps: p.steps, cfg: p.cfg, shift: p.shift,
    beats: p.model_id === 'ltx23-distilled-fp8' ? p.beats : [], seeds: s,
  }
}

export const fmtTime = (frame: number, fps: number): string => { const s = frame / Math.max(1, fps); const m = Math.floor(s / 60); return `${String(m).padStart(2, '0')}:${(s - m * 60).toFixed(2).padStart(5, '0')}` }

interface AnimateState {
  panel: AnimPanel; presets: AnimPresetSaved[]; lastPreset: string | null
  preview: AnimPreview | null; previewError: string | null
  clips: Clip[]; current: string | null; assets: Record<string, Asset>; pins: Record<string, { frame: number; asset_id: string }[]>
  view: AnimView; compareWith: string | null; playing: boolean; frame: number; speed: number; loop: boolean; onion: boolean
  inPoint: number | null; outPoint: number | null; extractEvery: number; busy: string | null
  set: (patch: Partial<AnimPanel>) => void
  setModel: (model_id: string) => void
  setTier: (tier: AnimPanel['tier'], orientation?: AnimPanel['orientation']) => void
  setStart: (id: string | null, goTo?: boolean) => void
  setEnd: (id: string | null, goTo?: boolean) => void
  swap: () => void
  addBeat: (asset_id: string, frame?: number) => void
  removeBeat: (i: number) => void
  refreshPreview: () => void
  loadClips: () => Promise<void>
  select: (id: string | null) => void
  onClipReady: (d: ClipReadyData) => void
  onClipUpdated: (d: ClipUpdatedData) => void
  measureIdentity: () => Promise<void>
  loadAsset: (id: string) => Promise<Asset | undefined>
  clip: () => Clip | undefined
  animate: (stage: boolean) => Promise<void>
  variations: () => Promise<void>
  rerun: () => Promise<void>
  tryOther: () => Promise<void>
  setView: (v: AnimView) => void
  setFrame: (n: number) => void
  step: (d: number) => void
  togglePlay: (on?: boolean) => void
  setInOut: (which: 'in' | 'out' | 'clear') => void
  range: () => [number, number]
  extract: (frames: number[]) => Promise<Asset[]>
  extractRange: () => Promise<Asset[]>
  sendFrameToEdit: () => Promise<void>
  useFrameAsStart: () => Promise<void>
  setState: (state: 'keep' | 'reject' | 'none') => Promise<void>
  savePreset: (name: string) => void
  applyPreset: (name: string) => void
  deletePreset: (name: string) => void
}

let previewTimer: ReturnType<typeof setTimeout> | null = null
let previewSeq = 0

export const useAnimate = create<AnimateState>()(
  persist(
    (set, get) => ({
      panel: DEFAULT_PANEL, presets: [], lastPreset: null, preview: null, previewError: null,
      clips: [], current: null, assets: {}, pins: {},
      view: 'player', compareWith: null, playing: false, frame: 0, speed: 1, loop: true, onion: false, inPoint: null, outPoint: null, extractEvery: 8, busy: null,

      set: (patch) => { set({ panel: { ...get().panel, ...patch } }); get().refreshPreview() },
      setModel: (model_id) => {
        const p = get().panel
        if (!MODEL_RULES[model_id] && !useSession.getState().capabilities?.i2v?.models[model_id]) return
        const r = modelRules(model_id)
        const [width, height] = sizeFor(model_id, p.tier, p.orientation, [p.width, p.height])
        get().set({ model_id, fps: r.fps, frames: r.frames, width, height, steps: null, cfg: null, shift: null })
      },
      setTier: (tier, orientation) => {
        const p = get().panel
        const o = orientation ?? p.orientation
        const [width, height] = sizeFor(p.model_id, tier, o, [p.width, p.height])
        get().set({ tier, orientation: o, width, height })
      },
      setStart: (id, goTo = false) => {
        get().set({ start: id })
        if (goTo) useSession.getState().setSuite('animate')
        if (id) void get().loadAsset(id)
      },
      setEnd: (id, goTo = false) => {
        get().set({ end: id })
        if (goTo) useSession.getState().setSuite('animate')
        if (id) void get().loadAsset(id)
      },
      swap: () => { const p = get().panel; if (p.end) get().set({ start: p.end, end: p.start }) },
      addBeat: (asset_id, frame) => {
        const p = get().panel
        const f = frame ?? Math.round(p.frames / 2)
        get().set({ beats: [...p.beats.filter((b) => b.frame !== f), { frame: Math.min(p.frames - 1, Math.max(1, f)), asset_id, strength: 0.6 }].sort((a, b) => a.frame - b.frame) })
        void get().loadAsset(asset_id)
      },
      removeBeat: (i) => get().set({ beats: get().panel.beats.filter((_, k) => k !== i) }),

      refreshPreview: () => {
        if (previewTimer) clearTimeout(previewTimer)
        previewTimer = setTimeout(() => {
          const p = get().panel
          const seq = ++previewSeq
          const body = recipeFor({ ...p, start: p.start ?? 'ast_pending' })
          void unwrap(http.POST('/recipes/preview', { body: { recipe: body } }))
            .then((pv) => { if (seq === previewSeq) set({ preview: isI2VPreview(pv) ? pv : null, previewError: null }) })
            .catch((e: ApiError) => { if (seq === previewSeq) set({ preview: null, previewError: e.detail ?? String(e) }) })
        }, 250)
      },

      loadClips: async () => {
        try {
          const r = await unwrap(http.GET('/clips'))
          const clips = r.items
          const cur = get().current && clips.some((c) => c.id === get().current) ? get().current : clips[0]?.id ?? null
          set({ clips, current: cur })
          if (cur && cur !== get().current) get().select(cur)
          for (const c of clips.slice(0, 12)) if (c.asset_id) void get().loadAsset(c.asset_id)
        } catch { /* no project */ }
      },
      select: (id) => {
        const c = get().clips.find((x) => x.id === id)
        set({ current: id, frame: 0, playing: false, inPoint: null, outPoint: null, compareWith: get().compareWith === id ? null : get().compareWith })
        if (c) {
          if (c.asset_id) void get().loadAsset(c.asset_id)
          void get().loadAsset(c.start_asset_id); if (c.end_asset_id) void get().loadAsset(c.end_asset_id)
          // pins: the frame index of every harvested frame (≤ 64 per clip)
          void Promise.all(c.extracted_asset_ids.map((aid) => get().loadAsset(aid))).then((as) => {
            const pins = as.filter((a): a is Asset => !!a).map((a) => ({ frame: Number((a.params as { frame_index?: number }).frame_index ?? -1), asset_id: a.id })).filter((p) => p.frame >= 0)
            set({ pins: { ...get().pins, [c.id]: pins } })
          })
        }
      },
      onClipReady: (d) => {
        void unwrap(http.GET('/clips')).then((r) => {
          set({ clips: r.items })
          get().select(d.clip_id)
          useSession.getState().toast('Clip ready — playing in Animate', 'success')
        }).catch(() => undefined)
      },
      onClipUpdated: (d) => set({ clips: get().clips.map((c) => c.id === d.clip_id ? { ...c, identity: d.identity ?? c.identity } : c) }),
      measureIdentity: async () => {
        const c = get().clip()
        if (!c) return
        set({ busy: 'measuring identity' })
        try { const r = await unwrap(http.POST('/clips/{clip_id}/identity', { params: { path: { clip_id: c.id } } })); set({ clips: get().clips.map((x) => x.id === r.id ? r : x) }) }
        catch (e) { useSession.getState().toast(`FaceSim failed: ${(e as ApiError).detail ?? e}`, 'error') } finally { set({ busy: null }) }
      },
      loadAsset: async (id) => {
        const have = get().assets[id]
        if (have) return have
        try { const a = await unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id: id } } })); set({ assets: { ...get().assets, [id]: a } }); return a } catch { return undefined }
      },
      clip: () => get().clips.find((c) => c.id === get().current),

      animate: async (stage) => {
        const p = get().panel
        const s = useSession.getState()
        if (!p.start) { s.toast('Set a start frame first (drop a Catalogue tile on the slot, or Shift+A in the Catalogue)', 'info'); return }
        if (get().preview?.missing.length) { s.toast(`Weights missing: ${get().preview!.missing.map((m) => m.model_id).join(', ')} — fetch them in Models`, 'error'); return }
        try {
          const r = await unwrap(http.POST('/jobs', { body: { recipe: recipeFor({ ...p, start: p.start }), stage } }))
          const n = r.jobs.length
          s.toast(stage ? `${n} clip${n > 1 ? 's' : ''} staged` : `Animating ${n} clip${n > 1 ? 's' : ''} — ≈ ${Math.round((get().preview?.estimate.seconds ?? 300) / 60)} min each`, 'success')
          if (p.seed_mode === 'increment') get().set({ seed: p.seed + n })
        } catch (e) { s.toast(`Animate failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },
      variations: async () => {
        const c = get().clip()
        if (!c) return
        const recipe = { ...(c.params.recipe as Record<string, unknown>), seeds: Array.from({ length: Math.max(1, get().panel.count) }, () => 0) }
        try { await unwrap(http.POST('/jobs', { body: { recipe, stage: false } })); useSession.getState().toast('Variations queued (new seeds)', 'success') } catch (e) { useSession.getState().toast(`Variations failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },
      rerun: async () => {
        const c = get().clip()
        if (!c) return
        const recipe = { ...(c.params.recipe as Record<string, unknown>), seeds: [c.seed] }
        try { await unwrap(http.POST('/jobs', { body: { recipe, stage: false } })); useSession.getState().toast(`Re-running seed ${c.seed}`, 'success') } catch (e) { useSession.getState().toast(`Re-run failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },
      tryOther: async () => {
        const c = get().clip()
        if (!c) return
        const other = c.model_id === 'wan22-i2v-high-fp8' ? 'ltx23-distilled-fp8' : 'wan22-i2v-high-fp8'
        const r = modelRules(other)
        const base = c.params.recipe as Record<string, unknown>
        const recipe = { ...base, model_id: other, fps: r.fps, frames: r.frames, width: r.draft[0], height: r.draft[1], beats: [], seeds: [0] }
        try { await unwrap(http.POST('/jobs', { body: { recipe, stage: false } })); useSession.getState().toast(`Trying the same inputs on ${r.short}`, 'success') } catch (e) { useSession.getState().toast(`Try on ${r.short} failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },

      setView: (view) => set({ view, playing: view === 'filmstrip' ? false : get().playing }),
      setFrame: (n) => { const c = get().clip(); const max = c ? c.frames - 1 : 0; set({ frame: Math.max(0, Math.min(max, Math.round(n))) }) },
      step: (d) => { get().togglePlay(false); get().setFrame(get().frame + d) },
      togglePlay: (on) => { const c = get().clip(); if (!c) return; const next = on ?? !get().playing; if (next && get().frame >= get().range()[1]) set({ frame: get().range()[0] }); set({ playing: next }) },
      setInOut: (which) => {
        if (which === 'clear') { set({ inPoint: null, outPoint: null }); return }
        const f = get().frame
        if (which === 'in') set({ inPoint: f, outPoint: get().outPoint !== null && get().outPoint! < f ? null : get().outPoint })
        else set({ outPoint: f, inPoint: get().inPoint !== null && get().inPoint! > f ? null : get().inPoint })
      },
      range: () => { const c = get().clip(); const n = c ? c.frames : 1; return [get().inPoint ?? 0, get().outPoint ?? n - 1] },

      extract: async (frames) => {
        const c = get().clip()
        if (!c) return []
        set({ busy: 'extracting' })
        try {
          const r = await unwrap(http.POST('/clips/{clip_id}/extract', { params: { path: { clip_id: c.id } }, body: { frames } }))
          set({ clips: get().clips.map((x) => x.id === c.id ? r.clip : x), assets: { ...get().assets, ...Object.fromEntries(r.items.map((a) => [a.id, a])) } })
          const pins = [...(get().pins[c.id] ?? []), ...r.items.map((a) => ({ frame: Number((a.params as { frame_index?: number }).frame_index ?? -1), asset_id: a.id }))]
          set({ pins: { ...get().pins, [c.id]: pins } })
          useSession.getState().toast(`${r.items.length} frame${r.items.length > 1 ? 's' : ''} extracted to the Catalogue`, 'success')
          return r.items
        } catch (e) { useSession.getState().toast(`Extract failed: ${(e as ApiError).detail ?? e}`, 'error'); return [] } finally { set({ busy: null }) }
      },
      extractRange: async () => {
        const [a, b] = get().range()
        const k = Math.max(1, get().extractEvery)
        const frames: number[] = []
        for (let f = a; f <= b && frames.length < 24; f += k) frames.push(f)
        return get().extract(frames)
      },
      sendFrameToEdit: async () => {
        const [a] = await get().extract([get().frame])
        if (a) void import('../edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(a.id))
      },
      useFrameAsStart: async () => {
        const [a] = await get().extract([get().frame])
        if (a) { get().setStart(a.id); useSession.getState().toast('The frame is the next clip\'s start (Extend, by hand)', 'info') }
      },
      setState: async (state) => {
        const c = get().clip()
        if (!c?.asset_id) return
        try { const a = await unwrap(http.PATCH('/assets/{asset_id}', { params: { path: { asset_id: c.asset_id } }, body: { state } })); set({ assets: { ...get().assets, [a.id]: a } }) } catch (e) { useSession.getState().toast(`Could not mark the clip: ${(e as ApiError).detail ?? e}`, 'error') }
      },

      savePreset: (name) => set({ presets: [...get().presets.filter((p) => p.name !== name), { name, panel: { ...get().panel, start: null, end: null, beats: [] }, saved_at: new Date().toISOString() }], lastPreset: name }),
      applyPreset: (name) => { const p = get().presets.find((x) => x.name === name); if (p) { get().set({ ...p.panel, start: get().panel.start, end: get().panel.end }); set({ lastPreset: name }) } },
      deletePreset: (name) => set({ presets: get().presets.filter((p) => p.name !== name) }),
    }),
    { name: 'loom2.animate', partialize: (s) => ({ panel: s.panel, presets: s.presets, lastPreset: s.lastPreset, speed: s.speed, loop: s.loop, onion: s.onion, extractEvery: s.extractEvery }) as never },
  ),
)

if (import.meta.env.DEV) (window as unknown as { __loom2Animate?: typeof useAnimate }).__loom2Animate = useAnimate      // dev: the headed check drives the player
