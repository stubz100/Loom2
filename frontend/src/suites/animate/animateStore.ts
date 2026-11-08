// Animate suite state (11): the Panel (inputs, model, length, presets), the live preview from /recipes/preview, the
// clip list, the player (frame, playing, in/out, onion, compare) and the verbs other suites call (set start / end,
// open a clip). Clips arrive through `clip.ready` events (06 §7).
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ApiError, http, unwrap } from '../../api/client'
import { isI2VPreview, type Asset, type Clip, type ClipReadyData, type ClipUpdatedData, type I2VPreview, type I2VRecipe, type JobOrigin } from '../../api/types'
import { byOrder, resolveModel } from '../../store/modelCaps'
import { FOR_SHOT, forLabel, originFor, useMakeFor } from '../../store/origin'
import { useSession } from '../../store/session'
import { DEV_HOOKS } from '../../devHooks'
import { registerTransport } from './transport'
import { navigate } from '../../frame/router'

/** The presets the server's I2V recipe takes (D38: the generated type, so a spec's own preset key reaches the panel — review K85). */
export type AnimPreset = NonNullable<I2VRecipe['preset']>
/** D156 (E41): the camera's move on the camera model — the core's WanCameraEmbedding paths; `static` holds it. */
export type CameraMove = 'static' | 'pan_left' | 'pan_right' | 'pan_up' | 'pan_down' | 'zoom_in' | 'zoom_out' | 'roll_cw' | 'roll_ccw'
export interface CameraMoveSpec { move: CameraMove; speed: number }
export const CAMERA_MOVES: [CameraMove, string][] = [['static', 'Static (held)'], ['pan_left', 'Pan left'], ['pan_right', 'Pan right'], ['pan_up', 'Pan up'], ['pan_down', 'Pan down'],
  ['zoom_in', 'Zoom in'], ['zoom_out', 'Zoom out'], ['roll_cw', 'Roll clockwise'], ['roll_ccw', 'Roll counter-clockwise']]
export const DEFAULT_CAMERA: CameraMoveSpec = { move: 'static', speed: 1 }
export interface Beat { frame: number; asset_id: string; strength: number }
export interface AnimPanel {
  start: string | null; end: string | null; prompt: string; negative: string; use_negative: boolean
  model_id: string; preset: AnimPreset; steps: number | null; cfg: number | null; shift: number | null
  tier: 'draft' | 'hd' | 'custom'; orientation: 'landscape' | 'portrait' | 'square'; width: number; height: number; frames: number; fps: number
  seed_mode: 'random' | 'fixed' | 'increment'; seed: number; count: number
  beats: Beat[]
  camera: CameraMoveSpec | null                      // D156: the camera model's move; null = the panel never set one (static on that model)
}
export type AnimPreview = I2VPreview                       // D38: the server's i2v preview reply
export interface AnimPresetSaved { name: string; panel: AnimPanel; saved_at: string }
export type AnimView = 'player' | 'compare' | 'windows'                // D99 (UX0 #14): the filmstrip is a track of the timeline (`filmTrack`), not a view; D165: the windows

/** 04 §9a / 11 §3c: native fps, Draft frame count, tier sizes, the frame rule and keyframe beats of a video model (the server snaps anyway). */
export interface ModelRules {
  fps: number; frames: number; step: number; mult: number; draft: [number, number]; hd: [number, number]; portrait: [number, number]; square: [number, number]; short: string; beats: boolean; camera: boolean
  base: number                     // D193: frames = base + step·n (Wan / LTX 1, H3 5)
  fpsFixed: boolean                // D193: the clip runs at `fps` whatever the panel says (H3 makes its sound at 24)
  maxPx: number | null             // D193: no larger size runs (H3: 1024×576)
  sound: boolean                   // D193: the model makes the clip's sound
  negative: boolean                // D193: the graph takes a negative (H3 none)
  presets: AnimPreset[]            // D193: the presets this model has (H3: Draft only)
}
export const MOTION_CHIPS = ['slow push-in', 'orbit left', 'handheld camera', 'wind in hair', 'turns to camera', 'walks left to right', 'camera holds still', 'rain keeps falling', 'looks down, then back up', 'subtle breathing']
export const DEFAULT_PANEL: AnimPanel = {
  start: null, end: null, prompt: '', negative: '', use_negative: false,
  model_id: '', preset: 'draft', steps: null, cfg: null, shift: null,
  tier: 'draft', orientation: 'landscape', width: 832, height: 480, frames: 81, fps: 16, seed_mode: 'random', seed: 1, count: 1, beats: [], camera: null,
}

/** Before the capabilities arrive: the panel's own defaults, no beats (the server snaps and checks anyway). */
const NEUTRAL: ModelRules = { fps: 16, frames: 81, step: 4, mult: 16, draft: [832, 480], hd: [1280, 720], portrait: [480, 832], square: [640, 640], short: '', beats: false, camera: false,
  base: 1, fpsFixed: false, maxPx: null, sound: false, negative: true, presets: ['draft', 'motion', 'quality'] }
const PRESET_ORDER: AnimPreset[] = ['draft', 'motion', 'quality']
/** The model's presets: the named order first, then (review K85) any other key its spec has, in the spec's order. */
const presetsOf = (spec: Record<string, unknown> | undefined): AnimPreset[] => {
  const keys = Object.keys(spec ?? {}).filter((k) => spec![k] != null) as AnimPreset[]
  return [...PRESET_ORDER.filter((k) => keys.includes(k)), ...keys.filter((k) => !PRESET_ORDER.includes(k))]
}

/** C25 / D65: a video model's rules from `/capabilities.i2v.models[id]` (its spec's geometry); a neutral fallback before they load. */
export function modelRules(id: string): ModelRules {
  const caps = useSession.getState().capabilities?.i2v
  const m = caps?.models[id]
  if (!m) return { ...NEUTRAL, short: id }
  const t = m.geometry?.tiers ?? {}
  const pair = (v: number[] | undefined, fallback: [number, number]): [number, number] => (v && v.length === 2 ? [v[0], v[1]] : fallback)
  const draft = pair(t.draft ?? caps?.tiers.draft?.[m.family] ?? m.size, NEUTRAL.draft)
  const presets = presetsOf(m.presets)
  return { fps: m.fps, frames: m.frames, step: m.frame_step, mult: m.size_mult, short: m.short, beats: !!(m.recipes?.beats ?? m.beats), camera: !!m.recipes?.camera, draft,
    hd: pair(t.hd ?? caps?.tiers.hd?.[m.family], draft), portrait: pair(t.portrait ?? caps?.portrait?.[m.family], [draft[1], draft[0]]), square: pair(t.square ?? caps?.square?.[m.family], NEUTRAL.square),
    base: m.geometry?.frame_base ?? 1, fpsFixed: !!m.geometry?.fps_fixed, maxPx: m.geometry?.max_px ?? null, sound: !!m.sound, negative: m.takes_negative !== false,
    presets: presets.length ? presets : NEUTRAL.presets }
}

/** D193: the smallest frame count on the model's grid (base + step·n) the panel offers — 9 for Wan / LTX, 22 for H3. Review K85: a step of
 *  0 or none (a spec without one) is no grid — the loop that walked it never ended. */
export function frameMin(r: { base: number; step: number | null | undefined }): number {
  const step = Number(r.step), base = Number(r.base) || 1
  if (!(step > 0)) return Math.max(9, base)
  return base + Math.max(0, Math.ceil((9 - base) / step)) * step
}

/** D65: the panel's model, or the variant's i2v default while it holds none (or one this build does not offer). */
export function panelModel(id: string): string {
  return resolveModel(id, 'i2v', (x) => !!useSession.getState().capabilities?.i2v?.models[x])
}

/** The video models in the server's order. */
export const videoModels = () => byOrder(useSession.getState().capabilities?.i2v?.models)

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
  const model_id = panelModel(p.model_id)
  const r = modelRules(model_id)                                               // review K85: once per recipe
  const s = seeds ?? (p.seed_mode === 'random' ? Array.from({ length: p.count }, () => 0) : p.seed_mode === 'fixed' ? Array.from({ length: p.count }, () => p.seed) : Array.from({ length: p.count }, (_, i) => p.seed + i))
  return {
    kind: 'i2v', model_id, start_asset: p.start, end_asset: p.end || null, prompt_text: p.prompt, negative: p.use_negative && r.negative ? p.negative : null,
    frames: p.frames, fps: p.fps, width: p.width, height: p.height, preset: p.preset, steps: p.steps, cfg: p.cfg, shift: p.shift,
    beats: r.beats ? p.beats : [], seeds: s,
    camera: r.camera ? (p.camera ?? DEFAULT_CAMERA) : null,      // D156: the camera model always runs a move (static by default); the plain one never
  }
}

/** Try the other model (review K71): a clip's recipe on another model — that model's frames, rate and Draft size, a camera move only when it
 *  takes one (a Fun-Camera clip's move on plain Wan failed every time), a preset it has, its negative only where it takes one, the preset's
 *  own steps / CFG / shift (as picking the model in the panel does), no beats, a new seed. */
export function otherRecipe(base: Record<string, unknown>, other: string): Record<string, unknown> {
  const r = modelRules(other)
  const preset = r.presets.includes(base.preset as AnimPreset) ? base.preset : r.presets[0]
  return { ...base, model_id: other, fps: r.fps, frames: r.frames, width: r.draft[0], height: r.draft[1], beats: [], seeds: [0], preset, steps: null, cfg: null, shift: null,
    negative: r.negative ? (base.negative ?? null) : null, camera: r.camera ? (base.camera ?? DEFAULT_CAMERA) : null }
}

/** Review K85: the panel's model is gone from the capabilities (H3 after its licence was unticked) or was never set — the variant's i2v
 *  default with that model's own values (`setModel`), so a submission never sends the default model with another model's frames and size. */
export function settleModel(): void {
  const caps = useSession.getState().capabilities
  const models = caps?.i2v?.models
  if (!models || models[useAnimate.getState().panel.model_id]) return
  const def = caps?.defaults?.i2v
  const next = (def && models[def] ? def : '') || byOrder(models)[0]?.[0]
  if (next) useAnimate.getState().setModel(next)
}

/** D90 (02 §9, X12): the Clips tab's filter — words of the prompt (D122: no keep / reject state). */
export interface ClipFilter { q: string }
/** The clips the Clips tab lists: trashed ones hidden once the live set is known (`live`: the asset ids of the clips not in the Trash),
 *  then the filter. */
export function visibleClips(clips: Clip[], live: Record<string, true> | null, f: ClipFilter): Clip[] {
  const words = f.q.trim().toLowerCase().split(/\s+/).filter(Boolean)
  return clips.filter((c) => {
    if (live && c.asset_id && !live[c.asset_id]) return false
    const text = `${c.prompt} ${c.model_id} seed ${c.seed}`.toLowerCase()
    return words.every((w) => text.includes(w))
  })
}

export const fmtTime = (frame: number, fps: number): string => { const s = frame / Math.max(1, fps); const m = Math.floor(s / 60); return `${String(m).padStart(2, '0')}:${(s - m * 60).toFixed(2).padStart(5, '0')}` }

interface AnimateState {
  panel: AnimPanel; presets: AnimPresetSaved[]; lastPreset: string | null
  /** Review K95: the project the panel's start, end and beats (asset ids) belong to — another project's open drops them. */
  panelProject: string | null
  preview: AnimPreview | null; previewError: string | null
  clips: Clip[]; current: string | null; assets: Record<string, Asset>; pins: Record<string, { frame: number; asset_id: string }[]>
  view: AnimView; filmTrack: boolean; compareWith: string | null; playing: boolean; frame: number; speed: number; loop: boolean; onion: boolean
  inPoint: number | null; outPoint: number | null; extractEvery: number; busy: string | null
  /** D90 (02 §9): the asset ids of the clips not in the Trash (null until asked), and the Clips tab's filter. */
  clipLive: Record<string, true> | null; clipFilter: ClipFilter
  loadClipStates: () => Promise<void>
  setClipFilter: (patch: Partial<ClipFilter>) => void
  /** The Catalogue's trash semantics (C, D90 B5): the clip's asset goes to the Trash, the toast offers Undo; Empty trash deletes the clip. */
  trashClip: (id?: string | null) => Promise<void>
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
  /** D95 (AN1, UX0 #11): the saved panels are a project record (`/project/animate-presets`); presets this browser still holds from before
   *  are moved into the project once (the first load that finds the project's list empty). */
  loadPresets: () => Promise<void>
  savePreset: (name: string) => void
  applyPreset: (name: string) => void
  deletePreset: (name: string) => void
}

/** Write the saved panels to the project (the server drops the frames). A failure is said; the list stays as it is on screen. */
async function putPresets(presets: { name: string; panel: AnimPanel; saved_at: string }[], last: string | null): Promise<void> {
  try { await unwrap(http.PUT('/project/animate-presets', { body: { presets: presets.map((p) => ({ name: p.name, panel: p.panel, saved_at: p.saved_at })), last } as never })) }
  catch (e) { useSession.getState().toast(`Saving the Animate presets failed: ${(e as ApiError).detail ?? e}`, 'error') }
}

let previewTimer: ReturnType<typeof setTimeout> | null = null
let previewSeq = 0
/** Review K68: the presets this browser kept before D95, read once from the persisted copy at start (never the in-memory list — that is the
 *  open project's: opening B after A wrote A's presets into B) and moved into the first project whose list is empty. */
let legacyPresets: { presets: AnimPresetSaved[]; last: string | null } | null = null
let presetsSeq = 0

/** D66: an Animate submission names the clip on screen when it was made (null: none), so a finished clip knows which view it belongs to. */
const clipOrigin = (ref: string | null): JobOrigin => originFor('animate', { suite: 'animate', surface: 'clip', ref })   // D90 (02 §5): or the For chip's shot
/** The toast's tail when a submission is made for a shot (the For chip). */
const forTail = (o: JobOrigin): string => { const f = o.surface === FOR_SHOT ? useMakeFor.getState().animate : null; return f ? ` for ${forLabel(f)} — they land as its takes` : '' }
/** The last automatic switch: from the clip a job was started on to the clip it produced (a batch of clips plays through in turn). */
let followed: { from: string | null; to: string } | null = null

export const useAnimate = create<AnimateState>()(
  persist(
    (set, get) => ({
      panel: DEFAULT_PANEL, presets: [], lastPreset: null, panelProject: null, preview: null, previewError: null,
      clips: [], current: null, assets: {}, pins: {},
      view: 'player', filmTrack: false, compareWith: null, playing: false, frame: 0, speed: 1, loop: true, onion: false, inPoint: null, outPoint: null, extractEvery: 8, busy: null,
      clipLive: null, clipFilter: { q: '' },

      set: (patch) => { set({ panel: { ...get().panel, ...patch } }); get().refreshPreview() },
      setModel: (model_id) => {
        const p = get().panel
        if (!useSession.getState().capabilities?.i2v?.models[model_id]) return
        const r = modelRules(model_id)
        const [width, height] = sizeFor(model_id, p.tier, p.orientation, [p.width, p.height])
        const preset = r.presets.includes(p.preset) ? p.preset : r.presets[0]          // D193: H3 has Draft only
        get().set({ model_id, preset, fps: r.fps, frames: r.frames, width, height, steps: null, cfg: null, shift: null })
      },
      setTier: (tier, orientation) => {
        const p = get().panel
        const o = orientation ?? p.orientation
        const [width, height] = sizeFor(p.model_id, tier, o, [p.width, p.height])
        get().set({ tier, orientation: o, width, height })
      },
      setStart: (id, goTo = false) => {
        get().set({ start: id })
        if (goTo) navigate({ suite: 'animate' })
        if (id) void get().loadAsset(id)
      },
      setEnd: (id, goTo = false) => {
        get().set({ end: id })
        if (goTo) navigate({ suite: 'animate' })
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
          const was = get().current
          const cur = was && clips.some((c) => c.id === was) ? was : clips[0]?.id ?? null
          set({ clips })
          // review K116: a clip landing as the current one is selected (its frames, its stills, its harvested pins) — the check ran after
          // `current` was already set, so it never did
          if (cur !== was) get().select(cur)
          for (const c of clips.slice(0, 12)) if (c.asset_id) void get().loadAsset(c.asset_id)
          void get().loadClipStates()
        } catch { /* no project */ }
      },
      loadClipStates: async () => {
        try {
          const r = await unwrap(http.GET('/assets', { params: { query: { folder: 'clips', limit: 2000 } } }))          // videos not in the Trash, with their state
          set({ assets: { ...get().assets, ...Object.fromEntries(r.items.map((a) => [a.id, a])) }, clipLive: Object.fromEntries(r.items.map((a) => [a.id, true as const])) })
        } catch { /* the list shows every clip */ }
      },
      setClipFilter: (patch) => set({ clipFilter: { ...get().clipFilter, ...patch } }),
      trashClip: async (id) => {
        const c = get().clips.find((x) => x.id === (id ?? get().current))
        const s = useSession.getState()
        if (!c?.asset_id) return
        const aid = c.asset_id
        try {
          await unwrap(http.POST('/assets/trash', { body: { ids: [aid] } }))
          const live = { ...(get().clipLive ?? {}) }; delete live[aid]
          set({ clipLive: get().clipLive ? live : null })
          if (get().current === c.id) { const next = visibleClips(get().clips, get().clipLive, get().clipFilter)[0]; get().select(next?.id ?? null) }
          s.toast('Clip moved to Trash', 'info', () => void unwrap(http.POST('/assets/restore', { body: { ids: [aid] } })).then(() => get().loadClipStates()))
        } catch (e) { s.toast(`Could not trash the clip: ${(e as ApiError).detail ?? e}`, 'error') }
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
      // D66 — the player switches to a new clip only when the clip belongs to the view on screen:
      //   · Animate is the active suite, and
      //   · the job was started in Animate (`origin.suite === 'animate'`) from the clip still shown (`origin.ref`, null = no clip shown),
      //     or the player is on the clip this rule last switched to from that same clip (the next clip of a batch follows on).
      // Anything else — the user went to another suite or opened another clip, or the job came from elsewhere — leaves the player alone
      // and toasts "Play". A clip without an origin (its job was queued before D66) follows whenever Animate is on screen, as before.
      onClipReady: (d) => {
        void unwrap(http.GET('/clips')).then((r) => {
          set({ clips: r.items })
          const s = useSession.getState()
          const o = d.origin ?? null
          const from = o?.ref ?? null
          const cur = get().current
          const onScreen = s.ui.suite === 'animate' && (!o || (o.suite === 'animate' && (from === cur || (followed?.from === from && followed.to === cur))))
          if (onScreen) {
            followed = { from, to: d.clip_id }
            get().select(d.clip_id)
            s.toast('Clip ready — playing at Performance', 'success')
            return
          }
          const c = r.items.find((x) => x.id === d.clip_id)
          s.toast(`Clip ready${c ? ` — seed ${c.seed}` : ''}`, 'success', { label: 'Play', run: () => {
            navigate({ suite: 'animate' }); get().select(d.clip_id); get().togglePlay(true)
          } })
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
        if (!p.start) { s.toast('Set a start frame first (drop a picture from the Bin on the slot, or Set as the start frame in its right-click menu)', 'info'); return }
        if (get().preview?.missing.length) { s.toast(`Weights missing: ${get().preview!.missing.map((m) => m.model_id).join(', ')} — fetch them in Models`, 'error'); return }
        try {
          const origin = clipOrigin(get().current)
          const r = await unwrap(http.POST('/jobs', { body: { recipe: recipeFor({ ...p, start: p.start }), stage, origin } }))
          const n = r.jobs.length
          s.toast((stage ? `${n} clip${n > 1 ? 's' : ''} queued for later — Run now in the Dock` : `Animating ${n} clip${n > 1 ? 's' : ''} — ≈ ${Math.round((get().preview?.estimate.seconds ?? 300) / 60)} min each`) + forTail(origin), 'success')
          if (p.seed_mode === 'increment') get().set({ seed: p.seed + n })
        } catch (e) { s.toast(`Animate failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },
      variations: async () => {
        const c = get().clip()
        if (!c) return
        const recipe = { ...(c.params.recipe as Record<string, unknown>), seeds: Array.from({ length: Math.max(1, get().panel.count) }, () => 0) }
        try { await unwrap(http.POST('/jobs', { body: { recipe, stage: false, origin: clipOrigin(c.id) } })); useSession.getState().toast('Variations queued (new seeds)', 'success') } catch (e) { useSession.getState().toast(`Variations failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },
      rerun: async () => {
        const c = get().clip()
        if (!c) return
        const recipe = { ...(c.params.recipe as Record<string, unknown>), seeds: [c.seed] }
        try { await unwrap(http.POST('/jobs', { body: { recipe, stage: false, origin: clipOrigin(c.id) } })); useSession.getState().toast(`Re-running seed ${c.seed}`, 'success') } catch (e) { useSession.getState().toast(`Re-run failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },
      tryOther: async () => {
        const c = get().clip()
        if (!c) return
        const other = videoModels().find(([id]) => id !== c.model_id)?.[0]
        if (!other) { useSession.getState().toast('No other video model is offered in this build', 'info'); return }
        const r = modelRules(other)
        const recipe = otherRecipe(c.params.recipe as Record<string, unknown>, other)
        try { await unwrap(http.POST('/jobs', { body: { recipe, stage: false, origin: clipOrigin(c.id) } })); useSession.getState().toast(`Trying the same inputs on ${r.short}`, 'success') } catch (e) { useSession.getState().toast(`Try on ${r.short} failed: ${(e as ApiError).detail ?? e}`, 'error') }
      },

      setView: (view) => set({ view }),
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
          useSession.getState().toast(`${r.items.length} frame${r.items.length > 1 ? 's' : ''} extracted to the Bin`, 'success')
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
      loadPresets: async () => {
        const n = ++presetsSeq
        const path = useSession.getState().project?.path ?? null
        const saved = (p: { name: string; panel: unknown; saved_at: string }): AnimPresetSaved =>
          ({ name: p.name, panel: { ...DEFAULT_PANEL, ...(p.panel as Partial<AnimPanel>), start: null, end: null, beats: [] }, saved_at: p.saved_at })
        try {
          const r = await unwrap(http.GET('/project/animate-presets'))
          if (n !== presetsSeq || (useSession.getState().project?.path ?? null) !== path) return      // review K68: another project opened meanwhile
          const legacy = legacyPresets
          if (!r.presets.length && legacy?.presets.length) {                             // this browser's presets from before D95: into the project, once
            legacyPresets = null
            const moved = legacy.presets.map(saved)
            await putPresets(moved, legacy.last)
            set({ presets: moved, lastPreset: legacy.last })
            useSession.getState().toast(`${moved.length} Animate preset${moved.length === 1 ? '' : 's'} moved from this browser into the project`, 'info')
            return
          }
          set({ presets: r.presets.map(saved), lastPreset: r.last ?? null })
        } catch { if (n === presetsSeq) set({ presets: [], lastPreset: null }) }      // no project open: none listed
      },
      savePreset: (name) => {
        set({ presets: [...get().presets.filter((p) => p.name !== name), { name, panel: { ...get().panel, start: null, end: null, beats: [] }, saved_at: new Date().toISOString() }], lastPreset: name })
        void putPresets(get().presets, name)
      },
      applyPreset: (name) => { const p = get().presets.find((x) => x.name === name); if (p) { get().set({ ...p.panel, start: get().panel.start, end: get().panel.end }); set({ lastPreset: name }) } },
      deletePreset: (name) => { set({ presets: get().presets.filter((p) => p.name !== name) }); void putPresets(get().presets, get().lastPreset === name ? null : get().lastPreset) },
    }),
    // D95 (AN1): the presets are the project's now — no longer written to this browser (an older copy is read once and moved, loadPresets)
    { name: 'loom2.animate', partialize: (s) => ({ panel: s.panel, panelProject: s.panelProject, speed: s.speed, loop: s.loop, onion: s.onion, extractEvery: s.extractEvery }) as never,
      // review K68: a copy saved before D95 still holds `presets` — kept aside for the one move (loadPresets), never the open project's list
      merge: (persisted, current) => {
        const { presets, lastPreset, ...rest } = (persisted ?? {}) as Partial<AnimateState>
        if (Array.isArray(presets) && presets.length) legacyPresets = { presets, last: lastPreset ?? null }
        return { ...current, ...rest }
      } },
  ),
)

/** Review K95 / K68: a project opened — the panel's start, end and beats are dropped when they were picked in another project (their asset ids
 *  name nothing here), and the presets listed are emptied until this project's arrive. */
function projectOpened(path: string): void {
  const s = useAnimate.getState()
  const other = s.panelProject !== null && s.panelProject !== path
  useAnimate.setState({ panelProject: path, presets: [], lastPreset: null,
    ...(other ? { panel: { ...s.panel, start: null, end: null, beats: [] } } : {}) })
}
{
  const path = (p: ReturnType<typeof useSession.getState>['project']) => (p?.open && p.path ? p.path : null)
  const now = path(useSession.getState().project)
  if (now && now !== useAnimate.getState().panelProject) projectOpened(now)
  settleModel()
  useSession.subscribe((s, prev) => {
    const p = path(s.project)
    if (p && p !== path(prev.project)) projectOpened(p)
    if (s.capabilities !== prev.capabilities) settleModel()                    // review K85: the panel's model went (H3 unticked) — the default's values
  })
}

if (DEV_HOOKS) (window as unknown as { __loom2Animate?: typeof useAnimate }).__loom2Animate = useAnimate      // dev: the headed check drives the player

// D121 (AW2): the Performance level's transport — the clip's frames, its in / out, its beats and harvested frames as the marks
{
  const s = () => useAnimate.getState()
  registerTransport('animate', {
    ready: () => !!s().clip(), playing: () => s().playing, play: (on) => s().togglePlay(on),
    frame: () => s().frame, seek: (f) => s().setFrame(f), step: (d) => s().step(d),
    home: () => { s().togglePlay(false); s().setFrame(0) }, end: () => { s().togglePlay(false); s().setFrame((s().clip()?.frames ?? 1) - 1) },
    setIn: () => s().setInOut('in'), setOut: () => s().setInOut('out'), clearInOut: () => s().setInOut('clear'), hasInOut: () => s().inPoint !== null || s().outPoint !== null,
    marks: () => { const c = s().clip(); return c ? [...c.beats.map((b) => b.frame), ...(s().pins[c.id] ?? []).map((p) => p.frame)] : [] },
  })
}
