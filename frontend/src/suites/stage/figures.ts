// D93 (C8): Stage figures bound to Cast characters — the pure parts: where a figure stands on screen (its position through the render
// camera, so "figure 1" is the left-most, as the prompt says), the figure mentions a StageShot sends (left to right, hidden figures left
// out), and Make frame ▸ in Stage's pre-binding of a shot's speakers to the stage's figures when the counts match. No three.js: the
// projection is the camera's own maths, so the tests read it without a canvas.
import type { Profile, StageCamera, StageObject } from '../../api/types'

type V3 = [number, number, number]
const sub = (a: number[], b: number[]): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const dot = (a: number[], b: number[]) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const cross = (a: number[], b: number[]): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
const norm = (a: V3): V3 => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l] }

/** A world point's horizontal place in the camera's view (left < 0 < right; the perspective divide, roll included), or null behind it. */
export function screenX(p: number[], cam: Pick<StageCamera, 'pos' | 'target' | 'roll'>): number | null {
  const f = norm(sub(cam.target, cam.pos))
  let r = norm(cross(f, [0, 1, 0]))
  let u = cross(r, f)
  if (cam.roll) { const a = (cam.roll * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a); [r, u] = [norm([r[0] * c + u[0] * s, r[1] * c + u[1] * s, r[2] * c + u[2] * s]), norm([u[0] * c - r[0] * s, u[1] * c - r[1] * s, u[2] * c - r[2] * s])] }
  const rel = sub(p, cam.pos)
  const z = dot(rel, f)
  return z > 1e-6 ? dot(rel, r) / z : null
}

/** The figures (mannequins) by their place on screen, left to right; a figure behind the camera goes last (its document order kept). */
export function figuresByScreen<T extends Pick<StageObject, 'kind' | 'transform'>>(objects: T[], cam: Pick<StageCamera, 'pos' | 'target' | 'roll'> | undefined): T[] {
  const figs = objects.filter((o) => o.kind === 'mannequin')
  if (!cam) return figs
  const xs = new Map(figs.map((o) => [o, screenX(o.transform.pos, cam)]))
  return [...figs].sort((a, b) => { const xa = xs.get(a), xb = xs.get(b); return xa == null ? (xb == null ? 0 : 1) : xb == null ? -1 : xa - xb })
}

/** The StageShot's figure mentions: the visible figures bound to a character, left to right ("figure 1" is the left-most). */
export function figureMentions(objects: StageObject[], cam: Pick<StageCamera, 'pos' | 'target' | 'roll'> | undefined): { profile_id: string; figure: string; version?: string }[] {
  return figuresByScreen(objects.filter((o) => o.visible && o.profile_id), cam).map((o) => ({ profile_id: o.profile_id!, figure: o.id, ...(o.version ? { version: o.version } : {}) }))
}

/** Make frame ▸ in Stage (UI4): the speakers bound to the figures in screen order when the counts match — {figure id → profile id}; null
 *  when they do not (the author binds them, a hint says how). A figure already bound to one of the speakers keeps it. */
export function prebind(objects: StageObject[], cam: Pick<StageCamera, 'pos' | 'target' | 'roll'> | undefined, speakers: Pick<Profile, 'id'>[]): Record<string, string> | null {
  const figs = figuresByScreen(objects.filter((o) => o.visible), cam)
  if (!speakers.length || figs.length !== speakers.length) return null
  const ids = speakers.map((p) => p.id)
  const kept = new Map(figs.filter((o) => o.profile_id && ids.includes(o.profile_id)).map((o) => [o.id, o.profile_id!]))
  const left = ids.filter((id) => ![...kept.values()].includes(id))
  const out: Record<string, string> = {}
  for (const o of figs) out[o.id] = kept.get(o.id) ?? left.shift()!
  return out
}
