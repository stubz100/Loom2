// D111 (PS5a, proto01_animate 16): *Make the final shot* — the finished scene split into layers. One layer per entity (the plate, each
// visible figure, each visible prop or 3D model, the shadows); Stage renders each layer's passes at the shot's rate through the active
// camera (the plate: the bare set's depth and lit clay; a figure alone with the set: its pose and depth; a prop alone with the set: its
// beauty and depth; the shadows: everything, lit) and uploads them (each frame once, by its hash) into a final record on the server.
// The later steps make each layer's own frames and the assembly from these.
import { useEffect } from 'react'
import { create } from 'zustand'
import { api, http, sha256Hex, unwrap, type ApiError } from '../../api/client'
import type { BatchPlan, Composition, Final, RenderSettings, StageDoc, StageObject } from '../../api/types'
import { useComposition } from '../animate/compositionStore'
import { askConfirm, useSession } from '../../store/session'
import { forLabel, useMakeFor } from '../../store/origin'
import { bodyHash, keyframesOf, sampleDoc, withKey, type SkeletonKey } from './anim'
import { st, type SequenceRenderer } from './stageStore'
import { navigate } from '../../frame/router'

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
/** SC3e (D120): a stage with a visible picture set — its plate is that picture through the relief, not a Klein still (finals.py picture_plate). */
export const hasPictureSet = (doc: StageDoc): boolean => doc.objects.some((o) => o.kind === 'set' && o.preset === 'image' && o.visible && !!o.plate_asset_id)
/** CW7 (04 §5): a stage with a visible built set skinned from its picture — its plate is the set rendered (finals.py built_plate). */
export const hasBuiltSet = (doc: StageDoc): boolean => doc.objects.some((o) => o.kind === 'set' && o.preset === 'built' && o.visible && !!o.place_set?.faces.some((f) => f.texture_asset_id))
/** SC3e: the final's plate is a picture set's picture, or (CW7) a built set rendered — Stage renders it, no job (the server decided when
 *  the final was made). */
export const picturePlated = (f: Final): boolean => f.layers.some((l) => l.id === 'plate' && (l.method === 'picture' || l.method === 'set'))
export const builtPlated = (f: Final): boolean => f.layers.some((l) => l.id === 'plate' && l.method === 'set')

// ---- CA3 (D130): the plate's method by the camera's travel ----------------------------------------------------------------------
type V3 = number[]
const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const norm = (v: V3) => Math.hypot(v[0], v[1], v[2])
const degrees = (a: V3, b: V3) => Math.acos(Math.min(1, Math.max(-1, (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / ((norm(a) * norm(b)) || 1)))) * 180 / Math.PI

export interface Travel { turn: number; orbit: number; widen: number }
/** How far the camera travels over the final's times against its first frame: the most its view turns (degrees), the most its place swings
 *  about the first frame's target (degrees: an orbit, a truck), and how much more it sees (its distance to the target over its focal length). */
export function cameraTravel(doc: StageDoc, camId: string, times: number[]): Travel {
  const cams = times.map((t) => sampleDoc(doc, t).cameras.find((c) => c.id === camId)).filter((c) => !!c)
  const c0 = cams[0]
  if (!c0) return { turn: 0, orbit: 0, widen: 1 }
  const view0 = sub(c0.target, c0.pos), arm0 = sub(c0.pos, c0.target)
  const seen0 = norm(view0) / Math.max(1, c0.focal_mm)
  let turn = 0, orbit = 0, widen = 1
  for (const c of cams) {
    turn = Math.max(turn, degrees(view0, sub(c.target, c.pos)))
    orbit = Math.max(orbit, degrees(arm0, sub(c.pos, c0.target)))
    widen = Math.max(widen, norm(sub(c.target, c.pos)) / Math.max(1, c.focal_mm) / (seen0 || 1))
  }
  return { turn, orbit, widen }
}

/** finals.py PLATE_PATH_MAX: LTX-2.3's longest clip — a longer plate is projected. */
export const PLATE_PATH_MAX = 257
/** D130: a camera that turns or swings more than this, or sees this much more, shows what the plate's still never saw. */
export const LARGE_MOVE = { degrees: 12, widen: 1.15 }
export type PlateMethod = 'projected' | 'filled' | 'generated'
export interface PlateChoice { method: PlateMethod; why: string }
/** D135 (PF1, D133's E35d): a large move's plate is projected and filled — the still projected along the path, what it never saw filled
 *  by Klein at keyframes Stage places (it stays on the set); a small move's is projected (cheap and exact). D130's generated plate
 *  (CA3) stays on the plate's row: it draws the unseen but drifts against the set. */
export function plateChoice(travel: Travel): PlateChoice {
  const turn = Math.round(Math.max(travel.turn, travel.orbit)), more = Math.round((travel.widen - 1) * 100)
  const large = turn > LARGE_MOVE.degrees || travel.widen > LARGE_MOVE.widen
  const move = turn > LARGE_MOVE.degrees ? `the camera turns ${turn}°` : travel.widen > LARGE_MOVE.widen ? `the camera sees ${more}% more` : 'the camera moves little'
  return large ? { method: 'filled', why: move } : { method: 'projected', why: move }
}


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

export interface MakeOptions { rate: Rate; name: string; shotId?: string | null; shotVersion?: string | null; size?: [number, number]; plate?: PlateMethod | null; onProgress?: (done: number, total: number, what: string) => void }

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
  const plate = opts.plate ?? (hasPictureSet(doc) || hasBuiltSet(doc) ? null : plateChoice(cameraTravel(doc, cam.id, plan.times)).method)
  const sampled = plan.times.map((t) => { const d = sampleDoc(doc, t); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d } })
  const actors = plan.layers.filter((l) => l.object_id).map((l) => l.object_id!)
  const todo = plan.layers.flatMap((l) => passesOf(l).map((p) => ({ l, p })))
  const uploaded = new Set<string>()
  const layers: Record<string, { passes: Record<string, string[]>; keypoints?: unknown[] }> = {}
  let done = 0
  const total = todo.length * plan.times.length
  for (const { l, p } of todo) {
    const keep = p.keep === 'all' ? actors : p.keep === 'self' ? [l.object_id!] : []
    const out = await renderPass(render, sampled, keep, w, h, p.kind, doc, uploaded, (n) => opts.onProgress?.(done + n, total, `${l.name} · ${p.name}`))
    done += plan.times.length
    const entry = layers[l.id] ??= { passes: {} }
    entry.passes[p.name] = out.shas
    if (l.kind === 'figure' && p.kind === 'pose') entry.keypoints = out.keypoints
  }
  return unwrap(http.POST('/finals', { body: {
    name: opts.name, stage_id: doc.id, camera_id: cam.id, stage_revision: doc.revision, range: { start: doc.range.start, end: doc.range.end }, rate: opts.rate,
    size: { w, h }, frames: plan.times.length, shot_id: opts.shotId ?? null, shot_version: opts.shotId ? opts.shotVersion ?? null : null,
    layers: plan.layers.map((l) => ({ id: l.id, kind: l.kind, name: l.name, object_id: l.object_id, profile_id: l.profile_id, version: l.version, method: l.kind === 'plate' ? plate : null,
      passes: layers[l.id].passes, keypoints: (layers[l.id].keypoints ?? null) as never, ...(l.kind === 'figure' ? bodyStamp(doc, l.object_id!, plan.times) : {}) })) } }))
}

/** One pass of a layer over the final's frames — rendered with only `keep`'s actors, each frame uploaded once (by its hash). */
async function renderPass(render: SequenceRenderer, sampled: { cam: NonNullable<StageDoc['cameras'][number]>; doc: StageDoc }[], keep: string[], w: number, h: number,
                          kind: 'depth' | 'clay' | 'pose' | 'beauty', doc: StageDoc, uploaded: Set<string>, onProgress?: (n: number) => void): Promise<{ shas: string[]; keypoints: unknown[] }> {
  const frames = sampled.map((f) => ({ cam: f.cam, doc: only(f.doc, keep) }))
  const out = await render(frames, w, h, kind, sampleDoc(doc, st().frame), onProgress)
  const shas: string[] = []
  for (const blob of out.blobs) {
    const sha = await sha256Hex(await blob.arrayBuffer())
    if (!uploaded.has(sha)) { await api.putBlob(sha, blob); uploaded.add(sha) }
    shas.push(sha)
  }
  return { shas, keypoints: out.keypoints.map((perFigure) => perFigure[0] ?? []) }        // a figure alone: its own keypoints
}

// ---- CS3 (proto01_UIcast 06 §2.10, D136 U19): the skeleton changed under a rendered character ------------------------------------------
/** What a figure layer stamps: the figure's own body (Cast's) and, per frame of the final, the body its guide is drawn with (skeleton keys
 *  sampled) as a hash. */
export function bodyStamp(doc: StageDoc, objectId: string, times: number[]): { body: Record<string, unknown> | null; body_hashes: string[] } {
  const own = doc.objects.find((o) => o.id === objectId)?.body ?? null
  return { body: own as Record<string, unknown> | null, body_hashes: times.map((t) => bodyHash(sampleDoc(doc, t).objects.find((o) => o.id === objectId)?.body ?? null)) }
}

/** Whether a final's character layer was drawn with another skeleton than the stage's now: the first frame (its index and Stage time) whose
 *  body differs, and the batch it falls in (finals.py plan_batches: 77 frames, then 72 more each). Null when nothing changed or the layer
 *  stamped nothing (a final made before CS3). */
export function skeletonChange(f: Final, doc: StageDoc, lid: string): { index: number; frame: number; batch: number } | null {
  const l = f.layers.find((x) => x.id === lid)
  if (!l || l.kind !== 'figure' || !l.object_id || l.body_hashes.length !== f.frames || doc.id !== f.stage_id) return null
  const times = framesAt(f.range.start, f.range.end, f.rate as Rate)
  const now = bodyStamp(doc, l.object_id, times).body_hashes
  const index = now.findIndex((h, i) => h !== l.body_hashes[i])
  return index < 0 ? null : { index, frame: times[index], batch: batchOf(index) }
}
/** The batch a frame index of a performance falls in (finals.py plan_batches). */
export const batchOf = (index: number): number => (index < 77 ? 0 : 1 + Math.floor((index - 77) / 72))

/** CS3: a character layer's passes drawn again from the stage as it is now (its pose and depth, the figure alone with the set) and sent with
 *  the body they were drawn with; the server encodes a performed layer's guide again. */
async function redrawLayer(f: Final, lid: string): Promise<Final> {
  if (!st().sequenceRenderer) (await import('./headless')).ensureHeadless()
  const render = st().sequenceRenderer as SequenceRenderer | null
  await st().flush()
  const doc = st().current, l = f.layers.find((x) => x.id === lid)
  const cam = doc?.cameras.find((c) => c.id === f.camera_id)
  if (!render || !doc || doc.id !== f.stage_id || !l?.object_id || !cam) throw new Error("open the final's stage to draw its guide again")
  const times = framesAt(f.range.start, f.range.end, f.rate as Rate)
  const sampled = times.map((t) => { const d = sampleDoc(doc, t); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d } })
  const uploaded = new Set<string>(), passes: Record<string, string[]> = {}
  let keypoints: unknown[] = []
  for (const p of passesOf({ id: lid, kind: 'figure', name: l.name, object_id: l.object_id, profile_id: l.profile_id, version: l.version })) {
    const out = await renderPass(render, sampled, [l.object_id], f.size.w, f.size.h, p.kind, doc, uploaded)
    passes[p.name] = out.shas
    if (p.kind === 'pose') keypoints = out.keypoints
  }
  return unwrap(http.PUT('/finals/{fid}/layers/{lid}/passes', { params: { path: { fid: f.id, lid } }, body: { passes, keypoints: keypoints as never, ...bodyStamp(doc, l.object_id, times) } }))
}

/** *Apply from a frame…*: the skeleton keys that keep every frame before `frame` as the layer was drawn — the figure's keys that took
 *  Cast's body before it now hold the old one (the layer's), and a key at the range's start holds it where none did — and from `frame` on
 *  Cast's skeleton. */
export function keysFrom(doc: StageDoc, objectId: string, old: StageObject['body'], frame: number): SkeletonKey[] {
  const ks = keyframesOf(doc).skeleton?.[objectId] ?? []
  let out: SkeletonKey[] = ks.map((x) => (x.frame < frame && x.body === null ? { ...x, body: old } : x))
  if (!out.some((x) => x.frame <= doc.range.start)) out = withKey(out, { frame: doc.range.start, transition: 0, body: old })
  return withKey(out, { frame, transition: 0, body: null })                    // replaces a key already at the frame
}

// ---- PS5b: the plate --------------------------------------------------------------------------------------------------------------
/** Queue the plate's still: the bare set's lit clay at the first frame through a Klein Stage shot, with the Shot tab's prompt and references
 *  (O4: in a scene, the scene's first plate leads them — `scene_plate`). */
export async function makePlate(f: Final): Promise<{ scene_plate?: string | null }> {
  const shot = st().shot
  return unwrap(http.POST('/finals/{fid}/plate', { params: { path: { fid: f.id } }, body: { prompt_text: shot.prompt_text, refs: shot.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })) as never, seed: 0 } }))
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
  return storePlate(f, blobs)
}

/** SC3e (D120): the plate from the picture — the picture set's relief, textured with its (clean) picture and the picture behind it,
 *  through each frame's camera with every actor hidden (Stage's beauty pass): the place itself, moving as the camera moves. No Klein
 *  still, no GPU job; the server stamps the set's picture as the plate's still. The stage must be the final's, open. */
export async function picturePlate(f: Final, onProgress?: (done: number, total: number) => void): Promise<Final> {
  const doc = st().current
  if (!doc || doc.id !== f.stage_id) throw new Error('open the final\'s stage to render its plate')
  if (!hasPictureSet(doc) && !hasBuiltSet(doc)) throw new Error('the stage has no picture set or built set any more')
  if (!st().sequenceRenderer) (await import('./headless')).ensureHeadless()
  const render = st().sequenceRenderer
  if (!render) throw new Error('the stage is not ready to render')
  const times = framesAt(f.range.start, f.range.end, f.rate as Rate)
  const camOf = (d: StageDoc) => d.cameras.find((c) => c.id === f.camera_id) ?? d.cameras[0]
  const frames = times.map((t) => { const d = sampleDoc(doc, t); return { cam: camOf(d), doc: only(d, []) } })
  const out = await render(frames, f.size.w, f.size.h, 'beauty', sampleDoc(doc, st().frame), onProgress)
  return storePlate(f, out.blobs)
}

/** The plate's frames uploaded (each once, by its hash) and stored as the layer's own; the layer is done. */
async function storePlate(f: Final, blobs: Blob[]): Promise<Final> {
  const shas: string[] = []
  const uploaded = new Set<string>()
  for (const blob of blobs) {
    const sha = await sha256Hex(await blob.arrayBuffer())
    if (!uploaded.has(sha)) { await api.putBlob(sha, blob); uploaded.add(sha) }
    shas.push(sha)
  }
  return unwrap(http.PUT('/finals/{fid}/layers/{lid}/frames', { params: { path: { fid: f.id, lid: 'plate' } }, body: { frames: shas } }))
}

/** The layers' size: the pose-driven model's short side on the model's grid at the project's aspect (Draft first, D18), else the clip
 *  size. V81: it was the model's own 832×480 whatever the project — a 9:16 project's final came out landscape, and 16:9 showed ≈ 2.5 %
 *  more picture than the viewport, the Stage shot and the guide (which follow the project); 848×480 ran on the CN rig (2026-10-15),
 *  480×848 on the V81 rig (2026-10-27). */
export function finalSize(): [number, number] {
  const a = useSession.getState().capabilities?.stage?.animate
  if (!a?.size?.length) return st().guideSize() as [number, number]
  const [mw, mh] = a.size as [number, number]
  const cur = st().current
  const aspect = cur ? cur.size.w / Math.max(1, cur.size.h) : mw / mh
  const short = Math.min(mw, mh)
  const snap = (v: number) => Math.max(16, Math.round(v / 16) * 16)
  return aspect >= 1 ? [snap(short * aspect), short] : [short, snap(short / aspect)]
}

// ---- the finals of the open stage -------------------------------------------------------------------------------------------------
interface FinalsState {
  finals: Final[]
  making: { done: number; total: number; what: string } | null
  projecting: string | null                                  // PS5b: the final whose plate Stage is projecting (SC3e: or rendering from the picture)
  awaiting: Record<string, { was: string | null; since: number; field: 'assembled_at' | 'clip_id' }>   // PS5e / AE1: a job's result awaited: the field's value before (the poll runs till it moves)
  compositions: Record<string, Composition | null>                     // AE1: per assembled final, its composition (null: none yet)
  load: () => Promise<void>
  /** AE1: write the composition from the layers and the assembly (again: the edits dropped, after a confirm). */
  compose: (id: string) => Promise<void>
  /** AE5: the finished shot's render settings and output modules (the next render uses them). */
  setRender: (id: string, patch: Partial<RenderSettings>) => Promise<void>
  /** AP1: the composition at Animate's Final level. */
  openFinal: (id: string) => void
  /** AE1: render the composition into the finished shot (effectcraft-cli on the CPU) — the final's clip. */
  render: (id: string) => Promise<void>
  make: (rate?: Rate) => Promise<Final | null>
  remove: (id: string) => Promise<void>
  plate: (id: string) => Promise<void>
  project: (id: string) => Promise<void>
  /** CA3 (D130) / PF1 (D135): the plate projected, projected and filled, or generated along the path (a still already made is kept). */
  setPlateMethod: (id: string, method: PlateMethod) => Promise<void>
  /** PF1 (Q29): the filled plate's in-between heal on or off. */
  setPlateHeal: (id: string, heal: boolean) => Promise<void>
  /** PF1: the final whose plate Stage is filling, and what it is doing. */
  filling: { id: string; what: string } | null
  /** PF1: one step of filling the plate (the poll drives it). */
  fill: (id: string) => Promise<void>
  /** PS5c: perform a character layer (Wan Animate in chained batches); a seed given is a re-take. */
  perform: (id: string, layer: string, seed?: number, opts?: { fromBatch?: number; stage?: boolean }) => Promise<void>
  /** CS3 (proto01_UIcast 06 §2.10): *the skeleton changed* — the layer's guide drawn again with the stage's skeleton now, then the whole
   *  layer performed again (its seed kept). */
  skeletonRerender: (id: string, layer: string) => Promise<void>
  /** CS3: *Apply from a frame…* — skeleton keys keep every frame before `frame` as the layer was drawn and take Cast's skeleton from it; the
   *  guide drawn again; the layer performed again from the batch the first changed frame falls in (the batches before it kept). */
  skeletonFrom: (id: string, layer: string, frame: number) => Promise<void>
  /** CA4: each final's batch plan (its states and costs), loaded with the finals. */
  plans: Record<string, BatchPlan>
  loadPlan: (id: string) => Promise<void>
  /** CA4: every character layer not performed yet, staged in the queue (Run staged releases them — an overnight start). */
  stagePerformances: (id: string) => Promise<void>
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
/** U0 (F41): a stage's newest final, by its creation time — the list is newest first from the server and a new final is prepended, so
 *  `.at(-1)` was the oldest (the walkthrough's foot performed and assembled Final 1 while Final 2 was the one being made). */
export function newestFinal(finals: Final[], stageId: string | null | undefined): Final | undefined {
  let best: Final | undefined
  for (const f of finals) if (f.stage_id === stageId && (!best || f.created_at > best.created_at)) best = f
  return best
}

export const useFinals = create<FinalsState>((set, get) => ({
  finals: [], making: null, projecting: null, filling: null, awaiting: {}, compositions: {},
  setRender: async (id, patch) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    const body = { ...f.render, ...patch }
    set({ finals: get().finals.map((x) => (x.id === id ? { ...x, render: body } : x)) })                // at once; the server's answer follows
    try {
      const next = await unwrap(http.PUT('/finals/{fid}/render', { params: { path: { fid: id } }, body }))
      set({ finals: get().finals.map((x) => (x.id === id ? next : x)) })
    } catch (e) { useSession.getState().toast(`Render settings: ${String((e as ApiError).detail ?? e)}`) }
  },
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
  openFinal: (id) => { void useComposition.getState().open(id); navigate({ suite: 'final' }) },   // D121: the Final level is a suite of its own
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
    if (picturePlated(f)) {                                                    // SC3e: Stage renders it here, in seconds
      if (get().projecting) return
      set({ projecting: id })
      try {
        const next = await picturePlate(f)
        set({ finals: replace(get().finals, next) })
        useSession.getState().toast(`${f.name}: ${builtPlated(f) ? `the plate is the built set — ${next.frames} frames through its faces` : `the plate is the picture — ${next.frames} frames through its relief`}`, 'success')
      } catch (e) { useSession.getState().toast(`Render the plate: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
      finally { set({ projecting: null }) }
      return
    }
    try {
      const r = await makePlate(f)
      useSession.getState().toast(`${f.name}: the plate is queued (a Klein Stage shot of the bare set${r.scene_plate ? ", the scene's first plate leading its references" : ''}) — ${f.layers.some((l) => l.id === 'plate' && l.method === 'generated')
        ? 'then generated along the camera path from it (LTX-2.3 on the bare set\'s depth)' : 'Stage projects it along the camera path when it lands'}`, 'info')
      await get().load()
    } catch (e) { useSession.getState().toast(`Make the plate: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  skeletonRerender: async (id, layer) => {
    const f = get().finals.find((x) => x.id === id), l = f?.layers.find((x) => x.id === layer)
    if (!f || !l) return
    try {
      const f2 = await redrawLayer(f, layer)
      set({ finals: replace(get().finals, f2) })
      if (l.batches.length) await get().perform(id, layer, l.seed)
      else useSession.getState().toast(`${l.name}: the guide drawn again with the new skeleton — Perform when ready`, 'info')
    } catch (e) { useSession.getState().toast(`${l.name}: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  skeletonFrom: async (id, layer, frame) => {
    const f = get().finals.find((x) => x.id === id), l = f?.layers.find((x) => x.id === layer)
    const doc = st().current
    if (!f || !l?.object_id || !doc) return
    try {
      st().setSkeletonKeys(l.object_id, keysFrom(doc, l.object_id, (l.body ?? null) as StageObject['body'], frame), 'apply the skeleton from a frame')
      const f2 = await redrawLayer(f, layer)
      set({ finals: replace(get().finals, f2) })
      const after = f2.layers.find((x) => x.id === layer)!.body_hashes
      const first = after.findIndex((h, i) => h !== l.body_hashes[i])
      if (first < 0) { useSession.getState().toast(`${l.name}: the frames are as they were — nothing to perform again`, 'info'); return }
      const k = batchOf(first)
      if (!l.batches.length) useSession.getState().toast(`${l.name}: the guide drawn again from frame ${frame} — Perform when ready`, 'info')
      else await get().perform(id, layer, l.seed, k ? { fromBatch: k } : undefined)
    } catch (e) { useSession.getState().toast(`${l.name}: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  perform: async (id, layer, seed, opts) => {
    const f = get().finals.find((x) => x.id === id)
    const l = f?.layers.find((x) => x.id === layer)
    if (!f || !l) return
    try {
      const r = await unwrap(http.POST('/finals/{fid}/layers/{lid}/run', { params: { path: { fid: id, lid: layer } }, body: { seed: seed ?? null, from_batch: opts?.fromBatch ?? 0, stage: !!opts?.stage } }))
      const how = opts?.stage ? 'staged' : 'queued'
      useSession.getState().toast(opts?.fromBatch ? `${l.name}: from batch ${opts.fromBatch + 1} of ${r.batches} again with a new seed — ${how}`
        : `${l.name}: ${r.batches} batch${r.batches === 1 ? '' : 'es'} of Wan Animate ${how}${r.placed ? ' — the reference stands where the figure starts' : ' — the figure is not whole at the start: the reference is centred'}`, 'info')
      await get().load()
      void get().loadPlan(id)
    } catch (e) { useSession.getState().toast(`Perform ${l.name}: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  plans: {},
  loadPlan: async (id) => {
    try { const p = await unwrap(http.GET('/finals/{fid}/plan', { params: { path: { fid: id } } })); set({ plans: { ...get().plans, [id]: p } }) } catch { /* a plan is advice */ }
  },
  stagePerformances: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    const todo = f.layers.filter((l) => l.kind === 'figure' && !l.batches.length)
    for (const l of todo) await get().perform(id, l.id, undefined, { stage: true })
    if (todo.length) useSession.getState().toast(`${todo.length} performance${todo.length === 1 ? '' : 's'} staged — the queue's Run staged starts them`, 'info')
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
      navigate({ suite: 'animate' })
      const an = m.useAnimate.getState()
      await an.loadClips(); an.select(clip)
    })
  },
  setPlateMethod: async (id, method) => {
    const f = get().finals.find((x) => x.id === id)
    if (!f) return
    try {
      const next = await unwrap(http.PUT('/finals/{fid}/layers/plate/method', { params: { path: { fid: id } }, body: { method, prompt_text: st().shot.prompt_text } }))
      set({ finals: replace(get().finals, next) })
      const p = next.layers.find((l) => l.id === 'plate')
      useSession.getState().toast(method === 'generated'
        ? `${f.name}: the plate is generated along the path${p?.status === 'queued' ? ' — its clip is queued (LTX-2.3 from the still on the bare set\'s depth)' : ' — Make the plate starts it'}`
        : method === 'filled' ? `${f.name}: the plate is projected and filled${p?.still_asset_id ? ' — Stage places its keyframes and Klein fills what the still never saw' : ' — Make the plate starts it'}`
        : `${f.name}: the plate is projected${p?.still_asset_id ? ' — Stage projects the still along the camera path' : ''}`, 'info')
    } catch (e) { useSession.getState().toast(`The plate's method: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  setPlateHeal: async (id, heal) => {
    try {
      const next = await unwrap(http.PUT('/finals/{fid}/layers/plate/heal', { params: { path: { fid: id } }, body: { heal } }))
      set({ finals: replace(get().finals, next) })
      useSession.getState().toast(heal ? 'The frames between keyframes are healed the next time the plate is filled (a few small Fills more)' : 'No heal: the frames between keyframes as projected', 'info')
    } catch (e) { useSession.getState().toast(`Heal: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
  },
  fill: async (id) => {
    const f = get().finals.find((x) => x.id === id)
    const doc = st().current
    if (!f || !doc || doc.id !== f.stage_id || get().projecting || get().filling) return
    set({ filling: { id, what: 'starting' } })
    try {
      if (!st().plateProjector) (await import('./headless')).ensureHeadless()
      const camOf = (d: StageDoc) => d.cameras.find((c) => c.id === f.camera_id) ?? d.cameras[0]
      const frames = framesAt(f.range.start, f.range.end, f.rate as Rate).map((t) => { const d = sampleDoc(doc, t); return { cam: camOf(d), doc: only(d, []) } })
      const { fillStep } = await import('./fillPlate')
      const r = await fillStep(f, frames, sampleDoc(doc, st().frame), (what) => set({ filling: { id, what } }))
      if (r.step === 'done') {
        set({ finals: replace(get().finals, r.final) })
        useSession.getState().toast(`${f.name}: the plate is projected and filled — ${r.final.frames} frames`, 'success')
      } else if (r.step === 'key') await get().load()
    } catch (e) {
      useSession.getState().toast(`Fill the plate: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error')
    } finally { set({ filling: null }) }
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
    const ready = get().finals.find((f) => f.stage_id === doc?.id && f.layers.some((l) => l.id === 'plate' && l.method === 'projected' && l.status === 'running' && l.still_asset_id && !l.frames_done))
    if (ready && !get().projecting) await get().project(ready.id)
    const filled = get().finals.find((f) => f.stage_id === doc?.id && f.layers.some((l) => l.id === 'plate' && l.method === 'filled' && l.status === 'running' && l.still_asset_id && !l.frames_done))
    if (filled && !get().projecting && !get().filling) await get().fill(filled.id)       // PF1: the next step (or waiting on a keyframe's Fill)
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
    const picture = hasPictureSet(doc), built = !picture && hasBuiltSet(doc)               // SC3e; CW7: a built set's plate is the set
    const cam = st().activeCamera()
    const plate = picture || built || !cam ? null : plateChoice(cameraTravel(doc, cam.id, plan.times))
    const forShot = useMakeFor.getState().animate           // D125 (A1, WB1): made for the For chip's shot version, its takes land there
    const ok = await askConfirm({ title: 'Make the final shot?', okLabel: 'Split into layers',
      text: `The scene through ${st().activeCamera()?.name ?? 'the camera'}, frames ${doc.range.start}–${doc.range.end} at ${rate} fps: ${plan.times.length} frames at ${w}×${h}. ` +
        `${plan.layers.length} layers — the plate, ${figures} figure${figures === 1 ? '' : 's'}, ${props} prop${props === 1 ? '' : 's'} and the shadows. Stage renders their passes here (a minute or two)` +
        (picture ? ', and the plate from the picture set\'s picture; the other layers are made next.' : built ? ', and the plate from the built set (its baked and filled faces, no drift on any move); the other layers are made next.' : '; the layers are made from them next.') +
        (plate ? ` The plate is ${plate.method === 'filled' ? 'projected and filled (Klein fills what the still never saw at keyframes: a few minutes on the GPU)' : 'its still projected along the path'}: ${plate.why}.` : '') +
        (forShot ? ` The finished shot becomes a take of ${forLabel(forShot)}.` : ' Its clips become takes of the shots that use this camera.') })
    if (!ok) return null
    set({ making: { done: 0, total: 1, what: 'starting' } })
    try {
      const n = get().finals.filter((f) => f.stage_id === doc.id).length + 1
      let f = await makeFinal({ rate, name: `Final ${n}`, shotId: forShot?.shot_id ?? null, shotVersion: forShot?.version ?? null, plate: plate?.method ?? null,
        onProgress: (done, total, what) => set({ making: { done, total, what } }) })
      set({ finals: [f, ...get().finals] })
      if (picturePlated(f)) {                                                  // SC3e: the plate is the picture — rendered now, no job to wait for
        set({ making: { done: 0, total: f.frames, what: 'the plate from the picture' } })
        try { f = await picturePlate(f, (done, total) => set({ making: { done, total, what: 'the plate from the picture' } })); set({ finals: replace(get().finals, f) }) }
        catch (e) { s.toast(`${f.name}: the plate from the picture: ${(e as ApiError).detail ?? (e as Error).message ?? e} — Render the plate on its row`, 'error'); return f }
      }
      s.toast(`${f.name}: ${f.layers.length} layers, ${f.frames} frames each — their passes are on disk${builtPlated(f) ? ', the plate is the built set' : picturePlated(f) ? ', the plate is the picture' : ''}`, 'success')
      return f
    } catch (e) { s.toast(`Make the final shot: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error'); return null } finally { set({ making: null }) }
  },
  remove: async (id) => {
    try { await unwrap(http.DELETE('/finals/{fid}', { params: { path: { fid: id } } })); set({ finals: get().finals.filter((f) => f.id !== id) }) }
    catch (e) { useSession.getState().toast(`Delete the final: ${(e as ApiError).detail ?? e}`, 'error') }
  },
}))

// ---- D121: the final shot's next step (Performance › Final shot's foot, `stage.final.next`) ----------------------------------------------
export interface FinalStep { label: string; run: (() => void) | null; why?: string }
/** The next thing the stage's newest final needs, in the pipeline's order: make it, the plate, each character performed (the matte follows by
 *  itself), the assembly, the composition, then the Final level. A step that waits on the queue has no `run` and says why. */
export function nextFinalStep(stageId: string | null): FinalStep {
  const fs = useFinals.getState()
  if (fs.making) return { label: 'Splitting…', run: null, why: `${fs.making.what} · ${fs.making.done} / ${fs.making.total}` }
  const f = stageId ? newestFinal(fs.finals, stageId) : undefined
  if (!f) {
    const s = st()
    const why = !stageId || !s.current ? 'open a stage in Clay' : !s.activeCamera() ? 'the stage has no camera' : s.rendering ? 'rendering…' : undefined
    return { label: 'Make the final shot… ▶', run: why ? null : () => void fs.make(16), why }
  }
  const plate = f.layers.find((l) => l.kind === 'plate' && (l.status === 'passes' || l.status === 'failed'))
  if (plate) return fs.projecting === f.id ? { label: 'Rendering the plate…', run: null, why: 'the picture through its relief' }
    : { label: plate.method === 'picture' || plate.method === 'set' ? 'Render the plate ▶' : 'Make the plate ▶', run: () => void fs.plate(f.id) }
  const fig = f.layers.find((l) => l.kind === 'figure' && (l.status === 'passes' || l.status === 'failed'))
  if (fig) return { label: `Perform ${fig.name} ▶`, run: () => void fs.perform(f.id, fig.id) }
  const working = f.layers.find((l) => l.status === 'queued' || l.status === 'running')
  if (working) return { label: 'Working…', run: null, why: `${working.name}: ${working.status === 'queued' ? 'in the queue' : 'running'}` }
  if (assembling(f.id)) return { label: 'Assembling…', run: null, why: `${f.name}: the layers into the shot` }
  if (!f.assembled_at) return readyToAssemble(f) ? { label: 'Assemble ▶', run: () => void fs.assemble(f.id) } : { label: 'Assemble ▶', run: null, why: 'a layer is not made yet' }
  if (!fs.compositions[f.id]) return { label: 'Make the composition ▶', run: () => void fs.compose(f.id) }
  return { label: 'Open in Final ▸', run: () => fs.openFinal(f.id) }
}

// ---- D121 (AW3): one poll for every mounted view of the finals -------------------------------------------------------------------------
let polls = 0
let pollTimer: number | null = null
/** The stage's finals loaded (again when the stage changes) and polled every 3 s while any view of them is mounted — the Final shot card, the
 *  Final level's Shot section, the stepper — one timer for all of them (a tick reloads only while a layer, an assembly or a render moves). */
export function useFinalsPoll(stageId: string | null | undefined): void {
  useEffect(() => { void useFinals.getState().load() }, [stageId])
  useEffect(() => {
    polls++
    if (pollTimer === null) pollTimer = window.setInterval(() => void useFinals.getState().tick(), 3000)
    return () => { polls--; if (!polls && pollTimer !== null) { window.clearInterval(pollTimer); pollTimer = null } }
  }, [])
}
