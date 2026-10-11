// Album page geometry (D34, proto01_design/01 §6c), pure: page ↔ screen coordinates, fit, the marquee's hit test, resize and z-order.
// PageView.tsx owns the gestures and the state; the arithmetic lives here so the unit suite (D68) can check it without a DOM.

export const CARD_RATIO = 0.8                                       // groups.py CARD_RATIO: a card is drawn in w × 0.8w
export const MIN_ITEM_W = 48                                        // the corner handle never shrinks an item below this (page px)
export const EMPTY_VIEW: View = { x: 40, y: 40 }                    // where an empty page puts its origin, at zoom 1

/** The page's pan: where page (0, 0) sits inside the host, in screen px. */
export interface View { x: number; y: number }
export interface Placed { kind: string; id: string; x: number; y: number; w: number }
export interface Rect { left: number; top: number }
export interface Marquee { x0: number; y0: number; x1: number; y1: number }
type HeightOf = (it: Placed) => number

/** An item's drawn height: a group card is w × CARD_RATIO, a photo keeps its aspect (4:3 while its size is unknown). */
export function itemHeight(it: { kind: string; w: number }, asset?: { w?: number | null; h?: number | null }): number {
  if (it.kind === 'group') return it.w * CARD_RATIO
  return asset?.w && asset?.h ? it.w * (asset.h / asset.w) : it.w * 0.75
}

/** A client point (pointer event) as page coordinates, given the host's client rect, the pan and the zoom. */
export function toPage(cx: number, cy: number, host: Rect, view: View, z: number): { x: number; y: number } {
  return { x: (cx - host.left - view.x) / z, y: (cy - host.top - view.y) / z }
}

/** The zoom (0.1 … 1, never enlarging) and pan that show every item inside a `width` × `height` host with a 32 px margin, centred
 *  horizontally and at least 24 px from the top; an empty page shows its origin at zoom 1. */
export function fitView(items: Placed[], heightOf: HeightOf, width: number, height: number): { zoom: number; view: View } {
  if (!items.length) return { zoom: 1, view: { ...EMPTY_VIEW } }
  const x0 = Math.min(...items.map((i) => i.x)), y0 = Math.min(...items.map((i) => i.y))
  const x1 = Math.max(...items.map((i) => i.x + i.w)), y1 = Math.max(...items.map((i) => i.y + heightOf(i)))
  const s = Math.max(0.1, Math.min(1, (width - 64) / (x1 - x0 || 1), (height - 64) / (y1 - y0 || 1)))
  return { zoom: s, view: { x: (width - (x1 - x0) * s) / 2 - x0 * s, y: Math.max(24, (height - (y1 - y0) * s) / 2) - y0 * s } }
}

/** The items a marquee (host-relative screen px, any corner order) touches: any overlap counts, touching an edge does not. */
export function marqueeHits<T extends Placed>(items: T[], m: Marquee, view: View, z: number, heightOf: (it: T) => number): T[] {
  const [ax, bx] = [Math.min(m.x0, m.x1), Math.max(m.x0, m.x1)].map((v) => (v - view.x) / z)
  const [ay, by] = [Math.min(m.y0, m.y1), Math.max(m.y0, m.y1)].map((v) => (v - view.y) / z)
  return items.filter((i) => i.x < bx && i.x + i.w > ax && i.y < by && i.y + heightOf(i) > ay)
}

/** The corner handle: a horizontal pointer move of `dx` screen px at zoom `z` resizes the width, never below MIN_ITEM_W. */
export function resizedWidth(w0: number, dx: number, z: number): number {
  return Math.max(MIN_ITEM_W, w0 + dx / z)
}

/** Bring to front / Send to back: the selected items, in their order, get consecutive z values above every item (front) or below
 *  every item (back); zero counts as present, so the first item brought forward on a fresh page lands at 1 and one sent back at −1.
 *  (Before D68 the back case ended on the old minimum when that was ≤ 0, tying with the item already at the back: a second Send to
 *  back, or items all at z 0, left the order to chance.) */
export function restack<T extends { z: number }>(items: T[], sel: T[], front: boolean): T[] {
  let z0 = front ? Math.max(0, ...items.map((i) => i.z)) : Math.min(0, ...items.map((i) => i.z)) - sel.length - 1
  return sel.map((i) => ({ ...i, z: ++z0 }))
}

/** A zoom by factor `k` that keeps the host point (cx, cy) still. */
export function zoomAbout(v: View, cx: number, cy: number, k: number): View {
  return { x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }
}
