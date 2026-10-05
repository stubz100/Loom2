// Free transform math (10 §4 Move / Transform): a layer is scaled and rotated about its centre and moved; the
// preview applies the same numbers to the PixiJS sprite, and `resample` bakes them into new pixels on apply.
export interface Xform { nodeId: string; cx: number; cy: number; w: number; h: number; sx: number; sy: number; rot: number }
export interface Pt { x: number; y: number }

export const isIdentity = (t: Xform, x: number, y: number) => Math.abs(t.sx - 1) < 1e-6 && Math.abs(t.sy - 1) < 1e-6 && Math.abs(t.rot) < 1e-6 && Math.abs(t.cx - (x + t.w / 2)) < 0.5 && Math.abs(t.cy - (y + t.h / 2)) < 0.5

/** Local (unscaled, unrotated, centre-relative) → document. */
export function toDoc(t: Xform, lx: number, ly: number): Pt {
  const x = lx * t.sx, y = ly * t.sy
  const c = Math.cos(t.rot), s = Math.sin(t.rot)
  return { x: t.cx + x * c - y * s, y: t.cy + x * s + y * c }
}
/** Document → local (unscaled, unrotated, centre-relative). */
export function toLocal(t: Xform, p: Pt): Pt {
  const dx = p.x - t.cx, dy = p.y - t.cy
  const c = Math.cos(-t.rot), s = Math.sin(-t.rot)
  return { x: dx * c - dy * s, y: dx * s + dy * c }
}
export const corners = (t: Xform): Pt[] => [toDoc(t, -t.w / 2, -t.h / 2), toDoc(t, t.w / 2, -t.h / 2), toDoc(t, t.w / 2, t.h / 2), toDoc(t, -t.w / 2, t.h / 2)]
/** The 8 scale handles with their local signs. */
export const handles = (t: Xform): (Pt & { hx: number; hy: number })[] =>
  [[-1, -1], [0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0]].map(([hx, hy]) => ({ ...toDoc(t, hx * t.w / 2, hy * t.h / 2), hx, hy }))
export function insideQuad(t: Xform, p: Pt): boolean {
  const u = toLocal(t, p)
  return Math.abs(u.x) <= Math.abs(t.sx) * t.w / 2 && Math.abs(u.y) <= Math.abs(t.sy) * t.h / 2
}
export function bbox(pts: Pt[]): { x: number; y: number; w: number; h: number } {
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y)
  const x = Math.floor(Math.min(...xs)), y = Math.floor(Math.min(...ys))
  return { x, y, w: Math.max(1, Math.ceil(Math.max(...xs)) - x), h: Math.max(1, Math.ceil(Math.max(...ys)) - y) }
}

/**
 * Bake the transform into pixels: `src` is a canvas whose pixel (0,0) sits at document (ox, oy). Returns a canvas
 * covering the transformed bounds and that canvas's document position.
 */
export function resample(src: HTMLCanvasElement, t: Xform, ox: number, oy: number): { canvas: HTMLCanvasElement; x: number; y: number } {
  const local = (x: number, y: number) => ({ x: x - t.cx, y: y - t.cy })
  const srcCorners = [local(ox, oy), local(ox + src.width, oy), local(ox + src.width, oy + src.height), local(ox, oy + src.height)].map((l) => toDoc(t, l.x, l.y))
  const bb = bbox(srcCorners)
  const canvas = document.createElement('canvas'); canvas.width = bb.w; canvas.height = bb.h
  const ctx = canvas.getContext('2d')!
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'
  ctx.translate(t.cx - bb.x, t.cy - bb.y)
  ctx.rotate(t.rot)
  ctx.scale(t.sx, t.sy)
  ctx.drawImage(src, ox - t.cx, oy - t.cy)
  return { canvas, x: bb.x, y: bb.y }
}
