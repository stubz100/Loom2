// D71 (ArtCraft P11): what a drop of Catalogue items does on each send-to target, as pure functions — the target's `describe` shows the
// verdict on the drag ghost, its `drop` takes `take`. A clip is known by the item's `media` (unknown media counts as an image; the
// server still validates).
import type { DragItem, DragPayload, DropVerdict } from './drag'

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`
const assets = (p: DragPayload | DragItem[]) => (Array.isArray(p) ? p : p.items).filter((i) => i.kind === 'asset')
const images = (items: DragItem[]) => items.filter((i) => !i.media || i.media === 'image')      // a clip or a mesh (P18) is not an image
export const meshes = (items: DragItem[]) => items.filter((i) => i.media === 'mesh')

/** Reference slots: images only, no duplicates, at most `max` in all (the model's `max_refs`). */
export function refDrop(current: string[], p: DragPayload | DragItem[], max: number): { take: string[]; verdict: DropVerdict } {
  const items = assets(p)
  const clips = items.length - images(items).length
  const fresh = [...new Set(images(items).map((i) => i.id))].filter((id) => !current.includes(id))
  const room = Math.max(0, max - current.length)
  const take = fresh.slice(0, room)
  if (!items.length) return { take, verdict: { ok: false } }
  if (clips === items.length) return { take, verdict: { ok: false, reason: clips === 1 ? "A clip can't be a reference" : "Clips can't be references" } }
  if (!fresh.length) return { take, verdict: { ok: false, reason: items.length === 1 ? 'Already a reference' : 'Already references' } }
  if (!room) return { take, verdict: { ok: false, reason: `All ${max} reference slots are full` } }
  const n = current.length + take.length
  const label = take.length === 1 ? `Add as reference ${n} of ${max}` : `Add ${take.length} references (${n} of ${max})`
  const over = fresh.length - take.length
  const notes = [over ? `${over} over the limit` : '', clips ? `${plural(clips, 'clip')} skipped` : ''].filter(Boolean)
  return { take, verdict: { ok: true, label: notes.length ? `${label} · ${notes.join(' · ')}` : label } }
}

/** Animate's start slot and tab: the first image starts, a second image ends. A clip is not a frame: the tab plays it (as the tile
 *  menu's Animate does), the slot refuses it. */
export function startDrop(p: DragPayload | DragItem[], opts: { tab?: boolean } = {}): { start?: string; end?: string; play?: string; verdict: DropVerdict } {
  const items = assets(p)
  if (!items.length) return { verdict: { ok: false } }
  if (items[0].media === 'video') return opts.tab ? { play: items[0].id, verdict: { ok: true, label: 'Play this clip (Performance)' } } : { verdict: { ok: false, reason: "A clip can't be the start frame" } }
  const end = items[1] && items[1].media !== 'video' ? items[1].id : undefined
  return { start: items[0].id, end, verdict: { ok: true, label: end ? 'Set the start and the end frame' : 'Set the start frame' } }
}

/** Animate's end slot: one image. */
export function endDrop(p: DragPayload | DragItem[]): { end?: string; verdict: DropVerdict } {
  const items = assets(p)
  if (!items.length) return { verdict: { ok: false } }
  if (items[0].media === 'video') return { verdict: { ok: false, reason: "A clip can't be the end frame" } }
  return { end: items[0].id, verdict: { ok: true, label: 'Set the end frame' } }
}

/** Opening in Edit (the tab, the empty stage): the first image. */
export function editOpenDrop(p: DragPayload | DragItem[]): { open?: string; verdict: DropVerdict } {
  const items = assets(p)
  const first = images(items)[0]
  if (!items.length) return { verdict: { ok: false } }
  if (!first) return { verdict: { ok: false, reason: 'Clips play at Performance, not in Edit' } }
  return { open: first.id, verdict: { ok: true, label: items.length > 1 ? `Open in Edit (the first of ${items.length})` : 'Open in Edit' } }
}

/** Layers from tiles (the canvas, the layers panel): every image, clips skipped. */
export function layerDrop(p: DragPayload | DragItem[], where?: string): { take: string[]; verdict: DropVerdict } {
  const items = assets(p)
  const take = images(items).map((i) => i.id)
  if (!items.length) return { take, verdict: { ok: false } }
  if (!take.length) return { take, verdict: { ok: false, reason: items.length === 1 ? "A clip can't be a layer" : "Clips can't be layers" } }
  const skipped = items.length - take.length
  const label = `Add ${take.length === 1 ? 'as a layer' : `${take.length} layers`}${where ? ` ${where}` : ''}`
  return { take, verdict: { ok: true, label: skipped ? `${label} · ${plural(skipped, 'clip')} skipped` : label } }
}

/** Animate's beats: every item becomes a beat. */
/** P17: the sequence lane — clips only (by asset or clip id); each goes to the end of the lane. */
export function laneDrop<C extends { id: string; asset_id?: string | null }>(p: DragPayload | DragItem[], clips: C[]): { take: C[]; verdict: DropVerdict } {
  const items = assets(p)
  if (!items.length) return { take: [], verdict: { ok: false } }
  const take = items.map((i) => clips.find((c) => c.asset_id === i.id || c.id === i.id)).filter((c): c is C => !!c)
  if (!take.length) return { take, verdict: { ok: false, reason: 'Only clips go on the lane' } }
  return { take, verdict: { ok: true, label: take.length === 1 ? 'Add to the end of the cut' : `Add ${take.length} clips to the cut` } }
}

/** P14: the Angle tab's source slot — one image; several drop the first; a clip is refused. */
export function angleDrop(p: DragPayload | DragItem[]): DropVerdict {
  const items = assets(p)
  if (!items.length) return { ok: false }
  if (!images(items).length) return { ok: false, reason: items.length === 1 ? "A clip can't get a new angle" : "Clips can't get a new angle" }
  return { ok: true, label: items.length > 1 ? 'Use the first image as the source' : 'Use as the source' }
}

/** ST3: the Shot tab's reference deck — images only; clips are refused. */
export function shotRefDrop(p: DragPayload | DragItem[], room: number): DropVerdict {
  const items = assets(p)
  if (!items.length) return { ok: false }
  const imgs = images(items)
  if (!imgs.length) return { ok: false, reason: items.length === 1 ? "A clip can't be a reference" : "Clips can't be references" }
  if (room <= 0) return { ok: false, reason: 'The deck is full for this method' }
  const n = Math.min(room, imgs.length)
  return { ok: true, label: n === 1 ? 'Add as a reference' : `Add ${n} references` }
}

export function beatDrop(p: DragPayload | DragItem[]): { take: string[]; verdict: DropVerdict } {
  const take = assets(p).map((i) => i.id)
  return { take, verdict: take.length ? { ok: true, label: take.length === 1 ? 'Add a beat' : `Add ${take.length} beats` } : { ok: false } }
}
