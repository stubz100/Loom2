// D165: a character layer's window and head box as keyframed boxes in the frame's pixels — the client's twin of
// orchestrator/loom2/boxes.py (keep them alike): the keys interpolate in straight lines, the first and the last held.

export type BoxKind = 'window' | 'head'
/** A key: the box's centre and its size — a window's height (its width follows Wan's portrait), a head box's side. */
export interface BoxKey { frame: number; cx: number; cy: number; h?: number; side?: number }
export interface Box { cx: number; cy: number; size: number }

export const sizeKey = (kind: BoxKind): 'h' | 'side' => (kind === 'window' ? 'h' : 'side')
const sizeOf = (k: BoxKey, kind: BoxKind): number => (kind === 'window' ? k.h : k.side) ?? 0
export const MIN_SIZE = 8

/** The box at a frame from the keys (null without keys). */
export function boxAt(keys: BoxKey[], kind: BoxKind, frame: number): Box | null {
  if (!keys.length) return null
  const ks = [...keys].sort((a, b) => a.frame - b.frame)
  if (frame <= ks[0].frame) return { cx: ks[0].cx, cy: ks[0].cy, size: sizeOf(ks[0], kind) }
  const last = ks[ks.length - 1]
  if (frame >= last.frame) return { cx: last.cx, cy: last.cy, size: sizeOf(last, kind) }
  const j = ks.findIndex((k) => k.frame > frame)
  const a = ks[j - 1], b = ks[j], t = (frame - a.frame) / (b.frame - a.frame)
  return { cx: a.cx + (b.cx - a.cx) * t, cy: a.cy + (b.cy - a.cy) * t, size: sizeOf(a, kind) + (sizeOf(b, kind) - sizeOf(a, kind)) * t }
}

/** The rectangle [x, y, w, h] of a box: a window keeps the shape of `win` (Wan's 480×848), a head box is square. */
export function rectOf(b: Box, kind: BoxKind, win: [number, number]): [number, number, number, number] {
  const w = kind === 'window' ? b.size * win[0] / win[1] : b.size
  return [b.cx - w / 2, b.cy - b.size / 2, w, b.size]
}

/** The keys with one at `frame` set to the box (replacing a key there). */
export function upsert(keys: BoxKey[], kind: BoxKind, frame: number, b: Box): BoxKey[] {
  const key: BoxKey = { frame, cx: round(b.cx), cy: round(b.cy), [sizeKey(kind)]: round(Math.max(MIN_SIZE, b.size)) }
  return [...keys.filter((k) => k.frame !== frame), key].sort((a, c) => a.frame - c.frame)
}

/** The keys without the one at `frame`. */
export const removeAt = (keys: BoxKey[], frame: number): BoxKey[] => keys.filter((k) => k.frame !== frame)

/** A box moved by (dx, dy), or resized about its centre so a corner meets (px, py) — the shape kept. */
export function moved(b: Box, dx: number, dy: number): Box { return { ...b, cx: b.cx + dx, cy: b.cy + dy } }
export function resized(b: Box, kind: BoxKind, px: number, py: number, win: [number, number]): Box {
  const byWidth = Math.abs(px - b.cx) * 2 * (kind === 'window' ? win[1] / win[0] : 1)
  return { ...b, size: Math.max(MIN_SIZE, byWidth, Math.abs(py - b.cy) * 2) }
}

const round = (v: number): number => Math.round(v * 100) / 100
