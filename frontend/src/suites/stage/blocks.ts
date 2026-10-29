// U5 (D157 G8; proto01_UI2 04 §3.2, 06 §2.4): a figure's clip blocks evaluated into keys — the same steps applying a clip took before
// (retarget onto the figure's hip, foot lock, the floor contact, loops along its path, in place, baked from where the figure stands), now
// run per block and cached by everything they read (the block, the figure's body and path, where it starts), so moving, looping or
// re-timing a block re-flows it and nothing is baked into the figure's keys. The evaluator (anim.ts) stays synchronous: a block not
// evaluated yet is left out (the figure keeps to its keys) and its evaluation is started; `blocksReady` waits for every block of a
// document — the renders call it before they sample a frame. Blocks start where the one before them ends, so they are evaluated in order.
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import type { StageDoc, StageObject } from '../../api/types'
import { bodyHash, keyframesOf, sampleFigure, setBlockRuns, type BlockRun, type ObjectKey } from './anim'
import { bodyDims } from './body'
import { mirrorJoints } from './ik'
import { bakeAlongPath, bakeKeys, repeatLoop } from './motion/bake'
import { footContact } from './motion/contact'
import { footLock } from './motion/footlock'
import { listFiles, retargetClip, type MotionFile } from './motion/library'
import { measure } from './motion/path'
import { walkAlong } from './motion/walkpath'

export type MotionBlock = NonNullable<StageDoc['tracks']>[string][number]
export type AnimationTemplate = { id: string; name: string; frames: number; fps: number; hip: number; keys: ObjectKey[] }

/** The figure's hip above its ankles (its own body's), as the retarget scales the root by. */
export function hipOf(o: Pick<StageObject, 'body'>): number {
  const d = bodyDims(o.body as never)
  return (0.04 + d.limbs.thigh + d.limbs.shin) * d.scale
}

const round = (v: number[]) => v.map((x) => Math.round(x * 1000) / 1000)
/** Everything a block's evaluation reads: a change to any of it evaluates the block again. */
export function blockKey(doc: Pick<StageDoc, 'size'>, o: Pick<StageObject, 'body' | 'path'>, b: MotionBlock, at: Pick<StageObject, 'transform'>): string {
  const { id: _id, length: _len, blend_in: _bi, blend_out: _bo, ...made } = b
  void _id; void _len; void _bi; void _bo
  return JSON.stringify([made, doc.size?.fps ?? 24, bodyHash(o.body ?? null), b.path ? o.path ?? null : null, round(at.transform.pos), round(at.transform.rot), round(at.transform.scale)])
}

// ---- the cache ----
const cache = new Map<string, { start: number; end: number; keys: ObjectKey[] }>()
const pending = new Map<string, Promise<void>>()
const failed = new Set<string>()                                         // evaluations that failed: tried again only when what they read changes
const CACHE_MAX = 256

interface BlocksState { version: number; errors: Record<string, string>; bump: () => void }
/** The evaluated blocks moved on (`version`): the viewport syncs again. A block that could not be evaluated keeps its reason. */
export const useBlocks = create<BlocksState>()((set, get) => ({ version: 0, errors: {}, bump: () => set({ version: get().version + 1 }) }))

let files: Promise<MotionFile[]> | null = null
const fileOf = async (id: string): Promise<MotionFile> => {
  files ??= listFiles().then((r) => r.items).catch((e) => { files = null; throw e })
  let f = (await files).find((x) => x.id === id)
  if (!f) { files = null; f = (await (files = listFiles().then((r) => r.items))).find((x) => x.id === id) }
  if (!f) throw new Error('its motion file is not in the library any more')
  return f
}
let templates: Promise<AnimationTemplate[]> | null = null
/** The templates moved (saved, removed): read them again. */
export function templatesChanged(): void { templates = null }
const templateOf = async (id: string): Promise<AnimationTemplate> => {
  templates ??= unwrap(http.GET('/stages/animations')).then((r) => [...r.items, ...r.library] as unknown as AnimationTemplate[]).catch((e) => { templates = null; throw e })
  const t = (await templates).find((x) => x.id === id)
  if (!t) throw new Error('its animation is not in the project or the library')
  return t
}

/** A library clip's block: the steps `motionStore.apply` ran, from where the figure stands at the block's start. */
async function libraryRun(doc: StageDoc, o: StageObject, b: MotionBlock, at: StageObject): Promise<ObjectKey[]> {
  const fps = doc.size?.fps || 24
  const clip = { file: await fileOf(b.source.id), name: b.source.clip, duration: 0, rig: null, rootMotion: false }
  const r = await retargetClip(clip, { fps, start: b.trim_in, end: b.trim_out ?? undefined, speed: b.speed, hip: hipOf(o) })
  let raw = r.frames
  if (b.mirror) raw = raw.map((f) => ({ ...f, joints: mirrorJoints(f.joints), offset: [-f.offset[0], f.offset[1], f.offset[2]] as [number, number, number] }))
  const path = b.path && o.path && o.path.length >= 2 ? (o.path as number[][]).map((p) => [p[0], p[1]] as [number, number]) : null
  const lock = (fr: typeof raw) => { const locked = b.foot_lock ? footLock(fr, o.body as never) : fr; return b.ground ? footContact(locked, o.body as never) : locked }
  let frames = lock(raw)
  let times = Math.max(1, b.loops)
  if (b.loops === 0 && path) {                                            // as many loops as its travel needs to cover the path
    const per = Math.hypot(frames[frames.length - 1].offset[0] - frames[0].offset[0], frames[frames.length - 1].offset[2] - frames[0].offset[2]) * (at.transform.scale[1] ?? 1)
    times = per > 0.05 ? Math.min(30, Math.ceil(measure(path).length / per)) : 1
  }
  if (times > 1) frames = lock(repeatLoop(raw, times))
  if (b.in_place && !path) frames = frames.map((f) => ({ ...f, offset: [0, f.offset[1], 0] as [number, number, number] }))
  return path ? (b.foot_lock ? walkAlong(frames, at.transform, b.start, path, o.body as never) : bakeAlongPath(frames, at.transform, b.start, path)) : bakeKeys(frames, at.transform, b.start)
}

/** A template's block: its keys re-based to where the figure stands (its position and facing), the root scaled by the figure's hip over
 *  the one it was saved from, re-timed by the speed, repeated by the loops. */
export function templateRun(t: Pick<AnimationTemplate, 'frames' | 'hip' | 'keys'>, o: Pick<StageObject, 'body'>, b: Pick<MotionBlock, 'start' | 'loops' | 'speed' | 'mirror' | 'in_place'>, at: Pick<StageObject, 'transform'>): ObjectKey[] {
  const keys = [...t.keys].sort((x, y) => x.frame - y.frame)
  if (!keys.length) return []
  const first = keys[0].transform, yaw = ((at.transform.rot[1] ?? 0) - (first.rot[1] ?? 0)) * Math.PI / 180
  const k = hipOf(o) / (t.hip || 0.91), c = Math.cos(yaw), s = Math.sin(yaw)
  const last = keys[keys.length - 1].transform
  const travel = [(last.pos[0] - first.pos[0]) * k, (last.pos[2] - first.pos[2]) * k]
  const out: ObjectKey[] = []
  for (let i = 0; i < Math.max(1, b.loops); i++) {
    for (const key of keys) {
      if (i > 0 && key === keys[0]) continue                              // a loop's first key is the last one's end
      let dx = (key.transform.pos[0] - first.pos[0]) * k + travel[0] * i, dz = (key.transform.pos[2] - first.pos[2]) * k + travel[1] * i
      if (b.mirror) dx = -dx
      if (b.in_place) { dx = 0; dz = 0 }
      const pos = [at.transform.pos[0] + dx * c + dz * s, at.transform.pos[1] + (key.transform.pos[1] - first.pos[1]) * k, at.transform.pos[2] - dx * s + dz * c]
      const rot = [key.transform.rot[0], at.transform.rot[1] + ((b.mirror ? -1 : 1) * ((key.transform.rot[1] ?? 0) - (first.rot[1] ?? 0))), key.transform.rot[2]]
      const pose = key.pose && b.mirror ? { ...key.pose, joints: mirrorJoints(key.pose.joints) } : key.pose
      out.push({ ...key, frame: b.start + Math.round((key.frame + i * (t.frames - 1)) / b.speed), transform: { pos, rot, scale: at.transform.scale }, pose })
    }
  }
  return out
}

async function evaluate(doc: StageDoc, o: StageObject, b: MotionBlock, at: StageObject): Promise<ObjectKey[]> {
  if (b.source.kind === 'template') return templateRun(await templateOf(b.source.id), o, b, at)
  return libraryRun(doc, o, b, at)
}

function schedule(key: string, doc: StageDoc, o: StageObject, b: MotionBlock, at: StageObject): void {
  if (pending.has(key)) return
  const p = evaluate(doc, o, b, at).then((keys) => {
    if (!keys.length) throw new Error('the clip came to no frames')
    if (cache.size >= CACHE_MAX) cache.delete(cache.keys().next().value as string)
    cache.set(key, { start: keys[0].frame, end: keys[keys.length - 1].frame, keys })
    const { [b.id]: _gone, ...errors } = useBlocks.getState().errors
    void _gone
    useBlocks.setState({ errors })
  }).catch((e) => { failed.add(key); useBlocks.setState({ errors: { ...useBlocks.getState().errors, [b.id]: e instanceof Error ? e.message : String(e) } }) })
    .finally(() => { pending.delete(key); useBlocks.getState().bump() })
  pending.set(key, p)
}

/** A figure's evaluated blocks in their order — the ones evaluated so far; the first one not evaluated yet starts its evaluation (the
 *  blocks after it wait: they start where it ends). */
export function blockRuns(doc: StageDoc, objectId: string, layer?: ObjectKey[]): BlockRun[] {
  const blocks = [...(doc.tracks?.[objectId] ?? [])].sort((a, b) => a.start - b.start)
  const o = doc.objects.find((x) => x.id === objectId)
  if (!o || !blocks.length) return []
  const out: BlockRun[] = []
  for (const b of blocks) {
    const at = sampleFigure(o, layer, out, b.start)
    const key = blockKey(doc, o, b, at)
    const hit = cache.get(key)
    if (!hit) {
      if (!failed.has(key)) schedule(key, doc, o, b, at)
      break
    }
    out.push({ id: b.id, start: hit.start, end: hit.end, blendIn: b.blend_in, keys: hit.keys })
  }
  return out
}
setBlockRuns(blockRuns)

/** Every block of the document evaluated (a render waits for this before it samples its frames). */
export async function blocksReady(doc: StageDoc): Promise<void> {
  for (let pass = 0; pass < 64; pass++) {
    const k = keyframesOf(doc)
    for (const id of Object.keys(doc.tracks ?? {})) blockRuns(doc, id, k.objects[id])
    if (![...pending.keys()].length) return
    await Promise.allSettled([...pending.values()])
  }
}

/** A block's evaluated keys (for *Bake to keys* and its length), once evaluated. */
export async function blockKeys(doc: StageDoc, objectId: string, blockId: string): Promise<ObjectKey[] | null> {
  await blocksReady(doc)
  return blockRuns(doc, objectId, keyframesOf(doc).objects[objectId]).find((r) => r.id === blockId)?.keys ?? null
}
