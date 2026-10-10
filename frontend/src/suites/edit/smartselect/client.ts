// D59: the editor's side of the smart-select Worker — one Worker for the session, the document image sent once per (source,
// revision), and "latest wins" for Quick Selection previews (a preview asked for while one runs replaces any queued one).
import type { Req } from './worker'

type WithoutId<T> = T extends unknown ? Omit<T, 'id'> : never
type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void }
let worker: Worker | null = null
let seq = 0
const pending = new Map<number, Pending>()
let sentKey = ''

function get(): Worker {
  if (worker) return worker
  worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })
  worker.onmessage = (e: MessageEvent<{ id: number; error?: string }>) => {
    const p = pending.get(e.data.id)
    if (!p) return
    pending.delete(e.data.id)
    if (e.data.error) p.reject(new Error(e.data.error)); else p.resolve(e.data)
  }
  worker.onerror = (e) => { for (const p of pending.values()) p.reject(new Error(e.message || 'smart-select worker failed')); pending.clear() }
  return worker
}
function call<T>(m: WithoutId<Req>, transfer: Transferable[] = []): Promise<T> {
  const id = ++seq
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: unknown) => void, reject })
    get().postMessage({ ...m, id }, transfer)
  })
}

/** Make sure the Worker holds the image `key` names; `rgba` is only built when it does not. */
export async function ensureImage(key: string, rgba: () => { data: Uint8ClampedArray; w: number; h: number }): Promise<void> {
  if (sentKey === key) return
  const img = rgba()
  const buf = img.data.slice().buffer
  sentKey = key
  try { await call({ op: 'image', key, w: img.w, h: img.h, rgba: buf }, [buf]) } catch (e) { sentKey = ''; throw e }
}
export function forgetImage(): void { sentKey = '' }
/** Starts the Worker and waits for its module (csp_check's `wasmprobe=1`: WebAssembly must instantiate under the production CSP). */
export async function probe(): Promise<void> { await call({ op: 'key' }) }

export interface QuickRegion { box: [number, number, number, number]; mask: Uint8Array; ms: number }
/** PhotoCraft's quick_select over the stroke's points (document px) with the brush diameter; null when it misses the image. */
export async function quickSelect(points: number[], size: number): Promise<QuickRegion | null> {
  const r = await call<{ ok: boolean; box: [number, number, number, number]; mask: Uint8Array; ms: number }>({ op: 'quick', points, size })
  return r.ok ? { box: r.box, mask: r.mask, ms: r.ms } : null
}

/** Latest-wins previews: while one runs, only the newest request waits; older ones resolve null. */
let previewBusy = false
let previewNext: { points: number[]; size: number; resolve: (r: QuickRegion | null) => void } | null = null
export function quickPreview(points: number[], size: number): Promise<QuickRegion | null> {
  return new Promise((resolve) => {
    if (previewBusy) { previewNext?.resolve(null); previewNext = { points, size, resolve }; return }
    previewBusy = true
    const run = (pts: number[], sz: number, done: (r: QuickRegion | null) => void) => {
      quickSelect(pts, sz).then(done, () => done(null)).finally(() => {
        const n = previewNext; previewNext = null
        if (n) run(n.points, n.size, n.resolve); else previewBusy = false
      })
    }
    run(points, size, resolve)
  })
}

export interface MagneticSettings { width: number; contrast: number }
export async function trace(from: [number, number], to: [number, number], guide: number[], s: MagneticSettings): Promise<number[]> {
  const r = await call<{ path: Float64Array }>({ op: 'trace', from, to, guide, width: s.width, contrast: s.contrast })
  return Array.from(r.path)
}
export async function snap(p: [number, number], s: MagneticSettings): Promise<[number, number]> {
  const r = await call<{ point: [number, number] }>({ op: 'snap', p, width: s.width, contrast: s.contrast })
  return r.point
}
