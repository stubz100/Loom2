// D111 (PS5a, proto01_animate 16): *Make the final shot* — the finished scene split into layers. One layer per entity (the plate, each
// visible figure, each visible prop or 3D model, the shadows); Stage renders each layer's passes at the shot's rate through the active
// camera (the plate: the bare set's depth and lit clay; a figure alone with the set: its pose and depth; a prop alone with the set: its
// beauty and depth; the shadows: everything, lit) and uploads them (each frame once, by its hash) into a final record on the server.
// The later steps make each layer's own frames and the assembly from these.
import { create } from 'zustand'
import { api, http, sha256Hex, unwrap, type ApiError } from '../../api/client'
import type { Composition, Final, StageDoc, StageObject } from '../../api/types'
import { useComposition } from '../animate/compositionStore'
import { askConfirm, useSession } from '../../store/session'
import { sampleDoc } from './anim'
import { st, type SequenceRenderer } from './stageStore'

export type Rate = 16 | 24
export interface PlanLayer { id: string; kind: 'plate' | 'figure' | 'prop' | 'shadows'; name: string; object_id: string | null; profile_id: string | null; version: string | null }
export interface FinalPlan { times: number[]; layers: PlanLayer[] }

/** The Stage times (24 fps frames) a final samples: every frame at F24, every 1.5th at F16 (D102; finals.py frames_at). */
export function framesAt(start: number, end: number, rate: Rate): number[] {
  if (end < start) return []
  const step = 24 / rate
  const n = Math.floor((end - start) / step + 1e-6) + 1
  return Array.from({ length: n }, (_, i) => Math.round((start + i * step) * 1e4) / 1e4)
}

/** finals.py plan_batches: a performance's 77-frame batches, carrying 5 (72 new each after the first). */
export const batchCount = (n: number): number => (n <= 77 ? 1 : 1 + Math.ceil((n - 77) / 72))

const isActor = (o: StageObject) => o.visible && (o.kind === 'mannequin' || o.kind === 'mesh' || o.kind === 'prop' || o.kind === 'plane')

/** The layers of a scene: the plate (the sets), each visible figure, each visible prop (a 3D model, a stand-in or an image plane), the shadows. */
export function planFinal(doc: StageDoc, rate: Rate): FinalPlan {
  const sets = doc.objects.filter((o) => o.kind === 'set' && o.visible)
  const layers: PlanLayer[] = [{ id: 'plate', kind: 'plate', name: sets.map((o) => o.name).join(' + ') || 'the set', object_id: null, profile_id: null, version: null }]
  for (const o of doc.objects.filter(isActor)) {
    layers.push({ id: o.id, kind: o.kind === 'mannequin' ? 'figure' : 'prop', name: o.name, object_id: o.id, profile_id: o.profile_id ?? null, version: o.version ?? null })
  }
  layers.push({ id: 'shadows', kind: 'shadows', name: 'Shadows', object_id: null, profile_id: null, version: null })
  return { times: framesAt(doc.range.start, doc.range.end, rate), layers }
}

/** The scene with only these actors visible (the sets and the lights stay). */
function only(d: StageDoc, keep: string[]): StageDoc {
  return { ...d, objects: d.objects.map((o) => (isActor(o) && !keep.includes(o.id) ? { ...o, visible: false } : o)) }
}

/** The renders each layer needs, in order (finals.py LAYER_PASSES). */
function passesOf(l: PlanLayer): { name: string; kind: 'depth' | 'clay' | 'pose' | 'beauty'; keep: 'none' | 'self' | 'all' }[] {
  if (l.kind === 'plate') return [{ name: 'depth', kind: 'depth', keep: 'none' }, { name: 'clay', kind: 'clay', keep: 'none' }]
  if (l.kind === 'shadows') return [{ name: 'clay', kind: 'clay', keep: 'all' }]
  if (l.kind === 'figure') return [{ name: 'pose', kind: 'pose', keep: 'self' }, { name: 'depth', kind: 'depth', keep: 'self' }]
  return [{ name: 'beauty', kind: 'beauty', keep: 'self' }, { name: 'depth', kind: 'depth', keep: 'self' }]
}

export interface MakeOptions { rate: Rate; name: string; shotId?: string | null; size?: [number, number]; onProgress?: (done: number, total: number, what: string) => void }

/** Render every layer's passes and make the final (no confirm: the command asks; the dev hook and the rig call this). */
export async function makeFinal(opts: MakeOptions): Promise<Final> {
  const s = st()
  if (!s.sequenceRenderer) (await import('./headless')).ensureHeadless()
  const render = st().sequenceRenderer as SequenceRenderer | null
  const cam = s.activeCamera()
  if (!render || !cam) throw new Error(!cam ? 'the stage has no camera' : 'the stage is not ready to render')
  await s.flush()
  const doc = st().current
  if (!doc) throw new Error('no stage open')
  const plan = planFinal(doc, opts.rate)
  const [w, h] = opts.size ?? finalSize()
  const sampled = plan.times.map((t) => { const d = sampleDoc(doc, t); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d } })
  const actors = plan.layers.filter((l) => l.object_id).map((l) => l.object_id!)
  const todo = plan.layers.flatMap((l) => passesOf(l).map((p) => ({ l, p })))
  const uploaded = new Set<string>()
  const layers: Record<string, { passes: Record<string, string[]>; keypoints?: unknown[] }> = {}
  let done = 0
  const total = todo.length * plan.times.length
  for (const { l, p } of todo) {
    const keep = p.keep === 'all' ? actors : p.keep === 'self' ? [l.object_id!] : []
    const frames = sampled.map((f) => ({ cam: f.cam, doc: only(f.doc, keep) }))
    const out = await render(frames, w, h, p.kind, sampleDoc(doc, st().frame), (n) => opts.onProgress?.(done + n, total, `${l.name} · ${p.name}`))
    const shas: string[] = []
    for (const blob of out.blobs) {
      const sha = await sha256Hex(await blob.arrayBuffer())
      if (!uploaded.has(sha)) { await api.putBlob(sha, blob); uploaded.add(sha) }
      shas.push(sha)
    }
    done += plan.times.length
    const entry = layers[l.id] ??= { passes: {} }
    entry.passes[p.name] = shas
    if (l.kind === 'figure' && p.kind === 'pose') entry.keypoints = out.keypoints.map((perFigure) => perFigure[0] ?? [])   // the figure alone: its own keypoints
  }
  return unwrap(http.POST('/finals', { body: {
    name: opts.name, stage_id: doc.id, camera_id: cam.id, stage_revision: doc.revision, range: { start: doc.range.start, end: doc.range.end }, rate: opts.rate,
    size: { w, h }, frames: plan.times.length, shot_id: opts.shotId ?? null,
    layers: plan.layers.map((l) => ({ id: l.id, kind: l.kind, name: l.name, object_id: l.object_id, profile_id: l.profile_id, version: l.version,
      passes: layers[l.id].passes, keypoints: (layers[l.id].keypoints ?? null) as never })) } }))
}

// ---- PS5b: the plate --------------------------------------------------------------------------------------------------------------
/** Queue the plate's still: the bare set's lit clay at the first frame through a Klein Stage shot, with the Shot tab's prompt and references. */
export async function makePlate(f: Final): Promise<void> {
  const shot = st().shot
  await unwrap(http.POST('/finals/{fid}/plate', { params: { path: { fid: f.id } }, body: { prompt_text: shot.prompt_text, refs: shot.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })) as never, seed: 0 } }))
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('the plate still did not load'))
    img.src = url
  })
}

/** Project the plate's still along the final's camera path (Stage: the still cast from the first frame's camera onto the set) and store the
 *  frames as the plate layer's own. The stage must be the final's, open. */
export async function projectPlate(f: Final, onProgress?: (done: number, total: number) => void): Promise<Final> {
  const plate = f.layers.find((l) => l.id === 'plate')
  const doc = st().current
  if (!plate?.still_asset_id) throw new Error('the plate has no still yet')
  if (!doc || doc.id !== f.stage_id) throw new Error('open the final\'s stage to project its plate')
  if (!st().plateProjector) (await import('./headless')).ensureHeadless()
  const project = st().plateProjector
  if (!project) throw new Error('the stage is not ready to render')
  const img = await loadImage(api.assetUrl(plate.still_asset_id))
  const times = framesAt(f.range.start, f.range.end, f.rate as Rate)
  const camOf = (d: StageDoc) => d.cameras.find((c) => c.id === f.camera_id) ?? d.cameras[0]
  const frames = times.map((t) => { const d = sampleDoc(doc, t); return { cam: camOf(d), doc: only(d, []) } })
  const blobs = await project(frames, f.size.w, f.size.h, img, frames[0].cam, img.naturalWidth / img.naturalHeight, sampleDoc(doc, st().frame), onProgress)
  const shas: string[] = []
  const uploaded = new Set<string>()
  for (const blob of blobs) {
    const sha = await sha256Hex(await blob.arrayBuffer())
    if (!uploaded.has(sha)) { await api.putBlob(sha, blob); uploaded.add(sha) }
    shas.push(sha)
  }
  return unwrap(http.PUT('/finals/{fid}/layers/{lid}/frames', { params: { path: { fid: f.id, lid: 'plate' } }, body: { frames: shas } }))
}

/** The layers' size: the pose-driven model's (Draft first, D18), else the clip size. */
export function finalSize(): [number, number] {
  const a = useSession.getState().capabilities?.stage?.animate
  return (a?.size?.length ? a.size : st().guideSize()) as [number, number]
}

// ---- the finals of the open stage -------------------------------------------------------------------------------------------------
interface FinalsState {
  finals: Final[]
  making: { done: number; total: number; what: string } | null
  projecting: string | null                                  // PS5b: the final whose plate Stage is projecting
  awaiting: Record<string, { was: string | null; since: number; field: 'assembled_at' | 'clip_id' }>   // PS5e / AE1: a job's result awaited: the field's value before (the poll runs till it moves)
  compositions: Record<string, Composition | null>                     // AE1: per assembled final, its composition (null: none yet)
  load: () => Promise<void>
  /** AE1: write the composition from the layers and the assembly (again: the edits dropped, after a confirm). */
  compose: (id: string) => Promise<void>
  /** AP1: the composition at Animate's Final level. */
  openFinal: (id: string) => void
  /** AE1: render the composition into the finished shot (effectcraft-cli on the CPU) — the final's clip. */
  render: (id: string) => Promise<void>
  make: (rate?: Rate) => Promise<Final | null>
  remove: (id: string) => Promise<void>
  plate: (id: string) => Promise<void>
  project: (id: string) => Promise<void>
  /** PS5c: perform a character layer (Wan Animate in chained batches); a seed given is a re-take. */
  perform: (id: string, layer: string, seed?: number) => Promise<void>
  /** PS5d: matte a performed character layer again (SAM 3 on its frames; it runs by itself after the last batch). */
  matte: (id: string, layer: string) => Promise<void>
  /** PS5e: composite the layers into the shot (a CPU job) — the clip lands on the final. */
  assemble: (id: string) => Promise<void>
  /** PS5e: the assembled shot in Animate's player. */
  play: (id: string) => void
  /** Watch the finals with work under way: reload them, and project a plate whose still has landed (once). */
  tick: () => Promise<void>
}

const busy = (f: Final) => f.layers.some((l) => l.status === 'queued' || l.status === 'running') || assembling(f.id) || rendering(f.id)
/** AE1: the final's render job (comp_render) is queued or running. */
export const rendering = (fid: string): boolean => Object.values(useSession.getState().jobs).some((j) => j.kind === 'comp_render' && j.origin?.ref === fid && (j.status === 'queued' || j.status === 'running'))
/** PS5e: the final's assembly job is queued or running (the session's jobs, by their origin). */
export const assembling = (fid: string): boolean => Object.values(useSession.getState().jobs).some((j) => j.kind === 'assemble_final' && j.origin?.ref === fid && (j.status === 'queued' || j.status === 'running'))
/** PS5e: every layer made — the plate projected, each character performed and matted. */
export const readyToAssemble = (f: Final): boolean => f.layers.every((l) => (l.kind === 'plate' || l.kind === 'figure' ? l.status === 'done' && l.frames_done === f.frames : true))
const replace = (list: Final[], f: Final) => list.map((x) => (x.id === f.id ? f : x))

export const useFinals = create<FinalsState>((set, get) => ({
  finals: [], making: null, projecting: null, awaiting: {}, compositions: {},
  compose: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    const have = get().compositions[id]
    if (have) {
      const ok = await askConfirm({ title: 'Make the composition again?', okLabel: 'Make it again',
        text: `${f.name}: the composition is written afresh from the layers and the assembly — its ${have.revision} edit${have.revision === 1 ? '' : 's'} ${have.revision === 1 ? 'is' : 'are'} dropped.` })
      if (!ok) return
    }
    try {
      const c = await unwrap(http.POST('/finals/{fid}/composition', { params: { path: { fid: id } } }))
      set({ compositions: { ...get().compositions, [id]: c } })
      useSession.getState().toast(`${f.name}: the composition is ready (${c.layers.length} layers) — Open in Final to scrub it`, 'success')
      if (useComposition.getState().finalId === id) void useComposition.getState().reload()
    } catch (e) { useSession.getState().toast(`Make the composition: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  openFinal: (id) => { void useComposition.getState().open(id); useSession.getState().setSuite('animate') },
  render: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    try {
      // AE4e: a processing layer whose layers below changed since it was rendered would freeze the old picture into the shot — ask first
      let stale: string[] = []
      try {
        const c = await unwrap(http.GET('/finals/{fid}/composition', { params: { path: { fid: id } } }))
        stale = Object.entries((c as { processing_stale?: Record<string, boolean> }).processing_stale ?? {}).filter(([, v]) => v).map(([k]) => k)
      } catch { stale = [] }
      if (stale.length) {
        const ok = await askConfirm({ title: `${f.name}: ${stale.length} processing layer${stale.length === 1 ? ' is' : 's are'} stale — render anyway?`,
          text: 'A layer below changed since it was rendered. Process it again first (its row in Final · Passes), or render the shot as it is.', okLabel: 'Render anyway' })
        if (!ok) return
      }
      await unwrap(http.POST('/finals/{fid}/composition/render', { params: { path: { fid: id } } }))
      set({ awaiting: { ...get().awaiting, [id]: { was: f.clip_id ?? null, since: Date.now(), field: 'clip_id' } } })
      useSession.getState().toast(`${f.name}: rendering the finished shot (effectcraft-cli on the CPU; the Dock shows the frames) — it becomes the final's clip`, 'info')
    } catch (e) { useSession.getState().toast(`Render the finished shot: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  plate: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    try {
      await makePlate(f)
      useSession.getState().toast(`${f.name}: the plate is queued (a Klein Stage shot of the bare set) — Stage projects it along the camera path when it lands`, 'info')
      await get().load()
    } catch (e) { useSession.getState().toast(`Make the plate: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  perform: async (id, layer, seed) => {
    const f = get().finals.find((x) => x.id === id)
    const l = f?.layers.find((x) => x.id === layer)
    if (!f || !l) return
    try {
      const r = await unwrap(http.POST('/finals/{fid}/layers/{lid}/run', { params: { path: { fid: id, lid: layer } }, body: { seed: seed ?? null } }))
      useSession.getState().toast(`${l.name}: ${r.batches} batch${r.batches === 1 ? '' : 'es'} of Wan Animate queued${r.placed ? ' — the reference stands where the figure starts' : ' — the figure is not whole at the start: the reference is centred'}`, 'info')
      await get().load()
    } catch (e) { useSession.getState().toast(`Perform ${l.name}: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  matte: async (id, layer) => {
    try { await unwrap(http.POST('/finals/{fid}/layers/{lid}/matte', { params: { path: { fid: id, lid: layer } }, body: { text: 'person' } })); await get().load() }
    catch (e) { useSession.getState().toast(`Matte: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  assemble: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    try {
      await unwrap(http.POST('/finals/{fid}/assemble', { params: { path: { fid: id } } }))
      set({ awaiting: { ...get().awaiting, [id]: { was: f.assembled_at ?? null, since: Date.now(), field: 'assembled_at' } } })
      useSession.getState().toast(`${f.name}: assembling the layers into the shot (the CPU; the Dock shows the frames)`, 'info')
    } catch (e) { useSession.getState().toast(`Assemble: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  play: (id) => {
    const clip = get().finals.find((x) => x.id === id)?.clip_id
    if (!clip) return
    void import('../animate/animateStore').then(async (m) => {
      useSession.getState().setSuite('animate')
      const an = m.useAnimate.getState()
      await an.loadClips(); an.select(clip)
    })
  },
  project: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f || get().projecting) return
    set({ projecting: id })
    try { const next = await projectPlate(f); set({ finals: replace(get().finals, next) }) }
    catch (e) { useSession.getState().toast(`Project the plate: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
    finally { set({ projecting: null }) }
  },
  tick: async () => {
    if (!get().finals.some(busy) && !Object.keys(get().awaiting).length) return
    await get().load()
    const waiting = Object.fromEntries(Object.entries(get().awaiting).filter(([id, a]) => {   // till the result moves; a failed job stops it after 15 s
      const f = get().finals.find((x) => x.id === id)
      return !!f && (f[a.field] ?? null) === a.was && (assembling(id) || rendering(id) || Date.now() - a.since < 15_000)
    }))
    if (Object.keys(waiting).length !== Object.keys(get().awaiting).length) set({ awaiting: waiting })
    const doc = st().current
    const ready = get().finals.find((f) => f.stage_id === doc?.id && f.layers.some((l) => l.id === 'plate' && l.status === 'running' && l.still_asset_id && !l.frames_done))
    if (ready && !get().projecting) await get().project(ready.id)
  },
  load: async () => {
    const doc = st().current
    if (!doc) { set({ finals: [] }); return }
    try {
      const finals = (await unwrap(http.GET('/finals', { params: { query: { stage_id: doc.id } } }))).items
      const pairs = await Promise.all(finals.filter((f) => f.assembled_at).map(async (f): Promise<[string, Composition | null]> => {
        try { return [f.id, await unwrap(http.GET('/finals/{fid}/composition', { params: { path: { fid: f.id } } }))] } catch { return [f.id, null] }   // 404: none yet
      }))
      set({ finals, compositions: Object.fromEntries(pairs) })
    } catch { /* the panel shows none */ }
  },
  make: async (rate = 16) => {
    const s = useSession.getState()
    const doc = st().current
    if (!doc || get().making) return null
    const plan = planFinal(doc, rate)
    const figures = plan.layers.filter((l) => l.kind === 'figure').length, props = plan.layers.filter((l) => l.kind === 'prop').length
    const [w, h] = finalSize()
    const ok = await askConfirm({ title: 'Make the final shot?', okLabel: 'Split into layers',
      text: `The scene through ${st().activeCamera()?.name ?? 'the camera'}, frames ${doc.range.start}–${doc.range.end} at ${rate} fps: ${plan.times.length} frames at ${w}×${h}. ` +
        `${plan.layers.length} layers — the plate, ${figures} figure${figures === 1 ? '' : 's'}, ${props} prop${props === 1 ? '' : 's'} and the shadows. Stage renders their passes here (a minute or two); the layers are made from them next.` })
    if (!ok) return null
    set({ making: { done: 0, total: 1, what: 'starting' } })
    try {
      const n = get().finals.filter((f) => f.stage_id === doc.id).length + 1
      const f = await makeFinal({ rate, name: `Final ${n}`, onProgress: (done, total, what) => set({ making: { done, total, what } }) })
      set({ finals: [f, ...get().finals] })
      s.toast(`${f.name}: ${f.layers.length} layers, ${f.frames} frames each — their passes are on disk`, 'success')
      return f
    } catch (e) { s.toast(`Make the final shot: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error'); return null } finally { set({ making: null }) }
  },
  remove: async (id) => {
    try { await unwrap(http.DELETE('/finals/{fid}', { params: { path: { fid: id } } })); set({ finals: get().finals.filter((f) => f.id !== id) }) }
    catch (e) { useSession.getState().toast(`Delete the final: ${(e as ApiError).detail ?? e}`, 'error') }
  },
}))
