// P13 / ST4 (D81, 16 §8): keyframes, pure. The document keeps `keyframes.camera[camId]` and `keyframes.objects[objId]` as sorted lists
// of keys; a key holds the state at its frame and how to reach it from the previous key (`linear` or `ease` = smoothstep). Between
// keys the state interpolates; before the first and after the last it holds. Without keys an object or camera is what the document
// says (the base state). Frames are integers at the project's fps (D18: 24); `range {start, end}` is inclusive.
// CS3 (proto01_UIcast 06 §2.10, D136 U19): `keyframes.skeleton[objId]` — skeleton keys: from a key's frame the figure's body is the key's
// (or, with none, the figure's own: Cast's), reached over the key's transition from the body before it; before the first key its own.
import type { StageCamera, StageDoc, StageObject } from '../../api/types'

export type Ease = 'linear' | 'ease'
export interface CameraKey { frame: number; ease: Ease; pos: number[]; target: number[]; focal_mm: number }
export interface ObjectKey { frame: number; ease: Ease; transform: { pos: number[]; rot: number[]; scale: number[] }; pose?: { preset?: string | null; joints: Record<string, number[]>; extra?: Record<string, number[]> } | null }
/** CS3: from `frame` the figure's body is `body` (null: the figure's own — its Cast version's, whatever it is now), reached over
 *  `transition` frames from the body before it (0: a cut). */
export interface SkeletonKey { frame: number; transition: number; body: StageObject['body'] | null }
export interface Keyframes { camera: Record<string, CameraKey[]>; objects: Record<string, ObjectKey[]>; skeleton?: Record<string, SkeletonKey[]> }

export const EMPTY_KEYS: Keyframes = { camera: {}, objects: {} }
export const smoothstep = (t: number) => t * t * (3 - 2 * t)
const lerp = (a: number, b: number, w: number) => a + (b - a) * w
const lerpV = (a: number[], b: number[], w: number) => a.map((x, i) => lerp(x, b[i] ?? x, w))
/** Rotations in degrees take the short way round. */
const lerpDeg = (a: number[], b: number[], w: number) => a.map((x, i) => { let d = ((b[i] ?? x) - x) % 360; if (d > 180) d -= 360; if (d < -180) d += 360; return x + d * w })

/** The document's keyframes with every list sorted and typed (a document from the server carries them as plain JSON). */
export function keyframesOf(doc: Pick<StageDoc, 'keyframes'>): Keyframes {
  const k = (doc.keyframes ?? {}) as Partial<Keyframes>
  const sortBy = <T extends { frame: number }>(xs: T[] | undefined) => [...(xs ?? [])].sort((a, b) => a.frame - b.frame)
  return { camera: Object.fromEntries(Object.entries(k.camera ?? {}).map(([id, ks]) => [id, sortBy(ks)])), objects: Object.fromEntries(Object.entries(k.objects ?? {}).map(([id, ks]) => [id, sortBy(ks)])),
    skeleton: Object.fromEntries(Object.entries(k.skeleton ?? {}).filter(([, ks]) => ks?.length).map(([id, ks]) => [id, sortBy(ks)])) }
}

/** The two keys around a frame and the eased weight between them; null without keys. */
export function bracket<T extends { frame: number; ease: Ease }>(keys: T[], frame: number): { a: T; b: T; w: number } | null {
  if (!keys.length) return null
  if (frame <= keys[0].frame) return { a: keys[0], b: keys[0], w: 0 }
  const last = keys[keys.length - 1]
  if (frame >= last.frame) return { a: last, b: last, w: 0 }
  let i = 0
  while (i + 1 < keys.length && keys[i + 1].frame <= frame) i++
  const a = keys[i], b = keys[i + 1]
  const t = b.frame === a.frame ? 0 : (frame - a.frame) / (b.frame - a.frame)
  return { a, b, w: b.ease === 'ease' ? smoothstep(t) : t }
}

export function sampleCamera(cam: StageCamera, keys: CameraKey[] | undefined, frame: number): StageCamera {
  const br = keys ? bracket(keys, frame) : null
  if (!br) return cam
  const { a, b, w } = br
  return { ...cam, pos: lerpV(a.pos, b.pos, w), target: lerpV(a.target, b.target, w), focal_mm: lerp(a.focal_mm, b.focal_mm, w) }
}

export function sampleObject(o: StageObject, keys: ObjectKey[] | undefined, frame: number): StageObject {
  const br = keys ? bracket(keys, frame) : null
  if (!br) return o
  const { a, b, w } = br
  const transform = { pos: lerpV(a.transform.pos, b.transform.pos, w), rot: lerpDeg(a.transform.rot, b.transform.rot, w), scale: lerpV(a.transform.scale, b.transform.scale, w) }
  // a pose preset switches at the halfway point; explicit joints interpolate when both keys carry the same joint names
  let pose = o.pose
  const pa = a.pose ?? o.pose, pb = b.pose ?? o.pose
  if (pa || pb) {
    const near = w < 0.5 ? pa : pb
    const ja = pa?.joints ?? {}, jb = pb?.joints ?? {}
    const names = Object.keys(ja).filter((n) => n in jb)
    // CA1: two keys that both carry every joint (a library clip's, a preset keyed on a keyed figure) interpolate across a preset change too
    const full = names.length >= 12
    const joints = names.length && (pa?.preset === pb?.preset || full) ? Object.fromEntries(names.map((n) => [n, lerpDeg(ja[n], jb[n], w)])) : (near?.joints ?? {})
    // CA1: the Detailed level's own bones interpolate the same way (a bone only one key has holds that key's turn)
    const xa = pa?.extra ?? {}, xb = pb?.extra ?? {}
    const extra = Object.fromEntries([...new Set([...Object.keys(xa), ...Object.keys(xb)])].map((n) => [n, xa[n] && xb[n] ? lerpDeg(xa[n], xb[n], w) : (w < 0.5 ? xa[n] ?? xb[n] : xb[n] ?? xa[n])]))
    pose = { preset: near?.preset ?? 'stand', joints, extra }
  }
  return { ...o, transform, pose }
}

type Body = NonNullable<StageObject['body']>
/** Two bodies blended factor by factor (the hands at rest too); what is not a number switches at the half. */
function lerpBody(a: Body, b: Body, w: number): Body {
  const blend = (x: Record<string, unknown>, y: Record<string, unknown>): Record<string, unknown> => {
    const out: Record<string, unknown> = { ...(w < 0.5 ? x : y) }
    for (const key of Object.keys(y)) {
      const u = x[key], v = y[key]
      if (typeof u === 'number' && typeof v === 'number') out[key] = lerp(u, v, w)
      else if (u && v && typeof u === 'object' && typeof v === 'object' && !Array.isArray(u)) out[key] = blend(u as Record<string, unknown>, v as Record<string, unknown>)
    }
    return out
  }
  return blend(a as unknown as Record<string, unknown>, b as unknown as Record<string, unknown>) as unknown as Body
}

/** CS3: the figure's body at a frame under its skeleton keys — the last key at or before it, reached (smoothstep) over its transition from
 *  the body before it; before the first key, or without keys, the figure's own. */
export function sampleBody(o: StageObject, keys: SkeletonKey[] | undefined, frame: number): StageObject {
  if (!keys?.length) return o
  const own = o.body ?? null
  const of = (k: SkeletonKey) => k.body ?? own
  let i = -1
  while (i + 1 < keys.length && keys[i + 1].frame <= frame) i++
  if (i < 0) return o
  const k = keys[i], to = of(k), from = i > 0 ? of(keys[i - 1]) : own
  const t = k.transition > 0 ? Math.min(1, (frame - k.frame) / k.transition) : 1
  const body = t >= 1 || !from || !to ? to : lerpBody(from, to, smoothstep(t))
  return body === own ? o : { ...o, body }
}

/** CS3: a body's fingerprint (FNV-1a over its fields in order, numbers to 4 places) — a final's guide stamps one per frame. */
export function bodyHash(body: unknown): string {
  const stable = (v: unknown): string => typeof v === 'number' ? String(Math.round(v * 1e4) / 1e4) : v === null || typeof v !== 'object' ? JSON.stringify(v ?? null)
    : Array.isArray(v) ? `[${v.map(stable).join(',')}]` : `{${Object.keys(v).sort().map((key) => `${JSON.stringify(key)}:${stable((v as Record<string, unknown>)[key])}`).join(',')}}`
  const s = stable(body)
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0 }
  return h.toString(16).padStart(8, '0')
}

/** The document as it stands at a frame: keyed cameras and objects sampled (CS3: the figures' bodies too), the rest as they are. */
export function sampleDoc(doc: StageDoc, frame: number): StageDoc {
  const k = keyframesOf(doc), sk = k.skeleton ?? {}
  if (!Object.keys(k.camera).length && !Object.keys(k.objects).length && !Object.keys(sk).length) return doc
  return { ...doc, cameras: doc.cameras.map((c) => sampleCamera(c, k.camera[c.id], frame)), objects: doc.objects.map((o) => sampleBody(sampleObject(o, k.objects[o.id], frame), sk[o.id], frame)) }
}

/** A key written at its frame (replacing one already there), the list kept sorted. */
export function withKey<T extends { frame: number }>(keys: T[] | undefined, key: T): T[] {
  return [...(keys ?? []).filter((k) => k.frame !== key.frame), key].sort((a, b) => a.frame - b.frame)
}
export function withoutKey<T extends { frame: number }>(keys: T[] | undefined, frame: number): T[] {
  return (keys ?? []).filter((k) => k.frame !== frame)
}
/** Every frame that has a key on the camera or on any object — the strip's markers. */
export function keyedFrames(k: Keyframes, cameraId: string | null): number[] {
  const out = new Set<number>()
  if (cameraId) for (const key of k.camera[cameraId] ?? []) out.add(key.frame)
  for (const ks of Object.values(k.objects)) for (const key of ks) out.add(key.frame)
  for (const ks of Object.values(k.skeleton ?? {})) for (const key of ks) out.add(key.frame)
  return [...out].sort((a, b) => a - b)
}
/** The previous / next keyed frame from `frame`, or null. */
export function neighbourKey(frames: number[], frame: number, dir: -1 | 1): number | null {
  const c = dir < 0 ? frames.filter((f) => f < frame) : frames.filter((f) => f > frame)
  return c.length ? (dir < 0 ? c[c.length - 1] : c[0]) : null
}
/** The clip's frame count for a range, snapped to the model's n·step + 1 (LTX: 8n + 1) without exceeding the range. */
export function clipFrames(start: number, end: number, step = 8): number {
  const n = Math.max(2, end - start + 1)
  return Math.max(step + 1, Math.floor((n - 1) / step) * step + 1)
}
