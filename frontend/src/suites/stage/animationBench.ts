// D182 (C2b, propo02 04 §4.3): the animation workshop — an animation is an asset of the author's. Opened on the animation bench (the
// project's one stage of purpose `animation`, made again each time: a figure standing at the origin playing the animation as its one
// block), it is edited with the tracks' means (C2: corrections and keys over the block, its trims, speed, loops, mirror, blends, a second
// clip dropped after it, the range cut) and written back — *Save* over the animation (the project's, revision-guarded; the library's, its
// file), *Save as…* a new one of the project's. *New animation…* starts from a figure standing still over N frames; a downloaded clip is
// made one's own with *Make it mine* (a copy on the mannequin rig, its file, clip and licence kept — D17). The tile's picture is the
// figure's first frame, rendered here and uploaded once the figure is drawn.
import { api, http, sha256Hex, unwrap } from '../../api/client'
import type { StageDoc } from '../../api/types'
import { askText, useSession } from '../../store/session'
import { keyframesOf, sampleFigure, type ObjectKey } from './anim'
import { putTemplates, rangeKeys, removeTemplate, templateToLibrary, useTemplates } from './blockEdit'
import { blockKeys, blockRuns, blocksReady, hipOf, templatesChanged, type AnimationTemplate, type MotionBlock } from './blocks'
import { thinKeys } from './motion/bake'
import { clipsOf, type MotionClip, type MotionFile } from './motion/library'
import { useMotion } from './motion/motionStore'
import { st, useStage } from './stageStore'

export type AnimRef = { kind: 'template'; id: string } | { kind: 'clip'; file: string; clip: string }
export const sameRef = (a: AnimRef | null, b: AnimRef | null): boolean => !!a && !!b && JSON.stringify(a) === JSON.stringify(b)

const toast = (t: string, kind: 'success' | 'error' | 'info' = 'info') => useSession.getState().toast(t, kind)
const newId = (p: string) => `${p}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`

/** What is on the bench now: the animation, the figure playing it, the bench stage. */
let bench: { ref: AnimRef; figure: string; stage: string } | null = null
export const onBench = (): { ref: AnimRef; figure: string; stage: string } | null => bench

export async function templateById(id: string): Promise<AnimationTemplate | null> {
  const t = useTemplates.getState()
  if (!t.loaded) await t.load()
  const { items, library } = useTemplates.getState()
  return items.find((x) => x.id === id) ?? library.find((x) => x.id === id) ?? null
}
export const inLibrary = (id: string): boolean => useTemplates.getState().library.some((x) => x.id === id) && !useTemplates.getState().items.some((x) => x.id === id)

export async function clipByRef(file: string, clip: string): Promise<{ file: MotionFile; clip: MotionClip } | null> {
  const m = useMotion.getState()
  if (!m.loaded) await m.refresh()
  const f = useMotion.getState().files.find((x) => x.id === file)
  if (!f) return null
  const have = useMotion.getState().clips[f.id]
  const clips = Array.isArray(have) ? have : await clipsOf(f).catch(() => [] as MotionClip[])
  if (!Array.isArray(have) && clips.length) useMotion.setState({ clips: { ...useMotion.getState().clips, [f.id]: clips } })
  const c = clips.find((x) => x.name === clip) ?? (f.ext === 'fbx' ? { file: f, name: f.name, duration: 0, rig: null, rootMotion: false } : undefined)
  return c ? { file: f, clip: c } : null
}

/** The animation's name as the tiles and the bench say it. */
export async function nameOf(ref: AnimRef): Promise<string> {
  if (ref.kind === 'template') return (await templateById(ref.id))?.name ?? 'an animation'
  return ref.clip
}

/** The bench opened on an animation: the stage made again, the animation as the figure's one block, the range its frames, the figure
 *  selected at frame 0. False when the animation is not there (any more). */
export async function openAnimationBench(ref: AnimRef): Promise<boolean> {
  const t = ref.kind === 'template' ? await templateById(ref.id) : null
  const c = ref.kind === 'clip' ? await clipByRef(ref.file, ref.clip) : null
  if (!t && !c) { toast('The animation is not in the library any more', 'error'); return false }
  const fps = useSession.getState().project?.format?.fps ?? 24
  const name = t?.name ?? c!.clip.name
  const frames = t ? t.frames : Math.max(2, Math.round((c!.clip.duration || 1) * fps))
  let stage: StageDoc
  try { stage = await unwrap(http.POST('/stages/animation-bench', { body: { name, frames } })) }
  catch (e) { toast(`The animation bench: ${(e as { detail?: string }).detail ?? e}`, 'error'); return false }
  await st().open(stage.id)
  const doc = useStage.getState().current
  const fig = doc?.objects.find((o) => o.kind === 'mannequin')
  if (!doc || !fig || doc.id !== stage.id) return false
  const block: MotionBlock = { id: newId('blk'), source: t ? { kind: 'template', id: t.id, clip: t.name } : { kind: 'library', id: c!.file.id, clip: c!.clip.name },
    start: 0, trim_in: 0, trim_out: null, loops: 1, speed: 1, blend_in: 0, blend_out: 0, in_place: false, foot_lock: true, ground: true, mirror: false, path: false, length: 0 } as MotionBlock
  const probe = { ...doc, tracks: { ...(doc.tracks ?? {}), [fig.id]: [block] } }
  const keys = await blockKeys(probe, fig.id, block.id)
  if (!keys?.length) { toast(`${name} could not be played on the bench`, 'error'); return false }
  const length = keys[keys.length - 1].frame - keys[0].frame + 1
  st().addBlock(fig.id, { ...block, length })
  st().setRange(0, Math.max(1, length - 1))
  st().select(fig.id)
  st().setFrame(0)
  bench = { ref, figure: fig.id, stage: stage.id }
  if (t?.try_on) st().bindFigure(fig.id, t.try_on)                           // D183 (C2c): the character it is tried on — its body and shell
  if (t && !t.thumb_asset_id) void thumbnailLater(t.id, fig.id)
  return true
}

export function closeAnimationBench(): void { bench = null }

/** D183 (C2c): who the bench figure is — the character whose shell it wears for this animation (null: the dummy). */
export function tryOnWho(): string | null {
  if (!bench) return null
  const figure = bench.figure
  return useStage.getState().current?.objects.find((o) => o.id === figure)?.profile_id ?? null
}

/** D183 (C2c): *Try it on ‹character›* — the bench figure bound to the character (its body and shell follow), remembered on the
 *  animation; null: the dummy, an animation being nobody's. */
export async function tryOn(profileId: string | null): Promise<void> {
  if (!bench) return
  st().bindFigure(bench.figure, profileId)
  if (bench.ref.kind !== 'template') return
  const t = await templateById(bench.ref.id)
  if (!t || (t.try_on ?? null) === profileId) return
  await patchAnimation(t, { try_on: profileId })
}

/** A template's fields written — the library's by its own route, the project's with the list. */
async function patchAnimation(t: AnimationTemplate, patch: Partial<AnimationTemplate>): Promise<boolean> {
  const next = { ...t, ...patch }
  if (inLibrary(t.id)) {
    try {
      const r = await unwrap(http.PUT('/stages/animations/library/{aid}', { params: { path: { aid: t.id } }, body: next as never }))
      useTemplates.setState({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[], loaded: true })
      templatesChanged()
      return true
    } catch (e) { toast(`Animation: ${(e as { detail?: string }).detail ?? e}`, 'error'); return false }
  }
  return putTemplates(useTemplates.getState().items.map((x) => (x.id === t.id ? next : x)))
}

/** The figure's first frame on the bench, once the figure is drawn, as the animation's tile picture. */
async function thumbnailLater(aid: string, figureId: string): Promise<void> {
  await new Promise((r) => setTimeout(r, 2500))
  if (bench?.figure !== figureId) return
  const { viewport } = await import('./stageCommands')
  const blob = await viewport.snapshot?.(figureId)
  if (!blob) return
  try {
    const sha = await sha256Hex(await blob.arrayBuffer())
    await api.putBlob(sha, blob)
    const r = await unwrap(http.POST('/stages/animations/{aid}/thumbnail', { params: { path: { aid } }, body: { blob: sha } }))
    useTemplates.setState({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[], loaded: true })
  } catch { /* the tile keeps its glyph */ }
}

/** The bench's track — the figure's clips, keys and corrections over the range — as an animation's keys, re-based to frame 0 and thinned. */
export async function benchKeys(): Promise<ObjectKey[] | null> {
  if (!bench) return null
  const keys = await rangeKeys(bench.figure)
  if (!keys.length) return null
  const f0 = keys[0].frame
  return thinKeys(keys).map((k) => ({ ...k, frame: k.frame - f0 }))
}

/** A template's record from the bench's track (its name and lineage kept, the keys new). */
async function fromBench(base: Partial<AnimationTemplate> & { name: string }, keys: ObjectKey[]): Promise<AnimationTemplate> {
  const doc = st().current, o = doc?.objects.find((x) => x.id === bench?.figure)
  return { id: newId('anm'), rig: 'mannequin', fps: doc?.size.fps || 24, hip: o ? hipOf(o) : 0.91, source: { stage_id: doc?.id ?? null, object_id: bench?.figure ?? null, start: doc?.range.start ?? 0, end: doc?.range.end ?? 0 },
    thumb_asset_id: null, ...base, keys, frames: (keys[keys.length - 1]?.frame ?? 0) + 1 } as unknown as AnimationTemplate
}

/** *Save*: the animation written over with the bench's track — the project's through the list (its revision), the library's through its file. */
export async function saveAnimationOver(): Promise<boolean> {
  if (!bench || bench.ref.kind !== 'template') return false
  const t = await templateById(bench.ref.id)
  const keys = await benchKeys()
  if (!t || !keys) { toast('Nothing to save: the bench is empty', 'info'); return false }
  const next = await fromBench({ ...t }, keys)
  if (inLibrary(t.id)) {
    try {
      const r = await unwrap(http.PUT('/stages/animations/library/{aid}', { params: { path: { aid: t.id } }, body: next as never }))
      useTemplates.setState({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[], loaded: true })
      templatesChanged()
    } catch (e) { toast(`Save: ${(e as { detail?: string }).detail ?? e}`, 'error'); return false }
  } else if (!(await putTemplates(useTemplates.getState().items.map((x) => (x.id === t.id ? next : x))))) return false
  toast(`${t.name} saved — ${next.frames} frames`, 'success')
  return true
}

/** *Save as…*: a new animation of the project's from the bench's track; a downloaded clip's copy keeps its file, clip and licence (D17). */
export async function saveAnimationAs(name: string): Promise<AnimationTemplate | null> {
  if (!bench) return null
  const keys = await benchKeys()
  if (!keys) { toast('Nothing to save: the bench is empty', 'info'); return null }
  const prov = bench.ref.kind === 'clip' ? await clipByRef(bench.ref.file, bench.ref.clip) : null
  const t = await fromBench({ name }, keys)
  if (prov) (t as unknown as { source: Record<string, unknown> }).source = { ...(t as unknown as { source: Record<string, unknown> }).source, file_id: prov.file.id, clip: prov.clip.name, licence: prov.file.licence }
  if (!(await putTemplates([...useTemplates.getState().items, t]))) return null
  toast(`${name} saved — under Mine; it applies to any figure`, 'success')
  bench = { ...bench, ref: { kind: 'template', id: t.id } }
  void thumbnailLater(t.id, bench.figure)
  return t
}

/** *Make it mine*: the downloaded clip on the bench as an animation of the author's (a copy on the mannequin rig). */
export async function makeMine(): Promise<AnimationTemplate | null> {
  if (!bench || bench.ref.kind !== 'clip') return null
  return saveAnimationAs(bench.ref.clip)
}

const STAND: ObjectKey = { frame: 0, ease: 'ease', transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, pose: { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null } }
/** *New animation…*: a figure standing still over N seconds, saved as the project's and opened on the bench. */
export async function newAnimation(name: string, seconds: number): Promise<AnimationTemplate | null> {
  const fps = useSession.getState().project?.format?.fps ?? 24
  const frames = Math.max(2, Math.round(seconds * fps))
  const t = { id: newId('anm'), name, rig: 'mannequin', frames, fps, hip: 0.91, keys: [STAND, { ...STAND, frame: frames - 1 }], source: {}, thumb_asset_id: null } as unknown as AnimationTemplate
  await useTemplates.getState().load()
  if (!(await putTemplates([...useTemplates.getState().items, t]))) return null
  return t
}

export async function renameAnimation(ref: AnimRef, name: string): Promise<void> {
  if (ref.kind !== 'template' || !name.trim()) return
  const t = await templateById(ref.id)
  if (!t) return
  if (inLibrary(t.id)) {
    try {
      const r = await unwrap(http.PUT('/stages/animations/library/{aid}', { params: { path: { aid: t.id } }, body: { ...t, name: name.trim() } as never }))
      useTemplates.setState({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[], loaded: true })
      templatesChanged()
    } catch (e) { toast(`Rename: ${(e as { detail?: string }).detail ?? e}`, 'error') }
    return
  }
  await putTemplates(useTemplates.getState().items.map((x) => (x.id === t.id ? { ...x, name: name.trim() } : x)))
}

/** A copy of the animation, the project's, named after it. */
export async function duplicateAnimation(ref: AnimRef): Promise<AnimationTemplate | null> {
  if (ref.kind !== 'template') return null
  const t = await templateById(ref.id)
  if (!t) return null
  const copy = { ...t, id: newId('anm'), name: `${t.name} copy`, thumb_asset_id: t.thumb_asset_id ?? null } as AnimationTemplate
  return (await putTemplates([...useTemplates.getState().items, copy])) ? copy : null
}

export async function removeAnimation(ref: AnimRef): Promise<void> {
  if (ref.kind !== 'template') return
  const t = await templateById(ref.id)
  if (!t) return
  await removeTemplate(t, inLibrary(t.id) ? 'library' : 'project')
}

export async function animationToLibrary(ref: AnimRef): Promise<void> {
  if (ref.kind !== 'template') return
  const t = await templateById(ref.id)
  if (t && !inLibrary(t.id)) await templateToLibrary(t)
}

/** The name and the seconds for *New animation…*, asked in two short dialogs. */
export async function askNewAnimation(): Promise<{ name: string; seconds: number } | null> {
  const name = await askText({ title: 'New animation', placeholder: 'its name', text: 'A figure standing still over a few seconds: pose it at the frames you want, then Save.' })
  if (!name?.trim()) return null
  const secs = await askText({ title: `${name.trim()} — how long?`, placeholder: 'seconds', initial: '4', text: 'Seconds (the project\'s fps); the range can be cut on the bench.' })
  const n = Number(secs)
  if (!secs || !Number.isFinite(n) || n <= 0) return null
  return { name: name.trim(), seconds: Math.min(60, n) }
}

/** The figure's keys over the whole range, for the tests and the driver (what Save would write). */
export async function previewKeys(doc: StageDoc, oid: string): Promise<ObjectKey[]> {
  await blocksReady(doc)
  const o = doc.objects.find((x) => x.id === oid)
  if (!o) return []
  const layer = keyframesOf(doc).objects[oid], runs = blockRuns(doc, oid, layer)
  const out: ObjectKey[] = []
  for (let f = doc.range.start; f <= doc.range.end; f++) { const s = sampleFigure(o, layer, runs, f); out.push({ frame: f, ease: 'linear', transform: s.transform, pose: s.pose ?? null }) }
  return out
}
