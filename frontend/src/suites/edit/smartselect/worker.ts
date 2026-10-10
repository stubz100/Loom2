// D59: the smart-select Worker — PhotoCraft's Quick Selection and Magnetic Lasso (photocraft-algo @ b37bff98, MIT OR Apache-2.0) as
// WebAssembly (pcwasm.wasm, built by scripts/build_pcwasm.py from frontend/wasm/pcwasm). One module instance, single-threaded; the
// document image is set once per (source, revision) and kept; requests run in arrival order.
/// <reference lib="webworker" />
import wasmUrl from './pcwasm.wasm?url'

interface Exports {
  memory: WebAssembly.Memory
  alloc(n: number): number
  dealloc(p: number, n: number): void
  set_image(p: number, w: number, h: number): void
  quick(p: number, n: number, size: number): number
  region_box(i: number): number
  region_mask(): number
  trace_guided(x0: number, y0: number, x1: number, y1: number, guide: number, n: number, width: number, contrast: number): number
  snap(x: number, y: number, width: number, contrast: number): number
  path_ptr(): number
}

let X: Exports | null = null
const ready = (async () => {
  const res = await fetch(wasmUrl)
  const { instance } = await WebAssembly.instantiate(await res.arrayBuffer(), {})
  X = instance.exports as unknown as Exports
})()
let imageKey = ''

export type Req =
  | { op: 'image'; id: number; key: string; w: number; h: number; rgba: ArrayBuffer }
  | { op: 'quick'; id: number; points: number[]; size: number }
  | { op: 'trace'; id: number; from: [number, number]; to: [number, number]; guide: number[]; width: number; contrast: number }
  | { op: 'snap'; id: number; p: [number, number]; width: number; contrast: number }
  | { op: 'key'; id: number }

const reply = (m: unknown, transfer: Transferable[] = []) => (self as unknown as DedicatedWorkerGlobalScope).postMessage(m, transfer)

self.onmessage = async (e: MessageEvent<Req>) => {
  const m = e.data
  try {
    await ready
    const x = X!
    const t0 = performance.now()
    if (m.op === 'key') { reply({ id: m.id, key: imageKey }); return }
    if (m.op === 'image') {
      const n = m.rgba.byteLength
      const p = x.alloc(n)
      new Uint8Array(x.memory.buffer, p, n).set(new Uint8Array(m.rgba))
      x.set_image(p, m.w, m.h)
      x.dealloc(p, n)
      imageKey = m.key
      reply({ id: m.id, ms: performance.now() - t0 })
      return
    }
    if (m.op === 'quick') {
      const n = m.points.length
      const p = x.alloc(n * 4)
      new Float32Array(x.memory.buffer, p, n).set(m.points)
      const ok = x.quick(p, n / 2, m.size)
      x.dealloc(p, n * 4)
      if (!ok) { reply({ id: m.id, ok: false, ms: performance.now() - t0 }); return }
      const box = [0, 1, 2, 3].map((i) => x.region_box(i)) as [number, number, number, number]
      const len = (box[2] - box[0]) * (box[3] - box[1])
      const mask = new Uint8Array(len)
      mask.set(new Uint8Array(x.memory.buffer, x.region_mask(), len))
      reply({ id: m.id, ok: true, box, mask, ms: performance.now() - t0 }, [mask.buffer])
      return
    }
    if (m.op === 'trace') {
      const g = m.guide.length
      const p = g ? x.alloc(g * 8) : 0
      if (g) new Float64Array(x.memory.buffer, p, g).set(m.guide)
      const n = x.trace_guided(m.from[0], m.from[1], m.to[0], m.to[1], p, g / 2, m.width, m.contrast)
      if (g) x.dealloc(p, g * 8)
      const path = new Float64Array(n * 2)
      path.set(new Float64Array(x.memory.buffer, x.path_ptr(), n * 2))
      reply({ id: m.id, path, ms: performance.now() - t0 }, [path.buffer])
      return
    }
    if (m.op === 'snap') {
      const ok = x.snap(m.p[0], m.p[1], m.width, m.contrast)
      const pt = ok ? Array.from(new Float64Array(x.memory.buffer, x.path_ptr(), 2)) : m.p
      reply({ id: m.id, point: pt, ms: performance.now() - t0 })
    }
  } catch (err) {
    reply({ id: m.id, error: String(err) })
  }
}
