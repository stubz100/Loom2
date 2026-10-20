// D111 (PS5a, proto01_animate 16): *Make the final shot* — the finished scene split into layers. One layer per entity (the plate, each
// visible figure, each visible prop or 3D model, the shadows); Stage renders each layer's passes at the shot's rate through the active
// camera (the plate: the bare set's depth and lit clay; a figure alone with the set: its pose and depth; a prop alone with the set: its
// beauty and depth; the shadows: everything, lit) and uploads them (each frame once, by its hash) into a final record on the server.
// The later steps make each layer's own frames and the assembly from these.
import { create } from 'zustand'
import { api, http, sha256Hex, unwrap, type ApiError } from '../../api/client'
import type { Final, StageDoc, StageObject } from '../../api/types'
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

/** The layers' size: the pose-driven model's (Draft first, D18), else the clip size. */
export function finalSize(): [number, number] {
  const a = useSession.getState().capabilities?.stage?.animate
  return (a?.size?.length ? a.size : st().guideSize()) as [number, number]
}

// ---- the finals of the open stage -------------------------------------------------------------------------------------------------
interface FinalsState {
  finals: Final[]
  making: { done: number; total: number; what: string } | null
  load: () => Promise<void>
  make: (rate?: Rate) => Promise<Final | null>
  remove: (id: string) => Promise<void>
}

export const useFinals = create<FinalsState>((set, get) => ({
  finals: [], making: null,
  load: async () => {
    const doc = st().current
    if (!doc) { set({ finals: [] }); return }
    try { set({ finals: (await unwrap(http.GET('/finals', { params: { query: { stage_id: doc.id } } }))).items }) } catch { /* the panel shows none */ }
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
