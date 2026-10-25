// D135 (PF1, proto01_animate 31 §4h): the plate projected and filled — Stage's part. From the plate's still (keyframe 0) Stage walks the
// camera path: each frame probed against the keyframes before it (the projector's coverage: the cosine at which a keyframe saw each pixel),
// a pixel *bad* when no keyframe saw it or the frame sees it more than twice as head-on as the best one did below 70° (it would be
// magnified); the first frame whose bad share passes 8 % (and the last frame) is the next keyframe — its composite (the most head-on
// keyframe per pixel) and its bad mask go up, and the server fills them (an Edit document's Fill, `POST /finals/{fid}/plate/keys`). With
// the heal on (Q29), each span's frame with the most bad pixels left becomes a small keyframe of its own until none keeps more than 0.5 %.
// Then every frame is its neighbouring keyframes projected, the most head-on per pixel, and the frames go up as the plate's own. One step
// per call (the finals' poll drives it), resumable from the keyframes on the server.
import { api, http, sha256Hex, unwrap } from '../../api/client'
import type { Final, StageCamera, StageDoc } from '../../api/types'
import { st } from './stageStore'

export const KEY_BAD = 0.08                         // E35d: a frame past this share of bad pixels is the next keyframe
export const HEAL_LEFT = 0.005                      // Q29: the heal goes on until no frame keeps more than this
export const SEEN = 0.05                            // a cosine below this: not seen (outside a keyframe's view or edge-on)
export const GRAZE = 0.34                           // seen below 70° …
export const MAG = 2                                // … and more than twice as head-on from the frame: magnified, bad
export const STACK = 3                              // the keyframes a frame is made from
const PROBE: [number, number] = [320, 180]

export interface Key { frame: number; asset_id: string | null; filled?: number; job_id?: string | null; heal?: boolean }
export interface Frame { cam: StageCamera; doc: StageDoc }

// ---- the pure picks ---------------------------------------------------------------------------------------------------------------
/** The keyframes a frame at `t` is made from: those at or before `before`, the most recent first. */
export function stackBefore(keys: number[], before: number, n = STACK): number[] {
  return keys.filter((k) => k <= before).sort((a, b) => b - a).slice(0, n)
}

/** A frame between keyframes: the nearer of the two around it first, the other, then the ones before (the first is the colour where none saw). */
export function stackAround(keys: number[], t: number, n = STACK): number[] {
  const sorted = [...keys].sort((a, b) => a - b)
  const a = sorted.filter((k) => k <= t).at(-1) ?? sorted[0]
  const b = sorted.find((k) => k > t)
  const pair = b === undefined ? [a] : t - a <= b - t ? [a, b] : [b, a]
  return [...pair, ...sorted.filter((k) => k < a).reverse()].slice(0, n)
}

/** Per pixel, the layer that saw it most head-on and its cosine (0–255): `covers` are RGBA coverage renders (grey in R). */
export function bestOf(covers: Uint8ClampedArray[], pixels: number): { best: Uint8Array; who: Int8Array } {
  const best = new Uint8Array(pixels), who = new Int8Array(pixels).fill(-1)
  covers.forEach((c, li) => { for (let p = 0; p < pixels; p++) { const v = c[p * 4]; if (v > best[p]) { best[p] = v; who[p] = li } } })
  return { best, who }
}

/** The bad pixels: seen by none, or seen below GRAZE by the best while the frame itself (`self`, its own coverage) sees them MAG times as head-on. */
export function badMask(best: Uint8Array, self: Uint8ClampedArray): { mask: Uint8Array; share: number } {
  const mask = new Uint8Array(best.length)
  let n = 0
  for (let p = 0; p < best.length; p++) {
    const b = best[p], m = self[p * 4]
    if (b < SEEN * 255 || (b < GRAZE * 255 && m > MAG * Math.max(b, 1))) { mask[p] = 255; n++ }
  }
  return { mask, share: n / Math.max(1, best.length) }
}

/** The composite: each pixel from the layer that saw it most head-on; where none saw it, the first layer's (clamped) colour. */
export function compose(colours: Uint8ClampedArray[], best: Uint8Array, who: Int8Array): Uint8ClampedArray<ArrayBuffer> {
  const out = new Uint8ClampedArray(colours[0].length)
  out.set(colours[0])
  for (let p = 0; p < best.length; p++) if (who[p] > 0 && best[p] >= SEEN * 255) out.set(colours[who[p]].subarray(p * 4, p * 4 + 4), p * 4)
  return out
}

/** Q29: the frame to heal — in the span with the most bad pixels left (above HEAL_LEFT), its worst frame; null when none is left. */
export function healPick(bad: (number | null)[], keys: number[]): number | null {
  let pick: number | null = null, worst = HEAL_LEFT
  bad.forEach((b, t) => { if (b !== null && b > worst && !keys.includes(t)) { worst = b; pick = t } })
  return pick
}

// ---- Stage's part (WebGL) ---------------------------------------------------------------------------------------------------------
const images: Record<string, Promise<HTMLImageElement>> = {}
function load(id: string): Promise<HTMLImageElement> {
  return images[id] ??= new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('a keyframe did not load'))
    img.src = api.assetUrl(id)
  })
}
async function pixels(blob: Blob, w: number, h: number): Promise<ImageData> {
  const c = new OffscreenCanvas(w, h), g = c.getContext('2d')!
  g.drawImage(await createImageBitmap(blob), 0, 0)
  return g.getImageData(0, 0, w, h)
}
async function png(data: Uint8ClampedArray<ArrayBuffer>, w: number, h: number): Promise<Blob> {
  const c = new OffscreenCanvas(w, h)
  c.getContext('2d')!.putImageData(new ImageData(data, w, h), 0, 0)
  return c.convertToBlob({ type: 'image/png' })
}
async function upload(blob: Blob): Promise<string> {
  const sha = await sha256Hex(await blob.arrayBuffer())
  await api.putBlob(sha, blob)
  return sha
}

interface Made { colours: Uint8ClampedArray[][]; covers: Uint8ClampedArray[][]; selves: Uint8ClampedArray[] }
/** The stack's keyframes projected into the frames: per layer its colour (unless only probing) and coverage; each frame's own coverage. */
async function project(frames: Frame[], idx: number[], w: number, h: number, stack: { asset: string; frame: number }[], restore: StageDoc, colour: boolean, own = true): Promise<Made> {
  const project = st().plateProjector
  if (!project) throw new Error('the stage is not ready to render')
  const sel = idx.map((i) => frames[i])
  const colours: Uint8ClampedArray[][] = [], covers: Uint8ClampedArray[][] = []
  for (const k of stack) {
    const img = await load(k.asset)
    const aspect = img.naturalWidth / img.naturalHeight
    covers.push(await Promise.all((await project(sel, w, h, img, frames[k.frame].cam, aspect, restore, undefined, true)).map(async (b) => (await pixels(b, w, h)).data)))
    if (colour) colours.push(await Promise.all((await project(sel, w, h, img, frames[k.frame].cam, aspect, restore)).map(async (b) => (await pixels(b, w, h)).data)))
  }
  const selves: Uint8ClampedArray[] = []
  const any = await load(stack[0].asset)                                // only the frame's own cosine is read: any picture
  if (own) for (const fr of sel) selves.push((await pixels((await project([fr], w, h, any, fr.cam, w / h, restore, undefined, true))[0], w, h)).data)
  return { colours, covers, selves }
}

export type FillState = { step: 'waiting' } | { step: 'key'; frame: number; heal: boolean } | { step: 'done'; final: Final }

/** One step of filling the plate: wait for a keyframe's Fill, place and send the next keyframe (or a heal), or make the frames. */
export async function fillStep(f: Final, frames: Frame[], restore: StageDoc, onProgress?: (what: string) => void): Promise<FillState> {
  const plate = f.layers.find((l) => l.id === 'plate')
  if (!plate?.still_asset_id) throw new Error('the plate has no still yet')
  const made = (plate.keys as unknown as Key[]) ?? []
  if (made.some((k) => !k.asset_id)) return { step: 'waiting' }
  const keyAsset: Record<number, string> = { 0: plate.still_asset_id }
  for (const k of made) keyAsset[k.frame] = k.asset_id!
  const keys = Object.keys(keyAsset).map(Number).sort((a, b) => a - b)
  const n = frames.length
  const last = keys.at(-1)!
  const still = await load(plate.still_asset_id)
  const [KW, KH] = [still.naturalWidth, still.naturalHeight]
  const stackOf = (frs: number[]) => frs.map((j) => ({ asset: keyAsset[j], frame: j }))
  const sendKey = async (t: number, stack: number[], heal: boolean): Promise<FillState> => {
    onProgress?.(`keyframe at frame ${t}${heal ? ' (heal)' : ''}`)
    const m = await project(frames, [t], KW, KH, stackOf(stack), restore, true)
    const px = KW * KH
    const { best, who } = bestOf(m.covers.map((c) => c[0]), px)
    const { mask } = badMask(best, m.selves[0])
    const comp = compose(m.colours.map((c) => c[0]), best, who)
    const grey = new Uint8ClampedArray(px * 4)
    for (let p = 0; p < px; p++) { const v = mask[p]; grey[p * 4] = v; grey[p * 4 + 1] = v; grey[p * 4 + 2] = v; grey[p * 4 + 3] = 255 }
    const [image, maskSha] = [await upload(await png(comp, KW, KH)), await upload(await png(grey, KW, KH))]
    await unwrap(http.POST('/finals/{fid}/plate/keys', { params: { path: { fid: f.id } }, body: { frame: t, image, mask: maskSha, heal } }))
    return { step: 'key', frame: t, heal }
  }
  if (last < n - 1) {                                                   // place the next keyframe: walk on from the last one
    for (let t = last + 1; t < n; t++) {
      onProgress?.(`probing frame ${t} of ${n - 1}`)
      const m = await project(frames, [t], PROBE[0], PROBE[1], stackOf(stackBefore(keys, last)), restore, false)
      const { best } = bestOf(m.covers.map((c) => c[0]), PROBE[0] * PROBE[1])
      if (badMask(best, m.selves[0]).share > KEY_BAD || t === n - 1) return sendKey(t, stackBefore(keys, last), false)
    }
  }
  if (plate.heal) {                                                     // Q29: heal what no keyframe saw in the frames between
    const bad: (number | null)[] = []
    for (let t = 0; t < n; t++) {
      if (keys.includes(t)) { bad.push(null); continue }
      onProgress?.(`checking frame ${t} for the heal`)
      const m = await project(frames, [t], PROBE[0], PROBE[1], stackOf(stackAround(keys, t)), restore, false)
      bad.push(badMask(bestOf(m.covers.map((c) => c[0]), PROBE[0] * PROBE[1]).best, m.selves[0]).share)
    }
    const pick = healPick(bad, keys)
    if (pick !== null) return sendKey(pick, stackAround(keys, pick), true)
  }
  const { w, h } = f.size
  const shas: string[] = new Array(n)
  for (let t = 0; t < n;) {                                             // the frames: their neighbouring keyframes, the most head-on per pixel
    const stack = stackAround(keys, t)                                  // the run of frames made from the same keyframes, projected together
    const run: number[] = []
    for (let u = t; u < n && run.length < 12 && stackAround(keys, u).join() === stack.join(); u++) run.push(u)
    onProgress?.(`frames ${t + 1}–${t + run.length} of ${n}`)
    const m = await project(frames, run, w, h, stackOf(stack), restore, true, false)
    for (let i = 0; i < run.length; i++) {
      const { best, who } = bestOf(m.covers.map((c) => c[i]), w * h)
      shas[run[i]] = await upload(await png(compose(m.colours.map((c) => c[i]), best, who), w, h))
    }
    t += run.length
  }
  const final = await unwrap(http.PUT('/finals/{fid}/layers/{lid}/frames', { params: { path: { fid: f.id, lid: 'plate' } }, body: { frames: shas } }))
  return { step: 'done', final }
}
