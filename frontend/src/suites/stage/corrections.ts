// C2 (D181, propo02 04 §4.3, P8 / P10; proto01_UI2 04 §3.2): the key layer over a figure's clip blocks is corrections — a key inside a
// block holds only the joints the author changed, on top of the block's pose at that frame (a head turn while the walk goes on), and
// successive edits at one frame accumulate; *Apply* lands a clip after the figure's last block, never at the playhead; a clip or a
// template dragged onto a track is read by its drag id. Pure, tested in corrections.test.ts.
import type { StageDoc, StageObject } from '../../api/types'
import type { ObjectKey } from './anim'

/** Half a degree: a joint that moved less is the block's own (the engine's round trip through radians). */
export const JOINT_TOL = 0.5

/** The joints of `pose` that differ from `base`'s beyond the tolerance — a correction's own joints. */
export function diffJoints(base: Record<string, number[]>, pose: Record<string, number[]>, tol = JOINT_TOL): Record<string, number[]> {
  const out: Record<string, number[]> = {}
  for (const [j, v] of Object.entries(pose)) {
    const b = base[j] ?? [0, 0, 0]
    if (v.some((x, i) => Math.abs(x - (b[i] ?? 0)) > tol)) out[j] = [...v]
  }
  return out
}

/** A correction key at `frame`: the joints changed on top of the block (`joints`, merged with the correction already there, the newest
 *  winning), the block's own transform and preset (what the key falls back to should its block go). */
export function correctionKey(frame: number, base: StageObject, joints: Record<string, number[]>, extra: Record<string, number[]> | undefined, existing: ObjectKey | undefined,
  held?: { pins?: unknown; contacts?: unknown; gaze?: unknown }): ObjectKey {
  const had = existing?.correction ? existing.pose?.joints ?? {} : {}
  const hadExtra = existing?.correction ? existing.pose?.extra ?? {} : {}
  // K12: the gaze, the pins and the holds ride the correction (they were written empty: Look at, Pin and Held to did nothing over a clip)
  const pose = { preset: base.pose?.preset ?? 'stand', joints: { ...had, ...joints }, extra: { ...hadExtra, ...(extra ?? {}) }, ground: base.pose?.ground ?? 0,
    pins: held?.pins ?? {}, contacts: held?.contacts ?? {}, gaze: held?.gaze ?? null } as NonNullable<ObjectKey['pose']>
  return { frame, ease: 'ease', correction: true, transform: { pos: [...base.transform.pos], rot: [...base.transform.rot], scale: [...base.transform.scale] }, pose }
}

/** The joints a correction names, for its diamond's words ("head, neck"). */
export const correctionWords = (k: Pick<ObjectKey, 'pose'>): string => [...Object.keys(k.pose?.joints ?? {}).map((j) => j.replace(/^([rl])_/, (_m, s: string) => (s === 'r' ? 'right ' : 'left '))),
  ...(k.pose?.gaze ? ['the gaze'] : []), ...(Object.keys(k.pose?.pins ?? {}).length ? ['pins'] : []), ...(Object.keys(k.pose?.contacts ?? {}).length ? ['holds'] : [])].join(', ') || 'nothing changed'

/** P10: where *Apply* lands a clip — after the figure's last block, else the shot's start; never the playhead. */
export function nextStart(doc: Pick<StageDoc, 'tracks' | 'range'>, oid: string): number {
  const blocks = doc.tracks?.[oid] ?? []
  return blocks.length ? Math.max(doc.range.start, ...blocks.map((b) => b.start + Math.max(1, b.length))) : doc.range.start
}

/** A clip (`clip:<file>:<name>`) or a template (`template:<id>`) dragged onto a track. */
export function clipDrop(id: string): { kind: 'clip'; file: string; clip: string } | { kind: 'template'; id: string } | null {
  if (id.startsWith('template:')) return { kind: 'template', id: id.slice(9) }
  if (!id.startsWith('clip:')) return null
  const rest = id.slice(5), i = rest.indexOf(':')
  return i > 0 ? { kind: 'clip', file: rest.slice(0, i), clip: rest.slice(i + 1) } : null
}
